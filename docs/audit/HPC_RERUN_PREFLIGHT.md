# HPC 1344 次重跑 — 起飞前自检报告 (Pre-flight Assurance)

生成时间: 2026-09-13
范围: `upload/` 待上传包 + 仓库根目录同一套代码
结论: **READY**（99 项断言全通过；1 项环境警告，见 §6）
本次自检脚本: `deploy/hpc/preflight_hpc_rerun.py`（只读，不训练）

---

## 1. 为什么必须自检：直接重跑会复现 P0 泄漏

审计（`PROJECT_SCIENTIFIC_REPRODUCIBILITY_AUDIT.md` / `issue_register.csv`）已确认：

| Issue | 问题 | 若不修就重跑的后果 |
|---|---|---|
| A1 (P0) | mixed 划分按**行**随机，同一 sgRNA 序列跨 train/test（实测泄漏 36.1%，旧口径 test∩train = 21%） | 448 次 mixed 全部复现泄漏 |
| A2 (P0) | 真 LOCO 的训练池含留出系同源序列（27–51% test 命中训练池） | 448 次 all 全部复现泄漏 |
| L5 | 反向互补近重复未纳入身份 | 残余 revcomp 泄漏（mixed 19 条 / LOCO 3 条） |
| A6 | mixed 的细胞系顺序取自文件系统 readdir 顺序 | 超算与本地划分结果**不可复现** |
| G7/G8 | run 元数据无数据/代码指纹、无 n_train/valid/test | 重跑后无法自证划分与数据一致性 |
| D5 | ΔR² 基线键缺 `random_seed` / `sequence_kernel` | mixed 4 seed、CNN 3 kernel 的基线互相覆盖，ΔR² 系统性错误 |

自检的核心目的：**在提交 1344 次计算之前，用待上传包自身的代码证明划分无泄漏、计划数为 1344、且结果可被验收脚本逐 run 复核。**

---

## 2. 本次落地修复（已同步到 `upload/`）

### 2.1 `core/data/splitting/cell_line_division.py`

1. **group-aware 划分（A1/A2）**
   - 新增 `group_aware_split_indices()`：按 sgRNA 身份整体分配，同一序列不跨 train/valid/test。
   - `divide_data(..., group_aware=True)` 为默认值；`mixed` 与 `all` 均走该路径。
   - **LOCO 训练池剔除留出系全部序列**（`heldout_sequences_excluded_from_train` 记录剔除条数）。
2. **反向互补身份（L5）**
   - `sequence_group_ids(..., revcomp_canonical=True)`：身份 = `min(seq, revcomp(seq))`。
   - 实测库内存在 revcomp 对（hct116 ∩ rc(hela)=30、hela ∩ rc(hl60)=3，系内亦有 12/130/58 条），只按精确序列分组会残留泄漏。
3. **single 也纳入同一契约**
   - `split_single_cell_line(..., group_aware=True)`：三种 split 统一为「同一序列/其反向互补不跨 split」。
4. **划分处自证 + 失败即停**
   - `split_identity_audit()` 在划分完成处计算 train/valid/test 的**原始序列**重叠、locus 重叠、revcomp 重叠，全部写入 run config。
   - `assert_no_sequence_leakage()`：`group_aware=True` 时若出现任何序列重叠 **直接抛错**，不产出泄漏结果。
   - `split_digest`：train/valid/test 序列集合 + 样本数的 sha256 前 16 位，用于事后证明「分析所用划分 == 训练所用划分」。
5. **确定性（A6）**
   - `discover_available_cell_lines()` 返回值 `sorted()`，不再依赖 readdir 顺序。

### 2.2 `workflows/training/data_digging.py`

- `split_type in ("all", "mixed")` 时都显式传 `--cell-lines hct116 hek293t hela hl60`。
  mixed 此前依赖文件系统顺序决定行拼接顺序 → 超算/本地划分漂移；现在两侧完全一致。

### 2.3 `workflows/training/train.py`

- 新增溯源字段（写入 `*_info.txt` 与 `*_config.json`，并自动进入 `analyse.collect_results` 的 `all_experiments.csv`）：
  `data_fingerprint`、`code_fingerprint`、`group_aware`、`split_digest`、`n_train`、`n_valid`、`n_test`、
  `heldout_sequences_excluded_from_train`、`audit_*`（8 项）。
- mixed 的 `cell_line` 显式置 `None`（旧口径），避免新增 `--cell-lines` 后被写成 `cell_lines[0]`。

### 2.4 `src/{cnn,mlp,transformer}`

- config 增加 `device_resolved`，记录该 run 实际跑在 `cpu` 还是 `cuda:N`（超算 CPU/GPU 混跑的异质性可事后识别）。

