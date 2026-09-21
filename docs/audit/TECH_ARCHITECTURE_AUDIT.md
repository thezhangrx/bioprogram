# CRISPR AI 平台代码技术架构与优化分析报告

**审计对象**：`/home/zhang/bioprogram/Submit`（CRISPR-Cas9 sgRNA 编辑效率预测与影响因素挖掘平台）
**审计方式**：静态扫描 + 运行时实测（所有性能数字均为本机跑出的真实值，不是估算）
**审计日期**：2026-09-19
**代码规模**：自有 Python 文件 **172** 个、约 **46 400** 行

| 层 | 文件数 | 行数 | 职责 |
|---|---:|---:|---|
| `core/` | 27 | 10 250 | 科学引擎（特征、划分、模型、归因） |
| `workflows/` | 9 | 3 479 | 用户入口（训练、挖掘、预测、编排） |
| `analysis/` | 72 | 19 856 | 分析层（统计、证据、报告、图表） |
| `tests/` | 36 | 6 244 | 测试（515 passed / 32 skipped） |
| `deploy/` | 9 | 2 972 | 部署与 HPC |
| `app/` | 19 | 3 599 | Web 工作台与桌面向导 |

---

## 一、代码技术栈总览

### 1.1 核心第三方库

| 技术/库 | 使用位置（代表） | 作用 | 解决的问题 | 带来的优势 |
|---|---|---|---|---|
| **numpy** (69 文件) | `core/features/engineering/feature_engineering.py`、`analysis/stats/bootstrap.py` | 张量构造、向量化统计 | 23×C 张量与 B×n 重采样的批量计算 | 比 Python 循环快 1–2 个数量级（实测见 §5.1） |
| **pandas** (89 文件) | `analysis/collect_results.py`、`analysis/stats/tasks.py` | 结果表聚合与联结 | 1344 run 的指标汇总、按族分组 | `groupby` 105 处 / `concat` 22 处，把"逐 run 循环"变成一行表达式 |
| **PyTorch** (21 文件) | `core/models/{cnn,mlp,transformer}/*.py` | 深度模型训练与梯度归因 | 卷积/注意力前向反向、`autograd.grad` | GPU 加速 + 自动微分（IG 无需手写梯度） |
| **scikit-learn** (15 文件) | `core/data/splitting/`、`analysis/paper_numbers.py` | 划分、指标、交叉验证、KDE | `KFold` / `Ridge` / `GridSearchCV` / `KernelDensity` | 标准化实现，避免自写 CV 出错 |
| **XGBoost** (2 文件) | `core/models/xgboost/xgboost.py` | 树集成 + 原生 TreeSHAP | 非线性交互 + 可精确分解的归因 | `pred_contribs` 直接给出 SHAP，**不依赖第三方 `shap` 包** |
| **SciPy** (7 文件) | `core/models/linear/linear_regression.py`、`analysis/stats/hypothesis_tests.py` | t/F 分布、精确检验 | 系数 p 值、ANOVA 的 F 上尾概率 | 统计分布实现可信；并有**无 scipy 时的正则不完全 Beta 连分式回退** |
| **matplotlib** (32 文件) / **seaborn** (8) | `analysis/panorama.py`、`analysis/visualization/` | 统计图与全景图 | 位置热图、forest plot、DAG | 出版级矢量图（PDF） |
| **pathlib** (117 文件) | `core/common/paths.py` | 跨平台路径解析 | 绝对路径写死、跨机器不可复现 | 全仓库 **0 处硬编码绝对路径** |
| **argparse** (29 文件) | 全部用户入口 | 命令行接口 | 用户改参数需读源码 | 每个入口 `--help` 自文档化 |
| **dataclasses** (16 文件，37 处 `@dataclass`) | `analysis/config.py`、`analysis/plans.py` | 结构化配置与结果类型 | 阈值散落、字典键拼写错误 | 单一来源 + 类型安全 + 不可变（`frozen=True`） |
| **concurrent.futures** (2 文件) | `workflows/training/data_digging.py:688` | 并发调度 | 1344 次实验串行太慢 | `ThreadPoolExecutor` 管理 worker 槽位 |
| **hashlib** (8 文件) | `workflows/training/train.py:57,93,102` | 指纹 | 结果与实验条件脱钩 | 数据/代码/环境/划分四类可核验指纹 |
| **subprocess** (15 文件) | `workflows/training/data_digging.py:421,463` | 进程隔离 | 单进程内跑 1344 个实验会互相污染 | 每个实验独立进程 + 独立 GPU 绑定 |

### 1.2 需要澄清的"疑似依赖"

| 模块 | 实际状态 |
|---|---|
| **joblib** | **不是依赖**。仅出现在 `workflows/training/train.py:77` 的**版本指纹串**中（探测是否存在以记录环境），代码未调用其 API |
| **numba** | 同上，仅在指纹串中；**未使用 JIT** |
| **tensorflow / Bio** | 仅存在于 `deploy/external/crispron/`（第三方模型 CRISPRon 的 vendored 运行时），**不属于本项目代码** |

> 这三点容易被误读为"项目用了 joblib 并行 / numba 加速"，实际都没有。

### 1.3 明确**未使用**的常见技术（审计发现）

| 技术 | 状态 | 影响 |
|---|---|---|
| `torch.cuda.amp` / `autocast` / `GradScaler` | ❌ 全项目 **0 处** | 无混合精度训练 |
| `multiprocessing` | ❌ 0 处 | 用 `ThreadPoolExecutor` + `subprocess` 替代 |
| `pin_memory` | ❌ 0 处 | DataLoader 未锁定页内存 |
| `tqdm` | ❌ 0 处 | 无进度条 |
| `contextlib.contextmanager` | ❌ 0 处 | 无自定义上下文管理器 |
| `functools.lru_cache` | ❌ 0 处 | 用自实现字典缓存（见 §2.3） |
| Parquet | ❌ 0 处（`read_csv` 107 / `to_csv` 87） | 全部中间产物为 CSV |

---

## 二、重点工程优化

### 2.1 配置驱动设计（Config-driven Architecture）

项目里有**两套**配置机制，成熟度**不同**——这是本次审计最重要的区分：

#### （1）特征配置：真·配置驱动 ✅

`data/metadata/feature_config.json`：

```json
{
  "sequence_channels": ["A","C","G","T"],
  "environment_features": [
    {"name":"CTCF","column":"CTCF","type":"per_position_binary",
     "encoding":{"A":1,"N":0},"enabled":true},
    {"name":"Dnase", ...}, {"name":"H3K4me3", ...}, {"name":"RRBS", ...}
  ]
}
```

消费方 `core/features/engineering/feature_engineering.py` 按 `type` 分派到三种编码器
（`per_position_binary` / `per_position_numeric` / `global_numeric`）。

**为什么不用 `CTCF = column[4]`？**

