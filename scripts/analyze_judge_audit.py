#!/usr/bin/env python3
"""Summarize the adjudicated Judge Audit and evaluate the preregistered gate."""

from __future__ import annotations

import csv
import html
import itertools
import json
import shutil
from pathlib import Path

from analysis_common import ROOT, as_bool, read_csv, write_csv


AUDIT_DIR = ROOT / "workstream_A_judge_audit"
SOURCE = ROOT / "workstream_A_judge_audit" / "judge_audit_adjudicated.csv"
MANIFEST = ROOT / "workstream_A_judge_audit" / "judge_audit_sampling_manifest.csv"
REPORT = ROOT / "build" / "judge_audit_report.md"
SVG = ROOT / "build" / "judge_audit_confusion_matrix.svg"
SENSITIVITY = ROOT / "build" / "judge_audit_label_substitution_sensitivity.csv"


def human_correct(label: str) -> bool:
    return label.strip() == "Correct"


def judge_correct(label: str) -> bool:
    return label.strip() == "1"


def grouped_metrics(rows: list[dict], key: str) -> list[dict]:
    result = []
    ordered = sorted(rows, key=lambda row: str(row.get(key, "")))
    for value, group in itertools.groupby(
        ordered, key=lambda row: str(row.get(key, ""))
    ):
        materialized = list(group)
        count = len(materialized)
        judge_positive = sum(row["judge_correct"] for row in materialized)
        human_positive = sum(row["human_correct"] for row in materialized)
        agreement = sum(row["agreement"] for row in materialized)
        result.append(
            {
                key: value or "(not applicable)",
                "n": count,
                "agreement": agreement / count,
                "judge_correct_rate": judge_positive / count,
                "human_correct_rate": human_positive / count,
                "bias_pp": 100 * (judge_positive - human_positive) / count,
            }
        )
    return result


def markdown_table(rows: list[dict], key: str) -> list[str]:
    lines = [
        f"| {key} | N | Agreement | Judge correct | Human correct | Bias (pp) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row[key]} | {row['n']} | {row['agreement']:.1%} | "
            f"{row['judge_correct_rate']:.1%} | "
            f"{row['human_correct_rate']:.1%} | {row['bias_pp']:+.1f} |"
        )
    return lines


def transition(left: bool, right: bool) -> str:
    return ("C" if left else "W") + ("C" if right else "W")


def write_confusion_svg(tp: int, tn: int, fp: int, fn: int) -> None:
    cells = [
        (260, 180, tn, "Human wrong / Judge wrong", "#d9f2e6"),
        (520, 180, fp, "Human wrong / Judge correct", "#fde2e0"),
        (260, 360, fn, "Human correct / Judge wrong", "#fff0cc"),
        (520, 360, tp, "Human correct / Judge correct", "#d9e8ff"),
    ]
    rects = []
    for x, y, count, label, color in cells:
        rects.append(
            f'<rect x="{x}" y="{y}" width="240" height="150" rx="10" '
            f'fill="{color}" stroke="#98a2b3"/>'
            f'<text x="{x + 120}" y="{y + 68}" text-anchor="middle" '
            f'font-size="38" font-weight="700">{count}</text>'
            f'<text x="{x + 120}" y="{y + 105}" text-anchor="middle" '
            f'font-size="14">{html.escape(label)}</text>'
        )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="820" height="570" viewBox="0 0 820 570">
