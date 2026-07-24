# PRM 评分能否预测推理步骤的可删除性？

## 基于 PRM800K 的反事实步骤删除研究

**作者：ZHANG RUICHEN**  
**单位：The Hong Kong University of Science and Technology**

> 更新版本：补充分层 target-step cluster bootstrap 与 length-matched Placebo Deletion 实验结果。

---

## 摘要

Process Reward Model（PRM）通常用于评价一个推理步骤是否局部正确、合理或存在错误。然而，reasoning-step pruning 真正需要判断的是另一个问题：**该步骤是否为后续推理所必需，或者能否在不损害最终答案的情况下被删除。**

本项目研究 PRM step rating 与 reasoning-step removability 之间的关系。我们从 PRM800K 中抽取 600 个目标步骤，其中 rating \(=1,0,-1\) 各 200 个，并对每个步骤构造 Control 与 Deletion 两种 continuation 条件。Control 保留目标步骤，Deletion 删除目标步骤后从相同位置重新生成后续推理。每个样本运行 4 次，共得到 2,400 组 paired observations 和 4,800 次生成。

项目进一步将步骤划分为 **Essential、Redundant 和 Harmful** 三类，用于刻画步骤在完整推理中的功能贡献。初步结果显示，PRM rating 与步骤贡献存在较强关联，但两者并不等价。Human-calibrated annotation 中，34.5% 的样本属于 off-diagonal cases。删除收益主要集中在 Harmful steps，尤其是 PRM rating \(=-1\) 且被判定为 Harmful 的步骤；相反，rating \(=0\) 且被判定为 Essential 的步骤在删除后表现出明显的准确率下降。

Target-step cluster bootstrap 进一步显示，删除效应随 step position、step length、prefix length 和 Control 稳定性显著变化。Length-matched Placebo Deletion 在 511 个可匹配 target steps 上得到总体 Target Effect \(=+7.97\) pp、Placebo Effect \(=-0.57\) pp、Pure Semantic Effect \(=+8.55\) pp；在最关键的 rating \(=-1\) × Harmful 组中，Pure Semantic Effect 为 \(+13.85\) pp。这表明主要删除收益不能仅由随机删除等长内容解释。

本项目的核心结论不是“PRM 无法反映步骤价值”，而是：

> **PRM rating 是预测 reasoning-step contribution 的有用先验，但不足以单独决定一个步骤是否应该被删除。**

---

## 1. 研究背景与动机

随着大语言模型生成的推理轨迹不断变长，推理过程中的重复、无效和误导性步骤也越来越多。为了降低推理成本并提升过程可解释性，一个自然方向是对 reasoning trace 进行 step-level pruning。

现有 PRM 主要回答：

> 当前步骤是否局部正确、合理或高质量？

但 pruning system 实际需要回答：

> 如果删掉当前步骤，模型是否仍然能够得到正确答案？

这两个问题并不相同。

一个局部正确的步骤可能只是：

- 重复已有结论；
- 对前文进行等价改写；
- 给出不影响后续推理的额外解释；
- 重复验证一个已经确定的结果。

这类步骤虽然正确，但可能是可删除的。

另一方面，一个评分较低的步骤也可能包含：

- 后续使用的变量定义；
- 必要的中间计算；
- 问题分解结果；
- 关键约束；
- 从一个推理阶段过渡到下一阶段的桥梁。

因此，局部不完美并不必然意味着可以删除。

更进一步，一些错误步骤会将模型锚定在错误分支上，使后续模型不断延续或合理化该错误。如果删除这些步骤，模型反而可能重新生成一条更正确的 continuation。

由此，本项目关注 **Step Correctness** 与 **Step Contribution** 的区别，并通过实际删除干预测量 reasoning step 对后续生成的影响。

---

## 2. 核心研究问题

### RQ1：PRM rating 与 reasoning-step removability 之间存在多强的关联？

研究 rating \(=1,0,-1\) 的步骤在删除后分别表现出怎样的：

- accuracy change；
- Correct \(\rightarrow\) Wrong rate；
- Wrong \(\rightarrow\) Correct rate；
- token change；
- abnormal continuation rate。

### RQ2：哪些步骤体现了 PRM rating 与 functional contribution 的错位？

重点研究以下 off-diagonal cases：

- rating \(=1\) 但 Redundant；
- rating \(=0\) 但 Essential；
- rating \(=-1\) 但并非 Harmful；
- 相同 PRM rating 下具有完全不同删除效果的步骤。

### RQ3：Essential、Redundant、Harmful 分类是否比 PRM rating 更接近真实删除效果？

比较：

- PRM rating；
- AI 标注的 step type；
- human-calibrated step type；
- 实际 deletion outcome。

研究哪种信号更适合：

- pruning candidate ranking；
- harmful-step detection；
- safe compression；
- dangerous deletion prevention。

### RQ4：删除步骤能否同时改善准确率和推理效率？

研究删除是否能够：

- 减少总生成 token；
- 降低 cannot continue 或 logical break；
- 保持正确答案；
- 修复原本错误的推理路径。

---

## 3. 与 PRM 和 PAV 的区别

