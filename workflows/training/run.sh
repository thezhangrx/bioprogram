#!/usr/bin/env bash
# 网格训练批量入口（超算平台用）。
#   bash run.sh              # 全量：single + all(LOCO) + mixed，共 1344 次运行
#   bash run.sh single       # 只跑 single
#   bash run.sh all          # 只跑 all（留一细胞系，train/valid=85/15，test=留出系全量）
#   bash run.sh mixed        # 只跑 mixed（4 seed）
#   WORKERS=8 bash run.sh    # 指定并发实验数（默认取 $WORKERS，未设为 4）
#
# 2026-09-13 重跑注意（P0 泄漏整改后）:
#   1) BATCH 默认改为 batch_20260913_groupaware —— **不要**复用旧的
#      batch_20260909_full：data_digging 会按「目录已存在 + info.txt + metrics.json」
#      判定该实验已完成并直接跳过，导致新旧（泄漏/无泄漏）结果混在一批里。
#   2) 起飞前先自检:  python deploy/hpc/preflight_hpc_rerun.py --package . --batch-name "$BATCH"
#   3) 跑完后验收:    python deploy/hpc/verify_hpc_rerun.py  --package . --batch-name "$BATCH"
#   4) 多卡节点 (如 8×A100): WORKERS 建议 = 可用卡数; 脚本会自动把 worker i 绑到
#      GPU 列表的第 i 个 (避免 8 个进程全挤在 0 号卡)。可用 GPUS="0 1 2 3" 覆盖。
set -euo pipefail
cd "$(dirname "$0")/../.."          # 切到项目根, 使默认相对路径生效

SPLITS="${1:-single all mixed}"
WORKERS="${WORKERS:-4}"
BATCH="${BATCH:-batch_20260913_groupaware}"
PY="${PY:-python}"
# GPUS: 并发 worker 的显卡绑定。留空 = 自动探测 nvidia-smi 后逐槽轮转绑定;
#       GPUS="0 1 2 3" 显式指定; GPUS="none" 关闭绑定。
GPUS="${GPUS:-}"
GPU_ARGS=()
if [ "${GPUS}" = "none" ]; then
  GPU_ARGS=(--gpus)
elif [ -n "${GPUS}" ]; then
  # shellcheck disable=SC2206
  GPU_ARGS=(--gpus ${GPUS})
fi

echo "[run.sh] splits=${SPLITS} workers=${WORKERS} batch=${BATCH} gpus=${GPUS:-auto} python=$("$PY" -V 2>&1)"

# 结果目录安全闸门: 非空即拒绝启动，避免复用旧批次结果。
RESULTS_DIR="results/${BATCH}"
if [ -d "${RESULTS_DIR}" ] && [ -n "$(ls -A "${RESULTS_DIR}" 2>/dev/null)" ]; then
  echo "[run.sh][FATAL] ${RESULTS_DIR} 已存在且非空 —— 会被判定为『已完成』而跳过。" >&2
  echo "[run.sh][FATAL] 请换 BATCH 名，或确认后手动清空该目录。" >&2
  exit 2
fi

exec "$PY" workflows/training/data_digging.py \
  --batch-name "${BATCH}" \
  --data-dir data/processed \
  --model-dir models/weights \
  --results-dir results/batches \
  --logs-dir results/logs \
  --split-types ${SPLITS} \
  --training-scope-epis ctcf dnase h3k4me3 rrbs \
  --workers "${WORKERS}" \
  --threads-per-worker "${THREADS_PER_WORKER:-0}" \
  "${GPU_ARGS[@]}"
