"""analyse.cellline.consistency — cell-line effect 汇总与 context 一致性 (重设计)。

判定不再只看 `all_same_sign`, 而是同时使用:
  1. direction consistency     —— 同向 cell line 占比 / 反向占比;
  2. effect-size heterogeneity —— max|effect| / median|effect|;
  3. CI overlap / separation   —— 若提供了各 cell line 的 bootstrap CI, 反向 cell line 的 CI
     与主体 CI 全部重叠时**不**升级为 conflicting (降为 dependent)。

标签 (全部可达; 阈值集中在 config.CelllineConsistencyConfig):
  Context-consistent   方向一致且幅度同质
  Context-dependent    方向一致但幅度异质; 或多数同向且少数反向但未达冲突线
  Context-conflicting  反向占比 >= conflicting_ratio
  Uncertain            有效 cell line 不足 / 无有限效应 / 无多数方向

科学边界: 只描述 effect 的跨 cell-line 分布, 不代表"机制不同", 也不是显著性检验。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analyse.config import AnalysisConfig

LABELS = ("Context-consistent", "Context-dependent", "Context-conflicting", "Uncertain")

EFFECT_DELTA_COLUMNS = {
    "main_r2_delta": "environment",
}


def _finite(value) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def _direction(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return "+" if value > 0 else ("-" if value < 0 else "0")


def _ci_overlaps(ci_a, ci_b) -> Optional[bool]:
    """两个 CI 是否重叠; 任一缺失返回 None (未知 -> 不做降级判断)。"""
    if not ci_a or not ci_b:
        return None
    lo_a, hi_a = _finite(ci_a[0]), _finite(ci_a[1])
    lo_b, hi_b = _finite(ci_b[0]), _finite(ci_b[1])
    if None in (lo_a, hi_a, lo_b, hi_b):
        return None
    return not (hi_a < lo_b or hi_b < lo_a)


def classify_cellline_consistency_detail(
    effects_by_cell_line: Dict[str, Optional[float]],
    ci_by_cell_line: Optional[Dict[str, Tuple[Optional[float], Optional[float]]]] = None,
    *,
    consistent_ratio: Optional[float] = None,
    conflicting_ratio: Optional[float] = None,
    heterogeneity_ratio: Optional[float] = None,
    min_cell_lines: Optional[int] = None,
    ci_overlap_relaxes: Optional[bool] = None,
    config: Optional[AnalysisConfig] = None,
) -> Dict:
    """完整判定结果 (label + 诊断量), 供 Evidence Matrix / 报告使用。"""
    cfg = (config or AnalysisConfig()).cellline
    consistent_ratio = cfg.consistent_ratio if consistent_ratio is None else consistent_ratio
    conflicting_ratio = cfg.conflicting_ratio if conflicting_ratio is None else conflicting_ratio
    heterogeneity_ratio = (cfg.heterogeneity_ratio if heterogeneity_ratio is None
                           else heterogeneity_ratio)
    min_cell_lines = cfg.min_cell_lines if min_cell_lines is None else min_cell_lines
    ci_overlap_relaxes = cfg.ci_overlap_relaxes if ci_overlap_relaxes is None else ci_overlap_relaxes

    values = {cl: v for cl, v in ((cl, _finite(e)) for cl, e in effects_by_cell_line.items())
              if v is not None}
    directions = {cl: _direction(v) for cl, v in values.items()}
    nonzero = {cl: d for cl, d in directions.items() if d in ("+", "-")}
    if len(values) < int(min_cell_lines) or len(nonzero) < int(min_cell_lines):
        return {"label": "Uncertain", "consensus_direction": None,
                "n_cell_lines": len(values), "n_majority": 0, "majority_ratio": None,
                "minority_ratio": None, "heterogeneity": None, "ci_overlap_relaxed": False,
                "reason": f"insufficient finite cell-line effects (<{min_cell_lines})"}

    n_pos = sum(1 for d in nonzero.values() if d == "+")
    n_neg = len(nonzero) - n_pos
    majority_dir = "+" if n_pos >= n_neg else "-"
    majority = [cl for cl, d in nonzero.items() if d == majority_dir]
    minority = [cl for cl, d in nonzero.items() if d != majority_dir]
    majority_ratio = len(majority) / len(nonzero)
    minority_ratio = len(minority) / len(nonzero)
    abs_vals = [abs(values[cl]) for cl in nonzero]
    median_abs = float(np.median(abs_vals))
    heterogeneity = (float(max(abs_vals) / median_abs) if median_abs > 0 else
                     (float("inf") if max(abs_vals) > 0 else 1.0))

    ci_overlap_relaxed = False
    if minority and ci_by_cell_line and ci_overlap_relaxes:
        majority_ci = [c for c in (ci_by_cell_line.get(cl) for cl in majority) if c]
        overlaps: List[bool] = []
        for cl in minority:
            for mc in majority_ci:
                ov = _ci_overlaps(ci_by_cell_line.get(cl), mc)
                if ov is not None:
                    overlaps.append(ov)
        if overlaps and all(overlaps):
            ci_overlap_relaxed = True

    if minority_ratio >= float(conflicting_ratio) and not ci_overlap_relaxed:
        label, reason = "Context-conflicting", (
            f"minority direction ratio {minority_ratio:.2f} >= {conflicting_ratio}")
    elif not minority and heterogeneity <= float(heterogeneity_ratio):
        label, reason = "Context-consistent", (
            f"same direction and homogeneous magnitude (max/median={heterogeneity:.2f})")
    elif majority_ratio >= float(consistent_ratio):
        label, reason = "Context-dependent", (
            (f"magnitude heterogeneity max/median={heterogeneity:.2f}" if not minority
             else f"minority direction {minority_ratio:.2f} but majority "
                  f"{majority_ratio:.2f} >= {consistent_ratio}")
            + ("; CI overlap relaxed" if ci_overlap_relaxed else ""))
    else:
        label, reason = "Uncertain", (
            f"no majority direction (ratio {majority_ratio:.2f} < {consistent_ratio})")

    return {"label": label, "consensus_direction": majority_dir,
            "n_cell_lines": len(values), "n_majority": len(majority),
            "majority_ratio": majority_ratio, "minority_ratio": minority_ratio,
            "heterogeneity": heterogeneity, "ci_overlap_relaxed": ci_overlap_relaxed,
            "reason": reason}


def classify_cellline_consistency(
    effects_by_cell_line: Dict[str, Optional[float]],
    consistent_ratio: float = 0.75,
    ci_by_cell_line: Optional[Dict[str, Tuple[Optional[float], Optional[float]]]] = None,
) -> Tuple[str, Optional[str]]:
    """向后兼容签名: 返回 (label, consensus_direction)。"""
    detail = classify_cellline_consistency_detail(
        effects_by_cell_line, ci_by_cell_line, consistent_ratio=consistent_ratio)
    return detail["label"], detail["consensus_direction"]


def summarize_environment_by_cellline(
    main_effects: pd.DataFrame,
    effect_column: str = "main_r2_delta",
    factor_column: str = "environment",
    consistent_ratio: float = 0.75,
    ci_by_cell_line: Optional[Dict[Tuple, Dict[str, Tuple[float, float]]]] = None,
    config: Optional[AnalysisConfig] = None,
) -> pd.DataFrame:
    """每个 (split, model, factor) 的 各 cell-line effect + context 标签 + 诊断列。

    ci_by_cell_line: {(split_type, factor): {cell_line: (lo, hi)}} —— bootstrap 得到的
    per-cell-line effect CI; 缺失时只用方向 + 幅度异质性 (绝不伪造 CI)。
    """
    if main_effects is None or main_effects.empty:
        return pd.DataFrame()
    keys = ["split_type", "model", factor_column]
    rows: List[Dict] = []
    for (split, model, factor), group in main_effects.groupby(keys, dropna=False):
        cell_map = {
            str(r["cell_line"]): float(r[effect_column])
            for _, r in group.iterrows()
            if pd.notna(r.get(effect_column))
        }
        ci_map = (ci_by_cell_line or {}).get((split, factor), {})
        detail = classify_cellline_consistency_detail(
            cell_map, ci_map, consistent_ratio=consistent_ratio, config=config)
        cell_summary = {f"effect_{cl}": v for cl, v in cell_map.items()}
        ci_summary = {f"ci_low_{cl}": (ci_map.get(cl) or (None, None))[0] for cl in cell_map}
        ci_summary.update({f"ci_high_{cl}": (ci_map.get(cl) or (None, None))[1]
                           for cl in cell_map})
        rows.append({
            "split_type": split,
            "model": model,
            "factor": factor,
            "factor_type": "environment",
            "n_cell_lines": detail["n_cell_lines"],
            "consensus_direction": detail["consensus_direction"],
            "context_label": detail["label"],
            "majority_ratio": detail["majority_ratio"],
            "minority_ratio": detail["minority_ratio"],
            "heterogeneity": detail["heterogeneity"],
            "ci_overlap_relaxed": detail["ci_overlap_relaxed"],
            "context_reason": detail["reason"],
            **cell_summary,
            **ci_summary,
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def consistency_counts(summary: pd.DataFrame) -> Dict[str, int]:
    if summary is None or summary.empty:
        return {}
    return summary["context_label"].value_counts().to_dict()
