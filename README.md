# 细胞环境感知型 CRISPR-Cas9 sgRNA 智能设计与影响因素发现平台

### Epigenetics-Aware Multimodal AI Platform for CRISPR-Cas9 sgRNA Design & Scientific Factor Discovery

> **参赛赛道**：赛道二 · AI 基因编辑与核酸工具设计
> **底盘系统**：SpCas9（20 nt protospacer + NGG PAM；本数据集 PAM 位于第 21–23 位，由数据验证）
> **本 README 是项目导航地图**：不打开代码，只看本文件即可定位任意程序、数据、模型、结果与文档。

---

## 1. 项目简介

**核心科学问题**：sgRNA 的编辑效率不仅取决于 23 nt 序列本身，还取决于**细胞环境**
（CTCF / Dnase / H3K4me3 / RRBS 等表观遗传通道）。本项目把
**预测 → 模型归因 → 统计检验 → 跨细胞系比较 → 证据整合 → 生物学假设** 组织为一条可追溯、可复现的流程。

1. **预测**：序列 + 细胞环境能否比纯序列更好地预测编辑效率？（`workflows/prediction/`）
2. **归因**：模型依赖哪些位点与通道？是否稳健？（`core/xai/`、`analysis/attribution/`）
3. **泛化**：跨细胞系（LOCO）与跨序列（group-aware）泛化时结论是否仍成立？（`analysis/environment/`、`analysis/evidence/`）

**AI 方法**：5 类模型（线性回归 / XGBoost / MLP / Transformer / 双分支 CNN）× 16 种环境组合 × 3 种划分
（single / LOCO `all` / mixed），共 **1344 次受控实验**；XAI（Integrated Gradients、ISM、原生 TreeSHAP、注意力）；
统计（配对 bootstrap、sign-flip 置换、BH-FDR）；环境证据三级分级（Evidence Tier）。

**当前研究范围**：4 个细胞系（hct116 / hek293t / hela / hl60）、23 nt sgRNA、23×8 = 184 维张量、
sequence-level 泛化声明（同一 sgRNA 及其反向互补不跨 train/valid/test）。

---

## 2. 项目目录树

