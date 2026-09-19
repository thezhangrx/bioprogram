# Current Workflow Map — Bash 可复现性验收（勘察阶段，未修改任何代码）

**勘察日期**：2026-09-19
**勘察方式**：**实测**每个入口的 `--help` 与实际执行，而非阅读代码推断。所有"PASS/FAIL"结论均来自实际运行的退出码与输出。
**用途**：本文件是后续整改的基线。凡标 ❌ 的项即为必须整改项。

---

## 0. 结论速览

| 维度 | 结论 |
|---|---|
| **核心引擎** | ✅ **可用**。训练 / data_digging / predict / collect 在给定**正确参数**时全部跑通并产出完整产物 |
| **README 命令** | ❌ **5 条主要命令中 3 条直接失败**（① 特征工程、② 训练、④ 预测），⑤ 报错却返回 exit 0 |
| **orchestrator 命令** | ❌ `feature_engineering` 步骤配置路径错误 + 数据集错配；`deliverables_check` 输出空命令 |
| **feature_schema** | ⚠️ **声明↔张量实测完全一致**（正面结论），但**声明字段严重不足**，用户无法从 schema 本身确定 encoding |
| **硬编码路径** | ✅ 项目自有代码与脚本中 **0 命中** |
| **环境声明** | ⚠️ 依赖清单存在，但 README 的环境表与实际运行栈不符；无 lock/校验 |
| **CLI 覆盖** | ⚠️ train.py 缺 optimizer / scheduler / activation / num-workers / gpu-id；predict.py 缺 feature-schema / output-format |
| **一致性测试** | ❌ 无 `tests/schema/`、`tests/cli/`、`tests/workflow/` |

---

## 1. 完整流程图（现状）

```text
input
  data/raw/<数据集>/*.csv                      ← 原始 CSV（逐细胞系）
  data/metadata/feature_config.json            ← 8 通道配置（序列 4 + 表观 4）
  data/metadata/feature_config_sequence_only.json  ← 4 通道配置
        │
        ▼  ❌ README ①  FAIL（缺 --config；--source-dir 语义已变）
preprocessing / feature construction
  core/features/engineering/feature_engineering.py
  --raw-data <数据集目录> --output-dir data/processed/<数据集> --config <配置>
        │
        ▼
schema
  data/processed/<数据集>/feature_schema.json   ← 自动生成，含 feature_names
        │
        ▼
split
  core/data/splitting/cell_line_division.py     ← 身份类划分 + 运行期重叠断言
        │
        ▼  ❌ README ②  FAIL（--data-dir data/processed 已非数据集目录）
train
  workflows/training/train.py          --data-set <名称> | --data-dir <数据集目录>
  workflows/training/data_digging.py   --data-set <名称>  （网格批量）✅ 可用
        │
        ▼  ⚠️ README 无独立 evaluation 章节（评估内嵌在 train 的测试集步骤）
evaluation
  <run>/<model>_metrics.json  = 测试集
  <run>/<model>_validation_metrics.json = 验证集
        │
        ▼  ✅ 可用（需配套 --results-dir）
data digging
  workflows/training/data_digging.py   ✅
  analysis/collect_results.py          ✅
        │
        ▼  ❌ README ④  FAIL（缺必填 --data-set/--data-dir）
prediction
  workflows/prediction/predict.py      ✅ 可用
        │
        ▼
results
  results/batches/<batch>/<run>/       逐 run 产物
  results/batches/<batch>/summary/     批次级汇总
  models/weights/<batch>/<run>/        权重
  results/logs/<batch>/<run>/          日志
        │
        ▼
visualization
  analysis/panorama.py                 （README ⑤ 部分）
  analysis/pipeline.py                 （README ⑤ 部分）
```

---

## 2. 逐步骤状态（实测）

### Step 1 环境准备 — ⚠️ 部分