| 若硬编码通道下标 | 配置驱动的效果 |
|---|---|
| 新增一条表观轨道要改核心编码函数 | 只加一个 JSON 条目（`enabled: true`） |
| 通道顺序靠约定，改一处忘另一处 | 顺序由 `environment_features` 列表唯一决定 |
| 无法表达"某数据集没有表观通道" | `environment_features: []` 自然表示 4 通道数据集 |
| 数据集差异写进 if-else | `data/metadata/datasets.json` 声明各数据集用哪份配置 |

**实测收益**：三个数据集（8 通道 184 维 / 4 通道 92 维）共用**同一份编码代码**，
无一处 `if dataset == "DeepCRISPR"` 式的分支。

#### （2）统计阈值配置：**不是文件配置** ⚠️（审计发现）

统计阈值集中在 `analysis/config.py`，但它是 **Python `@dataclass(frozen=True)`**：

```python
@dataclass(frozen=True)
class EvidenceRuleConfig:
    min_absolute_delta_r2: float = 0.01
    ci_crosses_zero_forces_inconclusive: bool = True
    min_bootstrap_iterations: int = 200
    statistical_gate_can_promote: bool = False
    effect_gate_mode: str = "model_mean"
```

调用方式是 `cfg = config or AnalysisConfig()`（`analysis/stats/tasks.py` 6 处），
**全项目没有任何 JSON/YAML 加载入口**（`analysis/config.py` 与 `analysis/pipeline.py` 中
`load_config`/`from_file` 均 0 命中）。

| 优点 | 代价 |
|---|---|
| 单一来源、类型安全、`frozen=True` 不可变、IDE 补全、可被测试直接 import | **变更阈值必须编辑 `.py` 文件**，非程序员无法调整 |

**结论**：若目标是"用户不改代码即可调阈值"，这一层应外置为 JSON/YAML
（`AnalysisConfig.from_file()`），当前是**中等成熟度**。

#### （3）数据集清单：配置驱动的正确范例 ✅

`data/metadata/datasets.json` 把"数据集 → raw 目录 / processed 目录 / feature_config /
标签列 / 通道数 / PAM 规则"全部声明化。`core/common/paths.py` 提供
`datasets_registry()` / `dataset_spec()` / `dataset_feature_config()` 三个读取器。

**新增一个数据集只需两步**：把 CSV 放进 `data/raw/<名称>/`、在 JSON 里加一条记录。
**零 Python 改动。**

---

### 2.2 模块化设计

#### （1）分层与依赖方向（实测）

```
core/          科学引擎         ← 不 import 任何上层（实测 0 处）✅
  ↑
  ├── workflows/   用户入口      ← 不 import analysis（实测 0 处）✅
  └── analysis/    分析层        ← 不 import workflows（实测 0 处）✅
```

**这是本项目最扎实的架构性质**：`core/` 对 `workflows/` 与 `analysis/` 的导入数
**均为 0**，依赖严格单向。含义是：

- 替换模型实现（`core/models/*`）**不会**波及分析代码；
- 改变特征工程**不会**波及模型代码（模型只吃 `(N, L, C)` 张量）；
- 修改 CLI**不会**影响科学逻辑。

#### （2）"结果文件即接口"（Artifact-as-Interface）

`analysis/` 对 `core/` 的导入只有三类（实测）：

| 导入 | 次数 | 用途 |
|---|---|---|
| `core.common.paths` | 9 | 路径解析（非逻辑耦合） |
| `core.data.splitting.cell_line_division` | 4 | 读 `feature_schema.json` 契约 |
| `core.models.linear.linear_regression` | **1** | 见下 |

那唯一一处（`analysis/reporting/paper_analysis/position18_signed_substitution_ism.py:201`）
是**论文反事实脚本**——它必须重建线性模型对象才能扰动输入，属合理例外。

其余全部通过**读取产物**协作：`analysis/stats/tasks.py:53` 的
`*_predictions.csv`（显式排除 `validation` 文件）、`*_metrics.json`、`*_info.txt`。
**这是高内聚低耦合的关键实现**：统计层不需要 import 任何模型类，只要文件格式稳定。

#### （3）高内聚的体现

| 模块 | 内聚点 |
|---|---|
| `core/data/splitting/cell_line_division.py` | 身份类划分 + 运行期重叠断言 + `split_digest` 全在一个文件（划分与自证不可分离） |
| `core/features/channels/cell_environment_combination.py` | 通道组合与 16 节点 factorial lattice 集中一处 |
| `analysis/config.py` | 全部科学阈值集中（**不散落各模块**，文件头即写明"阈值不得散落"） |
| `analysis/stats/` | bootstrap / permutation / FDR / effect_size 四个正交文件 |

#### （4）模型替换是否影响分析代码？

**不影响。** 新增第 6 类模型只需：在 `core/models/<name>/` 实现 `train()` 与
归因白名单列 → 在 `workflows/training/train.py` 的 `MODEL_MODULES` 注册。
`analysis/` 侧因只读 `*_metrics.json` / `*_predictions.csv`，**零改动**。

反证：项目已有 7 个配置（含 3 种 CNN 核）共用同一套分析代码，未出现分支。

---

### 2.3 数据处理优化

#### （1）NumPy 向量化

**显式使用**：
- `core/features/engineering/feature_engineering.py:411` 一次性 `np.zeros((23, C))` 再按下标置 1（而非逐位点拼接）
- `analysis/stats/bootstrap.py:189` 的**计数矩阵 + matvec**（见 §5.1，本次审计实测加速 **8.2×**）
- `core/models/linear/linear_regression.py:214-222` 用 `np.argsort` 向量化 BH-FDR

**为什么矩阵运算快**：`C @ v` 走 BLAS（多线程 + SIMD），而 Python `for` 循环每次迭代
都要付解释器开销与边界检查。对 `(B=2000, n=636)` 的规模，差距是数量级的。

**残留的非向量化点**（审计发现）：
- `core/models/cnn/cnn.py:300-307` 的 ISM 用 `for l in range(23): for c in range(C)`
- `core/models/mlp/mlp.py` 的 IG 用 `for i in range(N)` 逐样本

（详见 §6）

#### （2）Pandas 使用模式

| 操作 | 次数 | 典型用途 |
|---|---:|---|
| `astype` | 122 | 显式类型归一（防 dtype 漂移） |
| `groupby` | 105 | 按 (model, environment) 聚合、按 FDR 族分组 |
| `concat` | 22 | 逐细胞系结果纵向拼接 |
| `value_counts` | 18 | 分布核查 |
| `map` | 16 | 标签/类别映射 |
| `merge` | 10 | 归因表联结（`motif_candidates` × `motif_enrichment`） |
| `pivot_table` | 10 | 位置 × 碱基矩阵、热图输入 |
| `pivot` | — | 效应矩阵 |
| `drop_duplicates` | 6 | 重复测量识别 |

