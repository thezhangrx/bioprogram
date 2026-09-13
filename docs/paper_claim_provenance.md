# 论文事实来源表（Paper Claim → Source Artifact → Figure/Table）

本文件记录论文中每一处**定量结论**的来源文件、字段、对应图表、统计证据类型与解释级别。
所有数值均由 `paper/make_assets.py` 从只读结果文件重新计算，未手工填写。
结果根目录：`results/batch_20260909_full/`（`analyse_out/` 为分析产物，实验目录为训练产物）。

解释级别（与论文 §2.12/§3 一致）：
- **L1 观察**：直接由数据统计得到（计数、均值、中位数）
- **L2 模型支持**：由模型归因/预测得到
- **L3 多源证据**：多模型 × 统计检验 × 独立信息源一致
- **L4 假设**：可检验的生物学命题（论文只在假设章节使用）

---

## 1. 数据与设计

| Claim | Source result file | Field / column | Figure/Table | Statistical evidence | Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 过滤后 16 749 条 23 nt 序列（HCT116 4 239 / HEK293T 2 333 / HeLa 8 101 / HL60 2 076） | `data/proceeded_data/{cell}_metadata.csv` | `sgRNA`, `Normalized efficacy` | Table 1 | 计数 | L1 |
| 各细胞系平均效率 0.233–0.257 | 同上 | `Normalized efficacy` | Table 1 | 均值/SD/中位数 | L1 |
| PAM 位于第 21–23 位（第 22、23 位在 100% 记录中为 G） | 同上 | `sgRNA[20:23]` | Methods §2.2 | 频率统计 | L1 |
| 设计空间 1 344 次运行 = 7 模型配置 × 16 环境 × 12 设定 | `tables/experiment_table.csv` | `model`,`environment`,`split_type`,`random_seed` | Methods §2.6 | 计数 | L1 |
| Linear Regression 56/192 次运行发散（\|R²\|>10） | `tables/experiment_table.csv` | `R2` | Table 2, Fig. 2B | 计数 | L1 |
| `all` 与 `single` 划分逐位相同（max\|ΔR²\|=0） | `tables/experiment_table.csv` | `R2` by `split_type` | Limitations §5 | 逐位比较 | L1 |

## 2. 预测与泛化

| Claim | Source | Field | Figure/Table | Evidence | Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| single 划分中位 R²：XGBoost 0.115、MLP 0.085、CNN k7 0.080、Transformer 0.069、CNN k5 0.057、CNN k3 0.035 | `tables/experiment_table.csv` | `R2`（每组 64 次运行） | Table 2, Fig. 2A | 中位数/IQR（非参数） | L1 |
| mixed 划分整体更高（XGBoost 中位 0.164） | 同上 | `R2` | Table 2 | 中位数 | L1 |
| 按 held-out 细胞系分组行的差异 | `tables/loco_performance.csv` | `R2` | Fig. 2C（附退化说明） | 分组均值 | L1 |

## 3. 环境因素的增量预测价值

| Claim | Source | Field | Figure/Table | Evidence | Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 因子级平均主效应：CTCF −0.0010、DNase −0.0020、H3K4me3 −0.0059、RRBS −0.0093（排除发散行，模型等权） | `tables/environment_main_effects.csv` | `main_r2_delta` | Table 3, Fig. 3A–B | 跨模型均值 + bootstrap CI | L2/L3 |
| 因子级 95% CI：CTCF [−0.0105, 0.0048]、DNase [−0.0045, 0.0003]、H3K4me3 [−0.0127, −0.0011]、RRBS [−0.0243, −0.0010] | `docs/paper_analysis/factor_level_ci.csv`（per-model mean → bootstrap，B=2000, seed=2024） | `estimate`,`ci_low`,`ci_high` | Table 3, Fig. 7A | 百分位 bootstrap（模型级，n=7） | L3 |
| 方向分布：CTCF 6/7 模型为正；DNase 2/7；H3K4me3 1/7；RRBS 1/7 | `docs/paper_analysis/environment_cross_model.csv` | `n_positive`,`n_negative` | Table 3 | 计数 | L1 |
| 边级逐样本配对 bootstrap：1 906 条边中 166 条（8.7%）CI 不跨 0（CTCF 30/474、DNase 48/470、H3K4me3 38/480、RRBS 50/482） | `tables/bootstrap_results.csv`, `tables/environment_bootstrap.csv` | `estimate`,`ci_low`,`ci_high`,`excludes_zero`,`metric=R2` | Fig. 3C | 逐样本配对 bootstrap（B=2000, seed=2024, α=0.05） | L3 |
| 置换检验：边级 6/2 688、主效应 35/252、交互 9/504 通过 FDR<0.05 | `tables/permutation_results.csv` | `p_value`,`FDR`,`fdr_family` | Table 3 | sign-flip 置换（B=1000）+ BH-FDR（族内） | L3 |
| 区组析因 ANOVA：F=0.60/2.31/1.95/2.18，p=0.663/0.056/0.100/0.069；交互 p≥0.26；partial η²≤0.002；n=1 288，df_den=1 265 | `tables/anova_results.csv` | `F_statistic`,`p_value`,`effect_size`,`df_num`,`df_den` | Fig. 3D | Type-II 边际平方和 F 检验（区组：model/cell_line/split） | L3 |
| 结论：环境增量预测价值在本案例中未获稳健支持 | 上三行 | — | §3.3 | 三种方法交叉 | L3 |

