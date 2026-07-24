#!/usr/bin/env python3
"""Workstream M6: ProcessBench external validation.

Sampling (plan section 10.2): 300 target steps = 150 first-error steps +
150 locally-correct steps, balanced across the four source datasets,
early/middle/late positions, and source generators; at most one target per
record and two per problem. Conditions: control / target deletion /
position-and-length-matched placebo (char-length within +/-20%, closest
relative position), 3 runs each, generator Qwen3-8B under the frozen
protocol. Gold answers come from source datasets (99.5% coverage).

Subcommands: sample | generate | judge | analyze
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from analysis_common import (
    ROOT,
    SEED,
    fmt,
    percentile_interval,
    read_csv,
    stable_hash,
    write_csv,
)
from openrouter_workers import judge_generations, run_generation_tasks

OUT_DIR = ROOT / "workstream_M6_processbench"
DATA_DIR = OUT_DIR / "data"
SUBSETS = ["gsm8k", "math", "olympiadbench", "omnimath"]
GENERATOR_MODEL = "qwen/qwen3-8b"
RUNS = 3
PER_SUBSET_ERROR = 38
PER_SUBSET_CORRECT = 37


def position_bin(index: int, total: int) -> str:
    ratio = index / max(1, total - 1)
    return "early" if ratio < 1 / 3 else ("middle" if ratio < 2 / 3 else "late")


def placebo_matches(steps: list[str], k: int, max_matches: int = 3) -> list[int]:
    target_length = max(1, len(steps[k]))
    candidates = []
    for j, step in enumerate(steps):
        if j == k:
            continue
        ratio = len(step) / target_length
        if 0.8 <= ratio <= 1.2:
            candidates.append((abs(j - k), j))
    candidates.sort()
    return [j for _, j in candidates[:max_matches]]


def load_gold() -> dict[str, dict]:
    return json.loads((OUT_DIR / "gold_answers.json").read_text(encoding="utf-8"))["answers"]


def build_pools() -> dict[str, dict[str, list[dict]]]:
    gold = load_gold()
    pools: dict[str, dict[str, list[dict]]] = {}
    for subset in SUBSETS:
        records = json.load((DATA_DIR / f"{subset}.json").open())
        error_pool, correct_pool = [], []
        for record in records:
            key = f"{subset}|{record['id']}"
            if key not in gold or not record["steps"] or len(record["steps"]) < 3:
                continue
            base = {
                "subset": subset,
                "record_id": record["id"],
                "sample_key": key,
                "problem": record["problem"],
                "steps": record["steps"],
                "source_generator": record["generator"],
                "gold": gold[key]["gold"],
                "gold_source": gold[key]["source"],
                "final_answer_correct": record["final_answer_correct"],
            }
            label = record["label"]
            if label >= 0 and label < len(record["steps"]):
                error_pool.append({**base, "target_index": label, "step_class": "first_error"})
            if label == -1:
                index = stable_hash("m6pos|" + key) % len(record["steps"])
                correct_pool.append(
                    {**base, "target_index": index, "step_class": "locally_correct"}
                )
            elif label >= 2:
                index = stable_hash("m6pre|" + key) % label
                correct_pool.append(
                    {**base, "target_index": index, "step_class": "locally_correct_pre_error"}
                )
        pools[subset] = {"error": error_pool, "correct": correct_pool}
    return pools


def quota_pick(pool: list[dict], size: int) -> list[dict]:
    for item in pool:
        item["_pos"] = position_bin(item["target_index"], len(item["steps"]))
    picked: list[dict] = []
    used_problems: dict[str, int] = defaultdict(int)
    bins = ["early", "middle", "late"]
    base, extra = divmod(size, 3)
    quotas = {b: base + (1 if i < extra else 0) for i, b in enumerate(bins)}
    for bin_name in bins:
        candidates = sorted(
            (x for x in pool if x["_pos"] == bin_name),
            key=lambda x: (
                used_problems[x["problem"][:80]],
                stable_hash("m6gen|" + x["source_generator"]) % 7,
                stable_hash("m6|" + x["sample_key"]),
            ),
        )
        count = 0
        for item in candidates:
            if count >= quotas[bin_name]:
                break
            if used_problems[item["problem"][:80]] >= 2:
                continue
            picked.append(item)
            used_problems[item["problem"][:80]] += 1
            count += 1
    remaining = [x for x in pool if x not in picked]
    for item in sorted(remaining, key=lambda x: stable_hash("m6fill|" + x["sample_key"])):
        if len(picked) >= size:
            break
        if used_problems[item["problem"][:80]] >= 2:
            continue
        picked.append(item)
        used_problems[item["problem"][:80]] += 1
    return picked


def cmd_sample() -> None:
    pools = build_pools()
    cohort = []
    for subset in SUBSETS:
        cohort += quota_pick(pools[subset]["error"], PER_SUBSET_ERROR)
        cohort += quota_pick(pools[subset]["correct"], PER_SUBSET_CORRECT)
    # A record with label >= 2 can be sampled twice (first-error AND
    # pre-error locally-correct target). Disambiguate the second occurrence
    # so task ids never collide across different target indices.
    seen: set[str] = set()
    for item in cohort:
        if item["sample_key"] in seen:
            item["sample_key"] = f"{item['sample_key']}|s{item['target_index']}"
        seen.add(item["sample_key"])
    contexts = {}
    manifest = []
    tasks = []
    for item in cohort:
        sid = item["sample_key"]
        k = item["target_index"]
        contexts[sid] = {
            "step_id": sid,
            "problem": item["problem"],
            "steps": item["steps"],
            "target_index": k,
            "ground_truth_answer": item["gold"],
        }
        placebos = placebo_matches(item["steps"], k)
        manifest.append(
            {
                "sample_key": sid,
                "subset": item["subset"],
                "step_class": item["step_class"],
                "target_index": k,
                "total_steps": len(item["steps"]),
                "position_bin": position_bin(k, len(item["steps"])),
                "source_generator": item["source_generator"],
                "gold_source": item["gold_source"],
                "final_answer_correct": int(item["final_answer_correct"]),
                "placebo_eligible": int(bool(placebos)),
                "placebo_indices": json.dumps(placebos),
            }
        )
        for run in range(1, RUNS + 1):
            for condition, prefix_last in (("control", k), ("target_delete", k - 1)):
                tasks.append(
                    {
                        "taskId": f"{sid}|m6run{run}|{condition}",
                        "sampleId": sid,
                        "condition": condition,
                        "run": run,
                        "prefixLast": prefix_last,
                        "groundTruthAnswer": item["gold"],
                        "subset": item["subset"],
                        "stepClass": item["step_class"],
                        "sourceGenerator": item["source_generator"],
                        "targetStepIndex": k,
                    }
                )
            if placebos:
                placebo_index = placebos[(run - 1) % len(placebos)]
                tasks.append(
                    {
                        "taskId": f"{sid}|m6run{run}|placebo_delete",
                        "sampleId": sid,
                        "condition": "placebo_delete",
                        "run": run,
                        "prefixLast": placebo_index - 1,
                        "placeboStepIndex": placebo_index,
                        "groundTruthAnswer": item["gold"],
                        "subset": item["subset"],
                        "stepClass": item["step_class"],
                        "sourceGenerator": item["source_generator"],
                        "targetStepIndex": k,
                    }
                )
    with (OUT_DIR / "m6_contexts.jsonl").open("w", encoding="utf-8") as sink:
        for ctx in contexts.values():
            sink.write(json.dumps(ctx, ensure_ascii=False) + "\n")
    write_csv(OUT_DIR / "m6_sampling_manifest.csv", manifest)
    with (OUT_DIR / "m6_generation_tasks.jsonl").open("w", encoding="utf-8") as sink:
        for task in tasks:
            sink.write(json.dumps(task, ensure_ascii=False) + "\n")
    from collections import Counter

    print(
        "cohort:", len(cohort),
        Counter(m["subset"] for m in manifest),
        Counter(m["step_class"] for m in manifest),
        "placebo eligible:", sum(m["placebo_eligible"] for m in manifest),
        "tasks:", len(tasks),
    )


def load_m6_contexts() -> dict[str, dict]:
    contexts = {}
    with (OUT_DIR / "m6_contexts.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            contexts[record["step_id"]] = record
    return contexts


def cmd_generate() -> None:
    contexts = load_m6_contexts()
    tasks = [
        json.loads(line)
        for line in (OUT_DIR / "m6_generation_tasks.jsonl").open(encoding="utf-8")
        if line.strip()
    ]
    run_generation_tasks(
        tasks,
        contexts,
        OUT_DIR / "m6_generations.jsonl",
        model=GENERATOR_MODEL,
        workers=8,
        max_tokens=2048,
        no_think=True,
        json_mode=True,
    )


def cmd_judge() -> None:
    judge_generations(
        OUT_DIR / "m6_generations.jsonl",
        load_m6_contexts(),
        OUT_DIR / "m6_judgments.jsonl",
    )


def cmd_analyze() -> None:
    judgments = {}
    with (OUT_DIR / "m6_judgments.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                judgments[record["taskId"]] = record["correct"]
    by_step: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    meta: dict[str, dict] = {}
    with (OUT_DIR / "m6_generations.jsonl").open(encoding="utf-8") as handle:
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
                "subset": record["subset"],
                "step_class": record["stepClass"],
            }
    rows = []
    for sid, conditions in by_step.items():
        control = conditions.get("control", [])
        target = conditions.get("target_delete", [])
        placebo = conditions.get("placebo_delete", [])
        if not control or not target:
            continue
        control_rate = sum(control) / len(control)
        target_rate = sum(target) / len(target)
        row = {
            "sample_key": sid,
            **meta[sid],
            "control_rate": control_rate,
            "target_rate": target_rate,
            "target_effect": target_rate - control_rate,
            "danger": int(any(c == 1 for c in control) and target_rate < control_rate),
            "benefit": int(any(c == 0 for c in control) and target_rate > control_rate),
        }
        if placebo:
            placebo_rate = sum(placebo) / len(placebo)
            row["placebo_effect"] = placebo_rate - control_rate
            row["pure_semantic_effect"] = target_rate - placebo_rate
        rows.append(row)
    write_csv(OUT_DIR / "m6_step_effects.csv", rows)

    def boot(values: list[float]) -> tuple[float, float]:
        rng = random.Random(SEED)
        draws = [
            sum(values[rng.randrange(len(values))] for _ in values) / len(values)
            for _ in range(5000)
        ]
        return percentile_interval(draws)

    summary = []
    groups: dict[str, list[dict]] = {
        "overall": rows,
        "first_error": [r for r in rows if r["step_class"] == "first_error"],
        "locally_correct": [
            r for r in rows if r["step_class"].startswith("locally_correct")
        ],
    }
    for subset in SUBSETS:
        groups[f"subset:{subset}"] = [r for r in rows if r["subset"] == subset]
    for name, subset_rows in groups.items():
        for key in ("target_effect", "placebo_effect", "pure_semantic_effect"):
            values = [r[key] for r in subset_rows if key in r]
            if len(values) < 15:
                continue
            low, high = boot(values)
            summary.append(
                {
                    "group": name,
                    "estimand": key,
                    "steps": len(values),
                    "estimate_pp": fmt(100 * sum(values) / len(values), 2),
                    "ci_lower_pp": fmt(100 * low, 2),
                    "ci_upper_pp": fmt(100 * high, 2),
                }
            )
    write_csv(OUT_DIR / "m6_effect_summary.csv", summary)
    for row in summary:
        print(row)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "sample"
    {
        "sample": cmd_sample,
        "generate": cmd_generate,
        "judge": cmd_judge,
        "analyze": cmd_analyze,
    }[command]()
