# 项目全貌地图：从原始数据到四维度科学发现结论

> 对象：`/home/zhang/bioprogram/Submit`，批次 `results/batches/batch_20260909_full`（1 344 runs）。
> 原则：全部结论以**当前 production code 与真实产物**为准；与文档冲突处已在附录列出。
> 本文不解释统计工具的定义，只解释**每个分析为什么存在、与谁互补、不能回答什么**。
> 相关细节文档：`docs/statistics_and_parameters_zh.md`（参数与加权）、`docs/audit/evidence_tier_scientific_definition.md`（四维定义）、`docs/audit/evidence_tier_before_after.md`（Tier 结果）。
> 补充勘察记录（并行生成）：`docs/_map_data_and_qc.md`、`docs/_map_analysis_and_evidence.md`。

---

# Part 1 — 一张完整 Pipeline（阶段 → 代码 → 产物）

```text
[1] Input
    data/raw/{hct116,hek293t,hela,hl60}.csv   (sgRNA + CTCF/Dnase/H3K4me3/RRBS + Normalized efficacy)
        │
[2] Feature Engineering            core/features/engineering/feature_engineering.py (one-hot / env channel / dedup / schema)
        ├──> data/processed/{cell}_features_23x8.npy      (N,23,8)  ← 3D 模型输入
        ├──> data/processed/{cell}_features_184.npy       (N,184)   ← 2D 模型输入
        ├──> data/processed/{cell}_labels.npy             (N,)      ← 预测目标
        ├──> data/processed/{cell}_metadata.csv           (sgRNA/Cell line/Strand/…)  ← 位置与分层依据
        └──> data/processed/feature_schema.json + feature_engineering_summary.csv
        │
[3] QC / Validation                analysis/data_QC.py（KDE 离群/缺失/GC）、analysis/data/validation.py（指标一致性）
        │                          + core/data/splitting/cell_line_division.py::validate_cell_line_dataset（shape/NaN）
        └──> workspace/qc_sessions/qc_*/{quality_report.md, outliers_detailed_report.csv, qc_summary.json}
        │
[4] Split / Experimental Design    core/data/splitting/cell_line_division.py（single/all/mixed；LOCO 分支 0.85/0.15）
        │                          + core/features/channels/cell_environment_combination.py（环境列 mask 置零）
        └──> 每次 run 的 *_config.json（cell_lines / input_shape_* / random_seed / environment）
        │
[5] Training（不需细讲）           workflows/training/data_digging.py → workflows/training/train.py → src/{cnn,mlp,transformer,xgboost,linear_regression}
        └── 每条 run 三类资产：models/<batch>/<run>/{model}_model.pt|pkl   ← checkpoint
                               results/<batch>/<run>/{model}_{metrics.json, predictions.csv,
                                 feature_importance.csv, training_history.csv, info.txt, validation_*}
                               logs/<batch>/<run>/training.log
        └── summary/metrics_tables/all_experiments.csv（1 344 行，逐实验指标 + 全部 split/seed/环境元数据）
        │
[6] Post-hoc Scientific Analysis   analysis/pipeline.py（任务编排）→ analysis/environment|stats|attribution|cellline|sequence|evidence
        ├── Effect            : environment_conditional_delta_r2 / environment_main_effects / environment_edges /
        │                       environment_interactions / anova_results / cnn_kernel_paired（多尺度核）
        ├── Importance        : attribution_summary（linear 系数、XGB gain/SHAP、MLP IG、CNN IG/ISM、Transformer attention）
        ├── Statistical Evid. : bootstrap_results（逐样本配对）/ bootstrap_main_effects（模型级）/
        │                       bootstrap_cellline_effects / permutation_results（edge/main/interaction）+ BH-FDR /
        │                       anova_results / LR 训练侧 p、FDR
        ├── Robustness        : cellline_effects（context 标签）/ environment_by_cellline /
        │                       cross_model_position_consistency / kernel_position_profile / mixed 4 seed
        └── Motif             : motif_candidates / motif_instances / motif_enrichment / motif_consistency / motif_evidence
        │
[7] Evidence Integration           analysis/evidence/integration.py::environment_evidence_matrix + motif_evidence_rows
        └──> tables/evidence_matrix.csv（600 行）→ summary/06_evidence_integration.md
        │
[8] Candidate Factors / Hypotheses  analysis/evidence/hypothesis.py → summary/07_biological_hypotheses.md
        │                          + paper/tables/tab6_candidates.tex（C1 位置18 / C2 GAGG / C3 GGGG / CTGG 参考）
        │
[9] Independent Validation          ❌ 本仓库未执行（湿实验/外部数据），只给出建议实验
```

**训练阶段最终提供给下游的资产（下游只读这些）**

| 资产 | 位置 | 下游谁在用 |
| :--- | :--- | :--- |
| prediction 表 | `<run>/<model>_predictions.csv`（test cohort，含 `y_true/y_pred`） | 逐样本配对 bootstrap、置换检验（edge / main / interaction） |
| metrics | `<run>/<model>_metrics.json`、`summary/metrics_tables/all_experiments.csv` | ΔR²、ANOVA、cell-line 分层、Tier 的覆盖度 |
| checkpoint | `models/<batch>/<run>/*_model.pt` / `.pkl` | CNN/MLP/Transformer 的 IG、ISM、attention（**仅训练时算过一次，分析层不重算**） |
| feature importance 表 | `<run>/<model>_feature_importance.csv` | attribution 汇总、motif 发现、候选位置 |
| feature mapping / schema | `feature_schema.json`、`feature_names`、`plan["keep"]` | attribution 位置对齐、ISM、motif 映射、ANOVA 变量名 |
| metadata | `{cell}_metadata.csv` | 位置 18 碱基分组、GC、上下文；**也提供 sgRNA→位置语义** |
| split 元数据 | `all_experiments.csv` 的 `split_type/cell_line/random_seed/environment/model/sequence_kernel` | robustness 分层、cell-line 异质性、跨模型与跨 seed 聚合 |

