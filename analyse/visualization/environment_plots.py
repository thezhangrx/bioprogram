"""environment_plots — 条件 ΔR² 热图 + 主效应。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from analyse.visualization.core import save_figure


def render(conditional_summary: pd.DataFrame, main_effects: Optional[pd.DataFrame],
           out_dir: Path) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list = []

    # 条件 ΔR² 热图: rows=加入环境, cols=背景 S (跨 cell/model 平均)
    if {"environment_added", "background", "delta_r2_mean"}.issubset(conditional_summary.columns):
        pivot = conditional_summary.pivot_table(
            index="environment_added", columns="background", values="delta_r2_mean")
        if not pivot.empty:
            fig, ax = plt.subplots(figsize=(max(8, 0.9 * pivot.shape[1]), 0.9 * pivot.shape[0] + 2))
            sns.heatmap(pivot, cmap="RdBu_r", center=0, annot=False, ax=ax,
                        linewidths=0.4)
            ax.set_title("Conditional ΔR²(e | S) (paired cohort; means across contexts)")
            ax.set_xlabel("background S")
            ax.set_ylabel("added environment e")
            paths.append(save_figure(fig, out_dir / "conditional_delta_r2_heatmap.png"))

    if main_effects is not None and not main_effects.empty and \
            {"environment", "main_r2_delta"}.issubset(main_effects.columns):
        overall = main_effects.groupby("environment", dropna=False)["main_r2_delta"] \
            .mean().sort_values()
        fig, ax = plt.subplots(figsize=(8, 0.8 * len(overall) + 1))
        colors = ["#c0392b" if v < 0 else "#27ae60" for v in overall.values]
        overall.plot(kind="barh", ax=ax, color=colors)
        ax.axvline(0, color="black", lw=0.8)
        ax.set_title("Environment main effects (mean ΔR²)")
        paths.append(save_figure(fig, out_dir / "environment_main_effects.png"))
    return paths
