#!/usr/bin/env python3
"""Workstream M3: build the 120-step human double-annotation pilot.

Strata (40 each, per ACL-Main plan section 7.2 scaled to the Phase-0 pilot):
  diagonal      rating/type pair on the expected diagonal
                (1-essential, 0-redundant, -1-harmful; human-calibrated type)
  off_diagonal  any other rating/type pair
  random        random draw from the remaining pool

Each annotator receives a blinded sheet (independent random order, no rating,
no deletion outcome, no prior labels) plus an HTML reading view. The
step_id mapping is stored separately and must NOT be shared with annotators.
Stdlib only.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from analysis_common import ROOT, as_int, read_csv, stable_hash, write_csv

OUT_DIR = ROOT / "workstream_M3_human_annotation"
STRATUM_SIZE = 40
EXPECTED_DIAGONAL = {1: "essential", 0: "redundant", -1: "harmful"}


def load_contexts() -> dict[str, dict]:
    contexts = {}
    with (ROOT / "data" / "step_trajectory_context.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            contexts[record["step_id"]] = record
    return contexts


def sample_pilot(rows: list[dict]) -> list[dict]:
    def orderer(row: dict) -> int:
        return stable_hash("m3-pilot|" + row["step_id"])

    diagonal, off_diagonal = [], []
    for row in rows:
        rating = as_int(row["prm_rating"])
        type_hc = row["step_type_human_calibrated"].strip().lower()
        (diagonal if EXPECTED_DIAGONAL[rating] == type_hc else off_diagonal).append(row)
    picked = sorted(diagonal, key=orderer)[:STRATUM_SIZE]
    picked += sorted(off_diagonal, key=orderer)[:STRATUM_SIZE]
    chosen = {r["step_id"] for r in picked}
    rest = sorted((r for r in rows if r["step_id"] not in chosen), key=orderer)
    for row in picked:
        row_stratum = "diagonal" if row in diagonal else "off_diagonal"
        row["_stratum"] = row_stratum
    for row in rest[:STRATUM_SIZE]:
        row["_stratum"] = "random"
    return picked + rest[:STRATUM_SIZE]


def render_sheet_rows(sample: list[dict], contexts: dict[str, dict], annotator: str) -> list[dict]:
    ordered = sorted(sample, key=lambda r: stable_hash(f"m3-order-{annotator}|" + r["step_id"]))
    sheet = []
    for order, row in enumerate(ordered, start=1):
        ctx = contexts[row["step_id"]]
        steps = ctx["steps"]
        k = ctx["target_index"]
        sheet.append(
            {
                "annotation_order": order,
                "annotation_id": f"m3-{stable_hash('m3-blind|' + row['step_id']) % 10**8:08d}",
                "problem": ctx["problem"],
                "prefix_steps": "\n\n".join(steps[:k]),
                "target_step": steps[k],
                "downstream_steps": "\n\n".join(steps[k + 1 :]),
                "step_type_label": "",
                "confidence_1to5": "",
                "notes": "",
            }
        )
    return sheet


def render_html(sheet: list[dict], annotator: str) -> str:
    cards = []
    for row in sheet:
        cards.append(
            "<div class='card'>"
            f"<h3>#{row['annotation_order']} &mdash; {row['annotation_id']}</h3>"
            f"<p class='problem'><b>Problem:</b> {html.escape(row['problem'])}</p>"
            f"<details open><summary>Reasoning before the target step</summary>"
            f"<pre>{html.escape(row['prefix_steps']) or '(target is the first step)'}</pre></details>"
            f"<div class='target'><b>TARGET STEP</b><pre>{html.escape(row['target_step'])}</pre></div>"
            f"<details><summary>Original downstream continuation</summary>"
            f"<pre>{html.escape(row['downstream_steps']) or '(target is the last step)'}</pre></details>"
            "</div>"
        )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>M3 pilot sheet {annotator}</title>"
        "<style>body{font-family:Georgia,serif;max-width:900px;margin:24px auto;padding:0 16px}"
        ".card{border:1px solid #c8ccd4;border-radius:8px;padding:12px 16px;margin:18px 0}"
        ".target{background:#fff7e0;border:2px solid #d9a400;border-radius:6px;padding:8px;margin:10px 0}"
        "pre{white-space:pre-wrap;font-family:inherit;margin:6px 0}"
        ".problem{background:#eef3fb;padding:8px;border-radius:6px}</style></head><body>"
        f"<h1>Annotation sheet {annotator} (120 steps)</h1>"
        "<p>Fill in <code>step_type_label</code> (essential / redundant / harmful / uncertain), "
        "<code>confidence_1to5</code> and optional <code>notes</code> in the matching CSV row. "
        "Judge only the TARGET STEP's contribution to solving the problem.</p>"
        + "".join(cards)
        + "</body></html>"
    )


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    rows = read_csv(ROOT / "data" / "master_step_table.csv")
    contexts = load_contexts()
    sample = sample_pilot(rows)

    key_rows = []
    for row in sample:
        key_rows.append(
            {
                "annotation_id": f"m3-{stable_hash('m3-blind|' + row['step_id']) % 10**8:08d}",
                "step_id": row["step_id"],
                "stratum": row["_stratum"],
                "prm_rating": row["prm_rating"],
                "step_type_initial": row["step_type_initial"],
                "step_type_human_calibrated": row["step_type_human_calibrated"],
                "position_bin": row["position_bin"],
            }
        )
    write_csv(OUT_DIR / "m3_pilot_key_DO_NOT_SHARE.csv", key_rows)

    for annotator in ("A", "B"):
        sheet = render_sheet_rows(sample, contexts, annotator)
        write_csv(OUT_DIR / f"m3_pilot_sheet_{annotator}.csv", sheet)
        (OUT_DIR / f"m3_pilot_sheet_{annotator}.html").write_text(
            render_html(sheet, annotator), encoding="utf-8"
        )

    guideline = """# M3 Pilot 标注指南(120 steps,双人独立盲标)