| 方法 | 核心问题 | 干预或比较方向 | 主要对象 |
|---|---|---|---|
| PRM | 当前步骤是否局部正确或合理？ | 通常无显式 counterfactual intervention | Step correctness |
| PAV | 加入当前步骤后，未来成功概率增加多少？ | Prefix \(\rightarrow\) Prefix + Step | Prospective advantage |
| 本项目 | 已有步骤被删除后，后续推理是否受损或改善？ | Prefix + Step \(\rightarrow\) Prefix without Step | Retrospective removability |

PAV 与本项目都研究步骤对未来成功的贡献，但条件状态和干预方向不同。

PAV 更接近：

\[
V(h_{<t},s_t)-V(h_{<t})
\]

本项目实际测量的是：

\[
Y\bigl(h_{<t}\bigr)-Y\bigl(h_{<t},s_t\bigr)
\]

其中 \(Y\) 表示从给定 visible prefix 出发重新生成后得到正确答案的结果。

因此，两者相关，但不应被视为完全相同的量。

---

## 4. 核心假设

### H1：PRM rating 与 removability 相关，但不等价

预计 rating 越低，步骤越可能是 Harmful；rating 越高，步骤越可能是 Essential。但由于冗余、重复和上下文依赖，仍会存在大量 off-diagonal cases。

### H2：Harmful steps 是最有价值的删除对象

错误步骤可能形成 reasoning anchor，使模型继续沿错误路径生成。删除后，模型有机会重新规划，从而出现：

\[
\text{Wrong}\rightarrow\text{Correct}
\]

### H3：正确步骤不一定是必要步骤

部分 rating \(=1\) 的步骤即使完全正确，也可能不提供独特信息，因此可以被视为 compression candidates。

### H4：低评分步骤不一定可以安全删除

部分 rating \(=0\) 或 \(-1\) 的步骤可能承载后续所需信息。仅根据 PRM rating 直接删除会产生 Correct \(\rightarrow\) Wrong 风险。

### H5：PRM 应作为 ranking prior，而不是 hard deletion rule

更可靠的 pruning system 应结合：

- PRM rating；
- contribution type；
- prediction confidence；
- downstream validation；
- rollback mechanism。

---

## 5. 操作性定义

### 5.1 目标样本

每个目标样本包含：

- 问题 \(q\)；
- 目标步骤之前的 reasoning history \(h_{<t}\)；
- 目标步骤 \(s_t\)；
- 目标步骤之后的原始 reasoning；
- PRM rating \(r_t \in \{-1,0,1\}\)。

### 5.2 Control condition

模型输入：

\[
q,\ h_{<t},\ s_t
\]

随后从目标步骤之后重新生成 continuation。

### 5.3 Deletion condition

模型输入：

\[
q,\ h_{<t}
\]

目标步骤 \(s_t\) 被删除，模型从该位置重新生成 continuation。

### 5.4 实验实际测量的量

本实验不是从一个固定完成的答案中机械删除一句话，而是让模型从不同 visible prefix 重新生成。

因此，本项目测量的是：

> 目标步骤对新 continuation 的 contextual contribution。

它不等价于“删掉完整答案中的一句话后，剩余文本是否仍然逻辑连贯”。

### 5.5 Paired outcome

每个 Control/Deletion pair 根据最终答案得到四种结果：

| Control | Deletion | 解释 |
|---|---|---|
| Correct | Correct | 删除后仍然成功 |
| Correct | Wrong | 删除造成损害 |
| Wrong | Correct | 删除修复错误路径 |
| Wrong | Wrong | 两种条件均未得到正确答案 |

---

## 6. Step Contribution 分类

### 6.1 Essential

目标步骤提供后续推理所依赖的关键信息，例如：

- 变量或符号定义；
- 必要中间结果；
- 问题分解；
- 关键约束；
- 重要策略选择；
- 后续推理所需的逻辑桥梁。

### 6.2 Redundant

步骤本身可能正确，但没有提供独特信息，例如：

- 重复前文；
- 等价改写；
- 多余解释；
- 重复验证；
- 后续未使用的计算。

### 6.3 Harmful

步骤引入错误或误导信息，例如：

- 错误计算；
- 错误假设；
- 无效策略；
- 与问题无关的推导；
- 导致模型继续沿错误分支生成的中间结论。

### 6.4 Removable label 与 Step Type 的区别

Step Type 是语义分类；Removable label 是对删除安全性的预测。

二者不完全相同：

- Redundant 通常应更容易删除；
- Harmful 删除后可能改善结果；
- Essential 通常应被保护；
- 但实际删除效果仍受到模型随机性、prefix 状态和重新生成能力影响。

因此，语义标签只能作为候选信号，最终仍需通过 intervention 评估。

---

## 7. 数据集与采样

### 7.1 数据集

使用 OpenAI PRM800K Phase 2 test split。

### 7.2 样本规模

共抽取 600 个 target steps：

- PRM rating \(=1\)：200 个；
- PRM rating \(=0\)：200 个；
- PRM rating \(=-1\)：200 个。

每组覆盖：

- Early position；
- Middle position；
- Late position。

### 7.3 建议记录的控制变量

