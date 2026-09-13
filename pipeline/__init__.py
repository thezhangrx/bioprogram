"""平台共享编排层（向导与网页工作台共用）。

导出 ``PipelineContext`` / ``STEPS`` / ``list_steps`` / ``build_command`` 等，
详见 ``pipeline/steps.py`` 的模块文档。
"""
from .steps import (  # noqa: F401
    SCHEMA, CATEGORY_ANALYSIS, CATEGORY_DATA, CATEGORY_DELIVERABLE, CATEGORY_TRAIN,
    PipelineContext, StepSpec, STEPS, STEP_INDEX, build_command, get_step, list_steps,
    resolve_order, step_status,
)

__all__ = [
    "SCHEMA", "PipelineContext", "StepSpec", "STEPS", "STEP_INDEX",
    "build_command", "get_step", "list_steps", "resolve_order", "step_status",
    "CATEGORY_DATA", "CATEGORY_TRAIN", "CATEGORY_ANALYSIS", "CATEGORY_DELIVERABLE",
]
