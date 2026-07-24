#!/usr/bin/env python3
"""Build a standalone blind re-review page for judge-audit disagreements."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from build_judge_audit_html import (
    EXPECTED_FIELDS,
    clean_display_text,
    wrap_bare_math,
    wrap_bare_tex_lines,
)


ROOT = Path(__file__).resolve().parent
AUDIT_DIR = ROOT / "workstream_A_judge_audit"
MANIFEST = AUDIT_DIR / "judge_audit_sampling_manifest.csv"
ADJUDICATED = (
    AUDIT_DIR / "judge_audit_adjudication_completed_pre_disagreement_review.csv"
)
REVIEW_CSV = ROOT / "build" / "judge_audit_disagreement_review.csv"
REVIEW_HTML = ROOT / "build" / "judge_audit_disagreement_review.html"

HUMAN_FIELDS = [
    "human_label",
    "human_final_answer_normalized",
    "human_reason",
    "human_tool_needed",
    "human_confidence",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def is_human_correct(label: str) -> bool:
    return label.strip() == "Correct"


def is_judge_correct(label: str) -> bool:
    return label.strip() in {"1", "Correct", "correct"}


def safe_json(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def select_disagreements() -> list[dict[str, str]]:
    manifest = read_csv(MANIFEST)
    adjudicated = read_csv(ADJUDICATED)
    human_by_id = {row["audit_id"]: row for row in adjudicated}

    if len(manifest) != 200 or len(adjudicated) != 200:
        raise ValueError(
            f"Expected 200 rows in each input; got {len(manifest)} and "
            f"{len(adjudicated)}"
        )
    if set(human_by_id) != {row["audit_id"] for row in manifest}:
        raise ValueError("Audit IDs do not match between inputs")

    selected: list[dict[str, str]] = []
    for source in manifest:
        prior = human_by_id[source["audit_id"]]
        if is_judge_correct(source["judge_label"]) == is_human_correct(
            prior["human_label"]
        ):
            continue
        selected.append(
            {
                "audit_id": source["audit_id"],
                "annotation_instruction": (
                    "Independently re-review only this candidate output against "
                    "the question and reference answer. Choose exactly one label: "
                    "Correct; Incorrect; Ambiguous / insufficient information; "
                    "No valid final answer. Do not infer experimental condition, "
                    "automated judgment, or any prior human judgment."
                ),
                "question": source["question"],
                "ground_truth_answer": source["ground_truth_answer"],
                "candidate_output": source["candidate_output"],
                **{field: "" for field in HUMAN_FIELDS},
            }
        )

    if len(selected) != 28:
        raise ValueError(f"Expected 28 disagreements; got {len(selected)}")
    return selected


def write_review_csv(rows: list[dict[str, str]]) -> None:
    with REVIEW_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def render_html(rows: list[dict[str, str]]) -> str:
    display_rows = []
    for index, row in enumerate(rows, 1):
        display_rows.append(
            {
                **row,
                "review_id": f"R{index:02d}",
                "question_display": wrap_bare_tex_lines(
                    clean_display_text(row["question"])
                ),
                "reference_display": wrap_bare_math(
                    clean_display_text(row["ground_truth_answer"])
                ),
                "candidate_display": wrap_bare_tex_lines(
                    clean_display_text(
                        row["candidate_output"], unwrap_continuation=True
                    )
                ),
            }
        )

    data = safe_json(display_rows)
    fields = safe_json(EXPECTED_FIELDS)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Judge Audit 分歧记录盲审</title>
  <script>
    window.MathJax = {{
      tex: {{inlineMath: [["$", "$"], ["\\\\(", "\\\\)"]]}},
      svg: {{fontCache: "global"}}
    }};
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
  <style>
    :root {{
      color-scheme: light;
      --ink:#172033; --muted:#667085; --line:#d9dee8;
      --panel:#fff; --soft:#f5f7fb; --blue:#275efe; --green:#138a5b;
    }}
    * {{box-sizing:border-box}}
    body {{
      margin:0; color:var(--ink); background:var(--soft);
      font:15px/1.55 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
    }}
    header {{
      position:sticky; top:0; z-index:5; background:rgba(255,255,255,.96);
      border-bottom:1px solid var(--line); padding:14px 20px;
      display:flex; gap:18px; align-items:center; justify-content:space-between;
    }}
    h1 {{font-size:19px; margin:0}}
    .progress {{min-width:230px}}
    .progress-line {{height:8px; background:#e8ebf2; border-radius:9px; overflow:hidden}}
    .progress-line span {{display:block; height:100%; width:0; background:var(--green)}}
    .progress-text {{font-size:13px; color:var(--muted); margin-bottom:4px}}
    main {{max-width:1100px; margin:22px auto; padding:0 18px 80px}}
    .notice {{
      padding:13px 16px; margin-bottom:16px; border:1px solid #b9ccff;
      border-radius:10px; background:#eef3ff;
    }}
    .card {{
      background:var(--panel); border:1px solid var(--line);
      border-radius:12px; margin-bottom:14px; padding:18px;
      box-shadow:0 2px 9px rgba(16,24,40,.04);
    }}
    .case-head {{display:flex; justify-content:space-between; align-items:center}}
    .case-id {{font-weight:750; font-size:17px}}
    .subtle {{color:var(--muted); font-size:13px}}
    h2 {{font-size:14px; margin:0 0 8px; color:#344054}}
    .content {{white-space:pre-wrap; overflow-wrap:anywhere}}
    .candidate {{max-height:440px; overflow:auto}}
    .labels {{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px}}
    .label {{
      display:flex; gap:9px; align-items:center; border:1px solid var(--line);
      border-radius:9px; padding:10px 12px; cursor:pointer;
    }}
    .label:has(input:checked) {{border-color:var(--blue); background:#eef3ff}}
    .grid {{display:grid; grid-template-columns:1fr 1fr; gap:13px; margin-top:14px}}
    label.field {{display:block; font-weight:650}}
    input[type=text], select, textarea {{
      width:100%; margin-top:5px; border:1px solid #cbd1dc; border-radius:8px;
      padding:9px 10px; background:#fff; font:inherit; color:inherit;
    }}
    textarea {{min-height:88px; resize:vertical}}
    .wide {{grid-column:1/-1}}
    .actions {{
      position:fixed; left:0; right:0; bottom:0; z-index:5;
      display:flex; justify-content:center; gap:10px; padding:12px;
      background:rgba(255,255,255,.97); border-top:1px solid var(--line);
    }}
    button {{
      border:1px solid #bbc2cf; border-radius:8px; padding:9px 15px;
      background:#fff; color:var(--ink); font-weight:700; cursor:pointer;
    }}
    button.primary {{background:var(--blue); border-color:var(--blue); color:#fff}}
    button:disabled {{opacity:.45; cursor:not-allowed}}
    .done {{color:var(--green); font-weight:750}}
    @media (max-width:700px) {{
      header {{align-items:flex-start; flex-direction:column}}
      .progress {{width:100%}}
      .labels,.grid {{grid-template-columns:1fr}}
      .wide {{grid-column:auto}}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Judge Audit 分歧记录盲审</h1>
      <div class="subtle">28 条记录 · 自动保存到当前浏览器</div>
    </div>
    <div class="progress">
      <div class="progress-text" id="progressText"></div>
      <div class="progress-line"><span id="progressBar"></span></div>
    </div>
  </header>
  <main>
    <div class="notice">
      请根据题目、参考答案和候选输出重新独立判断。页面不会显示机器标签、
      第一次人工标签或实验条件。只有确认第一次判断确实有误时才改变结论。
    </div>
    <section class="card">
      <div class="case-head">
        <div class="case-id" id="reviewId"></div>
        <div id="doneState"></div>
      </div>
    </section>
    <section class="card"><h2>题目</h2><div class="content" id="question"></div></section>
    <section class="card"><h2>参考答案</h2><div class="content" id="reference"></div></section>
    <section class="card"><h2>候选输出</h2><div class="content candidate" id="candidate"></div></section>
    <section class="card">
      <h2>独立复核结论</h2>
      <div class="labels" id="labels"></div>
      <div class="grid">
        <label class="field">候选输出的最终答案（可选）
          <input type="text" id="normalized">
        </label>
        <label class="field">是否需要工具
          <select id="tool">
            <option value="">请选择</option><option value="no">no</option>
            <option value="yes">yes</option>
          </select>
        </label>
        <label class="field">信心
          <select id="confidence">
            <option value="">请选择</option><option value="high">high</option>
            <option value="medium">medium</option><option value="low">low</option>
          </select>
        </label>
        <label class="field wide">一句话说明判断依据
          <textarea id="reason"></textarea>
        </label>
      </div>
      <div class="subtle" style="margin-top:10px">
        完成条件：标签、是否需要工具、信心和判断依据均已填写。
        快捷键 1–4 选择标签，Ctrl+Enter 保存并进入下一条。
      </div>
    </section>
  </main>
  <div class="actions">
    <button id="prev">上一条</button>
    <button id="next">保存并下一条</button>
    <button id="backup">备份 JSON</button>
    <button class="primary" id="export">导出 Completed CSV</button>
  </div>
  <script>
    "use strict";
    const STORAGE_KEY = "judge-audit-disagreement-review-v1";
    const FIELDS = {fields};
    const LABELS = [
      "Correct", "Incorrect", "Ambiguous / insufficient information",
      "No valid final answer"
    ];
    const rows = {data};
    let current = 0;

    const $ = id => document.getElementById(id);
    const complete = row => Boolean(
      row.human_label && row.human_reason && row.human_tool_needed &&
      row.human_confidence
    );
    function restore() {{
      try {{
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{{}}");
        for (const row of rows) Object.assign(row, saved[row.audit_id] || {{}});
      }} catch (_) {{}}
    }}
    function persist() {{
      const data = Object.fromEntries(rows.map(row => [row.audit_id, {{
        human_label:row.human_label,
        human_final_answer_normalized:row.human_final_answer_normalized,
        human_reason:row.human_reason,
        human_tool_needed:row.human_tool_needed,
        human_confidence:row.human_confidence
      }}]));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    }}
    function commit() {{
      const row = rows[current];
      row.human_label =
        document.querySelector('input[name=label]:checked')?.value || "";
      row.human_final_answer_normalized = $("normalized").value.trim();
      row.human_reason = $("reason").value.trim();
      row.human_tool_needed = $("tool").value;
      row.human_confidence = $("confidence").value;
      persist();
      updateProgress();
    }}
    function typeset() {{
      if (window.MathJax?.typesetPromise) MathJax.typesetPromise();
    }}
    function render() {{
      const row = rows[current];
      $("reviewId").textContent = `${{row.review_id}} · 第 ${{current + 1}} / ${{rows.length}} 条`;
      $("doneState").textContent = complete(row) ? "已完成" : "未完成";
      $("doneState").className = complete(row) ? "done" : "subtle";
      $("question").innerHTML = row.question_display;
      $("reference").innerHTML = row.reference_display;
      $("candidate").innerHTML = row.candidate_display;
      $("labels").innerHTML = LABELS.map((label, i) =>
        `<label class="label"><input type="radio" name="label" value="${{label}}" ` +
        `${{row.human_label === label ? "checked" : ""}}>` +
        `<span>${{i + 1}}. ${{label}}</span></label>`
      ).join("");
      $("normalized").value = row.human_final_answer_normalized || "";
      $("reason").value = row.human_reason || "";
      $("tool").value = row.human_tool_needed || "";
      $("confidence").value = row.human_confidence || "";
      $("prev").disabled = current === 0;
      $("next").disabled = current === rows.length - 1;
      window.scrollTo({{top:0, behavior:"smooth"}});
      typeset();
    }}
    function updateProgress() {{
      const count = rows.filter(complete).length;
      $("progressText").textContent = `已完成 ${{count}} / ${{rows.length}}`;
      $("progressBar").style.width = `${{100 * count / rows.length}}%`;
    }}
    function escapeCsv(value) {{
      const text = String(value ?? "");
      return /[",\\r\\n]/.test(text) ? `"${{text.replaceAll('"','""')}}"` : text;
    }}
    function download(name, content, type) {{
      const url = URL.createObjectURL(new Blob([content], {{type}}));
      const link = Object.assign(document.createElement("a"), {{href:url, download:name}});
      document.body.appendChild(link); link.click(); link.remove();
      URL.revokeObjectURL(url);
    }}
    function exportCsv() {{
      commit();
      const missing = rows.filter(row => !complete(row)).length;
      if (missing && !confirm(`还有 ${{missing}} 条未完成，仍然导出吗？`)) return;
      const lines = [FIELDS.map(escapeCsv).join(",")];
      for (const row of rows) lines.push(
        FIELDS.map(field => escapeCsv(row[field])).join(",")
      );
      download(
        "judge_audit_disagreement_review_completed.csv",
        "\\ufeff" + lines.join("\\r\\n"), "text/csv;charset=utf-8"
      );
    }}
    $("prev").onclick = () => {{commit(); current--; render();}};
    $("next").onclick = () => {{commit(); current++; render();}};
    $("export").onclick = exportCsv;
    $("backup").onclick = () => {{
      commit();
      download(
        "judge_audit_disagreement_review_backup.json",
        JSON.stringify(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{{}}"), null, 2),
        "application/json;charset=utf-8"
      );
    }};
    document.addEventListener("change", event => {{
      if (event.target.matches("input[name=label],select")) commit();
    }});
    for (const id of ["normalized","reason"]) {{
      $(id).addEventListener("input", () => {{
        clearTimeout($(id)._timer);
        $(id)._timer = setTimeout(commit, 250);
      }});
    }}
    document.addEventListener("keydown", event => {{
      const editing = ["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName);
      if (!editing && ["1","2","3","4"].includes(event.key)) {{
        document.querySelectorAll("input[name=label]")[Number(event.key)-1].click();
      }}
      if (event.ctrlKey && event.key === "Enter") {{
        event.preventDefault(); commit();
        if (current < rows.length - 1) {{current++; render();}}
      }}
    }});
    window.addEventListener("beforeunload", commit);
    restore(); updateProgress(); render();
  </script>
</body>
</html>
"""


def main() -> None:
    rows = select_disagreements()
    write_review_csv(rows)
    REVIEW_HTML.write_text(render_html(rows), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "rows": len(rows),
                "csv": str(REVIEW_CSV),
                "html": str(REVIEW_HTML),
                "html_bytes": REVIEW_HTML.stat().st_size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
