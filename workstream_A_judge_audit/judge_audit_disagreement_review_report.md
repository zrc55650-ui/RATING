# Judge Audit disagreement re-review

- Records independently re-reviewed: **28/28**
- Exact human labels changed: **5/28**
- Binary correctness labels changed: **4/28**
- Reviewed disagreements that now agree with the automated judge: **4/28**
- Original 200-row adjudication preserved as `judge_audit_adjudication_completed_pre_disagreement_review.csv`
- Updated 200-row adjudication written to `judge_audit_adjudicated.csv`

This report records the blind re-review result; it does not itself determine the
Judge Audit gate. Run `analyze_judge_audit.py` to recompute the gate from all 200
records.
