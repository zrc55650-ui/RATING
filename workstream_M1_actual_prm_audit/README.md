# Workstream M1:Actual PRM Score Audit(打分管线,待 GPU/API 执行)

目标(计划 §5):用 2–3 个实际部署的 PRM 模型对全部 600 target steps 打分,
检验连续 PRM score 能否预测 dangerous / beneficial deletion 与 pure semantic effect。

## 状态(2026-07-24)

- ✅ `prm_scoring_input.jsonl`:600 条完整轨迹打分输入(problem + 全部 steps + target_index),
  已从 PRM800K 源数据重建并逐条验证;
- ✅ `score_with_qwen_prm.py`:discriminative PRM adapter(Qwen2.5-Math-PRM-7B 格式,
  `<extra_0>` 分隔符 + token-classification 头);**需要 GPU 机器**(bf16 约 15 GB VRAM);
- ✅ `score_with_generative_prm.py`:generative/LLM-judge PRM adapter,支持 OpenRouter
  (需 `OPENROUTER_API_KEY`)或本地 HF checkpoint(R-PRM / ThinkPRM 类);
- ✅ `analyze_prm_scores.py`:audit 分析(Task A–D:danger/benefit AUROC/AUPRC、
  Spearman vs step effect、matched-cohort semantic effect;自动纳入 ensemble
  mean/disagreement),自动发现本目录全部 `prm_scores_*.jsonl`;
- ⬜ 实际打分:本机(M1 Pro 16GB、无 torch)无法运行 7B PRM;等 GPU 或 API 凭证。

## 执行顺序(拿到算力后)

```bash
# 1. discriminative PRM(GPU 机器)
python score_with_qwen_prm.py --model Qwen/Qwen2.5-Math-PRM-7B

# 2. 第二个结构不同的 PRM(例如 Skywork-PRM / Math-Shepherd 类,按其模型卡改 adapter)
# 3. generative PRM(近似:reasoning LLM 作为 process judge;论文中需标注为 LLM-judge PRM)
export OPENROUTER_API_KEY=...
python score_with_generative_prm.py --backend openrouter --model deepseek/deepseek-r1-distill-qwen-14b

# 4. audit(在仓库根目录)
python workstream_M1_actual_prm_audit/analyze_prm_scores.py
```

所有 adapter 支持断点续跑(按 step_id 去重追加)。

## Go/No-Go(计划 §17)

至少 2 个 PRM 成功打分且输入格式可比 → Go;否则降级为 1 个 PRM + dataset label,
论文标题避免复数 "scores"。
