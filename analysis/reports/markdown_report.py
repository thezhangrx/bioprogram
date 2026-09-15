"""analysis.reports.markdown_report — summary/*.md 生成 (Phase 2 切片: overview + QC 摘要)。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from analysis.plans import AnalysisPlan


def _fmt(v) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def _md_table(df: pd.DataFrame, round_digits: int = 4) -> str:
    if df is None or df.empty:
        return "_空表_"
    lines = ["| " + " | ".join(str(c) for c in df.columns) + " |",
             "| " + " | ".join("---:" for _ in df.columns) + " |"]
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            cells.append(f"{v:.{round_digits}f}" if isinstance(v, float) else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_prediction_md(by_model_split: pd.DataFrame, loco: pd.DataFrame) -> str:
    lines = ["# 02 Prediction & Generalization\n"]
    lines.append("## 模型 × 划分 性能\n")
    lines.append(_md_table(by_model_split))
    lines.append("\n## LOCO 泛化 (all/留一细胞系)\n")
    lines.append(_md_table(loco))
    lines.append("\n> 解读以 generalization 与跨域稳定性为主, 不将预测 R² 直接等同于生物学重要性。\n")
    return "\n".join(lines)


def build_environment_md(conditional_summary: pd.DataFrame, main_effects: pd.DataFrame,
                         bootstrap_main: Optional[pd.DataFrame] = None,
                         permutation: Optional[pd.DataFrame] = None,
                         anova: Optional[pd.DataFrame] = None) -> str:
    lines = ["# 03 Environment Effects\n"]
    lines.append("> 所有 Δ 均来自同一 (split, cell, model, seed) 配对 cohort (Paired baseline)。")
    lines.append("ΔR²>0 表示加入该环境后 R² 提升 (正向增量)。\n")
    lines.append("## 条件 ΔR² (行=加入环境, 列=背景 S)\n")
    lines.append(_md_table(conditional_summary))
    lines.append("\n## 环境主效应 (对不含 e 的所有背景 S 平均 Δ(e|S))\n")
    lines.append(_md_table(main_effects))

    # ---- Bootstrap CI (per-sample paired, 同一 test 样本) ----
    if bootstrap_main is not None and not bootstrap_main.empty:
        cols = [c for c in ("feature", "estimate", "ci_low", "ci_high", "excludes_zero",
                            "n_bootstrap", "n_models", "estimate_basis", "status")
                if c in bootstrap_main.columns]
        lines.append("\n## Bootstrap CI — factor 级主效应 (每模型 main effect 的跨模型 bootstrap)\n")
        lines.append("> 单位 = 模型 (estimate_basis 已标注); per-sample paired ΔR² CI 见 "
                     "tables/bootstrap_results.csv (edge 级)。\n")
        lines.append(_md_table(bootstrap_main[cols], round_digits=6))
    else:
        lines.append("\n## Bootstrap CI\n\n> Unavailable: 本批未执行 bootstrap "
                     "(无 paired per-sample 预测或用户未选择)。\n")

    # ---- Permutation test ----
    if permutation is not None and not permutation.empty:
        perm = permutation.copy()
        if "status" in perm.columns:
            perm = perm[perm["status"] == "ok"]
        if not perm.empty:
            cols = [c for c in ("test_type", "split_type", "cell_line", "model", "factor",
                                "added_environment", "observed_effect", "p_value", "FDR",
                                "fdr_family", "null_hypothesis", "n_permutations", "seed")
                    if c in perm.columns]
            lines.append("\n## Permutation test (真实零假设; H0 见 null_hypothesis 列)\n")
            lines.append(_md_table(perm[cols], round_digits=6))
            lines.append("\n> FDR 按 family 分别校正 (fdr_family 列), 不同科学问题不混用 family。\n")
        else:
            lines.append("\n## Permutation test\n\n> Unavailable: 没有可检验的 effect。\n")
    else:
        lines.append("\n## Permutation test\n\n> Not performed / Unavailable。\n")

    # ---- ANOVA ----
    if anova is not None and not anova.empty:
        ok = anova[anova["status"] == "ok"] if "status" in anova.columns else anova
        if not ok.empty:
            cols = [c for c in ("model_scope", "split_type", "cell_line", "model", "factor",
                                "effect", "F_statistic", "df_num", "df_den", "p_value", "FDR",
                                "effect_size", "ci_low", "ci_high", "n_obs")
                    if c in ok.columns]
            lines.append("\n## Factorial ANOVA (Type-II extra-sum-of-squares; block = model/cell_line/split)\n")
            lines.append(_md_table(ok[cols], round_digits=6))
        reason = ""
        if "status" in anova.columns and (anova["status"] != "ok").all():
            reason = str(anova["reason"].iloc[0])
            lines.append(f"\n## Factorial ANOVA\n\n> Unavailable: {reason}\n")
    else:
        lines.append("\n## Factorial ANOVA\n\n> Not selected in Analysis Plan "
                     "(environment.anova / statistics.anova) 或不可用。\n")

    lines.append("\n> Environment contribution ≠ Model SHAP; 二者概念不同。")
    lines.append("SNR 是 attribution robustness, 不是 statistical significance。\n")
    return "\n".join(lines)


def build_overview_md(
    coverage: Dict[str, Any],
    plan: AnalysisPlan,
    status: Dict[str, Any],
    anomaly_rows: pd.DataFrame,
) -> str:
    lines: List[str] = []
    lines.append("# 00 Overview\n")
    lines.append(f"- experiment count: **{coverage.get('experiment_count')}**")
    lines.append(f"- valid experiments: **{coverage.get('valid_count')}**")
    lines.append(f"- models: {', '.join(coverage.get('models', [])) or '—'}")
    lines.append(f"- cell lines: {', '.join(coverage.get('cell_lines', [])) or '—'}")
    lines.append(f"- environments: {len(coverage.get('environments', []))}")
    lines.append(f"- splits: {', '.join(coverage.get('splits', [])) or '—'}")
    lines.append(f"- metric inconsistency (ΔR²/ΔRMSE 同号) rows: **{len(anomaly_rows)}**")

    lines.append("\n## Analysis Plan (实际选择)\n")
    for t in status.get("tasks", []):
        mark = {
            "completed": "✓", "pending": "☐", "skipped": "⊘",
            "unavailable": "⚠", "failed": "✗", "running": "⟳",
        }.get(t.get("status"), "○")
        reason = f"  ({t.get('reason')})" if t.get("reason") else ""
        lines.append(f"- {mark} {t['task_id']} [selected={t['selected']}, "
                     f"available={t['available']}, status={t['status']}]{reason}")
    lines.append("\n## 执行说明\n")
    lines.append("- 本报告由统一 experiment table 生成; 所有图/表引用同一数据源。")
    lines.append("- PFI/LOFO 等若训练端未生成, 一律标记 Unavailable, 不回头修改训练系统。")
    return "\n".join(lines) + "\n"


def build_cellline_md(summary: pd.DataFrame, counts: dict) -> str:
    lines = ["# 05 Cell-line Heterogeneity\n"]
    if summary is None or summary.empty:
        lines.append("> 无足够 cell-line 数据 (Unavailable)。\n")
        return "\n".join(lines)
    lines.append("## 一致性标签分布\n")
    for label, n in (counts or {}).items():
        lines.append(f"- {label}: {n}")
    lines.append("\n## feature × cell-line 效应 (环境主效应)\n")
    lines.append(_md_table(summary, round_digits=5))
    lines.append("\n> Context-consistent/dependent/conflicting 描述的是 effect 的跨细胞系分布;")
    lines.append("≠ biological mechanism 差异。\n")
    return "\n".join(lines)


def build_evidence_md(matrix: pd.DataFrame) -> str:
    lines = ["# 06 Evidence Integration\n"]
    if matrix is None or matrix.empty:
        lines.append("> 暂无可用证据矩阵。\n")
        return "\n".join(lines)
    lines.append("## Evidence Matrix (environment factors)\n")
    preferred = ["feature", "feature_type", "coverage", "applicable_models", "overall_effect",
                 "ci_low", "ci_high", "ci_excludes_zero", "n_bootstrap", "bootstrap_status",
                 "permutation_p", "permutation_fdr", "direction_concordance",
                 "cell_line_consistency", "evidence_tier"]
    cols = [c for c in preferred if c in matrix.columns]
    lines.append(_md_table(matrix[cols] if cols else matrix, round_digits=5))
    if "evidence_tier" in matrix.columns and "ci_excludes_zero" in matrix.columns:
        n_ci = int(matrix["ci_excludes_zero"].notna().sum())
        n_inc = int((matrix["evidence_tier"] == "Inconclusive").sum())
        lines.append(f"\n> CI 参与 tier 判定: {n_ci} 个 factor 有可用 CI; "
                     f"{n_inc} 个 factor 当前为 Inconclusive")
        lines.append("> (CI 跨 0 或方向冲突; 缺失 CI 时按规则降级, 绝不伪造 CI)。")
    lines.append("\n> Effect 与 Importance 严格分离: 本矩阵为 Environment contribution decomposition;")
    lines.append("Model SHAP/IG/ISM/Attention 见 attribution_summary.csv (单独概念)。")
    lines.append("Coverage 分母 = applicable models (不固定 5)。\n")
    return "\n".join(lines)


def build_hypotheses_md(matrix: pd.DataFrame) -> str:
    from analysis.evidence.hypothesis import generate_hypotheses_for_record
    from analysis.evidence.integration import tier_from_value
    from analysis.schemas import EvidenceRecord, EvidenceTier

    def _safe_int(value, default: int = 0) -> int:
        """coverage 容错: 非数值 (如 motif 的 '1/1 model families') 不再让整个阶段失败。"""
        try:
            return int(float(str(value).split("/")[0]))
        except (TypeError, ValueError):
            return default
    lines = ["# 07 Biological Hypotheses (候选, 需验证)\n"]
    if matrix is None or matrix.empty:
        lines.append("> 无证据矩阵可生成假设。\n")
        return "\n".join(lines)
    n = 0
    for _, r in matrix.iterrows():
        tier = tier_from_value(str(r.get("evidence_tier", "")))
        if tier in (EvidenceTier.TIER1, EvidenceTier.TIER2, EvidenceTier.TIER3):
            rec = EvidenceRecord(
                feature=str(r["feature"]), feature_type=str(r.get("feature_type", "")),
                applicable_models=str(r.get("applicable_models", "")).split(";"),
                coverage=_safe_int(r.get("coverage", 0) or 0),
                direction_concordance=(float(r["direction_concordance"])
                                       if pd.notna(r.get("direction_concordance")) else None),
                cell_line_consistency=r.get("cell_line_consistency"),
                overall_effect=(float(r["overall_effect"])
                                if pd.notna(r.get("overall_effect")) else None),
                tier=tier,
            )
            for h in generate_hypotheses_for_record(rec):
                lines.append(f"### {h['feature']}\n")
                lines.append(f"- hypothesis: {h['hypothesis']}")
                lines.append(f"- effect_size: {h['effect_size']}")
                lines.append(f"- supporting_models: {h['supporting_models']}")
                lines.append(f"- validation: {h['suggested_validation_experiment']}\n")
                n += 1
    if n == 0:
        lines.append("> 当前无 Tier1-3 证据, 不生成候选假设 (No current evidence ≠ No effect)。\n")
    return "\n".join(lines)


def build_data_quality_md(coverage: dict, table: pd.DataFrame, anomalies: pd.DataFrame) -> str:
    lines = ["# 01 Data Quality (批次级)\n"]
    lines.append(f"- experiments: {coverage.get('experiment_count')} | valid (R² finite): "
                 f"{coverage.get('valid_count')}")
    if table is not None and "cell_line" in table.columns and "environment" in table.columns:
        bal = table.groupby(["cell_line", "environment"]).size().unstack(fill_value=0)
        lines.append("\n## cell-line × environment 覆盖\n")
        lines.append(_md_table(bal.reset_index(), round_digits=0))
    lines.append("\n## Metric inconsistency (同 cohort ΔR²/ΔRMSE 同号)\n")
    if anomalies is None or anomalies.empty:
        lines.append("_无_")
    else:
        lines.append(_md_table(anomalies, round_digits=6))
    lines.append("\n> Eligible/Limited/Ineligible 的逐环境判定在训练前由 data_QC 输出;")
    lines.append("此处为批次级状态 (训练后只读)。\n")
    return "\n".join(lines)


def build_anomaly_md(anomalies: pd.DataFrame, matrix_excluded: int = 0) -> str:
    lines = ["# 08 Anomaly Report\n"]
    lines.append("## 类型说明\n")
    lines.append("- metric_inconsistency: 同一 cohort (同 seed 配对) 下 ΔR² 与 ΔRMSE 同号 "
                 "(R²=1-SSE/SST, RMSE=√(SSE/n) 的理论矛盾标记, 不删除实验)")
    lines.append(f"- numerical_instability_excluded_from_evidence: {matrix_excluded} 上下文行 "
                 "(|ΔR²| 超阈值, 不进证据矩阵; 见 anomaly_treatment 数据级报告)\n")
    if anomalies is None or anomalies.empty:
        lines.append("## 明细\n_无 metric inconsistency_\n")
    else:
        lines.append("## 明细 (METRIC_INCONSISTENCY)\n")
        lines.append(_md_table(anomalies, round_digits=6))
    lines.append("\n> 完整 machine-readable 见 tables/anomaly_report.csv。\n")
    return "\n".join(lines)
