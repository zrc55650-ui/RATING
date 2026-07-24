# ARR Aug 2026：A–F 工作流结果报告

**报告状态：** `READY_TO_FREEZE`  
**覆盖范围：** Workstream A–F；按既定范围不包含 G–H。  
**结果口径：** `judge_audit_adjudicated.csv` 是 Judge Audit 的最终、冻结真值文件；所有主表、附录表和图表源数据均由同一套冻结结果生成。  
**置信区间：** 目标 step 层级的 5,000 次 cluster bootstrap，报告 95% percentile CI。

## 1. 执行摘要

在 600 个 target steps、2,400 个 Control–Target 配对结果上，删除目标步骤带来 **+7.21 个百分点**的总体正确率变化（95% CI：+3.88 至 +10.58 pp）。主要收益集中在分析标签为 `rating=-1` 和 `Harmful` 的步骤；`rating=0`、`rating=1` 及 `Essential` 子组的区间跨过零。

Placebo-matched 分析覆盖 511 个步骤和 1,514 个 placebo runs。总体 target effect 为 **+7.97 pp**，placebo effect 为 **−0.57 pp**，因此纯语义效应为 **+8.55 pp**（95% CI：+4.83 至 +12.17 pp）。该结论只能外推到 511-step matched cohort，不能填补 89 个跳过步骤的未观测 placebo 结果。

Judge Audit 的二分类一致率为 **93.5%（187/200）**，最大条件偏差为 **2.3 pp**，因此预设 hard-stop gate 通过；但未达到“不加敏感性说明即可保留”的 95% 一致率阈值，最终审查等级是 **`PASS_WITH_SENSITIVITY`**。这意味着结果可冻结和报告，但不能声称自动评估器与人工评估完全等价。

## 2. 数据、队列与定义

| 项目 | 数值/定义 |
|---|---:|
| Full cohort | 600 steps；2,400 paired outcomes |
| Retained diagnostic cohort | 1,730 pairs；仅用于转移诊断，不替代 full cohort |
| Placebo-matched cohort | 511 steps；1,514 placebo runs；89 steps skipped |
| Target effect | Target deletion correct rate − Control correct rate |
| Placebo effect | Placebo deletion correct rate − Control correct rate |
| Pure semantic effect | Target effect − Placebo effect |
| Bootstrap | 5,000 replicates；step-level cluster bootstrap |

这张表确定了所有后续分母和效应定义。主效应使用 600-step full cohort；placebo 分解使用预先匹配后仍有有效 placebo 结果的 511 steps；retained cohort 仅回答“错误是否被修复/正确是否被破坏”的转移问题。

## 3. Workstream A：Judge Audit

| 输出 | Agreement | Precision | Recall | F1 | TP | TN | FP | FN | 最大条件偏差 | 配对转移一致率 | Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 200 | 93.5% | 92.6% | 93.6% | 93.1% | 88 | 99 | 7 | 6 | 2.3 pp | 91.7% | **PASS** |

200 个审计输出中有 187 个与人工 adjudication 一致。最大条件级偏差（automated correct rate 减 human correct rate）为 2.3 pp，低于 5 pp hard-stop 上限，因此 gate 通过；但 93.5% 低于 95% 的严格保留阈值，必须在主结果旁保留审计诊断与敏感性限定。

### A.1 条件诊断

| 条件 | N | Agreement | Judge correct | Human correct | Bias (pp) |
|---|---:|---:|---:|---:|---:|
| control | 90 | 92.2% | 46.7% | 47.8% | −1.1 |
| placebo_delete | 23 | 100.0% | 34.8% | 34.8% | +0.0 |
| target_delete | 87 | 93.1% | 51.7% | 49.4% | +2.3 |

条件诊断显示误差并非集中到某一个条件；target_delete 的偏差最大但仍只有 +2.3 pp。由于审计样本是目的性分层抽样，这些偏差用于边界和敏感性说明，不用于把 200 个审计标签直接加权校正到全部 6,114 个输出。

### A.2 直接标签替换敏感性

