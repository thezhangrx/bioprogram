# Evidence Tier 最终统计学与代码一致性审计

> 对象：`analysis/evidence/integration.py::classify_evidence_tier` 及其输入链；批次 `results/batches/batch_20260909_full`
> 方法：全部结论沿实际运行代码与真实资产核对，不依 README/注释推断；定量脚本
> `docs/audit/audit_factor_level_permutation.py`（只读）、`docs/audit/audit_min_absolute_delta_r2.py`（只读）
> 状态：**本报告只做审计，未修改任何 production code。**

> **实施状态（2026-09-13 更新）**：本审计提出的 R1–R6 已**全部实施**并逐阶段验证
> （`evidence_tier_R1_audit.md`、`R2_fdr_aggregation.md`、`R3_statistical_gate.md`、`R4_effect_aggregation.md`、`R5_concordance.md`），
> 结果变化见 `docs/audit/evidence_tier_before_after.md`：**环境因子 Tier 1 数量 1 → 0，RRBS 由 Tier 1 降为 Tier 2**。
> 本文保留为审计当时的历史记录；**当前权威口径以 `docs/audit/evidence_tier_scientific_definition.md` 与
> `docs/paper/evidence_tier_provenance.md` 为准**。

 推荐方案见 §10 与结尾"待确认的实施计划"。

---

## 结论速览（Q1–Q10）

| # | 问题 | 结论 | 关键证据 | 需改代码 | 需重算 | 需改论文 |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- |
| **Q1** | 当前 factor-level minimum FDR 是否可以称为 factor-level FDR？ | **不可以** | BH family 仅含同一 `(split,cell,model)` 下的 4 个 factor（63 族×4 行）；factor 级取值是对 63 个上下文取 **min**，无任何族间校正 | 是（命名/语义） | 是 | 是 |
| **Q2** | 是否存在 post-selection / extremum-selection 问题？ | **存在，且量级明确** | 4 个因子的 min p 全部 = 0.006993（同一值）；Bonferroni FWER = 0.441（63 上下文）/ **0.245**（35 个去重上下文） | — | — | — |
| **Q3** | 是否需要重新定义 factor-level statistical evidence？ | **需要** | `min(FDR)` 只能作为 existence-oriented 证据；正式 factor 级检验需组合**原始 p** 或构造 factor 级置换统计量 | 是 | 是 | 是 |
| **Q4** | cross-model bootstrap 应如何正式命名？ | **95% cross-model bootstrap interval（n = 7 model configurations）** | `bootstrap_main_effects`：unit=模型、等权、B=2000/seed 2024；7 模型共享同一份 16 749 条数据、标签、预处理、划分 | 是（命名/文档） | 否 | 是（Limitations） |
| **Q5** | direction concordance 的 denominator 是否存在虚高风险？ | **结构上存在**（`+ + 0 0 0 0 0` → 100 %），但本批**无 exact zero**，当前值与"分母=全部模型"相同 | `integration.py:18-28` 分母 = 非零方向；本批 4 个因子的 `==0` 计数均为 0 | 是（分母改为全部模型） | 否（本批结果不变） | 否 |
| **Q6** | 是否需要 neutral dead-zone？ | **本批不需要**；若引入 τ 必须有数据依据，**τ=0.01 会退化为全中性（禁用）** | 最小 \|ΔR²\|：dnase 2.5e-05、rrbs 6.5e-05、h3k4me3 2.7e-04、ctcf 8.8e-04，均 ≫ 浮点噪声（1e-16）；τ=1e-4 只把 dnase 0.714→0.600、rrbs 0.857→0.833（不改变任何 Tier） | 否（改用分母口径即可） | 否 | 否 |
| **Q7** | `unstable_effect_threshold=10` 的正式定位？ | **Numerical Divergence Rejection Criterion（工程性数值发散剔除门）**，不是统计阈值 | 代码为 `abs(main_r2_delta) < 10`；`collect_results.filter_valid` 另有 `\|R²\|>10 / MAE>10 / RMSE>10` | 是（统一命名+统一适用） | 是（见下） | 是（方法措辞） |
| **Q8** | RRBS Tier 1 是否仍然成立？ | **按当前实现"成立"，但两条门都不可防守**：effect 门仅由 linear 一个模型触发（其余 6 个 ≤0.0077），统计门是 63 上下文 min-FDR | 见 §3、§8 | 是 | 是 | 是 |
| **Q9** | 若成立，其 Effect / Statistical gate 分别是什么？ | Effect gate = **Pass（仅 linear，\|Δ\|=0.0529）**；Statistical gate = **Pass（min FDR 0.0093，来自 `all/hek293t/linear`）**；CI 不跨 0、concordance 0.857 | 同上 | — | — | — |
| **Q10** | 当前 Evidence Tier 能否作为论文最终版？ | **不能** | 统计门的因子级合法性不成立（Q1–Q3）+ 置换输入含发散值（§7）+ effect 门由单一不稳定模型决定（§3） | 是 | 是 | 是 |

