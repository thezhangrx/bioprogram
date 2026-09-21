# Gemini Prompt for CRISPR AI Discovery Platform Presentation

> **本文件是给 Gemini 的"生成 PPT 的提示词"，不是 PPT 本身。**
> 请把本文件整段作为 prompt 交给 Gemini（或任何 PPT 生成模型）。
> 本文件中所有数字均来自本项目当前权威产物，**Gemini 不得改写、不得四舍五入到失真、不得补造**。

---

## 0. 使用说明

- **唯一事实来源**：本文件第 2 节「硬性事实清单」与第 4 节「四维度证据评价体系」。
  凡是本文件没有给出的数字，Gemini **不得自行生成**；宁可不写数字，也不要编。
- **受众**：导师、评审专家、科研交流同行。
- **页数**：建议 18–22 页（含封面与结尾），每页一个核心观点。
- **语言**：中文正文 + 英文术语（首次出现时中英并列）。

---

## 1. PPT 定位

### 1.1 一句话定位

> 这不是一个"训练模型"的项目，而是一个**基于人工智能与统计学分析的 CRISPR-Cas9 sgRNA 编辑效率影响因素挖掘平台**。

### 1.2 核心目标

平台不只预测 editing efficiency，更要完成五件事：

1. 整合**序列信息**与**细胞环境（cell environment）**信息；
2. 用**多模型**学习复杂规律；
3. 用**统计学**与**可解释 AI** 方法挖掘影响因素；
4. 从预测结果中提取**潜在生物学规律**；
5. 形成从**数据到科学假设**的分析闭环。

### 1.3 科学逻辑主线（贯穿全篇）

$$
\boxed{
\text{数据}
\rightarrow
\text{模型}
\rightarrow
\text{统计分析}
\rightarrow
\text{规律挖掘}
\rightarrow
\text{科学解释}
}
$$

### 1.4 风格要求

- **科研汇报风格**：简洁、克制、高级；
- 参照 **Nature / Cell / Science 补充材料 presentation** 的视觉语言；
- **大量使用**流程图、示意图、统计图；
- **禁止**代码截图、目录树、参数列表堆砌、大段文字；
- 每页：一个核心观点 + 一个主要图 + 少量文字（≤ 5 行要点）。

---

## 2. 硬性事实清单（Gemini 只能使用这些数字）

### 2.1 数据集（三个独立数据集）

| 数据集 | 样本数 | 细胞系 | 环境通道 | 标签语义 | 来源 |
|---|---|---|---|---|---|
| **DeepCRISPR**（主数据集） | **16 749** | hct116 4 239 / hek293t 2 333 / hela 8 101 / hl60 2 076 | CTCF, Dnase, H3K4me3, RRBS（4 条） | 归一化编辑效率 [0,1] | Chuai et al. 2018, *Genome Biology* |
| **Hiranniramol**（外部复现） | **1 309** | 单细胞系 | 无 | `Edit Efficiency`（原 0–100 百分制，适配器 /100） | Hiranniramol et al. 2020, *Bioinformatics* 36(9):2684–2689 |
| **Labuhn**（外部复现） | **417** | 单细胞系 | 无 | `KO_reporter_assay`（已是 [0,1]） | Labuhn et al. 2018, *NAR* 46(3):1375–1385 |

**必须强调**：三个数据集的 **label semantics 不同**，不可当作同一个物理量比较。
跨数据集的 R² 只能读作"同一流程在不同数据集上的可预测性"。

序列定义：**23 nt = 20 nt protospacer + 3 nt PAM（NGG）**，PAM 位于第 21–23 位，**已包含在模型输入中**。

### 2.2 实验矩阵

- **1 344 次受控实验** = 7 个模型配置 × 16 种环境组合 × 12 个（划分, 种子）设定
- 三种划分各 **448**：`single`（细胞内 70/15/15）、`all`（真实留一细胞系 LOCO）、`mixed`（跨细胞系 70/15/15，种子 42–45）
- 外部数据集：各 **7** 次运行（`single`，7 个模型配置）
- 划分身份类：`min(sequence, revcomp(sequence))` —— 同一 sgRNA 及其反向互补视为同一身份，**不跨 train/valid/test**

### 2.3 模型（7 个配置 / 5 类）

| 模型 | 角色 | 可解释性工具 |
|---|---|---|
| Linear Regression | 基线 + 系数方向与统计推断 | 系数、SE、t、p、BH-FDR |
| XGBoost | 非线性与交互 | 原生 TreeSHAP |
| MLP | 一般非线性组合 | Integrated Gradients（IG） |
| 双分支 CNN（卷积核 3/5/7） | 位置特异的局部序列模式 | IG + In-silico mutagenesis（ISM） |
| Transformer | 跨位置长程依赖 | 注意力权重 |

> 关键表述：**模型不是最终答案，而是产生可解释证据的工具。**

### 2.4 核心结果（必须如实呈现，包括阴性结果）

**（1）跨数据集复现：序列可预测性是数据集依赖的**

| 数据集 | 测试 R² | 结论 |
|---|---|---|
| DeepCRISPR（`single` 7 配置中位） | **+0.067 … +0.120** | 弱正信号 |
| Hiranniramol | **+0.345 … +0.489**（Transformer 最高 R²=0.489, Pearson=0.709） | **复现成功** |
| Labuhn | **−0.725 … −0.050（7/7 全为负）** | **复现失败** |

**独立复核**（与官方划分无关的全数据 5 折交叉验证 + 200 次标签置换零分布）：
Hiranniramol CV R²=**+0.3886** vs 零分布 **−0.4668±0.0375**；Labuhn CV R²=**−0.1444** vs **−0.2869±0.0505**。

**Labuhn 失败机制**：标签标准差 0.2153（**不是低方差**）；6/7 个配置的「预测标准差/标签标准差」仅 **0.03–0.37**（预测坍缩）；Linear 例外（0.93）但与真值不相关（r=0.165），故 R² 最低 −0.725。

**（2）跨细胞系泛化失败**：LOCO 下 7 个配置中位 R² 全部落在 **−0.027 至 +0.010**（与均值基线不可区分）；按留出系展开异质性极大（HEK293T 最低 −0.266）。

**（3）环境通道未检出增量预测价值**（4 个因子全部 Inconclusive）：

| 因子 | 跨模型等权平均 ΔR² | 95% 区间 | effect 门（\|ΔR²\|≥0.01） | 组内最小边级 FDR | 区组 ANOVA p | 证据等级 |
|---|---|---|---|---|---|---|
| CTCF | +0.0003 | [−0.0035, +0.0038] | 未通过 | 0.0070 | 0.9892 | Inconclusive |
| DNase | +0.0013 | [−0.0013, +0.0043] | 未通过 | 0.0070 | 0.9996 | Inconclusive |
| H3K4me3 | −0.0007 | [−0.0033, +0.0018] | 未通过 | 0.0070 | 0.9753 | Inconclusive |
| RRBS | −0.0015 | [−0.0040, +0.0010] | 未通过 | 0.0070 | 0.9867 | Inconclusive |

效应量级 **3.2×10⁻⁴ – 1.5×10⁻³**，比预设门槛 0.01 低 **1–2 个数量级**；四个区间全部跨 0。

