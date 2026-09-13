"""analyse.evidence.rules — Evidence 标签规则 (阈值一律来自 config, 不散落)。"""
from __future__ import annotations

from typing import Optional

from analyse.config import AnalysisConfig
from analyse.schemas import EvidenceStrength

DEFAULT_CONFIG = AnalysisConfig()


def classify_statistical_by_fdr(
    fdr: Optional[float],
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> Optional[EvidenceStrength]:
    """仅用于真实假设检验输出的 FDR。"""
    if fdr is None or fdr != fdr:  # NaN
        return None
    rule = config.statistical
    if fdr < rule.fdr_strong:
        return EvidenceStrength.STRONG_STATISTICAL
    if fdr < rule.fdr_moderate:
        return EvidenceStrength.MODERATE_STATISTICAL
    if fdr < rule.fdr_weak:
        return EvidenceStrength.WEAK_STATISTICAL
    return None


def classify_attribution(
    snr: Optional[float],
    effect_magnitude: Optional[float],
    min_effect_size: Optional[float] = None,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> Optional[EvidenceStrength]:
    """
    归因/稳健性标签 (SNR 不是 statistical significance):
      Strong attribution 需要 SNR>=阈值 且 |effect|>=min_effect_size ("足够效应量")。
    """
    if snr is None or snr != snr or effect_magnitude is None or effect_magnitude != effect_magnitude:
        return None
    rule = config.attribution
    min_effect = min_effect_size if min_effect_size is not None else rule.min_effect_size
    # "足够效应量" 门槛适用于所有 attribution 级别:
    # 防止 effect 极小但 variance 更小导致的 SNR 虚高
    if abs(effect_magnitude) < min_effect:
        return None
    if snr >= rule.snr_threshold:
        return EvidenceStrength.STRONG_ATTRIBUTION
    if snr >= rule.snr_moderate:
        return EvidenceStrength.MODERATE_ATTRIBUTION
    if snr >= rule.snr_weak:
        return EvidenceStrength.WEAK_ATTRIBUTION
    return None


def classify_mutation_effect(
    snr: Optional[float],
    delta_mean: Optional[float],
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> Optional[EvidenceStrength]:
    """ISM 突变效应标签 (nucleotide substitution effect, 不是 feature importance)。"""
    if snr is None or delta_mean is None:
        return None
    rule = config.attribution
    if snr >= rule.snr_threshold and abs(delta_mean) >= rule.min_effect_size:
        return EvidenceStrength.STRONG_MUTATION_EFFECT
    return None


def direction_of(effect: Optional[float]) -> Optional[str]:
    if effect is None or effect != effect:
        return None
    return "+" if effect > 0 else ("-" if effect < 0 else "0")
