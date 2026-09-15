# Evidence Tier 的科学定义（唯一方法学解释）

> 配套：代码审计 `docs/audit/evidence_tier_code_audit.md`、溯源 `docs/paper/evidence_tier_provenance.md`
> 权威实现：`analysis/evidence/integration.py::classify_evidence_tier`（环境行与 motif 行共用同一函数）

---

## 1. 六个概念的分工（禁止混用）

| 概念 | 回答的问题 | 本项目中的量 | 允许的表述 | 禁止的表述 |
| :--- | :--- | :--- | :--- | :--- |
| **Effect（效应）** | "这个因素改变以后，预测结果/模型性能改变了多少？" | 环境增量 `ΔR²`（edge 级 / factor 级）、signed ISM `Δ`（第 18 位替换）、ANOVA effect、回归系数 | "增量预测价值"、"效应量级"、"方向" | 把不同来源的 effect 互换（见 §1.1） |
| **Importance（重要性）** | "模型在预测时有多依赖这个因素？" | SHAP、Integrated Gradients、CNN ISM 幅值、attention（辅助） | "模型依赖度"、"归因"、"敏感性" | "因果作用"、"生物学重要性" |
| **Statistical Evidence（统计证据）** | "观察到的 effect 是否有统计证据？" | bootstrap CI、permutation p、BH-FDR、回归 p | "CI 不跨 0"、"FDR<0.05" | 用 CI 冒充 p 值；用 FDR 冒充效应大小；对 SHAP/IG/ISM 原始值做 FDR 后称"显著" |
| **Robustness（稳健性）** | "换模型、seed、cell line、split 后结论是否仍稳定？" | 跨模型方向一致率、seed 复现、cell-line consistency、CI 稳定性 | "跨模型一致（cross-model concordance）"、"架构稳健性（architecture robustness）"、"降低模型依赖性（model-dependence reduction）" | "控制了过拟合"、"证明为真" |
| **Evidence Tier（证据等级）** | "已有计算证据的收敛性、覆盖度与稳健性综合到什么程度？" | Tier 1/2/3/Inconclusive/No current evidence | "证据收敛"、"稳健性评级" | effect size 排名、生物学重要性排名、因果证据、显著性排名 |
| **Factorial ANOVA（析因方差分析）** | "在整个析因设计中，因子及其交互贡献了多少全局变异？" | `R² ~ A*B*C*D + C(model)+C(cell_line)+C(split_type)`，Type-II 边际 F | "全局因子/交互推断" | "edge 级证据"、"Tier 的输入" |

### 1.1 不同来源的 Effect 不可互换

| Effect 量 | 物理含义 | 单位/参照 |
| :--- | :--- | :--- |
| `ΔR²`（环境增量） | 在给定背景下加入某表观通道后，**留出预测性能**的变化 | held-out R²（同一 test cohort 的配对差） |
| signed ISM `Δ` | 某位置碱基替换后，**模型输出**的变化（有符号） | 模型预测效率（0–1 尺度，未 clip） |
| ANOVA effect / F 的 `effect` 列 | 控制其他项后，因子**水平差**对 R² 的边际贡献 | R² |
| 回归系数 | 特征对**模型输出**的线性贡献 | 预测值尺度 |

它们都叫 effect，但"改变的是模型输出还是预测性能""是否配对""是全局还是条件"完全不同，
**不得跨表比较大小，也不得互换作为 Tier 的输入**。

### 1.2 bootstrap CI ≠ p 值；FDR ≠ effect size

* 因子级 bootstrap CI 的单位是**模型**（`n=7`，跨模型不确定性；见 `estimate_basis` 列），
  不是样本级置信区间；它不能被读作 p 值，也不提供拒绝/不拒绝的二元结论。
* FDR 只回答"在某个检验族内，这个 p 值有多值得注意"，**不携带效应量信息**；
  一个 FDR 极小但 |ΔR²|=0.002 的因子仍然是"稳定的小效应"。

---

## 2. Evidence Tier 的正式定义

> **Evidence Tier 是对现有 computational evidence 的 convergence、coverage 与 robustness 的综合评级。**
>
> Evidence Tier is an evidence-convergence / robustness classification — **not** a biological
> effect-size ranking, **not** a statistical-significance scale, and **not** causal inference.

