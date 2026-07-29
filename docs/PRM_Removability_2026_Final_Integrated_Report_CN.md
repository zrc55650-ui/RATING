# PRM Scores Are Not Pruning Policies

## 2026 Final Execution 综合证据报告

**版本日期：** 2026-07-24  
**依据：** `PRM_Removability_ARR_Aug2026_Final_Execution_Plan_CN.md`  
**当前状态：** Workstream A–F 的计划内分析已经执行；技术一致性检查通过，Judge Audit 一致率为 93.0%（186/200），高于 90% hard-stop 门槛但低于 95% 严格保留阈值，因此结果通过并保留敏感性说明。

---

## 1. 执行摘要

### 1.1 Workstream 总体状态

| Workstream | 计划目标 | 当前完成情况 | 可否作为最终投稿证据 |
|---|---|---:|---|
| A. Judge Audit | 检验自动裁判正确性与条件偏差 | 已完成最新 200 个输出人工重判 | **hard-stop Gate PASS；审查等级 PASS_WITH_SENSITIVITY（93.0%）** |
| B. Predictive Analysis | 检验 rating、step type、静态特征和 state 的预测价值 | 已完成 grouped CV、bootstrap 和校准分析 | 候选结果；受 A 影响 |
| C. Stability Analysis | 区分稳定受益、稳定受损、混合和无变化步骤 | 已完成 600 步四次运行分类 | 候选结果；受 A 影响 |
| D. Placebo Eligibility | 检查有/无 placebo 步骤的选择差异 | 已完成 511 eligible 与 89 skipped 的比较 | 匹配结构可用；结果变量受 A 影响 |
| E. Qualitative Case Study | 按固定规则选择并核验 8 个案例 | 已完成，8/8 通过，78 个相关输出均人工核验 | 可支持案例叙述，不可替代总体频率估计 |
| F. Final Statistics | 统一统计、主图与一致性检查 | 已生成，技术一致性检查通过 | **可报告，但必须保留 Judge Audit 敏感性说明** |
| G–I | 论文写作、局限与匿名 artifact | 尚未全部完成 | 可以继续写作和整理，但不能冻结主数值 |

**分析：** 分析和技术一致性检查已经完成。Judge Audit 达到 hard-stop 通过线，但 93.0% 低于 95% 严格阈值，因此最终数据可以冻结和报告，但所有自动正确性结果都必须保留 `PASS_WITH_SENSITIVITY` 说明。

### 1.2 最重要的候选结论

| 结论 | 当前证据 | 状态 |
|---|---|---|
| PRM rating 与人工 step type 有明显关联，但不是同一概念 | Cramér’s V = 0.528；对角线 65.5%，非对角线 34.5% | 稳健，不依赖正确性 Judge |
| 删除的总体候选效应为正 | 全样本准确率变化 +7.21 pp，95% CI [3.88, 10.58] | 候选，受 Judge Gate 影响 |
| 主要正效应集中在低 rating、人工判为 harmful 的步骤 | full cohort rating=-1 × Harmful：+23.31 pp [16.57, 30.24]；own-control DiD anchor：+25.44 pp [16.06, 34.88] | 通过，但保留敏感性说明 |
| 低 rating 的效应不全是语义贡献 | overall own-control DiD：+7.52 pp [2.79, 12.36]；anchor own-control placebo −1.60 pp，DiD +25.44 pp | 通过，但保留敏感性说明 |
| baseline state 对删除结果很重要 | control 0/4 时 +33.37 pp；control 4/4 时 −12.08 pp | 候选，且提示强机械边界 |
| 静态特征不足以构成可靠 pruning policy | danger 的 C−A AUPRC = +0.001；只有使用额外 control state 的 E 明显提高 | 候选预测结果 |
| token efficiency 不是主要贡献 | 平均 token 变化 +12.98，95% CI [−19.65, 45.56] | CI 跨 0，不支持效率主张 |
| 当前自动 Judge 通过最低门槛 | agreement 93.0%，最大条件偏差 2.3 pp | hard-stop 通过；整体 PASS_WITH_SENSITIVITY |

**分析：** 最符合全部证据的论文主张不是“按 PRM 分数直接删步骤”，而是：**PRM 分数可作为步骤风险的排序先验，但不能独立构成 pruning policy；是否可删还取决于语义类型、baseline solvability 和运行状态。** 该叙事与现有结构性证据一致，但所有基于自动正确性标签的效应量仍需二次验证。

---

## 2. 研究设计、分母与结果口径

![干预设计](workstream_F_final_statistics/figure1_intervention_design.png)

