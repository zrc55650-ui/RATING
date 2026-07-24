# Workstream F Final Tables

> **Submission gate: FAIL.** These tables are reproducible candidate estimates, but automated outcome labels are not frozen because Judge-human agreement is 88.0%.

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

## Table 2. Placebo-matched effect decomposition

Denominator: 511 matched target steps / 1,514 placebo runs. All effects are percentage points; pure semantic = Target − Placebo.

| Group | Steps | Placebo runs | Target effect (pp) | Placebo effect (pp) | Pure semantic effect (pp, 95% CI) |
|---|---:|---:|---:|---:|---:|
| Overall | 511 | 1514 | +7.97 | -0.57 | +8.55 ([+4.83, +12.17]) |
| rating=-1 | 169 | 458 | +22.78 | +9.47 | +13.31 ([+6.71, +19.53]) |
| step_type=Harmful | 201 | 563 | +18.41 | +3.57 | +14.84 ([+8.83, +20.61]) |
| rating=-1 x step_type=Harmful | 151 | 399 | +23.84 | +9.99 | +13.85 ([+6.95, +20.64]) |

## Table 3. Judge Audit

| Outputs | Agreement | Precision | Recall | F1 | TP | TN | FP | FN | Max condition bias | Pair-transition agreement | Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 200 | 88.0% | 84.2% | 89.9% | 87.0% | 80 | 96 | 15 | 9 | 3.4 pp | 71.7% | **FAIL** |

The preregistered hard stop is triggered by agreement below 90%. Do not present Tables 1–2 as audit-cleared estimates until remediation is complete.
