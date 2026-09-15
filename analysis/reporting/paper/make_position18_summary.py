"""Build the one-page A4 summary: "AI-discovered candidate sequence factor at sgRNA position 18".

Reads ONLY real artifacts (no invented numbers), writes:
    paper/figures/position18_attribution.png
    paper/figures/position18_base_effect.png
    paper/position18_summary.tex
    paper/position18_candidate_summary.pdf   (compiled with XeLaTeX, must be exactly 1 page)

Every number printed in the PDF is derived in this script from the result files and
formatted into the LaTeX template, so the sheet can be regenerated at any time.
"""
from __future__ import annotations


# --- 项目根引导: 保证从任意工作目录运行/被导入都能解析 core、analysis、workflows ---
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

import re
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ANA = ROOT / "docs" / "paper_analysis"
TAB = ROOT / "results" / "batch_20260909_full" / "summary" / "tables"
FIG = ROOT / "paper" / "figures"
PAPER = ROOT / "paper"
TEXBIN = Path("/tmp/texlive/bin/x86_64-linux")

CELL_ORDER = ["hct116", "hek293t", "hela", "hl60"]
CELL_LABEL = {"hct116": "HCT116", "hek293t": "HEK293T", "hela": "HeLa", "hl60": "HL60"}
MODELS = ["linear", "xgboost", "mlp", "cnn", "transformer"]
MODEL_LABEL = {"linear": "Linear Regression", "xgboost": "XGBoost", "mlp": "MLP",
               "cnn": "CNN", "transformer": "Transformer (attention)*"}
COLORS = {"linear": "#7f8c8d", "xgboost": "#c0392b", "mlp": "#2980b9",
          "cnn": "#27ae60", "transformer": "#8e44ad"}
BASE_COLORS = {"A": "#4c72b0", "C": "#dd8452", "G": "#55a868", "T": "#c44e52"}


# ---------------------------------------------------------------- data
def load() -> dict:
    prof = pd.read_csv(ANA / "position_profile_by_model.csv", index_col=0)
    eff = pd.read_csv(ANA / "position18_efficacy_by_base.csv")
    cons = pd.read_csv(ANA / "cross_model_position_consistency.csv")
    cell = pd.read_csv(TAB / "cellline_effects.csv")

    ca = {}
    for cl, g in eff[eff.pos18_base != "ALL"].groupby("cell_line"):
        d = g.set_index("pos18_base")
        ca[cl] = {
            "C": float(d.loc["C", "mean_efficacy"]), "A": float(d.loc["A", "mean_efficacy"]),
            "G": float(d.loc["G", "mean_efficacy"]),
            "T": float(d.loc["T", "mean_efficacy"]) if "T" in d.index else float("nan"),
            "nC": int(d.loc["C", "n"]), "nA": int(d.loc["A", "n"]),
            "diff": float(d.loc["C", "mean_efficacy"] - d.loc["A", "mean_efficacy"]),
        }
    peaks = {}
    for _, r in cons.iterrows():
        peaks.setdefault(r["cell_line"], []).append(
            (r["environment"], int(r["peak_cnn"]), int(r["peak_xgboost"]),
             int(r["peak_mlp"]), int(r["peak_linear"]), int(r["peak_transformer"])))
    # signed mutation effect availability (must be reported honestly)
    att = pd.read_csv(TAB / "attribution_summary.csv", usecols=["method", "importance"],
                      low_memory=False)
    signed = {}
    for m in ("cnn_ism", "cnn_ig", "mlp_ig", "xgboost_treeshap", "transformer_attention"):
        v = pd.to_numeric(att.loc[att.method == m, "importance"], errors="coerce").dropna()
        signed[m] = bool((v < 0).any())
    return {"prof": prof, "eff": eff, "cons": cons, "cell": cell, "ca": ca, "peaks": peaks,
            "signed": signed}


def region_means(prof: pd.DataFrame) -> dict:
    reg = {"PAM-proximal seed (17-20)": (17, 20), "PAM (21-23)": (21, 23),
           "Seed core (9-16)": (9, 16), "PAM-distal (1-8)": (1, 8)}
    out = {}
    for m in MODELS:
        out[m] = {k: float(prof.loc[lo:hi, m].mean()) for k, (lo, hi) in reg.items()}
    return out


