# Judge Audit disagreement re-review

- Records in the comparison table: **28**
- Exact human labels changed in the comparison table: **5/28**
- Binary correctness labels changed in the comparison table: **5/28**
- Reviewed disagreements that agree with the automated judge after review: **16/28**
- The latest 200-row human re-adjudication is the authoritative source for the overall audit result.
- The comparison table is retained as a review audit trail and is not used to overwrite the latest 200-row labels.

The overall Judge Audit result must be recomputed with `analyze_judge_audit.py` from
`judge_audit_sampling_manifest.csv` and `judge_audit_adjudicated.csv`.
