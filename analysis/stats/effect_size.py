"""analysis.stats.effect_size — Effect 定义与 paired-baseline 原则。

Paired baseline 原则: ΔR²(e|S)=R²(S+e)-R²(S) 只在两模型使用同一
eligible cohort (最好同一 train/valid/test indices) 时才有意义;
否则差异可能来自样本组成而非环境贡献。
"""
from __future__ import annotations

from typing import Optional, Tuple


def delta_pair(baseline_value: float, expanded_value: float) -> float:
    """返回 expanded - baseline (效果方向保持: 正=提升)。"""
    return float(expanded_value) - float(baseline_value)


def compute_paired_increment(
    baseline_metric: float,
    expanded_metric: float,
    baseline_n: Optional[int] = None,
    expanded_n: Optional[int] = None,
    tolerance: float = 0,
) -> Tuple[float, bool]:
    """
    仅在 cohort 样本量一致 (或允许容差内) 时返回可信增量。

    返回 (increment, paired_ok); paired_ok=False 时增量不得用于科学归因。
    """
    if baseline_n is not None and expanded_n is not None:
        if abs(int(baseline_n) - int(expanded_n)) > tolerance:
            return float("nan"), False
    return delta_pair(baseline_metric, expanded_metric), True
