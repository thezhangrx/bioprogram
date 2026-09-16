# Position-18 ISM audit

> Scope: read-only audit of the **existing** ISM artifacts in `results/`.
> No retraining, no modification of the CNN / ISM code, no re-computation of the
> project's existing bootstrap / permutation / FDR statistics.
> All numbers below are **descriptive** summaries of stored values; they are not
> hypothesis tests.

## 1. ISM source files

| Item | Finding |
| :--- | :--- |
| Raw ISM artifacts | 576 files named `cnn_feature_importance.csv`, one per CNN experiment (e.g. `results/batches/ultimate_run/all_cnn_all_heldout_hct116_kernel_3/cnn_feature_importance.csv`, `results/batches/ultimate_run/all_cnn_all_heldout_hct116_kernel_5/cnn_feature_importance.csv`, `results/batches/ultimate_run/all_cnn_all_heldout_hct116_kernel_7/cnn_feature_importance.csv`, `results/batches/ultimate_run/single_hl60_cnn_sequence_rrbs_kernel_7/cnn_feature_importance.csv`) |
| Columns | `Feature, Position, Channel, CNN_IG, CNN_ISM, ISM_SNR` |
| Granularity | one row per (position × channel); **aggregated over the test samples of that experiment** (no per-sample rows are stored) |
| Numbering checked | sequence-only runs: 92 rows (23 × 4); environment runs: 184 rows (23 × 8, incl. CTCF/Dnase/H3K4me3/RRBS) |
| Per-sample ISM arrays | **none** (`results/**/*.npy` = 7); ISM is not persisted per sample |
| Code that produced them | `core/models/cnn/cnn.py (compute_cnn_ism)` |
| Reusable trained checkpoints | 5 CNN checkpoints exist in `results/batches/ultimate_run/summary/ultimate/` (`ultimate_cnn33/53/73_model.pt` + config) — usable for a **signed** re-audit without retraining |

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
  converts it to 1-based (`analysis/attribution/extractors.py::_parse_position_channel` adds +1),
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

| kernel | channel | n | mean \|Δŷ\| | median | std | 95% CI (descriptive) | max | fraction channel is top |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: |
| ALL | A | 576 | 0.02069 | 0.01920 | 0.01101 | [0.01979, 0.02158] | 0.06487 | 0.38 |
| ALL | C | 576 | 0.02266 | 0.01904 | 0.01343 | [0.02156, 0.02375] | 0.06313 | 0.48 |
| ALL | G | 576 | 0.01372 | 0.01283 | 0.00646 | [0.01319, 0.01424] | 0.04286 | 0.01 |
| ALL | T | 576 | 0.01459 | 0.01374 | 0.00604 | [0.01409, 0.01508] | 0.03738 | 0.14 |

Reference-base composition at 1-based position 18 in the raw data (18982 guides,
`data/raw/*.csv`) — included because `18: C→A` is only *defined* for guides that carry C
at that position:

| Base at 1-based position 18 | guides | share |
| :--- | ---: | ---: |
| A | 6567 | 34.6 % |
| C | 5668 | 29.9 % |
| G | 5110 | 26.9 % |
| T | 1637 | 8.6 % |

Consequence: the requested substitution triple applies to the ≈30 % of guides with **C**
at position 18. The ISM artifacts contain **no reference-base column at all**, so the C→X triple
cannot be reconstructed from them even in principle.

## 4. Model consistency (CNN kernel 3 / 5 / 7)

