# M8 统计模型说明

- `m8_cluster_robust_logistic.csv`:run-level marginal logistic model(GEE 风格,problem 聚类 sandwich SE;非随机效应拟合,作为 cluster bootstrap 的一致性检查);
- 样本:4800 次 control/target runs,303 个 problem clusters;
- `m8_power_analysis.csv`:以冻结 600-step 结果为 DGP 的模拟检验力(400 次模拟/格,seed 20260723);
- 后续 M2/M6 判分完成后,在合并数据上加 generator/dataset 交互项。
