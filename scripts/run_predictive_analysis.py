#!/usr/bin/env python3
"""Grouped-CV prediction of dangerous and beneficial target deletion outcomes."""

from __future__ import annotations

import math
from pathlib import Path

from analysis_common import (
    BOOTSTRAP_REPLICATES,
    ROOT,
    SEED,
    as_float,
    as_int,
    fit_logistic_irls,
    fold_bootstrap_interval,
    fmt,
    grouped_fold_assignment,
    mean,
    metric_bundle,
    predict_logistic,
    read_csv,
    write_csv,
    write_svg,
    xml_escape,
)


MODEL_LABELS = {
    "A": "Rating-only",
    "B": "Type-only",
    "C": "Rating + Type",
    "D": "Static context",
    "E": "Trajectory state (oracle/extra-compute)",
}


def feature_vector(model: str, step: dict[str, str]) -> tuple[list[str], list[float]]:
    rating = as_int(step["prm_rating"])
    step_type = step["step_type_analysis"].lower()
    position = step["position_bin"].lower()
    rating_features = [float(rating == 0), float(rating == 1)]
    type_features = [float(step_type == "redundant"), float(step_type == "harmful")]

    names: list[str] = []
    values: list[float] = []
    if model in {"A", "C", "D", "E"}:
        names += ["rating_0", "rating_1"]
        values += rating_features
    if model in {"B", "C", "D", "E"}:
        names += ["type_redundant", "type_harmful"]
        values += type_features
    if model in {"C", "D", "E"}:
        names += [
            "rating0_x_redundant",
            "rating0_x_harmful",
            "rating1_x_redundant",
            "rating1_x_harmful",
        ]
        values += [
            rating_features[0] * type_features[0],
            rating_features[0] * type_features[1],
            rating_features[1] * type_features[0],
            rating_features[1] * type_features[1],
        ]
    if model in {"D", "E"}:
        names += ["position_middle", "position_late", "log_target_tokens", "log_prefix_tokens"]
        values += [
            float(position == "middle"),
            float(position == "late"),
            math.log1p(as_float(step["target_tokens"], 0.0)),
            math.log1p(as_float(step["prefix_tokens"], 0.0)),
        ]
    if model == "E":
        names += ["control_correct_frequency"]
        values += [as_int(step["control_correct_count"]) / 4.0]
    return names, values


def standardize(
    train: list[list[float]],
    test: list[list[float]],
    feature_names: list[str],
) -> tuple[list[list[float]], list[list[float]]]:
    continuous = {
        index
        for index, name in enumerate(feature_names)
        if name.startswith("log_") or name == "control_correct_frequency"
    }
    if not continuous:
        return train, test
    centers: dict[int, float] = {}
    scales: dict[int, float] = {}
    for index in continuous:
        column = [row[index] for row in train]
        center = mean(column)
        variance = mean((value - center) ** 2 for value in column)
        centers[index] = center
        scales[index] = math.sqrt(variance) if variance > 1e-12 else 1.0

    def transform(rows: list[list[float]]) -> list[list[float]]:
        result = []
        for row in rows:
            updated = list(row)
            for index in continuous:
                updated[index] = (updated[index] - centers[index]) / scales[index]
            result.append(updated)
        return result

    return transform(train), transform(test)


def build_dataset() -> tuple[list[dict], dict[str, dict[str, str]]]:
    steps = read_csv(ROOT / "data" / "master_step_table.csv")
    step_lookup = {step["step_id"]: step for step in steps}
    runs = read_csv(ROOT / "data" / "master_run_table.csv")
    controls = {
        (run["step_id"], run["run_id"]): run
        for run in runs
        if run["condition"] == "control"
    }
    targets = [
        run for run in runs if run["condition"] == "target_delete"
    ]
    rows: list[dict] = []
    for target in targets:
        key = (target["step_id"], target["run_id"])
        control = controls[key]
        step = step_lookup[target["step_id"]]
        control_correct = as_int(control["judge_label"])
        target_correct = as_int(target["judge_label"])
        rows.append(
            {
                "step_id": target["step_id"],
                "problem_id": target["problem_id"],
                "run_id": target["run_id"],
                "pair_id": target["pair_id"],
                "fold": "",
                "prm_rating": step["prm_rating"],
                "step_type_analysis": step["step_type_analysis"],
                "position_bin": step["position_bin"],
                "target_tokens": step["target_tokens"],
                "prefix_tokens": step["prefix_tokens"],
                "control_correct_frequency": step["control_correct_frequency"],
                "control_correct": control_correct,
                "target_correct": target_correct,
                "danger_outcome": int(control_correct == 1 and target_correct == 0),
                "benefit_outcome": int(control_correct == 0 and target_correct == 1),
            }
        )
    return rows, step_lookup


