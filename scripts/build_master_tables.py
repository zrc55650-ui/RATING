#!/usr/bin/env python3
"""Build the canonical step-level and run-level tables for the study."""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", default="data/qwen3-8b_deletion_pairs.csv")
    parser.add_argument("--generations", default="data/qwen_deletion_generations.jsonl")
    parser.add_argument(
        "--human-comparison", default="data/annotations/human_calibration/human_calibrated_600_comparison.csv"
    )
    parser.add_argument(
        "--sample-html", default="data/annotations/human_calibration/prm800k_ai_600_human_calibrated_flash.html"
    )
    parser.add_argument(
        "--placebo-selection", default="data/qwen3-8b_placebo_selection.jsonl"
    )
    parser.add_argument(
        "--placebo-workers", default="archive/worker_shards/qwen_placebo_worker??.jsonl"
    )
    parser.add_argument("--placebo-judges", default="archive/worker_shards/qwen_placebo_judge??.jsonl")
    parser.add_argument(
        "--target-judge-patterns",
        nargs="+",
        default=[
            "qwen_deletion_fast_judge??.jsonl",
            "qwen_deletion_tail_judge??.jsonl",
        ],
    )
    parser.add_argument("--step-output", default="data/master_step_table.csv")
    parser.add_argument("--run-output", default="data/master_run_table.csv")
    return parser.parse_args()


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in {path}:{line_number}") from exc
    return rows


def read_jsonl_glob(patterns: str | Iterable[str]) -> list[dict[str, Any]]:
    if isinstance(patterns, str):
        patterns = [patterns]
    files: list[str] = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))
    files = sorted(set(files))
    if not files:
        raise FileNotFoundError(f"No files match: {list(patterns)}")
    rows: list[dict[str, Any]] = []
    for path in files:
        rows.extend(read_jsonl(path))
    return rows


def read_embedded_samples(path: str | Path) -> list[dict[str, Any]]:
    html = Path(path).read_text(encoding="utf-8")
    match = re.search(
        r"const DATA = (.*?);\s*const samples = DATA\.samples;",
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError(f"Could not locate embedded DATA in {path}")
    payload = json.loads(match.group(1))
    return payload["samples"]


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"Not a boolean: {value!r}")


def normalize_space(value: Any) -> str:
    return " ".join(str(value or "").split())


