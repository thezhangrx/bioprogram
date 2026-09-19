# Bash 可复现性 / 用户入口 / README 规范 —— 验收与整改报告

**验收日期**：2026-09-19
**验收目标（boxed）**：`新用户仅依赖 Bash + README + 配置文件 → 完成项目全流程`
**验收方式**：**实机执行**。所有 PASS 均附实际命令与退出码；未能实跑的一律标 `NOT VERIFIED`。
**基线勘察**：`docs/reproducibility/CURRENT_WORKFLOW_MAP.md`（整改前的完整现状与问题清单）

---

## 结论速览

| 维度 | 整改前 | 整改后 |
|---|---|---|
| README 主命令可执行性 | ❌ 5 条中 3 条直接失败 | ✅ 全部通过（`tests/workflow/` 断言 + clean run） |
| orchestrator 生成的命令 | ❌ config 路径不存在、数据集错配、默认输出根是空中楼阁 | ✅ 按数据集解析正确 config；默认输出根 = 项目根 |
| feature_schema 声明 | ⚠️ 声明↔张量**一致**但**声明不足**，需读源码才能确定 encoding | ✅ v2 声明块齐备；`validate_feature_schema.py` 可验证 |
| schema↔tensor 自动校验 | ❌ 无 | ✅ `--all` → **76 passed / 0 failed** |
| 训练超参 CLI 覆盖 | ⚠️ 缺 optimizer/scheduler/activation/num-workers/gpu-id | ✅ 已补齐，**默认值逐位不变**（sha256 证据） |
| `collect_results` 失败退出码 | ❌ 报错却返回 0（脚本化陷阱） | ✅ 返回 1 |
| `main_wizard.py --help` | ❌ 挂起 180 s（直接启动 GUI） | ✅ 立即返回；死导入 `Input.*` 一并修复 |
| 硬编码绝对路径 | ✅ 项目代码 0 命中 | ✅ 保持 0 命中（新增代码亦无） |
| 一致性测试 | ❌ 无 `tests/{schema,cli,workflow}` | ✅ 新增 **132 passed / 18 skipped** |
| 全量测试 | 基线 508 passed / 1 failed | ✅ **515 passed / 32 skipped / 0 failed** |
| 用户视角端到端 | ❌ 无法按 README 走通 | ✅ **21 PASS / 0 FAIL**（`clean_user_test.sh`） |

---

## A. 当前 Workflow（含真实命令）

```text
input
  data/raw/<数据集>/*.csv                      原始 CSV
  data/metadata/feature_config*.json           编码配置（8 通道 / 纯序列）
  data/metadata/datasets.json                  数据集清单（单一数据源）
        │
        ▼  ① python core/features/engineering/validate_feature_schema.py --all
schema 校验（声明 == 实际张量）                   → 76 passed / 0 failed
        │
        ▼  ② python core/features/engineering/feature_engineering.py \
              --raw-data data/raw/DeepCRISPR \
              --output-dir data/processed/DeepCRISPR \
              --config data/metadata/feature_config.json
preprocess                                    → feature_schema.json + 23×8 张量
        │
        ▼  ③ python workflows/training/train.py \
              --model linear --split-type single --cell-line hct116 \
              --environment sequence --data-set DeepCRISPR \
              --results-dir results/batches --model-dir models/weights \
              --logs-dir results/logs --batch-name demo --run-name demo_linear --seed 42
train                                         → R2=0.1320（实测）
        │
        ▼  ④ cat results/batches/demo/demo_linear/linear_regression_metrics.json
evaluate（测试集口径；验证集为 *_validation_metrics.json）
        │
        ▼  ⑤ python workflows/training/data_digging.py --data-set DeepCRISPR \
              --cell-lines hct116 --models linear --split-types single \
              --environments sequence --batch-name demo --dry-run
data digging                                  → Experiment Plan -> Total: 1
        │
        ▼  ⑥ python workflows/prediction/predict.py --data-set DeepCRISPR \
              --batch-name demo --models linear --dry-run
predict                                       → 通道规划 8 通道/184 维（LR 161 维）
        │
        ▼  ⑦ python -m analysis.collect_results --results-dir results/batches --batch-name demo
collect                                       → summary/metrics_tables/*.csv
        │
        ▼  ⑧ python analysis/importance_extraction.py --batch_dir results/batches/demo
            python analysis/anomaly_treatment.py    --batch-dir results/batches/demo
results（关键特征库 + 异常报告）
        │
        ▼  ⑨ python analysis/panorama.py --batch-dir results/batches/demo
            python -m analysis.pipeline --batch-dir results/batches/demo \
                   --output results/batches/demo/analysis
visualization                                 → summary/plots/ + analysis/
```