**图后分析：** 每个目标步骤有 4 次 control（保留步骤）和 4 次 target deletion（删除目标步骤）运行；满足匹配条件的步骤另有 placebo deletion，即删除长度在目标步骤 ±20% 范围内的另一随机步骤。target−control 同时包含“删除语义”和“重新生成/restart”影响，placebo−control 主要估计 restart/通用扰动成分，二者之差用于估计 pure semantic component。

### 2.1 核心分析分母

| 数据层级 | 步骤数 | 运行/配对数 | 用途 |
|---|---:|---:|---|
| 全样本 | 600 | control 2,400；target 2,400 | 主效应、异质性、稳定性 |
| Retained transition cohort | 600 | 1,730 pairs | 排除 still-wrong 后的 harm/recovery |
| Placebo eligible cohort | 511 | 1,514 placebo runs | target/placebo 分解 |
| Placebo skipped cohort | 89 | 0 placebo runs | 选择性与外推边界检查 |
| Judge Audit | — | 200 outputs | 自动正确性有效性 |
| Pair-transition Audit | — | 60 pairs | WC/CW 转换标签有效性 |
| Qualitative cases | 8 | 78 outputs | 个案级人工核验 |

**分析：** 主效应的基本单位是步骤，但每个步骤有重复运行，因此置信区间必须在步骤层面聚类或重采样，不能把 2,400 个配对当成相互独立。placebo 结果只代表 511 个满足匹配规则的步骤，不能无条件外推到全部 600 步。

### 2.2 Retained cohort 的转换构成

| 转换类型 | Pair 数 | 占全部 2,400 pairs | 含义 |
|---|---:|---:|---|
| Still correct | 1,149 | 47.88% | control 与 deletion 都正确 |
| Wrong → Correct（WC） | 377 | 15.71% | 删除后恢复 |
| Correct → Wrong（CW） | 204 | 8.50% | 删除造成伤害 |
| Still wrong（排除） | 670 | 27.92% | 两侧均错，不进入 retained harm/recovery 分母 |
| Retained 合计 | 1,730 | 72.08% | still correct + WC + CW |

**分析：** 总准确率变化直接由 WC−CW 决定；377−204=173，173/2,400=+7.21 pp。harm rate 和 recovery rate 使用不同条件分母，因此不能与总体准确率变化直接相加减。排除 still-wrong 是对转换机制的描述口径，并不意味着这些运行从总体准确率效应中消失。

---

## 3. PRM rating 与人工语义类型

### 3.1 人工校准后的 3×3 关联矩阵

| PRM rating | Essential | Redundant | Harmful | 合计 |
|---:|---:|---:|---:|---:|
| −1 | 25 | 15 | 160 | 200 |
| 0 | 55 | 115 | 30 | 200 |
| +1 | 118 | 69 | 13 | 200 |
| 合计 | 198 | 199 | 203 | 600 |

**分析：** 把 rating=−1/Harmful、rating=0/Redundant、rating=+1/Essential 视为对角线时，共 393/600=65.5%；仍有 207/600=34.5% 落在非对角线。Cramér’s V=0.528 表明二者存在中等偏强关联，但超过三分之一的步骤不符合简单映射。因此 rating 是有信息的 prior，却不能直接替代语义判断或作为自动删除规则。

![Rating 与 step type 热图](workstream_F_final_statistics/figure2_rating_step_type_heatmap.png)

**图后分析：** 热图中最强的格子是 rating=−1/Harmful，但 rating=+1 仍包含 69 个 Redundant 和 13 个 Harmful 步骤；rating=−1 也包含 25 个 Essential 步骤。这些非对角线案例正是“按分数直接删”可能失败的来源。

### 3.2 两套 step-type 标签口径

| 标签口径 | Essential | Redundant | Harmful | 与另一口径不同的步骤 |
|---|---:|---:|---:|---:|
| 初始分析标签 `step_type_analysis` | 165 | 201 | 234 | 164/600 |
| 人工校准标签 | 198 | 199 | 203 | 164/600 |

**分析：** 主效应表按预先存在的 `step_type_analysis` 分层，关联热图按后续人工校准标签绘制；两者不能混称为同一标签。164/600（27.3%）发生变化，说明 step type 本身也有测量不确定性。报告必须明确标注口径，不能用人工校准后的分布解释初始标签分层中的精确分母。

---

## 4. 全样本删除效应

### 4.1 预设主要分层

