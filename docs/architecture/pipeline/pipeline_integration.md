# 统一编排层与前端整合（pipeline ⇄ wizard ⇄ web workspace）

本文档说明本轮把**桌面向导**、**网页工作台**与**底层脚本**统一到同一份流程定义后的架构、
接口与验证方式。它解决了此前"前端与引导程序各自为政"的问题。

---

## 1. 改造前的问题（实测）

| 问题 | 证据 |
| :--- | :--- |
| 两套互不感知的编排器 | 向导 `app/desktop/backend_runner.py` 自行拼 7 步 subprocess；网页 `app/backend/crispr_workspace/` 自行拼 CLI |
| 覆盖不一致 | 向导有 特征工程 / collect_results / anomaly_treatment / importance_extraction / 遗留可视化 / 交付物核对；网页**全都没有**（只有 QC、训练、analyse.pipeline） |
| 规则重复 | `workflows/training/data_digging.py` 注释写明"与 `app/desktop/backend_runner.build_active_environment_combinations` 同规则"——复制而非共用 |
| 前端点不到候选生成 | 后端 `TrainingConfig.kind` 已支持 `"predict"`，但前端 `TrainingPanel` 把 `kind` 写死为 `"dig"` |
| **运行状态永远 running** | 子进程结束后成为僵尸进程，`os.kill(pid, 0)` 仍成功 → 前端轮询永远拿不到 `completed`（本轮修复） |

---

## 2. 改造后的架构

```text
                 ┌──────────────────────────────┐
                 │   pipeline/steps.py（唯一真源）│
                 │  步骤 · 命令 · 依赖 · 产物     │
                 └───────┬──────────────┬───────┘
                         │              │
        ┌────────────────▼───┐   ┌──────▼─────────────────────────┐
        │ 桌面向导            │   │ 网页工作台                      │
        │ app/desktop/backend_runner│   │ app/backend/crispr_workspace/       │
        │  (7 步, Tkinter)    │   │  pipeline.py（步骤服务）         │
        └────────┬────────────┘   │  files.py（文件浏览）            │
                 │                │  training.submit_command（运行） │
                 │                └──────┬──────────────────────────┘
                 │                       │  /api/pipeline/*, /api/files/*
                 │                       │
                 ▼                       ▼
        ┌───────────────────────────────────────────────┐
        │  同一批底层脚本（科学计算零改动）               │
        │  core/features/engineering/feature_engineering.py · workflows/training/data_digging.py  │
        │  workflows/prediction/predict.py · analysis/collect_results.py       │
        │  analysis/anomaly_treatment.py                  │
        │  analysis/importance_extraction.py              │
        │  analysis/visualization.py · analyse.pipeline   │
        └───────────────────────────────────────────────┘
```

* **唯一定义源**：步骤、命令、依赖、产物只在 `pipeline/steps.py` 定义一次。
* **向导**：改为 `step_context()` + `step_command()` 调用共享层，行为与原实现一致（有测试锁定）。
* **网页后端**：新增 `pipeline.py`（列出/执行步骤）与 `files.py`（文件浏览），执行统一走
  `training.submit_command()`，因此**流程步骤与训练共用同一 run 存储**。
* **两种批次布局都兼容**：`batch_name` 非空 → `results/<batch>/`；为空 → `results/` 本身即批次目录
  （向导的独立输出根）。

---

## 3. 步骤注册表（9 步）

| step_id | 类别 | 重任务 | 产物（相对批次目录） |
| :--- | :--- | :---: | :--- |
| `feature_engineering` | data | | `data/processed/feature_schema.json`（仓库相对） |
| `train_grid` | train | ✅ | `summary/metrics_tables/all_experiments.csv` |
| `generate_candidates` | train | ✅ | `summary/赛道二_results.csv` |
| `collect_results` | analysis | | `summary/metrics_tables/all_experiments.csv` |
| `anomaly_treatment` | analysis | | `summary/anomaly_report.md` |
| `importance_extraction` | deliverable | | `summary/feature_importance/key_regulatory_biomarkers.csv` |
| `legacy_visualization` | analysis | | `summary/plots/` |
| `analysis_engine` | analysis | | `summary/{analysis_status.json,summary,figures}` |
| `deliverables_check` | deliverable | | 内部只读检查（无子进程） |