**编排层**（只读命令生成器，GUI/README/CLI 共用同一份定义）：

```bash
python -m workflows.orchestrator list
python -m workflows.orchestrator command --step feature_engineering --data-set DeepCRISPR
python -m workflows.orchestrator check   --step train_grid --data-set DeepCRISPR
python -m workflows.orchestrator context --data-set Hiranniramol
```

---

## B. feature_schema 规范（当前实际）

**声明版本**：`schema_version: 2`
**位置**：`data/processed/<数据集>/feature_schema.json`（自动生成，**请勿手工编辑**）
**要改编码**：改 `data/metadata/feature_config*.json` 后重跑特征工程。

| 项 | 实际值 | schema 中的声明位置 |
|---|---|---|
| nucleotide encoding | **one-hot** | `encoding.sequence.encoding` |
| alphabet | `A C G T` | `encoding.sequence.alphabet` |
| base → channel | `A→0, C→1, G→2, T→3` | `encoding.sequence.base_to_channel_index` |
| N 的处理 | **不支持**：不在 alphabet 即抛 `ValueError`，**不静默置零** | `encoding.sequence.unknown_base_policy = "error"` |
| channel order | `A C G T CTCF Dnase H3K4me3 RRBS`（8 通道）；`A C G T`（4 通道） | `layout.channel_order` / `channel_names` |
| sequence length | **23 nt** | `sequence_length` / `sequence_definition.length_nt` |
| PAM | **包含在张量内**，第 21–23 位（NGG）；protospacer 第 1–20 位 | `sequence_definition.pam_included_in_tensor` / `pam_positions` |
| environment channel | 逐位点二值，取值 ⊆ {0,1}；顺序 = `environment_features[].name` | `encoding.environment.features` |
| position indexing | **1-based** | `layout.position_indexing` |
| tensor shape | `(23, C)`；C = 8 / 4 | `layout.tensor_shape` |
| flatten order | **位置优先、通道内层**：`flat = pos0 * C + ch` | `layout.flatten_order` / `flatten_index_formula` |
| feature_count | 184（8 通道）/ 92（4 通道） | `feature_count`；`feature_names` 长度一致 |
| normalization | **张量内不做标准化**（`--use-scaler` 是模型级运行时开关，默认关） | `normalization.applied_in_tensor = false` |
| model input dim | linear 剔除 23 个 `*_T` → 161 / 69；xgboost·MLP 用 184 / 92；CNN·Transformer 用 `(23,C)` 不展平 | `model_compatibility.*` |
| source | 生成脚本、feature config 路径与 sha256 | `source` |

**"声明 == 实际"的验证**（用户可自行运行）：

```bash
$ python core/features/engineering/validate_feature_schema.py --all
  -> 76 passed, 0 failed, 2 skipped
结论: PASS — schema 声明与实际张量一致
```

覆盖的断言：必备字段、`channel_count`/`sequence_length`/`feature_count` 与张量维度、
`len(feature_names)`、**由 metadata 序列重建的 one-hot 与张量逐元素相等**（最大绝对差 0.0）、
环境取值 ⊆ {0,1}、`channel_names` 环境段顺序 == `environment_features` 声明顺序、
`layout` 与 `model_compatibility` 自洽。

> **勘察阶段曾担心存在 silent mismatch**（如 schema 写 A/C/G/T 而代码用 G/C/A/T）。
> 实测结论：**不存在**。184 维展平、序列通道重建、环境通道顺序全部一致。
> 真正的问题是**声明不足**——用户无法从 schema 本身读出 encoding、position indexing、
> PAM 是否包含、normalization 等，只能读源码。v2 已补齐。

---

## C. 主入口：用户如何控制实验

**入口**：`workflows/training/train.py`（单次实验）/ `workflows/training/data_digging.py`（网格批量）

```bash
python workflows/training/train.py --help    # 完整参数与 3 组示例
```

