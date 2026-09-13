"""共享编排层 + 流程/文件 API 的服务级测试（不需要 GPU、不执行重任务）。

覆盖：
1. ``pipeline.steps`` 注册表：命令构造、依赖拓扑、重复 id 检查、wizard 布局兼容；
2. ``pipeline`` 服务：步骤状态/ready 推断、内部步骤（交付物核对）、dry-run 提交；
3. ``training.submit_command``：通用子进程提交 + 运行日志流（用无害命令验证 print 文本）；
4. ``files`` 服务：目录列出、文本/CSV 预览、路径越界与敏感目录拦截。
"""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent      # 仓库根
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from crispr_workspace import config, files, pipeline, training      # noqa: E402
from pipeline import PipelineContext, STEPS, build_command, resolve_order  # noqa: E402


class TestStepRegistry(unittest.TestCase):
    def test_step_ids_unique_and_ordered(self):
        ids = [s.step_id for s in STEPS]
        self.assertEqual(len(ids), len(set(ids)), "step_id 必须唯一")
        self.assertIn("deliverables_check", ids)
        order = resolve_order(ids)
        for sid in ids:
            for dep in next(s for s in STEPS if s.step_id == sid).requires:
                self.assertLess(order.index(dep), order.index(sid),
                                f"{dep} 必须先于 {sid}")

    def test_all_path_arguments_are_absolute(self):
        """要求：Web 使用的程序不依赖相对路径，全部以绝对路径为准（含调试用 batch 形态）。"""
        ctx = PipelineContext(repo_root=ROOT, output_dir=str(ROOT / "out_test"))
        self._assert_absolute(ctx)
        self._assert_absolute(PipelineContext(repo_root=ROOT, output_dir=str(ROOT),
                                              batch_name="batch_debug"))

    def _assert_absolute(self, ctx):
        for step in STEPS:
            cmd = build_command(step.step_id, ctx)
            if step.kind == "internal":
                self.assertEqual(cmd, [])
                continue
            # 解释器必须是绝对路径
            self.assertTrue(Path(cmd[0]).is_absolute(), f"{step.step_id}: 解释器非绝对路径")
            for arg in cmd[1:]:
                if arg.startswith("-"):
                    continue
                looks_like_path = ("/" in arg or arg.endswith((".py", ".json", ".csv"))
                                   and " " not in arg)
                if looks_like_path:
                    self.assertTrue(Path(arg).is_absolute(),
                                    f"{step.step_id}: 非绝对路径参数 {arg!r}")

    def test_no_batch_name_anywhere(self):
        """batch 概念已移除：命令中不得出现 --batch-name / --batch_name。"""
        for ctx in (PipelineContext(repo_root=ROOT),
                    PipelineContext(repo_root=ROOT, output_dir=str(ROOT / "out_test"))):
            for step in STEPS:
                cmd = build_command(step.step_id, ctx)
                self.assertNotIn("--batch-name", cmd)
                self.assertNotIn("--batch_name", cmd)

    def test_output_dir_derives_results_models_logs(self):
        """output_dir 之下固定派生 results/ models/ logs/（无 batch 子目录）。"""
        ctx = PipelineContext(repo_root=ROOT, output_dir="/tmp/proj_out")
        self.assertEqual(ctx.results_path, Path("/tmp/proj_out/results"))
        self.assertEqual(ctx.models_path, Path("/tmp/proj_out/models"))
        self.assertEqual(ctx.logs_path, Path("/tmp/proj_out/logs"))
        cmd = build_command("collect_results", ctx)
        self.assertIn("--batch-dir", cmd)
        self.assertIn("/tmp/proj_out/results", cmd)

    def test_relative_paths_rejected(self):
        with self.assertRaises(ValueError):
            build_command("collect_results", PipelineContext(repo_root=ROOT, output_dir="relative/out"))

    def test_importance_extraction_uses_underscore_flags(self):
        ctx = PipelineContext(repo_root=ROOT, output_dir="/tmp/proj_out")
        cmd = build_command("importance_extraction", ctx)
        self.assertIn("--batch_dir", cmd)              # 脚本的下划线风格参数
        self.assertIn("/tmp/proj_out/results", cmd)
        self.assertNotIn("--batch_name", cmd)          # 前端路径不含 batch

    def test_heavy_flags(self):
        by_id = {s.step_id: s for s in STEPS}
        self.assertTrue(by_id["train_grid"].heavy)
        self.assertTrue(by_id["generate_candidates"].heavy)
        self.assertFalse(by_id["collect_results"].heavy)


