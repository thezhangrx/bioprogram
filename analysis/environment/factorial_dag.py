"""analysis.environment.factorial_dag — Environment Factorial DAG (2^4 lattice) 的数据层。

科学定义 (与报告/图中措辞保持一致):
    Node : 一个 environment combination (理论上 2^4 = 16 个)
    Edge : 从已有环境集合 S 增加一个新环境 e, 即 S -> S ∪ {e} (理论上 32 条)
    Edge value: conditional incremental effect  ΔR²_{e|S} = R²(S∪{e}) - R²(S)
    Primary effect: ΔR²          Direction: positive / negative
    Uncertainty: bootstrap CI (存在才填, 绝不伪造)

关键结构性质:
    * 每个 combination 只有一个节点, 但可以有多个父节点/入边
      (CTCF→CTCF+DNase 与 DNase→CTCF+DNase 同时存在);
    * 缺失/异常只改变 node.status / edge.status / warning, 不删除理论结构;
    * METRIC_INCONSISTENCY (ΔR² 与 ΔRMSE 同向) 只是 warning, 边仍然保留。

数据流 (禁止 visualization 自己扫描实验目录):
    existing results -> analysis.data.loaders (normalization)
        -> tables/environment_nodes.csv + tables/environment_edges.csv
        -> analysis.visualization.factorial_dag (纯 DataFrame 渲染)
"""
from __future__ import annotations

import itertools
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from analysis.environment.incremental_effect import (ALL_ENVIRONMENTS, combo_name,
                                                    compute_conditional_increments,
                                                    parse_environment_set)

# 规范序 (与 incremental_effect/combo_name 一致: 排序后拼接)
ENV_FACTORS: Tuple[str, ...] = ("ctcf", "dnase", "h3k4me3", "rrbs")
FACTOR_LABELS: Dict[str, str] = {"ctcf": "CTCF", "dnase": "DNase",
                                 "h3k4me3": "H3K4me3", "rrbs": "RRBS"}
NODE_METRICS: Tuple[str, ...] = ("R2", "RMSE", "MAE", "Pearson", "Spearman")
DELTA_COLUMNS: Tuple[str, ...] = ("delta_r2", "delta_rmse", "delta_mae",
                                  "delta_pearson", "delta_spearman")

NODE_COLUMNS = ["split_type", "cell_line", "model", "combination", "environment_count",
                "CTCF", "DNase", "H3K4me3", "RRBS",
                "r2", "rmse", "mae", "pearson", "spearman",
                "sample_count", "eligible_count", "n_invalid",
                "status", "warning"]

EDGE_COLUMNS = ["split_type", "cell_line", "model",
                "parent_combination", "child_combination", "added_environment",
                "parent_r2", "child_r2", "delta_r2",
                "parent_rmse", "child_rmse", "delta_rmse",
                "parent_mae", "child_mae", "delta_mae",
                "delta_pearson", "delta_spearman",
                "ci_low", "ci_high", "ci_excludes_zero", "n_bootstrap", "bootstrap_status",
                "n_paired", "status", "warning"]

DAG_MD_MARKER = "<!-- FACTORIAL_DAG_SECTION -->"


# ---------------------------------------------------------------------------
# 1) 理论结构 (不依赖任何实验数据; 用于完整性校验)
# ---------------------------------------------------------------------------
def theoretical_nodes() -> List[Dict]:
    """16 个理论 combination (level = 启用的环境因子个数 0..4)。"""
    out: List[Dict] = []
    for k in range(len(ENV_FACTORS) + 1):
        for subset in itertools.combinations(ENV_FACTORS, k):
            combo = combo_name(set(subset))
            row = {"combination": combo, "environment_count": k}
            for f in ENV_FACTORS:
                row[FACTOR_LABELS[f]] = bool(f in subset)
            out.append(row)
    return out


def theoretical_edges() -> List[Dict]:
    """32 条理论有向边 S -> S∪{e} (每个组合的每个合法单因素增加关系)。"""
    out: List[Dict] = []
    for k in range(len(ENV_FACTORS)):
        for subset in itertools.combinations(ENV_FACTORS, k):
            s = set(subset)
            for e in ENV_FACTORS:
                if e in s:
                    continue
                out.append({"parent_combination": combo_name(s),
                            "child_combination": combo_name(s | {e}),
                            "added_environment": e})
    return out


