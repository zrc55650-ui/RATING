#!/usr/bin/env python3
"""Prepare a blinded human audit of every run used by the provisional 8 cases."""

from __future__ import annotations

import json
from pathlib import Path

from analysis_common import ROOT, SEED, as_int, read_csv, stable_hash, write_csv


RECOMMENDED_COUNTS = {
    "negative_anchor": 3,
    "generic_restart": 2,
    "stable_correct_harmed": 2,
    "high_rated_redundant_ambiguity": 1,
}

BLIND_FIELDS = [
    "audit_id",
    "annotation_instruction",
    "question",
    "ground_truth_answer",
    "candidate_output",
    "human_label",
    "human_final_answer_normalized",
    "human_reason",
    "human_tool_needed",
    "human_confidence",
]

INSTRUCTION = (
    "Judge only this candidate output against the question and reference answer. "
    "Choose exactly one label: Correct; Incorrect; Ambiguous / insufficient "
    "information; No valid final answer. Do not infer the experimental condition "
    "or the qualitative case family."
)


def main() -> None:
    candidates = read_csv(ROOT / "workstream_E_qualitative_case_study" / "qualitative_case_candidates.csv")
    runs = read_csv(ROOT / "data" / "master_run_table.csv")
    prior_by_output: dict[str, dict[str, str]] = {}
    prior_manifest_path = ROOT / "workstream_A_judge_audit" / "judge_audit_sampling_manifest.csv"
    prior_adjudicated_path = ROOT / "workstream_A_judge_audit" / "judge_audit_adjudicated.csv"
    if prior_manifest_path.exists() and prior_adjudicated_path.exists():
        prior_manifest = read_csv(prior_manifest_path)
        prior_adjudicated = {
            row["audit_id"]: row for row in read_csv(prior_adjudicated_path)
        }
        for row in prior_manifest:
            if row["audit_id"] in prior_adjudicated:
                prior_by_output[row["output_id"]] = {
                    "prior_audit_id": row["audit_id"],
                    **prior_adjudicated[row["audit_id"]],
                }
    selected = [
        row
        for row in candidates
        if as_int(row["family_rank"])
        <= RECOMMENDED_COUNTS[row["case_family"]]
    ]
    if len(selected) != sum(RECOMMENDED_COUNTS.values()):
        raise ValueError(
            f"Expected {sum(RECOMMENDED_COUNTS.values())} provisional cases, "
            f"found {len(selected)}"
        )

    selected_by_step = {row["step_id"]: row for row in selected}
    selected_runs = [
        row for row in runs if row["step_id"] in selected_by_step
    ]
    output_ids = [row["output_id"] for row in selected_runs]
    if len(output_ids) != len(set(output_ids)):
        raise ValueError("Selected qualitative runs contain duplicate output IDs")
    if not selected_runs:
        raise ValueError("No qualitative runs were selected")

    # The order is deterministic but hides family, rank, step, and condition.
    selected_runs.sort(
        key=lambda row: (
            stable_hash(row["output_id"], SEED + 77),
            row["output_id"],
        )
    )

    manifest: list[dict[str, str | int]] = []
    blind: list[dict[str, str]] = []
    for index, run in enumerate(selected_runs, 1):
        candidate = selected_by_step[run["step_id"]]
        audit_id = f"QE{index:03d}"
        prior = prior_by_output.get(run["output_id"], {})
        manifest.append(
            {
                "selection_seed": SEED,
                "audit_id": audit_id,
                "case_family": candidate["case_family"],
                "family_rank": candidate["family_rank"],
                "step_id": run["step_id"],
                "problem_id": run["problem_id"],
                "output_id": run["output_id"],
                "pair_id": run["pair_id"],
                "pair_transition_automated": run["pair_transition"],
                "condition": run["condition"],
                "run_id": run["run_id"],
                "placebo_order": run["placebo_order"],
                "placebo_step_index": run["placebo_step_index"],
                "generator_status": run["generator_status"],
                "visible_tokens": run["visible_tokens"],
                "judge_label": run["judge_label"],
                "judge_reason": run["judge_reason"],
                "prior_audit_id": prior.get("prior_audit_id", ""),
                "prior_human_label": prior.get("human_label", ""),
            }
        )
        blind.append(
            {
                "audit_id": audit_id,
                "annotation_instruction": INSTRUCTION,
                "question": run["question"],
                "ground_truth_answer": run["ground_truth_answer"],
                "candidate_output": run["candidate_output"],
                "human_label": prior.get("human_label", ""),
                "human_final_answer_normalized": prior.get(
                    "human_final_answer_normalized", ""
                ),
                "human_reason": prior.get("human_reason", ""),
                "human_tool_needed": prior.get("human_tool_needed", ""),
                "human_confidence": prior.get("human_confidence", ""),
            }
        )

    write_csv(ROOT / "data" / "annotations" / "qualitative" / "qualitative_case_audit_manifest.csv", manifest)
    write_csv(
        ROOT / "data" / "annotations" / "qualitative" / "qualitative_case_audit_sheet.csv",
        blind,
        fieldnames=BLIND_FIELDS,
    )

    condition_counts: dict[str, int] = {}
    for row in selected_runs:
        condition_counts[row["condition"]] = (
            condition_counts.get(row["condition"], 0) + 1
        )
    summary = {
        "selection_seed": SEED,
        "provisional_cases": len(selected),
        "audit_outputs": len(selected_runs),
        "prefilled_from_prior_adjudication": sum(
            run["output_id"] in prior_by_output for run in selected_runs
        ),
        "conditions": condition_counts,
        "families": RECOMMENDED_COUNTS,
        "manifest": "qualitative_case_audit_manifest.csv",
        "blind_sheet": "qualitative_case_audit_sheet.csv",
    }
    (ROOT / "data" / "annotations" / "qualitative" / "qualitative_case_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