| 项 | 状态 | 证据 |
|---|---|---|
| 依赖清单存在 | ✅ | `deploy/environment/python/{requirements,requirements_frozen,requirements_hpc}.txt` |
| README 给出安装命令 | ✅ | `pip install -r deploy/environment/python/requirements_frozen.txt` |
| README 环境表准确 | ✅（**初查误判，此处更正**） | 初查时我判为「虚构」，实测后证明是**我错了**：分析环境正是 Python 3.12.3 / torch 2.13.0+cu130 / numpy 2.5.2 / pandas 3.0.5 / xgboost 3.4.1，与 `requirements_frozen.txt` 逐版本一致；而 `ultimate_run` 的 `env_fingerprint`（py3.10.21 / torch2.6.0+cu124 / xgboost2.0.3）对应超算栈 `requirements_hpc.txt`。**README 的两列映射是正确的**。唯一瑕疵：`requirements_frozen.txt` 注释头写着 HPC 重跑锁定环境，与其实际内容（开发栈）不符 |
| 无 lock 文件校验 | ❌ | 无 hash 校验，无法保证跨机一致 |
| 无 `pyproject.toml`/`setup.py` | ⚠️ | 项目以脚本方式运行，可接受，但 `python -m workflows.orchestrator` 依赖 CWD 在项目根 |

### Step 2 数据准备 — ⚠️

| 项 | 状态 | 说明 |
|---|---|---|
| 原始数据存在 | ✅ | `data/raw/{DeepCRISPR,Hiranniramol,Labuhn}/` |
| README 说明来源 | ✅ | 第 7 节，含 4 细胞系与表观通道 |
| README 给出**获取/放置**命令 | ❌ | 只说"原始 CSV 见 data/raw/"，**未说明如何从公开源下载、放哪、校验什么** |
| 各数据集 label 语义区分 | ⚠️ | README 第 7 节只描述 DeepCRISPR；Hiranniramol/Labuhn 的 label 语义差异仅在 `docs/reproducibility/EXTERNAL_DATASETS.md` |

### Step 3 schema — ⚠️ 一致但声明不足

**实测一致性（正面结论）**：

```
hct116   tensor=(4239, 23, 8)  序列通道 one-hot 重建一致=True  环境取值=[0.0, 1.0]
hek293t  tensor=(2333, 23, 8)  序列通道 one-hot 重建一致=True  环境取值=[0.0, 1.0]
hela     tensor=(8101, 23, 8)  序列通道 one-hot 重建一致=True  环境取值=[0.0, 1.0]
hl60     tensor=(2076, 23, 8)  序列通道 one-hot 重建一致=True  环境取值=[0.0, 1.0]

总样本=16749  非法碱基/长度=0
schema↔tensor 序列通道完全一致: True   最大绝对差: 0.0
展平维度: 184 = schema.feature_count 184 = len(feature_names) 184
```

即：**不存在**"schema 写 A/C/G/T 但代码用 G/C/A/T"这类 silent mismatch。

**但 schema 声明不足** —— 下表列出用户想从 schema 得知、而当前 schema **无法回答**的信息：

