#!/usr/bin/env python3
"""Summarize the adjudicated Judge Audit and evaluate the preregistered gate."""

from __future__ import annotations

import csv
import html
import itertools
import json
from pathlib import Path

from analysis_common import ROOT, read_csv


AUDIT_DIR = ROOT / "workstream_A_judge_audit"
SOURCE = AUDIT_DIR / "judge_audit_adjudicated.csv"
MANIFEST = AUDIT_DIR / "judge_audit_sampling_manifest.csv"
REPORT = AUDIT_DIR / "judge_audit_report.md"
SVG = AUDIT_DIR / "judge_audit_confusion_matrix.svg"


def human_correct(label: str) -> bool:
    return label.strip() == "Correct"


def judge_correct(label: str) -> bool:
    return label.strip() == "1"


def grouped_metrics(rows: list[dict], key: str) -> list[dict]:
    result = []
    ordered = sorted(rows, key=lambda row: str(row.get(key, "")))
    for value, group in itertools.groupby(
        ordered, key=lambda row: str(row.get(key, ""))
    ):
        materialized = list(group)
        count = len(materialized)
        judge_positive = sum(row["judge_correct"] for row in materialized)
        human_positive = sum(row["human_correct"] for row in materialized)
        agreement = sum(row["agreement"] for row in materialized)
        result.append(
            {
                key: value or "(not applicable)",
                "n": count,
                "agreement": agreement / count,
                "judge_correct_rate": judge_positive / count,
                "human_correct_rate": human_positive / count,
                "bias_pp": 100 * (judge_positive - human_positive) / count,
            }
        )
    return result


def markdown_table(rows: list[dict], key: str) -> list[str]:
    lines = [
        f"| {key} | N | Agreement | Judge correct | Human correct | Bias (pp) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row[key]} | {row['n']} | {row['agreement']:.1%} | "
            f"{row['judge_correct_rate']:.1%} | "
            f"{row['human_correct_rate']:.1%} | {row['bias_pp']:+.1f} |"
        )
    return lines


def transition(left: bool, right: bool) -> str:
    return ("C" if left else "W") + ("C" if right else "W")


def write_confusion_svg(tp: int, tn: int, fp: int, fn: int) -> None:
    cells = [
        (260, 180, tn, "Human wrong / Judge wrong", "#d9f2e6"),
        (520, 180, fp, "Human wrong / Judge correct", "#fde2e0"),
        (260, 360, fn, "Human correct / Judge wrong", "#fff0cc"),
        (520, 360, tp, "Human correct / Judge correct", "#d9e8ff"),
    ]
    rects = []
    for x, y, count, label, color in cells:
        rects.append(
            f'<rect x="{x}" y="{y}" width="240" height="150" rx="10" '
            f'fill="{color}" stroke="#98a2b3"/>'
            f'<text x="{x + 120}" y="{y + 68}" text-anchor="middle" '
            f'font-size="38" font-weight="700">{count}</text>'
            f'<text x="{x + 120}" y="{y + 105}" text-anchor="middle" '
            f'font-size="14">{html.escape(label)}</text>'
        )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="820" height="570" viewBox="0 0 820 570">
