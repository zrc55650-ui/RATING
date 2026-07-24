#!/usr/bin/env python3
"""Selection-bias audit for the 511 placebo-eligible and 89 skipped steps."""

from __future__ import annotations

import math
from pathlib import Path

from analysis_common import (
    BOOTSTRAP_REPLICATES,
    ROOT,
    SEED,
    as_bool,
    as_float,
    as_int,
    bootstrap_group_difference,
    fmt,
    mean,
    median,
    permutation_pvalue,
    quantile,
    read_csv,
    sample_sd,
    write_csv,
    write_svg,
    xml_escape,
)


CONTINUOUS = [
    ("target_tokens", "Target-step tokens"),
    ("prefix_tokens", "Prefix tokens"),
    ("control_avg_correct", "Control accuracy"),
    ("target_avg_correct", "Target-deletion accuracy"),
    ("target_effect", "Raw target effect"),
    ("danger_rate", "Step-level danger rate (defined subset)"),
    ("recovery_rate", "Step-level recovery rate (defined subset)"),
    ("mean_target_minus_control_tokens", "Mean token change"),
    ("completion_fraction", "Control/target completed fraction"),
]

CATEGORICAL = [
    ("prm_rating", "PRM rating"),
    ("step_type_analysis", "Analysis Step Type"),
    ("step_type_human_calibrated", "Human-calibrated Step Type"),
    ("rating_x_type", "Rating × analysis Step Type"),
    ("position_bin", "Step position"),
    ("control_stability", "Control stability"),
    ("has_abnormal_completion", "Any abnormal completion"),
]


def pooled_smd(left: list[float], right: list[float]) -> float:
    left_clean = [value for value in left if not math.isnan(value)]
    right_clean = [value for value in right if not math.isnan(value)]
    if len(left_clean) < 2 or len(right_clean) < 2:
        return math.nan
    pooled_variance = (
        (len(left_clean) - 1) * sample_sd(left_clean) ** 2
        + (len(right_clean) - 1) * sample_sd(right_clean) ** 2
    ) / (len(left_clean) + len(right_clean) - 2)
    if pooled_variance <= 1e-15:
        return 0.0 if mean(left_clean) == mean(right_clean) else math.inf
    return (mean(left_clean) - mean(right_clean)) / math.sqrt(pooled_variance)


def binary_smd(left_count: int, left_n: int, right_count: int, right_n: int) -> float:
    left_p = left_count / left_n
    right_p = right_count / right_n
    pooled = (left_count + right_count) / (left_n + right_n)
    denominator = math.sqrt(max(pooled * (1 - pooled), 0.0))
    if denominator <= 1e-15:
        return 0.0 if left_p == right_p else math.inf
    return (left_p - right_p) / denominator


def ks_statistic(left: list[float], right: list[float]) -> float:
    left_clean = sorted(value for value in left if not math.isnan(value))
    right_clean = sorted(value for value in right if not math.isnan(value))
    if not left_clean or not right_clean:
        return math.nan
    values = sorted(set(left_clean + right_clean))
    left_index = 0
    right_index = 0
    maximum = 0.0
    for value in values:
        while left_index < len(left_clean) and left_clean[left_index] <= value:
            left_index += 1
        while right_index < len(right_clean) and right_clean[right_index] <= value:
            right_index += 1
        maximum = max(
            maximum,
            abs(left_index / len(left_clean) - right_index / len(right_clean)),
        )
    return maximum


def chi_square_statistic(left: list[str], right: list[str]) -> float:
    levels = sorted(set(left + right))
    total = len(left) + len(right)
    result = 0.0
    for level in levels:
        level_total = left.count(level) + right.count(level)
        expected_left = len(left) * level_total / total
        expected_right = len(right) * level_total / total
        observed_left = left.count(level)
        observed_right = right.count(level)
        if expected_left:
            result += (observed_left - expected_left) ** 2 / expected_left
        if expected_right:
            result += (observed_right - expected_right) ** 2 / expected_right
    return result