## 4. 序列归因与位置模式

| Claim | Source | Field | Figure/Table | Evidence | Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| PAM 邻近种子区（17–20）为 CNN/MLP/Transformer/XGBoost 的最高归因区域；线性模型最高区域为 PAM（21–23） | `tables/attribution_summary.csv` → `docs/paper_analysis/region_attribution.csv` | `importance` by `position`,`channel`,`method` | Fig. 4B | 模型内归一化归因均值 | L2 |
| 跨模型位置谱 Spearman 0.28–0.61；top-3 重叠 0.30–0.53 | `docs/paper_analysis/cross_model_position_consistency.csv` | `mean_pairwise_spearman`,`mean_top3_overlap` | Table S2 | 秩相关（跨 23 位置） | L2 |
| 峰值位置：HCT116 第 18 位（线性 19）；HeLa 第 18 位（四模型一致）；HL60/HEK293T 第 20 位（线性 23/22） | 同上 | `peak_*` 列 | Table S2, Fig. 4A | argmax | L2 |
| 注意力峰值位于 1–2 或 19–20 位，与梯度/树归因不一致 | 同上 | `peak_transformer` | §3.4, §3.7 | 位置比较 | L1/L2 |
| 第 18 位碱基组成按细胞系不同（HCT116 A0.390/C0.325/G0.285；HEK293T C0.265/A0.250/T0.247/G0.237；HeLa A0.405/C0.307/G0.289；HL60 C0.290/T0.244/A0.238/G0.227） | `data/proceeded_data/*_metadata.csv` | `sgRNA[17]` | Fig. 4C | 频率 | L1 |
| 第 18 位 C vs A 平均效率差：HCT116 +0.090、HeLa +0.092、HL60 +0.028、HEK293T −0.016 | `docs/paper_analysis/position18_efficacy_by_base.csv` | `mean_efficacy`,`n` | Fig. 4C, Fig. 6B | 分组均值（n=472–1 652/组） | L1/L3 |
| 第 18 位归因中 C 占比：XGBoost 0.64–0.77、MLP 0.28–0.63、CNN 0.23–0.37、Transformer 0.25 恒定 | `docs/paper_analysis/position18_attribution.csv` | `C18_share_within_pos18` | Fig. 4D | 模型内占比 | L2 |

## 5. 多尺度 CNN（感受野消融）

| Claim | Source | Field | Figure/Table | Evidence | Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| k5−k3 = +0.0423 [0.0375, 0.0470]；k7−k3 = +0.0557 [0.0514, 0.0600]；k7−k5 = +0.0134 [0.0107, 0.0162] | `docs/paper_analysis/cnn_kernel_paired.csv`（192 组配对） | `mean_dR2`,`ci_low`,`ci_high`,`pct_positive` | Table 4, Fig. 5A | 配对差 + 配对 bootstrap CI | L3 |
| 配对为正比例 88.5% / 95.8% / 77.1% | 同上 | `pct_positive` | Table 4 | 计数 | L1 |
| 核间位置谱相关：k3–k5 ρ=0.82；k7 与二者 0.21–0.23 | `docs/paper_analysis/kernel_position_profile.csv` | 相关矩阵 | Fig. 5B, §3.5 | Spearman | L2 |
| 区域归因随核增大向 PAM 邻近集中（PAM-prox 0.0484→0.0557；PAM 0.0341→0.0473；远端 0.0443→0.0388） | 同上 | 区域均值 | Fig. 5C | 归一化归因均值 | L2 |
| 三配置候选模式长度中位数均为 4 nt（范围 4–11） | `tables/motif_candidates.csv` | `length` by `model_variant` | Fig. 5D | 中位数 | L1 |

## 6. 候选序列模式

