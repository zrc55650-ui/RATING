#!/usr/bin/env python3
"""Semantic-label ablation and length-adjusted deletion-effect regression."""

from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "master_step_table.csv"
LABEL_OUTPUT = ROOT / "data" / "semantic_label_ablation.csv"
REG_OUTPUT = ROOT / "data" / "semantic_length_regression.csv"
SEED = 20260802
BOOTSTRAPS = 5000


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def bootstrap_mean(values: list[float], rng: random.Random) -> tuple[float, float]:
    draws = [
        mean([values[rng.randrange(len(values))] for _ in values])
        for _ in range(BOOTSTRAPS)
    ]
    return quantile(draws, 0.025), quantile(draws, 0.975)


def bootstrap_difference(
    left: list[float], right: list[float], rng: random.Random
) -> tuple[float, float]:
    draws = []
    for _ in range(BOOTSTRAPS):
        left_mean = mean([left[rng.randrange(len(left))] for _ in left])
        right_mean = mean([right[rng.randrange(len(right))] for _ in right])
        draws.append(left_mean - right_mean)
    return quantile(draws, 0.025), quantile(draws, 0.975)


def solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting for the small OLS system."""
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    size = len(vector)
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-10:
            raise ValueError("singular design matrix")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                current - factor * pivot_value
                for current, pivot_value in zip(augmented[row], augmented[column])
            ]
    return [augmented[row][-1] for row in range(size)]


def design_row(row: dict[str, str]) -> list[float]:
    rating = row["prm_rating"].strip()
    semantic = row["step_type_analysis"].strip().lower()
    position = row["position_bin"].strip().lower()
    return [
        1.0,
        float(rating == "-1"),
        float(rating == "0"),
        float(semantic == "redundant"),
        float(semantic == "harmful"),
        float(position == "middle"),
        float(position == "late"),
        math.log1p(float(row["target_tokens"])),
    ]


def fit_ols(rows: list[dict[str, str]]) -> list[float]:
    design = [design_row(row) for row in rows]
    outcomes = [100.0 * float(row["target_effect"]) for row in rows]
    width = len(design[0])
    xtx = [[0.0 for _ in range(width)] for _ in range(width)]
    xty = [0.0 for _ in range(width)]
    for features, outcome in zip(design, outcomes):
        for i in range(width):
            xty[i] += features[i] * outcome
            for j in range(width):
                xtx[i][j] += features[i] * features[j]
    return solve_linear_system(xtx, xty)


def regression_bootstrap(rows: list[dict[str, str]], rng: random.Random) -> list[list[float]]:
    by_problem: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_problem[row["problem_id"]].append(row)
    clusters = list(by_problem.values())
    estimates = []
    while len(estimates) < BOOTSTRAPS:
        sample = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        sampled_rows = [row for cluster in sample for row in cluster]
        try:
            estimates.append(fit_ols(sampled_rows))
        except ValueError:
            continue
    return estimates


def main() -> None:
    with INPUT.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    anchor = [
        row for row in rows
        if row["prm_rating"].strip() == "-1"
        and row["step_type_analysis"].strip().lower() == "harmful"
    ]
    neg1 = [row for row in rows if row["prm_rating"].strip() == "-1"]
    neg1_nonharmful = [row for row in neg1 if row not in anchor]

    rng = random.Random(SEED)
    label_groups = [
        ("rating_neg1", "Rating = -1 only", neg1),
        ("rating_neg1_harmful", "Rating = -1 x Harmful", anchor),
        ("rating_neg1_nonharmful", "Rating = -1 x non-Harmful", neg1_nonharmful),
    ]
    label_rows = []
    for key, description, group in label_groups:
        effects = [100.0 * float(row["target_effect"]) for row in group]
        low, high = bootstrap_mean(effects, rng)
        label_rows.append({
            "metric": key,
            "description": description,
            "n": str(len(group)),
            "effect_pp": f"{mean(effects):.6f}",
            "ci_low_pp": f"{low:.6f}",
            "ci_high_pp": f"{high:.6f}",
            "seed": str(SEED),
            "bootstraps": str(BOOTSTRAPS),
        })
    anchor_effects = [100.0 * float(row["target_effect"]) for row in anchor]
    nonharmful_effects = [100.0 * float(row["target_effect"]) for row in neg1_nonharmful]
    low, high = bootstrap_difference(anchor_effects, nonharmful_effects, rng)
    label_rows.append({
        "metric": "rating_neg1_harmful_minus_nonharmful",
        "description": "Within-rating semantic contrast",
        "n": f"{len(anchor)} vs {len(neg1_nonharmful)}",
        "effect_pp": f"{mean(anchor_effects) - mean(nonharmful_effects):.6f}",
        "ci_low_pp": f"{low:.6f}",
        "ci_high_pp": f"{high:.6f}",
        "seed": str(SEED),
        "bootstraps": str(BOOTSTRAPS),
    })

    with LABEL_OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(label_rows[0].keys()))
        writer.writeheader()
        writer.writerows(label_rows)

    point = fit_ols(rows)
    bootstraps = regression_bootstrap(rows, rng)
    terms = [
        ("intercept", "Intercept"),
        ("rating_neg1", "Rating = -1 vs +1"),
        ("rating_zero", "Rating = 0 vs +1"),
        ("semantic_redundant", "Redundant vs Essential"),
        ("semantic_harmful", "Harmful vs Essential"),
        ("position_middle", "Middle vs Early"),
        ("position_late", "Late vs Early"),
        ("log_target_tokens", "log(1 + target tokens)"),
    ]
    regression_rows = []
    for index, (key, description) in enumerate(terms):
        values = [estimate[index] for estimate in bootstraps]
        regression_rows.append({
            "term": key,
            "description": description,
            "estimate_pp": f"{point[index]:.6f}",
            "ci_low_pp": f"{quantile(values, 0.025):.6f}",
            "ci_high_pp": f"{quantile(values, 0.975):.6f}",
            "n_steps": str(len(rows)),
            "n_problem_clusters": str(len({row['problem_id'] for row in rows})),
            "seed": str(SEED),
            "bootstraps": str(BOOTSTRAPS),
        })

    with REG_OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(regression_rows[0].keys()))
        writer.writeheader()
        writer.writerows(regression_rows)

    for row in label_rows:
        print("label", row["metric"], row["n"], row["effect_pp"], row["ci_low_pp"], row["ci_high_pp"])
    for row in regression_rows:
        if row["term"] in {"semantic_harmful", "log_target_tokens"}:
            print("regression", row["term"], row["estimate_pp"], row["ci_low_pp"], row["ci_high_pp"])


if __name__ == "__main__":
    main()
