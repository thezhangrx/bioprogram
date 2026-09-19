# 细胞环境感知型 CRISPR-Cas9 sgRNA 智能设计与影响因素发现平台

### Epigenetics-Aware Multimodal AI Platform for CRISPR-Cas9 sgRNA Design & Scientific Factor Discovery

> **参赛赛道**：赛道二 · AI 基因编辑与核酸工具设计
> **底盘系统**：SpCas9（20 nt protospacer + NGG PAM；本数据集 PAM 位于第 21–23 位，由数据验证）
> **本 README 是用户操作手册**：一个没有读过源码的用户，只依赖 Bash + 本文件 + `data/metadata/*.json`，
> 即可从零走完 **环境 → 数据 → schema → 预处理 → 训练 → 评估 → 数据挖掘 → 预测 → 结果汇总 → 可视化** 全流程。

**命令状态说明**：本 README 中标注 ✅ 的命令都在本仓库实机执行过并给出了实际输出。
标注 ⚠️ 的命令依赖前序步骤的产物。没有任何"你应该能跑"的未验证命令。
各步骤的实测记录见 `docs/reproducibility/CURRENT_WORKFLOW_MAP.md` 与 `docs/reproducibility/acceptance_record.md`。

---

## Quick Start（十步最小完整流程）

> 全部命令**以项目根目录为工作目录**。入口脚本内部自行解析项目根，不依赖当前目录。
> 下面每一步都是可直接复制执行的完整命令，**不需要修改任何 Python 文件**。

```bash
# ---------- 0. 环境 ----------
pip install -r deploy/environment/python/requirements_frozen.txt   # 开发/分析栈
# 超算（CentOS 7 / A100）改用：
# pip install -r deploy/environment/python/requirements_hpc.txt

# ---------- 1. 数据：把原始 CSV 放到 data/raw/<数据集>/ ----------
ls data/raw/DeepCRISPR/          # hct116.csv hek293t.csv hela.csv hl60.csv

# ---------- 2. schema：确认编码（无需读代码） ----------
python core/features/engineering/validate_feature_schema.py --all

# ---------- 3. 预处理：原始 CSV → 23×C 张量 + feature_schema.json ----------
python core/features/engineering/feature_engineering.py \
  --raw-data data/raw/DeepCRISPR \
  --output-dir data/processed/DeepCRISPR \
  --config data/metadata/feature_config.json

# ---------- 4. 训练：一次最小实验 ----------
python workflows/training/train.py \
  --model linear --split-type single --cell-line hct116 --environment sequence \
  --data-set DeepCRISPR \
  --results-dir results/batches --model-dir models/weights --logs-dir results/logs \
  --batch-name demo --run-name demo_linear --seed 42

# ---------- 5. 评估：读测试集指标 ----------
cat results/batches/demo/demo_linear/linear_regression_metrics.json

# ---------- 6. 数据挖掘：批量网格（先看计划，再真跑） ----------
python workflows/training/data_digging.py --data-set DeepCRISPR \
  --cell-lines hct116 --models linear xgboost --split-types single \
  --environments sequence --batch-name demo --dry-run

# ---------- 7. 预测：对候选序列打分 ----------
python workflows/prediction/predict.py --data-set DeepCRISPR \
  --batch-name demo --models linear --dry-run

# ---------- 8. 结果汇总 ----------
python -m analysis.collect_results --results-dir results/batches --batch-name demo

# ---------- 9. 关键特征库 ----------
python analysis/importance_extraction.py --batch_dir results/batches/demo

# ---------- 10. 可视化 ----------
python analysis/panorama.py --batch-dir results/batches/demo
python -m analysis.pipeline --batch-dir results/batches/demo --output results/batches/demo/analysis
```

**数据集切换**：把上面所有 `DeepCRISPR` 换成 `Hiranniramol` 或 `Labuhn` 即可。
`Hiranniramol` / `Labuhn` 没有表观通道，第 3 步的 `--config` 要换成
`data/metadata/feature_config_sequence_only.json`，且 `--environment` 只能用 `sequence`
（`data/metadata/datasets.json` 已登记这些差异，`orchestrator` 会自动选对）。

---

## 1. 项目简介

**核心科学问题**：sgRNA 的编辑效率不仅取决于 23 nt 序列本身，还取决于**细胞环境**
（CTCF / Dnase / H3K4me3 / RRBS 等表观遗传通道）。本项目把
**预测 → 模型归因 → 统计检验 → 跨细胞系比较 → 证据整合 → 生物学假设** 组织为一条可追溯、可复现的流程。

1. **预测**：序列 + 细胞环境能否比纯序列更好地预测编辑效率？
2. **归因**：模型依赖哪些位点与通道？是否稳健？
3. **泛化**：跨细胞系（LOCO）与跨序列（group-aware）泛化时结论是否仍成立？

**输入 / 输出一览**

| | 内容 |
|---|---|
| **输入** | `data/raw/<数据集>/*.csv`（23 nt sgRNA + 实测效率 + 可选表观通道）、`data/metadata/feature_config*.json`（编码配置）、`data/candidate/*.CSV`（待预测候选） |
| **处理** | `core/`（特征工程 → 划分 → 模型 → 归因）、`workflows/`（训练 / 挖掘 / 预测 / 编排）、`analysis/`（汇总 → 统计 → 证据 → 报告 → 图） |
| **输出** | `results/batches/<batch>/<run>/`（逐 run 指标与预测）、`results/batches/<batch>/summary/`（批次汇总、图、特征库）、`models/weights/<batch>/<run>/`（权重）、`results/logs/`（日志） |
| **模型** | 线性回归 / XGBoost / MLP / 双分支 CNN（卷积核 3/5/7）/ Transformer，共 7 个配置 |
| **分析目标** | 环境通道的增量预测价值、跨模型归因一致性、跨细胞系泛化、可实验检验的候选因素 |