| 范围 | 估计量 | Original | Substituted | Change (pp) |
|---|---|---:|---:|---:|
| full run table | control_correct_rate | 56.38% | 56.42% | +0.04 |
| full run table | target_delete_correct_rate | 63.58% | 63.50% | −0.08 |
| full run table | placebo_delete_correct_rate | 55.55% | 55.55% | +0.00 |
| full cohort | target − control | +7.21 | +7.08 | −0.12 |
| placebo-matched | target effect | +7.97 | +7.93 | −0.05 |
| placebo-matched | pure semantic effect | +8.55 | +8.50 | −0.05 |

把 200 个已审计输出的自动标签替换成人工标签后，full-cohort 主效应只变化 −0.12 pp，placebo-matched pure semantic effect 只变化 −0.05 pp。该结果支持数值稳定性，但仍是局部扰动检查，不是总体偏差校正。

## 4. Workstream B：Predictive Analysis

预测任务使用按 `problem_id` 分组的 5-fold cross-validation、fold-local preprocessing 和 5,000 次 paired bootstrap；Model E 使用四次 Control 运行的稳定性，属于 oracle/extra-compute upper bound。

### B.1 Danger deletion

样本为 1,353 runs，其中 204 个正例（15.1%）。

| Model | AUROC | AUPRC | Brier | ECE |
|---|---:|---:|---:|---:|
| A：Rating-only | 0.423 [0.355, 0.491] | 0.139 [0.097, 0.178] | 0.254 | 0.346 |
| B：Type-only | 0.551 [0.502, 0.603] | 0.208 [0.170, 0.245] | 0.249 | 0.344 |
| C：Rating + Type | 0.431 [0.394, 0.468] | 0.140 [0.099, 0.188] | 0.257 | 0.345 |
| D：Static context | 0.512 [0.486, 0.543] | 0.160 [0.119, 0.208] | 0.249 | 0.334 |
| E：Trajectory state（oracle） | 0.585 [0.527, 0.653] | 0.263 [0.185, 0.341] | 0.228 | 0.308 |

在 danger deletion 任务中，轨迹状态模型 E 的 AUPRC 高于静态上下文模型 D **+0.103**（95% CI：+0.048 至 +0.160），但它需要额外的四次 Control 运行，不能直接当作零成本 pruning policy。

### B.2 Benefit deletion

样本为 1,047 runs，其中 377 个正例（36.0%）。

| Model | AUROC | AUPRC | Brier | ECE |
|---|---:|---:|---:|---:|
| A：Rating-only | 0.520 [0.472, 0.568] | 0.432 [0.371, 0.488] | 0.251 | 0.137 |
| B：Type-only | 0.503 [0.462, 0.549] | 0.407 [0.362, 0.452] | 0.251 | 0.135 |
| C：Rating + Type | 0.484 [0.444, 0.536] | 0.380 [0.324, 0.433] | 0.255 | 0.130 |
| D：Static context | 0.566 [0.505, 0.609] | 0.412 [0.362, 0.462] | 0.252 | 0.169 |
| E：Trajectory state（oracle） | 0.599 [0.574, 0.618] | 0.478 [0.410, 0.547] | 0.246 | 0.176 |

在 benefit deletion 任务中，E 相对 D 的 AUPRC 增量为 **+0.065**（95% CI：+0.033 至 +0.091），说明 trajectory state 对预测有增益；这些是预测比较，不是因果效应，也不等于已经验证了部署规则。

## 5. Workstream C：Step-Level Stability

| 稳定性类别 | Steps | Share |
|---|---:|---:|
| Strongly beneficial | 99 | 16.5% |
| Weakly beneficial | 33 | 5.5% |
| Strongly harmful | 57 | 9.5% |
| Weakly harmful | 25 | 4.2% |
| Mixed / unstable | 9 | 1.5% |
| Stable no-change | 377 | 62.8% |

绝大多数步骤（62.8%）在四次 paired runs 中表现为 stable no-change；但仍有 99 个 strongly beneficial 和 57 个 strongly harmful。`rating=-1 × Harmful` 的 178 个步骤中，51 个（28.7%）strongly beneficial，说明平均收益不能替代 trajectory-level 风险检查。另有 298 个步骤 Control 4/4 correct，其中 54 个（18.1%）至少出现一次“纯伤害且无恢复”，因此部署前仍需要 rollback/trajectory-state validation。