### 2.5 `analysis/collect_results.py`（D5）

- `calculate_delta_R2` 的基线键由 `(split_type, cell_line, model)` 改为
  `(split_type, cell_line, model, mixed 的 random_seed, cnn 的 sequence_kernel)`，
  与 `data_digging.classify_experiments` 的身份键一致。
- 回归测试：`analysis/tests/test_delta_r2_baseline_pairing.py`（4 例）。

### 2.6 `upload/run.sh`

- 默认 batch 名从 `batch_20260909_full`（旧泄漏批次）改为 **`batch_20260913_groupaware`**。
- 新增**非空即拒绝启动**闸门：若 `results/<batch>` 已存在且非空 → `exit 2`。
  原因：`data_digging` 以「目录存在 + `*info*.txt` + `*metrics*.json`」判定实验已完成并**跳过**，
  复用旧批次名会让新旧（泄漏/无泄漏）结果混在同一批。（Issue A7）

### 2.7 `analysis/leakage.py`（与训练层规则对齐）

- 新增 `canonical_group_key()`，声明 canonical identity = `min(seq, revcomp(seq))`，
  作为**唯一权威定义**；`leakage_mask(group="sequence")` 改用该身份类。
- 训练包必须能独立上传，故不 import `analysis/`，而是镜像同一规则；
  两实现的等价性由 `analysis/tests/test_split_code_parity.py` 强制校验（8 例）。

### 2.8 平台适配与环境自证（G4，新增）

**注意**：`requirements_frozen.txt` 是**开发机审计栈**（torch 2.13.0+**cu130**、glibc 2.39）。
目标超算为 CentOS 7 / **glibc 2.17** / 驱动 **550.54.14（CUDA 12.4）**，两处约束需适配：

1. **torch 必须换 CUDA build**：cu130 轮子需 ≥580 驱动，550 只能跑 **cu124**；
   版本号仍保持 2.13.0（仅 kernel 编译目标不同）。
2. **glibc 2.17 只能用 manylinux2014 轮子**：`manylinux_2_28` 包会报
   `GLIBC_2.28 not found` → 走 conda-forge 最稳。

落地内容：

- 新增 `upload/requirements_hpc.txt`（平台目标栈，`--extra-index-url .../cu124` 置于 torch 之前）
  与 `upload/docs/HPC_ENVIRONMENT_FIT.md`（适配说明 + 报错对照 + 环境声明模板）。
- 自检 P8 改为**两级判定**：与 `requirements_hpc.txt` 不符 → FAIL；
  与开发机审计栈不符 → WARN 并列出差异包；`+cu124` 这类本地 build 标签不算版本不符。
- 每次运行记录 `env_fingerprint`（Python + 9 个包版本 + 绑定设备）
  与 `env_stack_id`（设备无关，用于全批一致性判定）；NN 模型另记 `torch_version`/`torch_cuda_build`。
- 验收脚本新增硬闸门：**全批 `env_stack_id` 必须唯一**；NN 模型 `device_resolved`
  混用 CPU/GPU 直接判 FAIL。
- 新增 `deploy/hpc/compare_env_equivalence.py`：对同名 run 比对两批指标，
  确定性模型阈值 1e-9、随机模型 1e-4，把"环境差异"从假设变成实测数字。

### 2.8b `requirements_frozen.txt`

- 仓库原有 `requirements.txt` 是宽松清单（`numpy<=1.26.4`、`pandas<=2.2.2`、
  `xgboost<=2.0.3`、`torch<=2.3.1`），与产生审计结论的实际数值栈不符。
  超算若按旧清单装包，会在 **xgboost 2.x→3.x、numpy/pandas 大版本** 差异下训练，
  数字不可与本地分析合并。
- 新增 `upload/requirements_frozen.txt` 锁定实际栈：
  python 3.12.3 / numpy 2.5.2 / pandas 3.0.5 / scipy 1.18.0 / scikit-learn 1.9.0 /
  xgboost 3.4.1 / torch 2.13.0 / shap 0.52.0 / joblib 1.5.3 / numba 0.67.0。
- 自检脚本 P8 逐项比对已安装版本与锁定版本，不一致即 FAIL。

---

## 3. 自检证据（`preflight_hpc_rerun.py --package Submit`）

99 项断言，0 失败（含依赖版本锁定）。关键项：

### P1/P2 计划与命名
- 环境组合 = 16（4 个表观特征的全部非空子集 + `sequence`，`all` 合并重复项）。
- `single` = 448、`all` = 448、`mixed` = 448，**总计 1344**，运行名全局唯一。
- CNN：single 192（16×4 细胞系×3 kernel）、mixed 192（16×3 kernel×4 seed）；非 CNN：各 256。
- mixed seed 集合 = {42, 43, 44, 45}。

