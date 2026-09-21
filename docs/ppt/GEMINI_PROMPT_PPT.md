# Gemini Prompt for CRISPR AI Discovery Platform Presentation

> **本文件是给 Gemini 的"生成 PPT 的提示词"，不是 PPT 本身。**
> 请把本文件整段作为 prompt 交给 Gemini。
> 本文件中所有数字均来自本项目当前权威产物，**Gemini 不得改写、不得补造**。

---

## 0. 使用说明与硬性约束

### 0.1 三条不可违反的规则

1. **唯一事实来源**：第 1 节「硬性事实清单」与正文第四部分「统计学工具与参数」。
   本文件未给出的数字，Gemini **不得自行生成**；宁可留空，也不要编。
2. **各部分独立**：全篇分为 **6 个大部分**。每部分**各说各的**，不互相引用、
   不互相依赖、不出现"如前所述"式的跨部分回指。听众从任意一个部分开始听都应能听懂。
3. **页数纪律**：
   - 每个**大部分**开头必须有 **1 张独立的章节封面页**（只有大标题，无正文）；
   - 每个**小部分**尽量只用 **1 张幻灯片**；
   - 小部分的标题放在页面**左上角**（不是居中、不是页眉横条）。

### 0.2 全篇结构（6 个大部分）

```text
封面
├─ 第一部分  背景
├─ 第二部分  项目流程
├─ 第三部分  五个模型的负责方向
├─ 第四部分  统计学工具与参数：数学原理与维度归类
├─ 第五部分  工具发现与验证手段
└─ 第六部分  项目发展
结尾页
```

### 0.3 受众与语言

- 受众：导师、评审专家、科研交流同行；
- 中文正文 + 英文术语（首次出现时中英并列）；
- 不要出现代码、命令行、目录树、参数堆砌。

---

## 1. 硬性事实清单（Gemini 只能使用这些数字）

> 本节是全篇的**事实底座**，只是给 Gemini 的素材库。**不要**把它整页展示在 PPT 上。

### 2.1 数据集（三个独立数据集）

| 数据集 | 样本数 | 细胞系 | 环境通道 | 标签语义 | 来源 |
|---|---|---|---|---|---|
| **DeepCRISPR**（主数据集） | **16 749** | hct116 4 239 / hek293t 2 333 / hela 8 101 / hl60 2 076 | CTCF, Dnase, H3K4me3, RRBS（4 条） | 归一化编辑效率 [0,1] | Chuai et al. 2018, *Genome Biology* |
| **Hiranniramol** | **1 309** | 单细胞系 | 无 | `Edit Efficiency`（原 0–100 百分制） | Hiranniramol et al. 2020, *Bioinformatics* 36(9):2684–2689 |
| **Labuhn** | **417** | 单细胞系 | 无 | `KO_reporter_assay`（已是 [0,1]） | Labuhn et al. 2018, *NAR* 46(3):1375–1385 |

**必须强调**：三者 **label semantics 不同**，不可当作同一个物理量比较。

序列定义：**23 nt = 20 nt protospacer + 3 nt PAM（NGG）**，PAM 位于第 21–23 位，**已包含在模型输入中**。

### 2.2 实验矩阵

- **1 344 次受控实验** = 7 个模型配置 × 16 种环境组合 × 12 个（划分, 种子）设定
- 三种划分各 **448**：`single`（细胞内 70/15/15）、`all`（真实留一细胞系 LOCO）、`mixed`（跨细胞系 70/15/15，种子 42–45）
- 外部数据集各 **7** 次运行
- 身份类：`min(sequence, revcomp(sequence))` —— 同一 sgRNA 及其反向互补视为同一身份，**不跨 train/valid/test**
- 环境组合 lattice：节点 **1 008**，边 **2 671**

### 2.3 五个模型（7 个配置）

| # | 模型 | 配置数 | 负责方向 |
|---|---|---|---|
| 1 | **Linear Regression** | 1 | 线性主效应；系数带方向与统计推断（SE / t / p / BH-FDR） |
| 2 | **XGBoost** | 1 | 非线性与特征交互；原生 TreeSHAP 可分解预测 |
| 3 | **MLP** | 1 | 一般非线性组合 |
| 4 | **CNN（双通道 · 三格式）** | **3** | 位置特异的局部序列模式 |
| 5 | **Transformer** | 1 | 跨位置长程依赖 |

> **CNN 的"双通道三格式"**：双通道 = **序列分支 + 环境分支**（两条分支各自卷积后融合）；
> 三格式 = 序列分支卷积核 **k=3 / 5 / 7** 三种感受野，各训练一次 → CNN 贡献 **3** 个配置。

### 2.4 核心结果（必须如实呈现，包括阴性结果）

**（1）跨数据集复现：序列可预测性是数据集依赖的**

| 数据集 | 测试 R² | 结论 |
|---|---|---|
| DeepCRISPR（`single` 7 配置中位） | **+0.067 … +0.120** | 弱正信号 |
| Hiranniramol | **+0.345 … +0.489**（Transformer 最高 R²=0.489, Pearson=0.709） | **复现成功** |
| Labuhn | **−0.725 … −0.050（7/7 全为负）** | **复现失败** |

**独立复核**（与官方划分无关的全数据 5 折交叉验证 + 200 次标签置换零分布）：
Hiranniramol CV R²=**+0.3886** vs 零分布 **−0.4668±0.0375**；Labuhn CV R²=**−0.1444** vs **−0.2869±0.0505**。

**Labuhn 失败机制**：标签标准差 0.2153（**不是低方差**）；6/7 配置的「预测标准差 / 标签标准差」仅 **0.03–0.37**（预测坍缩）；Linear 例外（0.93）但与真值不相关（r=0.165），故 R² 最低 −0.725。

**（2）跨细胞系泛化失败**：LOCO 下 7 个配置中位 R² 全部落在 **−0.027 至 +0.010**（与均值基线不可区分）；按留出系展开异质性极大（HEK293T 最低 −0.266）。

**（3）环境通道未检出增量预测价值**（4 个因子全部 Inconclusive）