| 用户问题 | 当前 schema 能否回答 | 实际答案（只能读代码得知） |
|---|---|---|
| sequence encoding 是什么？ | ❌ 无 `encoding` 字段 | one-hot（`feature_engineering.py:371`） |
| A/C/G/T/N 如何映射？ | ⚠️ 只有 `sequence_channels: [A,C,G,T]`，需推断索引 | A→ch0, C→ch1, G→ch2, T→ch3；**N 不被支持，出现即抛错** |
| channel 顺序？ | ✅ `channel_names` | A,C,G,T,CTCF,Dnase,H3K4me3,RRBS |
| sequence length 在哪定义？ | ✅ `sequence_length: 23` | 但代码中**三处重复定义**（`feature_engineering.py:145`、`dataset_adapters.py:54`、`cell_environment_combination.py`） |
| environment channel 顺序？ | ✅ `environment_features[].name` | 与 `channel_names` 一致 |
| feature_names ↔ tensor channels 一一对应？ | ✅ 实测一致 | 展平顺序 = 位置优先、通道内层 |
| position numbering 0/1-based？ | ❌ 无字段（`feature_names` 用 `pos1_` 暗示 1-based） | 1-based |
| PAM 是否包含在 tensor？ | ❌ 无字段 | **包含**（第 21–23 位为 PAM，第 1–20 为 protospacer） |
| seq 与 env 长度可否不同？ | ❌ | 不可：env 被强制 `(23,1)`，否则抛错 |
| 哪些 categorical / one-hot？ | ❌ | 序列 4 通道 one-hot；环境为逐位点二值 |
| 哪些 numeric？ | ❌ | 当前无 numeric 通道（代码支持 `per_position_numeric`/`global_numeric`） |
| normalization 定义？ | ❌ 无字段 | 无（`use_scaler` 默认 False，属运行时开关） |
| tensor shape 如何从 schema 推导？ | ⚠️ 需手工算 | `(sequence_length, channel_count)`；展平 `feature_count` |
| downstream 是否按 schema 顺序读？ | ❌ 无声明 | 是（实测一致），但无自动校验 |

### Step 4 preprocess — ❌ README 命令失败

```bash
# README 原文
python core/features/engineering/feature_engineering.py --source-dir data/raw --output-dir data/processed
# 实测
usage: ... --raw-data RAW_DATA --output-dir OUTPUT_DIR --config CONFIG
error: the following arguments are required: --config      ← exit=2
```

问题：
1. `--config` **必填**但 README 未给；
2. `--source-dir data/raw` 语义已变——现在是**按数据集**处理（`data/raw/DeepCRISPR` → `data/processed/DeepCRISPR`），传父目录会把三个数据集混在一起；
3. README 未区分 8 通道（DeepCRISPR）与 4 通道（外部数据集，需 `feature_config_sequence_only.json`）。

**正确形式（已实测的语义）**：
```bash
python core/features/engineering/feature_engineering.py \
  --raw-data data/raw/DeepCRISPR --output-dir data/processed/DeepCRISPR \
  --config data/metadata/feature_config.json
```

### Step 5 train — ❌ README 命令失败，但入口本身 ✅

```bash
# README 原文（--data-dir data/processed）
FileNotFoundError: feature_schema.json 不存在：.../data/processed/feature_schema.json   ← exit=1
```

原因：`data/processed/` 已重组为父目录（`DeepCRISPR/`、`Hiranniramol/`、`Labuhn/`），schema 在子目录。

**正确形式（已实测 PASS）**：
```bash
python workflows/training/train.py \
  --model linear --split-type single --cell-line hct116 --environment sequence \
  --data-set DeepCRISPR \
  --results-dir /tmp/cwt/results/batches --model-dir /tmp/cwt/models/weights --logs-dir /tmp/cwt/results/logs \
  --batch-name smoke --run-name smoke_linear
# → Test Evaluation -> R2: 0.1320；产物 11 个文件 ✓
```

`train.py` 内部**已调用** `validate_feature_schema()`（`train.py:188`），schema 缺失会显式报错 ✅。

### Step 6 evaluation — ⚠️ 无独立入口

评估内嵌在训练的最后一步（`cnn.py:757` 等），产物为：
- `<run>/<model>_metrics.json` = **测试集**
- `<run>/<model>_validation_metrics.json` = 验证集

**README 没有独立的 evaluation 章节，也未说明两个口径的区分**（该口径问题曾导致论文数字错误，见 `docs/paper/SCIENTIFIC_LOGIC_CHANGELOG.md` §5.1）。

### Step 7 data digging — ✅ 入口可用，❌ README 未收录