def parents_of(combination: str) -> List[str]:
    """组合的全部直接父组合 (少一个环境), 按规范序。"""
    s = parse_environment_set(combination)
    if not s:
        return []
    return [combo_name(s - {e}) for e in sorted(s)]


def children_of(combination: str) -> List[str]:
    """组合的全部直接子组合 (多一个环境), 按规范序。"""
    s = parse_environment_set(combination)
    return [combo_name(s | {e}) for e in ENV_FACTORS if e not in s]


def combination_label(combination: str) -> str:
    """人类可读标签: sequence-only / CTCF + DNase / ALL (4 factors)。"""
    s = parse_environment_set(combination)
    if not s:
        return "sequence-only"
    if len(s) == len(ENV_FACTORS):
        return "ALL (4 factors)"
    return " + ".join(FACTOR_LABELS[f] for f in ENV_FACTORS if f in s)


# ---------------------------------------------------------------------------
# 2) 观测数据 -> nodes / edges
# ---------------------------------------------------------------------------
def _finite(value) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def experiment_validity(row: pd.Series, threshold: float = 10.0) -> Tuple[bool, str]:
    """单实验有效性: 缺失 / 发散 / 相关系数越界 -> (False, reason)。"""
    for metric in ("R2", "RMSE", "MAE"):
        v = row.get(metric)
        if not _finite(v):
            return False, f"{metric}_missing"
        if abs(float(v)) > float(threshold):
            return False, f"{metric}_diverged(|{metric}|>{threshold:g})"
    for metric in ("Pearson", "Spearman"):
        v = row.get(metric)
        if _finite(v) and abs(float(v)) > 1.5:
            return False, f"{metric}_out_of_range"
    return True, ""


def _groups(table: pd.DataFrame) -> List[Tuple]:
    keys = ["split_type", "cell_line", "model"]
    if all(k in table.columns for k in keys):
        return list(table.groupby(keys, dropna=False))
    return [((None, None, None), table)]


def build_environment_nodes(table: pd.DataFrame, threshold: float = 10.0) -> pd.DataFrame:
    """每个 (split, cell_line, model, combination) 一行 —— **包含理论存在但数据缺失的组合**。

    缺失不删除节点: `status='unavailable'`, 指标为 NaN。
    """
    rows: List[Dict] = []
    for (split, cell, model), group in _groups(table):
        for tnode in theoretical_nodes():
            combo = tnode["combination"]
            sub = group[group["environment"].astype(str).str.lower() == combo]
            valid_rows, reasons = [], []
            for _, r in sub.iterrows():
                ok, why = experiment_validity(r, threshold)
                (valid_rows.append(r) if ok else reasons.append(why))
            if valid_rows:
                vdf = pd.DataFrame(valid_rows)
                means = {m: (float(pd.to_numeric(vdf[m], errors="coerce").mean())
                             if m in vdf.columns else float("nan")) for m in NODE_METRICS}
                status = "ok"
                warning = ("invalid_experiments_excluded:" + ",".join(sorted(set(reasons)))
                           if reasons else "")
            else:
                means = {m: float("nan") for m in NODE_METRICS}
                status = "unavailable"
                warning = ("no experiment for this combination" if len(sub) == 0
                           else "all experiments invalid:" + ",".join(sorted(set(reasons))))
            row = {"split_type": split, "cell_line": cell, "model": model,
                   "combination": combo, "environment_count": tnode["environment_count"]}
            for f in ENV_FACTORS:
                row[FACTOR_LABELS[f]] = tnode[FACTOR_LABELS[f]]
            row.update({"r2": means["R2"], "rmse": means["RMSE"], "mae": means["MAE"],
                        "pearson": means["Pearson"], "spearman": means["Spearman"],
                        "sample_count": int(len(sub)), "eligible_count": int(len(valid_rows)),
                        "n_invalid": int(len(sub) - len(valid_rows)),
                        "status": status, "warning": warning})
            rows.append(row)
    out = pd.DataFrame(rows)
    return out[[c for c in NODE_COLUMNS if c in out.columns]]


