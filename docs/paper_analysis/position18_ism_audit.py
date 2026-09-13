"""Position-18 ISM audit (read-only).

Question: do the existing ISM artifacts contain SIGNED per-substitution effects for
position 18 (C->A, C->G, C->T) that could guide a wet-lab design?

What it does:
  * scans every CNN experiment's raw ISM file (cnn_feature_importance.csv, 576 files),
  * reads the metadata from cnn_info.txt,
  * extracts the position-18 rows for the four sequence channels,
  * reports DESCRIPTIVE statistics only (no hypothesis tests are created here; the
    project's existing bootstrap / permutation / FDR artifacts are not re-computed),
  * writes results/analysis/position18_ISM_audit.csv and .md

It never trains, never modifies model/XAI code, and never writes into the experiment
directories.
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
BATCH = ROOT / "results" / "batch_20260909_full"
OUT = ROOT / "results" / "analysis"
POSITION = 18            # 1-based sgRNA position (paper numbering)
POSITION_RAW = POSITION - 1  # the raw CSV stores 0-based loop index (verified against attribution_summary)
SEQ_CHANNELS = ["A", "C", "G", "T"]
CODE_REF = "src/cnn/cnn.py:284-311 (compute_cnn_ism)"


def parse_info(path: Path) -> dict:
    info = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip().lower()] = v.strip()
    return info


def collect() -> pd.DataFrame:
    rows = []
    files = sorted(glob.glob(str(BATCH / "**" / "cnn_feature_importance.csv"), recursive=True))
    for f in files:
        exp = Path(f).parent
        info_files = list(exp.glob("*info*.txt"))
        info = parse_info(info_files[0]) if info_files else {}
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        need = {"Position", "Channel", "CNN_ISM"}
        if not need.issubset(df.columns):
            continue
        sel = df[(df["Channel"].isin(SEQ_CHANNELS)) & df["Position"].notna()]
        if sel.empty:
            continue
        kernel = info.get("sequence_kernel", "")
        if not kernel:
            m = re.search(r"kernel_(\d+)", exp.name)
            kernel = m.group(1) if m else ""
        base = {
            "experiment": exp.name,
            "split_type": info.get("split_type", ""),
            "cell_line": info.get("cell_line", ""),
            "environment": info.get("environment", ""),
            "random_seed": info.get("random_seed", ""),
            "kernel": str(kernel),
        }
        for _, r in sel.iterrows():
            rows.append({
                **base,
                "position": int(r["Position"]),
                "channel": str(r["Channel"]),
                "cnn_ism": float(r["CNN_ISM"]),
                "ism_snr": float(r["ISM_SNR"]) if "ISM_SNR" in df.columns and pd.notna(r.get("ISM_SNR")) else np.nan,
                "cnn_ig": float(r["CNN_IG"]) if "CNN_IG" in df.columns and pd.notna(r.get("CNN_IG")) else np.nan,
                "n_channels_in_file": int(df["Channel"].nunique()),
                "is_position18": bool(int(r["Position"]) == POSITION_RAW),
                "position_raw": int(r["Position"]),
            })
    return pd.DataFrame(rows)


def describe(g: pd.DataFrame) -> pd.Series:
    v = g["cnn_ism"]
    n = int(v.size)
    sd = float(v.std(ddof=1)) if n > 1 else float("nan")
    se = sd / np.sqrt(n) if n > 1 else float("nan")
    return pd.Series({
        "n": n,
        "mean_effect": float(v.mean()),
        "median_effect": float(v.median()),
        "std": sd,
        "ci_low": float(v.mean() - 1.96 * se) if n > 1 else float("nan"),
        "ci_high": float(v.mean() + 1.96 * se) if n > 1 else float("nan"),
        "min": float(v.min()),
        "max": float(v.max()),
        "mean_ism_snr": float(g["ism_snr"].mean()),
        "mean_cnn_ig": float(g["cnn_ig"].mean()),
    })


def build_audit(raw_all: pd.DataFrame) -> pd.DataFrame:
    raw_all = raw_all.copy()
    # NaN cell_line = runs pooled over cell lines (`mixed_cnn_all_seed_*`); label explicitly so
    # the audit CSV is self-describing (NaN would also poison `if c` filters -- bool(nan) is True).
    raw_all["cell_line"] = raw_all["cell_line"].apply(
        lambda c: c if isinstance(c, str) and c.strip().lower() not in ("", "none", "nan", "null")
        else "pooled")
    raw_all["rank_in_channel"] = (raw_all.groupby(["experiment", "channel"])["cnn_ism"]
                                  .rank(ascending=False, method="min"))
    raw = raw_all[raw_all["is_position18"]].copy()
    out = []
    # per (kernel, cell_line, channel) and overall per (kernel, channel), (cell_line, channel), channel
    for kernel in sorted(raw["kernel"].unique()):
        for cell in sorted([c for c in raw["cell_line"].unique() if c]):
            sub = raw[(raw["kernel"] == kernel) & (raw["cell_line"] == cell)]
            if sub.empty:
                continue
            for ch in SEQ_CHANNELS:
                g = sub[sub["channel"] == ch]
                if g.empty:
                    continue
                s = describe(g)
                top = (sub.groupby("experiment")
                          .apply(lambda d: d.loc[d["cnn_ism"].idxmax(), "channel"], include_groups=False))
                out.append({
                    "model": "cnn", "kernel": kernel, "cell_line": cell,
                    "position": POSITION, "reference_base": "not_stored",
                    "mutated_base": ch, **s.to_dict(),
                    "fraction_positive": "not_available", "fraction_negative": "not_available",
                    "available": "magnitude_only",
                    "signed_effect_available": False,
                    "fraction_channel_is_top": float((top == ch).mean()) if len(top) else float("nan"),
                    "rank_mean": float(g["rank_in_channel"].mean()),
                    "rank_median": float(g["rank_in_channel"].median()),
                    "fraction_rank_le3": float((g["rank_in_channel"] <= 3).mean()),
                })
    audit = pd.DataFrame(out)

    # overall rows (kernel=ALL / cell_line=ALL)
    extra = []
    for kernel in ["ALL"] + sorted(raw["kernel"].unique()):
        for cell in ["ALL"] + sorted([c for c in raw["cell_line"].unique() if c]):
            sub = raw.copy()
            if kernel != "ALL":
                sub = sub[sub["kernel"] == kernel]
            if cell != "ALL":
                sub = sub[sub["cell_line"] == cell]
            if sub.empty:
                continue
            for ch in SEQ_CHANNELS:
                g = sub[sub["channel"] == ch]
                if g.empty:
                    continue
                s = describe(g)
                top = (sub.groupby("experiment")
                          .apply(lambda d: d.loc[d["cnn_ism"].idxmax(), "channel"], include_groups=False))
                extra.append({
                    "model": "cnn", "kernel": kernel, "cell_line": cell,
                    "position": POSITION, "reference_base": "not_stored", "mutated_base": ch,
                    **s.to_dict(), "fraction_positive": "not_available", "fraction_negative": "not_available",
                    "available": "magnitude_only", "signed_effect_available": False,
                    "fraction_channel_is_top": float((top == ch).mean()) if len(top) else float("nan"),
                    "rank_mean": float(g["rank_in_channel"].mean()),
                    "rank_median": float(g["rank_in_channel"].median()),
                    "fraction_rank_le3": float((g["rank_in_channel"] <= 3).mean()),
                })
    audit = pd.concat([audit, pd.DataFrame(extra)], ignore_index=True)
    cols = ["model", "kernel", "cell_line", "position", "reference_base", "mutated_base",
            "n", "mean_effect", "median_effect", "std", "ci_low", "ci_high",
            "fraction_positive", "fraction_negative", "available",
            "signed_effect_available", "min", "max", "fraction_channel_is_top",
            "rank_mean", "rank_median", "fraction_rank_le3", "mean_ism_snr", "mean_cnn_ig"]
    audit = audit[cols]
    for c in ("kernel", "cell_line", "mutated_base", "reference_base", "available"):
        audit[c] = audit[c].astype(str)
    return audit


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw_all = collect()
    raw_all.to_csv(OUT / "ISM_all_positions_long.csv", index=False)
    raw = raw_all[raw_all["is_position18"]].copy()
    raw.to_csv(OUT / "position18_ISM_raw_long.csv", index=False)
    # NOTE: must pass the FULL long table so ranks are computed across all 23 positions
    # (build_audit subsets to position 18 internally).
    audit = build_audit(raw_all)
    audit.to_csv(OUT / "position18_ISM_audit.csv", index=False)

    files = sorted(glob.glob(str(BATCH / "**" / "cnn_feature_importance.csv"), recursive=True))
    per_sample = [p for p in glob.glob(str(ROOT / "results" / "**" / "*.npy"), recursive=True)]
    checkpoints = sorted(glob.glob(str(BATCH / "summary" / "ultimate" / "*_model.pt")))

    overall = audit[(audit.kernel == "ALL") & (audit.cell_line == "ALL")]
    rank_table = "\n".join(
        f"| 18: {r.mutated_base} | {r.rank_mean:.1f} | {r.rank_median:.0f} | {r.fraction_rank_le3:.2f} |"
        for r in overall.sort_values("mutated_base").itertuples())
    by_kernel = audit[(audit.kernel != "ALL") & (audit.cell_line == "ALL")]
    by_cell = audit[(audit.kernel == "ALL") & (audit.cell_line != "ALL")]

    def table(df: pd.DataFrame, key: str) -> str:
        lines = ["| " + key + " | channel | n | mean \\|Δŷ\\| | median | std | 95% CI (descriptive) | max | fraction channel is top |",
                 "| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: |"]
        for _, r in df.sort_values([key, "mutated_base"]).iterrows():
            ft = "NA" if pd.isna(r["fraction_channel_is_top"]) else f"{r['fraction_channel_is_top']:.2f}"
            lines.append(f"| {r[key]} | {r['mutated_base']} | {int(r['n'])} | {r['mean_effect']:.5f} | "
                         f"{r['median_effect']:.5f} | {r['std']:.5f} | "
                         f"[{r['ci_low']:.5f}, {r['ci_high']:.5f}] | {r['max']:.5f} | {ft} |")
        return "\n".join(lines)

    infos = []
    for p in files[:3] + files[-1:]:
        infos.append("`" + str(Path(p).relative_to(ROOT)) + "`")

    # Reference-base composition at 1-based position 18 (raw index 17), read from the raw
    # source sequences. Needed because "18: C→A" is only defined for guides carrying C there.
    base_counts: dict = {}
    n_seq = 0
    for src in sorted(glob.glob(str(ROOT / "data" / "source_data" / "*.csv"))):
        sdf = pd.read_csv(src)
        col = next((c for c in sdf.columns
                    if any(k in c.lower() for k in ("sg", "seq", "target"))), None)
        if col is None:
            continue
        for s in sdf[col].astype(str).str.upper().str.strip():
            if len(s) >= 23:
                base_counts[s[POSITION_RAW]] = base_counts.get(s[POSITION_RAW], 0) + 1
                n_seq += 1
    ref_rows = "\n".join(
        f"| {b} | {base_counts.get(b, 0)} | {100.0 * base_counts.get(b, 0) / max(n_seq, 1):.1f} % |"
        for b in "ACGT")
    c_share = 100.0 * base_counts.get("C", 0) / max(n_seq, 1)

    # Experiment composition, counted from the audit table (labels already normalized to `pooled`).
    _per = audit[(audit.kernel != "ALL") & (audit.cell_line != "ALL")]
    comp_cell = {k: int(v // len(SEQ_CHANNELS))
                 for k, v in _per.groupby("cell_line")["n"].sum().items()}
    comp_kernel = {k: int(v // len(SEQ_CHANNELS))
                   for k, v in _per.groupby("kernel")["n"].sum().items()}

    # Final status block (fixed field names requested for the audit).
    sens = overall.sort_values("mean_effect", ascending=False)
    top_ch = str(sens.iloc[0]["mutated_base"])
    top_val = float(sens.iloc[0]["mean_effect"])
    status_table = "\n".join(
        f"| **{k}** | {v} |" for k, v in [
            ("Position 18 ISM status",
             "magnitude-only (**unsigned**); no signed per-substitution effect is stored"),
            ("C→A", "**unavailable** — no sign in the artifact, no reference base recorded"),
            ("C→G", "**unavailable** — no sign in the artifact, no reference base recorded"),
            ("C→T", "**unavailable** — no sign in the artifact, no reference base recorded"),
            ("Best experimental candidate",
             f"no model-supported **directional** candidate (verdict C). Highest position-18 "
             f"sensitivity is the *channel toggle* {top_ch} (mean |Δŷ| = {top_val:.5f}); the "
             f"strongest **observational** (not predicted) signal is C→A"),
            ("Can current ISM support a directional wet-lab hypothesis?", "**No**"),
            ("Recommended next computational step",
             f"re-run ISM as a true substitution on the {len(checkpoints)} existing checkpoints in "
             f"`results/batch_20260909_full/summary/ultimate/` (keep reference base, store signed "
             f"Δŷ = ŷ(mut) − ŷ(WT)); no retraining needed"),
            ("Recommended wet-lab hypothesis",
             "test-of-effect, not direction: *perturbing position 18 (WT base C → A) changes "
             "measured editing efficiency relative to the unmodified sgRNA*; direction left "
             "unpredicted"),
        ])
    md = f"""# Position-18 ISM audit