def describe(values: list[float]) -> str:
    clean = [value for value in values if not math.isnan(value)]
    if not clean:
        return ""
    return (
        f"mean={mean(clean):.4f}; median={median(clean):.4f}; "
        f"IQR=[{quantile(clean, 0.25):.4f}, {quantile(clean, 0.75):.4f}]; n={len(clean)}"
    )


def loveplot(balance_rows: list[dict], path: Path) -> None:
    summary: dict[str, float] = {}
    for row in balance_rows:
        value = as_float(row["standardized_difference_or_distance"])
        if math.isnan(value) or math.isinf(value):
            continue
        summary[row["variable_label"]] = max(
            summary.get(row["variable_label"], 0.0), abs(value)
        )
    ordered = sorted(summary.items(), key=lambda item: item[1], reverse=True)
    width = 820
    row_height = 34
    height = 90 + row_height * len(ordered)
    left, right, top = 270, 45, 55
    plot_width = width - left - right
    maximum = max(0.5, max((value for _, value in ordered), default=0.5) * 1.08)
    pieces = [
        '<text x="30" y="30" class="title">Placebo eligibility balance</text>',
        '<text x="30" y="49" class="small">Absolute SMD; categorical variables use maximum level-wise SMD</text>',
    ]
    threshold_x = left + plot_width * 0.25 / maximum
    pieces.append(
        f'<line x1="{threshold_x}" y1="{top-8}" x2="{threshold_x}" '
        f'y2="{top+row_height*len(ordered)}" stroke="#c54a3f" stroke-width="2" stroke-dasharray="5 4"/>'
    )
    pieces.append(
        f'<text x="{threshold_x+5}" y="{top-12}" class="small" fill="#c54a3f">0.25 threshold</text>'
    )
    for index, (label, value) in enumerate(ordered):
        y = top + index * row_height
        x = left + plot_width * value / maximum
        color = "#c54a3f" if value >= 0.25 else "#4778b8"
        pieces.append(
            f'<text x="{left-12}" y="{y+5}" text-anchor="end" class="small">{xml_escape(label)}</text>'
        )
        pieces.append(
            f'<line x1="{left}" y1="{y}" x2="{x}" y2="{y}" stroke="{color}" stroke-width="4"/>'
        )
        pieces.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{color}"/>')
        pieces.append(
            f'<text x="{x+9}" y="{y+5}" class="small">{value:.2f}</text>'
        )
    write_svg(path, width, height, "\n".join(pieces))


