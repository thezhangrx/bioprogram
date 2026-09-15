# 只读勘察：CRISPR-Cas9 项目生物学/序列参数与数据获取流程

> ⚠️ **历史勘察快照（重构前）**：本文记录 2026-09-14 目录重构**之前**的结构，其中的路径名（`src/`、`analyse/`、`data/proceeded_data/`、`results/<batch>`）均为旧路径。
> 当前权威结构见 `README.md` 与 `docs/architecture/`；科学定义见 `docs/science/`。


> 勘察范围：`data/`、`src/`、仓库根脚本（`train.py`/`data_digging.py`/`predict.py`）、`models/batch_20260909_full/`、
> `results/batch_20260909_full/summary/`。本文件为新建产出，未修改任何已有文件。
> 文中每条结论都给出 `file:line` 或路径证据；无法从代码/产物确认的写 **未确认**。

---

## 0. 总览：数据流与目录

```
data/source_data/*.csv                                  原始表（含未编码的表观轨道字符串）
   │  src/feature_engineering.py   （pipeline step: feature_engineering）
   ▼
data/proceeded_data/*.npy + *_metadata.csv + feature_schema.json + feature_engineering_summary.csv
   │  data_digging.py  →  逐实验调用 train.py（网格）
   │  predict.py       →  通道裁剪 + 10 折 CV + 全量重训（终极模型 / 候选）
   ▼
models/<batch>/<run_name>/  +  results/<batch>/<run_name>/  +  logs/<batch>/<run_name>/
   ▼
results/<batch>/summary/ultimate/*  +  results/<batch>/summary/赛道二_results.csv
```

- 特征工程入口：`src/feature_engineering.py`，其在统一编排层中的命令定义为
  `pipeline/steps.py:220-224`（`--source-dir data/source_data --output-dir data/proceeded_data --config data/feature_config.json`，
  见 `src/feature_engineering.py:1967-2005` 的 CLI 默认值）。
- 网格训练入口：`pipeline/steps.py:227-246` 调 `data_digging.py`；候选生成入口 `pipeline/steps.py:248-270` 调 `predict.py`。
- 仓库 README 也画了同一条主线：`README.md:188-198`、`README.md:341`。
- 另有一条**向导用的旁路**（非本项目主数据来源）：`Input/backend_runner.py:62-112`
  `convert_raw_csv_to_npy()` 硬编码 8 通道（`Input/backend_runner.py:129`）并直接写 `*_features_23x8.npy` / `*_features_184.npy` / `*_labels.npy`。

### 0.1 原始表列名（事实）

`data/source_data/hct116.csv` 表头（`head -3` 实测）：

```
Chromosome,Start,End,Strand,sgRNA,CTCF,Dnase,H3K4me3,RRBS,Normalized efficacy
```

代码侧的“必需列”生成逻辑：`src/feature_engineering.py:1030-1060`（`Chromosome/Start/End/Strand/sgRNA` + 目标列 + 启用的表观列）；
目标列常量 `TARGET_COLUMN = "Normalized efficacy"` 在 `src/feature_engineering.py:134`。

### 0.2 各细胞系样本数（去重前后，事实）

`data/proceeded_data/feature_engineering_summary.csv`（全量 5 行，已读入）：

| cell_line | original_samples | duplicate_rows | final_samples | channel_count | feature_count |
|---|---|---|---|---|---|
| hct116 | 4239 | 0 | 4239 | 8 | 184 |
| hek293t | 4566 | 2233 | 2333 | 8 | 184 |
| hela | 8101 | 0 | 8101 | 8 | 184 |
| hl60 | 2076 | 0 | 2076 | 8 | 184 |

合计：原始 18982 → 去重 2233 → 最终 **16749**（= `ultimate_summary.json` 的 `n_samples`）。
去重规则：只删整行完全相同的记录（`pandas.DataFrame.duplicated(keep="first")`，`src/feature_engineering.py:1067-1127`，调用点 `1218-1223`）。

---

## 1. 序列层面

### 1.1 sgRNA 长度 = 23 nt

- 常量：`src/feature_engineering.py:132` `SEQUENCE_LENGTH = 23`；schema 中 `"sequence_length": 23`（`data/proceeded_data/feature_schema.json`）。
- 强制校验（长度不等于 23 直接抛错）：`src/feature_engineering.py:332-355`（`validate_sequence`）。
- 实测：四个 source CSV 的 `sgRNA` 长度集合均为 `{23}`；`End - Start + 1 = 23`（坐标跨度 23 nt）。

### 1.2 位置编号：1-based 命名 vs 0-based 张量下标

- 权重/特征名用 **1-based**：`generate_vector_feature_names` 从 `range(1, SEQUENCE_LENGTH+1)` 生成 `pos1_*`…`pos23_*`
  （`src/feature_engineering.py:919-951`，关键循环 `940-949`）。
- 张量编码用 **0-based**：`enumerate(sgrna)` 的下标直接作为矩阵行号（`src/feature_engineering.py:406-427`；表观同理 `467-485`）。
- 转换关系只出现在“命名 ↔ 下标”的映射处：`pos{N}` 对应张量下标 `N-1`。
  显式示例：`docs/paper_analysis/position18_signed_substitution_ism.py:44-45`
  （`POS_1B = 18`，`L = POS_1B - 1`，注释 “1-based sgRNA position”）。
