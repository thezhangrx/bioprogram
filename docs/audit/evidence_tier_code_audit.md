# Evidence Tier 代码审计（第一步：只审计，不改代码）

> 对象：`analysis/evidence/`、`analysis/config.py`、`analysis/stats/tasks.py`、`analysis/sequence/motif/pipeline.py`、
> `analysis/reports/markdown_report.py`、`paper/make_assets.py`、`paper/sections/*.tex`
> 批次：`results/batches/batch_20260909_full`（1 344 runs，evidence_matrix.csv 600 行）
> 方法：全部结论沿**实际调用链**验证（`grep` 调用点 + 逐文件阅读），不依据 README/注释推断。
> 审计脚本：`docs/audit/audit_min_absolute_delta_r2.py`（只读，产出 `docs/audit/evidence_tier_threshold_audit.csv`）

---

## 0. 结论摘要

1. **生产实现只有一个**：`analysis/evidence/integration.py::classify_evidence_tier`（`:43-65`），
   由 `environment_evidence_matrix`（`:184`）与 motif 行生成器（`sequence/motif/pipeline.py:362`）调用，
   结果写入 `tables/evidence_matrix.csv` → 论文 Table 3 的 `tier` 列 + Fig.7 标注 + §3.8/§2.10 正文。
2. **`analysis/evidence/rules.py` 未进入生产**：仅被 `analysis/tests/test_core.py` 导入；
   `classify_mutation_effect` 连测试都没有（0 个调用点）。它定义的 FDR 阶梯（0.001/0.01/0.05）与
   SNR 阶梯（2.5/1.8/1.2）**不参与任何 Tier 判定**。
3. **进入 Tier 的阈值只有 5 个**：coverage ≥ 2、concordance ≥ 0.80、|ΔR²| ≥ 0.01（effect 门）、
   permutation FDR < 0.05（统计门）、CI 不跨 0（且 n_bootstrap ≥ 200）；外加 |Δ| ≥ 10 的稳定性过滤与
   cell-line `Context-conflicting` 一票否决。
4. **2 个伪参数**：`statistical.fdr_nominal`（0 处引用）与 `evidence.ci_crosses_zero_forces_inconclusive`
   （配置存在但代码未读取，行为硬编码在 `integration.py:53`）。
5. **`|ΔR²| ≥ 0.01` 不是统计显著性阈值**，而是"最小绝对预测增益门"；经验审计显示它**不**是分布尾部
   （边级 36.9 % 的边超过它），且**系统性偏向弱基线模型/划分**（CNN k7 53 % vs XGBoost 12.5 %；
   single/all 45 % vs mixed 14 %）。相对口径（ΔR²/R²_baseline）在 2.5 %–5.5 % 的边上失去解释 → 不能替代。
6. **ANOVA 不进入 Tier（现状正确）**：`environment_evidence_matrix` 的入参只有
   `main_effects / cellline_summary / bootstrap_ci / permutation`，没有 ANOVA；ANOVA 只出现在
   `anova_results.csv` → Fig.3D / Table 3 的 `anova_F/anova_p` 列。
7. **论文方法描述与代码有 3 处不一致**：把未参与 Tier 的 SNR/FDR 阶梯写成"所有阈值统一配置"；
   把 effect 门写成"统计/归因强度"（环境路径没有归因成分）；`partial η²` 实际是经典 η²。
8. **发现一个真实的资产陈旧问题（重算后 Tier 发生变化）**：`tables/bootstrap_main_effects.csv` 是
   在 `bootstrap_main_effects` 的"先按模型均值再对模型 bootstrap"修正**之前**生成的，
   因此旧 `evidence_matrix.csv` 里 DNase 的 CI [−0.0046, −0.0001] 与论文 Fig.7 使用的
   后修正口径 CI（`docs/paper_analysis/factor_level_ci.csv`，[−0.0045, +0.0003]）**互相矛盾**。
   用当前代码重跑 `analyse.pipeline` 后 CI 变为 [−0.0052, +0.0004]（跨 0）→ **DNase 从 Tier 2 降为
   Inconclusive**，与论文自报的 CI 一致。这属于"CI 输入资产变化"触发条件，详见 §7。

---

## 1. 唯一生产实现与调用链

