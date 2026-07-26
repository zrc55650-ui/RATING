#!/usr/bin/env python3
"""Causal policy evaluation: net-effect harm budgets + nested selection.

Review issue 1: the previous risk--coverage tables budgeted the run-level
transition rate p_c(1-p_t), which is not causal harm -- a null intervention
on a stochastic step (p_c = p_t = 0.5) shows 25% "harm". This script
replaces it with:

  * mean net accuracy change per deleted step, Delta_i = p_t_hat - p_c_hat,
    certified by a one-sided 95% lower confidence bound from a
    problem-cluster bootstrap (budget: LCB >= -budget);
  * step-level tail risk: share of selected steps with observed Delta_i < 0,
    reported next to an exact stochastic-disagreement floor (the same share
    expected under the null p_t = p_c, computed from Binomial(4, p_pooled)),
    and the excess over that floor.

Review issue 3: the previous calibration/test split reused out-of-fold
predictions whose training folds crossed the split. Part B nests properly:
for each of 20 outer 50/50 problem splits, predictors are trained only on
calibration problems (inner 5-fold CV for calibration-side scores, full
calibration fit for test-side scores), coverage is chosen on calibration
under the LCB rule, and the choice is evaluated once on test.

Part C reworks the probe-and-rollback simulation under the same metrics,
with a do-nothing control-split-half row as the observable noise floor.

Stdlib only; run from the repository root.
"""

from __future__ import annotations

import json
import math
import random as rnd
from collections import defaultdict
from statistics import median

from analysis_common import (
    ROOT,
    as_float,
    as_int,
    fit_logistic_irls,
    fmt,
    read_csv,
    stable_hash,
    write_csv,
)
from run_predictive_analysis import feature_vector, standardize

OUT_DIR = ROOT / "workstream_M7_policy_risk_coverage"
BUDGETS = [0.01, 0.03, 0.05]  # certified net loss per deleted step (1/3/5 pp)
N_SPLITS = 20
BOOT = 1000
SEED = 20260723
Z_95 = 1.6448536269514722


# ---------------------------------------------------------------- data


def binom_pmf(n: int, p: float) -> list[float]:
    return [math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(n + 1)]


def null_floor_prob(
    c_runs: int, t_runs: int, pooled: float, threshold: float = 0.0
) -> float:
    """Stochastic-disagreement floor under the null p_t = p_c = pooled.

    threshold == 0.0 -> P(observed delta < 0); otherwise P(delta <= threshold).
    """
    pc = binom_pmf(c_runs, pooled)
    pt = binom_pmf(t_runs, pooled)
    prob = 0.0
    for a in range(c_runs + 1):
        for b in range(t_runs + 1):
            delta = b / t_runs - a / c_runs
            hit = delta < 0 if threshold == 0.0 else delta <= threshold + 1e-12
            if hit:
                prob += pc[a] * pt[b]
    return prob


NATURAL_SHARES = {}  # rating -> natural share, filled in load_steps


def load_natural_shares() -> dict[int, float]:
    """Chosen-path phase-2 test rating distribution (deployment frame)."""
    rows = read_csv(
        ROOT
        / "workstream_F_final_statistics"
        / "robustness"
        / "sampling_frame_audit.csv"
    )
    shares = {}
    for row in rows:
        if row["frame"] == "phase2_test_chosen_path":
            shares[as_int(row["rating"])] = as_float(row["share"])
    return shares


def load_steps() -> list[dict]:
    prm_scores: dict[str, dict[str, float]] = {}
    m1_dir = ROOT / "workstream_M1_actual_prm_audit"
    for stem in (
        "prm_scores_qwen25_math_prm_7b",
        "prm_scores_math_shepherd_mistral_7b",
        "prm_scores_llama31_8b_prm_deepseek",
    ):
        path = m1_dir / f"{stem}.jsonl"
        if not path.exists():
            continue
        column: dict[str, float] = {}
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("target_score") is not None:
                    column[record["step_id"]] = float(record["target_score"])
        prm_scores[stem.replace("prm_scores_", "")] = column

    oof: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in read_csv(ROOT / "predictive_analysis" / "predictive_predictions.csv"):
        oof[row["step_id"]][f"{row['model']}|{row['task']}"].append(
            as_float(row["predicted_probability"])
        )

    steps = []
    for row in read_csv(ROOT / "data" / "master_step_table.csv"):
        sid = row["step_id"]
        pooled = (as_int(row["control_correct_count"]) + as_int(row["target_correct_count"])) / 8.0
        pred = {key: sum(vals) / len(vals) for key, vals in oof.get(sid, {}).items()}
        steps.append(
            {
                "step_id": sid,
                "problem_id": row["problem_id"],
                "rating": as_int(row["prm_rating"]),
                "type": row["step_type_analysis"].strip().lower(),
                "delta": as_float(row["target_effect"]),
                "c2w": as_int(row["correct_to_wrong_count"]),
                "floor": null_floor_prob(4, 4, pooled),
                "floor_severe": null_floor_prob(4, 4, pooled, threshold=-0.5),
                "d_score": pred.get("D|benefit", 0.36) - pred.get("D|danger", 0.151),
                "e_score": pred.get("E|benefit", 0.36) - pred.get("E|danger", 0.151),
                "prm": {name: col.get(sid) for name, col in prm_scores.items()},
                "raw": row,
            }
        )
    shares = load_natural_shares()
    counts = {r: sum(1 for s in steps if s["rating"] == r) for r in (-1, 0, 1)}
    for step in steps:
        step["nat_weight"] = shares[step["rating"]] / (counts[step["rating"]] / len(steps))
    return steps


