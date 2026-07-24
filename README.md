# PRM800K Reasoning-Step Removability

本仓库包含 PRM800K 推理步骤删除实验的研究提案、可复核数据、Cluster Bootstrap 结果，以及长度匹配的 Placebo Deletion 分析。

## 主要文档

- [包含 Cluster Bootstrap 与 Placebo 结果的研究提案](PRM800K_Removability_Research_Proposal_CN_With_Cluster_Placebo_Results.md)
- [研究提案 PDF](PRM800K_Removability_Research_Proposal_CN_With_Cluster_Placebo_Results.pdf)

## 统计结果

所有置信区间均以 `step_id` 为聚类单位，进行 5,000 次 Cluster Bootstrap。

| 分析 | Markdown | CSV | HTML |
|---|---|---|---|
| Overall deletion metrics | [结果](qwen3-8b_cluster_bootstrap_metrics_5000.md) | [数据](qwen3-8b_cluster_bootstrap_metrics_5000.csv) | [表格](qwen3-8b_cluster_bootstrap_metrics_5000.html) |
| 分组 accuracy change | [结果](qwen3-8b_cluster_bootstrap_stratified_5000.md) | [数据](qwen3-8b_cluster_bootstrap_stratified_5000.csv) | [表格](qwen3-8b_cluster_bootstrap_stratified_5000.html) |
| Placebo / semantic effects | [结果](qwen3-8b_placebo_effects_5000.md) | [数据](qwen3-8b_placebo_effects_5000.csv) | [表格](qwen3-8b_placebo_effects_5000.html) |

分组分析覆盖：

- `step_position`：early / middle / late
- `step_length` 三分位：短 / 中 / 长
- `prefix_length` 三分位：短 / 中 / 长
- `control_correct_frequency`：0/4、1/4、2/4、3/4、4/4

Placebo 分析报告：

- Target Effect = `target_avg_correct - control_avg_correct`
- Placebo Effect = `placebo_avg_correct - control_avg_correct`
- Pure Semantic Effect = `target_avg_correct - placebo_avg_correct`

## 分析工作流与当前状态

- [`workstream_A_judge_audit/`](workstream_A_judge_audit/)：200 条 Judge
  Audit 及28条分歧盲审。复核后 Judge–human 一致率为 **88.0%（176/200）**，
  低于预设的90% Gate。
- [`predictive_analysis/`](predictive_analysis/)：按 `problem_id` 分组的
  5-fold CV，分别预测 dangerous deletion 与 beneficial deletion。
- [`step_stability_analysis/`](step_stability_analysis/)：四次 runs 下的稳定
  收益、稳定伤害和 mixed/unstable 分类。
- [`placebo_eligibility_analysis/`](placebo_eligibility_analysis/)：
  511 eligible 与89 skipped steps 的选择偏差审计。
- [`workstream_E_qualitative_case_study/`](workstream_E_qualitative_case_study/)：
  8/8 定性案例及78条人工复核输出。
- [`workstream_F_final_statistics/`](workstream_F_final_statistics/)：
  最终统计、主表、附录、四张主图、图源数据和一致性检查。

Workstream F 的技术一致性检查为 **PASS**，但 Judge Audit Gate 为
**FAIL**。因此自动 Judge 标签尚未冻结，结果数字应视为候选值，等待独立
第二 Judge、符号验证或关键子组的扩大人工复核。

## 数据文件

- `qwen3-8b_deletion_pairs.csv`：600 个 target steps × 4 次 runs，共 2,400 个配对结果。
- `qwen_deletion_generations.jsonl`：Control 与 Target Deletion 的生成记录。
- `qwen3-8b_placebo_selection.jsonl`：按目标步骤长度 ±20% 匹配的 Placebo 选择结果。
- `qwen3-8b_placebo_effects_5000_placebo_runs.csv`：1,514 次 Placebo Deletion 的汇总记录。
- `qwen3-8b_placebo_effects_5000_step_effects.csv`：以 target step 聚合后的效应数据。

## 复现

PowerShell 7 示例：

```powershell
pwsh ./run_cluster_bootstrap.ps1 -Replicates 5000
pwsh ./run_cluster_bootstrap_stratified.ps1 -Replicates 5000
pwsh ./run_placebo_effect_bootstrap.ps1 -Replicates 5000
```

Placebo 选择脚本使用 Qwen3 tokenizer：

```powershell
python ./select_placebo_steps.py
```

调用 OpenRouter 的生成与 judge 脚本从环境变量 `OPENROUTER_API_KEY` 读取密钥。仓库不包含 API key、请求临时文件、worker 日志或原始 API 分片。

Workstream F 的 Python 主流程不依赖第三方 Python 包。一键重建：

```powershell
uv run --no-sync python ./make_all_results.py
```

该命令从两张 master tables 与已冻结的 5,000 次 bootstrap CSV 生成 predictive、
stability、eligibility、qualitative candidates、主表、主图源文件和
`numbers_for_paper.json`。PDF 图可随后运行：

```powershell
uv run --no-sync python ./export_figures_pdf.py
```

完整环境、随机种子、输入输出和验证说明见
[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)。
