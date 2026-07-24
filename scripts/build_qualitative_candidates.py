#!/usr/bin/env python3
"""Deterministically select qualitative candidates; human verification remains required."""

from __future__ import annotations

import textwrap
from pathlib import Path

from analysis_common import (
    ROOT,
    SEED,
    as_bool,
    as_float,
    as_int,
    median,
    read_csv,
    stable_hash,
    write_csv,
)


def excerpt(text: str, limit: int = 1200) -> str:
    cleaned = " ".join((text or "").replace("\x0c", "\\f").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def choose_run(runs: list[dict], condition: str, transition: str | None = None, label: int | None = None):
    candidates = [run for run in runs if run["condition"] == condition]
    if transition is not None:
        candidates = [run for run in candidates if run["pair_transition"] == transition]
    if label is not None:
        candidates = [run for run in candidates if as_int(run["judge_label"]) == label]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda run: (
            as_int(run.get("visible_tokens")),
            stable_hash(run["output_id"], SEED),
        ),
    )[0]


def build_candidate(
    family: str,
    rank: int,
    step: dict,
    runs: list[dict],
    reason: str,
) -> dict:
    if family in {"negative_anchor", "generic_restart"}:
        target = choose_run(runs, "target_delete", "wrong_to_correct")
        control = (
            choose_run(runs, "control", "wrong_to_correct")
            or choose_run(runs, "control", label=0)
        )
    elif family == "stable_correct_harmed":
        target = choose_run(runs, "target_delete", "correct_to_wrong")
        control = (
            choose_run(runs, "control", "correct_to_wrong")
            or choose_run(runs, "control", label=1)
        )
    else:
        target = (
            choose_run(runs, "target_delete", "mixed")
            or choose_run(runs, "target_delete", label=0)
            or choose_run(runs, "target_delete")
        )
        control = choose_run(runs, "control")
    placebo = None
    if family == "negative_anchor":
        placebo = choose_run(runs, "placebo_delete", label=0) or choose_run(
            runs, "placebo_delete"
        )
    elif family == "generic_restart":
        placebo = choose_run(runs, "placebo_delete", label=1) or choose_run(
            runs, "placebo_delete"
        )
    else:
        placebo = choose_run(runs, "placebo_delete")

    return {
        "case_family": family,
        "family_rank": rank,
        "step_id": step["step_id"],
        "problem_id": step["problem_id"],
        "display_order": step["display_order"],
        "prm_rating": step["prm_rating"],
        "step_type_analysis": step["step_type_analysis"],
        "step_type_human_calibrated": step["step_type_human_calibrated"],
        "position_bin": step["position_bin"],
        "target_tokens": step["target_tokens"],
        "wrong_to_correct_count": step["wrong_to_correct_count"],
        "correct_to_wrong_count": step["correct_to_wrong_count"],
        "control_correct_count": step["control_correct_count"],
        "target_effect": step["target_effect"],
        "placebo_effect": step["placebo_effect"],
        "pure_semantic_effect": step["pure_semantic_effect"],
        "problem": step["problem"],
        "ground_truth_answer": step["ground_truth_answer"],
        "target_step_text": step["target_step_text"],
        "control_output_id": control["output_id"] if control else "",
        "control_excerpt": excerpt(control["candidate_output"]) if control else "",
        "target_output_id": target["output_id"] if target else "",
        "target_excerpt": excerpt(target["candidate_output"]) if target else "",
        "placebo_output_id": placebo["output_id"] if placebo else "",
        "placebo_excerpt": excerpt(placebo["candidate_output"]) if placebo else "",
        "automatic_selection_reason": reason,
        "verification_status": "PENDING HUMAN JUDGE AUDIT",
        "human_transition_verified": "",
        "human_case_notes": "",
    }


