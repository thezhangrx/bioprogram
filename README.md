# 细胞环境感知型 CRISPR-Cas9 sgRNA 智能设计与影响因素发现平台

### Epigenetics-Aware Multimodal AI Platform for CRISPR-Cas9 sgRNA Design & Scientific Factor Discovery

[![Python](https://img.shields.io/badge/Python-3.9%2F3.10-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-ee4c2c.svg)](https://pytorch.org/)
[![XGBoost](https://img.shields.io/badge/XGBoost-1.7%2B-green.svg)](https://xgboost.readthedocs.io/)
[![Track](https://img.shields.io/badge/Competition-Track%202%3A%20AI%20Gene%20Editing-orange.svg)](#)

> **参赛赛道**：赛道二 · AI 基因编辑与核酸工具设计
> **底盘系统**：SpCas9（20 nt protospacer + NGG PAM；本数据集 PAM 位于第 21–23 位，由数据验证）
> **一句话定位**：本平台不仅预测 sgRNA 编辑效率，而是把 **预测 → 模型归因 → 统计检验 → 跨细胞系比较 → 证据整合 → 生物学假设** 组织为一条可追溯、可复现的科学发现流程。

---

## 📑 目录

1. [项目要解决的问题](#1-项目要解决的问题)
2. [快速开始](#2-快速开始)
3. [目录结构](#3-目录结构)
4. [平台流程与模块](#4-平台流程与模块)
5. [模型与解释方法](#5-模型与解释方法)
6. [已有结果与交付物（含产出核对表）](#6-已有结果与交付物含产出核对表)
7. [结果摘要（真实数值）](#7-结果摘要真实数值)
8. [数据来源、许可与防泄漏](#8-数据来源许可与防泄漏)
9. [随机种子与可复现性](#9-随机种子与可复现性)
10. [Model Card（适用范围与已知局限）](#10-model-card适用范围与已知局限)
11. [已知限制：本平台不做与不能做的事](#11-已知限制本平台不做与不能做的事)
12. [文档与论文索引](#12-文档与论文索引)
13. [疑难排查](#13-疑难排查)
14. [团队贡献](#14-团队贡献)

---

## 1. 项目要解决的问题

CRISPR-Cas9 的 sgRNA 效率预测已有大量工作，但**预测精度提升并不等于科学理解**：线性模型给出方向与统计量却表达受限；树模型的 Gain/Weight/Cover 没有方向；深度模型能学到序列模式，但内部表示难以直接解释。

因此平台的目标不是"再训一个更准的模型"，而是回答四个科学问题：

| # | 科学问题 | 平台对应的分析 |
| :--- | :--- | :--- |
| 1 | 哪些序列位置与候选模式与编辑效率相关？ | 五类模型位置归因 + seqlet/聚类/motif + 富集检验 |
| 2 | 细胞表观遗传环境是否在序列之外提供**额外预测信息**？ | 16 组合全因子 ΔR² + 逐样本配对 bootstrap + 区组 ANOVA |
| 3 | 同一因素在不同 cell line 中是否保持方向与幅度？ | cell-line context 标签（一致 / 依赖 / 冲突 / 不确定） |
| 4 | 多个模型是否**独立**支持同一候选因素？ | 跨模型证据矩阵 + 证据分级（Tier 1–3 / Inconclusive） |

---

## 2. 快速开始

### 2.1 环境要求

| 项目 | 要求 |
| :--- | :--- |
| 操作系统 | Linux / macOS / Windows（本项目在 Linux 上开发与验证） |
| Python | 3.9 – 3.10（依赖与版本区间见 `requirements.txt`） |
| GPU | **不需要**：有 CUDA 时训练自动使用 GPU；分析、Notebook 与报告全程 CPU |
| Node.js | 仅图形工作台需要（≥ 18） |

```bash
python -m venv .venv && source .venv/bin/activate     # 或 conda create -n crispr python=3.10
pip install -r requirements.txt
```

### 2.2 四种使用方式

```bash
# 方式 A（推荐评委体验）：演示 Notebook —— 只读已有结果，不训练、不用 GPU，约 1 分钟
jupyter notebook notebooks/DeepCRISPR_scientific_discovery_demo.ipynb

# 方式 B：图形工作台（Notebook 式向导；Create Project 直接进入 Workspace）
bash scripts/run_workspace.sh              # 后端 API :8765 + 前端 :5173
#   Cell 01 Name（项目名可修改 + 目录弹窗选择输出目录；前端无 batch 概念）
#   Cell 02 Data Input（选已测/待测数据集 → 运行数据集探测：细胞系 + 表观通道）
#   Cell 03 Quality Control
#   Cell 04 User Decision / Mapping（列出数据集中实际出现的符号，如 A / N → 选择映射 → 可选执行特征工程）
#   Cell 05 Training / Device（Cells/Scope 来自探测结果；Device=cpu/gpu/cpu/gpu 按模型锁定；可选候选生成）
#   Cell 06 Analysis（直接使用 Cell 01 输出目录下的 results/，无需输入）+ 可选步骤
#   Cell 07 Reports + 可选交付物核对      Cell 08 Project Files（文件浏览/预览）
#   流程步骤已拆分到各阶段 cell，每步带勾选框由用户决定是否执行；训练/步骤输出实时显示

# 方式 C：桌面引导向导（7 步全流程，无需命令行参数）
python Input/main_wizard.py

# 方式 D：命令行复现（示例：单细胞系 + sequence 环境 + XGBoost）
python data_digging.py --help                                    # 受控实验网格运行器
python train.py --model xgboost --split-type single --cell-line hct116 \
                --environment sequence --batch-name demo
python -m analyse.pipeline --batch-dir results/demo              # 分析引擎（统计/证据/图表/报告）
python analyse/visualization.py --batch-dir results/demo         # 全景图（位置热图/环境树/表观对比）
```

**一条完整流水线**（从原始数据到分析报告）：

```bash
python src/feature_engineering.py --source-dir data/source_data \
        --output-dir data/proceeded_data --config data/feature_config.json   # Step 0 特征工程
python data_digging.py --batch-name demo --models linear xgboost mlp cnn transformer \
        --cell-lines hct116 hela --split-types single all                    # Step 1 网格训练
python analyse/collect_results.py --batch-name demo                          # Step 2 指标汇总
python analyse/importance_extraction.py --batch-name demo                    # Step 3 重要性/稳健性报告
python -m analyse.pipeline --batch-dir results/demo                          # Step 4 统计/证据/报告/图表
python analyse/visualization.py --batch-dir results/demo                     # Step 5 全景图
```

### 2.3 生成候选 sgRNA 清单

```bash
python design.py --dry-run                              # 先看计划（不训练、不写文件）
python design.py --candidate-top-k 20                   # 生成候选清单（多模型打分 + 优先级排序）
python screen.py --input my_candidates.csv --top-k 50   # 对给定候选清单做虚拟筛选
```

输出：`results/<batch>/summary/赛道二_results.csv`，字段包含候选编号（`CAND_sgRNA_001`…）、
23 nt 候选序列、预测编辑效率、推荐模型与排序理由（UTF-8 CSV）；
候选排序所用模型输出至 `results/<batch>/summary/ultimate/`。

> 定位说明：`design.py` / `screen.py` 做的是**候选优先级排序（candidate prioritization / screening）**，
> 不是序列从头生成（de novo generation）；两者都是 `predict.py` 的薄封装，不含独立科学逻辑。

---

## 3. 目录结构（对齐大赛《附件5》建议结构）

本项目按《附件5》建议的板块组织，并在下表给出「官方板块 → 本项目路径」的对应关系。
所有入口脚本均使用**相对路径**（`data/proceeded_data`、`models`、`results`、`logs`），
可在项目根目录直接运行，无硬编码绝对路径。

| 官方板块 | 本项目路径 | 说明 |
| :--- | :--- | :--- |
| `README.md` | `README.md` | 项目说明、环境、运行命令、输入输出与结果说明 |
| `requirements.txt` | `requirements.txt` | 依赖与版本区间（Python 3.9–3.10） |
| `data/` | `data/` | `source_data/`（原始 4 细胞系）+ `proceeded_data/`（23×8 特征产物与 `feature_schema.json`） |
| `src/` | `src/` | 训练侧核心源码：特征工程、5 类模型、XAI、划分与环境掩码 |
| `models/` | `models/` | **最终模型权重**：`models/<batch>/<run_name>/`（含 `*_model.pt/.pkl` 与 `*_config.json`） |
| `notebooks/` | `notebooks/` | 可执行 Notebook（只读结果演示）+ 生成脚本 + 导出图 |
| `logs/` | `logs/` | **训练日志**：`logs/<batch>/<run_name>/training.log`（另含 `logs/workspace/` 工作台运行日志） |
| `results/` | `results/` | 结果与候选清单（1 344 次运行 + 分析产物 + `summary/赛道二_results.csv`） |
| `train.py` | `train.py` | 单次训练入口（5 类模型 / 3 种划分 / 16 种环境组合） |
| `design.py` | `design.py` | **候选设计入口**（多模型打分 + 优先级排序；复用 `predict.py`） |
| `screen.py` | `screen.py` | **候选虚拟筛选入口**（对给定候选清单打分排序） |
| `predict.py` | `predict.py` | 推理 / 候选生成主程序（`--generate-candidates`、`--target-input`） |
| （额外）网格训练 | `data_digging.py` | 受控实验网格运行器（多模型 × 多环境 × 多划分 × 多种子） |
| （额外）分析引擎 | `analyse/` | 统计/证据/motif/报告引擎（只读 `results/`，131 项测试） |
| （额外）图形工作台 | `backend/` + `frontend/` | Notebook 式 Web 工作台（展示与编排，无科学计算） |
| （额外）桌面向导 | `Input/` | 7 步引导向导（`main_wizard.py` / `backend_runner.py`） |
| （额外）工具脚本 | `scripts/` | `run_workspace.sh`、`build_upload.sh`、`make_notebook.py` |
| （额外）文档 | `docs/` | 流水线文档、统计接线、HPC 环境与协议、性能台账、论文溯源与质量检查 |
| （额外）论文 | `paper/` | LaTeX 正式稿 + 已编译 PDF + 图表 + 参考文献 |

```text
Submit/
├── README.md                     # 本文件（官方板块）
├── requirements.txt              # 依赖（官方板块）
├── train.py                      # 训练入口（官方板块）
├── predict.py                    # 推理/候选生成（官方板块）
├── design.py                     # 候选设计入口（官方板块）
├── screen.py                     # 候选虚拟筛选入口（官方板块）
├── data_digging.py               # 受控实验网格运行器
├── data/                         # 官方板块：原始数据 + 特征产物
│   ├── feature_config.json
│   ├── source_data/
│   └── proceeded_data/
├── src/                          # 官方板块：训练侧核心源码
│   ├── feature_engineering.py
│   ├── linear_regression/ xgboost/ mlp/ cnn/ transformer/
│   └── input_control/
├── models/                       # 官方板块：模型权重（models/<batch>/<run_name>/）
├── notebooks/                    # 官方板块：演示 Notebook + 导出图
│   ├── DeepCRISPR_scientific_discovery_demo.ipynb
│   ├── build_notebook.py
│   └── figures/
├── results/                      # 官方板块：结果与候选清单
├── logs/                         # 官方板块：训练日志（logs/<batch>/<run_name>/training.log）
├── scripts/                      # 工具脚本
│   ├── run_workspace.sh
│   ├── build_upload.sh
│   └── make_notebook.py
├── analyse/                      # 分析引擎（只读 results/，含 tests/）
├── backend/ + frontend/          # Web 工作台
├── Input/                        # 桌面引导向导
├── docs/                         # 文档（含 HPC 环境/协议、性能台账、论文溯源）
└── paper/                        # 论文（LaTeX + compiled/main.pdf、main_v2.pdf）
```

## 4. 平台流程与模块

```text
原始数据 (data/source_data)
   ↓  src/feature_engineering.py
特征与数据映射 (data/proceeded_data + feature_schema.json)
   ↓  data_digging.py（网格）/ train.py（单次）
受控训练与评测 (results/<batch>/<run_name>/*_metrics.json, *_predictions.csv)
   ↓  analyse.pipeline（只读）
① QC 与结果校验   ② 预测与泛化   ③ 环境析因（16 组合）   ④ 序列归因与 motif
⑤ 细胞系异质性    ⑥ 统计检验（bootstrap / permutation / BH-FDR / ANOVA）
⑦ 跨模型证据整合  ⑧ Markdown 报告 + 图表 + 交互式科学发现报告
```

关键设计：**训练与分析解耦**。分析引擎只读结果文件，不重训、不改训练产物；报告层（含前端）只读
CSV / JSON / Markdown / PNG，**不复制任何统计规则**。

### 4.1 统一编排层（向导 ⇄ 网页工作台共用）

步骤、命令、依赖与产物只在 **`pipeline/steps.py`** 定义一次，桌面向导（`Input/backend_runner.py`）
与网页工作台（`backend/crispr_workspace/pipeline.py`）都调用它；执行统一走
`training.submit_command`，因此流程步骤与训练**共用同一 run 存储**（`/api/runs`、
`/api/runs/<id>/log` 实时输出、Cancel/Resume 一致）。

| step_id | 类别 | 重任务 | 产物 |
| :--- | :--- | :---: | :--- |
| `feature_engineering` | data | | `data/proceeded_data/feature_schema.json` |
| `train_grid` | train | ✅ | `summary/metrics_tables/all_experiments.csv` |
| `generate_candidates` | train | ✅ | `summary/赛道二_results.csv` |
| `collect_results` / `anomaly_treatment` / `legacy_visualization` | analysis | | `summary/metrics_tables`、`summary/anomaly_report.md`、`summary/plots` |
| `importance_extraction` | deliverable | | `summary/feature_importance/key_regulatory_biomarkers.csv` |
| `analysis_engine` | analysis | | `analyse_out/{analysis_status.json,summary,figures}` |
| `deliverables_check` | deliverable | | 内部只读核对 |

```bash
python -m pipeline list / check / order                  # 只读：步骤清单、产物状态、依赖顺序
python -m pipeline command --step train_grid             # 预览命令（不执行）
```

细节见 `docs/pipeline_integration.md`。

### 4.2 分析任务清单（写入 `analysis_status.json`）

| 任务 | 含义 |
| :--- | :--- |
| `qc` · `prediction` | 数据质量与预测/泛化汇总 |
| `environment_conditional_effect` · `environment_main_effect` | 配对 ΔR² 与主效应（16 组合全因子） |
| `environment_factorial_dag` | 2⁴ factorial lattice（16 节点 / 32 条条件边；缺失不伪造） |
| `bootstrap` · `hypothesis_testing` · `fdr_correction` | 逐样本配对 bootstrap、sign-flip 置换、分族 BH-FDR |
| `environment_anova` | Type-II 区组析因方差分析（模型/细胞系/划分为区组） |
| `sequence_attribution` · `cnn_ism` · `motif_discovery` · `motif_enrichment` | 位置归因、突变效应、候选模式与富集 |
| `cellline_heterogeneity` · `evidence_integration` · `hypothesis_generation` | 细胞系一致性、证据分级、候选假设 |

---

## 5. 模型与解释方法

| 模型 | 配置数 | 建模视角 | 归因方法 | 语义类别 |
| :--- | :--- | :--- | :--- | :--- |
| Linear Regression | 1 | 线性主效应 | 系数、SE、t、p、FDR（伪逆解析解） | Statistical evidence |
| XGBoost | 1 | 非线性与特征交互 | TreeSHAP（主）、Gain/Weight/Cover（辅） | Attribution |
| MLP | 1 | 一般非线性组合 | Integrated Gradients、SmoothGrad | Attribution |
| Dual-Branch CNN | 3（序列核 3/5/7） | 局部序列模式 | CNN_IG（主）、ISM（突变效应） | Attribution / Mutation effect |
| Transformer | 1 | 跨位置信息交互 | Attention、Attention Entropy | Supporting evidence only |

**语义边界（平台强制）**：`ΔR²` = 增量预测价值；`attribution` = 模型依赖强度；`SNR` = 归因稳健性；
`p/FDR` 仅来自真实零假设检验；**注意力、SNR、Gain/Weight/Cover 均不作为统计显著性**。

---

## 6. 已有结果与交付物（含产出核对表）

### 6.1 产出核对表（按仓库实测状态）

| 交付物 | 状态 | 位置 / 生成命令 |
| :--- | :--- | :--- |
| 训练结果（1 344 次运行） | ✅ 已存在 | `results/batch_20260909_full/<run_name>/` |
| 统一指标表 | ✅ 已存在 | `results/batch_20260909_full/summary/metrics_tables/all_experiments.csv` |
| 关键调控特征库 | ✅ 已存在 | `results/batch_20260909_full/summary/feature_importance/key_regulatory_biomarkers.csv`（92 489 行） |
| 分析表格 / 报告 / 图 | ✅ 已存在 | `results/batch_20260909_full/analyse_out/{tables,summary,figures}/` |
| **模型权重** | ✅ **已入库** | `models/batch_20260909_full/<run_name>/`（2 880 个文件：`*_model.pt` / `*.pkl` / `*_config.json` / diagnostics） |
| **训练日志** | ✅ **已入库** | `logs/batch_20260909_full/<run_name>/training.log`（1 344 份） |
| 演示 Notebook + 图 | ✅ 已存在 | `notebooks/DeepCRISPR_scientific_discovery_demo.ipynb`、`notebooks/figures/` |
| 正式论文 PDF | ✅ 已存在 | `paper/compiled/main.pdf`（v1，22 页）、`paper/compiled/main_v2.pdf`（v2，23 页） |
| **候选 sgRNA 清单** | ✅ **已存在** | `results/batch_20260909_full/summary/赛道二_results.csv`（20 条候选，含 `pos18_C(***)` 等驱动特征；由 `generate_candidates` 步骤产出） |
| 终极模型参数 | ✅ 已存在 | `results/batch_20260909_full/summary/ultimate/` |

> 说明：本表按仓库**实测**状态维护；未生成项给出准确命令，不标注为已完成。
> 模型权重与训练日志由 `train.py --model-dir models --logs-dir logs`（`data_digging.py` 同默认值）写入，
> 目录结构为 `models/<batch>/<run_name>/` 与 `logs/<batch>/<run_name>/`。

### 6.2 训练结果结构

```text
results/batch_20260909_full/
├── <run_name>/                     # *_metrics.json · *_predictions.csv · *_info.txt · *_feature_importance.csv
├── summary/metrics_tables/all_experiments.csv        # 1 344 行统一指标表
├── summary/feature_importance/                       # 7 个模型/方法重要性报告 + 关键调控特征库
└── summary/plots/                                    # 位置热图、环境增量树、消融视图、表观因子对比
```

### 6.3 分析产物结构

| 内容 | 文件 |
| :--- | :--- |
| 表格（28 个 CSV） | `experiment_table.csv`、`environment_main_effects.csv`、`environment_conditional_delta_r2.csv`、`environment_edges.csv`、`bootstrap_results.csv`、`permutation_results.csv`、`anova_results.csv`、`evidence_matrix.csv`、`motif_candidates.csv`、`attribution_summary.csv` 等 |
| 报告（15 个 Markdown） | `00_overview.md` … `07_biological_hypotheses.md`、`importance_vs_delta_r2.md`、`environment_dag_report.md` |
| 图（293 张 PNG） | `02_prediction/`、`03_environment/`（含 factorial DAG 63 张）、`04_motif/`、`05_cellline/`、`06_evidence/`、`07_evidence/` |
| 状态与溯源 | `analysis_status.json`（任务状态 + artifact 路径）、`analysis_plan.json`、`execution_log.json` |

---

## 7. 结果摘要（真实数值）

> 全部数字由结果文件重新计算，可用 `paper/make_assets.py` 与演示 Notebook 复现。

**① 预测能力（single 划分，每配置 64 次运行）**

| 模型 | 中位 R² | IQR |
| :--- | ---: | :--- |
| XGBoost | 0.115 | 0.090 – 0.124 |
| MLP | 0.085 | 0.041 – 0.099 |
| CNN k=7 | 0.080 | 0.063 – 0.101 |
| Transformer | 0.069 | 0.047 – 0.105 |
| CNN k=5 | 0.057 | 0.044 – 0.088 |
| CNN k=3 | 0.035 | 0.022 – 0.063 |
| Linear Regression | 0.087（21/64 次发散） | −0.001 – 0.101 |

**② 序列归因（跨模型）**：PAM 位于第 21–23 位（数据验证：100% 记录末两位为 GG）；
**4/5 个模型类**（CNN / MLP / Transformer / XGBoost）把 PAM 邻近种子区（17–20）列为最高归因区域；
第 18 位是跨模型平均归因谱的第 1 位；第 18 位归因中 C 的占比在 XGBoost 为 0.64–0.77。

**③ 多尺度 CNN（192 组严格配对实验）**：k5 − k3 = **+0.042**（88.5% 配对为正）；
k7 − k3 = **+0.056**（95.8%）；k7 − k5 = **+0.013**（77.1%）。
三个核配置提取的候选模式长度中位数均为 4 nt —— **核大小 ≠ motif 长度**。

**④ 环境增量预测价值（本数据集的诚实结论：弱）**：跨模型平均主效应 ΔR² 为 −0.0093 ~ −0.0009；
2 541 个 edge×seed 检验中仅 **257** 个 bootstrap 95% CI 不跨 0；区组析因 ANOVA 主效应
p = 0.056–0.663（n = 1 288）。证据矩阵中 RRBS 为 Tier 1、DNase 为 Tier 2，CTCF / H3K4me3 为 Inconclusive。

**⑤ 候选序列模式**：从 CNN 归因提取 **596** 个候选模式，其中 **64** 个通过 BH-FDR < 0.05；
最高支持度模式为 `CTGG`。

**⑥ 细胞系依赖**：第 18 位 C 相对 A 的平均效率差在 HCT116 为 +0.090、HeLa +0.092、
HL60 +0.028，而 **HEK293T 为 −0.016（方向反转）** —— 该序列特征具有 context dependence。

---

## 8. 数据来源、许可与防泄漏

- **数据来源**：公开基准数据集 **DeepCRISPR**（Chuai et al., *Genome Biology* 2018, 19:80；doi:10.1186/s13059-018-1459-4），
  含 4 个人类细胞系（HCT116 / HEK293T / HeLa / HL60）的 sgRNA 活性与匹配的表观基因组轨道
  （CTCF / DNase / H3K4me3 / RRBS，ENCODE 来源，随数据集提供）。
- **外部数据**：本项目**未引入任何额外外部数据**，未使用任何隐藏评测集。
- **数据流**：`data/source_data/`（原始）→ `data/proceeded_data/`（特征产物）；
  `feature_schema.json` 记录 23 nt × 8 通道 = **184 维**特征定义与编码规则；
  Linear Regression 内部按统计惯例剔除 `_T` 参照列（184 → 161），其余模型使用完整 184 维。
- **划分与防泄漏**：训练/验证/测试按 0.70/0.15/0.15 在**样本级**划分，种子固定（见 §9）；
  标准化（scaler）参数仅在训练集上拟合；同一 `(划分, 细胞系, 模型, 种子)` 的配对比较使用**同一测试集**；
  序列合法性与标签分布检查见 `analyse_out/summary/01_data_quality.md`。

---

## 9. 随机种子与可复现性

| 项目 | 取值 |
| :--- | :--- |
| `single` / `all` 划分 | 种子 42 |
| `mixed` 划分 | 种子 42 / 43 / 44 / 45（取均值） |
| bootstrap | 2 000 次重采样，种子 2024，α = 0.05 |
| permutation（sign-flip） | 1 000 次，种子 2024 |
| 分析阈值（`analyse/config.py`） | SNR 2.5 / 1.8 / 1.2；FDR 0.001 / 0.01 / 0.05；最小效应量 0.005；数值发散阈值 10.0 |
| ANOVA | 最少 32 观测、残差自由度 ≥ 5；效应 CI bootstrap 400 次 |
| motif | 长度 4–12 nt；位置分位 0.90、连续性分位 0.75；最小支持 seqlet ≥ 30、样本 ≥ 20；聚类相似度 0.90 |

复现命令：`python -m analyse.pipeline --batch-dir results/batch_20260909_full`。
引擎会把每个任务的**状态、原因与产物路径**写入 `analysis_status.json`，便于逐项核对；
演示 Notebook 的每一步都会打印其实际读取的结果文件。

---

## 10. Model Card（适用范围与已知局限）

**适用**
- 输入：23 nt 靶序列（A/C/G/T）+ 4 条逐位点二值表观遗传轨道 + 细胞系标识（single 划分）。
- 输出：归一化编辑效率预测值；位置/通道级模型归因；候选序列模式；跨模型证据分级。
- 场景：**同一数据分布内**的候选 sgRNA 优先级排序与机制假说生成；教学与科研探索。

**不适用 / 已知局限**
- 不用于临床或治疗决策；未在任何湿实验体系中验证。
- 预测性能有限（中位 R² 0.03–0.16），不可作为唯一筛选依据。
- 表观遗传通道为二值编码；环境增量贡献在本数据集中很弱且方向不一致。
- CNN 归因对卷积核大小敏感（k=7 与 k=3/5 的位置谱相关性仅 0.21–0.23）。
- 注意力权重不区分方向，仅作支持性信息；本批次缺 Transformer IG 产物。
- Linear Regression 在 192 次运行中 56 次数值发散（平台标记并隔离，不删除）。
- 当前权重/日志未入库（`models/`、`logs/` 为空）；如需复现训练请指定 `--model-dir` / `--logs-dir` 后重新运行。

---

## 11. 已知限制：本平台不做与不能做的事

1. **不做因果推断**：所有输出为预测 / 关联 / 归因证据；机制确认需突变或编辑实验。
2. **不重训、不改结果**：分析引擎与报告层只读训练产物（`analyse/`、`frontend/` 均无训练逻辑）。
3. **不伪造缺失结果**：结果缺失时任务记为 `unavailable`/`skipped` 并写明原因；Notebook 打印 `SKIP` 后跳过。
4. **本批次 LOCO 分支退化**：`all`（留一细胞系）划分的 R² 与 `single` **逐位相同**（max|ΔR²| = 0），
   因此 README 与论文均**不**把 `all` 结果当作跨细胞系泛化证据；真正的留一验证需重新执行训练配置。
5. **无湿实验验证**：编辑效率实测、切割活性、脱靶检测、编辑窗口与递送适配均未开展。
6. **非经典 PAM**：当前模型针对 NGG PAM；NAG/NGA 等需扩展 PAM 分支后重新训练。

---

## 12. 文档与论文索引

| 想了解 | 看这里 |
| :--- | :--- |
| 5 分钟看懂平台发现流程 | `notebooks/DeepCRISPR_scientific_discovery_demo.ipynb` |
| 全流程代码与数据流 | `docs/project_pipeline_and_code_documentation.md` |
| 分析引擎说明 | `analyse/README.md` |
| **统一编排层与前端整合**（向导 ⇄ 网页共用步骤定义、新 API、文件查看、实时日志） | `docs/pipeline_integration.md` |
| 统计工具接线与可用性 | `docs/statistical_analysis_status.md` |
| 论文结论 → 结果文件映射 | `docs/paper_claim_provenance.md` |
| 论文质量检查（科学性/文献/图表/LaTeX） | `docs/paper_quality_check.md` |
| 正式论文（22 页，7 图 7 表，12 篇核验文献） | `paper/compiled/main.pdf` |
| 论文图表复现脚本 | `paper/make_assets.py` |
| 前端与工作台架构 | `docs/frontend_architecture.md` |
| HPC 环境与实验协议 | `docs/HPC_ENVIRONMENT.md`、`docs/HPC_EXPERIMENT_PROTOCOL.md` |
| 性能与验收记录 | `docs/PERF_REPORT.md`、`docs/acceptance_record.md` |

---

## 13. 疑难排查

| 现象 | 处理 |
| :--- | :--- |
| Notebook 打印 `[SKIP] missing result file` | 该结果文件不存在（例如尚未运行分析流程）；先执行 `python -m analyse.pipeline --batch-dir results/<batch>` |
| `ModuleNotFoundError: analyse` | 在**项目根目录**运行，或 `export PYTHONPATH=$PWD` |
| 训练报 CUDA 相关错误 | 脚本自动回落 CPU；如需强制 CPU：`CUDA_VISIBLE_DEVICES="" python train.py ...` |
| 前端启动失败 | 需 Node ≥ 18；先 `cd frontend && npm install`，再 `bash scripts/run_workspace.sh` |
| 想删除项目 | Home 项目列表右侧「删除」→ 弹窗**倒计时 3 秒**后可确认；会级联删除项目目录与该项目输出目录（含 results/models/logs） |
| 误删交付结果的风险 | 已有保护：仓库内**任何**路径（含 `results/<batch>/`）不会被项目删除动作删掉；仅 workspace 内的项目输出可删 |
| 调试时想复核既有批次 | 用命令行参数：`python -m pipeline check --output-dir "$PWD" --batch-name batch_20260909_full`（前端不提供该输入） |
| Training 的 Cells / Scope 为空 | 先在 Cell 02 运行「数据集探测」；选项一律来自用户数据集 |
| Device 下拉被锁死 | 只勾了线性/树模型（linear、xgboost）时按规则锁定 cpu；勾选深度模型（mlp/cnn/transformer）后可选 gpu |
| 数据里有 A / N 需要决定 | Cell 04 会列出每个通道出现的符号（A 为明确可用、N 为未知），选择映射后保存即写入 `feature_config.user.json` 供特征工程使用 |
| 想重新生成论文图表 / 全景图 | `python paper/make_assets.py`；或 `python analyse/visualization.py --batch-dir results/<batch>` |
| 想生成候选清单 | `python design.py --candidate-top-k 20`（或前端 cell 7 运行 `generate_candidates`） |
| 前端看不到训练输出 / 状态一直 running | 本轮已修复僵尸进程判定（`training._process_alive` + reaper 线程）；确保后端为最新代码并重启 `scripts/run_workspace.sh` |
| 前端流程步骤显示 pending | 该步骤产物尚未生成；可在 cell 7 勾选 dry-run 先预览命令，或真实运行该步骤（重任务会写 models/results/logs） |

---

## 14. 团队贡献

| 角色 | 贡献 |
| :--- | :--- |
| （待补：成员姓名 / 单位） | 数据与特征工程；模型训练与调参；可解释性分析；统计与证据整合；前端与报告；论文撰写 |

> 提交前请补齐成员分工与单位信息。代码、数据与结果的可追溯性说明见 §6 与 `docs/paper_claim_provenance.md`。