---

# Part 2 — Downstream Analysis Dependency Graph

```text
prediction table (test cohort, y_true/y_pred)
├── ΔR²（逐样本配对，同 split/cell/model/seed 的 S 与 S+e）   → environment_conditional_delta_r2
│     ├── 因子主效应（先跨背景、再跨 seed）                  → environment_main_effects
│     │     ├── 边级 / 因子级 bootstrap                        → bootstrap_results / bootstrap_main_effects
│     │     ├── 置换检验（sign-flip）                          → permutation_results
│     │     ├── cell-line 分层与 context 标签                   → cellline_effects / environment_by_cellline
│     │     └── Evidence Tier（覆盖度/一致率/CI/增益门/统计门） → evidence_matrix
│     └── factorial DAG（节点/边/交互）                        → environment_nodes/edges/interactions
├── per-sample 损失差                                          → permutation（edge / interaction）
└── 与 R² 无关的逐样本配对检查                                  → metric_inconsistency（异常报告）

metrics 表 (experiment level, R²/MAE/RMSE/…)
├── prediction_summary / loco_performance                      → 论文 Table 2 / Fig.2
├── 配对方差分析（blocked factorial + per-group additive）      → anova_results
└── 多尺度核配对 ΔR²（同 cell/env/seed，k5−k3、k7−k3）          → cnn_kernel_paired（论文 Table 4 / Fig.5）

checkpoint + schema
├── Integrated Gradients（MLP / CNN / Transformer 按实现）      → attribution_summary.*_ig
├── CNN ISM（channel toggle，无符号幅值）                        → attribution_summary.cnn_ism（+ ISM_SNR）
├── Attention（Transformer，仅辅助）                             → attribution_summary.transformer_attention
└── 有符号替换 ISM（本会话新增，专门脚本）                        → results/tables/paper/position18_signed_substitution_ISM*

feature importance 表 + schema
├── 位置/通道归因汇总（先位置×通道，再模型内归一化）             → attribution_summary
├── 位置谱 / 区域谱                                              → results/tables/paper/*（由 analysis/reporting/paper_analysis/build_paper_tables.py 生成）
├── kernel 位置谱（跨 kernel 不混合）                            → kernel_position_profile
├── 跨模型位置一致性（10 个模型对等权）                          → cross_model_position_consistency
└── motif：seqlet 提取 → 聚类/consensus → 富集 → 稳定性          → motif_candidates / motif_instances /
                                                                   motif_enrichment / motif_consistency

metadata
├── 位置 18 碱基分组（sgRNA[17]）                               → position18_efficacy_by_base
├── GC / 长度 / PAM 校验                                        → QC 报告、PAM 定义（21–23）
└── 位置 18 归因占比                                            → position18_attribution

evidence_matrix
└── Tier → 假设生成（Tier1/2/3 才进入）                          → 07_biological_hypotheses
                                                                    → 论文候选表 C1/C2/C3
```

---

# Part 3 — 四维度知识地图（每条边解释"为什么放在一起"）

```text
Effect（改变/加入因素后，模型输出或预测性能变了多少）
├── ΔR²（edge / factor / kernel 配对）
│     · 单位：实验级留出 R² 的配对差；回答"加入这个环境通道是否提供增量预测信息"
│     · 不能回答：方向（正负由模型行为给出，不等于生物学方向）、是否真实（需 Statistical Evidence）
├── signed ISM Δ = f(x_mut) − f(x_WT)
│     · 单位：单条序列、单个位置/碱基的模型输出变化（有符号）
│     · 与 ΔR² 互补：ΔR² 是"因子层面"的增量信息，signed ISM 是"具体序列改变"的模型响应
└── ANOVA effect（全局因子/交互的边际贡献，η²=SS_term/SS_total）
      · 与 ΔR² 互补：ΔR² 是特定条件下的增量，ANOVA 是整个析因设计上的方差分解

Importance（模型在预测时依赖什么）
├── SHAP（XGBoost）/ IG（MLP、CNN）/ attention（Transformer，仅辅助）
│     · 回答"模型内部把多少决策权重放在这个特征/位置"
│     · 不能回答"改变它会不会真的改变预测"（那是有符号 perturbation 的问题）
├── CNN ISM magnitude（|Δ| 的均值）
│     · 回答"模型输出对翻转该通道有多敏感"；无符号
└── 与 Effect 的边界：Importance 高 ≠ Effect 大（模型可以依赖一个对性能没有增量的特征）

Statistical Evidence（观察到的 effect 有没有统计证据）
├── 逐样本配对 bootstrap（edge 级，B=2000）      → matched experiment-level uncertainty
├── 模型级 bootstrap（因子级，unit=模型，n=7）    → cross-model stability（**不是** guide 总体抽样）
├── permutation（sign-flip，B=1000，三类检验）    → 对"增量为 0"的零假设做随机化检验
├── BH-FDR（按科学问题族隔离）                    → 解决大量 edge/factor 检验的多重比较
└── LR 的 p/FDR                                  → 线性系数这一 Effect 的统计证据

Robustness（换条件后是否仍成立）
├── 跨模型（7 个配置，等权）        → 压力测试"是否依赖某个架构"
├── 跨 seed（mixed 42–45）          → 压力测试"是否依赖初始化/划分随机性"
├── 跨 cell line（4 系 + context 标签）→ 压力测试"是否为普适因素"
├── 跨 split（single/mixed/all）    → 压力测试"是否依赖训练数据范围"（⚠ 本批 all 退化，见附录）
├── 跨 kernel（k3/5/7）             → 压力测试"是否依赖感受野"
└── 方向一致率 / CI 稳定性          → 把"稳不稳"压缩成可进 Tier 的判据
```

