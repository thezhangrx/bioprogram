"""Standalone / Workflow Data QC 会话管理。

QC 引擎只有一个 (analysis/data_QC.py, 只读 CPU 体检): 本服务以子进程调用之,
与项目生命周期解耦。会话输出目录:
    <workspace>/qc_sessions/qc_YYYYmmdd_HHMMSS/
        session_manifest.json   (输入/指纹/状态/产物路径)
        qc_summary.json         (引擎输出, 机器可读)
        quality_report.md       (引擎输出)
        figures/*.png
复用规则: 仅当输入文件指纹与旧会话一致时才允许复用, 防止换数据后误用旧 QC。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import config, fingerprint, store

MANIFEST = "session_manifest.json"
ENGINE = Path("analysis") / "data_QC.py"


def _copy_inputs(src: List[str], dst: Path) -> List[str]:
    """输入可为文件或目录; 目录内取 csv/tsv。多来源散落时统一暂存到会话 inputs_src。"""
    collected: List[Path] = []
    for raw in src:
        p = Path(raw)
        if p.is_dir():
            collected += sorted(q for q in p.glob("*")
                                if q.suffix.lower() in (".csv", ".tsv"))
        elif p.is_file():
            collected.append(p)
    if not collected:
        raise ValueError("no dataset file given")
    if len(collected) == 1 and collected[0].parent == dst:
        return [str(collected[0])]
    if len(collected) == 1:
        return [str(collected[0])]
    staging = dst / "inputs_src"
    staging.mkdir(parents=True, exist_ok=True)
    names = set()
    out = []
    for q in collected:
        name = q.name
        i = 1
        while name in names:
            stem, suffix = q.stem, q.suffix
            name = f"{stem}_{i}{suffix}"
            i += 1
        names.add(name)
        shutil.copy2(q, staging / name)
        out.append(str(staging / name))
    return out


class QCSessionManager:
    def __init__(self, root: Optional[Path] = None):
        self.root = (root or config.default_workspace_root()) / "qc_sessions"
        self.root.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, sid: str) -> Path:
        d = self.root / sid
        if not d.exists():
            raise FileNotFoundError(f"qc session not found: {sid}")
        return d

    def list(self) -> List[Dict]:
        out = []
        for d in sorted(self.root.iterdir()):
            if d.is_dir():
                m = store.read_json(d / MANIFEST)
                if m:
                    out.append(m)
        return out

    def get(self, sid: str) -> Dict:
        d = self._session_dir(sid)
        m = store.read_json(d / MANIFEST) or {}
        summary = store.read_json(d / "qc_summary.json")
        if summary:
            m["qc_summary"] = summary
        figs = list((d / "figures").glob("*.png")) if (d / "figures").exists() else []
        figs += list(d.glob("*.png"))   # data_QC 默认把图写到会话根
        figures = sorted(set(figs))
        m["figures"] = [str(f) for f in figures]
        return m

    def start(self, input_paths: List[str], note: str = "") -> Dict:
        sid = datetime.now().strftime("qc_%Y%m%d_%H%M%S")
        d = self.root / sid
        d.mkdir(parents=True)
        resolved = _copy_inputs(input_paths, d)
        fp = fingerprint.fingerprint_dataset(resolved)
        manifest = {
            "session_id": sid,
            "schema": "qc.session/1",
            "created_at": store.utcnow(),
            "mode": "standalone",
            "status": "running",
            "note": note,
            "dataset": {"inputs": resolved, "fingerprint": fp, "n_samples_known": False},
            "outputs": {
                "summary": str(d / "qc_summary.json"),
                "report": str(d / "quality_report.md"),
                "figures_dir": str(d / "figures"),
            },
        }
        store.write_json(d / MANIFEST, manifest)
        self._launch(d, resolved, manifest)
        return manifest

    def _launch(self, session_dir: Path, inputs: List[str], manifest: Dict) -> None:
        from . import config as cfg
        engine = cfg.repo_root() / ENGINE
        cmd = [sys.executable, str(engine), "--output-dir", str(session_dir)]
        cmd += ["--data", inputs[0]]  # 单文件或已 staging 的目录
        manifest["command"] = " ".join(str(c) for c in cmd)
        store.write_json(session_dir / MANIFEST, manifest)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            manifest["status"] = "completed" if proc.returncode == 0 else "failed"
            manifest["returncode"] = proc.returncode
            manifest["completed_at"] = store.utcnow()
            manifest["stderr_tail"] = (proc.stderr or "")[-2000:]
        except subprocess.TimeoutExpired:
            manifest["status"] = "failed"
            manifest["returncode"] = -1
            manifest["stderr_tail"] = "timeout"
        store.write_json(session_dir / MANIFEST, manifest)

    def fingerprint(self, input_paths: List[str]) -> dict:
        return fingerprint.fingerprint_dataset(input_paths)

    @staticmethod
    def reusable(prev_manifest: Dict, new_fp: dict) -> bool:
        old = (prev_manifest.get("dataset") or {}).get("fingerprint")
        return bool(old) and fingerprint.same_fingerprint(old, new_fp)
