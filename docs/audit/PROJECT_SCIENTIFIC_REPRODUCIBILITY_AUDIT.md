# 项目级科研可重复性与科学有效性审计（Project-wide Scientific Reproducibility & Validity Audit）

> 对象：`/home/zhang/bioprogram/Submit`，批次 `results/batches/batch_20260909_full`（1 344 runs，2026-09-13 已合并 448 个真 LOCO run）。
> 原则：以 **实际代码 + 实际 artifact + 实际配置** 为准；不依据 README/论文描述推断；发现不一致即记录。
> 本文件**只做审计**：未修改代码、未重训模型、未删除数据。机器可读清单见同目录 `issue_register.csv` 与 9 张审计表。

---

## Part 1 — Executive Summary

| 严重度 | 数量 | 代表问题 |
| :--- | ---: | :--- |
| **P0** | **4** | mixed 孪生行泄漏 21 %；真 LOCO 亦被同一泄漏污染（hold-out 系 27–51 %）；single 内 revcomp/locus 孪生；`all` 历史退化（已修） |
| **P1** | **15** | test-set 兼作选择集；零方差表观通道；LR 秩亏；`min_edge_fdr` 名不副实；两套因子 CI；ANOVA 无 FDR；边表重复；`loco_performance` 未滤发散；Table 2 口径错误；CNN 重要性两套口径；motif 一致性口径放大；样本内 ISM/候选；热图 parser 错位；`calculate_delta_R2` seed 键风险 |
| **P2** | **9** | 11 个 CSV 无生成脚本；`conv_channels` no-op；loader 丢列；**安装环境与 requirements 严重不符**；XGBoost 版本风险；QC 缺 5 类检查；artifact 无 provenance；`n_train/valid/test` 缺失；环境组合规范化位置 |
| **P3** | **1** | 文档 stale/自相矛盾（LOCO 不可达、QC 维 161 vs 184、运行矩阵 64 vs 256、README 矛盾、HPC 脚本缺失） |

**当前项目是否已达到"可信地用于论文最终分析"的程度？**
**部分达到。** 具体分档见 Part 11：single-split 的域内性能与模型行为类结论可报（带 caveat）；所有 **mixed 与 LOCO 的绝对性能与增量效应**在按 `(sgRNA,label)` 去重前**必须重算**；环境因子 Tier、候选方向性结论属"可报但须降措辞/标注样本内"；"AI 设计的新候选"目前**不能声称**。

**最高优先级事实**：本项目的两个"泛化"实验（mixed、LOCO）共享同一根因泄漏（跨细胞系孪生行），把 mixed 性能（MLP 干净子集 R²=−0.004）与 LOCO 泛化（hct116 干净子集 R²=0.196，泄漏子集 0.344）都抬高了。**去重是单一最高杠杆的修复**。

---

## Part 2 — Data Lineage

```text
data/raw/{hct116,hek293t,hela,hl60}.csv        (sgRNA + CTCF/Dnase/H3K4me3/RRBS + Normalized efficacy)
  → core/features/engineering/feature_engineering.py：one-hot(4ch) + per-position binary(4ch) + 整行去重(2233 全在 hek293t)
  → data/processed/{cell}_features_23x8.npy / _184.npy / _labels.npy / _metadata.csv / feature_schema.json
  → analysis/data_QC.py（KDE 离群、缺失、GC）+ data/validation.py（指标同号）→ workspace/qc_sessions/qc_*/
  → core/data/splitting/cell_line_division.py（single 0.70/0.15/0.15；mixed 同；LOCO 训练池 0.85/0.15）
  → workflows/training/train.py（5 类模型）→ models/<batch>/<run>/*  results/<batch>/<run>/{metrics,predictions,feature_importance,info}
  → analysis/pipeline.py → analyse_out/{tables,summary,figures}
  → paper/make_assets.py → paper/tables/*.tex, docs/paper/figures/*
  → docs/paper/main/main.tex → paper/main.pdf（正式排版需 TeX；沙箱内用 make_pdf_fallback.py 生成审阅版）
```

**无 provenance 锚点**：run 目录只写 `*_info.txt` 与 config，**没有** git commit、数据指纹（sha1）、config hash、时间戳关联 → 无法从 artifact 反查代码/数据版本（Issue G7）。

---

## Part 3 — Dataset Routing / Identity

