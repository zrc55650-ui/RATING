#!/usr/bin/env python3
"""Honest policy selection: calibration/test split with a harm upper bound.

Splits the 600-step cohort into calibration and test halves by problem
(stable hash). On the calibration half each policy chooses its coverage as
the largest ranked prefix whose one-sided 95% Wilson upper bound on the
per-deleted-run harm rate stays within the budget; the chosen coverage
fraction is then applied to the test half and realized harm / net gain are
reported. Contrast with the in-sample selection of the main risk-coverage
table, which upper-bounds what honest selection can achieve.

Policies: rating-first ranking, model-D and model-E predictors (out-of-fold
scores from the frozen predictive analysis), and the trained-PRM score.
Stdlib only; run from the repository root.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict

from analysis_common import ROOT, as_float, as_int, fmt, read_csv, stable_hash, write_csv

OUT_DIR = ROOT / "workstream_M7_policy_risk_coverage"
BUDGETS = [0.01, 0.03, 0.05]
Z_95 = 1.6448536269514722


def wilson_upper(harm: float, n: int) -> float:
    if n == 0:
        return 1.0
    z2 = Z_95 * Z_95
    denom = 1 + z2 / n
    centre = harm + z2 / (2 * n)
    margin = Z_95 * math.sqrt(harm * (1 - harm) / n + z2 / (4 * n * n))
    return (centre + margin) / denom


def load_steps() -> list[dict]:
    sums: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in read_csv(ROOT / "predictive_analysis" / "predictive_predictions.csv"):
        sums[(row["step_id"], f"{row['model']}|{row['task']}")].append(
            as_float(row["predicted_probability"])
        )
    predictions: dict[str, dict[str, float]] = defaultdict(dict)
    for (sid, key), values in sums.items():
        predictions[sid][key] = sum(values) / len(values)
    prm_scores = {}
    path = ROOT / "workstream_M1_actual_prm_audit" / "prm_scores_qwen25_math_prm_7b.jsonl"
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("target_score") is not None:
                prm_scores[record["step_id"]] = float(record["target_score"])

    steps = []
    for row in read_csv(ROOT / "data" / "master_step_table.csv"):
        sid = row["step_id"]
        pred = predictions.get(sid, {})
        steps.append(
            {
                "step_id": sid,
                "problem_id": row["problem_id"],
                "rating": as_int(row["prm_rating"]),
                "delta": as_float(row["target_effect"]),
                "c2w": as_int(row["correct_to_wrong_count"]),
                "d_score": pred.get("D|benefit", 0.36) - pred.get("D|danger", 0.151),
                "e_score": pred.get("E|benefit", 0.36) - pred.get("E|danger", 0.151),
                "prm": prm_scores.get(sid),
                "split": "cal" if stable_hash("calsplit|" + row["problem_id"]) % 2 == 0 else "test",
            }
        )
    return steps


def rankers(steps):
    return {
        "rating_first": lambda s: (s["rating"], stable_hash(s["step_id"])),
        "predictor_D": lambda s: (-s["d_score"], stable_hash(s["step_id"])),
        "predictor_E": lambda s: (-s["e_score"], stable_hash(s["step_id"])),
        "trained_prm_score": lambda s: (
            s["prm"] if s["prm"] is not None else 1.0,
            stable_hash(s["step_id"]),
        ),
    }


def main() -> None:
    steps = load_steps()
    cal = [s for s in steps if s["split"] == "cal"]
    test = [s for s in steps if s["split"] == "test"]
    print(f"calibration {len(cal)} steps / test {len(test)} steps")
    rows = []
    for name, keyfun in rankers(steps).items():
        cal_order = sorted(cal, key=keyfun)
        test_order = sorted(test, key=keyfun)
        for budget in BUDGETS:
            best_frac = 0.0
            for k in range(1, len(cal_order) + 1):
                selected = cal_order[:k]
                harm = sum(s["c2w"] for s in selected) / (4 * k)
                if wilson_upper(harm, 4 * k) <= budget:
                    best_frac = k / len(cal_order)
            k_test = round(best_frac * len(test_order))
            selected = test_order[:k_test]
            harm_test = (
                sum(s["c2w"] for s in selected) / (4 * k_test) if k_test else float("nan")
            )
            net = 100 * sum(s["delta"] for s in selected) / len(test_order) if k_test else 0.0
            rows.append(
                {
                    "policy": name,
                    "budget": budget,
                    "calibration_coverage": fmt(best_frac, 4),
                    "test_steps_deleted": k_test,
                    "test_harm_rate": fmt(harm_test, 4) if k_test else "",
                    "test_harm_within_budget": int(k_test > 0 and harm_test <= budget),
                    "test_net_accuracy_change_pp": fmt(net, 2),
                }
            )
            print(rows[-1])
    write_csv(OUT_DIR / "policy_calibration_test_split.csv", rows)


if __name__ == "__main__":
    main()
