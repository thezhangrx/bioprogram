# 汇报数字的「池子」与「加权方式」勘察

> ⚠️ **历史勘察快照（重构前）**：本文记录 2026-09-14 目录重构**之前**的结构，其中的路径名（`src/`、`analyse/`、`data/proceeded_data/`、`results/<batch>`）均为旧路径。
> 当前权威结构见 `README.md` 与 `docs/architecture/`；科学定义见 `docs/science/`。


> 只读勘察产物。范围：本仓库 `results/batch_20260909_full/` 的全部对外汇报数字，以及
> `docs/paper_analysis/*.csv`。
> 每条目 = 产物路径 → 生成代码 file:line → 池子（哪些实验/样本/种子/细胞系） → 合成规则（含权重） → 备注/不确定性。
> 结论实证方式：读代码 + 用 pandas 对产物做数值反推（命令均在仓库内只读执行）。

## 0. 全局前提（影响所有数字）

- 本批实验网格 = **1 344** 个实验 = 16 环境组合 × 3 划分 × 4 细胞系 × 7 模型配置（CNN 展开 3 个卷积核）。
  证据：`results/batch_20260909_full/summary/metrics_tables/all_experiments.csv` 行数 1344；CNN 行 576。
  生成：`data_digging.py:125-164`（枚举）、`Input/backend_runner.py:45-59`（16 个环境组合 = sequence + 幂集，含 all）。
- 划分：`single`（单细胞系内部划分）、`all`（留一细胞系，`all_*_heldout_<cell>`）、`mixed`（四细胞系混合）。
  证据：`data_digging.py:167-180`（命名）。
- mixed 的 4 个种子 = **独立实验、独立文件夹**：`MIXED_SEEDS=[42,43,44,45]`（`data_digging.py:59`、`146-147`、`160-162`；`backend/crispr_workspace/training.py:32`）。
  `single`/`all` 只有 seed 42（`data_digging.py:274-275`，实为 `build_command` 中 `random_seed = seed if split_type=="mixed" else 42`；`all_experiments.csv` 中 grouped`(all,42)=448`、`(single,42)=448`、`(mixed,42..45)=112×4`）。
- **发散行**：linear 有 56/192 个实验 |R²|>10；多数汇总会先剔除这些行（见 §1、§3）。
- **重要不确定性**：`docs/paper_analysis/` 下多数 CSV **在本仓库中没有生成脚本**。全仓库 grep（排除 `.venv/.git`）只找到
  *读取方*：`paper/make_assets.py`（`578,589,690-698`）与 `paper/make_position18_summary.py:43-45`。
  `make_assets.py` 只 *写出* 3 个文件：`bootstrap_edge_by_factor.csv`（`paper/make_assets.py:723`）、
  `factor_level_ci.csv`（`:732`）、`asset_summary.json`（`:749`）。
  其余 CSV 由一份未提交/已丢失的脚本在 2026-09-12 15:2x 生成 → 其规则为本报告依据产物数值反推（标注置信度）。

---

## 1. mixed 多种子是否取平均？

**结论：同一批结果里，一部分产物对 4 个种子做等权算术平均，另一部分保留 1 行/实验（不平均）。**

