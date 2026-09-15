# Evidence Tier 溯源（provenance）

> 目的：固化 `configuration → integration → evidence table → visualization → paper asset` 的完整链条，
> 防止再次出现"配置存在但流水线不用"或"规则断裂"的情况。
> 相关文档：`docs/audit/evidence_tier_code_audit.md`（审计）、`docs/audit/evidence_tier_scientific_definition.md`（定义）

---

## 1. 权威实现（Authoritative implementation）

| 项 | 值 |
| :--- | :--- |
| **分级函数** | `analysis/evidence/integration.py::classify_evidence_tier`（三门外显式：effect / statistical / robustness） |
| **环境行生成** | `analysis/evidence/integration.py::environment_evidence_matrix` |
| **motif 行生成** | `analysis/sequence/motif/pipeline.py::motif_evidence_rows`（复用同一分级函数） |
| **已废弃** | `analysis/evidence/rules.py`（SNR/FDR 阶梯，未进入生产流水线，已于 2026-09-13 删除） |
| **字符串→枚举** | `analysis/evidence/integration.py::tier_from_value`（仅供报告展示/假设生成） |

---

## 2. 输入表（Input tables）

| 输入 | 生成代码 | 作用 |
| :--- | :--- | :--- |
| `tables/environment_main_effects.csv` | `analysis/environment/incremental_effect.py` | edge 级条件增量 → 因子主效应（先跨背景、再跨 seed 等权平均） |
| `tables/cellline_effects.csv` | `analysis/pipeline.py` → `analysis/cellline/consistency.py` | cell-line 上下文标签（众数进入矩阵） |
| `tables/bootstrap_main_effects.csv` | `analysis/stats/tasks.py::bootstrap_main_effects` | 因子级 **跨模型** bootstrap CI（`estimate_basis=cross_model_mean_of_main_effect`） |
| `tables/permutation_results.csv` | `analysis/stats/tasks.py::permutation_*` + `apply_fdr` | sign-flip 置换 p 值 + **族内** BH-FDR |
| （motif）`tables/motif_enrichment.csv` / `motif_candidates.csv` | `analysis/sequence/motif/*` | motif 行的 FDR 与 effect |
| **不读取** | `tables/anova_results.csv` | ANOVA 只供 Fig.3D / Table 3 展示，不参与 Tier |

---

## 3. 配置参数（Configuration）

| 参数 | 值 | 归属 | 是否参与 Tier |
| :--- | ---: | :--- | :--- |
| `consensus.min_coverage` | 2 | `ConsensusRuleConfig` | ✅ 覆盖度门槛（Tier1/Tier2） |
| `consensus.direction_concordance` | 0.80 | `ConsensusRuleConfig` | ✅ Tier1 的一致性门槛 |
| `consensus.unstable_effect_threshold` | 10.0 | `ConsensusRuleConfig` | ✅ 进矩阵前剔除不稳定上下文 |
| `evidence.min_absolute_delta_r2` | 0.01 | `EvidenceRuleConfig` | ✅ effect 门（**模型等权平均** \|ΔR²\|，`effect_gate_mode=model_mean`） |
| `evidence.ci_crosses_zero_forces_inconclusive` | True | `EvidenceRuleConfig` | ✅ CI 门开关（代码实际读取） |
| `evidence.min_bootstrap_iterations` | 200 | `EvidenceRuleConfig` | ✅ CI 可用性门槛（Model-Level Bootstrap Interval） |
| `evidence.statistical_gate_can_promote` | False | `EvidenceRuleConfig` | ✅ R3：统计门单独提升开关（仅回归对照） |
| `evidence.effect_gate_mode` | model_mean | `EvidenceRuleConfig` | ✅ R4：effect 门口径（`any_model` 仅敏感性分析） |
| `statistical.fdr_weak` | 0.05 | `StatisticalRuleConfig` | ✅ 统计门阈值（existence-oriented min edge-level FDR；**不能单独提升 Tier 1**） |
| `cellline.*`（`consistent_ratio`/`conflicting_ratio`/`heterogeneity_ratio`/`ci_overlap_relaxes`） | 0.75/0.25/2.0/True | `CelllineConsistencyConfig` | ✅ 产生 cell-line 标签，`Context-conflicting` 一票否决 |
| `statistical.fdr_strong` / `fdr_moderate` | 0.001 / 0.01 | `StatisticalRuleConfig` | ❌ 仅供 Importance–ΔR² 资产 |
| `attribution.snr_threshold/snr_moderate/snr_weak` | 2.5/1.8/1.2 | `AttributionRuleConfig` | ❌ 仅供 Importance–ΔR² 资产 |
| `attribution.min_effect_size` | 0.005 | `AttributionRuleConfig` | ❌ 仅供 Importance–ΔR² 资产 |
| ~~`statistical.fdr_nominal`~~ | ~~0.10~~ | — | **已删除（0 引用）** |
| ~~`consensus.environment_strong_effect`~~ | ~~0.01~~ | — | **已重命名为 `evidence.min_absolute_delta_r2`** |
| ~~`consensus.bootstrap_ci_exclude_zero_alpha` / `cellline_consistent_ratio` / `evidence.ci_alpha`~~ | — | — | **已删除（0 引用）** |

