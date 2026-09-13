"""轻量 JSON 状态存取 (manifest/status 一律落盘, 前端状态从文件恢复)。"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# 阶段/任务状态语义 (前端据此上色: 绿=completed, 黄=warning, 红=failed,
# 蓝=running, 灰=pending/disabled)
STAGE_ORDER = ["data", "qc", "mapping", "training", "analysis", "reports"]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path) -> Optional[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj: Dict[str, Any]) -> Path:
    """原子写: 先写临时文件再 rename, 防止半截文件被 GUI/恢复逻辑读到。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return p
