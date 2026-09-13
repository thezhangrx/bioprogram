# CRISPR Scientific Workspace — 验收记录 (Acceptance Record)

> 记录 Round 11 综合回归结果与交付物清单。所有“P0 训练系统零改动/引擎独立”红线由
> 静态守卫测试与架构文档保障; 全部科学计算仍走现有引擎子进程/只读产物。

## 1. 最终回归 (Round 11, 本机沙箱)
| 项 | 结果 |
|---|---|
| 后端 unittest (`backend/tests`) | **19/19 OK** (workspace / workflow interfaces / 真实 E2E smoke / project recovery / 零训练依赖静态守卫) |
| 前端 vitest | **4 文件 / 7 tests OK** (format、artifact 路径解析、StatusChip、EvidenceBadge) |
| 前端 `tsc --noEmit` + `vite build` | OK (54 模块, ~58KB gzip) |
| `scripts/run_workspace.sh` 冒烟 | backend `/api/health` OK · frontend HTTP 200 |
| E2E smoke 内容 | 真实 QC(引擎)→ 训练校验/preflight/dry-run → 真实 `analyse.pipeline`(合成小批次) → 报告 Artifact 读取 |

## 2. 交付物盘点 (对应需求 §44)
1. **新前端目录树** — `docs/frontend_architecture.md` §2; `frontend/` (api 6 客户端, components 10+, views 4)。
2. **页面/Component 结构** — Home(双入口+Projects)/CreateProject/Workspace(侧栏+Notebook Cell)/StandaloneQC。
3. **API 接口定义** — `backend/crispr_workspace/server.py` 路由 + `frontend/src/api/*.ts`; §3 总表。
4. **Workflow 接口** — `project/qc_service/training/analysis` services; state machine 文档 §4。
5. **Training interface** — `TrainingConfig`/`preflight`/`submit`/runs(progress,log,cancel,resume); §5。
6. **QC interface** — Standalone & Workflow 共用引擎; `qc_summary.json`; fingerprint/reuse; §6。
7. **Analysis interface** — Registry 任务目录; heuristic availability; `analysis_plan.json`; §7。
8. **AnalysisPlan interface** — registry→plan 映射 (engine schema 已校验可加载)。
9. **HPC / Runtime interface** — LocalRuntime(独立进程)/HpcRuntime(launcher+回写约定, 不实现 Slurm/CUDA)。
10. **Project recovery** — manifest/status 落盘 + 恢复测试 + Home 重开项目 UI。
11. **Notebook Cell 架构** — NotebookCell + 依赖门禁 (Waiting for dependency) + Cell 级 Run/Collapse。
12. **测试结果** — 上表; `backend/tests/*`, `frontend/src/**/*.test.ts(x)`。

## 3. 验收对照 (P0–P7)
| 优先级 | 结论 |
|---|---|
| P0 Training remains runnable (零改动) | ✅ 静态守卫 + 子进程调用; 未改任何训练代码 |
| P1 HPC remains runnable | ✅ data_digging/predict 原 CLI; HPC launcher 生成; GUI 不绑任务 |
| P2 Existing outputs compatible | ✅ 引擎原样运行, 产物未改 |
| P3 Workflow interfaces correct | ✅ 19 API 路由 + 单测/E2E |
| P4 Project recovery works | ✅ 测试 + UI |
| P5 QC/Training/Analysis integration | ✅ 真实 E2E |
| P6 Notebook-style UX | ✅ 双入口/阶段/单元格/Runs/Reports |
| P7 Viewer polish | ✅ CSV 数据浏览器 + MD 阅读器 + Evidence Badge |

## 4. 需在目标机器上完成的用户侧步骤
- 上传: `bash scripts/build_upload.sh /tmp/Submit_upload.tar.gz` → scp → 解压到 `Submit/`。
- 启动: `conda activate <env>; bash scripts/run_workspace.sh` → 浏览器 `http://127.0.0.1:5173`。
- HPC 真实训练/分析请按 `HPC_EXPERIMENT_PROTOCOL.md` 与 Workflow UI 的 dry-run/preflight 流程执行。
