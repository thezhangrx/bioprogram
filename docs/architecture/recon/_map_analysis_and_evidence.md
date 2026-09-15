# 训练后分析 → 四维度结论 → 证据整合 全链路地图（只读勘察）

> ⚠️ **历史勘察快照（重构前）**：本文记录 2026-09-14 目录重构**之前**的结构，其中的路径名（`src/`、`analyse/`、`data/proceeded_data/`、`results/<batch>`）均为旧路径。
> 当前权威结构见 `README.md` 与 `docs/architecture/`；科学定义见 `docs/science/`。


> 勘察对象：仓库 `/home/zhang/bioprogram/Submit`（工作树，未做任何修改）。
> 目标批次：`results/batch_20260909_full`（1 344 runs）。
> 分析引擎入口：`analyse/pipeline.py::run_analysis`（`analyse/pipeline.py:78-555`）。
> 产物根：`results/batch_20260909_full/summary/{tables,summary,figures}`。
> 本文件中的所有数字均由本批次实际产物的 pandas 读取结果给出（2026-09-13 状态）。

---

## 0. 批次事实基线（后续所有"统计单位"都以它为准）

| 事实 | 值 | 证据 |
| :--- | :--- | :--- |
| run 数 | 1 344 | `tables/experiment_table.csv` 1 344 行；`pipeline.py:94-95` |
| 环境组合 | 2⁴ = 16（4 因子：ctcf/dnase/h3k4me3/rrbs） | `analyse/environment/incremental_effect.py:16`；`factorial_dag.py:35` |
| 模型配置 | 7（linear, xgboost, mlp, cnn k=3/5/7, transformer） | `tables/prediction_summary.csv` 21 行 = 7×3 split |
| 细胞系 | 4（hct116, hek293t, hela, hl60） | `experiment_table.csv` |
| split | 3（single / mixed / all），**`all` 与 `single` 数值完全相同（max abs diff = 0.0）** | 本批 `experiment_table` pivot 实测；`paper/sections/05_limitations.tex:6` 有记录 |
| seed | single/all = 42；mixed = 42/43/44/45 | `tables/environment_main_effects.csv` 的 `n_seeds`：all/single=1，mixed=4 |
| 序列样本 | 16 749（过滤非法碱基后） | `docs/paper_analysis/asset_summary.json`；`data/proceeded_data/<cell>_metadata.csv` |
| 归因行 | 331 200（`tables/attribution_summary.csv`） | 7 组 (model, method) |
| 分析表 | 27 个 CSV；293 张 PNG | `ls summary/tables/*.csv`、`find figures -name '*.png'` |

**任务状态**（`summary/analysis_status.json`、`summary/execution_log.json`）：17 个任务全部 `completed`（含 ANOVA、motif enrichment——因为本次运行用的是打开开关的 plan `summary/analysis_plan.json`，而非 `plans.py:110-111` 的 `default_plan()`，后者 `environment.anova=False`、`sequence.motif_enrichment=False`）。

---

## 1. Effect 类（"改变后差多少"）

### 1.1 条件增量 ΔR² —— `tables/environment_conditional_delta_r2.csv`

* **代码位置**
  * 原始配对：`analyse/environment/incremental_effect.py::compute_conditional_increments`（`:51-90`），分组键 `GROUP_COLS = [split_type, cell_line, model, random_seed]`（`:17`）。
  * 聚合落盘：`summarize_conditional`（`:93-106`）；pipeline 调用 `analyse/pipeline.py:175-184`。
  * 只接受**同背景子集 + 恰好新增 1 个因子**的 (S, S∪{e})，且要求同 key 唯一行，否则拒绝（`:63-75`）。
* **输入资产**：`tables/experiment_table.csv` 的 `model/split_type/cell_line/environment/random_seed/R2/MAE/RMSE`（`analyse/data/loaders.py`）。
* **输出资产**：`tables/environment_conditional_delta_r2.csv`（2 016 行 = 63 个 (split,cell,model) 组 × 32 条 lattice 边，跨 seed 求均值）。
* **统计单位**：一次"边 × seed"配对，聚合成 (split, cell_line, model, environment_added, background)；`n_paired` 记录跨 seed 配对数（mixed=4，all/single=1）。
* **回答**：在给定背景 S 下再加入因子 e，留出 R² 提升/下降多少（可正可负）。
* **不能回答**：不是显著性（无 p/CI 列）；不能跨 seed 配对；不能当作因子全局贡献（依赖背景 S）；`all` 与 `single` 重复计数。

### 1.2 因子主效应 —— `tables/environment_main_effects.csv`

* **代码位置**：`incremental_effect.py::compute_main_effects`（`:109-133`）；pipeline `analyse/pipeline.py:186-197`。
* **输入**：`compute_conditional_increments` 的长表（"跨 seed 后再次跨背景等权平均"，`:117-130`）。
* **输出**：`tables/environment_main_effects.csv`（252 行 = 63 组 × 4 因子），列 `main_r2_delta / main_mae_delta / main_rmse_delta / n_seeds / n_backgrounds_avg`。
* **统计单位**：模型配置（每行一个 (split, cell_line, model, factor)），背景与 seed 等权。
* **回答**：该环境因子在一切背景上的平均增量预测价值。
* **不能回答**：不是 CI/显著性；不能解释交互；不按样本量加权；`all`≡`single` 导致重复。

### 1.3 DAG 边 —— `tables/environment_edges.csv`

* **代码位置**：`analyse/environment/factorial_dag.py::build_environment_edges`（`:198-303`，32 条理论边逐条配对同 seed）→ `merge_edge_ci`（`:306-334`）→ 落盘 `write_factorial_dag_artifacts`（`:547-599`）；pipeline `analyse/pipeline.py:286-313`。
* **输入**：`experiment_table`（同 cohort）＋ `tables/environment_bootstrap.csv`（CI，`analyse/stats/tasks.py::edge_ci_table:529-540`）。
* **输出**：`tables/environment_edges.csv`（**2 651 行，但唯一 (split,cell,model,parent,child) 只有 2 016 个**）、`environment_nodes.csv`（1 008）、`environment_ablation.csv`（2 651）、`environment_dag_report.csv`（63）。
* **统计单位**：一条 directed edge = 一个 (split, cell_line, model, parent_combination, child_combination)。
* **回答**：单步加入某因子的条件增量、方向、CI 是否跨 0。
* **不能回答**：不是树（一个组合有多父节点，合法）；`METRIC_INCONSISTENCY` 只是 warning；CI 列对 mixed 组被 seed 复制放大（见 §7 不一致 #9）。

### 1.4 成对交互 —— `tables/environment_interactions.csv`

* **代码位置**：`factorial_dag.py::build_environment_interactions`（`:384-406`）→ `incremental_effect.py::compute_pair_interactions`（`:136-172`）。
* **输入**：条件增量长表。
* **输出**：`tables/environment_interactions.csv`（378 行 = 63×6 因子对），列 `interaction_r2 / n_seeds / n_with_b / n_without_b`。
* **统计单位**：因子对 (a,b) × (split,cell,model)。
* **回答**：加入 a 的增量是否依赖 b 是否存在。
* **不能回答**：只有 ΔR²、没有 p/CI（置换交互在 `permutation_results.csv` 另存）；不参与 Evidence Tier。

### 1.5 ANOVA —— `tables/anova_results.csv`（blocked factorial + per-group）

