"""cellline_plots — feature × cell-line 效应与一致性。"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analyse.visualization.core import save_figure


def render(cellline_df: pd.DataFrame, out_dir: Path) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list = []
    if cellline_df.empty or not {"factor", "model", "context_label"}.issubset(cellline_df.columns):
        return paths

    if "context_label" in cellline_df.columns:
        counts = cellline_df["context_label"].value_counts()
        if not counts.empty:
            fig, ax = plt.subplots(figsize=(7, 4))
            counts.plot(kind="bar", ax=ax, color="#5b8def")
            ax.set_title("Context consistency label counts")
            ax.set_xticklabels(ax.get_xticklabels(), rotation=25)
            paths.append(save_figure(fig, out_dir / "context_consistency.png"))

    # 每个 factor 的各 cell-line effect (跨 model 平均)
    effect_cols = [c for c in cellline_df.columns if c.startswith("effect_")]
    if effect_cols:
        long = cellline_df.melt(id_vars=["factor", "model"], value_vars=effect_cols,
                                var_name="cell_line", value_name="effect")
        long["cell_line"] = long["cell_line"].str.replace("effect_", "", regex=False)
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.stripplot(data=long, x="factor", y="effect", hue="cell_line",
                      dodge=True, jitter=0.08, ax=ax, alpha=0.75)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_title("feature × cell-line effects")
        ax.legend(fontsize=8)
        paths.append(save_figure(fig, out_dir / "feature_cellline_effect.png"))
    return paths