**为什么必须四个维度一起看**：单一维度都能被"便宜的假象"满足——
Importance 高可能只是模型对噪声通道的依赖；Effect 大可能来自单次划分的偶然；
统计显著可能只是多重比较未校正；跨模型一致可能只是共享数据导致的同源偏差。
四维组合后才允许说"这是一个值得进入候选列表、但仍未经验证的**计算证据**"。

---

# Part 4 — 科学问题 → 分析组合 → 结论

### Q1 环境因素是否提供额外预测信息？（本项目最强否定结论）

```text
Effect        : ΔR² = R²(S∪{e}) − R²(S)，逐样本配对；4 个因子 × 7 模型 × 9 上下文的模型等权均值
                全部 |mean ΔR²| < 0.01（CTCF −0.00095 / DNase −0.00202 / H3K4me3 −0.00594 / RRBS −0.00932）
Statistical   : 逐样本配对 bootstrap CI（跨模型）→ CTCF、DNase 跨 0；置换检验按族 BH-FDR
                因子级取值 = **main-effect 检验**的最小 FDR（存在性证据；CTCF 0.0093 / DNase 0.0140 /
                H3K4me3 0.0093 / RRBS 0.0093，FWER 上界 0.23–0.25）。
                ⚠ 若改用真正的 **edge 级**最小 FDR，则为 CTCF 0.0639 / DNase 0.0160 / H3K4me3 0.0320 /
                RRBS 0.0746（全部 > 0.05）——命名与实现口径不一致，见附录 #9
Importance    : 环境通道的归因份额很小；且环境通道在 sequence-only 配置下被 mask 置零，模型本就主要依赖序列
ANOVA         : blocked factorial（响应=留出 R²，区组=model/cell/split）主效应 p=0.056–0.663，
                交互 p≥0.26，η² ≤ 0.002 → 全局层面也未检出
Robustness    : 7 模型方向不一致（4 个因子全部 model_direction_conflict=True）；cell-line 上下文冲突（CTCF、H3K4me3）
Evidence Tier : 环境因子 0 个 Tier 1（RRBS = Tier 2，其余 Inconclusive）
→ 结论：本批数据不支持"表观环境通道提供可检测的增量预测价值"；这是计算层面的否定证据，不等于"生物学无关"
```

### Q2 哪个序列位置最受模型依赖？

```text
Importance    : 位置谱（CNN IG / ISM 幅值、MLP IG、XGB TreeSHAP、Transformer attention）
                → PAM 邻近种子区（17–20）在 4/5 模型类中为最高归因区域；位置 18 在跨模型平均谱中排序第 1
Statistical   : 无（位置谱本身不是检验；一致性用 Robustness 度量，不用 p 值）
Robustness    : 跨模型位置谱平均 Spearman 0.28–0.61、top-3 overlap 0.30–0.53（模型间中等一致，不是完全相同）
                跨 cell line：位置 18 在 HCT116/HeLa 为众数峰，Transformer attention 峰值在 1–2（模型依赖）
→ 结论："位置 18 是被多模型重复优先化的**位置**"——这是 Importance 结论，不是 Effect 结论
```

### Q3 position 18 是否存在方向性 nucleotide effect？

```text
Effect(反事实) : 有符号替换 ISM（本会话新增）：把位置 18 的 C 换成 A/G/T，7 个 pooled 模型全部给出负 Δ
                C→A 平均 −0.067、C→G −0.050、C→T −0.057（模型间范围 −0.015…−0.082）
Statistical    : 每模型/替换的 bootstrap 95% CI（B=10000，sample-level）；40 个 (model×kernel×cell) 配置中
                C→A 38/40 同号、C→G 36/40、C>T 37/40；C→A 在 33/40 配置中是"最负"的替换
Importance     : 位置 18 的归因份额高（C 通道占比：XGB 0.64–0.77、MLP 0.28–0.63、CNN 0.23–0.37）
Robustness     : 细胞系异质——HCT116/HeLa 强负、HEK293T/HL60 接近 0（部分配置甚至为正）；实测 C−A 差
                HCT116 +0.090、HeLa +0.092、HL60 +0.027、HEK293T −0.015 与模型方向在 3/4 细胞系一致
→ 结论：**方向明确的模型预测（C→A 降幅最大且最稳）**，且与实测关联在多数细胞系同向；但模型在 obs 数据上训练，
  仍属 computational evidence（见 Part 5）
```

### Q4 哪些因素具有 cell-line specificity？

```text
Effect        : environment_main_effects 按 cell line 分层（environment_by_cellline）
                cellline_effects → context 标签（Context-consistent / -dependent / -conflicting / Uncertain）
                CTCF 在 HL60 反向；H3K4me3 在 HEK293T −0.0168 / HL60 +0.0065
Importance    : 位置 18 的归因份额与 ISM 幅值同样呈细胞系差异（HCT116/HeLa A/C > G/T）
Statistical   : 每 (split,factor,cell_line) 的模型级 bootstrap CI；反向 cell line 的 CI 与主体重叠时不升级为冲突
Robustness    : 方向占比 + 幅度异质性(max/median) + CI 重叠三判据 → 四标签
Evidence Tier : cell-line 冲突标签是 Tier 的**一票否决**项（CTCF、H3K4me3 因此 Inconclusive）
→ 结论：环境效应与位置 18 的碱基关联都表现为 **cell-context-dependent**，不是普适因素
```