- target step token length；
- visible prefix length；
- trajectory total length；
- step position；
- problem type；
- 原始 trajectory correctness；
- 同一问题或轨迹是否出现多个目标步骤。

---

## 8. 标注流程

### 8.1 Initial annotation

- DeepSeek V4 Flash 标注 415 个步骤；
- DeepSeek V4 Pro review 185 个不确定或冲突案例；
- 输出：
  - Removable label；
  - Step Type；
  - Confidence；
  - Reason。

### 8.2 Human calibration

从额外的 150 个 steps 中人工标注 75 个 examples，作为 few-shot demonstrations。

随后 DeepSeek V4 Flash 对全部 600 个步骤进行 blind re-label：

- 不看到旧标签；
- 不看到 deletion outcomes；
- 不使用 PRM rating 作为显式判断依据。

### 8.3 Annotation-level analysis

Human-calibrated labels 的分布为：

| PRM Rating | Essential | Redundant | Harmful | Total |
|---:|---:|---:|---:|---:|
| 1 | 118 | 69 | 13 | 200 |
| 0 | 55 | 115 | 30 | 200 |
| -1 | 25 | 15 | 160 | 200 |

关联统计：

- Pearson correlation：0.599；
- \(\chi^2(4)=334.93\)；
- \(p<0.001\)；
- Cramer’s \(V=0.528\)；
- Diagonal cases：393/600（65.5%）；
- Off-diagonal cases：207/600（34.5%）。

这表明 PRM rating 与 Step Type 有较强关联，但仍有超过三分之一的样本不能由 rating 直接推断其 contribution type。

---

## 9. 删除实验设置

### 9.1 生成模型

Qwen3-8B。

### 9.2 生成参数

Control 与 Deletion 使用匹配设置：

- temperature \(=0.7\)；
- top-p \(=0.8\)；
- max tokens \(=2048\)；
- `/no_think`。

### 9.3 重复次数

每个 sample 进行 4 次 paired runs：

\[
600\times4=2400
\]

共得到：

- 2,400 paired observations；
- 4,800 generations。

### 9.4 评价模型

使用 Qwen3-8B judge，在 temperature \(=0\) 下判断 final answer 与 ground truth 是否 mathematically equivalent。

---

## 10. 双层分析口径

最新报告排除了 670 个 Control 与 Deletion 均错误的 Still Wrong pairs。该筛选有助于分析“至少一个条件能够解出的样本”，但它使用了实验结果本身，因此不能替代全量数据上的 treatment effect。

本项目应明确区分两种分析。

### 10.1 Primary analysis：全量 2,400 pairs

全量分析用于估计 unconditional deletion effect。

主要指标：

- overall accuracy change；
- Correct \(\rightarrow\) Wrong；
- Wrong \(\rightarrow\) Correct；
- Still Correct；
- Still Wrong；
- total token change；
- completion abnormality。

这是论文主结果应采用的口径。

### 10.2 Secondary diagnostic analysis：retained 1,730 pairs

排除：

\[
670\ \text{Still Wrong pairs}
\]

保留：

\[
1730\ \text{pairs}
\]

该分析用于回答：

> 当至少一个 condition 可以正确解题时，删除与保留目标步骤的表现有什么差异？

该口径适合：

- 分析 recoverable cases；
- 分析 rating 和 Step Type 的 diagnostic pattern；
- 对比 deletion harm 与 recovery；
- 研究 token 和 completion status。

但 retained accuracy 是条件性 descriptive statistic，不能被解释为全体样本上的绝对准确率。

---

## 11. 评价指标

### 11.1 Accuracy metrics

#### Unconditional accuracy change

\[
\Delta_{\text{acc}}
=
\frac{1}{N}\sum_{i=1}^{N}
\left(
Y_i^{\text{del}}-Y_i^{\text{ctrl}}
\right)
\]

#### Safe deletion rate

\[
P(Y_{\text{del}}=1\mid Y_{\text{ctrl}}=1)
\]

#### Deletion harm rate

\[
P(Y_{\text{del}}=0\mid Y_{\text{ctrl}}=1)
\]

#### Recovery rate

\[
P(Y_{\text{del}}=1\mid Y_{\text{ctrl}}=0)
\]

### 11.2 Token metrics

定义：

\[
\text{Token Saved}
=
\text{Control Tokens}
-
\text{Deletion Tokens}
\]

同时报告：

- total token saving；
- mean token saving；
- median token saving；
- deletion shorter / equal / longer counts；
- token saving conditioned on correctness；
- accuracy–token trade-off。

### 11.3 Completion metrics

- Completed；
- Cannot Continue；
- Logical Break；
- newly induced abnormal outcomes；
- recovered abnormal outcomes。

### 11.4 Annotation metrics

- PRM rating × Step Type；
- off-diagonal rate；
- removable prediction confusion matrix；
- precision；
- recall；
- specificity；
- F1-score。

---

## 12. 初步实验结果

## 12.1 全量 2,400 pairs：unconditional results

