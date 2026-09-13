# 论文 v2 事实来源与审计表（paper_claim_provenance_v2）

对象：`paper/sections/*`（v2）+ `paper/compiled/main_v2.pdf`（23 页）
生成方式：全部数值由脚本从 `results/batch_20260909_full/analyse_out/` 与 `docs/paper_analysis/` 重算，未手工填写。
解释级别：**L1 观察**（数据统计）｜**L2 模型支持**（归因/预测）｜**L3 多源证据**（多模型 × 统计 × 独立信息源）｜**L4 假设**（可检验命题）

---

## 表 1 论文结论表（Claim → 章节 → 结果文件 → 证据 → 强度 → 措辞检查）

| # | Claim（v2 表述） | 章节 | Source result file | 统计/归因证据 | 强度 | 措辞是否过强 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 4 个细胞系共 16 749 条合法 23 nt 序列 | §3.1 | `data/proceeded_data/*_metadata.csv` | 计数 | L1 | 否 |
| 2 | 设计空间 = 7 配置 × 16 环境 × 12 设定 = 1 344 次运行 | §3.1 | `tables/experiment_table.csv` | 计数 | L1 | 否 |
| 3 | PAM 位于 21–23 位（末两位 100% 为 G） | §3.1/§2.2 | 同上（`sgRNA` 字段） | 频率 | L1 | 否（仅描述数据编号） |
| 4 | Linear Regression 56/192 次数值发散 | §3.1/§5 | `tables/experiment_table.csv`（$\|R^2\|>10$） | 计数 | L1 | 否（称 "technical limitation"） |
| 5 | 各模型中位 $R^2$ 0.035–0.115（single） | §3.2 | 同上 | 中位数/IQR | L1 | 否（明确"弱信号"） |
| 6 | XGBoost mixed 中位 $R^2$ = 0.161 | §3.2 | 同上 | 中位数 | L1 | 否 |
| 7 | 四类模型最高归因区域为 PAM 邻近种子区（17–20） | §3.4 | `tables/attribution_summary.csv` → `docs/paper_analysis/region_attribution.csv` | 模型内归一化归因均值 | L2 | 否（"identified by model attribution"） |
| 8 | 位置 18 进入 3/5 模型 top-3，跨模型平均谱第 1 | §3.4 | `docs/paper_analysis/position_profile_by_model.csv` | argmax / top-k | L2 | 否 |
| 9 | 第 18 位 C−A 效率差：+0.090/+0.092/+0.028/−0.016 | §3.4/§3.7 | `docs/paper_analysis/position18_efficacy_by_base.csv` | 分组均值（n=472–1 652/组） | L1→L3（与 7、10 合流） | 否（"candidate sequence-associated pattern"） |
| 10 | CNN ISM 在第 18 位呈细胞系差异 | §3.4 | `tables/attribution_summary.csv`（`cnn_ism`） | 替换效应均值 | L2 | 否（"mutation effect"） |
| 11 | 核 5/7 优于核 3：+0.0423 / +0.0557（192 配对） | §3.5 | `docs/paper_analysis/cnn_kernel_paired.csv` | 配对差 + bootstrap CI | L3 | 否（"in the tested settings"） |
| 12 | 核间归因谱相关 0.82（k3–k5）与 0.21–0.23（k7） | §3.5 | `docs/paper_analysis/kernel_position_profile.csv` | Spearman | L2 | 否（用于说明敏感性） |
| 13 | 归因随核增大向 PAM 邻近集中 | §3.5 | 同上（区域均值） | 归一化归因均值 | L2 | 否 |
| 14 | 三配置候选模式长度中位数均为 4 nt | §3.5/§3.6 | `tables/motif_candidates.csv` | 中位数 | L1 | 否（明确"核大小 ≠ 模式长度"） |
| 15 | 596 个候选模式；64 个 FDR<0.05 | §3.6 | `tables/motif_candidates.csv` + `motif_enrichment.csv` | Fisher + BH-FDR | L3 | 否（统一用 candidate pattern） |
| 16 | GAGG：899 seqlet、+0.012、OR 1.11、FDR 0.030（仅 HeLa） | §3.6 | 同上 | 富集 + 实测效率对比 | L3 + context-dependent | 否（标注单细胞系） |
| 17 | GGGG：435 seqlet、+0.060、OR 1.38、FDR 7×10⁻⁶（仅 HeLa） | §3.6 | 同上 | 同上 | L3 + context-dependent | 否 |
| 18 | CTGG：支持度最高（1 273）但 FDR = 1.0 | §3.6 | 同上 | 未通过富集 | L1（仅支持度） | 否（列为低优先级参考） |
| 19 | 环境主效应 $\|\Delta R^2\|<0.01$，方向不一致 | §3.3 | `tables/environment_main_effects.csv` | 跨模型均值 + CI | L3 | 否 |
| 20 | 边级 CI：166/1 906（边）与 257/2 541（边×种子）不跨 0 | §3.3 | `tables/bootstrap_results.csv`、`docs/paper_analysis/bootstrap_edge_by_factor.csv` | 逐样本配对 bootstrap | L3 | 否 |
| 21 | 置换 FDR<0.05：边 6/2 688、主效应 35/252、交互 9/504 | §3.3 | `tables/permutation_results.csv` | sign-flip + BH-FDR（族内） | L3 | 否（同时给出 ANOVA 反例） |
| 22 | 区组 ANOVA：$p$ = 0.663/0.056/0.100/0.069，交互 $p\ge0.26$ | §3.3 | `tables/anova_results.csv` | Type-II $F$ 检验（$n$=1 288） | L3 | 否 |
| 23 | 环境效应具细胞系依赖（CTCF 在 HL60 反向等） | §3.7 | `docs/paper_analysis/environment_by_cellline.csv`、`tables/cellline_effects.csv` | 分组均值 + context 标签 | L2/L3 | 否（"context-dependent association"） |
| 24 | 证据分级：RRBS Tier 1、DNase Tier 2、CTCF/H3K4me3 Inconclusive | §3.8 | `tables/evidence_matrix.csv` | 覆盖度+一致率+CI 规则 | L3 | 否（附 Tier 语义声明） |
| 25 | 候选 C1/C2/C3（Table 6） | §3.8/§7 | `tables/tab6_candidates.tex`（由 artifact 生成） | 多源汇总 + 预先标准 | L4 假设 | 否（"candidate / testable hypothesis"） |

