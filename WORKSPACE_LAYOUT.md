# Workspace Layout

Reorganized 2026-07-24. Rule of thumb: `data/` is frozen input, workstream
directories are canonical output, `build/` is disposable, `archive/` is
local-only history.

```
remove step/
├── README.md                        # overview + headline results + this map
├── REPRODUCIBILITY.md               # seeds, rebuild commands, checks
├── OVERNIGHT_STATUS_2026-07-24.md   # final execution report (M1–M9)
├── WORKSPACE_LAYOUT.md
├── .env                             # OPENROUTER_API_KEY (local only, never committed)
│
├── paper/                           # ACL submission: acl_latex.tex/.pdf, custom.bib, figures/
├── docs/                            # research plans + historical reports (CN)
│
├── data/                            # FROZEN primary data
│   ├── master_step_table.csv        #   600 steps (single source of step-level truth)
│   ├── master_run_table.csv         #   6,314 runs (control/target/placebo)
│   ├── phase2_test.jsonl            #   PRM800K source split
│   ├── step_trajectory_context.jsonl#   600 reconstructed full trajectories
│   ├── qwen_deletion_generations.jsonl
│   ├── qwen3-8b_*.{csv,md,html,jsonl,json}   # frozen 5,000-rep bootstrap results + placebo selection
│   └── annotations/                 #   human + AI annotation provenance
│       ├── human_calibration/       #     600-step human-calibrated labels + viewer HTML
│       ├── ai_labels/               #     AI annotation shards (600 + review185)
│       ├── blind100/                #     blind-100 audit
│       ├── judge_audit/             #     completed blinded sheets A/B + adjudication
│       └── qualitative/             #     case-audit manifest + completed human sheet
│
├── scripts/                         # ALL code (stdlib-only Python)
│   ├── analysis_common.py           #   shared helpers; defines ROOT/DATA/BUILD
│   ├── make_all_results.py          #   one-command B/C/D/E/F rebuild
│   ├── run_m*_pipeline.py, run_m*.py, run_*.py, build_*.py, ...
│   ├── openrouter_workers.py        #   shared OpenRouter generation/judging library
│   └── legacy_powershell/           #   original Windows workers (historical record;
│                                    #   internal paths reflect the pre-reorg root layout)
│
├── workstream_A_judge_audit/        # A: judge audit (93.0%, PASS)
├── predictive_analysis/             # B: 5-fold CV prediction + risk-coverage
├── step_stability_analysis/         # C: stability across 4 runs
├── placebo_eligibility_analysis/    # D: placebo-eligibility selection audit
├── workstream_E_qualitative_case_study/
├── workstream_F_final_statistics/   # F: final tables/figures + numbers_for_paper.json
├── workstream_M1_actual_prm_audit/  # M1+M5: 3 actual PRMs + cheap signals
├── workstream_M2_cross_generator/   # M2: phi-4 replication
├── workstream_M3_human_annotation/  # M3: pilot sheets (key file never committed)
├── workstream_M4_strong_controls/   # M4: C0–C3 incl. paraphrase control
├── workstream_M6_processbench/      # M6: external validation
├── workstream_M7_policy_risk_coverage/
├── workstream_M8_statistics/
├── benchmark_steprem/               # M9: StepRem benchmark release package
│
├── build/                           # regenerable intermediates (gitignored)
└── archive/                         # local-only (gitignored)
    ├── worker_shards/               #   raw generation/judge shards (needed only for
    │                                #   a from-scratch master-table rebuild)
    ├── html_viewers/                #   annotation UI snapshots
    ├── legacy_reports/              #   superseded reports + paper zip
    ├── root_output_duplicates/      #   pre-reorg root copies of workstream outputs
    └── temp/                        #   figure_export_temp, logs, old staging dirs
```

Path conventions inside scripts: frozen inputs via `ROOT / "data" / ...`,
intermediates via `ROOT / "build" / ...`, canonical outputs written directly to
their workstream directory. Relative CLI defaults assume the repo root as CWD.
