# R1–R6 执行报告（Evidence Tier 统计一致性重构）

> 执行顺序：**R1 → R2 → R3 → R4 → R5 → R6 → R7/R8 → R9 → R10 → R11**，每阶段均通过"代码测试 + 结果审计 + provenance 更新"后才进入下一阶段。
> 约束遵守情况：未新增统计方法、未改变 1344-run 实验设计、**未重新训练任何模型**、未为提升 Tier 1 数量调阈值、所有新阈值均参数化。

---

## 1. 逐阶段结果

| 阶段 | 改动（文件） | 验证 | Tier 影响 |
| :--- | :--- | :--- | :--- |
| **R1** | `analysis/stats/tasks.py`：`permutation_main_effects` 接入 `unstable_effect_threshold` 过滤（NaN/inf + `\|Δ\|≥10`），新增 `n_values_excluded` | 28 个无效检验 → **0**；剔除 130 条发散记录；min-FDR 与 selected_context 不变；**193 项测试通过** | 无 |
| **R2** | `analysis/evidence/integration.py`：`min(FDR)` 正式定义 = *Minimal Edge-level FDR across Tested Contexts*（existence-oriented）；新增 `min_edge_fdr`/`n_contexts`/`n_contexts_after_dedup`/`selected_context`/`selection_basis`/`statistical_evidence_role`/`fwer_upper_bound`/`extremum_note` | 4 项新测试；**Tier 不变** | 无 |
| **R3** | `analysis/config.py`（`statistical_gate_can_promote=False`）+ `integration.py`：三门外显式化（effect / statistical / robustness），新增 `robustness_gate_pass`、`tier_promotion_gate` | 2 项新测试（含显式打开开关的回归对照） | 关闭"统计门单独提升"路径（dnase 提升门显示 `statistical(disabled)`） |
| **R4** | `analysis/config.py`（`effect_gate_mode="model_mean"`）+ `integration.py`：effect 门 = 7 模型配置**等权平均** \|ΔR²\|；新增 `median_effect`/`n_models`/`model_direction_conflict`/`effect_gate_value` | 3 项新测试（单模型不能再决定 effect 门） | **RRBS: Tier 1 → Tier 2** |
| **R5** | `integration.py::direction_concordance`：分母 = **全部有效模型**（中性不缩小）；新增 `concordance_denominator`/`n_neutral_models` | 3 项新测试（1 正 + 6 零 → 1/7 而非 1.0） | 无数值变化（本批无精确零） |
| **R6** | `analysis/stats/tasks.py`：正式命名 **Model-Level Bootstrap Interval (n = 7 model configurations)** + `interval_type`；论文 `02_methods.tex`、`05_limitations.tex`、Table 3 caption 同步 | 1 项新测试 | 无 |
| **R7/R8** | `analysis/audit/regenerate_permutation_and_evidence.py --write`：用已有资产重算 permutation / bootstrap / evidence | before/after 见 `evidence_tier_before_after.md` | 环境 Tier 1 数量 **1 → 0** |
| **R9** | 论文 `02_methods.tex`（三门口径 + 命名）、`03_results.tex`（观察 1 改写）、`05_limitations.tex`（自助区间推断单位） | Table 3 与 CSV 逐值一致 | RRBS 表述改为 Tier 2 |
| **R10** | `analysis/reporting/paper/make_assets.py`：Table 3 解耦为 `mean_dR2 / median_dR2 / effect_gate / n_models / direction_conflict / min_edge_FDR / n_contexts / selected_context / fwer_upper_bound / concordance / mlevel_bootstrap / ci_excludes_zero / anova_F / anova_p / cell_line_context / tier` | 与 CSV 程序化比对全部一致 | — |
| **R11** | 10 项一致性验证（见 §3） | 全绿 | — |

---

## 2. 最终结果（R8 摘要）

| factor | mean ΔR²（M=7 等权） | effect 门 | 统计门（existence） | concordance（分母） | Model-Level Bootstrap | robustness | **Old → New Tier** |
| :--- | ---: | :--- | :--- | :--- | :--- | :--- | :--- |
| CTCF | −0.00095 | fail | pass（0.0093, n=34, FWER 0.238） | 0.857 (7) | [−0.0105, +0.0048] 跨 0 | fail | Inconclusive → Inconclusive |
| DNase | −0.00202 | fail | pass（0.0140, n=33, FWER 0.231） | 0.714 (7) | [−0.0052, +0.0004] 跨 0 | fail | Inconclusive → Inconclusive |
| H3K4me3 | −0.00594 | fail | pass（0.0093, n=35, FWER 0.245） | 0.857 (7) | [−0.0129, −0.0010] | pass | Inconclusive → Inconclusive（cell-line 冲突） |
| **RRBS** | −0.00932 | fail | pass（0.0093, n=35, FWER 0.245） | 0.857 (7) | [−0.0242, −0.0010] | pass | **Tier 1 → Tier 2** |

