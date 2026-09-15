# 训练/批量执行性能优化报告 (10 阶段进度台账)

> 约束红线全程遵守：不改模型结构/激活/损失/输入输出；不改 Linear/XGBoost/MLP/CNN/Transformer
> 建模思想；CNN 双分支不变、seq kernel∈{3,5,7}、env kernel=3；16 组合与 single/all/mixed 4-seed
> 设计不变；不删实验/不改 epoch/early stopping/seed/划分/指标；不改小模型规模/特征/样本。
> “可能改变数值结果”的优化默认不实施，仅提供显式开关并说明。
> 测量机：12 核 CPU（无 GPU），Python 3.12；数据 hct116（train≈2967/valid≈635/test≈637）。

## 阶段总览

| 阶段 | 内容 | 结果 |
|---|---|---|
| Phase 1 | 分段 Profiling | 见下；瓶颈 = ①每实验 python 启动/import ②DL 解释(CNN ISM/IG) |
| Phase 2 | 数据读取/预处理 | 已极低(load/split/env_prep<0.08s/实验)，保持现状 |
| Phase 4 | DataLoader | num_workers=0 最优(全内存 TensorDataset)；不改 batch |
| Phase 6 | 文件 IO | 已“实验结束一次性落盘”(7 文件 50–94KB)；保持现状 |
| Phase 8 | 实验并行 | 子进程并发 `--workers N`(无封顶逐位一致，但本机 oversubscribe) |
| Phase 8b | 进程内调度 | `--in-process`：省每实验 python 启动/import，与子进程逐位一致 |
| Phase 9 | 线程控制 | `--threads-per-worker T` 显式开关；默认关(会致线性 ~1e-4 漂移) |
| Phase 10 | 回归 | 抽样 5 模型族 ×(sequence/all) 与子进程 Δ=0 |

## Phase 1 分段耗时 (单实验, hct116, env=all, 秒)

| 阶段 | linear | xgboost | MLP(2ep) | CNN(2ep) | Transformer(2ep) |
|---|---|---|---|---|---|
| load | 0.012 | 0.008 | 0.013 | 0.010 | 0.014 |
| split | 0.018 | 0.012 | 0.020 | 0.016 | 0.020 |
| env_prep(16 组合合计) | 0.027 | 0.024 | 0.023 | 0.019 | 0.023 |
| train(净) | 0.521¹ | 0.201 | 1.255 | 2.886 | 4.284 |
| explanation(XAI) | —(fit 内) | 0.026 | 0.257 | **12.539** | 0.061 |
| 合计(测量) | ~0.59 | ~0.28 | ~1.6 | ~15.5 | ~4.4 |

¹含解析统计推断。固定开销：每实验子进程启动/import ≈1.5s(linear) ~2.6–3s(DL)。

## 阶段结论与代码开关

1. **`workflows/prediction/predict.py`**：
   - `--workers N`：并发执行独立的 workflows/training/train.py 子进程（默认 1=原串行，行为不变）。
   - `--in-process`：进程内顺序执行（复用解释器与已 import 模块；需与 workers=1 同用）。
   - `--threads-per-worker T`：并发时对子进程封顶 OMP/MKL/OpenBLAS 线程；默认 0=不封顶。
2. **`workflows/training/train.py`**：抽出 `execute_args(args)`，`main()` 仅做解析转发（供进程内调度复用同一代码路径）。
3. **`profile_experiment.py`**：可复跑的分段 profiling 工具（含 DL 解释阶段计时）。

## 基准数据

| 模式 | 6 实验墙钟(本轮同测) | 与串行子进程结果差 |
|---|---|---|
| 串行子进程(workers=1) | 47.9s(受本机负载波动, 另次 15.5s) | — |
| `--in-process` | 22.1s | **Δ=0（逐位一致）** |
| `--workers 4`(无封顶) | 76.4s(oversubscription) | Δ=0（逐位一致） |
| `--workers 4 --threads-per-worker 3` | 6.4s | xgb Δ=0；mlp≈3e-8；**linear≈1e-4(病态 all 可放大)** |

回归覆盖：linear/xgboost/mlp×sequence/all + cnn(k3)/transformer×sequence，子进程 vs 进程内均 **Δ=0**。

## 风险与后续（需用户决策/环境）
- 线程封顶能带来 2.4–3.1× 并发加速，但改变线性 BLAS 归约顺序 → 默认不实施；
  若接受 ~1e-4 线性漂移（xgb/mlp 几乎不受影响）再全局开启。
