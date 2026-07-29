# Workstream A – Judge Audit

This folder contains the required Judge Audit deliverables:

- `judge_audit_sampling_manifest.csv`
- `judge_audit_blinded_sheet_A.csv`
- `judge_audit_blinded_sheet_B.csv`
- `judge_audit_adjudicated.csv`
- `judge_audit_report.md`
- `judge_audit_confusion_matrix.pdf`
- `judge_audit_confusion_matrix.svg`
- `judge_audit_confusion_matrix.png`
- `judge_audit_disagreement_review_completed.csv`
- `judge_audit_disagreement_review_comparison.csv`
- `judge_audit_disagreement_review_report.md`
- `judge_audit_adjudication_completed_pre_disagreement_review.csv`

The latest 200-row human re-adjudication is the current audit truth. Its binary
agreement with the automated judge is 93.0% (186/200), so the preregistered
hard-stop gate passes. Because this remains below the stricter 95% threshold,
report the audit diagnostics as a sensitivity qualification. See
`judge_audit_report.md` for the confusion matrix and condition diagnostics.

The current audit report can be recomputed from the latest 200-row labels at
the repository root:

```powershell
uv run --no-sync python ./analyze_judge_audit.py
```