| cell line | feature file | label file | metadata | X/y/meta 行数 | 一致 | label 范围 | npy sha1(12) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| hct116 | `hct116_features_23x8.npy` | `hct116_labels.npy` | `hct116_metadata.csv` | 4239/4239/4239 | ✅ | [0.0003, 0.9459] | 见 `dataset_routing_audit.csv` |
| hek293t | `hek293t_features_23x8.npy` | `hek293t_labels.npy` | `hek293t_metadata.csv` | 2333/2333/2333 | ✅ | [0.0369, 0.5903] | 同上 |
| hela | `hela_features_23x8.npy` | `hela_labels.npy` | `hela_metadata.csv` | 8101/8101/8101 | ✅ | [0, 1] | 同上 |
| hl60 | `hl60_features_23x8.npy` | `hl60_labels.npy` | `hl60_metadata.csv` | 2076/2076/2076 | ✅ | [0.0278, 0.6927] | 同上 |

* 路径解析链：`--data-dir` + `get_feature_file_paths()` 按 `{cell_line}_features_{23}x{8}.npy` 拼名（`cell_line_division.py:75-86`），**未发现**"请求 hct116 却加载 hela"的路径分支；`load_cell_line` 缺文件会抛 `FileNotFoundError`（fail fast ✓）。
* 逐行身份（X_i ↔ y_i ↔ metadata_i）：用 `metadata.sgRNA` 与张量 argmax 交叉验证，**顺序一致率 1.0000**（此前多轮验证）；`analysis/attribution/extractors._parse_position_channel` 把 0-based 的 `{ch}_pos_{l}` +1 归一化，实测 attribution_summary 5 个模型 position 均为 1..23。
* 风险点：`analysis/data/loaders.py:38-87` 只保留 16 列 → `cell_lines/input_shape_*/sequence_kernel` 丢失（G3）；`Cell line` 由文件名注入，metadata 里也有同名列（两处来源，若文件被重命名会不一致）。

---

## Part 4 — Split / Leakage / Generalization

**重复分类学（严格区分，不默认等价）**

| 层级 | 定义 | 实测 | cell-line 对 | 是否 leakage | 处理建议 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| L1 | exact full-row duplicate | 2233（全在 hek293t，已去重） | — | 已消除 | — |
| L2 | same `(sgRNA, label)` | **2506** | hct116↔hela（另 hct116↔hl60 27、hela↔hl60 34） | **是**（跨文件未去重） | group-aware split 或全局去重 |
| L3 | same sgRNA（同系内） | 0（4 系 sgRNA 全唯一） | — | 否 | — |
| L4 | same genomic locus | mixed test∩train 524–534；single 内 HEK293T 21/350、HeLa 7/1215 | 多对 | **部分**（位点级近重复） | 至少 provenance 警告 + 可选 group split |
| L5 | reverse-complement / strand-equivalent | 21/21 配对互为 revcomp（9 +/-、12 -/+） | HEK293T、HeLa | **是（位点级）** | 与 L4 合并处理 |
| L6 | same biological observation across cell lines | = L2 的 2506 | hct116↔hela | 取决于声称的 generalization level | 需在论文中声明 |

**各 split 的实测完整性（复现 `divide_data`，见 `split_integrity_audit.csv`）**

| split | train∩test | train∩valid | valid∩test | 结论 |
| :--- | ---: | ---: | ---: | :--- |
| single (hct116/hek293t/hela/hl60) | 0/0/0/0 | 0 | 0 | ✅ 行级干净；但 L4/L5 位点孪生存在（HEK293T 6.0 %） |
| mixed (seed 42/43/44/45) | **524/523/532/534** | 535/523/523/513 | 120/117/108/108 | ❌ 行级泄漏 21 %（同一 `(sgRNA,label)`） |
| all(LOCO) held=hct116 / hela / hl60 / hek293t | **2152 / 2155 / 36 / 0** | 8/9/663/667 | 365/369/8/0 | ❌ hold-out 系 50.8 %/26.6 %/1.7 % 命中训练池（L2 根因）；held-out 系确实不在训练**细胞系**内 ✓ |

**各 split 真正支持的 generalization**

| split | 能支持 | 不能支持 |
| :--- | :--- | :--- |
| single | 域内样本级泛化（同细胞系） | 跨细胞系、跨 locus |
| mixed | **样本级**（且去重后才是干净的）；L2 未去重前连样本级都被污染 | 序列级/位点级泛化（同 `(sgRNA,label)` 跨系重复）、跨细胞系 |
| all(LOCO) | 跨细胞系泛化（held-out 系不在训练细胞系内 ✓） | 序列级泛化（L2 使 27–51 % test 与训练同 key）；"完全未见过的序列"泛化 |

**量化影响（已核验行对齐）**

