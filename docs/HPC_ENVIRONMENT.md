# HPC 超算平台环境说明 (CRISPR 项目专用)

> 整理时间/来源：依据部署该平台的用户所提供并经实际验证的信息归档。
> 适用节点：master（管理/建环境）、gpu2（轻量测试）、gpu3（正式 GPU 计算）。
> 注意：本文件是平台事实说明；环境版本锁文件请在平台上现场导出（见文末）。

## 1. 平台架构与 GPU

```text
平台架构
├── master                # Conda 创建/安装依赖/文件管理
├── gpu2
│   ├── GPU 0: NVIDIA GeForce ... 24 GB
│   └── GPU 1: NVIDIA GeForce ... 24 GB
└── gpu3
    └── 8 × NVIDIA A100-SXM4-80GB
```

### gpu2（轻量测试）
```text
GPU   : 2 × NVIDIA GeForce ..., 24 GB/卡
Driver: 525.105.17
CUDA  : 12.0 (nvidia-smi 报告)
```
适合小规模/冒烟测试，正式深度学习优先 gpu3。

### gpu3（正式实验）
```text
GPU   : 8 × NVIDIA A100-SXM4-80GB
显存  : 80 GB/卡
Driver: 550.54.14
CUDA  : 12.4 (nvidia-smi 报告)
MIG   : Disabled
```

### CUDA_VISIBLE_DEVICES 用法（已验证）
```bash
CUDA_VISIBLE_DEVICES=7 python ...
# 程序内部看到 cuda:0，实际物理设备是 GPU 7
```

## 2. 文件系统与路径

```text
用户工作目录入口: /home/zhanghaohong/zhangrixing
                  -> /data6/zhanghaohong/zhangrixing/   (软链接)

master / gpu2: /data6/zhanghaohong/zhangrixing
gpu3        : /data9/zhanghaohong/zhangrixing
```
同一底层存储，不同节点挂载路径不同。**gpu3 统一使用 `/data9/zhanghaohong/zhangrixing`**。

## 3. Conda

```text
服务器 Conda: /home/zhanghaohong/anaconda3  (Conda 24.11.3)
CRISPR 环境:
  master: /home/zhanghaohong/zhangrixing/.conda/envs/crispr
  gpu3  : /data9/zhanghaohong/zhangrixing/.conda/envs/crispr
```
gpu3 上激活请用（已验证）：
```bash
conda activate /data9/zhanghaohong/zhangrixing/.conda/envs/crispr
# 不要使用 /home/zhanghaohong/... 前缀路径
```

### 已知 Conda 警告（可忽略）
```text
Error while loading conda entry point: conda-libmamba-solver
(libarchive.so.19: cannot open shared object file)
```
当前 `solver: classic`，创建/安装均成功 → 记为 **libmamba 插件问题，不影响 classic solver 使用**；
不要因此升级服务器 Conda。

## 4. crispr 环境核心软件（实际部署版本）

```text
Python        3.10.21
NumPy         2.2.6
Pandas        2.3.3
SciPy         1.15.2
scikit-learn  1.7.2
Matplotlib    3.9.4
XGBoost       2.0.3
PyTorch       2.6.0+cu124  (CUDA 12.4, cuDNN 9.1, Triton 3.2.0)
```
已验证：Transformer 可运行于 gpu3 / A100 / GPU 7。

## 5. 网络策略

```text
master: 可访问 Conda/PyPI，但慢（实测 PyTorch 下载约 31.7 kB/s）
gpu3  : 部分外部域名无法解析（如 mirrors.tuna.tsinghua.edu.cn、repo.anaconda.com）
策略:   master 配源/下载依赖 → gpu3 只做 GPU 计算
大文件: 本地(WSL)下载 → scp 上传 master → 离线安装
```

## 6. 项目目录规范

```text
/data9/zhanghaohong/zhangrixing/
├── Submit/        # 项目代码（当前即 /data9/.../Submit，无需重排）
├── data/
├── results/
├── models/
├── logs/
├── checkpoints/
└── .conda/envs/crispr/
```

## 7. GPU 使用规范（老师要求）

- 每次使用前 `nvidia-smi` 查看负载。
- 确认空闲卡后：`CUDA_VISIBLE_DEVICES=N python ...`。
- 不要只看显存：同时观察 `Memory-Usage / GPU-Util / Processes`，避免干扰他人实验。

## 8. 环境锁文件导出（在平台上执行，勿在本沙箱）

```bash
# 1) master 或 gpu3 激活 crispr
conda activate /data9/zhanghaohong/zhangrixing/.conda/envs/crispr
cd /data9/zhanghaohong/zhangrixing/Submit

# 2) 导出 conda 环境
conda env export -n crispr > environment.yml

# 3) 导出 pip 锁（已激活环境内）
python -m pip freeze > requirements-hpc.txt

# 4) 提交到代码库 (git add environment.yml requirements-hpc.txt)
```
> `requirements.txt` 仍保留为跨平台/通用约束；HPC 精确恢复以
> `environment.yml` + `requirements-hpc.txt` 为准。

## 9. 相关工具（本项目内）

- `profile_experiment.py`：分段 profiling，`--device cpu|cuda`。
- `regression_compare.py`：优化前后结果一致性回归（`--quick`/`--extended`）。
- `PERF_REPORT.md`：性能优化 10 阶段台账与全部测量结论。
- 推荐执行方式与调度协议见 `HPC_EXPERIMENT_PROTOCOL.md`。