### Q5 哪些发现跨模型稳定？

```text
Robustness(跨模型) : (a) PAM 邻近区域最高归因：4/5 模型类一致 → 稳定
                     (b) CNN 核 k5/k7 > k3：192 组配对 ΔR² +0.0423 / +0.0557，CI 不跨 0，88.5%/95.8% 为正 → 稳定
                     (c) 位置谱形状：Spearman 0.28–0.61 → 中等一致
                     (d) 环境因子方向：一致率 0.71–0.86（但幅度不可忽略）→ 不稳定
Importance         : attention 与梯度/树归因不一致（注意力不区分碱基通道）→ 模型依赖
→ 结论：**方法学层面**的结论（PAM 邻近重要、更宽核更好）跨模型稳定；**生物学层面**的候选（位置 18、环境因子）
  则依赖模型类与细胞系
```

### Q6 哪些因素值得实验验证？

```text
候选来源 = Effect（有符号、方向明确） + Importance（多模型优先化） + Robustness（跨模型/细胞系一致性）
        − 已被统计证据否定的项（环境因子未被 Tier 1 认可）
C1 位置 18 的 C→A（signed ISM 最强最稳；实测 C−A 差最大且在 HCT116/HeLa 同向）
C2/C3 PAM 邻近 motif GAGG / GGGG 的核心破坏（HeLa 富集 FDR 0.030 / 7×10⁻⁶，但 cell-line support = 1）
参考 CTGG（支持度最高 1273 但富集 FDR = 1.0，不作为候选）
→ 结论：实验设计应写成"检验**是否存在**效应 + 方向预测已冻结"，而不是把模型预测当作已知因果
```

---

# Part 5 — 每个结论的"证据边界"

### C1 · 位置 18 的 C→A 是候选方向性突变
* **可以支持**：7 个 pooled 模型对 18: C→A 全部给出**负向**、且是三种替换中幅度最大且最稳定（38/40 配置同号）的预测；位置 18 被多模型优先化；实测 C−A 效率差在 HCT116/HeLa/HL60 为正、与模型方向一致。
* **不能支持**：C→A 在真实细胞中**必然**降低编辑效率；位置效应与碱基效应的分离（两者在本数据中纠缠）；因果机制（模型在观测数据上训练，Δ 是模型行为不是细胞行为）。
* **还需要**：WT vs C→A 的最小扰动湿实验（同一 sgRNA、同一 readout、多细胞系）；若能获得独立数据集（非训练来源）也可作为外部验证。

### C2 · 环境（表观）通道不提供增量预测价值
* **可以支持**：四个因子的模型等权平均 |ΔR²| < 0.01；跨模型 CI 有两个跨 0；方向在 7 模型间不一致；blocked factorial ANOVA 主效应 p=0.056–0.663、交互 p≥0.26；本批无环境因子达到 Tier 1。
* **不能支持**：表观遗传在生物学上不重要（编码方式为逐位点二值、且与序列特征冗余）；"ΔR²=0.0093 就是无效应"（它是不显著/未达门，不是等价于零）。
* **还需要**：连续型表观特征（信号强度而非二值）、更精细的结合位点注释；独立批次复现；或改用能提供统计功效的设计。

### C3 · PAM 邻近区域（17–20）是最重要的序列区域
* **可以支持**：4/5 模型类独立给出该区域最高归因；位置 18 在跨模型平均谱中第 1；区域均值随核增大向 PAM 邻近集中。
* **不能支持**：该区域内的**具体碱基规则**（位置 17–20 是序列语法的一部分，不等价于某个可编辑的生物学元件）；因果关系。
* **还需要**：饱和突变扫描（wet）+ 独立数据；以及把位置效应与碱基效应解耦的设计（例如固定背景的多位置替换）。

### C4 · 更宽的 CNN 感受野更好（k5/k7 > k3）
* **可以支持**：192 组严格配对、ΔR² +0.042 / +0.056、CI 不跨 0、正比例 88.5%/95.8%、分层一致。
* **不能支持**：k 越大越好（只测了 3/5/7）；核大小是生物学模式长度（三配置提取的模式长度中位数都是 4 nt）。这是**模型层面**结论。
* **还需要**：更大核范围；不同架构（attention/RNN）对照；同一结论在独立数据上的复现。

### C5 · motif 候选 GAGG / GGGG 与效率相关
* **可以支持**：seqlet 支持度与富集（HeLa：OR 1.11 FDR 0.030；OR 1.38 FDR 7×10⁻⁶），方向由"携带者 vs 背景"的实测效率对比给出。
* **不能支持**：motif 是模型的因果机制；跨细胞系普适（cell-line support = 1）；motif 与位置 18 的独立贡献。
* **还需要**：≥2 个细胞系的重复富集；motif 破坏实验；机制层面（例如 Cas9 结构/PAM 相互作用）验证。

### C6 · 跨细胞系泛化（LOCO）
* **可以支持**：目前**不能**支持任何跨细胞系泛化结论——本批 `all`（LOCO）划分退化为 `single`（`cell_lines` 长度 1、train+valid+test = 自身样本数、448/448 指标与 `single` 逐位相同）。
* **不能支持**：论文中"留一细胞系"的表述（须改为不可用或待重跑）。
* **还需要**：用修复后的 runner（`--cell-lines` 全量 + `--cell-line` 留出、训练池 85/15）重跑 448 次 `all` 实验（不需要重训 `single`/`mixed`）。

