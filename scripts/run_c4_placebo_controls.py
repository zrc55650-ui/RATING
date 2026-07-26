#!/usr/bin/env python3
"""C4: placebo own-controls for the difference-in-differences placebo fix.

Review issue: the frozen placebo contrast compares generation from prefix
1:p-1 against the *target's* control (prefix 1:t), so it confounds removing
step p with the different cutoff position. The proper matched contrast needs
the placebo cutoff's own control C_p (prefix 1:p, step p kept):

    DiD semantic effect = (Y_{t-1} - Y_t) - (Y_{p-1} - Y_p)

This script generates C_p runs mirroring every frozen placebo run 1:1
(primary cohort: 1,514 runs at the exact placebo_step_index of each frozen
placebo run; M2/phi-4 cohort: 891) and computes the DiD contrasts.

Subcommands:
    export-primary    build C_p tasks from data/master_run_table.csv
    generate-primary  generate via OpenRouter qwen3-8b (/no_think, frozen protocol)
    judge-primary     judge with the frozen qwen3-8b judge
    analyze-primary   DiD vs legacy contrast, by group, cluster bootstrap
    export-m2cp / generate-m2cp / judge-m2cp   same for the phi-4 cohort
"""

from __future__ import annotations

import json
import math
import random as rnd
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis_common import ROOT, SEED, as_int, fmt, percentile_interval, read_csv, write_csv  # noqa: E402
from openrouter_workers import (  # noqa: E402
    judge_generations,
    load_contexts,
    run_generation_tasks,
)

OUT_DIR = ROOT / "workstream_M12_placebo_did"
M2_DIR = ROOT / "workstream_M2_cross_generator"
PRIMARY_MODEL = "qwen/qwen3-8b"
M2_MODEL = "microsoft/phi-4"


def sid_col(rows: list[dict]) -> str:
    return next(c for c in rows[0] if c.endswith("step_id"))


def cmd_export_primary() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    runs = read_csv(ROOT / "data" / "master_run_table.csv")
    sid = sid_col(runs)
    tasks = []
    for row in runs:
        if row["condition"] != "placebo_delete":
            continue
        p = as_int(row["placebo_step_index"])
        tasks.append(
            {
                "taskId": f"{row[sid]}|c4placebo{row['placebo_order']}|step{p}",
                "sampleId": row[sid],
                "condition": "placebo_control",
                "prefixLast": p,
                "placeboStepIndex": p,
                "placeboOrder": as_int(row["placebo_order"]),
                "rating": as_int(row["prm_rating"]),
                "stepTypeAnalysis": row["step_type_analysis"].strip().lower(),
                "stepTypeHC": row["step_type_human_calibrated"].strip().lower(),
                "groundTruthAnswer": row["ground_truth_answer"],
            }
        )
    with (OUT_DIR / "c4_primary_tasks.jsonl").open("w", encoding="utf-8") as sink:
        for task in tasks:
            sink.write(json.dumps(task, ensure_ascii=False) + "\n")
    print(f"exported {len(tasks)} primary C_p tasks")


def cmd_generate_primary() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    tasks = [
        json.loads(line)
        for line in (OUT_DIR / "c4_primary_tasks.jsonl").open(encoding="utf-8")
        if line.strip()
    ]
    run_generation_tasks(
        tasks,
        contexts,
        OUT_DIR / "c4_primary_generations.jsonl",
        model=PRIMARY_MODEL,
        workers=12,
        max_tokens=4096,
        no_think=True,
        json_mode=True,
    )


def cmd_judge_primary() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    judge_generations(
        OUT_DIR / "c4_primary_generations.jsonl",
        contexts,
        OUT_DIR / "c4_primary_judgments.jsonl",
    )


def cmd_export_m2cp() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    tasks = []
    for line in (M2_DIR / "m2_generation_tasks.jsonl").open(encoding="utf-8"):
        if not line.strip():
            continue
        task = json.loads(line)
        if task["condition"] != "placebo_delete":
            continue
        p = as_int(task["placeboStepIndex"])
        record = dict(task)
        record["taskId"] = task["taskId"].replace("|m2run", "|m2cp") + f"|step{p}"
        record["condition"] = "placebo_control"
        record["prefixLast"] = p
        tasks.append(record)
    with (OUT_DIR / "c4_m2_tasks.jsonl").open("w", encoding="utf-8") as sink:
        for task in tasks:
            sink.write(json.dumps(task, ensure_ascii=False) + "\n")
    print(f"exported {len(tasks)} M2 C_p tasks")