<rect width="820" height="570" fill="white"/>
<style>text{{font-family:Arial,'Microsoft YaHei',sans-serif;fill:#172033}}</style>
<text x="410" y="48" text-anchor="middle" font-size="24" font-weight="700">Judge Audit Confusion Matrix</text>
<text x="410" y="78" text-anchor="middle" font-size="14" fill="#667085">N = 200 adjudicated outputs</text>
<text x="120" y="335" text-anchor="middle" font-size="17" font-weight="700" transform="rotate(-90 120 335)">Human adjudication</text>
<text x="500" y="535" text-anchor="middle" font-size="17" font-weight="700">Automated judge</text>
{''.join(rects)}
</svg>
"""
    SVG.write_text(svg, encoding="utf-8")


def main() -> None:
    manifest = read_csv(MANIFEST)
    adjudicated = read_csv(SOURCE)
    by_audit = {row["audit_id"]: row for row in adjudicated}
    if len(manifest) != 200 or len(adjudicated) != 200:
        raise ValueError(
            f"Expected 200 manifest and adjudicated rows; got "
            f"{len(manifest)} and {len(adjudicated)}"
        )
    if set(by_audit) != {row["audit_id"] for row in manifest}:
        raise ValueError("Manifest and adjudicated audit IDs do not match")
    if any(not row["human_label"].strip() for row in adjudicated):
        raise ValueError("Adjudicated CSV contains blank human labels")

    rows = []
    for row in manifest:
        human = by_audit[row["audit_id"]]
        j_correct = judge_correct(row["judge_label"])
        h_correct = human_correct(human["human_label"])
        rows.append(
            {
                **row,
                "human_label": human["human_label"],
                "human_reason": human["human_reason"],
                "judge_correct": j_correct,
                "human_correct": h_correct,
                "agreement": j_correct == h_correct,
            }
        )

    tp = sum(row["judge_correct"] and row["human_correct"] for row in rows)
    tn = sum(not row["judge_correct"] and not row["human_correct"] for row in rows)
    fp = sum(row["judge_correct"] and not row["human_correct"] for row in rows)
    fn = sum(not row["judge_correct"] and row["human_correct"] for row in rows)
    agreement = (tp + tn) / len(rows)

    condition = grouped_metrics(rows, "condition")
    max_condition_bias = max(abs(row["bias_pp"]) for row in condition)

    pair_rows = []
    ordered = sorted(rows, key=lambda row: row["case_id"])
    for case_id, group in itertools.groupby(
        ordered, key=lambda row: row["case_id"]
    ):
        materialized = list(group)
        by_role = {row["case_role"]: row for row in materialized}
        if set(by_role) != {"control", "target"}:
            continue
        control, target = by_role["control"], by_role["target"]
        auto_transition = transition(
            control["judge_correct"], target["judge_correct"]
        )
        human_transition = transition(
            control["human_correct"], target["human_correct"]
        )
        pair_rows.append(
            {
                "case_id": case_id,
                "stratum": control["stratum"],
                "automated": auto_transition,
                "human": human_transition,
                "agreement": auto_transition == human_transition,
            }
        )
    pair_agreement = (
        sum(row["agreement"] for row in pair_rows) / len(pair_rows)
    )

    gate_pass = agreement >= 0.90 and max_condition_bias <= 5.0
    decision = "PASS" if gate_pass else "FAIL"
    action = (
        "Freeze the current judge labels."
        if gate_pass
        else (
            "Do not freeze the current automated labels. Per the execution plan, "
            "use an independent judge, symbolic evaluator, or expanded human "
            "review of every conclusion-critical subset."
        )
    )

    lines = [
        "# Judge Audit Report",
        "",
        "## Gate decision",
        "",
        f"**{decision}.** Binary correctness agreement was **{agreement:.1%}** "
        f"({tp + tn}/200); the largest absolute condition-level correctness-rate "
        f"bias was **{max_condition_bias:.1f} pp**.",
        "",
        f"Action: {action}",
        "",
        "The hard-stop gate fails when agreement is < 90% or absolute condition "
        "bias is > 5 pp. Retaining the judge without remediation requires the "
        "stricter threshold of agreement >= 95% and bias < 3 pp; intermediate "
        "results require secondary review.",
        "",
        "## Binary confusion matrix",
        "",
        "| | Human correct | Human wrong |",
        "|---|---:|---:|",
        f"| Judge correct | {tp} | {fp} |",
        f"| Judge wrong | {fn} | {tn} |",
        "",
        f"- False-positive rate among human-wrong outputs: {fp / (fp + tn):.1%}.",
        f"- False-negative rate among human-correct outputs: {fn / (fn + tp):.1%}.",
        f"- Automated correct rate: {(tp + fp) / len(rows):.1%}.",
        f"- Human-adjudicated correct rate: {(tp + fn) / len(rows):.1%}.",
        "",
        "## Condition diagnostics",
        "",
        *markdown_table(condition, "condition"),
        "",
        "Bias is automated-judge correct rate minus human-adjudicated correct rate.",
        "",
        "## Sampling-stratum diagnostics",
        "",
        *markdown_table(grouped_metrics(rows, "stratum"), "stratum"),
        "",
        "## PRM-rating diagnostics",
        "",
        *markdown_table(grouped_metrics(rows, "prm_rating"), "prm_rating"),
        "",
        "## Pair-level transition audit",
        "",
        f"Among {len(pair_rows)} sampled control/target pairs, the automated and "
        f"human transition labels matched for "
        f"**{sum(row['agreement'] for row in pair_rows)}/{len(pair_rows)} "
        f"({pair_agreement:.1%})**.",
        "",
        "| Case | Stratum | Automated | Human |",
        "|---|---|---|---|",
    ]
    for row in pair_rows:
        if not row["agreement"]:
            lines.append(
                f"| {row['case_id']} | {row['stratum']} | "
                f"{row['automated']} | {row['human']} |"
            )
    lines += [
        "",
        "## Consequence for qualitative cases",
        "",
        "Only 4 of the 78 outputs belonging to the provisional eight qualitative "
        "cases occur in the 200-output audit. Because the overall gate failed, "
        "the remaining 74 outputs require direct human review before any case is "
        "marked verified. `qualitative_case_audit.html` is the blinded review "
        "instrument; the four prior adjudications are prefilled.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    write_confusion_svg(tp, tn, fp, fn)

    summary = {
        "n": len(rows),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "agreement": agreement,
        "max_absolute_condition_bias_pp": max_condition_bias,
        "pair_transition_agreement": pair_agreement,
        "gate": decision,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