- CNN ISM/IG 向量化可再省 ~10s+/实验，同样属“可能改浮点”项，默认不实施。
- GPU 机器上应重跑 profiling：DL 训练将更快，启动/import 与调度占比更大。
- 全量 1344 实验最终回归（含全部 env/kernel/seed）可在此基础上执行。

最后更新：Round-2 完成 Phase-8b(进程内调度) 与抽样 Phase-10 回归。

---

## Round-3 增补
- 新增 `regression_compare.py`：可复跑回归工具（`--quick` 6 实验；`--extended` 增 CNN k3/5/7 + Transformer）。
- 扩展回归实测（11 实验：linear/xgb/mlp×seq,all + cnn k3/5/7×seq + transformer×seq,all, epochs=1）：
  子进程串行 81.5s vs `--in-process` 38.4s（≈2.1×，负载波动下）；metric max |Δ| = 0（**PASS 逐位一致**）。
- 前次 6 实验快速回归：38.3s vs 9.1s（≈4.2×），Δ=0。

---

## Round-4 (GPU Profiling 请求) 结论
- **本执行环境无 GPU**（torch CPU 版、`torch.cuda.is_available()=False`、无 nvidia-smi）。
  真实 GPU 分阶段 profiling 需在用户 GPU 机执行：
  `python profile_experiment.py --all-models --epochs 2 --device cuda`（已在工具中实现 GPU 可用性守卫）。
- **CPU 分阶段实测**（hct116, env=all, epochs=2, 12 线程默认）：

| 阶段 | linear | xgboost | MLP | CNN(k3) | Transformer |
|---|---|---|---|---|---|
| load+split | 0.041 | 0.022 | 0.020 | 0.017 | 0.015 |
| env_prep_16 | 0.027 | 0.027 | 0.017 | 0.018 | 0.017 |
| train(净/2ep) | 0.090 | 0.143 | ~1.24 | 0.565 | ~1.98 |
| validation | —(fit内) | — | 0.009 | 0.064 | 0.081 |
| test eval | 0.002 | 0.001 | ~0.000 | 0.025 | 0.022 |
| explanation | — | 0.024 | 0.235 | **4.777** | 0.032 |
| save | 0.007 | 0.008 | 0.007 | 0.008 | 0.008 |
| 合计 | 0.166 | 0.224 | 1.78 | 10.9 | 2.30 |

- **CPU 线程对 XGBoost 训练**（300 树/3000×161）：1→5.46s, 2→3.32s, 4→2.24s, 6→2.08s, 12→2.01s（收益递减；该模型封顶不改数值）。
- **1344 实验理论总耗时（CPU 估计，显式假设）**：≈14.7h（linear 33s + xgb 42s + MLP 3.4h + CNN 5.8h + Transformer 5.5h；100 epochs 无早停、hct116 量级、静默机）。含早停典型 30–60% 削减 → 约 6–10h 区间；另每实验启动/import ~1.5–3s（进程内可省，对 GPU 机更重要）。GPU 数字需用户机复测。
- **瓶颈判定（CPU）**：DL 训练 epochs 主导（MLP/Transformer/CNN 全量）；CNN 短 epoch 时 explanation(ISM/IG) 占比显著（2ep 时 ~44%）；linear/xgb 主要开销=进程调度/启动；IO/preprocessing 非瓶颈。
- **优化前后一致性**：子进程 vs `--in-process` 多次回归（6/11 实验，覆盖 5 模型族与 CNN k3/5/7）metric max|Δ|=0 PASS；本轮快速回归再确认（14.99s vs 5.91s，Δ=0）。

### 待用户决策的候选（均未启用）
1. 线程封顶并发 `--threads-per-worker`（2.4–3.1×，linear ~1e-4 漂移）。
2. CNN ISM/IG 向量化（省每 CNN 实验 ~2–4s+，潜在浮点变化）。
3. 混合调度：仅对非线性实验启用封顶并发、linear 保持串行（xgb 不受影响、mlp ~1e-8，仍需授权）。

---

## Round-5 (Phase-10 广度回归)
- 扩展回归 80 实验：cells {hct116, hela} × envs {sequence, all} × splits {single, all, mixed(4 seeds)}；
  模型族 linear/xgboost/mlp + CNN(k3)/transformer(single/all)。
- 子进程串行 vs `--in-process`：**80/80 逐位一致 (metric max|Δ|=0)**。
- 墙钟：broad 151.7s→34.0s(≈4.5×)；ext(CNN/Transformer, explanation 占比高) 358.8s→216.5s(≈1.66×)。
- 结论：进程内调度在所有抽样划分/细胞系/环境上不改变任何数值；CNN explanation 越占主导，调度加速相对越小。
