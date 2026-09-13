"""analyse.evidence.integration — 跨模型/跨 cell-line 证据整合 (纯函数)。"""
from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from analyse.cellline.consistency import (classify_cellline_consistency,
                                          classify_cellline_consistency_detail)
from analyse.config import AnalysisConfig
from analyse.schemas import EvidenceRecord, EvidenceTier

DEFAULT_CONFIG = AnalysisConfig()


def direction_concordance(effects: Iterable[Optional[float]]) -> Optional[float]:
    """方向一致率: 去零方向中多数方向占比。无有效方向返回 None。"""
    signs: List[str] = []
    for e in effects:
        d = _direction_of_effect(e)
        if d and d != "0":
            signs.append(d)
    if not signs:
        return None
    counts = Counter(signs)
    return max(counts.values()) / len(signs)


def _direction_of_effect(effect: Optional[float]) -> Optional[str]:
    if effect is None:
        return None
    try:
        if np.isnan(float(effect)):
            return None
    except (TypeError, ValueError):
        return None
    e = float(effect)
    return "+" if e > 0 else ("-" if e < 0 else "0")


def classify_evidence_tier(
    applicable_model_count: int,
    supporting_model_count: int,
    concordance: Optional[float],
    strong_stat_or_attribution: bool,
    ci_crosses_zero: Optional[bool],
    conflicting_direction: bool = False,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> EvidenceTier:
    """按 132 节第 18 条规则给出 Tier。"""
    if conflicting_direction or (ci_crosses_zero is not None and ci_crosses_zero):
        return EvidenceTier.INCONCLUSIVE
    if supporting_model_count >= config.consensus.min_coverage and \
            (concordance is None or concordance >= config.consensus.direction_concordance) and \
            strong_stat_or_attribution:
        return EvidenceTier.TIER1
    if supporting_model_count >= config.consensus.min_coverage:
        return EvidenceTier.TIER2
    if supporting_model_count == 1 and strong_stat_or_attribution:
        return EvidenceTier.TIER3
    if applicable_model_count == 0:
        return EvidenceTier.NONE
    return EvidenceTier.INCONCLUSIVE


def evidence_record_row(record: EvidenceRecord) -> Dict:
    """Evidence matrix CSV 行 (跨模型列保持 None=不可用/未测, 不填 0)。"""
    stat = record.statistical[-1] if record.statistical else None
    attr = record.attribution
    return {
        "feature": record.feature,
        "feature_type": record.feature_type,
        "applicable_models": ";".join(record.applicable_models),
        "coverage": record.coverage,
        "direction_concordance": record.direction_concordance,
        "cell_line_consistency": record.cell_line_consistency,
        "overall_effect": record.overall_effect,
        "overall_importance": record.overall_importance,
        "statistical_evidence": stat.evidence_class.value if stat else None,
        "statistical_p": stat.p_value if stat else None,
        "statistical_fdr": stat.fdr if stat else None,
        "attribution_n_models": len(attr),
        "evidence_tier": record.tier.value,
        "note": record.note,
    }


def environment_evidence_matrix(
    main_effects: pd.DataFrame,
    cellline_summary: Optional[pd.DataFrame] = None,
    config: AnalysisConfig = DEFAULT_CONFIG,
    bootstrap_ci: Optional[pd.DataFrame] = None,
    permutation: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    环境因素证据矩阵 (环境级 factor):
      per (model, factor): 跨 split/cell-line 平均 main_r2_delta -> 方向;
      factor 级: coverage=有有限效应的模型数, direction concordance,
      overall effect=模型均值, tier 按规则分级。

    bootstrap_ci: per-factor CI 表 (analyse.stats.tasks.bootstrap_main_effects 输出),
                  含 feature/estimate/ci_low/ci_high/excludes_zero/n_bootstrap/status;
                  只有 n_bootstrap >= config.evidence.min_bootstrap_iterations 的 CI 才参与
                  tier 判定 (CI 跨 0 -> Inconclusive), 未接通时该列保持 None。
    permutation:  per-factor permutation 结果 (p_value/FDR), 用于补充 statistical evidence;
                  没有 p-value 的指标 (SHAP/IG/ISM/Attention/SNR) 绝不进入这里。

    注意: 本矩阵是 Environment contribution decomposition (Effect);
          Model SHAP/IG 等 importance 在 attribution_summary.csv, 不混入。
    """
    if main_effects is None or main_effects.empty:
        return pd.DataFrame()
    factor_col = "environment"
    # 数值不稳定隔离: |Δ| 超阈值的上下文不进证据矩阵 (对应 anomaly, 非删除)
    stable = main_effects
    if "main_r2_delta" in stable.columns:
        stable = stable[np.abs(pd.to_numeric(stable["main_r2_delta"], errors="coerce")) <
                        config.consensus.unstable_effect_threshold]
    model_mean = stable.groupby(["model", factor_col], dropna=False)["main_r2_delta"] \
        .mean().reset_index()
    rows = []
    for factor, sub in model_mean.groupby(factor_col, dropna=False):
        effects = {str(r["model"]): float(r["main_r2_delta"]) for _, r in sub.iterrows()}
        finite = {m: e for m, e in effects.items() if e == e}
        n_excluded = int((main_effects[main_effects[factor_col].astype(str) == factor]).shape[0]) \
            - int(len(sub))
        if not finite:
            continue
        concordance = direction_concordance(list(finite.values()))
        strong = any(abs(e) >= config.consensus.environment_strong_effect
                     for e in finite.values())
        overall = float(np.mean(list(finite.values())))
        # supporting = 有效且方向与总体一致的模型数
        majority_sign = "+" if overall > 0 else ("-" if overall < 0 else "0")
        supporting = sum(1 for e in finite.values()
                         if (e > 0 and majority_sign == "+") or (e < 0 and majority_sign == "-"))
        cell_label: Optional[str] = None
        if cellline_summary is not None and not cellline_summary.empty:
            groups = cellline_summary[cellline_summary["factor"] == factor]["context_label"]
            if len(groups):
                cell_label = groups.value_counts().idxmax()
        # ---- bootstrap CI (真正的样本级/跨模型不确定性) ----
        ci_low = ci_high = None
        ci_excludes_zero = None
        n_bootstrap = 0
        bootstrap_status = "unavailable"
        if bootstrap_ci is not None and not bootstrap_ci.empty and "feature" in bootstrap_ci.columns:
            hit = bootstrap_ci[bootstrap_ci["feature"].astype(str) == str(factor)]
            if len(hit):
                h = hit.iloc[0]
                n_bootstrap = int(h.get("n_bootstrap") or 0)
                bootstrap_status = str(h.get("status", "unavailable"))
                if (bootstrap_status == "ok" and
                        n_bootstrap >= int(config.evidence.min_bootstrap_iterations)):
                    ci_low = None if pd.isna(h.get("ci_low")) else float(h["ci_low"])
                    ci_high = None if pd.isna(h.get("ci_high")) else float(h["ci_high"])
                    if ci_low is not None and ci_high is not None:
                        ci_excludes_zero = not (ci_low <= 0 <= ci_high)
        ci_crosses_zero = (None if ci_excludes_zero is None else (not ci_excludes_zero))

        # ---- permutation p / FDR (只有真实零假设检验的结果才在这里) ----
        perm_p = perm_fdr = None
        perm_status = "not_run"
        if permutation is not None and not permutation.empty:
            psub = permutation[permutation.get("factor").astype(str) == str(factor)] \
                if "factor" in permutation.columns else permutation.iloc[0:0]
            pvals = pd.to_numeric(psub.get("p_value"), errors="coerce").dropna() \
                if "p_value" in psub.columns else pd.Series(dtype=float)
            if len(pvals):
                perm_p = float(pvals.min())
                fdr_vals = pd.to_numeric(psub.get("FDR"), errors="coerce").dropna() \
                    if "FDR" in psub.columns else pd.Series(dtype=float)
                perm_fdr = float(fdr_vals.min()) if len(fdr_vals) else None
                perm_status = "ok"
        statistical_support = bool(perm_fdr is not None and
                                   perm_fdr < config.statistical.fdr_weak)
        strong_evidence = bool(strong or statistical_support)

        if cell_label == "Context-conflicting":
            tier = EvidenceTier.INCONCLUSIVE
        else:
            tier = classify_evidence_tier(
                applicable_model_count=len(finite),
                supporting_model_count=supporting,
                concordance=concordance,
                strong_stat_or_attribution=strong_evidence,
                ci_crosses_zero=ci_crosses_zero,
                config=config,
            )
        rows.append({
            "feature": factor,
            "feature_type": "environment",
            "applicable_models": ";".join(sorted(finite)),
            "coverage": len(finite),
            "direction_concordance": concordance,
            "cell_line_consistency": cell_label,
            "overall_effect": round(overall, 6),
            "model_effects": ";".join(f"{m}={e:.4f}" for m, e in sorted(finite.items())),
            "unstable_rows_excluded": int(n_excluded),
            "ci_low": ci_low,
            "ci_high": ci_high,
            "ci_excludes_zero": ci_excludes_zero,
            "n_bootstrap": n_bootstrap,
            "bootstrap_status": bootstrap_status,
            "permutation_p": perm_p,
            "permutation_fdr": perm_fdr,
            "permutation_status": perm_status,
            "evidence_tier": tier.value,
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def tier_from_value(value: str):
    for tier in EvidenceTier:
        if tier.value == value:
            return tier
    return EvidenceTier.NONE


def direction_of(effect: Optional[float]) -> Optional[str]:
    """公开方向函数 (内部一致)。"""
    return _direction_of_effect(effect)
