# 项目统计学工具、生信参数与「每个数字的来源 / 加权」总表

> 对象批次：`results/batches/batch_20260909_full`（1 344 次运行，4 个细胞系，16 749 条 23 nt 序列）。
> 本文只记录**真实存在**的代码与产物，每条给 `file:line` 或产物路径；无法确证的写「未确认」，绝不补写。
> 关注点不是公式，而是：**这个数是从哪些实验/样本里、按什么权重合成出来的**。
> 支撑材料（本次勘察的完整版）：`docs/_recon_statistics.md`（743 行）、`docs/_recon_parameters.md`（486 行）、`docs/_recon_provenance.md`。

---

## 0. 阅读地图

| 章节 | 内容 |
| :--- | :--- |
| §1 | 上游实验矩阵与数据池（统计的"池子"里到底有谁） |
| §2 | 统计学工具清单（工具 / 参数 / 聚合规则 / 产物） |
| §3 | 生信与建模参数 |
| §4 | **每个数字的来源与加权**（核心） |
| §5 | 「不是平均」的规则清单 |
| §6 | 审计发现（含 2 个真实问题） |
| §7 | 缺口与未确认项 |
| §8 | 复现命令 |

三个术语：**池子** = 参与合成的实验/样本集合；**等权** = 每个单元权重相同；**取最优** = 不做平均而是选择（如按 CV R² 选超参）。

---

## 1. 上游：实验矩阵与数据池

### 1.1 数据
| 项 | 值 | 证据 |
| :--- | :--- | :--- |
| 细胞系 | HCT116 / HEK293T / HeLa / HL60 | `data/processed/*_metadata.csv` |
| 合法序列 | **16 749** 条 23 nt（原始 18 982 条，特征工程去重后） | `docs/paper_analysis/asset_summary.json`、`feature_engineering_summary.csv` |
| metadata 列 | `Cell line, Chromosome, Start, End, Strand, sgRNA, Normalized efficacy` | `data/processed/hct116_metadata.csv` |
| 特征文件 | `<cell>_features_23x8.npy` (N,23,8)、`<cell>_features_184.npy` (N,184)、`<cell>_labels.npy` | `core/data/splitting/cell_line_division.py:75-86` |
| 原始来源 | `data/raw/{hct116,hek293t,hela,hl60}.csv` | — |
| 目标待测集 | `data/candidate/todo_data.CSV`（`sgRNA,Efficacy`，180 513 行） | 勘察记录 |

### 1.2 运行矩阵（1 344 = 3 split × 448）

| split | 含义 | CNN | 其它 4 类模型（合计） | seed |
| :--- | :--- | ---: | ---: | :--- |
| `single` | 单细胞系内划分 | 192（4 细胞系 × 16 环境 × 3 kernel） | **256**（4 模型 × 4 细胞系 × 16 环境） | 42 |
| `all` | 留一细胞系（LOCO）**⚠ 本批实际退化为 single** | 192 | **256** | 42 |
| `mixed` | 4 细胞系合并训练 | 192（16 环境 × 3 kernel × **4 seed**） | **256**（4 模型 × 16 环境 × 4 seed） | **42/43/44/45** |

* 模型配置 7 种：`linear`、`xgboost`、`mlp`、`cnn(3|3)`、`cnn(5|3)`、`cnn(7|3)`、`transformer`（448 = 192 CNN + 256 非 CNN，逐 split 成立）。
* 环境组合 16 种 = 纯序列 + 4 个表观通道的 15 个非空子集。
* **只有 `mixed` 有 4 个种子** —— 这决定了后面「哪些平均、哪些不平均」。
* ⚠ `all` 退化原因（已逐层定位，见 §6 发现 2）：批处理从未传 `--cell-lines`，只传 `--cell-line`（`workflows/training/data_digging.py:309-310`）→ `workflows/training/train.py:661-662` 把 `cell_lines` 构造成 `[该细胞系]` → `divide_data:320` 只加载 1 个数据集 → `split_all_cell_lines:214-217` 的「单一细胞系退化保护」直接改走 `split_single_cell_line`。**证据**：384 个可读的 `all` 配置全部 `cell_lines` 长度 = 1；2967+635+637 = 4239 = HCT116 自身样本数（真 LOCO 应为训练池 ≈ 10 633）；448 个 `all` run 与同 (model/kernel, environment, cell line, seed) 的 `single` run 的 R²/RMSE/MAE/Pearson/Spearman **448/448 逐位相同**。

### 1.3 通道与展平维度（重要修正）

| 场景 | 实际输入 | 维度 | 证据 |
| :--- | :--- | ---: | :--- |
| **实验目录里的全部 run** | 8 通道张量；未选中的表观通道 **mask 置 0（不删列）** | **184 = 23×8**（2D）/ (N,23,8)（3D） | `cell_environment_combination.py:1151-1236`、`all_experiments.csv` 的 `input_shape_train=[N,184]` |
| 同上，**线性模型** | 再剔除 `_T` 参照列 | **161** | `core/models/linear/linear_regression.py:462-488` |
| **ultimate 模型（workflows/prediction/predict.py 纯序列规划）** | A/C/G/T 4 通道 | **92 = 23×4** | `workflows/prediction/predict.py:101-142`、`ultimate_summary.json`（`n_seq_channels=4, n_features=92`） |
| 同上，线性 ultimate | 再剔 `_T` | **69** | `ultimate_lr_model.json`（`n_features=69`） |
| CNN（`sequence_channels=4`） | 8 通道张量内部切片成 (N,23,4) | — | `core/models/cnn/cnn.py:566-637` |