| 产物 | 生成代码 | 是否对 seed 42–45 平均 | 规则/权重 |
| :--- | :--- | :--- | :--- |
| `summary/metrics_tables/mixed_cell_line_result.csv`（112 行 = 16 环境 × 7 模型） | `analyse/collect_results.py:291-309`（`groupby(["model","environment"]).mean()` 在 `:303`） | **是** | 先 `filter_valid`（`:176-179`，剔除 \|R²\|>10 或 MAE/RMSE>10 的 run），再按 (model, environment) **等权算术平均**；种子不额外加权、不按 n 加权。 |
| `summary/metrics_tables/baseline.csv`（mixed 行） | `analyse/collect_results.py:360-385`（显式注释「关键：对 mixed 模式跨 4 个随机种子求平均」`:374`，`mean()` `:376`） | **是** | 同上，等权。已数值验证：xgboost/sequence 4 seed R² = {0.1563,0.1570,0.1739,0.1867} → 0.168454 = baseline 行。 |
| `summary/metrics_tables/all_experiments.csv` | `analyse/collect_results.py:326-332` | **否** | 每个实验 1 行原样落盘（mixed 的 4 个 seed 各占 1 行）。 |
| `summary/tables/experiment_table.csv` | `analyse/data/loaders.py:38-87`（优先读 `all_experiments.csv`） | **否** | 逐实验行；`random_seed` 作为字段保留（`loaders.py:67,84`）。 |
| `summary/tables/prediction_summary.csv` | `analyse/prediction.py:11-21` | **否（先不平均种子）** | `groupby(["model","split_type"]).agg(["mean","std"])` 直接对 **实验行** 求均值；mixed 的 `n_experiments=64` = 16 环境 × 4 seed，即 4 个种子各算一个样本。 |
| `summary/tables/environment_main_effects.csv` | `analyse/environment/incremental_effect.py:109-129` | **是（两阶段）** | 先对「背景 S」求均值，再对 seed 求均值：`per_seed = groupby(split,cell,model,seed,env).mean()`（`:117-122`）→ `out = groupby(split,cell,model,env).mean()`（`:123-129`）；`mixed` 行 `n_seeds=4`。等权 per background、等权 per seed。 |
| `docs/paper_analysis/*.csv` 中的模型归因类 | 生成脚本缺失 | **无法确证**（见 §2） | 归因来源 `analysis_out/tables/attribution_summary.csv` **没有 seed 列**，mixed 的 4 个种子行是堆叠在一起的（e.g. 一组 736 行 = 4×184），因此这些 CSV 只能按行平均，**不能区分种子**。 |
| `summary/赛道二_results.csv` / `summary/ultimate/*` | `predict.py` | **不涉及** | mixed 池被 concat 成一份训练集（见 §4、§7），不使用 42–45 的多种子设计。 |

---

## 2. 576 个 CNN 实验的 ISM/IG 在 `docs/paper_analysis/*.csv` 里如何 pool？

**池子（确认）：全部 576 个 CNN 实验** = 16 环境 × (single 192 + all 192 + mixed 192，其中 mixed = 4 seed × 4 细胞？——mixed 无细胞系，实为 16 env × 4 seed × 3 kernel = 192)。
证据：`data_digging.py:149-162`；`all_experiments.csv` 中 `model` 含 cnn 的 576 行，`all/single/mixed` 各 192。
每个实验贡献 `23 位置 × (4 + 表观通道数)` 行；`attribution_summary.csv` 中 `cnn_ism` 与 `cnn_ig` **各 79 488 行 = 全部 576 个实验**（数学核验：2×(4 cells×3 kernels×96 env-channel 和)=…，实测 79488 与全 576 相符）。
生成：`analyse/pipeline.py:316-321`（`extract_attribution_table` → `attribution_summary.csv`），原始值来自每个实验文件夹的 `cnn_feature_importance.csv`（列 `CNN_IG`,`CNN_ISM`,`ISM_SNR`）。

**合成规则（反推，中等置信度）：**
- **不是按样本数 n 加权**（原始重要性文件没有 n 列，全程用等权 mean/sum）。
- 结构：先 **按位置汇总通道**（pos × channel → 位置向量），再 **按模型内归一化**，最后 **对实验/上下文等权平均**。
  已用 `attribution_summary.csv` 反推验证（非精确复现，最大偏差 0.003–0.015）：
  `position_profile_by_model.csv`（23 行 × 5 模型）≈ 对 **所有** cell_line/环境/划分/kernel/seed 混在一起，得到每模型 1 条 23 维归一化谱；
  `kernel_position_profile.csv`（cnn33/cnn53/cnn73 三条）≈ 同法但 **按 kernel 分开**，**不跨 kernel 混合**；
  `region_attribution.csv`（160 行）≈ **保留 cell_line × environment（仅 all / sequence 两个环境）× model × region**，region 内对位置取均值；
  `position18_attribution.csv`（720 行）≈ **保留 cell_line × environment(16) × split_type × model**，第 18 位 C 占比 = C 通道绝对归因 / 该位置各通道绝对归因之和（linear 恰为 1/3 = 0.3333，与「T 参照列被剔除、只剩 A/C/G」一致）。
- ISM vs IG 的取舍：`paper/make_assets.py:32-33` 的 `PRIMARY` 映射对 cnn 取 `cnn_ig`（每个模型只取 **一种代表方法**，不跨方法平均）；但原始 CNN 文件同时含 ISM/IG，kernel 曲线更接近 ISM。**属"取一种方法"而非平均**。
- **不确定性**：用 `attribution_summary.csv` 重算无法逐位复现这些 CSV（Spearman/区间有偏差），说明生成脚本还做了本仓库看不到的处理（很可能是按实验先归一化再平均、或剔除了部分实验）。**生成脚本不在仓库中**，无法给出 file:line。