> 禁伪参数：配置中保留的每一个阈值都有生产消费点；测试
> `analysis/tests/test_evidence_tier_rules.py::TestTierClassifyFunction.test_ci_gate_is_parameterized`
> 与 `TestAbsoluteEffectGate.test_threshold_is_parameterized` /
> `TestStatisticalGate.test_permutation_gate_threshold_is_parameterized`
> 验证"改阈值 → 输出确实变化"。

---

## 4. 阈值（Thresholds）与聚合（Aggregation）

```
environment_main_effects.csv  (split × cell × model × factor × seed)
   │  ① 稳定性过滤: |main_r2_delta| < 10                       (unstable_effect_threshold)
   │  ② 聚合: groupby(model, factor).mean()  -> 7 个模型等权均值
   ├─ coverage        = 有效模型数
   ├─ concordance     = 多数方向占比
   ├─ overall_effect  = 7 个模型均值的均值
   ├─ effect_gate_pass     = any(|per-model mean| >= 0.01)     (min_absolute_delta_r2)
   ├─ statistical_gate_pass= min(FDR of this factor) < 0.05    (statistical.fdr_weak)
   └─ ci_crosses_zero = NOT (ci_low <= 0 <= ci_high)           (bootstrap_main_effects, n>=200)
                    ↓
        classify_evidence_tier()  →  evidence_tier
```

* 全部为**等权**聚合（模型等权、背景/seed 等权）；**无按样本数 n 加权**。
* 置换 FDR 的取用规则是"**该因子所有行的最小 FDR**"，已显式写入输出列
  `permutation_selection = "min FDR over rows of this factor"`（选择性强，故留痕）。

---

## 5. 统计检验与多重比较

| 项 | 口径 |
| :--- | :--- |
| 因子级 CI | 跨**模型** bootstrap（`B=2000`, `seed=2024`, `alpha=0.05`），单位 = 模型 |
| 边级 CI | 逐样本配对 bootstrap（`B=2000`），单位 = test cohort |
| 置换 | sign-flip 随机化检验（`B=1000`, `seed=2024`） |
| 多重比较 | BH-FDR，**仅在族内**（`environment_edge|split|cell|model`、`environment_main|…`、`environment_interaction|…`、`environment_anova|global`、`environment_anova_group|…`、`motif_enrichment`） |
| 不做的校正 | ANOVA 表无 FDR 列；bootstrap CI 不做多重校正 |

---

## 6. 最终输出资产（Final output assets）

