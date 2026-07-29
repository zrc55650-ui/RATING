# Workstream F – Final statistics, figures, and consistency checks

This folder is the publication-facing Workstream F package generated from the
single master script `../make_all_results.py`.

## Status

- Technical consistency checks: **PASS**
- Judge Audit gate: **PASS**
- Judge–human binary agreement: **93.0% (186/200)**
- Maximum absolute condition bias: **2.3 percentage points**
- Paper-level status: **generated, but not frozen**

The statistical outputs pass the preregistered Judge Audit hard-stop gate.
Because agreement remains below the stricter 95% threshold, outcome-dependent
claims should retain the audit diagnostics and sensitivity qualification.

## Contents

- `final_tables.md` and `appendix_tables.md`: manuscript-facing tables.
- `numbers_for_paper.json`: single machine-readable source for reported values.
- `table1_*.csv` through `table3_*.csv`: table source data.
- `figure1_*` through `figure4_*`: SVG, PDF, PNG, and source CSV files.
- `workstream_F_execution_report.md`: concise execution summary.
- `workstream_F_consistency_audit.md`: denominator, sign, cohort, label-scope,
  confidence-interval, and provenance checks.

## Rebuild

From the repository root:

```powershell
uv run --no-sync python ./make_all_results.py
uv run --no-sync python ./export_figures_pdf.py
```

See `../REPRODUCIBILITY.md` for the frozen seeds, input packages, environment,
and validation procedure.