| 场景 | 模型 | 整体 R² | 泄漏子集 R² | 干净子集 R² |
| :--- | :--- | ---: | ---: | ---: |
| mixed seed42 single-env | XGBoost | +0.157 | **+0.381** | +0.102 |
| mixed seed42 single-env | MLP | +0.132 | **+0.690** | **−0.004** |
| mixed seed42 single-env | CNN(k5) | +0.147 | **+0.560** | +0.045 |
| LOCO held=hct116 | XGBoost | +0.262 | **+0.344** | +0.196 |
| LOCO held=hela | CNN(k5) | +0.119 | **+0.225** | +0.092 |
| LOCO held=hl60 | MLP | −0.723 | +0.703 | **−0.801** |

---

## Part 5 — Data Processing Integrity

* **Feature schema**：23×(A/C/G/T + CTCF/Dnase/H3K4me3/RRBS)=184；`feature_names=pos{p}_{ch}`（1-based、position-major）；线性剔 `_T`→161；CNN 由 schema 驱动取 4 通道。**未见 23x7 变体**；`feature_config.json` 与 `feature_schema.json` 一致（channel_names 8 项）。
* **零方差/近零方差**（`feature_integrity_audit.csv`）：HEK293T/HeLa 的 **Dnase 恒 1（var=0）**、HeLa CTCF frac₁=0.990（var 0.010）、RRBS 第 23 位在 4 系恒 0 → 不可识别通道；**不得**解释为"生物学无效应"。
* **线性代数**：hct116 sequence-only `Numerical rank=60 < 161`；56/192 线性 run 发散 → 系数/p/FDR 只在稳定子集内可信（Part 7）。
* **对齐**：X↔y↔metadata 顺序一致率 1.0000；prediction 表与 split 的 test 顺序在复现正确 cell-line 顺序后**逐行一致**（2 513/2 513 于 1e−6 内）→ 未发现 prediction 错位。
* **QC 缺口**：PAM/NGG、标签范围、跨文件/跨细胞系泄漏、表观零方差、shape-vs-schema（`validate_cell_line_dataset:98-110` 读 schema 不用）、序列级去重均**未实现**。

---

## Part 6 — Experimental / Statistical Integrity

| 项 | 实测口径 | 风险 |
| :--- | :--- | :--- |
| kernel/模型选择 | 单次 70/15/15 的 **test** 指标既用于比较又用于报告 | 选择偏置（B1） |
| ultimate 超参 | 10 折 CV 取最大，报告同一 CV 值 | 选择后估计（B2） |
| 逐样本配对 bootstrap | test cohort 内配对，B=2000 | 单位正确；但 cohort 被 mixed 泄漏污染 |
| 因子级 bootstrap | **unit = 模型配置，n=7** | 是"跨模型稳定性"，非 guide 抽样（已在论文/文档改名 Model-Level Bootstrap Interval） |
| permutation | edge 逐样本；main 用 8 个**嵌套**背景的 sign-flip（下界 2/2⁸=0.0078）；interaction 逐样本 | 背景非独立 → 名义 p 校准可疑；族内 BH 后**因子级取最小** = existence-oriented（D1） |
| FDR | 族 = `test_type|split|cell|model`（189 族；main 族大小 4）；motif 单族 596 | ANOVA **无 FDR**（D3） |
| ANOVA | blocked factorial，Type-II 边际，响应=实验级留出 R² | 与 edge-level 是两个问题；不参与 Tier ✓ |
| 统计单位 | 见 `statistical_unit_audit.csv`（12 项逐条） | model/sample/experiment 三级单位未在任何一处混用（除交叉模型比较的绝对阈值 C1） |

---

## Part 7 — Four-dimensional Analysis Integrity

* **Effect**：ΔR²（edge/factor/kernel 配对）单位=实验级 R² 配对差；signed ISM 单位=guide 的反事实 Δ（**样本内**）；ANOVA effect 单位=实验行。三者未互相替代 ✓，但**绝对阈值 `min_absolute_delta_r2=0.01` 与 baseline R² 量级相关**（弱基线更易通过，此前审计已量化）。
* **Importance**：多数为幅值（SHAP/IG/ISM magnitude/attention），唯一有符号的模型级列是 linear 的 `effect`；**CNN 存在两套口径**（E1）；热图 parser 错位（F1）但不影响 attribution 表。
* **Statistical Evidence**：bootstrap/permutation/FDR/LR p 的**单位混用风险已排除**（逐条见 `statistical_unit_audit.csv`），但 **`min_edge_fdr` 被写成 factor-level 语义**（D1）与**两套 CI 数值不同**（D2）。
* **Robustness**：跨模型 7 配置（等权）、跨 seed 4、跨 cell line 4、跨 kernel 3、跨 split 3（LOCO 现已真实）；**模型一致性不是独立重复**（共享数据），论文已按此措辞 ✓。
* **Evidence Integration**：三门外显式（effect/statistical/robustness），统计门不能单独提升 Tier；环境 4 因子合并 LOCO 后全部 Inconclusive（CTCF effect 门通过但 cell-line `Context-conflicting` 一票否决）。**ANOVA 不进入 Tier ✓**；importance/SNR 不进入 ✓。

