# Importance 指标选择说明 (Importance Metric Selection)

> 本文件解释二维 Importance–ΔR² 图中每个模型为什么选择该 Y 指标，以及哪些指标**没有**被当作 Y。

## 1. 各模型 Y 轴主指标

| 模型 | Y 轴主指标 | 启用 | 稳健性字段 | 统计字段 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| linear | Linear_Coefficient | yes | - | FDR | Y=\|系数\|; 方向由 signed 系数保留; FDR 仅用于统计筛选 |
| xgboost | TreeSHAP | yes | SHAP_SNR | - | Y=mean(\|SHAP\|); Gain/Weight/Cover 为树内部重要性(无方向), 仅 tooltip |
| mlp | MLP_IG | yes | IG_SNR | - | Y=mean(\|IG\|); IG_SNR 仅稳健性筛选 |
| cnn | CNN_IG | yes | ISM_SNR | - | Y=CNN_IG; 无 IG_SNR 输出 (不得假装存在); ISM_SNR 作为稳健性筛选但 ISM 语义为突变效应 |
| transformer | (unavailable) | no | Attention_SNR | - | 未输出 Transformer_IG (函数存在但从未调用/未入白名单); Attention 无方向, 不作为主 Y |

## 2. 明确不作为 Y 的字段与原因

| 字段 | 模型 | 不作为 Y 的原因 |
| :--- | :--- | :--- |
| XGB_Gain | xgboost | 树内部 importance (split gain), 无方向/无归因符号 |
| XGB_Weight | xgboost | 树内部 importance (split 次数), 无方向 |
| XGB_Cover | xgboost | 树内部 importance (覆盖样本数), 无方向 |
| SHAP_SNR | xgboost | 归因稳健性 (mean/std), 不是 effect magnitude |
| IG_SNR | mlp | 归因稳健性, 用于筛选而非 Y |
| CNN_ISM | cnn | counterfactual mutation effect (核苷酸替换), 属另一张 sequence 图 |
| ISM_SNR | cnn | 突变效应稳健性, 仅用于筛选 |
| Transformer_Attention | transformer | 注意力权重无正负方向, 不能当 effect |
| Attention_Entropy | transformer | 注意力集中度 (标量), 非 attribution magnitude |
| Attention_SNR | transformer | 注意力稳健性, 非 effect |
| SE | linear | 估计量标准误 (不确定性), 非 importance magnitude |
| t_stat | linear | 统计检验量, 非 importance magnitude |
| p_value | linear | 统计证据, 非 importance magnitude |
| FDR | linear | 统计证据 (多重校正 q 值), 用于筛选而非 Y |

## 3. 语义边界

- **Effect**: ΔR² 等预测增量 → 本图 X 轴；
- **Importance/Attribution**: 主指标 (|系数| / mean|SHAP| / mean|IG|) → 本图 Y 轴；
- **Robustness**: SNR 类 → 只作筛选 (Strong/Moderate/Weak attribution)，不作 Y；
- **Statistical Evidence**: 仅线性 FDR 等合法检验结果 → 只作 linear 的筛选与图例语义；
- 严禁把上述三类加权成综合分，也严禁把 SNR/FDR/Attention 称为 effect 或 significance。
