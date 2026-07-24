#!/usr/bin/env python3
"""Finalize the eight qualitative cases from the completed case-specific audit."""

from __future__ import annotations

import collections
import json
import math
import shutil
import textwrap
from pathlib import Path

from analysis_common import ROOT, as_int, read_csv, write_csv


RECOMMENDED_COUNTS = {
    "negative_anchor": 3,
    "generic_restart": 2,
    "stable_correct_harmed": 2,
    "high_rated_redundant_ambiguity": 1,
}

FAMILY_TITLES = {
    "negative_anchor": "Negative Anchor",
    "generic_restart": "Generic Restart",
    "stable_correct_harmed": "Stable-correct Harmed",
    "high_rated_redundant_ambiguity": "High-rated / Redundant Ambiguity",
}

CASE_NOTES = {
    "prm-2413c903941648a5": {
        "rating_rationale": (
            "The step was rated -1 and human-calibrated as Harmful because it "
            "anchors the continuation on a brittle global rationalization before "
            "the nested radical has been simplified term by term."
        ),
        "mechanism": (
            "Keeping the step sends all four controls into an error or unfinished "
            "derivation. Deleting it induces a clean termwise restart: "
            "\\(\\sqrt{845}=13\\sqrt5\\), the numerator becomes "
            "\\(169\\sqrt5/36\\), and all four runs reach \\(13/6\\). "
            "Placebo deletions never recover, isolating a target-specific effect."
        ),
        "paper_excerpt": (
            "Control: global rationalization produced an incorrect or unfinished "
            "derivation.\nTarget deletion: simplify each numerator term first; "
            "the expression reduces to \\(\\sqrt{169/36}=13/6\\).\n"
            "Placebo: 0/4 correct."
        ),
    },
    "prm-3fb0a1041b0e6522": {
        "rating_rationale": (
            "The -1/Harmful label is literal: 12 does not divide 2000 evenly, so "
            "the target step inserts the wrong remainder invariant."
        ),
        "mechanism": (
            "All controls and the placebo preserve the false claim and answer 4. "
            "After target deletion, every continuation recomputes 2004/12 "
            "directly and returns remainder 0. This is the clearest negative-anchor "
            "example because the deleted proposition is locally false."
        ),
        "paper_excerpt": (
            "Control: “Since 4 is less than 12 … the remainder … is 4.”\n"
            "Target deletion: “2004 divided by 12 gives quotient 167 and "
            "remainder 0.”\nHuman audit: WC=4, placebo=0/1 correct."
        ),
    },
    "prm-77fc0b169d8585bc": {
        "rating_rationale": (
            "The -1/Harmful step incorrectly excludes the origin, which is "
            "strictly inside the rectangle, and encourages further boundary "
            "bookkeeping errors."
        ),
        "mechanism": (
            "Controls inherit the mistaken geometry and all fail. Without the "
            "anchor, continuations use the correct interior ranges "
            "\\(-4\\le x\\le4\\) and \\(-3\\le y\\le3\\), yielding "
            "\\(9\\times7=63\\). None of the three placebo deletions recovers."
        ),
        "paper_excerpt": (
            "Control: used truncated interior ranges and obtained 35.\n"
            "Target deletion: nine integer x-values and seven y-values give 63.\n"
            "Human audit: WC=4; placebo=0/3 correct."
        ),
    },
    "prm-dfdb549c682c7822": {
        "rating_rationale": (
            "The removed step applies the wrong exponent to 256, but both target "
            "and unrelated placebo deletion trigger a fresh solution."
        ),
        "mechanism": (
            "Controls follow the exponent slip and answer \\(x=1\\). Target "
            "deletion restarts with \\(256=2^8\\); the placebo continuation "
            "independently takes the same full-problem restart route. Both "
            "conditions reach \\(x=2\\), so the raw gain is not target-specific."
        ),
        "paper_excerpt": (
            "Control: equated \\(2x=2\\) and returned \\(x=1\\).\n"
            "Target/placebo restart: \\(256^{1/2}=2^4\\), hence \\(2x=4\\) "
            "and \\(x=2\\).\nPure semantic effect: 0 pp."
        ),
    },
    "prm-2f5e5f1e6dacb0f7": {
        "rating_rationale": (
            "The target context is attached to an incorrect intermediate total, "
            "while both deletion conditions allow the model to recompute."
        ),
        "mechanism": (
            "Controls retain the erroneous remainder 4. Target deletion recovers "
            "the correct final remainder 1; placebo deletion follows a visibly "
            "different modular-summation path and also returns 1. The matched "
            "improvement therefore reflects restart behavior rather than unique "
            "semantic removal."
        ),
        "paper_excerpt": (
            "Control: returned remainder 4.\n"
            "Target deletion: recomputed the division and returned 1.\n"
            "Placebo: summed termwise residues modulo 9 and also returned 1."
        ),
    },
    "prm-0700321e0038e3d1": {
        "rating_rationale": (
            "The step is semantically generic and was human-calibrated Redundant, "
            "yet it functions as a procedural bridge that keeps generation moving."
        ),
        "mechanism": (
            "All four controls solve the linear equation to \\(x=83\\). Every "
            "target-deletion run merely restates the equation and stops without a "
            "final answer, while the placebo run remains correct. Deletion harm "
            "here is a continuation-state effect, not loss of mathematical facts."
        ),
        "paper_excerpt": (
            "Control: multiply by 2, obtain \\(3x-9=2x+74\\), then \\(x=83\\).\n"
            "Target deletion: restated the equation but produced no final answer.\n"
            "Human audit: CW=4."
        ),
    },
    "prm-ab1c7130781f0c6b": {
        "rating_rationale": (
            "The step contains the wrong 180-second result, but its explicit claim "
            "also gives the intact continuation a contradiction to detect."
        ),
        "mechanism": (
            "All controls eventually self-correct to 36 seconds. After deletion, "
            "all four target runs repeat the uncorrected 180-second path, whereas "
            "both placebo runs remain correct. A locally harmful step can thus "
            "serve as a useful error-detection cue in the realized trajectory."
        ),
        "paper_excerpt": (
            "Control: detected the period-calculation inconsistency and recovered "
            "36 seconds.\nTarget deletion: retained the 3-minute/180-second error.\n"
            "Human audit: CW=4; placebo=2/2 correct."
        ),
    },
    "prm-fa241fc7e4a6f419": {
        "rating_rationale": (
            "The step is high-rated and Redundant because “four miles per walking "
            "day” repeats the problem statement, but it stabilizes the final count."
        ),
        "mechanism": (
            "Controls preserve the February-only scope and return "
            "\\(9\\times4=36\\). Every target-deletion run counts January 30 as an "
            "additional February walking day and returns 40; the placebo run "
            "remains correct. Semantic redundancy therefore does not imply stable "
            "deletion safety."
        ),
        "paper_excerpt": (
            "Control: nine February walking days times four miles gives 36.\n"
            "Target deletion: counted January 30 among ten days and returned 40.\n"
            "Human audit: CW=4; placebo correct."
        ),
    },
}

