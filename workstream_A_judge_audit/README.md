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

After blind re-review of all 28 original disagreements, the adjudicated binary
agreement was 88.0% (176/200), so the preregistered
hard-stop gate did not pass. See `judge_audit_report.md` for the confusion
matrix, condition diagnostics, and required follow-up.

The 28-record blind re-review can be reconstructed and reapplied from the
repository root:

```powershell
uv run --no-sync python ./build_judge_audit_disagreement_review.py
uv run --no-sync python ./apply_judge_audit_disagreement_review.py
uv run --no-sync python ./analyze_judge_audit.py
```
