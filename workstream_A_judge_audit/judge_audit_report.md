# Judge Audit Report

## Gate decision

**PASS.** Binary correctness agreement was **93.5%** (187/200); the largest absolute condition-level correctness-rate bias was **2.3 pp**.

Action: The hard-stop gate passed and the project-designated adjudicated file is frozen. Because agreement is below 95%, report the audit diagnostics as a sensitivity boundary and do not claim evaluator equivalence.

The hard-stop gate fails when agreement is < 90% or absolute condition bias is > 5 pp. Retaining the judge without remediation requires the stricter threshold of agreement >= 95% and bias < 3 pp; intermediate results require secondary review.

## Binary confusion matrix

| | Human correct | Human wrong |
|---|---:|---:|
| Judge correct | 88 | 7 |
| Judge wrong | 6 | 99 |

- False-positive rate among human-wrong outputs: 6.6%.
- False-negative rate among human-correct outputs: 6.4%.
- Automated correct rate: 47.5%.
- Human-adjudicated correct rate: 47.0%.

## Condition diagnostics

| condition | N | Agreement | Judge correct | Human correct | Bias (pp) |
|---|---:|---:|---:|---:|---:|
| control | 90 | 92.2% | 46.7% | 47.8% | -1.1 |
| placebo_delete | 23 | 100.0% | 34.8% | 34.8% | +0.0 |
| target_delete | 87 | 93.1% | 51.7% | 49.4% | +2.3 |

Bias is automated-judge correct rate minus human-adjudicated correct rate.

## Sampling-stratum diagnostics

| stratum | N | Agreement | Judge correct | Human correct | Bias (pp) |
|---|---:|---:|---:|---:|---:|
| abnormal_or_ambiguous | 20 | 100.0% | 20.0% | 20.0% | +0.0 |
| concordant_still_correct | 10 | 80.0% | 100.0% | 80.0% | +20.0 |
| concordant_still_wrong | 10 | 100.0% | 0.0% | 0.0% | +0.0 |
| correct_to_wrong | 50 | 96.0% | 50.0% | 50.0% | +0.0 |
| target_placebo_discordant | 60 | 95.0% | 51.7% | 53.3% | -1.7 |
| wrong_to_correct | 50 | 88.0% | 50.0% | 50.0% | +0.0 |

## PRM-rating diagnostics

| prm_rating | N | Agreement | Judge correct | Human correct | Bias (pp) |
|---|---:|---:|---:|---:|---:|
| -1 | 56 | 92.9% | 39.3% | 42.9% | -3.6 |
| 0 | 72 | 93.1% | 51.4% | 50.0% | +1.4 |
| 1 | 72 | 94.4% | 50.0% | 47.2% | +2.8 |

## Pair-level transition audit

Among 60 sampled control/target pairs, the automated and human transition labels matched for **55/60 (91.7%)**.

| Case | Stratum | Automated | Human |
|---|---|---|---|
| CW010 | correct_to_wrong | CW | WC |
| SC003 | concordant_still_correct | CC | WW |
| WC010 | wrong_to_correct | WC | CW |
| WC014 | wrong_to_correct | WC | CW |
| WC024 | wrong_to_correct | WC | CW |

## Direct label-substitution sensitivity

This diagnostic replaces the automated label only for the 200 audited outputs and leaves the other 6,114 outputs unchanged. It is a local perturbation check, not a population-level bias correction, because the audit sample was purposively stratified.

| Scope | Estimand | N | Original | Substituted | Change (pp) |
|---|---|---:|---:|---:|---:|
| full run table | control_correct_rate | 2400 | +56.38 | +56.42 | +0.04 |
| full run table | target_delete_correct_rate | 2400 | +63.58 | +63.50 | -0.08 |
| full run table | placebo_delete_correct_rate | 1514 | +55.55 | +55.55 | +0.00 |
| full cohort | target_minus_control | 2400 | +7.21 | +7.08 | -0.12 |
| placebo-matched cohort | target_effect | 511 | +7.97 | +7.93 | -0.05 |
| placebo-matched cohort | placebo_effect | 511 | -0.57 | -0.57 | +0.00 |
| placebo-matched cohort | pure_semantic_effect | 511 | +8.55 | +8.50 | -0.05 |

## Consequence for qualitative cases

Only 4 of the 78 outputs belonging to the provisional eight qualitative cases occurred in the 200-output audit. Because the overall gate failed, Workstream E subsequently obtained direct human labels for all 78 case outputs. The final 8/8 cases passed their fixed family-specific rules. This separate verification supports the qualitative case narratives, but it does not clear the aggregate automated-outcome gate.
