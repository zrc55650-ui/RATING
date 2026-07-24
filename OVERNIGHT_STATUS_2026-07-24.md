# 通宵执行终报(2026-07-24 04:10 完成)

**全部可自动化的 M 工作流已跑完,论文已按新结果重写并编译。**
产出:`paper/acl_latex.pdf`(9 页:7 页正文 + Limitations/Ethics/References/附录,ACL 8 页上限内)。
总计新增 ~6,965 次生成 + ~1,200 次 PRM 打分 + 全部 judge 调用;服务器只用了 GPU 6/7,已全部释放。

## 各 Workstream 最终结果

### M1 实际 PRM 打分 ✅(3 个 PRM,超计划最低配置)
- Qwen2.5-Math-PRM-7B(真 checkpoint,A100):600/600;danger AUROC 0.57 ≈ 数据集 rating(0.56);
- gemini-2.5-flash / phi-4(LLM-judge PRM):均近随机;
- **ensemble disagreement 是最好的 benefit 信号**(AUPRC 0.38 vs 基率 0.24)→ abstention 结论成立。

### M2 跨 generator 复制 ✅(计划 §6.7「强成功」档)
- phi-4,300 步 × 3 条件 × 3 runs,2,691 条 100% 解析;
- overall target +12.4pp [8.3,16.8];anchor 组 semantic **+18.3pp [10.7,26.0]**(同向、CI 不跨 0);
- rating 0/1 ≈ 0 复现;符号一致率 65%;anchor×generator 交互 +15.1pp [3.6,26.8]
  → 方向普适、幅度依赖 generator。
- ⚠️ 选型变更:DeepSeek-R1-Distill 系在 OpenRouter 不可用/烧穿预算,改用 phi-4(论文脚注披露)。

### M4 强控制四条件 ✅(§8.7 强证据模式全命中)
- Anchor 组:C3(保义改写)≈C0(+1.7pp)而 C1>C2 +15.6pp、C1>C3 +19.2pp → **错误语义即 anchor**;
- Neutral 脆弱组:raw +24.1pp 但 C1−C2=0.0 → 纯 restart;
- Stable-correct:删除 −11.9pp,paraphrase 也 −8.3pp;
- paraphrase 排除率 7.9%(221/240);人工保真抽查(120 条)待做。

### M6 ProcessBench 外部验证 ✅
- 300 步(150+150,四子集平衡,12 个源模型),gold 99.5% 源数据集匹配;
- first-error semantic **+19.4pp [10.2,28.3]**;locally-correct ≈0;overall semantic +8.2 ≈ 主研究 +8.6;
- 难度梯度:GSM8K/MATH 语义效应显著,OlympiadBench 衰减,Omni-MATH restart 主导;
- ⚠️ 修复过一个采样 bug(label≥2 记录双重采样致 46 步 taskId 冲突):
  已去重清洗 + 补生成 708 条,污染文件留档 `*.contaminated.bak`;M2/M4 排查为 0 重复。

### M5 信号 baselines ✅
- entropy/NLL ≈ 随机(0.46–0.50);mask answer-prob drop 0.56/0.19(唯一有效的 answer-conditioned 信号)。

### M7 扩展 ✅
- 真 PRM 阈值 1% budget 只能删 20 步(gemini 0 步)→「不是 rating 的锅,是 correctness 信号类的锅」;
- **rollback:1 次探针生成把受伤步骤 12.2%→3.0%,净收益 +7.2→+11.5pp**。

### M8 统计 ✅
- power:现设计观测效应下 0.78–0.88;效应缩 60% 时 ~0.65–0.74;
- cluster-robust logistic:anchor×delete OR 1.97 [1.33,2.94];
- 跨 generator 配对交互分析入 `workstream_M8_statistics/`。

### M9 ✅
- `benchmark_steprem/`(432 dev/168 test 按 problem 划分 + eval 脚本 + dataset card);
- 论文全文重写:摘要/引言/协议/主结果(+跨 generator)/机制(+四条件表)/
  外部验证(新 §7)/信号(+Table 5)/策略(+PRM 阈值与 rollback)/Limitations 全部更新。

## 仍需要人做的(§18 六条现已满足 1/2/4/5/6 五条,唯缺第 3 条)

1. **M3 人工双标**:唯一未完成项(我不能替人标注)。材料在 `workstream_M3_human_annotation/`,
   发 sheet A/B 给两位标注者,key 文件勿外发;
2. M4 paraphrase 人工保真抽查 ≥120 条(第二标注者任务);
3. 第二位人工数字签字(Phase 0 必做);
4. 通读 `paper/acl_latex.pdf`(重点:摘要口径、phi-4 变更脚注、M6 采样修复是否需在文中说明);
5. 决定是否 commit(工作区全部变更未提交,git 白名单需扩充才能纳入新 workstream 目录)。
