#!/usr/bin/env python3
"""Workstream M7 extension: actual-PRM policies and rollback simulation.

Adds to the baseline risk-coverage analysis:
  1. deletion policies ranked by actual PRM scores (discriminative
     Qwen2.5-Math-PRM-7B and the LLM-judge PRMs from M1), delete lowest
     score first, plus a two-PRM disagreement-abstention variant;
  2. an honest offline rollback simulation: run 1 of the target condition
     serves as a validation probe (cost: one extra generation per
     candidate); deletion is accepted only if the probe run is correct,
     and evaluated on runs 2-4 against control runs 2-4.

Stdlib only; reuses the frozen master tables and M1 score files.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from analysis_common import ROOT, as_float, as_int, fmt, read_csv, stable_hash, write_csv

OUT_DIR = ROOT / "workstream_M7_policy_risk_coverage"
M1_DIR = ROOT / "workstream_M1_actual_prm_audit"
RUNS = 4
HARM_BUDGETS = [0.01, 0.03, 0.05]


def load_steps() -> list[dict]:
    steps = []
    for row in read_csv(ROOT / "data" / "master_step_table.csv"):
        steps.append(
            {
                "step_id": row["step_id"],
                "rating": as_int(row["prm_rating"]),
                "type_hc": row["step_type_human_calibrated"].strip().lower(),
                "delta": as_float(row["target_effect"]),
                "c2w": as_int(row["correct_to_wrong_count"]),
                "w2c": as_int(row["wrong_to_correct_count"]),
            }
        )
    return steps


def load_prm_scores() -> dict[str, dict[str, float]]:
    columns: dict[str, dict[str, float]] = {}
    for path in sorted(M1_DIR.glob("prm_scores_*.jsonl")):
        name = path.stem.replace("prm_scores_", "")
        scores = {}
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    if record.get("target_score") is not None:
                        scores[record["step_id"]] = float(record["target_score"])
        if len(scores) >= 500:
            columns[name] = scores
    return columns


def policy_metrics(selected: list[dict], total: int) -> dict:
    k = len(selected)
    deleted_runs = k * RUNS
    return {
        "n_steps": k,
        "coverage": fmt(k / total, 4),
        "net_accuracy_change_pp": fmt(100 * sum(s["delta"] for s in selected) / total, 3),
        "run_danger_rate": fmt(sum(s["c2w"] for s in selected) / deleted_runs, 4) if k else "",
        "run_benefit_rate": fmt(sum(s["w2c"] for s in selected) / deleted_runs, 4) if k else "",
    }


def prm_policies() -> None:
    steps = load_steps()
    total = len(steps)
    columns = load_prm_scores()
    rows = []
    for name, scores in columns.items():
        covered = [s for s in steps if s["step_id"] in scores]
        order = sorted(
            covered, key=lambda s: (scores[s["step_id"]], stable_hash(s["step_id"]))
        )
        for k in list(range(20, len(order) + 1, 20)):
            selected = order[:k]
            deleted_runs = k * RUNS
            danger = sum(s["c2w"] for s in selected) / deleted_runs
            rows.append(
                {
                    "policy": f"prm_threshold:{name}",
                    **policy_metrics(selected, total),
                    "_danger": danger,
                }
            )
    if len(columns) >= 2:
        # Pinned to the ensemble the paper reports (frozen before the extra
        # trained PRMs were added); analyze_prm_scores.py covers the full set.
        pinned = ("google_gemini_2_5_flash", "microsoft_phi_4")
        names = [n for n in pinned if n in columns] or sorted(columns)[:2]
        shared = [
            s
            for s in steps
            if all(s["step_id"] in columns[n] for n in names)
        ]
        def mean_score(s):
            return sum(columns[n][s["step_id"]] for n in names) / len(names)
        def disagreement(s):
            values = [columns[n][s["step_id"]] for n in names]
            return max(values) - min(values)
        agreeing = [s for s in shared if disagreement(s) <= 0.3]
        order = sorted(agreeing, key=lambda s: (mean_score(s), stable_hash(s["step_id"])))
        for k in list(range(20, len(order) + 1, 20)):
            selected = order[:k]
            danger = sum(s["c2w"] for s in selected) / (k * RUNS)
            rows.append(
                {
                    "policy": "prm_ensemble_low_score_abstain_on_disagreement",
                    **policy_metrics(selected, total),
                    "_danger": danger,
                }
            )
    budget_rows = []
    by_policy: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_policy[row["policy"]].append(row)
    for policy, policy_rows in by_policy.items():
        for budget in HARM_BUDGETS:
            feasible = [r for r in policy_rows if r["_danger"] <= budget + 1e-12]
            best = max(feasible, key=lambda r: r["n_steps"], default=None)
            budget_rows.append(
                {
                    "policy": policy,
                    "harm_budget": budget,
                    "max_steps_deletable": best["n_steps"] if best else 0,
                    "net_accuracy_change_pp": best["net_accuracy_change_pp"] if best else "",
                    "run_danger_rate": best["run_danger_rate"] if best else "",
                }
            )
    for row in rows:
        row.pop("_danger", None)
    write_csv(OUT_DIR / "policy_actual_prm_curves.csv", rows)
    write_csv(OUT_DIR / "policy_actual_prm_harm_budget.csv", budget_rows)
    for row in budget_rows:
        print(row)


def rollback_simulation() -> None:
    """Probe-and-rollback: target run 1 validates; evaluate on runs 2-4."""
    runs_by_step: dict[str, dict[str, dict[int, int]]] = defaultdict(lambda: defaultdict(dict))
    for row in read_csv(ROOT / "data" / "master_run_table.csv"):
        if row["condition"] not in ("control", "target_delete"):
            continue
        run_id = as_int(row["run_id"])
        runs_by_step[row["step_id"]][row["condition"]][run_id] = (
            1 if row["judge_label"].strip() == "1" else 0
        )
    steps = {s["step_id"]: s for s in load_steps()}
    candidate_sets = {
        "rating_neg1": [sid for sid, s in steps.items() if s["rating"] == -1],
        "neg1_x_harmful": [
            sid
            for sid, s in steps.items()
            if s["rating"] == -1 and s["type_hc"] == "harmful"
        ],
        "all_steps": list(steps),
    }
    rows = []
    for name, candidates in candidate_sets.items():
        naive_delta = []
        rollback_delta = []
        accepted = 0
        for sid in candidates:
            conditions = runs_by_step.get(sid, {})
            control = conditions.get("control", {})
            target = conditions.get("target_delete", {})
            eval_runs = [r for r in (2, 3, 4) if r in control and r in target]
            if 1 not in target or not eval_runs:
                continue
            control_rate = sum(control[r] for r in eval_runs) / len(eval_runs)
            target_rate = sum(target[r] for r in eval_runs) / len(eval_runs)
            naive_delta.append(target_rate - control_rate)
            if target[1] == 1:
                accepted += 1
                rollback_delta.append(target_rate - control_rate)
            else:
                rollback_delta.append(0.0)
        n = len(naive_delta)
        harm_naive = sum(1 for d in naive_delta if d < 0) / n
        harm_rollback = sum(1 for d in rollback_delta if d < 0) / n
        rows.append(
            {
                "candidate_set": name,
                "candidates": n,
                "accept_rate": fmt(accepted / n, 3),
                "naive_mean_delta_pp": fmt(100 * sum(naive_delta) / n, 2),
                "rollback_mean_delta_pp": fmt(100 * sum(rollback_delta) / n, 2),
                "naive_harmed_step_share": fmt(harm_naive, 3),
                "rollback_harmed_step_share": fmt(harm_rollback, 3),
                "extra_generations_per_candidate": 1,
            }
        )
        print(rows[-1])
    write_csv(OUT_DIR / "policy_rollback_simulation.csv", rows)


if __name__ == "__main__":
    prm_policies()
    rollback_simulation()