> Scope: read-only audit of the **existing** ISM artifacts in `results/`.
> No retraining, no modification of the CNN / ISM code, no re-computation of the
> project's existing bootstrap / permutation / FDR statistics.
> All numbers below are **descriptive** summaries of stored values; they are not
> hypothesis tests.

## 1. ISM source files

| Item | Finding |
| :--- | :--- |
| Raw ISM artifacts | {len(files)} files named `cnn_feature_importance.csv`, one per CNN experiment (e.g. {", ".join(infos)}) |
| Columns | `Feature, Position, Channel, CNN_IG, CNN_ISM, ISM_SNR` |
| Granularity | one row per (position × channel); **aggregated over the test samples of that experiment** (no per-sample rows are stored) |
| Numbering checked | sequence-only runs: 92 rows (23 × 4); environment runs: 184 rows (23 × 8, incl. CTCF/Dnase/H3K4me3/RRBS) |
| Per-sample ISM arrays | **none** (`results/**/*.npy` = {len(per_sample)}); ISM is not persisted per sample |
| Code that produced them | `{CODE_REF}` |
| Reusable trained checkpoints | {len(checkpoints)} CNN checkpoints exist in `results/batch_20260909_full/summary/ultimate/` (`ultimate_cnn33/53/73_model.pt` + config) — usable for a **signed** re-audit without retraining |