`data_digging.py` 是全项目 CLI 最完整的入口（26 个参数）：
```bash
python workflows/training/data_digging.py --data-set DeepCRISPR \
  --cell-lines hct116 --models linear --split-types single --environments sequence \
  --results-dir ... --model-dir ... --logs-dir ... --batch-name smoke --dry-run
# → [*] Dry run completed.  exit=0 ✓
```
**但 README 完全没有提到 `data_digging.py`** —— 用户无从知道它存在。

### Step 8 predict — ❌ README 命令失败，入口 ✅

```bash
# README 原文
predict.py --batch-name demo --target-input data/candidate/todo_data.CSV --candidate-top-k 50
# 实测
error: one of the arguments --data-set/--data_set/--dataset --data-dir is required   ← exit=2
```

**正确形式（已实测 PASS）**：
```bash
python workflows/prediction/predict.py --data-set DeepCRISPR --batch-name smoke \
  --results-dir /tmp/cwt/results/batches --models linear --dry-run
# → 通道规划: seq=[A,C,G,T] epi=[CTCF,Dnase,H3K4me3,RRBS] -> 8 通道/184 维 (LR 剔除 _T → 161)  ✓
```

### Step 9 result collection — ⚠️ 可用但退出码不可靠

```bash
python -m analysis.collect_results --results-dir /tmp/cwt/results/batches --batch-name smoke
# → metrics_tables 5 个文件  exit=0 ✓

# 但失败时：
python -m analysis.collect_results --batch-name <不存在的批次>
# → [Error] Batch directory '...' does not exist.   exit=0   ❌ 脚本化隐患
```

且 README ⑤ 只给 `--batch-name demo`，若训练时用了自定义 `--results-dir`，此处必须**同样**传 `--results-dir`——README 未说明这一配对要求。

### Step 10 visualization — ⚠️ 命令存在但依赖上游

```bash
python analysis/panorama.py --batch-dir results/batches/demo
python -m analysis.pipeline --batch-dir results/batches/demo
```
两个入口存在于 README ⑤，但未验证（依赖真实批次产物）。

---

## 3. 问题清单（按类型）

### 3.1 参数写死 / 路径写死

| 位置 | 问题 | 证据 |
|---|---|---|
| `SEQUENCE_LENGTH = 23` | **两处**重复定义（初查写成三处，此处更正）；取值一致 | `feature_engineering.py:145`、`dataset_adapters.py:54`。`DEFAULT_SEQUENCE_CHANNELS` 亦两处（`cell_environment_combination.py:165`、`feature_engineering.py:169`），取值一致。已由 `tests/schema/` 断言锁死一致性 |
| `cnn.py:624` | `seq_names = ["A","C","G","T"] if sequence_channels==4 else ["A","G","C"]` —— 非 4 通道时通道名顺序**与 schema 不同**（A,G,C vs A,C,G）。仅当未传 `channel_names` 时生效，属**潜在 silent mismatch** | `cnn.py:624` |
| `collect_results` | 默认 `--results-dir results/batches`，与训练的 `--results-dir` 必须手工配对 | 实测 |
| orchestrator 默认根 | 解析为 `output/models|results|logs`，但 **`output/` 目录不存在**，与 README 的 `results/`、`models/` 不一致 | `orchestrator command` 实测 |