---

## Part 8 — Candidate / Biological Interpretation Integrity

* **候选池**：`todo_data.CSV` 176 432 个唯一 sgRNA 中 **11 027（6.2 %）**在训练池内；ultimate 模型在全池重训后又给这些 guide 打分 → 这部分是**样本内预测**，不能称"AI 设计的新候选"（E3）。
* **signed ISM**：模型训练时见过全部被评估 guide → **model-internal counterfactual**，只能支持"模型预测方向"，不能支持生物学效应（E3）。
* **motif**：方向来自 carrier-vs-background 实测效率（attribution 无符号）；富集 HeLa-only；`model_consistency` 口径放大（E2）；"motif ≠ causal mechanism" 已在代码/表格 caption 声明 ✓。
* **cell-line 异质性**：环境效应（CTCF 在 HL60 反向、H3K4me3 在 HEK293T −0.0168）+ 位置 18 碱基效应均 context-dependent；论文已用 context 标签 ✓，但需与 Dnase 常数通道（C1）区分。
* **位置 18**：多模型一致方向（C→A 最强最稳）+ 实测 C−A 差 3/4 细胞系同向 → 属 **exploratory computational hypothesis**，非 confirmatory（Part 9/11）。

---

## Part 9 — Reproducibility

| 项 | 声明 | 实际 | 影响 |
| :--- | :--- | :--- | :--- |
| Python | 3.9/3.10 | **3.12.3** | 行为差异风险 |
| torch | ≤2.3.1 | **2.13.0+cu130** | 训练/数值差异 |
| xgboost | ≤2.0.3 | **3.4.1** | early stopping / predict 行为（G5） |
| numpy | ≤1.26.4 | **2.5.2** | NumPy 2.x 语义 |
| pandas | ≤2.2.2 | **3.0.5** | pandas 3.x 语义 |
| scikit-learn | ≤1.5.0 | **1.9.0** | 指标/切分实现 |
| CUDA | 可选 | 不可用（CPU） | 500+ run 的 CPU 重跑成本 |
| 随机性 | 固定 seed（42/2024） | split/bootstrap/permutation 可复现；torch/cudnn 未启用确定性算法 | 同 seed 大体可复现，未做位级保证 |
| provenance | — | artifact 无 commit/指纹 | 无法判定 artifact 与代码版本对应（G7） |
| cache/stale | — | `data_digging` 跳过已完成 run；`docs/paper_analysis` 11 表为孤本输入 | 旧 artifact 可能被新代码继续引用（G1） |

---

## Part 10 — Result Impact Matrix

| Issue | Severity | Affected result | Needs rerun | Scope | Paper impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| A1 mixed 泄漏 | P0 | mixed 性能、ΔR²、bootstrap、permutation、FDR、Tier | **是** | 448 mixed run 去重重算（或重跑 112） | §3.2 性能、§3.3 环境、Table 2/3、Fig.3/7 |
| A2 LOCO 泄漏 | P0 | LOCO 泛化、Fig.2C | **是** | 448 all run 去重重算 | §3.2 LOCO 段、Fig.2C |
| A3 revcomp 孪生 | P0 | single 位点级泛化（HEK293T/HeLa） | 建议 | 位点级去重或 group split | §3.4/§5 |
| B1 test 复用 | P1 | kernel 比较、模型排名 | 否 | 措辞 | Table 4/Fig.5 |
| C1 零方差通道 | P1 | DNase 在 HEK293T/HeLa 的"无增益" | **是** | 重算时排除/标注 | §3.3/§5 |
| D1 min_edge_fdr | P1 | 统计证据强度表述 | **是**（改名或改口径） | 因子级值 | §2.10/§3.8 |
| D2 两套 CI | P1 | Table 3 CI | **是** | 统一实现 | §3.3 vs §3.8 |
| D4 边表重复 | P1 | 边级分母 2541/1906/166 | **是** | 唯一键 | §3.3/Fig.3C |
| D6 loco_performance 未滤发散 | P1 | Fig.2C/Table 2 | **是** | 1 行修 + 重生成 | Fig.2C |
| F2 Table 2 口径 | P1 | 性能区间/linear 行 | **是** | 重算中位数 | Table 2 |
| E3 样本内 ISM/候选 | P1 | C1 方向性、候选排序 | 是（标注/剔除） | 局部 | §3.8/Table 6 |
| G4 环境不符 | P2 | 复现声明 | 否 | 更新 requirements | §2.11/附录 |

---

## Part 11 — Scientific Readiness