---

## 3. cell line 效应表怎么算？是否按 n 加权？

**结论：先算每个 (split, model, factor, cell_line) 的效应，再对 (split×model) 等权平均；全程不按 n 加权。**

- `summary/tables/cellline_effects.csv`（84 行 = 3 split × 7 model × 4 factor）
  生成：`analyse/pipeline.py:389-392` → `analyse/cellline/consistency.py:146-194`。
  它 **不重新算效应**，而是把 `environment_main_effects.csv` 的 `main_r2_delta` 按 (split, model, factor) 分组后
  逐 cell line 抄成 `effect_<cell>` 列（`consistency.py:163-172`），并额外输出 context 标签（`:176-191`）。
  `mixed` 的 `cell_line="none"` 被当作 **第 5 个"细胞系"** 一并纳入（列 `effect_none`）。
- `docs/paper_analysis/environment_by_cellline.csv`（20 行，列 `factor,cell_line,mean_dR2,n`）
  **生成脚本缺失**，但其数值可 **精确复现**：对 `environment_main_effects.csv` 按 `(factor, cell_line)` 分组，
  先剔除发散行 `|main_r2_delta| <= 10`（阈值定义 `analyse/config.py:38`），再取 `mean` 与 `size`。
  复现结果与产物逐值一致（如 ctcf/hct116 mean=0.004784333, n=12）。
  池子 = **3 种 split × 7 个模型**：`all` 与 `single` 各贡献 7 行且两者数值相同（本批 all/single 逐位一致），
  故 hct116/hek293t/hela/hl60 为 n=12–14（=14 行 − 被剔除的发散 linear 行），`none`(mixed) 为 n=6（7−1）。
  规则 = **等权 per (split×model) 行**；**不是按 n、也不按 seed**（main effect 内部已对 seed/背景取过均值，见 §1）。
- `environment_main_effects.csv` 本身的效应：对「不含 e 的全部背景 S」的 ΔR²(e|S) 先按 seed 平均、再跨背景平均，等权（`incremental_effect.py:51-129`）。
- **是否按 n 加权：否。** 全线用 `mean()`；没有任何地方把样本数当权重。

---

## 4. ultimate 模型的 CV R² / CV RMSE 与最终重训

产物：`summary/ultimate/ultimate_summary.json`（`cv_folds=10, epochs=15, seed=42, n_samples=16749, n_features=92`）、`ultimate_<model>_config.json`、`preds_<model>.npy`。

- **折数**：10 折 `KFold(n_splits=10, shuffle=True, random_state=seed)`，`seed=42`（`predict.py:409-423`；默认 `--ultimate-cv-folds 10` `:746`）。
- **每折 epoch 数**：`epochs=15`，固定，无早停（`predict.py:328-351, 746-748`；`_fit_torch_model` 只跑固定 `range(epochs)`）。
- **seed 是否统一**：是。CV 切分、模型初始化、DataLoader shuffle 全用同一个 `seed=42`（`predict.py:334-335, 415`；`:748` 默认值）。
- **CV R²**：每折 R² 的 **算术平均**（`predict.py:418-423`，`np.mean(r2_list)`）；CV RMSE 同法。**不是拼接所有折的样本后整体算 R²**。
- **超参选择 = 取最优**：对 `ULTIMATE_GRIDS`（`predict.py:68-92`）逐组跑 10 折 CV，**取 CV R² 最大的一组**（`predict.py:516-522`，`if best is None or cv_r2 > best["cv_r2"]`；断点续跑版同规则 `:963-969`）。报告值即该最优组的 CV R²/RMSE/std。
- **最终模型 = 全量重训**：用最优 config 在 **全部 mixed 样本** 上重训（`predict.py:525-526, 972-973`，传入 `np.arange(len(y))`）。
  训练池 = 所有 4 个细胞系 concat（`_load_mixed_subset` `predict.py:240-261`）；本批因 target 无表观通道，按 `plan` 裁成 **4 通道 sequence-only、92 维**（`predict.py:763-790`；`ultimate_summary.json:6-7`）。
