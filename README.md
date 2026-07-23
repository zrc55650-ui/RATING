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

