#!/usr/bin/env python3
"""Workstream M4: strong-control C2 (matched placebo) + C3 (paraphrase) runs.

Subcommands:
  paraphrase  generate semantic-preserving paraphrases for the 240 targets
              with an independent model (not the generator family)
  generate    run C2 + C3 continuations on Qwen3-8B (4 runs each, frozen
              protocol; C2 reuses the frozen matched placebo indices)
  judge       judge final answers
  analyze     four-condition comparison C0/C1 (reused) vs C2/C3 (new)
"""

from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

from analysis_common import (
    ROOT,
    SEED,
    as_int,
    fmt,
    percentile_interval,
    read_csv,
    write_csv,
)
from openrouter_workers import (
    call_chat,
    extract_json_object,
    judge_generations,
    load_api_key,
    load_contexts,
    run_generation_tasks,
)

OUT_DIR = ROOT / "workstream_M4_strong_controls"
PARAPHRASE_MODEL = "google/gemini-2.5-flash"
GENERATOR_MODEL = "qwen/qwen3-8b"
RUNS = 4

PARAPHRASE_PROMPT = """Paraphrase the following step from a mathematical solution.

Requirements:
- Preserve the exact mathematical meaning and the step's conclusion, INCLUDING any errors it contains (do not correct them).
- Do not add or remove information.
- Keep approximately the same length (within 40% of the original).
- Change the wording and sentence structure, not the mathematics.

Step to paraphrase:
{step}

Return only one valid JSON object: {{"paraphrase": "the reworded step"}}"""


def load_manifest() -> list[dict]:
    return read_csv(OUT_DIR / "strong_control_sampling_manifest.csv")


def load_master() -> dict[str, dict]:
    return {
        row["step_id"]: row for row in read_csv(ROOT / "data" / "master_step_table.csv")
    }