## 2. ISM definition (read from code, not from column names)

```python
X_mut[:, l, c] = np.where(X_mut[:, l, c] > 0, 0.0, 1.0)   # channel toggle
mut_preds = model(X_mut)
ism_deltas[:, l, c] = np.abs(mut_preds - base_preds)      # <- absolute value
mean_ism = np.mean(ism_deltas, axis=0); std_ism = np.std(ism_deltas, axis=0)
ISM_SNR  = mean_ism / (std_ism + 1e-12)
```

* **ISM definition**: `CNN_ISM[position, channel] = mean_over_samples( | ŷ(toggle channel c at position l) − ŷ(original) | )`.
* **Sign convention**: **absolute value is taken before averaging** → the stored value is
  non-negative by construction and carries **no direction**.
* **Reference base**: **not stored**. The CSV records only the channel that is toggled;
  it does not record which base the sample actually had at that position.
* **Operator caveat (measured from code)**: the perturbation is a *channel toggle*, not a
  base substitution. If the sample already had base `c` at position `l`, the channel is set
  to 0 (position becomes empty); if it did not, the channel is set to 1 **while the original
  base channel remains 1** (two active channels). `CNN_ISM[l, c]` therefore mixes both cases
  and cannot be read as "substituting the original base by `c`".
* **Standardisation**: none (raw mean/σ of the model output difference); only `ISM_SNR` is a
  ratio of the two.