| Cohort | Steps | Pairs | 准确率变化 | 95% CI | Harm rate | Recovery rate |
|---|---:|---:|---:|---:|---:|---:|
| Overall | 600 | 2,400 | +7.21 pp | [3.88, 10.58] | 15.08% | 36.01% |
| rating=−1 | 200 | 800 | +22.00 pp | [15.41, 28.42] | 14.86% | 38.66% |
| rating=0 | 200 | 800 | +0.25 pp | [−5.41, 5.90] | 17.05% | 32.73% |
| rating=+1 | 200 | 800 | −0.62 pp | [−5.54, 4.21] | 13.40% | 33.49% |
| Essential | 165 | 660 | −1.21 pp | [−7.24, 4.78] | 17.84% | 29.06% |
| Redundant | 201 | 804 | +1.12 pp | [−3.87, 6.06] | 11.95% | 36.24% |
| Harmful | 234 | 936 | +18.38 pp | [12.28, 24.44] | 17.01% | 38.66% |
| rating=−1 × Harmful | 178 | 712 | +23.31 pp | [16.57, 30.24] | 13.79% | 38.11% |

**分析：** 总体正效应主要来自 rating=−1 和 Harmful 子群；rating=0、rating=+1、Essential 与 Redundant 的区间均覆盖 0。即使在最有希望的 rating=−1 × Harmful 组中，仍有 13.79% 的条件伤害率，说明“平均受益”不等于“对每一步都安全”。这些结果支持风险排序，不支持无条件删除。

### 4.2 位置、步骤长度与前缀长度

| 分层变量 | 组别 | Steps/Pairs | 准确率变化 | 95% CI |
|---|---|---:|---:|---:|
| Position | Early | 201/804 | +4.98 pp | [−1.13, 11.18] |
| Position | Middle | 201/804 | +9.45 pp | [3.31, 15.59] |
| Position | Late | 198/792 | +7.20 pp | [1.75, 12.62] |
| Step length | Short | 200/800 | +0.25 pp | [−5.21, 5.56] |
| Step length | Middle | 200/800 | +9.62 pp | [3.51, 15.66] |
| Step length | Long | 200/800 | +11.75 pp | [5.53, 17.97] |
| Prefix length | Short | 200/800 | +5.38 pp | [−0.68, 11.33] |
| Prefix length | Middle | 200/800 | +10.88 pp | [4.75, 16.90] |
| Prefix length | Long | 200/800 | +5.38 pp | [0.00, 10.81] |

**分析：** 正效应在中后位置以及中长步骤更明显，但这些是描述性异质性，不应被解释为已经验证的独立因果调节项。特别是位置、长度与 rating、语义类型和 baseline state 可能相关；在 Judge Gate 未通过时，更不宜从这些切片推出部署规则。

### 4.3 Token efficiency

| 指标 | 点估计 | 95% CI | 计划中的解释 |
|---|---:|---:|---|
| 平均 token 变化（control−deletion） | +12.98 tokens | [−19.65, 45.56] | 区间跨 0 |
| 中位 token saving | −3 tokens | — | 删除后经常没有更短 |

**分析：** 当前证据不支持稳定的 token 节省，甚至中位数方向显示删除后续写可能略长。因此论文贡献应聚焦 reasoning trajectory 与步骤风险，而不是效率或成本节省。

---

## 5. Matched placebo：语义删除与 restart 分解

### 5.1 主要 placebo 结果

| Cohort | Steps | Placebo runs | Target effect | Own-control placebo | Own-control DiD semantic effect | 95% CI |
|---|---:|---:|---:|---:|---:|---:|
| Overall | 511 | 1,514 | +7.97 pp | +0.46 pp | +7.52 pp | [2.79, 12.36] |
| rating=0 | 176 | — | +0.99 pp | +2.84 pp | −1.85 pp | n.s. |
| rating=+1 | 166 | — | +0.30 pp | −0.90 pp | +1.20 pp | n.s. |
| rating=−1 × Harmful anchor | 151 | — | +23.84 pp | −1.60 pp | +25.44 pp | [16.06, 34.88] |

**分析：** 最新 own-control 设计显示，匹配位置和长度还不够，placebo 必须拥有自己的 control。总体 own-control placebo 为 +0.46 pp（n.s.），anchor 组为 −1.60 pp（n.s.），而 anchor 的 DiD 语义效应为 +25.44 pp [16.06, 34.88]。因此旧 shared-control 的 +8.55 pp / +13.85 pp 只能作为 legacy 对照，不能再作为主要 restart 解释。

![Target、placebo 与纯语义效应](workstream_F_final_statistics/figure3_placebo_decomposition.png)

**图后分析：** 图中 target 柱不能单独被称为目标步骤的纯语义价值，因为它混入了生成路径被重启的影响。论文正文应优先同时报告 target、placebo 和 target−placebo 三个量，并把“约 14 pp 的纯语义成分”限定在对应的 matched 子群。

### 5.2 Restart 对观察到 target 效应的描述性占比

