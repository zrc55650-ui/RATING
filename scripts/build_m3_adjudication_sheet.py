#!/usr/bin/env python3
"""Build an interactive transcription sheet for the M3 third-rater
adjudication: the 46 disagreement items, each showing full context and both
annotators' labels, with a radio group for the final adjudicated label and a
one-click CSV export (annotation_id, final_label, notes).

Stdlib only; run from the repository root.
"""

from __future__ import annotations

import json

from analysis_common import ROOT, read_csv, xml_escape

M3_DIR = ROOT / "workstream_M3_human_annotation"
CATS = [
    ("essential", "essential(关键推进)"),
    ("redundant", "redundant(冗余/过渡)"),
    ("harmful", "harmful(引入错误/坏方向)"),
    ("uncertain", "uncertain(无法判断)"),
]

STYLE = """
body{font-family:Georgia,'Songti SC',serif;max-width:920px;margin:0 auto;
  padding:70px 16px 60px;line-height:1.6}
.card{border:1px solid #c8ccd4;border-radius:8px;padding:12px 16px;margin:18px 0}
.card.done{border:2px solid #2e8b57;background:#f6fdf8}
.target{background:#fff7e0;border:2px solid #d9a400;border-radius:6px;padding:8px;margin:10px 0}
.votes{background:#f3eefb;border:1px solid #9b7fd4;border-radius:6px;padding:8px;margin:10px 0}
pre,.txt{white-space:pre-wrap;font-family:inherit;margin:6px 0}
.problem{background:#eef3fb;padding:8px;border-radius:6px}
#bar{position:fixed;top:0;left:0;right:0;background:#20232a;color:#fff;
  padding:10px 16px;display:flex;gap:16px;align-items:center;z-index:9;
  font-family:-apple-system,'PingFang SC',sans-serif}
#bar button{font-size:15px;padding:6px 14px;border-radius:6px;border:0;cursor:pointer}
#export{background:#d9a400;font-weight:bold}
.choices label{display:inline-block;margin:3px 12px 3px 0;cursor:pointer}
.choices{margin:8px 0}
textarea{width:100%;min-height:34px;font-family:inherit}
.warn{background:#fff2f0;border:2px solid #c0392b;border-radius:6px;padding:10px 14px;margin:14px 0}
"""

SCRIPT = """
const KEY='steprem_m3_adjudication';
let state={};
try{state=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){state={}}
function entry(id){if(!state[id])state[id]={};return state[id]}
function save(){localStorage.setItem(KEY,JSON.stringify(state));refresh()}
function refresh(){
  let done=0;
  for(const it of ITEMS){
    const s=state[it.id]||{};
    const ok=!!s.label;
    if(ok)done++;
    document.getElementById('card_'+it.id).classList.toggle('done',ok);
  }
  document.getElementById('progress').textContent='已完成 '+done+' / '+ITEMS.length;
  return done;
}
document.addEventListener('change',e=>{
  const t=e.target;
  if(t.name&&t.name.startsWith('lab_')){entry(t.name.slice(4)).label=t.value;save()}
});
document.addEventListener('input',e=>{
  const t=e.target;
  if(t.id&&t.id.startsWith('note_')){entry(t.id.slice(5)).notes=t.value;save()}
});
window.addEventListener('load',()=>{
  for(const it of ITEMS){
    const s=state[it.id];
    if(!s)continue;
    if(s.label){const el=document.querySelector('input[name="lab_'+it.id+'"][value="'+s.label+'"]');if(el)el.checked=true}
    if(s.notes)document.getElementById('note_'+it.id).value=s.notes;
  }
  refresh();
});
function firstOpen(){
  for(const it of ITEMS){
    if(!(state[it.id]&&state[it.id].label)){
      document.getElementById('card_'+it.id).scrollIntoView({behavior:'smooth',block:'center'});
      return;
    }
  }
  alert('全部完成,可以导出了!');
}
function exportCsv(){
  const done=refresh();
  const missing=ITEMS.length-done;
  if(missing>0&&!confirm('还有 '+missing+' 条未裁决。确定现在导出吗?'))return;
  const rows=[['annotation_id','final_label','notes']];
  for(const it of ITEMS){
    const s=state[it.id]||{};
    rows.push([it.id,s.label||'',s.notes||'']);
  }
  const csv='\\uFEFF'+rows.map(r=>r.map(f=>'"'+String(f).replace(/"/g,'""')+'"').join(',')).join('\\r\\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  a.download='m3_adjudication_final.csv';
  a.click();
}
"""


