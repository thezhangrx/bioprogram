"""analysis.pipeline — 证据分析引擎编排入口 (只编排; 科学计算在各模块)。

用法:
    python -m analysis.pipeline --batch-dir <batch> --output <out>
    python -m analysis.pipeline --batch-dir <batch> --analysis-plan plan.json
"""
from __future__ import annotations


# --- 项目根引导: 保证从任意工作目录运行/被导入都能解析 core、analysis、workflows ---
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json

import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from analysis import __version__ as ENGINE_VERSION
from analysis.config import AnalysisConfig
from analysis.data.loaders import coverage_summary, load_experiment_table
from analysis.data.validation import validate_metric_consistency
from analysis.plans import (AnalysisPlan, Capabilities, ExecutionPlan, ExecutionTask,
                           default_plan, validate_analysis_plan)
from analysis.reports.markdown_report import (build_anomaly_md, build_data_quality_md,
                                             build_overview_md)


@dataclass
class PipelineArtifacts:
    output_dir: Path
    tables_dir: Path
    reports_dir: Path
    figures_dir: Path

    @classmethod
    def create(cls, output: str | Path) -> "PipelineArtifacts":
        """产物根目录下的三个子目录。

        2026-09-13 起产物根为 <batch>/summary（旧为 <batch>/analyse_out），
        为避免出现 summary/summary 套娃，报告子目录命名为 reports/：
            <batch>/summary/tables    全部分析表 CSV
            <batch>/summary/reports   00_overview.md 等报告
            <batch>/summary/figures   分析引擎生成的图
        """
        out = Path(output)
        for sub in ("tables", "reports", "figures"):
            (out / sub).mkdir(parents=True, exist_ok=True)
        return cls(out, out / "tables", out / "reports", out / "figures")


def capabilities_from_table(table: pd.DataFrame, has_environment_cols: bool = True,
                            batch_dir: Optional[str | Path] = None) -> Capabilities:
    def contains(keyword: str) -> bool:
        if "model" not in table.columns:
            return False
        return bool(table["model"].astype(str).str.lower().str.contains(keyword).any())

    return Capabilities(
        n_cell_lines=int(table["cell_line"].nunique()) if "cell_line" in table.columns else 0,
        n_environment_factors=4 if has_environment_cols else 0,
        n_models=int(table["model"].nunique()) if "model" in table.columns else 0,
        has_environment_features=has_environment_cols,
        has_cnn=contains("cnn"),
        has_transformer=contains("trans"),
        has_xgboost=contains("xgb"),
        has_mlp=contains("mlp"),
        has_linear=contains("linear"),
        environment_factorial_observations=16 if has_environment_cols else 0,
        replication_per_cellline=4,
        has_bootstrap_results=bool(_has_paired_predictions(batch_dir, table)),
    )


def _has_paired_predictions(batch_dir: Optional[str | Path], table: pd.DataFrame,
                            sample_limit: int = 6) -> bool:
    """探测是否存在 per-sample 预测 artifact (bootstrap/permutation 的真实前置条件)。"""
    if batch_dir is None or table is None or table.empty or "run_name" not in table.columns:
        return False
    from analysis.stats.tasks import predictions_path
    for run in list(table["run_name"].dropna().astype(str).unique())[:sample_limit]:
        if predictions_path(batch_dir, run) is not None:
            return True
    return False