def _edge_deltas(parent: pd.Series, child: pd.Series) -> Dict[str, float]:
    """一条边的 5 个配对增量 (缺失 -> NaN, 不伪造)。"""
    pairs = {"delta_r2": ("R2", None), "delta_rmse": ("RMSE", None), "delta_mae": ("MAE", None),
             "delta_pearson": ("Pearson", None), "delta_spearman": ("Spearman", None)}
    out: Dict[str, float] = {}
    for name, (metric, _) in pairs.items():
        pv, cv = parent.get(metric), child.get(metric)
        out[name] = float(cv) - float(pv) if (_finite(pv) and _finite(cv)) else float("nan")
    return out


def build_environment_edges(table: pd.DataFrame, threshold: float = 10.0,
                            nodes: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """32 条理论边的观测值; 每条边独立配对同 cohort (split, cell, model, seed)。"""
    rows: List[Dict] = []
    node_lookup = {}
    if nodes is not None and not nodes.empty:
        for _, n in nodes.iterrows():
            node_lookup[(n["split_type"], n["cell_line"], n["model"], n["combination"])] = n

    for (split, cell, model), group in _groups(table):
        by_env: Dict[str, List[pd.Series]] = {}
        for _, r in group.iterrows():
            by_env.setdefault(str(r["environment"]).lower(), []).append(r)

        for tedge in theoretical_edges():
            parent_combo = tedge["parent_combination"]
            child_combo = tedge["child_combination"]
            added = tedge["added_environment"]

            parent_rows = by_env.get(parent_combo, [])
            child_rows = by_env.get(child_combo, [])

            def _valid_map(rs: Sequence[pd.Series]) -> Tuple[Dict, List[str]]:
                keep, bad = {}, []
                for r in rs:
                    ok, why = experiment_validity(r, threshold)
                    if not ok:
                        bad.append(why)
                        continue
                    seed = r.get("random_seed")
                    if seed in keep:
                        bad.append("duplicate_seed")
                        continue
                    keep[seed] = r
                return keep, bad

            pvalid, pbad = _valid_map(parent_rows)
            cvalid, cbad = _valid_map(child_rows)
            paired = sorted(set(pvalid) & set(cvalid), key=lambda s: str(s))

            warnings: List[str] = []
            if pbad or cbad:
                warnings.append("INVALID_EXPERIMENTS_EXCLUDED")
            row = {"split_type": split, "cell_line": cell, "model": model,
                   "parent_combination": parent_combo, "child_combination": child_combo,
                   "added_environment": added}
            if not paired:
                if not parent_rows:
                    reason = f"parent_unavailable({parent_combo})"
                elif not child_rows:
                    reason = f"child_unavailable({child_combo})"
                elif not pvalid:
                    reason = "parent_all_invalid"
                elif not cvalid:
                    reason = "child_all_invalid"
                else:
                    reason = "no_paired_seed"
                row.update({k: float("nan") for k in
                            ("parent_r2", "child_r2", "delta_r2", "parent_rmse", "child_rmse",
                             "delta_rmse", "parent_mae", "child_mae", "delta_mae",
                             "delta_pearson", "delta_spearman", "ci_low", "ci_high",
                             "ci_excludes_zero", "n_bootstrap")})
                row["bootstrap_status"] = "unavailable"
                row.update({"n_paired": 0, "status": "unavailable",
                            "warning": ";".join(warnings + [reason, "CI_UNAVAILABLE"])})
                rows.append(row)
                continue

            deltas = [_edge_deltas(pvalid[s], cvalid[s]) for s in paired]
            ddf = pd.DataFrame(deltas)
            inconsistent = any(
                (_finite(d["delta_r2"]) and _finite(d["delta_rmse"])) and
                ((d["delta_r2"] > 0 and d["delta_rmse"] > 0) or
                 (d["delta_r2"] < 0 and d["delta_rmse"] < 0))
                for d in deltas)
            if inconsistent:
                warnings.append("METRIC_INCONSISTENCY")
            warnings.append("CI_UNAVAILABLE")   # bootstrap runner 未接通: 不伪造 CI
            row.update({
                "parent_r2": float(pd.to_numeric(pd.Series([pvalid[s].get("R2") for s in paired]),
                                                errors="coerce").mean()),
                "child_r2": float(pd.to_numeric(pd.Series([cvalid[s].get("R2") for s in paired]),
                                               errors="coerce").mean()),
                "parent_rmse": float(pd.to_numeric(pd.Series([pvalid[s].get("RMSE") for s in paired]),
                                                  errors="coerce").mean()),
                "child_rmse": float(pd.to_numeric(pd.Series([cvalid[s].get("RMSE") for s in paired]),
                                                 errors="coerce").mean()),
                "parent_mae": float(pd.to_numeric(pd.Series([pvalid[s].get("MAE") for s in paired]),
                                                 errors="coerce").mean()),
                "child_mae": float(pd.to_numeric(pd.Series([cvalid[s].get("MAE") for s in paired]),
                                                errors="coerce").mean()),
            })
            for col in DELTA_COLUMNS:
                row[col] = (float(ddf[col].mean()) if col in ddf.columns and
                            ddf[col].notna().any() else float("nan"))
            row.update({"ci_low": float("nan"), "ci_high": float("nan"),
                        "ci_excludes_zero": None, "n_bootstrap": 0,
                        "bootstrap_status": "not_run",
                        "n_paired": int(len(paired)), "status": "ok",
                        "warning": ";".join(warnings)})
            rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=EDGE_COLUMNS)
    return out[[c for c in EDGE_COLUMNS if c in out.columns]]