> 未出现任何 L4→因果的跨越：全文 0 处 significant / causal / mechanism / universal / prove（"prove" 仅出现在文件名 `provenance` 中）。

---

## 表 2 论文结果表（已真实存在的结果清单）

| 结果类别 | 是否存在 | 位置 | v2 处理 |
| :--- | :--- | :--- | :--- |
| dataset / QC | ✅ | `01_data_quality.md`、`*_metadata.csv` | 正文 §3.1 + Table 1 |
| model performance（single/mixed/all） | ✅ | `experiment_table.csv`、`prediction_summary.csv` | 正文 §3.2 + Table 2 + Figure 2 |
| LOCO（all） | ✅（但退化） | `loco_performance.csv` | §3.2 面板 C + §2.4/§5 声明退化 |
| environment ΔR² | ✅ | `environment_main_effects.csv`、`environment_conditional_delta_r2.csv` | §3.3 + Table 3 + Figure 3 |
| bootstrap | ✅ | `bootstrap_results.csv`（7 770 行） | §3.3（边级与边×种子两个口径） |
| permutation | ✅ | `permutation_results.csv`（3 444 行） | §3.3 |
| FDR | ✅ | 同表 `FDR` 列（按族） | §3.3 |
| factorial ANOVA | ✅ | `anova_results.csv`（94 项） | §3.3 + Figure 3D |
| sequence attribution | ✅ | `attribution_summary.csv`（331 200 行） | §3.4 + Figure 4A/B |
| position 18 | ✅ | `position18_*.csv` | §3.4 + Figure 4C/D |
| nucleotide-specific efficacy | ✅ | `position18_efficacy_by_base.csv` | §3.4/§3.7 |
| CNN kernel ablation | ✅ | `docs/paper_analysis/cnn_kernel_paired.csv` | §3.5 + Table 4 + Figure 5 |
| CNN IG / ISM | ✅ | `attribution_summary.csv`（`cnn_ig`/`cnn_ism`） | §3.4/§3.5 |
| motif candidates | ✅ | `motif_candidates.csv`（596 行） | §3.6 + Table 5 |
| motif enrichment | ✅ | `motif_enrichment.csv`（596 检验） | §3.6 |
| motif instances | ✅ | `motif_instances.csv`（**172 098** 行、24 上下文） | §3.6（v2 修正数字） |
| cell-line heterogeneity | ✅ | `cellline_effects.csv`、`environment_by_cellline.csv` | §3.7 + Figure 6 |
| evidence integration | ✅ | `evidence_matrix.csv`（600 行） | §3.8 + Figure 7 + Table 3 |
| Importance–ΔR² | ✅ | `importance_vs_delta_r2.csv` | **Supplementary Figure S1** |
| provenance | ✅ | `analysis_status.json`、`execution_log.json`、`docs/paper_claim_provenance_v2.md` | §2.11 + 附录 |

