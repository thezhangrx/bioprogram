# 论文第二轮科学重构说明（paper_revision_v2）

对象：`paper/`（v1 = `compiled/main.pdf`，22 页；v2 = `compiled/main_v2.pdf`，23 页）
原则：不夸大、不伪造、不改训练体系；保留全部真实结果，仅重组叙事、强化/降级证据、修正数值口径。

---

## 一、修改总览

| 章节 | v1 状态 | v2 修改 | 理由 |
| :--- | :--- | :--- | :--- |
| Abstract | 罗列 6 项结果 | 重写为 Background→Gap→Platform→Methods→Key findings→Significance→Limitation，仅保留 5 项代表性发现，结尾明确 "computational case study" | 赛道与期刊都要求摘要有明确边界；避免"结果堆叠" |
| Introduction | 以模型演进为主 | 重组为 6 块：CRISPR 设计 → ML 预测 → 仅预测的局限 → 可解释性/因素发现缺口 → 发现流程 → 研究问题；**减少模型论文罗列** | 突出"为什么需要平台"而非"有多少模型" |
| Methods | 含大量工程细节 | 保留科学严谨性，压缩工程描述（移入附录/仓库文档）；新增 4 项方法学声明：LOCO 退化、证据等级定义、importance 归一化不可跨模型比较、候选优先级六条标准 | 让方法服务于科学主张与可复核性 |
| Results | §3.1–3.7（含 v1 §3.7 混合证据） | 重构为 §3.1–3.8（新增 3.6 候选模式独立成节、3.8 证据整合与候选优先级），每节统一"问题与方法 / 观察 / 稳健性 / 解释与限制" | 按科学逻辑而非代码模块组织 |
| Discussion | 5 节 | 重写为 8 节（发现什么 / 多模型价值 / 环境为何弱 / 第 18 位含义 / 感受野含义 / 细胞背景 / 未验证内容 / 如何设计实验）+ 赛道能力对照 | 直接回应评审最关心的解释与边界 |
| Limitations | 7 条 | 增补"已完成 vs 未完成"总述、环境效应量级与 Tier 的关系、importance 不可比、候选仅单细胞系富集、工具范围（PAM/系统） | 把限制写具体、可核查 |
| Conclusion | 6 条 | 重写为平台定位 + 5 条结论 + 两条后续主线 | 与摘要、Results 对齐 |
| **新增 §7 未来实验验证** | 无 | 新增 3 个方向（C1 单碱基替换 / C2–C3 模式破坏 / 独立数据集 + 真正 LOCO）与判定标准 | 赛道"实验验证"项需要可执行方案，但不得虚构实验 |

---

## 二、被强化的结果（进入主线）

| 结果 | v1 位置 | v2 强化方式 |
| :--- | :--- | :--- |
| **PAM 邻近区域多模型一致归因（4/5 模型类最高区域）** | §3.4 一段 | 提升为 §3.4 首个观察，明确"多模型独立支持"是平台核心证据；区分**位置效应 vs 碱基特异性效应** |
| **第 18 位（3/5 模型 top-3、跨模型平均谱第 1 位）** | §3.4 观察 3 | 与实测效率（+0.090/+0.092/+0.028/−0.016）与 CNN ISM 细胞系差异并列为**三条独立证据链**；直接进入候选 C1 |
| **CNN 核 3/5/7 配对结果（+0.042 / +0.056 / +0.013）** | §3.5 | 重定位为 **multi-scale local sequence context analysis**，按"性能→解释→模式长度"三层展开，并升级为方法学亮点（感受野 ≠ 模式长度） |
| **候选假设表（新 Table 6）** | 无 | 从 artifact 自动生成 4 行候选（C1 第 18 位 / C2 GAGG / C3 GGGG / CTGG 参考），含多模型支持、效应、稳健性、最小扰动与优先级 |
| **证据整合的分层输出** | §3.7 简述 | 明确"平台既输出 consensus 也输出 model-dependent evidence"，把跨模型分歧写成方法学价值 |

---

## 三、被降级的结论

| 结论 | v1 处理 | v2 处理 | 依据 |
| :--- | :--- | :--- | :--- |
| 环境因素 Tier 1/2 | 与效应并列表述 | 统一声明 **evidence tier ≠ biological effect strength**，并在 Results/Discussion/Table 三处标注 $|\Delta R^{2}|<0.01$ | Tier 由一致性/覆盖度/CI 决定，与效应量级无关 |
| Importance–ΔR² 图 | 正文 Figure 7B | **移至 Supplementary（Figure S1）**，并声明 $ \Delta R^{2}\neq$ importance、importance $\neq$ 显著性、importance 仅在模型内归一化 | 避免被误读为显著性图 |
| CTGG | "最高支持度模式" | 明确 **FDR = 1.0（未通过富集校正）**，仅作高支持度候选参考，优先级 low | artifact：support 1273、effect −0.046、OR 0.835、FDR 1.0 |
| "跨模型一致" | 部分表述较强 | 改为"一致部分 + 分歧部分并列"：线性峰值偏移、注意力与梯度/树归因不一致、MLP importance–ΔR² 方向相反 | 保留真实分歧 |
| LOCO | 已在 v1 说明退化 | 在 Methods、Results、Limitations、Future 四处统一声明；**明确"真正的 LOCO 属后续工作"** | `max\|R²_all − R²_single\| = 0` |
| "智能设计" | 标题沿用 | Methods/Discussion 明确当前为 **candidate prioritization / ranking**，非 de novo generation | `workflows/prediction/predict.py --generate-candidates` 的实际实现 |

