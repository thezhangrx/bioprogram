# 统计工具接线报告 (Statistical Analysis Status)

> 目标不是"让所有状态变成 ✓", 而是**真实实现 → 真实接线 → 真实输出 → 不产生伪统计结果**。
> 本文件由代码/测试/真实批次产物核对生成; 每一项都给出可验证的 artifact 路径。

批次: `results/batches/batch_20260909_full` (1344 experiments, 16 environment combinations, 7 model variants)

---

## 1. 总表

| Tool | Implemented | Wired | Output | Report | Frontend | Test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Bootstrap CI (`bootstrap_ci`) | ✓ | ✓ | ✓ `tables/bootstrap_main_effects.csv` | ✓ 03 | ✓ status+artifact | ✓ |
| Paired ΔR² bootstrap (`bootstrap_difference_ci` / per-sample paired) | ✓ | ✓ | ✓ `tables/bootstrap_results.csv` (7770 行 / 2541 ΔR² CI) | ✓ 03 + edges | ✓ | ✓ |
| Permutation test (`permutation_test_for_effect`) | ✓ (**本轮修正为 sign-flip**) | ✓ | ✓ `tables/permutation_results.csv` (3444 行) | ✓ 03 | ✓ | ✓ |
| BH-FDR (`bh_fdr`) | ✓ | ✓ | ✓ `FDR`/`fdr_family` 列 (189 families) | ✓ 03 | ✓ | ✓ |
| ANOVA (`factorial_anova`) | ✓ (**本轮真实实现**, 原为 placeholder) | ✓ | ✓ `tables/anova_results.csv` (94 行) | ✓ 03 | ✓ | ✓ |
| Effect size (`delta_pair`, `compute_paired_increment`) | ✓ | ✓ (经 incremental_effect 使用) | ✓ 同上 | ✓ 03 | ✓ | ✓ |
| Cell-line consistency | ✓ (**本轮重设计**, Context-dependent 原不可达) | ✓ | ✓ `tables/cellline_effects.csv` (含 heterogeneity/CI 诊断列) | ✓ 05 | ✓ | ✓ |
| Evidence Tier 使用 CI | ✓ (**本轮接通**, 原 `ci_crosses_zero=None`) | ✓ | ✓ `tables/evidence_matrix.csv` (ci_*/permutation_*) | ✓ 06 | ✓ | ✓ |
| Linear p/FDR (训练侧产生) | ✓ (训练侧) | ✓ 只读取 | ✓ `tables/importance_vs_delta_r2.csv` | ✓ 07 | ✓ | ✓ |
| Motif enrichment FDR (`motif_enrichment` family) | ✓ | ✓ | ✓ `tables/motif_enrichment.csv` (Fisher exact + BH-FDR) | ✓ 04 | ✓ | ✓ |
| ANOVA 交互 per-group | 部分 (n=1/cell 时不可估) | ✓ 记录 unavailable+reason | ✓ `anova_results.csv` | ✓ | ✓ | ✓ |

### 未接线 / 不可用的明确原因

| 项 | 状态 | 原因 |
| :--- | :--- | :--- |
| Permutation on SHAP / IG / ISM / Attention / Gain | **禁止** | 这些是 attribution / robustness, 没有明确 null hypothesis; 不能进 FDR。|
| `environment_shapley` | not implemented | 注册表存在但无 runner; 仍标 unavailable。|
| Motif enrichment 之外的其他 motif 统计 | 未实现 | motif 目前只有 Fisher exact + BH-FDR; 不做 motif-level 因果/剂量效应。|
| ANOVA per-group 交互项 | unavailable | 每个 (split, cell, model) 组合每个 env cell 只有 1 个观测 -> 设计饱和; 全局 blocked ANOVA 提供交互检验。|
| 单实验 bootstrap CI (n<3) | unavailable | 样本不足时 `available=False`, 绝不填 0。|

---

## 2. Paired ΔR² bootstrap 的口径 (科学定义)

* 单位: **per-sample**, 同一 eligible cohort / 同一 test 样本 (`<batch>/<run_name>/<model>_predictions.csv`);
* 配对: 同一 `(split_type, cell_line, model, random_seed)` 下 `S` 与 `S ∪ {e}` 的预测逐样本对齐,
  样本数不等 -> `status=unavailable, reason=cohort_mismatch` (不悄悄降级为非配对);