```text
Submit/
├── README.md                    ← 项目导航（本文件，根目录唯一文件）
├──
├── app/                         应用层（GUI / Web / 桌面）
│   ├── backend/                 工作台后端服务（crispr_workspace：项目、QC、流水线、产物）
│   ├── desktop/                 桌面向导（Tkinter：main_wizard）+ 后端桥接（backend_runner）
│   ├── frontend/                Web 前端（React + Vite + TypeScript）
│   └── scripts/                 本地一键启动脚本（run_workspace.sh）
│
├── core/                        科学核心（与 UI 无关、可独立复用）
│   ├── common/                  公共设施（paths.py：项目根与默认路径的唯一定义）
│   ├── data/splitting/          cell_line_division.py（single / LOCO / mixed 划分 + 泄漏闸门）
│   ├── features/
│   │   ├── engineering/         feature_engineering.py（配置驱动：原始 CSV → 23×C 张量 + schema）
│   │   └── channels/            cell_environment_combination.py（环境组合 → 模型输入通道裁剪）
│   ├── models/                  linear / xgboost / mlp / transformer / cnn（各一目录）
│   └── xai/importance/          xai_importance.py（白名单清洗：每模型允许的归因列）
│
├── workflows/                   流程与入口（“怎么跑”都在这里）
│   ├── orchestrator/            共享编排层：steps.py（GUI 与 Web 共用唯一命令定义）
│   ├── training/                train.py（单实验）、data_digging.py（网格调度）、run.sh（批量）
│   ├── prediction/              predict.py（mixed 十折 CV + 候选预测）
│   ├── design/                  design.py（候选设计一键入口，predict.py 的薄封装）
│   └── screening/               screen.py（候选序列批量虚拟筛选）
│
├── analysis/                    分析引擎（结果 → 统计 → 证据 → 报告）
│   ├── pipeline.py              ★ 分析引擎主入口（产出 summary/{tables,reports,figures}）
│   ├── config.py / plans.py     分析配置与 AnalysisPlan（任务开关）
│   ├── data/ data_QC.py         结果表加载、一致性校验、数据质量检查
│   ├── prediction.py            预测性能汇总（含 LOCO）
│   ├── environment/             环境因素分析（因子 DAG、条件增量效应）
│   ├── attribution/             位点×通道归因汇总
│   ├── sequence/motif/          motif 发现（seqlet → 聚类 → consensus）
│   ├── cellline/                细胞系异质性
│   ├── stats/                   统计推断（bootstrap / 置换 / ANOVA / FDR）
│   ├── evidence/                证据分级（Tier 唯一权威实现 integration.py）
│   ├── visualization/           图件渲染（环境/序列/细胞系/证据/重要性）
│   ├── reports/                  Markdown 报告生成
│   ├── reporting/               paper 资产与候选分析脚本
│   ├── audit/                   审计与重算脚本（泄漏控制、证据分级再生）
│   ├── collect_results.py       指标汇总（summary/metrics_tables）
│   ├── importance_extraction.py 特征重要性提取（白名单）
│   ├── anomaly_treatment.py     异常 run 检测与处理
│   └── panorama.py              全景图总入口（plots/）
│
├── data/                        数据（只读输入）
│   ├── raw/                     原始数据，按数据集分层：
│   │   ├── DeepCRISPR/          hct116/hek293t/hela/hl60.csv（23nt sgRNA + 4 表观通道）
│   │   ├── Hiranniramol/        Hiranniramol.CSV（Edit Efficiency 0-100，无表观通道）
│   │   └── Labuhn/              Labuhn.CSV（KO_reporter_assay 0-1，无表观通道）
│   ├── processed/               DeepCRISPR 的已处理特征（8 通道 / 184 维）
│   │   └── external/            Hiranniramol + Labuhn 的已处理特征（4 通道 / 92 维，2 个数据集）
│   ├── candidate/               候选/待测序列表（todo_data.CSV）
│   └── metadata/                feature_config.json（8 通道，含表观）、
│                                feature_config_sequence_only.json（4 通道，纯序列）
│
├── models/                      模型权重（按批次归档，与代码分离）
│   ├── weights/<batch>/<run>/   每次实验的模型文件（.pkl / .pt）与超参配置
│   └── weights/adhoc/           非批次的一次性实验权重
│
├── results/                     结果（与代码、模型分离）
│   ├── batches/<batch>/         每批次完整产物（见 §6）；<batch>/summary/ 为分析产物根
│   ├── tables/                  跨批次汇总表（audit/ 审计表、paper/ 论文用表）
│   └── logs/                    训练与运行日志（<batch>/、app/、adhoc/）
│
├── docs/                        文档
│   ├── paper/                   论文（main/ 正文与 PDF、sections/、tables/、figures/、supplementary/、zh/、review/）
│   ├── science/                 科学定义（统计与参数、维度、分析状态）
│   ├── architecture/            架构与代码地图（pipeline/、app/、recon/ 重构前勘察快照）
│   ├── reproducibility/         复现资料（HPC 环境与协议、验收记录、性能报告、证据溯源）
│   └── audit/                   科学有效性与可复现性审计（问题登记、泄漏审计、证据分级审计、HPC 自检报告）
│
├── deploy/                      部署与运行环境
│   ├── environment/python/      依赖清单（requirements*.txt）
│   └── hpc/                     超算：打包、自检、验收、环境等价性比对脚本与说明
│
├── notebooks/                   交互式演示
│   ├── demos/                   演示 notebook
│   ├── builders/                notebook 生成脚本
│   └── figures/                 notebook 用图
│
├── tests/                       测试
│   ├── scientific/              科学核心与方法学测试（划分无泄漏、统计口径、证据分级、motif…）
│   └── app/                     应用与编排测试（工作台、流水线、项目生命周期）
│
└── workspace/                   Agent / 开发工作区（**不属于正式交付物**）
    ├── projects/ qc_sessions/ runs/       应用运行时数据（GUI 工作台项目）
    ├── agent/ cache/ scratch/ temporary/  Agent 临时文件、缓存、调试输出
    ├── wheels/ environments/              离线安装包与虚拟环境存档
    ├── archive/                           已废弃但具溯源价值的旧产物
    └── credentials/                       本地部署密钥（绝不入库）
```

