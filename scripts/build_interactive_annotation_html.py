#!/usr/bin/env python3
"""Build four self-contained interactive annotation HTML files (one per
annotator). Each file bundles task guides, the M3 sheet (60 steps) and the M4
fidelity sheet (35 paraphrase pairs); answers are picked with radio buttons,
autosaved to localStorage, and exported to a single CSV with one click.

Reads the four_way CSV sheets produced by build_four_annotator_package.py.
Stdlib only; run from the repository root.
"""

from __future__ import annotations

import html
import json

from analysis_common import ROOT, read_csv, xml_escape

M3_DIR = ROOT / "workstream_M3_human_annotation"
M4_DIR = ROOT / "workstream_M4_strong_controls"
OUT_DIR = M3_DIR / "four_way"

M3_LABELS = [
    ("essential", "essential(关键推进,删了会断)"),
    ("redundant", "redundant(冗余/纯过渡)"),
    ("harmful", "harmful(引入错误/坏方向)"),
    ("uncertain", "uncertain(无法判断)"),
]
M4_LABELS = [
    ("faithful", "faithful(同一主张,错误也原样保留)"),
    ("minor_deviation", "minor_deviation(轻微增删,作用不变)"),
    ("meaning_changed", "meaning_changed(数学内容变了,含修正错误)"),
    ("uncertain", "uncertain(无法判断)"),
]

STYLE = """
body{font-family:Georgia,'Songti SC',serif;max-width:920px;margin:0 auto;
  padding:70px 16px 60px;line-height:1.6}
.card{border:1px solid #c8ccd4;border-radius:8px;padding:12px 16px;margin:18px 0}
.card.done{border:2px solid #2e8b57;background:#f6fdf8}
.target{background:#fff7e0;border:2px solid #d9a400;border-radius:6px;padding:8px;margin:10px 0}
.paraphrase{background:#e8f6ec;border:2px solid #2e8b57;border-radius:6px;padding:8px;margin:10px 0}
pre{white-space:pre-wrap;font-family:inherit;margin:6px 0}
.problem{background:#eef3fb;padding:8px;border-radius:6px}
#bar{position:fixed;top:0;left:0;right:0;background:#20232a;color:#fff;
  padding:10px 16px;display:flex;gap:16px;align-items:center;z-index:9;
  font-family:-apple-system,'PingFang SC',sans-serif}
#bar button{font-size:15px;padding:6px 14px;border-radius:6px;border:0;cursor:pointer}
#export{background:#d9a400;font-weight:bold}
.choices label{display:inline-block;margin:3px 12px 3px 0;cursor:pointer}
.choices{margin:8px 0}
textarea{width:100%;min-height:34px;font-family:inherit}
details{background:#f7f7f2;border:1px solid #ddd;border-radius:8px;
  padding:10px 14px;margin:14px 0}
summary{cursor:pointer;font-weight:bold;font-size:17px}
.warn{background:#fff2f0;border:2px solid #c0392b;border-radius:6px;padding:10px 14px;margin:14px 0}
h2.task{border-bottom:2px solid #d9a400;padding-bottom:4px;margin-top:40px}
"""