**（4）多模型归因指向 PAM 邻近位置（但必须分两个层级讲）**

- **位置层级（较强）**：XGBoost 逐上下文峰值落在 17–20 的比例 **100.0%（64/64）**、CNN **96.9%（62/64）**、MLP **90.6%（58/64）**、Transformer **65.6%（42/64）**；**Linear 例外，仅 21.9%（14/64），峰值在第 1 位**
- **跨模型平均谱**：五模型（含 Linear）峰值是 **第 1 位（0.0864）**；**剔除 Linear 后峰值才是第 18 位（0.0878）**
- **区域层级（仅部分一致）**：只有 **2/5** 个模型类的最高区域是 PAM 邻近种子区（XGBoost 0.327、Transformer 0.325）；CNN（0.344）与 MLP（0.336）最高区域是种子核心区；Linear 最高区域是 PAM 远端区（0.416）
- 跨模型位置谱平均两两 Spearman = **0.34**，top-3 重叠率 **0.42**

**（5）外部模型验证（独立第三方模型 CRISPRon）**

8 条预登记 WT 序列（第 18 位为 C），仅替换第 18 位一个碱基（C→A）：
- 本文 7 个模型与 CRISPRon 的扰动方向 **7/8 一致**（Pearson r=**0.629**，Spearman ρ=**0.476**，n=8）
- CRISPRon 侧 **7/8** 为负向，Δ 均值 **−12.43**，范围 −27.17 至 +9.16
- **唯一分歧样本 WT08 被保留在统计中，未剔除**

**（6）反事实扰动（饱和突变，无位置预设）**

552 条单碱基替换记录（8 序列 × 23 位点 × 3 替换），48 条破坏 PAM 被排除，504 条计分：
**第 18 位平均 |Δ| = 12.86，排名 1/21**（其后 17 位 7.68、20 位 7.18、19 位 6.99、16 位 5.36）；
第 18 位 C→A 平均变化 **−12.425**，其余位置平均仅 **+0.144**；逐序列 7/8 条排第 1。

**（7）观测性关联（E2，独立于模型）**

第 18 位 C 减 A 的**实测**平均效率差：HCT116 **+0.090**、HeLa **+0.092**、HL60 **+0.027**、**HEK293T −0.015（方向反转）**。
独立对照：GC–效率相关 Hiranniramol r=+0.262（p<10⁻⁴）、Labuhn r=+0.094（p=0.054）。

**（8）数据质量审计**

1 344/1 344 次运行的 train∩test 序列重叠与反向互补重叠**均为 0**；`split_digest` 逐条复核 **0 处不一致**；数据/代码/环境指纹各只有一种取值；960 个神经网络 run 全部在 GPU 上执行。
数值发散 run（|R²|≥10）**20 次**（测试集口径，全部为 Linear Regression），隔离而非删除。

---

## 3. 幻灯片逐页规划

> 每页给出：**页面标题 / 核心观点 / 需要展示的科学逻辑 / 图形设计建议**。
> Gemini 应按此结构生成，但文案需自行优化为演讲语言。

### 封面
- **标题**：面向 CRISPR-Cas9 编辑效率的 AI × 统计学影响因素挖掘平台
- **副标题**：从预测到规律发现 —— 多数据集复现、多模型外部验证与四维度证据体系
- **图形**：一条从左到右的极简流程线（数据 → 模型 → 证据 → 假设），无文字堆叠

### Slide 1 — 科学问题：编辑效率由什么决定？
- **核心观点**：sgRNA 编辑效率受多因素影响，但"哪些因素真正重要"仍未被可靠回答
- **科学逻辑**：介绍影响因素的五类候选 —— nucleotide sequence、PAM、position-dependent sequence preference、chromatin accessibility、transcriptional environment、epigenetic features
- **核心科学问题（突出显示）**：
  > 哪些因素真正影响 CRISPR 编辑效率？这些影响是否具有跨模型、跨数据集的稳定性？
- **图形**：sgRNA–Cas9–DNA 示意 + 六类因素环绕的辐射图；右下角小字："预测只是第一步"

### Slide 2 — 现有研究的缺口
- **核心观点**：绝大多数工作报告单一数据集、单一次划分的精度，既不检验复现，也不做外部验证
- **科学逻辑**：预测精度 ≠ 可复现规律；同源序列泄漏会系统性高估性能
- **图形**：左右对比 —— "通常做法：单数据集 + 随机划分" vs "本研究：多数据集 + 身份类划分 + 外部模型验证"

### Slide 3 — 平台整体流程（**重点页，建议全页流程大图**）
- **核心观点**：平台是一条从原始数据到生物学假设的完整证据链
- **流程图（全页）**：

```
Raw Data → Quality Control → Data Preprocessing → Feature Engineering
   → Multi-model Learning → Prediction Evaluation → Interpretability Analysis
   → Statistical Evidence → Biological Hypothesis
```

- **每个模块下方一行作用说明**（见 Slide 4–8）

### Slide 4 — 数据与质量控制（QC）
- **核心观点**：数据质量决定后续统计解释的可信度
- **科学逻辑**：QC 的目的不是"清洗数据"，而是保证**结论可信**——数据可靠、无泄漏、无异常主导、跨细胞系可比
- **需要展示的 QC 维度**（6 项）：
  sequence validity / missing value / feature distribution / duplicate detection / **split integrity（身份类不跨划分）** / feature variance check
- **实测数据**：1 344/1 344 run 序列与反向互补重叠 = 0；`split_digest` 0 处不一致；20 个发散 run 被隔离
- **图形**：漏斗图（原始 → QC → 入模），或六格 QC 检查清单 + 每格一个勾

### Slide 5 — 数据预处理与特征表示
- **核心观点**：平台把"序列"与"细胞环境"编码进同一个张量
- **科学逻辑**：raw sgRNA → sequence encoding → environment feature integration → model input tensor
  - sequence：nucleotide information + position-specific information（23 × 4 one-hot）
  - environment：CTCF / DNase / H3K4me3 / RRBS（23 × 4 逐位点二值）
- **强调**：平台采用 **config-driven feature schema**，环境变量可扩展而不改代码
- **图形**：左侧 sgRNA 序列 → 右侧 (23, 8) 张量热图；下方标注 "23 nt = 20 protospacer + 3 PAM"

### Slide 6 — 多模型学习（不讲代码，只讲"不同模型学不同规律"）
- **核心观点**：不同归纳偏置的模型互补，用于产生**可解释证据**而非刷分
- **科学逻辑**（五个卡片）：
  - **Linear Regression**：寻找线性贡献 → 适合 baseline 与 feature coefficient interpretation
  - **XGBoost**：树结构学习非线性关系 → 结合 SHAP 回答"哪些 feature 推动预测上升/下降"
  - **CNN (k=3/5/7)**：学习 position-specific motif 与 local sequence pattern
  - **Transformer**：学习 long-range dependency 与 complex sequence interaction
  - **MLP**：一般非线性组合
- **图形**：五个模型图标 + 各自的"学习目标"标注；底部横幅："模型不是最终答案，而是产生可解释证据的工具"

