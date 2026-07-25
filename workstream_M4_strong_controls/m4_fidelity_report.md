# M4 改写保真人工审核结果(2026-07-25)

**门槛判定:PASS。** faithful + minor_deviation = **97.1%**(≥90% 门槛),
meaning_changed 仅 3/140(2.1%);**negative_anchor 组 46 条中 0 条 meaning_changed
(保真率 100%)**——C3(保义改写)条件的关键前提成立:改写没有"悄悄修正错误"。

## 设计

从 221 条通过自动长度/格式检查的改写中分层抽 140 条
(anchor 46 / neutral 46 / stable 48),四位标注者各 35 条,盲评
(不显示分组、不显示删除结果),四选一
(faithful / minor_deviation / meaning_changed / uncertain)+ 信心 1–5。
指南核心规则:原句的错误必须被原样保留才算 faithful,悄悄改对 = meaning_changed。

## 结果(`m4_fidelity_results.csv`)

| 范围 | n | faithful | minor | changed | uncertain | 保真率(f+m) |
|---|---|---|---|---|---|---|
| **overall** | 140 | 100 | 36 | 3 | 1 | **97.1%** |
| negative_anchor | 46 | 34 | 12 | 0 | 0 | **100%** |
| neutral_comparison | 46 | 30 | 13 | 2 | 1 | 93.5% |
| stable_correct | 48 | 36 | 11 | 1 | 0 | 97.9% |

标注者口径差异:P1 大量使用 minor_deviation(26/35),其余三人 strict-faithful
83–91%;这影响 strict-faithful 口径(71.4%)但不影响 faithful+minor 门槛口径。
被标 meaning_changed / uncertain 的 4 条清单见 `m4_fidelity_flagged_items.csv`
(anchor 组 0 条;2 条来自口径最严的 P1)。

## 论文含义

anchor 组 100% 保真 → M4 四条件三角互证(C3≈C0、C1>C3 +19.2pp)的
"保义改写确实保义"前提获得人工确认,可写入论文;建议在 Limitations 中
如实注明 neutral 组有 2 条改写被判改变含义(占该组 4.3%)。