* **代码位置**：`analyse/stats/tasks.py::run_anova_tasks`（`:453-503`）＋ `_binary_factors`（`:444-450`）；核心 `analyse/stats/hypothesis_tests.py::factorial_anova`（`:244-370`，Type-II 边际 extra-sum-of-squares，`:317-329`）；pipeline `analyse/pipeline.py:251-270`。
* **输入**：`experiment_table` 的 `R2` × 4 个二值化环境因子（`_binary_factors:446-449`），block 因子 = model/cell_line/split_type（`config.py:101`）；剔除 |R²|≥10（`tasks.py:461-463`）。
* **输出**：`tables/anova_results.csv` 94 行：
  * `model_scope=blocked_factorial` 10 行（4 主效应 + 6 交互），`family_key=environment_anova|global`，`n_obs=1288`、`df_den=1265`；
  * `model_scope=per_group_additive_main` 84 行，28 `ok` / 56 `unavailable`（每 cell 只有 1 观测 → 设计饱和），族 `environment_anova_group|split|cell|model`（4 项/族）。
* **统计单位**：**一次实验的留出 R²**（不是样本）；blocked 设计把模型/细胞系/划分作为区组。
* **回答**：剥离区组方差后，因子主效应/成对交互的全局 F 检验。
* **不能回答**：不是"逐样本"推断；**没有 FDR 列**（`ANOVA_COLUMNS` `tasks.py:42-44`，`apply_fdr` 从不作用于它）；**不参与 Evidence Tier**。
* ⚠ 文档写 `n_obs=966`（`docs/statistical_analysis_status.md:79`），产物是 1 288。

### 1.6 Importance–ΔR² 二维表 —— `tables/importance_vs_delta_r2.csv`

* **代码位置**：`analyse/visualization/importance_delta.py::build_importance_delta_table`（`:215-327`）；ΔR² 侧 `factor_delta_r2`（`:177-209`，复用 conditional increment，剔除 |R²|>10）；importance 侧 `scan_factor_importance`（`:103-171`）；落盘 `run_importance_delta_analysis`（`:637-663`）；pipeline `analyse/pipeline.py:526-539`。
* **输入**
  * ΔR²：`experiment_table` → 条件增量 → 每 factor 跨背景均值；
  * importance：各实验目录的 `linear_regression_weights.csv / xgboost_feature_importance.csv / mlp_feature_importance.csv / cnn_feature_importance.csv / transformer_feature_importance.csv`（`IMPORTANCE_FILES:33-39`），主指标见 `analyse/importance_metrics.py::PRIMARY_METRICS:42-63`（linear `Linear_Coefficient`、xgb `TreeSHAP`、mlp `MLP_IG`、cnn `CNN_IG`、transformer 禁用）；factor 级 importance = 23 位点求和（`:139-158`）。
  * `tables/evidence_matrix.csv`（仅 merge `evidence_tier/coverage/...`，`merge_evidence_columns:428-464`）。
* **输出**：`tables/importance_vs_delta_r2.csv`（180 行 = 5 模型 × 36），`summary/07_importance_vs_delta_r2.md`、`summary/importance_vs_delta_r2.md`（别名）、`summary/importance_metric_selection.md`、`summary/importance_delta_r2_summary.json`、`figures/07_evidence/*.png`。
* **统计单位**：(model, split_type, cell_line, factor)；Y 轴在同 (model,split,cell) 内归一化为占比（`normalize_within_context:170-184`）。
* **回答**：某环境因子的预测增量（Effect）与模型对它的依赖强度（Importance）是否一致。
* **不能回答**：**本批 180 点中 strict 档通过 0 点**（`execution_log.json` `importance_delta`）；`delta_r2_ci_low/high` 全为 NaN（bootstrap 未接入该模块）；importance 不能跨模型比较量纲；不是显著性、不是因果。
* 相关但**独立**的多尺度 CNN 配对 ΔR²：`docs/paper_analysis/cnn_kernel_paired.csv`（k5−k3 / k7−k3 / k7−k5，各 192 对，mean_dR2、CI、pct_positive、excludes_zero）。**该文件在本仓库没有生成脚本**（见 §7 #1），其来源池为 cnn k=3/5/7 的配对实验。

### 1.7 Position 18 signed substitution ISM —— `results/analysis/position18_signed_substitution_ISM*.csv`

* **代码位置**：`docs/paper_analysis/position18_signed_substitution_ism.py`（`N_BOOT=10000`、`SEED=42`、`POS_1B=18`：`:55-59`；聚合与落盘 `:246-316`；与实测比较 `:440-450`；报告 `:542`）。
* **输入资产**
  * 已训练模型：`results/batch_20260909_full/summary/ultimate/ultimate_<kind>_model.pt`（7 个 pooled）+ `models/batch_20260909_full/single_<cell>_cnn_sequence_kernel_<k>/cnn_model.pt`（12 个 cell-specific）（`:47-49, 88-119`）；
  * 序列与标签：`data/proceeded_data/`（`load_dataset:64-70`）；
  * 实测位置 18 碱基效率：`docs/paper_analysis/position18_efficacy_by_base.csv`（`:385`）。
* **输出**：`results/analysis/position18_signed_substitution_ISM.csv`（141 行）、`..._per_sample.csv`、`..._vs_measured.csv`（10 行：4 cell 系 × 3 替换，`agree` 7/10；HEK293T 三种替换全部不一致）、`..._ISM.md`、`paper/figures/position18_signed_substitution.png`。
* **统计单位**：位置 18 = C 的每条实测 guide（pooled 模型 n=5 080；另有 per-cell 分层）；Δ = f(substituted) − f(actual)，三替换 C>A/C>G/C>T；CI = 逐样本 percentile bootstrap（描述性。
* **回答**：模型预测中"把第 18 位 C 换成 A/G/T"的**有符号**方向与幅度。
* **不能回答**：是模型预测不是实验因果（`..._ISM.md:222`、`:533`）；不训练/不改动任何模型；与实测的一致性只在 3/4 细胞系成立，且是关联。

### 1.8 线性回归系数 —— `linear_regression_weights.csv`（训练侧 Effect）

见 §3.5（作为 Statistical 证据也列出）。

---

## 2. Importance 类（"模型多依赖它"）

### 2.1 统一归因表 —— `tables/attribution_summary.csv`

* **代码位置**：`analyse/attribution/extractors.py::extract_attribution_table`（`:53-139`）；列映射 adapter `analyse/attribution/columns.py::_ROW_SPECS`（`:11-32`）；位置/通道解析 `_parse_position_channel`（`:24-38`）；pipeline `analyse/pipeline.py:315-333`。
* **输入**：批次下所有 `*.csv`（跳过含 pred/metric/history/summary/biomarker/training 的文件名，`:18, 57-62`）＋ `<exp>/*info*.txt`（model/split/cell_line/environment/kernel）。
* **输出**：`tables/attribution_summary.csv`（331 200 行，14 列）＋ `summary/04_sequence_motifs.md`（`attribution/summary.py:29-50`）。
* **统计单位**：一行 = 一个 (feature=position×channel, model family, method, split_type, cell_line, environment) 归因值；**没有 seed 列**（mixed 的 4 个 seed 被堆叠平均，`core.py:142`）。
* **各列语义（有符号 vs 幅值）**