### P3 数据完整性
- 4 个细胞系 3370–8101 行不等；`X_3d=(n,23,8)`、`X_2d=(n,184)`、`labels`、`metadata` 四者行数一致；无 NaN/Inf。
- 标签范围：hela [0.000,1.000]、hct116/hek293t/hl60 ⊆ [0.028,1.000]，落在 [-1.5,1.5] 内。
- 每个细胞系**系内 sgRNA 序列唯一**（hela 8101/8101、hct116 4239/4239、hek293t 2333/2333、hl60 2076/2076）。

### P4/P5 划分无泄漏（调用待上传包自身的 `divide_data`）

| split | 情形 | n_train / n_valid / n_test | train∩test 序列 | train∩revcomp(test) |
|---|---|---|---|---|
| single | hct116 | 2968 / 635 / 636 | 0 | 0 |
| single | hek293t | 1633 / 345 / 355 | 0 | 0 |
| single | hela | 5669 / 1215 / 1217 | 0 | 0 |
| single | hl60 | 1453 / 311 / 312 | 0 | 0 |
| mixed | seed 42 | 11738 / 2485 / 2526 | 0 | 0 |
| mixed | seed 43 | 11736 / 2514 / 2499 | 0 | 0 |
| mixed | seed 44 | 11709 / 2537 / 2503 | 0 | 0 |
| mixed | seed 45 | 11694 / 2554 / 2501 | 0 | 0 |
| all (LOCO) | held=hct116 | 7003 / 1240 / 4239 | 0 | 0 |
| all (LOCO) | held=hek293t | 12270 / 2144 / 2333 | 0 | 0 |
| all (LOCO) | held=hela | 3707 / 655 / 8101 | 0 | 0 |
| all (LOCO) | held=hl60 | 12313 / 2186 / 2076 | 0 | 0 |

- `all` 的 test 恰为留出系全量；留出系不在训练细胞系列表中；训练池剔除同源序列 4266 / 0 / 4285 / 173 条。

### P6 结果目录
- `results/batch_20260913_groupaware` 不存在 → 全新批次，旧泄漏结果不会被跳过复用。

### P7 溯源字段
- `workflows/training/train.py` / `cell_line_division.py` 均含全部预期字段与断言函数。

**多卡绑定验证**：用桩 `nvidia-smi`（模拟 8 卡）跑 4 个 single 实验，
worker 依次绑定 GPU 0/1/2/3，且 4 个 run 的 `env_stack_id` 完全一致（`eab98539b64ef4ef`）、
仅 `cvd=` 字段不同 —— 证明绑定既生效又不污染"同一套栈"的判定。

### 二阶审计（独立实现交叉验证，`analysis/tests/test_split_code_parity.py`，8 例通过）

用**分析层**（`analysis/leakage.py::classify_overlaps`）复核**训练层**（`divide_data`）实际产出的划分，
两套实现不共用代码路径。12 种划分配置 × 3 个 pair（train|test、train|valid、valid|test）全部为 0：

| 配置 | L2 同观测 | L3 同序列 | L4 同 locus | L5 反向互补 |
|---|---|---|---|---|
| single × 4 系 | 0 | 0 | 0 | 0 |
| mixed × 4 seed | 0 | 0 | 0 | 0 |
| all(LOCO) × 4 留出系 | 0 | 0 | 0 | 0 |

> 修复前的对照：mixed 泄漏 36.1%（含 revcomp 19 条）、LOCO 33.3%（含 revcomp 3 条）。
> 这意味着 A1/A2/A3/A5 在**划分层面**已经归零；剩余验证是重跑后确认落盘结果与该划分一致。

### 端到端最小批（12 run，`single`+`all`+`mixed` 各 4）
- `workflows/training/data_digging.py --models linear --environments sequence_ctcf --split-types single all mixed --workers 4` →
  **success=12, failed=0**；`all` 的 `n_train` = 7003/12270/3707/12313，证明 LOCO 未再退化成 single。
- 重跑 dry-run → `Completed: 12 | Pending: 0`，断点续跑判定正常。
- `analyse.collect_results` 可正常消费新格式（`all_experiments.csv` 含全部溯源列）。
- 收尾复核 `verify_hpc_rerun.py`：`split_digest` 逐 run 与本地重算一致（12/12），fingerprint 全批一致。

---

## 4. 超算执行步骤

