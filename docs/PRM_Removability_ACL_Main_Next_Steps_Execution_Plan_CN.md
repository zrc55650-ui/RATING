---
title: "PRM Scores Are Not Pruning Policies"
subtitle: "面向 ACL 2027 Main Conference 的下一阶段完整研究与执行计划"
author: "项目执行版（基于 A–F READY_TO_FREEZE 结果）"
date: "2026-07-24"
lang: zh-CN
---

# 0. 执行结论

当前 A–F 结果已经足以支持一篇较强的 ARR/Findings 风格 empirical audit，但若目标明确是 **ACL Main Conference**，仍然建议继续补实验。原因不是现有结果不可信，而是当前证据仍存在三个会限制 main-level impact 的结构性问题：

1. **研究对象主要是 PRM800K 的人工 step rating，而不是多个实际部署的 PRM 模型输出。**
2. **所有主要 continuation intervention 都由单一 generator（Qwen3-8B）完成。**
3. **主要数据来自单一数学数据源，尚未证明结论跨数据集、轨迹来源和模型成立。**

因此，下一阶段不应继续无目的扩表，也不应训练一个大型新 verifier。最有价值的升级路线是把项目从：

> “PRM800K 上的一个 deletion finding”

升级为：

> **一个系统审计 PRM correctness signals、semantic contribution 和 counterfactual removability 之间关系的 benchmark-style study。**

建议采用“双轨策略”：

- **短期：** 保持当前 A–F 数字冻结，完成 2026 年 8 月 ARR 投稿，作为外部审稿检查点。
- **ACL Main 强化期：** 补足实际 PRM scoring、跨 generator、跨数据集、人工语义标签和更严格干预控制，再形成 8 页 long paper。

当前项目不需要推翻重做。已有 600 steps、2,400 pairs、511-step placebo cohort、Judge Audit、cluster bootstrap、stability 和 qualitative cases 都应继续作为核心主干。

---

# 1. 当前证据已经证明了什么

## 1.1 可以冻结的主结果

### 结构性结果

- PRM rating 与 human-calibrated Essential / Redundant / Harmful 类型明显相关。
- Cramér’s \(V=0.528\)。
- 65.5% 位于预期对角线，但仍有 34.5% off-diagonal steps。
- 因此 step correctness 与 step contribution 相关但不等价。

### Full-cohort deletion result

在 600 个 target steps、2,400 个 paired outcomes 上：

\[
\Delta_{\mathrm{target}}=+7.21\text{ pp},
\quad
95\%\ \mathrm{CI}=[+3.88,+10.58].
\]

收益集中在：

- rating \(=-1\)：\(+22.00\) pp；
- Harmful：\(+18.38\) pp；
- rating \(=-1\)\(\times\)Harmful：\(+23.31\) pp。

rating \(=0\)、rating \(=1\)、Essential 和 Redundant 的区间均跨 0。

### Placebo decomposition

在 511-step matched cohort 中：

\[
\Delta_{\mathrm{target}}=+7.97\text{ pp},
\]

\[
\Delta_{\mathrm{placebo}}=-0.57\text{ pp},
\]

\[
\Delta_{\mathrm{semantic}}
=
\Delta_{\mathrm{target}}
-
\Delta_{\mathrm{placebo}}
=
+8.55\text{ pp}.
\]

对于 rating \(=-1\)\(\times\)Harmful：

\[
\Delta_{\mathrm{semantic}}=+13.85\text{ pp},
\quad
95\%\ \mathrm{CI}=[+6.95,+20.64].
\]

这支持 low-rated harmful steps 存在 target-specific negative-anchor effect，同时也说明 raw deletion gain 中包含 restart component。

### Evaluation validity

Judge Audit：

- Agreement：93.5%；
- Pair-transition agreement：91.7%；
- 最大 condition bias：2.3 pp；
- 200 个 audited labels 替换成人工 adjudication 后，overall effect 仅变化 \(-0.12\) pp，pure semantic effect 仅变化 \(-0.05\) pp。

因此当前主数字可以冻结，但论文必须保留 sensitivity 声明。

## 1.2 当前不能过度声称的内容

- 不能声称所有低分步骤都应删除。
- 不能声称 Redundant steps 能稳定节省 token。
- 不能声称当前 predictor 已经可以部署。
- 不能把 511-step placebo estimand 外推到全部 600 steps。
- 不能将 raw target effect 全部解释为目标步骤语义。
- 不能把当前结果称为跨模型、跨数据集的一般规律。
- 不能将 PRM800K 的人工标签直接等同于所有实际 PRM 的连续 score。