def merge_edge_ci(edges: pd.DataFrame, ci_table: Optional[pd.DataFrame]) -> pd.DataFrame:
    """合入真实的 bootstrap CI (analysis.stats.tasks.edge_ci_table 输出); 没有就保持 NaN。

    绝不伪造 CI: CI 缺失时保持 NaN + warning=CI_UNAVAILABLE。
    """
    out = edges.copy()
    if ci_table is None or ci_table.empty:
        return out
    keys = ["split_type", "cell_line", "model", "parent_combination", "child_combination"]
    if not all(k in ci_table.columns for k in keys):
        return out
    if not {"ci_low", "ci_high"}.issubset(ci_table.columns):
        return out
    extra = [c for c in ("ci_excludes_zero", "n_bootstrap", "bootstrap_status")
             if c in ci_table.columns]
    ci = ci_table[keys + ["ci_low", "ci_high"] + extra].copy()
    drop = [c for c in ["ci_low", "ci_high"] + extra if c in out.columns]
    out = out.drop(columns=drop).merge(ci, on=keys, how="left")
    has_ci = out["ci_low"].notna() | out["ci_high"].notna()
    warnings = (out["warning"].fillna("") if "warning" in out.columns
                else pd.Series("", index=out.index)).astype(str)
    with_ci = warnings.str.replace("CI_UNAVAILABLE", "CI_AVAILABLE", regex=False)
    out["warning"] = np.where(has_ci.to_numpy(), with_ci, warnings).tolist()
    for col in ("n_bootstrap",):
        if col in out.columns:
            out[col] = out[col].fillna(0).astype(int)
    if "bootstrap_status" in out.columns:
        out["bootstrap_status"] = out["bootstrap_status"].fillna("unavailable")
    return out


def load_edge_ci(tables_dir: str | Path) -> Optional[pd.DataFrame]:
    """查找已有的 bootstrap CI 表 (存在才用; 当前引擎通常没有)。"""
    candidates = ["environment_bootstrap.csv", "environment_edges_bootstrap.csv",
                  "bootstrap_environment.csv"]
    root = Path(tables_dir)
    for name in candidates:
        p = root / name
        if p.exists():
            try:
                df = pd.read_csv(p)
                if not df.empty:
                    return df
            except Exception:
                continue
    return None