def cmd_paraphrase() -> None:
    api_key = load_api_key()
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    manifest = load_manifest()
    out_path = OUT_DIR / "m4_paraphrases.jsonl"
    done = set()
    if out_path.exists():
        with out_path.open(encoding="utf-8") as handle:
            done = {json.loads(line)["step_id"] for line in handle if line.strip()}
    pending = [row for row in manifest if row["step_id"] not in done]
    print(f"paraphrase: {len(done)} done, {len(pending)} pending")
    import threading
    from concurrent.futures import ThreadPoolExecutor

    lock = threading.Lock()
    sink = out_path.open("a", encoding="utf-8")

    def work(row: dict) -> None:
        step_id = row["step_id"]
        target_text = contexts[step_id]["steps"][int(row["target_step_index"])] if "target_step_index" in row else None
        if target_text is None:
            ctx = contexts[step_id]
            target_text = ctx["steps"][ctx["target_index"]]
        for attempt in range(5):
            try:
                response = call_chat(
                    api_key,
                    PARAPHRASE_MODEL,
                    [{"role": "user", "content": PARAPHRASE_PROMPT.format(step=target_text)}],
                    temperature=0.7,
                    top_p=0.95,
                    max_tokens=2048,
                    json_mode=True,
                    no_think=False,
                )
                parsed = extract_json_object(
                    response["choices"][0]["message"].get("content") or ""
                )
                paraphrase = str((parsed or {}).get("paraphrase", "")).strip()
                ratio = len(paraphrase) / max(1, len(target_text))
                if paraphrase and 0.5 <= ratio <= 1.7 and paraphrase != target_text:
                    with lock:
                        sink.write(
                            json.dumps(
                                {
                                    "step_id": step_id,
                                    "original": target_text,
                                    "paraphrase": paraphrase,
                                    "length_ratio": round(ratio, 3),
                                    "model": PARAPHRASE_MODEL,
                                    "attempts": attempt + 1,
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        sink.flush()
                    return
            except Exception as error:  # noqa: BLE001
                if attempt == 4:
                    print(f"PARAPHRASE FAILED {step_id}: {str(error)[:150]}")
        print(f"PARAPHRASE UNUSABLE {step_id}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, pending))
    sink.close()


def build_tasks() -> list[dict]:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    master = load_master()
    paraphrases = {}
    with (OUT_DIR / "m4_paraphrases.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                paraphrases[record["step_id"]] = record["paraphrase"]
    tasks = []
    for row in load_manifest():
        step_id = row["step_id"]
        ctx = contexts[step_id]
        k = ctx["target_index"]
        placebo_indices = json.loads(master[step_id]["placebo_step_indices"] or "[]")
        ground_truth = master[step_id]["ground_truth_answer"]
        for run in range(1, RUNS + 1):
            if placebo_indices:
                placebo_index = placebo_indices[(run - 1) % len(placebo_indices)]
                tasks.append(
                    {
                        "taskId": f"{step_id}|m4run{run}|c2_placebo",
                        "sampleId": step_id,
                        "condition": "c2_placebo",
                        "run": run,
                        "prefixLast": placebo_index - 1,
                        "placeboStepIndex": placebo_index,
                        "groundTruthAnswer": ground_truth,
                        "strongControlGroup": row["strong_control_group"],
                        "targetStepIndex": k,
                    }
                )
            if step_id in paraphrases:
                tasks.append(
                    {
                        "taskId": f"{step_id}|m4run{run}|c3_paraphrase",
                        "sampleId": step_id,
                        "condition": "c3_paraphrase",
                        "run": run,
                        "prefixLast": k,
                        "substitute": {str(k): paraphrases[step_id]},
                        "groundTruthAnswer": ground_truth,
                        "strongControlGroup": row["strong_control_group"],
                        "targetStepIndex": k,
                    }
                )
    return tasks


def cmd_generate() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    tasks = build_tasks()
    print(f"m4 tasks: {len(tasks)}")
    run_generation_tasks(
        tasks,
        contexts,
        OUT_DIR / "m4_generations.jsonl",
        model=GENERATOR_MODEL,
        workers=8,
        max_tokens=2048,
        no_think=True,
        json_mode=True,
    )


def cmd_judge() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    judge_generations(
        OUT_DIR / "m4_generations.jsonl",
        contexts,
        OUT_DIR / "m4_judgments.jsonl",
    )


def cmd_analyze() -> None:
    judgments = {}
    with (OUT_DIR / "m4_judgments.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                judgments[record["taskId"]] = record["correct"]

    new_runs: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    groups: dict[str, str] = {}
    with (OUT_DIR / "m4_generations.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record["taskId"] in judgments:
                new_runs[record["sampleId"]][record["condition"]].append(
                    1 if judgments[record["taskId"]] else 0
                )
                groups[record["sampleId"]] = record["strongControlGroup"]

    master = load_master()
    rows = []
    for step_id, conditions in new_runs.items():
        entry = master[step_id]
        control_rate = as_int(entry["control_correct_count"]) / 4.0
        target_rate = as_int(entry["target_correct_count"]) / 4.0
        row = {
            "step_id": step_id,
            "group": groups[step_id],
            "c0_control_rate": control_rate,
            "c1_target_rate": target_rate,
        }
        for condition, key in (("c2_placebo", "c2_placebo_rate"), ("c3_paraphrase", "c3_paraphrase_rate")):
            outcomes = conditions.get(condition, [])
            if outcomes:
                row[key] = sum(outcomes) / len(outcomes)
                row[key.replace("_rate", "_runs")] = len(outcomes)
        if "c2_placebo_rate" in row:
            row["c1_vs_c2_target_specific"] = target_rate - row["c2_placebo_rate"]
        if "c3_paraphrase_rate" in row:
            row["c3_vs_c0_surface_form"] = row["c3_paraphrase_rate"] - control_rate
            row["c1_vs_c3_semantic_removal"] = target_rate - row["c3_paraphrase_rate"]
        row["c1_vs_c0_raw"] = target_rate - control_rate
        rows.append(row)
    write_csv(OUT_DIR / "m4_step_effects.csv", rows)

    def boot(values: list[float]) -> tuple[float, float]:
        rng = random.Random(SEED)
        draws = [
            sum(values[rng.randrange(len(values))] for _ in values) / len(values)
            for _ in range(5000)
        ]
        return percentile_interval(draws)

    summary = []
    contrasts = [
        "c1_vs_c0_raw",
        "c1_vs_c2_target_specific",
        "c3_vs_c0_surface_form",
        "c1_vs_c3_semantic_removal",
    ]
    for group in ("negative_anchor", "stable_correct", "neutral_comparison", "ALL"):
        subset = [r for r in rows if group == "ALL" or r["group"] == group]
        for contrast in contrasts:
            values = [r[contrast] for r in subset if contrast in r]
            if len(values) < 10:
                continue
            low, high = boot(values)
            summary.append(
                {
                    "group": group,
                    "contrast": contrast,
                    "steps": len(values),
                    "estimate_pp": fmt(100 * sum(values) / len(values), 2),
                    "ci_lower_pp": fmt(100 * low, 2),
                    "ci_upper_pp": fmt(100 * high, 2),
                }
            )
    write_csv(OUT_DIR / "m4_condition_contrasts.csv", summary)
    for row in summary:
        print(row)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "paraphrase"
    {
        "paraphrase": cmd_paraphrase,
        "generate": cmd_generate,
        "judge": cmd_judge,
        "analyze": cmd_analyze,
    }[command]()