**项目自有代码硬编码绝对路径：0 命中** ✅（`/home/...`、`C:\`、`/Users/` 在 workflows/analysis/deploy/app/tests/core 中均无匹配；95 个命中全部位于 vendored `deploy/external/crispron/venv/`）

### 3.2 依赖 Agent / 需改源码

| 位置 | 问题 |
|---|---|
| README ① ② ④ | 命令**不能直接运行**，用户按 README 走必然失败，只能靠 Agent 或读源码纠正 |
| `data_digging.py` | 完整可用但**README 未收录** → 用户不知道存在，等于依赖 Agent 告知 |
| `orchestrator` | 是唯一"统一入口"，但 README 只给了 `list/check/command` 三个动词，未说明它是**只读命令生成器**（不执行） |

### 3.3 缺少 README / 缺少校验

| 缺失 | 说明 |
|---|---|
| 无 Quick Start 十步 | README 是"核心程序查找表"，不是用户操作手册；无端到端最小流程 |
| 无独立 evaluation 章节 | 未说明测试集/验证集两个口径 |
| 无 data_digging 章节 | 最重要的分析入口未文档化 |
| 无 output structure 说明 | 第 6 节有目录说明，但未与各命令的 `--*-dir` 参数对应 |
| 无"用户该改哪里"规则 | 未区分 config 层与 core 层 |
| 无 `tests/schema|cli|workflow/` | 只有 `tests/{scientific,app}/`，无配置↔代码一致性检查 |

### 3.4 orchestrator 步骤命令缺陷（实测）

| 步骤 | 问题 |
|---|---|
| `feature_engineering` | `--config /home/.../data/feature_config.json` → **文件不存在**（真实路径 `data/metadata/feature_config.json`）；且 `--source-dir data/raw`（父目录）配 `--output-dir data/processed/DeepCRISPR` → **会把三个数据集写进 DeepCRISPR** |
| `deliverables_check` | 输出 `command: []` **空命令** |
| 全部步骤 | 默认输出根 `output/` 不存在，且与 README 的 `results/`、`models/` 不一致 |

---

## 4. 已实测 PASS 的命令（可作为整改后的 README 基线）

```bash
# 训练（最小可运行，已实测 R2=0.1320，产物 11 个）
python workflows/training/train.py \
  --model linear --split-type single --cell-line hct116 --environment sequence \
  --data-set DeepCRISPR \
  --results-dir results/batches --model-dir models/weights --logs-dir results/logs \
  --batch-name smoke --run-name smoke_linear

# data digging 计划（已实测）
python workflows/training/data_digging.py --data-set DeepCRISPR \
  --cell-lines hct116 --models linear --split-types single --environments sequence \
  --results-dir results/batches --model-dir models/weights --logs-dir results/logs \
  --batch-name smoke --dry-run

# 结果汇总（已实测 5 个产物；--results-dir 必须与训练一致）
python -m analysis.collect_results --results-dir results/batches --batch-name smoke

# 预测计划（已实测，打印通道规划）
python workflows/prediction/predict.py --data-set DeepCRISPR \
  --batch-name smoke --results-dir results/batches --models linear --dry-run
```

---

## 5. 整改优先级（本次任务范围）

1. **P0**：修复 README ① ② ④ 与 orchestrator 步骤命令（否则用户第一步就失败）
2. **P0**：`feature_schema.json` 声明补全（encoding / indexing / PAM / normalization / source），使 encoding 无需读代码
3. **P1**：README 重写为用户操作手册（Quick Start 十步 + 每步真实命令 + evaluation/data_digging 章节 + output structure + 该改哪里）
4. **P1**：`collect_results` 失败返回非零退出码
5. **P1**：补齐 train.py 缺失参数（optimizer/scheduler/activation/num-workers/gpu-id）
6. **P2**：新增 `tests/schema/`、`tests/cli/`、`tests/workflow/` 一致性检查
7. **P2**：`SEQUENCE_LENGTH` 三处重复 → 单一来源；`cnn.py:624` 的 A,G,C 回退名修正
8. **P2**：README 环境表按实际栈更正；数据获取步骤补全

---

## 6. 本阶段声明

**本文件为勘察产物，此阶段未修改任何代码。** 上述所有 PASS/FAIL 均来自实际执行。未执行的部分（如 `analysis/panorama.py`、`analysis.pipeline`、完整 1344 网格训练、`app/` 与 HPC 流程）在本次勘察中**未验证**，后续报告中若仍无法实跑将标 `NOT VERIFIED`。