def cmd_generate_m2cp() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    tasks = [
        json.loads(line)
        for line in (OUT_DIR / "c4_m2_tasks.jsonl").open(encoding="utf-8")
        if line.strip()
    ]
    run_generation_tasks(
        tasks,
        contexts,
        OUT_DIR / "c4_m2_generations.jsonl",
        model=M2_MODEL,
        workers=12,
        max_tokens=4096,
        no_think=False,
        json_mode=True,
    )


def cmd_judge_m2cp() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    judge_generations(
        OUT_DIR / "c4_m2_generations.jsonl",
        contexts,
        OUT_DIR / "c4_m2_judgments.jsonl",
    )


def cmd_export_m6cp() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    m6_dir = ROOT / "workstream_M6_processbench"
    tasks = []
    for line in (m6_dir / "m6_generation_tasks.jsonl").open(encoding="utf-8"):
        if not line.strip():
            continue
        task = json.loads(line)
        if task["condition"] != "placebo_delete":
            continue
        p = as_int(task["placeboStepIndex"])
        record = dict(task)
        record["taskId"] = task["taskId"].replace("|m6run", "|m6cp") + f"|step{p}"
        record["condition"] = "placebo_control"
        record["prefixLast"] = p
        tasks.append(record)
    with (OUT_DIR / "c4_m6_tasks.jsonl").open("w", encoding="utf-8") as sink:
        for task in tasks:
            sink.write(json.dumps(task, ensure_ascii=False) + "\n")
    print(f"exported {len(tasks)} M6 C_p tasks")


def cmd_generate_m6cp() -> None:
    from run_m6_pipeline import load_m6_contexts

    tasks = [
        json.loads(line)
        for line in (OUT_DIR / "c4_m6_tasks.jsonl").open(encoding="utf-8")
        if line.strip()
    ]
    run_generation_tasks(
        tasks,
        load_m6_contexts(),
        OUT_DIR / "c4_m6_generations.jsonl",
        model=PRIMARY_MODEL,
        workers=12,
        max_tokens=2048,
        no_think=True,
        json_mode=True,
    )


def cmd_judge_m6cp() -> None:
    from run_m6_pipeline import load_m6_contexts

    judge_generations(
        OUT_DIR / "c4_m6_generations.jsonl",
        load_m6_contexts(),
        OUT_DIR / "c4_m6_judgments.jsonl",
    )


def _did_from_taskfiles(
    gen_path: Path,
    judge_path: Path,
    cp_gen: Path,
    cp_judge: Path,
    group_of,
    out_prefix: str,
) -> None:
    """Generic DiD for M2/M6-style cohorts (tasks carry conditions + p)."""
    verdicts = {}
    with judge_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                verdicts[record["taskId"]] = 1 if record["correct"] else 0
    control: dict[str, list[int]] = defaultdict(list)
    target: dict[str, list[int]] = defaultdict(list)
    plc: dict[tuple[str, int], list[int]] = defaultdict(list)
    meta: dict[str, dict] = {}
    with gen_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record["taskId"] not in verdicts:
                continue
            y = verdicts[record["taskId"]]
            sid = record["sampleId"]
            meta[sid] = record
            if record["condition"] == "control":
                control[sid].append(y)
            elif record["condition"] == "target_delete":
                target[sid].append(y)
            elif record["condition"] == "placebo_delete":
                plc[(sid, as_int(record["placeboStepIndex"]))].append(y)
    cp = load_judged_cp(cp_gen, cp_judge)
    rows = []
    for sid in control:
        if sid not in target:
            continue
        pairs = [
            (plc[(s, p)], cp[(s, p)])
            for (s, p) in plc
            if s == sid and cp.get((s, p))
        ]
        tgt = sum(target[sid]) / len(target[sid]) - sum(control[sid]) / len(control[sid])
        row = {"step_id": sid, "group": group_of(meta[sid]), "target_effect": tgt}
        if pairs:
            own = [sum(a) / len(a) - sum(b) / len(b) for a, b in pairs]
            legacy = [
                sum(a) / len(a) - sum(control[sid]) / len(control[sid]) for a, _ in pairs
            ]
            row["placebo_own_effect"] = sum(own) / len(own)
            row["placebo_legacy_effect"] = sum(legacy) / len(legacy)
            row["did_semantic_effect"] = tgt - row["placebo_own_effect"]
            row["legacy_semantic_effect"] = tgt - row["placebo_legacy_effect"]
        rows.append(row)
    write_csv(OUT_DIR / f"{out_prefix}_step_effects.csv", rows)

    def boot(values: list[float]) -> tuple[float, float]:
        rng = rnd.Random(SEED)
        draws = [
            sum(values[rng.randrange(len(values))] for _ in values) / len(values)
            for _ in range(5000)
        ]
        return percentile_interval(draws)

    matched = [r for r in rows if "did_semantic_effect" in r]
    groups: dict[str, list[dict]] = {"overall": matched}
    for row in matched:
        groups.setdefault(row["group"], []).append(row)
        if "|" in row["group"]:
            for part in row["group"].split("|"):
                groups.setdefault(part, []).append(row)
    summary = []
    for name, subset in groups.items():
        if len(subset) < 10:
            continue
        for key in (
            "target_effect",
            "placebo_own_effect",
            "placebo_legacy_effect",
            "did_semantic_effect",
            "legacy_semantic_effect",
        ):
            values = [r[key] for r in subset]
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
            print(summary[-1])
    write_csv(OUT_DIR / f"{out_prefix}_did_summary.csv", summary)