调试命令（只读，不执行）：

```bash
python -m workflows.orchestrator list                       # 步骤清单
python -m workflows.orchestrator check                      # 按真实产物核对每步状态
python -m workflows.orchestrator command --step train_grid  # 预览命令
python -m workflows.orchestrator order                      # 依赖拓扑顺序
```

---

## 4. 新增 API

| 方法 | 路径 | 说明 |
| :--- | :--- | :--- |
| GET | `/api/pipeline/steps?batch=` | 步骤清单 + 产物状态 + 依赖就绪 + 命令预览 |
| POST | `/api/pipeline/run` | `{step_id, dry_run?, batch_name?, options?}`；重任务可 dry-run 预览 |
| GET | `/api/files?path=` | 目录列表（仅仓库内、排除 `.git/.venv/node_modules/__pycache__`） |
| GET | `/api/file-preview?path=` | 文本/JSON/CSV（截断 512 KB）/图片元数据 |
| GET | `/api/file-raw?path=` | 原始字节（图片、下载；≤8 MB） |
| GET | `/api/runs`、`/api/runs/<id>/log`、`/cancel`、`/resume` | 训练与流程步骤共用 |

安全：`files.py` 做仓库根边界检查与敏感目录拒绝（越界与 `.venv` 均返回 404+错误信息）。

---

## 5. 前端新增能力

| 组件 | 作用 |
| :--- | :--- |
| `components/PipelinePanel.tsx` | 按类别展示 9 个步骤：状态点、依赖、产物链接（点击在文件查看器打开）、dry-run 开关、重任务二次确认、运行 |
| `components/RunLogViewer.tsx` | **实时输出**：轮询 `/api/runs/<id>/log`，原样显示脚本 `print` 文本（子进程 stdout+stderr），带进度、Cancel/Resume、自动滚动 |
| `components/FileBrowser.tsx` | 项目文件浏览与预览：目录树、CSV 表格预览、Markdown/文本、图片、原始文件下载 |
| `TrainingPanel` | 改用 `RunLogViewer`（训练输出从"一次性读取"变为实时） |
| `WorkspaceView` | 新增两个 Notebook cell：`Pipeline / Deliverables` 与 `Project Files` |

前端入口：`bash app/scripts/run_workspace.sh` → http://127.0.0.1:5173

---

## 6. 本轮修复的真实缺陷

**僵尸进程导致状态永远 `running`**（直接影响"前端反映训练状况"）：

* 现象：子进程结束后父进程未 `wait()`，进程成为僵尸；`os.kill(pid, 0)` 对僵尸仍成功，
  于是 `_update_status` 一直判定"运行中"。
* 修复：`training.py` 新增 `_process_alive()`（Linux 下检查 `/proc/<pid>/stat` 的 `Z` 状态）
  + 提交时启动 daemon reaper 线程写 `done` 文件；服务重启后仍由日志兜底判定。
* 验证：`app/backend/tests/test_pipeline_orchestration.py::TestRunLogStream`（快速子进程必须变为
  `completed`）与真实 API 冒烟（`anomaly_treatment` → `status=completed, rc=0`）。

---

## 7. 验证记录

| 项目 | 结果 |
| :--- | :--- |
| 共享层一致性（向导 vs 注册表） | `app/backend/tests/test_wizard_shared_pipeline.py`（6 项） |
| 步骤/文件服务 | `app/backend/tests/test_pipeline_orchestration.py`（13 项） |
| backend 全量 | **38 tests OK** |
| analyse 全量（未受影响） | **174 tests OK** |
| 前端类型检查 + 构建 | `npm run build` 通过（`dist/` 生成） |
| 前端测试 | **23 tests passed**（含新增 7 项） |
| 真实 API 冒烟（服务 :8790） | `/api/pipeline/steps` 9 步；`deliverables_check` → completed；`train_grid` dry-run → run manifest；`anomaly_treatment` → **completed, rc=0**，日志 7 行 print 文本可读；`/api/files`、`/api/file-preview`（赛道二_results.csv，20 行）、`/api/file-raw`（PNG 119 KB）；`../../etc/passwd` 与 `.venv` 均被拒绝 |

