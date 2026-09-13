"""Workflow 接口测试: TrainingConfig/CLI 构建、Preflight、Runtime(dry-run)、
Analysis 任务目录与 AnalysisPlan 生成。均不触发真实训练/引擎运行。"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path


class WorkflowBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="crispr_ws_tf_")
        os.environ["CRISPR_WORKSPACE_ROOT"] = self.tmp
        self.addCleanup(self._clean)

    def _clean(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("CRISPR_WORKSPACE_ROOT", None)


class TestTrainingConfig(WorkflowBase):
    def test_dig_command_build(self):
        from crispr_workspace import training
        cfg = training.TrainingConfig(
            models=["linear", "xgboost"], cell_lines=["hct116"], split_types=["single"],
            training_scope_epis=["ctcf", "dnase"], batch_name="b1", dry_run=True)
        cmd = cfg.build_command()
        joined = " ".join(cmd)
        self.assertIn("data_digging.py", joined)
        self.assertIn("--batch-name b1", joined)
        self.assertIn("--training-scope-epis ctcf dnase", joined)
        self.assertIn("--dry-run", joined)
        self.assertIn("--models linear xgboost", joined)

    def test_predict_command_build(self):
        from crispr_workspace import training
        cfg = training.TrainingConfig(
            kind="predict", models=["linear", "xgboost"], cell_lines=["hct116", "hela"],
            target_input="data/todo_data.CSV", target_epigenetics=None, dry_run=True)
        joined = " ".join(cfg.build_command())
        self.assertIn("predict.py", joined)
        self.assertIn("--target-input data/todo_data.CSV", joined)
        self.assertNotIn("--in-process", joined)

    def test_preflight_on_repo_pool(self):
        from crispr_workspace import training
        cfg = training.TrainingConfig(models=["linear"], cell_lines=["hct116"],
                                      split_types=["single"], environments=["sequence"])
        r = training.preflight(cfg)
        self.assertTrue(r["ok"], r)

    def test_submit_dry_run_local(self):
        from crispr_workspace import training
        cfg = training.TrainingConfig(models=["linear"], cell_lines=["hct116"],
                                      split_types=["single"], environments=["sequence"],
                                      runtime="local_cpu", dry_run=True)
        st = training.submit(cfg, workspace_root=Path(self.tmp))
        self.assertEqual(st["status"], "dry-run")
        self.assertTrue(st["run_id"].startswith("dig_"))
        runs = training.list_runs(Path(self.tmp))
        self.assertEqual(len(runs), 1)
        s2 = training.status(st["run_id"], Path(self.tmp))
        self.assertEqual(s2["status"], "dry-run")


class TestAnalysisInterface(WorkflowBase):
    def test_registry_tasks(self):
        from crispr_workspace import analysis
        tasks = analysis.registry_tasks()
        ids = {t["task_id"] for t in tasks}
        for expect in ("qc", "prediction", "environment_conditional_effect",
                       "evidence_integration", "bootstrap"):
            self.assertIn(expect, ids)

    def test_build_plan_dict_selection(self):
        from crispr_workspace import analysis
        plan = analysis.build_plan_dict(
            ["qc", "environment_conditional_effect", "evidence_integration"])
        self.assertTrue(plan["run_qc"])
        self.assertTrue(plan["environment"]["conditional_effect"])
        self.assertFalse(plan["environment"]["main_effect"])
        self.assertFalse(plan["run_prediction_analysis"])
        self.assertTrue(plan["evidence"]["evidence_integration"])
        self.assertFalse(plan["sequence"]["position_attribution"])
        # 全不选 -> 顶层容器关闭
        empty = analysis.build_plan_dict([])
        self.assertFalse(empty["environment"]["enabled"])

    def test_heuristic_availability_no_batch(self):
        from crispr_workspace import analysis
        avail = analysis.heuristic_availability(None)
        self.assertFalse(avail["qc"]["available"])
        self.assertIn("No training results batch", avail["qc"]["reason"])


class TestWorkflowEndpoints(WorkflowBase):
    def _boot(self):
        import threading
        from crispr_workspace import server
        srv = server.serve(port=0, root=Path(self.tmp), blocking=False)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{port}"

    def _post(self, base, path, body):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def test_preflight_and_tasks_endpoints(self):
        base = self._boot()
        r = self._post(base, "/api/training/preflight",
                       {"config": {"models": ["linear"], "cell_lines": ["hct116"],
                                   "split_types": ["single"], "environments": ["sequence"]}})
        self.assertTrue(r["ok"], r)
        with urllib.request.urlopen(base + "/api/analysis/tasks") as resp:
            tasks = json.loads(resp.read())["tasks"]
        self.assertTrue(len(tasks) >= 5)
        plan = self._post(base, "/api/analysis/plan", {"selected_tasks": ["qc"]})
        self.assertTrue(plan["plan"]["run_qc"])
        self.assertFalse(plan["plan"]["run_prediction_analysis"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