def cmd_analyze_m2() -> None:
    _did_from_taskfiles(
        M2_DIR / "m2_generations.jsonl",
        M2_DIR / "m2_judgments.jsonl",
        OUT_DIR / "c4_m2_generations.jsonl",
        OUT_DIR / "c4_m2_judgments.jsonl",
        lambda record: record.get("m2Cell", ""),
        "c4_m2",
    )


def cmd_judge_m10cp() -> None:
    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    judge_generations(
        ROOT / "workstream_M10_longcot_replication" / "m10cp_generations.jsonl",
        contexts,
        OUT_DIR / "c4_m10_judgments_cp.jsonl",
    )


def cmd_analyze_m10() -> None:
    m10_dir = ROOT / "workstream_M10_longcot_replication"
    _did_from_taskfiles(
        m10_dir / "m10_generations.jsonl",
        m10_dir / "m10_judgments.jsonl",
        m10_dir / "m10cp_generations.jsonl",
        OUT_DIR / "c4_m10_judgments_cp.jsonl",
        lambda record: record.get("m2Cell", ""),
        "c4_m10",
    )


def cmd_analyze_m6() -> None:
    def group_of(record: dict) -> str:
        cls = record.get("stepClass", "")
        parts = [cls]
        if cls.startswith("locally_correct_"):
            parts.append("locally_correct_all")
        elif cls == "locally_correct":
            parts.append("locally_correct_all")
        parts.append(record.get("subset", ""))
        return "|".join(p for p in parts if p)

    _did_from_taskfiles(
        ROOT / "workstream_M6_processbench" / "m6_generations.jsonl",
        ROOT / "workstream_M6_processbench" / "m6_judgments.jsonl",
        OUT_DIR / "c4_m6_generations.jsonl",
        OUT_DIR / "c4_m6_judgments.jsonl",
        group_of,
        "c4_m6",
    )


