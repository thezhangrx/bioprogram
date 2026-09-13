"""本地 Workflow API 服务 (标准库 http.server, 零依赖)。

分层: server.py(路由) -> crispr_workspace.services (QC/Project/Artifact)。
前端只调 /api/*; 组件经 api/*.ts 客户端访问, 不在组件里散落 fetch。
将来可把本文件换成 FastAPI 挂载点, services 层不动。
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from . import (__version__, analysis, artifacts, config, dataset, files, fs_browser,
               pipeline, project, qc_service, store, training)

_qc = None
_workspace_root: Optional[Path] = None


def _body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"_raw": raw}


def _respond(handler: BaseHTTPRequestHandler, code: int, obj: Any) -> None:
    payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _send_file(handler: BaseHTTPRequestHandler, path: Path, mime: str) -> None:
    data = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _dispatch(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        method = self.command
        root = _workspace_root

        def one(key: str, default=None):
            v = qs.get(key)
            return v[0] if v else default

        try:
            # ----- health / meta -----
            if path == "/api/health" and method == "GET":
                return _respond(self, 200, {"ok": True, "engine": "crispr-workspace",
                                            "version": __version__,
                                            "workspace_root": str(root)})

            # ----- projects -----
            if path == "/api/projects" and method == "GET":
                return _respond(self, 200, {"projects": project.list_projects(root)})
            if path == "/api/projects" and method == "POST":
                b = _body(self)
                m = project.create_project(
                    name=b.get("name") or "Untitled Project",
                    dataset_paths=b.get("dataset_paths") or None,
                    root=root)
                return _respond(self, 201, m)
            if path.startswith("/api/projects/") and method == "GET":
                pid = path.rsplit("/", 1)[1]
                return _respond(self, 200, project.open_manifest(root, pid))
            if path == "/api/projects/from-qc" and method == "POST":
                b = _body(self)
                m = project.create_from_qc(root, b["session_id"], b.get("name") or "Project from QC",
                                           b.get("current_paths"))
                return _respond(self, 201, m)

            if path.startswith("/api/projects/") and path.endswith("/config") and method == "POST":
                pid = path.split("/")[-2]
                return _respond(self, 200, project.update_config(root, pid, _body(self).get("config", {})))
            if path.startswith("/api/projects/") and method == "DELETE":
                pid = path.rsplit("/", 1)[1]
                force = str(one("force", "0")).lower() in ("1", "true", "yes")
                return _respond(self, 200, project.delete_project(root, pid, force=force))

            # ----- 目录选择（弹窗用；只返回目录） -----
            if path == "/api/fs/list" and method == "GET":
                try:
                    return _respond(self, 200, fs_browser.list_dirs(one("path") or None))
                except fs_browser.FsError as e:
                    return _respond(self, 400, {"error": str(e)})
            if path == "/api/fs/suggest-output" and method == "GET":
                return _respond(self, 200,
                                {"path": fs_browser.suggest_output_dir(one("project_id") or "project")})
            if path == "/api/fs/mkdir" and method == "POST":
                b = _body(self)
                try:
                    return _respond(self, 201, fs_browser.make_dir(b.get("parent", ""), b.get("name", "")))
                except fs_browser.FsError as e:
                    return _respond(self, 400, {"error": str(e)})
            # ----- dataset inspection / user mapping -----
            if path == "/api/dataset/inspect" and method == "POST":
                b = _body(self)
                paths = b.get("paths") or []
                if not paths:
                    raise ValueError("paths required (用户已测数据集文件或目录)")
                return _respond(self, 200, dataset.inspect_dataset(paths))

            if path == "/api/dataset/mapping-config" and method == "POST":
                b = _body(self)
                inspection = b.get("inspection")
                if not inspection:
                    raise ValueError("inspection required (先运行 /api/dataset/inspect)")
                base = b.get("base_config") or str(config.repo_root() / "data" / "feature_config.json")
                pid = b.get("project_id")
                if pid:
                    out = project.project_dir(root, pid) / "inputs" / "feature_config.user.json"
                else:
                    out = root / "inputs" / "feature_config.user.json"
                cfg = dataset.build_user_config(Path(base), inspection,
                                                b.get("decisions") or {}, out)
                if pid:
                    project.update_config(root, pid, {
                        "feature_config": str(out),
                        "mapping_decisions": b.get("decisions") or {},
                        "inspection_summary": {
                            "cell_lines": inspection.get("cell_lines"),
                            "channels": inspection.get("channels"),
                            "inputs": inspection.get("inputs"),
                            "requires_mapping": inspection.get("requires_mapping"),
                        },
                    })
                return _respond(self, 200, {"config_path": str(out), "config": cfg})

            if path == "/api/training/device-policy" and method == "POST":
                b = _body(self)
                return _respond(self, 200, {"policy": training.device_policy(b.get("models"))})

            # ----- QC sessions -----
            if path == "/api/qc/sessions" and method == "GET":
                return _respond(self, 200, {"sessions": _qc.list()})
            if path == "/api/qc/sessions" and method == "POST":
                b = _body(self)
                note = b.get("note", "")
                session = _qc.start(input_paths=b.get("input_paths") or [], note=note)
                return _respond(self, 201, session)
            if path.startswith("/api/qc/sessions/") and method == "GET":
                sid = path.rsplit("/", 1)[1]
                return _respond(self, 200, _qc.get(sid))
            if path == "/api/qc/fingerprint" and method == "POST":
                b = _body(self)
                return _respond(self, 200, {"fingerprint": _qc.fingerprint(b.get("input_paths") or [])})
            if path == "/api/qc/reuse-check" and method == "POST":
                b = _body(self)
                prev = _qc.get(b["session_id"])
                fp = _qc.fingerprint(b.get("input_paths") or [])
                return _respond(self, 200, {"reusable": _qc.reusable(prev, fp), "fingerprint": fp})

            # ----- training / runtime -----
            if path == "/api/training/defaults" and method == "GET":
                import dataclasses
                cfg = training.TrainingConfig()
                return _respond(self, 200, {
                    "config": dataclasses.asdict(cfg),
                    "allowed": {"models": training.MODELS, "cell_lines": training.CELL_LINES,
                                "split_types": training.SPLITS, "cnn_kernels": training.KERNELS,
                                "mixed_seeds": training.MIXED_SEEDS,
                                "runtimes": ["local_cpu", "local_gpu", "hpc"]},
                })
            if path == "/api/training/preflight" and method == "POST":
                cfg = training.TrainingConfig.from_dict(_body(self).get("config", {}))
                return _respond(self, 200, training.preflight(cfg))
            if path == "/api/training/submit" and method == "POST":
                cfg = training.TrainingConfig.from_dict(_body(self).get("config", {}))
                st = training.submit(cfg)
                return _respond(self, 201, st)
            if path == "/api/runs" and method == "GET":
                return _respond(self, 200, {"runs": training.list_runs(root)})
            if path.startswith("/api/runs/") and method == "GET" and not path.endswith("/cancel") \
                    and not path.endswith("/resume") and not path.endswith("/log"):
                rid = path.rsplit("/", 1)[1]
                return _respond(self, 200, training.status(rid, root))
            if path.startswith("/api/runs/") and path.endswith("/log") and method == "GET":
                rid = path.split("/")[-2]
                st = training.status(rid, root)
                lp = st.get("log_path")
                lines = []
                if lp and Path(lp).exists():
                    raw = Path(lp).read_text(encoding="utf-8", errors="replace")
                    lines = raw.splitlines()[-250:]
                return _respond(self, 200, {"lines": lines})
            if path.endswith("/cancel") and method == "POST":
                rid = path.split("/")[-2]
                return _respond(self, 200, training.cancel(rid, root))
            if path.endswith("/resume") and method == "POST":
                rid = path.split("/")[-2]
                return _respond(self, 200, training.resume(rid, root))

            # ----- analysis / analysis plan -----
            if path == "/api/analysis/tasks" and method == "GET":
                batch = one("batch")
                tasks = analysis.registry_tasks()
                avail = analysis.heuristic_availability(batch) if batch else {}
                for t_ in tasks:
                    t_["available"] = avail.get(t_["task_id"], {}).get("available", None)
                    t_["reason"] = avail.get(t_["task_id"], {}).get("reason", "")
                return _respond(self, 200, {"tasks": tasks})
            if path == "/api/analysis/plan" and method == "POST":
                b = _body(self)
                return _respond(self, 200, {
                    "plan": analysis.build_plan_dict(b.get("selected_tasks"))})
            if path == "/api/analysis/run" and method == "POST":
                b = _body(self)
                batch = b.get("batch_dir")
                if not batch:
                    raise ValueError("batch_dir required (training results batch)")
                pid = b.get("project_id")
                if b.get("output_dir"):
                    out = b["output_dir"]
                elif pid:
                    out = str(root / "projects" / pid / "analysis")
                else:
                    out = str(root / "runs" / "analysis_tmp")
                m = analysis.run(batch, out, b.get("selected_tasks"),
                                 {"project_id": pid} if pid else b.get("project"))
                return _respond(self, 201, m)
            if path == "/api/analysis/outputs" and method == "GET":
                out = one("output_dir")
                if not out:
                    raise ValueError("output_dir required")
                return _respond(self, 200, analysis.list_outputs(out))

            # ----- project stage (由观测到状态的调用方回写; 状态源仍为 manifest) -----
            if path.startswith("/api/projects/") and path.endswith("/stage") and method == "POST":
                pid = path.split("/")[-2]
                b = _body(self)
                m = project.update_stage(root, pid, b["stage"], b["status"],
                                         b.get("detail"))
                return _respond(self, 200, m)

            if path == "/api/analysis/status" and method == "GET":
                out = one("output_dir")
                if not out:
                    raise ValueError("output_dir required")
                return _respond(self, 200, analysis.analysis_status(out))

            # ----- pipeline（共享编排层：向导与网页同一份步骤定义）-----
            if path == "/api/pipeline/steps" and method == "GET":
                payload = {}
                if one("output_dir"):
                    payload["output_dir"] = one("output_dir")
                return _respond(self, 200, pipeline.steps_payload(payload))
            if path == "/api/pipeline/run" and method == "POST":
                b = _body(self)
                if not b.get("step_id"):
                    raise ValueError("step_id required")
                m = pipeline.run(b["step_id"], b, workspace_root=root)
                return _respond(self, 201, m)

            # ----- files（项目文件浏览/查看；仅限仓库内非敏感路径）-----
            if path == "/api/files" and method == "GET":
                try:
                    return _respond(self, 200, files.list_dir(one("path", ".") or "."))
                except files.FileAccessError as e:
                    return _respond(self, 404, {"error": str(e)})
            if path == "/api/file-preview" and method == "GET":
                try:
                    return _respond(self, 200, files.read_file(one("path") or ""))
                except files.FileAccessError as e:
                    return _respond(self, 404, {"error": str(e)})
            if path == "/api/file-raw" and method == "GET":
                try:
                    fp = files.raw_path(one("path") or "")
                    return _send_file(self, fp, files.mime_for(fp))
                except files.FileAccessError as e:
                    return _respond(self, 404, {"error": str(e)})

            # ----- artifacts -----
            # ----- artifacts -----
            if path == "/api/artifacts" and method == "GET":
                p = one("path")
                if not p:
                    raise ValueError("missing path")
                base = one("base")
                off = int(one("offset", "0") or 0)
                lim = one("limit")
                try:
                    payload = artifacts.resolve_artifact(
                        p, [base] if base else None,
                        offset=off, limit=int(lim) if lim else None)
                    return _respond(self, 200, payload)
                except artifacts.ArtifactError as e:
                    return _respond(self, 404, {"error": str(e)})
            if path == "/api/artifact-raw" and method == "GET":
                p = one("path")
                if not p:
                    raise ValueError("missing path")
                try:
                    payload = artifacts.resolve_artifact(p)
                    f = Path(payload["path"])
                    mime = {"csv": "text/csv", "md": "text/markdown", "png": "image/png",
                            "jpg": "image/jpeg", "jpeg": "image/jpeg", "json": "application/json",
                            "txt": "text/plain", "log": "text/plain"}.get(payload["kind"], "application/octet-stream")
                    return _send_file(self, f, mime)
                except artifacts.ArtifactError as e:
                    return _respond(self, 404, {"error": str(e)})

            return _respond(self, 404, {"error": f"no route: {method} {path}"})
        except FileNotFoundError as e:
            return _respond(self, 404, {"error": str(e)})
        except ValueError as e:
            return _respond(self, 400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            return _respond(self, 500, {"error": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def serve(host: str = "127.0.0.1", port: int = 8765, root: Optional[Path] = None,
          blocking: bool = True) -> ThreadingHTTPServer:
    """启动本地服务。blocking=False 时返回 server (由调用方 start/close)。"""
    global _qc, _workspace_root
    _workspace_root = root or config.default_workspace_root()
    config.ensure_dirs(_workspace_root)
    _qc = qc_service.QCSessionManager(_workspace_root)
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    if blocking:
        print(f"[crispr-workspace] serving on http://{host}:{port} "
              f"(root={_workspace_root})")
        httpd.serve_forever()
    return httpd


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="CRISPR Scientific Workspace backend")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--root", default="",
                    help="workspace 根目录 (默认 <repo>/workspace 或 $CRISPR_WORKSPACE_ROOT)")
    args = ap.parse_args()
    serve(host=args.host, port=args.port,
          root=Path(args.root) if args.root else None)