SCRIPT = """
const KEY='steprem_annotations_'+PERSON;
let state={};
try{state=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){state={}}
function entry(id){if(!state[id])state[id]={};return state[id]}
function save(){localStorage.setItem(KEY,JSON.stringify(state));refresh()}
function refresh(){
  let done=0;
  for(const it of ITEMS){
    const s=state[it.id]||{};
    const ok=!!(s.label&&s.conf);
    if(ok)done++;
    document.getElementById('card_'+it.id).classList.toggle('done',ok);
  }
  document.getElementById('progress').textContent='已完成 '+done+' / '+ITEMS.length;
  return done;
}
document.addEventListener('change',e=>{
  const t=e.target;
  if(t.name&&t.name.startsWith('lab_')){entry(t.name.slice(4)).label=t.value;save()}
  if(t.name&&t.name.startsWith('conf_')){entry(t.name.slice(5)).conf=t.value;save()}
});
document.addEventListener('input',e=>{
  const t=e.target;
  if(t.id&&t.id.startsWith('note_')){entry(t.id.slice(5)).notes=t.value;save()}
});
function restore(){
  for(const it of ITEMS){
    const s=state[it.id];
    if(!s)continue;
    if(s.label){const el=document.querySelector('input[name="lab_'+it.id+'"][value="'+s.label+'"]');if(el)el.checked=true}
    if(s.conf){const el=document.querySelector('input[name="conf_'+it.id+'"][value="'+s.conf+'"]');if(el)el.checked=true}
    if(s.notes)document.getElementById('note_'+it.id).value=s.notes;
  }
  refresh();
}
function firstOpen(){
  for(const it of ITEMS){
    const s=state[it.id]||{};
    if(!(s.label&&s.conf)){
      document.getElementById('card_'+it.id).scrollIntoView({behavior:'smooth',block:'center'});
      return;
    }
  }
  alert('全部完成,可以导出了!');
}
function exportCsv(){
  const done=refresh();
  const missing=ITEMS.length-done;
  if(missing>0&&!confirm('还有 '+missing+' 条未完成(缺标签或信心分)。确定现在导出吗?'))return;
  const rows=[['task','annotation_order','annotation_id','label','confidence_1to5','notes']];
  for(const it of ITEMS){
    const s=state[it.id]||{};
    rows.push([it.task,it.order,it.id,s.label||'',s.conf||'',s.notes||'']);
  }
  const csv='\\uFEFF'+rows.map(r=>r.map(f=>'"'+String(f).replace(/"/g,'""')+'"').join(',')).join('\\r\\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  a.download='annotations_'+PERSON+'.csv';
  a.click();
}
window.addEventListener('load',restore);
"""


