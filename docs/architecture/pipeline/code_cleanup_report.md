# analyse — 代码清理报告 (Code Cleanup Report)

> 面向 spec "Phase 7: code-cleanup report / dead-code audit / 旧文件迁移说明"。
> 审计方法: AST 扫描 analysis/ 全部 .py (47 个文件, ~7.9k 行; 引擎新代码 ~3.3k 行),
> 统计跨模块引用 + 人工分类。日期: 以 git 记录为准。

## 1. 遗留脚本现状 (5 个旧文件, 由训练端调用 — 迁移而非删除)

| 文件 | 行数 | 当前角色 | 谁在调用 | 与引擎的关系 |
|---|---|---|---|---|
| analysis/collect_results.py | 441 | 训练后指标汇总 (metrics_tables) | app/desktop/backend_runner.py Step3 | 引擎 loaders 只读其结果文件, 不 import |
| analysis/anomaly_treatment.py | 489 | 两级异常检测 + anomaly_report.md (训练报告) | app/desktop/backend_runner.py Step4 | 引擎 validation/integration 独立实现同语义; 08_anomaly_report 引用其"数据级报告"说明 |
| analysis/importance_extraction.py | 907 | 生信稳健性 md + key_regulatory_biomarkers.csv | backend_runner Step5; scripts/make_notebook.py | 引擎 extractors 的产物 (feature_importance/) 是输入 |
| analysis/visualization.py | 959 | V6 显著性热图/环境树图 (训练报告) | backend_runner Step6 (内部函数惰性 import) | **同名遮蔽**: 引擎包 analysis/visualization/ 遮蔽该 .py |
| analysis/data_QC.py | 1768 | 向导 Step2 无头质控 (训练侧, 用户绑定任务) | GUI/向导 (独立部署) | 不冲突; 引擎 QC 是批次级校验 |

处理: **保留原位** — 全部被训练端或用户向导引用, 删除即破坏训练流程 (红线)。
同包名冲突仅发生在 visualization: 引擎 `visualization/__init__.py` 的 PEP 562
`__getattr__` 惰性加载旧模块并透传 `generate_all_visualizations` → backend_runner Step6
导入语义不变 (已实测通过), 新代码统一 `render_all`。迁移完成条件 (未来): 训练端 Step6 切换后,
旧 5 文件移至 `tools/legacy_analysis/` 归档, 引擎包移除桥接。

## 2. Dead-code audit (引擎侧, 跨模块 0 引用项)

| 符号 | 判定 | 说明 / 处置 |
|---|---|---|
| evidence/rules.classify_mutation_effect | **真孤儿** | ISM 突变效应标签接口, 无调用方 (extractors 未挂载 ISM 效应标签)。保留为 roadmap 接口 (schemas EvidenceStrength.STRONG_MUTATION_EFFECT 配套), 报告标注待 CNN ISM runner 接线; 不建议现在删 (公开 API) |
| environment.incremental_effect.compute_pair_interactions | 保留 (roadmap) | plan 字段 environment.interaction=False, 交互 runner 未挂载; 函数有独立单元测试 |
| stats/{bootstrap,hypothesis_tests,multiple_testing,effect_size} | 保留 (roadmap) | pipeline 中 bootstrap/hypothesis_testing/fdr_correction 任务 registered 且选中 → 状态 unavailable(reason), 绝不伪造; 模块有单测 |
| registry.py (3 公开函数) | 保留 (插件入口) | GUI 扩展点; 由 plans/validator 逻辑支持 |
| schemas 各 dataclass/Enum | 保留 (公开 API) | 测试直接引用; 序列化进 status/plan |
| data.loaders.iter_experiment_records / resolve_batch_dir | 保留 | record 级 API + 内部工具 (load_experiment_table 依赖 resolve_batch_dir) |
| markdown_report._md_table / attribution/extractors._* | 保留 | 模块内私有工具, 非跨模块死码 |
| visualization/__init__.__getattr__ / _load_legacy_viz_module | 保留 (兼容桥) | 见 §1; 迁移完成后随桥接一并删除 |

审计未发现引擎侧可安全删除的跨模块死码: 唯一"无引用"的公开函数
(classify_mutation_effect) 属计划内接口, 删除会造成 API 断裂而非清理。5 个旧文件
0 import 自引擎 (引擎是旧脚本产物/入口的单向消费者), 交叉污染不存在。

## 3. 重复实现说明 (有意为之, 边界清晰)

| 主题 | 旧文件 (训练端) | 引擎 (analysis/) | 为何不共用 |
|---|---|---|---|
| 指标同号矛盾 | anomaly_treatment (两级: 实验+数据) | data/validation.validate_metric_consistency (同 cohort/同 seed 配对) | 旧版服务于训练中断言, 引擎版按 paired-baseline 纪律重写 (mixed 多 seed 不跨 seed 比) |
| 发散实验 | anomaly_treatment.filter / collect_results.filter_valid | evidence/integration 不稳定阈值隔离 (不进矩阵, 不删实验) | 引擎采用"隔离+标注"而非删除, 语义升级 |
| 位置/通道解析 | visualization.parse_feature_position_channel | attribution/extractors._parse_position_channel | 引擎统一 1-based position + whitelist; 两者已单测对齐 |
| 质控 | data_QC.py (训练前用户数据) | pipeline qc 任务 (训练后批次) | 生命周期两端, 不做合并 |

共用会造成引擎依赖训练端代码 — 违反只读/单向依赖红线, 故刻意并行, 各有单测。

## 4. 已完成的清理 (本报告周期)

1. 删除引擎包内重复/错误位置文件: `core/xai/importance/xai_importance.py` 恢复训练端唯一位置 (曾误移
   analysis/), 引擎侧副本删除 → 训练导出不再 ModuleNotFoundError。
2. 修正 loaders 列大小写处理: 全部小写曾致 R² NaN (valid_count=0) → ids 小写规范化、
   metrics 保大写, 1344 行全部有效。
3. validation 空结果固定写表头 → metric_inconsistency.csv/anomaly_report.csv 空态可机器读。
4. evidence matrix 补 pd import / unstable 隔离 + context-conflict → Inconclusive;
   假设语言改为受控关联表述 (不再由 matrix 强推无依据机制结论)。
5. 本周期: visualization 分主题包 + render_all 入 pipeline (15 图, PNG 校验通过);
   PEP 562 兼容桥修复旧 visualization.py 遮蔽回归; pipeline execution_log 记录 figures
   (Path.relative_to 修正); 新增 test_phase6 端到端产物测试。
6. 遗留可清理项: analysis/README "重构进行中" 头注已随本文档周期移除 (见 §5 提交清单);
   __pycache__ 不入库。

## 5. 建议后续清理 (不阻塞当前交付)

- [ ] 训练端 backend_runner Step6 切换 render_all 之后: 归档 analysis/{visualization.py,
  collect_results.py, importance_extraction.py, anomaly_treatment.py} → tools/legacy_analysis/
  (data_QC.py 随用户向导任务另行处置)。
- [ ] CNN ISM runner 接线 classify_mutation_effect 并补端到端测试。
- [ ] 真实批 analysis_out 产物是否入库由用户定 (建议只入库 schema/tests/docs 与 sample 产物)。
