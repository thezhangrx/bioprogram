"""performance_plots — 预测/泛化图。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

from analyse.visualization.core import save_figure


def render(prediction_df: pd.DataFrame, loco_df: Optional[pd.DataFrame],
           out_dir: Path) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list = []

    if {"model", "split_type", "R2_mean"}.issubset(prediction_df.columns):
        fig, ax = plt.subplots(figsize=(10, 5))
        piv = prediction_df.pivot_table(index="model", columns="split_type",
                                        values="R2_mean")
        piv.plot(kind="bar", ax=ax, rot=30)
        ax.set_ylabel("mean R² (test cohort)")
        ax.set_title("Model performance by split type (mean R²)")
        ax.legend(title="split_type", fontsize=8)
        paths.append(save_figure(fig, out_dir / "model_performance.png"))

    if loco_df is not None and not loco_df.empty and {"model", "cell_line", "R2"}.issubset(loco_df.columns):
        fig, ax = plt.subplots(figsize=(10, 5))
        piv = loco_df.pivot_table(index="model", columns="cell_line", values="R2")
        piv.plot(kind="bar", ax=ax, rot=30)
        ax.set_ylabel("R² (LOCO held-out cell line)")
        ax.set_title("LOCO generalization (split='all')")
        paths.append(save_figure(fig, out_dir / "loco_performance.png"))
    return paths