| method（model） | `importance` | 有符号？ | `snr` | `effect` | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `linear_coefficient` | `Linear_Coefficient` | **有符号**（min −1.4e11 / max +4.4e11） | `t_stat`（有符号） | **同 `Linear_Coefficient`** | 唯一有符号族 |
| `xgboost_treeshap` | `TreeSHAP`（mean\|SHAP\|） | 幅值（≥0） | `SHAP_SNR`=mean/std | NaN | |
| `xgboost_gain` | `XGB_Gain` | 幅值（≥0） | 无 | NaN | 树内部，无方向 |
| `mlp_ig` | `MLP_IG` | 幅值（≥0） | `IG_SNR` | NaN | |
| `cnn_ism` | `CNN_ISM` | 幅值（≥5.8e-5） | `ISM_SNR` | NaN | 替换效应幅值 |
| `cnn_ig` | `CNN_IG` | 幅值（≥0） | **无** | NaN | |
| `transformer_attention` | `Transformer_Attention` | 幅值（≥1.5e-3） | `Attention_SNR` | NaN | 无方向；另有 `attention_entropy` |

* **唯一有符号的模型级 attribution 列 = `effect`**（仅 30 912 行 linear 有值，其余 300 288 行为 NaN；`extractors.py:93-111`）；linear 的 `importance` 也保留了符号，但其它模型的 `importance` 全部是幅值。
* **回答**：模型内部对各位置×通道/环境因子的依赖强度（及 linear 的方向）。
* **不能回答**：SHAP/IG/ISM/Gain/Attention **没有零假设**，不能做 p/FDR（`src/xai_importance.py:1-44` 白名单 + `_FORBIDDEN_STATS`）；SNR 不是显著性（`analyse/config.py:10-16`）；无 seed 列 → 不能做 seed 级稳定性。

### 2.2 `summary/feature_importance/*` 与 `key_regulatory_biomarkers.csv`

* **代码位置**：`analyse/importance_extraction.py`：单模型报告 `extract_linear_coefficients:299` / `extract_xgboost_importance:359` / `extract_mlp_importance:419` / `extract_cnn_importance:479` / `extract_transformer_importance:553`；汇总 `collect_all_model_features:679-785`（CNN 用 `CNN_ISM`+`ISM_SNR`，`metric_map:735-741`）；落盘 `generate_key_regulatory_biomarkers:787-855`；入口 `process_batch:858-877`。
* **输入**：各实验目录的 feature-importance CSV（同 2.1 的文件族）。
* **输出**：`results/batch_20260909_full/summary/feature_importance/{linear_coefficiency,xgboost_importance,mlp_importance,cnn33/cnn53/cnn73_importance,transformer_importance}.md` + `key_regulatory_biomarkers.csv`（92 489 行，中文列名，含 `FDR校正q值`——仅 linear 有值）。
* **统计单位**：一行 = (split_type, cell_line, environment, model, canonical_feature)；mixed 先剔不显著再等权平均（`:802-823`）；single/all 逐实验保留。
* **回答**：各模型在各上下文下"显著/高 SNR"的位点-通道清单。
* **不能回答**：显著性判据是**两套**——linear 用 BH-FDR 星级，非线性用 SNR 星级（2.5/1.8/1.2，`:112-123`）；CNN 用的是 **CNN_ISM**，而 Importance–ΔR² 用的是 **CNN_IG**（`importance_metrics.py:55-58, 73`）→ 同一仓库对"CNN 重要性"有两个定义；空输入会写 2 行硬编码 demo（`:792-799`，本批未触发，文件 92 489 行）。
* **注意**：该目录**不是** `summary/` 产物，而是 `pipeline/steps.py:346-364` 的 `importance_extraction` 交付步骤产物（`Input/backend_runner.py:267-289`）。

### 2.3 Motif 对 attribution 的使用方式

见 §6：只取 CNN `cnn_ism` / `cnn_ig`，环境∈{sequence, all}，通道∈{A,C,G,T}，位置 1-23；**方向不来自 attribution 符号**。

---

## 3. Statistical Evidence 类

### 3.1 逐样本配对 bootstrap —— `tables/bootstrap_results.csv`

* **代码位置**：`analyse/stats/tasks.py::bootstrap_environment_edges`（`:141-196`）；配对枚举 `_lattice_pairs`（`:104-135`）；读预测 `predictions_path:52-58` / `load_run_pairs:61-82`；核心 `analyse/stats/bootstrap.py::bootstrap_paired_metrics_ci_fast:250-306`；pipeline `analyse/pipeline.py:205-227`。
* **输入**：`<batch>/<run_name>/*_predictions.csv`（`y_true`/`y_pred`，排除 validation）；`experiment_table` 的有效性 `_valid_row:85-101`。
* **输出**：`tables/bootstrap_results.csv`（7 770 行 = 2 541×3 metric）；R² 行 2 541 条全部 `ok`、257 条 CI 不跨 0；`tables/environment_bootstrap.csv`（`edge_ci_table:529-540`，2 541 行）。
* **统计单位**：**per-sample 配对**（同一 (split,cell,model,seed) 的 S 与 S∪{e} 同 test cohort，`n_samples` 记录 637/2513 等）；重采样 B=2000、seed=2024、α=0.05（`config.py:196-198`）。
* **回答**：单条 lattice 边的 ΔR²/ΔMAE/ΔRMSE 的不确定性区间。
* **不能回答**：不是显著性检验也不是因果（`bootstrap.py:1-4`）；样本数不等 → `unavailable/cohort_mismatch`，绝不降级为非配对（`:172-178`）；不做多重校正。

### 3.2 模型级 bootstrap —— `tables/bootstrap_main_effects.csv`

* **代码位置**：`analyse/stats/tasks.py::bootstrap_main_effects`（`:199-244`）；核心 `bootstrap.py::bootstrap_ci:52-65`。
* **输入**：`environment_main_effects.csv`（先按 model 均值，再对模型向量 bootstrap）。
* **输出**：`tables/bootstrap_main_effects.csv`（4 行），列含 `interval_type=model_level_bootstrap`、`estimate_basis=cross_model_mean_of_main_effect`、`n_models=7`。
* **统计单位**：**模型配置（n=7）**——不是 guide/样本（`:201-207` 明确声明）。
* **回答**：因子效应在不同模型归纳偏置间的一致性（跨模型稳健性）。
* **不能回答**：不是 guide 总体抽样不确定性；7 个模型共享同一数据/划分，不可视为独立生物重复；n=7 下 percentile bootstrap 无严格覆盖保证。

### 3.3 每细胞系模型级 bootstrap —— `tables/bootstrap_cellline_effects.csv`

* **代码位置**：`tasks.py::bootstrap_cellline_effects`（`:543-579`）；消费 `cellline_ci_lookup`（`:582-592`）→ `cellline/consistency.py` CI 重叠松弛。
* **输出**：36 行 = (split, cell_line, factor) 的跨模型 CI；`estimate_basis=cross_model_mean_main_effect_per_cellline`。
* **统计单位**：模型（每 cell × factor 内）。
* **回答**：某因子在某细胞系内跨模型是否稳定（并用于 CI 重叠松弛）。
* **不能回答**：mixed 的 `cell_line=none` 只有 1 个"细胞系"，无法做 context 判定。

### 3.4 置换检验 —— `tables/permutation_results.csv`

* **代码位置**：`tasks.py::permutation_environment_edges:250-298`、`permutation_main_effects:301-342`、`permutation_interactions:345-412`；核心 `hypothesis_tests.py::permutation_test_for_effect_fast:372-399`（**sign-flip**，`:391-392`）；FDR `tasks.py::apply_fdr:418-438` + `multiple_testing.py::bh_fdr:13-35`；pipeline `analyse/pipeline.py:229-249`。
* **输入**：per-sample 预测（edge / interaction）、条件增量长表（main）。
* **输出**：`tables/permutation_results.csv` 3 444 行（2 688 edge + 504 interaction + 252 main），3 273 `ok`（171 `unavailable`），3 273 行有 FDR。
* **三种 test_type 的零假设与单位**

