#!/usr/bin/env python3
"""Reconstruct full PRM800K trajectory context for the 600 target steps.

Matches each master-table step to its phase2_test.jsonl source record by
problem text plus exact target-step text (target_step_index first, then a
text-search fallback). Writes step_trajectory_context.jsonl with the full
step list so downstream tooling (M1 PRM scoring, M3 human annotation) can
render prefix / target / downstream views. Stdlib only.
"""

from __future__ import annotations

import json
from pathlib import Path

from analysis_common import ROOT, as_int, read_csv

OUTPUT = ROOT / "data" / "step_trajectory_context.jsonl"


def build() -> list[dict]:
    by_problem: dict[str, list[dict]] = {}
    with (ROOT / "data" / "phase2_test.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            by_problem.setdefault(record["question"]["problem"].strip(), []).append(record)

    contexts = []
    unmatched = []
    for row in read_csv(ROOT / "data" / "master_step_table.csv"):
        problem = row["problem"].strip()
        target_text = row["target_step_text"].strip()
        declared_index = as_int(row["target_step_index"])
        matched_steps = None
        matched_index = None
        for record in by_problem.get(problem, []):
            steps = record["question"]["pre_generated_steps"]
            if declared_index < len(steps) and steps[declared_index].strip() == target_text:
                matched_steps, matched_index = steps, declared_index
                break
        if matched_steps is None:
            for record in by_problem.get(problem, []):
                steps = record["question"]["pre_generated_steps"]
                hits = [j for j, s in enumerate(steps) if s.strip() == target_text]
                if hits:
                    matched_steps, matched_index = steps, hits[0]
                    break
        if matched_steps is None:
            unmatched.append(row["step_id"])
            continue
        contexts.append(
            {
                "step_id": row["step_id"],
                "problem_id": row["problem_id"],
                "problem": problem,
                "ground_truth_answer": row["ground_truth_answer"],
                "steps": matched_steps,
                "target_index": matched_index,
                "declared_index": declared_index,
                "index_fallback_used": matched_index != declared_index,
            }
        )
    if unmatched:
        raise SystemExit(f"unmatched steps: {unmatched}")
    return contexts


def main() -> None:
    contexts = build()
    with OUTPUT.open("w", encoding="utf-8") as handle:
        for record in contexts:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    fallback = sum(1 for c in contexts if c["index_fallback_used"])
    print(f"wrote {len(contexts)} contexts ({fallback} via text fallback) -> {OUTPUT.name}")


if __name__ == "__main__":
    main()