| Metric | Control | Deletion | Change |
|---|---:|---:|---:|
| Correct Answers | 1,353 / 2,400 | 1,526 / 2,400 | +173 |
| Accuracy | 56.38% | 63.58% | +7.20 pp |
| Average Visible Tokens | 326.36 | 313.38 | -12.98 |
| Total Visible Tokens | 783,264 | 752,108 | -31,156（-3.98%） |

Paired transitions：

| Transition | Count | Share |
|---|---:|---:|
| Wrong \(\rightarrow\) Correct | 377 | 15.71% |
| Correct \(\rightarrow\) Wrong | 204 | 8.50% |
| Still Correct | 1,149 | 47.88% |
| Still Wrong | 670 | 27.92% |

净准确答案增量为：

\[
377-204=173
\]

这说明删除并非单纯压缩操作。在部分样本中，删除目标步骤会移除错误 reasoning anchor，使模型重新生成正确路径。

但删除不是无条件安全的，因为仍有 204 个 Correct \(\rightarrow\) Wrong transitions。

---

## 12.2 Retained 1,730 pairs：conditional diagnostic results

排除 670 个 Still Wrong pairs 后：

| Metric | Control | Deletion | Change |
|---|---:|---:|---:|
| Correct Answers | 1,353 / 1,730 | 1,526 / 1,730 | +173 |
| Accuracy | 78.21% | 88.21% | +10.00 pp |
| Total Visible Tokens | 460,979 | 401,802 | -59,177 |
| Mean Visible Tokens | 266.46 | 232.26 | -34.21 |
| Median Visible Tokens | 172 | 175 | +3 |

Retained paired transitions：

| Transition | Count | Share |
|---|---:|---:|
| Wrong \(\rightarrow\) Correct | 377 | 21.79% |
| Correct \(\rightarrow\) Wrong | 204 | 11.79% |
| Still Correct | 1,149 | 66.42% |

Deletion 在 retained cohort 中减少 12.84% total visible tokens，但 median token saving 为 \(-3\)，即典型样本中 Deletion 反而略长。总 token 节省主要由少数大幅缩短的长尾 outputs 驱动。

具体分布为：

- Deletion 更短：788；
- 相同长度：34；
- Deletion 更长：908。

因此，不能只报告 mean 或 aggregate token saving。

---

## 12.3 四次 paired runs

| Run | Retained n | Control Acc. | Deletion Acc. | Change | Wrong→Correct | Correct→Wrong | Token Saving Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 433 | 77.83% | 87.76% | +9.93 pp | 96 | 53 | 8.98% |
| 2 | 428 | 78.97% | 89.72% | +10.75 pp | 90 | 44 | 13.66% |
| 3 | 432 | 79.86% | 86.81% | +6.95 pp | 87 | 57 | 14.89% |
| 4 | 437 | 76.20% | 88.56% | +12.36 pp | 104 | 50 | 13.65% |

四个 runs 的 improvement 均为正，并且每个 run 都满足：

\[
\text{Wrong}\rightarrow\text{Correct}
>
\text{Correct}\rightarrow\text{Wrong}
\]

不过同一个 sample 出现在 4 次 runs 中，因此这些 observations 不是完全独立。

---

## 12.4 Completion status

在 retained cohort 中：

| Status | Control | Deletion | Net Change |
|---|---:|---:|---:|
| Completed | 1,656 | 1,701 | +45 |
| Cannot Continue | 47 | 23 | -24 |
| Logical Break | 27 | 6 | -21 |

Deletion 使 abnormal states 从 74 降到 29，但同时产生：

- 23 个新的 Cannot Continue；
- 6 个新的 Logical Break。

因此，aggregate completion improvement 不代表每个删除操作都安全。

---

## 12.5 Results by PRM rating

Retained cohort 中：

| PRM Rating | Retained n | Control Acc. | Deletion Acc. | Change | Wrong→Correct | Correct→Wrong | Token Saving Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 655 | 88.85% | 88.09% | -0.76 pp | 73 | 78 | 19.01% |
| 0 | 613 | 85.15% | 85.48% | +0.33 pp | 91 | 89 | 11.03% |
| -1 | 462 | 53.90% | 91.99% | +38.10 pp | 213 | 37 | 4.83% |

主要现象：

- rating \(=-1\) 的 deletion gain 最大；
- rating \(=1\) 略微下降；
- rating \(=0\) 基本中性。

但 rating \(=-1\) 中有 338/800，即 42.25% 的 pairs 被排除为 Still Wrong，明显高于其他 rating。因此 retained cohort 中的 91.99% Deletion Accuracy 不能解释为全量数据上的绝对性能。

---

## 12.6 Results by Step Type

### Initial labels

| Step Type | Retained n | Control Acc. | Deletion Acc. | Change | Wrong→Correct | Correct→Wrong |
|---|---:|---:|---:|---:|---:|---:|
| Essential | 494 | 86.23% | 84.62% | -1.61 pp | 68 | 76 |
| Redundant | 665 | 88.12% | 89.47% | +1.35 pp | 79 | 70 |
| Harmful | 571 | 59.72% | 89.84% | +30.12 pp | 230 | 58 |

### Human-calibrated labels

