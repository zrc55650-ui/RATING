# Reproducibility

## Frozen configuration

- Core cluster-bootstrap seed: `20260722`
- Downstream-analysis seed (analysis_common.SEED): `20260723`
- Bootstrap replicates: `5000`
- Main cohort: `600` target steps / `2,400` Control–Target pairs / `1,514` placebo runs
- Placebo-matched cohort: `511` target steps
- Extension cohorts: cross-generator `2,691` runs (M2), strong controls `1,843` (M4),
  ProcessBench `2,412` (M6), long-CoT `2,691` (M10), thinking-toggle `3,582` (M11)
- Placebo own-controls: `3,907` runs across four cohorts (M12)
- Total extension runs: `17,126`
- Judge Audit (latest 200-row re-adjudication): 93.0% agreement (186/200), hard-stop gate PASS;
  review tier `PASS_WITH_SENSITIVITY`

Last verified end-to-end on macOS (Darwin 24.6) with system `python3`; the original
A–F generation ran on Windows PowerShell 5.1 (workers archived under
`scripts/legacy_powershell/`). All statistics scripts use only the Python
standard library.

## Layout contract

- `data/` — frozen inputs (master tables, bootstrap CSVs, generation records,
  PRM800K `phase2_test.jsonl`, annotation provenance under `data/annotations/`).
  Scripts read these; only `scripts/build_master_tables.py` and
  `scripts/build_trajectory_context.py` write here.
- `build/` — regenerable intermediates (never committed).
- Workstream directories — canonical outputs; analysis scripts write directly
  into them.
- `archive/` — local-only raw worker shards and superseded reports (never
  committed). A from-scratch master-table rebuild needs the raw shards there;
  the public repository instead treats `data/master_*.csv` as frozen ground truth.

## Rebuild commands (from the repository root)

```bash
python3 scripts/make_all_results.py    # B/C/D/E/F statistics, tables, figures, numbers_for_paper.json
python3 workstream_M1_actual_prm_audit/analyze_prm_scores.py
python3 scripts/run_policy_risk_coverage.py && python3 scripts/run_m7_extension.py
python3 scripts/run_m8_statistics.py
python3 scripts/run_m2_pipeline.py analyze
python3 scripts/run_m4_pipeline.py analyze
python3 scripts/run_m6_pipeline.py analyze
python3 scripts/run_m9_benchmark_packaging.py
```

Generation/judging stages (`generate` / `judge` subcommands, PRM scoring, M5
signals) call OpenRouter or need a GPU and are already frozen; their outputs
live in the workstream directories, so the analyses above run fully offline.
`OPENROUTER_API_KEY` is read from `.env` at the repo root (never committed).

## Required checks after rebuilding

1. `workstream_F_final_statistics/workstream_F_consistency_audit.md` reports PASS.
2. Cohort denominators are 600/2400, 511/1514; run counts control 2400 /
   target 2400 / placebo 1514.
3. Point estimates lie inside their 95% CIs; pure semantic = target − placebo.
4. `numbers_for_paper.json`, tables, and figure sources agree with the paper.
5. Record an independent second-human numerical signoff before submission.

## Known deviations (disclosed in the paper)

- M2 generator is `microsoft/phi-4` (DeepSeek-R1-Distill models were
  unavailable/incompatible on OpenRouter at run time).
- M6 sampling had a duplicate-taskId bug (46 steps), fixed and regenerated;
  contaminated outputs are retained locally as `*.contaminated.bak` (not
  committed).
