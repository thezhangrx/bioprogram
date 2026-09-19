# External model validation: CRISPRon vs the project's model-derived counterfactual at sgRNA position 18

## 术语对照（本文档强制使用左侧表述）

| 使用（allowed） | 中文 | 禁止（forbidden unless paired experimental data exist） |
| --- | --- | --- |
| external model validation | 外部模型验证 | — |
| model-based counterfactual | 模型反事实 | causal proof |
| in-silico mutagenesis | 计算机内突变 | experimental effect |
| directional consistency | 方向一致性 | biological mechanism proof |
| cross-model consistency | 跨模型一致性 | 因果结论 |

CRISPRon 的输出是**预测**，不是实验测量；两个模型的一致只说明*model-derived counterfactual* 的方向在不同归纳偏置下可复现。

> **术语边界。** 本文档报告的是 *external model validation*：用独立的第三方预测模型 CRISPRon 对项目发现的候选序列规律做**方向一致性**检验。CRISPRon 的输出是**模型预测**，因此本文档只声明「CRISPRon 独立地预测 C18A 扰动后活性下降」，**不声明**「C18A 会导致真实编辑效率下降」，也不构成 *causal proof*。本项目**没有**配对的实验突变数据。

## A. 软件

| 项目 | 值 |
| --- | --- |
| 软件 | CRISPRon v1.0 (`crispron-main`) |
| 原始包 | `deploy/external/crispron/package/crispron-main.zip` |
| 包 sha256 | `3fa17a7cb3de043703ec3090505c96340e6da13f23acda8fd7f7268a3f572a9b` |
| 依赖 | CRISPRoff 1.1.2（`dependencies/crisproff-1.1.2.tar.gz`，sha256 `bb82cc905dfef5c1…`） |
| 安装实例 | `deploy/external/crispron/software/crispron-main`（原始 zip 未被修改） |
| 运行环境 | 隔离 venv `deploy/external/crispron/venv/`，python 3.12.3 |
| 依赖版本 | `{"Bio": "1.83", "RNA": "2.6.4", "keras": "2.14.0", "numpy": "1.26.4", "pandas": "2.2.2", "scipy": "1.15.3", "sklearn": "1.4.2", "tensorflow": "2.14.0"}` |

**官方自检（golden test）**：`bin/test.sh` 通过（`TEST ok`），且 `30mers.fa` / `23mers.fa` / `CRISPRparams.tsv` / `crispron.csv` 与包内 `test/outdir.original/` **逐字节一致**（sha256 全等）。详见 `deploy/external/crispron/logs/selftest_result.md`。

**唯一偏离官方安装之处**：官方要求 ViennaRNA 的 `RNAfold` 可执行文件（CRISPRoff 以 subprocess 调用）；PyPI 的 `ViennaRNA==2.6.4` 轮子只含 Python API。因此提供 `deploy/external/crispron/software/wrappers/RNAfold` shim，用**同版本**的 `RNA.fold()` 复现同一 MFE，并按 CRISPRoff 的解析格式输出。其数值等价性已由上述 golden test 证明（`CRISPRparams.tsv` 逐字节一致）。

## B. 样本

- 候选池：`results/tables/candidates/wt_position18_candidates.csv` —— 由 `analysis/candidates/wt_position18_selection.py` 从 DeepCRISPR **single 划分 test 集**按预先登记规则选出（无泄漏、禁止 cherry-picking）。
- 入选 8 条 WT；细胞系分布 {'hct116': np.int64(2), 'hek293t': np.int64(2), 'hela': np.int64(2), 'hl60': np.int64(2)}；实验效率 0.110–0.537；GC 45–70%。
- **本流程未重新挑选 WT，也未用任何 CRISPRon 结果做筛选。**