```
offline: 1 344 runs → results/<batch>/<run>/{model}_metrics.json / *_predictions.csv
   │
   ├─ analysis/stats/tasks.py::bootstrap_main_effects      → tables/bootstrap_main_effects.csv
   ├─ analysis/stats/tasks.py::permutation_* + apply_fdr   → tables/permutation_results.csv
   └─ analysis/environment/incremental_effect.py           → tables/environment_main_effects.csv
        │                                                     tables/cellline_effects.csv
        ▼
   analysis/pipeline.py:404-428  (task "evidence_integration")
        │   evidence_matrix = environment_evidence_matrix(main_df, cellline_df, config,
        │                          bootstrap_ci=stats_bundle["main_ci"],
        │                          permutation=stats_bundle["permutation"])
        ▼
   analysis/evidence/integration.py::environment_evidence_matrix       (环境行, :90-214)
        ├─ 稳定性过滤 |Δ| < consensus.unstable_effect_threshold(10.0)  (:118-120)
        ├─ per (model,factor) 均值 → coverage / concordance / overall   (:121-134)
        ├─ effect 门 strong = any(|per-model mean| ≥ 0.01)              (:132-133)
        ├─ 统计门 statistical_support = permutation FDR < 0.05          (:177-178)
        ├─ CI 门  n_bootstrap≥200 且 ci_excludes_zero                   (:149-161)
        ├─ cell-line 标签（众数），Context-conflicting → Inconclusive     (:139-143, :181-182)
        └─ classify_evidence_tier(...)                                  (:184-191)
   analysis/sequence/motif/pipeline.py::motif_evidence_rows            (motif 行, :362)
        └─ 复用同一个 classify_evidence_tier（coverage=model family 数, concordance=None, CI=None）
        ▼
   tables/evidence_matrix.csv  →  summary/06_evidence_integration.md
                               →  analysis/visualization/evidence_plots.render → figures/06_evidence/
                               →  markdown_report.build_hypotheses_md → 07_biological_hypotheses.md
                               →  paper/make_assets.py: Figure 7 + Table 3（tier 列）
```

**生产 Tier 定义（唯一权威）**：

| 顺序 | 条件 | 结果 | 代码 |
| ---: | :--- | :--- | :--- |
| 1 | `conflicting_direction` 或 `ci_crosses_zero` | `Inconclusive` | `integration.py:53-54` |
| 1b | （环境行专有）cell-line 众数标签 = `Context-conflicting` | `Inconclusive` | `:181-182` |
| 2 | `supporting ≥ 2` 且（concordance 为空或 ≥ 0.80）且 `strong_stat_or_attribution` | `Tier 1` | `:55-58` |
| 3 | `supporting ≥ 2` | `Tier 2` | `:59-60` |
| 4 | `supporting == 1` 且 `strong_stat_or_attribution` | `Tier 3` | `:61-62` |
| 5 | `applicable == 0` | `No current evidence` | `:63-64` |
| 6 | 其它 | `Inconclusive` | `:65` |

其中 `strong_stat_or_attribution = effect门 OR 统计门`（`:179`），`supporting` = 与模型等权均值同号的模型数（`:136-138`）。

---

## 2. 规则逐项审计（规则 → 定义 → 调用 → 资产 → 论文）

| # | 规则 / 函数 | 定义位置 | 实际调用位置 | 进入最终资产 | 进入论文 |
| ---: | :--- | :--- | :--- | :--- | :--- |
| 1 | `classify_evidence_tier` | `integration.py:43-65` | `integration.py:184`（环境）、`motif/pipeline.py:362`（motif）、`markdown_report.py:181`（展示用 `tier_from_value`） | ✅ `evidence_matrix.csv::evidence_tier`（600 行） | ✅ Table 3 `tier` 列、Fig.7 标注、§3.8、§2.10 |
| 2 | `direction_concordance` | `integration.py:18-28` | `integration.py:131` | ✅ `direction_concordance` 列 | ✅ Table 3、§3.8（0.86/0.71） |
| 3 | `environment_evidence_matrix` | `integration.py:90-214` | `pipeline.py:412` | ✅ 生成整张环境证据表 | ✅ Table 3 / Fig.7 |
| 4 | `evidence_record_row` | `integration.py:68-87` | **无调用点（死代码）** | ❌ | ❌ |
| 5 | `tier_from_value` | `integration.py:217-221` | `markdown_report.py:181` | ✅ 只用于把字符串转枚举 | ✅（间接：假设生成） |
| 6 | `rules.py::classify_statistical_by_fdr` | `rules.py:12-26` | **仅 `analysis/tests/test_core.py:20,86-89`** | ❌ | ❌ |
| 7 | `rules.py::classify_attribution` | `rules.py:29-53` | **仅 `tests/test_core.py:20,94-101`** | ❌ | ❌ |
| 8 | `rules.py::classify_mutation_effect` | `rules.py:56-67` | **0 个调用点** | ❌ | ❌ |
| 9 | `rules.py::direction_of` | `rules.py:70-73` | 0（`integration.py:31-40,224-226` 有等价实现） | ❌ | ❌ |
| 10 | `EvidenceStrength` 枚举 | `schemas.py:21-38` | 仅 `rules.py` + `tests/test_core.py` | ❌ | ❌ |
| 11 | `importance_metrics` 的 SNR/FDR 分档 | `importance_metrics.py:100-146` | `visualization/importance_delta.py:241-271`、`importance_vs_delta_r2.csv` | ✅（**属于 Importance–ΔR² 资产，不是 Tier**） | ✅ Supp. Fig S1 |

