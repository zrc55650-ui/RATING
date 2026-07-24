#!/usr/bin/env python3
"""Workstream M2: cross-generator replication pipeline.

Subcommands:
  sample    build the 300-step manifest + condition task list (plan section 6.3)
  generate  run continuations with the second generator (checkpointed)
  judge     judge final answers with the frozen judge protocol
  analyze   per-generator effects + cross-generator comparison vs Qwen3-8B

Sampling quotas: 100 steps per rating; all 100 rating=-1 steps drawn from the
rating=-1 x human-calibrated-Harmful pool (>=100 anchor requirement); 40
control-stable-correct steps within each of rating 0 and rating 1 (>=80
total); early/middle/late balanced inside every cell; placebo condition only
for placebo-eligible steps, reusing the frozen matched placebo indices.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from analysis_common import (
    ROOT,
    as_float,
    as_int,
    fmt,
    read_csv,
    stable_hash,
    write_csv,
)
from openrouter_workers import (
    judge_generations,
    load_contexts,
    run_generation_tasks,
)

OUT_DIR = ROOT / "workstream_M2_cross_generator"
GENERATOR_MODEL = "microsoft/phi-4"
RUNS_PER_CONDITION = 3
POSITION_BINS = ["early", "middle", "late"]


def load_steps() -> list[dict]:
    steps = []
    for row in read_csv(ROOT / "data" / "master_step_table.csv"):
        steps.append(
            {
                "step_id": row["step_id"],
                "problem_id": row["problem_id"],
                "rating": as_int(row["prm_rating"]),
                "type_hc": row["step_type_human_calibrated"].strip().lower(),
                "position_bin": row["position_bin"],
                "target_step_index": as_int(row["target_step_index"]),
                "control_correct_count": as_int(row["control_correct_count"]),
                "placebo_eligible": row["placebo_eligible"].strip() == "1",
                "placebo_step_indices": json.loads(row["placebo_step_indices"] or "[]"),
                "ground_truth_answer": row["ground_truth_answer"],
                "qwen_target_effect": as_float(row["target_effect"]),
                "qwen_pure_semantic_effect": as_float(row["pure_semantic_effect"]),
            }
        )
    return steps


def orderer(step: dict) -> tuple:
    return (not step["placebo_eligible"], stable_hash("m2|" + step["step_id"]))


def position_quota_pick(pool: list[dict], size: int) -> list[dict]:
    base, extra = divmod(size, len(POSITION_BINS))
    quotas = {
        b: base + (1 if i < extra else 0) for i, b in enumerate(POSITION_BINS)
    }
    picked: list[dict] = []
    picked_ids: set[str] = set()
    for bin_name in POSITION_BINS:
        candidates = sorted(
            (s for s in pool if s["position_bin"] == bin_name), key=orderer
        )
        take = candidates[: quotas[bin_name]]
        picked.extend(take)
        picked_ids.update(s["step_id"] for s in take)
    if len(picked) < size:
        rest = sorted((s for s in pool if s["step_id"] not in picked_ids), key=orderer)
        picked.extend(rest[: size - len(picked)])
    return picked


def sample_cohort(steps: list[dict]) -> list[dict]:
    chosen: list[dict] = []
    chosen_ids: set[str] = set()

    anchor_pool = [s for s in steps if s["rating"] == -1 and s["type_hc"] == "harmful"]
    group = position_quota_pick(anchor_pool, 100)
    for s in group:
        s["_m2_cell"] = "rating-1_anchor"
    chosen += group
    chosen_ids |= {s["step_id"] for s in group}

    for rating in (0, 1):
        rating_pool = [
            s for s in steps if s["rating"] == rating and s["step_id"] not in chosen_ids
        ]
        stable_pool = [s for s in rating_pool if s["control_correct_count"] == 4]
        stable_pick = position_quota_pick(stable_pool, 40)
        for s in stable_pick:
            s["_m2_cell"] = f"rating{rating}_stable"
        chosen += stable_pick
        chosen_ids |= {s["step_id"] for s in stable_pick}
        other_pool = [
            s
            for s in rating_pool
            if s["step_id"] not in chosen_ids and s["control_correct_count"] < 4
        ]
        other_pick = position_quota_pick(other_pool, 60)
        for s in other_pick:
            s["_m2_cell"] = f"rating{rating}_other"
        chosen += other_pick
        chosen_ids |= {s["step_id"] for s in other_pick}
    return chosen


def build_tasks(cohort: list[dict]) -> list[dict]:
    tasks = []
    for step in cohort:
        k = step["target_step_index"]
        conditions = [("control", k), ("target_delete", k - 1)]
        placebo_indices = step["placebo_step_indices"][:RUNS_PER_CONDITION]
        for run in range(1, RUNS_PER_CONDITION + 1):
            for condition, prefix_last in conditions:
                tasks.append(
                    {
                        "taskId": f"{step['step_id']}|m2run{run}|{condition}",
                        "sampleId": step["step_id"],
                        "condition": condition,
                        "run": run,
                        "prefixLast": prefix_last,
                        "groundTruthAnswer": step["ground_truth_answer"],
                        "rating": step["rating"],
                        "stepTypeHC": step["type_hc"],
                        "m2Cell": step["_m2_cell"],
                        "targetStepIndex": k,
                    }
                )
            if step["placebo_eligible"] and placebo_indices:
                placebo_index = placebo_indices[(run - 1) % len(placebo_indices)]
                tasks.append(
                    {
                        "taskId": f"{step['step_id']}|m2run{run}|placebo_delete",
                        "sampleId": step["step_id"],
                        "condition": "placebo_delete",
                        "run": run,
                        "prefixLast": placebo_index - 1,
                        "placeboStepIndex": placebo_index,
                        "groundTruthAnswer": step["ground_truth_answer"],
                        "rating": step["rating"],
                        "stepTypeHC": step["type_hc"],
                        "m2Cell": step["_m2_cell"],
                        "targetStepIndex": k,
                    }
                )
    return tasks


def cmd_sample() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    steps = load_steps()
    cohort = sample_cohort(steps)
    manifest = [
        {
            "step_id": s["step_id"],
            "problem_id": s["problem_id"],
            "m2_cell": s["_m2_cell"],
            "prm_rating": s["rating"],
            "step_type_human_calibrated": s["type_hc"],
            "position_bin": s["position_bin"],
            "control_correct_count": s["control_correct_count"],
            "placebo_eligible": int(s["placebo_eligible"]),
            "qwen_target_effect": fmt(s["qwen_target_effect"], 4),
            "qwen_pure_semantic_effect": fmt(s["qwen_pure_semantic_effect"], 4),
        }
        for s in cohort
    ]
    write_csv(OUT_DIR / "m2_sampling_manifest.csv", manifest)
    tasks = build_tasks(cohort)
    with (OUT_DIR / "m2_generation_tasks.jsonl").open("w", encoding="utf-8") as sink:
        for task in tasks:
            sink.write(json.dumps(task, ensure_ascii=False) + "\n")
    anchor = sum(1 for s in cohort if s["_m2_cell"] == "rating-1_anchor")
    stable = sum(1 for s in cohort if s["control_correct_count"] == 4)
    eligible = sum(1 for s in cohort if s["placebo_eligible"])
    print(
        f"cohort={len(cohort)} anchor={anchor} stable_correct={stable} "
        f"placebo_eligible={eligible} tasks={len(tasks)}"
    )


def cmd_generate() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    tasks = [
        json.loads(line)
        for line in (OUT_DIR / "m2_generation_tasks.jsonl").open(encoding="utf-8")
        if line.strip()
    ]
    run_generation_tasks(
        tasks,
        contexts,
        OUT_DIR / "m2_generations.jsonl",
        model=GENERATOR_MODEL,
        workers=8,
        max_tokens=4096,
        no_think=False,
        json_mode=True,
    )


def cmd_judge() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    judge_generations(
        OUT_DIR / "m2_generations.jsonl",
        contexts,
        OUT_DIR / "m2_judgments.jsonl",
    )


def cmd_analyze() -> None:
    from collections import defaultdict

    judgments = {}
    with (OUT_DIR / "m2_judgments.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                judgments[record["taskId"]] = record["correct"]
    by_step: dict[str, dict] = defaultdict(lambda: defaultdict(list))
    meta: dict[str, dict] = {}
    with (OUT_DIR / "m2_generations.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record["taskId"] not in judgments:
                continue
            by_step[record["sampleId"]][record["condition"]].append(
                1 if judgments[record["taskId"]] else 0
            )
            meta[record["sampleId"]] = {
                "rating": record["rating"],
                "type_hc": record["stepTypeHC"],
                "cell": record["m2Cell"],
            }

    rows = []
    for step_id, conditions in by_step.items():
        control = conditions.get("control", [])
        target = conditions.get("target_delete", [])
        placebo = conditions.get("placebo_delete", [])
        if not control or not target:
            continue
        control_rate = sum(control) / len(control)
        target_rate = sum(target) / len(target)
        row = {
            "step_id": step_id,
            **meta[step_id],
            "control_runs": len(control),
            "target_runs": len(target),
            "placebo_runs": len(placebo),
            "control_rate": control_rate,
            "target_rate": target_rate,
            "target_effect": target_rate - control_rate,
        }
        if placebo:
            placebo_rate = sum(placebo) / len(placebo)
            row["placebo_rate"] = placebo_rate
            row["placebo_effect"] = placebo_rate - control_rate
            row["pure_semantic_effect"] = target_rate - placebo_rate
        rows.append(row)

    import math
    import random as rnd

    from analysis_common import SEED, percentile_interval

    def boot_ci(values: list[float]) -> tuple[float, float]:
        rng = rnd.Random(SEED)
        draws = [
            sum(values[rng.randrange(len(values))] for _ in values) / len(values)
            for _ in range(5000)
        ]
        return percentile_interval(draws)

    def summarize(name: str, subset: list[dict], key: str) -> dict | None:
        values = [r[key] for r in subset if key in r and not math.isnan(r[key])]
        if len(values) < 10:
            return None
        low, high = boot_ci(values)
        return {
            "group": name,
            "estimand": key,
            "steps": len(values),
            "estimate_pp": fmt(100 * sum(values) / len(values), 2),
            "ci_lower_pp": fmt(100 * low, 2),
            "ci_upper_pp": fmt(100 * high, 2),
        }

    groups = {
        "overall": rows,
        "rating=-1_anchor": [r for r in rows if r["cell"] == "rating-1_anchor"],
        "rating=0": [r for r in rows if r["rating"] == 0],
        "rating=1": [r for r in rows if r["rating"] == 1],
        "stable_correct": [r for r in rows if r["cell"].endswith("_stable")],
    }
    summary_rows = []
    for name, subset in groups.items():
        for key in ("target_effect", "placebo_effect", "pure_semantic_effect"):
            result = summarize(name, subset, key)
            if result:
                summary_rows.append(result)
    write_csv(OUT_DIR / "m2_step_effects.csv", rows)
    write_csv(OUT_DIR / "m2_effect_summary.csv", summary_rows)

    qwen = {
        s["step_id"]: s
        for s in load_steps()
    }
    agree = [
        (r["target_effect"], qwen[r["step_id"]]["qwen_target_effect"])
        for r in rows
        if r["step_id"] in qwen
    ]
    both_nonzero = [(a, b) for a, b in agree if a != 0 and b != 0]
    sign_agreement = (
        sum(1 for a, b in both_nonzero if (a > 0) == (b > 0)) / len(both_nonzero)
        if both_nonzero
        else float("nan")
    )
    (OUT_DIR / "m2_cross_generator_summary.json").write_text(
        json.dumps(
            {
                "generator": GENERATOR_MODEL,
                "steps_analyzed": len(rows),
                "sign_agreement_nonzero_effects": sign_agreement,
                "nonzero_pairs": len(both_nonzero),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for row in summary_rows:
        print(row)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "sample"
    {"sample": cmd_sample, "generate": cmd_generate, "judge": cmd_judge, "analyze": cmd_analyze}[
        command
    ]()
