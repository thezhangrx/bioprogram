"""目录选择服务（前端"弹窗选取目录"用）。

只返回**目录**条目（不暴露文件内容），支持任意绝对路径浏览与新建目录。
用于让用户在 Web 界面里选择"训练结果输出目标文件夹"，避免手输路径。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config

#: 不允许浏览的伪文件系统
BLOCKED = {"/proc", "/sys", "/dev", "/run"}


class FsError(ValueError):
    pass


def roots() -> List[Dict[str, str]]:
    """常用起点：用户主目录、仓库、工作区、临时目录。"""
    cands = [("主目录", Path.home()), ("项目仓库", config.repo_root()),
             ("工作区", config.default_workspace_root()), ("/tmp", Path("/tmp"))]
    out: List[Dict[str, str]] = []
    seen = set()
    for label, p in cands:
        try:
            rp = p.resolve()
        except OSError:
            continue
        if rp in seen or not rp.is_dir():
            continue
        seen.add(rp)
        out.append({"label": label, "path": str(rp)})
    return out


def _check(p: Path) -> Path:
    try:
        rp = p.expanduser().resolve()
    except OSError as exc:
        raise FsError(f"无法解析路径: {p}") from exc
    for b in BLOCKED:
        if rp == Path(b) or Path(b) in rp.parents:
            raise FsError(f"该路径不允许浏览: {rp}")
    return rp


DATA_SUFFIXES = (".csv", ".tsv", ".txt", ".xlsx")


def list_dirs(path: Optional[str] = None, include_hidden: bool = False,
              include_files: bool = False) -> Dict[str, Any]:
    """列出目录内容。

    ``include_files=True`` 时同时返回可选的**数据文件**（csv/tsv/txt/xlsx），
    用于"数据集既可以是目录也可以是单个文件"的场景；其余文件不列出。
    """
    base = _check(Path(path)) if path else _check(Path.home())
    if not base.exists():
        raise FsError(f"目录不存在: {base}")
    if not base.is_dir():
        raise FsError(f"不是目录: {base}")
    entries: List[Dict[str, Any]] = []
    try:
        children = sorted(base.iterdir(), key=lambda p: p.name.lower())
    except PermissionError as exc:
        raise FsError(f"无权限读取: {base}") from exc
    for child in children:
        if child.is_symlink():
            continue
        try:
            is_dir = child.is_dir()
        except OSError:
            continue
        if not is_dir and not (include_files and child.suffix.lower() in DATA_SUFFIXES):
            continue
        if not include_hidden and child.name.startswith("."):
            continue
        try:
            n_items = sum(1 for _ in child.iterdir())
        except OSError:
            n_items = -1
        entries.append({"name": child.name, "path": str(child.resolve()),
                        "is_dir": is_dir, "size": 0 if is_dir else child.stat().st_size,
                        "is_empty": n_items == 0})
    parent = None if base.parent == base else str(base.parent)
    return {"path": str(base), "parent": parent, "roots": roots(), "entries": entries}


def make_dir(parent: str, name: str) -> Dict[str, Any]:
    """在 parent 下新建目录（用于"新建输出文件夹"）。"""
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise FsError(f"非法目录名: {name!r}")
    base = _check(Path(parent))
    if not base.is_dir():
        raise FsError(f"父目录不存在: {base}")
    target = (base / name).resolve()
    if target.exists():
        raise FsError(f"目录已存在: {target}")
    target.mkdir(parents=True)
    return {"path": str(target), "created": True}


def suggest_output_dir(project_id: str) -> str:
    """给项目一个默认输出目录（工作区内，删除项目时会被一并清理）。"""
    return str((config.default_workspace_root() / "projects" / project_id / "output").resolve())
