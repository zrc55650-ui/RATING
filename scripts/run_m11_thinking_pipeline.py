#!/usr/bin/env python3
"""M11: within-checkpoint thinking-mode contrast (Qwen3-8B, /think vs /no_think).

Review issue: attributing the long-CoT anchor collapse to "extended thinking"
from the R1-Distill replication confounds model, scale, training data, and
thinking mode. The clean contrast holds the checkpoint, provider, prompts,
and sampling fixed and toggles only the thinking mode: the primary cohort ran
qwen/qwen3-8b with /no_think; M11 reruns the identical M2 task list (plus
placebo own-controls) with thinking enabled.

Subcommands:
    export    build m11 tasks (M2 list -> |m11run, + 891 placebo controls |m11cp)
    probe     generate 20 tasks, report reasoning-token activation + parse rate
    generate  full generation via OpenRouter (no_think=False)
    judge     frozen qwen3-8b judge
    analyze   effects, DiD, and thinking-vs-no-thinking contrast on shared steps
"""

from __future__ import annotations

import json
import math
import random as rnd
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis_common import ROOT, SEED, as_int, fmt, percentile_interval, write_csv  # noqa: E402
from openrouter_workers import (  # noqa: E402
    judge_generations,
    load_contexts,
    run_generation_tasks,
)
from run_m2_pipeline import load_steps  # noqa: E402

OUT_DIR = ROOT / "workstream_M11_thinking_toggle"
M2_DIR = ROOT / "workstream_M2_cross_generator"
GENERATOR_MODEL = "qwen/qwen3-8b"
# Qwen3-8B thinking phases run long (10k+ tokens observed); give the full
# budget and disable json_mode, which corrupts the post-thinking content
# phase (same lesson as the R1 executor).
MAX_TOKENS = 24576


def build_tasks() -> list[dict]:
    tasks = []
    for line in (M2_DIR / "m2_generation_tasks.jsonl").open(encoding="utf-8"):
        if not line.strip():
            continue
        task = json.loads(line)
        record = dict(task)
        record["taskId"] = task["taskId"].replace("|m2run", "|m11run")
        tasks.append(record)
        if task["condition"] == "placebo_delete":
            p = as_int(task["placeboStepIndex"])
            cp = dict(task)
            cp["taskId"] = task["taskId"].replace("|m2run", "|m11cp") + f"|step{p}"
            cp["condition"] = "placebo_control"
            cp["prefixLast"] = p
            tasks.append(cp)
    return tasks


def cmd_export() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    tasks = build_tasks()
    with (OUT_DIR / "m11_tasks.jsonl").open("w", encoding="utf-8") as sink:
        for task in tasks:
            sink.write(json.dumps(task, ensure_ascii=False) + "\n")
    from collections import Counter
    print(f"exported {len(tasks)} tasks", Counter(t["condition"] for t in tasks))


def _generate(tasks: list[dict], out_name: str) -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    run_generation_tasks(
        tasks,
        contexts,
        OUT_DIR / out_name,
        model=GENERATOR_MODEL,
        workers=96,
        max_tokens=MAX_TOKENS,
        no_think=False,
        json_mode=False,
    )


def cmd_probe() -> None:
    tasks = build_tasks()
    rng = rnd.Random(SEED)
    sample = rng.sample(tasks, 20)
    _generate(sample, "m11_probe_generations.jsonl")
    n = think = parsed = 0
    with (OUT_DIR / "m11_probe_generations.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            n += 1
            think += 1 if record.get("reasoningTokens", 0) > 0 else 0
            parsed += 1 if record.get("parseOk") else 0
    print(f"probe: {n} generated, {think} with reasoning tokens, {parsed} parsed")


def cmd_generate() -> None:
    tasks = [
        json.loads(line)
        for line in (OUT_DIR / "m11_tasks.jsonl").open(encoding="utf-8")
        if line.strip()
    ]
    _generate(tasks, "m11_generations.jsonl")


def cmd_judge() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    judge_generations(
        OUT_DIR / "m11_generations.jsonl",
        contexts,
        OUT_DIR / "m11_judgments.jsonl",
    )


def cmd_analyze() -> None:
    judgments = {}
    with (OUT_DIR / "m11_judgments.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                judgments[record["taskId"]] = 1 if record["correct"] else 0
    by_step: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    cp_by_pair: dict[tuple[str, int], list[int]] = defaultdict(list)
    pd_by_pair: dict[tuple[str, int], list[int]] = defaultdict(list)
    meta: dict[str, dict] = {}
    think_tokens = []
    with (OUT_DIR / "m11_generations.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record["taskId"] not in judgments:
                continue
            y = judgments[record["taskId"]]
            think_tokens.append(record.get("reasoningTokens", 0))
            sid = record["sampleId"]
            if record["condition"] == "placebo_control":
                cp_by_pair[(sid, as_int(record["placeboStepIndex"]))].append(y)
                continue
            if record["condition"] == "placebo_delete":
                pd_by_pair[(sid, as_int(record["placeboStepIndex"]))].append(y)
            by_step[sid][record["condition"]].append(y)
            meta[sid] = {
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
            row["placebo_legacy_effect"] = placebo_rate - control_rate
            row["legacy_semantic_effect"] = row["target_effect"] - row["placebo_legacy_effect"]
            pairs = [
                (pd_by_pair[(step_id, p)], cp_by_pair[(step_id, p)])
                for (s, p) in pd_by_pair
                if s == step_id and cp_by_pair.get((step_id, p))
            ]
            if pairs:
                own = [
                    sum(pd) / len(pd) - sum(cp) / len(cp) for pd, cp in pairs
                ]
                row["placebo_own_effect"] = sum(own) / len(own)
                row["did_semantic_effect"] = row["target_effect"] - row["placebo_own_effect"]
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
        for key in (
            "target_effect",
            "placebo_legacy_effect",
            "legacy_semantic_effect",
            "placebo_own_effect",
            "did_semantic_effect",
        ):
            result = summarize(name, subset, key)
            if result:
                summary_rows.append(result)
    write_csv(OUT_DIR / "m11_step_effects.csv", rows)
    write_csv(OUT_DIR / "m11_effect_summary.csv", summary_rows)

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
    (OUT_DIR / "m11_summary.json").write_text(
        json.dumps(
            {
                "generator": GENERATOR_MODEL + " (thinking enabled)",
                "steps_analyzed": len(rows),
                "mean_reasoning_tokens": (
                    sum(think_tokens) / len(think_tokens) if think_tokens else 0
                ),
                "share_with_reasoning": (
                    sum(1 for t in think_tokens if t > 0) / len(think_tokens)
                    if think_tokens
                    else 0
                ),
                "sign_agreement_vs_nothink_nonzero": sign_agreement,
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
    {
        "export": cmd_export,
        "probe": cmd_probe,
        "generate": cmd_generate,
        "judge": cmd_judge,
        "analyze": cmd_analyze,
    }[command]()