→ 即 `sequence` 环境并不等于 4 通道输入，而是**表观通道全 0**；真正的 4 通道输入只出现在 ultimate / 单细胞系 CNN 的"纯序列"配置里。

---

## 2. 统计学工具清单

参数集中在 `analysis/config.py`：`bootstrap_iterations=2000`、`bootstrap_seed=2024`、`bootstrap_alpha=0.05`、`permutation_iterations=1000`、`random_seed=42`（`:174-178`）。

### 2.1 主流程已接线的工具

| # | 工具 | 代码位置 | 输入 | 关键参数 | **聚合 / 加权规则** | 产物（实测存在） |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Bootstrap CI（通用） | `analysis/stats/bootstrap.py:52` | 任意一维估计量 | B=2000, seed=2024, α=0.05 | 对样本索引有放回重采样，**等权** | — |
| 2 | 逐样本配对 ΔR² bootstrap | `analysis/stats/tasks.py:141` | 同 `(split,cell,model,seed)` 下 `S` 与 `S∪{e}` 的 `*_predictions.csv` | B=2000；样本不匹配 → `unavailable` | **逐样本配对**；**不跨 seed 平均**（每 seed 一行 CI） | `tables/bootstrap_results.csv`（7 770 行 / 2 541 个 ΔR² CI） |
| 3 | 配对指标 bootstrap | `bootstrap.py:189,250` | `[y_true, y_pred]` 对 | `n_iterations=2000` | multinomial 计数矩阵，同 n/seed 复用 | 供 #2 使用 |
| 4 | Permutation（sign-flip） | `hypothesis_tests.py:26,372`；`tasks.py:244,295,328` | edge / main / interaction 三类 effect | B=1000, seed=2024 | H0 逐行记录；符号可交换；type-I ≈0.057 @α=0.05 | `tables/permutation_results.csv`（3 444 行） |
| 5 | BH-FDR | `multiple_testing.py:13`；入口 `tasks.py:401` | 带 `p_value` 的结果 | 按 `family_key` 分组；`min_family_size=2` | **按科学问题分族**，不混用（见 §2.3） | `FDR` / `fdr_family` 列 |
| 6 | Factorial ANOVA | `hypothesis_tests.py:244`；`tasks.py:436` | `experiment_table.csv` | Type-II 边际 F；`min_observations=32`、`min_residual_df=5`、`ci_iterations=400` | blocked 设计 `R² ~ A*B*C*D + C(model)+C(cell_line)+C(split_type)`；另有 per-(split,cell,model) 加性主效应 | `tables/anova_results.csv`（94 行，**无 FDR 列**） |
| 7 | Effect size | `effect_size.py:12,17` | 基线/扩展值 | — | `delta_pair = 扩展 − 基线`；ANOVA 用 `partial_eta_squared` | 同上 |
| 8 | Cell-line consistency | `cellline/consistency.py`；阈值 `config.py:41-56` | 各细胞系效应 + CI | `min_cell_lines=2`、`consistent_ratio=0.75`、`conflicting_ratio=0.25`、`heterogeneity_ratio=2.0`、`ci_overlap_relaxes=True` | 方向 + 幅度异质性 + CI 重叠三判据；四标签全可达 | `tables/cellline_effects.csv`（84 行） |
| 9 | Evidence tier | **实际生效**：`evidence/integration.py:43-65,90-191`；阈值 `config.py:30-38` | bootstrap + permutation + coverage | `min_coverage=2`、`direction_concordance=0.80`、`min_bootstrap_iterations=200` | 见 §2.2 | `tables/evidence_matrix.csv`（600 行） |
| 10 | Motif enrichment | `sequence/motif/core.py`、`pipeline.py:335-397`；阈值 `config.py:82-137` | `motif_instances.csv`（172 098 行） | Fisher exact + BH-FDR（单一 `motif_enrichment` family）；foreground 分位 0.67 | **跨细胞系合并 2×2 计数**（pooled）；阈值按细胞系内分位 | `motif_enrichment.csv`、`motif_candidates.csv`（596 行） |
| 11 | 训练侧线性 t/p/FDR | 训练时写入，分析层只读 | `linear_*` 的特征 p 值 | BH（`linear_regression.py:219-232`） | family = 单次实验的特征集 | `importance_vs_delta_r2.csv`（180 行） |
| 12 | 描述性审计统计（本会话新增） | `docs/paper_analysis/position18_ism_audit.py`、`position18_signed_substitution_ism.py` | 576 个 `cnn_feature_importance.csv` / 已训练 checkpoint | IMS 审计：mean±1.96SE；signed ISM：B=10 000, seed=42 | 样本级 → 模型级**等权** → 配置**等权计数** | `results/analysis/position18_*` |

### 2.2 Evidence tier 实际判定（environment 行）

| 顺序 | 条件 | 结果 |
| ---: | :--- | :--- |
| 1 | `conflicting_direction` 或 `ci_crosses_zero` | `Inconclusive` |
| 1b | cell-line 众数标签 = `Context-conflicting` | 直接 `Inconclusive` |
| 2 | supporting ≥ **2** 且 (concordance 为空或 ≥ **0.80**) 且 strong | **Tier 1: Strong convergent** |
| 3 | supporting ≥ 2 | **Tier 2: Moderate convergent** |
| 4 | supporting == 1 且 strong | **Tier 3: Model-specific / exploratory** |
| 5 | applicable == 0 | `No current evidence` |
| 6 | 其它 | `Inconclusive` |