**降低复杂度的方式**：把"1344 个 run 的指标汇总"表达为
`groupby(["model","environment"]).mean()` 一行；把"跨细胞系一致性"表达为
`pivot` + 方向比较。若用纯 Python，等价逻辑需要嵌套字典与多层循环，且极易在键名上出错。

**未使用 `categorical`**：122 处 `astype` 说明是显式转换而非类别优化——对当前数据规模
（万级行）够用，若扩到百万行应改用 `category` dtype 降低内存。

#### （3）数据缓存机制

| 缓存 | 位置 | 效果 |
|---|---|---|
| **特征张量** | `data/processed/<数据集>/*.npy`（实测 **18 个**） | 特征工程只跑一次，训练直接 `np.load` |
| **逐 run 权重** | `models/weights/<batch>/<run>/`（实测 **5 802 个文件**） | 分析层可重建模型做反事实，无需重训 |
| **批次汇总表** | `results/batches/<batch>/summary/tables/*.csv` | 统计层复用，避免重算 bootstrap |
| **计数矩阵缓存** | `analysis/stats/bootstrap.py:_COUNT_CACHE` | **实测把 2 600 条边的 37.3 s 降到 0.022 s**（§5.1） |
| **`lru_cache`** | ❌ 未使用 | 用自实现 dict 缓存（可跨不同 n/B/seed 组合） |

**为什么缓存中间结果**：特征工程对 16 749 条序列做 23×8 one-hot，是纯 CPU 的
O(N·L·C) 操作；1344 次训练若每次重算，总开销与训练本身同量级。
缓存让"特征构造"与"训练"解耦为两个可独立重跑的阶段。

**审计发现**：`_COUNT_CACHE` 是**模块级无上限字典**，键为 `(n, B, seed)`。
本项目的 n 取值有限（≈300–3 000），实际条目数可控；但若 n 连续变化（如逐样本量不同的
实验），会持续增长。建议加 `maxsize` 或改用 `functools.lru_cache`。

---

## 三、模型训练优化分析

### 3.1 GPU 加速

**设备解析**（`workflows/training/train.py`、`core/models/*/`）：

```python
# 1) 训练前把 --gpu-id 写进环境变量（在 CUDA 初始化之前）
os.environ["CUDA_VISIBLE_DEVICES"] = gpu_id        # 如 "0" 或 "0,1"
# 2) 模型与数据搬到设备
model.to(device); X.to(device)
```

**数据流（CPU ↔ GPU）**：

```
numpy (N,23,C) 在主机内存
      ↓ torch.from_numpy(...).to(device)      一次性搬迁
GPU 显存：前向 → 损失 → 反向 → 参数更新
      ↓ .cpu().numpy()                        结果回主机
numpy 指标 / CSV 落盘
```

**真正跑在 GPU 上的步骤**：卷积/矩阵乘的 **forward**、**backward**、以及 IG 的
`autograd.grad`。**不在 GPU 上**：损失标量归约（可忽略）、指标计算、SHAP/ISM 的
numpy 汇总、CSV I/O。

**实测证据**：权威批次 1344 run 中 **960 个神经网络 run 的 `device_resolved` 全为 `cuda`**
（`results/tables/audit/ultimate_run_verify_report.md`），无 CPU/GPU 混跑。

**审计发现**：本机 `torch.cuda.is_available() == False`（无 GPU），训练自动落 CPU——
代码路径正确，但**本机无法验证 GPU 性能**。

### 3.2 Batch 训练

`DataLoader`（实测位于 cnn 5 处 / transformer 5 处 / mlp 4 处 / predict 2 处）：

| 参数 | 项目实际值 | 作用 |
|---|---|---|
| `batch_size` | **64**（网格）；ultimate 模型 **256** | 控制显存峰值与梯度噪声 |
| `shuffle` | 训练集 `True`，测试集 `False` | 打散批次顺序以免系统性偏差；评估必须固定顺序 |
| `num_workers` | **0**（默认；已接入 CLI） | 见下 |
| `pin_memory` | **未设置** | — |

**为什么 batch 训练**：
1. **显存**：全量 2 968×23×8 一次前向 + 保存中间激活会爆显存；batch=64 只需 1/46 的激活内存。
2. **GPU 利用率**：单样本前向无法填满 SM，batch 让卷积/GEMM 达到高占用率。
3. **收敛**：mini-batch 梯度噪声兼具正则化效果。

**审计发现（两点）**：
- `num_workers` 默认 **0**，即数据加载在**主进程同步**完成。本项目数据已全部在内存
  numpy 数组中（`TensorDataset`），无磁盘 I/O，因此 `num_workers=0` **是合理选择**——
  开多 worker 反而增加进程间拷贝开销。
- **未使用 `pin_memory`**：在 GPU 环境下，`pin_memory=True` 可让 H2D 拷贝走异步 DMA。
  当前缺失，是**中低优先级的可优化项**（收益取决于数据量，本项目张量小，影响有限）。

### 3.3 Mixed Precision / AMP

**审计结论：未使用。** `autocast`、`torch.cuda.amp`、`GradScaler` 全项目 **0 命中**。

**这意味着什么**：

| 若有 AMP | 当前无 AMP 的代价 |
|---|---|
| FP16/BF16 前向，显存约减半 | 显存占用偏高（FP32） |
| Tensor Core 加速，速度常提升 1.5–3× | 未利用 Tensor Core |
| `GradScaler` 防梯度下溢 | 需注意 FP32 下的梯度尺度 |

**为什么可以接受**：本项目模型很小（CNN 卷积通道 64/64/128，MLP 128→64，
Transformer `d_model=64`），FP32 下显存与速度都不是瓶颈（真正瓶颈是 1344 次实验的
**调度**，不是单次训练速度）。因此**未上 AMP 是合理的工程取舍**，而非缺陷。
若后续模型放大或改用更大 batch，应优先补 AMP。

### 3.4 Early stopping / Checkpoint

**早停实现**（`core/models/cnn/cnn.py:611-612, 780-845`）：

```python
patience=20, min_delta=1e-6
best_val_loss = np.inf; best_epoch = None
...
improvement = best_val_loss - val_loss
if improvement > min_delta:
    best_val_loss = val_loss
    best_epoch = epoch
    best_state_dict = copy.deepcopy(model.state_dict())    # 只在改进时深拷贝
...
model.load_state_dict(best_state_dict)                     # 训练结束回滚到 best epoch
```

**四项设计要点**：

1. **`min_delta` 阈值**：只有改进超过 1e-6 才算改进，避免被浮点噪声"骗取"重置计数。
2. **`copy.deepcopy(state_dict())` 只在改进时执行**：不是每个 epoch 都深拷贝，
   节省显存与时间。
3. **训练结束回滚 `load_state_dict(best_state_dict)`**：保证落盘的模型是**best epoch**
   而非最后一轮——这一点直接影响结果可信度（否则早停了却存了过拟合的末轮权重）。