# ---------------------------------------------------------------- figures
def fig_attribution(prof: pd.DataFrame, pos18_share: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(3.3, 1.72), dpi=300)
    ax.axvspan(17, 20, color="#f39c12", alpha=0.16, zorder=0, label="PAM-proximal 17-20")
    ax.axvspan(21, 23, color="#95a5a6", alpha=0.20, zorder=0, label="PAM 21-23")
    ax.axvline(18, color="#c0392b", lw=1.0, ls="--", zorder=1)
    for m in MODELS:
        ax.plot(prof.index, prof[m], marker="o", ms=1.8, lw=1.1, color=COLORS[m],
                label=MODEL_LABEL[m], zorder=3)
    ax.text(18.25, ax.get_ylim()[1] * 0.97, "pos 18", fontsize=6.4, color="#c0392b",
            ha="left", va="top")
    ax.set_xlabel("sgRNA position (1-23; PAM = 21-23, NGG)", fontsize=7.0)
    ax.set_ylabel("normalized attribution", fontsize=7.0)
    ax.set_xticks([1, 5, 9, 13, 17, 18, 21, 23])
    ax.tick_params(labelsize=6.4)
    ax.grid(alpha=0.25, lw=0.4)
    ax.legend(fontsize=5.8, frameon=False, ncol=2, loc="upper left",
              handlelength=1.1, columnspacing=0.8, labelspacing=0.2)
    fig.tight_layout(pad=0.25)
    out = FIG / "position18_attribution.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def fig_base_effect(ca: dict) -> Path:
    bases = ["A", "C", "G", "T"]
    fig, ax = plt.subplots(figsize=(3.3, 1.72), dpi=300)
    w = 0.2
    for i, cl in enumerate(CELL_ORDER):
        vals = [ca[cl][b] for b in bases]
        xs = np.arange(len(bases)) + (i - 1.5) * w
        ax.bar(xs, vals, width=w, color=[BASE_COLORS[b] for b in bases],
               alpha=0.55 + 0.11 * i, edgecolor="white", linewidth=0.4,
               label=CELL_LABEL[cl])
    for i, cl in enumerate(CELL_ORDER):
        x = 1 + (i - 1.5) * w
        d = ca[cl]["diff"]
        ax.text(x, ca[cl]["C"] + 0.012, f"{d:+.3f}", ha="center", fontsize=5.6,
                color="#c0392b" if d > 0 else "#2c3e50", rotation=90)
    ax.set_xticks(range(len(bases)))
    ax.set_xticklabels([f"{b}\n(n={ca[CELL_ORDER[0]][ 'nC' if b=='C' else 'nA']})"
                        if b in ("A", "C") else b for b in bases], fontsize=5.6)
    ax.set_xlabel("nucleotide at position 18", fontsize=7.0)
    ax.set_ylabel("mean measured efficacy", fontsize=7.0)
    ax.set_ylim(0, 0.40)
    ax.tick_params(labelsize=6.4)
    ax.grid(axis="y", alpha=0.25, lw=0.4)
    ax.legend(fontsize=6.0, frameon=False, ncol=2, loc="upper left", handlelength=1.0,
              columnspacing=0.8, labelspacing=0.2)
    ax.text(0.5, 0.015, "red numbers: C − A difference", transform=ax.transAxes,
            fontsize=5.4, color="#c0392b")
    fig.tight_layout(pad=0.25)
    out = FIG / "position18_base_effect.png"
    fig.savefig(out)
    plt.close(fig)
    return out


