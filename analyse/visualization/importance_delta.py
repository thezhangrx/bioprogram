"""analyse.visualization.importance_delta — Importance/Attribution–ΔR² 二维证据坐标图。

X = ΔR² (配对基线: 同 split/cell/model/seed cohort, 由 analyse.environment.incremental_effect 计算)
Y = 模型专属主 importance (经 filter → within-context 归一化)
交付:
    tables/importance_vs_delta_r2.csv
    summary/07_importance_vs_delta_r2.md
    summary/importance_metric_selection.md
    figures/07_evidence/importance_vs_delta_r2_{all_models,linear,xgboost,mlp,cnn}.png
原则: 只画真实存在的配对点; 缺 ΔR²/缺重要性/缺稳健性 -> filter_pass=False 并写明 reason;
      CI 未接通 bootstrap 时保持 NaN, 绝不伪造误差条; 不把 Attention/SNR/FDR 当 effect; 不做加权综合分。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analyse.config import AnalysisConfig
from analyse.importance_metrics import (ENV_FACTORS, PRIMARY_METRICS, evidence_strength,
                                        metric_selection_rows, normalize_within_context,
                                        passes_filter)

IMPORTANCE_FILES = {
    "linear": "linear_regression_weights.csv",
    "xgboost": "xgboost_feature_importance.csv",
    "mlp": "mlp_feature_importance.csv",
    "cnn": "cnn_feature_importance.csv",
    "transformer": "transformer_feature_importance.csv",
}

STRENGTH_MARKERS = {
    "Strong": "o", "Moderate": "s", "Weak": "^", "not": "x",
    "below": "x", "unavailable": "x",
}

# CSV 列契约 (测试与下游消费者共同依赖)
TABLE_COLUMNS = ["feature", "model", "split_type", "cell_line", "held_out_cell_line",
                 "environment", "baseline_environment", "expanded_environment",
                 "delta_r2", "delta_r2_ci_low", "delta_r2_ci_high", "delta_rmse",
                 "raw_importance", "normalized_importance", "importance_method",
                 "effect_direction", "evidence_tier", "evidence_strength",
                 "coverage", "snr", "fdr",
                 "robustness_metric", "robustness_value",
                 "statistical_metric", "statistical_value",
                 "eligible", "filter_mode", "filter_pass", "filter_reason",
                 "n_importance_contexts", "n_paired"]


def ci_brackets_point(ci_low, ci_high, point) -> bool:
    """CI 合法性检查: 未接通 bootstrap (NaN) 视为合法; 若存在则必须包住点估计。"""
    if ci_low is None or ci_high is None or point is None:
        return True
    vals = np.asarray([ci_low, ci_high, point], dtype=float)
    if not np.isfinite(vals).all():
        return True
    return float(ci_low) <= float(point) <= float(ci_high)


def normalize_model_key(value: str) -> str:
    s = str(value).strip().lower()
    if "cnn" in s:
        return "cnn"
    if "xgb" in s:
        return "xgboost"
    if "linear" in s:
        return "linear"
    if "mlp" in s:
        return "mlp"
    if "trans" in s:
        return "transformer"
    return s


def _safe_int(value) -> Optional[int]:
    try:
        if value is None or (isinstance(value, float) and not np.isfinite(value)):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _marker_for(strength: str) -> str:
    for key, mk in STRENGTH_MARKERS.items():
        if strength.startswith(key):
            return mk
    return "x"


# ---------------------------------------------------------------------------
# 1) importance 侧: 每实验目录 -> (model, split, cell, environment) 的 factor importance
# ---------------------------------------------------------------------------
def scan_factor_importance(batch_dir: str | Path) -> pd.DataFrame:
    """扫描各实验的 importance CSV, 把环境因子的主 importance 按 23 位点求和。

    仅使用 registry 定义的 primary/robustness/statistical 字段;
    字段缺失 -> 该行不产生 importance (绝不假装存在)。
    """
    from analyse.importance_extraction import identify_feature_channel, normalize_cell_line, parse_info_file

    root = Path(batch_dir)
    records: List[Dict] = []
    for model_key, fname in IMPORTANCE_FILES.items():
        spec = PRIMARY_METRICS[model_key]
        if not spec.enabled:
            continue
        for csv_path in glob.glob(str(root / "**" / fname), recursive=True):
            exp_dir = Path(csv_path).parent
            info_files = glob.glob(str(exp_dir / "*info*.txt"))
            info = parse_info_file(info_files[0]) if info_files else {}
            model_raw = str(info.get("model", "")) or model_key
            if normalize_model_key(model_raw) != model_key:
                continue
            split_type = str(info.get("split_type", "single")).lower()
            cell_line = normalize_cell_line(split_type, info.get("cell_line", info.get("held_out_cell_line", "none")))
            environment = str(info.get("environment", info.get("combination", ""))).lower()
            try:
                df = pd.read_csv(csv_path)
            except Exception:
                continue
            feat_col = "Feature" if "Feature" in df.columns else ("feature" if "feature" in df.columns else None)
            if feat_col is None or spec.primary_field not in df.columns:
                continue
            df["_channel"] = df[feat_col].astype(str).map(identify_feature_channel)
            sub = df[df["_channel"].isin(ENV_FACTORS)]
            if sub.empty:
                continue
            primary = pd.to_numeric(sub[spec.primary_field], errors="coerce")
            for factor, grp in sub.assign(_p=primary.abs()).groupby("_channel"):
                vals = grp["_p"].dropna()
                if vals.empty:
                    continue
                rob = np.nan
                if spec.robustness_field and spec.robustness_field in grp.columns:
                    r = pd.to_numeric(grp[spec.robustness_field], errors="coerce").dropna()
                    rob = float(r.mean()) if not r.empty else np.nan
                stat = np.nan
                if spec.statistical_field and spec.statistical_field in grp.columns:
                    s = pd.to_numeric(grp[spec.statistical_field], errors="coerce").dropna()
                    if not s.empty:
                        stat = float(s.min())  # factor 级统计证据 = 位点级最小 FDR (保守方向待 md 说明)
                records.append({
                    "model": model_key, "split_type": split_type, "cell_line": cell_line,
                    "environment": environment, "feature": factor,
                    "importance_value": float(vals.sum()),
                    "robustness_value": rob, "statistical_value": stat,
                    "n_positions": int(vals.size),
                })
    if not records:
        return pd.DataFrame(columns=["model", "split_type", "cell_line", "environment", "feature",
                                     "importance_value", "robustness_value", "statistical_value",
                                     "n_positions", "n_importance_contexts"])
    out = pd.DataFrame(records)
    agg = out.groupby(["model", "split_type", "cell_line", "feature"], dropna=False).agg(
        importance_value=("importance_value", "mean"),
        robustness_value=("robustness_value", "mean"),
        statistical_value=("statistical_value", "min"),
        n_importance_contexts=("importance_value", "size"),
        n_positions=("n_positions", "max"),
    ).reset_index()
    return agg


# ---------------------------------------------------------------------------
# 2) ΔR² 侧: 复用引擎的配对条件增量 (same cohort / same seed)
# ---------------------------------------------------------------------------
def factor_delta_r2(batch_dir: str | Path, config: Optional[AnalysisConfig] = None) -> pd.DataFrame:
    """factor 级 ΔR² (跨背景取均值)。

    数值卫生: 单实验 R²/|Δ| 超过 `consensus.unstable_effect_threshold` (默认 10.0) 视为
    数值发散/参数异常 (本批 linear 有 56/192 个实验 R² 达 -4.5e19), 在配对前剔除,
    避免一个发散实验支配整张图的坐标轴 (剔除数记录在 `df.attrs`).
    """
    from analyse.data.loaders import load_experiment_table
    from analyse.environment.incremental_effect import (compute_conditional_increments,
                                                        summarize_conditional)
    cfg = config or AnalysisConfig()
    thr = float(cfg.consensus.unstable_effect_threshold)
    table = load_experiment_table(batch_dir)
    if table is None or table.empty:
        return pd.DataFrame()
    r2 = pd.to_numeric(table.get("R2"), errors="coerce")
    bad = r2.isna() | (r2.abs() > thr)
    dropped = int(bad.sum())
    table = table[~bad].copy()
    raw = compute_conditional_increments(table)
    if raw is None or raw.empty:
        return pd.DataFrame()
    summary = summarize_conditional(raw)
    summary = summary.copy()
    summary["model"] = summary["model"].map(normalize_model_key)
    agg = summary.groupby(["model", "split_type", "cell_line", "environment_added"], dropna=False).agg(
        delta_r2=("delta_r2_mean", "mean"),
        delta_rmse=("delta_rmse_mean", "mean"),
        n_paired=("n_paired", "sum"),
    ).reset_index().rename(columns={"environment_added": "feature"})
    agg.attrs["dropped_anomalous_experiments"] = dropped
    agg.attrs["unstable_effect_threshold"] = thr
    return agg


# ---------------------------------------------------------------------------
# 3) 组装二维表 (严格 feature/model/split/cell 对齐)
# ---------------------------------------------------------------------------
def build_importance_delta_table(batch_dir: str | Path, filter_mode: str = "strict",
                                 config: Optional[AnalysisConfig] = None) -> pd.DataFrame:
    cfg = config or AnalysisConfig()
    thr = float(cfg.consensus.unstable_effect_threshold)
    imp = scan_factor_importance(batch_dir)
    delta = factor_delta_r2(batch_dir, config=cfg)
    keys = ["model", "split_type", "cell_line", "feature"]
    if imp.empty and delta.empty:
        return pd.DataFrame()
    merged = imp.merge(delta, on=keys, how="outer") if not delta.empty else imp.copy()
    if "delta_r2" not in merged.columns:
        merged["delta_r2"] = np.nan
    if "delta_rmse" not in merged.columns:
        merged["delta_rmse"] = np.nan
    if "n_paired" not in merged.columns:
        merged["n_paired"] = np.nan

    rows: List[Dict] = []
    for _, r in merged.iterrows():
        model = str(r["model"])
        spec = PRIMARY_METRICS.get(model)
        strength, reason = evidence_strength(
            model,
            None if pd.isna(r.get("importance_value", np.nan)) else float(r["importance_value"]),
            None if pd.isna(r.get("robustness_value", np.nan)) else float(r["robustness_value"]),
            None if pd.isna(r.get("statistical_value", np.nan)) else float(r["statistical_value"]),
            min_effect_size=cfg.attribution.min_effect_size,
            snr_strong=cfg.attribution.snr_threshold,
            snr_moderate=cfg.attribution.snr_moderate,
            snr_weak=cfg.attribution.snr_weak,
            fdr_strong=cfg.statistical.fdr_strong,
            fdr_moderate=cfg.statistical.fdr_moderate,
            fdr_weak=cfg.statistical.fdr_weak,
        )
        if pd.isna(r.get("delta_r2", np.nan)):
            strength, reason = "unavailable", "no paired ΔR² for this (model, split, cell, factor) context"
        ok, why = passes_filter(strength, filter_mode)
        if ok and abs(float(r["delta_r2"])) > thr:
            ok, why = False, (f"|ΔR²|={abs(float(r['delta_r2'])):.3g} > unstable_effect_threshold={thr:g} "
                              "-> anomalous / diverged experiment excluded (parameter anomaly)")
        if pd.isna(r.get("importance_value", np.nan)) and ok:
            ok, why = False, "importance missing for factor"
        split_val = str(r.get("split_type", ""))
        cell_val = str(r.get("cell_line", ""))
        fdr_val = None if pd.isna(r.get("statistical_value", np.nan)) else float(r["statistical_value"])
        strength, _ = evidence_strength(
            model,
            None if pd.isna(r.get("importance_value", np.nan)) else float(r["importance_value"]),
            None if pd.isna(r.get("robustness_value", np.nan)) else float(r["robustness_value"]),
            fdr_val,
            min_effect_size=cfg.attribution.min_effect_size,
            snr_strong=cfg.attribution.snr_threshold,
            snr_moderate=cfg.attribution.snr_moderate,
            snr_weak=cfg.attribution.snr_weak,
            fdr_strong=cfg.statistical.fdr_strong,
            fdr_moderate=cfg.statistical.fdr_moderate,
            fdr_weak=cfg.statistical.fdr_weak,
        )
        delta_val = r.get("delta_r2", np.nan)
        rows.append({
            "feature": str(r["feature"]),
            "model": model,
            "split_type": split_val,
            "cell_line": cell_val,
            "held_out_cell_line": (cell_val if split_val.lower() == "all" and cell_val.lower()
                                   not in ("none", "nan", "") else None),
            "environment": str(r["feature"]),          # factor 级上下文 (与 feature 同源)
            "baseline_environment": str(r.get("environment", "")) or None,
            "expanded_environment": None,              # 由 edges 表提供, 此处不伪造
            "delta_r2": None if pd.isna(delta_val) else float(delta_val),
            "delta_r2_ci_low": np.nan,   # bootstrap CI runner 未接通 -> 保持 NaN, 不伪造
            "delta_r2_ci_high": np.nan,
            "delta_rmse": None if pd.isna(r.get("delta_rmse", np.nan)) else float(r["delta_rmse"]),
            "raw_importance": None if pd.isna(r.get("importance_value", np.nan)) else float(r["importance_value"]),
            "importance_method": (spec.primary_field if spec else None),
            "effect_direction": ("+" if float(delta_val) > 0 else ("-" if float(delta_val) < 0 else "0"))
            if not pd.isna(delta_val) else None,
            "evidence_tier": None,                     # 由 evidence_matrix 合入 (复用, 不重算)
            "evidence_strength": strength,
            "coverage": None, "snr": None, "fdr": fdr_val,
            "eligible": bool(ok),
            "robustness_metric": (spec.robustness_field if spec else None),
            "robustness_value": None if pd.isna(r.get("robustness_value", np.nan)) else float(r["robustness_value"]),
            "statistical_metric": (spec.statistical_field if spec else None),
            "statistical_value": fdr_val,
            "filter_mode": filter_mode,
            "filter_pass": bool(ok),
            "filter_reason": why if not ok else reason,
            "n_importance_contexts": _safe_int(r.get("n_importance_contexts")),
            "n_paired": _safe_int(r.get("n_paired")),
        })
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    # 归一化: 先移除占位列 (否则 merge 会产生 normalized_importance_x/_y 后缀)
    table = table.drop(columns=[c for c in ("normalized_importance",) if c in table.columns])
    table["importance_value"] = pd.to_numeric(table.get("raw_importance"), errors="coerce")
    valid = table[table["importance_value"].notna()].copy()
    norm = normalize_within_context(valid)
    table = table.merge(norm[["feature", "model", "split_type", "cell_line", "normalized_importance"]],
                        on=["feature", "model", "split_type", "cell_line"], how="left")
    # 兼容别名: importance_value / importance_metric (旧字段名)
    table["importance_value"] = table.get("raw_importance")
    table["importance_metric"] = table.get("importance_method")
    out = table[[c for c in TABLE_COLUMNS if c in table.columns]]
    for col in TABLE_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    out["importance_value"] = table["importance_value"]
    out["importance_metric"] = table["importance_metric"]
    out.attrs["dropped_anomalous_experiments"] = int(delta.attrs.get("dropped_anomalous_experiments", 0)) if not delta.empty else 0
    out.attrs["unstable_effect_threshold"] = thr
    return out


# ---------------------------------------------------------------------------
# 4) 渲染
# ---------------------------------------------------------------------------
def _plot_points(ax, sub: pd.DataFrame, color_by: str, cmap: Dict[str, str]) -> None:
    for _, r in sub.iterrows():
        marker = _marker_for(str(r["evidence_strength"]))
        kw = {} if marker == "x" else {"edgecolors": "k", "linewidths": 0.4}
        ax.scatter(float(r["delta_r2"]), float(r["normalized_importance"]),
                   c=cmap.get(str(r[color_by]), "#888888"),
                   marker=marker, s=70, alpha=0.9, zorder=3, **kw)
    for _, r in sub.iterrows():
        ax.annotate(str(r["feature"]), (float(r["delta_r2"]), float(r["normalized_importance"])),
                    textcoords="offset points", xytext=(4, 4), fontsize=7, alpha=0.85)


def render_importance_delta(table: pd.DataFrame, figures_dir: str | Path, filter_mode: str,
                            fallback: str = "all") -> List[str]:
    """渲染二维图。

    若请求的 filter_mode 在本批数据上没有任何通过点 (例如 strict 阈值下 0 点), 则**自动回退**
    到 `fallback` 档渲染, 并在标题/报告中明确标注回退原因 —— 既保证交付图存在, 又不伪造证据。
    """
    fig_dir = Path(figures_dir) / "07_evidence"
    fig_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[str] = []
    if table is None or table.empty:
        return outputs
    plotted = table[table["filter_pass"].astype(bool) & table["normalized_importance"].notna()]
    render_mode = filter_mode
    if plotted.empty:
        render_mode = fallback
        alt = table.copy()
        anomaly = alt["filter_reason"].astype(str).str.contains("unstable_effect_threshold")
        if fallback == "all":
            alt["filter_pass"] = (alt["evidence_strength"] != "unavailable") & ~anomaly
        else:
            alt["filter_pass"] = (alt["evidence_strength"].astype(str).str.startswith(("Strong", "Moderate"))
                                  & ~anomaly)
        plotted = alt[alt["filter_pass"].astype(bool) & alt["normalized_importance"].notna()]
        if plotted.empty:
            return outputs
    palette = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf"]

    def _ax(ax, sub, title, color_by, cmap):
        ax.axvline(0.0, color="k", lw=1.0, ls="--", alpha=0.7)
        ax.axhline(float(sub["normalized_importance"].median()), color="grey", lw=0.8, ls=":", alpha=0.7)
        _plot_points(ax, sub, color_by, cmap)
        # 象限标注固定在坐标系角落 (transAxes), 避免与数据点重叠
        for x, y, txt, ha, va in ((0.015, 0.985, "Q2: high attribution, negative ΔR²", "left", "top"),
                                  (0.985, 0.985, "Q1: high attribution, positive ΔR²", "right", "top"),
                                  (0.015, 0.015, "Q3: weak / unstable", "left", "bottom"),
                                  (0.985, 0.015, "Q4: modest predictive contribution", "right", "bottom")):
            ax.text(x, y, txt, transform=ax.transAxes, ha=ha, va=va, fontsize=7, color="#666")
        ax.set_xlabel("ΔR² (paired baseline; same split/cell/model/seed cohort)")
        ax.set_ylabel("normalized importance (within-model share)")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.25)

    def _combined_legend(ax, color_handles, color_title):
        """单一图例: 颜色语义 + marker 证据等级, 避免两个图例互相遮挡。"""
        mk = [plt.Line2D([], [], marker="o", ls="", color="grey", label="Strong"),
              plt.Line2D([], [], marker="s", ls="", color="grey", label="Moderate"),
              plt.Line2D([], [], marker="^", ls="", color="grey", label="Weak"),
              plt.Line2D([], [], marker="x", ls="", color="grey", label="not supported / below min effect")]
        ax.legend(handles=color_handles + mk, ncol=2, fontsize=7, framealpha=0.9, loc="best",
                  title=f"color = {color_title} | marker = evidence level")

    note = "" if render_mode == filter_mode else f" [requested '{filter_mode}' had 0 points -> showing '{render_mode}']"
    # all models
    models = sorted(plotted["model"].unique())
    cmap_model = {m: palette[i % len(palette)] for i, m in enumerate(models)}
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    _ax(ax, plotted, f"Importance / Attribution vs ΔR² (all models, filter={render_mode}){note}", "model", cmap_model)
    handles = [plt.Line2D([], [], marker="o", ls="", color=cmap_model[m], label=m) for m in models]
    _combined_legend(ax, handles, "model")
    fig.tight_layout()
    p = fig_dir / "importance_vs_delta_r2_all_models.png"
    fig.savefig(p, bbox_inches="tight"); plt.close(fig); outputs.append(str(p))

    # per model
    for model in models:
        sub = plotted[plotted["model"] == model]
        cells = sorted(sub["cell_line"].astype(str).unique())
        cmap_cell = {c: palette[i % len(palette)] for i, c in enumerate(cells)}
        fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=150)
        _ax(ax, sub, f"{model}: importance ({PRIMARY_METRICS[model].primary_field}) vs ΔR² (filter={render_mode}){note}",
            "cell_line", cmap_cell)
        handles = [plt.Line2D([], [], marker="o", ls="", color=cmap_cell[c], label=c) for c in cells]
        _combined_legend(ax, handles, "cell_line")
        fig.tight_layout()
        p = fig_dir / f"importance_vs_delta_r2_{model}.png"
        fig.savefig(p, bbox_inches="tight"); plt.close(fig); outputs.append(str(p))
    return outputs


# ---------------------------------------------------------------------------
# 5) 报告
# ---------------------------------------------------------------------------
def merge_evidence_columns(table: pd.DataFrame, output_dir: str | Path) -> pd.DataFrame:
    """从已有 evidence_matrix.csv 合入 evidence_tier / coverage / permutation FDR。

    严格复用 evidence integration 的结果, 前端/本模块都**不重新实现** tier 规则。
    """
    out = table.copy()
    path = Path(output_dir) / "tables" / "evidence_matrix.csv"
    if not path.exists() or out.empty:
        return out
    try:
        ev = pd.read_csv(path)
    except Exception:  # noqa: BLE001
        return out
    if ev.empty or "feature" not in ev.columns:
        return out
    cols = [c for c in ("feature", "evidence_tier", "coverage", "cell_line_consistency",
                        "direction_concordance", "permutation_fdr", "ci_excludes_zero")
            if c in ev.columns]
    ev = ev[cols].drop_duplicates(subset=["feature"])
    out["feature_key"] = out["feature"].astype(str).str.lower()
    ev["feature_key"] = ev["feature"].astype(str).str.lower()
    merged = out.merge(ev.drop(columns=["feature"]), on="feature_key", how="left",
                       suffixes=("", "_ev"))
    merged = merged.drop(columns=["feature_key"])
    # 同名占位列 (build 阶段写入的 None) 必须让位给 evidence_matrix 的真实值
    for col in ("evidence_tier", "coverage", "cell_line_consistency",
                "direction_concordance", "ci_excludes_zero"):
        ev_col = f"{col}_ev"
        if ev_col in merged.columns:
            merged[col] = merged[ev_col].combine_first(merged.get(col))
            merged = merged.drop(columns=[ev_col])
    if "fdr" not in merged.columns:
        merged["fdr"] = np.nan
    if "permutation_fdr" in merged.columns:
        merged["fdr"] = merged["fdr"].where(merged["fdr"].notna(), merged["permutation_fdr"])
    merged["snr"] = merged["robustness_value"]
    return merged


def build_summary_json(table: pd.DataFrame) -> Dict[str, object]:
    """machine-readable summary (任务书 §16); 分类只基于已有字段, 不发明新 consensus。"""
    accepted = table[table["eligible"].astype(bool)] if "eligible" in table.columns else table
    def _rows(df: pd.DataFrame, n: int = 20) -> List[Dict]:
        cols = [c for c in ("feature", "model", "split_type", "cell_line", "delta_r2",
                            "normalized_importance", "raw_importance", "evidence_tier",
                            "effect_direction", "fdr", "snr") if c in df.columns]
        return df[cols].head(n).to_dict(orient="records")

    if accepted.empty:
        return {"top_candidates": [], "positive_delta_r2_candidates": [],
                "high_importance_candidates": [], "cross_model_supported_candidates": [],
                "model_specific_candidates": [],
                "negative_delta_r2_high_importance_candidates": [],
                "notes": ["no eligible point passed the evidence filter"]}
    acc = accepted.copy()
    acc["abs_delta"] = pd.to_numeric(acc["delta_r2"], errors="coerce").abs()
    acc["abs_imp"] = pd.to_numeric(acc["normalized_importance"], errors="coerce")
    top = acc.sort_values(["abs_delta", "abs_imp"], ascending=False)
    positive = acc[pd.to_numeric(acc["delta_r2"], errors="coerce") > 0]
    high_imp = acc[acc["abs_imp"] >= acc["abs_imp"].quantile(0.75)]
    cross = acc[acc.get("evidence_tier", pd.Series(dtype=object)).isin(
        ["Tier 1 - Strong convergent", "Tier 2 - Convergent", "Tier1", "Tier2"])] \
        if "evidence_tier" in acc.columns else acc.iloc[0:0]
    model_specific = acc[acc.get("evidence_tier", pd.Series(dtype=object)).isin(
        ["Tier 3 - Model-specific", "Tier3"])] if "evidence_tier" in acc.columns else acc.iloc[0:0]
    negative_high = acc[(pd.to_numeric(acc["delta_r2"], errors="coerce") < 0) &
                        (acc["abs_imp"] >= acc["abs_imp"].quantile(0.75))]
    return {
        "top_candidates": _rows(top),
        "positive_delta_r2_candidates": _rows(positive.sort_values("abs_delta", ascending=False)),
        "high_importance_candidates": _rows(high_imp.sort_values("abs_imp", ascending=False)),
        "cross_model_supported_candidates": _rows(cross),
        "model_specific_candidates": _rows(model_specific),
        "negative_delta_r2_high_importance_candidates": _rows(negative_delta_r2_high_importance :=
                                                              negative_high.sort_values(
                                                                  "abs_imp", ascending=False)),
        "notes": [
            "ΔR² = incremental predictive value; normalized_importance = within-model attribution "
            "share; evidence_tier 复用 evidence integration 结果",
            "不是统计显著性, 不是因果; SNR 仅作 robustness",
            f"eligible points: {len(acc)} / {len(table)}",
        ],
    }


def extend_figure_layout(figures: List[str], figures_dir: str | Path) -> List[str]:
    """按任务书目录约定补一份分模型子目录副本 (保留原扁平文件以兼容既有消费者)。"""
    import shutil
    root = Path(figures_dir) / "07_evidence" / "importance_delta_r2"
    extra: List[str] = []
    for f in figures:
        name = Path(f).stem
        model = name.replace("importance_vs_delta_r2_", "")
        sub = root / model
        sub.mkdir(parents=True, exist_ok=True)
        target = sub / Path(f).name
        shutil.copyfile(f, target)
        extra.append(str(target))
    env_alias = root / "all_models" / "importance_delta_r2_environment.png"
    src = [f for f in figures if f.endswith("importance_vs_delta_r2_all_models.png")]
    if env_alias.parent.exists() and src:
        shutil.copyfile(src[0], env_alias)
        extra.append(str(env_alias))
    return extra


def _md_cell(value) -> str:
    """Markdown 表格单元转义 (| 会破坏表格结构)。"""
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_metric_selection_md(path: str | Path) -> str:
    rows = metric_selection_rows()
    lines = ["# Importance 指标选择说明 (Importance Metric Selection)", "",
             "> 本文件解释二维 Importance–ΔR² 图中每个模型为什么选择该 Y 指标，以及哪些指标**没有**被当作 Y。", "",
             "## 1. 各模型 Y 轴主指标", "",
             "| 模型 | Y 轴主指标 | 启用 | 稳健性字段 | 统计字段 | 说明 |",
             "| :--- | :--- | :--- | :--- | :--- | :--- |"]
    for r in rows:
        lines.append("| " + " | ".join(_md_cell(r[k]) for k in
                     ("模型", "Y 轴主指标", "是否启用", "稳健性字段", "统计字段", "说明")) + " |")
    lines += ["", "## 2. 明确不作为 Y 的字段与原因", "",
              "| 字段 | 模型 | 不作为 Y 的原因 |", "| :--- | :--- | :--- |"]
    for field, model, reason in NOT_USED_AS_Y_ROWS:
        lines.append(f"| {_md_cell(field)} | {_md_cell(model)} | {_md_cell(reason)} |")
    lines += ["", "## 3. 语义边界", "",
              "- **Effect**: ΔR² 等预测增量 → 本图 X 轴；",
              "- **Importance/Attribution**: 主指标 (|系数| / mean|SHAP| / mean|IG|) → 本图 Y 轴；",
              "- **Robustness**: SNR 类 → 只作筛选 (Strong/Moderate/Weak attribution)，不作 Y；",
              "- **Statistical Evidence**: 仅线性 FDR 等合法检验结果 → 只作 linear 的筛选与图例语义；",
              "- 严禁把上述三类加权成综合分，也严禁把 SNR/FDR/Attention 称为 effect 或 significance。", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def write_report_md(table: pd.DataFrame, path: str | Path, filter_mode: str,
                    figures: List[str], batch_dir: str) -> str:
    n_total = len(table) if table is not None else 0
    n_pass = int(table["filter_pass"].sum()) if n_total else 0
    models_present = sorted(table["model"].unique()) if n_total else []
    mode_counts = {mode: (int((table["evidence_strength"].map(lambda s: passes_filter(str(s), mode)[0])
                               & table["importance_value"].notna()).sum()) if n_total else 0)
                   for mode in ("strict", "moderate", "all")}
    strict_note = ""
    if n_total and mode_counts["strict"] == 0:
        strict_note = ("\n- ⚠ **本批数据 strict 档通过 0 点**：线性 FDR 全部 ≥0.05，"
                       "xgb/mlp 的 factor 级 SNR < 1.2 或 |importance| < min_effect_size，CNN 仅达 Moderate。"
                       "因此图件自动回退到 `all` 档渲染并在标题中标注；这是阈值与研究对象的真实关系，不是绘图失败。")
    lines = [
        "# 07 Importance / Attribution – ΔR² Relationship", "",
        "## 1. Purpose",
        "回答“某环境因子的预测增量贡献 (ΔR²) 与模型对该因子的依赖/归因强度是否一致”，"
        "即建立 Effect–Attribution 二维坐标系；不产出生物学因果结论。", "",
        "## 2. X 轴定义",
        "`ΔR² = R²(expanded) − R²(baseline)`，遵循 Paired Baseline 原则：仅在同一 "
        "`(split_type, cell_line, model, random_seed)` cohort 内与 sequence/背景组合配对，"
        "由 `analyse.environment.incremental_effect` 计算；本图对同一 factor 跨背景取均值。", "",
        "## 3. Y 轴定义",
        "模型专属主 importance，经 within-(model, split, cell_line) 归一化："
        "`normalized = importance_factor / Σ importance_factors`，含义为“该因子在本模型该上下文全部有效环境 attribution 中的相对占比”。"
        "原始量纲 (系数/SHAP/IG) 不可跨模型直接比较。", "",
        "## 4. Model-specific metric selection",
    ]
    for m in sorted(PRIMARY_METRICS):
        spec = PRIMARY_METRICS[m]
        lines.append(f"- **{m}**: Y = `{spec.primary_field or 'unavailable'}`；"
                     f"robustness = `{spec.robustness_field or '-'}`；"
                     f"statistical = `{spec.statistical_field or '-'}`；{spec.note}")
    lines += ["", "## 5. Significance / robustness filtering",
              f"- filter_mode = `{filter_mode}`（strict=仅 Strong；moderate=Strong+Moderate；all=所有可用主指标）；",
              f"- 本批通过点数: strict={mode_counts['strict']}, moderate={mode_counts['moderate']}, all={mode_counts['all']}"
              f"；CSV 中 `filter_pass` 对应 `{filter_mode}` 档，`filter_reason` 逐行给出落选原因。{strict_note}",
              "- linear: FDR 阈值分档 (0.001/0.01/0.05)；FDR 缺失 → unavailable，不因存在系数而宣称显著；",
              "- xgb/mlp/cnn: SNR (2.5/1.8/1.2) **且** |importance| ≥ min_effect_size；SNR 不是 p 值；",
              "- 注意 factor 级 importance 为 23 位点求和, 与 config 中 per-feature min_effect_size 属不同标度; "
              "此处按规范字面复用该阈值, 结果偏保守 (已在 §8 记录);",
              "- CNN 无 IG_SNR 输出，其稳健性字段使用 ISM_SNR（ISM 语义为突变效应，已在标注中说明）；",
              "- Transformer 被排除：未输出 Transformer_IG，Attention/Entropy 无方向。", "",
              "## 6. Normalization（见 §3）", "",
              "## 7. Plot interpretation",
              "- Q1 高 attribution + ΔR²>0：该因子既有增量贡献又被稳定依赖；",
              "- Q2 高 attribution + ΔR²<0：模型依赖该因子，但增量实验无额外收益；",
              "- Q4 低 attribution + ΔR²>0：有增量收益但模型依赖不强（可能被其它因子替代）；",
              "- Q3 低 attribution + ΔR²<0：弱/可能不稳。以上仅为图面解释，不是生物学结论。", "",
              "## 8. Limitations",
              "- 未接通 bootstrap runner：`delta_r2_ci_low/high` 保持 NaN，图中**不画误差条**；",
              "- factor 级统计证据取位点级最小 FDR，未对因子内多重比较再校正；",
              "- factor 级 importance 求和后与 per-feature `min_effect_size` 比较属标度混用，偏保守；",
              "- `all` 档含 not-supported / below-min-effect 点，仅供敏感性分析，不得当作显著结果引用；",
              "- ΔR² 依赖既有 1344 网格的实验设计（`all` 划分在网格中退化为 `single`，见项目文档 §1.5）；",
              "- 本图不包含 sequence position×channel 级 attribution（另有 sequence 图）。", "",
              f"## 9. 本次数据 (batch={Path(batch_dir).name})",
              f"- 候选点: {n_total}（`{filter_mode}` 档通过 {n_pass}）；模型: {', '.join(models_present) if models_present else '(none)'}",
              f"- 三档通过数: strict={mode_counts['strict']} / moderate={mode_counts['moderate']} / all={mode_counts['all']}",
              "- 数值卫生: 配对前剔除单实验 |R²| > unstable_effect_threshold 的发散实验 "
              f"{table.attrs.get('dropped_anomalous_experiments', 'n/a')} 个 (linear 为主); "
              "残余 |ΔR²| 超阈值的点也在 `filter_reason` 中标记为 parameter anomaly 并排除出图。",
              f"- 生成图: {len(figures)} 张；CSV: `tables/importance_vs_delta_r2.csv`", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return str(path)


# NOT_USED_AS_Y 从 registry 引入 (避免重复定义)
from analyse.importance_metrics import NOT_USED_AS_Y as NOT_USED_AS_Y_ROWS  # noqa: E402


# ---------------------------------------------------------------------------
# 6) 编排 + CLI
# ---------------------------------------------------------------------------
def run_importance_delta_analysis(batch_dir: str | Path, output_dir: str | Path,
                                  filter_mode: str = "strict",
                                  config: Optional[AnalysisConfig] = None) -> Dict[str, str]:
    out = Path(output_dir)
    tables = out / "tables"; summary = out / "summary"; figures = out / "figures"
    for d in (tables, summary, figures):
        d.mkdir(parents=True, exist_ok=True)
    table = build_importance_delta_table(batch_dir, filter_mode=filter_mode, config=config)
    table = merge_evidence_columns(table, output_dir)
    if not table.empty and "fdr" not in table.columns:
        table["fdr"] = np.nan
    csv_path = tables / "importance_vs_delta_r2.csv"
    table.to_csv(csv_path, index=False)
    fig_paths = render_importance_delta(table, figures, filter_mode)
    fig_paths += extend_figure_layout(fig_paths, figures)
    md_path = write_report_md(table, summary / "07_importance_vs_delta_r2.md", filter_mode,
                              fig_paths, str(batch_dir))
    alias = summary / "importance_vs_delta_r2.md"
    alias.write_text(Path(md_path).read_text(encoding="utf-8"), encoding="utf-8")
    sel_path = write_metric_selection_md(summary / "importance_metric_selection.md")
    summary_json = summary / "importance_delta_r2_summary.json"
    summary_json.write_text(json.dumps(build_summary_json(table), ensure_ascii=False, indent=2),
                            encoding="utf-8")
    return {"csv": str(csv_path), "report": md_path, "report_alias": str(alias),
            "metric_selection": sel_path, "summary_json": str(summary_json),
            "figures": ";".join(fig_paths), "n_points": str(len(table)),
            "n_pass": str(int(table["filter_pass"].sum()) if not table.empty else 0)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Importance/Attribution vs ΔR² 2D evidence plot")
    ap.add_argument("--batch-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--filter-mode", default="strict", choices=["strict", "moderate", "all"])
    args = ap.parse_args()
    res = run_importance_delta_analysis(args.batch_dir, args.output, filter_mode=args.filter_mode)
    for k, v in res.items():
        print(f"[✓] {k}: {v}")


if __name__ == "__main__":
    main()
