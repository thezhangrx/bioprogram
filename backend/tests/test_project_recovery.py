"""Project recovery 端到端: 阶段/详情落盘后重开 (新实例) 必须可恢复。"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestProjectRecovery(unittest.TestCase):
    def test_stage_and_recovery(self):
        tmp = Path(tempfile.mkdtemp(prefix="crispr_rec_"))
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        from crispr_workspace import project, store

        m = project.create_project("Recovery", dataset_paths=[], root=tmp)
        pid = m["project_id"]

        # 模拟: QC 完成、分析运行并落盘 detail
        project.update_stage(tmp, pid, "qc", "completed",
                             {"qc_session": "qc_20260909_0001"})
        project.update_stage(tmp, pid, "analysis", "running",
                             {"output_dir": str(tmp / "projects" / pid / "analysis")})
        project.update_stage(tmp, pid, "analysis", "completed",
                             {"output_dir": str(tmp / "projects" / pid / "analysis"),
                              "tasks": ["qc", "evidence_integration"]})

        # “重启”: 全新读取 manifest (不依赖内存)
        restored = store.read_json(tmp / "projects" / pid / project.MANIFEST)
        self.assertEqual(restored["stages"]["qc"], "completed")
        self.assertEqual(restored["stages"]["analysis"], "completed")
        self.assertEqual(restored["stage_detail"]["analysis"]["output_dir"],
                         str(tmp / "projects" / pid / "analysis"))
        # project.update_stage 应可再次正常落盘
        project.update_stage(tmp, pid, "reports", "pending")
        self.assertEqual(project.open_manifest(tmp, pid)["stages"]["reports"], "pending")

    def test_outputs_listing(self):
        from crispr_workspace import analysis
        out = Path(tempfile.mkdtemp(prefix="crispr_out_"))
        self.addCleanup(lambda: shutil.rmtree(out, ignore_errors=True))
        (out / "summary").mkdir()
        (out / "tables").mkdir()
        (out / "summary" / "00_overview.md").write_text("# O", encoding="utf-8")
        (out / "tables" / "evidence_matrix.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        res = analysis.list_outputs(str(out))
        kinds = {(e["name"]) for e in res["entries"]}
        self.assertIn("00_overview.md", kinds)
        self.assertIn("evidence_matrix.csv", kinds)


if __name__ == "__main__":
    unittest.main(verbosity=2)
