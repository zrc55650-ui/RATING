---
title: "PRM Scores Are Not Pruning Policies"
subtitle: "2026 年 8 月 ARR 最终执行版 Research Proposal 与实施计划"
author: "项目内部执行文档"
date: "2026-07-22"
lang: zh-CN
toc: true
toc-depth: 3
numbersections: true
geometry: margin=0.78in
fontsize: 10pt
mainfont: "Noto Serif CJK SC"
sansfont: "Noto Sans CJK SC"
monofont: "Noto Sans Mono CJK SC"
colorlinks: true
linkcolor: blue
urlcolor: blue
header-includes:
  - |
    \usepackage{booktabs}
    \usepackage{longtable}
    \usepackage{array}
    \usepackage{xcolor}
    \usepackage{enumitem}
    \setlist{nosep,leftmargin=*}
    \renewcommand{\arraystretch}{1.15}
---

# 文档目的

本文档是项目的**最终执行版 RP**。它不再重新讨论是否应该做 placebo，也不再扩张研究范围，而是以现有结论为起点，把 2026 年 8 月 ARR 投稿前剩余的全部工作拆成可以直接执行、检查和交付的任务。

当前已经完成：

- 600 个 target steps、2,400 个 Control/Deletion paired observations；
- 511 个可匹配步骤上的 placebo experiment，共 1,514 次 placebo runs；
- target-step-level cluster bootstrap，5,000 replicates；
- rating、step type、rating x type、位置、步长、prefix 长度和 Control stability 的分层分析；
- full cohort、retained cohort 和 placebo-matched cohort 三套统计口径的区分。

## 2026-07-23 Pre-Audit 执行状态

在不使用人工 Audit 标签的前提下，以下工作已经完成：

1. `master_step_table.csv`（600 rows）和 `master_run_table.csv`（6,314 rows）；
2. 200-output blind Audit 抽样、A/B 表及本地 HTML 标注界面；
3. Rating-only 与 contribution-aware predictive analysis；
4. Step-level stability analysis；
5. Placebo eligible 511 vs skipped 89 的 selection-bias audit；
6. 32 个 qualitative case candidates 的固定规则筛选；
7. `make_all_results.py`、`numbers_for_paper.json`、pre-Audit 主表和 8 张 SVG/PDF 图。

新增分析结论：

- Predictive analysis 以 `problem_id` 做 5-fold grouped CV。静态 Rating + Type
  并未稳定超过 rating-only；使用 4 次 Control stability 的 Model E 在 danger 和
  benefit 任务上均有增益，但这是 extra-compute/oracle 结果，不能写成零成本部署模型。
- 预先固定的四次运行稳定性规则得到：99/600 Strongly beneficial、57/600
  Strongly harmful、9/600 Mixed/unstable；`rating=-1 × Harmful` 中 51/178
  为 Strongly beneficial。
- Placebo eligibility audit 显示 position 最大 level-wise SMD=0.298，prefix
  length SMD=0.268；eligible-minus-skipped raw target effect 为 +5.17 pp，
  95% CI [-3.77, 13.77]。因此 placebo 结论必须严格限定为 511-step matched
  cohort，不能无条件推广到全部 600 steps。
- Qualitative candidates 已自动选取，但在 Judge Audit 完成前不能称为
  human-verified cases。

当前仍未完成且必须纳入本执行计划：

1. Judge Audit 的人工标签、agreement、FP/FN、condition bias 与 sensitivity；
2. Qualitative cases 的人工 transition 验证和最终 8 例冻结；
3. 四页 ARR short paper 写作与 Audit 后最终数字替换；
4. 匿名代码、数据说明、Responsible NLP checklist 与提交检查。

---

# 1. 已冻结的论文结论

以下结论已经由全量 cluster bootstrap 和 placebo analysis 支持，后续实验的目标是验证其 soundness、补齐解释与呈现，而不是随意更换主故事。

## 1.1 PRM rating 有信息，但不是 pruning policy

Human-calibrated annotation 中：

- Cramer's \(V=0.528\)；
- 65.5% 为 diagonal cases；
- 34.5% 为 off-diagonal cases。

因此，PRM rating 与 Essential/Redundant/Harmful contribution 明显相关，但两者不是同一个 construct。PRM 可以用于 ranking，却不能直接转化为删除决定。

## 1.2 删除收益集中于 low-rated harmful steps

全量 600-step cluster bootstrap：

| Group | Steps | Accuracy change (pp) | 95% CI |
|---|---:|---:|---:|
| Overall | 600 | +7.21 | [3.88, 10.58] |
| rating = -1 | 200 | +22.00 | [15.41, 28.42] |
| Harmful | 234 | +18.38 | [12.28, 24.44] |
| rating = -1 x Harmful | 178 | +23.31 | [16.57, 30.24] |
| rating = 0 | 200 | +0.25 | [-5.41, 5.90] |
| rating = 1 | 200 | -0.63 | [-5.54, 4.21] |
| Essential | 165 | -1.21 | [-7.24, 4.78] |
| Redundant | 201 | +1.12 | [-3.87, 6.06] |

聚类校正后，稳定的正向平均效应主要集中于 rating = -1、Harmful 及其交叉组。

## 1.3 Negative-anchor effect 在 placebo 校正后仍成立

在 511 个 placebo-eligible steps 上：