| 因子 | 平均 ΔR² | 95% 区间 | effect 门（\|ΔR²\|≥0.01） | 组内最小边级 FDR | 区组 ANOVA p | 等级 |
|---|---|---|---|---|---|---|
| CTCF | +0.0003 | [−0.0035, +0.0038] | 未通过 | 0.0070 | 0.9892 | Inconclusive |
| DNase | +0.0013 | [−0.0013, +0.0043] | 未通过 | 0.0070 | 0.9996 | Inconclusive |
| H3K4me3 | −0.0007 | [−0.0033, +0.0018] | 未通过 | 0.0070 | 0.9753 | Inconclusive |
| RRBS | −0.0015 | [−0.0040, +0.0010] | 未通过 | 0.0070 | 0.9867 | Inconclusive |

效应量级 **3.2×10⁻⁴ – 1.5×10⁻³**，比门槛 0.01 低 **1–2 个数量级**；四区间全部跨 0。

**（4）多模型归因指向 PAM 邻近位置（必须分两个层级讲）**

- **位置层级（较强）**：逐上下文峰值落在 17–20 的比例 —— XGBoost **100.0%（64/64）**、CNN **96.9%（62/64）**、MLP **90.6%（58/64）**、Transformer **65.6%（42/64）**；**Linear 例外，仅 21.9%（14/64），峰值在第 1 位**
- **跨模型平均谱**：五模型（含 Linear）峰值是 **第 1 位（0.0864）**；**剔除 Linear 后峰值才是第 18 位（0.0878）**
- **区域层级（仅部分一致）**：只有 **2/5** 个模型类的最高区域是 PAM 邻近种子区（XGBoost 0.327、Transformer 0.325）；CNN（0.344）与 MLP（0.336）最高区域是种子核心区；Linear 最高区域是 PAM 远端区（0.416）
- 跨模型位置谱平均两两 Spearman = **0.34**，top-3 重叠率 **0.42**

**（5）外部平台验证**

8 条预登记 WT 序列（第 18 位为 C），仅替换第 18 位一个碱基（C→A）：
- 本文 7 模型与 CRISPRon 的扰动方向 **7/8 一致**（Pearson r=**0.629**，Spearman ρ=**0.476**，n=8）
- CRISPRon 侧 **7/8** 为负向，Δ 均值 **−12.43**，范围 −27.17 至 +9.16
- **唯一分歧样本 WT08 被保留在统计中，未剔除**

**（6）无位置预设的反事实扰动**

552 条单碱基替换记录（8 序列 × 23 位点 × 3 替换），48 条破坏 PAM 被排除，504 条计分：
**第 18 位平均 |Δ| = 12.86，排名 1/21**；第 18 位 C→A 平均 **−12.425**，其余位置平均仅 **+0.144**；逐序列 7/8 条排第 1。

**（7）观测性关联**

第 18 位 C 减 A 的**实测**平均效率差：HCT116 **+0.090**、HeLa **+0.092**、HL60 **+0.027**、**HEK293T −0.015（方向反转）**。

**（8）数据质量审计**

1 344/1 344 次运行的 train∩test 序列重叠与反向互补重叠**均为 0**；`split_digest` 逐条复核 **0 处不一致**；数据/代码/环境指纹各只有一种取值；960 个神经网络 run 全部在 GPU 上执行。数值发散 run（|R²|≥10）**20 次**（测试集口径），隔离而非删除。

---

## 2. 幻灯片逐页规划

> **统一版式规则（全篇适用）**
>
> | 类型 | 版式 |
> |---|---|
> | **章节封面页** | 整页留白 ≥ 70%；**只有大标题**（字号为正文 3–4 倍）+ 一条细装饰线；右下角 `Part N / 6`；无正文、无图 |
> | **内容页** | **小标题固定在左上角**（小字号、不加底色条）；一张主图占版面 ≥ 55%；下方 ≤ 4 行要点；结论句单独一行 |
> | **动画** | 全部使用**浮现（fade-in）**，顺序见 §3.2。**不使用**飞入、旋转、弹跳 |
> | **配色** | 深蓝/靛青 + 灰阶；**只用一个强调色**标注"显著 / 分歧 / 未检出" |
>
> **页数**：封面 1 + 章节封面 **6** + 内容页 **22** + 结尾 1 = **30 页**。
>
> **"≤ 4 行要点"的唯一例外**：第四部分的四个**维度页**（P4-2 … P4-5）按科学要求必须包含
> **① 回答什么科学问题 / ② 数学原理 / ③ 分析工具与参数 / ④ 能解释什么 / ⑤ 不能解释什么**
> 五个固定板块。因此这四页**不受"≤ 4 行"约束**，但要求：
> 公式必须**居中放大**呈现；②的公式与③的参数表各占半页；④与⑤用**对勾 / 叉号两栏对照**排版，
> 其中⑤用强调色。其余所有内容页仍须遵守 ≤ 4 行要点。

---

# 第一部分：背景

### P1-0｜章节封面页
- **版式**：整页大标题「**背景**」；右下角小字 `Part 1 / 6`
- **动画**：标题整体浮现

### P1-1｜为什么需要这个平台
- **左上角小标题**：`1.1 科学问题`
- **核心观点**：sgRNA 编辑效率受多因素影响，但"哪些因素真正重要"仍未被可靠回答
- **图形**：sgRNA–Cas9–DNA 复合物示意图，外围环绕六类候选影响因素 ——
  nucleotide sequence / PAM / position-dependent sequence preference /
  chromatin accessibility / transcriptional environment / epigenetic features
- **页面底部突出显示**（强调色，最后浮现）：
  > 哪些因素真正影响 CRISPR 编辑效率？这些影响是否具有跨模型、跨数据集的稳定性？
- **结论句**：**预测只是第一步，规律发现才是目标。**

---

# 第二部分：项目流程

### P2-0｜章节封面页
- **版式**：整页大标题「**项目流程**」；右下角 `Part 2 / 6`

### P2-1｜端到端流程（全页大图）
- **左上角小标题**：`2.1 从原始数据到证据链`
- **核心观点**：平台是一条可追溯的证据生产链，每一环都有明确职责
- **图形（全页横向流程条：9 个圆角卡片 + 箭头）**：

```text
Raw Data → Quality Control → Data Preprocessing → Feature Engineering
   → Multi-model Learning → Prediction Evaluation → Interpretability Analysis
   → Statistical Evidence → Biological Hypothesis
```

- **每个卡片下方一行职责**（浮现时逐个出现）：
  1. Raw Data — 实测 sgRNA 序列与效率
  2. Quality Control — 确保数据可靠、无泄漏
  3. Data Preprocessing — 序列与环境信息对齐
  4. Feature Engineering — 编码为模型输入张量
  5. Multi-model Learning — 多归纳偏置并行学习
  6. Prediction Evaluation — 留出集性能口径
  7. Interpretability Analysis — 模型归因与反事实
  8. Statistical Evidence — 效应量与置信度
  9. Biological Hypothesis — 可实验检验的候选

