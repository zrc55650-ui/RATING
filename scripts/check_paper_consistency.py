#!/usr/bin/env python3
"""Automated consistency checks: paper claims vs. frozen data sources.

Each check recomputes a paper-critical quantity from its canonical source file
and asserts the value cited in the paper. Run before every submission build:

    python3 scripts/check_paper_consistency.py

Exits nonzero on any failure. Stdlib only.
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from analysis_common import ROOT, as_float, as_int, read_csv

FAILURES = []


def check(name: str, actual, expected) -> None:
    ok = actual == expected
    print(("PASS " if ok else "FAIL ") + name + f": actual={actual} expected={expected}")
    if not ok:
        FAILURES.append(name)


def approx(name: str, actual: float, expected: float, tol: float) -> None:
    ok = abs(actual - expected) <= tol
    print(("PASS " if ok else "FAIL ") + name + f": actual={actual:.4f} expected={expected}")
    if not ok:
        FAILURES.append(name)


def main() -> None:
    steps = read_csv(ROOT / "data" / "master_step_table.csv")
    runs = read_csv(ROOT / "data" / "master_run_table.csv")

    # Cohort structure
    check("600 steps", len(steps), 600)
    check("ratings 200/200/200",
          sorted(Counter(s["prm_rating"] for s in steps).values()), [200, 200, 200])
    check("run counts", Counter(r["condition"] for r in runs),
          Counter({"control": 2400, "target_delete": 2400, "placebo_delete": 1514}))

    # Label sets (paper Section 3)
    init = Counter(s["step_type_initial"] for s in steps)
    hc = Counter(s["step_type_human_calibrated"] for s in steps)
    check("initial labels 165/201/234",
          (init["essential"], init["redundant"], init["harmful"]), (165, 201, 234))
    check("calibrated labels 198/199/203",
          (hc["essential"], hc["redundant"], hc["harmful"]), (198, 199, 203))
    anchor_init = [s for s in steps
                   if as_int(s["prm_rating"]) == -1 and s["step_type_initial"] == "harmful"]
    anchor_hc = [s for s in steps
                 if as_int(s["prm_rating"]) == -1 and s["step_type_human_calibrated"] == "harmful"]
    check("anchor initial 178", len(anchor_init), 178)
    check("anchor calibrated 160", len(anchor_hc), 160)
    check("anchor overlap 154",
          sum(1 for s in anchor_init if s["step_type_human_calibrated"] == "harmful"), 154)
    check("label disagreement 164",
          sum(1 for s in steps if s["step_type_initial"] != s["step_type_human_calibrated"]), 164)

    # Headline effects (paper Tables 1-2)
    approx("overall target effect +7.21pp",
           100 * sum(as_float(s["target_effect"]) for s in steps) / 600, 7.21, 0.01)
    approx("anchor(initial) target effect +23.31pp",
           100 * sum(as_float(s["target_effect"]) for s in anchor_init) / 178, 23.31, 0.01)
    approx("anchor(calibrated) target effect +20.94pp",
           100 * sum(as_float(s["target_effect"]) for s in anchor_hc) / 160, 20.94, 0.01)
    matched_init = [s for s in anchor_init if s["placebo_eligible"].strip() == "1"]
    check("anchor(initial) matched 151", len(matched_init), 151)
    sem = [as_float(s["pure_semantic_effect"]) for s in matched_init]
    approx("anchor(initial) placebo-corrected +13.85pp", 100 * sum(sem) / len(sem), 13.85, 0.01)

    # Placebo structure (paper Section 2/3)
    check("eligible 511", sum(1 for s in steps if s["placebo_eligible"].strip() == "1"), 511)
    check("placebo runs 1514", sum(as_int(s["placebo_run_count"], 0) for s in steps), 1514)

    # Placebo cutoff composition (paper Table placebocomp)
    comp = {r["placebo_step_rating"]: as_int(r["runs"]) for r in read_csv(
        ROOT / "workstream_F_final_statistics" / "robustness" / "placebo_step_rating_composition.csv")}
    check("placebo cutoffs rating -1 == 0", comp.get("-1", 0), 0)
    check("placebo cutoffs rating +1 == 900", comp.get("1"), 900)

    # Natural prevalence (paper Table natprev)
    nat = {r["scope"]: r for r in read_csv(
        ROOT / "workstream_F_final_statistics" / "robustness" / "natural_prevalence.csv")}
    approx("natural-prevalence overall -0.52pp",
           as_float(nat["natural_prevalence"]["overall_target_effect_pp"]), -0.52, 0.01)

    # Policy claims (paper Section 7)
    budget = {(r["policy"], as_float(r["harm_budget"])): as_int(r["max_steps_deletable"])
              for r in read_csv(ROOT / "workstream_M7_policy_risk_coverage" / "policy_actual_prm_harm_budget.csv")}
    check("trained PRM 20 steps @1% (in-sample)",
          budget.get(("prm_threshold:qwen25_math_prm_7b", 0.01)), 20)
    calib = read_csv(ROOT / "workstream_M7_policy_risk_coverage" / "policy_calibration_test_split.csv")
    zero_at_all = all(
        as_float(r["calibration_coverage"]) == 0.0
        for r in calib
        if r["policy"] == "rating_first" or r["policy"].startswith("prm:")
    )
    check("calibrated: rating & all trained PRMs certify zero everywhere", zero_at_all, True)
    for stem, label in (
        ("prm_scores_math_shepherd_mistral_7b", "Math-Shepherd 600 ok"),
        ("prm_scores_llama31_8b_prm_deepseek", "RLHFlow 600 ok"),
    ):
        path = ROOT / "workstream_M1_actual_prm_audit" / f"{stem}.jsonl"
        n_ok = sum(
            1 for line in path.open(encoding="utf-8")
            if json.loads(line).get("status") == "ok"
        )
        check(label, n_ok, 600)
    audit = {r["signal"]: r for r in read_csv(
        ROOT / "workstream_M1_actual_prm_audit" / "prm_score_audit_metrics.csv")}
    approx("Math-Shepherd danger AUROC 0.47",
           as_float(audit["actual_prm:math_shepherd_mistral_7b"]["danger_auroc_highscore_warns"]), 0.4673, 0.001)
    approx("RLHFlow danger AUROC 0.51",
           as_float(audit["actual_prm:llama31_8b_prm_deepseek"]["danger_auroc_highscore_warns"]), 0.5057, 0.001)
    approx("5-PRM disagreement benefit AUPRC 0.34",
           as_float(audit["actual_prm_disagreement_negated"]["benefit_auprc"]), 0.3441, 0.001)
    e3 = next(r for r in calib if r["policy"] == "predictor_E" and as_float(r["budget"]) == 0.03)
    approx("calibrated: predictor E coverage 28.8% @3%",
           as_float(e3["calibration_coverage"]), 0.2881, 0.001)
    approx("calibrated: predictor E test harm 1.2% @3%",
           as_float(e3["test_harm_rate"]), 0.0116, 0.001)

    # Extension cohort sizes (paper appendix)
    m2 = sum(1 for _ in (ROOT / "workstream_M2_cross_generator" / "m2_generations.jsonl").open(encoding="utf-8"))
    check("M2 generations 2691", m2, 2691)

    # M10 long-CoT replication (paper: cross-generator section, limitation, appendix)
    m10_dir = ROOT / "workstream_M10_longcot_replication"
    m10_rows = [json.loads(line) for line in (m10_dir / "m10_generations.jsonl").open(encoding="utf-8") if line.strip()]
    check("M10 generations 2691", len(m10_rows), 2691)
    check("M10 unique taskIds", len({r["taskId"] for r in m10_rows}), 2691)
    unparseable = [r for r in m10_rows if r.get("statusReason", "").startswith("Unparseable")]
    check("M10 unparseable 28 (footnote: 99.0% parsed)", len(unparseable), 28)
    m10sum = {(r["group"], r["estimand"]): r for r in read_csv(m10_dir / "m10_effect_summary.csv")}
    approx("M10 overall target +3.4pp",
           as_float(m10sum[("overall", "target_effect")]["estimate_pp"]), 3.44, 0.01)
    approx("M10 anchor target +7.0pp",
           as_float(m10sum[("rating=-1_anchor", "target_effect")]["estimate_pp"]), 7.00, 0.01)
    approx("M10 anchor placebo-corrected +1.7pp",
           as_float(m10sum[("rating=-1_anchor", "pure_semantic_effect")]["estimate_pp"]), 1.67, 0.01)
    approx("M10 anchor placebo-corrected CI lower -4.0",
           as_float(m10sum[("rating=-1_anchor", "pure_semantic_effect")]["ci_lower_pp"]), -4.00, 0.01)
    approx("M10 anchor placebo-corrected CI upper +7.3",
           as_float(m10sum[("rating=-1_anchor", "pure_semantic_effect")]["ci_upper_pp"]), 7.33, 0.01)
    effects = read_csv(m10_dir / "m10_step_effects.csv")
    anchor = [r for r in effects if r["cell"] == "rating-1_anchor"]
    anchor_ctrl = sum(as_float(r["control_rate"]) for r in anchor) / len(anchor)
    approx("M10 anchor control rate 77.7%", anchor_ctrl, 0.777, 0.001)
    nonzero = sum(1 for r in effects if as_float(r["target_effect"]) != 0)
    check("M10 nonzero-effect steps 82/300", nonzero, 82)
    m10meta = json.loads((m10_dir / "m10_longcot_summary.json").read_text(encoding="utf-8"))
    approx("M10 sign agreement 67%", m10meta["sign_agreement_vs_qwen_nonzero"], 0.6667, 0.001)
    check("M10 nonzero pairs 33", m10meta["nonzero_pairs"], 33)
    # Appendix run count: cross-generator + long-CoT + strong controls + ProcessBench
    check("extension run total 9656", m2 + len(m10_rows) + 1862 + 2412, 9656)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} CONSISTENCY FAILURES:", FAILURES)
        sys.exit(1)
    print("ALL CONSISTENCY CHECKS PASS")


if __name__ == "__main__":
    main()