* **Numbering (verified, not assumed)**: the raw CSV `Position` column is the **0-based** loop
  index `l` of `for l in range(L)` (feature names are `channel_pos_l`). The analysis layer
  converts it to 1-based (`analyse/attribution/extractors.py::_parse_position_channel` adds +1),
  which is confirmed by cross-checking `tables/attribution_summary.csv`
  (`T_pos_20` → `position = 21`). Therefore **1-based sgRNA position 18 = raw `Position` 17**,
  and PAM 21–23 = raw 20–22 (positions 22–23 are G in 100 % of the raw sequences).
* **Aggregation**: mean over samples within one experiment, then (in the analysis layer only)
  averaged over experiments per (kernel, cell line, position, channel).
* **Other model classes** (for completeness): `MLP_IG`, `TreeSHAP`, `Transformer_IG` are also
  stored as `mean(|·|)`; only `Linear_Coefficient` is signed (and 56/192 linear runs diverged).

## 3. Position 18 summary — requested substitutions

| Requested quantity | Status in current artifacts |
| :--- | :--- |
| `18: C→A` (signed) | **Unavailable** — no reference base, no sign |
| `18: C→G` (signed) | **Unavailable** |
| `18: C→T` (signed) | **Unavailable** |
| `18`: magnitude of toggling channel A/C/G/T | Available (below) |