| kernel | channel | n | mean \|Δŷ\| | median | std | 95% CI (descriptive) | max | fraction channel is top |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: |
| 3 | A | 192 | 0.01490 | 0.01427 | 0.00715 | [0.01389, 0.01591] | 0.03333 | 0.67 |
| 3 | C | 192 | 0.01072 | 0.01075 | 0.00357 | [0.01022, 0.01123] | 0.01858 | 0.11 |
| 3 | G | 192 | 0.01049 | 0.01005 | 0.00389 | [0.00994, 0.01104] | 0.02260 | 0.01 |
| 3 | T | 192 | 0.01112 | 0.01086 | 0.00405 | [0.01054, 0.01169] | 0.02027 | 0.21 |
| 5 | A | 192 | 0.02520 | 0.02490 | 0.01317 | [0.02334, 0.02707] | 0.06487 | 0.36 |
| 5 | C | 192 | 0.02488 | 0.02609 | 0.00966 | [0.02352, 0.02625] | 0.04864 | 0.49 |
| 5 | G | 192 | 0.01625 | 0.01458 | 0.00787 | [0.01514, 0.01737] | 0.04286 | 0.00 |
| 5 | T | 192 | 0.01755 | 0.01667 | 0.00666 | [0.01661, 0.01849] | 0.03738 | 0.15 |
| 7 | A | 192 | 0.02195 | 0.02320 | 0.00919 | [0.02065, 0.02325] | 0.04620 | 0.10 |
| 7 | C | 192 | 0.03236 | 0.03491 | 0.01393 | [0.03039, 0.03433] | 0.06313 | 0.83 |
| 7 | G | 192 | 0.01441 | 0.01368 | 0.00558 | [0.01362, 0.01519] | 0.03552 | 0.02 |
| 7 | T | 192 | 0.01509 | 0.01476 | 0.00529 | [0.01434, 0.01584] | 0.02744 | 0.05 |

## 5. Cell-line consistency

| cell_line | channel | n | mean \|Δŷ\| | median | std | 95% CI (descriptive) | max | fraction channel is top |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: |
| hct116 | A | 96 | 0.02348 | 0.02337 | 0.00684 | [0.02211, 0.02485] | 0.05463 | 0.50 |
| hct116 | C | 96 | 0.02525 | 0.02643 | 0.01275 | [0.02269, 0.02780] | 0.05841 | 0.50 |
| hct116 | G | 96 | 0.01464 | 0.01381 | 0.00554 | [0.01353, 0.01574] | 0.03578 | 0.00 |
| hct116 | T | 96 | 0.01661 | 0.01589 | 0.00529 | [0.01555, 0.01767] | 0.02932 | 0.00 |
| hek293t | A | 96 | 0.01660 | 0.01454 | 0.00800 | [0.01500, 0.01820] | 0.03576 | 0.17 |
| hek293t | C | 96 | 0.01866 | 0.01330 | 0.01167 | [0.01633, 0.02100] | 0.04623 | 0.40 |
| hek293t | G | 96 | 0.01257 | 0.01248 | 0.00422 | [0.01172, 0.01341] | 0.02616 | 0.01 |
| hek293t | T | 96 | 0.01679 | 0.01636 | 0.00546 | [0.01570, 0.01789] | 0.03106 | 0.43 |
| hela | A | 96 | 0.02371 | 0.01825 | 0.01829 | [0.02005, 0.02736] | 0.06487 | 0.61 |
| hela | C | 96 | 0.02006 | 0.01252 | 0.01659 | [0.01674, 0.02338] | 0.06313 | 0.32 |
| hela | G | 96 | 0.01565 | 0.01355 | 0.01177 | [0.01329, 0.01800] | 0.04286 | 0.04 |
| hela | T | 96 | 0.01252 | 0.01222 | 0.00767 | [0.01098, 0.01405] | 0.03738 | 0.02 |
| hl60 | A | 96 | 0.01389 | 0.01178 | 0.00608 | [0.01268, 0.01511] | 0.02820 | 0.26 |
| hl60 | C | 96 | 0.01588 | 0.01573 | 0.00726 | [0.01443, 0.01734] | 0.03936 | 0.38 |
| hl60 | G | 96 | 0.01165 | 0.01124 | 0.00366 | [0.01091, 0.01238] | 0.02277 | 0.00 |
| hl60 | T | 96 | 0.01457 | 0.01381 | 0.00511 | [0.01355, 0.01559] | 0.03177 | 0.36 |
| pooled | A | 192 | 0.02322 | 0.02308 | 0.00886 | [0.02196, 0.02447] | 0.05020 | 0.36 |
| pooled | C | 192 | 0.02804 | 0.03028 | 0.01281 | [0.02623, 0.02985] | 0.05851 | 0.64 |
| pooled | G | 192 | 0.01391 | 0.01342 | 0.00456 | [0.01326, 0.01455] | 0.02842 | 0.00 |
| pooled | T | 192 | 0.01351 | 0.01200 | 0.00558 | [0.01272, 0.01430] | 0.03032 | 0.00 |

