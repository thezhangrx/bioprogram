# 超算环境兼容性实测报告 —— 能不能跑？

日期：2026-09-14
被检对象：`upload/` 训练包（1344 次实验）
被检环境：按你给的超算版本**真实复刻**的 Python 3.10 环境

---

## 0. 结论

**能跑。** 五个模型（linear / xgboost / mlp / transformer / cnn）全部训练成功，
三种 split（single / all(LOCO) / mixed）12 次实验 12 次成功，**没有任何 API 不兼容报错**。

但"轻微数值偏移"这一条**不完全成立**，实测偏移量如下（见 §3）：确定性与线性模型在 1e-4~1e-3，
神经网络在 3e-3~1.2e-2。这个量级对"批内比较"无害，但**不得与旧环境跑出的数字混用**，
且 MLP 的 1.2e-2 已经超过证据分级 `effect_gate` 使用的 0.01 阈值（见 §4 第 3 条）。

---

## 1. 复刻方式（不是猜，是真跑）

沙箱里有 `/usr/bin/python3.10`，所以直接复刻了你的栈：

```bash
/usr/bin/python3.10 -m venv /tmp/hpcenv
pip install numpy==2.2.6 scipy==1.15.2 scikit-learn==1.7.2 pandas==2.2.3 \
            xgboost==2.1.4 shap==0.46.0 matplotlib==3.9.4 seaborn==0.13.2 tabulate==0.9.0
pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu   # 无显卡, 用 CPU 轮子测 API
```

复刻后的版本（与你的表对齐）：

| 包 | 你的超算 | 我复刻用的 | 备注 |
|---|---|---|---|
| Python | 3.10.21 | 3.10.20 | 一致 |
| NumPy | 2.2.6 | 2.2.6 | 一致 |
| SciPy | 1.15.2 | 1.15.2 | 一致 |
| scikit-learn | 1.7.2 | 1.7.2 | 一致 |
| PyTorch | 2.6.0+cu124 | 2.6.0+**cpu** | 版本一致；CUDA build 换成 cpu 是为了在无卡机器上测 **API 兼容性**（数值结果另有说明） |
| CUDA | 12.4 | — | 不适用 |
| Matplotlib | 3.9.4 | 3.9.4 | 一致 |
| XGBoost | 未确认 | 2.1.4 | 实测可用 |
| pandas | 未给出 | 2.2.3 | 实测可用（开发机为 3.0.5） |
| SHAP | 未确认 | 0.46.0 | 实测可用 |

然后**直接跑你的 `upload/` 包**（不是简化版）。

---

## 2. 跑通了什么（实测输出）

```
########## 1. 逐模型冒烟: single(hl60) ##########
linear       [✓] Finished Successfully
xgboost      [✓] Finished Successfully
mlp          [✓] Finished Successfully
transformer  [✓] Finished Successfully
cnn          [✓] Finished Successfully

########## 2. 三种 split (linear) ##########
[✓] Batch executed: success=12, failed=0
```

五个模型都走完了完整链路：数据加载 → 环境通道选择 → 训练 → 早停 → test 评估 →
XAI（linear 系数 / xgboost 原生 TreeSHAP / mlp+transformer 的 IG / cnn 的 ISM+IG）→ 落盘。

另外，自检脚本在复刻环境里跑出 **READY**：

```
[PASS] HPC 目标栈(requirements_hpc.txt): 4 个锁定版本全部匹配
[WARN] 与开发机审计栈存在版本差异: numpy 2.2.6 != 2.5.2; ... (平台约束, 已在 §3 量化)
结论: READY —— 可以提交 HPC 重跑
```

---

## 3. 数值偏移实测（这是"轻微"到底多轻微）

### 3.1 划分与数据：**完全不受影响**

同配置下两套环境的 `split_digest`（train/valid/test 序列集合的 sha256）**逐一相同**：

| 配置 | 开发机 | 超算栈 | n_train |
|---|---|---|---|
| single hct116 | `3ff84988cab5900c` | `3ff84988cab5900c` | 2968 |
| mixed seed42 | `a5e7933d539d4faf` | `a5e7933d539d4faf` | 11738 |
| LOCO held=hct116 | `a08287ce23c0a882` | `a08287ce23c0a882` | 7003 |
| LOCO held=hela | `63c43a369c73b943` | `63c43a369c73b943` | 3707 |

**含义**：无泄漏划分与样本量完全由代码和随机种子决定，与 numpy/pandas 版本无关。
"重跑后泄漏为 0"这一核心结论不受环境影响。

### 3.2 指标：不同模型差异量级不同