### P2-2｜数据与质量控制
- **左上角小标题**：`2.2 数据与质量控制`
- **核心观点**：数据质量决定后续统计解释的可信度
- **图形（六格图标矩阵，每格一个 QC 维度 + 状态勾）**：
  sequence validity / missing value / feature distribution / duplicate detection /
  **split integrity（身份类不跨划分）** / feature variance check
- **实测数字**（浮现）：
  - 1 344 / 1 344 run 的序列与反向互补重叠 = **0**
  - `split_digest` 逐条复核 **0 处不一致**
  - 数值发散 run **20 个**被隔离（不删除）
- **结论句**：**QC 不是"清洗数据"，而是保证结论可信。**

### P2-3｜特征工程与数据表示
- **左上角小标题**：`2.3 特征表示`
- **核心观点**：平台把"序列"与"细胞环境"编码进同一个张量
- **图形（左侧序列 → 右侧 (23, 8) 张量热图）**：

```text
raw sgRNA (23 nt)
   ↓ sequence encoding        → 23 × 4 one-hot（A/C/G/T）
   ↓ environment integration  → 23 × 4 逐位点二值（CTCF/Dnase/H3K4me3/RRBS）
   ↓ model input tensor       → (23, 8)，展平 184 维
```

- **标注**：`23 nt = 20 nt protospacer + 3 nt PAM（NGG，第 21–23 位，已包含在张量内）`
- **强调**（浮现）：采用 **config-driven feature schema**，新增环境变量只需改配置，不改代码
- **结论句**：**序列信息与环境信息在同一张量中对齐。**

---

# 第三部分：五个模型的负责方向

### P3-0｜章节封面页
- **版式**：整页大标题「**五个模型的负责方向**」；右下角 `Part 3 / 6`

### P3-1｜分工总览
- **左上角小标题**：`3.1 分工总览`
- **核心观点**：五个模型不是"选最优"，而是**用不同归纳偏置覆盖不同类型的规律**
- **图形（五列卡片 + 中央"可解释证据"汇聚箭头）**：

| 模型 | 学习目标 | 归因出口 |
|---|---|---|
| Linear | 线性主效应 | 系数（带方向 + SE / t / p / FDR） |
| XGBoost | 非线性与交互 | 原生 TreeSHAP |
| MLP | 一般非线性组合 | Integrated Gradients |
| CNN | 局部序列模式 | IG + ISM |
| Transformer | 长程依赖 | 注意力权重 |

- **结论句**：**模型不是最终答案，而是产生可解释证据的工具。**

### P3-2｜Linear Regression
- **左上角小标题**：`3.2 Linear Regression — 线性主效应`
- **核心观点**：给出**方向明确、可做统计推断**的基线
- **图形**：左 = 系数条形图（按 |系数| 排序，正负双色）；右 = 系数 ± SE 误差棒图
- **要点**（≤ 4 行）：
  - 目标函数：最小二乘解析解（Moore-Penrose 伪逆 + 偏置）
  - 哑变量陷阱防护：剔除全部 `*_T` 通道（每位点 1 个，共 23 个）→ **184 → 161 维**
  - 输出：系数、SE、t、p，以及族内 BH-FDR
- **结论句**：**唯一能直接给出"方向 + 统计量"的模型。**

### P3-3｜XGBoost
- **左上角小标题**：`3.3 XGBoost — 非线性与交互`
- **核心观点**：用树集成捕捉非线性与特征交互，并可用 TreeSHAP 精确分解单次预测
- **图形**：左 = 决策树分裂示意；右 = SHAP 蜂群图或特征贡献瀑布图
- **要点**：
  - 使用 XGBoost **原生 `pred_contribs`** 实现 TreeSHAP（不依赖第三方 `shap` 包）
  - 预测可分解为 $f(x) = \mathbb{E}[f(x)] + \sum_i \phi_i$
  - 网格参数：`n_estimators=300, max_depth=5, learning_rate=0.05`
- **结论句**：**回答"哪些 feature 推动预测上升或下降"。**

### P3-4｜MLP
- **左上角小标题**：`3.4 MLP — 一般非线性组合`
- **核心观点**：不预设结构，学习通用非线性映射
- **图形**：网络结构示意（128 → 64），叠加 IG 归因热图
- **要点**：
  - 归因方法：Integrated Gradients
  - 网格结构：hidden 128 → 64，dropout 0.2
- **结论句**：**作为"无结构先验"的对照模型。**

### P3-5｜CNN（双通道 · 三格式）
- **左上角小标题**：`3.5 CNN — 双通道三格式`
- **核心观点**：**两条分支**分别处理序列与环境，**三种感受野**覆盖不同宽度的局部模式
- **图形（双栏）**：
  - 左：双分支结构图 —— **序列分支**（1D 卷积）+ **环境分支**（1D 卷积）→ 融合 → 全连接输出
  - 右：三种卷积核感受野示意（k=3 / k=5 / k=7 覆盖的位点数不同）
- **要点**：
  - **双通道** = 序列分支 + 环境分支；**三格式** = 序列卷积核 **k = 3 / 5 / 7**，各训练一次 → CNN 贡献 **3** 个配置
  - 归因出口：IG + **ISM（in-silico mutagenesis）**
  - **ISM 算子**：默认 `CNN_ISM` 单通道翻转后取 \|Δ\|，对序列通道会产生分布外输入，**不等价于碱基替换**
  - 方向性结论用的是**真替换**实现（参照通道置 0 且目标通道置 1，保留符号）
- **结论句**：**感受野是模型超参数，不等于候选模式长度。**

### P3-6｜Transformer
- **左上角小标题**：`3.6 Transformer — 长程依赖`
- **核心观点**：用自注意力建模跨位置关系，给出位置间的关注强度
- **图形**：注意力矩阵热图（23 × 23）
- **要点**：
  - 结构：`d_model=64, nhead=4, layers=2`
  - 归因：注意力权重 —— **仅作支持性信息，不用于候选模式提取**
  - 注意力权重**不进入**任何 p 值或 FDR
- **结论句**：**提供跨位置关系的独立视角。**

---

# 第四部分：统计学工具与参数：数学原理与维度归类

