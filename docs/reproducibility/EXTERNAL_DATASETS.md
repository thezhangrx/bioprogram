# 外部数据集接入与 HPC 运行指南（Hiranniramol / Labuhn）

本页说明如何把 **三个独立数据集** 接入平台、各自的特征工程命令、
以及把它放到超算上做训练挖掘与预测的完整步骤。

---

## 1. 三个数据集

| 数据集 | 原始文件 | 真实效率列（标签） | 序列列 | 序列构造 | 表观通道 | 处理后规模 |
|---|---|---|---|---|---|---|
| **DeepCRISPR** | `data/raw/DeepCRISPR/{hct116,hek293t,hela,hl60}.csv` | `Normalized efficacy` | `sgRNA`（已是 23 nt） | 直接用 | **有**（CTCF/Dnase/H3K4me3/RRBS） | 16 749 样本 × **23×8 = 184** 维 |
| **Hiranniramol** | `data/raw/Hiranniramol/Hiranniramol.CSV` | `Edit Efficiency`（0–100） | `gRNA`（20 nt） | `Extended Target` 中定位 gRNA，取 **gRNA + 后 3 nt PAM** = 23 nt | 无 | 1 309 样本 × **23×4 = 92** 维 |
| **Labuhn** | `data/raw/Labuhn/Labuhn.CSV` | **`KO_reporter_assay`**（已是 0–1） | `sgRNA_sequence`（20 nt） | `extended_spacer` 中定位 sgRNA，取 **sgRNA + 后 3 nt PAM** = 23 nt | 无 | 417 样本 × **23×4 = 92** 维 |

量纲约定：工程的标签列统一叫 `Normalized efficacy` 且必须落在 **[0, 1]**。
Hiranniramol 是百分制，适配器自动 `/100`；Labuhn 的 `KO_reporter_assay` 本来就是 [0,1]，**不再除**。

### 适配层的硬校验（不会静默放过）

`core/features/engineering/dataset_adapters.py` 负责把上述差异抹平，规则是：

* spacer 必须 20 nt 且只含 `ACGT`；
* spacer 在 extended 序列里必须**唯一命中**（命中多次 → `spacer_ambiguous`，不猜）；
* 切出的 23 nt 必须**以 GG 结尾**（PAM），否则丢弃并计入 `pam_not_gg`
  （确有非 GG 的合法 PAM 时用 `--allow-non-gg-pam` 显式放行）；
* 同一 sgRNA 被**重复测量**（不同效率）→ 按均值合并并记录条数；
* 丢弃比例超过 **20%** 直接报错，而不是"成功"产出残缺数据。

适配结果会在运行日志第一行打印完整账目，例如：

```
[labuhn] 430 行 -> 417 行（丢弃 8，1.86%；原因：spacer_not_in_extended=8） | 重复测量合并 5 条序列
        | 效率 0~0.973 already [0,1] -> 0~0.973 | 表观通道=无 | PAM-GG=100.00%
```

单独自检（不写文件）：

```bash
python core/features/engineering/dataset_adapters.py --list
python core/features/engineering/dataset_adapters.py --raw-data data/raw/Labuhn/Labuhn.CSV --dry-run
```

---

## 2. 特征工程：三个路径都必须显式给出

`feature_engineering.py` **不再有任何指向 DeepCRISPR 的默认路径**
（`--raw-data` / `--output-dir` / `--config` 全是必填），
避免误处理数据集、也避免覆盖别的数据集的产物。

```bash
# DeepCRISPR（8 通道 / 184 维）
python core/features/engineering/feature_engineering.py \
    --raw-data data/raw/DeepCRISPR \
    --output-dir data/processed \
    --config data/metadata/feature_config.json

# 外部数据集（4 通道 / 92 维）：
# 两次写入同一目录 -> 该目录下有 2 个"细胞系"，才能跑 all(留一) 与 mixed
python core/features/engineering/feature_engineering.py \
    --raw-data data/raw/Hiranniramol/Hiranniramol.CSV \
    --output-dir data/processed/external \
    --config data/metadata/feature_config_sequence_only.json

python core/features/engineering/feature_engineering.py \
    --raw-data data/raw/Labuhn/Labuhn.CSV \
    --output-dir data/processed/external \
    --config data/metadata/feature_config_sequence_only.json
```

* `--format` 留空即按列名自动识别（`deepcrispr` / `hiranniramol` / `labuhn`）。
* `--raw-data` 可以是**文件**也可以是**目录**（目录会递归找 `*.csv` / `*.CSV`）。
* 多次写入同一 `--output-dir` 时 `feature_engineering_summary.csv` 会**累积**而不是覆盖。
* `--cell-lines a b` 可只处理指定文件；只跑单个数据集时 `all`/`mixed` 会退化，见 §5。

产物（以 `data/processed/external` 为例）：

```
feature_schema.json                 channel_count=4, feature_count=92
feature_engineering_summary.csv     每个数据集一行，含适配层账目与标签范围
hiranniramol_features_23x4.npy      (1309, 23, 4)
hiranniramol_features_92.npy        (1309, 92)
hiranniramol_labels.npy             (1309,)
hiranniramol_metadata.csv           Cell line, sgRNA, Normalized efficacy
labuhn_features_23x4.npy            (417, 23, 4)
labuhn_features_92.npy              (417, 92)
labuhn_labels.npy                   (417,)
labuhn_metadata.csv                 Cell line, Strand, sgRNA, Normalized efficacy
```

