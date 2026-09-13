"""配置与路径策略 (跨平台, 无硬编码实验室路径)。"""
from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent   # .../Submit


def repo_root() -> Path:
    return _REPO_ROOT


def default_workspace_root() -> Path:
    """默认工作根 = <仓库>/workspace; 可用环境变量 CRISPR_WORKSPACE_ROOT 覆盖。"""
    env = os.environ.get("CRISPR_WORKSPACE_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return _REPO_ROOT / "workspace"


def config_root() -> Path:
    """用户级配置目录 (如 HPC 根目录、runtime 偏好)。"""
    env = os.environ.get("CRISPR_WORKSPACE_CONFIG", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(os.path.expanduser("~")) / ".crispr_workspace"


def ensure_dirs(root: Path) -> None:
    for sub in ("projects", "qc_sessions", "runs"):
        (root / sub).mkdir(parents=True, exist_ok=True)


def allowed_read_roots() -> list:
    """Artifact Resolver 允许读取的根 (防止任意路径读取)。

    允许: workspace 根 (projects/qc_sessions/runs/analysis 输出等都由后端写在根下)
    + 仓库内已有训练结果目录 results。前端展示的文件必须落在这几个根之内。
    """
    ws = default_workspace_root()
    roots = [ws]
    repo = repo_root()
    for candidate in ("results",):
        p = repo / candidate
        if p.exists():
            roots.append(p)
    return [r.resolve() for r in roots]
