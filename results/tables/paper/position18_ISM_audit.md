# Position-18 ISM audit

> Scope: read-only audit of the **existing** ISM artifacts in `results/`.
> No retraining, no modification of the CNN / ISM code, no re-computation of the
> project's existing bootstrap / permutation / FDR statistics.
> All numbers below are **descriptive** summaries of stored values; they are not
> hypothesis tests.

## 1. ISM source files

| Item | Finding |
| :--- | :--- |
| Raw ISM artifacts | 576 files named `cnn_feature_importance.csv`, one per CNN experiment (e.g. `results/batch_20260909_full/all_cnn_all_heldout_hct116_kernel_3/cnn_feature_importance.csv`, `results/batch_20260909_full/all_cnn_all_heldout_hct116_kernel_5/cnn_feature_importance.csv`, `results/batch_20260909_full/all_cnn_all_heldout_hct116_kernel_7/cnn_feature_importance.csv`, `results/batch_20260909_full/single_hl60_cnn_sequence_rrbs_kernel_7/cnn_feature_importance.csv`) |
| Columns | `Feature, Position, Channel, CNN_IG, CNN_ISM, ISM_SNR` |
| Granularity | one row per (position × channel); **aggregated over the test samples of that experiment** (no per-sample rows are stored) |
| Numbering checked | sequence-only runs: 92 rows (23 × 4); environment runs: 184 rows (23 × 8, incl. CTCF/Dnase/H3K4me3/RRBS) |
| Per-sample ISM arrays | **none** (`results/**/*.npy` = 0); ISM is not persisted per sample |
| Code that produced them | `src/cnn/cnn.py:284-311 (compute_cnn_ism)` |
| Reusable trained checkpoints | 5 CNN checkpoints exist in `results/batch_20260909_full/summary/ultimate/` (`ultimate_cnn33/53/73_model.pt` + config) — usable for a **signed** re-audit without retraining |

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

| kernel | channel | n | mean \|Δŷ\| | median | std | 95% CI (descriptive) | max | fraction channel is top |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: |
| ALL | A | 576 | 0.02379 | 0.02456 | 0.01363 | [0.02268, 0.02490] | 0.05399 | 0.29 |
| ALL | C | 576 | 0.02699 | 0.01979 | 0.01808 | [0.02551, 0.02846] | 0.06819 | 0.44 |
| ALL | G | 576 | 0.01775 | 0.01733 | 0.00888 | [0.01703, 0.01848] | 0.04528 | 0.00 |
| ALL | T | 576 | 0.01734 | 0.01626 | 0.00767 | [0.01672, 0.01797] | 0.05123 | 0.27 |

Reference-base composition at 1-based position 18 in the raw data (18982 guides,
`data/source_data/*.csv`) — included because `18: C→A` is only *defined* for guides that carry C
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
| 3 | A | 192 | 0.01745 | 0.01749 | 0.00898 | [0.01618, 0.01872] | 0.03704 | 0.58 |
| 3 | C | 192 | 0.01352 | 0.01461 | 0.00528 | [0.01277, 0.01427] | 0.02447 | 0.10 |
| 3 | G | 192 | 0.01287 | 0.01313 | 0.00511 | [0.01214, 0.01359] | 0.02494 | 0.00 |
| 3 | T | 192 | 0.01323 | 0.01274 | 0.00374 | [0.01270, 0.01376] | 0.02282 | 0.32 |
| 5 | A | 192 | 0.02659 | 0.03052 | 0.01454 | [0.02454, 0.02865] | 0.05399 | 0.20 |
| 5 | C | 192 | 0.03075 | 0.03514 | 0.01774 | [0.02824, 0.03326] | 0.06819 | 0.47 |
| 5 | G | 192 | 0.01898 | 0.02033 | 0.00857 | [0.01777, 0.02020] | 0.04105 | 0.00 |
| 5 | T | 192 | 0.01919 | 0.01764 | 0.00762 | [0.01811, 0.02027] | 0.04215 | 0.33 |
| 7 | A | 192 | 0.02733 | 0.03197 | 0.01438 | [0.02529, 0.02936] | 0.05295 | 0.09 |
| 7 | C | 192 | 0.03669 | 0.04185 | 0.01871 | [0.03404, 0.03933] | 0.06667 | 0.76 |
| 7 | G | 192 | 0.02140 | 0.02230 | 0.00995 | [0.01999, 0.02281] | 0.04528 | 0.00 |
| 7 | T | 192 | 0.01961 | 0.01754 | 0.00891 | [0.01835, 0.02087] | 0.05123 | 0.15 |