---

## 3. 核心程序查找表

| 我要找… | 去哪里 |
|---|---|
| **数据处理 / 特征工程** | `core/features/engineering/feature_engineering.py` |
| **环境通道选择**（组合 → 模型输入） | `core/features/channels/cell_environment_combination.py` |
| **数据划分**（single / LOCO / mixed + 泄漏闸门） | `core/data/splitting/cell_line_division.py` |
| **模型** | `core/models/{linear,xgboost,mlp,transformer,cnn}/` |
| **模型解释 / 归因白名单** | `core/xai/importance/xai_importance.py` |
| **训练（单实验）** | `workflows/training/train.py` |
| **训练（1344 网格调度）** | `workflows/training/data_digging.py` → `workflows/training/run.sh` |
| **预测（十折 CV + 候选打分）** | `workflows/prediction/predict.py` |
| **候选设计（一键）** | `workflows/design/design.py` |
| **候选筛选** | `workflows/screening/screen.py` |
| **完整工作流编排** | `workflows/orchestrator/steps.py` |
| **环境因素分析** | `analysis/environment/`（因子 DAG：`analysis/environment/factorial_dag.py`） |
| **统计分析** | `analysis/stats/`（bootstrap / 置换 / ANOVA / FDR） |
| **证据分级（Evidence Tier）** | `analysis/evidence/integration.py` ★ 唯一权威实现 |
| **序列归因 / motif** | `analysis/attribution/`、`analysis/sequence/motif/` |
| **细胞系异质性** | `analysis/cellline/` |
| **图件渲染** | `analysis/visualization/`（证据图）、`analysis/panorama.py`（全景图） |
| **报告生成** | `analysis/reports/`、`analysis/pipeline.py` |
| **指标汇总 / 重要性提取** | `analysis/collect_results.py`、`analysis/importance_extraction.py` |
| **GUI / Web / 桌面** | `app/desktop/`、`app/frontend/`、`app/backend/` |
| **论文 / 科学定义** | `docs/paper/`、`docs/science/` |
| **架构与代码地图** | `docs/architecture/` |
| **复现 / 超算** | `docs/reproducibility/`、`deploy/hpc/` |
| **外部数据集接入（Hiranniramol / Labuhn）** | `docs/reproducibility/EXTERNAL_DATASETS.md` ★ 先读这个 |
| **原始格式适配层** | `core/features/engineering/dataset_adapters.py` |
| **审计与问题登记** | `docs/audit/` |
| **模型权重 / 结果 / 日志** | `models/weights/`、`results/batches/`、`results/logs/` |
| **临时开发环境** | `workspace/` |

---

## 4. 运行环境

| 项 | 开发/分析环境（审计栈） | 超算训练环境（目标栈） |
|---|---|---|
| OS | Linux (glibc 2.39) | CentOS 7 (glibc 2.17) |
| Python | 3.12.3 | 3.10.21 (conda-forge) |
| PyTorch | 2.13.0+cu130 | 2.6.0+cu124 |
| CUDA / GPU | CUDA 13.0 / 无 GPU（CPU） | CUDA 12.4 / 8 × A100-SXM4-80GB |
| NumPy / pandas | 2.5.2 / 3.0.5 | 2.2.6 / 2.3.3 |
| XGBoost | 3.4.1 | 2.0.3 |

**依赖清单**：`deploy/environment/python/`

```bash
# 开发机（本仓库默认环境）
pip install -r deploy/environment/python/requirements_frozen.txt
# 超算（CentOS 7 / A100）
pip install -r deploy/environment/python/requirements_hpc.txt
```

核心依赖：`numpy`、`pandas`、`scipy`、`scikit-learn`、`xgboost`、`torch`（`matplotlib`/`seaborn` 出图）。
说明：MLP 的 SHAP 类归因（DeepSHAP）与 SmoothGrad 已从项目中整体移除，**不再依赖 `shap` 包**；
XGBoost 的 TreeSHAP 使用其原生 `pred_contribs` 实现。

---

## 5. 运行入口（真实可执行）

