# HPC 平台适配说明（CentOS 7 / glibc 2.17 / 8×A100 / 驱动 550 / CUDA 12.4）

针对你的平台实际约束，说明 `requirements_frozen.txt`（开发机审计栈）里哪些能直接装、
哪些必须换、换了以后对数字有什么影响、怎么验证。

---

## 1. 你的平台 vs 开发机

| 项 | 开发机（产出审计结论的栈） | 你的超算 | 影响 |
|---|---|---|---|
| OS / glibc | WSL2 / glibc 2.39 | CentOS 7 kernel 3.10 / **glibc 2.17** | **pip 只能装 manylinux2014(`manylinux_2_17`) 轮子**；`manylinux_2_28` 的包会报 `GLIBC_2.28 not found` |
| Python | 3.12.3 | 3.12.2 (conda-forge) | 补丁级差异，无数值影响 |
| GPU | 无（CPU） | 8 × A100-SXM4-80GB | 训练会走 GPU；CNN/MLP/Transformer 自动用 cuda |
| 驱动 / CUDA | — | 550.54.14 / **CUDA 12.4** | **torch 的 cu130 build 需要 ≥580 驱动，你的机器跑不了** |

结论：**只有两处必须改** —— (1) glibc 2.17 决定装包渠道（走 conda-forge 最稳），
(2) torch 的 CUDA build 必须是 **cu124**。其余包的**版本号保持不变**。

---

## 2. 谁是"数值关键包"（决定 R²/MAE）

| 类别 | 包 | 是否影响指标 | 策略 |
|---|---|---|---|
| 数值关键 | numpy, pandas, scipy, scikit-learn, xgboost, torch | **是** | 版本号必须与开发机一致（torch 只换 CUDA build） |
| 训练期调用 | shap, joblib | 影响 TreeSHAP 重要性数值 | 版本尽量一致，不一致需声明 |
| 仅出图/报告 | matplotlib, seaborn, tabulate, openpyxl | 否（但缺失会让 run 保存阶段报错） | 装上即可，版本随意 |
| 间接依赖 | numba, llvmlite | 否（部分 shap explainer 用） | 让求解器按 numpy 兼容性自选 |

所以"不太契合"的痛点其实集中在 **6 个包 + 1 个 CUDA build**，不是整张清单。

---

## 3. 安装（推荐 conda-forge，绕开 glibc 2.17 轮子问题）

```bash
conda create -n crispr python=3.12.2 -c conda-forge -y
conda activate crispr

# 用平台适配清单（已把 cu124 索引写在 torch 之前）
pip install -r requirements_hpc.txt

# 若 torch 的 cu124 轮子在你的平台不存在（pip 报找不到匹配版本），改用 conda：
#   conda install -c conda-forge pytorch=2.13.0 pytorch-cuda=12.4 -y

# 自检（会检查 glibc/驱动/CUDA/版本栈，并给出差异）
python deploy/hpc/preflight_hpc_rerun.py --package . --batch-name batch_20260913_groupaware
```

在装之前先确认平台实际可获得的版本（**不要凭猜**）：