| Group | Target effect | Placebo effect | Pure semantic effect |
|---|---:|---:|---:|
| Overall | +7.97 | -0.57 | +8.55 [4.83, 12.17] |
| rating = -1 | +22.78 | +9.47 | +13.31 [6.71, 19.53] |
| Harmful | +18.41 | +3.57 | +14.84 [8.83, 20.61] |
| rating = -1 x Harmful | +23.84 | +9.99 | +13.85 [6.95, 20.64] |

所以论文应将 low-rated harmful steps 的核心量级写成**placebo-corrected 约 +14 pp**，而不是只报告 raw +23 pp。

## 1.4 Restart effect 真实存在，但不是总体解释

总体 placebo effect 为 -0.57 pp，95% CI 跨 0，因此通用 restart 不能解释总体 target-deletion gain。

但在 rating = -1 与 rating = -1 x Harmful 内，placebo effect 约为 +9.5 至 +10 pp，约占 raw gain 的 42%。论文必须明确：

$$
\text{Raw deletion gain}
=
\text{generic restart component}
+
\text{target-specific semantic component}.
$$

这同时形成一个方法论 finding：**没有 placebo control 的 deletion study 可能高估 target-specific contribution。**

## 1.5 Baseline solvability 是删除风险的重要状态变量

- Control 4/4 全错：删除后 +33.37 pp [27.52, 39.20]；
- Control 4/4 全对：删除后 -12.08 pp [-15.49, -8.91]。

这两个极端组有机械边界，不能解释为纯因果异质性；但它们清楚说明，删除的效用依赖当前 trajectory state。任何只看 step rating、不看当前轨迹是否稳定正确的 pruning rule 都会制造风险。

## 1.6 Token efficiency 不再作为主贡献

聚类校正后的 mean token change 为 12.98，95% CI [-19.65, 45.56]，CI 跨 0；此前 median token saving 为 -3，且 Deletion 更长的 pairs 多于更短的 pairs。

论文只保留以下 secondary observation：

> 删除 reasoning step 不保证生成更短，因为模型可能重新生成更长的替代路径。

---

# 2. Claim 边界与非目标

## 2.1 可以写进 Abstract 的主张

1. PRM rating 与 step contribution 相关但不等价；
2. 删除收益集中于 low-rated harmful steps；
3. placebo 校正后仍存在约 +14 pp target-specific semantic effect；
4. 低评分组内约四成 raw gain 来自 restart component；
5. 稳定正确轨迹上的删除平均有害，因此 PRM score 不是 standalone pruning policy。

## 2.2 只能作为描述性或 appendix 结果

- rating = 0 x Essential 的方向性风险：全量效应 -6.10 pp [-20.27, 7.69]，样本只有 41 steps；
- rating = 1 x Redundant 的可删除性：平均 effect 与 token saving 都不显著；
- position、step length、prefix length 的异质性：目前是描述性关联，不是因果机制。

## 2.3 明确不能声称

- deletion 带来显著 token efficiency；
- 所有低分步骤都应该删除；
- 所有 Redundant steps 都安全；
- rating = 0 x Essential 已被统计显著证明危险；
- rating = 0/1 的正 pure semantic effect 表示删除它们会提升准确率；
- 511-step placebo cohort 能无条件代表全部 600 steps；
- 已经训练出或验证了可部署的新 verifier；
- 结论已跨模型、跨数据集普遍成立。

## 2.4 截止前不再做的工作

- 新 verifier 训练；
- 多 benchmark 扩展；
- 第二 generator 的完整复现；
- 多步连续 pruning；
- RL 或在线 rollback system；
- 为了增加表格而加入未经预注册的复杂 baseline。

---

# 3. 投稿目标与最终交付物

## 3.1 ARR 时间与格式