> 两个外部数据集没有基因组坐标，因此 metadata **没有** `Chromosome/Start/End`。
> 下游容错已处理（划分只用 `sgRNA` 做身份分组）。

---

## 3. 起飞前自检（HPC）

```bash
# 外部数据集（期望 READY）
python deploy/hpc/preflight_hpc_rerun.py \
    --package . --data-dir data/processed/external --batch-name <新批次名>

# DeepCRISPR：加上 --strict-1344 仍会断言 1344 / 448 / 192 的原始矩阵形状
python deploy/hpc/preflight_hpc_rerun.py \
    --package . --data-dir data/processed --batch-name <新批次名> --strict-1344
```

自检现在**按 `--data-dir` 的实际维度推导期望值**，所以外部数据集也能 READY。
实测外部数据集：**66 项断言、0 失败**。

---

## 4. 训练挖掘（HPC）

`run.sh` 的 `DATA_DIR` 现在是**必填**（去掉 DeepCRISPR 隐式默认）：

```bash
# 外部数据集：TRAINING_SCOPE 为空 -> 按 schema 自动展开（4 通道只会得到 sequence）
DATA_DIR=data/processed/external TRAINING_SCOPE=none \
WORKERS=8 BATCH=<新批次名> bash workflows/training/run.sh

# DeepCRISPR：默认按 4 个表观因子展开出 16 种环境组合
DATA_DIR=data/processed WORKERS=8 BATCH=<新批次名> bash workflows/training/run.sh
```

等价的原生命令（便于按需裁剪规模）：

```bash
python workflows/training/data_digging.py \
    --data-dir data/processed/external \
    --model-dir models/weights \
    --results-dir results/batches \
    --logs-dir results/logs \
    --batch-name <新批次名> \
    --workers 8
```

`--data-dir` 必填；`--cell-lines` 不再被限制成 DeepCRISPR 的 4 个名字，
缺省即"该目录下实际发现的全部数据集"。计划规模由数据决定：

| 数据集 | 环境组合 | 计划实验数 |
|---|---|---|
| DeepCRISPR（4 细胞系） | 16 | 1 344 |
| 外部（2 数据集） | 1（`sequence`） | 56 |

---

## 5. 规模与划分的边界（务必先读）

* **只有 1 个数据集时**：`all`（留一）与 `mixed` 会退化成单数据集划分，
  但 run 名仍叫 `all_*` / `mixed_*`。`data_digging` 现在**两者都会 WARN**。
  要做真正的留一/mixed，请把两个外部数据集放进**同一个** `--output-dir`。
* **两个数据集序列高度重叠时**：`all` 会把 hold-out 的序列从训练池中全部剔除，
  若剔除后训练集为 0，现在会**直接报错**而不是产出 0 样本实验。
* **纯序列数据集只有 `sequence` 一种环境组合**：不会再有与它等价的 `all`
  （旧实现会多排一个重复实验）。`--environment all` 在 4 通道 schema 下会明确报"未知组合"。

---

## 6. 跑完后的落地验收

```bash
python deploy/hpc/verify_hpc_rerun.py \
    --package . --data-dir data/processed/external --batch-name <新批次名> \
    --out results/tables/audit/hpc_verify
```

验收会核对：计划覆盖度（按 `--data-dir` 推导，不再写死 448）、
run 身份唯一性、`data_fingerprint` / `code_fingerprint` / `env_stack_id` 全批一致、
NN 模型是否同一 device、以及**逐个 run 重算 `split_digest`**。

---

## 7. 预测 / 候选设计

```bash
# mixed 十折 + 目标待测集预测（--data-dir 必填）
python workflows/prediction/predict.py \
    --data-dir data/processed/external \
    --results-dir results/batches --batch-name <新批次名>
```

已知限制：这两份数据没有基因组坐标，候选输出里的**「位点」列会是 `chrUnknown(NA)`**
（`predict.py` 的 fallback 行为，不报错）。如果交付模板要求可定位位点，
需要用 `sgRNA` 序列本身替代，或补充坐标后再生成候选。

---

## 8. 已修的路径/默认值（本页相关）

| 位置 | 原行为 | 现行为 |
|---|---|---|
| `feature_engineering.py` | `--source-dir data/raw` / `--output-dir data/processed` / `--config …feature_config.json` 全有 DeepCRISPR 默认 | 三者**必填** |
| `cell_line_division.py::load_feature_schema` | schema 缺失时**静默写入** 8 通道 DeepCRISPR schema | 直接 `FileNotFoundError` |
| `cell_line_division.py::discover_available_cell_lines` | 找不到时回退成 4 个 DeepCRISPR 细胞系 | 直接 `FileNotFoundError` |
| `data_digging.py::load_environment_combinations` | schema 缺失时回退成 16 种组合 | 直接 `FileNotFoundError` |
| `data_digging.py` / `predict.py` / `design.py` | `--cell-lines` 只允许 4 个 DeepCRISPR 名字 | 由 `--data-dir` 实际内容决定 |
| `data_digging.py` / `predict.py` | `--data-dir` 默认 `data/processed` | **必填** |
| `workflows/training/run.sh` | `--data-dir data/processed` 写死 | `DATA_DIR` 必填 |
| `app/backend/crispr_workspace/training.py` | 校验硬编码 4 细胞系（GUI 选不了新数据集） | 按 `data_dir` 实际发现校验 |
| `app/desktop/backend_runner.py` | 永远写 `(N,23,8)` / `_features_23x8.npy` / 8 通道 schema | 通道数由勾选决定 |
