# summary/ 产物溯源表 —— 每个文件由哪个程序生成

批次示例：`results/batches/batch_20260909_full/`
整理时间：2026-09-13（路径迁移当日）

> **路径变更**：分析引擎 `analysis/pipeline.py` 的产物根由 `<batch>/analyse_out/` 改为 **`<batch>/summary/`**，
> 报告子目录 `summary/` 改为 **`reports/`**（避免出现 `summary/summary/`）。
> 旧目录已整体迁移并删除，历史文件见 §5。

---

## 0. 目录职责总览

| 子目录 / 文件 | 由谁写 | 入口命令 |
|---|---|---|
| `summary/metrics_tables/` | `analysis/collect_results.py` | `python -m analysis.collect_results --batch-name <batch>` |
| `summary/feature_importance/` | `analysis/importance_extraction.py` | GUI 流水线步骤 `importance_extraction` |
| `summary/plots/` | `analysis/panorama.py`（全景图，含显著性掩码热图/增量树） | `python analysis/panorama.py --batch-dir <batch>` |
| `summary/anomaly_report.md` | `analysis/anomaly_treatment.py` | GUI 流水线步骤 `anomaly_treatment` |
| `summary/赛道二_results.csv` | `workflows/prediction/predict.py`（候选预测） | `python workflows/prediction/predict.py ...` |
| `summary/ultimate/` | `workflows/prediction/predict.py` | 同上 |
| **`summary/tables/`** | **`analysis/pipeline.py`（分析引擎）** | `python -m analysis.pipeline --batch-dir <batch>` |
| **`summary/reports/`** | 同上 | 同上 |
| **`summary/figures/`** | 同上 | 同上 |
| **`summary/*.json`** | 同上 | 同上 |

**只有加粗的三行 + 三个 json 来自分析引擎**；其余是早期单点脚本的产物，两者互不覆盖
（唯一的历史重叠见 §5）。

---

## 1. `summary/tables/`（27 个 CSV，全部由 `analysis/pipeline.py` 调度）

写入点是 `artifacts.tables_dir / "<name>"`；"真实计算"列给出实际的统计实现模块。

