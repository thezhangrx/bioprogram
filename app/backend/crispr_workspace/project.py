"""Project Workspace: 创建/列出/打开项目, project_manifest.json 为状态源。"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import shutil

from . import config, fingerprint, store

MANIFEST = "project_manifest.json"

SCHEMA = "project.manifest/1"


def _slug(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", name.strip()).strip("_").lower()
    return s or "project"


def new_project_id() -> str:
    return datetime.now().strftime("proj_%Y%m%d_%H%M%S")


def projects_root(root: Optional[Path] = None) -> Path:
    r = (root or config.default_workspace_root()) / "projects"
    r.mkdir(parents=True, exist_ok=True)
    return r


def project_dir(root: Path, project_id: str) -> Path:
    d = projects_root(root) / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_project(name: str,
                   dataset_paths: Optional[List[str]] = None,
                   root: Optional[Path] = None,
                   reuse_fingerprint: Optional[dict] = None) -> Dict[str, Any]:
    """创建一个 Project Workspace 并落盘 project_manifest.json。

    绝不启动 QC/Training; 只建立骨架与数据集快照信息。
    """
    pid = new_project_id()
    if dataset_paths:
        fp = fingerprint.fingerprint_dataset(dataset_paths)
        if reuse_fingerprint and fp and fingerprint.same_fingerprint(fp, reuse_fingerprint):
            fp["reused_from_qc"] = True
    else:
        fp = None
    manifest = {
        "schema": SCHEMA,
        "project_id": pid,
        "name": name,
        "created_at": store.utcnow(),
        "updated_at": store.utcnow(),
        "dataset": {
            "input_paths": [str(Path(p).resolve()) for p in (dataset_paths or [])],
            "fingerprint": fp,
            "imported": bool(dataset_paths),
        },
        "stages": {s: "pending" for s in store.STAGE_ORDER},
        "config_versions": {"analysis_plan": None, "workflow_config": None, "training_config": None},
    }
    d = project_dir(root, pid)
    store.write_json(d / MANIFEST, manifest)
    for sub in ("inputs", "qc", "training", "analysis", "reports", "artifacts"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return manifest


def _resolve(root: Path, project_id: str) -> Path:
    d = projects_root(root) / project_id
    if not d.exists():
        raise FileNotFoundError(f"project not found: {project_id}")
    return d


def open_manifest(root: Path, project_id: str) -> Dict[str, Any]:
    m = store.read_json(_resolve(root, project_id) / MANIFEST)
    if m is None:
        raise FileNotFoundError(f"missing {MANIFEST} for {project_id}")
    return m


def update_stage(root: Path, project_id: str, stage: str, status: str,
                 detail: Optional[dict] = None) -> Dict[str, Any]:
    if stage not in store.STAGE_ORDER:
        raise ValueError(f"unknown stage: {stage}")
    d = _resolve(root, project_id)
    m = store.read_json(d / MANIFEST) or {}
    m.setdefault("stages", {})[stage] = status
    m["updated_at"] = store.utcnow()
    if detail:
        m.setdefault("stage_detail", {})[stage] = detail
    store.write_json(d / MANIFEST, m)
    return m


#: 允许写入 project_manifest 的"用户可编辑配置"键（白名单，避免任意写入）
EDITABLE_CONFIG_KEYS = (
    "output_dir", "target_paths", "data_dir", "raw_data_dir", "feature_config",
    "mapping_decisions", "inspection_summary", "device", "models", "cell_lines",
    "split_types", "scope_epi", "epochs",
)


def update_config(root: Path, project_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    """更新项目配置：项目名（可修改）、绝对输出目录、数据集、Mapping 决策、设备等。"""
    d = _resolve(root, project_id)
    m = store.read_json(d / MANIFEST) or {}
    patch = dict(patch or {})
    if patch.get("name"):                       # 用户可修改项目名
        m["name"] = str(patch.pop("name")).strip() or m.get("name")
    cfg = m.setdefault("config", {})
    for k, v in patch.items():
        if k in EDITABLE_CONFIG_KEYS and v is not None:
            cfg[k] = v
    m["updated_at"] = store.utcnow()
    store.write_json(d / MANIFEST, m)
    return m


#: 仓库内受保护的顶层目录（仅用于文档/提示；实际判定见 _is_protected：仓库内一律保护）
PROTECTED_PATHS = ("app", "analysis", "core", "data", "deploy", "docs", "models",
                   "notebooks", "results", "tests", "workflows", "workspace")


def _is_protected(target: Path, root: Path, repo: Optional[Path] = None) -> bool:
    """判断输出目录是否受保护（不允许随项目删除）。

    规则（2026-09 修订，事故驱动）：
      * 仓库根、文件系统根、用户主目录 → 保护；
      * **仓库内的任何路径都受保护**（results/、models/、logs/、data/、paper/…
        以及它们的任意下级目录，例如 results/<batch>/）；
      * 唯一例外：项目工作区 ``<workspace>/projects/<id>/output``（允许删除）。
    这样即使用户把输出目录选成 results/batch_xxx，也不会删掉交付结果。
    """
    repo = (repo or config.repo_root()).resolve()
    t = target.resolve()
    if t in (repo, Path("/"), Path.home().resolve()):
        return True
    workspace_projects = (root / "projects").resolve()
    inside_workspace = (workspace_projects == t) or (workspace_projects in t.parents)
    if t == repo or repo in t.parents:          # 仓库内
        return not inside_workspace
    return False


def _tree_size(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def delete_project(root: Path, project_id: str, delete_outputs: bool = True,
                   force: bool = False) -> Dict[str, Any]:
    """删除项目：项目目录 + **输出目录下的全部产物**（results/models/logs）。

    安全约束：
      * 只允许删除 ``workspace/projects/<id>`` 与项目配置中的 ``output_dir``；
      * 仓库自身的交付目录（results/models/logs/data/paper/...）受保护，
        除非显式 ``force=True``（前端不做该选项），否则跳过并如实报告。
    """
    d = _resolve(root, project_id)
    allowed_parent = (root / "projects").resolve()
    if allowed_parent not in d.resolve().parents:
        raise ValueError("refuse to delete outside workspace/projects")
    m = store.read_json(d / MANIFEST) or {}
    output_dir = ((m.get("config") or {}).get("output_dir") or "").strip()

    removed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    if delete_outputs and output_dir:
        out = Path(output_dir).expanduser()
        if out.is_absolute() and out.exists():
            if _is_protected(out, root) and not force:
                skipped.append({"path": str(out), "reason": "仓库交付目录受保护（未删除）"})
            else:
                size = _tree_size(out)
                shutil.rmtree(out)
                removed.append({"path": str(out), "bytes": size})

    size = _tree_size(d)
    shutil.rmtree(d)
    removed.append({"path": str(d), "bytes": size})
    return {"deleted": project_id, "name": m.get("name"), "removed": removed,
            "skipped": skipped, "freed_bytes": sum(r["bytes"] for r in removed)}


def list_projects(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    out = []
    base = projects_root(root)
    if not base.exists():
        return out
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        m = store.read_json(d / MANIFEST)
        if m:
            out.append(m)
    return out


def create_from_qc(root: Path, qc_session_id: str, name: str,
                   current_paths: Optional[List[str]] = None,
                   qc_manager=None) -> Dict:
    """从已完成 QC 会话创建项目: 复用其指纹(仅当数据未变), 避免重复计算。

    若给出 current_paths, 先校验其指纹 == 会话指纹, 不一致则抛 ValueError。
    """
    if qc_manager is None:
        from . import qc_service as _qc
        qc_manager = _qc.QCSessionManager(root)
    sess = qc_manager.get(qc_session_id)
    if sess.get("status") != "completed":
        raise ValueError("QC 会话未完成, 不能据此创建项目")
    session_inputs = (sess.get("dataset") or {}).get("inputs") or []
    paths = current_paths if current_paths is not None else session_inputs
    new_fp = fingerprint.fingerprint_dataset(paths)
    old_fp = (sess.get("dataset") or {}).get("fingerprint")
    if current_paths is not None:
        if not old_fp or not fingerprint.same_fingerprint(old_fp, new_fp):
            raise ValueError("数据集已变化, 不能复用旧 QC 结果; 请先重新运行 QC")
    return create_project(name=name, dataset_paths=paths,
                          reuse_fingerprint=old_fp or new_fp, root=root)
