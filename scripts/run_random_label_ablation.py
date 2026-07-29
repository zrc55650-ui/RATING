#!/usr/bin/env python3
"""Permutation ablation for semantic labels on the frozen 600-step cohort.

The ablation keeps the observed label margins but breaks the association
between semantic labels, ratings, and deletion outcomes.  The primary anchor
uses the initial labels; the policy-candidate analysis uses the calibrated
labels, matching the paper's frozen analyses.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "master_step_table.csv"
OUTPUT = ROOT / "data" / "random_semantic_label_ablation.csv"
SEED = 20260729
PERMUTATIONS = 5000


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def summarize(
    metric: str,
    observed: float,
    null: list[float],
    description: str,
) -> dict[str, str]:
    return {
        "metric": metric,
        "description": description,
        "observed": f"{observed:.6f}",
        "null_mean": f"{mean(null):.6f}",
        "null_p025": f"{quantile(null, 0.025):.6f}",
        "null_p50": f"{quantile(null, 0.50):.6f}",
        "null_p975": f"{quantile(null, 0.975):.6f}",
        "permutations": str(PERMUTATIONS),
        "seed": str(SEED),
    }


def anchor_metrics(rows: list[dict[str, str]], labels: list[str]) -> tuple[float, float, int]:
    low_rating = [i for i, row in enumerate(rows) if row["prm_rating"] == "-1"]
    anchor = [i for i in low_rating if labels[i] == "harmful"]
    non_anchor = [i for i in low_rating if labels[i] != "harmful"]
    anchor_effect = mean([float(rows[i]["target_effect"]) for i in anchor])
    non_anchor_effect = mean([float(rows[i]["target_effect"]) for i in non_anchor])
    return anchor_effect, anchor_effect - non_anchor_effect, len(anchor)


def policy_metrics(rows: list[dict[str, str]], labels: list[str]) -> tuple[float, float, int]:
    selected = [
        i
        for i, row in enumerate(rows)
        if row["prm_rating"] == "-1" and labels[i] == "harmful"
    ]
    return (
        len(selected) / len(rows),
        mean([float(rows[i]["target_effect"]) for i in selected]),
        len(selected),
    )


def main() -> None:
    with INPUT.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    primary = [row["step_type_analysis"].strip().lower() for row in rows]
    calibrated = [row["step_type_human_calibrated"].strip().lower() for row in rows]

    observed_anchor, observed_contrast, observed_anchor_n = anchor_metrics(rows, primary)
    observed_coverage, observed_policy_effect, observed_policy_n = policy_metrics(rows, calibrated)

    rng = random.Random(SEED)
    null_anchor_effect: list[float] = []
    null_anchor_contrast: list[float] = []
    null_anchor_n: list[float] = []
    null_policy_coverage: list[float] = []
    null_policy_effect: list[float] = []
    null_policy_n: list[float] = []

    for _ in range(PERMUTATIONS):
        shuffled_primary = primary.copy()
        shuffled_calibrated = calibrated.copy()
        rng.shuffle(shuffled_primary)
        rng.shuffle(shuffled_calibrated)

        anchor_effect, contrast, anchor_n = anchor_metrics(rows, shuffled_primary)
        coverage, policy_effect, policy_n = policy_metrics(rows, shuffled_calibrated)
        null_anchor_effect.append(anchor_effect)
        null_anchor_contrast.append(contrast)
        null_anchor_n.append(float(anchor_n))
        null_policy_coverage.append(coverage)
        null_policy_effect.append(policy_effect)
        null_policy_n.append(float(policy_n))

    output_rows = [
        summarize(
            "primary_anchor_mean_effect_pp",
            observed_anchor * 100.0,
            [value * 100.0 for value in null_anchor_effect],
            f"Raw mean effect for rating=-1 and harmful; observed n={observed_anchor_n}",
        ),
        summarize(
            "primary_within_rating_harmful_contrast_pp",
            observed_contrast * 100.0,
            [value * 100.0 for value in null_anchor_contrast],
            "Mean effect for rating=-1 and harmful minus rating=-1 and non-harmful",
        ),
        summarize(
            "primary_anchor_n",
            float(observed_anchor_n),
            null_anchor_n,
            "Count of rating=-1 and harmful steps under the primary label margins",
        ),
        summarize(
            "calibrated_policy_candidate_coverage_pct",
            observed_coverage * 100.0,
            [value * 100.0 for value in null_policy_coverage],
            f"Candidate coverage for rating=-1 and harmful; observed n={observed_policy_n}",
        ),
        summarize(
            "calibrated_policy_candidate_effect_pp",
            observed_policy_effect * 100.0,
            [value * 100.0 for value in null_policy_effect],
            "Mean target effect among rating=-1 and harmful policy candidates",
        ),
        summarize(
            "calibrated_policy_candidate_n",
            float(observed_policy_n),
            null_policy_n,
            "Count of rating=-1 and harmful policy candidates under calibrated margins",
        ),
    ]

    OUTPUT.parent.mkdir(exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_rows[0].keys())
        writer.writeheader()
        writer.writerows(output_rows)

    for row in output_rows:
        print(row["metric"], row["observed"], row["null_p025"], row["null_p975"])


if __name__ == "__main__":
    main()