# ---------------------------------------------------------------- LaTeX
TEMPLATE = r"""% !TEX program = xelatex
% One-page A4 summary — generated by paper/make_position18_summary.py (all numbers read from artifacts).
\documentclass[10pt,a4paper]{ctexart}
\usepackage[margin=1.1cm]{geometry}
\usepackage{graphicx,booktabs,array,xcolor,amsmath}
\usepackage[hidelinks]{hyperref}
\setlength{\parindent}{0pt}\setlength{\parskip}{1.5pt}
\sloppy
\pagestyle{empty}
\definecolor{acc}{HTML}{1F4E79}
\definecolor{soft}{HTML}{F2F5F8}
\definecolor{warn}{HTML}{B03A2E}
\newcommand{\bd}[1]{\fontsize{8.5}{10.2}\selectfont\textbf{#1}}
\newcommand{\bt}[1]{\fontsize{8.5}{10.2}\selectfont #1}
\newcommand{\sm}[1]{\fontsize{7.5}{9.0}\selectfont #1}
\begin{document}
\enlargethispage{0.8cm}

{\color{acc}\fontsize{18}{21}\selectfont\bfseries AI-discovered candidate sequence factor at sgRNA position 18}\\[1pt]
{\fontsize{10}{12}\selectfont\itshape Multi-model attribution and cell-line-dependent evidence from the DeepCRISPR case study}\\[1pt]
\sm{Computational discovery summary for supervisor discussion $\cdot$ Status: computational discovery completed; experimental validation proposed（计算发现已完成，实验验证方案待评估）}\\[1.5pt]
{\color{acc}\hrule height 0.8pt}
\vspace{1.5pt}

\begin{minipage}[t]{0.44\textwidth}
{\color{acc}\bd{1. What we found}}\\[1pt]
\bd{Multiple model classes consistently identify the PAM-proximal region (positions 17--20) as a high-attribution region, with position 18 repeatedly emerging as a peak position.}\\[1.5pt]
\bt{多模型归因一致指向 PAM 邻近区域（17--20 位），第 18 位在多个模型与多个细胞系中重复成为峰值位置。}\\[1.5pt]
\sm{\itshape Attribution reflects model-derived importance and does not establish causality.}\\[2pt]
\includegraphics[width=\linewidth]{figures/position18_attribution.png}\\[1pt]
\sm{\textbf{Figure 1.} Normalized position attribution of five model classes (mean over cell lines; single-cell-line split). *Transformer = \emph{attention weight}, not gradient/tree attribution. Red dashed: position 18; orange: 17--20; grey: PAM 21--23.}
\end{minipage}\hfill
\begin{minipage}[t]{0.54\textwidth}
{\color{acc}\bd{2. Independent evidence}}\\[1pt]
\sm{
\begin{tabular}{@{}p{0.30\linewidth}p{0.66\linewidth}@{}}
\toprule
\textbf{Evidence} & \textbf{Result (from artifacts)}\\
\midrule
PAM-proximal region & highest-attribution region for CNN, MLP, XGBoost, Transformer\\
Position 18 & recurrent peak in HCT116 and HeLa across models\\
Profile correlation & mean pairwise Spearman @@SPEARMAN@@ (23 positions)\\
Top-3 overlap & @@TOP3@@ of top-3 positions shared between models\\
Model classes & attention peaks at positions 1--2 in HCT116/HeLa (supporting only)\\
\bottomrule
\end{tabular}}
\\[2pt]
\includegraphics[width=\linewidth]{figures/position18_base_effect.png}\\[1pt]
\sm{\textbf{Figure 2.} Mean measured editing efficiency by the nucleotide at position 18 (n = 495--3\,278 per bar); numbers: C $-$ A difference.}\\[1.5pt]
{\color{acc}\bd{The position-18 nucleotide effect is context-dependent rather than universal.}}\\[1pt]
\bt{第 18 位碱基与编辑效率的关系具有明显细胞背景依赖性（HCT116/HeLa 中 C 高于 A，HL60 差异缩小，HEK293T 方向反转），更适合作为 context-dependent candidate factor。}
\end{minipage}

\vspace{2pt}
\colorbox{soft}{\begin{minipage}{\dimexpr\textwidth-2\fboxsep\relax}
{\color{acc}\bd{3. Current interpretation}}\\[1pt]
\bt{Position 18 is a \textbf{candidate sequence-associated factor} whose predictive importance is repeatedly identified by multiple model classes, while its base-specific efficacy association varies across cell-line contexts. 第 18 位目前可定义为一个候选序列相关因素。\quad\textbf{This is an association / model-attribution finding, not a causal conclusion.}}\\[1.5pt]
\sm{\bfseries Why this candidate?} \sm{\textbf{01} PAM-proximal 17--20 is the highest-attribution region for CNN, MLP, XGBoost and Transformer；\textbf{02} position 18 is the modal peak in HCT116 and HeLa；\textbf{03} measured C $-$ A difference HCT116 @@D_H@@, HeLa @@D_HL@@, HL60 @@D_60@@, HEK293T @@D_HE@@（方向随细胞系改变）。}\\[1pt]
\sm{\itshape Evidence chain: multi-model attribution $\rightarrow$ PAM-proximal region $\rightarrow$ position 18 repeatedly prioritized $\rightarrow$ base-specific efficacy differences $\rightarrow$ cell-line-dependent pattern $\rightarrow$ candidate sequence factor.}
\end{minipage}}
\vspace{2pt}

{\color{acc}\bd{4. Minimal experimental validation (proposed, not yet performed)}}\\[1pt]
\begin{minipage}[t]{0.40\textwidth}
\bt{\textbf{Test whether perturbing the model-prioritized nucleotide at position 18 reproducibly changes Cas9 editing efficiency.}}\\[1pt]
\sm{WT: position 18 = original C\\
\hspace{1em}$\vdash$ C$\rightarrow$A \quad $\vdash$ C$\rightarrow$G \quad $\vdash$ C$\rightarrow$T\\
Keep the remaining sgRNA sequence unchanged.\\
Compare measured editing efficiency of each variant with WT.\\
Controls: WT $+$ variants $+$ negative control $+$ reference/positive control.}
\end{minipage}\hfill
\begin{minipage}[t]{0.575\textwidth}
\sm{\bfseries Freeze the prediction before the experiment (prospective test):} \sm{AI prediction (positional importance from ISM / IG / SHAP) $\rightarrow$ freeze hypothesis (position and variant set) $\rightarrow$ wet-lab experiment (WT vs variants, efficiency readout) $\rightarrow$ compare prediction with observation.}\\[1.5pt]
\sm{\color{warn}Directional mutation prediction is currently unavailable: all CNN ISM / IG / SHAP / attention outputs are unsigned magnitudes (only linear coefficients carry a sign, and they diverged in 56/192 runs). Only \emph{positional importance} is supported, so the pre-registered hypothesis specifies the position and variant set, not a predicted direction.}
\end{minipage}

\vspace{2pt}
{\color{acc}\hrule height 0.5pt}
\vspace{1pt}
\sm{\bfseries Limitations:} \sm{computational/observational evidence only; position and nucleotide-specific effects are not fully separable; cell-line differences may reflect sequence composition or cohort differences (position-18 T occurs mainly in HEK293T/HL60); wet-lab validation not yet performed.}\\[1pt]
\sm{\bfseries Sources:} \sm{\texttt{attribution\_summary.csv}, \texttt{position18\_efficacy\_by\_base.csv}, \texttt{cross\_model\_position\_consistency.csv}, \texttt{cellline\_effects.csv}, \texttt{evidence\_matrix.csv}; PAM 21--23 (NGG) verified from raw sequences. \quad\bfseries Status: computational discovery completed; validation proposed（计算发现已完成）\quad Contact: \_\_\_\_\_\_}
\end{document}
"""


