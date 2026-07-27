#!/usr/bin/env python3
"""Joint rating x position natural-prevalence reweighting (review round 3).

The main-text natural-prevalence weights adjust rating composition only (the
cohort is position-balanced by design). This robustness check derives the
joint (rating, position-bin) distribution of the phase-2 test chosen-path
frame -- same bin rule as the cohort (index/(total-1); thirds) -- and
reweights the balanced cohort's mean target-deletion effect by joint weights
w(r,b) = nat_share(r,b) / cohort_share(r,b), next to the rating-only
weighting, with 5,000-replicate step-cluster bootstraps (seed 20260723).

Outputs workstream_F_final_statistics/robustness/
natural_prevalence_joint_position.csv. Stdlib only; run from scripts/.
"""

from __future__ import annotations

import json
import random
from collections import Counter

from analysis_common import ROOT, as_float, read_csv, write_csv

OUT = (
    ROOT
    / "workstream_F_final_statistics"
    / "robustness"
    / "natural_prevalence_joint_position.csv"
)
REPS = 5000
SEED = 20260723


def position_bin(index: int, total_steps: int) -> str:
    if total_steps <= 1:
        return "early"
    ratio = index / (total_steps - 1)
    if ratio < 1 / 3:
        return "early"
    if ratio < 2 / 3:
        return "middle"
    return "late"


def main() -> None:
    nat: Counter = Counter()
    with (ROOT / "data" / "phase2_test.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            steps = json.loads(line).get("label", {}).get("steps", [])
            total = len(steps)
            for index, step in enumerate(steps):
                completions = step.get("completions") or []
                picked = step.get("chosen_completion")
                if picked is None or not (0 <= picked < len(completions)):
                    continue
                rating = completions[picked].get("rating")
                if rating in (-1, 0, 1):
                    nat[(rating, position_bin(index, total))] += 1
    nat_total = sum(nat.values())

    cohort = [
        ((int(row["prm_rating"]), row["position_bin"]), as_float(row["target_effect"]))
        for row in read_csv(ROOT / "data" / "master_step_table.csv")
    ]
    coh_counts = Counter(key for key, _ in cohort)
    nat_rating: Counter = Counter()
    coh_rating: Counter = Counter()
    for (rating, _), count in nat.items():
        nat_rating[rating] += count
    for (rating, _), count in coh_counts.items():
        coh_rating[rating] += count

    def weights(joint: bool) -> dict[tuple[int, str], float]:
        table = {}
        for key, count in coh_counts.items():
            if joint:
                table[key] = (nat[key] / nat_total) / (count / len(cohort))
            else:
                table[key] = (nat_rating[key[0]] / nat_total) / (
                    coh_rating[key[0]] / len(cohort)
                )
        return table

    def weighted_mean(sample: list, table: dict) -> float:
        num = sum(table[key] * effect for key, effect in sample)
        den = sum(table[key] for key, _ in sample)
        return num / den

    rng = random.Random(SEED)
    rows_out = []
    for label, joint in (("rating_only", False), ("rating_x_position", True)):
        table = weights(joint)
        estimate = weighted_mean(cohort, table) * 100
        boots = sorted(
            weighted_mean(
                [cohort[rng.randrange(len(cohort))] for _ in range(len(cohort))],
                table,
            )
            * 100
            for _ in range(REPS)
        )
        rows_out.append(
            {
                "weighting": label,
                "mean_target_effect_pp": f"{estimate:.2f}",
                "ci_lower_pp": f"{boots[int(0.025 * REPS)]:.2f}",
                "ci_upper_pp": f"{boots[int(0.975 * REPS) - 1]:.2f}",
            }
        )
    for (rating, bin_), count in sorted(nat.items()):
        rows_out.append(
            {
                "weighting": f"natural_joint_share:{rating}:{bin_}",
                "mean_target_effect_pp": str(count),
                "ci_lower_pp": f"{count / nat_total:.4f}",
                "ci_upper_pp": "",
            }
        )
    write_csv(
        OUT,
        rows_out,
        ["weighting", "mean_target_effect_pp", "ci_lower_pp", "ci_upper_pp"],
    )
    for row in rows_out[:2]:
        print(row)


if __name__ == "__main__":
    main()
