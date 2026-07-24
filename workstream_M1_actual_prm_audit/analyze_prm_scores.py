#!/usr/bin/env python3
"""M1 audit: evaluate actual-PRM scores against removability outcomes.

Reads every prm_scores_*.jsonl in this directory plus the frozen master
table, then evaluates each signal on the plan's four tasks:

  A  dangerous deletion   step-level: any Control-correct -> Target-wrong
  B  beneficial deletion  step-level: any Control-wrong  -> Target-correct
  C  step-level average effect (Spearman correlation)
  D  placebo-corrected pure semantic effect, matched 511-step cohort only

Baselines: PRM800K rating, human-calibrated type (harmful=0 .. essential=1),
plus PRM ensemble mean and disagreement when >= 2 PRM score files exist.
Signals are oriented "higher = keep" so AUROC/AUPRC for danger reads
"does a high score warn against deletion". Stdlib only; run from repo root:

    python workstream_M1_actual_prm_audit/analyze_prm_scores.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from analysis_common import (  # noqa: E402
    ROOT,
    as_float,
    as_int,
    average_precision,
    fmt,
    mean,
    read_csv,
    roc_auc,
    sample_sd,
    write_csv,
)

OUT_DIR = ROOT / "workstream_M1_actual_prm_audit"
TYPE_ORDER = {"harmful": 0.0, "redundant": 0.5, "essential": 1.0}


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        result = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                result[order[k]] = rank
            i = j + 1
        return result

    rx, ry = ranks(xs), ranks(ys)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(
        sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)
    )
    return num / den if den else math.nan


def load_signals(steps: list[dict]) -> dict[str, dict[str, float]]:
    signals: dict[str, dict[str, float]] = {
        "prm800k_rating": {s["step_id"]: float(s["rating"]) for s in steps},
        "human_calibrated_type": {
            s["step_id"]: TYPE_ORDER[s["type_hc"]] for s in steps
        },
        "initial_type": {s["step_id"]: TYPE_ORDER[s["type_init"]] for s in steps},
    }
    m5_path = OUT_DIR / "m5_signals.jsonl"
    if m5_path.exists():
        entropy, nll, mask = {}, {}, {}
        with m5_path.open(encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("status") == "ok":
                    sid = record["step_id"]
                    entropy[sid] = -float(record["target_mean_entropy"])
                    nll[sid] = -float(record["target_mean_nll"])
                    mask[sid] = float(record["mask_importance"])
        signals["step_entropy_negated"] = entropy
        signals["step_nll_negated"] = nll
        signals["mask_answer_logp_drop"] = mask

    prm_columns: dict[str, dict[str, float]] = {}
    for path in sorted(OUT_DIR.glob("prm_scores_*.jsonl")):
        name = path.stem.replace("prm_scores_", "actual_prm:")
        column: dict[str, float] = {}
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("target_score") is not None:
                    column[record["step_id"]] = float(record["target_score"])
        if column:
            signals[name] = column
            prm_columns[name] = column
    if len(prm_columns) >= 2:
        shared = set.intersection(*(set(c) for c in prm_columns.values()))
        signals["actual_prm_ensemble_mean"] = {
            sid: mean([c[sid] for c in prm_columns.values()]) for sid in shared
        }
        signals["actual_prm_disagreement_negated"] = {
            sid: -sample_sd([c[sid] for c in prm_columns.values()]) for sid in shared
        }
    return signals


def main() -> None:
    steps = []
    for row in read_csv(ROOT / "data" / "master_step_table.csv"):
        steps.append(
            {
                "step_id": row["step_id"],
                "rating": as_int(row["prm_rating"]),
                "type_hc": row["step_type_human_calibrated"].strip().lower(),
                "type_init": row["step_type_initial"].strip().lower(),
                "danger": 1 if as_int(row["correct_to_wrong_count"]) > 0 else 0,
                "benefit": 1 if as_int(row["wrong_to_correct_count"]) > 0 else 0,
                "delta": as_float(row["target_effect"]),
                "semantic": as_float(row["pure_semantic_effect"]),
                "matched": row["placebo_eligible"].strip() == "1",
            }
        )
    signals = load_signals(steps)
    actual = [k for k in signals if k.startswith("actual_prm")]
    if not actual:
        print(
            "NOTE: no prm_scores_*.jsonl found - reporting dataset-label baselines "
            "only. Run the scoring adapters first for the actual-PRM audit."
        )

    rows = []
    for name, column in signals.items():
        covered = [s for s in steps if s["step_id"] in column]
        if len(covered) < 50:
            continue
        scores = [column[s["step_id"]] for s in covered]
        danger = [s["danger"] for s in covered]
        benefit = [s["benefit"] for s in covered]
        matched = [s for s in covered if s["matched"] and not math.isnan(s["semantic"])]
        rows.append(
            {
                "signal": name,
                "steps_covered": len(covered),
                "danger_auroc_highscore_warns": fmt(roc_auc(danger, scores), 4),
                "danger_auprc": fmt(average_precision(danger, scores), 4),
                "benefit_auroc_lowscore_flags": fmt(
                    roc_auc(benefit, [-v for v in scores]), 4
                ),
                "benefit_auprc": fmt(
                    average_precision(benefit, [-v for v in scores]), 4
                ),
                "spearman_score_vs_delta": fmt(
                    spearman(scores, [s["delta"] for s in covered]), 4
                ),
                "spearman_score_vs_semantic_matched": fmt(
                    spearman(
                        [column[s["step_id"]] for s in matched],
                        [s["semantic"] for s in matched],
                    ),
                    4,
                )
                if matched
                else "",
                "matched_steps": len(matched),
            }
        )
    write_csv(OUT_DIR / "prm_score_audit_metrics.csv", rows)
    for row in rows:
        print(row)
    print("->", OUT_DIR / "prm_score_audit_metrics.csv")


if __name__ == "__main__":
    main()