4. **`patience=20`**：连续 20 个 epoch 无改进即停，避免无效训练。

**Checkpoint 与可恢复性**：
- `save_model()` 保存 `{"model_state_dict":..., "config":...}`（`torch.save`）——
  **权重与配置同文件**，因此任何模型都能自解释（`core/models/cnn/cnn.py:580`）。
- 线性模型用 `pickle`（`linear_regression_model.pkl`）+ 独立 JSON 存权重与统计量。
- **审计发现**：保存的是**最终最优权重**，**不含 optimizer state / epoch 号**，
  因此**不支持从中间断点续训**（resume）。对本项目（单次训练分钟级、失败即重跑）
  可接受；若训练时长增大到小时级，应补 `optimizer.state_dict()` 与 `epoch`。

---

## 四、实验可重复性设计

### 4.1 Random seed 管理

**统一入口**（三个 torch 模型各有一份 `set_seed`，实测 `cnn.py:49-58` 等）：

```python
def set_seed(seed: int = 42):
    random.seed(seed)                 # Python 内置
    np.random.seed(seed)              # 全局 numpy 遗留接口
    torch.manual_seed(seed)           # torch CPU + 所有 GPU
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True   # 关闭非确定性卷积算法
        torch.backends.cudnn.benchmark = False      # 禁止 autotune 选算法
```

**为什么这 6 行决定实验可信度**：

| 设置 | 缺了会怎样 |
|---|---|
| `torch.manual_seed` | 权重初始化每次不同 → 同一配置两次跑出不同 R² |
| `torch.cuda.manual_seed_all` | 多卡时各卡 dropout 随机流不一致 |
| `cudnn.deterministic=True` | cuDNN 自动选最快卷积算法，不同算法浮点累加顺序不同 → 结果不可复现 |
| `cudnn.benchmark=False` | benchmark 会随输入尺寸切换算法，引入不确定性 |

**划分侧**用现代 Generator API：`np.random.default_rng(random_seed)`（30 处），
而非全局 `np.random.seed` —— `default_rng` 不污染全局状态，且跨 numpy 版本行为稳定。

**种子策略**：`single`/`all` 固定 **42**；`mixed` **42/43/44/45**（4 个种子用于估计变异）；
bootstrap **2024**；置换检验 **2024**；独立复核 **0**。

**审计发现**：`set_seed` 在 3 个模型文件中**重复实现**（cnn/mlp/transformer）。
若将来只改一处（例如加 `torch.use_deterministic_algorithms`），另两个模型会静默不一致。
**建议提取到 `core/common/`**。

### 4.2 Fingerprint 机制（本项目最强的可重复性设计）

`workflows/training/train.py` 定义三类指纹，逐 run 写入 `*_info.txt`：

| 指纹 | 构造 | 回答的问题 |
|---|---|---|
| `data_fingerprint` | 元数据内容哈希 + 特征文件大小 | 这批结果用的是哪份数据？ |
| `code_fingerprint` | 关键源文件 md5 | 用的是哪版代码？ |
| `env_fingerprint` / `env_stack_id` | 依赖版本串 + 设备可见性 | 哪套数值栈？ |
| `split_digest` | train/valid/test 序列集合与样本数的 **SHA-256 前 16 位** | 训练所用划分 == 分析所用划分？ |

**`split_digest` 是设计最巧的一环**：它把"划分"这一**中间态**变成可核验的**内容摘要**。
因为划分结果本身不落盘为文件（只落盘索引），事后无法直接比对；而 digest 让
"训练时实际使用的划分"与"分析阶段重算的划分"可以**逐条比对**。

**实测效果**：权威批次 1 344 个 run 的 `split_digest` 与本地按同一代码重算的结果
**逐条一致（0 处不一致）**；数据/代码/环境指纹**各只有 1 种取值**。

**为什么需要 `env_stack_id` 与 `env_fingerprint` 分开**：
`env_fingerprint` 含 `cvd=0`（GPU 可见性），**有意排除**在 `env_stack_id` 之外——
因为"同一数值栈跑在不同 GPU 上"应当仍算同一环境。这个区分（`train.py:97` 明确注释）
避免了把正常的设备差异误判为环境变更。

**局限性**：指纹是**事后可核验**，不是**事前可强制**。它记录"用了什么"，
但不阻止"用了不该用的"（例如误用废弃批次）。这一层需要流程约束补充。

### 4.3 Experiment tracking

| 追踪对象 | 落盘位置 | 内容 |
|---|---|---|
| 配置 | `<run>/<model>_info.txt`、`<model>_config.json` | 模型、划分、细胞系、环境、超参、设备、全部指纹 |
| 指标 | `<run>/<model>_metrics.json`（**测试集**）、`<model>_validation_metrics.json`（验证集） | R²/RMSE/MAE/Pearson/Spearman |
| 预测 | `<run>/<model>_predictions.csv` | 逐样本 `y_true, y_pred, error` |
| 归因 | `<run>/<model>_feature_importance.csv` | 白名单归因列 |
| 日志 | `results/logs/<batch>/<run>/training.log` | 每 10 epoch 一行（非每 epoch，避免日志爆炸） |
| 诊断 | `<model>_diagnostics.json` | 数值秩、条件数（线性）、`best_epoch` |

**设计模式：目录即实验记录**。没有引入 MLflow/W&B 等外部跟踪系统，而是用
`results/batches/<batch>/<run>/` 的**目录结构**承载全部元数据。优点：零外部依赖、
结果可 `rsync`、可被任何脚本直接读取；代价：无跨批次查询界面（由
`analysis/collect_results.py` 补上）。

**口径纪律**：`*_metrics.json` = 测试集，`*_validation_metrics.json` = 验证集，
两者文件名严格区分。这一约定曾被破坏并导致论文数字错误（发散计数被误记为 33），
现已在 `deploy/hpc/verify_hpc_rerun.py` 用代码强制（显式排除 validation 文件）。

---

## 五、统计分析代码工程设计

### 5.1 Bootstrap：计数矩阵 + matvec（本项目最精彩的性能优化）

**朴素实现**：对每条边、每个指标，循环 B 次重采样并重算指标。

**项目实现**（`analysis/stats/bootstrap.py:235-306`）：

```python
# 1) 预生成 (B, n) multinomial 计数矩阵，并按 (n, B, seed) 缓存
def _count_matrix(n, n_iterations, seed):
    key = (int(n), int(n_iterations), int(seed))
    cached = _COUNT_CACHE.get(key)
    if cached is None:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, n, size=(B, n))
        mat = np.zeros((B, n), dtype=np.float32)
        for i in range(B):
            mat[i] = np.bincount(idx[i], minlength=n)
        _COUNT_CACHE[key] = mat
    return cached

# 2) 充分统计量一次 matvec 得到全部 B 个重采样值
C = _count_matrix(n, B, seed)
sy_a, sy2_a = C @ ya32, C @ f32(ya * ya)      # Σy, Σy²
ssr_a = C @ f32(ea)                            # Σ(y-ŷ)²
sae_a = C @ f32(aea)                           # Σ|y-ŷ|
r2 = 1.0 - ssr / (sy2 - sy**2 / nf)           # 向量化重建 R²
```