## 5. Cell-line consistency

| cell_line | channel | n | mean \|Δŷ\| | median | std | 95% CI (descriptive) | max | fraction channel is top |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: |
| hct116 | A | 96 | 0.03163 | 0.02846 | 0.00991 | [0.02964, 0.03361] | 0.05295 | 0.65 |
| hct116 | C | 96 | 0.03113 | 0.03006 | 0.01393 | [0.02835, 0.03392] | 0.06583 | 0.35 |
| hct116 | G | 96 | 0.02243 | 0.02132 | 0.00633 | [0.02117, 0.02370] | 0.03797 | 0.00 |
| hct116 | T | 96 | 0.01862 | 0.01832 | 0.00340 | [0.01794, 0.01930] | 0.02652 | 0.00 |
| hek293t | A | 96 | 0.00959 | 0.00900 | 0.00273 | [0.00904, 0.01014] | 0.01678 | 0.02 |
| hek293t | C | 96 | 0.01165 | 0.00937 | 0.00525 | [0.01059, 0.01270] | 0.02789 | 0.33 |
| hek293t | G | 96 | 0.01037 | 0.00990 | 0.00360 | [0.00965, 0.01109] | 0.01845 | 0.00 |
| hek293t | T | 96 | 0.01138 | 0.01097 | 0.00342 | [0.01070, 0.01206] | 0.02364 | 0.65 |
| hela | A | 96 | 0.03788 | 0.03761 | 0.00724 | [0.03643, 0.03933] | 0.05333 | 0.48 |
| hela | C | 96 | 0.03808 | 0.04333 | 0.01497 | [0.03508, 0.04108] | 0.06491 | 0.52 |
| hela | G | 96 | 0.02031 | 0.01915 | 0.00432 | [0.01945, 0.02118] | 0.02993 | 0.00 |
| hela | T | 96 | 0.01769 | 0.01757 | 0.00283 | [0.01712, 0.01826] | 0.02587 | 0.00 |
| hl60 | A | 96 | 0.00689 | 0.00660 | 0.00201 | [0.00649, 0.00729] | 0.01260 | 0.02 |
| hl60 | C | 96 | 0.00735 | 0.00671 | 0.00290 | [0.00677, 0.00793] | 0.01758 | 0.04 |
| hl60 | G | 96 | 0.00689 | 0.00703 | 0.00180 | [0.00653, 0.00725] | 0.01249 | 0.00 |
| hl60 | T | 96 | 0.01125 | 0.01077 | 0.00261 | [0.01073, 0.01177] | 0.01790 | 0.94 |
| pooled | A | 192 | 0.02837 | 0.03044 | 0.00907 | [0.02709, 0.02966] | 0.05399 | 0.29 |
| pooled | C | 192 | 0.03685 | 0.04037 | 0.01666 | [0.03450, 0.03921] | 0.06819 | 0.70 |
| pooled | G | 192 | 0.02325 | 0.02284 | 0.00830 | [0.02207, 0.02442] | 0.04528 | 0.00 |
| pooled | T | 192 | 0.02256 | 0.02308 | 0.00966 | [0.02119, 0.02393] | 0.05123 | 0.01 |

`pooled` = runs trained on all cell lines together (`mixed_cnn_all_seed_*`).