| 用户想控制 | 参数 |
|---|---|
| **模型** | `--model {linear,xgboost,mlp,cnn,transformer}` |
| **数据集** | `--data-set DeepCRISPR\|Hiranniramol\|Labuhn`（大小写不敏感）或 `--data-dir <已处理目录>` |
| **超参数** | `--learning-rate` `--batch-size` `--epochs` `--dropout` `--weight-decay` `--patience` `--min-delta` `--hidden-dim1` `--hidden-dim2` `--conv-channels1` `--conv-channels2` `--sequence-kernel {3,5,7}` `--environment-kernel {3,5,7}` |
| **优化器** | `--optimizer {adam,adamw,sgd,rmsprop,adagrad}`（默认 `adam` = 改造前硬编码行为） |
| **调度器** | `--scheduler {none,cosine,step,exponential,plateau}`（默认 `none` = 改造前无调度器） |
| **激活** | `--activation {none,relu,gelu,...}`（默认 `none` = 沿用各模型原有激活，**不统一覆盖** Transformer 的 GELU） |
| **并行 / GPU** | `--num-workers`（默认 0）、`--gpu-id 0` 或 `0,1`（设 `CUDA_VISIBLE_DEVICES`）、`--device cuda\|cpu` |
| **输入路径** | `--data-set` / `--data-dir` |
| **输出路径** | `--results-dir` `--model-dir` `--logs-dir` |
| **seed** | `--seed`（mixed 另可 `--mixed-seeds`） |
| **划分** | `--split-type {single,all,mixed}` + `--train-ratio` `--valid-ratio` `--test-ratio` |
| **环境组合** | `--environment sequence_ctcf_dnase` 形式 |
| **实验/批次名** | `--run-name` `--batch-name` |

**默认值不变性**（关键安全属性）：新增的 5 个参数默认值精确复现改造前行为，实测证据——
同一命令下 `linear_regression_metrics.json` sha256 前后相同（`929869bf…`），
mlp/cnn/transformer 的 `*_metrics.json` 亦逐字节相同；`data_digging` 生成的默认 train 命令行
改造前后 `cmp` 完全一致。

---

## D. data_digging.py（完整命令与参数）

```bash
# 计划模式（不训练、不写文件）
python workflows/training/data_digging.py \
  --data-set DeepCRISPR \
  --cell-lines hct116 hek293t \
  --models linear xgboost cnn \
  --split-types single mixed \
  --mixed-seeds 42 43 \
  --cnn-kernels 3 5 7 \
  --environments sequence sequence_ctcf \
  --batch-name demo \
  --workers 4 \
  --dry-run
```

| 参数组 | 参数 |
|---|---|
| 数据 | `--data-set` / `--data-dir`（二选一，必填） |
| 实验空间 | `--training-scope-epis`（自动展开环境组合）或 `--environments`；`--models` `--cell-lines` `--split-types` `--mixed-seeds` `--cnn-kernels` |
| 输出 | `--batch-name` `--results-dir` `--model-dir` `--logs-dir` |
| 超参 | 与 train.py 同名（含新增的 `--optimizer` `--scheduler` `--activation` `--num-workers` `--gpu-id`） |
| 并行 | `--workers` `--gpus` `--threads-per-worker` `--in-process` |
| 预览 | `--dry-run` |

实测（计划模式）：

```text
[Dataset] DeepCRISPR -> .../data/processed/DeepCRISPR
[Environments] 共 1 种: sequence
[Datasets] ... 下发现 4 个: hct116, hek293t, hela, hl60
Experiment Plan -> Total: 1 | Completed: 1 | Pending: 0
[*] Dry run completed.
```

> 整改前 README **完全没有提到 `data_digging.py`** —— 用户无从知道最重要的分析入口存在。现已作为 §9 独立章节。

---

## E. predict.py（完整命令与参数）

```bash
# 计划模式
python workflows/prediction/predict.py \
  --data-set DeepCRISPR --batch-name demo --models linear --dry-run

# 对候选序列打分
python workflows/prediction/predict.py \
  --data-set DeepCRISPR --batch-name demo \
  --models linear xgboost cnn \
  --target-input data/candidate/todo_data.CSV \
  --target-epigenetics CTCF Dnase \
  --candidate-top-k 50
```