| 分类 | 结论 |
| :--- | :--- |
| **SAFE TO REPORT** | (1) 数据规模/组成/PAM 位置（21–23、22–23 恒 G）；(2) single 域内性能区间（中位 R² 0.035–0.115，**single 行级 0 泄漏**）；(3) 多尺度核配对比较的**方向与量级**（+0.042/+0.056，192 配对，CI 不跨 0，但须注明 test 复用）；(4) PAM 邻近 17–20 为多模型最高归因区域；(5) 方法学结论"核大小 ≠ 模式长度"（三配置中位 4 nt）；(6) 环境因子在**去重前**的结论"未达 Tier 1"（保守方向仍成立） |
| **REPORT WITH CAVEAT** | (1) 位置 18 的方向性（模型内反事实、样本内、7 模型一致）；(2) 跨模型一致性（非独立重复）；(3) motif 候选 GAGG/GGGG（HeLa-only、富集≠机制）；(4) Model-Level Bootstrap Interval（n=7）；(5) ANOVA 不显著（与 edge 级是两个问题）；(6) 合并后的 LOCO 泛化（**须先解决 A2 泄漏**） |
| **REQUIRES RECOMPUTATION** | (1) mixed 全部性能/ΔR²/统计量（A1）；(2) LOCO 泛化（A2）；(3) 环境 ΔR² 的 DNase 部分（C1）；(4) `min_edge_fdr` 与两套 CI（D1/D2）；(5) 边级分母（D4）；(6) `loco_performance`（D6）；(7) Table 2（F2）；(8) motif 一致性标签（E2） |
| **MUST NOT BE CLAIMED** | (1) "AI 设计的新候选"（E3，6.2 % 训练池重叠）；(2) 因果机制/生物学效应（全部为模型行为）；(3) "SOTA 预测性能"（mixed 泄漏 + single 弱信号）；(4) 独立重复/独立验证（跨模型共享数据）；(5) "跨细胞系普适"（cell-line 冲突 + 零方差通道） |

---

## Part 12 — 已知 20 项问题的当前状态

| # | 已知问题 | 状态 |
| ---: | :--- | :--- |
| 1 | mixed cross-cell-line overlap | **Still present**（21 %，已量化） |
| 2 | LOCO 旧实现 | **Verified fixed（代码+数据）**；但当前实现仍受 L2 泄漏影响 → Partially fixed |
| 3 | same-locus revcomp overlap | **Still present**（HEK293T 6.0 %） |
| 4 | candidate pool ↔ training overlap | **Still present**（6.2 %） |
| 5 | signed ISM 样本内 | **Still present**（设计如此，需标注） |
| 6 | test-set / model-selection reuse | **Still present**（结构性） |
| 7 | zero/near-zero variance env | **Still present**（Dnase var=0 in 2/4 系） |
| 8 | LR rank deficiency | **Still present**（rank 60<161；56/192 发散） |
| 9 | position heatmap parser offset | **Still present**（图层面） |
| 10 | Tier minimum-FDR aggregation | **Partially fixed**（R2 改名 + 加 provenance；口径名仍不准 D1） |
| 11 | model-level bootstrap n=7 | **Fixed（命名/语义）**，设计未变 |
| 12 | direction concordance denominator | **Fixed**（R5 分母=全部有效模型；本批数值不变） |
| 13 | numerical divergence threshold | **Partially fixed**（R1 覆盖 permutation；`loco_performance` 仍缺 D6） |
| 14 | prediction summary / aggregation bug | **Still present**（Table 2，F2） |
| 15 | `calculate_delta_R2` seed key | **Unknown/Likely**（D5，未量化） |
| 16 | CNN channel/config mismatch | **Still present**（G2，config 记录不生效） |
| 17 | XGBoost version / best_iteration | **Unknown**（G5，未验证） |
| 18 | environment combination duplicate risk | **Still present（latent）**（H1） |
| 19 | missing / inconsistent config files | **Partially**（`feature_config.user.json` 缺失、HPC 脚本缺失；H2） |
| 20 | paper number ↔ artifact provenance | **Partially**（新增 provenance 文档；Table 2/CI/loco 数值仍有问题） |

---

## Part 13 — Final Issue Extraction（供人工逐条审视）

### Critical Issues

**P0 · A1 — mixed 跨细胞系孪生行导致 test∩train ≈21 %**
**问题：** hct116↔hela 有 2 506 行 `(sgRNA,label)` 完全相同，逐文件整行去重不覆盖跨文件重复，mixed 划分把其中 21 % 放进 test。
**为什么重要：** mixed 的性能与一切增量效应（ΔR²→bootstrap→permutation→FDR→Tier）被记忆化抬高——泄漏子集 R² 0.381/0.690/0.560 vs 干净 0.102/**−0.004**/0.045。
**证据：** `feature_engineering.py` 逐文件 `duplicated(keep="first")`；复现 `divide_data(mixed)`：test∩train = 524–534；泄漏/干净子集 R² 见 Part 4 表。
**状态：** Confirmed