### Slide 7 — 预测性能：三个数据集给出三个不同结论（**关键页**）
- **核心观点**：序列可预测性是**数据集依赖的**，不可假定为可移植
- **科学逻辑**：同一套流程、同一批模型、同一评估脚本，在三个独立数据集上给出三种结果
- **图形（推荐 bar + 零参考线）**：三组柱状图 —— DeepCRISPR 0.067–0.120、Hiranniramol 0.345–0.489、Labuhn 全部为负（−0.725 至 −0.050）；叠加独立 5 折 CV 与标签置换零分布区间
- **必须出现的副图**：Labuhn 的"预测坍缩"诊断（预测标准差/标签标准差 = 0.03–0.37，对照 Hiranniramol 0.67–0.83）

### Slide 8 — 跨细胞系泛化失败
- **核心观点**：模型能学到序列信号，但该信号**不能跨细胞系迁移**
- **科学逻辑**：真实留一细胞系（LOCO）下，7 个配置中位 R² 全部落在 −0.027 至 +0.010，与均值基线不可区分
- **图形**：LOCO 按留出系展开的小提琴图/散点图（HEK293T 最低 −0.266）

### Slide 9 — 环境因素的影响：未检出（诚实的阴性结果）
- **核心观点**：四个表观遗传因子均未达到预设的增量预测门槛
- **科学逻辑**：效应量 3.2×10⁻⁴–1.5×10⁻³，比门槛 0.01 低 1–2 个数量级；区间全部跨 0；ANOVA 主效应 p=0.975–0.9996
- **措辞纪律**：必须写成 **"未检出（not detected）"**，不能写成"无作用（no effect）"
- **图形**：forest plot（四个因子的 ΔR² 与 95% CI）+ 门槛竖虚线 0.01；右侧配 ANOVA p 值小表

### Slide 10 — 四维度证据评价体系（**核心章节，建议 1 页总览 + 4 页展开**，详见第 4 节）
- **核心观点**：四个维度回答四类**不同的**科学问题，不可互相替代
- **图形**：四象限/阶梯图 `Performance → Attribution → Statistical Evidence → Robustness`

### Slide 11–14 — 四个维度各自展开（见第 4 节每维度的 5 项要求）

### Slide 15 — 多模型序列归因：PAM 邻近位置
- **核心观点**：四个非模型类的位置归因高度集中于 PAM 邻近窗口，但**线性模型例外**，且区域层级只有 2/5 一致
- **图形（推荐位置热图/谱线）**：23 个位置的归一化归因谱（各模型一条线），阴影标注 17–20 与 21–23；下方两张小图：(a) 逐上下文峰值落在 17–20 的比例条形图；(b) 区域汇总堆叠条形图（显示 2/5）

### Slide 16 — 外部模型验证：独立第三方模型确认方向
- **核心观点**：把归因结论从"我们的模型这样做"推进到"两个独立构造的模型系统同向响应"
- **科学逻辑**：CRISPRon 在训练数据、输入编码（30 nt + CRISPRoff 能量项）、输出尺度上均与本文平台不同；8 条预登记 WT、仅改第 18 位一位碱基；**7/8 方向一致**，唯一分歧样本保留
- **图形**：配对斜率图（WT → C18A 的 CRISPRon 评分配对变化）+ 散点图（Δ_ours vs Δ_CRISPRon，标注 WT08 为分歧点）

### Slide 17 — 无位置预设的反事实扰动
- **核心观点**：饱和突变**独立地**把第 18 位排在首位——排除"我们恰好挑了一个看起来重要的位置"
- **科学逻辑**：552 条单碱基替换穷举（48 条破坏 PAM 被排除）→ 第 18 位平均 |Δ| 排名 1/21；C→A 平均 −12.425 vs 其余 +0.144
- **图形**：21 个位置的平均 |Δ| 条形图（第 18 位高亮）+ 逐序列排名小图

### Slide 18 — 观测性关联：独立于模型的第三条证据
- **核心观点**：实测标签在三个细胞系上给出与模型同向的碱基关联，但 **HEK293T 方向反转**
- **图形**：四细胞系分组柱状图（C vs A 的实测平均效率），HEK293T 用不同颜色标注反转

### Slide 19 — Interpretation Limitation（**必须单独一页**）
- **核心观点**：解释工具各有其"能说"与"不能说"
- **科学逻辑（四行对照表，见第 6 节）**：
  - SHAP → 说明**模型依赖**
  - Integrated Gradients → 说明**模型内部路径归因**
  - ISM / 反事实扰动 → 说明**模型预测变化**
  - Permutation / FDR / ANOVA → 说明**统计可信度**
  - **只有实验（wet-lab）才能证明真实生物效应**
- **图形**：阶梯图 —— 模型解释 → 统计证据 → 实验验证，前两级在本研究中，第三级标注"未做"

### Slide 20 — 从证据到生物学假设
- **核心观点**：本文唯一被写成"候选假设"的结论是第 18 位，且它止步于可证伪假设
- **科学逻辑**：第 18 位同时获得 E2（实测关联）、E3（多模型归因）、E4（模型反事实 + 外部模型）三层**互相独立**的支持；**不含任何 E5（实验）证据**
- **假设陈述（可直接引用）**：
  > 在本文数据覆盖的 sgRNA 中，PAM 邻近区第 18 位的碱基身份与编辑效率存在关联，方向在多个模型族与一个独立外部模型上一致；第 18 位由 C 替换为 A 会降低编辑效率。该效应大小依赖细胞背景。
- **图形**：三层证据汇聚到第 18 位的汇聚图（convergence diagram）+ 右侧"最小扰动方案"示意（仅改 1 nt）

### Slide 21 — 未来发展
- **数据扩展**：more cell lines / more epigenetic features / single-cell data
- **模型扩展**：foundation model / multimodal AI / biological language model
- **实验验证**：CRISPR screening / Perturb-seq / wet-lab validation
- **最终目标**：AI-driven CRISPR biological discovery platform
- **图形**：三轮扩展的同心圆或路线图

### 结尾页
- **一句话**：本平台不追求最高准确率，而是建立 `Prediction → Interpretation → Evidence → Discovery` 的科学发现流程
- **图形**：与封面呼应的流程线，末端点亮"Discovery"

---

## 4. 四维度证据评价体系（Four-dimensional Evidence Framework）——**核心章节**

### 4.0 为什么需要它（总览页）

该体系不是罗列统计工具，而是用于回答 CRISPR 编辑效率规律挖掘中的**四类不同科学问题**：

$$
\boxed{
\text{Performance}
\rightarrow
\text{Attribution}
\rightarrow
\text{Statistical Evidence}
\rightarrow
\text{Robustness}
}
$$

**总览页必须出现的两条纪律**：

1. 四个维度**不可互相替代**：低维度的结论不能升级为高维度的结论。
2. **四维度并不覆盖全部证据类型**。本项目另有一套独立的 **六层证据分类（E1–E6）**，
   四维度大致对应 E1 + E3 + E4 + 统计支持，而 **E2（观测性关联）不在四维度内**，
   **E5（实验证据）在本研究中完全空缺**，**E6（因果）不作任何断言**。
   → PPT 必须显式呈现这一映射，避免让听众以为四维度已经把证据讲全了。

**映射表（建议单独做成一张图）**

