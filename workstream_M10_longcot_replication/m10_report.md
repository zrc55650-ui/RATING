# M10: Long-CoT Generator Replication (DeepSeek-R1-Distill-Qwen-14B)

Completes the plan's nominal second generator, which was unavailable via the
API provider at freeze time (phi-4 was the disclosed substitute; see the M2
workstream). Reuses the **identical 2,691-task list** as M2 (300 steps x
{control, target_delete, placebo_delete} x 3 runs, minus 9 tasks for steps
without an eligible placebo), so the replications are directly comparable.

## Protocol

- Generator: `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B` served locally with
  vLLM 0.26.0 (8 replicas, `--max-model-len 20480`), temperature 0.7 /
  top-p 0.8 (frozen protocol values), no `json_mode` (it would suppress the
  `<think>` phase).
- Prompts: exact M2 system/user construction (`run_m10_longcot_pipeline.py
  export`); taskIds carry the `|m10run` suffix.
- Executor: `scripts/server_r1_executor.py`, up to 4 whole-request attempts,
  checkpointed by taskId. Initial pass used `max_tokens` 12288; tasks still
  unparseable after 4 attempts were regenerated with the repaired parser at
  `max_tokens` 16384.
- Judge: frozen `qwen/qwen3-8b` judge pipeline, unchanged
  (`run_m10_longcot_pipeline.py judge`).

## Parse repair

R1 frequently writes raw LaTeX inside JSON strings (`\pmod`, `\$`, `\frac`),
which are illegal JSON escapes and defeated `json.loads` even when the JSON
object was complete; a smaller fraction of draws omit JSON entirely and end
with a prose `\boxed{...}` answer. `extract_json_object` now repairs invalid
escapes (keeping `\"` and `\\`, doubling every other backslash, consuming
pairwise) before parsing, applied to the direct parse, the brace depth-scan,
and the reverse `raw_decode` recovery. This reduced unparseable-after-4-
attempts records from 477/2,691 (17.7%) to **28/2,691 (1.04%)**, balanced
across conditions (control 7 / target 8 / placebo 13). Unparseable records
carry an empty `finalAnswer` and are ruled incorrect by the judge
(`rule:no-answer`), matching the frozen semantics.

Final generation status: 2,650 completed / 9 logical_break / 32
cannot_continue (28 of which are the parse failures above).

## Results (`m10_effect_summary.csv`, 5,000-rep bootstrap, seed 20260723)

| Group | Target effect (pp) | Placebo effect (pp) | Placebo-corrected (pp) |
|---|---|---|---|
| Overall (300) | +3.44 [+1.00, +6.00] | +1.46 [-1.57, +4.49] | +1.80 [-1.23, +4.60] |
| Anchor (rating -1 x Harmful, 100) | +7.00 [+2.67, +11.67] | +5.33 [-0.33, +11.33] | **+1.67 [-4.00, +7.33]** |
| rating=0 (100) | +0.33 [-3.33, +4.00] | +0.67 [-2.67, +4.33] | -0.33 [-5.33, +4.67] |
| rating=1 (100) | +3.00 [-1.33, +7.67] | -1.72 [-7.22, +3.78] | +4.12 [-0.69, +8.93] |
| Stable-correct (80) | +2.08 [-1.25, +5.83] | +0.42 [-2.92, +3.75] | +1.67 [-0.83, +4.17] |

Baselines: control accuracy 83.8% overall and **77.7% on anchor steps**
(vs. much lower no-thinking baselines) — the long-CoT model recovers from
erroneous prefixes unaided, so this is genuine robustness, not a pure
ceiling artifact (22 pp of headroom remained in the anchor group). Only
82/300 steps shift outcome at all; among the 33 steps with nonzero effects
under both R1 and Qwen3-8B, signs agree for 66.7%
(`m10_longcot_summary.json`).

## Interpretation

The negative-anchor mechanism largely disappears under a long-CoT
generator: the small anchor-group deletion gain is placebo-indistinguishable
(restart, not semantics). Extended thinking re-derives the solution rather
than trusting the visible prefix. This scopes the paper's anchor claims to
no-thinking mid-size generation and independently supports the core thesis:
whether deletion helps is a property of the step-generator pair, and no
score inspection substitutes for counterfactual validation.

## Caveats

- The 16,384-token retry cap (vs. 12,288 initial) applies only to the 477
  regenerated tasks; caps are infrastructure, prompts and sampling were
  identical.
- Escape repair can degrade LaTeX inside recovered strings (e.g. pmatrix
  separators `\\` -> `\`); affected answers remain recognizable to the
  judge, and only records that would otherwise be unparseable go through
  the repaired path with any corruption risk.
- 28 unparseable records (1.04%) are scored incorrect; their condition
  balance bounds any differential-attrition bias well below the reported
  effect sizes.

## Files

- `m10_prompt_tasks.jsonl` — 2,691 self-contained prompts (M2 task reuse)
- `m10_generations.jsonl` — final generations (deduplicated, checkpointed)
- `m10_judgments.jsonl` — frozen qwen3-8b judgments
- `m10_step_effects.csv` / `m10_effect_summary.csv` / `m10_longcot_summary.json`
- Server-side executor: `scripts/server_r1_executor.py`