def run_analysis(
    batch_dir: str | Path,
    output: str | Path,
    plan: Optional[AnalysisPlan] = None,
    config: Optional[AnalysisConfig] = None,
) -> Dict[str, Any]:
    """Phase-2 垂直切片: 统一表 -> 校验 -> overview/status/plan 产物。

    后续阶段将在此编排器中挂载 environment/sequence/cell-line/evidence 任务,
    每个任务保持 selected/available/status 三态, GUI 只读 analysis_status.json。
    """
    plan = plan or default_plan()
    config = config or AnalysisConfig()
    artifacts = PipelineArtifacts.create(output)

    # 1) 统一实验表 (只读)
    table = load_experiment_table(batch_dir)
    table.to_csv(artifacts.tables_dir / "experiment_table.csv", index=False)

    # 2) 批次级校验
    anomalies = validate_metric_consistency(table)
    anomalies.to_csv(artifacts.tables_dir / "metric_inconsistency.csv", index=False)

    # 3) availability -> execution plan
    caps = capabilities_from_table(table, has_environment_cols=True, batch_dir=batch_dir)
    task_states = validate_analysis_plan(plan, caps)
    execution_tasks: List[ExecutionTask] = [
        ExecutionTask(
            task_id=st["task_id"], selected=bool(st["selected"]),
            available=bool(st["available"]), status=str(st["status"]),
            reason=str(st.get("reason", "")),
        )
        for st in task_states.values()
    ]

    # 4) 执行 (本构建已实现: qc/prediction/environment conditional+main)
    from analysis.environment.incremental_effect import (compute_conditional_increments,
                                                        compute_main_effects,
                                                        summarize_conditional)
    from analysis.prediction import loco_performance, performance_by_model_split
    from analysis.reports.markdown_report import (build_environment_md, build_prediction_md)

    executed: Dict[str, str] = {}
    completed_at = datetime.now(timezone.utc).isoformat()

    task_artifacts = {
        "qc": "reports/01_data_quality.md",
        "prediction": "tables/prediction_summary.csv",
        "environment_conditional_effect": "tables/environment_conditional_delta_r2.csv",
        "environment_main_effect": "tables/environment_main_effects.csv",
        "environment_factorial_dag": "tables/environment_edges.csv",
        "bootstrap": "tables/bootstrap_results.csv",
        "hypothesis_testing": "tables/permutation_results.csv",
        "fdr_correction": "tables/permutation_results.csv",
        "environment_anova": "tables/anova_results.csv",
        "sequence_attribution": "tables/attribution_summary.csv",
        "motif_discovery": "tables/motif_candidates.csv",
        "motif_enrichment": "tables/motif_enrichment.csv",
        "cellline_heterogeneity": "tables/cellline_effects.csv",
        "evidence_integration": "tables/evidence_matrix.csv",
        "hypothesis_generation": "reports/07_biological_hypotheses.md",
    }

    def _finish(task_id: str, status: str = "completed", reason: str = ""):
        for task in execution_tasks:
            if task.task_id == task_id:
                task.status = status
                task.reason = reason or task.reason
                task.completed_at = completed_at
                if task_id in task_artifacts:
                    task.artifact = task_artifacts[task_id]
                executed[task_id] = status
                return

    # 仅当 selected & available 才执行; 否则保持 skipped/unavailable
    state = {t.task_id: t for t in execution_tasks}

    def _should_run(task_id: str) -> bool:
        t = state.get(task_id)
        return bool(t and t.status == "pending" and t.selected and t.available)

    if _should_run("qc"):
        _finish("qc")

    prediction_df, loco_df = None, None
    prediction_ok = _should_run("prediction")
    if prediction_ok:
        try:
            prediction_df = performance_by_model_split(table)
            loco_df = loco_performance(table)
            prediction_df.to_csv(artifacts.tables_dir / "prediction_summary.csv", index=False)
            loco_df.to_csv(artifacts.tables_dir / "loco_performance.csv", index=False)
            _finish("prediction")
        except Exception as exc:  # noqa: BLE001
            _finish("prediction", "failed", f"prediction analysis failed: {exc}")

    cond_summary, main_df = None, None
    if _should_run("environment_conditional_effect"):
        try:
            cond_raw = compute_conditional_increments(table)
            cond_summary = summarize_conditional(cond_raw)
            cond_summary.to_csv(artifacts.tables_dir / "environment_conditional_delta_r2.csv",
                                index=False)
            _finish("environment_conditional_effect")
        except Exception as exc:  # noqa: BLE001
            _finish("environment_conditional_effect", "failed",
                    f"conditional effect failed: {exc}")

    if _should_run("environment_main_effect"):
        if cond_raw is None:
            _finish("environment_main_effect", "unavailable",
                    "environment_main_effect requires conditional effect data")
            main_df = None
        else:
            try:
                main_df = compute_main_effects(cond_raw)
                main_df.to_csv(artifacts.tables_dir / "environment_main_effects.csv", index=False)
                _finish("environment_main_effect")
            except Exception as exc:  # noqa: BLE001
                _finish("environment_main_effect", "failed", f"main effect failed: {exc}")

    # ------------------------------------------------------------------
    # 统计工具接线 (bootstrap / permutation / BH-FDR / ANOVA) —— 只读已有产物
    # 顺序: 必须先于 factorial DAG (edges 要带 CI) 与 evidence matrix (CI 参与 tier)
    # ------------------------------------------------------------------
    stats_bundle = {"bootstrap": None, "permutation": None, "anova": None,
                    "main_ci": None, "cellline_ci": None, "fdr": None}
    if _should_run("bootstrap"):
        try:
            from analysis.stats.tasks import bootstrap_cellline_effects, bootstrap_environment_edges, bootstrap_main_effects, edge_ci_table
            bs = bootstrap_environment_edges(batch_dir, table, config=config)
            bs.to_csv(artifacts.tables_dir / "bootstrap_results.csv", index=False)
            main_ci = bootstrap_main_effects(main_df, config=config) if main_df is not None \
                else None
            if main_ci is not None:
                main_ci.to_csv(artifacts.tables_dir / "bootstrap_main_effects.csv", index=False)
            cell_ci = bootstrap_cellline_effects(main_df, config=config) if main_df is not None \
                else None
            if cell_ci is not None:
                cell_ci.to_csv(artifacts.tables_dir / "bootstrap_cellline_effects.csv",
                               index=False)
            ec = edge_ci_table(bs)
            ec.to_csv(artifacts.tables_dir / "environment_bootstrap.csv", index=False)
            stats_bundle.update({"bootstrap": bs, "main_ci": main_ci, "cellline_ci": cell_ci})
            n_ci = int(((bs["metric"] == "R2") & (bs["status"] == "ok")).sum())
            _finish("bootstrap", "completed",
                    f"tables/bootstrap_results.csv ({n_ci} ΔR² CIs); "
                    f"paired per-sample bootstrap")
        except Exception as exc:  # noqa: BLE001
            _finish("bootstrap", "failed", f"bootstrap wiring failed: {exc}")

    if _should_run("hypothesis_testing"):
        try:
            from analysis.stats.tasks import (apply_fdr, permutation_environment_edges,
                                             permutation_interactions,
                                             permutation_main_effects)
            parts = [permutation_environment_edges(batch_dir, table, config=config)]
            if cond_summary is not None:
                parts.append(permutation_main_effects(cond_summary, config=config))
            parts.append(permutation_interactions(batch_dir, table, config=config))
            perm = pd.concat([p for p in parts if p is not None and not p.empty],
                             ignore_index=True) if any(
                p is not None and not p.empty for p in parts) else pd.DataFrame()
            perm = apply_fdr(perm, config=config)
            perm.to_csv(artifacts.tables_dir / "permutation_results.csv", index=False)
            stats_bundle["permutation"] = perm
            stats_bundle["fdr"] = perm
            n_ok = int((perm["status"] == "ok").sum()) if not perm.empty else 0
            _finish("hypothesis_testing", "completed",
                    f"tables/permutation_results.csv ({n_ok} tests, BH-FDR by family)")
        except Exception as exc:  # noqa: BLE001
            _finish("hypothesis_testing", "failed", f"permutation wiring failed: {exc}")

    anova_enabled = bool(getattr(plan.statistics, "anova", True))
    if state.get("environment_anova") is not None:
        if not anova_enabled or not plan.environment.anova:
            _finish("environment_anova", "skipped", "user_disabled")
        elif _should_run("environment_anova"):
            try:
                from analysis.stats.tasks import run_anova_tasks
                anova = run_anova_tasks(table, config=config)
                anova.to_csv(artifacts.tables_dir / "anova_results.csv", index=False)
                stats_bundle["anova"] = anova
                ok = int((anova["status"] == "ok").sum()) if not anova.empty else 0
                if ok == 0:
                    reason = (anova["reason"].iloc[0] if not anova.empty else "no estimable term")
                    _finish("environment_anova", "unavailable",
                            f"insufficient_data: {reason}")
                else:
                    _finish("environment_anova", "completed",
                            f"tables/anova_results.csv ({ok} terms)")
            except Exception as exc:  # noqa: BLE001
                _finish("environment_anova", "failed", f"ANOVA failed: {exc}")

    # FDR 不是独立分析: 只有存在可校正 family 时才执行 (否则如实记录)
    if state.get("fdr_correction") is not None and state["fdr_correction"].selected:
        perm_df = stats_bundle.get("permutation")
        n_families = 0
        if perm_df is not None and not perm_df.empty and "fdr_status" in perm_df.columns:
            n_families = int(perm_df.loc[perm_df["fdr_status"] == "ok", "fdr_family"].nunique())
        if n_families > 0:
            _finish("fdr_correction", "completed",
                    f"BH-FDR applied to {n_families} p-value families "
                    f"(不与其他问题混用 family)")
        else:
            _finish("fdr_correction", "unavailable",
                    "no corrigible p-value family available in this batch")

    # Environment Factorial DAG (2^4 lattice): normalized table -> nodes/edges -> figures.
    # 必须在下方的 "pending -> unavailable" 汇总之前执行; 03_environment_effects.md 的
    # DAG 章节在 03 报告写完后统一追加 (避免被 build_environment_md 覆盖)。
    dag_md_text = ""
    if _should_run("environment_factorial_dag"):
        try:
            from analysis.environment.factorial_dag import write_factorial_dag_artifacts
            from analysis.visualization.factorial_dag import (
                render_ablation_delta_r2, render_conditional_delta_r2,
                render_environment_interactions, render_factorial_dag)
            dag_paths = write_factorial_dag_artifacts(
                batch_dir, artifacts.tables_dir, artifacts.reports_dir,
                threshold=config.consensus.unstable_effect_threshold, write_md=False)
            dag_md_text = dag_paths.get("dag_md", "")
            dag_nodes = pd.read_csv(dag_paths["nodes"])
            dag_edges = pd.read_csv(dag_paths["edges"])
            env_fig_dir = artifacts.figures_dir / "03_environment"   # §22/§37 目录约定
            dag_figs = render_factorial_dag(dag_nodes, dag_edges, env_fig_dir)
            dag_delta_figs = render_conditional_delta_r2(dag_edges, env_fig_dir)
            dag_abl_figs = render_ablation_delta_r2(
                pd.read_csv(dag_paths["ablation"]), env_fig_dir)
            dag_int_figs = render_environment_interactions(
                pd.read_csv(dag_paths["interactions"]), env_fig_dir)
            _finish("environment_factorial_dag", "completed",
                    f"{len(dag_figs)} DAG, {len(dag_delta_figs)} conditional-ΔR², "
                    f"{len(dag_abl_figs)} ablation, {len(dag_int_figs)} interaction figures")
        except Exception as exc:  # noqa: BLE001
            _finish("environment_factorial_dag", "failed", f"factorial DAG failed: {exc}")

    attribution_table = None
    if _should_run("sequence_attribution"):
        try:
            from analysis.attribution.extractors import extract_attribution_table
            from analysis.attribution.summary import build_motif_summary_md
            attribution_table = extract_attribution_table(batch_dir)
            attribution_table.to_csv(artifacts.tables_dir / "attribution_summary.csv", index=False)
            (artifacts.reports_dir / "04_sequence_motifs.md").write_text(
                build_motif_summary_md(attribution_table), encoding="utf-8")
            _finish("sequence_attribution")
            has_cnn_rows = bool(
                attribution_table["model"].astype(str).str.contains("cnn").any()
                if not attribution_table.empty else False)
            if _should_run("cnn_ism") and has_cnn_rows:
                _finish("cnn_ism")
            elif state.get("cnn_ism") and state["cnn_ism"].selected and not has_cnn_rows:
                _finish("cnn_ism", "unavailable", "no CNN importance outputs in batch")
        except Exception as exc:  # noqa: BLE001
            _finish("sequence_attribution", "failed", f"attribution extraction failed: {exc}")

    # Sequence Motif Discovery (attribution -> seqlet -> clustering -> consensus -> enrichment)
    motif_result: Dict[str, object] = {}
    if state.get("motif_discovery") is not None:
        seq_state = state["motif_discovery"]
        if not plan.sequence.motif_discovery:
            _finish("motif_discovery", "skipped", "user_disabled")
        elif seq_state.status == "pending":
            try:
                from analysis.sequence.motif.pipeline import run_and_write
                motif_result = run_and_write(
                    attribution_table if attribution_table is not None else pd.DataFrame(),
                    batch_dir, artifacts.tables_dir, artifacts.reports_dir, artifacts.figures_dir,
                    config=config, discovery=True,
                    enrichment=bool(plan.sequence.motif_enrichment))
                from analysis.sequence.motif.pipeline import motif_evidence_rows
                motif_result["motif_evidence"] = pd.DataFrame(
                    motif_evidence_rows(motif_result.get("motifs", []),
                                        motif_result.get("enrichment", [])))
                n_motifs = int(motif_result.get("summary", {}).get("n_motifs", 0))
                if n_motifs == 0:
                    _finish("motif_discovery", "unavailable",
                            "; ".join(motif_result.get("unavailable_reasons", []))
                            or "no motif passed support thresholds")
                else:
                    _finish("motif_discovery", "completed",
                            f"tables/motif_candidates.csv ({n_motifs} motifs; "
                            f"{motif_result.get('summary', {}).get('n_seqlets')} seqlets)")
                enr_state = state.get("motif_enrichment")
                if enr_state is not None:
                    if not plan.sequence.motif_enrichment:
                        _finish("motif_enrichment", "skipped", "user_disabled")
                    elif n_motifs == 0:
                        _finish("motif_enrichment", "unavailable",
                                "motif_enrichment requires motif candidates")
                    else:
                        n_ok = sum(1 for e in motif_result.get("enrichment", [])
                                   if e.get("status") == "ok")
                        n_sig = sum(1 for e in motif_result.get("enrichment", [])
                                    if e.get("FDR") is not None
                                    and float(e["FDR"]) < config.motif.enrichment_fdr)
                        _finish("motif_enrichment", "completed",
                                f"tables/motif_enrichment.csv ({n_ok} tests, "
                                f"{n_sig} pass FDR<{config.motif.enrichment_fdr})")
            except Exception as exc:  # noqa: BLE001
                _finish("motif_discovery", "failed", f"motif discovery failed: {exc}")

    cellline_df, evidence_matrix, matrix_excluded = None, None, 0
    if _should_run("cellline_heterogeneity"):
        if main_df is None:
            _finish("cellline_heterogeneity", "unavailable",
                    "cellline heterogeneity requires environment main effects")
        else:
            try:
                from analysis.cellline.consistency import (consistency_counts,
                                                          summarize_environment_by_cellline)
                from analysis.reports.markdown_report import build_cellline_md
                from analysis.stats.tasks import cellline_ci_lookup
                cellline_df = summarize_environment_by_cellline(
                    main_df, ci_by_cell_line=cellline_ci_lookup(stats_bundle.get("cellline_ci")),
                    config=config)
                cellline_df.to_csv(artifacts.tables_dir / "cellline_effects.csv", index=False)
                (artifacts.reports_dir / "05_cellline_heterogeneity.md").write_text(
                    build_cellline_md(cellline_df, consistency_counts(cellline_df)),
                    encoding="utf-8")
                _finish("cellline_heterogeneity")
            except Exception as exc:  # noqa: BLE001
                _finish("cellline_heterogeneity", "failed",
                        f"cellline analysis failed: {exc}")

    if _should_run("evidence_integration"):
        if main_df is None:
            _finish("evidence_integration", "unavailable",
                    "evidence integration requires environment effects")
        else:
            try:
                from analysis.evidence.integration import environment_evidence_matrix
                from analysis.reports.markdown_report import build_evidence_md
                evidence_matrix = environment_evidence_matrix(
                    main_df, cellline_df, config,
                    bootstrap_ci=stats_bundle.get("main_ci"),
                    permutation=stats_bundle.get("permutation"))
                motif_ev = motif_result.get("motif_evidence")
                if motif_ev is not None and not motif_ev.empty and not evidence_matrix.empty:
                    evidence_matrix = pd.concat([evidence_matrix, motif_ev],
                                                ignore_index=True, sort=False)
                evidence_matrix.to_csv(artifacts.tables_dir / "evidence_matrix.csv", index=False)
                (artifacts.reports_dir / "06_evidence_integration.md").write_text(
                    build_evidence_md(evidence_matrix), encoding="utf-8")
                # 不稳定上下文 (|ΔR²| >= unstable_effect_threshold) 已排除出矩阵, 计入 anomaly 报告
                matrix_excluded = int(
                    (pd.to_numeric(main_df["main_r2_delta"], errors="coerce").abs()
                     >= config.consensus.unstable_effect_threshold).sum()
                ) if "main_r2_delta" in main_df.columns else 0
                _finish("evidence_integration")
            except Exception as exc:  # noqa: BLE001
                _finish("evidence_integration", "failed",
                        f"evidence integration failed: {exc}")

    if _should_run("hypothesis_generation"):
        if evidence_matrix is None or evidence_matrix.empty:
            _finish("hypothesis_generation", "unavailable",
                    "hypothesis generation requires non-empty evidence matrix")
        else:
            try:
                from analysis.reports.markdown_report import build_hypotheses_md
                (artifacts.reports_dir / "07_biological_hypotheses.md").write_text(
                    build_hypotheses_md(evidence_matrix), encoding="utf-8")
                _finish("hypothesis_generation")
            except Exception as exc:  # noqa: BLE001
                _finish("hypothesis_generation", "failed",
                        f"hypothesis generation failed: {exc}")

    # 尚未实现但被选中的任务: 明确 unavailable (绝不伪造)
    for task in execution_tasks:
        if task.status == "pending" and task.selected:
            task.status = "unavailable"
            task.reason = "analysis module not yet implemented in this build (phase roadmap)"
            task.completed_at = completed_at
            executed[task.task_id] = "unavailable"

    ep = ExecutionPlan(plan=plan, tasks=execution_tasks)
    ep.completed_at = datetime.now(timezone.utc).isoformat()

    # 5) 产物
    coverage = coverage_summary(table)
    status_dict = ep.to_status_dict()
    status_dict.update({
        "engine_version": ENGINE_VERSION,
        "batch": str(batch_dir),
        "config": config.as_dict(),
    })
    plan.save(artifacts.output_dir / "analysis_plan.json")
    ep.save_status(artifacts.output_dir / "analysis_status.json")

    overview_md = build_overview_md(coverage, plan, status_dict, anomalies)
    (artifacts.reports_dir / "00_overview.md").write_text(overview_md, encoding="utf-8")

    # 批次级 qc 报告 (01/08 + anomaly_report.csv; 机器可读见 tables/)
    anomaly_report = anomalies.copy() if anomalies is not None else pd.DataFrame()
    if not anomaly_report.empty:
        if "flags" in anomaly_report.columns:
            anomaly_report.insert(0, "anomaly_type", anomaly_report["flags"].map(
                lambda f: (f.split(";")[0].rsplit("_", 1)[0]
                           if isinstance(f, str) and f else "metric_inconsistency")))
        anomaly_report.to_csv(artifacts.tables_dir / "anomaly_report.csv", index=False)
    else:
        pd.DataFrame(columns=["anomaly_type", "row", "experiment", "flags",
                              "delta_r2", "delta_rmse"]) \
            .to_csv(artifacts.tables_dir / "anomaly_report.csv", index=False)
    (artifacts.reports_dir / "01_data_quality.md").write_text(
        build_data_quality_md(coverage, table, anomalies), encoding="utf-8")
    (artifacts.reports_dir / "08_anomaly_report.md").write_text(
        build_anomaly_md(anomalies, matrix_excluded), encoding="utf-8")

    if prediction_ok:
        (artifacts.reports_dir / "02_prediction_generalization.md").write_text(
            build_prediction_md(prediction_df, loco_df), encoding="utf-8")
    if cond_summary is not None and main_df is not None:
        (artifacts.reports_dir / "03_environment_effects.md").write_text(
            build_environment_md(cond_summary, main_df,
                                 bootstrap_main=stats_bundle.get("main_ci"),
                                 permutation=stats_bundle.get("permutation"),
                                 anova=stats_bundle.get("anova")), encoding="utf-8")
    if dag_md_text:
        from analysis.environment.factorial_dag import append_dag_section
        append_dag_section(artifacts.reports_dir, dag_md_text)

    (artifacts.output_dir / "execution_log.json").write_text(
        json.dumps({"executed": executed,
                    "completed_at": ep.completed_at,
                    "status_counts": {
                        s: sum(1 for t in execution_tasks if t.status == s)
                        for s in {t.status for t in execution_tasks}
                    }}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 6) 图形渲染 + Importance–ΔR² 二维证据图 (只消费上面已落盘的表格数据; 失败不阻断已完成的科学计算)
    if executed.get("visualization") is None:
        execution_log_path = artifacts.output_dir / "execution_log.json"

        def _patch_log(key: str, value: str, refresh_figures: bool = True) -> None:
            log = json.loads(execution_log_path.read_text(encoding="utf-8"))
            log.setdefault("executed", {})[key] = value
            if refresh_figures:
                log["figures"] = sorted(
                    str(p.relative_to(artifacts.figures_dir))
                    for p in artifacts.figures_dir.rglob("*.png"))
            execution_log_path.write_text(
                json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

        # 6a) Importance / Attribution – ΔR² (tables/importance_vs_delta_r2.csv,
        #     summary/07_importance_vs_delta_r2.md, summary/importance_metric_selection.md,
        #     figures/07_evidence/*.png)
        try:
            from analysis.visualization.importance_delta import run_importance_delta_analysis
            imp_res = run_importance_delta_analysis(
                batch_dir, artifacts.output_dir, filter_mode="strict", config=config)
            executed["importance_delta"] = (
                f"completed: {imp_res['n_points']} candidate points, "
                f"{imp_res['n_pass']} pass strict filter")
            _patch_log("importance_delta", executed["importance_delta"])
        except Exception as exc:  # noqa: BLE001
            executed["importance_delta"] = f"failed: {exc}"
            _patch_log("importance_delta", executed["importance_delta"], refresh_figures=False)

        # 6c) 常规图组
        try:
            from analysis.visualization import render_all
            render_all(
                artifacts.figures_dir,
                prediction_df=prediction_df, loco_df=loco_df,
                conditional_summary=cond_summary, main_effects=main_df,
                attribution_table=attribution_table, cellline_df=cellline_df,
                evidence_matrix=evidence_matrix)
            executed["visualization"] = "completed"
            _patch_log("visualization", "completed")
        except Exception as exc:  # noqa: BLE001
            executed["visualization"] = f"failed: {exc}"
            _patch_log("visualization", executed["visualization"], refresh_figures=False)
    return status_dict


def main() -> None:
    ap = argparse.ArgumentParser(description="CRISPR evidence analysis engine (analysis.pipeline)")
    ap.add_argument("--batch-dir", type=str, required=True, help="训练结果批次目录")
    ap.add_argument("--output", type=str, default="", help="输出目录 (默认 <batch>/summary)")
    ap.add_argument("--analysis-plan", type=str, default="", help="可选 AnalysisPlan json")
    args = ap.parse_args()

    batch = Path(args.batch_dir)
    output = Path(args.output) if args.output else (batch / "summary")
    plan = AnalysisPlan.load(args.analysis_plan) if args.analysis_plan else default_plan()
    status = run_analysis(batch_dir=batch, output=output, plan=plan)
    print(f"[✓] pipeline finished -> {output}")
    print(f"    tasks: " + "; ".join(
        f"{t['task_id']}={t['status']}" for t in status.get("tasks", [])
    ))


if __name__ == "__main__":
    main()
