"""crispr_workspace — CRISPR Scientific Workspace 本地后端 (Workflow API).

原则:
  * 只负责: 项目/配置/编排/任务启动/状态监控/日志与结果浏览接口;
    科学计算 (QC/Training/Analyse/Statistics/XAI/Reports) 一律通过
    现有引擎 (analyse.data_QC / data_digging.py / predict.py / analyse.pipeline)
    以子进程或只读接口调用 —— 本包绝不 import 训练模型代码。
  * 零第三方运行时依赖 (仅 Python 标准库), 可在 Windows/Linux CPU 直接运行;
    将来可无缝替换为 FastAPI 实现 (路由/服务分层已按此设计)。
"""
__version__ = "0.1.0"