def cmd_analyze_m4() -> None:
    """Recompute the M4 placebo contrast with own controls (C_p reuse)."""
    manifest = {
        row["step_id"]: row["strong_control_group"]
        for row in read_csv(
            ROOT / "workstream_M4_strong_controls" / "strong_control_sampling_manifest.csv"
        )
    }
    verdicts = {}
    with (ROOT / "workstream_M4_strong_controls" / "m4_judgments.jsonl").open(
        encoding="utf-8"
    ) as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                verdicts[record["taskId"]] = 1 if record["correct"] else 0
    c2: dict[tuple[str, int], list[int]] = defaultdict(list)
    with (ROOT / "workstream_M4_strong_controls" / "m4_generations.jsonl").open(
        encoding="utf-8"
    ) as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("condition") != "c2_placebo":
                continue
            if record["taskId"] not in verdicts:
                continue
            c2[(record["sampleId"], as_int(record["placeboStepIndex"]))].append(
                verdicts[record["taskId"]]
            )
    cp = load_judged_cp(
        OUT_DIR / "c4_primary_generations.jsonl", OUT_DIR / "c4_primary_judgments.jsonl"
    )
    by_step: dict[str, list[float]] = defaultdict(list)
    for (sid, p), outcomes in c2.items():
        if (sid, p) in cp and cp[(sid, p)]:
            own = sum(outcomes) / len(outcomes) - sum(cp[(sid, p)]) / len(cp[(sid, p)])
            by_step[sid].append(own)
    rows = [
        {
            "step_id": sid,
            "group": manifest.get(sid, "?"),
            "c2_own_effect": sum(vals) / len(vals),
        }
        for sid, vals in by_step.items()
    ]
    write_csv(OUT_DIR / "c4_m4_c2_own_effects.csv", rows)

    def boot(values: list[float]) -> tuple[float, float]:
        rng = rnd.Random(SEED)
        draws = [
            sum(values[rng.randrange(len(values))] for _ in values) / len(values)
            for _ in range(5000)
        ]
        return percentile_interval(draws)

    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(row["c2_own_effect"])
        groups["overall"].append(row["c2_own_effect"])
    summary = []
    for name, values in groups.items():
        low, high = boot(values)
        summary.append(
            {
                "group": name,
                "steps": len(values),
                "c2_own_effect_pp": fmt(100 * sum(values) / len(values), 2),
                "ci_lower_pp": fmt(100 * low, 2),
                "ci_upper_pp": fmt(100 * high, 2),
            }
        )
        print(summary[-1])
    write_csv(OUT_DIR / "c4_m4_c2_own_summary.csv", summary)


def cmd_export_m10cp() -> None:
    """Self-contained R1 placebo-control prompts for the server executor."""
    from openrouter_workers import GENERATION_SYSTEM_PROMPT, build_visible_prefix

    contexts = load_contexts(ROOT / "data" / "step_trajectory_context.jsonl")
    out_path = ROOT / "workstream_M10_longcot_replication" / "m10cp_prompt_tasks.jsonl"
    n = 0
    with out_path.open("w", encoding="utf-8") as sink:
        for line in (OUT_DIR / "c4_m2_tasks.jsonl").open(encoding="utf-8"):
            if not line.strip():
                continue
            task = json.loads(line)
            sample = contexts[task["sampleId"]]
            prefix = build_visible_prefix(sample["steps"], as_int(task["prefixLast"]), None)
            record = dict(task)
            record["taskId"] = task["taskId"].replace("|m2cp", "|m10cp")
            record["system"] = GENERATION_SYSTEM_PROMPT
            record["user"] = (
                f"MATHEMATICS PROBLEM:\n{sample['problem']}\n\n"
                f"VISIBLE SOLUTION PREFIX:\n{prefix}"
            )
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            n += 1
    print(f"exported {n} R1 C_p prompt tasks -> {out_path}")


def load_judged_cp(gen_path: Path, judge_path: Path) -> dict[tuple[str, int], list[int]]:
    """(step_id, placebo_index) -> list of 0/1 outcomes for C_p runs."""
    verdicts = {}
    with judge_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                verdicts[record["taskId"]] = 1 if record["correct"] else 0
    outcomes: dict[tuple[str, int], list[int]] = defaultdict(list)
    with gen_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record["taskId"] not in verdicts:
                continue
            key = (record["sampleId"], as_int(record["placeboStepIndex"]))
            outcomes[key].append(verdicts[record["taskId"]])
    return outcomes


