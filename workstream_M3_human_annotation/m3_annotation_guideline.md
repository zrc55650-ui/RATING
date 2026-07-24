# M3 Pilot 标注指南(120 steps,双人独立盲标)

## 任务

对每个 TARGET STEP,仅根据 problem、之前的推理(prefix)和原始下游轨迹,
判断该步骤对解题的语义贡献,四选一:

- **essential**:删除该步会丢失后续推理需要的关键信息或关键推进;
- **redundant**:该步重复已有信息、纯过渡或不影响后续推理;
- **harmful**:该步引入错误、误导方向或把推理锚定在坏路径上;
- **uncertain**:贡献依赖无法判断的上下文,或多种解读均合理。

## 规则

1. 独立完成,不与另一位标注者讨论;
2. 只看 sheet 内提供的文本;不查询 PRM 分数、删除实验结果或任何旧标签;
3. `confidence_1to5`:1=非常不确定,5=非常确定;
4. 不要强行三分类:确实无法判断时用 uncertain 并在 notes 说明;
5. 每完成 30 条休息一次,避免疲劳漂移;
6. 完成后只回传 CSV(三列填写完毕),不要改动其他列。

## 材料

- `m3_pilot_sheet_A.csv` / `m3_pilot_sheet_B.csv`:两位标注者各自的表(顺序不同);
- 同名 `.html`:阅读视图(与 CSV 行一一对应,以 annotation_id 对齐);
- `m3_pilot_key_DO_NOT_SHARE.csv`:仅项目负责人保存,用于回链 step_id 与计算一致性。

## 评价(标注完成后)

raw agreement、Cohen's kappa、Gwet's AC1、per-class precision/recall、
分歧类型学;pilot 通过标准:raw agreement >= 80% 且 kappa/AC1 >= 0.65
(达标后扩展到 300-600 steps 正式标注)。