**总体建议：`REDEFINE`（门槛语义与命名）+ `RECOMPUTE`（置换了输入与 Tier 资产）。** 预期结果：**RRBS 由 Tier 1 → Tier 2，本批不再有任何环境因子达到 Tier 1。** 该结论不因"保住 Tier 1"而调整。

---

## 1. 当前 Production Tier 规则（以运行代码为准）

**唯一权威实现**：`analysis/evidence/integration.py::classify_evidence_tier`（`:43-65`）。
调用点：`environment_evidence_matrix`（环境行，`:184`）、`sequence/motif/pipeline.py::motif_evidence_rows`（motif 行，`:362`）。

### 1.1 入参与对应统计量

| 入参 | 来源统计量 | 单位 | 是否真正决定 Tier |
| :--- | :--- | :--- | :--- |
| `applicable_model_count` | 有有限稳定主效应的模型数 | 模型 | ✅（仅用于 `coverage==0 → No current evidence`） |
| `supporting_model_count` | 与"模型等权均值"同号的模型数 | 模型 | ✅ Tier1/Tier2 的覆盖度门槛 |
| `concordance` | 多数方向占比（分母 = **非零方向**） | 模型 | ✅ 仅 Tier 1 |
| `strong_stat_or_attribution` | `effect_gate OR statistical_gate` | — | ✅ 强度门 |
| `ci_crosses_zero` | 跨模型 bootstrap CI 是否跨 0 | 模型 | ✅ 一票否决（最优先） |
| `conflicting_direction` | 方向冲突标记 | — | ✅ 一票否决 |
| 环境行附加：`cell_line_consistency` | 跨细胞系上下文标签众数 | cell line | ✅ `Context-conflicting` 一票否决 |

### 1.2 只有以下阈值进入 Tier（其余为其它资产使用）

| 阈值 | 配置 | 参与 Tier |
| :--- | :--- | :--- |
| 覆盖度 ≥ 2 | `consensus.min_coverage` | ✅ |
| 方向一致率 ≥ 0.80 | `consensus.direction_concordance` | ✅ |
| 最小绝对预测增益 0.01 | `evidence.min_absolute_delta_r2` | ✅（effect 门） |
| 置换 FDR < 0.05 | `statistical.fdr_weak` | ✅（统计门） |
| CI 迭代数 ≥ 200、CI 跨 0 | `evidence.min_bootstrap_iterations` / `ci_crosses_zero_forces_inconclusive` | ✅ |
| 数值发散门 \|Δ\| < 10 | `consensus.unstable_effect_threshold` | ✅（矩阵与 CI，**置换路径缺失**，见 §7） |
| SNR 2.5/1.8/1.2、最小效应量 0.005、FDR 0.001/0.01 | `attribution.*` / `statistical.fdr_strong`、`fdr_moderate` | ❌ 仅 Importance–ΔR² 资产 |

### 1.3 最终 Tier 资产由哪些表生成

```
environment_main_effects.csv ─┐
cellline_effects.csv ─────────┼→ environment_evidence_matrix() ─┐
bootstrap_main_effects.csv ───┤                                  ├→ evidence_matrix.csv
permutation_results.csv ──────┘                                  │   → 06_evidence_integration.md
motif_enrichment / candidates ─→ motif_evidence_rows() ──────────┘   → 07_biological_hypotheses.md
                                                                     → figures/06_evidence/*
                                                                     → Table 3 / Fig. 7
anova_results.csv ─────────────→ Fig. 3D / Table 3 的 anova_F、anova_p（**不进 Tier**）
```

