# 论文质量检查清单（Paper Quality Check）

检查对象：`paper/`（LaTeX 正式稿）与 `docs/paper_claim_provenance.md`（事实来源表）。
检查时间：由本轮分析生成；所有数值可经 `python paper/make_assets.py` 复现。

---

## 1. 科学正确性（Scientific correctness）

| 检查项 | 结果 | 说明 |
| :--- | :--- | :--- |
| 无因果过度声明 | ✅ | 全文搜索 `causes / proves / determines / 因果 / 机制证明`：仅在"不构成因果结论""机制验证需独立实验"等否定语境中出现（Limitations §5、Discussion §4.5）。 |
| 未将归因当作显著性 | ✅ | Methods §2.7 与 Results §3.4 明确 attribution magnitude ≠ significance；显著性仅出现在 bootstrap CI、置换检验、ANOVA 与 Fisher 富集语境。 |
| 未将 ΔR² 当作因果效应 | ✅ | ΔR² 一律表述为 incremental predictive value / 增量预测贡献。 |
| 未将 kernel size 当作 motif length | ✅ | Methods §2.9 与 Results §3.5 明确二者不同；Fig. 5D 直接用数据说明三配置模式长度中位数均为 4 nt。 |
| 未将 attention 当作显著性 | ✅ | 注意力仅作支持性信息；Results §3.4/§3.7 报告其峰值位置与梯度/树归因不一致。 |
| 未将 cell-line 差异直接解释为机制 | ✅ | 一律使用 context-dependent association；Limitations §7 说明样本量/标签分布等替代解释。 |
| 未把单模型结果写成 consensus | ✅ | 跨模型结论均给出覆盖度（如 CTGG 的 "跨 4 个细胞系"，环境因子的 "6/7 模型"）。 |
| 所有定量结论可追溯 | ✅ | 每条定量 claim 在 `docs/paper_claim_provenance.md` 中对应到具体结果文件与字段。 |
| 所有统计结论有计算支持 | ✅ | CI：`bootstrap_results.csv`；p/FDR：`permutation_results.csv`；ANOVA：`anova_results.csv`；富集：`motif_enrichment.csv`。报告中出现的每个统计量均有对应文件。 |
| 缺失/不可用如实标注 | ✅ | Transformer IG 缺失（跨模型 motif 比较标 unavailable）、seed 级 motif 支持缺失（`motif_consistency.csv` 中标注原因）、`all` 划分退化（Limitations §1）均显式说明。 |
| 未修改实验结果 | ✅ | 本轮仅新增 `paper/`、`docs/paper_analysis/`、`docs/paper_*.md`；`results/` 未改动（仅为只读输入）。 |

## 2. 参考文献（References）

| 检查项 | 结果 | 说明 |
| :--- | :--- | :--- |
| 每篇文献真实可核验 | ✅ | 12 篇全部经 PubMed esummary / Crossref / OpenAlex / arXiv 页面核验（记录见 provenance §8）。 |
| BibTeX 字段完整 | ✅ | 全部含 author/title/journal 或 booktitle/year/volume 或 pages/doi 或 eprint。 |
| DOI/PMID 已核验 | ✅ | 期刊论文含 DOI 与 PMID；会议论文含 DOI（XGBoost）或 arXiv ID（SHAP/IG/Transformer）。 |
| 无重复文献 | ✅ | 12 个 key 互不重复，正文引用与 .bib 一一对应。 |
| 引用位置恰当 | ✅ | CRISPR 基础 → Jinek/Cong；规则模型 → Doench2014/2016、MorenoMateos2015；深度序列模型 → Alipanahi2015、Kelley2016、Chuai2018；方法 → Chen2016、Lundberg2017、Sundararajan2017、Vaswani2017。 |
| 未用文献支撑本文实验结果 | ✅ | 本文定量结论全部引用 `results/` 产物；文献仅用于背景与方法出处。 |

## 3. 语言与术语（Language）

| 检查项 | 结果 | 说明 |
| :--- | :--- | :--- |
| 术语一致 | ✅ | 模型统一为 Linear Regression / XGBoost / MLP / Dual-Branch CNN / Transformer；环境因子统一为 CTCF、DNase、H3K4me3、RRBS；细胞系统一为 HCT116、HEK293T、HeLa、HL60。 |
| 缩写首次出现给全称 | ✅ | MLP、CNN、IG、ISM、SHAP、PAM、FDR、LOCO、BH-FDR、IUPAC 均在首次出现处给出中英文全称。 |
| 时态一致 | ✅ | 方法学与结果均用现在时/过去时规范表述（"we computed"，"the model showed"）。 |
| 无宣传性措辞 | ✅ | 全文搜索 `obviously / clearly / remarkably / dramatically / revolutionary / novel / powerful`：0 处。 |
| 证据等级措辞一致 | ✅ | 观察用 "was observed/showed"；模型支持用 "was consistently identified by the models"；多源用 "was supported by convergent evidence"；假设用 "suggests/provides a testable hypothesis"。 |
| 数字格式统一 | ✅ | R²/RMSE/MAE/ΔR² 三位小数；p 值三位小数或科学计数法；CI 统一 `[low, high]`；n 用千分位空格。 |

