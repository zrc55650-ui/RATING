# Workstream C: Step-Level Stability Analysis

This folder contains the pre-Audit stability analysis based on four paired
Control/Target Deletion runs for each of 600 target steps.

## Frozen categories

- **Strongly beneficial:** Wrong-to-Correct count ≥ 2 and Correct-to-Wrong count = 0
- **Weakly beneficial:** Wrong-to-Correct count = 1 and Correct-to-Wrong count = 0
- **Strongly harmful:** Correct-to-Wrong count ≥ 2 and Wrong-to-Correct count = 0
- **Weakly harmful:** Correct-to-Wrong count = 1 and Wrong-to-Correct count = 0
- **Mixed / unstable:** both transition directions occur
- **Stable no-change:** neither transition direction occurs

## Files

- `step_stability_labels.csv`: one stability label per target step (600 rows)
- `step_stability_by_group.csv`: category distributions by rating, Step Type,
  rating × Step Type, and Control correctness frequency
- `step_stability_report.md`: main findings and interpretation boundary
- `step_stability_heatmap.svg`: editable figure source
- `step_stability_heatmap.pdf`: paper-ready figure

## Interpretation boundary

Four runs measure empirical consistency; they do not precisely estimate an
individual step's true treatment probability. Results currently use automatic
Judge labels. Human Judge Audit is not required to generate these outputs, but
an audit-corrected sensitivity check is required before final submission.
