#!/usr/bin/env python3
"""Build standalone, blinded HTML annotation interfaces from audit CSV files."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from pathlib import Path


EXPECTED_FIELDS = [
    "audit_id",
    "annotation_instruction",
    "question",
    "ground_truth_answer",
    "candidate_output",
    "human_label",
    "human_final_answer_normalized",
    "human_reason",
    "human_tool_needed",
    "human_confidence",
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-a", default="judge_audit_blinded_sheet_A.csv"
    )
    parser.add_argument(
        "--input-b", default="judge_audit_blinded_sheet_B.csv"
    )
    parser.add_argument(
        "--output-a", default="judge_audit_blinded_sheet_A.html"
    )
    parser.add_argument(
        "--output-b", default="judge_audit_blinded_sheet_B.html"
    )
    parser.add_argument(
        "--sheet",
        choices=("a", "b", "both"),
        default="both",
        help="Build only sheet A, only sheet B, or both sheets.",
    )
    return parser.parse_args()


def read_blind_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_FIELDS:
            raise ValueError(
                f"{path} has unexpected fields: {reader.fieldnames}; "
                f"expected {EXPECTED_FIELDS}"
            )
        rows = list(reader)
    ids = [row["audit_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path} contains duplicate audit IDs")
    return rows


def safe_json_for_script(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def decode_json_string_fragment(value: str) -> str:
    """Best-effort decode for truncated '{"continuation":"..."}' model output."""
    result: list[str] = []
    index = 0
    escapes = {
        '"': '"',
        "\\": "\\",
        "/": "/",
        "n": "\n",
        "r": "\r",
    }
    while index < len(value):
        char = value[index]
        if char != "\\" or index + 1 >= len(value):
            result.append(char)
            index += 1
            continue
        next_char = value[index + 1]
        if next_char == "u" and index + 5 < len(value):
            code = value[index + 2 : index + 6]
            if re.fullmatch(r"[0-9a-fA-F]{4}", code):
                result.append(chr(int(code, 16)))
                index += 6
                continue
        if next_char in escapes:
            result.append(escapes[next_char])
            index += 2
            continue
        result.extend(["\\", next_char])
        index += 2
    return "".join(result)


def clean_truncated_tail(value: str) -> str:
    """Remove a partial final clause from a truncated continuation."""
    text = value.rstrip()
    sentence_ends = list(re.finditer(r'[.!?](?=(?:["\')\]]*)?(?:\s|$))', text))
    if sentence_ends:
        last_end = sentence_ends[-1].end()
        if text[last_end:].strip():
            text = text[:last_end].rstrip()
    else:
        dollar_positions = [
            match.start()
            for match in re.finditer(r"(?<!\\)\$", text)
        ]
        if len(dollar_positions) % 2:
            text = text[: dollar_positions[-1]].rstrip(" \t\r\n,:;")

    return text


def has_damaged_tex_tail(value: str) -> bool:
    """Detect an unfinished TeX command at the very end of an output."""
    text = value.rstrip()
    dollar_count = len(re.findall(r"(?<!\\)\$", text))
    if dollar_count % 2 == 0:
        return False
    return bool(
        re.search(r"\\+\s*$", text)
        or re.search(r"\\(?:text|frac|dfrac|sqrt)\{[^}\n]*$", text)
    )


def clean_display_text(value: str, *, unwrap_continuation: bool = False) -> str:
    """Improve readability without changing the source/exported audit record."""
    text = str(value or "")
    stripped = text.strip()
    truncated_continuation = False
    if unwrap_continuation and stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                for key in ("continuation", "output", "content", "answer"):
                    if isinstance(payload.get(key), str):
                        text = payload[key]
                        break
        except json.JSONDecodeError:
            match = re.match(r'^\s*\{\s*"continuation"\s*:\s*"', text)
            if match:
                fragment = text[match.end() :]
                if fragment.endswith('"}'):
                    fragment = fragment[:-2]
                text = decode_json_string_fragment(fragment)
                truncated_continuation = True

    # Recover TeX commands damaged when JSON escapes such as \f and \t were
    # interpreted as ASCII control characters by an upstream response parser.
    text = (
        text.replace("\b", "\\b")
        .replace("\t", "\\t")
        .replace("\f", "\\f")
        .replace("\v", "\\v")
    )

    for malformed, repaired in [
        ("\\/geq", "\\geq"),
        ("\\/leq", "\\leq"),
        ("\\/neq", "\\neq"),
        ("\\/times", "\\times"),
        ("\\/rightarrow", "\\rightarrow"),
    ]:
        text = text.replace(malformed, repaired)

    # Some malformed generations contain hundreds of empty TeX spacing commands.
    text = re.sub(r"(?:\\+\s*text\s*\{\s*\}\s*){3,}", r"\\;", text)
    text = re.sub(r"(?:\\+\s*,\s*){8,}", r"\\,", text)
    if truncated_continuation or has_damaged_tex_tail(text):
        text = clean_truncated_tail(text)
    return text


def wrap_bare_math(value: str) -> str:
    """Add delimiters to compact answer fields stored as bare TeX."""
    text = value.strip()
    if not text or re.search(r"(?<!\\)\$|\\\(|\\\[", text):
        return text
    return rf"\({text}\)"


BARE_TEX_COMMAND = re.compile(
    r"\\(?:"
    r"frac|dfrac|sqrt|begin|end|text|boxed|binom|cdot|times|theta|pi|"
    r"neq|leq|geq|infty|cup|cap|pm|mathbf|mathbb"
    r")\b"
)


def wrap_bare_tex_lines(value: str) -> str:
    """Wrap an undelimited TeX expression that occupies the end of a line."""
    wrapped_lines: list[str] = []
    for line in value.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        newline = line[len(body) :]
        command = BARE_TEX_COMMAND.search(body)
        has_delimiter = bool(re.search(r"(?<!\\)\$|\\\(|\\\[", body))
        if not command or has_delimiter:
            wrapped_lines.append(line)
            continue

        prefix = body[: command.start()]
        expression = body[command.start() :].rstrip()
        suffix = ""
        if expression.endswith((".", ",", ";", ":")):
            suffix = expression[-1]
            expression = expression[:-1].rstrip()
        wrapped_lines.append(
            f"{prefix}\\({expression}\\){suffix}{newline}"
        )
    return "".join(wrapped_lines)


def build_html(rows: list[dict[str, str]], sheet_name: str, output_name: str) -> str:
    data_json = safe_json_for_script(rows)
    display_rows = {
        row["audit_id"]: {
            "question": wrap_bare_tex_lines(clean_display_text(row["question"])),
            "ground_truth_answer": wrap_bare_math(
                clean_display_text(row["ground_truth_answer"])
            ),
            "candidate_output": wrap_bare_tex_lines(
                clean_display_text(
                    row["candidate_output"], unwrap_continuation=True
                )
            ),
        }
        for row in rows
    }
    display_json = safe_json_for_script(display_rows)
    title = f"Judge Audit Blind Annotation — {sheet_name}"
    storage_key = f"prm-removability-judge-audit-{sheet_name.lower()}-v1"
    completed_csv = Path(output_name).with_suffix("").name + "_completed.csv"
    escaped_title = html.escape(title)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{escaped_title}</title>
  <script>
    window.MathJax = {{
      loader: {{load: ["[tex]/ams"]}},
      tex: {{
        packages: {{"[+]": ["ams"]}},
        inlineMath: [["$", "$"], ["\\\\(", "\\\\)"]],
        displayMath: [["$$", "$$"], ["\\\\[", "\\\\]"]],
        processEscapes: true
      }},
      svg: {{fontCache: "local"}},
      startup: {{typeset: false}}
    }};
  </script>
  <script defer
    src="https://cdn.jsdelivr.net/npm/mathjax@4/tex-svg.js"
    onload="window.auditMathLoaded=true;if(window.auditTypesetAll)window.auditTypesetAll();"
    onerror="window.auditMathFailed=true;if(window.auditUpdateMathStatus)window.auditUpdateMathStatus();"></script>
  <style>
    :root {{
      --bg: #f4f6f9;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #667085;
      --line: #d9dee8;
      --blue: #2357d8;
      --blue-soft: #eaf0ff;
      --green: #087443;
      --green-soft: #e8f7ef;
      --red: #b42318;
      --red-soft: #feefed;
      --amber: #9a6700;
      --amber-soft: #fff6dd;
      --purple: #6941c6;
      --purple-soft: #f3efff;
      --shadow: 0 8px 28px rgba(23, 32, 51, .08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font-family: Inter, "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
    }}
    button, input, textarea, select {{ font: inherit; }}
    button {{ cursor: pointer; }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      gap: 18px;
      padding: 14px 22px;
      background: rgba(255,255,255,.96);
      border-bottom: 1px solid var(--line);
      box-shadow: 0 2px 12px rgba(23, 32, 51, .05);
    }}
    .brand {{ min-width: 250px; }}
    .brand h1 {{ margin: 0; font-size: 18px; }}
    .brand p {{ margin: 3px 0 0; color: var(--muted); font-size: 12px; }}
    .math-status {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      margin-top: 5px;
      color: var(--muted);
      font-size: 11px;
    }}
    .math-status::before {{
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #d0d5dd;
    }}
    .math-status.ready {{ color: var(--green); }}
    .math-status.ready::before {{ background: var(--green); }}
    .math-status.failed {{ color: var(--amber); }}
    .math-status.failed::before {{ background: var(--amber); }}
    .progress-wrap {{ flex: 1; min-width: 180px; }}
    .progress-meta {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 5px;
      color: var(--muted);
      font-size: 12px;
    }}
    .progress-track {{
      height: 9px;
      overflow: hidden;
      border-radius: 999px;
      background: #e9edf3;
    }}
    .progress-bar {{
      width: 0;
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, #2357d8, #16a36a);
      transition: width .2s ease;
    }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }}
    .btn {{
      min-height: 36px;
      padding: 7px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--ink);
      background: #fff;
    }}
    .btn:hover {{ border-color: #aab4c5; background: #f8fafc; }}
    .btn.primary {{ color: #fff; border-color: var(--blue); background: var(--blue); }}
    .btn.danger {{ color: var(--red); }}
    .layout {{
      display: grid;
      grid-template-columns: 270px minmax(0, 1fr);
      gap: 18px;
      max-width: 1500px;
      margin: 0 auto;
      padding: 18px;
    }}
    .sidebar {{
      position: sticky;
      top: 84px;
      height: calc(100vh - 102px);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}
    .sidebar-tools {{ padding: 12px; border-bottom: 1px solid var(--line); }}
    .sidebar-tools input, .sidebar-tools select {{
      width: 100%;
      height: 36px;
      margin-bottom: 8px;
      padding: 6px 9px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }}
    .case-list {{ flex: 1; overflow: auto; padding: 7px; }}
    .case-item {{
      width: 100%;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 7px;
      align-items: center;
      margin-bottom: 5px;
      padding: 9px 10px;
      border: 1px solid transparent;
      border-radius: 8px;
      text-align: left;
      color: var(--ink);
      background: transparent;
    }}
    .case-item:hover {{ background: #f7f9fc; }}
    .case-item.active {{ border-color: #b9c9f7; background: var(--blue-soft); }}
    .case-item.done .dot {{ background: var(--green); }}
    .dot {{ width: 9px; height: 9px; border-radius: 50%; background: #cbd2de; }}
    .empty-list {{ padding: 30px 12px; color: var(--muted); text-align: center; }}
    main {{ min-width: 0; }}
    .case-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      padding: 14px 18px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}
    .case-header h2 {{ margin: 0; font-size: 19px; }}
    .save-state {{ color: var(--green); font-size: 12px; }}
    .card {{
      margin-bottom: 14px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}
    .card h3 {{
      margin: 0 0 11px;
      color: #344054;
      font-size: 13px;
      letter-spacing: .03em;
      text-transform: uppercase;
    }}
    .card-heading {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 11px;
    }}
    .card-heading h3 {{ margin: 0; }}
    .mini-btn {{
      padding: 5px 8px;
      border: 1px solid var(--line);
      border-radius: 7px;
      color: var(--muted);
      background: #fff;
      font-size: 11px;
    }}
    .content {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      line-height: 1.62;
      font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
    }}
    .question {{ font-size: 16px; }}
    .reference {{
      padding: 12px 14px;
      border-left: 4px solid var(--green);
      border-radius: 7px;
      background: var(--green-soft);
      font-weight: 650;
    }}
    .candidate {{
      max-height: 46vh;
      overflow: auto;
      padding: 15px;
      border: 1px solid #e2e7ef;
      border-radius: 8px;
      background: #fbfcfe;
      font-size: 15px;
    }}
    .math-warning {{
      margin: 0 0 10px;
      padding: 8px 10px;
      border-radius: 7px;
      color: var(--amber);
      background: var(--amber-soft);
      font-size: 12px;
    }}
    mjx-container[jax="SVG"][display="true"] {{
      max-width: 100%;
      overflow-x: auto;
      overflow-y: hidden;
      padding: 5px 0;
    }}
    .labels {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 9px;
    }}
    .label-choice {{
      position: relative;
      min-height: 51px;
      display: flex;
      align-items: center;
      gap: 9px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 9px;
      background: #fff;
    }}
    .label-choice:hover {{ border-color: #aeb8c9; }}
    .label-choice:has(input:checked) {{
      border-color: var(--blue);
      background: var(--blue-soft);
      box-shadow: 0 0 0 2px rgba(35,87,216,.08);
    }}
    .key {{
      min-width: 23px;
      padding: 2px 5px;
      border: 1px solid #cfd6e2;
      border-radius: 5px;
      color: var(--muted);
      background: #f7f8fb;
      font-size: 11px;
      text-align: center;
    }}
    .form-grid {{
      display: grid;
      grid-template-columns: 1fr 190px 190px;
      gap: 12px;
      margin-top: 14px;
    }}
    .field label {{
      display: block;
      margin-bottom: 6px;
      color: #475467;
      font-size: 13px;
      font-weight: 600;
    }}
    .field input, .field textarea, .field select {{
      width: 100%;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--ink);
      background: #fff;
    }}
    .field textarea {{ min-height: 85px; resize: vertical; line-height: 1.5; }}
    .reason-field {{ grid-column: 1 / -1; }}
    .nav {{
      position: sticky;
      bottom: 0;
      display: flex;
      justify-content: space-between;
      gap: 10px;
      padding: 12px 0 2px;
      background: linear-gradient(transparent, var(--bg) 22%);
    }}
    .nav .btn {{ min-width: 130px; }}
    .hint {{ margin-top: 10px; color: var(--muted); font-size: 12px; }}
    .hidden {{ display: none !important; }}
    .toast {{
      position: fixed;
      right: 20px;
      bottom: 20px;
      z-index: 50;
      max-width: 360px;
      padding: 11px 15px;
      border-radius: 9px;
      color: #fff;
      background: #172033;
      box-shadow: var(--shadow);
      opacity: 0;
      transform: translateY(10px);
      pointer-events: none;
      transition: .18s ease;
    }}
    .toast.show {{ opacity: 1; transform: translateY(0); }}
    @media (max-width: 900px) {{
      .topbar {{ align-items: flex-start; flex-wrap: wrap; }}
      .brand {{ min-width: 0; }}
      .progress-wrap {{ order: 3; flex-basis: 100%; }}
      .layout {{ grid-template-columns: 1fr; padding: 10px; }}
      .sidebar {{ position: static; height: auto; max-height: 310px; }}
      .form-grid {{ grid-template-columns: 1fr; }}
      .reason-field {{ grid-column: auto; }}
      .labels {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <h1>Judge Audit 盲审 — {html.escape(sheet_name)}</h1>
      <p>标注数据留在本地 · 自动保存 · 不显示实验条件</p>
      <span class="math-status" id="mathStatus">公式渲染组件加载中</span>
    </div>
    <div class="progress-wrap">
      <div class="progress-meta">
        <span id="progressText">0 / {len(rows)} 完成</span>
        <span id="progressPercent">0%</span>
      </div>
      <div class="progress-track"><div class="progress-bar" id="progressBar"></div></div>
    </div>
    <div class="actions">
      <button class="btn" id="backupButton">导出备份 JSON</button>
      <label class="btn" for="restoreInput">导入备份</label>
      <input class="hidden" id="restoreInput" type="file" accept=".json,application/json">
      <button class="btn primary" id="exportButton">导出 Completed CSV</button>
    </div>
  </header>

  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-tools">
        <input id="searchInput" type="search" placeholder="搜索 audit_id">
        <select id="filterSelect">
          <option value="all">全部样本</option>
          <option value="incomplete">仅未完成</option>
          <option value="complete">仅已完成</option>
        </select>
      </div>
      <div class="case-list" id="caseList"></div>
    </aside>

    <main>
      <section class="case-header">
        <h2 id="auditId">—</h2>
        <span class="save-state" id="saveState">已自动保存</span>
      </section>

      <section class="card">
        <h3>Question</h3>
        <div class="content question" id="question"></div>
      </section>

      <section class="card">
        <h3>Reference answer</h3>
        <div class="content reference" id="reference"></div>
      </section>

      <section class="card">
        <div class="card-heading">
          <h3>Candidate output</h3>
          <button type="button" class="mini-btn" id="rawToggle">显示原始文本</button>
        </div>
        <div class="math-warning hidden" id="mathWarning">
          此输出包含异常超长公式，为避免浏览器卡顿，Candidate 部分暂不渲染；可查看原始文本。
        </div>
        <div class="content candidate" id="candidate"></div>
      </section>

      <section class="card">
        <h3>Human annotation</h3>
        <div class="labels" id="labelChoices">
          <label class="label-choice">
            <input type="radio" name="humanLabel" value="Correct">
            <span class="key">1</span><span>Correct</span>
          </label>
          <label class="label-choice">
            <input type="radio" name="humanLabel" value="Incorrect">
            <span class="key">2</span><span>Incorrect</span>
          </label>
          <label class="label-choice">
            <input type="radio" name="humanLabel" value="Ambiguous / insufficient information">
            <span class="key">3</span><span>Ambiguous / insufficient information</span>
          </label>
          <label class="label-choice">
            <input type="radio" name="humanLabel" value="No valid final answer">
            <span class="key">4</span><span>No valid final answer</span>
          </label>
        </div>

        <div class="form-grid">
          <div class="field">
            <label for="normalizedAnswer">人工抽取的 normalized final answer</label>
            <input id="normalizedAnswer" type="text" autocomplete="off">
          </div>
          <div class="field">
            <label for="toolNeeded">需要 calculator / symbolic tool？</label>
            <select id="toolNeeded">
              <option value="">请选择</option>
              <option value="no">no</option>
              <option value="yes">yes</option>
            </select>
          </div>
          <div class="field">
            <label for="confidence">Annotator confidence</label>
            <select id="confidence">
              <option value="">请选择</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </div>
          <div class="field reason-field">
            <label for="reason">一句话判定理由</label>
            <textarea id="reason"></textarea>
          </div>
        </div>
        <div class="hint">
          完成标准：label、tool、confidence、reason 均已填写。快捷键 1–4 选择标签；Ctrl+Enter 保存并进入下一条。
        </div>
      </section>

      <div class="nav">
        <button class="btn" id="previousButton">← 上一条</button>
        <button class="btn danger" id="clearButton">清空当前标注</button>
        <button class="btn primary" id="nextButton">下一条 →</button>
      </div>
    </main>
  </div>
  <div class="toast" id="toast"></div>

  <script>
    "use strict";
    const EMBEDDED_ROWS = {data_json};
    const DISPLAY_ROWS = {display_json};
    const STORAGE_KEY = {json.dumps(storage_key)};
    const COMPLETED_CSV_NAME = {json.dumps(completed_csv)};
    const LABELS = [
      "Correct",
      "Incorrect",
      "Ambiguous / insufficient information",
      "No valid final answer"
    ];
    const editableFields = [
      "human_label",
      "human_final_answer_normalized",
      "human_reason",
      "human_tool_needed",
      "human_confidence"
    ];
    let rows = EMBEDDED_ROWS.map(row => ({{...row}}));
    let currentIndex = 0;
    let filteredIndices = rows.map((_, index) => index);
    let showRawCandidate = false;

    const el = id => document.getElementById(id);
    const auditId = el("auditId");
    const question = el("question");
    const reference = el("reference");
    const candidate = el("candidate");
    const normalizedAnswer = el("normalizedAnswer");
    const toolNeeded = el("toolNeeded");
    const confidence = el("confidence");
    const reason = el("reason");
    const caseList = el("caseList");
    const searchInput = el("searchInput");
    const filterSelect = el("filterSelect");

    function updateMathStatus() {{
      const status = el("mathStatus");
      if (window.MathJax?.typesetPromise) {{
        status.textContent = "公式渲染已启用";
        status.className = "math-status ready";
      }} else if (window.auditMathFailed) {{
        status.textContent = "公式组件未加载，将显示 LaTeX 原文";
        status.className = "math-status failed";
      }} else {{
        status.textContent = "公式渲染组件加载中";
        status.className = "math-status";
      }}
    }}
    window.auditUpdateMathStatus = updateMathStatus;

    function pathologicalMath(text) {{
      if (text.length > 18000) return true;
      const blocks = text.match(/\\$\\$[\\s\\S]*?\\$\\$|\\\\\\[[\\s\\S]*?\\\\\\]/g) || [];
      return blocks.some(block => block.length > 5000);
    }}

    function typesetVisible() {{
      updateMathStatus();
      if (!window.MathJax?.startup?.promise || !window.MathJax?.typesetPromise) return;
      const current = rows[currentIndex];
      const display = DISPLAY_ROWS[current.audit_id];
      const elements = [question, reference];
      const skipCandidate = showRawCandidate || pathologicalMath(display.candidate_output);
      el("mathWarning").classList.toggle("hidden", !skipCandidate || showRawCandidate);
      if (!skipCandidate) elements.push(candidate);
      window.MathJax.startup.promise
        .then(() => {{
          window.MathJax.typesetClear(elements);
          return window.MathJax.typesetPromise(elements);
        }})
        .catch(() => {{
          el("mathStatus").textContent = "部分公式无法渲染，已保留原文";
          el("mathStatus").className = "math-status failed";
        }});
    }}
    window.auditTypesetAll = typesetVisible;

    function escapeCsv(value) {{
      const text = String(value ?? "");
      return '"' + text.replaceAll('"', '""') + '"';
    }}

    function isComplete(row) {{
      return Boolean(
        LABELS.includes(row.human_label) &&
        row.human_reason.trim() &&
        ["yes", "no"].includes(row.human_tool_needed) &&
        ["high", "medium", "low"].includes(row.human_confidence)
      );
    }}

    function persist() {{
      const annotations = {{}};
      for (const row of rows) {{
        annotations[row.audit_id] = Object.fromEntries(
          editableFields.map(field => [field, row[field] ?? ""])
        );
      }}
      try {{
        localStorage.setItem(STORAGE_KEY, JSON.stringify({{
          version: 1,
          saved_at: new Date().toISOString(),
          annotations
        }}));
        el("saveState").textContent = "已自动保存 " + new Date().toLocaleTimeString();
      }} catch (error) {{
        el("saveState").textContent = "浏览器存储不可用，请导出备份";
      }}
    }}

    function restoreLocal() {{
      try {{
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw);
        mergeAnnotations(saved.annotations || {{}});
      }} catch (error) {{
        showToast("本地进度读取失败，将使用空白表。");
      }}
    }}

    function mergeAnnotations(annotations) {{
      for (const row of rows) {{
        const saved = annotations[row.audit_id];
        if (!saved) continue;
        for (const field of editableFields) {{
          if (typeof saved[field] === "string") row[field] = saved[field];
        }}
      }}
    }}

    function commitCurrent() {{
      const row = rows[currentIndex];
      const selected = document.querySelector('input[name="humanLabel"]:checked');
      row.human_label = selected ? selected.value : "";
      row.human_final_answer_normalized = normalizedAnswer.value.trim();
      row.human_reason = reason.value.trim();
      row.human_tool_needed = toolNeeded.value;
      row.human_confidence = confidence.value;
      persist();
      updateProgress();
    }}

    function renderCurrent() {{
      const row = rows[currentIndex];
      const display = DISPLAY_ROWS[row.audit_id];
      auditId.textContent = row.audit_id;
      question.textContent = display.question;
      reference.textContent = display.ground_truth_answer;
      candidate.textContent = showRawCandidate
        ? row.candidate_output
        : display.candidate_output;
      el("rawToggle").textContent = showRawCandidate
        ? "显示清理并渲染后的文本"
        : "显示原始文本";
      normalizedAnswer.value = row.human_final_answer_normalized || "";
      reason.value = row.human_reason || "";
      toolNeeded.value = row.human_tool_needed || "";
      confidence.value = row.human_confidence || "";
      document.querySelectorAll('input[name="humanLabel"]').forEach(input => {{
        input.checked = input.value === row.human_label;
      }});
      renderList();
      document.querySelector(".candidate").scrollTop = 0;
      typesetVisible();
    }}

    function updateProgress() {{
      const complete = rows.filter(isComplete).length;
      const percent = Math.round(100 * complete / rows.length);
      el("progressText").textContent = `${{complete}} / ${{rows.length}} 完成`;
      el("progressPercent").textContent = `${{percent}}%`;
      el("progressBar").style.width = `${{percent}}%`;
    }}

    function applyFilter() {{
      const query = searchInput.value.trim().toLowerCase();
      const mode = filterSelect.value;
      filteredIndices = rows
        .map((row, index) => ({{row, index}}))
        .filter(({{
          row
        }}) => {{
          const matchesQuery = !query || row.audit_id.toLowerCase().includes(query);
          const complete = isComplete(row);
          const matchesMode =
            mode === "all" ||
            (mode === "complete" && complete) ||
            (mode === "incomplete" && !complete);
          return matchesQuery && matchesMode;
        }})
        .map(item => item.index);
      renderList();
    }}

    function renderList() {{
      caseList.replaceChildren();
      if (!filteredIndices.length) {{
        const empty = document.createElement("div");
        empty.className = "empty-list";
        empty.textContent = "没有符合筛选条件的样本";
        caseList.appendChild(empty);
        return;
      }}
      const fragment = document.createDocumentFragment();
      for (const index of filteredIndices) {{
        const row = rows[index];
        const button = document.createElement("button");
        button.type = "button";
        button.className =
          "case-item" +
          (index === currentIndex ? " active" : "") +
          (isComplete(row) ? " done" : "");
        const name = document.createElement("span");
        name.textContent = row.audit_id;
        const dot = document.createElement("span");
        dot.className = "dot";
        button.append(name, dot);
        button.addEventListener("click", () => {{
          commitCurrent();
          currentIndex = index;
          renderCurrent();
        }});
        fragment.appendChild(button);
      }}
      caseList.appendChild(fragment);
      const active = caseList.querySelector(".active");
      if (active) active.scrollIntoView({{block: "nearest"}});
    }}

    function move(direction) {{
      commitCurrent();
      const list = filteredIndices.length ? filteredIndices : rows.map((_, i) => i);
      let position = list.indexOf(currentIndex);
      if (position < 0) position = 0;
      position = Math.max(0, Math.min(list.length - 1, position + direction));
      currentIndex = list[position];
      renderCurrent();
      window.scrollTo({{top: 0, behavior: "smooth"}});
    }}

    function showToast(message) {{
      const toast = el("toast");
      toast.textContent = message;
      toast.classList.add("show");
      clearTimeout(showToast.timer);
      showToast.timer = setTimeout(() => toast.classList.remove("show"), 2400);
    }}

    function download(name, content, mime) {{
      const blob = new Blob([content], {{type: mime}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }}

    function exportCsv() {{
      commitCurrent();
      const incomplete = rows.filter(row => !isComplete(row));
      if (incomplete.length) {{
        const proceed = confirm(
          `还有 ${{incomplete.length}} 条未完成。是否仍然导出当前 CSV？`
        );
        if (!proceed) return;
      }}
      const fields = {safe_json_for_script(EXPECTED_FIELDS)};
      const lines = [fields.map(escapeCsv).join(",")];
      for (const row of rows) {{
        lines.push(fields.map(field => escapeCsv(row[field] ?? "")).join(","));
      }}
      download(
        COMPLETED_CSV_NAME,
        "\\ufeff" + lines.join("\\r\\n"),
        "text/csv;charset=utf-8"
      );
      showToast("Completed CSV 已导出。");
    }}

    function exportBackup() {{
      commitCurrent();
      const annotations = Object.fromEntries(
        rows.map(row => [
          row.audit_id,
          Object.fromEntries(editableFields.map(field => [field, row[field] ?? ""]))
        ])
      );
      download(
        STORAGE_KEY + "-backup.json",
        JSON.stringify({{
          version: 1,
          sheet: {json.dumps(sheet_name)},
          saved_at: new Date().toISOString(),
          annotations
        }}, null, 2),
        "application/json;charset=utf-8"
      );
      showToast("备份 JSON 已导出。");
    }}

    function importBackup(file) {{
      const reader = new FileReader();
      reader.onload = () => {{
        try {{
          const payload = JSON.parse(reader.result);
          if (!payload.annotations || typeof payload.annotations !== "object") {{
            throw new Error("missing annotations");
          }}
          mergeAnnotations(payload.annotations);
          persist();
          applyFilter();
          renderCurrent();
          updateProgress();
          showToast("备份已恢复。");
        }} catch (error) {{
          alert("无法导入该备份文件。");
        }}
      }};
      reader.readAsText(file, "utf-8");
    }}

    document.querySelectorAll('input[name="humanLabel"]').forEach(input => {{
      input.addEventListener("change", commitCurrent);
    }});
    [normalizedAnswer, reason].forEach(input => {{
      input.addEventListener("input", () => {{
        clearTimeout(input.saveTimer);
        input.saveTimer = setTimeout(commitCurrent, 350);
      }});
    }});
    [toolNeeded, confidence].forEach(input => input.addEventListener("change", commitCurrent));
    searchInput.addEventListener("input", applyFilter);
    filterSelect.addEventListener("change", applyFilter);
    el("previousButton").addEventListener("click", () => move(-1));
    el("nextButton").addEventListener("click", () => move(1));
    el("exportButton").addEventListener("click", exportCsv);
    el("backupButton").addEventListener("click", exportBackup);
    el("restoreInput").addEventListener("change", event => {{
      const file = event.target.files[0];
      if (file) importBackup(file);
      event.target.value = "";
    }});
    el("clearButton").addEventListener("click", () => {{
      if (!confirm(`确定清空 ${{rows[currentIndex].audit_id}} 的当前人工标注吗？`)) return;
      for (const field of editableFields) rows[currentIndex][field] = "";
      persist();
      renderCurrent();
      updateProgress();
    }});
    el("rawToggle").addEventListener("click", () => {{
      showRawCandidate = !showRawCandidate;
      renderCurrent();
    }});
    document.addEventListener("keydown", event => {{
      const tag = document.activeElement?.tagName;
      const editingText = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      if (event.ctrlKey && event.key === "Enter") {{
        event.preventDefault();
        move(1);
        return;
      }}
      if (!editingText && ["1", "2", "3", "4"].includes(event.key)) {{
        const value = LABELS[Number(event.key) - 1];
        const input = [...document.querySelectorAll('input[name="humanLabel"]')]
          .find(item => item.value === value);
        input.checked = true;
        commitCurrent();
        renderList();
      }}
    }});
    window.addEventListener("beforeunload", commitCurrent);

    restoreLocal();
    updateProgress();
    applyFilter();
    renderCurrent();
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    jobs = [
        (args.input_a, args.output_a, "Annotator A"),
        (args.input_b, args.output_b, "Annotator B"),
    ]
    if args.sheet != "both":
        selected_index = 0 if args.sheet == "a" else 1
        jobs = [jobs[selected_index]]
    summary: list[dict[str, object]] = []
    for input_path, output_path, sheet_name in jobs:
        rows = read_blind_csv(input_path)
        rendered = build_html(rows, sheet_name, output_path)
        Path(output_path).write_text(rendered, encoding="utf-8", newline="\n")
        summary.append(
            {
                "input": input_path,
                "output": output_path,
                "rows": len(rows),
                "bytes": Path(output_path).stat().st_size,
            }
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
