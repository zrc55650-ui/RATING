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
        for r in calib if r["policy"] in ("rating_first", "trained_prm_score")
    )
    check("calibrated: rating & PRM certify zero everywhere", zero_at_all, True)
    e3 = next(r for r in calib if r["policy"] == "predictor_E" and as_float(r["budget"]) == 0.03)
    approx("calibrated: predictor E coverage 28.8% @3%",
           as_float(e3["calibration_coverage"]), 0.2881, 0.001)
    approx("calibrated: predictor E test harm 1.2% @3%",
           as_float(e3["test_harm_rate"]), 0.0116, 0.001)

    # Extension cohort sizes (paper appendix)
    m2 = sum(1 for _ in (ROOT / "workstream_M2_cross_generator" / "m2_generations.jsonl").open(encoding="utf-8"))
    check("M2 generations 2691", m2, 2691)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} CONSISTENCY FAILURES:", FAILURES)
        sys.exit(1)
    print("ALL CONSISTENCY CHECKS PASS")


if __name__ == "__main__":
    main()