| Step Type | Retained n | Control Acc. | Deletion Acc. | Change | Wrong→Correct | Correct→Wrong | Token Saving Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Essential | 634 | 84.86% | 87.38% | +2.52 pp | 96 | 80 | 16.44% |
| Redundant | 630 | 86.03% | 87.78% | +1.75 pp | 88 | 77 | 10.09% |
| Harmful | 466 | 58.58% | 89.91% | +31.33 pp | 193 | 47 | 11.86% |

Harmful 在两种 annotation version 下都表现出最强、最稳定的 deletion gain。

Essential 在 human-calibrated broad average 下为正，并不意味着所有 Essential steps 都可以安全删除。Broad class average 会混合不同 rating、位置、问题难度和 continuation recoverability，因此必须结合细分 diagnostic groups 分析。

---

## 12.7 关键 Rating × Step Type diagnostic groups

### Human-calibrated labels

| Diagnostic Group | Retained n | Control Acc. | Deletion Acc. | Change | Wrong→Correct | Correct→Wrong | Token Saving Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Rating \(0\) × Essential | 163 | 91.41% | 82.21% | -9.20 pp | 14 | 29 | 17.48% |
| Rating \(1\) × Redundant | 227 | 89.87% | 88.11% | -1.76 pp | 23 | 27 | 15.69% |
| Rating \(-1\) × Harmful | 350 | 52.57% | 90.86% | +38.29 pp | 166 | 32 | 5.50% |

这些结果构成项目最重要的证据：

### Rating \(0\) × Essential

Neutral local quality 不等于 deletion safety。即使 token saving 较高，删除后准确率仍下降 9.20 pp。

### Rating \(1\) × Redundant

正确且冗余的步骤更接近 compression candidate，但 human-calibrated result 仍为轻微负向，因此不能作为无条件删除规则。

### Rating \(-1\) × Harmful

删除收益最强，支持“错误步骤形成 reasoning anchor”的假设。

---

## 12.8 Removable classifier

Human calibration 后：

| Metric | Initial | Human-Calibrated | Change |
|---|---:|---:|---:|
| Accuracy | 50.00% | 60.17% | +10.17 pp |
| Precision | 90.35% | 88.86% | -1.49 pp |
| Recall | 48.49% | 62.71% | +14.22 pp |
| Specificity | 61.27% | 41.18% | -20.09 pp |
| F1-score | 63.11% | 73.53% | +10.42 pp |

Human calibration 主要提升 Recall 和 F1-score，但降低 Specificity。

在 retained cohort 中，human-calibrated predicted-removable group 仍包含 120 个 dangerous false-positive pairs。因此，该 classifier 更适合：

- candidate ranking；
- high-recall screening；
- verified deletion pipeline；

而不适合直接执行不可逆删除。

---

## 12.9 分层 Target-Step Cluster Bootstrap 结果

为避免把同一 target step 的 4 次重复运行视为相互独立，本节以 `step_id` 为聚类单位进行 5,000 次 cluster bootstrap。每次从 600 个 target steps 中有放回抽取 600 个 steps，并保留入选 step 的全部 4 次 runs。表中的 `accuracy change` 为 Deletion Accuracy 减去 Control Accuracy，单位为百分点；括号内为 percentile 95% confidence interval。`Wrong → Correct` 和 `Correct → Wrong` 为原始 2,400 pairs 中的观测数量。

长度分组在 step 层面按排名三等分，每组 200 个 target steps：

- `step_length`：Control prompt tokens 与 Deletion prompt tokens 的差值；
- `prefix_length`：删除目标 step 后实际可见输入的 prompt tokens；
- 分位数边界出现相同 token 长度时，以 `sampleId` 作确定性排序。

| 分组维度 | 分组 | 定义 | Target steps | Pairs | Accuracy change (pp) | Wrong → Correct | Correct → Wrong |
|---|---|---|---:|---:|---:|---:|---:|
| step position | Early | early | 201 | 804 | +4.98 \([-1.13,\ 11.18]\) | 127 | 87 |
| step position | Middle | middle | 201 | 804 | +9.45 \([3.31,\ 15.59]\) | 144 | 68 |
| step position | Late | late | 198 | 792 | +7.20 \([1.75,\ 12.62]\) | 106 | 49 |
| step length | Short | rank 1–200；4–27 tokens | 200 | 800 | +0.25 \([-5.21,\ 5.56]\) | 72 | 70 |
| step length | Middle | rank 201–400；27–40 tokens | 200 | 800 | +9.63 \([3.51,\ 15.66]\) | 148 | 71 |
| step length | Long | rank 401–600；40–648 tokens | 200 | 800 | +11.75 \([5.53,\ 17.97]\) | 157 | 63 |
| prefix length | Short | rank 1–200；272–431 tokens | 200 | 800 | +5.38 \([-0.68,\ 11.33]\) | 121 | 78 |
| prefix length | Middle | rank 201–400；432–577 tokens | 200 | 800 | +10.88 \([4.75,\ 16.90]\) | 155 | 68 |
| prefix length | Long | rank 401–600；578–1,229 tokens | 200 | 800 | +5.38 \([0.00,\ 10.81]\) | 101 | 58 |
| control correct frequency | 0/4 | 4 次 Control 均错误 | 224 | 896 | +33.37 \([27.52,\ 39.20]\) | 299 | 0 |
| control correct frequency | 1/4 | 4 次中 1 次正确 | 23 | 92 | +15.22 \([-1.25,\ 32.29]\) | 28 | 14 |
| control correct frequency | 2/4 | 4 次中 2 次正确 | 27 | 108 | +9.26 \([-8.93,\ 26.25]\) | 31 | 21 |
| control correct frequency | 3/4 | 4 次中 3 次正确 | 28 | 112 | -5.36 \([-20.69,\ 8.33]\) | 19 | 25 |
| control correct frequency | 4/4 | 4 次 Control 均正确 | 298 | 1,192 | -12.08 \([-15.49,\ -8.91]\) | 0 | 144 |