| 资产 | 生成路径 | 关键列 |
| :--- | :--- | :--- |
| `summary/tables/evidence_matrix.csv`（600 行） | `analysis/pipeline.py`（task `evidence_integration`） | `evidence_tier`, `coverage`, `direction_concordance`, `overall_effect`, `ci_low/high`, `ci_excludes_zero`, `n_bootstrap`, `bootstrap_status`, `permutation_p`, `permutation_fdr`, `effect_gate_pass`, `statistical_gate_pass`, `strong_evidence_basis`, `min_absolute_delta_r2`, `permutation_selection`, `cell_line_consistency` |
| `summary/reports/06_evidence_integration.md` | `analysis/reports/markdown_report.py::build_evidence_md` | 人读版本 |
| `summary/reports/07_biological_hypotheses.md` | `build_hypotheses_md`（`EvidenceRecord`，不含统计字段） | Tier 1/2/3 → 候选假设 |
| `summary/figures/06_evidence/*` | `analysis/visualization/evidence_plots.py` | tier 分布/CI 图 |
| `summary/feature_importance/...`（Importance–ΔR²） | `analysis/importance_metrics.py` | **另一条资产线**，使用 SNR/FDR 阶梯，与 Tier 无关 |

---

## 7. 论文产物（Paper table / figure）

| 论文元素 | 来源列 | 说明 |
| :--- | :--- | :--- |
| Table 3 `tier` 列 | `evidence_matrix.evidence_tier`（`feature_type=environment`） | 与代码逐字一致（枚举 value） |
| Table 3 `anova_F` / `anova_p` | `anova_results.csv`（`model_scope=blocked_factorial`） | **独立展示**，不参与 Tier |
| Table 3 `permutation_fdr` / `ci_*` | `evidence_matrix` 对应列 | 统计证据展示 |
| Figure 7 | `evidence_matrix` + `docs/paper_analysis/factor_level_ci.csv` | 标注 `Tier k \| FDR=…` |
| 补充表 S1（`tabS1_methods.tex`） | `paper/make_assets.py`（读 `AnalysisConfig`） | 已拆分"参与 Tier"与"仅 Importance–ΔR²"两组阈值 |
| 方法 §2.10（`paper/sections/02_methods.tex`） | 本文档 §2–§5 | 已同步为唯一权威规则 |

---

## 8. 变更记录与回归

| 日期 | 变更 | 回归验证 |
| :--- | :--- | :--- |
| 2026-09-13 | 删除 `evidence/rules.py`（未接入生产）；删除 `EvidenceStrength` 与 `evidence_record_row` 死代码 | 全量测试 188 项通过 |
| 2026-09-13 | `environment_strong_effect` → `evidence.min_absolute_delta_r2`；删除 `fdr_nominal`、`bootstrap_ci_exclude_zero_alpha`、`cellline_consistent_ratio`、`ci_alpha` 四个 0 引用参数；`ci_crosses_zero_forces_inconclusive` 真正接入 | `scripts/regenerate_evidence_tier_assets.py`：环境 4 行 `evidence_tier` 与 coverage/concordance/overall_effect/ci_excludes_zero/permutation_fdr **逐行完全一致**（max|Δ| = 0） |
| 2026-09-13 | 新增 provenance 列（`effect_gate_pass`/`statistical_gate_pass`/`strong_evidence_basis`/`min_absolute_delta_r2`/`permutation_selection`） | 在**旧 CI 输入**下 tier 分布不变（环境 2 Inconclusive / 1 Tier1 / 1 Tier2；motif 100 Inconclusive / 496 Tier3） |
| 2026-09-13 | **完整重跑 evidence 环节**（`analyse.pipeline --analysis-plan …`）：发现 `bootstrap_main_effects.csv` 为修正前口径的陈旧资产（其 CI 与论文 Fig.7 的 `factor_level_ci.csv` 矛盾），刷新后 DNase 的跨模型 CI 跨 0 | **DNase 由 Tier 2 → Inconclusive**；环境变为 3 Inconclusive / 1 Tier1，motif 不变。论文 `03_results.tex` 观察 1 与 `05_limitations.tex` 已同步改写 |
| 2026-09-13 | 新增 17 项最小测试 `analysis/tests/test_evidence_tier_rules.py` | `python -m unittest analyse.tests.test_evidence_tier_rules -v` → 17/17 通过 |