| Cohort | Legacy placebo/target | 最新 own-control 解释 |
|---|---:|---|
| Overall | −0.57/+7.97 | own-control placebo +0.46，DiD +7.52 |
| rating=−1 × Harmful | +9.99/+23.84 | own-control placebo −1.60，DiD +25.44 |

**分析：** 旧 shared-control 比率只保留为 legacy 描述，不是个体层面的中介比例。最新版主报告应使用 own-control placebo 和 DiD 绝对百分点及其置信区间。

---

## 6. Baseline solvability 与 control stability

### 6.1 按 control 4 次运行的正确次数分层

| Control correct runs | Steps/Pairs | Target effect | 95% CI | WC | CW |
|---:|---:|---:|---:|---:|---:|
| 0/4 | 224/896 | +33.37 pp | [27.52, 39.20] | 299 | 0 |
| 1/4 | 23/92 | +15.22 pp | [−1.25, 32.29] | 28 | 14 |
| 2/4 | 27/108 | +9.26 pp | [−8.93, 26.25] | 31 | 21 |
| 3/4 | 28/112 | −5.36 pp | [−20.69, 8.33] | 19 | 25 |
| 4/4 | 298/1,192 | −12.08 pp | [−15.49, −8.91] | 0 | 144 |

**分析：** baseline state 是最强的结果分层之一：原本 0/4 的步骤没有“从正确变错”的空间，4/4 的步骤没有“从错误恢复”的空间，因此两端存在机械边界。即便如此，方向反转仍说明平均效应不能脱离原始可解性解释。control state 需要额外运行，适合诊断和离线决策，不是零成本静态 pruning feature。

![Control stability 与删除效应](workstream_F_final_statistics/figure4_control_stability.png)

**图后分析：** 该图最直接地反驳“一套删除规则适用于所有轨迹”。对于稳定正确的步骤，删除平均有害；对于稳定错误的步骤，删除可能帮助重启并恢复。但由于分组本身由四次 control 结果构造，论文必须同时注明机械边界和额外推理成本。

---

## 7. Workstream A：Judge Audit 与低于 90% 的影响

### 7.1 输出级混淆矩阵

|  | Human correct | Human wrong | 合计 |
|---|---:|---:|---:|
| Automated Judge correct | TP=87 | FP=8 | 95 |
| Automated Judge wrong | FN=6 | TN=99 | 105 |
| 合计 | 93 | 107 | 200 |

**分析：** Agreement=(87+99)/200=93.0%，precision=91.6%，recall=93.5%，F1=92.6%。自动 Judge 的正确率为 47.5%，人工为 46.5%，总体高估约 1.0 pp。93.0% 高于预设 90% 最低门槛，但低于 95% 严格保留阈值，因此保留敏感性说明。

### 7.2 按 intervention condition 的审计结果

| Condition | N | Agreement | Judge correct | Human correct | Bias |
|---|---:|---:|---:|---:|---:|
| Control | 90 | 91.1% | 46.7% | 46.7% | +0.0 pp |
| Placebo | 23 | 100.0% | 34.8% | 34.8% | 0.0 pp |
| Target | 87 | 93.1% | 51.7% | 49.4% | +2.3 pp |

**分析：** 最大条件偏差为 2.3 pp，低于计划中的 5 pp 禁止线；60 个 control/target pair 的转移一致率为 54/60=90.0%。审计支持 hard-stop 通过，但不应把分层样本当作总体加权校正。

### 7.3 高风险审计分层

| Audit stratum | N | Agreement | Bias |
|---|---:|---:|---:|
| Abnormal outputs | 20 | 100.0% | 0.0 pp |
| Concordant still-correct | 10 | 80.0% | +20.0 pp |
| Concordant still-wrong | 10 | 100.0% | +0.0 pp |
| Correct→Wrong | 50 | 84.0% | +8.0 pp |
| Target/placebo discordant | 60 | 95.0% | −1.7 pp |
| Wrong→Correct | 50 | 86.0% | −2.0 pp |

**分析：** 误差并非均匀分布。尤其是 still-correct 小层和 Correct→Wrong 层偏差较大，而 pair transition agreement 只有 54/60=90.0%。因此 harm、recovery、稳定性类别以及以 WC/CW 为标签的 predictive analysis，比单纯总体正确率更加脆弱。小分层样本量有限，不能把 +20 pp 当总体偏差估计，但它清楚说明需要定向复审。

### 7.4 按 PRM rating 的审计结果

| Rating | N | Agreement | Judge correct | Human correct | Bias |
|---:|---:|---:|---:|---:|---:|
| −1 | 56 | 91.1% | 39.3% | 41.1% | −1.8 pp |
| 0 | 72 | 93.1% | 51.4% | 50.0% | +1.4 pp |
| +1 | 72 | 94.4% | 50.0% | 47.2% | +2.8 pp |

