# Qwen3-8B Deletion Experiment: Cluster Bootstrap Results

- Source: `qwen3-8b_deletion_pairs.csv` (2,400 observations; 600 step clusters; 4 runs per step)
- Cluster unit: `sampleId` (treated as `step_id`)
- Step type: original `stepTypeLabel` in the source CSV
- Bootstrap: 5000 replicates; 600 clusters sampled with replacement per replicate; seed = 20260722
- CI: percentile 95% interval using the 2.5% and 97.5% quantiles
- Metrics: accuracy change; harm rate = P(deleted incorrect | control correct); recovery rate = P(deleted correct | control incorrect); mean token change = control tokens - deleted tokens (positive means tokens saved)
- Table cells show point estimate [95% CI]; accuracy change is in percentage points and rate metrics are percentages

| Group | Target steps | Pairs | Accuracy change (pp) | Harm rate | Recovery rate | Mean token change |
|---|---:|---:|---:|---:|---:|---:|
| Overall | 600 | 2400 | 7.21 [3.88, 10.58] | 15.08% [11.90%, 18.41%] | 36.01% [30.80%, 41.24%] | 12.98 [-19.65, 45.56] |
| rating=-1 | 200 | 800 | 22.00 [15.41, 28.42] | 14.86% [8.22%, 22.59%] | 38.66% [31.31%, 46.27%] | -5.90 [-60.21, 47.94] |
| rating=0 | 200 | 800 | 0.25 [-5.41, 5.90] | 17.05% [11.62%, 22.87%] | 32.73% [23.43%, 42.60%] | 21.40 [-30.66, 76.05] |
| rating=1 | 200 | 800 | -0.63 [-5.54, 4.21] | 13.40% [9.04%, 18.17%] | 33.49% [23.53%, 43.95%] | 23.44 [-38.82, 87.25] |
| step_type=Essential | 165 | 660 | -1.21 [-7.24, 4.78] | 17.84% [11.94%, 24.39%] | 29.06% [19.38%, 39.24%] | 40.33 [-28.36, 114.58] |
| step_type=Redundant | 201 | 804 | 1.12 [-3.87, 6.06] | 11.95% [7.83%, 16.56%] | 36.24% [25.77%, 47.37%] | -5.84 [-57.19, 44.71] |
| step_type=Harmful | 234 | 936 | 18.38 [12.28, 24.44] | 17.01% [10.72%, 23.92%] | 38.66% [31.65%, 45.92%] | 9.86 [-43.32, 62.29] |
| rating=-1 x step_type=Essential | 14 | 56 | 17.86 [-4.55, 44.44] | 20.00% [0.00%, 50.00%] | 38.89% [9.09%, 72.41%] | -23.36 [-108.75, 44.36] |
| rating=-1 x step_type=Redundant | 8 | 32 | 0.00 [-39.29, 40.00] | 19.23% [0.00%, 52.17%] | 83.33% [0.00%, 100.00%] | 159.84 [-136.06, 699.70] |
| rating=-1 x step_type=Harmful | 178 | 712 | 23.31 [16.57, 30.24] | 13.79% [6.70%, 22.17%] | 38.11% [30.34%, 45.95%] | -11.97 [-69.73, 44.80] |
| rating=0 x step_type=Essential | 41 | 164 | -6.10 [-20.27, 7.69] | 27.08% [11.58%, 44.07%] | 23.53% [7.78%, 42.47%] | 47.93 [-75.07, 201.70] |
| rating=0 x step_type=Redundant | 121 | 484 | 1.65 [-4.89, 8.33] | 13.19% [7.48%, 19.71%] | 32.28% [20.44%, 45.22%] | -17.18 [-79.15, 42.71] |
| rating=0 x step_type=Harmful | 38 | 152 | 2.63 [-12.14, 17.68] | 20.00% [7.83%, 33.95%] | 46.15% [22.22%, 71.74%] | 115.59 [5.13, 252.87] |
| rating=1 x step_type=Essential | 110 | 440 | -1.82 [-8.66, 4.79] | 14.84% [8.71%, 21.68%] | 29.23% [16.67%, 42.58%] | 45.61 [-47.60, 138.75] |
| rating=1 x step_type=Redundant | 72 | 288 | 0.35 [-7.24, 7.91] | 9.40% [3.98%, 16.05%] | 42.59% [22.22%, 65.86%] | -5.19 [-89.31, 78.94] |
| rating=1 x step_type=Harmful | 18 | 72 | 2.78 [-19.64, 25.03] | 26.32% [3.33%, 50.00%] | 35.29% [9.09%, 68.97%] | 2.56 [-300.15, 264.02] |
