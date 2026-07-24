#!/usr/bin/env python3
"""Build a standalone side-by-side adjudication interface from two audit CSVs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from build_judge_audit_html import (
    EXPECTED_FIELDS,
    clean_display_text,
    read_blind_csv,
    safe_json_for_script,
    wrap_bare_math,
    wrap_bare_tex_lines,
)


HUMAN_FIELDS = [
    "human_label",
    "human_final_answer_normalized",
    "human_reason",
    "human_tool_needed",
    "human_confidence",
]
CONTENT_FIELDS = [
    "annotation_instruction",
    "question",
    "ground_truth_answer",
    "candidate_output",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-a",
        default="data/annotations/judge_audit/judge_audit_blinded_sheet_A_completed（A）.csv",
    )
    parser.add_argument(
        "--input-b",
        default="data/annotations/judge_audit/judge_audit_blinded_sheet_A_completed（B）.csv",
    )
    parser.add_argument(
        "--output",
        default="build/judge_audit_adjudication.html",
    )
    return parser.parse_args()


def merge_rows(
    rows_a: list[dict[str, str]],
    rows_b: list[dict[str, str]],
) -> list[dict[str, object]]:
    by_id_b = {row["audit_id"]: row for row in rows_b}
    ids_a = [row["audit_id"] for row in rows_a]
    ids_b = [row["audit_id"] for row in rows_b]
    if set(ids_a) != set(ids_b):
        only_a = sorted(set(ids_a) - set(ids_b))
        only_b = sorted(set(ids_b) - set(ids_a))
        raise ValueError(
            f"Audit IDs do not match. Only A: {only_a}; only B: {only_b}"
        )

    merged: list[dict[str, object]] = []
    for row_a in rows_a:
        audit_id = row_a["audit_id"]
        row_b = by_id_b[audit_id]
        mismatches = [
            field
            for field in CONTENT_FIELDS
            if row_a[field] != row_b[field]
        ]
        if mismatches:
            raise ValueError(
                f"{audit_id} differs between files in fields: {mismatches}"
            )
        merged.append(
            {
                "audit_id": audit_id,
                "annotation_instruction": row_a["annotation_instruction"],
                "question": row_a["question"],
                "ground_truth_answer": row_a["ground_truth_answer"],
                "candidate_output": row_a["candidate_output"],
                "display": {
                    "question": wrap_bare_tex_lines(
                        clean_display_text(row_a["question"])
                    ),
                    "ground_truth_answer": wrap_bare_math(
                        clean_display_text(row_a["ground_truth_answer"])
                    ),
                    "candidate_output": wrap_bare_tex_lines(
                        clean_display_text(
                            row_a["candidate_output"],
                            unwrap_continuation=True,
                        )
                    ),
                },
                "a": {field: row_a[field] for field in HUMAN_FIELDS},
                "b": {field: row_b[field] for field in HUMAN_FIELDS},
                "label_agreement": (
                    row_a["human_label"].strip()
                    == row_b["human_label"].strip()
                ),
            }
        )
    return merged


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Judge Audit Adjudication</title>
  <script>
    window.MathJax = {
      loader: {load: ["[tex]/ams"]},
      tex: {
        packages: {"[+]": ["ams"]},
        inlineMath: [["$", "$"], ["\\(", "\\)"]],
        displayMath: [["$$", "$$"], ["\\[", "\\]"]],
        processEscapes: true
      },
      svg: {fontCache: "local"},
      startup: {typeset: false}
    };
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@4/tex-svg.js"
    onload="window.mathReady=true;if(window.typesetCurrent)window.typesetCurrent();"
    onerror="document.getElementById('mathStatus').textContent='MathJax 未加载；原始 TeX 仍可阅读';"></script>
  <style>
    :root {
      --bg:#f3f5f8; --panel:#fff; --ink:#172033; --muted:#667085;
      --line:#d8dee9; --blue:#2254d1; --blue-soft:#edf3ff;
      --red:#b42318; --red-soft:#fff0ee; --green:#067647;
      --green-soft:#ecfdf3; --amber:#9a5b00; --amber-soft:#fff7e6;
      --shadow:0 8px 24px rgba(24,34,51,.08);
    }
    * { box-sizing:border-box; }
    body {
      margin:0; color:var(--ink); background:var(--bg);
      font:14px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",
        "Microsoft YaHei",sans-serif;
    }
    button,input,textarea,select { font:inherit; }
    button { cursor:pointer; }
    .topbar {
      position:sticky; top:0; z-index:20; display:flex; gap:18px;
      align-items:center; padding:12px 18px; background:#101828; color:white;
      box-shadow:0 2px 10px rgba(0,0,0,.2);
    }
    .topbar h1 { margin:0; font-size:18px; white-space:nowrap; }
    .summary { display:flex; flex-wrap:wrap; gap:8px; }
    .summary span {
      padding:3px 9px; border-radius:999px; background:rgba(255,255,255,.12);
      font-size:12px;
    }
    .summary .warn { background:#7a2e0e; }
    .summary .ok { background:#075e45; }
    #mathStatus { margin-left:auto; font-size:12px; color:#cbd5e1; }
    .app { display:grid; grid-template-columns:300px minmax(0,1fr); min-height:calc(100vh - 52px); }
    aside {
      position:sticky; top:52px; align-self:start; height:calc(100vh - 52px);
      border-right:1px solid var(--line); background:var(--panel);
      display:flex; flex-direction:column;
    }
    .tools { padding:12px; border-bottom:1px solid var(--line); }
    .tools input,.tools select {
      width:100%; padding:8px 9px; margin-bottom:8px; border:1px solid var(--line);
      border-radius:7px; background:white;
    }
    .tool-row { display:grid; grid-template-columns:1fr 1fr; gap:7px; }
    .tool-row button,.export-row button {
      border:1px solid var(--line); border-radius:7px; background:white; padding:7px;
    }
    .tool-row button:hover,.export-row button:hover { background:var(--blue-soft); }
    .progress-line { font-size:12px; color:var(--muted); margin-top:8px; }
    #caseList { overflow:auto; padding:7px; }
    .case {
      width:100%; display:grid; grid-template-columns:1fr auto; gap:7px;
      text-align:left; padding:8px 9px; margin-bottom:5px; border:1px solid var(--line);
      border-radius:7px; background:white; color:var(--ink);
    }
    .case:hover { border-color:#9bb3ee; }
    .case.active { outline:2px solid var(--blue); border-color:transparent; }
    .case.disagreement { border-left:5px solid var(--red); }
    .case.resolved { border-left-color:var(--green); background:#f7fff9; }
    .case .labels { color:var(--muted); font-size:11px; overflow:hidden; text-overflow:ellipsis; }
    .case .mark { font-weight:700; }
    main { min-width:0; padding:18px; }
    .nav {
      display:flex; align-items:center; gap:8px; margin-bottom:12px;
    }
    .nav button {
      border:1px solid var(--line); border-radius:7px; background:white; padding:7px 12px;
    }
    .nav .spacer { flex:1; }
    .badge {
      display:inline-flex; align-items:center; border-radius:999px;
      padding:3px 9px; font-size:12px; font-weight:650;
    }
    .badge.agree { color:var(--green); background:var(--green-soft); }
    .badge.disagree { color:var(--red); background:var(--red-soft); }
    .badge.saved { color:var(--blue); background:var(--blue-soft); }
    .badge[hidden] { display:none; }
    .panel {
      background:var(--panel); border:1px solid var(--line); border-radius:10px;
      box-shadow:var(--shadow); padding:16px; margin-bottom:14px;
    }
    .panel h2,.panel h3 { margin:0 0 9px; line-height:1.25; }
    .panel h2 { font-size:17px; }
    .panel h3 { font-size:14px; color:#344054; }
    .content {
      white-space:pre-wrap; overflow-wrap:anywhere; max-height:340px; overflow:auto;
      padding:12px; border-radius:8px; background:#f8fafc; border:1px solid #e8ecf2;
    }
    .candidate .content { max-height:440px; }
    .raw-toggle { float:right; border:0; color:var(--blue); background:transparent; }
    .comparison { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
    .annotator { border-top:4px solid #6d8ce5; }
    .annotator.b { border-top-color:#a477d6; }
    .label-big {
      display:inline-block; padding:6px 10px; margin-bottom:10px; border-radius:7px;
      background:#eef2f7; font-weight:750;
    }
    dl { display:grid; grid-template-columns:120px 1fr; gap:7px 10px; margin:0; }
    dt { color:var(--muted); }
    dd { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; }
    .decision { border:2px solid #a9bce9; }
    .decision-head { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
    .decision-head h2 { margin-right:auto; }
    .adopt {
      border:1px solid var(--line); border-radius:7px; background:white; padding:7px 10px;
    }
    .adopt:hover { background:var(--blue-soft); border-color:#9bb3ee; }
    .labels-grid {
      display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; margin:14px 0;
    }
    .choice {
      display:flex; gap:7px; align-items:flex-start; padding:10px;
      border:1px solid var(--line); border-radius:8px; background:#fafbfc;
    }
    .choice:has(input:checked) { border-color:var(--blue); background:var(--blue-soft); }
    .form-grid { display:grid; grid-template-columns:1fr 180px 180px; gap:10px; }
    label.field { display:block; color:var(--muted); font-size:12px; }
    .field input,.field textarea,.field select {
      display:block; width:100%; margin-top:4px; padding:8px 9px; color:var(--ink);
      border:1px solid var(--line); border-radius:7px; background:white;
    }
    .field textarea { resize:vertical; min-height:78px; }
    .reason-field { grid-column:1/-1; }
    .save-state { margin-top:8px; font-size:12px; color:var(--muted); }
    .bottom-actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
    .bottom-actions button {
      border:0; border-radius:7px; background:var(--blue); color:white; padding:8px 12px;
    }
    .bottom-actions .secondary { background:#475467; }
    .bottom-actions .danger { background:#9f2d24; }
    .empty { padding:24px; color:var(--muted); text-align:center; }
    mjx-container { overflow-x:auto; overflow-y:hidden; max-width:100%; }
    @media (max-width:980px) {
      .app { grid-template-columns:1fr; }
      aside { position:relative; top:auto; height:320px; border-right:0; border-bottom:1px solid var(--line); }
      .comparison,.labels-grid { grid-template-columns:1fr; }
      .form-grid { grid-template-columns:1fr; }
      .reason-field { grid-column:auto; }
      #mathStatus { display:none; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <h1>Judge Audit Adjudication</h1>
    <div class="summary">
      <span id="totalCount"></span><span class="ok" id="agreeCount"></span>
      <span class="warn" id="disagreeCount"></span><span id="resolvedCount"></span>
    </div>
    <span id="mathStatus">MathJax 加载中…</span>
  </header>
  <div class="app">
    <aside>
      <div class="tools">
        <input id="search" type="search" placeholder="搜索 audit_id / 标签 / 理由">
        <select id="filter">
          <option value="disagreements">仅标签分歧（推荐）</option>
          <option value="unresolved">仅未裁决分歧</option>
          <option value="resolved">仅已裁决分歧</option>
          <option value="agreements">仅一致项</option>
          <option value="all">全部 200 条</option>
        </select>
        <div class="tool-row">
          <button id="prevSide" type="button">← 上一条</button>
          <button id="nextSide" type="button">下一条 →</button>
        </div>
        <div class="progress-line" id="progressLine"></div>
      </div>
      <div id="caseList"></div>
    </aside>
    <main>
      <div class="nav">
        <button id="prevMain" type="button">← 上一条</button>
        <button id="nextMain" type="button">下一条 →</button>
        <span class="spacer"></span>
        <strong id="auditId"></strong>
        <span class="badge" id="agreementBadge"></span>
        <span class="badge saved" id="overrideBadge" hidden>已有人工裁决</span>
      </div>

      <section class="panel">
        <h3>Question</h3>
        <div class="content" id="question"></div>
        <h3 style="margin-top:14px">Reference answer</h3>
        <div class="content" id="reference"></div>
      </section>

      <section class="panel candidate">
        <button class="raw-toggle" id="rawToggle" type="button">显示原始输出</button>
        <h3>Candidate output</h3>
        <div class="content" id="candidate"></div>
      </section>

      <div class="comparison">
        <section class="panel annotator">
          <h2>Annotator A</h2>
          <div class="label-big" id="labelA"></div>
          <dl>
            <dt>Normalized answer</dt><dd id="answerA"></dd>
            <dt>Reason</dt><dd id="reasonA"></dd>
            <dt>Tool needed</dt><dd id="toolA"></dd>
            <dt>Confidence</dt><dd id="confidenceA"></dd>
          </dl>
        </section>
        <section class="panel annotator b">
          <h2>Annotator B</h2>
          <div class="label-big" id="labelB"></div>
          <dl>
            <dt>Normalized answer</dt><dd id="answerB"></dd>
            <dt>Reason</dt><dd id="reasonB"></dd>
            <dt>Tool needed</dt><dd id="toolB"></dd>
            <dt>Confidence</dt><dd id="confidenceB"></dd>
          </dl>
        </section>
      </div>

      <section class="panel decision">
        <div class="decision-head">
          <h2>Adjudication decision</h2>
          <button class="adopt" id="adoptA" type="button">采用 A 整套标注</button>
          <button class="adopt" id="adoptB" type="button">采用 B 整套标注</button>
          <button class="adopt" id="clearDecision" type="button">清除此条裁决</button>
        </div>
        <div class="labels-grid">
          <label class="choice"><input type="radio" name="decisionLabel" value="Correct">Correct</label>
          <label class="choice"><input type="radio" name="decisionLabel" value="Incorrect">Incorrect</label>
          <label class="choice"><input type="radio" name="decisionLabel" value="Ambiguous / insufficient information">Ambiguous / insufficient information</label>
          <label class="choice"><input type="radio" name="decisionLabel" value="No valid final answer">No valid final answer</label>
        </div>
        <div class="form-grid">
          <label class="field">Final answer normalized
            <input id="decisionAnswer" type="text" autocomplete="off">
          </label>
          <label class="field">Tool needed
            <select id="decisionTool">
              <option value=""></option><option value="no">no</option><option value="yes">yes</option>
            </select>
          </label>
          <label class="field">Confidence
            <select id="decisionConfidence">
              <option value=""></option><option value="high">high</option>
              <option value="medium">medium</option><option value="low">low</option>
            </select>
          </label>
          <label class="field reason-field">Adjudication reason
            <textarea id="decisionReason" placeholder="记录最终判断依据；采用 A/B 后仍可修改"></textarea>
          </label>
        </div>
        <div class="save-state" id="saveState"></div>
        <div class="bottom-actions">
          <button id="exportFinal" type="button">导出 adjudicated CSV</button>
          <button id="exportTrail" class="secondary" type="button">导出 audit trail CSV</button>
          <button id="backupJson" class="secondary" type="button">备份进度 JSON</button>
          <button id="restoreJson" class="secondary" type="button">恢复进度 JSON</button>
          <input id="restoreInput" type="file" accept=".json,application/json" hidden>
          <button id="clearAll" class="danger" type="button">清空全部人工裁决</button>
        </div>
      </section>
    </main>
  </div>

  <script>
    const ROWS = __DATA__;
    const STORAGE_KEY = "judge-audit-adjudication-v1";
    const FINAL_CSV_NAME = __FINAL_NAME__;
    const TRAIL_CSV_NAME = __TRAIL_NAME__;
    const HUMAN_FIELDS = [
      "human_label","human_final_answer_normalized","human_reason",
      "human_tool_needed","human_confidence"
    ];
    const labelInputs = [...document.querySelectorAll('input[name="decisionLabel"]')];
    const el = id => document.getElementById(id);
    let decisions = {};
    let visible = [];
    let currentId = null;
    let showRaw = false;
    let saveTimer = null;

    function loadLocal() {
      try {
        const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
        if (stored && typeof stored === "object") decisions = stored;
      } catch (_) { decisions = {}; }
    }
    function persist() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(decisions));
      el("saveState").textContent = "已自动保存到此浏览器 · " + new Date().toLocaleTimeString();
      updateSummary();
      renderList();
    }
    function rowById(id) { return ROWS.find(row => row.audit_id === id); }
    function isResolved(row) {
      return row.label_agreement || Boolean(decisions[row.audit_id]?.human_label);
    }
    function effectiveDecision(row) {
      if (decisions[row.audit_id]) return {...decisions[row.audit_id]};
      if (row.label_agreement) return {...row.a, decision_source:"agreement"};
      return {
        human_label:"", human_final_answer_normalized:"", human_reason:"",
        human_tool_needed:"", human_confidence:"", decision_source:""
      };
    }
    function countStats() {
      const disagreements = ROWS.filter(r => !r.label_agreement);
      return {
        total: ROWS.length,
        agree: ROWS.length - disagreements.length,
        disagree: disagreements.length,
        resolved: disagreements.filter(r => decisions[r.audit_id]?.human_label).length
      };
    }
    function updateSummary() {
      const s = countStats();
      el("totalCount").textContent = `共 ${s.total}`;
      el("agreeCount").textContent = `一致 ${s.agree}`;
      el("disagreeCount").textContent = `分歧 ${s.disagree}`;
      el("resolvedCount").textContent = `已裁决 ${s.resolved}/${s.disagree}`;
      el("progressLine").textContent = `标签分歧裁决进度：${s.resolved} / ${s.disagree}`;
    }
    function matches(row) {
      const q = el("search").value.trim().toLowerCase();
      if (!q) return true;
      return [
        row.audit_id,row.a.human_label,row.b.human_label,
        row.a.human_reason,row.b.human_reason,row.question
      ].join("\n").toLowerCase().includes(q);
    }
    function applyFilter(keepCurrent=true) {
      const mode = el("filter").value;
      visible = ROWS.filter(row => {
        if (!matches(row)) return false;
        if (mode === "disagreements") return !row.label_agreement;
        if (mode === "unresolved") return !row.label_agreement && !decisions[row.audit_id]?.human_label;
        if (mode === "resolved") return !row.label_agreement && Boolean(decisions[row.audit_id]?.human_label);
        if (mode === "agreements") return row.label_agreement;
        return true;
      });
      if (!keepCurrent || !visible.some(r => r.audit_id === currentId)) {
        currentId = visible[0]?.audit_id || null;
      }
      renderList();
      renderCurrent();
    }
    function renderList() {
      const list = el("caseList");
      list.replaceChildren();
      if (!visible.length) {
        const empty = document.createElement("div");
        empty.className = "empty"; empty.textContent = "当前筛选下没有条目";
        list.append(empty); return;
      }
      visible.forEach(row => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "case" +
          (!row.label_agreement ? " disagreement" : "") +
          (!row.label_agreement && decisions[row.audit_id]?.human_label ? " resolved" : "") +
          (row.audit_id === currentId ? " active" : "");
        const left = document.createElement("span");
        const id = document.createElement("strong");
        id.textContent = row.audit_id;
        const labels = document.createElement("div");
        labels.className = "labels";
        labels.textContent = row.label_agreement
          ? row.a.human_label
          : `A: ${row.a.human_label} · B: ${row.b.human_label}`;
        left.append(id, labels);
        const mark = document.createElement("span");
        mark.className = "mark";
        mark.textContent = row.label_agreement ? "✓" :
          (decisions[row.audit_id]?.human_label ? "✓" : "!");
        button.append(left, mark);
        button.onclick = () => { commitCurrent(); currentId=row.audit_id; renderList(); renderCurrent(); };
        list.append(button);
      });
      list.querySelector(".case.active")?.scrollIntoView({block:"nearest"});
    }
    function setText(id, value) { el(id).textContent = value || "—"; }
    function renderAnnotator(prefix, data) {
      setText("label"+prefix, data.human_label);
      setText("answer"+prefix, data.human_final_answer_normalized);
      setText("reason"+prefix, data.human_reason);
      setText("tool"+prefix, data.human_tool_needed);
      setText("confidence"+prefix, data.human_confidence);
    }
    async function typesetCurrent() {
      if (!window.MathJax?.typesetPromise) return;
      const targets = [el("question"),el("reference"),el("candidate")];
      try {
        MathJax.typesetClear(targets);
        await MathJax.typesetPromise(targets);
        el("mathStatus").textContent = "MathJax 已加载";
      } catch (_) {
        el("mathStatus").textContent = "部分公式渲染失败；可查看原始 TeX";
      }
    }
    function renderCurrent() {
      const row = rowById(currentId);
      if (!row) {
        el("auditId").textContent = "无条目";
        return;
      }
      el("auditId").textContent = row.audit_id;
      const badge = el("agreementBadge");
      badge.textContent = row.label_agreement ? "标签一致" : "标签分歧";
      badge.className = "badge " + (row.label_agreement ? "agree" : "disagree");
      el("overrideBadge").hidden = !decisions[row.audit_id];
      el("question").textContent = row.display.question;
      el("reference").textContent = row.display.ground_truth_answer;
      el("candidate").textContent = showRaw ? row.candidate_output : row.display.candidate_output;
      el("rawToggle").textContent = showRaw ? "显示清理版输出" : "显示原始输出";
      renderAnnotator("A", row.a); renderAnnotator("B", row.b);

      const decision = effectiveDecision(row);
      labelInputs.forEach(input => input.checked = input.value === decision.human_label);
      el("decisionAnswer").value = decision.human_final_answer_normalized || "";
      el("decisionReason").value = decision.human_reason || "";
      el("decisionTool").value = decision.human_tool_needed || "";
      el("decisionConfidence").value = decision.human_confidence || "";
      el("saveState").textContent = decisions[row.audit_id]
        ? `人工裁决来源：${decision.decision_source || "manual"}`
        : (row.label_agreement
          ? "两位标注者标签一致；导出时默认采用 A 的完整记录，可在此覆盖"
          : "尚未裁决；点击“采用 A/B”或手动填写");
      typesetCurrent();
    }
    function readForm(source="manual") {
      return {
        human_label: labelInputs.find(input => input.checked)?.value || "",
        human_final_answer_normalized: el("decisionAnswer").value.trim(),
        human_reason: el("decisionReason").value.trim(),
        human_tool_needed: el("decisionTool").value,
        human_confidence: el("decisionConfidence").value,
        decision_source: source
      };
    }
    function commitCurrent() {
      const row = rowById(currentId);
      if (!row) return;
      const form = readForm(decisions[row.audit_id]?.decision_source || "manual");
      const inherited = !decisions[row.audit_id] && row.label_agreement;
      if (inherited) return;
      const hasValue = HUMAN_FIELDS.some(field => Boolean(form[field]));
      if (hasValue) decisions[row.audit_id] = form;
      else delete decisions[row.audit_id];
      clearTimeout(saveTimer);
      saveTimer = setTimeout(persist, 100);
    }
    function adopt(which) {
      const row = rowById(currentId); if (!row) return;
      decisions[row.audit_id] = {...row[which.toLowerCase()], decision_source:which};
      persist(); renderCurrent();
    }
    function clearDecision() {
      const row = rowById(currentId); if (!row) return;
      delete decisions[row.audit_id]; persist(); renderCurrent();
    }
    function move(delta) {
      commitCurrent();
      if (!visible.length) return;
      const index = Math.max(0, visible.findIndex(row => row.audit_id === currentId));
      const next = Math.min(visible.length-1, Math.max(0,index+delta));
      currentId = visible[next].audit_id;
      renderList(); renderCurrent();
    }
    function csvCell(value) {
      const text = String(value ?? "");
      return /[",\r\n]/.test(text) ? `"${text.replaceAll('"','""')}"` : text;
    }
    function download(name, text, type) {
      const blob = new Blob([text], {type});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href=url; link.download=name; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    function exportFinal() {
      commitCurrent();
      const header = [
        "audit_id","annotation_instruction","question","ground_truth_answer",
        "candidate_output",...HUMAN_FIELDS
      ];
      const lines = [header.map(csvCell).join(",")];
      ROWS.forEach(row => {
        const d = effectiveDecision(row);
        lines.push([
          row.audit_id,row.annotation_instruction,row.question,
          row.ground_truth_answer,row.candidate_output,
          ...HUMAN_FIELDS.map(field => d[field] || "")
        ].map(csvCell).join(","));
      });
      download(FINAL_CSV_NAME, "\ufeff"+lines.join("\r\n"), "text/csv;charset=utf-8");
    }
    function exportTrail() {
      commitCurrent();
      const prefixes = ["a","b","adjudicated"];
      const header = [
        "audit_id","label_agreement","decision_source",
        ...prefixes.flatMap(prefix => HUMAN_FIELDS.map(field => `${prefix}_${field}`))
      ];
      const lines = [header.map(csvCell).join(",")];
      ROWS.forEach(row => {
        const d = effectiveDecision(row);
        lines.push([
          row.audit_id,row.label_agreement ? "yes" : "no",d.decision_source || "",
          ...HUMAN_FIELDS.map(f => row.a[f] || ""),
          ...HUMAN_FIELDS.map(f => row.b[f] || ""),
          ...HUMAN_FIELDS.map(f => d[f] || "")
        ].map(csvCell).join(","));
      });
      download(TRAIL_CSV_NAME, "\ufeff"+lines.join("\r\n"), "text/csv;charset=utf-8");
    }
    function backup() {
      commitCurrent();
      download(
        "judge_audit_adjudication_progress.json",
        JSON.stringify({version:1,created_at:new Date().toISOString(),decisions},null,2),
        "application/json;charset=utf-8"
      );
    }
    function restore(file) {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const parsed = JSON.parse(reader.result);
          const incoming = parsed.decisions || parsed;
          if (!incoming || typeof incoming !== "object") throw new Error("invalid");
          decisions = incoming; persist(); applyFilter(false);
        } catch (_) { alert("无法读取该进度 JSON。"); }
      };
      reader.readAsText(file,"utf-8");
    }

    el("filter").onchange = () => { commitCurrent(); applyFilter(false); };
    el("search").oninput = () => applyFilter(false);
    ["prevSide","prevMain"].forEach(id => el(id).onclick=()=>move(-1));
    ["nextSide","nextMain"].forEach(id => el(id).onclick=()=>move(1));
    el("adoptA").onclick=()=>adopt("A");
    el("adoptB").onclick=()=>adopt("B");
    el("clearDecision").onclick=clearDecision;
    el("rawToggle").onclick=()=>{ showRaw=!showRaw; renderCurrent(); };
    labelInputs.forEach(input => input.onchange=()=>{ decisions[currentId]=readForm("manual"); persist(); });
    ["decisionAnswer","decisionReason"].forEach(id => {
      el(id).oninput=()=>{ clearTimeout(saveTimer); saveTimer=setTimeout(commitCurrent,350); };
    });
    ["decisionTool","decisionConfidence"].forEach(id => el(id).onchange=commitCurrent);
    el("exportFinal").onclick=exportFinal;
    el("exportTrail").onclick=exportTrail;
    el("backupJson").onclick=backup;
    el("restoreJson").onclick=()=>el("restoreInput").click();
    el("restoreInput").onchange=e=>{ if(e.target.files[0]) restore(e.target.files[0]); e.target.value=""; };
    el("clearAll").onclick=()=>{
      if(confirm("确定清空本浏览器中全部人工裁决吗？原始 A/B 标注不会受影响。")) {
        decisions={}; localStorage.removeItem(STORAGE_KEY); applyFilter(false); updateSummary();
      }
    };
    document.addEventListener("keydown", event => {
      if (event.target.matches("input,textarea,select")) return;
      if (event.key === "ArrowLeft" || event.key.toLowerCase() === "k") move(-1);
      if (event.key === "ArrowRight" || event.key.toLowerCase() === "j") move(1);
      if (event.key.toLowerCase() === "a") adopt("A");
      if (event.key.toLowerCase() === "b") adopt("B");
      if (["1","2","3","4"].includes(event.key)) {
        labelInputs[Number(event.key)-1].click();
      }
    });
    window.addEventListener("beforeunload",commitCurrent);

    loadLocal();
    updateSummary();
    applyFilter(false);
  </script>
</body>
</html>
"""


def build_html(rows: list[dict[str, object]], output_path: Path) -> str:
    final_name = output_path.with_suffix("").name + "_completed.csv"
    trail_name = output_path.with_suffix("").name + "_audit_trail.csv"
    return (
        HTML_TEMPLATE.replace("__DATA__", safe_json_for_script(rows))
        .replace("__FINAL_NAME__", json.dumps(final_name, ensure_ascii=False))
        .replace("__TRAIL_NAME__", json.dumps(trail_name, ensure_ascii=False))
    )


def main() -> None:
    args = parse_args()
    rows_a = read_blind_csv(args.input_a)
    rows_b = read_blind_csv(args.input_b)
    merged = merge_rows(rows_a, rows_b)
    output = Path(args.output)
    output.write_text(build_html(merged, output), encoding="utf-8", newline="\n")
    disagreements = sum(not bool(row["label_agreement"]) for row in merged)
    print(
        json.dumps(
            {
                "input_a": args.input_a,
                "input_b": args.input_b,
                "output": str(output),
                "rows": len(merged),
                "label_agreements": len(merged) - disagreements,
                "label_disagreements": disagreements,
                "bytes": output.stat().st_size,
                "fields": EXPECTED_FIELDS,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