ROLE_SUMMARIES = {
    "prm-2413c903941648a5": {
        "control": "The global rationalization path produced an incorrect or unfinished derivation.",
        "target": "Termwise simplification reduced the expression to \\(\\sqrt{169/36}=13/6\\).",
        "placebo": "All four placebo continuations remained incorrect or unfinished.",
    },
    "prm-3fb0a1041b0e6522": {
        "control": "Preserved the false claim about 2000 and returned remainder 4.",
        "target": "Recomputed 2004 divided by 12 and returned remainder 0.",
        "placebo": "Preserved the same false claim and returned remainder 4.",
    },
    "prm-77fc0b169d8585bc": {
        "control": "Used truncated interior ranges and obtained 35.",
        "target": "Counted nine integer x-values and seven y-values, obtaining 63.",
        "placebo": "All three placebo continuations used incorrect geometric counts.",
    },
    "prm-dfdb549c682c7822": {
        "control": "Followed the exponent slip, equated \\(2x=2\\), and returned \\(x=1\\).",
        "target": "Restarted with \\(256=2^8\\), so \\(2x=4\\) and \\(x=2\\).",
        "placebo": "Independently restarted from the full equation and also returned \\(x=2\\).",
    },
    "prm-2f5e5f1e6dacb0f7": {
        "control": "Retained the erroneous intermediate total and returned remainder 4.",
        "target": "Recomputed the final division and returned remainder 1.",
        "placebo": "Used a distinct termwise modular-summation path and returned 1.",
    },
    "prm-0700321e0038e3d1": {
        "control": "Solved \\((3x-9)/2=x+37\\) through to \\(x=83\\).",
        "target": "Restated the equation but stopped without a final answer in all four runs.",
        "placebo": "Continued the algebraic solution and returned \\(x=83\\).",
    },
    "prm-ab1c7130781f0c6b": {
        "control": "Detected the period-calculation inconsistency and recovered 36 seconds.",
        "target": "Retained the three-minute error and returned 180 seconds.",
        "placebo": "Both placebo continuations remained correct at 36 seconds.",
    },
    "prm-fa241fc7e4a6f419": {
        "control": "Counted nine February walking days and returned 36 miles.",
        "target": "Incorrectly counted January 30 among ten days and returned 40 miles.",
        "placebo": "Preserved the February-only count and returned 36 miles.",
    },
}