* `supporting` = 与模型等权均值同号的模型数；`strong` = 任一 `|Δ| ≥ 0.01` 或 permutation FDR < 0.05；
* CI 参与判定需 `bootstrap_status=="ok"` 且 `n_bootstrap ≥ 200`；进矩阵前剔除 `|main_r2_delta| ≥ 10`；
* motif 行复用同一函数，但 coverage = 模型家族数、concordance 为空、strong = FDR<0.05 或（|effect|≥0.01 且 kernel 变体≥2）；无方向的 Tier1 降级为 Tier3。
* ⚠ `analysis/evidence/rules.py` 的三个 `classify_*`（FDR 0.001/0.01/0.05、SNR 2.5/1.8/1.2、|effect|≥0.005 分档）**只被单测调用，未接产线**；Importance–ΔR² 的 `evidence_strength` 用的是同一套阈值的另一份实现（`importance_metrics.py:100-146`）。

### 2.3 多重比较：只有 BH-FDR 一种，按族隔离

| family 前缀 | 出处 | 细分 |
| :--- | :--- | :--- |
| `environment_edge\|…` | `tasks.py:265` | `<split>\|<cell>\|<model>` |
| `environment_main\|…` | `tasks.py:312` | 同上 |
| `environment_interaction\|…` | `tasks.py:380-381` | 同上 |
| `environment_anova\|global`、`environment_anova_group\|…` | `config.py:143-148` | — |
| `motif_enrichment` | `motif/core.py:509-516` | 单一族 |

* **不做校正的**：`anova_results.csv`（无 FDR 列）、`bootstrap_results.csv` 的 CI、位置 18 的两个审计脚本（明确声明不做检验/校正）。
* **禁止**：SNR / SHAP / IG / ISM / attention 的原始值进入 p 值或 FDR（`schemas.py:8-9`、`integration.py:107-108`、`tasks.py:7`）。
* ⚠ `config.FdrFamilyConfig.enabled_families` 的命名与代码实际写入的 `family_key` 前缀不一致，且 `apply_fdr` 未使用该白名单（未确认是否有意）。

### 2.4 其它随机性参数

| 用途 | 参数 | 出处 |
| :--- | :--- | :--- |
| QC KDE | 5 折 / 24 点 / 子抽样 2000 / seed 42 | `analysis/data_QC.py` |
| 异常检测 | IsolationForest `contamination=0.01`, seed 42 | `analysis/anomaly_treatment.py` |
| 发散阈值 | `|metric| > 10` → 剔除 | `config.py:38`、`collect_results.py:178` |
| 位置 18 审计 CI | `mean ± 1.96·SE` | `docs/paper_analysis/position18_ism_audit.py` |
| 位置 18 有符号 ISM | B=10 000, seed 42 | `docs/paper_analysis/position18_signed_substitution_ism.py` |

---

## 3. 生信与建模参数

| 类别 | 参数 | 值 | 证据 |
| :--- | :--- | :--- | :--- |
| 序列 | 长度 / 构成 | 23 nt = 20 nt protospacer + NGG | `core/features/engineering/feature_engineering.py:132` |
| 序列 | PAM | 位置 21–23；22–23 恒为 GG（4 个源文件 100 %） | 频率统计 |
| 序列 | 位置编号 | 特征名 1-based `pos1..pos23`；张量下标 0-based | `feature_engineering.py:940-949`、`:406-427` |
| 序列 | Strand | **只记录，不参与编码**；全仓库无 reverse-complement | 勘察确认 |
| 序列 | 非 ACGT | 序列通道遇非 ACGT **直接抛错**；表观通道只允许 A→1 / N→0 | `feature_engineering.py:411-418, 471-478` |
| 通道 | 序列 4 + 表观 4 | A/C/G/T one-hot + CTCF/Dnase/H3K4me3/RRBS per-position binary | `data/metadata/feature_config.json` |
| 划分 | 比例 / 分层 | 0.70 / 0.15 / 0.15；**非分层**（无 StratifiedKFold） | `cell_line_division.py:154-172` |
| 划分 | 种子 | single/all = 42；mixed = 42/43/44/45 | `workflows/training/data_digging.py:59,275` |
| 训练（实验网格） | epochs / batch / lr / dropout / wd / patience / min_delta | 100 / 64 / 1e-3 / 0.2 / 0.0 / 20 / 1e-6 | `workflows/training/train.py:619-642` |
| 训练（实验网格） | MLP hidden / kernel / scaler | 128→64 / 3（可选 3,5,7）/ 默认关 | 同上 |
| 训练（实验网格） | XGBoost | `n_estimators=300, max_depth=5, lr=0.05` | `core/models/xgboost/xgboost.py:37-48` |
| 训练（实验网格） | CNN 实际滤波器 | `sequence_filters=64, environment_filters=64, fusion_filters=128` | `core/models/cnn/cnn.py:517-519` |
| 训练（experiment） | Transformer | d_model=64, nhead=4, layers=2 | `transformer.py:148-158` |
| 训练（ultimate） | 10 折 KFold(shuffle, seed 42)、每折 15 epochs、AdamW lr 1e-3、batch 256 | — | `workflows/prediction/predict.py:328-351,409-423,743-748` |
| 训练（ultimate） | XGBoost 最优 `n_estimators=200, max_depth=4`；MLP `hidden_dim1=256, dropout=0.3` | — | `ultimate_*_config.json` |
| 线性 | 形式 | Moore-Penrose 伪逆 + 偏置（`y = Xw + b`），`use_scaler=False` | `linear_regression.py:56-110` |