**环境因子 Tier 1 = 0；motif 行不变（100 Inconclusive / 496 Tier 3）。**

## 3. R11 十项最终验证

| # | 验证项 | 结果 |
| ---: | :--- | :--- |
| 1 | 没有第二套 Tier implementation | ✅ 只有 `integration.py::classify_evidence_tier` 返回 Tier（其余为消费者） |
| 2 | `rules.py` 不再被依赖 | ✅ 文件已删除；仅模块 docstring 保留历史说明 |
| 3 | permutation divergence filter 生效 | ✅ `\|observed_effect\|>10` 行数 28 → **0**；`n_values_excluded` 合计 130 |
| 4 | min FDR 不再被称 factor-level FDR | ✅ 论文/表格中仅以否定语境出现；正式名 = *Minimal Edge-level FDR across Tested Contexts* |
| 5 | statistical gate 无法单独升级 Tier 1 | ✅ `statistical_gate_can_promote=False`（默认），并有参数化回归测试 |
| 6 | effect 使用 model-equal-weight mean | ✅ `effect_gate_mode=model_mean`，输出 `effect_gate_value` |
| 7 | concordance denominator 不因 neutral 缩小 | ✅ 分母 = 7（`concordance_denominator`），构造性用例 1 正 + 6 零 → 1/7 |
| 8 | bootstrap 文档明确 n=7 models | ✅ 方法/Table 3 caption/Limitations + `interval_type=model_level_bootstrap` |
| 9 | Table 3 与代码输出一致 | ✅ 4 个因子逐值比对通过 |
| 10 | 论文 RRBS Tier 与 CSV 一致 | ✅ 论文写 Tier 2，CSV = `Tier 2: Moderate convergent evidence` |

**测试**：`analysis/tests/test_evidence_tier_rules` **29 项**；`unittest discover analysis/tests` **200 项全部通过**。

## 4. 未改变的内容（明确边界）

* 未新增任何统计检验方法（未引入 Fisher / Simes / HMP / Cauchy）；
* 未修改 sign-flip 置换方法、`n_permutations=1000`、`seed=2024`、BH-FDR 方法与 family 划分；
* 未修改 `min_absolute_delta_r2 = 0.01`、`direction_concordance = 0.80`、`min_coverage = 2`、`fdr_weak = 0.05`；
* 未重训模型、未重跑 1344 次实验；
* ANOVA 仍与 Tier 完全解耦（`TestAnovaIndependence` 保持通过）。

## 5. 产物清单

| 类别 | 文件 |
| :--- | :--- |
| 阶段记录 | `docs/audit/evidence_tier_R1_audit.md`、`R2_fdr_aggregation.md`、`R3_statistical_gate.md`、`R4_effect_aggregation.md`、`R5_concordance.md`、本文件 |
| 结果审计 | `docs/audit/evidence_tier_before_after.md` |
| 审计与定义 | `docs/audit/evidence_tier_final_statistical_audit.md`（含实施状态注记）、`docs/audit/evidence_tier_scientific_definition.md`、`docs/audit/evidence_tier_code_audit.md` |
| 溯源 | `docs/paper/evidence_tier_provenance.md`（§10 记录 R1–R6 与回归） |
| 代码 | `analysis/stats/tasks.py`、`analysis/evidence/integration.py`、`analysis/config.py` |
| 测试 | `analysis/tests/test_evidence_tier_rules.py`（29 项） |
| 工具 | `analysis/audit/regenerate_permutation_and_evidence.py`、`docs/audit/audit_factor_level_permutation.py` |
| 资产 | `tables/permutation_results.csv`、`tables/bootstrap_main_effects.csv`、`tables/evidence_matrix.csv`、`summary/06_evidence_integration.md`、`paper/tables/tab3_environment.tex`、`docs/paper/figures/fig7_evidence.*` |
| 论文 | `paper/sections/02_methods.tex`、`03_results.tex`、`05_limitations.tex`；`paper/compiled/main.pdf`（审阅版；正式排版需 TeX Live） |

## 6. 复现

```bash
python analysis/audit/regenerate_permutation_and_evidence.py --write   # 重算 permutation/bootstrap/evidence（不重训）
python analysis/reporting/paper/make_assets.py                                     # 论文表格与图
python -m unittest analyse.tests.test_evidence_tier_rules -v    # 29 项
python -m unittest discover -s analysis/tests -t . -p "test_*.py"  # 200 项
```
