#!/usr/bin/env python3
"""Four-run empirical stability analysis at the target-step level."""

from __future__ import annotations

import math
from pathlib import Path

from analysis_common import (
    ROOT,
    as_bool,
    as_float,
    as_int,
    fmt,
    fmt_pp,
    mean,
    read_csv,
    write_csv,
    write_svg,
    xml_escape,
)


CATEGORIES = [
    "Strongly beneficial",
    "Weakly beneficial",
    "Strongly harmful",
    "Weakly harmful",
    "Mixed / unstable",
    "Stable no-change",
]


def classify(step: dict[str, str]) -> str:
    wc = as_int(step["wrong_to_correct_count"])
    cw = as_int(step["correct_to_wrong_count"])
    if wc >= 2 and cw == 0:
        return "Strongly beneficial"
    if wc == 1 and cw == 0:
        return "Weakly beneficial"
    if cw >= 2 and wc == 0:
        return "Strongly harmful"
    if cw == 1 and wc == 0:
        return "Weakly harmful"
    if wc > 0 and cw > 0:
        return "Mixed / unstable"
    return "Stable no-change"


def summarize_group(
    dimension: str,
    group: str,
    members: list[dict],
) -> list[dict]:
    eligible = [
        as_float(step["pure_semantic_effect"])
        for step in members
        if as_bool(step["placebo_eligible"])
    ]
    rows = []
    for category in CATEGORIES:
        count = sum(step["stability_category"] == category for step in members)
        rows.append(
            {
                "dimension": dimension,
                "group": group,
                "stability_category": category,
                "steps": len(members),
                "category_count": count,
                "category_share": fmt(count / len(members), 6),
                "mean_target_effect": fmt(
                    mean(as_float(step["target_effect"]) for step in members), 6
                ),
                "placebo_eligible_steps": len(eligible),
                "mean_pure_semantic_effect": fmt(mean(eligible), 6),
                "sign_conflict_steps": sum(
                    step["stability_category"] == "Mixed / unstable" for step in members
                ),
            }
        )
    return rows


def heatmap(steps: list[dict], path: Path) -> None:
    ratings = [-1, 0, 1]
    types = ["essential", "redundant", "harmful"]
    width, height = 790, 470
    left, top = 160, 95
    cell_width, cell_height = 190, 100
    pieces = [
        '<text x="40" y="34" class="title">Step-level stability by PRM rating × analysis Step Type</text>',
        '<text x="40" y="56" class="small">Cell: strongly beneficial share; below: mean target effect (pp)</text>',
    ]
    for column, step_type in enumerate(types):
        x = left + column * cell_width + cell_width / 2
        pieces.append(
            f'<text x="{x}" y="{top-18}" text-anchor="middle" class="label">'
            f"{xml_escape(step_type.title())}</text>"
        )
    for row_index, rating in enumerate(ratings):
        y = top + row_index * cell_height
        pieces.append(
            f'<text x="{left-18}" y="{y+cell_height/2+5}" text-anchor="end" class="label">'
            f"rating {rating}</text>"
        )
        for column, step_type in enumerate(types):
            members = [
                step
                for step in steps
                if as_int(step["prm_rating"]) == rating
                and step["step_type_analysis"].lower() == step_type
            ]
            strong_share = (
                mean(
                    float(step["stability_category"] == "Strongly beneficial")
                    for step in members
                )
                if members
                else math.nan
            )
            target_effect = (
                mean(as_float(step["target_effect"]) for step in members)
                if members
                else math.nan
            )
            intensity = 0 if math.isnan(strong_share) else min(1.0, strong_share / 0.6)
            red = round(242 - intensity * 155)
            green = round(247 - intensity * 80)
            blue = round(252 - intensity * 25)
            x = left + column * cell_width
            pieces.append(
                f'<rect x="{x}" y="{y}" width="{cell_width-5}" height="{cell_height-5}" '
                f'fill="rgb({red},{green},{blue})" stroke="#cbd2df"/>'
            )
            label = "—" if math.isnan(strong_share) else f"{strong_share*100:.1f}%"
            effect = "—" if math.isnan(target_effect) else f"{target_effect*100:+.1f} pp"
            pieces.append(
                f'<text x="{x+(cell_width-5)/2}" y="{y+42}" text-anchor="middle" '
                f'style="font-size:22px;font-weight:700">{label}</text>'
            )
            pieces.append(
                f'<text x="{x+(cell_width-5)/2}" y="{y+69}" text-anchor="middle" '
                f'class="small">{effect}; n={len(members)}</text>'
            )
    write_svg(path, width, height, "\n".join(pieces))


