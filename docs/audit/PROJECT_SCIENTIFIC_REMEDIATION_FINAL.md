# 项目级科研有效性整改报告（Scientific Validity Remediation — Final）

> 基线：`docs/audit/issue_register.csv`（P0 4 / P1 15 / P2 9 / P3 1；Confirmed 26 / Likely 2 / 0 Possible）
> 本报告记录**已执行**的整改、**验证证据**、**二次审计发现**与**仍未关闭项**。整改全程：未删除数据、未调阈值、未重训模型、未覆盖任何旧资产。

---

## Part 1 — Executive Summary

| 维度 | 整改前 | 整改后 |
| :--- | :--- | :--- |
| P0（可使结论失效） | 4 open | **A4 已闭环（FIXED_AND_VERIFIED）**；A1/A2 **评估层已重算并验证**，训练层重跑仍待执行；A3 转为 DOCUMENTED_LIMITATION |
| P1（改变某类科学结论） | 15 open | **5 FIXED_AND_VERIFIED**（D4 / D6 / F1 / F2 + A4），**9 DOCUMENTED_LIMITATION**，**1 OPEN**（D2；E2 亦待修） |
| P2/P3 | 10 open | 全部 **DOCUMENTED_LIMITATION / OPEN**（本轮未处理；不影响核心结论，但影响复现声明） |
| 测试 | 200 项 | **213 项全绿**（新增 identity/leakage 10 项 + LOCO 回归 3 项） |

**二次审计（第二十一节要求）已执行**：整改本身引入 1 个新问题（`loco_performance` 列名变更导致论文 Fig.2 构建 KeyError）→ **当场发现并修复**（`make_assets` 改用 `R2_median`），`paper/make_assets.py` 重新跑通。

### 最终判定

```text
PROJECT SCIENTIFIC READINESS: REQUIRES FURTHER RECOMPUTATION
```

理由（严格对照第 20 节标准）：
* P0 = 0 open **尚未满足**：A1/A2 的**评估层**已重算验证，但模型本身仍在含孪生行的池上训练 → 需要 group-aware 重跑 448 mixed + 448 all；
* P1 仍有 1 项 OPEN（D2 两套 CI）+ E2 待修；
* 已满足的部分：A4 闭环、D4/D6/F1/F2 修复并验证、论文 Table 2/Fig.2 与 canonical 数据一致、identity/leakage policy 有唯一权威实现与测试。

---

## Part 2 — Before → After（逐 issue）

| Issue | Before | Action | Recomputed? | After | Scientific impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A1** mixed 孪生行泄漏 | test∩train 21–21.5 %；泄漏子集 R² 0.381/0.690/0.560 | 新增 `analysis/leakage.py`（canonical identity：sequence / observation / locus；`leakage_mask`；`group_aware_split`）+ 对全部 448 mixed run 重算 **leakage-controlled 指标**（新资产，不覆盖旧值） | ✅ 评估层 | mixed 中位 R² **0.127 → 0.047**；泄漏比例 36.1 %；按模型：cnn 0.138→0.016、linear 0.086→0.055、mlp 0.117→0.047、transformer 0.121→0.069、xgboost 0.167→0.080 | mixed 性能与增量效应须用新口径；"mixed 优于 single"不再成立 |
| **A2** LOCO 同源泄漏 | hold-out 系 27–51 % test 命中训练池 | 同一 policy 对 448 all run 重算（`group="sequence"`） | ✅ 评估层 | LOCO 中位 R² **0.0878 → 0.0215**；泄漏 33.3 %；mlp 0.096→**−0.066**、xgboost 0.146→0.015 | 真实跨细胞系泛化远弱于此前报告 |
| **A3** single locus/revcomp 孪生 | HEK293T 21/350、HeLa 7/1215 | 提供 `locus_key` / `revcomp` / `classify_overlaps`（L1–L6 六类计数）；论文只允许声称 sample + sequence 级 | 分类入库 | L4/L5 计数进入 `leakage_overlap_audit.csv` | locus 级泛化**不得**声称 |
| **A4** LOCO 历史退化 | all ≡ single 448/448 | 合并 448 真 LOCO；新增 `analysis/tests/test_loco_regression.py`（all≠single、held-out 不在训练细胞系、seed 不跨配） | ✅ | all vs single **0/448** 相同；回归测试常驻 | 跨细胞系泛化重新可用（但受 A2 限制） |
| **D4** 边表重复 | 2 651 行 vs 唯一 2 016 | `make_assets` 按 canonical experiment key 去重 `environment_bootstrap`/`edges` | ✅ | 分母回落至 canonical 唯一键（ctcf 485 edges 等，随 LOCO 数据更新） | 论文边级分母不再被放大 |
| **D6** loco_performance 未滤发散 | max\|R²\| = 2.85×10¹⁹ | `analysis/prediction.py::loco_performance` 接入 `unstable_effect_threshold`（10.0），输出 mean/median/n_valid | ✅ | max\|R²\| = **0.945**；新增 `n_valid` 列 | Fig.2C 不再出现垃圾值 |
| **F1** 位置热图 parser | 1-based 源被再 +1 → 位置 2..23（缺 1） | 在 `analysis/visualization.py` 内联 canonical 规则（`pos12_A`→12；`A_pos_12`→13） | ✅ 解析验证 | `A_pos_0→1`、`T_pos_17→18`、`G_pos_22→23`、`pos1_A→1` | 热图与 attribution 表位置一致（图待重绘） |
| **F2** Table 2 口径 | median≡mean、SD=NA、diverged=1、linear=−1.87e16 | 改为从 canonical `experiment_table.csv` 聚合：n / n_valid / median / mean / SD / diverged | ✅ | 例：linear single n=64/n_valid=43/median 0.087/diverged 21；xgb mixed 0.161 | 论文性能表与真实实验一致 |
| **C2/D3/D1/E1/E3/B1/B2/C1** | — | 登记为 DOCUMENTED_LIMITATION（含量化证据与限定措辞） | 部分 | 见 `issue_register_final.csv` | 需按限定措辞书写 |
| **D2/E2/G1–G8/H1/H2** | — | 未处理 | — | OPEN | 见下节 |

