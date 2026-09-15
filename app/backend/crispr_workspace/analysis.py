"""Analysis / AnalysisPlan 接口。

- 可选任务列表来自 Analyse Registry (analysis.registry), 不在页面硬编码;
- availability 在提交时由引擎严格判定; 此服务提供基于产物的浅层提示 (GUI 只读);
- Run = 子进程调 analysis.pipeline (现有引擎), 状态从 analysis_status.json 读取。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config, store

# 任务 id -> (engine plan 路径字段), 与 analyse 引擎 AnalysisPlan 对齐
TASK_PLAN_MAP: Dict[str, List[str]] = {
    "qc": ["run_qc"],
    "prediction": ["run_prediction_analysis"],
    "environment_conditional_effect": ["environment", "conditional_effect"],
    "environment_main_effect": ["environment", "main_effect"],
    "environment_anova": ["environment", "anova"],
    "environment_shapley": ["environment", "shapley"],
    "sequence_attribution": ["sequence", "position_attribution"],
    "cnn_ism": ["sequence", "ism"],
    "motif_discovery": ["sequence", "motif_discovery"],
    "motif_enrichment": ["sequence", "motif_enrichment"],
    "cellline_heterogeneity": ["cell_line", "heterogeneity"],
    "bootstrap": ["statistics", "bootstrap"],
    "hypothesis_testing": ["statistics", "hypothesis_testing"],
    "fdr_correction": ["statistics", "fdr_correction"],
    "evidence_integration": ["evidence", "evidence_integration"],
    "hypothesis_generation": ["evidence", "hypothesis_generation"],
}


def _default_plan_dict() -> Dict[str, Any]:
    return {
        "plan_version": "1.0",
        "run_qc": True,
        "run_prediction_analysis": True,
        "environment": {"enabled": True, "conditional_effect": True, "main_effect": True,
                        "interaction": False, "shapley": False, "anova": False},
        "sequence": {"enabled": True, "position_attribution": True, "ism": True,
                     "motif_discovery": True, "motif_enrichment": False},
        "cell_line": {"enabled": True, "heterogeneity": True, "interaction": False,
                      "consistency": True},
        # 引擎 StatisticsPlan/EvidencePlan 容器无 enabled 字段 (勿加)
        "statistics": {"bootstrap": True, "hypothesis_testing": True, "fdr_correction": True},
        "evidence": {"cross_model": True, "evidence_integration": True,
                     "hypothesis_generation": True},
    }


def registry_tasks() -> List[Dict]:
    """来自 analysis.registry 的任务目录 (找不到则回退到 engine 默认任务表)。"""
    try:
        from analysis.registry import registered_tasks
        items = registered_tasks()

        def _val(spec: Any, name: str, default):
            if isinstance(spec, dict):
                return spec.get(name, default)
            return getattr(spec, name, default)

        out = []
        for spec in items:
            task_id = _val(spec, "task_id", None)
            if task_id is None:
                continue
            deps = _val(spec, "dependencies", []) or []
            out.append({
                "task_id": task_id,
                "display": _val(spec, "display", task_id),
                "category": _val(spec, "category", ""),
                "dependencies": list(deps),
            })
        return out
    except Exception:
        return [
            {"task_id": tid, "display": disp, "category": cat, "dependencies": []}
            for tid, disp, cat in [
                ("qc", "Data QC", "core"), ("prediction", "Prediction & Generalization", "core"),
                ("environment_conditional_effect", "Conditional ΔR²", "core"),
                ("environment_main_effect", "Environment Main Effects", "core"),
                ("sequence_attribution", "Sequence Attribution", "core"),
                ("cnn_ism", "CNN ISM", "core"),
                ("cellline_heterogeneity", "Cell-line Heterogeneity", "core"),
                ("evidence_integration", "Evidence Integration", "core"),
                ("hypothesis_generation", "Biological Hypotheses", "core"),
                ("bootstrap", "Bootstrap Confidence Intervals", "advanced"),
                ("environment_anova", "ANOVA / Factorial", "advanced"),
                ("environment_shapley", "Environment Shapley", "advanced"),
                ("motif_discovery", "Motif Discovery", "advanced"),
                ("motif_enrichment", "Motif Enrichment", "advanced"),
                ("hypothesis_testing", "Extended Hypothesis Testing", "advanced"),
                ("fdr_correction", "FDR Correction", "advanced"),
            ]
        ]


def heuristic_availability(batch_dir: Optional[str]) -> Dict[str, Dict]:
    """基于训练产物的浅层可用性提示 (真值由引擎在运行时判定)。

    扫描 results 目录名: 细胞系数目 / 环境组合 / 模型 / CNN。
    """
    base = Path(batch_dir) if batch_dir and Path(batch_dir).exists() else None
    cells: set = set()
    env_combos: set = set()
    has_cnn = False
    n_dirs = 0
    if base:
        for d in base.iterdir():
            if not d.is_dir() or d.name == "summary":
                continue
            n_dirs += 1
            name = d.name
            if "cnn" in name:
                has_cnn = True
            for c in ("hct116", "hek293t", "hela", "hl60"):
                if c in name:
                    cells.add(c)
            m = re.search(r"(sequence[\w]*)", name)
            if m:
                env_combos.add(m.group(1))
    hints = {
        "no_batch": base is None,
        "n_experiment_dirs": n_dirs,
        "cell_lines": sorted(cells),
        "n_environments_seen": len(env_combos),
        "has_cnn": has_cnn,
    }
    avail: Dict[str, Dict] = {}
    for t in registry_tasks():
        tid = t["task_id"]
        reason = ""
        ok = True
        if hints["no_batch"]:
            ok, reason = False, "No training results batch (batch_dir missing)"
        elif tid in ("cellline_heterogeneity",):
            if len(hints["cell_lines"]) < 2:
                ok, reason = False, "Cell-line heterogeneity needs ≥2 cell lines"
        elif tid == "cnn_ism":
            if not hints["has_cnn"]:
                ok, reason = False, "CNN attribution artifact not found"
        elif tid.startswith("environment_") or tid in ("prediction", "evidence_integration",
                                                       "hypothesis_generation", "bootstrap"):
            if hints["n_environments_seen"] == 0:
                ok, reason = False, "No environment factors detected in results"
        avail[tid] = {"available": ok, "reason": reason}
    return avail


def build_plan_dict(selected: Optional[List[str]], defaults: Optional[List[str]] = None) -> Dict[str, Any]:
    """由勾选的 task ids -> engine AnalysisPlan JSON。

    defaults: 若给出, 用作未显式选择时的基准 (缺省=不勾选的关)。
    """
    selected = set(selected or [])
    plan = _default_plan_dict()

    def set_by_path(path: List[str], value: bool) -> None:
        node = plan
        for p in path[:-1]:
            node = node[p]
        node[path[-1]] = value

    for tid in TASK_PLAN_MAP:
        set_by_path(TASK_PLAN_MAP[tid], tid in selected)
    # 顶层 enabled 容器 (仅引擎带 enabled 字段的容器) 跟随子项 (避免全关还跑)
    for grp, subs in (("environment", ["conditional_effect", "main_effect", "anova", "shapley"]),
                      ("sequence", ["position_attribution", "ism", "motif_discovery", "motif_enrichment"]),
                      ("cell_line", ["heterogeneity"])):
        plan[grp]["enabled"] = any(plan[grp][s] for s in subs)
    return plan


def run(batch_dir: str, output_dir: str, selected_task_ids: Optional[List[str]],
        project_meta: Optional[Dict] = None) -> Dict:
    """启动 analysis.pipeline (子进程); 状态落盘 analysis_status.json。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    plan = build_plan_dict(selected_task_ids)
    plan_path = out / "analysis_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "schema": "analysis.run/1",
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "running",
        "batch_dir": str(Path(batch_dir).resolve()),
        "output_dir": str(out.resolve()),
        "plan_path": str(plan_path),
        "selected_tasks": list(selected_task_ids or []),
        "project": project_meta or {},
    }
    store.write_json(out / "analysis_run.json", manifest)
    logf = open(out / "analysis_run.log", "w", encoding="utf-8")
    cmd = [sys.executable, "-m", "analysis.pipeline",
           "--batch-dir", batch_dir, "--output", str(out),
           "--analysis-plan", str(plan_path)]
    proc = subprocess.Popen(cmd, cwd=str(config.repo_root()),
                            stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    manifest["pid"] = proc.pid
    logf.close()
    store.write_json(out / "analysis_run.json", manifest)
    return manifest


def analysis_status(output_dir: str) -> Dict:
    out = Path(output_dir)
    engine_status = store.read_json(out / "analysis_status.json")
    run = store.read_json(out / "analysis_run.json")
    merged = dict(run or {})
    if engine_status:
        merged["engine_status"] = engine_status
        tasks = engine_status.get("tasks")
        statuses = {t["task_id"]: t["status"] for t in tasks} if tasks else {}
        merged["task_status"] = statuses
        all_done = tasks and all(t["status"] in ("completed", "failed", "skipped", "unavailable")
                                 for t in tasks)
        merged["status"] = "completed" if all_done else "running"
    elif out.exists() and (out / "execution_log.json").exists():
        merged["status"] = "completed"
    else:
        pid = merged.get("pid")
        alive = True
        if pid:
            try:
                os.kill(int(pid), 0)
            except OSError:
                alive = False
        tail_txt = ""
        log = out / "analysis_run.log"
        if log.exists():
            tail_txt = log.read_text(encoding="utf-8", errors="replace")[-1500:]
        if merged.get("status") == "running" and not alive:
            merged["status"] = "failed"
            merged["error_tail"] = tail_txt
    return merged


def list_outputs(output_dir: str) -> Dict:
    """浅层列出 analyse 产物 (summary md / tables csv / figures png)。"""
    root = Path(output_dir)
    entries = []
    # 新布局 <out>/reports + 旧布局 <out>/summary 都兼容
    for sub, kind in (("reports", "md"), ("summary", "md"), ("tables", "csv"), ("figures", "png")):
        d = root / sub
        if not d.exists():
            continue
        for f in sorted(d.glob(f"*.{kind}")):
            entries.append({"name": f.name, "path": str(f),
                            "rel": f"{sub}/{f.name}", "kind": kind})
    return {"output_dir": str(root.resolve()), "entries": entries}
