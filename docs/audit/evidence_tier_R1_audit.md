# R1 执行记录：修复 permutation 路径的发散过滤（numerical divergence filtering）

> 阶段：**R1 / R1–R6 分阶段重构的第 1 步**
> 原则：只修 bug，不改 permutation 方法/迭代数/seed/BH 方法，不改 Tier 规则。

---

## 1. 问题定位

| 项 | 内容 |
| :--- | :--- |
| 原始判据 | `consensus.unstable_effect_threshold = 10.0`（`analysis/config.py:38`），用法为 `abs(x) < 10` 才保留 |
| 已有过滤位置 | 证据矩阵 `integration.py:118-120`；跨模型 bootstrap `tasks.py::bootstrap_main_effects`；边级置换 `tasks.py::_valid_row:85-103`；交互置换 `tasks.py::permutation_interactions`（`valid = {… _valid_row(row, thr)}`） |
| **缺失位置** | `tasks.py::permutation_main_effects:295-325` —— 直接对 `environment_conditional_delta_r2.csv` 的 `delta_r2_mean` 做 `dropna()`，**没有任何发散过滤** |
| 实际污染 | `environment_conditional_delta_r2.csv` 中 **130 行 \|ΔR²\| > 10**（全部来自 linear，最大 1.24×10¹⁹）进入置换；产生 **28 行 \|observed_effect\| > 10** 的无效检验（占主效应置换的 11 %），其 p 值落在 0.40–0.88 |

## 2. 修改内容（最小改动）

`analysis/stats/tasks.py::permutation_main_effects`

```python
thr = float(cfg.consensus.unstable_effect_threshold)      # 复用同一参数, 不新增阈值
raw = pd.to_numeric(sub["delta_r2_mean"], errors="coerce")
finite = raw[np.isfinite(raw)]                            # NaN / ±inf 一并剔除
vals = finite[finite.abs() < thr].tolist()                # numerical divergence 剔除
n_excluded = int(len(finite) - len(vals))
```

* 新增 provenance 列 `n_values_excluded`（`PERMUTATION_COLUMNS` 同步扩展），受影响行的 `reason` 追加"已剔除 N 个发散/无效值"。
* **未改动**：sign-flip 方法、`n_permutations=1000`、`seed=2024`、two-sided、`apply_fdr` 的 BH 与 `family_key` 规则、任何 Tier 阈值。

## 3. 修复前 / 修复后（真实资产比对）

| 指标 | 修复前 | 修复后 |
| :--- | ---: | ---: |
| `permutation_results.csv` 总行数 | 3 444 | 3 444 |
| main-effect 中 `\|observed_effect\| > 10` 的无效检验 | **28** | **0** |
| main-effect 中 `status=unavailable` 的行 | 0 | 5（剔除后有效背景 < 3） |
| 被剔除的发散/无效记录（`n_values_excluded` 合计） | — | **130** |
| 受影响的上下文数 | — | 28 |

## 4. 是否改变已有 factor-level FDR？

| factor | 上下文数（旧→新） | min raw p | min FDR | min-FDR 来源 | FWER 上界（去重上下文） |
| :--- | :--- | ---: | ---: | :--- | ---: |
| ctcf | 63 → 61 | 0.006993（不变） | 0.009324（不变） | `all/hek293t/linear`（不变） | 0.238 |
| dnase | 63 → 60 | 0.006993（不变） | 0.013986（不变） | `all/hl60/transformer`（不变） | 0.231 |
| h3k4me3 | 63 → 63 | 0.006993（不变） | 0.009324（不变） | `all/hek293t/linear`（不变） | 0.245 |
| rrbs | 63 → 63 | 0.006993（不变） | 0.009324（不变） | `all/hek293t/linear`（不变） | 0.245 |

**结论：R1 不改变任何 factor 的 min-FDR 与 Tier**（发散行的 p 值本来就大，未被选为最小）。
它的作用是**恢复统计有效性**：清除了 28 个建立在 \|ΔR²\|≈10¹⁵ 上的无效检验、统一了三条路径的口径、
并让"参与选择的上下文数"可被审计（`n_values_excluded` 列）。

环境 Tier 对照（R1 后）：ctcf Inconclusive、dnase Inconclusive、h3k4me3 Inconclusive、**rrbs Tier 1**（R2–R4 将处理其合法性）。

## 5. 测试与产物

| 项 | 结果 |
| :--- | :--- |
| 全量测试 `python -m unittest discover -s analysis/tests -t . -p "test_*.py"` | **188 项通过** |
| 重新生成 | `scripts/regenerate_permutation_and_evidence.py --write`（复用引擎同一函数，未重训） |
| 更新资产 | `tables/permutation_results.csv`（3 444 行，新增 `n_values_excluded`）、`tables/evidence_matrix.csv`（600 行） |
| 备份 | `/tmp/perm_before_r1.csv`（R1 前快照，供 before/after 对照） |

## 6. 进入 R2 的判定

R1 验证通过：**bug 已消除、测试全绿、Tier 未意外变化、provenance 列已落盘** → 允许进入 **R2（重新定义 minimum FDR 的含义）**。