def md_to_html(md_path, replacements=(), skip_sections=()) -> str:
    text = md_path.read_text(encoding="utf-8")
    for old, new in replacements:
        assert old in text, f"{md_path.name}: missing {old!r}"
        text = text.replace(old, new)
    out, in_list = [], False
    skipping = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            skipping = line[3:].strip() in skip_sections
        if skipping:
            continue
        esc = html.escape(line, quote=False)
        while "**" in esc:
            esc = esc.replace("**", "<b>", 1).replace("**", "</b>", 1)
        while esc.count("`") >= 2:
            esc = esc.replace("`", "<code>", 1).replace("`", "</code>", 1)
        if line.startswith("# "):
            continue  # the <details> summary already names the guide
        elif line.startswith("## "):
            out.append(f"<h3>{esc[3:]}</h3>")
        elif line.startswith(("- ", "* ")) or (line[:3].rstrip(". ").isdigit() and ". " in line[:5]):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = esc.split(" ", 1)[1] if line.startswith(("- ", "* ")) else esc.split(". ", 1)[1]
            out.append(f"<li>{item}</li>")
        elif not line:
            if in_list:
                out.append("</ul>")
                in_list = False
        elif in_list and raw[:1].isspace():
            out[-1] = out[-1][: -len("</li>")] + " " + esc.strip() + "</li>"
        else:
            out.append(f"<p>{esc}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def choices_block(item_id: str, labels: list[tuple[str, str]], note_hint: str) -> str:
    label_radios = "".join(
        f"<label><input type='radio' name='lab_{item_id}' value='{value}'> {text}</label>"
        for value, text in labels
    )
    conf_radios = "".join(
        f"<label><input type='radio' name='conf_{item_id}' value='{v}'> {v}</label>"
        for v in range(1, 6)
    )
    return (
        f"<div class='choices'><b>标签:</b><br>{label_radios}</div>"
        f"<div class='choices'><b>信心(1=很不确定,5=很确定):</b> {conf_radios}</div>"
        f"<textarea id='note_{item_id}' placeholder='{note_hint}'></textarea>"
    )


def build_person(person: str, index: int, m3_guide: str, m4_guide: str) -> None:
    m3_rows = read_csv(OUT_DIR / f"m3_sheet_{person}.csv")
    m4_rows = read_csv(M4_DIR / "four_way" / f"m4_fidelity_sheet_{person}.csv")
    items, cards_m3, cards_m4 = [], [], []

    for row in m3_rows:
        item_id = row["annotation_id"]
        items.append({"task": "m3", "order": int(row["annotation_order"]), "id": item_id})
        cards_m3.append(
            f"<div class='card' id='card_{item_id}'>"
            f"<h3>任务一 #{row['annotation_order']} / {len(m3_rows)} &middot; {item_id}</h3>"
            f"<div class='problem'><b>Problem</b><pre>{xml_escape(row['problem'])}</pre></div>"
            f"<b>之前的推理(prefix)</b><pre>{xml_escape(row['prefix_steps'])}</pre>"
            f"<div class='target'><b>TARGET STEP(只判断这一步)</b><pre>{xml_escape(row['target_step'])}</pre></div>"
            f"<b>之后的推理(downstream)</b><pre>{xml_escape(row['downstream_steps'])}</pre>"
            + choices_block(item_id, M3_LABELS, "选填备注")
            + "</div>"
        )
    for row in m4_rows:
        item_id = row["annotation_id"]
        items.append({"task": "m4_fidelity", "order": int(row["annotation_order"]), "id": item_id})
        cards_m4.append(
            f"<div class='card' id='card_{item_id}'>"
            f"<h3>任务二 #{row['annotation_order']} / {len(m4_rows)} &middot; {item_id}</h3>"
            f"<div class='problem'><b>Problem</b><pre>{xml_escape(row['problem'])}</pre></div>"
            f"<div class='target'><b>ORIGINAL STEP(原句)</b><pre>{xml_escape(row['original_step'])}</pre></div>"
            f"<div class='paraphrase'><b>PARAPHRASE(改写句)</b><pre>{xml_escape(row['paraphrase_step'])}</pre></div>"
            + choices_block(item_id, M4_LABELS, "选填;判 meaning_changed 请写哪里变了")
            + "</div>"
        )

    doc = (
        "<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>"
        f"<title>标注者{index} · 标注任务(95 条)</title><style>{STYLE}</style></head><body>"
        "<div id='bar'><span id='progress'>已完成 0 / 95</span>"
        "<button onclick='firstOpen()'>跳到下一条未完成</button>"
        "<button id='export' onclick='exportCsv()'>完成后点我导出 CSV</button></div>"
        f"<h1>标注者{index}:两项小任务,共 {len(items)} 条(约 75 分钟)</h1>"
        "<div class='warn'><b>使用须知</b>:直接在本页面点选,答案自动保存在这台电脑的浏览器里"
        "(请全程用同一台电脑、同一浏览器打开本文件,不要用无痕/隐私模式)。"
        "全部完成后点右上角<b>导出 CSV</b>,把下载的 <code>annotations_"
        f"{person}.csv</code> 文件发回即可。请独立完成,不要与任何人讨论题目,"
        "不要查询数据集标签或论文。</div>"
        f"<details open><summary>任务一指南:推理步骤类型判断({len(m3_rows)} 条,必读)</summary>{m3_guide}</details>"
        f"<details open><summary>任务二指南:改写保真对比({len(m4_rows)} 条,必读)</summary>{m4_guide}</details>"
        f"<h2 class='task'>任务一:步骤类型判断({len(m3_rows)} 条)</h2>"
        + "".join(cards_m3)
        + f"<h2 class='task'>任务二:改写保真对比({len(m4_rows)} 条,比任务一快很多)</h2>"
        + "".join(cards_m4)
        + "<div style='text-align:center;margin:40px 0'>"
        "<button style='font-size:18px;padding:10px 26px' onclick='exportCsv()'>导出 CSV</button></div>"
        f"<script>const PERSON={json.dumps(person)};const ITEMS={json.dumps(items)};{SCRIPT}</script>"
        "</body></html>"
    )
    out_path = OUT_DIR / f"interactive_annotator{index}_{person}.html"
    out_path.write_text(doc, encoding="utf-8")
    print(out_path, f"({len(items)} items)")


def main() -> None:
    m3_guide = md_to_html(
        M3_DIR / "m3_annotation_guideline.md",
        (
            ("(120 steps,双人独立盲标)", "(每人 60 条)"),
            ("6. 完成后只回传 CSV(三列填写完毕),不要改动其他列。",
             "6. 全部完成后点页面右上角「导出 CSV」,把下载的文件发回。"),
        ),
        skip_sections=("材料", "评价(标注完成后)"),
    )
    m4_guide = md_to_html(
        M4_DIR / "m4_fidelity_guideline.md",
        (
            ("(140 条,单人独立盲标)", "(每人 35 条)"),
            ("5. 每完成 35 条休息一次。", "5. 一口气可完成,累了随时休息。"),
        ),
        skip_sections=("材料与回传",),
    )
    for index, person in enumerate(["P1", "P2", "P3", "P4"], start=1):
        build_person(person, index, m3_guide, m4_guide)


if __name__ == "__main__":
    main()
