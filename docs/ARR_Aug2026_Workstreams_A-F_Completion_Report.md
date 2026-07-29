# ARR Aug 2026 Workstreams A–F Completion Report

## Scope and single source of truth

- Scope: Workstreams A–F only. Workstreams G–H are intentionally excluded.
- Final human audit truth: `judge_audit_adjudicated.csv` in the workspace root.
- The original GBK-encoded bytes are preserved as
  `judge_audit_adjudicated.original_gbk.csv`; the canonical file was normalized
  to UTF-8 without changing its 200 IDs or labels.
- Root analytical inputs are authoritative. Workstream directories contain
  synchronized copies only.
- Random seed: `20260723`; bootstrap/permutation replicates: 5,000.

## Completion status

| Workstream | Status | Required outputs |
|---|---|---|
| A — Judge Audit | Complete; PASS with sensitivity qualification | 6/6 |
| B — Predictive Analysis | Complete | 6/6 |
| C — Step-Level Stability | Complete | 4/4 |
| D — Placebo Eligibility | Complete | 4/4 |
| E — Qualitative Cases | Complete; 8/8 verified | 4/4 |
| F — Final Statistics | Complete; technical consistency PASS | Tables, four main figures, source CSVs, and `numbers_for_paper.json` |

All 36 explicitly named A–F deliverables in the execution plan exist and are
non-empty.

## Workstream A — final audit result

- Outputs: 200; binary agreement: 186/200 = **93.0%**.
- Confusion matrix: TP 87, TN 99, FP 8, FN 6.
- Correct-class precision: **91.6%**; recall: **93.5%**; F1: **92.6%**.
- Maximum absolute condition bias: **2.3 pp**.
- Pair-transition agreement: **90.0%**.
- Hard-stop gate: **PASS**.
- Review tier: **PASS_WITH_SENSITIVITY**, because agreement is below the
  stricter 95% retain-without-remediation threshold.

### Direct audited-label substitution sensitivity

This check replaces only the 200 audited labels and leaves the other 6,114 run
labels unchanged. It is a local perturbation, not a population correction.

- Full-cohort Target − Control: **+7.21 pp → +7.12 pp** (−0.08 pp).
- Matched-cohort target effect: **+7.97 pp → +7.97 pp** (+0.00 pp).
- Matched-cohort placebo effect: **−0.57 pp → −0.52 pp** (+0.05 pp).
- Matched-cohort pure semantic effect: **+8.55 pp → +8.50 pp** (−0.05 pp).

The known audited errors do not materially change the headline aggregate
effects. Full details are in
`judge_audit_label_substitution_sensitivity.csv` and `judge_audit_report.md`.

## Workstream B — predictive analysis

- Five-fold grouped cross-validation by `problem_id`; no run leakage.
- Danger task: 1,353 runs, 204 positives (15.1%).
- Benefit task: 1,047 runs, 377 positives (36.0%).
- The prespecified inclusion threshold is met for both tasks.
- Model E remains an oracle/extra-compute upper bound because it uses four
  Control runs.

## Workstream C — stability

- Strongly beneficial: 99/600 (16.5%).
- Strongly harmful: 57/600 (9.5%).
- Mixed/unstable: 9/600 (1.5%).
- Stable no-change: 377/600 (62.8%).
- Among 298 steps with Control 4/4 correct, 54 (18.1%) show at least one harmful
  transition and no recovery.

## Workstream D — placebo eligibility

- Eligible: 511 steps; skipped: 89 steps.
- Placebo runs: 1,514.
- Prespecified balance/effect thresholds are crossed; all placebo conclusions
  must remain restricted to the 511-step matched cohort.

## Workstream E — qualitative cases

- 78/78 case-specific outputs reviewed.
- 8/8 cases pass their fixed family-specific rules:
  - 3 Negative Anchor;
  - 2 Generic Restart;
  - 2 Stable-correct Harmed;
  - 1 High-rated / Redundant Ambiguity.
- Final outputs:
  `qualitative_cases_verified.csv`, `qualitative_cases.md`, and
  `qualitative_cases_appendix.tex`.

## Workstream F — frozen numerical outputs

- Full cohort: 600 steps / 2,400 pairs.
- Retained cohort: 1,730 pairs.
- Placebo-matched cohort: 511 steps / 1,514 placebo runs.
- Overall full-cohort Target − Control effect:
  **+7.21 pp** [**+3.88, +10.58**].
- `rating=-1 × Harmful` matched pure semantic effect:
  **+13.85 pp** [**+6.95, +20.64**].
- PRM-rating × human-calibrated Step Type:
  Cramer’s V **0.528**; off-diagonal share **34.5%**.
- Technical consistency audit: **PASS**.
- Final analysis status: **READY_TO_FREEZE**, with the Judge Audit sensitivity
  qualification stated above.

`numbers_for_paper.json` is the sole numerical source for final tables and
figure-source CSVs.
