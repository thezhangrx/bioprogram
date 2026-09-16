# 04 Sequence Attribution & Motif Candidates

## Attribution 覆盖

| model | method | n_rows |
| cnn | cnn_ig | 79488 |
| cnn | cnn_ism | 79488 |
| linear | linear_coefficient | 30912 |
| mlp | mlp_ig | 35328 |
| transformer | transformer_attention | 35328 |
| xgboost | xgboost_gain | 35328 |
| xgboost | xgboost_treeshap | 35328 |

## 高归因特征 (per model × method, 跨 context 平均 |importance| 前 N)

| model       | method                | feature        |   mean_abs_importance |   mean_importance |   n_contexts |
|:------------|:----------------------|:---------------|----------------------:|------------------:|-------------:|
| cnn         | cnn_ig                | G_pos_21       |           0.0124218   |       0.0124218   |          576 |
| cnn         | cnn_ig                | G_pos_22       |           0.0122372   |       0.0122372   |          576 |
| cnn         | cnn_ig                | A_pos_17       |           0.0100403   |       0.0100403   |          576 |
| cnn         | cnn_ig                | C_pos_19       |           0.00896521  |       0.00896521  |          576 |
| cnn         | cnn_ig                | A_pos_18       |           0.00740521  |       0.00740521  |          576 |
| cnn         | cnn_ig                | T_pos_20       |           0.00729126  |       0.00729126  |          576 |
| cnn         | cnn_ig                | A_pos_20       |           0.00685841  |       0.00685841  |          576 |
| cnn         | cnn_ig                | A_pos_16       |           0.00603788  |       0.00603788  |          576 |
| cnn         | cnn_ig                | A_pos_19       |           0.00563319  |       0.00563319  |          576 |
| cnn         | cnn_ig                | C_pos_17       |           0.00556665  |       0.00556665  |          576 |
| cnn         | cnn_ism               | C_pos_17       |           0.0226554   |       0.0226554   |          576 |
| cnn         | cnn_ism               | A_pos_17       |           0.0206854   |       0.0206854   |          576 |
| cnn         | cnn_ism               | T_pos_19       |           0.0184662   |       0.0184662   |          576 |
| cnn         | cnn_ism               | C_pos_19       |           0.0178164   |       0.0178164   |          576 |
| cnn         | cnn_ism               | T_pos_18       |           0.0169248   |       0.0169248   |          576 |
| cnn         | cnn_ism               | A_pos_18       |           0.016679    |       0.016679    |          576 |
| cnn         | cnn_ism               | T_pos_20       |           0.0164818   |       0.0164818   |          576 |
| cnn         | cnn_ism               | G_pos_19       |           0.016227    |       0.016227    |          576 |
| cnn         | cnn_ism               | T_pos_17       |           0.0145858   |       0.0145858   |          576 |
| cnn         | cnn_ism               | G_pos_15       |           0.0144525   |       0.0144525   |          576 |
| linear      | linear_coefficient    | pos1_Dnase     |           2.53029e+10 |      -6.24058e+09 |          192 |
| linear      | linear_coefficient    | pos5_Dnase     |           2.36581e+10 |       8.97305e+09 |          192 |
| linear      | linear_coefficient    | pos1_CTCF      |           1.73051e+10 |      -5.16572e+09 |          192 |
| linear      | linear_coefficient    | pos4_Dnase     |           1.45566e+10 |      -9.10274e+09 |          192 |
| linear      | linear_coefficient    | pos2_Dnase     |           1.42959e+10 |       2.27647e+09 |          192 |
| linear      | linear_coefficient    | pos3_Dnase     |           1.38281e+10 |      -8.32174e+09 |          192 |
| linear      | linear_coefficient    | pos23_G        |           1.35233e+10 |       5.83949e+08 |          192 |
| linear      | linear_coefficient    | pos22_G        |           1.22539e+10 |      -2.97947e+09 |          192 |
| linear      | linear_coefficient    | pos1_H3K4me3   |           3.51545e+09 |       1.11098e+08 |          192 |
| linear      | linear_coefficient    | pos19_G        |           1.86688e+09 |       2.15514e+08 |          192 |
| mlp         | mlp_ig                | pos18_C        |           0.0126934   |       0.0126934   |          192 |
| mlp         | mlp_ig                | pos23_G        |           0.0080627   |       0.0080627   |          192 |
| mlp         | mlp_ig                | pos20_G        |           0.00796563  |       0.00796563  |          192 |
| mlp         | mlp_ig                | pos18_A        |           0.00760294  |       0.00760294  |          192 |
| mlp         | mlp_ig                | pos1_G         |           0.00612365  |       0.00612365  |          192 |
| mlp         | mlp_ig                | pos22_G        |           0.00478165  |       0.00478165  |          192 |
| mlp         | mlp_ig                | pos16_C        |           0.00472055  |       0.00472055  |          192 |
| mlp         | mlp_ig                | pos14_T        |           0.00463563  |       0.00463563  |          192 |
| mlp         | mlp_ig                | pos19_G        |           0.00439188  |       0.00439188  |          192 |
| mlp         | mlp_ig                | pos14_G        |           0.00419211  |       0.00419211  |          192 |
| transformer | transformer_attention | A_pos_18       |           0.10446     |       0.10446     |          192 |
| transformer | transformer_attention | CTCF_pos_18    |           0.10446     |       0.10446     |          192 |
| transformer | transformer_attention | T_pos_18       |           0.10446     |       0.10446     |          192 |
| transformer | transformer_attention | RRBS_pos_18    |           0.10446     |       0.10446     |          192 |
| transformer | transformer_attention | H3K4me3_pos_18 |           0.10446     |       0.10446     |          192 |
| transformer | transformer_attention | G_pos_18       |           0.10446     |       0.10446     |          192 |
| transformer | transformer_attention | Dnase_pos_18   |           0.10446     |       0.10446     |          192 |
| transformer | transformer_attention | C_pos_18       |           0.10446     |       0.10446     |          192 |
| transformer | transformer_attention | Dnase_pos_19   |           0.101873    |       0.101873    |          192 |
| transformer | transformer_attention | G_pos_19       |           0.101873    |       0.101873    |          192 |
| xgboost     | xgboost_gain          | pos18_C        |           0.606512    |       0.606512    |          192 |
| xgboost     | xgboost_gain          | pos20_G        |           0.245486    |       0.245486    |          192 |
| xgboost     | xgboost_gain          | pos18_A        |           0.232046    |       0.232046    |          192 |
| xgboost     | xgboost_gain          | pos18_G        |           0.225198    |       0.225198    |          192 |
| xgboost     | xgboost_gain          | pos20_C        |           0.212862    |       0.212862    |          192 |
| xgboost     | xgboost_gain          | pos19_A        |           0.191592    |       0.191592    |          192 |
| xgboost     | xgboost_gain          | pos1_G         |           0.186542    |       0.186542    |          192 |
| xgboost     | xgboost_gain          | pos16_G        |           0.178106    |       0.178106    |          192 |
| xgboost     | xgboost_gain          | pos14_G        |           0.177121    |       0.177121    |          192 |
| xgboost     | xgboost_gain          | pos19_C        |           0.161401    |       0.161401    |          192 |
| xgboost     | xgboost_treeshap      | pos18_C        |           0.0191343   |       0.0191343   |          192 |
| xgboost     | xgboost_treeshap      | pos20_G        |           0.00858527  |       0.00858527  |          192 |
| xgboost     | xgboost_treeshap      | pos1_G         |           0.00736144  |       0.00736144  |          192 |
| xgboost     | xgboost_treeshap      | pos16_G        |           0.00593042  |       0.00593042  |          192 |
| xgboost     | xgboost_treeshap      | pos18_A        |           0.00592254  |       0.00592254  |          192 |
| xgboost     | xgboost_treeshap      | pos14_G        |           0.0055706   |       0.0055706   |          192 |
| xgboost     | xgboost_treeshap      | pos19_A        |           0.00520984  |       0.00520984  |          192 |
| xgboost     | xgboost_treeshap      | pos21_G        |           0.00481958  |       0.00481958  |          192 |
| xgboost     | xgboost_treeshap      | pos20_C        |           0.00478379  |       0.00478379  |          192 |
| xgboost     | xgboost_treeshap      | pos14_T        |           0.00446357  |       0.00446357  |          192 |

> 说明: 本表是 importance/attribution 证据; 不做成统计显著标签。
> ISM 为核苷酸替换效应 (nucleotide substitution effect), 不是普通 feature importance。
> motif discovery / enrichment / known-motif 比较由后续 Phase 提供 (当前 unavailable)。
