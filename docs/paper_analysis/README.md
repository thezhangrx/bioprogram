# 论文结果挖掘中间产物（paper_analysis/）

本目录保存论文写作前的**结果挖掘**输出。所有文件由 `paper/make_assets.py` 从只读结果文件
（`results/batch_20260909_full/analyse_out/`、`data/proceeded_data/`）重新计算得到，
不在论文中手工填写任何数值。

| 文件 | 内容 | 论文位置 |
| :--- | :--- | :--- |
| `nucleotide_frequency_by_position.csv` | 23 个位置 × 4 碱基频率（用于 PAM 定义与位置 18 分析） | Methods §2.2 |
| `position18_efficacy_by_base.csv` | 第 18 位碱基 × 细胞系的实测效率均值/中位/SD/n | Fig. 4C, Fig. 6B |
| `position18_attribution.csv` | 第 18 位各模型归因与 C 占比 | Fig. 4D |
| `cross_model_position_consistency.csv` | 五模型位置谱峰值、平均 Spearman、top-3 重叠 | Table S2, §3.4 |
| `position_profile_by_model.csv` | 五模型 23 位置归一化归因谱 | Fig. 4A |
| `region_attribution.csv` | PAM / PAM 邻近种子区 / 种子核心 / PAM 远端 的区域平均归因 | Fig. 4B |
| `cnn_ism_position_profile.csv` | CNN ISM 位置谱 | §3.4 |
| `kernel_position_profile.csv` | CNN k=3/5/7 的位置归因谱 | Fig. 5B–C |
| `cnn_kernel_paired.csv` | 192 组配对实验的核间 ΔR² 与 bootstrap CI | Table 4, Fig. 5A |
| `environment_cross_model.csv` | 环境因子跨模型主效应（排除发散行） | Table 3 |
| `environment_by_cellline.csv` | 环境因子 × 细胞系平均 ΔR² | Fig. 6A |
| `bootstrap_edge_by_factor.csv` | 逐样本配对 bootstrap 中 CI 不跨 0 的边数（按因子） | Fig. 3C |
| `factor_level_ci.csv` | 因子级一致口径 bootstrap CI（模型等权） | Table 3, Fig. 7A |
| `asset_summary.json` | 本次资产生成的规模摘要 | — |

**注意**：`analyse/stats/tasks.py::bootstrap_main_effects` 原先对全部 (模型×划分×细胞系) 行
直接 bootstrap，在网格不均衡时会出现置信区间不包含点估计的情形；本轮已修正为“先按模型求均值、
再对模型 bootstrap”，`factor_level_ci.csv` 即按修正后口径计算。
