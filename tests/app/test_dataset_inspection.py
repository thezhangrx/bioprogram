"""数据集探测 + Mapping + Device 策略 + 项目删除 的服务级测试。

用真实用户数据集 ``data/source_data`` 验证（对应需求 4）：
探测必须给出细胞系、表观通道，并在待 Mapping 列表中**同时出现 A 与 N**。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for p in (str(ROOT), str(ROOT / "app" / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from crispr_workspace import config, dataset, project, training   # noqa: E402

SOURCE = ROOT / "data" / "raw"


@unittest.skipUnless(SOURCE.is_dir(), "data/raw 不存在")
class TestDatasetInspection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = dataset.inspect_dataset([str(SOURCE)])

    def test_cell_lines_from_filenames(self):
        self.assertEqual(sorted(self.result["cell_lines"]),
                         ["hct116", "hek293t", "hela", "hl60"])

    def test_channels_detected(self):
        self.assertEqual(sorted(self.result["channels"]),
                         ["CTCF", "Dnase", "H3K4me3", "RRBS"])

    def test_sequence_and_label_columns(self):
        self.assertEqual(self.result["sequence_column"], "sgRNA")
        self.assertEqual(self.result["label_column"], "Normalized efficacy")
        self.assertEqual(self.result["sequence_length"], 23)

    def test_mapping_includes_A_and_N(self):
        """需求 4：User Decision/Mapping 中必须有 A 和 N 待 Mapping。"""
        symbols = {m["symbol"] for m in self.result["mapping_items"] if m["scope"] == "channel"}
        self.assertIn("A", symbols)
        self.assertIn("N", symbols)
        amb = {m["symbol"] for m in self.result["mapping_items"] if m["ambiguous"]}
        self.assertIn("N", amb)
        self.assertNotIn("A", amb)          # A 有明确默认值 (1)，N 需人工确认
        self.assertTrue(self.result["requires_mapping"])
        self.assertGreaterEqual(self.result["pending_mapping"], 4)

    def test_defaults_follow_shipped_feature_config(self):
        by_key = {(m["channel"], m["symbol"]): m for m in self.result["mapping_items"]
                  if m["scope"] == "channel"}
        self.assertEqual(by_key[("CTCF", "A")]["default_value"], 1)
        self.assertEqual(by_key[("CTCF", "N")]["default_value"], 0)

    def test_user_config_applies_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "feature_config.user.json"
            cfg = dataset.build_user_config(
                ROOT / "data" / "metadata" / "feature_config.json", self.result,
                {"CTCF:N": 1, "RRBS:N": 0}, out)
            self.assertTrue(out.exists())
            enc = {f["name"]: f["encoding"] for f in cfg["environment_features"]}
            self.assertEqual(enc["CTCF"]["N"], 1)      # 用户改成 1
            self.assertEqual(enc["RRBS"]["N"], 0)
            self.assertEqual(enc["CTCF"]["A"], 1)      # 未决策项沿用默认
            json.loads(out.read_text(encoding="utf-8"))  # 合法 JSON

    def test_missing_paths_rejected(self):
        with self.assertRaises(dataset.DatasetError):
            dataset.inspect_dataset([str(ROOT / "__no_such_dir__")])


class TestDevicePolicy(unittest.TestCase):
    def test_cpu_only_models_lock_cpu(self):
        pol = training.device_policy(["linear"])
        self.assertEqual(pol["allowed"], ["cpu"])
        self.assertTrue(pol["locked"])
        self.assertEqual(training.device_policy(["xgboost", "linear"])["allowed"], ["cpu"])

    def test_deep_models_allow_cpu_or_gpu(self):
        for models in (["cnn"], ["mlp", "cnn", "transformer"]):
            pol = training.device_policy(models)
            self.assertEqual(pol["allowed"], ["cpu", "gpu"])
            self.assertFalse(pol["locked"])

    def test_mixed_models_allow_cpu_or_cpu_gpu(self):
        pol = training.device_policy(["linear", "cnn"])
        self.assertEqual(pol["allowed"], ["cpu", "cpu/gpu"])

    def test_cpu_forces_no_gpu(self):
        dev = training.resolve_device("cpu", ["cnn"])
        self.assertTrue(dev["cpu_only"])
        self.assertEqual(dev["cuda_visible"], "")

    def test_gpu_rejected_for_cpu_only_models(self):
        with self.assertRaises(ValueError):
            training.resolve_device("gpu", ["linear"])


class TestProjectDeleteAndConfig(unittest.TestCase):
    def test_delete_removes_project_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m = project.create_project("demo", [], root=root)
            d = root / "projects" / m["project_id"]
            self.assertTrue(d.exists())
            out = project.delete_project(root, m["project_id"])
            self.assertEqual(out["deleted"], m["project_id"])
            self.assertFalse(d.exists())
            self.assertEqual(project.list_projects(root), [])

    def test_update_config_rename_and_whitelist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m = project.create_project("旧名字", [], root=root)
            project.update_config(root, m["project_id"],
                                  {"name": "新名字", "output_dir": str(root / "out"),
                                   "secret_key": "nope"})
            man = project.open_manifest(root, m["project_id"])
            self.assertEqual(man["name"], "新名字")            # 项目名可修改
            self.assertEqual(man["config"]["output_dir"], str(root / "out"))
            self.assertNotIn("secret_key", man["config"])

    def test_delete_cascades_to_output_dir(self):
        """删除项目必须同时删除输出目录（results/models/logs）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "proj_output"
            m = project.create_project("demo", [], root=root)
            pid = m["project_id"]
            project.update_config(root, pid, {"output_dir": str(out)})
            for sub in ("results", "models", "logs"):
                (out / sub).mkdir(parents=True)
                (out / sub / "f.bin").write_bytes(b"0" * 512)
            res = project.delete_project(root, pid)
            self.assertFalse(out.exists(), "输出目录应被一并删除")
            self.assertGreater(res["freed_bytes"], 0)
            self.assertEqual(res["removed"][0]["path"], str(out))

    def test_delete_protects_nested_repo_dirs(self):
        """回归：仓库内**任意下级目录**都受保护（曾因只保护直接子目录而误删 results/<batch>）。"""
        nested = config.repo_root() / "results" / "batch_20260909_full"
        self.assertTrue(project._is_protected(nested, Path(tempfile.gettempdir())))
        self.assertTrue(project._is_protected(config.repo_root() / "models" / "batch_x",
                                              Path(tempfile.gettempdir())))
        self.assertTrue(project._is_protected(config.repo_root(), Path(tempfile.gettempdir())))
        ws = config.default_workspace_root() / "projects" / "p1" / "output"
        self.assertFalse(project._is_protected(ws, config.default_workspace_root()))
        self.assertFalse(project._is_protected(Path("/tmp/some_project_out"),
                                               Path(tempfile.gettempdir())))

    def test_delete_protects_repo_delivery_dirs(self):
        """指向仓库交付目录的 output_dir 受保护，不会被误删。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m = project.create_project("demo", [], root=root)
            pid = m["project_id"]
            protected = config.repo_root() / "results"
            project.update_config(root, pid, {"output_dir": str(protected)})
            res = project.delete_project(root, pid)
            self.assertTrue(protected.exists(), "仓库 results/ 不能被删除")
            self.assertTrue(res["skipped"], "应报告被跳过的受保护路径")


if __name__ == "__main__":
    unittest.main()