**四个叠加的优化**：

1. **计数矩阵替代重采样数组**：不需要物化 `(B, n, 2)` 的预测副本，
   只需 `(B, n)` 的 float32 计数 —— 内存降一个数量级。
2. **matvec 代替循环**：`C @ v` 一次算出全部 B 个重采样和（BLAS）。
3. **一次重采样服务多个指标**：R²/MAE/RMSE 共用同一个 `C`，抽取次数减为 1/3。
4. **充分统计量**：只累积 Σy、Σy²、Σ(y−ŷ)²、Σ|y−ŷ|，即可重建任意重采样的指标，
   无需重新前向或重新对齐预测。

**实测（本次审计跑出）**：

| 实现 | 耗时（n=636, B=2000, 3 指标） |
|---|---|
| 朴素逐次重采样 | **229.8 ms** |
| 计数矩阵向量化 | **28.0 ms** |
| **加速比** | **8.2×** |

R² 的 CI **逐位相同**（`[-0.079213, 0.003400]`）；MAE/RMSE 的 CI 有极小差异，
因为朴素版对每个指标独立抽签、快速版共用一批重采样——两者都是合法的 bootstrap 抽样，
不是 bug。

**缓存效果（实测）**：

| 场景 | 耗时 |
|---|---|
| 首次构建计数矩阵 | 14.3 ms |
| 其后 2 599 次复用（同一 n/B/seed） | **21.7 ms** |
| 若每次重建 | **37.3 s** |

即缓存部分**约 1 700×**。这直接决定了"2 600 条边 × 3 指标"的分析能否在秒级完成。

**精度取舍（有意的）**：重采样分布用 **float32** matvec（仅用于取 percentile），
**点估计仍用 float64 原值**。代码注释明确写了这一取舍——percentile 对末位精度不敏感，
而 float32 让 matvec 内存与带宽减半。

**失败处理**：`n < 3`、含非有限值、`bootstrap_status != ok`、迭代数 < 200 时返回
`available=False`，**不伪造区间**。实测 7 954 行中 **55 行**为 unavailable。

### 5.2 Permutation test：sign-flip（而非重排）

`analysis/stats/hypothesis_tests.py:26-63`：

```python
# 注意: 直接对中心化值做"重排"对均值是恒等变换(置换不改变均值), 会得到退化的 p;
# 因此必须翻转符号而不是重排位置。
centered = arr - null_effect
for _ in range(B):
    signs = rng.integers(0, 2, size=n) * 2 - 1     # ±1
    perm_stat = np.mean(signs * centered)
    count += perm_stat >= stat_obs
p = (count + 1) / (B + 1)
```

**工程亮点（也是科学正确性的关键）**：

1. **用符号翻转而非位置重排**：对"均值"这一统计量，重排是恒等变换（置换不改变均值），
   会得到退化甚至恒为 1 的 p 值。代码里明确写出了这个陷阱——**这是很多人会写错的地方**。
2. **符号生成向量化**：`rng.integers(0,2,size=n)*2-1` 一次生成整个 ±1 向量。
3. **`p = (count+1)/(B+1)`**：加 1 平滑，避免 `p=0`（无置换超过观测不等于概率为 0）。
4. **`n < 3` 返回不可用**：不伪造 p 值。实测 3 444 行中 **66 行**不可用。

**权衡**：外层 B 循环未向量化（每轮一次 `np.mean`）。因 B=1000 且 n 较小，
实测可接受；若需再加速，可预生成 `(B, n)` 的 ±1 矩阵并 `matmul`。

### 5.3 FDR：族隔离

`analysis/stats/multiple_testing.py` 仅 35 行，实现标准 BH：

```python
p = np.asarray(p_values)
order = np.argsort(p)
ranked = p[order] * m / (np.arange(1, m+1))
q = np.minimum.accumulate(ranked[::-1])[::-1]      # 保持单调
```

**关键设计不在算法而在"分族"**：`family_key` 形如
`environment_edge|mixed|none|cnn(3|3)`，即**按科学问题分族**，绝不把
"环境边检验"与"motif 富集检验"并入同一个族。实测 **189 个族**。

**为什么必须分族**：把不同科学问题的 p 值混在一起校正，会让样本量大的族
稀释小族的显著性（或反之）。族隔离保证"每个 FDR 回答一个明确的科学问题"。

**实测**：`min_family_size=2`（规模不足记 `not_applicable` 而非静默跳过）。

### 5.4 ANOVA：Type-II 边际平方和 + 设计矩阵

`analysis/stats/hypothesis_tests.py:244`：

- 用**设计矩阵 + extra-sum-of-squares** 计算 Type-II 边际 F（不是手写公式）
- **区组设计** `R² ~ A*B*C*D + C(model)+C(cell_line)+C(split_type)`：把模型与细胞系的
  均值差异**消去**，避免它们混入因子效应
- **交互项**：`a*b` 的 dummy 列逐元素乘积
- **降级策略**：`len(df) < min_observations(32)` 或残差自由度不足 → 返回
  `unavailable` + 原因串，**不返回近似值**
- **`ci_iterations=400`**：effect contrast 的 bootstrap CI
- **无 scipy 时的回退**：用正则不完全 Beta 连分式自实现 F 上尾概率

**实测**：94 行中 **38 ok / 56 unavailable**——降级机制被真实触发，
说明"不伪造"不是空话。**有意不加 FDR 列**（ANOVA 回答 global 问题）。

### 5.5 独立复核：与官方划分无关的 CV

`analysis/paper_numbers.py:129-143`：

```python
Ridge(alpha=1.0) + KFold(5, shuffle=True, random_state=0)
null = [r2_score(rng.permutation(y), pred) for _ in range(200)]
```

**设计意图**：仅比较"同一批划分下的测试 R²"无法区分"数据本身无信号"与
"该划分恰好困难"。因此额外做一次**与官方划分完全无关**的 5 折 CV，
并用 200 次标签置换构造零分布。判据是 CV R² 相对零分布的位置。

这是**统计证伪设计**而非精度比较：它让"Labuhn 无信号"这一阴性结论站得住。

---

## 六、可解释性模块技术分析

### 6.1 SHAP：使用 XGBoost 原生 TreeSHAP

**选择**：`pred_contribs`（XGBoost 原生），**不依赖第三方 `shap` 包**。