---

# 2. 为什么当前版本更像强 Findings，而不是稳定 ACL Main

| Main-level 审稿问题 | 当前状态 | 风险 |
|---|---|---|
| 是否测试了实际 PRM 模型，而不仅是训练数据标签？ | 未系统测试 | 标题中的 “PRM Scores” 可能被质疑为 construct mismatch |
| 结果是否依赖 Qwen3-8B 的 recoverability？ | 单一 generator | negative-anchor effect 可能是模型特有 |
| 结果是否依赖 PRM800K/MATH？ | 单一主数据源 | 泛化范围有限 |
| Semantic Step Type 是否由可靠人工标注支持？ | 主要为 AI + few-shot calibration；两套标签差异 27.3% | contribution taxonomy 可信度不足 |
| 是否比较了更直接的 importance/removability signals？ | 仅有 rating/type/static predictor | 无法回答“PRM 不够，那什么更有效？” |
| Placebo 是否严格匹配位置、运行次数和边界？ | 511 steps；89 skipped；placebo runs 不完全等量 | 仍有选择性和方差不对称 |
| 是否形成 benchmark / reusable protocol？ | 已有数据管线，但尚未包装 | Impact 和 community utility 有提升空间 |

ACL Main 强化的核心，不是把样本量从 600 机械增到 1,000，而是逐项解决上述 reviewer questions。

---

# 3. 建议的最终论文定位

## 3.1 推荐标题

### 首选

**PRM Scores Are Not Pruning Policies: Auditing Reasoning-Step Removability across Verifiers, Generators, and Datasets**

### 更偏 benchmark

**PRM-Rem: A Counterfactual Benchmark for Reasoning-Step Removability**

### 更偏机制

**Correct Does Not Mean Necessary: Negative Reasoning Anchors and the Limits of Process Rewards**

## 3.2 ACL Main 版本的核心贡献

1. **Conceptual contribution**  
   明确区分 step correctness、semantic contribution、prospective advantage 和 retrospective removability。

2. **Evaluation protocol**  
   提出 Control / Target deletion / matched placebo / semantic-preserving control 的反事实干预协议。

3. **Benchmark contribution**  
   提供跨 PRM signals、跨 generators、跨 datasets 的 removability benchmark。

4. **Empirical finding**  
   低评分 harmful steps 富集 target-specific negative anchors，但同一组仍包含危险删除。

5. **Methodological finding**  
   不带 matched placebo 的 deletion studies 会混淆 semantic effect 与 restart effect。

6. **Policy implication**  
   PRM 分数适合 candidate ranking，不适合 standalone deletion；安全系统需要 state、validation 和 rollback。

---

# 4. ACL Main 必做实验总览

| Workstream | 核心目的 | 优先级 | 是否需要新生成 |
|---|---|---:|---:|
| M1. Actual-PRM Score Audit | 解决“标签不等于实际 PRM score” | P0 | 否，主要是打分 |
| M2. Cross-Generator Replication | 检查 effect 是否依赖 Qwen3-8B | P0 | 是 |
| M3. Human Semantic Annotation | 解决两套 Step Type 差异与标注可信度 | P0 | 否 |
| M4. Strengthened Intervention Controls | 更严格分离语义、restart、位置和边界 | P0 | 是 |
| M5. Signal Baseline Comparison | 比较 PRM、entropy、masking、attention 等信号 | P0 | 部分 |
| M6. Cross-Dataset External Validation | 检查是否仅限 PRM800K/MATH | P1 | 是 |
| M7. Selective Policy / Risk-Coverage | 将 audit 转化为可操作系统结论 | P1 | 可复用现有数据 |
| M8. Hierarchical Statistics | 统一处理 step/problem/model 随机效应 | P1 | 否 |
| M9. Benchmark and Artifact Release | 提升 impact 与复现价值 | P0 | 否 |

---

# 5. Workstream M1：Actual-PRM Score Audit

## 5.1 动机

当前使用的是 PRM800K 的人工 rating。它代表 PRM supervision 的目标标签，但不等价于实际 PRM 模型在部署时输出的 score。

如果论文标题和结论使用 “PRM Scores”，必须直接回答：

> 不同实际 PRM 给出的 score，能否预测 dangerous deletion、beneficial deletion 和 pure semantic effect？

这是 ACL Main 版本最重要且最便宜的补强。

## 5.2 模型选择

至少选择 3 类可复现 PRM：