| 参数 | 说明 |
|---|---|
| `--data-set` / `--data-dir` | **必填**（二选一）——整改前 README 漏了它，命令直接 exit=2 |
| `--models` | `linear`/`xgboost`/`mlp`/`transformer`/`cnn`（cnn 展开 3 种卷积核） |
| `--target-input` | 待预测 CSV 或含 CSV 的目录 |
| `--target-epigenetics` | 目标序列**实际具备**的表观通道；缺省从目标文件列自动识别 |
| `--candidate-top-k` | 候选数 |
| `--ultimate-dir` | 终极模型参数目录（默认 `<batch>/summary/ultimate`） |
| `--ultimate-cv-folds` `--ultimate-epochs` `--ultimate-seed` | 终极模型训练参数 |
| `--results-dir` `--batch-name` | 输出位置 |
| `--device` `--dry-run` | 设备 / 计划模式 |

**输入 / 输出契约**：输入 = 候选序列（+可选表观通道）；输出 = `summary/赛道二_results.csv`（候选排序）、
`summary/ultimate/`（模型权重与配置）、`preds_*.npy`。**全部落盘并打印确切路径**，不会只打印到终端。

实测（计划模式）：

```text
[Dry-run] 计划摘要 (未执行任何训练/写入):
  - 模式            : pooled (mixed 已测池自身)
  - 通道规划        : seq=['A','C','G','T'] epi=['CTCF','Dnase','H3K4me3','RRBS'] -> 8 通道 / 184 维
                      (LR 剔除 _T 参照列后 161 维, T 为基准)
  - 将输出          : results/batches/demo/summary/赛道二_results.csv
```

---

## F. README 新增 / 修改章节

README 由「核心程序查找表」重写为「用户操作手册」（337 行 → 约 800 行）。

| 章节 | 状态 | 内容 |
|---|---|---|
| **Quick Start（十一步）** | 🆕 | 每步都是可直接复制执行的完整命令；无「Run preprocessing here」式空指令 |
| 1 项目简介 | ♻️ | 输入 / 输出 / 模型 / 分析目标一览表 |
| 2 仓库结构 | ♻️ | 标注「用户配置区」与「二次开发区」 |
| 3 运行环境 | ♻️ | 两栈对照 + **不可混用的警告** + 无 GPU 说明 |
| 4 数据集 | 🆕 | 三个数据集逐项：Source/License/Raw/Processed/Sequence field/Label field/Length/PAM/Cell lines/Env features/Preprocessing/Split；**明确 label semantics 不可跨数据集比较** |
| 5 Feature schema | 🆕 | 编码规范全表 + 校验命令 + 「只看 schema 能确定的 15 个问题」 |
| 6 预处理 | 🆕 | 三个数据集各自的完整命令 |
| 7 训练 | 🆕 | 最小例子（含实测输出）+ 用户控制表 + 默认值不变性说明 + 批量网格 |
| 8 评估 | 🆕 | 测试集 / 验证集口径区分（此前缺失，曾导致计数错误） |
| 9 数据挖掘 | 🆕 | `data_digging.py` 完整命令与参数表（此前 README 未收录） |
| 10 预测 | 🆕 | 完整命令 + 输入输出契约 |
| 11 结果汇总 | 🆕 | `collect_results` + 退出码语义 + `--results-dir` 配对提醒 |
| 12 可视化 | 🆕 | `panorama.py` + `analysis.pipeline`（含实测输出） |
| 13 输出结构 | ♻️ | `results/` `models/` `logs/` `data/processed/` 逐目录说明 |
| 14 用户应该改哪里 | 🆕 | ✅ 允许修改（config/CLI） vs ❌ 不要修改（core 逻辑），并给出判据 |
| 15 可复现性 | ♻️ | 五要素指纹 + 身份类划分 + 固定种子 + 权威批次状态 |
| 16 编排层 | 🆕 | orchestrator 四个动作 + 步骤清单 + internal 步骤说明 |
| 17 测试 | 🆕 | 科学/app/一致性 三层测试命令 |
| 18 HPC | ♻️ | 打包/自检/验收/环境比对 |
| 19 其它入口 | ♻️ | design/screen/notebooks/app/外部验证 |
| 20 权威定义 | ♻️ | 每概念唯一来源表 |
| **21 已知边界与未自动化部分** | 🆕 | 诚实列出 6 条（见下方 H 的 NOT VERIFIED） |

**README 本身也纳入了自动测试**（`tests/workflow/test_readme_commands.py`）：
抽取 README 中所有 Python 命令，断言脚本/模块存在、**每个 `--flag` 都被目标脚本接受**、
首个命令包含必填参数、引用路径无死链、必要章节关键词齐备。
负向验证：注入 `--source-dir`（错误 flag）后 2 个测试立即失败。

---

## G. 文件归档

### 新增（8）