| test_type | H0（`null_hypothesis` 列原文） | 备择 | 统计单位 |
| :--- | :--- | :--- | :--- |
| `environment_edge` | mean per-sample loss difference (SE_parent − SE_child) = 0 on the same test samples (sign-flip) | greater | 每个 test 样本的 SE 差 |
| `environment_main_effect` | mean conditional ΔR² over backgrounds = 0 (sign-flip over background values) | two-sided | 背景×seed 的条件增量 |
| `environment_interaction` | mean per-sample interaction I(a,b) = 0 (sign-flip over pooled background contrasts) | two-sided | 每样本的 4 组合交互 contrast |

* B=1000、seed=2024；p=(count+1)/(B+1)。
* **回答**：在明确零假设下，效应均值是否偏离 0。
* **不能回答**：置换不改 effect 大小；main-effect 检验的单位是"背景条件增量"，不是样本；`min_family_size=2` 不足则 `not_applicable`。

### 3.5 FDR / `family_key` 的真实分组（已核实）

* **代码**：`tasks.py:426`（`fdr_family = family_key`）→ `:429-437` 逐族 BH。族键由三处构造函数给出：`tasks.py:271`（edge）、`:325`（main）、`:397-398`（interaction）。
* **实际分组**
  * `environment_edge|{split_type}|{cell_line}|{model}`：**63 个族**，族大小 **32**（single/all）或 **128**（mixed，= 32 边 × 4 seed）；
  * `environment_main|{split_type}|{cell_line}|{model}`：63 族，族大小恒为 **4**（4 因子）；
  * `environment_interaction|{split_type}|{cell_line}|{model}`：63 族，族大小 **6**（C(4,2)）或 **24**（×4 seed）；
  * 合计 **189 个族**（与 `analysis_status.json` 的 "189 p-value families" 一致）。
  * **motif**：`fdr_family="motif_enrichment"` 单族 596 成员（`core.py:465`、`apply_enrichment_fdr:509-516`）。
  * **linear**：一次实验中全部 162 个权重（161 特征 + Bias）成一族（`src/linear_regression/linear_regression.py:220-232`）。
  * **ANOVA**：`family_key` 已写入（`tasks.py:483, 502`）但**没有任何 BH 调用**（`apply_fdr` 只被 permutation 调用：`pipeline.py:241`、`scripts/regenerate_permutation_and_evidence.py:46`）；`FdrFamilyConfig.enabled_families`（`config.py:165-170`）**0 消费点**。
  * `min_family_size=2`（`config.py:171`）仅在 `apply_fdr:431` 生效。
* **回答**：同一科学问题族内的假发现率控制。
* **不能回答**：跨族不能合并解读；"族"内把 4 个 seed 混在一起（mixed 族大小 128/24），因此 FDR 不是"每 seed"控制；ANOVA 完全无 FDR。

### 3.6 线性模型训练侧 p/FDR —— `linear_regression_weights.csv`

* **代码位置**：`src/linear_regression/linear_regression.py`：SE/t/p `:214-218`、BH-FDR `:220-232`、显著性星级 `:239-242`；落盘+白名单 `save_weights:528-566`；白名单 `src/xai_importance.py:28-44`。
* **输出**：每实验一份 `results/batch_20260909_full/<run_name>/linear_regression_weights.csv`（192 份），列 `Feature, Linear_Coefficient, SE, t_stat, p_value, FDR`；例：`mixed_linear_all_seed_42` 162 行、FDR<0.05 32 个。
* **统计单位**：一次线性拟合内的一条权重（同一实验的 162 个权重共用一个 BH family）。
* **回答**：线性主效应系数的方向与统计显著性。
* **不能回答**：线性假设；只覆盖 linear 模型；进入分析链后被压缩为 `importance_vs_delta_r2.csv` 的 `fdr`/`statistical_value`（factor 级取位点最小 FDR，`importance_delta.py:151`），**不参与 Tier**。

---

## 4. Robustness 类

### 4.1 细胞系 context 标签 —— `tables/cellline_effects.csv`

* **代码位置**：`analyse/cellline/consistency.py::summarize_environment_by_cellline`（`:146-194`）→ `classify_cellline_consistency_detail`（`:58-132`）；pipeline `analyse/pipeline.py:381-402`。
* **输入**：`environment_main_effects.csv`（`main_r2_delta`）＋ `bootstrap_cellline_effects` 的 CI（`cellline_ci_lookup`）。
* **输出**：`tables/cellline_effects.csv` 84 行（3 split × 7 model × 4 factor）+ `summary/05_cellline_heterogeneity.md`。
* **产生逻辑与阈值**（全部来自 `config.py:43-58`）
  1. 有效 cell line < `min_cell_lines=2` 或无多数方向 → `Uncertain`（mixed 的 `none` 即走此分支，28 行）；
  2. 反向占比 ≥ `conflicting_ratio=0.25` → `Context-conflicting`，但若反向者的 CI 与**全部**主体 CI 重叠则 `ci_overlap_relaxed=True` 降级（`:100-114`）；
  3. 无反向且 `max|effect|/median|effect| ≤ heterogeneity_ratio=2.0` → `Context-consistent`；
  4. 多数同向占比 ≥ `consistent_ratio=0.75` → `Context-dependent`；
  5. 否则 `Uncertain`。
* **本批分布**：`Context-conflicting 30 / Context-consistent 2 / Context-dependent 16 / Uncertain 36`。
* **回答**：同一因子在不同细胞系间方向/幅度是否一致。
* **不能回答**：不是"机制不同"的证明，也不是显著性检验（模块 docstring `:15`）；标签会被 evidence matrix 取众数后使用（`integration.py:195-198`），且 `Context-conflicting` 一票否决（`:273-274`）。

### 4.2 环境×细胞系均值 —— `docs/paper_analysis/environment_by_cellline.csv`

* 20 行 `factor, cell_line, mean_dR2, n`。**仓库内无生成脚本**；`_recon_provenance.md:72-73, 153, 179` 已逐值复现为"`environment_main_effects` 剔除 |ΔR²|>10 后按 (factor,cell) 等权 mean"。
* 单位：模型（每 cell 内 3 split × 7 model 行），回答细胞系异质性；不能回答统计显著性。

### 4.3 跨模型位置一致性 / 跨 kernel 谱 —— `docs/paper_analysis/cross_model_position_consistency.csv`、`kernel_position_profile.csv`

* 8 行（4 cell × {all, sequence}）：`mean_pairwise_spearman`（0.28–0.61）、`mean_top3_overlap`（0.30–0.53）、各模型峰值位置。`kernel_position_profile.csv`：23 位置 × cnn33/53/73 的归一化归因。
* 输入来源为 `attribution_summary.csv` 的 CNN 池；**两份都无 in-repo 生成脚本**（`make_assets.py:706-712` 只读）。
* 回答：不同模型/卷积核对同一位置谱的排序一致性（Robustness）。
* 不能回答：Spearman 只能重算到近似（`_recon_provenance.md:110`），无 CI、无 p。

### 4.4 mixed 的 4 seed 稳健性体现在哪里