| ID | cell_line | WT (23 nt) | PAM | Exp. efficiency | GC% |
| --- | --- | --- | --- | --- | --- |
| WT01 | hct116 | GACAGGAAGGTGCTGTACACAGG | AGG | 0.110 | 55.000 |
| WT02 | hek293t | TTATGGTGTGACAGTGCCTCCGG | CGG | 0.144 | 50.000 |
| WT03 | hek293t | CCTTCAGCCTCCTTGTGCTCTGG | TGG | 0.214 | 60.000 |
| WT04 | hela | TCAGAATCCCATTCTTCCACAGG | AGG | 0.267 | 45.000 |
| WT05 | hct116 | ACCAACTACCAGCTGGGCACAGG | AGG | 0.537 | 60.000 |
| WT06 | hela | TAATGCATCTGCCATCACGGTGG | TGG | 0.503 | 50.000 |
| WT07 | hl60 | AGCCGGCCCGTAAGATCCGCAGG | AGG | 0.344 | 70.000 |
| WT08 | hl60 | GGCCGAAAGAGCCGTGGCCTTGG | TGG | 0.187 | 70.000 |

## C. 序列与坐标映射

| 项目约定 | CRISPRon 约定 |
| --- | --- |
| 23 nt = protospacer 1–20 + PAM 21–23 | 30 nt = 4 nt + target(20 nt) + PAM(3 nt, NGG) + 3 nt |
| Position 18（23 nt 内 1-based） | 30 nt 内 0-based 下标 `21` = 21 |

映射规则：`crispron_index = 4 + (position_1b − 1)`，由 `analysis/external_validation/crispron_adapter.py::describe_mapping()` 显式推导并写入每次运行的 `config.json`。**未默认把「23 nt 第 18 位」当成「20 nt gRNA 第 18 位」**——虽然本项目两者恰好重合（protospacer 就是前 20 nt），但代码按 `spacer_len` 计算而非假设。

**逐条序列验证**（WT 与 C18A 唯一差异 = 位点 18；PAM／侧翼／方向均不变）：

| ID | WT | C18A | PAM | qc_only_pos18_changed | qc_pam_unchanged | qc_flanks_identical | qc_orientation_preserved |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WT01 | GACAGGAAGGTGCTGTACACAGG | GACAGGAAGGTGCTGTAAACAGG | AGG | True | True | True | True |
| WT02 | TTATGGTGTGACAGTGCCTCCGG | TTATGGTGTGACAGTGCATCCGG | CGG | True | True | True | True |
| WT03 | CCTTCAGCCTCCTTGTGCTCTGG | CCTTCAGCCTCCTTGTGATCTGG | TGG | True | True | True | True |
| WT04 | TCAGAATCCCATTCTTCCACAGG | TCAGAATCCCATTCTTCAACAGG | AGG | True | True | True | True |
| WT05 | ACCAACTACCAGCTGGGCACAGG | ACCAACTACCAGCTGGGAACAGG | AGG | True | True | True | True |
| WT06 | TAATGCATCTGCCATCACGGTGG | TAATGCATCTGCCATCAAGGTGG | TGG | True | True | True | True |
| WT07 | AGCCGGCCCGTAAGATCCGCAGG | AGCCGGCCCGTAAGATCAGCAGG | AGG | True | True | True | True |
| WT08 | GGCCGAAAGAGCCGTGGCCTTGG | GGCCGAAAGAGCCGTGGACTTGG | TGG | True | True | True | True |

## D. CRISPRon predictions and directional consistency

| sample_id | cell_line | WT_sequence | mutant_sequence | mutation | PAM | WT_prediction | mutant_prediction | delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WT01 | hct116 | GACAGGAAGGTGCTGTACACAGG | GACAGGAAGGTGCTGTAAACAGG | C18A | AGG | 50.740 | 23.570 | -27.170 |
| WT02 | hek293t | TTATGGTGTGACAGTGCCTCCGG | TTATGGTGTGACAGTGCATCCGG | C18A | CGG | 47.790 | 34.030 | -13.760 |
| WT03 | hek293t | CCTTCAGCCTCCTTGTGCTCTGG | CCTTCAGCCTCCTTGTGATCTGG | C18A | TGG | 29.750 | 20.850 | -8.900 |
| WT04 | hela | TCAGAATCCCATTCTTCCACAGG | TCAGAATCCCATTCTTCAACAGG | C18A | AGG | 35.930 | 15.330 | -20.600 |
| WT05 | hct116 | ACCAACTACCAGCTGGGCACAGG | ACCAACTACCAGCTGGGAACAGG | C18A | AGG | 60.520 | 51.740 | -8.780 |
| WT06 | hela | TAATGCATCTGCCATCACGGTGG | TAATGCATCTGCCATCAAGGTGG | C18A | TGG | 76.390 | 62.510 | -13.880 |
| WT07 | hl60 | AGCCGGCCCGTAAGATCCGCAGG | AGCCGGCCCGTAAGATCAGCAGG | C18A | AGG | 50.680 | 35.210 | -15.470 |
| WT08 | hl60 | GGCCGAAAGAGCCGTGGCCTTGG | GGCCGAAAGAGCCGTGGACTTGG | C18A | TGG | 22.260 | 31.420 | 9.160 |