---

## 2. factor-level permutation 证据的真实计算链

```
environment_conditional_delta_r2.csv   (2016 行；键 = split, cell, model, factor, background)
        │  ※ 无 |Δ| < 10 过滤（见 §7）
        ▼
permutation_main_effects()             (analysis/stats/tasks.py:295-331)
   ├─ 每个 (split, cell, model, factor) 取 8 个 background 的条件增量
   ├─ H0: 条件增量的背景均值 = 0；sign-flip 随机化，two-sided，B=1000，seed=2024
   └─ 输出 252 行（63 上下文 × 4 factor），列 p_value / n_values=8 / family_key
        ▼
apply_fdr()                            (tasks.py:401-421)
   └─ BH，family_key = `environment_main|<split>|<cell>|<model>`（**每族恰好 4 行 = 4 个 factor**）
        ▼
integration.py:163-178
   ├─ psub = permutation[factor == f]
   ├─ perm_p   = psub.p_value.min()      ← **取最小原始 p**
   ├─ perm_fdr = psub.FDR.min()          ← **取最小已校正 FDR**
   └─ statistical_gate_pass = perm_fdr < statistical.fdr_weak (0.05)
        ▼
classify_evidence_tier()
```

**A. 到底取的是哪一个？** → **两者都取，判定用 FDR**：`perm_p = min(raw p)`（仅记录），
`perm_fdr = min(BH-FDR)`（**决定统计门**）。BH 本身在同一 `(split,cell,model)` 内的 4 个 factor 之间做，
已用真实数据校验（stored = 手算 BH，逐位一致）。

**B. 一个 factor 包含多少 edge / context？**

| factor | main-effect 行 | BH 族数（每族 4 行） | 上下文总数 | 去重后（去 `all`，本批 `all ≡ single`） |
| :--- | ---: | ---: | ---: | ---: |
| ctcf | 63 | 63 | 63 | 35 |
| dnase | 63 | 63 | 63 | 35 |
| h3k4me3 | 63 | 63 | 63 | 35 |
| rrbs | 63 | 63 | 63 | 35 |

上下文构成：`single` 4 细胞系 × 7 模型 + `all` 4 留出细胞系 × 7 模型 + `mixed` 1 × 7 = 63。

**C. 这些检验是否独立？** → **不独立**，且有完全重复：

| 依赖来源 | 证据 |
| :--- | :--- |
| 共享模型 | 63 行只来自 **7 个模型配置**（每模型 9 个上下文） |
| 共享细胞系/序列 | 同一模型在 4 个细胞系上共享预处理与标签 |
| 共享背景 | 8 个背景是**嵌套环境组合**（sequence ⊂ sequence+ctcf ⊂ …），其条件增量彼此相关 |
| 共享 seed | main-effect 行不带 seed（`random_seed=None`），混合划分的多 seed 已在上游平均 |
| **完全重复** | `all` 与 `single` 的 p 值**63 对中 28 对完全相同**（本批 `all` 退化为 `single`） |
| 检验统计量离散 | 全部 252 行 `n_values=8` → sign-flip 零分布只有 2⁸=256 种符号模式，p 值下界 ≈ 2/256 = **0.0078** |

---

## 3. `minimum FDR` 的统计合法性

**结论：不能解释为 factor-level FDR。**

1. **族内校正只覆盖 4 个 factor**：BH 的 family 是"同一上下文下的 4 个 factor"，因此"FDR 0.0093"实际只比原始 p 大 4/3 倍；它**没有**对"跨 63 个上下文挑选最小"这一步做任何校正。
2. **选择偏倚（extremum selection）**：做法是 `min` over 63（去重 35）个依赖检验 → 该量的分布**不是**任何单一零假设下的 p/FDR 分布；在全局零假设下，取最小本身就会给出很小的值。
3. **量级核对（Bonferroni 上界，最保守）**：min raw p = 0.006993 → FWER ≤ 63 × 0.006993 = **0.441**（全部上下文）/ 35 × 0.006993 = **0.245**（去重后）。**在 0.05 水平上不显著。**
4. **四个因子同时取到同一个最小值**（0.006993 = 7/1001）：这是"同一下界 + 共同上下文"的典型特征，而非四个独立因子各自显著。
5. **下界不可忽略**：n_values=8 的 sign-flip 检验最极端事件是"8 个背景同号"，其零概率 = 2/2⁸ = 0.0078 —— 观测到的 0.006993 正是这个**下界**。也就是说，该检验**根本无法给出小于 ~0.008 的 p 值**，达不到常见的 0.001/0.005 级别；在 35 个去重上下文里，22 个（去重后 12 个）上下文命中该下界。
6. **`permutation_selection` 列只提供 provenance**（记录"取族内最小 FDR"这一事实），**不能**把该值恢复成有 Type-I 控制的 factor 级量。