| 产物 | 体现方式 |
| :--- | :--- |
| `tables/bootstrap_results.csv` | 有 `random_seed` 列（mixed 42/43/44/45），每条边 4 行 CI（实测 mixed 859 行 / 224 唯一边） |
| `tables/permutation_results.csv` | mixed 每族 128（edge）/24（interaction）行 = 4 seed；FDR 在族内跨 seed 一起校正 |
| `tables/environment_conditional_delta_r2.csv` | `n_paired=4`（mixed），`summarize_conditional` 对 seed 取均值 |
| `tables/environment_main_effects.csv` | `n_seeds=4`（mixed）；`n_backgrounds_avg` |
| `docs/paper_analysis/bootstrap_edge_by_factor.csv` | `excl_all` = 全 seed 的 CI 都不跨 0 的**保守并集**，`n_seeds_total`（`make_assets.py:726-739`） |
| `tables/attribution_summary.csv` | **没有 seed 列** → motif seed 支持记 `unavailable`（`motif/pipeline.py:256-260`） |

### 4.5 其他一致性指标

* `docs/paper_analysis/environment_cross_model.csv`（4 行：每 factor 的 7 模型均值/min/max/正负计数）；
* `docs/paper_analysis/factor_level_ci.csv`（4 行，模型等权 CI，`make_assets.py:356-377, 747-748`）——与 `bootstrap_main_effects.csv` **不是同一实现**（见 §7 #2）；
* `tables/motif_consistency.csv`（跨 CNN kernel / 跨 cell line / cross-model-transformer / seed，见 §6）；
* `tables/loco_performance.csv` 与 `prediction_summary.csv`（LOCO 泛化）——但本批 `all`≡`single`，`all` 划分**不能**作为真实跨细胞系泛化证据。

---

## 5. Evidence Integration（唯一权威分级）

### 5.1 环境行生成与判定链

* **代码**：`analyse/evidence/integration.py::environment_evidence_matrix`（`:132-337`）；唯一分级函数 `classify_evidence_tier`（`:72-129`）；pipeline 调用 `analyse/pipeline.py:404-431`。
* **输入列 → 门 → Tier 的完整链条**：

| 步骤 | 代码 | 输入 | 输出列 |
| :--- | :--- | :--- | :--- |
| ① 不稳定隔离 | `integration.py:158-162` | `main_effects.main_r2_delta`，阈值 `consensus.unstable_effect_threshold=10.0` | `unstable_rows_excluded` |
| ② 跨 split/cell 聚合到模型 | `:163-164` | `groupby(model, environment).mean()` | `model_effects` |
| ③ 覆盖/方向 | `:173, 191-193` | 有限模型效应 | `coverage=n_models`、`direction_concordance`、`concordance_denominator`、`n_neutral_models` |
| ④ effect 门 | `:179-189` | `effect_gate_mode="model_mean"`（`config.py:87`） | `effect_gate_pass`、`effect_gate_value`、`median_effect`、`model_direction_conflict` |
| ⑤ CI 门 | `:204-220` | `bootstrap_main_effects`（B≥`min_bootstrap_iterations=200`） | `ci_low/ci_high/ci_excludes_zero/n_bootstrap/bootstrap_status`；CI 跨 0 → `Inconclusive` |
| ⑥ 统计门 | `:229-267` | `permutation_results` 中 `test_type=="environment_main_effect"` 的行 | `permutation_p/permutation_fdr`、`min_edge_fdr`、`n_contexts*`、`fwer_upper_bound`；`<fdr_weak(0.05)` → pass |
| ⑦ 稳健性门 | `:217-220` | `concordance ≥ 0.80` 且 CI 不跨 0 | `robustness_gate_pass` |
| ⑧ 分级 | `classify_evidence_tier:112-129` | 三门外显式 | `tier_promotion_gate`、`evidence_tier` |
| ⑨ cell-line 一票否决 | `:273-274` | `cellline_effects.context_label` 众数 | `cell_line_consistency` |

* **规则原文**（`:91-98`）：方向冲突 / CI 跨 0 → `Inconclusive`；supporting≥`min_coverage=2` 且 concordance≥0.80 且 robustness 且**可提升门** → Tier 1；supporting≥2 → Tier 2；supporting==1 且有支持证据 → Tier 3；applicable==0 → `No current evidence`；否则 `Inconclusive`。
* **可提升门** = `effect_gate OR (statistical_gate AND statistical_gate_can_promote)`，后者默认 **False**（`config.py:82`）→ **统计证据不能单独升 Tier 1**。
* **关键细节**：`min_edge_fdr` 名字叫 edge，实际取的是 `test_type=="environment_main_effect"` 行（`:237-238`）的 **main-effect FDR 最小值**。实测：ctcf 的 main min FDR=0.009324，而真正 edge min FDR=0.06394。

### 5.2 当前 Tier 分布（`tables/evidence_matrix.csv`，600 行）

| feature_type | Tier | 数量 | 是哪些 |
| :--- | :--- | ---: | :--- |
| `environment` | Tier 1 | 0 | — |
| `environment` | Tier 2 | 1 | **rrbs** |
| `environment` | Tier 3 | 0 | — |
| `environment` | Inconclusive | 3 | ctcf（CI 跨 0 + Context-conflicting）、dnase（CI 跨 0 + concordance 0.714）、h3k4me3（CI 不跨 0 但 Context-conflicting 一票否决） |
| `motif` | Tier 1/2 | 0 | **结构性不可能**（见下） |
| `motif` | Tier 3 | 496 | coverage=1 且有支持证据 |
| `motif` | Inconclusive | 100 | `strong=False`（effect 门 fail 且 enrichment FDR≥0.05） |

* environment 4 行的 `effect_gate_pass` 全为 False（\|mean ΔR²\| 0.00095–0.00932 < 0.01）；`statistical_gate_pass` 全为 True，但 `tier_promotion_gate="statistical(disabled)"`。
* **motif 行结构性上限**：`motif_evidence_rows`（`motif/pipeline.py:335-398`）中 `families={'cnn'}` → `supporting=applicable=1`，永远 < `min_coverage=2`，因此 Tier 1/2 不可达（`:355-356, 363-366`）；`concordance=None`、`ci_crosses_zero=None`。

### 5.3 哪些分析**没有**进入 Tier（代码证据）

| 未进入项 | 代码证据 |
| :--- | :--- |
| **ANOVA**（p/F/η²） | `environment_evidence_matrix` 签名只有 `main_effects/cellline_summary/config/bootstrap_ci/permutation`（`integration.py:132-138`）；pipeline 调用未传 anova（`pipeline.py:412-415`）；`grep anova analyse/evidence/` 无命中 |
| **Importance / attribution**（SHAP/IG/ISM/Gain/Attention/SNR） | `integration.py:150-153` 注释明确排除；`importance_delta.py:428-464` 只**读** tier 回填 CSV，无反向写入 |
| **SNR 阶梯 / min_effect_size / FDR 阶梯（0.001/0.01）** | 只在 `importance_metrics.py:100-167`；`StatisticalRuleConfig` docstring `config.py:21-27` 声明"不参与 Evidence Tier" |
| **edge 级 bootstrap CI**（`bootstrap_results.csv`/`environment_bootstrap.csv`） | pipeline 只把 `bootstrap_main_effects` 作为 `bootstrap_ci` 传入（`pipeline.py:210-213, 414`） |
| **DAG nodes/ablation/interactions/DAG report** | 只用于画图与报告（`pipeline.py:296-311`），未进入矩阵 |
| **permutation 的 interaction 行** | factor 行只筛 `test_type=="environment_main_effect"`（`integration.py:237-238`），交互行 `factor="a*b"` 永不命中 |
| **线性训练侧 p/FDR** | 只经 `importance_vs_delta_r2.csv` 的 `fdr` 列（`importance_delta.py:259, 294`），该列不被 tier 读取 |
| **prediction / LOCO 指标** | 只在 `summary/02_prediction_generalization.md` 与图 |
| **motif_consistency 表本身** | tier 只用 `motif_candidates.model_consistency` 列的数值（`motif/pipeline.py:353`），不读 consistency 表 |
| **cellline CI 本身** | CI 只通过"是否松弛 conflicting"影响标签（`consistency.py:100-114`），进而一票否决 |

