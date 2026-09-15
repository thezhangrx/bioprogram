# Position-18 signed substitution ISM — C>A, C>G, C>T

> Reference base = the base actually present at position 18 (guides with **C**); operator = a true
> one-hot substitution (C channel off, target channel on); Δ = raw model output (mutant) − (WT).
> **No retraining**: the 7 pooled *ultimate* models and 12 cell-line-specific CNN checkpoints that
> already exist in the repo were re-used unchanged. Intervals are percentile bootstrap CIs
> (10,000 resamples, seed 42) over the measured sample set — a descriptive interval for
> these data, not a population inference.

## 0. Data and correctness checks

| Item | Value |
| :--- | :--- |
| Measured guides used | 16749 (4 cell lines: hct116, hek293t, hela, hl60) |
| Guides with position 18 = C (analysis set) | **5080** (30.3 %) |
| Tensor ↔ metadata sequence agreement | 1.0000 |
| PAM positions 22–23 = GG | 1.000 |
| Position-18 base (metadata) | {'A': 6009, 'C': 5080, 'G': 4576, 'T': 1084} |
| Models re-used | 7 pooled (Linear, XGBoost, MLP, CNN k=3/5/7, Transformer) + 12 cell-line-specific CNNs |

## 1. Pooled models — signed Δ per substitution

| model | kernel | cell line | substitution | n | mean Δ | median Δ | 95% bootstrap CI | P(Δ>0) | direction | CI excludes 0 |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | :--- | ---: | :--- | :--- |
| CNN(k=3) | 3 | ALL | C>A | 5080 | -0.02457 | -0.01948 | [-0.02540, -0.02373] | 0.218 | decrease | yes |
| CNN(k=3) | 3 | ALL | C>G | 5080 | -0.01912 | -0.01406 | [-0.01987, -0.01837] | 0.240 | decrease | yes |
| CNN(k=3) | 3 | ALL | C>T | 5080 | -0.01497 | -0.01032 | [-0.01569, -0.01424] | 0.315 | decrease | yes |
| CNN(k=5) | 5 | ALL | C>A | 5080 | -0.05729 | -0.04611 | [-0.05864, -0.05597] | 0.064 | decrease | yes |
| CNN(k=5) | 5 | ALL | C>G | 5080 | -0.03892 | -0.02821 | [-0.04023, -0.03765] | 0.195 | decrease | yes |
| CNN(k=5) | 5 | ALL | C>T | 5080 | -0.05027 | -0.04061 | [-0.05159, -0.04897] | 0.099 | decrease | yes |
| CNN(k=7) | 7 | ALL | C>A | 5080 | -0.07850 | -0.06430 | [-0.08059, -0.07643] | 0.115 | decrease | yes |
| CNN(k=7) | 7 | ALL | C>G | 5080 | -0.05502 | -0.04340 | [-0.05696, -0.05309] | 0.197 | decrease | yes |
| CNN(k=7) | 7 | ALL | C>T | 5080 | -0.07798 | -0.06527 | [-0.08007, -0.07593] | 0.141 | decrease | yes |
| Linear | - | ALL | C>A | 5080 | -0.07534 | -0.07534 | [-0.07534, -0.07534] | 0.000 | decrease | yes |
| Linear | - | ALL | C>G | 5080 | -0.05796 | -0.05796 | [-0.05796, -0.05796] | 0.000 | decrease | yes |
| Linear | - | ALL | C>T | 5080 | -0.05653 | -0.05653 | [-0.05653, -0.05653] | 0.000 | decrease | yes |
| MLP | - | ALL | C>A | 5080 | -0.08169 | -0.07948 | [-0.08320, -0.08019] | 0.060 | decrease | yes |
| MLP | - | ALL | C>G | 5080 | -0.06438 | -0.05943 | [-0.06577, -0.06298] | 0.078 | decrease | yes |
| MLP | - | ALL | C>T | 5080 | -0.07014 | -0.06529 | [-0.07154, -0.06867] | 0.066 | decrease | yes |
| Transformer | - | ALL | C>A | 5080 | -0.08038 | -0.08584 | [-0.08124, -0.07955] | 0.000 | decrease | yes |
| Transformer | - | ALL | C>G | 5080 | -0.05632 | -0.05751 | [-0.05699, -0.05563] | 0.003 | decrease | yes |
| Transformer | - | ALL | C>T | 5080 | -0.07092 | -0.07547 | [-0.07176, -0.07007] | 0.018 | decrease | yes |
| XGBoost | - | ALL | C>A | 5080 | -0.07322 | -0.07340 | [-0.07412, -0.07233] | 0.015 | decrease | yes |
| XGBoost | - | ALL | C>G | 5080 | -0.05660 | -0.05544 | [-0.05742, -0.05578] | 0.031 | decrease | yes |
| XGBoost | - | ALL | C>T | 5080 | -0.05921 | -0.05931 | [-0.05995, -0.05845] | 0.022 | decrease | yes |