def risk_coverage_rows(
    task: str,
    model: str,
    outcomes: list[int],
    scores: list[float],
) -> list[dict]:
    if task == "danger":
        order = sorted(range(len(scores)), key=lambda index: (scores[index], index))
        measure_name = "observed_danger_rate"
    else:
        order = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
        measure_name = "observed_benefit_precision"
    result = []
    for percentage in range(5, 101, 5):
        count = max(1, round(len(order) * percentage / 100))
        selected = order[:count]
        result.append(
            {
                "task": task,
                "model": model,
                "coverage": percentage / 100,
                measure_name: mean(outcomes[index] for index in selected),
                "selected_runs": count,
            }
        )
    return result


def plot_risk_coverage(task: str, rows: list[dict], output: Path) -> None:
    width, height = 760, 470
    left, right, top, bottom = 80, 30, 60, 70
    plot_width = width - left - right
    plot_height = height - top - bottom
    measure = "observed_danger_rate" if task == "danger" else "observed_benefit_precision"
    title = (
        "Danger risk–coverage (accept lowest predicted risk)"
        if task == "danger"
        else "Benefit precision–coverage (select highest predicted benefit)"
    )
    colors = {"A": "#78849a", "C": "#3569b8", "E": "#d4663d"}
    maximum = max(float(row.get(measure, 0.0) or 0.0) for row in rows)
    y_max = max(0.1, math.ceil(maximum * 10) / 10)
    pieces = [f'<text x="{left}" y="32" class="title">{xml_escape(title)}</text>']
    for tick in range(6):
        y_value = y_max * tick / 5
        y = top + plot_height - plot_height * tick / 5
        pieces.append(f'<line x1="{left}" y1="{y}" x2="{left+plot_width}" y2="{y}" class="grid"/>')
        pieces.append(f'<text x="{left-10}" y="{y+4}" text-anchor="end" class="small">{y_value:.2f}</text>')
    for tick in range(6):
        x_value = tick / 5
        x = left + plot_width * tick / 5
        pieces.append(f'<text x="{x}" y="{top+plot_height+24}" text-anchor="middle" class="small">{x_value:.1f}</text>')
    pieces += [
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" class="axis"/>',
        f'<line x1="{left}" y1="{top+plot_height}" x2="{left+plot_width}" y2="{top+plot_height}" class="axis"/>',
        f'<text x="{left+plot_width/2}" y="{height-20}" text-anchor="middle" class="label">Coverage</text>',
    ]
    grouped = {
        model: [row for row in rows if row["model"] == model]
        for model in ("A", "C", "E")
    }
    for legend_index, model in enumerate(("A", "C", "E")):
        points = []
        for row in grouped[model]:
            x = left + plot_width * float(row["coverage"])
            y = top + plot_height * (1 - float(row[measure]) / y_max)
            points.append(f"{x:.1f},{y:.1f}")
        pieces.append(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{colors[model]}" '
            'stroke-width="3"/>'
        )
        legend_x = left + 370 + legend_index * 92
        pieces.append(
            f'<line x1="{legend_x}" y1="31" x2="{legend_x+20}" y2="31" '
            f'stroke="{colors[model]}" stroke-width="3"/>'
        )
        pieces.append(
            f'<text x="{legend_x+25}" y="35" class="small">{model}</text>'
        )
    write_svg(output, width, height, "\n".join(pieces))


