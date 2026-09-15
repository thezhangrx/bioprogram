"""analysis.evidence.integration — 跨模型/跨 cell-line 证据整合 (纯函数)。

**Evidence Tier 的权威实现就在本模块** (`classify_evidence_tier` + `environment_evidence_matrix`)。
`analysis/evidence/rules.py` 的旧 SNR/FDR 分档规则**未进入生产流水线**, 已删除, 以避免两套定义。

术语纪律 (禁止混用):
    Effect        效应大小/预测性能增量/反事实模型效应 (ΔR²、系数、ISM Δ、enrichment effect)
    Importance    模型预测归因或依赖程度 (SHAP/IG/ISM 幅值/attention)
    Statistical   统计证据 (p / FDR / bootstrap CI / permutation)
    Robustness    跨模型、seed、cell line、split 的稳定性 (concordance / consistency / CI 稳定)
    Evidence Tier 对已有计算证据的 convergence / coverage / robustness 综合评级

Tier 明确**不代表**: effect size 排名、生物学重要性排名、因果证据、单纯的显著性排名。
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.cellline.consistency import (classify_cellline_consistency,
                                          classify_cellline_consistency_detail)
from analysis.config import AnalysisConfig
from analysis.schemas import EvidenceTier

DEFAULT_CONFIG = AnalysisConfig()


def direction_concordance(effects: Iterable[Optional[float]],
                          denominator: Optional[int] = None) -> Optional[float]:
    """方向一致率 = 支持多数方向的模型数 / **全部有效模型配置数** (R5)。

    * 分母默认 = 全部有限效应（有效模型）个数，**不因中性/精确零效应而缩小**；
      这避免了 "1 正 + 6 中性 → 1/1 = 100 %" 式的虚高。
    * 无效/发散模型应在进入本函数前按数据质量剔除（调用方已做），
      其分母由输出列 `concordance_denominator` 显式记录。
    * 传入 `denominator` 可复现旧口径（分母 = 非零方向数），仅供回归对照。
    * 不引入 dead-zone：`0` 仅指浮点精确为 0（本批无此情形）。
    """
    vals: List[float] = []
    for e in effects:
        d = _direction_of_effect(e)
        if d is not None:
            vals.append(1.0 if d == "+" else (-1.0 if d == "-" else 0.0))
    if not vals:
        return None
    nonzero = [v for v in vals if v != 0.0]
    if not nonzero:
        return None
    pos = sum(1 for v in nonzero if v > 0)
    majority = max(pos, len(nonzero) - pos)
    denom = int(denominator) if denominator is not None else len(vals)
    if denom <= 0:
        return None
    return majority / denom


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
    strong_stat_or_attribution: Optional[bool] = None,
    ci_crosses_zero: Optional[bool] = None,
    conflicting_direction: bool = False,
    config: AnalysisConfig = DEFAULT_CONFIG,
    effect_gate: Optional[bool] = None,
    statistical_gate: Optional[bool] = None,
    robustness_gate: Optional[bool] = None,
) -> EvidenceTier:
    """**唯一权威的 Evidence Tier 规则** (生产实现; 环境行与 motif 行共用)。

    三个门显式区分 (R3):
      effect_gate       : 该 factor 是否达到最小绝对预测增益 (|\u0394R\u00b2| >= evidence.min_absolute_delta_r2)
      statistical_gate  : 是否存在统计证据 (permutation 存在性证据 / motif FDR)
      robustness_gate   : 覆盖度以外的稳健性条件 (CI 不跨 0 且方向一致率达标)

    规则 (阈值全部来自 config, 不散落):
      1. 方向冲突, 或 config.evidence.ci_crosses_zero_forces_inconclusive 为真且 CI 跨 0 -> Inconclusive
      2. supporting >= consensus.min_coverage 且 (concordance 为空或 >= consensus.direction_concordance)
         且 robustness_gate 且 **可提升门** -> Tier 1
      3. supporting >= consensus.min_coverage -> Tier 2
      4. supporting == 1 且 (effect_gate 或 statistical_gate) -> Tier 3
      5. applicable == 0 -> No current evidence
      6. 其它 -> Inconclusive

    **可提升门** = effect_gate OR (statistical_gate AND
    evidence.statistical_gate_can_promote[默认 False])。
    即: 统计证据只能支持或限制候选, **不能单独**把未达到最小预测增益的 factor 提升为 Tier 1。
    本函数只做分级, 不改变任何 effect / 统计量, 也不做效应量排序。
    """
    # 兼容旧调用方 (仅传合并布尔量时, 视为 effect 门; motif 路径即如此)
    if effect_gate is None:
        effect_gate = bool(strong_stat_or_attribution)
    statistical_gate = bool(statistical_gate)
    if robustness_gate is None:
        robustness_gate = (concordance is None or
                           concordance >= config.consensus.direction_concordance)
    can_promote = bool(effect_gate or (statistical_gate and
                                       config.evidence.statistical_gate_can_promote))
    supportive = bool(effect_gate or statistical_gate)

    ci_blocks = bool(getattr(config.evidence, "ci_crosses_zero_forces_inconclusive", True))
    if conflicting_direction or (ci_blocks and ci_crosses_zero is not None and ci_crosses_zero):
        return EvidenceTier.INCONCLUSIVE
    if supporting_model_count >= config.consensus.min_coverage and \
            (concordance is None or concordance >= config.consensus.direction_concordance) and \
            robustness_gate and can_promote:
        return EvidenceTier.TIER1
    if supporting_model_count >= config.consensus.min_coverage:
        return EvidenceTier.TIER2
    if supporting_model_count == 1 and supportive:
        return EvidenceTier.TIER3
    if applicable_model_count == 0:
        return EvidenceTier.NONE
    return EvidenceTier.INCONCLUSIVE


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

    bootstrap_ci: per-factor CI 表 (analysis.stats.tasks.bootstrap_main_effects 输出),
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
        # effect 门: 最小**绝对**预测增益 (ΔR²), 不是统计显著性阈值。
        # R4: 统计单位 = 模型配置。默认用模型等权平均 |mean ΔR²| 判定 (M 个模型等权,
        #     不按样本量/细胞系加权, 不因某模型更极端而加权);
        #     旧口径 "any_model"(任一模型达标) 保留为敏感性分析。
        # 模型间异质性同时保留: median_effect / model_effects / model_direction_conflict。
        overall = float(np.mean(list(finite.values())))
        median_effect = float(np.median(list(finite.values())))
        signs = {_direction_of_effect(e) for e in finite.values()}
        model_direction_conflict = bool(("+" in signs) and ("-" in signs))
        thr = float(config.evidence.min_absolute_delta_r2)
        mode = str(getattr(config.evidence, "effect_gate_mode", "model_mean"))
        if mode == "any_model":
            effect_gate_value = float(max(abs(e) for e in finite.values()))
        else:
            effect_gate_value = float(abs(overall))
        effect_gate_pass = bool(effect_gate_value >= thr)
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
        # R3: robustness 门 = 方向一致率达标 且 CI 不跨 0（与 Tier1 的既有条件等价, 显式化）
        robustness_gate = bool(
            (concordance is None or concordance >= config.consensus.direction_concordance)
            and not (ci_crosses_zero is True))

        # ---- permutation p / FDR (只有真实零假设检验的结果才在这里) ----
        perm_p = perm_fdr = None
        perm_status = "not_run"
        # ---- permutation: Minimal Edge-level FDR across Tested Contexts (R2) ----
        # 语义 = existence-oriented evidence（"该 factor 是否至少在一个 tested context 中有统计证据"），
        # **不是** factor-level FDR。选择方式是 extremum selection（跨上下文取最小），
        # 因此必须同时记录参与选择的上下文数与 FWER 上界。
        min_edge_fdr = None
        n_contexts = n_contexts_after_dedup = 0
        selected_context = None
        fwer_upper_bound = None
        if permutation is not None and not permutation.empty:
            psub = permutation[permutation.get("factor").astype(str) == str(factor)] \
                if "factor" in permutation.columns else permutation.iloc[0:0]
            # 显式限定为因子主效应检验（交互行的 factor 名为 "a*b"，本不会命中，此处写明以防歧义）
            if "test_type" in psub.columns:
                psub = psub[psub["test_type"].astype(str) == "environment_main_effect"]
            psub = psub.dropna(subset=["p_value"]) if "p_value" in psub.columns else psub.iloc[0:0]
            if len(psub):
                perm_status = "ok"
                n_contexts = int(len(psub))
                # 去重：同一 (cell_line, model, observed_effect, p_value) 在不同 split 下重复出现
                # （本批 all ≡ single）→ 只计一次，得到"有效独立上下文数"的保守近似。
                if {"cell_line", "model", "observed_effect", "p_value"}.issubset(psub.columns):
                    dup = psub.duplicated(subset=["cell_line", "model", "observed_effect",
                                                  "p_value"], keep="first")
                    n_contexts_after_dedup = int(len(psub) - int(dup.sum()))
                else:
                    n_contexts_after_dedup = n_contexts
                pvals = pd.to_numeric(psub["p_value"], errors="coerce")
                perm_p = float(pvals.min())
                fdr_vals = pd.to_numeric(psub.get("FDR"), errors="coerce").dropna() \
                    if "FDR" in psub.columns else pd.Series(dtype=float)
                if len(fdr_vals):
                    min_edge_fdr = float(fdr_vals.min())
                    perm_fdr = min_edge_fdr
                    i_min = psub.loc[pd.to_numeric(psub["FDR"], errors="coerce") == min_edge_fdr]
                    r_min = i_min.iloc[0]
                    selected_context = "/".join(str(r_min.get(k)) for k in
                                                ("split_type", "cell_line", "model"))
                    # Bonferroni 上界（正相关下保守）：跨上下文选择的最小 p 的 family-wise 上界
                    fwer_upper_bound = float(min(1.0, perm_p * max(n_contexts_after_dedup, 1)))
        # 统计门: 该 factor 是否至少在一个 tested context 中达到 edge 级 FDR 阈值。
        # R2 只改语义与 provenance, 不改变该门的布尔值（R3 再改提升规则）。
        statistical_gate_pass = bool(perm_fdr is not None and
                                     perm_fdr < config.statistical.fdr_weak)
        strong_evidence = bool(effect_gate_pass or statistical_gate_pass)
        basis = ("both" if (effect_gate_pass and statistical_gate_pass)
                 else "absolute_effect" if effect_gate_pass
                 else "permutation_fdr" if statistical_gate_pass else "none")

        if cell_label == "Context-conflicting":
            tier = EvidenceTier.INCONCLUSIVE
        else:
            tier = classify_evidence_tier(
                applicable_model_count=len(finite),
                supporting_model_count=supporting,
                concordance=concordance,
                ci_crosses_zero=ci_crosses_zero,
                config=config,
                effect_gate=effect_gate_pass,
                statistical_gate=statistical_gate_pass,
                robustness_gate=robustness_gate,
            )
        rows.append({
            "feature": factor,
            "feature_type": "environment",
            "applicable_models": ";".join(sorted(finite)),
            "coverage": len(finite),
            "direction_concordance": concordance,
            "concordance_denominator": len(finite),          # R5: 全部有效模型, 不因中性缩小
            "n_neutral_models": int(sum(1 for e in finite.values() if e == 0.0)),
            "cell_line_consistency": cell_label,
            "overall_effect": round(overall, 6),
            "model_effects": ";".join(f"{m}={e:.4f}" for m, e in sorted(finite.items())),
            "unstable_rows_excluded": int(n_excluded),
            # --- Tier 门的 provenance (不改变任何统计量, 只把判定依据显式留痕) ---
            "effect_gate_pass": effect_gate_pass,
            "effect_gate_mode": mode,
            "effect_gate_value": round(effect_gate_value, 6),
            "median_effect": round(median_effect, 6),
            "n_models": len(finite),
            "model_direction_conflict": model_direction_conflict,
            "statistical_gate_pass": statistical_gate_pass,
            "robustness_gate_pass": robustness_gate,
            "tier_promotion_gate": (
                "effect" if effect_gate_pass
                else "statistical" if (statistical_gate_pass and
                                       config.evidence.statistical_gate_can_promote)
                else "statistical(disabled)" if statistical_gate_pass else "none"),
            "strong_evidence_basis": basis,
            "min_absolute_delta_r2": config.evidence.min_absolute_delta_r2,
            "permutation_selection": "min FDR over rows of this factor",
            "ci_low": ci_low,
            "ci_high": ci_high,
            "ci_excludes_zero": ci_excludes_zero,
            "n_bootstrap": n_bootstrap,
            "bootstrap_status": bootstrap_status,
            "permutation_p": perm_p,
            "permutation_fdr": perm_fdr,
            "permutation_status": perm_status,
            # --- R2: existence-oriented permutation evidence 的 provenance ---
            "min_edge_fdr": min_edge_fdr,
            "n_contexts": n_contexts,
            "n_contexts_after_dedup": n_contexts_after_dedup,
            "selected_context": selected_context,
            "selection_basis": "minimum_edge_level_FDR_across_tested_contexts",
            "statistical_evidence_role": "existence_oriented",
            "fwer_upper_bound": fwer_upper_bound,
            "extremum_note": ("min over tested contexts = post-selection extremum; "
                              "NOT a factor-level FDR (no family-wise control)"),
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