1. **标准 discriminative math PRM**  
   例如 Qwen2.5-Math-PRM-7B 或同等级公开模型。

2. **Reasoning/generative PRM**  
   例如 R-PRM 或 Process Reward Models That Think 的公开 checkpoint/实现。

3. **不同监督范式 PRM**  
   例如 Math-Shepherd 类 potential reward、uPRM 或其他无需人工标签的公开 PRM。

模型最终以可用 checkpoint、许可证和输入格式为准。若第三类部署困难，最低配置为两个结构不同的 PRM。

## 5.3 数据范围

第一阶段对已有全部 600 steps 打分。

每个 PRM 保存：

- raw score；
- normalized score；
- trajectory-relative percentile；
- target step 与前一步 score difference；
- target step 与 trajectory mean/min score difference；
- score confidence（若模型提供）。

## 5.4 评价任务

### Task A：预测 dangerous deletion

\[
Y_{\mathrm{danger}}
=
\mathbb{1}
[\mathrm{Control\ Correct}\rightarrow\mathrm{Target\ Wrong}]
\]

### Task B：预测 beneficial deletion

\[
Y_{\mathrm{benefit}}
=
\mathbb{1}
[\mathrm{Control\ Wrong}\rightarrow\mathrm{Target\ Correct}]
\]

### Task C：预测 step-level average effect

\[
\bar{\Delta}_i
=
\frac{1}{K}
\sum_{j=1}^{K}
(Y^{\mathrm{target}}_{ij}-Y^{\mathrm{control}}_{ij})
\]

### Task D：预测 placebo-corrected semantic effect

仅在 511 matched steps 上：

\[
\Delta^{\mathrm{semantic}}_i
=
\Delta^{\mathrm{target}}_i
-
\Delta^{\mathrm{placebo}}_i.
\]

## 5.5 指标

- Spearman correlation；
- AUROC；
- AUPRC；
- Brier score；
- ECE；
- risk-coverage curve；
- dangerous deletion rate at fixed coverage；
- coverage at fixed harm budget（1%、3%、5%）。

## 5.6 必须比较的 baselines

- PRM800K discrete rating；
- human-calibrated Step Type；
- initial Step Type；
- static context features；
- actual PRM continuous scores；
- actual PRM ensemble mean / disagreement。

## 5.7 成功标准

满足任一即可形成有价值结果：

1. 实际 PRM score 仍不能可靠预测 removability：加强“PRM is not policy”。
2. 某些 PRM 明显优于 dataset rating：形成“不同 PRM supervision paradigms 对 removability 的差异”。
3. PRM ensemble disagreement 能识别危险删除：形成 uncertainty-based abstention 结果。
4. PRM score 能排序 benefit 但不能排序 danger：形成 ranking-safety asymmetry。

## 5.8 输出

- `prm_score_matrix.csv`
- `prm_score_audit_report.md`
- PRM × task performance table
- PRM score calibration figure
- PRM disagreement × deletion risk figure

---

# 6. Workstream M2：Cross-Generator Replication

## 6.1 动机

当前 effect 可能部分来自 Qwen3-8B 对错误 prefix 的特定恢复能力。ACL Main 至少需要一个第二 generator。

## 6.2 推荐模型

### 最低配置

选择一个不同训练路径的 7B–14B reasoning model，例如：

- DeepSeek-R1-Distill-Qwen-7B/14B；
- 或其他可稳定输出数学 continuation 的开源 reasoning model。

### 理想配置

再加入一个同家族不同规模模型，例如 Qwen3-14B，以区分：

- family effect；
- scale effect；
- generic generator effect。

## 6.3 样本设计

最低 300 steps：

- rating \(=-1,0,1\) 各 100；
- early/middle/late 平衡；
- human-calibrated Essential/Redundant/Harmful 尽量平衡；
- 至少 100 个 rating \(=-1\)\(\times\)Harmful；
- 至少 80 个 control-stable-correct steps；
- placebo eligible 和 skipped 状态记录。

若资源不足，最低可用 240 steps：

- 每个 rating 80；
- 关键 negative-anchor 组不少于 80；
- stable-correct 组不少于 60。

## 6.4 条件

每个 step：

1. Control；
2. Target deletion；
3. Position-and-length-matched placebo deletion。

每个条件至少 3 runs；理想为 4 runs。

## 6.5 主要分析

- 每个 generator 单独的 target effect；
- pure semantic effect；
- rating/type heterogeneity；
- generator × intervention interaction；
- step-level effect sign agreement；
- negative-anchor case transfer rate。

## 6.6 统计模型

