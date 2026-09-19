#!/usr/bin/env python3
"""外部模型验证的图件生成（Level 1–4）。

图件统一输出到 ``results/figures/external_validation/``（项目新采用的结果图目录）。
所有图都标注这是 model-based counterfactual，避免被误读为实验效应。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt        # noqa: E402
import numpy as np                     # noqa: E402
import pandas as pd                    # noqa: E402

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from analysis.external_validation.validate_position18 import FIG_DIR, TABLE_DIR  # noqa: E402

DISCLAIMER = ("External model validation — model-based counterfactual "
              "(not an experimental effect)")


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_paired(standard: pd.DataFrame, out: Path, pos: int = 18) -> Path:
    """Level 1：WT vs C18A 配对图。"""
    d = standard.dropna(subset=["WT_prediction", "mutant_prediction"])
    fig, ax = plt.subplots(figsize=(6.2, 5.0))
    cmap = plt.get_cmap("tab10")
    for i, (_, r) in enumerate(d.iterrows()):
        color = cmap(i % 10)
        ax.plot([0, 1], [r["WT_prediction"], r["mutant_prediction"]],
                marker="o", color=color, lw=1.4, ms=5)
        ax.annotate(f"{r['sample_id']} ({r['cell_line']})",
                    (1, r["mutant_prediction"]), xytext=(6, 0),
                    textcoords="offset points", fontsize=7, color=color, va="center")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["WT", f"C{pos}A"])
    ax.set_ylabel("CRISPRon predicted indel frequency (%)")
    ax.set_title(f"CRISPRon: WT vs C{pos}A (n={len(d)})\n{DISCLAIMER}", fontsize=9)
    ax.grid(alpha=0.25)
    return _save(fig, out)


def fig_delta_distribution(standard: pd.DataFrame, out: Path, pos: int = 18) -> Path:
    """Level 2：Δ 分布 + 方向一致性。"""
    d = standard.dropna(subset=["delta"])
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    colors = ["#c0392b" if v < 0 else "#2980b9" for v in d["delta"]]
    ax.bar(d["sample_id"], d["delta"], color=colors)
    ax.axhline(0, color="black", lw=0.8)
    frac = float((d["delta"] < 0).mean()) if len(d) else float("nan")
    ax.set_ylabel(f"Δ = f(C{pos}A) − f(WT)   [CRISPRon %]")
    ax.set_title(f"Δ distribution — {int((d['delta']<0).sum())}/{len(d)} negative "
                 f"(consistency {frac:.2f})\n{DISCLAIMER}", fontsize=9)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(alpha=0.25, axis="y")
    return _save(fig, out)


def fig_cross_model(cmp_df: pd.DataFrame, out: Path, pos: int = 18) -> Path:
    """Level 3：我们的 Δ vs CRISPRon 的 Δ（只比方向/秩，不比原始尺度）。"""
    v = cmp_df.dropna(subset=["delta", "delta_ours_mean"])
    fig, ax = plt.subplots(figsize=(5.6, 5.0))
    agree = v["agree_direction"]
    ax.scatter(v.loc[agree, "delta"], v.loc[agree, "delta_ours_mean"],
               c="#27ae60", s=55, label="direction agrees", zorder=3)
    ax.scatter(v.loc[~agree, "delta"], v.loc[~agree, "delta_ours_mean"],
               c="#c0392b", s=70, marker="X", label="disagrees", zorder=3)
    for _, r in v.iterrows():
        ax.annotate(r["sample_id"], (r["delta"], r["delta_ours_mean"]),
                    xytext=(5, 3), textcoords="offset points", fontsize=7)
    ax.axhline(0, color="grey", lw=0.7); ax.axvline(0, color="grey", lw=0.7)
    ax.set_xlabel(f"Δ CRISPRon (C{pos}A − WT)  [%]")
    ax.set_ylabel(f"Δ project model (C{pos}A − WT)  [efficiency units]")
    ax.set_title("Cross-model direction agreement\n"
                 "(scales differ — compare signs/ranks only)", fontsize=9)
    ax.legend(fontsize=8); ax.grid(alpha=0.25)
    return _save(fig, out)


def fig_mutagenesis_heatmap(eff: pd.DataFrame, out: Path, pos: int = 18) -> Path:
    """Level 4：position × substitution 效应热图（多序列平均）。"""
    ok = eff[eff["recognized"] & eff["delta"].notna()]
    if ok.empty:
        raise ValueError("没有可用的突变效应数据")
    piv = ok.pivot_table(index="substitution", columns="position_1b",
                         values="delta", aggfunc="mean")
    order = ["A>C", "A>G", "A>T", "C>A", "C>G", "C>T",
             "G>A", "G>C", "G>T", "T>A", "T>C", "T>G"]
    piv = piv.reindex([s for s in order if s in piv.index])
    fig, ax = plt.subplots(figsize=(11, 3.8))
    vmax = float(np.nanmax(np.abs(piv.values)))
    im = ax.imshow(piv.values, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(len(piv.columns)))
    ax.set_xticklabels([int(c) for c in piv.columns], fontsize=7)
    ax.set_yticks(range(len(piv.index))); ax.set_yticklabels(piv.index, fontsize=7)
    ax.set_xlabel("position in the 23-nt target+PAM (1-based)")
    ax.set_ylabel("substitution")
    if pos in list(piv.columns):
        xi = list(piv.columns).index(pos)
        ax.axvline(xi, color="black", lw=1.6, ls="--")
        # 标注放在热图内部底端，避免与标题重叠
        ax.annotate(f"pos {pos}", xy=(xi, len(piv.index) - 0.35),
                    ha="center", va="top", fontsize=8, color="black",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="black", lw=0.5))
    ax.set_title(f"CRISPRon systematic in-silico mutagenesis — mean Δ across "
                 f"{ok['sample_id'].nunique()} WT sequences\n{DISCLAIMER}", fontsize=9)
    fig.colorbar(im, ax=ax, label="mean Δ (CRISPRon %)", pad=0.01)
    return _save(fig, out)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成外部模型验证的图件")
    ap.add_argument("--wt-run", default="crispron_pos18_v1")
    ap.add_argument("--mut-run", default="crispron_mutagenesis_v1")
    args = ap.parse_args()

    made = []
    std_p = TABLE_DIR / f"{args.wt_run}_wt_c18a_predictions.csv"
    cmp_p = TABLE_DIR / f"{args.wt_run}_cross_model.csv"
    eff_p = TABLE_DIR / f"{args.mut_run}_effects.csv"

    if std_p.exists():
        std = pd.read_csv(std_p)
        made.append(fig_paired(std, FIG_DIR / "fig1_wt_vs_c18a_paired.png"))
        made.append(fig_delta_distribution(std, FIG_DIR / "fig2_delta_distribution.png"))
    if cmp_p.exists():
        made.append(fig_cross_model(pd.read_csv(cmp_p), FIG_DIR / "fig3_ours_vs_crispron.png"))
    if eff_p.exists():
        made.append(fig_mutagenesis_heatmap(pd.read_csv(eff_p),
                                           FIG_DIR / "fig4_position_substitution_heatmap.png"))
    for p in made:
        print(f"[✓] {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
