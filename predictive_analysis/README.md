# Workstream B: Predictive Analysis

This folder contains the pre-Audit outputs for the two deletion-outcome
prediction tasks:

- **Dangerous deletion:** Control is correct and Target Deletion is wrong.
- **Beneficial deletion:** Control is wrong and Target Deletion is correct.

## Validation design

- 5-fold grouped cross-validation by `problem_id`
- all four runs for a target step remain in the same fold
- L2-regularized logistic regression
- balanced class weights; no SMOTE
- preprocessing fitted within each training fold
- 5,000 paired fold-bootstrap replicates for confidence intervals

## Files

- `predictive_fold_assignments.csv`: fixed fold membership for 600 target steps
- `predictive_run_level_dataset.csv`: 2,400 Control/Target paired runs
- `predictive_metrics.csv`: AUROC, AUPRC, Brier score, ECE, specificity,
  precision coverage, and model-comparison intervals
- `predictive_predictions.csv`: out-of-fold probabilities for all five models
- `predictive_analysis_report.md`: analysis summary and interpretation
- `risk_coverage_{danger,benefit}.csv`: figure source data
- `risk_coverage_{danger,benefit}.svg`: editable vector figures
- `risk_coverage_{danger,benefit}.pdf`: paper-ready figures

## Interpretation boundary

These results use the automatic Judge labels. Human Judge Audit is not
required to generate the analysis, but an audit-corrected sensitivity check
is required before final submission.

Model E uses the correctness frequency from four Control runs. It is an
extra-compute/oracle trajectory-state analysis, not a zero-cost pruning
policy.