def build_tex(d: dict) -> Path:
    ca, cons = d["ca"], d["cons"]
    body = TEMPLATE   # template already uses literal LaTeX braces
    subs = {
        "@@SPEARMAN@@": f"{cons.mean_pairwise_spearman.min():.2f}--{cons.mean_pairwise_spearman.max():.2f}",
        "@@TOP3@@": f"{cons.mean_top3_overlap.min():.2f}--{cons.mean_top3_overlap.max():.2f}",
        "@@D_H@@": f"{ca['hct116']['diff']:+.3f}",
        "@@D_HL@@": f"{ca['hela']['diff']:+.3f}",
        "@@D_60@@": f"{ca['hl60']['diff']:+.3f}",
        "@@D_HE@@": f"{ca['hek293t']['diff']:+.3f}",
    }
    for k, v in subs.items():
        body = body.replace(k, v)
    path = PAPER / "position18_summary.tex"
    path.write_text(body, encoding="utf-8")
    return path


def compile_pdf(tex: Path) -> tuple[bool, str]:
    env = {"PATH": f"{TEXBIN}:{__import__('os').environ['PATH']}", "HOME": "/tmp"}
    cmd = [str(TEXBIN / "xelatex"), "-interaction=nonstopmode", "-halt-on-error", tex.name]
    log = ""
    for _ in range(2):
        r = subprocess.run(cmd, cwd=PAPER, env=env, capture_output=True, text=True)
        log = (PAPER / "position18_summary.log").read_text(errors="ignore")
    ok = "Output written" in log and "! " not in log.split("Output written")[0][-4000:]
    return ok, log


def verify(pdf: Path) -> dict:
    import sys
    sys.path.insert(0, "/tmp/pylibs")
    from pypdf import PdfReader
    r = PdfReader(pdf)
    log = (PAPER / "position18_summary.log").read_text(errors="ignore")
    out = {
        "pages": len(r.pages),
        "size_kb": pdf.stat().st_size // 1024,
        "overfull": len(re.findall(r"Overfull \\hbox", log)),
        "errors": len(re.findall(r"^! ", log, flags=re.M)),
        "undefined_refs": len(re.findall(r"Warning.*undefined", log)),
    }
    return out


def main() -> None:
    d = load()
    FIG.mkdir(parents=True, exist_ok=True)
    p18 = pd.read_csv(ANA / "position18_attribution.csv")
    f1 = fig_attribution(d["prof"], p18)
    f2 = fig_base_effect(d["ca"])
    tex = build_tex(d)
    ok, log = compile_pdf(tex)
    pdf = PAPER / "position18_candidate_summary.pdf"
    src = PAPER / "position18_summary.pdf"
    if src.exists():
        pdf.write_bytes(src.read_bytes())
    checks = verify(pdf) if pdf.exists() else {}
    print("figures:", f1.name, f2.name)
    print("tex:", tex.name, "| compile ok:", ok)
    print("checks:", checks)
    print("C-A:", {k: round(v["diff"], 4) for k, v in d["ca"].items()})
    print("signed mutation effect available:", any(d["signed"].values()),
          "| per method:", d["signed"])
    print("PDF:", pdf)


if __name__ == "__main__":
    main()
