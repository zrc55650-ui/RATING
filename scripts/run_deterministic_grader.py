#!/usr/bin/env python3
"""Deterministic grader robustness check (review issue: judge self-evaluation).

The frozen outcome evaluator is a Qwen3-8B judge scoring a Qwen3-8B
generator, which invites a self-evaluation-bias concern. This script grades
every primary-cohort run with a deterministic two-tier grader in the spirit
of the PRM800K reference grader:

  tier 1: PRM800K-style string normalization + exact match;
  tier 2: SymPy symbolic equivalence on answers that fail tier 1 but parse
          (requires sympy; skipped gracefully if unavailable).

It reports agreement with the LLM judge and recomputes the headline deletion
effects under the deterministic grader, so the observed judge effect on every
headline number is on record.

Run with a sympy-equipped interpreter for tier 2:
    <venv>/bin/python scripts/run_deterministic_grader.py
"""

from __future__ import annotations

import re
from collections import defaultdict

from analysis_common import ROOT, as_int, fmt, read_csv, write_csv

OUT = ROOT / "workstream_A_judge_audit" / "deterministic_grader_comparison.csv"

try:
    import sympy
    from sympy import simplify

    HAVE_SYMPY = True
except ImportError:
    HAVE_SYMPY = False


def normalize(answer: str) -> str:
    """PRM800K-style answer normalization (string tier)."""
    if answer is None:
        return ""
    text = str(answer).strip()
    match = re.search(r"\\boxed\{(.*)\}", text)
    if match:
        text = match.group(1)
    text = text.replace("\\left", "").replace("\\right", "")
    text = text.replace("\\!", "").replace("\\,", "").replace("\\ ", " ")
    text = text.replace("\\$", "").replace("$", "").replace("\\%", "").replace("%", "")
    text = text.replace("^{\\circ}", "").replace("^\\circ", "")
    text = re.sub(r"\\text\{[^}]*\}", "", text)
    text = re.sub(r"\\mbox\{[^}]*\}", "", text)
    text = text.replace("\\cdot", "*").replace("\\times", "*")
    text = re.sub(r"\\d?frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
    text = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", text)
    text = re.sub(r"\\sqrt(\w)", r"sqrt(\1)", text)
    text = text.replace("\\pi", "pi").replace("\\infty", "oo")
    text = text.replace("dfrac", "frac").replace("tfrac", "frac")
    text = text.replace(" ", "").replace(",", "").lower()
    text = text.rstrip(".")
    if re.fullmatch(r"-?\d+\.0+", text):
        text = text.split(".")[0]
    if re.fullmatch(r"0\.\d+", text):
        text = text.lstrip("0")
    return text


def sympy_equal(a: str, b: str) -> bool:
    if not HAVE_SYMPY or not a or not b or max(len(a), len(b)) > 80:
        return False
    try:
        expr_a = sympy.sympify(a.replace("^", "**"), rational=True)
        expr_b = sympy.sympify(b.replace("^", "**"), rational=True)
        return bool(simplify(expr_a - expr_b) == 0)
    except Exception:  # noqa: BLE001 - any parse/eval failure means "unknown"
        return False


def grade(candidate: str, truth: str) -> tuple[int, str]:
    norm_c, norm_t = normalize(candidate), normalize(truth)
    if not norm_c:
        return 0, "no_answer"
    if norm_c == norm_t:
        return 1, "string_match"
    if sympy_equal(norm_c, norm_t):
        return 1, "sympy_equal"
    return 0, "mismatch"


def effect(by_step: dict[str, dict[str, list[int]]], subset=None) -> float:
    deltas = []
    for sid, conds in by_step.items():
        if subset is not None and sid not in subset:
            continue
        control, target = conds.get("control", []), conds.get("target_delete", [])
        if control and target:
            deltas.append(sum(target) / len(target) - sum(control) / len(control))
    return 100 * sum(deltas) / len(deltas)


def main() -> None:
    runs = read_csv(ROOT / "data" / "master_run_table.csv")
    steps = {r["step_id"]: r for r in read_csv(ROOT / "data" / "master_step_table.csv")}
    anchor = {
        sid
        for sid, s in steps.items()
        if as_int(s["prm_rating"]) == -1 and s["step_type_analysis"].strip().lower() == "harmful"
    }
    agree = disagree = 0
    tiers = defaultdict(int)
    judge_steps: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    det_steps: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    disagreements = []
    for row in runs:
        judge = 1 if row["judge_label"].strip() == "1" else 0
        det, tier = grade(row["final_answer_normalized"] or row["final_answer_raw"], row["ground_truth_answer"])
        tiers[tier] += 1
        if det == judge:
            agree += 1
        else:
            disagree += 1
            if len(disagreements) < 400:
                disagreements.append(
                    {
                        "output_id": row["output_id"],
                        "condition": row["condition"],
                        "judge_label": judge,
                        "det_label": det,
                        "det_tier": tier,
                        "candidate": (row["final_answer_normalized"] or "")[:80],
                        "truth": row["ground_truth_answer"][:80],
                    }
                )
        if row["condition"] in ("control", "target_delete"):
            judge_steps[row["step_id"]][row["condition"]].append(judge)
            det_steps[row["step_id"]][row["condition"]].append(det)

    total = agree + disagree
    print(f"sympy available: {HAVE_SYMPY}")
    print(f"runs graded: {total}; agreement with LLM judge: {agree / total:.4f}")
    print("tier breakdown:", dict(tiers))
    rows = [
        {"metric": "agreement_with_llm_judge", "value": fmt(agree / total, 4)},
        {"metric": "runs_graded", "value": total},
        {"metric": "sympy_available", "value": int(HAVE_SYMPY)},
    ]
    for name, subset in (("overall", None), ("anchor_rating-1xHarmful", anchor)):
        judge_eff = effect(judge_steps, subset)
        det_eff = effect(det_steps, subset)
        rows.append({"metric": f"target_effect_{name}_llm_judge_pp", "value": fmt(judge_eff, 2)})
        rows.append({"metric": f"target_effect_{name}_det_grader_pp", "value": fmt(det_eff, 2)})
        rows.append({"metric": f"target_effect_{name}_abs_diff_pp", "value": fmt(abs(judge_eff - det_eff), 2)})
        print(f"{name}: judge {judge_eff:.2f}pp vs deterministic {det_eff:.2f}pp")
    write_csv(OUT, rows)
    write_csv(ROOT / "workstream_A_judge_audit" / "deterministic_grader_disagreements.csv", disagreements)


if __name__ == "__main__":
    main()