# ---------------------------------------------------------------- metrics


def cluster_lcb(
    selected: list[dict], reps: int, seed: int, weighted: bool = False
) -> float:
    """One-sided 95% lower bound of (weighted) mean delta, resampling problems."""
    by_problem: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for step in selected:
        weight = step.get("nat_weight", 1.0) if weighted else 1.0
        by_problem[step["problem_id"]].append((step["delta"], weight))
    problems = sorted(by_problem)
    if len(problems) < 2:
        return -1.0
    rng = rnd.Random(seed)
    draws = []
    for _ in range(reps):
        num = den = 0.0
        for _ in problems:
            for value, weight in by_problem[problems[rng.randrange(len(problems))]]:
                num += value * weight
                den += weight
        draws.append(num / den if den else 0.0)
    draws.sort()
    return draws[int(0.05 * len(draws))]


def cluster_lcb_normal(selected: list[dict], weighted: bool = False) -> float:
    """Fast one-sided 95% LCB: cluster-robust SE via problem-level influence."""
    by_problem: dict[str, list[tuple[float, float]]] = defaultdict(list)
    num = den = 0.0
    for step in selected:
        weight = step.get("nat_weight", 1.0) if weighted else 1.0
        by_problem[step["problem_id"]].append((step["delta"], weight))
        num += step["delta"] * weight
        den += weight
    m = len(by_problem)
    if m < 2 or den == 0.0:
        return -1.0
    theta = num / den
    ss = 0.0
    for pairs in by_problem.values():
        g = sum(w * (d - theta) for d, w in pairs)
        ss += g * g
    se = math.sqrt(m / (m - 1) * ss) / den
    return theta - Z_95 * se


def wmean(selected: list[dict], key: str, weighted: bool) -> float:
    num = den = 0.0
    for step in selected:
        weight = step.get("nat_weight", 1.0) if weighted else 1.0
        value = step[key] if not callable(key) else key(step)
        num += value * weight
        den += weight
    return num / den if den else float("nan")


def tail_metrics(selected: list[dict], weighted: bool = False) -> dict:
    def share(pred) -> float:
        num = den = 0.0
        for step in selected:
            weight = step.get("nat_weight", 1.0) if weighted else 1.0
            num += weight * (1.0 if pred(step) else 0.0)
            den += weight
        return num / den

    def wavg(key: str) -> float:
        num = den = 0.0
        for step in selected:
            weight = step.get("nat_weight", 1.0) if weighted else 1.0
            num += weight * step[key]
            den += weight
        return num / den

    harmed = share(lambda s: s["delta"] < 0)
    severe = share(lambda s: s["delta"] <= -0.5)
    return {
        "harmed_share_obs": fmt(harmed, 3),
        "harmed_share_null_floor": fmt(wavg("floor"), 3),
        "harmed_share_excess": fmt(max(0.0, harmed - wavg("floor")), 3),
        "harmed_share_severe": fmt(severe, 3),
        "severe_null_floor": fmt(wavg("floor_severe"), 3),
        "severe_excess": fmt(max(0.0, severe - wavg("floor_severe")), 3),
    }