<rect width="820" height="570" fill="white"/>
<style>text{{font-family:Arial,'Microsoft YaHei',sans-serif;fill:#172033}}</style>
<text x="410" y="48" text-anchor="middle" font-size="24" font-weight="700">Judge Audit Confusion Matrix</text>
<text x="410" y="78" text-anchor="middle" font-size="14" fill="#667085">N = 200 adjudicated outputs</text>
<text x="120" y="335" text-anchor="middle" font-size="17" font-weight="700" transform="rotate(-90 120 335)">Human adjudication</text>
<text x="500" y="535" text-anchor="middle" font-size="17" font-weight="700">Automated judge</text>
{''.join(rects)}
</svg>
"""
    SVG.write_text(svg, encoding="utf-8")


def compute_substitution_sensitivity(
    manifest: list[dict[str, str]],
    by_audit: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    """Replace only audited labels; this is a perturbation, not population correction."""
    replacements = {
        row["output_id"]: int(
            by_audit[row["audit_id"]]["human_label"].strip() == "Correct"
        )
        for row in manifest
    }
    runs = read_csv(ROOT / "data" / "master_run_table.csv")
    steps = read_csv(ROOT / "data" / "master_step_table.csv")
    eligible = {
        row["step_id"] for row in steps if as_bool(row["placebo_eligible"])
    }
    by_step_condition: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in runs:
        original = int(float(row["judge_label"]))
        materialized: dict[str, object] = {
            **row,
            "original": original,
            "substituted": replacements.get(row["output_id"], original),
        }
        by_step_condition.setdefault(
            (row["step_id"], row["condition"]), []
        ).append(materialized)

    def rate(members: list[dict[str, object]], field: str) -> float:
        return sum(int(row[field]) for row in members) / len(members)

    def result_row(
        scope: str,
        estimand: str,
        original: float,
        substituted: float,
        n: int,
        note: str,
    ) -> dict[str, object]:
        return {
            "scope": scope,
            "estimand": estimand,
            "n": n,
            "original_estimate": f"{original:.9f}",
            "adjudicated_substitution_estimate": f"{substituted:.9f}",
            "change_pp": f"{100 * (substituted - original):+.6f}",
            "interpretation": note,
        }

    output: list[dict[str, object]] = []
    for condition in ("control", "target_delete", "placebo_delete"):
        members = [row for row in runs if row["condition"] == condition]
        original = sum(int(float(row["judge_label"])) for row in members) / len(members)
        substituted = sum(
            replacements.get(row["output_id"], int(float(row["judge_label"])))
            for row in members
        ) / len(members)
        output.append(
            result_row(
                "full run table",
                f"{condition}_correct_rate",
                original,
                substituted,
                len(members),
                "Direct replacement of audited outputs only.",
            )
        )

    control = [row for row in runs if row["condition"] == "control"]
    target = [row for row in runs if row["condition"] == "target_delete"]
    full_original = (
        sum(int(float(row["judge_label"])) for row in target) / len(target)
        - sum(int(float(row["judge_label"])) for row in control) / len(control)
    )
    full_substituted = (
        sum(
            replacements.get(row["output_id"], int(float(row["judge_label"])))
            for row in target
        )
        / len(target)
        - sum(
            replacements.get(row["output_id"], int(float(row["judge_label"])))
            for row in control
        )
        / len(control)
    )
    output.append(
        result_row(
            "full cohort",
            "target_minus_control",
            full_original,
            full_substituted,
            len(target),
            "Paired design aggregate after replacing the 200 audited outputs.",
        )
    )

    def matched_effects(field: str, step_ids: set[str]) -> tuple[float, float, float]:
        target_effects: list[float] = []
        placebo_effects: list[float] = []
        for step_id in step_ids:
            groups = {
                condition: by_step_condition[(step_id, condition)]
                for condition in ("control", "target_delete", "placebo_delete")
            }
            control_rate = rate(groups["control"], field)
            target_effects.append(rate(groups["target_delete"], field) - control_rate)
            placebo_effects.append(rate(groups["placebo_delete"], field) - control_rate)
        target_effect = sum(target_effects) / len(target_effects)
        placebo_effect = sum(placebo_effects) / len(placebo_effects)
        return target_effect, placebo_effect, target_effect - placebo_effect

    original_effects = matched_effects("original", eligible)
    substituted_effects = matched_effects("substituted", eligible)
    for index, estimand in enumerate(
        ("target_effect", "placebo_effect", "pure_semantic_effect")
    ):
        output.append(
            result_row(
                "placebo-matched cohort",
                estimand,
                original_effects[index],
                substituted_effects[index],
                len(eligible),
                "Equal-weighted step-level effect; audited outputs replaced only.",
            )
        )
    return output


def main() -> None:
    manifest = read_csv(MANIFEST)
    adjudicated = read_csv(SOURCE)
    by_audit = {row["audit_id"]: row for row in adjudicated}
    if len(manifest) != 200 or len(adjudicated) != 200:
        raise ValueError(
            f"Expected 200 manifest and adjudicated rows; got "
            f"{len(manifest)} and {len(adjudicated)}"
        )
    if set(by_audit) != {row["audit_id"] for row in manifest}:
        raise ValueError("Manifest and adjudicated audit IDs do not match")
    if any(not row["human_label"].strip() for row in adjudicated):
        raise ValueError("Adjudicated CSV contains blank human labels")

    rows = []
    for row in manifest:
        human = by_audit[row["audit_id"]]
        j_correct = judge_correct(row["judge_label"])
        h_correct = human_correct(human["human_label"])
        rows.append(
            {
                **row,
                "human_label": human["human_label"],
                "human_reason": human["human_reason"],
                "judge_correct": j_correct,
                "human_correct": h_correct,
                "agreement": j_correct == h_correct,
            }
        )

    tp = sum(row["judge_correct"] and row["human_correct"] for row in rows)
    tn = sum(not row["judge_correct"] and not row["human_correct"] for row in rows)
    fp = sum(row["judge_correct"] and not row["human_correct"] for row in rows)
    fn = sum(not row["judge_correct"] and row["human_correct"] for row in rows)
    agreement = (tp + tn) / len(rows)

    condition = grouped_metrics(rows, "condition")
    max_condition_bias = max(abs(row["bias_pp"]) for row in condition)

    pair_rows = []
    ordered = sorted(rows, key=lambda row: row["case_id"])
    for case_id, group in itertools.groupby(
        ordered, key=lambda row: row["case_id"]
    ):
        materialized = list(group)
        by_role = {row["case_role"]: row for row in materialized}
        if set(by_role) != {"control", "target"}:
            continue
        control, target = by_role["control"], by_role["target"]
        auto_transition = transition(
            control["judge_correct"], target["judge_correct"]
        )
        human_transition = transition(
            control["human_correct"], target["human_correct"]
        )
        pair_rows.append(
            {
                "case_id": case_id,
                "stratum": control["stratum"],
                "automated": auto_transition,
                "human": human_transition,
                "agreement": auto_transition == human_transition,
            }
        )
    pair_agreement = (
        sum(row["agreement"] for row in pair_rows) / len(pair_rows)
    )

    gate_pass = agreement >= 0.90 and max_condition_bias <= 5.0
    decision = "PASS" if gate_pass else "FAIL"
    if not gate_pass:
        action = (
            "Do not freeze the current automated labels. Per the execution plan, "
            "use an independent judge, symbolic evaluator, or expanded human "
            "review of every conclusion-critical subset."
        )
    elif agreement >= 0.95 and max_condition_bias < 3.0:
        action = "Freeze the current labels; the strict retain-without-remediation threshold passed."
    else:
        action = (
            "The hard-stop gate passed and the project-designated adjudicated file "
            "is frozen. Because agreement is below 95%, report the audit diagnostics "
            "as a sensitivity boundary and do not claim evaluator equivalence."
        )
    sensitivity = compute_substitution_sensitivity(manifest, by_audit)
    write_csv(SENSITIVITY, sensitivity)

    lines = [
        "# Judge Audit Report",
        "",
        "## Gate decision",
        "",
        f"**{decision}.** Binary correctness agreement was **{agreement:.1%}** "
        f"({tp + tn}/200); the largest absolute condition-level correctness-rate "
        f"bias was **{max_condition_bias:.1f} pp**.",
        "",
        f"Action: {action}",
        "",
        "The hard-stop gate fails when agreement is < 90% or absolute condition "
        "bias is > 5 pp. Retaining the judge without remediation requires the "
        "stricter threshold of agreement >= 95% and bias < 3 pp; intermediate "
        "results require secondary review.",
        "",
        "## Binary confusion matrix",
        "",
        "| | Human correct | Human wrong |",
        "|---|---:|---:|",
        f"| Judge correct | {tp} | {fp} |",
        f"| Judge wrong | {fn} | {tn} |",
        "",
        f"- False-positive rate among human-wrong outputs: {fp / (fp + tn):.1%}.",
        f"- False-negative rate among human-correct outputs: {fn / (fn + tp):.1%}.",
        f"- Automated correct rate: {(tp + fp) / len(rows):.1%}.",
        f"- Human-adjudicated correct rate: {(tp + fn) / len(rows):.1%}.",
        "",
        "## Condition diagnostics",
        "",
        *markdown_table(condition, "condition"),
        "",
        "Bias is automated-judge correct rate minus human-adjudicated correct rate.",
        "",
        "## Sampling-stratum diagnostics",
        "",
        *markdown_table(grouped_metrics(rows, "stratum"), "stratum"),
        "",
        "## PRM-rating diagnostics",
        "",
        *markdown_table(grouped_metrics(rows, "prm_rating"), "prm_rating"),
        "",
        "## Pair-level transition audit",
        "",
        f"Among {len(pair_rows)} sampled control/target pairs, the automated and "
        f"human transition labels matched for "
        f"**{sum(row['agreement'] for row in pair_rows)}/{len(pair_rows)} "
        f"({pair_agreement:.1%})**.",
        "",
        "| Case | Stratum | Automated | Human |",
        "|---|---|---|---|",
    ]
    for row in pair_rows:
        if not row["agreement"]:
            lines.append(
                f"| {row['case_id']} | {row['stratum']} | "
                f"{row['automated']} | {row['human']} |"
            )
    lines += [
        "",
        "## Direct label-substitution sensitivity",
        "",
        "This diagnostic replaces the automated label only for the 200 audited "
        "outputs and leaves the other 6,114 outputs unchanged. It is a local "
        "perturbation check, not a population-level bias correction, because the "
        "audit sample was purposively stratified.",
        "",
        "| Scope | Estimand | N | Original | Substituted | Change (pp) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in sensitivity:
        lines.append(
            f"| {row['scope']} | {row['estimand']} | {row['n']} | "
            f"{100 * float(row['original_estimate']):+.2f} | "
            f"{100 * float(row['adjudicated_substitution_estimate']):+.2f} | "
            f"{float(row['change_pp']):+.2f} |"
        )
    lines += [
        "",
        "## Consequence for qualitative cases",
        "",
        "Only 4 of the 78 outputs belonging to the provisional eight qualitative "
        "cases occurred in the 200-output audit. Because the overall gate failed, "
        "Workstream E subsequently obtained direct human labels for all 78 case "
        "outputs. The final 8/8 cases passed their fixed family-specific rules. "
        "This separate verification supports the qualitative case narratives, "
        "but it does not clear the aggregate automated-outcome gate.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    write_confusion_svg(tp, tn, fp, fn)
    AUDIT_DIR.mkdir(exist_ok=True)
    for path in (REPORT, SVG, SENSITIVITY):
        shutil.copyfile(path, AUDIT_DIR / path.name)

    summary = {
        "n": len(rows),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "agreement": agreement,
        "max_absolute_condition_bias_pp": max_condition_bias,
        "pair_transition_agreement": pair_agreement,
        "label_substitution_sensitivity": sensitivity,
        "gate": decision,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