---

## 6. Motif 分析

### 6.1 五张表的生成代码与池子

* **编排**：`analyse/sequence/motif/pipeline.py::run_motif_discovery`（`:41-190`）→ `write_motif_tables`（`:279-317`）→ `run_and_write`（`:618-633`）；pipeline 调用 `analyse/pipeline.py:335-379`。
* **池子（逐步过滤）**
  1. `tables/attribution_summary.csv` → `core.load_attribution`（`core.py:81-99`）：`method ∈ {cnn_ism, cnn_ig, transformer_attention}`，`model ∈ {cnn}` 或 supporting method，`environment ∈ {sequence, all}`，`channel ∈ {A,C,G,T}`；
  2. 实际生成 motif 时**只保留 `cnn_ism`/`cnn_ig`**（`pipeline.py:84-87`，`transformer_attention` 被 `continue` 掉，`transformer_ig` 不存在）；
  3. 序列池：`data/proceeded_data/<cell_line>_metadata.csv`（`core.load_sequences:61-78`，`sgRNA` + `*efficacy*`）；实际用到 4 个细胞系、16 749 条；
  4. seqlet：位置×通道 attribution 的**specificity**（减同位置其它碱基均值，`core.py:164-169`）→ 分位 0.90 + 连续 ≥2 位点超 0.75 分位 → 长度 4–12、每样本 ≤2 窗口（`extract_seqlets:205-254`；阈值 `config.py:123-128`）；
  5. 聚类：贪心相似度（与 consensus ≥0.90）→ 二次合并 ≥0.95（`cluster_seqlets:305-332`、`merge_similar_clusters:335-358`）；
  6. 支持门槛：seqlet ≥30 且 sample ≥20（`finalize_clusters:382`）；
  7. per-context 截断：≤8 正常 + ≤3 exploratory（`pipeline.py:115-129`）。
* **产物**

| 表 | 行数 | 生成位置 | 内容 |
| :--- | ---: | :--- | :--- |
| `tables/motif_instances.csv` | 172 098 行（596 motif 的实例；30 MB）。注意 `n_seqlets=545 060` 是**聚类前的 seqlet 总数**（`motif/pipeline.py:184`，见 `analysis_status.json`），不是本文件行数 | `pipeline.py:297-304`；列 `core.INSTANCE_COLUMNS:33-36` | seqlet 级：sample/cell/position/sequence/attribution_score/ism_effect/ig_effect/direction/efficacy |
| `tables/motif_candidates.csv` | 596 | `pipeline.py:285-295`；列 `core.CANDIDATE_COLUMNS:38-46` | motif 级：consensus/iupac/human_pattern/regex/length/support/mean_effect/effect_direction/FDR/evidence_strength |
| `tables/motif_enrichment.csv` | 596 | `pipeline.py:306-308`；`core.enrichment_for_motif:462-506` | Fisher exact OR/p/FDR |
| `tables/motif_consistency.csv` | 1 194（596 kernel + 596 cell_line + 1 cross_model_transformer + 1 seed） | `pipeline.py:206-261, 310-312` | 跨 kernel variant / 跨 cell line / 跨模型 / seed |
| `tables/motif_evidence.csv` | 596 | `pipeline.py:314-316` + `motif_evidence_rows:335-398` | 进入 evidence_matrix 的 motif 行 |

* 另有 `summary/04_sequence_and_motifs.md`（motif 章节，`build_motif_md:530-602`、`append_motif_section:605-615`）与 `figures/04_motif/*`（logos/位置/一致性/富集，`render_motif_figures:401-423`）。

### 6.2 方向来源（attribution 无符号）

* `core.signed_value_column`（`:102-115`）在**已过滤行**上检测 `effect/signed_effect/importance_signed`：CNN 与 attention 行的 `effect` 全为 NaN → 返回 `None` → 全部 seqlet `direction="unsigned"`（`extract_seqlets:235-242`），单分组（`pipeline.py:99-113`）。
* motif 方向改由 **carrier vs background 的实测 efficacy 对比**给出：`finalize_clusters:395-411`，`mean_effect = mean(eff_carrier) − mean(eff_background)`，`direction_source="carrier_vs_background_measured_efficacy"`；本批 596 行全部走此路径。
* `motif_candidates.warning` 显式记录 `attribution_unsigned: direction from measured efficacy contrast`（`pipeline.py:174-176`）。

### 6.3 enrichment 的池子与 "≠ causal mechanism" 依据

* 前景 = 每个细胞系内 efficiency ≥ q0.67；背景 = **该细胞系全部有 efficacy 的序列（包含前景本身，嵌套）**（`core.py:479-485`）；跨细胞系汇总后做单次 Fisher exact（`alternative="greater"`，`:498-502`）；族内 BH-FDR（`apply_enrichment_fdr:509-516`）。本批 596 个检验、64 个 FDR<0.05。
* **"motif enrichment ≠ causal mechanism" 的代码/文档依据**
  * 代码：`motif/pipeline.py:535-537`（"候选序列模式，**不是**因果结论，也不称 significant motif 除非 enrichment 通过 FDR"）；`:594-601` Limitations（"方向来自 measured efficacy 对比（关联性, 非因果）"）；
  * 报告：`summary/reports/04_sequence_and_motifs.md:78`；
  * 论文：`paper/tables/tab5_motifs.tex:4`（"not a causal effect"）；
  * 状态文档：`docs/statistical_analysis_status.md:32`（"不做 motif-level 因果/剂量效应"）。
* **回答**：某序列模式在高效序列中是否比背景更常见（关联）。
* **不能回答**：因果机制；不做 motif-level 剂量/机制检验；attention 不是 motif extractor；CNN vs Transformer 跨模型比较 `unavailable`；seed 级支持 `unavailable`。

### 6.4 需要注意的数据缺陷

* `motif_candidates.model_consistency` 实测 2–24，而 `motif_consistency.n_total` 恒为 3（kernel 变体数）。原因：`_build_consistency`（`pipeline.py:206-229`）把"同 (environment, method) 组内所有相似 motif"都计为 supporting，跨细胞系的重复 motif 被反复计数，导致 `n_supporting = 1 + len(shared)` 可远超 3。该值随后被 `stability_label`（`core.py:522-545`）与 `motif_evidence_rows`（`pipeline.py:353, 362`）当作"跨架构复现"证据 → 340 个 motif 得到 "Moderate motif evidence"（见 §7 #10）。
* `motif_evidence.csv` 的 `permutation_p/permutation_fdr` 在 motif 行里实际是 **Fisher 富集 p/FDR**（`motif/pipeline.py:385-387`），与 environment 行的 sign-flip 置换不是同一检验；tier 只用到 FDR 阈值，语义尚可，但列名易误读。

---

## 7. 文档与代码不一致清单（逐条，含验证）

> 标 ✅ 的条目本次已用产物/代码双向核对。