`pooled` = runs trained on all cell lines together (`mixed_cnn_all_seed_*`).

Cell-line composition of the audited experiments (number of CNN experiments): {"hct116": 192, "hek293t": 192, "hela": 192, "hl60": 192, "pooled": 384}; kernels: {"3": 384, "5": 384, "7": 384}.

## 5b. Is position 18 itself among the highest-magnitude positions?

Descriptive rank of position 18 within each experiment × channel (1 = largest `CNN_ISM`
among the 23 positions), pooled over all 576 CNN experiments per channel:

| Channel toggle | mean rank | median rank | fraction with rank ≤ 3 |
| :--- | ---: | ---: | ---: |
| 18: A | 3.4 | 1 | 0.79 |
| 18: C | 4.6 | 1 | 0.69 |
| 18: G | 8.0 | 6 | 0.18 |
| 18: T | 9.0 | 6 | 0.26 |

This is the only statement the ISM artifacts support about position 18: the model output is
sensitive to perturbing this position, and that sensitivity can be ranked across positions —
but it still carries **no direction**.

## 6. Experimental candidate ranking

A **directional** ranking (which of C→A / C→G / C→T would raise or lower efficiency) is
**not possible** from these artifacts. What can be ranked is the *position-level sensitivity*
to toggling each channel — this is explicitly **not** a mutation-direction prediction:

| Rank | Channel toggle at position 18 | Mean \|Δŷ\| (pooled) | Interpretation |
| ---: | :--- | ---: | :--- |
| 1 | 18: toggle C | 0.02266 | highest mean absolute prediction change for this channel toggle |
| 2 | 18: toggle A | 0.02069 | highest mean absolute prediction change for this channel toggle |
| 3 | 18: toggle T | 0.01459 | highest mean absolute prediction change for this channel toggle |
| 4 | 18: toggle G | 0.01372 | highest mean absolute prediction change for this channel toggle |

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
  sequence channels (magnitudes in the tables above); pooling over 576 experiments
  gives mean |Δŷ| between 0.01372 and 0.02266.
* Nothing about direction: the stored quantity is an absolute value.

**What we still do not know**
* Whether any specific substitution at position 18 (C→A, C→G, C→T) increases or decreases
  editing efficiency — neither computationally (no signed ISM) nor experimentally (not yet tested).
* Whether the measured C−A differences reflect the position-18 base itself or co-varying sequence
  composition (e.g. position-18 T occurs mainly in HEK293T/HL60).

## 9. Recommended next steps

1. **Minimal signed ISM re-run (no retraining)**: use the existing checkpoints in
   `results/batches/ultimate_run/summary/ultimate/ultimate_cnn{33,53,73}_model.pt` and a small
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

* Audit script: `analysis/reporting/paper_analysis/position18_ism_audit.py` (read-only).
* Outputs: `results/tables/paper/position18_ISM_audit.csv`, `results/tables/paper/position18_ISM_raw_long.csv`.
* Inputs: 576 × `results/batches/ultimate_run/*/cnn_feature_importance.csv` (+ `*_info.txt` metadata).
* No file inside any experiment directory was created, modified or deleted.

## 11. Final status block

| Field | Value |
| :--- | :--- |
| **Position 18 ISM status** | magnitude-only (**unsigned**); no signed per-substitution effect is stored |
| **C→A** | **unavailable** — no sign in the artifact, no reference base recorded |
| **C→G** | **unavailable** — no sign in the artifact, no reference base recorded |
| **C→T** | **unavailable** — no sign in the artifact, no reference base recorded |
| **Best experimental candidate** | no model-supported **directional** candidate (verdict C). Highest position-18 sensitivity is the *channel toggle* C (mean |Δŷ| = 0.02266); the strongest **observational** (not predicted) signal is C→A |
| **Can current ISM support a directional wet-lab hypothesis?** | **No** |
| **Recommended next computational step** | re-run ISM as a true substitution on the 5 existing checkpoints in `results/batches/ultimate_run/summary/ultimate/` (keep reference base, store signed Δŷ = ŷ(mut) − ŷ(WT)); no retraining needed |
| **Recommended wet-lab hypothesis** | test-of-effect, not direction: *perturbing position 18 (WT base C → A) changes measured editing efficiency relative to the unmodified sgRNA*; direction left unpredicted |
