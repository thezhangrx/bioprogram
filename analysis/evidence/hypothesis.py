"""analysis.evidence.hypothesis — 生物假设语言 (受控措辞)。

禁止: causes / proves / determines; 只能用 associated / suggests / supports /
candidate factor / context-dependent / testable hypothesis。
"""
from __future__ import annotations


def _safe_int(value, default: int = 0) -> int:
    """coverage 等字段容错解析: 非数值 (如 '1/1 model families') 不抛错。"""
    try:
        return int(float(str(value).split("/")[0]))
    except (TypeError, ValueError):
        return default

from typing import Dict, List

from analysis.schemas import EvidenceRecord, EvidenceTier

_ALLOWED_VERBS = ("associated with", "suggests", "supports", "candidate", "context-dependent")


def generate_hypotheses_for_record(record: EvidenceRecord) -> List[Dict[str, str]]:
    """为 EvidenceRecord 生成结构化假设 (每条含证据/效应/不确定性/验证建议)。"""
    tier = record.tier
    stat = record.statistical[-1] if record.statistical else None
    if (record.overall_effect or 0) > 0:
        direction_word = "positively"
    elif (record.overall_effect or 0) < 0:
        direction_word = "negatively"
    else:
        direction_word = "not clearly"
    base = (f"{record.feature} is a candidate factor {direction_word} "
            f"associated with editing efficiency")
    hypotheses: List[Dict[str, str]] = []

    if tier in (EvidenceTier.TIER1, EvidenceTier.TIER2):
        if record.cell_line_consistency == "Context-conflicting":
            support_phrase = "suggests context-dependent contributions"
        else:
            support_phrase = "strongly supports" if tier == EvidenceTier.TIER1 else "supports"
        sentence = (
            f"{base}; the observed cross-model evidence {support_phrase} "
            f"a role consistent with {record.feature_type} regulation of CRISPR activity."
        )
    elif tier == EvidenceTier.TIER3:
        sentence = (
            f"{base}; the observed model-specific attribution evidence suggests a "
            f"feature warranting targeted follow-up (single-model support)."
        )
    elif tier == EvidenceTier.INCONCLUSIVE:
        sentence = (
            f"The observed evidence for {record.feature} is inconclusive: effects were "
            f"unstable or directionally conflicting across models/cell lines."
        )
    else:
        sentence = (
            f"No current evidence in this dataset supports a stable role of {record.feature}; "
            f"this is not evidence of absence of effect."
        )

    interpretation = (
        f"If {record.feature_type} is sequence-level, a testable interpretation is that "
        f"{record.feature} modulates sgRNA/DNA hybrid stability or epigenetic accessibility; "
        f"if environment-level, that the feature marks permissive chromatin context."
    )
    suggested_validation = (
        f"Suggested validation: {record.feature}-targeted perturbation (e.g., motif mutation "
        f"or epigenetic inhibition) in the supporting cell lines, with editing-efficiency readout."
    )
    hypotheses.append({
        "feature": record.feature,
        "hypothesis": sentence,
        "observed_evidence": record.tier.value,
        "effect_size": f"{record.overall_effect}" if record.overall_effect is not None else "unavailable",
        "uncertainty": "CI crosses 0" if record.note == "ci_crosses_zero" else "see CI columns",
        "supporting_models": ";".join(record.applicable_models) or "unavailable",
        "supporting_statistical_test": stat.test if stat else "unavailable",
        "possible_biological_interpretation": interpretation,
        "suggested_validation_experiment": suggested_validation,
    })
    return hypotheses