## 2. Cell-line strata (pooled models, same guides split by cell line)

| model | kernel | cell line | substitution | n | mean Δ | median Δ | 95% bootstrap CI | P(Δ>0) | direction | CI excludes 0 |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | :--- | ---: | :--- | :--- |
| CNN(k=3) | 3 | hct116 | C>A | 1377 | -0.02979 | -0.02549 | [-0.03143, -0.02823] | 0.150 | decrease | yes |
| CNN(k=3) | 3 | hct116 | C>G | 1377 | -0.02210 | -0.01714 | [-0.02350, -0.02069] | 0.203 | decrease | yes |
| CNN(k=3) | 3 | hct116 | C>T | 1377 | -0.01764 | -0.01263 | [-0.01910, -0.01621] | 0.283 | decrease | yes |
| CNN(k=3) | 3 | hek293t | C>A | 618 | -0.01033 | -0.00448 | [-0.01241, -0.00832] | 0.406 | decrease | yes |
| CNN(k=3) | 3 | hek293t | C>G | 618 | -0.00948 | -0.00564 | [-0.01133, -0.00767] | 0.359 | decrease | yes |
| CNN(k=3) | 3 | hek293t | C>T | 618 | -0.00924 | -0.00547 | [-0.01102, -0.00750] | 0.390 | decrease | yes |
| CNN(k=3) | 3 | hela | C>A | 2483 | -0.02822 | -0.02463 | [-0.02936, -0.02705] | 0.170 | decrease | yes |
| CNN(k=3) | 3 | hela | C>G | 2483 | -0.02148 | -0.01698 | [-0.02257, -0.02044] | 0.211 | decrease | yes |
| CNN(k=3) | 3 | hela | C>T | 2483 | -0.01570 | -0.01102 | [-0.01681, -0.01463] | 0.310 | decrease | yes |
| CNN(k=3) | 3 | hl60 | C>A | 602 | -0.01224 | -0.00761 | [-0.01440, -0.01006] | 0.380 | decrease | yes |
| CNN(k=3) | 3 | hl60 | C>G | 602 | -0.01245 | -0.00751 | [-0.01454, -0.01042] | 0.319 | decrease | yes |
| CNN(k=3) | 3 | hl60 | C>T | 602 | -0.01178 | -0.00765 | [-0.01373, -0.00979] | 0.332 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>A | 1377 | -0.06447 | -0.05640 | [-0.06714, -0.06185] | 0.046 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>G | 1377 | -0.04377 | -0.03421 | [-0.04641, -0.04117] | 0.170 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>T | 1377 | -0.05662 | -0.04674 | [-0.05915, -0.05412] | 0.065 | decrease | yes |
| CNN(k=5) | 5 | hek293t | C>A | 618 | -0.03230 | -0.02169 | [-0.03533, -0.02935] | 0.129 | decrease | yes |
| CNN(k=5) | 5 | hek293t | C>G | 618 | -0.01939 | -0.01125 | [-0.02231, -0.01656] | 0.320 | decrease | yes |
| CNN(k=5) | 5 | hek293t | C>T | 618 | -0.02670 | -0.01678 | [-0.02965, -0.02393] | 0.227 | decrease | yes |
| CNN(k=5) | 5 | hela | C>A | 2483 | -0.06344 | -0.05441 | [-0.06537, -0.06151] | 0.047 | decrease | yes |
| CNN(k=5) | 5 | hela | C>G | 2483 | -0.04407 | -0.03436 | [-0.04603, -0.04212] | 0.166 | decrease | yes |
| CNN(k=5) | 5 | hela | C>T | 2483 | -0.05582 | -0.04648 | [-0.05772, -0.05396] | 0.069 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>A | 602 | -0.04116 | -0.03007 | [-0.04454, -0.03781] | 0.110 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>G | 602 | -0.02665 | -0.01781 | [-0.02982, -0.02350] | 0.248 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>T | 602 | -0.03706 | -0.02631 | [-0.04035, -0.03379] | 0.168 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>A | 1377 | -0.08863 | -0.07631 | [-0.09257, -0.08464] | 0.083 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>G | 1377 | -0.06239 | -0.05068 | [-0.06618, -0.05863] | 0.157 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>T | 1377 | -0.08930 | -0.07682 | [-0.09330, -0.08533] | 0.083 | decrease | yes |
| CNN(k=7) | 7 | hek293t | C>A | 618 | -0.03826 | -0.02426 | [-0.04243, -0.03420] | 0.225 | decrease | yes |
| CNN(k=7) | 7 | hek293t | C>G | 618 | -0.01793 | -0.00971 | [-0.02189, -0.01392] | 0.385 | decrease | yes |
| CNN(k=7) | 7 | hek293t | C>T | 618 | -0.02979 | -0.01697 | [-0.03448, -0.02519] | 0.385 | decrease | yes |
| CNN(k=7) | 7 | hela | C>A | 2483 | -0.08928 | -0.07724 | [-0.09233, -0.08630] | 0.089 | decrease | yes |
| CNN(k=7) | 7 | hela | C>G | 2483 | -0.06488 | -0.05421 | [-0.06773, -0.06208] | 0.152 | decrease | yes |
| CNN(k=7) | 7 | hela | C>T | 2483 | -0.08967 | -0.07820 | [-0.09263, -0.08668] | 0.091 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>A | 602 | -0.05216 | -0.03773 | [-0.05742, -0.04699] | 0.183 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>G | 602 | -0.03553 | -0.02399 | [-0.04028, -0.03095] | 0.286 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>T | 602 | -0.05334 | -0.04163 | [-0.05859, -0.04822] | 0.228 | decrease | yes |
| Linear | - | hct116 | C>A | 1377 | -0.07534 | -0.07534 | [-0.07534, -0.07534] | 0.000 | decrease | yes |
| Linear | - | hct116 | C>G | 1377 | -0.05796 | -0.05796 | [-0.05796, -0.05796] | 0.000 | decrease | yes |
| Linear | - | hct116 | C>T | 1377 | -0.05653 | -0.05653 | [-0.05653, -0.05653] | 0.000 | decrease | yes |
| Linear | - | hek293t | C>A | 618 | -0.07534 | -0.07534 | [-0.07534, -0.07534] | 0.000 | decrease | yes |
| Linear | - | hek293t | C>G | 618 | -0.05796 | -0.05796 | [-0.05796, -0.05796] | 0.000 | decrease | yes |
| Linear | - | hek293t | C>T | 618 | -0.05653 | -0.05653 | [-0.05653, -0.05653] | 0.000 | decrease | yes |
| Linear | - | hela | C>A | 2483 | -0.07534 | -0.07534 | [-0.07534, -0.07534] | 0.000 | decrease | yes |
| Linear | - | hela | C>G | 2483 | -0.05796 | -0.05796 | [-0.05796, -0.05796] | 0.000 | decrease | yes |
| Linear | - | hela | C>T | 2483 | -0.05653 | -0.05653 | [-0.05653, -0.05653] | 0.000 | decrease | yes |
| Linear | - | hl60 | C>A | 602 | -0.07534 | -0.07534 | [-0.07534, -0.07534] | 0.000 | decrease | yes |
| Linear | - | hl60 | C>G | 602 | -0.05796 | -0.05796 | [-0.05796, -0.05796] | 0.000 | decrease | yes |
| Linear | - | hl60 | C>T | 602 | -0.05653 | -0.05653 | [-0.05653, -0.05653] | 0.000 | decrease | yes |
| MLP | - | hct116 | C>A | 1377 | -0.08931 | -0.08714 | [-0.09220, -0.08658] | 0.037 | decrease | yes |
| MLP | - | hct116 | C>G | 1377 | -0.06983 | -0.06437 | [-0.07242, -0.06729] | 0.049 | decrease | yes |
| MLP | - | hct116 | C>T | 1377 | -0.07891 | -0.07445 | [-0.08160, -0.07631] | 0.027 | decrease | yes |
| MLP | - | hek293t | C>A | 618 | -0.05128 | -0.04565 | [-0.05519, -0.04741] | 0.150 | decrease | yes |
| MLP | - | hek293t | C>G | 618 | -0.03864 | -0.03634 | [-0.04208, -0.03517] | 0.210 | decrease | yes |
| MLP | - | hek293t | C>T | 618 | -0.03891 | -0.03153 | [-0.04263, -0.03524] | 0.206 | decrease | yes |
| MLP | - | hela | C>A | 2483 | -0.09099 | -0.08852 | [-0.09312, -0.08895] | 0.035 | decrease | yes |
| MLP | - | hela | C>G | 2483 | -0.07210 | -0.06616 | [-0.07402, -0.07018] | 0.044 | decrease | yes |
| MLP | - | hela | C>T | 2483 | -0.07905 | -0.07382 | [-0.08106, -0.07709] | 0.028 | decrease | yes |
| MLP | - | hl60 | C>A | 602 | -0.05715 | -0.05212 | [-0.06134, -0.05315] | 0.118 | decrease | yes |
| MLP | - | hl60 | C>G | 602 | -0.04647 | -0.03930 | [-0.05037, -0.04261] | 0.143 | decrease | yes |
| MLP | - | hl60 | C>T | 602 | -0.04537 | -0.04034 | [-0.04922, -0.04152] | 0.171 | decrease | yes |
| Transformer | - | hct116 | C>A | 1377 | -0.08921 | -0.09017 | [-0.09038, -0.08805] | 0.000 | decrease | yes |
| Transformer | - | hct116 | C>G | 1377 | -0.06134 | -0.06086 | [-0.06243, -0.06025] | 0.000 | decrease | yes |
| Transformer | - | hct116 | C>T | 1377 | -0.07975 | -0.07952 | [-0.08083, -0.07863] | 0.000 | decrease | yes |
| Transformer | - | hek293t | C>A | 618 | -0.05147 | -0.04156 | [-0.05462, -0.04840] | 0.000 | decrease | yes |
| Transformer | - | hek293t | C>G | 618 | -0.03821 | -0.03356 | [-0.04041, -0.03605] | 0.013 | decrease | yes |
| Transformer | - | hek293t | C>T | 618 | -0.04159 | -0.02508 | [-0.04476, -0.03853] | 0.076 | decrease | yes |
| Transformer | - | hela | C>A | 2483 | -0.08911 | -0.08987 | [-0.08998, -0.08823] | 0.000 | decrease | yes |
| Transformer | - | hela | C>G | 2483 | -0.06182 | -0.06169 | [-0.06264, -0.06102] | 0.000 | decrease | yes |
| Transformer | - | hela | C>T | 2483 | -0.07960 | -0.07891 | [-0.08043, -0.07875] | 0.000 | decrease | yes |
| Transformer | - | hl60 | C>A | 602 | -0.05388 | -0.04951 | [-0.05699, -0.05081] | 0.000 | decrease | yes |
| Transformer | - | hl60 | C>G | 602 | -0.04075 | -0.03817 | [-0.04308, -0.03853] | 0.015 | decrease | yes |
| Transformer | - | hl60 | C>T | 602 | -0.04508 | -0.03768 | [-0.04829, -0.04187] | 0.071 | decrease | yes |
| XGBoost | - | hct116 | C>A | 1377 | -0.07955 | -0.07930 | [-0.08107, -0.07801] | 0.000 | decrease | yes |
| XGBoost | - | hct116 | C>G | 1377 | -0.06205 | -0.05943 | [-0.06349, -0.06068] | 0.001 | decrease | yes |
| XGBoost | - | hct116 | C>T | 1377 | -0.06488 | -0.06423 | [-0.06610, -0.06366] | 0.000 | decrease | yes |
| XGBoost | - | hek293t | C>A | 618 | -0.05180 | -0.04851 | [-0.05471, -0.04894] | 0.078 | decrease | yes |
| XGBoost | - | hek293t | C>G | 618 | -0.03684 | -0.03510 | [-0.03952, -0.03424] | 0.136 | decrease | yes |
| XGBoost | - | hek293t | C>T | 618 | -0.04040 | -0.03825 | [-0.04277, -0.03797] | 0.094 | decrease | yes |
| XGBoost | - | hela | C>A | 2483 | -0.07971 | -0.07987 | [-0.08087, -0.07857] | 0.000 | decrease | yes |
| XGBoost | - | hela | C>G | 2483 | -0.06267 | -0.06014 | [-0.06371, -0.06162] | 0.001 | decrease | yes |
| XGBoost | - | hela | C>T | 2483 | -0.06497 | -0.06422 | [-0.06588, -0.06405] | 0.001 | decrease | yes |
| XGBoost | - | hl60 | C>A | 602 | -0.05398 | -0.05293 | [-0.05665, -0.05138] | 0.045 | decrease | yes |
| XGBoost | - | hl60 | C>G | 602 | -0.03940 | -0.03765 | [-0.04195, -0.03687] | 0.111 | decrease | yes |
| XGBoost | - | hl60 | C>T | 602 | -0.04176 | -0.04173 | [-0.04408, -0.03940] | 0.086 | decrease | yes |