| 四维度 | 对应本项目证据层 | 本项目是否具备 |
|---|---|---|
| D1 Prediction Performance | **E1** 预测证据 | ✅ 有（含跨数据集复现边界） |
| D2 Feature Attribution | **E3** 归因证据 + **E4** 反事实证据 | ✅ 有（含外部模型验证） |
| D3 Statistical Evidence | 为 E1/E2/E3 提供统计支持 | ✅ 有 |
| D4 Robustness & Generalization | **E1** 的稳健性与复现边界 | ✅ 有（但结论是"部分复现/部分失败"） |
| （维度外）**E2** 关联证据 | 第 18 位 C/A 分组实测效率差 | ✅ 有 |
| （维度外）**E5** 实验证据 | 湿实验验证 | ❌ **本研究无** |
| （维度外）**E6** 因果证据 | 因果结论 | ❌ **不作断言** |

---

### Dimension 1：Prediction Performance（预测能力）

**① 回答什么科学问题**
> 模型是否能够学习 sgRNA 与 editing efficiency 之间的关系？

这是整个分析体系的基础：**如果模型不能预测，后续解释没有意义。**

**② 使用什么数学指标**

- **R²（决定系数）**
  $$R^2 = 1 - \frac{SSE}{SST}$$
  回答："模型捕获了多少有效信息？"——模型预测能解释标签方差的比例。
- **RMSE**
  $$RMSE = \sqrt{\frac{1}{n}\sum_{i}(y_i - \hat{y}_i)^2}$$
  预测误差规模（与大误差同量纲）。
- **MAE**：平均预测偏差（对离群点更稳健）。
- 辅助：**Pearson r**（线性相关）、**Spearman ρ**（秩相关）。

**③ 使用哪些分析工具**

- 单次实验：留出测试集评估（训练时按验证损失早停并回滚至 best epoch checkpoint）
- 多模型比较：7 个模型配置，报告**中位数与四分位距**而非均值
- 三种划分对照：`single` / `mixed` / `all`（LOCO）
- 跨数据集：同一流程在 3 个独立数据集上运行
- **独立复核**：与官方划分无关的全数据 5 折 CV + 200 次标签置换零分布

**④ 可以解释什么**

✓ 模型是否有效学习规律
✓ 不同模型架构的性能差异
✓ 不同数据划分下的泛化能力
✓ **性能是否可跨数据集复现**（本项目最重要的用途）

**⑤ 不能解释什么**

✗ 哪个 feature 重要
✗ 某个生物因素是否导致编辑效率变化
✗ 因果关系

---

### Dimension 2：Feature Attribution（模型归因）

**① 回答什么科学问题**
> 模型认为哪些输入变量影响预测结果？

重点：解释**模型内部决策依据**。

**② 使用什么数学指标**

- **SHAP（Shapley value）**：把预测拆解为基线 + 各 feature 贡献
  $$f(x) = \mathbb{E}[f(x)] + \sum_i \phi_i$$
  $\phi_i$ 表示 feature $i$ 对预测的贡献。
  回答："模型预测为什么变高/变低？"（适用 XGBoost / 树模型）
