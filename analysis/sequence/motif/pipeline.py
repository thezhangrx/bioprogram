"""analysis.sequence.motif.pipeline — motif discovery 编排 (tables → figures → markdown)。

数据流 (只读已有 artifact):
    tables/attribution_summary.csv  +  <data_root>/<cell>_metadata.csv
        -> seqlets -> clustering -> motif candidates
        -> enrichment (可选) -> stability / cross-model
        -> tables/motif_*.csv + figures/04_motif/* + summary/04_sequence_and_motifs.md
        -> motif evidence rows (进入 evidence_matrix)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analysis.config import AnalysisConfig, MotifDiscoveryConfig
from analysis.sequence.motif import core
from analysis.sequence.motif.iupac import (IUPAC_TO_BASES, information_content,
                                          matches_iupac, pfm_from_instances)

MOTIF_MD_MARKER = "<!-- MOTIF_DISCOVERY_SECTION -->"


def _safe(value) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_")


def _plan_flags(plan) -> Tuple[bool, bool]:
    seq = getattr(plan, "sequence", None)
    discovery = bool(getattr(seq, "motif_discovery", True)) if seq else True
    enrichment = bool(getattr(seq, "motif_enrichment", False)) if seq else False
    return discovery, enrichment


def run_motif_discovery(attribution_table: pd.DataFrame,
                        batch_dir: str | Path,
                        data_root: Optional[str | Path] = None,
                        config: Optional[AnalysisConfig] = None,
                        discovery: bool = True,
                        enrichment: bool = False) -> Dict[str, object]:
    """完整 motif discovery; 返回 {tables, figures, motifs, summary}。"""
    cfg = (config or AnalysisConfig()).motif
    root = Path(data_root) if data_root else Path(cfg.data_root)
    attr = core.load_attribution(attribution_table, cfg)
    signed_col = core.signed_value_column(attr)      # 只在序列 attribution 行上判断
    signed_profiles = core.signed_profiles(attr, signed_col) if signed_col else {}
    result: Dict[str, object] = {
        "motifs": [], "instances": [], "enrichment": [], "consistency": [],
        "tables": {}, "figures": [], "summary": {}, "signed_column": signed_col,
        "unavailable_reasons": [],
    }
    if not discovery:
        result["unavailable_reasons"].append("user_disabled (sequence.motif_discovery=false)")
        return result
    if attr.empty:
        result["unavailable_reasons"].append(
            "no compatible sequence attribution artifact (CNN ISM/IG or Transformer IG)")
        return result

    profiles = core.position_profiles(attr)
    sequences_by_cell: Dict[str, pd.DataFrame] = {}
    for cell in sorted(set(attr["cell_line"]) - {"none", "nan", ""}):
        seqs = core.load_sequences(root, cell)
        if not seqs.empty:
            sequences_by_cell[cell] = seqs
    if not sequences_by_cell:
        result["unavailable_reasons"].append(
            f"no sequence metadata under {root} (<cell_line>_metadata.csv)")
        return result

    all_seqlets: List[Dict] = []
    motif_seqlets: Dict[Tuple, List[Dict]] = {}
    for key, profile in profiles.items():
        model, arch, split, cell, environment, method = key
        seqs = sequences_by_cell.get(cell)
        if seqs is None:
            continue
        if method not in cfg.primary_methods:
            # Transformer IG 若存在则可用; attention 只作 supporting, 不生成 motif
            if method != cfg.transformer_ig_method:
                continue
        context = {"model": model, "model_variant": arch, "split_type": split,
                   "environment": environment, "attribution_method": method}
        seqlets = core.extract_seqlets(
            seqs, profile, cfg, context, signed=bool(signed_col),
            signed_profile=signed_profiles.get(key) if signed_col else None)
        if not seqlets:
            continue
        core.add_dual_method_effects(seqlets, profiles)
        all_seqlets.extend(seqlets)
        motif_seqlets[key] = seqlets

    # 正负方向分开 (有符号 attribution 时); 当前批次为 unsigned -> 单一分组, 方向在 motif 级给出
    clusters: List[Dict] = []
    for key, seqlets in motif_seqlets.items():
        def _bucket(sl: Dict) -> str:
            d = str(sl.get("direction", "unsigned"))
            return d if d in ("signed_positive", "signed_negative") else "unsigned"

        directions: Dict[str, List[Dict]] = {}
        for sl in seqlets:
            directions.setdefault(_bucket(sl), []).append(sl)
        for tag, group in directions.items():
            if not group:
                continue
            got = core.cluster_seqlets(group, cfg)
            clusters.extend(core.finalize_clusters(got, cfg, sequences_by_cell))

    # per-context 截断 (按 support 排序), 避免同一 context 产出上百个近重复 motif
    by_context: Dict[Tuple, List[Dict]] = {}
    for cl in clusters:
        key = (cl["model_source"], cl.get("model_variant"), cl["split_type"],
               cl["cell_lines"][0], cl["environment"], cl["attribution_method"],
               cl.get("direction", "unsigned"))
        by_context.setdefault(key, []).append(cl)
    capped: List[Dict] = []
    for key, group in by_context.items():
        group.sort(key=lambda c: (c["support_count"], -c["ambiguous_fraction"]), reverse=True)
        ok = [c for c in group if c.get("ambiguous_fraction", 1.0) <= cfg.max_ambiguous_fraction]
        vague = [c for c in group if c.get("ambiguous_fraction", 1.0) > cfg.max_ambiguous_fraction]
        capped.extend(ok[:int(cfg.max_motifs_per_context)])
        capped.extend(vague[:int(cfg.max_exploratory_per_context)])
    clusters = capped

    # motif id + region
    motifs: List[Dict] = []
    for i, cl in enumerate(sorted(clusters, key=lambda c: c["support_count"], reverse=True), 1):
        cl["motif_id"] = (f"motif_{_safe(cl['model_variant'] or cl['model_source'])}_"
                          f"{_safe(cl['cell_lines'][0])}_{_safe(cl['environment'])}_"
                          f"{_safe(cl['attribution_method'])}_{i:03d}")
        cl["region"] = core.region_of(cl["position_start"], cl["position_end"], cfg)
        motifs.append(cl)

    # enrichment (独立可选步骤)
    enrichment_rows: List[Dict] = []
    if enrichment and motifs:
        for m in motifs:
            enrichment_rows.append(core.enrichment_for_motif(m, sequences_by_cell, cfg,
                                                            cfg.enrichment_fdr))
        enrichment_rows = core.apply_enrichment_fdr(enrichment_rows)
    elif not enrichment:
        for m in motifs:
            enrichment_rows.append({"motif_id": m["motif_id"], "fdr_family": "motif_enrichment",
                                    "status": "not_performed",
                                    "reason": "motif_enrichment=false in AnalysisPlan",
                                    "foreground_count": None, "foreground_total": None,
                                    "background_count": None, "background_total": None,
                                    "effect": None, "enrichment": None, "odds_ratio": None,
                                    "p_value": None, "FDR": None})
    enrich_by_id = {r["motif_id"]: r for r in enrichment_rows}

    # stability / consistency
    consistency_rows = _build_consistency(motifs, cfg)
    for m in motifs:
        e = enrich_by_id.get(m["motif_id"], {})
        fdr = e.get("FDR") if e.get("status") == "ok" else None
        m["enrichment"] = e.get("enrichment")
        m["odds_ratio"] = e.get("odds_ratio")
        m["p_value"] = e.get("p_value")
        m["FDR"] = fdr
        m["stability"] = _stability_value(m)
        m["model_consistency"] = _n_members(consistency_rows, m["motif_id"], "cnn_kernel_variant")
        m["cellline_consistency"] = _n_members(consistency_rows, m["motif_id"], "cell_line")
        m["evidence_strength"] = core.stability_label(m, cfg, fdr)
        m["status"] = m.get("status", "ok")
        if m.get("ambiguous_fraction", 0) > cfg.max_ambiguous_fraction:
            m["status"] = "exploratory"
        m["warning"] = ("" if signed_col else
                        "attribution_unsigned: direction from measured efficacy contrast")
        m["seed_support"] = None
        m["direction"] = m.get("direction", "unsigned")

    result.update({"motifs": motifs, "enrichment": enrichment_rows,
                   "consistency": consistency_rows,
                   "instances": all_seqlets, "sequences": sequences_by_cell})
    result["summary"] = {
        "n_seqlets": len(all_seqlets),
        "n_motifs": len(motifs),
        "n_cell_lines": len(sequences_by_cell),
        "n_contexts": len(motif_seqlets),
        "signed_attribution": bool(signed_col),
        "enrichment_performed": bool(enrichment),
    }
    return result


def _n_members(rows: List[Dict], motif_id: str, comparison_type: str) -> Optional[int]:
    for r in rows:
        if r["motif_id"] == motif_id and r["comparison_type"] == comparison_type:
            return int(r["n_supporting"])
    return None


def _stability_value(motif: Dict) -> str:
    if motif.get("model_consistency") is None:
        return "unavailable"
    return f"models={motif['model_consistency']};celllines={motif.get('cellline_support')}"


def _build_consistency(motifs: List[Dict], cfg: MotifDiscoveryConfig) -> List[Dict]:
    """跨 CNN kernel variant 与跨 cell-line 的 motif 支持; seed 支持如实记为 unavailable。"""
    rows: List[Dict] = []
    groups: Dict[Tuple[str, str], List[Dict]] = {}
    for m in motifs:
        groups.setdefault((m["environment"], m["attribution_method"]), []).append(m)
    for (env, method), members in groups.items():
        variants = sorted({str(m.get("model_variant")) for m in members})
        for m in members:
            shared = []
            for other in members:
                if other is m or other["length"] != m["length"]:
                    continue
                sim = _iupac_similarity(m["iupac"], other["iupac"])
                if sim >= cfg.stability_similarity:
                    shared.append(f"{other['model_variant']}:{other['motif_id']}")
            rows.append({"motif_id": m["motif_id"],
                         "comparison_type": "cnn_kernel_variant",
                         "group": f"{env}|{method}", "n_supporting": 1 + len(shared),
                         "n_total": max(len(variants), 1),
                         "supporting_members": ";".join(sorted({str(m.get("model_variant"))} |
                                                               {s.split(":")[0] for s in shared})),
                         "shared_with": ";".join(sorted(shared)), "similarity": 1.0,
                         "status": "ok", "reason": ""})
    # 跨 cell line: 同 environment/method/variant 下 consensus 相似的 motif
    for m in motifs:
        others = [o for o in motifs
                  if o is not m and o["environment"] == m["environment"]
                  and o["attribution_method"] == m["attribution_method"]
                  and o["model_variant"] == m["model_variant"]
                  and o["length"] == m["length"]
                  and set(o["cell_lines"]) != set(m["cell_lines"])
                  and _iupac_similarity(m["iupac"], o["iupac"]) >= cfg.stability_similarity]
        rows.append({"motif_id": m["motif_id"], "comparison_type": "cell_line",
                     "group": f"{m['environment']}|{m['attribution_method']}",
                     "n_supporting": len({c for o in others for c in o["cell_lines"]} |
                                         set(m["cell_lines"])),
                     "n_total": len({o['cell_lines'][0] for o in others} | set(m["cell_lines"])),
                     "supporting_members": ";".join(sorted({c for o in others
                                                            for c in o["cell_lines"]} |
                                                           set(m["cell_lines"]))),
                     "shared_with": ";".join(sorted(o["motif_id"] for o in others)),
                     "similarity": 1.0, "status": "ok", "reason": ""})
    # transformer: 无 IG artifact -> 明确 unavailable (attention 不是 motif extractor)
    rows.append({"motif_id": "(all)", "comparison_type": "cross_model_transformer",
                 "group": "cnn_vs_transformer", "n_supporting": 0, "n_total": 1,
                 "supporting_members": "", "shared_with": "", "similarity": None,
                 "status": "unavailable",
                 "reason": ("no Transformer IG artifact: only Transformer_Attention exists, "
                            "and attention is not a motif extractor")})
    rows.append({"motif_id": "(all)", "comparison_type": "seed", "group": "mixed_seeds",
                 "n_supporting": 0, "n_total": 0, "supporting_members": "", "shared_with": "",
                 "similarity": None, "status": "unavailable",
                 "reason": ("attribution_summary 不含 random_seed -> seed-level motif support "
                            "无法计算; 用 sample/model-variant/cell-line support 代替")})
    return rows


def _iupac_similarity(a: str, b: str) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    hits = 0
    for ca, cb in zip(a, b):
        ba = set(IUPAC_TO_BASES.get(ca.upper(), ()))
        bb = set(IUPAC_TO_BASES.get(cb.upper(), ()))
        if ba and bb and ba & bb:
            hits += 1
    return hits / len(a)


# ---------------------------------------------------------------------------
# 表格 / 图 / 报告
# ---------------------------------------------------------------------------
def write_motif_tables(result: Dict, tables_dir: str | Path) -> Dict[str, str]:
    tables = Path(tables_dir)
    tables.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, str] = {}
    motifs = result.get("motifs", [])

    cand_rows = []
    for m in motifs:
        row = {c: m.get(c) for c in core.CANDIDATE_COLUMNS}
        row["sequence"] = m.get("sequence")
        row["position_distribution"] = m.get("position_distribution")
        row["preferred_position"] = _preferred_position(m)
        row["seed_support"] = None
        cand_rows.append(row)
    cand = pd.DataFrame(cand_rows, columns=core.CANDIDATE_COLUMNS)
    cand.to_csv(tables / "motif_candidates.csv", index=False)
    paths["candidates"] = str(tables / "motif_candidates.csv")

    inst_rows = []
    for m in motifs:
        for inst in m["instances"]:
            inst_rows.append({"motif_id": m["motif_id"], **{k: inst.get(k) for k in
                             core.INSTANCE_COLUMNS if k != "motif_id"}})
    inst = pd.DataFrame(inst_rows, columns=core.INSTANCE_COLUMNS)
    inst.to_csv(tables / "motif_instances.csv", index=False)
    paths["instances"] = str(tables / "motif_instances.csv")

    enr = pd.DataFrame(result.get("enrichment", []), columns=core.ENRICHMENT_COLUMNS)
    enr.to_csv(tables / "motif_enrichment.csv", index=False)
    paths["enrichment"] = str(tables / "motif_enrichment.csv")

    cons = pd.DataFrame(result.get("consistency", []), columns=core.CONSISTENCY_COLUMNS)
    cons.to_csv(tables / "motif_consistency.csv", index=False)
    paths["consistency"] = str(tables / "motif_consistency.csv")

    ev = motif_evidence_rows(motifs, result.get("enrichment", []))
    pd.DataFrame(ev).to_csv(tables / "motif_evidence.csv", index=False)
    paths["evidence"] = str(tables / "motif_evidence.csv")
    return paths


def _preferred_position(m: Dict) -> str:
    dist = {}
    for part in str(m.get("position_distribution") or "").split(";"):
        if ":" in part:
            pos, cnt = part.split(":", 1)
            try:
                dist[int(pos)] = int(cnt)
            except ValueError:
                continue
    if not dist:
        return ""
    top = sorted(dist.items(), key=lambda kv: kv[1], reverse=True)[:3]
    return ";".join(str(p) for p, _ in sorted(top))


def motif_evidence_rows(motifs: List[Dict], enrichment_rows: List[Dict]) -> List[Dict]:
    """motif -> Evidence Matrix 行 (feature_type='motif'), 复用统一 tier 规则。

    coverage 口径 = **支持的 model family 数** (当前只有 CNN 能做 motif discovery;
    Transformer 无 IG -> 不计入), 不用 kernel variant 数冒充跨模型覆盖;
    kernel variant 复现与 cell-line 复现分别放在 model_variant_support / cellline_support 列。
    """
    from analysis.evidence.integration import classify_evidence_tier
    from analysis.schemas import EvidenceTier

    cfg = AnalysisConfig()
    enr = {r["motif_id"]: r for r in enrichment_rows}
    families = sorted({str(m.get("model_source") or "cnn") for m in motifs}) or ["cnn"]
    n_families = len(families)
    rows: List[Dict] = []
    for m in motifs:
        e = enr.get(m["motif_id"], {})
        fdr = e.get("FDR") if e.get("status") == "ok" else None
        variants = int(m.get("model_consistency") or 1)
        cells = int(m.get("cellline_consistency") or m.get("cellline_support") or 1)
        supporting = n_families
        applicable = n_families
        statistical = bool(fdr is not None and fdr < cfg.statistical.fdr_weak)
        # effect 门复用 Tier 的权威阈值 (最小绝对增益门), 不另设副本
        strong = bool(statistical or (m.get("mean_effect") is not None and
                                      abs(float(m.get("mean_effect") or 0)) >=
                                      cfg.evidence.min_absolute_delta_r2
                                      and variants >= cfg.motif.evidence_strong_min_models))
        tier = classify_evidence_tier(
            applicable_model_count=applicable, supporting_model_count=supporting,
            concordance=None, strong_stat_or_attribution=strong, ci_crosses_zero=None,
            config=cfg)
        if m.get("effect_direction") is None and tier == EvidenceTier.TIER1:
            tier = EvidenceTier.TIER3
        rows.append({
            "feature": m.get("human_pattern") or m.get("iupac"),
            "feature_type": "motif",
            "applicable_models": str(m.get("model_variant") or m.get("model_source")),
            "coverage": supporting,
            "coverage_detail": f"{supporting}/{n_families} model families",
            "model_families": ";".join(families),
            "model_variant_support": variants,
            "cellline_support_count": cells,
            "direction_concordance": None,
            "cell_line_consistency": f"{m.get('cellline_support')} cell line(s)",
            "overall_effect": m.get("mean_effect"),
            "model_effects": "",
            "unstable_rows_excluded": 0,
            "ci_low": None, "ci_high": None, "ci_excludes_zero": None, "n_bootstrap": 0,
            "bootstrap_status": "not_applicable (motif effect uses measured-efficacy contrast)",
            "permutation_p": e.get("p_value"),
            "permutation_fdr": fdr,
            "permutation_status": e.get("status", "not_performed"),
            "evidence_tier": tier.value,
            "motif_id": m["motif_id"],
            "iupac": m.get("iupac"),
            "human_pattern": m.get("human_pattern"),
            "regex": m.get("regex"),
            "effect_direction": m.get("effect_direction"),
            "direction_source": m.get("direction_source"),
            "support_count": m.get("support_count"),
            "evidence_strength": m.get("evidence_strength"),
        })
    return rows


def render_motif_figures(result: Dict, figures_dir: str | Path,
                         max_logos: int = 12) -> List[str]:
    motifs = result.get("motifs", [])
    out_dir = Path(figures_dir) / "04_motif"
    (out_dir / "motif_logos").mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for m in sorted(motifs, key=lambda x: x["support_count"], reverse=True)[:max_logos]:
        p = out_dir / "motif_logos" / f"{_safe(m['motif_id'])}.png"
        _draw_logo(m, p)
        written.append(str(p))
    if motifs:
        p = out_dir / "motif_position_distribution.png"
        _draw_positions(motifs, p)
        written.append(str(p))
        p = out_dir / "motif_consistency.png"
        _draw_consistency(motifs, result.get("consistency", []), p)
        written.append(str(p))
    enr = [r for r in result.get("enrichment", []) if r.get("status") == "ok"]
    if enr:
        p = out_dir / "motif_enrichment.png"
        _draw_enrichment(enr, p)
        written.append(str(p))
    return written


def _draw_logo(motif: Dict, path: Path) -> None:
    pfm = motif.get("pfm")
    if pfm is None or np.asarray(pfm).sum() == 0:
        pfm = pfm_from_instances([i["sequence"] for i in motif["instances"]], motif["length"])
    pfm = np.asarray(pfm, dtype=float)
    ic = information_content(pfm)
    total = pfm.sum(axis=0, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        freq = np.where(total > 0, pfm / total, 0.0)
    colors = {"A": "#2e7d32", "C": "#1565c0", "G": "#ef6c00", "T": "#c62828"}
    fig, ax = plt.subplots(figsize=(max(3.0, 0.45 * motif["length"] + 1.6), 2.6), dpi=150)
    for j in range(pfm.shape[1]):
        bottom = 0.0
        for i, base in enumerate(core.SEQ_CHANNELS):
            h = float(freq[i, j] * ic[j])
            if h <= 0:
                continue
            ax.bar(j + 1, h, bottom=bottom, color=colors[base], width=0.85,
                   edgecolor="white", linewidth=0.4)
            if h > 0.25:
                ax.text(j + 1, bottom + h / 2, base, ha="center", va="center",
                        fontsize=7, color="white")
            bottom += h
    ax.set_xticks(range(1, pfm.shape[1] + 1))
    ax.set_xticklabels([str(motif["position_start"] + k) for k in range(pfm.shape[1])],
                       fontsize=6)
    ax.set_ylabel("bits", fontsize=7)
    ax.set_ylim(0, 2.05)
    ax.set_title(f"{motif['motif_id']}\n{motif['human_pattern']}  (IUPAC {motif['iupac']})",
                 fontsize=7)
    ax.tick_params(axis="y", labelsize=6)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _draw_positions(motifs: List[Dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    for m in motifs[:8]:
        dist = {}
        for part in str(m.get("position_distribution") or "").split(";"):
            if ":" in part:
                p, c = part.split(":", 1)
                try:
                    dist[int(p)] = int(c)
                except ValueError:
                    continue
        if not dist:
            continue
        xs = sorted(dist)
        ax.plot(xs, [dist[x] for x in xs], marker="o", ms=3, lw=1,
                label=f"{m['iupac']} ({m['support_count']})")
    ax.set_xlabel("seqlet start position (1-based)", fontsize=8)
    ax.set_ylabel("seqlet count", fontsize=8)
    ax.set_title("Motif position distribution (top motifs)", fontsize=9)
    ax.legend(fontsize=6, ncol=2)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _draw_consistency(motifs: List[Dict], consistency: List[Dict], path: Path) -> None:
    n_models = [int(m.get("model_consistency") or 0) for m in motifs[:20]]
    n_cells = [int(m.get("cellline_support") or 0) for m in motifs[:20]]
    labels = [m["iupac"] for m in motifs[:20]]
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(7.5, max(3.0, 0.3 * len(labels) + 1.5)), dpi=150)
    ax.barh(y - 0.2, n_models, height=0.4, color="#1565c0", label="model variants supporting")
    ax.barh(y + 0.2, n_cells, height=0.4, color="#2e7d32", label="cell lines supporting")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6)
    ax.set_xlabel("support count", fontsize=8)
    ax.set_title("Motif stability (model-variant / cell-line support; seed support unavailable)",
                 fontsize=8.5)
    ax.legend(fontsize=7)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _draw_enrichment(rows: List[Dict], path: Path) -> None:
    df = pd.DataFrame(rows).sort_values("odds_ratio", ascending=True)
    labels = [f"{r['motif_id'].split('_')[-1]}" for _, r in df.iterrows()]
    fig, ax = plt.subplots(figsize=(7.5, max(3.0, 0.3 * len(df) + 1.5)), dpi=150)
    y = np.arange(len(df))
    vals = pd.to_numeric(df["odds_ratio"], errors="coerce").fillna(0.0)
    colors = ["#2e7d32" if v > 1 else "#c62828" for v in vals]
    ax.barh(y, np.log2(np.maximum(vals, 1e-6)), color=colors, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6)
    for yi, (v, fdr) in enumerate(zip(vals, df["FDR"])):
        ax.text(0.02, yi, f"OR={v:.2f} FDR={fdr:.3g}" if pd.notna(fdr) else f"OR={v:.2f}",
                va="center", fontsize=5.5)
    ax.axvline(0, color="k", lw=0.8, ls="--")
    ax.set_xlabel("log2 odds ratio (foreground vs background)", fontsize=8)
    ax.set_title("Motif enrichment (Fisher exact + BH-FDR, family=motif_enrichment)", fontsize=8.5)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def build_motif_md(result: Dict, cfg: MotifDiscoveryConfig, batch_dir: str = "") -> str:
    """summary/04_sequence_and_motifs.md 的 Motif Discovery 章节 (含 Methodology)。"""
    motifs = result.get("motifs", [])
    summ = result.get("summary", {})
    lines = [MOTIF_MD_MARKER, "## Sequence Motif Discovery", "",
             "> Motif 表示 *sequence pattern associated with model-predicted / measured editing "
             "efficiency* 的候选序列模式, **不是**因果结论, 也不称 \"significant motif\" "
             "除非 enrichment 通过 FDR。", ""]
    if not motifs:
        reason = "; ".join(result.get("unavailable_reasons", [])) or "no motif passed support thresholds"
        lines += ["**Status: unavailable**", "", f"- reason: {reason}", ""]
        return "\n".join(lines)

    lines += ["### Methodology (可直接追溯)", "",
              "| 项 | 值 |", "| :--- | :--- |",
              f"| Motif source | {', '.join(cfg.model_families)} "
              f"(Transformer IG: "
              f"{'available' if cfg.transformer_ig_method in set() else 'unavailable (只有 attention, 不作 extractor)'}) |",
              f"| Attribution method | primary: {', '.join(cfg.primary_methods)}; "
              f"supporting: {', '.join(cfg.supporting_methods) or '-'} |",
              f"| Contexts | {', '.join(cfg.contexts)} (environment-masked 模型不作为序列 motif 来源) |",
              f"| Seqlet extraction | 位置级 attribution 分位 q={cfg.attribution_quantile} + "
              f"局部连续 (q={cfg.continuity_quantile}, >= {cfg.continuity_min_positions} 连续位置), "
              f"每样本 <= {cfg.max_seqlets_per_sample} 窗口; **不是 top-N 单点** |",
              f"| Motif length range | {cfg.min_length}-{cfg.max_length} nt (由 attribution 窗口与"
              f"聚类确定; kernel size 不等于 motif 长度) |",
              f"| Clustering | 贪心相似度聚类 (与 cluster consensus 一致率 >= "
              f"{cfg.similarity_threshold}) |",
              f"| Minimum support | seqlet >= {cfg.min_seqlet_support}, sample >= "
              f"{cfg.min_sample_support} |",
              f"| Consensus representation | IUPAC 退化码 (次优碱基频率 >= {cfg.degenerate_fraction}) |",
              "| Human-readable representation | (A/G)TC 形式 (human_pattern 列) |",
              "| Regex representation | [AG]TC 形式 (regex 列, 与 human_pattern 分开保存) |",
              f"| Enrichment | {'performed' if summ.get('enrichment_performed') else 'not performed'} "
              f"(foreground = efficacy 上 {cfg.enrichment_foreground_quantile:.0%}; "
              f"background = {cfg.enrichment_background}); Fisher exact + BH-FDR "
              f"family=motif_enrichment, threshold FDR < {cfg.enrichment_fdr} |",
              f"| Direction | attribution 无符号 -> 由 carrier vs background measured-efficacy "
              f"对比给出 (`direction_source` 列记录) |",
              f"| Stability criteria | 跨 CNN kernel variant (相似度 >= {cfg.stability_similarity}) "
              f"与跨 cell line; seed-level 见下方说明 |",
              f"| Region definitions | {cfg.region_ranges or 'schema 未定义 seed/PAM -> 全部 Other (不假设)'} |",
              ""]

    lines += ["### Motif candidates", "",
              "| motif_id | consensus | IUPAC | human pattern | regex | len | support | "
              "samples | cell lines | mean effect | direction | enrichment (FDR) | evidence |",
              "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"]
    for m in motifs[:40]:
        enr = m.get("enrichment")
        fdr = m.get("FDR")
        enr_txt = (f"{enr:.3g} (FDR={fdr:.3g})" if enr is not None and fdr is not None
                   else "not performed / unavailable")
        lines.append(f"| {m['motif_id']} | {m['consensus']} | {m['iupac']} | "
                     f"`{m['human_pattern']}` | `{m['regex']}` | {m['length']} | "
                     f"{m['support_count']} | {m['sample_support']} | {m['cellline_support']} | "
                     f"{m.get('mean_effect'):+.4f} | {m.get('effect_direction') or 'n/a'} | "
                     f"{enr_txt} | {m.get('evidence_strength')} |")
    lines += ["", f"- seqlets: **{summ.get('n_seqlets')}**; motifs passing support: "
                  f"**{summ.get('n_motifs')}**; contexts: {summ.get('n_contexts')}; "
                  f"cell lines with sequences: {summ.get('n_cell_lines')}",
              "- 位置分布 / logo / consistency 图见 `figures/04_motif/`;",
              "- seed-level motif support: **unavailable** (attribution_summary 不含 random_seed)。", ""]

    lines += ["### Limitations", "",
              "- attribution 为无符号 magnitude -> 不能按 attribution 正负分组; 方向来自 measured "
              "efficacy 对比 (关联性, 非因果);",
              "- 当前批次无 Transformer IG -> cross-model (CNN vs Transformer) 比较 unavailable; "
              "attention 不作 motif extractor;",
              "- motif 长度由窗口/聚类决定, 与 CNN kernel size 无关;",
              "- enrichment 若未在 AnalysisPlan 中启用, 则没有任何 p-value / FDR, "
              "不得称 statistically enriched。", ""]
    return "\n".join(lines)


def append_motif_section(summary_dir: str | Path, md: str) -> Path:
    """写入 summary/04_sequence_and_motifs.md (幂等: 先移除旧章节)。"""
    summary = Path(summary_dir)
    summary.mkdir(parents=True, exist_ok=True)
    target = summary / "04_sequence_and_motifs.md"
    existing = target.read_text(encoding="utf-8") if target.exists() else \
        "# 04 Sequence & Motifs\n"
    if MOTIF_MD_MARKER in existing:
        existing = existing.split(MOTIF_MD_MARKER)[0].rstrip() + "\n"
    target.write_text(existing.rstrip() + "\n\n" + md.strip() + "\n", encoding="utf-8")
    return target


def run_and_write(attribution_table: pd.DataFrame, batch_dir: str | Path,
                  tables_dir: str | Path, summary_dir: str | Path,
                  figures_dir: str | Path, data_root: Optional[str | Path] = None,
                  config: Optional[AnalysisConfig] = None,
                  discovery: bool = True, enrichment: bool = False) -> Dict[str, object]:
    """编排 + 落盘 (tables / figures / markdown), 返回结果字典。"""
    cfg = (config or AnalysisConfig()).motif
    result = run_motif_discovery(attribution_table, batch_dir, data_root=data_root,
                                 config=config, discovery=discovery, enrichment=enrichment)
    paths = write_motif_tables(result, tables_dir) if result.get("motifs") else {}
    figs = render_motif_figures(result, figures_dir) if result.get("motifs") else []
    md_path = append_motif_section(summary_dir, build_motif_md(result, cfg, str(batch_dir)))
    paths["md"] = str(md_path)
    result["table_paths"] = paths
    result["figure_paths"] = figs
    return result
