# StepRem: A Counterfactual Benchmark for Reasoning-Step Removability

600 PRM800K reasoning steps with paired counterfactual continuation outcomes
(Control / Target deletion / matched Placebo deletion; Qwen3-8B generator,
4 runs per condition, LLM-judged with a 200-output human audit).

## Task

Predict, for a held-out step, the run-level consequences of deleting it:
- **danger**: at least one Control-correct run flips to wrong;
- **benefit**: at least one Control-wrong run flips to correct.

## Files

- `steprem_dev.csv` — development split with all outcome columns;
- `steprem_test_public.csv` — test split, features only;
- `steprem_test_hidden.csv` — test outcomes (kept by maintainers; here for
  local evaluation only — do not train on it);
- `evaluate.py` — scoring script (AUPRC for danger and benefit).

Splits are by problem (no problem crosses splits). Trajectory text comes from
OpenAI PRM800K (MIT); see the paper for the full protocol, judge audit, and
limitations. Placebo columns are populated for the 511 matched steps only.

## Anti-leakage note

Outcome columns encode Qwen3-8B behavior at temperature 0.7; they are not
step-intrinsic labels. Cross-generator transfer is an open question the
benchmark is designed to measure — see the paper's M2 replication.