### C7 · 证据分级本身
* **可以支持**：Evidence Tier 是对 coverage / concordance / 稳健性 / 统计支持 / 最小预测增益的**收敛性评级**；本批环境因子最高只有 Tier 2。
* **不能支持**：Tier 与效应量大小、生物学重要性、因果性、显著性排序的等价。
* **还需要**：若要把某因子写成"重要"，需要**独立**（非同一模型族的同源证据）的实验或外部数据。

---

# Part 5b — 数据完整性缺陷对结论的影响（本轮核实，均为 production 产物级事实）

这三条不属于"文档笔误"，而是**会影响结论解释**的数据/代码缺陷，使用本文档任何结论前必须先读本节。

### (i) mixed 划分存在跨细胞系孪生行 → test 与 train 重叠约 21 %

* 事实：hct116 与 hela 之间有 **2 506 行**在 `(sgRNA, 标签)` 上完全相同（另有 hct116∩hl60 = 27、hela∩hl60 = 34）；
  去重是**逐文件整行** `duplicated(keep="first")`（2233 行全部落在 hek293t），因此跨细胞系的重复行**全部保留**。
* 复现（`divide_data(split_type="mixed")`）：

| seed | test n | `(sgRNA,label)` 同时出现在 train | 占比 | 同时出现在 valid |
| ---: | ---: | ---: | ---: | ---: |
| 42 | 2 513 | **541** | **21.5 %** | 130 |
| 43 | 2 513 | 531 | 21.1 % | 116 |
| 44 | 2 513 | 532 | 21.2 % | 127 |
| 45 | 2 513 | 522 | 20.8 % | 107 |

* 污染链：mixed test R²/RMSE 被高估 → `prediction_summary` → 环境 ΔR² → 逐样本配对 bootstrap → permutation → BH-FDR → **Evidence Tier**。
* 边界：`single` 划分实测 **0 泄漏**；因此"域内（single）"结论不受影响，而"合并训练（mixed）"的绝对性能与增量效应都需打折看待。
* 现有 QC（列/缺失/整行去重/长度/非 ACGT/形状/NaN/单态位点/70 % 门禁/离群/指标同号）**没有**任何跨细胞系或序列级泄漏检测。

### (ii) 表观通道存在零方差/近零方差轨道（QC 未捕获）

从 `{cell}_features_23x8.npy` 的通道 4–7（CTCF/Dnase/H3K4me3/RRBS）实测：

| cell line | CTCF frac₁ (var) | **Dnase frac₁ (var)** | H3K4me3 frac₁ (var) | RRBS frac₁ (var) |
| :--- | :--- | :--- | :--- | :--- |
| hct116 | 0.866 (0.116) | 0.951 (0.047) | 0.840 (0.134) | 0.009 (0.009) |
| **hek293t** | 0.669 (0.221) | **1.000 (0.0000)** | 0.797 (0.162) | 0.006 (0.006) |
| **hela** | **0.990 (0.010)** | **1.000 (0.0000)** | 0.972 (0.027) | 0.010 (0.010) |
| hl60 | 0.384 (0.237) | 0.974 (0.026) | 0.815 (0.151) | 0.012 (0.011) |

* **HEK293T 与 HeLa 的 Dnase 通道恒为 1（零方差）** → 这两个细胞系的 `sequence_dnase*` run 在结构上不可能获得任何增益；
  因此"DNase 无增量价值"在这两个细胞系是**常数特征造成的假象**，不能作为生物学证据。
* CTCF 在 HeLa 接近恒定（0.990）、RRBS 第 23 位在**全部 4 个细胞系**恒为 0 → 秩亏（hct116 sequence-only 线性 `Numerical rank=60 < 161`）与近零增益部分来自设计，而非生物学。
* 现有 QC 只对 `sgRNA` 做单态位点检测（仅报 pos22/23 恒为 G），**没有**对表观通道做零方差检测。

### (iii) 位置热图使用了错位的 legacy 解析器（只影响图，不影响 attribution 表）

* `analysis/visualization.py::parse_feature_position_channel:177-180` 对所有 ≤22 的位置值一律 +1：
  对 **1-based** 的 linear/xgboost/mlp 特征名 → 位置集合变成 **2..23（缺 1）**；对 **0-based** 的 cnn/transformer 反而正确。
  `_draw_single_heatmap:454-461` 再补 `range(1,24)` → pos1 恒为 0、pos22/23 撞列被 mean 合并。
* 影响范围：`summary/plots/01_position_heatmaps/*_{linear,xgboost,mlp}_heatmap.png`（live step，`pipeline/steps.py:292-297`）；
  `tables/attribution_summary.csv`（分析层用 `_parse_position_channel`，实测 5 个模型 position 均为 1..23）**不受影响**。
* 与文档冲突：`analysis/docs/code_cleanup_report.md:46` 声称两个解析器"已单测对齐"。

### (iv) 数据泄漏全量清单（本轮系统排查）与对数据挖掘的量化影响

**泄漏源清单（按严重度）**