建议使用 mixed-effects logistic model：

\[
\operatorname{logit}P(Y_{ijgm}=1)
=
\beta_0
+
\beta_1 D
+
\beta_2 R
+
\beta_3 T
+
\beta_4 G
+
\beta_5 D\times G
+
u_{\mathrm{step}}
+
u_{\mathrm{problem}}.
\]

其中 \(G\) 为 generator。

同时保留 step-level cluster bootstrap，便于与原实验一致。

## 6.7 成功标准

### 强成功

- 第二 generator 上 Overall 或 low-rated harmful pure semantic effect 同方向且 CI 不跨 0；
- cross-generator sign agreement 明显高于随机；
- generator interaction 不改变主结论。

### 可接受

- overall effect 大小不同，但 low-rated harmful enrichment 仍存在；
- 结论改写为“effect magnitude is generator-dependent, but PRM-policy mismatch generalizes”。

### Pivot

若第二 generator 完全不复现：

> Removability is not an intrinsic property of a step alone; it is a property of the step-generator pair.

这依然是重要 finding，但论文标题和理论必须转向 **conditional removability**。

---

# 7. Workstream M3：Human Semantic Annotation

## 7.1 动机

当前两套 Step Type labels 有 164/600（27.3%）不同。若 Essential/Redundant/Harmful 是论文核心概念，需要直接的人类一致性证据。

## 7.2 最低方案

双人独立标注 300 steps：

- 100 个 diagonal cases；
- 100 个 off-diagonal cases；
- 100 个随机样本；
- 覆盖所有 rating/type/position；
- annotator 不可看到 PRM rating、deletion outcome 和旧标签。

## 7.3 理想方案

全部 600 steps 双人独立标注，分歧由第三人 adjudicate。

## 7.4 标签体系

建议四类：

1. Essential；
2. Redundant；
3. Harmful；
4. Uncertain / context-dependent。

不要强迫所有步骤进入三分类。Uncertain 本身可用于分析 deletion instability。

## 7.5 Annotation protocol

每个 annotator 可见：

- problem；
- reasoning prefix；
- target step；
- original downstream trajectory。

不可见：

- rating；
- Control/Target/Placebo outcomes；
- generator answer correctness；
- previous AI label。

## 7.6 评价

- raw agreement；
- Cohen’s \(\kappa\)；
- Gwet’s AC1（类别不平衡时更稳）；
- per-class precision/recall；
- disagreement taxonomy；
- label sensitivity analysis。

## 7.7 成功标准

- raw agreement \(\geq 80\%\)；
- \(\kappa\) 或 AC1 \(\geq 0.65\)；
- adjudicated human labels 上 low-rated harmful effect 方向保持；
- Uncertain 类显著富集 mixed/unstable outcomes。

## 7.8 若一致性较低

不要隐藏。将其转为 finding：

> Semantic contribution itself is underdetermined from a single fixed trajectory, motivating intervention-based rather than label-only evaluation.

---

# 8. Workstream M4：Strengthened Intervention Controls

## 8.1 当前 placebo 的不足

- 511/600 可匹配；
- position 最大 SMD 为 0.298；
- placebo run 数与 control/target 不完全对称；
- placebo 删除位置与 target 位置不完全一致；
- 只能粗略估计 generic restart。

## 8.2 Strong-Control 子集

选择 240 steps：

- 80 个 rating \(=-1\)\(\times\)Harmful；
- 80 个 stable-correct / dangerous candidates；
- 80 个 rating \(=0/1\) 的 neutral comparison；
- position、step length、prefix length 平衡。

## 8.3 四条件设计

### C0：Control

保留原 target step。

### C1：Target deletion

删除 target step。

### C2：Position-and-length-matched placebo

在尽量相同 relative position 删除长度接近的其他 step。若无法匹配则不纳入 primary matched estimand。

### C3：Semantic-preserving paraphrase

用独立模型对 target step 做保持数学含义的 paraphrase：

- 不改变结论；
- 不添加新信息；
- 近似保持长度；
- 人工抽查语义保真度。

## 8.4 解释

- C1 vs C0：raw deletion effect；
- C2 vs C0：generic deletion/restart effect；
- C1 vs C2：target-specific deletion effect；
- C3 vs C0：surface-form sensitivity；
- C1 vs C3：移除语义内容相对于保留语义的作用。

对于 Harmful steps，若 paraphrase 保留错误语义，则 C3 应接近 Control，而 deletion 应改善。这是 negative anchor 机制的强证据。

## 8.5 Runs

