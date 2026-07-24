# Workstream F Execution Report

The full statistics/tables/figures pipeline completed and passed all technical consistency checks. The paper-level freeze remains blocked by the failed Judge Audit.

## Candidate headline numbers

- Full cohort (600 steps / 2,400 pairs): overall target-deletion change **+7.21 pp** [+3.88, +10.58].
- Placebo-matched cohort (511 steps / 1,514 placebo runs): `rating=-1 × Harmful` pure semantic effect **+13.85 pp** [+6.95, +20.64].
- Annotation association: Cramer’s V **0.528**; off-diagonal share **34.5%**.

## Completed supporting work

- Judge Audit: completed on 200 outputs; gate **FAIL**.
- Qualitative cases: 8/8 verified from 78 human-reviewed outputs.
- Main tables, appendix tables, four main figures, figure-source CSVs, and `numbers_for_paper.json` regenerated from one script.

## Required before paper freeze

Remediate the Judge gate with an independent judge, symbolic evaluator, or expanded human review of each conclusion-critical subset, then rerun this script.