**每个实验报出的指标是什么**（容易误解，单独说明）：单次 `0.7/0.15/0.15` 留出划分（`workflows/training/data_digging.py:407-409`），训练时按验证损失早停并**回滚到 best epoch 的 checkpoint**（不是最后一轮、也不是多轮平均）(`core/models/cnn/cnn.py:684-743`、`mlp.py:595-655`、`transformer.py:622-681`)，因此**每个实验只有 1 个测试集 R²**，不是 CV 均值 —— 只有 ultimate 模型才是 10 折 CV。

⚠ **`conv_channels1/2` 未生效**：实验网格与 ultimate 都把 `conv_channels1/2` 写进 config，但 `core/models/cnn/cnn.py::train()` 的形参名是 `sequence_filters/environment_filters/fusion_filters`，`workflows/training/train.py:423-434` 按签名过滤 kwargs → **记录的是 32/64，模型实际用默认 64/64/128**。

---

## 4. 核心：每个数字的来源与加权

> 用法：**产物 → 池子（谁进来了）→ 合成规则（怎么加权）→ 代码**。全项目跨实验聚合一律**等权**；**没有任何按样本数 n 的加权平均**。

| # | 数字 / 产物 | 池子 | **合成规则（关键）** | 代码 |
| ---: | :--- | :--- | :--- | :--- |
| 1 | `mixed_cell_line_result.csv` 的 R²/RMSE/MAE/Pearson/Spearman | 同 `(model, environment)` 的全部 run（CNN 按 kernel 分开命名） | **对 4 个随机种子等权算术平均**（`groupby(["model","environment"]).mean()`）；**平均前先剔除发散行** | `analysis/collect_results.py:291-309` + `:178` |
| 2 | `baseline.csv` 的 mixed 行 | 同上（4 seed） | 跨 4 seed 等权平均，`cell_line="none"` | `collect_results.py:368-378`（注释：「对 mixed 模式跨 4 个随机种子求平均」） |
| 3 | `single_cell_line_result.csv` / `all_cell_line_result.csv` | 各实验（single/all 只有 seed 42） | **不平均，一行 = 一次实验** | `collect_results.py:270-289` |
| 4 | 论文 **Table 2**「R²_median / R²_mean」 | `prediction_summary.csv`（每 (model,split) **仅 1 行**） | ⚠ **实为"64 个实验的均值"这 1 个数再取中位 → 中位=均值**；发散行未剔除，`diverged` 只数到 1 | `paper/make_assets.py:487-508`（见 §6 发现 1） |
| 5 | `prediction_summary.csv` | `experiment_table.csv` 该 (model,split) 的 64 个实验 | 等权均值 + std(ddof=1) + 实验计数 | `analysis/prediction.py:11-21` |
| 6 | ultimate `cv_r2_mean` | 同一 mixed 数据（16 749 样本）的 10 折 | **10 折均值 → 超参网格中取 CV R² 最大 → 全量重训** | `workflows/prediction/predict.py:476-560` |
| 7 | `factor_level_ci.csv`（Fig.7 / Table 3 的 CI） | 每个因子的 main effect 行 | **两步等权**：先 `groupby(model)` 求均值（跨背景/seed）→ 再对 **7 个模型** bootstrap 2000 次 | `paper/make_assets.py:356-377`（注释：「equal weight per model」） |
| 8 | `environment_cross_model.csv` | 7 个模型的 main ΔR² | **7 模型等权均值** + min/max + 正负计数 + 每模型一列 | 产物存在；⚠ 生成脚本不在仓库 |
| 9 | `bootstrap_edge_by_factor.csv`（Fig.3C） | 每条 lattice edge `(split,cell,model,parent,child)` 的多个 seed | **先按 edge 跨 seed：estimate=mean、ci_low=min、ci_high=max、excl_all=all(...)（保守并集）**；再按因子计边数 | `make_assets.py:702-723` |
| 10 | `bootstrap_results.csv` | 同 `(split,cell,model,seed)` 的两次运行逐样本预测 | 逐样本配对重采样；B=2000；**每 seed 一行，不跨 seed 平均** | `tasks.py:141-198` |
| 11 | 环境主效应 `main_r2_delta` | (split,cell,model,env) | **先跨背景均值 → 再跨 seed 均值** | `analysis/environment/incremental_effect.py` |
| 12 | 条件增量 / DAG 边 Δmetric | (split,cell,model,env,background) / 组合对 | 同 seed 内配对 → 再跨 seed 等权平均 | 同上、`factorial_dag.py` |
| 13 | 成对交互 `interaction_r2` | (split,cell,model,a,b) | 每 seed 内（含 b 均值 − 不含 b 均值）→ 跨 seed 均值 | 同上 |
| 14 | `cnn_kernel_paired.csv`（Table 4：+0.0423 / +0.0557） | 192 组配对（同 cell/env/seed 的 k5−k3、k7−k3） | **配对差值** + bootstrap CI + 正比例 | 产物存在；⚠ 生成脚本不在仓库 |
| 15 | `cross_model_position_consistency.csv`（Spearman 0.28–0.61、top-3 0.30–0.53） | 每 (cell_line, environment) 的 5 模型 23 位置归因谱 | 模型**两两** Spearman → 模型对**等权平均**；top-3 重叠同理 | 产物存在；⚠ 生成脚本不在仓库 |
| 16 | `position18_efficacy_by_base.csv`（C−A = +0.090/+0.092/+0.028/−0.015） | 每 (cell_line, 位置18碱基) 的**全部原始实测样本**：HCT116 4 239 / HEK293T 2 333 / HeLa 8 101 / HL60 2 076（合计 16 749） | **直接对样本求 count/mean/median/std（等权 per 样本）**；位置 18 = `sgRNA[17]`；不先按实验平均、不按实验数加权。⚠ 生成脚本缺失，但**数值已逐位复现** | 产物存在；反推可精确复现 |
| 17 | 归因谱类表（`position_profile_by_model`、`region_attribution`、`position18_attribution`、`cnn_ism_position_profile`、`kernel_position_profile`） | `tables/attribution_summary.csv`（331 200 行；其中 `cnn_ism`、`cnn_ig` **各 79 488 行 = 全部 576 个 CNN 实验**） | 位置×通道先汇总 → **模型内归一化** → **跨实验/上下文等权平均**；`position_profile` 把 cell/env/split/kernel/seed **全部混在一起**（每模型 1 条 23 维谱），`kernel_position_profile` **按 kernel 分开不混合**，`region_attribution` 保留 cell_line × env(all/sequence)，`position18_attribution` 保留 cell×env×split。CNN 的**代表方法取 `cnn_ig`**（每模型只取一种，不跨 IG/ISM/SHAP 平均） | `paper/make_assets.py:32-33`（PRIMARY 映射）；⚠ 这些 CSV 的生成脚本不在仓库，数值只能近似反推（§6 发现 3） |
| 17b | `cellline_effects.csv`（84 行 = 3 split × 7 模型 × 4 因子） | 直接抄 `environment_main_effects.csv` 的 `main_r2_delta` | **不重算、不再平均**；按 (split, model, factor) 分组把各细胞系抄成 `effect_<cell>` 列；**mixed 的 `cell_line="none"` 被当作第 5 个"细胞系"**（`effect_none`） | `analysis/pipeline.py:389-392` → `cellline/consistency.py:146-194` |
| 17c | `environment_by_cellline.csv`（20 行） | `environment_main_effects.csv` 的 **3 split × 7 模型** 行 | 剔除 \|ΔR²\|>10 后按 `(factor, cell_line)` **等权均值 + 计数**（无 n 加权）；本批 n = 12/14/12/12/6（`all` 与 `single` 数值逐位相同→重复计入） | 生成脚本缺失，但**数值可精确复现**（如 ctcf/hct116 = 0.004784333, n=12） |
| 17d | `summary/feature_importance/*_importance.md`（7 个文件） | 各实验目录的 `*_feature_importance.csv` | **完全不聚合**：每 (实验, 特征) 1 行；4 个 mixed seed 变成 4 行同键重复（无 seed 列）；CNN 按 kernel 拆 3 个文件 | `analysis/importance_extraction.py:266-296,539-547` |
| 17e | `feature_importance/key_regulatory_biomarkers.csv`（652 行） | 5 模型族 7 配置；CNN 用 `CNN_ISM`、显著性用 `ISM_SNR`；线性用 BH-FDR，非线性用 SNR 阈值 2.5/1.8/1.2 | **仅 mixed 聚合**：**先剔除不显著行**，再 `groupby(split,cell,env,model_key,feature).mean()` → **只对"显著种子"做等权算术平均**；single/all 逐实验保留 1 行；kernel 不混合 | `importance_extraction.py:735-741,787-855`（已数值验证：某键 = 3 个显著 seed 的均值） |
| 18 | 项目原有 CNN ISM | 每次实验的测试样本 | **样本级 \|Δŷ\| 均值 → 每实验一个值（CSV 行）→ 分析层再对实验等权平均**；无符号 | `core/models/cnn/cnn.py:284-311` |
| 19 | 本会话 **position-18 signed substitution ISM** | 位置 18 = C 的 5 080 条 guide × 19 个模型 | 样本级 Δ → **每模型一个均值（7 个 pooled 模型等权）**；稳定性按 40 个配置**等权计数**；B=10 000 | `docs/paper_analysis/position18_signed_substitution_ism.py` |
| 20 | `赛道二_results.csv` 候选排序（20 行，`训练方式_细胞系 = mixed_all`） | 目标待测集 `data/candidate/todo_data.CSV` | 每个 ultimate 模型预测后 clip 到 [0,1] → **consensus = `cv_r2 > 0` 的模型等权平均**（无则全部）→ 按 consensus 取 Top-K。**本批实际只用 6 个模型**：`CNN(7|3)` 因 `cv_r2 = −0.016 < 0` 被排除（但它仍出现在明细串里：`…\|CNN(7\|3):0.76`） | `workflows/prediction/predict.py:651-700`；实测 `对应模型` 列 = `Ultimate_Consensus (Linear+XGBoost+MLP+Transformer+CNN(3\|3)+CNN(5\|3))` |
| 21 | motif 候选 596 / FDR<0.05 64 个（GAGG OR 1.11 FDR 0.030；GGGG OR 1.38 FDR 7e-6） | `motif_instances.csv` 的 seqlet | Fisher exact + **BH-FDR（族内）**；跨细胞系**合并 2×2 计数**；方向来自 measured efficacy 对比 | `motif_enrichment.csv` |
| 22 | Evidence tier（RRBS Tier1、DNase Tier2、CTCF/H3K4me3 Inconclusive） | 因子级 coverage + 一致率 + CI + permutation FDR | 规则判定（非平均），见 §2.2 | `evidence/integration.py:43-65` |
| 23 | `importance_vs_delta_r2.csv` | (model, split, cell, factor) | 位点 `|importance|` **求和** → 跨 environment 上下文算术平均 → 按上下文总和归一化；统计列取**最小 FDR** | `analysis/importance_metrics.py` |
| 24 | 论文 Table 1（各细胞系 n / mean / median / sd / GC） | 该细胞系全部样本 | 直接对样本求统计量；GC = G/C 数 / (23×n) | `make_assets.py:468-485` |
| 25 | LOCO（`all`）性能 | 留一细胞系的实验 | 按 (model, cell_line) 等权平均 | `analysis/prediction.py:24-35` |