每个条件 4 runs。原 Qwen3-8B 的 C0/C1 可复用，新增：

\[
240\times 4\times 2=1,920
\]

次 placebo/paraphrase runs。

## 8.6 Paraphrase validity audit

- 人工检查至少 120 个 paraphrases；
- 标注 meaning preserved / partially changed / changed；
- primary analysis 仅保留 meaning-preserved；
- 报告 exclusion rate。

## 8.7 成功标准

对于 rating \(=-1\)\(\times\)Harmful：

\[
\mathrm{Acc}(C1)
>
\mathrm{Acc}(C2),
\]

且：

\[
\mathrm{Acc}(C1)
>
\mathrm{Acc}(C3).
\]

若 C3 与 C0 相近，而 C1 提升，则最支持“错误语义本身形成 anchor”。

## 8.8 可能 Pivot

- 若 C3 也明显改善：说明 wording/surface form 而非纯语义可能驱动 effect。
- 若 C2 与 C1 相同：说明 restart 是主要机制。
- 若不同 generator 呈不同模式：说明 removability 是 generator-conditional。

---

# 9. Workstream M5：Signal Baseline Comparison

## 9.1 目的

ACL Main 不应只说明 PRM 不足，还应回答：

> 哪一类信号更接近 removability？

## 9.2 P0 baselines

### B1：Actual PRM scores

来自 M1。

### B2：Step entropy

计算 target step 内 token predictive entropy 或 average negative log probability。

测试低 entropy 是否更像 Redundant，以及 entropy 是否预测 danger/benefit。

### B3：Counterfactual answer-probability drop

对 target step 做 mask/ablation，测量正确答案概率变化：

\[
I_{\mathrm{mask}}
=
\log p(y^\star\mid h)
-
\log p(y^\star\mid h\setminus s_t).
\]

这是 outcome-oriented importance signal。

### B4：Simple structural baselines

- target step length；
- position；
- prefix length；
- lexical repetition；
- similarity to prior steps；
- equation/entity overlap with downstream reasoning。

## 9.3 P1 baseline

### Attention-based contribution

根据模型可访问性，计算 target step tokens 对 answer/end-of-reasoning tokens 的 attention contribution。

由于 attention implementation 和层聚合选择较多，只有在代码成熟时加入，不应拖延主实验。

## 9.4 统一比较

预测：

- dangerous deletion；
- beneficial deletion；
- stable beneficial；
- pure semantic effect sign。

评价：

- AUROC / AUPRC；
- risk-coverage；
- calibration；
- compute cost；
- cross-generator transfer。

## 9.5 预期核心表

| Signal | Requires PRM | Requires answer | Requires extra generation | Danger AUPRC | Benefit AUPRC | Cross-model |
|---|---:|---:|---:|---:|---:|---:|
| PRM rating | No | No | No | | | |
| Actual PRM | Yes | No | No | | | |
| Step entropy | No | No | No | | | |
| Mask probability drop | No | Yes | Forward pass | | | |
| Trajectory state | No | Yes | Multiple runs | | | |

## 9.6 Main-level finding 目标

最理想的结果不是必须提出新 SOTA，而是形成清楚的 trade-off：

> Cheap local correctness signals are poorly calibrated for deletion risk; outcome-conditioned counterfactual signals are more informative but computationally expensive.

---

# 10. Workstream M6：Cross-Dataset External Validation

## 10.1 推荐数据集

### 首选：ProcessBench

优势：

- 人工标注 first erroneous step；
- 轨迹来自多种模型；
- 覆盖 GSM8K、MATH、OlympiadBench、Omni-MATH；
- 能测试不同难度和 source-model trajectories。

### 备选：PRMBench

优势：

- 大量 fine-grained step labels；
- 包含 simplicity、soundness、sensitivity 等维度；
- 与 contribution/removability 的概念区分更贴近。

### 资源允许时

ProcessBench 做主 external validation，PRMBench 做小规模辅助。

## 10.2 ProcessBench 抽样

300 target steps：

- 150 个 first-error / incorrect steps；
- 150 个 locally correct steps；
- 四个 source datasets 尽量平衡；
- early/middle/late 平衡；
- source model 平衡；
- 不从同一 trajectory 抽过多步骤。

## 10.3 条件

最低：

- Control；
- Target deletion；
- position-and-length-matched placebo；
- 每条件 3 runs。

## 10.4 研究问题

- incorrect step 是否富集 beneficial deletion？
- correct step 是否等价于 non-removable？
- low PRM model score 是否在新数据上预测 danger/benefit？
- negative-anchor effect 是否随题目难度和 source model 变化？

