# analysis/tests/test_split_code_parity.py
"""二阶审计: 训练层划分实现 vs 分析层泄漏实现的交叉验证。

存在两套实现（训练包必须能独立上传，故不 import analysis/）：
  * 训练层: src/input_control/cell_line_division.py  (sequence_group_ids / divide_data)
  * 分析层: analysis/leakage.py                       (canonical_group_key / classify_overlaps)

本测试强制二者规则一致，并用**独立的分析层实现**复核训练层实际产出的
train/valid/test 划分无序列泄漏（L3 精确重复、L5 反向互补均为 0）。
"""
from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.leakage import canonical_group_key, classify_overlaps, leakage_mask, revcomp
from core.data.splitting.cell_line_division import (divide_data, raw_sequence_ids,
                                                  sequence_group_ids)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "proceeded_data"
CELLS = ["hct116", "hek293t", "hela", "hl60"]


def _meta(cell: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"{cell}_metadata.csv")


@unittest.skipUnless(DATA_DIR.exists(), "数据集不在仓库内")
class TestIdentityRuleParity(unittest.TestCase):
    def test_two_implementations_agree_on_group_key(self):
        for cell in CELLS:
            meta = _meta(cell)
            train_side = sequence_group_ids(meta)
            analysis_side = canonical_group_key(meta).to_numpy()
            np.testing.assert_array_equal(train_side, analysis_side)

    def test_revcomp_rule_is_involution_on_canonical_class(self):
        meta = _meta("hek293t")
        keys = canonical_group_key(meta)
        for original, key in zip(meta["sgRNA"].astype(str).str.upper(), keys.head(50)):
            self.assertEqual(key, min(key, revcomp(key)), msg=f"{original} -> {key}")

    def test_raw_ids_untouched_by_canonicalisation(self):
        meta = _meta("hct116")
        raw = raw_sequence_ids(meta)
        self.assertTrue((raw == meta["sgRNA"].astype(str).str.upper().str.strip().to_numpy()).all())


@unittest.skipUnless(DATA_DIR.exists(), "数据集不在仓库内")
class TestSecondOrderLeakageAudit(unittest.TestCase):
    """用分析层实现复核训练层划分（不共用任何代码路径）。"""

    def _audit(self, split: dict) -> dict:
        train_meta = split["metadata_train"]
        valid_meta = split["metadata_valid"]
        test_meta = split["metadata_test"]
        return {
            "train_test": classify_overlaps(train_meta, test_meta, "train|test"),
            "train_valid": classify_overlaps(train_meta, valid_meta, "train|valid"),
            "valid_test": classify_overlaps(valid_meta, test_meta, "valid|test"),
        }

    def assertNoLeakage(self, stats: dict, label: str) -> None:
        """四类重叠全部必须为 0 (L2 观测 / L3 序列 / L4 locus / L5 反向互补)。"""
        for key in ("L2_same_observation", "L3_same_sequence",
                    "L4_same_locus", "L5_revcomp_pair"):
            self.assertEqual(stats[key], 0, f"{label} {key}={stats[key]}")

    def test_single_splits_have_no_overlap_in_any_class(self):
        for cell in CELLS:
            split = divide_data(str(DATA_DIR), "single", cell_line=cell, random_seed=42)
            for pair, stats in self._audit(split).items():
                self.assertNoLeakage(stats, f"single/{cell} {pair}")

    def test_mixed_splits_have_no_overlap_in_any_class(self):
        for seed in (42, 43, 44, 45):
            split = divide_data(str(DATA_DIR), "mixed", cell_lines=CELLS, random_seed=seed)
            for pair, stats in self._audit(split).items():
                self.assertNoLeakage(stats, f"mixed/{seed} {pair}")

    def test_loco_splits_have_no_overlap_in_any_class(self):
        for held in CELLS:
            split = divide_data(str(DATA_DIR), "all", cell_line=held,
                                cell_lines=CELLS, random_seed=42)
            for pair, stats in self._audit(split).items():
                self.assertNoLeakage(stats, f"LOCO/{held} {pair}")

    def test_analysis_side_mask_keeps_entire_test_set(self):
        """分析层 leakage_mask 若把 test 全判为泄漏, 说明两套实现不一致。"""
        for seed in (42, 43, 44, 45):
            split = divide_data(str(DATA_DIR), "mixed", cell_lines=CELLS, random_seed=seed)
            keep = leakage_mask(split["metadata_test"], split["metadata_train"], group="sequence")
            self.assertTrue(keep.all(), f"mixed/{seed}: 分析层仍判定 {int((~keep).sum())} 条 test 被 train 见过")

    def test_loco_excludes_heldout_sequences_from_training_pool(self):
        for held in CELLS:
            split = divide_data(str(DATA_DIR), "all", cell_line=held,
                                cell_lines=CELLS, random_seed=42)
            held_seqs = set(canonical_group_key(_meta(held)))
            pool = pd.concat([split["metadata_train"], split["metadata_valid"]], ignore_index=True)
            overlap = set(canonical_group_key(pool)) & held_seqs
            self.assertEqual(len(overlap), 0, f"LOCO/{held}: 训练池仍含 {len(overlap)} 个留出系身份类")
            self.assertEqual(split["n_test"], len(_meta(held)))


if __name__ == "__main__":
    unittest.main()