> 全部命令以**项目根目录**为工作目录；入口脚本内部自行解析项目根，不依赖当前目录。

```bash
# ---------- ① 数据与特征工程 ----------
python core/features/engineering/feature_engineering.py \
    --source-dir data/raw --output-dir data/processed

# ---------- ② 训练：单次实验 ----------
python workflows/training/train.py \
    --model xgboost --split-type mixed --environment sequence_ctcf_dnase \
    --data-dir data/processed --results-dir results/batches \
    --model-dir models/weights --logs-dir results/logs \
    --batch-name demo --run-name mixed_xgboost_sequence_ctcf_dnase_seed_42 --seed 42

# ---------- ③ 训练：1344 网格（超算批量） ----------
bash workflows/training/run.sh                 # single + all + mixed
bash workflows/training/run.sh single          # 只跑 single
WORKERS=8 GPUS="0 1 2 3 4 5 6 7" bash workflows/training/run.sh

# ---------- ④ 预测 / 候选设计 / 筛选 ----------
python workflows/prediction/predict.py --batch-name demo \
       --target-input data/candidate/todo_data.CSV --candidate-top-k 50
python workflows/design/design.py --batch-name demo --candidate-top-k 50
python workflows/screening/screen.py --input data/candidate/todo_data.CSV --batch-name demo

# ---------- ⑤ 分析：指标汇总 → 分析引擎 → 全景图 ----------
python -m analysis.collect_results --batch-name demo
python -m analysis.pipeline        --batch-dir results/batches/demo
python analysis/panorama.py        --batch-dir results/batches/demo

# ---------- ⑥ 完整工作流（GUI/Web 共用同一定义） ----------
python -m workflows.orchestrator list
python -m workflows.orchestrator check   --step train_grid
python -m workflows.orchestrator command --step train_grid

# ---------- ⑦ Demo ----------
jupyter lab notebooks/demos/01_pipeline_demo.ipynb
jupyter lab notebooks/demos/DeepCRISPR_scientific_discovery_demo.ipynb

# ---------- ⑧ 应用 ----------
bash app/scripts/run_workspace.sh              # Web 工作台（前端 + 后端）
python app/desktop/main_wizard.py              # 桌面向导

# ---------- ⑨ 测试 ----------
python -m unittest discover -s tests/scientific -t .     # 科学核心
python -m unittest discover -s tests/app -t .            # 应用与编排

# ---------- ⑩ 超算：打包 / 自检 / 验收 / 环境比对 ----------
bash deploy/hpc/build_upload.sh
python deploy/hpc/preflight_hpc_rerun.py --package . --batch-name <batch>
python deploy/hpc/verify_hpc_rerun.py    --package . --batch-name <batch>
python deploy/hpc/compare_env_equivalence.py --reference <批A> --candidate <批B>
```

---

## 6. 输入输出

```text
输入
  data/raw/*.csv                     原始逐细胞系数据（序列 + 表观通道字符串 + 效率标签）
  data/metadata/feature_config.json  环境通道定义与编码规则（新增通道只改此文件）
  data/candidate/todo_data.CSV       候选/待测序列
  运行时配置                          AnalysisPlan（分析任务开关）由 analysis/plans.py 定义

处理
  core/                              特征工程 → 通道裁剪 → 模型
  workflows/                         训练 / 预测 / 设计 / 筛选 / 编排
  analysis/                          汇总 → 统计 → 证据 → 报告 → 图

输出
  results/batches/<batch>/<run>/     每个实验：
        *_metrics.json               测试集指标（R² / MAE / RMSE / Pearson / Spearman）
        *_predictions.csv            逐样本预测
        *_info.txt                   运行配置 + 划分审计（n_train/valid/test、audit_*、split_digest）
        *_feature_importance.csv     白名单归因列
  results/batches/<batch>/summary/   批次级分析产物：
        metrics_tables/              all_experiments.csv 等汇总表
        tables/ reports/ figures/    分析引擎产物
        plots/ feature_importance/   全景图与重要性
        ultimate/ 赛道二_results.csv 候选模型与候选清单
  models/weights/<batch>/<run>/      模型权重
  results/logs/<batch>/<run>/        训练日志
```

---