* 重采样: 每次迭代对**同一批样本索引**重采样两侧模型 (multinomial 计数矩阵 matvec),
  `B=2000`, `seed=2024`, `alpha=0.05` (全部来自 `AnalysisConfig`);
* 输出: `estimate / ci_low / ci_high / excludes_zero / n_bootstrap / seed / alpha / n_samples / status`;
* 语义: **不确定性/稳定性证据**, 不是显著性, 也不是因果。

本批结果: 2541/2651 条 lattice edge 有 ΔR² CI, 其中 **257 条 CI 不跨 0**;
110 条不可用 (linear 发散被排除 / 缺预测 artifact)。

---

## 3. Permutation test 的口径与修正

* H0 与 alternative 逐行写入 `null_hypothesis` / `alternative` 列;
* 三类 effect: `environment_edge` (per-sample SE 差, one-sided greater)、
  `environment_main_effect` (背景条件增量, two-sided)、
  `environment_interaction` (per-sample 交互 contrast, two-sided);
* **本轮修正的真实 bug**: 原实现对"中心化后的值做重排", 而置换不改变均值 -> p 恒为 `1/(B+1)`
  的退化结果; 现改为 **sign-flip 随机化检验** (H0 下差值关于 0 对称, 符号可交换),
  300 次模拟的 type-I error ≈ 0.057 @ α=0.05 (校准正常);
* FDR: 按 `fdr_family` 分组校正, 每个 family = 一个科学问题
  (`environment_edge|split|cell|model` 等), 不同问题不混用;
  family 成员数 < `config.fdr.min_family_size` 时记 `not_applicable`, 不伪造 FDR。

---

## 4. ANOVA 的真实设计 (不把每个 R² 当独立重复)

数据层级检查结论 (来自 `summary/metrics_tables/all_experiments.csv`):
每个 (split, cell, model, seed) 在 16 个 environment combination 上各 1 次观测;
`single`/`all` 划分 1 个 seed, `mixed` 4 个 seed; 7 个 model variant × 4 cell line × 3 split。

因此实现两种互补设计:

1. **blocked factorial** (`model_scope=blocked_factorial`):
   `R² ~ A*B*C*D + C(model) + C(cell_line) + C(split_type)`,
   Type-II 边际 extra-sum-of-squares F 检验 (主效应 4 项 + 成对交互 6 项);
   本批 `n_obs=966`, `df_den=1265`。block 因子吸收模型/细胞系均值差异,
   避免把跨模型 R² 差异误当环境效应。
2. **per-group additive main** (`model_scope=per_group_additive_main`):
   每个 (split, cell, model) 内 16 个组合、`df_den=11`, 只估加性主效应
   (n=1/cell 无法估交互, 明确不估, 不伪造)。

输出字段: `factor / effect / F_statistic / p_value / df_num / df_den / effect_size(partial η²) /
ci_low / ci_high / n_obs / family_key / status / reason`;
effect 的 CI 由行级 bootstrap (`config.anova.ci_iterations`) 给出, 迭代数=0 时为 None。
数据不足 -> `status=unavailable, reason=insufficient_data: ...`。

**本批 ANOVA 结果 (blocked factorial)**: 4 个环境因子主效应 F=0.60/2.31/1.95/2.18,
p=0.66/0.056/0.100/0.069, partial η² ≈ 0.0005–0.0018; 6 个交互项 p=0.26–0.85。
即在控制 model/cell-line/split 后, 环境因子的 R² 主效应在本批数据中**未达统计显著**。

---

## 5. AnalysisPlan 开关与状态语义

```json
{"environment": {"anova": true}, "statistics": {"bootstrap": true, "permutation_test": true,
                                                "fdr_correction": true, "anova": true}}
```

| 情形 | status | reason |
| :--- | :--- | :--- |
| ANOVA 关闭 | `skipped` | `user_disabled` |
| ANOVA 开启但数据不足 | `skipped` / `unavailable` | `insufficient_data: ...` |
| ANOVA 执行成功 | `completed` | `tables/anova_results.csv (N terms)` |
| bootstrap/permutation 无配对预测 | `skipped` | `insufficient_data: no paired per-sample prediction artifact` |
| FDR 但无可校正 family | `unavailable` | `no corrigible p-value family available in this batch` |

