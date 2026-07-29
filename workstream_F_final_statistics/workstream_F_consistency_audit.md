# Workstream F Consistency Audit

- Technical consistency: **PASS**.
- Judge Audit submission gate: **PASS**.
- Final freeze status: **READY_TO_FREEZE**.
- Formal second-human numerical signoff: **NOT RECORDED** (independent computational recalculation and figure inspection completed).

A technical PASS means denominators, signs, cohorts, label scopes, CIs, and output provenance agree. It does not override the Judge Audit gate.

| Check | Status | Detail |
|---|---|---|
| full_cohort_steps | PASS | observed=600; expected=600 |
| full_cohort_pairs | PASS | observed=2400; expected=2400 |
| run_condition_denominators | PASS | observed={'control': 2400, 'target_delete': 2400, 'placebo_delete': 1514} |
| retained_cohort_pairs | PASS | observed=1730; expected=1730 |
| transition_partition | PASS | observed={'still_wrong': 670, 'still_correct': 1149, 'correct_to_wrong': 204, 'wrong_to_correct': 377} |
| placebo_matched_denominators | PASS | eligible_steps=511; placebo_runs=1514 |
| analysis_type_denominators | PASS | analysis_types={'essential': 165, 'redundant': 201, 'harmful': 234} |
| initial_vs_calibrated_type_scope | PASS | calibrated_types={'harmful': 203, 'redundant': 199, 'essential': 198}; changed=164 |
| placebo_effect_identity | PASS | Pure semantic effect equals Target effect minus Placebo effect. |
| confidence_interval_order | PASS | All displayed point estimates lie within their 95% CIs. |
| bootstrap_replicates | PASS | expected=5000 |
| qualitative_cases | PASS | status=VERIFIED; cases=8; outputs=78 |
| judge_audit_complete | PASS | gate=PASS; n=200 |
| single_numeric_source | PASS | Main/appendix tables and figure-source CSVs are generated from the same in-memory rows written to numbers_for_paper.json. |

## Label-scope decision

- Table 1 step-type effects use `step_type_analysis` (the original analysis label): Essential 165, Redundant 201, Harmful 234.
- Figure 2 uses `step_type_human_calibrated`: Essential 198, Redundant 199, Harmful 203. A total of 164/600 labels differ between these fields.

## Freeze decision

Judge Audit passed the hard-stop gate: binary agreement was 93.0% and maximum condition bias was 2.3 pp. The project-designated adjudicated file is frozen as the single audit truth source. Because agreement is below 95%, the result is classified as `PASS_WITH_SENSITIVITY` and the audit diagnostics remain a required sensitivity qualification.
