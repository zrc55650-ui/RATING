#!/usr/bin/env python3
"""Reviewer-response reconciliation statistics.

1. Label-set robustness: target effect and placebo-corrected contrast for the
   anchor group under BOTH label passes (initial/analysis vs human-calibrated),
   each with a fresh 5,000-replicate cluster bootstrap, clustered by step and
   (as an additional robustness axis) by problem.
2. Label overlap between the two passes.
3. Placebo composition: PRM800K ratings of the steps deleted by the matched
   placebo interventions.
4. Excluded-paraphrase bias check: the 19/240 strong-control steps whose
   paraphrase failed automatic checks, compared with the 221 retained.

Outputs to workstream_F_final_statistics/robustness/ and the M4 directory.
Stdlib only; run from the repository root.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict

from analysis_common import ROOT, as_float, as_int, fmt, read_csv, write_csv

OUT_DIR = ROOT / "workstream_F_final_statistics" / "robustness"
M4_DIR = ROOT / "workstream_M4_strong_controls"
REPLICATES = 5000
SEED = 20260723


def load_steps() -> list[dict]:
    steps = []
    for row in read_csv(ROOT / "data" / "master_step_table.csv"):
        steps.append(
            {
                "step_id": row["step_id"],
                "problem_id": row["problem_id"],
                "rating": as_int(row["prm_rating"]),
                "type_init": row["step_type_initial"].strip().lower(),
                "type_hc": row["step_type_human_calibrated"].strip().lower(),
                "target_effect": as_float(row["target_effect"]),
                "semantic": as_float(row["pure_semantic_effect"]),
                "eligible": row["placebo_eligible"].strip() == "1",
                "placebo_runs": as_int(row["placebo_run_count"], 0),
                "source_line": as_int(row["source_line"]),
                "placebo_indices": json.loads(row["placebo_step_indices"] or "[]"),
            }
        )
    return steps


def cluster_bootstrap_mean(
    values_by_cluster: dict[str, list[float]], replicates: int, seed: int
) -> tuple[float, float, float]:
    clusters = sorted(values_by_cluster)
    flat = [v for c in clusters for v in values_by_cluster[c]]
    point = sum(flat) / len(flat)
    rng = random.Random(seed)
    stats = []
    for _ in range(replicates):
        sample = [
            v
            for _ in clusters
            for v in values_by_cluster[clusters[rng.randrange(len(clusters))]]
        ]
        stats.append(sum(sample) / len(sample))
    stats.sort()
    lo = stats[int(0.025 * replicates)]
    hi = stats[min(int(0.975 * replicates), replicates - 1)]
    return point, lo, hi


def group_row(name, steps, value_key, cluster_key, seed):
    usable = [s for s in steps if not (s[value_key] != s[value_key])]  # drop NaN
    by_cluster: dict[str, list[float]] = defaultdict(list)
    for s in usable:
        by_cluster[s[cluster_key]].append(s[value_key])
    point, lo, hi = cluster_bootstrap_mean(by_cluster, REPLICATES, seed)
    return {
        "group": name,
        "metric": value_key,
        "cluster_unit": cluster_key,
        "n_steps": len(usable),
        "n_clusters": len(by_cluster),
        "effect_pp": fmt(100 * point, 2),
        "ci_lower_pp": fmt(100 * lo, 2),
        "ci_upper_pp": fmt(100 * hi, 2),
    }


def label_robustness(steps: list[dict]) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    anchors = {
        "anchor_initial_labels": [
            s for s in steps if s["rating"] == -1 and s["type_init"] == "harmful"
        ],
        "anchor_human_calibrated": [
            s for s in steps if s["rating"] == -1 and s["type_hc"] == "harmful"
        ],
    }
    rows = []
    seed = SEED
    for name, group in anchors.items():
        for cluster_key in ("step_id", "problem_id"):
            seed += 1
            rows.append(group_row(name, group, "target_effect", cluster_key, seed))
            matched = [s for s in group if s["eligible"]]
            seed += 1
            rows.append(
                group_row(f"{name}_matched", matched, "semantic", cluster_key, seed)
            )
    for cluster_key in ("step_id", "problem_id"):
        seed += 1
        rows.append(group_row("overall_600", steps, "target_effect", cluster_key, seed))
    write_csv(OUT_DIR / "label_set_robustness.csv", rows)
    for r in rows:
        print(r)

    both = [
        s for s in steps if s["rating"] == -1 and s["type_init"] == "harmful"
        and s["type_hc"] == "harmful"
    ]
    overlap = {
        "anchor_initial": len(anchors["anchor_initial_labels"]),
        "anchor_human_calibrated": len(anchors["anchor_human_calibrated"]),
        "anchor_intersection": len(both),
        "type_agreement_600": sum(1 for s in steps if s["type_init"] == s["type_hc"]),
    }
    (OUT_DIR / "label_overlap.json").write_text(
        json.dumps(overlap, indent=2) + "\n", encoding="utf-8"
    )
    print(overlap)


def placebo_composition(steps: list[dict]) -> None:
    """Ratings of the steps that placebo deletion actually removed."""
    records: dict[int, dict] = {}
    with (ROOT / "data" / "phase2_test.jsonl").open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            records[lineno] = None if not line.strip() else line

    rating_counter: Counter = Counter()
    matched_steps = 0
    for s in steps:
        if not s["placebo_indices"]:
            continue
        raw = records.get(s["source_line"])
        if raw is None:
            continue
        record = json.loads(raw)
        ratings = []
        for step in record.get("label", {}).get("steps", []):
            chosen = step.get("chosen_completion")
            completions = step.get("completions") or []
            if chosen is None or chosen >= len(completions):
                ratings.append(None)
            else:
                ratings.append(completions[chosen].get("rating"))
        matched_steps += 1
        for idx in s["placebo_indices"]:
            rating = ratings[idx] if 0 <= idx < len(ratings) else None
            rating_counter[str(rating)] += 1
    total = sum(rating_counter.values())
    rows = [
        {"placebo_step_rating": k, "runs": v, "share": fmt(v / total, 4)}
        for k, v in sorted(rating_counter.items())
    ]
    write_csv(OUT_DIR / "placebo_step_rating_composition.csv", rows)
    print("placebo composition over", total, "placebo runs from", matched_steps, "steps")
    for r in rows:
        print(r)


def excluded_paraphrase_bias() -> None:
    manifest = read_csv(M4_DIR / "strong_control_sampling_manifest.csv")
    have = set()
    with (M4_DIR / "m4_paraphrases.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                have.add(json.loads(line)["step_id"])
    rows = []
    for status, subset in (
        ("retained_221", [m for m in manifest if m["step_id"] in have]),
        ("excluded_19", [m for m in manifest if m["step_id"] not in have]),
    ):
        n = len(subset)
        rows.append(
            {
                "status": status,
                "n": n,
                "share_anchor": fmt(
                    sum(1 for m in subset if m["strong_control_group"] == "negative_anchor") / n, 3
                ),
                "share_stable": fmt(
                    sum(1 for m in subset if m["strong_control_group"] == "stable_correct") / n, 3
                ),
                "share_neutral": fmt(
                    sum(1 for m in subset if m["strong_control_group"] == "neutral_comparison") / n, 3
                ),
                "mean_target_tokens": fmt(
                    sum(as_int(m["target_tokens"]) for m in subset) / n, 1
                ),
                "share_rating_neg1": fmt(
                    sum(1 for m in subset if as_int(m["prm_rating"]) == -1) / n, 3
                ),
            }
        )
        print(rows[-1])
    write_csv(M4_DIR / "m4_excluded_paraphrase_bias.csv", rows)


def main() -> None:
    steps = load_steps()
    label_robustness(steps)
    placebo_composition(steps)
    excluded_paraphrase_bias()


if __name__ == "__main__":
    main()