## 3. Cell-line-specific CNN checkpoints (model trained on that cell line only)

| model | kernel | cell line | substitution | n | mean Δ | median Δ | 95% bootstrap CI | P(Δ>0) | direction | CI excludes 0 |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | :--- | ---: | :--- | :--- |
| CNN(k=3) | 3 | hct116 | C>A | 1377 | -0.03186 | -0.03136 | [-0.03364, -0.03009] | 0.180 | decrease | yes |
| CNN(k=3) | 3 | hct116 | C>G | 1377 | -0.02567 | -0.02114 | [-0.02740, -0.02399] | 0.220 | decrease | yes |
| CNN(k=3) | 3 | hct116 | C>T | 1377 | -0.01359 | -0.01054 | [-0.01538, -0.01175] | 0.358 | decrease | yes |
| CNN(k=3) | 3 | hek293t | C>A | 618 | -0.00421 | -0.00496 | [-0.00574, -0.00260] | 0.369 | decrease | yes |
| CNN(k=3) | 3 | hek293t | C>G | 618 | +0.00089 | +0.00136 | [-0.00055, +0.00225] | 0.537 | increase | no |
| CNN(k=3) | 3 | hek293t | C>T | 618 | +0.00706 | +0.00311 | [+0.00520, +0.00890] | 0.589 | increase | yes |
| CNN(k=3) | 3 | hela | C>A | 2483 | -0.03393 | -0.03168 | [-0.03509, -0.03275] | 0.114 | decrease | yes |
| CNN(k=3) | 3 | hela | C>G | 2483 | -0.02495 | -0.02132 | [-0.02607, -0.02381] | 0.194 | decrease | yes |
| CNN(k=3) | 3 | hela | C>T | 2483 | -0.01035 | -0.01050 | [-0.01122, -0.00946] | 0.299 | decrease | yes |
| CNN(k=3) | 3 | hl60 | C>A | 602 | +0.00014 | +0.00002 | [-0.00057, +0.00084] | 0.502 | increase | no |
| CNN(k=3) | 3 | hl60 | C>G | 602 | -0.00003 | -0.00019 | [-0.00080, +0.00076] | 0.495 | decrease | no |
| CNN(k=3) | 3 | hl60 | C>T | 602 | -0.00850 | -0.00928 | [-0.00933, -0.00767] | 0.208 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>A | 1377 | -0.09290 | -0.09291 | [-0.09485, -0.09096] | 0.002 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>G | 1377 | -0.05774 | -0.05410 | [-0.05988, -0.05556] | 0.060 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>T | 1377 | -0.03948 | -0.03700 | [-0.04145, -0.03749] | 0.142 | decrease | yes |
| CNN(k=5) | 5 | hek293t | C>A | 618 | -0.00333 | -0.00300 | [-0.00414, -0.00254] | 0.393 | decrease | yes |
| CNN(k=5) | 5 | hek293t | C>G | 618 | +0.00294 | +0.00296 | [+0.00226, +0.00363] | 0.639 | increase | yes |
| CNN(k=5) | 5 | hek293t | C>T | 618 | +0.00556 | +0.00591 | [+0.00491, +0.00619] | 0.751 | increase | yes |
| CNN(k=5) | 5 | hela | C>A | 2483 | -0.07152 | -0.07017 | [-0.07251, -0.07051] | 0.000 | decrease | yes |
| CNN(k=5) | 5 | hela | C>G | 2483 | -0.04328 | -0.04169 | [-0.04416, -0.04241] | 0.014 | decrease | yes |
| CNN(k=5) | 5 | hela | C>T | 2483 | -0.03848 | -0.03606 | [-0.03941, -0.03757] | 0.031 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>A | 602 | -0.00537 | -0.00538 | [-0.00621, -0.00453] | 0.289 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>G | 602 | -0.00074 | -0.00027 | [-0.00163, +0.00019] | 0.490 | decrease | no |
| CNN(k=5) | 5 | hl60 | C>T | 602 | -0.01313 | -0.01361 | [-0.01410, -0.01216] | 0.163 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>A | 1377 | -0.09296 | -0.09255 | [-0.09467, -0.09127] | 0.000 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>G | 1377 | -0.05970 | -0.05829 | [-0.06130, -0.05816] | 0.011 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>T | 1377 | -0.04915 | -0.04738 | [-0.05060, -0.04770] | 0.025 | decrease | yes |
| CNN(k=7) | 7 | hek293t | C>A | 618 | +0.00035 | -0.00188 | [-0.00126, +0.00195] | 0.474 | increase | no |
| CNN(k=7) | 7 | hek293t | C>G | 618 | +0.00252 | +0.00219 | [+0.00122, +0.00377] | 0.547 | increase | yes |
| CNN(k=7) | 7 | hek293t | C>T | 618 | +0.02028 | +0.01616 | [+0.01832, +0.02223] | 0.772 | increase | yes |
| CNN(k=7) | 7 | hela | C>A | 2483 | -0.11033 | -0.10954 | [-0.11223, -0.10845] | 0.002 | decrease | yes |
| CNN(k=7) | 7 | hela | C>G | 2483 | -0.07475 | -0.06827 | [-0.07653, -0.07298] | 0.019 | decrease | yes |
| CNN(k=7) | 7 | hela | C>T | 2483 | -0.05267 | -0.05046 | [-0.05419, -0.05114] | 0.080 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>A | 602 | -0.00962 | -0.00936 | [-0.01048, -0.00877] | 0.176 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>G | 602 | +0.00012 | +0.00055 | [-0.00094, +0.00115] | 0.518 | increase | no |
| CNN(k=7) | 7 | hl60 | C>T | 602 | -0.02390 | -0.02432 | [-0.02510, -0.02270] | 0.065 | decrease | yes |

