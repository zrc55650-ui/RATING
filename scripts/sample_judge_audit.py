#!/usr/bin/env python3
"""Select the fixed 200-output blinded Judge Audit sample."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


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

ANNOTATION_INSTRUCTION = (
    "Judge only this candidate output against the question and reference answer. "
    "Choose exactly one label: Correct; Incorrect; Ambiguous / insufficient information; "
    "No valid final answer. Do not infer any experimental condition."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-run", default="data/master_run_table.csv")
    parser.add_argument("--master-step", default="data/master_step_table.csv")
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument(
        "--manifest-output", default="build/judge_audit_sampling_manifest.csv"
    )
    parser.add_argument(
        "--blind-a-output", default="build/judge_audit_blinded_sheet_A.csv"
    )
    parser.add_argument(
        "--blind-b-output", default="build/judge_audit_blinded_sheet_B.csv"
    )
    return parser.parse_args()


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: str | Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def bool_int(value: Any) -> int:
    return int(str(value).strip().lower() in {"1", "true", "yes"})


def balance_key(candidate: dict[str, Any], fields: Iterable[str]) -> tuple[str, ...]:
    return tuple(str(candidate.get(field, "")) for field in fields)


def balanced_select(
    candidates: list[dict[str, Any]],
    count: int,
    used_output_ids: set[str],
    rng: random.Random,
    balance_fields: list[str],
    prefer_unique_steps: bool = True,
) -> list[dict[str, Any]]:
    """Round-robin across strata while avoiding already selected output IDs."""

    available = [
        candidate
        for candidate in candidates
        if not (set(candidate["output_ids"]) & used_output_ids)
    ]
    buckets: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for candidate in available:
        buckets[balance_key(candidate, balance_fields)].append(candidate)
    for values in buckets.values():
        rng.shuffle(values)

    keys = sorted(buckets)
    rng.shuffle(keys)
    selected: list[dict[str, Any]] = []
    local_output_ids = set(used_output_ids)
    selected_steps: set[str] = set()

    def take_pass(enforce_unique_steps: bool) -> None:
        made_progress = True
        while len(selected) < count and made_progress:
            made_progress = False
            round_keys = list(keys)
            rng.shuffle(round_keys)
            for key in round_keys:
                bucket = buckets[key]
                chosen_index = None
                for index, candidate in enumerate(bucket):
                    if set(candidate["output_ids"]) & local_output_ids:
                        continue
                    if enforce_unique_steps and candidate["step_id"] in selected_steps:
                        continue
                    chosen_index = index
                    break
                if chosen_index is None:
                    continue
                candidate = bucket.pop(chosen_index)
                selected.append(candidate)
                local_output_ids.update(candidate["output_ids"])
                selected_steps.add(candidate["step_id"])
                made_progress = True
                if len(selected) == count:
                    return

    take_pass(prefer_unique_steps)
    if len(selected) < count and prefer_unique_steps:
        take_pass(False)
    if len(selected) != count:
        raise ValueError(
            f"Could select only {len(selected)} of {count} requested candidates"
        )
    used_output_ids.update(
        output_id for candidate in selected for output_id in candidate["output_ids"]
    )
    return selected


def pair_candidates(
    pairs: dict[str, dict[str, dict[str, str]]],
    transition: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for pair_id, by_condition in pairs.items():
        if set(by_condition) != {"control", "target_delete"}:
            raise ValueError(f"Incomplete Control/Target pair {pair_id}")
        control = by_condition["control"]
        target = by_condition["target_delete"]
        if control["pair_transition"] != transition:
            continue
        result.append(
            {
                "step_id": control["step_id"],
                "pair_id": pair_id,
                "prm_rating": control["prm_rating"],
                "step_type_analysis": control["step_type_analysis"],
                "position_bin": control["position_bin"],
                "output_ids": [control["output_id"], target["output_id"]],
                "outputs": [("control", control), ("target", target)],
                "selection_reason": transition,
            }
        )
    return result


def case_rows(
    selected: list[dict[str, Any]],
    stratum: str,
    prefix: str,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index, candidate in enumerate(selected, 1):
        candidate = dict(candidate)
        candidate["stratum"] = stratum
        candidate["case_id"] = f"{prefix}{index:03d}"
        cases.append(candidate)
    return cases


def blind_row(manifest_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "audit_id": manifest_row["audit_id"],
        "annotation_instruction": ANNOTATION_INSTRUCTION,
        "question": manifest_row["question"],
        "ground_truth_answer": manifest_row["ground_truth_answer"],
        "candidate_output": manifest_row["candidate_output"],
        "human_label": "",
        "human_final_answer_normalized": "",
        "human_reason": "",
        "human_tool_needed": "",
        "human_confidence": "",
    }


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)

    runs = read_csv(args.master_run)
    steps = read_csv(args.master_step)
    if len(runs) != 6314 or len(steps) != 600:
        raise ValueError("Master tables do not have the expected 6314/600 rows")

    outputs_by_id: dict[str, dict[str, str]] = {}
    runs_by_step: dict[str, list[dict[str, str]]] = defaultdict(list)
    pairs: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in runs:
        output_id = row["output_id"]
        if output_id in outputs_by_id:
            raise ValueError(f"Duplicate output ID in master table: {output_id}")
        outputs_by_id[output_id] = row
        runs_by_step[row["step_id"]].append(row)
        if row["pair_id"]:
            pairs[row["pair_id"]][row["condition"]] = row

    used_output_ids: set[str] = set()
    all_cases: list[dict[str, Any]] = []

    # Priority 1: dangerous deletions (25 pairs / 50 outputs).
    cw = balanced_select(
        pair_candidates(pairs, "correct_to_wrong"),
        25,
        used_output_ids,
        rng,
        ["prm_rating", "step_type_analysis", "position_bin"],
    )
    all_cases.extend(case_rows(cw, "correct_to_wrong", "CW"))

    # Priority 2: recoveries (25 pairs / 50 outputs).
    wc = balanced_select(
        pair_candidates(pairs, "wrong_to_correct"),
        25,
        used_output_ids,
        rng,
        ["prm_rating", "step_type_analysis", "position_bin"],
    )
    all_cases.extend(case_rows(wc, "wrong_to_correct", "WC"))

    # Priority 3: 20 Target-vs-Placebo discordant triads.
    triad_candidates: list[dict[str, Any]] = []
    for step_id, step_runs in runs_by_step.items():
        controls = {
            row["pair_id"]: row for row in step_runs if row["condition"] == "control"
        }
        targets = [
            row for row in step_runs if row["condition"] == "target_delete"
        ]
        placebos = [
            row for row in step_runs if row["condition"] == "placebo_delete"
        ]
        options: list[tuple[dict[str, str], dict[str, str], dict[str, str]]] = []
        for target in targets:
            control = controls[target["pair_id"]]
            for placebo in placebos:
                if bool_int(target["judge_label"]) != bool_int(placebo["judge_label"]):
                    option_ids = {
                        control["output_id"],
                        target["output_id"],
                        placebo["output_id"],
                    }
                    if not (option_ids & used_output_ids):
                        options.append((control, target, placebo))
        if not options:
            continue
        rng.shuffle(options)
        control, target, placebo = options[0]
        direction = (
            "target_correct_placebo_wrong"
            if bool_int(target["judge_label"])
            else "target_wrong_placebo_correct"
        )
        triad_candidates.append(
            {
                "step_id": step_id,
                "prm_rating": target["prm_rating"],
                "step_type_analysis": target["step_type_analysis"],
                "position_bin": target["position_bin"],
                "discordance_direction": direction,
                "output_ids": [
                    control["output_id"],
                    target["output_id"],
                    placebo["output_id"],
                ],
                "outputs": [
                    ("control", control),
                    ("target", target),
                    ("placebo", placebo),
                ],
                "selection_reason": direction,
            }
        )
    triads = balanced_select(
        triad_candidates,
        20,
        used_output_ids,
        rng,
        [
            "discordance_direction",
            "prm_rating",
            "step_type_analysis",
            "position_bin",
        ],
    )
    all_cases.extend(case_rows(triads, "target_placebo_discordant", "TPD"))

    # Priority 4: 20 abnormal/ambiguous/long-output singles.
    visible_values = sorted(int(row["visible_tokens"]) for row in runs)
    q75_index = math.ceil(0.75 * len(visible_values)) - 1
    q75 = visible_values[q75_index]
    abnormal_candidates: list[dict[str, Any]] = []
    for row in runs:
        if row["output_id"] in used_output_ids:
            continue
        reasons: list[str] = []
        if row["generator_status"] != "completed":
            reasons.append(f"status:{row['generator_status']}")
        if not row["final_answer_normalized"].strip():
            reasons.append("no_valid_final_answer")
        if row["judge_model"] == "rule:no-answer":
            reasons.append("rule_no_answer")
        if int(row["visible_tokens"]) >= q75:
            reasons.append("long_output_q4")
        if not reasons:
            continue
        category = (
            "abnormal_or_no_answer"
            if any(reason != "long_output_q4" for reason in reasons)
            else "long_output_q4"
        )
        abnormal_candidates.append(
            {
                "step_id": row["step_id"],
                "prm_rating": row["prm_rating"],
                "step_type_analysis": row["step_type_analysis"],
                "position_bin": row["position_bin"],
                "condition": row["condition"],
                "abnormal_category": category,
                "output_ids": [row["output_id"]],
                "outputs": [("single", row)],
                "selection_reason": ";".join(reasons),
            }
        )
    abnormal = balanced_select(
        abnormal_candidates,
        20,
        used_output_ids,
        rng,
        ["abnormal_category", "condition", "prm_rating", "position_bin"],
    )
    all_cases.extend(case_rows(abnormal, "abnormal_or_ambiguous", "ABN"))

    # Priority 5: 5 Still Correct and 5 Still Wrong random concordant pairs.
    still_correct = balanced_select(
        pair_candidates(pairs, "still_correct"),
        5,
        used_output_ids,
        rng,
        ["prm_rating", "step_type_analysis", "position_bin"],
    )
    still_wrong = balanced_select(
        pair_candidates(pairs, "still_wrong"),
        5,
        used_output_ids,
        rng,
        ["prm_rating", "step_type_analysis", "position_bin"],
    )
    all_cases.extend(case_rows(still_correct, "concordant_still_correct", "SC"))
    all_cases.extend(case_rows(still_wrong, "concordant_still_wrong", "SW"))

    manifest_entries: list[dict[str, Any]] = []
    for case in all_cases:
        for role, row in case["outputs"]:
            manifest_entries.append(
                {
                    "sampling_seed": args.seed,
                    "audit_id": "",
                    "case_id": case["case_id"],
                    "stratum": case["stratum"],
                    "case_role": role,
                    "selection_reason": case["selection_reason"],
                    "output_id": row["output_id"],
                    "step_id": row["step_id"],
                    "problem_id": row["problem_id"],
                    "trajectory_id": row["trajectory_id"],
                    "run_id": row["run_id"],
                    "condition": row["condition"],
                    "pair_id": row["pair_id"],
                    "pair_transition": row["pair_transition"],
                    "prm_rating": row["prm_rating"],
                    "step_type_analysis": row["step_type_analysis"],
                    "step_type_human_calibrated": row[
                        "step_type_human_calibrated"
                    ],
                    "position_bin": row["position_bin"],
                    "generator_status": row["generator_status"],
                    "visible_tokens": row["visible_tokens"],
                    "question": row["question"],
                    "ground_truth_answer": row["ground_truth_answer"],
                    "candidate_output": row["candidate_output"],
                    "final_answer_raw": row["final_answer_raw"],
                    "judge_label": row["judge_label"],
                    "judge_reason": row["judge_reason"],
                    "judge_model": row["judge_model"],
                    "included_in_blind_sheet_B": 0,
                }
            )

    if len(manifest_entries) != 200:
        raise ValueError(f"Expected 200 audit outputs, found {len(manifest_entries)}")
    output_ids = [row["output_id"] for row in manifest_entries]
    if len(set(output_ids)) != 200:
        raise ValueError("Audit sample contains duplicate output IDs")

    # Random blind order; the audit ID does not reveal stratum or case membership.
    order_rng = random.Random(args.seed + 1)
    order_rng.shuffle(manifest_entries)
    for index, row in enumerate(manifest_entries, 1):
        row["audit_id"] = f"JA{index:03d}"

    # Minimum dual-annotation plan: all 50 C->W outputs plus 20 abnormal and
    # 10 independently sampled remaining outputs.
    cw_entries = [
        row for row in manifest_entries if row["stratum"] == "correct_to_wrong"
    ]
    abnormal_entries = [
        row for row in manifest_entries if row["stratum"] == "abnormal_or_ambiguous"
    ]
    b_ids = {row["output_id"] for row in cw_entries + abnormal_entries}
    remaining = [row for row in manifest_entries if row["output_id"] not in b_ids]
    b_rng = random.Random(args.seed + 2)
    b_rng.shuffle(remaining)
    b_entries = cw_entries + abnormal_entries + remaining[:10]
    if len(b_entries) != 80 or len({row["output_id"] for row in b_entries}) != 80:
        raise ValueError("Blind sheet B is not an 80-output distinct subset")
    for row in b_entries:
        row["included_in_blind_sheet_B"] = 1

    blind_a = [blind_row(row) for row in sorted(manifest_entries, key=lambda r: r["audit_id"])]
    b_rng.shuffle(b_entries)
    blind_b = [blind_row(row) for row in b_entries]

    manifest_fields = list(manifest_entries[0])
    write_csv(
        args.manifest_output,
        sorted(manifest_entries, key=lambda row: row["audit_id"]),
        manifest_fields,
    )
    write_csv(args.blind_a_output, blind_a, BLIND_FIELDS)
    write_csv(args.blind_b_output, blind_b, BLIND_FIELDS)

    stratum_outputs = Counter(row["stratum"] for row in manifest_entries)
    stratum_cases = Counter(case["stratum"] for case in all_cases)
    condition_counts = Counter(row["condition"] for row in manifest_entries)
    print(
        json.dumps(
            {
                "seed": args.seed,
                "manifest": args.manifest_output,
                "distinct_outputs": len(manifest_entries),
                "cases_by_stratum": dict(stratum_cases),
                "outputs_by_stratum": dict(stratum_outputs),
                "outputs_by_condition": dict(condition_counts),
                "blind_sheet_A_rows": len(blind_a),
                "blind_sheet_B_rows": len(blind_b),
                "long_output_q75_threshold": q75,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
