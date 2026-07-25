#!/usr/bin/env python3
"""Analyze the returned four-annotator sheets (2026-07-25).

M3 pilot (120 steps, each labeled by two independent annotators):
  raw agreement, Cohen's kappa, Gwet's AC1 per pair and pooled
  (gate: agreement >= 0.80 and kappa/AC1 >= 0.65), consensus labels,
  disagreement list, and validity against dataset labels and the frozen
  deletion outcomes.

M4 paraphrase fidelity audit (140 items, single coverage):
  fidelity distribution overall and per strong-control group
  (gate: faithful + minor_deviation >= 0.90).

Stdlib only; run from the repository root.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from analysis_common import ROOT, as_float, as_int, fmt, read_csv, write_csv

RET_DIR = ROOT / "data" / "annotations" / "returns_2026-07-25"
M3_DIR = ROOT / "workstream_M3_human_annotation"
M4_DIR = ROOT / "workstream_M4_strong_controls"
M3_CATS = ["essential", "redundant", "harmful", "uncertain"]
M4_CATS = ["faithful", "minor_deviation", "meaning_changed", "uncertain"]
PAIRS = [("P1", "P2"), ("P3", "P4")]


def load_returns() -> dict[str, dict[str, dict]]:
    data: dict[str, dict[str, dict]] = {}
    for person in ("P1", "P2", "P3", "P4"):
        rows = read_csv(RET_DIR / f"annotations_{person}.csv")
        data[person] = {r["annotation_id"]: r for r in rows}
        assert len(data[person]) == 95, (person, len(data[person]))
    return data


def agreement_metrics(pairs: list[tuple[str, str]], cats: list[str]) -> dict:
    n = len(pairs)
    p_o = sum(1 for a, b in pairs if a == b) / n
    marg_a = Counter(a for a, _ in pairs)
    marg_b = Counter(b for _, b in pairs)
    p_e_kappa = sum((marg_a[c] / n) * (marg_b[c] / n) for c in cats)
    kappa = (p_o - p_e_kappa) / (1 - p_e_kappa) if p_e_kappa < 1 else float("nan")
    pi = {c: (marg_a[c] + marg_b[c]) / (2 * n) for c in cats}
    p_e_ac1 = sum(pi[c] * (1 - pi[c]) for c in cats) / (len(cats) - 1)
    ac1 = (p_o - p_e_ac1) / (1 - p_e_ac1) if p_e_ac1 < 1 else float("nan")
    return {"n_items": n, "raw_agreement": p_o, "cohen_kappa": kappa, "gwet_ac1": ac1}


def analyze_m3(returns: dict) -> dict:
    key = {r["annotation_id"]: r for r in read_csv(M3_DIR / "m3_pilot_key_DO_NOT_SHARE.csv")}
    steps = {r["step_id"]: r for r in read_csv(ROOT / "data" / "master_step_table.csv")}
    texts = {}
    for sheet in ("P1", "P3"):
        for row in read_csv(M3_DIR / "four_way" / f"m3_sheet_{sheet}.csv"):
            texts[row["annotation_id"]] = row["target_step"]

    metric_rows, all_pairs = [], []
    consensus, disagreements = {}, []
    for rater_a, rater_b in PAIRS:
        ids = sorted(
            i for i in returns[rater_a] if returns[rater_a][i]["task"] == "m3"
        )
        assert ids == sorted(
            i for i in returns[rater_b] if returns[rater_b][i]["task"] == "m3"
        ), f"item mismatch {rater_a}/{rater_b}"
        pair_labels = [
            (returns[rater_a][i]["label"], returns[rater_b][i]["label"]) for i in ids
        ]
        all_pairs.extend(pair_labels)
        metrics = agreement_metrics(pair_labels, M3_CATS)
        metric_rows.append(
            {"scope": f"pair_{rater_a}x{rater_b}",
             **{k: fmt(v, 4) if isinstance(v, float) else v for k, v in metrics.items()}}
        )
        for i in ids:
            lab_a, lab_b = returns[rater_a][i]["label"], returns[rater_b][i]["label"]
            if lab_a == lab_b:
                consensus[i] = lab_a
            else:
                disagreements.append(
                    {
                        "annotation_id": i,
                        "step_id": key[i]["step_id"],
                        "rater_pair": f"{rater_a}x{rater_b}",
                        "label_a": lab_a,
                        "label_b": lab_b,
                        "conf_a": returns[rater_a][i]["confidence_1to5"],
                        "conf_b": returns[rater_b][i]["confidence_1to5"],
                        "notes_a": returns[rater_a][i]["notes"],
                        "notes_b": returns[rater_b][i]["notes"],
                        "dataset_type": key[i]["step_type_human_calibrated"],
                        "prm_rating": key[i]["prm_rating"],
                        "target_step": texts.get(i, ""),
                    }
                )
    pooled = agreement_metrics(all_pairs, M3_CATS)
    metric_rows.append(
        {"scope": "pooled_120",
         **{k: fmt(v, 4) if isinstance(v, float) else v for k, v in pooled.items()}}
    )
    solid = [(a, b) for a, b in all_pairs if a != "uncertain" and b != "uncertain"]
    metrics3 = agreement_metrics(solid, ["essential", "redundant", "harmful"])
    metric_rows.append(
        {"scope": "pooled_excl_uncertain",
         **{k: fmt(v, 4) if isinstance(v, float) else v for k, v in metrics3.items()}}
    )
    write_csv(M3_DIR / "m3_pilot_agreement.csv", metric_rows)

    confusion = Counter(all_pairs)
    write_csv(
        M3_DIR / "m3_pilot_confusion.csv",
        [
            {"rater_a\\rater_b": ca, **{cb: confusion.get((ca, cb), 0) for cb in M3_CATS}}
            for ca in M3_CATS
        ],
    )
    write_csv(M3_DIR / "m3_pilot_disagreements.csv", disagreements)

    validity_rows = []
    effect_by_label: dict[str, list[dict]] = defaultdict(list)
    match_dataset = 0
    for i, label in consensus.items():
        k = key[i]
        step = steps[k["step_id"]]
        if label == k["step_type_human_calibrated"]:
            match_dataset += 1
        effect_by_label[label].append(step)
    for label in M3_CATS:
        group = effect_by_label.get(label, [])
        if not group:
            continue
        semantic = [
            as_float(s["pure_semantic_effect"])
            for s in group
            if s["pure_semantic_effect"] not in ("", "nan")
        ]
        validity_rows.append(
            {
                "human_consensus_label": label,
                "n_steps": len(group),
                "share_rating_neg1": fmt(
                    sum(1 for s in group if as_int(s["prm_rating"]) == -1) / len(group), 3
                ),
                "mean_target_effect_pp": fmt(
                    100 * sum(as_float(s["target_effect"]) for s in group) / len(group), 2
                ),
                "mean_pure_semantic_effect_pp": fmt(
                    100 * sum(semantic) / len(semantic), 2
                ) if semantic else "",
                "danger_step_share": fmt(
                    sum(1 for s in group if as_int(s["correct_to_wrong_count"]) > 0)
                    / len(group), 3
                ),
                "benefit_step_share": fmt(
                    sum(1 for s in group if as_int(s["wrong_to_correct_count"]) > 0)
                    / len(group), 3
                ),
            }
        )
    write_csv(M3_DIR / "m3_pilot_validity.csv", validity_rows)

    return {
        "per_pair": metric_rows,
        "consensus_items": len(consensus),
        "disagreements": len(disagreements),
        "consensus_match_dataset_label": fmt(match_dataset / len(consensus), 4),
        "gate_agreement_ge_080": pooled["raw_agreement"] >= 0.80,
        "gate_kappa_or_ac1_ge_065": pooled["cohen_kappa"] >= 0.65 or pooled["gwet_ac1"] >= 0.65,
        "pooled": pooled,
    }


def analyze_m4(returns: dict) -> dict:
    key = {
        r["annotation_id"]: r
        for r in read_csv(M4_DIR / "m4_fidelity_key_DO_NOT_SHARE.csv")
    }
    rows = []
    for person in ("P1", "P2", "P3", "P4"):
        for i, r in returns[person].items():
            if r["task"] == "m4_fidelity":
                rows.append(
                    {
                        "annotator": person,
                        "annotation_id": i,
                        "label": r["label"],
                        "confidence": r["confidence_1to5"],
                        "notes": r["notes"],
                        "group": key[i]["strong_control_group"],
                        "step_id": key[i]["step_id"],
                    }
                )
    assert len(rows) == 140, len(rows)

    def rates(subset: list[dict]) -> dict:
        counts = Counter(r["label"] for r in subset)
        n = len(subset)
        return {
            "n_items": n,
            **{c: counts.get(c, 0) for c in M4_CATS},
            "strict_faithful_rate": fmt(counts.get("faithful", 0) / n, 4),
            "fidelity_rate_faithful_plus_minor": fmt(
                (counts.get("faithful", 0) + counts.get("minor_deviation", 0)) / n, 4
            ),
            "meaning_changed_rate": fmt(counts.get("meaning_changed", 0) / n, 4),
        }

    out_rows = [{"scope": "overall", **rates(rows)}]
    for group in sorted({r["group"] for r in rows}):
        out_rows.append(
            {"scope": f"group:{group}", **rates([r for r in rows if r["group"] == group])}
        )
    for person in ("P1", "P2", "P3", "P4"):
        out_rows.append(
            {"scope": f"annotator:{person}",
             **rates([r for r in rows if r["annotator"] == person])}
        )
    write_csv(M4_DIR / "m4_fidelity_results.csv", out_rows)

    flagged = [
        {k: r[k] for k in ("annotation_id", "step_id", "group", "annotator",
                            "label", "confidence", "notes")}
        for r in rows
        if r["label"] in ("meaning_changed", "uncertain")
    ]
    write_csv(M4_DIR / "m4_fidelity_flagged_items.csv", flagged)

    overall = rates(rows)
    return {
        "overall": overall,
        "flagged_items": len(flagged),
        "gate_fidelity_ge_090": float(overall["fidelity_rate_faithful_plus_minor"]) >= 0.90,
    }


def main() -> None:
    returns = load_returns()
    m3 = analyze_m3(returns)
    m4 = analyze_m4(returns)
    print(json.dumps({"m3": m3, "m4": m4}, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
