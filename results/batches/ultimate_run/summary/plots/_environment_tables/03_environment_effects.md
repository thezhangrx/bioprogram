# 03 Environment Effects

<!-- FACTORIAL_DAG_SECTION -->
## 2^4 Environment Factorial DAG

### Factorial design
- 环境因子 4 个 (CTCF, DNase, H3K4me3, RRBS) -> 理论组合 2^4 = 16 nodes
- 理论有向边 (单因素增加关系) = 4 × 2^(4-1) = 32
- 本批观测: 有效 nodes 994 / 16 × groups; 有效 edges 1978; METRIC_INCONSISTENCY edges 0; 有 CI 的 edges 0
- batch: `ultimate_run`

### 定义
| 元素 | 含义 |
| :--- | :--- |
| Node | 一个 environment combination (sequence-only 为 level 0) |
| Directed edge | 从 S 增加一个新环境 e: S → S ∪ {e} |
| Edge value | conditional incremental effect ΔR²_{e\|S} = R²(S∪{e}) − R²(S) |
| Primary metric | ΔR² (方向 = effect direction, **不是** statistical significance) |
| Uncertainty | bootstrap CI (存在才展示; 本批未接通则保持 NaN) |

### 为什么一个组合可以有多个父节点
该 DAG 保留**不同环境添加顺序**产生的条件增量, 因此同一个 combination 可以有多个父节点:
`CTCF → CTCF+DNase` (即 ΔR²_{DNase|CTCF}) 与 `DNase → CTCF+DNase` (即 ΔR²_{CTCF|DNase})
都是合法边且必须同时存在。这正是 factorial design 的 context-dependent conditional effect,
严格树结构无法表达 (树要求每个节点只有一个父节点)。

### 缺失 / 异常处理
- 组合缺失 -> `node.status = unavailable` (节点保留在理论结构中, 不删除);
- 单实验发散/缺失/相关越界 -> 从均值与配对中排除, 计入 `n_invalid`, 并写 warning;
- ΔR² 与 ΔRMSE 同向 (同一 paired cohort) -> 边标记 `METRIC_INCONSISTENCY`, **边仍然保留**;
- CI 未接通时保持 NaN, 绝不伪造。

### 两个视图必须区分命名
| 视图 | 方向 | 定义 | 回答的问题 |
| :--- | :--- | :--- | :--- |
| Additive view (本 DAG) | sequence → ALL | ΔR²_{e\|S} = R²(S+e) − R²(S) | 增加一个环境因子带来多少提升 |
| Ablation view (辅助) | ALL → sequence | ΔR²_ablation = R²(S) − R²(S∖e) | 移除一个环境因子损失多少 |

> 两者是不同的科学量, 不共用 "environment contribution" 这一名称。

### 本批完整性 (每 group)

| split | cell_line | model | nodes(ok/theory) | edges(valid/theory) | inconsistency | invalid exp | unavailable combos |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| all | hct116 | cnn(3|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hct116 | cnn(5|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hct116 | cnn(7|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hct116 | linear | 8/16 | 12/32 | 0 | 8 | sequence_dnase, sequence_ctcf_dnase, sequence_dnase_h3k4me3, sequence_dnase_rrbs, sequence_ctcf_dnase_h3k4me3, sequence_ |
| all | hct116 | mlp | 16/16 | 32/32 | 0 | 0 |  |
| all | hct116 | transformer | 16/16 | 32/32 | 0 | 0 |  |
| all | hct116 | xgboost | 16/16 | 32/32 | 0 | 0 |  |
| all | hek293t | cnn(3|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hek293t | cnn(5|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hek293t | cnn(7|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hek293t | linear | 16/16 | 32/32 | 0 | 0 |  |
| all | hek293t | mlp | 16/16 | 32/32 | 0 | 0 |  |
| all | hek293t | transformer | 16/16 | 32/32 | 0 | 0 |  |
| all | hek293t | xgboost | 16/16 | 32/32 | 0 | 0 |  |
| all | hela | cnn(3|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hela | cnn(5|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hela | cnn(7|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hela | linear | 16/16 | 32/32 | 0 | 0 |  |
| all | hela | mlp | 16/16 | 32/32 | 0 | 0 |  |
| all | hela | transformer | 16/16 | 32/32 | 0 | 0 |  |
| all | hela | xgboost | 16/16 | 32/32 | 0 | 0 |  |
| all | hl60 | cnn(3|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hl60 | cnn(5|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hl60 | cnn(7|3) | 16/16 | 32/32 | 0 | 0 |  |
| all | hl60 | linear | 16/16 | 32/32 | 0 | 0 |  |
| all | hl60 | mlp | 16/16 | 32/32 | 0 | 0 |  |
| all | hl60 | transformer | 16/16 | 32/32 | 0 | 0 |  |
| all | hl60 | xgboost | 16/16 | 32/32 | 0 | 0 |  |
| mixed | none | cnn(3|3) | 16/16 | 32/32 | 0 | 0 |  |
| mixed | none | cnn(5|3) | 16/16 | 32/32 | 0 | 0 |  |
| mixed | none | cnn(7|3) | 16/16 | 32/32 | 0 | 0 |  |
| mixed | none | linear | 16/16 | 32/32 | 0 | 6 |  |
| mixed | none | mlp | 16/16 | 32/32 | 0 | 0 |  |
| mixed | none | transformer | 16/16 | 32/32 | 0 | 0 |  |
| mixed | none | xgboost | 16/16 | 32/32 | 0 | 0 |  |
| single | hct116 | cnn(3|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hct116 | cnn(5|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hct116 | cnn(7|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hct116 | linear | 16/16 | 32/32 | 0 | 0 |  |
| single | hct116 | mlp | 16/16 | 32/32 | 0 | 0 |  |
| single | hct116 | transformer | 16/16 | 32/32 | 0 | 0 |  |
| single | hct116 | xgboost | 16/16 | 32/32 | 0 | 0 |  |
| single | hek293t | cnn(3|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hek293t | cnn(5|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hek293t | cnn(7|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hek293t | linear | 16/16 | 32/32 | 0 | 0 |  |
| single | hek293t | mlp | 16/16 | 32/32 | 0 | 0 |  |
| single | hek293t | transformer | 16/16 | 32/32 | 0 | 0 |  |
| single | hek293t | xgboost | 16/16 | 32/32 | 0 | 0 |  |
| single | hela | cnn(3|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hela | cnn(5|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hela | cnn(7|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hela | linear | 16/16 | 32/32 | 0 | 0 |  |
| single | hela | mlp | 16/16 | 32/32 | 0 | 0 |  |
| single | hela | transformer | 16/16 | 32/32 | 0 | 0 |  |
| single | hela | xgboost | 16/16 | 32/32 | 0 | 0 |  |
| single | hl60 | cnn(3|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hl60 | cnn(5|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hl60 | cnn(7|3) | 16/16 | 32/32 | 0 | 0 |  |
| single | hl60 | linear | 10/16 | 14/32 | 0 | 6 | sequence_h3k4me3, sequence_dnase_h3k4me3, sequence_ctcf_dnase_h3k4me3, sequence_ctcf_h3k4me3_rrbs, sequence_dnase_h3k4me |
| single | hl60 | mlp | 16/16 | 32/32 | 0 | 0 |  |
| single | hl60 | transformer | 16/16 | 32/32 | 0 | 0 |  |
| single | hl60 | xgboost | 16/16 | 32/32 | 0 | 0 |  |
