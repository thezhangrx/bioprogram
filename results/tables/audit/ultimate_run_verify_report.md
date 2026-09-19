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
- 警告项: 20

## 警告
- all_linear_all_heldout_hct116: 数值发散 R2=-1.1036558405629403e+18 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_ctcf_dnase_h3k4me3_heldout_hct116: 数值发散 R2=-1.2346487394492056e+19 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_ctcf_dnase_heldout_hct116: 数值发散 R2=-4.1171388522977714e+19 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_ctcf_dnase_rrbs_heldout_hct116: 数值发散 R2=-2.6611851382391896e+16 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_dnase_h3k4me3_heldout_hct116: 数值发散 R2=-7.278874105363035e+19 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_dnase_h3k4me3_rrbs_heldout_hct116: 数值发散 R2=-7.754732215139507e+19 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_dnase_heldout_hct116: 数值发散 R2=-2.9403506563768638e+20 (分析层须按 |R²|<10 剔除)
- all_linear_sequence_dnase_rrbs_heldout_hct116: 数值发散 R2=-3.9673470461309564e+20 (分析层须按 |R²|<10 剔除)
- mixed_linear_all_seed_42: 数值发散 R2=-1.224028777311605e+18 (分析层须按 |R²|<10 剔除)
- mixed_linear_sequence_ctcf_dnase_rrbs_seed_42: 数值发散 R2=-4.704408775889988e+16 (分析层须按 |R²|<10 剔除)
- mixed_linear_sequence_dnase_h3k4me3_rrbs_seed_42: 数值发散 R2=-1.598495714259286e+19 (分析层须按 |R²|<10 剔除)
- mixed_linear_sequence_dnase_h3k4me3_seed_42: 数值发散 R2=-1.692202567621396e+19 (分析层须按 |R²|<10 剔除)
- mixed_linear_sequence_dnase_rrbs_seed_42: 数值发散 R2=-2.1003734615547953e+19 (分析层须按 |R²|<10 剔除)
- mixed_linear_sequence_dnase_seed_42: 数值发散 R2=-4.532008090282079e+19 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_all: 数值发散 R2=-4692.814674922972 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_ctcf_dnase_h3k4me3: 数值发散 R2=-2883628375711838.5 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_ctcf_h3k4me3_rrbs: 数值发散 R2=-1938093581107672.8 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_dnase_h3k4me3: 数值发散 R2=-10673899261186.285 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_dnase_h3k4me3_rrbs: 数值发散 R2=-1127111165178793.2 (分析层须按 |R²|<10 剔除)
- single_hl60_linear_sequence_h3k4me3: 数值发散 R2=-9.367863594823454e+16 (分析层须按 |R²|<10 剔除)

## 按 split × model 汇总 (R²)

| split | model | n | n_valid | median R² | mean R² |
|---|---|---|---|---|---|
| all | cnn | 192 | 192 | -0.0212 | -0.0801 |
| all | linear | 64 | 56 | 0.0103 | -0.1054 |
| all | mlp | 64 | 64 | -0.0003 | -0.0756 |
| all | transformer | 64 | 64 | -0.0084 | -0.1112 |
| all | xgboost | 64 | 64 | -0.0072 | -0.0871 |
| mixed | cnn | 192 | 192 | 0.0634 | 0.0634 |
| mixed | linear | 64 | 58 | 0.0696 | 0.0732 |
| mixed | mlp | 64 | 64 | 0.0753 | 0.0725 |
| mixed | transformer | 64 | 64 | 0.0734 | 0.0750 |
| mixed | xgboost | 64 | 64 | 0.0951 | 0.0949 |
| single | cnn | 192 | 192 | 0.0727 | 0.0720 |
| single | linear | 64 | 58 | 0.0824 | 0.0710 |
| single | mlp | 64 | 64 | 0.1022 | 0.0817 |
| single | transformer | 64 | 64 | 0.0988 | 0.0829 |
| single | xgboost | 64 | 64 | 0.1334 | 0.1054 |