1. **✅ `docs/paper_analysis/README.md` 声称"所有文件由 `paper/make_assets.py` 重新计算得到"——不成立。**
   `make_assets.py` 对 13 个 CSV 中的 11 个只 `read_csv`（`:706-714`），只写 `bootstrap_edge_by_factor.csv`（`:739`）、`factor_level_ci.csv`（`:748`）、`asset_summary.json`（`:765`）。
   无 in-repo 生成脚本的 11 个：`nucleotide_frequency_by_position / position18_efficacy_by_base / position18_attribution / cross_model_position_consistency / position_profile_by_model / region_attribution / cnn_ism_position_profile / kernel_position_profile / cnn_kernel_paired / environment_by_cellline / environment_cross_model`。
   `README.md:301`（"全部数字…可用 `paper/make_assets.py` … 复现"）同样误导；`docs/_recon_provenance.md:18-24, 196` 已记录该事实但它仍是 README 的正式说明。

2. **✅ 同一"因子级 CI"存在两套实现，数值不同，且论文同篇引用两个版本。**
   * `analyse/stats/tasks.py::bootstrap_main_effects`（`:199-244`，RNG 用 `bootstrap.py:52-65` 的 `rng.integers`）→ 进 `evidence_matrix`；
   * `paper/make_assets.py::factor_ci`（`:356-377`，`rng.choice(vals, size=(n, k))`）→ `docs/paper_analysis/factor_level_ci.csv`，进 Fig.7。
   实测差异：DNase `[-0.005229, +0.000402]` vs `[-0.004515, +0.000302]`；H3K4me3 `[-0.012900, -0.000988]` vs `[-0.012662, -0.001116]`；RRBS `[-0.024192, -0.000950]` vs `[-0.024287, -0.001025]`。
   论文 `paper/sections/03_results.tex:49` 用 factor_level_ci 的数，`:147` 用 bootstrap_main_effects 的数（DNase 两处不一致）；`docs/audit/evidence_tier_before_after.md` 只列了后者。

3. **✅ ANOVA effect size：文档/配置说 partial η²，代码算的是 η²。**
   `analyse/config.py:99` `effect_size_metric="partial_eta_squared"`（0 消费点）；`hypothesis_tests.py:331` 实为 `eta = ss_term / ss_total`（经典 η²）。`docs/statistical_analysis_status.md:86` 与 `paper/sections/03_results.tex:53` 写 "partial η²"，而 `paper/sections/02_methods.tex:40` 写 "η² = SS_term/SS_total"。
   `docs/_recon_statistics.md:158` 直接把 `ss_term/ss_total` 标为 "partial η² 语义"。

4. **✅ ANOVA 从不做 FDR，但配置/文档把 ANOVA 列为一个 FDR family。**
   `config.py:165-170` `enabled_families` 含 `environment_anova / environment_anova_group`，**0 消费点**；`apply_fdr` 只被 permutation 调用（`pipeline.py:241`）；`anova_results.csv` 无 FDR 列（`ANOVA_COLUMNS tasks.py:42-44`）。`paper/sections/02_methods.tex:40` 写 "BH-FDR … 析因 ANOVA … 各自成族"；`docs/paper/evidence_tier_provenance.md:92` 在 BH-FDR 行里列 ANOVA 族，`:93` 又说"ANOVA 表无 FDR 列"（自相矛盾）。

5. **✅ `min_edge_fdr` / `selection_basis` / `statistical_evidence_role` 的命名与代码不符。**
   代码筛的是 `test_type=="environment_main_effect"`（`integration.py:237-238`），值是**主效应** FDR 最小值；实测 ctcf main min FDR=0.009324 vs 真正 edge min FDR=0.06394。但文档/论文统一称其为 "Minimal Edge-level FDR across Tested Contexts"（`docs/audit/evidence_tier_R2_fdr_aggregation.md`、`docs/paper/evidence_tier_provenance.md:46, 92`、`paper/sections/02_methods.tex:48`、`paper/sections/03_results.tex:147`）。

6. **✅ `docs/statistical_analysis_status.md:79` 写 "本批 n_obs=966, df_den=1265"，产物是 `n_obs=1288`。**
   `anova_results.csv` 的 10 个 blocked_factorial 行全部 `n_obs=1288`；`tasks.py:461-463` 剔除后真实入模 n=1288。论文 `03_results.tex:53` 写 n=1 288（正确）。

7. **✅ 论文置换计数与产物不符。**
   `paper/sections/03_results.tex:51` 写"主效应检验 35/252 … 通过 FDR<0.05"，实测 `permutation_results.csv` 中 `environment_main_effect` 且 FDR<0.05 = **30**/252（p<0.05 才是 54）。交互 9/504、edge 6/2 688 与产物一致。

8. **✅ `README.md:292` 写"表格（28 个 CSV）"，实际 `summary/tables/` 只有 27 个 CSV。**

9. **✅ `environment_edges.csv`（及 `environment_ablation.csv`）mixed 行被 CI 合并重复放大。**
   `merge_edge_ci`（`factorial_dag.py:306-334`）的 merge key 不含 `random_seed`，而 `bootstrap_results` 对 mixed 有 4 个 seed → 每个 mixed 边 4 行：文件 2 651 行 vs 唯一键 2 016，mixed 组 859 行 / 224 唯一边（all/single 组未受影响）。文档把 edges 描述成"一条边一行"，下游 `make_assets.py:730` 靠 `drop_duplicates` 绕过。

10. **✅ motif 的 `model_consistency` / `model_variant_support` 系统性高估。**
    `_build_consistency`（`motif/pipeline.py:206-229`）`n_supporting = 1 + len(shared)`，shared 是"同 environment/method 内所有相似 motif"（含其它细胞系的重复 motif），`n_total` 才是 kernel 变体数 3。实测 `model_consistency` 2–24（512/596 > 3），却被 `stability_label`（`core.py:535-540`）与 tier 当作跨架构支持（`motif/pipeline.py:353-362`），产生 340 个 "Moderate motif evidence"。

11. **✅ R7/R8 之后仍有旧 Tier 结论残留在文档。**
    `docs/statistics_and_parameters_zh.md:188` 与 `docs/paper_claim_provenance_v2.md:36` 仍写 "RRBS Tier1、DNase Tier2、CTCF/H3K4me3 Inconclusive"；当前 `evidence_matrix.csv` 是 RRBS **Tier 2**、DNase **Inconclusive**、环境 Tier 1 数 = 0（`docs/audit/evidence_tier_before_after.md` 已更新，但那两份没同步）。

12. **✅ `docs/paper/evidence_tier_provenance.md:72` 的伪代码仍是旧口径。**
    写 `effect_gate_pass = any(|per-model mean| >= 0.01)`，而代码默认 `model_mean`（`config.py:87`、`integration.py:184-189`），同文档 `:169`（R4）又说改成了模型等权平均。
    同类残留：`docs/_recon_statistics.md:275, 595` 描述的是 R3/R4 之前的"strong 布尔量直接升 Tier 1"规则。

13. **✅ 04 报告存在两个近重复文件，命名与文档不一致。**
    `analyse/pipeline.py:322-323` 写 `summary/04_sequence_motifs.md`（attribution 摘要，`attribution/summary.py`）；motif 管线写 `summary/04_sequence_and_motifs.md`（`motif/pipeline.py:605-615`）。后者只含 motif 章节、不含 attribution 覆盖表。`docs/statistical_analysis_status.md:192` 只提后者。

14. **✅ `analysis_status.json` 的 reason 有陈旧值。**
    `environment_conditional_effect` 状态 `completed` 但 reason 仍是 `"environment features unavailable"`；`hypothesis_generation` reason 仍是 `"hypothesis_generation requires evidence integration"`（`pipeline.py:141-150` 的 `_finish` 在无新 reason 时保留校验期的旧 reason）。

