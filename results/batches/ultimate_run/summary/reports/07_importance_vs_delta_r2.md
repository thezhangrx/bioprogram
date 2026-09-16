# 07 Importance / Attribution – ΔR² Relationship

## 1. Purpose
回答“某环境因子的预测增量贡献 (ΔR²) 与模型对该因子的依赖/归因强度是否一致”，即建立 Effect–Attribution 二维坐标系；不产出生物学因果结论。

## 2. X 轴定义
`ΔR² = R²(expanded) − R²(baseline)`，遵循 Paired Baseline 原则：仅在同一 `(split_type, cell_line, model, random_seed)` cohort 内与 sequence/背景组合配对，由 `analysis.environment.incremental_effect` 计算；本图对同一 factor 跨背景取均值。

## 3. Y 轴定义
模型专属主 importance，经 within-(model, split, cell_line) 归一化：`normalized = importance_factor / Σ importance_factors`，含义为“该因子在本模型该上下文全部有效环境 attribution 中的相对占比”。原始量纲 (系数/SHAP/IG) 不可跨模型直接比较。

## 4. Model-specific metric selection
- **cnn**: Y = `CNN_IG`；robustness = `ISM_SNR`；statistical = `-`；Y=CNN_IG; 无 IG_SNR 输出 (不得假装存在); ISM_SNR 作为稳健性筛选但 ISM 语义为突变效应
- **linear**: Y = `Linear_Coefficient`；robustness = `-`；statistical = `FDR`；Y=|系数|; 方向由 signed 系数保留; FDR 仅用于统计筛选
- **mlp**: Y = `MLP_IG`；robustness = `IG_SNR`；statistical = `-`；Y=mean(|IG|); IG_SNR 仅稳健性筛选
- **transformer**: Y = `unavailable`；robustness = `Attention_SNR`；statistical = `-`；未输出 Transformer_IG (函数存在但从未调用/未入白名单); Attention 无方向, 不作为主 Y
- **xgboost**: Y = `TreeSHAP`；robustness = `SHAP_SNR`；statistical = `-`；Y=mean(|SHAP|); Gain/Weight/Cover 为树内部重要性(无方向), 仅 tooltip

## 5. Significance / robustness filtering
- filter_mode = `strict`（strict=仅 Strong；moderate=Strong+Moderate；all=所有可用主指标）；
- 本批通过点数: strict=6, moderate=17, all=144；CSV 中 `filter_pass` 对应 `strict` 档，`filter_reason` 逐行给出落选原因。
- linear: FDR 阈值分档 (0.001/0.01/0.05)；FDR 缺失 → unavailable，不因存在系数而宣称显著；
- xgb/mlp/cnn: SNR (2.5/1.8/1.2) **且** |importance| ≥ min_effect_size；SNR 不是 p 值；
- 注意 factor 级 importance 为 23 位点求和, 与 config 中 per-feature min_effect_size 属不同标度; 此处按规范字面复用该阈值, 结果偏保守 (已在 §8 记录);
- CNN 无 IG_SNR 输出，其稳健性字段使用 ISM_SNR（ISM 语义为突变效应，已在标注中说明）；
- Transformer 被排除：未输出 Transformer_IG，Attention/Entropy 无方向。

## 6. Normalization（见 §3）

## 7. Plot interpretation
- Q1 高 attribution + ΔR²>0：该因子既有增量贡献又被稳定依赖；
- Q2 高 attribution + ΔR²<0：模型依赖该因子，但增量实验无额外收益；
- Q4 低 attribution + ΔR²>0：有增量收益但模型依赖不强（可能被其它因子替代）；
- Q3 低 attribution + ΔR²<0：弱/可能不稳。以上仅为图面解释，不是生物学结论。

## 8. Limitations
- 未接通 bootstrap runner：`delta_r2_ci_low/high` 保持 NaN，图中**不画误差条**；
- factor 级统计证据取位点级最小 FDR，未对因子内多重比较再校正；
- factor 级 importance 求和后与 per-feature `min_effect_size` 比较属标度混用，偏保守；
- `all` 档含 not-supported / below-min-effect 点，仅供敏感性分析，不得当作显著结果引用；
- ΔR² 依赖既有 1344 网格的实验设计（`all` 划分在网格中退化为 `single`，见项目文档 §1.5）；
- 本图不包含 sequence position×channel 级 attribution（另有 sequence 图）。

## 9. 本次数据 (batch=ultimate_run)
- 候选点: 180（`strict` 档通过 6）；模型: cnn, linear, mlp, transformer, xgboost
- 三档通过数: strict=6 / moderate=17 / all=144
- 数值卫生: 配对前剔除单实验 |R²| > unstable_effect_threshold 的发散实验 n/a 个 (linear 为主); 残余 |ΔR²| 超阈值的点也在 `filter_reason` 中标记为 parameter anomaly 并排除出图。
- 生成图: 7 张；CSV: `tables/importance_vs_delta_r2.csv`
