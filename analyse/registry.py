"""analyse.registry — 分析任务注册表 (新增分析 = 注册任务, 不改 GUI/核心流程)。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class AnalysisTaskSpec:
    task_id: str
    name: str
    category: str            # qc / statistics / biology / evidence
    dependencies: List[str] = field(default_factory=list)
    runner: Optional[Callable] = None
    basic: bool = True       # Basic 分析默认展示; False 归入 Advanced
    description: str = ""


_registry: Dict[str, AnalysisTaskSpec] = {}


def register_analysis(
    task_id: str,
    name: str,
    category: str,
    dependencies: Optional[List[str]] = None,
    runner: Optional[Callable] = None,
    basic: bool = True,
    description: str = "",
) -> None:
    if task_id in _registry:
        raise KeyError(f"analysis task already registered: {task_id}")
    _registry[task_id] = AnalysisTaskSpec(
        task_id=task_id, name=name, category=category,
        dependencies=list(dependencies or []), runner=runner,
        basic=basic, description=description,
    )


def registered_tasks() -> List[AnalysisTaskSpec]:
    return list(_registry.values())


def registry_to_dict() -> Dict:
    return {t.task_id: {"name": t.name, "category": t.category,
                        "dependencies": t.dependencies, "basic": t.basic,
                        "description": t.description,
                        "runner_registered": t.runner is not None}
            for t in _registry.values()}


# 内置任务声明 (runner=None 表示对应阶段实现尚未注册, availability 另由 validator 判定)
for _spec in [
    ("qc", "Data Quality Control", "qc", [], None, True, "批次级 QC/结果校验"),
    ("prediction", "Prediction & Generalization", "qc", ["qc"], None, True, ""),
    ("environment_conditional_effect", "Environment Conditional ΔR²", "biology",
     ["prediction"], None, True, ""),
    ("environment_main_effect", "Environment Main Effects", "biology",
     ["prediction"], None, True, ""),
    ("environment_factorial_dag", "Environment Factorial DAG (2^4 lattice)", "biology",
     ["environment_conditional_effect"], None, True,
     "16 combination nodes + 32 conditional edges; 缺失组合保留为 unavailable 节点"),
    ("environment_anova", "ANOVA / Factorial Statistics", "statistics",
     ["environment_main_effect"], None, False, "需要足够 factorial observations"),
    ("environment_shapley", "Environment Shapley", "biology",
     ["environment_conditional_effect"], None, False, ""),
    ("sequence_attribution", "Sequence Attribution", "biology", ["prediction"], None, True, ""),
    ("cnn_ism", "CNN ISM", "biology", ["sequence_attribution"], None, True, "需要 CNN 输出"),
    ("motif_discovery", "Sequence Motif Discovery", "biology", ["sequence_attribution"], None,
     False, "seqlet -> clustering -> consensus (IUPAC/human/regex); 需要 CNN ISM/IG 或 Transformer IG"),
    ("motif_enrichment", "Motif Enrichment (Fisher + BH-FDR)", "statistics", ["motif_discovery"],
     None, False, "独立可选步骤; foreground=高效序列, background=all eligible sequences"),
    ("cellline_heterogeneity", "Cell-line Heterogeneity", "biology",
     ["prediction"], None, True, "需要 ≥2 个 cell line"),
    ("bootstrap", "Bootstrap Confidence Intervals", "statistics", [], None, False, ""),
    ("hypothesis_testing", "Extended Hypothesis Testing", "statistics", [], None, False, ""),
    ("evidence_integration", "Cross-model Evidence Integration", "evidence",
     ["sequence_attribution", "environment_conditional_effect"], None, True, ""),
    ("hypothesis_generation", "Biological Hypothesis Generation", "evidence",
     ["evidence_integration"], None, True, ""),
]:
    register_analysis(*_spec)