**未重跑 1 344 次实验**：本次只做参数化/改名/加溯源列，生产规则数值未变，故按"复用已有资产"原则重新生成
evidence tables（`scripts/regenerate_evidence_tier_assets.py --write`）。

---

## 9. 复现命令

```bash
# Tier 资产（复用已有中间产物，不重跑训练）
python scripts/regenerate_evidence_tier_assets.py            # dry-run：逐行比对 tier
python scripts/regenerate_evidence_tier_assets.py --write    # 写回 evidence_matrix.csv

# 完整分析流水线（含 evidence integration；沿用原 plan 以保持 ANOVA 开关一致）
python -m analysis.pipeline --batch-dir results/batches/batch_20260909_full \
       --analysis-plan results/batches/batch_20260909_full/summary/analysis_plan.json

# 测试
python -m unittest analyse.tests.test_evidence_tier_rules -v
python -m unittest discover -s analysis/tests -t . -p "test_*.py"

# 阈值经验审计
python docs/audit/audit_min_absolute_delta_r2.py

# 论文表格（含补充表 S1 阈值分组）
python paper/make_assets.py
```


---

## 10. R1–R6 重构（2026-09-13）后的口径与回归

| 阶段 | 改动 | 验证 |
| :--- | :--- | :--- |
| R1 | `permutation_main_effects` 接入 `unstable_effect_threshold` 过滤（与矩阵/CI/边级/交互一致），新增 `n_values_excluded` | 28 个无效检验 → 0；min-FDR 与 Tier 不变（`docs/audit/evidence_tier_R1_audit.md`） |
| R2 | `min(FDR)` 正式定义 = **Minimal Edge-level FDR across Tested Contexts**（existence-oriented）；新增 `min_edge_fdr`/`n_contexts`/`n_contexts_after_dedup`/`selected_context`/`selection_basis`/`statistical_evidence_role`/`fwer_upper_bound`/`extremum_note` | Tier 不变（`evidence_tier_R2_fdr_aggregation.md`） |
| R3 | 三门外显式化；统计门**不得单独**提升 Tier 1（`statistical_gate_can_promote=False`） | dnase 提升门显示 `statistical(disabled)`（`evidence_tier_R3_statistical_gate.md`） |
| R4 | effect 门 = **模型等权平均** \|ΔR²\|（`effect_gate_mode=model_mean`），保留 median / n_models / model_direction_conflict | **RRBS: Tier 1 → Tier 2**（`evidence_tier_R4_effect_aggregation.md`） |
| R5 | concordance 分母 = **全部有效模型**（中性不缩小分母），新增 `concordance_denominator`/`n_neutral_models` | 本批数值不变（`evidence_tier_R5_concordance.md`） |
| R6 | bootstrap 正式命名 **Model-Level Bootstrap Interval (n = 7 model configurations)**，新增 `interval_type`；论文方法/Table 3 caption/Limitations 同步 | 无数值变化 |
| R7/R8 | 用已有资产重算 permutation/bootstrap/evidence；产出 before/after | `docs/audit/evidence_tier_before_after.md`：环境 Tier 1 数 1 → 0 |

**最终 asset 关键列**（`evidence_matrix.csv`，environment 行）：
`overall_effect`、`median_effect`、`n_models`、`model_direction_conflict`、`model_effects`、
`effect_gate_pass`、`effect_gate_mode`、`effect_gate_value`、
`statistical_gate_pass`、`min_edge_fdr`、`n_contexts`、`n_contexts_after_dedup`、`selected_context`、`selection_basis`、`statistical_evidence_role`、`fwer_upper_bound`、`extremum_note`、
`direction_concordance`、`concordance_denominator`、`n_neutral_models`、
`ci_low`/`ci_high`/`ci_excludes_zero`/`n_bootstrap`/`bootstrap_status`、
`robustness_gate_pass`、`tier_promotion_gate`、`evidence_tier`。

**重算命令**（不重训模型）：
```bash
python scripts/regenerate_permutation_and_evidence.py --write
python paper/make_assets.py
```