**判定**：项目存在**两套"强度"语言**——生产用的 Evidence **Tier**（收敛性/稳健性分级）与
`rules.py`/`importance` 的 **Strength**（SNR/FDR 分档）。后者中只有 importance 一路真正产出资产；
`rules.py` 一路完全悬空。为避免"两套互相矛盾的 Tier 定义"，应删除悬空的那一套。

---

## 3. 阈值逐项审计（是否真正参与 Tier）

| 阈值 | 配置项（`analysis/config.py`） | 是否进入 Tier | 进入位置 / 现状 |
| :--- | :--- | :--- | :--- |
| coverage ≥ 2 | `consensus.min_coverage=2`（`:33`） | ✅ | `integration.py:55,59,61`（Tier1/Tier2 门槛；=1 且 strong → Tier3） |
| direction concordance ≥ 0.80 | `consensus.direction_concordance=0.80`（`:34`） | ✅ | `integration.py:56`（只作用于 Tier1） |
| **\|ΔR²\| ≥ 0.01** | `consensus.environment_strong_effect=0.01`（`:37`） | ✅ | `integration.py:132-133`（per-**model** 均值的最大绝对值，OR 进 `strong`）；motif 侧 `motif/pipeline.py:360` |
| permutation FDR < 0.05 | `statistical.fdr_weak=0.05`（`:25`） | ✅ | `integration.py:177-178`（`statistical_support`，与 effect 门取 OR） |
| CI 跨 0 → Inconclusive | ⚠️ `evidence.ci_crosses_zero_forces_inconclusive=True`（`:64`）**未被读取** | ✅（硬编码行为） | `integration.py:53`；配置项是**伪参数** |
| bootstrap 迭代数门槛 200 | `evidence.min_bootstrap_iterations=200`（`:65`） | ✅ | `integration.py:155-156`（不足则 CI 不参与判定） |
| \|Δ\| ≥ 10 稳定性过滤 | `consensus.unstable_effect_threshold=10.0`（`:38`） | ✅ | `integration.py:118-120`；置零前剔除，未删数据 |
| cell-line Context-conflicting 一票否决 | `cellline.conflicting_ratio/consistent_ratio/heterogeneity_ratio`（`:52-56`） | ✅ | `integration.py:139-143,181-182`（经 `classify_cellline_consistency`） |
| FDR 0.001 / 0.01（strong/moderate） | `statistical.fdr_strong/fdr_moderate`（`:23-24`） | ❌ | 只被 `rules.py:20,22`（死代码）与 importance 资产引用 |
| FDR 0.10（nominal） | `statistical.fdr_nominal=0.10`（`:26`） | ❌ | **全仓库 0 处引用（伪参数）** |
| SNR 2.5 / 1.8 / 1.2 | `attribution.snr_threshold/snr_moderate/snr_weak`（`:12-14`） | ❌ | 只被 `rules.py`（死代码）与 importance 资产引用；**Tier 路径无任何归因/SNR 成分** |
| min effect size 0.005（attribution） | `attribution.min_effect_size=0.005`（`:15`） | ❌ | 同上 |

---

## 4. `|ΔR²| ≥ 0.01` 的经验审计（对应任务第四步）