**规模**：3 个数据集、5 类模型（7 配置）× 16 环境组合 × 3 种划分 = DeepCRISPR 上 1344 次受控实验。

---

## 2. 仓库结构

```text
data/                      数据（不写代码，只放数据与配置）
  raw/<数据集>/            原始 CSV（输入）
  processed/<数据集>/      处理后张量 + feature_schema.json（模型输入）
  metadata/                ← 用户配置区（见 §5、§14）
    feature_config.json            8 通道：序列 4 + 表观 4（DeepCRISPR）
    feature_config_sequence_only.json  4 通道：纯序列（Hiranniramol / Labuhn）
    datasets.json                  数据集清单（单一数据源）
  candidate/               候选/待测序列

core/                      科学引擎（二次开发区，普通用户不改）
  common/paths.py          唯一权威路径解析
  features/engineering/    特征工程 + schema 生成 + schema 校验器
  features/channels/       通道组合与环境 lattice
  data/splitting/          身份类划分 + 泄漏审计
  models/                  5 类模型实现
  xai/                     归因白名单

workflows/                 用户入口（CLI 层）
  training/train.py        单次实验
  training/data_digging.py 网格批量挖掘
  training/run.sh          HPC 批量（single/all/mixed）
  prediction/predict.py    mixed 交叉验证 + 候选预测
  design/ screen/          候选设计 / 筛选
  orchestrator/            步骤注册表（只读命令生成器）

analysis/                  分析层（只读训练产物）
  collect_results.py       指标汇总
  pipeline.py              分析引擎（统计/证据/报告/图表）
  importance_extraction.py 关键调控特征库
  anomaly_treatment.py     异常实验检测
  panorama.py              全景图

results/                   输出（全部由程序生成）
  batches/<batch>/<run>/        逐 run 产物
  batches/<batch>/summary/      批次级汇总
  logs/<batch>/<run>/           训练日志
  tables/                       跨批次汇总表
models/weights/<batch>/<run>/   模型权重

deploy/                    部署与 HPC
  environment/python/      依赖清单（frozen / hpc / 宽松）
  hpc/                     打包、自检、验收、环境比对
  external/crispron/       第三方模型 CRISPRon（外部验证用）
docs/                      文档与论文
tests/                     测试（scientific / app / schema / cli / workflow）
```

---

## 3. 运行环境

| 项 | 开发 / 分析环境（审计栈） | 超算训练环境（目标栈） |
|---|---|---|
| OS | Linux (glibc 2.39) | CentOS 7 (glibc 2.17) |
| Python | 3.12.3 | 3.10.21 (conda-forge) |
| PyTorch | 2.13.0+cu130 | 2.6.0+cu124 |
| CUDA / GPU | CUDA 13.0 / 无 GPU（本机 CPU） | CUDA 12.4 / 8 × A100-SXM4-80GB |
| NumPy / pandas | 2.5.2 / 3.0.5 | 2.2.6 / 2.3.3 |
| XGBoost | 3.4.1 | 2.0.3 |

```bash
# 开发机（本仓库默认环境）
pip install -r deploy/environment/python/requirements_frozen.txt
# 超算（CentOS 7 / A100）
pip install -r deploy/environment/python/requirements_hpc.txt
```

核心依赖：`numpy`、`pandas`、`scipy`、`scikit-learn`、`xgboost`、`torch`（`matplotlib` / `seaborn` 出图）。

> ⚠️ **两个环境不可混用**：`ultimate_run` 批次的 1344 次实验是在**超算栈**（py3.10.21 / torch2.6.0 / xgboost2.0.3）上产生的。
> 数值栈变化会直接改变 R²（XGBoost 2.x→3.x 的默认参数语义、numpy/pandas 浮点归约、torch 算子差异）。
> 每个 run 的 `*_info.txt` 都记录了 `env_fingerprint` 与 `env_stack_id`，可比对。
>
> ⚠️ 本机无 GPU，`torch.cuda.is_available()` 为 `False`，神经网络模型会自动落到 CPU（`device_resolved` 字段可见）。

---

## 4. 数据集

三个数据集由 `data/metadata/datasets.json` 统一登记（**单一数据源**，新增数据集只需在此登记 + 放数据，不改代码）。

### 4.1 DeepCRISPR（主数据集）