class TestPipelineService(unittest.TestCase):
    def test_steps_payload_shape(self):
        # 交付结果位于 <repo>/results/batch_20260909_full：
        # 用 output_dir=<repo> + 调试用 batch_name 命中真实产物（前端不传 batch_name）
        payload = pipeline.steps_payload({"output_dir": str(ROOT),
                                          "batch_name": "batch_20260909_full"})
        self.assertEqual(payload["schema"], "pipeline.run/1")
        self.assertEqual(len(payload["steps"]), len(STEPS))
        for step in payload["steps"]:
            self.assertIn(step["status"], {"completed", "partial", "pending"})
            self.assertIn("ready", step)
            self.assertIn("command", step)
        # 真实批次里 feature_engineering / train_grid 的产物应已存在
        by_id = {s["step_id"]: s for s in payload["steps"]}
        self.assertEqual(by_id["feature_engineering"]["status"], "completed")
        self.assertEqual(by_id["train_grid"]["status"], "completed")

    def test_internal_step_checks_deliverables(self):
        res = pipeline.run("deliverables_check",
                           {"output_dir": str(ROOT), "batch_name": "batch_20260909_full"})
        self.assertEqual(res["kind"], "internal")
        self.assertIsNone(res["run_id"])
        self.assertEqual(res["status"], "completed")
        self.assertTrue(all(c["exists"] for c in res["checks"]))

    def test_dry_run_does_not_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = pipeline.run("collect_results",
                               {"output_dir": str(ROOT), "dry_run": True,
                                "batch_name": "batch_20260909_full"},
                               workspace_root=Path(tmp))
            self.assertEqual(res["status"], "dry-run")
            self.assertIn("collect_results.py", res["command"])
            cmd = str(res["command"]).split()
            self.assertTrue(Path(cmd[1]).is_absolute(), f"脚本路径非绝对: {cmd[1]}")
            self.assertTrue((Path(tmp) / "runs" / res["run_id"] / "plan.json").exists())

    def test_unknown_step_rejected(self):
        with self.assertRaises(KeyError):
            pipeline.run("not_a_step", {"dry_run": True})


class TestRunLogStream(unittest.TestCase):
    def test_submit_command_streams_stdout_to_log(self):
        """通用提交：子进程 print 的文字应出现在 /api/runs/<id>/log 读取的 run.log 中。"""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            cmd = [sys.executable, "-c",
                   "print('[Step 1/3] hello from pipeline'); print('done')"]
            st = training.submit_command(cmd, kind="pipeline_smoke", workspace_root=ws)
            self.assertIn("run_id", st)
            log_path = Path(st["log_path"])
            for _ in range(50):
                if (ws / "runs" / st["run_id"] / training.DONE_FILE).exists():
                    break
                time.sleep(0.1)
            st2 = training.status(st["run_id"], ws)
            self.assertEqual(st2["status"], "completed")
            text = log_path.read_text(encoding="utf-8")
            self.assertIn("hello from pipeline", text)
            self.assertIn("done", text)


class TestFilesService(unittest.TestCase):
    def test_list_and_preview(self):
        listing = files.list_dir("results")
        self.assertTrue(any(e["name"] == "batch_20260909_full" for e in listing["entries"]))
        preview = files.read_file("results/batch_20260909_full/summary/赛道二_results.csv")
        self.assertEqual(preview["kind"], "text")
        self.assertIn("候选编号", preview["columns"][1])
        self.assertGreater(preview["data_rows"], 0)

    def test_traversal_and_denylist_blocked(self):
        for bad in ("../../etc/passwd", "/etc/passwd", ".git/config", "frontend/node_modules"):
            with self.assertRaises(files.FileAccessError):
                files.resolve(bad)

    def test_missing_path_raises(self):
        with self.assertRaises(files.FileAccessError):
            files.read_file("results/__definitely_missing__.csv")


if __name__ == "__main__":
    unittest.main()