def cmd_analyze_primary() -> None:
    runs = read_csv(ROOT / "data" / "master_run_table.csv")
    sid = sid_col(runs)
    control: dict[str, list[int]] = defaultdict(list)
    target: dict[str, list[int]] = defaultdict(list)
    plc_del: dict[tuple[str, int], list[int]] = defaultdict(list)
    meta: dict[str, dict] = {}
    for row in runs:
        y = 1 if row["judge_label"].strip() == "1" else 0
        key = row[sid]
        if row["condition"] == "control":
            control[key].append(y)
        elif row["condition"] == "target_delete":
            target[key].append(y)
        elif row["condition"] == "placebo_delete":
            plc_del[(key, as_int(row["placebo_step_index"]))].append(y)
        meta.setdefault(
            key,
            {
                "problem_id": row["problem_id"],
                "rating": as_int(row["prm_rating"]),
                "type_analysis": row["step_type_analysis"].strip().lower(),
                "type_hc": row["step_type_human_calibrated"].strip().lower(),
            },
        )
    cp = load_judged_cp(
        OUT_DIR / "c4_primary_generations.jsonl", OUT_DIR / "c4_primary_judgments.jsonl"
    )

    rows = []
    for step_id in control:
        if step_id not in target:
            continue
        pairs = [
            (p, plc_del[(s, p)], cp[(s, p)])
            for (s, p) in plc_del
            if s == step_id and (s, p) in cp and cp[(s, p)]
        ]
        tgt_effect = sum(target[step_id]) / len(target[step_id]) - sum(
            control[step_id]
        ) / len(control[step_id])
        row = {
            "step_id": step_id,
            **meta[step_id],
            "target_effect": tgt_effect,
            "n_placebo_pairs": len(pairs),
        }
        if pairs:
            own = [
                sum(pd) / len(pd) - sum(cpv) / len(cpv) for _, pd, cpv in pairs
            ]
            legacy = [
                sum(pd) / len(pd) - sum(control[step_id]) / len(control[step_id])
                for _, pd, _ in pairs
            ]
            row["placebo_own_effect"] = sum(own) / len(own)
            row["placebo_legacy_effect"] = sum(legacy) / len(legacy)
            row["did_semantic_effect"] = tgt_effect - row["placebo_own_effect"]
            row["legacy_semantic_effect"] = tgt_effect - row["placebo_legacy_effect"]
        rows.append(row)
    write_csv(OUT_DIR / "c4_primary_step_effects.csv", rows)

    def boot(values: list[float], clusters: list[str]) -> tuple[float, float]:
        by_cluster: dict[str, list[float]] = defaultdict(list)
        for value, cluster in zip(values, clusters):
            by_cluster[cluster].append(value)
        keys = sorted(by_cluster)
        rng = rnd.Random(SEED)
        draws = []
        for _ in range(5000):
            sample: list[float] = []
            for _ in keys:
                sample.extend(by_cluster[keys[rng.randrange(len(keys))]])
            draws.append(sum(sample) / len(sample))
        return percentile_interval(draws)

    matched = [r for r in rows if "did_semantic_effect" in r]
    groups = {
        "overall": matched,
        "anchor_rating-1xHarmful": [
            r for r in matched if r["rating"] == -1 and r["type_analysis"] == "harmful"
        ],
        "rating=-1": [r for r in matched if r["rating"] == -1],
        "rating=0": [r for r in matched if r["rating"] == 0],
        "rating=1": [r for r in matched if r["rating"] == 1],
        "harmful": [r for r in matched if r["type_analysis"] == "harmful"],
    }
    summary = []
    for name, subset in groups.items():
        if len(subset) < 10:
            continue
        for key in (
            "target_effect",
            "placebo_own_effect",
            "placebo_legacy_effect",
            "did_semantic_effect",
            "legacy_semantic_effect",
        ):
            values = [r[key] for r in subset if not math.isnan(r[key])]
            low, high = boot(values, [r["step_id"] for r in subset])
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
    write_csv(OUT_DIR / "c4_primary_did_summary.csv", summary)
    for row in summary:
        print(row)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "export-primary"
    {
        "export-primary": cmd_export_primary,
        "generate-primary": cmd_generate_primary,
        "judge-primary": cmd_judge_primary,
        "analyze-primary": cmd_analyze_primary,
        "export-m2cp": cmd_export_m2cp,
        "generate-m2cp": cmd_generate_m2cp,
        "judge-m2cp": cmd_judge_m2cp,
        "export-m10cp": cmd_export_m10cp,
        "export-m6cp": cmd_export_m6cp,
        "generate-m6cp": cmd_generate_m6cp,
        "judge-m6cp": cmd_judge_m6cp,
        "analyze-m2": cmd_analyze_m2,
        "analyze-m4": cmd_analyze_m4,
        "analyze-m6": cmd_analyze_m6,
        "judge-m10cp": cmd_judge_m10cp,
        "analyze-m10": cmd_analyze_m10,
    }[command]()
