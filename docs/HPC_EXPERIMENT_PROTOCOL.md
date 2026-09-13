# HPC 正式实验运行协议 (CRISPR 项目)

> 目标：在 gpu3（8×A100-80GB）上把 1344 个实验稳定、可续跑、可复现地跑完。
> 依据：本仓库已完成的性能工作（PERF_REPORT.md）与本会话验证的安全结论：
>   - `--in-process`（进程内顺序执行）在 CPU 上 80 实验跨 cells/envs/splits 与原子进程**逐位一致**，
>     并消除每实验 python 启动/import 开销 → 推荐默认执行方式。
>   - 未授权任何可能改变数值的优化：`--threads-per-worker` 默认关闭、CNN ISM/IG 向量化未启用。
>   - GPU 上的逐位一致性需在 gpu3 上**重新验证**（GPU 浮点可能微小抖动，宜用指标级容差回归）。

## 0. 前置准备（一次性）

```bash
# gpu3 上激活环境（勿用 /home 前缀路径）
conda activate /data9/zhanghaohong/zhangrixing/.conda/envs/crispr
cd /data9/zhanghaohong/zhangrixing/Submit

# 数据必须存在于 gpu3（如缺失，从 master 同步 data/proceeded_data）
ls data/proceeded_data/*.npy >/dev/null || echo "需要同步数据"

# 环境/GPU 探针
python -c "import torch;print(torch.__version__, torch.cuda.is_available(), torch.cuda.device_count())"
nvidia-smi   # 查看 GPU-Util / Memory / Processes，选择空闲卡
```

## 1. （可选但推荐）GPU 单实验分阶段 profiling

每模型族各跑一次代表性实验，先得到 GPU 端真实数字与瓶颈：
```bash
CUDA_VISIBLE_DEVICES=7 python profile_experiment.py --model transformer --epochs 2 --device cuda
CUDA_VISIBLE_DEVICES=7 python profile_experiment.py --model cnn        --epochs 2 --device cuda
CUDA_VISIBLE_DEVICES=7 python profile_experiment.py --model mlp        --epochs 2 --device cuda
# linear / xgboost 主要为 CPU 计算，可选
```
观察 load/train/validation/test/explanation/save 各阶段；据此决定是否 8 卡并行即可满足时间预算。

## 2. 正式批量（1344 实验）：8×A100 各跑一片，共享同一 batch

策略：**一个 GPU 一个 data_digging 进程 + `--in-process` 顺序执行**（不在单卡内并发抢卡）；
按 16 个环境组合切成 8 片（每片 2 个 env），每片跑全部 models/cells/splits → 每卡 168 实验。
> 已测数据网格挖掘程序已自 predict.py 拆分为 **data_digging.py**；
> predict.py 只负责 mixed 十折 CV + 目标待测数据集预测（见 §5）。
脚本见仓库：`HPC_launch_full_batch.sh`（内容示例）：
```bash
for i in 0 1 2 3 4 5 6 7; do
  CUDA_VISIBLE_DEVICES=$i nohup python data_digging.py \
    --batch-name full \
    --data-dir data/proceeded_data \
    --results-dir results --model-dir models --logs-dir logs \
    --models linear xgboost mlp transformer cnn \
    --cell-lines hct116 hek293t hela hl60 \
    --split-types single all mixed \
    --environments ${ENV_SLICE[$i]} \
    --in-process \
    > logs/batch_gpu$i.log 2>&1 &
done
```
要点：
- 8 片环境集合互不重叠且并集=16 组合（含 `all`）。
- 共享同一 `--batch-name full` → 所有产物收敛到 `results/full`，天然支持**断点续跑**：
  中断后重跑同一命令，已完成实验会被自动跳过（data_digging 自带 completed 判定）。
- 只读校验：`tail -f logs/batch_gpu*.log`；`nvidia-smi` 观察各卡。

## 3. 运行期监控与续跑

```bash
nvidia-smi -l 10                       # 观察显存/利用率/进程
grep -c "Finished Successfully" logs/batch_gpu*.log   # 进度
# 失败/中断后直接重跑第 2 步命令即可续跑剩余实验
```
若某进程崩溃（内存等），重跑该片命令；已完成目录不会重复训练。

## 4. 跑完后的分析管线（CPU，可在 master 或任一节点执行）

```bash
cd /data9/zhanghaohong/zhangrixing/Submit
# 4.1 汇总评测指标（按需限制 split，与实验一致）
python analyse/collect_results.py --batch-dir results/full --split-types single all mixed
# 4.2 异常检测
python analyse/anomaly_treatment.py --batch-dir results/full
# 4.3 特征重要性/白名单提取 + key_regulatory_biomarkers.csv
python analyse/importance_extraction.py --batch_dir results/full
# 4.4 图表（热图/环境增量树/表观对比）
python analyse/visualization.py --batch-dir results/full
```

## 5. 赛道二候选与终极模型（batch 完成后执行一次, 目标数据集预测）

> predict.py 已只保留 Ultimate mixed 十折 CV + 目标预测: 按目标【实际具备】的表观通道
> (--target-epigenetics) 裁剪 mixed 十折训练输入后训练并预测, 保证训练/预测特征空间一致;
> 线性终极模型与 data_digging 网格 LR 相同地剔除 _T 参照列 (T 为基准)。

```bash
CUDA_VISIBLE_DEVICES=0 python predict.py \
  --batch-name full \
  --data-dir data/proceeded_data \
  --results-dir results \
  --models linear xgboost mlp transformer cnn \
  --cell-lines hct116 hek293t hela hl60 \
  --target-input /path/to/待测数据集.csv \
  --target-epigenetics CTCF Dnase H3K4me3 RRBS
```
（对目标数据集做 10 折 CV 选超参 + 全量重训 + 真实预测共识, 输出
`results/full/summary/赛道二_results.csv`；模型参数保存于 summary/ultimate/。
不带 `--target-input` 时兼容旧用法: 对 mixed 已测池自身 Top-K。）

## 6. GPU 端一致性验证（建议在正式全量前先做一次）

```bash
# 用 regression_compare 的自定义目录模式对比两个批次
python regression_compare.py --quick --epochs 1          # CPU 快速回归（本地已 PASS）
# GPU 上因浮点特性，同一命令两次也可能有 ~1e-7 级差异：
# 对比时应采用指标级容差（|ΔR2|<1e-6 等），不要以“逐位相同”为唯一标准。
```

## 7. 纪律与红线（沿用本项目结论）

- 不修改模型结构/实验设计/seed/超参/early-stopping/评价指标。
- `--threads-per-worker`（线程封顶并发）默认不启用；CNN ISM/IG 向量化未授权前不启用。
- 正式结果以本协议配置为准；任何候选优化先在小样本上验证“不改变科学结论”再议。

## 8. 环境锁与备份

正式开跑前后把环境锁文件提交入库（见 HPC_ENVIRONMENT.md §8）：
```bash
conda env export -n crispr > environment.yml
python -m pip freeze > requirements-hpc.txt
```