What the artifacts *do* contain for position 18 (descriptive, all kernels & cell lines pooled):

{table(overall, "kernel")}

Reference-base composition at 1-based position 18 in the raw data ({n_seq} guides,
`data/source_data/*.csv`) — included because `18: C→A` is only *defined* for guides that carry C
at that position:

| Base at 1-based position 18 | guides | share |
| :--- | ---: | ---: |
{ref_rows}

Consequence: the requested substitution triple applies to the ≈{c_share:.0f} % of guides with **C**
at position 18. The ISM artifacts contain **no reference-base column at all**, so the C→X triple
cannot be reconstructed from them even in principle.

## 4. Model consistency (CNN kernel 3 / 5 / 7)

{table(by_kernel, "kernel")}

## 5. Cell-line consistency

{table(by_cell, "cell_line")}

`pooled` = runs trained on all cell lines together (`mixed_cnn_all_seed_*`).

Cell-line composition of the audited experiments (number of CNN experiments): {json.dumps(comp_cell)}; kernels: {json.dumps(comp_kernel)}.

## 5b. Is position 18 itself among the highest-magnitude positions?

Descriptive rank of position 18 within each experiment × channel (1 = largest `CNN_ISM`
among the 23 positions), pooled over all {int(overall["n"].max())} CNN experiments per channel:

| Channel toggle | mean rank | median rank | fraction with rank \u2264 3 |
| :--- | ---: | ---: | ---: |
{rank_table}

This is the only statement the ISM artifacts support about position 18: the model output is
sensitive to perturbing this position, and that sensitivity can be ranked across positions —
but it still carries **no direction**.

## 6. Experimental candidate ranking

A **directional** ranking (which of C→A / C→G / C→T would raise or lower efficiency) is
**not possible** from these artifacts. What can be ranked is the *position-level sensitivity*
to toggling each channel — this is explicitly **not** a mutation-direction prediction:

| Rank | Channel toggle at position 18 | Mean \\|Δŷ\\| (pooled) | Interpretation |
| ---: | :--- | ---: | :--- |
""" + "\n".join(
        f"| {i} | 18: toggle {r.mutated_base} | {r.mean_effect:.5f} | highest mean absolute prediction change for this channel toggle |"
        for i, r in enumerate(overall.sort_values("mean_effect", ascending=False).itertuples(), 1)
    ) + f"""

