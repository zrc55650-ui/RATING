# Placebo Eligibility and Selection-Bias Audit

- Eligible: **511** steps
- Skipped: **89** steps
- Balance threshold: absolute SMD ≥ 0.25
- Effect-difference threshold: absolute raw-effect difference ≥ 5 pp
- Resampling/permutation replicates: **5000**

## Largest balance differences

| Variable | Maximum absolute SMD |
|---|---:|
| Step position | 0.298 |
| Prefix tokens | 0.268 |
| Target-step tokens | 0.243 |
| Human-calibrated Step Type | 0.238 |
| Control stability | 0.234 |
| Rating × analysis Step Type | 0.209 |
| PRM rating | 0.159 |
| Control accuracy | 0.157 |
| Mean token change | 0.151 |
| Step-level recovery rate (defined subset) | 0.145 |

## Outcome differences: eligible minus skipped

| Metric | Eligible | Skipped | Difference | 95% CI |
|---|---:|---:|---:|---:|
| control_accuracy | 55.28 | 62.64 | -7.36 pp | [-17.51, +3.17] |
| target_accuracy | 63.26 | 65.45 | -2.19 pp | [-12.35, +7.91] |
| raw_target_effect | 7.97 | 2.81 | +5.17 pp | [-3.77, +13.77] |
| harm_rate | 15.49 | 13.00 | +2.48 pp | [-5.78, +10.43] |
| recovery_rate | 36.98 | 29.32 | +7.66 pp | [-8.32, +22.48] |
| mean_token_change | -22.15 | 39.64 | -61.78 tokens | [-125.69, -0.98] |
| completion_fraction | 93.32 | 91.15 | +2.17 pp | [-2.26, +7.07] |

## Decision

**Placebo conclusions must remain explicitly restricted to the 511-step matched cohort.** At least one pre-specified balance/effect threshold was crossed.

This audit cannot impute unobserved placebo outcomes for the 89 skipped steps.