- 有效配对：**8/8**
- Δ < 0（预测下降）：**7** 条，Δ > 0：1 条
- **方向一致性 P(Δ<0) = 0.875**
- Δ 均值 -12.425，中位数 -13.820，范围 [-27.170, +9.160]

## E. Cross-model validation: consistency with the project's own Δ

项目侧 Δ 取自 `results/tables/paper/position18_signed_substitution_ISM_per_sample.csv`（项目 pooled ultimate 模型的 per-sample 反事实 Δ，7 个模型等权平均）。两侧**尺度不同**（项目为归一化效率单位，CRISPRon 为 indel %），因此只比较**方向与秩**。

| sample_id | cell_line | Δ project model | Δ CRISPRon | sign_ours | sign_crispron | agree_direction |
| --- | --- | --- | --- | --- | --- | --- |
| WT01 | hct116 | -0.102 | -27.170 | -1.000 | -1.000 | True |
| WT02 | hek293t | -0.026 | -13.760 | -1.000 | -1.000 | True |
| WT03 | hek293t | -0.055 | -8.900 | -1.000 | -1.000 | True |
| WT04 | hela | -0.109 | -20.600 | -1.000 | -1.000 | True |
| WT05 | hct116 | -0.105 | -8.780 | -1.000 | -1.000 | True |
| WT06 | hela | -0.071 | -13.880 | -1.000 | -1.000 | True |
| WT07 | hl60 | -0.050 | -15.470 | -1.000 | -1.000 | True |
| WT08 | hl60 | -0.021 | 9.160 | -1.000 | 1.000 | False |

- 方向一致：**7/8 = 0.875**
- Pearson r = 0.629；Spearman ρ = 0.476（n=8，样本量很小，仅作描述）

- **不一致样本（如实保留，未做任何调整）：['WT08']**。可能原因：模型架构与训练数据不同、CRISPRon 的特征包含 RNA/DNA 杂交与自折叠能量而本项目模型只有序列+表观通道、score 尺度不同、以及细胞系依赖性。

## F. Systematic in-silico mutagenesis (position × substitution)

- 枚举 8 条 WT × 23 位 × 3 替换；CRISPRon 可评估 504 条
- **Position 18 的 C→A 平均 Δ = -12.425**；其它位置 C→A 平均 Δ = +0.144
- Position 18 在「位置平均 |Δ| 强度谱」中排名 **1/21**（1 = 影响最强）

| ID | #C positions | rank of pos18 | percentile |
| --- | --- | --- | --- |
| WT01 | 4 | 1 | 1.000 |
| WT02 | 5 | 1 | 1.000 |
| WT03 | 9 | 1 | 1.000 |
| WT04 | 8 | 1 | 1.000 |
| WT05 | 8 | 1 | 1.000 |
| WT06 | 6 | 1 | 1.000 |
| WT07 | 8 | 1 | 1.000 |
| WT08 | 6 | 2 | 0.800 |

位置影响强度前 10 名（mean |Δ| 跨全部替换与全部序列）：

| position | mean |Δ| | rank |
| --- | --- | --- |
| 18.000 | 12.862 | 1 |
| 17.000 | 7.681 | 2 |
| 20.000 | 7.177 | 3 |
| 19.000 | 6.992 | 4 |
| 16.000 | 5.363 | 5 |
| 15.000 | 5.218 | 6 |
| 13.000 | 4.541 | 7 |
| 14.000 | 4.144 | 8 |
| 11.000 | 3.833 | 9 |
| 5.000 | 3.693 | 10 |

**边界**：修改 PAM(21–23) 可能破坏 NGG，CRISPRon 不再把该位点识别为 target，这类替换记为 `pam_preserved=False` 并**排除**在效应矩阵之外——这是方法本身的定义边界，不是失败。

## G. Scientific interpretation（严格分级）