def is_correct(label: str) -> bool:
    return label.strip() == "Correct"


def fmt_effect(value: float | None) -> str:
    return "" if value is None or math.isnan(value) else f"{value:.6f}"


def short(value: str, width: int = 520) -> str:
    return textwrap.shorten(
        " ".join((value or "").replace("\x0c", "\\f").split()),
        width=width,
        placeholder="…",
    )


def tex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def plain_for_tex(value: str) -> str:
    return (
        value.replace(r"\(", "")
        .replace(r"\)", "")
        .replace(r"\sqrt", "sqrt")
        .replace(r"\le", "<=")
        .replace(r"\times", "x")
        .replace("{", "(")
        .replace("}", ")")
    )


def compute_case(
    candidate: dict[str, str],
    runs: list[dict[str, str]],
    audit_by_id: dict[str, dict[str, str]],
) -> dict[str, object]:
    reviewed = []
    for run in runs:
        audit = audit_by_id[run["audit_id"]]
        reviewed.append(
            {
                **run,
                "human_label": audit["human_label"],
                "human_reason": audit["human_reason"],
                "human_correct": is_correct(audit["human_label"]),
            }
        )
    by_condition: dict[str, list[dict]] = collections.defaultdict(list)
    by_output: dict[str, dict] = {}
    for row in reviewed:
        by_condition[row["condition"]].append(row)
        by_output[row["output_id"]] = row

    control = by_condition["control"]
    target = by_condition["target_delete"]
    placebo = by_condition["placebo_delete"]
    if len(control) != 4 or len(target) != 4:
        raise ValueError(
            f"{candidate['step_id']} does not have four control and target runs"
        )

    control_by_pair = {row["pair_id"]: row for row in control}
    target_by_pair = {row["pair_id"]: row for row in target}
    if set(control_by_pair) != set(target_by_pair):
        raise ValueError(
            f"{candidate['step_id']} has unmatched control/target pair IDs"
        )
    transitions = collections.Counter()
    for pair_id in sorted(control_by_pair):
        left = control_by_pair[pair_id]["human_correct"]
        right = target_by_pair[pair_id]["human_correct"]
        code = ("C" if left else "W") + ("C" if right else "W")
        transitions[code] += 1

    control_rate = sum(row["human_correct"] for row in control) / len(control)
    target_rate = sum(row["human_correct"] for row in target) / len(target)
    placebo_rate = (
        sum(row["human_correct"] for row in placebo) / len(placebo)
        if placebo
        else math.nan
    )
    target_effect = target_rate - control_rate
    placebo_effect = (
        placebo_rate - control_rate if placebo else math.nan
    )
    pure_effect = target_rate - placebo_rate if placebo else math.nan

    family = candidate["case_family"]
    if family == "negative_anchor":
        passes = (
            as_int(candidate["prm_rating"]) == -1
            and candidate["step_type_human_calibrated"].lower() == "harmful"
            and transitions["WC"] >= 2
            and transitions["CW"] == 0
            and pure_effect > 0
            and target_effect > placebo_effect
        )
    elif family == "generic_restart":
        passes = (
            target_effect > 0
            and placebo_effect > 0
            and transitions["WC"] >= 1
        )
    elif family == "stable_correct_harmed":
        passes = (
            sum(row["human_correct"] for row in control) == 4
            and transitions["CW"] >= 2
        )
    else:
        passes = (
            as_int(candidate["prm_rating"]) == 1
            and candidate["step_type_human_calibrated"].lower() == "redundant"
            and transitions["CW"] > 0
        )

    note = CASE_NOTES[candidate["step_id"]]
    role_summaries = ROLE_SUMMARIES[candidate["step_id"]]
    representative = {}
    for role in ("control", "target", "placebo"):
        output_id = candidate[f"{role}_output_id"]
        representative[f"{role}_human_label"] = (
            by_output[output_id]["human_label"] if output_id else ""
        )

    return {
        **candidate,
        "human_control_correct_count": sum(
            row["human_correct"] for row in control
        ),
        "human_control_run_count": len(control),
        "human_target_correct_count": sum(
            row["human_correct"] for row in target
        ),
        "human_target_run_count": len(target),
        "human_placebo_correct_count": sum(
            row["human_correct"] for row in placebo
        ),
        "human_placebo_run_count": len(placebo),
        "human_wrong_to_correct_count": transitions["WC"],
        "human_correct_to_wrong_count": transitions["CW"],
        "human_still_correct_count": transitions["CC"],
        "human_still_wrong_count": transitions["WW"],
        "human_target_effect": fmt_effect(target_effect),
        "human_placebo_effect": fmt_effect(placebo_effect),
        "human_pure_semantic_effect": fmt_effect(pure_effect),
        "verification_status": "VERIFIED" if passes else "FAILED",
        "human_transition_verified": "yes" if passes else "no",
        "verification_source": "qualitative_case_audit_completed.csv",
        "rating_type_rationale": note["rating_rationale"],
        "mechanism_explanation": note["mechanism"],
        "paper_excerpt": note["paper_excerpt"],
        "control_key_excerpt": role_summaries["control"],
        "target_key_excerpt": role_summaries["target"],
        "placebo_key_excerpt": role_summaries["placebo"],
        "human_case_notes": (
            f"All {len(reviewed)} available condition outputs were human-labeled; "
            f"the fixed {FAMILY_TITLES[family]} rule "
            f"{'passed' if passes else 'failed'}."
        ),
        **representative,
    }