> 数据：`experiment_table.csv`（1 344 runs）、`environment_edges.csv`（2 541 边）、
> `environment_main_effects.csv`（252 行，剔除 |Δ|≥10 后 224 行）。明细见
> `docs/audit/evidence_tier_threshold_audit.csv`，复现脚本 `docs/audit/audit_min_absolute_delta_r2.py`。

### 4.1 baseline R² 分布（剔除发散 |R²|≥10）

| model | split | n | P5 | P50 | P95 | R²≤0 的 run | R²<0.01 的 run |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| cnn(3\|3) | single/all | 64 | −0.0043 | 0.0351 | 0.0706 | 4 | 10 |
| cnn(5\|3) | single/all | 64 | 0.0248 | 0.0569 | 0.1108 | 1 | 1 |
| cnn(7\|3) | single/all | 64 | 0.0233 | 0.0795 | 0.1190 | 0 | 1 |
| mlp | single/all | 64 | 0.0175 | 0.0851 | 0.1076 | 0 | 0 |
| transformer | single/all | 64 | 0.0290 | 0.0687 | 0.1187 | 0 | 2 |
| xgboost | single/all | 64 | 0.0431 | 0.1155 | 0.1421 | 0 | 0 |
| linear | single/all | 43 | −0.0552 | 0.0874 | 0.1125 | **12** | **14** |
| （mixed 全部模型） | mixed | 50–64 | 0.0689 | 0.0831–0.1612 | 0.1850 | 0 | 0 |

**含义**：baseline 跨越 "R²<0（线性发散后的残余）/ R²≈0.03（弱）/ R²≈0.16（最强）" 三个数量级区间。

### 4.2 ΔR² 分布与 0.01 的覆盖

| 层级 | n | min | P25 | P50 | P75 | max | \|ΔR²\|≥0.01 | 占比 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 边级 `delta_r2` | 2 541 | −0.0761 | −0.0076 | −0.0010 | +0.0058 | +0.0686 | 938 | **36.9 %** |
| 因子级 `main_r2_delta`（\|Δ\|<10） | 224 | −0.0529 | −0.0065 | −0.0008 | +0.0049 | +0.0236 | 49 | **21.9 %** |

**含义**：0.01 落在分布**主体之内**（不是尾部）。它作为"最小绝对预测增益门"是**宽松的**，
因此它**不能**被解读为显著性阈值，也不表示"超过即重要"。

### 4.3 Tier 中真正使用它的位置

`strong = any(|per (factor, model) 均值| ≥ 0.01)`：

| factor | 模型数 | 模型均值 | min | max | \|ΔR²\|≥0.01 的模型数 | effect 门 |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| ctcf | 7 | −0.0009 | −0.0281 | +0.0072 | 1 | ✅（但被 CI/细胞系冲突否决） |
| dnase | 7 | −0.0020 | −0.0077 | +0.0015 | **0** | ❌ |
| h3k4me3 | 7 | −0.0059 | −0.0246 | +0.0016 | 1 | ✅（被 Context-conflicting 否决） |
| rrbs | 7 | −0.0093 | −0.0529 | +0.0010 | 1 | ✅ |

**关键**：RRBS 的总体均值 |−0.0093| < 0.01，它能进 Tier 1 靠的是**统计门**（permutation FDR = 0.0093 < 0.05），
而不是 effect 门——这正是"两个正交门取 OR"的直接后果，必须在论文/文档中写明（现状 Fig.7 caption 只说
"四个因子的 |ΔR²| 均小于 0.01"，与 Tier 1 并列时容易被读成自相矛盾）。

### 4.4 阈值是否系统性偏向某些 model / split / cell line

| 分组 | \|ΔR²\|≥0.01 占比 |
| :--- | ---: |
| CNN k=3 / k=5 / k=7 | 42.7 % / 47.9 % / **53.1 %** |
| MLP / Transformer / Linear / XGBoost | 39.1 % / 33.9 % / 16.7 % / **12.5 %** |
| split = single / all / mixed | 45.4 % / 45.4 % / **14.4 %** |
| cell_line = HEK293T / HL60 / HCT116 / HeLa / (mixed none) | 57.1 % / 53.6 % / 46.4 % / **24.6 %** / 14.4 % |

**含义**：0.01 是**绝对**门槛，而 baseline 越弱（CNN k3/k7、single/all、HeLa 样本多但 R² 低）越容易"通过"，
baseline 越强（XGBoost、mixed）越难。因此该门**不可跨模型直接比较**，只能作为"该 factor 是否存在
非平凡的绝对增量"的存在性门。**若未来要跨模型比较，需要另行设计并论证口径，本次不引入。**

