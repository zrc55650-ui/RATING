#!/usr/bin/env python3
"""Build the blinded M4 paraphrase-fidelity audit sheet (>=120 items).

Samples accepted paraphrases from workstream_M4_strong_controls stratified by
strong-control group (group is hidden from the annotator), shuffles them with
the frozen seed, and emits:

  m4_fidelity_sheet.csv          annotator-facing sheet (fill 3 columns)
  m4_fidelity_sheet.html         reading view, one card per item
  m4_fidelity_key_DO_NOT_SHARE.csv   id -> step_id/group mapping (never share)
  m4_fidelity_summary.json

Stdlib only; run from the repository root.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict

from analysis_common import ROOT, SEED, read_csv, stable_hash, write_csv, xml_escape

OUT_DIR = ROOT / "workstream_M4_strong_controls"
TARGET_ITEMS = 140


def main() -> None:
    paraphrases = []
    with (OUT_DIR / "m4_paraphrases.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                paraphrases.append(json.loads(line))
    group_by_step = {
        row["step_id"]: row["strong_control_group"]
        for row in read_csv(OUT_DIR / "strong_control_sampling_manifest.csv")
    }
    problem_by_step = {
        row["step_id"]: row["problem"]
        for row in read_csv(ROOT / "data" / "master_step_table.csv")
    }

    by_group: dict[str, list[dict]] = defaultdict(list)
    for record in paraphrases:
        by_group[group_by_step[record["step_id"]]].append(record)
    for records in by_group.values():
        records.sort(key=lambda r: r["step_id"])

    total = sum(len(v) for v in by_group.values())
    rng = random.Random(SEED)
    sample: list[dict] = []
    for group in sorted(by_group):
        records = by_group[group]
        quota = round(TARGET_ITEMS * len(records) / total)
        sample.extend(rng.sample(records, min(quota, len(records))))
    rng.shuffle(sample)

    sheet_rows, key_rows, cards = [], [], []
    for order, record in enumerate(sample, start=1):
        annotation_id = f"m4f-{stable_hash('m4-fidelity|' + record['step_id']) % 10**8:08d}"
        problem = problem_by_step[record["step_id"]]
        sheet_rows.append(
            {
                "annotation_order": order,
                "annotation_id": annotation_id,
                "problem": problem,
                "original_step": record["original"],
                "paraphrase_step": record["paraphrase"],
                "fidelity_label": "",
                "confidence_1to5": "",
                "notes": "",
            }
        )
        key_rows.append(
            {
                "annotation_id": annotation_id,
                "step_id": record["step_id"],
                "strong_control_group": group_by_step[record["step_id"]],
                "length_ratio": record["length_ratio"],
                "paraphrase_model": record["model"],
            }
        )
        cards.append(
            f"<div class='card'><h3>#{order} &middot; {annotation_id}</h3>"
            f"<div class='problem'><b>Problem</b><pre>{xml_escape(problem)}</pre></div>"
            f"<div class='original'><b>ORIGINAL STEP</b><pre>{xml_escape(record['original'])}</pre></div>"
            f"<div class='paraphrase'><b>PARAPHRASE</b><pre>{xml_escape(record['paraphrase'])}</pre></div>"
            "</div>"
        )

    write_csv(OUT_DIR / "m4_fidelity_sheet.csv", sheet_rows)
    write_csv(OUT_DIR / "m4_fidelity_key_DO_NOT_SHARE.csv", key_rows)
    (OUT_DIR / "m4_fidelity_sheet.html").write_text(
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>M4 paraphrase fidelity audit</title>"
        "<style>body{font-family:Georgia,serif;max-width:900px;margin:24px auto;padding:0 16px}"
        ".card{border:1px solid #c8ccd4;border-radius:8px;padding:12px 16px;margin:18px 0}"
        ".original{background:#fff7e0;border:2px solid #d9a400;border-radius:6px;padding:8px;margin:10px 0}"
        ".paraphrase{background:#e8f6ec;border:2px solid #2e8b57;border-radius:6px;padding:8px;margin:10px 0}"
        "pre{white-space:pre-wrap;font-family:inherit;margin:6px 0}"
        ".problem{background:#eef3fb;padding:8px;border-radius:6px}</style></head><body>"
        f"<h1>M4 paraphrase fidelity audit ({len(sheet_rows)} items)</h1>"
        "<p>Fill in <code>fidelity_label</code> (faithful / minor_deviation / "
        "meaning_changed / uncertain), <code>confidence_1to5</code> and optional "
        "<code>notes</code> in the matching CSV row. Judge ONLY whether the "
        "paraphrase preserves the complete meaning of the original step &mdash; "
        "including any errors the original contains.</p>"
        + "".join(cards)
        + "</body></html>",
        encoding="utf-8",
    )
    summary = {
        "items": len(sheet_rows),
        "seed": SEED,
        "per_group": {g: sum(1 for k in key_rows if k["strong_control_group"] == g)
                      for g in sorted(by_group)},
        "source_paraphrases": total,
    }
    (OUT_DIR / "m4_fidelity_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
