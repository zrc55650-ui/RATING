#!/usr/bin/env python3
"""Create the main-text PRM-rating versus deletion-effect figure."""

from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path

from analysis_common import (
    ROOT,
    as_float,
    as_int,
    fmt,
    read_csv,
    stable_hash,
    write_csv,
    write_svg,
    xml_escape,
)


INPUT = ROOT / "data" / "master_step_table.csv"
SOURCE = ROOT / "data" / "prm_rating_vs_deletion_effect.csv"
SVG = ROOT / "build" / "figure5_prm_rating_vs_deletion_effect.svg"
BOOTSTRAPS = 5000
SEED = 20260803
COLORS = {"essential": "#2f6f9f", "redundant": "#d99024", "harmful": "#c33c54"}
TYPE_ORDER = ("essential", "redundant", "harmful")
RATING_ORDER = (-1, 0, 1)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def main() -> None:
    rows = read_csv(INPUT)
    groups: dict[tuple[int, str], list[float]] = defaultdict(list)
    for row in rows:
        groups[(as_int(row["prm_rating"]), row["step_type_analysis"].strip().lower())].append(
            100.0 * as_float(row["target_effect"])
        )

    rng = random.Random(SEED)
    summary = []
    for rating in RATING_ORDER:
        for semantic_type in TYPE_ORDER:
            values = groups[(rating, semantic_type)]
            draws = [
                sum(values[rng.randrange(len(values))] for _ in values) / len(values)
                for _ in range(BOOTSTRAPS)
            ]
            summary.append({
                "row_type": "summary",
                "step_id": "",
                "rating": str(rating),
                "semantic_type": semantic_type,
                "target_effect_pp": fmt(sum(values) / len(values), 6),
                "ci_low_pp": fmt(percentile(draws, 0.025), 6),
                "ci_high_pp": fmt(percentile(draws, 0.975), 6),
                "x_jitter": "",
            })

    point_rows = []
    for row in rows:
        rating = as_int(row["prm_rating"])
        semantic_type = row["step_type_analysis"].strip().lower()
        jitter = ((stable_hash(row["step_id"], seed=SEED) % 1000) / 1000.0 - 0.5) * 0.22
        point_rows.append({
            "row_type": "point",
            "step_id": row["step_id"],
            "rating": str(rating),
            "semantic_type": semantic_type,
            "target_effect_pp": fmt(100.0 * as_float(row["target_effect"]), 6),
            "ci_low_pp": "",
            "ci_high_pp": "",
            "x_jitter": fmt(jitter, 6),
        })
    write_csv(SOURCE, point_rows + summary)

    width, height = 900, 580
    left, right, top, bottom = 82, 180, 58, 82
    plot_width = width - left - right
    plot_height = height - top - bottom
    y_min, y_max = -100.0, 100.0

    def x_coord(rating: float) -> float:
        return left + (rating + 1.0) / 2.0 * plot_width

    def y_coord(effect: float) -> float:
        bounded = min(y_max, max(y_min, effect))
        return top + (y_max - bounded) / (y_max - y_min) * plot_height

    body = []
    for tick in (-100, -50, 0, 50, 100):
        y = y_coord(tick)
        zero_style = ' stroke="#8c96a8" stroke-width="1.6"' if tick == 0 else ""
        body.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" '
            f'class="grid"{zero_style}/>'
        )
        body.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" class="small" text-anchor="end">{tick}</text>'
        )
    for rating in RATING_ORDER:
        x = x_coord(rating)
        body.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" class="grid"/>'
        )
        body.append(
            f'<text x="{x:.1f}" y="{top + plot_height + 25}" class="label" text-anchor="middle">{rating:+d}</text>'
        )

    body.append(
        f'<rect x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" fill="none" class="axis"/>'
    )
    body.append(
        f'<text x="{left + plot_width / 2:.1f}" y="{height - 22}" class="label" text-anchor="middle">PRM rating (local correctness)</text>'
    )
    body.append(
        f'<text x="22" y="{top + plot_height / 2:.1f}" class="label" text-anchor="middle" '
        f'transform="rotate(-90 22 {top + plot_height / 2:.1f})">Deletion effect: target minus control (pp)</text>'
    )
    body.append(
        f'<text x="{left}" y="30" class="title">PRM rating vs. target-deletion effect</text>'
    )

    for row in point_rows:
        x = x_coord(float(row["rating"])) + float(row["x_jitter"]) * plot_width / 2.0
        y = y_coord(float(row["target_effect_pp"]))
        body.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.7" fill="{COLORS[row["semantic_type"]]}" opacity="0.34"/>'
        )

    type_offsets = {"essential": -0.13, "redundant": 0.0, "harmful": 0.13}
    for row in summary:
        rating = float(row["rating"])
        semantic_type = row["semantic_type"]
        x = x_coord(rating + type_offsets[semantic_type])
        mean_y = y_coord(float(row["target_effect_pp"]))
        low_y = y_coord(float(row["ci_low_pp"]))
        high_y = y_coord(float(row["ci_high_pp"]))
        color = COLORS[semantic_type]
        body.append(f'<line x1="{x:.1f}" y1="{low_y:.1f}" x2="{x:.1f}" y2="{high_y:.1f}" stroke="{color}" stroke-width="2.2"/>')
        body.append(f'<line x1="{x - 5:.1f}" y1="{low_y:.1f}" x2="{x + 5:.1f}" y2="{low_y:.1f}" stroke="{color}" stroke-width="2.2"/>')
        body.append(f'<line x1="{x - 5:.1f}" y1="{high_y:.1f}" x2="{x + 5:.1f}" y2="{high_y:.1f}" stroke="{color}" stroke-width="2.2"/>')
        body.append(f'<circle cx="{x:.1f}" cy="{mean_y:.1f}" r="5.8" fill="{color}" stroke="white" stroke-width="1.5"/>')

    legend_x = left + plot_width + 28
    legend_y = top + 48
    body.append(f'<text x="{legend_x}" y="{legend_y - 20}" class="label">Semantic type</text>')
    for semantic_type in TYPE_ORDER:
        body.append(f'<circle cx="{legend_x + 6}" cy="{legend_y:.1f}" r="5" fill="{COLORS[semantic_type]}"/>')
        body.append(f'<text x="{legend_x + 20}" y="{legend_y + 4:.1f}" class="small">{xml_escape(semantic_type.title())}</text>')
        legend_y += 24
    body.append(f'<text x="{legend_x}" y="{legend_y + 18:.1f}" class="small">Points: 600 steps</text>')
    body.append(f'<text x="{legend_x}" y="{legend_y + 38:.1f}" class="small">Dots: step effects</text>')
    body.append(f'<text x="{legend_x}" y="{legend_y + 56:.1f}" class="small">Marks: mean plus/minus 95% CI</text>')

    write_svg(SVG, width, height, "\n".join(body))
    print(f"Wrote {SVG}")
    print(f"Wrote {SOURCE}")


if __name__ == "__main__":
    main()
