"""analysis.schemas — 统一科学记录类型与证据标签。

Evidence Tier 的唯一权威实现: analysis/evidence/integration.py::classify_evidence_tier。

术语纪律:
    Effect           影响大小/方向 (ΔR²、系数、ISM effect、enrichment effect)
    Importance       模型依赖 (SHAP/IG/ISM/Attention/Gain/PFI/LOFO)
    StatisticalEvidence 只有明确假设检验/CI 才使用 (p/FDR/CI 等)

禁止: 对 SHAP/IG/ISM/Gain 原始值做 FDR 后称为 statistical significance;
      SNR>=2.5 只能称为 attribution/robustness strength。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Evidence 标签 (统一证据强度语言, 替代纯星号)
# ---------------------------------------------------------------------------
class EvidenceTier(str, Enum):
    TIER1 = "Tier 1: Strong convergent evidence"
    TIER2 = "Tier 2: Moderate convergent evidence"
    TIER3 = "Tier 3: Model-specific / exploratory evidence"
    INCONCLUSIVE = "Inconclusive"
    NONE = "No current evidence"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvidenceClass(str, Enum):
    """科学结论必须归属的类别 (禁止混称)。"""

    STATISTICAL = "statistical evidence"
    ATTRIBUTION = "attribution evidence"
    PREDICTIVE = "predictive evidence"
    ROBUSTNESS = "robustness evidence"
    CROSS_MODEL = "cross-model evidence"
    CONTEXT = "context evidence"
    MUTATION = "mutation effect"


# ---------------------------------------------------------------------------
# 统一记录
# ---------------------------------------------------------------------------
@dataclass
class ExperimentRecord:
    """一条实验的元数据 + 同一 test cohort 指标。"""

    experiment_id: str
    model: str
    architecture: Optional[str]
    split_type: str
    cell_line: str
    environment: str
    seed: int
    n_train: int
    n_valid: int
    n_test: int
    r2: float
    mae: float
    rmse: float
    pearson: float
    spearman: float
    status: str = "completed"
    batch: Optional[str] = None
    source_file: Optional[str] = None
    raw: Dict = field(default_factory=dict)


@dataclass
class AttributionRecord:
    """单特征单方法归因记录 (importance, 不承载统计检验)。"""

    feature: str
    model: str
    architecture: Optional[str]
    split_type: str
    cell_line: str
    environment: str
    method: str                       # linear/xgboost_treeshap/mlp_ig/cnn_ism/cnn_ig/transformer_attention
    importance: float = float("nan")  # attribution magnitude (mean|value|)
    effect: Optional[float] = None    # 可选 signed effect (ISM Δ、linear coefficient 另见统计层)
    snr: float = float("nan")
    attention_entropy: Optional[float] = None
    source_file: Optional[str] = None


@dataclass
class StatisticalEvidence:
    """仅来自真实检验/CI 的统计证据 (无检验则字段留空, 禁止伪造)。"""

    feature: Optional[str] = None
    test: Optional[str] = None                # e.g. 'linear_t_fdr', 'anova', 'enrichment_fisher'
    effect: Optional[float] = None
    effect_size: Optional[float] = None
    statistic: Optional[float] = None         # t / F / z
    p_value: Optional[float] = None
    fdr: Optional[float] = None
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    n: Optional[int] = None
    direction: Optional[str] = None           # '+' / '-' / None
    evidence_class: EvidenceClass = EvidenceClass.STATISTICAL


@dataclass
class EnvironmentEffect:
    """条件/主效应/Shapley 环境贡献 (Effect 层; CI 存在性取决于是否运行 Bootstrap)。"""

    environment: str
    background: Optional[str]              # S (None 表示相对 sequence-only)
    split_type: str
    cell_line: str
    model: str
    delta_r2: Optional[float] = None
    delta_mae: Optional[float] = None
    delta_rmse: Optional[float] = None
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    main_effect: bool = False
    paired_cohort: bool = True
    eligible_n: Optional[int] = None


@dataclass
class CellLineEffect:
    """feature × cell_line 的 effect + 一致性判断。"""

    factor: str                              # sequence feature 或 environment
    cell_line: str
    effect: Optional[float] = None
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    direction: Optional[str] = None
    context_label: Optional[str] = None      # Context-consistent / Context-dependent / Context-conflicting


@dataclass
class MotifRecord:
    """序列 motif 候选 (统计 enrichment 只在真正检验后进行)。"""

    motif_id: str
    motif: str
    model: str
    cell_line: str
    enrichment_effect: Optional[float] = None
    enrichment_p: Optional[float] = None
    enrichment_fdr: Optional[float] = None
    stability: Optional[str] = None
    known_motif_hit: Optional[str] = None
    method: str = "seqlet-extraction"


@dataclass
class EvidenceRecord:
    """统一 evidence matrix 行 (跨模型整合后的 feature 级结论)。"""

    feature: str
    feature_type: str                        # nucleotide_position / environment / gc / motif
    applicable_models: List[str] = field(default_factory=list)
    coverage: int = 0
    direction_concordance: Optional[float] = None
    cell_line_consistency: Optional[str] = None
    overall_effect: Optional[float] = None
    overall_importance: Optional[float] = None
    statistical: List[StatisticalEvidence] = field(default_factory=list)
    attribution: List[AttributionRecord] = field(default_factory=list)
    environment: Optional[EnvironmentEffect] = None
    tier: EvidenceTier = EvidenceTier.NONE
    class_labels: List[EvidenceClass] = field(default_factory=list)
    note: Optional[str] = None
