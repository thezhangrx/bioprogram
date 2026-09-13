"""analyse.config — 集中科学规则配置 (阈值不得散落各模块)。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class AttributionRuleConfig:
    """归因稳健性阈值: SNR 仅作为 robustness/attribution strength, 不是统计显著。"""

    snr_threshold: float = 2.5          # "strong" 归因的 SNR 下界
    snr_moderate: float = 1.8
    snr_weak: float = 1.2
    min_effect_size: float = 0.005      # "足够效应量" 下限 (可配置, 非写死 universal)
    method: str = "mean_over_std"


@dataclass(frozen=True)
class StatisticalRuleConfig:
    """统计检验证据分级 (仅用于真正假设检验结果: 如线性 t/p/FDR、ANOVA、enrichment)。"""

    fdr_strong: float = 0.001
    fdr_moderate: float = 0.01
    fdr_weak: float = 0.05
    fdr_nominal: float = 0.10


@dataclass(frozen=True)
class ConsensusRuleConfig:
    """跨模型/跨 cell-line 一致性规则。"""

    min_coverage: int = 2            # 至少 2 个适用模型才算 Convergent evidence
    direction_concordance: float = 0.80
    bootstrap_ci_exclude_zero_alpha: float = 0.05
    cellline_consistent_ratio: float = 0.75
    environment_strong_effect: float = 0.01   # env 级“强效应”阈值 (可配置)
    unstable_effect_threshold: float = 10.0  # |Δ| 超过视为数值不稳定, 不进证据矩阵


@dataclass(frozen=True)
class CelllineConsistencyConfig:
    """cell-line context 判定阈值 (方向 + 幅度异质性 + CI 重叠, 不只 all_same_sign)。

    标签语义 (全部可达):
      Context-consistent   方向一致且幅度同质
      Context-dependent    方向一致但幅度异质; 或多数方向一致且存在少数反向但未达冲突线
      Context-conflicting  反向占比达到 conflicting_ratio
      Uncertain            有效 cell line 数不足 / 证据缺失
    """

    min_cell_lines: int = 2
    consistent_ratio: float = 0.75     # 同向占比 >= 该值 -> consistent 候选
    conflicting_ratio: float = 0.25    # 反向占比 >= 该值 -> conflicting
    heterogeneity_ratio: float = 2.0   # max|effect| / median|effect| 超过 -> 幅度异质 -> dependent
    ci_overlap_relaxes: bool = True    # 反向 cell line 的 CI 与主体重叠时不升级为 conflicting


@dataclass(frozen=True)
class EvidenceRuleConfig:
    """CI 进入 Evidence Tier 的策略 (bootstrap 未接通时不得伪造 CI)。"""

    ci_alpha: float = 0.05
    ci_crosses_zero_forces_inconclusive: bool = True
    min_bootstrap_iterations: int = 200     # 迭代数不足的 CI 不参与 tier 判定


@dataclass(frozen=True)
class AnovaRuleConfig:
    """factorial ANOVA 运行条件与输出定义 (数据不足 -> unavailable, 绝不伪造)。"""

    enabled_default: bool = True
    min_observations: int = 32          # 少于 -> unavailable(insufficient_data)
    min_residual_df: int = 5            # 残差自由度下限
    include_interactions: bool = True
    run_per_group: bool = True          # 额外做 per (split, cell, model) 加性主效应 ANOVA
    effect_size_metric: str = "partial_eta_squared"
    ci_iterations: int = 400            # effect contrast 的 bootstrap CI 迭代数
    block_factors: tuple = ("model", "cell_line", "split_type")


@dataclass(frozen=True)
class MotifDiscoveryConfig:
    """Sequence motif discovery 阈值 (全部集中在此, 不散落代码)。

    输入边界 (重要): 当前批次只有 **无符号** attribution magnitude (CNN_IG/CNN_ISM 均为正值),
    因此 seqlet 不能按 attribution 符号分正负; 方向改由
    "carrier vs background 的 measured efficacy 对比" 给出 (direction_source 列显式记录),
    绝不伪造 attribution sign。
    """

    # 数据源
    data_root: str = "data/proceeded_data"      # <cell_line>_metadata.csv (+ _184.csv)
    primary_methods: tuple = ("cnn_ism", "cnn_ig")      # 主要 motif extractor
    supporting_methods: tuple = ("transformer_attention",)   # 只作 supporting evidence
    transformer_ig_method: str = "transformer_ig"       # 存在才用于 motif (当前不存在)
    contexts: tuple = ("sequence", "all")       # 只在这些 environment 上下文提 motif
    model_families: tuple = ("cnn",)            # MLP/XGB/Linear 不作为 motif extractor

    # seqlet 提取
    max_length: int = 12
    attribution_quantile: float = 0.90          # 位置级 attribution 阈值分位
    continuity_quantile: float = 0.75           # 局部连续性阈值分位
    continuity_min_positions: int = 2           # 至少连续多少个位置达标
    max_seqlets_per_sample: int = 2
    min_seqlet_score: float = 0.0               # 绝对下限 (0 = 只用分位)

    # 聚类 / consensus
    similarity_threshold: float = 0.90          # 与 cluster consensus 的最小一致率 (短 motif 必须更严)
    merge_similarity: float = 0.95              # 聚类后 consensus 再合并的相似度
    max_ambiguous_fraction: float = 0.34        # 退化位点占比上限, 超过 -> status=exploratory
    degenerate_fraction: float = 0.25           # 次优碱基频率 >= 该值 -> 退化码
    min_length: int = 4                         # motif 长度下限 (3 太短难有特异性)

    # support / stability
    min_seqlet_support: int = 30
    min_sample_support: int = 20
    max_motifs_per_context: int = 8      # 每个 context 保留的高支持 motif 上限
    max_exploratory_per_context: int = 3 # 模糊度过高的 motif 只留少量作 exploratory
    min_cellline_support: int = 2
    stability_similarity: float = 0.80          # 跨 cell-line/model 视为同一 motif 的相似度

    # 位置 / region (schema 未定义 seed/PAM -> 默认不假设, 全部 Other)
    region_ranges: tuple = ()                   # ((name, start, end), ...) 1-based 闭区间
    preferred_position_bins: int = 5

    # enrichment (独立可选步骤)
    enrichment_enabled_default: bool = False
    enrichment_foreground_quantile: float = 0.67   # 高效序列 = efficacy 上三分位
    enrichment_background: str = "all_eligible_sequences"
    enrichment_min_carriers: int = 5
    enrichment_fdr: float = 0.05

    # evidence
    evidence_strong_min_models: int = 2
    evidence_strong_fdr: float = 0.05


@dataclass(frozen=True)
class FdrFamilyConfig:
    """multiple-testing family 定义: 不同科学问题绝不并入同一个 FDR family。"""

    enabled_families: tuple = ("environment_permutation_edge",
                               "environment_permutation_main",
                               "environment_permutation_interaction",
                               "environment_anova",
                               "environment_anova_group",
                               "motif_enrichment")
    min_family_size: int = 2            # family 规模不足时不做校正 (记录 not_applicable)


@dataclass(frozen=True)
class QCConfig:
    """QC 门禁 (detection 层), 不负责任何用户科学决策。"""

    environment_missing_rate_limit: float = 0.30   # 环境整体缺失率 >30% -> Ineligible
    strict_complete_gate: float = 70.0             # 70% 门禁 (沿用)
    ambiguous_detection_only: bool = True          # 只检测, 处理策略由 Wizard 决策


@dataclass(frozen=True)
class AnalysisConfig:
    """分析全局配置 (集中入口, 供 pipeline 读取)。"""

    attribution: AttributionRuleConfig = field(default_factory=AttributionRuleConfig)
    statistical: StatisticalRuleConfig = field(default_factory=StatisticalRuleConfig)
    consensus: ConsensusRuleConfig = field(default_factory=ConsensusRuleConfig)
    cellline: CelllineConsistencyConfig = field(default_factory=CelllineConsistencyConfig)
    evidence: EvidenceRuleConfig = field(default_factory=EvidenceRuleConfig)
    anova: AnovaRuleConfig = field(default_factory=AnovaRuleConfig)
    fdr: FdrFamilyConfig = field(default_factory=FdrFamilyConfig)
    motif: MotifDiscoveryConfig = field(default_factory=MotifDiscoveryConfig)
    qc: QCConfig = field(default_factory=QCConfig)
    bootstrap_iterations: int = 2000
    bootstrap_seed: int = 2024
    bootstrap_alpha: float = 0.05
    permutation_iterations: int = 1000
    random_seed: int = 42

    def as_dict(self) -> Dict:
        from dataclasses import asdict
        return asdict(self)