| | 原生 `pred_contribs` | 第三方 `shap` 包 |
|---|---|---|
| 依赖 | XGBoost 自带 | 额外依赖 + 版本耦合 |
| 算法 | 精确 TreeSHAP（多项式时间） | 同一算法 |
| 集成 | `Booster.predict(pred_contribs=True)` 直接返回 `(N, D+1)` | 需包装 API |
| 开销 | 与一次预测同量级 | 有 Python 层开销 |

**工程收益**：少一个依赖、少一层 API、结果与模型版本严格一致。
**代价**：只能用于树模型（这正是"不同模型选不同解释方法"的原因）。

### 6.2 Integrated Gradients：路径离散积分

`core/models/mlp/mlp.py`：

```python
baseline = np.zeros_like(X)                     # 零点基线
alphas = np.linspace(0.0, 1.0, steps + 1)       # 路径离散点
for i in range(N):                              # ⚠️ 逐样本
    step_pts = b + alphas[:,None] * (x - b)     # (steps+1, D) 一次构造整条路径
    preds = model(step_tensor)                  # 一次前向覆盖全部路径点 ✅
    grads = torch.autograd.grad(preds.sum(), step_tensor)[0]
    avg_grads = np.mean(grads[:-1], axis=0)     # 梯形法近似积分
    ig = diff * avg_grads                       # 完备性: Σ IG == f(x) - f(b)
```

**优化点与残留瓶颈**：

| 设计 | 评价 |
|---|---|
| **路径点批量前向**（`steps+1` 个点在一次 `model()` 调用中） | ✅ 关键优化：把 `steps` 次前向压成 1 次 |
| `torch.autograd.grad` 而非 `loss.backward()` | ✅ 不构筑计算图残留，梯度直接返回 |
| `grads[:-1]` 去掉末点 | ✅ 梯形法端点处理正确 |
| **`for i in range(N)` 逐样本** | ⚠️ 残留瓶颈：636 样本 = 636 次前向 |
| `torch.no_grad()` 未在外层包裹 | ✅ 正确——IG 必须保留梯度 |

**为什么逐样本**：不同样本的 `(steps+1, D)` 形状相同，**理论上可合并为
`(N, steps+1, D)` 一次前向**。当前未做，是明确的优化空间（内存换速度）。
steps 取值：MLP **30**、CNN 默认 **25**、CNN 调用处 **20**。

### 6.3 ISM：批量生成的代价与优化

`core/models/cnn/cnn.py:284-311`：

```python
base_preds = model(X)                          # 基准：1 次全批前向
for l in range(L):                             # 23
    for c in range(C):                         # 8
        X_mut = X.copy()                       # 复制整批 (N,23,C)
        X_mut[:, l, c] = np.where(X_mut[:, l, c] > 0, 0.0, 1.0)
        mut_preds = model(X_mut)               # 全批前向
        ism_deltas[:, l, c] = np.abs(mut_preds - base_preds)
```

**计算量**：`L × C = 23 × 8 = 184` 次**全批**前向（不是 184×N 次单样本前向）。

**为什么这样是好设计**：
- **批量在样本维**（`X` 是整个测试集）→ 每次前向都被 GPU 充分利用，
  避免 184×N 次小前向的启动开销。
- 对 N=636 的测试集，184 次全批前向 ≈ 184 次 batch 前向，
  远快于"逐样本 × 逐位点"的 117 000 次前向。

**残留问题（审计发现）**：
1. **内层循环未向量化**：可改为一次性构造 `(L*C, N, L, C)` 的扰动张量并单次前向
   （内存换速度）。当前 184 次循环在 Python 层，每次有 `X.copy()` 的
   `N×23×8` 内存拷贝开销。
2. **`X.copy()` 每次全量复制**：184 × 636×23×8 × 4 B ≈ **82 MB 的冗余拷贝**（实测单次 457 KB × 184），
   可用"原地改动 + 改回"（in-place swap）避免。
3. **算子语义**：单通道翻转对 one-hot 序列通道会产生分布外输入
   （该位点全 0 或两个 1），**不等价于碱基替换**。项目为此另写了真替换实现
   （`position18_signed_substitution_ism.py`）用于方向性结论——**这是正确的科学处理**。

**均值/标准差**：`mean_ism = mean over samples`、`std_ism = std over samples` →
`ISM_SNR = mean/(std+1e-12)`。注意因为 `|Δ|` 已提前取过，此处 `std` 作用于 `|Δ|`，
故 CNN 的 SNR 是**标准形式**，与 MLP/XGBoost 的**混合形式**不同（代码与论文均已注明）。

### 6.4 归因白名单（防止越界解释）

`core/xai/importance/xai_importance.py` 定义每个模型**允许输出**的归因列：

```python
"cnn": ["CNN_IG", "CNN_ISM", "ISM_SNR"],
"linear": ["Linear_Coefficient", "SE", "t_stat", "p_value", "FDR"],
```

并用 `export_feature_table(model_key, df, rename=...)` 在**写出前强制裁剪**：
未列入白名单的列（如 Attention 熵、Gain/Cover）**不会落盘**。

**为什么这是工程亮点**：它把"科学纪律"变成**代码约束**而非文档约定。
深度模型没有经典参数检验前提，因此白名单里**没有 p/FDR 列**——
从数据结构层面杜绝了"对 CNN 归因报 p 值"这类越界解释。

---

## 七、代码中的高级 Python 技巧