> 因此：`min(FDR)` 的合法解释只有一种 —— **"该 factor 在至少一个被测试上下文中达到了最小可观测的 edge 级 FDR 下界"**，属 existence-oriented 证据，**不是** factor-level FDR。

---

## 4. factor-level aggregation 候选方案比较

| 维度 | **方案 A：保留 min FDR** | **方案 B：组合原始 p**（Fisher / Simes / HMP / Cauchy） | **方案 C：真正的 factor 级置换检验** |
| :--- | :--- | :--- | :--- |
| 统计解释 | "至少在 1 个上下文存在 edge 级证据"（存在性） | "该 factor 的多个上下文 p 值整体偏离零"（全局检验） | "该 factor 的整体统计量在 factor 级零分布下的位置" |
| 多重比较风险 | ❌ 无族间控制（FWER ≥0.245） | ✅ 组合本身给全局 p，再对 4 个 factor 做 BH | ✅ 一步到位（一次检验 + 对 4 个 factor 的 BH） |
| 依赖结构要求 | 不要求，但解释力最弱 | ⚠️ Fisher 要求独立；Simes/HMP 在正相关下较稳健但**非严格保证**；本批为**强正相关 + 完全重复**（all≡single） → 需先按上下文去重 | 需在零分布中保留上下文间的相关结构（在每个上下文内做 sign-flip、对 factor 级统计量联合重采样） |
| 实现复杂度 | 0（现状） | 中（需从现有 p 值算组合量；不需重训） | 中高（需扩展 `permutation_main_effects` 输出 factor 级统计量与其零分布；不需重训） |
| 与现有设计兼容 | 完全兼容 | 兼容（新增一列） | 兼容（沿用 sign-flip 框架与 seed） |
| 论文可防守程度 | 低（"取最小"难以防守） | 中（需说明依赖结构与去重） | **高**（单次检验、族内 BH、零分布明确） |
| 附加问题 | — | 仍需处理 p 值离散/下界（n=8 → 下界 0.0078） | 同样受限：因子级统计量的零分布来自相同背景结构，但**下界问题被聚合缓解** |

**决策：`REDEFINE` + `RECOMPUTE`**
* **立即（最小改动）**：方案 A **降级为存在性证据**——改名（不再称 factor-level FDR）、记录测试上下文数、给出 FWER 上界；**统计门不再单独把 factor 提升到 Tier 1**（需同时通过 effect 门，或采用可防守的 factor 级标准）。
* **推荐（正式）**：实施方案 C（factor 级置换检验，复用现有 sign-flip 框架与 seed，不重训）；在此之前论文按"存在性证据 + FWER 说明"表述。
* **不推荐**：直接对 FDR 再做 Fisher/Simes/HMP（把已校正量当原始 p 用，方法上错误）。

---

## 5. Cross-model bootstrap 的准确解释与命名

| 项 | 事实（代码/资产核对） |
| :--- | :--- |
| 重采样单元 | **模型配置（model configuration）**，n = 7 |
| 是否等于 7 次独立实验 | **否**：7 个模型共享同一份 16 749 条数据、同一标签、同一预处理、同一划分 |
| 统计量 | 先按模型求稳定主效应均值（模型等权），再对 7 个模型百分位 bootstrap（B=2000, seed=2024, α=0.05） |
| 覆盖保证 | n=7 的百分位 bootstrap 覆盖概率**没有**可靠保证（小样本 + 离散 + 强相关） |
| 复算核对 | `estimate` 与 7 模型等权均值逐位一致；CI：ctcf [−0.0105,+0.0048]、dnase [−0.0052,+0.0004]（跨 0）、h3k4me3 [−0.0129,−0.0010]、rrbs [−0.0242,−0.0010]（不跨 0） |