---

## 5. 「不是平均」的规则清单

| 位置 | 规则 | 代码 |
| :--- | :--- | :--- |
| ultimate 超参选择 | **取 CV R² 最大**的配置 | `workflows/prediction/predict.py:516-522` |
| 候选排序 | consensus = 正 CV R² 模型**等权平均**（不是按 R² 加权）；`cv_r2 ≤ 0` 的模型整体剔除 | `workflows/prediction/predict.py:680-681` |
| 论文边级 CI | 跨 seed 取 `min(ci_low)/max(ci_high)`、`all(不跨0)` → **保守并集** | `make_assets.py:711-715` |
| Evidence 的 permutation p/FDR | 该 factor 所有行取 **min** | `evidence/integration.py` |
| Evidence 的 cell-line 一致性 | 该 factor 的 `context_label` **众数** | 同上 |
| cell-line 异质性 | `max\|effect\| / median\|effect\|` | `cellline/consistency.py` |
| 位置/区域代表值 | **argmax / top-k**（峰值位置、top-3 重叠） | `cross_model_position_consistency.csv` |
| Importance 统计列 | 取**最小 FDR** | `importance_metrics.py` |
| 数据级异常 | 取 `max\|weight\|` | `data_QC.py` |
| 发散处理 | 汇总表**剔除**发散行；`all_experiments.csv` **保留**全部 | `collect_results.py:178` |
| 实验指标 | 取 **best-validation-loss epoch** 的 checkpoint（非最后一轮、非多轮平均） | `cnn.py:684-743` 等 |
| 断点续跑 | 有完成标记就**复用旧结果**，不重算、不平均 | `workflows/prediction/predict.py:873-877,950-955` |
| 已完成的训练实验 | `data_digging` 直接**跳过**（取已存在的 run 目录） | `workflows/training/data_digging.py:197-247` |
| 目标输入文件 | 取 `sorted(glob("*.csv"))[0]` / `csv_candidates[0]`（**取第一个**） | `app/desktop/backend_runner.py:159-161,232-234` |
| benchmark npy | 已存在则**复用不重算** | `app/desktop/backend_runner.py:152-155` |
| 归因方法 | 每个模型**只取一种代表方法**（CNN→`cnn_ig`），不跨 IG/ISM/SHAP 平均 | `make_assets.py:32-33` |
| `key_regulatory_biomarkers` | **先剔不显著种子，再等权平均**（只对显著 seed 求均值） | `importance_extraction.py:802-816` |
| 权重 | **无任何 n 加权**；跨实验一律等权 | 全仓核对 |

