# analyse — CRISPR 编辑效率影响因素发现与证据整合分析引擎

> 状态: Phase 1–7 已落地并在 1344 组真实批全链路验证 (31 项单测全绿)。
> 引擎对训练系统 (src/, predict.py, Input/) **只读**; 训练流程未因分析需求改动。

## 1. 职责
把 1344 组 sgRNA 编辑效率实验结果转化为证据链:
Data QC → Prediction/Generalization → Environment Factor → Sequence/Motif →
Cell-line Context → Evidence Integration → Biological Hypothesis。

## 2. 术语纪律 (核心红线)
- **Effect**: ΔR²/ΔMAE/ΔRMSE/系数/ISM effect/enrichment effect
- **Importance/Attribution**: SHAP/IG/ISM/Attention/Gain (非 p 值; 本引擎 7 方法白名单)
- **Statistical Evidence**: 仅来自明确检验/CI (regression p/FDR, ANOVA, enrichment p/FDR,
  permutation/bootstrap)
- SNR≥2.5 + 足够效应量 → "Strong attribution", **绝不称为 statistical significance**;
  对 attribution 做检验必须先建 permutation/bootstrap null, 再 FDR
- Evidence Tier: Tier1/2/3 / Inconclusive / No current evidence (无 "证明无关" 表述)

## 3. 模块结构
```text
analyse/
├── __init__.py          版本
├── config.py            SNR/FDR/consensus/QC 阈值集中配置 (seed 固定可复现)
├── schemas.py           统一记录 + Evidence 标签
├── plans.py             AnalysisPlan / Capabilities / Validator (selected/available/status)
├── registry.py          分析任务注册表 (新增方法=注册, 不改 GUI)
├── pipeline.py          run_analysis() 编排入口 (python -m analyse.pipeline)
├── data/                loaders 统一实验表 + validation 同 cohort 一致性
├── stats/               effect_size / multiple_testing(BH-FDR) / bootstrap / hypothesis_tests (避开标准库同名)
├── environment/         条件增量 / 主效应 (同 seed 配对, 跨 seed 永不配对)
├── attribution/         whitelist 字段 → 统一 attribution 表 + motif 摘要
├── cellline/            context 一致性 / 汇总 (Context-consistent/dependent/conflicting)
├── evidence/            Strength 标签 / matrix+Tier / 受控假设语言
├── reports/             summary/0X_*.md 生成
├── visualization/       render_all(统一表) → figures/<02..06>/ (300dpi)
├── docs/                workflow_architecture / interface_contract / code_cleanup_report
└── tests/               unittest 31 项
```

## 4. 当前实现范围 (全部经 1344 真实批验证)
- 统一实验表 (1344 行全部有效) + 同 seed 配对一致性校验 (0 矛盾) + anomaly_report.csv
- prediction (model×split×cell 汇总 + LOCO) / environment 条件 ΔR² + 主效应
- attribution 统一表 (287k 行: linear/xgb/mlp/cnn/transformer 白名单方法) + motif md
- cell-line 一致性标签 + evidence matrix (Tier; 28 个发散线性上下文按阈值隔离, 不删实验;
  Context-conflicting → Inconclusive) + 受控生物假设
- summary/00–08 md + tables/ CSV + figures/ 15 PNG + plan/status/execution_log JSON
- 未实现任务 (motif discovery/ANOVA/Shapley/bootstrap runner 等) → unavailable+reason,
  绝不伪造; 计划/接口/注册已就绪

## 5. CLI 与测试
```bash
python -m analyse.pipeline --batch-dir <batch> --output <out>
python -m analyse.pipeline --batch-dir <batch> --analysis-plan plan.json
python -m unittest discover -s analyse/tests        # 31 tests, OK
```

## 6. 遗留脚本与兼容
- analyse/ 根目录 5 个旧脚本 (collect_results/anomaly_treatment/importance_extraction/
  visualization/data_QC) 由训练流程 Input/backend_runner.py 与向导调用 — 保留原位;
  引擎不依赖它们 (单向消费其产物)。
- `analyse.visualization` 包遮蔽旧同名模块 → PEP 562 兼容桥透传
  `generate_all_visualizations` (backend_runner Step6 语义不变), 新代码一律 `render_all`。
- 迁移/清理清单与死码审计: 见 docs/code_cleanup_report.md。

## 7. 路线图完成度
- Phase 1 现状扫描/统一 schema            ✅
- Phase 2 数据/统计/计划/三层状态校验      ✅
- Phase 3 QC/prediction/environment runner ✅ (ANOVA/Shapley runner 注册待挂载)
- Phase 4 attribution 统一抽取 + motif    ✅
- Phase 5 cell-line + evidence matrix/Tier ✅
- Phase 6 visualization + summary 00–08 + CLI 文档 ✅
- Phase 7 docs (architecture/interface/cleanup) + 旧文件迁移说明 + dead-code audit ✅
- 待续 (需用户决策/训练端配合): motif discovery/enrichment runner, ANOVA/Shapley/
  bootstrap/hypothesis runner 挂载, CNN ISM 突变效应接线 (classify_mutation_effect)。
