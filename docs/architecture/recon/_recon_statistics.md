# 统计学工具代码勘察 (只读盘点)

> ⚠️ **历史勘察快照（重构前）**：本文记录 2026-09-14 目录重构**之前**的结构，其中的路径名（`src/`、`analyse/`、`data/proceeded_data/`、`results/<batch>`）均为旧路径。
> 当前权威结构见 `README.md` 与 `docs/architecture/`；科学定义见 `docs/science/`。


> 勘察范围: 仓库 `/home/zhang/bioprogram/Submit` 中**已实现且已被调用/接线**的统计量生成路径。
> 方式: 逐文件阅读 `analyse/stats/`、`analyse/evidence/`、`analyse/cellline/`、`analyse/environment/`、
> `analyse/importance_metrics.py`、`analyse/anomaly_treatment.py`、`analyse/data_QC.py`、`analyse/prediction.py`、
> `analyse/config.py`、`analyse/pipeline.py`、`analyse/collect_results.py`、`docs/paper_analysis/*.py`、
> `paper/make_assets.py`，并核对 `results/`、`docs/` 中实际产物。
> 本文件只做勘察记录, **未修改任何已有文件**。
>
> 标注约定:
> * `[已接线]` = 在 `analyse/pipeline.py::run_analysis` 的真实执行路径上, 产物已落盘;
> * `[仅测试]` = 实现存在、有单测覆盖, 但主流程不调用;
> * `[未确认]` = 仓库内找不到生成脚本/判定依据, 不猜测。

---

## 0. 总览

| # | 工具 | 代码位置 | 状态 | 主产物 |
| :-- | :--- | :--- | :--- | :--- |
| 1 | 百分位 Bootstrap CI (`bootstrap_ci`) | `analyse/stats/bootstrap.py:52` | 已接线 | `tables/bootstrap_main_effects.csv` |
| 2 | 通用差值 Bootstrap (`bootstrap_difference_ci`) | `bootstrap.py:68` | 仅测试 | — |
| 3 | 配对 per-sample Δmetric Bootstrap (`bootstrap_paired_metric_ci`) | `bootstrap.py:132` | 仅测试 | — |
| 4 | 向量化配对 Bootstrap (`..._fast`) | `bootstrap.py:189` | 仅测试 | — |
| 5 | 多指标批量配对 Bootstrap (`..._metrics_ci_fast`) | `bootstrap.py:250` | 已接线 | `tables/bootstrap_results.csv` |
| 6 | Effect 定义 / 配对基线 (`delta_pair`, `compute_paired_increment`) | `effect_size.py:12,17` | 已接线(经配对层) | 同上 |
| 7 | BH-FDR (`bh_fdr`) | `multiple_testing.py:13` | 已接线 | `permutation_results.csv` 的 `FDR` 列 |
| 8 | 符号翻转置换检验 (`permutation_test_for_effect[_fast]`) | `hypothesis_tests.py:26,372` | 已接线 | `tables/permutation_results.csv` |
| 9 | Factorial ANOVA (Type-II SS F 检验) | `hypothesis_tests.py:244` | 已接线 | `tables/anova_results.csv` |
| 10 | ANOVA 兼容包装 (`anova_interface`) | `hypothesis_tests.py:65` | 未接线 | — |
| 11 | 边级 ΔR²/ΔMAE/ΔRMSE Bootstrap 接线 | `stats/tasks.py:141` | 已接线 | `tables/bootstrap_results.csv` |
| 12 | factor 级跨模型 Bootstrap CI | `stats/tasks.py:199` | 已接线 | `tables/bootstrap_main_effects.csv` |
| 13 | cell-line 级跨模型 Bootstrap CI | `stats/tasks.py:526` | 已接线 | `tables/bootstrap_cellline_effects.csv` |
| 14 | 环境边置换检验 | `stats/tasks.py:244` | 已接线 | `permutation_results.csv` |
| 15 | 环境主效应置换检验 | `stats/tasks.py:295` | 已接线 | 同上 |
| 16 | 环境交互置换检验 | `stats/tasks.py:328` | 已接线 | 同上 |
| 17 | 按 family 的 BH-FDR 接线 (`apply_fdr`) | `stats/tasks.py:401` | 已接线 | 同上 `FDR`/`fdr_family` |
| 18 | ANOVA 任务接线 (`run_anova_tasks`) | `stats/tasks.py:436` | 已接线 | `tables/anova_results.csv` |
| 19 | 条件增量 / 主效应 / 成对交互 | `environment/incremental_effect.py:51,109,136` | 已接线 | `environment_conditional_delta_r2.csv` 等 |
| 20 | Factorial DAG 节点/边聚合 | `environment/factorial_dag.py:147,198` | 已接线 | `environment_nodes.csv`, `environment_edges.csv` |
| 21 | Ablation 视图 / 交互聚合 | `factorial_dag.py:357,384` | 已接线 | `environment_ablation.csv`, `environment_interactions.csv` |
| 22 | 方向一致率 / Evidence Tier | `evidence/integration.py:18,43` | 已接线 | `tables/evidence_matrix.csv` |
| 23 | 环境证据矩阵聚合 | `evidence/integration.py:90` | 已接线 | 同上 |
| 24 | cell-line context 一致性判定 | `cellline/consistency.py:58,146` | 已接线 | `tables/cellline_effects.csv` |
| 25 | FDR/SNR 分级规则 (rules.py) | `evidence/rules.py:12,29,56` | 仅测试 | — |
| 26 | 重要性-ΔR² 证据强度分级 (`evidence_strength`) | `importance_metrics.py:100` | 已接线 | `importance_vs_delta_r2.csv` |
| 27 | 因子 importance 扫描/归一化 | `visualization/importance_delta.py:103,215` | 已接线 | 同上 |
| 28 | 实验级/数据级异常检测 | `anomaly_treatment.py:144,215` | 已接线(独立脚本) | `summary/anomaly_report.md` |
| 29 | 指标一致性标记 | `data/validation.py:14,29` | 已接线 | `tables/metric_inconsistency.csv` |
| 30 | 预测性能均值/标准差 | `prediction.py:11,24` | 已接线 | `prediction_summary.csv`, `loco_performance.csv` |
| 31 | KDE 带宽 CV 选择 + 3σ 离群提示 | `data_QC.py:157,348` | 已接线(GUI/独立) | `qc_summary.json` 等 |
| 32 | IsolationForest 多模态离群检测 | `data_QC.py:1099` | 已接线(GUI/独立) | `outliers_detailed_report.csv` |
| 33 | 结果收集侧 ΔR² / 多种子平均 | `collect_results.py:217,291,360` | 已接线(独立脚本) | `summary/metrics_tables/*.csv` |
| 34 | 归因 importance 跨 context 均值 | `attribution/summary.py:9` | 已接线 | `summary/04_sequence_motifs.md` |
| 35 | Seqlet 分位阈值 + motif consensus 支持度 | `sequence/motif/core.py:205,416` | 已接线 | `tables/motif_candidates.csv` |
| 36 | Motif Fisher 精确检验 + BH-FDR | `sequence/motif/core.py:462,509` | 已接线 | `tables/motif_enrichment.csv` |
| 37 | Motif evidence 分级 / 稳定性 | `motif/core.py:522`, `motif/pipeline.py:335` | 已接线 | `motif_candidates.csv`, `motif_evidence.csv` |
| 38 | 训练侧线性 OLS SE/t/p/BH-FDR | `src/linear_regression/linear_regression.py:190` | 已接线(训练侧) | 各实验 `*_feature_importance.csv` |
| 39 | 论文 Table/Fig 的 factor 级 CI | `paper/make_assets.py:356` | 已执行 | `docs/paper_analysis/factor_level_ci.csv` |
| 40 | 论文边级 bootstrap 保守并集聚合 | `paper/make_assets.py:702` | 已执行 | `docs/paper_analysis/bootstrap_edge_by_factor.csv` |
| 41 | Position-18 ISM 审计描述统计 | `docs/paper_analysis/position18_ism_audit.py:91` | 已执行 | `results/analysis/position18_ISM_audit.csv` |
| 42 | Position-18 有符号替换 ISM Bootstrap | `docs/paper_analysis/position18_signed_substitution_ism.py:210` | 已执行 | `results/analysis/position18_signed_substitution_ISM.csv` |
| 43 | 论文预测表 mean/median/sd | `paper/make_assets.py:463` | 已执行 | `paper/tables/tab1_dataset.tex`, `tab2_prediction.tex` |

---

## 1. `analyse/stats/bootstrap.py` — Bootstrap 系列