### 2.1 判定规则（唯一权威版本）

输入（全部由 edge-level 证据聚合，见溯源文档）：

* `coverage`：有稳定主效应估计的模型数（`model_mean` 行数）
* `supporting`：与模型等权均值**同号**的模型数
* `concordance`：多数方向占比（去零方向）
* `ci_crosses_zero`：跨模型 bootstrap CI 是否跨 0（需 `status=ok` 且 `n_bootstrap ≥ 200`）
* `effect_gate_pass`：任一模型稳定主效应满足 `|ΔR²| ≥ min_absolute_delta_r2`（默认 0.01）
* `statistical_gate_pass`：该因子在置换族内的 FDR `< statistical.fdr_weak`（默认 0.05）
* `conflicting_direction` / cell-line 标签（`Context-conflicting`）

| 顺序 | 条件 | Tier | 语义 |
| ---: | :--- | :--- | :--- |
| 1 | 方向冲突，或 CI 跨 0（`ci_crosses_zero_forces_inconclusive=True` 时） | **Inconclusive** | 证据自相矛盾或不确定性过大（**优先级最高**） |
| 2 | `supporting ≥ 2` 且 `concordance ≥ 0.80` 且 `robustness_gate` 且 **effect 门通过** | **Tier 1** | 多模型收敛 + 方向一致 + 稳健 + **达到最小绝对预测增益** |
| 3 | `supporting ≥ 2` | **Tier 2** | 多模型收敛但一致率/稳健性/增益不足以升级 |
| 4 | `supporting == 1` 且（effect 门 或 统计门通过） | **Tier 3** | 单模型特异 / 探索性 |
| 5 | `coverage == 0` | **No current evidence** | 没有可用估计（≠ "无效应"） |
| 6 | 其它 | **Inconclusive** | 覆盖或方向信息不足 |

### 2.2 三个门的分工：统计证据不能单独提升

* **effect 门**（`evidence.min_absolute_delta_r2 = 0.01`，口径 = **M 个模型配置的等权平均**）：
  回答"增量在绝对尺度上是否非平凡"。**只有它能把因子提升到 Tier 1**。
* **统计门**（`statistical.fdr_weak = 0.05`，输入 = *Minimal Edge-level FDR across Tested Contexts*）：
  回答"该增量是否**至少在一个被测试上下文中**出现统计证据"。它是 existence-oriented 证据，
  存在 extremum selection；**不能单独提升 Tier 1**（可由 `evidence.statistical_gate_can_promote` 显式打开，
  仅用于回归/敏感性对照，默认 `False`）。它可以支持 effect 证据、排除缺乏统计支持的候选、参与 Tier 2 与注释。
* **robustness 门**：方向一致率达标 且 Model-Level Bootstrap 区间不跨 0。

本批的实例（R1–R6 完成后）：四个因子的模型等权平均 \|ΔR²\| 分别为
0.00095 / 0.00202 / 0.00594 / 0.00932，**全部 < 0.01** → effect 门全部 fail；
因此即使统计门全部通过（min_edge_FDR 0.0093–0.0140，但 FWER 上界 0.23–0.25），
本批**没有任何环境因子达到 Tier 1**：RRBS = Tier 2，其余 Inconclusive。

---

## 3. `min_absolute_delta_r2 = 0.01` 的正确定义

* 正式名称：**minimum absolute predictive gain threshold（最小绝对预测增益门）**。
* 单位：与响应变量相同（held-out R²），因此只能在同一响应变量口径内使用。
* **不是** statistical significance threshold，**不具有**普适统计学含义，**不得**暗示"超过即重要"。
* 经验依据（审计脚本 `docs/audit/audit_min_absolute_delta_r2.py`）：
  * 边级 ΔR² 的 P50 = −0.0010、P75 = +0.0058、max = +0.0686；**36.9 % 的边 ≥ 0.01** → 该阈值位于分布主体内，属**宽松**的存在性门；
  * 阈值**不中立**：CNN k7 53.1 % vs XGBoost 12.5 %；single/all 45.4 % vs mixed 14.4 %；HEK293T 57.1 % vs HeLa 24.6 %。
    原因是它是**绝对**门，而 baseline R² 本身跨模型/划分差 4–5 倍 → **不可跨模型直接比较**。
