"""8 通道回归测试: 清除 7 通道遗留 (T 不得被丢弃 / flat 索引按 8 通道解析)。

背景: 旧 7 通道时代残留三处 -> (a) importance_extraction.get_active_channels 只激活 {a,g,c};
(b) identify_feature_channel/extract_feature_position 用 %7 / //7; (c) visualization.SEQ_CHANNELS 缺 T;
(d) data_QC 离群向量每位点只编码 A/G/C。本测试锁定修复后的行为。
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


class TestImportanceChannels8(unittest.TestCase):
    def test_active_channels_include_T(self):
        from analysis.importance_extraction import get_active_channels
        for env in ("sequence", "sequence_ctcf", "sequence_ctcf_dnase_h3k4me3", "all"):
            self.assertIn("t", get_active_channels(env), env)
            self.assertIn("a", get_active_channels(env), env)

    def test_T_feature_valid_in_every_environment(self):
        from analysis.importance_extraction import is_feature_valid_for_env
        for env in ("sequence", "sequence_ctcf", "all"):
            self.assertTrue(is_feature_valid_for_env("pos1_T", env), env)
            self.assertTrue(is_feature_valid_for_env("T_pos_20", env), env)
        # 表观通道仍按环境门控 (sequence 不含 CTCF)
        self.assertFalse(is_feature_valid_for_env("pos1_CTCF", "sequence"))
        self.assertTrue(is_feature_valid_for_env("pos1_CTCF", "sequence_ctcf"))

    def test_flat_feature_index_uses_8_channels(self):
        from analysis.importance_extraction import (SCHEMA_CHANNELS, extract_feature_position,
                                                   identify_feature_channel)
        n = len(SCHEMA_CHANNELS)
        self.assertEqual(n, 8)
        self.assertEqual(identify_feature_channel("feat_7"), SCHEMA_CHANNELS[7 % n])
        self.assertEqual(identify_feature_channel("feat_8"), SCHEMA_CHANNELS[8 % n])
        # 23 位点 × 8 通道 = 184: feat_9 属于第 2 个位点 (0-based 1)
        self.assertEqual(extract_feature_position("feat_9"), 9 // n)


class TestVisualizationLegacy8(unittest.TestCase):
    def _load_legacy(self):
        path = ROOT / "analysis" / "panorama.py"   # 原 visualization.py（与证据图包同名冲突，已更名）
        spec = importlib.util.spec_from_file_location("legacy_visualization_8ch_test", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_seq_channels_include_T_and_parser(self):
        mod = self._load_legacy()
        self.assertIn("T", mod.SEQ_CHANNELS)
        self.assertEqual(set(mod.SEQ_CHANNELS), {"A", "C", "G", "T"})
        self.assertEqual(len(mod.CHANNELS), 8)
        pos, ch = mod.parse_feature_position_channel("T_pos_20")
        self.assertEqual(ch, "T")
        self.assertEqual(pos, 21)  # 0-based 20 -> 1-based 21


class TestDataQcFeatureDim8(unittest.TestCase):
    def test_outlier_vector_dim_is_8_channel(self):
        try:
            import pandas as pd  # noqa: F401
        except Exception:
            self.skipTest("pandas unavailable")
        import json
        import random
        import pandas as pd
        from analysis.data_QC import run_data_qc
        tmp = Path(tempfile.mkdtemp(prefix="qc_8ch_"))
        rng = random.Random(7)
        rows = []
        for _ in range(60):
            rows.append({
                "sgRNA": "".join(rng.choice("ACGT") for _ in range(23)),
                "CTCF": "".join(rng.choice("AN") for _ in range(23)),
                "Dnase": "".join(rng.choice("AN") for _ in range(23)),
                "H3K4me3": "".join(rng.choice("AN") for _ in range(23)),
                "RRBS": "".join(rng.choice("AN") for _ in range(23)),
                "Normalized efficacy": round(0.3 + 0.6 * rng.random(), 4),
            })
        ds = tmp / "tiny.csv"
        pd.DataFrame(rows).to_csv(ds, index=False)
        result = run_data_qc(data_path=str(ds), output_dir=str(tmp / "out"))
        ol = result.get("outliers", {})
        # 4 碱基 × 23 + 4 表观 × 23 = 184
        self.assertEqual(int(ol.get("feature_dim", -1)), 184)


if __name__ == "__main__":
    unittest.main(verbosity=2)