| 文件 | 作用 |
|---|---|
| `data/metadata/datasets.json` | **数据集清单（单一数据源）**：raw/processed/feature_config/label 语义/cell lines |
| `core/features/engineering/validate_feature_schema.py` | **schema↔tensor 用户级校验器**（`--data-set/--data-dir/--all`） |
| `docs/reproducibility/CURRENT_WORKFLOW_MAP.md` | 整改前现状勘察与问题清单（含 2 处自我更正） |
| `docs/reproducibility/ACCEPTANCE_REPORT_USER_WORKFLOW.md` | 本报告 |
| `tests/schema/test_schema_consistency.py` | schema ↔ tensor 一致性（含常量单值性） |
| `tests/cli/test_cli_contract.py` | CLI 契约（--help/必填参数/退出码/orchestrator 命令） |
| `tests/workflow/test_readme_commands.py` | **README 命令可执行性**（flag 接受性、必填参数、路径死链） |
| `tests/workflow/clean_user_test.sh` | **用户视角端到端验收脚本**（21 项，含 4 项负向） |

### 修改（14）

| 文件 | 改动 |
|---|---|
| `README.md` | 整体重写为用户操作手册（见 F） |
| `core/common/paths.py` | 新增 `datasets_registry()` / `dataset_spec()` / `dataset_feature_config()`（数据集→config 的唯一权威） |
| `core/features/engineering/feature_engineering.py` | schema v2 声明块（encoding/layout/sequence_definition/normalization/model_compatibility/source）；`SCHEMA_VERSION`；config 溯源戳（路径+sha256） |
| `workflows/orchestrator/steps.py` | 修复 feature_config 默认路径（`data/feature_config.json` → 按数据集解析）；默认输出根 `output/` → 项目根；internal 步骤返回 `note`+`artifacts` 而非裸空数组 |
| `analysis/collect_results.py` | 失败返回 **exit 1**（原为 0）；`--help` 加示例与产品说明；`results_root` 不存在时不再 `iterdir()` 崩溃 |
| `app/desktop/main_wizard.py` | 新增 `_cli()`：`--help`/`--version` **立即返回**（原为启动 GUI 挂起 180 s）；无显示环境给出可操作提示；修复死导入 `Input.backend_runner` → `app.desktop.backend_runner` |
| `workflows/training/train.py` | 新增 5 个超参（`--optimizer/--scheduler/--activation/--num-workers/--gpu-id`）+ epilog 示例 |
| `workflows/training/data_digging.py` | 同上 5 个参数并透传；**仅在偏离默认值时才追加 flag** |
| `core/models/{cnn,mlp,transformer}.py` | `build_optimizer/build_scheduler/build_activation`；默认完全等价于改造前 |
| `deploy/environment/python/requirements_frozen.txt` | 更正误导性注释头（原写「HPC 重跑锁定环境」，实际内容是开发栈） |
| `data/processed/{DeepCRISPR,Hiranniramol,Labuhn}/feature_schema.json` | 升级到 v2（**张量与元数据逐字节未变**，24 个文件 sha256 相同） |
| `data/processed/DeepCRISPR/feature_engineering_summary.csv` | 重生成的汇总（内容同步） |

---

## H. Workflow Validation（实测结果）

| 检查项 | 结果 | 证据 |
|---|---|---|
| schema validation | ✅ **PASS** | `validate_feature_schema.py --all` → 76 passed / 0 failed |
| preprocess | ✅ **PASS** | DeepCRISPR 重生成；24 个张量/元数据文件 sha256 逐字节不变 |
| training smoke test | ✅ **PASS** | linear/single/hct116/sequence → `R2=0.1320`；clean run Step4 |
| evaluation | ✅ **PASS** | 测试集与验证集指标文件均可读且分离（Step5/5b） |
| data digging | ✅ **PASS** | `--dry-run` → `Experiment Plan -> Total: 1` |
| prediction | ✅ **PASS** | `--dry-run` → 打印通道规划 8 通道/184 维 |
| result collection | ✅ **PASS** | `metrics_tables` 产物存在；失败路径正确返回 exit 1 |
| README commands | ✅ **PASS** | `tests/workflow/` 断言 + `clean_user_test.sh` **21 PASS / 0 FAIL** |
| 关键特征库 / 异常检测 / 全景图 / 分析引擎 | ✅ **PASS** | clean run Step9/Step10a/Step10b |
| orchestrator（list/command/context） | ✅ **PASS** | clean run Orch 三项 |
| 负向路径（4 项） | ✅ **PASS** | 批次不存在 / 缺必填参数 / 预测缺数据集 / 未知数据集 → 均正确返回非零 |
| 全量测试 | ✅ **PASS** | **515 passed / 32 skipped / 0 failed** |