- 实测 `ultimate_summary.json`：lr 0.0815、xgboost 0.1274、mlp 0.1453、transformer 0.0837、cnn33 0.0596、cnn53 0.0925、**cnn73 = −0.0160**（负值，后续被剔除，见 §7）。
- **"最优"而非平均**：最终写入的是胜出 config 单次全量训练；CV 只用于选 config 与报告，不参与模型集成。

---

## 5. 跨模型一致性（mean pairwise Spearman 0.28–0.61、top-3 overlap 0.30–0.53）

产物：`docs/paper_analysis/cross_model_position_consistency.csv`（8 行 = 4 细胞系 × {all, sequence}）。

- **生成脚本缺失**（非 `make_assets.py` 产物；`make_assets.py:578,693` 只读取）。以下为结构反推 + 数值部分复现：
- **模型对**：5 个模型（linear, xgboost, mlp, cnn, transformer）的全部 C(5,2)=10 个无序对；`mean_pairwise_spearman` 与 `mean_top3_overlap` 是这 10 个值的 **等权算术平均**（无加权）。
- **位置集合**：23 个位置全用（列 `n_positions=23`）；每条谱是「模型内归一化的 23 维位置归因谱」。
  峰值列 `peak_*` = 该 (cell_line, environment, model) 谱的 `argmax`。
- **是否先按细胞系平均：否。** 每行就是一个细胞系 × 一个环境（`all`/`sequence`），**不跨细胞系合并**；仅在该 (cell_line, environment) 内部跨 split/kernel/seed 池化。
- top-3 overlap 数值均为 k/30（10 对 × 每对 ∈{0,1/3,2/3,1}），与"10 对等权"一致。
- **不确定性**：用 `summary/tables/attribution_summary.csv` 重算可复现 part of top-3 overlap，但 Spearman 有偏差（如 hela/all 参考 0.611，重算 0.42–0.50），提示生成脚本对实验谱做了额外归一化/剔除。置信度：池子结构高，精确归一化中。

---

## 6. `position18_efficacy_by_base.csv` 的 mean_efficacy 与 n

产物：`docs/paper_analysis/position18_efficacy_by_base.csv`（19 行 = 4 细胞系 × 碱基 + ALL 行）。

- **生成脚本缺失**，但数值 **精确可复现**：直接来自 **实测数据** `data/proceeded_data/{cell}_metadata.csv`，
  第 18 位 = `sgRNA`（0-based）第 17 个字符，按该碱基分组对 `Normalized efficacy` 求
  `count / mean / median / std`。
- **池子**：每个细胞系 **全部已测样本**，不区分实验/划分/种子/表观环境：
  HCT116 4 239（A1652/C1377/G1210）、HEK293T 2 333（+T577）、HeLa 8 101、HL60 2 076（+T507）；
  `ALL` 行 = 该细胞系全部样本。与 `asset_summary.json` 的 `n_samples=16749` 一致。
- **权重：等权 per 样本**（pandas 默认 mean），**不是** per 实验、也不是 per 细胞系再平均。复现值与产物逐位相同（如 hct116/C mean=0.309420, n=1377）。

---

## 7. `summary/赛道二_results.csv` 的分数/排名怎么合成？

- **生成代码**：`predict.py:892-928`（`_write_track2_from_preds`，断点续跑路径）或 `predict.py:651-716`（`generate_track2_results_ultimate`，一次性路径）；调用方 `predict.py:822-837`（`main`）。
- **输入来自 target 输入**：本批目标文件 = `data/todo_data.CSV`（180 512 条 `sgRNA`+`Efficacy`）。
  验证：`赛道二_results.csv` 的 20 条候选序列 **全部** 出现在该文件中。该文件无染色体/坐标 → `位点=chrUnknown(NA)`（`extract_locus_from_row` `predict.py:566-605`）；无表观列 → target 通道规划退化为 **序列-only 4 通道**（`ultimate_summary.json` `n_features=92`）。
- **模型集成**：7 个 ultimate 模型各自对 target 打分（`predict.py:880-889`，lr 剔除 `_T` 参照列），**先 clip 到 [0,1]**（`:889`）。
- **合并规则 = 等权算术平均，且只保留 CV R²>0 的模型**：
  `usable = [r["model"] for r in rows if cv_r2 > 0]`（`predict.py:895`）→ 本批 cnn73（CV R²=−0.016）被 **剔除出共识**，
  共识 = `np.mean(pred_mat, axis=0)`（`:896-897`）。
  `对应模型` 列实际为 `Ultimate_Consensus (Linear+XGBoost+MLP+Transformer+CNN(3|3)+CNN(5|3))`（6 个模型，等权，无 n 加权）。