---

## 表 3 比赛评分覆盖表

| 评分项 | 分值 | 论文已有证据 | 强度 | 当前缺口 | v2 是否体现 | 还需要什么 |
| :--- | ---: | :--- | :--- | :--- | :--- | :--- |
| 选题价值与工具理解 | 15 | §1 明确 SpCas9 + NGG PAM、编辑效率瓶颈、序列/环境/背景三重依赖；§2.2 由数据核对 PAM 编号 | 强 | 仅 Cas9，未覆盖 HYER 等系统；无结构/脱靶/编辑窗口/递送维度 | ✅ §1、§2.2、§5 | 后续可增加系统与 PAM 变体分支 |
| AI 设计与模型方法 | 25 | 5 类模型 ×7 配置 ×16 环境 ×12 设定的受控实验；XAI 全覆盖；统计体系（bootstrap/置换/BH-FDR/ANOVA）；motif 发现；证据整合 | 强 | 无生成式设计；无结构输入；无脱靶建模 | ✅ §2.3–§2.11、§3.2–§3.8 | 结构/脱靶/编辑窗口模块可作为下一版扩展 |
| 候选工具与设计创新 | 20 | Table 6 给出 4 个候选（C1 第 18 位、C2 GAGG、C3 GGGG、CTGG 参考），含多模型支持、效应、稳健性、最小扰动、优先级；`predict.py --generate-candidates` 提供候选排序 | 中 | 候选为"已有序列排序 + 假设"，非 de novo 生成；尚无实验闭环 | ✅ §2.10/§3.8/§7 | 湿实验或独立数据集验证；GenAI 序列生成模块 |
| 实验验证与性能证据 | 25 | 计算验证完整（1 344 次运行、统计推断、跨细胞系比较）；性能区间如实报告（中位 $R^2$ 0.035–0.115）；§7 给出最小扰动实验设计 | 中（计算侧强、湿实验缺失） | 无编辑效率湿实验、无切割活性、无脱靶检测、无编辑窗口验证 | ✅ §3.2、§5、§7 | 实际实验数据（C1/C2 最小扰动） |
| 提交材料与展示 | 15 | 论文 v1/v2 PDF、图表脚本、`docs/` 溯源与质量检查、Notebook 演示、README 产出核对表、requirements、HPC 协议 | 中强 | `models/`、`logs/` 为空；PPT（带录音）未在仓库内 | ✅ 仓库层面；论文内以 §2.11 与附录映射体现 | 补模型权重/训练日志、PPT 与录音 |

---

## 表 4 科学证据等级表