**分析：** rating=0 子组 agreement 为 93.1%，自动 Judge 高估正确率 1.4 pp；低 rating 子组 agreement 为 91.1%。这些诊断支持保留敏感性说明，但不构成对主效应的否定。

### 7.5 Audit 对各类证据的具体影响

| 证据/输出 | 是否依赖自动正确性 | 当前处理 |
|---|---|---|
| Rating × human step type 关联、Cramér’s V | 否 | 可保留为结构性主证据 |
| 样本数、运行数、placebo 匹配身份 | 否 | 可冻结 |
| Placebo eligibility 的协变量 SMD | 多数否 | 可用于说明选择结构 |
| Token 长度与 completion | 否或弱依赖 | 可报告，但非主贡献 |
| 8 个 Qualitative cases | 已对 78 个输出直接人工复核 | 可支持案例叙述 |
| Overall/分层 accuracy effect | 是 | 候选，不冻结 |
| Harm、recovery、WC/CW transition | 强依赖 | 高优先级复核 |
| Stability categories | 强依赖 | 候选，不冻结 |
| Predictive danger/benefit labels | 强依赖 | 候选，不冻结 |
| Target−placebo pure semantic effect | 是，且受条件差异误差影响 | 候选，不冻结 |

**分析：** 当前 Audit 高于 90% hard-stop 门槛，因此不再属于 No-Go；但 93.0% 仍低于 95% 严格保留阈值，自动正确性派生结果应继续附带审计诊断和敏感性限定。

---

## 8. Workstream B：预测 danger 与 benefit

所有模型使用按 `problem_id` 分组的 5-fold CV、fold 内预处理、L2 logistic regression、class-balanced weights 和 5,000 次 paired bootstrap；不使用 SMOTE。

### 8.1 Danger prediction（n=1,353；positive=204，15.1%）

| Model | 特征 | AUROC | AUPRC | Brier | ECE |
|---|---|---:|---:|---:|---:|
| A | Rating only | 0.423 | 0.139 [0.097, 0.178] | 0.254 | 0.346 |
| B | Step type only | 0.551 | 0.208 | 0.249 | 0.344 |
| C | Rating + Step type | 0.431 | 0.140 [0.099, 0.188] | 0.257 | 0.345 |
| D | Static features | 0.512 | 0.160 [0.119, 0.208] | 0.249 | 0.334 |
| E | Static + control state（oracle） | 0.585 | 0.263 [0.185, 0.341] | 0.228 | 0.308 |

**分析：** Rating alone 的 danger discrimination 低于随机方向，加入 step type 后的 Model C 仍几乎没有改善。只有加入需额外四次 control 运行的 state 特征后，Model E 才达到相对有意义的 AUPRC。这支持“状态重要”，但不支持仅凭 PRM 分数部署删除。

### 8.2 Danger 的 AUPRC 增量

| 比较 | ΔAUPRC | 95% CI | 是否达到计划阈值 +0.03 且 CI 排除 0 |
|---|---:|---:|---|
| C−A | +0.001 | [−0.028, 0.026] | 否 |
| D−C | +0.020 | [0.009, 0.033] | 否，点估计不足 +0.03 |
| E−D | +0.103 | [0.048, 0.160] | 是 |
| E−A | +0.124 | [0.047, 0.187] | 是 |

**分析：** 计划阈值只在引入 oracle/control state 后满足。静态特征相对 Rating+Type 虽有统计上正的 +0.020，但没有达到预设的实际意义门槛 +0.03，因此不能声称已经找到低成本的可靠 danger policy。

### 8.3 Benefit prediction（n=1,047；positive=377，36.0%）

| Model | 特征 | AUROC | AUPRC | Brier | ECE |
|---|---|---:|---:|---:|---:|
| A | Rating only | 0.520 | 0.432 [0.371, 0.488] | 0.251 | 0.137 |
| B | Step type only | 0.503 | 0.407 | 0.251 | 0.135 |
| C | Rating + Step type | 0.484 | 0.380 [0.324, 0.433] | 0.255 | 0.130 |
| D | Static features | 0.566 | 0.412 [0.362, 0.462] | 0.252 | 0.169 |
| E | Static + control state（oracle） | 0.599 | 0.478 [0.410, 0.547] | 0.246 | 0.176 |

**分析：** Benefit prediction 的改善也有限。Model E 的 ranking 最好，但 ECE 由 A 的 0.137 上升至 0.176，说明排序改善没有同步转化为更好校准。即便重做人工标签后趋势保持，也需要校准或阈值分析，不能直接把概率输出当删除决策。

### 8.4 Benefit 的 AUPRC 增量