---

## 6. 审计发现（汇总过程中发现的真实问题）

### 发现 1：论文 Table 2 口径错误（真实 bug，已影响 `paper/tables/tab2_prediction.tex`）
`paper/make_assets.py:487-508` 从 `prediction_summary.csv`（每 (model, split) 仅 1 行，共 21 行）取 `R2_mean`，再对该 1 行求中位数/均值：

* `R2_median` ≡ `R2_mean`，`R2_sd` = `NA`，但表头声明 "Medians over experiments are reported"；
* `diverged` 统计的是行数（linear 显示 1，实为 **56/192**：single 21、mixed 14、all 21）；
* linear 行被发散值主导：**single = −1.87×10¹⁶、mixed = −1.44×10¹⁸**，已进入论文 PDF。

从 `experiment_table.csv`（1 344 行）重算的正确中位数：

| model | single 中位（全部） | single（剔除发散） | mixed 中位（全部） | mixed（剔除发散） | 发散数 |
| :--- | ---: | ---: | ---: | ---: | ---: |
| cnn(3\|3) | 0.0351 | 0.0351 | 0.0602 | 0.0602 | 0/0 |
| cnn(5\|3) | 0.0569 | 0.0569 | 0.1346 | 0.1346 | 0/0 |
| cnn(7\|3) | 0.0795 | 0.0795 | 0.1481 | 0.1481 | 0/0 |
| mlp | 0.0851 | 0.0851 | 0.1108 | 0.1108 | 0/0 |
| transformer | 0.0687 | 0.0687 | 0.1103 | 0.1103 | 0/0 |
| xgboost | 0.1155 | 0.1155 | 0.1612 | 0.1612 | 0/0 |
| linear | −0.0014 | **0.0874** | 0.0772 | **0.0831** | 21 / 14 |