| 文件 | 写入点 | 真实计算函数 | 统计单位 / 口径 |
|---|---|---|---|
| `experiment_table.csv` | `analysis/pipeline.py:103` | `analysis/data/loaders.py::load_experiment_table` + `capabilities_from_table` | 每 run 一行（1344 行） |
| `metric_inconsistency.csv` | `analysis/pipeline.py:107` | `analysis/data/validation.py::validate_metric_consistency` | 每 run 一行（校验标记） |
| `prediction_summary.csv` | `analysis/pipeline.py:176` | `analysis/prediction.py::performance_by_model_split` | split × cell × model |
| `loco_performance.csv` | `analysis/pipeline.py:177` | `analysis/prediction.py::loco_performance` | 留出细胞系（滤 `abs(R²)<10`） |
| `environment_conditional_delta_r2.csv` | `analysis/pipeline.py:187` | `analysis/environment/incremental_effect.py::compute_conditional_increments` | 边（父→子环境）配对 ΔR² |
| `environment_main_effects.csv` | `analysis/pipeline.py:202` | `analysis/environment/incremental_effect.py::compute_main_effects` | 因子水平（模型等权均值） |
| `bootstrap_results.csv` | `analysis/pipeline.py:217` | `analysis/stats/tasks.py::bootstrap_main_effects` | 模型级 bootstrap（n=7 配置） |
| `bootstrap_main_effects.csv` | `analysis/pipeline.py:221` | `analysis/stats/tasks.py::edge_ci_table` / `bootstrap_main_effects` | 因子水平 CI |
| `bootstrap_cellline_effects.csv` | `analysis/pipeline.py:225` | `analysis/stats/tasks.py::bootstrap_cellline_effects` | 细胞系级 CI |
| `environment_bootstrap.csv` | `analysis/pipeline.py:228` | `analysis/stats/tasks.py::bootstrap_environment_edges` | 边级 CI（逐样本配对） |
| `permutation_results.csv` | `analysis/pipeline.py:250` | `analysis/stats/tasks.py::permutation_*` + `apply_fdr` | sign-flip 置换 + BH-FDR（族 `test_type\|split\|cell\|model`） |
| `anova_results.csv` | `analysis/pipeline.py:267` | `analysis/stats/tasks.py` 区组 ANOVA（statsmodels） | 因子；**不做 FDR**（设计如此） |
| `attribution_summary.csv` | `analysis/pipeline.py:329` | `analysis/attribution/*`（ISM/IG/TreeSHAP 解析） | 位点 × 通道聚合 |
| `motif_candidates.csv` | `analysis/sequence/motif/pipeline.py:294` | 同上模块 `run_and_write` | motif（seqlet→聚类→consensus） |
| `motif_instances.csv` | `analysis/sequence/motif/pipeline.py:303` | 同上 | motif × 出现实例 |
| `motif_enrichment.csv` | `analysis/sequence/motif/pipeline.py:307` | 同上（超几何 + BH） | motif |
| `motif_consistency.csv` | `analysis/sequence/motif/pipeline.py:311` | 同上 | motif × 模型 |
| `motif_evidence.csv` | `analysis/sequence/motif/pipeline.py:315` | 同上 | motif（证据分级） |
| `cellline_effects.csv` | `analysis/pipeline.py:403` | `analysis/environment/*` 细胞系异质性 | 细胞系 × 环境 |
| `evidence_matrix.csv` | `analysis/pipeline.py:428` | `analysis/evidence/integration.py::environment_evidence_matrix`（唯一 Tier 权威实现 `classify_evidence_tier`） | 环境因子（三闸门） |
| `importance_vs_delta_r2.csv` | `analysis/visualization/importance_delta.py:649` | `importance_delta.py::build_importance_delta_table` | 重要性 × ΔR² 二维证据点 |
| `environment_nodes.csv` | `analysis/environment/factorial_dag.py:561` | `build_environment_nodes` | 2⁴ 因子格点（16 节点 × split × cell × model） |
| `environment_edges.csv` | `analysis/environment/factorial_dag.py:562` | `build_environment_edges`（+ `edge_ci_table` 合并 CI 列） | 条件边（32 边/格） |
| `environment_ablation.csv` | `analysis/environment/factorial_dag.py:563` | 同上（消融方向） | 消融边 |
| `environment_interactions.csv` | `analysis/environment/factorial_dag.py:564` | `build_environment_interactions` | 因子对交互 |
| `environment_dag_report.csv` | `analysis/environment/factorial_dag.py:565` | 同上（一致性汇总） | split × cell × model |
| `anomaly_report.csv` | `analysis/pipeline.py:487,491` | 批次级异常检测（发散 / 缺失 / 不一致） | 每异常一行 |

---

## 2. `summary/reports/`（15 个文件，全部由 `analysis/pipeline.py` 及其子模块写）

| 文件 | 写入点 | 内容来源 |
|---|---|---|
| `00_overview.md` | `analysis/pipeline.py:478` | `analysis/reports/markdown_report.py::build_overview_md` |
| `01_data_quality.md` | `analysis/pipeline.py:492` | 数据 QC（序列合法性、标签分布、覆盖） |
| `02_prediction_generalization.md` | `analysis/pipeline.py:498` | `build_prediction_md`（含 mixed/LOCO 泛化） |
| `03_environment_effects.md` | `analysis/pipeline.py:501` + `analysis/environment/factorial_dag.py:515::append_dag_section` | `build_environment_md` + DAG 报告段落 |
| `04_sequence_motifs.md` | `analysis/pipeline.py:330` | 序列归因摘要（motif 关闭时的版本） |
| `04_sequence_and_motifs.md` | `analysis/sequence/motif/pipeline.py:609::append_motif_section` | motif 发现完整报告（开启时生成） |
| `05_cellline_heterogeneity.md` | `analysis/pipeline.py:404` | 细胞系异质性（`Context-conflicting` 判定） |
| `06_evidence_integration.md` | `analysis/pipeline.py:429` | 环境证据矩阵与 Tier 结论 |
| `07_biological_hypotheses.md` | `analysis/pipeline.py:448` | 由证据矩阵生成假设清单 |
| `08_anomaly_report.md` | `analysis/pipeline.py:494` | 异常检测（发散 run 等） |
| `environment_dag_report.md` | `analysis/environment/factorial_dag.py:566` | 因子 DAG 一致性报告 |
| `07_importance_vs_delta_r2.md` | `analysis/visualization/importance_delta.py:653` | 重要性/ΔR² 二维证据报告 |
| `importance_vs_delta_r2.md` | `analysis/visualization/importance_delta.py:655` | 同上（别名/兼容名） |
| `importance_metric_selection.md` | `analysis/visualization/importance_delta.py:657` | 重要性口径选择说明 |
| `importance_delta_r2_summary.json` | `analysis/visualization/importance_delta.py:658` | 上述报告的机读摘要 |