Caveat: a large `CNN_ISM` value for channel *c* at position 18 means "changing the indicator of
base *c* at this position moves the model output", averaged over samples in which *c* may or may
not have been the original base. It does **not** identify a substitution, and it does not tell us
whether the edited sequence would be predicted more or less efficient.

## 7. Can this be used for wet-lab design?

**C. No** (unsigned ISM branch):

> Current ISM results support positional importance but do not provide a directional mutation
> hypothesis. A wet-lab experiment should therefore be framed as testing **whether** position 18
> perturbation has an effect, rather than testing a specific predicted direction.

Additional constraint inherited from the audit: even the *magnitude* at (18, c) is produced by a
toggle operator without a stored reference base, so the experiment should not be described as
"testing the model-predicted C→A effect".

## 8. What we know / what ISM adds / what we still do not know

**What we know**
* Position 18 is repeatedly prioritized by four model classes (CNN/MLP/XGBoost/Transformer
  attention) and lies in the PAM-proximal region (17–20); PAM = 21–23 (NGG), verified from the
  raw sequences (positions 22–23 are G in 100 % of records).
* Measured efficiency differs by the nucleotide observed at position 18, with a cell-line
  dependent pattern (C−A: HCT116 +0.090, HeLa +0.092, HL60 +0.027, HEK293T −0.015).

**What ISM additionally tells us**
* The model output at position 18 is sensitive to single-channel perturbation in all four
  sequence channels (magnitudes in the tables above); pooling over {int(overall['n'].iloc[0])} experiments
  gives mean |Δŷ| between {overall['mean_effect'].min():.5f} and {overall['mean_effect'].max():.5f}.
* Nothing about direction: the stored quantity is an absolute value.

**What we still do not know**
* Whether any specific substitution at position 18 (C→A, C→G, C→T) increases or decreases
  editing efficiency — neither computationally (no signed ISM) nor experimentally (not yet tested).
* Whether the measured C−A differences reflect the position-18 base itself or co-varying sequence
  composition (e.g. position-18 T occurs mainly in HEK293T/HL60).

## 9. Recommended next steps

1. **Minimal signed ISM re-run (no retraining)**: use the existing checkpoints in
   `results/batch_20260909_full/summary/ultimate/ultimate_cnn{{33,53,73}}_model.pt` and a small
   audit script that, for the candidate sgRNAs only, performs a *true substitution*
   (set original base channel to 0 **and** target base channel to 1), keeps the reference base,
   and stores the signed Δŷ = ŷ(mutant) − ŷ(wild type) per sample. This is a few hundred forward
   passes, not a re-run of the 1 344 experiments.
2. **Freeze the hypothesis before the wet-lab work**: record the predicted sign and ranking of
   the three substitutions, so the experiment becomes a prospective test rather than post-hoc
   interpretation.
3. **Frame the current wet-lab proposal accordingly**: test *whether* position-18 perturbation
   changes measured editing efficiency (WT vs C→A/G/T with the rest of the sgRNA unchanged),
   without claiming a predicted direction.

## 10. Reproducibility

* Audit script: `docs/paper_analysis/position18_ism_audit.py` (read-only).
* Outputs: `results/analysis/position18_ISM_audit.csv`, `results/analysis/position18_ISM_raw_long.csv`.
* Inputs: {len(files)} × `results/batch_20260909_full/*/cnn_feature_importance.csv` (+ `*_info.txt` metadata).
* No file inside any experiment directory was created, modified or deleted.

## 11. Final status block

| Field | Value |
| :--- | :--- |
{status_table}
"""
    (OUT / "position18_ISM_audit.md").write_text(md, encoding="utf-8")

    print("experiments with ISM rows:", raw["experiment"].nunique())
    print("audit rows:", len(audit), "| csv:", OUT / "position18_ISM_audit.csv")
    print(overall[["mutated_base", "n", "mean_effect", "median_effect", "std"]].to_string(index=False))
    print("signed ISM available:", bool(audit["signed_effect_available"].any()))


if __name__ == "__main__":
    main()
