# Workstream F Final Tables

> **Submission gate: PASS_WITH_SENSITIVITY.** The Judge Audit hard-stop gate passed, but agreement remains below the stricter 95% retain-without-remediation threshold.

## Table 1. Full-cohort target deletion effects

Denominator: 600 target steps / 2,400 paired Control–Target outcomes. Step-type rows use the original analysis labels.

| Group | Steps | Pairs | Accuracy change (pp) | 95% CI (pp) | Harm rate | Recovery rate |
|---|---:|---:|---:|---:|---:|---:|
| Overall | 600 | 2400 | +7.21 | [+3.88, +10.58] | 15.08% | 36.01% |
| rating=-1 | 200 | 800 | +22.00 | [+15.41, +28.42] | 14.86% | 38.66% |
| rating=0 | 200 | 800 | +0.25 | [-5.41, +5.90] | 17.05% | 32.73% |
| rating=1 | 200 | 800 | -0.62 | [-5.54, +4.21] | 13.40% | 33.49% |
| step_type=Essential | 165 | 660 | -1.21 | [-7.24, +4.78] | 17.84% | 29.06% |
| step_type=Redundant | 201 | 804 | +1.12 | [-3.87, +6.06] | 11.95% | 36.24% |
| step_type=Harmful | 234 | 936 | +18.38 | [+12.28, +24.44] | 17.01% | 38.66% |
| rating=-1 x step_type=Harmful | 178 | 712 | +23.31 | [+16.57, +30.24] | 13.79% | 38.11% |

## Table 2. Legacy placebo-matched effect decomposition

Denominator: 511 matched target steps / 1,514 placebo runs. These are legacy shared-control contrasts; the latest own-control DiD results are reported in Workstream M12 and the manuscript.

| Group | Steps | Placebo runs | Target effect (pp) | Legacy placebo effect (pp) | Legacy pure semantic effect (pp, 95% CI) |
|---|---:|---:|---:|---:|---:|
| Overall | 511 | 1514 | +7.97 | -0.57 | +8.55 ([+4.83, +12.17]) |
| rating=-1 | 169 | 458 | +22.78 | +9.47 | +13.31 ([+6.71, +19.53]) |
| step_type=Harmful | 201 | 563 | +18.41 | +3.57 | +14.84 ([+8.83, +20.61]) |
| rating=-1 x step_type=Harmful | 151 | 399 | +23.84 | +9.99 | +13.85 ([+6.95, +20.64]) |

## Table 2b. Latest own-control DiD decomposition

Each placebo cutoff receives its own control. These are the latest mechanism estimates.

| Cohort | Own-control placebo (pp) | DiD semantic effect (pp, 95% CI) |
|---|---:|---:|
| Overall | +0.46 | +7.52 ([+2.79, +12.36]) |
| rating=-1 × Harmful anchor | -1.60 | +25.44 ([+16.06, +34.88]) |

## Table 3. Judge Audit

| Outputs | Agreement | Precision | Recall | F1 | TP | TN | FP | FN | Max condition bias | Pair-transition agreement | Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 200 | 93.0% | 91.6% | 93.5% | 92.6% | 87 | 99 | 8 | 6 | 2.3 pp | 90.0% | **PASS** |

The preregistered hard-stop gate passed. Because agreement remains below the stricter 95% retain-without-remediation threshold, Tables 1–2 should be accompanied by the audit diagnostics and described as passing with sensitivity qualification.
