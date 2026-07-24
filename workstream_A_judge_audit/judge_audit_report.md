# Judge Audit Report

## Gate decision

**FAIL.** Binary correctness agreement was **86.0%** (172/200); the largest absolute condition-level correctness-rate bias was **4.6 pp**.

Action: Do not freeze the current automated labels. Per the execution plan, use an independent judge, symbolic evaluator, or expanded human review of every conclusion-critical subset.

The hard-stop gate fails when agreement is < 90% or absolute condition bias is > 5 pp. Retaining the judge without remediation requires the stricter threshold of agreement >= 95% and bias < 3 pp; intermediate results require secondary review.

## Binary confusion matrix

| | Human correct | Human wrong |
|---|---:|---:|
| Judge correct | 77 | 18 |
| Judge wrong | 10 | 95 |

- False-positive rate among human-wrong outputs: 15.9%.
- False-negative rate among human-correct outputs: 11.5%.
- Automated correct rate: 47.5%.
- Human-adjudicated correct rate: 43.5%.

## Condition diagnostics

| condition | N | Agreement | Judge correct | Human correct | Bias (pp) |
|---|---:|---:|---:|---:|---:|
| control | 90 | 81.1% | 46.7% | 43.3% | +3.3 |
| placebo_delete | 23 | 95.7% | 34.8% | 30.4% | +4.3 |
| target_delete | 87 | 88.5% | 51.7% | 47.1% | +4.6 |

Bias is automated-judge correct rate minus human-adjudicated correct rate.

## Sampling-stratum diagnostics

| stratum | N | Agreement | Judge correct | Human correct | Bias (pp) |
|---|---:|---:|---:|---:|---:|
| abnormal_or_ambiguous | 20 | 100.0% | 20.0% | 20.0% | +0.0 |
| concordant_still_correct | 10 | 50.0% | 100.0% | 50.0% | +50.0 |
| concordant_still_wrong | 10 | 90.0% | 0.0% | 10.0% | -10.0 |
| correct_to_wrong | 50 | 84.0% | 50.0% | 42.0% | +8.0 |
| target_placebo_discordant | 60 | 91.7% | 51.7% | 50.0% | +1.7 |
| wrong_to_correct | 50 | 82.0% | 50.0% | 52.0% | -2.0 |

## PRM-rating diagnostics

| prm_rating | N | Agreement | Judge correct | Human correct | Bias (pp) |
|---|---:|---:|---:|---:|---:|
| -1 | 56 | 87.5% | 39.3% | 41.1% | -1.8 |
| 0 | 72 | 80.6% | 51.4% | 40.3% | +11.1 |
| 1 | 72 | 90.3% | 50.0% | 48.6% | +1.4 |

## Pair-level transition audit

Among 60 sampled control/target pairs, the automated and human transition labels matched for **41/60 (68.3%)**.

| Case | Stratum | Automated | Human |
|---|---|---|---|
| CW003 | correct_to_wrong | CW | WW |
| CW004 | correct_to_wrong | CW | WW |
| CW010 | correct_to_wrong | CW | WC |
| CW016 | correct_to_wrong | CW | WW |
| CW017 | correct_to_wrong | CW | WW |
| CW020 | correct_to_wrong | CW | CC |
| CW025 | correct_to_wrong | CW | WW |
| SC003 | concordant_still_correct | CC | WW |
| SC004 | concordant_still_correct | CC | CW |
| SC005 | concordant_still_correct | CC | WW |
| SW002 | concordant_still_wrong | WW | CW |
| WC005 | wrong_to_correct | WC | WW |
| WC010 | wrong_to_correct | WC | CC |
| WC011 | wrong_to_correct | WC | CW |
| WC012 | wrong_to_correct | WC | WW |
| WC014 | wrong_to_correct | WC | CC |
| WC022 | wrong_to_correct | WC | WW |
| WC024 | wrong_to_correct | WC | CC |
| WC025 | wrong_to_correct | WC | CC |

## Consequence for qualitative cases

Only 4 of the 78 outputs belonging to the provisional eight qualitative cases occur in the 200-output audit. Because the overall gate failed, the remaining 74 outputs require direct human review before any case is marked verified. `qualitative_case_audit.html` is the blinded review instrument; the four prior adjudications are prefilled.