| # | 泄漏源 | 机制 | 实测规模 | 影响范围 |
| ---: | :--- | :--- | :--- | :--- |
| L1 | **mixed 跨细胞系孪生行** | hct116↔hela 有 2 506 行 `(sgRNA,label)` 完全相同（另有 hct116↔hl60 27、hela↔hl60 34）；去重只做逐文件整行，跨文件重复全部保留 | test∩train = **528/2 513 (21.0 %)**（seed 42；43–45 为 20.8–21.5 %），另 ~4–5 % 与 valid 重叠 | mixed 全部结论 |
| L2 | **`all`（LOCO）退化** | 只传 `--cell-line` → 单细胞系 70/15/15；"留出细胞系"= 自己 | ~~448/448 与 single 逐位相同~~ → **2026-09-13 已合并真 LOCO 重跑**（448 run，4 系训练 + 1 系留出；all vs single 逐位相同 **0/448**） | 已修复（产物级）；详见下方"L2 修复后结果" |
| L3 | **同 locus 反向互补孪生（single 内）** | 同一 `(Chromosome,Start,End)` 在 train/test 各出现一次（正/负链，sgRNA 互为 revcomp，标签不同） | HEK293T **21/350 = 6.0 %**；HeLa 7/1 215 = 0.6 %；hct116/hl60 = 0 | single 的位点级近重复 |
| L4 | **候选集与训练池重叠** | ultimate 模型在 mixed 全池（16 749）上重训后给 `data/candidate/todo_data.CSV` 打分 | todo 的 176 432 个唯一 sgRNA 中 **11 027 (6.2 %)** 在训练池内 → 这些候选是**样本内预测** | 候选排序（赛道二_results.csv） |
| L5 | **有符号 ISM 为样本内分析** | position-18 signed ISM 用全部 5 080 条 C@18 guide（模型训练时见过）计算 Δ | 无 hold-out | 位置 18 的方向性结论（属模型行为审计，不是泛化证据） |
| L6 | **测试集兼作模型/配置选择集** | 网格实验只有单次 70/15/15，用同一 test 比较 kernel/模型并报告性能；ultimate 用 CV 选超参后又报告该 CV 值 | 结构性（无嵌套 CV） | "k5/k7>k3""mixed 优于 single"等比较 |
| L7 | 标准化泄漏 | `scaler` 只在 train 上 `fit`（`linear_regression.py:163`、`cnn.py:645`），且 `use_scaler` 默认 False | **无** | — |

**量化影响（mixed seed 42 / environment=sequence；行对齐已用 `y_true` 逐行核验 2 513/2 513 通过）**

| 模型 | 整体 R² | **泄漏子集**（n=528）R² | **干净子集**（n=1 985）R² | single 中位 R²（同环境） |
| :--- | ---: | ---: | ---: | ---: |
| XGBoost | +0.157 | **+0.381** | +0.102 | 0.1155 |
| MLP | +0.132 | **+0.690** | **−0.004** | 0.0851 |
| CNN(k=5) | +0.147 | **+0.560** | +0.045 | 0.0569 |

**结论（本项目层面）**
1. mixed 的"预测性能"主要由**被记忆的重复行**贡献：去掉泄漏行后，MLP 的 R² 降到 ≈0、CNN 降到 0.045、XGBoost 0.102。
2. 因此"**mixed（合并训练）优于 single**"这一比较**很可能是泄漏造成的假象**（XGBoost：clean mixed 0.102 < single 0.116；MLP：−0.004 < 0.085；CNN k5：0.045 < 0.057）。
3. 环境 ΔR² / bootstrap / permutation / FDR / Tier 全部在**同一个被污染的 mixed cohort** 上计算 → 一切基于 mixed 的增量效应估计都带乐观偏置；而 `single` 实测 **0 行泄漏**（每个细胞系 sgRNA 全唯一），故"域内（single）"性能与 `single` 上的结论不受此影响。
4. 泄漏还会改变**模型排序**（越能记忆的模型越占优：MLP 在泄漏子集 +0.69、干净子集 −0.004），进而影响"哪个模型最好"与"哪个模型的环境效应显著"这类判断。
5. 归因/ motif 可能被记忆化影响（模型对训练序列的记忆会推高这些序列的 attribution），HeLa-only 的 GAGG/GGGG 富集是否部分源于此，**尚无证据**，只能作为待查假设。
6. L4/L5/L6 属于"样本内使用/选择偏置"，不是行级泄漏；报告时必须分别声明（L4 影响候选分数、L5 影响方向性结论的效力、L6 影响模型间比较）。

**按影响排序的补救建议**：① L1 全局按 `(sgRNA,label)`（或按 locus）去重后重跑 4 个 seed 的 mixed（28 run/seed → 112 run，不需重训 single）；② L4 在候选打分时剔除与训练池重叠的 guide 或明确标注；③ L6 改为嵌套 CV 或至少把"选择用集"与"报告用集"分离；④ L3 在 QC 中增加 locus/revcomp 近重复检测（目前已完全缺失）。

### (v) L2 修复后结果（2026-09-13 合并 448 个真 LOCO run，未重训 single/mixed）

| 项 | 修复前（退化） | 修复后（真 LOCO） |
| :--- | :--- | :--- |
| `all` vs `single` 指标 | 448/448 逐位相同 | **0/448** |
| LOCO R² 中位（全模型） | （与 single 相同，≈0.08） | **0.0275** |
| 按留出细胞系的中位 R² | — | HCT116 **+0.143**、HeLa **+0.094**、HL60 **−0.082**、HEK293T **−0.512** |
| 按模型的中位 R² | — | k5 **0.064**、XGBoost 0.052、Transformer 0.041、Linear 0.026、k3 0.016、k7 −0.013、MLP −0.045 |
| 环境证据 Tier | 3 Inconclusive + RRBS Tier 2 | **4 个全部 Inconclusive** |