def main() -> None:
    rows, step_lookup = build_dataset()
    step_rows = list(step_lookup.values())
    group_assignment = grouped_fold_assignment(step_rows, "problem_id", folds=5, seed=SEED)
    for row in rows:
        row["fold"] = group_assignment[row["problem_id"]]

    fold_rows = [
        {
            "step_id": step["step_id"],
            "problem_id": step["problem_id"],
            "fold": group_assignment[step["problem_id"]],
        }
        for step in sorted(step_rows, key=lambda item: as_int(item["display_order"]))
    ]
    write_csv(ROOT / "predictive_analysis" / "predictive_fold_assignments.csv", fold_rows)
    write_csv(ROOT / "predictive_analysis" / "predictive_run_level_dataset.csv", rows)

    task_rows = {
        "danger": [row for row in rows if row["control_correct"] == 1],
        "benefit": [row for row in rows if row["control_correct"] == 0],
    }
    predictions_output: list[dict] = []
    metrics_output: list[dict] = []
    all_fold_metrics: dict[tuple[str, str, str], list[float]] = {}
    all_oof: dict[tuple[str, str], tuple[list[int], list[float]]] = {}

    for task, dataset in task_rows.items():
        outcome_key = f"{task}_outcome"
        for model in MODEL_LABELS:
            oof_by_index: dict[int, float] = {}
            fold_metrics: dict[str, list[float]] = {}
            for fold in range(5):
                train_indices = [
                    index for index, row in enumerate(dataset) if row["fold"] != fold
                ]
                test_indices = [
                    index for index, row in enumerate(dataset) if row["fold"] == fold
                ]
                names, _ = feature_vector(model, step_lookup[dataset[0]["step_id"]])
                x_train = [
                    feature_vector(model, step_lookup[dataset[index]["step_id"]])[1]
                    for index in train_indices
                ]
                x_test = [
                    feature_vector(model, step_lookup[dataset[index]["step_id"]])[1]
                    for index in test_indices
                ]
                x_train, x_test = standardize(x_train, x_test, names)
                y_train = [dataset[index][outcome_key] for index in train_indices]
                y_test = [dataset[index][outcome_key] for index in test_indices]
                coefficients = fit_logistic_irls(x_train, y_train, l2=1.0)
                scores = predict_logistic(coefficients, x_test)
                for index, score in zip(test_indices, scores):
                    oof_by_index[index] = score
                bundle = metric_bundle(y_test, scores)
                for metric, value in bundle.items():
                    fold_metrics.setdefault(metric, []).append(value)
            outcomes = [row[outcome_key] for row in dataset]
            scores = [oof_by_index[index] for index in range(len(dataset))]
            all_oof[(task, model)] = (outcomes, scores)
            for index, (row, outcome, score) in enumerate(zip(dataset, outcomes, scores)):
                predictions_output.append(
                    {
                        "task": task,
                        "model": model,
                        "pair_id": row["pair_id"],
                        "step_id": row["step_id"],
                        "problem_id": row["problem_id"],
                        "run_id": row["run_id"],
                        "fold": row["fold"],
                        "outcome": outcome,
                        "predicted_probability": f"{score:.8f}",
                    }
                )
            for metric, values in fold_metrics.items():
                estimate = mean(values)
                lower, upper = fold_bootstrap_interval(
                    values, BOOTSTRAP_REPLICATES, SEED + stable_metric_offset(task, model, metric)
                )
                all_fold_metrics[(task, model, metric)] = values
                metrics_output.append(
                    {
                        "task": task,
                        "model": model,
                        "model_label": MODEL_LABELS[model],
                        "metric": metric,
                        "estimate": fmt(estimate, 6),
                        "ci_lower": fmt(lower, 6),
                        "ci_upper": fmt(upper, 6),
                        "n_runs": len(dataset),
                        "n_positive": sum(outcomes),
                        "base_rate": fmt(mean(outcomes), 6),
                        "cv_unit": "problem_id",
                        "folds": 5,
                        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
                    }
                )

        for comparison_left, comparison_right in (("C", "A"), ("D", "C"), ("E", "D"), ("E", "A")):
            left_values = all_fold_metrics[(task, comparison_left, "auprc")]
            right_values = all_fold_metrics[(task, comparison_right, "auprc")]
            differences = [left - right for left, right in zip(left_values, right_values)]
            lower, upper = fold_bootstrap_interval(
                differences,
                BOOTSTRAP_REPLICATES,
                SEED + stable_metric_offset(task, comparison_left, comparison_right),
            )
            metrics_output.append(
                {
                    "task": task,
                    "model": f"{comparison_left}-{comparison_right}",
                    "model_label": f"AUPRC delta: {comparison_left} minus {comparison_right}",
                    "metric": "delta_auprc",
                    "estimate": fmt(mean(differences), 6),
                    "ci_lower": fmt(lower, 6),
                    "ci_upper": fmt(upper, 6),
                    "n_runs": len(task_rows[task]),
                    "n_positive": sum(row[f"{task}_outcome"] for row in task_rows[task]),
                    "base_rate": fmt(
                        mean(row[f"{task}_outcome"] for row in task_rows[task]), 6
                    ),
                    "cv_unit": "problem_id",
                    "folds": 5,
                    "bootstrap_replicates": BOOTSTRAP_REPLICATES,
                }
            )

    write_csv(ROOT / "predictive_analysis" / "predictive_predictions.csv", predictions_output)
    write_csv(ROOT / "predictive_analysis" / "predictive_metrics.csv", metrics_output)

    for task in ("danger", "benefit"):
        curve_rows: list[dict] = []
        for model in ("A", "C", "E"):
            outcomes, scores = all_oof[(task, model)]
            curve_rows.extend(risk_coverage_rows(task, model, outcomes, scores))
        write_csv(ROOT / f"risk_coverage_{task}.csv", curve_rows)
        plot_risk_coverage(task, curve_rows, ROOT / f"risk_coverage_{task}.svg")

    metrics_lookup = {
        (row["task"], row["model"], row["metric"]): row for row in metrics_output
    }
    lines = [
        "# Predictive Analysis Report",
        "",
        f"- Seed: `{SEED}`",
        "- Validation: 5-fold grouped cross-validation by `problem_id`.",
        "- Model: L2-regularized logistic regression with fold-local preprocessing.",
        "- Class imbalance: balanced class weights; no SMOTE.",
        "- Confidence intervals: 5,000 paired bootstrap resamples of the five held-out folds.",
        "- Model E uses four-run Control stability and is an oracle/extra-compute upper bound.",
        "",
    ]
    for task in ("danger", "benefit"):
        dataset = task_rows[task]
        outcome_key = f"{task}_outcome"
        lines += [
            f"## {task.title()} deletion",
            "",
            f"Runs: **{len(dataset)}**; positives: **{sum(row[outcome_key] for row in dataset)}** "
            f"({mean(row[outcome_key] for row in dataset)*100:.1f}%).",
            "",
            "| Model | AUROC | AUPRC | Brier | ECE |",
            "|---|---:|---:|---:|---:|",
        ]
        for model in MODEL_LABELS:
            values = []
            for metric in ("auroc", "auprc", "brier", "ece_10bin"):
                row = metrics_lookup[(task, model, metric)]
                values.append(
                    f"{float(row['estimate']):.3f} "
                    f"[{float(row['ci_lower']):.3f}, {float(row['ci_upper']):.3f}]"
                )
            lines.append(f"| {model}: {MODEL_LABELS[model]} | " + " | ".join(values) + " |")
        lines += ["", "AUPRC increments:", ""]
        for comparison in ("C-A", "D-C", "E-D", "E-A"):
            row = metrics_lookup[(task, comparison, "delta_auprc")]
            lines.append(
                f"- {comparison}: {float(row['estimate']):+.3f} "
                f"[{float(row['ci_lower']):+.3f}, {float(row['ci_upper']):+.3f}]"
            )
        c_delta = metrics_lookup[(task, "C-A", "delta_auprc")]
        e_delta = metrics_lookup[(task, "E-A", "delta_auprc")]
        qualifies = (
            float(c_delta["estimate"]) >= 0.03 and float(c_delta["ci_lower"]) > 0
        ) or (
            float(e_delta["estimate"]) >= 0.03 and float(e_delta["ci_lower"]) > 0
        )
        lines += [
            "",
            "Pre-specified inclusion threshold: "
            + ("**met**." if qualifies else "**not met; keep exploratory/appendix only**."),
            "",
        ]
    lines += [
        "## Interpretation boundary",
        "",
        "These are predictive, not causal, comparisons. Model E is not a zero-cost pruning "
        "policy because it uses four Control runs. The final Judge Audit passed the "
        "hard-stop gate with sensitivity qualification; the direct audited-label "
        "substitution check is reported separately and is not a population correction.",
        "",
    ]
    (ROOT / "predictive_analysis" / "predictive_analysis_report.md").write_text("\n".join(lines), encoding="utf-8")


def stable_metric_offset(*parts: str) -> int:
    return sum((index + 1) * sum(ord(char) for char in part) for index, part in enumerate(parts))


if __name__ == "__main__":
    main()
