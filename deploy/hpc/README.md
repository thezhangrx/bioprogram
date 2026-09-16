# HPC 重跑说明（1344 次实验）

本目录 = 待上传到超算的完整**训练**包（数据 + 代码 + 自检/验收脚本）。
本批次采用 **group-aware 无泄漏划分**（见 `docs/audit/HPC_RERUN_PREFLIGHT.md`）。
**已发布的权威批次名为 `ultimate_run`**（1344/1344，验收 PASS）；下表命令里的
`<新批次名>` 请替换为你本次要创建的新目录名——不要复用 `ultimate_run` 或任何已存在的非空目录。

**超算只负责训练出数据**（1344 个 run 的指标/预测/重要性/元数据）；
所有分析、统计检验、图表、论文资产都在本地用仓库的 `analysis/` 完成。
因此本包**不含** `analysis/`、`tests/`、`app/backend/`、`app/frontend/`。

包指纹（用于确认上传的是正确版本，任一次抽样 run 的 `*_info.txt` 都应一致）：
`code_fingerprint = 7a623e031a7c5272`、`data_fingerprint = ecac199fa27ea80d`。
`MANIFEST.md5` 列出全部文件校验和，上传后可用 `md5sum -c MANIFEST.md5` 自检。

## 目录

```
workflows/training/train.py                       单实验训练入口（被 data_digging 逐个调用）
workflows/training/data_digging.py                网格调度：展开 16 环境 × 4 模型 × 3 split = 1344
workflows/training/run.sh                         批量入口（含批次安全闸门）
workflows/prediction/predict.py                   候选预测（本次重跑不需要）
core/                                             模型与数据处理
data/processed/<数据集>/                          已处理特征 + 标签 + metadata
                                                   (DeepCRISPR/ Hiranniramol/ Labuhn/)
deploy/hpc/preflight_hpc_rerun.py                 起飞前自检（只读）
deploy/hpc/verify_hpc_rerun.py                    跑完后验收（只读）
deploy/environment/python/requirements_hpc.txt    本平台环境清单 ← 按这个装
deploy/environment/python/requirements_frozen.txt 开发机审计栈（用于比对差异）
docs/audit/HPC_ENVIRONMENT_FIT.md                 平台适配说明（cu124、多卡绑定、等价性验证）
docs/audit/HPC_ENV_COMPATIBILITY_REPORT.md        ★实测报告：你的栈能不能跑 + 实测数值偏移
docs/audit/HPC_RERUN_PREFLIGHT.md                 自检报告（含证据、限制、验收标准）
```

## 三步走

```bash
# 0) 环境：你现有的 crispr 环境(3.10.21)已实测可跑，只需补三个"未确认"的包
#    pip install -r deploy/environment/python/requirements_hpc.txt
#    python -c "import xgboost,torch;print(xgboost.__version__, torch.__version__)"   # 必须都有
#    注意：本项目已移除 shap 依赖（SmoothGrad/DeepSHAP 已下线），HPC 环境不需要 shap
#    实测结论与数值偏移见 docs/HPC_ENV_COMPATIBILITY_REPORT.md

# 1) 起飞前自检：必须打印 "结论: READY"
python deploy/hpc/preflight_hpc_rerun.py --package . --data-set DeepCRISPR --batch-name <新批次名>

# 2) 全量重跑（DATA_DIR 必填：去掉指向 DeepCRISPR 的隐式默认）
DATA_SET=DeepCRISPR WORKERS=8 bash workflows/training/run.sh
#   bash workflows/training/run.sh single | ... all | ... mixed   # 分片跑
#
#   外部数据集（4 通道 / 只有 sequence 环境）：用 DATA_SET=<名称> 指定即可
#   DATA_SET=Hiranniramol TRAINING_SCOPE=none WORKERS=8 bash workflows/training/run.sh
#   DATA_SET=Labuhn       TRAINING_SCOPE=none WORKERS=8 bash workflows/training/run.sh
#   —— TRAINING_SCOPE 留空/设为 none 时按该数据集的 feature_schema.json 自动展开；
#      4 通道只会得到 1 种组合，计划规模 14（单数据集）而非 1344。
#   —— 自检同样用 --data-set（可加 --strict-1344 只对 DeepCRISPR 断言 1344 矩阵）：
#      python deploy/hpc/preflight_hpc_rerun.py --package . --data-set Hiranniramol --batch-name <名>
#   中断后用**同一命令**再跑 = 断点续跑（已完成的 run 自动跳过）
#   GPU 节点上 torch 自动用 cuda；WORKERS 建议 = 卡数(8)，脚本自动把 worker i 绑到第 i 张卡
#   GPUS="none" 关闭绑定; GPUS="0 1 2 3" 显式指定（详见 docs/HPC_ENVIRONMENT_FIT.md）

# 3) 跑完验收：必须打印 "验收结论: PASS"
python deploy/hpc/verify_hpc_rerun.py --package . --data-set DeepCRISPR --batch-name <新批次名>
tar czf <新批次名>.tar.gz results/batches/<新批次名>
```

## 硬性约束

| 约束 | 原因 |
|---|---|
| **不要**改 `BATCH` 为 `batch_20260909_full`（已废弃的泄漏批次） 或任何已存在的非空目录 | 已存在的 run 会被判定「已完成」而跳过，新旧（泄漏/无泄漏）结果混批 |
| 不要手改 `core/data/splitting/cell_line_division.py` 的划分逻辑 | 该文件内的 `assert_no_sequence_leakage` 是泄漏闸门，改动会使结论失效 |
| 不要移动/改名 `data/processed/<数据集>/` 下的文件 | 每个 run 记录 `data_fingerprint`，改名会导致全批指纹不一致 |
| 跑完后不要只拷贝部分 run 目录 | 验收脚本按 1344 全覆盖核对 |

## 每个 run 会落盘什么

`results/batches/<batch>/<run_name>/`：
`*_metrics.json`（test 指标）、`*_predictions.csv`、`*_validation_*`、`*_info.txt`（含配置 + 划分审计）、
`*_config.json`（NN 模型）、`*_feature_importance.csv`。

`*_info.txt` 里与可复现性相关的字段：

```
group_aware: True
split_digest: 3ff84988cab5900c          # 划分的 sha256 前 16 位
n_train / n_valid / n_test: 2968 / 635 / 636
heldout_sequences_excluded_from_train: 0     # 仅 LOCO 有意义
audit_train_test_sequence_overlap: 0         # 必须为 0
audit_train_test_revcomp_overlap: 0          # 必须为 0
data_fingerprint / code_fingerprint: ...
device_resolved: cuda:0                      # 或 cpu
```