## 10.5 成功标准

- correctness–removability mismatch 在第二数据源继续存在；
- 至少一个外部子群复现 target-specific beneficial deletion；
- PRM score/rating 的排序趋势跨数据源大致一致。

## 10.6 若外部数据不复现

转为更精准结论：

> The mismatch is strongest in trajectories produced under PRM800K-style supervision and is not universal across reasoning datasets.

这仍然有价值，但必须缩小泛化范围。

---

# 11. Workstream M7：Selective Policy 与 Risk-Coverage

## 11.1 动机

当前结论“不能直接删”是负面的。ACL Main 版本最好给出可操作的选择性策略评价，即使不提出复杂新模型。

## 11.2 Policy baselines

1. Random deletion；
2. rating \(=-1\) threshold；
3. Harmful-only；
4. rating \(=-1\)\(\times\)Harmful；
5. actual PRM score threshold；
6. PRM ensemble + abstention；
7. counterfactual importance threshold；
8. state-aware oracle upper bound。

## 11.3 评价方式

在 coverage \(c\) 下：

- net accuracy change；
- dangerous deletion rate；
- beneficial deletion yield；
- rollback frequency；
- compute cost；
- calibration。

核心图：

- x-axis：deletion coverage；
- y-axis：harm rate / net accuracy；
- 多条 policy curves。

## 11.4 固定安全预算

报告：

- 在 1% harm budget 下可删除多少 steps；
- 在 3% harm budget 下可删除多少 steps；
- 在 5% harm budget 下可删除多少 steps。

## 11.5 Rollback simulation

简单离线策略：

1. 选择候选 step；
2. 生成删除 continuation；
3. 若 verifier/answer confidence 下降，则回退 Control；
4. 否则接受 deletion。

比较：

- accuracy；
- compute multiplier；
- acceptance rate；
- residual harm。

## 11.6 结论边界

若所有 cheap policy 都无法在合理 coverage 下控制 harm，这本身是强 finding：

> Reliable pruning requires expensive validation, eliminating much of the presumed efficiency benefit.

---

# 12. Workstream M8：统计模型与敏感性

## 12.1 Primary estimands

提前固定：

1. Full-cohort target effect；
2. Matched-cohort pure semantic effect；
3. low-rated harmful pure semantic effect；
4. cross-generator interaction；
5. cross-dataset interaction；
6. harm at fixed policy coverage。

## 12.2 Hierarchical model

加入：

- random intercept for problem；
- random intercept for target step；
- fixed effects for generator、dataset、rating、type、intervention；
- key interactions。

## 12.3 Multiple comparisons

主文只保留预设 5–6 个 hypotheses。其他 slicing 标注 exploratory，并使用 FDR 或仅报告 CI，不依据单独 p-value 讲故事。

## 12.4 Sensitivity

- Judge label substitution；
- human-label-only subset；
- initial vs calibrated Step Type；
- matched vs full cohort；
- 3-run vs 4-run estimates；
- excluding abnormal continuations；
- excluding paraphrase failures；
- one-step-per-problem subset。

## 12.5 Power check

在跑 cross-model 和 cross-dataset 前，用现有效应和 ICC 做 simulation-based power analysis，避免继续抽取不足以区分 5–8 pp effect 的样本。

---

# 13. Workstream M9：Benchmark 与 Artifact

## 13.1 建议发布内容

### Data

- target step IDs；
- problem and prefix；
- PRM800K rating；
- actual PRM scores；
- human semantic labels；
- Control/Target/Placebo/Paraphrase outputs；
- automatic + audited correctness；
- completion status；
- step-level effects；
- generator metadata。

### Code

- intervention builder；
- matched-placebo selector；
- PRM scoring adapters；
- answer evaluator；
- cluster bootstrap；
- hierarchical model；
- risk-coverage analysis；
- figure/table generation。

### Documentation

- dataset card；
- annotation guide；
- model/license table；
- limitations；
- reproducibility README；
- single numeric source。

## 13.2 数据拆分

若希望形成 benchmark：

- train/development：可公开 outcomes；
- test：隐藏部分 intervention labels，提供 evaluation script；
- 按 problem 划分，防止同题泄漏。

## 13.3 命名建议

- **PRM-Rem**
- **StepRem**
- **RemovabilityBench**

---

# 14. 样本量、生成量和预算

## 14.1 推荐最低 ACL Main 配置