| Claim | Source | Field | Figure/Table | Evidence | Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 596 个候选模式（50 Strong / 340 Moderate / 206 Model-specific）；545 060 个 seqlet | `tables/motif_candidates.csv`, `tables/motif_instances.csv` | `evidence_strength`,`support_count` | §3.6, Table 5 | 支持度与复现性规则 | L2/L3 |
| 长度中位 4 nt（532/596 为 4 nt），支持度中位 194 | `tables/motif_candidates.csv` | `length`,`support_count` | Fig. 5D, Table 5 | 分布统计 | L1 |
| 位置高度集中：382/596 起始于第 20 位 | 同上 | `position_start` | §3.6 | 计数 | L1 |
| 64/596 通过富集 BH-FDR<0.05（前景=效率上三分位，背景=全部可用序列） | `tables/motif_enrichment.csv` | `p_value`,`FDR`,`odds_ratio` | Table 5, §3.6 | Fisher 精确检验 + BH-FDR（`motif_enrichment` 族） | L3 |
| 最高支持度模式 CTGG（1 273 seqlet，方向为负，Δ效率 −0.046，FDR 未达阈值） | `tables/motif_candidates.csv` | `human_pattern`,`support_count`,`effect_direction`,`mean_effect`,`FDR` | Table 5 | 支持度 + 实测效率对比 | L1/L2 |
| 方向来自 carrier vs background 实测效率对比（非 attribution 符号） | 同上 | `direction_source` | Methods §2.9 | 方法学说明 | L2 |

## 7. 细胞系异质性与证据整合

| Claim | Source | Field | Figure/Table | Evidence | Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| CTCF ΔR²：HCT116 +0.0048、HEK293T +0.0077、HeLa +0.0009、HL60 −0.0038 | `docs/paper_analysis/environment_by_cellline.csv` | `mean_dR2` | Fig. 6A | 分组均值（stable 行） | L1 |
| H3K4me3 在 HEK293T −0.0168、HL60 +0.0065（方向相反） | 同上 | `mean_dR2` | Fig. 6A | 分组均值 | L1 |
| context 标签计数：CTCF 12 conflicting / 2 consistent / 7 uncertain；DNase 8 dependent / 13 uncertain；RRBS 6 conflicting / 6 dependent / 9 uncertain | `tables/cellline_effects.csv` | `context_label` | Fig. 6C | 方向+异质性+CI 规则 | L2/L3 |
| 环境证据分级：RRBS Tier 1、DNase Tier 2、CTCF/H3K4me3 Inconclusive | `tables/evidence_matrix.csv` | `evidence_tier`,`coverage`,`permutation_fdr`,`ci_excludes_zero` | Table 3, Fig. 7A | 覆盖度+一致率+CI 规则 | L3 |
| ΔR²–importance 相关：XGBoost 0.56、线性 0.30、CNN 0.25、MLP −0.16、Transformer 不可用 | `tables/importance_vs_delta_r2.csv` | `delta_r2`,`normalized_importance` | Fig. 7B | Spearman | L2 |
| 反例集合（发散运行、注意力位置不一致、91.3% 边 CI 跨 0、ANOVA 不显著、MLP 负相关） | 多文件（见上） | — | §3.7 | 汇总 | L1–L3 |

---

## 8. 外部引用核验记录

| BibTeX key | 核验来源 | 关键标识 |
| :--- | :--- | :--- |
| `Jinek2012Science` | PubMed esummary | PMID 22745249; doi:10.1126/science.1225829 |
| `Cong2013Science` | PubMed esummary | PMID 23287718; doi:10.1126/science.1231143 |
| `Doench2014NatBiotechnol` | PubMed esummary | PMID 25184501; doi:10.1038/nbt.3026 |
| `Doench2016NatBiotechnol` | PubMed esummary | PMID 26780180; doi:10.1038/nbt.3437 |
| `MorenoMateos2015NatMethods` | PubMed esummary | PMID 26322839; doi:10.1038/nmeth.3543 |
| `Chuai2018GenomeBiol` | PubMed esummary | PMID 29945655; doi:10.1186/s13059-018-1459-4 |
| `Alipanahi2015NatBiotechnol` | PubMed esummary | PMID 26213851; doi:10.1038/nbt.3300 |
| `Kelley2016GenomeRes` | PubMed esummary | PMID 27197224; doi:10.1101/gr.200535.115 |
| `Chen2016KDD` | Crossref | doi:10.1145/2939672.2939785 (pp. 785–794) |
| `Lundberg2017NeurIPS` | OpenAlex | arXiv:1705.07874 (NeurIPS 30, 2017) |
| `Sundararajan2017ICML` | arXiv abs page | arXiv:1703.01365 (PMLR 70:3319–3328) |
| `Vaswani2017NeurIPS` | OpenAlex（作者/标题核验） | arXiv:1706.03762 (NeurIPS 30, 2017) |