要点：
1. **跨细胞系泛化确实存在但很弱**，且**高度依赖留出细胞系**：HCT116/HeLa 可被其余三系预测，HEK293T/HL60 基本失败（R² 为负）。
2. 环境因子结论进一步收紧：CTCF 在 LOCO 数据上均值 ΔR² 变为 **+0.0136**（effect 门通过、CI [0.0061, 0.0226] 不跨 0、一致率 0.857），但 **cell-line 上下文为 `Context-conflicting` → 一票否决 → Inconclusive**；DNase/H3K4me3/RRBS 的 effect 门与 CI 均不通过。
3. motif 行随归因重算而变化：Tier 3 由 496 → **455**，Inconclusive 由 100 → **160**。
4. 旧的退化 `all` 产物备份在 `_backup_degenerate_all_20260913b/`（143 MB，448×3 目录）。
5. **本轮只修了 L2**：L1（mixed 21 % 泄漏）、L3（locus/revcomp 孪生）、L4（候选集 6.2 % 样本内）、L5（ISM 样本内）、L6（测试集兼选择集）**均未处理**，mixed 相关结论仍带乐观偏置。
6. 新发现（同类问题）：`loco_performance.csv` 未过滤数值发散行 → `linear/hct116` 的 LOCO R² 显示 **−2.85×10¹⁹**（`analysis/prediction.py::loco_performance` 直接 `groupby.mean()`，与 R1 修过的置换路径同源缺陷）。

---

# Part 6 — 最终学习重点（六层）

**第一层：数据如何决定"能做什么分析"**
数据里有什么变量，决定了分析的上限：23 nt × 4 通道 + 4 个二值表观通道 + 细胞系 + 实测标签 →
因此能问"位置/碱基"与"环境通道"两类问题，能按细胞系分层，但**不能**问连续表观强度、脱靶、编辑窗口。
metadata 里的 `sgRNA` 是位置语义的唯一来源（位置 18 就是 sgRNA[17]），schema 是跨分析对齐的唯一契约。

**第二层：Effect 与 Importance 如何互补**
ΔR² 回答"加入因素后**预测性能**是否提高"；signed ISM 回答"把**这条序列**的这个碱基改掉，**模型输出**怎么变"；
SHAP/IG/attention 回答"模型**依赖**什么"。三者单位不同、对象不同，**不可互相替代**：
Importance 高的特征可能对性能零增量；Effect 小的因子可能在具体上下文中有明确方向响应。

**第三层：Statistical Evidence 如何验证 Effect**
bootstrap 给出 uncertainty（注意单位：模型级 vs 样本级）；permutation 给出"增量为 0"的零假设检验；
FDR 处理大量 edge/factor 检验的多重性。关键纪律：`p ≠ effect`、`FDR ≠ effect size`、
`min over many contexts ≠ factor-level FDR`（存在性证据，必须标注 extremum selection）。

**第四层：Robustness 如何挑战前面的结论**
跨模型（是否只是某个架构的偏好）、跨 seed（是否只是划分随机性）、跨 cell line（是否只是某个背景）、
跨 split（是否依赖训练数据范围）、跨 kernel（是否依赖感受野）。
压力测试失败不等于结论为假，而是把结论降级为"context-dependent"或"model-specific"。

**第五层：Evidence Integration 如何形成候选因素**
Tier = 对一个因素已有计算证据的 convergence/coverage/robustness 评级：
覆盖度 ≥2 模型、方向一致率 ≥0.80、稳健性（CI 不跨 0）、以及 **effect 门（模型等权平均 |ΔR²| ≥0.01）**。
统计证据只能支持，不能单独提升（本批 RRBS 因 effect 门未过而停在 Tier 2）。
ANOVA 回答全局因子/交互结构，**不进入** Tier；motif 的 importance 也不进入 Tier。

**第六层：哪些结论仍不能称为因果**
本项目的终点是 **computational evidence → candidate factor → biological hypothesis**：
模型在观测数据上训练，跨模型一致只降低"模型依赖性"，**不是**独立重复，更不能代替实验；
所有 ΔR²/ISM/SHAP 都描述"模型的行为"，只有在独立实验或独立数据上复现后，才能谈机制与因果。

---

# 附录 — 文档与代码不一致清单（以代码/产物为准）

| # | 不一致 | 事实 | 影响 |
| ---: | :--- | :--- | :--- |
| 1 | 论文/文档称 `all` 为"留一细胞系泛化" | ~~本批 `all` 退化为 `single`~~ → 2026-09-13 已合并真 LOCO 重跑（all vs single **0/448** 相同），跨细胞系泛化结论**现已可用**（但绝对性能大幅下降，见"L2 修复后结果"） | 论文 §3.2/§2.4 的 LOCO 表述与 `loco_performance.csv` 需按新数据更新 |
| 2 | 论文 Table 2 声称"对实验取中位数" | `make_assets.py:487-508` 实际取的是 `prediction_summary.csv` 单行的均值（median≡mean），且 linear 发散行未剔除（single 显示 −1.87×10¹⁶） | Table 2 的 linear 行与"median"标签不可用 |
| 3 | 方法文写 `partial η²` | 代码计算 `η² = SS_term/SS_total`（经典 η²），两者差 4–5 倍 | 论文数值需改名或改算 |
| 4 | `results/tables/paper/` 的 12 张中间表现已由 `analysis/reporting/paper_analysis/build_paper_tables.py` 统一生成（审计 G1 已闭合）；此前 | 实际只有 `bootstrap_edge_by_factor.csv`、`factor_level_ci.csv` 由该脚本写；其余 11 个无仓库内生成脚本 | 这些表的超参不可复现，只能引用现有文件 |
| 5 | `conv_channels1/2` 被写入 config | `core/models/cnn/cnn.py::train()` 形参为 `sequence_filters/...`，参数被 `workflows/training/train.py` 按签名过滤 → 实际用默认 64/64/128 | config 中的 32/64 不代表实际架构 |
| 6 | 早期文档称 `evidence/rules.py` 被生产使用 | 仅被单测引用，已删除；权威规则 = `integration.py::classify_evidence_tier` | — |
| 7 | 本批环境 Tier 的旧值（RRBS Tier 1 / DNase Tier 2） | R1–R6 后：环境因子 0 个 Tier 1，RRBS = Tier 2，其余 Inconclusive | 论文 §3.8 已同步改写 |
| 8 | `summary/feature_importance` 与 `analysis/importance_metrics` 对 CNN 用不同归因列 | 前者用 `CNN_ISM`+`ISM_SNR`；后者用 `CNN_IG` 且显式排除 ISM | 引用"CNN 重要性"时必须说明用哪一套 |