`analysis_status.json` 每个 task 现包含 `artifact` 字段 (前端 Artifact Viewer 直接读取):

```json
{"task_id": "environment_anova", "selected": true, "available": true,
 "status": "completed", "artifact": "tables/anova_results.csv", "reason": "..."}
```

---

## 6. Evidence Integration 中的 CI

`environment_evidence_matrix(..., bootstrap_ci=..., permutation=...)`:

* factor 级 CI = 各模型 main effect 的跨模型 bootstrap (`estimate_basis` 列显式标注单位);
* 仅当 `status=ok` 且 `n_bootstrap >= config.evidence.min_bootstrap_iterations (200)` 时 CI 参与判定;
* `CI 跨 0 -> Inconclusive`; `permutation FDR < config.statistical.fdr_weak -> 计入 statistical support`;
* 输出新列: `ci_low / ci_high / ci_excludes_zero / n_bootstrap / bootstrap_status /
  permutation_p / permutation_fdr / permutation_status`。

**边界**: SNR / Attention / SHAP / IG / ISM 永不进入 p-value 或 FDR; 只有真实零假设检验结果才进。

**Evidence Tier 权威规则 (2026-09-13 审计后)**: 分级函数唯一 = `analysis/evidence/integration.py::classify_evidence_tier`
(环境行与 motif 行共用)。参与 Tier 的阈值只有: 覆盖度 `consensus.min_coverage=2`、方向一致率
`consensus.direction_concordance=0.80`、最小绝对增益门 `evidence.min_absolute_delta_r2=0.01`(effect 门,
**不是显著性阈值**)、置换统计门 `statistical.fdr_weak=0.05`、CI 门(`ci_crosses_zero_forces_inconclusive`,
`min_bootstrap_iterations=200`)与 `Context-conflicting` 一票否决; **统计证据不能单独把因子提升为 Tier 1**：Tier 1 要求 effect 门（模型等权平均 |ΔR²| ≥ 0.01）通过；统计门（Minimal Edge-level FDR across Tested Contexts，existence-oriented）用于支持/排除与 Tier 2 注释。bootstrap 区间的正式名称为 Model-Level Bootstrap Interval (n = 7 model configurations)。R1–R6 实施后本批环境因子 Tier 1 数量为 0（RRBS = Tier 2），见 docs/audit/evidence_tier_before_after.md。
SNR 阶梯(2.5/1.8/1.2)、`min_effect_size=0.005`、FDR 阶梯(0.001/0.01) **只用于 Importance–ΔR² 资产, 不参与 Tier**;
原 `evidence/rules.py`(未接入生产)已删除。ANOVA 不参与 Tier(回答全局因子/交互问题)。
详见 `docs/audit/evidence_tier_code_audit.md`、`docs/audit/evidence_tier_scientific_definition.md`、
`docs/paper/evidence_tier_provenance.md`; 测试 `analysis/tests/test_evidence_tier_rules.py`(17 项)。

---

## 7. Cell-line consistency 重设计

判定输入: 方向一致性 + 幅度异质性 (`max|effect| / median|effect|`) + CI 重叠
(反向 cell line 的 CI 与主体 CI 全部重叠时不升级为 conflicting)。

四种标签均可达 (测试 `TestCelllineLabelsReachable` 逐一验证):

| 标签 | 触发条件 (本批阈值) |
| :--- | :--- |
| Context-consistent | 方向一致且 `max/median <= 2.0` |
| Context-dependent | 方向一致但幅度异质; 或多数同向 ≥0.75 且存在未达冲突线的反向 |
| Context-conflicting | 反向占比 ≥ 0.25 (且 CI 未全部重叠) |
| Uncertain | 有效 cell line < 2 或无多数方向 |

阈值全部在 `config.CelllineConsistencyConfig`, 不散落代码。

---

## 8. 复现方式

```bash
# 统计接线 (默认 ANOVA 关闭)
python -m analysis.pipeline --batch-dir results/batches/batch_20260909_full

# 打开 ANOVA
python -m analysis.pipeline --batch-dir results/batches/batch_20260909_full --analysis-plan plan_anova_on.json

# 测试
python -m unittest analyse.tests.test_stats_wiring -v
```

