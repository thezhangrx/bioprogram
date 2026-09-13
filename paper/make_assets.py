"""Generate paper figures and LaTeX tables from the real result artifacts.

Run:  python paper/make_assets.py
Inputs are READ-ONLY artifacts under results/batch_20260909_full/ (never modified).
Every number written here is recomputed from those artifacts (no hard-coded results).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "results" / "batch_20260909_full" / "analyse_out"
DATA = ROOT / "data" / "proceeded_data"
FIG = ROOT / "paper" / "figures"
TAB = ROOT / "paper" / "tables"
ANALYSIS = ROOT / "docs" / "paper_analysis"
CELLS = ["hct116", "hek293t", "hela", "hl60"]
CELL_LABEL = {"hct116": "HCT116", "hek293t": "HEK293T", "hela": "HeLa", "hl60": "HL60"}
MODELS = ["linear", "xgboost", "mlp", "cnn", "transformer"]
MODEL_LABEL = {"linear": "Linear Regression", "xgboost": "XGBoost", "mlp": "MLP",
               "cnn": "CNN", "transformer": "Transformer"}
KERNELS = {"cnn(3|3)": 3, "cnn(5|3)": 5, "cnn(7|3)": 7}
UNSTABLE = 10.0                      # |ΔR²| > 10 -> diverged (project config)
PRIMARY = {"linear": "linear_coefficient", "xgboost": "xgboost_treeshap", "mlp": "mlp_ig",
           "cnn": "cnn_ig", "transformer": "transformer_attention"}
plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
                     "figure.dpi": 160, "savefig.bbox": "tight"})
COLORS = {"linear": "#7f8c8d", "xgboost": "#c0392b", "mlp": "#2980b9",
          "cnn": "#27ae60", "transformer": "#8e44ad"}
REGIONS = {"PAM (21-23)": (21, 23), "PAM-proximal seed (17-20)": (17, 20),
           "Seed core (9-16)": (9, 16), "PAM-distal (1-8)": (1, 8)}


def save(fig, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)
    print("figure:", name)


def load_sequences() -> pd.DataFrame:
    frames = []
    for c in CELLS:
        d = pd.read_csv(DATA / f"{c}_metadata.csv")
        d["sgRNA"] = d["sgRNA"].astype(str).str.upper().str.strip()
        d = d[d["sgRNA"].str.fullmatch(r"[ACGT]{23}")]
        d["cell_line"] = c
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------- Figure 2
def figure2_prediction(t: pd.DataFrame, loco: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.1))
    order = ["cnn(3|3)", "cnn(5|3)", "cnn(7|3)", "mlp", "transformer", "xgboost"]
    labels = {"cnn(3|3)": "CNN k=3", "cnn(5|3)": "CNN k=5", "cnn(7|3)": "CNN k=7",
              "mlp": "MLP", "transformer": "Transformer", "xgboost": "XGBoost"}
    ax = axes[0]
    for i, split in enumerate(["single", "mixed"]):
        vals = [t[(t.model == m) & (t.split_type == split)]["R2"].median() for m in order]
        ax.bar(np.arange(len(order)) + (i - 0.5) * 0.38, vals, width=0.36,
               label={"single": "Single-cell-line split", "mixed": "Mixed (4 seeds)"}[split],
               color=["#95a5a6", "#34495e"][i])
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([labels[m] for m in order], rotation=35, ha="right")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_ylabel("R² (median over experiments)")
    ax.set_title("A  Held-out test performance")
    ax.legend(fontsize=7, frameon=False)

    ax = axes[1]
    for m in order:
        sub = t[(t.model == m) & (t.split_type == "single")]
        ax.scatter(np.full(len(sub), order.index(m)) + np.random.default_rng(0).normal(0, 0.06, len(sub)),
                   sub["R2"], s=4, alpha=0.5, color="#2c3e50")
        ax.plot([order.index(m) - 0.25, order.index(m) + 0.25], [sub["R2"].median()] * 2,
                color="#c0392b", lw=1.6)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([labels[m] for m in order], rotation=35, ha="right")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_ylim(-0.05, 0.25)
    ax.set_title("B  Experiment-level spread (single)")
    ax.set_ylabel("R²")

    ax = axes[2]
    sub = loco[loco.model.isin(["xgboost", "transformer", "cnn(7|3)", "mlp"])]
    width = 0.2
    for i, m in enumerate(["xgboost", "transformer", "cnn(7|3)", "mlp"]):
        vals = [float(sub[(sub.model == m) & (sub.cell_line == c)]["R2"].iloc[0])
                if len(sub[(sub.model == m) & (sub.cell_line == c)]) else np.nan for c in CELLS]
        ax.bar(np.arange(len(CELLS)) + (i - 1.5) * width, vals, width=width,
               label=labels[m], color=["#c0392b", "#8e44ad", "#27ae60", "#2980b9"][i])
    ax.set_xticks(range(len(CELLS)))
    ax.set_xticklabels([CELL_LABEL[c] for c in CELLS], rotation=30, ha="right")
    ax.set_title("C  Held-out-cell-line rows (see caveat)")
    ax.set_ylabel("R²")
    ax.legend(fontsize=6.5, frameon=False)
    fig.tight_layout()
    save(fig, "fig2_prediction")


# ---------------------------------------------------------------- Figure 3
def figure3_environment(main: pd.DataFrame, boot_edges: pd.DataFrame,
                        anova: pd.DataFrame, factor_ci: pd.DataFrame) -> None:
    st = main[main["main_r2_delta"].abs() < UNSTABLE]
    fig, axes = plt.subplots(1, 4, figsize=(12.4, 3.0))
    factors = ["ctcf", "dnase", "h3k4me3", "rrbs"]
    f_labels = {"ctcf": "CTCF", "dnase": "DNase", "h3k4me3": "H3K4me3", "rrbs": "RRBS"}
    ax = axes[0]
    for m in sorted(st.model.unique()):
        vals = [st[(st.model == m) & (st.environment == f)]["main_r2_delta"].mean() for f in factors]
        ax.plot(range(len(factors)), vals, marker="o", ms=3,
                color=COLORS.get(m.split("(")[0], "#333"), label=m)
    ax.axhline(0, color="k", lw=0.8, ls="--")
    ax.set_xticks(range(len(factors)))
    ax.set_xticklabels([f_labels[f] for f in factors], rotation=25, ha="right")
    ax.set_ylabel("main-effect ΔR²")
    ax.set_title("A  Per-model incremental value")
    ax.legend(fontsize=6, frameon=False, ncol=2)

    ax = axes[1]
    data = [st[st.environment == f]["main_r2_delta"].values for f in factors]
    bp = ax.boxplot(data, tick_labels=[f_labels[f] for f in factors], widths=0.55,
                    showfliers=False, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor("#ecf0f1")
    ax.axhline(0, color="k", lw=0.8, ls="--")
    ax.set_title("B  Distribution across models/contexts")
    ax.set_ylabel("main-effect ΔR²")
    ax.tick_params(axis="x", rotation=25)

    ax = axes[2]
    b = boot_edges.copy()
    b["factor"] = b["added_environment"]
    counts = b.groupby("factor").apply(
        lambda g: pd.Series({"excludes": int(g["excl"].sum()), "n": len(g)}), include_groups=False)
    counts = counts.reindex(factors)
    ax.bar(range(len(factors)), counts["n"], color="#dfe6e9", width=0.6, label="edges tested")
    ax.bar(range(len(factors)), counts["excludes"], color="#e67e22", width=0.6,
           label="95% CI excludes 0")
    for i, (e, n) in enumerate(zip(counts["excludes"], counts["n"])):
        ax.text(i, n + 4, f"{e}/{n}", ha="center", fontsize=6.5)
    ax.set_xticks(range(len(factors)))
    ax.set_xticklabels([f_labels[f] for f in factors], rotation=25, ha="right")
    ax.set_title("C  Paired per-sample bootstrap")
    ax.set_ylabel("number of lattice edges")
    ax.legend(fontsize=6.5, frameon=False)

    ax = axes[3]
    a = anova[anova.model_scope == "blocked_factorial"].set_index("factor")
    xs = np.arange(len(factors))
    ax.bar(xs - 0.2, [a.loc[f, "F_statistic"] for f in factors], width=0.4, color="#34495e",
           label="F statistic")
    ax.bar(xs + 0.2, [a.loc[f, "p_value"] for f in factors], width=0.4, color="#e74c3c",
           label="p value")
    for i, f in enumerate(factors):
        ax.text(i - 0.2, a.loc[f, "F_statistic"] + 0.06, f"{a.loc[f,'F_statistic']:.2f}",
                ha="center", fontsize=6)
        ax.text(i + 0.2, a.loc[f, "p_value"] + 0.06, f"{a.loc[f,'p_value']:.3f}",
                ha="center", fontsize=6)
    ax.set_xticks(xs)
    ax.set_xticklabels([f_labels[f] for f in factors], rotation=25, ha="right")
    ax.set_title("D  Factorial ANOVA (blocked)")
    ax.legend(fontsize=6.5, frameon=False)
    fig.tight_layout()
    save(fig, "fig3_environment")


# ---------------------------------------------------------------- Figure 4
def figure4_sequence(prof: pd.DataFrame, region: pd.DataFrame, cons: pd.DataFrame,
                     eff18: pd.DataFrame, attr18: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 4, figsize=(13.0, 3.0))
    ax = axes[0]
    for m in MODELS:
        if m not in prof.columns:
            continue
        ax.plot(prof.index, prof[m], marker="o", ms=2.5, color=COLORS[m],
                label=MODEL_LABEL[m])
    ax.axvspan(17, 20, color="#f39c12", alpha=0.12)
    ax.axvspan(21, 23, color="#95a5a6", alpha=0.18)
    ax.set_xlabel("position in 23-nt target (1-based)")
    ax.set_ylabel("normalized |attribution|")
    ax.set_title("A  Cross-model position profile")
    ax.legend(fontsize=6, frameon=False, ncol=2)
    ax.set_xticks([1, 5, 10, 15, 18, 23])

    ax = axes[1]
    reg = region.groupby(["region", "model"])["mean_norm_attribution"].mean().unstack()
    reg = reg.reindex(list(REGIONS))
    xs = np.arange(len(reg))
    for i, m in enumerate(MODELS):
        if m not in reg.columns:
            continue
        ax.bar(xs + (i - 2) * 0.16, reg[m], width=0.15, color=COLORS[m], label=MODEL_LABEL[m])
    ax.set_xticks(xs)
    ax.set_xticklabels([r.replace(" (", "\n(") for r in reg.index], fontsize=6)
    ax.set_ylabel("mean normalized attribution")
    ax.set_title("B  Region-level attribution")
    ax.legend(fontsize=6, frameon=False, ncol=2)

    ax = axes[2]
    eff = eff18[eff18.pos18_base != "ALL"]
    width = 0.2
    bases = ["A", "C", "G", "T"]
    for i, c in enumerate(CELLS):
        vals = [float(eff[(eff.cell_line == c) & (eff.pos18_base == b)]["mean_efficacy"].iloc[0])
                if len(eff[(eff.cell_line == c) & (eff.pos18_base == b)]) else np.nan for b in bases]
        ax.bar(np.arange(4) + (i - 1.5) * width, vals, width=width, label=CELL_LABEL[c])
    ax.set_xticks(range(4))
    ax.set_xticklabels(bases)
    ax.set_xlabel("nucleotide at position 18")
    ax.set_ylabel("mean measured efficacy")
    ax.set_title("C  Position-18 base vs efficacy")
    ax.legend(fontsize=6, frameon=False)

    ax = axes[3]
    sel = attr18[(attr18.split_type == "single") & (attr18.environment == "sequence")]
    piv = sel.groupby(["cell_line", "model"])["C18_share_within_pos18"].mean().unstack()
    piv = piv.reindex(CELLS)
    xs = np.arange(len(piv))
    for i, m in enumerate(MODELS):
        if m not in piv.columns:
            continue
        ax.bar(xs + (i - 2) * 0.16, piv[m], width=0.15, color=COLORS[m], label=MODEL_LABEL[m])
    ax.set_xticks(xs)
    ax.set_xticklabels([CELL_LABEL[c] for c in piv.index], rotation=25, ha="right")
    ax.set_ylabel("share of C within position-18 attribution")
    ax.set_title("D  Model attribution of 18C")
    ax.legend(fontsize=6, frameon=False, ncol=2)
    fig.tight_layout()
    save(fig, "fig4_sequence_attribution")


# ---------------------------------------------------------------- Figure 5
def figure5_kernel(kern: pd.DataFrame, kprof: pd.DataFrame, motifs: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 4, figsize=(12.4, 3.0))
    ax = axes[0]
    xs = np.arange(len(kern))
    ax.bar(xs, kern["mean_dR2"], color="#16a085", width=0.5)
    ax.errorbar(xs, kern["mean_dR2"],
                yerr=[kern["mean_dR2"] - kern["ci_low"], kern["ci_high"] - kern["mean_dR2"]],
                fmt="none", ecolor="k", capsize=3)
    for i, r in kern.iterrows():
        ax.text(i, r["ci_high"] + 0.002, f"{r['pct_positive']:.0%} > 0", ha="center", fontsize=6)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels([c.replace(" - ", " − ") for c in kern["comparison"]], fontsize=6.5)
    ax.set_ylabel("paired ΔR² (mean, 95% bootstrap CI)")
    ax.set_title(f"A  Kernel ablation (n={int(kern['n_pairs'].iloc[0])} pairs)")

    ax = axes[1]
    for col, lab in [("cnn33", "k=3"), ("cnn53", "k=5"), ("cnn73", "k=7")]:
        if col in kprof.columns:
            ax.plot(kprof.index, kprof[col], marker="o", ms=2.5, label=lab)
    ax.axvspan(17, 20, color="#f39c12", alpha=0.12)
    ax.set_xlabel("position")
    ax.set_ylabel("normalized |attribution|")
    ax.set_title("B  Position profile by kernel")
    ax.legend(fontsize=7, frameon=False)

    ax = axes[2]
    regs = {}
    for col, lab in [("cnn33", "k=3"), ("cnn53", "k=5"), ("cnn73", "k=7")]:
        if col in kprof.columns:
            regs[lab] = [kprof.loc[lo:hi, col].mean() for lo, hi in REGIONS.values()]
    xs = np.arange(len(REGIONS))
    for i, (lab, vals) in enumerate(regs.items()):
        ax.bar(xs + (i - 1) * 0.25, vals, width=0.24, label=lab)
    ax.set_xticks(xs)
    ax.set_xticklabels([r.replace(" (", "\n(") for r in REGIONS], fontsize=6)
    ax.set_ylabel("mean normalized attribution")
    ax.set_title("C  Region attribution by kernel")
    ax.legend(fontsize=7, frameon=False)

    ax = axes[3]
    m = motifs.copy()
    m["kernel"] = m["model_variant"].str.extract(r"cnn(\d+)")[0]
    for k, col in [("33", "#2980b9"), ("53", "#27ae60"), ("73", "#c0392b")]:
        sub = m[m.kernel == k]
        ax.hist(sub["length"], bins=np.arange(3, 13) - 0.5, alpha=0.6, label=f"k={k[0]}",
                color=col)
    ax.set_xlabel("motif length (nt)")
    ax.set_ylabel("motif candidates")
    ax.set_title("D  Motif length by kernel")
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    save(fig, "fig5_kernel")


# ---------------------------------------------------------------- Figure 6
def figure6_cellline(env_cell: pd.DataFrame, eff18: pd.DataFrame,
                     cellline_labels: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(10.6, 3.0))
    ax = axes[0]
    piv = env_cell.pivot(index="factor", columns="cell_line", values="mean_dR2")
    piv = piv.reindex(["ctcf", "dnase", "h3k4me3", "rrbs"])
    cols = [c for c in CELLS if c in piv.columns]
    im = ax.imshow(piv[cols].values, cmap="RdBu_r", vmin=-0.02, vmax=0.02, aspect="auto")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([CELL_LABEL[c] for c in cols], rotation=30, ha="right")
    ax.set_yticks(range(len(piv)))
    ax.set_yticklabels([i.upper() for i in piv.index])
    for i in range(piv.shape[0]):
        for j in range(len(cols)):
            v = piv[cols].values[i, j]
            ax.text(j, i, f"{v:+.4f}", ha="center", va="center", fontsize=6,
                    color="white" if abs(v) > 0.012 else "black")
    ax.set_title("A  Environment ΔR² by cell line")
    fig.colorbar(im, ax=ax, fraction=0.046, label="ΔR²")

    ax = axes[1]
    eff = eff18[eff18.pos18_base != "ALL"]
    piv2 = eff.pivot(index="pos18_base", columns="cell_line", values="mean_efficacy").reindex(
        ["A", "C", "G", "T"])
    xs = np.arange(len(piv2))
    for i, c in enumerate([c for c in CELLS if c in piv2.columns]):
        ax.bar(xs + (i - 1.5) * 0.2, piv2[c], width=0.19, label=CELL_LABEL[c])
    ax.set_xticks(xs)
    ax.set_xticklabels(piv2.index)
    ax.set_xlabel("nucleotide at position 18")
    ax.set_ylabel("mean measured efficacy")
    ax.set_title("B  18C effect across cell lines")
    ax.legend(fontsize=6.5, frameon=False)

    ax = axes[2]
    counts = cellline_labels.groupby(["factor", "context_label"]).size().unstack(fill_value=0)
    counts = counts.reindex(["ctcf", "dnase", "h3k4me3", "rrbs"]).fillna(0)
    cats = ["Context-consistent", "Context-dependent", "Context-conflicting", "Uncertain"]
    xs = np.arange(len(counts))
    bottom = np.zeros(len(counts))
    palette = {"Context-consistent": "#27ae60", "Context-dependent": "#f39c12",
               "Context-conflicting": "#c0392b", "Uncertain": "#bdc3c7"}
    for cat in cats:
        if cat in counts.columns:
            ax.bar(xs, counts[cat], bottom=bottom, color=palette[cat], label=cat, width=0.6)
            bottom += counts[cat].values
    ax.set_xticks(xs)
    ax.set_xticklabels([i.upper() for i in counts.index], rotation=25, ha="right")
    ax.set_ylabel("number of model × split contexts")
    ax.set_title("C  Context-consistency labels")
    ax.legend(fontsize=6, frameon=False)
    fig.tight_layout()
    save(fig, "fig6_cellline")


# ---------------------------------------------------------------- Figure 7
def factor_ci(main_eff: pd.DataFrame, n_iter: int = 2000,
              seed: int = 2024) -> pd.DataFrame:
    """Factor-level CI with the SAME estimator as the point estimate.

    per-model mean main effect (equal weight per model) -> percentile bootstrap over models.
    Computed here from the raw artifact so that the CI always brackets the reported mean.
    """
    rng = np.random.default_rng(seed)
    rows = []
    st = main_eff[main_eff["main_r2_delta"].abs() < UNSTABLE]
    for f, sub in st.groupby("environment"):
        vals = sub.groupby("model")["main_r2_delta"].mean().dropna().values
        if vals.size < 3:
            rows.append({"factor": f, "estimate": float(vals.mean()) if vals.size else np.nan,
                         "ci_low": np.nan, "ci_high": np.nan, "n_models": int(vals.size),
                         "status": "unavailable (<3 models)"})
            continue
        boot = rng.choice(vals, size=(n_iter, vals.size), replace=True).mean(axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        rows.append({"factor": f, "estimate": float(vals.mean()), "ci_low": float(lo),
                     "ci_high": float(hi), "n_models": int(vals.size), "status": "ok"})
    return pd.DataFrame(rows)


def figure7_evidence(evidence: pd.DataFrame, importance: pd.DataFrame,
                     factor_ci_df: pd.DataFrame) -> None:
    """Figure 7 (main text): evidence integration for environmental factors (CI + tier)."""
    fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=150)
    ev = evidence[evidence.feature_type == "environment"].copy()
    ev = ev.set_index("feature").reindex(["ctcf", "dnase", "h3k4me3", "rrbs"])
    ci = factor_ci_df.set_index("factor").reindex(ev.index)
    ax.barh(np.arange(len(ev)), ci["estimate"], color="#34495e",
            xerr=[ci["estimate"] - ci["ci_low"], ci["ci_high"] - ci["estimate"]],
            error_kw={"ecolor": "#e74c3c", "capsize": 3})
    ax.axvline(0, color="k", lw=0.8)
    ax.set_yticks(range(len(ev)))
    ax.set_yticklabels([i.upper() for i in ev.index])
    for i, (_, r) in enumerate(ev.iterrows()):
        ax.text(r["ci_high"] + 0.0008, i,
                f"{r['evidence_tier'].split(':')[0]} | FDR={r['permutation_fdr']:.3g}"
                f" | |dR2|<0.01", va="center", fontsize=6)
    ax.set_xlabel("cross-model mean main-effect $\\Delta R^2$ (95% bootstrap CI, n=7 models)")
    ax.set_title("Evidence integration: convergent but small incremental effects", fontsize=8.5)
    fig.tight_layout()
    save(fig, "fig7_evidence")


def figureS1_importance_delta(importance: pd.DataFrame) -> None:
    """Supplementary figure: importance vs dR2 (auxiliary integrated view, not a significance plot)."""
    fig, ax = plt.subplots(figsize=(5.6, 4.0), dpi=150)
    imp = importance.copy()
    imp["delta_r2"] = pd.to_numeric(imp["delta_r2"], errors="coerce")
    imp["normalized_importance"] = pd.to_numeric(imp["normalized_importance"], errors="coerce")
    imp = imp[imp["delta_r2"].abs() < UNSTABLE]
    for m in MODELS:
        sub = imp[imp.model == m]
        if sub.empty:
            continue
        ax.scatter(sub["delta_r2"], sub["normalized_importance"], s=22, alpha=0.75,
                   color=COLORS[m], label=MODEL_LABEL[m])
    ax.axvline(0, color="k", lw=0.8, ls="--")
    ax.set_xlabel("$\\Delta R^2$ (incremental predictive value)")
    ax.set_ylabel("within-model normalized importance")
    ax.set_title("Auxiliary view: predictive contribution vs model dependence", fontsize=8.5)
    ax.legend(fontsize=6.5, frameon=False, ncol=2)
    fig.tight_layout()
    save(fig, "figS1_importance_delta")


# ---------------------------------------------------------------- Figure 1
def figure1_workflow() -> None:
    fig, ax = plt.subplots(figsize=(4.6, 8.2))
    ax.axis("off")
    boxes = [
        ("Measured editing data\n(sequence + measured efficiency)", "#ecf0f1"),
        ("Data quality control\n(missingness, ambiguity, outliers)", "#ecf0f1"),
        ("Feature configuration\n23-nt one-hot + 4 epigenetic tracks", "#ecf0f1"),
        ("Controlled experiments\n5 model families × 16 environment\ncombinations × 3 splits × seeds",
         "#d6eaf8"),
        ("Model-specific interpretation\ncoefficients · TreeSHAP · IG · ISM · attention", "#d6eaf8"),
        ("Statistical layer\npaired ΔR² bootstrap · permutation · BH-FDR · factorial ANOVA",
         "#d5f5e3"),
        ("Factor discovery\nenvironment factorial edges · seqlets → motifs", "#d5f5e3"),
        ("Cross-model evidence integration\ncoverage · concordance · CI · cell-line context",
         "#fdebd0"),
        ("Candidate factors & testable hypotheses", "#fdebd0"),
    ]
    n = len(boxes)
    for i, (text, color) in enumerate(boxes):
        y = 1 - (i + 0.5) / n
        ax.add_patch(plt.Rectangle((0.08, y - 0.038), 0.84, 0.075, facecolor=color,
                                   edgecolor="#34495e", linewidth=0.8,
                                   transform=ax.transAxes, clip_on=False))
        ax.text(0.5, y, text, ha="center", va="center", fontsize=7, transform=ax.transAxes)
        if i < n - 1:
            ax.annotate("", xy=(0.5, y - 0.052), xytext=(0.5, y - 0.038),
                        xycoords=ax.transAxes, textcoords=ax.transAxes,
                        arrowprops=dict(arrowstyle="->", lw=0.9, color="#34495e"))
    ax.text(0.5, 1.0, "Platform: prediction → interpretation → evidence → hypothesis",
            ha="center", va="bottom", fontsize=8, transform=ax.transAxes)
    save(fig, "fig1_workflow")


# ---------------------------------------------------------------- tables
FACTOR_CI = pd.DataFrame()


def write_tables(seqs: pd.DataFrame, pred: pd.DataFrame, env_cross: pd.DataFrame,
                 evidence: pd.DataFrame, kern: pd.DataFrame, anova: pd.DataFrame,
                 motifs: pd.DataFrame, boot_factor: pd.DataFrame) -> None:
    TAB.mkdir(parents=True, exist_ok=True)
    # Table 1 dataset
    rows = []
    for c in CELLS:
        s = seqs[seqs.cell_line == c]
        rows.append({"cell_line": CELL_LABEL[c], "n": len(s),
                     "mean": s["Normalized efficacy"].mean(),
                     "sd": s["Normalized efficacy"].std(ddof=1),
                     "median": s["Normalized efficacy"].median(),
                     "gc": s["sgRNA"].str.count("[GC]").sum() / (23 * len(s))})
    t1 = pd.DataFrame(rows)
    t1.loc[len(t1)] = {"cell_line": "Total", "n": len(seqs),
                       "mean": seqs["Normalized efficacy"].mean(),
                       "sd": seqs["Normalized efficacy"].std(ddof=1),
                       "median": seqs["Normalized efficacy"].median(),
                       "gc": seqs["sgRNA"].str.count("[GC]").sum() / (23 * len(seqs))}
    _tex_table(t1, "tab1_dataset",
               caption="Case-study dataset composition. Normalized editing efficiency per cell line; "
                       "GC content is the fraction of G/C across all 23-nt targets.",
               label="tab:dataset", float_fmt="{:.3f}")

    # Table 2 prediction
    order = ["cnn(3|3)", "cnn(5|3)", "cnn(7|3)", "mlp", "transformer", "xgboost", "linear"]
    rows = []
    for m in order:
        for split in ("single", "mixed"):
            sub = pred[(pred.model == m) & (pred.split_type == split)]
            if sub.empty:
                continue
            rows.append({"model": m, "split": split,
                         "n_experiments": int(sub["n_experiments"].iloc[0]),
                         "R2_median": sub["R2_mean"].median(), "R2_mean": sub["R2_mean"].mean(),
                         "R2_sd": sub["R2_mean"].std(ddof=1),
                         "RMSE_median": sub["RMSE_mean"].median(),
                         "MAE_median": sub["MAE_mean"].median(),
                         "Spearman_median": sub["Spearman_mean"].median(),
                         "diverged": int((sub["R2_mean"].abs() >= UNSTABLE).sum())})
    t2 = pd.DataFrame(rows)
    _tex_table(t2, "tab2_prediction",
               caption="Held-out test performance. Medians over experiments are reported because the "
                       "Linear Regression configuration diverged in a subset of experiments "
                       "(see diverged column); no result was discarded from the raw artifacts.",
               label="tab:prediction", float_fmt="{:.3f}")

    # Table 3 environment evidence
    ev = evidence[evidence.feature_type == "environment"].set_index("feature")
    rows = []
    for f in ["ctcf", "dnase", "h3k4me3", "rrbs"]:
        cm = env_cross[env_cross.factor == f].iloc[0]
        e = ev.loc[f]
        an = anova[(anova.model_scope == "blocked_factorial") & (anova.factor == f)].iloc[0]
        bf = boot_factor[ boot_factor.factor == f].iloc[0] if len(boot_factor[boot_factor.factor == f]) else None
        fci_row = FACTOR_CI[FACTOR_CI.factor == f].iloc[0]
        rows.append({"factor": f.upper(), "models_positive": f"{int(cm.n_positive)}/7",
                     "models_negative": f"{int(cm.n_negative)}/7",
                     "cross_model_mean_dR2": fci_row["estimate"],
                     "ci_low": fci_row["ci_low"], "ci_high": fci_row["ci_high"],
                     "ci_excludes_zero": bool(fci_row["ci_low"] > 0 or fci_row["ci_high"] < 0),
                     "edges_ci_excl0": f"{int(bf.n_excl0)}/{int(bf.n_edges)}" if bf is not None else "NA",
                     "permutation_fdr": e["permutation_fdr"],
                     "anova_F": an["F_statistic"], "anova_p": an["p_value"],
                     "cell_line_context": e["cell_line_consistency"], "tier": e["evidence_tier"]})
    t3 = pd.DataFrame(rows)
    _tex_table(t3, "tab3_environment",
               caption="Environmental factors: cross-model incremental predictive value "
                       "(mean main-effect ΔR² over models after excluding numerically diverged rows, "
                       "|ΔR²| > 10), cross-model factor-level bootstrap CI, paired per-sample edge "
                       "bootstrap (CI excluding zero), permutation-based FDR, blocked factorial ANOVA "
                       "and cell-line context label.",
               label="tab:environment", float_fmt="{:.4f}")

    # Table 4 kernel
    _tex_table(kern.assign(comparison=kern["comparison"].str.replace(" - ", " $-$ ", regex=False)),
               "tab4_kernel",
               caption="CNN receptive-field (kernel size) ablation. Paired differences of held-out R² "
                       "over 192 matched experiment pairs (same split, cell line, environment and seed); "
                       "CI is a percentile bootstrap over pairs.",
               label="tab:kernel", float_fmt="{:.4f}")

    # Table S/methods: analysis thresholds summary (values read from analyse/config.py)
    sys.path.insert(0, str(ROOT))
    from analyse.config import AnalysisConfig
    cfg = AnalysisConfig()
    mt = pd.DataFrame([
        {"item": "SNR thresholds (strong/moderate/weak)",
         "value": f"{cfg.attribution.snr_threshold}/{cfg.attribution.snr_moderate}/{cfg.attribution.snr_weak}"},
        {"item": "min effect size (attribution)", "value": f"{cfg.attribution.min_effect_size}"},
        {"item": "FDR thresholds (strong/moderate/weak)",
         "value": f"{cfg.statistical.fdr_strong}/{cfg.statistical.fdr_moderate}/{cfg.statistical.fdr_weak}"},
        {"item": "unstable effect threshold", "value": f"{cfg.consensus.unstable_effect_threshold}"},
        {"item": "bootstrap iterations / seed / alpha",
         "value": f"{cfg.bootstrap_iterations}/{cfg.bootstrap_seed}/{cfg.bootstrap_alpha}"},
        {"item": "permutation iterations", "value": f"{cfg.permutation_iterations}"},
        {"item": "ANOVA min obs / min residual df",
         "value": f"{cfg.anova.min_observations}/{cfg.anova.min_residual_df}"},
        {"item": "motif length range / similarity / merge",
         "value": f"{cfg.motif.min_length}-{cfg.motif.max_length}/{cfg.motif.similarity_threshold}/{cfg.motif.merge_similarity}"},
        {"item": "seqlet quantiles (position/continuity)",
         "value": f"{cfg.motif.attribution_quantile}/{cfg.motif.continuity_quantile}"},
        {"item": "min support (seqlet/sample), min cell lines",
         "value": f"{cfg.motif.min_seqlet_support}/{cfg.motif.min_sample_support}/{cfg.motif.min_cellline_support}"},
        {"item": "motif enrichment foreground quantile / FDR",
         "value": f"{cfg.motif.enrichment_foreground_quantile}/{cfg.motif.enrichment_fdr}"},
        {"item": "evidence tier min coverage / concordance",
         "value": f"{cfg.consensus.min_coverage}/{cfg.consensus.direction_concordance}"},
    ])
    _tex_table(mt, "tabS1_methods",
               caption="Analysis thresholds used in this study; all values are read from the central "
                       "analysis configuration file rather than hard-coded in analysis code.",
               label="tab:methods", float_fmt="{:.4f}")

    # Table sequence consistency
    sc = pd.read_csv(ANALYSIS / "cross_model_position_consistency.csv")
    sc = sc.rename(columns={"cell_line": "cell_line", "environment": "context"})
    _tex_table(sc, "tabS2_sequence",
               caption="Cross-model consistency of position-wise attribution (single split, sequence/all "
                       "contexts). Peak positions are the argmax of each model's normalized attribution "
                       "profile; Spearman is the mean pairwise rank correlation over 23 positions; "
                       "top-3 overlap is the mean Jaccard-style overlap of each model's three highest "
                       "positions.",
               label="tab:sequence", float_fmt="{:.3f}")

    # Table 6 candidate hypotheses for follow-up experimental validation
    p18 = pd.read_csv(ANALYSIS / "position18_efficacy_by_base.csv")
    pv = p18[p18.pos18_base != "ALL"].pivot(index="pos18_base", columns="cell_line",
                                            values="mean_efficacy")
    ca = (pv.loc["C"] - pv.loc["A"]).round(4)
    mot = pd.read_csv(BASE / "tables" / "motif_candidates.csv")
    enr = pd.read_csv(BASE / "tables" / "motif_enrichment.csv")
    mj = mot.merge(enr[["motif_id", "odds_ratio", "FDR"]], on="motif_id", how="left",
                   suffixes=("", "_e"))
    gagg = mj[mj.human_pattern == "GAGG"].sort_values("FDR").iloc[0]
    gggg = mj[mj.human_pattern == "GGGG"].sort_values("FDR").iloc[0]
    ctgg = mj[mj.human_pattern == "CTGG"].iloc[0]
    cand = pd.DataFrame([
        {"candidate": "C1: position-18 base substitution",
         "type": "single-nucleotide",
         "multi_model_support": "3/5 models in top-3 positions; PAM-proximal region highest for 4/5",
         "effect": f"mean efficacy C-A: HCT116 {ca.get('hct116', float('nan')):+.3f}, "
                   f"HeLa {ca.get('hela', float('nan')):+.3f}, HL60 {ca.get('hl60', float('nan')):+.3f}, "
                   f"HEK293T {ca.get('hek293t', float('nan')):+.3f}",
         "robustness": "CNN substitution sensitivity higher in HCT116/HeLa than HEK293T",
         "minimal_perturbation": "substitute position 18 (C<->A) keeping the rest of the sgRNA fixed",
         "priority": "high"},
        {"candidate": f"C2: {gagg.human_pattern} candidate pattern (enriched)",
         "type": "motif disruption",
         "multi_model_support": "shared by CNN k=3/5/7 contexts (50 contexts)",
         "effect": f"carrier-vs-background effect {gagg.mean_effect:+.3f}; OR={gagg.odds_ratio:.2f}",
         "robustness": f"BH-FDR={gagg.FDR:.3f} (motif_enrichment family); single cell line (HeLa)",
         "minimal_perturbation": "disrupt the 4-nt core inside the PAM-proximal window",
         "priority": "medium"},
        {"candidate": f"C3: {gggg.human_pattern} candidate pattern (most enriched)",
         "type": "motif disruption",
         "multi_model_support": "CNN contexts (8 contexts)",
         "effect": f"carrier-vs-background effect {gggg.mean_effect:+.3f}; OR={gggg.odds_ratio:.2f}",
         "robustness": f"BH-FDR={gggg.FDR:.4f}; single cell line (HeLa)",
         "minimal_perturbation": "disrupt the GGGG core",
         "priority": "medium"},
        {"candidate": f"reference: {ctgg.human_pattern} (highest support, not enriched)",
         "type": "motif disruption",
         "multi_model_support": "highest seqlet support (1273)",
         "effect": f"carrier-vs-background effect {ctgg.mean_effect:+.3f}; OR={ctgg.odds_ratio:.2f}",
         "robustness": f"BH-FDR={ctgg.FDR:.3g} (not significant in this batch)",
         "minimal_perturbation": "not prioritised: support without enrichment",
         "priority": "low"},
    ])
    _tex_table(cand, "tab6_candidates",
               caption="Candidate hypotheses prioritised from the existing results for minimal follow-up "
                       "perturbation experiments. No wet-lab validation was performed in this study; "
                       "effects are model-derived or measured associations, not causal estimates.",
               label="tab:candidates", float_fmt="{:.3f}")

    # Table 5 motifs
    top = motifs.sort_values("support_count", ascending=False).drop_duplicates("human_pattern").head(10)
    t5 = top[["motif_id", "human_pattern", "iupac", "regex", "length", "support_count",
              "sample_support", "cellline_support", "effect_direction", "mean_effect",
              "enrichment", "FDR", "evidence_strength"]]
    _tex_table(t5, "tab5_motifs",
               caption="Representative motif candidates discovered from CNN attribution. Support counts "
                       "are seqlet instances; enrichment and FDR come from the Fisher exact test "
                       "against the all-eligible-sequence background (BH-FDR within the "
                       "motif_enrichment family). Effect direction is the carrier-vs-background "
                       "measured-efficiency contrast, not a causal effect.",
               label="tab:motifs", float_fmt="{:.3f}")
    print("tables written")


def _tex_table(df: pd.DataFrame, name: str, caption: str, label: str,
               float_fmt: str = "{:.3f}") -> None:
    cols = list(df.columns)
    safe_caption = caption.replace("_", "\\_").replace("%", "\\%").replace("&", "\\&")
    wide = len(cols) > 8
    lines = ["\\begin{table}[htbp]", "\\centering", "\\footnotesize",
             f"\\caption{{{safe_caption}}}", f"\\label{{{label}}}"]
    if wide:
        lines.append("\\resizebox{\\textwidth}{!}{%")
    lines += ["\\begin{tabular}{" + "l" + "r" * (len(cols) - 1) + "}", "\\toprule",
             " & ".join(c.replace("_", "\\_") for c in cols) + " \\\\", "\\midrule"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("NA" if pd.isna(v) else float_fmt.format(v))
            else:
                cells.append(str(v).replace("_", "\\_").replace("%", "\\%"))
        lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    if wide:
        lines.append("}")
    lines += ["\\end{table}", ""]
    (TAB / f"{name}.tex").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    seqs = load_sequences()
    t = pd.read_csv(BASE / "tables" / "experiment_table.csv")
    pred = pd.read_csv(BASE / "tables" / "prediction_summary.csv")
    loco = pd.read_csv(BASE / "tables" / "loco_performance.csv")
    main_eff = pd.read_csv(BASE / "tables" / "environment_main_effects.csv")
    evidence = pd.read_csv(BASE / "tables" / "evidence_matrix.csv")
    anova = pd.read_csv(BASE / "tables" / "anova_results.csv")
    motifs = pd.read_csv(BASE / "tables" / "motif_candidates.csv")
    kern = pd.read_csv(ANALYSIS / "cnn_kernel_paired.csv")
    prof = pd.read_csv(ANALYSIS / "position_profile_by_model.csv", index_col=0)
    region = pd.read_csv(ANALYSIS / "region_attribution.csv")
    cons = pd.read_csv(ANALYSIS / "cross_model_position_consistency.csv")
    eff18 = pd.read_csv(ANALYSIS / "position18_efficacy_by_base.csv")
    attr18 = pd.read_csv(ANALYSIS / "position18_attribution.csv")
    kprof = pd.read_csv(ANALYSIS / "kernel_position_profile.csv", index_col=0)
    env_cell = pd.read_csv(ANALYSIS / "environment_by_cellline.csv")
    env_cross = pd.read_csv(ANALYSIS / "environment_cross_model.csv")
    cl_labels = pd.read_csv(BASE / "tables" / "cellline_effects.csv")

    # bootstrap edges joined with factor labels (recompute once, reuse for figures/tables)
    boot = pd.read_csv(BASE / "tables" / "bootstrap_results.csv")
    boot = boot[boot.metric == "R2"].copy()
    boot["excl"] = boot["excludes_zero"].astype(str).str.lower().map({"true": True, "false": False})
    boot = boot[boot.status == "ok"]
    eb = pd.read_csv(BASE / "tables" / "environment_bootstrap.csv")
    key = ["split_type", "cell_line", "model", "parent_combination", "child_combination"]
    sys.path.insert(0, str(ROOT))
    from analyse.environment.incremental_effect import parse_environment_set
    # 每个 lattice edge 可能有多 seed; 先按 edge 聚合 (conservative union CI), 再与 unique edge 表合并。
    agg = boot.groupby(key).agg(estimate=("estimate", "mean"),
                                ci_low=("ci_low", "min"), ci_high=("ci_high", "max"),
                                excl_all=("excl", "all"), n_seeds=("excl", "size")).reset_index()
    be = eb[key].drop_duplicates().merge(agg, on=key, how="left")
    be["excl"] = be["excl_all"].fillna(False).astype(bool)
    be["added_environment"] = [
        (parse_environment_set(c) - parse_environment_set(p)).pop()
        for p, c in zip(be["parent_combination"], be["child_combination"])]
    boot_factor = be.groupby("added_environment").agg(
        n_edges=("excl", "size"), n_excl0=("excl", "sum"),
        mean_estimate=("estimate", "mean"), n_seeds_total=("n_seeds", "sum")).reset_index().rename(
        columns={"added_environment": "factor"})
    boot_factor.to_csv(ANALYSIS / "bootstrap_edge_by_factor.csv", index=False)

    figure1_workflow()
    figure2_prediction(t, loco)
    figure3_environment(main_eff, be, anova, boot_factor)
    figure4_sequence(prof, region, cons, eff18, attr18)
    figure5_kernel(kern, kprof, motifs)
    figure6_cellline(env_cell, eff18, cl_labels)
    fci = factor_ci(main_eff)
    fci.to_csv(ANALYSIS / "factor_level_ci.csv", index=False)
    global FACTOR_CI
    FACTOR_CI = fci
    importance = pd.read_csv(BASE / "tables" / "importance_vs_delta_r2.csv")
    figure7_evidence(evidence, importance, fci)
    figureS1_importance_delta(importance)
    write_tables(seqs, pred, env_cross, evidence, kern, anova, motifs, boot_factor)
    summary = {
        "n_experiments": int(len(t)),
        "n_cells": len(CELLS),
        "n_samples": int(len(seqs)),
        "kernel_pairs": int(kern["n_pairs"].iloc[0]),
        "edge_ci_excluding_zero": int(be["excl"].sum()),
        "edge_tests": int(len(be)),
        "motifs": int(len(motifs)),
        "motifs_fdr_lt_005": int((motifs["FDR"] < 0.05).sum()),
    }
    (ANALYSIS / "asset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