## 6. Workstream D：Placebo Eligibility and Selection-Bias Audit

| 项目 | 数值 |
|---|---:|
| Eligible steps | 511 |
| Skipped steps | 89 |
| 最大绝对 SMD | 0.298（step position） |
| Balance threshold | absolute SMD ≥ 0.25 |
| Effect-difference threshold | absolute raw-effect difference ≥ 5 pp |
| Resampling/permutation | 5,000 replicates |

至少一个预设平衡或效应差异阈值被触发，所以 placebo 结论必须明确限制在 511-step matched cohort；89 个 skipped steps 没有可被审慎填补的 placebo 结果。

### D.1 Eligible 与 skipped 的结果差异

| Metric | Eligible | Skipped | Eligible − skipped | 95% CI |
|---|---:|---:|---:|---:|
| control accuracy | 55.28% | 62.64% | −7.36 pp | [−17.51, +3.17] |
| target accuracy | 63.26% | 65.45% | −2.19 pp | [−12.35, +7.91] |
| raw target effect | +7.97 pp | +2.81 pp | +5.17 pp | [−3.77, +13.77] |
| harm rate | 15.49% | 13.00% | +2.48 pp | [−5.78, +10.43] |
| recovery rate | 36.98% | 29.32% | +7.66 pp | [−8.32, +22.48] |
| mean token change | −22.15 | 39.64 | −61.78 tokens | [−125.69, −0.98] |

Eligible cohort 的 raw target effect 比 skipped cohort 高 5.17 pp，但区间跨零；同时 token change 差异较大。因此 placebo matched 分解可作为目标特异性诊断，不能当作全 600-step cohort 的无偏总体估计。

## 7. Workstream E：Qualitative Case Study

| Case family | Cases | 典型结果 |
|---|---:|---|
| Negative Anchor | 3 | Target +100 pp；Placebo +0 pp；Pure +100 pp |
| Generic Restart | 2 | Target +100 pp；Placebo +100 pp；Pure +0 pp |
| Stable-correct Harmed | 2 | Target −100 pp；Placebo +0 pp；Pure −100 pp |
| High-rated / Redundant Ambiguity | 1 | Target −100 pp；Placebo +0 pp；Pure −100 pp |
| **合计** | **8** | **8/8 通过家族特异性验证规则** |

8 个案例的 78 个 Control、Target-deletion 和可用 Placebo 输出均已完成直接人工标注，且 8/8 通过预先固定的 family-specific transition rule。案例用于说明机制，不用于估计总体频率；其中 Generic Restart 展示了 raw gain 可能来自重新开始而非目标语义删除，Stable-correct Harmed 与高评分冗余案例则说明删除安全性不能由单一评分或“Redundant”标签保证。

## 8. Workstream F：最终统计与一致性

### F.1 Full-cohort target deletion

| Group | Steps | Pairs | Accuracy change (pp) | 95% CI (pp) | Harm rate | Recovery rate |
|---|---:|---:|---:|---:|---:|---:|
| Overall | 600 | 2400 | **+7.21** | [+3.88, +10.58] | 15.08% | 36.01% |
| rating=-1 | 200 | 800 | **+22.00** | [+15.41, +28.42] | 14.86% | 38.66% |
| rating=0 | 200 | 800 | +0.25 | [−5.41, +5.90] | 17.05% | 32.73% |
| rating=1 | 200 | 800 | −0.62 | [−5.54, +4.21] | 13.40% | 33.49% |
| step_type=Essential | 165 | 660 | −1.21 | [−7.24, +4.78] | 17.84% | 29.06% |
| step_type=Redundant | 201 | 804 | +1.12 | [−3.87, +6.06] | 11.95% | 36.24% |
| step_type=Harmful | 234 | 936 | **+18.38** | [+12.28, +24.44] | 17.01% | 38.66% |
| rating=-1 × Harmful | 178 | 712 | **+23.31** | [+16.57, +30.24] | 13.79% | 38.11% |