测试分层: unit (bootstrap/permutation/BH/ANOVA) → task runner (合成 batch 含真实 predictions)
→ 证据整合/状态契约 → real-batch smoke (缺 artifact 自动 skip, 不伪造)。


---

## 9. Sequence Motif Discovery 接线状态 (Block 2)

| 组件 | 状态 | 产物 |
| :--- | :--- | :--- |
| IUPAC / human pattern / regex 三种表示 (分开保存) | ✓ 实现 + 测试 | `tables/motif_candidates.csv` 的 `iupac` / `human_pattern` / `regex` 列 |
| Seqlet 提取 (attribution specificity + 局部连续窗口) | ✓ | `tables/motif_instances.csv` (seqlet 级) |
| 正负方向分离 | ✓ 有符号时; 当前批次 attribution 无符号 -> 方向来自 measured efficacy 对比 (`direction_source`) | `motif_candidates.effect_direction` |
| 聚类 + consensus + support 门槛 | ✓ | `motif_candidates` (length 4-11, support/sample/cell-line) |
| Enrichment (foreground=高效序列, background=all eligible) | ✓ (plan 可选) | `motif_enrichment.csv` (p_value/FDR/family) |
| Stability (kernel variant / cell-line) 与 cross-model | ✓ (Transformer IG 缺 -> cross_model unavailable; seed 支持 unavailable 且写明原因) | `motif_consistency.csv` |
| Evidence Matrix 联动 | ✓ | `motif_evidence.csv` + `evidence_matrix.csv` 的 `feature_type=motif` 行 |
| 报告 | ✓ | `summary/04_sequence_and_motifs.md` (含 Methodology) |
| 图表 | ✓ | `figures/04_motif/` (logos / position / enrichment / consistency) |

**不可用项及原因 (不伪造)**: Transformer IG 不存在 (只有 attention, 不作 motif extractor);
`attribution_summary` 不含 `random_seed` -> seed-level motif support 不可计算, 已用
sample / model-variant / cell-line support 代替并在报告中写明。

---

## 10. Interactive Scientific Discovery Report (Block 3)

| 能力 | 实现 |
| :--- | :--- |
| 报告数据层 | `app/frontend/src/reports/ReportDataAdapter.ts` (唯一数据入口: CSV/MD/JSON -> ReportData) |
| 章节 | Overview / Dataset & Quality / Prediction / Environment / Sequence & Motifs / Cell-line / Evidence / Hypotheses / Provenance |
| Key Findings drill-down | Finding -> section -> artifact (View analysis / View source) |
| Evidence Card | 直接展示后端字段 (ΔR²/CI/coverage/concordance/cell-line/permutation FDR) |
| 交互 | 表格 search/filter/sort/page、tier 筛选、fullscreen、Print/PDF、Export HTML |
| 复用 viewer | 复用既有 `ArtifactViewer`(CSV/Markdown) 与 MarkdownViewer |
| 前端不复制统计规则 | 只显示后端 `evidence_tier`/`evidence_strength`/`ci_excludes_zero`/FDR, 无任何阈值判断 |
| 测试 | `app/frontend/src/reports/ScientificReport.test.ts` (9 例) + 全量 vitest 16 例 |

---

## 11. Importance–ΔR² 二维证据图 (Block 4)

| 要求 | 实现 |
| :--- | :--- |
| 规定 CSV 字段 | `tables/importance_vs_delta_r2.csv` 含 held_out_cell_line / environment / baseline_environment / expanded_environment / raw_importance / importance_method / effect_direction / evidence_tier / coverage / snr / fdr / eligible / filter_reason |
| machine-readable summary | `summary/importance_delta_r2_summary.json` (6 类候选) |
| 报告 | `summary/importance_vs_delta_r2.md` (+ 兼容别名 `summary/importance_vs_delta_r2.md`) |
| 图表目录 | `figures/07_evidence/importance_delta_r2/{all_models,linear,xgboost,mlp,cnn}/` + 环境专用别名图 |
| 测试 | `analysis/tests/test_importance_delta_r2.py` (16 项) |
| 复用而非重算 | evidence_tier/coverage/permutation FDR 直接读 `evidence_matrix.csv`; SNR 只作 robustness |
