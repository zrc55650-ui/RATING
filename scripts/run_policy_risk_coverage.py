#!/usr/bin/env python3
"""Workstream M7: selective deletion policy risk-coverage baselines.

Compares fixed deletion policies on the frozen 600-step cohort:
random / rating threshold / harmful-only / rating x harmful /
static predictor / trajectory-state predictor / oracle upper bound.

Inputs: master_step_table.csv, predictive_analysis/predictive_predictions.csv.
Outputs under workstream_M7_policy_risk_coverage/. Stdlib only.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from analysis_common import (
    ROOT,
    SEED,
    as_float,
    as_int,
    fmt,
    fmt_pp,
    read_csv,
    stable_hash,
    write_csv,
    write_svg,
)

OUT_DIR = ROOT / "workstream_M7_policy_risk_coverage"
RUNS_PER_STEP = 4
BOOTSTRAP_REPLICATES = 5000
HARM_BUDGETS = [0.01, 0.03, 0.05]
FIXED_COVERAGES = [0.05, 0.10, 1.0 / 3.0, 0.50]


def load_steps() -> list[dict]:
    steps = []
    for row in read_csv(ROOT / "data" / "master_step_table.csv"):
        steps.append(
            {
                "step_id": row["step_id"],
                "rating": as_int(row["prm_rating"]),
                "type_hc": row["step_type_human_calibrated"].strip().lower(),
                "delta": as_float(row["target_effect"]),
                "c2w": as_int(row["correct_to_wrong_count"]),
                "w2c": as_int(row["wrong_to_correct_count"]),
                "control_correct": as_int(row["control_correct_count"]),
            }
        )
    return steps


def load_predictor_scores(models: tuple[str, ...] = ("D", "E")) -> dict[str, dict[str, dict[str, float]]]:
    """step_id -> model -> {danger, benefit} out-of-fold probabilities.

    Danger predictions exist only for steps with >=1 control-correct run and
    benefit predictions only for steps with >=1 control-wrong run. Prediction
    availability therefore encodes control-run state: a static deployable
    policy must not exploit it, so model D imputes missing values with the
    task base rate (no information). Model E is the explicitly state-aware
    policy, where imputing the factually exact 0.0 is allowed.
    """
    scores: dict[str, dict[str, dict[str, float]]] = {}
    for row in read_csv(ROOT / "predictive_analysis" / "predictive_predictions.csv"):
        model = row["model"]
        if model not in models:
            continue
        step = scores.setdefault(row["step_id"], {})
        entry = step.setdefault(model, {})
        entry.setdefault(row["task"], as_float(row["predicted_probability"]))
    return scores


def ranked_order(steps: list[dict], tier_of, score_of=None) -> list[int]:
    """Sort step indices by (tier, -score, stable hash) for deterministic curves."""

    def sort_key(index: int):
        step = steps[index]
        score = -score_of(step) if score_of else 0.0
        return (tier_of(step), score, stable_hash(step["step_id"]))

    return sorted(range(len(steps)), key=sort_key)


def curve_points(steps: list[dict], order: list[int], grid: list[int]) -> list[dict]:
    total = len(steps)
    points = []
    cum_delta = 0.0
    cum_c2w = 0
    cum_w2c = 0
    cum_correct_runs = 0
    cum_step_danger = 0
    position = 0
    for k in grid:
        while position < k:
            step = steps[order[position]]
            cum_delta += step["delta"]
            cum_c2w += step["c2w"]
            cum_w2c += step["w2c"]
            cum_correct_runs += step["control_correct"]
            cum_step_danger += 1 if step["c2w"] > 0 else 0
            position += 1
        deleted_runs = k * RUNS_PER_STEP
        points.append(
            {
                "n_steps": k,
                "coverage": k / total,
                "net_accuracy_change_pp": 100.0 * cum_delta / total,
                "avg_selected_effect_pp": 100.0 * cum_delta / k if k else math.nan,
                "run_danger_rate": cum_c2w / deleted_runs if k else math.nan,
                "danger_rate_among_correct": (
                    cum_c2w / cum_correct_runs if cum_correct_runs else 0.0
                ),
                "run_benefit_rate": cum_w2c / deleted_runs if k else math.nan,
                "step_danger_rate": cum_step_danger / k if k else math.nan,
            }
        )
    return points


def random_policy_points(steps: list[dict], grid: list[int]) -> list[dict]:
    """Analytic expectation over uniformly random step selection."""
    total = len(steps)
    mean_delta = sum(s["delta"] for s in steps) / total
    overall_danger = sum(s["c2w"] for s in steps) / (total * RUNS_PER_STEP)
    overall_benefit = sum(s["w2c"] for s in steps) / (total * RUNS_PER_STEP)
    overall_correct = sum(s["control_correct"] for s in steps)
    danger_among_correct = sum(s["c2w"] for s in steps) / overall_correct
    step_danger = sum(1 for s in steps if s["c2w"] > 0) / total
    points = []
    for k in grid:
        points.append(
            {
                "n_steps": k,
                "coverage": k / total,
                "net_accuracy_change_pp": 100.0 * mean_delta * k / total,
                "avg_selected_effect_pp": 100.0 * mean_delta,
                "run_danger_rate": overall_danger,
                "danger_rate_among_correct": danger_among_correct,
                "run_benefit_rate": overall_benefit,
                "step_danger_rate": step_danger,
            }
        )
    return points


def bootstrap_net_change(steps: list[dict], selected_ids: set[str]) -> tuple[float, float]:
    """Cluster bootstrap (step level) CI for cohort net accuracy change in pp."""
    rng = random.Random(SEED)
    total = len(steps)
    deltas = [s["delta"] if s["step_id"] in selected_ids else 0.0 for s in steps]
    draws = []
    for _ in range(BOOTSTRAP_REPLICATES):
        draw = sum(deltas[rng.randrange(total)] for _ in range(total)) / total
        draws.append(100.0 * draw)
    draws.sort()
    lower = draws[int(0.025 * (BOOTSTRAP_REPLICATES - 1))]
    upper = draws[int(0.975 * (BOOTSTRAP_REPLICATES - 1))]
    return lower, upper


def harm_budget_row(policy: str, points: list[dict], budget: float) -> dict:
    feasible = [p for p in points if p["run_danger_rate"] <= budget + 1e-12]
    best = max(feasible, key=lambda p: p["n_steps"], default=None)
    return {
        "policy": policy,
        "harm_budget": budget,
        "max_steps_deletable": best["n_steps"] if best else 0,
        "coverage": fmt(best["coverage"], 4) if best else "0",
        "net_accuracy_change_pp": fmt(best["net_accuracy_change_pp"], 3) if best else "",
        "run_danger_rate": fmt(best["run_danger_rate"], 4) if best else "",
        "run_benefit_rate": fmt(best["run_benefit_rate"], 4) if best else "",
    }


def line_chart(
    path: Path,
    title: str,
    series: list[tuple[str, str, list[tuple[float, float]]]],
    y_label: str,
    y_min: float,
    y_max: float,
    reference_lines: list[tuple[float, str]] | None = None,
) -> None:
    width, height = 860, 520
    left, right, top, bottom = 90, 260, 70, 60
    plot_w = width - left - right
    plot_h = height - top - bottom

    def sx(x: float) -> float:
        return left + x * plot_w

    def sy(y: float) -> float:
        return top + (y_max - y) / (y_max - y_min) * plot_h

    body = [f'<text x="{left}" y="36" class="title">{title}</text>']
    for tick in range(0, 11, 2):
        x = sx(tick / 10)
        body.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + plot_h}" class="grid"/>')
        body.append(
            f'<text x="{x}" y="{top + plot_h + 22}" class="small" text-anchor="middle">{tick * 10}%</text>'
        )
    ticks = 6
    for i in range(ticks + 1):
        value = y_min + (y_max - y_min) * i / ticks
        y = sy(value)
        body.append(f'<line x1="{left}" y1="{y}" x2="{left + plot_w}" y2="{y}" class="grid"/>')
        body.append(
            f'<text x="{left - 8}" y="{y + 4}" class="small" text-anchor="end">{value:.1f}</text>'
        )
    for value, label in reference_lines or []:
        y = sy(value)
        body.append(
            f'<line x1="{left}" y1="{y}" x2="{left + plot_w}" y2="{y}" '
            f'stroke="#b02a37" stroke-width="1" stroke-dasharray="6 4"/>'
        )
        body.append(f'<text x="{left + plot_w + 6}" y="{y + 4}" class="small" fill="#b02a37">{label}</text>')
    body.append(
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" class="axis"/>'
    )
    body.append(
        f'<text x="{left + plot_w / 2}" y="{height - 16}" class="label" text-anchor="middle">Deletion coverage (% of 600 steps)</text>'
    )
    body.append(
        f'<text x="24" y="{top + plot_h / 2}" class="label" text-anchor="middle" '
        f'transform="rotate(-90 24 {top + plot_h / 2})">{y_label}</text>'
    )
    legend_y = top + 6
    for name, color, points in series:
        coords = " ".join(
            f"{sx(x):.1f},{sy(min(max(y, y_min), y_max)):.1f}" for x, y in points
        )
        body.append(
            f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.4"/>'
        )
        body.append(
            f'<line x1="{left + plot_w + 14}" y1="{legend_y}" x2="{left + plot_w + 40}" '
            f'y2="{legend_y}" stroke="{color}" stroke-width="3"/>'
        )
        body.append(
            f'<text x="{left + plot_w + 46}" y="{legend_y + 4}" class="small">{name}</text>'
        )
        legend_y += 22
    write_svg(path, width, height, "\n".join(body))


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    steps = load_steps()
    scores = load_predictor_scores()
    total = len(steps)
    grid = sorted(set(list(range(10, total + 1, 10)) + [total]))

    danger_base = sum(s["c2w"] for s in steps) / max(
        1, sum(s["control_correct"] for s in steps)
    )
    benefit_base = sum(s["w2c"] for s in steps) / max(
        1, sum(RUNS_PER_STEP - s["control_correct"] for s in steps)
    )

    def predictor_score(step: dict, model: str) -> float:
        entry = scores.get(step["step_id"], {}).get(model, {})
        if model == "D":
            benefit = entry.get("benefit", benefit_base)
            danger = entry.get("danger", danger_base)
        else:
            benefit = entry.get("benefit", 0.0)
            danger = entry.get("danger", 0.0)
        return benefit - danger

    policies: dict[str, dict] = {}
    policies["random"] = {
        "label": "Random deletion",
        "color": "#8791a5",
        "points": random_policy_points(steps, grid),
        "natural_k": None,
        "order": None,
    }

    definitions = [
        (
            "rating_neg1",
            "Rating = -1 threshold",
            "#1f77b4",
            lambda s: {-1: 0, 0: 1, 1: 2}[s["rating"]],
            None,
            lambda s: s["rating"] == -1,
        ),
        (
            "harmful_only",
            "Harmful-only (human-calibrated)",
            "#ff7f0e",
            lambda s: 0 if s["type_hc"] == "harmful" else 1,
            None,
            lambda s: s["type_hc"] == "harmful",
        ),
        (
            "neg1_x_harmful",
            "Rating = -1 x Harmful",
            "#2ca02c",
            lambda s: 0
            if (s["rating"] == -1 and s["type_hc"] == "harmful")
            else (1 if (s["rating"] == -1 or s["type_hc"] == "harmful") else 2),
            None,
            lambda s: s["rating"] == -1 and s["type_hc"] == "harmful",
        ),
        (
            "predictor_static",
            "Static predictor (model D)",
            "#9467bd",
            lambda s: 0,
            lambda s: predictor_score(s, "D"),
            None,
        ),
        (
            "predictor_state",
            "Trajectory-state predictor (model E)",
            "#17becf",
            lambda s: 0,
            lambda s: predictor_score(s, "E"),
            None,
        ),
        (
            "oracle",
            "Oracle upper bound (observed effect)",
            "#d62728",
            lambda s: 0,
            lambda s: s["delta"],
            None,
        ),
    ]

    for key, label, color, tier_of, score_of, natural in definitions:
        order = ranked_order(steps, tier_of, score_of)
        natural_k = sum(1 for s in steps if natural(s)) if natural else None
        local_grid = sorted(set(grid + ([natural_k] if natural_k else [])))
        policies[key] = {
            "label": label,
            "color": color,
            "points": curve_points(steps, order, local_grid),
            "natural_k": natural_k,
            "order": order,
        }

    curve_rows = []
    for key, policy in policies.items():
        for point in policy["points"]:
            curve_rows.append(
                {
                    "policy": key,
                    "policy_label": policy["label"],
                    **{
                        field: (fmt(value, 4) if isinstance(value, float) else value)
                        for field, value in point.items()
                    },
                }
            )
    write_csv(OUT_DIR / "policy_risk_coverage_curves.csv", curve_rows)

    operating_rows = []
    for key, policy in policies.items():
        targets = []
        if policy["natural_k"]:
            targets.append(("natural_set", policy["natural_k"]))
        for coverage in FIXED_COVERAGES:
            targets.append((f"coverage_{coverage:.2f}", round(coverage * total)))
        for tag, k in targets:
            point = next((p for p in policy["points"] if p["n_steps"] == k), None)
            if point is None:
                continue
            row = {
                "policy": key,
                "policy_label": policy["label"],
                "operating_point": tag,
                **{
                    field: (fmt(value, 4) if isinstance(value, float) else value)
                    for field, value in point.items()
                },
            }
            if policy["order"] is not None:
                selected = {steps[i]["step_id"] for i in policy["order"][:k]}
                lower, upper = bootstrap_net_change(steps, selected)
                row["net_change_ci_lower_pp"] = fmt(lower, 3)
                row["net_change_ci_upper_pp"] = fmt(upper, 3)
            operating_rows.append(row)
    write_csv(OUT_DIR / "policy_operating_points.csv", operating_rows)

    budget_rows = []
    for key, policy in policies.items():
        for budget in HARM_BUDGETS:
            budget_rows.append(harm_budget_row(key, policy["points"], budget))
    write_csv(OUT_DIR / "policy_harm_budget.csv", budget_rows)

    chart_series_danger = [
        (policy["label"], policy["color"], [(p["coverage"], 100.0 * p["run_danger_rate"]) for p in policy["points"]])
        for key, policy in policies.items()
    ]
    line_chart(
        OUT_DIR / "policy_risk_coverage_danger.svg",
        "Dangerous deletion rate vs coverage by policy",
        chart_series_danger,
        "Correct-to-wrong rate per deleted run (%)",
        0.0,
        20.0,
        reference_lines=[(1.0, "1% budget"), (3.0, "3% budget"), (5.0, "5% budget")],
    )
    chart_series_net = [
        (policy["label"], policy["color"], [(p["coverage"], p["net_accuracy_change_pp"]) for p in policy["points"]])
        for key, policy in policies.items()
    ]
    line_chart(
        OUT_DIR / "policy_net_accuracy.svg",
        "Cohort net accuracy change vs coverage by policy",
        chart_series_net,
        "Net accuracy change (pp, cohort of 600)",
        -2.0,
        16.0,
    )

    summary = {
        "cohort_steps": total,
        "runs_per_step": RUNS_PER_STEP,
        "overall_run_danger_rate": sum(s["c2w"] for s in steps) / (total * RUNS_PER_STEP),
        "overall_run_benefit_rate": sum(s["w2c"] for s in steps) / (total * RUNS_PER_STEP),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "seed": SEED,
        "policies": {key: policy["label"] for key, policy in policies.items()},
        "natural_set_sizes": {
            key: policy["natural_k"] for key, policy in policies.items() if policy["natural_k"]
        },
    }
    (OUT_DIR / "policy_risk_coverage_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    write_report(policies, budget_rows, operating_rows, summary)
    print("Workstream M7 policy risk-coverage generated:", OUT_DIR)


def write_report(policies, budget_rows, operating_rows, summary) -> None:
    lines = [
        "# Workstream M7:Selective Deletion Policy Risk-Coverage Baseline",
        "",
        "基于冻结的 600-step / 2,400-pair 主表离线评估固定删除策略。",
        "danger 定义为 run-level Control Correct -> Target Wrong(每次删除动作的伤害率,",
        "分母为被删 step 的全部 4 个 paired runs);net accuracy change 以 600-step 全 cohort 为分母。",
        "预测器分数为 5-fold problem-level CV 的 out-of-fold 概率(model D = static context,",
        "model E = trajectory state),排序分数为 P(benefit) - P(danger)。",
        "model D 对无预测的 step(预测可得性本身编码 control 状态)以任务基率填补,",
        "避免 static 策略泄漏 state 信息;model E 为显式 state-aware 策略,按事实填 0。",
        "CI 为 step-level cluster bootstrap(5,000 次)。",
        "",
        "## 策略自然工作点(natural set 或固定 coverage)",
        "",
        "| Policy | Operating point | Steps | Coverage | Net Δacc (pp) | 95% CI | Danger/run | Benefit/run |",
        "|---|---|---:|---:|---:|---|---:|---:|",
    ]
    for row in operating_rows:
        if row["operating_point"] not in {"natural_set", "coverage_0.33"}:
            continue
        ci = (
            f"[{row.get('net_change_ci_lower_pp', '')}, {row.get('net_change_ci_upper_pp', '')}]"
            if row.get("net_change_ci_lower_pp")
            else "analytic"
        )
        lines.append(
            f"| {row['policy_label']} | {row['operating_point']} | {row['n_steps']} "
            f"| {row['coverage']} | {row['net_accuracy_change_pp']} | {ci} "
            f"| {row['run_danger_rate']} | {row['run_benefit_rate']} |"
        )
    lines += [
        "",
        "## 固定 harm budget 下的可删除量",
        "",
        "| Policy | Budget | Max steps | Coverage | Net Δacc (pp) | Danger/run |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in budget_rows:
        label = policies[row["policy"]]["label"]
        lines.append(
            f"| {label} | {row['harm_budget']:.0%} | {row['max_steps_deletable']} "
            f"| {row['coverage']} | {row['net_accuracy_change_pp']} | {row['run_danger_rate']} |"
        )
    lines += [
        "",
        "## 输出文件",
        "",
        "- `policy_risk_coverage_curves.csv`:全部策略 x coverage 网格曲线数据;",
        "- `policy_operating_points.csv`:自然工作点与固定 coverage 点(含 bootstrap CI);",
        "- `policy_harm_budget.csv`:1%/3%/5% harm budget 下的最大可删除量;",
        "- `policy_risk_coverage_danger.svg` / `policy_net_accuracy.svg`:主图;",
        "- `policy_risk_coverage_summary.json`:参数与自然集合大小。",
        "",
        "## 解读边界",
        "",
        "- 本分析复用已冻结 runs,是 retrospective 评价,不涉及新生成;",
        "- danger 率分母为删除动作(4 runs/step);以 control-correct runs 为分母的伤害率见",
        "  `danger_rate_among_correct` 列,数值更高,结论方向一致;",
        "- oracle 曲线使用观测效应排序,是不可部署的上界;",
        "- random 策略为解析期望,无抽样 CI。",
    ]
    (OUT_DIR / "policy_risk_coverage_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