15. **✅ 代码内 docstring 过期：`analyse/stats/hypothesis_tests.py:381`。**
    写 "通过对中心化后的值做随机重排得到 null 分布"，实际实现是 sign-flip（`:391-392`）；同文件 `:34-38` 与 `docs/statistical_analysis_status.md:59-61` 已说明修正。

16. **✅ 死配置字段（0 消费点），与"每个阈值都有生产消费点"的声明不一致。**
    `AnovaRuleConfig.enabled_default`（`config.py:94`）、`AnovaRuleConfig.effect_size_metric`（`:99`）、`MotifDiscoveryConfig.enrichment_enabled_default`（`:150`）、`MotifDiscoveryConfig.preferred_position_bins`（`:147`）均无消费者；`docs/paper/evidence_tier_provenance.md:55` 声称"配置中保留的每一个阈值都有生产消费点"（该声明限定在 Tier 阈值，但未注明这 4 个例外）。

17. **`motif_enrichment` 的前景/背景是嵌套集合。**
    `core.enrichment_for_motif:480-485`：前景 = 上三分位，背景 = 全部（含前景），OR 因此是"相对全体的富集"而非"前景 vs 非前景"。文档描述（`paper/sections/02_methods.tex:44`）与代码一致，但结果解读（OR≈0.87 被视为 depletion）需要注意这一口径。

18. **`key_regulatory_biomarkers.csv` 在输入为空时会写 2 行硬编码 demo 数据。**
    `analyse/importance_extraction.py:792-799`；本批未触发（92 489 行）。若上游提取失败，交付物会静默变成 demo 行——文档 `docs/project_pipeline_and_code_documentation.md:1874` 有此记录，但 README 未提示。

19. **同一仓库对"CNN 重要性"有两个定义（文档已指出但仍在用）。**
    交付物链 `importance_extraction.py:735-741` 用 `CNN_ISM`+`ISM_SNR`；分析引擎链 `importance_metrics.py:55-58, 73` 用 `CNN_IG` 并显式排除 `CNN_ISM`。`docs/statistics_and_parameters_zh.md:295`、`docs/_recon_provenance.md:206` 已记录，但两套产物同时存在且命名相近。

---

## 8. 一页速查：产物 → 生成者 → 单位 → 是否进 Tier

| 产物（相对 `summary/`） | 生成代码（file:line） | 统计单位 | 进 Tier？ |
| :--- | :--- | :--- | :---: |
| `tables/experiment_table.csv` | `pipeline.py:94-95`；`data/loaders.py` | 1 次实验 | 否（是输入） |
| `tables/prediction_summary.csv` / `loco_performance.csv` | `pipeline.py:164-170`；`analyse/prediction.py` | (model, split) | 否 |
| `tables/environment_conditional_delta_r2.csv` | `incremental_effect.py:51-106` | 边 × seed 配对 | 否 |
| `tables/environment_main_effects.csv` | `incremental_effect.py:109-133` | 模型配置 | **是（唯一 Effect 输入）** |
| `tables/environment_edges.csv` / `nodes` / `ablation` / `interactions` / `dag_report` | `factorial_dag.py:147-599` | 边 / 组合 / 因子对 | 否 |
| `tables/anova_results.csv` | `stats/tasks.py:453-503` | 一次实验 R²（blocked 设计） | **否** |
| `tables/attribution_summary.csv` | `attribution/extractors.py:53-139` | (feature, model, method, 上下文) | 否 |
| `tables/bootstrap_results.csv` / `environment_bootstrap.csv` | `stats/tasks.py:141-196, 529-540` | per-sample 配对 | 否（仅 Fig/报告） |
| `tables/bootstrap_main_effects.csv` | `stats/tasks.py:199-244` | 模型（n=7） | **是（CI 门）** |
| `tables/bootstrap_cellline_effects.csv` | `stats/tasks.py:543-579` | 模型（每 cell） | 间接（松弛标签） |
| `tables/permutation_results.csv` | `stats/tasks.py:250-438` | 样本 / 背景 / 交互 contrast | **是（统计门，仅 main 行）** |
| `tables/cellline_effects.csv` | `cellline/consistency.py:146-194` | (split, model, factor) | **是（众数标签，冲突否决）** |
| `tables/evidence_matrix.csv` | `evidence/integration.py:132-337` + `motif/pipeline.py:335-398` | 因子（环境）/ motif | **产出本身** |
| `tables/importance_vs_delta_r2.csv` | `visualization/importance_delta.py:215-663` | (model, split, cell, factor) | 否（只读 Tier） |
| `tables/motif_*.csv` | `sequence/motif/pipeline.py:41-633` | motif / seqlet | 仅 `motif_evidence` 行 |
| `results/analysis/position18_signed_substitution_ISM*.csv` | `docs/paper_analysis/position18_signed_substitution_ism.py` | guide（位置 18=C） | 否 |
| `docs/paper_analysis/*.csv`（11 个） | **无生成脚本** | 混杂（模型/实验/样本） | 否 |
| `summary/feature_importance/*` | `analyse/importance_extraction.py:299-877` | (split, cell, env, model, feature) | 否 |
| `results/batch_*/<run_name>/linear_regression_weights.csv` | `src/linear_regression/linear_regression.py:528-566` | 权重（实验内 162 个） | 否 |

---

## 9. 复现命令（只读/不改产物）

```bash
# 完整分析（复用打开的 plan，含 ANOVA 与 motif enrichment）
.venv/bin/python -m analyse.pipeline --batch-dir results/batch_20260909_full \
    --analysis-plan results/batch_20260909_full/summary/analysis_plan.json

# 仅重量化 permutation/bootstrap/evidence（R1–R8 工具）
.venv/bin/python scripts/regenerate_permutation_and_evidence.py        # dry-run
.venv/bin/python scripts/regenerate_evidence_tier_assets.py            # dry-run

# 论文图表/表（依赖 docs/paper_analysis/ 中 11 个无源 CSV 必须已存在）
.venv/bin/python paper/make_assets.py

# Position18 有符号替换 ISM（需已训练模型 + data/proceeded_data）
.venv/bin/python docs/paper_analysis/position18_signed_substitution_ism.py

# Tier 规则测试
.venv/bin/python -m unittest analyse.tests.test_evidence_tier_rules -v
```

---

## 10. 最重要的三个不一致（结论）

1. **`docs/paper_analysis/` 的 11 个 CSV 在仓库内没有生成脚本**，却被 README 与目录 README 描述为 `paper/make_assets.py` 的可复现产物（`docs/paper_analysis/README.md`、`README.md:301`）。论文 Fig.4/5/Table 3–4 的位置谱、kernel 配对、环境×细胞系等数字因此**不可从仓库端到端复现**。
2. **因子级 CI 有两套实现、数值不同，且论文同篇两处引用不同版本**（`stats/tasks.py:199-244` vs `paper/make_assets.py:356-377`；`03_results.tex:49` vs `:147`），同时 `factor_level_ci.csv` 与 `bootstrap_main_effects.csv` 并存，消费方互不知情。
3. **`min_edge_fdr` 名不副实**：它实际是 `environment_main_effect` 行的最小 FDR（`evidence/integration.py:237-238`；ctcf 0.009324 vs 真 edge 0.06394），却被论文方法/结果与多份审计文档统一称为 "Minimal **Edge-level** FDR across Tested Contexts"，并作为 statistical gate 阈值来源；ANOVA 的 `family_key` 已写入但从不做 BH-FDR（`config.py:165-170` 为死配置）。