def main() -> None:
    steps = read_csv(ROOT / "data" / "master_step_table.csv")
    runs = read_csv(ROOT / "data" / "master_run_table.csv")
    runs_by_step: dict[str, list[dict]] = {}
    for run in runs:
        runs_by_step.setdefault(run["step_id"], []).append(run)
    token_median = median(as_float(step["target_tokens"]) for step in steps)

    negative = [
        step
        for step in steps
        if as_int(step["prm_rating"]) == -1
        and step["step_type_human_calibrated"].lower() == "harmful"
        and as_int(step["wrong_to_correct_count"]) >= 2
        and as_int(step["correct_to_wrong_count"]) == 0
        and as_bool(step["placebo_eligible"])
        and as_float(step["pure_semantic_effect"]) > 0
        and as_float(step["target_effect"]) > as_float(step["placebo_effect"])
    ]
    negative.sort(
        key=lambda step: (
            -as_float(step["pure_semantic_effect"]),
            abs(as_float(step["target_tokens"]) - token_median),
            stable_hash(step["step_id"], SEED),
        )
    )

    generic = [
        step
        for step in steps
        if as_bool(step["placebo_eligible"])
        and as_float(step["target_effect"]) > 0
        and as_float(step["placebo_effect"]) > 0
        and as_int(step["wrong_to_correct_count"]) >= 1
    ]
    generic.sort(
        key=lambda step: (
            -min(as_float(step["target_effect"]), as_float(step["placebo_effect"])),
            abs(as_float(step["target_tokens"]) - token_median),
            stable_hash(step["step_id"], SEED + 1),
        )
    )

    harmed = [
        step
        for step in steps
        if as_int(step["control_correct_count"]) == 4
        and as_int(step["correct_to_wrong_count"]) >= 2
    ]
    harmed.sort(
        key=lambda step: (
            -as_int(step["correct_to_wrong_count"]),
            abs(as_float(step["target_tokens"]) - token_median),
            stable_hash(step["step_id"], SEED + 2),
        )
    )

    ambiguity = [
        step
        for step in steps
        if as_int(step["prm_rating"]) == 1
        and step["step_type_human_calibrated"].lower() == "redundant"
        and (
            as_bool(step["sign_conflict"])
            or as_int(step["correct_to_wrong_count"]) > 0
        )
    ]
    ambiguity.sort(
        key=lambda step: (
            -as_int(step["correct_to_wrong_count"]),
            -as_int(step["wrong_to_correct_count"]),
            stable_hash(step["step_id"], SEED + 3),
        )
    )

    selections = [
        (
            "negative_anchor",
            negative[:8],
            "rating=-1; human-calibrated Harmful; WC>=2; CW=0; positive pure semantic effect",
        ),
        (
            "generic_restart",
            generic[:8],
            "Target and Placebo effects both positive; at least one target WC transition",
        ),
        (
            "stable_correct_harmed",
            harmed[:8],
            "Control 4/4 correct; target deletion produces at least two CW transitions",
        ),
        (
            "high_rated_redundant_ambiguity",
            ambiguity[:8],
            "rating=1; human-calibrated Redundant; observed harm or mixed transitions",
        ),
    ]
    candidates = []
    for family, selected, reason in selections:
        for rank, step in enumerate(selected, start=1):
            candidates.append(
                build_candidate(
                    family,
                    rank,
                    step,
                    runs_by_step[step["step_id"]],
                    reason,
                )
            )
    write_csv(ROOT / "workstream_E_qualitative_case_study" / "qualitative_case_candidates.csv", candidates)

    recommended_counts = {
        "negative_anchor": 3,
        "generic_restart": 2,
        "stable_correct_harmed": 2,
        "high_rated_redundant_ambiguity": 1,
    }
    lines = [
        "# Qualitative Case Candidates — Pending Human Verification",
        "",
        f"Selection seed: `{SEED}`.",
        "",
        "> 这些不是最终论文案例。按照预先固定的规则自动筛选后，仍必须通过 Judge Audit，"
        "并人工确认 transition、可读性和机制解释。当前文档不能作为人工正确性证据。",
        "",
        "## Recommended provisional set",
        "",
    ]
    for family, count in recommended_counts.items():
        selected = [
            row
            for row in candidates
            if row["case_family"] == family and int(row["family_rank"]) <= count
        ]
        lines += [f"### {family.replace('_', ' ').title()}", ""]
        for row in selected:
            target_effect = as_float(row["target_effect"]) * 100
            pure = as_float(row["pure_semantic_effect"]) * 100
            lines += [
                f"#### {row['step_id']}",
                "",
                f"- Rating / type: `{row['prm_rating']}` / "
                f"`{row['step_type_human_calibrated']}` (human-calibrated)",
                f"- WC / CW: `{row['wrong_to_correct_count']}` / "
                f"`{row['correct_to_wrong_count']}`",
                f"- Raw target effect: `{target_effect:+.1f} pp`",
                (
                    f"- Pure semantic effect: `{pure:+.1f} pp`"
                    if row["pure_semantic_effect"]
                    else "- Pure semantic effect: not available"
                ),
                f"- Problem: {textwrap.shorten(row['problem'], width=260, placeholder='…')}",
                f"- Target step: {textwrap.shorten(row['target_step_text'], width=260, placeholder='…')}",
                "- Verification: **PENDING**",
                "",
            ]
    lines += [
        "## Verification checklist after Audit",
        "",
        "- 人工确认 Control/Target/Placebo 最终答案；",
        "- 人工确认所述 transition 不是自动 Judge 噪声；",
        "- 检查输出没有被截断或格式异常；",
        "- 检查案例机制与类别命名一致；",
        "- 只保留短、清晰、具有代表性的 excerpt；",
        "- 将通过项写入 `qualitative_cases_verified.csv`。",
        "",
    ]
    (ROOT / "workstream_E_qualitative_case_study" / "qualitative_cases.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