def rankers(steps: list[dict]) -> dict:
    ranker_map = {
        "random": lambda s: stable_hash("rnd|" + s["step_id"]),
        "rating_first": lambda s: (s["rating"], stable_hash(s["step_id"])),
        "harmful_first": lambda s: (s["type"] != "harmful", stable_hash(s["step_id"])),
        "intersection_first": lambda s: (
            not (s["rating"] == -1 and s["type"] == "harmful"),
            s["rating"],
            stable_hash(s["step_id"]),
        ),
    }
    for name in sorted(steps[0]["prm"]):
        ranker_map[f"prm:{name}"] = lambda s, _n=name: (
            s["prm"][_n] if s["prm"].get(_n) is not None else 1.0,
            stable_hash(s["step_id"]),
        )
    return ranker_map


# ---------------------------------------------------------------- part A


def part_a_insample(steps: list[dict]) -> None:
    ranker_map = dict(rankers(steps))
    ranker_map["predictor_D"] = lambda s: (-s["d_score"], stable_hash(s["step_id"]))
    ranker_map["predictor_E"] = lambda s: (-s["e_score"], stable_hash(s["step_id"]))
    ranker_map["oracle"] = lambda s: (-s["delta"], stable_hash(s["step_id"]))
    total_weight = sum(s["nat_weight"] for s in steps)
    rows = []
    for regime, weighted in (("balanced_cohort", False), ("natural_prevalence", True)):
        for name, keyfun in ranker_map.items():
            order = sorted(steps, key=keyfun)
            for budget in BUDGETS:
                best = None
                for k in range(10, len(order) + 1, 10):
                    selected = order[:k]
                    lcb = cluster_lcb_normal(selected, weighted=weighted)
                    if lcb >= -budget:
                        best = (k, selected)
                row = {
                    "regime": regime,
                    "policy": name,
                    "budget_pp": fmt(100 * budget, 0),
                    "max_steps_certified": best[0] if best else 0,
                }
                if best:
                    selected = best[1]
                    if weighted:
                        coverage = sum(s["nat_weight"] for s in selected) / total_weight
                    else:
                        coverage = best[0] / len(order)
                    boot_lcb = cluster_lcb(selected, 2000, SEED + best[0], weighted=weighted)
                    row["coverage_of_traffic"] = fmt(coverage, 4)
                    row["net_per_deletion_pp"] = fmt(
                        100 * wmean(selected, "delta", weighted), 2
                    )
                    row["net_lcb_normal_pp"] = fmt(
                        100 * cluster_lcb_normal(selected, weighted), 2
                    )
                    row["net_lcb_boot_pp"] = fmt(100 * boot_lcb, 2)
                    row.update(tail_metrics(selected, weighted))
                else:
                    row["coverage_of_traffic"] = "0"
                rows.append(row)
                print(row)
    write_csv(OUT_DIR / "policy_causal_insample.csv", rows)


# ---------------------------------------------------------------- part B


TASKS = ("danger", "benefit")


def train_and_score(
    train_rows: list[dict],
    score_steps: list[dict],
    model: str,
    step_lookup: dict[str, dict],
) -> dict[str, float]:
    """Train run-level danger/benefit logistics; return step score P(b)-P(d)."""
    scores: dict[str, dict[str, float]] = defaultdict(dict)
    names, _ = feature_vector(model, train_rows[0]["step_raw"])
    for task in TASKS:
        x_train = [feature_vector(model, r["step_raw"])[1] for r in train_rows]
        y_train = [r[f"{task}_outcome"] for r in train_rows]
        x_score = [feature_vector(model, step_lookup[s["step_id"]])[1] for s in score_steps]
        x_train_std, x_score_std = standardize(x_train, x_score, names)
        coefficients = fit_logistic_irls(x_train_std, y_train, l2=1.0)
        for step, xs in zip(score_steps, x_score_std):
            z = coefficients[0] + sum(c * v for c, v in zip(coefficients[1:], xs))
            scores[step["step_id"]][task] = 1.0 / (1.0 + math.exp(-z))
    return {
        sid: values["benefit"] - values["danger"] for sid, values in scores.items()
    }