* 相对口径（`ΔR²/R²_baseline`）不可替代：本批 66 条边的 parent R² ≤ 0、112 条 < 0.01、
  146 条相对提升 > 100 %、32 条符号不可解释 → **不使用相对 R² 提升率作为判据**。

---

## 4. Tier 1 代表什么 / 不代表什么

**代表（R3/R4 之后的定义）**：
* 至少 2 个（本批环境因子为 7 个）模型对同一因子给出了**同号**的稳定主效应估计；
* 多数方向占比 ≥ 0.80，且分母为**全部有效模型**（R5）；
* Model-Level Bootstrap Interval（n = 7 模型配置）不跨 0，且迭代数 ≥ 200；
* **模型等权平均 \|ΔR²\| ≥ 0.01（effect 门必须通过）**；
* 跨细胞系上下文**未**被判为 `Context-conflicting`。
* 统计证据（existence-oriented 的 min edge-level FDR）可以提供支持，但**不能替代** effect 门。

**不代表**：
* ❌ 生物学上最重要 / 效应最大（Tier 与 |ΔR²| 无关；本批 Tier 1 的 |ΔR²| 仅 0.0093）；
* ❌ 因果证据（全部来自观测数据上的模型行为，属 computational evidence）；
* ❌ 显著性或"p<0.05"的另一种写法（FDR 门与 CI 门服务于不同的判定层）；
* ❌ 可跨因子/跨数据集直接比较的排序（覆盖度与一致率依赖模型集合）；
* ❌ "控制了过拟合"（跨模型一致只降低模型依赖性，不构成统计意义上的控制）。

> **本批最终结果（R1–R6 后）**：环境因子 0 个 Tier 1；RRBS = **Tier 2**（effect 门 fail，统计门 pass 但不能单独提升）；
> CTCF / DNase / H3K4me3 = Inconclusive。详见 `docs/audit/evidence_tier_before_after.md`。

---

## 5. 与 Factorial ANOVA 的关系

```text
Edge-level evidence:  具体增量效应 (在给定背景 S 上加入因子 e)
        ↓  per-model 均值 → coverage / concordance / bootstrap CI / permutation
     Evidence Tier      →  evidence_matrix.csv  →  Table 3 / Fig. 7

Factorial ANOVA:      全局因子与交互的主效应 (响应 = 留出 R², 区组 = model/cell/split)
        ↓
     anova_results.csv  →  Fig. 3D / Table 3 的 anova_F、anova_p 列
```

* **Edge-level evidence evaluates specific incremental effects**（给定背景下的条件增量）；
  **factorial ANOVA evaluates the global variation attributable to factors and their interactions
  within the factorial design**（对全网格的方差分解）。两者回答不同问题。
* 因此论文可以同时报告"ANOVA 未检出显著主效应（p = 0.056–0.663）"与"RRBS 达到 Tier 1"，
  只要说明前者是全局因子/交互项推断、后者是具体增量效应的收敛性评级。
* 禁止的表述："ANOVA 是宏观、permutation 是微观"（错误地暗示二者是同一分析的不同尺度），
  以及用 ANOVA 的 p 值去验证或否定 Tier 等级。
* 实现约束：`environment_evidence_matrix()` 的签名中**不含任何 ANOVA 参数**，
  并由测试 `TestAnovaIndependence` 保证 ANOVA 列变化不改变 edge-level Tier。

---

## 6. 术语红线（写入代码 docstring 与论文方法）

1. bootstrap CI ≠ p-value；FDR ≠ effect size。
2. SNR / attention / SHAP / IG / ISM 幅值**永不**进入 p 值或 FDR；它们只能称
   attribution / robustness strength。
3. 跨模型一致只能称 cross-model concordance / architecture robustness / model-dependence
   reduction，不得称"控制过拟合"。
4. Tier 不得写成"生物学上最重要"，不得写成"因果证据"，不得作为效应量排序使用。
5. 不得为了得到更多 Tier 1 而调整阈值；阈值改动必须有数据依据并记录在溯源文档中。
