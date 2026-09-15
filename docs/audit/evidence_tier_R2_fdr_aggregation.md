# R2 执行记录：重新定义 minimum FDR 的含义（factor 级聚合语义）

> 阶段：**R2 / R1–R6**
> 原则：只改语义与 provenance，不改 Tier 规则、不改统计方法。

---

## 1. 变更前 vs 变更后（命名与语义）

| | 变更前 | 变更后 |
| :--- | :--- | :--- |
| 名称 | `permutation_fdr`（被读作 factor-level FDR） | **`min_edge_fdr`** = *Minimal Edge-level FDR across Tested Contexts* |
| 语义 | 隐含"该 factor 全局显著" | **existence-oriented**：回答"该 factor 是否**至少在一个 tested context** 中出现统计证据" |
| 多重比较 | 只在同一 (split,cell,model) 内的 4 个 factor 间做 BH；跨上下文取最小**无任何控制** | 明确记录 extremum selection 事实与 FWER 上界，不再声称 factor 级显著性 |
| 选择过程 | 无记录 | `selected_context` / `selection_basis` / `n_contexts*` / `fwer_upper_bound` / `extremum_note` 全部落盘 |
| 是否 factor-level FDR | ❌ 非 | ❌ 非（明确声明） |

`permutation_fdr` 列保留为兼容别名（值 = `min_edge_fdr`），避免破坏 Table 3 / Fig. 7 的既有读取路径。

## 2. 代码改动（`analysis/evidence/integration.py::environment_evidence_matrix`）

1. 显式限定 `test_type == "environment_main_effect"`（此前靠"交互行的 factor 名含 `*`"隐式排除）。
2. 新增去重：同一 `(cell_line, model, observed_effect, p_value)` 在不同 split 下重复出现时只计一次
   （本批 `all ≡ single`，去重后 63 → 35）。
3. 新增 provenance 字段：

| 字段 | 含义 | 本批取值（ctcf / dnase / h3k4me3 / rrbs） |
| :--- | :--- | :--- |
| `min_edge_fdr` | 跨 tested contexts 的最小 edge 级 FDR | 0.009324 / 0.013986 / 0.009324 / 0.009324 |
| `n_contexts` | 参与选择的上下文数（R1 过滤后） | 61 / 60 / 63 / 63 |
| `n_contexts_after_dedup` | 去掉重复上下文后的有效数 | 34 / 33 / 35 / 35 |
| `selected_context` | 最小 FDR 来自哪个上下文 | all/hek293t/linear（ctcf、h3k4me3、rrbs）；all/hl60/transformer（dnase） |
| `selection_basis` | 选择依据（固定串） | `minimum_edge_level_FDR_across_tested_contexts` |
| `statistical_evidence_role` | 证据角色 | `existence_oriented` |
| `fwer_upper_bound` | Bonferroni 上界 = `min(1, min_p × n_contexts_after_dedup)` | **0.238 / 0.231 / 0.245 / 0.245** |
| `extremum_note` | 明确不是 factor-level FDR | `min over tested contexts = post-selection extremum; NOT a factor-level FDR (no family-wise control)` |

> `fwer_upper_bound` 是**保守上界**（正相关下 Bonferroni 更保守），不是新统计检验，也不需要新方法；
> 它只用于说明"即使按最保守的多重比较口径，跨上下文取最小也不显著（全部 > 0.05）"。

## 3. 未改变的内容

* Tier 判定规则与所有阈值（R3/R4 才会改）；
* permutation 方法、`n_permutations=1000`、`seed=2024`、two-sided、BH-FDR 方法与 family 划分；
* 本批 Tier 结果（R2 后仍为：ctcf Inconclusive、dnase Inconclusive、h3k4me3 Inconclusive、**rrbs Tier 1**）——
  R3/R4 将按"effect 门 + 稳健性"重新裁定。

## 4. 明确未做的事（按 R2 禁止事项）

* ❌ 没有把 min-FDR 改名后继续称其为 factor-level significance；
* ❌ 没有由 min-FDR 推导 biological importance；
* ❌ 没有用"RRBS 当前是 Tier 1"反向决定聚合方法；
* ❌ 没有把 Fisher / Simes / HMP / Cauchy 直接当最终方案（仅在最终审计报告 §4 中作为候选方案比较，
  结论是"需组合**原始 p** 且先解决依赖与重复上下文问题；正式方案推荐 factor 级置换检验"）。

## 5. 测试与产物

| 项 | 结果 |
| :--- | :--- |
| 新增测试 | `TestPermutationEvidenceProvenance`（4 项：语义标签、上下文计数与 FWER 上界、重复上下文去重、R2 不改变 Tier） |
| `analysis/tests/test_evidence_tier_rules` | **21 项通过** |
| 其余测试 | `unittest discover analysis/tests` 全绿（见 R11 汇总） |
| 更新资产 | `tables/permutation_results.csv`（含 `n_values_excluded`）、`tables/evidence_matrix.csv`（新增 8 列） |

## 6. 进入 R3 的判定

R2 验证通过：**语义已改正、provenance 完整、Tier 未意外变化、测试全绿** → 允许进入 **R3（统计门不得单独提升到 Tier 1）**。