| 模块 | Steps | Conditions/Runs | 预计新 generations |
|---|---:|---:|---:|
| Strong controls on Qwen3-8B | 240 | 新增 placebo + paraphrase，各 4 runs | 1,920 |
| Second generator replication | 300 | 3 conditions × 3 runs | 2,700 |
| ProcessBench external validation | 300 | 3 conditions × 3 runs | 2,700 |
| Paraphrase generation | 240 | 1–2 candidates | 240–480 |
| 合计 | — | — | 约 7,560–7,800 |

Actual PRM scoring 和 entropy/masking forward passes 不计入 autoregressive generation 数。

## 14.2 资源紧张版本

- Second generator：240 steps；
- ProcessBench：200 steps；
- Strong controls：180 steps；
- 每条件 3 runs。

预计约 4,000–5,000 新 generations。

## 14.3 不推荐的资源使用

- 不要把所有预算用于把原 600 steps 从 4 runs 提升到 16 runs；
- 不要在没有外部验证前继续只扩 PRM800K；
- 不要训练大型 verifier 再用同一数据测试；
- 不要优先做多步连续删除；
- 不要用更多 token analysis 替代 correctness/safety evidence。

---

# 15. 分阶段执行时间表

## Phase 0：2026-07-24 至 2026-08-03 — ARR 冻结与低成本增强

目标：保持 A–F READY_TO_FREEZE，完成可在截止前落地的便宜分析。

### 必做

- 完成 2–3 个 actual PRM 对 600 steps 的评分；
- 运行 PRM score audit；
- 完成第二位人工数字签字；
- 统一两套 Step Type 命名；
- 写完 4 页 ARR short 或 8 页初版；
- artifact 匿名化；
- 完成 Limitations 与 Judge sensitivity。

### 尽量做

- 启动 120-step human double annotation pilot；
- 运行 risk-coverage baseline；
- 完成 strong-control 采样和代码 sanity check。

### 不要求在 8 月 3 日前完成

- 第二 generator 全量；
- cross-dataset；
- 全部 600 人工双标；
- 完整 benchmark release。

## Phase 1：2026-08-04 至 2026-08-24 — Cross-Generator + Human Labels

- 完成 300-step second-generator replication；
- 完成至少 300-step 双人标注；
- 运行 cross-generator mixed-effects；
- 完成 strong-control 四条件实验；
- 冻结 negative-anchor mechanism。

## Phase 2：2026-08-25 至 2026-09-20 — Cross-Dataset + Signal Baselines

- 完成 ProcessBench 300-step external validation；
- 完成 entropy 和 masking baselines；
- 比较 actual PRMs；
- 完成 policy risk-coverage；
- 整理 external qualitative cases。

## Phase 3：ARR Reviews 后 — ACL Main 重写

ARR 2026 年 8 月 cycle 的评审可作为第一轮外部反馈。根据 reviews：

- 补充 reviewer 指出的 critical baseline；
- 冻结 8 页 long-paper story；
- 扩充 related work 和 theory framing；
- 完成公开 artifact；
- 决定是否进入后续 ARR cycle。

ACL 2027 官方 submission 和 commitment 日期目前尚未公布，因此此阶段以“结果质量完成”为里程碑，而不是假设具体 ACL deadline。

---

# 16. 人员分工

## 新手同学

- actual PRM scoring pipeline；
- human annotation 界面与数据整理；
- strong-control 数据生成；
- ProcessBench 数据清洗；
- qualitative case records；
- artifact README。

## 你/项目负责人

- hypothesis freeze；
- sampling 和 estimand 审核；
- annotation guideline；
- statistical design；
- main figures；
- paper framing；
- reviewer-facing claim boundary。

## 第二标注者

- blind human Step Type annotation；
- paraphrase semantic-validity audit；
- disagreement adjudication。

## 可选高级合作者

重点请其 review：

- causal interpretation；
- mixed-effects / selection bias；
- related-work novelty；
- ACL main narrative。

---

# 17. 每个 Workstream 的 Go/No-Go

| Workstream | Go 标准 | 若不通过 |
|---|---|---|
| Actual PRM audit | 至少 2 个 PRM 成功打分且输入格式可比 | 降级为 1 个 PRM + dataset label，标题避免复数 scores |
| Cross-generator | 关键组方向复现或明确 model interaction | 转向 conditional removability |
| Human annotation | agreement ≥80%，AC1/κ ≥0.65 | 将语义类型降级为 exploratory，强调 intervention |
| Strong controls | target 超过 placebo/paraphrase，或得到清晰机制差异 | 转向 restart/surface confound paper |
| Cross-dataset | mismatch 或 anchor 至少部分复现 | 缩小到 PRM800K/MATH-specific audit |
| Signal baseline | 至少形成清晰 cost-safety trade-off | 保留 negative result：无 cheap signal 足够 |
| Selective policy | 固定 harm budget 下优于 rating threshold | 强调 validation cost 与不适合部署 |

