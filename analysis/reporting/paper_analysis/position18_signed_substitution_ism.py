#!/usr/bin/env python3
"""Small SIGNED substitution ISM at sgRNA position 18 (1-based).

Question
--------
For every measured guide whose 1-based position 18 is **C**, what is the signed prediction change

    Delta = f(substituted sequence) - f(actual sequence)

for the three substitutions  C->A / C->G / C->T ?

Method (no retraining, no modification of existing model/ISM code)
----------------------------------------------------------------
* Reference base = the base actually present in the sequence (read from the metadata `sgRNA`
  column and cross-checked against the one-hot tensor).
* Operator = a **true substitution** at position 18: the C channel is set to 0 AND the target
  channel is set to 1 (unlike `compute_cnn_ism`, which toggles a single channel and takes |.|).
* Models are the already-trained artifacts:
      - 7 pooled "ultimate" models: results/batch_20260909_full/summary/ultimate/
      - 12 cell-line-specific CNNs: models/batch_20260909_full/single_<cell>_cnn_sequence_kernel_<k>/
* Delta is computed on raw model outputs (same convention as the stored ISM / IG artifacts,
  which do not clip), and the clipped variant is recorded only as a robustness column.
* Uncertainty = percentile bootstrap over samples (10 000 resamples, seed 42), reported as a
  **descriptive interval for this measured sample set**, not a population inference.

Outputs
-------
    results/analysis/position18_signed_substitution_ISM.csv            aggregated
    results/analysis/position18_signed_substitution_ISM_per_sample.csv per-sample deltas
    results/analysis/position18_signed_substitution_ISM.md             report
    paper/figures/position18_signed_substitution.png                   figure
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import predict as P  # noqa: E402  (reuse the exact training-time builders / predict path)

DATA = ROOT / "data" / "proceeded_data"
ULT = ROOT / "results" / "batch_20260909_full" / "summary" / "ultimate"
CELL_MODELS = ROOT / "models" / "batch_20260909_full"
OUT = ROOT / "results" / "analysis"
FIGDIR = ROOT / "paper" / "figures"

CELLS = ["hct116", "hek293t", "hela", "hl60"]
SEQ = ["A", "C", "G", "T"]
POS_1B = 18            # 1-based sgRNA position of interest
L = POS_1B - 1         # 0-based index inside the 23-nt tensor
SUBS = ["C>A", "C>G", "C>T"]
N_BOOT = 10_000
SEED = 42
DEVICE = "cpu"


# --------------------------------------------------------------------------- data
def load_dataset():
    schema = json.loads((DATA / "feature_schema.json").read_text(encoding="utf-8"))
    plan = P.build_channel_plan(schema, None)          # sequence-only -> 4 channels, 92 features
    X3, X2, y, meta, chosen = P._load_mixed_subset(str(DATA), schema, plan, CELLS)
    assert X2.shape[1] == len(plan["feature_names"]) == 23 * plan["n_channels"] == 92
    assert plan["channels"] == SEQ, plan["channels"]
    return schema, plan, X3, X2, y, meta, chosen


def check_numbering(X3, meta):
    """Verify tensor channel order and that 1-based position 18 is tensor index 17."""
    sg = meta["sgRNA"].astype(str).str.upper().str.strip()
    idx = np.argmax(X3[:, :, :4], axis=2)
    from_tensor = np.array(SEQ)[idx]
    match_all = float((from_tensor == np.array([list(s) for s in sg])[:, :23]).mean())
    pam_gg = float(sg.str[21:23].eq("GG").mean())
    return {
        "cell_order_match": match_all,
        "pam_pos22_23_is_GG": pam_gg,
        "base_at_pos18_from_meta": sg.str[L].value_counts().to_dict(),
        "base_at_pos18_from_tensor": pd.Series(from_tensor[:, L]).value_counts().to_dict(),
    }


# --------------------------------------------------------------------------- models
def _torch_state(path: Path):
    """Accept both checkpoint layouts found in the repo:
    ultimate/*.pt -> {"state_dict": ..., "config": ...}
    models/.../cnn_model.pt -> {"model_state_dict": ..., "config": ...}"""
    import torch
    obj = torch.load(str(path), map_location="cpu", weights_only=False)
    for key in ("state_dict", "model_state_dict"):
        if isinstance(obj, dict) and key in obj:
            return obj[key]
    return obj


def build_model(kind: str, cfg: dict):
    """Instantiate exactly the architecture used at training time and load its weights."""
    import torch
    model = P._build_torch_model(kind, 92, 4, cfg, DEVICE, 4)
    model.load_state_dict(_torch_state(ULT / f"ultimate_{kind}_model.pt"), strict=True)
    model.eval()
    return model


def build_cell_cnn(cell: str, kernel: int):
    import torch
    cfg = json.loads((CELL_MODELS / f"single_{cell}_cnn_sequence_kernel_{kernel}"
                      / "cnn_config.json").read_text(encoding="utf-8"))
    kind = f"cnn{kernel}3"
    model = P._build_torch_model(kind, 92, 4, cfg, DEVICE, 4)
    model.load_state_dict(_torch_state(CELL_MODELS / f"single_{cell}_cnn_sequence_kernel_{kernel}"
                                       / "cnn_model.pt"), strict=True)
    model.eval()
    return model


def ultimate_registry():
    """Pooled models trained on all four cell lines (sequence-only, 92 features)."""
    reg = []
    spec = [("lr", "Linear", "-"), ("xgboost", "XGBoost", "-"), ("mlp", "MLP", "-"),
            ("cnn33", "CNN(k=3)", "3"), ("cnn53", "CNN(k=5)", "5"),
            ("cnn73", "CNN(k=7)", "7"), ("transformer", "Transformer", "-")]
    for kind, display, kernel in spec:
        cfile = ULT / f"ultimate_{kind}_config.json"
        cfg_info = json.loads(cfile.read_text(encoding="utf-8")) if cfile.exists() else {}
        reg.append({
            "model_id": f"ultimate:{kind}", "scope": "pooled", "kind": kind, "display": display,
            "kernel": kernel, "cell_line": "ALL", "cv_r2": cfg_info.get("cv_r2_mean"),
            "config": cfg_info.get("best_config", {}),
        })
    return reg


def cell_registry():
    reg = []
    for cell in CELLS:
        for k in (3, 5, 7):
            cfile = (CELL_MODELS / f"single_{cell}_cnn_sequence_kernel_{k}" / "cnn_config.json")
            cfg_info = json.loads(cfile.read_text(encoding="utf-8"))
            reg.append({
                "model_id": f"cellcnn:{cell}:k{k}", "scope": "cell_specific", "kind": f"cnn{k}3",
                "display": f"CNN(k={k})", "kernel": str(k), "cell_line": cell,
                "cv_r2": np.nan, "config": cfg_info,
            })
    return reg


def load_predictor(entry: dict, feature_names):
    """Return predict(X2, X3). `feature_names` must be the full 92-dim plan names (LR drops _T)."""
    kind = entry["kind"]
    if entry["scope"] == "pooled":
        if kind == "lr":
            from core.models.linear.linear_regression import LinearRegressionModel
            info = json.loads((ULT / "ultimate_lr_model.json").read_text(encoding="utf-8"))
            m = LinearRegressionModel(use_scaler=bool(info.get("use_scaler", False)))
            m.weights = np.asarray(info["weights"], dtype=np.float64)
            m.feature_count = int(info["n_features"])
            m.is_fitted = True
            X_check, names_kept = P._drop_lr_reference_columns(
                np.zeros((1, len(feature_names))), list(feature_names))
            assert names_kept == list(info["feature_names"]), "LR feature order mismatch"
            return lambda X2, X3: P._predict_model(
                "lr", m, P._drop_lr_reference_columns(X2, list(feature_names))[0], DEVICE)
        if kind == "xgboost":
            import pickle
            with open(ULT / "ultimate_xgboost_model.pkl", "rb") as f:
                m = pickle.load(f)
            return lambda X2, X3: P._predict_model("xgboost", m, X2, DEVICE)
        m = build_model(kind, entry["config"])
        if kind in P.KIND_USES_2D:      # MLP consumes the flattened (N, 92) tensor
            return lambda X2, X3: P._predict_model(kind, m, X2, DEVICE)
        return lambda X2, X3: P._predict_model(kind, m, X3, DEVICE)
    # cell-line-specific CNN (sequence-only)
    m = build_cell_cnn(entry["cell_line"], int(entry["kernel"]))
    return lambda X2, X3: P._predict_model(entry["kind"], m, X3, DEVICE)


# --------------------------------------------------------------------------- deltas
def substituted(X3c: np.ndarray, target: str) -> np.ndarray:
    """True substitution at tensor index 17: original C -> target (one-hot, single channel on)."""
    Xm = X3c.copy()
    Xm[:, L, :] = 0.0
    Xm[:, L, SEQ.index(target)] = 1.0
    return Xm


def deltas_for_entry(entry, X3c, X2c, predict):
    """Signed deltas (mutant - wildtype) for the three substitutions on the given subset."""
    wt = predict(X2c, X3c)
    # correctness self-check: rebuilding the same C one-hot must reproduce the wild type exactly
    X_same = substituted(X3c, "C")
    assert np.array_equal(X_same, X3c)
    assert float(np.abs(predict(X_same.reshape(len(X_same), -1), X_same) - wt).max()) < 1e-9
    wt_clip = np.clip(wt, 0.0, 1.0)
    out = {}
    for sub in SUBS:
        target = sub[-1]
        Xm = substituted(X3c, target)
        mu = predict(Xm.reshape(len(Xm), -1), Xm)
        out[sub] = mu - wt
        out[f"{sub}#clip"] = np.clip(mu, 0.0, 1.0) - wt_clip
    return out


def bootstrap_ci(delta: np.ndarray, rng: np.random.Generator, n_boot: int = N_BOOT):
    n = len(delta)
    if n < 2:
        return (float("nan"), float("nan"))
    means = np.empty(n_boot, dtype=np.float64)
    block = max(1, min(n_boot, int(2e6 // max(n, 1))))     # memory-safe chunking
    filled = 0
    while filled < n_boot:
        b = min(block, n_boot - filled)
        idx = rng.integers(0, n, size=(b, n))
        means[filled:filled + b] = delta[idx].mean(axis=1)
        filled += b
    return tuple(float(v) for v in np.percentile(means, [2.5, 97.5]))


def describe(delta: np.ndarray, rng, model_id, scope, display, kernel, cell_line, sub, cv_r2,
             delta_clip=None):
    n = len(delta)
    lo, hi = bootstrap_ci(delta, rng)
    mean = float(delta.mean())
    clip_sign_flip = (float(np.mean(np.sign(delta) != np.sign(delta_clip)))
                      if delta_clip is not None else float("nan"))
    return {
        "model_id": model_id, "scope": scope, "model": display, "kernel": kernel,
        "cell_line": cell_line, "substitution": sub, "n": n,
        "mean_delta": mean, "median_delta": float(np.median(delta)),
        "std": float(delta.std(ddof=1)) if n > 1 else float("nan"),
        "boot_ci_low": lo, "boot_ci_high": hi,
        "frac_positive": float(np.mean(delta > 0)), "frac_negative": float(np.mean(delta < 0)),
        "direction": ("increase" if mean > 0 else "decrease" if mean < 0 else "zero"),
        "ci_excludes_zero": bool(lo > 0 or hi < 0),
        "mean_delta_clipped": float(delta_clip.mean()) if delta_clip is not None else float("nan"),
        "frac_clip_changes_sign": clip_sign_flip,
        "cv_r2": cv_r2,
    }


# --------------------------------------------------------------------------- main
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGDIR.mkdir(parents=True, exist_ok=True)
    schema, plan, X3, X2, y, meta, chosen = load_dataset()
    checks = check_numbering(X3, meta)

    cell_col = "Cell line" if "Cell line" in meta.columns else "cell_line"
    cells = meta[cell_col].astype(str).str.lower().to_numpy()
    sg = meta["sgRNA"].astype(str).str.upper().str.strip().to_numpy()
    base18 = np.array([s[L] for s in sg])

    sel_c = np.where(base18 == "C")[0]
    print(f"[data] samples={len(y)} | cells={chosen} | pos18=C: {len(sel_c)} "
          f"({100 * len(sel_c) / len(y):.1f} %)")
    print(f"[check] tensor/meta order match={checks['cell_order_match']:.4f} | "
          f"PAM GG={checks['pam_pos22_23_is_GG']:.3f} | "
          f"pos18 base (meta)={checks['base_at_pos18_from_meta']}")

    rng = np.random.default_rng(SEED)
    rows, per_sample = [], []
    registry = ultimate_registry() + cell_registry()

    for entry in registry:
        if entry["scope"] == "pooled":
            idx = sel_c
        else:
            idx = sel_c[cells[sel_c] == entry["cell_line"]]
        if len(idx) == 0:
            print(f"[skip] {entry['model_id']}: no sample with position 18 = C")
            continue
        X3c, X2c = np.ascontiguousarray(X3[idx]), np.ascontiguousarray(X2[idx])
        predict = load_predictor(entry, plan["feature_names"])
        d = deltas_for_entry(entry, X3c, X2c, predict)

        # model-level aggregate (its own sample set)
        for sub in SUBS:
            rows.append(describe(d[sub], rng, entry["model_id"], entry["scope"], entry["display"],
                                 entry["kernel"], entry["cell_line"], sub, entry["cv_r2"],
                                 d[f"{sub}#clip"]))
        # per-cell-line strata for the pooled models
        if entry["scope"] == "pooled":
            for cell in CELLS:
                m = cells[idx] == cell
                if m.sum() < 2:
                    continue
                for sub in SUBS:
                    rows.append(describe(d[sub][m], rng, entry["model_id"], entry["scope"],
                                         entry["display"], entry["kernel"], cell, sub,
                                         entry["cv_r2"], d[f"{sub}#clip"][m]))
        # per-sample table (pooled models only -> one row per sample, wide)
        if entry["scope"] == "pooled":
            for j, sidx in enumerate(idx):
                per_sample.append({
                    "sample_id": int(sidx), "cell_line": cells[sidx], "sgRNA": sg[sidx],
                    "base_pos18": base18[sidx], "model": entry["display"],
                    "kernel": entry["kernel"], "y_measured": float(y[sidx]),
                    "delta_C_A": float(d["C>A"][j]), "delta_C_G": float(d["C>G"][j]),
                    "delta_C_T": float(d["C>T"][j]),
                })
        print(f"[ok] {entry['model_id']:<26} n={len(idx):>5} "
              f"Δ(C>A)={d['C>A'].mean():+.5f}  Δ(C>G)={d['C>G'].mean():+.5f}  "
              f"Δ(C>T)={d['C>T'].mean():+.5f}")

    agg = pd.DataFrame(rows)
    agg.to_csv(OUT / "position18_signed_substitution_ISM.csv", index=False)
    ps = pd.DataFrame(per_sample)
    ps.to_csv(OUT / "position18_signed_substitution_ISM_per_sample.csv", index=False)
    print(f"\n[write] {OUT / 'position18_signed_substitution_ISM.csv'} ({len(agg)} rows)")
    print(f"[write] {OUT / 'position18_signed_substitution_ISM_per_sample.csv'} ({len(ps)} rows)")

    make_figure(agg)
    write_report(agg, checks, len(sel_c), len(y), chosen)
    return agg, ps


def make_figure(agg: pd.DataFrame) -> None:
    """Two rows: pooled models (top) and cell-line-specific CNN checkpoints (bottom)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pooled = agg[(agg.scope == "pooled") & (agg.cell_line == "ALL")]
    spec = agg[agg.scope == "cell_specific"]
    order = ["Linear", "XGBoost", "MLP", "CNN(k=3)", "CNN(k=5)", "CNN(k=7)", "Transformer"]
    sub_color = {"C>A": "#c0392b", "C>G": "#27ae60", "C>T": "#2980b9"}
    cell_color = {"hct116": "#2c3e50", "hek293t": "#e67e22", "hela": "#16a085", "hl60": "#8e44ad"}

    fig, axes = plt.subplots(2, 3, figsize=(13.6, 8.4),
                             gridspec_kw={"height_ratios": [1, 1.35]})
    for j, sub in enumerate(SUBS):
        ax = axes[0, j]
        d = pooled[pooled.substitution == sub].set_index("model").reindex(order).dropna(how="all")
        y = np.arange(len(d))[::-1]
        ax.errorbar(d["mean_delta"], y,
                    xerr=[d["mean_delta"] - d["boot_ci_low"], d["boot_ci_high"] - d["mean_delta"]],
                    fmt="o", color=sub_color[sub], ecolor="#7f8c8d", capsize=3, markersize=6)
        ax.axvline(0.0, color="black", lw=1, ls="--")
        ax.set_title(f"pooled models — 18: {sub}", fontsize=11)
        ax.set_yticks(y); ax.set_yticklabels(d.index, fontsize=9)
        ax.grid(alpha=0.25, axis="x")

        ax2 = axes[1, j]
        d2 = spec[spec.substitution == sub].copy()
        d2["label"] = d2["cell_line"] + " k" + d2["kernel"].astype(str)
        d2 = d2.sort_values(["cell_line", "kernel"], ascending=[False, True])
        y2 = np.arange(len(d2))
        ax2.errorbar(d2["mean_delta"], y2,
                     xerr=[d2["mean_delta"] - d2["boot_ci_low"],
                           d2["boot_ci_high"] - d2["mean_delta"]],
                     fmt="o", ecolor="#7f8c8d", capsize=2, markersize=5,
                     color="black", zorder=1)
        for yy, (_, r) in zip(y2, d2.iterrows()):
            ax2.plot(r["mean_delta"], yy, "o", color=cell_color[r["cell_line"]], markersize=6,
                     zorder=2, label=r["cell_line"])
        ax2.axvline(0.0, color="black", lw=1, ls="--")
        ax2.set_title(f"cell-line-specific CNN — 18: {sub}", fontsize=11)
        ax2.set_yticks(y2); ax2.set_yticklabels(d2["label"], fontsize=8)
        ax2.grid(alpha=0.25, axis="x")
        handles = [plt.Line2D([], [], marker="o", ls="", color=cell_color[c], label=c)
                   for c in CELLS]
        ax2.legend(handles=handles, fontsize=8, loc="lower left", framealpha=0.9)
    for ax in axes[1]:
        ax.set_xlabel("signed Δ prediction (mutant − WT)", fontsize=9)
    fig.suptitle("Signed substitution effect at sgRNA position 18 — reference base = C "
                 "(bar = percentile bootstrap 95% CI over guides)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIGDIR / "position18_signed_substitution.png", dpi=185)
    plt.close(fig)
    print(f"[write] {FIGDIR / 'position18_signed_substitution.png'}")


def measured_comparison(agg: pd.DataFrame):
    """Compare model-predicted C>X direction with the measured per-base efficacy difference.

    Sign convention: mean_delta(C>X) < 0  <=>  predicted efficacy(C) > efficacy(X);
    measured "C - X" > 0 means the same thing. Only 4 cell lines -> descriptive, not a test.
    """
    path = ROOT / "docs" / "paper_analysis" / "position18_efficacy_by_base.csv"
    if not path.exists():
        return None
    eff = pd.read_csv(path)
    eff = eff[eff.pos18_base != "ALL"]
    piv = eff.pivot_table(index="cell_line", columns="pos18_base", values="mean_efficacy")
    cnt = eff.pivot_table(index="cell_line", columns="pos18_base", values="n")
    b = agg[(agg.scope == "pooled") & (agg.cell_line != "ALL")]
    rows = []
    for sub, base in (("C>A", "A"), ("C>G", "G"), ("C>T", "T")):
        model = b[b.substitution == sub].groupby("cell_line")["mean_delta"].mean()
        for cell in model.index:
            if cell not in piv.index or base not in piv.columns or "C" not in piv.columns:
                continue
            if pd.isna(piv.loc[cell, base]) or int(cnt.loc[cell, base] or 0) == 0:
                continue          # no measured guide with this base in this cell line
            m_diff = float(piv.loc[cell, "C"] - piv.loc[cell, base])
            rows.append({"substitution": sub, "cell_line": cell,
                         "model_mean_delta": float(model.loc[cell]),
                         "measured_C_minus_X": m_diff,
                         "model_says_C_better": bool(model.loc[cell] < 0),
                         "measured_says_C_better": bool(m_diff > 0),
                         "agree": bool((model.loc[cell] < 0) == (m_diff > 0)),
                         "n_C": int(cnt.loc[cell, "C"]),
                         "n_X": (int(cnt.loc[cell, base]) if pd.notna(cnt.loc[cell, base]) else 0)})
    return pd.DataFrame(rows)


def _table(d: pd.DataFrame, key: str = "model") -> str:
    """Markdown table; always shows model + cell line so every row is identifiable."""
    if d.empty:
        return "_(no rows)_"
    lines = ["| model | kernel | cell line | substitution | n | mean Δ | median Δ | "
             "95% bootstrap CI | P(Δ>0) | direction | CI excludes 0 |",
             "| :--- | :--- | :--- | :--- | ---: | ---: | ---: | :--- | ---: | :--- | :--- |"]
    for _, r in d.sort_values(["model", "cell_line", "kernel", "substitution"]).iterrows():
        lines.append(
            f"| {r['model']} | {r['kernel']} | {r['cell_line']} | {r['substitution']} | "
            f"{int(r['n'])} | {r['mean_delta']:+.5f} | {r['median_delta']:+.5f} | "
            f"[{r['boot_ci_low']:+.5f}, {r['boot_ci_high']:+.5f}] | {r['frac_positive']:.3f} | "
            f"{r['direction']} | {'yes' if r['ci_excludes_zero'] else 'no'} |")
    return "\n".join(lines)


def write_report(agg: pd.DataFrame, checks: dict, n_c: int, n_all: int, chosen: list) -> None:
    pooled = agg[(agg.scope == "pooled") & (agg.cell_line == "ALL")]
    by_line = agg[(agg.scope == "pooled") & (agg.cell_line != "ALL")]
    cell_spec = agg[agg.scope == "cell_specific"]

    # stability: sign agreement across every (model, kernel, cell line) configuration
    def stability_table():
        lines = ["| substitution | configurations | same sign | share | mean of means | "
                 "configs with CI excluding 0 |", "| :--- | ---: | ---: | ---: | ---: | ---: |"]
        for sub in SUBS:
            d = agg[(agg.substitution == sub) & (agg.cell_line != "ALL")]
            s = np.sign(d["mean_delta"])
            pos = int((s > 0).sum())
            neg = int((s < 0).sum())
            dom = "increase" if pos >= neg else "decrease"
            lines.append(f"| {sub} | {len(d)} | {dom} | {max(pos, neg) / len(d):.2f} | "
                         f"{d['mean_delta'].mean():+.5f} | {int(d['ci_excludes_zero'].sum())} |")
        return "\n".join(lines)

    cmp_df = measured_comparison(agg)
    if cmp_df is not None:
        cmp_df.to_csv(OUT / "position18_signed_substitution_ISM_vs_measured.csv", index=False)
        cmp_lines = ["| substitution | cell line | model mean Δ | measured C − X | model direction | "
                     "measured direction | agree | n(C) | n(X) |",
                     "| :--- | :--- | ---: | ---: | :--- | :--- | :--- | ---: | ---: |"]
        for _, r in cmp_df.iterrows():
            cmp_lines.append(
                f"| {r['substitution']} | {r['cell_line']} | {r['model_mean_delta']:+.5f} | "
                f"{r['measured_C_minus_X']:+.3f} | "
                f"{'C better' if r['model_says_C_better'] else 'X better'} | "
                f"{'C better' if r['measured_says_C_better'] else 'X better'} | "
                f"{'yes' if r['agree'] else 'NO'} | {r['n_C']} | {r['n_X']} |")
        cmp_table = "\n".join(cmp_lines)
        agree_share = float(cmp_df.agree.mean())
    else:
        cmp_table, agree_share = "_(measured per-base efficacy file not found)_", float("nan")

    ps = pd.read_csv(OUT / "position18_signed_substitution_ISM_per_sample.csv")
    agree = {}
    for a, b in [("delta_C_A", "delta_C_G"), ("delta_C_A", "delta_C_T"), ("delta_C_G", "delta_C_T")]:
        agree[f"{a[-1]} vs {b[-1]}"] = float(np.mean(np.sign(ps[a]) == np.sign(ps[b])))

    md = f"""# Position-18 signed substitution ISM — {", ".join(SUBS)}

> Reference base = the base actually present at position 18 (guides with **C**); operator = a true
> one-hot substitution (C channel off, target channel on); Δ = raw model output (mutant) − (WT).
> **No retraining**: the 7 pooled *ultimate* models and 12 cell-line-specific CNN checkpoints that
> already exist in the repo were re-used unchanged. Intervals are percentile bootstrap CIs
> ({N_BOOT:,} resamples, seed {SEED}) over the measured sample set — a descriptive interval for
> these data, not a population inference.

## 0. Data and correctness checks

| Item | Value |
| :--- | :--- |
| Measured guides used | {n_all} (4 cell lines: {", ".join(chosen)}) |
| Guides with position 18 = C (analysis set) | **{n_c}** ({100 * n_c / n_all:.1f} %) |
| Tensor ↔ metadata sequence agreement | {checks['cell_order_match']:.4f} |
| PAM positions 22–23 = GG | {checks['pam_pos22_23_is_GG']:.3f} |
| Position-18 base (metadata) | {checks['base_at_pos18_from_meta']} |
| Models re-used | 7 pooled (Linear, XGBoost, MLP, CNN k=3/5/7, Transformer) + 12 cell-line-specific CNNs |

## 1. Pooled models — signed Δ per substitution

{_table(pooled)}

## 2. Cell-line strata (pooled models, same guides split by cell line)

{_table(by_line)}

## 3. Cell-line-specific CNN checkpoints (model trained on that cell line only)

{_table(cell_spec)}

## 4. Stability across configurations

Every row below is one (model × kernel × cell line) configuration (the pooled models are also
counted once per cell-line stratum); "same sign" = share of configurations agreeing with the
majority direction.

{stability_table()}

Per-sample sign agreement between substitutions (pooled models, n={len(ps)} sample×model rows):
{json.dumps({k: round(v, 3) for k, v in agree.items()})}

## 5. Do the model predictions agree with the measured efficacy differences?

Measured per-base efficacy comes from `docs/paper_analysis/position18_efficacy_by_base.csv`
(observational data, same guides). "C better" = predicted efficacy(C) > efficacy(X) for the model,
and measured efficacy(C) > efficacy(X) for the data.

{cmp_table}

Agreement rate: **{agree_share:.2%}** of the (substitution × cell line) cells
(4 cell lines only — this is a descriptive comparison, not a statistical test).

## 6. Answers to the three questions

See the chat summary; the machine-readable basis is
`results/analysis/position18_signed_substitution_ISM.csv`
(pooled models), `..._per_sample.csv` (per-sample Δ) and `..._vs_measured.csv` (this section).

## 7. Caveats

* The models are trained on **observational** data; Δ is a model prediction, not a causal effect.
* Predictive quality differs strongly between model classes (`cv_r2_mean`: MLP 0.145,
  XGBoost 0.127, CNN(k=5) 0.092, Linear 0.081, CNN(k=3) 0.060, **CNN(k=7) −0.016**). A model whose
  CV R² is ≈0 or negative cannot support a directional claim; it is reported for completeness only.
* Δ is taken on raw model outputs (the convention used by the stored ISM/IG/SHAP artifacts);
  the clipped-output variant is stored in `mean_delta_clipped` / `frac_clip_changes_sign`.
* Only guides with C at position 18 are analysed, so these results say nothing about the ~70 % of
  guides carrying A/G/T there.
"""
    (OUT / "position18_signed_substitution_ISM.md").write_text(md, encoding="utf-8")
    print(f"[write] {OUT / 'position18_signed_substitution_ISM.md'}")


if __name__ == "__main__":
    main()
