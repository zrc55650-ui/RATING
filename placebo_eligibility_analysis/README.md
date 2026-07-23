# Workstream D: Placebo Eligibility and Selection Bias

This directory contains the complete pre-Audit output package for the
placebo-eligibility and selection-bias analysis.

## Files

- `placebo_eligibility_step_table.csv`: step-level eligibility indicators,
  covariates, outcome summaries, and placebo run counts for all 600 target
  steps.
- `placebo_eligibility_balance.csv`: eligible-versus-skipped balance
  diagnostics, including standardized differences and permutation tests.
- `placebo_eligibility_effect_differences.csv`: cluster-bootstrap outcome
  differences between eligible and skipped steps (5,000 replicates).
- `placebo_eligibility_audit.md`: human-readable summary, threshold checks,
  and interpretation.
- `placebo_eligibility_loveplot.svg`: editable vector balance plot.
- `placebo_eligibility_loveplot.pdf`: publication-ready balance plot.

## Cohort and interpretation

- Placebo eligible: 511 steps.
- Placebo skipped: 89 steps.
- Clustering unit: `step_id`.
- Bootstrap/permutation replicates: 5,000.

At least one pre-specified balance or effect-difference threshold was crossed.
Therefore, placebo conclusions must be restricted to the 511-step matched
cohort; the analysis does not impute placebo outcomes for the 89 skipped
steps.

Human Audit results are not required for the metadata balance diagnostics.
Accuracy-based comparisons should receive the planned Audit sensitivity
analysis before final submission.
