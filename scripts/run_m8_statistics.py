#!/usr/bin/env python3
"""Workstream M8: pre-registered statistics upgrades.

Part 1 — simulation-based power analysis for the M2/M6 designs (plan 12.5):
using the frozen 600-step outcome distribution as the data-generating
process, simulate N-step / R-run replications and measure the power to
detect target and pure-semantic effects of the observed and smaller sizes.

Part 2 — run-level logistic model with problem-cluster-robust (sandwich)
standard errors: logit P(correct) on deletion, rating, type and the
anchor interaction. This is a GEE-style marginal model (not a random-effects
fit) and is labeled as such. Stdlib only.
"""

from __future__ import annotations

import json
import math
import random

from analysis_common import (
    ROOT,
    SEED,
    as_float,
    as_int,
    fit_logistic_irls,
    fmt,
    read_csv,
    sigmoid,
    write_csv,
)

OUT_DIR = ROOT / "workstream_M8_statistics"
SIMULATIONS = 400


def load_steps() -> list[dict]:
    steps = []
    for row in read_csv(ROOT / "data" / "master_step_table.csv"):
        steps.append(
            {
                "step_id": row["step_id"],
                "problem_id": row["problem_id"],
                "rating": as_int(row["prm_rating"]),
                "type_hc": row["step_type_human_calibrated"].strip().lower(),
                "p_control": as_int(row["control_correct_count"]) / 4.0,
                "p_target": as_int(row["target_correct_count"]) / 4.0,
                "p_placebo": as_float(row["placebo_avg_correct"]),
                "eligible": row["placebo_eligible"].strip() == "1",
                "anchor": row["prm_rating"] == "-1"
                and row["step_type_human_calibrated"].strip().lower() == "harmful",
            }
        )
    return steps


def simulate_power(
    steps: list[dict],
    n_steps: int,
    runs: int,
    estimand: str,
    effect_scale: float,
    anchor_only: bool,
    rng: random.Random,
) -> float:
    """Fraction of simulations whose 95% normal CI excludes zero."""
    pool = [s for s in steps if (s["anchor"] if anchor_only else True)]
    if estimand == "semantic":
        pool = [s for s in pool if s["eligible"] and not math.isnan(s["p_placebo"])]
    hits = 0
    for _ in range(SIMULATIONS):
        sample = [pool[rng.randrange(len(pool))] for _ in range(n_steps)]
        effects = []
        for s in sample:
            base = s["p_control"]
            if estimand == "target":
                shifted = base + (s["p_target"] - base) * effect_scale
            else:
                shifted = s["p_placebo"] + (s["p_target"] - s["p_placebo"]) * effect_scale
            shifted = min(1.0, max(0.0, shifted))
            reference = base if estimand == "target" else min(1.0, max(0.0, s["p_placebo"]))
            draw_new = sum(rng.random() < shifted for _ in range(runs)) / runs
            draw_ref = sum(rng.random() < reference for _ in range(runs)) / runs
            effects.append(draw_new - draw_ref)
        mean = sum(effects) / len(effects)
        variance = sum((e - mean) ** 2 for e in effects) / (len(effects) - 1)
        se = math.sqrt(variance / len(effects))
        if se > 0 and abs(mean) / se >= 1.96:
            hits += 1
    return hits / SIMULATIONS


def cmd_power() -> list[dict]:
    steps = load_steps()
    rng = random.Random(SEED)
    rows = []
    designs = [
        ("M2 overall target, 300 steps x 3 runs", 300, 3, "target", False),
        ("M2 anchor semantic, 100 anchors x 3 runs", 100, 3, "semantic", True),
        ("M6 overall target, 300 steps x 3 runs", 300, 3, "target", False),
        ("M2 anchor semantic, 80 anchors x 3 runs", 80, 3, "semantic", True),
        ("M4 anchor contrast, 80 anchors x 4 runs", 80, 4, "semantic", True),
    ]
    for label, n, runs, estimand, anchor_only in designs:
        for scale, scale_label in ((1.0, "observed"), (0.6, "60% of observed"), (0.35, "35% of observed")):
            power = simulate_power(steps, n, runs, estimand, scale, anchor_only, rng)
            rows.append(
                {
                    "design": label,
                    "estimand": estimand,
                    "effect_size": scale_label,
                    "power": fmt(power, 3),
                }
            )
            print(rows[-1])
    write_csv(OUT_DIR / "m8_power_analysis.csv", rows)
    return rows