def main() -> None:
    steps = read_csv(ROOT / "master_step_table.csv")
    output_rows = []
    for step in steps:
        updated = dict(step)
        updated["stability_category"] = classify(step)
        updated["danger_rate_defined"] = int(as_int(step["control_correct_count"]) > 0)
        updated["recovery_rate_defined"] = int(as_int(step["control_correct_count"]) < 4)
        output_rows.append(updated)
    write_csv(ROOT / "step_stability_labels.csv", output_rows)

    group_specs: list[tuple[str, str, list[dict]]] = [("overall", "Overall", output_rows)]
    for rating in (-1, 0, 1):
        group_specs.append(
            (
                "prm_rating",
                str(rating),
                [step for step in output_rows if as_int(step["prm_rating"]) == rating],
            )
        )
    for label_column in ("step_type_analysis", "step_type_human_calibrated"):
        for step_type in ("essential", "redundant", "harmful"):
            group_specs.append(
                (
                    label_column,
                    step_type,
                    [
                        step
                        for step in output_rows
                        if step[label_column].lower() == step_type
                    ],
                )
            )
    for rating in (-1, 0, 1):
        for step_type in ("essential", "redundant", "harmful"):
            members = [
                step
                for step in output_rows
                if as_int(step["prm_rating"]) == rating
                and step["step_type_analysis"].lower() == step_type
            ]
            if members:
                group_specs.append(
                    ("rating_x_step_type_analysis", f"{rating} x {step_type}", members)
                )
    for frequency in ("0/4", "1/4", "2/4", "3/4", "4/4"):
        numerator = int(frequency[0])
        group_specs.append(
            (
                "control_correct_frequency",
                frequency,
                [
                    step
                    for step in output_rows
                    if as_int(step["control_correct_count"]) == numerator
                ],
            )
        )

    summary_rows: list[dict] = []
    for dimension, group, members in group_specs:
        summary_rows.extend(summarize_group(dimension, group, members))
    write_csv(ROOT / "step_stability_by_group.csv", summary_rows)
    heatmap(output_rows, ROOT / "step_stability_heatmap.svg")

    overall_counts = {
        category: sum(step["stability_category"] == category for step in output_rows)
        for category in CATEGORIES
    }
    key_group = [
        step
        for step in output_rows
        if as_int(step["prm_rating"]) == -1
        and step["step_type_analysis"].lower() == "harmful"
    ]
    stable_correct = [
        step for step in output_rows if as_int(step["control_correct_count"]) == 4
    ]
    lines = [
        "# Step-Level Stability Report",
        "",
        "本分析使用每个 target step 的 4 次 paired runs，类别定义在分组结果之前固定。"
        "它衡量 empirical consistency，不等同于个体步骤真实概率。",
        "",
        "## Overall",
        "",
        "| Category | Steps | Share |",
        "|---|---:|---:|",
    ]
    for category in CATEGORIES:
        count = overall_counts[category]
        lines.append(f"| {category} | {count} | {count/len(output_rows)*100:.1f}% |")
    strong_key = sum(
        step["stability_category"] == "Strongly beneficial" for step in key_group
    )
    weak_key = sum(
        step["stability_category"] == "Weakly beneficial" for step in key_group
    )
    mixed_key = sum(step["stability_category"] == "Mixed / unstable" for step in key_group)
    harmed_stable = sum(
        step["stability_category"] in {"Strongly harmful", "Weakly harmful"}
        for step in stable_correct
    )
    lines += [
        "",
        "## Key diagnostic groups",
        "",
        f"- `rating=-1 × Harmful`（analysis label）共 **{len(key_group)}** steps："
        f"Strongly beneficial **{strong_key} ({strong_key/len(key_group)*100:.1f}%)**，"
        f"Weakly beneficial **{weak_key} ({weak_key/len(key_group)*100:.1f}%)**，"
        f"Mixed/unstable **{mixed_key} ({mixed_key/len(key_group)*100:.1f}%)**。",
        f"- Control 4/4 correct 共 **{len(stable_correct)}** steps；其中至少出现一次纯伤害且无恢复的 "
        f"step 为 **{harmed_stable} ({harmed_stable/len(stable_correct)*100:.1f}%)**。",
        "",
        "## Interpretation",
        "",
        "平均正效应不意味着每个 low-rated harmful step 都稳定获益。部署型 pruning 规则仍需要"
        " trajectory-state validation 与 rollback。Placebo pure-semantic 分组仅限 eligible steps。",
        "",
        "Audit-corrected stability labels 尚待人工 Judge Audit 完成后进行 sensitivity analysis。",
        "",
    ]
    (ROOT / "step_stability_report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
