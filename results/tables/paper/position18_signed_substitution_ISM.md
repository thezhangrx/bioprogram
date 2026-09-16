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
| CNN(k=3) | 3 | ALL | C>A | 5080 | -0.02786 | -0.02484 | [-0.02851, -0.02721] | 0.096 | decrease | yes |
| CNN(k=3) | 3 | ALL | C>G | 5080 | -0.01818 | -0.01483 | [-0.01881, -0.01755] | 0.187 | decrease | yes |
| CNN(k=3) | 3 | ALL | C>T | 5080 | -0.01457 | -0.01055 | [-0.01516, -0.01396] | 0.245 | decrease | yes |
| CNN(k=5) | 5 | ALL | C>A | 5080 | -0.05744 | -0.04744 | [-0.05863, -0.05629] | 0.017 | decrease | yes |
| CNN(k=5) | 5 | ALL | C>G | 5080 | -0.04311 | -0.03334 | [-0.04423, -0.04200] | 0.078 | decrease | yes |
| CNN(k=5) | 5 | ALL | C>T | 5080 | -0.04775 | -0.03866 | [-0.04887, -0.04663] | 0.045 | decrease | yes |
| CNN(k=7) | 7 | ALL | C>A | 5080 | -0.10259 | -0.08895 | [-0.10499, -0.10026] | 0.078 | decrease | yes |
| CNN(k=7) | 7 | ALL | C>G | 5080 | -0.07013 | -0.06091 | [-0.07222, -0.06806] | 0.142 | decrease | yes |
| CNN(k=7) | 7 | ALL | C>T | 5080 | -0.09636 | -0.08831 | [-0.09823, -0.09447] | 0.035 | decrease | yes |
| Linear | - | ALL | C>A | 5080 | -0.07649 | -0.07649 | [-0.07649, -0.07649] | 0.000 | decrease | yes |
| Linear | - | ALL | C>G | 5080 | -0.05940 | -0.05940 | [-0.05940, -0.05940] | 0.000 | decrease | yes |
| Linear | - | ALL | C>T | 5080 | -0.05242 | -0.05242 | [-0.05242, -0.05242] | 0.000 | decrease | yes |
| MLP | - | ALL | C>A | 5080 | -0.07222 | -0.06795 | [-0.07347, -0.07097] | 0.024 | decrease | yes |
| MLP | - | ALL | C>G | 5080 | -0.04843 | -0.04359 | [-0.04942, -0.04744] | 0.046 | decrease | yes |
| MLP | - | ALL | C>T | 5080 | -0.05195 | -0.04620 | [-0.05301, -0.05085] | 0.048 | decrease | yes |
| Transformer | - | ALL | C>A | 5080 | -0.08428 | -0.08526 | [-0.08530, -0.08328] | 0.000 | decrease | yes |
| Transformer | - | ALL | C>G | 5080 | -0.06392 | -0.06527 | [-0.06480, -0.06304] | 0.024 | decrease | yes |
| Transformer | - | ALL | C>T | 5080 | -0.06825 | -0.06869 | [-0.06908, -0.06741] | 0.000 | decrease | yes |
| XGBoost | - | ALL | C>A | 5080 | -0.07398 | -0.07388 | [-0.07489, -0.07306] | 0.015 | decrease | yes |
| XGBoost | - | ALL | C>G | 5080 | -0.05724 | -0.05507 | [-0.05805, -0.05644] | 0.029 | decrease | yes |
| XGBoost | - | ALL | C>T | 5080 | -0.05716 | -0.05658 | [-0.05790, -0.05642] | 0.021 | decrease | yes |

## 2. Cell-line strata (pooled models, same guides split by cell line)