**命名建议**：**"95% cross-model bootstrap interval (n = 7 model configurations)"**。
理由：它明确写出重采样单元与样本量，最不容易被读成"16 749 条 sgRNA 的抽样不确定性"；
`Cross-Architecture Consensus Interval` 含义偏"共识"，`Model-level Bootstrap CI` 亦可接受但不如前者明确。
**禁止**表述为 biological replication / independent replicates / 样本级置信区间。
**Limitations 必写**：n=7 下百分位 bootstrap 的覆盖性质有限，该区间只用于刻画 effect 在**不同模型归纳偏置之间的一致性/稳定性**。

---

## 6. Direction concordance 的分母与 neutral rule

**代码事实**（`integration.py:18-40`）：`+`/`−`/`0` 由 `e > 0 / e < 0 / e == 0` 判定（**精确等于 0**，无 τ），
`concordance = max(计数) / len(非零符号)` → **分母 = 非零方向（定义 B）**。

| factor | n | + | − | ==0 | 当前(定义 B) | 定义 A（分母=全部） | τ=1e-4（B） | τ=0.01（B，禁用） |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ctcf | 7 | 6 | 1 | 0 | 0.857 | 0.857 | 0.857 | 1.000（6 中性） |
| dnase | 7 | 2 | 5 | 0 | 0.714 | 0.714 | 0.600（2 中性） | 全中性 |
| h3k4me3 | 7 | 1 | 6 | 0 | 0.857 | 0.857 | 0.857 | 1.000（6 中性） |
| rrbs | 7 | 1 | 6 | 0 | 0.857 | 0.857 | 0.833（1 中性） | 1.000（6 中性） |

结论：
1. **虚高风险是结构性的**（`+ + 0 0 0 0 0` → 1.00），但**本批无 exact zero**，定义 A 与定义 B 给出相同数值 → 当前结论未被虚高，但规则应改成**分母 = 全部适用模型（定义 A）**，代价为零、无需引入任意 τ。
2. **τ = 1e-4 缺乏数据依据**：本批最小 \|ΔR²\| = 2.5e-05（dnase），远大于浮点噪声（~1e-16），且换 τ 不改变任何 Tier；`τ = 0.01` 会把 6–7 个模型判为中性、使 concordance 退化到 1.0，**必须禁用**。
3. 若未来数据出现 `\|ΔR²\| ≤ 1e-6` 量级的"伪零"，再以**实测数值噪声尺度**为依据引入 dead-zone，并参数化（`direction_dead_zone`），而不是照搬常数。

---

## 7. `unstable_effect_threshold = 10` 审计

* **精确形式**：`abs(main_r2_delta) < 10`（严格小于）= 保留；用于
  `environment_evidence_matrix`（`:118-120`）与 `bootstrap_main_effects`（`tasks.py:217-219`）。
  另一处独立形式：`collect_results.filter_valid`（`|R²| > 10 或 MAE > 10 或 RMSE > 10` → 从汇总表剔除）。
* **定位**：**Numerical Divergence Rejection Criterion（工程性数值发散剔除门）**。
  `R² = 1 − SS_res/SS_tot`，极端负 R² 意味着训练/评估已经数值异常；它**不是** statistical cutoff、
  stability significance threshold 或 biological threshold，也不应被写成"ΔR² > 10 有统计学意义"。
* **过滤在三条路径上的适用情况（逐一核对代码）**：

| 路径 | 是否过滤 | 代码 |
| :--- | :--- | :--- |
| 证据矩阵（因子主效应） | ✅ `abs(main_r2_delta) < 10` | `integration.py:118-120` |
| 跨模型 bootstrap CI | ✅ 同一阈值 | `tasks.py:bootstrap_main_effects` |
| 边级置换（`permutation_environment_edges`） | ✅ 经 `_valid_row`（`\|R²\|>thr` 判无效） | `tasks.py:85-103` |
| 交互置换（`permutation_interactions`） | ✅ 同上 | `tasks.py` 交互路径 `valid = {… _valid_row(row, thr)}` |
| **因子主效应置换（`permutation_main_effects`）** | ❌ **无任何过滤** | `tasks.py:295-331` |