- **排名规则**：`np.argsort(consensus)[::-1][:top_k]`，即按共识分 **降序取 Top-20**（`predict.py:898`；`--candidate-top-k` 默认 20 `:743`）。
- **展示细节**：`预测编辑效率` 写作 `共识值 [Linear:x|XGBoost:x|...]`，括号里 **仍含被剔除的 CNN(7|3)**（`predict.py:910` 遍历 `preds`，而 `:897` 只用 `usable`）。→ 看单模型分解时勿把括号内 7 个数当等权共识。
- `训练方式_细胞系` 恒为 `mixed_all`（`:913`）——候选分 **不区分细胞系**，是四细胞系混合池的共识。

---

## 8. 全部「取最优 / 取首个 / 取最后 / 取并集 / 排除」而非平均的规则

1. **Ultimate 超参 = 取 CV R² 最大的一组**（不是多组平均）：`predict.py:521`、`:968`。
2. **共识只用 CV R²>0 的模型**（排除式筛选，不是加权）：`predict.py:679`、`:895`。
3. **断点续跑 = 有完成标记就复用旧结果，不重算不平均**：`predict.py:873-877`、`:950-955`。
4. **网格实验的指标取「验证损失最优 epoch」的 checkpoint**（早停后 `load_state_dict(best_state_dict)`），**不是最后一轮、也不是多轮平均**：
   `src/cnn/cnn.py:684-743`、`src/mlp/mlp.py:595-655`、`src/transformer/transformer.py:622-681`；
   配置默认 `epochs=100, patience=20, min_delta=1e-6`（`data_digging.py:410-416`），划分 `0.7/0.15/0.15` 单次留出（`data_digging.py:407-409`；`train.py:491-500`）。每个实验只报 **1 个测试集 R²**，不是 CV 均值。
5. **发散实验先剔除再平均**：`collect_results.py:176-179`（\|R²\|>10 或 MAE>10 或 RMSE>10 丢弃）。
   `docs/paper_analysis/environment_by_cellline.csv` 同样带 \|ΔR²\|≤10 过滤（阈值 `analyse/config.py:38`，已数值复现）。
   分析引擎的因子矩阵也排除不稳定上下文（`analyse/pipeline.py:423-426`）。
6. **Table 2 / Fig. 2 用中位数而非均值**（因 linear 发散）：`paper/make_assets.py:497-502`、`:69,85`。
7. **每个模型只取一种代表归因方法**（`PRIMARY` 映射，不跨 IG/ISM/SHAP 平均）：`paper/make_assets.py:32-33`。
8. **因子级 CI：先按模型求均值，再对模型做 bootstrap（模型等权）**，不是把 (模型×划分×细胞系) 行混在一起 bootstrap：
   `paper/make_assets.py:356-378`（`vals = sub.groupby("model")["main_r2_delta"].mean()`）。
9. **逐样本边级 bootstrap 的多 seed 聚合 = 保守并集**：`ci_low=min, ci_high=max, excl_all=all`，而非对 seed 取均值：
   `paper/make_assets.py:711-723`（`bootstrap_edge_by_factor.csv`）。
10. **`data_digging` 遇已完成实验直接跳过（取首个已存在的 run 目录）**：`data_digging.py:197-247`。
11. **目标文件选取取「第一个」**：`sorted(glob("*.csv"))[0]`（`Input/backend_runner.py:232-234`）；CSV 候选 `csv_candidates[0]`（`:159-161`）。
12. **特征工程复用已存在的 benchmark npy，不重算**：`Input/backend_runner.py:152-155`。

---

## 附：产物 → 代码 速查表