| model | kernel | cell line | substitution | n | mean Δ | median Δ | 95% bootstrap CI | P(Δ>0) | direction | CI excludes 0 |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | :--- | ---: | :--- | :--- |
| CNN(k=3) | 3 | hct116 | C>A | 1377 | -0.03062 | -0.02801 | [-0.03180, -0.02949] | 0.049 | decrease | yes |
| CNN(k=3) | 3 | hct116 | C>G | 1377 | -0.01977 | -0.01688 | [-0.02088, -0.01864] | 0.145 | decrease | yes |
| CNN(k=3) | 3 | hct116 | C>T | 1377 | -0.01604 | -0.01296 | [-0.01722, -0.01485] | 0.236 | decrease | yes |
| CNN(k=3) | 3 | hek293t | C>A | 618 | -0.01282 | -0.00914 | [-0.01442, -0.01124] | 0.235 | decrease | yes |
| CNN(k=3) | 3 | hek293t | C>G | 618 | -0.00826 | -0.00572 | [-0.00970, -0.00680] | 0.291 | decrease | yes |
| CNN(k=3) | 3 | hek293t | C>T | 618 | -0.00993 | -0.00752 | [-0.01123, -0.00866] | 0.218 | decrease | yes |
| CNN(k=3) | 3 | hela | C>A | 2483 | -0.03411 | -0.03203 | [-0.03504, -0.03318] | 0.056 | decrease | yes |
| CNN(k=3) | 3 | hela | C>G | 2483 | -0.02216 | -0.01963 | [-0.02312, -0.02124] | 0.163 | decrease | yes |
| CNN(k=3) | 3 | hela | C>T | 2483 | -0.01613 | -0.01286 | [-0.01708, -0.01519] | 0.266 | decrease | yes |
| CNN(k=3) | 3 | hl60 | C>A | 602 | -0.01119 | -0.00748 | [-0.01255, -0.00985] | 0.228 | decrease | yes |
| CNN(k=3) | 3 | hl60 | C>G | 602 | -0.00831 | -0.00562 | [-0.00965, -0.00700] | 0.271 | decrease | yes |
| CNN(k=3) | 3 | hl60 | C>T | 602 | -0.00954 | -0.00712 | [-0.01075, -0.00835] | 0.204 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>A | 1377 | -0.06157 | -0.05380 | [-0.06387, -0.05931] | 0.013 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>G | 1377 | -0.04540 | -0.03708 | [-0.04752, -0.04332] | 0.065 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>T | 1377 | -0.05082 | -0.04345 | [-0.05298, -0.04874] | 0.040 | decrease | yes |
| CNN(k=5) | 5 | hek293t | C>A | 618 | -0.03388 | -0.02436 | [-0.03635, -0.03153] | 0.021 | decrease | yes |
| CNN(k=5) | 5 | hek293t | C>G | 618 | -0.02508 | -0.01526 | [-0.02744, -0.02271] | 0.136 | decrease | yes |
| CNN(k=5) | 5 | hek293t | C>T | 618 | -0.02925 | -0.01997 | [-0.03157, -0.02710] | 0.049 | decrease | yes |
| CNN(k=5) | 5 | hela | C>A | 2483 | -0.06740 | -0.05923 | [-0.06915, -0.06571] | 0.012 | decrease | yes |
| CNN(k=5) | 5 | hela | C>G | 2483 | -0.05112 | -0.04311 | [-0.05287, -0.04941] | 0.063 | decrease | yes |
| CNN(k=5) | 5 | hela | C>T | 2483 | -0.05557 | -0.04843 | [-0.05727, -0.05393] | 0.046 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>A | 602 | -0.03111 | -0.02153 | [-0.03366, -0.02865] | 0.038 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>G | 602 | -0.02333 | -0.01545 | [-0.02564, -0.02116] | 0.111 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>T | 602 | -0.02747 | -0.01834 | [-0.02985, -0.02514] | 0.050 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>A | 1377 | -0.10997 | -0.09842 | [-0.11439, -0.10533] | 0.065 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>G | 1377 | -0.07415 | -0.06652 | [-0.07816, -0.07029] | 0.137 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>T | 1377 | -0.10297 | -0.09451 | [-0.10660, -0.09949] | 0.027 | decrease | yes |
| CNN(k=7) | 7 | hek293t | C>A | 618 | -0.06064 | -0.04540 | [-0.06579, -0.05575] | 0.084 | decrease | yes |
| CNN(k=7) | 7 | hek293t | C>G | 618 | -0.03837 | -0.02660 | [-0.04289, -0.03387] | 0.199 | decrease | yes |
| CNN(k=7) | 7 | hek293t | C>T | 618 | -0.06022 | -0.04809 | [-0.06429, -0.05622] | 0.040 | decrease | yes |
| CNN(k=7) | 7 | hela | C>A | 2483 | -0.12114 | -0.11283 | [-0.12466, -0.11774] | 0.074 | decrease | yes |
| CNN(k=7) | 7 | hela | C>G | 2483 | -0.08350 | -0.08010 | [-0.08662, -0.08051] | 0.124 | decrease | yes |
| CNN(k=7) | 7 | hela | C>T | 2483 | -0.11132 | -0.10735 | [-0.11402, -0.10862] | 0.035 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>A | 602 | -0.05227 | -0.03638 | [-0.05734, -0.04724] | 0.118 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>G | 602 | -0.03838 | -0.02280 | [-0.04277, -0.03411] | 0.168 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>T | 602 | -0.05660 | -0.04058 | [-0.06092, -0.05237] | 0.043 | decrease | yes |
| Linear | - | hct116 | C>A | 1377 | -0.07649 | -0.07649 | [-0.07649, -0.07649] | 0.000 | decrease | yes |
| Linear | - | hct116 | C>G | 1377 | -0.05940 | -0.05940 | [-0.05940, -0.05940] | 0.000 | decrease | yes |
| Linear | - | hct116 | C>T | 1377 | -0.05242 | -0.05242 | [-0.05242, -0.05242] | 0.000 | decrease | yes |
| Linear | - | hek293t | C>A | 618 | -0.07649 | -0.07649 | [-0.07649, -0.07649] | 0.000 | decrease | yes |
| Linear | - | hek293t | C>G | 618 | -0.05940 | -0.05940 | [-0.05940, -0.05940] | 0.000 | decrease | yes |
| Linear | - | hek293t | C>T | 618 | -0.05242 | -0.05242 | [-0.05242, -0.05242] | 0.000 | decrease | yes |
| Linear | - | hela | C>A | 2483 | -0.07649 | -0.07649 | [-0.07649, -0.07649] | 0.000 | decrease | yes |
| Linear | - | hela | C>G | 2483 | -0.05940 | -0.05940 | [-0.05940, -0.05940] | 0.000 | decrease | yes |
| Linear | - | hela | C>T | 2483 | -0.05242 | -0.05242 | [-0.05242, -0.05242] | 0.000 | decrease | yes |
| Linear | - | hl60 | C>A | 602 | -0.07649 | -0.07649 | [-0.07649, -0.07649] | 0.000 | decrease | yes |
| Linear | - | hl60 | C>G | 602 | -0.05940 | -0.05940 | [-0.05940, -0.05940] | 0.000 | decrease | yes |
| Linear | - | hl60 | C>T | 602 | -0.05242 | -0.05242 | [-0.05242, -0.05242] | 0.000 | decrease | yes |
| MLP | - | hct116 | C>A | 1377 | -0.08212 | -0.07591 | [-0.08461, -0.07970] | 0.008 | decrease | yes |
| MLP | - | hct116 | C>G | 1377 | -0.05622 | -0.05000 | [-0.05829, -0.05423] | 0.026 | decrease | yes |
| MLP | - | hct116 | C>T | 1377 | -0.06096 | -0.05405 | [-0.06312, -0.05887] | 0.020 | decrease | yes |
| MLP | - | hek293t | C>A | 618 | -0.04438 | -0.03614 | [-0.04735, -0.04143] | 0.073 | decrease | yes |
| MLP | - | hek293t | C>G | 618 | -0.03007 | -0.02391 | [-0.03237, -0.02780] | 0.104 | decrease | yes |
| MLP | - | hek293t | C>T | 618 | -0.03026 | -0.02300 | [-0.03276, -0.02784] | 0.117 | decrease | yes |
| MLP | - | hela | C>A | 2483 | -0.08176 | -0.07820 | [-0.08341, -0.08013] | 0.007 | decrease | yes |
| MLP | - | hela | C>G | 2483 | -0.05368 | -0.04898 | [-0.05498, -0.05234] | 0.022 | decrease | yes |
| MLP | - | hela | C>T | 2483 | -0.05839 | -0.05378 | [-0.05981, -0.05698] | 0.019 | decrease | yes |
| MLP | - | hl60 | C>A | 602 | -0.03879 | -0.02889 | [-0.04179, -0.03585] | 0.085 | decrease | yes |
| MLP | - | hl60 | C>G | 602 | -0.02778 | -0.02136 | [-0.03016, -0.02545] | 0.128 | decrease | yes |
| MLP | - | hl60 | C>T | 602 | -0.02701 | -0.01878 | [-0.02951, -0.02448] | 0.166 | decrease | yes |
| Transformer | - | hct116 | C>A | 1377 | -0.09372 | -0.09104 | [-0.09544, -0.09202] | 0.000 | decrease | yes |
| Transformer | - | hct116 | C>G | 1377 | -0.07087 | -0.06925 | [-0.07231, -0.06941] | 0.000 | decrease | yes |
| Transformer | - | hct116 | C>T | 1377 | -0.07563 | -0.07234 | [-0.07706, -0.07417] | 0.000 | decrease | yes |
| Transformer | - | hek293t | C>A | 618 | -0.05267 | -0.04182 | [-0.05578, -0.04969] | 0.000 | decrease | yes |
| Transformer | - | hek293t | C>G | 618 | -0.03700 | -0.02807 | [-0.03984, -0.03431] | 0.128 | decrease | yes |
| Transformer | - | hek293t | C>T | 618 | -0.04211 | -0.03272 | [-0.04469, -0.03962] | 0.002 | decrease | yes |
| Transformer | - | hela | C>A | 2483 | -0.09578 | -0.09398 | [-0.09689, -0.09467] | 0.000 | decrease | yes |
| Transformer | - | hela | C>G | 2483 | -0.07398 | -0.07366 | [-0.07498, -0.07299] | 0.000 | decrease | yes |
| Transformer | - | hela | C>T | 2483 | -0.07792 | -0.07426 | [-0.07884, -0.07700] | 0.000 | decrease | yes |
| Transformer | - | hl60 | C>A | 602 | -0.04766 | -0.04139 | [-0.05038, -0.04505] | 0.000 | decrease | yes |
| Transformer | - | hl60 | C>G | 602 | -0.03422 | -0.02693 | [-0.03666, -0.03191] | 0.073 | decrease | yes |
| Transformer | - | hl60 | C>T | 602 | -0.03829 | -0.03098 | [-0.04056, -0.03605] | 0.002 | decrease | yes |
| XGBoost | - | hct116 | C>A | 1377 | -0.07989 | -0.07844 | [-0.08145, -0.07829] | 0.001 | decrease | yes |
| XGBoost | - | hct116 | C>G | 1377 | -0.06234 | -0.05910 | [-0.06375, -0.06096] | 0.001 | decrease | yes |
| XGBoost | - | hct116 | C>T | 1377 | -0.06231 | -0.06021 | [-0.06355, -0.06108] | 0.002 | decrease | yes |
| XGBoost | - | hek293t | C>A | 618 | -0.05309 | -0.05264 | [-0.05584, -0.05034] | 0.063 | decrease | yes |
| XGBoost | - | hek293t | C>G | 618 | -0.03834 | -0.03721 | [-0.04079, -0.03587] | 0.110 | decrease | yes |
| XGBoost | - | hek293t | C>T | 618 | -0.03919 | -0.03790 | [-0.04135, -0.03698] | 0.076 | decrease | yes |
| XGBoost | - | hela | C>A | 2483 | -0.08199 | -0.08130 | [-0.08317, -0.08081] | 0.001 | decrease | yes |
| XGBoost | - | hela | C>G | 2483 | -0.06450 | -0.06123 | [-0.06550, -0.06346] | 0.001 | decrease | yes |
| XGBoost | - | hela | C>T | 2483 | -0.06391 | -0.06227 | [-0.06481, -0.06298] | 0.000 | decrease | yes |
| XGBoost | - | hl60 | C>A | 602 | -0.04882 | -0.04730 | [-0.05141, -0.04631] | 0.055 | decrease | yes |
| XGBoost | - | hl60 | C>G | 602 | -0.03506 | -0.03411 | [-0.03736, -0.03279] | 0.123 | decrease | yes |
| XGBoost | - | hl60 | C>T | 602 | -0.03599 | -0.03618 | [-0.03813, -0.03384] | 0.091 | decrease | yes |

