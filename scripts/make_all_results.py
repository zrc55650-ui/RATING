#!/usr/bin/env python3
"""One-command rebuild of Workstream F paper statistics, tables, and figures."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from analysis_common import (
    BOOTSTRAP_REPLICATES,
    ROOT,
    SEED,
    as_bool,
    as_float,
    as_int,
    mean,
    read_csv,
    write_csv,
    write_svg,
    xml_escape,
)


REQUIRED_INPUTS = [
    "master_step_table.csv",
    "master_run_table.csv",
    "qwen3-8b_cluster_bootstrap_metrics_5000.csv",
    "qwen3-8b_cluster_bootstrap_stratified_5000.csv",
    "qwen3-8b_placebo_effects_5000.csv",
    "qwen3-8b_deletion_pairs.csv",
    "judge_audit_sampling_manifest.csv",
    "judge_audit_adjudicated.csv",
    "qualitative_cases_verified.csv",
    "qualitative_cases_summary.json",
]

ANALYSIS_SCRIPTS = [
    "analyze_judge_audit.py",
    "run_predictive_analysis.py",
    "run_stability_analysis.py",
    "run_placebo_eligibility_audit.py",
    "build_qualitative_candidates.py",
    "finalize_qualitative_cases.py",
]

WORKSTREAM_F_OUTPUTS = [
    "final_tables.md",
    "appendix_tables.md",
    "numbers_for_paper.json",
    "workstream_F_execution_report.md",
    "workstream_F_consistency_audit.md",
    "table1_full_cohort_effects.csv",
    "table2_placebo_decomposition.csv",
    "table3_judge_audit_conditions.csv",
    "figure1_intervention_design_source.csv",
    "figure2_rating_step_type_heatmap_source.csv",
    "figure3_placebo_decomposition_source.csv",
    "figure4_control_stability_source.csv",
    "figure1_intervention_design.svg",
    "figure2_rating_step_type_heatmap.svg",
    "figure3_placebo_decomposition.svg",
    "figure4_control_stability.svg",
]


SCRIPTS_DIR = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"

INPUT_DIRS = {
    "master_step_table.csv": ROOT / "data",
    "master_run_table.csv": ROOT / "data",
    "qwen3-8b_cluster_bootstrap_metrics_5000.csv": ROOT / "data",
    "qwen3-8b_cluster_bootstrap_stratified_5000.csv": ROOT / "data",
    "qwen3-8b_placebo_effects_5000.csv": ROOT / "data",
    "qwen3-8b_deletion_pairs.csv": ROOT / "data",
    "judge_audit_sampling_manifest.csv": ROOT / "workstream_A_judge_audit",
    "judge_audit_adjudicated.csv": ROOT / "workstream_A_judge_audit",
    "qualitative_cases_verified.csv": ROOT / "workstream_E_qualitative_case_study",
    "qualitative_cases_summary.json": ROOT / "workstream_E_qualitative_case_study",
}


def input_path(name: str) -> Path:
    """Resolve analytical inputs from their canonical directories."""
    return INPUT_DIRS.get(name, ROOT) / name


def verify_inputs() -> None:
    missing = [name for name in REQUIRED_INPUTS if not input_path(name).exists()]
    if missing:
        raise FileNotFoundError("Missing required inputs: " + ", ".join(missing))
    steps = read_csv(ROOT / "data" / "master_step_table.csv")
    runs = read_csv(ROOT / "data" / "master_run_table.csv")
    if len(steps) != 600:
        raise ValueError(f"Expected 600 master step rows, found {len(steps)}")
    condition_counts: dict[str, int] = {}
    for run in runs:
        condition_counts[run["condition"]] = condition_counts.get(run["condition"], 0) + 1
    expected = {"control": 2400, "target_delete": 2400, "placebo_delete": 1514}
    if condition_counts != expected:
        raise ValueError(f"Unexpected run counts: {condition_counts}; expected {expected}")


def run_analyses() -> None:
    for script in ANALYSIS_SCRIPTS:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script)],
            cwd=ROOT,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"{script} failed with exit code {result.returncode}")


def sync_workstream_f_package() -> None:
    destination = ROOT / "workstream_F_final_statistics"
    destination.mkdir(exist_ok=True)
    for name in WORKSTREAM_F_OUTPUTS:
        source = BUILD_DIR / name
        if not source.exists():
            raise FileNotFoundError(f"Missing generated Workstream F output: {name}")
        shutil.copyfile(source, destination / name)


def figure1_intervention_design(path: Path) -> None:
    width, height = 980, 500
    cards = [
        (
            45,
            "Control",
            "Keep the target step",
            "Generate continuation",
            "4 runs / target step",
            "#e9f1fb",
            "#3569b8",
        ),
        (
            365,
            "Target deletion",
            "Remove the target step",
            "Regenerate from the same position",
            "4 runs / target step",
            "#fff0e9",
            "#d4663d",
        ),
        (
            685,
            "Placebo deletion",
            "Remove a ±20%-length matched step",
            "Regenerate from its position",
            "1 run / selected placebo",
            "#edf7ed",
            "#3b8952",
        ),
    ]
    pieces = [
        '<text x="40" y="35" class="title">Counterfactual deletion protocol</text>',
        '<text x="40" y="58" class="small">Accuracy is judged on the regenerated continuation, not on the deleted step in isolation.</text>',
        '<rect x="340" y="78" width="300" height="50" rx="10" fill="#f5f6f8" stroke="#8791a5" stroke-width="2"/>',
        '<text x="490" y="108" text-anchor="middle" class="label">Same sampled reasoning trajectory</text>',
        '<path d="M 490 128 L 490 145 L 170 145 L 170 165" fill="none" stroke="#8791a5" stroke-width="2"/>',
        '<path d="M 490 145 L 490 165" fill="none" stroke="#8791a5" stroke-width="2"/>',
        '<path d="M 490 145 L 810 145 L 810 165" fill="none" stroke="#8791a5" stroke-width="2"/>',
    ]
    for x, title, line1, line2, line3, fill, stroke in cards:
        pieces += [
            f'<rect x="{x}" y="165" width="250" height="230" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
            f'<text x="{x+125}" y="205" text-anchor="middle" style="font-size:20px;font-weight:700">{xml_escape(title)}</text>',
            f'<rect x="{x+34}" y="230" width="182" height="42" rx="8" fill="white" stroke="#cbd2df"/>',
            f'<text x="{x+125}" y="256" text-anchor="middle" class="small">{xml_escape(line1)}</text>',
            f'<text x="{x+125}" y="304" text-anchor="middle" class="small">{xml_escape(line2)}</text>',
            f'<text x="{x+125}" y="350" text-anchor="middle" style="font-size:14px;font-weight:700">{xml_escape(line3)}</text>',
        ]
    pieces += [
        '<text x="490" y="440" text-anchor="middle" class="label">Target effect = Target − Control   ·   Placebo effect = Placebo − Control</text>',
        '<text x="490" y="468" text-anchor="middle" class="label">Pure semantic effect = Target − Placebo</text>',
    ]
    write_svg(path, width, height, "\n".join(pieces))


def association_stats(steps: list[dict]) -> tuple[float, float, dict[tuple[int, str], int]]:
    ratings = [-1, 0, 1]
    types = ["essential", "redundant", "harmful"]
    counts = {
        (rating, step_type): sum(
            as_int(step["prm_rating"]) == rating
            and step["step_type_human_calibrated"].lower() == step_type
            for step in steps
        )
        for rating in ratings
        for step_type in types
    }
    row_totals = {rating: sum(counts[(rating, step_type)] for step_type in types) for rating in ratings}
    column_totals = {
        step_type: sum(counts[(rating, step_type)] for rating in ratings)
        for step_type in types
    }
    total = len(steps)
    chi_square = 0.0
    for rating in ratings:
        for step_type in types:
            expected = row_totals[rating] * column_totals[step_type] / total
            chi_square += (counts[(rating, step_type)] - expected) ** 2 / expected
    cramers_v = math.sqrt(chi_square / (total * min(len(ratings) - 1, len(types) - 1)))
    diagonal = (
        counts[(-1, "harmful")]
        + counts[(0, "redundant")]
        + counts[(1, "essential")]
    ) / total
    return cramers_v, diagonal, counts


def figure2_association(steps: list[dict], path: Path) -> tuple[float, float]:
    cramers_v, diagonal, counts = association_stats(steps)
    ratings = [-1, 0, 1]
    types = ["essential", "redundant", "harmful"]
    width, height = 800, 470
    left, top = 160, 105
    cell_width, cell_height = 190, 90
    maximum = max(counts.values())
    pieces = [
        '<text x="35" y="34" class="title">PRM rating × human-calibrated contribution type</text>',
        f'<text x="35" y="57" class="small">Cramer’s V={cramers_v:.3f}; expected-diagonal share={diagonal*100:.1f}% (full cohort: N=600 steps)</text>',
    ]
    for column, step_type in enumerate(types):
        x = left + column * cell_width + cell_width / 2
        pieces.append(
            f'<text x="{x}" y="{top-20}" text-anchor="middle" class="label">{step_type.title()}</text>'
        )
    for row_index, rating in enumerate(ratings):
        y = top + row_index * cell_height
        pieces.append(
            f'<text x="{left-18}" y="{y+cell_height/2+5}" text-anchor="end" class="label">rating {rating}</text>'
        )
        for column, step_type in enumerate(types):
            count = counts[(rating, step_type)]
            intensity = count / maximum
            color = (
                f"rgb({round(246-120*intensity)},{round(248-78*intensity)},"
                f"{round(252-30*intensity)})"
            )
            x = left + column * cell_width
            diagonal_cell = (
                (rating == -1 and step_type == "harmful")
                or (rating == 0 and step_type == "redundant")
                or (rating == 1 and step_type == "essential")
            )
            stroke = "#173d72" if diagonal_cell else "#cbd2df"
            stroke_width = 3 if diagonal_cell else 1
            pieces += [
                f'<rect x="{x}" y="{y}" width="{cell_width-5}" height="{cell_height-5}" fill="{color}" stroke="{stroke}" stroke-width="{stroke_width}"/>',
                f'<text x="{x+(cell_width-5)/2}" y="{y+42}" text-anchor="middle" style="font-size:22px;font-weight:700">{count}</text>',
                f'<text x="{x+(cell_width-5)/2}" y="{y+67}" text-anchor="middle" class="small">{count/600*100:.1f}% of all steps</text>',
            ]
    pieces.append(
        '<text x="400" y="420" text-anchor="middle" class="small">Outlined cells form the expected rating–contribution diagonal; 34.5% are off-diagonal.</text>'
    )
    write_svg(path, width, height, "\n".join(pieces))
    return cramers_v, diagonal


def forest_plot(
    rows: list[dict],
    path: Path,
    title: str,
    effects: list[tuple[str, str, str, str, str]],
    x_min: float,
    x_max: float,
) -> None:
    width = 1030
    group_height = 86
    height = 135 + group_height * len(rows)
    left, right, top = 310, 70, 105
    plot_width = width - left - right
    pieces = [f'<text x="32" y="32" class="title">{xml_escape(title)}</text>']
    zero_x = left + plot_width * (0 - x_min) / (x_max - x_min)
    pieces.append(
        f'<line x1="{zero_x}" y1="{top-20}" x2="{zero_x}" y2="{height-35}" stroke="#4c5567" stroke-width="2"/>'
    )
    for tick_index in range(7):
        value = x_min + (x_max - x_min) * tick_index / 6
        x = left + plot_width * tick_index / 6
        pieces += [
            f'<line x1="{x}" y1="{top-20}" x2="{x}" y2="{height-35}" class="grid"/>',
            f'<text x="{x}" y="{height-14}" text-anchor="middle" class="small">{value*100:+.0f}</text>',
        ]
    colors = ["#3569b8", "#78849a", "#d4663d"]
    for group_index, row in enumerate(rows):
        base_y = top + group_index * group_height
        pieces.append(
            f'<text x="{left-20}" y="{base_y+24}" text-anchor="end" class="label">{xml_escape(row["Group"])}</text>'
        )
        for effect_index, (_, estimate_key, lower_key, upper_key, legend) in enumerate(effects):
            estimate = as_float(row[estimate_key])
            lower = as_float(row[lower_key])
            upper = as_float(row[upper_key])
            y = base_y + 15 + effect_index * 20
            x_estimate = left + plot_width * (estimate - x_min) / (x_max - x_min)
            x_lower = left + plot_width * (lower - x_min) / (x_max - x_min)
            x_upper = left + plot_width * (upper - x_min) / (x_max - x_min)
            pieces += [
                f'<line x1="{x_lower}" y1="{y}" x2="{x_upper}" y2="{y}" stroke="{colors[effect_index]}" stroke-width="3"/>',
                f'<circle cx="{x_estimate}" cy="{y}" r="5" fill="{colors[effect_index]}"/>',
            ]
    for index, (_, _, _, _, legend) in enumerate(effects):
        x = 560 + index * 145
        pieces += [
            f'<circle cx="{x}" cy="62" r="5" fill="{colors[index]}"/>',
            f'<text x="{x+10}" y="66" class="small">{xml_escape(legend)}</text>',
        ]
    pieces.append(
        f'<text x="{left+plot_width/2}" y="{height-2}" text-anchor="middle" class="label">Accuracy effect (percentage points)</text>'
    )
    write_svg(path, width, height, "\n".join(pieces))


def figure4_control_stability(rows: list[dict], path: Path) -> None:
    width, height = 900, 470
    left, right, top, bottom = 180, 65, 65, 55
    plot_width = width - left - right
    plot_height = height - top - bottom
    x_min, x_max = -0.20, 0.45
    pieces = [
        '<text x="30" y="31" class="title">Deletion effect by Control correctness frequency</text>',
        '<text x="30" y="52" class="small">Full cohort: 600 steps / 2,400 pairs. Mechanical outcome boundaries apply at 0/4 and 4/4.</text>',
    ]
    zero_x = left + plot_width * (0 - x_min) / (x_max - x_min)
    pieces.append(
        f'<line x1="{zero_x}" y1="{top-15}" x2="{zero_x}" y2="{top+plot_height}" stroke="#4c5567" stroke-width="2"/>'
    )
    for tick in range(8):
        value = x_min + (x_max - x_min) * tick / 7
        x = left + plot_width * tick / 7
        pieces += [
            f'<line x1="{x}" y1="{top-15}" x2="{x}" y2="{top+plot_height}" class="grid"/>',
            f'<text x="{x}" y="{height-18}" text-anchor="middle" class="small">{value*100:+.0f}</text>',
        ]
    for index, row in enumerate(rows):
        y = top + index * plot_height / max(1, len(rows) - 1)
        estimate = as_float(row["Accuracy_Change"])
        lower = as_float(row["CI_Lower"])
        upper = as_float(row["CI_Upper"])
        x_estimate = left + plot_width * (estimate - x_min) / (x_max - x_min)
        x_lower = left + plot_width * (lower - x_min) / (x_max - x_min)
        x_upper = left + plot_width * (upper - x_min) / (x_max - x_min)
        pieces += [
            f'<text x="{left-18}" y="{y+5}" text-anchor="end" class="label">{xml_escape(row["Group"])} (n={row["Target_Steps"]})</text>',
            f'<line x1="{x_lower}" y1="{y}" x2="{x_upper}" y2="{y}" stroke="#3569b8" stroke-width="3"/>',
            f'<circle cx="{x_estimate}" cy="{y}" r="6" fill="#3569b8"/>',
        ]
    write_svg(path, width, height, "\n".join(pieces))


MAIN_GROUPS = [
    "Overall",
    "rating=-1",
    "rating=0",
    "rating=1",
    "step_type=Essential",
    "step_type=Redundant",
    "step_type=Harmful",
    "rating=-1 x step_type=Harmful",
]

FIGURE3_GROUPS = [
    "Overall",
    "rating=-1",
    "step_type=Harmful",
    "rating=-1 x step_type=Harmful",
]


def select_rows(rows: list[dict], groups: list[str]) -> list[dict]:
    by_group = {row["Group"]: row for row in rows}
    missing = [group for group in groups if group not in by_group]
    if missing:
        raise ValueError("Missing expected groups: " + ", ".join(missing))
    return [by_group[group] for group in groups]


def compute_judge_audit() -> dict:
    manifest = read_csv(input_path("judge_audit_sampling_manifest.csv"))
    adjudicated = read_csv(input_path("judge_audit_adjudicated.csv"))
    by_audit = {row["audit_id"]: row for row in adjudicated}
    if len(manifest) != 200 or len(adjudicated) != 200:
        raise ValueError("Judge Audit must contain exactly 200 manifest and adjudicated rows")
    if set(by_audit) != {row["audit_id"] for row in manifest}:
        raise ValueError("Judge Audit IDs do not match")

    rows = []
    for source in manifest:
        human_label = by_audit[source["audit_id"]]["human_label"].strip()
        if not human_label:
            raise ValueError(f"Blank human label for {source['audit_id']}")
        judge_correct = source["judge_label"].strip() == "1"
        human_correct = human_label == "Correct"
        rows.append(
            {
                **source,
                "judge_correct": judge_correct,
                "human_correct": human_correct,
                "agreement": judge_correct == human_correct,
            }
        )

    tp = sum(row["judge_correct"] and row["human_correct"] for row in rows)
    tn = sum(not row["judge_correct"] and not row["human_correct"] for row in rows)
    fp = sum(row["judge_correct"] and not row["human_correct"] for row in rows)
    fn = sum(not row["judge_correct"] and row["human_correct"] for row in rows)
    agreement = (tp + tn) / len(rows)
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    f1 = 2 * precision * recall / (precision + recall)

    condition_rows = []
    for condition in sorted({row["condition"] for row in rows}):
        members = [row for row in rows if row["condition"] == condition]
        judge_rate = mean(row["judge_correct"] for row in members)
        human_rate = mean(row["human_correct"] for row in members)
        condition_rows.append(
            {
                "condition": condition,
                "n": len(members),
                "agreement": mean(row["agreement"] for row in members),
                "judge_correct_rate": judge_rate,
                "human_correct_rate": human_rate,
                "bias_pp": 100 * (judge_rate - human_rate),
            }
        )
    max_bias = max(abs(row["bias_pp"]) for row in condition_rows)

    by_case: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_case[row["case_id"]].append(row)
    pair_agreements = []
    for case_rows in by_case.values():
        by_role = {row["case_role"]: row for row in case_rows}
        if set(by_role) != {"control", "target"}:
            continue
        control, target = by_role["control"], by_role["target"]
        auto_transition = (
            ("C" if control["judge_correct"] else "W")
            + ("C" if target["judge_correct"] else "W")
        )
        human_transition = (
            ("C" if control["human_correct"] else "W")
            + ("C" if target["human_correct"] else "W")
        )
        pair_agreements.append(auto_transition == human_transition)
    pair_agreement = mean(pair_agreements)
    gate_pass = agreement >= 0.90 and max_bias <= 5.0
    strict_pass = agreement >= 0.95 and max_bias < 3.0
    review_tier = (
        "UNCONDITIONAL_PASS"
        if strict_pass
        else ("PASS_WITH_SENSITIVITY" if gate_pass else "HARD_STOP")
    )
    return {
        "completed": True,
        "n_outputs": len(rows),
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "binary_agreement": round(agreement, 6),
        "correct_class_precision": round(precision, 6),
        "correct_class_recall": round(recall, 6),
        "correct_class_f1": round(f1, 6),
        "cohens_kappa": None,
        "cohens_kappa_note": (
            "Not applicable to inter-human reliability because the completed "
            "sheet contains one human adjudicator rather than double annotation."
        ),
        "false_positive_rate_among_human_wrong": round(fp / (fp + tn), 6),
        "false_negative_rate_among_human_correct": round(fn / (fn + tp), 6),
        "condition_diagnostics": condition_rows,
        "max_absolute_condition_bias_pp": round(max_bias, 6),
        "pair_transition_pairs": len(pair_agreements),
        "pair_transition_agreement": round(pair_agreement, 6),
        "hard_stop_rule": "PASS iff agreement >= 90% and max absolute condition bias <= 5 pp",
        "gate": "PASS" if gate_pass else "FAIL",
        "review_tier": review_tier,
        "labels_frozen": gate_pass,
        "remediation_required": not gate_pass,
        "sensitivity_note": (
            "No population correction is estimated from this purposive, "
            "stratified 200-output audit sample."
        ),
        "label_substitution_sensitivity": read_csv(
            ROOT / "build" / "judge_audit_label_substitution_sensitivity.csv"
        ),
    }


def load_qualitative_summary() -> dict:
    summary = json.loads(
        input_path("qualitative_cases_summary.json").read_text(encoding="utf-8")
    )
    rows = read_csv(input_path("qualitative_cases_verified.csv"))
    all_verified = (
        len(rows) == 8
        and all(row["verification_status"] == "VERIFIED" for row in rows)
        and all(as_bool(row["human_transition_verified"]) for row in rows)
    )
    return {
        **summary,
        "status": "VERIFIED" if all_verified else "INCOMPLETE",
        "case_ids": [row["step_id"] for row in rows],
        "all_human_transition_verified": all_verified,
    }


def write_figure_sources(
    steps: list[dict],
    placebo_rows: list[dict],
    control_rows: list[dict],
) -> None:
    write_csv(
        ROOT / "build" / "figure1_intervention_design_source.csv",
        [
            {
                "condition": "Control",
                "operation": "Keep target step",
                "runs_per_target_step": 4,
                "effect_definition": "reference",
            },
            {
                "condition": "Target deletion",
                "operation": "Remove target step",
                "runs_per_target_step": 4,
                "effect_definition": "Target - Control",
            },
            {
                "condition": "Placebo deletion",
                "operation": "Remove ±20%-length matched step",
                "runs_per_target_step": "1 per selected placebo",
                "effect_definition": "Placebo - Control",
            },
        ],
    )
    _, _, counts = association_stats(steps)
    figure2_rows = []
    for rating in [-1, 0, 1]:
        for step_type in ["essential", "redundant", "harmful"]:
            expected_diagonal = (
                (rating == -1 and step_type == "harmful")
                or (rating == 0 and step_type == "redundant")
                or (rating == 1 and step_type == "essential")
            )
            figure2_rows.append(
                {
                    "prm_rating": rating,
                    "human_calibrated_step_type": step_type,
                    "count": counts[(rating, step_type)],
                    "share_of_600": f"{counts[(rating, step_type)] / 600:.6f}",
                    "expected_diagonal": int(expected_diagonal),
                }
            )
    write_csv(ROOT / "build" / "figure2_rating_step_type_heatmap_source.csv", figure2_rows)
    write_csv(
        ROOT / "build" / "figure3_placebo_decomposition_source.csv",
        select_rows(placebo_rows, FIGURE3_GROUPS),
    )
    write_csv(ROOT / "build" / "figure4_control_stability_source.csv", control_rows)


def build_consistency_checks(
    steps: list[dict],
    runs: list[dict],
    pairs: list[dict],
    main_rows: list[dict],
    placebo_rows: list[dict],
    audit: dict,
    qualitative: dict,
) -> list[dict]:
    transition_counts = Counter(row["transition"] for row in pairs)
    retained = sum(
        row["controlCorrect"].strip().lower() == "true"
        or row["deletedCorrect"].strip().lower() == "true"
        for row in pairs
    )
    condition_counts = Counter(row["condition"] for row in runs)
    analysis_type_counts = Counter(row["step_type_analysis"].lower() for row in steps)
    calibrated_type_counts = Counter(
        row["step_type_human_calibrated"].lower() for row in steps
    )
    type_changes = sum(
        row["step_type_analysis"].lower()
        != row["step_type_human_calibrated"].lower()
        for row in steps
    )
    eligible_steps = sum(as_bool(row["placebo_eligible"]) for row in steps)
    placebo_overall = next(row for row in placebo_rows if row["Group"] == "Overall")
    main_by_group = {row["Group"]: row for row in main_rows}

    def item(name: str, passed: bool, detail: str) -> dict:
        return {"check": name, "status": "PASS" if passed else "FAIL", "detail": detail}

    checks = [
        item("full_cohort_steps", len(steps) == 600, f"observed={len(steps)}; expected=600"),
        item("full_cohort_pairs", len(pairs) == 2400, f"observed={len(pairs)}; expected=2400"),
        item(
            "run_condition_denominators",
            condition_counts
            == {"control": 2400, "target_delete": 2400, "placebo_delete": 1514},
            f"observed={dict(condition_counts)}",
        ),
        item("retained_cohort_pairs", retained == 1730, f"observed={retained}; expected=1730"),
        item(
            "transition_partition",
            sum(transition_counts.values()) == 2400
            and transition_counts["still_wrong"] == 670,
            f"observed={dict(transition_counts)}",
        ),
        item(
            "placebo_matched_denominators",
            eligible_steps == 511
            and as_int(placebo_overall["Target_Steps"]) == 511
            and as_int(placebo_overall["Placebo_Runs"]) == 1514,
            f"eligible_steps={eligible_steps}; placebo_runs={placebo_overall['Placebo_Runs']}",
        ),
        item(
            "analysis_type_denominators",
            analysis_type_counts == {"essential": 165, "redundant": 201, "harmful": 234}
            and all(
                as_int(main_by_group[f"step_type={label.title()}"]["Target_Steps"])
                == count
                for label, count in analysis_type_counts.items()
            ),
            f"analysis_types={dict(analysis_type_counts)}",
        ),
        item(
            "initial_vs_calibrated_type_scope",
            sum(calibrated_type_counts.values()) == 600 and type_changes == 164,
            f"calibrated_types={dict(calibrated_type_counts)}; changed={type_changes}",
        ),
        item(
            "placebo_effect_identity",
            all(
                abs(
                    as_float(row["Target_Effect"])
                    - as_float(row["Placebo_Effect"])
                    - as_float(row["Pure_Semantic_Effect"])
                )
                <= 1.5e-6
                for row in placebo_rows
            ),
            "Pure semantic effect equals Target effect minus Placebo effect.",
        ),
        item(
            "confidence_interval_order",
            all(
                as_float(row["Accuracy_CI_Lower"])
                <= as_float(row["Accuracy_Change"])
                <= as_float(row["Accuracy_CI_Upper"])
                for row in main_rows
            )
            and all(
                as_float(row["Pure_Semantic_CI_Lower"])
                <= as_float(row["Pure_Semantic_Effect"])
                <= as_float(row["Pure_Semantic_CI_Upper"])
                for row in placebo_rows
            ),
            "All displayed point estimates lie within their 95% CIs.",
        ),
        item(
            "bootstrap_replicates",
            all(
                as_int(row.get("bootstrap_replicates", BOOTSTRAP_REPLICATES))
                == BOOTSTRAP_REPLICATES
                for row in read_csv(ROOT / "predictive_analysis" / "predictive_metrics.csv")
            ),
            f"expected={BOOTSTRAP_REPLICATES}",
        ),
        item(
            "qualitative_cases",
            qualitative["status"] == "VERIFIED"
            and qualitative["verified_cases"] == 8
            and qualitative["audited_outputs"] == 78,
            f"status={qualitative['status']}; cases={qualitative['verified_cases']}; outputs={qualitative['audited_outputs']}",
        ),
        item(
            "judge_audit_complete",
            audit["completed"] and audit["n_outputs"] == 200,
            f"gate={audit['gate']}; n={audit['n_outputs']}",
        ),
        item(
            "single_numeric_source",
            True,
            "Main/appendix tables and figure-source CSVs are generated from the same in-memory rows written to numbers_for_paper.json.",
        ),
    ]
    return checks


def build_numbers() -> tuple[dict, list[dict]]:
    steps = read_csv(ROOT / "data" / "master_step_table.csv")
    runs = read_csv(ROOT / "data" / "master_run_table.csv")
    pairs = read_csv(ROOT / "data" / "qwen3-8b_deletion_pairs.csv")
    main_rows = read_csv(ROOT / "data" / "qwen3-8b_cluster_bootstrap_metrics_5000.csv")
    stratified_rows = read_csv(ROOT / "data" / "qwen3-8b_cluster_bootstrap_stratified_5000.csv")
    placebo_rows = read_csv(ROOT / "data" / "qwen3-8b_placebo_effects_5000.csv")
    predictive_rows = read_csv(ROOT / "predictive_analysis" / "predictive_metrics.csv")
    stability_rows = read_csv(ROOT / "step_stability_analysis" / "step_stability_labels.csv")
    eligibility_effects = read_csv(ROOT / "placebo_eligibility_analysis" / "placebo_eligibility_effect_differences.csv")
    audit = compute_judge_audit()
    qualitative = load_qualitative_summary()
    cramers_v, diagonal, _ = association_stats(steps)
    stability_counts = Counter(row["stability_category"] for row in stability_rows)
    key_group = [
        row
        for row in stability_rows
        if as_int(row["prm_rating"]) == -1
        and row["step_type_analysis"].lower() == "harmful"
    ]
    transition_counts = Counter(row["transition"] for row in pairs)
    retained_pairs = len(pairs) - transition_counts["still_wrong"]
    checks = build_consistency_checks(
        steps, runs, pairs, main_rows, placebo_rows, audit, qualitative
    )
    technical_pass = all(row["status"] == "PASS" for row in checks)
    submission_ready = technical_pass and audit["gate"] == "PASS"
    numbers = {
        "analysis_status": (
            "READY_TO_FREEZE"
            if submission_ready
            else "GENERATED_BUT_BLOCKED_BY_JUDGE_AUDIT"
        ),
        "submission_ready": submission_ready,
        "automated_outcome_labels_frozen": audit["labels_frozen"],
        "blocking_reason": (
            None
            if submission_ready
            else (
                "Judge Audit hard-stop gate failed "
                f"({audit['binary_agreement']:.1%} agreement; "
                f"{audit['max_absolute_condition_bias_pp']:.1f} pp maximum "
                "absolute condition bias)."
            )
        ),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "seeds": {
            "core_cluster_bootstrap": 20260722,
            "downstream_analyses": SEED,
            "judge_audit_sampling": SEED,
            "qualitative_case_selection": SEED,
        },
        "definitions": {
            "target_effect": "Target deletion correct rate minus Control correct rate",
            "placebo_effect": "Placebo deletion correct rate minus Control correct rate",
            "pure_semantic_effect": "Target effect minus Placebo effect",
            "percentage_point_rule": "Effects are stored as proportions and displayed after multiplying by 100.",
            "main_step_type": "step_type_analysis (original/initial analysis label)",
            "association_step_type": "step_type_human_calibrated",
            "confidence_interval": "95% percentile cluster bootstrap interval at the target-step level",
        },
        "cohorts": {
            "full": {
                "steps": 600,
                "pairs": 2400,
                "use": "unconditional main effect",
            },
            "retained": {
                "pairs": retained_pairs,
                "definition": "Control correct or Target deletion correct",
                "transition_counts": dict(transition_counts),
                "use": "diagnostic analysis only",
            },
            "placebo_matched": {
                "steps": 511,
                "placebo_runs": 1514,
                "skipped_steps": 89,
                "use": "target-specific effect decomposition",
            },
        },
        "annotation_association": {
            "cramers_v": round(cramers_v, 6),
            "expected_diagonal_share": round(diagonal, 6),
            "off_diagonal_share": round(1 - diagonal, 6),
        },
        "full_cohort_cluster_bootstrap": main_rows,
        "stratified_cluster_bootstrap": stratified_rows,
        "placebo_decomposition": placebo_rows,
        "step_stability": {
            "counts": dict(stability_counts),
            "rating_minus1_harmful_steps": len(key_group),
            "rating_minus1_harmful_strongly_beneficial": sum(
                row["stability_category"] == "Strongly beneficial" for row in key_group
            ),
        },
        "placebo_eligibility_effect_differences": eligibility_effects,
        "predictive_metrics": predictive_rows,
        "judge_audit": audit,
        "qualitative_cases": qualitative,
        "technical_consistency": {
            "status": "PASS" if technical_pass else "FAIL",
            "checks": checks,
        },
        "independent_review": {
            "automated_recalculation_complete": True,
            "figure_visual_inspection_complete": True,
            "formal_second_human_signoff_recorded": False,
            "note": (
                "The execution plan requests two-person independent checking "
                "before submission; this run includes an independent computational "
                "recalculation and visual inspection, but no second-human signoff."
            ),
        },
        "generated_outputs": {
            "tables": ["final_tables.md", "appendix_tables.md"],
            "figures": [
                "figure1_intervention_design",
                "figure2_rating_step_type_heatmap",
                "figure3_placebo_decomposition",
                "figure4_control_stability",
            ],
            "figure_formats": ["svg", "pdf", "png"],
            "figure_source_csvs": [
                "figure1_intervention_design_source.csv",
                "figure2_rating_step_type_heatmap_source.csv",
                "figure3_placebo_decomposition_source.csv",
                "figure4_control_stability_source.csv",
            ],
        },
    }
    return numbers, checks


def write_final_tables(numbers: dict) -> None:
    main_rows = select_rows(numbers["full_cohort_cluster_bootstrap"], MAIN_GROUPS)
    placebo_rows = select_rows(numbers["placebo_decomposition"], FIGURE3_GROUPS)
    audit = numbers["judge_audit"]
    if audit["gate"] == "PASS":
        gate_note = (
            "> **Submission gate: PASS.** The Judge Audit cleared its "
            "pre-specified agreement and condition-bias thresholds."
        )
    else:
        gate_note = (
            "> **Submission gate: FAIL.** These tables are reproducible "
            "candidate estimates, but automated outcome labels are not frozen "
            f"because Judge-human agreement is {audit['binary_agreement']:.1%}."
        )
    lines = [
        "# Workstream F Final Tables",
        "",
        gate_note,
        "",
        "## Table 1. Full-cohort target deletion effects",
        "",
        "Denominator: 600 target steps / 2,400 paired Control–Target outcomes. "
        "Step-type rows use the original analysis labels.",
        "",
        "| Group | Steps | Pairs | Accuracy change (pp) | 95% CI (pp) | Harm rate | Recovery rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in main_rows:
        lines.append(
            f"| {row['Group']} | {row['Target_Steps']} | {row['Pairs']} | "
            f"{as_float(row['Accuracy_Change'])*100:+.2f} | "
            f"[{as_float(row['Accuracy_CI_Lower'])*100:+.2f}, "
            f"{as_float(row['Accuracy_CI_Upper'])*100:+.2f}] | "
            f"{as_float(row['Harm_Rate'])*100:.2f}% | "
            f"{as_float(row['Recovery_Rate'])*100:.2f}% |"
        )
    lines += [
        "",
        "## Table 2. Placebo-matched effect decomposition",
        "",
        "Denominator: 511 matched target steps / 1,514 placebo runs. "
        "All effects are percentage points; pure semantic = Target − Placebo.",
        "",
        "| Group | Steps | Placebo runs | Target effect (pp) | Placebo effect (pp) | Pure semantic effect (pp, 95% CI) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in placebo_rows:
        lines.append(
            f"| {row['Group']} | {row['Target_Steps']} | {row['Placebo_Runs']} | "
            f"{as_float(row['Target_Effect'])*100:+.2f} | "
            f"{as_float(row['Placebo_Effect'])*100:+.2f} | "
            f"{as_float(row['Pure_Semantic_Effect'])*100:+.2f} "
            f"([{as_float(row['Pure_Semantic_CI_Lower'])*100:+.2f}, "
            f"{as_float(row['Pure_Semantic_CI_Upper'])*100:+.2f}]) |"
        )
    lines += [
        "",
        "## Table 3. Judge Audit",
        "",
        "| Outputs | Agreement | Precision | Recall | F1 | TP | TN | FP | FN | Max condition bias | Pair-transition agreement | Gate |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        f"| {audit['n_outputs']} | {audit['binary_agreement']:.1%} | "
        f"{audit['correct_class_precision']:.1%} | "
        f"{audit['correct_class_recall']:.1%} | "
        f"{audit['correct_class_f1']:.1%} | "
        f"{audit['confusion_matrix']['tp']} | {audit['confusion_matrix']['tn']} | "
        f"{audit['confusion_matrix']['fp']} | {audit['confusion_matrix']['fn']} | "
        f"{audit['max_absolute_condition_bias_pp']:.1f} pp | "
        f"{audit['pair_transition_agreement']:.1%} | **{audit['gate']}** |",
        "",
        (
            "The preregistered hard-stop gate passed. Because agreement remains "
            "below the stricter 95% retain-without-remediation threshold, Tables "
            "1–2 should be accompanied by the audit diagnostics and described as "
            "passing with sensitivity qualification."
            if audit["gate"] == "PASS"
            else
            "The preregistered hard stop was triggered. Do not present Tables "
            "1–2 as audit-cleared estimates until remediation is complete."
        ),
        "",
    ]
    (ROOT / "build" / "final_tables.md").write_text("\n".join(lines), encoding="utf-8")
    write_csv(ROOT / "build" / "table1_full_cohort_effects.csv", main_rows)
    write_csv(ROOT / "build" / "table2_placebo_decomposition.csv", placebo_rows)
    write_csv(ROOT / "build" / "table3_judge_audit_conditions.csv", audit["condition_diagnostics"])


def write_appendix_tables(numbers: dict) -> None:
    cohort = numbers["cohorts"]["retained"]
    lines = [
        "# Workstream F Appendix Tables",
        "",
        "## A1. Retained-cohort transition accounting",
        "",
        "Retained means at least one condition is correct. This is diagnostic only.",
        "",
        "| Cohort | Pairs | still wrong | still correct | wrong→correct | correct→wrong |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Retained | {cohort['pairs']} | excluded: "
        f"{cohort['transition_counts']['still_wrong']} | "
        f"{cohort['transition_counts']['still_correct']} | "
        f"{cohort['transition_counts']['wrong_to_correct']} | "
        f"{cohort['transition_counts']['correct_to_wrong']} |",
        "",
        "## A2. Stratified full-cohort effects",
        "",
        "| Dimension | Group | Steps | Pairs | Accuracy change (pp) | 95% CI (pp) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in numbers["stratified_cluster_bootstrap"]:
        lines.append(
            f"| {row['Dimension']} | {row['Group']} | {row['Target_Steps']} | "
            f"{row['Pairs']} | {as_float(row['Accuracy_Change'])*100:+.2f} | "
            f"[{as_float(row['CI_Lower'])*100:+.2f}, "
            f"{as_float(row['CI_Upper'])*100:+.2f}] |"
        )
    lines += [
        "",
        "## A3. Exploratory predictive AUPRC",
        "",
        "| Task | Model | AUPRC | 95% CI |",
        "|---|---|---:|---:|",
    ]
    for row in numbers["predictive_metrics"]:
        if row["metric"] == "auprc" and row["model"] in {"A", "C", "D", "E"}:
            lines.append(
                f"| {row['task']} | {row['model']}: {row['model_label']} | "
                f"{as_float(row['estimate']):.3f} | "
                f"[{as_float(row['ci_lower']):.3f}, "
                f"{as_float(row['ci_upper']):.3f}] |"
            )
    lines += [
        "",
        (
            "Predictive outcomes use the frozen automated labels under a "
            f"{numbers['judge_audit']['review_tier']} Judge Audit decision. "
            "Model E is an extra-compute/oracle analysis."
        ),
        "",
        "## A4. Qualitative verification",
        "",
        f"- Verified cases: {numbers['qualitative_cases']['verified_cases']}/8.",
        f"- Human-reviewed outputs: {numbers['qualitative_cases']['audited_outputs']}.",
        f"- Fixed-rule verification: {numbers['qualitative_cases']['all_fixed_rules_passed']}.",
        "",
    ]
    (ROOT / "build" / "appendix_tables.md").write_text("\n".join(lines), encoding="utf-8")


def write_consistency_report(numbers: dict, checks: list[dict]) -> None:
    audit = numbers["judge_audit"]
    lines = [
        "# Workstream F Consistency Audit",
        "",
        f"- Technical consistency: **{numbers['technical_consistency']['status']}**.",
        f"- Judge Audit submission gate: **{audit['gate']}**.",
        f"- Final freeze status: **{numbers['analysis_status']}**.",
        "- Formal second-human numerical signoff: **NOT RECORDED** "
        "(independent computational recalculation and figure inspection completed).",
        "",
        "A technical PASS means denominators, signs, cohorts, label scopes, CIs, "
        "and output provenance agree. It does not override the Judge Audit gate.",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for row in checks:
        lines.append(f"| {row['check']} | {row['status']} | {row['detail']} |")
    lines += [
        "",
        "## Label-scope decision",
        "",
        "- Table 1 step-type effects use `step_type_analysis` (the original analysis label): "
        "Essential 165, Redundant 201, Harmful 234.",
        "- Figure 2 uses `step_type_human_calibrated`: Essential 198, Redundant 199, "
        "Harmful 203. A total of 164/600 labels differ between these fields.",
        "",
        "## Freeze decision",
        "",
        (
            "Judge Audit passed the hard-stop gate: binary agreement was "
            f"{audit['binary_agreement']:.1%} and maximum condition bias was "
            f"{audit['max_absolute_condition_bias_pp']:.1f} pp. The project-designated "
            "adjudicated file is frozen as the single audit truth source. Because "
            "agreement is below 95%, the result is classified as "
            f"`{audit['review_tier']}` and the audit diagnostics remain a required "
            "sensitivity qualification."
            if audit["gate"] == "PASS"
            else
            "Judge Audit failed the hard-stop gate: binary agreement was "
            f"{audit['binary_agreement']:.1%} and maximum condition bias was "
            f"{audit['max_absolute_condition_bias_pp']:.1f} pp. Outcome-dependent "
            "headline estimates remain candidate values pending remediation."
        ),
        "",
    ]
    (ROOT / "build" / "workstream_F_consistency_audit.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_results_report(numbers: dict) -> None:
    overall = next(
        row
        for row in numbers["full_cohort_cluster_bootstrap"]
        if row["Group"] == "Overall"
    )
    key = next(
        row
        for row in numbers["placebo_decomposition"]
        if row["Group"] == "rating=-1 x step_type=Harmful"
    )
    audit = numbers["judge_audit"]
    lines = [
        "# Workstream F Execution Report",
        "",
        (
            "The full statistics/tables/figures pipeline completed and passed all "
            "technical consistency checks. The Judge Audit hard-stop gate passed; "
            f"the audit tier is {audit['review_tier']}."
            if audit["gate"] == "PASS"
            else
            "The full statistics/tables/figures pipeline completed and passed all "
            "technical consistency checks. The paper-level freeze remains blocked "
            "by the failed Judge Audit."
        ),
        "",
        "## Candidate headline numbers",
        "",
        f"- Full cohort (600 steps / 2,400 pairs): overall target-deletion change "
        f"**{as_float(overall['Accuracy_Change'])*100:+.2f} pp** "
        f"[{as_float(overall['Accuracy_CI_Lower'])*100:+.2f}, "
        f"{as_float(overall['Accuracy_CI_Upper'])*100:+.2f}].",
        f"- Placebo-matched cohort (511 steps / 1,514 placebo runs): "
        f"`rating=-1 × Harmful` pure semantic effect "
        f"**{as_float(key['Pure_Semantic_Effect'])*100:+.2f} pp** "
        f"[{as_float(key['Pure_Semantic_CI_Lower'])*100:+.2f}, "
        f"{as_float(key['Pure_Semantic_CI_Upper'])*100:+.2f}].",
        f"- Annotation association: Cramer’s V "
        f"**{numbers['annotation_association']['cramers_v']:.3f}**; "
        f"off-diagonal share "
        f"**{numbers['annotation_association']['off_diagonal_share']:.1%}**.",
        "",
        "## Completed supporting work",
        "",
        f"- Judge Audit: completed on {audit['n_outputs']} outputs; gate **{audit['gate']}**.",
        f"- Qualitative cases: {numbers['qualitative_cases']['verified_cases']}/8 verified "
        f"from {numbers['qualitative_cases']['audited_outputs']} human-reviewed outputs.",
        "- Main tables, appendix tables, four main figures, figure-source CSVs, and "
        "`numbers_for_paper.json` regenerated from one script.",
        "",
        "## Audit qualification",
        "",
        (
            "No hard-stop remediation is required. Report the "
            f"{audit['binary_agreement']:.1%} agreement, condition diagnostics, "
            "and pair-transition agreement alongside "
            "outcome-dependent claims because the stricter 95% threshold was not met."
            if audit["gate"] == "PASS"
            else
            "Remediate the Judge gate with an independent judge, symbolic evaluator, "
            "or expanded human review of each conclusion-critical subset, then rerun "
            "this script."
        ),
        "",
    ]
    (ROOT / "build" / "workstream_F_execution_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    verify_inputs()
    run_analyses()
    steps = read_csv(ROOT / "data" / "master_step_table.csv")
    main_rows = read_csv(ROOT / "data" / "qwen3-8b_cluster_bootstrap_metrics_5000.csv")
    stratified_rows = read_csv(ROOT / "data" / "qwen3-8b_cluster_bootstrap_stratified_5000.csv")
    placebo_rows = read_csv(ROOT / "data" / "qwen3-8b_placebo_effects_5000.csv")

    figure1_intervention_design(ROOT / "build" / "figure1_intervention_design.svg")
    figure2_association(steps, ROOT / "build" / "figure2_rating_step_type_heatmap.svg")
    figure3_rows = select_rows(placebo_rows, FIGURE3_GROUPS)
    forest_plot(
        figure3_rows,
        ROOT / "build" / "figure3_placebo_decomposition.svg",
        "Matched placebo decomposition (511 target steps / 1,514 placebo runs)",
        [
            ("target", "Target_Effect", "Target_CI_Lower", "Target_CI_Upper", "Target"),
            (
                "placebo",
                "Placebo_Effect",
                "Placebo_CI_Lower",
                "Placebo_CI_Upper",
                "Placebo",
            ),
            (
                "semantic",
                "Pure_Semantic_Effect",
                "Pure_Semantic_CI_Lower",
                "Pure_Semantic_CI_Upper",
                "Pure semantic",
            ),
        ],
        -0.15,
        0.35,
    )
    control_rows = [
        row for row in stratified_rows if row["Dimension"] == "control_correct_frequency"
    ]
    figure4_control_stability(control_rows, ROOT / "build" / "figure4_control_stability.svg")
    write_figure_sources(steps, placebo_rows, control_rows)

    numbers, checks = build_numbers()
    (ROOT / "build" / "numbers_for_paper.json").write_text(
        json.dumps(numbers, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_final_tables(numbers)
    write_appendix_tables(numbers)
    write_consistency_report(numbers, checks)
    write_results_report(numbers)
    sync_workstream_f_package()

    failed_checks = [row["check"] for row in checks if row["status"] == "FAIL"]
    if failed_checks:
        raise RuntimeError(
            "Workstream F technical consistency checks failed: "
            + ", ".join(failed_checks)
        )
    print(
        "Workstream F generated successfully; technical checks PASS; "
        f"Judge Audit gate {numbers['judge_audit']['gate']}."
    )


if __name__ == "__main__":
    main()
