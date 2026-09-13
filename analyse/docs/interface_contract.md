# analyse — 接口契约 (Interface Contract)

> 消费者 (未来 GUI/CLI/笔记本) 与本引擎之间的稳定接口。分析侧承诺:
> 只读训练产物、分层状态、机器可读产物、术语纪律。契约版本随 engine_version。

## 1. 入口 (分析请求)

```bash
python -m analyse.pipeline --batch-dir <batch_dir> --output <out_dir> [--analysis-plan plan.json]
```

- `--batch-dir`: 训练结果批次目录 (含 summary/metrics_tables/all_experiments.csv,
  可带 legacy 实验子目录)。
- `--output`: 默认 `<batch>/analyse_out`。输出目录结构固定:
  `tables/ summary/ figures/ analysis_plan.json analysis_status.json execution_log.json`。
- `--analysis-plan`: 可选; 缺省 = `default_plan()` (全选已实现项)。失败/不合法 → 拒绝并报 reason,
  引擎不改写用户 plan 之外的分析范围。

## 2. AnalysisPlan JSON (输入 schema)

```json
{
  "plan_version": "1.0",
  "run_qc": true,
  "run_prediction_analysis": true,
  "environment":   {"enabled": true,  "conditional_effect": true, "main_effect": true,
                    "interaction": false, "shapley": false, "anova": false},
  "sequence":      {"enabled": true,  "position_attribution": true, "ism": true,
                    "motif_discovery": true, "motif_enrichment": false},
  "cell_line":     {"enabled": true,  "heterogeneity": true, "consistency": true, "interaction": false},
  "statistics":    {"bootstrap": true, "hypothesis_testing": true, "fdr_correction": true},
  "evidence":      {"cross_model": true, "evidence_integration": true, "hypothesis_generation": true}
}
```

任务 id 全集 (registry/validator 输出): `qc, prediction, environment_conditional_effect,
environment_main_effect, environment_anova, environment_shapley, sequence_attribution,
cnn_ism, motif_discovery, motif_enrichment, cellline_heterogeneity, bootstrap,
hypothesis_testing, fdr_correction, evidence_integration, hypothesis_generation`。

## 3. analysis_status.json (输出 schema, GUI 状态源)

```json
{
  "engine_version": "0.1.0",
  "batch": "<batch_dir>",
  "completed_at": "ISO-8601 (UTC)",
  "config": {"attribution": {...}, "statistical": {...}, "consensus": {...}, "qc": {...},
             "bootstrap_n": 2000, "bootstrap_seed": 2024, "permutation_n": 1000,
             "permutation_seed": 42},
  "tasks": [
    {"task_id": "qc", "selected": true, "available": true, "status": "completed",
     "reason": "", "completed_at": "..."}
  ]
}
```

状态枚举 (三层): selected / available / status;
status ∈ pending|running|completed|failed|skipped|unavailable。
约定: skipped=未选中; unavailable=选中但缺能力/依赖 (reason 必填); failed=执行异常 (reason 必填)。

## 4. 表格 schema (tables/, CSV 首行即列名)

| 文件 | 关键列 | 配对键/说明 |
|---|---|---|
| experiment_table.csv | model,split_type,cell_line,environment,random_seed,n_train,n_valid,n_test,R2,RMSE,MAE,Pearson,Spearman,MSE,run_name | 统一表 (metrics 大写, ids 小写规范化) |
| metric_inconsistency.csv / anomaly_report.csv | anomaly_type,row,experiment,flags,delta_r2,delta_rmse | 空则仅表头 |
| prediction_summary.csv | 按 (model, split, cell…) 的均值±std | 与 LOCO 同 cohort |
| environment_conditional_delta_r2.csv | split_type,cell_line,model,random_seed,environment,delta_r2,delta_rmse,… | 相对同 cohort sequence 基线 |
| environment_main_effects.csv | model,environment,main_r2_delta,… (含 cell 行) | 条件增量再平均 |
| attribution_summary.csv | feature,channel,position,model,architecture,split_type,cell_line,environment,method,importance,snr,effect,attention_entropy,source_file | position 1-based; 不做跨方法 FDR |
| cellline_effects.csv | model,factor,context_label,context_ratio,… | 标签: Context-consistent/dependent/conflicting |
| evidence_matrix.csv | feature,coverage,concordance,overall_effect,evidence_tier,unstable_rows_excluded,… | tier: Tier1/2/3/Inconclusive/No current evidence |

## 5. 报告文件 (summary/, 人类可读; 编号=分析阶段)

`00_overview` `01_data_quality` `02_prediction_generalization` `03_environment_effects`
`04_sequence_motifs` `05_cellline_heterogeneity` `06_evidence_integration`
`07_biological_hypotheses` `08_anomaly_report` — 均 UTF-8 Markdown, 表为管道表。

## 6. 证据语言契约 (evidence/hypothesis.py)

- Effect 层: "增加/减少 X (±Δ)"、"与 … 正/负相关"。
- 标签: coverage≥2 → Convergent evidence; 方向一致率≥80% → Directionally consistent;
  细胞系: Context-consistent/dependent/conflicting; 冲突或 CI 跨 0 → Inconclusive。
- **禁用**: "证明无关/无作用/无显著 (SNR 语境)/statistically significant (attribution 语境)"。
  → 用 "No current evidence"。
- Tier1/2/3 定义 (Evidence Tier): Tier1=强效应×多模型×方向一致 (可进入结论);
  Tier3=单模型弱提示; 均需 hypothesis_generation 用受控语言 (suggests/supports/candidate)。

## 7. 统计契约 (stats/)

- paired baseline: 同 (split, cell_line, model, random_seed) 才可差; 混合 seed 间永不相减。
- BH-FDR 单 family 使用 (regression p 集合 / enrichment p 集合各成 family)。
- bootstrap: percentile CI 与 paired-difference CI; fixed seed 2024。
- permutation: 效应方向置换检验 (fixed seed 42); ANOVA/Shapley runner 就绪前状态 unavailable。

## 8. 兼容/迁移契约

- `analyse.visualization` 包遮蔽旧同名模块; 通过 PEP 562 `__getattr__` 惰性桥接
  `generate_all_visualizations` (训练流程 backend_runner Step6 用法不变; 新代码用 `render_all`)。
- 引擎绝不 import 训练模块 (src/, predict.py); legacy analyse/*.py 由训练端调用, 引擎不依赖。