---

## 8. 使用方式

```bash
# 1) 网页工作台（前端 → 后端 → 共享层）
bash app/scripts/run_workspace.sh         # 后端 :8765 + 前端 :5173
#    Workspace → cell 7「Pipeline / Deliverables」：勾选 dry-run → Run；cell 8「Project Files」查看产物

# 2) 桌面向导（同一份步骤定义）
python app/desktop/main_wizard.py

# 3) 命令行（同一份步骤定义）
python -m workflows.orchestrator check
python -m workflows.orchestrator command --step importance_extraction
```

> 重任务（`train_grid`、`generate_candidates`）会真实写入 `models/`、`results/`、`logs/`；
> 前端会二次确认，且可先用 dry-run 预览命令。

---

## 9. 前端（Web）与调试（CLI）的明确分工

> 本节对应"注意区分前端和调试"的要求。

| 维度 | **前端（Web 工作台）** | **调试 / 命令行** |
| :--- | :--- | :--- |
| batch 概念 | **完全没有**（界面上不存在任何 batch 输入） | `--batch-name` 可选参数，默认空 = 直接使用 `results/` 目录本身 |
| 批次定位方式 | 用户在 Cell 01「Name」用**目录弹窗**选择绝对输出目录 | `python -m workflows.orchestrator command --step X --output-dir <abs> [--batch-name <name>]` |
| 训练结果位置 | `<输出目录>/results`（`models/`、`logs/` 同层） | 同上；带 `--batch-name` 时为其子目录（用于复核既有交付结果） |
| 项目名 | 可随时修改（Cell 01），并体现在项目列表 | —（CLI 无项目概念） |
| 删除 | 弹窗 + **3 秒倒计时**后确认；级联删除项目目录与输出目录 | `DELETE /api/projects/<id>`（可加 `?force=1`，默认不删受保护路径） |
| 路径 | **不拼接路径**：所有路径由后端返回（`/api/pipeline/steps` 的 `context` 全为绝对路径） | 同样强制绝对路径；共享层对相对路径直接报错 |

调试用法示例（复核仓库内既有交付结果 `results/batches/batch_20260909_full`）：

```bash
python -m workflows.orchestrator check    --output-dir "$PWD" --batch-name batch_20260909_full
python -m workflows.orchestrator command  --step collect_results --output-dir "$PWD" --batch-name batch_20260909_full
#   -> analysis/collect_results.py --batch-dir /.../Submit/results/batches/batch_20260909_full
```

前端用法（无 batch；命令由后端按绝对路径拼装）：

```
Cell 01 Name  -> 选择输出目录 /home/.../workspace/projects/<id>/output
Cell 05 Training -> workflows/training/data_digging.py --results-dir /home/.../output/results --model-dir .../models --logs-dir .../logs
Cell 06 Analysis -> 直接使用 /home/.../output/results（无需用户输入）
```

## 10. 删除安全规则（事故驱动修订）

**规则**：删除项目时，只有满足以下条件才会真正删除输出目录——
* 该目录位于工作区内（`<repo>/workspace/...`），或仓库之外；
* 仓库内的**任何**路径（`results/`、`models/`、`logs/`、`data/`、`paper/` 及其**任意下级目录**）
  一律受保护，跳过并如实回报。

**背景（真实事故与修复）**：早期实现只保护仓库的**直接子目录**，未覆盖 `results/<batch>/`。
在测试级联删除时，指向 `results/batches/batch_20260909_full` 的输出目录被整目录删除，
导致 1344 个实验目录与 `summary` 丢失。已从当日 19:32 的打包备份
（`/tmp/test_upload.tar.gz`，含 10 301 个 `results/` 文件）完整恢复，
并新增回归测试 `test_delete_protects_nested_repo_dirs` 锁定该规则。

**恢复核验**：实验目录 1 344 个；`summary` 表格 27 / 报告 15 / 图 293；
`summary/feature_importance` 8、`summary/plots` 503；`paper/make_assets.py`
可重新生成全部论文资产（192 配对、166/1906 边、596 模式、64 个 FDR<0.05，数值与事故前一致）。
