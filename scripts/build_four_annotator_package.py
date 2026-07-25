#!/usr/bin/env python3
"""Split the M3 pilot (120 double-annotated) and M4 fidelity audit (140 single)
across FOUR annotators at roughly one hour each.

Design:
  M3  P1 and P2 independently annotate half H1 (60 steps); P3 and P4 annotate
      half H2. Every step keeps exactly two independent annotators. Halves are
      stratified by the sampling stratum; P1/P3 see sheet-A item order,
      P2/P4 see sheet-B item order (order-effect control preserved).
  M4  140 paraphrase items dealt into four 35-item shares, interleaved across
      strong-control groups (group stays hidden from annotators).

Outputs land in workstream_M3_human_annotation/four_way/ and
workstream_M4_strong_controls/four_way/. Assignment keys are *_DO_NOT_SHARE
files. Stdlib only; run from the repository root.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict

from analysis_common import ROOT, SEED, read_csv, write_csv, xml_escape

M3_DIR = ROOT / "workstream_M3_human_annotation"
M4_DIR = ROOT / "workstream_M4_strong_controls"

STYLE = (
    "<style>body{font-family:Georgia,serif;max-width:900px;margin:24px auto;padding:0 16px}"
    ".card{border:1px solid #c8ccd4;border-radius:8px;padding:12px 16px;margin:18px 0}"
    ".target{background:#fff7e0;border:2px solid #d9a400;border-radius:6px;padding:8px;margin:10px 0}"
    ".paraphrase{background:#e8f6ec;border:2px solid #2e8b57;border-radius:6px;padding:8px;margin:10px 0}"
    "pre{white-space:pre-wrap;font-family:inherit;margin:6px 0}"
    ".problem{background:#eef3fb;padding:8px;border-radius:6px}</style>"
)


def html_doc(title: str, intro: str, cards: list[str]) -> str:
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title>{STYLE}</head><body>"
        f"<h1>{title}</h1><p>{intro}</p>" + "".join(cards) + "</body></html>"
    )


def build_m3() -> dict:
    key = read_csv(M3_DIR / "m3_pilot_key_DO_NOT_SHARE.csv")
    sheet_a = read_csv(M3_DIR / "m3_pilot_sheet_A.csv")
    sheet_b = read_csv(M3_DIR / "m3_pilot_sheet_B.csv")

    rng = random.Random(SEED + 4)
    halves: dict[str, str] = {}
    by_stratum: dict[str, list[str]] = defaultdict(list)
    for row in key:
        by_stratum[row["stratum"]].append(row["annotation_id"])
    for stratum in sorted(by_stratum):
        ids = sorted(by_stratum[stratum])
        rng.shuffle(ids)
        for i, annotation_id in enumerate(ids):
            halves[annotation_id] = "H1" if i < len(ids) // 2 else "H2"

    plan = {"P1": ("H1", sheet_a), "P2": ("H1", sheet_b),
            "P3": ("H2", sheet_a), "P4": ("H2", sheet_b)}
    out_dir = M3_DIR / "four_way"
    out_dir.mkdir(exist_ok=True)
    assignment_rows = []
    for person in sorted(plan):
        half, source = plan[person]
        rows = [dict(r) for r in source if halves[r["annotation_id"]] == half]
        cards = []
        for order, row in enumerate(rows, start=1):
            row["annotation_order"] = order
            cards.append(
                f"<div class='card'><h3>#{order} &middot; {row['annotation_id']}</h3>"
                f"<div class='problem'><b>Problem</b><pre>{xml_escape(row['problem'])}</pre></div>"
                f"<b>Prefix (before the target step)</b><pre>{xml_escape(row['prefix_steps'])}</pre>"
                f"<div class='target'><b>TARGET STEP</b><pre>{xml_escape(row['target_step'])}</pre></div>"
                f"<b>Downstream (after the target step)</b><pre>{xml_escape(row['downstream_steps'])}</pre>"
                "</div>"
            )
            assignment_rows.append(
                {"task": "m3", "annotator": person, "annotation_id": row["annotation_id"],
                 "half": half}
            )
        write_csv(out_dir / f"m3_sheet_{person}.csv", rows)
        (out_dir / f"m3_sheet_{person}.html").write_text(
            html_doc(
                f"M3 annotation sheet {person} (60 steps)",
                "Fill in <code>step_type_label</code> (essential / redundant / harmful / "
                "uncertain), <code>confidence_1to5</code> and optional <code>notes</code> "
                "in the matching CSV row. Judge only the TARGET STEP's contribution.",
                cards,
            ),
            encoding="utf-8",
        )
    write_csv(out_dir / "m3_four_way_assignment_DO_NOT_SHARE.csv", assignment_rows)
    return {p: sum(1 for r in assignment_rows if r["annotator"] == p) for p in sorted(plan)}


def build_m4() -> dict:
    key_rows = read_csv(M4_DIR / "m4_fidelity_key_DO_NOT_SHARE.csv")
    group_of = {r["annotation_id"]: r["strong_control_group"] for r in key_rows}
    sheet = read_csv(M4_DIR / "m4_fidelity_sheet.csv")

    rng = random.Random(SEED + 44)
    by_group: dict[str, list[dict]] = defaultdict(list)
    for row in sheet:
        by_group[group_of[row["annotation_id"]]].append(dict(row))
    interleaved: list[dict] = []
    pools = {g: rng.sample(v, len(v)) for g, v in by_group.items()}
    while any(pools.values()):
        for group in sorted(pools):
            if pools[group]:
                interleaved.append(pools[group].pop())

    out_dir = M4_DIR / "four_way"
    out_dir.mkdir(exist_ok=True)
    persons = ["P1", "P2", "P3", "P4"]
    share = len(interleaved) // len(persons)
    assignment_rows, counts = [], {}
    for i, person in enumerate(persons):
        rows = interleaved[i * share:(i + 1) * share]
        rows.sort(key=lambda r: int(r["annotation_order"]))
        cards = []
        for order, row in enumerate(rows, start=1):
            row["annotation_order"] = order
            cards.append(
                f"<div class='card'><h3>#{order} &middot; {row['annotation_id']}</h3>"
                f"<div class='problem'><b>Problem</b><pre>{xml_escape(row['problem'])}</pre></div>"
                f"<div class='target'><b>ORIGINAL STEP</b><pre>{xml_escape(row['original_step'])}</pre></div>"
                f"<div class='paraphrase'><b>PARAPHRASE</b><pre>{xml_escape(row['paraphrase_step'])}</pre></div>"
                "</div>"
            )
            assignment_rows.append(
                {"task": "m4_fidelity", "annotator": person,
                 "annotation_id": row["annotation_id"],
                 "strong_control_group": group_of[row["annotation_id"]]}
            )
        write_csv(out_dir / f"m4_fidelity_sheet_{person}.csv", rows)
        (out_dir / f"m4_fidelity_sheet_{person}.html").write_text(
            html_doc(
                f"M4 paraphrase fidelity sheet {person} ({len(rows)} items)",
                "Fill in <code>fidelity_label</code> (faithful / minor_deviation / "
                "meaning_changed / uncertain), <code>confidence_1to5</code> and optional "
                "<code>notes</code>. Judge ONLY whether the paraphrase preserves the "
                "complete meaning of the original step &mdash; including any errors.",
                cards,
            ),
            encoding="utf-8",
        )
        counts[person] = Counter(
            group_of[r["annotation_id"]]
            for r in assignment_rows
            if r["annotator"] == person
        )
    write_csv(out_dir / "m4_four_way_assignment_DO_NOT_SHARE.csv", assignment_rows)
    return {p: dict(c) for p, c in counts.items()}


def main() -> None:
    m3_counts = build_m3()
    m4_counts = build_m4()
    summary = {"seed": SEED, "m3_items_per_annotator": m3_counts,
               "m4_items_per_annotator_by_group": m4_counts}
    (M3_DIR / "four_way" / "four_way_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
