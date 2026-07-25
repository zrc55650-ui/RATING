#!/usr/bin/env python3
"""M10: long-CoT generator replication (DeepSeek-R1-Distill-Qwen-14B).

Reuses the exact M2 cohort and task list (300 steps x 3 conditions x 3 runs)
so the two replications are directly comparable. Generation runs on a GPU box
via server_r1_executor.py against a local vLLM endpoint; judging reuses the
frozen Qwen3-8B judge pipeline.

Subcommands:
    export    build self-contained prompt tasks (m10_prompt_tasks.jsonl)
    judge     judge returned m10_generations.jsonl
    analyze   effects + placebo-corrected contrasts + sign agreement
"""

from __future__ import annotations

import json
import math
import random as rnd
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis_common import ROOT, SEED, fmt, percentile_interval, write_csv  # noqa: E402
from openrouter_workers import (  # noqa: E402
    GENERATION_SYSTEM_PROMPT,
    build_visible_prefix,
    judge_generations,
    load_contexts,
)
from run_m2_pipeline import load_steps  # noqa: E402

OUT_DIR = ROOT / "workstream_M10_longcot_replication"
M2_DIR = ROOT / "workstream_M2_cross_generator"
GENERATOR_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B"


def cmd_export() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    tasks = [
        json.loads(line)
        for line in (M2_DIR / "m2_generation_tasks.jsonl").open(encoding="utf-8")
        if line.strip()
    ]
    with (OUT_DIR / "m10_prompt_tasks.jsonl").open("w", encoding="utf-8") as sink:
        for task in tasks:
            sample = contexts[task["sampleId"]]
            prefix = build_visible_prefix(sample["steps"], int(task["prefixLast"]), None)
            record = dict(task)
            record["taskId"] = task["taskId"].replace("|m2run", "|m10run")
            record["system"] = GENERATION_SYSTEM_PROMPT
            record["user"] = (
                f"MATHEMATICS PROBLEM:\n{sample['problem']}\n\n"
                f"VISIBLE SOLUTION PREFIX:\n{prefix}"
            )
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"exported {len(tasks)} prompt tasks -> {OUT_DIR / 'm10_prompt_tasks.jsonl'}")


def cmd_judge() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    judge_generations(
        OUT_DIR / "m10_generations.jsonl",
        contexts,
        OUT_DIR / "m10_judgments.jsonl",
    )


def cmd_analyze() -> None:
    judgments = {}
    with (OUT_DIR / "m10_judgments.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                judgments[record["taskId"]] = record["correct"]
    by_step: dict[str, dict] = defaultdict(lambda: defaultdict(list))
    meta: dict[str, dict] = {}
    with (OUT_DIR / "m10_generations.jsonl").open(encoding="utf-8") as handle:
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
    write_csv(OUT_DIR / "m10_step_effects.csv", rows)
    write_csv(OUT_DIR / "m10_effect_summary.csv", summary_rows)

    qwen = {s["step_id"]: s for s in load_steps()}
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
    (OUT_DIR / "m10_longcot_summary.json").write_text(
        json.dumps(
            {
                "generator": GENERATOR_MODEL,
                "steps_analyzed": len(rows),
                "sign_agreement_vs_qwen_nonzero": sign_agreement,
                "nonzero_pairs": len(both_nonzero),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for row in summary_rows:
        print(row)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "export"
    {"export": cmd_export, "judge": cmd_judge, "analyze": cmd_analyze}[command]()
