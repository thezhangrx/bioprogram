# R4 执行记录：effect gate 改为模型等权均值口径

> 阶段：**R4 / R1–R6**　原则：改变 effect 的统计单位，不调阈值（`min_absolute_delta_r2` 仍为 0.01）。

---

## 1. 改动

### 1.1 配置（`EvidenceRuleConfig`）

```python
effect_gate_mode: str = "model_mean"   # 默认; "any_model" 保留为敏感性分析
```

### 1.2 统计定义（`integration.py::environment_evidence_matrix`）

$$\Delta R^2_{\text{factor}} = \frac{1}{M}\sum_{m=1}^{M}\Delta R^2_m,\qquad M=7 \text{ 个模型配置等权}$$

* 每个模型贡献 1 票；**不按样本量、不按细胞系数目加权**；不因某模型更极端而加权。
* 旧口径 `any_model`（任一模型 \|ΔR²\| ≥ 0.01）降级为**敏感性分析**，默认关闭。
* 明确这是 **cross-model average effect**，不是 sample-level population effect。

### 1.3 保留异质性（不靠均值掩盖分歧）

新增输出列：`median_effect`、`n_models`、`model_direction_conflict`、`effect_gate_value`、`effect_gate_mode`；
原有 `model_effects`（每模型明细）与 `ci_low/ci_high`（effect CI）继续保留。

## 2. 本批结果（关键变化）

| factor | mean ΔR²（M=7 等权） | median | 方向冲突 | effect gate（原 any_model） | effect gate（R4 model_mean） | statistical gate | robustness | **Tier** |
| :--- | ---: | ---: | :--- | :--- | :--- | :--- | :--- | :--- |
| ctcf | −0.00095 | +0.00295 | 是 | pass（linear −0.0281） | **fail** | pass | fail（CI 跨 0） | Inconclusive |
| dnase | −0.00202 | −0.00005 | 是 | fail | fail | pass | fail（CI 跨 0） | Inconclusive |
| h3k4me3 | −0.00594 | −0.00309 | 是 | pass（linear −0.0246） | **fail** | pass | pass | Inconclusive（cell-line 冲突） |
| **rrbs** | **−0.00932** | −0.00303 | 是 | pass（linear −0.0529） | **fail** | pass | pass | **Tier 1 → Tier 2** |

**RRBS 的降级原因（代码逻辑，非调阈值）**：
1. 原 effect 门由**唯一一个模型**（linear）触发 —— 去掉 linear 后其余 6 个模型最大 \|ΔR²\|=0.0048；
2. R4 后 effect 门改用 7 模型等权均值：\|−0.00932\| < 0.01 → **effect gate = fail**；
3. R3 已规定统计门不能单独提升 → RRBS 落到 **Tier 2**（覆盖度 7 ≥ 2、concordance 0.857 ≥ 0.80、CI 不跨 0）。

结果分布：**环境因子 0 个 Tier 1；3 个 Inconclusive + 1 个 Tier 2**；motif 行不受影响（100 Inconclusive / 496 Tier 3）。

## 3. 模型间异质性（避免被均值掩盖）

四个因子的 `model_direction_conflict` 均为 **True**（7 个模型中同时存在正、负效应），
`model_effects` 逐模型明细完整保留，Table 3 / 资产中同时给出 mean 与 median，
论文表述需说明"跨模型方向并不统一"（与既有 §3.3 的观察一致）。

## 4. 测试

| 测试 | 结果 |
| :--- | :--- |
| `test_model_mean_mode_blocks_single_extreme_model`（1 个极端模型不能再决定 effect 门） | ✅ |
| `test_any_model_mode_is_sensitivity_only`（显式切到 any_model 时恢复旧口径） | ✅ |
| `test_heterogeneity_is_preserved`（median / n_models / 方向冲突 / 逐模型明细） | ✅ |
| `analysis/tests/test_evidence_tier_rules` | **25 项通过** |
| `unittest discover analysis/tests` | **193 项通过** |

## 5. 进入 R5 的判定

R4 验证通过：**effect 门口径已改为模型等权均值、RRBS 如期降为 Tier 2、异质性列齐全、测试全绿**
→ 允许进入 **R5（concordance 分母改为全部有效模型）**。