主要发现：

1. **位置异质性。** Middle 和 Late 位置的删除收益显著为正；Early 的区间跨越 0，说明早期删除的平均收益更不稳定。
2. **目标 step 长度异质性。** Short steps 的平均效应接近 0；Middle 和 Long steps 的删除收益分别为 \(+9.63\) pp 和 \(+11.75\) pp。该关系是描述性关联，不能单独解释为长度的因果作用。
3. **Prefix length 呈非单调关系。** Middle-prefix 组收益最大；Long-prefix 组的区间下界四舍五入后为 0.00 pp。
4. **Control 稳定性是最强的分层变量。** 对 4 次 Control 均错误的 steps，删除带来 \(+33.37\) pp；对 4 次 Control 均正确的 steps，删除造成 \(-12.08\) pp。这说明删除收益高度依赖于 baseline solvability。

---

## 12.10 Length-Matched Placebo Deletion 结果

### 12.10.1 Placebo 选择与运行

Placebo 实验用于比较“删除目标 step”与“删除同一轨迹中长度相近的其他 step”：

1. 使用 `Qwen/Qwen3-8B` 官方 tokenizer 计算轨迹中每个 step 的 token 长度；
2. 对每个 target step，筛选长度位于目标长度 \(0.8\times\) 至 \(1.2\times\) 的非目标 steps；
3. 使用固定随机种子，从合格 candidates 中最多抽取 4 个 Placebo steps；
4. 若 candidates 少于 4 个则全部使用；若没有 candidate，则跳过该 target step；
5. 每个 Placebo step 单独删除一次，从该 Placebo 所在位置之前的 prefix 重新生成 continuation；
6. 使用与主实验相同的 `qwen/qwen3-8b` judge 判断最终答案是否正确。

600 个 target steps 中，511 个至少有 1 个合格 Placebo，89 个因无长度匹配 candidate 被跳过。最终共运行 1,514 次 Placebo Deletion。每个 target step 先计算：

\[
\text{control\_avg\_correct}
=
\frac{1}{4}\sum_{r=1}^{4}Y^{\text{ctrl}}_{ir},
\]

\[
\text{target\_avg\_correct}
=
\frac{1}{4}\sum_{r=1}^{4}Y^{\text{target-del}}_{ir},
\]

\[
\text{placebo\_avg\_correct}
=
\frac{1}{K_i}\sum_{k=1}^{K_i}Y^{\text{placebo-del}}_{ik},
\qquad K_i\in\{1,2,3,4\}.
\]

随后定义：

\[
\text{Target Effect}
=
\text{target\_avg\_correct}
-
\text{control\_avg\_correct},
\]

\[
\text{Placebo Effect}
=
\text{placebo\_avg\_correct}
-
\text{control\_avg\_correct},
\]

\[
\text{Pure Semantic Effect}
=
\text{target\_avg\_correct}
-
\text{placebo\_avg\_correct}.
\]

三个效应均先在 target-step 层面计算，再在各报告组内以 `step_id` 有放回重采样 5,000 次。下表单位为百分点，括号内为 percentile 95% confidence interval。

| Group | Eligible target steps | Placebo runs | Target Effect | Placebo Effect | Pure Semantic Effect |
|---|---:|---:|---:|---:|---:|
| Overall | 511 | 1,514 | +7.97 \([4.26,\ 11.69]\) | -0.57 \([-4.13,\ 3.13]\) | +8.55 \([4.83,\ 12.17]\) |
| rating \(=-1\) | 169 | 458 | +22.78 \([16.12,\ 29.59]\) | +9.47 \([2.86,\ 15.93]\) | +13.31 \([6.71,\ 19.53]\) |
| rating \(=0\) | 176 | 539 | +0.99 \([-5.40,\ 7.39]\) | -5.63 \([-12.12,\ 0.76]\) | +6.63 \([0.19,\ 13.21]\) |
| rating \(=1\) | 166 | 517 | +0.30 \([-5.27,\ 5.87]\) | -5.42 \([-11.19,\ 0.70]\) | +5.72 \([-0.05,\ 11.40]\) |
| Step Type = Harmful | 201 | 563 | +18.41 \([11.94,\ 24.88]\) | +3.57 \([-2.57,\ 9.74]\) | +14.84 \([8.83,\ 20.61]\) |
| rating \(=-1\) × Harmful | 151 | 399 | +23.84 \([16.89,\ 30.96]\) | +9.99 \([2.92,\ 17.00]\) | +13.85 \([6.95,\ 20.64]\) |