---

# 18. 最终 ACL Main 结果包的最低标准

为了有较真实的 ACL Main 竞争力，建议至少达到以下 6 项中的 5 项：

1. **实际 PRM 模型审计：** 至少 2–3 个公开 PRM；
2. **跨 generator：** 至少第二个 reasoning model；
3. **直接人工语义标注：** 至少 300 steps 双标；
4. **严格干预控制：** matched placebo + semantic-preserving paraphrase；
5. **外部数据：** ProcessBench 或 PRMBench 至少一个；
6. **统一 benchmark/policy comparison：** PRM、entropy、masking 和 risk-coverage。

其中第 1、2、3、4 项最重要。若缺少其中两个以上，论文仍更接近强 Findings，而不是稳健 Main。

---

# 19. 建议的 8 页论文结构

## Page 1：Introduction

- correctness vs removability；
- 为什么 PRM score 不等于 deletion policy；
- negative anchors；
- placebo 与 restart；
- contributions。

## Page 2：Related Work + Definitions

- PRM / PRMBench / ProcessBench；
- reasoning pruning；
- functional importance；
- PAV / causal credit；
- 定义四个 constructs。

## Page 3：Benchmark and Intervention Protocol

- datasets；
- generators；
- actual PRMs；
- Control/Target/Placebo/Paraphrase；
- human annotation；
- Judge audit。

## Page 4：Main Full-Cohort Results

- overall；
- rating/type；
- cross-generator；
- cross-dataset。

## Page 5：Mechanism Decomposition

- target/placebo/paraphrase；
- negative anchors；
- restart effect；
- qualitative cases。

## Page 6：Which Signals Predict Removability?

- PRM scores；
- entropy；
- masking；
- state；
- danger/benefit。

## Page 7：Selective Policy and Safety

- risk-coverage；
- harm budget；
- rollback；
- compute trade-off。

## Page 8：Discussion and Conclusion

- conditional removability；
- limitations；
- implications for PRM training and reasoning systems。

---

# 20. 最终建议

当前项目**不是没有实验需要做**。准确的判断是：

- 对 2026 年 8 月 ARR：A–F 已经足够冻结和投稿；
- 对 ACL Main：还需要从“单数据、单 generator、标签审计”升级为“实际 PRM、跨模型、跨数据和严格干预”的系统研究。

最高优先级顺序应为：

1. **Actual PRM Score Audit**
2. **Second Generator Replication**
3. **Human Double Annotation**
4. **Matched Placebo + Paraphrase Strong Controls**
5. **Counterfactual/Entropy Baseline Comparison**
6. **ProcessBench External Validation**
7. **Risk-Coverage and Benchmark Release**

不要先训练新 verifier，也不要继续以 token saving 作为主线。

最有机会冲 ACL Main 的最终故事是：

> **Reasoning-step removability is neither an intrinsic consequence of local correctness nor a property captured reliably by current PRMs. Across verifiers, generators, and datasets, low-rated harmful steps are enriched for negative anchors, but raw deletion gains combine target semantics with restart effects and retain non-negligible safety risk. Reliable pruning therefore requires counterfactual validation and selective abstention rather than score thresholding.**

---

# References and Positioning Checklist

- Lightman et al. *Let’s Verify Step by Step*.
- Setlur et al. *Rewarding Progress: Scaling Automated Process Verifiers for LLM Reasoning*.
- Song et al. *PRMBench: A Fine-grained and Challenging Benchmark for Process-Level Reward Models*.
- Zheng et al. *ProcessBench: Identifying Process Errors in Mathematical Reasoning*.
- Choi et al. *Think Clearly: Improving Reasoning via Redundant Token Pruning*.
- Singh and Hakkani-Tür. *Do LLMs Encode Functional Importance of Reasoning Tokens?*
- Li et al. *Compressing Chain-of-Thought in LLMs via Step Entropy*.
- Khandoga et al. *Beyond Uniform Credit: Causal Credit Assignment for Policy Optimization*.
- Liang et al. *Step-level Trace Evaluation and Pruning for Efficient Test-Time Reasoning*.
- Khalifa et al. *Process Reward Models That Think*.
