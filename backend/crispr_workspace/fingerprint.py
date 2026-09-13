"""数据指纹: 判断“当前输入 == 上次 QC 的输入”, 防止错误复用旧 QC。"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Optional


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def fingerprint_dataset(paths: List[str]) -> dict:
    """对输入文件集合生成指纹 (文件 sha256 + 基本统计)。

    paths 可为文件或目录 (目录取其下 *.csv/*.tsv)。
    """
    files: List[dict] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            collected = sorted([q for q in p.glob("*") if q.suffix.lower() in (".csv", ".tsv")])
        elif p.is_file():
            collected = [p]
        else:
            continue
        for q in collected:
            try:
                files.append({
                    "name": q.name,
                    "path": str(q.resolve()),
                    "size": q.stat().st_size,
                    "sha256": file_sha256(q),
                })
            except OSError:
                continue
    files.sort(key=lambda x: x["path"])
    digest = hashlib.sha256()
    for f in files:
        digest.update(f["path"].encode("utf-8"))
        digest.update(f["sha256"].encode("ascii"))
    return {
        "algorithm": "sha256",
        "digest": digest.hexdigest(),
        "files": files,
        "n_files": len(files),
        "total_bytes": int(sum(f["size"] for f in files)),
    }


def same_fingerprint(a: Optional[dict], b: Optional[dict]) -> bool:
    if not a or not b:
        return False
    return bool(a.get("digest")) and a["digest"] == b.get("digest")