## 4. Stability across configurations

Every row below is one (model × kernel × cell line) configuration (the pooled models are also
counted once per cell-line stratum); "same sign" = share of configurations agreeing with the
majority direction.

| substitution | configurations | same sign | share | mean of means | configs with CI excluding 0 |
| :--- | ---: | ---: | ---: | ---: | ---: |
| C>A | 40 | decrease | 0.95 | -0.05362 | 38 |
| C>G | 40 | decrease | 0.90 | -0.03806 | 36 |
| C>T | 40 | decrease | 0.93 | -0.04089 | 40 |

Per-sample sign agreement between substitutions (pooled models, n=35560 sample×model rows):
{"A vs G": 0.903, "A vs T": 0.919, "G vs T": 0.9}

## 5. Do the model predictions agree with the measured efficacy differences?

Measured per-base efficacy comes from `docs/paper_analysis/position18_efficacy_by_base.csv`
(observational data, same guides). "C better" = predicted efficacy(C) > efficacy(X) for the model,
and measured efficacy(C) > efficacy(X) for the data.

| substitution | cell line | model mean Δ | measured C − X | model direction | measured direction | agree | n(C) | n(X) |
| :--- | :--- | ---: | ---: | :--- | :--- | :--- | ---: | ---: |
| C>A | hct116 | -0.07376 | +0.090 | C better | C better | yes | 1377 | 1652 |
| C>A | hek293t | -0.04440 | -0.015 | C better | X better | NO | 618 | 584 |
| C>A | hela | -0.07373 | +0.092 | C better | C better | yes | 2483 | 3278 |
| C>A | hl60 | -0.04942 | +0.027 | C better | C better | yes | 602 | 495 |
| C>G | hct116 | -0.05421 | +0.070 | C better | C better | yes | 1377 | 1210 |
| C>G | hek293t | -0.03121 | -0.016 | C better | X better | NO | 618 | 554 |
| C>G | hela | -0.05500 | +0.072 | C better | C better | yes | 2483 | 2340 |
| C>G | hl60 | -0.03703 | +0.029 | C better | C better | yes | 602 | 472 |
| C>T | hek293t | -0.03474 | -0.026 | C better | X better | NO | 618 | 577 |
| C>T | hl60 | -0.04156 | +0.043 | C better | C better | yes | 602 | 507 |

Agreement rate: **70.00%** of the (substitution × cell line) cells
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