### 4.5 为什么不用 relative improvement（ΔR²/R²_baseline）

| 相对口径的失效情形 | 边数 | 占比 |
| :--- | ---: | ---: |
| parent R² ≤ 0（比值符号反转，无意义） | 66 | 2.5 % |
| parent R² < 0.01（分母趋 0，比值爆炸） | 112 | 4.2 % |
| \|相对提升\| > 100 %（ΔR² 大于 baseline 本身） | 146 | 5.5 % |
| 相对提升为负且分母为负（符号已不可解释） | 32 | 1.2 % |

**结论**：在本批数据里 baseline R² 存在 ≤0 与 <0.01 的情形（线性发散残余 + 弱模型），
相对提升会出现符号反转与爆炸；**不使用相对 R² 提升率作为主判据**。
`0.01` 保留，并明确命名为 **minimum absolute predictive gain threshold**（最小绝对预测增益门），
参数化为 `min_absolute_delta_r2`，不做普适统计学解释。

---

## 5. 逻辑问题清单与最小修复方案

| # | 问题 | 证据 | 最小修复 |
| ---: | :--- | :--- | :--- |
| 1 | 存在两套"证据强度"定义（生产 Tier vs `rules.py` 死代码） | `rules.py` 仅被 `tests/test_core.py` 引用；`classify_mutation_effect` 0 引用 | 删除 `rules.py`（连同 `EvidenceStrength`、`evidence_record_row` 死代码），只保留 `integration.classify_evidence_tier`；同步删改 `test_core.py` 中对应测试 |
| 2 | `environment_strong_effect` 名称误导（暗示显著性） | `integration.py:132` | 改名并参数化为 `evidence.min_absolute_delta_r2 = 0.01`；motif 侧同步 |
| 3 | `fdr_nominal` 伪参数 | 全仓 0 引用 | 删除 |
| 4 | `ci_crosses_zero_forces_inconclusive` 伪参数 | 配置存在但 `integration.py:53` 硬编码 | 让代码真正读取该配置（默认 True，行为不变） |
| 5 | `strong`（max）与 `overall_effect`（mean）口径不同，输出未标注 | `integration.py:132` vs `:134` | 新增列 `effect_gate_pass` / `statistical_gate_pass` / `strong_evidence_basis`，不改数值 |
| 6 | permutation p/FDR 取该 factor 所有行的 **min**（选择性强） | `integration.py:169-175` | 新增列 `permutation_selection="min over family rows"` 显式留痕；不改数值（避免改变既有结论） |
| 7 | 论文方法把 SNR/FDR 阶梯写成"所有阈值统一配置"；把 effect 门写成"统计/归因强度"；`partial η²` 实为经典 η² | `paper/sections/02_methods.tex:40,48`；`hypothesis_tests.py:331` | 改论文方法段：给出 Tier 的 5 个阈值、说明 SNR/FDR 阶梯只服务 Importance–ΔR² 资产、η² 口径改正；补充表 S1 增加 `min_absolute_delta_r2` 行并注明各阈值归属 |

**保持不变的正确设计**（不做改动）：
- Tier 判定只读 `main_df / cellline_df / bootstrap_ci / permutation`，**不读 ANOVA**；
- 不稳定上下文先剔除、绝不删除原始数据；
- 数据不足一律 `unavailable` + `reason`，不伪造；
- 无 CI 时不阻塞 Tier（`ci_crosses_zero=None` → 该门不生效），但会在输出中保留
  `bootstrap_status/n_bootstrap` 供读者判断（本次仅补充 provenance 列，不改变该行为）。

---

## 6. ANOVA 与 Evidence Tier 的边界（现状核验）

```text
Edge-level evidence:  main_r2_delta (per split/cell/model/seed)
        ↓  per-model mean effect + bootstrap CI + permutation + concordance + cell-line 标签
     Evidence Tier  →  evidence_matrix.csv → Table 3 / Fig.7

Factorial ANOVA:      R² ~ A*B*C*D + C(model)+C(cell_line)+C(split_type)   (Type-II 边际 F)
        ↓
     Global factor / interaction inference → anova_results.csv → Fig.3D / Table 3(anova_F, anova_p)
```

