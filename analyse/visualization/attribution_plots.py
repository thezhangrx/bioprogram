"""attribution_plots — 位置归因热图 (per method; magnitude)。"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analyse.visualization.core import save_figure

CHANNEL_ORDER = ["A", "C", "G", "T", "CTCF", "Dnase", "H3K4me3", "RRBS"]


def render(attribution_table: pd.DataFrame, out_dir: Path) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list = []
    if not {"method", "channel", "position", "importance"}.issubset(attribution_table.columns):
        return paths
    work = attribution_table.dropna(subset=["channel", "position", "importance"]).copy()
    if work.empty:
        return paths
    work["channel"] = work["channel"].astype(str).str.upper()
    work = work[work["channel"].isin(CHANNEL_ORDER)]
    for method, sub in work.groupby("method", dropna=False):
        pivot = sub.pivot_table(index="channel", columns="position",
                                values="importance", aggfunc="mean")
        pivot = pivot.reindex([c for c in CHANNEL_ORDER if c in pivot.index])
        cols = sorted(pivot.columns)
        pivot = pivot[cols]
        if pivot.empty or pivot.notna().sum().sum() == 0:
            continue
        fig, ax = plt.subplots(figsize=(11, max(3, 0.55 * pivot.shape[0] + 1)))
        sns.heatmap(pivot, cmap="YlGnBu", ax=ax, linewidths=0.4)
        ax.set_title(f"Position attribution magnitude — {method}")
        ax.set_xlabel("position (1-based)")
        paths.append(save_figure(fig, out_dir / f"position_attribution_{method}.png"))
    return paths