## 任务

对每个 TARGET STEP,仅根据 problem、之前的推理(prefix)和原始下游轨迹,
判断该步骤对解题的语义贡献,四选一:

- **essential**:删除该步会丢失后续推理需要的关键信息或关键推进;
- **redundant**:该步重复已有信息、纯过渡或不影响后续推理;
- **harmful**:该步引入错误、误导方向或把推理锚定在坏路径上;
- **uncertain**:贡献依赖无法判断的上下文,或多种解读均合理。

## 规则

1. 独立完成,不与另一位标注者讨论;
2. 只看 sheet 内提供的文本;不查询 PRM 分数、删除实验结果或任何旧标签;
3. `confidence_1to5`:1=非常不确定,5=非常确定;
4. 不要强行三分类:确实无法判断时用 uncertain 并在 notes 说明;
5. 每完成 30 条休息一次,避免疲劳漂移;
6. 完成后只回传 CSV(三列填写完毕),不要改动其他列。

## 材料

- `m3_pilot_sheet_A.csv` / `m3_pilot_sheet_B.csv`:两位标注者各自的表(顺序不同);
- 同名 `.html`:阅读视图(与 CSV 行一一对应,以 annotation_id 对齐);
- `m3_pilot_key_DO_NOT_SHARE.csv`:仅项目负责人保存,用于回链 step_id 与计算一致性。

## 评价(标注完成后)

raw agreement、Cohen's kappa、Gwet's AC1、per-class precision/recall、
分歧类型学;pilot 通过标准:raw agreement >= 80% 且 kappa/AC1 >= 0.65
(达标后扩展到 300-600 steps 正式标注)。
"""
    (OUT_DIR / "m3_annotation_guideline.md").write_text(guideline, encoding="utf-8")

    strata = {}
    for row in key_rows:
        strata[row["stratum"]] = strata.get(row["stratum"], 0) + 1
    summary = {
        "pilot_steps": len(key_rows),
        "strata": strata,
        "expected_diagonal_mapping": {str(k): v for k, v in EXPECTED_DIAGONAL.items()},
        "blinding": "sheets contain no step_id, rating, outcome, or prior label",
        "orders_differ_between_annotators": True,
    }
    (OUT_DIR / "m3_pilot_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("Workstream M3 pilot generated:", OUT_DIR, summary)


if __name__ == "__main__":
    main()
