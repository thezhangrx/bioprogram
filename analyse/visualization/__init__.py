"""analyse.visualization — 证据引擎图表 (分主题模块; 300dpi PNG)。

原则: 图只从统一 tables/DataFrame 重建, 不自行扫描实验目录。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from analyse.visualization.core import save_figure, style_figure  # noqa: E402
from analyse.visualization import (attribution_plots, cellline_plots,  # noqa: E402
                                   environment_plots, evidence_plots,
                                   performance_plots)


def render_all(figures_dir: str | Path,
               prediction_df: Optional[pd.DataFrame] = None,
               loco_df: Optional[pd.DataFrame] = None,
               conditional_summary: Optional[pd.DataFrame] = None,
               main_effects: Optional[pd.DataFrame] = None,
               attribution_table: Optional[pd.DataFrame] = None,
               cellline_df: Optional[pd.DataFrame] = None,
               evidence_matrix: Optional[pd.DataFrame] = None) -> list:
    """由内存中的统一表渲染全部可用图 (缺数据则跳过该主题)。"""
    out = Path(figures_dir)
    style_figure()
    rendered: list = []
    for folder in ("02_prediction", "03_environment", "04_sequence",
                   "05_cellline", "06_evidence"):
        (out / folder).mkdir(parents=True, exist_ok=True)

    if prediction_df is not None and not prediction_df.empty:
        rendered += performance_plots.render(prediction_df, loco_df, out / "02_prediction")
    if conditional_summary is not None and not conditional_summary.empty:
        rendered += environment_plots.render(conditional_summary, main_effects,
                                             out / "03_environment")
    if attribution_table is not None and not attribution_table.empty:
        rendered += attribution_plots.render(attribution_table, out / "04_sequence")
    if cellline_df is not None and not cellline_df.empty:
        rendered += cellline_plots.render(cellline_df, out / "05_cellline")
    if evidence_matrix is not None and not evidence_matrix.empty:
        rendered += evidence_plots.render(evidence_matrix, out / "06_evidence")
    return rendered


# ---------------------------------------------------------------------------
# 兼容桥 (迁移期): 旧单文件 analyse/visualization.py 与证据引擎包同名。
# 包目录会遮蔽同目录下的 .py 模块, 导致训练流程 backend_runner Step 6 的
# `from analyse.visualization import generate_all_visualizations` 失效。
# 用 PEP 562 __getattr__ 惰性加载旧模块文件并透传其函数 —— 不改训练侧代码。
# 新代码一律用 render_all; 旧入口仅作兼容, 随迁移完成移除。
# ---------------------------------------------------------------------------
_LEGACY_VIZ_FILE = Path(__file__).resolve().parent.parent / "visualization.py"
_legacy_viz_module = None


def _load_legacy_viz_module():
    global _legacy_viz_module
    if _legacy_viz_module is None:
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location("analyse._legacy_viz_module",
                                                      _LEGACY_VIZ_FILE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _legacy_viz_module = module
    return _legacy_viz_module


def __getattr__(name: str):
    if name == "generate_all_visualizations":
        return getattr(_load_legacy_viz_module(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