---

## 四、从正文移入 Supplementary 的内容

| 内容 | v1 | v2 |
| :--- | :--- | :--- |
| Importance–ΔR² 图 | 正文 Figure 7B | **Supplementary Figure S1**（正文 Figure 7 仅保留环境 CI + 证据等级） |
| 分析阈值完整清单 | 正文 Methods 列表 | 保留摘要式描述，完整表在 Supplementary Table S1 |
| 跨模型位置一致性明细表 | 正文（v1 表 S2 引用） | Supplementary Table S2 |
| 7 770 行 bootstrap / 3 444 行置换 / 94 项 ANOVA / 596 模式明细 / 545k→172k seqlet 实例 | 部分在正文描述 | 全部指向 `results/` 与 Interactive Report |
| 工程实现细节（模块、接口、测试） | 正文 Methods 若干段 | 仓库文档 `docs/project_pipeline_and_code_documentation.md` |

---

## 五、新增的限制声明

1. **已完成 vs 未完成**：计算验证（1 344 次受控实验、统计推断、跨细胞系比较、候选发现）已完成；湿实验、独立生物学验证、真正 LOCO 重训未完成。
2. **证据等级语义**：Tier 反映一致性与稳健程度，不代表效应强度；$|\Delta R^{2}|<0.01$ 时高 Tier 不等于"强因素"。
3. **importance 不可跨模型比较**：仅在模型/分析组内归一化。
4. **候选模式的细胞系局限**：通过富集的模式（GAGG/GGGG）目前仅在 HeLa 达到显著（cell-line support = 1）。
5. **位置效应与碱基效应不可完全分离**（第 18 位）。
6. **工具范围**：仅 SpCas9 + NGG PAM；非经典 PAM、其他 Cas 变体、碱基编辑未纳入。
7. **设计能力边界**：候选优先级排序，不含序列从头生成。

---

## 六、数值审计驱动的修正（以 artifact 为准）

| 项目 | v1 文本 | v2 文本（artifact 值） | 来源 |
| :--- | :--- | :--- | :--- |
| XGBoost mixed 中位 $R^{2}$ | 0.164 | **0.161** | `tables/experiment_table.csv` |
| seqlet 实例数 / 上下文数 | 545 060 / 80 | **172 098 / 24** | `tables/motif_instances.csv` |
| GGGG 携带者效应 | +0.047 | **+0.060**（OR 1.38，FDR $7\times10^{-6}$） | `tables/motif_candidates.csv` + `motif_enrichment.csv` |

其余全部数值经脚本重算一致（见 `docs/paper_quality_check_v2.md` 的 Numerical Audit 表）：16 749、1 344、各模型中位 R²、56/192 发散、核配对 +0.0423/+0.0557/+0.0134、166/1 906、257/2 541、6/2 688、35/252、9/504、ANOVA $F/p$/$\eta^2$、596/64、第 18 位 C−A 四细胞系、方向一致率 0.86/0.71。

---

## 七、未改动的内容（刻意保留）

- 所有训练配置、随机种子、阈值配置（`analysis/config.py`）与 `results/` 产物：**零修改**（本轮仅只读）。
- 分析引擎与训练代码：**零修改**。
- 参考文献：仍为 12 篇已核验条目，未新增、未重复。
- 全部"不漂亮"的结果：线性模型 56 次发散、注意力峰值与梯度/树归因不一致、MLP importance–ΔR² 负相关、环境效应弱且方向不一致——全部保留在正文。

---

## 八、v2 的科学定位（最终表述）

> 本工作构建的是一个**基因编辑影响因素科学发现平台**：从已有编辑实验数据出发，通过受控多模型预测、模型归因、统计推断、环境增量分析、序列模式挖掘、细胞背景比较与证据整合，逐层产生**候选影响因素与可检验假设**。DeepCRISPR 案例用于展示该流程的工作方式与边界，而不是主张平台在所有编辑系统上均适用。

平台的科学性不来自"所有分析都得到阳性结果"，而来自能够在统一、可追溯的框架中区分**稳定证据、模型特异性现象、上下文依赖现象与不确定结果**。