## 4. 图表（Figures & Tables）

| 检查项 | 结果 | 说明 |
| :--- | :--- | :--- |
| 正文每个图都被引用 | ✅ | Fig. 1–7 分别在 Methods §2.1 与 Results §3.1–3.7 引用。 |
| 正文每个表都被引用 | ✅ | Table 1–5 在 §3.1–3.6 引用；Table S1/S2 在附录引用。 |
| Caption 自洽 | ✅ | 每个 caption 包含数据来源、分组、坐标轴含义、颜色/形状含义、统计指标与解释限制。 |
| 坐标轴与单位完整 | ✅ | 所有图含轴标签；归因图明确标注 "normalized"；ΔR² 图标注 paired baseline。 |
| 统计标注有定义 | ✅ | CI 在 caption 中说明为 bootstrap 百分位区间；误差线含义逐图说明。 |
| 图与正文数值一致 | ✅ | 图表均由 `paper/make_assets.py` 与正文同源生成（同一 CSV）。 |
| 图件格式 | ✅ | PDF（矢量）+ PNG（预览）双份，位于 `docs/paper/figures/`。 |

## 5. LaTeX 工程（LaTeX）

| 检查项 | 结果 | 说明 |
| :--- | :--- | :--- |
| 结构与文件齐全 | ✅ | `main.tex`、`references.bib`、`sections/`（8 个）、`tables/`（7 个）、`figures/`（7×2）、`supplementary/`、`compiled/`。 |
| 标签与引用闭合 | ✅ | 所有 `\ref`/`\label` 对（fig:workflow, fig:prediction, fig:environment, fig:sequence, fig:kernel, fig:cellline, fig:evidence；tab:dataset…tab:methods, tab:sequence, tab:claimmap）均在文中定义；`\cite` 的 12 个 key 均在 `references.bib` 中。 |
| 无未定义引用 | ✅ **已编译验证** | XeLaTeX 编译 3 遍：**0 errors / 0 undefined references / 0 undefined citations**（日志 `paper/compiled/main.log`）。 |
| 编译命令 | ✅ | `xelatex main.tex → bibtex main → xelatex main.tex ×2`（TeX Live 2023 + ctex/xecjk/fandol；`latexmk -xelatex -bibtex main.tex` 等效）。 |
| 编译产物 | ✅ | `paper/compiled/main.pdf`：**22 页**，7 幅矢量图 + 7 个表格 + 参考文献全部嵌入；`main.log` 一并保留。 |
| 版式细节 | ⚠ | 9 处 Overfull hbox（宽表已用 `\resizebox` 处理）；如需完全消除，可在目标模板中调整列宽或改为横向表。 |

## 6. 与框架文档（docs/论文.md）的一致性

| 检查项 | 结果 | 说明 |
| :--- | :--- | :--- |
| 章节结构 | ✅ | 采用 3.1–3.7 的 Results 组织（数据与设计 / 预测与泛化 / 环境增量 / PAM 邻近模式 / 多尺度 CNN / 细胞系异质性 / 跨模型证据整合），并将原 §15–§20 的占位内容替换为真实结果。 |
| 平台定位 | ✅ | 强调 "prediction → interpretation → evidence → hypothesis"，未退化为 model benchmark。 |
| 案例定位 | ✅ | 明确 DeepCRISPR 为案例验证而非平台适用性唯一证明。 |
| 标题与术语 | ✅ | 使用"基因编辑系统/CRISPR-Cas9 基因编辑系统"，未使用"多类基因编辑系统"或"机制挖掘"。 |
| 未编造内容 | ✅ | 框架中"这里放你的 Figure"等占位均替换为真实图件；未虚构实验、统计或文献。 |

## 7. 待办与风险提示

1. **TeX 编译**：已在沙箱内用用户模式 TeX Live 实际编译通过（22 页/0 错误，见 `paper/compiled/main.log`）。若目标期刊有指定模板，请替换 `\documentclass`/`\bibliographystyle` 后重编译；`ctex` 字体与 `natbib` 样式可按期刊要求调整。
2. **作者信息**：`main.tex` 中作者、单位与基金信息待补。
3. **遗留分析项**：Transformer IG 产物缺失（跨模型 motif 收敛判定受限）；`all`（留一细胞系）划分在本批次退化，独立的跨细胞系泛化验证需在训练侧重新执行配置后补充。
4. **统计口径提示**：环境因子的置换检验与区组 ANOVA 结论不一致已如实报告（§3.3 稳健性），如目标期刊要求单一主分析，建议以区组 ANOVA 为主要推断、置换检验为敏感性分析。