## 3. Cell-line-specific CNN checkpoints (model trained on that cell line only)

| model | kernel | cell line | substitution | n | mean Δ | median Δ | 95% bootstrap CI | P(Δ>0) | direction | CI excludes 0 |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | :--- | ---: | :--- | :--- |
| CNN(k=3) | 3 | hct116 | C>A | 1377 | -0.01556 | -0.01634 | [-0.01679, -0.01434] | 0.251 | decrease | yes |
| CNN(k=3) | 3 | hct116 | C>G | 1377 | -0.00781 | -0.00849 | [-0.00890, -0.00670] | 0.367 | decrease | yes |
| CNN(k=3) | 3 | hct116 | C>T | 1377 | -0.00034 | -0.00006 | [-0.00129, +0.00062] | 0.497 | decrease | no |
| CNN(k=3) | 3 | hek293t | C>A | 618 | -0.00345 | -0.00358 | [-0.00478, -0.00211] | 0.416 | decrease | yes |
| CNN(k=3) | 3 | hek293t | C>G | 618 | +0.00357 | +0.00377 | [+0.00235, +0.00477] | 0.589 | increase | yes |
| CNN(k=3) | 3 | hek293t | C>T | 618 | +0.00662 | +0.00490 | [+0.00519, +0.00807] | 0.633 | increase | yes |
| CNN(k=3) | 3 | hela | C>A | 2483 | -0.02751 | -0.02733 | [-0.02827, -0.02673] | 0.080 | decrease | yes |
| CNN(k=3) | 3 | hela | C>G | 2483 | -0.01602 | -0.01546 | [-0.01683, -0.01517] | 0.224 | decrease | yes |
| CNN(k=3) | 3 | hela | C>T | 2483 | -0.01248 | -0.01145 | [-0.01318, -0.01179] | 0.243 | decrease | yes |
| CNN(k=3) | 3 | hl60 | C>A | 602 | -0.00213 | -0.00242 | [-0.00318, -0.00105] | 0.424 | decrease | yes |
| CNN(k=3) | 3 | hl60 | C>G | 602 | -0.00134 | -0.00154 | [-0.00243, -0.00028] | 0.458 | decrease | yes |
| CNN(k=3) | 3 | hl60 | C>T | 602 | -0.01200 | -0.01179 | [-0.01303, -0.01097] | 0.161 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>A | 1377 | -0.05140 | -0.05299 | [-0.05277, -0.05003] | 0.024 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>G | 1377 | -0.03052 | -0.02948 | [-0.03177, -0.02924] | 0.087 | decrease | yes |
| CNN(k=5) | 5 | hct116 | C>T | 1377 | -0.01251 | -0.01218 | [-0.01378, -0.01120] | 0.315 | decrease | yes |
| CNN(k=5) | 5 | hek293t | C>A | 618 | -0.00685 | -0.00700 | [-0.00793, -0.00579] | 0.316 | decrease | yes |
| CNN(k=5) | 5 | hek293t | C>G | 618 | +0.00274 | +0.00228 | [+0.00176, +0.00372] | 0.578 | increase | yes |
| CNN(k=5) | 5 | hek293t | C>T | 618 | +0.01032 | +0.00974 | [+0.00915, +0.01146] | 0.730 | increase | yes |
| CNN(k=5) | 5 | hela | C>A | 2483 | -0.08995 | -0.08849 | [-0.09160, -0.08832] | 0.008 | decrease | yes |
| CNN(k=5) | 5 | hela | C>G | 2483 | -0.06538 | -0.06149 | [-0.06719, -0.06356] | 0.060 | decrease | yes |
| CNN(k=5) | 5 | hela | C>T | 2483 | -0.05503 | -0.05357 | [-0.05639, -0.05370] | 0.036 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>A | 602 | -0.01675 | -0.01603 | [-0.01830, -0.01518] | 0.194 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>G | 602 | -0.00838 | -0.00743 | [-0.01015, -0.00664] | 0.364 | decrease | yes |
| CNN(k=5) | 5 | hl60 | C>T | 602 | -0.02008 | -0.02078 | [-0.02202, -0.01821] | 0.199 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>A | 1377 | -0.08376 | -0.08356 | [-0.08546, -0.08205] | 0.001 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>G | 1377 | -0.07044 | -0.06991 | [-0.07212, -0.06881] | 0.003 | decrease | yes |
| CNN(k=7) | 7 | hct116 | C>T | 1377 | -0.05280 | -0.05183 | [-0.05419, -0.05139] | 0.015 | decrease | yes |
| CNN(k=7) | 7 | hek293t | C>A | 618 | +0.00616 | +0.00659 | [+0.00522, +0.00711] | 0.693 | increase | yes |
| CNN(k=7) | 7 | hek293t | C>G | 618 | +0.00679 | +0.00652 | [+0.00614, +0.00746] | 0.785 | increase | yes |
| CNN(k=7) | 7 | hek293t | C>T | 618 | +0.01328 | +0.01227 | [+0.01236, +0.01424] | 0.867 | increase | yes |
| CNN(k=7) | 7 | hela | C>A | 2483 | -0.08761 | -0.08595 | [-0.08897, -0.08625] | 0.000 | decrease | yes |
| CNN(k=7) | 7 | hela | C>G | 2483 | -0.06877 | -0.06618 | [-0.07018, -0.06736] | 0.010 | decrease | yes |
| CNN(k=7) | 7 | hela | C>T | 2483 | -0.04970 | -0.04673 | [-0.05081, -0.04862] | 0.013 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>A | 602 | -0.00909 | -0.00885 | [-0.00998, -0.00820] | 0.213 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>G | 602 | -0.00447 | -0.00349 | [-0.00558, -0.00336] | 0.420 | decrease | yes |
| CNN(k=7) | 7 | hl60 | C>T | 602 | -0.02422 | -0.02460 | [-0.02539, -0.02303] | 0.061 | decrease | yes |