主要发现：

1. **总体目标效应主要来自 target-specific component。** Overall Placebo Effect 接近 0 且区间跨越 0，而 Pure Semantic Effect 为 \(+8.55\) pp，95% CI 为 \([4.83,\ 12.17]\)。
2. **低评分步骤同时包含一般删除收益和目标语义收益。** rating \(=-1\) 的 Placebo Effect 为 \(+9.47\) pp，但扣除该基线后，Pure Semantic Effect 仍为 \(+13.31\) pp。
3. **Harmful label 提供独立的 target-specific signal。** Harmful steps 的 Pure Semantic Effect 为 \(+14.84\) pp。
4. **关键组结果稳定。** rating \(=-1\) × Harmful 的 Target Effect 为 \(+23.84\) pp，其中 Placebo Effect 为 \(+9.99\) pp，Pure Semantic Effect 仍达到 \(+13.85\) pp。
5. **rating \(=0\) 的分解值得进一步检查。** 其原始 Target Effect 接近 0，但 Placebo baseline 为负，因此 Pure Semantic Effect 为 \(+6.63\) pp，区间下界仅略高于 0。

需要谨慎解释 `Placebo Effect`：Placebo step 在其自身位置被删除，因此它不仅反映长度匹配，还可能包含删除位置、可见 prefix 长度和 Placebo step 自身语义的影响。它是一个 **length-matched operational deletion baseline**，不能视为已经完全隔离的“纯长度因果效应”。此外，Placebo 结果仅适用于 511 个有合格匹配项的 target steps；由于 89 个 steps 被排除，表中的 Target Effect 与全量 600-step 主分析不必完全一致。

---

## 13. 统计分析计划

### 13.1 Clustered uncertainty estimation

由于每个 target step 被重复运行 4 次，不能将 2,400 pairs 视为完全独立样本。

主分析应采用 target-step-level cluster bootstrap：

1. 以 600 个 target steps 为采样单位；
2. 每次有放回抽取 600 个 steps；
3. 保留每个 step 的全部 4 次 runs；
4. 重新计算 accuracy change、harm rate、recovery rate 和 token change；
5. 重复 1,000–10,000 次；
6. 报告 95% confidence interval。

本版本已完成 5,000 次 target-step cluster bootstrap；主分层结果见第 12.9 节，Placebo effect decomposition 见第 12.10 节。

### 13.2 McNemar test

标准 McNemar test 可作为辅助结果，但由于未建模 sample-level clustering，不应将极小的 p-value 作为主要证据。

### 13.3 Stratified analysis

至少按以下因素分层：

- PRM rating；
- Step Type；
- rating × Step Type；
- step position；
- step length；
- prefix length；
- problem difficulty；
- control correctness frequency。

目前已完成 step position、step length、prefix length 与 control correctness frequency 的分层 bootstrap；problem difficulty 仍留待后续分析。

---

## 14. 下一阶段实验

### 14.1 保留全量结果作为主分析

不能只报告排除 Still Wrong 后的数字。

最终报告应同时呈现：

1. 全量 2,400 pairs 的 unconditional effect；
2. retained 1,730 pairs 的 conditional diagnostic effect。

### 14.2 Placebo deletion：已完成，待扩展

本版本已经完成第三种条件：

- Control：保留目标步骤；
- Target Deletion：删除目标步骤；
- Placebo Deletion：删除同一轨迹中长度为目标 step \(0.8\times\)–\(1.2\times\) 的非目标 step。

已完成结果见第 12.10 节。后续扩展重点为：

- 进一步匹配 Placebo 与 target 的位置及 prefix length；
- 使用多个随机种子重复 Placebo 选择；
- 对无合格 Placebo 的 89 个 target steps 分析 selection bias；
- 使用不同 generator 和 judge 复现 effect decomposition。

### 14.3 Judge calibration

随机抽取 100–200 个 generation outputs 进行人工核验，报告：

- judge–human agreement；
- false-positive rate；
- false-negative rate；
- 模糊等价案例。

优先使用：

1. final-answer extraction；
2. exact match；
3. symbolic equivalence；
4. 仅在无法自动判断时使用 LLM judge。

### 14.4 跨模型验证

在计算资源允许时，选择部分样本在第二个 generator 上复现：

- 验证 PRM rating × contribution mismatch 是否跨模型存在；
- 检查 Harmful deletion gain 是否依赖于 Qwen3-8B；
- 检查不同模型的 recoverability 是否不同。

### 14.5 多步骤删除

当前项目研究单步删除。若单步结果稳定，可进一步探索：

- 连续删除多个 Redundant steps；
- 逐步删除多个 Harmful steps；
- 删除顺序；
- cumulative token saving；
- error accumulation；
- rollback policy。

---

## 15. 预期贡献

### 1. 明确区分 Step Correctness 与 Step Contribution

说明局部正确性不能直接等价为下游必要性。

### 2. 提出 reasoning-step removability 的反事实操作化定义

