"""Artifact Resolver / 预览服务。

只做: 路径解析(限白名单根内) + 类型识别 + CSV/Markdown/JSON 预览读取。
不做任何科学计算; 格式化(科学记数/方向/Evidence Badge)由前端基于原始值完成。
"""
from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config

PREVIEW_ROWS = 200
MAX_BYTES = 256 * 1024 * 1024  # 超过此大小直接提示后端截断/分页, 不整读


class ArtifactError(Exception):
    pass


def _confine(path: Path, roots: List[Path]) -> Path:
    p = path.resolve()
    for r in roots:
        try:
            p.relative_to(r)
            return p
        except ValueError:
            continue
    raise ArtifactError(f"path outside allowed artifact roots: {path}")


def classify(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv"):
        return "csv"
    if suffix in (".md", ".markdown", ".txt"):
        return "md" if suffix in (".md", ".markdown") else "txt"
    if suffix == ".json":
        return "json"
    if suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        return "image"
    if suffix in (".log",):
        return "log"
    return "other"


def _sniff_numeric(raw: str) -> Optional[str]:
    """轻量类型探测: 仅用于展示提示; 原始值不回写。"""
    s = raw.strip()
    if s in ("", "NA", "NaN", "nan", "null", "None", "-"):
        return "missing"
    try:
        float(s)
        return "float" if any(c in s for c in ".eE") else "int"
    except ValueError:
        return "text"


def resolve_artifact(rel_or_abs: str,
                     base_dirs: Optional[List[str]] = None,
                     offset: int = 0,
                     limit: Optional[int] = None) -> Dict[str, Any]:
    """解析一个 artifact 并返回其展示所需内容。

    rel_or_abs: 绝对路径, 或相对某 allowed root 的路径;
    base_dirs: 额外允许的基准目录 (如某 project dir), 与全局白名单取并集。
    """
    roots = [Path(r) for r in config.allowed_read_roots()]
    for b in (base_dirs or []):
        roots.append(Path(b).resolve())

    p = Path(rel_or_abs)
    if not p.is_absolute():
        # 相对路径: 依次相对 workspace 根 / 仓库根 / 各 allowed root 尝试
        candidates = [config.default_workspace_root() / rel_or_abs,
                      config.repo_root() / rel_or_abs] + \
                     [r / rel_or_abs for r in roots]
        hit = None
        for cand in candidates:
            if cand.exists():
                hit = cand
                break
        if hit is None:
            raise ArtifactError(f"artifact not found: {rel_or_abs}")
        p = hit

    p = _confine(p, roots)
    if not p.exists() or not p.is_file():
        raise ArtifactError(f"not a file: {p}")

    size = p.stat().st_size
    kind = classify(p)
    meta = {
        "path": str(p),
        "name": p.name,
        "kind": kind,
        "size": size,
        "mtime": p.stat().st_mtime,
    }

    if kind == "csv":
        return {**meta, **_csv_payload(p, offset=int(offset or 0), limit=limit)}
    if kind in ("md", "txt"):
        if size > MAX_BYTES:
            raise ArtifactError("file too large to preview")
        return {**meta, "text": p.read_text(encoding="utf-8", errors="replace")}
    if kind == "json":
        if size > MAX_BYTES:
            raise ArtifactError("file too large to preview")
        obj = json.loads(p.read_text(encoding="utf-8"))
        return {**meta, "json": obj}
    if kind == "image":
        return meta  # 图片走 /api/artifact-raw 二进制
    return {**meta, "text": ""}


def _csv_payload(p: Path, offset: int = 0,
                 limit: Optional[int] = None) -> Dict[str, Any]:
    """流式 CSV 预览/分页: 先扫总数(不全量载入内存), 再取目标区间行。"""
    delim = "," if p.suffix.lower() == ".csv" else "\t"
    want = int(limit or PREVIEW_ROWS)
    with open(p, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(io.StringIO(f.read(256 * 1024 * 1024)), delimiter=delim)
        header: List[str] = []
        rows: List[List[str]] = []
        total = 0
        first = True
        for row in reader:
            if not row:
                continue
            if first:
                header = row
                first = False
                continue
            total += 1
            if offset <= total - 1 < offset + want:
                rows.append(row)
    cols = header or ([f"col{i}" for i in range(max((len(r) for r in rows), default=0))])
    hints = []
    for c in range(len(cols)):
        values = [r[c] for r in rows[:50] if c < len(r)]
        num = sum(1 for v in values if _sniff_numeric(v) in ("float", "int"))
        hints.append("numeric" if values and num >= max(1, len(values) // 2) else "text")
    return {
        "data_rows": total,
        "offset": offset,
        "limit": want,
        "columns": cols,
        "rows": rows,
        "type_hints": hints,
        "truncated": (offset + len(rows)) < total,
        "row_limit": want,
    }