* **⚠ 发现一致性缺陷（本次审计新发现）**：该过滤**没有应用到 `permutation_main_effects` 的输入**。
  * `environment_conditional_delta_r2.csv` 中有 **130 行 |ΔR²| > 1e6（全部来自 linear 模型，max 1.24×10¹⁹）**；
  * 它们直接进入 `permutation_main_effects`，产生 **28 行 |observed_effect| > 10 的置换检验（全部 linear）**，
    即 **11 % 的 factor 级检验建立在发散值上**（其 p 值落在 0.40–0.88，未直接制造假阳性，但检验本身无效、且虚增了测试多重性）；
  * 后果：矩阵/CI 用"过滤后"数据、置换用"未过滤"数据 → 三者口径不一致，属**代码一致性缺陷**，必须修复（把同一 `unstable_effect_threshold` 应用到置换输入）。

---

## 8. RRBS Tier 1 的合法性分析

### 8.1 当前实际状态（Tier 1 的两条门）

| 门 | 当前是否通过 | 证据 |
| :--- | :--- | :--- |
| 覆盖度 ≥2 | ✅ 7 | — |
| 方向一致率 ≥0.80 | ✅ 0.857（6 负 / 1 正） | §6 |
| CI 不跨 0 | ✅ [−0.0242, −0.0010] | 跨模型 bootstrap |
| **Effect gate** | ✅ **仅因 linear 一个模型** | per-model 主效应：linear **−0.0529**、cnn3 +0.0010、cnn5 −0.0020、cnn7 −0.0001、mlp −0.0034、transformer −0.0030、xgboost −0.0048 → **6/7 个模型 \|Δ\| < 0.0077** |
| **Statistical gate** | ✅（但合法性不足） | min FDR 0.0093 来自 `all/hek293t/linear`；FWER 上界 0.245–0.441；且 p 处于 sign-flip 下界 |
| `Context-conflicting` | 否（标签 Uncertain） | — |

### 8.2 判定

1. **Effect gate 不可防守**：门是 `any(|per-model mean| ≥ 0.01)`，实际由**唯一一个模型**触发，而该模型正是
   含 130 行发散条件增量、56/192 次运行发散的 linear。模型等权均值 |−0.0093| < 0.01；
   也就是说：**去掉 linear，RRBS 立刻不通过 effect 门**。
2. **Statistical gate 不可防守**：如 §2/§3，`min(FDR)` 无 factor 级 Type-I 控制；Bonferroni 上界 0.245（去重）已 > 0.05；
   且 0.006993 是 sign-flip 零分布的下界值（2/2⁸），分辨率不足。
3. **因此：RRBS 当前 Tier 1 的结论强度必须下调。** 按 §10 推荐方案修正后：

| factor | 模型等权 ΔR² | Effect gate（均值口径） | Statistical gate（可防守标准） | CI 不跨 0 | concordance | **修正后 Tier** |
| :--- | ---: | :--- | :--- | :--- | ---: | :--- |
| ctcf | −0.00095 | fail | fail | 否 | 0.857 | Inconclusive |
| dnase | −0.00202 | fail | fail | 否 | 0.714 | Inconclusive |
| h3k4me3 | −0.00594 | fail | fail | 是 | 0.857 | Inconclusive（`Context-conflicting`） |
| rrbs | −0.00932 | fail | fail | 是 | 0.857 | **Tier 2**（覆盖度与一致率达标，强度门均不通过） |

→ **本批不再有环境因子达到 Tier 1。** 这是"宁可降低结论强度"的必然结果，而不是为了让结果更好看。

---

## 9. ANOVA 与 Evidence Tier 的独立性（复核）

* `environment_evidence_matrix()` 的签名与调用（`pipeline.py:412-415`）**不含 ANOVA**；ANOVA 只出现在 `anova_results.csv` → Table 3 的 `anova_F/anova_p` 与 Fig. 3D；测试 `TestAnovaIndependence` 固定该边界。
* 正确表述：**Edge-level evidence evaluates specific incremental predictive effects under defined backgrounds, whereas factorial ANOVA evaluates global factor and interaction effects across the factorial design.** 两者 **address different inferential questions**，结果 **can be compatible**。
* **禁止**："ANOVA 宏观 / permutation 微观"；也**禁止**把二者写成"independently validate each other"（它们不是相互独立验证，只是回答不同问题）。