### P4-0｜章节封面页
- **版式**：整页大标题「**统计学工具与参数**」；副标题小字「数学原理与维度归类」；右下角 `Part 4 / 6`

### P4-1｜四维度总览
- **左上角小标题**：`4.1 四维度框架`
- **核心观点**：四个维度回答**四类不同的科学问题**，不可互相替代
- **图形（四级阶梯图）**：

```text
Performance → Attribution → Statistical Evidence → Robustness
```

- **四个维度各自回答的一句话**（浮现逐条出现）：
  1. **Performance** — 模型是否学到了规律？
  2. **Attribution** — 模型认为哪些输入影响预测？
  3. **Statistical Evidence** — 观察到的规律是否可能只是随机？
  4. **Robustness** — 规律是否依赖某一次训练 / 某个模型 / 某个数据集？
- **纪律句**（强调色）：**低维度的结论不能升级为高维度的结论。**

### P4-2｜维度一 · 预测能力
- **左上角小标题**：`4.2 维度一 · 预测能力`
- **① 回答什么科学问题**：模型是否能够学习 sgRNA 与 editing efficiency 之间的关系？
  （**如果模型不能预测，后续解释没有意义**）
- **② 数学原理**（公式居中，逐个浮现）：

$$R^2 = 1 - \frac{SSE}{SST}$$
> 模型预测能解释标签方差的比例 —— "模型捕获了多少有效信息？"

$$RMSE = \sqrt{\frac{1}{n}\sum_{i}(y_i - \hat{y}_i)^2}$$
> 预测误差规模（与大误差同量纲）。

$$MAE = \frac{1}{n}\sum_i |y_i - \hat{y}_i|$$
> 平均预测偏差（对离群点更稳健）。

辅助指标：**Pearson r**（线性相关）、**Spearman ρ**（秩相关）。

- **③ 分析工具与参数**：留出测试集评估（早停并回滚至 best-epoch checkpoint）；
  7 个配置报告**中位数与四分位距**而非均值；三种划分对照；跨 3 个数据集；
  独立复核用 **5 折 CV（Ridge α=1.0）+ 200 次标签置换零分布**
- **④ 能解释**：模型是否有效学习；不同架构性能差异；不同划分下的泛化能力；**性能是否可跨数据集复现**
- **⑤ 不能解释**：哪个 feature 重要；某个生物因素是否导致效率变化；因果关系
- **图形**：三数据集并列条形图 + 零参考线 + 零分布阴影带

### P4-3｜维度二 · 模型归因
- **左上角小标题**：`4.3 维度二 · 模型归因`
- **① 回答什么科学问题**：模型认为哪些输入变量影响预测结果？（解释**模型内部决策依据**）
- **② 数学原理**：

**SHAP（Shapley value）** —— 把预测拆解为基线 + 各 feature 贡献：
$$f(x) = \mathbb{E}[f(x)] + \sum_i \phi_i$$

