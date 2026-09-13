# Frontend / Workflow Architecture (CRISPR Scientific Workspace)

> 状态: **终版草案 (Rounds 1–9)**。后端 18 项单测 + 真实 E2E smoke 通过; 前端 tsc/vite build + vitest 通过。
> 目标体验: Notebook-like Scientific Workspace (Jupyter + Dashboard + Experiment Manager)。

## 1. 架构原则
- 前端 = Orchestrator: UI / 配置 / 编排 / 启动 / 状态监控 / 日志 / 结果浏览 / 用户决策。
- 科学计算 (QC/Training/Analyse/Statistics/XAI/Reports) 只经 **现有引擎**: 只读产物 或
  子进程调用 `data_digging.py / predict.py / analyse.pipeline / data_QC.py`。
- **禁止**: 前端 import 训练/统计模块、复制科学判定 (SNR/FDR/evidence)、修改任何训练代码/参数默认/seed/split/CLI/产物。
- 状态一律来自磁盘 manifest/status json; GUI 可替换、各引擎可独立、Training 可脱离 GUI 在 HPC 运行。

## 2. 目录结构
```text
backend/
└── crispr_workspace/          # 本地 Workflow API (零第三方依赖, stdlib http.server)
    ├── config.py              根/白名单/用户配置 (CRISPR_WORKSPACE_ROOT 等)
    ├── store.py               JSON 原子读写
    ├── fingerprint.py         数据集 sha256 指纹
    ├── project.py             Project + project_manifest.json + create_from_qc
    ├── qc_service.py          Standalone/Workflow QC 会话 (子进程 data_QC)
    ├── training.py            TrainingConfig/Preflight/Local+HPC Runtime Adapter
    ├── analysis.py            Registry 任务目录/AnalysisPlan/pipeline 运行与状态
    ├── artifacts.py           Artifact Resolver (csv 分页/md/json/image, 路径白名单)
    └── server.py              /api/* 路由
backend/tests/                 (18 项: workspace/workflow/e2e/recovery)
frontend/                      React18+TS+Vite+Tailwind
├── src/api/{client,project,qc,training,analysis,artifacts}.ts
├── src/components/{StatusChip,NotebookCell,EvidenceBadge,TrainingPanel,AnalysisPanel,ReportsPanel,RunsHistory,QcDashboard}
├── src/components/artifacts/{ArtifactViewer,CsvViewer,MarkdownViewer}
├── src/views/{HomeView,WorkspaceView,StandaloneQcView}   # Create Project 直接进 Workspace
└── src/lib/format.ts · types.ts · App.tsx · main.tsx
docs/frontend_architecture.md    (本文)
scripts/run_workspace.sh / scripts/build_upload.sh
```

## 3. API 一览 (Workflow)
| 域 | 端点 |
|---|---|
| meta | GET /api/health |
| project | GET/POST /api/projects · GET /api/projects/{id} · POST /api/projects/from-qc · POST /api/projects/{id}/stage |
| qc | POST /api/qc/sessions · GET /api/qc/sessions[/{id}] · POST /api/qc/fingerprint · POST /api/qc/reuse-check |
| training | GET /api/training/defaults · POST /api/training/preflight · POST /api/training/submit · GET /api/runs · GET /api/runs/{id}[/log] · POST /api/runs/{id}/cancel\|resume |
| analysis | GET /api/analysis/tasks · POST /api/analysis/plan · POST /api/analysis/run · GET /api/analysis/status · GET /api/analysis/outputs |
| artifacts | GET /api/artifacts?path=&offset=&limit= · GET /api/artifact-raw?path= |

## 4. 状态与持久化 (Project recovery)
- `project_manifest.json` (stages: data/qc/mapping/training/analysis/reports + stage_detail + config_versions)
- `qc_sessions/<id>/session_manifest.json` + `qc_summary.json` + `quality_report.md`
- `runs/<id>/training_status.json` (status/progress/log/done 标记; dry-run/submitted_external/running/completed/failed/cancelled)
- analysis 输出 `analysis_status.json` + `execution_log.json`
前端不猜状态; 重新打开项目即从上述文件恢复 (Round5 recovery 测试覆盖)。

## 5. Training / Runtime 契约
- TrainingConfig 只含训练系统现有参数; 保存→Validate→**Preflight**(数据集/输出可写/配置/runtime/目标输入) → Run。
- Local: 独立子进程 + start_new_session (GUI 关闭继续); Cancel 经 Adapter SIGTERM 进程组; Resume=同命令重跑(断点续跑)。
- HPC: Adapter 只生成可提交 launcher 与回写约定 (`submitted_external` + job 侧写 training_status.json), 不实现 Slurm/CUDA。

## 6. QC 接口 (双入口共用引擎)
- Standalone: 首页「Dataset Quality Check」→ 多文件/目录 → data_QC(只读, CPU) → Dashboard/报告/导出。
- Workflow: 项目 QC Cell 复用同引擎; 决策写 `workflow_config.json`, 不改原始数据。
- 指纹复用: 相同指纹可复用旧 QC; 数据变化则拒绝 (后端守卫) → from-qc 建项目。