def main() -> None:
    steps = read_csv(ROOT / "master_step_table.csv")
    runs = read_csv(ROOT / "master_run_table.csv")
    run_groups: dict[str, list[dict[str, str]]] = {}
    for run in runs:
        if run["condition"] in {"control", "target_delete"}:
            run_groups.setdefault(run["step_id"], []).append(run)

    audit_steps = []
    for step in steps:
        updated = dict(step)
        relevant_runs = run_groups[step["step_id"]]
        completed = sum(run["generator_status"] == "completed" for run in relevant_runs)
        updated["completion_fraction"] = completed / len(relevant_runs)
        updated["has_abnormal_completion"] = str(
            any(run["generator_status"] != "completed" for run in relevant_runs)
        ).lower()
        updated["rating_x_type"] = (
            f"{step['prm_rating']} x {step['step_type_analysis'].lower()}"
        )
        updated["eligibility_group"] = (
            "eligible" if as_bool(step["placebo_eligible"]) else "skipped"
        )
        audit_steps.append(updated)

    selected_columns = [
        "step_id",
        "problem_id",
        "prm_rating",
        "step_type_analysis",
        "step_type_human_calibrated",
        "rating_x_type",
        "position_bin",
        "target_tokens",
        "prefix_tokens",
        "control_correct_count",
        "target_correct_count",
        "control_avg_correct",
        "target_avg_correct",
        "target_effect",
        "correct_to_wrong_count",
        "wrong_to_correct_count",
        "danger_rate",
        "recovery_rate",
        "mean_target_minus_control_tokens",
        "completion_fraction",
        "has_abnormal_completion",
        "placebo_eligible",
        "placebo_run_count",
        "eligibility_group",
    ]
    write_csv(
        ROOT / "placebo_eligibility_step_table.csv",
        audit_steps,
        fieldnames=selected_columns,
    )
    eligible = [step for step in audit_steps if step["eligibility_group"] == "eligible"]
    skipped = [step for step in audit_steps if step["eligibility_group"] == "skipped"]

    balance_rows: list[dict] = []
    for variable_index, (column, label) in enumerate(CONTINUOUS):
        left = [as_float(step[column]) for step in eligible]
        right = [as_float(step[column]) for step in skipped]
        smd = pooled_smd(left, right)
        ks = ks_statistic(left, right)
        clean_left = [value for value in left if not math.isnan(value)]
        clean_right = [value for value in right if not math.isnan(value)]
        combined = clean_left + clean_right
        p_value = permutation_pvalue(
            combined,
            len(clean_left),
            lambda first, second: mean(first) - mean(second),
            BOOTSTRAP_REPLICATES,
            SEED + 100 + variable_index,
        )
        balance_rows.append(
            {
                "variable": column,
                "variable_label": label,
                "variable_type": "continuous",
                "level": "",
                "eligible_summary": describe(left),
                "skipped_summary": describe(right),
                "difference": fmt(mean(clean_left) - mean(clean_right), 6),
                "standardized_difference_or_distance": fmt(smd, 6),
                "ks_or_chi_square": fmt(ks, 6),
                "permutation_p": fmt(p_value, 6),
                "eligible_n": len(clean_left),
                "skipped_n": len(clean_right),
            }
        )

    for variable_index, (column, label) in enumerate(CATEGORICAL):
        left = [step[column] for step in eligible]
        right = [step[column] for step in skipped]
        chi_square = chi_square_statistic(left, right)
        combined = left + right
        p_value = permutation_pvalue(
            combined,
            len(left),
            chi_square_statistic,
            BOOTSTRAP_REPLICATES,
            SEED + 500 + variable_index,
        )
        for level in sorted(set(combined)):
            left_count = left.count(level)
            right_count = right.count(level)
            balance_rows.append(
                {
                    "variable": column,
                    "variable_label": label,
                    "variable_type": "categorical",
                    "level": level,
                    "eligible_summary": f"{left_count}/{len(left)} ({left_count/len(left):.4f})",
                    "skipped_summary": f"{right_count}/{len(right)} ({right_count/len(right):.4f})",
                    "difference": fmt(left_count / len(left) - right_count / len(right), 6),
                    "standardized_difference_or_distance": fmt(
                        binary_smd(left_count, len(left), right_count, len(right)), 6
                    ),
                    "ks_or_chi_square": fmt(chi_square, 6),
                    "permutation_p": fmt(p_value, 6),
                    "eligible_n": len(left),
                    "skipped_n": len(right),
                }
            )
    write_csv(ROOT / "placebo_eligibility_balance.csv", balance_rows)

    def mean_field(column: str):
        return lambda members: mean(as_float(step[column]) for step in members)

    def control_accuracy(members: list[dict]) -> float:
        return sum(as_int(step["control_correct_count"]) for step in members) / (
            4 * len(members)
        )

    def target_accuracy(members: list[dict]) -> float:
        return sum(as_int(step["target_correct_count"]) for step in members) / (
            4 * len(members)
        )

    def harm_rate(members: list[dict]) -> float:
        denominator = sum(as_int(step["control_correct_count"]) for step in members)
        return (
            sum(as_int(step["correct_to_wrong_count"]) for step in members) / denominator
            if denominator
            else math.nan
        )

    def recovery_rate(members: list[dict]) -> float:
        denominator = sum(4 - as_int(step["control_correct_count"]) for step in members)
        return (
            sum(as_int(step["wrong_to_correct_count"]) for step in members) / denominator
            if denominator
            else math.nan
        )

    effect_specs = [
        ("control_accuracy", control_accuracy),
        ("target_accuracy", target_accuracy),
        ("raw_target_effect", mean_field("target_effect")),
        ("harm_rate", harm_rate),
        ("recovery_rate", recovery_rate),
        ("mean_token_change", mean_field("mean_target_minus_control_tokens")),
        ("completion_fraction", mean_field("completion_fraction")),
    ]
    effect_rows = []
    for index, (metric, statistic) in enumerate(effect_specs):
        estimate, lower, upper = bootstrap_group_difference(
            eligible,
            skipped,
            statistic,
            BOOTSTRAP_REPLICATES,
            SEED + 900 + index,
        )
        effect_rows.append(
            {
                "metric": metric,
                "eligible_estimate": fmt(statistic(eligible), 6),
                "skipped_estimate": fmt(statistic(skipped), 6),
                "eligible_minus_skipped": fmt(estimate, 6),
                "ci_lower": fmt(lower, 6),
                "ci_upper": fmt(upper, 6),
                "eligible_steps": len(eligible),
                "skipped_steps": len(skipped),
                "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            }
        )
    write_csv(ROOT / "placebo_eligibility_effect_differences.csv", effect_rows)
    loveplot(balance_rows, ROOT / "placebo_eligibility_loveplot.svg")

    max_smd_by_variable: dict[str, float] = {}
    for row in balance_rows:
        value = abs(as_float(row["standardized_difference_or_distance"]))
        if not math.isnan(value) and not math.isinf(value):
            max_smd_by_variable[row["variable_label"]] = max(
                max_smd_by_variable.get(row["variable_label"], 0.0), value
            )
    largest = sorted(max_smd_by_variable.items(), key=lambda item: item[1], reverse=True)
    raw_row = next(row for row in effect_rows if row["metric"] == "raw_target_effect")
    strict_limit = (
        any(value >= 0.25 for _, value in largest)
        or abs(as_float(raw_row["eligible_minus_skipped"])) >= 0.05
    )
    lines = [
        "# Placebo Eligibility and Selection-Bias Audit",
        "",
        f"- Eligible: **{len(eligible)}** steps",
        f"- Skipped: **{len(skipped)}** steps",
        f"- Balance threshold: absolute SMD ≥ 0.25",
        f"- Effect-difference threshold: absolute raw-effect difference ≥ 5 pp",
        f"- Resampling/permutation replicates: **{BOOTSTRAP_REPLICATES}**",
        "",
        "## Largest balance differences",
        "",
        "| Variable | Maximum absolute SMD |",
        "|---|---:|",
    ]
    for label, value in largest[:10]:
        lines.append(f"| {label} | {value:.3f} |")
    lines += [
        "",
        "## Outcome differences: eligible minus skipped",
        "",
        "| Metric | Eligible | Skipped | Difference | 95% CI |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in effect_rows:
        scale = 100 if row["metric"] != "mean_token_change" else 1
        suffix = " pp" if scale == 100 else " tokens"
        lines.append(
            f"| {row['metric']} | {as_float(row['eligible_estimate'])*scale:.2f} | "
            f"{as_float(row['skipped_estimate'])*scale:.2f} | "
            f"{as_float(row['eligible_minus_skipped'])*scale:+.2f}{suffix} | "
            f"[{as_float(row['ci_lower'])*scale:+.2f}, "
            f"{as_float(row['ci_upper'])*scale:+.2f}] |"
        )
    lines += [
        "",
        "## Decision",
        "",
        (
            "**Placebo conclusions must remain explicitly restricted to the 511-step "
            "matched cohort.** At least one pre-specified balance/effect threshold was crossed."
            if strict_limit
            else "The matched cohort is broadly similar under the pre-specified thresholds, "
            "but the 511/600 coverage limitation must still be reported."
        ),
        "",
        "This audit cannot impute unobserved placebo outcomes for the 89 skipped steps.",
        "",
    ]
    (ROOT / "placebo_eligibility_audit.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