# ---------------------------------------------------------------------------
# 3) Ablation view (与 additive view 严格区分) + 交互
# ---------------------------------------------------------------------------
def build_ablation_edges(edges: pd.DataFrame) -> pd.DataFrame:
    """Ablation view: ΔR²_ablation = R²(S) - R²(S∖{e}) = -ΔR²_{e|S∖{e}} (同配对 cohort)。

    与 additive view 是**不同的科学量**, 不得混称 "environment contribution"。
    """
    if edges is None or edges.empty:
        return pd.DataFrame(columns=["split_type", "cell_line", "model",
                                     "full_combination", "ablated_environment",
                                     "reduced_combination", "r2_full", "r2_reduced",
                                     "delta_r2_ablation", "delta_rmse_ablation",
                                     "n_paired", "status", "warning"])
    rows: List[Dict] = []
    for _, e in edges.iterrows():
        rows.append({
            "split_type": e["split_type"], "cell_line": e["cell_line"], "model": e["model"],
            "full_combination": e["child_combination"],
            "ablated_environment": e["added_environment"],
            "reduced_combination": e["parent_combination"],
            "r2_full": e.get("child_r2"), "r2_reduced": e.get("parent_r2"),
            "delta_r2_ablation": (-float(e["delta_r2"]) if _finite(e.get("delta_r2")) else np.nan),
            "delta_rmse_ablation": (-float(e["delta_rmse"]) if _finite(e.get("delta_rmse")) else np.nan),
            "n_paired": e.get("n_paired"), "status": e.get("status"),
            "warning": e.get("warning"),
        })
    return pd.DataFrame(rows)


def build_environment_interactions(table: pd.DataFrame) -> pd.DataFrame:
    """成对交互 (基于 factorial edges, 不从任何 canonical tree 猜测)。

    I(a,b) = 在含 b 背景上的 Δ(a|·) 均值 − 在不含 b 背景上的 Δ(a|·) 均值 (跨 seed 平均)。
    """
    raw = compute_conditional_increments(table)
    if raw.empty:
        return pd.DataFrame(columns=["split_type", "cell_line", "model", "factor_a", "factor_b",
                                     "interaction_r2", "n_seeds", "n_with_b", "n_without_b"])
    from analysis.environment.incremental_effect import compute_pair_interactions
    per_seed = compute_pair_interactions(raw)
    if per_seed.empty:
        return pd.DataFrame(columns=["split_type", "cell_line", "model", "factor_a", "factor_b",
                                     "interaction_r2", "n_seeds", "n_with_b", "n_without_b"])
    agg = per_seed.groupby(["split_type", "cell_line", "model", "factor_a", "factor_b"],
                           dropna=False).agg(
        interaction_r2=("interaction_r2", "mean"),
        n_seeds=("interaction_r2", "size"),
        n_with_b=("n_with_b", "mean"),
        n_without_b=("n_without_b", "mean"),
    ).reset_index()
    agg["interaction_r2"] = agg["interaction_r2"].round(6)
    return agg


