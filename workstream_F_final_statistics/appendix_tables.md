# Workstream F Appendix Tables

## A1. Retained-cohort transition accounting

Retained means at least one condition is correct. This is diagnostic only.

| Cohort | Pairs | still wrong | still correct | wrong→correct | correct→wrong |
|---|---:|---:|---:|---:|---:|
| Retained | 1730 | excluded: 670 | 1149 | 377 | 204 |

## A2. Stratified full-cohort effects

| Dimension | Group | Steps | Pairs | Accuracy change (pp) | 95% CI (pp) |
|---|---|---:|---:|---:|---:|
| step_position | early | 201 | 804 | +4.98 | [-1.13, +11.18] |
| step_position | middle | 201 | 804 | +9.45 | [+3.31, +15.59] |
| step_position | late | 198 | 792 | +7.20 | [+1.75, +12.62] |
| step_length | short | 200 | 800 | +0.25 | [-5.21, +5.56] |
| step_length | middle | 200 | 800 | +9.62 | [+3.51, +15.66] |
| step_length | long | 200 | 800 | +11.75 | [+5.53, +17.97] |
| prefix_length | short | 200 | 800 | +5.38 | [-0.68, +11.33] |
| prefix_length | middle | 200 | 800 | +10.88 | [+4.75, +16.90] |
| prefix_length | long | 200 | 800 | +5.38 | [+0.00, +10.81] |
| control_correct_frequency | 0/4 | 224 | 896 | +33.37 | [+27.52, +39.20] |
| control_correct_frequency | 1/4 | 23 | 92 | +15.22 | [-1.25, +32.29] |
| control_correct_frequency | 2/4 | 27 | 108 | +9.26 | [-8.93, +26.25] |
| control_correct_frequency | 3/4 | 28 | 112 | -5.36 | [-20.69, +8.33] |
| control_correct_frequency | 4/4 | 298 | 1192 | -12.08 | [-15.49, -8.91] |

## A3. Exploratory predictive AUPRC

| Task | Model | AUPRC | 95% CI |
|---|---|---:|---:|
| danger | A: Rating-only | 0.139 | [0.097, 0.178] |
| danger | C: Rating + Type | 0.140 | [0.099, 0.188] |
| danger | D: Static context | 0.160 | [0.119, 0.208] |
| danger | E: Trajectory state (oracle/extra-compute) | 0.263 | [0.185, 0.341] |
| benefit | A: Rating-only | 0.432 | [0.371, 0.488] |
| benefit | C: Rating + Type | 0.380 | [0.324, 0.433] |
| benefit | D: Static context | 0.412 | [0.362, 0.462] |
| benefit | E: Trajectory state (oracle/extra-compute) | 0.478 | [0.410, 0.547] |

Predictive outcomes inherit the failed Judge gate. Model E is an extra-compute/oracle analysis.

## A4. Qualitative verification

- Verified cases: 8/8.
- Human-reviewed outputs: 78.
- Fixed-rule verification: True.