| 结论 | 等级 | 判定依据 | 备注 |
| :--- | :--- | :--- | :--- |
| PAM 邻近区域（17–20）为多模型最高归因区域 | **Strong evidence（模型层面）** | 4/5 模型类独立一致 + 区域均值排序 + 与 PAM 定义一致 | 属 model-derived evidence，非生物学因果 |
| 更宽 CNN 感受野改善预测（k5/k7 > k3） | **Strong evidence（模型层面）** | 192 组配对、均值 +0.042/+0.056、CI 不跨 0、88.5%/95.8% 为正、分层一致 | 受限"tested settings" |
| 卷积核大小 ≠ 候选模式长度 | **Strong evidence（方法学）** | 三配置模式长度中位数同为 4 nt | 直接可验证的方法学结论 |
| 第 18 位为候选序列相关位置 | **Moderate evidence** | 3/5 模型 top-3 + 跨模型平均谱第 1 + 细胞系依赖的实测效率差 + ISM 支持 | 位置效应与碱基效应不可完全分离 |
| GAGG / GGGG 候选模式富集 | **Context-dependent evidence** | FDR 0.030 / 7×10⁻⁶，但仅 HeLa（cell-line support = 1） | 不能外推为普适模式 |
| 各环境因子的主效应 | **Inconclusive / weak evidence** | $\|\Delta R^2\|<0.01$、91.3% 边 CI 跨 0、区组 ANOVA 不显著 | Tier 1/2 仅表示一致性，不表示强度 |
| CTGG 为高支持度模式 | **Model-specific / support-only** | 支持度最高（1 273），但 FDR = 1.0 | 已在 §3.6 明确 |
| 线性模型在部分运行中发散 | **Technical limitation** | 56/192 次 $\|R^2\|>10$ | 平台标记隔离而非删除 |
| `all`（LOCO）划分结果 | **Technical limitation** | `all` 与 `single` 逐位相同 | 不作泛化证据 |
| 注意力与梯度/树归因不一致 | **Model-dependent evidence** | 峰值位置差异；注意力不区分碱基通道 | 保留为方法学价值 |
| 候选 C1/C2/C3 | **Testable hypothesis（L4）** | 由上述证据按预先标准优先排序 | 未经实验验证 |

---

## 表 5 v2 图表与结果文件映射

| 图表 | 内容 | 来源 |
| :--- | :--- | :--- |
| Figure 1 | 平台科学发现流程 | —（示意图） |
| Figure 2 | 预测性能（A/B/C） | `tables/experiment_table.csv`、`loco_performance.csv` |
| Figure 3 | 环境增量与统计证据（A–D） | `environment_main_effects.csv`、`bootstrap_results.csv`、`anova_results.csv` |
| Figure 4 | 跨模型序列归因 + 第 18 位 | `attribution_summary.csv`、`position18_*.csv` |
| Figure 5 | 多尺度 CNN（A–D） | `docs/paper_analysis/cnn_kernel_paired.csv`、`kernel_position_profile.csv`、`motif_candidates.csv` |
| Figure 6 | 细胞系背景异质性（A–C） | `environment_by_cellline.csv`、`cellline_effects.csv` |
| Figure 7 | 证据整合（环境因子 CI + 等级） | `evidence_matrix.csv`、`docs/paper_analysis/factor_level_ci.csv` |
| Figure S1（补充） | Importance–ΔR² 辅助视图 | `importance_vs_delta_r2.csv` |
| Table 1 | 数据集组成 | `data/proceeded_data/*_metadata.csv` |
| Table 2 | 预测性能汇总 | `tables/experiment_table.csv` |
| Table 3 | 环境因素完整证据 | `environment_main_effects.csv`、`bootstrap_results.csv`、`permutation_results.csv`、`anova_results.csv`、`cellline_effects.csv`、`evidence_matrix.csv` |
| Table 4 | 核消融配对结果 | `docs/paper_analysis/cnn_kernel_paired.csv` |
| Table 5 | 代表候选模式 | `motif_candidates.csv`、`motif_enrichment.csv` |
| Table 6（新） | 候选假设与最小扰动方案 | 由上述 artifact 汇总生成 |
| Table S1/S2 | 阈值清单 / 跨模型位置一致性 | `analyse/config.py`、`docs/paper_analysis/cross_model_position_consistency.csv` |