2026 年 8 月 ARR submission deadline 为 **8 月 3 日**，所有作者 reviewer registration deadline 为 **8 月 5 日**。该 cycle 当前对应的 participating venue 包括 EACL 2027。ARR short paper 为最多 4 页正文，Limitations section 必须单独存在，且不计入正文页数。[ARR Dates and Venues](https://aclrollingreview.org/dates)；[ARR Call for Papers](https://aclrollingreview.org/cfp)。

## 3.2 最终必须交付

| Deliverable | 最终文件 | 完成标准 |
|---|---|---|
| Judge audit | `judge_audit_200_outputs.csv` + report | 有人类标签、agreement、FP/FN、condition bias |
| Predictive analysis | `predictive_analysis.{csv,md,pdf}` | grouped CV，无 step leakage，含 AUROC/AUPRC/calibration |
| Stability analysis | `step_stability.{csv,md}` | 600-step aggregation、明确类别规则、分组结果 |
| Selection-bias audit | `placebo_eligibility_audit.{csv,md}` | 比较 511 eligible 与 89 skipped |
| Qualitative cases | `qualitative_cases.md` | 6-9 个，按固定规则、人工复核 |
| Master statistics | `make_all_results.py` 及输出 | 一条命令生成全部主表和主图 |
| Paper | Anonymous ARR PDF + source | 4 页正文、Limitations、References、Checklist |
| Anonymous artifact | repo / zip | 无姓名、路径、非匿名链接和环境秘密 |

## 3.3 成功标准

本项目的成功不是训练出新模型，而是完成一篇范围清楚、统计严谨、可复现的 empirical short paper。投稿前至少满足：

- judge audit 不显示严重或 condition-specific bias；
- placebo-corrected negative-anchor effect 在人工校验后方向不变；
- 所有主数字由单一脚本产生；
- full、retained、placebo-matched 三种分母绝不混用；
- 论文不再把 token efficiency 写成主贡献；
- 所有 claim 都能在主表、主图或 appendix 中找到直接证据。

---

# 4. 数据与单一事实源

## 4.1 现有核心文件

| 内容 | 文件 |
|---|---|
| 原始 2,400 paired outcomes | `qwen3-8b_deletion_pairs.csv` |
| 全量 generation records | `qwen_deletion_generations.jsonl` |
| 全量 cluster bootstrap | `qwen3-8b_cluster_bootstrap_metrics_5000.{csv,md,html}` |
| 分层 bootstrap | `qwen3-8b_cluster_bootstrap_stratified_5000.{csv,md,html}` |
| Placebo effect decomposition | `qwen3-8b_placebo_effects_5000.{csv,md,html}` |
| Placebo step-level effects | `qwen3-8b_placebo_effects_5000_step_effects.csv` |
| Placebo run-level outcomes | `qwen3-8b_placebo_effects_5000_placebo_runs.csv` |
| Placebo selection | `qwen3-8b_placebo_selection.jsonl` |
| Placebo selection summary | `qwen3-8b_placebo_selection_summary.json` |
| Human-calibrated labels | `human_calibrated_600_comparison.csv` |

## 4.2 建立 master table

首先生成一个 `master_step_table.csv`，每行一个 target step，至少包含：

- `step_id`；
- `problem_id` / `trajectory_id`；
- `prm_rating`；
- `step_type_initial`；
- `step_type_human_calibrated`；
- `position_bin`；
- `target_tokens`；
- `prefix_tokens`；
- 4 次 Control correctness；
- 4 次 Target deletion correctness；
- Wrong -> Correct count；
- Correct -> Wrong count；
- net correctness gain；
- Control stability；
- placebo eligibility；
- placebo step id、长度、位置；
- placebo correctness；
- target effect、placebo effect、pure semantic effect；
- completion status counts；
- token statistics。

所有后续分析只从 master table 或明确的 run-level long table 读取，禁止每个脚本单独重新拼接原始文件。

## 4.3 Run-level long table

生成 `master_run_table.csv`，每行对应一个 step-run-condition：

- `step_id`；
- `run_id`；
- `condition` in {control, target_delete, placebo_delete}；
- `output_id`；
- `final_answer_raw`；
- `final_answer_normalized`；
- `judge_label`；
- `human_label`；
- `visible_tokens`；
- `completion_status`；
- `seed` / generation metadata。

该表用于 judge audit、grouped CV 和最终 reproducibility check。

---

# 5. Workstream A：Judge Audit（最高优先级）

## 5.1 目的

当前 generator 与 judge 都使用 Qwen3-8B。审稿人会质疑：

- self-preference；
- 长度或格式偏差；
- 数学等价误判；
- Control、Target、Placebo 条件间的 asymmetric error；
- Wrong -> Correct / Correct -> Wrong 是否由 judge 噪声造成。

Judge audit 的目标不是简单给出一个总体 agreement，而是检查**主结论所依赖的 discordant transitions 是否可靠，以及 judge error 是否随 condition、rating 或 output length 系统变化。**

## 5.2 精确抽样：200 个 distinct outputs

采用固定 seed，并保存抽样清单。尽量去重；若同一 output 命中多个 stratum，仅保留一次并从该 stratum 补抽。

| Stratum | Case 数 | Output 数 | 抽样规则 |
|---|---:|---:|---|
| Wrong -> Correct | 25 pairs | 50 | rating/type/position 尽量平衡 |
| Correct -> Wrong | 25 pairs | 50 | 强制覆盖 dangerous deletions |
| Target vs Placebo discordant | 20 triads | 60 | Control/Target/Placebo 三个输出全审 |
| Concordant random controls | 10 pairs | 20 | 5 Still Correct + 5 Still Wrong |
| Abnormal / ambiguous | 20 singles | 20 | Cannot Continue、Logical Break、复杂等价、长输出 |
| **总计** |  | **200** |  |

若 triad 与 transition stratum 重叠，则以 200 个 distinct outputs 为硬上限，按以下优先级补足：

1. Correct -> Wrong；
2. Wrong -> Correct；
3. Target vs Placebo discordant；
4. abnormal；
5. random concordant。

## 5.3 Blind annotation 界面

Annotator 只能看到：

- question；
- ground-truth answer；
- 当前 candidate output；
- 必要时的 answer-extraction instruction。

Annotator不能看到：

- condition 名称；
- PRM rating；
- Step Type；
- 当前 judge label；
- 该 output 与其他 output 的配对关系。

每个 output 的标签：

- `Correct`；
- `Incorrect`；
- `Ambiguous / insufficient information`；
- `No valid final answer`。

同时记录：

- 人工抽取的 normalized final answer；
- 一句话判定理由；
- 是否需要 symbolic tool / calculator；
- annotator confidence：high / medium / low。

## 5.4 Annotator 配置

首选：两名 annotators 独立标注全部 200 outputs，分歧由第三人或项目负责人 adjudicate。

时间不足的最低方案：

- Annotator A 标注全部 200；
- Annotator B 独立标注 80 个，其中优先覆盖全部 50 个 Correct -> Wrong outputs 和 30 个随机/ambiguous outputs；
- 所有 A/B 分歧由负责人 adjudicate。

## 5.5 评价指标

必须报告：

- Judge-human agreement；
- Cohen's kappa（若有双人覆盖）；
- judge precision / recall / F1 for `Correct`；
- false-positive rate：judge correct、human incorrect；
- false-negative rate：judge incorrect、human correct；
- disagreement by condition；
- disagreement by transition type；
- disagreement by rating；
- disagreement by output-length quartile；
- pair-level transition agreement：judge 与 human 是否给出相同的 W->C / C->W / SC / SW。

## 5.6 决策门槛

| Audit 结果 | 行动 |
|---|---|
| Agreement >= 95%，且任意 condition 的 error-rate 差异 < 3 pp | 保留现有 judge 结果，主文报告 audit |
| Agreement 90%-95%，或 condition bias 3-5 pp | 对全部主结论相关 discordant pairs 做二次规则/人工复核；主文加入 sensitivity result |
| Agreement < 90%，或 condition bias > 5 pp | 不允许直接提交现有主数字；使用 independent judge、symbolic evaluator 或扩展人工判定重新评估关键 subset |
| C->W 中 judge error 明显高于 W->C | 重新计算 harm rate 和 safe-deletion claims，不能只校正总体 accuracy |

## 5.7 输出文件

- `judge_audit_sampling_manifest.csv`；
- `judge_audit_blinded_sheet_A.csv`；
- `judge_audit_blinded_sheet_B.csv`；
- `judge_audit_adjudicated.csv`；
- `judge_audit_report.md`；
- `judge_audit_confusion_matrix.pdf`。

## 5.8 人员分工

- 学生：生成 manifest、准备 blind sheet、完成第一轮标注、统计；
- 指导者：检查抽样逻辑、完成第二标注或 adjudication、决定是否触发重评；
- 共同：审阅所有 C->W disagreements。

---

# 6. Workstream B：Predictive Analysis

## 6.1 研究目标

检验 Step Type 和 trajectory-state 信息是否提供超出 PRM rating 的 deletion-outcome prediction。该分析不是训练新 verifier，而是用简单、可解释模型证明：**rating-only policy 缺失哪些信息。**

## 6.2 两个独立预测任务

### Dangerous deletion

只在 Control 正确的 run 上定义：

$$
Y_{danger}=\mathbb{1}[\text{Target deletion is wrong}].
$$

这直接预测 Correct -> Wrong 风险。

### Beneficial deletion

只在 Control 错误的 run 上定义：

$$
Y_{benefit}=\mathbb{1}[\text{Target deletion is correct}].
$$

这直接预测 Wrong -> Correct recovery。

不要将 Still Wrong 当成“安全删除”，也不要把两个任务合成单一 removable label。

## 6.3 特征组

| Model | Features | 解释 |
|---|---|---|
| A: Rating-only | PRM rating | 模拟最简单 PRM pruning rule |
| B: Type-only | Essential/Redundant/Harmful | 测试 contribution label 本身 |
| C: Rating + Type | rating、type、interaction | 检验两类信号互补性 |
| D: Static context | C + position、target length、prefix length | 加入无需额外 sampling 的信息 |
| E: Trajectory state | D + Control stability | 测试当前轨迹状态的额外价值 |

注意：Control stability 使用 4 次 Control 结果，属于 oracle/extra-compute state feature，不能与零成本 static model 混为一谈。论文中应明确 Model E 代表“若允许少量状态估计”的 upper-bound analysis。

## 6.4 数据切分

- 使用 5-fold grouped cross-validation；
- group 优先使用 `problem_id`，避免同一问题的多个 step 跨 train/test；
- 若 problem_id 不完整，至少按 `step_id` 分组，保证 4 次 runs 不跨 fold；
- 所有预处理仅在 training fold 拟合；
- 类别不平衡使用 class weight，不用 SMOTE；
- 固定 seed，并保存 fold assignment。

## 6.5 模型

主模型只使用：

- Logistic regression；
- 可选一个 shallow gradient-boosted tree 作为 nonlinear sensitivity check。

short paper 主文不需要复杂模型。若非线性模型提高很小，只保留 logistic regression。

## 6.6 指标

每个任务分别报告：

- AUROC；
- AUPRC；
- Brier score；
- expected calibration error；
- risk-coverage curve；
- 在 90%、95% precision 下的 coverage；
- fold-level mean 与 bootstrap 95% CI。

危险删除任务优先看 AUPRC、specificity 和 risk-coverage，而不是只看 AUROC。

## 6.7 关键比较

主比较：

1. C vs A：Step Type 是否超越 rating-only；
2. D vs C：位置/长度是否增加价值；
3. E vs D：trajectory state 是否是最强增量；
4. Benefit 与 Danger 是否需要不同模型。

## 6.8 纳入论文的门槛

| 结果 | 处理 |
|---|---|
| C 或 E 相对 A 的 AUPRC 提升 >= 0.03，且 bootstrap CI 不跨 0 | 主文或主表 |
| 仅有小幅或不稳定提升 | appendix，作为 exploratory analysis |
| Rating-only 已与完整模型相当 | 诚实报告，不强行解释互补性；论文主线仍依赖 intervention results |

## 6.9 输出

- `predictive_fold_assignments.csv`；
- `predictive_run_level_dataset.csv`；
- `predictive_metrics.csv`；
- `risk_coverage_danger.pdf`；
- `risk_coverage_benefit.pdf`；
- `predictive_analysis_report.md`。

---

# 7. Workstream C：Step-Level Stability Analysis

## 7.1 目的

平均 treatment effect 不能说明一个具体 step 是否稳定可删。每个 step 已有 4 次 runs，可用于区分稳定收益、稳定伤害和 stochastic instability。

## 7.2 Step-level 统计量

对每个 step \(i\)：

- \(n_{WC}\)：Wrong -> Correct 次数；
- \(n_{CW}\)：Correct -> Wrong 次数；
- \(n_{SC}\)：Still Correct 次数；
- \(n_{SW}\)：Still Wrong 次数；
- net gain：\((n_{WC}-n_{CW})/4\)；
- danger rate：\(n_{CW}/n_{ControlCorrect}\)；
- recovery rate：\(n_{WC}/n_{ControlWrong}\)；
- sign conflict：是否同时出现 W->C 和 C->W。

## 7.3 预先固定的类别

| 类别 | 定义 |
|---|---|
| Strongly beneficial | \(n_{WC} \ge 2\) 且 \(n_{CW}=0\) |
| Weakly beneficial | \(n_{WC}=1\) 且 \(n_{CW}=0\) |
| Strongly harmful | \(n_{CW} \ge 2\) 且 \(n_{WC}=0\) |
| Weakly harmful | \(n_{CW}=1\) 且 \(n_{WC}=0\) |
| Mixed / unstable | \(n_{WC}>0\) 且 \(n_{CW}>0\) |
| Stable no-change | \(n_{WC}=n_{CW}=0\) |

类别规则必须在看分组结果前冻结，避免事后改阈值。

## 7.4 分析内容

- 各稳定类别总体占比；
- 按 rating、Step Type、rating x type 分布；
- placebo pure semantic effect 在稳定类别中的差异；
- `Mixed / unstable` 是否集中在特定位置、长度或低 confidence annotation；
- rating = -1 x Harmful 中有多少是 consistently beneficial，而不是只靠少数 run；
- Control 4/4 correct 组中 dangerous deletion 的 step-level 分布。

## 7.5 主文表述规则

- 若 rating = -1 x Harmful 中 Strongly beneficial 占比明显高于其他组，可作为机制支持；
- 若大多数 effect 来自 Weakly beneficial 或 Mixed steps，应弱化“稳定 anchor”表述；
- 不把 4 次 runs 当成足够估计个体真实概率，明确 stability 只是 empirical consistency。

## 7.6 输出

- `step_stability_labels.csv`；
- `step_stability_by_group.csv`；
- `step_stability_heatmap.pdf`；
- `step_stability_report.md`。

---

# 8. Workstream D：Placebo Eligibility 与 Selection Bias

## 8.1 问题

Placebo analysis 只覆盖 511/600 steps，89 个 steps 因找不到 0.8-1.2 倍长度的匹配 step 而被跳过。若 skipped steps 系统性更短、更长、更靠前或 deletion effect 不同，placebo conclusion 只能适用于 matched cohort。

## 8.2 比较变量

比较 Eligible 511 与 Skipped 89：

- PRM rating；
- Step Type；
- rating x type；
- early/middle/late；
- target-step length；
- prefix length；
- Control accuracy；
- Target deletion accuracy；
- raw target effect；
- C->W harm rate；
- W->C recovery rate；
- completion status；
- token change。

## 8.3 统计方法

- 类别变量：比例差、chi-square 或 Fisher exact；
- 连续变量：median/IQR、standardized mean difference、KS 或 permutation test；
- effect difference：step-level cluster bootstrap；
- 重点报告 SMD，而不是只看 p-value。

## 8.4 判断标准

| 结果 | 论文处理 |
|---|---|
| 关键变量 SMD < 0.25，raw effect 差异 < 5 pp | 可称 matched cohort 与全体大体相似，但仍写 limitation |
| 任一关键变量 SMD >= 0.25 或 effect 差异 >= 5 pp | placebo conclusion 严格限定为 511-step matched cohort |
| skipped steps 主要是极端长度且 effect 明显不同 | appendix 展示；不临时设计新 placebo 补跑，除非只需很小成本 |

## 8.5 可选 sensitivity

若时间允许，可以用 propensity score / inverse probability weighting 做 descriptive sensitivity，但不能用它“补造”未观测 placebo outcomes。主结论仍基于 observed matched cohort。

## 8.6 输出

- `placebo_eligibility_step_table.csv`；
- `placebo_eligibility_balance.csv`；
- `placebo_eligibility_loveplot.pdf`；
- `placebo_eligibility_audit.md`。

---

# 9. Workstream E：Qualitative Case Study

## 9.1 目的

案例必须解释数字背后的机制，同时避免 cherry-picking。所有案例先通过 human judge audit，再按固定规则自动排序选取。

## 9.2 最终案例构成：建议 8 个

| 类别 | 数量 | 选择目标 |
|---|---:|---|
| Negative anchor | 3 | rating = -1 x Harmful，Target 恢复、Placebo 未恢复 |
| Generic restart | 2 | Target 与 Placebo 都改善，展示 raw gain 的非语义部分 |
| Stable-correct harmed | 2 | Control 4/4 correct，删除后至少 2 次错误 |
| High-rated / redundant ambiguity | 1 | 语义冗余但删除并非稳定安全 |

若需要覆盖 rating = 0 x Essential，可将最后一个替换为一个方向性危险案例，但必须标明“illustrative, not statistically conclusive”。

## 9.3 固定筛选规则

### Negative-anchor cases

满足：

- human-calibrated type = Harmful；
- rating = -1；
- \(n_{WC} \ge 2\)，\(n_{CW}=0\)；
- placebo 没有产生同等恢复；
- human audit 确认 transition；
- 在满足条件的样本中，按 pure semantic effect 降序，再按 target length 中位附近优先，固定 seed 打破并列。

### Generic-restart cases

满足 Target 与 Placebo 均把错误变正确，且两者 continuation 使用不同路径。按可读性和代表性排序，不选异常格式样本。

### Stable-correct harmed cases

Control 4/4 correct，Target deletion 至少 2/4 wrong，人工确认 target 包含后续依赖的信息。

## 9.4 每个案例的展示模板

1. Problem 简述；
2. Target step；
3. 为什么 PRM/Step Type 如此标注；
4. Control continuation 的关键片段；
5. Target-deletion continuation 的关键片段；
6. Placebo continuation（适用时）；
7. 人工判定；
8. 机制解释；
9. 不超过 2-4 行的 excerpt，完整输出放 appendix/artifact。

## 9.5 输出

- `qualitative_case_candidates.csv`；
- `qualitative_cases_verified.csv`；
- `qualitative_cases.md`；
- appendix-ready LaTeX table。

---

# 10. Workstream F：最终统计、主图与一致性检查

## 10.1 单一 master script

建立 `make_all_results.py`，固定：

- bootstrap replicates = 5,000；
- seeds；
- group definitions；
- denominator definitions；
- confidence-interval method；
- plot labels；
- rounding rules。

一条命令应生成：

- 主文所有表格；
- appendix 表格；
- 全部 figure source CSV；
- PDF/PNG figures；
- `numbers_for_paper.json`。

论文正文中的每个数字只允许从 `numbers_for_paper.json` 复制。

## 10.2 三种 cohort 的明确命名

| 名称 | N | 用途 |
|---|---:|---|
| Full cohort | 600 steps / 2,400 pairs | unconditional main effect |
| Retained cohort | 1,730 pairs | 至少一个 condition 正确的 diagnostic analysis |
| Placebo-matched cohort | 511 steps / 1,514 placebo runs | target-specific effect decomposition |

图表标题和 caption 必须写 cohort 与分母，禁止只写“accuracy”。

## 10.3 最终主图

### Figure 1：实验设计

Control、Target deletion、Placebo deletion 三条件流程图，并注明 Target/Control 各 4 runs、Placebo 每 step 1 run。

### Figure 2：PRM rating x Step Type heatmap

展示 diagonal association 与 34.5% off-diagonal。

### Figure 3：Effect decomposition（最重要）

对 Overall、rating = -1、Harmful、rating = -1 x Harmful 展示：

- Target effect；
- Placebo effect；
- Pure semantic effect；
- cluster-bootstrap 95% CI。

### Figure 4 或主表：State-dependent deletion risk

展示 Control stability strata 的 effect，并在 caption 中说明机械边界。

## 10.4 最终主表

- Table 1：Full cohort overall/rating/type effects；
- Table 2：Placebo decomposition；
- Table 3（可选）：Predictive models 或 judge audit。

short paper 页数不足时，Table 3 移 appendix。

## 10.5 数字审计

提交前两人独立检查：

- 分母；
- percentage point 与 percent；
- target/placebo sign；
- raw 与 corrected effect；
- initial 与 human-calibrated type；
- full 与 retained；
- step 数与 run 数；
- CI rounding 后是否仍与原值一致。

---

# 11. Workstream G：四页 Short Paper 写作计划

## 11.1 推荐标题

**PRM Scores Are Not Pruning Policies: A Counterfactual Study of Reasoning-Step Removability**

## 11.2 Abstract 的四层结构

1. Gap：PRM 评价 local correctness，但 pruning 需要 removability；
2. Protocol：600 PRM800K steps、2,400 paired continuations、511-step matched placebo；
3. Findings：34.5% off-diagonal；low-rated harmful placebo-corrected +14 pp；约四成 raw gain 是 restart；
4. Implication：PRM 是 ranking prior，不是 standalone deletion rule。

## 11.3 正文页面预算

### Page 1：Introduction

- correctness vs contribution；
- 为什么 deletion evaluation 需要 placebo；
- 3 个 contributions；
- 不在 Introduction 主打 token efficiency。

### Page 2：Method

- PRM800K sampling；
- annotation；
- Control/Target/Placebo；
- full vs matched cohort；
- cluster bootstrap；
- Figure 1。

### Page 3：Main Results

- association heatmap；
- full cohort effects；
- placebo decomposition Figure 3；
- negative-anchor finding。

### Page 4：Safety、State 与 Discussion

- Control stability；
- judge audit 简表；
- predictive analysis（若有效）；
- pruning design implication；
- conclusion。

## 11.4 Appendix / Supplement

- full annotation prompt；
- generation prompt；
- judge prompt；
- all run-level results；
- retained cohort tables；
- token analyses；
- stability tables；
- selection-bias audit；
- qualitative cases；
- Responsible NLP details；
- reproducibility checklist。

## 11.5 推荐 contributions 文案逻辑

1. 提出 matched counterfactual deletion audit，用于检验 PRM rating 是否适合 pruning；
2. 发现 PRM 与 contribution 强相关但非等价，删除收益集中于 low-rated harmful steps；
3. 使用 placebo 将 raw gain 分解为 restart 与 target-specific components；
4. 证明当前 trajectory state 对 deletion safety 至关重要。

---

# 12. Workstream H：Limitations、Responsible NLP 与风险

## 12.1 必须写入 Limitations

- 单一数据集 PRM800K；
- 主要 generator 为 Qwen3-8B；
- generator 与 judge 同模型家族；
- deletion 后重新生成，而不是固定 trace 的机械删除；
- placebo 是 length-matched operational baseline，不是严格纯长度 causal control；
- placebo 删除位置与 target 位置不完全相同；
- Placebo 每 step 只有 1 run，方差大于 Control/Target；
- placebo 只覆盖 511/600 steps；
- Essential/Redundant/Harmful 主要由 AI 在 human few-shot calibration 后标注；
- 4 runs 只能测 empirical consistency，不能精确估计 individual-step true effect；
- Control stability strata 存在 mechanical boundary；
- token 结果不稳定；
- 结论不能直接外推到在线推理或其他模型。

## 12.2 风险与使用边界

主要风险是读者把结果误用为“低 rating 自动删除”。论文必须明确：

- overall harm rate 仍约 15%；
- low-rated harmful 组也不是零风险；
- safe deployment 需要 validation 与 rollback；
- 本研究是 evaluator audit，不是生产 pruning system。

## 12.3 Responsible NLP checklist

ARR 要求在 submission form 填写 Responsible NLP Research checklist，并在论文中讨论 limitation、artifact、license、compute 和潜在风险。提交前检查：

- PRM800K 的引用、版本和 license；
- Qwen3-8B 的模型版本与 license；
- DeepSeek annotation model 的版本；
- generation 次数、参数、硬件和 approximate compute；
- human annotation 人数、流程、补偿或课程性质；
- 是否包含个人信息：本项目原则上不涉及；
- release artifact 的 intended use 和 license。

---

# 13. Workstream I：匿名化与可复现 Artifact

## 13.1 推荐目录结构

```
project/
  README.md
  LICENSE
  requirements.txt
  configs/
    generation.yaml
    bootstrap.yaml
    placebo.yaml
  data/
    README.md
    sample_ids.csv
    derived/
  scripts/
    build_master_tables.py
    run_cluster_bootstrap.py
    run_placebo_analysis.py
    run_predictive_analysis.py
    run_stability_analysis.py
    sample_judge_audit.py
    make_all_results.py
  prompts/
    annotation.txt
    generation.txt
    judge.txt
  results/
    tables/
    figures/
  paper/
    appendix_tables/
```

## 13.2 匿名化检查

- 删除作者姓名、学校、邮箱；
- 删除本地绝对路径；
- 删除 Git commit author metadata 或使用匿名镜像；
- 不使用可追踪下载者的 Dropbox 等链接；
- README 不提实验室、课程或导师；
- 清理 PDF metadata；
- 检查脚本中的 username、server host、API key；
- 若公开 repo，使用匿名 Git hosting，并测试无登录访问。

## 13.3 可复现最低标准

- 固定依赖版本；
- 所有 random seeds 记录；
- 提供 sample selection manifest；
- 提供 derived data 或生成 derived data 的脚本；
- 一条命令重建主表和主图；
- README 说明不能重发的原始模型 output 如何获取；
- 对受 license 限制的数据只发布 IDs 和 transformation scripts。

---

# 14. 人员分工

## 14.1 学生主责

- build master tables；
- judge-audit blind sheets 与第一轮标注；
- predictive-analysis data preparation；
- stability analysis；
- placebo eligibility audit；
- qualitative candidate extraction；
- figure 初稿；
- artifact README 与运行测试。

## 14.2 指导者主责

- judge second annotation / adjudication；
- 统计定义和 claim 边界；
- master-script review；
- qualitative final selection；
- Introduction、Discussion、Limitations；
- 最终数字审计和投稿决定。

## 14.3 共同完成

- C->W cases 复核；
- abstract；
- related work；
- internal review；
- anonymization；
- OpenReview submission 与 author registration。

若只有一名执行者，优先顺序仍为：Judge audit > master statistics > paper > selection/stability > predictive analysis。

---

# 15. 逐日实行计划

## 7 月 23 日：数据冻结与 Judge Audit 抽样

**必须产出：**

- `master_step_table.csv`；
- `master_run_table.csv`；
- `judge_audit_sampling_manifest.csv`；
- blind sheets。

**检查点：**

- 200 distinct outputs；
- stratum 数量正确；
- annotator 看不到 condition、rating、judge label；
- 手动检查 10 个样本是否能正常标注。

## 7 月 24 日：完成 Judge Audit

**必须产出：**

- 第一 annotator 全部标签；
- 第二 annotator overlap；
- adjudicated labels；
- agreement、FP/FN、condition bias。

**Gate 1：**

- 若 agreement < 90% 或 condition bias > 5 pp，立即暂停 predictive analysis，优先修正 evaluation；
- 若通过，则冻结 accuracy labels。

## 7 月 25 日：Predictive Analysis

**必须产出：**

- grouped folds；
- A-E 五组模型；
- danger 和 benefit 两任务；
- AUROC/AUPRC/calibration/risk-coverage；
- 是否进入主文的决定。

## 7 月 26 日：Stability 与 Placebo Selection Bias

**必须产出：**

- step stability labels；
- stability by rating/type；
- eligible vs skipped balance table；
- matched-cohort generalization 边界。

## 7 月 27 日：Qualitative Cases 与主图

**必须产出：**

- 8 个 verified cases；
- Figure 1 intervention diagram；
- Figure 2 heatmap；
- Figure 3 placebo decomposition；
- Control-stability figure/table。

## 7 月 28 日：完整英文初稿

**必须产出：**

- 4 页正文完整 draft；
- Limitations；
- References；
- Appendix 结构；
- 所有 placeholder 数字清零。

## 7 月 29 日：内部技术 Review

Review checklist：

- 是否误用 retained accuracy；
- 是否把 raw gain 当 semantic effect；
- 是否把 token 写成显著；
- 是否过度解释 Control stability；
- 是否明确 placebo 511-step selection；
- 是否报告 dangerous deletion。

## 7 月 30 日：Artifact 与 Appendix

**必须产出：**

- 匿名 repo/zip；
- prompts；
- sample IDs；
- master script；
- appendix tables；
- compute / license notes。

## 7 月 31 日：第二轮 Paper Review

- 非作者视角阅读；
- 删除所有不必要 claim；
- 压缩至 4 页；
- 检查图字号；
- 检查同一数字是否一致。

## 8 月 1 日：格式与 Responsible NLP

- ACL template；
- Limitations 标题；
- anonymity；
- Responsible NLP checklist；
- PDF metadata；
- citation completeness。

## 8 月 2 日：Final Freeze

- 运行 `make_all_results.py`；
- 重编 PDF；
- 两人逐项核对数字；
- 上传 OpenReview draft；
- 检查作者列表不可再改；
- 预览 supplement。

## 8 月 3 日：提交

- 提交 ARR；
- 保存 submission receipt；
- 将最终 PDF、source、artifact hash 归档。

## 8 月 5 日前

- 所有作者完成 ARR reviewer registration；
- 截图或记录完成状态。

---

# 16. Go / No-Go 决策门槛

## 16.1 可以按当前主故事提交

同时满足：

- Judge audit agreement >= 90%，没有 >5 pp condition bias；
- human-audited subset 中 negative-anchor effect 方向不变；
- placebo-corrected result 可由 master script 重建；
- 511 vs 89 selection-bias 被清楚限定；
- 主文没有 token-efficiency claim；
- anonymous artifact 可运行。

## 16.2 需要弱化但仍可提交

- predictive analysis 无提升；
- stability 结果较混合；
- qualitative cases 不够漂亮；
- judge agreement 90%-95% 但 sensitivity analysis 后主效应仍稳定。

这些不会推翻 intervention-based paper，只需将对应分析移 appendix。

## 16.3 不应按当前版本提交

- judge audit 显示 severe condition-specific error，且来不及重评；
- human labels 使 low-rated harmful pure semantic effect 消失或反向；
- master script 无法复现已有表格；
- full / matched / retained cohort 数字仍混用；
- artifact 或论文存在 anonymity violation。

---

# 17. 最终 Paper 的中心叙事

论文不是“我们发现删步骤能节省 token”，也不是“低 PRM 分就应该删”。最终叙事应为：

1. PRM 评价 local correctness，而 pruning 需要 counterfactual removability；
2. PRM rating 与 contribution 有较强关联，但 34.5% 的步骤偏离 expected diagonal；
3. raw deletion gain 主要集中于 low-rated harmful steps；
4. matched placebo 表明其中既有 generic restart，也有更大的 target-specific semantic component；
5. 当前 trajectory 已稳定正确时，删除会产生净伤害；
6. 因此 PRM 是 candidate-ranking prior，而不是 standalone pruning policy；
7. 安全系统需要 contribution signal、trajectory-state estimation、downstream validation 与 rollback。

推荐结尾：

> Process scores tell us whether a step looks correct. They do not, by themselves, tell us whether the step should be removed. Reliable reasoning pruning requires separating local correctness, trajectory state, and counterfactual contribution.

---

# 18. 最终 Checklist

## Judge

- [ ] 200 distinct outputs；
- [ ] blind annotation；
- [ ] C->W 与 W->C 都覆盖；
- [ ] agreement / FP / FN / condition bias；
- [ ] audit 后重算 sensitivity。

## Analysis

- [x] danger 与 benefit 分开预测；
- [x] grouped CV；
- [x] no run leakage；
- [x] stability rules 冻结；
- [x] 511 vs 89 balance audit；
- [x] full / retained / matched labels 清楚。

## Cases

- [x] 固定筛选规则；
- [ ] 人工验证；
- [x] 至少一个 restart confound candidate；
- [ ] 不把方向性案例写成统计结论。

## Paper

- [ ] 4 页正文；
- [ ] 独立 Limitations；
- [ ] raw 与 placebo-corrected 同时报；
- [ ] token 降级；
- [ ] state-boundary caveat；
- [ ] dangerous deletion 不隐藏。

## Artifact

- [ ] one-command rebuild；
- [ ] seeds；
- [ ] configs；
- [ ] prompts；
- [ ] sample IDs；
- [ ] license；
- [ ] anonymous paths/repo；
- [ ] PDF metadata cleaned。

## Submission

- [ ] OpenReview author list 最终确认；
- [ ] 8 月 3 日前提交；
- [ ] 8 月 5 日前所有作者 reviewer registration；
- [ ] submission receipt 归档。

---

# References and Official Submission Sources

- ACL Rolling Review. [Dates and Venues](https://aclrollingreview.org/dates). Accessed 2026-07-22.
- ACL Rolling Review. [Call for Papers](https://aclrollingreview.org/cfp). Accessed 2026-07-22.
- ACL Rolling Review. [Responsible NLP Research Checklist](https://aclrollingreview.org/responsibleNLPresearch/). Accessed 2026-07-22.
- OpenAI PRM800K and associated process-supervision resources.
- Lightman et al. *Let's Verify Step by Step*. ICLR 2024.
- Process Advantage Verifier and related process-verification work.
