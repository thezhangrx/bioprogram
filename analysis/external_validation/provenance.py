"""外部模型验证的 provenance 采集与 manifest 生成。

按项目既有做法采集"可追溯"所需的全部字段：软件版本、原始包文件名与 checksum、
执行命令、运行环境、依赖版本、输入文件与序列 hash、模型配置、输出文件、时间戳、
代码指纹（复用训练侧同一套 code fingerprint 定义，见 ``core/features/...`` 的
provenance 逻辑；这里用等价实现以免 import 训练栈）。

设计约束
--------
* 不读网络、不写死绝对路径；
* 每次运行产出一行 manifest（追加到 manifest.csv），便于多次运行累积对照；
* 缺失字段写 ""，不静默伪造。
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MANIFEST_COLUMNS = [
    "run_id", "stage", "timestamp_utc",
    "software", "software_version", "package_file", "package_sha256", "software_dir",
    "dependency", "dependency_version", "dependency_sha256",
    "execution_command", "conda_env", "python_version", "python_executable",
    "dependency_versions_json",
    "input_file", "input_sha256", "n_input_records", "input_sequence_sha256",
    "model_config", "output_file", "output_sha256",
    "code_fingerprint", "data_source", "batch", "notes",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_of_sequences(seqs: Iterable[str]) -> str:
    """输入序列集合的规范化 hash（排序后拼接，保证与记录顺序无关）。"""
    joined = "\n".join(sorted(str(s).strip().upper() for s in seqs))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def code_fingerprint(paths: Optional[Iterable[str | Path]] = None) -> str:
    """项目代码指纹：对外部验证相关脚本内容取 hash（与内容绑定，不随 mtime 变）。"""
    if paths is None:
        base = PROJECT_ROOT / "analysis" / "external_validation"
        paths = sorted(base.glob("*.py"))
    h = hashlib.sha256()
    for p in paths:
        p = Path(p)
        if p.exists():
            h.update(p.name.encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _pip_versions(python_exe: str, packages: List[str]) -> Dict[str, str]:
    """在指定解释器里取依赖版本（子进程执行，避免污染当前进程）。"""
    code = (
        "import json,importlib\n"
        f"names={packages!r}\n"
        "out={}\n"
        "for n in names:\n"
        "    try:\n"
        "        out[n]=getattr(importlib.import_module(n),'__version__','?')\n"
        "    except Exception as e:\n"
        "        out[n]='MISSING'\n"
        "print(json.dumps(out))\n"
    )
    try:
        proc = subprocess.run([python_exe, "-c", code], capture_output=True, text=True, timeout=120)
        return json.loads(proc.stdout.strip().splitlines()[-1]) if proc.returncode == 0 else {}
    except Exception:
        return {}


def collect_environment(python_exe: str) -> Dict[str, object]:
    packages = ["numpy", "scipy", "pandas", "Bio", "tensorflow", "keras", "sklearn", "RNA"]
    versions = _pip_versions(python_exe, packages)
    return {
        "python_version": platform.python_version(),
        "python_executable": python_exe,
        "dependency_versions_json": json.dumps(versions, ensure_ascii=False, sort_keys=True),
        "tensorflow": versions.get("tensorflow", ""),
        "viennarna": versions.get("RNA", ""),
    }


def build_manifest_row(**kw) -> Dict[str, object]:
    """按 MANIFEST_COLUMNS 生成一行；未知键进 notes。"""
    row = {c: "" for c in MANIFEST_COLUMNS}
    extra = {}
    for k, v in kw.items():
        if k in row:
            row[k] = v
        else:
            extra[k] = v
    if extra:
        row["notes"] = (str(row["notes"]) + " " + json.dumps(extra, ensure_ascii=False)).strip()
    return row


def append_manifest(path: Path, rows: List[Dict[str, object]]) -> Path:
    """把本次运行的行追加进 manifest.csv（列顺序稳定）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame(rows)
    for c in MANIFEST_COLUMNS:
        if c not in new.columns:
            new[c] = ""
    new = new[MANIFEST_COLUMNS]
    if path.exists() and path.stat().st_size > 0:
        old = pd.read_csv(path, dtype=str).fillna("")
        for c in MANIFEST_COLUMNS:
            if c not in old.columns:
                old[c] = ""
        out = pd.concat([old[MANIFEST_COLUMNS], new.astype(str)], ignore_index=True)
    else:
        out = new.astype(str)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return path
