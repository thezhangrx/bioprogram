# Evidence Tier：修改前 / 修改后对照（R8）

> 阶段：**R8 / R1–R6 全部实施后的结果审计**
> 对照基准 = 本轮开始时（CI 资产已刷新、R1–R6 未实施）的 `evidence_matrix.csv`
> 修改后 = 当前 `results/batches/batch_20260909_full/analyse_out/tables/evidence_matrix.csv`（2026-09-13）
> 说明：**未重新训练任何模型、未重跑 1 344 次实验**，全部用已有中间资产重算。

---

## 1. 总览：Tier 变化

| factor | Old Tier | **New Tier** | 变化 | 原因 |
| :--- | :--- | :--- | :--- | :--- |
| CTCF | Inconclusive | Inconclusive | — | CI 跨 0（−0.0105…+0.0048）；且 cell-line `Context-conflicting` |
| DNase | Inconclusive | Inconclusive | — | CI 跨 0（−0.0052…+0.0004）；方向一致率 0.714 < 0.80 |
| H3K4me3 | Inconclusive | Inconclusive | — | cell-line `Context-conflicting` 一票否决（其余条件满足） |
| **RRBS** | **Tier 1** | **Tier 2** | **↓ 降级** | effect 门由"任一模型"改为**模型等权均值**后 \|−0.00932\| < 0.01 → fail；统计门虽通过但按 R3 **不能单独提升** |

**环境因子 Tier 1 数量：1 → 0。** motif 行不受影响（100 Inconclusive / 496 Tier 3）。

## 2. 逐项明细（修改后，全部由代码输出）

| factor | mean ΔR² | median ΔR² | M | 方向冲突 | effect 门（model_mean） | effect 门值 | statistical 门 | min_edge_FDR | n_contexts | 去重后 | selected_context | FWER 上界 | concordance（分母） | Model-Level Bootstrap | robustness | 提升门 | Tier |
| :--- | ---: | ---: | ---: | :--- | :--- | ---: | :--- | ---: | ---: | ---: | :--- | ---: | :--- | :--- | :--- | :--- | :--- |
| CTCF | −0.00095 | +0.00295 | 7 | 是 | **fail** | 0.00095 | pass | 0.009324 | 61 | 34 | all/hek293t/linear | 0.238 | 0.857 (7) | [−0.01049, +0.00479] 跨 0 | fail | statistical(disabled) | Inconclusive |
| DNase | −0.00202 | −0.00005 | 7 | 是 | **fail** | 0.00202 | pass | 0.013986 | 60 | 33 | all/hl60/transformer | 0.231 | 0.714 (7) | [−0.00523, +0.00040] 跨 0 | fail | statistical(disabled) | Inconclusive |
| H3K4me3 | −0.00594 | −0.00309 | 7 | 是 | **fail** | 0.00594 | pass | 0.009324 | 63 | 35 | all/hek293t/linear | 0.245 | 0.857 (7) | [−0.01290, −0.00099] | pass | statistical(disabled) | Inconclusive |
| RRBS | −0.00932 | −0.00303 | 7 | 是 | **fail** | 0.00932 | pass | 0.009324 | 63 | 35 | all/hek293t/linear | 0.245 | 0.857 (7) | [−0.02419, −0.00095] | pass | statistical(disabled) | **Tier 2** |

> 四个因子的 `model_direction_conflict` 均为 **True**（7 个模型同时给出正、负效应），
> `median ΔR²` 与 `mean ΔR²` 差距明显（例如 CTCF：mean −0.00095 vs median +0.00295）
> —— 异质性未被均值掩盖，已在资产中逐模型列出（`model_effects`）。

## 3. 每项改动的贡献分解

| 改动 | 对 Tier 的影响 | 证据 |
| :--- | :--- | :--- |
| **R1** 置换路径发散过滤 | 无 Tier 变化 | 28 个无效检验清零；4 个因子的 min-FDR 与 selected_context 均不变 |
| **R2** min-FDR 语义/溯源（existence-oriented） | 无数值变化 | 新增 `min_edge_fdr`/`n_contexts`/`n_contexts_after_dedup`/`selected_context`/`fw er_upper_bound`/`extremum_note`；Tier 未动 |
| **R3** 统计门不得单独提升 | 关掉"统计门单独提升"路径 | dnase 的 `tier_promotion_gate` 显示 `statistical(disabled)`；RRBS 此时仍由 effect 门（any_model）支撑 → Tier 1 |
| **R4** effect 门改模型等权均值 | **RRBS: Tier 1 → Tier 2** | effect 门值由 `max\|ΔR²\|=0.0529`（linear 单模型）变为 `\|mean ΔR²\|=0.00932 < 0.01` |
| **R5** concordance 分母=全部有效模型 | 本批数值不变（无精确零），规则不再可被中性虚高 | 分母 7、中性数 0；构造性用例：1 正 + 6 零 → 1/7（旧口径 1.0） |
| **R6** Model-Level Bootstrap Interval 命名 | 无数值变化 | `interval_type=model_level_bootstrap`、`n_models=7`；论文方法与 Limitations 已同步 |

## 4. 科学解释（写入论文的措辞）

> 在当前 DeepCRISPR 数据与 7 个模型配置下，四个表观环境通道的**模型等权平均增量预测价值均小于 0.01**，
> 且 7 个模型之间的效应方向并不一致。仅有 RRBS 在覆盖度、方向一致率与 Model-Level Bootstrap 区间上满足稳健性条件，
> 但其绝对预测增益未达到预定义的最小增益门（`min_absolute_delta_r2 = 0.01`），
> 因此落在 **Tier 2**；即使它在部分上下文中显示出统计证据（Minimal Edge-level FDR = 0.0093），
> 该证据是 **existence-oriented**、且跨 35 个上下文取最小（FWER 上界 0.245），**不足以**把因子提升为 Tier 1。
> 本批数据因此**不支持**任何环境因子成为"具有实质预测增益的高等级证据"。

## 5. 资产与可复现

| 项 | 位置/命令 |
| :--- | :--- |
| 修改前快照 | `/tmp/perm_before_r1.csv`（permutation）、R1–R6 各阶段记录见 `docs/audit/evidence_tier_R1_audit.md` … `R5_concordance.md` |
| 重算命令 | `python scripts/regenerate_permutation_and_evidence.py --write`（复用引擎同一函数） |
| 受影响资产 | `permutation_results.csv`（+`n_values_excluded`）、`bootstrap_main_effects.csv`（+`interval_type`）、`evidence_matrix.csv`（+18 列）、`06_evidence_integration.md`、Table 3、Fig. 7 |
