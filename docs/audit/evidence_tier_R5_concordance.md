# R5 执行记录：concordance 分母改为全部有效模型

> 阶段：**R5 / R1–R6**　原则：修正分母口径，**不引入任何 dead-zone 阈值**。

---

## 1. 改动

`integration.py::direction_concordance(effects, denominator=None)`

```text
concordance = 支持多数方向的模型数 / 全部有效模型配置数        (默认, R5)
            = 支持多数方向的模型数 / 非零方向模型数            (denominator=非零数, 旧口径, 仅回归对照)
```

* 分母默认 = 全部有限效应（有效模型）个数；**中性/精确零不缩小分母**。
* 无效/发散模型仍按数据质量在进入本函数前剔除，其数量由 `n_models` 记录，
  分母由新增列 `concordance_denominator` 记录，中性计数由 `n_neutral_models` 记录。
* **不引入 τ**：`0` 只表示浮点精确为 0。理由（数据依据见最终审计报告 §6）：
  本批最小 \|ΔR²\| = 2.5×10⁻⁵（dnase），远大于浮点噪声（~10⁻¹⁶），
  且 τ=0.01 会让 6–7 个模型变中性并把 concordance 退化为 1.0，属不可用口径。

## 2. 本批结果（数值不变，规则变严）

| factor | concordance（新口径，分母=7） | 旧口径（分母=非零） | 分母 | 中性数 | Tier |
| :--- | ---: | ---: | ---: | ---: | :--- |
| ctcf | 0.857 | 0.857 | 7 | 0 | Inconclusive |
| dnase | 0.714 | 0.714 | 7 | 0 | Inconclusive |
| h3k4me3 | 0.857 | 0.857 | 7 | 0 | Inconclusive |
| rrbs | 0.857 | 0.857 | 7 | 0 | Tier 2 |

本批无精确零 → 两种口径数值相同（**结论未被虚高，但规则不再存在虚高空间**）。

## 3. 测试

| 测试 | 结果 |
| :--- | :--- |
| `test_zeros_do_not_inflate_concordance`（1 正 + 6 零：新口径 1/7，旧口径 1.0） | ✅ |
| `test_denominator_recorded_in_matrix`（分母与中性数落盘） | ✅ |
| `test_all_zero_returns_none`（全中性 → None，不伪造 1.0） | ✅ |
| `analysis/tests/test_evidence_tier_rules` | **28 项通过** |
| `unittest discover analysis/tests` | **196 项通过** |

## 4. 进入 R6 的判定

R5 验证通过：**分母不再因中性缩小、本批数值未变、测试全绿** → 允许进入 **R6（bootstrap 命名与 Limitations）**。
