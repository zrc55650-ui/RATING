# M3 人工标注 Pilot 结果(2026-07-25)

**门槛判定:FAIL。** 预设通过标准为 raw agreement ≥ 80% 且 κ/AC1 ≥ 0.65;
实测 pooled agreement 61.7%,Cohen's κ 0.40,Gwet's AC1 0.52。
按预案不进入 300–600 步正式标注,先做分歧裁决与指南修订。

## 设计

120 步(40 diagonal / 40 off-diagonal / 40 random),四人两两背靠背:
P1×P2 标注前 60 步,P3×P4 标注后 60 步;交互式 HTML 盲标
(无 PRM 分数、无数据集标签、无删除结果),四选一
(essential / redundant / harmful / uncertain)+ 信心 1–5。
回收文件:`data/annotations/returns_2026-07-25/annotations_P1..P4.csv`,全部 95/95 完成、无空白。

## 一致性(`m3_pilot_agreement.csv`)

| 范围 | n | raw agreement | Cohen's κ | Gwet's AC1 |
|---|---|---|---|---|
| P1×P2 | 60 | 0.533 | 0.230 | 0.418 |
| P3×P4 | 60 | 0.700 | 0.515 | 0.624 |
| **pooled** | 120 | **0.617** | **0.397** | **0.516** |
| pooled(剔除 uncertain) | 112 | 0.661 | 0.448 | 0.514 |

## 分歧结构诊断(`m3_pilot_confusion.csv` / `m3_pilot_disagreements.csv`)

46 条分歧中:

1. **essential ↔ redundant 边界占 24/46(52%)**——"该步是否提供后续必需的信息"
   的判断口径不统一,是首要修订对象;
2. **P1 是离群标注者**:60 条只标了 1 条 harmful(P2 同批标了 7 条),
   P1×P2 的 κ(0.23)远低于 P3×P4(0.51);P1 在 M4 任务中同样表现出
   系统性偏严的类别口径。P1 需重新校准培训或更换;
3. harmful 类相对稳健:双方都用 harmful 时一致 15 条,
   harmful 相关混淆主要与 essential(11 条);
4. 12/46 的分歧至少一方信心 ≤2,属"自知不确定"型。

## 效度信号(`m3_pilot_validity.csv`,74 条共识子集)

尽管信度未达标,共识标签与冻结实验结果高度同向:

| 人工共识 | n | rating=-1 占比 | 平均 target 效应 | 平均纯语义效应 | danger 步占比 |
|---|---|---|---|---|---|
| harmful | 15 | 93.3% | +25.00pp | **+22.92pp** | 0.000 |
| essential | 42 | 21.4% | +4.17pp | +2.55pp | 0.214 |
| redundant | 17 | 11.8% | −22.06pp | −5.77pp | 0.353 |

人工共识 harmful 的删除收益与论文 anchor 结论一致;人工认为 redundant 的步骤
删除后 raw 效应反而 −22pp 而纯语义仅 −5.8pp——与"截断删除的 restart 代价"
叙事一致。

## 后续(按计划的 pilot-fail 预案)

1. 对 46 条分歧做第三方裁决(材料已备:`m3_pilot_disagreements.csv`
   含双方标签、信心、备注、原文);
2. 指南 v2:给 essential/redundant 边界补判定规则与范例
   (「删除后下一步是否引用该步引入的量/结论」);
3. P1 重新校准或更换后,抽 40–60 步复测;复测达标再扩 300–600 步;
4. 论文中 §18 第 3 条(人工标注)仍记为未满足;当前版本按
   "pilot + 效度信号 + 已识别的边界问题"如实披露。

> **2026-07-25 追记**:第三人已完成 46 条分歧的手写裁决,论文 Limitations 暂以「reported adjudication accuracy 93%(records to be digitized)」引用;**投稿前必须**用 `m3_adjudication_sheet.html` 转录出 `m3_adjudication_final.csv`,由 `analyze_human_annotations.py` 复算后把该句替换为精确口径(注意:120 条终标 vs 数据集标签的一致率数学上限为 82.5%,93% 只能是其他口径,转录后核实)。