def load_runs() -> list[dict]:
    runs = []
    step_meta = {s["step_id"]: s for s in load_steps()}
    for row in read_csv(ROOT / "data" / "master_run_table.csv"):
        if row["condition"] not in ("control", "target_delete"):
            continue
        meta = step_meta.get(row["step_id"])
        if meta is None:
            continue
        runs.append(
            {
                "problem_id": meta["problem_id"],
                "correct": 1 if row["judge_label"].strip() == "1" else 0,
                "deleted": 1 if row["condition"] == "target_delete" else 0,
                "rating_neg1": 1 if meta["rating"] == -1 else 0,
                "rating_pos1": 1 if meta["rating"] == 1 else 0,
                "harmful": 1 if meta["type_hc"] == "harmful" else 0,
                "essential": 1 if meta["type_hc"] == "essential" else 0,
                "anchor_x_delete": 1 if (meta["anchor"] and row["condition"] == "target_delete") else 0,
            }
        )
    return runs


def cmd_model() -> None:
    runs = load_runs()
    if not runs:
        print("run table columns not as expected; inspect master_run_table.csv")
        return
    features = [
        "deleted",
        "rating_neg1",
        "rating_pos1",
        "harmful",
        "essential",
        "anchor_x_delete",
    ]
    x_rows = [[float(r[f]) for f in features] for r in runs]
    outcomes = [r["correct"] for r in runs]
    coefficients = fit_logistic_irls(x_rows, outcomes, l2=1e-4)

    # Problem-cluster-robust sandwich covariance.
    width = len(coefficients)
    design = [[1.0, *row] for row in x_rows]
    bread = [[0.0] * width for _ in range(width)]
    cluster_scores: dict[str, list[float]] = {}
    for row, outcome, run in zip(design, outcomes, runs):
        probability = sigmoid(sum(c * v for c, v in zip(coefficients, row)))
        weight = max(probability * (1 - probability), 1e-8)
        residual = outcome - probability
        score = cluster_scores.setdefault(run["problem_id"], [0.0] * width)
        for i in range(width):
            score[i] += row[i] * residual
            for j in range(width):
                bread[i][j] += row[i] * row[j] * weight
    from analysis_common import solve_linear_system

    identity = [[1.0 if i == j else 0.0 for j in range(width)] for i in range(width)]
    bread_inv = [solve_linear_system(bread, col) for col in map(list, zip(*identity))]
    meat = [[0.0] * width for _ in range(width)]
    for score in cluster_scores.values():
        for i in range(width):
            for j in range(width):
                meat[i][j] += score[i] * score[j]
    # sandwich = B^-1 M B^-1  (B symmetric)
    tmp = [
        [sum(bread_inv[i][k] * meat[k][j] for k in range(width)) for j in range(width)]
        for i in range(width)
    ]
    cov = [
        [sum(tmp[i][k] * bread_inv[k][j] for k in range(width)) for j in range(width)]
        for i in range(width)
    ]
    names = ["intercept", *features]
    rows = []
    for index, name in enumerate(names):
        estimate = coefficients[index]
        se = math.sqrt(max(cov[index][index], 0.0))
        rows.append(
            {
                "term": name,
                "log_odds": fmt(estimate, 4),
                "cluster_robust_se": fmt(se, 4),
                "z": fmt(estimate / se if se else float("nan"), 2),
                "odds_ratio": fmt(math.exp(estimate), 3),
                "ci_lower_or": fmt(math.exp(estimate - 1.96 * se), 3),
                "ci_upper_or": fmt(math.exp(estimate + 1.96 * se), 3),
            }
        )
        print(rows[-1])
    write_csv(OUT_DIR / "m8_cluster_robust_logistic.csv", rows)
    (OUT_DIR / "m8_model_notes.md").write_text(
        "# M8 统计模型说明\n\n"
        "- `m8_cluster_robust_logistic.csv`:run-level marginal logistic model"
        "(GEE 风格,problem 聚类 sandwich SE;非随机效应拟合,作为 cluster bootstrap 的一致性检查);\n"
        f"- 样本:{len(runs)} 次 control/target runs,{len(cluster_scores)} 个 problem clusters;\n"
        "- `m8_power_analysis.csv`:以冻结 600-step 结果为 DGP 的模拟检验力"
        f"({SIMULATIONS} 次模拟/格,seed {SEED});\n"
        "- 后续 M2/M6 判分完成后,在合并数据上加 generator/dataset 交互项。\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    OUT_DIR.mkdir(exist_ok=True)
    cmd_power()
    cmd_model()