### NOT VERIFIED（未能实跑，明确标注）

| 项 | 原因 |
|---|---|
| `app/scripts/run_workspace.sh`（Web 工作台） | 需要前端构建与后端服务；未在本次验收中启动 |
| `deploy/hpc/*`（打包 / 自检 / 验收 / 环境比对） | 需要超算环境与已打包批次 |
| `workflows/design/design.py`、`workflows/screening/screen.py` **实际执行** | 仅验证了 `--help` 与 `--dry-run` 存在；未跑真实候选流程 |
| `notebooks/demos/*` | 未执行 Jupyter |
| 完整 1344 网格训练 | 成本过高；本次只跑最小冒烟（README §Quick Start 明确区分 smoke test 与 full experiment） |
| `--num-workers > 0` 端到端 | 沙箱禁止 POSIX semaphore，DataLoader 起 worker 报 `PermissionError [Errno 13]`（环境限制）；已用 recorder 证明参数到达 DataLoader |
| `--gpu-id` 真实绑定 GPU | 本机无 GPU（`torch.cuda.is_available() == False`）；已验证 `CUDA_VISIBLE_DEVICES` 被正确设置（`env_fingerprint` 尾部 `cvd=0`） |
| `app/desktop/main_wizard.py` GUI 实际交互 | 需要 X11 交互；仅验证了 `--help`/`--version` 与窗口可创建 |

---

## I. 仍然存在的人工步骤、环境依赖与未完全自动化部分

不隐瞒：

1. **数据获取仍是人工步骤**。项目不提供从公开源自动下载/校验数据的脚本。用户需按 README §4 的
   来源链接自行获取 CSV 放入 `data/raw/<数据集>/`。各数据集的**许可条款**只能到原文/原仓库确认，
   本仓库未内嵌许可文本。
2. **环境依赖两个不可互换的数值栈**。分析用 `requirements_frozen.txt`（py3.12/torch2.13），
   训练用 `requirements_hpc.txt`（py3.10/torch2.6）。混用会改变 R²。用户必须为训练步骤显式选择栈，
   这一步**无法自动判定**（取决于用户在哪台机器上跑）。
3. **`--environment` 取值需要参考既有组合**。组合名是下划线连接的通道序列，顺序需与 channel 顺序一致；
   README 给了示例，但没有交互式枚举命令（可用 `orchestrator command --step train_grid` 看到项目实际使用的组合）。
4. **本机无 GPU**，神经网络在本机落 CPU。完整网格必须走 HPC（`run.sh`）。
5. **`--layers`（隐藏层数）未暴露为 CLI**。各模型架构层数固定，可调的是 `--hidden-dim1/2`、
   `--conv-channels1/2`；Transformer 的 `num_layers/d_model/nhead/dim_feedforward` 已是 `train()` 形参、
   只差 CLI 接线（纯增量、低风险，本次未做以避免扩大改动面）。
6. **`data_digging --gpu-id` 与既有 `--gpus`（worker 轮转绑定）是两套机制**，同时使用时 train.py 内的
   `os.environ` 覆盖会胜出（已在 `--help` 注明）。
7. **`SEQUENCE_LENGTH` / `DEFAULT_SEQUENCE_CHANNELS` 仍各有两处定义**（取值一致）。
   本次未做去重（会触及多个模块的导入面），改为用 `tests/schema/` 断言锁死一致性——
   这是"先加护栏、再重构"的选择。
8. **`cnn.py` 的通道名回退分支**（`sequence_channels != 4` 时用 `["A","G","C"]`）仍是潜在 silent mismatch 源。
   当前所有数据集都是 4 序列通道，因此不会触发；已在 Workflow Map 中记录，本次未改。

---

## J. 本报告所有 PASS 的验证入口

```bash
# 1. schema ↔ tensor
python core/features/engineering/validate_feature_schema.py --all

# 2. 一致性测试（schema / CLI / README 命令）
python -m pytest tests/schema tests/cli tests/workflow -q

# 3. 全量测试
python -m pytest tests/ -q

# 4. 用户视角端到端（21 项，含负向）
bash tests/workflow/clean_user_test.sh
```