def markdown_case(row: dict[str, object]) -> list[str]:
    target_effect = 100 * float(str(row["human_target_effect"]))
    placebo_effect = 100 * float(str(row["human_placebo_effect"]))
    pure_effect = 100 * float(str(row["human_pure_semantic_effect"]))
    return [
        f"### {row['step_id']}",
        "",
        f"1. **Problem.** {row['problem']}",
        f"2. **Target step.** {row['target_step_text']}",
        (
            "3. **PRM / Step Type interpretation.** "
            f"Rating `{row['prm_rating']}`; analysis type "
            f"`{row['step_type_analysis']}`; human-calibrated type "
            f"`{row['step_type_human_calibrated']}`. "
            f"{row['rating_type_rationale']}"
        ),
        (
            "4. **Control continuation.** "
            f"[{row['control_human_label']}] {row['control_key_excerpt']}"
        ),
        (
            "5. **Target-deletion continuation.** "
            f"[{row['target_human_label']}] {row['target_key_excerpt']}"
        ),
        (
            "6. **Placebo continuation.** "
            f"[{row['placebo_human_label']}] {row['placebo_key_excerpt']}"
        ),
        (
            "7. **Human verdict.** "
            f"Control `{row['human_control_correct_count']}/"
            f"{row['human_control_run_count']}`, Target `"
            f"{row['human_target_correct_count']}/"
            f"{row['human_target_run_count']}`, Placebo `"
            f"{row['human_placebo_correct_count']}/"
            f"{row['human_placebo_run_count']}`; "
            f"WC/CW = `{row['human_wrong_to_correct_count']}/"
            f"{row['human_correct_to_wrong_count']}`; "
            f"Target effect `{target_effect:+.0f} pp`, Placebo effect "
            f"`{placebo_effect:+.0f} pp`, pure semantic effect "
            f"`{pure_effect:+.0f} pp`."
        ),
        f"8. **Mechanism.** {row['mechanism_explanation']}",
        "9. **Paper-length excerpt.**",
        "",
        "> " + str(row["paper_excerpt"]).replace("\n", "\n> "),
        "",
    ]