- 巡检脚本同时交叉验证编号：`docs/paper_analysis/position18_signed_substitution_ism.py:59-71`（`check_numbering`）。

### 1.3 PAM 位置

- 输入 sgRNA 是“20 nt protospacer + NGG PAM”的完整 23 nt，代码**不做 PAM 切分**，整条 23 nt 进入张量。
- PAM 位于 **第 21–23 位，其中 22–23 位为 GG**。证据：
  - 实测：四个 source CSV 中 `sgRNA[21:23] == "GG"` 的比例均为 **1.0**（100%）；第 21 位为 A/C/G/T 混合。
  - 代码侧显式断言：`docs/paper_analysis/position18_signed_substitution_ism.py:75-77`
    `pam_gg = sg.str[21:23].eq("GG").mean()`，键名为 `"pam_pos22_23_is_GG"`。
  - 另一处把 PAM 排除在“驱动位点”之外：`predict.py:623`（`range(min(20, ...))`，即只用前 20 nt 推导候选驱动特征）。
- 未确认：PAM 的生物学类型（是否为 SpCas9 NGG）在代码/配置中无显式声明；只从序列模式与 README 数据集描述推断。

### 1.4 链方向 Strand：记录但不使用，无 reverse-complement

- `Strand` 出现在必需列与元数据列中：`src/feature_engineering.py:136-143`（`METADATA_COLUMNS`）、`1037-1044`（`get_required_columns`）。
- 编码只读 `row["sgRNA"]`：`src/feature_engineering.py:842-845`（`encode_sgrna(row["sgRNA"], ...)`），`Strand` 从未参与任何计算。
- 全仓库 `*.py` grep `reverse_complement|revcomp|complement|反向互补` **无任何命中**（已排除 `.venv`/`.git`）。
- 结论：`+` / `-` 两条链的 sgRNA 均按 CSV 中给出的 5'→3' 方向直接 one-hot，不做反向互补。
- 实测链分布：hct116 2176+/2063−、hek293t 2135+/2431−、hela 4182+/3919−、hl60 1054+/1022−（两链都真实存在）。

### 1.5 非 ACGT 字符处理

- **序列通道**：`encode_sgrna` 遇到不在 `sequence_channels`（A/C/G/T）中的字符**直接抛 `ValueError`**，不做 N→全 0 或跳过：
  `src/feature_engineering.py:411-418`。实测四个 source CSV 的 sgRNA 无任何非 ACGT 行（`fullmatch` 检查通过）。
- **表观通道**：`encode_per_position_binary` 对不在 `encoding` 字典中的符号同样抛错：`src/feature_engineering.py:471-478`；
  当前 `encoding` 只允许 `A`(→1) 与 `N`(→0)（`data/feature_config.json`）。
  实测各表观列字符集合：CTCF/H3K4me3/RRBS 为 `{A,N}`；**Dnase 在 hek293t 与 hela 中只有 `A`**（无 N）。
- **预测侧（目标数据集）**：非 ACGT 碱基被静默忽略（保持全 0），缺失的表观列整通道置 0 并打印 WARN：
  `predict.py:196-221`（`s.ljust(23,"N")` 截断/补齐；`b in base_to_plan` 才置 1）。
- 未确认：`Normalized efficacy` 的归一化算法/是否按细胞系归一，代码中无实现、也无可复现说明（README 称数据来自 DeepCRISPR/Chuai et al. 2018，未在代码内验证）。

---

## 2. 通道与编码

### 2.1 通道构成（共 8 通道）

配置：`data/feature_config.json`：

```json
"sequence_channels": ["A","C","G","T"],
"environment_features": [ CTCF, Dnase, H3K4me3, RRBS ]  // 均为 "type": "per_position_binary", "encoding": {"A":1,"N":0}, "enabled": true
```

schema 汇总（`data/proceeded_data/feature_schema.json`）：

- `channel_count: 8`，`feature_count: 184`，`sequence_length: 23`
- `channel_names: ["A","C","G","T","CTCF","Dnase","H3K4me3","RRBS"]`（顺序即张量最后一维顺序）
- `feature_names`: `pos1_A … pos23_RRBS`，展平顺序为“先位置后通道”（每 8 个一组）。

代码侧：通道规范由 config 拼装，`src/feature_engineering.py:757-806`（`get_channel_specs`）；
schema 生成 `src/feature_engineering.py:958-1023`；碱基通道常量 `147-152`；
组合模块的同一常量 `src/input_control/cell_environment_combination.py:165-170`。

### 2.2 序列通道编码（per-position 4-碱基 one-hot）

- 每个位置一个长度 4 的 one-hot：`A→[1,0,0,0]`、`C→[0,1,0,0]`、`G→[0,0,1,0]`、`T→[0,0,0,1]`
  （docstring `src/feature_engineering.py:362-375`；实现 `398-427`，赋值 `encoded[position, channel_index] = 1.0`）。
- 张量形状 `(23, 4)`，`dtype=float32`（`398-404`）。

### 2.3 表观通道编码（per-position binary）