论文正文写的「中位 R² 0.035–0.115（single）」与真中位数一致，而 Table 2 显示的是均值（如 cnn3 single 0.038）→ **正文与表格口径不一致**。

### 发现 2：`all`（LOCO）划分在本批退化为 `single`（448/448 逐位相同）

**本来的设计（你说的是对的）**：`core/data/splitting/cell_line_division.py:219-236` 就是"3 个细胞系训练、1 个细胞系测试"的留一划分：
* `train_cls = 除 test_cell_line 外的细胞系`，`train_data = 合并这 3 个细胞系`；
* 再对训练池做 **`train_fraction=0.85, validation_fraction=0.15, test_fraction=0.0`**（`:225`，**注意这里写死 85/15，不使用 CLI 的 0.7/0.15/0.15**）；
* 测试集 = 被留出的细胞系**全部样本**（100 %）。

**实际发生的**：该分支要求同时满足「`test_cell_line` 有值」且「加载了多个细胞系」。但批量运行器 `workflows/training/data_digging.py:281-310` 只传 `--cell-line <cell>`，**从不传 `--cell-lines`**；`workflows/training/train.py:661-662` 于是把 `cell_lines` 构造成 `[该细胞系]`，`divide_data:320` 只加载 1 个数据集，命中 `split_all_cell_lines:214-217` 的退化保护 → **改走 `split_single_cell_line`，即单细胞系 70/15/15**。

**量化证据（修复前）**：
* `all_cnn_sequence_heldout_hct116_kernel_3` 的 `cell_lines = ["hct116"]`，train/valid/test = 2967/635/637，合计 **4239 = HCT116 自身样本数**（真 LOCO 的训练池应为 16749−4239 = 12510，按 85/15 拆成 ≈10 633/1 877）；
* 384 个可解析的 `all` 配置**全部** `cell_lines` 长度为 1；
* 448 个 `all` run 与同 `(model/kernel, environment, cell line, seed)` 的 `single` run，五个指标 **448/448 完全相等**（差值 < 1e-12）。

**→ 代码已于 2026-09-13 修复并验证；本批数据按用户决定「不在本地重跑」，批次已完整还原到修复前状态（`all` 仍是退化的旧产物）。**

改动两处：
1. `workflows/training/data_digging.py`：`build_command` 新增 `loco_cells` 参数，`main` 传入 `args.cell_lines or CELL_LINES`；当 `split_type == "all"` 时命令追加 `--cell-lines <全部细胞系>`（保留原有的 `--cell-line <留出细胞系>`）。注意必须传**全集**而不是"其余三个"——`split_all_cell_lines` 要求被留出的细胞系也在已加载的 `datasets` 里，否则会掉进另一个 fallback 分支。
2. `core/data/splitting/cell_line_division.py`：**新增 `create_train_valid_indices()`**（train/valid 两路，85/15）并让 LOCO 分支改用它。原代码调用 `create_split_indices(..., test_fraction=0.0)`，而该函数的入口校验 `validate_split_fractions` 要求三段比例**均 > 0** → 该分支只要被走到就必然抛 `ValueError`，**这是 LOCO 从未生效的第二个原因**（与运行器不传 `--cell-lines` 相互叠加）。

**修复后已验证的划分**（本地试跑，`models/.../all_*_heldout_<cell>/*_info.txt`，`cell_lines` 均为 4 个细胞系）：

| 留出细胞系 | train (85 %) | valid (15 %) | test (100 % 留出系) |
| :--- | ---: | ---: | ---: |
| HCT116 | 10 633 | 1 877 | 4 239 |
| HEK293T | 12 253 | 2 163 | 2 333 |
| HeLa | 7 350 | 1 298 | 8 101 |
| HL60 | 12 472 | 2 201 | 2 076 |

（`train + valid = 0.85/0.15 × (16749 − 留出系样本数)`，逐项吻合；且 LOCO 指标不再与 `single` 相同，例：`all_linear_sequence_heldout_hct116` R²=0.1142 / test n=4 239 vs `single_hct116_linear_sequence` R²=0.0907 / test n=637。）

**当前批次状态**：`all` 的 448 个旧产物已完整还原（`results/`+`models/`+`logs/` 各 448 个目录，`cell_lines` 仍为单细胞系、`all` 与 `single` 仍 448/448 逐位相同）；`summary/metrics_tables` 与 `summary` 未刷新，与还原后的数据保持自洽。本地试跑产生的中间产物已删除，临时备份目录已清理；重跑日志保留在 `logs/loco_rerun_20260913.log`。

**在 HPC / 其他机器上重跑的步骤**（代码已修好，只需搬运代码；运行器会自动跳过已完成的 run）：
```bash
python workflows/training/data_digging.py --batch-name batch_20260909_full --split-types all --workers <N>   # ① 真 LOCO 重跑
bash scripts/refresh_after_loco_rerun.sh                                                  # ② 重建汇总+summary 并核对
```
该脚本会核对 448 个 `all` run 的划分形状、`all`↔`single` 是否仍逐位相同，并产出 `results/analysis/loco_after_fix_summary.{md,csv}`（LOCO R² 按模型/留出系统计）。

**后果（修复前，即当前批次的状态）**：`loco_performance.csv`、论文中"留一细胞系/跨细胞系泛化"的表述缺乏支撑；`all` 的 448 次运行与 `single` 完全重复（等于浪费了 1/3 算力）。