def main() -> None:
    disagreements = read_csv(M3_DIR / "m3_pilot_disagreements.csv")
    context = {}
    for sheet in ("P1", "P3"):
        for row in read_csv(M3_DIR / "four_way" / f"m3_sheet_{sheet}.csv"):
            context[row["annotation_id"]] = row

    items, cards = [], []
    for order, row in enumerate(disagreements, start=1):
        item_id = row["annotation_id"]
        ctx = context[item_id]
        items.append({"id": item_id})
        cards.append(
            f"<div class='card' id='card_{item_id}'>"
            f"<h3>#{order} / {len(disagreements)} &middot; {item_id}"
            f"(标注对 {row['rater_pair']})</h3>"
            f"<div class='problem'><b>Problem</b><div class='txt'>{xml_escape(ctx['problem'])}</div></div>"
            f"<b>之前的推理(prefix)</b><div class='txt'>{xml_escape(ctx['prefix_steps'])}</div>"
            f"<div class='target'><b>TARGET STEP</b><div class='txt'>{xml_escape(ctx['target_step'])}</div></div>"
            f"<b>之后的推理(downstream)</b><div class='txt'>{xml_escape(ctx['downstream_steps'])}</div>"
            f"<div class='votes'><b>两位标注者的分歧</b>:A = <code>{row['label_a']}</code>"
            f"(信心 {row['conf_a']}{',备注:' + xml_escape(row['notes_a']) if row['notes_a'] else ''})"
            f" &nbsp;vs&nbsp; B = <code>{row['label_b']}</code>"
            f"(信心 {row['conf_b']}{',备注:' + xml_escape(row['notes_b']) if row['notes_b'] else ''})</div>"
            "<div class='choices'><b>最终裁决:</b><br>"
            + "".join(
                f"<label><input type='radio' name='lab_{item_id}' value='{v}'> {t}</label>"
                for v, t in CATS
            )
            + "</div>"
            f"<textarea id='note_{item_id}' placeholder='选填:裁决理由'></textarea>"
            "</div>"
        )

    mathjax = (
        "<script>window.MathJax={tex:{inlineMath:[['$','$'],['\\\\(','\\\\)']],"
        "displayMath:[['$$','$$'],['\\\\[','\\\\]']],processEscapes:true,"
        "processEnvironments:true},options:{skipHtmlTags:"
        "['script','noscript','style','textarea','code']}};</script>"
        "<script async src='https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js'></script>"
    )
    doc = (
        "<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>"
        f"<title>M3 分歧裁决转录({len(items)} 条)</title>{mathjax}"
        f"<style>{STYLE}</style></head><body>"
        "<div id='bar'><span id='progress'>已完成 0 / 46</span>"
        "<button onclick='firstOpen()'>跳到下一条未裁决</button>"
        "<button id='export' onclick='exportCsv()'>完成后点我导出 CSV</button></div>"
        f"<h1>M3 分歧裁决转录({len(items)} 条)</h1>"
        "<div class='warn'>对照第三位裁决人的手写记录,把每条的最终标签点选进来;"
        "若裁决人愿意直接在本页面裁决亦可(每条卡片底部已列出两位标注者的分歧标签与理由)。"
        "答案自动保存在本机浏览器;完成后点右上角导出 "
        "<code>m3_adjudication_final.csv</code> 发回。公式渲染需联网。</div>"
        + "".join(cards)
        + "<div style='text-align:center;margin:40px 0'>"
        "<button style='font-size:18px;padding:10px 26px' onclick='exportCsv()'>导出 CSV</button></div>"
        f"<script>const ITEMS={json.dumps(items)};{SCRIPT}</script>"
        "</body></html>"
    )
    out = M3_DIR / "m3_adjudication_sheet.html"
    out.write_text(doc, encoding="utf-8-sig")
    print(out, f"({len(items)} items)")


if __name__ == "__main__":
    main()