| 技巧 | 使用位置 | 解决的问题 | 若没有会怎样 |
|---|---|---|---|
| **`@dataclass(frozen=True)`**（37 处） | `analysis/config.py`（10 类）、`analysis/plans.py`（9）、`analysis/schemas.py`（7）、`workflows/orchestrator/steps.py`（2） | 结构化配置/结果；`frozen` 保证阈值不被运行时改写 | 用裸 dict → 键名拼写错误、阈值可被意外覆盖 |
| **`@property`**（`steps.py` 10 处、`crispron_adapter.py` 4、`validate_feature_schema.py` 1） | `PipelineContext.data_path` / `raw_data_path` / `feature_config_path` | 把"路径推导"变成声明式属性，调用方写 `ctx.data_path` 而非调函数 | 路径拼装散落各处，改目录约定要改很多点 |
| **`@classmethod` / `from_dict`** | `steps.py:PipelineContext.from_dict`、`CrispronInput` | 多来源构造（CLI / dict / 默认）统一 | 重复的构造分支 |
| **类型提示**（`->` / `: Type`，69 文件用 `typing`） | `core/common/paths.py`（9 处）、`cell_line_division.py`（23）、`crispron_adapter.py`、`validate_feature_schema.py` | 静态可读性、IDE 检查、`x: Dict[str, List[Path]]` 自文档 | 接口语义靠注释，易误用 |
| **`pathlib.Path`**（117 文件） | 全面替代 `os.path` | 跨平台路径、`/` 运算符拼接、`.rglob()` 递归 | 字符串拼路径 → Windows/Linux 不兼容 |
| **`argparse` + `RawDescriptionHelpFormatter` + `epilog`**（29 文件） | `feature_engineering.py`、`train.py`、`data_digging.py`、`predict.py`、`validate_feature_schema.py` | CLI 自文档化，示例直接写在 `--help` | 用户必须读源码才能调用 |
| **`f-string` + 多行报错** | `core/common/paths.py:resolve_dataset` 的"列出可用数据集"错误 | 失败时给出可操作的下一步 | 只报 `FileNotFoundError`，用户不知怎么修 |
| **`np.errstate` 上下文** | `bootstrap.py` 的 R² 计算 | 抑制除零警告但保留 NaN 语义 | 警告刷屏，且易被误当错误 |
| **`copy.deepcopy(state_dict())` 条件执行** | 三个 torch 模型 | 只保存 best epoch 权重 | 每 epoch 深拷贝 → 显存与时间浪费 |
| **`ThreadPoolExecutor` + `subprocess`** | `data_digging.py:688`、`wt_position18_selection.py` | 并发调度实验，每实验独立进程 | 串行慢；同进程跑多实验会互相污染状态 |
| **`hashlib` 内容指纹** | `train.py:57,93,102` | 把数据/代码/环境变成可比对的短串 | 只能靠文件名与时间戳判断来源 |
| **`importlib.util.find_spec`** | `tests/workflow/test_readme_commands.py` | 静态验证 README 里 `python -m` 的模块存在 | 文档漂移无法发现 |
| **延迟导入（函数内 import）** | `steps.py:107` 的 `from core.common.paths import resolve_dataset`；`position18_signed_substitution_ism.py:201` | 避免循环导入、避免重依赖在轻路径加载 | 循环 import 报错 |
| **单例日志器** `getLogger(f"CNN_{log_path}")` | 三个 torch 模型 | 逐 run 独立日志文件 | 多 run 日志串流 |
| **`pickle` + JSON 双通道持久化** | 线性模型（`.pkl` 权重 + `_model.json` 可读权重） | 机器用 pickle、人读 JSON | 只能用二进制，无法人工核查 |

### 7.1 明确**未使用**的 Python 特性

| 特性 | 状态 | 说明 |
|---|---|---|
| `contextlib.contextmanager` | ❌ 0 处 | 无自定义上下文管理器（文件操作直接用 `open()`/`Path.read_text()`） |
| `functools.lru_cache` | ❌ 0 处 | 用自实现 `_COUNT_CACHE` dict |
| `functools.partial` / `wraps` | ❌ 0 处 | — |
| **装饰器（自定义）** | ❌ 0 处 | **无日志/计时/缓存装饰器**；日志与计时均在函数体内手写 |
| `multiprocessing` / `ProcessPoolExecutor` | ❌ 0 处 | 用 `ThreadPoolExecutor` 起 `subprocess` |
| `asyncio` | ❌ 0 处 | 不需要 |

**审计评价**：缺少自定义装饰器意味着**计时/日志逻辑重复**。例如每个模型的
训练循环都各自写 `logging.info` 与 epoch 计时。若引入 `@timed` / `@logged`
装饰器可显著减少重复。这是**中低优先级**的可维护性改进。

---

## 八、项目性能优化地图