**核验结果**：与上述结构一致。`environment_evidence_matrix` 的签名（`integration.py:90-96`）不含 ANOVA；
`pipeline.py:412-415` 也未把 ANOVA 传入。ANOVA 结果只参与 Fig.3D 与 Table 3 的两列展示。

**准确表述**（替代"宏观/微观"）：

> Edge-level evidence evaluates specific incremental effects (a given factor added on top of a given
> background), whereas factorial ANOVA evaluates the global variation attributable to factors and their
> interactions within the factorial design (response variable = held-out R², blocks = model/cell
> line/split). They answer different questions; reporting "ANOVA not significant" together with
> "factor X reaches Tier 1" is not a contradiction: the former concerns the omnibus factor/interaction
> terms, the latter concerns convergence and robustness of the specific incremental effects.

---

## 7. 是否需要重新计算 Tier（本次实际发生的情形）

| 触发条件 | 实际是否触发 | 说明 |
| :--- | :--- | :--- |
| production rule 被修改 | 否 | 只做参数化/改名/加 provenance 列，分级逻辑与阈值数值不变 |
| aggregation 逻辑变化 | 否 | `per-model mean` / `supporting` / `concordance` 未动 |
| threshold 被修改 | 否 | `min_absolute_delta_r2` 仍为 0.01；`fdr_weak` 仍为 0.05 |
| **FDR / permutation / CI 的输入发生变化** | **是** | `bootstrap_main_effects.csv` 是**修正前**口径的陈旧资产；重跑后 DNase 的跨模型 CI 由 [−0.0046, −0.0001] 变为 [−0.0052, +0.0004]（跨 0） |
| 原 Tier 资产由错误代码生成 | 部分 | 旧 `evidence_matrix.csv` 的 CI 列与论文 Fig.7 的 CI 口径不一致（见 §0 第 8 条） |

**结论与动作**：
1. **不重跑 1 344 次实验**（训练产物与 Tier 无关）；
2. 先做"参数化回归比对"：`scripts/regenerate_evidence_tier_assets.py`（不给 `--write`）验证
   在**旧 CI 输入**下 tier 逐行不变（已通过：环境 4 行 tier 与 coverage/concordance/overall_effect/
   ci_excludes_zero/permutation_fdr 完全一致，max|Δ| = 0）；
3. 再用当前代码完整重跑 evidence 环节（`python -m analysis.pipeline ... --analysis-plan ...`），
   **刷新 `bootstrap_main_effects.csv` 等中间资产并重算 Tier**；
4. 重算后的环境 Tier（2026-09-13 16:44）：

| factor | coverage | concordance | overall ΔR² | CI | CI 跨 0 | perm FDR | effect 门 | 统计门 | **Tier** |
| :--- | ---: | ---: | ---: | :--- | :--- | ---: | :--- | :--- | :--- |
| ctcf | 7 | 0.857 | −0.00095 | [−0.0105, +0.0048] | 是 | 0.0093 | ✅ | ✅ | **Inconclusive** |
| dnase | 7 | 0.714 | −0.00202 | [−0.0052, +0.0004] | **是** | 0.0140 | ❌ | ✅ | **Inconclusive**（原为 Tier 2） |
| h3k4me3 | 7 | 0.857 | −0.00594 | [−0.0129, −0.0010] | 否 | 0.0093 | ✅ | ✅ | **Inconclusive**（`Context-conflicting` 一票否决） |
| rrbs | 7 | 0.857 | −0.00932 | [−0.0242, −0.0010] | 否 | 0.0093 | ✅ | ✅ | **Tier 1** |

   motif 行不受影响：100 Inconclusive / 496 Tier 3（与旧资产一致）。
5. 论文同步（已完成）：`paper/sections/03_results.tex` 观察 1 由"RRBS 与 DNase 分别达到 Tier 1 与 Tier 2"
   改为"仅 RRBS 达到 Tier 1；DNase 因 CI 跨 0 与 CTCF、H3K4me3 同为 Inconclusive"；
   `paper/sections/05_limitations.tex` 的"Tier 1/2"改为"Tier 1"。

## 8. 复现

```bash
python docs/audit/audit_min_absolute_delta_r2.py          # 阈值审计（只读）
python -m unittest analyse.tests.test_evidence_tier_rules -v
python -m analysis.pipeline --batch-dir results/batches/batch_20260909_full \
       --analysis-plan results/batches/batch_20260909_full/analyse_out/analysis_plan.json
```