## 7. Analysis / AnalysisPlan
- 任务目录来自 `analyse/registry`; Selected/Available(含 reason)/Unavailable/Skipped/Completed 由引擎与启发式共同呈现, 最终由引擎运行时判定。
- 勾选 → `analysis_plan.json` (engine AnalysisPlan schema) → analyse.pipeline 子进程 → 逐 task 状态/产物; 报告列出 summary md 并可阅读。

## 8. Notebook Cell 模型
- Cell: Data / QC / Mapping(决策) / Training / Analysis / Reports; 每格可 Run/Collapse; 依赖未满足显示 “Waiting for dependency” (不硬报错)。
- 重新执行只作用于该 Cell (分析可仅重跑当前分析与配置)。

## 9. Artifact Viewer
- 统一 `ArtifactViewer` 按类型分派; CSV = 数据浏览器 (服务端分页/搜索/排序/列显隐/冻结首列/科学格式/缺失“—”/Evidence Badge/方向仅限 Δ 类列); MD = 科研报告阅读器 (标题/表格/代码/引用/列表/图经 Resolver/artifact 链接可点); 原始值始终保留 (Raw ≠ Display), 不做任何重算。

## 10. 测试与 E2E smoke
- 后端 18 项 (workspace / workflow interfaces / **真实 E2E: QC(引擎)→训练校验+preflight+dry-run→真实 analyse.pipeline→报告读取** / project recovery)。
- 前端 vitest 4 项 (format、artifact 相对路径解析) + `tsc` + `vite build`。
- P0 训练系统零改动; 既有产物不变 (引擎原样调用)。

## 11. 运行
```bash
bash scripts/run_workspace.sh           # 后端 8765 + 前端 5173 (打开 http://127.0.0.1:5173)
# 后端独立: PYTHONPATH=backend python3 -m crispr_workspace.server --port 8765
# 打包上传: bash scripts/build_upload.sh /tmp/Submit_upload.tar.gz
```

## 12. 验收对照
- 双入口(Create Project / Dataset Quality Check) ✅ · QC 只读+指纹守卫 ✅ · Training(本地独立进程/HPC launcher)+Preflight+Monitor ✅
- Analysis(AnalysisPlan from Registry+逐 task 状态) ✅ · Notebook Cells+依赖门禁 ✅ · Artifact Viewer(CSV/MD) ✅
- Reports/History/Runs ✅ · Project recovery ✅ · GUI 可替换/引擎独立/HPC 不绑 GUI ✅ · 未修改训练系统与既有产物 ✅


---

## 附：统一编排层整合（本轮新增）

* **共享步骤定义**：`pipeline/steps.py`（向导与网页共用）；服务层 `backend/crispr_workspace/pipeline.py`。
* **新增 API**：`/api/pipeline/steps`、`/api/pipeline/run`、`/api/files`、`/api/file-preview`、`/api/file-raw`。
* **新增组件**：`PipelinePanel`（9 步运行/状态/产物）、`RunLogViewer`（实时 print 输出 + Cancel/Resume）、
  `FileBrowser`（目录浏览 + CSV/Markdown/图片预览）；`TrainingPanel` 改用 `RunLogViewer`。
* **文件安全**：仅允许仓库根内路径，拒绝 `.git/.venv/node_modules/__pycache__` 与越界路径。
* **修复**：子进程僵尸态导致的"状态永远 running"（`training._process_alive` + reaper 线程写 done 文件）。
* 详见 `docs/pipeline_integration.md`。


---

## 附二：工作台流程改版（本轮）

| Cell | 模块 | 说明 |
| :--- | :--- | :--- |
| 01 | **Batch** | 用户输入 batch 名 + 训练结果输出目标文件夹（决定 results/models/logs 的批次目录） |
| 02 | **Data Input** | 选择已测/待测数据集，运行**数据集探测**程序 → 细胞系与表观通道 |
| 03 | Quality Control | 现有 QC |
| 04 | **User Decision / Mapping** | 探测完成后显示：逐通道列出实际出现的符号（如 **A**、**N**）并选择映射；保存后在本 cell 内可选执行**特征工程** |
| 05 | **Training / Device** | Cells / Scope epi 选项来自 Cell 02 探测结果；**Device** 取代 Runtime（cpu / gpu / cpu/gpu，按模型锁定）；填写输出目录；可选执行候选生成 |
| 06 | Analysis | `Training results batch` 默认取 Cell 05 的批次；可选执行 collect_results / anomaly / importance / 全景图 / 分析引擎 |
| 07 | Reports | 报告 + 可选交付物核对 |
| 08 | Project Files | 文件浏览与预览（CSV/Markdown/图片） |

* **Create Project** 不再经过独立表单页：点击即创建并进入 Workspace；Home 的项目列表支持**手动删除**。
* 流程步骤不再集中在单独模块，而是**嵌入各自阶段**，每个步骤都有勾选框，用户自行决定是否执行。