def stable_id(prefix: str, value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def rounded(value: float | None, digits: int = 6) -> str | float:
    return "" if value is None else round(value, digits)


def safe_mean(values: Iterable[float | int]) -> float | None:
    materialized = list(values)
    return mean(materialized) if materialized else None


def position_bin(index: int, total_steps: int) -> str:
    if total_steps <= 1:
        return "early"
    ratio = index / (total_steps - 1)
    if ratio < 1 / 3:
        return "early"
    if ratio < 2 / 3:
        return "middle"
    return "late"


def require_unique(rows: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row[key])
        if value in result:
            raise ValueError(f"Duplicate {label} key {value}")
        result[value] = row
    return result


def write_csv(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()

    pairs = read_csv(args.pairs)
    generations = read_jsonl(args.generations)
    human_rows = read_csv(args.human_comparison)
    samples = read_embedded_samples(args.sample_html)
    placebo_selection = read_jsonl(args.placebo_selection)
    placebo_workers = read_jsonl_glob(args.placebo_workers)
    placebo_judges = read_jsonl_glob(args.placebo_judges)
    target_judges = read_jsonl_glob(args.target_judge_patterns)

    if len(pairs) != 2400:
        raise ValueError(f"Expected 2400 paired outcomes, found {len(pairs)}")
    if len(generations) != 4800:
        raise ValueError(f"Expected 4800 Control/Target generations, found {len(generations)}")
    if len(human_rows) != 600 or len(samples) != 600:
        raise ValueError("Expected 600 human-comparison and embedded sample rows")
    if len(placebo_workers) != 1514 or len(placebo_judges) != 1514:
        raise ValueError("Expected 1514 Placebo generations and 1514 Placebo judgments")
    if len(target_judges) != 4800:
        raise ValueError(f"Expected 4800 Control/Target judgments, found {len(target_judges)}")

    pair_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pairs:
        pair_groups[row["sampleId"]].append(row)
    if len(pair_groups) != 600 or any(len(rows) != 4 for rows in pair_groups.values()):
        raise ValueError("Paired outcomes must contain four runs for each of 600 steps")

    human_by_id = require_unique(human_rows, "id", "human comparison")
    sample_by_id = require_unique(samples, "id", "embedded sample")
    generation_by_task = require_unique(generations, "taskId", "generation")
    target_judge_by_task = require_unique(target_judges, "taskId", "target judge")
    placebo_worker_by_task = require_unique(placebo_workers, "taskId", "placebo generation")
    placebo_judge_by_task = require_unique(placebo_judges, "taskId", "placebo judge")
    selection_by_task = require_unique(placebo_selection, "taskId", "placebo selection")

    sample_ids = set(pair_groups)
    for label, keys in [
        ("human comparison", set(human_by_id)),
        ("embedded samples", set(sample_by_id)),
    ]:
        if keys != sample_ids:
            raise ValueError(f"{label} sample IDs do not match paired outcomes")
    if set(placebo_worker_by_task) != set(placebo_judge_by_task):
        raise ValueError("Placebo generation and judge task IDs do not match")
    if set(placebo_worker_by_task) != set(selection_by_task):
        raise ValueError("Placebo generation and selection task IDs do not match")
    if set(generation_by_task) != set(target_judge_by_task):
        raise ValueError("Control/Target generation and judge task IDs do not match")

    selection_by_step: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in placebo_selection:
        selection_by_step[str(row["sampleId"])].append(row)

    placebo_tasks_by_step: dict[str, list[str]] = defaultdict(list)
    for task_id, row in placebo_worker_by_task.items():
        placebo_tasks_by_step[str(row["sampleId"])].append(task_id)

    step_identity: dict[str, dict[str, str]] = {}
    for step_id, sample in sample_by_id.items():
        problem_norm = normalize_space(sample["problem"])
        trajectory_norm = [normalize_space(step) for step in sample["steps"]]
        step_identity[step_id] = {
            "problem_id": stable_id("problem", problem_norm),
            "trajectory_id": stable_id(
                "trajectory", {"problem": problem_norm, "steps": trajectory_norm}
            ),
        }

    run_rows: list[dict[str, Any]] = []
    step_rows: list[dict[str, Any]] = []

    for step_id in sorted(sample_ids, key=lambda value: int(sample_by_id[value]["displayOrder"])):
        sample = sample_by_id[step_id]
        human = human_by_id[step_id]
        identity = step_identity[step_id]
        step_pairs = sorted(pair_groups[step_id], key=lambda row: int(row["run"]))

        analysis_types = {row["stepTypeLabel"].lower() for row in step_pairs}
        analysis_removable = {row["removableLabel"].lower() for row in step_pairs}
        if len(analysis_types) != 1 or len(analysis_removable) != 1:
            raise ValueError(f"Inconsistent analysis labels for {step_id}")
        analysis_type = next(iter(analysis_types))
        analysis_removable_label = next(iter(analysis_removable))
        if analysis_type != human["oldStepType"].lower():
            raise ValueError(f"Analysis/old Step Type mismatch for {step_id}")

        control_correct = [parse_bool(row["controlCorrect"]) for row in step_pairs]
        target_correct = [parse_bool(row["deletedCorrect"]) for row in step_pairs]
        transitions = Counter(row["transition"] for row in step_pairs)
        n_control_correct = sum(control_correct)
        n_target_correct = sum(target_correct)
        n_wc = transitions["wrong_to_correct"]
        n_cw = transitions["correct_to_wrong"]
        n_sc = transitions["still_correct"]
        n_sw = transitions["still_wrong"]

        control_generations: list[dict[str, Any]] = []
        target_generations: list[dict[str, Any]] = []
        target_token_values: list[int] = []
        prefix_token_values: list[int] = []

        for pair in step_pairs:
            run = int(pair["run"])
            control_task = f"{step_id}|run{run}|control"
            target_task = f"{step_id}|run{run}|deleted"
            control_gen = generation_by_task[control_task]
            target_gen = generation_by_task[target_task]
            control_generations.append(control_gen)
            target_generations.append(target_gen)
            target_token_values.append(
                int(control_gen["promptTokens"]) - int(target_gen["promptTokens"])
            )
            prefix_token_values.append(int(target_gen["promptTokens"]))

            for condition, generation, judge, is_correct in [
                (
                    "control",
                    control_gen,
                    target_judge_by_task[control_task],
                    parse_bool(pair["controlCorrect"]),
                ),
                (
                    "target_delete",
                    target_gen,
                    target_judge_by_task[target_task],
                    parse_bool(pair["deletedCorrect"]),
                ),
            ]:
                if parse_bool(judge["correct"]) != is_correct:
                    raise ValueError(f"Pair/judge correctness mismatch for {generation['taskId']}")
                run_rows.append(
                    {
                        "step_id": step_id,
                        "problem_id": identity["problem_id"],
                        "trajectory_id": identity["trajectory_id"],
                        "display_order": int(sample["displayOrder"]),
                        "run_id": run,
                        "condition": condition,
                        "output_id": generation["taskId"],
                        "pair_id": f"{step_id}|run{run}",
                        "pair_transition": pair["transition"],
                        "prm_rating": int(pair["rating"]),
                        "step_type_analysis": analysis_type,
                        "step_type_human_calibrated": human["newStepType"].lower(),
                        "position_bin": pair["position"].lower(),
                        "question": sample["problem"],
                        "target_step_text": sample["targetText"],
                        "target_step_index": int(sample["stepIndex"]),
                        "ground_truth_answer": generation["groundTruthAnswer"],
                        "candidate_output": generation["continuation"],
                        "final_answer_raw": generation["finalAnswer"],
                        "final_answer_normalized": normalize_space(generation["finalAnswer"]),
                        "judge_label": int(is_correct),
                        "judge_reason": judge["judgeReason"],
                        "judge_model": judge["judgeModel"],
                        "human_label": "",
                        "human_final_answer_normalized": "",
                        "human_reason": "",
                        "human_tool_needed": "",
                        "human_confidence": "",
                        "generator_status": generation["generatorStatus"],
                        "generator_status_reason": generation["generatorStatusReason"],
                        "generator_model": generation["model"],
                        "temperature": generation["temperature"],
                        "top_p": generation["topP"],
                        "prompt_tokens": int(generation["promptTokens"]),
                        "completion_tokens": int(generation["completionTokens"]),
                        "reasoning_tokens": int(generation["reasoningTokens"]),
                        "visible_tokens": int(generation["visibleOutputTokens"]),
                        "output_characters": len(str(generation["continuation"])),
                        "generated_at": generation["generatedAt"],
                        "seed": "",
                        "placebo_order": "",
                        "placebo_step_index": "",
                        "placebo_step_tokens": "",
                        "placebo_position_bin": "",
                        "length_ratio": "",
                    }
                )

        if len(set(target_token_values)) != 1 or len(set(prefix_token_values)) != 1:
            raise ValueError(f"Prompt-derived token lengths vary across runs for {step_id}")
        target_tokens = target_token_values[0]
        prefix_tokens = prefix_token_values[0]

        selected = sorted(
            selection_by_step.get(step_id, []), key=lambda row: int(row["placeboOrder"])
        )
        placebo_correct: list[bool] = []
        placebo_visible_tokens: list[int] = []
        placebo_statuses: Counter[str] = Counter()

        for selection in selected:
            task_id = str(selection["taskId"])
            generation = placebo_worker_by_task[task_id]
            judge = placebo_judge_by_task[task_id]
            is_correct = parse_bool(judge["correct"])
            placebo_correct.append(is_correct)
            placebo_visible_tokens.append(int(generation["visibleOutputTokens"]))
            placebo_statuses[str(generation["generatorStatus"])] += 1

            p_index = int(selection["placeboStepIndex"])
            total_steps = int(selection["trajectorySteps"])
            run_rows.append(
                {
                    "step_id": step_id,
                    "problem_id": identity["problem_id"],
                    "trajectory_id": identity["trajectory_id"],
                    "display_order": int(sample["displayOrder"]),
                    "run_id": f"P{int(selection['placeboOrder'])}",
                    "condition": "placebo_delete",
                    "output_id": task_id,
                    "pair_id": "",
                    "pair_transition": "",
                    "prm_rating": int(generation["rating"]),
                    "step_type_analysis": analysis_type,
                    "step_type_human_calibrated": human["newStepType"].lower(),
                    "position_bin": str(generation["position"]).lower(),
                    "question": sample["problem"],
                    "target_step_text": sample["targetText"],
                    "target_step_index": int(sample["stepIndex"]),
                    "ground_truth_answer": generation["groundTruthAnswer"],
                    "candidate_output": generation["continuation"],
                    "final_answer_raw": generation["finalAnswer"],
                    "final_answer_normalized": normalize_space(generation["finalAnswer"]),
                    "judge_label": int(is_correct),
                    "judge_reason": judge["judgeReason"],
                    "judge_model": judge["judgeModel"],
                    "human_label": "",
                    "human_final_answer_normalized": "",
                    "human_reason": "",
                    "human_tool_needed": "",
                    "human_confidence": "",
                    "generator_status": generation["generatorStatus"],
                    "generator_status_reason": generation["generatorStatusReason"],
                    "generator_model": generation["model"],
                    "temperature": generation["temperature"],
                    "top_p": generation["topP"],
                    "prompt_tokens": int(generation["promptTokens"]),
                    "completion_tokens": int(generation["completionTokens"]),
                    "reasoning_tokens": int(generation["reasoningTokens"]),
                    "visible_tokens": int(generation["visibleOutputTokens"]),
                    "output_characters": len(str(generation["continuation"])),
                    "generated_at": generation["generatedAt"],
                    "seed": "",
                    "placebo_order": int(selection["placeboOrder"]),
                    "placebo_step_index": p_index,
                    "placebo_step_tokens": int(selection["placeboStepTokens"]),
                    "placebo_position_bin": position_bin(p_index, total_steps),
                    "length_ratio": round(float(selection["lengthRatio"]), 6),
                }
            )

        control_avg = n_control_correct / 4
        target_avg = n_target_correct / 4
        target_effect = target_avg - control_avg
        placebo_avg = safe_mean(int(value) for value in placebo_correct)
        placebo_effect = None if placebo_avg is None else placebo_avg - control_avg
        pure_semantic = None if placebo_avg is None else target_avg - placebo_avg

        step_rows.append(
            {
                "step_id": step_id,
                "problem_id": identity["problem_id"],
                "trajectory_id": identity["trajectory_id"],
                "display_order": int(sample["displayOrder"]),
                "target_key": sample["targetKey"],
                "source_dataset": sample["source"]["dataset"],
                "source_phase": sample["source"]["phase"],
                "source_split": sample["source"]["split"],
                "source_line": sample["source"]["line"],
                "problem": sample["problem"],
                "ground_truth_answer": sample["groundTruthAnswer"],
                "target_step_text": sample["targetText"],
                "target_step_index": int(sample["stepIndex"]),
                "target_step_number": int(sample["stepNumber"]),
                "total_steps": int(sample["totalSteps"]),
                "prm_rating": int(sample["rating"]),
                "step_type_analysis": analysis_type,
                "step_type_initial": human["oldStepType"].lower(),
                "step_type_human_calibrated": human["newStepType"].lower(),
                "removable_analysis": analysis_removable_label,
                "removable_initial": human["oldRemovable"].lower(),
                "removable_human_calibrated": human["newRemovable"].lower(),
                "human_calibration_confidence": human["newConfidence"],
                "human_calibration_reason": human["newReason"],
                "position_bin": str(sample["position"]).lower(),
                "position_ratio": round(float(sample["positionRatio"]), 6),
                "target_tokens": target_tokens,
                "prefix_tokens": prefix_tokens,
                "control_correct_count": n_control_correct,
                "target_correct_count": n_target_correct,
                "control_correct_frequency": f"{n_control_correct}/4",
                "control_avg_correct": rounded(control_avg),
                "target_avg_correct": rounded(target_avg),
                "wrong_to_correct_count": n_wc,
                "correct_to_wrong_count": n_cw,
                "still_correct_count": n_sc,
                "still_wrong_count": n_sw,
                "net_correctness_gain": rounded((n_wc - n_cw) / 4),
                "danger_rate": rounded(n_cw / n_control_correct if n_control_correct else None),
                "recovery_rate": rounded(
                    n_wc / (4 - n_control_correct) if n_control_correct < 4 else None
                ),
                "sign_conflict": int(n_wc > 0 and n_cw > 0),
                "control_stability": f"correct_{n_control_correct}_of_4",
                "target_effect": rounded(target_effect),
                "mean_control_visible_tokens": rounded(
                    safe_mean(int(row["visibleOutputTokens"]) for row in control_generations)
                ),
                "mean_target_visible_tokens": rounded(
                    safe_mean(int(row["visibleOutputTokens"]) for row in target_generations)
                ),
                "mean_target_minus_control_tokens": rounded(
                    safe_mean(
                        int(target["visibleOutputTokens"])
                        - int(control["visibleOutputTokens"])
                        for control, target in zip(
                            control_generations, target_generations, strict=True
                        )
                    )
                ),
                "mean_tokens_saved": rounded(
                    safe_mean(int(row["tokensSaved"]) for row in step_pairs)
                ),
                "control_status_counts": json_cell(
                    dict(sorted(Counter(row["controlStatus"] for row in step_pairs).items()))
                ),
                "target_status_counts": json_cell(
                    dict(sorted(Counter(row["deletedStatus"] for row in step_pairs).items()))
                ),
                "placebo_eligible": int(bool(selected)),
                "placebo_run_count": len(selected),
                "placebo_eligible_candidate_count": (
                    int(selected[0]["eligibleCandidateCount"]) if selected else 0
                ),
                "placebo_task_ids": json_cell([row["taskId"] for row in selected]),
                "placebo_step_indices": json_cell(
                    [int(row["placeboStepIndex"]) for row in selected]
                ),
                "placebo_step_tokens": json_cell(
                    [int(row["placeboStepTokens"]) for row in selected]
                ),
                "placebo_position_bins": json_cell(
                    [
                        position_bin(
                            int(row["placeboStepIndex"]), int(row["trajectorySteps"])
                        )
                        for row in selected
                    ]
                ),
                "placebo_correct_labels": json_cell([int(value) for value in placebo_correct]),
                "placebo_avg_correct": rounded(placebo_avg),
                "placebo_effect": rounded(placebo_effect),
                "pure_semantic_effect": rounded(pure_semantic),
                "mean_placebo_visible_tokens": rounded(
                    safe_mean(placebo_visible_tokens)
                ),
                "placebo_status_counts": json_cell(dict(sorted(placebo_statuses.items()))),
            }
        )

    if len(step_rows) != 600:
        raise ValueError(f"Expected 600 step rows, found {len(step_rows)}")
    if len(run_rows) != 6314:
        raise ValueError(f"Expected 6314 run rows, found {len(run_rows)}")
    output_ids = [row["output_id"] for row in run_rows]
    if len(set(output_ids)) != len(output_ids):
        raise ValueError("Master run output IDs are not unique")
    condition_counts = Counter(row["condition"] for row in run_rows)
    expected_conditions = {
        "control": 2400,
        "target_delete": 2400,
        "placebo_delete": 1514,
    }
    if condition_counts != expected_conditions:
        raise ValueError(
            f"Unexpected master-run condition counts: {dict(condition_counts)}"
        )

    step_fields = list(step_rows[0])
    run_fields = list(run_rows[0])
    write_csv(args.step_output, step_rows, step_fields)
    write_csv(args.run_output, run_rows, run_fields)

    print(
        json.dumps(
            {
                "step_output": args.step_output,
                "step_rows": len(step_rows),
                "run_output": args.run_output,
                "run_rows": len(run_rows),
                "condition_counts": dict(condition_counts),
                "placebo_eligible_steps": sum(
                    int(row["placebo_eligible"]) for row in step_rows
                ),
                "placebo_skipped_steps": sum(
                    not int(row["placebo_eligible"]) for row in step_rows
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