| 产物 | 代码位置 | 池子 | 合成规则 |
| :--- | :--- | :--- | :--- |
| `summary/metrics_tables/all_experiments.csv` | `analyse/collect_results.py:326-332` | 1344 个实验目录 | 逐实验 1 行，不聚合 |
| `summary/metrics_tables/mixed_cell_line_result.csv` | `collect_results.py:291-309` | 16 env × 7 model × 4 seed | 剔除发散行后按 (model,env) 等权 mean |
| `summary/metrics_tables/baseline.csv` | `collect_results.py:360-385` | mixed 的 4 seed | 等权 mean |
| `summary/metrics_tables/{single,all}_cell_line_result.csv` | `collect_results.py:273-288` | 对应 split 的各实验 | 逐实验 1 行 |
| `summary/tables/experiment_table.csv` | `analyse/data/loaders.py:38-87` | 同 all_experiments | 逐实验行 |
| `summary/tables/prediction_summary.csv` | `analyse/prediction.py:11-21` | per (model, split) 全部实验行 | mean/std，seed 各算 1 个 |
| `summary/tables/environment_main_effects.csv` | `analyse/environment/incremental_effect.py:109-129` | per (split,cell,model,factor) | 先跨背景、再跨 seed 等权 mean；`n_seeds` |
| `summary/tables/cellline_effects.csv` | `analyse/pipeline.py:389-392` + `analyse/cellline/consistency.py:146-194` | 同上 | 抄 main effect + context 标签，无再平均 |
| `docs/paper_analysis/environment_by_cellline.csv` | **脚本缺失**；反推 | 3 split × 7 model 的 main effect 行 | 剔除 \|ΔR²\|>10 后按 (factor,cell) 等权 mean |
| `docs/paper_analysis/position18_efficacy_by_base.csv` | **脚本缺失**；反推 | 每细胞系全部实测样本 | 等权 per 样本，pos18=sgRNA[17]，实测 `Normalized efficacy` |
| `docs/paper_analysis/position_profile_by_model.csv` / `kernel_position_profile.csv` / `region_attribution.csv` / `position18_attribution.csv` | **脚本缺失**；输入来自 `summary/tables/attribution_summary.csv`（`analyse/pipeline.py:316-321`） | CNN 全部 576 实验（ISM/IG 各 79488 行）+ 其余模型 | 位置×通道汇总 → 模型内归一化 → 跨实验等权；见 §2 |
| `docs/paper_analysis/cross_model_position_consistency.csv` | **脚本缺失** | 4 cell × {all,sequence} × 5 model | 10 个模型对等权 mean Spearman / top-3 |
| `docs/paper_analysis/cnn_kernel_paired.csv` | **脚本缺失** | 配对 kernel 实验（每比较 n=192 对） | 配对差 + 配对 bootstrap CI；`mean_dR2` 等权 |
| `docs/paper_analysis/bootstrap_edge_by_factor.csv` | `paper/make_assets.py:711-723` | `tables/bootstrap_results.csv` 的 R2 行 | 先按 edge 聚多 seed（CI 取并集），再按 factor 计数/mean |
| `docs/paper_analysis/factor_level_ci.csv` | `paper/make_assets.py:356-378, 731-732` | per-model mean main effect | 模型等权 mean → 百分位 bootstrap(2000, seed=2024) |
| `docs/paper_analysis/asset_summary.json` | `paper/make_assets.py:739-749` | 上述各表 | 计数/汇总，无加权 |
| `summary/ultimate/*` + `ultimate_summary.json` | `predict.py:476-559, 931-1003` | mixed 4 细胞系 16749 样本 | 10 折 CV(seed 42, 15 epochs) 选最优 config → 全量重训 |
| `summary/赛道二_results.csv` | `predict.py:892-928` / `651-716` | `data/todo_data.CSV` 180512 条 target | CV R²>0 的模型等权 mean → 降序 Top-20 |
| `summary/feature_importance/{linear_coefficiency,xgboost,mlp,cnn33,cnn53,cnn73,transformer}_importance.md` | `analyse/importance_extraction.py:266-296`（写）、`:299-611`（各模型抽取）、`:858-875`（`process_batch`，经 `pipeline/steps.py:287-289,344-349`、`Input/backend_runner.py:267-272`） | 各实验目录的 `*_feature_importance.csv`；**不做聚合**，每 (实验, 特征) 1 行（`_write_importance_md:285-295`） | **无平均**：`split_type/environment/cell_line` 各自保留；CNN 按 kernel 拆 3 个文件（`:539-547`）；4 个 mixed seed 变成 4 行同键重复（无 seed 列） |
| `summary/feature_importance/key_regulatory_biomarkers.csv` | `analyse/importance_extraction.py:679-784`（收集）+ `:787-855`（写） | 5 模型族 7 个配置，CNN 用 **CNN_ISM**（`metric_map:735-741`），显著性用 `ISM_SNR`（`:742,751,760`）；linear 用 BH-FDR（`:240-247`），非线性用 SNR 阈值 `***≥2.5/**≥1.8/*≥1.2/.≥0.8`（`:112-123`），纳入条件 `sig_score>0`（`:802`） | **mixed 才聚合**：先剔除不显著行，再 `groupby(split_type,cell_line,environment,model_key,feature).mean()`（`:808-816`）→ **只对"显著种子"做等权算术平均**（不是 n 加权、不是中位数）；single/all 逐实验保留 1 行（`:804,825-827`）；kernel 不混合 |
| `summary/03_environment_effects.md` + `summary/tables/*.csv` | `analyse/pipeline.py:493`、`analyse/environment/factorial_dag.py:512-563` | `experiment_table` 的 (split,cell,model) 组 | Factorial DAG：ΔR²(e\|S)=R²(S∪e)−R²(S)，边保留全部加序；见 §3 |
| `summary/anomaly_report.md` | `analyse/anomaly_treatment.py` | `all_experiments.csv` | 标记不删除（`Input/backend_runner.py:260-265`） |

