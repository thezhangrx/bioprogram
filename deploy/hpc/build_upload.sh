#!/usr/bin/env bash
# 打包当前仓库为上传压缩包 (排除运行/环境噪音)。用法: bash deploy/hpc/build_upload.sh [输出路径]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # deploy/hpc/ -> 项目根
OUT="${1:-/tmp/Submit_upload.tar.gz}"
cd "$ROOT"
tar --exclude='./_no_upload' \
    --exclude='*/__pycache__' \
    --exclude='*.pyc' \
    --exclude='./.npm_tmp' \
    --exclude='./app/frontend/node_modules' \
    --exclude='./app/frontend/dist' \
    --exclude='./.venv' \
    --exclude='./results/logs' \
    --exclude='./.git' \
    -czf "$OUT" .
echo "[✓] 已生成: $OUT"
echo "    远端解压: cd <Submit> && tar -xzf $(basename "$OUT") (在仓库目录内解压)"
