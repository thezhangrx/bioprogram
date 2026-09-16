# HPC 训练 / 预测包（上传到超算后先读这个）

本包只含**训练与预测**所需的代码和数据。分析、统计检验、图表、论文资产都在本地仓库用
`analysis/` 完成——超算只负责跑出 run 产物。

```
core/            模型与数据处理（训练/预测的全部代码路径）
workflows/       training/（train.py 单实验、data_digging.py 网格调度、run.sh 批量入口）
                 prediction/、design/、screening/、orchestrator/
deploy/hpc/      preflight_hpc_rerun.py 起飞前自检、verify_hpc_rerun.py 跑完验收
deploy/environment/python/requirements_hpc.txt   本平台环境清单
data/processed/  <数据集>/ 已处理特征 + 标签 + metadata + feature_schema.json
data/raw/        <数据集>/ 原始数据（想重跑特征工程时用）
data/metadata/   feature_config*.json（通道与编码定义）
data/candidate/  todo_data.CSV（候选待测表）
docs/            HPC 环境与外部数据集说明
MANIFEST.md5     全部文件校验和
```

先解压后**在包目录内**执行下面的命令（相对路径都相对包根）。

---

## 0. 校验包完整

```bash
md5sum -c MANIFEST.md5 | grep -v ': OK$'   # 无输出 = 全部一致
python -V                                  # 需要 3.10+
```

## 1. 装环境

```bash
pip install -r deploy/environment/python/requirements_hpc.txt
python -c "import xgboost, torch, sklearn, pandas, numpy; print('deps ok')"
```

> `shap` **不需要**（已从训练代码中移除）。`pandas==2.3.3` 若只能用 conda 装也正常。

## 2. 数据集

`data/processed/` 按数据集分层，用 `--data-set <名称>` 选择（大小写不敏感）：

| `--data-set` | 细胞系/数据集 | 通道×位置 → 特征 | 环境组合 | 计划实验数 | 建议 split |
|---|---|---|---|---|---|
| `DeepCRISPR` | 4（hct116/hek293t/hela/hl60） | 23×8 → 184 | 16 | 1 344 | single + all + mixed |
| `Hiranniramol` | 1 | 23×4 → 92 | 1（`sequence`） | 42 | **只跑 single** |
| `Labuhn` | 1 | 23×4 → 92 | 1（`sequence`） | 42 | **只跑 single** |

* `Hiranniramol` / `Labuhn` 各自目录里只有 1 个数据集，`all`（留一）与 `mixed` 会**退化成
  单数据集划分**（脚本会 WARN，run 名仍叫 `all_*`/`mixed_*`）。
* 想在这两个数据集之间做 leave-one-dataset-out：把它们写进**同一个**输出目录，再用
  `--data-dir` 指向它：

  ```bash
  python core/features/engineering/feature_engineering.py \
      --raw-data data/raw/Hiranniramol/Hiranniramol.CSV \
      --output-dir data/processed/external_combined \
      --config data/metadata/feature_config_sequence_only.json
  python core/features/engineering/feature_engineering.py \
      --raw-data data/raw/Labuhn/Labuhn.CSV \
      --output-dir data/processed/external_combined \
      --config data/metadata/feature_config_sequence_only.json
  # 之后 --data-dir data/processed/external_combined（56 个实验）
  ```

## 3. 起飞前自检（必须 READY）

```bash
# DeepCRISPR
python deploy/hpc/preflight_hpc_rerun.py --package . --data-set DeepCRISPR --batch-name <批次名>

# 想额外断言原始的 1344 / 448 / 192 矩阵形状：
python deploy/hpc/preflight_hpc_rerun.py --package . --data-set DeepCRISPR \
    --batch-name <批次名> --strict-1344

# 外部数据集（只跑 single）
python deploy/hpc/preflight_hpc_rerun.py --package . --data-set Labuhn \
    --batch-name <批次名> --split-types single
```

自检会核对：环境依赖、数据集与 schema 维度、每个数据集的矩阵形状与标签范围、
划分无序列/反向互补泄漏、结果目录未被复用、溯源字段齐全。

## 4. 训练挖掘

用 `run.sh`（推荐；带批次安全闸门与多卡绑定）：

