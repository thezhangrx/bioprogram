# 04 Sequence & Motifs

<!-- MOTIF_DISCOVERY_SECTION -->
## Sequence Motif Discovery

> Motif 表示 *sequence pattern associated with model-predicted / measured editing efficiency* 的候选序列模式, **不是**因果结论, 也不称 "significant motif" 除非 enrichment 通过 FDR。

### Methodology (可直接追溯)

| 项 | 值 |
| :--- | :--- |
| Motif source | cnn (Transformer IG: unavailable (只有 attention, 不作 extractor)) |
| Attribution method | primary: cnn_ism, cnn_ig; supporting: transformer_attention |
| Contexts | sequence, all (environment-masked 模型不作为序列 motif 来源) |
| Seqlet extraction | 位置级 attribution 分位 q=0.9 + 局部连续 (q=0.75, >= 2 连续位置), 每样本 <= 2 窗口; **不是 top-N 单点** |
| Motif length range | 4-12 nt (由 attribution 窗口与聚类确定; kernel size 不等于 motif 长度) |
| Clustering | 贪心相似度聚类 (与 cluster consensus 一致率 >= 0.9) |
| Minimum support | seqlet >= 30, sample >= 20 |
| Consensus representation | IUPAC 退化码 (次优碱基频率 >= 0.25) |
| Human-readable representation | (A/G)TC 形式 (human_pattern 列) |
| Regex representation | [AG]TC 形式 (regex 列, 与 human_pattern 分开保存) |
| Enrichment | performed (foreground = efficacy 上 67%; background = all_eligible_sequences); Fisher exact + BH-FDR family=motif_enrichment, threshold FDR < 0.05 |
| Direction | attribution 无符号 -> 由 carrier vs background measured-efficacy 对比给出 (`direction_source` 列记录) |
| Stability criteria | 跨 CNN kernel variant (相似度 >= 0.8) 与跨 cell line; seed-level 见下方说明 |
| Region definitions | schema 未定义 seed/PAM -> 全部 Other (不假设) |

### Motif candidates

