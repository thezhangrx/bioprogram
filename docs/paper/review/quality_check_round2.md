# 论文 v2 质量检查（paper_quality_check_v2）

对象：`paper/sections/*`（v2）→ `paper/compiled/main_v2.pdf`（XeLaTeX，23 页）
检查时间：第二轮重构后；所有数值由脚本从 `results/` 重新计算。

---

## 1. 编译与 LaTeX 工程

| 检查项 | 结果 | 证据 |
| :--- | :--- | :--- |
| 是否真实编译 | ✅ | XeLaTeX ×2 → `Output written on main.pdf (23 pages)` |
| LaTeX 错误 | ✅ 0 | `grep -c '^!' main.log` = 0 |
| 未定义引用 / 引用文献 | ✅ 0 / 0 | `Warning.*undefined` 计数 = 0 |
| 标签闭合 | ✅ | 新增 `fig:importance`（补充图 S1）、`tab:candidates`（正文 Table 6）均已定义并被引用 |
| 表格就位 | ✅ | Table 1–6 分别置于 §3.1/§3.2/§3.3/§3.5/§3.6/§3.8，S1–S2 在附录 |
| 图件 | ✅ | 正文 7 图（PDF 矢量）+ 补充 1 图；Importance–ΔR² 已移出正文 |
| Overfull hbox | ⚠ 少量 | 宽表已用 `\resizebox` 缩放；如需完全消除可在目标模板调整列宽 |
| 产物归档 | ✅ | `compiled/main.pdf`（v1，22 页）与 `compiled/main_v2.pdf`（v2，23 页）并存，各带 `main*.log` |

---

## 2. Claim Audit（结论强度）

指令要求全文搜索并逐句审查：`prove / demonstrate / significant / key determinant / critical / mechanism / regulates / causal / universal / important`（含中文对应夸大词）。

| 关键词 | 出现次数 | 说明 |
| :--- | ---: | :--- |
| prove | 0（1 处为文件名 `provenance`） | 无"证明"式表述 |
| demonstrate | 0 | 统一改为 `showed / was observed / was identified by` |
| significant | 0 | 显著性只用 $p$/FDR 数值表述，不使用定性"显著" |
| causal / causality | 0 | 全文明确 attribution ≠ causality |
| mechanism | 0 | 统一改为 "candidate factor / testable hypothesis" |
| universal | 0 | 第 18 位结论限定为 context-dependent |
| key determinant / critical / 首创 / 全球领先 / 革命性 | 0 | — |

措辞分层（v2 实际使用）：
- 观察 → `showed / was observed`
- 模型证据 → `was identified by model attribution / was supported by`
- 多源证据 → `was supported by convergent evidence`（例：PAM 邻近区域、核消融）
- 假设 → `suggests / is consistent with / provides a testable hypothesis`（例：C1/C2/C3）

**结论：未发现从"模型归因或统计相关"直接跳到因果的句子。**

---

## 3. Numerical Audit（数值一致性）

脚本逐项重算（`results/batches/batch_20260909_full/summary/` 与 `docs/paper_analysis/`）：

| 项目 | 论文值 | 重算值 | 判定 |
| :--- | :--- | :--- | :--- |
| 合法 23 nt 序列 | 16 749 | 16 749（4 239/2 333/8 101/2 076） | ✅ |
| 受控运行数 / 配置 / 环境 | 1 344 / 7 / 16 | 1 344 / 7 / 16（6 个划分×种子设定） | ✅ |
| single 中位 $R^2$ | 0.115 / 0.085 / 0.080 / 0.069 / 0.057 / 0.035 | 同（XGBoost/MLP/CNN7/Transformer/CNN5/CNN3） | ✅ |
| Linear single 中位（+发散数） | 0.087 + 21/64 | 0.087 + 21/64 | ✅ |
| Linear 发散总数 | 56/192 | 56/192 | ✅ |
| XGBoost mixed 中位 | **0.161**（v1 为 0.164） | 0.161 | ✅ 已修正 |
| 核配对差 | +0.0423 / +0.0557 / +0.0134 | +0.04234 / +0.05565 / +0.01338（CI 同论文） | ✅ |
| 配对为正比例 | 88.5% / 95.8% / 77.1% | 88.54% / 95.83% / 77.08% | ✅ |
| 边级 CI 不跨 0 | 166/1 906 | 30+48+38+50 = 166 / 474+470+480+482 = 1 906 | ✅ |
| 边×种子 CI 不跨 0 | 257/2 541 | 257/2 541 | ✅ |
| 置换 FDR<0.05 | 6/2 688、35/252、9/504 | 逐族累加 = 6 / 35 / 9 | ✅ |
| 区组 ANOVA | $F$=0.60/2.31/1.95/2.18；$p$=0.663/0.056/0.100/0.069 | 同；交互 min $p$=0.265；$\max$ partial $\eta^2$=0.0018 | ✅ |
| 方向一致率 | 0.86（RRBS）/0.71（DNase） | 0.857 / 0.714 | ✅ |
| 候选模式 | 596 个 / 64 个 FDR<0.05 | 596 / 64 | ✅ |
| 模式长度 / 支持度中位 / 起始位 20 | 532 个 4 nt / 194 / 382 | 532 / 194 / 382 | ✅ |
| seqlet 实例 / 上下文 | **172 098 / 24**（v1 为 545 060 / 80） | 172 098 / 24 | ✅ 已修正 |
| GAGG | 899、+0.012、OR 1.11、FDR 0.030、1 细胞系 | 同 | ✅ |
| GGGG | 435、**+0.060**、OR 1.38、FDR 7×10⁻⁶、1 细胞系 | 同（v1 文本为 +0.047） | ✅ 已修正 |
| CTGG | 1 273、−0.046、FDR 1.0 | 同 | ✅ |
| 第 18 位 C−A | +0.090/+0.092/+0.028/−0.016 | +0.0904/+0.0924/+0.0273/−0.0155 | ✅ |
| 位置 18 模型支持 | 3/5 模型 top-3 | 3/5（CNN、MLP、XGBoost） | ✅ |
| 环境最高归因区域 | 4/5 模型类 = PAM 邻近种子区 | 4/5（线性为 PAM 21–23） | ✅ |

