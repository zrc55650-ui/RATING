# Workstream M7:Selective Deletion Policy Risk-Coverage Baseline

基于冻结的 600-step / 2,400-pair 主表离线评估固定删除策略。
danger 定义为 run-level Control Correct -> Target Wrong(每次删除动作的伤害率,
分母为被删 step 的全部 4 个 paired runs);net accuracy change 以 600-step 全 cohort 为分母。
预测器分数为 5-fold problem-level CV 的 out-of-fold 概率(model D = static context,
model E = trajectory state),排序分数为 P(benefit) - P(danger)。
model D 对无预测的 step(预测可得性本身编码 control 状态)以任务基率填补,
避免 static 策略泄漏 state 信息;model E 为显式 state-aware 策略,按事实填 0。
CI 为 step-level cluster bootstrap(5,000 次)。

## 策略自然工作点(natural set 或固定 coverage)

| Policy | Operating point | Steps | Coverage | Net Δacc (pp) | 95% CI | Danger/run | Benefit/run |
|---|---|---:|---:|---:|---|---:|---:|
| Random deletion | coverage_0.33 | 200 | 0.3333 | 2.4028 | analytic | 0.0850 | 0.1571 |
| Rating = -1 threshold | natural_set | 200 | 0.3333 | 7.3333 | [5.083, 9.667] | 0.0462 | 0.2662 |
| Rating = -1 threshold | coverage_0.33 | 200 | 0.3333 | 7.3333 | [5.083, 9.667] | 0.0462 | 0.2662 |
| Harmful-only (human-calibrated) | natural_set | 203 | 0.3383 | 6.0833 | [3.875, 8.417] | 0.0579 | 0.2377 |
| Harmful-only (human-calibrated) | coverage_0.33 | 200 | 0.3333 | 6.2500 | [4.042, 8.583] | 0.0537 | 0.2412 |
| Rating = -1 x Harmful | natural_set | 160 | 0.2667 | 5.5833 | [3.583, 7.708] | 0.0500 | 0.2594 |
| Rating = -1 x Harmful | coverage_0.33 | 200 | 0.3333 | 7.2917 | [5.125, 9.583] | 0.0450 | 0.2637 |
| Static predictor (model D) | coverage_0.33 | 200 | 0.3333 | 11.1250 | [8.792, 13.625] | 0.0100 | 0.3438 |
| Trajectory-state predictor (model E) | coverage_0.33 | 200 | 0.3333 | 10.6250 | [8.333, 13.042] | 0.0088 | 0.3275 |
| Oracle upper bound (observed effect) | coverage_0.33 | 200 | 0.3333 | 15.3333 | [12.792, 18.042] | 0.0037 | 0.4637 |

## 固定 harm budget 下的可删除量

| Policy | Budget | Max steps | Coverage | Net Δacc (pp) | Danger/run |
|---|---:|---:|---:|---:|---:|
| Random deletion | 1% | 0 | 0 |  |  |
| Random deletion | 3% | 0 | 0 |  |  |
| Random deletion | 5% | 0 | 0 |  |  |
| Rating = -1 threshold | 1% | 0 | 0 |  |  |
| Rating = -1 threshold | 3% | 50 | 0.0833 | 2.083 | 0.0250 |
| Rating = -1 threshold | 5% | 210 | 0.3500 | 7.583 | 0.0464 |
| Harmful-only (human-calibrated) | 1% | 0 | 0 |  |  |
| Harmful-only (human-calibrated) | 3% | 10 | 0.0167 | 0.292 | 0.0250 |
| Harmful-only (human-calibrated) | 5% | 180 | 0.3000 | 5.292 | 0.0458 |
| Rating = -1 x Harmful | 1% | 0 | 0 |  |  |
| Rating = -1 x Harmful | 3% | 10 | 0.0167 | 0.375 | 0.0250 |
| Rating = -1 x Harmful | 5% | 240 | 0.4000 | 8.000 | 0.0500 |
| Static predictor (model D) | 1% | 200 | 0.3333 | 11.125 | 0.0100 |
| Static predictor (model D) | 3% | 240 | 0.4000 | 12.000 | 0.0229 |
| Static predictor (model D) | 5% | 380 | 0.6333 | 11.125 | 0.0474 |
| Trajectory-state predictor (model E) | 1% | 210 | 0.3500 | 11.500 | 0.0083 |
| Trajectory-state predictor (model E) | 3% | 250 | 0.4167 | 12.000 | 0.0280 |
| Trajectory-state predictor (model E) | 5% | 280 | 0.4667 | 12.250 | 0.0437 |
| Oracle upper bound (observed effect) | 1% | 530 | 0.8833 | 14.750 | 0.0099 |
| Oracle upper bound (observed effect) | 3% | 550 | 0.9167 | 13.625 | 0.0227 |
| Oracle upper bound (observed effect) | 5% | 570 | 0.9500 | 11.792 | 0.0412 |

## 输出文件

- `policy_risk_coverage_curves.csv`:全部策略 x coverage 网格曲线数据;
- `policy_operating_points.csv`:自然工作点与固定 coverage 点(含 bootstrap CI);
- `policy_harm_budget.csv`:1%/3%/5% harm budget 下的最大可删除量;
- `policy_risk_coverage_danger.svg` / `policy_net_accuracy.svg`:主图;
- `policy_risk_coverage_summary.json`:参数与自然集合大小。

## 解读边界

- 本分析复用已冻结 runs,是 retrospective 评价,不涉及新生成;
- danger 率分母为删除动作(4 runs/step);以 control-correct runs 为分母的伤害率见
  `danger_rate_among_correct` 列,数值更高,结论方向一致;
- oracle 曲线使用观测效应排序,是不可部署的上界;
- random 策略为解析期望,无抽样 CI。
