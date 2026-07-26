# M12: Placebo Own-Controls and Difference-in-Differences

Review issue (round 2, major issue 2): the frozen placebo contrast compares
generation from prefix `1:p-1` against the **target's** control (prefix
`1:t`), so it confounds "removing step p" with "moving the cutoff" — placebo
cutoffs before the target silently delete the target too, and cutoffs after
it carry extra steps the control never shows. The proper matched estimand is
a difference-in-differences with the placebo cutoff's own control:

    DiD semantic = (Y_{t-1} - Y_t) - (Y_{p-1} - Y_p)

## New data

C_p runs (prefix kept through p, truncated after) mirroring every frozen
placebo run 1:1, generated with each cohort's frozen generator, sampling
parameters, prompts, and judge:

| Cohort | C_p runs | Generator |
|---|---|---|
| Primary | 1,514 (1,513 returned; 1 provider error) | qwen/qwen3-8b, /no_think |
| M2 cross-generator | 891 | microsoft/phi-4 |
| M6 ProcessBench | 612 | qwen/qwen3-8b, /no_think |
| M10 long-CoT | 891 | R1-Distill-Qwen-14B (local vLLM) |
| M11 thinking-toggle | 891 (part of the M11 batch) | qwen/qwen3-8b, thinking |

## Headline results (primary cohort, `c4_primary_did_summary.csv`)

| Group | target | placebo vs target-control (legacy) | placebo vs own control | DiD semantic |
|---|---|---|---|---|
| Overall (511) | +7.97 | -0.57 | +0.46 | +7.52 [+2.79, +12.36] |
| Anchors -1xHarmful (151) | +23.84 | +9.99 | **-1.60 [-6.46, +3.20]** | **+25.44 [+16.06, +34.88]** |
| rating=0 (176) | +0.99 | -5.63 | +2.84 | -1.85 (n.s.) |
| rating=+1 (166) | +0.30 | -5.42 | -0.90 | +1.20 (n.s.) |

The legacy "+10pp restart component" decomposes by cutoff side: anchor-group
placebo cutoffs **before** the target show +21.1pp against the shared
control (their prefixes drop the anchor too), cutoffs **after** it show
-6.8pp; own-control effects are null on both sides (-5.2 / +4.3). There is
no restart benefit; the anchor's content does all the work. The
single-control design *understated* the anchor semantic effect (+13.9 -> 
+25.4) and manufactured spurious rating-0/+1 "semantic" effects that vanish
under DiD.

Replications: phi-4 anchors own-placebo -1.25 (n.s.), DiD +34.92
[+25.83, +44.67] (`c4_m2_did_summary.csv`). M4 strong-control C2 placebos
against own controls: negative_anchor -0.73, stable_correct -0.83,
neutral_comparison +3.85, overall +0.76 — all n.s.
(`c4_m4_c2_own_summary.csv`); the fragile-neutral group's raw uplifts are
regression-to-the-mean from fragility conditioning, not restart benefits.

## Drift check

C_p runs are a fresh generation batch. 128 C_p runs have byte-identical
prompts to frozen target_delete runs (p = t-1): new 67.2% vs frozen 64.1%
(+3.1pp, SE ~4pp) — consistent with zero and small against the contrasts.
A +3.1pp uniform drift adjustment would move the anchor own-placebo effect
from -1.6 to ~+1.5 and the DiD from +25.4 to ~+22.3, leaving every
qualitative conclusion unchanged.

## Files

- `c4_*_tasks.jsonl` / `c4_*_generations.jsonl` / `c4_*_judgments.jsonl`
- `c4_primary_step_effects.csv`, `c4_primary_did_summary.csv`
- `c4_m2_step_effects.csv`, `c4_m2_did_summary.csv`
- `c4_m4_c2_own_effects.csv`, `c4_m4_c2_own_summary.csv`
- `c4_m6_*`, `c4_m10_*` (ProcessBench and long-CoT DiD)
- Pipeline: `scripts/run_c4_placebo_controls.py`