---

## 3. `summary/*.json`（分析引擎状态，3 个）

| 文件 | 写入点 | 用途 |
|---|---|---|
| `analysis_plan.json` | `analysis/pipeline.py:474`（`plan.save`） | 本次运行的 AnalysisPlan（哪些任务开关打开） |
| `analysis_status.json` | `analysis/pipeline.py:475`（`ep.save_status`） | 17 个任务的 selected/available/status/artifact |
| `execution_log.json` | `analysis/pipeline.py:510` | 逐任务执行记录 + 产物路径（含图计数） |

---

## 4. `summary/figures/`（304 张 PNG）

| 子目录 | 数量 | 渲染代码 |
|---|---|---|
| `03_environment/` | 254 | `analysis/visualization/factorial_dag.py`（`render_factorial_dag` / `render_conditional_delta_r2` / `render_ablation_delta_r2` / `render_environment_interactions`）；入口 `analysis/pipeline.py:310` 指定 `figures_dir/"03_environment"` |
| `04_motif/` | 26 | `analysis/sequence/motif/pipeline.py:404`（`out_dir = figures_dir/"04_motif"`） |
| `07_evidence/` | 11 | `analysis/visualization/importance_delta.py:352,516`（`figures_dir/"07_evidence"`） |
| `04_sequence/` | 7 | `analysis/visualization/__init__.py:47`（`attribution_plots.render`） |
| `02_prediction/` | 2 | `analysis/visualization/__init__.py:42`（`performance_plots.render`） |
| `05_cellline/` | 2 | `analysis/visualization/__init__.py:49`（`cellline_plots.render`） |
| `06_evidence/` | 2 | `analysis/visualization/__init__.py:51`（`evidence_plots.render`） |

---

## 5. 路径迁移与冲突处理（2026-09-13）

迁移映射：

```
analyse_out/tables/*.csv      -> summary/tables/*.csv
analyse_out/summary/*.md|json -> summary/reports/*          (子目录改名, 避免 summary/summary)
analyse_out/figures/**        -> summary/figures/**
analyse_out/*.json            -> summary/*.json
analyse_out/                  -> 已删除
```

**冲突**：`summary/tables/` 里原有 5 个 9-12 生成的同名文件，内容与引擎版不同
（例如 `environment_edges.csv` 旧 2017 行 / 新 2652 行，旧版无 bootstrap CI 列），
已备份到 **`summary/tables/_legacy_20260912_visualization/`**，未删除：

```
environment_ablation.csv  environment_dag_report.csv  environment_edges.csv
environment_interactions.csv  environment_nodes.csv
```

**冲突根因**：`analysis/panorama.py`（全景图步骤）曾把 5 个环境中间表写进 `summary/tables/`，
与分析引擎同址同名。已在源头修复——全景图现在写到 `summary/plots/_environment_tables/`，
`summary/tables/` 从此归分析引擎独占。

**未迁移/不受影响**：`summary/metrics_tables/`、`plots/`、`feature_importance/`、
`feature_importance_backup_pre8ch/`、`ultimate/`、`赛道二_results.csv`、`anomaly_report.md`、
`environment_dag_report.md`、`03_environment_effects.md` 仍由各自脚本原地生成（见 §0）。

---

## 6. 复现命令

```bash
# ① 指标表（summary/metrics_tables/）
python -m analysis.collect_results --batch-name batch_20260913_groupaware

# ② 分析引擎（summary/{tables,reports,figures} + 3 个 json）—— 默认输出即 <batch>/summary
python -m analysis.pipeline --batch-dir results/batch_20260913_groupaware

# ③ 全景图（summary/plots/，含自己的中间表 summary/plots/_environment_tables/）
python analysis/panorama.py --batch-dir results/batch_20260913_groupaware
```

> 若需自定义输出目录：`--output <dir>`，其下固定生成 `tables/ reports/ figures/`。