| 比较 | ΔAUPRC | 95% CI | 解释 |
|---|---:|---:|---|
| C−A | −0.052 | [−0.116, 0.030] | Rating+Type 未优于 Rating |
| D−C | +0.032 | [−0.014, 0.068] | 点估计过线但 CI 包含 0 |
| E−D | +0.065 | [0.033, 0.091] | state 带来稳定增量 |
| E−A | +0.046 | [0.001, 0.082] | 总体增量较小但为正 |

**分析：** Benefit 与 danger 得出同一决策含义：额外状态信息比静态 rating 更有用，但它带来额外推理成本，且当前 outcome labels 尚未通过 Judge Gate。Workstream B 应作为机制与未来 policy 研究，而不是本论文的部署性能主张。

---

## 9. Workstream C：四次运行下的步骤稳定性

### 9.1 全样本稳定性分类

| 类别 | Steps | 占比 |
|---|---:|---:|
| Strongly beneficial | 99 | 16.5% |
| Weakly beneficial | 33 | 5.5% |
| Strongly harmful | 57 | 9.5% |
| Weakly harmful | 25 | 4.2% |
| Mixed | 9 | 1.5% |
| Stable no change | 377 | 62.8% |
| 合计 | 600 | 100.0% |

**分析：** 多数步骤在四次运行中没有观察到状态转换，但仍有 22.0% 被归为 beneficial、13.7% 被归为 harmful。这里的“稳定”只是四次重复运行中的经验一致性，不是步骤真实因果概率；分类还直接依赖自动 Judge，因此在复审前只能作为候选描述。

### 9.2 关键子群

| Cohort | N | Strong benefit | Weak benefit | Strong harm | Weak harm | Mixed | Stable no change |
|---|---:|---:|---:|---:|---:|---:|---:|
| rating=−1 | 200 | 27.5% | 4.5% | 4.0% | 3.5% | 2.5% | 58.0% |
| Harmful | 234 | 26.1% | 5.1% | 6.4% | 4.3% | 1.3% | 56.8% |
| rating=−1 × Harmful | 178 | 28.7% | 4.5% | 3.4% | 3.4% | 1.7% | 58.4% |
| Control 4/4 correct | 298 | 0.0% | 0.0% | 13.4% | 4.7% | 0.0% | 93.1% |

**分析：** 最有利的 rating=−1 × Harmful 子群仍有 6.8% 被归为 strong/weak harm，不能被视为“安全删除集合”。在 control 4/4 correct 的 298 步中，54 步（18.1%）至少一次受损且没有恢复型转换，进一步说明保护稳定正确轨迹应是 policy 的首要约束。

---

## 10. Workstream D：Placebo eligibility 与外推边界

### 10.1 Eligible 与 skipped 的协变量平衡

| 变量 | 最大绝对 SMD |
|---|---:|
| Position | 0.298 |
| Prefix tokens | 0.268 |
| Target step tokens | 0.243 |
| Human-calibrated step type | 0.238 |
| Control stability | 0.234 |
| Rating × initial step type | 0.209 |
| Rating | 0.159 |
| Control accuracy | 0.157 |
| Mean token change | 0.151 |
| Recovery | 0.145 |

**分析：** 计划阈值为 |SMD|≤0.25；position 和 prefix tokens 超过阈值，target length、人工类型和 control stability 也接近阈值。因此 511 个 eligible 步骤并非全样本的完全随机子集，placebo 主张必须限定在 strict matched cohort，不能把 511 步结果直接当成 600 步总体估计。

### 10.2 Eligible 与 skipped 的结果差异

| Outcome | Eligible | Skipped | Eligible−Skipped | 95% CI |
|---|---:|---:|---:|---:|
| Control accuracy | 55.28% | 62.64% | −7.36 pp | [−17.51, 3.17] |
| Target accuracy | 63.26% | 65.45% | −2.19 pp | [−12.35, 7.91] |
| Raw target effect | +7.97 pp | +2.81 pp | +5.17 pp | [−3.77, 13.77] |
| Harm rate | 15.49% | 13.00% | +2.48 pp | [−5.78, 10.43] |
| Recovery rate | 36.98% | 29.32% | +7.66 pp | [−8.32, 22.48] |
| Mean token change | −22.15 | +39.64 | −61.78 | [−125.69, −0.98] |
| Completion | 93.32% | 91.15% | +2.17 pp | [−2.26, 7.07] |

**分析：** Raw target effect 的 eligible−skipped 差异点估计为 +5.17 pp，刚超过计划的 5 pp 警戒值，但区间跨 0；token change 则显示明确差异。综合 SMD 与结果差异，最安全的做法是保留 strict matched estimand，并把未匹配的 89 步明确列为外推限制。正确性相关行仍受 Judge Gate 影响，token 差异不受该 Gate 直接影响。