- 每个表观轨道是长度 23 的字符串（`A`/`N`），逐位查表：`value=1.0 if encoding[value]`，输出 `(23,1)`
  （`src/feature_engineering.py:436-487`，关键赋值 `480-485`）。
- 当前映射：`A→1.0`（该位点有信号/可用）、`N→0.0`（未知/缺失）。**没有 0/1 之外的中间值**（除非改用 `per_position_numeric` 类型，`src/feature_engineering.py:608-626`）。
- 目标数据集侧的等价规则：字符串位 ∈ `{'1','A','Y','T'}` → 1，其余 → 0（`predict.py:213-215`；向导旁路同规则 `Input/backend_runner.py:100-102`）。

### 2.4 总通道数与展平维度：23×8=184 与 23×4=92

- `build_feature_matrix` 把 `[序列(23,4)] + [4 个表观(23,1)]` 沿 axis=1 拼接，得到 `(23,8)`，并断言通道数一致
  （`src/feature_engineering.py:813-912`，拼接 `885-888`，形状断言 `890-910`）。
- **184 = 23×8**：2D 模型（linear / xgboost / mlp）的输入。展平在 `flatten_features`
  （`src/input_control/cell_environment_combination.py:1243-1261`），调用点 `prepare_model_input` `1295-1350`。
  环境组合只做 **mask 置零、不删列**（`apply_environment_combination` `1151-1236`，mask 构造 `1063-1144`），
  因此**即使 `environment=sequence`，2D 模型输入仍是 184 维（其中表观列全 0）**。
  - 实测证据：`models/batch_20260909_full/all_xgboost_sequence_heldout_hela/xgboost_config.json`
    `input_shape_train: [5670, 184]`、`feature_count: 184`；`results/batch_20260909_full/single_hct116_linear_sequence/linear_regression_info.txt`
    `input_shape_train: [2967, 184]` 而 `environment: sequence`。
- **161 = 184 − 23（LR 专用）**：线性回归额外剔除所有 `_T` 参照列（哑变量陷阱防护，T 为基准）：
  `src/linear_regression/linear_regression.py:462-488`（`select_non_t_reference_features`）、调用 `673-746`。
  实测 `linear_regression_info.txt`：`Feature count: 161`；`all_experiments.csv` 中 linear 行 `Feature count=161`。
- **92 = 23×4**：只在“通道规划 = 纯序列（4 通道）”时出现。来源是 `predict.py:101-136` 的 `build_channel_plan`
  （`target_epis` 为空/None → 只保留 A/C/G/T；裁剪+展平 `predict.py:139-142`）。
  - 实测证据：`results/batch_20260909_full/summary/ultimate/ultimate_summary.json`
    `"n_seq_channels": 4, "n_features": 92`；各 `ultimate_*_config.json` 均 `"n_features": 92`。
  - LR 在该 92 维上再剔 `_T` → **69 = 92 − 23**：`results/.../ultimate/ultimate_lr_model.json` `"n_features": 69` 且 `feature_names` 只含 `_A/_C/_G`；
    代码 `predict.py:354-362` + `src/linear_regression/linear_regression.py:468-488`。
  - 另有第三方脚本显式断言该路径：`docs/paper_analysis/position18_signed_substitution_ism.py:57-59`
    （`plan = P.build_channel_plan(schema, None)`，断言 `23 * plan["n_channels"] == 92`）。
- **23×4 作为 3D 张量的情形（CNN）**：CNN 先拿到 `(N,23,8)`，再在 `train()` 内按
  `sequence_channels`（=A/C/G/T 计数）+ `selected_environments` **切片**：
  - 切分逻辑：`src/cnn/cnn.py:566-637`；`selected_env` 为空 → 只留 `[..., :4]`（=23×4），非空 → `seq + env` 列拼接。
  - 前向再对 3D 输入做分支切分：`src/cnn/cnn.py:176-199`（sequence 分支 `186-187`，environment 分支 `191-195`）。
  - 实测：`single_hct116_cnn_sequence_kernel_3/cnn_config.json` 记 `selected_environments: []`、
    `sequence_channels: 4`、`environment_channels: 0`；`sequence_ctcf` 则为 `environment_channels: 1`。
  - 注意：**config 里记录的 `input_shape_*` 仍是裁剪前的 `(N,23,8)`**（由 train.py 在调用模型前写入，
    `train.py:538-540`），CNN 内部实际通道数另记在 `sequence_channels`/`environment_channels` 键。

---

## 3. 数据划分

### 3.1 split type 与比例

- 三种 split type：`single`、`all`、`mixed`（`train.py:45-49` `VALID_SPLIT_TYPES`；生成逻辑 `data_digging.py:125-164`）。
- 默认比例 **0.70 / 0.15 / 0.15**：
  `train.py:33-35`（`DEFAULT_TRAIN_RATIO/VALID/TEST`）、`data_digging.py:407-409`、`src/input_control/cell_line_division.py:21-23`。
- 比例校验（三者之和必须为 1；`all` 分支另用 0.85/0.15 切“其余细胞系的合并池”）：
  `train.py:207-225`；`src/input_control/cell_line_division.py:89-95`、`210-236`（`225` 行写死 `train_fraction=0.85, validation_fraction=0.15, test_fraction=0.0`）。