**修正原则**：以 artifact 为准；三处不一致已在 v2 文本修正，并记录于 `docs/paper_revision_v2.md` §6。

---

## 4. 降级与边界检查（v2 专项）

| 检查项 | 结果 | 说明 |
| :--- | :--- | :--- |
| Evidence tier ≠ effect size | ✅ | Methods §2.9 定义 + Results §3.8 + Table 3 caption + Figure 7 caption 四处声明 |
| Importance–ΔR² 定位 | ✅ | 移至 Supplementary Figure S1；正文 Figure 7 仅保留环境 CI + 等级 |
| Importance 归一化声明 | ✅ | Methods §2.10 与 Figure 4 caption：importance 仅在模型内归一化，不可跨模型类比较 |
| kernel size ≠ motif length | ✅ | §3.5 观察 3、§3.5 解释、Discussion §4.5、Figure 5 caption 四处强调 |
| LOCO 降级 | ✅ | Methods §2.4、Results §3.1、Limitations、Future §7 四处声明退化且不作泛化证据 |
| 环境弱结果保留 | ✅ | §3.3 完整保留（小效应、方向不一致、ANOVA 不显著、方法间不一致） |
| 未伪造湿实验 | ✅ | 全文无实验数值；§7 仅给设计、读出与判定标准 |
| "智能设计"表述 | ✅ | 明确为 candidate prioritization / ranking；未使用 de novo generation |
| 与训练系统解耦 | ✅ | 本轮未修改任何训练/分析代码与 `results/`（仅只读 + 生成论文/文档） |

---

## 5. 图表检查

| 检查项 | 结果 | 说明 |
| :--- | :--- | :--- |
| 正文图数量 | ✅ 7（Figure 1–7） | 与赛道建议一致 |
| 每图被正文引用 | ✅ | Methods §2.1 与 Results §3.1–3.8 全部引用 |
| 每表被正文引用 | ✅ | Table 1–6、S1–S2 均有引用 |
| Caption 自洽 | ✅ | 均含分组、坐标含义、统计标注与解释边界（含"非显著性图"等声明） |
| 图与正文数值一致 | ✅ | 图表与正文同源（`paper/make_assets.py` 生成的 CSV） |
| 新增 Table 6 内容 | ✅ | 4 行候选，含最小扰动方案与优先级；caption 明确"无湿实验验证、非因果估计" |

---

## 6. 参考文献检查

| 检查项 | 结果 |
| :--- | :--- |
| 文献数量 | 12（未新增、未删除） |
| 真实可核验 | ✅ PubMed / Crossref / OpenAlex / arXiv 已核验（DOI/PMID 记录见 v1 provenance §8） |
| 引用与 bib 一一对应 | ✅ `bibtex` 0 error，编译 0 undefined citation |
| 关键外部事实均有引用 | ✅ Cas9 基础（Jinek/Cong）、规则方法（Doench 2014/2016、Moreno-Mateos）、深度模型（Alipanahi/Kelley/Chuai）、方法（Chen/Lundberg/Sundararajan/Vaswani） |

---

## 7. 与赛道评分逻辑的对齐（论文内自然覆盖，不写评分表）

| 评分项 | v2 覆盖位置 |
| :--- | :--- |
| 选题价值与工具理解 | §1.1、§2.2（PAM 由数据核对）、§5（工具范围） |
| AI 设计与模型方法 | §2.3–§2.11（受控实验、归因语义、统计、motif、证据整合）、§3.2–§3.8 |
| 候选工具与设计创新 | §2.10（候选优先级六标准）、§3.8 + Table 6、§4.8–4.9 |
| 实验验证与性能证据 | §3.2（计算验证与性能边界）、§5（已完成/未完成）、§7（未来实验设计） |
| 提交材料与展示 | §2.11（可复现性与 artifact）、附录 provenance 映射；仓库 `docs/` + Notebook + README |

---

## 8. 遗留事项（需用户决定）

1. `models/`、`logs/` 仍为空；如需评审复现训练，需要重新运行并保存权重与日志。
2. 候选清单 `results/赛道二_results.csv` 仍未生成（可用 `workflows/prediction/predict.py --generate-candidates` 生成）。
3. 展示 PPT（带录音）尚未在仓库中。
4. 真正的 LOCO 重训、C1/C2/C3 的湿实验验证属于后续工作，v2 已在 §5 与 §7 明确。