```bash
# DeepCRISPR 全量（single + all + mixed，1344 次）
DATA_SET=DeepCRISPR WORKERS=8 BATCH=<批次名> bash workflows/training/run.sh

# 分片跑
DATA_SET=DeepCRISPR WORKERS=8 BATCH=<批次名> bash workflows/training/run.sh single
DATA_SET=DeepCRISPR WORKERS=8 BATCH=<批次名> bash workflows/training/run.sh all
DATA_SET=DeepCRISPR WORKERS=8 BATCH=<批次名> bash workflows/training/run.sh mixed

# 外部数据集（单数据集目录 -> 只跑 single）
DATA_SET=Hiranniramol TRAINING_SCOPE=none WORKERS=8 BATCH=<批次名> bash workflows/training/run.sh single
DATA_SET=Labuhn       TRAINING_SCOPE=none WORKERS=8 BATCH=<批次名> bash workflows/training/run.sh single
```

* `WORKERS` 建议 = 可用 GPU 数；脚本会把 worker i 绑到第 i 张卡（`GPUS="0 1 2 3"` 可覆盖，
  `GPUS=none` 关闭绑定）。
* `TRAINING_SCOPE` 默认按 DeepCRISPR 的 4 个表观因子展开 16 种组合；纯序列数据集请传
  `TRAINING_SCOPE=none`，让它按该数据集的 `feature_schema.json` 自动展开（只会得到 `sequence`）。
* **断点续跑**：中断后用**同一条命令**再跑即可，已完成的 run 会自动跳过。
* **不要复用非空批次目录**：已存在的 run 会被判为"已完成"而跳过，导致新旧结果混批。
  `run.sh` 会在目录非空时直接拒绝启动。

等价的原生命令（便于自定义规模）：

```bash
python workflows/training/data_digging.py \
    --data-set DeepCRISPR \
    --model-dir models/weights --results-dir results/batches --logs-dir results/logs \
    --batch-name <批次名> --workers 8
```

## 5. 跑完验收

```bash
# 全量
python deploy/hpc/verify_hpc_rerun.py --package . --data-set DeepCRISPR --batch-name <批次名>

# 只跑了部分 split / 部分模型时，用同样的选择参数，否则未跑的会被判为"缺失"
python deploy/hpc/verify_hpc_rerun.py --package . --data-set Labuhn --batch-name <批次名> \
    --split-types single --models linear xgboost mlp transformer cnn
```

验收会核对：计划覆盖度（按数据集 + 所选子集推导）、run 身份唯一性、
`data_fingerprint` / `code_fingerprint` / `env_stack_id` 全批一致、NN 模型是否同一 device、
以及**逐个 run 重算 `split_digest`**。期望 `验收结论: PASS`。

## 6. 预测 / 候选设计（可选）

```bash
python workflows/prediction/predict.py --data-set DeepCRISPR \
    --results-dir results/batches --batch-name <批次名>
```

> 注意：`Hiranniramol` / `Labuhn` 没有基因组坐标，候选输出的「位点」列会是
> `chrUnknown(NA)`（不报错）。若交付模板要求可定位位点，请用 `sgRNA` 序列替代或补坐标。

## 7. 把结果带回来

```bash
tar czf <批次名>.tar.gz results/batches/<批次名> models/weights/<批次名> results/logs/<批次名>
```

本地拿到后在仓库里做分析与验收；`results/` 与 `models/` 在本地是分开归档的。

---

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 自检 `NOT READY` | 按失败项逐条处理；维度/hash 不符时**不要**强行开跑 |
| 提示批次目录非空 | 换 `BATCH` 名，或确认后清空该目录 |
| `找不到数据集 'xxx'` | 名称拼错；错误信息里会列出可用数据集 |
| `environment size=1 超过当前环境数量=0` | 4 通道数据集请传 `TRAINING_SCOPE=none`（当前版本已修，一般不会再见） |
| 部分 run 失败 | 用同一命令重跑 = 断点续跑；跑完用 `verify_hpc_rerun.py` 看缺失清单 |
| `torch.cuda 不可用` | 检查驱动与 CUDA build 匹配（550 驱动 → cu124 轮子） |