def part_b_nested(steps: list[dict]) -> None:
    run_rows = []
    step_lookup = {s["step_id"]: s["raw"] for s in steps}
    for row in read_csv(ROOT / "predictive_analysis" / "predictive_run_level_dataset.csv"):
        sid_key = next(c for c in row if c.endswith("step_id"))
        sid = row[sid_key]
        run_rows.append(
            {
                "step_id": sid,
                "problem_id": row["problem_id"],
                "danger_outcome": as_int(row["danger_outcome"]),
                "benefit_outcome": as_int(row["benefit_outcome"]),
                "step_raw": step_lookup[sid],
            }
        )
    step_by_id = {s["step_id"]: s for s in steps}
    static = rankers(steps)
    detail_rows = []
    for split in range(N_SPLITS):
        problems = sorted({s["problem_id"] for s in steps})
        cal_problems = {
            p for p in problems if stable_hash(f"outer{split}|{p}") % 2 == 0
        }
        cal = [s for s in steps if s["problem_id"] in cal_problems]
        test = [s for s in steps if s["problem_id"] not in cal_problems]
        cal_runs = [r for r in run_rows if r["problem_id"] in cal_problems]

        policy_scores: dict[str, tuple[dict, dict]] = {}
        for model in ("D", "E"):
            inner_scores: dict[str, float] = {}
            cal_prob_list = sorted(cal_problems)
            for fold in range(5):
                fold_problems = {
                    p for p in cal_prob_list if stable_hash(f"inner{split}|{p}") % 5 == fold
                }
                train = [r for r in cal_runs if r["problem_id"] not in fold_problems]
                score = [s for s in cal if s["problem_id"] in fold_problems]
                if not train or not score:
                    continue
                inner_scores.update(train_and_score(train, score, model, step_lookup))
            test_scores = train_and_score(cal_runs, test, model, step_lookup)
            policy_scores[f"predictor_{model}"] = (inner_scores, test_scores)

        def order_by(policy: str, subset: list[dict], side: str) -> list[dict]:
            if policy in static:
                return sorted(subset, key=static[policy])
            inner, outer = policy_scores[policy]
            table = inner if side == "cal" else outer
            return sorted(
                subset,
                key=lambda s: (-table.get(s["step_id"], -1.0), stable_hash(s["step_id"])),
            )

        for regime, weighted in (("balanced_cohort", False), ("natural_prevalence", True)):
            for policy in list(static) + list(policy_scores):
                cal_order = order_by(policy, cal, "cal")
                test_order = order_by(policy, test, "test")
                for budget in BUDGETS:
                    best_k = 0
                    best_lcb = 0.0
                    for k in range(10, len(cal_order) + 1, 10):
                        lcb = cluster_lcb_normal(cal_order[:k], weighted=weighted)
                        if lcb >= -budget:
                            best_k = k
                            best_lcb = lcb
                    frac = best_k / len(cal_order) if cal_order else 0.0
                    k_test = round(frac * len(test_order))
                    row = {
                        "split": split,
                        "regime": regime,
                        "policy": policy,
                        "budget_pp": fmt(100 * budget, 0),
                        "cal_coverage": fmt(frac, 3),
                        "cal_net_lcb_pp": fmt(100 * best_lcb, 2) if best_k else "",
                        "test_steps_deleted": k_test,
                    }
                    if k_test:
                        selected = test_order[:k_test]
                        row["test_net_per_deletion_pp"] = fmt(
                            100 * wmean(selected, "delta", weighted), 2
                        )
                        row.update(
                            {
                                f"test_{k}": v
                                for k, v in tail_metrics(selected, weighted).items()
                            }
                        )
                    detail_rows.append(row)
        print(f"split {split} done")
    write_csv(OUT_DIR / "policy_causal_nested_splits.csv", detail_rows)

    summary = []
    by_key: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in detail_rows:
        by_key[(row["regime"], row["policy"], row["budget_pp"])].append(row)
    for (regime, policy, budget), rows_k in sorted(by_key.items()):
        coverages = [as_float(r["cal_coverage"]) for r in rows_k]
        nets = [
            as_float(r["test_net_per_deletion_pp"])
            for r in rows_k
            if r.get("test_net_per_deletion_pp")
        ]
        excesses = [
            as_float(r["test_harmed_share_excess"])
            for r in rows_k
            if r.get("test_harmed_share_excess")
        ]
        summary.append(
            {
                "regime": regime,
                "policy": policy,
                "budget_pp": budget,
                "splits_with_nonzero_coverage": sum(1 for c in coverages if c > 0),
                "median_cal_coverage": fmt(median(coverages), 3),
                "min_cal_coverage": fmt(min(coverages), 3),
                "max_cal_coverage": fmt(max(coverages), 3),
                "median_test_net_per_deletion_pp": fmt(median(nets), 2) if nets else "",
                "median_test_harmed_excess": fmt(median(excesses), 3) if excesses else "",
            }
        )
        print(summary[-1])
    write_csv(OUT_DIR / "policy_causal_nested_summary.csv", summary)


# ---------------------------------------------------------------- part C