```bash
pip index versions torch --index-url https://download.pytorch.org/whl/cu124
conda search -c conda-forge 'numpy=2.5.*'
python -c "import torch;print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

自检脚本 P8 的判定规则：

* 与 `requirements_hpc.txt` 不一致 → **FAIL**（装错环境必须停下）；
* 与 `requirements_frozen.txt`（开发机审计栈）不一致 → **WARN** 并列出差异包；
* `torch.__version__` 的本地 build 标签（`+cu124` / `+cu130`）不算版本不符，
  但会在输出中显式打印，便于确认 CUDA build。

---

## 4. 8×A100 上的并发与显存

* **worker↔GPU 绑定已内置**：`run.sh` 自动 `nvidia-smi` 探测，worker i 绑到第 i 张卡
  （`CUDA_VISIBLE_DEVICES`）。没有这一步，8 个 worker 会全挤在 0 号卡上，
  既浪费 7 张卡又容易 OOM。
* 建议 `WORKERS=8`（= 卡数）。显式指定：`GPUS="0 1 2 3 4 5 6 7"`；关闭绑定：`GPUS=none`。
* A100-80GB 单卡跑本项目 CNN（23×8 输入、几十万参数）余量很大，1 进程/卡没问题。
* `--threads-per-worker` 默认 0（不封顶）。8 个 worker 同时跑 xgboost/shap 会抢占 CPU，
  若节点 CPU 核数紧张可设 `THREADS_PER_WORKER=4` —— 但这会改变 BLAS 归约顺序，
  **可能引入 ~1e-4 漂移**，默认不启用。
* 每个 run 会记录 `env_fingerprint`（含 `cvd=` 即绑定的可见设备）、`device_resolved`、
  `torch_version`、`torch_cuda_build`，验收脚本会检查全批指纹是否唯一。

---

## 5. 环境差异的验证流程（不要默认"应该没影响"）

版本号一旦不同，等价性就必须**实测**，不能假设：

```bash
# A) 超算上跑参考小批（与开发机同名同配置）
cd upload
python workflows/training/data_digging.py --batch-name env_check --split-types single all mixed \
    --models linear xgboost mlp cnn --environments sequence sequence_ctcf --workers 8
tar czf env_check.tar.gz results/env_check

# B) 开发机上跑同一批到 local_env_check（同一条命令，改 batch 名）
#    注意 CNN/MLP 在 CPU 与 GPU 上本就不逐位一致 → 只在同设备类型间比对

# C) 比对并出报告
python deploy/hpc/compare_env_equivalence.py \
    --reference results/local_env_check --candidate results/env_check \
    --out results/tables/audit/env_equivalence
```

判定标准：

| 模型 | 期望 | 阈值 |
|---|---|---|
| linear / xgboost（纯 CPU 确定性） | 同数据同种子应完全一致 | `1e-9` |
| mlp / cnn / transformer（BLAS/CUDA kernel） | 允许极小漂移 | `1e-4` |

超出阈值 → 环境差异已进入"影响结论"的量级，必须在论文/答辩中写明。

---

## 6. 需要写进论文/报告的环境声明

用下面这段（把实际值填上）：

> 全部 1344 次实验在同一超算环境完成：CentOS 7 (glibc 2.17)、Python 3.12.2 (conda-forge)、
> numpy 2.5.2、pandas 3.0.5、scipy 1.18.0、scikit-learn 1.9.0、xgboost 3.4.1、
> torch 2.13.0 (CUDA 12.4 build)、8 × NVIDIA A100-SXM4-80GB（驱动 550.54.14）。
> 每次运行在 `*_info.txt` 中记录 `env_fingerprint`；经核验全批 1344 个实验的
> `env_fingerprint_id` 唯一（`verify_hpc_rerun.py`），即结果不受跨环境异质性影响。
> 与开发机审计栈的差异仅为 torch 的 CUDA build（cu130→cu124，受驱动版本约束），
> 经 `compare_env_equivalence.py` 在同一批 run 上比对，|ΔR²| ≤ <填入实测值>。

---

## 7. 常见报错对照

| 报错 | 原因 | 处理 |
|---|---|---|
| `ImportError: GLIBC_2.28 not found` | 装到了 manylinux_2_28 轮子 | 改用 conda-forge 安装该包 |
| `The NVIDIA driver on your system is too old` / `CUDA error: no kernel image` | 装了 cu130 等更高 CUDA build | 卸载后装 cu124 build |
| `torch.cuda.is_available() == False` | 在无 GPU 的登录节点 / 未申请 GPU 资源 | 用 `srun`/`sbatch` 申请 GPU 节点后再自检 |
| 8 个 worker 但只有 GPU0 有负载 | 未做 worker↔GPU 绑定 | 用本次的 `run.sh`（已内置自动绑定） |
| `ModuleNotFoundError: numba` | shap 的间接依赖未装 | `pip install numba llvmlite`（conda-forge） |