## 7. 数据来源与复现

**数据来源**：4 个细胞系（hct116、hek293t、hela、hl60）的已测 sgRNA 编辑效率 + 对应位点表观遗传通道
（CTCF、Dnase、H3K4me3、RRBS）。原始 CSV 见 `data/raw/`，处理后特征见 `data/processed/`；
数据许可与出处见 `docs/reproducibility/`。

**数据处理**：`core/features/engineering/feature_engineering.py` 依 `data/metadata/feature_config.json`
生成 23×8 = 184 维张量（A/C/G/T + 4 表观；表观通道 A=1 / N=0）与 `feature_schema.json`。

**去重与泄漏防控**（`core/data/splitting/cell_line_division.py`）：
* 身份键 = `min(sequence, revcomp(sequence))`（同一 sgRNA 及其反向互补视为同一身份类）；
* 三种划分全部 group-aware：**同一序列不跨 train/valid/test**；
* LOCO(`all`) 训练池先剔除留出系全部同源序列，再按 85/15 划分；
* 划分处自证：`audit_train_test_sequence_overlap == 0` 且 `audit_train_test_revcomp_overlap == 0`，非零即抛错；
  `split_digest`（sha256 前 16 位）随结果落盘，可核验「训练所用划分 == 分析所用划分」。

**split**：single / mixed 为 70/15/15（按序列分组）；LOCO 为 85/15 + 留出系全量测试。

**随机种子**：single / all 固定 42；mixed 42/43/44/45；bootstrap 2024；置换检验 B=1000（seed 2024）。

**模型版本与溯源**：每次运行在 `*_info.txt` 记录 `data_fingerprint`（数据 sha256）、`code_fingerprint`（关键代码 md5）、
`env_fingerprint` / `env_stack_id`（数值栈）、`split_digest`（划分），结果可溯源到
「数据 + 配置 + 代码 + 模型 + 随机种子」。

**结果来源与当前状态**：

* **权威批次 = `ultimate_run`**（`results/batches/ultimate_run/`）：1344 次实验，group-aware 无泄漏划分，
  验收 `PASS`（1344/1344、三种划分各 448、`split_digest` 逐条复核 0 不一致、全批单一环境栈、
  960 个神经网络 run 全部 CUDA）。验收报告：`results/tables/audit/ultimate_run_verify_report.md`。
* **历史批次 `batch_20260909_full` 已废弃**（`DEPRECATED_LEAKY_BATCH.md`）：存在已确认的划分泄漏
  （mixed 36.1%、LOCO 33.3%），仅用于泄漏前后对照，**不得用于论文数字**。
* **关键科学影响（必须写入论文）**：去除泄漏后 LOCO 泛化性能塌陷 —— 中位 R² 由旧批次 0.0362
  降至 **−0.0083**（mixed 0.1184 → 0.0734；single 0.0704 → 0.0808）。即此前报告的跨细胞系泛化
  主要由同源序列泄漏支撑；4 个表观因子在删除 DeepSHAP/SmoothGrad 后全部判为 **Inconclusive**
  （效果门槛 |ΔR²| 仅 3.2e-4 ~ 1.5e-3，远低于 0.01 阈值）。
* 审计与整改全过程见 `docs/audit/`。

---

## 8. 当前权威定义（同一概念只有一个来源）

| 概念 | 唯一权威位置 |
|---|---|
| 特征维度与环境通道 | `data/metadata/feature_config.json` + `data/processed/feature_schema.json` |
| 数据划分与泄漏防控 | `core/data/splitting/cell_line_division.py` |
| 归因白名单（每模型允许列） | `core/xai/importance/xai_importance.py` |
| 统计口径（bootstrap / 置换 / FDR） | `analysis/stats/` |
| 证据分级（Evidence Tier） | `analysis/evidence/integration.py` |
| 分析任务开关 | `analysis/plans.py`（AnalysisPlan） |
| 流水线步骤与命令 | `workflows/orchestrator/steps.py` |
| 项目路径约定 | `core/common/paths.py` |
| 依赖清单 | `deploy/environment/python/` |
| 模型权重 / 结果 / 日志 | `models/weights/`、`results/batches/`、`results/logs/` |