### 发现 3：`docs/paper_analysis/` 中 11 个 CSV 无生成脚本
只有 `bootstrap_edge_by_factor.csv`、`factor_level_ci.csv` 由 `make_assets.py:723,732` 生成；其余 11 个（`nucleotide_frequency_by_position`、`position18_efficacy_by_base`、`position18_attribution`、`cross_model_position_consistency`、`position_profile_by_model`、`region_attribution`、`cnn_ism_position_profile`、`kernel_position_profile`、`cnn_kernel_paired`、`environment_cross_model`、`environment_by_cellline`）全仓库 grep 无写入点，而 `docs/paper_analysis/README.md:3-5` 声称由 `make_assets.py` 重新计算 → **README 与代码事实不符，这些表目前无法一键复现**（其超参/种子无法确认）。

### 发现 4：`calculate_delta_R2` 的基线 key 不含 seed
`analysis/collect_results.py:221-243` 的基线匹配键不含 `random_seed`，与 `incremental_effect.py` / `data/validation.py` 的"同 seed 配对"原则不一致 → mixed 的 4 个 seed 之间**可能发生跨 seed 相减**（代码无保护，未确认实际影响）。

### 发现 5：文档间数值不一致
`docs/paper_claim_provenance_v2.md:21` 仍写 HEK293T 的 C−A = **−0.016**；最新核对（未舍入 −0.0155）与已修正的论文正文均为 **−0.015**。

### 发现 6：同一仓库存在两套「CNN 重要性」定义
`summary/feature_importance/key_regulatory_biomarkers.csv` 对 CNN 用 **`CNN_ISM` + `ISM_SNR`**（`importance_extraction.py:735-741`）；而 `analysis/importance_metrics.py:55-58` 的 `PRIMARY_METRICS` 用 **`CNN_IG` 且显式排除 `CNN_ISM`**（`:73`），供 `analysis/visualization/importance_delta.py:29` 与 Importance–ΔR² 使用。引用头条数字时必须说明用的是哪一套；论文若混用会自相矛盾。

### 发现 7：能力边界（非 bug）
项目原有 ISM/IG/SHAP/attention 全部为**无符号幅度**，只能做重要性/稳健性；有符号分析只能靠线性系数（56/192 发散）或本会话新增的 signed substitution ISM。

---

## 7. 缺口与未确认项

| 项 | 状态 / 原因 |
| :--- | :--- |
| `environment_shapley` | 未实现（注册表存在，无 runner） |
| Transformer IG | 不存在（只有 attention，不作 motif extractor） |
| ANOVA per-group 交互 | unavailable（每格 n=1，设计饱和） |
| ANOVA 的 FDR | 无（`anova_results.csv` 无 FDR 列） |
| `bootstrap_difference_ci`、`paired_metric_ci` runner、`anova_interface`、`rules.py::classify_*` | 已实现但**仅单测调用**，未进主流程 |
| `FdrFamilyConfig.enabled_families` | 命名与实际 `family_key` 不一致，且未被 `apply_fdr` 使用 |
| `Normalized efficacy` 归一化算法 | 仓库内无实现（README 称来自 DeepCRISPR） |
| PAM 类型声明 | 仅由序列模式与命名推断（无配置显式声明 NGG/SpCas9） |
| `data/feature_config.user.json` | README 提到但仓库内不存在 |
| `all` 退化 / `conv_channels` 未生效 | 代码行为确定，是否设计意图**未确认** |
| `summary/tables/*` 与 `summary/tables/*` | 3/5 个文件 md5 不同，未定位到复制/生成代码 |
| XGBoost 版本 | `requirements.txt:16` 钉 `xgboost<=2.0.3`，环境实装 3.4.1；网格实验用 `early_stopping_rounds=30`+`best_iteration`，但 `predict` 未传 `iteration_range`，是否按 best_iteration 截断未独立验证 |
| 16 个环境名 | `build_active_environment_combinations` 返回 17 个（`all` 重复），由 `workflows/training/data_digging.py:63-94` 去重为 16；绕过 data_digging 直调会重复计数 |
| 湿实验 / 脱靶 / 编辑窗口 / 结构输入 / 生成式设计 | 缺口（见 `paper_claim_provenance_v2.md` 表 3） |

---

## 8. 复现命令

```bash
# ① 全量统计分析（bootstrap / permutation / BH-FDR / cell-line / motif；ANOVA 默认关闭）
python -m analysis.pipeline --batch-dir results/batches/batch_20260909_full
python -m analysis.pipeline --batch-dir results/batches/batch_20260909_full --analysis-plan plan_anova_on.json  # 打开 ANOVA

# ② 论文资产（图表 + Table 2/3 + factor_level_ci.csv）
python paper/make_assets.py

# ③ 单页 A4 摘要
python paper/make_position18_summary.py

# ④ 位置 18 两个审计脚本（只读 / 复用已训练模型，不重训）
python docs/paper_analysis/position18_ism_audit.py
python docs/paper_analysis/position18_signed_substitution_ism.py

# ⑤ 统计接线测试
python -m unittest analyse.tests.test_stats_wiring -v
```

---

*本文由代码与真实批次产物核对生成；三份完整勘察记录见 `docs/_recon_statistics.md`、`docs/_recon_parameters.md`、`docs/_recon_provenance.md`。标注「未确认」的条目在后续核对后会更新。*
