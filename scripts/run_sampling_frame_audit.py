#!/usr/bin/env python3
"""Sampling-frame audit for the natural-prevalence reweighting (review issue).

Documents, with integer counts, how the balanced 600-step cohort relates to
the PRM800K phase-2 test frames:

  * chosen-path frame: steps on the annotator-chosen trajectory (the
    deployment-visible reasoning); 16,481 rated steps.
  * all-completions frame: every rated candidate completion, including
    alternatives the annotators rated but did not continue; 26,256.

and where each cohort target step comes from (chosen vs alternative), by
rating. Outputs workstream_F_final_statistics/robustness/sampling_frame_audit.csv.
Stdlib only; run from the repository root.
"""

from __future__ import annotations

import json
from collections import Counter

from analysis_common import ROOT, read_csv, write_csv

OUT = ROOT / "workstream_F_final_statistics" / "robustness" / "sampling_frame_audit.csv"


def main() -> None:
    chosen: Counter = Counter()
    allc: Counter = Counter()
    by_problem: dict[str, list[dict]] = {}
    with (ROOT / "data" / "phase2_test.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            by_problem.setdefault(
                record.get("question", {}).get("problem", "").strip(), []
            ).append(record)
            for step in record.get("label", {}).get("steps", []):
                completions = step.get("completions") or []
                picked = step.get("chosen_completion")
                for index, completion in enumerate(completions):
                    rating = completion.get("rating")
                    if rating in (-1, 0, 1):
                        allc[rating] += 1
                        if picked is not None and index == picked:
                            chosen[rating] += 1

    steps = {row["step_id"]: row for row in read_csv(ROOT / "data" / "master_step_table.csv")}
    contexts = [
        json.loads(line)
        for line in (ROOT / "data" / "step_trajectory_context.jsonl").open(encoding="utf-8")
        if line.strip()
    ]
    role_by_rating: Counter = Counter()
    for context in contexts:
        target = context["steps"][context["target_index"]].strip()
        role = "not_found"
        for record in by_problem.get(context["problem"].strip(), []):
            for step in record.get("label", {}).get("steps", []):
                completions = step.get("completions") or []
                picked = step.get("chosen_completion")
                for index, completion in enumerate(completions):
                    if (completion.get("text") or "").strip() == target:
                        role = (
                            "chosen"
                            if picked is not None and index == picked
                            else "alternative"
                        )
        rating = steps[context["step_id"]]["prm_rating"]
        role_by_rating[(role, rating)] += 1

    rows = []
    for rating in (-1, 0, 1):
        rows.append(
            {
                "frame": "phase2_test_chosen_path",
                "rating": rating,
                "count": chosen[rating],
                "share": f"{chosen[rating] / sum(chosen.values()):.4f}",
            }
        )
    for rating in (-1, 0, 1):
        rows.append(
            {
                "frame": "phase2_test_all_completions",
                "rating": rating,
                "count": allc[rating],
                "share": f"{allc[rating] / sum(allc.values()):.4f}",
            }
        )
    for (role, rating), count in sorted(role_by_rating.items()):
        rows.append(
            {
                "frame": f"cohort_target_provenance:{role}",
                "rating": rating,
                "count": count,
                "share": f"{count / 600:.4f}",
            }
        )
    rows.append(
        {
            "frame": "cohort_unique",
            "rating": "",
            "count": len({c["problem_id"] for c in contexts}),
            "share": "unique_problems",
        }
    )
    write_csv(OUT, rows)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