def part_c_rollback(steps: list[dict]) -> None:
    runs_by_step: dict[str, dict[str, dict[int, int]]] = defaultdict(lambda: defaultdict(dict))
    for row in read_csv(ROOT / "data" / "master_run_table.csv"):
        if row["condition"] not in ("control", "target_delete"):
            continue
        sid_key = next(c for c in row if c.endswith("step_id"))
        try:
            run_id = as_int(row["run_id"])
        except ValueError:
            continue
        runs_by_step[row[sid_key]][row["condition"]][run_id] = (
            1 if row["judge_label"].strip() == "1" else 0
        )
    step_by_id = {s["step_id"]: s for s in steps}
    candidate_sets = {
        "rating_neg1": [sid for sid, s in step_by_id.items() if s["rating"] == -1],
        "all_steps": list(step_by_id),
    }
    rows = []
    for name, candidates in candidate_sets.items():
        deltas_naive: list[tuple[str, float, float]] = []
        deltas_roll: list[tuple[str, float, float]] = []
        accepted = 0
        for sid in candidates:
            conditions = runs_by_step.get(sid, {})
            control = conditions.get("control", {})
            target = conditions.get("target_delete", {})
            eval_runs = [r for r in (2, 3, 4) if r in control and r in target]
            if 1 not in target or len(eval_runs) < 3:
                continue
            c_rate = sum(control[r] for r in eval_runs) / len(eval_runs)
            t_rate = sum(target[r] for r in eval_runs) / len(eval_runs)
            pooled = (
                sum(control[r] for r in eval_runs) + sum(target[r] for r in eval_runs)
            ) / (2 * len(eval_runs))
            floor = null_floor_prob(len(eval_runs), len(eval_runs), pooled)
            deltas_naive.append((step_by_id[sid]["problem_id"], t_rate - c_rate, floor))
            if target[1] == 1:
                accepted += 1
                deltas_roll.append((step_by_id[sid]["problem_id"], t_rate - c_rate, floor))
            else:
                deltas_roll.append((step_by_id[sid]["problem_id"], 0.0, 0.0))
        for label, data in (("naive", deltas_naive), ("rollback", deltas_roll)):
            values = [d for _, d, _ in data]
            floors = [f for _, _, f in data]
            fake = [
                {"problem_id": p, "delta": d} for p, d, _ in data
            ]
            lcb = cluster_lcb(fake, 2000, SEED + 7)
            harmed = sum(1 for v in values if v < 0) / len(values)
            floor = sum(floors) / len(floors)
            rows.append(
                {
                    "candidate_set": name,
                    "policy": label,
                    "candidates": len(values),
                    "accept_rate": fmt(accepted / len(values), 3) if label == "rollback" else "1.0",
                    "net_per_candidate_pp": fmt(100 * sum(values) / len(values), 2),
                    "net_lcb_pp": fmt(100 * lcb, 2),
                    "harmed_share_obs": fmt(harmed, 3),
                    "harmed_share_null_floor": fmt(floor, 3),
                    "harmed_share_excess": fmt(max(0.0, harmed - floor), 3),
                }
            )
            print(rows[-1])
    # do-nothing null calibration: control runs 1-2 vs 3-4
    null_data = []
    for sid, conditions in runs_by_step.items():
        control = conditions.get("control", {})
        if not all(r in control for r in (1, 2, 3, 4)):
            continue
        a = (control[1] + control[2]) / 2
        b = (control[3] + control[4]) / 2
        pooled = (control[1] + control[2] + control[3] + control[4]) / 4
        null_data.append(
            (step_by_id[sid]["problem_id"], b - a, null_floor_prob(2, 2, pooled))
        )
    values = [d for _, d, _ in null_data]
    harmed = sum(1 for v in values if v < 0) / len(values)
    floor = sum(f for _, _, f in null_data) / len(null_data)
    rows.append(
        {
            "candidate_set": "all_steps",
            "policy": "do_nothing_control_split",
            "candidates": len(values),
            "accept_rate": "1.0",
            "net_per_candidate_pp": fmt(100 * sum(values) / len(values), 2),
            "net_lcb_pp": "",
            "harmed_share_obs": fmt(harmed, 3),
            "harmed_share_null_floor": fmt(floor, 3),
            "harmed_share_excess": fmt(max(0.0, harmed - floor), 3),
        }
    )
    print(rows[-1])
    write_csv(OUT_DIR / "policy_rollback_causal.csv", rows)


if __name__ == "__main__":
    import sys

    steps = load_steps()
    part = sys.argv[1] if len(sys.argv) > 1 else "all"
    if part in ("a", "all"):
        part_a_insample(steps)
    if part in ("b", "all"):
        part_b_nested(steps)
    if part in ("c", "all"):
        part_c_rollback(steps)