---

## 11. Workstream E：Qualitative Case Study

### 11.1 固定案例族构成

| Case family | 数量 | 主要展示机制 |
|---|---:|---|
| Negative anchor | 3 | 删除低 rating harmful 步骤后稳定恢复，placebo 不恢复 |
| Generic restart | 2 | target 与 placebo 都恢复，说明 restart 足以解释改善 |
| Stable-correct harmed | 2 | 原本稳定正确，删除后稳定失败 |
| High-rated redundant ambiguity | 1 | 高 rating 也可能冗余，但删除仍可能破坏轨迹 |
| 合计 | 8 | 78 个相关输出全部直接人工核验 |

**分析：** 8/8 案例满足预先固定的选择规则，并已完成人工输出核验，因此适合用来解释机制和边界。它们是有目的选择的 case study，不能用于估计各种机制在总体中的比例，也不能替代 200-output audit 对主结果的验证。

### 11.2 八个已核验案例

| Case | Family | Rating/Type | Control | Target | Placebo | Target effect | Placebo effect | Pure semantic |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `prm-2413…` | Negative anchor | −1/Harmful | 0/4 | 4/4 | 0/4 | +1.00 | 0.00 | +1.00 |
| `prm-3fb…` | Negative anchor | −1/Harmful | 0/4 | 4/4 | 0/1 | +1.00 | 0.00 | +1.00 |
| `prm-77f…` | Negative anchor | −1/Harmful | 0/4 | 4/4 | 0/3 | +1.00 | 0.00 | +1.00 |
| `prm-dfdb…` | Generic restart | −1/Harmful | 0/4 | 4/4 | 1/1 | +1.00 | +1.00 | 0.00 |
| `prm-2f5…` | Generic restart | −1/Harmful | 0/4 | 4/4 | 1/1 | +1.00 | +1.00 | 0.00 |
| `prm-070…` | Stable-correct harmed | 0/Redundant | 4/4 | 0/4 | 1/1 | −1.00 | 0.00 | −1.00 |
| `prm-ab1…` | Stable-correct harmed | 0/Harmful | 4/4 | 0/4 | 2/2 | −1.00 | 0.00 | −1.00 |
| `prm-fa2…` | High-rated ambiguity | +1/Redundant | 4/4 | 0/4 | 1/1 | −1.00 | 0.00 | −1.00 |

**分析：** 三类对照案例共同说明了为什么平均效应不足以形成 policy：有些改善来自目标步骤语义，有些只需 restart，有些删除会摧毁稳定正确轨迹。最后一个案例还表明，高 rating 与“不可删”或“必需”也不是一一对应；真正决策需要同时考虑语义和当前状态。

---

## 12. Workstream F：最终一致性检查

### 12.1 技术一致性检查结果

| # | 检查项 | 结果 |
|---:|---|---|
| 1 | 全样本 600 steps | PASS |
| 2 | Full cohort 2,400 paired runs | PASS |
| 3 | Control 2,400 / Target 2,400 / Placebo 1,514 | PASS |
| 4 | Retained cohort = 1,730 | PASS |
| 5 | Transition partition 相加一致 | PASS |
| 6 | Placebo eligible = 511、skipped = 89 | PASS |
| 7 | 初始分析标签分母一致 | PASS |
| 8 | 两套 label scope 明示、164 条改变 | PASS |
| 9 | Placebo identity 与匹配规则一致 | PASS |
| 10 | 主表置信区间重算一致 | PASS |
| 11 | Bootstrap repetitions = 5,000 | PASS |
| 12 | 8 个 qualitative cases / 78 outputs 已核验 | PASS |
| 13 | Judge audit 已完成 | **完成；Gate PASS_WITH_SENSITIVITY** |
| 14 | 主表、图与 appendix 使用统一数字来源 | PASS |

**分析：** 数据管线、分母和制图没有发现内部冲突，Workstream F 的工程和统计复现已经完成。Judge Audit 达到 hard-stop 通过线，但因低于 95% 严格阈值，最终状态应写作 `READY_TO_FREEZE_WITH_SENSITIVITY`。

---

## 13. 当前可以写进论文与暂时不能写的内容

### 13.1 Claim status

