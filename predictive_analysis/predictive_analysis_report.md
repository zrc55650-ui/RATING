# Predictive Analysis Report

- Seed: `20260723`
- Validation: 5-fold grouped cross-validation by `problem_id`.
- Model: L2-regularized logistic regression with fold-local preprocessing.
- Class imbalance: balanced class weights; no SMOTE.
- Confidence intervals: 5,000 paired bootstrap resamples of the five held-out folds.
- Model E uses four-run Control stability and is an oracle/extra-compute upper bound.

## Danger deletion

Runs: **1353**; positives: **204** (15.1%).

| Model | AUROC | AUPRC | Brier | ECE |
|---|---:|---:|---:|---:|
| A: Rating-only | 0.423 [0.355, 0.491] | 0.139 [0.097, 0.178] | 0.254 [0.248, 0.259] | 0.346 [0.294, 0.390] |
| B: Type-only | 0.551 [0.502, 0.603] | 0.208 [0.170, 0.245] | 0.249 [0.240, 0.256] | 0.344 [0.289, 0.394] |
| C: Rating + Type | 0.431 [0.394, 0.468] | 0.140 [0.099, 0.188] | 0.257 [0.244, 0.272] | 0.345 [0.285, 0.399] |
| D: Static context | 0.512 [0.486, 0.543] | 0.160 [0.119, 0.208] | 0.249 [0.242, 0.256] | 0.334 [0.288, 0.376] |
| E: Trajectory state (oracle/extra-compute) | 0.585 [0.527, 0.653] | 0.263 [0.185, 0.341] | 0.228 [0.221, 0.237] | 0.308 [0.256, 0.347] |

AUPRC increments:

- C-A: +0.001 [-0.028, +0.026]
- D-C: +0.020 [+0.009, +0.033]
- E-D: +0.103 [+0.048, +0.160]
- E-A: +0.124 [+0.047, +0.187]

Pre-specified inclusion threshold: **met**.

## Benefit deletion

Runs: **1047**; positives: **377** (36.0%).

| Model | AUROC | AUPRC | Brier | ECE |
|---|---:|---:|---:|---:|
| A: Rating-only | 0.520 [0.472, 0.568] | 0.432 [0.371, 0.488] | 0.251 [0.249, 0.254] | 0.137 [0.108, 0.182] |
| B: Type-only | 0.503 [0.462, 0.549] | 0.407 [0.362, 0.452] | 0.251 [0.247, 0.255] | 0.135 [0.106, 0.176] |
| C: Rating + Type | 0.484 [0.444, 0.536] | 0.380 [0.324, 0.433] | 0.255 [0.249, 0.260] | 0.130 [0.102, 0.175] |
| D: Static context | 0.566 [0.505, 0.609] | 0.412 [0.362, 0.462] | 0.252 [0.243, 0.266] | 0.169 [0.141, 0.201] |
| E: Trajectory state (oracle/extra-compute) | 0.599 [0.574, 0.618] | 0.478 [0.410, 0.547] | 0.246 [0.238, 0.257] | 0.176 [0.146, 0.206] |

AUPRC increments:

- C-A: -0.052 [-0.116, +0.030]
- D-C: +0.032 [-0.014, +0.068]
- E-D: +0.065 [+0.033, +0.091]
- E-A: +0.046 [+0.001, +0.082]

Pre-specified inclusion threshold: **met**.

## Interpretation boundary

These are predictive, not causal, comparisons. Model E is not a zero-cost pruning policy because it uses four Control runs. Audit-corrected labels remain pending.