**P0 · A2 — 真 LOCO 亦被同一泄漏污染（hold-out 系 27–51 % test 命中训练池）**
**问题：** 留出细胞系的 guide 通过 L2 孪生行出现在训练用的其他细胞系中（held=hct116 2 152/4 239 = 50.8 %；hela 26.6 %）。
**为什么重要：** 刚合并的 LOCO 泛化数字仍带记忆化成分（0.344 vs 干净 0.196），跨细胞系泛化被高估。
**证据：** 复现 `divide_data(all, cell_line=held)` 的 `(sgRNA,label)` 交集；LOCO run 的泄漏/干净子集 R²（Part 4 表）。
**状态：** Confirmed

**P0 · A3 — single 内同 locus 反向互补孪生跨 train/test**
**问题：** 6.0 % 的 HEK293T test 位点在 train 有 revcomp 孪生（21/21 互为 revcomp，链组合 9 +/-、12 -/+），且两行 label 不同。
**为什么重要：** 位点级近重复使 single 的位点泛化与位置归因偏乐观；也提示同一位点标签不稳定。
**证据：** `(Chromosome,Start,End)` 交集 + revcomp 检验；Part 4 L4/L5。
**状态：** Confirmed

**P0 · A4 — `all`(LOCO) 历史退化曾使全部跨细胞系结论失效**
**问题：** 旧批 `all` 与 `single` 448/448 逐位相同（语义上"留出系"即自己）。
**为什么重要：** 此前所有"跨细胞系泛化"表述无效；现已合并真 LOCO（0/448 相同），但论文文本仍待更新。
**证据：** `logs/loco_rerun_20260913.log`、合并后 `all_experiments.csv`（all vs single 0/448）。
**状态：** Verified fixed（数据层已修；文本待改）

### Major Issues

**P1 · B1 — 网格模型用同一 test split 做选择并报告**
**问题：** kernel/模型比较与最终性能取自同一次 70/15/15 的 test 指标（无嵌套 CV）。
**为什么重要：** Table 4/Fig.5 与模型排名带选择偏置。
**证据：** `workflows/training/data_digging.py` 单次划分；`cnn_kernel_paired.csv` 由该 test 指标配对得到。
**状态：** Confirmed

**P1 · B2 — ultimate 超参选择后报告同一 CV 值**
**问题：** 10 折 CV 取最大配置，`cv_r2_mean` 直接作为报告值。
**为什么重要：** CV R² 是选择后估计，向上偏。
**证据：** `workflows/prediction/predict.py:516-522`；`ultimate_*_config.json`。
**状态：** Confirmed

**P1 · C1 — 表观通道零方差/近零方差未过滤**
**问题：** HEK293T/HeLa 的 Dnase 恒 1（var=0），HeLa CTCF var=0.010，RRBS 第 23 位 4 系恒 0。
**为什么重要：** 这两系"DNase 无增益"是常数特征假象；不能作为生物学证据。
**证据：** `feature_integrity_audit.csv`（npy 逐通道实测）。
**状态：** Confirmed

**P1 · C2 — LR 秩亏/病态使系数与 p/FDR 不稳**
**问题：** hct116 sequence-only rank 60 < 161；56/192 线性 run 发散。
**为什么重要：** LR 系数/p/FDR 与 Importance–ΔR² 只在稳定子集内可信。
**证据：** `all_experiments.csv`（Numerical rank、Condition number、|R²|>10 计数）。
**状态：** Confirmed

**P1 · D1 — `min_edge_fdr` 名不副实**
**问题：** 实际取该因子 **main-effect** 检验的最小 FDR（63 行），文档/论文称 "Minimal **Edge**-level FDR"。
**为什么重要：** 统计证据强度被说强 4–8 倍；真 edge 级最小 FDR（CTCF 0.0639/DNase 0.0160/H3K4me3 0.0320/RRBS 0.0746）全部 >0.05。
**证据：** `integration.py` 以 `factor == f` 过滤（edge 行 `factor` 为 NaN）；`permutation_results.csv` 逐 test_type 最小 FDR。
**状态：** Confirmed

**P1 · D2 — 因子级 bootstrap 两套实现数值不同**
**问题：** `tasks.py` 与 `make_assets.py` 各一套，DNase 等 CI 差在第 3 位小数。
**为什么重要：** 论文 §3.3 与 §3.8 同篇引用不同数值。
**证据：** 两文件的 CI 对照（Part 6/10）。
**状态：** Confirmed