## 未查完 / 明确的不确定性

1. `docs/paper_analysis/` 中除 `bootstrap_edge_by_factor.csv`、`factor_level_ci.csv`、`asset_summary.json` 外，**生成脚本不在仓库内**；§2/§5 的规则是数值反推，池子结构可高置信，精确归一化/剔除细节中置信。
2. `summary/feature_importance/*` 已查清（见速查表 + 下方"补充"），但两套 CNN 重要性定义并存，需在论文口径上二选一。
3. `cnn_kernel_paired.csv` 的 192 对究竟是「64 个 (cell×env) × 3 比较」还是「192 个 (cell×env×split)」未能区分（生成脚本缺失）。
4. `summary/tables/*.csv` 与 `summary/tables/*.csv` 内容部分不同（3/5 文件 md5 不同），哪次运行写出 `summary/tables` 未定位到复制代码。
5. XGBoost 网格实验用 `early_stopping_rounds=30` + `best_iteration`（`src/xgboost/xgboost.py:527,572,213-215`），但 `predict` 未传 `iteration_range`（`:233-237`），是否按 best_iteration 截断未独立验证（`requirements.txt:16` 钉 `xgboost<=2.0.3`，环境实装 3.4.1）。
6. 16 个环境名的来源：`build_active_environment_combinations` 返回 17 个名字（显式全组合 + `all` 重复），由 `data_digging._canonicalize_combinations`（`data_digging.py:63-94`）去重为 16；绕过 data_digging 直接调用会重复计数 `all`。

## 补充：feature_importance 的已验证细节（子任务实证）

- `.md` 报告列白名单 `XAI_WHITELIST:134-140`：cnn = `CNN_IG + CNN_ISM + ISM_SNR` 全列；linear = `Linear_Coefficient/SE/t_stat/p_value/FDR`；xgboost = `XGB_Gain/Weight/Cover/TreeSHAP/SHAP_SNR`；mlp = `MLP_IG/IG_SNR`；transformer = `Transformer_Attention/Attention_Entropy/Attention_SNR`。
- `key_regulatory_biomarkers.csv` 对 CNN 用 **CNN_ISM**（`importance_extraction.py:735-741`）；而另一套 `analyse/importance_metrics.py:55-58` 的 `PRIMARY_METRICS` 用 **CNN_IG 且显式排除 CNN_ISM**（`NOT_USED_AS_Y:73`），供 `analyse/visualization/importance_delta.py:29` 使用。**同一仓库对"CNN 重要性"存在两个不同定义**，引用头条数字时须确认用的哪套。
- 数值验证（CNN_ISM, `mixed,none,sequence_dnase_rrbs,cnn73,pos11_G`）= 0.020736258942633826 = 4 个 mixed seed 的 `.md` 值 (0.0224/0.0249/0.0227/0.0129) 的等权均值；另一例 `mixed,none,sequence_h3k4me3_rrbs,cnn73,pos22_T` 的 CSV 值 = 仅 **3 个显著 seed** 的均值（0.0218059），证明"先剔不显著、再平均"。
- `key_regulatory_biomarkers.csv` **未**应用 `is_feature_valid_for_env`（与 `.md` 写手不同），含 652 行 `environment=="sequence"` 却带表观通道的行，全部来自 transformer —— 潜在口径不一致。

