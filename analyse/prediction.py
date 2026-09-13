"""analyse.prediction — 预测/泛化性能分析 (只读统一表)。"""
from __future__ import annotations

from typing import Dict

import pandas as pd

METRICS = ["R2", "MAE", "RMSE", "Pearson", "Spearman"]


def performance_by_model_split(table: pd.DataFrame) -> pd.DataFrame:
    """模型 × split 的指标均值/标准差与实验数。"""
    cols = ["model", "split_type"] + METRICS
    cols = [c for c in cols if c in table.columns]
    agg = table.groupby(["model", "split_type"], dropna=False)[
        [c for c in METRICS if c in table.columns]
    ].agg(["mean", "std"]).reset_index()
    agg.columns = ["_".join(str(x).strip("_") for x in c).strip("_") if isinstance(c, tuple)
                   else str(c) for c in agg.columns]
    n = table.groupby(["model", "split_type"], dropna=False).size().rename("n_experiments")
    return agg.merge(n, on=["model", "split_type"], how="left")


def loco_performance(table: pd.DataFrame) -> pd.DataFrame:
    """LOCO (split='all' 留一细胞系跨域) 泛化表。"""
    sub = table[table["split_type"].str.lower() == "all"].copy()
    if sub.empty:
        return pd.DataFrame()
    cols = ["model", "cell_line"] + [c for c in METRICS if c in sub.columns]
    sub = sub.groupby(["model", "cell_line"], dropna=False)[
        [c for c in METRICS if c in sub.columns]
    ].mean().reset_index()
    n = table[table["split_type"].str.lower() == "all"].groupby(
        ["model", "cell_line"], dropna=False).size().rename("n_experiments")
    return sub.merge(n, on=["model", "cell_line"], how="left")