def write_markdown(rows: list[dict[str, object]]) -> None:
    lines = [
        "# Verified Qualitative Cases",
        "",
        "Selection seed: `20260723`.",
        "",
        "These eight cases were selected by the preregistered deterministic rules. "
        "All 78 associated Control, Target-deletion, and available Placebo outputs "
        "were then human-labeled; four labels came from the original adjudicated "
        "audit and 74 from the case-specific supplemental audit. All eight cases "
        "passed their family-specific transition rule.",
        "",
        "> These cases illustrate mechanisms and are not estimates of population "
        "frequency. Effects below are within-case descriptive differences.",
        "",
        "## Verification summary",
        "",
        "| Family | Step | Human C/T/P | WC/CW | Target | Placebo | Pure |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {FAMILY_TITLES[str(row['case_family'])]} | "
            f"`{row['step_id']}` | "
            f"{row['human_control_correct_count']}/"
            f"{row['human_control_run_count']} · "
            f"{row['human_target_correct_count']}/"
            f"{row['human_target_run_count']} · "
            f"{row['human_placebo_correct_count']}/"
            f"{row['human_placebo_run_count']} | "
            f"{row['human_wrong_to_correct_count']}/"
            f"{row['human_correct_to_wrong_count']} | "
            f"{100 * float(str(row['human_target_effect'])):+.0f} pp | "
            f"{100 * float(str(row['human_placebo_effect'])):+.0f} pp | "
            f"{100 * float(str(row['human_pure_semantic_effect'])):+.0f} pp |"
        )
    lines.append("")
    for family in RECOMMENDED_COUNTS:
        lines += [f"## {FAMILY_TITLES[family]}", ""]
        for row in rows:
            if row["case_family"] == family:
                lines += markdown_case(row)
    lines += [
        "## Artifact note",
        "",
        "The short excerpts above are for the manuscript. Full outputs and "
        "per-output human labels remain in `qualitative_case_audit_completed.csv`; "
        "the blinded mapping is in `qualitative_case_audit_manifest.csv`.",
        "",
    ]
    (ROOT / "workstream_E_qualitative_case_study" / "qualitative_cases.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_latex(rows: list[dict[str, object]]) -> None:
    lines = [
        r"% Auto-generated by finalize_qualitative_cases.py",
        r"% Requires \usepackage{booktabs,tabularx}.",
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        r"\caption{Human-verified qualitative cases. C/T/P reports the number of correct Control, Target-deletion, and Placebo outputs; effects are descriptive percentage-point differences within each case.}",
        r"\label{tab:qualitative-cases}",
        r"\begin{tabularx}{\textwidth}{@{}p{2.5cm}p{3.4cm}c c r r r X@{}}",
        r"\toprule",
        r"Family & Step ID & C/T/P & WC/CW & Target & Placebo & Pure & Mechanism \\",
        r"\midrule",
    ]
    for row in rows:
        mechanism = plain_for_tex(
            short(str(row["mechanism_explanation"]), width=190)
        )
        lines.append(
            f"{tex_escape(FAMILY_TITLES[str(row['case_family'])])} & "
            f"\\texttt{{{tex_escape(str(row['step_id']))}}} & "
            f"{row['human_control_correct_count']}/"
            f"{row['human_control_run_count']}; "
            f"{row['human_target_correct_count']}/"
            f"{row['human_target_run_count']}; "
            f"{row['human_placebo_correct_count']}/"
            f"{row['human_placebo_run_count']} & "
            f"{row['human_wrong_to_correct_count']}/"
            f"{row['human_correct_to_wrong_count']} & "
            f"{100 * float(str(row['human_target_effect'])):+.0f} & "
            f"{100 * float(str(row['human_placebo_effect'])):+.0f} & "
            f"{100 * float(str(row['human_pure_semantic_effect'])):+.0f} & "
            f"{tex_escape(mechanism)} \\\\"
        )
    lines += [
        r"\bottomrule",
        r"\end{tabularx}",
        r"\end{table*}",
        "",
    ]
    (ROOT / "workstream_E_qualitative_case_study" / "qualitative_cases_appendix.tex").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    candidates = read_csv(ROOT / "workstream_E_qualitative_case_study" / "qualitative_case_candidates.csv")
    manifest = read_csv(ROOT / "data" / "annotations" / "qualitative" / "qualitative_case_audit_manifest.csv")
    audit = read_csv(ROOT / "data" / "annotations" / "qualitative" / "qualitative_case_audit_completed.csv")
    audit_by_id = {row["audit_id"]: row for row in audit}
    if len(audit) != 78 or set(audit_by_id) != {
        row["audit_id"] for row in manifest
    }:
        raise ValueError("Completed audit and manifest do not contain the same 78 IDs")
    if any(not row["human_label"].strip() for row in audit):
        raise ValueError("Completed qualitative audit contains blank labels")

    selected = [
        row
        for row in candidates
        if as_int(row["family_rank"])
        <= RECOMMENDED_COUNTS[row["case_family"]]
    ]
    runs_by_step: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for row in manifest:
        runs_by_step[row["step_id"]].append(row)
    verified = [
        compute_case(row, runs_by_step[row["step_id"]], audit_by_id)
        for row in selected
    ]
    failures = [
        row["step_id"]
        for row in verified
        if row["verification_status"] != "VERIFIED"
    ]
    if failures:
        raise ValueError(
            "The following provisional cases failed their fixed rule and must be "
            f"replaced before finalization: {failures}"
        )

    write_csv(ROOT / "workstream_E_qualitative_case_study" / "qualitative_cases_verified.csv", verified)
    write_markdown(verified)
    write_latex(verified)
    summary = {
        "verified_cases": len(verified),
        "families": dict(
            collections.Counter(row["case_family"] for row in verified)
        ),
        "audited_outputs": len(audit),
        "all_fixed_rules_passed": True,
        "outputs": [
            "qualitative_cases_verified.csv",
            "qualitative_cases.md",
            "qualitative_cases_appendix.tex",
        ],
    }
    (ROOT / "workstream_E_qualitative_case_study" / "qualitative_cases_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
