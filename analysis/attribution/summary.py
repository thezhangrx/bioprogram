"""analysis.attribution.summary — 统一 attribution 表 -> 04 sequence/motif 摘要。"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def top_attribution_features(table: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """每 (model, method) 按平均 |importance| 取 top-N 特征 (跨 cell/split 均值)。"""
    if table.empty:
        return pd.DataFrame()
    work = table.copy()
    work["abs_importance"] = work["importance"].abs()
    grouped = work.groupby(["model", "method", "feature"], dropna=False).agg(
        mean_abs_importance=("abs_importance", "mean"),
        mean_importance=("importance", "mean"),
        n_contexts=("feature", "size"),
    ).reset_index()
    out = []
    for (model, method), sub in grouped.groupby(["model", "method"], dropna=False):
        sub = sub.sort_values("mean_abs_importance", ascending=False).head(top_n)
        out.append(sub)
    if not out:
        return pd.DataFrame()
    return pd.concat(out, ignore_index=True)


def build_motif_summary_md(table: pd.DataFrame, top_n: int = 10) -> str:
    lines = ["# 04 Sequence Attribution & Motif Candidates\n"]
    if table.empty:
        lines.append("> 未找到可用 attribution 输出 (Unavailable)。\n")
        return "\n".join(lines)
    lines.append("## Attribution 覆盖\n")
    coverage = table.groupby(["model", "method"]).agg(
        n_features=("feature", "count"), n_contexts=("split_type", "size")).reset_index()
    lines.append("| model | method | n_rows |")
    for _, r in table.groupby(["model", "method"]).size().reset_index(name="n").iterrows():
        lines.append(f"| {r['model']} | {r['method']} | {int(r['n'])} |")
    lines.append("\n## 高归因特征 (per model × method, 跨 context 平均 |importance| 前 N)\n")
    top = top_attribution_features(table, top_n=top_n)
    if not top.empty:
        try:
            lines.append(top.to_markdown(index=False))
        except Exception:
            lines.append("```\n" + top.to_string(index=False) + "\n```")
    lines.append("\n> 说明: 本表是 importance/attribution 证据; 不做成统计显著标签。")
    lines.append("> ISM 为核苷酸替换效应 (nucleotide substitution effect), 不是普通 feature importance。")
    lines.append("> motif discovery / enrichment / known-motif 比较由后续 Phase 提供 (当前 unavailable)。\n")
    return "\n".join(lines)
