将你项目中的统计学工具、生信及建模参数按照这四个维度进行严谨归类与拆解：

---

### 1. Effect（变化幅度 / 效应量）

回答「这个因素改变后，模型预测或实际活性会改变多少」，体现具体的数值跳变与方向。

* **逐样本配对 $\Delta R^2$（Paired $\Delta R^2$）**：同背景下引入新表观通道与基线模型的表现差值（$\Delta = R^2_{\text{扩展}} - R^2_{\text{基线}}$）。


* **环境主效应（`main_r2_delta`）**：固定配置下跨 8 种背景上下文、跨随机种子求均值后的边际 $\Delta R^2$ 变化量。


* **条件增量与成对交互项（Lattice Edge Delta & `interaction_r2`）**：在析因 DAG 图上单步加通道的边级增量，以及两个表观通道间的两两交互差值。


* **ANOVA 主效应调整差（`effect` on $-$ off）与 $\eta^2$ / partial $\eta^2$**：控制区组后各表观通道对留出 $R^2$ 的边际改变量与方差解释比。


* **有符号突变归因（Position-18 Signed Substitution ISM）**：将特定位置（如位置 18）突变为不同碱基引起的预测活性实测增减量（$\hat{y}_{\text{mut}} - \hat{y}_{\text{wt}}$）。


* **线性模型回归系数（Regression Coefficients / Weights）**：一维线性模型的真实特征权重（反映单位特征变动对预测的边际影响）。


* **Motif 富集优势比（Odds Ratio, OR）**：高活性序列相比于背景富集某类 k-mer/seqlet 的倍数幅度。



---

### 2. Importance（预测贡献 / 依赖程度）

回答「模型在做前向推理时，内部多大程度依赖这个特征/位点」，体现特征在黑盒表征中的敏感性与归因权重（全项目原生实现均为**无符号幅度**）。

* **集成梯度（CNN Integrated Gradients, `cnn_ig`）**：分析层评估特征位点重要性的基准代表性归因方法。


* **无符号计算机诱变（CNN In-silico Mutagenesis, `cnn_ism`）**：每次实验测试样本对特征突变的无符号响应幅度均值（$\vert{}\Delta \hat{y}\vert{}$）。


* **信噪比分档指标（`ISM_SNR`）**：筛选关键调控生物标志物时度量归因信号清晰度的指标（分档阈值 2.5/1.8/1.2）。


* **Transformer 自注意力权重（Attention Weights）**：Transformer 架构中各序列位置之间的互相关联权重（仅作辅助归因）。


* **重要性分布谱（Attribution Profiles）**：跨 23 个碱基位置归一化后的相对贡献分布（如 `position_profile_by_model`、`region_attribution`）。



---

### 3. Statistical Evidence（统计证据强弱）

回答「观察到的效应或差异，究竟是真实信号还是纯随机噪声」，提供严格的假设检验与假阳性防护。

* **Bootstrap 置信区间（Bootstrap CI，通用 / 配对 / 行级）**：
* 通用估计量重抽样 CI（$B=2000, \alpha=0.05$）；


* 配对模型指标差值 CI（用于零交叉 `ci_crosses_zero` 过滤）；


* ANOVA 效应量行级 CI（400 次重抽样）；


* 极端位置审计 CI（$B=10\,000$ 或 $\text{mean} \pm 1.96\text{SE}$）。




* **符号翻转置换检验（Sign-flip Permutation Test）**：
* 在零假设下通过随机反转配对差值符号构造经验零分布，计算单/多因子的精确经验 $p$ 值（$B=1000$）。




* **Benjamini-Hochberg FDR（BH-FDR 多重比较校正）**：
* 按科学问题分族隔离（`family_key`）的错误发现率校正（控制 $\text{FDR} \le \alpha$）。




* **Factorial ANOVA $F$ 检验（Type-II Marginal F-test）**：
* 检验剥离区组方差后，表观环境通道额外平方和是否显著脱离零点（给出 $F$ 统计量与 $p$ 值）。




* **Fisher 精确检验（Fisher's Exact Test）**：
* 用于 Motif 候选模式在前景与背景序列中 $2 \times 2$ 列联表的显著性检验。




* **线性模型参数显著性检验（Linear $t$-test / $p$-value）**：
* 训练侧线性回归特征权重的 $t$ 检验及其配套的 BH-FDR。





---

### 4. Robustness（结论稳定程度 / 跨域泛化）

回答「这个结论换了模型、随机种子、细胞系或数据划分后还站得住脚吗」，度量结论在不同扰动下的抗噪性与收敛性。

* **细胞系一致性判定（Cell-line Consistency Framework）**：
* 基于 `consistent_ratio=0.75`、`conflicting_ratio=0.25` 以及异质性比率（`heterogeneity_ratio=2.0`）综合判定的四大跨细胞系统计标签；


* 区间重叠松弛机制（`ci_overlap_relaxes=True`）。




* **跨模型方向一致性（Direction Concordance & Supporting Models）**：
* 评估至少 2 个以上模型结构给出相同方向的比例（阈值 $\ge 0.80$）。




* **跨模型位置归因一致性（Cross-model Position Consistency）**：
* 多模型归因谱之间的两两 Spearman 秩相关系数（0.28–0.61）与 Top-3 峰值位点重合度（0.30–0.53）。




* **多种子保守并集（Conservative Union across Seeds）**：
* 跨 4 个随机种子（42/43/44/45）合并 CI 时取 $\min(\text{ci\_low})$ 与 $\max(\text{ci\_high})$，并要求全种子不跨零（`excl_all`）。




* **留一细胞系泛化评估（LOCO / `all` Split）**：
* 3 细胞系训练、1 细胞系 100% 留出测试，评估跨宿主细胞系迁移预测的泛化稳定性。




* **综合证据分级矩阵（Evidence Tiering Matrix）**：
* 统合 Bootstrap CI、置换检验 FDR、覆盖模型数（`min_coverage=2`）及跨细胞系标签，裁定属于 Tier 1（强收敛）、Tier 2、Tier 3 还是 Inconclusive（无定论）的最终仲裁机制。





---

### 5. 跨维度的基础支撑参数（生信与建模底座）

这部分参数不单独属于某一维度，而是决定了上述四个维度度量质量的**数据基座与约束条件**：

* **序列与表观编码规范**：23 nt 长度（20 nt protospacer + NGG PAM，PAM 恒在 21–23 位），A/C/G/T 四通道 + 4 个二值化表观通道（未选时 mask 置 0）；


* **划分机制**：0.70 / 0.15 / 0.15 非分层随机划分（针对 mixed 采用 4 种子；single/all 采用固定种子 42）；


* **发散过滤与截断阈值**：$\vert{}R^2\vert{} > 10$ 强行剔除（防止极端异常主导总体方差），模型指标取验证集最小损失回滚轮次（Best Epoch）而非训练末轮。