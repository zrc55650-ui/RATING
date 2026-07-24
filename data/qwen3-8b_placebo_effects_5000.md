# Qwen3-8B Placebo deletion effects

- Eligible cohort: 511 of 600 target steps; 89 steps with no length-matched non-target step were skipped
- Placebo selection: official Qwen3 tokenizer; non-target step length within 0.8-1.2 times target length; up to four random matches per target; seed = 20260723
- Placebo runs: 1,514; one independent deletion continuation per selected Placebo step; judged with qwen/qwen3-8b
- Step-level effects use the mean of four control runs, four target deletion runs, and all available Placebo runs for that target
- Bootstrap: 5000 replicates, resampling target steps with replacement within each reported group; seed = 20260722; percentile 95% CI
- Effect cells are percentage points: point estimate [95% CI]

| Group | Target steps | Placebo runs | Target Effect | Placebo Effect | Pure Semantic Effect |
|---|---:|---:|---:|---:|---:|
| Overall | 511 | 1514 | 7.97 [4.26, 11.69] | -0.57 [-4.13, 3.13] | 8.55 [4.83, 12.17] |
| rating=-1 | 169 | 458 | 22.78 [16.12, 29.59] | 9.47 [2.86, 15.93] | 13.31 [6.71, 19.53] |
| rating=0 | 176 | 539 | 0.99 [-5.40, 7.39] | -5.63 [-12.12, 0.76] | 6.63 [0.19, 13.21] |
| rating=1 | 166 | 517 | 0.30 [-5.27, 5.87] | -5.42 [-11.19, 0.70] | 5.72 [-0.05, 11.40] |
| step_type=Harmful | 201 | 563 | 18.41 [11.94, 24.88] | 3.57 [-2.57, 9.74] | 14.84 [8.83, 20.61] |
| rating=-1 x step_type=Harmful | 151 | 399 | 23.84 [16.89, 30.96] | 9.99 [2.92, 17.00] | 13.85 [6.95, 20.64] |
