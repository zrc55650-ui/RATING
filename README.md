# PRM Scores Are Not Pruning Policies: A Counterfactual Study of Reasoning-Step Removability

反事实删除实验:PRM800K 高低分步骤在"删除后重新生成"下的真实可移除性。
目标投稿:ACL 2027 Main。论文源码与 PDF 见 [`paper/`](paper/)。

## 核心结论(全部数字以 `workstream_F_final_statistics/numbers_for_paper.json` 为准)

- **主研究(Qwen3-8B,600 步 / 2,400 对)**:删除 rating=-1 步骤整体 Δ +7.21pp [3.88, 10.58];
  full-cohort rating=-1 × human "Harmful" 锚点组 target +23.31pp [16.57, 30.24]；matched cohort 的 own-control DiD semantic +25.44pp [16.06, 34.88]。旧 shared-control pure semantic +8.55pp/+13.85pp 仅作为 legacy 对照。
- **跨 generator 复制(M2, phi-4)**:anchor 组 own-control DiD 语义效应 +34.9pp [25.8, 44.7]；旧 shared-control pure semantic +18.3pp 仅作为 legacy 对照保留。
- **强控制四条件(M4)**:保义改写 ≈ 保留(+1.7pp),删除 > 改写 +19.2pp → 错误语义本身就是 anchor。
- **外部验证(M6, ProcessBench)**:first-error 步骤 own-control DiD 语义效应 +35.4pp [22.8, 48.9]；raw target effect 为 +24.8pp，旧 shared-control pure semantic +19.4pp 仅作为 legacy 对照。
- **实际 PRM 审计(M1/M5/M7)**:真 PRM(Qwen2.5-Math-PRM-7B)对删除危险的 AUROC 仅 0.57;
  entropy/NLL 纯随机;1% 伤害预算下真 PRM 阈值策略只能删 20/600 步;
  1 次 rollback 探针把受伤步骤从 12.2% 降到 3.0%。
- **Judge 审计(A)**:200 条盲审后 judge–human 一致率 93.0%（186/200），hard-stop Gate PASS；整体审查等级为 `PASS_WITH_SENSITIVITY`，pair-transition agreement 为 90.0%。

## 目录结构

| 路径 | 内容 |
|---|---|
| `paper/` | ACL LaTeX 论文(`acl_latex.tex` / `acl_latex.pdf`)与图表 |
| `data/` | 冻结主数据:master 表(600 步 / 6,314 runs)、bootstrap 结果、生成记录、PRM800K 源、标注原始数据(`data/annotations/`) |
| `scripts/` | 全部分析与实验管线(纯标准库 Python;`legacy_powershell/` 为原始 Windows worker 存档) |
| `workstream_A_judge_audit/` | Judge 审计(200 条盲审、混淆矩阵、敏感性) |
| `predictive_analysis/` 等三个目录 | Workstream B/C/D:预测、稳定性、placebo 资格审计 |
| `workstream_E_qualitative_case_study/` | 8 个人工验证定性案例 |
| `workstream_F_final_statistics/` | 最终统计包:主表、四张主图、`numbers_for_paper.json`、一致性审计 |
| `workstream_M1_actual_prm_audit/` | 3 个实际 PRM 打分 + M5 信号(entropy/NLL/mask) |
| `workstream_M2_cross_generator/` | phi-4 跨 generator 复制(2,691 条生成) |
| `workstream_M3_human_annotation/` | 人工标注试点材料(盲审 sheet A/B;答案 key 不入库) |
| `workstream_M4_strong_controls/` | C0–C3 四条件强控制(含保义改写) |
| `workstream_M6_processbench/` | ProcessBench 外部验证(300 步 / 2,412 条生成) |
| `workstream_M7_policy_risk_coverage/` | 删除策略 risk–coverage、伤害预算、rollback 模拟 |
| `workstream_M8_statistics/` | 功效分析、cluster-robust logistic、generator 交互 |
| `benchmark_steprem/` | StepRem 基准发布包(432 dev / 168 test + 评测脚本) |
| `docs/` | 研究计划、执行方案、历史报告(中文) |
| `build/`(不入库) | 分析脚本的可再生中间产物 |
| `archive/`(不入库) | 原始 worker 分片、旧报告、标注 HTML 界面 |

## 快速复现

核心统计全部只用 Python 标准库,在仓库根目录运行:

```bash
python3 scripts/make_all_results.py      # 重建 Workstream B/C/D/E/F 全部统计、主表、主图
python3 workstream_M1_actual_prm_audit/analyze_prm_scores.py
python3 scripts/run_m8_statistics.py
python3 scripts/run_m2_pipeline.py analyze   # M4/M6 同理:run_m4_pipeline.py / run_m6_pipeline.py
```

生成类管线(`run_m2/m4/m6_pipeline.py` 的 generate/judge 子命令)需要 OpenRouter API key
(根目录 `.env` 中的 `OPENROUTER_API_KEY`,不入库);全部生成记录已冻结在各 workstream 目录,
分析可离线重跑。种子、环境与校验清单见 [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md),
布局细节见 [`WORKSPACE_LAYOUT.md`](WORKSPACE_LAYOUT.md),
最近一次全量执行报告见 [`OVERNIGHT_STATUS_2026-07-24.md`](OVERNIGHT_STATUS_2026-07-24.md)。