```
┌─────────────────────────────────────────────────────────────────────┐
│ 数据层 (Data Layer)                                                  │
├─────────────────────────────────────────────────────────────────────┤
│ ① NumPy 张量构造      np.zeros((23,C)) + 下标置 1（非逐位拼接）        │
│ ② 向量化统计          (B,n) 计数矩阵 + BLAS matvec → 实测 8.2×        │
│ ③ 计数矩阵缓存        _COUNT_CACHE[(n,B,seed)] → 37.3s 降到 0.022s   │
│ ④ 中间结果缓存        .npy 特征(18) / 5 802 模型文件 / summary CSV    │
│ ⑤ Pandas 聚合         groupby(105) / pivot_table(10) 替代嵌套循环     │
│ ⑥ ⚠️ 未用 Parquet     全 CSV（read_csv 107 / to_csv 87）              │
│ ⑦ ⚠️ 未用 categorical  122 处 astype，未做类别 dtype 优化             │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 模型层 (Model Layer)                                                 │
├─────────────────────────────────────────────────────────────────────┤
│ ① GPU 迁移            model.to(device) + 张量一次性搬迁；960 run 全 CUDA│
│ ② DataLoader 批训练   batch 64(网格)/256(ultimate)；shuffle 正确区分   │
│ ③ 路径点批量 IG       (steps+1, D) 一次前向 → 省 steps 倍前向         │
│ ④ ISM 样本维批量      184 次全批前向（非 184×N 次单样本）             │
│ ⑤ 早停 + best 回滚    patience=20 / min_delta=1e-6 / deepcopy 条件执行│
│ ⑥ 闭式解             线性用 pinv 解析解，无迭代                        │
│ ⑦ 原生 TreeSHAP       无第三方 shap 依赖                              │
│ ⑧ ❌ 无 AMP           未用 autocast/GradScaler（模型小，取舍合理）     │
│ ⑨ ❌ 无 pin_memory    异步 H2D 拷贝未启用                             │
│ ⑩ ⚠️ IG 样本维循环    for i in range(N) 为残留瓶颈                    │
│ ⑪ ⚠️ 不支持 resume    checkpoint 不含 optimizer state / epoch         │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 分析层 (Analysis Layer)                                              │
├─────────────────────────────────────────────────────────────────────┤
│ ① 向量化 bootstrap    matvec + 充分统计量 + 多指标共用一次重采样       │
│ ② Sign-flip 置换      向量化 ±1 生成；(count+1)/(B+1) 平滑            │
│ ③ 向量化 FDR          argsort + minimum.accumulate（保持单调）        │
│ ④ ANOVA 设计矩阵      Type-II 边际 SS + 区组；不足即 unavailable      │
│ ⑤ 并发调度            1344 实验 ThreadPoolExecutor + subprocess 隔离  │
│ ⑥ GPU 轮转绑定        worker_slot % len(gpu_ids) → CUDA_VISIBLE_DEVICES│
│ ⑦ 只读产物协作        读 *_predictions.csv / *_metrics.json，零模型耦合│
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 工程层 (Engineering Layer)                                            │
├─────────────────────────────────────────────────────────────────────┤
│ ① 配置驱动（特征）    feature_config.json → 新增轨道零代码改动 ✅      │
│ ② 配置驱动（数据集）  datasets.json + paths.py 三个读取器 ✅          │
│ ③ ⚠️ 阈值在 .py        AnalysisConfig 为 frozen dataclass，需改代码   │
│ ④ 单向分层            core ← workflows / analysis（core 上层依赖 0）✅ │
│ ⑤ 结果文件即接口      产物为唯一跨层契约，替换模型不影响分析 ✅        │
│ ⑥ 四类指纹            data/code/env/split_digest，逐 run 落盘 ✅      │
│ ⑦ 归因白名单          越界列无法落盘（代码级科学纪律）✅              │
│ ⑧ 运行期自证          划分重叠非零即抛错；split_digest 可复核 ✅      │
│ ⑨ CLI 自文档          29 个 argparse 入口，示例写在 epilog            │
│ ⑩ 测试护栏            515 passed；含 schema/CLI/README 一致性测试     │
│ ⑪ ⚠️ set_seed 重复     三份实现，改一处会静默不一致                    │
│ ⑫ ⚠️ 无自定义装饰器    计时/日志重复，缺 @timed/@logged               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 九、代码质量评价：工程成熟度

评级标准：**A（优秀）/ B（良好）/ C（可用但有明显缺口）**

### 1. 可维护性 — **B+**

| 加分 | 减分 |
|---|---|
| 单向分层（`core` 对上层 0 依赖）实测严格成立 | `set_seed` 在 3 个模型中重复实现 |
| 37 个 `@dataclass` 结构化配置，阈值单一来源 | 无自定义装饰器 → 计时/日志在各模型重复 |
| 命名一致（`*_info.txt` / `*_metrics.json` / `*_feature_importance.csv`） | `analysis/config.py` 阈值改动需编辑代码 |
| 172 文件 / 46 400 行，模块边界清晰 | 部分长文件（`cell_environment_combination.py` 超 1 800 行） |
| 中文注释解释"为什么"（如 sign-flip 陷阱、精度取舍） | — |

### 2. 可扩展性 — **A−**

| 加分 | 减分 |
|---|---|
| 新增数据集：改 1 个 JSON + 放数据，**零代码** | 新增统计阈值需改 `.py` |
| 新增环境通道：改 `feature_config.json`，编码器按 `type` 分派 | 新增模型仍需在 `train.py` 注册（可接受） |
| 新增模型：`core/models/<name>/` + 注册；分析层零改动 | — |
| 三层正交架构（core / workflows / analysis） | — |

### 3. 运行效率 — **B**

| 已优化 | 未优化 |
|---|---|
| 向量化 bootstrap（**实测 8.2×**）+ 计数矩阵缓存（**37.3s → 0.022s**） | **无 AMP**（模型小，取舍合理） |
| 样本维批量 IG / ISM | **IG 样本维 Python 循环**（可合并为 (N,steps+1,D)） |
| 早停 + 条件 deepcopy | **ISM 每次 `X.copy()`** ≈ 82 MB 冗余拷贝 |
| 并发 + GPU 轮转调度 | **ISD 内层 L×C 循环**未合并为单次前向 |
| 缓存中间产物 | **无 pin_memory**；**全 CSV 无 Parquet** |

### 4. 科研可重复性 — **A**

本项目**最强的一环**：

- 四类指纹（data / code / env / `split_digest`）逐 run 落盘，且 `env_stack_id` 有意排除 `cvd`
- 种子完整：Python / numpy / torch / cuda + `cudnn.deterministic=True` + `benchmark=False`
- 划分运行期自证：重叠非零即抛错；`split_digest` 可事后逐条复核
- 身份类定义（`min(seq, revcomp)`）防止同源泄漏
- 测试集 / 验证集口径在**文件名层面**区分，并被代码强制
- 权威批次验收：1 344/1 344、重叠 0、digest 0 不一致、单一环境栈
- 独立复核：与官方划分无关的 5 折 CV + 标签置换零分布

### 5. 工程规范性 — **B+**

| 加分 | 减分 |
|---|---|
| 515 passed / 32 skipped，含 schema / CLI / README 一致性测试 | 无 `pyproject.toml` / `setup.py`（以脚本方式运行） |
| 依赖清单三份（frozen / hpc / 宽松）+ 环境指纹 | 无 `pre-commit` / `ruff` / `mypy` 配置（未接入 lint） |
| CLI 全部 `--help` 自文档化并带示例 | 无 CI 配置文件（未见 `.github/workflows/`） |
| 无硬编码绝对路径（实测 0 处） | 未使用结构化日志（`logging` 仅 5 文件） |
| 失败返回非零退出码（已修复 `collect_results`） | `_COUNT_CACHE` 无上限（长期运行内存增长） |

### 综合评分

| 维度 | 评级 |
|---|---|
| 可维护性 | **B+** |
| 可扩展性 | **A−** |
| 运行效率 | **B** |
| **科研可重复性** | **A** |
| 工程规范性 | **B+** |

**总体定位**：**科研软件中的上游水平**。可重复性达到 A 级（指纹 + 种子 + 划分自证
+ 产物即接口这一组合在学术项目中相当少见）；分层架构与配置驱动达到 A−；
运行效率为 B（瓶颈不在算法而在若干未向量化的循环与未启用的 AMP/pin_memory）；
规范性为 B+（缺 CI / lint / 打包元数据）。

**最影响结论可信度的设计（值得保留）**：四类指纹 + `split_digest` + 运行期重叠断言
+ 归因白名单。这四项把"科学纪律"从文档约定变成了**代码约束**。

---

## 十、优先改进建议（按投入产出比排序）

| 优先级 | 项 | 预期收益 | 风险 |
|---|---|---|---|
| **P1** | IG 样本维向量化：`(N, steps+1, D)` 单次前向 | 前向次数从 N 降到 1（→ 数十倍） | 内存随 N 线性增长，需分批 |
| **P1** | ISM 内层 `L×C` 合并为单次批量前向 + 去掉 `X.copy()` | 省 82 MB 拷贝与 184 次 Python 循环 | 需构造 `(L*C, N, L, C)` 张量，注意显存 |
| **P1** | `set_seed` 提取到 `core/common/` 单一实现 | 消除三处漂移风险 | 低 |
| **P2** | `AnalysisConfig.from_file()` 支持 JSON 覆盖 | 让阈值真正"配置驱动" | 低（保留 dataclass 默认值） |
| **P2** | `_COUNT_CACHE` 加 `maxsize` 或改 `lru_cache` | 消除长期运行的内存增长 | 低 |
| **P2** | 补 `pyproject.toml` + ruff/mypy + CI | 规范性与自动化 | 低 |
| **P3** | checkpoint 增加 `optimizer.state_dict()` + epoch | 支持断点续训 | 低 |
| **P3** | 大表改 Parquet；分类列用 `category` dtype | I/O 与内存 | 需改下游读取 |
| **P3** | 启用 `pin_memory=True`（GPU 环境） | 异步 H2D 拷贝 | 低 |
| **P3** | 引入 `@timed` / `@logged` 装饰器 | 减少重复代码 | 低 |

> **不建议**为追求"先进"而引入 AMP：当前模型小（CNN 64/64/128、Transformer d=64），
> 真正的成本中心是**1344 次实验的调度**而非单次训练速度。上 AMP 的复杂度收益比不佳。
