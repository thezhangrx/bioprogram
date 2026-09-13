# analyse — 工作流架构 (Workflow Architecture)

> 证据分析引擎只读消费训练产物; 训练系统 (src/, predict.py, Input/) 不被分析需求修改。
> 本文描述端到端编排与各阶段的输入/输出契约。

## 1. 端到端工作流

```text
[训练端, 已完成] 1344 实验批次 (HPC 8×A100)
        │  每实验目录: info/result json; 批次 summary/metrics_tables/all_experiments.csv
        │  + summary/feature_importance/*.md  (xai_importance.py 导出, whitelist 字段)
        ▼
[分析端 analyse.pipeline --batch-dir <batch> --output <out>]   ← 只读
  qc (01/08) → prediction (02) → environment conditional+main (03)
  → sequence attribution (04) → cellline heterogeneity (05)
  → evidence integration (06) → hypothesis generation (07)
        │  每阶段: tables/*.csv (机器可读) + summary/0X_*.md (人类可读)
        ▼
[产物] analysis_plan.json / analysis_status.json / execution_log.json
       figures/<02..06>/  (证据图, 300dpi PNG)
        ▼
[消费者] 未来 GUI/CLI 只写 AnalysisPlan、只读 status/reports —— 不接触训练系统
```

## 2. 分层职责 (依赖方向只向下)

| 层 | 模块 | 职责 |
|---|---|---|
| 配置 | `analyse/config.py` | 阈值集中: SNR≥2.5/min_effect_size/FDR 档位/consensus/QC/bootstrap-seed |
| Schema | `analyse/schemas.py` | ExperimentRecord/AttributionRecord/StatisticalEvidence/… + Evidence 标签 |
| 计划 | `analyse/plans.py` | AnalysisPlan → Validator (selected/available/status) → ExecutionPlan/status json |
| 编排 | `analyse/pipeline.py` | `run_analysis()`; 任务状态机 pending→completed/failed/unavailable/skipped |
| 注册 | `analyse/registry.py` | 任务目录 (新增分析=注册, GUI 零改动) |
| 数据 | `analyse/data/` | 统一实验表加载 (metrics_tables 优先, legacy 目录扫描适配) + 一致性校验 |
| 统计 | `analyse/stats/` | Δ+paired-baseline / BH-FDR / bootstrap CI / permutation (runner 待挂载; 包名避开标准库 statistics) |
| 归因 | `analyse/attribution/` | whitelist 字段 → 统一 attribution 表 (7 方法 × 位置通道) |
| 环境效应 | `analyse/environment/` | 条件增量 / 主效应 (同 seed cohort 配对) |
| 细胞系 | `analyse/cellline/` | context 一致性 / 跨细胞系汇总 |
| 证据 | `analyse/evidence/` | Evidence Strength 标签 / matrix + Tier / 受控假设语言 |
| 报告 | `analyse/reports/` | summary/0X_*.md 生成 |
| 图形 | `analyse/visualization/` | render_all(统一表) → figures/ 分主题 PNG |

铁律:
1. **只读训练产物**: 全链路无写训练目录代码; 训练产物变更是训练端职责 (预测/特征导出的浮点
   改动必须先在训练端验证, 见 docs/PERF_REPORT.md)。
2. **术语隔离**: effect / importance(attribution) / statistical evidence 三层标签互不冒充;
   SNR 永不称为 p 值; FDR 只作用于真检验的 family。
3. **配对基线**: 任何 Δ 统计只在同一 (split, cell_line, model, random_seed) cohort 内。
4. **不伪造**: 未实现/数据不足 → 状态 unavailable + reason; 无假设证据 → "No current evidence"。

## 3. 执行状态机 (三层状态)

```text
selected (用户要什么, AnalysisPlan)
  × available (数据/能力支持吗, validate_analysis_plan)
  → status (实际: pending → completed | failed | unavailable | skipped)
```

- 选中且 available → 执行; 成功 completed, 异常 failed (+reason 进 status json)。
- 未选中 → skipped; 选中但缺能力/依赖 → unavailable (+reason, 绝不退化为空结果)。
- 当前 build 的 unavailable: motif_discovery / bootstrap / hypothesis_testing / fdr_correction /
  environment ANOVA / Shapley runner (接口与注册已就绪, runner 属 roadmap)。

## 4. 阶段产物清单 (本 build 全绿, 1344 真实批)

| 阶段 | tables/ | summary/ | figures/ |
|---|---|---|---|
| qc | experiment_table.csv, metric_inconsistency.csv, anomaly_report.csv | 00_overview, 01_data_quality, 08_anomaly_report | — |
| prediction | prediction_summary.csv, loco_performance.csv | 02_prediction_generalization | 02_prediction/*.png |
| environment | environment_conditional_delta_r2.csv, environment_main_effects.csv | 03_environment_effects | 03_environment/*.png |
| attribution | attribution_summary.csv (287k 行) | 04_sequence_motifs | 04_sequence/*.png (7 方法) |
| cellline | cellline_effects.csv | 05_cellline_heterogeneity | 05_cellline/*.png |
| evidence | evidence_matrix.csv | 06_evidence_integration, 07_biological_hypotheses | 06_evidence/*.png |

执行元数据: `analysis_plan.json` (计划快照, 复现) / `analysis_status.json` (GUI 状态源) /
`execution_log.json` (executed 字典 + figures 清单)。

## 5. 数值稳定性护栏

- `|ΔR²| >= unstable_effect_threshold (10.0)` 的上下文不进证据矩阵
  (真实批: 28 行发散线性上下文被隔离; 不删除实验, 见 08_anomaly_report.md)。
- Context-conflicting (方向在细胞系间冲突) → 证据 Inconclusive。
- bootstrap/permutation 固定 seed (2024/42) 保证 CI/置换可复现。