同配置（single / hl60 / sequence_ctcf）、同随机种子、同设备类型（都是 CPU）：

| 模型 | 训练设置 | \|ΔR²\| | \|ΔMAE\| | 说明 |
|---|---|---|---|---|
| linear | 解析解 | 5.5e-04 | 4.7e-05 | LAPACK 版本差异 |
| xgboost | 早停 | 1.3e-03 | 6.7e-04 | 直方图分箱/并行归约差异 |
| cnn | 早停@epoch25 | **2.8e-03** | 5.8e-04 | 与开发机同轮数收敛 |
| mlp | 早停@epoch7 | **1.2e-02** | 3.4e-04 | 与开发机同轮数收敛 |
| transformer | 3 epoch 初测 | 2.0e-02 | 2.2e-03 | 未充分收敛, 仅说明可跑 |

补充：12 次 linear 批（3 种 split）的偏移在 7.7e-07 ~ 8.3e-05，比 single 更小。

---

## 4. 结论怎么用（三条硬规则）

1. **1344 次必须全部在同一环境跑完**。批内所有比较（ΔR²、bootstrap、置换、证据分级）
   都是同一套数值栈内部的自洽比较 → 结论有效。每个 run 的 `*_info.txt` 都记录了
   `env_stack_id`，验收脚本 `verify_hpc_rerun.py` 会强制全批一致。

2. **不得与新环境外的任何旧数字合并**。旧 `batch_20260909_full`（开发机栈 + 旧泄漏划分）
   已标记废弃；新批次整体替换论文/PPT 中的全部指标。

3. **注意 MLP 的偏移与证据门槛同量级**。证据分级的效果门槛是 `|ΔR²| ≥ 0.01`，
   而 MLP 的跨环境漂移实测 1.2e-2 > 0.01。这意味着"某个 MLP 配置的 Tier 判定"
   在不同环境之间**可能翻转**。处理办法（二选一）：
   - 论文只报告 HPC 批次的数字，并写明环境指纹（推荐）；
   - 或不要在 MLP 上做"刚好卡在 0.01 附近"的强声明。

4. **同一批次不要混 CPU/GPU**。GPU 与 CPU 的差异比版本差异更大；
   `device_resolved` 混用会被验收脚本判 FAIL。你的 8×A100 节点上会全部走 CUDA。

---

## 5. 你还需要确认的两个包（否则会掉 run）

| 包 | 缺失后果 | 确认命令 |
|---|---|---|
| **xgboost** | **256 个 xgboost run 全部失败** | `python -c "import xgboost;print(xgboost.__version__)"` |
| ~~shap~~ | **已不需要**：2026-09-14 已将 MLP 的 SHAP 类归因整体移除，代码不再引用 shap | 无需安装 |
| pandas | 全部 run 失败 | `python -c "import pandas;print(pandas.__version__)"` |

实测：xgboost **2.1.4** 与 shap **0.46.0** 都可用。注意 xgboost 代码用的是
`booster.predict(dmat, pred_contribs=True)` 原生 TreeSHAP，**不依赖 shap 包**。

---

## 6. 跑完后如何验证环境差异（把上面的偏移落到你自己的批次上）

```bash
# A) 超算: 跑一批分层抽样参考实验（与开发机同名同配置）
cd upload && python workflows/training/data_digging.py --batch-name env_check --split-types single all mixed \
    --models linear xgboost mlp cnn --environments sequence sequence_ctcf --workers 8
tar czf env_check.tar.gz results/env_check

# B) 开发机: 用同一命令跑 local_env_check（把 batch 名改掉）

# C) 比对（阈值: 确定性模型 1e-9, 随机模型 1e-4）
python deploy/hpc/compare_env_equivalence.py \
  --reference results/local_env_check --candidate results/env_check \
  --out results/tables/audit/env_equivalence
```

输出会给出逐 run 的 |ΔR²| 与最大偏离，直接写进论文的环境声明。

---

## 7. 本次实测**没有**覆盖的部分（据实声明）

1. **GPU 路径未实测**：沙箱无显卡，torch 用的是 cpu 轮子。GPU 上的算子差异属于额外偏移，
   但批内自洽性不受影响。上机后自检脚本会打印 `cuda_available=True` 与卡数。
2. **未跑满 1344 次**：只做了 5 个模型 + 12 次 split 批（覆盖全部代码路径，未覆盖全部组合）。
3. **分析层未在 3.10/pandas 2.2 下测**：分析（`analysis/`）在开发机跑，用 pandas 3.0.5，不受影响。
4. **transformer 的漂移数字来自 3 epoch 初测**，仅用于证明"能跑"，不代表收敛后的真实偏移。