- **Integrated Gradients（IG）**：沿 baseline→输入的路径累计梯度贡献
  $$IG_i(x) = (x_i - x'_i)\int_0^1 \frac{\partial F\big(x' + \alpha(x - x')\big)}{\partial x_i}\, d\alpha$$
  适用 CNN / Transformer；回答"哪些位置、哪些 feature 影响神经网络输出"。
- **注意力权重**：Transformer 的跨位置依赖（本项目**仅作支持性信息，不用于候选模式提取**）
- **SNR（归因稳健性）**：跨样本的效应均值与效应波动之比 —— **不是检验统计量**
  - CNN `ISM_SNR` = `mean(|Δŷ|)/std(|Δŷ|)`（标准形式）
  - XGBoost/MLP/Transformer = `mean(|φ|)/std(φ)`（混合形式，分母为有符号归因的标准差）
  - → 因此 **SNR 只在同一模型内部排序，不跨模型比较**

**③ 使用哪些分析工具**

| 工具 | 对象 | 本项目产物 |
|---|---|---|
| 线性系数（含 SE / t / p / BH-FDR） | Linear | `linear_*_weights.csv` |
| 原生 TreeSHAP（`pred_contribs`） | XGBoost | `*_feature_importance.csv` |
| Integrated Gradients | MLP / CNN / Transformer | 同上 |
| **In-silico mutagenesis（ISM）** | CNN | 同上（`CNN_ISM` 列） |
| 位置/区域归因谱 | 全部 | `position_profile_by_model.csv`、`region_attribution.csv` |
| 候选序列模式（seqlet → cluster → consensus） | CNN IG/ISM | `motif_candidates.csv` |

**ISM 的定义（PPT 需明确区分两种实现，避免误导）**：
- **平台默认 `CNN_ISM`**：对每个（位点，通道）**单独翻转一个通道**后取 $|\Delta|$，再对样本取均值。
  算子为 $\Delta = f(\text{mutant}) - f(\text{WT})$ 的**绝对值**。
  注意：对 one-hot **序列**通道，单通道翻转会产生"该位点全 0"或"两个 1"的**分布外输入**，**不等价于碱基替换**；对二值环境通道则含义明确。
- **符号化替换 ISM（用于反事实方向）**：**真替换**（参照通道置 0 且目标通道置 1）并**保留符号**。
  本项目的第 18 位 C→A 方向性结论来自这一实现，与 `CNN_ISM` 不是同一个量。

**④ 可以解释什么**

✓ 模型关注哪些位置、哪些 feature 贡献预测
✓ 序列中潜在的 motif / position-specific 规律
✓ 模型之间的归因分歧（本项目如实保留，不平均掉）

**⑤ 不能解释什么**

✗ 生物真实因果
✗ 实验一定产生相同效果
✗ feature 一定具有机制作用
✗ **attribution ≠ biological experiment**（必须在页面上明写）

---

### Dimension 3：Statistical Evidence（统计证据）

**① 回答什么科学问题**
> 观察到的规律是否可能只是随机现象？

用于过滤模型解释中的偶然发现。

**② 使用什么数学指标**

- **置换检验（Permutation / sign-flip）**
  思想：破坏真实关系（随机翻转符号）→ 重新计算效果 → 与真实结果比较
  零假设 $H_0$：$(x - \text{null})$ 关于 0 对称 ⇒ 符号可交换；统计量 = 均值
  $$p = \frac{\#\{\text{perm} \ge \text{obs}\} + 1}{B + 1}$$
  回答："当前效果是否超过随机情况下可能出现的范围？"
- **FDR（Benjamini–Hochberg）**
  $$\text{FDR} = \mathbb{E}\left[\frac{\text{False Discovery}}{\text{Total Discovery}}\right]$$
  解释：在所有被判定为显著的因素中，**预计假阳性的比例**。
- **ANOVA（Type-II 边际平方和 F 检验）**
  $$\text{Total Variance} = \text{Factor} + \text{Interaction} + \text{Error}$$
  回答："某个因素是否解释整体结果变化？"；效应量用 **partial η²**。
- 辅助：配对 bootstrap 置信区间、cell-line 一致性标签。

**③ 使用哪些分析工具（本项目实际参数，全部为已接线实现）**

| 工具 | 关键参数（本项目实际值） | 产物 |
|---|---|---|
| **逐样本配对 bootstrap（ΔR²）** | **B = 2000**，**seed = 2024**，**α = 0.05**，百分位区间；逐样本配对 | `bootstrap_results.csv`（**7 954** 行 = R² 2 633 + MAE 2 633 + RMSE 2 633 + 55 unavailable） |
| **Model-Level Bootstrap**（重采样单位 = **7 个模型配置**） | B = 2000，seed 2024；模型等权 | `factor_level_ci.csv` |
| **配对指标 bootstrap（向量化）** | `n_iterations = 2000`，multinomial 计数矩阵 | 供上述使用 |
| **置换检验（sign-flip）** | **B = 1000**，**seed = 2024**；单侧 greater / less 或双侧；样本数 < 3 → 不可用；`p=(count+1)/(B+1)` | `permutation_results.csv`（**3 444** 行 = edge 2 688 + interaction 504 + main_effect 252） |
| **BH-FDR** | 按 `family_key` 分族校正；`min_family_size = 2`；实测 **189** 个族 | `FDR` / `fdr_family` 列 |
| **Factorial ANOVA（Type-II）** | `min_observations=32`、`min_residual_df=5`、`include_interactions=True`、`ci_iterations=400`；响应 = 留出 R²；因子 = 4 个二水平环境因子；**区组因子 = model / cell_line / split_type** | `anova_results.csv`（**94** 行，38 ok / 56 unavailable；blocked_factorial 10 + per_group_additive 84）。**注意：该表无 FDR 列（有意决策）** |
| **Effect size 定义** | `ΔR² = R²(S∪{e}) − R²(S)`；`delta_pair = 扩展 − 基线`；交互 `I(a,b) = Δ(a\|S₀∪{b}) − Δ(a\|S₀)`；ANOVA 用 `partial_eta_squared` | 同上 |
| **Cell-line consistency（4 标签）** | `min_cell_lines=2`、`consistent_ratio=0.75`、`conflicting_ratio=0.25`、`heterogeneity_ratio=2.0`、`ci_overlap_relaxes=True` | `cellline_effects.csv`（**84** 行：Uncertain 38 / Context-conflicting 24 / Context-dependent 20 / Context-consistent 2） |
| **Motif enrichment** | **Fisher 精确检验 + BH-FDR**（单一 `motif_enrichment` 族）；foreground = 效率上三分位（`quantile=0.67`）；背景 = 全部可用序列；`min_carriers=5`；`enrichment_fdr=0.05` | `motif_enrichment.csv`（**656** 候选，**65** 个 FDR<0.05） |
| **训练侧线性推断** | 系数 SE / t / p，BH-FDR within 单次实验的特征集 | `linear_*_weights.csv` |
| **描述性审计统计** | 位置 18 ISM 审计：**mean ± 1.96·SE**；符号化 ISM：**B = 10 000, seed 42** | `results/tables/paper/position18_*` |

**FDR 族划分（必须分族，绝不混用）**

| family 前缀 | 细分维度 | 实测族数 |
|---|---|---|
| `environment_edge\|…` | `<split>\|<cell>\|<model>` | — |
| `environment_main\|…` | 同上 | — |
| `environment_interaction\|…` | 同上 | — |
| `environment_anova` / `environment_anova_group` | 全局 / 分组 | — |
| `motif_enrichment` | 单一族 | 1 |
| **合计** | | **189** |

**不做多重校正的（有意决策，PPT 需注明）**：`anova_results.csv`（无 FDR 列）、bootstrap CI、位置 18 的两个审计脚本（明确声明样本量不足，只报描述统计与排名）。

**禁止**：SNR / SHAP / IG / ISM / attention 的**原始值**进入任何 p 值或 FDR。

**Permutation 与 ANOVA 的关系（PPT 需单独一页强调）**

- **Permutation 偏向 local evidence**：某个具体因素加入后**是否产生可靠增益**（逐样本、条件性）
- **ANOVA 偏向 global variance explanation**：因素在整个析因设计中的**贡献**
- 二者**不是替代关系而是互补**：
  $$\text{Specific Evidence} + \text{Global Effect}$$
- 因此"ANOVA 未检出显著主效应"与"某因子在某背景下有统计证据"**并不矛盾**，不可互相引用为反例。

**④ 可以解释什么**

✓ 发现是否超过随机
✓ 是否具有统计支持
✓ 多重比较风险是否被控制

**⑤ 不能解释什么**

✗ 生物机制
✗ 效应一定很大（本项目环境因子全部未过 effect 门即为实例）
✗ 因果关系

---

### Dimension 4：Robustness & Generalization（稳定性与泛化）

**① 回答什么科学问题**
> 发现的规律是否依赖某一次训练、某一个模型、某一个数据集？

**② 使用什么数学指标**

- **Bootstrap CI**：效应不确定性。**CI 跨 0 ⇒ 效应方向不稳定。**
  本项目使用 **cross-model bootstrap**，重采样单位是**不同模型**（不是单条 guide），
  因此该区间刻画的是"不同模型归纳偏置之间的一致性（cross-model robustness）"，
  **不是 guide 总体的抽样不确定性**（7 个模型共享同一份数据，不构成独立生物学重复）。
- **Cross-model concordance（方向一致率）**
  $$\text{Concordance} = \frac{\#\{\text{同向模型}\}}{\#\{\text{有效模型}\}}$$
- **覆盖度（coverage）**：与模型等权均值同号的模型数
- **独立数据集验证**：把同一流程搬到外部数据集，检验结论能否迁移

**③ 使用哪些分析工具（本项目实际参数）**

| 工具 | 本项目实际值 | 结论 |
|---|---|---|
| Model-Level Bootstrap CI（n=7 模型） | B=2000, seed 2024；`min_bootstrap_iterations=200` | 四个环境因子区间**全部跨 0** |
| 逐样本配对 bootstrap CI（边级） | B=2000, seed 2024 | 原始 2 633 条 R² CI 中 **805** 条不跨 0；去重后的保守口径为 **1 978** 条边、**640** 条不跨 0（CTCF 163/496、DNase 155/492、H3K4me3 168/494、RRBS 154/496） |
| Cell-line consistency | 4 标签（阈值见 D3） | Uncertain 38 / Conflicting 24 / Dependent 20 / Consistent 2 → 环境结论**不具跨细胞系稳定性** |
| **独立数据集验证** | 3 个数据集同一流程 | DeepCRISPR 弱正 / Hiranniramol **复现成功** / Labuhn **复现失败** |
| **独立外部模型验证** | CRISPRon，8 条预登记实例 | 方向一致性 **7/8**（r=0.629, ρ=0.476） |
| **无位置预设的饱和突变** | 552 条替换记录 | 第 18 位排名 **1/21** |
| 证据等级（Evidence Tier） | 门槛见下 | 环境 4/4 **Inconclusive**；motif 465 Tier 3 + 191 Inconclusive；**无 Tier 1 / Tier 2** |

**Evidence Tier 的权威判定规则（本项目唯一权威实现）**

| 门槛 | 值 | 含义 |
|---|---|---|
| `min_coverage` | **2** | 与模型等权均值同号的模型数 ≥ 2 |
| `direction_concordance` | **0.80** | 多数方向占比（仅 Tier 1 要求） |
| `ci_crosses_zero_forces_inconclusive` | **True** | 跨模型 CI 跨 0 → 直接 Inconclusive |
| `min_bootstrap_iterations` | **200** | 迭代数不足的 CI 不参与判定（不伪造 CI） |
| `min_absolute_delta_r2`（**effect 门**） | **0.01** | 最小**绝对**预测增益；**不是显著性阈值** |
| `statistical_gate_can_promote` | **False** | **统计证据不能单独把因子提升为 Tier 1** |
| `effect_gate_mode` | `model_mean` | effect 门的统计单位 = 模型配置（等权平均），不按样本量加权 |
| 发散阈值 | `\|Δ\| ≥ 10` | 数值不稳定行剔除，不进证据矩阵 |

**五档证据等级**：`Tier 1 Strong convergent` / `Tier 2 Moderate convergent` / `Tier 3 Model-specific (exploratory)` / `Inconclusive` / `No current evidence`

> PPT 必须强调：**Evidence Tier 是对已有计算证据的收敛性/覆盖度/稳健性的综合评级，不是生物学效应强度、不是效应量排名、不是显著性刻度、不是因果结论。**
> 在增量效应很小（|ΔR²| < 0.01）时，高等级仅表示多个模型对该小效应的判断一致。

**④ 可以解释什么**

✓ 规律是否稳定、是否依赖单一模型
✓ 是否具有一定泛化能力（**本项目在此给出的是负向答案**）

**⑤ 不能解释什么**

✗ 已经证明生物机制
✗ 直接替代实验验证
✗ **跨数据集泛化**：本项目实测结论是"序列可预测性不可移植"

---

### 四维度闭环（PPT 结尾必须展示）

```
                 Prediction
                     │
                     ▼
          Model learns pattern
                     │
                     ▼
                Attribution
                     │
                     ▼
      What features influence model?
                     │
                     ▼
           Statistical Evidence
                     │
                     ▼
        Is this signal beyond chance?
                     │
                     ▼
          Robustness Validation
                     │
                     ▼
       Is this discovery reproducible?
                     │
                     ▼
           Biological Hypothesis
                     │
                     ▼
   （下一级：Experiment —— 本研究未做）
```

**必须强调**：该平台不是寻找"最高准确率模型"，而是建立

$$
\text{Prediction} \rightarrow \text{Interpretation} \rightarrow \text{Evidence} \rightarrow \text{Discovery}
$$

的科学发现流程。所有结果必须明确区分：**prediction / association / statistical evidence / biological validation**。避免过度解释。

---

## 5. 视觉规范

### 5.1 每页结构

- **一个核心观点**（页面主标题，读者 3 秒内能读懂）
- **一个主要图**（占版面 ≥ 50%）
- **少量文字**（≤ 5 行要点；正文用短句，不用完整段落）

### 5.2 推荐图形类型

| 用途 | 推荐图 |
|---|---|
| 平台流程 | 横向流程条（Raw data → QC → AI → Evidence → Discovery），圆角卡片 + 箭头 |
| 数据处理 | 序列 → 张量热图（23×8）的映射示意 |
| 模型对比 | 分组条形图 + 零参考线；排序后的点阵图（dot plot） |
| 位置归因 | **23 位点热图**（模型 × 位置）；谱线图（每模型一条线） |
| 环境因子证据 | **Forest plot**（效应量 + 95% CI + 门槛竖线） |
| 统计证据总览 | **Evidence matrix**（effect size × confidence × FDR × robustness 的四格矩阵或气泡图） |
| 复现性 | 三数据集并列条形图 + 零分布阴影带 |
| 外部验证 | 配对斜率图 + 一致性散点图（标注分歧点） |
| 反事实扰动 | 位置条形图（高亮第 18 位）+ 排名分布 |
| 单碱基替换全景 | **Volcano plot** 或 **Δ 热图**（位置 × 替换） |
| 证据分层 | 阶梯/漏斗图（模型解释 → 统计证据 → 实验验证） |
| 假设收敛 | 收敛图（三条独立证据线汇聚到第 18 位） |

### 5.3 配色与排版

- 主色：深蓝/靛青（科学感）+ 灰阶（结构）；**仅用一个强调色**标注"显著/分歧/未检出"
- 阳性结果、阴性结果、未检出结果使用**一致的语义配色**（例如绿=支持、灰=未检出、红=方向冲突），并在全篇保持一致
- 字体：无衬线；数字使用等宽或半等宽字体以对齐
- 每页留白 ≥ 25%

---

## 6. 必须避免的内容

| 禁止 | 原因 |
|---|---|
| **代码截图** | 受众是导师/评审，不是开发者 |
| **文件目录树、命令行** | 工程细节，与科学逻辑无关 |
| **参数列表堆砌**（把第 2/4 节所有参数直接贴到页面上） | 参数是"可核查的底账"，不是幻灯片内容；应放在**附录页**或**备份页** |
| **大段文字** | 违反"一页一观点" |
| **只展示 accuracy 而回避阴性结果** | 本项目最重要的发现之一是**复现失败**，隐去即失真 |
| **把 attribution 写成"机制"或"证明"** | attribution 只说明模型依赖强度 |
| **把 ISM / 外部模型一致写成"实验验证"** | 它们是模型内部反事实（E4），不是湿实验（E5） |
| **把 Evidence Tier 写成"显著性强弱排名"** | 它是收敛性/覆盖度评级 |
| **把环境因子的"未检出"写成"无作用"** | 只能说"在本设定下未检出" |
| **暗示三个数据集的效率是同一个物理量** | label semantics 不同（见 2.1） |
| **声称跨数据集泛化能力** | 实测结论是不可移植 |
| **使用"因果证明/实验效应/机制证明/C18A 导致效率下降"等措辞** | 违反证据分层纪律 |

---

## 7. 最终叙事路线（Narrative Arc）

PPT 应沿以下五幕推进，每幕结束时给出一句"结论句"：

**第 1 幕｜问题（Slide 1–2）**
编辑效率受多因素影响，但"哪些因素重要、是否稳定"未被可靠回答。
> 结论句：**预测不是终点，可复现的规律发现才是。**

**第 2 幕｜平台（Slide 3–6）**
数据 → QC → 特征 → 多模型，构成一条可追溯的证据生产链。
> 结论句：**模型不是答案，而是产生可解释证据的工具。**

**第 3 幕｜预测能力的边界（Slide 7–9）**
三个数据集给出三种结果：弱正 / 复现成功 / **复现失败**；跨细胞系迁移失败；环境通道未检出。
> 结论句：**序列可预测性是数据集依赖的，不可移植。**

**第 4 幕｜四维度证据体系 + 规律挖掘（Slide 10–18）**
Performance → Attribution → Statistical Evidence → Robustness。
位置归因指向 PAM 邻近窗口；独立外部模型确认第 18 位扰动方向；饱和突变把第 18 位排到首位；实测关联独立支持同向结论。
> 结论句：**第 18 位获得三层互相独立的支持，但仍然只是假设。**

**第 5 幕｜边界与未来（Slide 19–21）**
解释能力的边界；E5（实验）完全空缺；未来用扩展数据、基础模型与湿实验闭环。
> 结论句：**从 Prediction 到 Discovery，缺的最后一环是实验。**

---

## 8. Gemini 输出格式要求

请 Gemini 输出：

1. **一份完整的幻灯片清单**（页码 / 标题 / 核心观点 / 要点 ≤ 5 条 / 建议图形 / 图中需要标注的具体数字）
2. 每页的**演讲者备注**（2–4 句，说明这一页要讲清楚的逻辑）
3. **图表规格说明**：每张图建议用什么类型、横纵轴是什么、需要标注哪些数值
4. **附录页建议**：把第 2 节与第 4 节的完整参数表放入"备份页/附录"，正文只引用必要数字

**不要**：
- 不要生成真实图片文件；
- 不要编造本文件未给出的数字；
- 不要删减阴性结果（Labuhn 复现失败、环境全 Inconclusive、无 Tier 1/2、无 E5 证据）。

---

## 9. 术语与措辞红线

| 允许写 | 禁止写 |
|---|---|
| 外部模型验证 / 独立第三方模型 | 实验验证、已被证实 |
| 模型内部反事实 / in-silico 突变 | 真实效应、实验效应 |
| 方向一致性 / 跨模型一致性 | 因果证明 |
| 与均值基线不可区分 | 模型无效 |
| **未检出（not detected）** | 无作用（no effect） |
| 观测性关联 | 因果关联 |
| 候选假设 / 待实验验证 | 生物学机制 |
| 数据集依赖 / 不可移植 | 通用预测器 |
| 归因强度（模型依赖强度） | 归因显著性 |

---

## 10. 附录：可引用的图与表清单

**已有图（可直接引用或重绘）**

| 文件 | 内容 |
|---|---|
| `docs/paper/figures/fig1_workflow.pdf` | 平台科学发现流程图 |
| `docs/paper/figures/fig2_prediction.pdf` | 三划分下的预测性能（含 LOCO 塌陷） |
| `docs/paper/figures/fig3_environment.pdf` | 环境因子增量效应与统计证据 |
| `docs/paper/figures/fig4_sequence_attribution.pdf` | 跨模型序列归因谱 |
| `docs/paper/figures/fig5_kernel.pdf` | CNN 感受野消融 |
| `docs/paper/figures/fig6_cellline.pdf` | 细胞背景异质性 |
| `docs/paper/figures/fig7_evidence.pdf` | 证据整合（环境因子 forest 图） |
| `docs/paper/figures/fig_ext_a…d_*.png` | 外部模型验证四联图（配对变化 / 一致性散点 / Δ 热图 / Δ 分布） |
| `docs/paper/figures/position18_*.png` | 第 18 位碱基效应与符号化替换 |

**已有表（建议放入附录页）**

| 文件 | 内容 |
|---|---|
| `docs/paper/tables/tab0_data_quality.tex` | 数据质量与泄漏审计 |
| `docs/paper/tables/tab1_dataset.tex` | 三数据集组成 |
| `docs/paper/tables/tab2_prediction.tex` | 逐配置预测性能 |
| `docs/paper/tables/tab3_environment.tex` | 环境因子完整统计（含 FWER 上界、ANOVA） |
| `docs/paper/tables/tab4_kernel.tex` | CNN 核配对消融 |
| `docs/paper/tables/tab5_motifs.tex` | 候选序列模式 |
| `docs/paper/tables/tab6_candidates.tex` | 候选假设优先级 |
| `docs/paper/tables/tab7_replication.tex` | **跨数据集复现主表** |
| `docs/paper/tables/tab8_external_validation.tex` | **CRISPRon 外部验证逐样本** |
| `docs/paper/tables/tab9_counterfactual.tex` | **饱和突变 21 位点** |
| `docs/paper/tables/tab10_evidence_layers.tex` | **六层证据 E1–E6 定义** |
| `docs/paper/tables/tab11_attribution_position.tex` | **位置层级归因权威值** |
| `docs/paper/supplementary/supplementary.tex` | 补充材料（含 ANOVA/bootstrap/permutation 明细引用） |

**统计参数的唯一权威来源**（如需核对，指向这些文件而非本 PPT）

- `analysis/config.py` —— 全部阈值集中于此（bootstrap / permutation / FDR / ANOVA / evidence / cell-line / motif / QC）
- `analysis/stats/{bootstrap,hypothesis_tests,multiple_testing,effect_size}.py` —— 统计实现
- `analysis/evidence/integration.py::classify_evidence_tier` —— **Evidence Tier 唯一权威**
- `results/batches/ultimate_run/summary/tables/` —— 统计产物（`bootstrap_results.csv` 7 954 行、`permutation_results.csv` 3 444 行、`anova_results.csv` 94 行、`evidence_matrix.csv` 660 行、`cellline_effects.csv` 84 行、`motif_enrichment.csv` 656 行）
- `docs/science/statistics_and_parameters_zh.md` —— 统计学工具总表（**注意：该文档部分数字来自旧批次，引用前请以 `results/batches/ultimate_run/` 为准**）

---

## 11. 附录 A：完整统计参数清单（取自 `analysis/config.py`，逐字段无遗漏）

> 本附录由 `AnalysisConfig()` 实例直接导出，保证与代码一致。
> **这是 PPT 的备份页素材**：正文只引用必要数字，完整参数放在附录/答疑页。

### 11.1 全局随机性与迭代参数

| 参数 | 值 | 含义 |
|---|---|---|
| `bootstrap_iterations` | **2000** | — |
| `bootstrap_seed` | **2024** | — |
| `bootstrap_alpha` | **0.05** | — |
| `permutation_iterations` | **1000** | — |
| `random_seed` | **42** | — |

### 11.2 `AttributionRuleConfig`

归因稳健性阈值。**SNR 仅作 robustness/attribution strength，不是统计显著**；不参与 Evidence Tier。

| 参数 | 值 |
|---|---|
| `snr_threshold` | `2.5` |
| `snr_moderate` | `1.8` |
| `snr_weak` | `1.2` |
| `min_effect_size` | `0.005` |
| `method` | `mean_over_std` |

### 11.3 `StatisticalRuleConfig`

统计证据**分档**阈值。仅用于 Importance–ΔR² 资产的 evidence_strength 标签与线性回归训练侧 FDR 分档；**不参与 Evidence Tier**（Tier 只用 fdr_weak 作为统计门）。

| 参数 | 值 |
|---|---|
| `fdr_strong` | `0.001` |
| `fdr_moderate` | `0.01` |
| `fdr_weak` | `0.05` |

### 11.4 `ConsensusRuleConfig`

跨模型 / 跨 cell-line 一致性规则（Evidence Tier 的覆盖度与方向一致率门槛）。

| 参数 | 值 |
|---|---|
| `min_coverage` | `2` |
| `direction_concordance` | `0.8` |
| `cellline_consistent_ratio` | `0.75` |
| `unstable_effect_threshold` | `10.0` |

### 11.5 `CelllineConsistencyConfig`

cell-line context 判定阈值（方向 + 幅度异质性 + CI 重叠）。

| 参数 | 值 |
|---|---|
| `min_cell_lines` | `2` |
| `consistent_ratio` | `0.75` |
| `conflicting_ratio` | `0.25` |
| `heterogeneity_ratio` | `2.0` |
| `ci_overlap_relaxes` | `True` |

### 11.6 `EvidenceRuleConfig`

**Evidence Tier 的权威阈值**（唯一来源，由 evidence/integration.py 消费）。

| 参数 | 值 |
|---|---|
| `min_absolute_delta_r2` | `0.01` |
| `ci_crosses_zero_forces_inconclusive` | `True` |
| `min_bootstrap_iterations` | `200` |
| `statistical_gate_can_promote` | `False` |
| `effect_gate_mode` | `model_mean` |

### 11.7 `AnovaRuleConfig`

factorial ANOVA 运行条件与输出定义（数据不足 → unavailable，绝不伪造）。

| 参数 | 值 |
|---|---|
| `enabled_default` | `True` |
| `min_observations` | `32` |
| `min_residual_df` | `5` |
| `include_interactions` | `True` |
| `run_per_group` | `True` |
| `effect_size_metric` | `partial_eta_squared` |
| `ci_iterations` | `400` |
| `block_factors` | `('model', 'cell_line', 'split_type')` |

### 11.8 `FdrFamilyConfig`

multiple-testing family 定义：不同科学问题绝不并入同一 FDR 族。

| 参数 | 值 |
|---|---|
| `enabled_families` | `('environment_permutation_edge', 'environment_permutation_main', 'environment_permutation_interaction', 'environment_anova', 'environment_anova_group', 'motif_enrichment')` |
| `min_family_size` | `2` |

### 11.9 `MotifDiscoveryConfig`

序列 motif discovery 全部阈值。输入边界：当前批次 attribution 为**无符号** magnitude，方向由 carrier-vs-background 实测效率对比给出。

| 参数 | 值 |
|---|---|
| `data_root` | `data/processed/DeepCRISPR` |
| `primary_methods` | `('cnn_ism', 'cnn_ig')` |
| `supporting_methods` | `('transformer_attention',)` |
| `transformer_ig_method` | `transformer_ig` |
| `contexts` | `('sequence', 'all')` |
| `model_families` | `('cnn',)` |
| `max_length` | `12` |
| `attribution_quantile` | `0.9` |
| `continuity_quantile` | `0.75` |
| `continuity_min_positions` | `2` |
| `max_seqlets_per_sample` | `2` |
| `min_seqlet_score` | `0.0` |
| `similarity_threshold` | `0.9` |
| `merge_similarity` | `0.95` |
| `max_ambiguous_fraction` | `0.34` |
| `degenerate_fraction` | `0.25` |
| `min_length` | `4` |
| `min_seqlet_support` | `30` |
| `min_sample_support` | `20` |
| `max_motifs_per_context` | `8` |
| `max_exploratory_per_context` | `3` |
| `min_cellline_support` | `2` |
| `stability_similarity` | `0.8` |
| `region_ranges` | `()` |
| `preferred_position_bins` | `5` |
| `enrichment_enabled_default` | `False` |
| `enrichment_foreground_quantile` | `0.67` |
| `enrichment_background` | `all_eligible_sequences` |
| `enrichment_min_carriers` | `5` |
| `enrichment_fdr` | `0.05` |
| `evidence_strong_min_models` | `2` |
| `evidence_strong_fdr` | `0.05` |

### 11.10 `QCConfig`

QC 门禁（detection 层，不负责用户科学决策）。

| 参数 | 值 |
|---|---|
| `environment_missing_rate_limit` | `0.3` |
| `strict_complete_gate` | `70.0` |
| `ambiguous_detection_only` | `True` |

### 11.11 附录 B：不在 `analysis/config.py` 中的统计参数（已逐项核实）

| 用途 | 参数 | 实测值 | 代码位置 |
|---|---|---|---|
| 外部验证·位置 18 有符号替换 ISM 的 CI | 百分位 bootstrap **B = 10 000**，**seed = 42** | — | `analysis/reporting/paper_analysis/position18_signed_substitution_ism.py` |
| 外部验证·位置 18 ISM 描述性审计 | **mean ± 1.96·SE** | — | `analysis/reporting/paper_analysis/position18_ism_audit.py` |
| **与官方划分无关的独立复核** | 全数据 **5 折 CV**，`Ridge(alpha=1.0)`，标准化后；零分布 = **200 次标签置换**，`random_state=0` | — | `analysis/paper_numbers.py` |
| QC·编辑效率分布 | **Gaussian KDE**，`GridSearchCV` + **5 折 CV**（KernelDensity 负对数似然） | 子抽样上限 **2000** | `analysis/data_QC.py` |
| 数值发散隔离 | \|metric\| > **10** → 剔除（不进统计与证据矩阵） | 实测 **20** 个 run（测试集口径） | `analysis/config.py`、`analysis/collect_results.py` |
| 异常检测（实验级） | 规则：加入表观环境后 `ΔR²` 与 `ΔRMSE` **同向变化** ⇒ 指标矛盾，标记可疑 | — | `analysis/anomaly_treatment.py` |
| 异常检测（数据级） | 规则：线性回归 \|Weight\| > **10.0**（病态矩阵/数值爆炸） | — | 同上 |
| 划分摘要 | `split_digest` = train/valid/test 序列集合与样本数的 **SHA-256 前 16 位** | 1 344 run 逐条复核 **0 处不一致** | `core/data/splitting/cell_line_division.py` |
| 身份类定义 | `min(sequence, revcomp(sequence))`；运行期计算重叠，非零即抛错中止 | 1 344/1 344 重叠 = **0** | 同上 |
| 指纹 | `data_fingerprint` / `code_fingerprint` / `env_fingerprint` / `env_stack_id` | 各只有 **1** 种取值 | 每个 run 的 `*_info.txt` |
| 置换检验的可用下限 | 有效样本数 **< 3** ⇒ 返回不可用（不伪造 p） | 66 / 3 444 行不可用 | `analysis/stats/hypothesis_tests.py` |
| bootstrap 的可用下限 | 样本数不等 / 预测文件缺失 ⇒ `unavailable` | 55 / 7 954 行不可用 | `analysis/stats/tasks.py` |
| 环境组合 lattice | 节点 **1 008**，边 **2 671**（16 节点 factorial lattice 的全部单因素边） | — | `environment_nodes.csv` / `environment_edges.csv` |

> **重要澄清（避免在 PPT 中出错）**：本项目**未使用** IsolationForest 或任何机器学习离群点检测。
> 异常检测是**两条确定性规则**（指标矛盾 + 数值爆炸）。某些旧文档中的 "IsolationForest contamination=0.01" 说法与当前代码不符。

### 11.12 附录 C：本项目**明确不做**的统计处理（PPT 需诚实标注）

| 未做 | 说明 |
|---|---|
| ANOVA 的 FDR 校正 | `anova_results.csv` **无 FDR 列**（有意决策：ANOVA 回答 global 问题，不做族内校正） |
| bootstrap CI 的多重校正 | CI 本身不做 FDR |
| 位置 18 的显著性检验 | 样本量不足（每条序列在该位点只有 1 个观测），**只报描述统计与排名** |
| 环境因子的**因果**检验 | 观察性数据，无干预实验 |
| 效应量的**样本加权** | 全项目跨实验聚合**一律等权**；**无任何按样本数 n 的加权平均** |
| SNR / SHAP / IG / ISM / attention 的 p 值 | **禁止**这些原始值进入 p 值或 FDR |
| 湿实验验证（E5） | **完全空缺** —— 这是全篇最重要的边界 |