### 3.2 随机种子

- 全局默认：`DEFAULT_RANDOM_SEED = 42`（`train.py:31`）。
- 网格 **mixed 专用 4 个种子**：`MIXED_SEEDS = [42, 43, 44, 45]`（`data_digging.py:59`，用于构造实验 `146-147`）。
- `single` / `all` 强制 42：`data_digging.py:275`（`random_seed = seed if split_type == "mixed" else 42`）。
- ultimate：`--ultimate-seed` 默认 42（`predict.py:748`），写入 `ultimate_summary.json` 的 `"seed": 42`。
- 实测 run 名中的种子只出现 42/43/44/45，且只在 `mixed_*_seed_*` 中出现。

### 3.3 是否分层

- **不分层**。划分实现为“`np.random.default_rng(seed)` → `rng.shuffle(indices)` → 按 `floor(n*ratio)` 前后切段”：
  `src/input_control/cell_line_division.py:154-172`（`train_size = int(np.floor(...))`，前置 `max(1, ...)` 保护）。
- 全仓库 `*.py` 无 `StratifiedKFold` / `stratify=` 调用（已 grep 验证，无命中）。
- ultimate 的 CV 用 `KFold(n_splits=folds, shuffle=True, random_state=seed)`（**非分层**）：`predict.py:409-423`（构造在 `413-415`）。

### 3.4 三种 split 的实际语义（含一处重要事实修正）

| split | 代码意图 | 实际行为（本批次） |
|---|---|---|
| `single` | 单个细胞系内按 0.7/0.15/0.15 划分 | 同意图（`cell_line_division.py:195-207`） |
| `mixed` | 4 个细胞系合并后按 0.7/0.15/0.15 划分 | 同意图（`cell_line_division.py:256-273`；实测 `input_shape_train [11724,184]`，11724+2512+2513 = 16749） |
| `all` | 留一细胞系（train/valid 来自其余细胞系，test=被留出细胞系） | **退化为该细胞系内的 single 划分**（见下） |

`all` 退化的证据链：

1. `data_digging.py` 构造 `all` 实验命令时只传 `--cell-line <heldout>`，**从不传 `--cell-lines`**：
   `data_digging.py:309-310`。
2. `train.py:execute_args` 在只有单数 `cell_line` 时构造 `cell_lines = [cell_line]`：`train.py:659-666`。
3. `divide_data` 把 `cell_lines` 过滤为可用的该细胞系，只加载 1 个 dataset：
   `src/input_control/cell_line_division.py:311-322`（`load_all_cell_lines(cell_lines=[heldout])`）。
4. `split_all_cell_lines` 首行即“单细胞系退化保护”，直接返回 `split_single_cell_line`：
   `src/input_control/cell_line_division.py:214-217`。

实测交叉验证（train+valid+test 恰好等于被命名细胞系自身的总数）：

| run | input_shape_train/valid/test | 总和 | 该细胞系总数 |
|---|---|---|---|
| `all_mlp_all_heldout_hct116` | 2967 / 635 / 637 | 4239 | hct116 4239 |
| `all_cnn_sequence_heldout_hek293t_kernel_3` | 1633 / 349 / 351 | 2333 | hek293t 2333 |
| `all_transformer_sequence_heldout_hl60` | 1453 / 311 / 312 | 2076 | hl60 2076 |

进一步：把 `single_<cell>_<model>_<env>` 与 `all_<model>_<env>_heldout_<cell>` 的测试集指标对比，**数值完全相同**
（seed 同为 42，数据切分相同）：

| 配对 | single R2 / RMSE | all R2 / RMSE |
|---|---|---|
| `single_hct116_mlp_sequence` vs `all_mlp_sequence_heldout_hct116` | 0.093679 / 0.163773 | 0.093679 / 0.163773 |
| `single_hela_xgboost_all` vs `all_xgboost_all_heldout_hela` | 0.122991 / 0.165385 | 0.122991 / 0.165385 |
| `single_hl60_transformer_sequence` vs `all_transformer_sequence_heldout_hl60` | 0.096256 / 0.116633 | 0.096256 / 0.116633 |

> 结论：`all` 命名中的 “heldout” 在本批次产物中并未实现跨细胞系留出；`all` 与 `single` 是同一实验的两次运行。
> 该行为由代码路径确定；**是否为设计意图未确认**（`split_all_cell_lines` 的留一分支 `219-236` 客观存在，只是未被触发）。

---

## 4. 训练超参数：默认值与可选网格

### 4.1 统一 CLI 默认值（`train.py:599-644`，`data_digging.py:407-421` 同值）