---

## 10. 最终推荐方案（KEEP / REDEFINE / RECOMPUTE）

**判定：`REDEFINE`（门槛语义与命名）+ `RECOMPUTE`（置换输入与 Tier 资产）。** 具体 6 项最小改动：

| # | 改动 | 类型 | 是否改变本批 Tier |
| ---: | :--- | :--- | :--- |
| R1 | 把 `unstable_effect_threshold` **一致地**应用到置换输入（剔除 130 行发散条件增量 / 28 行无效检验） | **Bug 修复**（代码一致性） | 间接（去掉无效检验与虚增多重性） |
| R2 | 把 `min(FDR)` 正式更名为 **"minimum edge-level FDR across tested contexts (existence-oriented)"**，输出 `n_contexts`、`n_contexts_unique`、`min_p_fwer_bound`，并在文档/论文中声明它不是 factor-level FDR | 语义/命名 | 否 |
| R3 | 统计门**不再单独**把 factor 提升到 Tier 1：要么要求 effect 门同时通过，要么采用可防守的 factor 级标准（先 Bonferroni/FWER 上界，随后实施方案 C 的 factor 级置换检验） | **门槛定义** | **是**（RRBS → Tier 2） |
| R4 | Effect gate 改为**模型等权均值口径** `\|overall_effect\| ≥ min_absolute_delta_r2`（与报告值、CI 同口径），并把"any-model"作为敏感性分析单独报告 | **门槛定义** | **是**（RRBS/cnn 等不再靠单模型通过） |
| R5 | `direction_concordance` 分母改为**全部适用模型**（定义 A），参数化；不引入 τ=1e-4；若未来需要 dead-zone，必须以实测噪声尺度为依据并参数化 | 定义修正 | 否（本批数值不变） |
| R6 | 命名与 Limitations：**95% cross-model bootstrap interval (n = 7 model configurations)**；说明其度量的是跨模型一致性、非样本抽样不确定性；n=7 百分位 bootstrap 覆盖有限 | 表述 | 否 |

**重算范围**（R1/R3/R4 生效后）：`permutation_results.csv` → `evidence_matrix.csv` → Table 3 / Fig. 7 / §3.8 表述；
**不需要重新训练模型，也不需要重跑 1 344 次实验**（置换与 Tier 均可用现有 predictions 与中间表重算）。
若采用方案 C（factor 级置换检验），同样只需重跑置换步骤。

**明确不做**：不为提高 Tier 1 数量调整任何阈值；不把 ANOVA 塞进 Tier；不把 7 个模型当独立生物学重复；
不新增与 factor 级证据无关的统计方法。

---

## 待确认的实施计划（等你确认后执行）

1. `analysis/config.py`：新增 `evidence.statistical_gate_requires`（`"effect_and_factorwise"` 默认）与
   `evidence.factorwise_alpha`（默认 0.05）；`min_absolute_delta_r2` 口径由 "any model" 改为 "model-equal-weight mean"
   并保留 `effect_gate_mode ∈ {mean, any_model}` 以便敏感性分析。
2. `analysis/stats/tasks.py`：置换输入加 `|Δ| < unstable_effect_threshold` 过滤（与矩阵/CI 一致）。
3. `analysis/evidence/integration.py`：统计门改用 factor 级可防守标准 + 输出 `n_contexts`/`min_p_fwer_bound`/`effect_gate_mode`；
   `direction_concordance` 分母改为全部适用模型。
4. 测试：扩充 `test_evidence_tier_rules.py`（min-FDR 不得称 factor FDR、FWER 门槛、分母口径、发散过滤、mean vs any-model 敏感性）。
5. 重算并更新 `evidence_matrix.csv`、`06_evidence_integration.md`、Table 3、Fig. 7、补充表 S1，同步论文 §3.8/§5/§2.10。
6. 更新 `docs/paper/evidence_tier_provenance.md` 的变更记录与回归证据。

预期重算结果：**环境因子 0 个 Tier 1，RRBS = Tier 2，其余 Inconclusive**；motif 行不受影响。