| 项 | 内容 |
|---|---|
| Source | Chuai et al. 2018, *Genome Biology*, "DeepCRISPR: optimized CRISPR guide RNA design by deep learning"，doi:[10.1186/s13059-018-1459-4](https://doi.org/10.1186/s13059-018-1459-4) |
| License | 遵循原始出版物与其数据仓库的条款；**使用前请到原文/原仓库确认** |
| Raw location | `data/raw/DeepCRISPR/{hct116,hek293t,hela,hl60}.csv` |
| Processed location | `data/processed/DeepCRISPR/` |
| Sequence field | `sgRNA`（23 nt） |
| Label field | `Normalized efficacy`（已是 [0,1]，不再缩放） |
| Sequence length | 23 nt（20 nt protospacer + 3 nt PAM） |
| PAM | NGG，位于第 21–23 位（已包含在张量内） |
| Cell lines | hct116 / hek293t / hela / hl60 |
| Environment features | CTCF, Dnase, H3K4me3, RRBS（逐位点二值可及性） |
| Preprocessing | `feature_engineering.py --config data/metadata/feature_config.json` → 23×8 = 184 维 |
| Split | `single`（细胞内 70/15/15）、`all`（真实 LOCO，训练池先剔除留出系同源序列）、`mixed`（跨细胞系 70/15/15，种子 42–45） |

### 4.2 Hiranniramol（外部复现数据集）

| 项 | 内容 |
|---|---|
| Source | Hiranniramol et al. 2020, *Bioinformatics* 36(9):2684–2689，doi:[10.1093/bioinformatics/btaa041](https://doi.org/10.1093/bioinformatics/btaa041) |
| License | 遵循原始出版物条款；使用前请到原文确认 |
| Raw location | `data/raw/Hiranniramol/Hiranniramol.CSV`（单文件） |
| Processed location | `data/processed/Hiranniramol/` |
| Sequence field | `gRNA`（20 nt） |
| Label field | `Edit Efficiency`（**原始为 0–100 百分制**，适配器自动 /100） |
| Sequence length | 构造为 23 nt（gRNA + 后 3 nt PAM） |
| PAM | 由 `Extended Target` 定位 gRNA 后取后 3 nt，要求 GG |
| Cell lines | 单细胞系（`hiranniramol`） |
| Environment features | **无**（纯序列，4 通道 / 92 维） |
| Preprocessing | `--config data/metadata/feature_config_sequence_only.json --format hiranniramol` |
| Split | 仅 `single`（70/15/15） |

### 4.3 Labuhn（外部复现数据集）

| 项 | 内容 |
|---|---|
| Source | Labuhn et al. 2018, *Nucleic Acids Research* 46(3):1375–1385，doi:[10.1093/nar/gkx1268](https://doi.org/10.1093/nar/gkx1268) |
| License | 遵循原始出版物条款；使用前请到原文确认 |
| Raw location | `data/raw/Labuhn/Labuhn.CSV`（单文件） |
| Processed location | `data/processed/Labuhn/` |
| Sequence field | `sgRNA_sequence`（20 nt） |
| Label field | `KO_reporter_assay`（**已是 [0,1]**，不再缩放） |
| Sequence length | 构造为 23 nt |
| PAM | 由 `extended_spacer` 定位后取后 3 nt，要求 GG |
| Cell lines | 单细胞系（`labuhn`） |
| Environment features | **无**（纯序列，4 通道 / 92 维） |
| Preprocessing | `--config data/metadata/feature_config_sequence_only.json --format labuhn` |
| Split | 仅 `single`；同一 sgRNA 的重复测量按均值合并（5 条） |

> ⚠️ **不同数据集的 label semantics 不同，不可当作同一个物理量比较。**
> DeepCRISPR 是归一化编辑效率、Hiranniramol 是百分制 `Edit Efficiency`、Labuhn 是 `KO_reporter_assay`。
> 三者的测定方式、细胞体系与 readout 均不同。跨数据集的 R² **只能读作"同一流程在不同数据集上的可预测性"**，
> 不能读作"同一量的预测难度"。详见 `docs/reproducibility/EXTERNAL_DATASETS.md`。

---

## 5. Feature schema（编码规范）

**文件位置**：`data/processed/<数据集>/feature_schema.json`（**由特征工程自动生成，请勿手工编辑**）

用户要"改编码"时改的是 **`data/metadata/feature_config*.json`**（见 §14），然后重跑特征工程。

### 5.1 当前实际编码（`schema_version: 2` 声明）

| 项 | 实际值 |
|---|---|
| Sequence encoding | **one-hot**（`encoding.sequence.encoding = "one_hot"`） |
| Alphabet | `A`, `C`, `G`, `T`（`encoding.sequence.alphabet`） |
| Channel order | `A`(0), `C`(1), `G`(2), `T`(3), `CTCF`(4), `Dnase`(5), `H3K4me3`(6), `RRBS`(7) |
| base → channel | `A→0, C→1, G→2, T→3`（`encoding.sequence.base_to_channel_index`） |
| N 的处理 | **不支持**。碱基不在 alphabet 中即抛 `ValueError`（`unknown_base_policy: "error"`），**不会静默置零** |
| Sequence length | 23 nt（`sequence_length`） |
| PAM | **包含在张量内**，位于第 21–23 位；protospacer 为第 1–20 位（`sequence_definition.pam_included_in_tensor = true`） |
| Position indexing | **1-based**（`layout.position_indexing`；`feature_names` 写作 `pos1_A` … `pos23_RRBS`） |
| Tensor shape | `(23, C)`；DeepCRISPR `C=8`，外部数据集 `C=4`（`layout.tensor_shape`） |
| Flatten order | **位置优先、通道内层**：`flat_index = position0 * C + channel_index`（`layout.flatten_order = "position_major"`） |
| Flatten dim | `feature_count` = 184（8 通道）/ 92（4 通道） |
| Environment encoding | 逐位点二值，取值 ⊆ {0,1}（配置中 `A=1 可及 / N=0 不可及` 是**原始 CSV 字符串**到二值的映射，不是通道下标） |
| Normalization | **张量内不做任何标准化**（`normalization.applied_in_tensor = false`）。标准化是模型级运行时开关 `--use-scaler`（默认关闭） |
| Model input dim | linear 剔除全部 `*_T` 通道（每位点 1 个，共 23 个）：184→**161**、92→**69**；xgboost/MLP 用完整 184/92；CNN/Transformer 用 `(23, C)` 不展平（`model_compatibility`） |

### 5.2 验证"声明 == 实际"

```bash
# 校验全部数据集
python core/features/engineering/validate_feature_schema.py --all

# 单个数据集
python core/features/engineering/validate_feature_schema.py --data-set DeepCRISPR
```

该脚本会断言：通道数/序列长度/展平维度与张量一致、`channel_names` 的环境段顺序与 `environment_features`
声明一致、**由 metadata 序列重建的 one-hot 与张量逐元素相等**、环境取值 ⊆ {0,1}、
`layout` 与 `model_compatibility` 声明自洽。退出码 0 = 通过。

**实测结果（本仓库现状）**：

```text
$ python core/features/engineering/validate_feature_schema.py --all
  ...
  -> 76 passed, 0 failed, 2 skipped
结论: PASS — schema 声明与实际张量一致
```

### 5.3 用户只看 schema 就能确定的 15 个问题

| 问题 | schema 中的答案位置 |
|---|---|
| sequence 编码格式 | `encoding.sequence.encoding` |
| nucleotide encoding | `encoding.sequence.alphabet` + `base_to_channel_index` |
| A/C/G/T/N 映射 | `base_to_channel_index`（N 见 `unsupported_bases`） |
| channel 顺序 | `layout.channel_order` / `channel_names` |
| sequence length 定义处 | `sequence_length` / `sequence_definition.length_nt` |
| environment channel 顺序 | `encoding.environment.features[].name`，与 `channel_names` 环境段一致 |
| feature_names ↔ tensor channels | `layout.feature_names_layout`（可执行 §5.2 校验） |
| position numbering | `layout.position_indexing` |
| PAM 是否在 tensor 内 | `sequence_definition.pam_included_in_tensor` + `pam_positions` |
| seq 与 env 长度可否不同 | `layout.sequence_block`（环境特征形状被强制为 `(23,1)`） |
| 哪些 categorical / one-hot | `encoding.sequence.encoding`、`encoding.environment.features[].type` |
| 哪些 numeric | `encoding.environment.features[].type`（当前无 numeric 通道） |
| normalization | `normalization.applied_in_tensor` |
| tensor shape 推导 | `layout.tensor_shape` / `layout.flatten_index_formula` |
| downstream 是否按 schema 顺序读 | `layout.channel_order` + §5.2 校验脚本 |

---

## 6. 预处理（Preprocessing）

**入口**：`core/features/engineering/feature_engineering.py`
**作用**：原始 CSV → `(N, 23, C)` 张量 + 展平 CSV + `feature_schema.json` + `feature_engineering_summary.csv`

```bash
# DeepCRISPR（8 通道，含表观遗传）
python core/features/engineering/feature_engineering.py \
  --raw-data data/raw/DeepCRISPR \
  --output-dir data/processed/DeepCRISPR \
  --config data/metadata/feature_config.json

# Hiranniramol（4 通道，纯序列）
python core/features/engineering/feature_engineering.py \
  --raw-data data/raw/Hiranniramol/Hiranniramol.CSV \
  --output-dir data/processed/Hiranniramol \
  --config data/metadata/feature_config_sequence_only.json \
  --format hiranniramol

# Labuhn（4 通道，纯序列）
python core/features/engineering/feature_engineering.py \
  --raw-data data/raw/Labuhn/Labuhn.CSV \
  --output-dir data/processed/Labuhn \
  --config data/metadata/feature_config_sequence_only.json \
  --format labuhn
```

三个输入路径（`--raw-data` / `--output-dir` / `--config`）**都必须显式给出**，没有隐含默认值——
这样不会误处理、也不会覆盖别的数据集。`--help` 里有完整示例。

**产物**：`feature_schema.json`、`<cell>_features_23x<n>.npy`、`<cell>_features_184.npy`、
`<cell>_labels.npy`、`<cell>_metadata.csv`、`feature_engineering_summary.csv`。

> 实测：重复运行特征工程，24 个张量/元数据文件的 SHA-256 **逐字节不变**（确定性）。

---

## 7. 训练（Training）

**入口**：`workflows/training/train.py`

### 7.1 最小可运行例子（已实测）

```bash
python workflows/training/train.py \
  --model linear --split-type single --cell-line hct116 --environment sequence \
  --data-set DeepCRISPR \
  --results-dir results/batches --model-dir models/weights --logs-dir results/logs \
  --batch-name demo --run-name demo_linear --seed 42
```

实测输出：

```text
2026-09-19 22:14:58 | INFO | Train shape: (2968, 161), Test shape: (636, 161)
2026-09-19 22:14:58 | INFO | Test Evaluation -> R2: 0.1320, Pearson: 0.3635, MAE: 0.1339
[✓] Experiment demo_linear Finished Successfully.
```

### 7.2 用户如何控制实验

| 想改什么 | 改哪个参数 | 可选值 / 说明 |
|---|---|---|
| **模型** | `--model` | `linear` / `xgboost` / `mlp` / `cnn` / `transformer` |
| **数据集** | `--data-set` | `DeepCRISPR` / `Hiranniramol` / `Labuhn`（大小写不敏感）；或 `--data-dir data/processed/<数据集>` |
| **划分** | `--split-type` | `single` / `all`(LOCO) / `mixed` |
| **细胞系** | `--cell-line` / `--cell-lines` | 单细胞系或列表 |
| **环境组合** | `--environment` | `sequence`、`sequence_ctcf`、`sequence_ctcf_dnase` …（用 `+` 无，用 `_` 连接；`sequence` 表示纯序列） |
| **划分比例** | `--train-ratio` `--valid-ratio` `--test-ratio` | 默认 0.7 / 0.15 / 0.15 |
| **随机种子** | `--seed` | 默认 42 |
| **CNN 卷积核** | `--sequence-kernel` / `--environment-kernel` | 3 / 5 / 7 |
| **网络宽度** | `--hidden-dim1` `--hidden-dim2` `--conv-channels1` `--conv-channels2` | 默认 128 / 64 / 32 / 64 |
| **正则化** | `--dropout` `--weight-decay` | |
| **优化** | `--learning-rate` `--batch-size` `--epochs` | |
| **优化器** | `--optimizer` | `adam`（默认，等价于改造前的硬编码行为）/ `adamw` / `sgd` / `rmsprop` / `adagrad`；仅 mlp/cnn/transformer 生效 |
| **学习率调度** | `--scheduler` | `none`（默认，不创建调度器）/ `cosine` / `step` / `exponential` / `plateau`（按验证损失） |
| **激活函数** | `--activation` | `none`（默认＝沿用各模型原有激活：CNN/MLP 为 ReLU、Transformer 为 GELU）/ `relu` / `gelu` / `tanh` / `sigmoid` / `leaky_relu` / `elu` / `silu` |
| **数据加载并行** | `--num-workers` | DataLoader worker 数，默认 `0` |
| **绑定物理 GPU** | `--gpu-id` | 如 `0` 或 `0,1`；设置 `CUDA_VISIBLE_DEVICES` 后再训练。与 `--device` 的区别：`--device` 在**可见集合内**选序号，`--gpu-id` 改的是**可见集合本身**（多进程并行要隔离显存时用这个） |
| **早停** | `--patience` `--min-delta` | 默认 20 / 1e-6 |
| **标准化** | `--use-scaler` | 默认关闭 |
| **设备** | `--device` | 如 `cuda` / `cpu`（默认自动解析） |
| **输出路径** | `--results-dir` `--model-dir` `--logs-dir` | 相对项目根或绝对路径 |
| **实验名 / 批次名** | `--run-name` `--batch-name` | `--batch-name` 是产物分子目录名 |
| **自定义模型模块** | `--model-module` | 高级用法，指向自定义实现 |

`--optimizer` / `--scheduler` / `--activation` / `--num-workers` / `--gpu-id` 在
`workflows/training/data_digging.py` 中同名可用，会透传给每个训练子进程。

**默认值保证**：上表所有默认值都与加入这些参数之前**逐位一致**。实测证据（改造前后同一命令）：
linear 的 `linear_regression_metrics.json` sha256 相同（`929869bf…`），mlp/cnn/transformer 的
`*_metrics.json` 亦逐字节相同；`data_digging` 生成的默认 train 命令行与改造前 `cmp` 完全一致。
新增参数只在**显式传入**时才改变行为（`*_info.txt` 会记录
`optimizer`/`scheduler`/`activation`/`num_workers`/`gpu_id` 五个留痕键，可用于核对）。

例：

```bash
python workflows/training/train.py \
  --model mlp --split-type mixed --environment sequence_ctcf \
  --data-set DeepCRISPR --batch-name demo --run-name demo_mlp_sgd \
  --optimizer sgd --scheduler cosine --activation gelu \
  --learning-rate 1e-3 --epochs 100 --gpu-id 0
```


### 7.3 批量网格训练

```bash
# 看计划（不训练、不写文件）
python workflows/training/data_digging.py --data-set DeepCRISPR \
  --cell-lines hct116 --models linear xgboost --split-types single \
  --environments sequence --batch-name demo --dry-run

# 真跑（用 --training-scope-epis 让它自动展开全部环境组合）
python workflows/training/data_digging.py --data-set DeepCRISPR \
  --training-scope-epis CTCF Dnase --models linear xgboost \
  --split-types single --batch-name demo --workers 4
```

HPC 全网格（single + all + mixed）：

```bash
bash workflows/training/run.sh
WORKERS=8 GPUS="0 1 2 3 4 5 6 7" bash workflows/training/run.sh
```

---

## 8. 评估（Evaluation）

评估内嵌在训练的最后一步，**不需要单独的命令**——训练完成即产出测试集与验证集两套指标。

```bash
# 测试集指标（写论文/报告请一律用这个）
cat results/batches/demo/demo_linear/linear_regression_metrics.json

# 验证集指标（仅用于选最优 epoch，不作为性能口径）
cat results/batches/demo/demo_linear/linear_regression_validation_metrics.json

# 逐样本预测
head results/batches/demo/demo_linear/linear_regression_predictions.csv
```

> ⚠️ **口径约定（重要）**：`*_metrics.json` = **测试集**；`*_validation_metrics.json` = 验证集。
> 两套口径混用会让同一批 run 的数字漂移（本项目曾因此把数值发散计数误记为 33，实际测试集口径为 20）。
> 全文/全报告请统一用测试集口径。

`*_info.txt` 记录了完整的运行配置与划分审计：`n_train/n_valid/n_test`、`audit_train_test_sequence_overlap`、
`audit_train_test_revcomp_overlap`、`split_digest`、`data_fingerprint`、`code_fingerprint`、`env_stack_id`。

---

## 9. 数据挖掘（Data Digging）

**入口**：`workflows/training/data_digging.py` —— 全项目参数最完整的用户级 CLI。

```bash
# 计划模式（强烈建议先跑）
python workflows/training/data_digging.py --data-set DeepCRISPR \
  --cell-lines hct116 --models linear --split-types single \
  --environments sequence --batch-name demo --dry-run

# 真跑
python workflows/training/data_digging.py --data-set DeepCRISPR \
  --training-scope-epis CTCF --models linear xgboost cnn \
  --split-types single mixed --mixed-seeds 42 43 \
  --cnn-kernels 3 5 7 --batch-name demo --workers 4
```

实测（计划模式）：

```text
[Dataset] DeepCRISPR -> /home/zhang/bioprogram/Submit/data/processed/DeepCRISPR
[Environments] 共 1 种: sequence
[Datasets] ... 下发现 4 个: hct116, hek293t, hela, hl60
Experiment Plan -> Total: 1 | Completed: 1 | Pending: 0
[*] Dry run completed.
```

主要参数：

| 参数 | 说明 |
|---|---|
| `--data-set` / `--data-dir` | 数据集（二选一，必填） |
| `--training-scope-epis` | 要深入挖掘的表观特征，自动展开全部环境组合 |
| `--environments` | 显式环境组合列表（与上面二选一） |
| `--models` `--cell-lines` `--split-types` `--mixed-seeds` `--cnn-kernels` | 实验空间 |
| `--batch-name` `--results-dir` `--model-dir` `--logs-dir` | 输出位置 |
| `--workers` `--gpus` `--threads-per-worker` `--in-process` | 并行与设备 |
| `--dry-run` | 只打印计划，不训练不写文件 |

---

## 10. 预测（Prediction）

**入口**：`workflows/prediction/predict.py`
**作用**：mixed 十折交叉验证训练"终极模型" → 对目标候选序列打分 → 输出候选清单。

```bash
# 计划模式
python workflows/prediction/predict.py --data-set DeepCRISPR \
  --batch-name demo --models linear --dry-run

# 对候选文件打分
python workflows/prediction/predict.py --data-set DeepCRISPR \
  --batch-name demo --models linear xgboost cnn \
  --target-input data/candidate/todo_data.CSV \
  --target-epigenetics CTCF Dnase --candidate-top-k 50
```

实测（计划模式）：

```text
[Dry-run] 计划摘要 (未执行任何训练/写入):
  - 模式            : pooled (mixed 已测池自身)
  - 通道规划        : seq=['A','C','G','T'] epi=['CTCF','Dnase','H3K4me3','RRBS'] -> 8 通道 / 184 维
                      (LR 剔除 _T 参照列后 161 维, T 为基准)
  - Mixed 训练数据  : 16749 样本 x 184 维 | 细胞系: ['hct116','hek293t','hela','hl60']
  - 将输出          : results/batches/demo/summary/赛道二_results.csv
  - 模型将保存至    : results/batches/demo/summary/ultimate
```

**输入 / 输出契约**：

| | 内容 |
|---|---|
| 输入 | `--target-input`：CSV 文件或含 CSV 的目录；列需含序列列（如 `sgRNA`）与（可选）表观通道列 |
| 输入（环境） | `--target-epigenetics`：目标序列**实际具备**的表观通道；缺省从目标文件列自动识别 |
| 输出 | `<batch>/summary/赛道二_results.csv`（候选排序）、`<batch>/summary/ultimate/`（终极模型权重与配置）、`preds_*.npy`（逐模型预测） |
| 模型来源 | `--ultimate-dir`（默认 `<batch>/summary/ultimate`） |

> 结果不会只打印到终端：全部落盘到 `summary/`，并打印确切路径。

---

## 11. 结果汇总（Result Collection）

```bash
# 最近修改的批次
python -m analysis.collect_results --latest

# 指定批次（--results-dir 必须与训练时一致！）
python -m analysis.collect_results --results-dir results/batches --batch-name demo

# 直接指定批次目录
python -m analysis.collect_results --batch-dir results/batches/demo

# 只要 single 划分
python -m analysis.collect_results --batch-name demo --split-types single
```

**产物**：`<batch>/summary/metrics_tables/{single,all,mixed}_cell_line_result.csv` 与序列表基线表。

> ⚠️ `--results-dir` 必须与训练时用的值**一致**，否则会报"批次目录不存在"并返回退出码 1。
> 退出码：0 成功 / 1 批次目录不存在 / 2 用法错误。

可选的后续分析：

```bash
# 关键调控特征库（白名单归因 → key_regulatory_biomarkers.csv）
python analysis/importance_extraction.py --batch_dir results/batches/demo

# 异常实验检测
python analysis/anomaly_treatment.py --batch-dir results/batches/demo
```

---

## 12. 可视化（Visualization）

```bash
# 全景图（位置热图 / 环境 DAG / 消融树 / 表观因子对比）
python analysis/panorama.py --batch-dir results/batches/demo

# 分析引擎（统计 / 证据 / 报告 / 图表，17 个任务）
python -m analysis.pipeline --batch-dir results/batches/demo --output results/batches/demo/analysis
```

实测：

```text
$ python -m analysis.pipeline --batch-dir .../demo --output .../demo/analysis
[✓] pipeline finished -> .../demo/analysis
    tasks: qc=completed; prediction=completed; environment_conditional_effect=completed;
           environment_main_effect=completed; environment_factorial_dag=completed;
           sequence_attribution=completed; bootstrap=completed; hypothesis_testing=completed;
           evidence_integration=completed; (其余按批次规模自动 skipped/unavailable)

$ python analysis/panorama.py --batch-dir .../demo
[🎉] 全部图表已分类保存 -> .../demo/summary/plots
```

---

## 13. 输出结构

```text
results/batches/<batch>/
  <run>/                          每次实验一个目录
    <model>_metrics.json                  ★ 测试集指标（R²/MAE/RMSE/Pearson/Spearman）
    <model>_validation_metrics.json        验证集指标（仅用于选 epoch）
    <model>_predictions.csv                逐样本预测
    <model>_info.txt                       运行配置 + 划分审计 + 三类指纹
    <model>_feature_importance.csv         归因白名单列
  summary/                        批次级产物
    metrics_tables/                        汇总表（collect_results）
    tables/ reports/ figures/              分析引擎产物（pipeline）
    plots/                                 全景图（panorama）
    feature_importance/                    关键调控特征库（importance_extraction）
    ultimate/                              终极模型与候选清单（predict）
    anomaly_report.md                      异常检测报告
  analysis/                       分析引擎输出（--output 指定时）

models/weights/<batch>/<run>/     模型权重（.pkl / .pt / .json）
results/logs/<batch>/<run>/       训练日志
data/processed/<数据集>/          处理后张量 + feature_schema.json
```

---

## 14. 用户应该改哪里

### ✅ 允许修改（不需要改代码）

| 想改什么 | 改哪里 |
|---|---|
| **特征编码 / 环境通道** | `data/metadata/feature_config.json`（8 通道）或 `feature_config_sequence_only.json`（纯序列） |
| **新增数据集登记** | `data/metadata/datasets.json` + 把 CSV 放到 `data/raw/<名称>/` |
| **模型超参数** | 训练命令行参数（见 §7.2）；批量用 `data_digging.py` 同名参数 |
| **实验空间** | `--models` / `--environments` / `--split-types` / `--mixed-seeds` / `--cnn-kernels` |
| **输入输出路径** | `--data-set` / `--data-dir` / `--results-dir` / `--model-dir` / `--logs-dir` |
| **实验名 / 批次名** | `--run-name` / `--batch-name` |
| **随机种子** | `--seed`（mixed 另可用 `--mixed-seeds`） |

### ❌ 不要修改（除非二次开发）

| 文件 | 原因 |
|---|---|
| `core/models/**` | 模型实现；改动会破坏已发布结果的 `code_fingerprint` 一致性 |
| `core/features/engineering/feature_engineering.py` | 预处理逻辑；编码语义的权威实现 |
| `core/data/splitting/**` | 划分与泄漏防控；改动会让 `split_digest` 失效 |
| `workflows/prediction/predict.py` | 预测逻辑 |
| `data/processed/<数据集>/feature_schema.json` | **自动生成**；要改编码请改 feature config 后重跑特征工程 |

> 判据：**只要一个改动需要你打开 `.py` 文件，先确认它不能通过 `data/metadata/*.json` + 命令行参数完成。**
> 如果确实不能，那是一个应当被修复的设计缺口，请按 §16 提 issue 式记录。

---

## 15. 可复现性

每个 run 的 `*_info.txt` 记录五要素，使结果可溯源到「数据 + 配置 + 代码 + 模型 + 随机种子」：

| 字段 | 含义 |
|---|---|
| `data_fingerprint` | 数据内容哈希（含特征文件大小） |
| `code_fingerprint` | 关键源文件 md5 |
| `env_fingerprint` / `env_stack_id` | 数值栈版本与设备可见性 |
| `split_digest` | 划分摘要（sha256 前 16 位），可核验"训练所用划分 == 分析所用划分" |
| `audit_train_test_sequence_overlap` / `audit_train_test_revcomp_overlap` / `audit_train_test_locus_overlap` | 泄漏审计；group-aware 模式下非零即抛错中止 |

**身份类与泄漏防控**（`core/data/splitting/cell_line_division.py`）：

- 身份键 = `min(sequence, revcomp(sequence))`（同一 sgRNA 及其反向互补视为同一身份类）
- 三种划分全部 group-aware：**同一序列不跨 train/valid/test**
- LOCO(`all`) 训练池先剔除留出系全部同源序列，再按 85/15 划分
- 划分处自证：重叠非零即抛错；`split_digest` 随结果落盘

**固定种子**：single / all 固定 42；mixed 42/43/44/45；bootstrap 2024；置换检验 B=1000（seed 2024）。

**数据来源与当前状态**：

- **权威批次 = `ultimate_run`**（`results/batches/ultimate_run/`）：1344 次实验，group-aware 无泄漏划分，
  验收 `PASS`（1344/1344、三种划分各 448、`split_digest` 逐条复核 0 不一致、全批单一环境栈、960 个神经网络 run 全部 CUDA）。
  验收报告：`results/tables/audit/ultimate_run_verify_report.md`。
- **历史批次 `batch_20260909_full` 已废弃**（整改与弃用依据见 `docs/audit/PROJECT_SCIENTIFIC_REPRODUCIBILITY_AUDIT.md`
  与 `docs/audit/SUMMARY_ARTIFACT_PROVENANCE.md`）：存在已确认的划分泄漏
  （mixed 36.1%、LOCO 33.3%），仅用于泄漏前后对照，**不得用于论文数字**。

**环境一致性比对**：

```bash
python deploy/hpc/compare_env_equivalence.py --reference <批A> --candidate <批B>
```

---

## 16. 完整工作流与编排（Orchestrator）

`workflows/orchestrator` 是**只读步骤注册表**：它不执行任何步骤，只负责生成"这一步该跑什么命令"
以及"这一步的产物是否已存在"。GUI / Web 与本 README 共用同一份定义。

```bash
# 列出全部步骤
python -m workflows.orchestrator list

# 查看某一步的真实命令（可直接复制执行）
python -m workflows.orchestrator command --step feature_engineering --data-set DeepCRISPR
python -m workflows.orchestrator command --step train_grid --data-set DeepCRISPR

# 检查产物是否齐备
python -m workflows.orchestrator check --step train_grid --data-set DeepCRISPR

# 查看当前上下文解析结果（数据集 → 路径）
python -m workflows.orchestrator context --data-set Hiranniramol

# 依赖顺序
python -m workflows.orchestrator order --step collect_results
```

步骤清单（`list` 实测输出）：

```text
feature_engineering    [data        light] 特征工程（序列+表观张量 + schema）
train_grid             [train       heavy] 受控网格训练（data_digging.py）
generate_candidates    [train       heavy] 候选生成与优先级排序（predict.py）
collect_results        [analysis    light] 指标汇总（collect_results.py）
anomaly_treatment      [analysis    light] 异常实验检测（anomaly_treatment.py）
importance_extraction  [deliverable light] 关键调控特征库（importance_extraction.py）
legacy_visualization   [analysis    light] 全景图（panorama.py）
analysis_engine        [analysis    light] 分析引擎（analysis.pipeline）
deliverables_check     [deliverable light] 交付物核对
```

> `deliverables_check` 是 `kind=internal` 的内部检查，**没有子进程命令**。`command` 动作对它
> 会返回 `command: []` 并附带 `note` 说明与产物路径，而不是静默返回空数组。
>
> 默认输出根 = **项目根**，因此 `<root>/results/batches` 与 `<root>/models/weights` 正好落在
> README 约定的位置。可用 `--output-dir` 改到别处（Web 前端始终显式传入）。

---

## 17. 测试

```bash
# 科学核心（特征/划分/模型/统计/外部验证）
python -m unittest discover -s tests/scientific -t .

# 应用与编排
python -m unittest discover -s tests/app -t .

# 全量（pytest）
python -m pytest tests/ -q
```

配置与代码的一致性检查（schema ↔ tensor、CLI ↔ 运行时参数、README 命令可执行）：

```bash
python -m pytest tests/schema tests/cli tests/workflow -q
```

---

## 18. 超算（HPC）

```bash
bash deploy/hpc/build_upload.sh                                  # 打包
python deploy/hpc/preflight_hpc_rerun.py --package . --data-set DeepCRISPR --batch-name <batch>
python deploy/hpc/verify_hpc_rerun.py    --package . --data-set DeepCRISPR --batch-name <batch>
python deploy/hpc/compare_env_equivalence.py --reference <批A> --candidate <批B>
```

环境与实验协议见 `docs/reproducibility/HPC_ENVIRONMENT.md`、`HPC_EXPERIMENT_PROTOCOL.md`。

---

## 19. 其它入口

```bash
# 候选设计与筛选
python workflows/design/design.py --batch-name <batch> --candidate-top-k 50
python workflows/screening/screen.py --input data/candidate/todo_data.CSV --batch-name <batch>

# Demo 笔记本
jupyter lab notebooks/demos/01_pipeline_demo.ipynb

# 应用
bash app/scripts/run_workspace.sh          # Web 工作台
python app/desktop/main_wizard.py          # 桌面向导

# 外部模型验证（第三方 CRISPRon，见 docs/reproducibility/EXTERNAL_MODEL_VALIDATION_CRISPRON.md）
python -m analysis.external_validation.validate_position18 --help
```

---

## 20. 权威定义（同一概念只有一个来源）

| 概念 | 唯一权威位置 |
|---|---|
| 路径解析 | `core/common/paths.py` |
| 数据集清单（raw/processed/config/label 语义） | `data/metadata/datasets.json` |
| 特征编码与通道定义 | `data/metadata/feature_config*.json` → 生成 `data/processed/<数据集>/feature_schema.json` |
| schema 声明语义 | schema 的 `encoding` / `layout` / `sequence_definition` / `normalization` / `model_compatibility` 块 |
| 数据划分与泄漏防控 | `core/data/splitting/cell_line_division.py` |
| 归因白名单（每模型允许列） | `core/xai/importance/xai_importance.py` |
| 步骤注册表（GUI/README/CLI 共用） | `workflows/orchestrator/steps.py` |
| 依赖锁定 | `deploy/environment/python/requirements_{frozen,hpc}.txt` |

---

## 21. 已知边界与未自动化部分

诚实列出，不隐瞒：

1. **数据集获取未脚本化**：本项目不提供从公开源自动下载数据的脚本。用户需按 §4 的来源链接自行获取，
   放入 `data/raw/<数据集>/`。各数据集的**许可条款请到原始出版物/仓库确认**。
2. **`--environment` 取值需查环境组合命名规则**：形如 `sequence_ctcf_dnase`（下划线连接、顺序需与
   channel 顺序一致）。用 `python -m workflows.orchestrator command --step train_grid` 可看到本项目实际使用的组合。
3. **本机无 GPU**：神经网络模型在本机落 CPU，速度远慢于 HPC。完整 1344 网格请用 `run.sh` + HPC。
4. **`analysis.pipeline` 的部分任务需要足够规模的批次**：在小批次上会自动标记 `skipped` / `unavailable`
   （如 `motif_discovery`、`environment_anova`），这是设计行为，非错误。
5. **`app/`（Web 工作台与桌面向导）未在本次验收中实跑**，其命令保留自原 README。
6. **HPC 步骤（`deploy/hpc/*`）未在本次验收中实跑**（需要超算环境与已打包批次）。
