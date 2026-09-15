# HPC 重跑验收报告 — ultimate_run

- 计划实验: 1344
- 实际 run 目录: 1344
- 可解析 run: 1344
- 分 split: {'all': 448, 'mixed': 448, 'single': 448}
- split_digest 复核: 已复核 1344 个 run, 不一致 0
- data_fingerprint: {'ecac199fa27ea80d': 1344}
- code_fingerprint: {'2661d5bdd1cd9c2a': 1344}
- device_resolved: {'cuda': 960, '?': 384}
- env_stack_id: {'625cc71596d7d94d': 1344}
- 失败项: 0
- 警告项: 33

## 警告
- all_linear_all_heldout_hct116: 数值发散 R2=-10050581424.443584 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_ctcf_dnase_h3k4me3_heldout_hct116: 数值发散 R2=-407393638601.69293 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_ctcf_dnase_heldout_hct116: 数值发散 R2=-213604887461.27664 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_ctcf_dnase_rrbs_heldout_hct116: 数值发散 R2=-8110025295.874095 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_dnase_h3k4me3_heldout_hct116: 数值发散 R2=-4064148727.775788 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_dnase_h3k4me3_rrbs_heldout_hct116: 数值发散 R2=-2.0144099443448335e+18 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_dnase_heldout_hct116: 数值发散 R2=-18967269972751.723 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_dnase_rrbs_heldout_hct116: 数值发散 R2=-32084588545.913456 (分析层须按 |R²|<10 剔除)
- mixed_linear_all_seed_42: 数值发散 R2=-1.1871130474681316e+18 (分析层须按 |R²|<10 剔除)
- mixed_linear_sequence_ctcf_dnase_rrbs_seed_42: 数值发散 R2=-4.562527569314228e+16 (分析层须按 |R²|<10 剔除)
- mixed_linear_sequence_dnase_h3k4me3_rrbs_seed_42: 数值发散 R2=-1.550286360941777e+19 (分析层须按 |R²|<10 剔除)
- mixed_linear_sequence_dnase_h3k4me3_seed_42: 数值发散 R2=-1.6411670904929225e+19 (分析层须按 |R²|<10 剔除)
- mixed_linear_sequence_dnase_rrbs_seed_42: 数值发散 R2=-2.0370278764585755e+19 (分析层须按 |R²|<10 剔除)
- mixed_linear_sequence_dnase_seed_42: 数值发散 R2=-4.395326348049907e+19 (分析层须按 |R²|<10 剔除)
- single_hela_linear_all: 数值发散 R2=-2469925585.746402 (分析层须按 |R²|<10 剔除)
- single_hela_linear_sequence_ctcf: 数值发散 R2=-5054222598214290.0 (分析层须按 |R²|<10 剔除)
- single_hela_linear_sequence_ctcf_dnase: 数值发散 R2=-274.44452174454017 (分析层须按 |R²|<10 剔除)
- single_hela_linear_sequence_ctcf_dnase_h3k4me3: 数值发散 R2=-4858072558.908395 (分析层须按 |R²|<10 剔除)
- single_hela_linear_sequence_ctcf_dnase_rrbs: 数值发散 R2=-1102925106.2243152 (分析层须按 |R²|<10 剔除)
- single_hela_linear_sequence_dnase_h3k4me3: 数值发散 R2=-163905135308.538 (分析层须按 |R²|<10 剔除)
- single_hela_linear_sequence_dnase_h3k4me3_rrbs: 数值发散 R2=-719286286893.9249 (分析层须按 |R²|<10 剔除)
- single_hela_linear_sequence_h3k4me3: 数值发散 R2=-10433190941149.734 (分析层须按 |R²|<10 剔除)
- single_hela_linear_sequence_h3k4me3_rrbs: 数值发散 R2=-1071187483489.8691 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_all: 数值发散 R2=-9.10966320645435e+20 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_ctcf_dnase: 数值发散 R2=-1.0456394599749471e+21 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_ctcf_dnase_h3k4me3: 数值发散 R2=-2.398561786084544e+21 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_ctcf_dnase_rrbs: 数值发散 R2=-2.1438717000397137e+21 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_ctcf_h3k4me3_rrbs: 数值发散 R2=-1.1518491223008099e+18 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_dnase: 数值发散 R2=-3.0357698404497916e+20 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_dnase_h3k4me3: 数值发散 R2=-3.187418455090394e+20 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_dnase_h3k4me3_rrbs: 数值发散 R2=-3.932077536512039e+20 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_dnase_rrbs: 数值发散 R2=-2.798143201515626e+20 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_h3k4me3: 数值发散 R2=-2.948362254353464e+17 (分析层须按 |R²|<10 剔除)

## 按 split × model 汇总 (R²)

| split | model | n | n_valid | median R² | mean R² |
|---|---|---|---|---|---|
| all | cnn | 192 | 192 | 0.0557 | 0.0654 |
| all | linear | 64 | 56 | 0.0648 | 0.0517 |
| all | mlp | 64 | 64 | 0.0531 | 0.0505 |
| all | transformer | 64 | 64 | 0.0783 | 0.0712 |
| all | xgboost | 64 | 64 | 0.0852 | 0.0720 |
| mixed | cnn | 192 | 192 | 0.0714 | 0.0709 |
| mixed | linear | 64 | 58 | 0.0559 | 0.0553 |
| mixed | mlp | 64 | 64 | 0.0695 | 0.0691 |
| mixed | transformer | 64 | 64 | 0.0836 | 0.0837 |
| mixed | xgboost | 64 | 64 | 0.0957 | 0.0914 |
| single | cnn | 192 | 192 | 0.1042 | 0.1077 |
| single | linear | 64 | 45 | 0.1102 | 0.0644 |
| single | mlp | 64 | 64 | 0.1270 | 0.1067 |
| single | transformer | 64 | 64 | 0.1266 | 0.1180 |
| single | xgboost | 64 | 64 | 0.1287 | 0.1137 |