| motif_id | consensus | IUPAC | human pattern | regex | len | support | samples | cell lines | mean effect | direction | enrichment (FDR) | evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| motif_cnn33_hela_sequence_cnn_ig_001 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1273 | 1273 | 1 | -0.0461 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn33_hela_all_cnn_ig_002 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1273 | 1273 | 1 | -0.0461 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn53_hela_sequence_cnn_ig_003 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1273 | 1273 | 1 | -0.0461 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_all_cnn_ig_004 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1273 | 1273 | 1 | -0.0461 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_sequence_cnn_ig_005 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1273 | 1273 | 1 | -0.0461 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_all_cnn_ig_006 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1273 | 1273 | 1 | -0.0461 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_sequence_cnn_ig_007 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1273 | 1273 | 1 | -0.0461 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn33_hela_all_cnn_ism_008 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1178 | 1178 | 1 | -0.0376 | - | 0.87 (FDR=1) | Model-specific motif |
| motif_cnn33_hela_all_cnn_ig_009 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1167 | 1167 | 1 | -0.0386 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn53_hela_sequence_cnn_ig_010 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1167 | 1167 | 1 | -0.0386 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn53_hela_all_cnn_ig_011 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 1145 | 1145 | 1 | -0.0456 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn33_hela_sequence_cnn_ig_012 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 1083 | 1083 | 1 | -0.0304 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn33_hela_sequence_cnn_ig_013 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 1083 | 1083 | 1 | -0.0304 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn53_hela_all_cnn_ig_014 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 1083 | 1083 | 1 | -0.0304 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn53_hela_sequence_cnn_ig_015 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 1083 | 1083 | 1 | -0.0304 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn53_hela_all_cnn_ig_016 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 1083 | 1083 | 1 | -0.0304 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_all_cnn_ig_017 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 1083 | 1083 | 1 | -0.0304 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_sequence_cnn_ig_018 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 1083 | 1083 | 1 | -0.0304 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_all_cnn_ig_019 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 1083 | 1083 | 1 | -0.0304 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_sequence_cnn_ig_020 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 1083 | 1083 | 1 | -0.0304 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn33_hela_all_cnn_ig_021 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 1053 | 1053 | 1 | -0.0264 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn53_hela_all_cnn_ig_022 | CTGG | CTGG | `CTGG` | `CTGG` | 4 | 974 | 974 | 1 | -0.0389 | - | 0.87 (FDR=1) | Moderate motif evidence |
| motif_cnn33_hela_all_cnn_ism_023 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 964 | 964 | 1 | -0.0163 | - | 0.934 (FDR=1) | Model-specific motif |
| motif_cnn53_hela_sequence_cnn_ig_024 | CAGG | CAGG | `CAGG` | `CAGG` | 4 | 964 | 964 | 1 | -0.0163 | - | 0.934 (FDR=1) | Moderate motif evidence |
| motif_cnn33_hela_sequence_cnn_ig_025 | GAGG | GAGG | `GAGG` | `GAGG` | 4 | 899 | 899 | 1 | +0.0121 | + | 1.08 (FDR=0.0309) | Strong motif evidence |
| motif_cnn53_hela_all_cnn_ig_026 | GAGG | GAGG | `GAGG` | `GAGG` | 4 | 899 | 899 | 1 | +0.0121 | + | 1.08 (FDR=0.0309) | Strong motif evidence |
| motif_cnn53_hela_sequence_cnn_ig_027 | GAGG | GAGG | `GAGG` | `GAGG` | 4 | 899 | 899 | 1 | +0.0121 | + | 1.08 (FDR=0.0309) | Strong motif evidence |
| motif_cnn73_hela_all_cnn_ig_028 | GAGG | GAGG | `GAGG` | `GAGG` | 4 | 899 | 899 | 1 | +0.0121 | + | 1.08 (FDR=0.0309) | Strong motif evidence |
| motif_cnn73_hela_sequence_cnn_ig_029 | GAGG | GAGG | `GAGG` | `GAGG` | 4 | 899 | 899 | 1 | +0.0121 | + | 1.08 (FDR=0.0309) | Strong motif evidence |
| motif_cnn73_hela_all_cnn_ig_030 | GAGG | GAGG | `GAGG` | `GAGG` | 4 | 899 | 899 | 1 | +0.0121 | + | 1.08 (FDR=0.0309) | Strong motif evidence |
| motif_cnn73_hela_sequence_cnn_ig_031 | GAGG | GAGG | `GAGG` | `GAGG` | 4 | 899 | 899 | 1 | +0.0121 | + | 1.08 (FDR=0.0309) | Strong motif evidence |
| motif_cnn33_hela_all_cnn_ig_032 | AAGG | AAGG | `AAGG` | `AAGG` | 4 | 890 | 890 | 1 | -0.0095 | - | 0.983 (FDR=1) | Moderate motif evidence |
| motif_cnn33_hela_sequence_cnn_ig_033 | AAGG | AAGG | `AAGG` | `AAGG` | 4 | 890 | 890 | 1 | -0.0095 | - | 0.983 (FDR=1) | Moderate motif evidence |
| motif_cnn33_hela_all_cnn_ig_034 | AAGG | AAGG | `AAGG` | `AAGG` | 4 | 890 | 890 | 1 | -0.0095 | - | 0.983 (FDR=1) | Moderate motif evidence |
| motif_cnn53_hela_all_cnn_ig_035 | AAGG | AAGG | `AAGG` | `AAGG` | 4 | 890 | 890 | 1 | -0.0095 | - | 0.983 (FDR=1) | Moderate motif evidence |
| motif_cnn53_hela_sequence_cnn_ig_036 | AAGG | AAGG | `AAGG` | `AAGG` | 4 | 890 | 890 | 1 | -0.0095 | - | 0.983 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_all_cnn_ig_037 | AAGG | AAGG | `AAGG` | `AAGG` | 4 | 890 | 890 | 1 | -0.0095 | - | 0.983 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_sequence_cnn_ig_038 | AAGG | AAGG | `AAGG` | `AAGG` | 4 | 890 | 890 | 1 | -0.0095 | - | 0.983 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_all_cnn_ig_039 | AAGG | AAGG | `AAGG` | `AAGG` | 4 | 890 | 890 | 1 | -0.0095 | - | 0.983 (FDR=1) | Moderate motif evidence |
| motif_cnn73_hela_sequence_cnn_ig_040 | AAGG | AAGG | `AAGG` | `AAGG` | 4 | 890 | 890 | 1 | -0.0095 | - | 0.983 (FDR=1) | Moderate motif evidence |

- seqlets: **559773**; motifs passing support: **656**; contexts: 96; cell lines with sequences: 4
- 位置分布 / logo / consistency 图见 `figures/04_motif/`;
- seed-level motif support: **unavailable** (attribution_summary 不含 random_seed)。

### Limitations

- attribution 为无符号 magnitude -> 不能按 attribution 正负分组; 方向来自 measured efficacy 对比 (关联性, 非因果);
- 当前批次无 Transformer IG -> cross-model (CNN vs Transformer) 比较 unavailable; attention 不作 motif extractor;
- motif 长度由窗口/聚类决定, 与 CNN kernel size 无关;
- enrichment 若未在 AnalysisPlan 中启用, 则没有任何 p-value / FDR, 不得称 statistically enriched。