**P1 · D3 — ANOVA 从不做 FDR，且 `FdrFamilyConfig` 含死配置**
**问题：** `anova_results.csv` 无 FDR 列；`apply_fdr` 只覆盖 permutation 与 motif。
**为什么重要：** 10 个 blocked 项 + 28 个 per-group 项未校正。
**证据：** `analysis/stats/tasks.py::apply_fdr`；`config.py` enabled_families。
**状态：** Confirmed

**P1 · D4 — 边表重复行放大分母**
**问题：** `environment_edges.csv` 2 651 行 vs 唯一键 2 016（635 条重复全在 mixed）。
**为什么重要：** 论文"2 541 条边/166 条不跨 0"等分母被放大。
**证据：** 按 split 计数（mixed 859 vs 唯一 224）。
**状态：** Confirmed

**P1 · D5 — `calculate_delta_R2` 基线匹配不含 seed**
**问题：** 基线 key 无 `random_seed`，与同 seed 配对原则不一致。
**为什么重要：** mixed 表的 `delta_R2` 可能跨 seed 相减。
**证据：** `collect_results.py:221-243`。
**状态：** Likely

**P1 · D6 — `loco_performance.csv` 未过滤发散行**
**问题：** `linear/hct116` LOCO R² = −2.85×10¹⁹ 直接进入资产。
**为什么重要：** Fig.2C/Table 2 出现垃圾值。
**证据：** `loco_performance.csv`；`analysis/prediction.py::loco_performance` 直接 `groupby.mean()`。
**状态：** Confirmed

**P1 · E1 — CNN 重要性两套口径并存**
**问题：** `key_regulatory_biomarkers` 用 `CNN_ISM`+`ISM_SNR`；`importance_metrics` 用 `CNN_IG` 且排除 ISM。
**为什么重要：** 引用"CNN 重要性"时必须说明用哪一套，否则论文自相矛盾。
**证据：** `importance_extraction.py:735-741` vs `importance_metrics.py:55-58,73`。
**状态：** Confirmed

**P1 · E2 — motif 一致性口径放大**
**问题：** `model_consistency` 取值 2–24，而实际 kernel 变体只有 3；340 个 motif 因 ≥2 被判 Moderate。
**为什么重要：** motif 稳定性/证据等级被高估。
**证据：** `motif_candidates.csv` + 训练矩阵（k3/5/7）。
**状态：** Confirmed

**P1 · E3 — signed ISM 与候选打分均为样本内**
**问题：** 位置 18 signed ISM 使用模型训练时见过的 5 080 条 guide；`todo_data` 6.2 % 落在训练池。
**为什么重要：** 不能称"AI 设计的新候选"；方向性结论只能作为 model-internal counterfactual。
**证据：** `results/analysis/position18_signed_substitution_ISM_per_sample.csv`（5080 条）；`todo_data.CSV` ∩ 训练 sgRNA = 11 027/176 432。
**状态：** Confirmed

**P1 · F1 — 位置热图解析器错位**
**问题：** `analysis/visualization.py:177-180` 对 1-based 源（linear/xgboost/mlp）再 +1 → 图位置 2..23（无 1）；分析层 parser 正确。
**为什么重要：** 热图与 attribution 表不一致，可能被误读为"位置 1 无重要性"。
**证据：** 该函数 vs `attribution/extractors._parse_position_channel`；产物 `summary/plots/01_position_heatmaps/*_{linear,xgboost,mlp}*.png`。
**状态：** Confirmed

**P1 · F2 — Table 2 口径错误**
**问题：** 声称"对实验取中位"，实为对单行（`prediction_summary` 每 model×split 1 行）取中位；`R2_sd=NA`、`diverged` 只计 1、linear 未剔发散。
**为什么重要：** 论文 Table 2 的 linear 行 = −1.87×10¹⁶，性能区间与正文口径不一致。
**证据：** `paper/tables/tab2_prediction.tex`；`make_assets.py:487-508`。
**状态：** Confirmed

### Reproducibility / Interpretation Issues

**P2 · G1 — 11 个 `docs/paper_analysis` CSV 无仓库内生成脚本**
**问题：** README 称均由 `make_assets.py` 生成，实际该脚本只读它们（只有 2 个文件由它写）。
**为什么重要：** Fig.4/5、Table 3–4 无法端到端复现。
**证据：** `make_assets.py:706-714`；`docs/paper_analysis/README.md:3-5`。
**状态：** Confirmed

**P2 · G2 — `conv_channels1/2` 从不生效**
**问题：** config 记录 32/64，模型实际用默认 64/64/128。
**为什么重要：** 配置无法复现真实架构。
**证据：** `core/models/cnn/cnn.py::train` 形参名；`workflows/training/train.py:428` 按签名过滤。
**状态：** Confirmed

