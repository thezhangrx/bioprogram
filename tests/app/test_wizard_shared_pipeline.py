"""向导 ⇄ 共享编排层一致性测试。

背景：桌面向导（``app/desktop/backend_runner.py``）与网页工作台（``app/backend/crispr_workspace``）
过去各写一套 subprocess 调用；本轮起两者共用 ``pipeline/steps.py``。
本测试锁定：
1. 向导的 ``step_context`` 使用向导布局（``batch_name=""`` → ``--batch-dir``）；
2. 向导为各步骤构造的命令与共享层完全一致（不再各自拼装 CLI）；
3. 关键参数（models / cell-lines / environments / split-types / target-epigenetics /
   plots-dir）确实进入命令，避免重构时丢参数；
4. 模块导入不需要 tkinter（可在无显示环境运行）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for p in (str(ROOT), str(ROOT / "app" / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

import importlib

wizard = importlib.import_module("app.desktop.backend_runner")
from workflows.orchestrator import build_command  # noqa: E402


class TestWizardUsesSharedSteps(unittest.TestCase):
    def setUp(self):
        self.root = Path("/tmp/wizard_out")
        self.dirs = dict(root_path=self.root,
                         proceeded_data_dir=ROOT / "data" / "processed")

    def test_context_uses_output_dir_with_absolute_paths(self):
        ctx = wizard.step_context(**self.dirs, models=["xgboost"])
        self.assertEqual(ctx.output_root, self.root)
        self.assertEqual(ctx.results_path, self.root / "results" / "batches")
        cmd = wizard.step_command("collect_results", ctx)
        self.assertIn("--batch-dir", cmd)
        self.assertNotIn("--batch-name", cmd)
        self.assertIn(str(self.root / "results" / "batches"), cmd)
        self.assertTrue(Path(cmd[0]).is_absolute())

    def test_command_matches_shared_registry(self):
        ctx = wizard.step_context(**self.dirs, split_types=["single"])
        for step_id in ("collect_results", "anomaly_treatment",
                        "importance_extraction", "legacy_visualization"):
            self.assertEqual(wizard.step_command(step_id, ctx),
                             build_command(step_id, ctx), f"{step_id} 与共享层不一致")

    def test_training_options_forwarded(self):
        ctx = wizard.step_context(**self.dirs, models=["linear", "cnn"], cell_lines=["hct116"],
                                  environments=["sequence", "sequence_ctcf"],
                                  split_types=["single", "mixed"])
        cmd = wizard.step_command("train_grid", ctx)
        self.assertIn("workflows/training/data_digging.py", " ".join(cmd))
        for flag in ("--models", "--cell-lines", "--environments", "--split-types"):
            self.assertIn(flag, cmd)
        self.assertIn("hct116", cmd)

    def test_candidate_options_forwarded(self):
        ctx = wizard.step_context(**self.dirs, models=["cnn"], cell_lines=["hela"],
                                  target_input="/tmp/target.csv",
                                  target_epigenetics=["ctcf", "dnase"],
                                  ultimate_dir=str(self.root / "ultimate"))
        cmd = wizard.step_command("generate_candidates", ctx)
        joined = " ".join(cmd)
        self.assertIn("predict.py", joined)
        self.assertIn("--generate-candidates", cmd)
        self.assertIn("--target-input", cmd)
        self.assertIn("--target-epigenetics", cmd)
        self.assertIn("--ultimate-dir", cmd)

    def test_plots_dir_forwarded(self):
        ctx = wizard.step_context(**self.dirs,
                                  plots_dir=str(self.root / "results" / "summary" / "plots"))
        cmd = wizard.step_command("legacy_visualization", ctx)
        self.assertIn("--output-dir", cmd)

    def test_environment_combinations_unchanged(self):
        """向导原有的环境组合规则必须保持（与 data_digging.py 的规则一致）。"""
        combos = wizard.build_active_environment_combinations(["ctcf", "dnase"])
        self.assertEqual(combos, ["sequence", "sequence_ctcf", "sequence_dnase",
                                  "sequence_ctcf_dnase"])
        self.assertEqual(wizard.build_active_environment_combinations([]), ["sequence"])
        full = wizard.build_active_environment_combinations(["ctcf", "dnase", "h3k4me3", "rrbs"])
        self.assertIn("all", full)
        self.assertEqual(len(full), 17)      # 2^4 组合 + all


if __name__ == "__main__":
    unittest.main()