通过 Control/Deletion paired continuation 实际测量步骤的 contextual contribution。

### 3. 系统刻画 PRM rating 与 removability 的关系

证明 PRM rating 有预测价值，但存在显著 off-diagonal cases。

### 4. 识别最有价值和最危险的 deletion groups

- 最有价值：rating \(-1\) × Harmful；
- 最危险：rating \(0\) × Essential；
- 需验证的压缩候选：rating \(1\) × Redundant。

### 5. 为 reasoning-step pruning 提供设计原则

未来 pruning system 应采用：

\[
\text{PRM Prior}
+
\text{Contribution Model}
+
\text{Downstream Validation}
+
\text{Rollback}
\]

而不是仅依赖单一 PRM threshold。

---

## 16. 局限性

### 16.1 Intervention 不是固定轨迹机械删除

模型会重新生成 continuation，因此测到的是 contextual contribution 与 model recoverability 的结合。

### 16.2 生成模型和 judge 属于同一模型家族

这可能引入自偏好，需要人工校准或不同 judge 验证。

### 16.3 Still Wrong filtering 存在 outcome-based selection

Retained cohort 适合 diagnostic analysis，但不能替代全量 treatment effect。

### 16.4 AI annotation 不能视为 ground truth

Human-calibrated labels 仍然依赖 few-shot AI classification，需要更多人工一致性检查。

### 16.5 Broad Step Type 不能保证 individual deletion safety

即使某个类别平均表现良好，单个步骤仍可能产生危险删除。

### 16.6 Placebo matching 尚未完全隔离长度机制

Placebo 仅按 step token length 匹配，并在 Placebo 自身位置执行删除，因此 target 与 Placebo 的 step position、visible prefix length 可能不同。当前 Placebo Effect 应解释为 length-matched operational baseline，而不是纯长度因果效应。与此同时，无合格匹配项的 89 个 target steps 未进入 Placebo 分析，可能产生 matched-cohort selection bias。

---

## 17. 时间安排

### Week 1：数据与统计修正

- 同时整理 full cohort 与 retained cohort；
- 实现 target-step-level cluster bootstrap；
- 检查重复问题和重复轨迹；
- 重新计算各分组置信区间。

### Week 2：Judge calibration

- 人工核验 100–200 个 outputs；
- 比较 exact match、symbolic judge 和 LLM judge；
- 修正误判样本。

### Week 3：Placebo deletion

- 构造 length-matched random deletion；
- 运行小规模 pilot；
- 比较 target-specific effect。

### Week 4：扩展实验

- 按位置、长度和难度分层；
- 分析 unstable samples；
- 选择部分样本进行第二模型复现。

### Week 5：图表与案例分析

- 整理主要表格；
- 选取典型 Essential、Redundant、Harmful 案例；
- 展示正确但冗余、低分但必要、错误且有害的案例。

### Week 6：论文或技术报告写作

- 完成方法、实验和局限性；
- 明确 full 与 retained 两种口径；
- 整理代码、数据和复现实验说明。

---

## 18. 推荐图表

1. **实验流程图**  
   Sampling → Annotation → Human Calibration → Paired Deletion → Answer Evaluation → Statistical Analysis

2. **全量 Control 与 Deletion accuracy 对比**

3. **四种 paired transition 堆叠图**

4. **Full cohort 与 retained cohort 对比图**

5. **PRM rating × Step Type heatmap**

6. **三个 diagnostic groups 的 accuracy change 图**
   - \(0\times\) Essential
   - \(1\times\) Redundant
   - \(-1\times\) Harmful

7. **Token saving distribution**
   - Mean
   - Median
   - Shorter / Same / Longer counts

8. **Completion status transition 图**

9. **Human calibration 前后 classifier metrics**

10. **Target deletion 与 placebo deletion 对比**

---

## 19. 预期结论

本项目预计得出以下结论：

> PRM rating 与 reasoning-step contribution 存在明显关联，但它们是相关而不等价的两个构念。

PRM rating 可以作为步骤筛选和候选排序的先验信号，但不能直接作为自动删除规则。

删除收益主要集中在 Harmful steps，尤其是 rating \(=-1\) 且被识别为 Harmful 的步骤。此类步骤可能将模型锚定在错误推理路径上，删除后能够显著增加 Wrong \(\rightarrow\) Correct transitions。

Redundant steps 的主要价值在于 compression，而不是稳定提升准确率。即使是 rating \(=1\) 的 Redundant steps，也需要 downstream validation。

Essential steps，尤其是 rating \(=0\) × Essential 的 off-diagonal cases，说明中性或不完美的局部评分并不代表步骤可被安全删除。

因此，一个可靠的 reasoning-step pruning system 应显式建模：

- Step Correctness；
- Step Contribution；
- Prediction Uncertainty；
- Downstream Outcome；
- Rollback Ability。

---

## References

1. Hunter Lightman et al. *Let’s Verify Step by Step*. ICLR 2024.
2. OpenAI PRM800K.
3. Process Advantage Verifier, arXiv:2410.08146.
4. PRM-related reasoning evaluation work, arXiv:2504.16828.
