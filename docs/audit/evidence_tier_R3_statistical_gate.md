# R3 执行记录：统计门不得单独提升到 Tier 1

> 阶段：**R3 / R1–R6**　原则：只改"提升规则"，不改阈值、不改统计方法。

---

## 1. 改动

### 1.1 配置（`analysis/config.py::EvidenceRuleConfig`）

```python
statistical_gate_can_promote: bool = False   # R3: 统计证据不能单独提升 Tier 1（仅供回归对照）
```

### 1.2 分级函数（`integration.py::classify_evidence_tier`）

三个门**显式区分**并各自作为入参：

| 门 | 定义 | 作用 |
| :--- | :--- | :--- |
| `effect_gate` | 达到最小绝对预测增益 `\|ΔR²\| ≥ evidence.min_absolute_delta_r2` | **可提升 Tier 1** |
| `statistical_gate` | 存在统计证据（permutation 存在性证据 / motif FDR） | 支持、限制、参与 Tier 2 与注释；**默认不可单独提升 Tier 1** |
| `robustness_gate` | 方向一致率达标 **且** CI 不跨 0 | Tier 1 的必要条件（显式化原有隐含条件） |

```python
can_promote  = effect_gate or (statistical_gate and config.evidence.statistical_gate_can_promote)
supportive   = effect_gate or statistical_gate        # 供 Tier 3（单模型 + 支持性证据）
Tier1 ⇔ coverage ≥ 2 ∧ concordance ≥ 0.80 ∧ robustness_gate ∧ can_promote
```

兼容性：旧调用方（motif 路径）只传合并布尔量时，该布尔量被视为 `effect_gate`（行为不变；
motif 的 `supporting = 1`，本来就只能落在 Tier 3/Inconclusive）。

### 1.3 输出列

新增 `robustness_gate_pass`、`tier_promotion_gate`（`effect` / `statistical` / `statistical(disabled)` / `none`）。

## 2. 本批效果（`evidence_matrix.csv`）

| factor | mean ΔR² | effect gate | statistical gate | robustness gate | **提升门** | Tier |
| :--- | ---: | :--- | :--- | :--- | :--- | :--- |
| ctcf | −0.00095 | pass | pass | **fail（CI 跨 0）** | effect | Inconclusive |
| dnase | −0.00202 | fail | pass | fail（CI 跨 0） | **statistical(disabled)** | Inconclusive |
| h3k4me3 | −0.00594 | pass | pass | pass | effect | Inconclusive（`Context-conflicting`） |
| rrbs | −0.00932 | pass | pass | pass | effect | **Tier 1（仍）** |

**必须说明的一点**：R3 **没有**把 RRBS 降级——因为当前 effect 门口径是
`any(|per-model mean| ≥ 0.01)`，而 RRBS 恰好由 linear 单个模型（−0.0529）满足。
R3 的实际作用是：把"统计门单独提升"这条路径关掉（本批 dnase 的 `tier_promotion_gate`
已显示为 `statistical(disabled)`）。**RRBS 的降级由 R4（effect 门改为模型等权均值口径）完成**，
这与预期一致，不是通过调阈值实现。

## 3. 测试

| 测试 | 结果 |
| :--- | :--- |
| `test_permutation_fdr_alone_cannot_promote_to_tier1`（R3 语义：仅统计门 → Tier 2） | ✅ |
| `test_statistical_promotion_is_parameterized`（显式开启 `statistical_gate_can_promote` 时恢复旧 OR 行为，仅作回归对照） | ✅ |
| `test_ci_gate_is_parameterized`、`test_insufficient_coverage` 等既有用例 | ✅ |
| `analysis/tests/test_evidence_tier_rules` | **22 项通过** |
| `unittest discover analysis/tests` | **193 项通过** |

## 4. 进入 R4 的判定

R3 验证通过：**三门外显式化、统计门不能单独提升、Tier 结果与预期一致（RRBS 仍由 effect 门支撑）、测试全绿**
→ 允许进入 **R4（effect gate 改为模型等权均值口径）**。
