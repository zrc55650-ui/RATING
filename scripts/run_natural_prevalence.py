#!/usr/bin/env python3
"""Natural-prevalence reweighting of the balanced 600-step cohort.

The cohort is case--control balanced (200 steps per rating). This script
computes the natural rating prevalence over all rated steps in the PRM800K
phase-2 test split, then reweights cohort estimates by
w(r) = p_natural(r) / (1/3):

  * overall target-deletion effect (weighted cluster bootstrap over steps)
  * run-level danger and benefit base rates
  * share of steps that are dangerous / beneficial to delete

Outputs workstream_F_final_statistics/robustness/natural_prevalence.csv.
Stdlib only; run from the repository root.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict

from analysis_common import ROOT, as_float, as_int, fmt, read_csv, write_csv

OUT_DIR = ROOT / "workstream_F_final_statistics" / "robustness"
REPLICATES = 5000
SEED = 20260723


def natural_rating_distribution() -> dict[int, float]:
    counter: Counter = Counter()
    with (ROOT / "data" / "phase2_test.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            for step in record.get("label", {}).get("steps", []):
                chosen = step.get("chosen_completion")
                completions = step.get("completions") or []
                if chosen is None or chosen >= len(completions):
                    continue
                rating = completions[chosen].get("rating")
                if rating in (-1, 0, 1):
                    counter[rating] += 1
    total = sum(counter.values())
    return {r: counter[r] / total for r in (-1, 0, 1)}, total


def weighted_mean(pairs: list[tuple[float, float]]) -> float:
    wsum = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / wsum


def weighted_cluster_bootstrap(
    pairs_by_step: dict[str, tuple[float, float]], seed: int
) -> tuple[float, float, float]:
    ids = sorted(pairs_by_step)
    point = weighted_mean([pairs_by_step[i] for i in ids])
    rng = random.Random(seed)
    stats = []
    for _ in range(REPLICATES):
        sample = [pairs_by_step[ids[rng.randrange(len(ids))]] for _ in ids]
        stats.append(weighted_mean(sample))
    stats.sort()
    return point, stats[int(0.025 * REPLICATES)], stats[min(int(0.975 * REPLICATES), REPLICATES - 1)]


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    natural, n_rated = natural_rating_distribution()
    print("natural prevalence over", n_rated, "rated phase-2 test steps:", natural)
    weights = {r: natural[r] / (1 / 3) for r in natural}

    steps = []
    for row in read_csv(ROOT / "data" / "master_step_table.csv"):
        rating = as_int(row["prm_rating"])
        steps.append(
            {
                "step_id": row["step_id"],
                "rating": rating,
                "w": weights[rating],
                "target_effect": as_float(row["target_effect"]),
                "c2w": as_int(row["correct_to_wrong_count"]),
                "w2c": as_int(row["wrong_to_correct_count"]),
                "control_correct": as_int(row["control_correct_count"]),
            }
        )

    rows = []
    for scope, use_weights in (("balanced_cohort", False), ("natural_prevalence", True)):
        pairs = {
            s["step_id"]: (s["target_effect"], s["w"] if use_weights else 1.0)
            for s in steps
        }
        point, lo, hi = weighted_cluster_bootstrap(pairs, SEED + (7 if use_weights else 3))
        wsum = sum(s["w"] if use_weights else 1.0 for s in steps)
        danger_runs = sum(s["c2w"] * (s["w"] if use_weights else 1.0) for s in steps)
        benefit_runs = sum(s["w2c"] * (s["w"] if use_weights else 1.0) for s in steps)
        rows.append(
            {
                "scope": scope,
                "overall_target_effect_pp": fmt(100 * point, 2),
                "ci_lower_pp": fmt(100 * lo, 2),
                "ci_upper_pp": fmt(100 * hi, 2),
                "run_danger_rate": fmt(danger_runs / (4 * wsum), 4),
                "run_benefit_rate": fmt(benefit_runs / (4 * wsum), 4),
                "dangerous_step_share": fmt(
                    sum((s["w"] if use_weights else 1.0) for s in steps if s["c2w"] > 0) / wsum, 4
                ),
                "beneficial_step_share": fmt(
                    sum((s["w"] if use_weights else 1.0) for s in steps if s["w2c"] > 0) / wsum, 4
                ),
            }
        )
        print(rows[-1])
    write_csv(OUT_DIR / "natural_prevalence.csv", rows)
    (OUT_DIR / "natural_prevalence_weights.json").write_text(
        json.dumps(
            {"natural_distribution": {str(k): v for k, v in natural.items()},
             "n_rated_steps": n_rated,
             "weights": {str(k): v for k, v in weights.items()}},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
