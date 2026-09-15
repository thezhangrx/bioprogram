# 项目完整流程与代码实现说明

> 生成时间：2026-09-12 08:41　|　代码基线：工作区快照（git commit `9b2def2b`, branch `main`, 含 886 删除/348 未跟踪等未提交改动）
> 生成方式：AST 扫描（77 个 .py / 564 个函数与方法）+ 4 路并行人工阅读函数体（READ-ONLY，未修改任何项目代码）。

## 关键发现速览（本次逆向梳理实测）

1. **`all` 划分在网格中等价于 `single`（逐位相同）**：`workflows/training/data_digging.py` 只传 `--cell-line`，
   `workflows/training/train.py:663-664` 回填 `cell_lines=[cl]`，`split_all_cell_lines:214-217` 的退化保护改为细胞系内划分；
   实测 8/8 组（mlp/xgboost/transformer/cnn × hct116/hela）六项指标逐位相同。真正的 LOCO 分支因
   `test_fraction=0.0` 触发 `validate_split_fractions` 的 `>0` 校验而抛错、当前不可达。→ 网格未提供跨细胞系泛化实验。
2. **环境组合 = 通道零掩码，不降维**：未选表观通道被置 0，2D 输入恒为 `(N,184)`、3D 恒为 `(N,23,8)`
   （`cell_environment_combination.apply_environment_combination`）。
3. **当前 schema**：`[A,C,G,T,CTCF,Dnase,H3K4me3,RRBS]`、23×8=184；线性回归单独剔除 23 个 `_T` 列 → 161
   （`core/xai/importance/xai_importance.py` 白名单与 `linear_regression.select_non_t_reference_features`）。
4. **XAI 实况**：XGB G/W/C+TreeSHAP、MLP IG、CNN IG+ISM（全部 23×C 位点翻转）、
   Transformer 注意力+熵（熵是**全局标量广播**到所有位置）；**未实现**：permutation test、
   CNN_IG_SNR；Transformer IG 有函数但**从未被调用**。SNR 星级阈值只在
   `analysis/importance_extraction.py` 后处理里，`src/` 内没有。
5. **workflows/prediction/predict.py 与网格训练不是同一训练机制**：workflows/prediction/predict.py 直接 import 模型类并以
   AdamW/lr=1e-3/batch=256/epochs=15（默认）训练、10 折 `KFold`、**无早停**；网格路径经 `workflows/training/train.py`
   使用 Adam/MSE/batch=64/epochs=100/patience=20。workflows/prediction/predict.py 的断点续跑判据是 `ultimate/progress.json`
   + `preds_<kind>.npy`，**不扫描 results/batch**。
6. **实跑分析产物规模（1344 实验批次）**：`summary` 9 篇 summary、10 张 tables、15 张 figures；
   `attribution_summary.csv` 实测 **331,200 行**；证据矩阵 4 行、Tier 全 Inconclusive（不稳定上下文隔离 +
   环境主效应发散），status_counts = completed 9 / unavailable 4 / skipped 3。
7. **前端/Workflow 现状**：26 条 API 路由；`workflow_config.json` 与 `pipeline_config.json` **无任何写入实现**；
   `analysis_status.json` 实测不含 `engine_version/batch/config` 与 task `completed_at`（与
   `docs/interface_contract.md` 描述不符）；standalone QC 多文件输入实际只取第一个文件。

---

## 目录

- **总说明与总流程（§0–§1）**
- 0. 文档说明
  - 0.1 文档目的
  - 0.2 分析范围
  - 0.3 代码基线（快照）
  - 0.4 方法与判据
  - 0.5 文档与代码不一致的总体清单（先总后分）
- 1. 项目总体流程
  - 1.1 总流程图（真实实现的三种主要入口）
  - 1.2 分析引擎（analyse）的执行顺序
  - 1.3 条件分支与并行机制（代码事实）
  - 1.4 数据流（形态变化，逐段标注负责程序）
- **数据输入 / QC / 预处理 / 特征工程 / 数据划分（§2–§6）**
- 2. 数据输入
  - 2.1 输入形态与入口
    - 2.1.1 三个入口，职责不同
    - 2.1.2 原始 CSV 的真实列结构
    - 2.1.3 列自动识别与编码自适应（QC 侧）
  - 2.2 原始 CSV → NPY：`app/desktop/backend_runner.py`（向导路径）
  - 2.3 已落盘数据资产（只读校验）
- 3. 数据质量控制 (QC)
  - 3.1 `analysis/data_QC.py`（1768 行）
    - 3.1.1 模块级常量（默认阈值集中处）
    - 3.1.2 基础 IO / 统计工具函数
    - 3.1.3 `class DataQualityController`（`:371`）
    - 3.1.4 顶层入口与 CLI
  - 3.2 QC 产物 schema
  - 3.3 结果级 QC：`analysis/anomaly_treatment.py` + `analysis/data/validation.py`
    - 3.3.1 `analysis/anomaly_treatment.py`（489 行）
    - 3.3.2 `analysis/data/validation.py`（63 行）
  - 3.4 QC → 用户决策 边界
- 4. 数据映射与预处理
  - 4.1 序列编码
  - 4.2 表观/环境通道编码
  - 4.3 去重 / 缺失 / 掩码 / 标准化
- 5. 特征工程
  - 5.1 `core/features/engineering/feature_engineering.py` 函数级清单
    - 配置加载与校验
    - 编码
    - schema 与命名
    - 读入、清洗与变换
    - 落盘
    - 编排与 CLI
  - 5.2 schema 与 shape 变化（真实数字）
  - 5.3 特征命名/顺序
- 6. 数据划分与数据集构建
  - 6.1 single / all / mixed 语义
  - 6.2 train/valid/test 比例、seed、LOCO
  - 6.3 每实验目录产物
  - 6.4 数据流总览
  - 6.5 与文档/注释不一致之处
  - 本节自检
- **模型训练与 XAI（§7–§10）**
- 7. 模型训练
  - 7.1 训练总入口 workflows/training/train.py (CLI→流程)
    - 7.1.1 顶部常量
    - 7.1.2 CLI 参数表（`parse_args`, workflows/training/train.py:599-644）
    - 7.1.3 主流程（`run_one_experiment`, workflows/training/train.py:441-592）
    - 7.1.4 scaler 的 fit-on-train 证据（workflows/training/train.py 只传标志，不拟合）
    - 7.1.5 目录与 run_name 约定
  - 7.2 五模型并行/分发机制
    - 7.2.1 模型名 → 模块映射（唯一权威表）
    - 7.2.2 workflows/training/data_digging.py（Training Scope 网格）→ 子进程调用 workflows/training/train.py
    - 7.2.3 workflows/prediction/predict.py（Ultimate mixed 十折）**不调用 workflows/training/train.py**
    - 7.2.4 GUI/后端（app/backend/crispr_workspace/training.py）
  - 7.3 Linear Regression（core/models/linear/linear_regression.py，852 行）
    - class `LinearRegressionModel` (linear_regression.py:56)
    - 模块级函数
    - 输入/输出/训练流程（`train`, linear_regression.py:673-816）
  - 7.4 XGBoost（core/models/xgboost/xgboost.py，694 行）
    - 默认超参 `DEFAULT_PARAMS` (xgboost.py:37-48)
    - class `XGBoostModel` (xgboost.py:145)
    - XAI 导出 `get_feature_importance` (xgboost.py:296-371)
    - 训练流程（`train`, xgboost.py:509-659）
  - 7.5 MLP（core/models/mlp/mlp.py，801 行）
    - 架构 `MLPModel` (mlp.py:95-127)
    - XAI 辅助函数
    - 训练循环（`train`, mlp.py:481-765）
  - 7.6 CNN（core/models/cnn/cnn.py，873 行）
    - 架构 `CNNModel` (cnn.py:89-199) —— 双分支，逐层精确参数
    - kernel 变体 cnn33 / cnn53 / cnn73
    - 通道切分（train, cnn.py:563-637）
    - 训练循环（cnn.py:689-745）
    - XAI：ISM 与 3D-IG
  - 7.7 Transformer（core/models/transformer/transformer.py，805 行）
    - 结构（精确维度）
    - 训练循环（transformer.py:627-683）
    - 注意力与熵
  - 7.8 每实验 Artifact 表
- 8. XAI / Feature Attribution
  - 8.1 实现清单核对表
  - 8.2 各方法函数级说明
    - `get_feature_importance(model, feature_names, X_eval, y_eval, random_seed=42)` — xgboost.py:296
    - `compute_integrated_gradients(model, X, device, steps=30)` — mlp.py:212
    - `compute_mlp_robustness_importance(model, X_eval, feature_names, device)` — mlp.py:274
    - `compute_cnn_ism(model, X, device)` — cnn.py:284
    - `compute_cnn_integrated_gradients(model, X, device, steps=25)` — cnn.py:314
    - `compute_transformer_attention_robustness(model, X, device)` — transformer.py:289
    - `compute_transformer_integrated_gradients(..., steps=20)` — transformer.py:321
    - `export_feature_table(model_key, df, rename=None, drop=None, origin="")` — xai_importance.py:76
  - 8.3 SNR 定义（精确公式）与阈值使用位置
  - 8.4 白名单列（`WHITELIST_COLUMNS`, core/xai/importance/xai_importance.py:29-36）
- 9. 训练输出与实验目录结构
- 10. 与 README/注释不一致之处
  - 本节自检
- **结果收集与 Analyse 分析引擎（§11–§14）**
- 11. 实验结果收集与汇总 (legacy scripts; each with 状态/职责/输入/输出/函数清单)
  - 11.1 analysis/collect_results.py (441 行) — 指标汇总表生成
    - 实验发现与解析规则
    - 排序 / 过滤 / ΔR²
    - 函数清单
    - CLI 与产出定位
  - 11.2 analysis/importance_extraction.py (908 行) — 特征重要性抽取与白名单报告
    - 常量与白名单（XAI 学术红线）
    - 函数清单
  - 11.3 analysis/visualization.py (959 行) — V6 显著性掩码热图 / 环境增量树 / 表观对比
    - 关键函数
  - 11.4 analysis/anomaly_treatment.py (489 行) — 两级异常检测报告
    - 函数清单
    - 函数与规则
- 12. Analyse 证据分析引擎
  - 12.1 总览与运行入口
  - 12.2 配置与阈值（`analysis/config.py`，全部默认值）
  - 12.3 schemas 与 Evidence 标签（`analysis/schemas.py`）
    - 标签 → 生产使用映射（grep 实证）
  - 12.4 plans / registry / capabilities
  - 12.5 pipeline 逐阶段
  - 12.6 data 层
    - `analysis/data/loaders.py`
    - `analysis/data/validation.py`
  - 12.7 statistics
  - 12.8 environment 增量与主效应（`analysis/environment/incremental_effect.py`）
  - 12.9 attribution 抽取
    - 列适配 `analysis/attribution/columns.py`
    - 行抽取 `analysis/attribution/extractors.py`
  - 12.10 cell-line 一致性
  - 12.11 evidence 整合
    - `analysis/evidence/rules.py`（标签规则，阈值全部来自 config）
    - `analysis/evidence/integration.py`（证据矩阵）
    - `analysis/evidence/hypothesis.py`（受控语言）
  - 12.12 reports & visualization
    - `analysis/reports/markdown_report.py`（builder → 文件）
    - `analysis/visualization/`（新包，`render_all`）
  - 12.13 产物 schema（实跑 `results/batches/batch_20260909_full/summary/`）
    - 目录
    - summary/*.md（编号 = 分析阶段）
    - tables/*.csv（列名 = 实测首行）
    - figures/*.png（实跑 15 张，`execution_log.figures` 全量列出）
    - JSON 元数据
    - 只读核验命令（本文档所用，均不写仓库）
  - 产物清单与规模
  - 不稳定隔离与字段语义
  - 测试规模与死码审计
- 13. 测试体系（`analysis/tests/`，unittest，无 pytest 依赖）
- 14. 与文档/注释不一致或未实现项
  - 本节自检
- **运行器 / Wizard / Workflow / 前端 / Runtime（§15–§23）**
- 15. 实验运行器 (workflows/prediction/predict.py / workflows/training/data_digging.py: 职责边界, CLI 参数表, 调用链)
  - 15.1 职责边界 (由代码 docstring 与 main() 实证)
  - 15.2 workflows/prediction/predict.py CLI 参数表 (`parse_args`, workflows/prediction/predict.py:723-754)
  - 15.3 通道规划与目标特征 (Target Epigenetics)
  - 15.4 Ultimate 模型与网格
  - 15.5 RESUME 机制 (workflows/prediction/predict.py)
  - 15.6 输出 `赛道二_results.csv`
  - 15.7 workflows/training/data_digging.py CLI 参数表 (`parse_args`, workflows/training/data_digging.py:384-433)
  - 15.8 网格实验引擎 (workflows/training/data_digging.py)
- 16. Wizard / Workflow (main_wizard 7 步 form_data 字段表; backend_runner 步骤 1–7 调用链; 条件分支; 自动 vs 用户决策)
  - 16.1 Wizard 骨架
  - 16.2 7 步与 form_data 字段表
  - 16.3 表观级联逻辑 (`_update_epigenetic_cascade_linkage`, `:443-460`)
  - 16.4 校验 (自动) vs 用户决策
  - 16.5 backend_runner.execute_full_pipeline 步骤 1–7 (`app/desktop/backend_runner.py:144-306`)
- 17. Local Workflow API (app/backend/crispr_workspace 逐文件函数级; 完整 API 表)
  - 17.1 config.py (48 行)
  - 17.2 store.py (41 行)
  - 17.3 fingerprint.py (61 行)
  - 17.4 project.py (136 行) — `project_manifest.json` 为状态源
  - 17.5 qc_service.py (141 行)
  - 17.6 training.py (494 行) — TrainingConfig / Preflight / Runtime Adapter
    - TrainingConfig 字段 (`@dataclass`, `:37-187`) 与 CLI 映射
    - LocalRuntime (`:235-357`)
    - HpcRuntime (`:360-437`)
  - 17.7 analysis.py (256 行)
  - 17.8 artifacts.py (158 行)
  - 17.9 server.py (279 行) — 完整 API 表
- 18. Frontend (页面树/组件树; 每组件职责与所用 API; Artifact Viewer 行为; Notebook 依赖门禁; vitest)
  - 18.1 页面树 / 组件树
  - 18.2 各组件职责与所用 API
  - 18.3 Artifact Viewer 行为 (端到端)
  - 18.4 Notebook 依赖门禁
  - 18.5 vitest 测试
- 19. Runtime / HPC (LocalRuntime vs HpcRuntime 状态机; 命令生成; 日志/状态文件位置; Slurm 边界)
  - 19.1 状态机 (字段来源: `training_status.json`)
  - 19.2 命令生成
  - 19.3 日志/状态文件位置 (workspace 根 = `$CRISPR_WORKSPACE_ROOT` 或 `<repo>/workspace`, `config.py:14-19`)
  - 19.4 Slurm / HPC 边界 (代码做了什么 / 没做什么)
- 20. 配置文件与状态文件体系
- 21. 跨模块接口
- 22. 运行入口清单
- 23. 与文档/注释不一致或未实现项
  - 本节自检
- **模块调用关系 / 历史残留 / 总结 / 论文映射（§24–§27）**
- 24. 模块调用关系（import 依赖 vs 运行顺序）
  - 24.1 运行顺序主链（call chain，实测）
  - 24.2 import 依赖（静态，节选）
  - 24.3 静态“无项目内 import”但 Active 的模块（实测）
- 25. 历史代码 / 残留代码 / 未实现项
  - 25.1 文件级状态（依据引用实测；完整 77 行见附录 A）
  - 25.2 函数级残留（示例）
  - 25.3 重复实现风险（跨文件同名函数，AST 实测）
- 26. 当前项目完整执行流程总结（一页版）
- 27. 与论文方法部分对应的技术模块
  - 1.5 关键实现事实（极易误解，写论文/复现时必须按此）
- 附：文档自检（本主文档部分）
- **附录：程序索引与函数清单（自动生成）**
- 附录（自动生成索引）
  - 附录 A：程序索引（按目录）
  - 附录 B：函数清单（按程序）
    - workflows/training/data_digging.py  (518 lines, Active)
    - workflows/prediction/predict.py  (1008 lines, Active)
    - workflows/training/train.py  (734 lines, Active)
    - app/desktop/backend_runner.py  (306 lines, Active)
    - app/desktop/main_wizard.py  (536 lines, Active)
    - analysis/anomaly_treatment.py  (489 lines, Active)
    - analysis/collect_results.py  (442 lines, Active)
    - analysis/config.py  (65 lines, Active)
    - analysis/data_QC.py  (1768 lines, Active)
    - analysis/importance_extraction.py  (908 lines, Active)
    - analysis/pipeline.py  (345 lines, Active)
    - analysis/plans.py  (242 lines, Active)
    - analysis/prediction.py  (35 lines, Active)
    - analysis/registry.py  (77 lines, Active)
    - analysis/visualization.py  (959 lines, Active)
    - core/features/engineering/feature_engineering.py  (2029 lines, Active)
    - core/xai/importance/xai_importance.py  (135 lines, Active)
    - analysis/attribution/columns.py  (61 lines, Active)
    - analysis/attribution/extractors.py  (139 lines, Active)
    - analysis/attribution/summary.py  (50 lines, Active)
    - analysis/cellline/consistency.py  (60 lines, Active)
    - analysis/data/loaders.py  (173 lines, Active)
    - analysis/data/validation.py  (63 lines, Active)
    - analysis/environment/incremental_effect.py  (170 lines, Active)
    - analysis/evidence/hypothesis.py  (74 lines, Active)
    - analysis/evidence/integration.py  (194 lines, Active)
    - analysis/evidence/rules.py  (73 lines, Active)
    - analysis/reports/markdown_report.py  (180 lines, Active)
    - analysis/stats/bootstrap.py  (107 lines, Active)
    - analysis/stats/effect_size.py  (32 lines, Active)
    - analysis/stats/hypothesis_tests.py  (76 lines, Active)
    - analysis/stats/multiple_testing.py  (35 lines, Active)
    - analysis/tests/test_attribution.py  (78 lines, Test-only)
    - analysis/tests/test_core.py  (201 lines, Test-only)
    - analysis/tests/test_environment.py  (70 lines, Test-only)
    - analysis/tests/test_phase5.py  (63 lines, Test-only)
    - analysis/tests/test_phase6.py  (110 lines, Test-only)
    - analysis/visualization/__init__.py  (84 lines, Active)
    - analysis/visualization/attribution_plots.py  (38 lines, Active)
    - analysis/visualization/cellline_plots.py  (41 lines, Active)
    - analysis/visualization/core.py  (21 lines, Active)
    - analysis/visualization/environment_plots.py  (43 lines, Active)
    - analysis/visualization/evidence_plots.py  (36 lines, Active)
    - analysis/visualization/performance_plots.py  (35 lines, Active)
    - app/backend/crispr_workspace/analysis.py  (256 lines, Active)
    - app/backend/crispr_workspace/artifacts.py  (158 lines, Active)
    - app/backend/crispr_workspace/config.py  (48 lines, Active)
    - app/backend/crispr_workspace/fingerprint.py  (61 lines, Active)
    - app/backend/crispr_workspace/project.py  (136 lines, Active)
    - app/backend/crispr_workspace/qc_service.py  (141 lines, Active)
    - app/backend/crispr_workspace/server.py  (279 lines, Active)
    - app/backend/crispr_workspace/store.py  (41 lines, Active)
    - app/backend/crispr_workspace/training.py  (494 lines, Active)
    - app/backend/tests/test_e2e_smoke.py  (127 lines, Test-only)
    - app/backend/tests/test_no_training_dependency.py  (42 lines, Test-only)
    - app/backend/tests/test_project_recovery.py  (54 lines, Test-only)
    - app/backend/tests/test_workflow_interfaces.py  (131 lines, Test-only)
    - app/backend/tests/test_workspace.py  (157 lines, Test-only)
    - core/models/cnn/cnn.py  (873 lines, Active)
    - core/features/channels/cell_environment_combination.py  (1908 lines, Active)
    - core/data/splitting/cell_line_division.py  (334 lines, Active)
    - core/models/linear/linear_regression.py  (852 lines, Active)
    - core/models/mlp/mlp.py  (801 lines, Active)
    - core/models/transformer/transformer.py  (805 lines, Active)
    - core/models/xgboost/xgboost.py  (694 lines, Active)

---

> 本文档由对当前代码库的**只读逆向梳理**生成。所有事实以仓库中的实际代码为准；
> 文档/注释与代码不一致处均已单独标注（见 §0.5、§25、各章节末“不一致”小节）。

# 0. 文档说明

## 0.1 文档目的
把项目从“原始数据进入”到“特征工程 → 训练 → XAI → 结果汇总 → 分析 → 证据整合 → 报告 → Workflow/前端”的**真实实现**记录为单一技术地图，用于论文 Methods/Supplementary、技术报告、答辩、复现与后续工程开发。

## 0.2 分析范围
- Python：77 个文件，21,840 行（不含 `.venv/`、`node_modules/`、`_no_upload/`、`workspace/`、`results/` 数据）。
- 前端：`app/frontend/src/` 32 个 `.ts/.tsx` 文件 + `package.json`/`vite.config.ts`。
- 脚本：`app/scripts/run_workspace.sh`、`deploy/hpc/build_upload.sh`；配置：`data/metadata/feature_config.json`、`data/processed/feature_schema.json`。
- HPC 文档：`HPC_ENVIRONMENT.md`、`HPC_EXPERIMENT_PROTOCOL.md`、`PERF_REPORT.md`。

## 0.3 代码基线（快照）
| 项 | 值 |
|---|---|
| 工作目录 | `/home/zhang/bioprogram/Submit` |
| Git 仓库根 | `/home/zhang/bioprogram`（Submit 为仓库子目录；`git rev-parse --show-toplevel` 实测） |
| Git commit | `9b2def2b`（“第一次提交”） |
| Git branch | `main` |
| 工作区状态 | **大量未提交改动**：886 项删除(D)、348 项未跟踪(??)、8 项 MM、7 项 M、3 项 MD、2 项 AM（`git status --short` 全仓统计） |

`git status --short` 实测要点（节选）：
```text
 M README.md
MM analysis/collect_results.py
MD analysis/visualize_results.py          # 工作区已删除该文件
AM data/metadata/feature_config.json
AM data/processed/feature_schema.json
 D data/processed/*_161.* / *_23x7.*   # 旧 7 通道产物被删除
 D logs/batch_20260818_clean/**            # 旧日志被删除
 D models/batch_20260818_clean/**          # 旧模型文件被删除
 D delete.py
```
**重要基线事实**：Submit 目录内共 **53 项未跟踪**，其中 **15 个 `.py`/`.ts`/`.tsx` 核心代码文件未纳入 git**
（例如 `workflows/training/train.py`、`workflows/training/data_digging.py`、`analysis/` 新引擎多数文件、`core/xai/importance/xai_importance.py`、`app/scripts/run_workspace.sh` 等，见 `git status --short -- . | grep '^??'`）。
因此：**当前代码库没有对应这些实现的提交版本**，本快照的复现基线应以工作区文件为准（而非 commit `9b2def2b`）。
> 另：`analysis/visualize_results.py` 在工作区已不存在（`ls` 实测缺失）；`analysis/visualization.py` 才是现存的旧单文件可视化脚本。

## 0.4 方法与判据
- 以 AST 扫描 + 人工阅读函数体的方式建立程序/函数索引；索引见附录 A/B。
- “调用关系”分为两类并分别标注：**import 依赖**（静态）与**运行顺序**（实际函数调用/子进程调用）。
- 程序状态取值：`Active` / `Legacy` / `Unused` / `Planned(未实现)` / `Uncertain`；判定依据为其被引用的实际情况。
- 无法从代码确定的内容一律写“无法从当前代码确定”。

## 0.5 文档与代码不一致的总体清单（先总后分）
1. `README.md` 曾引用 `notebooks/01_pipeline_demo.ipynb`，但仓库中**不存在 `notebooks/` 目录**；该 notebook 由 `scripts/make_notebook.py` 生成（脚本在，产物不在）。
2. `README.md` 曾写 `visualize_variant_importance.py`，实际文件为 `analysis/visualization.py`（已修正）。
3. `analysis/visualization.py`（旧单文件）与 `analysis/visualization/`（新包）**同名冲突**：包优先；包内 `__init__.py` 用 PEP 562 `__getattr__` 惰性桥接旧模块的 `generate_all_visualizations`，`app/desktop/backend_runner.py` Step6 因此仍可用。
4. `workflows/prediction/predict.py` 中 `train_ultimate_models()` 与 `generate_track2_results_ultimate()` 仍存在但 **`main()` 已不再调用**（被 `run_ultimate_with_resume()` 取代），属 Unused。
5. `analysis/registry.py` 登记的部分任务（motif discovery 等）在 `analysis/pipeline.py` 中状态为 `unavailable`（未实现，附 reason），属 Planned。
6. `stats/hypothesis_tests.anova_interface` 为占位（`available=False`），不是已实现 ANOVA。
7. `workspace/` 目录为运行期默认工作根（可能为空），不属于代码。
8. **接口不一致（实测）**：`analysis/registry.py` 的任务规格字段是 `name`（无 `display`），而
   `app/backend/crispr_workspace/analysis.py::registry_tasks()` 读取的是 `display` → 未命中时回退为 `task_id`，
   因此前端任务列表显示的是 task id 而非人类可读名称。
9. **前端分组不一致（实测）**：`app/frontend/src/components/AnalysisPanel.tsx` 按 `core/advanced` 两组过滤，
   而 registry/后端给出的 `category` 取值是 `qc/biology/statistics/evidence` → 该面板当前会把所有任务过滤为空
   （需在后续工程修复；本次仅记录）。
10. `analysis/registry.py` 中所有内置任务的 `runner=None`：**runner 未通过 registry 注册**，
    实际阶段实现直接写在 `analysis/pipeline.py` 的 `run_analysis()` 中（registry 目前仅作任务目录/UI 来源）。
11. `scripts/make_notebook.py`（生成 `notebooks/01_pipeline_demo.ipynb`）内部**自相矛盾**：
    第 19 行 markdown 仍写 `(N, 23, 7)`，第 89 行代码却构造 `np.zeros((n_demo, 23, 8))`，
    第 215–218 行又把 161 维线性权重 `reshape(23, 7).T`（161 = 23×7 是“剔除 `_T` 后”的列数，不是通道数）。
    属遗留 demo 视图，未随 8 通道改造同步（代码实测行号如上）。
12. `create_channel_mask` docstring 的示例掩码为 7 通道形态（`[1,1,1,0,0,0,0]`），当前 schema 为 8 通道；
    代码按 schema 动态生成，注释过期（见 §1.5 第 6 条）。

---

# 1. 项目总体流程

## 1.1 总流程图（真实实现的三种主要入口）
```text
入口 A：7 步 GUI 向导 (app/desktop/main_wizard.py → app/desktop/backend_runner.py)
入口 B：Scientific Workspace (app/scripts/run_workspace.sh → app/backend/crispr_workspace/server.py + app/frontend/)
入口 C：各阶段独立 CLI (workflows/training/data_digging.py / workflows/prediction/predict.py / analyse.pipeline / data_QC.py / analysis/*.py)

入口 A 的执行顺序（execute_full_pipeline 实测顺序）:
[Step1] 特征工程 (run_feature_engineering_step / convert_raw_csv_to_npy)
   ↓
[Step2a] 网格挖掘 workflows/training/data_digging.py（Training Scope 环境组合 × 模型）→ 每实验子进程 workflows/training/train.py
   ↓
[Step2b] 条件分支：仅当 has_target（勾选目标基因组）→ workflows/prediction/predict.py（mixed 十折 CV + 目标预测）
   ↓
[Step3] analysis/collect_results.py（→ summary/metrics_tables/）
   ↓
[Step4] analysis/anomaly_treatment.py（→ summary/anomaly_report.md）
   ↓
[Step5] analysis/importance_extraction.py（→ summary/feature_importance/ + key_regulatory_biomarkers.csv）
   ↓
[Step6] analysis/visualization.py::generate_all_visualizations（经同名包兼容桥）→ summary/plots/
   ↓
[Step7] 交付物核对（会话/候选表/ultimate/特征库/指标表/重要性/图）

单实验内部（workflows/training/train.py）:
特征加载 → divide_data(single|all|mixed) → prepare_train_valid_test(环境组合掩码)
 → 按模型分发 train_function → 训练/验证/早停/测试 → 指标+XAI → 写 {model}_*.json/csv/txt + 模型文件
```

## 1.2 分析引擎（analyse）的执行顺序
`python -m analysis.pipeline --batch-dir <batch> --output <out>`（`analysis/pipeline.py::run_analysis`）按注册任务逐段执行：
```text
qc → prediction → environment_conditional_effect → environment_main_effect
   → sequence_attribution（含 cnn_ism 判定）→ cellline_heterogeneity
   → evidence_integration → hypothesis_generation
   → 最后 render_all() 渲染 figures/（失败不阻断已完成的科学计算）
产物：tables/*.csv、summary/00..08.md、figures/02..06/*.png、
      analysis_plan.json、analysis_status.json、execution_log.json
未实现/数据不足的任务写入 status=unavailable + reason（绝不伪造）：
      motif_discovery、bootstrap、hypothesis_testing、fdr_correction 等
```

## 1.3 条件分支与并行机制（代码事实）
| 条件 | 行为 | 位置 |
|---|---|---|
| GUI 勾选“候选设计/目标基因组” | 追加 `workflows/prediction/predict.py --target-input ... --target-epigenetics ...` | `app/desktop/backend_runner.py` Step2b |
| 环境组合 = 4 个表观全部 | 归一化为单一 `all`（丢弃显式四元名，避免 17 组合→1428 实验） | `workflows/training/data_digging.py::_canonicalize_combinations` |
| 用户选择 models/cell-lines/split-types | 决定 `generate_experiments` 笛卡尔积 | `workflows/training/data_digging.py::generate_experiments` |
| `--in-process` | 复用解释器顺序执行（避免每实验 python 启动开销） | `workflows/training/data_digging.py::run_experiment_in_process` |
| `--workers>1` | 实验级并发（每个实验仍是相同 workflows/training/train.py 子进程） | `workflows/training/data_digging.py::build_worker_env/run_one_experiment` |
| `--threads-per-worker>0` | 并发时限制 OMP/MKL 线程（**会改变浮点求和顺序**，默认关闭） | 同上（代码注释明确标注风险） |
| predict 断点续跑 | `ultimate/progress.json` + `preds_<kind>.npy` 完成标记，存在则跳过该模型 | `workflows/prediction/predict.py::run_ultimate_with_resume/_kind_done` |
| data_digging 断点续跑 | 扫描 results/[batch]/ 实验目录 info 判定 completed（**不看 batch 中“有目录”即完成**，只有 info/metrics 齐全才算） | `workflows/training/data_digging.py::build_completed_lookup/classify_experiments` |
| 分析任务未选中 | status=skipped，不执行 | `analysis/plans.py::validate_analysis_plan` |
| XAI 计算开关 | GUI `xai_vars`（linear/xgb/mlp/cnn/transformer 各自开关）→ 传 workflows/training/train.py `--compute-shap` 等 | `app/desktop/main_wizard.py` Step5 / `workflows/training/train.py` |

并行执行：网格实验按“一个 GPU 一个 `workflows/training/data_digging.py` 进程 + 环境切片”并行（见 `HPC_EXPERIMENT_PROTOCOL.md` §2）；
五类模型在同一进程内按顺序训练（每个实验一个模型），GUI/Workflow 层面可多卡并行。

## 1.4 数据流（形态变化，逐段标注负责程序）
```text
原始 CSV（每细胞系一个文件；列含 sgRNA / Chromosome / Start / End / 表观轨道 / efficacy）
  │  core/features/engineering/feature_engineering.py::load_source_csv（去重 remove_duplicate_rows）
  ▼
DataFrame（N 行；metadata 列 + 目标列）
  │  engineer_dataframe → build_feature_matrix（逐行编码）
  ▼
features_3d (N, 23, C)  +  features_2d (N, 23*C)  +  labels (N,)
  │  save_matrix_csv / save_vector_csv / save_numpy_files / save_feature_schema
  ▼
data/processed/ : {cell}_23x{C}.csv, {cell}_{23*C}.csv,
                       {cell}_features_23x{C}.npy, {cell}_features_{23*C}.npy,
                       {cell}_labels.npy, {cell}_metadata.csv, feature_schema.json
  │  workflows/training/train.py::prepare_split_data → src/input_control/cell_line_division.divide_data
  ▼
X_train_3d / X_valid_3d / X_test_3d （single=按细胞系内部随机划分；all=留一细胞系；mixed=跨细胞系混合+多种子）
  │  workflows/training/train.py::prepare_model_data → cell_environment_combination.prepare_train_valid_test
  ▼
模型输入：表格类 (linear/xgboost/mlp) 用 (N,23*C) 二维；CNN/Transformer 用 (N,23,C) 或通道子集
  │  各模型 train 函数（训练/早停/测试）
  ▼
每实验目录 results/<batch>/<run_name>/：
  {model}_metrics.json、{model}_validation_metrics.json、{model}_info.txt、
  {model}_predictions.csv、{model}_validation_predictions.csv、
  {model}_feature_importance.csv（树/网络类）、linear_regression_weights.csv 等
  │  analysis/collect_results.py::collect_batch
  ▼
summary/metrics_tables/all_experiments.csv（规范列；另出 single/all/mixed 汇总表与 baseline.csv）
  │  analysis/pipeline.py::load_experiment_table（统一表；ids 小写化、metrics 保大写）
  ▼
canonical experiment_table.csv
  │  environment / attribution / cellline / evidence / reports / visualization
  ▼
summary/tables/*.csv + summary/00..08.md + figures/*.png
```
> 关键 shape 事实（来自 `data/processed/feature_schema.json` 与 FE 代码）：
> `sequence_length = 23`；`sequence_channels = [A, C, G, T]`；4 个表观通道 `[CTCF, Dnase, H3K4me3, RRBS]`；
> `channel_count = 8`；`feature_count = 23 × 8 = 184`；列名模式 `pos{p}_{channel}`。

---


---

# 2. 数据输入

> **本节范围**：数据输入形态、原始 CSV → 特征张量转换、数据质量控制 (QC)、数据映射与预处理、特征工程、数据集划分与产物。
> **证据规则**：本文所有事实均来自对仓库源码与已落盘产物的直接阅读/只读校验，不采信 README 与模块 docstring 的自我声明；docstring 与实际代码冲突处一律在 §6.5 显式列出。
> **只读声明**：本节编写过程未修改仓库内任何文件；仅以只读方式 `np.load(..., mmap_mode="r")` / `pd.read_csv(nrows=...)` 校验了 `data/processed/` 的真实 shape。
> **代码标识符**保留英文原文；`path:line` 指该事实所在行。

## 2.1 输入形态与入口

### 2.1.1 三个入口，职责不同

| 入口 | 文件 | 触发方式 | Status | 证据 |
| :--- | :--- | :--- | :--- | :--- |
| ① 7 步 Tk 向导 | `app/desktop/main_wizard.py` → `app/desktop/backend_runner.py` | `_launch_pipeline` → `execute_full_pipeline` | **Active** | `app/desktop/backend_runner.py:144` 被 `main_wizard` 的启动回调调用 |
| ② 特征工程 CLI | `core/features/engineering/feature_engineering.py` | `python core/features/engineering/feature_engineering.py --source-dir … --output-dir … --config …` | **Active（数据实际来源，但运行时不被调用）** | 见 §2.3 判定证据 |
| ③ Workspace HTTP 后端 | `app/backend/crispr_workspace/server.py` + `qc_service.py` | `POST /api/qc/sessions` | **Active** | `server.py:92-99`；QC 引擎以子进程调用 |

**关键事实：向导第 2 步不是 QC。** `app/desktop/main_wizard.py:146` 的第 2 步标题是「选择已测量数据与待预测基因组」，全文件不含 `data_QC` / `qc` 字样（grep 无命中）。`analysis/data_QC.py:5` 声称「供 7 步交互式向导 (GUI/CLI) 第二步调用」——当前仓库不存在这条调用链，真实集成方是后端 `qc_service.QCSessionManager._launch`（`app/backend/crispr_workspace/qc_service.py:116-133`）。

### 2.1.2 原始 CSV 的真实列结构

真实表头（`data/raw/*.csv`，4 个细胞系一致）：

```
Chromosome,Start,End,Strand,sgRNA,CTCF,Dnase,H3K4me3,RRBS,Normalized efficacy
chr1,19513973,19513995,+,ACGTTAGCAGTTTGATGGCATGG,AAAA…(23),AAAA…NNNN(23),AAAA…(23),NNNN…(23),0.15850929346693232
```

- 目标列名固定为 `Normalized efficacy`（`core/features/engineering/feature_engineering.py:134` `TARGET_COLUMN`）。
- 元数据列固定 6 个（`core/features/engineering/feature_engineering.py:136-143` `METADATA_COLUMNS`）：`Cell line`（处理时由代码 `df.insert(0, "Cell line", cell_line)` 注入，`core/features/engineering/feature_engineering.py:1229-1233`）、`Chromosome`、`Start`、`End`、`Strand`、`sgRNA`。
- 4 条环境轨道为 23 字符的 `A`/`N` 串（不是数值）；`A` 表示该位点有注释、`N` 表示无注释。
- `data/candidate/todo_data.CSV` 是另一种形态（仅 `sgRNA,Efficacy` 两列，无坐标、无环境轨道），**不满足** `get_required_columns()` 的必需列要求（`core/features/engineering/feature_engineering.py:1030-1060`），无法直接进入本流水线；仓库内除文件本身外无任何代码引用它。
- 向导默认列名（`app/desktop/main_wizard.py:30-38`）：`seq_col="sgRNA"`、`target_col="Normalized efficacy"`、`epi_cols_raw="CTCF, Dnase, H3K4me3, RRBS"`、`chrom_col="Chromosome"`、`start_col="Start"`、`end_col="End"`、`seq_len=23`。

### 2.1.3 列自动识别与编码自适应（QC 侧）

`analysis/data_QC.py` 不要求用户显式给列名，使用三级别名匹配：

- `SEQ_COL_ALIASES`（`:62-65`）：`sgRNA / sgRNA sequence / Sequence / sequence / seq / Guide / GuideSeq / guide_seq / protospacer / 23nt / target_site / spacer`。
- `TARGET_COL_ALIASES`（`:70-74`）：`Normalized efficacy / Efficiency / Editing efficiency / normalized_efficacy / label / target / Activity / y / Y`。
- `CELL_LINE_COL_ALIASES`（`:66-69`）。
- `EPI_NAME_MAP`（`:77-89`）把小写关键字映射为规范显示名：`ctcf→CTCF`、`dnase/dhs→Dnase`、`h3k4me3/h3k4→H3K4me3`、`h3k27ac→H3K27ac`、`rrbs/methylation/bisulfite→RRBS`、`atac→ATAC`；含 `sequence/feature/coverage/score_norm` 的列名被忽略（`_EPI_IGNORE_WORDS`，`:89`）。
- 匹配规则（`_detect_epigenetic_columns`，`:137-150`）：列名**精确等于**关键字，或以 `关键字_` 开头，或以 `_关键字` 结尾；每个规范名只保留首个命中列。
- 序列列用 `_find_column_fuzzy`（`:124-134`，先精确后子串双向包含），目标列/细胞系列用 `_find_column`（`:114-121`，仅精确+忽略大小写）。
- 读取编码：`_read_table`（`:100-111`）按 `.tsv/.txt→\t`、其余 `,` 分隔，依次尝试 `utf-8 → gb18030 → latin-1`；解析失败不再换编码重试，直接 `ValueError`。

## 2.2 原始 CSV → NPY：`app/desktop/backend_runner.py`（向导路径）

**Status: Active**（`execute_full_pipeline` 第 1/7 步，`app/desktop/backend_runner.py:177-182`）。

- `build_active_environment_combinations(active_epis: List[str]) -> List[str]`（`:23-37`）：由勾选表观项展开组合名，规则为 `["sequence"] + 所有非空子集的 "sequence_" + "_".join(sorted(subset))`；仅当集合恰为 `{ctcf,dnase,h3k4me3,rrbs}` 时追加 `"all"`。**注意**：这里生成的子集名已按字母排序（如 `sequence_ctcf_dnase`），与 `src/input_control/cell_environment_combination.make_combination_name_from_environments` 的排序规则一致。

- `convert_raw_csv_to_npy(csv_path, cell_line, output_dir, form_data)`（`:40-91`）：**向导路径真正的编码器**，与 `core/features/engineering/feature_engineering.py` 是两套独立实现。
  1. 列名解析：`form_data["seq_col"]` / `["target_col"]`；若不在 columns 中，则按列名含 `sgrna|seq`、含 `effic|label|target` 兜底（`:48-56`）。
  2. 固定分配 `X_3d = np.zeros((n_samples, 23, 8), dtype=np.float32)`（`:60`）——**23 与 8 为硬编码字面量**，与向导 `seq_len` 变量无关。
  3. 序列通道索引硬编码 `{'A':0,'C':1,'G':2,'T':3}`（`:61`）；序列串 `upper().strip()` 后 `ljust(23,'N')[:23]`（`:65`）——**短序列右侧补 `N`、长序列直接截断**；非 ACGT 字符不置位，形成「全零列」而非报错（`:66-69`）。
  4. 表观列按 `{'ctcf':4,'dnase':5,'h3k4me3':6,'rrbs':7}` 顺序（`:71`）在 `df.columns` 中做**子串匹配**（`if epi_k in c.lower()`，`:74-75`）。取值规则（`:78-82`）：字符串长度恰为 23 时逐位 `'1','A','Y','T' → 1.0`，其余 `→ 0.0`；`int/float/np.number` 时**整条通道广播为该标量**；其他情况（含字符串长度≠23）静默保持 0。
  5. `X_2d = X_3d.reshape(n_samples, -1)`（`:84`）→ `(N,184)`。
  6. 标签：`df[target_col].to_numpy(float32)`；**若目标列不存在，则生成 `np.random.uniform(0.5,0.9,n)` 随机标签**（`:85`，仅打印成功信息，不告警）。
  7. 落盘 4 个文件：`{cl}_features_23x8.npy`、`{cl}_features_184.npy`、`{cl}_labels.npy`、`{cl}_metadata.csv`（`:87-90`）。其中 metadata 是**原始 df 全列原样落盘**（不是 `METADATA_COLUMNS` 子集）。

- `run_feature_engineering_step(form_data, raw_data_dir, output_data_dir, target_cell_lines)`（`:94-141`）：
  - 先把仓库基准 `data/processed/*.*` 中「目标目录尚不存在」的文件拷入输出目录（`:100-105`）；
  - 写出 `feature_schema.json`，其 `channel_names` 硬编码为 `["A","C","G","T","CTCF","Dnase","H3K4me3","RRBS"]`，`sequence_length = form_data["seq_len"]`，`feature_count = seq_len * 8`（`:107-117`）——**若用户把 `seq_len` 改成非 23，schema 与实际 `(N,23,8)` 张量将不一致**；
  - 逐细胞系：已有 `{cl}_features_23x8.npy` 则跳过；否则优先从基准目录拷贝同名前缀文件，再从传入 CSV（文件本身或目录内 `*{cl}*.csv` 或任意 `*.csv`）调用 `convert_raw_csv_to_npy`（`:127-139`）。

- `execute_full_pipeline(form_data, root_output_dir)`（`:144-306`）：7 步编排（特征工程 → `workflows/training/data_digging.py` → 可选 `workflows/prediction/predict.py` → `collect_results.py` → `anomaly_treatment.py` → `importance_extraction.py` → `visualization.generate_all_visualizations`），每步以 `subprocess.run` 调用，返回码非 0 仅打印 `[Warning]` 不中断（`:206-207`、`:240-241`）。

## 2.3 已落盘数据资产（只读校验）

`data/processed/` 真实内容（`np.load(mmap_mode="r")` + 行数统计）：

| cell line | `*_features_23x8.npy` | `*_features_184.npy` | `*_labels.npy` | `*_metadata.csv` 行数 | dtype |
| :--- | :--- | :--- | :--- | ---: | :--- |
| hct116 | `(4239, 23, 8)` | `(4239, 184)` | `(4239,)` | 4239 | float32 |
| hek293t | `(2333, 23, 8)` | `(2333, 184)` | `(2333,)` | 2333 | float32 |
| hela | `(8101, 23, 8)` | `(8101, 184)` | `(8101,)` | 8101 | float32 |
| hl60 | `(2076, 23, 8)` | `(2076, 184)` | `(2076,)` | 2076 | float32 |

`*_metadata.csv` 列（实测）：`Cell line, Chromosome, Start, End, Strand, sgRNA, Normalized efficacy`。
`data/processed/feature_engineering_summary.csv` 实测内容：

```
cell_line,original_samples,duplicate_rows,final_samples,channel_count,feature_count
hct116,4239,0,4239,8,184
hek293t,4566,2233,2333,8,184
hela,8101,0,8101,8,184
hl60,2076,0,2076,8,184
```

**来源判定**：该 summary 文件的列名恰为 `process_one_csv` 的返回字典键（`core/features/engineering/feature_engineering.py:1739-1757`）且只由 `process_all_csv` 写出（`:1899-1911`）；`app/desktop/backend_runner.py` 不生成该文件。因此仓库内 `proceeded_data/*.npy` 是 **`core/features/engineering/feature_engineering.py` CLI 的产物**，而运行时向导走的是 `backend_runner.convert_raw_csv_to_npy`。两者产物命名相同、语义有差异（见 §6.5）。

---

# 3. 数据质量控制 (QC)

## 3.1 `analysis/data_QC.py`（1768 行）

**Status: Active**——被 `app/backend/crispr_workspace/qc_service.py:24`（`ENGINE = Path("analyse")/"data_QC.py"`）以子进程调用（`--output-dir <session> --data <inputs[0]>`），前端 `app/frontend/src/components/QcDashboard.tsx` 只读渲染其 `qc_summary.json`。**全模块只读：无任何 `to_csv` 写回原始数据、无 `drop`/`replace`/`fillna` 落盘，唯一写出的表格是独立命名的 `outliers_detailed_report.csv`。**

### 3.1.1 模块级常量（默认阈值集中处）

| 常量 | 值 | 行 |
| :--- | :--- | ---: |
| `DEFAULT_OUTPUT_DIR` | `"data/data_report"` | `:54` |
| `STANDARD_BASES` | `("A","C","G","T")` | `:55` |
| `DEFAULT_POSITION_LENGTH` | `23` | `:56` |
| `DEFAULT_CV_FOLDS` | `5` | `:57` |
| `DEFAULT_CV_SUBSAMPLE` | `2000` | `:58` |
| `DEFAULT_CONTAMINATION` | `0.01` | `:59` |
| `DEFAULT_RANDOM_STATE` | `42` | `:60` |
| `TRACK_CHARS` | `frozenset("ACGTNY10.+-")` | `:258` |
| `_POSITIONAL_CORE_NAMES` | `{"CTCF","Dnase","H3K4me3","RRBS"}` | `:259` |
| 70% 门禁常数 | `70.0`（**内联字面量，非命名常量**） | `:1056` |

**注意**：`analysis/config.py:41-47` 另有一份 `QCConfig`（`environment_missing_rate_limit=0.30`、`strict_complete_gate=70.0`、`ambiguous_detection_only=True`），但 `data_QC.py` 的 import 列表中**没有** `analyse.config`（`:27-47`），即这些阈值存在两处定义且未打通（见 §6.5）。

### 3.1.2 基础 IO / 统计工具函数

- `_as_path(path) -> Path`（`:96`）：`Path(path).expanduser()`。
- `_read_table(path) -> (DataFrame, encoding)`（`:100`）：见 §2.1.3。
- `_find_column(columns, aliases) -> Optional[str]`（`:114`）：精确+忽略大小写。
- `_find_column_fuzzy(columns, aliases) -> Optional[str]`（`:124`）：先精确，再双向子串包含。
- `_detect_epigenetic_columns(columns) -> Dict[规范名, 实际列名]`（`:137`）。
- `_cv_bandwidth(values, cv=5, n_subsample=2000, random_state=42, n_grid=24) -> float`（`:157-196`）：**高斯核 KDE 带宽的交叉验证选择，注释明确「严禁经验写死」**。流程：过滤非有限值 → `std = v.std(ddof=0)`；`std<=1e-12` 时退化 `max(1e-6, |mean|*0.5)` → 搜索区间 `[std*0.05, std*1.5]`，在**对数空间**取 `np.geomspace(lo, hi, 24)` → 样本量 > 2000 时用 `default_rng(42)` 无放回子抽样 → `n_folds = min(cv, max(2, min(100, n//2)))` → `GridSearchCV(KernelDensity(kernel="gaussian"), param_grid={"bandwidth": grid}, cv=KFold(shuffle=True, random_state=42), n_jobs=-1)` 取 `best_params_["bandwidth"]`。样本 <3 时返回 `nanstd` 或 `1e-3`；空返回 `1.0`。
- `_kde_values(values, bandwidth, n_points=400, pad=0.15) -> (xs, ys)`（`:199-210`）：在 `[min-0.15*span, max+0.15*span]` 上求 `exp(score_samples)`；<3 个有效值返回空数组。
- `_parse_epi_vector(value, length) -> Optional[ndarray]`（`:213-251`）：**表观值统一的「逐位点向量化」入口**。规则：`None`/`NaN`/空串 → `None`；`"[...]"` JSON 数组长度==length → 原值；长度==length 的字符串 → 逐字符 `ch in ("A","Y","T","1") → 1.0 else 0.0`；长度 1 的单字符（`A/N/0/1/Y/T`）→ 广播为该常数；list/tuple/ndarray 长度==length 或 ==1 同理；其他标量 → `float` 广播；无法解析 → `None`（上层做中位数填充）。
- `_is_blank_value(value) -> bool`（`:262-272`）：`None` / 空白串 / `pd.isna`。
- `_sample_feature_info(value, length) -> Dict`（`:274-321`）：单值类型判别，返回 `kind ∈ {blank, pos, scalar, token}`、`units`（位点数）、`has_nan`、`preview`。判定顺序：空 → `blank`；字符串 `"[...]"` → 尝试 JSON 解析成 `pos`（`NAN/nan` 统一为 `NaN`，`:294`），失败 → `token`；字符串字符集 ⊆ `TRACK_CHARS` 且长度 >1 → `pos`（`units=len`，**含长度异常者，供对齐检测**）；其余字符串 → `token`；array-like → `pos`；数值 → `scalar`；其他 → `token`。
- `_style_figure()`（`:324`）：`sns.set_theme(style="whitegrid", font_scale=1.05)` + DejaVu Sans。
- `_save_figure(fig, path)`（`:330`）：`tight_layout()` → `savefig(dpi=300, bbox_inches="tight")` → `close`。
- `_sequence_gc_percent(seq) -> Optional[float]`（`:340-345`）：`(count G + count C)/len*100`，**分母是串长，`N` 也计入分母**。
- `_outlier_reason_hints(y_value, gc_value, y_all, gc_all) -> List[str]`（`:348-368`）：归因提示三选一/多选——`extreme_target_y`（`|y-mean| > 3*std` **或** `y<0` **或** `y>1`，`:360`）、`abnormal_gc`（`|gc-mean| > 3*std`，`:364`）、都不满足则 `multivariate_anomaly`（`:367`）。要求全体有限值 ≥3 才做统计。

### 3.1.3 `class DataQualityController`（`:371`）

**构造函数 `__init__(data_path, output_dir=None, sequence_column=None, target_column=None, cell_line_column=None, epigenetic_columns=None, context_columns=None, force_positional=None, force_global=None, position_length=23, cv_folds=5, cv_subsample=2000, contamination=0.01, random_state=42, verbose=True)`（`:376-441`）**：
- `_resolve_input_files` 解析输入；空则 `FileNotFoundError`（`:403-404`）。
- 逐文件 `_read_table` 读入，任一文件为空即 `ValueError`（`:408-412`）。
- **只用第一个文件的列**做列映射探测（`probe_cols = self.frames[0][1].columns`，`:414`）；`sequence_column` 用 fuzzy，`target_column`/`cell_line_column` 用精确。
- `feature_spec = epigenetic_columns + context_columns`（`:434-437`）；`channel_types` 由 `_classify_channels` 填充；`long` 为长表；`result` 为最终 dict。

- `_build_long_frame() -> DataFrame`（`:446-493`）：多文件纵向拼成一张长表，列为 `_file`（文件名）、`_row`（**原始文件 1-based 行号，含表头；实现为 `int(i)+2`**，`:482`）、`_cl`（小写细胞系）、`sequence`（strip+upper）、`y`（float，不可解析 → `NaN`）、以及 `feature_spec` 的每个规范名列。细胞系来源：优先 `cell_line_column` 列值，空则回退为**文件名按 `[_\-.]` 切分的第一段小写**（`:455-456`）。

- `profile_sample_sizes() -> Dict`（`:498-517`）→ `result["sample_size"]`：有效样本 = 序列长度>0 且（若有目标列）`y` 非空；输出 `per_cell_line` / `total_samples` / `n_files` / `n_raw_rows`。

- `kde_target_efficiency() -> Dict`（`:522-577`）→ `result["target_efficiency"]`：对全体有限 `y` 做 CV 带宽 KDE；`n_valid>=3` 时写 `bandwidth_pooled`、`bandwidth_search_range`（`[std*0.05, std*1.5]`）、`skewness`、`kurtosis`、`mean`、`std`、`subsampled_cv`，并绘图 `target_efficiency_kde.png`（含每细胞系曲线 + 全体虚线 + 直方图，300 DPI）。

- `detect_ambiguous_bases() -> Dict`（`:582-612`）→ `result["ambiguous_bases"]`：逐序列求 `set(s) - set("ACGT")`；输出 `detected_ambiguous_bases`（排序字符表）、`per_base_frequency`、`total_ambiguous_characters`、`n_affected_sequences`、`affected_ratio`（分母为序列非空样本数）、`affected_rows`（file/row/cell_line）、`iupac_hint`（与 `"NRYSWKMBDHV"` 的交集）。**只统计，不替换、不删除。**

- `detect_monomorphic_positions() -> Dict`（`:617-653`）→ `result["monomorphic_positions"]`：**仅用长度 == `position_length`(23) 的序列**（`:622`）；按全体与按细胞系分别扫描 23 个位点，若某位点 `unique().size == 1` 记为单态；**分组样本数 < 3 直接跳过**（`:628-629`）；输出 `aligned_n`、`whole_dataset`、`per_cell_line` 与固定文案 `biological_risk_note`（提示零方差列会导致奇异矩阵）。

- `profile_gc_content() -> Dict`（`:658-712`）→ `result["gc_content"]`：逐序列 GC%，输出 `n_valid`、`bandwidth_pooled`、`bandwidth_search_range`、`mean/std/min/max`、`skewness`，以及**固定 `recommend_gc_as_feature = True`**（`:682`；有效值 <3 时为 `False`，`:710`）；绘图 `gc_content_kde.png`。

- `length_consistency() -> Dict`（`:717-744`）→ `result["length_consistency"]`：以**长度众数**作为 `recommended_length_L`（`:722-723`，不是硬编码 23）；逐行记录 `len(s) != mode` 的异常（file/row/cell_line/length/sequence）；输出 `length_distribution`、`n_length_anomalies`、`anomaly_ratio`。

- `_classify_channels() -> Dict[str,str]`（`:749-804`）→ 赋值 `self.channel_types`：对 `feature_spec` 每列按**取值格式**分类为 `positional` / `global_numeric` / `global_categorical`。`force_positional` / `force_global` 优先。自动判定阈值：`n_pos >= 0.6*tot 且 n_pos >= max(n_scalar,n_cat)` → `positional`；否则 `n_scalar >= n_cat 且 n_scalar >= 0.5*tot` → `global_numeric`；否则 `global_categorical`（`:796-801`）。缺省（无有效值/列缺失）时，`_POSITIONAL_CORE_NAMES` 中的名字 → `positional`，其余 → `global_categorical`（`:759-760`）。

- `length_alignment_qc() -> Dict`（`:809-935`）→ `result["length_alignment"]`（补充 QC-A）：位置型通道逐样本校验 `units == L`（L 取 `length_consistency.recommended_length_L`，回退 `position_length`，`:816-817`）；每通道输出 `n_aligned / n_misaligned / misaligned_ratio / n_blank / n_partial_nan`，明细 `misaligned_rows[:200]`、`blank_rows[:200]`、`misaligned_rows_truncated`（`:868-879`）。全局标量/离散列**明确不做 L 匹配**，只输出缺失率、非空数、唯一值数、以及 `mean/std/min/max` 或前 6 类频数（`:893-920`）。

- `zero_annotation_diagnostics() -> Dict`（`:940-1021`）→ `result["zero_annotation"]`（补充 QC-B）：区分「单通道整轨无标注」（该样本该通道 `_sample_feature_info.kind == "blank"`）与「局部点位缺失」（`kind=="pos" and has_nan`），以及「全局纯空白样本」（所有位置型核心通道同行均为 blank，`:996-1001`）。明细截断：`row_indexes[:500]`、`rows[:300]`、`rows_truncated`（`:983-985`）、局部缺失 `rows[:100]`（`:990`）。

- `epigenetic_gating() -> Dict`（`:1026-1094`）→ `result["epigenetic_gating"]`（70% 门禁）：
  - 按 `_cl` 分组；每通道先算 `coverage_pct`（非 blank 比例，`:1043-1044`）。
  - **仅对 `positional` 通道**再算 `strict_complete_pct`：非空且 `_parse_epi_vector(v, 23)` 可解析的样本占比（`:1046-1055`）。
  - **门禁阈值：`blocked = strict_pct < 70.0`**（`:1056`）；任一细胞系触发即把该通道加入全局 `blocked_channels`（`:1057-1058`）。
  - `global_numeric` / `global_categorical` 通道**不做 L 门禁**，`gate_blocked_under_70` 恒为 `False`，并附 `note`（`:1067-1077`）。
  - `gate_mode_rule` 文案声称「特征工程阶段强制禁用该通道参与消融实验与训练，或必须降级为 Zero-Masking 模式」（`:1084-1087`）——**该强制行为在仓库中无任何实现**（见 §3.4）。

- `detect_outliers_iforest() -> Dict`（`:1099-1202`）→ `result["outliers"]`（Isolation Forest 多模态离群）：
  - 特征向量构造（`:1106-1123`）：每个位点 **3 维序列 One-Hot，顺序 A / G / C——T 被有意省略**（`:1112-1114`）；序列不足 23 的位置补 `NaN`；随后每个表观通道追加 `_parse_epi_vector` 的 23 维结果，不可解析则 23 个 `NaN`。故 `feature_dim = 3*23 + 23*n_epi`（4 通道 = 161）。
  - 样本 <10 或全无有限值 → 跳过并写 `note`（`:1128-1131`）。
  - **中位数填充（仅用于离群检测）** → `StandardScaler().fit_transform`（在全体样本上拟合，`:1134-1137`）→ `IsolationForest(contamination=0.01, random_state=42, n_jobs=-1)`（`:1139-1143`）→ `decision_function` 作为 `anomaly_score`（越低越异常）。
  - 输出 `n_outliers`、`outlier_ratio`、`row_indexes`、`outlier_rows`、`per_cell_line_outlier_counts`、`detailed_rows`、`detailed_report_file="outliers_detailed_report.csv"`、`mean_outlier_efficiency` / `mean_all_efficiency` / `mean_efficiency_deviation`、以及 `handling_note`（建议用户评估保留或剔除，`:1196-1199`）。

- `_aggregate() -> None`（`:1207-1274`）：汇总 `qc_pass = (len(blocked_channels) == 0)`（`:1249`）、`issues`（未识别序列列/目标列、无表观列、门禁告警、非标准碱基、长度不对齐、纯空白样本等，`:1211-1247`）、`recommendations`（`:1251-1262`）、`metadata`（列映射 + 每列类型 + 文件列表 + `recommended_length_L`，`:1263-1274`）。

- `run() -> Dict`（`:1276-1301`）：建输出目录 → 建长表 → **按固定顺序**执行 11 个方法：`profile_sample_sizes, kde_target_efficiency, detect_ambiguous_bases, detect_monomorphic_positions, profile_gc_content, length_consistency, _classify_channels, length_alignment_qc, zero_annotation_diagnostics, epigenetic_gating, detect_outliers_iforest`（`:1285-1290`）；每个方法用 `try/except` 包裹，异常只记入 `result["module_errors"][fn_name]` 并继续（`:1291-1298`）；最后 `_aggregate()`。

- `build_markdown() -> str`（`:1306-1570`）：见 §3.2。
- `write_outputs() -> Dict[str,str]`（`:1575-1610`）：写 `quality_report.md`（utf-8）、`qc_summary.json`（`json.dumps(..., ensure_ascii=False, indent=2, default=_default)`，numpy 类型 → Python 原生，`:1582-1593`）、`outliers_detailed_report.csv`（**仅当 `detailed_rows` 非空时写出**，`utf-8-sig` 编码，显式列序，`:1596-1603`）；返回 5 个产物路径（含两个 PNG 路径，即使未绘图也会返回该路径）。

### 3.1.4 顶层入口与 CLI

- `_resolve_input_files(data_path) -> List[Path]`（`:1617-1635`）：目录 → `*.csv + *.tsv + *.txt` 排序；单文件 → 自身；序列 → 逐项校验存在。
- `run_data_qc(data_path, output_dir=None, **kwargs) -> Dict`（`:1638-1659`）：`DataQualityController(...).run()` + `write_outputs()`，返回完整 summary dict（与 `qc_summary.json` 内容一致）。
- `_demo_data()`（`:1666-1676`）/ `_synthesize_demo()`（`:1679-1714`）：优先用 `data/raw`；否则在临时目录合成 3 个脏数据 CSV（含 `N` 碱基、长度异常、`H3K4me3` 缺失列）。
- `main()` + `parse_args`（`:1717-1725`）：**有 argparse，仅 3 个参数**：`--data`（默认 `"auto"`）、`--output-dir`（默认 `None` → `data/data_report/`）、`--print-markdown`（flag）。**CLI 无法传入 `contamination` / `cv_folds` / 列映射等参数**，这些只能通过 Python API `run_data_qc(..., **kwargs)` 传入。

## 3.2 QC 产物 schema

**`qc_summary.json`** 顶层 key（`write_outputs` 直接 dump `self.result`，故 key 即为 `self.result` 的赋值集合）：

| key | 来源行 | 关键字段 |
| :--- | ---: | :--- |
| `sample_size` | `:516` | `per_cell_line`, `total_samples`, `n_files`, `n_raw_rows` |
| `target_efficiency` | `:576` | `n_valid`, `bandwidth_pooled`, `bandwidth_search_range`, `skewness`, `kurtosis`, `mean`, `std`, `subsampled_cv` |
| `ambiguous_bases` | `:611` | `detected_ambiguous_bases`, `per_base_frequency`, `total_ambiguous_characters`, `n_affected_sequences`, `affected_ratio`, `affected_rows`, `iupac_hint` |
| `monomorphic_positions` | `:652` | `aligned_n`, `whole_dataset`, `per_cell_line`, `biological_risk_note` |
| `gc_content` | `:711` | `n_valid`, `bandwidth_pooled`, `bandwidth_search_range`, `mean/std/min/max`, `skewness`, `recommend_gc_as_feature` |
| `length_consistency` | `:743` | `recommended_length_L`, `length_distribution`, `n_length_anomalies`, `anomaly_ratio`, `anomalies` |
| `length_alignment` | `:934` | `recommended_length_L`, `positional_channels`, `global_numeric_channels`, `global_categorical_channels`, `per_channel_alignment`, `global_feature_stats`, `note_types` |
| `zero_annotation` | `:1020` | `positional_channels`, `single_channel_all_blank`, `partial_positional_missing`, `global_all_channels_blank`, `note_definition` |
| `epigenetic_gating` | `:1093` | `channels`, `per_cell_line`, `blocked_channels`, `gate_mode_rule`, `warnings` |
| `outliers` | `:1130` / `:1201` | `n_samples`, `feature_dim`, `n_outliers`, `contamination`, `outlier_ratio`, `row_indexes`, `outlier_rows`, `per_cell_line_outlier_counts`, `detailed_rows`, `detailed_report_file`, `mean_*_efficiency`, `mean_efficiency_deviation`, `handling_note` |
| `module_errors` | `:1296` | 仅当某 QC 子模块抛异常时出现：`{方法名: 异常字符串}` |
| `qc_pass` | `:1249` | `bool`，等价于「无通道被 70% 门禁 block」 |
| `issues` | `:1250` | `List[str]` 告警 |
| `recommendations` | `:1251` | `List[str]` 建议 |
| `metadata` | `:1263` | `sequence_column`, `target_column`, `cell_line_column`, `epigenetic_columns`, `feature_columns{name:{column,type}}`, `files`, `recommended_length_L` |

**`quality_report.md` 章节**（`build_markdown` 实际 append 的标题，顺序固定）：

1. 头部：标题 + 生成时间 + 数据文件 + 输出目录 + `QC 状态: ✅ PASS / ⚠️ REVIEW`（`:1309-1313`）。
2. `## 1. 细胞系样本容量 (Sample Size Profiling)`（`:1317`）。
3. `## 3. 非标准碱基探测 (Ambiguous Base Detection)`（`:1328`）。
4. `## 4. 单核苷酸单态/零方差位点 (Monomorphic Positions)`（`:1353`）。
5. `## 5. GC 含量分布 (GC Content Profiling)`（`:1377`）。
6. `## 6. 序列长度一致性 (Sequence Length Consistency)`（`:1391`）。
7. `## 7. 表观遗传完整度与 70% 门禁 (Epigenetic Completeness & Hard Gating)`（`:1414`）。
8. `## 8. 多模态离群检测 (Isolation Forest)`（`:1437`）。
9. `## 9. 序列 × 表观长度对齐检测 (Length Alignment QC)`（`:1458`）。
10. `## 10. 表观零标注诊断 (Zero-Annotation Diagnostics)`（`:1510`）。
11. `## 汇总与建议`（`:1560`）+ `*QC PASS = ...*`（`:1569`）。

**注意：Markdown 中没有 `## 2` 章节**——第 2 项（编辑效率 KDE）只产出图片与 `target_efficiency` JSON，不写正文（docstring `:12` 声称报告覆盖「第 1,3,4,5,6,7,8 项」，与代码实际多出的 9/10 节也不一致）。

**图片**：`target_efficiency_kde.png`（`:575`）、`gc_content_kde.png`（`:708`），均 **300 DPI**、写在 `self.output_dir` 根目录（不是 `figures/` 子目录；`qc_service.py:86-87` 因此同时 glob 会话根与 `figures/`）。

**`outliers_detailed_report.csv` 列**（`:1600-1602`）：`sample_index`（= 原始文件 1-based 行号，`:1168`）、`file`、`cell_line`、`sequence`、`target_y`、`anomaly_score`（`decision_function` 值，`round 6`）、`gc_content`（`round 4`）、`outlier_reason_hints`（`; ` 连接）。

## 3.3 结果级 QC：`analysis/anomaly_treatment.py` + `analysis/data/validation.py`

### 3.3.1 `analysis/anomaly_treatment.py`（489 行）

**Status: Active**——由 `app/desktop/backend_runner.py:255-261` 在流程第 4/7 步以子进程调用（`--batch-dir <results>`）。

- 常量：`DEFAULT_COEF_THRESHOLD = 10.0`（`:35`）、`DEFAULT_SIGN_TOL = 1e-6`（`:36`）、`MODEL_NAME_MAP`（`:38-45`）。
- `parse_info_file(info_path) -> Dict`（`:52-61`）：逐行 `k: v` 解析并小写化 key/value；文件不存在返回 `{}`。
- `normalize_model(raw_model) -> str`（`:64-76`）：按子串 `linear/xgb/mlp/cnn/trans` 归一。
- `normalize_cell_line(split_type, raw_cell_line) -> str`（`:79-85`）：**`mixed` 一律归为 `'none'`**；空/`none`/`unknown` → `'unknown'`。
- `load_metrics_table(batch_dir) -> DataFrame`（`:92-117`）：优先 `<batch>/summary/metrics_tables/all_experiments.csv`，再 `<batch>/summary/all_experiments.csv`（`:93-96`）；都不可用时回退调用 `analyse.collect_results.collect_batch`（`:106-116`）。该 CSV 由 `analysis/collect_results.py:332` 写出。
- `aggregate_metrics(df) -> DataFrame`（`:120-137`）：id 列小写化后按 **`['split_type','cell_line','model','environment']` 求均值**（`:135-136`）。**分组键不含 `random_seed`，因此 mixed 的 4 个种子（42/43/44/45）在此被平均掉。**
- `detect_experiment_level_anomalies(metrics_df, sign_tol=1e-6) -> DataFrame`（`:144-208`）：以 `environment == 'sequence'` 行为基线，键为 `(split_type, cell_line, model)`（`:162`）；`|delta| <= sign_tol` 跳过（`:182-183`）；**同号（同增或同减）即判为指标矛盾**（`:185-187`），写入 `R2_baseline/R2/delta_R2/RMSE_baseline/RMSE/delta_RMSE/verdict` 与中文判定文案（`:190-193`）。
- `detect_data_level_anomalies(batch_dir, coef_threshold=10.0) -> DataFrame`（`:215-278`）：glob `**/*weights*.csv`，无则 `**/linear*coefficient*.csv`（`:221-224`）；跳过路径含 `summary` 的文件（`:227-228`）；从同级 `*info*.txt` 取 `model/split_type/cell_line/environment`，**非 linear 模型跳过**（`:234-236`）；列名容忍 `feature|feat` 与 `linear_coefficient|weight|coefficient|coef`（`:248-249`）；**跳过含 `bias` / `intercept` 的项**（`:258`）；**`abs(val) <= 10.0` 跳过，严格大于 10.0 才记录**（`:264`）；输出 `split_type/cell_line/environment/feature/weight/t_stat`。
- `aggregate_data_anomalies(detail_df) -> DataFrame`（`:281-299`）：按 `(cell_line, environment)` 聚合 `anomaly_count`、`max_abs_weight`、`example_features`（按 |weight| 降序前 3），并按 `max_abs_weight` 降序。
- `_fmt(value, digits=4) -> str`（`:306-309`）：NaN → `"N/A"`。
- `build_anomaly_report(batch_dir, exp_anoms, data_anoms_detail, data_anoms_agg, metrics_found, coef_threshold, sign_tol) -> str`（`:312-400`）：Markdown 结构 = 头部（含两条规则与容差）+ `## 1. 实验级异常 (指标同向矛盾)`（表格 11 列）+ `## 2. 数据级异常 (线性回归系数极大)`（`### 2.1` 汇总表、`### 2.2` 明细按 |Weight| 降序 **最多 200 条**，`:375`）+ `## 3. 汇总统计与处置建议`（含「建议检查特征矩阵的秩与条件数，或对线性模型启用 `--use-scaler` 与正则化」，`:394-396`）。
- `run_anomaly_treatment(batch_dir, summary_dir=None, coef_threshold=10.0, sign_tol=1e-6) -> str`（`:407-448`）：输出 `<batch>/summary/anomaly_report.md`（`summary_dir` 可覆盖，`:414`、`:444`）。
- `main()` + `parse_args`（`:451-462`）：**有 argparse**，参数 `--results-dir`(默认 `results`)、`--batch-name`、`--batch-dir`、`--latest`、`--summary-dir`、`--coef-threshold`(默认 10.0)、`--sign-tol`(默认 1e-6)。批次选择逻辑：无 `--batch-dir/--batch-name` 时，若 `results` 根下存在 `single_*/all_*/mixed_*` 目录则把根当批次，否则取 mtime 最新的子目录（`:468-474`）。

### 3.3.2 `analysis/data/validation.py`（63 行）

**Status: Active**——由 `analysis/pipeline.py:21` import、`:84` 调用（`anomalies = validate_metric_consistency(table)`），结果写 `tables/metric_inconsistency.csv`（`pipeline.py:85`）；单测见 `analysis/tests/test_core.py:16,42-50,163`。

- `metric_consistency_flags(delta_r2, delta_rmse, tol=1e-9) -> List[str]`（`:14-26`）：返回 `metric_inconsistency_same_increase`（两者 > +tol）、`metric_inconsistency_same_decrease`（两者 < -tol）或空列表（即 `ok`，不显式返回该标签）。
- `validate_metric_consistency(table, tol=1e-9) -> DataFrame`（`:29-63`）：**配对规则（paired cohort）**——基线字典的键是 `(split_type, cell_line, model, seed)`，其中 `seed` 取自 `random_seed`，缺省字符串 `"none"`（`:38-40`）；**`environment == 'sequence'` 行只作基线、不参与打分**（`:36-37`、`:44-45`）；表为空或无 `environment` 列时返回空表（列 `row,flags,delta_r2,delta_rmse`）；命中行输出 `row`、`experiment`（`run_name`）、`flags`、`delta_r2`、`delta_rmse`（均 `round 6`）。
- **拒绝行为**：模块 docstring（`:1-6`）明确「此检查只『标记不一致』，不删除任何实验 (Metric inconsistency != 实验无效)」；代码中确实只有 `DataFrame` 构造，无删除/过滤写回。

**两套结果级 QC 的规则差异（重要）**：`validation.py` 按 `(…, seed)` **同种子配对**，而 `anomaly_treatment.py:135-136` 先把多种子聚合成均值再比较——后者违反前者的「mixed 多 seed 绝不跨 seed 比较」原则（见 §6.5）。

## 3.4 QC → 用户决策 边界

1. **QC 只检测、不修改数据**：`analysis/data_QC.py` 全文无写原始 CSV、无 `drop_duplicates`、无 `replace`、无 `fillna` 落盘（grep `duplicated|drop_duplicates|dedup` 在该文件零命中）。唯一的中位数填充只作用于离群检测的**内存副本** `Xf`（`:1134-1136`），不落盘、不回写。唯一的数据表输出是独立文件 `outliers_detailed_report.csv`。
2. **「70% 门禁 + 强制禁用 / Zero-Masking」尚未实现**：`epigenetic_gating` 只把结果写进 `blocked_channels` 与 Markdown 文案；全仓库 grep `blocked_channels` 的消费者只有 `app/frontend/src/components/QcDashboard.tsx:21`（且它读的是 `qc_pass` 而非 `blocked_channels`）。`Zero-Masking` 一词只出现在 `data_QC.py:1086/1255/1431` 的文案里，`core/features/channels/cell_environment_combination.py` 中的 masking 是**通道选择掩码**（选中即保留原始值、未选中即置零），不是「整通道缺失时的降级填充」。
3. **`analysis/config.py:47` 的 `ambiguous_detection_only=True`** 表达了「只检测，处理策略由 Wizard 决策」的设计意图，但该 dataclass 未被 `data_QC.py` 引用（`data_QC.py:27-47` 无 `analyse.config` import）；`AnalysisConfig` 的实际消费者是 `analysis/evidence/*` 与 `analysis/pipeline.py`。
4. **`workflow_config.json` 目前只是一个占位符，不存在写入机制**：全仓库仅 3 处提及——`app/backend/crispr_workspace/project.py:64`（`config_versions` 中恒为 `None` 的键）、`app/frontend/src/views/WorkspaceView.tsx:104,106`（文案）、`docs/frontend_architecture.md:61`（文档）。**没有任何代码写出 `workflow_config.json`。**
5. **已实现的「决策」路径只有指纹校验**：`QCSessionManager.start/store`（`app/backend/crispr_workspace/qc_service.py:92-114`）落 `session_manifest.json`（`schema: "qc.session/1"`、`status`、`dataset.fingerprint`、`outputs`）；`create_from_qc`（`app/backend/crispr_workspace/project.py:113-131`）要求 `status == "completed"`，且当传入 `current_paths` 时比对指纹、不一致即 `ValueError("数据集已变化, 不能复用旧 QC 结果; 请先重新运行 QC")`。这是「不得换数据后误用旧 QC」的硬约束，与「用户勾选禁用通道」无关。
6. `analysis/pipeline.py:133-134` 中任务 `qc` 的「执行」是空操作（`if _should_run("qc"): _finish("qc")`），批次级数据质量内容来自 `build_data_quality_md`（`analysis/reports/markdown_report.py:152-165`），与 `data_QC.py` 是两套不同层级的东西。

---

# 4. 数据映射与预处理

## 4.1 序列编码

仓库中存在**两套独立实现**，语义并不等价：

**A. 严格编码器（`core/features/engineering/feature_engineering.py`，数据实际来源）**

```python
validate_sequence(sequence, name)        # :332-355  str().strip().upper()，len != 23 直接 ValueError
encode_sgrna(sgrna, sequence_channels=None)  # :358-429
```

- 输出 dtype `float32`、形状 `(23, C_seq)`（`:398-404`）。
- 通道表 `channel_to_index` 由 `sequence_channels` 顺序动态生成（`:392-396`）。
- 默认 `DEFAULT_SEQUENCE_CHANNELS = ["A","C","G","T"]`（`:147-152`），**四碱基全部显式存在**，`pos_b` 置 1.0（`:420-427`）；`T` 拥有独立通道（不是隐式参照）。
- **任何不在 `sequence_channels` 中的字符 → `ValueError`**（`:411-418`），即含 `N` 的序列会让整个 `process_one_csv` 失败（异常被 `engineer_dataframe` 包成 `处理第 {index+2} 行失败`，`:1270-1273`）。
- 线性回归侧另有「哑变量陷阱防护」：`select_non_t_reference_features`（`core/models/linear/linear_regression.py:468-488`）剔除所有以 `_T` 结尾的特征列（`REFERENCE_T_SUFFIX = "_T"`，`:465`），`184 → 161`，以 `T` 为基准对照（`:734-744`）；实测 `results/batches/batch_20260909_full/single_hct116_linear_all/linear_regression_info.txt` 记录 `Feature count: 161 / Numerical rank: 149 / Condition number: 565.6`。**特征张量本身始终保留 T 通道**（`core/features/engineering/feature_engineering.py:372-374`）。

**B. 宽松编码器（`app/desktop/backend_runner.convert_raw_csv_to_npy`，向导路径）**

- 序列通道索引硬编码 `{'A':0,'C':1,'G':2,'T':3}`（`app/desktop/backend_runner.py:61`），与 A 一致。
- 但序列先 `ljust(23,'N')[:23]`（`:65`），**不报错**；非 ACGT 字符不置位 → 该位点形成全零列（`:66-69`）。

## 4.2 表观/环境通道编码

**通道顺序（全局唯一约定）**：`A, C, G, T, CTCF, Dnase, H3K4me3, RRBS`，共 8 通道（`data/processed/feature_schema.json:53-62`、`data/metadata/feature_config.json:2-49`、`core/features/engineering/feature_engineering.py:147-152` + 配置顺序、`app/desktop/backend_runner.py:107`）。环境通道顺序 = `feature_config.json` 中 `environment_features` 的**数组顺序**（`get_channel_specs`，`core/features/engineering/feature_engineering.py:794-804`），不是字母序。

**`per_position_binary` 语义**（当前 4 条轨道全部使用）：23 字符串逐位查 `encoding` 字典，**`"A" → 1.0`、`"N" → 0.0`**（`data/metadata/feature_config.json:13-16` 等）；出现字典外字符 → `ValueError`（`core/features/engineering/feature_engineering.py:471-478`）。输出 `(23,1)` float32。

**另两种已实现但当前配置未启用的类型**：

- `per_position_numeric`（`encode_per_position_numeric`，`:608-626`）：输入 23 个连续值，接受 list/tuple/ndarray、`"[0.1,0.2,...]"` JSON、`"0.1,0.2,..."` 逗号串（`parse_position_numeric_values`，`:494-601`）；个数必须 ==23；含 NaN/Inf → `ValueError`；输出 `(23,1)`。
- `global_numeric`（`encode_global_numeric`，`:633-691`）：单个标量**广播到 23 个位点**，输出 `(23,1)`；NaN/Inf → `ValueError`。
- 校验见 `validate_feature_config`（`:215-297`）：三种 type 白名单、`per_position_binary` 必须有 `encoding` dict、`enabled` 必须 bool、名称不得重复。

**汇总语义**：所有环境类型都保证 `(23,1)`，`build_feature_matrix` 校验后 `np.concatenate(matrices, axis=1)` 并断言最终形状 `(23, 4+n_env)`（`:866-910`）。

**QC 侧的另一种读法**：`_parse_epi_vector` 把 `A/Y/T/1` 视为 1、其余（含 `N/0`）视为 0（`analysis/data_QC.py:236-238`），与 `feature_config.json` 的 `{A:1, N:0}` 一致；但 QC 的**离群特征向量只用 A/G/C 三个序列通道**（`:1112-1114`），与模型的 4 通道不一致。

## 4.3 去重 / 缺失 / 掩码 / 标准化

| 处理 | 是否存在 | 实现位置与语义 |
| :--- | :--- | :--- |
| **去重** | **仅特征工程有** | `remove_duplicate_rows`（`core/features/engineering/feature_engineering.py:1067-1126`）：`df.duplicated(keep="first")`，**仅删除整行完全相同的记录**；`load_source_csv` 在列检查与缺失检查之后调用（`:1218-1223`）。实测 hek293t `4566 → 2333`（删 2233），其余 3 系 0 条。**QC (`data_QC.py`) 不做任何去重**（grep 无命中）。 |
| **缺失值** | **特征工程 `ValueError` 中止；向导路径静默补零** | 特征工程：`df[required_columns].isnull().any().any()` 为真即抛 `ValueError` 并列出各列缺失计数（`:1187-1212`）。向导路径：匹配不到表观列 / 长度≠23 / 非数值 → 该通道保持 0（`app/desktop/backend_runner.py:74-82`），目标列缺失 → 随机标签（`:85`）。QC：只统计不处理。 |
| **掩码 (masking)** | **有，但只是通道选择** | `create_channel_mask(schema, combination, selected_environments)`（`core/features/channels/cell_environment_combination.py:1063-1144`）：长度 = `channel_count` 的 float32 向量；序列通道**恒为 1**（`:1120-1128`），被选中的环境通道置 1。`apply_environment_combination`（`:1151-1236`）先校验 `X_3d.shape[1:] == (sequence_length, channel_count)` 且 `np.isfinite(X_3d).all()`（NaN/Inf → `ValueError`，`:1210-1216`），再返回 `X_3d.copy() * mask.reshape(1,1,C)`（原数组不修改，`:1228-1236`）。**未选中通道被置 0 而非删除**，故所有组合的特征维度恒为 `23*8 = 184`。 |
| **标准化 / 归一化** | **数据管线内不存在；仅在模型训练层以 opt-in 开关存在** | `core/features/engineering/feature_engineering.py`、`cell_line_division.py`、`cell_environment_combination.py`、`data_QC.py` 均无 scaler 拟合（QC 的 `StandardScaler` 只用于离群检测，`analysis/data_QC.py:1137`）。模型侧：`workflows/training/train.py:623 --use-scaler`（`action="store_true"`，**默认关闭**），经 `build_train_kwargs` 透传 `use_scaler`（`workflows/training/train.py:402`）。MLP：`scaler.fit_transform(X_train)` 后 `transform(X_valid/X_test)`（`core/models/mlp/mlp.py:555-563`，日志 `StandardScaler fitted on training data.`）；CNN 同理（`core/models/cnn/cnn.py:640-650`，把 `(N,L,C)` reshape 成 `(N*L,C)` 拟合，并落盘 `cnn_scaler.pkl`，`:790-794`）；线性回归：`fit_transform(X_train)` / `transform(X)`（`core/models/linear/linear_regression.py:159-162`、`:275-278`），`use_scaler` 与权重一同存盘（`:312`、`:375-382`）。实测批次 `results/batches/batch_20260909_full` 的 `*_info.txt` 全部为 `use_scaler: False`。 |
| **缺失值填充 (imputation)** | **数据管线内不存在** | 除 QC 离群检测的内存中位数填充外，无任何 `fillna`/`SimpleImputer`。 |
| **重采样 / 类别平衡** | **不存在** | 无 SMOTE、无样本权重、无 `class_weight`。 |

---

# 5. 特征工程

## 5.1 `core/features/engineering/feature_engineering.py` 函数级清单

**Status: Uncertain（CLI 可达、数据实际由它产出，但运行时流水线不 import 它）**——证据：全仓库 grep `feature_engineering` 只命中 `app/desktop/backend_runner.py:94/182`（那是**同名但独立**的 `run_feature_engineering_step`，其内部不 import 本模块）与本文件自身；但 `data/processed/feature_engineering_summary.csv` 的列只可能由本文件 `process_all_csv` 写出（§2.3）。

### 配置加载与校验

- `load_feature_config(config_file) -> dict`（`:159-208`）：读 JSON；文件不存在 → `FileNotFoundError`；非 object / 缺 `environment_features` / 非 list → `ValueError`；最后调用 `validate_feature_config`。
- `validate_feature_config(config) -> None`（`:215-297`）：逐 spec 校验必需键 `name/column/type`、名称唯一、type ∈ `{per_position_binary, per_position_numeric, global_numeric}`、binary 必须有 encoding dict、`enabled` 必须 bool。
- `get_enabled_environment_features(config) -> List[dict]`（`:304-325`）：`spec.get("enabled", True)` 为真者，**保持配置顺序**。
- `get_channel_specs(config) -> List[dict]`（`:757-806`）：序列通道（`config.get("sequence_channels", DEFAULT_SEQUENCE_CHANNELS)`）在前、启用的环境特征在后，每项为 `{name, source, type}`。
- `get_required_columns(config) -> List[str]`（`:1030-1060`）：固定 6 列（`Chromosome/Start/End/Strand/sgRNA/Normalized efficacy`）+ 去重后的各环境源列。

### 编码

- `validate_sequence(sequence, name="sequence") -> str`（`:332-355`）：`strip().upper()` 且长度必须 ==23。
- `encode_sgrna(sgrna, sequence_channels=None) -> ndarray(23,C_seq)`（`:358-429`）：见 §4.1。
- `encode_per_position_binary(sequence, feature_name, encoding) -> ndarray(23,1)`（`:436-487`）：见 §4.2。
- `parse_position_numeric_values(value, feature_name) -> ndarray(23,)`（`:494-601`）：三种输入形态解析 + 长度/有限性校验。
- `encode_per_position_numeric(value, feature_name) -> ndarray(23,1)`（`:608-626`）：`reshape(23,1)`。
- `encode_global_numeric(value, feature_name) -> ndarray(23,1)`（`:633-691`）：标量广播。
- `encode_environment_feature(row, spec) -> ndarray(23,1)`（`:698-750`）：按 `spec["column"]` 取原始列（列不存在 → `ValueError`），按 `spec["type"]` 分派到上述三个编码器；未知 type → `RuntimeError`。
- `build_feature_matrix(row, config) -> ndarray(23,C)`（`:813-912`）：`encode_sgrna(row["sgRNA"])` → 逐个环境特征 append（每个都断言 `(23,1)`）→ `np.concatenate(axis=1)` → 断言 `(23, 4+n_env)`。

### schema 与命名

- `generate_vector_feature_names(config) -> List[str]`（`:919-951`）：位置外循环、通道内循环，命名 `f"pos{position}_{channel['name']}"`，共 `23*C` 个。
- `generate_feature_schema(config) -> dict`（`:958-1023`）：输出 7 个键 `sequence_length / sequence_channels / environment_features / channel_count / feature_count / channel_names / feature_names`；`channel_count = len(channel_specs)`，`feature_count = 23 * channel_count`。
- `save_feature_schema(config, output_file) -> None`（`:1532-1557`）：`json.dump(..., indent=4, ensure_ascii=False)`。

### 读入、清洗与变换

- `remove_duplicate_rows(df) -> (df, duplicate_count)`（`:1067-1126`）：整行去重 + 打印三段计数。
- `load_source_csv(csv_file, cell_line, config) -> (df, duplicate_count)`（`:1133-1238`）：`pd.read_csv` → 空文件 `ValueError` → 必需列检查 → 缺失值检查（抛错）→ 去重 → `df.insert(0, "Cell line", cell_line)`。
- `engineer_dataframe(df, config) -> (features_3d, features_2d, labels)`（`:1245-1343`）：`df.iterrows()` 逐行编码（异常包装为「处理第 {index+2} 行失败」）→ `np.asarray(matrices, dtype=np.float32)` → `features_3d` 形状断言 `(N,23,C)` → `features_2d = features_3d.reshape(len(df), 23*C)` → `labels = df[TARGET_COLUMN].to_numpy(float32)`。

### 落盘

- `save_matrix_csv(df, features_3d, output_file, config) -> None`（`:1350-1384`）：列为 `METADATA_COLUMNS` + `features`（`matrix.tolist()` 的嵌套列表字符串）+ `Normalized efficacy`。
- `save_vector_csv(df, features_2d, output_file, config) -> None`（`:1391-1447`）：`METADATA_COLUMNS` + 184 个 `posN_通道` 列 + 目标列；写入前断言 `features_2d.shape[1] == len(feature_names)`。
- `save_numpy_files(features_3d, features_2d, labels, output_dir, cell_line) -> None`（`:1454-1498`）：写 `{cl}_features_23x{C}.npy`、`{cl}_features_{F}.npy`、`{cl}_labels.npy`，其中 C/F 从数组实测形状取（**非写死**）。
- `save_metadata(df, output_file) -> None`（`:1504-1525`）：`METADATA_COLUMNS` + 目标列 → `{cl}_metadata.csv`。

### 编排与 CLI

- `process_one_csv(csv_file, output_dir, config) -> dict`（`:1564-1757`）：cell_line 取**文件名去扩展名**（`:1573-1577`）→ 加载/清洗 → 特征工程 → 计算 4 个输出路径 → 依次 save 四个产物 → 打印汇总 → 返回 `{cell_line, original_samples, duplicate_rows, final_samples, channel_count, feature_count}`。
- `process_all_csv(source_dir, output_dir, config) -> None`（`:1764-1960`）：`glob("*.csv")` 排序 → 打印 schema → **先写一次 `feature_schema.json`**（`:1867-1875`）→ 逐文件处理 → 汇总写 `feature_engineering_summary.csv`（`:1899-1911`）。
- `parse_args() / main()`（`:1967-2029`）：**有 argparse**，3 个参数：`--source-dir`（默认 `data/raw`）、`--output-dir`（默认 `data/processed`）、`--config`（默认 `data/metadata/feature_config.json`）。**无 `--seed`、无 `--use-scaler`、无 `--contamination` 等参数**。

## 5.2 schema 与 shape 变化（真实数字）

```
data/raw/{cl}.csv
  └─ pd.read_csv → DataFrame (N_raw, 10)   列: Chromosome,Start,End,Strand,sgRNA,
                                                 CTCF,Dnase,H3K4me3,RRBS,Normalized efficacy
  └─ remove_duplicate_rows (整行去重)        hek293t 4566 → 2333; 其余 0 删除
  └─ df.insert(0,"Cell line",cl) → (N, 11)
  └─ engineer_dataframe 逐行
        encode_sgrna          → (23, 4)       # A,C,G,T 各 1 通道
        ×4 per_position_binary→ (23, 1) each  # CTCF,Dnase,H3K4me3,RRBS
        concatenate axis=1    → (23, 8)
  └─ np.asarray(dtype=float32) → X_3d (N, 23, 8)     实测: 4239/2333/8101/2076
  └─ reshape(N, 23*8)          → X_2d (N, 184)
  └─ df["Normalized efficacy"] → y (N,) float32
```

`data/metadata/feature_config.json` / `data/processed/feature_schema.json` 的实际取值（逐键核对）：

| 字段 | 值 |
| :--- | :--- |
| `sequence_length` | `23`（schema 有；config 中无此键，由代码常量 `SEQUENCE_LENGTH=23` 决定） |
| `sequence_channels` | `["A","C","G","T"]` |
| `environment_features` | 4 个对象，依次 `CTCF`、`Dnase`、`H3K4me3`、`RRBS`，均 `type="per_position_binary"`、`encoding={"A":1,"N":0}`、`enabled=true`，`column` 与 `name` 同名 |
| `channel_count` | `8`（schema 有；config 无，由 `len(channel_specs)` 推出） |
| `feature_count` | `184`（= 23×8） |
| `channel_names` | `["A","C","G","T","CTCF","Dnase","H3K4me3","RRBS"]` |
| `feature_names` | 184 项，`pos1_A, pos1_C, pos1_G, pos1_T, pos1_CTCF, pos1_Dnase, pos1_H3K4me3, pos1_RRBS, pos2_A, … pos23_RRBS` |

`feature_schema.json` 顶层**没有** `random_seed` / `train_ratio` / `scaler` 等字段；`environment_features` 在 schema 中保留了完整 spec（含 `encoding` 与 `enabled`），而 `app/desktop/backend_runner.py:108-114` 写出的 schema **只有 5 个键**（`sequence_length`/`channel_count`/`feature_count`/`channel_names`/`sequence_channels`），**没有 `feature_names`，也没有 `environment_features`**。

## 5.3 特征命名/顺序

- 展平顺序 = **位置主序**：`for position in 1..23: for channel in channel_names:`（`generate_vector_feature_names`，`core/features/engineering/feature_engineering.py:940-949`）。
- `channel_names` 顺序即张量第 3 维顺序：`A, C, G, T, CTCF, Dnase, H3K4me3, RRBS`。
- 训练侧 `workflows/training/train.py:build_feature_names`（`:306-322`）用同一规则重建 2D 特征名；若数量不匹配则整体降级为 `feature_0..feature_{n-1}`（`:317-318`）。
- 1D/3D 语义：`pos1_A` 对应 `X_3d[:,0,0]`，`pos23_RRBS` 对应 `X_3d[:,22,7]`，`X_2d[:,183]`。

---

# 6. 数据划分与数据集构建

**主实现**：`core/data/splitting/cell_line_division.py`（**Status: Active**——`workflows/training/train.py:242` import 并调用 `divide_data`；`workflows/prediction/predict.py:242` import `discover_available_cell_lines/load_cell_line`、`:759` import `load_feature_schema`；`scripts/make_notebook.py:138` 亦引用）。

## 6.1 single / all / mixed 语义

| split_type | 入口函数 | 语义（代码行为） |
| :--- | :--- | :--- |
| `single` | `split_single_cell_line`（`:195-207`） | 单个细胞系内部按比例随机划分；`train/validation/test_cell_lines` 都写 `[cell_line]`；`split_type="single"` |
| `all` | `split_all_cell_lines`（`:210-253`） | **两种子模式**：① 传入 `test_cell_line`（且存在于 datasets）→ 留一细胞系（LOCO/Leave-One-Out）：其余细胞系 merge 作训练池，池内再切 train/valid，测试集 = 整个留出细胞系（`:219-236`）；② 未传 → **各细胞系各自独立划分后合并**（每个细胞系用 `random_seed + i` 偏移，`:240-241`），`train/validation/test_cell_lines` 均为全列表 |
| `mixed` | `split_mixed_cell_lines`（`:256-273`） | 先把所有细胞系 `merge_datasets` 成一个大池，再整体随机划分（`:261-262`）；`cell_line="none"` |

- `divide_data(data_dir, split_type, cell_line=None, cell_lines=None, train_fraction=0.70, validation_fraction=0.15, test_fraction=0.15, random_seed=42)`（`:295-334`）：统一入口。`cell_lines` 缺省用 `discover_available_cell_lines`，并**过滤掉不在可用列表中的名字**（`:313`）；`single` 用 `cell_line or cell_lines[0]`。结果附 `schema`、三个 fraction、`n_train/n_valid/n_test`，再经 `attach_public_fields`（`:276-292`）展开出 `X_train_3d/X_valid_3d/X_test_3d/X_train_2d/X_valid_2d/X_test_2d/y_train/y_valid/y_test/metadata_train/metadata_valid/metadata_test`。
- **退化保护（实测触发）**：`split_all_cell_lines` 开头 `if len(datasets) == 1 or len(cell_lines) <= 1:` 直接返回 `split_single_cell_line(...)`，但**返回值仍是 `split_type="single"`**（`:214-217`）；而 `workflows/training/data_digging.py` 为 `all` 模式逐个细胞系单独调度（`build_command` 只传 `--cell-line`，`workflows/training/data_digging.py:313-314`），因此实测目录 `results/batches/batch_20260909_full/all_linear_all_heldout_hela/` 的 info 中 `split_type: all` 但 `cell_lines: ['hela']`、`input_shape_train: [5670, 184]`（= floor(8101×0.7)），**实际是细胞系内 70/15/15 划分，并非跨细胞系泛化**。`all_cnn_all_heldout_hct116_kernel_3` 同理（`[2967,23,8]/[635,...]/[637,...]`）。
- **实测 mixed**：`mixed_linear_all_seed_42` → `input_shape_train: [11724,184]`、`valid [2512]`、`test [2513]`，总数 16749 = 4239+2333+8101+2076，与「先合并再划分」一致。
- `workflows/training/train.py` 侧：`prepare_split_data`（`:232-252`）→ `cld.divide_data`；`validate_split_result`（`:259-284`）只校验 `X_*_3d` 为 3D 且样本数与 `y` 一致；`prepare_model_data`（`:291-299`）→ `cell_environment_combination.prepare_train_valid_test`。
- `workflows/prediction/predict.py` 的 mixed 十折 CV 走 `_load_mixed_subset`（`workflows/prediction/predict.py:241-260`），直接 concatenate 各细胞系，**不复用 `divide_data`**；`--ultimate-cv-folds` 默认 `10`、`--ultimate-seed` 默认 `42`（`workflows/prediction/predict.py:746-748`）。

## 6.2 train/valid/test 比例、seed、LOCO

**比例常量**：

- `cell_line_division.py:21-23`：`DEFAULT_TRAIN_FRACTION = 0.70`、`DEFAULT_VALIDATION_FRACTION = 0.15`、`DEFAULT_TEST_FRACTION = 0.15`。
- `workflows/training/train.py:33-35`：`DEFAULT_TRAIN_RATIO = 0.70`、`DEFAULT_VALID_RATIO = 0.15`、`DEFAULT_TEST_RATIO = 0.15`；`workflows/training/train.py:619-621` CLI 默认同值。
- `workflows/training/data_digging.py:409-411`：同样 `0.70/0.15/0.15`。
- `validate_split_fractions`（`cell_line_division.py:89-95`）：三者必须 > 0 且和 ≈ 1（`atol=1e-5`）。`workflows/training/train.py:validate_split_configuration`（`:207-225`）另用 `atol=1e-8` 复核。

**划分算法**（`create_split_indices`，`:154-172`）：`n_samples < 3` → `ValueError`；`rng = np.random.default_rng(random_seed)` → `indices = arange(n)` → `rng.shuffle(indices)`；`train_size = int(np.floor(n*0.70))`、`validation_size = int(np.floor(n*0.15))`，两者 `max(1, …)`；`test = indices[train_size+validation_size:]`（若已到末尾则退化为 `indices[train_size:]`）。**注意：`test_fraction` 只参与「和是否为 1」的校验，不参与任何 size 计算；`floor` 产生的余数全部归入 test。**

**seed**：

- 默认 `random_seed=42`（`cell_line_division.py:154/195/210/256/303`；`workflows/training/train.py:31 DEFAULT_RANDOM_SEED = 42`、`:622 --seed`）。
- `all`（模式②，各系独立划分）用 `random_seed + i` 逐个偏移（`cell_line_division.py:241`）。
- `workflows/training/data_digging.py:59 MIXED_SEEDS = [42, 43, 44, 45]`；`build_command` 对 non-mixed **强制 `random_seed = 42`**（`workflows/training/data_digging.py:275`），对 mixed 用 42/43/44/45（`:146`、`:160`）。`--mixed-seeds` 可覆盖（`:404`）。
- 每次实验的 seed 写入 `config["random_seed"]` 与模型 kwargs 的 `random_seed`/`seed` 双键（`workflows/training/train.py:400-401`）。

**LOCO / 留一细胞系**：

- 触发条件：`split_type="all"` 且 `cell_line`（即 `test_cell_line`）存在于 datasets（`cell_line_division.py:219`）。
- **内部硬编码 `train_fraction=0.85, validation_fraction=0.15, test_fraction=0.0`**（`:225`），**完全忽略调用方传入的 0.70/0.15/0.15**。`validate_split_fractions` 要求各项 > 0，而 `test_fraction=0.0` 会抛 `ValueError`——好在 `create_split_indices` 内部**不**调用 `validate_split_fractions`（该调用只在 `divide_data:306` 与 `create_split_indices` 自身的第一行… 需注意：`create_split_indices` 第一行确实调用了 `validate_split_fractions`，故 LOCO 分支这一行在运行时必然抛 `ValueError: Train / Validation / Test 比例必须 > 0。`）。**这是一处真实缺陷**：LOCO 分支在当前代码下不可用。
- 运行命名：`all_{model}_{environment}_heldout_{cell_line}`（`workflows/training/data_digging.py:172`；`workflows/training/train.py:164` 同规则）。
- 测试集 = 留出细胞系的**全部样本**（不切片，`:235`）。

## 6.3 每实验目录产物

目录命名（由调用方决定，`workflows/training/train.py:build_batch_directories:178-200`）：`{results}/{batch}/{run_name}`，`run_name` 规则见 `workflows/training/train.py:generate_run_name:156-171`（`single_{cl}_{model}_{env}_{ts}` / `all_{model}_{env}_heldout_{cl}_{ts}` / `mixed_{model}_{env}_{ts}`）；但 `data_digging` 传入固定 `--run-name`（`workflows/training/data_digging.py:281`），故实际目录名**无时间戳**。

实测目录内容（`results/batches/batch_20260909_full/single_hct116_linear_all/`）：

| 文件 | 写出者 | 说明 |
| :--- | :--- | :--- |
| `linear_regression_info.txt` | `core/models/linear/linear_regression.py:630` | 头部含 `Feature count / Numerical rank / Condition number / Scaler / pinv_rcond`，随后是完整 `config`（含 `channel_names`、`input_shape_train/valid/test`）与 Validation/Test 六项指标 |
| `linear_regression_metrics.json` | 同 `:612` | 测试集指标 |
| `linear_regression_validation_metrics.json` | 同 `:616` | 验证集指标 |
| `linear_regression_predictions.csv` / `linear_regression_validation_predictions.csv` | 同 `:621` / `:782` | `y_true, y_pred, error`（`save_predictions`，`:516-522`） |
| `linear_regression_weights.csv` | 同 `:624` | anomaly_treatment 数据级异常的输入 |
| `linear_regression_diagnostics.json` | 同 `:302` / `:627` | SVD/秩/条件数诊断 |

其余模型的同类产物：`cnn_info.txt / cnn_metrics.json / cnn_validation_metrics.json / cnn_predictions.csv / cnn_validation_predictions.csv / cnn_training_history.csv`（`core/models/cnn/cnn.py:428-456`）、`mlp_*`（`core/models/mlp/mlp.py:352-380`）、`transformer_*`（`core/models/transformer/transformer.py:434-462`）、`xgboost_*`（`core/models/xgboost/xgboost.py:431-442`）。

**批次级产物**：`{batch}/summary/metrics_tables/all_experiments.csv`、`single_cell_line_result.csv`、`all_cell_line_result.csv`、`mixed_cell_line_result.csv`、`baseline.csv`（`analysis/collect_results.py:332-396`，输出目录 `:436`）；`{batch}/summary/anomaly_report.md`（`anomaly_treatment.py:444`）；`{batch}/summary/feature_importance/key_regulatory_biomarkers.csv`（`backend_runner.py:289`）；`{batch}/summary/赛道二_results.csv`（`workflows/prediction/predict.py:821`）与 `{batch}/summary/ultimate/`（默认目录 `workflows/prediction/predict.py:796`，模型/配置落盘 `:435-469`）。

**注意**：`info.txt` / `metrics.json` 由**各模型模块的 `train()`** 写出，`workflows/training/train.py` 本身不写这些文件；`workflows/training/train.py` 只负责组装 `config` 与 kwargs 并透传（`workflows/training/train.py:520-592`）。

---

## 6.4 数据流总览

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ 原始 CSV                                                                              │
│   data/raw/{hct116,hek293t,hela,hl60}.csv  (N, 10)                            │
│   Chromosome,Start,End,Strand,sgRNA,CTCF,Dnase,H3K4me3,RRBS,Normalized efficacy       │
│   环境轨道 = 23 字符 A/N 串                                                            │
└───────────────┬──────────────────────────────────────────────┬───────────────────────┘
                │ 路径 A（数据实际来源）                        │ 路径 B（向导运行时）
                ▼                                              ▼
   core/features/engineering/feature_engineering.py  (CLI)              app/desktop/backend_runner.convert_raw_csv_to_npy
   ① load_source_csv: 必需列 + 缺失值检查(报错)      ① 列名兜底探测 seq_col/target_col
      ② remove_duplicate_rows (整行去重)              ② 硬编码 zeros((N,23,8))
   ③ encode_sgrna → (23,4) A/C/G/T 全通道           ③ 硬编码索引 A0 C1 G2 T3;
   ④ encode_per_position_binary ×4 → (23,1)           ljust(23,'N')[:23]; 未知碱基→全零列
      encoding={"A":1,"N":0}                       ④ 表观列名子串匹配; 串长23→'1/A/Y/T'=1;
   ⑤ concatenate → X_3d (N,23,8) → X_2d (N,184)       数值→整通道广播
   ⑥ 落盘: {cl}_23x8.csv / {cl}_184.csv /           ⑤ 落盘: {cl}_features_23x8.npy /
           {cl}_features_23x8.npy / {cl}_features_184.npy /       {cl}_features_184.npy /
           {cl}_labels.npy / {cl}_metadata.csv                    {cl}_labels.npy / {cl}_metadata.csv
      + feature_schema.json (7 键)                  + feature_schema.json (5 键, 硬编码 8 通道)
      + feature_engineering_summary.csv             (并预拷贝 data/processed 基准文件)
                │                                              │
                └──────────────────┬───────────────────────────┘
                                   ▼
                  data/processed/   (N,23,8) + (N,184) + y + metadata + schema
                                   │
        ┌──────────────────────────┼───────────────────────────────┐
        │ 只读 QC                   │ 训练/评估                      │ 结果级 QC
        ▼                          ▼                               ▼
 analysis/data_QC.py        workflows/training/train.py                                analysis/collect_results.py
 11 个检测模块:             ├─ validate_feature_schema               → summary/metrics_tables/
  sample_size              ├─ prepare_split_data                    all_experiments.csv
  kde y (CV带宽)           │   → src/input_control/                       │
  ambiguous_bases          │     cell_line_division.divide_data     ├─ analysis/anomaly_treatment.py
  monomorphic              │     single / all(LOCO|各系独立) / mixed │   ├─ 实验级: ΔR2 与 ΔRMSE 同号
  gc_content               │   → create_split_indices(seed=42)      │   └─ 数据级: |Weight| > 10.0
  length_consistency       │     0.70/0.15/0.15, floor 余数入 test └─ analysis/data/validation.py
  _classify_channels       ├─ prepare_model_data                         同 (split,cell,model,seed)
  length_alignment (QC-A)  │   → cell_environment_combination           配对 ΔR2/ΔRMSE 同号标记
  zero_annotation (QC-B)   │     .prepare_train_valid_test             (只标记, 不删除)
  epigenetic_gating(70%)   │     create_channel_mask → 未选通道置 0
  detect_outliers_iforest  │     flatten (N,184) / 保持 (N,23,C)
        │                  └─ build_train_kwargs (use_scaler 默认 False)
        ▼                          │
  data/data_report/                ▼
   quality_report.md        模型 train()  (src/{linear_regression,xgboost,mlp,cnn,transformer})
   qc_summary.json           └─ 可选 StandardScaler: fit on TRAIN only
   outliers_detailed_report.csv      → transform valid/test
   target_efficiency_kde.png   └─ {run}/{model}_info.txt / _metrics.json /
   gc_content_kde.png              _predictions.csv / (linear)_weights.csv …
        │                          │
        └──► 仅展示/建议,           └──► workflows/training/data_digging.py 网格 (1346 个 run 实测)
             不修改任何数据             └─► workflows/prediction/predict.py: mixed 10 折 CV → ultimate/ 赛道二_results.csv
```

---

## 6.5 与文档/注释不一致之处

1. **`analysis/data_QC.py:5` 声称「供 7 步交互式向导 (GUI/CLI) 第二步调用」**：`app/desktop/main_wizard.py` 第 2 步是「选择已测量数据与待预测基因组」（`:146`），全文件不含 `qc`/`data_QC`；真实调用方是 `app/backend/crispr_workspace/qc_service.py:116-133`（HTTP 后端）。另有 `app/backend/crispr_workspace/analysis.py:22` 处名为 `qc` 的任务，但 `analysis/pipeline.py:133-134` 对它是空操作。
2. **`core/features/engineering/feature_engineering.py:99-115` 的输出示例已过期**：docstring 写 `hct116_23x7.csv`、`hct116_161.csv`、`hct116_features_23x7.npy`、`hct116_features_161.npy`（7 通道 / 161 维）；同一文件 `:145-152` 的注释与全部代码逻辑、`data/metadata/feature_config.json`、`data/processed/feature_schema.json`、实测 `.npy` 均为 **8 通道 / 184 维**。161 维在仓库中的真实来源是**线性回归剔除 23 个 `_T` 列后的输入**（`core/models/linear/linear_regression.py:468-488`）。
3. **`analysis/data_QC.py:12` 声称报告含「第 1,3,4,5,6,7,8 项」**：实际 `build_markdown` 写出 `## 1,3,4,5,6,7,8,9,10` —— 第 2 项确实缺席（与 docstring 一致），但多出 9/10 两节（补充 QC-A/QC-B），docstring 未提及。
4. **`core/data/splitting/cell_line_division.py:5` 声称「彻底去除写死的 4 大细胞系」**：`discover_available_cell_lines` 在目录为空时仍硬编码返回 `["hct116","hek293t","hela","hl60"]`（`:72`）。
5. **`cell_line_division` 内部 schema 默认值自相矛盾**：`load_feature_schema` 的 `default_schema` 用 `channel_count=8 / feature_count=184`（`:30-31`），但 `get_feature_file_paths`（`:78`）与 `validate_cell_line_dataset`（`:100`）的 `.get("channel_count", 7)` 回退默认值是 **7**；若 schema 缺 `channel_count`，会去找不存在的 `*_features_23x7.npy`。
6. **`load_feature_schema` 是「读」函数却会写盘**：文件缺失、0 字节或 JSON 损坏时**自动写入** `feature_schema.json`（`cell_line_division.py:37-41`、`:46-50`）。与该模块「只读发现」的设计叙述相悖，也会在只读数据目录上抛 `PermissionError`。
7. **QC 的 70% 门禁文案承诺了未实现的强制行为**：`data_QC.py:1084-1087` 与 `:1428-1431` 称「系统将在特征工程阶段**强制禁用**该环境通道参与消融实验与训练，或必须降级为 Zero-Masking 模式」。`blocked_channels` 在仓库内**无任何消费方**（仅 `app/frontend/.../QcDashboard.tsx:21` 读 `qc_pass`），`core/features/engineering/feature_engineering.py` / `cell_environment_combination.py` / `workflows/training/train.py` 均不读 QC 结果；`Zero-Masking` 在代码中不存在实现，只有通道选择掩码。
8. **阈值没有集中管理**：`analysis/config.py:1` 声明「阈值不得散落各模块」，`QCConfig`（`:41-47`）给出 `strict_complete_gate=70.0`、`environment_missing_rate_limit=0.30`、`ambiguous_detection_only=True`；但 `analysis/data_QC.py` 未 import 该模块，70% 是**内联字面量**（`:1056`），`0.30` 缺失率上限与 `Eligible/Limited/Ineligible` 三态标签在全仓库**均无实现**（`Ineligible` 仅出现在 `analysis/reports/markdown_report.py:162` 的说明文字中）。
9. **两套结果级 QC 的配对规则不一致**：`analysis/data/validation.py:1-6` 明示「mixed 多 seed 绝不跨 seed 比较 (paired cohort 原则)」，其基线键含 `seed`（`:38-40`）；`analysis/anomaly_treatment.py:135-136` 的 `aggregate_metrics` 按 `(split_type, cell_line, model, environment)` 求均值、**丢弃 `random_seed`**，再据此比较 ΔR²/ΔRMSE（`:162-180`）。两者对同一批 mixed 结果可能给出不同判定。
10. **`workflow_config.json` 只有文档与前端文案，没有代码**：`docs/frontend_architecture.md:61`、`app/frontend/src/views/WorkspaceView.tsx:104,106` 描述「决策写 workflow_config.json，不写入原始数据」；后端仅有 `project.py:64` 的 `config_versions.workflow_config = None` 占位，**无任何写入函数**。当前唯一可验证的「决策落盘」是 QC 会话 manifest 与 `create_from_qc` 的指纹一致性校验（`qc_service.py:97-113`、`project.py:113-131`）。
11. **`backend_runner.convert_raw_csv_to_npy` 的目标列兜底会伪造标签**：目标列匹配失败时用 `np.random.uniform(0.5, 0.9, n)` 作为 `y`（`app/desktop/backend_runner.py:85`），仅打印成功信息，不告警、不中止。
12. **两条编码路径的容错策略相反**：`src/feature_engineering.encode_sgrna` 遇到非 ACGT 立即 `ValueError`（`:411-418`），而 `app/desktop/backend_runner.convert_raw_csv_to_npy` 补 `N` 并留下全零列（`:64-69`）——同一份含 `N` 的 CSV 在两条路径下行为完全不同（前者不可处理，后者静默通过）。
13. **`feature_engineering.py` 的模块输出示例称 7 通道，而 `app/desktop/backend_runner` 的 schema 硬编码 8 通道**；同时后者把 `sequence_length` 取自向导 `seq_len`（`:110`），却把张量固定为 23（`:60`），二者可能不一致。
14. **`app/desktop/backend_runner.py` 会覆盖用户数据来源**：`run_feature_engineering_step` 先把仓库基准 `data/processed/*.*` 拷入用户输出目录（`:100-105`），并对已存在同名 `{cl}_features_23x8.npy` 的细胞系**跳过转换**（`:130-133`）。因此当用户细胞系名与基准 4 系同名（默认向导值即为这 4 系，`main_wizard.py:32`）时，用户上传的数据可能被基准数据静默替换。
15. **`create_split_indices` 的 test 比例由 `floor` 余数决定**：`test_fraction` 参数只参与 `validate_split_fractions` 的和校验（`cell_line_division.py:155`），不参与 size 计算；实测 4239 → 2967/635/637（而非 635.85 的取整值）。
16. **`create_split_indices` 对 `test_fraction=0.0` 无豁免**：LOCO 分支传入 `test_fraction=0.0`（`cell_line_division.py:225`），而 `create_split_indices` 第一行即调用 `validate_split_fractions`（`:155`），后者要求所有 fraction > 0（`:91-92`）→ **LOCO 分支在当前代码下必然抛 `ValueError`**，属不可达路径。
17. **`data_QC` 的 `--data auto` 默认指向仓库自带 `data/raw`**（`_demo_data`，`:1666-1676`），而非用户数据；直接跑 CLI 会对仓库基准数据出报告。
18. **QC 离群检测的序列 One-Hot 只用 A/G/C**（`analysis/data_QC.py:1112-1114`，T 被省略），与模型输入 4 通道不一致；且 `StandardScaler` 在**全体样本**上拟合（`:1137`），若把该 `anomaly_score` 当模型特征会引入跨 train/test 的信息泄漏（当前仅作 QC 报告，不进入训练）。
19. **`outliers_detailed_report.csv` 的 `sample_index` 实为文件行号**（含表头偏移 +2，`:482`、`:1168`），并非 0-based 样本下标；列名与语义不符。
20. **QC 报告只统计「序列长度」而不校验 23**：`recommended_length_L` 取长度众数（`:722-723`），若数据整体是 20nt，报告会推荐 20nt，而下游 `encode_sgrna` 硬要求 23（`core/features/engineering/feature_engineering.py:346`）。

---

## 本节自检

以下条目均在本节编写时**逐条回到源码核对**（含行号），非依据 README/docstring：

- [x] **序列编码完整 A/C/G/T** — 是。`DEFAULT_SEQUENCE_CHANNELS = ["A","C","G","T"]`（`core/features/engineering/feature_engineering.py:147-152`），`encode_sgrna` 对非 ACGT 抛错（`:411-418`）；`data/metadata/feature_config.json:2-7` 与 `feature_schema.json:3-8` 一致；`app/desktop/backend_runner.py:61` 亦为 A0/C1/G2/T3。**但** QC 侧离群向量只用 A/G/C（`analysis/data_QC.py:1112-1114`），已在 §4.2/§6.5 标注。
- [x] **通道顺序** — 是。`["A","C","G","T","CTCF","Dnase","H3K4me3","RRBS"]`，来自 config 中 `sequence_channels` + `environment_features` 数组顺序（`feature_engineering.get_channel_specs:757-806`）；实测 schema 与全部 `*_info.txt` 一致。
- [x] **序列长度 = 23** — 是。常量 `SEQUENCE_LENGTH = 23`（`:132`）、`validate_sequence` 强校验（`:346`）、schema `sequence_length: 23`、实测张量 `(N,23,C)`。
- [x] **通道数 = 8、特征数 = 184** — 是。config 4 序列 + 4 环境；实测 `(N,23,8)`、`(N,184)`；`feature_engineering_summary.csv` 记录 `channel_count=8, feature_count=184`。线性回归另剔除 23 个 `_T` 列 → 161（`linear_regression.py:468-488`）。
- [x] **去重** — 是，但**仅** `remove_duplicate_rows` 的整行 `duplicated(keep="first")`（`:1067-1126`），仅存在于特征工程 CLI 路径；QC 与向导路径均无去重（实测 hek293t 4566→2333）。
- [x] **标准化 / scaler** — 数据管线内**不存在**；仅模型训练侧 `--use-scaler`（默认 False）且在 train 上 `fit`、valid/test 上 `transform`（`mlp.py:555-563`、`cnn.py:640-650`、`linear_regression.py:159-162/275-278`）。实测该批次全部 `use_scaler: False`。
- [x] **缺失 / 非标准碱基处理** — 特征工程：缺失值 `ValueError` 中止（`:1187-1212`），非 ACGT `ValueError`（`:411-418`）；向导路径：静默补 `N`/补零/随机标签（`backend_runner.py:64-85`）；QC：只检测不处理（`detect_ambiguous_bases:582-612`），`analysis/config.py:47 ambiguous_detection_only=True` 未被 QC 引擎引用。
- [x] **QC 阈值** — 70% 门禁 `70.0`（`data_QC.py:1056`，内联）；`contamination=0.01`、`random_state=42`（`:59-60`）；KDE 带宽 CV 5 折 / 子抽样 2000 / 网格 24 点 / 搜索区间 `[0.05σ, 1.5σ]`（`:57-58`、`:178-190`）；离群归因 `3σ` 与 `y∉[0,1]`（`:360-365`）；通道类型判定 `0.6*tot` 与 `0.5*tot`（`:796-801`）；结果级 `|Weight| > 10.0`（`anomaly_treatment.py:35`）与 `sign_tol=1e-6`（`:36`）/ `tol=1e-9`（`validation.py:14`）。
- [x] **离群方法** — IsolationForest（`n_jobs=-1`），特征 = 23×3(A/G/C) + 23×n_epi，中位数填充 + `StandardScaler`（全体拟合），`decision_function` 作分值（`data_QC.py:1134-1147`）。
- [x] **划分规则** — `single` 系内随机、`all` 分 LOCO（当前抛错）与各系独立后合并、`mixed` 先合并再随机；比例 0.70/0.15/0.15，`floor` 取整、余数归 test；seed 默认 42，mixed 网格用 42/43/44/45，non-mixed 强制 42（`cell_line_division.py:154-273`、`workflows/training/data_digging.py:59/275`）；LOCO 内部硬编码 0.85/0.15 且因 `test_fraction=0.0` 触发 `validate_split_fractions` 报错（`:225` + `:91-92` + `:155`）。
- [x] **seed** — 见上；`workflows/training/train.py:31/622`、`cell_line_division.py:154`、`workflows/training/data_digging.py:59`、`data_QC.py:60`、`workflows/prediction/predict.py:748` 均为可追溯的具体值。
- [x] **CLI 存在性** — `core/features/engineering/feature_engineering.py`（3 参数）、`analysis/data_QC.py`（3 参数）、`analysis/anomaly_treatment.py`（7 参数）**均有 argparse**；`core/data/splitting/cell_line_division.py`、`core/features/channels/cell_environment_combination.py`、`analysis/data/validation.py` **均无 argparse**（后者仅 `if __name__ == "__main__"` 自测块位于 `cell_environment_combination.py:1765-1908`）。
- [x] **程序 Status** — `core/features/engineering/feature_engineering.py` = Uncertain（CLI 可达、产出仓库数据，但运行时无 import）；`cell_line_division.py` / `cell_environment_combination.py` / `data_QC.py` / `anomaly_treatment.py` / `data/validation.py` / `app/desktop/backend_runner.py` = Active（均给出调用方与行号）；`data/candidate/todo_data.CSV` = Unused（无代码引用）。


---

# 7. 模型训练

> 文档范围：`workflows/training/train.py`（733 行）+ `src/{linear_regression,xgboost,mlp,cnn,transformer}/*.py` + `core/xai/importance/xai_importance.py`，
> 以及调用方 `workflows/training/data_digging.py` / `workflows/prediction/predict.py` / `app/backend/crispr_workspace/training.py`。
> 所有事实均来自实际源码，标注 `path:line`。**Status: 已完成**（仅阅读，未修改任何仓库文件）。

## 7.1 训练总入口 workflows/training/train.py (CLI→流程)

`workflows/training/train.py` 是"单次实验"的唯一统一入口：一次进程 = 一个 (model, split_type, environment, cell_line) 组合。
核心职责是**编排**（取 schema → 切分 → 环境通道裁剪 → 组装 kwargs → 动态 import 模型 → 调用模型 `train()`），
本身不实现任何训练算法，也不自己拟合 scaler。

### 7.1.1 顶部常量

| 常量 | 值 | 位置 |
|---|---|---|
| `DEFAULT_DATA_DIR` | `data/processed` | workflows/training/train.py:26 |
| `DEFAULT_MODEL_DIR` / `DEFAULT_RESULTS_DIR` / `DEFAULT_LOGS_DIR` | `models` / `results` / `logs` | workflows/training/train.py:27-29 |
| `DEFAULT_BATCH_NAME` | `default` | workflows/training/train.py:30 |
| `DEFAULT_RANDOM_SEED` | `42` | workflows/training/train.py:31 |
| `DEFAULT_TRAIN_RATIO` / `VALID` / `TEST` | `0.70` / `0.15` / `0.15` | workflows/training/train.py:33-35 |
| `ALL_MODELS` | `["linear","xgboost","mlp","cnn","transformer"]` | workflows/training/train.py:37-43 |
| `VALID_SPLIT_TYPES` | `["single","all","mixed"]` | workflows/training/train.py:45-49 |
| `MODEL_MODULES` | linear/linear_regression → `src.linear_regression.linear_regression`；xgboost → `src.xgboost.xgboost`；mlp → `src.mlp.mlp`；cnn → `src.cnn.cnn`；transformer → `src.transformer.transformer` | workflows/training/train.py:56-63 |

### 7.1.2 CLI 参数表（`parse_args`, workflows/training/train.py:599-644）

| 参数 | 类型/choices | 默认值 | 说明 |
|---|---|---|---|
| `--model` | 必填, choices=ALL_MODELS | — | 模型名 |
| `--model-module` | str | `None` | 覆盖 `MODEL_MODULES` 的模块路径 |
| `--split-type` | 必填, choices=VALID_SPLIT_TYPES | — | `single`/`all`/`mixed` |
| `--cell-line` | str | `None` | 单细胞系 或 all 模式的留出细胞系 |
| `--cell-lines` | nargs+ | `None` | 多细胞系列表 |
| `--environment` | 必填 str | — | 环境组合名，如 `sequence_ctcf_dnase`、`all` |
| `--data-dir` | str | `data/processed` | 需含 `feature_schema.json` |
| `--batch-name` | str | `default` | 空/`.`/`none`/`flat` → 不建二级目录 (workflows/training/train.py:185-189) |
| `--run-name` | str | `None` | 缺省则由 `generate_run_name` 生成 |
| `--model-dir` / `--results-dir` / `--logs-dir` | str | `models` / `results` / `logs` | 输出根 |
| `--train-ratio` / `--valid-ratio` / `--test-ratio` | float | `0.70` / `0.15` / `0.15` | 三者之和必须 = 1 (workflows/training/train.py:223-225) |
| `--seed` | int | `42` | 透传给模型 `train(random_seed=/seed=)` |
| `--use-scaler` | store_true | `False` | 仅传标志，**workflows/training/train.py 不拟合 scaler** |
| `--epochs` | int | `100` | torch 模型 |
| `--batch-size` | int | `64` | torch 模型 |
| `--learning-rate` | float | `1e-3` | torch 模型 |
| `--dropout` | float | `0.2` | MLP/CNN/Transformer |
| `--weight-decay` | float | `0.0` | Adam 的 weight_decay |
| `--patience` | int | `20` | 早停耐心 |
| `--min-delta` | float | `1e-6` | 早停最小改善 |
| `--hidden-dim1` / `--hidden-dim2` | int | `128` / `64` | MLP 隐层（CNN/XGB 不消费） |
| `--conv-channels1` / `--conv-channels2` | int | `32` / `64` | **写了 config 但无模型消费**（见 10 节） |
| `--sequence-kernel` | choices=[3,5,7] | `3` | CNN 序列分支核（=cnn33/53/73） |
| `--environment-kernel` | choices=[3,5,7] | `3` | CNN 环境分支核（调用方恒传 3） |
| `--device` | str | `None` | `None` → `cuda` if available else `cpu` |

### 7.1.3 主流程（`run_one_experiment`, workflows/training/train.py:441-592）

1. `sanitize_name` 归一化 model/split/environment（小写、空格与斜杠→`_`，workflows/training/train.py:70-74）。
2. `run_name` 缺省 → `generate_run_name`（workflows/training/train.py:480-486）。
3. `validate_feature_schema(data_dir)` 读取并校验 `feature_schema.json` 必含
   `sequence_length / channel_count / channel_names`（workflows/training/train.py:92-105）。
4. `load_model_train_function` 用 `importlib.import_module` 动态导入并取出模块级 `train`（workflows/training/train.py:112-131）。
5. `prepare_split_data` → `src.input_control.cell_line_division.divide_data(...)`，
   传 `train_fraction/validation_fraction/test_fraction/random_seed`（workflows/training/train.py:232-252）。
6. `validate_split_result` 校验 `X_{train,valid,test}_3d` 与 `y_*` 存在、3D、样本数一致（workflows/training/train.py:259-284）。
7. `prepare_model_data` → `src.input_control.cell_environment_combination.prepare_train_valid_test(
   split_data, schema, combination=environment, model_type=model_name)`；
   对 2D 模型走 `flatten_features`（(N,L,C)→(N,L*C)），对 3D 模型保持 (N,L,C)
   （cell_environment_combination.py:1295-1347、1243-1266、172-182）。
8. `validate_model_input_shape`：`{linear, linear_regression, xgboost, mlp}` 要求 2D，
   `{cnn, transformer}` 要求 3D（workflows/training/train.py:329-343）。
9. `build_feature_names`（workflows/training/train.py:306-322）：2D 时为 `pos{1..L}_{channel}`（按 channel_names 内层循环），
   长度与 `X.shape[1]` 不符则退化为 `feature_{i}`；3D 时直接返回 `channel_names`。
10. 组装 `config`（workflows/training/train.py:520-555）：run_name/model/model_module/split_type/cell_line(s)/environment/
    combination/selected_environments/environment_count/random_seed/三个 ratio/sequence_length/channel_count/
    channel_names/三个 input_shape/use_scaler/sequence_kernel/environment_kernel/epochs/batch_size/
    learning_rate/hidden_dim1/hidden_dim2/conv_channels1/conv_channels2/dropout/weight_decay/patience/min_delta。
11. `build_train_kwargs`（workflows/training/train.py:350-434）按被调 `train()` 的签名过滤：若模型 `train()` 有 `**kwargs`
    则整体透传；否则只保留签名中存在的键，并强制要求 `X_train,y_train,X_test,y_test` 四个核心键
    （workflows/training/train.py:429-432）。别名同时提供：`model_dir/model_dir_root`、`result_dir/results_dir`、
    `log_dir/logs_dir`、`random_seed/seed`、`sequence_kernel(_size)`、`environment_kernel(_size)`。
12. `result = train_function(**train_kwargs)`，返回 `{"run_name","config","result"}`（workflows/training/train.py:591-592）。

### 7.1.4 scaler 的 fit-on-train 证据（workflows/training/train.py 只传标志，不拟合）

- `workflows/training/train.py` 全文没有 `StandardScaler`/`fit_transform` 调用；仅把 `use_scaler` 放进 config
  （workflows/training/train.py:541）与 kwargs（workflows/training/train.py:402、572），最终由 `execute_args` 传 `use_scaler=args.use_scaler`
  （workflows/training/train.py:703）。
- 拟合点全部在模型内部，且**只在训练集上 fit**、对 valid/test 只 `transform`：
  - Linear: `linear_regression.py:159-163`（`self.scaler.fit_transform(X_train)`，predict 时 transform，251-284）。
  - MLP: `mlp.py:558-563`（`fit_transform(X_train)` → `transform(X_valid)` → `transform(X_test)`）。
  - CNN: `cnn.py:643-650`（reshape(-1,C) 后 fit，train 只 fit 一次）。
  - Transformer: `transformer.py:582-589`（同上）。
  - XGBoost: **不实现 scaler**，`train()` 形参 `use_scaler`（xgboost.py:522）在函数体内从未被引用。

### 7.1.5 目录与 run_name 约定

- 批次目录：`build_batch_directories` 生成 `models/<batch>`、`results/<batch>`、`logs/<batch>`
  （workflows/training/train.py:178-200）；batch 为空或 `./none/flat` 时直接用根目录。
- 单实验子目录再由各模型 `train()` 拼 `os.path.join(<root>, run_name)`（如 linear_regression.py:699-705）。
- `generate_run_name`（workflows/training/train.py:156-171）：
  - `single` → `single_{cell_line}_{model}_{environment}_{YYYYmmdd_HHMMSS}`
  - `all` → `all_{model}_{environment}_heldout_{cell_line}_{YYYYmmdd_HHMMSS}`
  - `mixed` → `mixed_{model}_{environment}_{YYYYmmdd_HHMMSS}`
- 实际批量运行时调用方**显式传 `--run-name`**（workflows/training/data_digging.py:287），因此真实实验目录名不带时间戳，
  CNN 额外带 `_kernel_{k}`（workflows/training/data_digging.py:178-179）。仓库实测目录如
  `results/batches/batch_20260909_full/all_cnn_all_heldout_hct116_kernel_3/`。

## 7.2 五模型并行/分发机制

### 7.2.1 模型名 → 模块映射（唯一权威表）

| model 名 | 模块 | 模块内入口 |
|---|---|---|
| `linear` / `linear_regression` | `src.linear_regression.linear_regression` | `train()` (linear_regression.py:673) |
| `xgboost` | `src.xgboost.xgboost` | `train()` (xgboost.py:509) |
| `mlp` | `src.mlp.mlp` | `train()` (mlp.py:481) |
| `cnn` | `src.cnn.cnn` | `train()` (cnn.py:498) |
| `transformer` | `src.transformer.transformer` | `train()` (transformer.py:504) |

映射见 workflows/training/train.py:56-63；`load_model_train_function` 只要求模块暴露 `train` 属性（workflows/training/train.py:127-131）。

### 7.2.2 workflows/training/data_digging.py（Training Scope 网格）→ 子进程调用 workflows/training/train.py

- 常量：`MODELS=[linear,xgboost,mlp,transformer]`、`CNN_MODELS=[cnn]`、`CELL_LINES=[hct116,hek293t,hela,hl60]`、
  `MIXED_SEEDS=[42,43,44,45]`、`CNN_KERNELS=[3,5,7]`（workflows/training/data_digging.py:55-60）。
- `generate_experiments`（workflows/training/data_digging.py:125-164）：非 CNN 模型 × environment × {single(4 cell)、
  all(4 留一)、mixed(4 seed)}；CNN 再额外 × 3 个卷积核（153-162）。
- `build_run_name`（167-180）与 workflows/training/train.py 规则一致，但 mixed 带 `_seed_{s}`、CNN 带 `_kernel_{k}`；
  `build_command`（250-321）固定 `--run-name`，CNN 才追加
  `--sequence-kernel k --environment-kernel 3`（313），`--use-scaler` 可选（318-319）。
- 执行方式三选一：`subprocess.run([sys.executable, workflows/training/train.py, ...])`（324-338）；
  `--in-process` 时改写 `sys.argv` 后 `import train; train.main()`（341-362）；
  `--workers>1` 用 `ThreadPoolExecutor` 并发跑子进程（498-507），可选
  `--threads-per-worker` 封顶 OMP/MKL 线程（365-379）。
- 断点续跑：扫描 `results/<batch>/*` 的 `*info*.txt` 解析 model/environment/split/cell/seed/kernel 作为
  完成键（183-247），已完成实验跳过（456、489-514）。

### 7.2.3 workflows/prediction/predict.py（Ultimate mixed 十折）**不调用 workflows/training/train.py**

`workflows/prediction/predict.py` 直接 `import` 模型类自行训练与预测，不复用 workflows/training/train.py 的 CLI/编排：

- `_build_torch_model`（workflows/prediction/predict.py:288-325）：`from src.mlp.mlp import MLPModel`（292）、
  `from src.cnn.cnn import CNNModel`（304）、`from src.transformer.transformer import TransformerModel`（315）；
  CNN 的序列核由 kind 名第 4 个字符解析 `seq_k = int(kind[3])`（303），环境核固定 3（309）。
- `_fit_model`（365-392）：lr → `LinearRegressionModel(use_scaler=cfg)`（369-372）；
  xgboost → 裸 `xgb.XGBRegressor(n_estimators=100,max_depth=3,lr=0.05,subsample=0.8,colsample=0.8,
  reg:squarederror,n_jobs=-1,random_state=seed)`（376-387）；torch → `_fit_torch_model`。
- `_fit_torch_model`（328-351）：`AdamW(lr=cfg.get("lr",1e-3), weight_decay=0.0)`、`MSELoss`、
  `DataLoader(batch_size=256, shuffle=True)`、无验证集/无早停，固定跑 `--ultimate-epochs`（默认 15）。
- `_run_ultimate_cv`（409-423）：`KFold(n_splits=10, shuffle=True, random_state=42)`，
  选 `ULTIMATE_GRIDS`（68-92）中最优 CV R² 配置，再全量重训并保存到
  `results/<batch>/summary/ultimate/`（476-558）。
- `ULTIMATE_MODEL_ORDER=["lr","xgboost","mlp","cnn33","cnn53","cnn73","transformer"]`（49），
  `cnn` 自动展开为 cnn33/cnn53/cnn73（268-285）。

### 7.2.4 GUI/后端（app/backend/crispr_workspace/training.py）

- `TrainingConfig`（37-88）只做 CLI 编排，明确"绝不 import/修改训练代码"（1-10）；
  `_dig_command`（137-167）拼 `workflows/training/data_digging.py` 参数（含 `--conv-channels1/2`，154），
  `_predict_command`（169-187）拼 `workflows/prediction/predict.py` 参数；`LocalRuntime.submit` 用子进程
  `start_new_session=True` 并落盘 `training_status.json`/`done.rc`（242-281）。
- `app/desktop/main_wizard.py` 的 XAI 勾选框（324/332/340/348）仅存于 `xai_vars`，**不产生任何 CLI 参数**。

## 7.3 Linear Regression（core/models/linear/linear_regression.py，852 行）

### class `LinearRegressionModel` (linear_regression.py:56)

| 成员 | 说明 | 位置 |
|---|---|---|
| `__init__(use_scaler=False, pinv_rcond=1e-15)` | 保存开关与伪逆截断阈值；状态：weights/SE/t/p/FDR/significance、singular_values/rank/condition_number | 71-109 |
| `fit(X_train, y_train)` | float64 校验（2D、有限、样本数一致）→ 可选 scaler → 末列加 1 构造 `X_bias=[X,1]` → SVD 诊断 → `weights = pinv(X_bias, rcond) @ y` | 115-245 |
| `predict(X)` | 校验特征数一致、有限 → 可选 scaler.transform → `X_bias @ weights` | 251-284 |
| `save(model_dir)` | 写 `linear_regression_model.pkl`（含权重与全部统计量）、`linear_regression_scaler.pkl`（scaler 为 None 也写）、`linear_regression_diagnostics.json` | 290-345 |
| `load(model_dir)` | 读回 pkl 与 scaler pkl | 351-388 |

**求解器与统计推断（核心）**
- OLS 由 Moore–Penrose 伪逆解析求解：`X_pinv = np.linalg.pinv(X_bias, rcond=1e-15)`，
  `weights = (X_pinv @ y_train)`（linear_regression.py:194-195）。
- SVD 诊断：`np.linalg.svd(X_bias, compute_uv=False)`；`rank = #{σ > rcond*σ_max}`；
  `condition_number = σ_max / σ_min_nonzero`（176-188）。
- 自由度 `dof = max(1, N - rank)`，`mse_resid = SSR/dof`（205-206）。
- `Var(w_i) = mse_resid * Σ_j X_pinv[i,j]^2`（210），下限截断 1e-15；`SE=sqrt`，`t=w/SE`（211-214）。
- 双尾 p：`p = 2*(1 - scipy.stats.t.cdf(|t|, df=dof))`（217）。
- FDR：Benjamini–Hochberg 手写倒序累积最小 q 值（220-232）；显著性符号
  `*** <0.001`、`** <0.01`、`* <0.05`、`.` <0.1（235-240）。

### 模块级函数

| 函数 | 功能 | 位置 |
|---|---|---|
| `calculate_metrics(y_true,y_pred)` | MSE/RMSE/MAE/R2/Pearson/Spearman（R2 在 ss_tot≈0 时 NaN；相关系数在零方差时 NaN） | 395-441 |
| `generate_default_feature_names(n)` | `Feature_1..n` + `"Bias"` | 448-454 |
| `select_non_t_reference_features(X, names)` | 剔除所有以 `_T` 结尾的列（哑变量陷阱防护，T 为基准），返回 `(X_sub, names_sub, keep_indices)`；无 `_T` 列时原样返回且 keep=[] | 468-488 |
| `create_logger(log_dir)` | `training.log`，文件 + 控制台 handler | 491-509 |
| `save_predictions` | `y_true,y_pred,error` CSV | 516-522 |
| `save_weights(model, names, out)` | 装配 `Feature/Weight/Std_Error/t_stat/p_value/p_adj_fdr/Significance`，随后强制 `export_feature_table("linear", ...)` 白名单清洗后写 CSV | 529-570 |
| `save_linear_diagnostics(model, out)` | feature_count/numerical_rank/condition_number/pinv_rcond/singular_values | 577-591 |
| `save_results(...)` | 写 metrics/validation_metrics/predictions/weights/diagnostics/info | 598-666 |
| `train(...)` | 统一入口 | 673-816 |

### 输入/输出/训练流程（`train`, linear_regression.py:673-816）

- 输入：`X_train,y_train,X_test,y_test`（2D，必需）、`X_valid,y_valid`、`feature_names`、`run_name`、
  三个目录、`config`、`use_scaler=False`、`pinv_rcond=1e-15`、`random_seed=None`（**未被使用**，697）。
- 流程：建三个 run 目录 → logger → float64 转换 → 维度/样本数校验 →
  **若 `len(feature_names)==X.shape[1]` 则剔除 `_T` 列并对 X_test/X_valid 施加同一 `keep_indices`**
  （735-746；实测 184 → 161）→ `feature_names` 末尾补 `"Bias"`（748-758）→
  `LinearRegressionModel(use_scaler, pinv_rcond).fit()` → 统计显著特征计数日志（771-774）→
  valid 预测与指标（含 `linear_regression_validation_predictions.csv`，779-783）→ test 预测与指标 →
  `model.save()` + `save_results()` → 返回 model/metrics/predictions/model_paths/result_paths/log_path。
- **`_T` 剔除只在线性模型发生**：XGBoost/MLP 保留 184 列（实测 `input_shape_train: [2967,184]`），
  Linear 为 161 列（实测 weights CSV 163 行 = 161 特征 + Bias + 表头）。

## 7.4 XGBoost（core/models/xgboost/xgboost.py，694 行）

### 默认超参 `DEFAULT_PARAMS` (xgboost.py:37-48)

| 参数 | 值 |
|---|---|
| `n_estimators` | 300 |
| `max_depth` | 5 |
| `learning_rate` | 0.05 |
| `subsample` | 0.8 |
| `colsample_bytree` | 0.8 |
| `min_child_weight` | 1 |
| `reg_alpha` / `reg_lambda` | 0.0 / 1.0 |
| `objective` / `eval_metric` | `reg:squarederror` / `rmse` |

> `workflows/training/train.py` 不传 `params`（`build_train_kwargs` 的 all_kwargs 无该键，workflows/training/train.py:384-421），
> 因此网格训练**恒用上表默认值**；只有 workflows/prediction/predict.py 的 Ultimate 路径另建 `n_estimators/max_depth` 网格（workflows/prediction/predict.py:70-73）。

### class `XGBoostModel` (xgboost.py:145)

| 成员 | 说明 | 位置 |
|---|---|---|
| `__init__(params=None, random_seed=42, n_jobs=-1, verbose=False, early_stopping_rounds=30)` | `DEFAULT_PARAMS.copy()` 后 update(params) | 146-167 |
| `_create_model(use_early_stopping)` | `xgb.XGBRegressor(**params, random_state, n_jobs, verbosity, [early_stopping_rounds])` | 169-178 |
| `fit(X_train,y_train,X_valid,y_valid)` | float32；有验证集时 `eval_set=[(train),(valid)]` 且启用早停；记录 `best_iteration/best_score/evals_result`；无验证集时 `best_iteration=n_estimators-1` | 180-231 |
| `predict(X)` / `save` / `load` | 预测；`xgboost_model.json` + `xgboost_config.json`（含 params/seed/best_iteration）；load 读回 config | 233-289 |

### XAI 导出 `get_feature_importance` (xgboost.py:296-371)

- `booster.get_score(importance_type=...)` 依次取 `gain/weight/cover`，按 `f{i}` 对齐到 `model.feature_count`
  （缺失补 0）（324-334）。
- TreeSHAP：`xgb.DMatrix(X_eval)` → `booster.predict(dmat, pred_contribs=True)[:, :-1]`（丢弃偏置列）
  （342-345）；`SHAP_mean = mean(|SHAP|)`，`SHAP_SNR = mean(|SHAP|) / (std(SHAP)+1e-12)`（347-353）。
- 白名单清洗后按 `XGB_Gain` 降序（362-371）。
- `X_eval` 由 `train()` 传 **测试集**（不足则训练集）（xgboost.py:606）。
- **无置换检验**：模块 docstring 明确"置换检验已移除"（16），全仓库 grep `permutation` 仅命中
  `core/xai/importance/xai_importance.py:44` 的禁用字段清单。

### 训练流程（`train`, xgboost.py:509-659）

float32 → 维度校验 → 有验证集才设 `effective_early_stopping=30`（572，CLI 的 patience/min_delta 对 XGB 无效）→
`XGBoostModel(...).fit()` → valid/test 指标 → `get_feature_importance` → config 合并
（model/input_dim/feature_count/random_seed/best_iteration/best_score，618-626）→ `model.save` + `save_results` → 返回。

## 7.5 MLP（core/models/mlp/mlp.py，801 行）

### 架构 `MLPModel` (mlp.py:95-127)

```
Linear(input_dim → hidden_dim1=128) → ReLU → Dropout(0.2)
→ Linear(128 → hidden_dim2=64)      → ReLU → Dropout(0.2)
→ Linear(64 → 1)
```
输入必须 2D (N, D)（124-127）；`input_dim` 由 `X_train.shape[1]` 决定（548），XGB 同样 184 维。

### XAI 辅助函数

| 函数 | 功能 | 位置 |
|---|---|---|
| `set_seed(seed=42)` | random/np/torch/cuda 种子 + cudnn deterministic | 55-63 |
| `evaluate_model` | 无梯度评估，返回 (平均 loss, y_true, y_pred) | 179-205 |
| `compute_integrated_gradients(model, X, device, steps=30)` | 原生 IG | 212-242 |
| `compute_mlp_robustness_importance(model, X_eval, feature_names, device)` | 组装白名单表 | 274-321 |

- **IG 细节**：baseline = `np.zeros_like(X)`（223）；`alphas = np.linspace(0,1,steps+1)`（227）；
  逐步点 `b + a*(x-b)`；对 `preds.sum()` 求 `torch.autograd.grad`；`avg_grads = mean(grads[:-1])`；
  `IG = (x - baseline) * avg_grads`（233-240）。**默认 steps=30，但 `compute_mlp_robustness_importance`
  调用时传 `steps=25`（mlp.py:290）**。
- **导出列**：`IG_Mean = mean|IG|`、`IG_SNR = mean|IG| / (std(IG)+1e-12)`、
  再 rename `IG_Mean→MLP_IG`（312-316），按 `MLP_IG` 降序（319）。

### 训练循环（`train`, mlp.py:481-765）

| 项 | 值 | 位置 |
|---|---|---|
| 精度 | float32 | 525-533 |
| scaler | `use_scaler=True` 时 train 上 `fit_transform`，valid/test 只 `transform` | 554-563 |
| device | `None` → `cuda` if available else `cpu` | 566-568 |
| loss | `nn.MSELoss()` | 579 |
| optimizer | `torch.optim.Adam(lr=learning_rate=1e-3, weight_decay=0.0)` | 580 |
| DataLoader | train `batch_size=64, shuffle=True, num_workers=0`；valid `shuffle=False` | 583-589 |
| epochs | 100（CLI 默认） | 600 |
| 早停 | `improvement = best_val_loss - val_loss > min_delta(1e-6)` 才更新 best；否则计数 +1；`epochs_without_improvement >= patience(20)` 触发 break | 631-650 |
| checkpoint | `copy.deepcopy(model.state_dict())` 保存最优，训练结束 `load_state_dict(best_state_dict)` | 636、653-655 |
| 日志 | epoch 1 / 每 10 / 最后 / best epoch | 641-646 |
| 无验证集 | 不早停，`best_epoch = epoch`（最后一次） | 656-657 |
| XAI 评估集 | `X_test`（非空）否则 `X_train` | 679-686 |
| 保存 | `mlp_model.pt`（state_dict+config）、`mlp_scaler.pkl`（若有）、`mlp_config.json` | 700-711 |

## 7.6 CNN（core/models/cnn/cnn.py，873 行）

### 架构 `CNNModel` (cnn.py:89-199) —— 双分支，逐层精确参数

构造形参（90-100）：`sequence_channels`、`environment_channels`、`sequence_kernel=3`、`environment_kernel=3`、
`sequence_filters=64`、`environment_filters=64`、`fusion_filters=128`、`dropout=0.2`。
**注意：`workflows/training/train.py --conv-channels1/2`（32/64）与这些 filters 无关，实际恒为 64/64/128。**

| 分支 | 层 | 输入 → 输出 | 位置 |
|---|---|---|---|
| 序列 | `Conv2d(1 → 64, kernel=(ks, C_seq), padding=(ks//2, 0))` | (N,1,23,C_seq) → (N,64,23,1) | 121-126 |
| 序列 | `BatchNorm2d(64)` → `ReLU` | 同 shape | 127-128 |
| 序列 | `Conv2d(64 → 64, kernel=(ks,1), padding=(ks//2,0))` | (N,64,23,1) → (N,64,23,1) | 129-134 |
| 序列 | `BatchNorm2d(64)` → `ReLU` → `AdaptiveAvgPool2d((1,1))` → reshape | → (N,64) | 135-138, 187 |
| 环境 | `Conv2d(1 → 64, kernel=(ke, C_env), padding=(ke//2,0))` → BN(`64`) → ReLU | (N,1,23,C_env) → (N,64,23,1) | 142-150 |
| 环境 | `Conv2d(64 → 64, kernel=(ke,1), padding=(ke//2,0))` → BN → ReLU → `AdaptiveAvgPool2d((1,1))` | → (N,64) | 151-160, 194 |
| 环境缺省 | `environment_channels == 0` → `self.environment_branch = None` | — | 161-162 |
| 融合 | `Linear(64 + 64·[C_env>0] → 128)` → ReLU → Dropout(0.2) → `Linear(128→64)` → ReLU → Dropout(0.2) → `Linear(64→1)` | → (N,1) | 165-174 |

- `fusion_input = sequence_filters + (environment_filters if environment_channels>0 else 0)`（165），
  即**有环境分支 128 维，纯序列 64 维**。
- `forward`（176-199）：输入必须 (N, L, C)，`C == sequence_channels + environment_channels`；
  `seq_x = x[:, :, :C_seq].unsqueeze(1)`（186）；`env_x = x[:, :, C_seq:].unsqueeze(1)`（193）；
  `torch.cat([seq_feat, env_feat], dim=1)` → `fusion`（197-198）。
- 因为 padding 均为 `kernel//2`（same）且末端是 `AdaptiveAvgPool2d((1,1))`，
  **输出维度与 kernel 无关**，仅感受野不同。

### kernel 变体 cnn33 / cnn53 / cnn73

- 网格端：`CNN_KERNELS=[3,5,7]`（workflows/training/data_digging.py:60），`build_command` 对 CNN 追加
  `--sequence-kernel k --environment-kernel 3`（workflows/training/data_digging.py:312-313），run_name 加 `_kernel_{k}`
  （workflows/training/data_digging.py:178-179）。
- Ultimate 端：`cnn33→seq_k=3`、`cnn53→5`、`cnn73→7`，环境核固定 3（workflows/prediction/predict.py:301-311）。
- 因此三个变体 = **序列分支核 3/5/7 + 环境分支核 3**，其余（64/64/128、dropout 0.2、Adam、batch 64…）完全一致。

### 通道切分（train, cnn.py:563-637）

- 优先由 `config['channel_names']` 驱动（570-577）：`_NUCLEOTIDE_CHANNELS={"A","C","G","T"}`（565），
  `sequence_channels = #{name ∈ ACGT}`，环境通道按 schema 顺序记录绝对列号 `env_positions_abs`。
- 缺 schema 时回退 `sequence_channels=3` + `default_environment_order=['ctcf','dnase','h3k4me3','rrbs']`（564、579-581）。
- `config['selected_environments']`：`[]` → 纯序列（切片掉环境列，`environment_channels=0`，591-594）；
  子集 → `concat(seq列, 选中env列)` 并对 valid/test 同步（596-616）；`None` → 使用全部环境列（618-621）。
- 实测 `all` 环境：`input_shape_train [2967, 23, 8]`，即 C_seq=4 + C_env=4。

### 训练循环（cnn.py:689-745）

与 MLP 完全同构：`MSELoss`（670）、`Adam(lr=1e-3, weight_decay=0.0)`（671）、
train loader `batch_size=64, shuffle=True`（675）、valid `shuffle=False`（680）、epochs 100、
`improvement > min_delta(1e-6)` 更新 best（720-727）、`patience=20` 早停（736-738）、
`deepcopy(state_dict)` + 训练末恢复最佳（724、741-743）、每 10 epoch 打日志（729-734）。

### XAI：ISM 与 3D-IG

| 函数 | 功能 | 位置 |
|---|---|---|
| `compute_cnn_ism(model, X, device)` | 虚拟饱和突变 | 284-311 |
| `compute_cnn_integrated_gradients(model, X, device, steps=25)` | 3D 输入 IG | 314-343 |
| `compute_cnn_robustness_importance(model, X_eval, channel_names, device)` | 组装白名单表 | 346-397 |

- **ISM 逐位点/逐通道**：`for l in range(L): for c in range(C)`（L=23, C=全部通道，实测 8），
  突变规则 `X_mut[:,l,c] = np.where(X_mut[:,l,c] > 0, 0.0, 1.0)`（置零/置一翻转），
  记录 `|ŷ_mut − ŷ_base|`（300-307）；对样本求 mean/std → `(L,C)`（309-310）。
  **共 L×C = 184 次全量前向**，无批量并行。
- **CNN IG**：baseline 全零，`alphas=linspace(0,1,steps+1)`，`IG = (x-baseline)*mean(grads[:-1])`，
  返回 `mean|IG|` 与 `std(IG)`（325-343）；调用处 `steps=20`（366，函数默认 25）。
- 导出表：`Feature = f"{channel}_pos_{l}"`，附 `Position`、`Channel`；
  `ISM_SNR = ism_mean / (ism_std + 1e-12)`（363）；
  rename `ISM_Mean_Delta→CNN_ISM`、`IG_Mean→CNN_IG`（390-394）；按 `CNN_ISM` 降序（395）。
  **CNN 的 IG 标准差被丢弃（`_ig_std`），白名单无 CNN_IG_SNR**（366、34）。

## 7.7 Transformer（core/models/transformer/transformer.py，805 行）

### 结构（精确维度）

| 组件 | 定义 | 位置 |
|---|---|---|
| `PositionalEncoding(d_model=64, max_length=23)` | 经典正弦 PE：`pe[:,0::2]=sin(pos·div)`、`pe[:,1::2]=cos(...)`，`div=exp(arange(0,d,2)·(-ln10000/d))`；`forward` 返回 `x + pe[:, :L, :]`，超长报错 | 89-111 |
| `TransformerEncoderLayerWithAttn(d_model=64, nhead=4, dim_feedforward=128, dropout=0.2)` | **Pre-LN**：`norm1 → MultiheadAttention(need_weights=True, average_attn_weights=False) → 残差`；`norm2 → Linear(64→128) → GELU → Dropout → Linear(128→64) → 残差` | 118-144 |
| `TransformerModel(input_dim=C, max_sequence_length=23, d_model=64, nhead=4, num_layers=2, dim_feedforward=128, dropout=0.2)` | `input_projection = Linear(input_dim → 64)`；`position_encoding`；`layers = 2 × 上述 EncoderLayer`；`regressor = Linear(64→32) → GELU → Dropout(0.2) → Linear(32→1)` | 147-183 |
| `forward(x, return_attn=False)` | 输入 (N,L,C) → 投影 → PE → 逐层 → **mean pooling over L**（`x.mean(dim=1)`）→ regressor；`return_attn=True` 时额外返回**最后一层**注意力 `(N, nhead, L, L)` | 185-204 |

- 约束：`d_model % nhead == 0`（161-162）；`nhead=4, d_model=64` → head_dim=16。
- 通道名回退列表为 `["A","G","C","CTCF","Dnase","H3K4me3","RRBS"]`（572）——顺序与 schema 的
  `["A","C","G","T",...]` 不一致且缺 T，仅在 `feature_names` 长度不等于通道数时用于 3D 表命名（573-576）。

### 训练循环（transformer.py:627-683）

`MSELoss`（608）、`Adam(lr=1e-3, weight_decay=0.0)`（609）、batch 64 shuffle=True（613）、
epochs 100、`improvement > 1e-6` 更新 best（657-665）、`patience=20`（674-676）、
`deepcopy` + 恢复最佳（662、679-681）、每 10 epoch 日志（667-672）。
`feature_names` 若长度等于通道数则当作通道名（573-574）。

### 注意力与熵

| 函数 | 功能 | 位置 |
|---|---|---|
| `compute_transformer_attention_robustness(model, X, device)` | 返回 `(pos_attn_mean(L,), mean_entropy(L,), pos_attn_snr(L,))` | 289-318 |
| `compute_transformer_integrated_gradients(..., steps=20)` | 3D-IG 辅助实现，**当前未被调用、也不在白名单** | 321-350 |
| `compute_transformer_robustness_importance(model, X_eval, channel_names, device)` | 组装白名单表 | 353-403 |

- 取 `model(X, return_attn=True)` 得 `(N, nhead, L, L)` → 跨头平均 `(N,L,L)`（302-305）。
- `incoming_attn = mean(mean_head_attn, axis=1)` → `(N,L)`：位点 j 被所有 query 关注的平均强度（308）。
- 位点级 `pos_attn_mean/std = mean/std(incoming_attn, axis=0)`，`pos_attn_snr = mean/(std+1e-12)`（309-311）。
- **香农熵**：`incoming_attn` 先按行归一？否——直接 `H = -Σ_j A_j·log2(A_j+eps)`（315）；
  `entropy_per_sample` 形状 `(N,)`，再 `np.full(L, mean(entropy_per_sample))` 广播到所有位点（316）。
  实测导出表 184 行中 `Attention_Entropy` 只有 **1 个唯一值（4.086）**，
  证明该列是"每次实验一个全局标量"，并非逐位点熵。
- 导出：每 (l,c) 一行，`Feature=f"{channel}_pos_{l}"`，三列 rename 为
  `Transformer_Attention / Attention_Entropy / Attention_SNR`（394-400），按注意力降序（401）。

## 7.8 每实验 Artifact 表

`<M>` = `linear_regression` / `xgboost` / `mlp` / `cnn` / `transformer`。
写入点为 `<models_root>/<batch>/<run_name>/`、`<results_root>/<batch>/<run_name>/`、`<logs_root>/<batch>/<run_name>/`。

| Artifact 文件 | 生成函数 (path:line) | 字段/内容 | 下游消费者 |
|---|---|---|---|
| `<M>_metrics.json`（linear: `linear_regression_metrics.json`） | linear 598-614 / xgb 431-433 / mlp 352-354 / cnn 428-430 / trans 434-436 | 测试集 6 指标 MSE/RMSE/MAE/R2/Pearson/Spearman | `analysis/collect_results.py`, `analysis/data/loaders.py:127-131`（排除 `validation` 名） |
| `<M>_validation_metrics.json` | linear 616-619 / xgb 435-440 / mlp 356-361 / cnn 432-437 / trans 438-443 | 验证集 6 指标（有效验证集时才写） | 同上（被显式排除，不参与汇总主指标） |
| `<M>_predictions.csv` | linear 621-622 / xgb 442-443 / mlp 363-364 / cnn 439-440 / trans 445-446 | `y_true,y_pred,error` | 分析脚本、人工核查 |
| `<M>_validation_predictions.csv` | linear 782-783（另存）/ xgb 445-449 / mlp 366-370 / cnn 442-446 / trans 448-452 | `y_true,y_pred,error` | 同上 |
| 特征重要性 CSV：`linear_regression_weights.csv` / `xgboost_feature_importance.csv` / `mlp_feature_importance.csv` / `cnn_feature_importance.csv` / `transformer_feature_importance.csv` | linear 624-625 / xgb 452-454 / mlp 373-375 / cnn 449-451 / trans 455-457 | 白名单列（见 8.4）+ `Feature`(+`Position/Channel`) | `analysis/importance_extraction.py`（→ `summary/feature_importance/*.md`）、`analysis/visualization.py:169`（`**/*importance*.csv` 与 `**/*weights*.csv`） |
| `<M>_training_history.csv` | xgb `save_training_history` 391-408 / mlp 377-378 / cnn 453-454 / trans 459-460（**linear 无**） | `epoch,train_loss,validation_loss`（xgb 为 `iteration,train_rmse,validation_rmse`） | 训练曲线分析 |
| `<M>_info.txt` | linear 630-657 / xgb 459-492 / mlp 380-401 / cnn 456-477 / trans 462-483 | run_name、时间、配置字典、valid/test 指标（xgb 另有 best_iteration/best_score/超参） | `analysis/collect_results.py:38`, `analysis/data/loaders.py:115-125`, `workflows/training/data_digging.py:183-229`（续跑判定） |
| `linear_regression_diagnostics.json` | `save_linear_diagnostics` 577-591 与 `save_results` 627-628；**另在模型目录由 `save` 再写一份** 326-339 | feature_count/numerical_rank/condition_number/pinv_rcond/singular_values | 共线性诊断 |
| 模型文件 | linear `linear_regression_model.pkl`+`linear_regression_scaler.pkl`（300-324）；xgb `xgboost_model.json`+`xgboost_config.json`（244-263）；mlp/cnn/trans `<M>_model.pt`+`<M>_config.json`(+`<M>_scaler.pkl`)（mlp 700-711、cnn 787-798、trans 726-737） | 权重/state_dict + config | `workflows/prediction/predict.py` 不读这些文件（自行重训）；供人工/后续加载 |
| `training.log` | 各模块 `create_logger`（linear 491-509, xgb 120-138, mlp 70-88, cnn 65-82, trans 65-82） | 训练日志（文件+控制台） | 排障 |
| 汇总（非训练产出） | `analysis/collect_results.py:312-355` | `summary/metrics_tables/{all_experiments,single_cell_line_result,all_cell_line_result,mixed_cell_line_result,baseline}.csv` | GUI/可视化 |
| 汇总（非训练产出） | `analysis/importance_extraction.py` | `summary/feature_importance/{linear_coefficiency,xgboost_importance,mlp_importance,cnn33/cnn53/cnn73_importance,transformer_importance}.md` + `key_regulatory_biomarkers.csv` | `analysis/visualization.py:303-320`（星级掩码热图） |
| Ultimate（非 workflows/training/train.py） | `workflows/prediction/predict.py` 476-558 | `summary/ultimate/ultimate_{lr,mlp,cnn33,cnn53,cnn73,transformer}_model.*`、`ultimate_{xgboost}_model.pkl`、`ultimate_summary.json` | `workflows/prediction/predict.py` 生成 `summary/赛道二_results.csv` |

---

# 8. XAI / Feature Attribution

## 8.1 实现清单核对表

| Method | 模型 | 实现函数 (path:line) | 输出列 | SNR? | Status |
|---|---|---|---|---|---|
| Linear coefficient（OLS 伪逆） | Linear | `LinearRegressionModel.fit` linear_regression.py:194-195 | `Linear_Coefficient` | 否（用 SE/t/p/FDR） | **已实现** |
| 标准误 / t / p / BH-FDR | Linear | linear_regression.py:205-232 | `SE`,`t_stat`,`p_value`,`FDR` | 否 | **已实现**（唯一允许经典统计的模型） |
| XGB Gain | XGBoost | `get_feature_importance` xgboost.py:330-334 | `XGB_Gain` | 否 | **已实现** |
| XGB Weight（分裂频次） | XGBoost | 同上 | `XGB_Weight` | 否 | **已实现** |
| XGB Cover（覆盖量） | XGBoost | 同上 | `XGB_Cover` | 否 | **已实现** |
| TreeSHAP（原生 pred_contribs） | XGBoost | xgboost.py:340-357 | `TreeSHAP`（mean\|SHAP\|） | 是 → `SHAP_SNR` | **已实现** |
| 置换检验 / 置换 p 值 | XGBoost（及全部非线性） | — | — | — | **当前代码未实现**（docstring 声明已移除，xgboost.py:16；全仓库无实现） |
| MLP Integrated Gradients | MLP | `compute_integrated_gradients` mlp.py:212-242；调用 mlp.py:290（steps=25） | `MLP_IG` | 是 → `IG_SNR`（mlp.py:294） | **已实现** |
| CNN In-Silico Mutagenesis | CNN | `compute_cnn_ism` cnn.py:284-311 | `CNN_ISM`（mean\|Δŷ\|） | 是 → `ISM_SNR`（cnn.py:363） | **已实现** |
| CNN Integrated Gradients | CNN | `compute_cnn_integrated_gradients` cnn.py:314-343；调用 cnn.py:366（steps=20） | `CNN_IG` | 否（`_ig_std` 丢弃） | **已实现** |
| Transformer Self-Attention 聚合 | Transformer | `compute_transformer_attention_robustness` transformer.py:289-318 | `Transformer_Attention`（位点级 incoming 注意力均值） | 是 → `Attention_SNR`（311） | **已实现** |
| Attention Entropy（香农） | Transformer | transformer.py:313-316 | `Attention_Entropy`（**全表同一标量**） | 否 | **已实现**（但非逐位点熵，见 8.2） |
| Transformer Integrated Gradients | Transformer | `compute_transformer_integrated_gradients` transformer.py:321-350 | —（无导出列） | — | **函数存在但当前未被调用/未导出**（docstring transformer.py:365 承认 "IG … 已从导出中移除"） |
| SNR 指标族 | XGB/MLP/CNN/Transformer | 见 8.3 | `SHAP_SNR`,`IG_SNR`,`ISM_SNR`,`Attention_SNR` | — | **已实现** |
| SNR ★ 星级（★≥2.5 …） | 4 个非线性模型 | `analysis/importance_extraction.py:111-122, 249-262`（**不在 src/ 训练代码内**） | `.md` 报表 `sig` 列 | — | **已实现于后处理**；训练 CSV 不含星级 |

## 8.2 各方法函数级说明

### `get_feature_importance(model, feature_names, X_eval, y_eval, random_seed=42)` — xgboost.py:296
- 输入：已拟合 `XGBoostModel`、特征名（长度必须等于 `feature_count`）、评估矩阵（训练路径传 **X_test**，xgboost.py:606）。
- 输出：`pd.DataFrame`，列 = `Feature + XGB_Gain,XGB_Weight,XGB_Cover,TreeSHAP,SHAP_SNR`（白名单清洗后），按 `XGB_Gain` 降序。
- 算法：`booster.get_score(gain/weight/cover)` → `f{i}` 对齐；`pred_contribs=True` 原生 TreeSHAP
  取 `[:, :-1]` 去掉 bias 列；`TreeSHAP_i = mean(|SHAP_i|)`；`SHAP_SNR_i = mean(|SHAP_i|)/(std(SHAP_i)+1e-12)`。
  `X_eval` 为空或异常时 `SHAP_*` 全为 NaN（337-338、354-355 的 try/except 静默吞异常）。

### `compute_integrated_gradients(model, X, device, steps=30)` — mlp.py:212
- 输入：2D 特征矩阵 `X (N,D)`；输出：`(N,D)` float32 归因矩阵。
- baseline = 全零（223）；`steps+1` 个插值点（含 α=0 与 α=1）；对每一步的 `Σ_i ŷ` 求 `autograd.grad`；
  `avg_grads = grads[:-1].mean(0)`（239）；`IG = (x − baseline)·avg_grads`（240）。
- 逐样本循环，**未做 batch 并行**。


### `compute_mlp_robustness_importance(model, X_eval, feature_names, device)` — mlp.py:274
- `MLP_IG = mean|IG|`、`IG_SNR = mean|IG| / (std(IG)+1e-12)`（290-298）；
  `export_feature_table("mlp", rename={"IG_Mean":"MLP_IG"})` 后按 `MLP_IG` 降序。

### `compute_cnn_ism(model, X, device)` — cnn.py:284
- 输入 `X (N,L,C)`；输出 `(mean_ism (L,C), std_ism (L,C))`。
- **突变集合 = 全部 L×C 个 (位点, 通道) 组合**：`for l in range(L): for c in range(C)`（300-301）。
- 突变规则是"翻转二值"：`X_mut[:,l,c] = where(X>0, 0.0, 1.0)`（304），而非固定置零或换成其他碱基。
- `Δ = |ŷ_mut − ŷ_base|`（307）；对样本维求 mean/std（309-310）。
- 计算量：每样本 L×C 次前向，全量一次 ISM 需 `N × 184` 次推理（无早停/无子采样）。

### `compute_cnn_integrated_gradients(model, X, device, steps=25)` — cnn.py:314
- 3D 版 IG：`baseline = zeros_like(X)`，α 网格 `linspace(0,1,steps+1)`，逐样本求 `Σŷ` 的梯度，
  `IG = (x−baseline)·mean(grads[:-1])`（327-339）；返回 `mean|IG| (L,C)` 与 `std(IG) (L,C)`。
- 调用处 `steps=20`（cnn.py:366）→ 每样本 21 次前向。

### `compute_transformer_attention_robustness(model, X, device)` — transformer.py:289
- 输入 `X (N,L,C)`；输出 `(pos_attn_mean (L,), mean_entropy (L,), pos_attn_snr (L,))`。
- 注意力来源：`model(X, return_attn=True)` 的**最后一层** `(N,nhead,L,L)`（300-302）；
  跨头 `mean(axis=1)` → `(N,L,L)`；`incoming_attn = mean(axis=1)` → 位点 j 的平均被关注度 `(N,L)`（305-308）。
- `pos_attn_mean/std` 对样本求；`pos_attn_snr = mean/(std+1e-12)`（309-311）。
- **熵公式**：`H = −Σ_j incoming_attn[j]·log2(incoming_attn[j] + 1e-12)`（315）。
  `incoming_attn` 每行近似为一个概率分布（softmax 输出沿 query 已归一，平均后行和≈1），
  因此每样本得到**一个**标量；`mean_entropy = np.full(L, mean(H))`（316）把它复制到全部 23 个位点。
  实测 184 行 `Attention_Entropy` 唯一值数 = 1（4.0860033）：**该列不区分位点，也不区分通道**。

### `compute_transformer_integrated_gradients(..., steps=20)` — transformer.py:321
- 与 CNN/MLP IG 同构的 3D 实现（zeros baseline、α 网格、`mean|IG|`），
  但 `train()` 的 XAI 分支（702-711）只调用 `compute_transformer_robustness_importance`，
  白名单（xai_importance.py:35）也不含任何 IG 列 → **当前训练流程不产出 Transformer IG**。

### `export_feature_table(model_key, df, rename=None, drop=None, origin="")` — xai_importance.py:76
- 输入：模型键、待导出 DataFrame、可选 rename、来源标记；输出：清洗后的 DataFrame。
- 步骤：`model_key` 小写；未知键原样返回（92-94）；合并 `LEGACY_RENAME_MAP` 与调用方 `rename`，
  按**列名小写**匹配后 rename（97-107）；仅保留 `_ID_COLUMNS ∪ WHITELIST`，列序 = 标识列 + 白名单（109-113）；
  非线性模型若残留 `_FORBIDDEN_STATS` 任一键 → 直接 `raise ValueError`（115-121）。
- `drop` 形参被声明但未使用（79，函数体内无引用）。
- `validate_nonlinear_has_no_stats(df, model_key, origin)`（125-135）：仅校验、不修改，命中禁用列即抛错。

## 8.3 SNR 定义（精确公式）与阈值使用位置

各模型 SNR 统一是 "逐特征 mean / std" 的归因稳健性比值（`1e-12` 防零）：

| 列名 | 公式（源码原式） | 位置 |
|---|---|---|
| `SHAP_SNR` | `mean(|SHAP_i|) / (std(SHAP_i) + 1e-12)`，mean/std 沿**样本维** | xgboost.py:350-353 |
| `IG_SNR` | `mean(|IG_i|) / (std(IG_i) + 1e-12)`（分子用 \|·\| 的均值，分母用 **带符号** IG 的标准差） | mlp.py:292-294 |
| `ISM_SNR` | `mean_n(|Δŷ_{l,c}|) / (std_n(|Δŷ_{l,c}|) + 1e-12)`，逐 (位点,通道) | cnn.py:363 |
| `Attention_SNR` | `mean_n(incoming_attn_j) / (std_n(incoming_attn_j) + 1e-12)`，逐位点 j | transformer.py:311 |

> 注意：CNN 的 IG 算了 std 但**没有对应的 SNR 导出列**
> （cnn.py:366 `_ig_std`、mlp.py:297 `_sg_std_mat`）。

**阈值/星级使用位置（不在训练代码中）**：
- `analysis/importance_extraction.py:111-122` `get_snr_significance_code`：
  `SNR ≥ 2.5 → "***"`，`≥1.8 → "**"`，`≥1.2 → "*"`，`≥0.8 → "."`，否则 `""`。
- 线性模型改走 FDR 星级 `_sig_for_fdr`（239-246：`<0.001/0.01/0.05/0.10`）；
  非线性走 `_derive_sig`（249-262），并写入 `.md` 报表的 `sig` 列（276-284），
  由 `analysis/visualization.py:303-320` 解析后用于热图显著性掩码（446）。
- `analysis/schemas.py:9` 与 `analysis/evidence/rules.py:36-44` 明确"SNR 不是 p 值"，
  并要求 SNR 与 |effect| 双门槛才可称 strong attribution。
- **`src/` 训练侧没有任何 SNR 阈值/星级逻辑**（全仓库 `2.5` 无命中于 `src/`）。

## 8.4 白名单列（`WHITELIST_COLUMNS`, core/xai/importance/xai_importance.py:29-36）

```python
WHITELIST_COLUMNS = {
    "linear":            ["Linear_Coefficient", "SE", "t_stat", "p_value", "FDR"],
    "linear_regression": ["Linear_Coefficient", "SE", "t_stat", "p_value", "FDR"],
    "xgboost":           ["XGB_Gain", "XGB_Weight", "XGB_Cover", "TreeSHAP", "SHAP_SNR"],
    "mlp":               ["MLP_IG", "IG_SNR"],
    "cnn":               ["CNN_IG", "CNN_ISM", "ISM_SNR"],
    "transformer":       ["Transformer_Attention", "Attention_Entropy", "Attention_SNR"],
}
```

- 标识列 `_ID_COLUMNS = {"Feature","Position","Channel", "feature","position","channel"}`（39）。
- 非线性禁用统计列 `_FORBIDDEN_STATS`（42-45）：`t_stat,t_value,p_value,p_val,p_adj,p_adj_fdr,fdr,
  permutation_p_val,permutation_p_adj_fdr,permutation_delta_r2,q_value`。
- 旧名兼容 `LEGACY_RENAME_MAP`（48-73）：如 `weight/coefficient/coef→Linear_Coefficient`、
  `std_error/se→SE`、`p_adj_fdr/p_adj/q→FDR`、`importance_gain/gain→XGB_Gain`、
  `importance_weight→XGB_Weight`、`importance_cover→XGB_Cover`、`shap_mean/mean_abs_shap→TreeSHAP`、
  `ig_mean/mean_ig→MLP_IG`、
  `ism_mean_delta/ism_mean→CNN_ISM`、`cnn_ig→CNN_IG`、
  `attn_weight/attention_weight→Transformer_Attention`、`attn_entropy/attention_entropy→Attention_Entropy`。
- 实测导出表头验证：`Feature,Linear_Coefficient,SE,t_stat,p_value,FDR`（linear）/
  `Feature,XGB_Gain,XGB_Weight,XGB_Cover,TreeSHAP,SHAP_SNR`（xgb）/
  `Feature,MLP_IG,IG_SNR`（mlp）/
  `Feature,Position,Channel,CNN_IG,CNN_ISM,ISM_SNR`（cnn）/
  `Feature,Position,Channel,Transformer_Attention,Attention_Entropy,Attention_SNR`（transformer）。

---

# 9. 训练输出与实验目录结构

真实目录示例（来自仓库现有产物）：

```
results/
└── batch_20260909_full/                 # --batch-name batch_20260909_full（1346 个实验目录）
    ├── all_linear_all_heldout_hct116/   # split_type=all, model=linear, env=all, 留出 hct116
    │   ├── linear_regression_metrics.json
    │   ├── linear_regression_validation_metrics.json
    │   ├── linear_regression_predictions.csv
    │   ├── linear_regression_validation_predictions.csv
    │   ├── linear_regression_weights.csv          # 163 行 = 161 特征 + Bias + 表头
    │   ├── linear_regression_diagnostics.json
    │   └── linear_regression_info.txt
    ├── all_xgboost_all_heldout_hct116/  # 7 个文件（含 xgboost_training_history.csv）
    ├── all_mlp_all_heldout_hct116/
    ├── all_transformer_all_heldout_hct116/
    ├── all_cnn_all_heldout_hct116_kernel_3/        # CNN 三核变体各一套
    ├── all_cnn_all_heldout_hct116_kernel_5/
    ├── all_cnn_all_heldout_hct116_kernel_7/
    └── summary/                          # 由 analysis/ 与 workflows/prediction/predict.py 产生，非 workflows/training/train.py
        ├── metrics_tables/{all_experiments,baseline,single_cell_line_result,
        │                   all_cell_line_result,mixed_cell_line_result}.csv
        ├── feature_importance/{linear_coefficiency,xgboost_importance,mlp_importance,
        │                       cnn33_importance,cnn53_importance,cnn73_importance,
        │                       transformer_importance}.md + key_regulatory_biomarkers.csv
        ├── ultimate/ultimate_{lr,xgboost,mlp,cnn33,cnn53,cnn73,transformer}_*  + ultimate_summary.json
        └── 赛道二_results.csv
```

每个文件的产生点：

| 目录 | 产生者 |
|---|---|
| `results/<batch>/<run_name>/*` | 各模型 `train()` 的 `save_results` / `save_predictions` / `save_weights` / `save_training_history` / `save_linear_diagnostics` |
| `models/<batch>/<run_name>/*` | 各模型 `save()`/`save_model()`（当前 checkout 中 `models/` 与 `logs/` 为空目录，未保留产物） |
| `logs/<batch>/<run_name>/training.log` | 各模块 `create_logger`（同上，当前为空） |
| `results/<batch>/summary/metrics_tables/*` | `analysis/collect_results.py:312-355` |
| `results/<batch>/summary/feature_importance/*` | `analysis/importance_extraction.py`（各 `extract_*_importance`） |
| `results/<batch>/summary/ultimate/*` | `workflows/prediction/predict.py:542-558` + `_save_ultimate_model`（434-473） |
| `results/<batch>/summary/赛道二_results.csv` | `workflows/prediction/predict.py:821`（`generate_track2_results_ultimate`, 651+） |
| `workspace/runs/<kind>_<ts>/{training_status.json,plan.json,run.log,submit.sh}` | `app/backend/crispr_workspace/training.py:242-281, 371-390` |

物理量核对（`all_*_all_heldout_hct116`）：train 2967 / valid 635 / test 637 行；
2D 模型 184 列（linear 内部减为 161），3D 模型 (23, 8)。`random_seed=42`，ratio 0.7/0.15/0.15。

---

# 10. 与 README/注释不一致之处

| # | 出处 | 声明 | 代码事实 |
|---|---|---|---|
| 1 | README:60 | `xgboost/ # 梯度提升树 (含原生 TreeSHAP 信噪比与**置换检验**)` | 置换检验已被删除：xgboost.py:16 明确"置换检验已移除"，全仓库无实现，仅在 `_FORBIDDEN_STATS` 中作为禁用列名出现（xai_importance.py:44） |
| 2 | README:215-218 | 非线性模型统一 `SNR ≥ 2.5 (***)` | 训练侧（src/）无任何 SNR 星级逻辑；阈值只存在于后处理 `analysis/importance_extraction.py:111-122`，且报告里是 `.md` 的 `sig` 列而非训练 CSV 列 |
| 4 | README:215 | XGBoost 指标 `Gain, SHAP_mean, SHAP_SNR` | 导出列名为 `XGB_Gain/XGB_Weight/XGB_Cover/TreeSHAP/SHAP_SNR`（SHAP_mean 在清洗时被 rename 为 TreeSHAP，xai_importance.py:59） |
| 5 | README:217 | CNN 指标 `ISM_Mean_Delta, ISM_SNR` | 实际导出 `CNN_IG, CNN_ISM, ISM_SNR`（含 IG，ISM_Mean_Delta 被 rename；cnn.py:390-394） |
| 6 | README:218 | Transformer 指标 `Attn_Weight, Attn_Entropy, Attn_SNR` | 导出为 `Transformer_Attention/Attention_Entropy/Attention_SNR`（transformer.py:396-398） |
| 7 | README:196 / 图 | "[Step 3] importance_extraction.py 提取 p-val/FDR/TreeSHAP/ISM" | 说明性文字，实际还含 MLP IG、CNN IG、Transformer 注意力/熵，且非线性模型被强制禁止 p/FDR |
| 8 | transformer.py:15-16, 360-365 | 模块 docstring 列 "自注意力…" 与 "IG 与置换检验列已从导出中移除" | 自洽；但 `compute_transformer_integrated_gradients`（321-350）成了**死代码**（无调用点），容易被误读为"Transformer 有 IG 导出" |
| 9 | transformer.py:313-316 注释"各 Position 的注意力熵" | 实际 `np.full(L, mean(entropy_per_sample))` 是**全局单标量广播**，实测唯一值 = 1；位点间无差异 |
| 10 | workflows/training/train.py:636-641 vs cnn.py:517-519 | CLI 暴露 `--conv-channels1/--conv-channels2`（默认 32/64），并写入 config 与 `*_info.txt` | 五个 `train()` 均不接受这两个键，`build_train_kwargs` 按签名过滤（workflows/training/train.py:428）后**静默丢弃**；CNN 实际恒用 `sequence_filters=64, environment_filters=64, fusion_filters=128`（cnn.py:96-98、517-519）。`--hidden-dim2` 对 CNN 同样无效 |
| 11 | workflows/training/train.py:622 / workflows/training/data_digging.py:275 | `--seed` 号称控制随机性 | Linear `train(random_seed=None)` 收到后**从未使用**（linear_regression.py:697）；XGBoost 仅设 `random_state`（无全局 seed）；只有 MLP/CNN/Transformer 调 `set_seed`（mlp.py:511、cnn.py:528、transformer.py:533） |
| 12 | workflows/training/train.py:540-541 + CLI `--use-scaler` | 通用 scaler 开关 | XGBoost `train(use_scaler=False)` 形参从未被引用（xgboost.py:522）→ 对 XGBoost **无效**；Linear 的 scaler 在 `fit` 内拟合（159-163）而非 workflows/training/train.py |
| 13 | README:196 流程图 "Step 1 workflows/training/data_digging.py" | 暗示统一走 data_digging→workflows/training/train.py | `workflows/prediction/predict.py` **完全不调用 workflows/training/train.py**，自带 torch 训练循环（AdamW、batch 256、lr 1e-3、epochs=15、无早停，workflows/prediction/predict.py:328-351），与 workflows/training/train.py 路径（Adam、batch 64、epochs 100、patience 20）超参不同 |
| 14 | app/desktop/main_wizard.py:324-348 XAI 勾选框（含"计算 TreeSHAP 归因信噪比"） | 暗示可开关 XAI | 复选框只写入 `form_data["xai_vars"]`，不生成任何 CLI 参数；训练路径的 XAI **无条件执行**（mlp.py、cnn.py、transformer.py、xgboost.py） |
| 15 | workflows/training/train.py:376-377 | conv_channels 默认 32/64 作为"模型超参"出现在每个实验的 config | 该字段会写入 `cnn_info.txt`，但对应层宽实为 64/64/128，**artifact 记录与实际结构不一致** |
| 16 | linear_regression.py:454 vs save_weights:543-550 | `generate_default_feature_names` 返回 `Feature_i + "Bias"`（已含 Bias） | `save_weights` 在 `len(names)==feature_count` 时才补 Bias；若外部传入的是"不含 Bias"的名字则补齐，逻辑自洽，但默认名函数与 `train()` 的分支（750-758）存在两套同名逻辑，易混淆 |
| 17 | 当前 checkout 状态 | README 描述 `models/`、`logs/` 产物 | `models/`、`logs/` 为空目录，仓库仅保留 `results/batches/batch_20260909_full/`（1346 个实验目录），无法据此核验模型文件与 `training.log` 的真实内容 |

---

## 本节自检

- [x] **五个模型全部覆盖**：`linear`(7.3)、`xgboost`(7.4)、`mlp`(7.5)、`cnn`(7.6)、`transformer`(7.7)，
      每个都有 class/函数清单 + 训练循环精确超参 + 输出表；`MODEL_MODULES` 映射（workflows/training/train.py:56-63）已列出。
- [x] **CNN 分支维度精确**：序列分支 `Conv2d(1→64, k=(ks,C_seq), pad=(ks//2,0)) → BN64 → ReLU →
      Conv2d(64→64, k=(ks,1)) → BN64 → ReLU → AdaptiveAvgPool2d((1,1))`；
      环境分支同构（`ke`、64 filters）；融合 `Linear(128→128)→ReLU→Dropout(0.2)→Linear(128→64)→ReLU→
      Dropout(0.2)→Linear(64→1)`，纯序列时融合输入 64 维（cnn.py:120-174）。kernel 变体 3/5/7 + 环境核 3。
- [x] **Transformer 维度精确**：`input_projection Linear(C→64)`、正弦 PE(max_length=23)、
      `num_layers=2`、`nhead=4`、`dim_feedforward=128`、Pre-LN、mean pooling over L、
      regressor `Linear(64→32)→GELU→Dropout(0.2)→Linear(32→1)`（transformer.py:89-204）。
- [x] **XAI 方法存在/缺失表**（8.1）逐项核对：Linear coefficient ✅、XGB Gain/Weight/Cover ✅、
      TreeSHAP ✅、MLP IG ✅、CNN IG ✅、CNN ISM ✅、
      Transformer Attention ✅、Attention Entropy ✅、SNR×4 ✅；
      置换检验 ❌"当前代码未实现"、Transformer IG ❌"实现存在但未被调用/未导出"、
      CNN_IG_SNR ❌"未实现"。
- [x] **scaler 只在训练集 fit**：linear_regression.py:159-163、mlp.py:558-563、cnn.py:643-650、
      transformer.py:582-589；workflows/training/train.py 不拟合只透传（workflows/training/train.py:402/541/572/703）；XGBoost 不实现。
- [x] **早停参数**：MLP/CNN/Transformer 统一 `patience=20`、`min_delta=1e-6`、
      `improvement > min_delta` 才刷新 best、`deepcopy(state_dict)` 恢复最佳
      （mlp.py:631-655、cnn.py:719-745、transformer.py:657-683）；XGBoost 用
      `early_stopping_rounds=30` + `eval_set=[train,valid]`（xgboost.py:152/175-176/202）；Linear 无早停。
- [x] **artifact 名称**（7.8 + 9 节）：`<M>_metrics.json`、`<M>_validation_metrics.json`、
      `<M>_predictions.csv`、`<M>_validation_predictions.csv`、`linear_regression_weights.csv`/
      `<M>_feature_importance.csv`、`<M>_training_history.csv`、`<M>_info.txt`、
      `linear_regression_diagnostics.json`、模型文件、`training.log` 均已逐一给出产生函数与消费者。
- [x] **SNR 公式**（8.3）四条均为源码原式并标注 `path:line`；星级阈值定位到
      `analysis/importance_extraction.py:111-122`（训练侧无阈值）。
- [x] **白名单列**（8.4）逐字复制 `WHITELIST_COLUMNS`（xai_importance.py:29-36），
      并以真实 CSV 表头交叉验证。
- [x] **不一致清单**（10 节）17 条，全部有代码定位。
- [x] **只读约束**：未修改/新增/删除任何仓库文件，唯一输出为 `/tmp/doc_sections/02_models_train_xai.md`。


---

# 11. 实验结果收集与汇总 (legacy scripts; each with 状态/职责/输入/输出/函数清单)

> 本节只依据源码与实跑产物。所有 `path:line` 均指当前工作区文件。
> 判定口径: **Active** = 有实际调用方 (训练端 `app/desktop/backend_runner.py` / 向导 / 引擎 / 文档命令);
> **Legacy** = 保留原位、被训练端以旧语义调用但引擎不使用; **Unused** = 定义后无引用;
> **Uncertain** = 代码存在但无法从仓库确定是否执行。
> 实跑产物取自唯一真实批次 `results/batches/batch_20260909_full/`（1344 组实验）。

## 11.1 analysis/collect_results.py (441 行) — 指标汇总表生成

| 项 | 内容 |
|---|---|
| 状态 | **Active**（`app/desktop/backend_runner.py:244-252` Step3 以 `--batch-dir` + `--split-types` 调用; `HPC_EXPERIMENT_PROTOCOL.md:77`; `README.md:145`） |
| 职责 | 扫描批次目录内每个实验目录，把 `*info*.txt` 元数据 + `*_metrics.json` 指标 + `*_validation_metrics.json` 验证指标拼成一张宽表，再产出 all/single/all-split/mixed 结果表与 sequence 基线表 |
| 输入 | 批次目录（内含 `single_* / all_* / mixed_*` 实验子目录）；每目录 `X_info.txt`、`X_metrics.json`、`X_validation_metrics.json`（实测文件如 `single_hct116_cnn_all_kernel_3/{cnn_info.txt,cnn_metrics.json,cnn_validation_metrics.json}`） |
| 输出 | `<batch>/summary/metrics_tables/`：`all_experiments.csv`（始终）、`single_cell_line_result.csv`、`all_cell_line_result.csv`、`mixed_cell_line_result.csv`（按勾选 split 选择性生成）、`baseline.csv`。实测该目录 5 个文件，`all_experiments.csv` = 1344 行 × 75 列 |

### 实验发现与解析规则
- `collect_batch()` (`analysis/collect_results.py:147-167`)：只遍历 `batch_dir.iterdir()` 的**直接子目录**，跳过名为 `summary` 的目录；发现门槛是 `glob("*info*.txt")` 或 `glob("*metrics*.json")` 非空 (`:155`)；单目录解析异常只打印 `[Warning]` 继续，无记录则 `RuntimeError` (`:162-163`)。
- `find_file(folder, "_info.txt")` (`:105-109`) 取 `*_info.txt*` 的**第一个**命中（无排序保证）；注意门槛用 `*info*.txt`，而真正读取用 `"_info.txt"`，因此形如 `info.txt`（无下划线）的目录会通过门槛但解析为空 dict（**不一致**）。
- `parse_info_txt()` (`:38-71`) 是唯一做类型推断的解析器：`[...]` 走 `ast.literal_eval`；`true/false` → bool；含 `.` → `float`；否则 `int`；失败保留字符串。实测 info 中 `sequence_kernel: 3` 之类被转成 int，`channel_names: [...]` 转成 list。
- 模型名归一 `build_model_name()` (`:74-95`)：`linear_regression|linear → "linear"`；含 `cnn` → `f"cnn({seq_k}|{env_k})"`，优先读 `sequence_kernel_shape/environment_kernel_shape`（list 取首元素），否则回落 `sequence_kernel/environment_kernel`，默认 3。**实测本批 info 只有 `sequence_kernel/environment_kernel`**，故 shape 分支从未触发。
- 其它归一 (`:120-131`)：`split_type` 小写；`mixed → cell_line="none"`，否则小写或 `"unknown"`；`environment` 取 `environment` 否则 `combination`，小写。
- `data["model"]` 与 `data["model_display"]` 同值 (`:131-132`)，`model_display` 在写盘前被 drop (`:328-329`)。
- 指标合并 (`:134-142`)：`*_metrics.json` 排除文件名含 `validation` 者；验证指标统一加前缀 `validation_`。

### 排序 / 过滤 / ΔR²
- `MODEL_ORDER` (`:21-29`) = linear, xgboost, mlp, cnn(3|3), cnn(5|3), cnn(7|3), transformer；`SPLIT_ORDER` (`:31-35`) = single 0 / all 1 / mixed 2；`env_sort_key()` (`:182-192`) 把 `sequence` 排 0、`sequence_*` 按因子个数、`all` 排 99。
- `filter_valid()` (`:176-179`)：剔除 `R2` 为 NaN **或** `|R2| > 10.0` **或** `MAE > 10.0` **或** `RMSE > 10.0` 的行；直接按下标访问 `df["R2"]/["MAE"]/["RMSE"]`，列缺失会 KeyError（无防御）。
- `calculate_delta_R2()` (`:217-244`)：以 `environment == "sequence"` 的行为基线，键为 `(split_type, cell_line, model)`（`:227`），逐行 `delta_R2 = R2 - baseline`；sequence 行置 0.0。**该键不含 `random_seed`**，mixed 多 seed 时 `baseline_map[key]` 会被后写覆盖（`:228`），与引擎同 seed 配对纪律 (`analysis/data/validation.py:37-40`) 语义不同 —— 属旧版设计。
- 结果表构造 `build_result_dataframe()` (`:247-270`)：列顺序 = cell_line?(可选) → model → environment → `MAE/RMSE` → `Pearson/Spearman` → `R2` → `delta_R2` → `validation_MAE/RMSE` → `validation_Pearson/Spearman` → `validation_R2`；成对指标由 `format_pair()` 格式化为 `"%.4f/%.4f"` (`:170-173`)，NaN → 空串。
- `create_single_result()` (`:273-278`, 带 cell_line)、`create_all_result()` (`:281-288`, 追加 `test_cell_line` 列)、`create_mixed_result()` (`:291-309`, 先按 `(model, environment)` 对 10 个指标列求均值合并多 seed，再算 ΔR²)。
- `create_baseline()` (`:360-385`)：仅 `environment == "sequence"`；non-mixed 逐 cell line 保留，mixed 按 `(model, split_type)` 跨 seed 求均值后 `cell_line="none"` (`:374-378`)；列 = model, split_type, cell_line, R2, MAE, RMSE, Pearson, Spearman。
- 注释明示 `summary.md` 与 `environment_effect_summary.csv` 已不再生成 (`:391-392`)，函数只写 `baseline.csv`。

### 函数清单
| 函数 (行) | 作用要点 |
|---|---|
| `parse_info_txt(path)` (`:38-71`) | `k: v` 解析 + 类型推断（list/bool/float/int），无文件返回 `{}` |
| `build_model_name(info)` (`:74-95`) | 模型名归一，CNN 产 `cnn({seq_k}|{env_k})` |
| `load_json(path)` (`:98-102`) | 空路径/不存在 → `{}` |
| `find_file(folder, keyword, exclude=None)` (`:105-109`) | `glob("*{keyword}*")` 取首个，可排除含 `exclude` 的文件名 |
| `collect_one_experiment(folder)` (`:112-144`) | 单实验 = run_name + info + metrics + `validation_*`，并做 split/cell/env 归一 |
| `collect_batch(batch_dir)` (`:147-167`) | 目录级发现与容错，产出宽表，去重列 (`:166`) |
| `format_pair(a, b)` (`:170-173`) | `"%.4f/%.4f"`，任一 NaN → `""` |
| `filter_valid(df)` (`:176-179`) | 发散/缺失剔除（`|R2|>10 / MAE>10 / RMSE>10`） |
| `env_sort_key(env)` (`:182-192`) | 环境名排序键（sequence=0，`sequence_*` 按因子数，all=99） |
| `get_sort_keys(row, …)` (`:195-204`) | `(split_rank, env_rank, env_name, model_rank, cell_line)` |
| `sort_dataframe(df, …)` (`:207-214`) | 以 `_sort_key` 临时列排序后 drop |
| `calculate_delta_R2(df)` (`:217-244`) | sequence 基线 ΔR²（键无 seed，见上文⚠） |
| `build_result_dataframe(df, include_cell_line)` (`:247-270`) | 结果表列装配 + 排序 |
| `create_single_result` / `create_all_result` / `create_mixed_result` (`:273-309`) | 三种 split 的结果表（all 追加 `test_cell_line`；mixed 先跨 seed 平均） |
| `save_result_tables(df, metrics_dir, selected_splits)` (`:312-357`) | 写 `all_experiments.csv` + 按勾选写 3 张结果表（未勾选打印 skipped） |
| `create_baseline(df, selected_splits)` (`:360-385`) | sequence-only 基线表（mixed 跨 seed 平均） |
| `save_baseline_table(df, metrics_dir, selected_splits)` (`:388-397`) | 写 `baseline.csv` |
| `main()` (`:400-439`) | CLI + 批次自动判定 + 调度 |

### CLI 与产出定位
`main()` (`:400-439`)：`--results-dir`（默认 `results`）、`--batch-name`、`--batch-dir`、`--latest`、`--split-types {single,all,mixed}+`；输出目录固定 `<batch>/summary/metrics_tables` (`:436`)。
批次自动判定 (`:417-422`)：若 `results` 下直接存在以 `single_/all_/mixed_` 开头的目录则它本身即批次，否则取 mtime 最新的非 `summary` 子目录。**`--latest` 声明后在函数体内从未使用（Unused 参数）**。

## 11.2 analysis/importance_extraction.py (908 行) — 特征重要性抽取与白名单报告

| 项 | 内容 |
|---|---|
| 状态 | **Active**（`app/desktop/backend_runner.py:264-270` Step5 `--batch_dir`; `scripts/make_notebook.py:262` 直接 import） |
| 职责 | 逐模型族扫描实验目录内的重要性/权重 CSV，按白名单剔除非法统计列，生成 5 族（CNN 按卷积核拆 3 份）`.md` 报告 + `key_regulatory_biomarkers.csv` 关键特征库 |
| 输入 | `<batch>/**/*.csv`（跳过文件名含 `pred/metric/history/summary` 者，`:304-306`）+ 同目录 `*info*.txt` |
| 输出 | `<batch>/summary/feature_importance/{linear_coefficiency.md, xgboost_importance.md, mlp_importance.md, cnn33_importance.md, cnn53_importance.md, cnn73_importance.md, transformer_importance.md, key_regulatory_biomarkers.csv}`（实测 8 个文件齐全） |

### 常量与白名单（XAI 学术红线）
- `SCHEMA_CHANNELS = [a,c,g,t,ctcf,dnase,h3k4me3,rrbs]` (`:23`)，`EPI_CHANNELS = [ctcf,dnase,h3k4me3,rrbs]` (`:24`)，`CHANNEL_ORDER` (`:26-30`, unknown→99)。
- `XAI_WHITELIST` (`:133-139`)：linear = `Linear_Coefficient, SE, t_stat, p_value, FDR`；xgboost = `XGB_Gain, XGB_Weight, XGB_Cover, TreeSHAP, SHAP_SNR`；mlp = `MLP_IG, IG_SNR`；cnn = `CNN_IG, CNN_ISM, ISM_SNR`；transformer = `Transformer_Attention, Attention_Entropy, Attention_SNR`。
- `XAI_ALIAS` (`:142-174`) 把旧列名（`weight/coef/importance_gain/shap_mean/ism_mean_delta/attn_weight/...`）映射到白名单规范名。
- `FORBIDDEN_PARAMETRIC_COLS` (`:177-180`) = `t_stat,t_value,p_value,p_val,p_adj,p_adj_fdr,fdr,q_value,permutation_p_val,permutation_p_adj_fdr,permutation_delta_r2`；非线性模型命中即 **drop + Warning** (`:228-233`)。
- `XAI_SIG_NOTE` (`:184-190`) 与 `XAI_SNR_COL` (`:192-197`) 定义 linear 用 BH-FDR、非线性用 SNR 的星级口径；`_MODEL_TOKEN` (`:199-205`) **定义后无任何引用（Unused）**。

### 函数清单
| 函数 (行) | 作用要点 |
|---|---|
| `parse_info_file` (`:33-42`) | `k: v` 逐行，**键值全部 lower 且不做类型转换**（与 `collect_results.parse_info_txt` 不同） |
| `normalize_cell_line` (`:45-51`) | mixed→`none`；空/`none`/`unknown`→`unknown` |
| `get_active_channels` (`:54-62`) | 基底 `{a,g,c}`；`all/all_features/full`→8 通道；否则按子串加入表观通道 |
| `identify_feature_channel` (`:65-80`) | 先匹配 h3k4me3→ctcf→dnase→rrbs，再正则匹配单碱基（含 `pos\d*_?a` 等写法）；`feat_N`/纯数字回落 `SCHEMA_CHANNELS[idx % 7]`（`:78`，用 **7** 而数组长 8 → `rrbs` 永不被推断，属实现瑕疵） |
| `extract_feature_position` (`:83-94`) | `pos_?(\d+)` → 数字；`feat_N` → `N // 7`（同 7/8 瑕疵）；尾部 `_(\d+)$`；否则 999 |
| `is_feature_valid_for_env` (`:97-101`) | 通道不在该环境激活集合即丢弃；`unknown` 一律保留 |
| `get_snr_significance_code` (`:111-122`) | SNR≥2.5→`***`，≥1.8→`**`，≥1.2→`*`，≥0.8→`.`，否则空 |
| `_sanitize_importance_table` (`:208-236`) | alias 重命名 → 仅保留标识列 + 白名单列 → 非线性剔非法统计列 |
| `_sig_for_fdr` (`:239-246`) | `<0.001 *** / <0.01 ** / <0.05 * / <0.10 .` |
| `_derive_sig` (`:249-262`) | linear 走 FDR 星级，其余走各自 SNR 列 |
| `_write_importance_md` (`:265-295`) | 写 `| split_type | environment | cell_line | feature | <metrics> | sig |` 表，数值 `%.4f`，缺失 `N/A` |
| `extract_linear_coefficients` (`:298-355`) | 需 `Linear_Coefficient`；输出 `linear_coefficiency.md` |
| `extract_xgboost_importance` (`:358-415`) | 需 `XGB_Gain`；输出 `xgboost_importance.md` |
| `extract_mlp_importance` (`:418-475`) | 需 `MLP_IG` |
| `extract_cnn_importance` (`:478-549`) | 从 `sequence_kernel`（默认 3，仅接受 3/5/7）分桶，按 kernel 输出 `cnn{3,5,7}3_importance.md` |
| `extract_transformer_importance` (`:552-610`) | 需 `Transformer_Attention` |
| `get_canonical_feature_id` (`:624-675`) | **核心归一**：`bias/intercept → (-999,'Bias','Bias')`；通道按 h3k4me3/ctcf/dnase/rrbs/a/g/c/t 子串；`^pos(\d+)_` 视为 1-based；`pos_(\d+)` 或尾部数字视为 0-based 且 `raw<=22 → +1`；越界保留原名 |
| `collect_all_model_features` (`:678-783`) | 跨族汇总：模型族归一到 `linear/xgboost/mlp/cnn{3,5,7}3/transformer`；`metric_map` 取 `(贡献列, SNR 列)` (`:734-740`)；linear 另取 `p_value/FDR`，非线性强制 `p_val=fdr=NaN` (`:760`) |
| `generate_key_regulatory_biomarkers` (`:786-854`) | 仅保留 `sig_score > 0`；mixed 按 `(split_type,cell_line,environment,model_key,canonical_feature)` 求均值并用 `score_to_sym` 反推星级 (`:816-822`)；输出中文列名 CSV（`训练方式(split_type)…FDR校正q值`）；**输入为空时写入 2 行硬编码 demo 数据** (`:792-799`) |
| `process_batch` (`:857-874`) | 依次调用 5 族抽取 + biomarker 生成，输出目录固定 `<batch>/summary/feature_importance` |
| `main` (`:877-904`) | `--results_dir/--batch_name/--batch_dir/--latest/--all_batches`；**`--latest` 与 `--all_batches` 均未被使用（Unused 参数）** |

实测 `key_regulatory_biomarkers.csv` 前 2 行：`all,hct116,all,cnn33,pos9_CTCF,***,0.005757…,2.685…,`（FDR 列为空 → 非线性模型不留 FDR，符合红线）。

## 11.3 analysis/visualization.py (959 行) — V6 显著性掩码热图 / 环境增量树 / 表观对比

| 项 | 内容 |
|---|---|
| 状态 | **Legacy（但仍在调用链上）**：新包 `analysis/visualization/` 同名遮蔽该文件，包内 PEP 562 `__getattr__` 惰性加载本文件并透传 `generate_all_visualizations` (`analysis/visualization/__init__.py:56-84`)，`app/desktop/backend_runner.py:274-279` Step6 与 `HPC_EXPERIMENT_PROTOCOL.md:82` 仍走旧入口 |
| 职责 | ① 23nt 位置热图（无显著性位点白色掩码）② 去重组合环境增量树 ③ 4 类表观因子 SNR 对比 |
| 输入 | `<batch>/**/*importance*.csv`、`/**/*weights*.csv`（`:169`）；`summary/feature_importance/*.md` 星级 (`:306-358`)；`summary/metrics_tables/all_experiments.csv`（缺失时回落 `collect_batch`，`:511-536`） |
| 输出 | 默认 `<batch>/summary/plots/`：`01_position_heatmaps/`、`02_env_increment_trees/`、`03_epigenetic_comparisons/`。**实测该批次无 `summary/plots/` 目录 → 本批未产出（Uncertain：是否运行过无法从仓库确定）** |

### 关键函数
| 函数 (行) | 要点 |
|---|---|
| `FEATURE_IMPORTANCE_FILES` (`:46-55`) | md 文件名→模型族，含旧版未拆分 `cnn_importance→cnn` 兼容 |
| `MODEL_METRIC_CONFIG` (`:58-89`) / `_metric_cfg` (`:92-99`) | 各族指标列候选与色图：linear `RdBu_r`(center 0)、xgboost `YlOrRd`、mlp `YlOrRd`、cnn `Reds`、transformer `Purples`；`cnn33/53/73` 复用 cnn |
| `_make_heatmap_cmap` (`:102-118`) | `cmap.set_bad("#ffffff")` 白掩码；**非线性色图自 0.25 处截断**，低幅值显著格仍可见 |
| `parse_feature_position_channel` (`:137-164`) | `pos_?(\d+)` 否则尾部 `_(\d+)`；`0..22 → +1`；`>23 → ((pos-1)%23)+1`；bias/intercept→`(-999,'Bias')` |
| `load_raw_feature_records` (`:167-299`) | 跳过路径含 `summary` 或名含 `pred` 的文件；按 `col_candidates` 找值列，找不到用第 2 列 (`:224`)；SNR 列回落链 `shap_snr→ism_snr→t_stat→ig_snr→attn_snr→attention_snr` (`:226-229`)；**异常值隔离**：linear 值 clip ±1.0、SNR clip [0.01,10]，非线性 SNR clip [0.01,15] (`:243-252`)；无任何记录时生成 42 种子 demo 数据 (`:272-297`) |
| `load_significance_table` (`:306-358`) | 解析 md 管道表：`cells[0]=split, [1]=env, [2]=cell, [3]=feature, cells[-1]=sig`；`SIG_RANK = {"":0,".":1,"*":2,"**":3,"***":4}` (`:43`) |
| `_build_significance_rank` (`:400-431`) | 与 pivot 同形的秩矩阵，同特征取**最高**星级；`cnn*` 同时接受 family=`cnn` 旧文件 (`:410-413`) |
| `_draw_single_heatmap` (`:434-504`) | pivot channel×position、缺失位点补 0；`mask = (rank==0)` 仅当存在显著性数据 (`:455-456`)；色阶 linear `v_max=max(0.35,min(1.0,p98|·|))`、非线性 `v_min=0, v_max=max(1e-3,p98)` (`:461-469`)；红色虚线 x=10、深红实线 x=20 标注 Non-Seed/Seed/PAM (`:495-500`) |
| `load_metrics_table` (`:511-536`) | 优先 `summary/metrics_tables/all_experiments.csv`，其次 `summary/all_experiments.csv`，再回落 `analyse.collect_results.collect_batch` |
| `_filter_valid_metrics` (`:539-554`) | 与 `collect_results.filter_valid` 同规则（`|R2|>10 / MAE>10 / RMSE>10`），列缺失则跳过该列 |
| `_prepare_tree_metrics` (`:557-575`) | ids 小写化后按 `(split_type,cell_line,model,environment)` 求 `R2/MAE` 均值（mixed 多 seed 合并） |
| `_demo_tree_metrics` (`:578-597`) | 无指标时的演示树数据（base R2 0.55 / MAE 0.142，增量 ctcf +0.030、dnase +0.050、h3k4me3 +0.020、rrbs −0.010） |
| `combo_name` (`:600-606`) | 排序去重后 `sequence`/`all`(4 因子)/`sequence_a_b` |
| `_build_dedup_combo_tree` (`:626-670`) | **去重组合树**：规范序 `EPI_CHANNELS = CTCF<Dnase<H3K4me3<RRBS`，每步只能加入比路径最大下标更靠后的环境 → 每个组合全树恰好出现一次；`max_env_count=3`（**4 因子 `all` 节点永不出现**）；父子任一实测缺失即剪枝，不生成 N/A 占位 (`:658-659`)；`delta = child - parent` (`:661-664`) |
| `_walk_combo_tree` (`:673-678`) / `_layout_combo_tree` (`:686-704`) / `_check_no_box_overlap` (`:707-726`) | 先序遍历 / 叶槽布局（`LAYOUT_STEP=2.2`，内部节点 x=子节点中心）/ 同层框重叠校验（返回重叠对数） |
| `generate_env_increment_trees` (`:729-773`) | 每 `(split_type,cell_line,model)` 一图，文件名 `tree_{split}_{cell}_{model}.png`（非字母数字→`_`）；缺 `sequence` 基线则跳过该组 (`:757-759`) |
| `_draw_env_increment_tree` (`:776-860`) | 节点三行文本 `env / dR2 / dMAE`；配色根 `#f5b041`、dR2>0 `#a9dfbf`、<0 `#f5b7b1`、=0 `#f9e79f`；`BOX_W_BY_DEPTH` (`:682`) 与 4 层 y 坐标 (`:806`) |
| `generate_epigenetic_comparisons` (`:867-881`) / `_draw_epi_box` (`:884-904`) | 仅表观通道，boxplot 展示 SNR，palette CTCF/Dnase/H3K4me3/RRBS |
| `generate_all_visualizations` (`:911-930`) | 三步调度；打印文案写 “V4” 而文件头写 “V6” (`:916` vs `:3`，版本串不一致) |

## 11.4 analysis/anomaly_treatment.py (489 行) — 两级异常检测报告

| 项 | 内容 |
|---|---|
| 状态 | **Active**（`app/desktop/backend_runner.py:255-262` Step4） |
| 阈值 | `DEFAULT_COEF_THRESHOLD = 10.0` (`:35`)、`DEFAULT_SIGN_TOL = 1e-6` (`:36`) |
| 输入 | `summary/metrics_tables/all_experiments.csv`（缺失回落 `collect_batch`，`:92-117`）；`<batch>/**/*weights*.csv` 或 `**/linear*coefficient*.csv` (`:221-224`) |
| 输出 | `<batch>/summary/anomaly_report.md`（`run_anomaly_treatment` `:407-448`） |

### 函数清单
| 函数 (行) | 作用要点 |
|---|---|
| `parse_info_file` (`:52-61`) | `k: v` 小写化，无类型推断 |
| `normalize_model` (`:64-76`) | 关键字归一到 linear/xgboost/mlp/cnn/transformer |
| `normalize_cell_line` (`:79-85`) | mixed→`none`，空/unknown→`unknown` |
| `load_metrics_table` (`:92-117`) | metrics_tables 优先，回落 `collect_batch` |
| `aggregate_metrics` (`:120-137`) | 按 `(split,cell,model,env)` 求均值 |
| `detect_experiment_level_anomalies` (`:144-208`) | ΔR²/ΔRMSE 同向 → 标记（含 verdict 文案） |
| `detect_data_level_anomalies` (`:215-278`) | `|Weight|>10` 的线性特征明细 |
| `aggregate_data_anomalies` (`:281-299`) | 按 `(cell_line, environment)` 汇总 + 前 3 示例 |
| `_fmt` (`:306-309`) | NaN → `N/A`，否则定长小数 |
| `build_anomaly_report` (`:312-400`) | 三段式 md 报告（含 200 条明细上限） |
| `run_anomaly_treatment` (`:407-448`) | 主流程，写 `<batch>/summary/anomaly_report.md` |
| `main` (`:451-485`) | CLI（`--coef-threshold/--sign-tol/--summary-dir`，`--latest` 未使用） |

### 函数与规则
- `parse_info_file` (`:52-61`) / `normalize_model` (`:64-76`) / `normalize_cell_line` (`:79-85`)：与 11.2 同风格的小写解析与族归一。
- `aggregate_metrics` (`:120-137`)：ids 小写后按 `(split_type,cell_line,model,environment)` 对 `R2/MAE/RMSE/MSE` 求均值（消解 mixed 多 seed）。
- **实验级异常** `detect_experiment_level_anomalies` (`:144-208`)：基线键 `(split_type,cell_line,model)` 取 `environment=="sequence"` 的 `(R2,RMSE)` (`:160-163`)；`delta_R2 = R2-baseline`、`delta_RMSE` 同理；`|delta| <= 1e-6` 跳过 (`:182`)；**同向（同正或同负）判为指标矛盾**并给中文 verdict (`:185-193`)。
- **数据级异常** `detect_data_level_anomalies` (`:215-278`)：仅 `model == 'linear'`；跳过 `bias/intercept` 特征 (`:258`)；`|weight| > 10.0` 记一条（含可选 `t_stat`）。
- `aggregate_data_anomalies` (`:281-299`)：按 `(cell_line, environment)` 聚合异常数、`max|weight|`、前 3 个示例特征。
- `build_anomaly_report` (`:312-400`)：§1 实验级明细表 / §2.1 聚合表 / §2.2 明细（按 `|weight|` 降序，**最多 200 条**，`:373-375`）/ §3 汇总与处置建议（建议复核、检查条件数、`--use-scaler`）。
- `main` (`:451-485`)：`--results-dir/--batch-name/--batch-dir/--latest/--summary-dir/--coef-threshold/--sign-tol`；**`--latest` 未被使用（Unused 参数）**。

> 补充：`analysis/visualize_results.py` 在 git 索引中存在但工作区**已删除**（`git ls-files` 列出、`ls` 缺失），仓库任何文档/代码均不再引用 → **已移除的 Legacy 文件**。

---

# 12. Analyse 证据分析引擎

## 12.1 总览与运行入口

- 包版本 `__version__ = "0.1.0"` (`analysis/__init__.py:16`)；铁律为对训练系统只读、不反向 import (`analysis/__init__.py:13`)。
- CLI 入口：`python -m analysis.pipeline --batch-dir <batch> [--output <out>] [--analysis-plan plan.json]` (`analysis/pipeline.py:327-341`)。`--batch-dir` 必填；`--output` 缺省 `<batch>/summary` (`:335`)；`--analysis-plan` 缺省 `default_plan()` (`:336`)。
- GUI/后端入口：`app/backend/crispr_workspace/analysis.py:202-204` 以子进程 `python -m analysis.pipeline --batch-dir … --output … --analysis-plan …` 调用，任务勾选由 registry 目录渲染，状态读 `analysis_status.json`。
- 编排主函数 `run_analysis(batch_dir, output, plan, config) -> Dict` (`analysis/pipeline.py:64-324`)，只做编排，科学计算分布在各模块 (`:1`)。
- **阶段执行顺序**（源码顺序，非并行）：
  1. 载入统一表并落盘 `tables/experiment_table.csv` (`:80-81`)
  2. 批次级校验 → `tables/metric_inconsistency.csv` (`:84-85`)
  3. `capabilities_from_table` → `validate_analysis_plan` → `ExecutionTask` 列表 (`:88-97`)
  4. `qc` (`:125-126`)
  5. `prediction` (`:128-138`)
  6. `environment_conditional_effect` (`:140-150`)
  7. `environment_main_effect` (`:152-163`)
  8. `sequence_attribution`，并在其内判定 `cnn_ism` (`:165-183`)
  9. `cellline_heterogeneity` (`:185-203`)
  10. `evidence_integration` (`:205-225`)
  11. `hypothesis_generation` (`:227-239`)
  12. 剩余 `pending & selected` 统一置 `unavailable` + reason "analysis module not yet implemented in this build (phase roadmap)" (`:241-247`)
  13. 产物：plan/status/overview/anomaly CSV + 01/08 md (`:249-281`)、02/03 md (`:283-288`)、`execution_log.json` (`:290-298`)
  14. 图形 `render_all(...)`，写回 `execution_log.json` 的 `executed.visualization` 与 `figures` (`:300-323`)
- **三层状态语义** (`analysis/plans.py:1-7`)：`selected`（用户是否选）× `available`（数据/依赖是否支持）→ `status`（实际执行）。`ExecutionStatus` (`plans.py:18-24`) = `pending|running|completed|skipped|unavailable|failed`。约定：`skipped` 表示未选中或依赖不满足（validator 一律给 `skipped`，`:149-153`）；`unavailable` 表示选中但无 runner/能力不足且 reason 必填；`failed` 表示执行异常。
- 防御规则：`_should_run()` 仅对 `status == "pending" and selected and available` 的任务执行 (`:121-123`)；每个阶段独立 `try/except` 并写入 `failed + reason`，不中断其它阶段。

## 12.2 配置与阈值（`analysis/config.py`，全部默认值）

| 配置对象 | 字段 | 默认值 | 行 |
|---|---|---|---|
| `AttributionRuleConfig` | `snr_threshold` | 2.5 | `config.py:12` |
| | `snr_moderate` | 1.8 | `:13` |
| | `snr_weak` | 1.2 | `:14` |
| | `min_effect_size` | 0.005 | `:15` |
| | `method` | `"mean_over_std"` | `:16` |
| `StatisticalRuleConfig` | `fdr_strong` | 0.001 | `:23` |
| | `fdr_moderate` | 0.01 | `:24` |
| | `fdr_weak` | 0.05 | `:25` |
| `ConsensusRuleConfig` | `min_coverage` | 2 | `:33` |
| | `direction_concordance` | 0.80 | `:34` |
| | `unstable_effect_threshold` | 10.0 | `:38` |
| `QCConfig` | `environment_missing_rate_limit` | 0.30 | `:45` |
| | `strict_complete_gate` | 70.0 | `:46` |
| | `ambiguous_detection_only` | True | `:47` |
| `AnalysisConfig` | `bootstrap_iterations` | 2000 | `:58` |
| | `bootstrap_seed` | 2024 | `:59` |
| | `permutation_iterations` | 1000 | `:60` |
| | `random_seed` | 42 | `:61` |

- **Evidence Tier 的权威阈值（2026-09-13 审计后）**：`consensus.min_coverage`、`consensus.direction_concordance`、`consensus.unstable_effect_threshold`、`evidence.min_absolute_delta_r2`、`evidence.ci_crosses_zero_forces_inconclusive`、`evidence.min_bootstrap_iterations`、`statistical.fdr_weak`，以及 `cellline.*`（产生上下文标签）—— 全部在 `evidence/integration.py::environment_evidence_matrix` / `classify_evidence_tier` 消费。`attribution.snr_*`、`attribution.min_effect_size`、`statistical.fdr_strong/fdr_moderate` **只服务 Importance–ΔR² 辅助资产，不参与 Tier**。原 `evidence/rules.py`（死代码）与 `fdr_nominal`/`bootstrap_ci_exclude_zero_alpha`/`cellline_consistent_ratio`/`ci_alpha`/`environment_strong_effect` 已删除或改名，详见 `docs/audit/evidence_tier_code_audit.md` 与 `docs/paper/evidence_tier_provenance.md`。
- `AnalysisConfig.as_dict()` 用 `dataclasses.asdict` (`:63-65`)，键名为 `bootstrap_iterations / bootstrap_seed / permutation_iterations / random_seed`（**与 `analysis/docs/interface_contract.md:44-46` 写的 `bootstrap_n/permutation_n` 不一致**）。

## 12.3 schemas 与 Evidence 标签（`analysis/schemas.py`）

- 术语纪律（模块 docstring `:3-9`）：`Effect` / `Importance` / `StatisticalEvidence` 三层互不冒充；禁止对 SHAP/IG/ISM/Gain 原始值做 FDR 后称 statistical significance；SNR≥2.5 只能叫 attribution/robustness strength。
- `EvidenceStrength(str, Enum)` (`:21-37`)：`STRONG/MODERATE/WEAK_STATISTICAL`、`STRONG/MODERATE/WEAK_ATTRIBUTION`、**`STRONG_MUTATION_EFFECT`**（`:28`，"Strong mutation effect"）、`PREDICTIVE_DEPENDENCE`、`CONVERGENT`、`DIRECTIONALLY_CONSISTENT`、`CONTEXT_CONSISTENT`、`SUPPORTING`、`STABLE`、`UNCERTAIN`、`INCONCLUSIVE`、`NO_CURRENT_EVIDENCE`（注释明确"不等于 no effect"，`:37`）。
- `EvidenceTier` (`:40-45`)：`TIER1 = "Tier 1: Strong convergent evidence"`、`TIER2 = "Tier 2: Moderate convergent evidence"`、`TIER3 = "Tier 3: Model-specific / exploratory evidence"`、`INCONCLUSIVE`、`NONE = "No current evidence"`。
- `TaskStatus` (`:48-56`) 与 `ExecutionStatus` 重复，且**全仓 0 引用（Unused）**；pipeline 用 `plans.ExecutionStatus` 的字符串值。
- `EvidenceClass` (`:59-68`)：`statistical / attribution / predictive / robustness / cross-model / context / mutation effect`。
- 记录类型：`ExperimentRecord` (`:74-96`)、`AttributionRecord` (`:99-114`，含 `method` 枚举注释 `linear/xgboost_treeshap/mlp_ig/cnn_ism/cnn_ig/transformer_attention`)、`StatisticalEvidence` (`:117-132`，字段缺失即 `None`，"无检验则字段留空, 禁止伪造")、`EnvironmentEffect` (`:135-151`，含 `paired_cohort: bool = True`)、`CellLineEffect` (`:154-164`)、`MotifRecord` (`:167-180`)、`EvidenceRecord` (`:183-200`)。
- 生产链路真正落盘的只有 DataFrame 路径；`ExperimentRecord` 仅 `iter_experiment_records` 构造、`MotifRecord`/`CellLineEffect`/`StatisticalEvidence`/`EvidenceClass` **无生产引用**（dataclass 公开 API / roadmap）。

### 标签 → 生产使用映射（grep 实证）
| 标签/类型 | 生产消费点 | 判定 |
|---|---|---|
| `EvidenceStrength.STRONG/MODERATE/WEAK_ATTRIBUTION` | 仅 `rules.classify_attribution`（无生产调用方） | 已实现未接线 |
| `EvidenceStrength.STRONG/MODERATE/WEAK_STATISTICAL` | 仅 `rules.classify_statistical_by_fdr`（无生产调用方） | 已实现未接线（FDR runner 未挂载） |
| `EvidenceStrength.STRONG_MUTATION_EFFECT` | `rules.classify_mutation_effect`（无调用方） | 孤儿接口，待 CNN ISM runner |
| `CONVERGENT` / `DIRECTIONALLY_CONSISTENT` / `CONTEXT_CONSISTENT` / `SUPPORTING` / `STABLE` / `UNCERTAIN` / `PREDICTIVE_DEPENDENCE` | 无 | 预留（`interface_contract.md:84` 描述的标签尚未落到产物） |
| `EvidenceTier.TIER1/2/3/INCONCLUSIVE/NONE` | `classify_evidence_tier` → `environment_evidence_matrix.evidence_tier`（CSV/md/图） | **实际使用** |
| `EvidenceClass` / `MotifRecord` / `CellLineEffect` / `StatisticalEvidence` | 无 | 公开 API / roadmap |
| `AttributionRecord` | 无（抽取直接产 DataFrame） | 结构等价物，未实例化 |

## 12.4 plans / registry / capabilities

- `AnalysisPlan` (`plans.py:68-105`)：`plan_version="1.0"`、`run_qc`、`run_prediction_analysis` 与 5 个子计划 `EnvironmentPlan`(`:27-34`：enabled/conditional_effect/main_effect=True，interaction/shapley/anova=False)、`SequencePlan`(`:37-44`：enabled/position_attribution/ism/motif_discovery=True，motif_enrichment=False)、`CellLinePlan`(`:47-52`)、`StatisticsPlan`(`:55-59`，bootstrap/hypothesis_testing/fdr_correction=True)、`EvidencePlan`(`:62-65`)；`to_json_dict/save/load/from_dict`。
- `Capabilities` (`plans.py:115-133`)：数据可得性快照（n_cell_lines / n_environment_factors / n_models / has_* / environment_factorial_observations / replication_per_cellline / reasons）。**注意 `pipeline.capabilities_from_table` (`pipeline.py:43-61`) 只从表里推 model 关键字与 cell_line 数**，`n_environment_factors=4`、`environment_factorial_observations=16`、`replication_per_cellline=4` 是**硬编码常量**（`:51,59,60`），并非由数据推导，与 docstring "由实际数据推导" (`plans.py:117`) 不符。
- `validate_analysis_plan(plan, caps)` (`plans.py:136-193`) 返回 16 个任务的 `{task_id, selected, available, reason, status}`；`status = "skipped"` 当且仅当未选中或 `available=False` 或依赖不满足 (`:149-153`)，**validator 永不产出 `unavailable`**（由 pipeline 兜底）。
- `ExecutionPlan` (`plans.py:211-241`)：`to_status_dict()` 只序列化 `plan_version/started_at/completed_at/tasks[{task_id,selected,available,status,reason}]`（`:220-235`）；`save_status()` 写 JSON。`ExecutionTask` 的 `dependencies/started_at/completed_at` **不落盘**。
- **task id 全集（16 个，`plans.py:156-192` 与 `registry.py:53-76` 一致）**：`qc, prediction, environment_conditional_effect, environment_main_effect, environment_anova, environment_shapley, sequence_attribution, cnn_ism, motif_discovery, motif_enrichment, cellline_heterogeneity, bootstrap, hypothesis_testing, fdr_correction, evidence_integration, hypothesis_generation`。
- `registry.py`：`AnalysisTaskSpec(task_id,name,category,dependencies,runner,basic,description)` (`:8-16`)；`register_analysis` 重复注册抛 `KeyError` (`:31-32`)；`registered_tasks()`/`registry_to_dict()` (`:40-49`)。内置 15 条声明注册（无 `fdr_correction`，`:53-76`），**所有 `runner=None`**，注释说明 runner 未注册、availability 另由 validator 判定 (`:52`)。
- registry 的消费者是后端 GUI 目录（`app/backend/crispr_workspace/analysis.py:59-63`），**pipeline 内部不读 registry**（阶段是硬编码顺序）。
- 分类/依赖要点：`environment_anova`(statistics, 依赖 environment_main_effect, `basic=False`)、`environment_shapley`(biology, 依赖 conditional)、`motif_discovery`(biology, `basic=False`)、`motif_enrichment`(statistics, 依赖 motif_discovery)、`bootstrap/hypothesis_testing`(statistics, `basic=False`)、`evidence_integration`(evidence, 依赖 sequence_attribution + environment_conditional_effect)、`hypothesis_generation`(evidence, 依赖 evidence_integration)。

## 12.5 pipeline 逐阶段

| # | task id | 执行函数/逻辑 | 产出文件 | 失败/unavailable 语义 |
|---|---|---|---|---|
| 0 | （前置，非任务） | `load_experiment_table` (`pipeline.py:80`)、`coverage_summary` (`:253`) | `tables/experiment_table.csv` | 载入失败抛 `RuntimeError/ValueError`（`data/loaders.py:52,61`），整批中止 |
| 0 | （前置） | `validate_metric_consistency` (`:84`) | `tables/metric_inconsistency.csv` | 异常只标记不删除 (`validation.py:4-5`) |
| 1 | `qc` | 仅 `_finish("qc")` (`:125-126`)，实际 QC 已在 0 步落盘 | `summary/00_overview.md`、`01_data_quality.md`、`tables/anomaly_report.csv` | 无异常分支；报告永远生成 |
| 2 | `prediction` | `performance_by_model_split` + `loco_performance` (`:132-133`) | `tables/prediction_summary.csv`、`loco_performance.csv`、`summary/02_prediction_generalization.md`（仅当 `prediction_ok`，`:283-285`） | 异常 → `failed + "prediction analysis failed: …"` (`:137-138`) |
| 3 | `environment_conditional_effect` | `compute_conditional_increments` + `summarize_conditional` (`:143-144`) | `tables/environment_conditional_delta_r2.csv` | 异常 → `failed` (`:148-150`) |
| 4 | `environment_main_effect` | 依赖 `cond_raw`；`compute_main_effects` (`:152-163`) | `tables/environment_main_effects.csv` | `cond_raw is None` → `unavailable + "environment_main_effect requires conditional effect data"` (`:154-155`)；异常 → `failed` |
| 5 | `sequence_attribution` | `extract_attribution_table` + `build_motif_summary_md` (`:168-173`) | `tables/attribution_summary.csv`、`summary/04_sequence_motifs.md` | 异常 → `failed + "attribution extraction failed: …"`（此时 04 md 不生成） |
| 5b | `cnn_ism` | 无独立计算：由 attribution 表 `model` 是否含 `cnn` 决定 (`:175-181`) | 无独立文件（数据在 attribution_summary.csv 的 `cnn_ism` 方法行） | 无 CNN 行 → `unavailable + "no CNN importance outputs in batch"` |
| 6 | `cellline_heterogeneity` | 依赖 `main_df`；`summarize_environment_by_cellline` + `consistency_counts` (`:192-198`) | `tables/cellline_effects.csv`、`summary/05_cellline_heterogeneity.md` | `main_df is None` → `unavailable + "cellline heterogeneity requires environment main effects"` |
| 7 | `evidence_integration` | 依赖 `main_df`；`environment_evidence_matrix(main_df, cellline_df, config)` (`:211-213`) | `tables/evidence_matrix.csv`、`summary/06_evidence_integration.md` | `main_df is None` → `unavailable`；异常 → `failed` |
| 8 | `hypothesis_generation` | 依赖非空 `evidence_matrix`；`build_hypotheses_md` (`:227-236`) | `summary/07_biological_hypotheses.md` | 空矩阵 → `unavailable + "hypothesis generation requires non-empty evidence matrix"` |
| 9 | 剩余 pending&selected | 统一置 `unavailable` (`:241-247`) | 无 | reason 固定为 phase roadmap 文案 |
| 10 | `visualization`（不在 registry） | `render_all(...)` (`:300-317`) | `figures/<02..06>/*.png` + `execution_log.json.figures` | 异常 → `executed["visualization"] = "failed: …"`，**不阻断**已完成的科学计算 (`:318-323`) |

- `_finish()` 语义 (`:109-116`)：仅在传入非空 reason 时覆盖原 reason；**空 reason 会保留 validator 给的旧 reason**，因此实跑 `analysis_status.json` 中 `environment_conditional_effect`（completed）仍带 reason `"environment features unavailable"`、`cellline_heterogeneity` 带 `"need >=2 cell lines"`、`hypothesis_generation` 带 `"hypothesis_generation requires evidence integration"` —— 状态与 reason 语义轻微错配（**不一致，见 §14**）。
- 未实现但被选中的任务在真实批中为：`motif_discovery`、`bootstrap`、`hypothesis_testing`、`fdr_correction` → 全部 `unavailable`；`environment_anova`、`environment_shapley`、`motif_enrichment` 默认未选中 → `skipped`。统计：`status_counts = {completed: 9, unavailable: 4, skipped: 3}`（`execution_log.json`）。

## 12.6 data 层

### `analysis/data/loaders.py`
- 模块契约 (`:1-7`)：优先 `1) <batch>/summary/metrics_tables/all_experiments.csv` → `2) <batch>/summary/all_experiments.csv` → `3) legacy 目录扫描`；字段差异用 adapter 而非改训练输出。
- `resolve_batch_dir(batch_dir, results_root="results")` (`:22-31`)：路径存在即用，否则取 `results` 下 mtime 最新非 `summary` 子目录；不存在抛 `FileNotFoundError`。
- `load_experiment_table(batch_dir)` (`:38-87`)：
  - 逐个候选读取，空表继续下一候选 (`:53-56`)；全失败则 `_legacy_scan_experiments` (`:58`)，来源写 `source_table`（`:82`）。
  - id 列**大小写归一**：`lower2col` 查 `model/split_type/cell_line/environment` + `random_seed/n_train/n_valid/n_test`；缺失时 `environment → "unknown"`，其余 → `pd.NA` (`:67-74`)。
  - 指标列**保持 canonical 大写**（`R2/MAE/RMSE/Pearson/Spearman/MSE`）并 `pd.to_numeric(errors="coerce")` (`:76-81`)；缺失补 NaN。
  - 最终 schema 列序：`REQUIRED_ID_COLUMNS + [random_seed,n_train,n_valid,n_test] + METRIC_COLUMNS + [source_table, run_name]` (`:84-86`)；**原始多余列不再暴露**。
- `_legacy_scan_experiments` (`:90-112`)：逐实验目录读 `*info*.txt`（首个）+ `*_metrics.json`（排除 `validation`，`:128`），只填 `model/split_type/cell_line/environment/random_seed` 与指标，`cell_line` 取 `info.cell_line`（**不做 mixed→none 归一**，与引擎其它处不一致）。
- `iter_experiment_records` (`:134-158`)：逐行构造 `ExperimentRecord`；`architecture` 取 `sequence_kernel` 列（统一表中不存在 → None）；数值缺失 → 0（seed/n）或直接 `float()`（指标列已保证 NaN 存在）；**当前无生产调用点（公开 API）**。
- `coverage_summary` (`:161-173`)：experiment_count、valid_count（R² 非 NaN 数）、models/cell_lines/environments/splits 去重排序列表。

### `analysis/data/validation.py`
- 规则 (`:1-5`)：同一 test cohort 下 `R²=1-SSE/SST`、`RMSE=√(SSE/n)`，故 ΔR² 与 ΔRMSE 不应同号；**只标记不一致，不删除实验**（Metric inconsistency ≠ 实验无效）。
- `metric_consistency_flags(delta_r2, delta_rmse, tol=1e-9)` (`:14-26`)：同增 → `metric_inconsistency_same_increase`，同减 → `metric_inconsistency_same_decrease`，否则空列表。
- `validate_metric_consistency(table, tol=1e-9)` (`:29-63`)：基线键 = `(split_type, cell_line, model, random_seed)`（`:37-40`，注释明确"mixed 多 seed 绝不跨 seed 比较"）；仅对 `environment != "sequence"` 同 seed 配对行算 Δ；输出列 `row, experiment, flags, delta_r2, delta_rmse`（Δ 保留 6 位，`:58-59`）；空结果返回**带表头**的 DataFrame (`:62`)。

## 12.7 statistics

- `effect_size.py`：
  - `delta_pair(baseline, expanded)` (`:12-14`) = `expanded - baseline`（正=提升）。
  - `compute_paired_increment(baseline_metric, expanded_metric, baseline_n=None, expanded_n=None, tolerance=0)` (`:17-32`)：样本量差超容差 → `(NaN, False)`，注释"paired_ok=False 时增量不得用于科学归因" (`:27`)。
  - **生产环境模块未调用它**（直接相减，`environment/incremental_effect.py:84`）；仅单测使用。
- `multiple_testing.py`：`bh_fdr(p_values)` (`:13-35`) 标准 BH step-up，从最大 p 逆向取 `min` 保证 q 单调非降 (`:31-34`)，`min(q,1.0)` 截断；非有限 p 原位 NaN (`:24-25`)；docstring 强调"只允许对同一假设检验 family 校正；线性系数、ANOVA、motif enrichment 分属不同 family，不得混入同一个 FDR" (`:3-5`)。
- `bootstrap.py`：
  - `BootstrapResult` (`:13-22`)：`estimate/ci_low/ci_high/bootstrap_std/n_iterations/seed/excludes_zero/available`；注释"CI 缺失用 unavailable, 绝不用 0 冒充" (`:22`)。
  - `bootstrap_ci(data, estimator, n_iterations=2000, seed=2024, alpha=0.05)` (`:52-65`)：先剔除 `None/非有限` 值；**有效样本 < 3 → `available=False` 且所有数值字段 None** (`:63-64`)；否则 percentile CI `[α/2, 1-α/2]`，`bootstrap_std` 用 `ddof=1` (`:38-44`)。
  - `bootstrap_difference_ci(baseline, expanded, metric_fn, …, paired=True)` (`:68-107`)：`paired=True` 时**逐对重采样** `metric(b[idx]) - metric(a[idx])`；任一侧 <3 或 `paired and a.size != b.size` → `available=False` (`:85-88`)；`paired=False` 两侧独立重采样（仅供探索）(`:96-99`)；`excludes_zero = not (lo <= 0 <= hi)` (`:47,106`)；语义明确为"稳定性/不确定性证据, 不等于统计显著或因果" (`:81`)。
- `hypothesis_tests.py`：
  - 规则 (`:3-4`)：对 attribution 做显著性前必须先建 null distribution（permutation/bootstrap），再算 p，之后才允许 FDR；SNR 本身不是 p。
  - `PermutationTestResult` (`:16-22`，含 `null_stats_available`)。
  - `permutation_test_for_effect(effect_values, null_effect=0.0, n_permutations=1000, seed=2024, one_sided="greater")` (`:25-53`)：`arr.size < 3` → `p=NaN, null_stats_available=False` (`:38-40`)；中心化 `arr - mean + null_effect` 后重排 (`:42-45`)；`p = (count+1)/(n_permutations+1)` (`:52`)；支持 `greater/less/two_sided`（`else` 分支为双侧，`:50-51`）。
  - `anova_interface(data, factors, response, design_info=None, config=None)` (`:56-73`)：**占位实现，恒返回 `{"available": False, "reason": "ANOVA 实现位于 Phase 3 (factorial_analysis), 当前版本未启用", 其余字段 None}`**；docstring 承诺的输出 schema `factor/effect/F_statistic/p_value/FDR/effect_size/CI` 仅为字段占位。
  - `__all__` 导出 `bh_fdr, PermutationTestResult, permutation_test_for_effect, anova_interface` (`:76`)；`permutation_test_for_effect`、`anova_interface`、`bh_fdr` 在 pipeline 中**均无 runner 调用**（task `hypothesis_testing`/`fdr_correction` 恒 `unavailable`）。

## 12.8 environment 增量与主效应（`analysis/environment/incremental_effect.py`）

- 设计契约 (`:1-8`)：16 组合 = 4 环境因子 2^4 全因子；`ΔR²(e|S) = metric(S+e) - metric(S)`，且 `(S+e, S)` 必须来自同一 `(split_type, cell_line, model, seed)` 分组（同 eligible cohort / 同 test indices）；**不同 seed 绝不跨 seed 配对**。
- 常量：`ALL_ENVIRONMENTS = {ctcf,dnase,h3k4me3,rrbs}` (`:16`)、`GROUP_COLS = [split_type, cell_line, model, random_seed]` (`:17`)、`METRIC_PAIRS = [(R2,delta_r2),(MAE,delta_mae),(RMSE,delta_rmse)]` (`:18`)。
- `parse_environment_set(environment)` (`:21-31`)：`sequence → ∅`；`all → 4 因子`；否则按 `_` 切分、去掉前导 `sequence`、仅保留合法因子；`combo_name` (`:34-39`) 反向拼名（排序后 `sequence_a_b` / `all`）。
- `compute_conditional_increments(table)` (`:51-90`)：按 `GROUP_COLS` 分组；组内按 `environment` 再分组建索引；对每对 `(background, candidate)` 仅当 `len(cand_set - bg_set) == 1` 且 `bg_set ⊆ cand_set` 时成立 (`:67-68`)；**同 key 出现多行直接拒绝（不做隐式平均）** (`:70-71`)；任一指标 NaN 则跳过 (`:74`)；输出长表列 = `GROUP_COLS + [environment_added, background, background_set, delta_r2, delta_mae, delta_rmse]`，Δ 为 `float(c - b)` (`:83-84`)。
- `summarize_conditional(raw)` (`:93-106`)：按 `(split, cell, model, environment_added, background, background_set)` 聚合跨 seed 均值，列 `delta_r2_mean/delta_mae_mean/delta_rmse_mean/n_paired`，Δ 保留 6 位。
- `compute_main_effects(conditional_raw)` (`:109-133`)：**两级平均** —— 先按 `(…, random_seed, environment_added)` 对背景求均值（`n_backgrounds` 计数），再按 `(split, cell, model, environment)` 跨 seed 求均值；输出 `main_r2_delta/main_mae_delta/main_rmse_delta/n_seeds/n_backgrounds_avg`，并把 `environment_added` 重命名为 `environment` (`:130`)。
- `compute_pair_interactions(conditional_raw)` (`:136-170`)：成对交互 `I(a,b) = mean(Δ(a|S+b)) - mean(Δ(a|S∌b))`（`:155-161`）；输出 `(split, cell, model, random_seed, factor_a, factor_b, interaction_r2, n_with_b, n_without_b)`。**无生产调用（plan `environment.interaction=False`），仅预留（Unused/roadmap）**。
- 单测锚点：`tests/test_environment.py:14-23` 构造 `sequence/sequence_ctcf/sequence_dnase/sequence_ctcf_dnase` 四行，断言 4 条配对增量分别为 +0.03 / −0.05 / +0.10 / +0.02，主效应 ctcf = 0.065、dnase = −0.015（`:41-44,65-66`）；跨 seed 时每组合恰好 2 条（`:46-55`）。
- 真实批产物：`environment_conditional_delta_r2.csv` 2016 行、`environment_main_effects.csv` 252 行（每因子 63 行 = 7 模型 × 9 (split,cell) 组合）。

## 12.9 attribution 抽取

### 列适配 `analysis/attribution/columns.py`
- `_ROW_SPECS` (`:11-32`) 定义 **7 个方法**（每族可多方法）：`linear_coefficient`(linear)、`xgboost_treeshap`+`xgboost_gain`(xgboost)、`mlp_ig`(mlp)、`cnn_ism`+`cnn_ig`(cnn)、`transformer_attention`(transformer)；每项 = `(method, importance候选, snr候选, effect候选, entropy候选)`，按候选顺序取首个存在列。
- `FEATURE_ID_CANDIDATES=["feature"]`、`POSITION_CANDIDATES=["position","pos"]`、`CHANNEL_CANDIDATES=["channel","ch"]` (`:35-37`)；`family_from_model` (`:40-52`) 按关键字 `linear/xgb/mlp/cnn/trans` 归族；`pick_column` (`:55-61`) 忽略大小写命中。

### 行抽取 `analysis/attribution/extractors.py`
- `SKIP_NAME_TOKENS = ("pred","metric","history","summary","biomarker","training")` (`:18`)；`CANONICAL_COLUMNS` (`:19-21`) = `feature, channel, position, model, architecture, split_type, cell_line, environment, method, importance, snr, effect, attention_entropy, source_file`（**无 p/FDR 字段**，单测 `test_attribution.py:58-59` 显式断言 `p_value/fdr/permutation` 不外泄）。
- `_parse_position_channel(feature)` (`:24-38`)：正则 `pos_?(\d+)`；`one_based = m.start()==0 and fn.lower().startswith("pos")` (`:31`) —— 即 **`pos20_G` 取 20（1-based）**，**`G_pos_20` / `T_pos_20` 视为 0-based 索引 → 21**；通道取 pos 片段之外尾部按 `[_\-.]` 切分的首个非数字 token。实测：`pos20_G→(20,'G')`、`A_pos_0→(1,'A')`、`T_pos_20→(21,'T')`。
- `extract_attribution_table(batch_dir)` (`:53-139`)：`batch.glob("**/*.csv")` 排序遍历；跳过文件名含 SKIP token 者 (`:57-59`) 与父目录名为 `summary` 者 (`:61-62`)；模型族由 `info.model` 或目录名推 (`:64-65`)；`mixed → cell_line="none"` (`:81-82`)；CNN 写 `architecture = f"cnn{k}3"`（`sequence_kernel` 默认 3，`:86-91`）；跳过 `bias/intercept`/空特征 (`:102`)；linear 若 effect 存在则 `importance = abs(effect)`（importance 缺省时，`:110-111`）；数值列统一 `to_numeric(errors="coerce")` (`:137-138`)；空结果返回带 `CANONICAL_COLUMNS` 的空表 (`:135`)。
- 产出摘要 `analysis/attribution/summary.py`：`top_attribution_features(table, top_n=10)` (`:9-26`) 按 `(model, method, feature)` 求 `mean|importance|`/`mean importance`/`n_contexts`，再每 `(model, method)` 取 top-N；`build_motif_summary_md` (`:29-50`) 写 04 md，末尾三条声明：本表是 importance/attribution 证据、不做统计显著标签；ISM 是核苷酸替换效应；motif discovery/enrichment/known-motif 比较由后续 Phase 提供（当前 unavailable）(`:47-49`)。**`:35-36` 计算的 `coverage` DataFrame 未被使用（死代码）**。

## 12.10 cell-line 一致性

- `analysis/cellline/consistency.py`：模块 docstring 明确"不做 predictive R² 不同 = biological mechanism 不同式解读" (`:3-5`)。
- `summarize_environment_by_cellline(main_effects, effect_column="main_r2_delta", factor_column="environment", consistent_ratio=0.75)` (`:20-54`)：按 `(split_type, model, factor)` 分组，把各 cell_line 的 effect 收成 `cell_map`，调用 `classify_cellline_consistency` 得 `(label, direction)`，输出列 `split_type, model, factor, factor_type="environment", n_cell_lines, consensus_direction, context_label, effect_<cell>…`。
- `consistency_counts(summary)` (`:57-60`)：`context_label` 频次 dict，供 05 md 与 `_md_table` 使用。
- **一致性判定规则** `analysis/evidence/integration.py:41-62`：先剔除非有限与 0 方向 (`:52-53`)；**已知方向 < 2 → `("Uncertain", None)`** (`:54-55`)；存在任何少数方向 → `"Context-conflicting"`（返回多数方向，`:58-59`）；多数占比 ≥ `consistent_ratio(0.75)` → `"Context-consistent"`（`:60-61`）；否则 `"Context-dependent"`（`:62`）。
  - **代码事实：`Context-dependent` 在当前规则下不可达** —— 方向全同则占比恒为 1.0 ≥ 0.75 → consistent；方向不全同则 minority 非空 → conflicting。实测 05 md 标签分布仅 `Context-conflicting: 50 / Uncertain: 28 / Context-consistent: 6`，可作旁证（详见 §14）。
- pipeline 调用 `summarize_environment_by_cellline(main_df)` **未传 `config.consensus.cellline_consistent_ratio`**（`pipeline.py:195`），实际使用函数默认 0.75；两值相同故当前无行为差异，但配置未接线。

## 12.11 evidence 整合

### `analysis/evidence/rules.py`（标签规则，阈值全部来自 config）
- `classify_statistical_by_fdr(fdr, config)` (`:12-26`)：NaN → None；`<0.001` STRONG、`<0.01` MODERATE、`<0.05` WEAK、否则 None（docstring：仅用于真实假设检验输出的 FDR）。
- `classify_attribution(snr, effect_magnitude, min_effect_size=None, config)` (`:29-53`)：任一参数 NaN → None；**`|effect| < min_effect_size(0.005)` → None（所有级别统一的"足够效应量"门槛，防止 effect 极小但方差更小导致 SNR 虚高）** (`:43-46`)；`snr>=2.5 → Strong attribution`、`>=1.8 → Moderate`、`>=1.2 → Weak`、否则 None。
- `classify_mutation_effect(snr, delta_mean, config)` (`:56-67`)：`snr>=2.5 且 |delta_mean|>=0.005` → `EvidenceStrength.STRONG_MUTATION_EFFECT`，否则 None；**无任何调用方（孤儿接口，roadmap 待 CNN ISM runner 接线）**。
- `direction_of(effect)` (`:70-73`)：`'+'/'-'/'0'/None`。
- **`rules.py` 的三个 classify 函数在 pipeline 中无消费点**（仅 `tests/test_core.py:84-102` 使用）→ 标签体系已实现但未接入证据矩阵产出。

### `analysis/evidence/integration.py`（证据矩阵）
- `direction_concordance(effects)` (`:16-26`)：去零后多数方向占比；无有效方向 → None。
- `classify_cellline_consistency(...)` (`:41-62`)：见 §12.10。
- **Tier 规则 `classify_evidence_tier(...)`** (`:65-87`)，签名 `(applicable_model_count, supporting_model_count, concordance, strong_stat_or_attribution, ci_crosses_zero, conflicting_direction=False, config)`：
  1. `conflicting_direction` 或 `ci_crosses_zero is True` → **`INCONCLUSIVE`** (`:75-76`)；
  2. `supporting_model_count >= min_coverage(2)` **且** (`concordance is None` 或 `concordance >= 0.80`) **且** `strong_stat_or_attribution` → **`TIER1`** (`:77-80`)；
  3. `supporting_model_count >= 2` → **`TIER2`** (`:81-82`)；
  4. `supporting_model_count == 1` 且 strong → **`TIER3`** (`:83-84`)；
  5. `applicable_model_count == 0` → **`NONE`** (`:85-86`)；否则 `INCONCLUSIVE`。
- `environment_evidence_matrix(main_effects, cellline_summary=None, config)` (`:112-182`)：
  - **数值不稳定隔离** (`:129-133`)：`|main_r2_delta| < unstable_effect_threshold(10.0)` 才进入矩阵（严格小于；等于 10 也排除）；隔离而非删除实验。
  - 先按 `(model, environment)` 求均值 (`:134-135`)，再逐 factor：`finite` = 有效效应模型集 (`:138-139`)；`concordance`；`effect_gate_pass = any(|e| >= evidence.min_absolute_delta_r2(0.01))` (`:142-146`)；`overall_effect = mean(finite)` (`:147`)；`supporting` = 与总体多数符号相同的模型数 (`:149-151`)。
  - **Context 冲突降级**：若该 factor 在 cellline_summary 中的 `context_label` 众数为 `"Context-conflicting"` → 直接 `INCONCLUSIVE`，不再走 Tier 判据 (`:152-159`)。
  - 输出列：`feature, feature_type="environment", applicable_models, coverage, direction_concordance, cell_line_consistency, overall_effect, model_effects, unstable_rows_excluded, effect_gate_pass, statistical_gate_pass, strong_evidence_basis, min_absolute_delta_r2, permutation_selection, ci_low, ci_high, ci_excludes_zero, n_bootstrap, bootstrap_status, permutation_p, permutation_fdr, permutation_status, evidence_tier`。
  - `applicable_models` 与 `coverage` 分母 = 有有限效应的模型数（注释"Coverage 分母 = applicable models (不固定 5)"，`reports/markdown_report.py:110`）。
- `evidence_record_row(record)` (`:90-109`)：把 `EvidenceRecord` 展成 CSV 行（None 表示不可用/未测，**不填 0**）；**无调用方（Unused）**。
- `tier_from_value(value)` (`:185-189`) 供 07 md 反查枚举（唯一生产调用点 `markdown_report.py:116,124`）；`direction_of` (`:192-194`) 公开包装，无外部调用。
- 真实批结果：4 个环境因子 coverage 均 7、`direction_concordance` 0.714/0.857、`cell_line_consistency = Context-conflicting` → **4 行全为 `Inconclusive`**，故 07 md 不生成任何候选假设（"No current evidence ≠ No effect"）。

### `analysis/evidence/hypothesis.py`（受控语言）
- 禁令 (`:1-4`)：禁止 `causes / proves / determines`，只允许 `associated / suggests / supports / candidate factor / context-dependent / testable hypothesis`；`_ALLOWED_VERBS` (`:12`) 仅作文档化常量（未被代码断言使用）。
- `generate_hypotheses_for_record(record)` (`:15-73`)：方向词 `positively/negatively/not clearly` (`:19-24`)；Tier1/2 → "strongly supports"（Tier1）/"supports"（Tier2），若 `cell_line_consistency == "Context-conflicting"` 改用 "suggests context-dependent contributions" (`:29-37`)；Tier3 → 单模型提示 + 需 targeted follow-up (`:38-42`)；Inconclusive → "effects were unstable or directionally conflicting" (`:43-47`)；其余 → "No current evidence in this dataset supports a stable role …; this is not evidence of absence of effect." (`:48-52`)。
- 每条假设固定 8 个字段 (`:63-73`)：`feature, hypothesis, observed_evidence, effect_size, uncertainty, supporting_models, supporting_statistical_test, possible_biological_interpretation, suggested_validation_experiment`；`uncertainty` 仅在 `record.note == "ci_crosses_zero"` 时写 "CI crosses 0"，否则 "see CI columns" (`:68`)；缺失值一律 "unavailable"（不编造）。

## 12.12 reports & visualization

### `analysis/reports/markdown_report.py`（builder → 文件）
| builder (行) | 产出 | 要点 |
|---|---|---|
| `build_overview_md` (`:55-83`) | `00_overview.md` | 实验数/有效数/models/cell lines/environments 数/splits/矛盾行数；**Analysis Plan 清单以 `✓ ☐ ⊘ ⚠ ✗ ⟳` 标注 selected/available/status** (`:73-79`)；执行说明含"PFI/LOFO 若训练端未生成一律 Unavailable" (`:82`) |
| `build_data_quality_md` (`:149-164`) | `01_data_quality.md` | experiments/valid；`cell_line × environment` 覆盖交叉表 (`:153-156`)；metric inconsistency 明细；注明 Eligible/Limited/Ineligible 判定在训练前由 `data_QC` 输出 (`:162-163`) |
| `build_prediction_md` (`:33-40`) | `02_prediction_generalization.md` | 模型×划分性能表 + LOCO 表 + "不将预测 R² 直接等同于生物学重要性" (`:39`) |
| `build_environment_md` (`:43-52`) | `03_environment_effects.md` | 声明配对 cohort；条件 ΔR² 表 + 主效应表；"Environment contribution ≠ Model SHAP" (`:51`) |
| `build_cellline_md` (`:86-98`) | `05_cellline_heterogeneity.md` | 标签分布 + feature×cell-line 表；"≠ biological mechanism 差异" (`:96-97`) |
| `build_evidence_md` (`:101-111`) | `06_evidence_integration.md` | Evidence Matrix + Effect/Importance 分离声明 + coverage 分母说明 |
| `build_hypotheses_md` (`:114-146`) | `07_biological_hypotheses.md` | 仅 Tier1/2/3 生成假设；无 Tier1-3 时写 "No current evidence ≠ No effect" (`:145`) |
| `build_anomaly_md` (`:167-180`) | `08_anomaly_report.md` | 类型说明 + `numerical_instability_excluded_from_evidence: N` 上下文行数 + inconsistency 明细 + machine-readable 指引 |
| （由 `attribution/summary.build_motif_summary_md`） | `04_sequence_motifs.md` | 见 §12.9 |
| `_md_table` (`:19-30`) | — | 通用管道表，float 用 `round_digits` 格式化；空表输出 `_空表_` |

### `analysis/visualization/`（新包，`render_all`）
- 原则 (`__init__.py:1-3`)：图只从统一 tables/DataFrame 重建，不自行扫描实验目录；`matplotlib.use("Agg")` (`:12`)。
- `render_all(figures_dir, prediction_df, loco_df, conditional_summary, main_effects, attribution_table, cellline_df, evidence_matrix)` (`:25-52`)：先 `style_figure()`，创建 `02_prediction/03_environment/04_sequence/05_cellline/06_evidence` 五个目录，再按数据是否存在逐主题 `render`，返回 PNG 路径列表（缺数据即跳过该主题）。
- `core.style_figure()` (`core.py:10-13`)：seaborn whitegrid + DejaVu Sans；`save_figure(fig, path, dpi=150)` (`:16-21`)：`tight_layout` + `bbox_inches="tight"` + 关闭 figure，返回路径字符串（**默认 dpi=150，与文档/README 声称 "300dpi" 不符**）。
- 各主题产物：
  - `performance_plots.render` (`:13-35`)：需 `{model,split_type,R2_mean}` → `model_performance.png`；`loco_df` 需 `{model,cell_line,R2}` → `loco_performance.png`。
  - `environment_plots.render` (`:15-43`)：需 `{environment_added,background,delta_r2_mean}` → `conditional_delta_r2_heatmap.png`（`RdBu_r`, center 0）；需 `{environment,main_r2_delta}` → `environment_main_effects.png`（负值红/正值绿）。
  - `attribution_plots.render` (`:15-38`)：需 `{method,channel,position,importance}`；每 method 一张 `position_attribution_<method>.png`（`YlGnBu`，通道顺序 A,C,G,T,CTCF,Dnase,H3K4me3,RRBS）。
  - `cellline_plots.render` (`:13-41`)：`context_consistency.png`（标签计数）+ `feature_cellline_effect.png`（`effect_*` 列 melt 后 stripplot）。
  - `evidence_plots.render` (`:13-36`)：`evidence_tier_summary.png`（tier 计数）+ `evidence_matrix_heatmap.png`（coverage/concordance/overall_effect，`viridis`，annot `.3f`）。
- 兼容桥 (`__init__.py:56-84`)：`_load_legacy_viz_module()` 以 `importlib.util.spec_from_file_location("analyse._legacy_viz_module", analysis/visualization.py)` 惰性加载旧模块；`__getattr__("generate_all_visualizations")` 透传；其它属性抛 `AttributeError`。

## 12.13 产物 schema（实跑 `results/batches/batch_20260909_full/summary/`）

### 目录
`tables/`、`summary/`、`figures/` + `analysis_plan.json`、`analysis_status.json`、`execution_log.json`（`PipelineArtifacts.create`, `pipeline.py:35-40`；GUI 运行还会额外生成 `analysis_run.json`/`analysis_run.log`，见 `app/backend/crispr_workspace/analysis.py:186-206`，非引擎产物）。

### summary/*.md（编号 = 分析阶段）
| 文件 | 生成函数 | 实测 |
|---|---|---|
| `00_overview.md` | `build_overview_md` | 1344 实验 / 1344 有效 / 7 模型 / 5 cell lines / 16 environments / splits all,mixed,single / 0 矛盾行 + 16 任务状态清单 |
| `01_data_quality.md` | `build_data_quality_md` | 5×16 覆盖矩阵（4 cell line 各 14，`none` 28）+ "无 metric inconsistency" |
| `02_prediction_generalization.md` | `build_prediction_md` | 21 行（7 模型 × 3 split）+ LOCO 28 行 |
| `03_environment_effects.md` | `build_environment_md` | 条件 ΔR² 2016 行 + 主效应 252 行的表 |
| `04_sequence_motifs.md` | `build_motif_summary_md` | 7 个 (model, method) 覆盖表 + 每方法 top-10 |
| `05_cellline_heterogeneity.md` | `build_cellline_md` | 标签分布 50/28/6 + 84 行 effect 表 |
| `06_evidence_integration.md` | `build_evidence_md` | 4 行环境证据矩阵，全 Inconclusive |
| `07_biological_hypotheses.md` | `build_hypotheses_md` | 仅一句"No Tier1-3 → 不生成候选假设" |
| `08_anomaly_report.md` | `build_anomaly_md` | `numerical_instability_excluded_from_evidence: 28`；明细"无 metric inconsistency" |

### tables/*.csv（列名 = 实测首行）
| 文件 | 行数 | 关键列 |
|---|---|---|
| `experiment_table.csv` | 1344 | `model,split_type,cell_line,environment,random_seed,n_train,n_valid,n_test,R2,MAE,RMSE,Pearson,Spearman,MSE,source_table,run_name`（本批 `n_train/n_valid/n_test` 全为空 → 源表无这些列，`loaders.py:67-74` 填 `pd.NA`） |
| `metric_inconsistency.csv` | 0 | `row,experiment,flags,delta_r2,delta_rmse`（空表仅表头） |
| `anomaly_report.csv` | 0 | `anomaly_type,row,experiment,flags,delta_r2,delta_rmse`；非空时 `anomaly_type` 由 `flags` 首段 `rsplit("_",1)[0]` 推出（`pipeline.py:270-272`） |
| `prediction_summary.csv` | 21 | `model,split_type,R2_mean,R2_std,MAE_mean,MAE_std,RMSE_mean,RMSE_std,Pearson_mean,Pearson_std,Spearman_mean,Spearman_std,n_experiments` |
| `loco_performance.csv` | 28 | `model,cell_line,R2,MAE,RMSE,Pearson,Spearman,n_experiments`（`split_type=='all'` 子集） |
| `environment_conditional_delta_r2.csv` | 2016 | `split_type,cell_line,model,environment_added,background,background_set,delta_r2_mean,delta_mae_mean,delta_rmse_mean,n_paired` |
| `environment_main_effects.csv` | 252 | `split_type,cell_line,model,environment,main_r2_delta,main_mae_delta,main_rmse_delta,n_seeds,n_backgrounds_avg` |
| `attribution_summary.csv` | 331200 | `feature,channel,position,model,architecture,split_type,cell_line,environment,method,importance,snr,effect,attention_entropy,source_file` |
| `cellline_effects.csv` | 84 | `split_type,model,factor,factor_type,n_cell_lines,consensus_direction,context_label,effect_hct116,effect_hek293t,effect_hela,effect_hl60,effect_none` |
| `evidence_matrix.csv` | 4 | `feature,feature_type,applicable_models,coverage,direction_concordance,cell_line_consistency,overall_effect,model_effects,unstable_rows_excluded,evidence_tier` |

### figures/*.png（实跑 15 张，`execution_log.figures` 全量列出）
`02_prediction/{model_performance,loco_performance}.png`；`03_environment/{conditional_delta_r2_heatmap,environment_main_effects}.png`；`04_sequence/position_attribution_{linear_coefficient,xgboost_treeshap,xgboost_gain,mlp_ig,cnn_ism,cnn_ig,transformer_attention}.png`（7 张）；`05_cellline/{context_consistency,feature_cellline_effect}.png`；`06_evidence/{evidence_tier_summary,evidence_matrix_heatmap}.png`。

### JSON 元数据
- `analysis_plan.json` = `AnalysisPlan.to_json_dict()` (`pipeline.py:260`)：`plan_version` + `run_qc` + `run_prediction_analysis` + 5 个子计划（与 §12.4 默认值一致；实测与 `default_plan()` 相同）。
- `analysis_status.json` = `ExecutionPlan.to_status_dict()` (`plans.py:220-235`；`pipeline.py:261`)，字段仅 `plan_version / started_at / completed_at / tasks[{task_id,selected,available,status,reason}]`。
- `execution_log.json` (`pipeline.py:290-298` + `:311-323`)：`{"executed": {task_id|"visualization": status}, "completed_at", "status_counts": {status: n}, "figures": [相对 figures/ 的路径…]}`。实测 `executed` 含 14 项（13 任务 + visualization），`status_counts = {completed:9, unavailable:4, skipped:3}`。

### 只读核验命令（本文档所用，均不写仓库）
```bash
## 产物清单与规模
find results/batches/batch_20260909_full/summary -type f | sort
wc -l results/batches/batch_20260909_full/summary/tables/*.csv
awk 'END{print NR-1}' results/batches/batch_20260909_full/summary/tables/attribution_summary.csv   # 331200
ls results/batches/batch_20260909_full/summary/figures/*/*.png | wc -l                            # 15
## 不稳定隔离与字段语义
python3 - <<'EOF'
import csv,collections
rows=list(csv.DictReader(open('results/batches/batch_20260909_full/summary/tables/environment_main_effects.csv')))
print(collections.Counter(r['environment'] for r in rows))                      # 每因子 63 行
print(sum(1 for r in rows if abs(float(r['main_r2_delta']))>=10.0))             # 28（真实不稳定行）
EOF
## 测试规模与死码审计
grep -c 'def test_' analysis/tests/test_*.py
grep -rn "<symbol>" --include="*.py" analysis/ app/backend/          # 逐个未使用符号核验
```

---

# 13. 测试体系（`analysis/tests/`，unittest，无 pytest 依赖）

- 运行方式（`analysis/README.md:55`）：`python -m unittest discover -s analysis/tests`（或单文件 `python analysis/tests/test_core.py`，文件末尾自带 `unittest.main(verbosity=2)`）。共 **31 个 test 方法**：test_core 20 / test_environment 4 / test_attribution 3 / test_phase5 3 / test_phase6 1（`grep -c "def test_"` 实测）。
- `test_core.py`（`analysis/tests/test_core.py`）：
  - `TestEffectSize` (`:28-37`)：同 cohort（n 相等）增量 = 0.05 且 paired_ok；n 100 vs 90 → 增量 NaN 且 paired_ok=False。
  - `TestMetricConsistency` (`:40-50`)：`(0.03,0.02)`→same_increase；`(-0.03,-0.02)`→same_decrease；反向 → 空。
  - `TestFDR` (`:53-64`)：`p=[0.001,0.004,0.02,0.1]` 的 q 单调非降且 `q[0]=0.004`；`None` 位保持 NaN 且末尾 q ≤ 1。
  - `TestBootstrap` (`:67-80`)：同 seed 两次 CI 完全一致、CI 覆盖估计值；**非配对（3 vs 2）→ `available=False`（不是 0）**。
  - `TestEvidenceRules` (`:83-102`)：FDR 0.0005/0.005/0.03 → Strong/Moderate/Weak，0.2 → None；`classify_attribution(9.0, 0.05)` 必须是 `Strong attribution`（断言标签值不含 statistical 语义）；`effect=1e-6` 时高 SNR 也不得给标签（min_effect_size 门禁）。
  - `TestIntegration` (`:105-130`)：`direction_concordance([0.1,0.2,-0.3]) = 2/3`，全 None → None；3 个同向 cell line → `Context-consistent` + 方向 `+`；Tier1 需 supporting≥2 且 strong 且 concordance=1.0（`ci_crosses_zero=False`）；`conflicting_direction=True` → Inconsistent→`INCONCLUSIVE`。
  - `TestLoaderAndValidation` (`:133-165`)：在临时目录造 4 行 `all_experiments.csv`，验证 loader 读 4 行且 R² 全有效，且**只有同 seed 的 (R²↑, RMSE↑) 行被标记**（另一 seed 的 (↑,↓) 不误伤）→ 直接锚定"同 seed 配对"契约。
  - `TestAnalysisPlanValidator` (`:168-197`)：`motif_enrichment=True` 而 `motif_discovery=False` → available False 且 status `skipped`；`environment_anova=True` 但 factorial observations=0 → selected True / available False / skipped；`n_cell_lines=1` → `cellline_heterogeneity` available False。
- `test_environment.py`：`parse_environment_set` 三种输入 (`:26-31`)；条件增量 4 条配对的精确数值与"每 (add, background) 跨 seed 恰好 2 条" (`:34-55`)；主效应 ctcf=0.065 / dnase=−0.015 (`:58-66`)。
- `test_attribution.py`：临时批次含线性新白名单 CSV 与 xgboost 旧列（含 `Permutation_p_val`）；断言总行数 1+4（linear 1 行剔除 Bias；xgboost 2 特征 × 2 方法）、methods 含 `linear_coefficient/xgboost_treeshap/xgboost_gain`、无 `Bias` 行、**统一表不含 `p_value/fdr/permutation` 列** (`:48-59`)；位置解析 `pos20_G→20`、`pos18_C→'C'` (`:61-67`)；`top_attribution_features(top_n=2)` 非空且 ≤ 2×(model,method) 组数 (`:69-74`)。
- `test_phase5.py`：构造含 2 个 ±1e13 发散行的主效应表 → 矩阵 `unstable_rows_excluded >= 2` 且 `|overall_effect| < 1.0`（不稳定值不进均值）(`:34-40`)；`cellline_summary` 全 `Context-conflicting` → 该 factor tier = `Inconclusive` (`:42-53`)；`summarize_environment_by_cellline` 中 m1/ctcf = `Context-consistent` 且总行数 4（2 模型 × 2 环境）(`:55-59`)。
- `test_phase6.py`：合成 2 模型 × 2 cell line × 4 环境的批次，`plan.sequence.enabled=False`、bootstrap/hypothesis/fdr=False，跑 `run_analysis` 端到端；断言 7 个任务 completed、`sequence_attribution != failed`；`summary/` 下 00/01/02/03/05/06/07/08 md 均存在且长度 >50，01 含 "cell-line × environment 覆盖"、08 含 "明细"；`tables/anomaly_report.csv` 必含 `anomaly_type` 列（空态也有表头）；`figures/*/*.png` ≥ 3；`execution_log.json` 中 `executed.visualization == "completed"` 且 `figures` ≥ 3 且均为 png (`:59-106`)。**该测试同时是"未实现任务不得伪造成 completed"的回归保障。**
- 未覆盖项（grep 实证）：`stats/hypothesis_tests.py`（permutation / ANOVA 占位）、`environment.compute_pair_interactions`、（2026-09-13 删除的 `evidence/rules.py` 中 `classify_mutation_effect` 曾属未覆盖项）、`data.loaders.iter_experiment_records`、`attribution.columns.pick_column` 均无单测（**与 `analysis/docs/code_cleanup_report.md:22,25` 声称"函数有独立单元测试/模块有单测"不符**）。

---

# 14. 与文档/注释不一致或未实现项

| # | 类型 | 事实（代码/产物） | 文档或注释的说法 | 证据 |
|---|---|---|---|---|
| 1 | 未实现 | `motif_discovery` 无 runner，选中后状态 `unavailable`（reason: analysis module not yet implemented in this build (phase roadmap)） | `analysis/README.md:73` 把 "Phase 4 attribution 统一抽取 + motif" 标为 ✅，而 `:74` "待续" 才列出 motif discovery runner；`SequencePlan.motif_discovery` 默认 True（`:42`） | `analysis/pipeline.py:241-247`；`results/.../analysis_status.json`；`analysis/docs/workflow_architecture.md:61` 亦承认其 unavailable |
| 2 | 未实现（占位） | `anova_interface()` 恒返回 `available=False` | interface_contract §7 "ANOVA/Shapley runner 就绪前状态 unavailable"（一致），但 registry 注释称"需要足够 factorial observations"暗示可运行 | `analysis/stats/hypothesis_tests.py:56-73`; `analysis/registry.py:60-63` |
| 3 | 未实现 | `bootstrap`/`hypothesis_testing`/`fdr_correction` 三个统计任务恒 `unavailable`（无 runner 挂载），尽管 `stats/` 四个模块已实现且有部分单测 | `docs/workflow_architecture.md:2 表格` 把 stats 层描述为已实现能力；`analysis/README.md:36-37` 标注为 roadmap（一致） | `analysis/registry.py:70-71`（runner=None）；`analysis/pipeline.py:241-247` |
| 4 | 死规则 | `classify_cellline_consistency` 的 `"Context-dependent"` 分支不可达（方向全同→consistent，方向不全同→conflicting） | docstring 与 interface_contract §6 均把 Context-dependent 列为正常标签；`CellLineEffect.context_label` 注释同样列出 | `analysis/evidence/integration.py:52-62`；实测 05 md 标签仅 conflicting/uncertain/consistent（`results/.../summary/05_cellline_heterogeneity.md`） |
| 5 | 字段语义错 | `evidence_matrix.unstable_rows_excluded` 实为"该 factor 被 groupby 折叠掉的行数"（63 行 → 7 模型行 ⇒ 56），真实不稳定行每因子仅 7 行 | `docs/workflow_architecture.md:5` 与 08 md 把它当"被隔离的发散上下文数（28）" | `analysis/evidence/integration.py:140-141`；实测 `unstable_rows_excluded=56`/因子，而 pipeline 独立统计的 `matrix_excluded=28`（`pipeline.py:218-221`） |
| 6 | 配置未接线 | `cellline_consistent_ratio=0.75`、`QCConfig.*`、`fdr_nominal`、`bootstrap_iterations`、`permutation_iterations`、`bootstrap_ci_exclude_zero_alpha` 无消费点；`summarize_environment_by_cellline` 用函数默认值 0.75 而非 config | docs 称"阈值一律来自 config，不散落" | `analysis/evidence/rules.py:1`；`analysis/pipeline.py:195`；`grep` 0 命中 |
| 7 | 状态/reason 错配 | completed 任务的 `reason` 会保留 validator 旧文案（如 `"environment features unavailable"`、`"need >=2 cell lines"`） | 约定 "unavailable=选中但缺能力 (reason 必填)"，未定义 completed 携带 reason | `analysis/pipeline.py:109-116`；实测 `analysis_status.json` |
| 8 | 文档 schema 与产物不符 | 实际 `analysis_status.json` 无 `engine_version/batch/config`，task 内无 `completed_at`；这些字段只存在于**返回值** `status_dict`（供 00 md 使用） | `analysis/docs/interface_contract.md:41-53` 把这些字段写进输出 schema（`:45` engine_version、`:49` `bootstrap_n/permutation_n/permutation_seed`、`:53` task.completed_at） | `analysis/pipeline.py:254-261`; `analysis/plans.py:220-235`; 实测 JSON |
| 9 | 行数/规模数字 | `attribution_summary.csv` 实测 **331 200** 行；`figures/` 实测 15 张 PNG；单测 31 项 | `analysis/README.md:44`、`analysis/docs/workflow_architecture.md:71` 写 "287k 行" | `awk 'END{print NR-1}'`；`ls figures/*/*.png | wc -l` |
| 10 | 图形规格 | `save_figure(dpi=150)`、`plt.subplots(dpi=150)` | `analysis/README.md:36`、`analysis/docs/workflow_architecture.md:20`、`visualization/__init__.py:1` 声称 "300dpi" | `analysis/visualization/core.py:16-21`；`environment_plots.py:25` |
| 11 | 版本串 | 同文件头 "V6" 与运行打印 "启动全景生信绘图引擎 (V4)" | 二者互斥 | `analysis/visualization.py:3` vs `:916` |
| 12 | 死代码 | 多处枚举/dataclass/函数无生产调用：`TaskStatus`、`MotifRecord`、`CellLineEffect`、`StatisticalEvidence`（仅作字段）、`EvidenceClass`、`evidence_record_row`、`classify_mutation_effect`、`compute_pair_interactions`、`compute_paired_increment`（仅测试）、`_MODEL_TOKEN`、`attribution/summary.py:35-36` 的 `coverage`、`rules.py` 的两个 classify 函数（仅测试） | `code_cleanup_report.md:27-29` 只承认其中 3 类为 roadmap，未列全 | 逐符号 grep（详见各小节） |
| 13 | 注释声称的单测 | `code_cleanup_report.md:28` 称 `compute_pair_interactions` "有独立单元测试"、`:29` 称 `stats/{bootstrap,hypothesis_tests,…}` "模块有单测" | `test_environment.py` 无该函数引用；`hypothesis_tests` 无任何测试引用 | `grep -rn compute_pair_interactions analysis/tests` 0 命中 |
| 14 | legacy 参数未生效 | `collect_results.py --latest`、`importance_extraction.py --latest/--all_batches`、`anomaly_treatment.py --latest` 声明后未使用（批次选择改由 mtime 自动判定） | `--help` 文案暗示可用 | `collect_results.py:405,411-422`；`importance_extraction.py:882-883,886-897`；`anomaly_treatment.py:456,464-474` |
| 15 | legacy 解析不一致 | `collect_results` 的门槛 glob `*info*.txt` 与真正的 `"_info.txt"` 关键字不一致；`parse_info_txt` 做类型推断而 `importance_extraction/anomaly_treatment/visualization` 的 `parse_info_file` 只保留小写字符串 | 各处注释均称"解析 info" | 对比 `collect_results.py:105-114,38-71` 与 `importance_extraction.py:33-42` |
| 16 | 7/8 通道瑕疵 | `SCHEMA_CHANNELS` 长 8，但 `identify_feature_channel` 与 `extract_feature_position` 用 `% 7` / `// 7` → `rrbs`(idx 7) 永不被推断，位点也会错位 | 注释称覆盖 8 通道 schema | `importance_extraction.py:23,71-79,83-94` |
| 17 | 新引擎无发散过滤 | `prediction_summary.csv` 中 linear 的 `R2_mean ≈ -1.87e16`（含发散实验）；引擎只做"隔离不删除"（且隔离仅作用于证据矩阵），预测/归因表不过滤 | 文档强调数值稳定性护栏 | `analysis/data/loaders.py`（无 filter）；实测 `02_prediction_generalization.md` linear 行 |
| 18 | Capabilities 非数据推导 | `n_environment_factors=4`、`environment_factorial_observations=16`、`replication_per_cellline=4` 硬编码，即使表无环境特征且 `has_environment_cols=True` 默认 | `plans.py:117` "由实际数据推导的可用性" | `analysis/pipeline.py:43-61,88` |
| 19 | 已删除的 legacy 文件 | `analysis/visualize_results.py` 在 git 索引中、工作区不存在，且无任何引用 | 无文档提及 | `git ls-files Submit/analyse`；`ls` 缺失 |
| 20 | 队列内重复实现 | `anomaly_treatment`（实验级同向矛盾）与 `data/validation`（同 seed 配对同向矛盾）语义重叠但键不同（前者键无 seed） | `code_cleanup_report.md:3 表格` 已说明"有意并行" | `anomaly_treatment.py:160-163` vs `validation.py:37-40` |

---

## 本节自检

- **summary 00–08 md 全覆盖**：§12.12 给出 9 个 md 的 builder 函数与行号（`00_overview` `01_data_quality` `02_prediction_generalization` `03_environment_effects` `04_sequence_motifs` `05_cellline_heterogeneity` `06_evidence_integration` `07_biological_hypotheses` `08_anomaly_report`）；§12.13 逐文件核对实跑产物均存在（04 只在 `sequence_attribution` 成功时生成）。
- **tables 清单完整**：§12.13 列出 10 个 CSV 的行数 + 实测列名（experiment_table / metric_inconsistency / anomaly_report / prediction_summary / loco_performance / environment_conditional_delta_r2 / environment_main_effects / attribution_summary / cellline_effects / evidence_matrix），并注明空表也写表头。
- **阈值表**：§12.2 完整列出 4 个 dataclass + `AnalysisConfig` 的全部默认值（SNR 2.5/1.8/1.2、min_effect_size 0.005、FDR 0.001/0.01/0.05/0.10、min_coverage 2、concordance 0.80、cellline_ratio 0.75、env_strong 0.01、unstable 10.0、QC 0.30/70.0、bootstrap 2000/seed 2024、permutation 1000/seed 42），并标注哪些未被消费；§11 另列 legacy 阈值（|R2|/MAE/RMSE>10、SNR 2.5/1.8/1.2/0.8、|Weight|>10、sign_tol 1e-6、p98/±1.0/[0.01,10]/[0.01,15] clip、200 条明细上限）。
- **Tier 规则**：§12.11 逐条给出 `classify_evidence_tier` 的 5 个分支（conflicting/CI 跨 0 → Inconclusive；supporting≥2 且 strong 且 concordance≥0.80 → Tier1；supporting≥2 → Tier2；supporting==1 且 strong → Tier3；applicable==0 → No current evidence），并给出 Context-conflicting 直接降级 Inconclusive 的旁路（`integration.py:152-159`，实测 4 行全 Inconclusive）。
- **配对基线**：§12.6/§12.8/§12.11 三处引用同一契约 —— `(split_type, cell_line, model, random_seed)` 才可相减（`validation.py:37-40`、`incremental_effect.py:17,61,116`），跨 seed 永不相减，单测 `test_environment.py:46-55`、`test_core.py:133-165` 双向锚定；并指出 legacy `collect_results.calculate_delta_R2` 的键不含 seed（§11.1）。
- **unavailable 语义**：§12.1/§12.5/§12.7 说明"未实现/缺能力 → `unavailable` + reason，绝不伪造；`skipped` 仅表示未选中或依赖不满足"，实测 4 个任务 `unavailable`、3 个 `skipped`、9 个 `completed`；`test_phase6.py` 断言不得把未实现任务写成 failed/completed。
- **registry task ids**：§12.4 列出 16 个 id 全集并注明 registry 实际注册 15 条（缺 `fdr_correction`）、全部 `runner=None`、pipeline 不读 registry、GUI 从 registry 渲染任务目录。
- **tests**：§13 覆盖 5 个测试文件 31 个用例的断言要点、运行命令（`python -m unittest discover -s analysis/tests`）与未覆盖清单（hypothesis_tests / compute_pair_interactions / classify_mutation_effect / iter_experiment_records）。
- **图/表/JSON 与函数映射**：§12.12 给出 `render_all` 的 5 个主题目录、15 张 PNG 的文件名与触发列条件；§12.13 给出 3 个 JSON 的字段级 schema 与实测内容。
- **不一致项**：§14 汇总 20 条（含 motif/ANOVA/统计 runner 未实现、Context-dependent 不可达、`unstable_rows_excluded` 语义错、status schema 与 interface_contract 不符、287k vs 331 200 行、dpi 150 vs 300dpi、V4/V6 版本串、legacy `--latest` 未使用、7/8 通道瑕疵等），每条附 `path:line` 或实测命令依据。
- **未使用/不确定标注**：Active/Legacy/Unused/Uncertain 均在 §11 各表与 §12 各节显式给出（如 `visualization.py` 为 Legacy-but-active-by-bridge；`summary/plots/` 本批缺失 → Uncertain；`analysis/visualize_results.py` 已删除）。


---

# 15. 实验运行器 (workflows/prediction/predict.py / workflows/training/data_digging.py: 职责边界, CLI 参数表, 调用链)

## 15.1 职责边界 (由代码 docstring 与 main() 实证)

| 文件 | 唯一职责 | 证据 |
|---|---|---|
| `workflows/prediction/predict.py` | mixed 已测池 10 折 CV 选超参 → 全量重训 Ultimate 模型 → 对【目标待测数据集】真实预测 → 写 `赛道二_results.csv` | `workflows/prediction/predict.py:1-24` (docstring), `workflows/prediction/predict.py:757-840` (`main`) |
| `workflows/training/data_digging.py` | 已测数据 Training Scope 网格实验 (逐实验 subprocess 调 `workflows/training/train.py`) | `workflows/training/data_digging.py:1-17`, `workflows/training/data_digging.py:436-514` |

两者都不再做对方的旧职责 (拆分注释: `workflows/prediction/predict.py:5-9`, `workflows/training/data_digging.py:5-10`)。`workflows/prediction/predict.py` 中仍残留旧职责的两个函数 `train_ultimate_models` (`workflows/prediction/predict.py:476-559`) 与 `generate_track2_results_ultimate` (`workflows/prediction/predict.py:651-716`),**在仓库内无任何调用点**(`grep -rn` 全仓库仅命中定义行) → 标记 **Legacy / Unused**;`main()` 走的是 `run_ultimate_with_resume` (`workflows/prediction/predict.py:931-1003`) + `_write_track2_from_preds` (`workflows/prediction/predict.py:892-928`)。

## 15.2 workflows/prediction/predict.py CLI 参数表 (`parse_args`, workflows/prediction/predict.py:723-754)

| 参数 | 类型/取值 | 默认 | 作用 |
|---|---|---|---|
| `--data-dir` | str | `data/processed` | 已测数据 + `feature_schema.json` 根 |
| `--results-dir` | str | `results` | 结果根 |
| `--batch-name` | str | `""` | 空 → 直接 `results/summary/`; 非空 → `results/[batch]/summary/` (`workflows/prediction/predict.py:793-796`) |
| `--models` | nargs+, choices `linear xgboost mlp transformer cnn` | `None`(全部) | 终极模型; `cnn` 展开为 cnn33/53/73 (`workflows/prediction/predict.py:268-285`) |
| `--cell-lines` | nargs+, choices `hct116 hek293t hela hl60` | `None`(目录内全部) | 参与 mixed 10 折的细胞系 |
| `--target-input` | str | `""` | 目标待测 CSV 文件或目录; 空 = pooled 旧行为 |
| `--target-epigenetics` | nargs+ | `None` | 目标实际具备的表观通道; 缺省从目标文件列自动识别 (`workflows/prediction/predict.py:766-770`) |
| `--candidate-top-k` | int | `20` | 共识排序取 Top-K |
| `--ultimate-dir` | str | `None` | 缺省 `results/[batch]/summary/ultimate` (`workflows/prediction/predict.py:796`) |
| `--ultimate-cv-folds` | int | `10` | CV 折数 |
| `--ultimate-epochs` | int | `15` | torch 模型每折 epochs |
| `--ultimate-seed` | int | `42` | KFold/训练 seed |
| `--device` | str | `None` | 空则 torch.cuda 探测 (`workflows/prediction/predict.py:939-944`) |
| `--dry-run` | flag | False | 只打印模式/通道规划/数据量/模型计划, 不建目录不写文件 (`workflows/prediction/predict.py:798-815`) |
| `--generate-candidates` | flag | False | **已废弃无意义**, 代码中除 `add_argument` 外无任何引用 (`workflows/prediction/predict.py:752-753`) |

## 15.3 通道规划与目标特征 (Target Epigenetics)

| 函数 | 行 | 行为 |
|---|---|---|
| `build_channel_plan(schema, target_epis)` | 101-136 | 从 `schema["channel_names"]` 取序列通道 (名字 ∈ `{A,C,G,T}`, `SEQ_LETTERS` 46) 恒选; 表观通道 = `target_epis` 中存在的 (忽略大小写); 缺 `channel_names` → `ValueError`; 无碱基通道 → `ValueError`; 不在 schema 的请求通道打印 `[WARN]` 并忽略。返回 `{keep, channels, seq_letters, epi, n_seq, n_channels, seq_len, feature_names}`; `feature_names = [f"pos{p}_{ch}" for p in 1..seq_len for ch in kept]` |
| `subset_arrays_3d(X3, plan)` | 139-142 | `(N,23,C) → (N,23,K)` + 展平 `(N,23K)` |
| `detect_sequence_column(df)` | 145-152 | 先按 `SEQ_COL_CANDIDATES` (`sgRNA/sequence/Sequence/23nt/protospacer`, 47), 再模糊匹配含 `sgrna`/`seq` |
| `load_target_dataframe(path)` | 155-174 | 目录 → 取第一个能解析出序列列的 `*.csv`/`*.CSV`; 文件 → 直接读; 找不到 → `FileNotFoundError` |
| `build_target_features(df, schema, plan)` | 177-221 | 序列 4 碱基 One-Hot (仅 plan 内碱基); 表观列按列名小写包含匹配, 长度 23 字符串 (`1/A/Y/T`→1) 或数值标量整行填充; 缺列 → 该通道全 0 并 `[WARN]` |
| `resolve_target_epis_from_file(df, schema)` | 224-233 | 目标列名 (小写) 精确或子串命中 schema 表观通道名 → 返回通道列表 |
| `_load_mixed_subset(data_dir, schema, plan, cell_lines)` | 240-261 | 走 `src.input_control.cell_line_division.discover_available_cell_lines/load_cell_line`, 拼接多细胞系后按 plan 裁剪; 无可用细胞系 → `FileNotFoundError` |

`main()` 断言 `X2.shape[1] == len(feature_names) == 23 * n_channels` (`workflows/prediction/predict.py:789-790`)。
**严格子集对齐**: 训练输入 (mixed) 与预测输入 (target) 用同一 `plan` 裁剪 —— pooled 模式用 schema 全通道 (`workflows/prediction/predict.py:779-782`), target 模式用目标实际通道。

## 15.4 Ultimate 模型与网格

| 项 | 内容 (行) |
|---|---|
| `ULTIMATE_MODEL_ORDER` | `lr, xgboost, mlp, cnn33, cnn53, cnn73, transformer` (49) |
| `ULTIMATE_GRIDS` | lr: `[{use_scaler:False}]`; xgboost: `{n_estimators:100,max_depth:3}` / `{200,4}`; mlp: `{hidden_dim1:128,dropout:0.2}` / `{256,0.3}`; cnn33: `{conv_channels1:32,conv_channels2:64,dropout:0.2}` / `{48,96,0.3}`; cnn53/cnn73: 各 1 组 `{32,64,0.2}`; transformer: `{dropout:0.1}` / `{0.2}` (68-92) |
| `KIND_USES_2D` | `{lr, xgboost, mlp}` → 用展平 2D 输入 (93) |
| `TORCH_KINDS` | `{mlp, cnn33, cnn53, cnn73, transformer}` (94) |
| `_expand_ultimate_models` | `linear`→`lr`, 含 `xgb`→`xgboost`, `cnn`→三卷积核, 未知名忽略; 空则 `["lr"]` (268-285) |
| `_build_torch_model` | mlp→`MLPModel(input_dim, hidden_dim1, hidden_dim2=64, dropout)`; cnn→`CNNModel(sequence_channels=n_seq, environment_channels=总通道-seq, sequence_kernel=kind[3], environment_kernel=3)`; transformer→`TransformerModel(input_dim=通道数, d_model=64, nhead=4, num_layers=2)` (288-325) |
| `_fit_torch_model` | `torch.manual_seed(seed)`+`np.random.seed(seed)`; batch 256 shuffle; AdamW(lr=cfg.lr 默认 1e-3, weight_decay=0); MSELoss; epoch 循环无 early-stop (328-351) |
| `_fit_model` | lr→`LinearRegressionModel(use_scaler)`; xgboost→`XGBRegressor(n_estimators,max_depth,learning_rate=0.05,subsample=0.8,colsample_bytree=0.8,reg:squarederror,n_jobs=-1,random_state=seed)`; 其它→torch (365-392) |
| `_predict_model` | 非 torch 走 `model.predict`; torch 走 `torch.no_grad`, 分块 2048 (395-406) |
| `_run_ultimate_cv` | `KFold(n_splits, shuffle=True, random_state=seed)`, 每折独立 `_fit_model`, 预测 `clip(0,1)`, 返回 `(mean_r2, mean_rmse, std_r2)` (409-423) |

**LR `_T` 参照列对齐 (parity)**: `_drop_lr_reference_columns` (`workflows/prediction/predict.py:354-362`) 调 `src.linear_regression.linear_regression.select_non_t_reference_features` (`core/models/linear/linear_regression.py:468-488`), 剔除所有以 `_T` 结尾的特征列 (T 为基准, 184→161)。训练端 (`workflows/prediction/predict.py:511-512`)、预测端 (`workflows/prediction/predict.py:669`, `884`)、汇总端 (`workflows/prediction/predict.py:900-902` 复用 progress 中保存的 `lr_names`) 三处一致。若无 `_T` 列 (7 通道旧数据) 原样返回。

`_save_ultimate_model` (`workflows/prediction/predict.py:434-473`): lr → `ultimate_lr_model.json` (含 `weights/std_errors/t_stats/use_scaler/feature_names`); xgboost → `ultimate_xgboost_model.pkl` + `_config.json`; torch → `ultimate_<kind>_model.pt` (`{state_dict, config}`) + `_config.json`; 全部经 `_atomic_bytes` (`workflows/prediction/predict.py:426-431`, 同目录 `.tmp` + `os.replace`)。

## 15.5 RESUME 机制 (workflows/prediction/predict.py)

| 函数/常量 | 行 | 事实 |
|---|---|---|
| `PROGRESS_FILE = "progress.json"` | 850 | 完成标记文件, 位于 `ultimate_dir` |
| `_load_progress` | 857-865 | 读 `{"models":[...]}`; 文件缺失/解析异常 → `[]` |
| `_save_progress` | 868-870 | 原子写整个 models 列表 |
| `_kind_done(rows, kind)` | 873-877 | 完成判据 = progress 中有该 `model` **且** `preds_file` 路径 `os.path.exists` |
| `run_ultimate_with_resume` | 931-1003 | 逐 kind: 已完成 → `np.load(row["preds_file"])` 复用并打印 `[Resume]`; 未完成 → CV 选参 + 全量重训 + `_save_ultimate_model` + `_preds_on_target` → `np.save` 到 `preds_<kind>.npy` (原子写, `workflows/prediction/predict.py:977-980`) → 追加/替换同 model 的 row (`workflows/prediction/predict.py:988-991`) |
| 结束 | 996-1003 | 写 `ultimate_summary.json` (models 直接取 progress rows); `preds` 为空 → `RuntimeError`; 否则 `_write_track2_from_preds` |

**明确事实 (代码注释 `workflows/prediction/predict.py:819-820, 845-849`)**: 完成判据是本 run 的 `ultimate/progress.json` 条目 + 原子落盘的 `preds_<kind>.npy`;**绝不扫描 `results/` 或 batch 目录** —— 未跑完的实验目录一律忽略, 中断后重跑同一命令只补"没有完成标记"的模型。断点续跑版汇总不再需要模型对象 (`_write_track2_from_preds`, `workflows/prediction/predict.py:892-928`)。

## 15.6 输出 `赛道二_results.csv`

写入者 `_write_track2_from_preds` (`workflows/prediction/predict.py:892-928`), 输出路径 `results/[batch]/summary/赛道二_results.csv` (`workflows/prediction/predict.py:821`), `utf-8-sig`。

- 共识: `usable = [cv_r2 > 0 的模型] or 全部` (`:895`), `consensus = mean(preds[usable])` (`:897`), `argsort` 降序取 Top-K (`:898`)。
- 列 (7 列, 与仓库实测文件一致): `训练方式_细胞系`(恒 `mixed_all`)、`候选编号`(`CAND_sgRNA_%03d`)、`位点`(`extract_locus_from_row`, `workflows/prediction/predict.py:566-605`, `chr(start~end)` 或从 gene 名正则抽取, 兜底 `chrUnknown(...)`)、`候选序列(23nt)`、`预测编辑效率`(`%.4f [Linear:0.36|XGBoost:0.42|...]` 逐模型分解)、`最显著正向促进特征 (Top Positive Drivers)`(`match_ultimate_drivers`, `workflows/prediction/predict.py:608-648`: 仅前 20nt、仅 LR 权重 > 0 的 `pos{p}_{base}`, 相对最大权重 0.8/0.5/0.2 → `***`/`**`/`*`/`.`)、`对应模型`(`Ultimate_Consensus (Linear+...)`)。
- `match_ultimate_drivers` 在权重长度 ≠ `len(feature_names)+1` 或权重非有限值时返回 `"N/A"`。

## 15.7 workflows/training/data_digging.py CLI 参数表 (`parse_args`, workflows/training/data_digging.py:384-433)

| 参数 | 默认 | 说明 |
|---|---|---|
| `--batch-name` | `""` | 经 `sanitize_batch_name` 小写化并替换空格/斜杠 (`:121-122`, `:449`) |
| `--data-dir` / `--model-dir` / `--results-dir` / `--logs-dir` | `data/processed` / `models` / `results` / `logs` | 透传 `workflows/training/train.py` |
| `--training-scope-epis` | `None` | 向导第 4 步选项 2: 勾选表观 → `build_training_scope_combinations` 展开 |
| `--environments` | `None` | 显式环境组合 (与上者二选一) |
| `--models` | `None`(全部, 含 cnn) | choices `linear xgboost mlp transformer cnn` |
| `--cell-lines` | `None`(全 4 系) | choices `hct116 hek293t hela hl60` |
| `--split-types` | `["single","all","mixed"]` | choices 同 |
| `--mixed-seeds` | `[42,43,44,45]` | **解析后从未使用** (见 §23) |
| `--cnn-kernels` | `[3,5,7]` | **解析后从未使用** (见 §23) |
| `--train-ratio/--valid-ratio/--test-ratio` | 0.70/0.15/0.15 | |
| `--epochs/--batch-size/--learning-rate/--dropout/--weight-decay/--patience/--min-delta` | 100/64/1e-3/0.2/0.0/20/1e-6 | |
| `--hidden-dim1/--hidden-dim2/--conv-channels1/--conv-channels2` | 128/64/32/64 | |
| `--device` | `None` | |
| `--use-scaler` | flag | |
| `--workers` | `1` | 实验级并发; 1 = 串行子进程 |
| `--in-process` | flag | 复用解释器顺序执行 (与 workers>1 不同用) |
| `--threads-per-worker` | `0` | >0 才封顶 OMP/MKL/BLAS |
| `--dry-run` | flag | 只打印计划 |

## 15.8 网格实验引擎 (workflows/training/data_digging.py)

| 函数 | 行 | 事实 |
|---|---|---|
| `build_training_scope_combinations(active_epis)` | 37-52 | `["sequence"]` + 所有非空子集 (`sequence_` + 排序后 token 下划线连接) + 恰为四项全集时补 `"all"` |
| `_canonicalize_combinations(combos)` | 63-94 | **`all` 去重规则**: 若列表含 `all`, 则把 token 集合等于"全集"(所有组合中出现过的表观 token 并集) 的显式组合丢弃 (打印 `[Environments] 检测到 N 个与 all 等价的显式全特征组合, 已并入 all`); 不含 `all` 时原样返回。目的: 避免 `sequence_ctcf_dnase_h3k4me3_rrbs` 与 `all` 重复导致实验翻倍 (注释提到 1428 = 17×84) |
| `load_environment_combinations(data_dir)` | 97-115 | 无 `feature_schema.json` → 硬编码 16 组合 (含 `all`); 否则 `generate_combination_names(schema, include_all=True, include_sequence=True, sizes=[0,1,2,3])`; 异常 → `["sequence","all"]` |
| `Experiment` | 118 | `Tuple[model, environment, split_type, cell_line|None, seed|None, kernel|None]` |
| `generate_experiments` | 125-164 | 非 cnn 模型 × 环境 × split: `single` 逐细胞系 / `all` 逐留一细胞系 / `mixed` 逐 seed ∈ `MIXED_SEEDS=[42,43,44,45]`; cnn 再 × `CNN_KERNELS=[3,5,7]` (55-60, 146-162) |
| `build_run_name` | 167-180 | `single_{cl}_{model}_{env}` / `all_{model}_{env}_heldout_{cl}` / `mixed_{model}_{env}_seed_{seed}`; cnn 追加 `_kernel_{k}` |
| `parse_folder_info` | 183-194 | 读实验目录内第一个 `*info*.txt` (键小写化) 与判定 `*metrics*.json` 存在 |
| `build_completed_lookup` | 197-229 | **扫描 batch 目录**逐 run 目录: model 归一 (`linear/xgboost/mlp/cnn/transformer`), env ← `environment|combination`, split ← `split_type`, cell ← `cell_line|held_out_cell_line` (mixed 强制 None), seed ← `random_seed|seed` (默认 42), kernel ← `sequence_kernel|kernel` (默认 3); key = `(model, env, split, cell, seed if mixed else None, kernel if cnn else None)` |
| `classify_experiments` | 232-247 | 按同一 key 规则把 plan 分成 `completed` / `pending` (resume 依据) |
| `build_command` | 250-321 | 生成 `[sys.executable, <repo>/train.py, --model, --split-type, --environment, --batch-name, --run-name, --data-dir, --model-dir, --results-dir, --logs-dir, --train-ratio, --valid-ratio, --test-ratio, --seed, --epochs, --batch-size, --learning-rate, --dropout, --weight-decay, --patience, --min-delta, --hidden-dim1, --hidden-dim2, --conv-channels1, --conv-channels2]`; `cell_line != None` → `--cell-line`; cnn → `--sequence-kernel <k> --environment-kernel 3`; device → `--device`; use_scaler → `--use-scaler`。`random_seed = seed if mixed else 42` |
| `run_one_experiment` | 324-338 | `subprocess.run(cmd, check=False)`; 返回 `{model, run_name, return_code, status}` |
| `run_experiment_in_process` | 341-362 | 改写 `sys.argv = [workflows/training/train.py] + cmd[2:]` 后 `import train; train.main()`; **仅限顺序执行** (sys.argv 进程全局); 异常吞掉返回 failed |
| `build_worker_env` | 365-379 | 仅当 `workers>1 且 per_worker_threads>0` 才设置 `OMP/MKL/OPENBLAS/NUMEXPR/VECLIB_MAXIMUM_THREADS`, 否则返回 `None` (子进程环境与串行逐位一致) |
| `main` | 436-514 | 环境展开/解析 → canonicalize → 生成实验 → `classify_experiments` → dry-run 直接 return → 执行: `--in-process` 顺序 / `workers>1` 用 `ThreadPoolExecutor(max_workers)` 提交 `run_one_experiment` / 否则串行 |

`workflows/training/train.py` 侧产物命名 (resume 依赖): run 目录内 `<model>_info.txt` (含 `run_name/model/split_type/cell_line/environment/combination/random_seed/sequence_kernel/...`) 与 `<model>_metrics.json`; 实测目录 `results/batches/batch_20260909_full/all_cnn_all_heldout_hct116_kernel_3/{cnn_info.txt,cnn_metrics.json,cnn_validation_metrics.json,...}` 验证了该 glob 契约。`workflows/training/train.py` 打印 `[✓] Experiment <run_name> Finished Successfully.` (`workflows/training/train.py:724`)。

---

# 16. Wizard / Workflow (main_wizard 7 步 form_data 字段表; backend_runner 步骤 1–7 调用链; 条件分支; 自动 vs 用户决策)

## 16.1 Wizard 骨架

`CRISPRPlatformWizard(tk.Tk)` (`app/desktop/main_wizard.py:22`), 窗口 880x700, `total_steps = 7` (`:70`)。骨架: header (标题 + `ttk.Progressbar(maximum=7)`) / `container` / footer (`btn_prev`, `btn_next`) (`:80-103`)。`_show_step(step)` (`:109-427`) 每步重建 container 内容; `_clear_content` (`:105-107`) 销毁全部子控件。

## 16.2 7 步与 form_data 字段表

`form_data` 初始化于 `:29-67`。

| 步 | 标题 (`:1xx`) | 涉及 form_data 键 | 控件行为 |
|---|---|---|---|
| 1 | 平台核心宗旨与数据准备规范 (`:119`) | 无 (纯说明文本 `:122-143`) | — |
| 2 | 选择已测量数据与待预测基因组 (`:147`) | `measured_data_dir`(StringVar)、`enable_target_genome`(BooleanVar, 默认 True)、`target_genome_dir`(StringVar) | Folder A 文件/目录选择; Folder B 复选开关 → `_update_folder_b_state` 启停 `target_genome_widgets` (`:437-441`) |
| 3 | 设定特征维度与 CSV 列名映射 (`:189`) | `cell_lines_raw`(`hct116, hek293t, hela, hl60`)、`seq_len`(IntVar 23)、`seq_col`(`sgRNA`)、`target_col`(`Normalized efficacy`)、`epi_cols_raw`(`CTCF, Dnase, H3K4me3, RRBS`)、`chrom_col`(`Chromosome`)、`start_col`(`Start`)、`end_col`(`End`) | 坐标三控件在 Folder B 关时 `DISABLED` (`:231-233`) |
| 4 | 选择细胞系挖掘范围与待测表观环境完备度 (`:237`) | `selected_cell_lines`(dict[str,BooleanVar])、`selected_environments`(dict, Training Scope)、`target_available_environments`(dict, Target Epigenetics) | 由 `cell_lines_raw`/`epi_cols_raw` 重建并保留旧勾选 (`:243-259`); 训练表观勾选绑定 `_update_epigenetic_cascade_linkage` (`:275-278`) |
| 5 | 训练划分模式、预测模型与生信稳健性配置 (`:299`) | `split_vars`{single,all,mixed 默认 True}、`model_vars`{linear,xgboost,mlp,cnn,transformer 默认 True}、`xai_vars`{xgb_shap,mlp_sg,cnn_ism,trans_entropy 默认 True} | 模型勾选绑定 `_update_xai_linkage` (`:462-480`): 取消模型 → 其 XAI 变量置 False 且控件 DISABLED; 勾选 → 置 True |
| 6 | 核对与确认全流程配置信息 (`:356`) | 只读汇总 `:360-384` | 生成"配置核对单"文本 (输入路径/Folder B 状态/划分模式数/细胞系数/训练表观/待测表观/模型数), `state=DISABLED` |
| 7 | 确认总输出目录并启动全流程 (`:389`) | `root_output_dir`(默认 `<repo>/Project_Output`, `:66`) | 目录选择 + 归档结构说明文本 (`:405-427`); `btn_next` 文案变 "确认配置并启动流程" (`:115`) |

## 16.3 表观级联逻辑 (`_update_epigenetic_cascade_linkage`, `:443-460`)

规则 (docstring `:444-448`): 对每个待测表观项 —— 仅当 `enable_target_genome` 为真**且**训练集该项被勾选时, 待测控件 `NORMAL`; 否则强制 `target_available_environments[epi].set(False)` 并 `DISABLED`。
调用时机: Step 4 绘制完成时 (`:295`)、训练表观 checkbutton 的 `command` (`:277`)。

## 16.4 校验 (自动) vs 用户决策

| 类型 | 内容 | 位置 |
|---|---|---|
| 自动校验 | Step 4→5: 至少 1 个细胞系 | `:487-490` |
| 自动校验 | Step 5→6: 至少 1 种划分模式; 至少 1 个模型 | `:492-498` |
| 自动校验 | Step 7 启动: 输出目录非空 | `:506-509` |
| 用户决策 | Folder A/B 路径、列名映射、细胞系子集、训练表观集合、待测表观集合、划分模式、模型阵列、XAI 开关、总输出目录 | Step 2–5, 7 |
| 自动默认 | `measured_data_dir` 空 → backend_runner 回落 `data/processed` (`app/desktop/backend_runner.py:178-180`); 无细胞系→`hct116`, 无模型→`linear`, 无划分→`single` (`:167-169`) |

`_launch_pipeline` (`:505-516`) 禁用按钮并起 `threading.Thread(target=self._run_backend_task, args=(out_root,), daemon=True)`; `_run_backend_task` (`:518-531`) `from Input.backend_runner import execute_full_pipeline` → 完成/失败弹窗 → `finally: self.destroy()`。

## 16.5 backend_runner.execute_full_pipeline 步骤 1–7 (`app/desktop/backend_runner.py:144-306`)

前置: 建 `<root>/{models,results,logs,proceeded_data}` (`:148-156`); 读取勾选 `active_cls/active_epis/active_models/active_splits` (`:158-161`); `has_target = enable_target_genome and target_genome_dir 非空` (`:164`); `target_available_epis` 仅 has_target 时取 (`:165`); 环境组合 `build_active_environment_combinations(active_epis)` (`:171`, 定义 `:23-37`, 与 data_digging 同规则)。

| 步骤 | 打印 | 调用 | 细节 |
|---|---|---|---|
| 1/7 特征工程 | `:177` | `run_feature_engineering_step(form_data, raw_measured, proceeded_data_dir, active_cls)` (`:182`; 定义 `:94-141`) | raw 不存在 → 回落 `<repo>/data/processed`; 拷 benchmark 文件; 写 `feature_schema.json` (`channel_names=["A","C","G","T","CTCF","Dnase","H3K4me3","RRBS"]`, `:107-117`); 逐细胞系: 已有 `_features_23x8.npy` 跳过, 否则拷 benchmark → `convert_raw_csv_to_npy` |
| 2/7 网格挖掘 | `:187` | `subprocess.run([sys.executable, <repo>/data_digging.py, --batch-name "", --data-dir, --model-dir, --results-dir, --logs-dir, --models *active_models, --cell-lines *active_cls, --environments *active_environments, --split-types *active_splits])` (`:193-205`) | `batch_name = ""` (`:173`) → 结果落 `results/` 根; 返回码非 0 仅 `[Warning]` |
| 2b/7 候选预测 (条件) | `:210` | `workflows/prediction/predict.py` (`:223-233`): `--batch-name ""`, `--data-dir`, `--results-dir`, `--models`, `--cell-lines`, `--target-input`, `--ultimate-dir <root>/ultimate`, 条件追加 `--target-epigenetics *target_available_epis` (`:235-236`) | 仅 `has_target`; `target_genome_dir` 为文件直接用, 为目录取第一个 `*.csv`/`*.CSV`, 无效则打印警告并跳过 (`:212-221`) |
| 3/7 指标收集 | `:244` | `analysis/collect_results.py --batch-dir <results> --split-types *active_splits` (`:246-252`) | 脚本不存在则跳过 |
| 4/7 异常检测 | `:255` | `analysis/anomaly_treatment.py --batch-dir <results>` (`:256-261`) | 生成 `summary/anomaly_report.md` |
| 5/7 重要性提取 | `:264` | `analysis/importance_extraction.py --batch_dir <results>` (`:265-270`) | **注意下划线参数名** (`:269`) |
| 6/7 可视化 | `:273` | 进程内 `from analyse.visualization import generate_all_visualizations` → `generate_all_visualizations(batch_dir_str=<results>, plots_dir_str=<results>/summary/plots)` (`:274-281`) | 异常仅打印; 参数名 `batch_dir_str/plots_dir_str` |
| 7/7 交付物核对 | `:284` | 逐项 `path.exists()` 打 `[OK]/[MISSING]` | 交付物 = `summary/赛道二_results.csv`、`<root>/ultimate`、`summary/feature_importance/key_regulatory_biomarkers.csv`、`summary/anomaly_report.md`、`summary/metrics_tables`、`summary/feature_importance`、`summary/plots` (`:286-294`); 无 target 时跳过含"赛道二"/"ultimate"两项 (`:297-299`) |

`convert_raw_csv_to_npy` (`:40-91`): 固定 `(N,23,8)` 张量, `seq_ch_idx={A:0,C:1,G:2,T:3}`, 表观 `{ctcf:4,dnase:5,h3k4me3:6,rrbs:7}`; 表观列小写包含匹配; 字符串长度 23 → `1/A/Y/T` 为 1; 数值 → 整列填充; 无 target 列 → `np.random.uniform(0.5,0.9)` 假标签; 输出 `<cl>_features_23x8.npy`、`<cl>_features_184.npy`、`<cl>_labels.npy`、`<cl>_metadata.csv` (`:87-90`)。

---

# 17. Local Workflow API (app/backend/crispr_workspace 逐文件函数级; 完整 API 表)

包原则 (`app/backend/crispr_workspace/__init__.py:1-11`): 只做项目/配置/编排/启停/状态/日志与结果浏览; 科学计算一律子进程或只读产物;**零第三方运行时依赖**; 版本 `0.1.0`。静态守卫测试 `app/backend/tests/test_no_training_dependency.py` 禁止 `import src/train/predict/data_digging` 与顶层 `import analyse`。

## 17.1 config.py (48 行)

| 函数 | 行 | 事实 |
|---|---|---|
| `repo_root()` | 10-11 | `Path(__file__).parent.parent.parent` = 仓库根 |
| `default_workspace_root()` | 14-19 | `$CRISPR_WORKSPACE_ROOT` 覆盖, 否则 `<repo>/workspace` |
| `config_root()` | 22-27 | `$CRISPR_WORKSPACE_CONFIG` 覆盖, 否则 `~/.crispr_workspace` |
| `ensure_dirs(root)` | 30-32 | 建 `projects/ qc_sessions/ runs/` |
| `allowed_read_roots()` | 35-48 | workspace 根 + (存在时) `<repo>/results`; Artifact Resolver 白名单 |

## 17.2 store.py (41 行)

`STAGE_ORDER = ["data","qc","mapping","training","analysis","reports"]` (`:13`); `utcnow()` ISO 秒级 UTC (`:16-17`); `read_json(path)` 缺失→`None` (`:20-25`); `write_json(path,obj)` 原子写 (`tempfile.mkstemp` 同目录 + `os.replace`, 失败清理 tmp, `:28-41`)。

## 17.3 fingerprint.py (61 行)

`file_sha256(path, chunk=1MB)` (`:9-17`); `fingerprint_dataset(paths)`: 目录取 `.csv/.tsv`, 文件直接用, 逐文件 `{name,path,size,sha256}` 按 path 排序后 digest = sha256(path+sha256 串接), 返回 `{algorithm:"sha256", digest, files, n_files, total_bytes}` (`:20-55`); `same_fingerprint(a,b)`: 双方有 digest 且相等 (`:58-61`)。

## 17.4 project.py (136 行) — `project_manifest.json` 为状态源

| 函数 | 行 | 事实 |
|---|---|---|
| `_slug` / `new_project_id` | 16-22 | id 形如 `proj_%Y%m%d_%H%M%S` |
| `projects_root(root=None)` / `project_dir` | 25-34 | `<ws>/projects[/<pid>]`, 自动建目录 |
| `create_project(name, dataset_paths, root, reuse_fingerprint)` | 37-70 | 写 manifest: `schema="project.manifest/1"`, `project_id/name/created_at/updated_at`, `dataset{input_paths(abs), fingerprint, imported}`, `stages` 全 `pending`, `config_versions{analysis_plan:null, workflow_config:null, training_config:null}`; 建 6 子目录 `inputs/qc/training/analysis/reports/artifacts`。**绝不启动 QC/Training** |
| `open_manifest` / `_resolve` | 73-84 | 缺失 → `FileNotFoundError` |
| `update_stage(root, pid, stage, status, detail=None)` | 87-98 | stage 必须 ∈ `STAGE_ORDER` 否则 `ValueError`; 写 `stages[stage]` + `updated_at` + 可选 `stage_detail[stage]` |
| `list_projects(root=None)` | 101-112 | 目录升序收集有 manifest 的项目 |
| `create_from_qc(root, qc_session_id, name, current_paths=None, qc_manager=None)` | 115-136 | 会话必须 `completed` 否则 `ValueError`; 传 `current_paths` 时先比对指纹, 不一致 → `ValueError("数据集已变化...")`; 调 `create_project(..., reuse_fingerprint=old_fp)` |

## 17.5 qc_service.py (141 行)

`MANIFEST="session_manifest.json"`, `ENGINE=analysis/data_QC.py` (`:23-24`)。`_copy_inputs(src,dst)` (`:27-57`): 目录取 `csv/tsv`, 文件直用; 0 个 → `ValueError("no dataset file given")`; 单个直接返回; 多个 → 复制到 `<session>/inputs_src/` 并去重文件名。
`QCSessionManager` (`:60`): `__init__` → `<ws>/qc_sessions`; `list()` (`:71-78`); `get(sid)` (`:80-90`) 合并 `qc_summary.json` 与 `figures`(会话 `figures/*.png` + 会话根 `*.png`, 去重排序); `start(input_paths, note)` (`:92-114`) 生成 `qc_%Y%m%d_%H%M%S`, 写 manifest (`status="running"`, `mode="standalone"`, `dataset{inputs,fingerprint,n_samples_known:False}`, `outputs{summary,report,figures_dir}`), 然后 `_launch`; `_launch` (`:116-133`) 记录 `command`, `subprocess.run(capture_output=True, timeout=7200)`, 回写 `status/returncode/completed_at/stderr_tail(尾 2000 字符)`; 超时 → `failed`, `stderr_tail="timeout"`; `fingerprint(input_paths)` (`:135-136`); `reusable(prev_manifest,new_fp)` 静态 (`:138-141`)。

**注意**: `_launch` 只把 `inputs[0]` 传给引擎 (`:120`) —— 多文件输入时实际只体检 staged 的第一个文件, 与注释"单文件或已 staging 的目录"不符 (见 §23)。

## 17.6 training.py (494 行) — TrainingConfig / Preflight / Runtime Adapter

常量: `MODELS=[linear,xgboost,mlp,transformer,cnn]`, `CELL_LINES=[hct116,hek293t,hela,hl60]`, `SPLITS=[single,all,mixed]`, `KERNELS=[3,5,7]`, `MIXED_SEEDS=[42,43,44,45]`, `STATUS_FILE="training_status.json"`, `DONE_FILE="done.rc"` (`:27-34`)。

### TrainingConfig 字段 (`@dataclass`, `:37-187`) 与 CLI 映射
| 字段 | 默认 | 映射 (build_command) |
|---|---|---|
| `kind` | `"dig"` | 选脚本: `dig`→workflows/training/data_digging.py / `predict`→workflows/prediction/predict.py (`:128-132`) |
| `models` | `["linear","xgboost"]` | `--models` |
| `cell_lines` | 4 系 | `--cell-lines` |
| `split_types` | `["single"]` | `--split-types` (仅 dig) |
| `environments` | `None` | `--environments` (与 training_scope_epis 互斥, 后者优先, `:145-148`) |
| `training_scope_epis` | `None` | `--training-scope-epis` |
| `mixed_seeds` / `cnn_kernels` | `[42-45]` / `[3,5,7]` | **无 CLI 映射** (data_digging 无对应用法, 见 §23) |
| `epochs…conv_channels2` (14 项) | 与 data_digging 默认一致 | `--epochs --batch-size --learning-rate --dropout --weight-decay --patience --min-delta --hidden-dim1 --hidden-dim2 --conv-channels1 --conv-channels2` (`:149-154`) |
| `train_ratio/valid_ratio/test_ratio` | 0.70/0.15/0.15 | **未出现在 dig 命令中** (build_command 未追加, 依赖 workflows/training/train.py 默认) |
| `use_scaler` | False | `--use-scaler` (仅真值追加) |
| `data_dir/results_dir/model_dir/logs_dir` | `""` → `default_dirs()` 填 `<repo>/data/processed`、`<repo>/results`、`<repo>/models`、`<repo>/logs` (`:93-102`) | `--data-dir --model-dir --results-dir --logs-dir` |
| `batch_name` | `""` | `--batch-name` |
| `runtime` | `"local_cpu"` | 选 adapter (`local_cpu`/`local_gpu`/`hpc`) |
| `device` | `None` | `--device` |
| `workers`/`in_process`/`threads_per_worker` | 1 / True / 0 | `--in-process`; workers>1 → `--workers`, 且 threads>0 才 `--threads-per-worker` (`:157-162`) |
| `cuda_visible` | `None` | 不由 CLI 传递: LocalRuntime 设环境变量 `CUDA_VISIBLE_DEVICES` (`:271-272`) |
| predict 专用: `target_input/target_epigenetics/ultimate_cv_folds/ultimate_epochs/ultimate_seed/candidate_top_k` | ""/None/10/15/42/20 | `--target-input --target-epigenetics --ultimate-cv-folds --ultimate-epochs --ultimate-seed --candidate-top-k` (`:169-187`) |
| `dry_run` | False | 两脚本均追加 `--dry-run`; LocalRuntime 只写 plan 不启进程 |

`from_dict` 过滤未知键 (`:104-109`); `validate()` (`:112-125`) 检查 models/cell_lines/split_types 取值、runtime 枚举、`kind=predict` 且 `target_input` 非空时必须存在。
`preflight(cfg)` (`:190-221`): 逐项 `{"check","ok","message"}` —— **Dataset exists** (data_dir 存在且 `feature_schema.json` 存在, 或存在 `*_features_*.npy`), **Output writable (results/models/logs)** (mkdir + `os.access(W_OK)`), **Training configuration valid** (validate 汇总), **Runtime available** (恒 True, 注释: 真实可用性由 Adapter 探测), **Target input exists** (仅 predict + target_input)。返回 `{"ok":bool,"checks":[...]}`。

### LocalRuntime (`:235-357`)
| 方法 | 行 | 事实 |
|---|---|---|
| `submit` | 242-281 | run_id = `_run_id(kind)` = `dig_/predict_%Y%m%d_%H%M%S`; 建 `runs/<rid>`; 先写 status (`schema="training.status/1"`, `status="dry-run"|"running"`, `runtime/device/batch_name/started_at/command(空格连接)/cwd/pid=None/job_id=None/progress{done:0,total:None,ratio:None}/log_path/done_file`); `dry_run` → **只写 `plan.json` (asdict(cfg)) 并返回, 不起进程**; 否则 `Popen(cmd, cwd=repo, env 可选 CUDA_VISIBLE_DEVICES, stdout=run.log, stderr=STDOUT, start_new_session=True)` (GUI 解耦) 后回写 `pid` |
| `status` | 283-289 | 读 status → `_update_status` |
| `_update_status` | 291-306 | 有 `done.rc` → `completed`(rc=0)/`failed` 且写 `returncode/ended_at`; 否则若 pid 存在用 `os.kill(pid,0)` 探活, 进程消失 → `_guess_from_log`; 最后 `_progress_from_log` 并落盘 |
| `_guess_from_log` | 308-314 | 日志含 `[✓] All batch experiments executed.` 或 `赛道二_results.csv` → `completed`, 否则 `failed`; 无日志 → `running` |
| `_progress_from_log` (static) | 316-330 | 正则 `Total:\s*(\d+)` 取 total, `Experiment\s+(\d+)/(\d+)\] Starting` 取最大 done; `ratio = done/total` |
| `cancel` | 332-346 | `os.killpg(pid, SIGTERM)` (捕获异常); 写 `status="cancelled"` + `cancelled_at` |
| `resume` | 348-357 | 删 `done.rc`; 读 `runs/<rid>/config.json` → `TrainingConfig(**...)` → 重新 `submit` (同命令重跑, 靠 data_digging 的 completed 判定续跑) |

### HpcRuntime (`:360-437`)
| 方法 | 行 | 事实 |
|---|---|---|
| `submit` | 371-408 | 写 `config.json`; 生成 `submit.sh`: `#!/usr/bin/env bash` + `set -euo pipefail` + 注释"示例: 单卡执行; 8 卡分片请按 HPC_EXPERIMENT_PROTOCOL.md" + `export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}` + `cd <repo>` + `<cmd> > <rdir>/run.log 2>&1` + `echo $? > <rdir>/done.rc`; status: `status="submitted_external"`, `runtime="hpc"`, `launcher/job_id=None/progress/note`("GUI 不直接管理 HPC 作业; 请按平台提交 launcher 或 sbatch 后把 job_id 填入, 进度由 job 侧回写 training_status.json") |
| `status` | 410-420 | 有 `done.rc` → `completed` (**不读 rc**, 即便 rc≠0 也判 completed); 否则复用 `LocalRuntime._progress_from_log` |
| `cancel` | 422-427 | 只把状态标记 `cancelled` + note "取消需在 HPC 侧执行 scancel (GUI 不做)" |
| `resume` | 429-437 | 删 `done.rc`, 状态置 `submitted_external` + `resumed_at`; **不重新生成脚本、不重跑** |

模块级: `adapter_for(runtime, ws)` (`:440-443`, 非 hpc 一律 LocalRuntime); `submit(cfg, workspace_root, save_config=True)` (`:446-458`) 先 validate, 提交后把 `asdict(cfg)` 写到 `runs/<rid>/config.json`; `status/cancel/resume(run_id, ws)` (`:461-482`) 以 status 文件里的 `runtime` 路由; `list_runs(ws)` (`:485-494`) 收集 `runs/*/training_status.json`。

## 17.7 analysis.py (256 行)

| 函数 | 行 | 事实 |
|---|---|---|
| `TASK_PLAN_MAP` | 21-38 | 16 个 task_id → engine plan 字段路径 (如 `environment_anova → ["environment","anova"]`, `evidence_integration → ["evidence","evidence_integration"]`) |
| `_default_plan_dict()` | 41-56 | `plan_version:"1.0"`, `run_qc:True`, `run_prediction_analysis:True`, `environment{enabled,conditional_effect,main_effect,interaction:False,shapley:False,anova:False}`, `sequence{enabled,position_attribution,ism,motif_discovery,motif_enrichment:False}`, `cell_line{enabled,heterogeneity,interaction:False,consistency}`, `statistics{bootstrap,hypothesis_testing,fdr_correction}` (**无 enabled**), `evidence{cross_model,evidence_integration,hypothesis_generation}` (**无 enabled**) —— 代码注释 `:52` 明确"引擎 StatisticsPlan/EvidencePlan 容器无 enabled 字段 (勿加)", 与 `analysis/plans.py:54-65` 一致 |
| `registry_tasks()` | 59-103 | 优先 `analyse.registry.registered_tasks()`, 映射为 `{task_id, display(←name), category, dependencies}`; 异常 → 16 条硬编码回退表 (含 category `core`/`advanced`, 与 registry 的 `qc/biology/statistics/evidence` 不同) |
| `heuristic_availability(batch_dir)` | 106-155 | 扫 batch 目录 (跳过 `summary`): 细胞系集合 (4 系名)、`has_cnn`、`n_experiment_dirs`、环境组合数 (正则 `(sequence[\w]*)`); 规则: 无 batch → 全部不可用; `cellline_heterogeneity` 需 ≥2 细胞系; `cnn_ism` 需 CNN 目录; `environment_*`/`prediction`/`evidence_integration`/`hypothesis_generation`/`bootstrap` 需检测到环境组合。返回 `{task_id: {available, reason}}` |
| `build_plan_dict(selected, defaults=None)` | 158-179 | 以默认 plan 为底, 按 `TASK_PLAN_MAP` 把选中 task 置 True / 未选置 False; 顶层 `environment/sequence/cell_line` 的 `enabled` = 其子项任一为真 (`:175-178`); `statistics/evidence` 不加 enabled |
| `run(batch_dir, output_dir, selected_task_ids, project_meta)` | 182-210 | 建 output; 写 `analysis_plan.json`; 写 `analysis_run.json` (`schema="analysis.run/1"`, status running, batch_dir/output_dir/plan_path/selected_tasks/project); `Popen([python,"-m","analyse.pipeline","--batch-dir",...,"--output",...,"--analysis-plan",...], cwd=repo, stdout=analysis_run.log, start_new_session=True)`; 回写 `pid` |
| `analysis_status(output_dir)` | 213-243 | 合并 `analysis_run.json` + `analysis_status.json`: 有 engine status → `engine_status` + `task_status{task_id:status}`; 全 task ∈ (`completed/failed/skipped/unavailable`) → `completed` 否则 `running`; 无 engine status 但有 `execution_log.json` → `completed`; 否则若 pid 不存在且状态仍 running → `failed` + `error_tail`(日志尾 1500 字符) |
| `list_outputs(output_dir)` | 246-256 | 浅层列 `summary/*.md`、`tables/*.csv`、`figures/*.png` → `{name,path,kind}` |

## 17.8 artifacts.py (158 行)

`PREVIEW_ROWS=200`, `MAX_BYTES=256MB` (`:18-19`)。`ArtifactError` (`:22`); `_confine(path, roots)` 必须落在白名单根内否则抛错 (`:26-34`); `classify(path)`: csv/tsv→`csv`, md/markdown→`md`, txt→`txt`, json→`json`, png/jpg/jpeg/gif/webp→`image`, log→`log`, 其它 `other` (`:37-49`); `_sniff_numeric` (`:52-62`)。
`resolve_artifact(rel_or_abs, base_dirs=None, offset=0, limit=None)` (`:64-119`): roots = `allowed_read_roots()` ∪ `base_dirs`; 相对路径依次尝试 workspace 根 / 仓库根 / 各 root; `_confine` → 不存在/非文件 → `ArtifactError`; 返回 `{path,name,kind,size,mtime}` + 类型负载: csv → `_csv_payload`; md/txt → `text`(超 256MB 报"file too large to preview"); json → `json`; image → 仅 meta (二进制走 `/api/artifact-raw`); other → `text:""`。
`_csv_payload(p, offset, limit)` (`:122-158`): 一次读入(上限 256MB)后 csv.reader; 统计 `data_rows` 总数, 取 `[offset, offset+limit)` 区间; `limit` 默认 `PREVIEW_ROWS`; `columns` 取表头; `type_hints` 按每列前 50 行过半可数值 → `numeric` 否则 `text`; 返回 `{data_rows, offset, limit, columns, rows, type_hints, truncated, row_limit}`。

## 17.9 server.py (279 行) — 完整 API 表

`ThreadingHTTPServer` + 单 `Handler`; `_dispatch` 统一 try/except: `FileNotFoundError→404`, `ValueError→400`, 其它 `→500 {"error": "Type: msg"}` (`:233-238`); 响应 JSON + `Access-Control-Allow-Origin: *` (`:33-40`); 文件响应 `_send_file` (`:43-50`); `do_OPTIONS` 204 + CORS 头 (`:246-251`)。
**路由总数 = 26 条** (`server.py:70-232`; 构成: 19 条 `if path == "..."` 精确分支 + 5 条 `path.startswith(...)` 动态段分支 + 2 条 `path.endswith("/cancel"|"/resume")` 分支), 全部集中在 `_dispatch` 的 if 链。

| # | 方法 | 路径 | 请求 | 响应 | 作用 | 行 |
|---|---|---|---|---|---|---|
| 1 | GET | `/api/health` | — | `{ok,engine,version,workspace_root}` | 健康检查 | 70-73 |
| 2 | GET | `/api/projects` | — | `{projects:[manifest]}` | 项目列表 | 76-77 |
| 3 | POST | `/api/projects` | `{name,dataset_paths}` | 201 manifest | 建项目 (不跑 QC/训练) | 78-84 |
| 4 | GET | `/api/projects/{id}` | — | manifest | 打开项目 (状态源) | 85-87 |
| 5 | POST | `/api/projects/from-qc` | `{session_id,name,current_paths?}` | 201 manifest | 复用已完成 QC 建项目 (指纹守卫) | 88-92 |
| 6 | POST | `/api/projects/{id}/stage` | `{stage,status,detail?}` | manifest | 回写阶段状态 | 189-194 |
| 7 | GET | `/api/qc/sessions` | — | `{sessions:[...]}` | QC 会话列表 | 95-96 |
| 8 | POST | `/api/qc/sessions` | `{input_paths:[],note}` | 201 session | 启动 QC 子进程 | 97-101 |
| 9 | GET | `/api/qc/sessions/{id}` | — | session(+`qc_summary`,`figures`) | 会话详情/轮询 | 102-104 |
| 10 | POST | `/api/qc/fingerprint` | `{input_paths}` | `{fingerprint}` | 计算指纹 (**前端未调用**) | 105-107 |
| 11 | POST | `/api/qc/reuse-check` | `{session_id,input_paths}` | `{reusable,fingerprint}` | 复用校验 (**前端未调用**) | 108-112 |
| 12 | GET | `/api/training/defaults` | — | `{config:TrainingConfig默认, allowed:{models,cell_lines,split_types,cnn_kernels,mixed_seeds,runtimes}}` | 参数面下发 | 115-124 |
| 13 | POST | `/api/training/preflight` | `{config}` | `{ok,checks[]}` | 预检 | 125-127 |
| 14 | POST | `/api/training/submit` | `{config}` | 201 status | 提交 (validate+adapter 路由) | 128-131 |
| 15 | GET | `/api/runs` | — | `{runs:[...]}` | 运行历史 | 132-133 |
| 16 | GET | `/api/runs/{id}` | — | status | 轮询状态 | 134-137 |
| 17 | GET | `/api/runs/{id}/log` | — | `{lines: 末 250 行}` | 日志尾部 | 138-146 |
| 18 | POST | `/api/runs/{id}/cancel` | — | status | 取消 (Local 杀进程组) | 147-149 |
| 19 | POST | `/api/runs/{id}/resume` | — | status | 续跑 | 150-152 |
| 20 | GET | `/api/analysis/tasks` | `?batch=` | `{tasks:[{...,available,reason}]}` | Registry 任务目录 + 启发式可用性 | 155-162 |
| 21 | POST | `/api/analysis/plan` | `{selected_tasks}` | `{plan}` | 生成 engine AnalysisPlan (**前端未调用**) | 163-166 |
| 22 | POST | `/api/analysis/run` | `{batch_dir,selected_tasks,project_id?,output_dir?}` | 201 run manifest | 起 analyse.pipeline 子进程 | 167-181 |
| 23 | GET | `/api/analysis/outputs` | `?output_dir=` | `{output_dir,entries[]}` | 列 summary/tables/figures | 182-186 |
| 24 | GET | `/api/analysis/status` | `?output_dir=` | merged status | 逐 task 状态 | 196-200 |
| 25 | GET | `/api/artifacts` | `?path=&offset=&limit=&base=` | artifact payload / 404 | Resolver + CSV 分页 | 204-217 |
| 26 | GET | `/api/artifact-raw` | `?path=` | 二进制 (按 kind 定 MIME) | 原图/原文件下载 | 218-230 |

默认输出目录规则 (路由 22): `output_dir` 优先 → 有 `project_id` 用 `<ws>/projects/<pid>/analysis` → 否则 `<ws>/runs/analysis_tmp` (`:173-178`)。
`serve(host="127.0.0.1", port=8765, root=None, blocking=True)` (`:254-267`): 设全局 `_workspace_root`, `ensure_dirs`, 建 `QCSessionManager`, `ThreadingHTTPServer`, `daemon_threads=True`; `__main__` 支持 `--host/--port/--root` (`:270-279`)。

---

# 18. Frontend (页面树/组件树; 每组件职责与所用 API; Artifact Viewer 行为; Notebook 依赖门禁; vitest)

技术栈: React 18 + TS + Vite 5 + Tailwind 4 (`app/frontend/package.json:13-27`)。scripts: `dev`/`build`(`tsc --noEmit && vite build`)/`preview`/`typecheck`/`test`(`vitest run`) (`:6-12`)。`vite.config.ts`: port 5173, 代理 `/api → http://127.0.0.1:8765`(changeOrigin) (`vite.config.ts:7-15`)。API base 可由 `VITE_API_BASE` 覆盖 (`src/api/client.ts:2`)。

## 18.1 页面树 / 组件树

```
main.tsx (ReactDOM.createRoot + StrictMode)            src/main.tsx:6-10
└── App.tsx  Screen = home | new-project | project{id} | qc    src/App.tsx:7-37
    ├── HomeView(onCreate,onQc,onOpen)                        views/HomeView.tsx:5-58
    │     └── StageSummary (6 阶段圆点)                        :60-72
    ├── CreateProjectView(onOpen,onExit)                      views/CreateProjectView.tsx:4-49
    ├── StandaloneQcView(onExit,onOpenProject)                views/StandaloneQcView.tsx:8-101
    │     └── QcDashboard(session)                            components/QcDashboard.tsx:27-74
    │           (该视图 import 了 ArtifactViewer 但未渲染: views/StandaloneQcView.tsx:4)
    └── WorkspaceView(projectId,onExit)                       views/WorkspaceView.tsx:21-127
          ├── StageDot (阶段圆点)                              :134-140
          ├── RunsHistory                                      components/RunsHistory.tsx:4-33
          ├── NotebookCell ×6                                  components/NotebookCell.tsx:5-34
          │     └── StatusChip                                 components/StatusChip.tsx:13-21
          ├── ArtifactViewer (Cell 2, md)                       WorkspaceView.tsx:98
          ├── TrainingPanel (Cell 4)                            components/TrainingPanel.tsx:6-136
          │     └── RunMonitor                                 :138-161
          ├── AnalysisPanel (Cell 5)                            components/AnalysisPanel.tsx:10-91
          │     └── ArtifactViewer (md 报告)                    :88
          └── ReportsPanel (Cell 6)                             components/ReportsPanel.tsx:5-41
                └── MarkdownViewer                              components/artifacts/MarkdownViewer.tsx:121-135
ArtifactViewer → CsvViewer | MarkdownViewer                  components/artifacts/ArtifactViewer.tsx:5-9
CsvViewer → evidenceBadge / format.ts                        components/artifacts/CsvViewer.tsx:12-27, 29-143
```

## 18.2 各组件职责与所用 API

| 组件 | 职责 | 调用的 API | 关键细节 |
|---|---|---|---|
| `App` | 4 屏状态机 (无路由库) | — | `Screen` 联合类型 `App.tsx:7-11` |
| `HomeView` | 双入口卡片 + 项目列表 + 6 阶段圆点 | `projectApi.list()` | 失败置空数组 (`:14`) |
| ~~`CreateProjectView`~~ | 已移除：Create Project 直接创建并进入 Workspace（batch 在 Cell 01 填写） | — | — |
| `WorkspaceView` | 左侧 6 阶段导航 + Notebook 主区; 触发 workflow QC | `projectApi.open`, `qcApi.start`, `projectApi.updateStage(analysis, completed, {output_dir})` | QC 启动后仅存 `qcSession` 本地态, **不回写 `stages.qc`**; 只有 analysis 阶段被写回 (`:116-119`) |
| `StandaloneQcView` | 独立 QC: 多路径输入 → 启动 → 1.2s 轮询 → Dashboard/历史 | `qcApi.list/start/get`, `projectApi.fromQc` | `onOpenProject` 复用指纹建项目 (`:72-77`); 失败显示 `stderr_tail` 末 500 字符 |
| `QcDashboard` | 只读渲染 `qc_summary` + 图集 + 报告下载 | `artifactApi.rawUrl` | Overall 判定: 有 ambiguous/outliers → 🟡; `qc_pass===false` → 🔴; true → 🟢 (`:15-25`) |
| `NotebookCell` | Cell 容器: 序号/标题/StatusChip/hint/actions/折叠 | — | `status !== "pending"` 才显示 chip (`:19`) |
| `StatusChip` | 7 态 → 文案与配色 | — | MAP: completed/running/failed/pending/skipped/unavailable/warning (`:3-11`) |
| `EvidenceBadge` | 把后端 evidence 字符串渲染为统一 Badge, **不做阈值判定** | — | 正则 strong/moderate/model-specific\|exploratory/inconclusive; 无匹配原样显示 (`:5-23`) |
| `TrainingPanel` | 训练配置 (Models/Cells/Splits/Scope epi/Runtime/dry-run/batch/epochs) + Preflight + 提交 + 轮询 + Cancel/Resume | `trainingApi.defaults/preflight/submit/status/cancel/resume/log` | 默认勾选 `allowed.models[0]` 与 `allowed.cell_lines[0]`, splits `["single"]`, runtime `local_cpu`, **dry-run 默认勾选**(`:15`); 仅 `status==="running"` 才 1.5s 轮询 (`:53-60`); Cancel 按钮在 running/submitted_external 显示, Resume 在 cancelled/failed 显示 (`:116-117`) |
| `RunMonitor` | run_id/status/command 摘要 + 进度条 + 日志 (末 250 行) | `trainingApi.log` | 依赖变化时重取日志 (`:140-143`) |
| `RunsHistory` | 侧栏运行历史列表 + 点击展开末 30 行日志 | `trainingApi.runs/log` | |
| `AnalysisPanel` | Registry 任务 (core/advanced 分组) 勾选 + batch 路径 + 运行 + 轮询 + 完成后渲染总览报告 | `analysisApi.tasks/run/status`, `ArtifactViewer` | 初始选中 `{qc, prediction}` (`:12`); `available===false` 的任务 disabled 并显示 reason (`:65-71`); 完成时回调 `onCompleted(out)` 并默认读 `<out>/summary/00_overview.md` (`:35`) |
| `ReportsPanel` | 列 analysis 产物中的 md 并阅读 | `analysisApiOutputs.list`, `MarkdownViewer` | 优先选 `00_` 前缀 md (`:14-15`); `outputDir` 来自 `stage_detail.analysis.output_dir` (`WorkspaceView.tsx:129-132`) |
| `ArtifactViewer` | 按 kind 分派 csv/md | — | 其它 kind 显示 Unsupported (`:8`) |
| `CsvViewer` | 数据浏览器: 服务端分页(PAGE=50)/当前页搜索/列排序/列显隐/冻结首列/数值格式化/缺失 `—`/Evidence 列 Badge/方向箭头 | `artifactApi.page(path, offset, limit)` | 方向箭头仅对表头匹配 `delta\|d_r2\|coefficient\|effect\|main_r2` 且不匹配 `gain\|weight\|cover\|attention\|pfi` 的数值列 (`:7-8, 20-23`); 翻页靠 `truncated`/`pages` (`:111`) |
| `MarkdownViewer` | 安全科研 Markdown 渲染: 标题/列表/引用/hr/代码块/表格/段落, 内联粗体与行内码 | `artifactApi.asMarkdown`, `artifactApi.rawUrl` | 先 `esc()` 转义 HTML 再识别结构 (`:5-9, 32`); 图片/链接经 `resolveRel(basePath, rel)` 解析为绝对路径后交给 `/api/artifact-raw` (`:11-19, 30-31, 133`); 图片加载失败隐藏 (`:37`) |

## 18.3 Artifact Viewer 行为 (端到端)

1. 组件把绝对路径或相对 workspace 根路径交给 `artifactApi`; 相对路径由后端在 workspace 根/仓库根/白名单根中解析 (`artifacts.py:77-92`)。
2. CSV: `artifactApi.page` → `/api/artifacts?path=&offset=&limit=`; 每页 50 行; 搜索与排序**仅作用于当前页数据** (前端 `filtered`/`sorted` 基于已取 `rows`, `CsvViewer.tsx:58-79`); 行总数来自 `data_rows`。
3. Markdown/txt: `artifactApi.asMarkdown` → `/api/artifacts` 返回 `text`; 图片与链接改走 `/api/artifact-raw?path=`。
4. 原始值始终保留在 `title` 属性中, 展示层只格式化不回写 (`lib/format.ts:1`, `CsvViewer.tsx:22-25`)。
5. 越界路径 → 后端 `ArtifactError` → 404 → 组件显示 `Unable to render artifact — ...`。

## 18.4 Notebook 依赖门禁

| Cell | 门禁条件 | 未满足表现 |
|---|---|---|
| 1 Data | `m.dataset.imported` | 显示 `no dataset imported` hint; fingerprint 显示 `—` |
| 2 QC | 按钮 `disabled = runQc \|\| !input_paths.length` | 文案 "Waiting for dependency: 请先在 Data 阶段导入数据集…" (`WorkspaceView.tsx:96-97`) |
| 3 Mapping | `m.stages.qc !== "completed"` → 显示 Waiting; 提示决策写入 `workflow_config.json` (`:102-107`) | 仅文案, 无按钮 |
| 4 Training | 无门禁 (TrainingPanel 自行 preflight) | — |
| 5 Analysis | `m.stages.training !== "completed"` → 黄色提示, **但仍渲染 AnalysisPanel** (软门禁, `:113-115`) | "可显式指定已有 results batch 路径运行分析" |
| 6 Reports | `analysisOutputOf(m)` 为 null | "分析运行完成后自动填充（Analysis 阶段）" (`ReportsPanel.tsx:19`) |

**事实缺口**: 除 AnalysisPanel 完成回调写 `analysis` 阶段外, 仓库中不存在把 `qc/training/mapping/reports` 置为 `completed` 的生产代码路径 (`updateStage` 调用点仅 `WorkspaceView.tsx:118`), 因此 3/6 号门禁在实际使用中不会被自动解除 (见 §23)。

## 18.5 vitest 测试

| 文件 | 用例数 | 覆盖 |
|---|---|---|
| `src/lib/format.test.ts` | 3 | `formatNumber` 科学计数/千分位、`isMissing`/`missingLabel` 不把缺失变 0、`effectGlyph` 方向仅对明确有向值 |
| `src/lib/resolve.test.ts` | 1 | `resolveRel` 解析 `../figures/a.png` 与同级路径 |
| `src/components/StatusChip.test.tsx` | 1 | jsdom 渲染语义标签 (Completed/Running/Unavailable) |
| `src/components/EvidenceBadge.test.tsx` | 2 | 已知 evidence 串映射 Badge; 未知值原样透传 |
| 合计 | **4 文件 / 7 用例** | `docs/acceptance_record.md` 记录一致; 无组件级 E2E/快照测试; jsdom 通过文件头 `// @vitest-environment jsdom` 指定, `vite.config.ts` 无 `test` 段 |
| 辅助 | `src/test/render.tsx` | `renderJsx`/`cleanupJsx` 基于 `react-dom/client` + `act` |

---

# 19. Runtime / HPC (LocalRuntime vs HpcRuntime 状态机; 命令生成; 日志/状态文件位置; Slurm 边界)

## 19.1 状态机 (字段来源: `training_status.json`)

```
LocalRuntime:
  dry_run=True  ──submit──▶ "dry-run"            (终态; 只写 plan.json)
  dry_run=False ──submit──▶ "running"  ──done.rc rc=0──▶ "completed"
                                      ──done.rc rc≠0──▶ "failed"
                                      ──进程消失且无 done, 日志命中完成串──▶ "completed"
                                      ──进程消失且无 done, 日志未命中────▶ "failed"
                                      ──cancel(SIGTERM 进程组)──────────▶ "cancelled"
  "cancelled" | "failed" ──resume(删 done.rc, 读 config.json, 重跑同命令)──▶ "running"

HpcRuntime:
  ──submit──▶ "submitted_external"  ──done.rc 出现──▶ "completed"   (不校验 rc)
                                    ──cancel──▶ "cancelled" (仅标记; 真取消需 scancel)
                                    ──resume──▶ "submitted_external" + resumed_at (不重提交)
```

`training_status.json` 字段全集 (以 `LocalRuntime.submit` 为基, `training.py:248-264`): `run_id, kind, schema="training.status/1", status, runtime, device, batch_name, started_at, command, cwd, pid, job_id, progress{done,total,ratio}, log_path, done_file`; 运行期追加 `returncode/ended_at` (`:296-298`) 或 `cancelled_at` (`:343-345`) 或 `resumed_at` (HPC, `:435`); HPC 额外 `launcher/note` (`:399,404`)。

## 19.2 命令生成

- 基础: `[sys.executable, <repo>/<script>]` (`training.py:134-135`); 脚本由 `kind` 决定。
- dig 命令参数顺序固定: `--batch-name, --data-dir, --model-dir, --results-dir, --logs-dir, --models…, --cell-lines…, --split-types…, [--training-scope-epis…|--environments…], --epochs…--conv-channels2, [--use-scaler], [--in-process], [--workers N [--threads-per-worker T]], [--device D], [--dry-run]` (`:137-167`)。
- predict 命令: `--data-dir, --results-dir, --batch-name, --models…, --cell-lines…, --ultimate-cv-folds, --ultimate-epochs, --ultimate-seed, --candidate-top-k, [--target-input], [--target-epigenetics…], [--device], [--dry-run]` (`:169-187`)。
- Local: `Popen(..., start_new_session=True)`, `CUDA_VISIBLE_DEVICES` 来自 `cfg.cuda_visible` (`:270-276`)。
- HPC: 生成 `submit.sh` (见 §17.6), 单卡示例, `export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}`。

## 19.3 日志/状态文件位置 (workspace 根 = `$CRISPR_WORKSPACE_ROOT` 或 `<repo>/workspace`, `config.py:14-19`)

```
<ws>/runs/<rid>/training_status.json    状态源 (每次 status 调用回写)
<ws>/runs/<rid>/run.log                 子进程 stdout+stderr (HPC 由 launcher 重定向)
<ws>/runs/<rid>/done.rc                 完成标记 (HPC 脚本 echo $?)
<ws>/runs/<rid>/config.json             TrainingConfig asdict (submit 包装器写; resume 读)
<ws>/runs/<rid>/plan.json               仅 dry-run
<ws>/runs/<rid>/submit.sh               仅 HPC launcher
<ws>/qc_sessions/<sid>/session_manifest.json · qc_summary.json · quality_report.md · figures/*.png
<ws>/projects/<pid>/project_manifest.json + inputs/qc/training/analysis/reports/artifacts/
```

## 19.4 Slurm / HPC 边界 (代码做了什么 / 没做什么)

**代码做了** (`training.py:360-437`): 生成可提交 bash launcher; 记录 `launcher` 路径与 job 回写约定; `status()` 允许从 `done.rc` + `run.log` 判定完成与进度; `cancel()` 只改状态并明确要求用户在 HPC 侧 `scancel`; GUI 完全不持有 HPC 作业句柄。
**代码没做** (注释 `:8-9, 361-364, 404-405` 明示): 不实现 Slurm/`sbatch`/`squeue`/`scancel`; 不管理 CUDA/MIG; 不生成 8 卡分片脚本; 不轮询 job_id (字段 `job_id` 恒为 `None`, 需用户手工填入)。

**HPC 文档中的真实执行协议** (`HPC_EXPERIMENT_PROTOCOL.md`):
- 环境: `conda activate /data9/zhanghaohong/zhangrixing/.conda/envs/crispr`, 工作目录 `/data9/zhanghaohong/zhangrixing/Submit` (§0, §1)。
- 推荐方式: **一个 GPU 一个 `workflows/training/data_digging.py` 进程 + `--in-process` 顺序执行**, 用 `CUDA_VISIBLE_DEVICES=$i` 与 `nohup` 后台启动, 8 片环境集合互不重叠且并集 = 16 组合, 每卡 168 实验, 共享 `--batch-name full` (§2)。
- 断点续跑语义: 中断后重跑同一命令, 已完成实验被 `data_digging` 的 completed 判定跳过 (§2 要点, §3)。
- 监控: `nvidia-smi -l 10`, `grep -c "Finished Successfully" logs/batch_gpu*.log` (§3)。
- 分析管线在 CPU 上跑: `collect_results.py --batch-dir results/full --split-types single all mixed` → `anomaly_treatment.py` → `importance_extraction.py --batch_dir` → `visualization.py --batch-dir` (§4)。
- 赛道二: `CUDA_VISIBLE_DEVICES=0 python workflows/prediction/predict.py ... --target-input ... --target-epigenetics CTCF Dnase H3K4me3 RRBS` (§5)。
- GPU 一致性: 不以"逐位相同"为唯一标准, 用指标级容差 (§6)。
- `HPC_ENVIRONMENT.md` 记录: gpu3 = 8×A100-80GB, Driver 550.54.14 / CUDA 12.4, `CUDA_VISIBLE_DEVICES=7` → 程序内可见 `cuda:0` (§1); gpu3 路径统一 `/data9/...` (§2); Python 3.10.21 / PyTorch 2.6.0+cu124 等实际版本 (§4)。
- **文档引用的文件缺失**: `HPC_launch_full_batch.sh`、`profile_experiment.py`、`regression_compare.py`、`environment.yml`、`requirements-hpc.txt` 在仓库中均不存在 (见 §23)。

---

# 20. 配置文件与状态文件体系

| 文件 | 生成者 (代码位置) | 读取者 | 关键字段 | 生命周期 |
|---|---|---|---|---|
| `feature_schema.json` | `core/features/engineering/feature_engineering.py` / `backend_runner.run_feature_engineering_step` (`:107-117`) | `predict.main`, `data_digging.load_environment_combinations`, `workflows/training/train.py`, `cell_line_division.load_feature_schema` | `sequence_length, channel_count, feature_count, channel_names[8], sequence_channels` | 数据准备后长期存在; 预测/训练每次读 |
| `<cl>_features_23x8.npy` / `_184.npy` / `_labels.npy` / `_metadata.csv` | 特征工程 / `convert_raw_csv_to_npy` (`backend_runner.py:87-90`) | `load_cell_line` → predict/data_digging/train | 张量形状、标签、元数据列 | 同上 |
| `project_manifest.json` | `project.create_project` (`:52-67`) / `update_stage` (`:87-98`) | `project.open_manifest/list_projects`, server 路由 2/4/5/6, 前端 `types.ProjectManifest` | `schema, project_id, name, created_at, updated_at, dataset{input_paths,fingerprint,imported}, stages{6}, stage_detail, config_versions{analysis_plan,workflow_config,training_config}` | 项目级; 每次 stage 回写 |
| `session_manifest.json` | `qc_service.QCSessionManager.start/_launch` (`:98-133`) | `qc_service.get/list`, `project.create_from_qc`, server 路由 7/8/9 | `session_id, schema="qc.session/1", created_at, mode, status(running/completed/failed), note, dataset{inputs,fingerprint,n_samples_known}, outputs{summary,report,figures_dir}, command, returncode, completed_at, stderr_tail` | QC 会话级 |
| `qc_summary.json` | 引擎 `analysis/data_QC.py` (`:1580`) | `qc_service.get`, `QcDashboard` | 引擎 QC 结构化结果 (`sample_size.total_samples/per_cell_line`, `length_consistency.recommended_length_L`, `ambiguous_bases.n_affected_sequences`, `outliers.n_outliers`, `qc_pass`) | QC 完成后 |
| `quality_report.md` / `figures/*.png` | `analysis/data_QC.py` (`:1577`) | `/api/artifacts`, `/api/artifact-raw`, QcDashboard | Markdown 报告; PNG 图 | QC 完成后 |
| `training_status.json` | `training.LocalRuntime/HpcRuntime` (经 `store.write_json`) | `training.status/list_runs`, server 路由 15-19, 前端 `RunManifest` | 见 §19.1 | run 级; 每次 status 回写 |
| `runs/<rid>/config.json` | `training.submit(save_config=True)` (`:454-458`) / `HpcRuntime.submit` (`:378`) | `LocalRuntime.resume` (`:356`) | `TrainingConfig` 全字段 | 提交时写, resume 读 |
| `runs/<rid>/plan.json` | `LocalRuntime.submit` (dry_run, `:266-269`) | 人工审阅 | `asdict(cfg)` | dry-run 专用 |
| `runs/<rid>/run.log` | `LocalRuntime.submit` Popen / HPC launcher | `_guess_from_log`, `_progress_from_log`, 路由 17, RunsHistory/RunMonitor | 训练/网格 stdout | run 级 |
| `runs/<rid>/done.rc` | HPC launcher `echo $? > done.rc` (`:388`) | `_update_status`, HpcRuntime.status | 返回码文本 | 完成标记 |
| `runs/<rid>/submit.sh` | `HpcRuntime.submit` (`:380-390`) | 用户手工提交 | bash 脚本 | HPC 专用 |
| `analysis_plan.json` | `analysis.build_plan_dict`→`run` (`:187-189`) | `analyse.pipeline --analysis-plan`, 前端 `analysisApi.plan` | engine `AnalysisPlan` (plan_version/run_qc/run_prediction_analysis/environment/sequence/cell_line/statistics/evidence) | 每次 run 前重写 |
| `analysis_run.json` | `analysis.run` (`:190-209`) | `analysis_status`, 前端 | `schema="analysis.run/1", started_at, status, batch_dir, output_dir, plan_path, selected_tasks, project, pid` | run 生命周期 |
| `analysis_run.log` | `analysis.run` Popen | `analysis_status` (`error_tail`) | 引擎 stdout | run 生命周期 |
| `analysis_status.json` | `analysis/pipeline.py:261` (`ExecutionPlan.save_status`) | `analysis.analysis_status`, 前端轮询 | `plan_version, started_at, completed_at, tasks[{task_id,selected,available,status,reason}]` | 引擎写, GUI 只读 |
| `execution_log.json` | `analysis/pipeline.py:290, 302-323` | `analysis_status` 兜底判 completed | `executed{task→status}`, `figures[]` | 引擎写 |
| `analysis/{tables,summary,figures}/` | `PipelineArtifacts.create` (`analysis/pipeline.py:29-40`) | `analysis.list_outputs`, ReportsPanel, ArtifactViewer | 表格 csv / 报告 md / 图 png | 分析产物 |
| `progress.json` (ultimate_dir) | `predict._save_progress` (`:868-870`) | `_load_progress`, `_kind_done`, 断点续跑 | `{"models":[{model,config,cv_r2,cv_rmse,cv_r2_std,file,preds_file,n_rows,lr_weights?,lr_names?}]}` | 每模型完成即原子重写 |
| `preds_<kind>.npy` | `run_ultimate_with_resume` (`:977-980`, 原子写) | `_kind_done` 存在性判据; 复用时 `np.load` | `float64 (M,)` clip 0..1 | 与 progress 条目同时生效 |
| `ultimate_summary.json` | `run_ultimate_with_resume` (`:996-999`); 旧路径 `train_ultimate_models` (`:542-557`) | 人工/下游 | `n_samples, cv_folds, epochs, seed, n_seq_channels, models[]` | 每次 run 末尾重写 |
| `ultimate_<kind>_model.{json,pkl,pt}` + `_config.json` | `_save_ultimate_model` (`:434-473`) | 预测/复现 | lr: 权重/标准误/t/p/use_scaler; xgb: pickle; torch: `{state_dict,config}` | run 级 |
| `赛道二_results.csv` | `_write_track2_from_preds` (`:892-928`) | 交付物核对 (`backend_runner.py:287`) | 7 列 (见 §15.6) | 每次 run 末尾重写 |
| `results/<batch>/<run_name>/<model>_info.txt` + `_metrics.json` | `workflows/training/train.py` | `data_digging.parse_folder_info` → resume | `model/environment/combination/split_type/cell_line/random_seed/sequence_kernel/...` | 实验级 |
| `workflow_config.json` | **无生成者** | 前端文案引用 (`WorkspaceView.tsx:104,106`)、`project_manifest.config_versions` 占位键 (`project.py:64`)、docs §6 | — | **未实现** (见 §23) |
| `pipeline_config.json` | **无生成者** | 向导 Step 7 说明文本 (`main_wizard.py:408`) | — | **未实现** |
| `logs/workspace/backend.log` / `logs/workspace/frontend.log` | `app/scripts/run_workspace.sh` | 人工 | 服务端 stdout | 每次启动覆盖 |

---

# 21. 跨模块接口

| # | 链路 | 输入 | 输出/格式 | 调用者 | 被调用者 |
|---|---|---|---|---|---|
| 1 | QC → Wizard/Frontend | 用户给定 CSV/TSV/目录 `input_paths` | `session_manifest.json`(status) + `qc_summary.json` + `quality_report.md` + `figures/*.png` | `StandaloneQcView` / `WorkspaceView` → `POST /api/qc/sessions` | `qc_service.QCSessionManager` → 子进程 `analysis/data_QC.py --data <f> --output-dir <session>` |
| 2 | QC → Project (指纹) | `session_id` + 可选 `current_paths` | `project_manifest.json` (含复用指纹, `dataset.fingerprint.reused_from_qc`) | `StandaloneQcView` 按钮 → `POST /api/projects/from-qc` | `project.create_from_qc` → `fingerprint.fingerprint_dataset` (不一致则 `ValueError`) |
| 3 | Wizard → Training | `form_data` 勾选 (细胞系/表观/模型/划分) | 7 步流水线: 特征工程 → `workflows/training/data_digging.py` CLI → (可选) `workflows/prediction/predict.py` CLI → analyse 4 脚本 → plots → 交付物核对 | `main_wizard._run_backend_task` | `app/desktop/backend_runner.execute_full_pipeline` → `subprocess.run` |
| 4 | Training → Analyse | `results/<batch>/<run_dir>/{<model>_info.txt,<model>_metrics.json,...}` | `results/<batch>/summary/{metrics_tables/*.csv, feature_importance/*, anomaly_report.md, plots/*}` | `backend_runner` Step 3-6; 或 `AnalysisPanel` 指定 batch 路径 | `analysis/collect_results.py`, `anomaly_treatment.py`, `importance_extraction.py`, `visualization.generate_all_visualizations` |
| 5 | Workflow → Analyse | `batch_dir` + `selected_tasks[]` (+ `project_id`/`output_dir`) | `analysis_plan.json` → `analysis_status.json`/`execution_log.json` + `tables/summary/figures` | `POST /api/analysis/run` | `analysis.build_plan_dict` → 子进程 `python -m analysis.pipeline --batch-dir --output --analysis-plan` |
| 6 | Analyse → Reports | `output_dir` | `{entries:[{name,path,kind}]}`; md 文本经 resolver | `ReportsPanel` (`analysisApiOutputs.list`) → `MarkdownViewer` → `GET /api/artifacts` / `/api/artifact-raw` | `analysis.list_outputs`, `artifacts.resolve_artifact` |
| 7 | Workflow → Runtime | `TrainingConfig` dict (`POST /api/training/submit`) | `training_status.json` + `run.log` + `done.rc` | `server` 路由 14 → `training.submit` → `adapter_for(runtime)` | `LocalRuntime` / `HpcRuntime` |
| 8 | Runtime → Workflow → Frontend | run_id | `training_status.json` 全员字段 (status/progress/log_path/command/…) | `TrainingPanel`/`RunsHistory` 1.5s 轮询 `GET /api/runs/{id}`、`/log` | `training.status/list_runs` + 日志解析 |
| 9 | Frontend → Workflow | `fetch` JSON (`api/client.ts` 唯一出口, `VITE_API_BASE` 或 vite 代理) | JSON (`Access-Control-Allow-Origin: *`) | 全部组件 | `server.Handler._dispatch` (26 路由) |
| 10 | Predict → 交付物 | mixed npy + `feature_schema.json` + `--target-input` | `summary/ultimate/progress.json`、`preds_<kind>.npy`、`ultimate_*`、`ultimate_summary.json`、`赛道二_results.csv` | `predict.main` / `TrainingConfig(kind="predict")` | `run_ultimate_with_resume` |
| 11 | Grid → workflows/training/train.py | `Experiment` 元组 | `results/<batch>/<run_name>/…` + `logs/` + `models/` | `data_digging.main` | `workflows/training/train.py` (子进程或 in-process) |

---

# 22. 运行入口清单

| 入口 | 命令 | 关键事实 |
|---|---|---|
| Full workflow GUI (本地 Web) | `bash app/scripts/run_workspace.sh` | 后端 `PYTHONPATH=<repo>/backend python3 -m crispr_workspace.server --port 8765 --root $WS_ROOT` (日志 `logs/workspace/backend.log`); 前端 `npm run dev -- --port 5173` (node_modules 缺失时自动 `npm install`); 打开 `http://127.0.0.1:5173` (`run_workspace.sh:1-27`) |
| 后端单独启动 | `PYTHONPATH=backend python3 -m crispr_workspace.server --port 8765 [--root DIR]` | 默认 root `<repo>/workspace`; 可用 `CRISPR_WORKSPACE_ROOT` (`app/backend/README.md:8-14`, `server.py:270-279`) |
| 前端构建/类型检查 | `cd frontend && npm run build` / `npm run typecheck` | `tsc --noEmit -p tsconfig.json && vite build` (`package.json:8-10`); `app/frontend/dist` 当前不存在 |
| 前端测试 | `cd frontend && npm test` | `vitest run`, 4 文件 7 用例 |
| Standalone QC | GUI 首页 "Dataset Quality Check" → 填路径 → Run QC | 轮询 1.2s; 可一键 "Create Project using this dataset" |
| 桌面 7 步向导 (无代码) | `python app/desktop/main_wizard.py` | 默认输出根 `<repo>/Project_Output`; 后台线程调 `execute_full_pipeline` (`README.md:121`, `main_wizard.py:534-536`) |
| 特征工程 | `python core/features/engineering/feature_engineering.py` (**README 写的 `python feature_engineering.py` 不存在**) | 生成 `(N,23,8)` 与 `feature_schema.json` |
| grid training | `python workflows/training/data_digging.py --batch-name <b> --models ... --cell-lines ... --split-types single all mixed [--training-scope-epis ... \| --environments ...] [--in-process] [--workers N] [--dry-run]` | 源: `README.md:140`, `HPC_EXPERIMENT_PROTOCOL.md:43-56`; 并发语义见 §15.8 |
| Ultimate predict (含断点续跑) | `python workflows/prediction/predict.py --batch-name <b> --data-dir data/processed --results-dir results --models linear xgboost mlp transformer cnn --cell-lines ... --target-input <csv> --target-epigenetics CTCF Dnase H3K4me3 RRBS` | 中断后重跑同一命令 → 只补缺完成标记的模型 (`workflows/prediction/predict.py:819-820,845-849`) |
| analyse | `python analysis/collect_results.py --batch-dir results/<b> --split-types single all mixed`; `analysis/anomaly_treatment.py --batch-dir …`; `analysis/importance_extraction.py --batch_dir …`(下划线); `analysis/visualization.py --batch-dir …`(连字符) | 参数风格不统一, 见 §23 |
| collect / importance / 可视化 (README 步骤 2/3/5) | `README.md:145,150,164` | README 使用的 `--batch-name`(importance) 与 `--batch_dir`(visualization) 与脚本定义的参数名不符 |
| Workflow Analyse 子进程 | `python -m analysis.pipeline --batch-dir <b> --output <out> --analysis-plan <plan.json>` | `analysis.py:202-204` |
| 数据 QC 引擎 (headless) | `python analysis/data_QC.py --data <csv|dir> --output-dir <dir> [--print-markdown]` | `data_QC.py:1717-1721` |
| tests (后端) | `cd backend && PYTHONPATH=. python3 -m unittest tests.test_workspace -v` (README); 全套 = `app/backend/tests/{test_workspace,test_workflow_interfaces,test_e2e_smoke,test_project_recovery,test_no_training_dependency}.py` | 实测 19 个 `def test_`; E2E smoke 含真实 QC + analyse.pipeline(合成小批次) + artifact 读取; 训练仅 dry-run |
| 打包上传 | `bash deploy/hpc/build_upload.sh [out.tar.gz]` | 排除 `_no_upload/__pycache__/*.pyc/.npm_tmp/app/frontend/node_modules/app/frontend/dist/.venv/.git` (`build_upload.sh:7-15`) |
| HPC 全量 | 见 `HPC_EXPERIMENT_PROTOCOL.md` §2 (8×`CUDA_VISIBLE_DEVICES=$i nohup python workflows/training/data_digging.py … --in-process`) | 引用的 `HPC_launch_full_batch.sh` 不在仓库 |

---

# 23. 与文档/注释不一致或未实现项

| # | 位置 | 文档/注释说法 | 代码事实 | 判定 |
|---|---|---|---|---|
| 1 | `workflows/training/data_digging.py:404-405` vs `:146-162` | 暴露 `--mixed-seeds` / `--cnn-kernels` 参数 | `main()` 调 `generate_experiments` 时**未传**这两项, 函数内部直接用模块常量 `MIXED_SEEDS`/`CNN_KERNELS` → 两个 CLI 参数完全无效 | **Unused / 参数失效** |
| 2 | `workflows/prediction/predict.py:752-753` | `--generate-candidates` "(兼容旧参数, 已无意义)" | 除 `add_argument` 外全仓库无引用 | **Unused** (代码自认) |
| 3 | `workflows/prediction/predict.py:476-559 / 651-716` | — | `train_ultimate_models`、`generate_track2_results_ultimate` 无调用点; `main()` 走 `run_ultimate_with_resume` | **Legacy** |
| 4 | `qc_service.py:120` 注释"单文件或已 staging 的目录" | 多文件输入应整体送检 | `cmd += ["--data", inputs[0]]`, 多文件时只传 `inputs_src/` 下的**第一个**文件 | **行为与注释不符 (Uncertain 是否为缺陷)** |
| 5 | `WorkspaceView.tsx:104-106`, `docs/frontend_architecture.md:61`, `project.py:64` | 决策写入 `workflow_config.json` | 仓库无任何生成者; 仅 manifest 的 `config_versions.workflow_config` 为 `null` 占位与前端文案 | **未实现** |
| 6 | `main_wizard.py:408` | 输出根含 `pipeline_config.json` | 全仓库无该文件的写入代码 | **未实现** |
| 7 | `docs/acceptance_record.md:23` "19 API 路由" | 19 | 19 恰等于 `if path == "..."` 精确匹配分支数 (`server.py`); 加上 5 条 `path.startswith(...)` 动态段分支 (projects/{id}、qc/sessions/{id}、runs/{id}、runs/{id}/log、projects/{id}/stage) 与 2 条 `path.endswith("/cancel"\|"/resume")` 分支后, **可调用路由 = 26** (§17.9) | **文档口径偏低 (仅计精确路径)** |
| 8 | `HPC_EXPERIMENT_PROTOCOL.md:42,17` 引用 `HPC_launch_full_batch.sh`; `HPC_ENVIRONMENT.md:137-138` 引用 `profile_experiment.py`、`regression_compare.py`; 两文档 §8 引用 `environment.yml`/`requirements-hpc.txt` | 均**不存在于仓库** | **文档引用缺失文件** |
| 9 | `README.md:145,150,164` | Step 2 `collect_results.py --batch-name`(存在, ✓); Step 3 `importance_extraction.py --batch-name`; Step 5 `visualization.py --batch_dir` | `importance_extraction.py:879-883` 定义 `--results_dir/--batch_name/--batch_dir`(**下划线**); `visualization.py:935-938` 定义 `--results-dir/--batch-name/--batch-dir/--output-dir`(**连字符**) → 两处示例参数名都会导致 argparse 报错 | **文档/代码不一致** |
| 10 | `README.md:135` Step 0 `python feature_engineering.py` | 根目录无此文件, 实际为 `core/features/engineering/feature_engineering.py` | **文档路径过期** |
| 11 | `README.md:174` 方式 3 引用 `notebooks/01_pipeline_demo.ipynb` | 仓库无 `notebooks/` 目录 | **文档引用缺失产物** |
| 12 | `app/backend/README.md:17` | 接口见 `docs/frontend_architecture.md` §4 接口表 | 实际接口表在 §3 | **交叉引用错位 (轻微)** |
| 13 | `docs/frontend_architecture.md:77` "前端 vitest 4 项" | 4 项 | 实际 4 文件 **7** 用例 (acceptance_record 已更正为 7) | **文档不一致 (architecture 文档未更新)** |
| 14 | `types.ts:64` `total_rows` | 前端类型声明 CSV 载荷含 `total_rows` | 后端 `_csv_payload` 返回 `data_rows`, 无 `total_rows`; 该字段无任何读取方 | **未使用字段** |
| 15 | `app/frontend/src/api/qc.ts:9-13` `reuseCheck`, `api/artifacts.ts:24-30` `asCsv`, `api/analysis.ts:30-31` `plan` | 客户端方法已定义 | 组件层零调用 (`grep` 验证) → 对应后端路由 11/21 无前端消费者; `asCsv` 亦无用 | **Unused** |
| 16 | `server.py:147-152` | 路由意图为 `/api/runs/{id}/cancel|resume` | 判定仅用 `path.endswith("/cancel"|"/resume")`, 未校验 `/api/runs/` 前缀 (任意 `POST .../cancel` 都会命中) | **路由宽松 (Uncertain 是否预期)** |
| 17 | `server.py:22-30` `_body` | JSON 缺字段期望 400 | 解析失败返回 `{"_raw":...}`; `b["session_id"]`/`b["stage"]` 等缺键 → `KeyError` → 500 而非 400 | **错误码不一致** |
| 18 | `HpcRuntime.status` (`training.py:415-417`) | 完成判定同 Local | 只要 `done.rc` 存在即 `"completed"`, **不读返回码** (Local 会读 rc 区分 failed) | **两 runtime 语义不一致** |
| 19 | `TrainingConfig.train_ratio/valid_ratio/test_ratio` | 字段存在且有默认 0.70/0.15/0.15 | `_dig_command` 未追加 `--train-ratio/--valid-ratio/--test-ratio` → 前端改这些值不生效 | **字段未接线** |
| 20 | `TrainingConfig.mixed_seeds/cnn_kernels` | 字段存在并被 `/api/training/defaults` 下发为 `allowed.mixed_seeds/cnn_kernels` | 无 CLI 映射 (§17.6) → 前端无法真正改变 seed/卷积核集合 | **字段未接线** |
| 21 | `app/frontend/src/views/StandaloneQcView.tsx:4` | import `ArtifactViewer` | 该视图未渲染 `ArtifactViewer` (仅 QcDashboard) | **未使用 import** |
| 22 | Notebook 门禁文档 (`docs/frontend_architecture.md:69`) | 每格依赖未满足显示 Waiting | 只有 analysis 阶段会被写回 (`updateStage` 唯一调用点); `qc/training/mapping/reports` 无任何生产者 → Mapping/Reports 门禁不会自动解除 | **部分实现** |
| 23 | `analysis.py:174-178` | 仅对有 `enabled` 的容器 (environment/sequence/cell_line) 设置 `enabled` | 与 `analysis/plans.py:54-65` (StatisticsPlan/EvidencePlan 确无 `enabled`) 一致; `task()` 对 statistics/evidence 直接读子字段 (`plans.py:186-192`) | **一致 (易误改点, 已在注释标注)** |
| 24 | `app/scripts/run_workspace.sh` | 前端 `npm run dev` | `app/frontend/dist` 不存在, 且 `server.py` **不提供静态文件服务** → 无 dev server 时 Web GUI 不可用 (与 DSH `dsh web` GUI 无关, 属另一服务) | **部署事实** |
| 25 | `analysis/registry.py:52-76` | 15 条内置任务注册; runner 全为 `None` | `analysis.registry_tasks()` 回退表含 16 条 (额外 `fdr_correction`), 仅当 `import analyse.registry` 失败时才使用 → 正常路径任务数 = 15 | **回退表与注册表条目数不一致** |

---

## 本节自检

- **predict resume**: 覆盖 `PROGRESS_FILE`/`_load_progress`/`_save_progress`/`_kind_done`/`preds_<kind>.npy` 原子写/`run_ultimate_with_resume` 跳过逻辑, 并明确"不扫描 results/batch 目录"(`workflows/prediction/predict.py:819-820, 845-849, 873-877, 931-1003`, §15.5) ✅
- **data_digging resume**: 覆盖 `parse_folder_info`/`build_completed_lookup`/`classify_experiments` 的 key 规则与 `*info*.txt`+`*metrics*.json` 扫描依据 (`workflows/training/data_digging.py:183-247`, §15.8) ✅
- **wizard steps**: 7 步逐条给出标题、form_data 键、控件联动与校验 (`app/desktop/main_wizard.py:109-427`, §16.2–16.4) ✅
- **backend routes count**: 26 条 (method+path) 全表, 含请求/响应/作用/行号, 另记 `do_OPTIONS` (§17.9) ✅
- **TrainingConfig→CLI mapping**: 逐字段映射表, 并标出 4 项未接线 (`train_ratio*`, `mixed_seeds`, `cnn_kernels`, `cuda_visible` 走环境变量) (§17.6, §23 #19/#20) ✅
- **HPC adapter boundaries**: 生成 launcher/状态回写/进度解析 vs 不实现 Slurm/sbatch/scancel/8 卡分片/job 轮询; 附文档中的真实 8-slice + `CUDA_VISIBLE_DEVICES` + `nohup` + `--in-process` + 续跑协议与缺失脚本 (§19.4, §23 #8) ✅
- **frontend tree**: 页面树+组件树+逐组件职责/API 表+Artifact Viewer 行为+Notebook 门禁+vitest 4 文件 7 用例 (§18.1–18.5) ✅
- **state files**: 25 行状态/配置文件表 (生成者/读取者/关键字段/生命周期), 含 2 项未实现文件与 1 项占位键 (§20) ✅
- **entry points**: 18 类入口 (GUI/Standalone QC/grid/predict+续跑/analyse×4/importance/collect/tests/HPC/打包等) 及命令 (§22) ✅
- **doc/code discrepancies**: 25 条, 逐条给出"文档说法 | 代码事实 | 判定" (§23) ✅


---

# 24. 模块调用关系（import 依赖 vs 运行顺序）

## 24.1 运行顺序主链（call chain，实测）
```text
app/desktop/main_wizard.py (GUI)
  └── app/desktop/backend_runner.py::execute_full_pipeline(form_data, root_output_dir)
        ├── run_feature_engineering_step()
        │     └── convert_raw_csv_to_npy()  或 复制基准 npy
        ├── workflows/training/data_digging.py  (subprocess)
        │     └── workflows/training/train.py::main()  (subprocess 或 --in-process 时 import train 后调用 main)
        │           ├── src/input_control/cell_line_division.divide_data()
        │           ├── src/input_control/cell_environment_combination.prepare_train_valid_test()
        │           └── <model module>.train(...)      # 由 MODEL_MODULES 动态 import
        ├── workflows/prediction/predict.py  (仅 has_target; subprocess)
        │     └── run_ultimate_with_resume()
        │           ├── _run_ultimate_cv()/_fit_model()/_predict_model()
        │           └── _write_track2_from_preds()
        ├── analysis/collect_results.py (subprocess)  → summary/metrics_tables/
        ├── analysis/anomaly_treatment.py (subprocess) → summary/anomaly_report.md
        ├── analysis/importance_extraction.py (subprocess) → summary/feature_importance/
        └── analysis/visualization.py::generate_all_visualizations()  (经包兼容桥 import)
              → summary/plots/

analysis/pipeline.py::run_analysis()
  ├── analysis/data/loaders.load_experiment_table()
  ├── analysis/data/validation.validate_metric_consistency()
  ├── analysis/environment/incremental_effect.*
  ├── analysis/attribution/extractors.extract_attribution_table()
  ├── analysis/cellline/consistency.*
  ├── analysis/evidence/integration.environment_evidence_matrix()
  ├── analysis/reports/markdown_report.build_*()
  └── analysis/visualization.render_all()

Scientific Workspace:
frontend (React) ──HTTP──> app/backend/crispr_workspace/server.py::Handler
   ├── project.*        (manifest/CRUD/from-qc/stage)
   ├── qc_service.QCSessionManager ──subprocess──> analysis/data_QC.py
   ├── training.TrainingConfig.build_command() ──> workflows/training/data_digging.py / workflows/prediction/predict.py
   │     └── LocalRuntime/HpcRuntime (training_status.json)
   ├── analysis.registry_tasks/build_plan_dict/run ──subprocess──> python -m analysis.pipeline
   └── artifacts.resolve_artifact()（白名单 + CSV 分页）
```

## 24.2 import 依赖（静态，节选）
```text
analysis/pipeline.py imports:
  analyse.{config, plans, prediction}
  analyse.data.{loaders, validation}
  analyse.environment.incremental_effect
  analyse.attribution.{extractors, summary}
  analyse.cellline.consistency
  analyse.evidence.integration
  analyse.reports.markdown_report
  analyse.visualization                     （包；__init__.py 内含 render_all 与旧模块桥）
app/backend/crispr_workspace/server.py imports:
  .{analysis, artifacts, config, project, qc_service, store, training}
app/backend/crispr_workspace/analysis.py:
  运行期 try-import `analyse.registry`（仅取任务目录；科学计算仍走子进程）
src/* 模型模块:
  各自 import `src.xai_importance`（白名单列/导出）
workflows/training/train.py:
  用 importlib 按 MODEL_MODULES 字符串动态 import 模型模块（因此静态 import 图上出现“无入度”的模块，如 core/models/xgboost/xgboost.py）
```
> **重要区分**：`backend_runner.py` 通过**子进程字符串路径**调用 `workflows/training/data_digging.py/predict.py/collect_results.py/anomaly_treatment.py/importance_extraction.py`，
> 因此这些模块在静态 import 图中“入度=0”，但它们都是 Active（有真实运行调用）。
> 同理 `analysis/visualization.py` 通过包 `__getattr__` 的 importlib 桥被调用。

## 24.3 静态“无项目内 import”但 Active 的模块（实测）
`app/desktop/main_wizard.py`、`app/desktop/backend_runner.py`、`workflows/prediction/predict.py`、`workflows/training/data_digging.py`、`workflows/training/train.py`、`scripts/make_notebook.py`、
`core/features/engineering/feature_engineering.py`、`core/models/xgboost/xgboost.py`（动态 import）、
`analysis/{data_QC,collect_results,importance_extraction,anomaly_treatment,visualization}.py`（子进程/桥）、
`app/backend/crispr_workspace/*`（由 server/CLI 启动）。

---

# 25. 历史代码 / 残留代码 / 未实现项

## 25.1 文件级状态（依据引用实测；完整 77 行见附录 A）
| 文件 | 状态 | 判定依据 |
|---|---|---|
| `workflows/training/train.py`, `workflows/prediction/predict.py`, `workflows/training/data_digging.py`, `core/features/engineering/feature_engineering.py` | Active（入口） | CLI 入口，被文档/GUI/Workflow 调用 |
| `src/{linear_regression,xgboost,mlp,cnn,transformer}/*.py`, `core/xai/importance/xai_importance.py`, `src/input_control/*.py` | Active（训练系统） | 被 workflows/training/train.py/各模型引用 |
| `analysis/{data_QC,collect_results,importance_extraction,anomaly_treatment,visualization}.py` | Active（训练侧独立脚本） | 被 `app/desktop/backend_runner.py` 以子进程/桥调用；`HPC_EXPERIMENT_PROTOCOL.md` 亦引用 |
| `analysis/` 新引擎（pipeline/config/schemas/plans/registry/data/stats/environment/attribution/cellline/evidence/reports/visualization 包） | Active（分析引擎） | 被 pipeline/backend.analysis/tests 引用 |
| `app/backend/crispr_workspace/*` | Active（Workflow 后端） | 被 server/CLI/前端/测试引用 |
| `app/frontend/src/**` | Active（前端） | vite 构建入口 `main.tsx` → `App.tsx` |
| `analysis/visualize_results.py` | **工作区已删除** | `ls` 不存在；git status 标 `D` |
| `notebooks/`（目录） | **不存在**（由 `scripts/make_notebook.py` 生成） | `ls notebooks` 失败 |
| `scripts/make_notebook.py` | Active（Utility） | 生成 demo notebook 的独立脚本 |

## 25.2 函数级残留（示例）
- `workflows/prediction/predict.py::train_ultimate_models` / `generate_track2_results_ultimate`：**Unused**（`main()` 已改用 `run_ultimate_with_resume`；grep 确认无调用）。
- `analysis/stats/hypothesis_tests.py::anova_interface`：**Planned/Placeholder**（返回 `available=False`）。
- `analysis/analysis.py`（engine）任务 `motif_discovery`：**Planned**；`bootstrap/hypothesis_testing/fdr_correction`：runner 未挂载（`unavailable`）。
- `analysis/registry.py` 中登记但未实现的任务：以 pipeline 运行时的 status/reason 为准（不伪造）。

## 25.3 重复实现风险（跨文件同名函数，AST 实测）
| 重复功能 | 出现位置 | 风险 |
|---|---|---|
| `calculate_metrics`, `create_logger`, `save_predictions`, `save_results`, `train`, `predict`, `set_seed`, `save_model`, `evaluate_model` | 5 个模型模块各自实现 | 修改指标/日志格式需同步 5 处 |
| `build_command` | `workflows/training/data_digging.py` vs `app/backend/crispr_workspace/training.py` | 两套 CLI 拼装（前者直连 workflows/training/train.py，后者编排 data_digging/predict） |
| `parse_info_txt` / `parse_info_file` | `collect_results.py` / `importance_extraction.py` / `visualization.py` | 三份 info.txt 解析 |
| `load_metrics_table` | `anomaly_treatment.py` / `visualization.py` | 两份指标表读取 |
| `normalize_cell_line` | `anomaly_treatment.py` / `importance_extraction.py` | 细胞系名规范化重复 |
| `generate_default_feature_names` | `linear_regression.py` / `xgboost.py` | 默认特征名生成重复 |
| `load_feature_schema` | `cell_environment_combination.py` / `cell_line_division.py` | schema 读取/兜底重复 |
| `combo_name` | `environment/incremental_effect.py` / `visualization.py` | 环境组合名生成重复 |
| `_fmt` | `anomaly_treatment.py` / `reports/markdown_report.py` | 表格格式化重复 |
> 本次任务**不修改**以上任何代码，仅记录。

---

# 26. 当前项目完整执行流程总结（一页版）

1. **数据进入**：原始 CSV（每细胞系）经 GUI 选择或 CLI 指定；`feature_engineering.py` 读取并去重。
2. **特征工程**：逐行编码为 `(N,23,8)`（A/C/G/T 四通道 One-Hot + 4 表观通道），并写出 2D/3D npy/csv、metadata 与 `feature_schema.json`。
3. **QC（只读）**：`analysis/data_QC.py` 体检（长度/歧义碱基/缺失/GC/离群），产出 `qc_summary.json`、`quality_report.md`、图；不修改数据；决策由 Wizard/Workflow 记录配置。
4. **训练配置**：GUI Step5/Workflow `TrainingConfig`（models/cells/splits/environments/超参/runtime）。
5. **网格实验**：`workflows/training/data_digging.py` 生成实验清单（single/all/mixed × 环境组合 × 模型 × CNN 核），逐实验调用 `workflows/training/train.py`；支持断点续跑与 8 卡并行。
6. **单实验训练**：`workflows/training/train.py` 划分数据（single/all/mixed）→ 环境组合掩码 → 模型训练/早停/测试 → 指标与 XAI 落盘。
7. **XAI**：linear 系数+统计检验、XGB Gain/Weight/Cover/TreeSHAP、MLP IG、CNN IG/ISM、Transformer Attention/熵，并计算 SNR；白名单列由 `core/xai/importance/xai_importance.py` 定义。
8. **结果收集**：`collect_results.py` 扫描实验目录 → `metrics_tables/all_experiments.csv` 等；`importance_extraction.py` 汇总重要性报告与特征库。
9. **结果级 QC**：`anomaly_treatment.py` 两级异常检测报告；`analysis/data/validation.py` 同 cohort 指标一致性标记。
10. **分析引擎**：`analyse.pipeline` 统一表 → 预测/环境/序列/细胞系/证据/假设 → tables+summary+figures。
11. **Workflow/前端**：本地 API 编排上述引擎（只读产物+子进程），提供 Project/Notebook/Artifact Viewer/Standalone QC。
12. **HPC**：`CUDA_VISIBLE_DEVICES` + 每卡一个 `workflows/training/data_digging.py` 进程 + `--in-process`，共享 batch 断点续跑；`workflows/prediction/predict.py` 支持模型级续跑。

---

# 27. 与论文方法部分对应的技术模块

| 论文方法小节 | 对应实现（代码位置） | 可写的关键事实 |
|---|---|---|
| 数据与预处理 | `core/features/engineering/feature_engineering.py`, `src/input_control/*` | 23nt；4 碱基 One-Hot；4 表观通道；去重；schema 化 |
| 数据体检/质控 | `analysis/data_QC.py` | 只读检测；`qc_summary.json` 字段；离群 IsolationForest；阈值集中 |
| 数据划分 | `src/input_control/cell_line_division.divide_data` | train/valid/test=0.70/0.15/0.15；seed=42；mixed 42–45；all=留一细胞系 |
| 模型阵列 | `src/{linear_regression,xgboost,mlp,cnn,transformer}` | 各模型超参与架构（见 §7） |
| 训练协议 | `workflows/training/train.py`, `workflows/training/data_digging.py` | 实验网格；早停 patience/min_delta；checkpoint；日志 |
| 可解释性 | `core/xai/importance/xai_importance.py` + 各模型 XAI 函数 | 方法清单、SNR 定义、白名单列 |
| 实验规模与复现 | `workflows/training/data_digging.py`, `HPC_EXPERIMENT_PROTOCOL.md` | 1344 实验构成；8×A100 分片；`--in-process` |
| 统计与证据 | `analysis/` 引擎（config/stats/environment/evidence） | 配对基线原则、FDR family、Bootstrap、Evidence Tier、不稳定隔离 |
| 结果与报告 | `analysis/reports`, `analysis/visualization`, `frontend` | summary 00–08、figures、Artifact Viewer |

---

## 1.5 关键实现事实（极易误解，写论文/复现时必须按此）
1. **环境组合 = 通道零掩码，不是降维/列选择**：
   `cell_environment_combination.apply_environment_combination()` 先由 `create_channel_mask()` 生成
   长度 = `schema.channel_count` 的 0/1 掩码（sequence 通道恒为 1），再对 `(N,23,C)` 张量做**逐元素相乘**
   （`X_3d.copy() * mask`）。因此：
   - 3D 模型输入始终为 `(N,23,C)`，未选中的表观通道被置 0（不是删除列）；
   - 2D 模型输入始终为 `flatten_features()` 后的 `(N,23*C)`（当前 = `(N,184)`），维度不随组合变化。
2. **`all` 划分的 train/valid 比例与 CLI 默认不同**：当 `split_type="all"` 且指定了 `cell_line`（留一细胞系）时，
   `split_all_cell_lines()` 对其余细胞系合并数据使用**硬编码 `train=0.85 / valid=0.15`**（`test_fraction=0.0`），
   测试集 = 整个留出细胞系。CLI 的 `--train-ratio/--valid-ratio/--test-ratio`（默认 0.70/0.15/0.15）在该分支**不生效**。
3. **`single` / `mixed` 比例**：使用 `create_split_indices()` 的 `floor(N*ratio)` 取整，test = 余数；
   随机划分用 `np.random.default_rng(seed).shuffle()`。默认 0.70/0.15/0.15、seed=42。
4. **网格里的 seed**：`data_digging.generate_experiments()` 中 `single`/`all` 使用 workflows/training/train.py 默认 seed（42）；
   `mixed` 使用 `MIXED_SEEDS = [42, 43, 44, 45]` 四次重复（`workflows/training/train.py::build_command` 对 mixed 传对应 seed）。
5. **标准化开关默认关闭**：`--use-scaler`（workflows/training/train.py / data_digging 默认 False）；
   scaler 的具体拟合位置见 §7（各模型训练函数内部，仅当开关开启）。
6. **列名/维度**：当前 schema `channel_names = [A, C, G, T, CTCF, Dnase, H3K4me3, RRBS]`，
   `feature_count = 184`，列名 `pos{p}_{channel}`；`create_channel_mask` 的 docstring 示例仍是旧 7 通道
   （`[1,1,1,0,0,0,0]`），与当前 8 通道 schema 不一致（属注释过期，代码以 schema 为准）。
7. **⚠️ 关键缺陷：网格中的 `all` 划分实际退化为 `single`（已硬证据确认）**
   证据链（全部实测）：
   - `workflows/training/data_digging.py::build_command` 只传 `--cell-line <cl>`，不传 `--cell-lines`；
   - `workflows/training/train.py:663-664`：`if cell_line and not cell_lines: cell_lines = [cell_line]`；
   - `core/data/splitting/cell_line_division.py::divide_data` 把 `cell_lines` 过滤为可用集合（此处只有 1 个）；
   - `split_all_cell_lines`（`:214-217`）中 `len(datasets)==1 or len(cell_lines)<=1` → **退化保护**
     直接调用 `split_single_cell_line()`（同比例、同 seed）。
   后果：对同一 (model, environment, cell_line)，`all_*_heldout_<cl>` 与 `single_<cl>_*` 使用**完全相同**的
   数据划分与随机种子。实测 `results/batches/batch_20260909_full/` 中 **8/8** 组 (mlp/xgboost/transformer/cnn ×
   hct116/hela) 的 `*_metrics.json` 六个指标（MSE/RMSE/MAE/R2/Pearson/Spearman）**逐位相同**
   （例如 linear hct116：R2=0.090741899561539 两者一致）。
   另：真正的 LOCO 分支（多细胞系 + `test_cell_line`）调用
   `create_split_indices(train=0.85, validation=0.15, test=0.0)`，而 `validate_split_fractions`
   （`:89-95`）要求每个比例 `> 0` → 该分支**会抛 `ValueError`，当前不可达**。
   → 结论：当前 1344 网格并未提供真正的“留一细胞系/跨细胞系泛化”实验；`all` 与 `single` 为重复实验。
   写论文/复现时必须按此事实描述（或先修训练侧再重跑，属训练系统改动，需另行授权与回归）。

# 附：文档自检（本主文档部分）
- [x] 代码基线（commit/branch/status）
- [x] 三个入口与 Step1–7 执行顺序（实测）
- [x] 分析引擎 8 段顺序与 unavailable 语义
- [x] 条件分支/并行/续跑机制（data_digging 与 predict 两种判据）
- [x] 数据流与关键 shape（23/8/184）与负责程序
- [x] import 依赖 vs 运行顺序（含“入度 0 但 Active”的解释）
- [x] 残留/未实现/重复实现清单（含函数级）
- [x] 论文方法映射


---

# 附录（自动生成索引）

> 由 AST 扫描当前代码库生成 (READ-ONLY)。函数条目格式：`行号 名称(参数) — 文档首行`。

## 附录 A：程序索引（按目录）

| 程序 (path) | 行数 | 状态 | 职责 | 函数/方法数 |
|---|---:|---|---|---:|
| `workflows/training/data_digging.py` | 518 | Active (入口) | 已测数据 Training Scope 网格实验引擎 | 15 |
| `scripts/make_notebook.py` | 320 | Active (入口) | 生成 notebooks/01_pipeline_demo.ipynb 的脚本 | 0 |
| `workflows/prediction/predict.py` | 1008 | Active (入口) | mixed 十折 CV + 目标集预测 (Ultimate, 含断点续跑) | 29 |
| `workflows/training/train.py` | 734 | Active (入口) | 单次实验训练与评估入口 (dispatching 五模型) | 20 |
| `app/desktop/backend_runner.py` | 306 | Active | 向导后端全流程调度 (Step1–7) | 4 |
| `app/desktop/main_wizard.py` | 536 | Active (入口) | 7 步 Tkinter 引导向导 | 13 |
| `analysis/__init__.py` | 16 | Active (分析引擎) | analyse — CRISPR 编辑效率影响因素发现与证据整合分析引擎。 | 0 |
| `analysis/anomaly_treatment.py` | 489 | Active (训练侧独立脚本, 由 app/desktop/backend_runner.py 以子进程调用) | 两级异常检测与 anomaly_report.md | 12 |
| `analysis/collect_results.py` | 442 | Active (训练侧独立脚本, 由 app/desktop/backend_runner.py 以子进程调用) | 实验目录扫描 → metrics_tables 汇总 | 20 |
| `analysis/config.py` | 65 | Active (分析引擎) | analyse.config — 集中科学规则配置 (阈值不得散落各模块)。 | 1 |
| `analysis/data_QC.py` | 1768 | Active (训练侧独立脚本, 由 app/desktop/backend_runner.py 以子进程调用) | 数据体检 (只读 QC, qc_summary.json/报告/图) | 36 |
| `analysis/importance_extraction.py` | 908 | Active (训练侧独立脚本, 由 app/desktop/backend_runner.py 以子进程调用) | 各模型重要性白名单 → feature_importance md/CSV + 特征库 | 22 |
| `analysis/pipeline.py` | 345 | Active (分析引擎) | 分析引擎编排入口 (python -m analysis.pipeline) | 4 |
| `analysis/plans.py` | 242 | Active (分析引擎) | analyse.plans — AnalysisPlan / Validator / ExecutionPlan / 状 | 8 |
| `analysis/prediction.py` | 35 | Active (分析引擎) | analyse.prediction — 预测/泛化性能分析 (只读统一表)。 | 2 |
| `analysis/registry.py` | 77 | Active (分析引擎) | analyse.registry — 分析任务注册表 (新增分析 = 注册任务, 不改 GUI/核心流程)。 | 3 |
| `analysis/schemas.py` | 200 | Active (分析引擎) | analyse.schemas — 统一科学记录类型与证据标签。 | 0 |
| `analysis/visualization.py` | 959 | Active (训练侧独立脚本, 由 app/desktop/backend_runner.py 以子进程调用) | V6 显著性热图/环境增量树/表观对比 (旧单文件) | 25 |
| `core/features/engineering/feature_engineering.py` | 2029 | Active (入口) | 原始 CSV → 23×C 特征矩阵/schema/npy | 27 |
| `core/xai/importance/xai_importance.py` | 135 | Active (训练系统) | XAI 特征重要性输出【白名单】与导出清洗 (学术红线) | 2 |
| `analysis/attribution/__init__.py` | 5 | Active (分析引擎) | analyse.attribution — 模型专属 attribution 统一抽取 (线性/树/深度)。 | 0 |
| `analysis/attribution/columns.py` | 61 | Active (分析引擎) | analyse.attribution.columns — 各模型重要性 CSV 列 -> 统一字段 的映射 (adap | 2 |
| `analysis/attribution/extractors.py` | 139 | Active (分析引擎) | analyse.attribution.extractors — 从训练产物抽取统一 attribution 表。 | 3 |
| `analysis/attribution/summary.py` | 50 | Active (分析引擎) | analyse.attribution.summary — 统一 attribution 表 -> 04 sequenc | 2 |
| `analysis/cellline/__init__.py` | 1 | Active (分析引擎) | analyse.cellline — feature × cell-line 效应与一致性。 | 0 |
| `analysis/cellline/consistency.py` | 60 | Active (分析引擎) | analyse.cellline.consistency — cell-line effect 汇总与 context  | 2 |
| `analysis/data/__init__.py` | 1 | Active (分析引擎) | analyse.data — 批量结果只读加载/字段适配/校验 (训练系统只读)。 | 0 |
| `analysis/data/loaders.py` | 173 | Active (分析引擎) | analyse.data.loaders — 从训练产物建立统一实验表 (只读, 不修改原始结果)。 | 8 |
| `analysis/data/validation.py` | 63 | Active (分析引擎) | analyse.data.validation — 结果校验。 | 2 |
| `analysis/environment/__init__.py` | 1 | Active (分析引擎) | analyse.environment — 环境因素效应分析 (条件 ΔR² / 主效应 / 交互占位)。 | 0 |
| `analysis/environment/incremental_effect.py` | 170 | Active (分析引擎) | analyse.environment.incremental_effect — 条件 ΔR² / 主效应 (Paire | 7 |
| `analysis/evidence/__init__.py` | 1 | Active (分析引擎) | analyse.evidence — Evidence Strength/Tier/假设语言规则。 | 0 |
| `analysis/evidence/hypothesis.py` | 74 | Active (分析引擎) | analyse.evidence.hypothesis — 生物假设语言 (受控措辞)。 | 1 |
| `analysis/evidence/integration.py` | 194 | Active (分析引擎) | analyse.evidence.integration — 跨模型/跨 cell-line 证据整合 (纯函数)。 | 8 |
| ~~`analysis/evidence/rules.py`~~ | ~~73~~ | **Deleted 2026-09-13** | 旧 SNR/FDR 证据标签规则；经审计确认未进入生产流水线（仅单测引用），已删除以避免两套 Tier 定义。权威规则见 `analysis/evidence/integration.py::classify_evidence_tier`。 | 0 |
| `analysis/reports/__init__.py` | 1 | Active (分析引擎) | analyse.reports — Markdown/表格 生成 (统一引用统一数据, 不自行扫描)。 | 0 |
| `analysis/reports/markdown_report.py` | 180 | Active (分析引擎) | analyse.reports.markdown_report — summary/*.md 生成 (Phase 2 切 | 10 |
| `analysis/stats/__init__.py` | 2 | Active (分析引擎) | analyse.stats — Effect/CI/检验/FDR/Bootstrap 规范实现 (无副作用纯函数; 名  | 0 |
| `analysis/stats/bootstrap.py` | 107 | Active (分析引擎) | analyse.stats.bootstrap — Bootstrap CI (仅稳定性证据, 非因果/显著)。 | 3 |
| `analysis/stats/effect_size.py` | 32 | Active (分析引擎) | analyse.stats.effect_size — Effect 定义与 paired-baseline 原则。 | 2 |
| `analysis/stats/hypothesis_tests.py` | 76 | Active (分析引擎) | analyse.stats.hypothesis_tests — 归因统计检验接口。 | 2 |
| `analysis/stats/multiple_testing.py` | 35 | Active (分析引擎) | analyse.stats.multiple_testing — BH-FDR (Benjamini-Hochberg) | 1 |
| `analysis/tests/__init__.py` | 0 | Test-only | — | 0 |
| `analysis/tests/test_attribution.py` | 78 | Test-only | analyse.tests.test_attribution — attribution 统一抽取测试。 | 4 |
| `analysis/tests/test_core.py` | 201 | Test-only | analyse.tests — 核心科学函数测试 (unittest, 无 pytest 依赖)。 | 20 |
| `analysis/tests/test_environment.py` | 70 | Test-only | analyse.tests.test_environment — 条件 ΔR² / 主效应 (Paired baseli | 5 |
| `analysis/tests/test_phase5.py` | 63 | Test-only | analyse.tests.test_phase5 — cell-line 一致性 + evidence matrix  | 4 |
| `analysis/tests/test_phase6.py` | 110 | Test-only | analyse.tests.test_phase6 — pipeline 端到端报告/图形产物 (Phase 6)。 | 2 |
| `analysis/visualization/__init__.py` | 84 | Active (分析引擎) | analyse.visualization — 证据引擎图表 (分主题模块; 300dpi PNG)。 | 3 |
| `analysis/visualization/attribution_plots.py` | 38 | Active (分析引擎) | attribution_plots — 位置归因热图 (per method; magnitude)。 | 1 |
| `analysis/visualization/cellline_plots.py` | 41 | Active (分析引擎) | cellline_plots — feature × cell-line 效应与一致性。 | 1 |
| `analysis/visualization/core.py` | 21 | Active (分析引擎) | analyse.visualization.core — 图表样式/保存基元。 | 2 |
| `analysis/visualization/environment_plots.py` | 43 | Active (分析引擎) | environment_plots — 条件 ΔR² 热图 + 主效应。 | 1 |
| `analysis/visualization/evidence_plots.py` | 36 | Active (分析引擎) | evidence_plots — 证据矩阵/层级汇总。 | 1 |
| `analysis/visualization/performance_plots.py` | 35 | Active (分析引擎) | performance_plots — 预测/泛化图。 | 1 |
| `app/backend/crispr_workspace/__init__.py` | 11 | Active (Workflow 后端) | crispr_workspace — CRISPR Scientific Workspace 本地后端 (Workflo | 0 |
| `app/backend/crispr_workspace/analysis.py` | 256 | Active (Workflow 后端) | Analysis / AnalysisPlan 接口。 | 7 |
| `app/backend/crispr_workspace/artifacts.py` | 158 | Active (Workflow 后端) | Artifact Resolver / 预览服务。 | 5 |
| `app/backend/crispr_workspace/config.py` | 48 | Active (Workflow 后端) | 配置与路径策略 (跨平台, 无硬编码实验室路径)。 | 5 |
| `app/backend/crispr_workspace/fingerprint.py` | 61 | Active (Workflow 后端) | 数据指纹: 判断“当前输入 == 上次 QC 的输入”, 防止错误复用旧 QC。 | 3 |
| `app/backend/crispr_workspace/project.py` | 136 | Active (Workflow 后端) | Project Workspace: 创建/列出/打开项目, project_manifest.json 为状态源。 | 10 |
| `app/backend/crispr_workspace/qc_service.py` | 141 | Active (Workflow 后端) | Standalone / Workflow Data QC 会话管理。 | 9 |
| `app/backend/crispr_workspace/server.py` | 279 | Active (入口) | 本地 Workflow API (/api/*) | 9 |
| `app/backend/crispr_workspace/store.py` | 41 | Active (Workflow 后端) | 轻量 JSON 状态存取 (manifest/status 一律落盘, 前端状态从文件恢复)。 | 3 |
| `app/backend/crispr_workspace/training.py` | 494 | Active (Workflow 后端) | Training / Runtime Adapter 接口。 | 29 |
| `app/backend/tests/test_e2e_smoke.py` | 127 | Test-only | 端到端 smoke (无 GPU): QC(真实引擎) → 训练(校验+preflight+dry-run) | 3 |
| `app/backend/tests/test_no_training_dependency.py` | 42 | Test-only | 静态守卫: Workflow 后端绝不 import 训练/引擎科学模块 (红线 P0)。 | 1 |
| `app/backend/tests/test_project_recovery.py` | 54 | Test-only | Project recovery 端到端: 阶段/详情落盘后重开 (新实例) 必须可恢复。 | 2 |
| `app/backend/tests/test_workflow_interfaces.py` | 131 | Test-only | Workflow 接口测试: TrainingConfig/CLI 构建、Preflight、Runtime(dry-r | 12 |
| `app/backend/tests/test_workspace.py` | 157 | Test-only | crispr_workspace 后端单测 (仅标准库 + 可选的 analysis/data_QC 引擎)。 | 11 |
| `core/models/cnn/cnn.py` | 873 | Active (训练系统) | CNN | 13 |
| `core/features/channels/cell_environment_combination.py` | 1908 | Active (训练系统) | Cell Environment Combination | 23 |
| `core/data/splitting/cell_line_division.py` | 334 | Active (训练系统) | Cell Line Division (动态数据发现与零硬编码版) | 15 |
| `core/models/linear/linear_regression.py` | 852 | Active (训练系统) | Linear Regression Model | 14 |
| `core/models/mlp/mlp.py` | 801 | Active (训练系统) | MLP | 14 |
| `core/models/transformer/transformer.py` | 805 | Active (训练系统) | Transformer | 17 |
| `core/models/xgboost/xgboost.py` | 694 | Active (训练系统) | XGBoost | 14 |

## 附录 B：函数清单（按程序）

### workflows/training/data_digging.py  (518 lines, Active)
- `L37` **build_training_scope_combinations(active_epis)** — 由第4步选项2(Training Scope)勾选的表观特征展开为网格环境组合。
- `L63` **_canonicalize_combinations(combos)** — 归一化环境组合: “全部表观特征”的组合统一只保留 `all`。
- `L97` **load_environment_combinations(data_dir)**
- `L121` **sanitize_batch_name(batch_name)**
- `L125` **generate_experiments(environments, selected_models, selected_cells, selected_splits)**
- `L167` **build_run_name(experiment)**
- `L183` **parse_folder_info(folder)**
- `L197` **build_completed_lookup(results_batch_dir)**
- `L232` **classify_experiments(experiments, results_batch_dir)**
- `L250` **build_command(experiment, batch_name, data_dir, model_dir, results_dir, logs_dir, train_ratio, valid_ratio, test_ratio, use_scaler, epochs, batch_size, learning_rate, dropout, weight_decay, patience, min_delta, hidden_dim1, hidden_dim2, conv_channels1, conv_channels2, device)**
- `L324` **run_one_experiment(experiment, index, total, env)**
- `L341` **run_experiment_in_process(experiment, index, total)** — 进程内执行单实验: 复用当前 python 解释器调用 train.main(),
- `L365` **build_worker_env(workers, per_worker_threads)** — 并发执行时的子进程线程环境 (Phase-9 调优接口)。
- `L384` **parse_args()**
- `L436` **main()**

### workflows/prediction/predict.py  (1008 lines, Active)
- `L101` **build_channel_plan(schema, target_epis)** — 按目标实际具备的表观通道从 schema.channel_names 中选取列下标(保序)。
- `L139` **subset_arrays_3d(X3, plan)** — 按 plan 裁剪 (N,23,C) -> (N,23,K) 并展平 (N,23*K)。
- `L145` **detect_sequence_column(df)**
- `L155` **load_target_dataframe(target_input)** — 读入目标待测数据集 (CSV 文件或含 CSV 的目录); 返回 (df, 使用文件路径)。
- `L177` **build_target_features(df, schema, plan)** — 把目标 CSV 编码为与训练一致的 (M,23,K) (通道顺序=plan, 保 schema 序)。
- `L224` **resolve_target_epis_from_file(df, schema)**
- `L240` **_load_mixed_subset(data_dir, schema, plan, cell_lines)**
- `L268` **_expand_ultimate_models(selected_models)**
- `L288` **_build_torch_model(kind, input_dim_2d, input_dim_3d_channels, cfg, device, n_seq_channels)** — 构建 torch 模型 (n_seq_channels 由通道规划给出, 兼容 7ch/8ch 池)。
- `L328` **_fit_torch_model(model, X, y, cfg, device, epochs, seed)**
- `L354` **_drop_lr_reference_columns(X2, feature_names)** — 线性终极模型与 data_digging 网格 LR 一致的参照处理:
- `L365` **_fit_model(kind, cfg, X2, X3, y, tr_idx, device, epochs, seed, n_seq_channels)**
- `L395` **_predict_model(kind, model, X, device)**
- `L409` **_run_ultimate_cv(kind, cfg, X2, X3, y, folds, device, epochs, seed, n_seq_channels)** — 对单个超参配置执行 K 折交叉验证, 返回 (mean_r2, mean_rmse, std_r2)。
- `L426` **_atomic_bytes(path, data)** — 原子写: 先写同目录临时文件再 rename, 保证“文件存在即完整”。
- `L434` **_save_ultimate_model(kind, model, best, feature_names, ultimate_dir)**
- `L476` **train_ultimate_models(X2, X3, y, feature_names, selected_models, ultimate_dir, cv_folds, epochs, device, seed, n_seq_channels)** — 在给定 (已按目标通道裁剪的) mixed 数据上: 逐模型 10 折 CV 选超参 -> 全量重训。
- `L566` **extract_locus_from_row(row)**
- `L608` **match_ultimate_drivers(seq_23nt, lr_weights, feature_names, max_n)** — 基于 Ultimate LR 系数推导候选序列自身携带的正向驱动特征与星级 (1~20nt 纯序列)。
- `L651` **generate_track2_results_ultimate(trained, X2_target, X3_target, meta_target, full_feature_names, top_k, output_path)** — 由终极模型对目标数据 X 做真实预测, 共识排序取 Top-K, 输出 赛道二_results.csv。
- `L723` **parse_args()**
- `L757` **main()**
- `L853` **_progress_path(ultimate_dir)**
- `L857` **_load_progress(ultimate_dir)**
- `L868` **_save_progress(ultimate_dir, rows)**
- `L873` **_kind_done(rows, kind)**
- `L880` **_preds_on_target(kind, model, X2_full, X3, full_feature_names, device)** — 对目标(或已测池)做预测; lr 使用与训练一致的 _T 剔除列。
- `L892` **_write_track2_from_preds(rows, preds, meta, top_k, output_path)** — 由各模型已保存的预测数组生成 赛道二_results.csv (不再需要模型对象)。
- `L931` **run_ultimate_with_resume(X2, X3, y, feature_names, selected_models, ultimate_dir, cv_folds, epochs, device, seed, n_seq_channels, target_X2, target_X3, target_meta, top_k, output_path)** — mixed 十折 CV + 全量重训 + 预测, 支持中断续跑 (完成判据见函数说明)。

### workflows/training/train.py  (734 lines, Active)
- `L70` **sanitize_name(value)**
- `L77` **sanitize_batch_name(value)**
- `L85` **validate_data_dir(data_dir)**
- `L92` **validate_feature_schema(data_dir)**
- `L112` **load_model_train_function(model, model_module)**
- `L138` **get_train_signature(train_function)**
- `L142` **print_train_interface(train_function, module_path)**
- `L156` **generate_run_name(model, split_type, environment, cell_line)**
- `L178` **build_batch_directories(batch_name, model_root_dir, results_root_dir, logs_root_dir)**
- `L207` **validate_split_configuration(split_type, cell_line, train_ratio, valid_ratio, test_ratio)**
- `L232` **prepare_split_data(data_dir, split_type, cell_line, cell_lines, train_ratio, valid_ratio, test_ratio, random_seed)**
- `L259` **validate_split_result(split_data)**
- `L291` **prepare_model_data(split_data, schema, environment, model_name)**
- `L306` **build_feature_names(schema, model_name, X_train)**
- `L329` **validate_model_input_shape(model_name, X_train, X_valid, X_test)**
- `L350` **build_train_kwargs(train_function, X_train, y_train, X_valid, y_valid, X_test, y_test, feature_names, run_name, model_dir, results_dir, logs_dir, config, random_seed, use_scaler, sequence_kernel, environment_kernel, epochs, batch_size, learning_rate, dropout, patience, min_delta, hidden_dim1, hidden_dim2, conv_channels1, conv_channels2, weight_decay, device)**
- `L441` **run_one_experiment(model_name, split_type, cell_line, cell_lines, environment, data_dir, batch_name, model_dir, results_dir, logs_dir, random_seed, train_ratio, valid_ratio, test_ratio, use_scaler, sequence_kernel, environment_kernel, epochs, batch_size, learning_rate, hidden_dim1, hidden_dim2, conv_channels1, conv_channels2, dropout, weight_decay, patience, min_delta, device, model_module, run_name)**
- `L599` **parse_args()**
- `L651` **execute_args(args)** — 由已解析的 CLI 参数执行单次实验 (与 main() 完全同一路径;
- `L728` **main()**

### app/desktop/backend_runner.py  (306 lines, Active)
- `L23` **build_active_environment_combinations(active_epis)**
- `L40` **convert_raw_csv_to_npy(csv_path, cell_line, output_dir, form_data)**
- `L94` **run_feature_engineering_step(form_data, raw_data_dir, output_data_dir, target_cell_lines)**
- `L144` **execute_full_pipeline(form_data, root_output_dir)**

### app/desktop/main_wizard.py  (536 lines, Active)
- class **CRISPRPlatformWizard** (L22)
  - `L23` **__init__(self)**
  - `L80` **_setup_ui_skeleton(self)**
  - `L105` **_clear_content(self)**
  - `L109` **_show_step(self, step)**
  - `L429` **_choose_file(self, var_name)**
  - `L433` **_choose_dir(self, var_name)**
  - `L437` **_update_folder_b_state(self)** — 控制 Folder B 控件的激活与禁用状态
  - `L443` **_update_epigenetic_cascade_linkage(self)** — 核心联动：
  - `L462` **_update_xai_linkage(self)**
  - `L482` **prev_step(self)**
  - `L486` **next_step(self)**
  - `L505` **_launch_pipeline(self)**
  - `L518` **_run_backend_task(self, out_root)**

### analysis/anomaly_treatment.py  (489 lines, Active)
- `L52` **parse_info_file(info_path)**
- `L64` **normalize_model(raw_model)**
- `L79` **normalize_cell_line(split_type, raw_cell_line)**
- `L92` **load_metrics_table(batch_dir)**
- `L120` **aggregate_metrics(df)** — 对 mixed 多种子等重复实验求平均，得到 (split_type, cell_line, model, environment) 唯一行。
- `L144` **detect_experiment_level_anomalies(metrics_df, sign_tol)** — 相对 sequence-only 基线计算 delta_R2 / delta_RMSE。
- `L215` **detect_data_level_anomalies(batch_dir, coef_threshold)** — 扫描线性回归权重文件，/Weight/ 超过阈值即标记。
- `L281` **aggregate_data_anomalies(detail_df)** — 按 (cell_line, environment) 聚合数据级异常。
- `L306` **_fmt(value, digits)**
- `L312` **build_anomaly_report(batch_dir, exp_anoms, data_anoms_detail, data_anoms_agg, metrics_found, coef_threshold, sign_tol)**
- `L407` **run_anomaly_treatment(batch_dir, summary_dir, coef_threshold, sign_tol)**
- `L451` **main()**

### analysis/collect_results.py  (442 lines, Active)
- `L38` **parse_info_txt(path)**
- `L74` **build_model_name(info)**
- `L98` **load_json(path)**
- `L105` **find_file(folder, keyword, exclude)**
- `L112` **collect_one_experiment(folder)**
- `L147` **collect_batch(batch_dir)**
- `L170` **format_pair(a, b)**
- `L176` **filter_valid(df)**
- `L182` **env_sort_key(env)**
- `L195` **get_sort_keys(row, model_col, env_col, split_col, cell_col)**
- `L207` **sort_dataframe(df, model_col, env_col, split_col, cell_col)**
- `L217` **calculate_delta_R2(df)**
- `L247` **build_result_dataframe(df, include_cell_line)**
- `L273` **create_single_result(df)**
- `L281` **create_all_result(df)**
- `L291` **create_mixed_result(df)**
- `L312` **save_result_tables(df, metrics_dir, selected_splits)** — 保存评测指标 CSV。
- `L360` **create_baseline(df, selected_splits)**
- `L388` **save_baseline_table(df, metrics_dir, selected_splits)** — 仅保存 sequence-only 基线性能表 (baseline.csv)。
- `L400` **main()**

### analysis/config.py  (65 lines, Active)
- class **AttributionRuleConfig** (L9)
- class **StatisticalRuleConfig** (L20)
- class **ConsensusRuleConfig** (L30)
- class **QCConfig** (L42)
- class **AnalysisConfig** (L51)
  - `L63` **as_dict(self)**

### analysis/data_QC.py  (1768 lines, Active)
- `L96` **_as_path(path)**
- `L100` **_read_table(path)** — 读取 csv / tsv，编码在 utf-8 / gb18030(含 gbk) / latin-1 之间自适应。
- `L114` **_find_column(columns, aliases)** — 按别名精确/忽略大小写查找列名。
- `L124` **_find_column_fuzzy(columns, aliases)**
- `L137` **_detect_epigenetic_columns(columns)** — 自动识别表观通道列 (小写关键字匹配)，返回 {规范通道名: 实际列名}。
- `L157` **_cv_bandwidth(values, cv, n_subsample, random_state, n_grid)** — 高斯核密度估计带宽选择 (严禁经验写死)：
- `L199` **_kde_values(values, bandwidth, n_points, pad)**
- `L213` **_parse_epi_vector(value, length)** — 表观通道值 -> 长度为 length 的逐位点向量 (供离群检测展平)。
- `L262` **_is_blank_value(value)** — 判空: None / NaN / 空白字符串。
- `L274` **_sample_feature_info(value, length)** — 单样本单特征列的取值解析 (不做特征列类型假设, 只按值本身格式分类):
- `L324` **_style_figure()**
- `L330` **_save_figure(fig, path)**
- `L340` **_sequence_gc_percent(seq)** — 单条序列 GC 含量 (%)；无有效碱基返回 None。
- `L348` **_outlier_reason_hints(y_value, gc_value, y_all, gc_all)** — 为离群样本给出简要归因提示 (供回溯/过滤):
- `L1617` **_resolve_input_files(data_path)**
- `L1638` **run_data_qc(data_path, output_dir)** — 第二步数据质控顶层入口。
- `L1666` **_demo_data()** — 构建演示数据源:
- `L1679` **_synthesize_demo()** — 合成 3 个细胞系脏数据 CSV (包含 N 碱基、长度异常、缺失表观通道)。
- `L1717` **main()**
- class **DataQualityController** (L371)
  - `L376` **__init__(self, data_path, output_dir, sequence_column, target_column, cell_line_column, epigenetic_columns, context_columns, force_positional, force_global, position_length, cv_folds, cv_subsample, contamination, random_state, verbose)**
  - `L446` **_build_long_frame(self)**
  - `L498` **profile_sample_sizes(self)**
  - `L522` **kde_target_efficiency(self)**
  - `L582` **detect_ambiguous_bases(self)**
  - `L617` **detect_monomorphic_positions(self)**
  - `L658` **profile_gc_content(self)**
  - `L717` **length_consistency(self)**
  - `L749` **_classify_channels(self)** — 对 feature_spec 中每列按【数据格式】自动判别：
  - `L809` **length_alignment_qc(self)** — 空间位置型特征逐样本校验位点数 == 序列长度 L (模式长度):
  - `L940` **zero_annotation_diagnostics(self)** — 区分"局部点位缺失"与"全轨完全未测":
  - `L1026` **epigenetic_gating(self)**
  - `L1099` **detect_outliers_iforest(self)**
  - `L1207` **_aggregate(self)**
  - `L1276` **run(self)**
  - `L1306` **build_markdown(self)**
  - `L1575` **write_outputs(self)**

### analysis/importance_extraction.py  (908 lines, Active)
- `L33` **parse_info_file(info_path)**
- `L45` **normalize_cell_line(split_type, raw_cell_line)**
- `L54` **get_active_channels(environment_str)**
- `L65` **identify_feature_channel(feature_name)**
- `L83` **extract_feature_position(feature_name)**
- `L97` **is_feature_valid_for_env(feature_name, environment_str)**
- `L104` **sort_dataframe_by_position(df)**
- `L111` **get_snr_significance_code(snr_val)**
- `L208` **_sanitize_importance_table(model_key, df, source)** — 字段合规清洗 (防御性断言 + Warning):
- `L239` **_sig_for_fdr(value)**
- `L249` **_derive_sig(model_key, row)** — 非线性 -> SNR 星级; 线性 -> FDR 星级。
- `L265` **_write_importance_md(model_key, records_df, out_md, title, metric_columns)** — 把已带上下文列 (split_type/environment/cell_line/feature) 的规范表写为 MD。
- `L298` **extract_linear_coefficients(target_batch_dir, feature_importance_dir)** — Linear Regression —— 经典参数检验 (白名单: Linear_Coefficient/SE/t_stat/p_value/FDR)。
- `L358` **extract_xgboost_importance(target_batch_dir, feature_importance_dir)** — XGBoost —— XAI 白名单 (XGB_Gain/XGB_Weight/XGB_Cover/TreeSHAP/SHAP_SNR), 无 p/FDR。
- `L418` **extract_mlp_importance(target_batch_dir, feature_importance_dir)** — MLP —— XAI 白名单 (MLP_IG/IG_SNR), 无 p/FDR。
- `L478` **extract_cnn_importance(target_batch_dir, feature_importance_dir)** — CNN —— XAI 白名单 (CNN_IG/CNN_ISM/ISM_SNR), 无 p/FDR。
- `L552` **extract_transformer_importance(target_batch_dir, feature_importance_dir)** — Transformer —— XAI 白名单 (Transformer_Attention/Attention_Entropy/Attention_SNR), 无 p/FDR。
- `L624` **get_canonical_feature_id(feat_name)** — 【核心归一化函数】将各种格式的特征名统一归一化为标准的 (1..23 位点, 通道名, 标准显示名)
- `L678` **collect_all_model_features(target_batch_dir)** — 汇总 5 大模型全部实验的特征重要性 CSV -> 关键调控特征库数据源。
- `L786` **generate_key_regulatory_biomarkers(df_all_feats, output_path)** — 汇总所有实验划分下 5 大模型识别出的关键特征 (原 results.py 功能)。
- `L857` **process_batch(batch_dir)**
- `L877` **main()**

### analysis/pipeline.py  (345 lines, Active)
- `L43` **capabilities_from_table(table, has_environment_cols)**
- `L64` **run_analysis(batch_dir, output, plan, config)** — Phase-2 垂直切片: 统一表 -> 校验 -> overview/status/plan 产物。
- `L327` **main()**
- class **PipelineArtifacts** (L29)
  - `L36` **create(cls, output)**

### analysis/plans.py  (242 lines, Active)
- `L108` **default_plan()**
- `L136` **validate_analysis_plan(plan, caps)** — 依赖 + 数据可得性校验。返回每个可选任务的
- class **ExecutionStatus** (L18)
- class **EnvironmentPlan** (L28)
- class **SequencePlan** (L38)
- class **CellLinePlan** (L47)
- class **StatisticsPlan** (L55)
- class **EvidencePlan** (L62)
- class **AnalysisPlan** (L69)
  - `L81` **to_json_dict(self)**
  - `L84` **save(self, path)**
  - `L90` **from_dict(cls, data)**
  - `L103` **load(cls, path)**
- class **Capabilities** (L116)
- class **ExecutionTask** (L200)
- class **ExecutionPlan** (L212)
  - `L220` **to_status_dict(self)**
  - `L237` **save_status(self, path)**

### analysis/prediction.py  (35 lines, Active)
- `L11` **performance_by_model_split(table)** — 模型 × split 的指标均值/标准差与实验数。
- `L24` **loco_performance(table)** — LOCO (split='all' 留一细胞系跨域) 泛化表。

### analysis/registry.py  (77 lines, Active)
- `L22` **register_analysis(task_id, name, category, dependencies, runner, basic, description)**
- `L40` **registered_tasks()**
- `L44` **registry_to_dict()**
- class **AnalysisTaskSpec** (L9)

### analysis/visualization.py  (959 lines, Active)
- `L92` **_metric_cfg(m_fam)** — 按模型族取指标配置 (cnn33/cnn53/cnn73 共用 cnn 配置)。
- `L102` **_make_heatmap_cmap(cfg, m_fam)** — 构造热图色图：
- `L125` **parse_info_file(info_path)**
- `L137` **parse_feature_position_channel(feat_name)**
- `L167` **load_raw_feature_records(batch_dir)**
- `L306` **load_significance_table(batch_dir)** — 解析 summary/feature_importance/ 下 5 大模型的 .md 报告，
- `L365` **generate_position_heatmaps(df_records, output_dir, sig_df)**
- `L400` **_build_significance_rank(sig_df, m_fam, split_type, cell_line, index_channels, columns_positions)** — 构造与热图 pivot 同形的显著性数值矩阵 (0=无, 1='.', 2='*', 3='**', 4='***')。
- `L434` **_draw_single_heatmap(sub_df, title_prefix, m_fam, output_path, sig_df, split_type, cell_line)**
- `L511` **load_metrics_table(batch_dir)** — 加载评测指标表 (优先 metrics_tables/all_experiments.csv)。
- `L539` **_filter_valid_metrics(df)** — 剔除发散实验 (与 collect_results.filter_valid 同规则)。
- `L557` **_prepare_tree_metrics(metrics_df)** — 按 (split_type, cell_line, model, environment) 求平均 (mixed 多种子合并)。
- `L578` **_demo_tree_metrics()** — 指标数据缺失时的演示兜底 (保持引擎零报错)。
- `L600` **combo_name(env_list)**
- `L626` **_build_dedup_combo_tree(combo_map, max_env_count)** — 以『组合集合』为节点构建去重环境增量树：
- `L673` **_walk_combo_tree(root)** — 先序遍历去重组合树 (用于校验/测试)。
- `L686` **_layout_combo_tree(root, step)** — 自上而下对去重组合树做叶槽布局：
- `L707` **_check_no_box_overlap(root, step, box_w_by_depth)** — 校验同层节点方框是否横向重叠 (仅用于测试/调试)。
- `L729` **generate_env_increment_trees(batch_dir, output_dir)** — 环境增量树图 (去重组合路径版)：
- `L776` **_draw_env_increment_tree(combo_map, base_r2, base_mae, title, output_path)** — 以"组合集合"为节点绘制去重环境增量树：
- `L867` **generate_epigenetic_comparisons(df_records, output_dir)**
- `L884` **_draw_epi_box(sub_df, title_str, palette, output_path)**
- `L911` **generate_all_visualizations(batch_dir_str, plots_dir_str)**
- `L933` **main()**
- class **_ComboTreeNode** (L613)
  - `L616` **__init__(self, envs, add_env)**

### core/features/engineering/feature_engineering.py  (2029 lines, Active)
- `L159` **load_feature_config(config_file)** — 读取 feature configuration JSON。
- `L215` **validate_feature_config(config)** — 检查 feature config 是否合法。
- `L304` **get_enabled_environment_features(config)** — 获取当前启用的 environment features。
- `L332` **validate_sequence(sequence, name)** — 检查序列长度是否为23。
- `L358` **encode_sgrna(sgrna, sequence_channels)** — 23nt sgRNA -> 23 × number_of_sequence_channels
- `L436` **encode_per_position_binary(sequence, feature_name, encoding)** — 将23字符环境轨道编码为23×1。
- `L494` **parse_position_numeric_values(value, feature_name)** — 解析23个 position-specific numeric values。
- `L608` **encode_per_position_numeric(value, feature_name)** — 23个连续数值 -> 23×1。
- `L633` **encode_global_numeric(value, feature_name)** — 一个 global scalar -> 23×1。
- `L698` **encode_environment_feature(row, spec)** — 根据 configuration 编码单个 environment feature。
- `L757` **get_channel_specs(config)** — 返回最终所有 channels 的定义。
- `L813` **build_feature_matrix(row, config)** — 一条样本：
- `L919` **generate_vector_feature_names(config)** — 根据 config 动态生成：
- `L958` **generate_feature_schema(config)** — 生成完整 feature schema。
- `L1030` **get_required_columns(config)** — 根据 config 动态生成 required columns。
- `L1067` **remove_duplicate_rows(df)** — 删除完全重复的原始记录。
- `L1133` **load_source_csv(csv_file, cell_line, config)** — 读取一个 source CSV。
- `L1245` **engineer_dataframe(df, config)** — DataFrame ->
- `L1350` **save_matrix_csv(df, features_3d, output_file, config)** — 保存 metadata + matrix。
- `L1391` **save_vector_csv(df, features_2d, output_file, config)** — 保存 metadata + 动态维度特征。
- `L1454` **save_numpy_files(features_3d, features_2d, labels, output_dir, cell_line)** — 保存动态维度 NumPy arrays。
- `L1504` **save_metadata(df, output_file)** — 保存 metadata。
- `L1532` **save_feature_schema(config, output_file)** — 保存 feature schema。
- `L1564` **process_one_csv(csv_file, output_dir, config)** — 处理单个 cell-line CSV。
- `L1764` **process_all_csv(source_dir, output_dir, config)** — 批量处理所有 CSV。
- `L1967` **parse_args()**
- `L2012` **main()**

### core/xai/importance/xai_importance.py  (135 lines, Active)
- `L76` **export_feature_table(model_key, df, rename, drop, origin)** — 导出前强制白名单清洗 (供 src 各模型 save 前调用):
- `L125` **validate_nonlinear_has_no_stats(df, model_key, origin)** — 防御性断言: 校验非线性模型输出表中无 t/p/FDR 等经典统计列。

### analysis/attribution/columns.py  (61 lines, Active)
- `L40` **family_from_model(model_raw)**
- `L55` **pick_column(columns, candidates)** — 按列名(忽略大小写)顺序挑选候选列, 返回实际列名。

### analysis/attribution/extractors.py  (139 lines, Active)
- `L24` **_parse_position_channel(feature)**
- `L41` **_read_info(exp_dir)**
- `L53` **extract_attribution_table(batch_dir)**

### analysis/attribution/summary.py  (50 lines, Active)
- `L9` **top_attribution_features(table, top_n)** — 每 (model, method) 按平均 /importance/ 取 top-N 特征 (跨 cell/split 均值)。
- `L29` **build_motif_summary_md(table, top_n)**

### analysis/cellline/consistency.py  (60 lines, Active)
- `L20` **summarize_environment_by_cellline(main_effects, effect_column, factor_column, consistent_ratio)** — 输入: pipeline 的 environment_main_effects.csv (split/cell_line/model/environment/main_r2_delta)
- `L57` **consistency_counts(summary)**

### analysis/data/loaders.py  (173 lines, Active)
- `L22` **resolve_batch_dir(batch_dir, results_root)** — 解析批次目录; 允许传 results 根目录(自动选最新含 summary 的批次)。
- `L34` **_coerce_float(series)**
- `L38` **load_experiment_table(batch_dir)** — 建立统一 experiment table (DataFrame), 列: run/model/.../metrics。
- `L90` **_legacy_scan_experiments(batch)** — legacy adapter: 无 summary 表时直接扫实验目录 info+metrics json。
- `L115` **_parse_info(exp_dir)**
- `L127` **_load_metrics_json(exp_dir)**
- `L134` **iter_experiment_records(table)** — 把统一表逐行转为 ExperimentRecord (缺失统计量保留 NaN, 不伪造)。
- `L161` **coverage_summary(table)** — 00_overview 所需的 model/cell-line/environment 覆盖。

### analysis/data/validation.py  (63 lines, Active)
- `L14` **metric_consistency_flags(delta_r2, delta_rmse, tol)** — 同一 cohort 下 R2/RMSE 同向变化 = 指标不一致 (理论矛盾)。
- `L29` **validate_metric_consistency(table, tol)** — 对 sequence 基线外的每行相对同 (split, cell_line, model) sequence 计算 delta 并标记。

### analysis/environment/incremental_effect.py  (170 lines, Active)
- `L21` **parse_environment_set(environment)** — 环境组合名 -> 环境因子集合。'sequence'->(), 'all'->4 因子。
- `L34` **combo_name(env_set)**
- `L42` **_row_env_index(rows_by_env)**
- `L51` **compute_conditional_increments(table)** — 对每个 (split, cell, model, seed) 分组, 求所有可配对 (S, S+e) 的增量。
- `L93` **summarize_conditional(raw)** — 按 (split, cell, model, add, background) 聚合 (跨 seed 均值, 报告 n 配对)。
- `L109` **compute_main_effects(conditional_raw)** — 主效应 e = 对一切不含 e 的背景 S 的 Δ(e/S) 平均 (跨 seed 后再跨背景平均)。
- `L136` **compute_pair_interactions(conditional_raw)** — 预测/统计交互占位实现: I(a,b) 用标准 2^4 正交对比平均:

### analysis/evidence/hypothesis.py  (74 lines, Active)
- `L15` **generate_hypotheses_for_record(record)** — 为 EvidenceRecord 生成结构化假设 (每条含证据/效应/不确定性/验证建议)。

### analysis/evidence/integration.py  (194 lines, Active)
- `L16` **direction_concordance(effects)** — 方向一致率: 去零方向中多数方向占比。无有效方向返回 None。
- `L29` **_direction_of_effect(effect)**
- `L41` **classify_cellline_consistency(effects_by_cell_line, consistent_ratio)** — 返回 (label, consensus_direction):
- `L65` **classify_evidence_tier(applicable_model_count, supporting_model_count, concordance, strong_stat_or_attribution, ci_crosses_zero, conflicting_direction, config)** — 按 132 节第 18 条规则给出 Tier。
- `L90` **evidence_record_row(record)** — Evidence matrix CSV 行 (跨模型列保持 None=不可用/未测, 不填 0)。
- `L112` **environment_evidence_matrix(main_effects, cellline_summary, config)** — 环境因素证据矩阵 (环境级 factor):
- `L185` **tier_from_value(value)**
- `L192` **direction_of(effect)** — 公开方向函数 (内部一致)。

### analysis/evidence/rules.py  (73 lines, Active)
- `L12` **classify_statistical_by_fdr(fdr, config)** — 仅用于真实假设检验输出的 FDR。
- `L29` **classify_attribution(snr, effect_magnitude, min_effect_size, config)** — 归因/稳健性标签 (SNR 不是 statistical significance):
- `L56` **classify_mutation_effect(snr, delta_mean, config)** — ISM 突变效应标签 (nucleotide substitution effect, 不是 feature importance)。
- `L70` **direction_of(effect)**

### analysis/reports/markdown_report.py  (180 lines, Active)
- `L11` **_fmt(v)**
- `L19` **_md_table(df, round_digits)**
- `L33` **build_prediction_md(by_model_split, loco)**
- `L43` **build_environment_md(conditional_summary, main_effects)**
- `L55` **build_overview_md(coverage, plan, status, anomaly_rows)**
- `L86` **build_cellline_md(summary, counts)**
- `L101` **build_evidence_md(matrix)**
- `L114` **build_hypotheses_md(matrix)**
- `L149` **build_data_quality_md(coverage, table, anomalies)**
- `L167` **build_anomaly_md(anomalies, matrix_excluded)**

### analysis/stats/bootstrap.py  (107 lines, Active)
- `L25` **_bootstrap_stats(values, estimator, n_iterations, seed, alpha)**
- `L52` **bootstrap_ci(data, estimator, n_iterations, seed, alpha)** — 对 data 重采样估计 estimator 的 percentile CI (estimator: np.ndarray -> float)。
- `L68` **bootstrap_difference_ci(baseline, expanded, metric_fn, n_iterations, seed, alpha, paired)** — 环境增量 Δmetric 的 Bootstrap CI (Paired baseline 原则):
- class **BootstrapResult** (L14)

### analysis/stats/effect_size.py  (32 lines, Active)
- `L12` **delta_pair(baseline_value, expanded_value)** — 返回 expanded - baseline (效果方向保持: 正=提升)。
- `L17` **compute_paired_increment(baseline_metric, expanded_metric, baseline_n, expanded_n, tolerance)** — 仅在 cohort 样本量一致 (或允许容差内) 时返回可信增量。

### analysis/stats/hypothesis_tests.py  (76 lines, Active)
- `L25` **permutation_test_for_effect(effect_values, null_effect, n_permutations, seed, one_sided)** — 单侧置换检验: H0 效应=null_effect。
- `L56` **anova_interface(data, factors, response, design_info, config)** — ANOVA = Factor effect statistical analysis (Phase 待实现, 返回不可用占位)。
- class **PermutationTestResult** (L17)

### analysis/stats/multiple_testing.py  (35 lines, Active)
- `L13` **bh_fdr(p_values)** — Benjamini-Hochberg FDR (q 值单调非降, 数值兼容 statsmodels.multipletests)。

### analysis/tests/test_attribution.py  (78 lines, Test-only)
- `L14` **_make_batch()**
- class **TestAttributionExtraction** (L47)
  - `L48` **test_canonical_rows(self)**
  - `L61` **test_position_channel_parsing(self)**
  - `L69` **test_top_summary(self)**

### analysis/tests/test_core.py  (201 lines, Test-only)
- class **TestEffectSize** (L28)
  - `L29` **test_paired_increment_same_cohort(self)**
  - `L34` **test_paired_increment_different_cohort_flagged(self)**
- class **TestMetricConsistency** (L40)
  - `L41` **test_same_increase_is_inconsistency(self)**
  - `L45` **test_same_decrease_is_inconsistency(self)**
  - `L49` **test_opposite_signs_ok(self)**
- class **TestFDR** (L53)
  - `L54` **test_bh_known_result(self)**
  - `L61` **test_nan_preserved(self)**
- class **TestBootstrap** (L67)
  - `L68` **test_ci_reproducible_and_contains_mean(self)**
  - `L78` **test_unpaired_baseline_unavailable(self)**
- class **TestEvidenceRules** (L83)
  - `L84` **test_fdr_labels(self)**
  - `L91` **test_snr_never_called_statistical(self)**
  - `L98` **test_min_effect_size_gate(self)**
- class **TestIntegration** (L105)
  - `L106` **test_direction_concordance(self)**
  - `L110` **test_cellline_consistency(self)**
  - `L116` **test_tier1_requires_two_models_and_strong_evidence(self)**
  - `L124` **test_conflicting_direction_inconclusive(self)**
- class **TestLoaderAndValidation** (L133)
  - `L134` **test_loader_and_same_cohort_consistency(self)**
- class **TestAnalysisPlanValidator** (L168)
  - `L169` **test_motif_enrichment_needs_discovery(self)**
  - `L180` **test_selected_but_unavailable_anova(self)**
  - `L191` **test_cellline_needs_two_lines(self)**

### analysis/tests/test_environment.py  (70 lines, Test-only)
- `L13` **_table()**
- class **TestParseEnvSet** (L26)
  - `L27` **test_parse(self)**
- class **TestConditionalIncrements** (L34)
  - `L35` **test_pairing_is_same_seed_only(self)**
  - `L46` **test_no_cross_seed_pairing(self)**
- class **TestMainEffects** (L58)
  - `L59` **test_two_factor_main_effect(self)**

### analysis/tests/test_phase5.py  (63 lines, Test-only)
- `L14` **_main_effects()**
- class **TestEvidenceMatrixPhase5** (L33)
  - `L34` **test_unstable_rows_excluded(self)**
  - `L42` **test_context_conflict_downgrades_to_inconclusive(self)**
  - `L55` **test_cellline_summary_labels(self)**

### analysis/tests/test_phase6.py  (110 lines, Test-only)
- `L35` **_make_batch(root)**
- class **TestPhase6PipelineReports** (L59)
  - `L60` **test_pipeline_reports_and_figures(self)**

### analysis/visualization/__init__.py  (84 lines, Active)
- `L25` **render_all(figures_dir, prediction_df, loco_df, conditional_summary, main_effects, attribution_table, cellline_df, evidence_matrix)** — 由内存中的统一表渲染全部可用图 (缺数据则跳过该主题)。
- `L66` **_load_legacy_viz_module()**
- `L81` **__getattr__(name)**

### analysis/visualization/attribution_plots.py  (38 lines, Active)
- `L15` **render(attribution_table, out_dir)**

### analysis/visualization/cellline_plots.py  (41 lines, Active)
- `L13` **render(cellline_df, out_dir)**

### analysis/visualization/core.py  (21 lines, Active)
- `L10` **style_figure()**
- `L16` **save_figure(fig, path, dpi)**

### analysis/visualization/environment_plots.py  (43 lines, Active)
- `L15` **render(conditional_summary, main_effects, out_dir)**

### analysis/visualization/evidence_plots.py  (36 lines, Active)
- `L13` **render(evidence_matrix, out_dir)**

### analysis/visualization/performance_plots.py  (35 lines, Active)
- `L13` **render(prediction_df, loco_df, out_dir)**

### app/backend/crispr_workspace/analysis.py  (256 lines, Active)
- `L41` **_default_plan_dict()**
- `L59` **registry_tasks()** — 来自 analyse.registry 的任务目录 (找不到则回退到 engine 默认任务表)。
- `L106` **heuristic_availability(batch_dir)** — 基于训练产物的浅层可用性提示 (真值由引擎在运行时判定)。
- `L158` **build_plan_dict(selected, defaults)** — 由勾选的 task ids -> engine AnalysisPlan JSON。
- `L182` **run(batch_dir, output_dir, selected_task_ids, project_meta)** — 启动 analyse.pipeline (子进程); 状态落盘 analysis_status.json。
- `L213` **analysis_status(output_dir)**
- `L246` **list_outputs(output_dir)** — 浅层列出 analyse 产物 (summary md / tables csv / figures png)。

### app/backend/crispr_workspace/artifacts.py  (158 lines, Active)
- `L26` **_confine(path, roots)**
- `L37` **classify(path)**
- `L52` **_sniff_numeric(raw)** — 轻量类型探测: 仅用于展示提示; 原始值不回写。
- `L64` **resolve_artifact(rel_or_abs, base_dirs, offset, limit)** — 解析一个 artifact 并返回其展示所需内容。
- `L122` **_csv_payload(p, offset, limit)** — 流式 CSV 预览/分页: 先扫总数(不全量载入内存), 再取目标区间行。
- class **ArtifactError** (L22)

### app/backend/crispr_workspace/config.py  (48 lines, Active)
- `L10` **repo_root()**
- `L14` **default_workspace_root()** — 默认工作根 = <仓库>/workspace; 可用环境变量 CRISPR_WORKSPACE_ROOT 覆盖。
- `L22` **config_root()** — 用户级配置目录 (如 HPC 根目录、runtime 偏好)。
- `L30` **ensure_dirs(root)**
- `L35` **allowed_read_roots()** — Artifact Resolver 允许读取的根 (防止任意路径读取)。

### app/backend/crispr_workspace/fingerprint.py  (61 lines, Active)
- `L9` **file_sha256(path, chunk)**
- `L20` **fingerprint_dataset(paths)** — 对输入文件集合生成指纹 (文件 sha256 + 基本统计)。
- `L58` **same_fingerprint(a, b)**

### app/backend/crispr_workspace/project.py  (136 lines, Active)
- `L16` **_slug(name)**
- `L21` **new_project_id()**
- `L25` **projects_root(root)**
- `L31` **project_dir(root, project_id)**
- `L37` **create_project(name, dataset_paths, root, reuse_fingerprint)** — 创建一个 Project Workspace 并落盘 project_manifest.json。
- `L73` **_resolve(root, project_id)**
- `L80` **open_manifest(root, project_id)**
- `L87` **update_stage(root, project_id, stage, status, detail)**
- `L101` **list_projects(root)**
- `L115` **create_from_qc(root, qc_session_id, name, current_paths, qc_manager)** — 从已完成 QC 会话创建项目: 复用其指纹(仅当数据未变), 避免重复计算。

### app/backend/crispr_workspace/qc_service.py  (141 lines, Active)
- `L27` **_copy_inputs(src, dst)** — 输入可为文件或目录; 目录内取 csv/tsv。多来源散落时统一暂存到会话 inputs_src。
- class **QCSessionManager** (L60)
  - `L61` **__init__(self, root)**
  - `L65` **_session_dir(self, sid)**
  - `L71` **list(self)**
  - `L80` **get(self, sid)**
  - `L92` **start(self, input_paths, note)**
  - `L116` **_launch(self, session_dir, inputs, manifest)**
  - `L135` **fingerprint(self, input_paths)**
  - `L139` **reusable(prev_manifest, new_fp)**

### app/backend/crispr_workspace/server.py  (279 lines, Active)
- `L22` **_body(handler)**
- `L33` **_respond(handler, code, obj)**
- `L43` **_send_file(handler, path, mime)**
- `L254` **serve(host, port, root, blocking)** — 启动本地服务。blocking=False 时返回 server (由调用方 start/close)。
- class **Handler** (L53)
  - `L54` **log_message(self)**
  - `L57` **_dispatch(self)**
  - `L240` **do_GET(self)**
  - `L243` **do_POST(self)**
  - `L246` **do_OPTIONS(self)**

### app/backend/crispr_workspace/store.py  (41 lines, Active)
- `L16` **utcnow()**
- `L20` **read_json(path)**
- `L28` **write_json(path, obj)** — 原子写: 先写临时文件再 rename, 防止半截文件被 GUI/恢复逻辑读到。

### app/backend/crispr_workspace/training.py  (494 lines, Active)
- `L190` **preflight(cfg)** — 运行前检查: 数据集/QC/输出可写/runtime 可用/配置有效。
- `L227` **_now()**
- `L231` **_run_id(kind)**
- `L440` **adapter_for(runtime, workspace_root)**
- `L446` **submit(cfg, workspace_root, save_config)** — 统一提交入口 (Runtime Adapter 路由)。
- `L461` **status(run_id, workspace_root)**
- `L469` **cancel(run_id, workspace_root)**
- `L477` **resume(run_id, workspace_root)**
- `L485` **list_runs(workspace_root)**
- class **TrainingConfig** (L38)
  - `L93` **default_dirs(self)**
  - `L105` **from_dict(cls, d)**
  - `L112` **validate(self)**
  - `L128` **build_command(self)**
  - `L134` **_base(self, script)**
  - `L137` **_dig_command(self)**
  - `L169` **_predict_command(self)**
- class **LocalRuntime** (L235)
  - `L238` **__init__(self, workspace_root)**
  - `L242` **submit(self, cfg)**
  - `L283` **status(self, rid)**
  - `L291` **_update_status(self, rdir, st)**
  - `L308` **_guess_from_log(self, log_path)**
  - `L317` **_progress_from_log(log_path, st)**
  - `L332` **cancel(self, rid)**
  - `L348` **resume(self, rid)** — Resume = 以相同命令重跑 (data_digging 自带断点续跑 completed 判定)。
- class **HpcRuntime** (L360)
  - `L367` **__init__(self, workspace_root)**
  - `L371` **submit(self, cfg)**
  - `L410` **status(self, rid)**
  - `L422` **cancel(self, rid)**
  - `L429` **resume(self, rid)**

### app/backend/tests/test_e2e_smoke.py  (127 lines, Test-only)
- `L19` **_make_dataset(dirp)**
- `L33` **_make_mini_batch(batch)**
- class **TestEndToEndSmoke** (L56)
  - `L57` **test_workflow_smoke(self)**

### app/backend/tests/test_no_training_dependency.py  (42 lines, Test-only)
- class **TestNoTrainingDependency** (L25)
  - `L26` **test_package_never_imports_training_science(self)**

### app/backend/tests/test_project_recovery.py  (54 lines, Test-only)
- class **TestProjectRecovery** (L11)
  - `L12` **test_stage_and_recovery(self)**
  - `L39` **test_outputs_listing(self)**

### app/backend/tests/test_workflow_interfaces.py  (131 lines, Test-only)
- class **WorkflowBase** (L13)
  - `L14` **setUp(self)**
  - `L19` **_clean(self)**
- class **TestTrainingConfig** (L25)
  - `L26` **test_dig_command_build(self)**
  - `L39` **test_predict_command_build(self)**
  - `L49` **test_preflight_on_repo_pool(self)**
  - `L56` **test_submit_dry_run_local(self)**
- class **TestAnalysisInterface** (L70)
  - `L71` **test_registry_tasks(self)**
  - `L79` **test_build_plan_dict_selection(self)**
  - `L93` **test_heuristic_availability_no_batch(self)**
- class **TestWorkflowEndpoints** (L100)
  - `L101` **_boot(self)**
  - `L110` **_post(self, base, path, body)**
  - `L116` **test_preflight_and_tasks_endpoints(self)**

### app/backend/tests/test_workspace.py  (157 lines, Test-only)
- class **WorkspaceBase** (L14)
  - `L15` **setUp(self)**
  - `L20` **_cleanup(self)**
- class **TestStoreAndProject** (L26)
  - `L27` **test_create_and_open_manifest(self)**
  - `L37` **test_write_json_atomic(self)**
- class **TestFingerprint** (L44)
  - `L45` **test_change_detected(self)**
- class **TestArtifactResolver** (L57)
  - `L58` **test_csv_and_md(self)**
  - `L76` **test_outside_root_denied(self)**
- class **TestQCSession** (L84)
  - `L85` **_make_dataset(self, name)**
  - `L100` **test_qc_standalone_run(self)**
- class **TestServer** (L132)
  - `L133` **_boot(self)**
  - `L143` **test_health_and_project_flow(self)**

### core/models/cnn/cnn.py  (873 lines, Active)
- `L49` **set_seed(seed)**
- `L65` **create_logger(log_dir)**
- `L206` **calculate_metrics(y_true, y_pred)**
- `L251` **evaluate_model(model, data_loader, criterion, device)**
- `L284` **compute_cnn_ism(model, X, device)** — In-Silico Mutagenesis (ISM，虚拟饱和突变)
- `L314` **compute_cnn_integrated_gradients(model, X, device, steps)** — 针对 3D 输入 (N, L, C) 的完备性积分梯度计算
- `L346` **compute_cnn_robustness_importance(model, X_eval, channel_names, device)** — CNN 双分支卷积的基因级归因 (XAI 白名单输出)：
- `L404` **save_predictions(y_true, y_pred, output_file)**
- `L413` **save_results(y_valid, y_valid_pred, valid_metrics, y_test, y_test_pred, test_metrics, history, result_dir, run_name, config, importance_df)**
- `L490` **save_model(model, model_path, config)**
- `L498` **train(X_train, y_train, X_test, y_test, X_valid, y_valid, feature_names, run_name, model_dir, result_dir, log_dir, config, random_seed, epochs, batch_size, learning_rate, sequence_kernel, environment_kernel, sequence_filters, environment_filters, fusion_filters, dropout, weight_decay, patience, min_delta, num_workers, device, use_scaler)**
- class **CNNModel** (L89)
  - `L90` **__init__(self, sequence_channels, environment_channels, sequence_kernel, environment_kernel, sequence_filters, environment_filters, fusion_filters, dropout)**
  - `L176` **forward(self, x)**

### core/features/channels/cell_environment_combination.py  (1908 lines, Active)
- `L189` **load_feature_schema(data_dir)** — 读取 feature_schema.json。
- `L272` **get_channel_names(schema)** — 获取所有 channel 名称。
- `L302` **get_sequence_channels(schema)** — 获取 sequence channels。
- `L350` **get_environment_channels(schema)** — 自动得到：
- `L384` **build_channel_index(schema)** — channel name → channel index
- `L408` **validate_selected_environments(schema, selected_environments)** — 验证 environment 是否存在。
- `L491` **make_combination_name_from_environments(selected_environments)** — 根据 environment 列表生成稳定名称。
- `L538` **make_combination_name(schema, selected_environments, combination)** — 为当前组合生成稳定名称。
- `L582` **get_combinations_by_size(schema, size)** — 返回指定 environment 数量的全部组合。
- `L672` **generate_combinations_by_size(schema, size)** — 指定环境数量生成组合字典。
- `L694` **generate_environment_combinations(schema, sizes)** — 生成指定规模的 environment combinations。
- `L783` **generate_combination_names(schema, include_all, include_sequence, sizes)** — 只生成组合名称。
- `L902` **resolve_environment_selection(schema, combination, selected_environments, environment_size)** — 解析最终使用的 environment。
- `L1063` **create_channel_mask(schema, combination, selected_environments)** — 创建 channel mask。
- `L1151` **apply_environment_combination(X_3d, schema, combination, selected_environments)** — 对 X_3d 应用 environment mask。
- `L1243` **flatten_features(X_3d)** — (N,L,C)
- `L1268` **normalize_model_type(model_type)**
- `L1295` **prepare_model_input(X_3d, schema, model_type, combination, selected_environments)** — 将原始 3D feature 转换成模型输入。
- `L1357` **prepare_train_valid_test(split_data, schema, combination, selected_environments, model_type)** — 将新的 cell_line_division.py
- `L1520` **generate_all_combinations(X_3d, schema, model_type)** — 为一个 X_3d 生成当前实验体系中的全部组合。
- `L1562` **generate_custom_combination(X_3d, schema, selected_environments, model_type)** — 生成自定义 environment combination。
- `L1595` **get_combination_metadata(schema, combination, selected_environments)** — 获取实验组合结构信息。
- `L1692` **print_combination_info(schema, combination, selected_environments)** — 打印当前 combination 信息。

### core/data/splitting/cell_line_division.py  (334 lines, Active)
- `L26` **load_feature_schema(data_dir)**
- `L55` **discover_available_cell_lines(data_dir)** — 动态扫描 data_dir 目录下实际拥有的细胞系
- `L75` **get_feature_file_paths(data_dir, cell_line, schema)**
- `L89` **validate_split_fractions(train_fraction, validation_fraction, test_fraction)**
- `L98` **validate_cell_line_dataset(cell_line, X_3d, X_2d, y, metadata, schema)**
- `L113` **load_cell_line(data_dir, cell_line, schema)**
- `L140` **load_all_cell_lines(data_dir, cell_lines, schema)**
- `L154` **create_split_indices(n_samples, train_fraction, validation_fraction, test_fraction, random_seed)**
- `L175` **slice_dataset(dataset, indices)**
- `L184` **merge_datasets(datasets)**
- `L195` **split_single_cell_line(dataset, cell_line, train_fraction, validation_fraction, test_fraction, random_seed)**
- `L210` **split_all_cell_lines(datasets, cell_lines, test_cell_line, train_fraction, validation_fraction, test_fraction, random_seed)** — 留一细胞系 (Leave-One-Out) 或 跨细胞系划分
- `L256` **split_mixed_cell_lines(datasets, cell_lines, train_fraction, validation_fraction, test_fraction, random_seed)**
- `L276` **attach_public_fields(split_data)**
- `L295` **divide_data(data_dir, split_type, cell_line, cell_lines, train_fraction, validation_fraction, test_fraction, random_seed)**

### core/models/linear/linear_regression.py  (852 lines, Active)
- `L395` **calculate_metrics(y_true, y_pred)** — 计算：MSE, RMSE, MAE, R2, Pearson, Spearman
- `L448` **generate_default_feature_names(feature_count)** — 动态生成默认 feature names (末尾带 Bias)。
- `L468` **select_non_t_reference_features(X, feature_names)** — 将 (N, 184) 四碱基 One-Hot 输入收缩为 (N, 161):
- `L491` **create_logger(log_dir)**
- `L516` **save_predictions(y_true, y_pred, output_file)**
- `L529` **save_weights(model, feature_names, output_file)** — 保存模型权重及统计推断指标 (白名单: Linear_Coefficient, SE, t_stat, p_value, FDR)。
- `L577` **save_linear_diagnostics(model, output_file)**
- `L598` **save_results(model, y_valid, valid_metrics, y_test, y_pred, test_metrics, feature_names, result_dir, run_name, config)**
- `L673` **train(X_train, y_train, X_test, y_test, X_valid, y_valid, feature_names, run_name, model_dir, result_dir, log_dir, config, use_scaler, pinv_rcond, random_seed)**
- class **LinearRegressionModel** (L56)
  - `L71` **__init__(self, use_scaler, pinv_rcond)** — 参数
  - `L115` **fit(self, X_train, y_train)** — 训练模型并计算统计检验指标 (SE, t-stat, p-value, FDR)。
  - `L251` **predict(self, X)** — 预测。
  - `L290` **save(self, model_dir)** — 保存模型状态与诊断。
  - `L351` **load(self, model_dir)** — 加载模型。

### core/models/mlp/mlp.py  (801 lines, Active)
- `L55` **set_seed(seed)**
- `L70` **create_logger(log_dir)**
- `L134` **calculate_metrics(y_true, y_pred)**
- `L179` **evaluate_model(model, data_loader, criterion, device)**
- `L212` **compute_integrated_gradients(model, X, device, steps)** — 原生 PyTorch 实现 Integrated Gradients (完备性积分梯度)
- `L274` **compute_mlp_robustness_importance(model, X_eval, feature_names, device)** — MLP 特征归因稳健性 (XAI 白名单输出)：
- `L328` **save_predictions(y_true, y_pred, output_file)**
- `L337` **save_results(y_valid, y_valid_pred, valid_metrics, y_test, y_test_pred, test_metrics, history, result_dir, run_name, config, importance_df)**
- `L414` **save_model(model, model_path, config)**
- `L481` **train(X_train, y_train, X_test, y_test, X_valid, y_valid, feature_names, run_name, model_dir, result_dir, log_dir, config, random_seed, epochs, batch_size, learning_rate, hidden_dim1, hidden_dim2, dropout, weight_decay, patience, min_delta, num_workers, device, use_scaler)**
- class **MLPModel** (L95)
  - `L96` **__init__(self, input_dim, hidden_dim1, hidden_dim2, dropout)**
  - `L124` **forward(self, x)**

### core/models/transformer/transformer.py  (805 lines, Active)
- `L50` **set_seed(seed)**
- `L65` **create_logger(log_dir)**
- `L211` **calculate_metrics(y_true, y_pred)**
- `L256` **evaluate_model(model, data_loader, criterion, device)**
- `L289` **compute_transformer_attention_robustness(model, X, device)** — 计算各 Position 的注意力强度 (Attn_Weight)、注意力熵 (Attn_Entropy) 与注意力信噪比 (Attn_SNR)
- `L321` **compute_transformer_integrated_gradients(model, X, device, steps)** — 3D 输入 (N, L, C) 的完备性积分梯度计算
- `L353` **compute_transformer_robustness_importance(model, X_eval, channel_names, device)** — Transformer 自注意力空间聚焦度归因 (XAI 白名单输出)：
- `L410` **save_predictions(y_true, y_pred, output_file)**
- `L419` **save_results(y_valid, y_valid_pred, valid_metrics, y_test, y_test_pred, test_metrics, history, result_dir, run_name, config, importance_df)**
- `L496` **save_model(model, model_path, config)**
- `L504` **train(X_train, y_train, X_test, y_test, X_valid, y_valid, feature_names, run_name, model_dir, result_dir, log_dir, config, random_seed, epochs, batch_size, learning_rate, d_model, nhead, num_layers, dim_feedforward, dropout, weight_decay, patience, min_delta, num_workers, device, use_scaler)**
- class **PositionalEncoding** (L89)
  - `L90` **__init__(self, d_model, max_length)**
  - `L107` **forward(self, x)**
- class **TransformerEncoderLayerWithAttn** (L118)
  - `L122` **__init__(self, d_model, nhead, dim_feedforward, dropout)**
  - `L135` **forward(self, src)**
- class **TransformerModel** (L147)
  - `L148` **__init__(self, input_dim, max_sequence_length, d_model, nhead, num_layers, dim_feedforward, dropout)**
  - `L185` **forward(self, x, return_attn)**

### core/models/xgboost/xgboost.py  (694 lines, Active)
- `L55` **calculate_metrics(y_true, y_pred)** — 计算：MSE, RMSE, MAE, R2, Pearson, Spearman
- `L110` **generate_default_feature_names(feature_count)**
- `L120` **create_logger(log_dir)**
- `L296` **get_feature_importance(model, feature_names, X_eval, y_eval, random_seed)** — 提取树模型特征重要性 (XAI 白名单输出)：
- `L378` **save_predictions(y_true, y_pred, output_file)**
- `L391` **save_training_history(model, output_file)**
- `L415` **save_results(model, y_valid, y_valid_pred, valid_metrics, y_test, y_test_pred, test_metrics, feature_names, result_dir, run_name, config, importance_df)**
- `L509` **train(X_train, y_train, X_test, y_test, X_valid, y_valid, feature_names, run_name, model_dir, result_dir, log_dir, config, use_scaler, random_seed, params, n_jobs, verbose, early_stopping_rounds)**
- class **XGBoostModel** (L145)
  - `L146` **__init__(self, params, random_seed, n_jobs, verbose, early_stopping_rounds)**
  - `L169` **_create_model(self, use_early_stopping)**
  - `L180` **fit(self, X_train, y_train, X_valid, y_valid)**
  - `L233` **predict(self, X)**
  - `L239` **save(self, model_dir, experiment_config)**
  - `L267` **load(self, model_dir)**