Cell-line composition of the audited experiments (number of CNN experiments): {"hct116": 192, "hek293t": 192, "hela": 192, "hl60": 192, "pooled": 384}; kernels: {"3": 384, "5": 384, "7": 384}.

## 5b. Is position 18 itself among the highest-magnitude positions?

Descriptive rank of position 18 within each experiment × channel (1 = largest `CNN_ISM`
among the 23 positions), pooled over all 576 CNN experiments per channel:

| Channel toggle | mean rank | median rank | fraction with rank ≤ 3 |
| :--- | ---: | ---: | ---: |
| 18: A | 4.1 | 1 | 0.69 |
| 18: C | 4.6 | 2 | 0.63 |
| 18: G | 6.7 | 5 | 0.28 |
| 18: T | 9.5 | 7 | 0.27 |

This is the only statement the ISM artifacts support about position 18: the model output is
sensitive to perturbing this position, and that sensitivity can be ranked across positions —
but it still carries **no direction**.

## 6. Experimental candidate ranking

A **directional** ranking (which of C→A / C→G / C→T would raise or lower efficiency) is
**not possible** from these artifacts. What can be ranked is the *position-level sensitivity*
to toggling each channel — this is explicitly **not** a mutation-direction prediction:

| Rank | Channel toggle at position 18 | Mean \|Δŷ\| (pooled) | Interpretation |
| ---: | :--- | ---: | :--- |
| 1 | 18: toggle C | 0.02699 | highest mean absolute prediction change for this channel toggle |
| 2 | 18: toggle A | 0.02379 | highest mean absolute prediction change for this channel toggle |
| 3 | 18: toggle G | 0.01775 | highest mean absolute prediction change for this channel toggle |
| 4 | 18: toggle T | 0.01734 | highest mean absolute prediction change for this channel toggle |

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
  gives mean |Δŷ| between 0.01734 and 0.02699.
* Nothing about direction: the stored quantity is an absolute value.

**What we still do not know**
* Whether any specific substitution at position 18 (C→A, C→G, C→T) increases or decreases
  editing efficiency — neither computationally (no signed ISM) nor experimentally (not yet tested).
* Whether the measured C−A differences reflect the position-18 base itself or co-varying sequence
  composition (e.g. position-18 T occurs mainly in HEK293T/HL60).

## 9. Recommended next steps

1. **Minimal signed ISM re-run (no retraining)**: use the existing checkpoints in
   `results/batch_20260909_full/summary/ultimate/ultimate_cnn{33,53,73}_model.pt` and a small
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
* Inputs: 576 × `results/batch_20260909_full/*/cnn_feature_importance.csv` (+ `*_info.txt` metadata).
* No file inside any experiment directory was created, modified or deleted.

## 11. Final status block

| Field | Value |
| :--- | :--- |
| **Position 18 ISM status** | magnitude-only (**unsigned**); no signed per-substitution effect is stored |
| **C→A** | **unavailable** — no sign in the artifact, no reference base recorded |
| **C→G** | **unavailable** — no sign in the artifact, no reference base recorded |
| **C→T** | **unavailable** — no sign in the artifact, no reference base recorded |
| **Best experimental candidate** | no model-supported **directional** candidate (verdict C). Highest position-18 sensitivity is the *channel toggle* C (mean |Δŷ| = 0.02699); the strongest **observational** (not predicted) signal is C→A |
| **Can current ISM support a directional wet-lab hypothesis?** | **No** |
| **Recommended next computational step** | re-run ISM as a true substitution on the 5 existing checkpoints in `results/batch_20260909_full/summary/ultimate/` (keep reference base, store signed Δŷ = ŷ(mut) − ŷ(WT)); no retraining needed |
| **Recommended wet-lab hypothesis** | test-of-effect, not direction: *perturbing position 18 (WT base C → A) changes measured editing efficiency relative to the unmodified sgRNA*; direction left unpredicted |
