"""analyse — CRISPR 编辑效率影响因素发现与证据整合分析引擎。

分层职责：
    analyse.config      证据/统计/QC 阈值等集中配置
    analyse.schemas     统一数据记录与 Evidence 标签 (dataclass/Enum)
    analyse.data        批量结果只读加载、字段适配、校验 (训练系统只读)
    analyse.stats       Effect/CI/检验/FDR/Bootstrap 等规范实现 (名称避开标准库 statistics)
    analyse.evidence    Evidence Strength/Tier/一致性/假设语言规则
    analyse.plans       AnalysisPlan / Validator / ExecutionPlan / 状态
    analyse.registry    分析任务注册表 (可扩展插件入口)
    analyse.pipeline    编排入口 (GUI/CLI 只提供 AnalysisPlan)

铁律: 本包对训练系统 (src/, predict.py 等) 只读; 不反向 import 训练模块。
"""

__version__ = "0.1.0"