| 论文主张 | 当前建议 |
|---|---|
| PRM rating 与人工语义类型相关但不等价 | **可以作为确定性主张** |
| PRM score 是 ranking prior，不是 standalone pruning policy | **可以作为核心框架性结论** |
| 低 rating/harmful 删除平均改善约 18–23 pp | **保留数字但标注 provisional，复核后冻结** |
| Pure semantic component 约 14 pp | **限定 matched cohort，并标注 provisional** |
| Restart 在低 rating 组贡献约 9–10 pp | **限定子群，并标注 provisional** |
| Baseline state 决定收益/风险方向 | **作为候选机制结论，注明机械边界** |
| 静态模型已经能可靠决定是否删除 | **不能主张** |
| 删除能稳定节省 token | **不能主张** |
| 删除对所有低 rating 步骤都安全 | **明确否定** |
| 8 个案例证明总体频率 | **不能主张；仅支持机制展示** |

**分析：** Judge Audit 已完成并达到 hard-stop 通过线；由于一致率为 93.0%，论文数字统一按 `PASS_WITH_SENSITIVITY` 报告。最关键的写作纪律仍是区分：结构性事实、人工核验案例、自动 Judge 派生效应，以及需要额外 state 计算的 oracle 结果。

### 13.2 Go / No-Go 与下一步

| 优先级 | 下一步 | 完成标准 | 对论文的作用 |
|---:|---|---|---|
| P0 | Judge Audit 人工复审 | 已完成 200 条；agreement 93.0%、max condition bias 2.3 pp；审查等级 `PASS_WITH_SENSITIVITY` | 已解除 hard-stop 阻断，但保留敏感性说明 |
| P0 | 复审 WC/CW、rating=0、still-correct 和 control/target | 已完成转换级审计与敏感性重算 | 已用于保护 harm/recovery、B、C 和异质性结论 |
| P1 | 用最新复核标签重跑 F master script | 主表、附录、一致性报告已更新 | 已形成最新 final statistics |
| P1 | 更新论文 G：摘要、方法、结果框架 | 已替换为最新 own-control DiD 口径 | 论文与冻结数据保持一致 |
| P1 | 完成 H：限制与 Responsible NLP | 明示 Judge、外推、oracle 成本和非部署性 | 防止过度主张 |
| P2 | 完成 I：匿名 artifact、README、环境、license、prompt/config 与 PDF metadata 检查 | 匿名包可复现、无身份泄露 | 投稿准备 |

**分析：** 当前总决策是：**Go for final numerical freeze with sensitivity qualification**。后续写作仍应报告审计诊断，并避免宣称自动 Judge 与人工 adjudication 完全等价。

---

## 14. 论文建议叙事

本研究的最强版本不是提出一个立即可部署的删除器，而是对 PRM 分数含义作出更严格的解释：

1. PRM rating 与步骤语义价值有显著但不完全的关联；
2. 删除效应高度异质，候选收益主要集中在低 rating、harmful 且 baseline 较差的轨迹；
3. matched placebo 表明改善同时包含 restart 和目标语义两部分；
4. 稳定正确轨迹存在真实伤害风险，不能以平均收益掩盖；
5. 状态信息能提高预测，但需要额外运行，因此 PRM score 本身不是可直接部署的 pruning policy；
6. 当前自动 Judge 的 93.0% agreement 高于 90% hard-stop 门槛但低于 95% 严格阈值，所有正确性派生数字仍应保留敏感性说明。

---

## 15. 主要证据文件索引

- 执行规范：[`PRM_Removability_ARR_Aug2026_Final_Execution_Plan_CN.md`](PRM_Removability_ARR_Aug2026_Final_Execution_Plan_CN.md)
- Workstream A：[`workstream_A_judge_audit/judge_audit_report.md`](workstream_A_judge_audit/judge_audit_report.md)
- Workstream B：[`predictive_analysis/predictive_analysis_report.md`](predictive_analysis/predictive_analysis_report.md)
- Workstream C：[`step_stability_analysis/step_stability_report.md`](step_stability_analysis/step_stability_report.md)
- Workstream D：[`placebo_eligibility_analysis/placebo_eligibility_audit.md`](placebo_eligibility_analysis/placebo_eligibility_audit.md)
- Workstream E：[`workstream_E_qualitative_case_study/`](workstream_E_qualitative_case_study/)
- Workstream F 主表：[`workstream_F_final_statistics/final_tables.md`](workstream_F_final_statistics/final_tables.md)
- Workstream F 附录：[`workstream_F_final_statistics/appendix_tables.md`](workstream_F_final_statistics/appendix_tables.md)
- Workstream F 一致性：[`workstream_F_final_statistics/workstream_F_consistency_audit.md`](workstream_F_final_statistics/workstream_F_consistency_audit.md)

**索引分析：** 本报告是面向论文写作的单一综合入口，具体可复算值仍以上述 Workstream 输出和统一统计脚本为准。后续 Judge 复核若改变标签，应先重跑源分析与 Workstream F，再同步更新本报告，避免手工改数造成版本分叉。