**Integrated Gradients（IG）** —— 沿 baseline→输入的路径累计梯度：
$$IG_i(x) = (x_i - x'_i)\int_0^1 \frac{\partial F\big(x' + \alpha(x - x')\big)}{\partial x_i}\, d\alpha$$

**ISM（in-silico mutagenesis）**：
$$\Delta = f(\text{mutant}) - f(\text{WT})$$

**SNR（归因稳健性）** —— 跨样本的效应均值与效应波动之比（**不是检验统计量**）：
- CNN：`mean(|Δŷ|) / std(|Δŷ|)`（标准形式）
- XGBoost / MLP / Transformer：`mean(|φ|) / std(φ)`（混合形式，分母为**有符号**归因的标准差）
- → 因此 **SNR 只在同一模型内部排序，不跨模型比较**

- **③ 分析工具**：线性系数（SE / t / p / BH-FDR）· 原生 TreeSHAP · Integrated Gradients ·
  CNN ISM · 注意力权重 · 位置与区域归因谱 · 候选序列模式（seqlet → cluster → consensus）
- **④ 能解释**：模型关注哪些位置与 feature；序列中的 position-specific 规律；
  模型间归因分歧（如实保留，不平均掉）
- **⑤ 不能解释**：生物真实因果；实验一定产生相同效果；feature 一定具有机制作用
- **页面必须明写**：**attribution ≠ biological experiment**
- **图形**：23 位点归因谱（每模型一条线）+ 区域汇总堆叠条形图

### P4-4｜维度三 · 统计证据
- **左上角小标题**：`4.4 维度三 · 统计证据`
- **① 回答什么科学问题**：观察到的规律是否可能只是随机现象？
- **② 数学原理**：

**置换检验（Permutation / sign-flip）**
$H_0$：$(x - \text{null})$ 关于 0 对称 ⇒ 符号可交换；统计量 = 均值
$$p = \frac{\#\{\text{perm} \ge \text{obs}\} + 1}{B + 1}$$

**FDR（Benjamini–Hochberg）**
$$\text{FDR} = \mathbb{E}\left[\frac{\text{False Discovery}}{\text{Total Discovery}}\right]$$

**ANOVA（Type-II 边际平方和 F 检验）**
$$\text{Total Variance} = \text{Factor} + \text{Interaction} + \text{Error}$$
效应量：**partial η²** $= SS_{\text{term}} / SS_{\text{total}}$

- **③ 分析工具与参数（本项目实际值）**：

| 工具 | 参数 | 产物规模 |
|---|---|---|
| 逐样本配对 bootstrap（ΔR²） | **B = 2000**，**seed = 2024**，**α = 0.05**，百分位区间 | `bootstrap_results.csv` **7 954** 行 |
| Model-Level Bootstrap（单位 = **7 个模型配置**） | B = 2000，seed 2024，模型等权 | `factor_level_ci.csv` |
| 置换检验（sign-flip） | **B = 1000**，**seed = 2024**；`p=(count+1)/(B+1)`；样本 < 3 → 不可用 | `permutation_results.csv` **3 444** 行 |
| BH-FDR | 按族校正，`min_family_size = 2`；实测 **189** 个族 | `FDR` / `fdr_family` 列 |
| Factorial ANOVA（Type-II） | `min_observations=32`、`min_residual_df=5`、`include_interactions=True`、`ci_iterations=400`；响应 = 留出 R²；**区组 = model / cell_line / split_type** | `anova_results.csv` **94** 行（38 ok / 56 unavailable）。**无 FDR 列（有意决策）** |
| Motif enrichment | **Fisher 精确检验 + BH-FDR**（单一族）；foreground = 效率上三分位（`quantile=0.67`）；`min_carriers=5` | 656 候选，**65** 个 FDR<0.05 |
| 效应量定义 | `ΔR² = R²(S∪{e}) − R²(S)`；`I(a,b) = Δ(a\|S₀∪{b}) − Δ(a\|S₀)` | — |

- **FDR 族必须分族，绝不混用**：`environment_edge` / `environment_main` / `environment_interaction` /
  `environment_anova` / `environment_anova_group` / `motif_enrichment`
- **不做多重校正的（有意决策）**：ANOVA 表、bootstrap CI、位置 18 的审计脚本
  （样本量不足，只报描述统计与排名）
- **禁止**：SNR / SHAP / IG / ISM / attention 的**原始值**进入任何 p 值或 FDR
- **④ 能解释**：发现是否超过随机；是否具有统计支持；多重比较风险是否被控制
- **⑤ 不能解释**：生物机制；效应一定很大；因果关系
- **图形**：forest plot（四因子效应 + 95% CI + 门槛竖线）

### P4-5｜维度四 · 稳定性与泛化
- **左上角小标题**：`4.5 维度四 · 稳定性与泛化`
- **① 回答什么科学问题**：发现的规律是否依赖某一次训练、某一个模型、某一个数据集？
- **② 数学原理**：

**Bootstrap CI** —— 效应不确定性；**CI 跨 0 ⇒ 效应方向不稳定**
> 本项目使用 **cross-model bootstrap**，重采样单位是**不同模型**（不是单条 guide）。
> 因此该区间刻画的是"不同模型归纳偏置之间的一致性（cross-model robustness）"，
> **不是 guide 总体的抽样不确定性**（7 个模型共享同一份数据，不构成独立生物学重复）。

**Cross-model concordance（方向一致率）**
$$\text{Concordance} = \frac{\#\{\text{同向模型}\}}{\#\{\text{有效模型}\}}$$

**覆盖度（coverage）** = 与模型等权均值同号的模型数

- **③ 分析工具与参数（本项目实际值）**：

| 门槛 | 值 | 含义 |
|---|---|---|
| `min_coverage` | **2** | 同号模型数 ≥ 2 |
| `direction_concordance` | **0.80** | 多数方向占比（仅 Tier 1 要求） |
| `ci_crosses_zero_forces_inconclusive` | **True** | 跨模型 CI 跨 0 → 直接 Inconclusive |
| `min_bootstrap_iterations` | **200** | 迭代数不足的 CI 不参与判定（不伪造 CI） |
| `min_absolute_delta_r2`（**effect 门**） | **0.01** | 最小**绝对**预测增益；**不是显著性阈值** |
| `statistical_gate_can_promote` | **False** | **统计证据不能单独把因子提升为 Tier 1** |
| `effect_gate_mode` | `model_mean` | effect 门单位 = 模型配置等权平均 |
| 发散阈值 | `\|Δ\| ≥ 10` | 数值不稳定行剔除，不进证据矩阵 |

**五档证据等级**：`Tier 1 Strong convergent` / `Tier 2 Moderate convergent` /
`Tier 3 Model-specific (exploratory)` / `Inconclusive` / `No current evidence`

**本项目实测**：环境 4/4 **Inconclusive**；motif 465 Tier 3 + 191 Inconclusive；**无 Tier 1 / Tier 2**。

**边级 CI 实测**：原始 2 633 条 R² CI 中 **805** 条不跨 0；保守去重口径
**1 978** 条边、**640** 条不跨 0（CTCF 163/496、DNase 155/492、H3K4me3 168/494、RRBS 154/496）。

**Cell-line consistency 四标签**（`min_cell_lines=2`、`consistent_ratio=0.75`、
`conflicting_ratio=0.25`、`heterogeneity_ratio=2.0`）：实测 Uncertain **38** /
Context-conflicting **24** / Context-dependent **20** / Context-consistent **2**。

- **④ 能解释**：规律是否稳定、是否依赖单一模型；是否具有一定泛化能力
- **⑤ 不能解释**：已证明生物机制；直接替代实验验证
- **必须强调**：**Evidence Tier 是收敛性/覆盖度/稳健性的综合评级，不是生物学效应强度、
  不是效应量排名、不是显著性刻度、不是因果结论。**
- **图形**：证据等级分布条形图 + cell-line 四标签饼图

### P4-6｜参数归类总表
- **左上角小标题**：`4.6 参数归类`
- **核心观点**：统计参数集中在**一个配置文件**，按科学问题归类，不散落代码
- **图形（六大类卡片，每类列 3–5 个代表参数）**：

| 归类 | 代表参数 |
|---|---|
| 迭代与随机性 | `bootstrap_iterations=2000`、`bootstrap_seed=2024`、`bootstrap_alpha=0.05`、`permutation_iterations=1000`、`random_seed=42` |
| 效应门与覆盖度 | `min_absolute_delta_r2=0.01`、`min_coverage=2`、`direction_concordance=0.80`、`min_bootstrap_iterations=200` |
| 细胞系一致性 | `min_cell_lines=2`、`consistent_ratio=0.75`、`conflicting_ratio=0.25`、`heterogeneity_ratio=2.0` |
| 析因 ANOVA | `min_observations=32`、`min_residual_df=5`、`ci_iterations=400`、`effect_size_metric=partial_eta_squared` |
| 多重检验族 | 6 个 family 前缀 + `min_family_size=2` |
| Motif discovery | `attribution_quantile=0.90`、`similarity_threshold=0.90`、`min_seqlet_support=30`、`enrichment_fdr=0.05` |
| 归因稳健性（**不参与 Tier**） | `snr_threshold=2.5`、`snr_moderate=1.8`、`snr_weak=1.2`、`min_effect_size=0.005` |

- **结论句**：**参数集中管理，是可核查的底账，不是幻灯片内容。**（完整 81 项见附录 A）

---

# 第五部分：工具发现与验证手段

### P5-0｜章节封面页
- **版式**：整页大标题「**工具发现与验证手段**」；副标题小字「两个独立数据集 + 一个独立预测平台」；右下角 `Part 5 / 6`

### P5-1｜为什么需要额外的发现与验证手段
- **左上角小标题**：`5.1 动机`
- **核心观点**：单一数据集上的结论无法自证；必须引入**外部**数据与**外部**系统
- **图形（三分支汇聚图）**：中心为"平台结论"，三条外伸箭头指向
  ① 独立数据集 A、② 独立数据集 B、③ 独立预测平台
- **三个问题**（浮现逐条）：
  1. 换成**另一个数据集**，序列信号还在吗？
  2. 换成**另一个细胞体系**，信号还在吗？
  3. 换成**别人训练的模型**，它会作同样的判断吗？

### P5-2｜手段一 · 两个独立数据集
- **左上角小标题**：`5.2 独立数据集复现`
- **核心观点**：同一套流程、同一批模型、同一评估脚本，搬到两个来源与规模都不同的数据集上
- **图形（三列对比 + 零参考线）**：

| 数据集 | 样本数 | 细胞系 | 环境通道 | 测试 R² | 结论 |
|---|---|---|---|---|---|
| DeepCRISPR | 16 749 | 4 | 4 条 | **+0.067 … +0.120** | 弱正信号 |
| **Hiranniramol** | 1 309 | 1 | 无 | **+0.345 … +0.489** | **复现成功** |
| **Labuhn** | 417 | 1 | 无 | **−0.725 … −0.050（7/7 全负）** | **复现失败** |

- **独立复核**（浮现）：Hiranniramol CV R²=**+0.3886** vs 零分布 **−0.4668±0.0375**；
  Labuhn CV R²=**−0.1444** vs **−0.2869±0.0505**
- **失败机制诊断**（浮现，配小图）：Labuhn 标签标准差 0.2153（**不是低方差**），
  但 6/7 配置的「预测标准差 / 标签标准差」仅 **0.03–0.37** → **预测坍缩**
- **结论句**：**序列可预测性是数据集依赖的，不可移植。**

### P5-3｜手段二 · 独立预测平台（CRISPRon）
- **左上角小标题**：`5.3 独立预测平台验证`
- **核心观点**：用**别人训练、不同输入编码、不同输出尺度**的模型检验同一扰动方向
- **图形（左：配对斜率图；右：一致性散点图）**：
  - 左：8 条 WT 序列在 C→A 前后 CRISPRon 评分的配对变化
  - 右：本文 7 模型 Δ 与 CRISPRon Δ 的散点，标注唯一分歧点 WT08
- **要点**：
  - 8 条**预登记** WT 序列（第 18 位为 C），仅改第 18 位 **1 个碱基**
  - 方向一致性 **7/8**（Pearson r=**0.629**，Spearman ρ=**0.476**，n=8）
  - CRISPRon 侧 **7/8** 为负向，Δ 均值 **−12.43**
  - **唯一分歧样本 WT08 保留在统计中，未剔除**
- **结论句**：**两个独立构造的模型系统对同一扰动给出同向响应 —— 但这仍是模型行为，不是实验。**

### P5-4｜手段三 · 无位置预设的反事实扰动
- **左上角小标题**：`5.4 饱和突变（反事实扰动）`
- **核心观点**：穷举全部位点的单碱基替换，让重要位置**自己浮出来**，排除"恰好挑中"
- **图形**：21 个位置的平均 |Δ| 条形图（第 18 位高亮）+ 逐序列排名小图
- **要点**：
  - 552 条替换记录（8 序列 × 23 位点 × 3 替换），48 条破坏 PAM 被排除，**504 条计分**
  - **第 18 位平均 |Δ| = 12.86，排名 1/21**
  - 第 18 位 C→A 平均 **−12.425**，其余位置平均仅 **+0.144**
  - 逐序列 7/8 条排第 1
- **结论句**：**排名来自穷举，不来自人为指定。**

---

# 第六部分：项目发展

### P6-0｜章节封面页
- **版式**：整页大标题「**项目发展**」；右下角 `Part 6 / 6`

### P6-1｜三个扩展方向
- **左上角小标题**：`6.1 扩展方向`
- **核心观点**：从"计算发现"走向"实验闭环"
- **图形（三列路线卡片 + 底部汇聚到 "AI-driven CRISPR discovery platform"）**：

| 方向 | 内容 |
|---|---|
| **数据扩展** | more cell lines / more epigenetic features / single-cell data |
| **模型扩展** | foundation model / multimodal AI / biological language model |
| **实验验证** | CRISPR screening / Perturb-seq / wet-lab validation |

- **结论句**：**最终目标是 AI-driven CRISPR biological discovery platform。**

### P6-2｜边界与下一步
- **左上角小标题**：`6.2 边界与下一步`
- **核心观点**：本研究止步于"可证伪假设"，缺的最后一环是实验
- **图形（三级阶梯图）**：模型解释 → 统计证据 → **实验验证**（第三级标注"本研究未做"）
- **要点**：
  - 本文唯一被写成"候选假设"的结论是**第 18 位**，它同时获得三层**互相独立**的支持：
    实测关联 + 多模型归因 + 模型反事实与外部平台
  - **不含任何实验证据**，因此不构成因果结论
  - 最小验证方案：保持其余 22 nt 不变，**仅替换第 18 位**（C↔A），做配对效率测定
- **结论句**：**从 Prediction 到 Discovery，缺的最后一环是实验。**

---

## 结尾页
- **一句话**（居中，最后浮现）：
  > 本平台不追求最高准确率，而是建立
  > `Prediction → Interpretation → Evidence → Discovery`
  > 的科学发现流程。
- **图形**：与封面呼应的极简流程线，末端点亮 `Discovery`
- **不要**放任何表格或数字

---

## 3. 视觉规范

### 3.1 三类页面的版式（严格执行）

| 页面类型 | 版式要求 |
|---|---|
| **章节封面页**（6 张） | 整页留白 ≥ 70%；**只有大标题**（字号为正文 3–4 倍）+ 一条细装饰线；右下角 `Part N / 6`；无正文、无图 |
| **内容页** | **小标题固定左上角**（小字号，不加底色条）；一张主图占版面 ≥ 55%；下方 ≤ 4 行要点；结论句单独一行 |
| **结尾页** | 与封面同版式，仅一句结论 + 一条流程线 |

### 3.2 动画：统一使用「浮现」

- **章节封面页**：大标题整体浮现（约 0.5 s），无其它元素
- **内容页**按顺序浮现：
  1. 左上角小标题（约 0.3 s）
  2. 图形**骨架**（坐标轴 / 流程框 / 卡片轮廓）
  3. 图形**数据**（数据点、条形、连线）
  4. 要点文本（逐行，每行间隔约 0.2 s）
  5. **结论句最后浮现**（可用强调色）
- **禁止**：飞入、旋转、弹跳、闪烁、音效、3D 翻转

### 3.3 配色与排版

- 主色：深蓝 / 靛青（科学感）+ 灰阶（结构）
- **只用一个强调色**标注"显著 / 分歧 / 未检出"，全篇一致
- 语义配色保持一致：**绿 = 支持、灰 = 未检出、红 = 方向冲突**
- 字体：无衬线；数字建议等宽或半等宽以对齐
- 每页留白 ≥ 25%；正文行距 ≥ 1.4

### 3.4 推荐图形类型

| 用途 | 推荐图 |
|---|---|
| 平台流程 | 横向流程条（9 个圆角卡片 + 箭头） |
| 数据表示 | 序列 → (23, 8) 张量热图的映射示意 |
| 模型分工 | 五列卡片 + 汇聚箭头 |
| 位置归因 | 23 位点**热图**（模型 × 位置）+ 谱线图 |
| 环境因子证据 | **Forest plot**（效应量 + 95% CI + 门槛竖线） |
| 统计维度总览 | 四级阶梯图 + 每级一句话 |
| 参数归类 | 六类卡片矩阵 |
| 复现性 | 三数据集并列条形图 + 零分布阴影带 |
| 外部平台验证 | 配对斜率图 + 一致性散点图（标注分歧点） |
| 反事实扰动 | 位置条形图（高亮第 18 位）+ 排名分布 |
| 证据分层 | 阶梯图（模型解释 → 统计证据 → 实验验证） |

---

## 4. 必须避免的内容

| 禁止 | 原因 |
|---|---|
| **代码截图 / 命令行 / 目录树** | 受众是导师与评审，不是开发者 |
| **把参数表直接贴到正文页** | 参数是"可核查的底账"；完整 81 项放**附录**，正文只引用必要数字 |
| **大段文字** | 违反"一页一观点" |
| **跨部分回指**（"如第三部分所述…"） | 违背"各部分各说各的" |
| **章节封面页上放正文** | 封面页只有大标题 |
| **小标题居中或做成页眉横条** | 小部分标题必须在**左上角** |
| **动画用飞入 / 旋转 / 弹跳** | 统一用**浮现** |
| **只展示 accuracy 而回避阴性结果** | 复现失败是本项目最重要的发现之一，隐去即失真 |
| **把 attribution 写成"机制"或"证明"** | attribution 只说明模型依赖强度 |
| **把 ISM / 外部平台一致写成"实验验证"** | 它们是模型内部反事实，不是湿实验 |
| **把 Evidence Tier 写成"显著性强弱排名"** | 它是收敛性/覆盖度评级 |
| **把环境因子的"未检出"写成"无作用"** | 只能说"在本设定下未检出" |
| **暗示三个数据集的效率是同一物理量** | label semantics 不同 |
| **声称跨数据集泛化能力** | 实测结论是不可移植 |

---

## 5. 最终叙事路线

六个部分**相互独立**，各自有独立的开场与收束。听众从任意部分开始都应能听懂。

| 部分 | 一句话主旨 | 收束句 |
|---|---|---|
| **第一部分 背景** | 编辑效率受多因素影响，但"哪些因素重要"未被可靠回答 | 预测只是第一步，规律发现才是目标 |
| **第二部分 项目流程** | 平台是一条可追溯的证据生产链，每一环职责明确 | 数据在这一步变成模型输入 |
| **第三部分 五个模型** | 五个模型用不同归纳偏置覆盖不同类型的规律 | 模型不是答案，而是产生可解释证据的工具 |
| **第四部分 统计学工具与参数** | 四维度回答四类不同问题；参数集中归类 | 低维结论不能升级为高维结论 |
| **第五部分 工具发现与验证手段** | 用两个独立数据集和一个独立平台检验结论 | 序列可预测性不可移植；外部平台给出同向响应 |
| **第六部分 项目发展** | 从计算发现走向实验闭环 | 缺的最后一环是实验 |

**部分之间的转换**：只用**章节封面页**过渡，不做文字承接、不做逻辑回指。

---

## 6. 术语与措辞红线

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

## 7. Gemini 输出格式要求

请 Gemini 输出：

1. **完整的幻灯片清单**，按本文件结构标注：
   - 页面类型（`章节封面页` / `内容页` / `结尾页`）
   - 页码与章节归属（如 `P4-3`）
   - 左上角小标题文本（内容页）
   - 核心观点（一句话）
   - 要点（≤ 4 行）
   - 建议图形类型 + 图中需要标注的具体数字
   - 浮现动画的元素顺序
2. **每页的演讲者备注**（2–4 句，说明这一页要讲清楚的逻辑）
3. **附录页建议**：把第 9 节的完整参数表放入"备份页"，正文不出现
4. **模板规格**：页面尺寸、字号层级（大标题 / 左上角小标题 / 正文 / 图注）、
   配色 hex、留白比例

**不要**：
- 不要生成真实图片文件；
- 不要编造本文件未给出的数字；
- 不要删减阴性结果（Labuhn 复现失败、环境全 Inconclusive、无 Tier 1/2、无实验证据）；
- 不要在各部分之间添加"如前所述"式的关联。

---

## 8. 附录：可引用的图与表清单

**已有图（可直接引用或重绘）**

| 文件 | 内容 | 对应页 |
|---|---|---|
| `docs/paper/figures/fig1_workflow.pdf` | 平台科学发现流程图 | P2-1 |
| `docs/paper/figures/fig2_prediction.pdf` | 三划分下的预测性能 | P4-2 |
| `docs/paper/figures/fig3_environment.pdf` | 环境因子增量效应与统计证据 | P4-4 |
| `docs/paper/figures/fig4_sequence_attribution.pdf` | 跨模型序列归因谱 | P4-3 |
| `docs/paper/figures/fig5_kernel.pdf` | CNN 感受野消融 | P3-5 |
| `docs/paper/figures/fig6_cellline.pdf` | 细胞背景异质性 | P4-5 |
| `docs/paper/figures/fig7_evidence.pdf` | 证据整合 forest 图 | P4-5 |
| `docs/paper/figures/fig_ext_a…d_*.png` | 外部模型验证四联图 | P5-3 |
| `docs/paper/figures/position18_*.png` | 第 18 位碱基效应与符号化替换 | P5-4 |

**已有表（放入附录页）**

| 文件 | 内容 |
|---|---|
| `docs/paper/tables/tab0_data_quality.tex` | 数据质量与泄漏审计（P2-2） |
| `docs/paper/tables/tab1_dataset.tex` | 三数据集组成（P5-2） |
| `docs/paper/tables/tab2_prediction.tex` | 逐配置预测性能（P4-2） |
| `docs/paper/tables/tab3_environment.tex` | 环境因子完整统计（P4-4） |
| `docs/paper/tables/tab4_kernel.tex` | CNN 核配对消融（P3-5） |
| `docs/paper/tables/tab5_motifs.tex` | 候选序列模式（P4-3） |
| `docs/paper/tables/tab6_candidates.tex` | 候选假设优先级（P6-2） |
| `docs/paper/tables/tab7_replication.tex` | 跨数据集复现主表（P5-2） |
| `docs/paper/tables/tab8_external_validation.tex` | 外部平台验证逐样本（P5-3） |
| `docs/paper/tables/tab9_counterfactual.tex` | 饱和突变 21 位点（P5-4） |
| `docs/paper/tables/tab10_evidence_layers.tex` | 六层证据 E1–E6 定义（附录） |
| `docs/paper/tables/tab11_attribution_position.tex` | 位置层级归因权威值（P4-3） |

**统计参数的唯一权威来源**（如需核对，指向这些文件而非本 PPT）

- `analysis/config.py` —— 全部阈值集中于此
- `analysis/stats/{bootstrap,hypothesis_tests,multiple_testing,effect_size}.py` —— 统计实现
- `analysis/evidence/integration.py::classify_evidence_tier` —— **Evidence Tier 唯一权威**
- `results/batches/ultimate_run/summary/tables/` —— 统计产物
- `results/paper_rewrite/authoritative_numbers.json` —— 论文数字权威来源

---

## 9. 附录 A：完整统计参数清单（取自 `analysis/config.py`，逐字段无遗漏）

> 本附录由 `AnalysisConfig()` 实例直接导出，保证与代码一致。
> **这是 PPT 的备份页素材**：正文只引用必要数字，完整参数放在附录/答疑页。

### 9.1 全局随机性与迭代参数

| 参数 | 值 | 含义 |
|---|---|---|
| `bootstrap_iterations` | **2000** | — |
| `bootstrap_seed` | **2024** | — |
| `bootstrap_alpha` | **0.05** | — |
| `permutation_iterations` | **1000** | — |
| `random_seed` | **42** | — |

### 9.2 `AttributionRuleConfig`

归因稳健性阈值。**SNR 仅作 robustness/attribution strength，不是统计显著**；不参与 Evidence Tier。

| 参数 | 值 |
|---|---|
| `snr_threshold` | `2.5` |
| `snr_moderate` | `1.8` |
| `snr_weak` | `1.2` |
| `min_effect_size` | `0.005` |
| `method` | `mean_over_std` |

### 9.3 `StatisticalRuleConfig`

统计证据**分档**阈值。仅用于 Importance–ΔR² 资产的 evidence_strength 标签与线性回归训练侧 FDR 分档；**不参与 Evidence Tier**（Tier 只用 fdr_weak 作为统计门）。

| 参数 | 值 |
|---|---|
| `fdr_strong` | `0.001` |
| `fdr_moderate` | `0.01` |
| `fdr_weak` | `0.05` |

### 9.4 `ConsensusRuleConfig`

跨模型 / 跨 cell-line 一致性规则（Evidence Tier 的覆盖度与方向一致率门槛）。

| 参数 | 值 |
|---|---|
| `min_coverage` | `2` |
| `direction_concordance` | `0.8` |
| `cellline_consistent_ratio` | `0.75` |
| `unstable_effect_threshold` | `10.0` |

### 9.5 `CelllineConsistencyConfig`

cell-line context 判定阈值（方向 + 幅度异质性 + CI 重叠）。

| 参数 | 值 |
|---|---|
| `min_cell_lines` | `2` |
| `consistent_ratio` | `0.75` |
| `conflicting_ratio` | `0.25` |
| `heterogeneity_ratio` | `2.0` |
| `ci_overlap_relaxes` | `True` |

### 9.6 `EvidenceRuleConfig`

**Evidence Tier 的权威阈值**（唯一来源，由 evidence/integration.py 消费）。

| 参数 | 值 |
|---|---|
| `min_absolute_delta_r2` | `0.01` |
| `ci_crosses_zero_forces_inconclusive` | `True` |
| `min_bootstrap_iterations` | `200` |
| `statistical_gate_can_promote` | `False` |
| `effect_gate_mode` | `model_mean` |

### 9.7 `AnovaRuleConfig`

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

### 9.8 `FdrFamilyConfig`

multiple-testing family 定义：不同科学问题绝不并入同一 FDR 族。

| 参数 | 值 |
|---|---|
| `enabled_families` | `('environment_permutation_edge', 'environment_permutation_main', 'environment_permutation_interaction', 'environment_anova', 'environment_anova_group', 'motif_enrichment')` |
| `min_family_size` | `2` |

### 9.9 `MotifDiscoveryConfig`

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

### 9.10 `QCConfig`

QC 门禁（detection 层，不负责用户科学决策）。

| 参数 | 值 |
|---|---|
| `environment_missing_rate_limit` | `0.3` |
| `strict_complete_gate` | `70.0` |
| `ambiguous_detection_only` | `True` |

### 9.11 附录 B：不在 `analysis/config.py` 中的统计参数（已逐项核实）

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

### 9.12 附录 C：本项目**明确不做**的统计处理（PPT 需诚实标注）

| 未做 | 说明 |
|---|---|
| ANOVA 的 FDR 校正 | `anova_results.csv` **无 FDR 列**（有意决策：ANOVA 回答 global 问题，不做族内校正） |
| bootstrap CI 的多重校正 | CI 本身不做 FDR |
| 位置 18 的显著性检验 | 样本量不足（每条序列在该位点只有 1 个观测），**只报描述统计与排名** |
| 环境因子的**因果**检验 | 观察性数据，无干预实验 |
| 效应量的**样本加权** | 全项目跨实验聚合**一律等权**；**无任何按样本数 n 的加权平均** |
| SNR / SHAP / IG / ISM / attention 的 p 值 | **禁止**这些原始值进入 p 值或 FDR |
| 湿实验验证（E5） | **完全空缺** —— 这是全篇最重要的边界 |
