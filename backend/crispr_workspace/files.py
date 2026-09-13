"""项目文件浏览与读取（前端"文件查看器"用）。

安全边界
--------
* 只允许读取**仓库根目录之内**的路径；``..`` 逃逸、绝对路径越界一律拒绝。
* 拒绝敏感/噪音目录：``.git``、``.venv``、``node_modules``、``__pycache__``、``dist``。
* 文本按大小截断（默认 512 KB），二进制只返回元数据（图片可走 ``raw_path`` 直接取字节）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config

DENY_DIRS = {".git", ".venv", "node_modules", "__pycache__", "dist", ".npm_tmp",
             ".pytest_cache", ".mypy_cache", ".ruff_cache"}
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".tsv", ".json", ".log", ".yaml", ".yml", ".tex",
                 ".bib", ".py", ".ts", ".tsx", ".js", ".jsx", ".sh", ".cfg", ".ini", ".toml",
                 ".html", ".css", ".rst", ".ipynb"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
MAX_TEXT_BYTES = 512 * 1024
MAX_RAW_BYTES = 8 * 1024 * 1024


class FileAccessError(ValueError):
    pass


def _root() -> Path:
    return config.repo_root().resolve()


def resolve(rel: str, must_exist: bool = True) -> Path:
    """把仓库相对路径解析为绝对路径，并做越界/敏感目录检查。"""
    raw = (rel or "").strip()
    if raw in ("", ".", "./"):
        p = _root()
    else:
        candidate = Path(raw)
        if candidate.is_absolute():
            p = candidate
        else:
            p = _root() / candidate
    try:
        p = p.resolve()
    except OSError as exc:  # pragma: no cover
        raise FileAccessError(f"cannot resolve path: {rel}") from exc
    root = _root()
    if p != root and root not in p.parents:
        raise FileAccessError(f"path outside project root: {rel}")
    rel_parts = p.relative_to(root).parts
    for part in rel_parts:
        if part in DENY_DIRS:
            raise FileAccessError(f"path is excluded: {part}")
    if must_exist and not p.exists():
        raise FileAccessError(f"not found: {rel}")
    return p


def _rel(p: Path) -> str:
    root = _root()
    return str(p.relative_to(root)) if p != root else "."


def _kind(p: Path) -> str:
    if p.is_dir():
        return "dir"
    suf = p.suffix.lower()
    if suf in IMAGE_SUFFIXES:
        return "image"
    if suf in TEXT_SUFFIXES:
        return "text"
    return "binary"


def list_dir(rel: str = ".", limit: int = 800) -> Dict[str, Any]:
    """列出目录内容（目录在前、按名称排序）。"""
    d = resolve(rel)
    if not d.is_dir():
        raise FileAccessError(f"not a directory: {rel}")
    entries: List[Dict[str, Any]] = []
    for child in sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        if child.name in DENY_DIRS:
            continue
        try:
            st = child.stat()
        except OSError:
            continue
        entries.append({
            "name": child.name, "path": _rel(child), "kind": _kind(child),
            "is_dir": child.is_dir(), "size": 0 if child.is_dir() else st.st_size,
            "mtime": st.st_mtime,
        })
        if len(entries) >= limit:
            break
    parent = None if d == _root() else _rel(d.parent)
    return {"path": _rel(d), "parent": parent, "entries": entries,
            "truncated": len(entries) >= limit}


def read_file(rel: str, max_bytes: int = MAX_TEXT_BYTES) -> Dict[str, Any]:
    """读取文本/JSON/CSV（截断）；图片与二进制只返回元数据 + raw 路径。"""
    p = resolve(rel)
    if p.is_dir():
        raise FileAccessError(f"is a directory: {rel}")
    st = p.stat()
    kind = _kind(p)
    base = {"path": _rel(p), "name": p.name, "kind": kind, "size": st.st_size,
            "mtime": st.st_mtime}
    if kind == "image":
        base["raw_path"] = f"/api/file-raw?path={_rel(p)}"
        return base
    if kind == "binary":
        base["note"] = "二进制文件（表格型权重/模型文件不在前端解析）"
        base["raw_path"] = f"/api/file-raw?path={_rel(p)}"
        return base

    with open(p, "rb") as fh:
        raw = fh.read(max_bytes + 1)
    truncated = len(raw) > max_bytes
    text = raw[:max_bytes].decode("utf-8", errors="replace")
    base["truncated"] = truncated
    base["text"] = text

    suffix = p.suffix.lower()
    if suffix == ".json":
        try:
            base["json"] = json.loads(text)
        except json.JSONDecodeError:
            pass
    elif suffix in (".csv", ".tsv"):
        sep = "\t" if suffix == ".tsv" else ","
        lines = text.splitlines()
        rows = [ln.split(sep) for ln in lines[:201]]
        base["columns"] = rows[0] if rows else []
        base["rows"] = rows[1:201]
        base["data_rows"] = max(len(lines) - 1, 0)
        base["row_limit"] = 200
    return base


def raw_path(rel: str) -> Path:
    """返回可直接按字节发送的文件路径（图片/下载用）。"""
    p = resolve(rel)
    if p.is_dir():
        raise FileAccessError(f"is a directory: {rel}")
    if p.stat().st_size > MAX_RAW_BYTES:
        raise FileAccessError(f"file too large to serve: {p.stat().st_size} bytes")
    return p


def mime_for(p: Path) -> str:
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
        ".csv": "text/csv; charset=utf-8", ".tsv": "text/tab-separated-values; charset=utf-8",
        ".md": "text/markdown; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".txt": "text/plain; charset=utf-8", ".log": "text/plain; charset=utf-8",
        ".pdf": "application/pdf",
    }.get(p.suffix.lower(), "application/octet-stream")