| 参数 | 默认值 | 证据 |
|---|---|---|
| `epochs` | 100 | `train.py:625`；`data_digging.py:410` |
| `batch_size` | 64 | `train.py:626`；`data_digging.py:411` |
| `learning_rate` | 1e-3 | `train.py:627`；`data_digging.py:412` |
| `dropout` | 0.2 | `train.py:628`；`data_digging.py:413` |
| `weight_decay` | 0.0 | `train.py:629`；`data_digging.py:414` |
| `patience` | 20 | `train.py:630`；`data_digging.py:415` |
| `min_delta` | 1e-6 | `train.py:631`；`data_digging.py:416` |
| `hidden_dim1` | 128 | `train.py:636`；`data_digging.py:418` |
| `hidden_dim2` | 64 | `train.py:637`；`data_digging.py:419` |
| `conv_channels1` | 32 | `train.py:638`；`data_digging.py:420` |
| `conv_channels2` | 64 | `train.py:639`；`data_digging.py:421` |
| `sequence_kernel` / `environment_kernel` | 3（可选 3/5/7） | `train.py:640-641` |
| `train/valid/test_ratio` | 0.70/0.15/0.15 | `train.py:619-621` |
| `use_scaler` | **False**（`action="store_true"`） | `train.py:623`；`data_digging.py:424` |
| `device` | None（自动 cuda/cpu） | `train.py:642`；`cnn.py:652-655` |

参数透传机制：`train.py:350-434`（`build_train_kwargs`），**关键点 `423-434`：按 `inspect.signature` 过滤，
模型 `train()` 不接受的键会被丢弃**。网格侧参数装配在 `data_digging.py:250-321`，实验值在 `465-487`。

### 4.2 各模型构造/默认超参

| 模型 | 构造与默认 | 证据 |
|---|---|---|
| linear | `LinearRegressionModel(use_scaler=False, pinv_rcond=1e-15)`；Moore-Penrose 伪逆 + 截距（`X_bias=[X,1]`） | `src/linear_regression/linear_regression.py:56-175`（init `71-89`，fit `115-171`）；`train()` 签名 `673-698` |
| xgboost | `n_estimators=300, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=1, reg_alpha=0.0, reg_lambda=1.0, objective=reg:squarederror, eval_metric=rmse`；`early_stopping_rounds=30`，`n_jobs=-1` | `src/xgboost/xgboost.py:37-48`、`509-527` |
| mlp | `MLPModel(input_dim, hidden_dim1=128, hidden_dim2=64, dropout=0.2)`，结构 `Linear→ReLU→Dropout→Linear→ReLU→Dropout→Linear(→1)`；优化器 Adam | `src/mlp/mlp.py:96-125`；`train` `481-506`，Adam `580` |
| transformer | `TransformerModel(input_dim, max_sequence_length=23, d_model=64, nhead=4, num_layers=2, dim_feedforward=128, dropout=0.2)`；Adam | `src/transformer/transformer.py:148-190`；`train` `504-531`（`nhead=4` L522、`num_layers=2` L523、`dropout=0.2` L525），Adam `609` |
| cnn | `CNNModel(sequence_channels, environment_channels, sequence_kernel=3, environment_kernel=3, sequence_filters=64, environment_filters=64, fusion_filters=128, dropout=0.2)`；双分支（序列分支卷积核 `(k, 4)`，环境分支 `(k, E)`）+ 融合 MLP `128→64→1`；Adam | `src/cnn/cnn.py:89-199`（init `90-174`，默认值 `94-99`，融合层 `164-174`）；`train` `498-527`，Adam `671` |

**注意（CNN 的 `conv_channels1/2` 在网格中未生效）**：`cnn.train()` 的形参是
`sequence_filters / environment_filters / fusion_filters`（`src/cnn/cnn.py:517-519`），**没有** `conv_channels1/2`；
而 `train.py:build_train_kwargs` 会按签名丢弃不接受的键（`train.py:423-434`）。
因此网格 run 的 `cnn_config.json` 里虽然记录了 `conv_channels1: 32, conv_channels2: 64`，CNN 实际用的是默认 **64/64/128**。
（`data_digging.py:305-306` 只把这两个值透传给 train.py 的 CLI。）

### 4.3 每个 run 的早停/日志

- 早停：验证损失改善需 `> min_delta`，否则计数；`epochs_without_improvement >= patience` 即停：
  MLP `src/mlp/mlp.py:598-648`、CNN `src/cnn/cnn.py:687-736`、Transformer `src/transformer/transformer.py:625-674`。
- 日志频率 `epoch==1 or epoch%10==0 or epoch==epochs or epoch==best_epoch`（同上文件对应行）。
- XGBoost 用 `early_stopping_rounds=30` + 验证集（`xgboost.py:527`），实测 `best_iteration: 132`
  （`models/batch_20260909_full/all_xgboost_sequence_heldout_hela/xgboost_config.json`）。

### 4.4 可选网格（ultimate，`predict.py`）

`ULTIMATE_GRIDS`（`predict.py:68-92`）：

| kind | 网格 |
|---|---|
| lr | `{use_scaler: False}`（1 组） |
| xgboost | `{n_estimators:100, max_depth:3}`、`{200, 4}`（2 组） |
| mlp | `{hidden_dim1:128, dropout:0.2}`、`{256, 0.3}`（2 组） |
| cnn33 | `{conv_channels1:32, conv_channels2:64, dropout:0.2}`、`{48, 96, 0.3}`（2 组） |
| cnn53 | `{32, 64, 0.2}`（1 组） |
| cnn73 | `{32, 64, 0.2}`（1 组） |
| transformer | `{dropout:0.1}`、`{dropout:0.2}`（2 组） |

