"""analysis.importance_metrics — Importance–ΔR² 二维图的“Y 轴指标注册表 + 证据筛选”规则。

设计原则 (与研究规范一致):
  * Effect / Importance / Robustness / StatisticalEvidence 四类语义**严格分离**;
  * Y 轴只使用“有方向或至少有明确归因幅度定义”的主指标 (primary), 并按模型选择:
        linear      : |Linear_Coefficient|      (FDR 仅作统计筛选, 不作 Y)
        xgboost     : TreeSHAP = mean(|SHAP|)  (Gain/Weight/Cover 仅 tooltip; SHAP_SNR 仅稳健性筛选)
        mlp         : MLP_IG = mean(|IG|)       (IG_SNR 仅稳健性筛选)
        cnn         : CNN_IG                    (ISM/ISM_SNR 属 counterfactual mutation, 不作本图 Y)
        transformer : 不可用 (未输出 Transformer_IG; Attention/Entropy 无方向, 只作支持性证据)
  * 归一化: 同一 (model, split_type, cell_line, context) 内按所选 factor 的 primary importance 求占比;
  * 严禁把 SNR/FDR/Attention 当作 effect, 也严禁把多指标加权成 "significance_score"。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# 环境因子 (本图默认分析单位 = 一个环境 factor, 而不是 position×channel)
ENV_FACTORS = ["ctcf", "dnase", "h3k4me3", "rrbs"]

# 证据筛选档位
FILTER_MODES = ("strict", "moderate", "all")


@dataclass(frozen=True)
class PrimaryMetricSpec:
    """模型主指标定义 (Y 轴)。"""

    model_key: str
    enabled: bool
    primary_field: Optional[str]        # CSV 中的字段名
    transform: str = "abs"              # abs | signed | None
    robustness_field: Optional[str] = None
    statistical_field: Optional[str] = None
    note: str = ""


PRIMARY_METRICS: Dict[str, PrimaryMetricSpec] = {
    "linear": PrimaryMetricSpec(
        "linear", True, "Linear_Coefficient", "abs",
        robustness_field=None, statistical_field="FDR",
        note="Y=|系数|; 方向由 signed 系数保留; FDR 仅用于统计筛选"),
    "xgboost": PrimaryMetricSpec(
        "xgboost", True, "TreeSHAP", "abs",
        robustness_field="SHAP_SNR",
        note="Y=mean(|SHAP|); Gain/Weight/Cover 为树内部重要性(无方向), 仅 tooltip"),
    "mlp": PrimaryMetricSpec(
        "mlp", True, "MLP_IG", "abs",
        robustness_field="IG_SNR",
        note="Y=mean(|IG|); IG_SNR 仅稳健性筛选"),
    "cnn": PrimaryMetricSpec(
        "cnn", True, "CNN_IG", "abs",
        robustness_field="ISM_SNR",
        note="Y=CNN_IG; 无 IG_SNR 输出 (不得假装存在); ISM_SNR 作为稳健性筛选但 ISM 语义为突变效应"),
    "transformer": PrimaryMetricSpec(
        "transformer", False, None, "abs",
        robustness_field="Attention_SNR",
        note="未输出 Transformer_IG (函数存在但从未调用/未入白名单); Attention 无方向, 不作为主 Y"),
}

# 明确“不作为 Y”的字段与原因 (写入 summary/importance_metric_selection.md)
NOT_USED_AS_Y: List[Tuple[str, str, str]] = [
    ("XGB_Gain", "xgboost", "树内部 importance (split gain), 无方向/无归因符号"),
    ("XGB_Weight", "xgboost", "树内部 importance (split 次数), 无方向"),
    ("XGB_Cover", "xgboost", "树内部 importance (覆盖样本数), 无方向"),
    ("SHAP_SNR", "xgboost", "归因稳健性 (mean/std), 不是 effect magnitude"),
    ("IG_SNR", "mlp", "归因稳健性, 用于筛选而非 Y"),
    ("CNN_ISM", "cnn", "counterfactual mutation effect (核苷酸替换), 属另一张 sequence 图"),
    ("ISM_SNR", "cnn", "突变效应稳健性, 仅用于筛选"),
    ("Transformer_Attention", "transformer", "注意力权重无正负方向, 不能当 effect"),
    ("Attention_Entropy", "transformer", "注意力集中度 (标量), 非 attribution magnitude"),
    ("Attention_SNR", "transformer", "注意力稳健性, 非 effect"),
    ("SE", "linear", "估计量标准误 (不确定性), 非 importance magnitude"),
    ("t_stat", "linear", "统计检验量, 非 importance magnitude"),
    ("p_value", "linear", "统计证据, 非 importance magnitude"),
    ("FDR", "linear", "统计证据 (多重校正 q 值), 用于筛选而非 Y"),
]


def metric_selection_rows() -> List[Dict[str, str]]:
    """生成指标选择说明表 (供 md 输出)。"""
    rows: List[Dict[str, str]] = []
    for key, spec in PRIMARY_METRICS.items():
        rows.append({
            "模型": key,
            "Y 轴主指标": spec.primary_field or "(unavailable)",
            "是否启用": "yes" if spec.enabled else "no",
            "稳健性字段": spec.robustness_field or "-",
            "统计字段": spec.statistical_field or "-",
            "说明": spec.note,
        })
    return rows


def evidence_strength(model_key: str,
                      primary_value: Optional[float],
                      robustness_value: Optional[float],
                      statistical_value: Optional[float],
                      *,
                      min_effect_size: float = 0.005,
                      snr_strong: float = 2.5,
                      snr_moderate: float = 1.8,
                      snr_weak: float = 1.2,
                      fdr_strong: float = 0.001,
                      fdr_moderate: float = 0.01,
                      fdr_weak: float = 0.05) -> Tuple[str, str]:
    """返回 (evidence_strength, reason)。

    linear      -> Statistical evidence (FDR 分档)
    xgb/mlp/cnn -> Attribution evidence (SNR 分档 + 最小效应量门槛)
    transformer -> 不参与主图
    """
    spec = PRIMARY_METRICS.get(model_key)
    if spec is None or not spec.enabled:
        return "unavailable", "model has no directional primary importance (e.g. Transformer IG missing)"
    if primary_value is None or not np.isfinite(primary_value):
        return "unavailable", "primary importance missing"
    if model_key == "linear":
        if statistical_value is None or not np.isfinite(statistical_value):
            return "unavailable", "FDR missing -> cannot claim statistical evidence"
        fdr = float(statistical_value)
        if fdr < fdr_strong:
            return "Strong statistical evidence", f"FDR={fdr:g} < {fdr_strong:g}"
        if fdr < fdr_moderate:
            return "Moderate statistical evidence", f"FDR={fdr:g} < {fdr_moderate:g}"
        if fdr < fdr_weak:
            return "Weak statistical evidence", f"FDR={fdr:g} < {fdr_weak:g}"
        return "not statistically supported", f"FDR={fdr:g} >= {fdr_weak:g}"
    # 非线性: attribution evidence
    if robustness_value is None or not np.isfinite(robustness_value):
        return "unavailable", "robustness (SNR) missing -> no attribution strength claim"
    snr = float(robustness_value)
    if abs(float(primary_value)) < float(min_effect_size):
        return "below min effect", f"|importance|={abs(float(primary_value)):g} < min_effect_size={min_effect_size:g}"
    if snr >= snr_strong:
        return "Strong attribution evidence", f"SNR={snr:.3g} >= {snr_strong:g}"
    if snr >= snr_moderate:
        return "Moderate attribution evidence", f"SNR={snr:.3g} >= {snr_moderate:g}"
    if snr >= snr_weak:
        return "Weak attribution evidence", f"SNR={snr:.3g} >= {snr_weak:g}"
    return "not attribution-supported", f"SNR={snr:.3g} < {snr_weak:g}"


def passes_filter(strength: str, mode: str = "strict") -> Tuple[bool, str]:
    """按 filter_mode 判定是否进入主图 (不修改任何科学量)。"""
    mode = str(mode).strip().lower()
    if mode not in FILTER_MODES:
        mode = "strict"
    if strength == "unavailable":
        return False, "evidence unavailable (missing metric), not drawn"
    if mode == "all":
        # 敏感性分析档: 只要有合法主指标就画, 包含 not-supported / below-min-effect,
        # 仅在图上用 marker/颜色区分证据等级, 不改变任何数值。
        return True, "filter_mode=all: any available importance drawn (sensitivity analysis)"
    if mode == "moderate":
        if strength.startswith(("Strong", "Moderate")):
            return True, "filter_mode=moderate: Strong+Moderate drawn"
        return False, f"filter_mode=moderate excludes: {strength}"
    # strict
    if strength.startswith("Strong"):
        return True, "filter_mode=strict: Strong evidence only"
    return False, f"filter_mode=strict excludes: {strength}"


def normalize_within_context(df: pd.DataFrame,
                             value_col: str = "importance_value",
                             out_col: str = "normalized_importance",
                             group_cols: Tuple[str, ...] = ("model", "split_type", "cell_line")) -> pd.DataFrame:
    """同 (model, split_type, cell_line) 内按 factor 求和做占比归一化。

    说明: 跨模型原始 importance 量纲不可比; 归一化后 Y 的含义 =
    “该 factor 在该模型该上下文的全部有效环境 attribution 中所占相对贡献”。
    """
    out = df.copy()
    vals = pd.to_numeric(out[value_col], errors="coerce")
    denom = vals.groupby([out[c] for c in group_cols]).transform("sum")
    with np.errstate(invalid="ignore", divide="ignore"):
        out[out_col] = np.where(denom > 0, vals / denom, np.nan)
    return out


def available_models(df: pd.DataFrame) -> List[str]:
    """当前数据里真正有可用主指标的模型 (按 registry 过滤)。"""
    if df is None or df.empty or "model" not in df.columns:
        return []
    out = []
    for m in sorted(df["model"].unique()):
        spec = PRIMARY_METRICS.get(str(m))
        if spec and spec.enabled:
            out.append(str(m))
    return out
