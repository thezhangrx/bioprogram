"""crispr_workspace 后端单测 (仅标准库 + 可选的 analysis/data_QC 引擎)。"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent


class WorkspaceBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="crispr_ws_test_")
        os.environ["CRISPR_WORKSPACE_ROOT"] = self.tmp
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("CRISPR_WORKSPACE_ROOT", None)


class TestStoreAndProject(WorkspaceBase):
    def test_create_and_open_manifest(self):
        from crispr_workspace import project, store
        m = project.create_project("Demo Project", dataset_paths=[])
        pid = m["project_id"]
        self.assertEqual(m["stages"]["qc"], "pending")
        again = project.open_manifest(Path(self.tmp), pid)
        self.assertEqual(again["name"], "Demo Project")
        project.update_stage(Path(self.tmp), pid, "qc", "completed")
        self.assertEqual(project.open_manifest(Path(self.tmp), pid)["stages"]["qc"], "completed")

    def test_write_json_atomic(self):
        from crispr_workspace import store
        p = Path(self.tmp) / "nested" / "a.json"
        store.write_json(p, {"x": 1})
        self.assertEqual(store.read_json(p), {"x": 1})


class TestFingerprint(WorkspaceBase):
    def test_change_detected(self):
        from crispr_workspace import fingerprint
        f = Path(self.tmp) / "d.csv"
        f.write_text("a,b\n1,2\n", encoding="utf-8")
        fp1 = fingerprint.fingerprint_dataset([str(f)])
        f.write_text("a,b\n1,3\n", encoding="utf-8")
        fp2 = fingerprint.fingerprint_dataset([str(f)])
        self.assertTrue(fp1["digest"] != fp2["digest"])
        # 当前文件指纹应等于 fp2
        self.assertTrue(fingerprint.same_fingerprint(fp2, fingerprint.fingerprint_dataset([str(f)])))


class TestArtifactResolver(WorkspaceBase):
    def test_csv_and_md(self):
        from crispr_workspace import artifacts
        from crispr_workspace.config import allowed_read_roots
        roots = allowed_read_roots()
        f = Path(self.tmp) / "r.csv"
        f.mkdir(exist_ok=True) if False else None
        # 先造一个测试文件放在 qc root 下以便 allowed
        qc_root = Path(self.tmp) / "qc_sessions"
        qc_root.mkdir(parents=True, exist_ok=True)
        (qc_root / "table.csv").write_text("feature,delta_r2,evidence\nCTCF,+0.032,Strong\n", encoding="utf-8")
        payload = artifacts.resolve_artifact("qc_sessions/table.csv")
        self.assertEqual(payload["kind"], "csv")
        self.assertEqual(payload["columns"], ["feature", "delta_r2", "evidence"])
        (qc_root / "note.md").write_text("# Title\n|a|b|\n|-|-|\n|1|2|\n", encoding="utf-8")
        md = artifacts.resolve_artifact("qc_sessions/note.md")
        self.assertEqual(md["kind"], "md")
        self.assertIn("# Title", md["text"])

    def test_outside_root_denied(self):
        from crispr_workspace import artifacts
        evil = Path(tempfile.mkdtemp()) / "secret.csv"
        evil.write_text("x\n", encoding="utf-8")
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.resolve_artifact(str(evil))


class TestQCSession(WorkspaceBase):
    def _make_dataset(self, name: str = "tiny_data") -> Path:
        import numpy as np  # noqa: F401  (数据合成仅测试用)
        import pandas as pd
        import random
        base = Path(self.tmp) / name
        base.mkdir(parents=True)
        rng = random.Random(3)
        bases = "ACGT"
        rows = []
        for i in range(60):
            seq = "".join(rng.choice(bases) for _ in range(23))
            rows.append({"sgRNA": seq, "Normalized efficacy": round(0.3 + 0.5 * rng.random(), 4)})
        pd.DataFrame(rows).to_csv(base / "tiny.csv", index=False)
        return base

    def test_qc_standalone_run(self):
        pd_ok = True
        try:
            import pandas  # noqa: F401
        except Exception:
            pd_ok = False
        if not pd_ok:
            self.skipTest("pandas unavailable")
        from crispr_workspace import qc_service
        mgr = qc_service.QCSessionManager(Path(self.tmp))
        ds = self._make_dataset()
        sess = mgr.start(input_paths=[str(ds)])
        self.assertEqual(sess["status"], "completed")
        m = mgr.get(sess["session_id"])
        self.assertTrue(Path(m["outputs"]["summary"]).exists())
        summary = json.loads(Path(m["outputs"]["summary"]).read_text(encoding="utf-8"))
        self.assertIn("outliers", summary)
        # 指纹复用守卫: 同输入 -> 可复用
        fp = mgr.fingerprint([str(ds)])
        self.assertTrue(mgr.reusable(m, fp))
        # 换数据 -> 不可复用
        ds2 = self._make_dataset("tiny_data_b")
        ds2.joinpath("extra.txt").write_text("x", encoding="utf-8")
        fp2 = mgr.fingerprint([str(ds2)])
        # 目录指纹基于 csv/tsv 文件集合; 追加 txt 不改集合 -> 仍相同; 直接改 csv 验证
        import pandas as pd
        pd.DataFrame({"sgRNA": ["A" * 23], "Normalized efficacy": [0.9]}).to_csv(
            ds2 / "tiny.csv", mode="a", header=False, index=False)
        fp3 = mgr.fingerprint([str(ds2)])
        self.assertFalse(mgr.reusable(m, fp3))


class TestServer(WorkspaceBase):
    def _boot(self):
        import threading
        from crispr_workspace import server
        srv = server.serve(port=0, root=Path(self.tmp), blocking=False)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{port}"

    def test_health_and_project_flow(self):
        base = self._boot()
        with urllib.request.urlopen(base + "/api/health") as r:
            self.assertEqual(json.loads(r.read())["ok"], True)
        req = urllib.request.Request(base + "/api/projects", data=json.dumps(
            {"name": "Smoke"}).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            m = json.loads(r.read())
        self.assertTrue(m["project_id"].startswith("proj_"))
        with urllib.request.urlopen(base + "/api/projects") as r:
            self.assertEqual(len(json.loads(r.read())["projects"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
