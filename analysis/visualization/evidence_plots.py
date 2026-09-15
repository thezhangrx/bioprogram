"""evidence_plots — 证据矩阵/层级汇总。"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis.visualization.core import save_figure


def render(evidence_matrix: pd.DataFrame, out_dir: Path) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list = []
    if evidence_matrix.empty:
        return paths

    if "evidence_tier" in evidence_matrix.columns:
        counts = evidence_matrix["evidence_tier"].value_counts()
        if not counts.empty:
            fig, ax = plt.subplots(figsize=(8, 4))
            counts.plot(kind="bar", ax=ax, color="#8e44ad")
            ax.set_title("Evidence tier summary")
            ax.set_xticklabels(ax.get_xticklabels(), rotation=20)
            paths.append(save_figure(fig, out_dir / "evidence_tier_summary.png"))

    if {"feature", "coverage", "direction_concordance", "overall_effect"}.issubset(
            evidence_matrix.columns):
        cols = ["coverage", "direction_concordance", "overall_effect"]
        pivot = evidence_matrix.set_index("feature")[cols]
        fig, ax = plt.subplots(figsize=(max(7, 1.2 * len(pivot)), 5))
        sns.heatmap(pivot.astype(float), annot=True, fmt=".3f", cmap="viridis", ax=ax)
        ax.set_title("Evidence matrix (environment factors)")
        paths.append(save_figure(fig, out_dir / "evidence_matrix_heatmap.png"))
    return paths