总体 +7.21 pp 的收益主要由 `rating=-1` 和 `Harmful` 子组驱动；`Essential` 和 `Redundant` 的总体区间均跨零，所以不能把“删除”泛化为所有步骤的安全操作。表中 step type 使用原始 `step_type_analysis` 标签；图 2 使用 human-calibrated 标签，两者有 164/600 个步骤不同，不能混用分母。

### F.2 Placebo-matched decomposition

| Group | Steps | Placebo runs | Target effect (pp) | Placebo effect (pp) | Pure semantic effect (pp, 95% CI) |
|---|---:|---:|---:|---:|---:|
| Overall | 511 | 1514 | +7.97 | −0.57 | **+8.55 ([+4.83, +12.17])** |
| rating=-1 | 169 | 458 | +22.78 | +9.47 | **+13.31 ([+6.71, +19.53])** |
| step_type=Harmful | 201 | 563 | +18.41 | +3.57 | **+14.84 ([+8.83, +20.61])** |
| rating=-1 × Harmful | 151 | 399 | +23.84 | +9.99 | **+13.85 ([+6.95, +20.64])** |

在可匹配的 511 steps 内，target deletion 的提升大于 placebo deletion，整体纯语义效应为 +8.55 pp。`rating=-1 × Harmful` 的纯语义效应为 +13.85 pp，但该表仍受 D 节选择性限制，不能替代 full-cohort 主效应。

### F.3 技术一致性与冻结结论

| 检查 | 状态 |
|---|---|
| Full cohort steps/pairs | PASS（600 / 2400） |
| Retained transition partition | PASS（670 / 1,149 / 204 / 377） |
| Placebo denominators | PASS（511 steps / 1,514 runs） |
| Analysis-type denominators | PASS（Essential 165 / Redundant 201 / Harmful 234） |
| Pure semantic identity | PASS（Target − Placebo） |
| CI ordering and bootstrap count | PASS（5,000） |
| Qualitative verification | PASS（8 cases / 78 outputs） |
| Single numeric source | PASS |
| Technical consistency | **PASS** |
| Final analysis status | **READY_TO_FREEZE** |

所有分母、符号、队列边界、CI 顺序、qualitative 输出数和单一数值源检查均通过。正式的第二位人工数值签字尚未记录；当前已完成独立计算复核和图形视觉检查。因此 `READY_TO_FREEZE` 表示计算结果一致且可冻结，不表示已经完成额外的第二人工签字。

## 9. 结论与报告边界

1. 在当前数据和预设口径下，目标步骤删除在 full cohort 上显示出正向总体变化，且效果集中在低评分、Harmful 相关步骤。
2. Judge Audit 通过 hard-stop，但审查等级是 `PASS_WITH_SENSITIVITY`；不得宣称自动 judge 与人工 adjudication 等价，也不得忽略敏感性说明。
3. Placebo 分解支持 511-step matched cohort 中存在 target-specific signal，但由于 eligibility/selection audit 触发阈值，不能把该分解无条件外推到 89 个 skipped steps。
4. Predictive 模型结果是预测性能，不是因果识别；Model E 使用额外 Control 运行，不能直接视为零成本部署方案。
5. Qualitative cases 说明了负锚点、generic restart、稳定正确被伤害和高评分冗余歧义等机制，但不提供总体发生率估计。
6. 这些结果支持继续进行受控、带 rollback 的验证；不支持仅凭评分或静态标签自动删除全部步骤。

## 10. 主要输出文件

- `judge_audit_adjudicated.csv`：最终 Judge Audit 真值源。
- `judge_audit_report.md`：审计 gate、条件诊断、转移审计和敏感性分析。
- `judge_audit_label_substitution_sensitivity.csv`：局部标签替换敏感性结果。
- `final_tables.md`、`appendix_tables.md`：Workstream F 主表与附录表。
- `predictive_analysis_report.md`：Workstream B 预测结果。
- `step_stability_report.md`：Workstream C 稳定性结果。
- `placebo_eligibility_audit.md`：Workstream D 匹配资格与选择偏差审计。
- `qualitative_cases.md`、`qualitative_cases_verified.csv`：Workstream E 已验证案例及逐输出标签。
- `workstream_F_consistency_audit.md`：Workstream F 技术一致性审计。
- `numbers_for_paper.json`：冻结后的单一数值源与 provenance 元数据。