# ---------------------------------------------------------------------------
# 4) 报告
# ---------------------------------------------------------------------------
def build_dag_report(nodes: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    """每个 (split, cell, model) 一行的完整性/缺失/异常统计。"""
    rows: List[Dict] = []
    if nodes is None or nodes.empty:
        return pd.DataFrame(columns=["split_type", "cell_line", "model",
                                     "theoretical_nodes", "observed_nodes", "unavailable_nodes",
                                     "theoretical_edges", "valid_edges", "unavailable_edges",
                                     "metric_inconsistency_edges", "invalid_experiments",
                                     "unavailable_combinations"])
    n_theo_nodes, n_theo_edges = len(theoretical_nodes()), len(theoretical_edges())
    for (split, cell, model), nsub in nodes.groupby(["split_type", "cell_line", "model"],
                                                    dropna=False):
        esub = edges[(edges["split_type"] == split) & (edges["cell_line"] == cell) &
                     (edges["model"] == model)] if not edges.empty else edges
        n_ok_nodes = int((nsub["status"] == "ok").sum())
        n_ok_edges = int((esub["status"] == "ok").sum()) if not esub.empty else 0
        rows.append({
            "split_type": split, "cell_line": cell, "model": model,
            "theoretical_nodes": n_theo_nodes, "observed_nodes": n_ok_nodes,
            "unavailable_nodes": n_theo_nodes - n_ok_nodes,
            "theoretical_edges": n_theo_edges, "valid_edges": n_ok_edges,
            "unavailable_edges": n_theo_edges - n_ok_edges,
            "metric_inconsistency_edges": int(esub["warning"].fillna("")
                                              .str.contains("METRIC_INCONSISTENCY").sum())
            if not esub.empty else 0,
            "invalid_experiments": int(nsub["n_invalid"].sum()),
            "unavailable_combinations": ", ".join(
                nsub.loc[nsub["status"] != "ok", "combination"].astype(str).tolist()),
        })
    return pd.DataFrame(rows)


def build_environment_effects_md(nodes: pd.DataFrame, edges: pd.DataFrame,
                                 report: pd.DataFrame, batch_dir: str = "") -> str:
    """summary/03_environment_effects.md 的 Factorial DAG 章节 (带幂等 marker)。"""
    n_theo_nodes, n_theo_edges = len(theoretical_nodes()), len(theoretical_edges())
    obs_nodes = int((nodes["status"] == "ok").sum()) if not nodes.empty else 0
    obs_edges = int((edges["status"] == "ok").sum()) if not edges.empty else 0
    incons = int(edges["warning"].fillna("").str.contains("METRIC_INCONSISTENCY").sum()) \
        if not edges.empty else 0
    ci_avail = int((edges["ci_low"].notna() | edges["ci_high"].notna()).sum()) \
        if not edges.empty else 0
    lines = [
        DAG_MD_MARKER,
        "## 2^4 Environment Factorial DAG",
        "",
        "### Factorial design",
        f"- 环境因子 {len(ENV_FACTORS)} 个 ({', '.join(FACTOR_LABELS[f] for f in ENV_FACTORS)}) "
        f"-> 理论组合 2^{len(ENV_FACTORS)} = {n_theo_nodes} nodes",
        f"- 理论有向边 (单因素增加关系) = 4 × 2^(4-1) = {n_theo_edges}",
        f"- 本批观测: 有效 nodes {obs_nodes} / {n_theo_nodes} × groups; "
        f"有效 edges {obs_edges}; METRIC_INCONSISTENCY edges {incons}; 有 CI 的 edges {ci_avail}",
        f"- batch: `{Path(batch_dir).name if batch_dir else 'n/a'}`",
        "",
        "### 定义",
        "| 元素 | 含义 |",
        "| :--- | :--- |",
        "| Node | 一个 environment combination (sequence-only 为 level 0) |",
        "| Directed edge | 从 S 增加一个新环境 e: S → S ∪ {e} |",
        "| Edge value | conditional incremental effect ΔR²_{e\\|S} = R²(S∪{e}) − R²(S) |",
        "| Primary metric | ΔR² (方向 = effect direction, **不是** statistical significance) |",
        "| Uncertainty | bootstrap CI (存在才展示; 本批未接通则保持 NaN) |",
        "",
        "### 为什么一个组合可以有多个父节点",
        "该 DAG 保留**不同环境添加顺序**产生的条件增量, 因此同一个 combination 可以有多个父节点:",
        "`CTCF → CTCF+DNase` (即 ΔR²_{DNase|CTCF}) 与 `DNase → CTCF+DNase` (即 ΔR²_{CTCF|DNase})",
        "都是合法边且必须同时存在。这正是 factorial design 的 context-dependent conditional effect,",
        "严格树结构无法表达 (树要求每个节点只有一个父节点)。",
        "",
        "### 缺失 / 异常处理",
        "- 组合缺失 -> `node.status = unavailable` (节点保留在理论结构中, 不删除);",
        "- 单实验发散/缺失/相关越界 -> 从均值与配对中排除, 计入 `n_invalid`, 并写 warning;",
        "- ΔR² 与 ΔRMSE 同向 (同一 paired cohort) -> 边标记 `METRIC_INCONSISTENCY`, **边仍然保留**;",
        "- CI 未接通时保持 NaN, 绝不伪造。",
        "",
        "### 两个视图必须区分命名",
        "| 视图 | 方向 | 定义 | 回答的问题 |",
        "| :--- | :--- | :--- | :--- |",
        "| Additive view (本 DAG) | sequence → ALL | ΔR²_{e\\|S} = R²(S+e) − R²(S) | 增加一个环境因子带来多少提升 |",
        "| Ablation view (辅助) | ALL → sequence | ΔR²_ablation = R²(S) − R²(S∖e) | 移除一个环境因子损失多少 |",
        "",
        "> 两者是不同的科学量, 不共用 \"environment contribution\" 这一名称。",
        "",
    ]
    if not report.empty:
        lines += ["### 本批完整性 (每 group)", "",
                  "| split | cell_line | model | nodes(ok/theory) | edges(valid/theory) | "
                  "inconsistency | invalid exp | unavailable combos |",
                  "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"]
        for _, r in report.iterrows():
            lines.append(f"| {r['split_type']} | {r['cell_line']} | {r['model']} | "
                         f"{r['observed_nodes']}/{r['theoretical_nodes']} | "
                         f"{r['valid_edges']}/{r['theoretical_edges']} | "
                         f"{r['metric_inconsistency_edges']} | {r['invalid_experiments']} | "
                         f"{str(r['unavailable_combinations'])[:120]} |")
        lines.append("")
    return "\n".join(lines)


def append_dag_section(summary_dir: str | Path, dag_md: str) -> Path:
    """把 DAG 章节写入 summary/03_environment_effects.md (幂等: 先移除旧章节)。"""
    summary = Path(summary_dir)
    summary.mkdir(parents=True, exist_ok=True)
    target = summary / "03_environment_effects.md"
    existing = target.read_text(encoding="utf-8") if target.exists() else \
        "# 03 Environment Effects\n"
    if DAG_MD_MARKER in existing:
        existing = existing.split(DAG_MD_MARKER)[0].rstrip() + "\n"
    target.write_text(existing.rstrip() + "\n\n" + dag_md.strip() + "\n", encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# 5) 编排 (数据 -> 表 -> 渲染)
# ---------------------------------------------------------------------------
def build_factorial_dag_tables(batch_dir: str | Path, threshold: Optional[float] = None,
                               tables_dir: Optional[str | Path] = None
                               ) -> Dict[str, pd.DataFrame]:
    """从统一 normalized experiment table 生成 nodes/edges/ablation/interactions。"""
    from analysis.config import AnalysisConfig
    from analysis.data.loaders import load_experiment_table

    thr = float(threshold if threshold is not None else
                AnalysisConfig().consensus.unstable_effect_threshold)
    table = load_experiment_table(batch_dir)
    nodes = build_environment_nodes(table, threshold=thr)
    edges = build_environment_edges(table, threshold=thr, nodes=nodes)
    ci_dir = Path(tables_dir) if tables_dir else (Path(batch_dir) / "summary" / "tables")
    edges = merge_edge_ci(edges, load_edge_ci(ci_dir))
    ablation = build_ablation_edges(edges)
    interactions = build_environment_interactions(table)
    return {"nodes": nodes, "edges": edges, "ablation": ablation,
            "interactions": interactions, "threshold": thr, "table": table}


def write_factorial_dag_artifacts(batch_dir: str | Path, tables_dir: str | Path,
                                  summary_dir: str | Path,
                                  threshold: Optional[float] = None,
                                  write_md: bool = True) -> Dict[str, str]:
    """写出 environment_nodes.csv / environment_edges.csv(+ablation/interactions) 与报告。"""
    tables_dir, summary_dir = Path(tables_dir), Path(summary_dir)
    tables_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)

    built = build_factorial_dag_tables(batch_dir, threshold=threshold, tables_dir=tables_dir)
    nodes, edges = built["nodes"], built["edges"]
    report = build_dag_report(nodes, edges)

    paths = {
        "nodes": str(tables_dir / "environment_nodes.csv"),
        "edges": str(tables_dir / "environment_edges.csv"),
        "ablation": str(tables_dir / "environment_ablation.csv"),
        "interactions": str(tables_dir / "environment_interactions.csv"),
        "report_csv": str(tables_dir / "environment_dag_report.csv"),
        "report_md": str(summary_dir / "environment_dag_report.md"),
    }
    nodes.to_csv(paths["nodes"], index=False)
    edges.to_csv(paths["edges"], index=False)
    built["ablation"].to_csv(paths["ablation"], index=False)
    built["interactions"].to_csv(paths["interactions"], index=False)
    report.to_csv(paths["report_csv"], index=False)

    dag_md = build_environment_effects_md(nodes, edges, report, batch_dir=str(batch_dir))
    paths["dag_md"] = dag_md
    if write_md:
        paths["environment_effects_md"] = str(append_dag_section(summary_dir, dag_md))

    rep_lines = ["# Environment Factorial DAG Report", "",
                 f"- 理论 nodes: {len(theoretical_nodes())}; 理论 edges: {len(theoretical_edges())}",
                 f"- 观测有效 nodes: {int((nodes['status'] == 'ok').sum()) if not nodes.empty else 0}",
                 f"- 观测有效 edges: {int((edges['status'] == 'ok').sum()) if not edges.empty else 0}",
                 f"- METRIC_INCONSISTENCY edges: "
                 f"{int(edges['warning'].fillna('').str.contains('METRIC_INCONSISTENCY').sum()) if not edges.empty else 0}",
                 f"- 有 CI 的 edges: "
                 f"{int((edges['ci_low'].notna() | edges['ci_high'].notna()).sum()) if not edges.empty else 0}",
                 f"- 异常阈值 |metric| > {built['threshold']:g}", "",
                 "## Groups", "",
                 "| split | cell_line | model | nodes | edges | inconsistency | unavailable |",
                 "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"]
    for _, r in report.iterrows():
        rep_lines.append(f"| {r['split_type']} | {r['cell_line']} | {r['model']} | "
                         f"{r['observed_nodes']}/{r['theoretical_nodes']} | "
                         f"{r['valid_edges']}/{r['theoretical_edges']} | "
                         f"{r['metric_inconsistency_edges']} | "
                         f"{str(r['unavailable_combinations'])[:150]} |")
    rep_lines.append("")
    Path(paths["report_md"]).write_text("\n".join(rep_lines), encoding="utf-8")
    return paths


def generate_environment_factorial_dag(batch_dir: str | Path,
                                       figures_dir: str | Path,
                                       tables_dir: Optional[str | Path] = None,
                                       summary_dir: Optional[str | Path] = None,
                                       threshold: Optional[float] = None,
                                       orientation: str = "sequence_top") -> Dict[str, object]:
    """完整入口: tables -> (nodes/edges csv) -> factorial_dag / conditional_delta_r2 PNG。"""
    batch = Path(batch_dir)
    figures_dir = Path(figures_dir)
    # 2026-09-13: 产物根由 <batch>/analyse_out 改为 <batch>/summary，
    # 报告子目录随之改名 summary/ -> summary/reports/ (避免 summary/summary 套娃)。
    tables_dir = Path(tables_dir) if tables_dir else (batch / "summary" / "tables")
    summary_dir = Path(summary_dir) if summary_dir else (batch / "summary" / "reports")

    paths = write_factorial_dag_artifacts(batch, tables_dir, summary_dir, threshold=threshold)
    nodes = pd.read_csv(paths["nodes"])
    edges = pd.read_csv(paths["edges"])

    from analysis.visualization.factorial_dag import (render_ablation_delta_r2,
                                                     render_conditional_delta_r2,
                                                     render_environment_interactions,
                                                     render_factorial_dag)
    figs = render_factorial_dag(nodes, edges, figures_dir, orientation=orientation)
    delta_figs = render_conditional_delta_r2(edges, figures_dir)
    ablation = pd.read_csv(paths["ablation"])
    interactions = pd.read_csv(paths["interactions"])
    ablation_figs = render_ablation_delta_r2(ablation, figures_dir)
    interaction_figs = render_environment_interactions(interactions, figures_dir)
    return {"paths": paths, "dag_figures": figs, "delta_figures": delta_figs,
            "ablation_figures": ablation_figs, "interaction_figures": interaction_figs,
            "nodes": nodes, "edges": edges}