ultimate 训练细节：`train_ultimate_models` `predict.py:476-559`；`KFold(10, shuffle, seed)` `409-423`；
torch 侧 `AdamW(lr=1e-3, weight_decay=0.0)`、`batch_size=256`、`epochs=15`（默认）`predict.py:328-351`；
XGBoost 侧 `learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, objective=reg:squarederror, n_jobs=-1`
且 n_estimators/max_depth 来自网格（`predict.py:374-387`）。
CLI 默认：`--ultimate-cv-folds 10`、`--ultimate-epochs 15`、`--ultimate-seed 42`、`--candidate-top-k 20`（`predict.py:743-748`）。
实测 `ultimate_summary.json`：`cv_folds: 10, epochs: 15, seed: 42, n_features: 92`。

**注意（ultimate CNN 的 `conv_channels1/2` 同样未生效）**：`_build_torch_model` 构造 `CNNModel` 时只传
`sequence_kernel/environment_kernel/dropout`，未传 `sequence_filters/environment_filters`（`predict.py:302-312`），
因此 `cnn33` 两组配置的差异实际只来自 `dropout`（0.2 vs 0.3）。**是否为设计意图未确认。**

### 4.5 是否用 scaler

- 默认**不用**。`use_scaler` 需显式 `--use-scaler`（`train.py:623`），网格默认关闭（`data_digging.py:424`）。
- 各模型若开启则用 `StandardScaler`，且只在训练集拟合：
  MLP `src/mlp/mlp.py:555-563`、CNN `src/cnn/cnn.py:641-650`、Transformer `src/transformer/transformer.py:580-582`、
  Linear `src/linear_regression/linear_regression.py:159-163`（scaler 另存 `linear_regression_scaler.pkl`）。
- 实测：抽查的 6 个 run config 全部 `"use_scaler": false`；`ultimate_summary.json` 中 lr 最优配置亦为 `use_scaler: false`。

---

## 5. 实验矩阵规模（batch_20260909_full）

### 5.1 事实计数（命令与结果）

```bash
$ ls -d models/batch_20260909_full/*/ | wc -l          # 1344   （模型 run 目录）
$ ls -d logs/batch_20260909_full/*/  | wc -l           # 1344   （日志 run 目录）
$ ls results/batch_20260909_full | wc -l               # 1345   （1344 run + summary/；旧 analyse_out/ 已于 2026-09-13 并入 summary/）
$ ls -d results/batch_20260909_full/*/ | grep -v summary | wc -l   # 1344 （纯训练 run）
$ wc -l results/batch_20260909_full/summary/metrics_tables/all_experiments.csv  # 1345 = 表头 + 1344 行
```

按 split 前缀统计：`single` 448 / `all` 448 / `mixed` 448（合计 1344）。
按模型统计（目录名含 `_<model>_`）：linear 192 / xgboost 192 / mlp 192 / transformer 192 / cnn 576（合计 1344）。

### 5.2 维度分解与公式

`data_digging.py:125-164` 的笛卡尔积：

- 环境组合 **16** 种：`sequence`(1) + C(4,1)=4 + C(4,2)=6 + C(4,3)=4 + `all`(1)
  （`src/input_control/cell_environment_combination.py:694-780`、`783-895` 明确写 “共 16 combinations”；
  `data_digging.py:97-115` 从 schema 加载）。
- 细胞系 4：`CELL_LINES = ["hct116","hek293t","hela","hl60"]`（`data_digging.py:58`）。
- 划分 3：`single` / `all` / `mixed`；`mixed` 再乘 4 个种子 `[42,43,44,45]`（`data_digging.py:59`）。
- CNN 额外乘 3 个核：`CNN_KERNELS = [3,5,7]`（`data_digging.py:60`，`312-313` 传 `--sequence-kernel`，`--environment-kernel` 恒 3）。

计算：

```
非 CNN：4 模型 × 16 环境 × (4 single细胞 + 4 all细胞 + 4 mixed种子) = 4 × 16 × 12 = 768
CNN   ：1 模型 × 16 环境 × 3 核 × (4 + 4 + 4)                    = 16 × 3 × 12  = 576
合计 = 768 + 576 = 1344                                            ✅ 与 ls 计数一致
```

### 5.3 实际目录名规律（实测 16 个环境名，`sort -u`）

```
all, sequence, sequence_ctcf, sequence_ctcf_dnase, sequence_ctcf_dnase_h3k4me3,
sequence_ctcf_dnase_rrbs, sequence_ctcf_h3k4me3, sequence_ctcf_h3k4me3_rrbs,
sequence_ctcf_rrbs, sequence_dnase, sequence_dnase_h3k4me3, sequence_dnase_h3k4me3_rrbs,
sequence_dnase_rrbs, sequence_h3k4me3, sequence_h3k4me3_rrbs, sequence_rrbs
```

种子实测值：`seed_42, seed_43, seed_44, seed_45`；核实测值：`kernel_3, kernel_5, kernel_7`；
留出细胞系实测值：`heldout_hct116, heldout_hek293t, heldout_hela, heldout_hl60`。

命名规则（`data_digging.py:167-180` `build_run_name`，与 `train.py:156-171` 一致）：