### 1.1 百分位 Bootstrap CI (`bootstrap_ci`)
- **代码位置**: `analyse/stats/bootstrap.py:25-49` (`_bootstrap_stats`), `:52-65` (`bootstrap_ci`)
- **用途**: 对任意 `estimator` 的单组数值给出 percentile bootstrap 置信区间, 定位是**稳定性/不确定性证据**, 文件头明确写"非因果/显著"(`bootstrap.py:1`)。
- **输入**: 调用方传入的 float 序列。真实接线两处:
  - `stats/tasks.py:214-231`: 每个 factor 的 **每模型 main effect 均值**列表;
  - `stats/tasks.py:541-555`: 每个 `(split_type, cell_line, factor)` 的 **跨模型 `main_r2_delta`** 列表。
  - 原始来源: `tables/environment_main_effects.csv` 列 `main_r2_delta`(由 #19 生成)。
- **关键超参**: `n_iterations=2000`, `seed=2024`, `alpha=0.05`(`bootstrap.py:55-57`); 由 `AnalysisConfig.bootstrap_iterations/bootstrap_seed/bootstrap_alpha` 注入(`config.py:174-176`)。样本 `<3` 返回 `available=False`(`:63-64`)。
- **聚合与加权**:
  - 对输入值做**等概率有放回重采样**(每个值权重 `1/n`), **不按样本数 n 加权**;
  - `estimator` 在接线处固定为 `lambda x: float(np.mean(x))`(`tasks.py:229`, `:553`) → **算术平均**;
  - 无分组、无多次实验平均、无"取最优"规则;
  - 单位是"模型"(跨模型 bootstrap), 输出用 `estimate_basis="cross_model_mean_of_main_effect"` 显式标注(`tasks.py:225`, `:550`), 避免误读为样本级 CI。
- **输出**: `tables/bootstrap_main_effects.csv`(列 `feature,estimate,ci_low,ci_high,excludes_zero,n_bootstrap,seed,n_models,estimate_basis,status`)与 `tables/bootstrap_cellline_effects.csv`。
- **产物存在性**: 已存在 — `results/batch_20260909_full/summary/tables/bootstrap_main_effects.csv`(4 行数据 + 表头)、`.../bootstrap_cellline_effects.csv`(36 行数据 + 表头)。

### 1.2 通用差值 Bootstrap (`bootstrap_difference_ci`) `[仅测试]`
- **代码位置**: `bootstrap.py:68-107`
- **用途**: baseline 与 expanded 两组之间 `Δmetric` 的 bootstrap CI, `paired=True` 时逐对同索引重采样, 样本数不等返回 unavailable(`:87-88`)。
- **输入**: 两组 float 序列 + `metric_fn`。
- **关键超参**: `n_iterations=2000`, `seed=2024`, `alpha=0.05`, `paired=True`(默认签名 `:74-75`)。
- **聚合与加权**: 逐对样本重采样后 `metric(b[idx]) - metric(a[idx])`, 即**配对差**; 不按 n 加权。
- **输出**: 仅返回 `BootstrapResult`, 无落盘。
- **产物存在性**: 无。仅在 `analyse/tests/test_core.py:79`、`test_stats_wiring.py:81,88` 使用。

### 1.3 配对 per-sample Δmetric Bootstrap (`bootstrap_paired_metric_ci`)
- **代码位置**: `bootstrap.py:132-169`; 辅助 `metric_r2/metric_mae/metric_rmse` 在 `:113-129`, `PAIRED_METRIC_FUNCTIONS` 在 `:172`。
- **用途**: 同一批 test 样本下 `Δmetric = metric(expanded) − metric(baseline)` 的配对 bootstrap(`R²/MAE/RMSE`)。
- **输入**: `pairs = (n,2) = [y_true,y_pred]` 数组, 来自 `<batch>/<run_name>/*_predictions.csv` 的 `y_true`/`y_pred` 列(`tasks.py:52-82`, 排除 `validation` 文件)。
- **关键超参**: `n_iterations=2000`, `seed=2024`, `alpha=0.05`; `n<3` 或两侧样本数不等 → `available=False`(`:151-152`)。
- **聚合与加权**: 每次迭代对**同一批样本索引**重采样两侧模型(`:160-161`), 因此 Δ 方差含样本组成相关性; 未按 n 加权。
- **输出**: 无直接落盘(被 1.5 取代)。
- **产物存在性**: 无。仅 `test_stats_wiring.py:103`。

### 1.4 向量化配对 Bootstrap (`bootstrap_paired_metric_ci_fast`) `[仅测试]`
- **代码位置**: `bootstrap.py:189-226`; 向量化 metric 在 `:175-186`。
- **说明**: 与 1.3 语义一致, 随机数消耗方式不同(同 seed 下不保证逐位一致, `:200`)。主流程未调用。

### 1.5 多指标批量配对 Bootstrap (`bootstrap_paired_metrics_ci_fast`) `[已接线]`
- **代码位置**: `bootstrap.py:250-306`; 重采样计数矩阵缓存 `_count_matrix` 在 `:235-247`。
- **用途**: 一次重采样同时给出 `R2/MAE/RMSE` 三个 metric 的配对 CI("~2600 条边"批量场景提速, `:260-262`)。
- **输入**: 同上(`y_true,y_pred` per-sample); 调用点 `tasks.py:179-181`(`bootstrap_environment_edges`)。
- **关键超参**: `n_iterations=2000`, `seed=2024`, `alpha=0.05`(来自 `AnalysisConfig`); 同一 `(n, n_iterations, seed)` 的 multinomial 计数矩阵被**进程内缓存复用**(`_COUNT_CACHE`, `:232-247`)。
- **聚合与加权**:
  - 每次迭代对**同一批样本索引**同时重采样 baseline 与 expanded(`:272-284`);
  - R² 用计数矩阵 matvec 重算 `SS_res` 与 `SS_tot`(`:281-300`);
  - 点估计仍用 float64 原值; 重采样分布用 float32(`:278-279`);
  - **不按 n 加权**, 无跨实验/跨 kernel 平均;
  - 非有限重采样值被丢弃后再取分位(`:287-289`)。
- **输出**: `tables/bootstrap_results.csv`(`tasks.py:196`, 列见 `BOOTSTRAP_COLUMNS` `tasks.py:33-36`)。
- **产物存在性**: 已存在 — `results/batch_20260909_full/summary/tables/bootstrap_results.csv`(7770 数据行, 含 `metric=R2/MAE/RMSE`)。

### 1.6 Effect 定义与配对基线 (`delta_pair`, `compute_paired_increment`)
- **代码位置**: `analyse/stats/effect_size.py:12-14`, `:17-32`
- **用途**: 定义 `Δ = expanded − baseline`(正=提升); `compute_paired_increment` 仅在两侧样本量一致(或容差内)时返回可信增量, 否则返回 `(nan, False)`(`:29-31`)。
- **输入**: 标量 metric 与两侧 n。
- **关键超参**: `tolerance=0`。
- **聚合与加权**: 纯差值, 无加权。
- **输出**: 无独立落盘; 配对思想由 `environment/incremental_effect.py` 的 `GROUP_COLS`(`split_type, cell_line, model, random_seed`, `:17`)落地。
- **产物存在性**: 逻辑已体现在 `environment_conditional_delta_r2.csv` / `bootstrap_results.csv`, 无同名产物。

---

## 2. `analyse/stats/hypothesis_tests.py` — 置换检验与 ANOVA

### 2.1 符号翻转随机化检验 (`permutation_test_for_effect`)
- **代码位置**: `hypothesis_tests.py:26-62`; 向量化版本 `:372-400`。
- **用途**: one-sample(sign-flip)置换检验; `H0: (x − null_effect) 关于 0 对称` → 符号可交换; 统计量=均值。文件头注释解释了为什么不能对中心化值"重排"(`:46-48`)。
- **输入**: `effect_values` 序列。三处接线:
  - `tasks.py:280-285`(`environment_edge`): `SE_parent_i − SE_child_i`, 同一 test 样本(`SE=(y_true−y_pred)²`);
  - `tasks.py:302-321`(`environment_main_effect`): 每 `(split, cell, model, factor)` 的 `delta_r2_mean`(来自 `environment_conditional_delta_r2.csv` 列 `delta_r2_mean`);
  - `tasks.py:351-391`(`environment_interaction`): 逐背景 `S0` 的**样本级交互 contrast** 堆叠后按样本均值。
- **关键超参**: `n_permutations=1000`(`:29`), `seed=2024`(`:30`), `one_sided` ∈ `greater|less|two_sided`; 由 `config.permutation_iterations=1000` 与 `config.bootstrap_seed=2024` 注入(`config.py:177,175`); 样本 `<3` → `null_stats_available=False`(`:42-44`)。p 值加一平滑 `p=(count+1)/(B+1)`(`:61`)。
- **聚合与加权**:
  - edge 检验: `SE_parent − SE_child` 的**逐样本**列表(不聚合), 单侧 `greater`;
  - main effect 检验: 对同一 (split, cell, model, factor) 的**多背景 `delta_r2_mean` 列表**做检验(对背景等权, `tasks.py:305`), 双侧; 样本 `<3` 记 unavailable(`:313-317`);
  - interaction 检验: 先把各背景的 per-sample contrast **按样本位置平均**(`np.mean(np.vstack(diffs), axis=0)`, `tasks.py:388`), 再做检验 → 相当于**背景等权后再样本级检验**;
  - 无"取最优"; 无 n 加权。
- **输出**: `tables/permutation_results.csv`(`tasks.py:242`, 列见 `PERMUTATION_COLUMNS` `tasks.py:37-41`; 含 `null_hypothesis`/`alternative`/`n_permutations`/`seed`/`family_key`)。
- **产物存在性**: 已存在 — `.../tables/permutation_results.csv`(3444 数据行)。

### 2.2 Factorial ANOVA (`factorial_anova`)
- **代码位置**: `hypothesis_tests.py:244-369`; 结果 dataclass `AnovaTermResult` `:120-145`; 设计矩阵 `_dummy_columns` `:148-154`, `_design_from_terms` `:157-180`; RSS `_fit_rss` `:183-186`; F 上尾概率 `_f_sf` `:189-241`(scipy 优先, 否则正则不完全 Beta 连分式)。
- **用途**: **Type-II 边际 extra-sum-of-squares F 检验**: `response ~ factors(+成对交互)+block`, 避免把每个 R² 当独立重复(`:255-262`)。
- **输入**: 统一实验表(`tables/experiment_table.csv`, 由 `summary/metrics_tables/all_experiments.csv` 归一化); `response="R2"`, `factors` = 环境二值列(由 `tasks.py:_binary_factors` `:427-433` 从 `environment` 组合名解析), `block_factors=("model","cell_line","split_type")`(`config.py:79`)。`tasks.py:445-446` 先剔除 `R2` 非有限或 `|R2|>10` 的行。
- **关键超参**: `min_observations=32`, `min_residual_df=5`, `include_interactions=True`, `alpha=0.05`, `ci_iterations=400`(effect contrast 的**行级 bootstrap** 迭代数, `config.py:78`), `seed=2024`; 不足 → `status="unavailable"` 且统计量为 `None`(`:275-310`)。
- **聚合与加权**:
  - design 用 dummy 编码(丢弃首水平防共线); 交互列 = dummy 逐元素乘积(`:175-178`);
  - 逐 term 用 reduced model 的 `RSS_red − RSS_full` 构造 F(`:328-330`);
  - `effect_size = ss_term / ss_total`(partial η² 语义, `:331`);
  - 二值因子的 `effect` = 回归系数(水平1−水平0)之差(`:335-343`);
  - effect 的 CI = **对行(观测)有放回重采样**后重估系数差的 percentile CI(`:344-357`), **不是**对模型/kernel 平均;
  - 主流程跑两种 design(`tasks.py:436-486`): 全局 `blocked_factorial`(含交互, `n_iterations=ci_iterations=400`)与每个 `(split,cell,model)` 的 `per_group_additive_main`(**`n_iterations=0` → CI 为 None**, 只估加性主效应, `:478-483`)。
- **输出**: `tables/anova_results.csv`(列见 `ANOVA_COLUMNS` `tasks.py:42-44`; 含 `F_statistic,p_value,df_num,df_den,effect_size,ci_low,ci_high,n_obs,family_key,status,reason`)。
- **产物存在性**: 已存在 — `.../tables/anova_results.csv`(94 数据行)。`docs/statistical_analysis_status.md:90-92` 记载本批 blocked factorial 主效应 F=0.60/2.31/1.95/2.18、p=0.66/0.056/0.100/0.069、partial η²≈0.0005–0.0018, 交互 p=0.26–0.85(与产物一致, 未逐行复核)。

### 2.3 ANOVA 兼容包装 (`anova_interface`) `[未接线]`
- **代码位置**: `hypothesis_tests.py:65-110`
- **说明**: 旧签名包装, 内部调用 `factorial_anova` 并只取第一个 `ok` term(`:106-109`), `FDR` 字段恒为 `None`。仓库内无主流程调用点(仅 `__all__` 导出)。

---

## 3. `analyse/stats/multiple_testing.py` — BH-FDR

### 3.1 Benjamini–Hochberg FDR (`bh_fdr`)
- **代码位置**: `analyse/stats/multiple_testing.py:13-35`
- **用途**: 对一组 p 值给 q 值(单调非降, 数值兼容 `statsmodels.multipletests`), 非有限 p 原位 NaN(`:19-25`)。
- **输入**: `Iterable[Optional[float]]`。三个使用点:
  1. `stats/tasks.py:401-421`(`apply_fdr`)对 `permutation_results.csv` 的 `p_value` 按 `family_key` 分组校正;
  2. `sequence/motif/core.py:509-516`(`apply_enrichment_fdr`)对 `motif_enrichment` 一个 family;
  3. `src/linear_regression/linear_regression.py:219-232`(训练侧自实现同算法, 见 §11)。
- **关键超参**: 算法本身无参数; `min_family_size=2`(`config.py:149`)。
- **聚合与加权**: 逐 p 值的 rank 校正, 与样本数/权重无关; 输出与输入等长。
- **输出**: 列 `FDR`(permutation)与 `p_adj_fdr`(linear); motif enrichment 列 `FDR`。
- **产物存在性**: 已存在 — `permutation_results.csv` 含 `FDR`/`fdr_family`/`fdr_status`; `motif_enrichment.csv` 含 `FDR`/`fdr_family`; 线性实验目录的 `*_feature_importance.csv` 含 `FDR`。

**FDR family 与作用范围(实际)**:

| family | 生成位置 | 成员定义 | 典型规模 |
| :--- | :--- | :--- | :--- |
| `environment_edge\|<split>\|<cell>\|<model>` | `tasks.py:265` | 同一 group 下所有 lattice 边(`_lattice_pairs`) | 每 family 数十条 |
| `environment_main\|<split>\|<cell>\|<model>` | `tasks.py:312` | 同一 group 下所有环境因子的主效应检验 | 4 |
| `environment_interaction\|<split>\|<cell>\|<model>` | `tasks.py:380-381` | 同一 group 下所有因子对的交互检验 | 6 |
| `environment_anova\|global` | `tasks.py:466` | 全局 blocked factorial 的所有 term | ~10 |
| `environment_anova_group\|<split>\|<cell>\|<model>` | `tasks.py:485` | per-group 加性主效应 term | 4 |
| `motif_enrichment` | `motif/core.py:465` | 所有 motif 的 Fisher exact p | 596 |

- **注意**: `config.FdrFamilyConfig.enabled_families`(`config.py:143-148`)列出的 6 个 family 与代码实际写入的 `family_key` **字符串不一致**(config 用 `environment_permutation_edge` 等, 代码用 `environment_edge` 等)。当前 `apply_fdr` 只按数据里的 `family_key` 分组, **未校验 `enabled_families` 白名单**; `config.py` 的 `min_family_size=2` 是实际生效的。该不一致是否设计意图 **未确认**。
- ANOVA 结果表虽含 p 值, 但 `apply_fdr` 只处理 permutation 表; `anova_results.csv` 中 **没有 FDR 列**(表头已核对)。ANOVA 的 FDR 校正是否应做 **未确认/未实现**。

---

## 4. `analyse/stats/tasks.py` — 统计工具接线层

### 4.1 环境边配对 Bootstrap (`bootstrap_environment_edges`)
- **代码位置**: `tasks.py:141-196`; 边枚举 `_lattice_pairs` `:104-135`; 预测读取 `predictions_path` `:52-58`、`load_run_pairs` `:61-82`; 有效性 `_valid_row` `:85-101`。
- **用途**: 为每条 `S → S∪{e}` lattice 边计算 `ΔR²/ΔMAE/ΔRMSE` 的 per-sample 配对 bootstrap CI。
- **输入**:
  - 边来源: `tables/experiment_table.csv`(列 `split_type,cell_line,model,random_seed,environment,run_name,R2,MAE,RMSE,Pearson,Spearman`);
  - 样本级: `<batch>/<run_name>/*_predictions.csv` 的 `y_true,y_pred`(排除 `*validation*`)。
- **关键超参**: `B=2000`, `seed=2024`, `alpha=0.05`; 剔除 `|R2|>10` 等无效实验; 两侧样本数不等 → `status=unavailable, reason=cohort_mismatch`(`:172-178`); 缺预测 → `prediction_artifact_missing`(`:165-171`)。
- **聚合与加权**:
  - 严格同一 `(split_type, cell_line, model, random_seed)` 分组内配对(`:107-108`);
  - 每行 = "(边 × metric)" 一个 CI, **不跨 seed 平均**; 同一 factor 的多条边以多行并存;
  - 点估计 = 两侧 metric 差, 不做模型/kernel 平均。
- **输出**: `tables/bootstrap_results.csv`; 另经 `edge_ci_table`(`:512-523`)抽出 `metric=="R2"` 行生成 `tables/environment_bootstrap.csv`, 再由 `factorial_dag.merge_edge_ci` 合入 `environment_edges.csv`。
- **产物存在性**: 已存在 — `bootstrap_results.csv`(7770 行)、`environment_bootstrap.csv`、`environment_edges.csv`(2651 行, 含 `ci_low/ci_high/ci_excludes_zero/n_bootstrap/bootstrap_status`)。

### 4.2 factor 级跨模型 Bootstrap CI (`bootstrap_main_effects`)
- **代码位置**: `tasks.py:199-238`
- **用途**: 为每个环境 factor 给 factor 级 CI, 供 Evidence Tier 的"CI 是否跨 0"判定。
- **输入**: `tables/environment_main_effects.csv` 的 `environment`,`model`,`main_r2_delta`。
- **关键超参**: `B=2000`, `seed=2024`, `alpha=0.05`; 需 `>=3` 个模型(`:221-227`)。
- **聚合与加权**:
  - 先按 `|main_r2_delta| < unstable_effect_threshold(10.0)` 剔除(`:213-220`);
  - **先按 model 求均值(等权, 每个模型一票)**, 再对模型列表做 bootstrap(`:219-231`);
  - 这是 `docs/paper_analysis/README.md:24-26` 记录的修正: 原实现对全部 `(模型×划分×细胞系)` 行直接 bootstrap, 网格不均衡时 CI 可能不含点估计。
- **输出**: `tables/bootstrap_main_effects.csv`。
- **产物存在性**: 已存在(4 factor 行)。

### 4.3 cell-line 级跨模型 Bootstrap CI (`bootstrap_cellline_effects`)
- **代码位置**: `tasks.py:526-562`
- **用途**: 每个 `(split_type, cell_line, factor)` 的跨模型 main effect CI, 供 cell-line CI overlap 判定。
- **输入**: 同上表的 `main_r2_delta`。
- **关键超参**: `B=2000`, `seed=2024`, `alpha=0.05`; `>=3` 个模型。
- **聚合与加权**: 单元 = **模型**; 在每个 `(split, cell, factor)` 内对有限值等权 bootstrap 均值; 输出 `estimate_basis="cross_model_mean_main_effect_per_cellline"`(`:550`)。
- **输出**: `tables/bootstrap_cellline_effects.csv`; 经 `cellline_ci_lookup`(`:565-575`)转成 `{(split,factor): {cell:(lo,hi)}}` 供一致性判定。
- **产物存在性**: 已存在(36 行)。

### 4.4 置换检验接线(三处)
- **位置**: `permutation_environment_edges` `tasks.py:244-292`、`permutation_main_effects` `:295-325`、`permutation_interactions` `:328-395`。
- **超参**: `n_permutations=1000`(`config.permutation_iterations`), `seed=2024`(`config.bootstrap_seed`); edge 单侧 `greater`, main/interaction 双侧。
- **聚合与加权**: 见 §2.1; 特别地 interaction 在把各背景 per-sample contrast 汇总时使用 `np.mean(np.vstack(diffs), axis=0)`(`:388`)——**背景等权、按样本位置对齐**。
- **产物存在性**: `permutation_results.csv`(3444 行)。

### 4.5 FDR 接线 (`apply_fdr`)
- **代码位置**: `tasks.py:401-421`
- **规则**: `fdr_family = family_key`; 每个 family 内 finite p 数 `< min_family_size(2)` → `fdr_status="not_applicable (...)"`; 否则 `bh_fdr` 写 `FDR` 并置 `fdr_status="ok"`。
- **产物存在性**: `permutation_results.csv` 的 `FDR/fdr_family/fdr_status` 列已存在。

### 4.6 ANOVA 接线 (`run_anova_tasks`)
- **代码位置**: `tasks.py:436-486`; 二值因子构造 `_binary_factors` `:427-433`。
- **关键超参**: 全部来自 `config.anova`(min_observations=32, min_residual_df=5, include_interactions=True, ci_iterations=400, block_factors=(model,cell_line,split_type))。
- **聚合与加权**: 全局 1 次 blocked ANOVA + 每 `(split,cell,model)` 1 次加性 ANOVA; 每个 term 一行, 不做跨组平均。
- **产物存在性**: `tables/anova_results.csv`(94 行)。

### 4.7 能力探测 (`statistics_capabilities`)
- **代码位置**: `tasks.py:492-509`
- **说明**: 基于 artifact 存在性判断 bootstrap/permutation/anova 是否可跑; `anova_available = n_rows >= 32`。非统计量, 但决定上面工具是否执行。

---

## 5. `analyse/evidence/` — 证据分级与整合

### 5.1 方向一致率 (`direction_concordance`)
- **代码位置**: `analyse/evidence/integration.py:18-28`
- **用途**: 在"去零方向"中, 多数方向占比 = `max(count(+), count(−)) / len(nonzero)`。
- **输入**: effect 列表。
- **关键超参**: 无。
- **聚合与加权**: **模型等权**(每个模型算一票, 不做 n 加权), 不取平均。
- **输出**: `evidence_matrix.csv` 的 `direction_concordance` 列。

### 5.2 Evidence Tier 判定 (`classify_evidence_tier`)
- **代码位置**: `integration.py:43-65`
- **判定规则(按顺序)**:
  1. `conflicting_direction == True` 或 `ci_crosses_zero == True` → `Inconclusive`;
  2. `supporting_model_count >= consensus.min_coverage (2)` 且 (`concordance is None` 或 `concordance >= consensus.direction_concordance (0.80)`) 且 `strong_stat_or_attribution` → `Tier 1: Strong convergent evidence`;
  3. `supporting_model_count >= 2` → `Tier 2: Moderate convergent evidence`;
  4. `supporting_model_count == 1` 且 `strong_stat_or_attribution` → `Tier 3: Model-specific / exploratory evidence`;
  5. `applicable_model_count == 0` → `No current evidence`;
  6. 其它 → `Inconclusive`。
- **阈值来源**: `analyse/config.py:30-38`(`min_coverage=2`, `direction_concordance=0.80`, `cellline_consistent_ratio=0.75`, `environment_strong_effect=0.01`, `unstable_effect_threshold=10.0`)。
- **Tier 文案**: `analyse/schemas.py:40-45`。

### 5.3 环境证据矩阵 (`environment_evidence_matrix`)
- **代码位置**: `integration.py:90-214`
- **用途**: 把环境 factor 的主效应、跨模型一致性、CI、置换 p/FDR、cell-line context 汇成一行一个 factor 的证据行。
- **输入**:
  - `tables/environment_main_effects.csv`: `model`,`environment`,`main_r2_delta`;
  - `tables/cellline_effects.csv`: `factor`,`context_label`(取众数);
  - `tables/bootstrap_main_effects.csv`(经 pipeline `stats_bundle["main_ci"]`);
  - `tables/permutation_results.csv`(经 `stats_bundle["permutation"]`)。
- **关键超参**: `unstable_effect_threshold=10.0`, `environment_strong_effect=0.01`, `min_bootstrap_iterations=200`, `fdr_weak=0.05`, `min_coverage=2`, `direction_concordance=0.80`。
- **聚合与加权(重点)**:
  - **稳定性过滤**: `|main_r2_delta| < 10.0` 才进入矩阵(`:118-120`), 被排除行数记 `unstable_rows_excluded`;
  - **两级平均**: 先 `model_mean = groupby(model, factor).mean()`(跨 split/cell 行的**算术平均**), 再 `overall = mean(各模型均值)` → **模型等权**;
  - **supporting 定义**: 与总体均值同号的模型数(`:136-138`), 不是"CI 显著"的模型数;
  - **strong 判定**: `any(|e| >= 0.01)` 或 **permutation FDR < 0.05**(`statistical_support`, `:177-179`), 二者取"或";
  - **CI**: 只有 `bootstrap_status=="ok"` 且 `n_bootstrap >= 200` 才采信(`:155-160`); `ci_crosses_zero = not excludes_zero`, 缺失保持 `None`(不伪造);
  - **非平均规则(取最优)**: `permutation_p` 与 `permutation_fdr` 取该 factor 所有行中的 **最小值**(`:172,175`)——即"最有利"的 p/FDR;
  - **cell_line_consistency**: 对该 factor 的 `context_label` 取 **众数**(`value_counts().idxmax()`, `:140-143`); 若为 `Context-conflicting` 直接覆盖为 `Inconclusive`(`:181-182`)。
- **输出**: `tables/evidence_matrix.csv`(环境行)之外, pipeline 还会 `concat` motif 证据行(`pipeline.py:416-420`)。
- **产物存在性**: 已存在 — `.../tables/evidence_matrix.csv`(600 数据行, 含环境与 motif 行; 含 `coverage,direction_concordance,ci_low,ci_high,n_bootstrap,permutation_p,permutation_fdr,evidence_tier`)。

### 5.4 `evidence/rules.py` 分级函数 `[仅测试]`
- **代码位置**: `classify_statistical_by_fdr` `rules.py:12-26`; `classify_attribution` `:29-53`; `classify_mutation_effect` `:56-67`; `direction_of` `:70-73`。
- **规则**:
  - 统计证据(严格 `<`): `FDR < 0.001` → Strong statistical; `< 0.01` → Moderate; `< 0.05` → Weak; 否则 None(`:20-26`), 阈值来自 `config.statistical`(`config.py:23-26`, 另有 `fdr_nominal=0.10` 未被该函数使用)。
  - 归因证据: 先要求 `|effect| >= min_effect_size`(默认 0.005), 再 `SNR >= 2.5` → Strong attribution, `>=1.8` → Moderate, `>=1.2` → Weak, 否则 None(`:45-53`)。
  - 突变效应: `SNR >= 2.5` **且** `|delta_mean| >= 0.005` → Strong mutation effect(`:65-67`)。
- **重要事实**: 这三个函数在仓库内**只有单测调用**(`analyse/tests/test_core.py:86-101`), **未接入 pipeline**; 实际生效的统计学分级是 §5.2 的 `classify_evidence_tier` 与 §8.1 的 `evidence_strength`。`direction_of`(public)同样无生产调用。

### 5.5 假设生成 (`generate_hypotheses_for_record`)
- **代码位置**: `analyse/evidence/hypothesis.py:23-81`
- **用途**: 按 Tier 生成受控措辞的可检验假设句。
- **输入**: `EvidenceRecord`(由 `evidence_matrix` 行构造, `reports/markdown_report.py` 侧)。
- **分级文案规则**: `TIER1/TIER2` + `cell_line_consistency=="Context-conflicting"` → "suggests context-dependent contributions"; 其它 TIER1 → "strongly supports", TIER2 → "supports"; `TIER3` → "single-model support"; `INCONCLUSIVE` → 不结论; 其它(NONE) → "No current evidence"(`:37-60`)。
- **聚合**: 无统计计算, 纯文案。
- **产物存在性**: `summary/07_biological_hypotheses.md` 已存在。

---

## 6. `analyse/cellline/consistency.py` — cell-line 一致性

### 6.1 完整判定 (`classify_cellline_consistency_detail`)
- **代码位置**: `consistency.py:58-132`
- **用途**: 用"方向一致率 + 幅度异质性 + CI 重叠"给出 4 类 context 标签(不再只看 `all_same_sign`)。
- **输入**: `effects_by_cell_line: {cell: effect}`; 可选 `ci_by_cell_line: {cell: (lo,hi)}`(来自 `bootstrap_cellline_effects.csv` 经 `cellline_ci_lookup`)。
- **关键超参**(`config.CelllineConsistencyConfig`, `config.py:41-57`): `min_cell_lines=2`, `consistent_ratio=0.75`, `conflicting_ratio=0.25`, `heterogeneity_ratio=2.0`, `ci_overlap_relaxes=True`。
- **聚合与加权(重点)**:
  - 有效值 `< min_cell_lines` 或非零方向数不足 → `Uncertain`(`:82-86`);
  - majority 方向 = 非零方向多数(平票取 `-`, `:90`); `majority_ratio = n_majority / n_nonzero`(**cell line 等权**, 不是按样本数加权);
  - **异质性 = max|effect| / median|effect|**(`:95-98`) → 非平均、非加权, 是极值比;
  - **CI overlap 放宽**: 若**所有** minority×majority 的 CI 两两重叠, 则 `ci_overlap_relaxed=True`, 不升级为 conflicting(`:100-110`);
  - 判定顺序: `minority_ratio >= 0.25 且未放宽` → `Context-conflicting`; 无 minority 且 `heterogeneity <= 2.0` → `Context-consistent`; `majority_ratio >= 0.75` → `Context-dependent`; 否则 `Uncertain`(`:112-126`)。
- **输出**: dict(label + 诊断量), 由 `summarize_environment_by_cellline` 写表。

### 6.2 汇总表 (`summarize_environment_by_cellline`)
- **代码位置**: `consistency.py:146-194`
- **输入**: `environment_main_effects.csv`(`main_r2_delta`), 按 `(split_type, model, factor)` 分组, 组内每 cell line 一个 effect。
- **聚合与加权**: 每个 `(split, model, factor)` 一行; 不跨 cell line 平均(逐 cell 列展开为 `effect_<cell>` 与 `ci_low/high_<cell>`); 标签由 6.1 给出。
- **输出**: `tables/cellline_effects.csv`(`pipeline.py:395`)。
- **产物存在性**: 已存在 — 84 数据行, 列含 `context_label,majority_ratio,minority_ratio,heterogeneity,ci_overlap_relaxed,effect_<cell>,ci_low_<cell>,ci_high_<cell>`。

### 6.3 计数 (`consistency_counts`)
- **位置**: `consistency.py:197-200`; 仅 `value_counts()` 供 md 报告。

---

## 7. `analyse/environment/` — 条件增量与 Factorial DAG

### 7.1 条件增量 (`compute_conditional_increments`)
- **代码位置**: `incremental_effect.py:51-90`; `GROUP_COLS` `:17`, `METRIC_PAIRS` `:18`。
- **用途**: 在**同一** `(split_type, cell_line, model, random_seed)` 内枚举所有 `S → S+e`, 计算 `Δ = metric(S+e) − metric(S)`(R²/MAE/RMSE)。
- **输入**: 统一实验表 `environment`,`R2`,`MAE`,`RMSE`,`random_seed` 等列。
- **关键超参/约束**: 同一 key 出现多行 → 直接拒绝而非隐式平均(`:70-71`); 任一 metric NaN → 跳过(`:74-75`)。
- **聚合与加权**: 输出**长表, 每行 = 一次配对增量**, 无任何平均; **不跨 seed 配对**(`:6-7` 注释)。
- **输出**: 中间表; 落盘产物为它的聚合版本 `tables/environment_conditional_delta_r2.csv`。

### 7.2 条件增量汇总 (`summarize_conditional`)
- **代码位置**: `incremental_effect.py:93-106`
- **聚合与加权**: 按 `(split, cell, model, environment_added, background)` 分组, 对同组内多 seed 取 **算术平均**(`delta_r2_mean/delta_mae_mean/delta_rmse_mean`), 记录 `n_paired` 计数。→ **先按背景分组, 再跨 seed 平均**。
- **产物存在性**: `environment_conditional_delta_r2.csv`(2016 数据行)。

### 7.3 主效应 (`compute_main_effects`)
- **代码位置**: `incremental_effect.py:109-133`
- **聚合与加权(重点, 两级平均)**:
  1. 先按 `(split, cell, model, random_seed, environment_added)` 对**所有背景**求算术平均 → `per_seed`(并记 `n_backgrounds`);
  2. 再按 `(split, cell, model, environment_added)` 对**所有 seed** 求算术平均 → `main_r2_delta/main_mae_delta/main_rmse_delta`, 记 `n_seeds` 与 `n_backgrounds_avg`(`:123-130`)。
  - 即 **背景等权 + seed 等权**, **不按样本数 n 加权**, 不使用中位数/取最优。
- **输出**: `tables/environment_main_effects.csv`(`pipeline.py:194`)。
- **产物存在性**: 已存在(252 数据行)。

### 7.4 成对交互 (`compute_pair_interactions`)
- **代码位置**: `incremental_effect.py:136-172`
- **用途**: `I(a,b) = E[Δ(a|S+b)] − E[Δ(a|S不含b)]`。
- **聚合与加权**: 每个 `(split,cell,model,seed)` 内, 对含 b / 不含 b 的背景集合各取**算术平均**后相减(`:163`); 输出每 seed 一行。
- **关键点**: 注释记录了一个已修 bug——背景名必须解析成集合再判断 b(`:154-156`)。

### 7.5 Factorial DAG 节点 (`build_environment_nodes`)
- **代码位置**: `factorial_dag.py:147-184`; 有效性 `experiment_validity` `:125-137`。
- **用途**: 每个 `(split, cell, model, 环境组合)` 一行, **理论上 16 个组合全部保留**(缺失也建行)。
- **输入**: 统一实验表 `environment, R2, MAE, RMSE, Pearson, Spearman`。
- **关键超参**: `threshold=10.0`(来自 `consensus.unstable_effect_threshold`); 缺失/发散/相关越界 → 从均值中剔除并记 `n_invalid` + warning(`:159-172`)。
- **聚合与加权**: 同组合内所有有效实验(含多 seed)对每个 metric 取 **算术平均**(`vdf[m].mean()`, `:163-164`); 节点保留 `sample_count/eligible_count/n_invalid`。
- **输出**: `tables/environment_nodes.csv`。

### 7.6 Factorial DAG 边 (`build_environment_edges`)
- **代码位置**: `factorial_dag.py:198-303`
- **用途**: 每条理论边一行, 值 = 条件增量 ΔR²(及 ΔRMSE/ΔMAE/ΔPearson/ΔSpearman)。
- **聚合与加权(重点)**:
  - 同一 `(split,cell,model)` 内按 **`random_seed` 配对**: 只保留两侧都有效的同 seed(`:220-236`), 重复 seed 记 `duplicate_seed` 并丢弃;
  - 边的 `parent_r2/child_r2/...` 与各 `delta_*` 都是**配对 seed 的算术平均**(`:277-292`);
  - `n_paired` 记录配对数;
  - 若两侧 `delta_r2` 与 `delta_rmse` **同向**, 标 `METRIC_INCONSISTENCY` warning, **但边保留**(`:268-274`);
  - CI 不在此计算, 初始写 `CI_UNAVAILABLE`/`not_run`(`:275,293-296`), 再由 `merge_edge_ci` `:306-334` 用 `environment_bootstrap.csv` 左连接合入。
- **输出**: `tables/environment_edges.csv`。
- **产物存在性**: 已存在(2651 数据行, 含 CI 列)。

### 7.7 Ablation 视图 (`build_ablation_edges`)
- **位置**: `factorial_dag.py:357-381`
- **规则**: `ΔR²_ablation = R²(S) − R²(S∖{e}) = −ΔR²_{e|S∖{e}}`(`:376-377`); 直接取反, **无再平均**。产物 `tables/environment_ablation.csv` 已存在。

### 7.8 交互聚合 (`build_environment_interactions`)
- **位置**: `factorial_dag.py:384-406`
- **聚合与加权**: 先 `compute_pair_interactions` 得每 seed 的 `interaction_r2`; 再按 `(split,cell,model,factor_a,factor_b)` 对 seed 取 **算术平均**, 同时 `n_seeds=size`、`n_with_b/n_without_b=mean`(`:398-404`)。产物 `tables/environment_interactions.csv` 已存在。

### 7.9 DAG 完整性报告 (`build_dag_report`) 与 md
- **位置**: `factorial_dag.py:412-441`, md 章节 `:444-508`, 落盘 `:547-599`。
- **内容**: 每个 group 的 `theoretical_nodes=16` / `theoretical_edges=32`、`valid/unavailable` 计数、`METRIC_INCONSISTENCY` 计数、`invalid_experiments`、缺失组合名。产物 `environment_dag_report.csv`、`environment_dag_report.md`、`summary/03_environment_effects.md` 的 marker 章节均已存在。
- **CI 表查找** (`load_edge_ci`, `:337-351`): 依次尝试 `environment_bootstrap.csv` / `environment_edges_bootstrap.csv` / `bootstrap_environment.csv`。

---

## 8. 重要性 / 异常 / QC (其余指定文件)

### 8.1 证据强度分级 (`evidence_strength`) — `analyse/importance_metrics.py`
- **代码位置**: `PRIMARY_METRICS` `importance_metrics.py:42-63`; `evidence_strength` `:100-146`; `passes_filter` `:149-167`; `normalize_within_context` `:170-184`。
- **用途**: 为 Importance–ΔR² 图给每个 `(model, factor, context)` 一个证据档位与原因。
- **输入**: 每模型主指标 + 稳健性(SNR)+ 统计(FDR): linear→`Linear_Coefficient`/`FDR`; xgboost→`TreeSHAP`/`SHAP_SNR`; mlp→`MLP_IG`/`IG_SNR`; cnn→`CNN_IG`/`ISM_SNR`; transformer→禁用(`:42-63`)。
- **关键超参**: `min_effect_size=0.005`, `snr_strong/moderate/weak=2.5/1.8/1.2`, `fdr_strong/moderate/weak=0.001/0.01/0.05`(默认值即 `config` 值)。
- **判定**:
  - linear: 按 FDR 分档(严格 `<`), 无 FDR → `unavailable`(`:123-133`);
  - 非线性: 无 SNR → `unavailable`; `|importance| < 0.005` → `below min effect`; 再按 SNR 分档(`:135-146`)。
- **聚合与加权**: 无加权, 不做综合分(注释明确禁止 `significance_score`, `:12`); 归一化是**同 `(model, split_type, cell_line)` 内按 factor 求和做占比**(`normalize_within_context`), 即"相对贡献份额", 非平均。
- **输出**: 合入 `tables/importance_vs_delta_r2.csv` 的 `evidence_strength/evidence_tier` 等列。
- **产物存在性**: 已存在(180 数据行)。

### 8.2 Importance–ΔR² 组装 (`analyse/visualization/importance_delta.py`)
- **代码位置**: `scan_factor_importance` `:103-171`; `factor_delta_r2` `:177-209`; `build_importance_delta_table` `:215-327`; `merge_evidence_columns` `:428-464`; 主入口 `run_importance_delta_analysis` `:637`。
- **输入**: 各实验目录的 importance CSV(`xgb_feature_importance.csv` 等, 见 `IMPORTANCE_FILES`)+ `*info*.txt` 元数据; ΔR² 侧复用 `environment_conditional_delta_r2.csv`。
- **聚合与加权(重点)**:
  - importance 侧: 对某环境 factor 的 23 个位点**先取 `|primary|` 再求和**(`:139-158`, `importance_value = vals.sum()`), `robustness_value = mean(SNR)`, `statistical_value = min(FDR)`(**取最小 FDR, 非平均**);
  - 再按 `(model, split_type, cell_line, feature)` **跨 environment 上下文取算术平均**(`:164-170`), `n_importance_contexts` 记上下文数;
  - ΔR² 侧: 剔除 `|R2| > 10.0` 的实验后, 复用条件增量汇总, 再按 `(model, split, cell, feature)` 对背景取均值、`n_paired` **求和**(`:202-206`);
  - CI 列 `delta_r2_ci_low/high` 恒为 `NaN`(注释: bootstrap runner 未接通, 不伪造, `:285-286`);
  - evidence_tier / coverage / permutation_fdr 直接 **从 `evidence_matrix.csv` 合入复用, 不重算**(`merge_evidence_columns`, `:428-464`);
  - 归一化: `normalized_importance` = 该 factor 在同 `(model, split, cell)` 内的重要性占比。
- **输出**: `tables/importance_vs_delta_r2.csv`, `summary/importance_delta_r2_summary.json`, `summary/07_importance_vs_delta_r2.md`, `summary/importance_metric_selection.md`, `figures/07_evidence/*`。
- **产物存在性**: 全部已存在(见 `results/batch_20260909_full/summary/`)。

### 8.3 异常检测 (`analyse/anomaly_treatment.py`)
- **位置**: `aggregate_metrics` `:120-137`; `detect_experiment_level_anomalies` `:144-208`; `detect_data_level_anomalies` `:215-278`; `aggregate_data_anomalies` `:281-299`; 报告 `:312-400`。
- **用途**: 两级异常检测(实验级指标矛盾 + 数据级线性系数爆炸)。
- **输入**: 优先 `summary/metrics_tables/all_experiments.csv`, 缺失回退扫描实验目录(`:92-117`); 数据级扫 `**/*weights*.csv` / `**/linear*coefficient*.csv`。
- **关键超参**: `coef_threshold=10.0`, `sign_tol=1e-6`(`:35-36`)。
- **聚合与加权**:
  - `aggregate_metrics`: 按 `(split_type, cell_line, model, environment)` 对 `R2/MAE/RMSE/MSE` 取 **算术平均**(多 seed 平均, `:135-136`);
  - 实验级规则: 相对同 `(split, cell_line, model)` 的 `sequence` 基线算 `delta_R2/delta_RMSE`, **同号**即标异常(`:185-193`)——注意此处基线 map 的 key **不含 seed**, 与其它模块的同 seed 配对原则不一致;
  - 数据级聚合: 按 `(cell_line, environment)` 计 `anomaly_count` 与 `max|weight|`(**取最大绝对值**), 例举前 3 个 `|weight|` 最大特征(`:285-297`)。
- **输出**: `summary/anomaly_report.md`(独立脚本入口 `run_anomaly_treatment`, `:407`)。
- **产物存在性**: 已存在 — `results/batch_20260909_full/summary/anomaly_report.md`, 以及 pipeline 侧的 `summary/tables/anomaly_report.csv`、`summary/08_anomaly_report.md`。

### 8.4 指标一致性标记 (`analyse/data/validation.py`)
- **位置**: `metric_consistency_flags` `:14-26`; `validate_metric_consistency` `:29-63`。
- **规则**: 同一 `(split_type, cell_line, model, random_seed)` 的 `sequence` 基线下, `ΔR²` 与 `ΔRMSE` 同号 → `metric_inconsistency_same_increase/same_decrease`(`tol=1e-9`); **只标记不删除**。
- **关键差异**: 这里**显式带 `random_seed`**(`:38-39`), 与 §8.3 的口径不同。
- **产物存在性**: `summary/tables/metric_inconsistency.csv` 已存在。

### 8.5 预测性能汇总 (`analyse/prediction.py`)
- **位置**: `performance_by_model_split` `:11-21`; `loco_performance` `:24-35`。
- **输入**: 统一实验表的 `R2,MAE,RMSE,Pearson,Spearman`。
- **聚合与加权**: 按 `(model, split_type)` 对每个 metric 给 `mean` 与 `std`(pandas 默认**样本标准差 ddof=1**)并合并实验数 `n_experiments`; LOCO 表筛 `split_type=="all"` 后按 `(model, cell_line)` 取 **均值**。无 n 加权。
- **产物存在性**: `tables/prediction_summary.csv`、`tables/loco_performance.csv` 已存在。

### 8.6 数据质控 (`analyse/data_QC.py`)
- **KDE 带宽 CV 选择** (`_cv_bandwidth`, `:157-196`): 高斯核, `GridSearchCV` + `KFold(5 折, shuffle=True)`; 网格 24 点在**对数空间** `h ∈ [0.05σ, 1.5σ]`; 样本 > `cv_subsample=2000` 时无放回子抽样(seed=42); 常数向量用 `max(1e-6, 0.5|mean|)`。
- **KDE 曲线** (`_kde_values`, `:199-210`): 400 点, 边界 pad 15%。
- **目标效率 KDE** (`kde_target_efficiency`, `:522-577`): 全体与每 cell line 各自选带宽; 记录 `skewness`/`kurtosis`(scipy.stats)/`mean`/`std`(ddof=0); 样本 `<3` 不做。
- **GC 含量** (`profile_gc_content`, `:658-712`): 逐序列 `(G+C)/len×100`, 同样 CV 带宽 KDE; `recommend_gc_as_feature` 标记。
- **离群提示** (`_outlier_reason_hints`, `:348-368`): `|y − mean| > 3σ` 或 `y ∉ [0,1]` → `extreme_target_y`; GC 同理 `abnormal_gc`; 否则 `multivariate_anomaly`。
- **IsolationForest** (`detect_outliers_iforest`, `:1099-1202`): 展平 23×(4 碱基 one-hot) + 表观逐位点; **中位数填充 → `StandardScaler` → IsolationForest(contamination=0.01, random_state=42, n_jobs=-1)**; 记录 `anomaly_score`(decision_function)、每 cell line 计数、离群/全体平均效率差。
- **默认常量**: `DEFAULT_CV_FOLDS=5`, `DEFAULT_CV_SUBSAMPLE=2000`, `DEFAULT_CONTAMINATION=0.01`, `DEFAULT_RANDOM_STATE=42`(`:57-60`)。
- **产物存在性**: 已存在 — `workspace/qc_sessions/qc_20260912_203603/qc_summary.json`、`outliers_detailed_report.csv`、`quality_report.md`、`gc_content_kde.png`、`target_efficiency_kde.png`。

### 8.7 结果收集侧统计 (`analyse/collect_results.py`) `[独立脚本, 非 analyse.pipeline 路径]`
- **位置**: `calculate_delta_R2` `:217-244`; `create_mixed_result` `:291-309`; `create_baseline` `:360-385`; `filter_valid` `:176-179`; `build_result_dataframe` `:247-270`。
- **用途**: 从各实验目录 `*_info.txt`/`*_metrics.json` 收集指标, 生成基线/结果表。
- **聚合与加权(重点)**:
  - `filter_valid`: 剔除 `R2` NaN 或 `|R2|>10` 或 `MAE>10` 或 `RMSE>10`(`:177-179`);
  - `calculate_delta_R2`: baseline map 的 key 是 `(split_type, cell_line, model)`, **不含 random_seed**(`:221-243`)→ mixed 多 seed 时后写覆盖前值, 存在跨 seed 配对风险(与 §7.1/§8.4 的"绝不跨 seed"原则冲突)。是否有意 **未确认**;
  - `create_mixed_result`: 按 `(model, environment)` 对 10 个指标列取 **算术平均**(`:303`), 并对 mixed 的 4 个 seed 求平均(`:374` 注释);
  - `create_baseline`: 非 mixed 行原样保留, mixed 行按 `(model, split_type)` 取均值并置 `cell_line="none"`(`:375-380`)。
- **输出**: `summary/metrics_tables/all_experiments.csv`、`single_cell_line_result.csv`、`all_cell_line_result.csv`、`mixed_cell_line_result.csv`、`baseline.csv`。
- **产物存在性**: 全部已存在 — `results/batch_20260909_full/summary/metrics_tables/`。

---

## 9. Sequence motif 统计 (因 config 的 FDR family 明确包含, 一并盘点)

### 9.1 Seqlet 提取的"分位阈值 + 局部连续"
- **位置**: `analyse/sequence/motif/core.py:205-254`(窗口 `_run_windows` ~`:180-202`), 对比度矩阵 `_contrast_matrix` 见 `:128-149` 附近。
- **规则**: 位置级 attribution **specificity**(当前碱基 attribution − 该位置其它碱基均值)的 `attribution_quantile=0.90` 与 `continuity_quantile=0.75` 双阈值; 至少 `continuity_min_positions=2` 个连续位置达标; 每样本最多 `max_seqlets_per_sample=2`; motif 长度 `min_length=4`..`max_length=12`(`config.py:101-113`)。阈值作用在**位置级峰值**, 窗口均值仅用于排序/限流(`:232-234`)。
- **聚合**: 每窗口分数 = 窗口内分数**算术平均**(`:194`); 同 `(start,end)` 保留最高分(`:198-200`)。

### 9.2 Motif consensus / 支持度
- **位置**: `core.py:416-447`(consensus 记录), 相似度 `_similarity_to_codes` `:276-284`。
- **聚合与加权(重点)**:
  - `support_count` = 支持该 consensus 的 **seqlet 实例数**; `sample_support` = 去重样本数; `cellline_support` = 支持 cell line 数;
  - `attribution_snr = mean(score) / (std(score, ddof=1) + 1e-12)`(仅当实例数 >1, `:443-445`)→ 跨实例的 **SNR = 均值/样本标准差**;
  - `mean_effect` = carrier 组 measured efficacy 均值 − background 均值(`:409`)——**方向来自实测效率对比, 不是 attribution 符号**, `direction_source` 显式记录(`:411`);
  - `position_mean` = seqlet 起点算术平均; `position_std` = 样本标准差(ddof=1)(`:435-436`);
  - motif 聚类阈值 `similarity_threshold=0.90`, `merge_similarity=0.95`(`config.py:109-110`)。
- **产物存在性**: `tables/motif_candidates.csv`(596 数据行; `seed_support` 列为空→`unavailable`, 原因见 `motif/pipeline.py:256-259`「attribution_summary 不含 random_seed」)。

### 9.3 Motif Fisher 精确检验 + BH-FDR
- **位置**: `core.py:462-506`(`enrichment_for_motif`), `:509-516`(`apply_enrichment_fdr`)。
- **输入**: 各 cell line 的 `sgRNA` 与 `efficacy`; foreground = `efficacy >= quantile(0.67)`(每 cell line 内取分位, `:479`), background = 全部有 efficacy 的序列。
- **检验**: `scipy.stats.fisher_exact([[fg_hit, fg_miss],[bg_hit,bg_miss]], alternative="greater")`(`:499-500`); 同时给 `effect = fg_rate − bg_rate`、`enrichment = fg_rate/bg_rate`、`odds_ratio=(a·d)/(b·c)`。
- **聚合与加权(重点)**: 计数在**所有 cell line 上求和**(`:482-485`)——即在 cell-line 层做 **pooled 2×2 表**, 不按 cell line 平均; foreground 阈值却是**每个 cell line 内部**的分位。最小 carrier 门槛 `enrichment_min_carriers=5`(`config.py:131`)。
- **FDR**: 只在 `motif_enrichment` 一个 family 内做 BH(`:509-516`), 阈值 `enrichment_fdr=0.05`(`config.py:132`)。
- **产物存在性**: `tables/motif_enrichment.csv`(596 数据行, 列 `effect,enrichment,odds_ratio,p_value,FDR,fdr_family,status,reason`)。

### 9.4 Motif evidence 分级
- **位置**: `core.py:522-545`(`stability_label`), `motif/pipeline.py:335-397`(`motif_evidence_rows`)。
- **规则**: 复用 `classify_evidence_tier`, `coverage = 支持的 model family 数`(当前仅 CNN, `:338-348`); `statistical = FDR < 0.05`; `strong = statistical or (|mean_effect| >= 0.01 and variants >= 2)`(`:357-361`); `effect_direction is None` 的 Tier1 降为 Tier3(`:366-367`)。
- **stability_label**: `FDR < 0.05 且 variants>=2 且 cells>=2` → Strong motif evidence; variants>=2 且 cells>=2 → Moderate; variants>=2 → Model-specific; `support_count>=30` → Exploratory; 否则 Inconclusive(`:535-545`)。
- **产物存在性**: `tables/motif_evidence.csv`、`motif_evidence` 行并入 `evidence_matrix.csv`。

---

## 10. 训练侧线性统计 (被 analyse 层只读使用)

### 10.1 OLS SE / t / 双尾 p / BH-FDR
- **代码位置**: `src/linear_regression/linear_regression.py:190-242`
- **输入**: 训练集设计矩阵 `X_bias` 与 `y_train`。
- **方法**: 权重用 Moore–Penrose 伪逆(`pinv`, rcond=`self.pinv_rcond`); `dof = max(1, n_samples − rank)`; `MSE_resid = SSR/dof`; `Var(w_i) = MSE·Σ_j X_pinv[i,j]²`(下限 1e-15); `SE=√Var`; `t = w/SE`; 双尾 `p = 2(1 − t.cdf(|t|, dof))`; BH-FDR 手写实现(`:219-232`); 显著性符号 `***/**/*/.` 对应 `p_adj < 0.001/0.01/0.05/0.1`(`:236-240`)。
- **聚合与加权**: 逐权重(逐特征)计算, 无加权。
- **输出**: 实验目录 `*_weights.csv` / `*_feature_importance.csv` 的 `Linear_Coefficient, SE, t_stat, p_value, FDR` 白名单列(`:535-562`; 白名单定义在 `analyse/importance_extraction.py:135`)。
- **产物存在性**: 已存在 — `results/batch_20260909_full/summary/feature_importance/linear_coefficiency.md`、`key_regulatory_biomarkers.csv`。

### 10.2 训练侧重要性的均值聚合
- **位置**: `analyse/importance_extraction.py:744-784`(逐实验逐特征), `:787-855`(`generate_key_regulatory_biomarkers`)。
- **聚合与加权**: mixed split 的多实验按 `(split, cell, environment, model_key, canonical_feature)` 对 `sig_score/contribution_val/abs_contrib/snr/p_val/fdr` 取 **算术平均**(`:808-816`), 再把平均 `sig_score` 映射回星级(`:817-823`); 非 mixed 行原样保留。线性→FDR 星级, 非线性→SNR 星级(`:754-761`)。

### 10.3 归因 importance 跨 context 平均
- **位置**: `analyse/attribution/summary.py:9-26`
- **聚合**: 按 `(model, method, feature)` 对 `|importance|` 与 `importance` 取**算术平均**, 记 `n_contexts`; 每个 `(model,method)` 取 `mean_abs_importance` **top-10**(**非平均的"取最优"规则**)。
- **产物存在性**: `summary/reports/04_sequence_motifs.md` 已存在。

---

## 11. `docs/paper_analysis/` 与 `paper/make_assets.py` 的统计量

### 11.1 `position18_ism_audit.py` — 描述统计 + 正态近似 CI
- **位置**: `docs/paper_analysis/position18_ism_audit.py:38-88`(采集), `:91-107`(`describe`), `:110-185`(聚合)。
- **输入**: 每个 CNN 实验目录的 `cnn_feature_importance.csv`(列 `Feature, Position, Channel, CNN_IG, CNN_ISM, ISM_SNR`)+ `*info*.txt`; 审计对象为 `Position == 17`(0-based, 即 1-based 18)。
- **统计量**: `n, mean, median, std(ddof=1), min, max, mean_ism_snr, mean_cnn_ig`, 以及 **95% CI = mean ± 1.96·SE**(SE = sd/√n)——**正态近似, 不是 bootstrap**; 另有 `fraction_channel_is_top`、`rank_mean/median`、`fraction_rank_le3`(rank 在 `experiment × channel` 内对 23 个位置**取最大排名**, `:117-118`)。
- **聚合与加权(重点)**: 行 = `(kernel × cell_line × channel)` 或 `(ALL × cell_line × channel)` 或 `(kernel × ALL × channel)` 或 `(ALL × ALL × channel)`;
  - 该审计**不做假设检验、不做多重校正**(文件头 `:10-11` 与 md `:277-281` 明确声明);
  - 所有统计量在"位置18 × 通道"的**池化实例**上计算; 通道之间不互相平均; kernel/cell_line 只作为**分组维度**分别报告, 不跨维平均;
  - `pooled` 标签用于无 cell_line 的混合训练运行(`:112-116`)。
- **输出**: `results/analysis/position18_ISM_audit.csv`、`position18_ISM_raw_long.csv`、`ISM_all_positions_long.csv`、`position18_ISM_audit.md`。
- **产物存在性**: 全部已存在(见 `results/analysis/`)。

### 11.2 `position18_signed_substitution_ism.py` — 有符号替换 + Bootstrap CI
- **位置**: `docs/paper_analysis/position18_signed_substitution_ism.py:210-222`(`bootstrap_ci`), `:225-244`(`describe`), `:248-320`(主流程), `:435-446`(稳定性表)。
- **用途**: 对 1-based 位置 18 为 C 的 guide 做**真正的碱基替换** `C>A/C>G/C>T`, 计算 `Δ = f(mutant) − f(WT)`, 给 percentile bootstrap CI。
- **输入**: 已训练模型(7 个 pooled `results/batch_20260909_full/summary/ultimate/*`, 12 个 cell-line-specific CNN `models/batch_20260909_full/single_<cell>_cnn_sequence_kernel_<k>/`)+ `data/proceeded_data` 的序列与标签(经 `predict.py::_load_mixed_subset`); 对照用 `docs/paper_analysis/position18_efficacy_by_base.csv`。
- **关键超参**: `N_BOOT=10_000`, `SEED=42`, `DEVICE="cpu"`, 百分位 `[2.5, 97.5]`(`:58-60`, `:222`); 每条 CI 在**该模型该替换的样本子集**上重采样。
- **聚合与加权(重点)**:
  - 对每个模型 × 替换给 `mean/median/std(ddof=1)/boot CI/frac_positive/frac_negative/ci_excludes_zero`, 以及 clipped 变体的稳健列(`:232-244`);
  - pooled 模型额外按 cell line 分层重复计算(`:288-296`), **不做跨 cell line 平均**;
  - `stability_table`: 对同一替换, 统计所有 `(model × kernel × cell line)` 配置中与多数方向同号的**占比**(`:435-446`);
  - 与实测对比 (`measured_comparison`, `:379-410`): 对每个 `(替换, cell line)`, **模型侧取该 cell line 上所有 pooled 模型 `mean_delta` 的均值**(`:395`)与实测 `C − X` 比较, 统计 agree 比例(仅 4 个 cell line, 明确声明为描述性而非检验, `:383`)。
- **输出**: `results/analysis/position18_signed_substitution_ISM.csv`、`..._per_sample.csv`、`..._vs_measured.csv`、`..._ISM.md`、`paper/figures/position18_signed_substitution.png`。
- **产物存在性**: 全部已存在。

### 11.3 `paper/make_assets.py` — 论文图表的聚合口径
- **`factor_ci`** (`:356-377`): 独立重算 factor 级 CI, 与 §4.2 同口径——先剔除 `|ΔR²| >= 10`, **按 model 求均值(等权)**, 再对模型做 percentile bootstrap; 超参 `n_iter=2000`、`seed=2024`、百分位 `[2.5, 97.5]`; `<3` 个模型 → unavailable。产物 `docs/paper_analysis/factor_level_ci.csv`(已存在)。
- **边级 bootstrap 聚合** (`:702-723`): 读 `bootstrap_results.csv`(只取 `metric=="R2"`、`status=="ok"`), 按边 key(不含 seed)聚合:
  - `estimate = mean(estimate)`(**算术平均**);
  - `ci_low = min(ci_low)`、`ci_high = max(ci_high)` → **"保守并集"区间, 不是对 seed 平均后的 CI**;
  - `excl_all = all(excl)`、`n_seeds = size`;
  - 再按 `added_environment` 汇总: `n_edges`、`n_excl0 = sum(true)`、`mean_estimate = mean`、`n_seeds_total = sum`。
  - 产物 `docs/paper_analysis/bootstrap_edge_by_factor.csv`(已存在; 4 行 factor)。
- **Table 1/2** (`:463-508`): 数据集表给 `mean / std(ddof=1) / median / GC 比例`; 预测表对 `R2_mean`(先由 `prediction_summary.csv` 按 model×split 得到)再取 `median/mean/std(ddof=1)`, 并统计 `|R2_mean|>=10` 的 `diverged` 数。
- **Figure 2/3/4/5/6** 中的聚合: 如 `figure3` 对 `st.model`×factor 取 `mean`(`:120`), `figure4` 对 region×model 取 `mean`(`:197`), `figure5` 对 region 内位置取 `mean`(`:274`), `figure6` 直接用 `environment_by_cellline.csv` 的 `mean_dR2` 透视。均为算术平均。
- **产物存在性**: `paper/tables/tab1_dataset.tex`…`tabS2_sequence.tex`、`paper/figures/fig1..fig7/figS1` 均已存在。

### 11.4 `paper/make_position18_summary.py`
- **位置**: `paper/make_position18_summary.py:42-80`(读取), `:74-80`(`region_means`)。
- **聚合**: 位置谱按 region 取 `prof.loc[lo:hi, m].mean()`(**区间算术平均**); C−A 差 = 两碱基 `mean_efficacy` 之差(`:56`); Spearman 与 top-3 overlap 直接取自 `cross_model_position_consistency.csv`(不重算)。
- **产物存在性**: `paper/position18_summary.tex`、`paper/position18_candidate_summary.pdf`、`paper/figures/position18_attribution.png`、`position18_base_effect.png` 均已存在。

---

## 12. Evidence Tier / 证据分级 判定规则与阈值(汇总)

### 12.1 实际生效的 Tier 判定(environment 行)
来源 `analyse/evidence/integration.py:43-65` + `:90-191`, 阈值 `analyse/config.py:30-38`:

| 顺序 | 条件 | 结果 |
| :-- | :-- | :-- |
| 1 | `conflicting_direction` 或 `ci_crosses_zero == True` | `Inconclusive` |
| 1b | (environment 专有) cell_line 众数标签 == `Context-conflicting` | 直接 `Inconclusive`(`integration.py:181-182`) |
| 2 | supporting ≥ **2** 且 (concordance 为 None 或 ≥ **0.80**) 且 strong | `Tier 1: Strong convergent evidence` |
| 3 | supporting ≥ **2** | `Tier 2: Moderate convergent evidence` |
| 4 | supporting == 1 且 strong | `Tier 3: Model-specific / exploratory evidence` |
| 5 | applicable == 0 | `No current evidence` |
| 6 | 其它 | `Inconclusive` |

其中:
- `supporting` = 与 `overall`(有限模型效应均值)同号的模型数(`:136-138`);
- `strong = any(|effect| ≥ 0.01) 或 permutation FDR < 0.05`(`:132-133`, `:177-179`);
- CI 参与判定需 `bootstrap_status=="ok"` 且 `n_bootstrap ≥ 200`(`config.evidence.min_bootstrap_iterations`, `:155-156`);
- 进入矩阵前先剔除 `|main_r2_delta| ≥ 10.0`(`:118-120`)。

### 12.2 Motif 行
`motif/pipeline.py:335-397`: 复用同一 `classify_evidence_tier`, 但 `coverage = model family 数`, `concordance=None`, `ci_crosses_zero=None`; `strong = FDR<0.05 或 (|mean_effect| ≥ 0.01 且 kernel variants ≥ 2)`; 无方向的 Tier1 降级为 Tier3。

### 12.3 `evidence/rules.py` 的分级(仅单测)
- 统计: `FDR < 0.001 / 0.01 / 0.05` → Strong/Moderate/Weak statistical(`fdr_nominal=0.10` 定义了但未用);
- 归因: `|effect| ≥ 0.005` 且 `SNR ≥ 2.5 / 1.8 / 1.2` → Strong/Moderate/Weak attribution;
- 突变: `SNR ≥ 2.5` 且 `|Δmean| ≥ 0.005` → Strong mutation effect;
- 全部为严格 `<` / `>=` 比较, 阈值取自 `config.attribution` / `config.statistical`。

### 12.4 Importance–ΔR² 的 `evidence_strength`
`analyse/importance_metrics.py:100-146`(与 12.3 同阈值): linear→FDR 分档; 非线性→先 `|importance| ≥ 0.005` 门槛, 再按 SNR `2.5/1.8/1.2` 分档; transformer 恒 `unavailable`。

---

## 13. 多重比较校正: 方法与作用范围

- **方法**: 只有 **Benjamini–Hochberg FDR** 一种; 两处实现:
  1. `analyse/stats/multiple_testing.py:13-35`(`bh_fdr`, q 值单调非降);
  2. `src/linear_regression/linear_regression.py:219-232`(训练侧同算法, 写 `p_adj_fdr`/`FDR`)。
- **作用范围(按 family 隔离)**:
  - `permutation_results.csv`: 按 `family_key` 分组做 BH(`tasks.py:401-421`), 代码实际写入的 family 前缀有 `environment_edge|`、`environment_main|`、`environment_interaction|`, 每个再以 `<split>|<cell>|<model>` 细分(`tasks.py:265,312,380-381`);
  - `motif_enrichment` 单一 family(`motif/core.py:509-516`);
  - 线性回归: 每次训练内对**该模型全部特征权重**的 p 值做 BH(训练侧, family = 单次实验的特征集)。
- **不做校正的部分**: `anova_results.csv` 无 `FDR` 列; `bootstrap_results.csv` 的 CI 不做多重校正; `position18_ism_audit.py` 明确声明不做检验/校正; `position18_signed_substitution_ism.py` 只给每配置各自的 CI, 无 multiplicity 校正。
- **family 规模门槛**: `min_family_size=2`(`config.py:149`); 不足 → `fdr_status="not_applicable (family size ...)"`, **不伪造 FDR**。
- **禁止项**(代码注释明示): SNR / SHAP / IG / ISM / Attention 的原始值不得进入 p-value 或 FDR(`schemas.py:8-9`, `integration.py:107-108`, `tasks.py:7`)。

---

## 14. 随机种子 / 重采样次数 / 置信水平 的实际取值

| 参数 | 值 | 出处 |
| :--- | :--- | :--- |
| bootstrap 迭代数 | **2000** | `config.py:174`; `bootstrap.py:55`; `make_assets.py:356` |
| bootstrap 随机种子 | **2024** | `config.py:175`; `bootstrap.py:56`; `hypothesis_tests.py:30/99` |
| bootstrap 置信水平 | **alpha=0.05** → 95% percentile 区间 | `config.py:176`; `bootstrap.py:57` |
| permutation 次数 | **1000** | `config.py:177`; `hypothesis_tests.py:29` |
| permutation 随机种子 | **2024** | 同上(`cfg.bootstrap_seed`) |
| ANOVA effect CI 迭代数 | **400** | `config.py:78`(`anova.ci_iterations`) |
| ANOVA 随机种子 | **2024** | `tasks.py:464` |
| 全局 random_seed | **42** | `config.py:178` |
| evidence CI 最小迭代门槛 | **200** | `config.py:65` |
| QC KDE CV | **5 折**, 网格 **24** 点, 子抽样 **2000**, seed **42** | `data_QC.py:57-60,157-196` |
| QC IsolationForest | contamination **0.01**, random_state **42** | `data_QC.py:59-60,1139-1143` |
| QC 离群提示阈值 | **3σ** | `data_QC.py:360,364` |
| 数值发散阈值 | **|metric| > 10.0** | `config.py:38`; `factorial_dag.py:125` |
| Position-18 有符号 ISM bootstrap | **10000** 次, seed **42**, 百分位 2.5/97.5 | `position18_signed_substitution_ism.py:58-59,222` |
| Position-18 ISM 审计 CI | 正态近似 **mean ± 1.96·SE** | `position18_ism_audit.py:101-102` |
| 论文 factor 级 CI | **2000** 次, seed **2024**, 百分位 2.5/97.5 | `make_assets.py:356,373-374` |
| 图示抖动随机种子 | **42**(`visualization.py:291`)、**0**(`make_assets.py:83`) | 仅绘图抖动 |
| QC demo 合成数据 | **7** | `data_QC.py:1683`(仅 demo) |
| 单测中的种子 | 0,1,2,3,4,5,6,7,8,9,11 等 | `analyse/tests/*`(不影响产物) |

**未发现** 任何使用 `alpha` 非 0.05 的生产路径; **未发现** 除 BH 以外的多重校正方法(Bonferroni/Holm 等); **未发现** 非参数检验(Wilcoxon/Mann-Whitney/Kruskal)在产线代码中。

---

## 15. 聚合与加权规则专题(重点)

| 统计量 | 聚合维度 | 规则 | 是否按 n 加权 | 是否有"取最优/取最大" |
| :--- | :--- | :--- | :--- | :--- |
| 环境主效应 `main_r2_delta` | (split,cell,model,env) | 先跨背景均值, 再跨 seed 均值 | 否(背景/seed 等权) | 否 |
| 条件增量 `delta_r2_mean` | (split,cell,model,env,background) | 跨 seed 算术平均 | 否 | 否 |
| 成对交互 `interaction_r2` | (split,cell,model,a,b) | 每 seed 内(含b均值−不含b均值), 再跨 seed 均值 | 否 | 否 |
| DAG 节点 metric | (split,cell,model,组合) | 同组合全部有效实验算术平均 | 否 | 否 |
| DAG 边 Δmetric | (split,cell,model,组合对) | 同 seed 配对后再跨 seed 算术平均 | 否 | 否 |
| 边级 Bootstrap CI | (split,cell,model,seed,边) | 逐样本配对重采样, **不跨 seed 平均** | 否 | 否 |
| factor 级 CI | factor | **先按 model 均值, 再对 model bootstrap** | 否(模型等权) | 否 |
| cell-line 级 CI | (split,cell,factor) | 对模型等权 bootstrap 均值 | 否 | 否 |
| Evidence `overall_effect` | factor | 先按 model 均值(跨 split/cell), 再模型等权平均 | 否 | 否 |
| Evidence `direction_concordance` | factor | 多数方向占比(模型等权) | 否 | 否 |
| Evidence `permutation_p/fdr` | factor | 该 factor 所有行取 **min** | 否 | **是(取最小 p/FDR)** |
| Evidence `cell_line_consistency` | factor | 该 factor 的 `context_label` **众数** | 否 | **是(取众数)** |
| Evidence CI | factor | 只有 `n_bootstrap >= 200` 的 CI 才采信 | 否 | 否 |
| cell-line 异质性 | (split,model,factor) | `max|effect| / median|effect|` | 否 | **是(max 与 median 的比)** |
| cell-line majority/minority ratio | 同上 | cell line 等权计数比 | 否 | 否 |
| Importance factor 值 | (model,split,cell,factor) | 位点 `|importance|` **求和**, 再跨 environment 上下文算术平均 | 否 | 否 |
| Importance 归一化 | 同 (model,split,cell) | factor 值 / 该上下文全部 factor 值之和 | 否 | 否 |
| Importance 统计列 | (model,split,cell,factor) | 位点/上下文 FDR 取 **最小** | 否 | **是(取最小 FDR)** |
| 线性系数 SNR/显著性 | 逐特征 | SNR=mean/std; FDR 分档 | 否 | 否 |
| Motif `attribution_snr` | motif | 实例 `mean(score)/std(score,ddof=1)` | 否 | 否 |
| Motif enrichment | motif | **跨 cell line 合并 2×2 计数**(pooled), foreground 阈值按 cell line 内分位 | 否(计数合并) | 否 |
| Motif 稳定性 | motif | 支持 kernel variant / cell line **计数**; 无方向时降级 | 否 | 否 |
| 预测性能表 | (model,split) | mean + std(ddof=1) + n | 否 | 否 |
| mixed 结果表 | (model,environment) | 多 seed 算术平均 | 否 | 否 |
| 论文边级 CI | 边(跨 seed) | estimate=mean; ci_low=**min**; ci_high=**max**(保守并集) | 否 | **是(CI 取并集)** |
| 论文 factor CI | factor | 同 factor 级 CI 口径(模型等权 bootstrap) | 否 | 否 |

**没有发现**任何统计量按样本数 `n` 做加权平均; 所有跨实验/跨 seed/跨模型的汇总均为**等权算术平均**(少数为 min/max/众数/median 比值等非平均规则, 已在上表标出)。

---

## 16. 产物存在性核对表(实测)

| 统计工具 | 声明输出 | 实际存在路径 | 状态 |
| :--- | :--- | :--- | :--- |
| 边级配对 Bootstrap | `tables/bootstrap_results.csv` | `results/batch_20260909_full/summary/tables/bootstrap_results.csv`(7770 行) | ✅ |
| factor 级 CI | `tables/bootstrap_main_effects.csv` | 同目录(4 行) | ✅ |
| cell-line 级 CI | `tables/bootstrap_cellline_effects.csv` | 同目录(36 行) | ✅ |
| BH-FDR / 置换 | `tables/permutation_results.csv` | 同目录(3444 行, 含 `FDR/fdr_family`) | ✅ |
| ANOVA | `tables/anova_results.csv` | 同目录(94 行) | ✅ |
| Evidence 整合 | `tables/evidence_matrix.csv` | 同目录(600 行) | ✅ |
| cell-line 一致性 | `tables/cellline_effects.csv` | 同目录(84 行) | ✅ |
| 主效应 / 条件增量 | `environment_main_effects.csv` / `environment_conditional_delta_r2.csv` | 同目录(252 / 2016 行) | ✅ |
| Factorial DAG | `environment_nodes.csv` / `environment_edges.csv` / `environment_ablation.csv` / `environment_interactions.csv` / `environment_dag_report.csv` | 同目录(全部存在) | ✅ |
| Importance–ΔR² | `tables/importance_vs_delta_r2.csv` + `summary/importance_delta_r2_summary.json` + md | 同目录(180 行; json/md 存在) | ✅ |
| 指标一致性 | `tables/metric_inconsistency.csv` | 同目录 | ✅ |
| 预测性能 | `prediction_summary.csv` / `loco_performance.csv` | 同目录 | ✅ |
| Motif | `motif_candidates.csv` / `motif_instances.csv` / `motif_enrichment.csv` / `motif_consistency.csv` / `motif_evidence.csv` | 同目录(motif_candidates/motif_enrichment 各 596 数据行; motif_instances 172098 行) | ✅ |
| 异常报告 | `summary/anomaly_report.md` | `results/batch_20260909_full/summary/anomaly_report.md` + `summary/reports/08_anomaly_report.md` | ✅ |
| 结果收集 | `summary/metrics_tables/*.csv` | `results/batch_20260909_full/summary/metrics_tables/`(5 个 csv) | ✅ |
| 线性统计 | 实验目录特征重要性 | `results/batch_20260909_full/summary/feature_importance/key_regulatory_biomarkers.csv` 等 | ✅ |
| QC | `qc_summary.json` 等 | `workspace/qc_sessions/qc_20260912_203603/` | ✅ |
| Position-18 审计 | `results/analysis/position18_ISM_audit.csv` | `results/analysis/` | ✅ |
| Position-18 有符号 ISM | `results/analysis/position18_signed_substitution_ISM.csv` 等 | `results/analysis/`(4 个文件) | ✅ |
| 论文表格/图 | `paper/tables/*.tex` | `paper/tables/tab1..tab6, tabS1, tabS2` | ✅ |
| 论文 paper_analysis | `docs/paper_analysis/*.csv` | 全部 13 个 csv + `asset_summary.json` 存在 | ✅ |

---

## 17. 明确标注为"未确认"的事项

1. **`docs/paper_analysis/` 中多数 CSV 的生成脚本不在仓库内**。`paper/make_assets.py` 只**读取**下列文件, 不生成它们:
   `nucleotide_frequency_by_position.csv`、`position18_efficacy_by_base.csv`、`position18_attribution.csv`、
   `cross_model_position_consistency.csv`、`position_profile_by_model.csv`、`region_attribution.csv`、
   `cnn_ism_position_profile.csv`、`kernel_position_profile.csv`、`cnn_kernel_paired.csv`、
   `environment_cross_model.csv`、`environment_by_cellline.csv`。
   `docs/paper_analysis/README.md:1-5` 声称"所有文件由 `paper/make_assets.py` … 重新计算得到", 与代码事实**不一致**。
   仅 `factor_level_ci.csv`、`bootstrap_edge_by_factor.csv` 由 `make_assets.py` 生成(`:731-732`, `:723`)。
   全仓库 grep(排除 `.git`)未找到这些 CSV 的写入点 → **未确认**其确切超参(如 `cnn_kernel_paired` 的 bootstrap 次数/种子)。
   可从列结构推断但**未验证**的口径: `environment_cross_model.csv` 的 `n_models/mean_dR2/min/max/n_negative/n_positive/model_*` 看似"按模型先平均再跨模型汇总"; `environment_by_cellline.csv` 的 `mean_dR2,n` 看似"按 (factor, cell_line) 分组均值"; 均属推断。
2. `analyse/stats/bootstrap.py` 的 `bootstrap_difference_ci`、`bootstrap_paired_metric_ci`、`bootstrap_paired_metric_ci_fast` 与 `hypothesis_tests.anova_interface`、`evidence/rules.py` 的三个 `classify_*` **仅被单测使用**, 未进主流程(已逐处确认调用点)。
3. `config.FdrFamilyConfig.enabled_families`(`config.py:143-148`)的命名与代码实际写入的 `family_key` 前缀不一致, 且 `apply_fdr` 未使用该白名单; 是有意还是历史遗留 **未确认**。
4. `analyse/collect_results.py::calculate_delta_R2`(`:221-243`)的基线 key 不含 `random_seed`, 与 `incremental_effect.py`/`data/validation.py` 的"同 seed 配对"原则不同; 是否会造成 mixed 多 seed 的跨 seed 相减 **未确认**(代码未加保护)。
5. ANOVA 结果未做 FDR 校正(`anova_results.csv` 无 `FDR` 列), 是否有后续校正计划 **未确认**。
6. `docs/statistical_analysis_status.md` 中的具体数值(F=0.60/2.31/1.95/2.18 等)仅与产物行数核对一致, **未逐行复核**其统计数值本身。
7. `analyse/data_QC.py` 与 `collect_results.py`/`anomaly_treatment.py` 属于 GUI/独立脚本路径, 不在 `analyse/pipeline.py` 的 `executed` 任务清单内; 其"是否每个生产批次都实际运行" **未确认**。