| 9 | 列名 `min_edge_fdr` 与文档/论文措辞 "Minimal **Edge**-level FDR across Tested Contexts" | 代码实际只取 `test_type == "environment_main_effect"` 的最小 FDR（`integration.py`：edge 行的 `factor` 列为 NaN，因此 `factor == f` 过滤天然排除了 2 688 行 edge 检验）；真实 edge 级最小 FDR 为 CTCF 0.0639 / DNase 0.0160 / H3K4me3 0.0320 / **RRBS 0.0746**（全部 > 0.05） | 命名高估了统计证据的强度；若按真 edge 口径，任何因子都无法通过统计门（Tier 结论不变，因为 effect 门已全部 fail） |
| 10 | 因子级 CI 有两套实现且数值不同 | `analysis/stats/tasks.py::bootstrap_main_effects`（DNase [−0.005229, +0.000402]）vs `paper/make_assets.py::factor_ci`（[−0.004515, +0.000302]）；CTCF 两者相同，H3K4me3/RRBS 亦差在第 3 位小数。论文 `03_results.tex:49` 与 `:147` 同篇引用不同版本 | 两套口径的"是否跨 0"结论一致（CTCF/DNase 跨 0），Tier 不受影响；但论文内部数值不自洽，应统一到 `bootstrap_main_effects` |
| 11 | `environment_edges.csv` 存在重复行 | 2 651 行 vs 唯一键 2 016；重复全部在 `mixed`（859 行 vs 224 唯一，635 条重复），源于 CI merge；`all/single` 无重复 | 论文中"2 541 条边有 CI / 166 条不跨 0"等分母被放大，应改为唯一键口径（2 016） |
| 12 | `FdrFamilyConfig.enabled_families` 列了 `environment_anova` | ANOVA 结果表有 `family_key` 但**从不做 BH-FDR**（`apply_fdr` 只作用于 permutation 与 motif 富集） | 属"配置存在但流水线不用"的死配置，应在配置中移除或在文档中声明 ANOVA 不做校正 |
| 13 | motif 的 `model_consistency` 取值 2–24 | 实际 kernel 变体只有 3 个（k3/k5/k7），该列被用于"≥2 变体"的证据门槛 → 340 个 motif 被判为 Moderate | motif 的稳定性口径被放大，需在方法中说明该列的真实构造（或改为 ≤3 的口径） |

| 14 | 跨细胞系孪生行导致 mixed test 与 train 重叠约 21 % | hct116∩hela 在 `(sgRNA,label)` 上完全相同 **2 506 行**；逐文件整行去重不去跨文件重复；复现 `divide_data(mixed)`：test∩train = 541/531/532/522（seed 42–45），另 ~4.8 % 与 valid 重叠；single 实测 0 泄漏 | mixed 的绝对性能与一切基于 mixed 的增量效应（ΔR²→bootstrap→permutation→FDR→Tier）均被乐观偏置；**本文档 Part 4 Q1 的环境结论需加此限定** |
| 15 | 表观通道零方差/近零方差未被 QC 捕获 | HEK293T、HeLa 的 **Dnase 通道恒为 1（var=0）**；HeLa 的 CTCF frac₁=0.990；RRBS 第 23 位在 4 个细胞系恒为 0；`data_QC.py` 只查 sgRNA 单态位点 | 这两系的"DNase 无增益"是常数特征假象；线性秩亏与部分近零增益属设计缺陷，不能作为生物学证据 |
| 16 | 位置热图解析器错位（1-based 源被再 +1） | `analysis/visualization.py:177-180` 对 ≤22 一律 +1 → linear/xgboost/mlp 的图位置变为 2..23（无 1）；分析层 `_parse_position_channel` 正确（实测 1..23）；`code_cleanup_report.md:46` 称两者"已对齐" | 只影响 `summary/plots/01_position_heatmaps/*_{linear,xgboost,mlp}*.png`；attribution 表与所有下游统计不受影响 |
| 17 | `analysis/data/loaders.py:38-87` 只保留 16 列 | 丢掉 `cell_lines / input_shape_* / sequence_kernel` 等 split 元数据 | 分析链失去"LOCO 退化检测"与"样本量分层"能力（这也是 LOCO 退化长期未被自动发现的原因之一） |

> 说明：本任务**未修改任何代码**；上述第 1–6 条为既有事实，第 7 条为上一轮 R1–R6 重构后的结果，第 8 条需在论文口径上二选一。