| split | run_name 模板 | 示例 |
|---|---|---|
| single | `single_{cell}_{model}_{env}` | `single_hct116_linear_sequence` |
| all | `all_{model}_{env}_heldout_{cell}` | `all_mlp_all_heldout_hct116` |
| mixed | `mixed_{model}_{env}_seed_{seed}` | `mixed_mlp_all_seed_42` |
| CNN 后缀 | 以上基础上追加 `_kernel_{3|5|7}` | `single_hela_cnn_sequence_rrbs_kernel_5` |

### 5.4 环境组合去重（历史坑）

`data_digging.py:63-94` `_canonicalize_combinations`：若列表同时含 `all` 与显式全特征名
（`sequence_ctcf_dnase_h3k4me3_rrbs`，同一含义），丢弃后者，避免实验翻倍。
docstring 记录此前出现过 `1428 = 17×84` 的重复膨胀；本批次实测环境名只有 16 个、无该重复。

---

## 6. 数据流与文件格式（逐步：输入 → 输出）

### 步骤 1：原始表 → 特征工程（`src/feature_engineering.py`）

- 输入
  - `data/source_data/{cell_line}.csv`，列：`Chromosome, Start, End, Strand, sgRNA, CTCF, Dnase, H3K4me3, RRBS, Normalized efficacy`
    （`src/feature_engineering.py:1030-1060`；`--source-dir` 默认 `data/source_data`，`1976-1983`）。
  - `data/feature_config.json`（`--config` 默认，`1994-2003`）。
- 处理：列检查 + 缺失值检查（`1187-1212`）→ 整行去重（`1218-1223`）→ 插入 `Cell line` 列（`1229-1233`）
  → 逐行编码 `23×8`（`1259-1282`）→ 展平 `N×184`（`1295-1301`）→ 目标 `float32`（`1303-1307`）。
- 输出（`data/proceeded_data/`，文件名在 `process_one_csv` 拼装 `1635-1649`、`save_numpy_files` `1454-1497`、
  schema/summary `1867-1875` / `1899-1911`）：

| 文件 | 形状/格式 | 代码 |
|---|---|---|
| `{cell}_features_23x{channel_count}.npy` → `{cell}_features_23x8.npy` | `(N, 23, 8)` float32 | `1473-1480` |
| `{cell}_features_{feature_count}.npy` → `{cell}_features_184.npy` | `(N, 184)` float32（行主序展平） | `1482-1489`、`1295-1301` |
| `{cell}_labels.npy` | `(N,)` float32（= `Normalized efficacy`） | `1491-1497` |
| `{cell}_metadata.csv` | 见下（7 列） | `1504-1525`、`1646-1649` |
| `{cell}_23x8.csv` | `Cell line,Chromosome,Start,End,Strand,sgRNA,features,Normalized efficacy`；`features` 为 23×8 嵌套列表 | `1350-1384`、`1635-1639` |
| `{cell}_184.csv` | `Cell line,…,sgRNA,pos1_A,…,pos23_RRBS,Normalized efficacy`（184 个特征列，列名 = `feature_names`） | `1391-1447`、`1641-1644` |
| `feature_schema.json` | 通道/特征定义（`sequence_length/channel_count/feature_count/channel_names/feature_names/sequence_channels/environment_features`） | `1532-1557`、`1867-1875` |
| `feature_engineering_summary.csv` | `cell_line,original_samples,duplicate_rows,final_samples,channel_count,feature_count` | `1899-1911` |

- **metadata 列名（实测文件头）**：
  `Cell line, Chromosome, Start, End, Strand, sgRNA, Normalized efficacy`
  （常量 `src/feature_engineering.py:136-143` + `save_metadata` `1512-1525`）。
  实测行数：hct116 4239、hek293t 2333、hela 8101、hl60 2076（与 labels 长度一致，加载时强校验
  `src/input_control/cell_line_division.py:98-110`）。

### 步骤 2：proceeded_data → 模型输入（`src/input_control/`）

- 文件路径解析规则（由 schema 动态决定维度）：`src/input_control/cell_line_division.py:75-86`
  `X_3d = {cell}_features_{seq_len}x{channel_count}.npy`、`X_2d = {cell}_features_{feature_count}.npy`、
  `y = {cell}_labels.npy`、`metadata = {cell}_metadata.csv`。
- 数据划分：`divide_data`（`cell_line_division.py:295-334`）按 split type 产出
  `X_train/valid/test_3d`、`X_train/valid/test_2d`、`y_*`、`metadata_*`（`attach_public_fields` `276-292`）。
- 环境通道裁剪 + 模型类型路由：`prepare_train_valid_test`（`cell_environment_combination.py:1357-1513`）→
  `prepare_model_input`（`1295-1350`）：2D 模型 `(N,23,C)→(N,23*C)`，3D 模型保持 `(N,23,C)`；
  未选中的表观通道 **mask 置 0**（`1151-1236`）。
- 形状校验：`train.py:329-343`（linear/xgboost/mlp 要求 2D；cnn/transformer 要求 3D）。

### 步骤 3：训练 → 模型/结果/日志

