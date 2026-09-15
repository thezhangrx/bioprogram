# 项目文件树（核心文件与程序）

工作目录：`/home/zhang/bioprogram/Submit`
格式：`|-- 文件名   说明`（每行一条，说明一行内）

**未列出**：`results/`、`models/`、`logs/`、所有 `__pycache__/` 与 `*.pyc`、
`app/frontend/node_modules/`（5 059 个依赖文件）、`.git/`、`.venv/`、`.ssh_push/`、
`_backup_degenerate_all_20260913b/` 内部、`workspace/runs/*/` 内部、`.ssh_push/`（gitignore 的 HPC 推送私钥）。

```
.
|-- workflows/training/train.py                     单实验训练入口（被 data_digging 逐个调用）
|-- workflows/training/data_digging.py              网格调度：16 环境 × 4 模型 × 3 split = 1344 次实验
|-- workflows/prediction/predict.py                   mixed 十折交叉验证 + 目标数据集候选预测
|-- workflows/design/design.py                    一键候选设计（候选优先级排序，非 de novo 生成）
|-- workflows/screening/screen.py                    一键虚拟筛选（对给定候选序列清单打分排序）
|-- run.sh                       批量训练入口（批次安全闸门 + 多卡自动绑定）
|-- requirements.txt             早期宽松依赖清单（面向旧平台）
|-- requirements_frozen.txt      开发机审计栈锁定版本（numpy 2.5.2 / torch 2.13.0+cu130）
|-- requirements_hpc.txt         超算目标栈（glibc 2.17 + 驱动 550 → torch cu124）
|-- README.md                    项目总说明
|-- README_HPC_RERUN.md          超算重跑操作说明
|-- .gitignore                   版本忽略规则
|
|-- src/                         【训练代码】模型与数据处理
|   |-- feature_engineering.py           sgRNA 序列 + 表观环境特征工程（23×8 → 184 维）
|   |-- xai_importance.py                XAI 特征重要性白名单与导出清洗（学术红线）
|   |-- input_control/
|   |   |-- cell_line_division.py        数据划分：group-aware 无泄漏切分 + 泄漏自证闸门
|   |   |-- cell_environment_combination.py  表观通道组合选择与训练输入组装
|   |-- cnn/cnn.py                       双分支 CNN（序列核 × 环境核）+ ISM/IG 重要性
|   |-- mlp/mlp.py                       MLP 模型 + Integrated Gradients
|   |-- transformer/transformer.py       Transformer 模型 + 注意力稳健性
|   |-- xgboost/xgboost.py               XGBoost + TreeSHAP 重要性
|   |-- linear_regression/linear_regression.py  线性回归（含统计推断与秩诊断）
|
|-- analysis/                     【分析引擎】只读训练产物，产出证据
|   |-- __init__.py                      分析引擎包声明
|   |-- pipeline.py                      编排入口（产物根 <batch>/summary）
|   |-- plans.py                         AnalysisPlan / 执行计划与状态
|   |-- registry.py                      分析任务注册表（新增分析只需注册）
|   |-- config.py                        集中科学规则配置（阈值不散落）
|   |-- schemas.py                       统一科学记录类型与证据标签
|   |-- leakage.py                       身份/重叠分类学与 group-aware 划分（权威定义）
|   |-- prediction.py                    预测与泛化性能（含 LOCO）
|   |-- collect_results.py               扫描 run 目录汇总为统一指标表
|   |-- anomaly_treatment.py             批量实验异常检测与治疗报告（标记不删除）
|   |-- importance_extraction.py         多模型重要性/稳健性提取（官方交付物）
|   |-- importance_metrics.py            重要性–ΔR² 二维图的指标注册表与筛选规则
|   |-- data_QC.py                       数据质控与特征探测引擎
|   |-- visualization.py                 全景图引擎（位置热图/增量树/表观对比）
|   |-- README.md                        分析引擎说明
|   |-- data/
|   |   |-- __init__.py                  数据层包声明
|   |   |-- loaders.py                   训练产物 → 统一实验表（只读）
|   |   |-- validation.py                结果校验与指标一致性标记
|   |-- environment/
|   |   |-- __init__.py                  环境分析包声明
|   |   |-- incremental_effect.py        条件 ΔR² / 主效应（配对基线原则）
|   |   |-- factorial_dag.py             2^4 因子 DAG 数据层（节点/边/消融/交互）
|   |-- stats/
|   |   |-- __init__.py                  统计层包声明
|   |   |-- bootstrap.py                 Bootstrap CI（稳定性证据，非因果）
|   |   |-- effect_size.py               Effect 定义与配对基线原则
|   |   |-- hypothesis_tests.py          归因统计检验接口
|   |   |-- multiple_testing.py          BH-FDR 多重检验校正
|   |   |-- tasks.py                     统计工具接到真实 effect（bootstrap/置换/FDR/ANOVA）
|   |-- evidence/
|   |   |-- __init__.py                  证据层包声明
|   |   |-- integration.py               跨模型/跨细胞系证据整合（唯一 Tier 权威实现）
|   |   |-- hypothesis.py                生物假设的受控措辞
|   |-- cellline/
|   |   |-- __init__.py                  细胞系分析包声明
|   |   |-- consistency.py               细胞系效应汇总与上下文一致性判定
|   |-- attribution/
|   |   |-- __init__.py                  attribution 包声明
|   |   |-- extractors.py                从训练产物抽取统一 attribution 表
|   |   |-- columns.py                   各模型重要性列名 → 统一字段映射
|   |   |-- summary.py                   统一 attribution → 序列/motif 摘要
|   |-- sequence/
|   |   |-- __init__.py                  序列层包声明
|   |   |-- motif/
|   |   |   |-- __init__.py              motif 包声明
|   |   |   |-- core.py                  seqlet 提取/聚类/consensus/富集/稳定性
|   |   |   |-- iupac.py                 motif 三种表示形式（分开保存）
|   |   |   |-- pipeline.py              motif 发现编排（tables → figures → markdown）
|   |-- reports/
|   |   |-- __init__.py                  报告层包声明
|   |   |-- markdown_report.py           summary/reports/*.md 生成
|   |-- visualization/
|   |   |-- __init__.py                  图表包声明与总渲染入口
|   |   |-- core.py                      图表样式与保存基元
|   |   |-- performance_plots.py         预测/泛化图
|   |   |-- environment_plots.py         条件 ΔR² 热图 + 主效应
|   |   |-- attribution_plots.py         位置归因热图
|   |   |-- cellline_plots.py            特征 × 细胞系效应图
|   |   |-- evidence_plots.py            证据矩阵/层级汇总图
|   |   |-- factorial_dag.py             因子 DAG 渲染
|   |   |-- importance_delta.py          重要性–ΔR² 二维证据坐标图
|   |-- docs/
|   |   |-- interface_contract.md        分析引擎接口契约（产物结构/CLI）
|   |   |-- workflow_architecture.md     分析工作流架构
|   |   |-- code_cleanup_report.md       代码清理报告
|   |-- tests/
|   |   |-- __init__.py                  测试包声明
|   |   |-- test_core.py                 核心科学函数（配对基线/ΔR²/FDR/CI/Tier）
|   |   |-- test_8channel_no_legacy.py   8 通道回归（T 不得被丢弃）
|   |   |-- test_leakage_identity.py     身份/重叠/group-aware 划分
|   |   |-- test_split_code_parity.py    训练层 vs 分析层划分交叉验证（二阶审计）
|   |   |-- test_loco_regression.py      LOCO 未再退化为 single 的守卫
|   |   |-- test_delta_r2_baseline_pairing.py  ΔR² 基线配对（含 seed/kernel）
|   |   |-- test_environment.py          条件 ΔR² / 主效应
|   |   |-- test_environment_dag.py      因子 DAG（2^4 格）
|   |   |-- test_ablation_tree.py        消融树
|   |   |-- test_attribution.py          attribution 统一抽取
|   |   |-- test_importance_delta.py     重要性–ΔR² 二维证据图
|   |   |-- test_importance_delta_r2.py  同一主题的任务书 16 项
|   |   |-- test_evidence_tier_rules.py  Evidence Tier 权威规则
|   |   |-- test_stats_wiring.py         统计接线（实现→输出→报告→前端状态）
|   |   |-- test_phase5.py               细胞系一致性 + 证据矩阵
|   |   |-- test_phase6.py               端到端报告/图形产物
|   |   |-- test_motif_discovery.py      motif 发现（含降级路径）
|
|-- pipeline/                    【共享编排层】向导与网页工作台共用
|   |-- __init__.py                      包声明
|   |-- __main__.py                      python -m workflows.orchestrator 只读调试入口
|   |-- steps.py                         全部可执行步骤注册表（含产物声明）
|
|-- app/backend/                     【本地后端】Workflow API（标准库，零依赖）
|   |-- README.md                        后端说明
|   |-- crispr_workspace/
|   |   |-- __init__.py                  包声明
|   |   |-- server.py                    本地 HTTP API 服务
|   |   |-- project.py                   项目创建/打开（manifest 为状态源）
|   |   |-- pipeline.py                  步骤列表 + 受控执行
|   |   |-- dataset.py                   数据集探测：从用户数据推断可选项
|   |   |-- config.py                    跨平台路径策略
|   |   |-- store.py                     JSON 状态存取（状态可从文件恢复）
|   |   |-- artifacts.py                 产物定位与预览服务
|   |   |-- files.py                     项目文件浏览与读取
|   |   |-- fs_browser.py                目录选择服务
|   |   |-- fingerprint.py               数据指纹（防止错误复用旧 QC）
|   |   |-- qc_service.py                Data QC 会话管理
|   |   |-- analysis.py                  分析接口
|   |   |-- training.py                  训练适配接口
|   |-- tests/
|   |   |-- test_workspace.py            后端单测（仅标准库）
|   |   |-- test_dataset_inspection.py   数据集探测 + Mapping + Device + 删除
|   |   |-- test_e2e_smoke.py            端到端 smoke（QC 真实引擎 + 训练 dry-run）
|   |   |-- test_no_training_dependency.py  红线守卫：后端不得 import 训练模块
|   |   |-- test_pipeline_orchestration.py  编排层与流程/文件 API
|   |   |-- test_project_recovery.py     项目重开后状态可恢复
|   |   |-- test_wizard_shared_pipeline.py  向导 ⇄ 编排层一致性
|   |   |-- test_workflow_interfaces.py  TrainingConfig/CLI/Preflight/Runtime 接口
|
|-- app/frontend/                    【网页工作台】React + Vite
|   |-- index.html                       页面模板
|   |-- package.json                     前端依赖与脚本
|   |-- package-lock.json                依赖锁定
|   |-- vite.config.ts                   Vite 构建配置
|   |-- tsconfig.json                    TS 配置
|   |-- tsconfig.node.json               TS（Node 侧）配置
|   |-- dist/index.html                  已构建静态产物入口
|   |-- dist/assets/index-4caFx63G.js    已构建 JS bundle
|   |-- dist/assets/index-CPScUQu8.css  已构建 CSS bundle
|   |-- src/
|   |   |-- main.tsx                     React 挂载
|   |   |-- App.tsx                      应用入口与路由
|   |   |-- types.ts                     全局类型定义
|   |   |-- index.css                    全局样式
|   |   |-- vite-env.d.ts                Vite 类型声明
|   |   |-- api/
|   |   |   |-- client.ts               HTTP 客户端封装
|   |   |   |-- project.ts              项目接口
|   |   |   |-- dataset.ts              数据集接口
|   |   |   |-- dataset.test.ts         数据集接口测试
|   |   |   |-- pipeline.ts             流水线接口
|   |   |   |-- pipeline.test.ts        流水线接口测试
|   |   |   |-- training.ts             训练接口
|   |   |   |-- analysis.ts             分析接口
|   |   |   |-- artifacts.ts            产物接口
|   |   |   |-- files.ts                文件读取接口
|   |   |   |-- fs.ts                   目录浏览接口
|   |   |   |-- qc.ts                   QC 接口
|   |   |-- components/
|   |   |   |-- StepRunner.tsx          步骤执行器
|   |   |   |-- DataInputCell.tsx       数据输入单元格
|   |   |   |-- MappingCell.tsx         列映射单元格
|   |   |   |-- NameCell.tsx            名称单元格
|   |   |   |-- DirPicker.tsx           目录选择弹窗
|   |   |   |-- FileBrowser.tsx         文件浏览器
|   |   |   |-- QcDashboard.tsx         QC 仪表盘
|   |   |   |-- TrainingPanel.tsx       训练面板
|   |   |   |-- AnalysisPanel.tsx       分析面板
|   |   |   |-- ReportsPanel.tsx        报告面板
|   |   |   |-- RunsHistory.tsx         运行历史
|   |   |   |-- RunLogViewer.tsx        运行日志查看器
|   |   |   |-- NotebookCell.tsx        notebook 单元格
|   |   |   |-- EvidenceBadge.tsx       证据等级徽标
|   |   |   |-- EvidenceBadge.test.tsx  证据徽标测试
|   |   |   |-- StatusChip.tsx          状态标签
|   |   |   |-- StatusChip.test.tsx     状态标签测试
|   |   |   |-- artifacts/
|   |   |   |   |-- ArtifactViewer.tsx  产物查看器
|   |   |   |   |-- CsvViewer.tsx       CSV 预览
|   |   |   |   |-- MarkdownViewer.tsx  Markdown 预览
|   |   |-- views/
|   |   |   |-- HomeView.tsx            首页
|   |   |   |-- WorkspaceView.tsx       工作台视图
|   |   |   |-- StandaloneQcView.tsx    独立 QC 视图
|   |   |-- reports/
|   |   |   |-- ScientificReport.tsx    科学报告渲染
|   |   |   |-- ScientificReport.test.ts 报告渲染测试
|   |   |   |-- ReportDataAdapter.ts    报告数据适配
|   |   |   |-- sections.tsx            报告章节组件
|   |   |   |-- types.ts                报告类型
|   |   |-- lib/
|   |   |   |-- format.ts               数值/文本格式化
|   |   |   |-- format.test.ts          格式化测试
|   |   |   |-- labels.ts               中文标签映射
|   |   |   |-- pipeline.ts             前端流程推导
|   |   |   |-- pipeline.test.ts        流程推导测试
|   |   |   |-- resolve.test.ts         产物解析测试
|   |   |-- test/render.tsx             测试用渲染工具
|
|-- app/desktop/                       【桌面向导】7 步交互客户端
|   |-- main_wizard.py                   7 步引导向导客户端（交互与联动）
|   |-- backend_runner.py                后端全自动执行引擎（含候选设计模式）
|
|-- data/                        【数据】
|   |-- feature_config.json              特征/通道配置
|   |-- todo_data.CSV                    待处理数据清单
|   |-- source_data/
|   |   |-- hct116.csv                   原始数据（hct116）
|   |   |-- hek293t.csv                  原始数据（hek293t）
|   |   |-- hela.csv                     原始数据（hela）
|   |   |-- hl60.csv                     原始数据（hl60）
|   |-- proceeded_data/                  训练用成品数据
|   |   |-- feature_schema.json          特征 schema（23×8=184）
|   |   |-- feature_engineering_summary.csv  特征工程摘要
|   |   |-- hct116_metadata.csv          hct116 的 sgRNA/位点/标签（训练读取）
|   |   |-- hct116_labels.npy            hct116 标签
|   |   |-- hct116_features_23x8.npy     hct116 3D 特征
|   |   |-- hct116_features_184.npy      hct116 2D 展平特征
|   |   |-- hct116_184.csv               hct116 的 CSV 版（训练不读，供人工核对）
|   |   |-- hct116_23x8.csv              hct116 的 CSV 版（训练不读）
|   |   |-- hek293t_metadata.csv / _labels.npy / _features_23x8.npy / _features_184.npy  hek293t 训练数据
|   |   |-- hek293t_184.csv / hek293t_23x8.csv   hek293t CSV 版（训练不读）
|   |   |-- hela_metadata.csv / hela_labels.npy / hela_features_23x8.npy / hela_features_184.npy  hela 训练数据
|   |   |-- hela_184.csv / hela_23x8.csv         hela CSV 版（训练不读）
|   |   |-- hl60_metadata.csv / hl60_labels.npy / hl60_features_23x8.npy / hl60_features_184.npy  hl60 训练数据
|   |   |-- hl60_184.csv / hl60_23x8.csv         hl60 CSV 版（训练不读）
|
|-- upload/                      【超算上传包】只训练，42 个文件，与仓库同源
|   |-- MANIFEST.md5                     全包校验和（md5sum -c 自检）
|   |-- README_HPC_RERUN.md              超算三步走说明
|   |-- workflows/training/train.py / workflows/training/data_digging.py / run.sh   训练入口与调度（同根目录版本）
|   |-- workflows/prediction/predict.py                       候选预测（本次重跑不需要）
|   |-- requirements.txt                 宽松清单
|   |-- requirements_frozen.txt          开发机审计栈
|   |-- requirements_hpc.txt             超算目标栈（cu124）
|   |-- src/                             训练代码副本（含修复版 cell_line_division.py）
|   |-- data/metadata/feature_config.json         特征配置
|   |-- data/processed/feature_schema.json      特征 schema 副本
|   |-- data/processed/feature_engineering_summary.csv  特征工程摘要
|   |-- data/processed/{hct116,hek293t,hela,hl60}_{metadata.csv,labels.npy,features_23x8.npy,features_184.npy}  四系训练数据
|   |-- deploy/hpc/preflight_hpc_rerun.py   起飞前自检（99 项断言）
|   |-- deploy/hpc/verify_hpc_rerun.py      跑完验收（覆盖度 + split_digest 复核）
|   |-- deploy/hpc/compare_env_equivalence.py  环境等价性比对
|   |-- docs/HPC_RERUN_PREFLIGHT.md      自检报告
|   |-- docs/HPC_ENVIRONMENT_FIT.md      平台适配说明
|
|-- scripts/                     【运维脚本】
|   |-- preflight_hpc_rerun.py           起飞前自检（计划/数据/划分/批次/溯源/版本）
|   |-- verify_hpc_rerun.py              跑完验收（1344 覆盖度 + 逐 run 复核）
|   |-- compare_env_equivalence.py       两套环境的指标等价性比对
|   |-- leakage_controlled_recompute.py  旧批次泄漏控制后的评估重算
|   |-- regenerate_evidence_tier_assets.py  复用中间资产重生成 Tier 资产
|   |-- regenerate_permutation_and_evidence.py  R1–R7 阶段化再生成（不重训）
|   |-- build_upload.sh                  构建超算上传包
|   |-- run_workspace.sh                 启动本地工作台
|   |-- make_notebook.py                 生成 pipeline 演示 notebook
|   |-- refresh_after_loco_rerun.sh      LOCO 重跑后的自动刷新流程
|
|-- notebooks/                   【演示】
|   |-- 01_pipeline_demo.ipynb                     全流程演示
|   |-- DeepCRISPR_scientific_discovery_demo.ipynb 科学发现演示（只读结果）
|   |-- build_notebook.py                          从真实结果构建上述 notebook
|   |-- figures/fig1_model_performance.png         演示图 1（模型性能）
|   |-- figures/fig2_sequence_attribution.png      演示图 2（序列归因）
|   |-- figures/fig3_cnn_kernel_ablation.png       演示图 3（卷积极消融）
|   |-- figures/fig4_environment_incremental.png   演示图 4（环境增量）
|
|-- paper/                       【论文】
|   |-- main.tex                         论文正文 LaTeX 源
|   |-- main.pdf                         论文正文编译产物
|   |-- references.bib                   参考文献
|   |-- main.aux                         LaTeX 编译中间文件
|   |-- main.bbl                         LaTeX 参考文献编译产物
|   |-- main.log                         LaTeX 编译日志
|   |-- main.out                         LaTeX 书签输出
|   |-- make_assets.py                   从真实产物生成论文图与表
|   |-- make_pdf_fallback.py             无 TeX 环境时的回退 PDF 渲染
|   |-- make_position18_summary.py       位置 18 一页 A4 摘要生成
|   |-- position18_summary.tex           位置 18 摘要源
|   |-- position18_summary.pdf           位置 18 摘要编译产物
|   |-- position18_candidate_summary.pdf 位置 18 候选汇总单页
|   |-- position18_summary.aux            LaTeX 编译中间文件
|   |-- position18_summary.log            LaTeX 编译日志
|   |-- position18_summary.out            LaTeX 编译输出
|   |-- README_BUILD.md                  论文构建说明
|   |-- sections/
|   |   |-- 00_abstract.tex              摘要
|   |   |-- 01_introduction.tex          引言
|   |   |-- 02_methods.tex               方法
|   |   |-- 03_results.tex               结果
|   |   |-- 04_discussion.tex            讨论
|   |   |-- 05_limitations.tex           局限
|   |   |-- 06_conclusion.tex            结论
|   |   |-- 07_availability.tex          数据/代码可用性
|   |   |-- 08_future_validation.tex     未来实验验证
|   |-- supplementary/supplementary.tex  补充材料
|   |-- tables/
|   |   |-- tab1_dataset.tex             表 1 数据集
|   |   |-- tab2_prediction.tex          表 2 预测性能
|   |   |-- tab3_environment.tex         表 3 环境效应
|   |   |-- tab4_kernel.tex              表 4 卷积核对比
|   |   |-- tab5_motifs.tex              表 5 motif
|   |   |-- tab6_candidates.tex          表 6 候选清单
|   |   |-- tabS1_methods.tex            附表 1 方法
|   |   |-- tabS2_sequence.tex           附表 2 序列
|   |-- figures/                         每张图同时提供 png 与 pdf
|   |   |-- fig1_workflow.png / .pdf        图 1 工作流（方法示意）
|   |   |-- fig2_prediction.png / .pdf      图 2 预测与泛化
|   |   |-- fig3_environment.png / .pdf     图 3 环境效应
|   |   |-- fig4_sequence_attribution.png / .pdf  图 4 序列归因
|   |   |-- fig5_kernel.png / .pdf          图 5 卷积核消融
|   |   |-- fig6_cellline.png / .pdf        图 6 细胞系异质性
|   |   |-- fig7_evidence.png / .pdf        图 7 证据整合
|   |   |-- figS1_importance_delta.png / .pdf  附图 S1 重要性–ΔR²
|   |   |-- position18_attribution.png      位置 18 归因图
|   |   |-- position18_base_effect.png      位置 18 碱基效应图
|   |   |-- position18_signed_substitution.png  位置 18 有符号替换 ISM 图
|   |-- compiled/
|   |   |-- main.tex / main.pdf             历史编译版本
|   |   |-- main_v2.pdf / main_v2.log       历史第二版编译产物
|   |   |-- README_PDF.md                   PDF 产物说明
|
|-- docs/                        【文档】
|   |-- PROJECT_TREE.md                  本文件（项目文件树）
|   |-- PROJECT_FULL_PIPELINE_MAP.md     全流程地图
|   |-- project_pipeline_and_code_documentation.md  项目与代码文档（主文档）
|   |-- statistics_and_parameters_zh.md  统计口径与参数中文说明
|   |-- statistical_analysis_status.md   统计分析状态
|   |-- pipeline_integration.md          流水线集成说明
|   |-- dimension.md                     维度与数据结构说明
|   |-- frontend_architecture.md         前端架构
|   |-- HPC_ENVIRONMENT.md               超算环境说明
|   |-- HPC_EXPERIMENT_PROTOCOL.md       超算实验协议
|   |-- PERF_REPORT.md                   性能报告
|   |-- acceptance_record.md             验收记录
|   |-- 论文.md                          中文论文草稿
|   |-- _map_data_and_qc.md              数据与 QC 地图
|   |-- _map_analysis_and_evidence.md    分析与证据地图
|   |-- _recon_parameters.md             参数重建
|   |-- _recon_provenance.md             溯源重建
|   |-- _recon_statistics.md             统计重建
|   |-- paper_claim_provenance.md        论文论断溯源（旧）
|   |-- paper_claim_provenance_v2.md     论文论断溯源（v2）
|   |-- paper_quality_check.md           论文质量检查（旧）
|   |-- paper_quality_check_v2.md        论文质量检查（v2）
|   |-- paper_revision_v2.md             论文修订记录 v2
|   |-- paper/evidence_tier_provenance.md  Tier 溯源说明
|   |-- paper_analysis/
|   |   |-- README.md                    论文数字重算说明
|   |   |-- position18_ism_audit.py      位置 18 ISM 审计脚本
|   |   |-- position18_signed_substitution_ism.py  有符号替换 ISM
|   |   |-- asset_summary.json           资产汇总
|   |   |-- bootstrap_edge_by_factor.csv 因子级 bootstrap 边
|   |   |-- cnn_ism_position_profile.csv CNN ISM 位置轮廓
|   |   |-- cnn_kernel_paired.csv        CNN 卷积核配对比较
|   |   |-- cross_model_position_consistency.csv 跨模型位置一致性
|   |   |-- environment_by_cellline.csv  环境 × 细胞系
|   |   |-- environment_cross_model.csv  环境跨模型
|   |   |-- factor_level_ci.csv          因子水平 CI
|   |   |-- kernel_position_profile.csv  卷积核位置轮廓
|   |   |-- nucleotide_frequency_by_position.csv 位置碱基频率
|   |   |-- position18_attribution.csv   位置 18 归因
|   |   |-- position18_efficacy_by_base.csv 位置 18 碱基效应
|   |   |-- position_profile_by_model.csv 各模型位置轮廓
|   |   |-- region_attribution.csv       区域归因
|   |-- audit/
|       |-- PROJECT_SCIENTIFIC_REPRODUCIBILITY_AUDIT.md  项目级可复现性审计
|       |-- PROJECT_SCIENTIFIC_REMEDIATION_FINAL.md      整改结论
|       |-- SUMMARY_ARTIFACT_PROVENANCE.md               summary 产物溯源（谁生成什么）
|       |-- HPC_RERUN_PREFLIGHT.md                       HPC 重跑自检报告
|       |-- HPC_ENVIRONMENT_FIT.md                       超算平台适配说明
|       |-- issue_register.csv                           问题登记册（初版）
|       |-- issue_register_final.csv                     问题登记册（最终状态）
|       |-- paper_claim_audit_final.csv                  论文论断审计
|       |-- leakage_controlled_recompute.md              泄漏控制重算说明
|       |-- evidence_tier_scientific_definition.md       Tier 科学定义
|       |-- evidence_tier_R1_audit.md                    Tier 改造 R1 审计
|       |-- evidence_tier_R2_fdr_aggregation.md          Tier 改造 R2（FDR 归族）
|       |-- evidence_tier_R3_statistical_gate.md         Tier 改造 R3（统计闸门）
|       |-- evidence_tier_R4_effect_aggregation.md       Tier 改造 R4（效应聚合）
|       |-- evidence_tier_R5_concordance.md              Tier 改造 R5（一致性）
|       |-- evidence_tier_R1_R6_execution.md             Tier 改造 R1–R6 执行记录
|       |-- evidence_tier_code_audit.md                  Tier 代码审计
|       |-- evidence_tier_before_after.md                Tier 改造前后对比
|       |-- evidence_tier_final_statistical_audit.md     Tier 最终统计审计
|       |-- evidence_tier_threshold_audit.csv            阈值审计
|       |-- dataset_routing_audit.csv                    数据路由审计
|       |-- split_integrity_audit.csv                    划分完整性审计
|       |-- leakage_overlap_audit.csv                    泄漏重叠审计
|       |-- preprocessing_leakage_audit.csv              预处理泄漏审计
|       |-- feature_integrity_audit.csv                  特征完整性审计
|       |-- statistical_unit_audit.csv                   统计单位审计
|       |-- experiment_identity_audit.csv                实验身份审计
|       |-- environment_reproducibility_audit.csv        环境可复现性审计
|       |-- audit_min_absolute_delta_r2.py               |ΔR²|≥0.01 门槛审计脚本
|       |-- audit_factor_level_permutation.py            因子水平置换审计脚本
|
|-- workspace/                   【运行时工作区】（运行产物，非源码）
|   |-- projects/                        项目状态（每个项目一个 proj_* 目录）
|   |   |-- proj_*/project_manifest.json 项目清单（状态源）
|   |   |-- proj_*/inputs/               该项目输入数据副本
|   |   |-- proj_*/qc/                   该项目 QC 结果
|   |   |-- proj_*/training/             该项目训练配置
|   |   |-- proj_*/artifacts/            该项目产物索引/预览
|   |   |-- proj_*/reports/              该项目报告
|   |   |-- proj_*/output/{results,models,logs}/  该项目训练输出
|   |   |-- proj_*/analysis/             该项目分析引擎快照（analysis/{tables,summary,figures} + 4 个 json）
|   |   |-- proj_*/analysis_plan.json    该项目使用的分析计划
|   |   |-- proj_*/analysis_status.json  分析任务状态快照
|   |   |-- proj_*/analysis_run.json     分析运行记录
|   |   |-- proj_*/analysis_run.log      分析运行日志
|   |   |-- proj_*/training_status.json  训练状态快照
|   |   |-- proj_*/project_events.log    项目事件流水
|   |-- qc_sessions/                     独立 Data QC 会话记录
|   |   |-- qc_*/session_manifest.json   QC 会话清单
|   |   |-- qc_*/qc_summary.json         QC 汇总结果
|   |   |-- qc_*/quality_report.md       QC 质量报告
|   |   |-- qc_*/outliers_detailed_report.csv  离群点明细
|   |   |-- qc_*/gc_content_kde.png      GC 含量分布图
|   |   |-- qc_*/target_efficiency_kde.png  目标效率分布图
|   |-- runs/                            流水线各步骤运行日志（每步一目录，内部未展开）
|
|-- _backup_degenerate_all_20260913b/    448 个"all 退化成 single"旧目录的备份（未展开）
```

## 四条主链

- **训练链**：`workflows/training/data_digging.py → workflows/training/train.py → src/{cnn,mlp,transformer,xgboost,linear_regression}`，划分由 `core/data/splitting/cell_line_division.py` 负责。
- **分析链**：`analysis/collect_results.py → analysis/pipeline.py → paper/make_assets.py`，产物统一写入 `results/<batch>/summary/`。
- **工作台链**：`app/frontend/ → app/backend/crispr_workspace/ → pipeline/steps.py`。
- **超算链**：`upload/`（自检 → `run.sh` 跑 1344 → 验收 → 回传）。
