#!/usr/bin/env bash
# CRISPR Scientific Workspace 本地启动 (后端 API + 前端 dev server)
# 依赖: Python3(标准库) + Node/npm(frontend)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # scripts/ 的上一级 = 项目根
PORT_BACK="${PORT_BACK:-8765}"
PORT_FRONT="${PORT_FRONT:-5173}"
WS_ROOT="${CRISPR_WORKSPACE_ROOT:-$ROOT/workspace}"
WS_LOG_DIR="$ROOT/logs/workspace"
mkdir -p "$WS_LOG_DIR"

# 1) 后端
PYTHONPATH="$ROOT/backend" python3 -m crispr_workspace.server \
  --port "$PORT_BACK" --root "$WS_ROOT" > "$WS_LOG_DIR/backend.log" 2>&1 &
BACK_PID=$!
echo "[backend] http://127.0.0.1:$PORT_BACK  (pid $BACK_PID, root=$WS_ROOT)"

# 2) 前端 (确保依赖已安装)
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "[frontend] npm install ..."
  (cd "$ROOT/frontend" && npm install --no-audit --no-fund)
fi
(cd "$ROOT/frontend" && npm run dev -- --port "$PORT_FRONT") > "$WS_LOG_DIR/frontend.log" 2>&1 &
FRONT_PID=$!
echo "[frontend] http://127.0.0.1:$PORT_FRONT (pid $FRONT_PID)"

trap 'echo; echo "stopping..."; kill $BACK_PID $FRONT_PID 2>/dev/null || true' EXIT INT TERM
echo "打开浏览器: http://127.0.0.1:$PORT_FRONT  (Ctrl+C 退出)"
wait