## 4. Stability across configurations

Every row below is one (model × kernel × cell line) configuration (the pooled models are also
counted once per cell-line stratum); "same sign" = share of configurations agreeing with the
majority direction.

| substitution | configurations | same sign | share | mean of means | configs with CI excluding 0 |
| :--- | ---: | ---: | ---: | ---: | ---: |
| C>A | 40 | decrease | 0.97 | -0.05303 | 40 |
| C>G | 40 | decrease | 0.93 | -0.03799 | 40 |
| C>T | 40 | decrease | 0.93 | -0.03941 | 39 |

Per-sample sign agreement between substitutions (pooled models, n=35560 sample×model rows):
{"A vs G": 0.93, "A vs T": 0.94, "G vs T": 0.924}

## 5. Do the model predictions agree with the measured efficacy differences?

Measured per-base efficacy comes from `results/tables/paper/position18_efficacy_by_base.csv`
(observational data, same guides). "C better" = predicted efficacy(C) > efficacy(X) for the model,
and measured efficacy(C) > efficacy(X) for the data.

| substitution | cell line | model mean Δ | measured C − X | model direction | measured direction | agree | n(C) | n(X) |
| :--- | :--- | ---: | ---: | :--- | :--- | :--- | ---: | ---: |
| C>A | hct116 | -0.07634 | +0.090 | C better | C better | yes | 1377 | 1652 |
| C>A | hek293t | -0.04771 | -0.015 | C better | X better | NO | 618 | 584 |
| C>A | hela | -0.07981 | +0.092 | C better | C better | yes | 2483 | 3278 |
| C>A | hl60 | -0.04376 | +0.027 | C better | C better | yes | 602 | 495 |
| C>G | hct116 | -0.05545 | +0.070 | C better | C better | yes | 1377 | 1210 |
| C>G | hek293t | -0.03379 | -0.016 | C better | X better | NO | 618 | 554 |
| C>G | hela | -0.05833 | +0.072 | C better | C better | yes | 2483 | 2340 |
| C>G | hl60 | -0.03236 | +0.029 | C better | C better | yes | 602 | 472 |
| C>T | hek293t | -0.03763 | -0.026 | C better | X better | NO | 618 | 577 |
| C>T | hl60 | -0.03533 | +0.043 | C better | C better | yes | 602 | 507 |

Agreement rate: **70.00%** of the (substitution × cell line) cells
(4 cell lines only — this is a descriptive comparison, not a statistical test).

## 6. Answers to the three questions

See the chat summary; the machine-readable basis is
`results/tables/paper/position18_signed_substitution_ISM.csv`
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
