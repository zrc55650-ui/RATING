#!/usr/bin/env python3
"""Validate and apply the completed blind disagreement re-review."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AUDIT_DIR = ROOT / "workstream_A_judge_audit"
MANIFEST = AUDIT_DIR / "judge_audit_sampling_manifest.csv"
SOURCE = AUDIT_DIR / "judge_audit_adjudication_completed_pre_disagreement_review.csv"
CANONICAL = AUDIT_DIR / "judge_audit_adjudicated.csv"
REVIEW = AUDIT_DIR / "judge_audit_disagreement_review_completed.csv"
COMPARISON = AUDIT_DIR / "judge_audit_disagreement_review_comparison.csv"
REPORT = AUDIT_DIR / "judge_audit_disagreement_review_report.md"

HUMAN_FIELDS = [
    "human_label",
    "human_final_answer_normalized",
    "human_reason",
    "human_tool_needed",
    "human_confidence",
]
REQUIRED_REVIEW_FIELDS = [
    "audit_id",
    "annotation_instruction",
    "question",
    "ground_truth_answer",
    "candidate_output",
    *HUMAN_FIELDS,
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(
    path: Path, fieldnames: list[str], rows: list[dict[str, object]]
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def human_correct(label: str) -> bool:
    return label.strip() == "Correct"


def judge_correct(label: str) -> bool:
    return label.strip() in {"1", "Correct", "correct"}


def main() -> None:
    source_fields, source_rows = read_csv(SOURCE)
    review_fields, review_rows = read_csv(REVIEW)
    _, manifest_rows = read_csv(MANIFEST)

    if len(source_rows) != 200 or len(manifest_rows) != 200:
        raise ValueError("The source and manifest must each contain 200 rows")
    if review_fields != REQUIRED_REVIEW_FIELDS:
        raise ValueError(
            f"Unexpected review fields: {review_fields}; "
            f"expected {REQUIRED_REVIEW_FIELDS}"
        )
    if len(review_rows) != 28:
        raise ValueError(f"Expected 28 reviewed rows; got {len(review_rows)}")
    if len({row["audit_id"] for row in review_rows}) != 28:
        raise ValueError("Review contains duplicate audit IDs")
    for field in ["human_label", "human_reason", "human_tool_needed", "human_confidence"]:
        blank = [
            row["audit_id"]
            for row in review_rows
            if not row[field].strip()
        ]
        if blank:
            raise ValueError(f"Blank {field} values for: {blank}")

    source_by_id = {row["audit_id"]: row for row in source_rows}
    manifest_by_id = {row["audit_id"]: row for row in manifest_rows}
    if set(source_by_id) != set(manifest_by_id):
        raise ValueError("Source and manifest audit IDs do not match")

    expected_ids = {
        audit_id
        for audit_id, source in source_by_id.items()
        if human_correct(source["human_label"])
        != judge_correct(manifest_by_id[audit_id]["judge_label"])
    }
    review_ids = {row["audit_id"] for row in review_rows}
    if len(expected_ids) != 28 or review_ids != expected_ids:
        raise ValueError("Review IDs are not exactly the 28 original disagreements")

    review_by_id = {row["audit_id"]: row for row in review_rows}
    comparison_rows: list[dict[str, object]] = []
    exact_changes = 0
    binary_changes = 0
    now_agree = 0
    for audit_id in sorted(review_ids):
        before = source_by_id[audit_id]
        after = review_by_id[audit_id]
        machine = manifest_by_id[audit_id]
        exact_changed = before["human_label"] != after["human_label"]
        binary_changed = human_correct(before["human_label"]) != human_correct(
            after["human_label"]
        )
        agrees_after = human_correct(after["human_label"]) == judge_correct(
            machine["judge_label"]
        )
        exact_changes += int(exact_changed)
        binary_changes += int(binary_changed)
        now_agree += int(agrees_after)
        comparison_rows.append(
            {
                "audit_id": audit_id,
                "condition": machine["condition"],
                "judge_label": machine["judge_label"],
                "initial_human_label": before["human_label"],
                "review_human_label": after["human_label"],
                "exact_label_changed": str(exact_changed).lower(),
                "binary_correctness_changed": str(binary_changed).lower(),
                "judge_human_agree_after_review": str(agrees_after).lower(),
                "initial_human_reason": before["human_reason"],
                "review_human_reason": after["human_reason"],
            }
        )

    for row in source_rows:
        reviewed = review_by_id.get(row["audit_id"])
        if reviewed:
            for field in HUMAN_FIELDS:
                row[field] = reviewed[field]
    write_csv(CANONICAL, source_fields, source_rows)

    comparison_fields = [
        "audit_id",
        "condition",
        "judge_label",
        "initial_human_label",
        "review_human_label",
        "exact_label_changed",
        "binary_correctness_changed",
        "judge_human_agree_after_review",
        "initial_human_reason",
        "review_human_reason",
    ]
    write_csv(COMPARISON, comparison_fields, comparison_rows)

    report = f"""# Judge Audit disagreement re-review

- Records independently re-reviewed: **28/28**
- Exact human labels changed: **{exact_changes}/28**
- Binary correctness labels changed: **{binary_changes}/28**
- Reviewed disagreements that now agree with the automated judge: **{now_agree}/28**
- Original 200-row adjudication preserved as `{SOURCE.name}`
- Updated 200-row adjudication written to `{CANONICAL.name}`

This report records the blind re-review result; it does not itself determine the
Judge Audit gate. Run `analyze_judge_audit.py` to recompute the gate from all 200
records.
"""
    REPORT.write_text(report, encoding="utf-8", newline="\n")

    print(
        json.dumps(
            {
                "reviewed": len(review_rows),
                "exact_label_changes": exact_changes,
                "binary_correctness_changes": binary_changes,
                "reviewed_now_agree": now_agree,
                "canonical_sha256": digest(CANONICAL),
                "source_sha256": digest(SOURCE),
                "comparison": str(COMPARISON),
                "report": str(REPORT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
