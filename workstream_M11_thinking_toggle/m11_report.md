# M11: Within-Checkpoint Thinking-Mode Toggle (Qwen3-8B)

Review issue (round 2, major issue 5): the long-CoT replication (M10,
R1-Distill-Qwen-14B) changes model family, scale, and training data at
once, so "long-CoT neutralizes anchors" was confounded. The cleanest
identification is to toggle thinking on the **same** checkpoint. Qwen3-8B
supports exactly this: the frozen primary protocol appended `/no_think`;
M11 reruns the identical tasks with thinking enabled and nothing else
changed (same provider, prompts, sampling parameters, judge).

## Protocol

- Generator: `qwen/qwen3-8b` via OpenRouter, thinking mode (no `/no_think`
  suffix), temperature 0.7 / top-p 0.8 (frozen protocol values).
- `json_mode` **disabled**: probing showed structured-output mode corrupts
  thinking generations (content degenerates to a bare JSON string while all
  budget goes to reasoning tokens). Answers are parsed from the content with
  the standard `extract_json_object` recovery instead. `MAX_TOKENS` 24,576
  to accommodate the reasoning phase.
- Tasks: the identical M2/M10 2,691-task list (300 steps x {control,
  target_delete, placebo_delete} x 3 runs, minus 9 tasks for steps without
  an eligible placebo), taskIds `|m11run`, **plus** 891 placebo own-control
  C_p runs (`|m11cp`, mirroring the frozen placebo cutoffs 1:1) = 3,582
  generations, all completed.
- Thinking activated on **100%** of runs; mean 2,514 reasoning tokens
  (`m11_summary.json`).
- Judge: frozen `qwen/qwen3-8b` judge pipeline, unchanged.

## Results (`m11_effect_summary.csv`, 5,000-rep cluster bootstrap)

| Group | Target effect (pp) | Placebo vs own control (pp) | DiD semantic (pp) |
|---|---|---|---|
| Overall (300) | -2.00 [-5.33, +1.22] | +3.40 [+0.36, +6.51] | -5.64 [-10.30, -1.12] |
| Anchor (rating -1 x Harmful, 100) | **-3.00 [-8.01, +2.33]** | +0.50 [-4.59, +5.75] | **-3.50 [-11.50, +4.33]** |
| rating=0 (100) | -2.00 [-6.67, +3.00] | +4.42 [+0.16, +9.08] | -6.42 [-12.59, -0.00] |
| rating=+1 (100) | -1.00 [-7.67, +5.34] | +5.33 [-0.69, +11.60] | -7.04 [-16.84, +2.32] |
| Stable-correct (80) | -4.17 [-10.83, +2.50] | +4.90 [-1.35, +11.25] | -9.06 [-18.65, +0.11] |

No-thinking baselines on the **same 300-step subcohort** (frozen primary
runs): anchor control accuracy 26.8% with a +21.8 pp deletion effect;
overall +10.5 pp. With thinking, anchor control accuracy rises to
**83.3%** and the deletion effect collapses to **-3.0 pp**. Only 77/300
steps shift outcome at all, and step-level effect signs agree with the
no-thinking runs at chance (56%, n=32 nonzero pairs).

## Interpretation

This is the within-checkpoint contrast the review asked for: identical
weights, prompts, provider, and sampling — only the thinking mode toggled.
The anchor effect (+21.8 -> -3.0 pp) and its DiD semantic component
(+25.4 -> -3.5 pp against the primary cohort's full-cohort estimate)
collapse under thinking, so the collapse observed for R1-Distill (M10,
DiD -1.0) is attributable to extended thinking itself rather than to
R1's model, scale, or training data. Under thinking, no deletion condition
helps: target deletions are slightly negative everywhere, and the small
positive own-control placebo effects make the overall DiD mildly negative
— consistent with a generator that re-derives the solution and, if
anything, loses a little information when steps are removed.

## Caveats

- One generation batch (no frozen/refresh split); the M12 drift check
  applies only to no-thinking C_p batches. All M11 contrasts are internal
  to the batch, so batch drift cancels within every estimand.
- **No-answer rate.** 437/3,582 runs (12.2%) end without a parseable final
  answer (411 JSON-parse failures + 26 parsed-but-empty) and are ruled
  incorrect by the frozen judge semantics ("No candidate final answer was
  produced."), same rule as every other cohort. Thinking mode emits JSON
  less reliably than `/no_think` (M10's R1 rate was 1.0% after parse
  repair; the no-think cohorts are ~0%). The failures are balanced across
  conditions — control 97/900 (10.8%), target_delete 114/900 (12.7%),
  placebo_delete 107/891 (12.0%), C_p 119/891 (13.4%) — so differential
  attrition is bounded at ~2 pp, an order of magnitude below the +21.8 ->
  -3.0 pp anchor contrast. If anything the penalty deflates the thinking
  baselines: anchor control accuracy is 83.3% *with* no-answers scored
  wrong.
- Token cap: only 3/3,582 runs hit the 24,576-token completion cap.
- Reasoning content is not judged; only the final answer enters the frozen
  judge pipeline, identical to every other cohort.

## Files

- `m11_tasks.jsonl` — 3,582 task prompts (2,691 `|m11run` + 891 `|m11cp`)
- `m11_probe_generations.jsonl` — 20-task probe that surfaced the
  json_mode/thinking incompatibility
- `m11_generations.jsonl` — 3,582 generations (checkpointed, deduplicated)
- `m11_judgments.jsonl` — frozen qwen3-8b judgments
- `m11_step_effects.csv` / `m11_effect_summary.csv` / `m11_summary.json`
- Pipeline: `scripts/run_m11_thinking_pipeline.py`