```bash
# 0) 上传 upload/ 整个目录（含 data/、src/、scripts/）
cd Submit

# 1) 自检（必须 READY 才继续；约 2–3 分钟）
python deploy/hpc/preflight_hpc_rerun.py --package . --batch-name batch_20260913_groupaware

# 2) 全量重跑（1344 = single 448 + all 448 + mixed 448）
WORKERS=8 bash workflows/training/run.sh                 # 或分三次: bash workflows/training/run.sh single / all / mixed
#   - GPU 节点上 torch 自动用 cuda（无需 --device）
#   - 单卡建议 WORKERS ≤ GPU 数；CNN 显存不足时降到 1–2
#   - 中断后**用同一命令**再跑即断点续跑（已完成的 run 会被跳过）

# 3) 落地验收（必须 PASS 才进入分析）
python deploy/hpc/verify_hpc_rerun.py --package . --batch-name batch_20260913_groupaware

# 4) 打包回传
tar czf batch_20260913_groupaware.tar.gz results/batch_20260913_groupaware
```

> 严禁：把结果写进 `batch_20260909_full`（旧泄漏批次）或任何已存在的非空 batch 目录。

---

## 5. 重跑后的分析步骤（本地）

```bash
python -m analysis.collect_results --batch-name batch_20260913_groupaware
python -m analysis.pipeline --batch-dir results/batch_20260913_groupaware --analysis-plan <plan>
python analysis/reporting/paper/make_assets.py            # Table 2 / Fig.2 等
python analysis/audit/leakage_controlled_recompute.py   # 期望：泄漏比例 = 0（旧批次为 36.1% / 33.3%）
```

- 因为是全新代码口径，**旧 `batch_20260909_full` 的任何数字都不得与新批次混用**；论文/PPT 中所有指标需整体替换。
- 逐 run 的 `split_digest` 与 `n_train/n_valid/n_test` 已随结果落盘，可作为「分析所用划分 == 训练所用划分」的证明。

---

## 6. 已知限制与后续动作（不得静默）

1. **样本量口径变化**（新旧不可逐 run 对比）：
   - mixed train：旧（逐行划分）11724 → 新（group-aware）11694–11738，总量几乎不变；
   - LOCO train：留出 hct116 10633 → 7003、hela 7350 → 3707、hl60 12472 → 12313、hek293t 12253 → 12270（剔除同源序列 4266 / 4285 / 173 / 0 条）。
   因此**跨留出系比较被训练集规模混淆**（hela 留出时 train 仅 3707），论文中必须同时报告 `n_train`。
2. **torch 未见 CUDA（本自检环境）**：本地为 CPU 环境；超算上请确认 GPU 驱动与 `torch.cuda.is_available()`。若部分 run 落 CPU、部分落 GPU，`device_resolved` 会出现两种取值，验收脚本会给出警告；建议同批同设备。
3. **数值发散 run**：ill-conditioned 的 linear/single/hela 已实测出现 `R² ≈ -2.6e18`。分析层按既有规则 `|R²| < 10` 剔除并在表中记录 `n_valid`，该规则不变、不因重跑而调整。
4. **未修（仍开放）**：D2（两处 factor-level CI 实现不统一）、E2（motif `model_consistency` 口径）、G1–G6 数据/文档项。这些不影响 1344 次训练本身的正确性，但会影响后续论文数字，需在分析阶段继续关闭。
5. **`all` 的 test 全量留出系**（8101 行 for hela）意味着 test 集规模在留出系间差异大，R² 的可比性有限——沿用既有口径，不作改动。

---

## 7. 验收标准（重跑完成后逐条核对）

| 编号 | 判据 | 结果 |
|---|---|---|
| V1 | 1344 个 run 目录，`single/all/mixed` 各 448，身份无重复 | `verify_hpc_rerun.py` |
| V2 | 每个 run 有 `*_info.txt` + `*_metrics.json` | 同上 |
| V3 | 每个 run `audit_train_test_sequence_overlap = 0` 且 `audit_train_test_revcomp_overlap = 0` | 同上 |
| V4 | 每个 run `group_aware = True` | 同上 |
| V5 | 全批 `data_fingerprint` / `code_fingerprint` 各只有 1 种取值 | 同上 |
| V6 | 每个 run 的 `split_digest`、`n_train/n_valid/n_test` 与本地重算一致 | 同上 |
| V7 | 发散 run（`|R²| ≥ 10`）被列出并在分析中剔除 | 同上（警告区） |
| V8 | 重新计算的泄漏比例为 0 | `analysis/audit/leakage_controlled_recompute.py` |
| V9 | 全批 `device_resolved` 唯一（不混 CPU/GPU 节点） | `verify_hpc_rerun.py`（警告区） |
| V10 | 训练环境与 `requirements_frozen.txt` 一致 | `preflight_hpc_rerun.py` P8 |
