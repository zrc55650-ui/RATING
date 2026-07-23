# Step-Level Stability Report

本分析使用每个 target step 的 4 次 paired runs，类别定义在分组结果之前固定。它衡量 empirical consistency，不等同于个体步骤真实概率。

## Overall

| Category | Steps | Share |
|---|---:|---:|
| Strongly beneficial | 99 | 16.5% |
| Weakly beneficial | 33 | 5.5% |
| Strongly harmful | 57 | 9.5% |
| Weakly harmful | 25 | 4.2% |
| Mixed / unstable | 9 | 1.5% |
| Stable no-change | 377 | 62.8% |

## Key diagnostic groups

- `rating=-1 × Harmful`（analysis label）共 **178** steps：Strongly beneficial **51 (28.7%)**，Weakly beneficial **8 (4.5%)**，Mixed/unstable **3 (1.7%)**。
- Control 4/4 correct 共 **298** steps；其中至少出现一次纯伤害且无恢复的 step 为 **54 (18.1%)**。

## Interpretation

平均正效应不意味着每个 low-rated harmful step 都稳定获益。部署型 pruning 规则仍需要 trajectory-state validation 与 rollback。Placebo pure-semantic 分组仅限 eligible steps。

Audit-corrected stability labels 尚待人工 Judge Audit 完成后进行 sensitivity analysis。