---

## Part 3 — 交付的代码/资产变更

| 类型 | 文件 | 说明 |
| :--- | :--- | :--- |
| 新增（权威实现） | `analysis/leakage.py` | canonical identity（sequence / observation / locus）、重叠分类学（L2–L5）、`leakage_mask`、`group_aware_split` |
| 新增（测试） | `analysis/tests/test_leakage_identity.py`（10 项）、`analysis/tests/test_loco_regression.py`（3 项） | 覆盖 A1/A2/A3/A4 + D5 守卫雏形 |
| 新增（重算脚本） | `analysis/audit/leakage_controlled_recompute.py` | 对 896 个 mixed/all run 做 leakage-controlled 评估（不训练） |
| 新增（资产） | `results/analysis/leakage_controlled_metrics.csv`、`docs/audit/leakage_controlled_recompute.md`、`docs/audit/feature_integrity_audit.csv`、`split_integrity_audit.csv`、`leakage_overlap_audit.csv`、`statistical_unit_audit.csv`、`environment_reproducibility_audit.csv`、`dataset_routing_audit.csv`、`experiment_identity_audit.csv` | 审计与重算产物（旧资产保留） |
| 修改 | `analysis/prediction.py`（D6）、`analysis/visualization.py`（F1）、`paper/make_assets.py`（D4/F2 + Fig.2 适配） | 均为最小改动 |
| 重生成 | `tables/loco_performance.csv`、`paper/tables/tab2_prediction.tex`、`docs/paper/figures/fig2_prediction.pdf`、`docs/paper_analysis/bootstrap_edge_by_factor.csv` | 与 canonical 口径一致 |

---

## Part 4 — 二次审计（regression audit）发现

| # | 新问题 | 证据 | 处置 |
| ---: | :--- | :--- | :--- |
| S1 | D6 改动重命名 `loco_performance` 列（`R2`→`R2_mean/R2_median`），`paper/make_assets.py:95` 仍读 `loco["R2"]` → `KeyError: 'R2'` | 复现：`python paper/make_assets.py` 报 KeyError | **当场修复**（改用 `R2_median` 并加注释），重新构建通过 |
| S2 | Table 2 现新增 `all`(LOCO) 行，而论文正文/表注此前只描述 single/mixed | `paper/tables/tab2_prediction.tex` 现含 all 行 | 论文文本需同步（已登记） |
| S3 | motif 资产随 LOCO 数据重算而变化（候选 596→615、FDR<0.05 64→71） | `summary/asset_summary.json` | 论文 §3.6 数字需同步（已登记） |
| S4 | `bootstrap_edge_by_factor` 分母随去重与 LOCO 数据同时变化（474→485 edges） | `docs/paper_analysis/bootstrap_edge_by_factor.csv` | 论文 §3.3 分母需同步（已登记） |

---

## Part 5 — 仍未关闭（按优先级与最小必要路径）

```text
P0（唯一剩余）：group-aware 重训
  1) 用 analyse.leakage.group_aware_split(sgRNA) 重建 mixed 划分 → 重跑 448 mixed（如需 GPU，见 upload/ 包）
     all 划分：训练池需剔除 hold-out 系的全部 sgRNA 后再训 448 all
  2) 之后重跑：collect_results → analyse.pipeline → make_assets
  3) 用同一脚本重算 leakage-controlled 指标，确认泄漏比例 = 0
P1：
  D2 统一 factor-level CI（保留 stats/tasks.py 一套）→ 重生成 Table 3 / Fig.7
  E2 修 motif model_consistency 口径（kernel 变体 ≤3）→ 重算 motif 标签
  D5 修 collect_results 基线 seed 键
P2/P3：G1–G8、H1、H2（复现声明、provenance、QC 补全、文档同步）
```

**当前可报告的边界**（未完成 P0 重训前）：

* **SAFE TO REPORT**：数据规模/组成/PAM；single 域内性能（Table 2 已修）；位置 18 的模型行为；kernel 比较的**方向**（标注 fixed-split）。
* **REPORT WITH CAVEAT**：环境因子结论（含 DNase 常数通道限制）；motif 候选（HeLa-only）；Model-Level Bootstrap（n=7）。
* **REQUIRES RECOMPUTATION**：mixed 与 LOCO 的绝对性能与增量效应（本文档已给出 leakage-controlled 版本作为临时口径）。
* **MUST NOT BE CLAIMED**：AI 设计新候选（6.2 % 训练池重叠）；因果/机制；SOTA 性能；独立验证。

---

## Part 6 — 复现命令（本次整改）

```bash
python -m unittest analyse.tests.test_leakage_identity -v      # 10 项 identity/leakage
python -m unittest analyse.tests.test_loco_regression -v       # 3 项 LOCO 守卫
python -m unittest discover -s analysis/tests -t . -p "test_*.py"   # 213 项
python analysis/audit/leakage_controlled_recompute.py                 # P0 评估层重算（不训练）
python paper/make_assets.py                                    # D4/F2/Fig.2 重生成
python docs/audit/audit_factor_level_permutation.py            # D1 口径审计
```
