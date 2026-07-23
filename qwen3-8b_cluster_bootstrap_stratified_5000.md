# Stratified target-step cluster bootstrap

- Source: `qwen3-8b_deletion_pairs.csv`; 600 target steps; 4 runs per step; 2,400 pairs
- Bootstrap: 5000 replicates; each replicate samples 600 target steps with replacement and retains all four runs; seed = 20260722
- CI: percentile 95% interval; cells show point estimate [95% CI] in percentage points
- Step length: control prompt tokens minus deleted prompt tokens; prefix length: deleted-condition prompt tokens
- Length tertiles: rank-based at the step level (200 steps each; ties broken deterministically by sampleId)
- Transition counts are observed counts in the original data, not bootstrap averages

| Dimension | Group | Definition | Steps | Pairs | Accuracy change (pp) | Wrong to correct | Correct to wrong |
|---|---|---|---:|---:|---:|---:|---:|
| step_position | early | early | 201 | 804 | 4.98 [-1.13, 11.18] | 127 | 87 |
| step_position | middle | middle | 201 | 804 | 9.45 [3.31, 15.59] | 144 | 68 |
| step_position | late | late | 198 | 792 | 7.20 [1.75, 12.62] | 106 | 49 |
| step_length | short | ranks 1-200; 4-27 prompt tokens | 200 | 800 | 0.25 [-5.21, 5.56] | 72 | 70 |
| step_length | middle | ranks 201-400; 27-40 prompt tokens | 200 | 800 | 9.63 [3.51, 15.66] | 148 | 71 |
| step_length | long | ranks 401-600; 40-648 prompt tokens | 200 | 800 | 11.75 [5.53, 17.97] | 157 | 63 |
| prefix_length | short | ranks 1-200; 272-431 prompt tokens | 200 | 800 | 5.38 [-0.68, 11.33] | 121 | 78 |
| prefix_length | middle | ranks 201-400; 432-577 prompt tokens | 200 | 800 | 10.88 [4.75, 16.90] | 155 | 68 |
| prefix_length | long | ranks 401-600; 578-1229 prompt tokens | 200 | 800 | 5.38 [0.00, 10.81] | 101 | 58 |
| control_correct_frequency | 0/4 | 0 of 4 control runs correct | 224 | 896 | 33.37 [27.52, 39.20] | 299 | 0 |
| control_correct_frequency | 1/4 | 1 of 4 control runs correct | 23 | 92 | 15.22 [-1.25, 32.29] | 28 | 14 |
| control_correct_frequency | 2/4 | 2 of 4 control runs correct | 27 | 108 | 9.26 [-8.93, 26.25] | 31 | 21 |
| control_correct_frequency | 3/4 | 3 of 4 control runs correct | 28 | 112 | -5.36 [-20.69, 8.33] | 19 | 25 |
| control_correct_frequency | 4/4 | 4 of 4 control runs correct | 298 | 1192 | -12.08 [-15.49, -8.91] | 0 | 144 |