`data_digging.py` 逐实验调用 `train.py`（子进程 `run_one_experiment` `324-338`，或进程内 `341-362`），
run 目录由 `train.py:178-200` 建立（`*_root_dir/<batch_name>/`）。

**`models/<batch>/<run_name>/`**（实测）：

| 模型 | 文件 |
|---|---|
| linear | `linear_regression_model.pkl`、`linear_regression_scaler.pkl`、`linear_regression_diagnostics.json` |
| xgboost | `xgboost_model.json`、`xgboost_config.json` |
| mlp / cnn / transformer | `{model}_config.json`、`{model}_model.pt` |

**`results/<batch>/<run_name>/`**（实测）：

| 文件族 | 说明 |
|---|---|
| `{model}_info.txt` | 人类可读配置 + 验证/测试指标（linear 为 `linear_regression_info.txt`） |
| `{model}_metrics.json` | 测试集指标 MSE/RMSE/MAE/R2/Pearson/Spearman |
| `{model}_validation_metrics.json` + `{model}_validation_predictions.csv` | 验证集 |
| `{model}_predictions.csv` | 测试集预测 |
| `{model}_training_history.csv` | 逐 epoch 损失 |
| `{model}_feature_importance.csv` | 特征重要性 / 系数 |
| `linear_regression_weights.csv` | 仅 LR：权重与统计量 |

**`logs/<batch>/<run_name>/training.log`**：各模型 `create_logger`（如 `src/linear_regression/linear_regression.py:491-509`）。

**`results/<batch>/summary/`**：`metrics_tables/all_experiments.csv`（1345 行 = 表头 + 1344 实验，
列为 run 配置 + 指标，样例见下）、`metrics_tables/{all,single,mixed}_cell_line_result.csv`、`baseline.csv`、
`feature_importance/`、`plots/`、`tables/`、`anomaly_report.md`、`03_environment_effects.md`、
`environment_dag_report.md`、`赛道二_results.csv`、`ultimate/`。
`all_experiments.csv` 表头（实测）包含：
`run_name, Time, model, model_module, split_type, cell_line, cell_lines, environment, combination, selected_environments, environment_count, random_seed, train_ratio, validation_ratio, test_ratio, sequence_length, channel_count, channel_names, input_shape_train/valid/test, use_scaler, sequence_kernel, environment_kernel, epochs, batch_size, learning_rate, hidden_dim1, hidden_dim2, conv_channels1, conv_channels2, dropout, weight_decay, patience, min_delta, d_model, nhead, num_layers, best_epoch, best_validation_loss, MSE…Spearman, validation_*, sequence_channels, environment_channels, input_dim, feature_count, Feature count, Numerical rank, Condition number, Scaler, pinv_rcond, Best iteration…`。

### 步骤 4：predict.py → ultimate 模型与候选

- 入口 `predict.py:757-840`；默认 `ultimate_dir = results/<batch>/summary/ultimate`（`predict.py:793-796`）。
- 通道规划（决定 92 vs 184）：`build_channel_plan` `predict.py:101-136`；裁剪展平 `139-142`；
  mixed 数据装载 `240-261`。
- 输出：
  - `results/<batch>/summary/ultimate/ultimate_{lr,xgboost,mlp,cnn33,cnn53,cnn73,transformer}_config.json`
  - 模型文件 `ultimate_lr_model.json`、`ultimate_xgboost_model.pkl`、`ultimate_*_model.pt`（`predict.py:434-473`）
  - `ultimate_summary.json`（`predict.py:542-558`；含 `n_samples, cv_folds, epochs, seed, n_seq_channels, n_features, models[]`）
  - `results/<batch>/summary/赛道二_results.csv`（候选 Top-K，`predict.py:821`）
- 目标待测输入：`data/todo_data.CSV`，表头 `sgRNA,Efficacy`（180513 行）；目标编码规则见 `predict.py:177-221`。

---

## 7. 关键不确定项（未确认）

1. **`all` split 退化为 `single` 是否为设计意图** —— 代码行为确定（§3.4），但“heldout”语义与实现不符，属 bug 还是有意为之，未在代码/注释中找到说明。
2. **CNN 的 `conv_channels1/2`（网格）与 `conv_channels1/2`（ultimate）均未传入 `CNNModel`** —— 代码路径确定（§4.2、§4.4），是否为遗漏未确认。
3. **`Normalized efficacy` 的归一化算法与来源** —— 代码内无实现；README 称来自 DeepCRISPR（Chuai et al. 2018），未在仓库内独立验证。
4. **PAM 类型（NGG / SpCas9）** —— 仅由序列模式（22–23 位恒为 GG）与脚本命名推断，无配置或注释显式声明。
5. **`data/feature_config.user.json`** —— README（`README.md:430`）提到该用户映射文件，但 `data/` 下实际只有
   `feature_config.json`，未见 user 版；主流程使用的是 `feature_config.json`。
6. **`results/batch_20260909_full/summary/`** 是唯一的非训练 run 目录（指标表 + 分析引擎产物，见 `README.md:218`）。旧 `analyse_out/` 已于 2026-09-13 迁移进 `summary/`（`tables/ reports/ figures/`），迁移与冲突处理见 `docs/audit/SUMMARY_ARTIFACT_PROVENANCE.md`。
