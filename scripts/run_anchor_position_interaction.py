#!/usr/bin/env python3
"""Anchor-by-position robustness analysis on the frozen primary cohort."""

from __future__ import annotations

import csv
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "master_step_table.csv"
OUTPUT = ROOT / "data" / "anchor_position_interaction.csv"
SEED = 20260801
BOOTSTRAPS = 5000
POSITIONS = ("early", "middle", "late")


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
    draws = []
    for _ in range(BOOTSTRAPS):
        draws.append(mean([values[rng.randrange(len(values))] for _ in values]))
    return quantile(draws, 0.025), quantile(draws, 0.975)


def bootstrap_contrast(
    left: list[float], right: list[float], rng: random.Random
) -> tuple[float, float]:
    draws = []
    for _ in range(BOOTSTRAPS):
        left_draw = mean([left[rng.randrange(len(left))] for _ in left])
        right_draw = mean([right[rng.randrange(len(right))] for _ in right])
        draws.append(left_draw - right_draw)
    return quantile(draws, 0.025), quantile(draws, 0.975)


def bootstrap_interaction(
    left_anchor: list[float],
    left_other: list[float],
    right_anchor: list[float],
    right_other: list[float],
    rng: random.Random,
) -> tuple[float, float]:
    draws = []
    for _ in range(BOOTSTRAPS):
        left = mean([left_anchor[rng.randrange(len(left_anchor))] for _ in left_anchor])
        left -= mean([left_other[rng.randrange(len(left_other))] for _ in left_other])
        right = mean([right_anchor[rng.randrange(len(right_anchor))] for _ in right_anchor])
        right -= mean([right_other[rng.randrange(len(right_other))] for _ in right_other])
        draws.append(left - right)
    return quantile(draws, 0.025), quantile(draws, 0.975)


def main() -> None:
    with INPUT.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    cells: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        anchor = (
            row["prm_rating"].strip() == "-1"
            and row["step_type_analysis"].strip().lower() == "harmful"
        )
        group = "anchor" if anchor else "other"
        position = row["position_bin"].strip().lower()
        cells.setdefault((group, position), []).append(float(row["target_effect"]) * 100.0)

    rng = random.Random(SEED)
    output_rows: list[dict[str, str]] = []
    for position in POSITIONS:
        anchor_values = cells[("anchor", position)]
        other_values = cells[("other", position)]
        anchor_ci = bootstrap_mean(anchor_values, rng)
        other_ci = bootstrap_mean(other_values, rng)
        contrast = mean(anchor_values) - mean(other_values)
        contrast_ci = bootstrap_contrast(anchor_values, other_values, rng)
        output_rows.extend(
            [
                {
                    "row_type": "cell",
                    "position": position,
                    "group": "anchor",
                    "n": str(len(anchor_values)),
                    "effect_pp": f"{mean(anchor_values):.6f}",
                    "ci_low_pp": f"{anchor_ci[0]:.6f}",
                    "ci_high_pp": f"{anchor_ci[1]:.6f}",
                    "contrast_pp": "",
                    "contrast_ci_low_pp": "",
                    "contrast_ci_high_pp": "",
                },
                {
                    "row_type": "cell",
                    "position": position,
                    "group": "other",
                    "n": str(len(other_values)),
                    "effect_pp": f"{mean(other_values):.6f}",
                    "ci_low_pp": f"{other_ci[0]:.6f}",
                    "ci_high_pp": f"{other_ci[1]:.6f}",
                    "contrast_pp": "",
                    "contrast_ci_low_pp": "",
                    "contrast_ci_high_pp": "",
                },
                {
                    "row_type": "interaction",
                    "position": position,
                    "group": "anchor_minus_other",
                    "n": str(len(anchor_values) + len(other_values)),
                    "effect_pp": "",
                    "ci_low_pp": "",
                    "ci_high_pp": "",
                    "contrast_pp": f"{contrast:.6f}",
                    "contrast_ci_low_pp": f"{contrast_ci[0]:.6f}",
                    "contrast_ci_high_pp": f"{contrast_ci[1]:.6f}",
                },
            ]
        )

    anchor_contrasts = {
        row["position"]: float(row["contrast_pp"])
        for row in output_rows
        if row["row_type"] == "interaction"
    }
    pairwise_rows = []
    for left, right in (("early", "middle"), ("early", "late"), ("middle", "late")):
        left_values = cells[("anchor", left)]
        right_values = cells[("anchor", right)]
        ci = bootstrap_interaction(
            left_values,
            cells[("other", left)],
            right_values,
            cells[("other", right)],
            rng,
        )
        pairwise_rows.append(
            {
                "row_type": "anchor_position_difference",
                "position": f"{left}_minus_{right}",
                "group": "anchor_effect_difference",
                "n": str(len(left_values) + len(right_values)),
                "effect_pp": "",
                "ci_low_pp": "",
                "ci_high_pp": "",
                "contrast_pp": f"{anchor_contrasts[left] - anchor_contrasts[right]:.6f}",
                "contrast_ci_low_pp": f"{ci[0]:.6f}",
                "contrast_ci_high_pp": f"{ci[1]:.6f}",
            }
        )
    output_rows.extend(pairwise_rows)

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(output_rows[0].keys()) + ["seed", "bootstraps"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in output_rows:
            row["seed"] = str(SEED)
            row["bootstraps"] = str(BOOTSTRAPS)
            writer.writerow(row)

    for row in output_rows:
        if row["row_type"] in {"cell", "interaction", "anchor_position_difference"}:
            print(row["row_type"], row["position"], row["group"], row["n"],
                  row["effect_pp"] or row["contrast_pp"],
                  row["ci_low_pp"] or row["contrast_ci_low_pp"],
                  row["ci_high_pp"] or row["contrast_ci_high_pp"])


if __name__ == "__main__":
    main()
