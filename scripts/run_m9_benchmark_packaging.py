#!/usr/bin/env python3
"""Workstream M9: package the removability benchmark (StepRem).

Splits the 600-step cohort by problem (stable hash, ~70/30) into a public
development split (full outcomes) and a held-out test split whose outcome
columns are withheld from the public file; ships an evaluation script and a
dataset card. Stdlib only.
"""

from __future__ import annotations

import json

from analysis_common import ROOT, read_csv, stable_hash, write_csv

OUT_DIR = ROOT / "benchmark_steprem"

PUBLIC_FEATURES = [
    "step_id",
    "problem_id",
    "problem",
    "target_step_text",
    "target_step_index",
    "total_steps",
    "prm_rating",
    "step_type_initial",
    "step_type_human_calibrated",
    "position_bin",
    "position_ratio",
    "target_tokens",
    "prefix_tokens",
    "placebo_eligible",
]
OUTCOME_COLUMNS = [
    "control_correct_count",
    "target_correct_count",
    "wrong_to_correct_count",
    "correct_to_wrong_count",
    "target_effect",
    "placebo_avg_correct",
    "placebo_effect",
    "pure_semantic_effect",
]

EVAL_SCRIPT = '''#!/usr/bin/env python3
"""StepRem test-split evaluation.

Input: a CSV with columns step_id, danger_score, benefit_score where higher
danger_score means "more likely to destroy a correct run if deleted" and
higher benefit_score means "more likely to rescue a wrong run".

Usage: python evaluate.py predictions.csv steprem_test_hidden.csv
"""
import csv
import sys


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def auprc(labels, scores):
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    positives = sum(labels)
    if not positives:
        return float("nan")
    tp = 0
    total = 0.0
    for rank, index in enumerate(order, 1):
        if labels[index]:
            tp += 1
            total += tp / rank
    return total / positives


def main():
    predictions = {r["step_id"]: r for r in read(sys.argv[1])}
    hidden = read(sys.argv[2])
    rows = [r for r in hidden if r["step_id"] in predictions]
    if len(rows) < len(hidden):
        print(f"WARNING: {len(hidden) - len(rows)} test steps missing predictions")
    danger_labels = [1 if int(r["correct_to_wrong_count"]) > 0 else 0 for r in rows]
    benefit_labels = [1 if int(r["wrong_to_correct_count"]) > 0 else 0 for r in rows]
    danger_scores = [float(predictions[r["step_id"]]["danger_score"]) for r in rows]
    benefit_scores = [float(predictions[r["step_id"]]["benefit_score"]) for r in rows]
    print("steps evaluated:", len(rows))
    print("danger AUPRC:", round(auprc(danger_labels, danger_scores), 4),
          "| base rate:", round(sum(danger_labels) / len(rows), 4))
    print("benefit AUPRC:", round(auprc(benefit_labels, benefit_scores), 4),
          "| base rate:", round(sum(benefit_labels) / len(rows), 4))


if __name__ == "__main__":
    main()
'''

DATASET_CARD = """# StepRem: A Counterfactual Benchmark for Reasoning-Step Removability

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
"""


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    rows = read_csv(ROOT / "data" / "master_step_table.csv")
    dev_rows, test_public, test_hidden = [], [], []
    for row in rows:
        is_test = stable_hash("steprem-split|" + row["problem_id"]) % 100 < 30
        public = {k: row[k] for k in PUBLIC_FEATURES}
        full = {**public, **{k: row[k] for k in OUTCOME_COLUMNS}}
        if is_test:
            test_public.append(public)
            test_hidden.append(full)
        else:
            dev_rows.append(full)
    write_csv(OUT_DIR / "steprem_dev.csv", dev_rows)
    write_csv(OUT_DIR / "steprem_test_public.csv", test_public)
    write_csv(OUT_DIR / "steprem_test_hidden.csv", test_hidden)
    (OUT_DIR / "evaluate.py").write_text(EVAL_SCRIPT, encoding="utf-8")
    (OUT_DIR / "DATASET_CARD.md").write_text(DATASET_CARD, encoding="utf-8")
    problems = {r["problem_id"] for r in rows}
    test_problems = {r["problem_id"] for r in test_hidden}
    print(
        f"dev steps: {len(dev_rows)}, test steps: {len(test_hidden)}, "
        f"problems: {len(problems)} (test {len(test_problems)})"
    )


if __name__ == "__main__":
    main()
