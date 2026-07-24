# Workstream M4:Strong-Control 240-Step 采样

按 ACL Main 计划 8.2 节从冻结的 600-step 主表抽取三个互斥组(各 80 步):

- `negative_anchor`:rating = -1 且 human-calibrated Harmful;
- `stable_correct`:control 4/4 correct(dangerous deletion 候选),不含 A 组;
- `neutral_comparison`:rating 0/1 且 control 非 4/4,不含 A 组。

组内按 position bin 配额(~27/27/26)平衡,优先选择 placebo-eligible steps
(C2 条件需要 position-and-length-matched placebo),stable hash 确定性排序,可复现。

## 采样结果

- 组大小:{'negative_anchor': 80, 'stable_correct': 80, 'neutral_comparison': 80}
- 采样池:{'negative_anchor': 160, 'stable_correct': 258, 'neutral_comparison': 155}
- position 分布:{"negative_anchor": {"early": 27, "middle": 27, "late": 26}, "stable_correct": {"early": 27, "middle": 27, "late": 26}, "neutral_comparison": {"early": 27, "middle": 27, "late": 26}}
- placebo eligible:{'negative_anchor': 80, 'stable_correct': 80, 'neutral_comparison': 80}
- sanity check:PASS

## 四条件设计与新生成预算

| 条件 | 说明 | Runs | 来源 |
|---|---|---:|---|
| C0 Control | 保留原 target step | 4 | 复用已有 runs |
| C1 Target deletion | 删除 target step | 4 | 复用已有 runs |
| C2 Matched placebo | 位置+长度匹配的其他 step 删除 | 4 | 新生成 |
| C3 Semantic-preserving paraphrase | 独立模型保义改写 | 4 | 新生成 |

新增 continuation runs:240 x 4 x 2 = **1920**;
paraphrase 生成:**240** 条(1 candidate/step,失败再补)。

## 输出文件

- `strong_control_sampling_manifest.csv`:240 步采样清单;
- `strong_control_balance.csv`:三组间 position/step length/prefix length 的 SMD;
- `strong_control_paraphrase_inputs.jsonl`:C3 paraphrase 生成输入;
- `strong_control_summary.json`:参数、配额与 sanity check 结果。

## 已知边界

- `negative_anchor` 组 target step 天然长于 `stable_correct` 组(target_tokens SMD ~0.7),
  这是两组定义带来的池子属性,不是采样缺陷;主 estimand 是同一 step 内 C0-C3 的
  within-step 对比,组间长度差异不进入该对比。跨组比较时按组分层报告,不做直接合并。

## 后续动作

1. C3 paraphrase 用独立模型(非 Qwen3-8B)生成,人工抽查至少 120 条语义保真;
2. C2 placebo 复用 `select_placebo_steps.py` 的匹配逻辑,对 89 个不可匹配步骤记录排除;
3. 新 runs 完成后按 C1-C2(target-specific)、C1-C3(semantic-content)分解机制。
