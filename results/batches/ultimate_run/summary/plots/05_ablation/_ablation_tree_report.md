# Ablation Tree Report

结构: 根 = sequence 基线 → level1 = ALL(4 环境) → level2 = 3 环境 → level3 = 2 环境。
每层相对父组合消融一个环境; 每个组合只出现一次; 异常节点 (缺失/发散/指标不一致) 视为 dup,
不绘制且其下整棵子树一并隐藏。

- 生成图: 61 / 分组 63; 累计剪除/缺失节点 2
- 异常阈值: |metric| > 10 (consensus.unstable_effect_threshold) 或 dR2 与 dRMSE 同向

| split | cell_line | model | status | nodes | pruned | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| all | hct116 | cnn(3\|3) | drawn | 12 | 0 | tree_all_hct116_cnn_3_3.png |
| all | hct116 | cnn(5\|3) | drawn | 12 | 0 | tree_all_hct116_cnn_5_3.png |
| all | hct116 | cnn(7\|3) | drawn | 12 | 0 | tree_all_hct116_cnn_7_3.png |
| all | hct116 | linear | skipped | 0 | 1 | all: metrics missing for this combination |
| all | hct116 | mlp | drawn | 12 | 0 | tree_all_hct116_mlp.png |
| all | hct116 | transformer | drawn | 12 | 0 | tree_all_hct116_transformer.png |
| all | hct116 | xgboost | drawn | 12 | 0 | tree_all_hct116_xgboost.png |
| all | hek293t | cnn(3\|3) | drawn | 12 | 0 | tree_all_hek293t_cnn_3_3.png |
| all | hek293t | cnn(5\|3) | drawn | 12 | 0 | tree_all_hek293t_cnn_5_3.png |
| all | hek293t | cnn(7\|3) | drawn | 12 | 0 | tree_all_hek293t_cnn_7_3.png |
| all | hek293t | linear | drawn | 12 | 0 | tree_all_hek293t_linear.png |
| all | hek293t | mlp | drawn | 12 | 0 | tree_all_hek293t_mlp.png |
| all | hek293t | transformer | drawn | 12 | 0 | tree_all_hek293t_transformer.png |
| all | hek293t | xgboost | drawn | 12 | 0 | tree_all_hek293t_xgboost.png |
| all | hela | cnn(3\|3) | drawn | 12 | 0 | tree_all_hela_cnn_3_3.png |
| all | hela | cnn(5\|3) | drawn | 12 | 0 | tree_all_hela_cnn_5_3.png |
| all | hela | cnn(7\|3) | drawn | 12 | 0 | tree_all_hela_cnn_7_3.png |
| all | hela | linear | drawn | 12 | 0 | tree_all_hela_linear.png |
| all | hela | mlp | drawn | 12 | 0 | tree_all_hela_mlp.png |
| all | hela | transformer | drawn | 12 | 0 | tree_all_hela_transformer.png |
| all | hela | xgboost | drawn | 12 | 0 | tree_all_hela_xgboost.png |
| all | hl60 | cnn(3\|3) | drawn | 12 | 0 | tree_all_hl60_cnn_3_3.png |
| all | hl60 | cnn(5\|3) | drawn | 12 | 0 | tree_all_hl60_cnn_5_3.png |
| all | hl60 | cnn(7\|3) | drawn | 12 | 0 | tree_all_hl60_cnn_7_3.png |
| all | hl60 | linear | drawn | 12 | 0 | tree_all_hl60_linear.png |
| all | hl60 | mlp | drawn | 12 | 0 | tree_all_hl60_mlp.png |
| all | hl60 | transformer | drawn | 12 | 0 | tree_all_hl60_transformer.png |
| all | hl60 | xgboost | drawn | 12 | 0 | tree_all_hl60_xgboost.png |
| mixed | none | cnn(3\|3) | drawn | 12 | 0 | tree_mixed_none_cnn_3_3.png |
| mixed | none | cnn(5\|3) | drawn | 12 | 0 | tree_mixed_none_cnn_5_3.png |
| mixed | none | cnn(7\|3) | drawn | 12 | 0 | tree_mixed_none_cnn_7_3.png |
| mixed | none | linear | drawn | 12 | 0 | tree_mixed_none_linear.png |
| mixed | none | mlp | drawn | 12 | 0 | tree_mixed_none_mlp.png |
| mixed | none | transformer | drawn | 12 | 0 | tree_mixed_none_transformer.png |
| mixed | none | xgboost | drawn | 12 | 0 | tree_mixed_none_xgboost.png |
| single | hct116 | cnn(3\|3) | drawn | 12 | 0 | tree_single_hct116_cnn_3_3.png |
| single | hct116 | cnn(5\|3) | drawn | 12 | 0 | tree_single_hct116_cnn_5_3.png |
| single | hct116 | cnn(7\|3) | drawn | 12 | 0 | tree_single_hct116_cnn_7_3.png |
| single | hct116 | linear | drawn | 12 | 0 | tree_single_hct116_linear.png |
| single | hct116 | mlp | drawn | 12 | 0 | tree_single_hct116_mlp.png |
| single | hct116 | transformer | drawn | 12 | 0 | tree_single_hct116_transformer.png |
| single | hct116 | xgboost | drawn | 12 | 0 | tree_single_hct116_xgboost.png |
| single | hek293t | cnn(3\|3) | drawn | 12 | 0 | tree_single_hek293t_cnn_3_3.png |
| single | hek293t | cnn(5\|3) | drawn | 12 | 0 | tree_single_hek293t_cnn_5_3.png |
| single | hek293t | cnn(7\|3) | drawn | 12 | 0 | tree_single_hek293t_cnn_7_3.png |
| single | hek293t | linear | drawn | 12 | 0 | tree_single_hek293t_linear.png |
| single | hek293t | mlp | drawn | 12 | 0 | tree_single_hek293t_mlp.png |
| single | hek293t | transformer | drawn | 12 | 0 | tree_single_hek293t_transformer.png |
| single | hek293t | xgboost | drawn | 12 | 0 | tree_single_hek293t_xgboost.png |
| single | hela | cnn(3\|3) | drawn | 12 | 0 | tree_single_hela_cnn_3_3.png |
| single | hela | cnn(5\|3) | drawn | 12 | 0 | tree_single_hela_cnn_5_3.png |
| single | hela | cnn(7\|3) | drawn | 12 | 0 | tree_single_hela_cnn_7_3.png |
| single | hela | linear | drawn | 12 | 0 | tree_single_hela_linear.png |
| single | hela | mlp | drawn | 12 | 0 | tree_single_hela_mlp.png |
| single | hela | transformer | drawn | 12 | 0 | tree_single_hela_transformer.png |
| single | hela | xgboost | drawn | 12 | 0 | tree_single_hela_xgboost.png |
| single | hl60 | cnn(3\|3) | drawn | 12 | 0 | tree_single_hl60_cnn_3_3.png |
| single | hl60 | cnn(5\|3) | drawn | 12 | 0 | tree_single_hl60_cnn_5_3.png |
| single | hl60 | cnn(7\|3) | drawn | 12 | 0 | tree_single_hl60_cnn_7_3.png |
| single | hl60 | linear | skipped | 0 | 1 | all: metrics missing for this combination |
| single | hl60 | mlp | drawn | 12 | 0 | tree_single_hl60_mlp.png |
| single | hl60 | transformer | drawn | 12 | 0 | tree_single_hl60_transformer.png |
| single | hl60 | xgboost | drawn | 12 | 0 | tree_single_hl60_xgboost.png |