**P2 · G3 — `loaders.py` 丢列**
**问题：** 仅保留 16 列，丢弃 `cell_lines/input_shape_*/sequence_kernel`。
**为什么重要：** 分析链失去退化检测与样本量分层能力（LOCO 退化长期未被发现的原因之一）。
**证据：** `analysis/data/loaders.py:38-87`。
**状态：** Confirmed

**P2 · G4 — 安装环境与 requirements 严重不符**
**问题：** python 3.12.3、torch 2.13.0、xgboost 3.4.1、numpy 2.5.2、pandas 3.0.5、sklearn 1.9.0 vs requirements 的 3.9/3.10、≤2.3.1、≤2.0.3、≤1.26.4、≤2.2.2、≤1.5.0。
**为什么重要：** 全部产物的复现声明与实际环境不符；xgboost/numpy 跨大版本。
**证据：** `environment_reproducibility_audit.csv`。
**状态：** Confirmed

**P2 · G5 — XGBoost early stopping / iteration_range 未对齐**
**问题：** 训练用 `early_stopping_rounds=30` 与 `best_iteration`，predict 未传 `iteration_range`。
**为什么重要：** 预测是否按 best_iteration 截断未验证（版本差异下风险更高）。
**证据：** `core/models/xgboost/xgboost.py:527,572,213-215`。
**状态：** Likely

**P2 · G6 — QC 缺关键检查**
**问题：** 无 PAM/NGG、标签范围、跨文件/跨细胞系泄漏、表观零方差、shape-vs-schema 检查。
**为什么重要：** 上述 P0/P1 问题因此长期未被自动发现。
**证据：** `analysis/data_QC.py`；`cell_line_division.py:98-110`。
**状态：** Confirmed

**P2 · G7 — artifact 无 provenance**
**问题：** 无 git commit / dataset fingerprint / config hash 写入产物。
**为什么重要：** 无法判定 artifact 与代码版本对应，存在 "old artifact + new code" 歧义。
**证据：** run 目录内容（`*_info.txt` + config）。
**状态：** Confirmed

**P2 · G8 — `n_train/valid/test` 在分析层缺失**
**问题：** 该字段未保留/解析（全 NA）。
**为什么重要：** 无法做样本量分层与功效评估。
**证据：** `analysis/data/loaders.py`。
**状态：** Confirmed

**P2 · H1 — 环境组合规范化仅在 `data_digging` 内做**
**问题：** 17→16 去重只在 `_canonicalize_combinations` 内；绕过入口（手工 `workflows/training/train.py`）会重复计数 `all`。
**为什么重要：** 后续重跑若绕过入口会污染实验矩阵。
**证据：** `workflows/training/data_digging.py:63-94`。
**状态：** Confirmed

### Minor Audit Issues

**P3 · H2 — 文档 stale/自相矛盾**
**问题：** 文档仍称 LOCO"不可达/抛 ValueError"（代码已修）；QC 离群维写 161（实际 184）；运行矩阵写非 CNN 每 split 64（实际 256，已修）；README 关于 models/logs 自相矛盾；HPC 协议引用 3 个不存在的脚本。
**为什么重要：** 影响审计效率与开源可维护性（不影响科学结论）。
**证据：** `docs/project_pipeline_and_code_documentation.md:11,952,1055,1076,3094`、`README.md:382 vs 267`、`docs/HPC_EXPERIMENT_PROTOCOL.md:29,42,110`。
**状态：** Confirmed

---

## Part 14 — 汇总

```text
Confirmed: 26
Likely:     2
Possible:   0
（另 1 项 Verified fixed：A4）

P0: 4
P1: 15
P2: 9
P3: 1
```

**PROJECT SCIENTIFIC READINESS: REQUIRES RECOMPUTATION**（mixed 与 LOCO 相关的全部性能/增量/统计结论；其余为 READY WITH CAVEATS）

**最小必要修复路径（按影响排序，未执行）**

```text
P0: A1 全局按 (sgRNA,label) 去重 → 重算/重跑 mixed；A2 用同一去重后的池重算 LOCO；
    A3 位点级(revcomp)去重或 group-aware split；A4 已完成（论文文本同步）
P1: C1 零方差通道标注/排除 → D6 loco_performance 过滤 → F2 Table 2 重算 → D4 边表唯一键
    → D1 min_edge_fdr 改名或改口径 → D2 统一 CI → D3 ANOVA FDR 声明 → E1/E2 口径二选一
    → E3 标注 in-domain rediscovery → F1 热图 parser
P2: G4 requirements 校正 → G1 补生成脚本 → G7 provenance 字段 → G6 QC 补检查 → G3 loader 补列
    → G2/G5/G8/H1
P3: H2 文档同步
```