```
prediction ≠ attribution ≠ counterfactual ≠ experimental effect ≠ causality
```

本次得到的是：

1. **CRISPRon 独立预测** C18A 扰动后活性下降 （7/8 条，一致性 0.88）→ 可写 *CRISPRon independently predicts a decreased activity after the C18A sequence perturbation*。
2. **项目模型与 CRISPRon 方向一致**（7/8）→ 可写 *the direction of the model-derived counterfactual effect is concordant across independent predictive models*。

**不能写**：*C18A causes editing efficiency to decrease* —— 本项目没有配对的实验突变数据，两个模型都是预测器，一致性只说明方向在不同归纳偏置下可复现，不构成因果或机制证据。

**不支持的部分**：
- 不支持效应**幅度**的定量外推（两模型尺度不同，且都未做概率校准）；
- 不支持该效应在其它细胞系/其它位点的普适性（仅 8 条代表性序列）；
- 不支持任何生物学机制解释。

## H. 质量控制清单与文件组织

自动检查 **12/12** 项通过：

| 检查项 | 通过 | 说明 |
| --- | --- | --- |
| WT/mutant 只有一个碱基差异 | True | 8/8 通过 |
| 差异位置恰为 Position 18 | True | 全部为 C18A（位点 18 由项目约定推导，非硬编码字符串） |
| PAM 有效 | True | PAM 集合 ['AGG', 'CGG', 'TGG']（均以 GG 结尾） |
| orientation 一致 | True | 30-mer 中 target 段与项目 23 nt 完全一致，未发生反向互补 |
| CRISPRon 对目标产生预测 | True | 8/8 的 WT 与 C18A 都拿到预测 |
| 是否出现多个潜在 target | True | 每条记录 target 数: WT=[np.int64(1)], C18A=[np.int64(1)] |
| 重复序列 | True | 8 条 WT 序列互不相同（代表性挑选阶段已按 canonical identity 去重） |
| reverse-complement duplicate | True | 无反向互补重复 |
| 缺失结果 | True | WT 缺失 0，C18A 缺失 0 |
| 异常预测值 | True | 全部落在 CRISPRon 训练标签范围 [0,100]：[15.33, 76.39] |
| 格式转换导致的序列变化 | True | WT 与 C18A 使用完全相同的 4 nt / 3 nt 侧翼 |
| 是否存在由 CRISPRon 结果反向筛选样本 | True | WT 来自预先登记的代表性挑选（analysis/candidates）；本流程在挑选完成后才运行 CRISPRon |

### 文件组织

| 内容 | 位置 |
| --- | --- |
| 原始 CRISPRon 压缩包（未修改） | `deploy/external/crispron/package/` |
| 解压后的 CRISPRon（安装实例） | `deploy/external/crispron/software/crispron-main/` |
| CRISPRoff 依赖（原始 tar.gz + 解压） | `deploy/external/crispron/dependencies/` |
| RNAfold shim | `deploy/external/crispron/software/wrappers/` |
| 隔离环境 + 安装记录 | `deploy/external/crispron/venv/`、`INSTALL_NOTES.md` |
| 自检日志 | `deploy/external/crispron/logs/` |
| wrapper / adapter 代码 | `analysis/external_validation/` |
| 输入 FASTA + 配置快照 | `results/external_validation/<run>/inputs/` |
| CRISPRon 原始输出 | `results/external_validation/<run>/raw/` |
| 运行日志 | `results/external_validation/<run>/logs/` |
| provenance manifest | `results/external_validation/<run>/external_validation_manifest.csv` |
| 清洗后的结果表 | `results/tables/external_validation/` |
| 图 | `results/figures/external_validation/` |
| 本报告 | `docs/reproducibility/EXTERNAL_MODEL_VALIDATION_CRISPRON.md` |

复现命令：

```bash
# 1) 安装（一次性；见 deploy/external/crispron/INSTALL_NOTES.md）
# 2) Level 1–3
python analysis/external_validation/validate_position18.py --run-id crispron_pos18_v1
# 3) Level 4
python analysis/external_validation/systematic_mutagenesis.py --run-id crispron_mutagenesis_v1
# 4) 图
python analysis/external_validation/figures.py
# 5) 报告
python analysis/external_validation/make_report.py
```
