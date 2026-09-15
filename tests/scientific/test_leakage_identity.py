"""Leakage identity / taxonomy / group-aware split 的最小测试集。

对应整改 issue：
  A1  mixed 跨细胞系 (sgRNA,label) overlap  → classify_overlaps / leakage_mask
  A2  LOCO 同源泄漏                          → 同一 policy 复用于 all
  A3  locus / revcomp 重叠分类                → locus_key / revcomp / classify_overlaps
  以及 group_aware_split 的"同组不跨 split"不变式。
"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from analysis.leakage import (classify_overlaps, group_aware_split, leakage_mask,
                             locus_key, observation_key, revcomp, sequence_key)


def _meta(seqs, labels, cells=None, loci=None):
    d = pd.DataFrame({"sgRNA": seqs, "Normalized efficacy": labels})
    if cells is not None:
        d["Cell line"] = cells
    if loci is not None:
        d[["Chromosome", "Start", "End"]] = pd.DataFrame(loci, columns=["Chromosome", "Start", "End"])
    return d


class TestIdentity(unittest.TestCase):
    def test_sequence_key_normalizes(self):
        m = _meta([" acgt ", "ACGT"], [0.1, 0.2])
        self.assertEqual(list(sequence_key(m)), ["ACGT", "ACGT"])

    def test_observation_key_includes_label(self):
        m = _meta(["ACGT", "ACGT"], [0.1, 0.1000004])
        self.assertEqual(len(set(observation_key(m, ndigits=6))), 1)
        m2 = _meta(["ACGT", "ACGT"], [0.1, 0.4])
        self.assertEqual(len(set(observation_key(m2, ndigits=6))), 2)

    def test_locus_key(self):
        m = _meta(["A" * 23], [0.1], loci=[("chr1", 100, 123)])
        self.assertEqual(list(locus_key(m)), ["chr1:100-123"])


class TestLeakageMask(unittest.TestCase):
    def setUp(self):
        # train: AAA(0.5) / CCC(0.2)；test: AAA 同 observation、AAA 不同 label、CCC 见过、ACG 全新
        self.train = _meta(["AAA", "CCC"], [0.5, 0.2])
        self.test = _meta(["AAA", "AAA", "CCC", "ACG"], [0.5, 0.9, 0.7, 0.3])

    def test_sequence_group_blocks_any_seen_sequence(self):
        keep = leakage_mask(self.test, self.train, group="sequence")
        # AAA 两行都见过序列 → 屏蔽；CCC 见过 → 屏蔽；ACG 是全新 identity class → 保留
        self.assertEqual(list(keep), [False, False, False, True])

    def test_sequence_group_also_blocks_revcomp_near_duplicates(self):
        # GGG 的反向互补是 CCC（已在 train 中）→ 必须一并屏蔽（L5 整改）
        train = _meta(["CCC"], [0.2])
        test = _meta(["GGG", "ACG"], [0.3, 0.4])
        keep = leakage_mask(test, train, group="sequence")
        self.assertEqual(list(keep), [False, True])

    def test_observation_group_blocks_only_same_label(self):
        keep = leakage_mask(self.test, self.train, group="observation")
        # 只有 AAA+0.5 与 train 完全同 observation → 屏蔽；
        # AAA+0.9 / CCC+0.7 / ACG+0.3 都是**新的 observation** → 保留（sequence 组则会全部屏蔽）
        self.assertEqual(list(keep), [False, True, True, True])

    def test_unknown_group_raises(self):
        with self.assertRaises(ValueError):
            leakage_mask(self.test, self.train, group="locus")


class TestClassification(unittest.TestCase):
    def test_six_level_counts(self):
        a = _meta(["AAA", "TTT"], [0.5, 0.2], cells=["hct116", "hct116"],
                  loci=[("chr1", 10, 33), ("chr2", 20, 43)])
        # b 与 a：AAA+0.5 完全相同；CCC 是 AAA 的 revcomp；位点 chr1:10-33 相同
        b = _meta(["AAA", "CCC", "GGG"], [0.5, 0.4, 0.1], cells=["hela", "hela", "hela"],
                  loci=[("chr1", 10, 33), ("chr9", 1, 24), ("chr8", 5, 28)])
        r = classify_overlaps(a, b, label="hct116∩hela")
        self.assertEqual(r["L2_same_observation"], 1)
        self.assertEqual(r["L3_same_sequence"], 1)
        self.assertEqual(r["L4_same_locus"], 1)
        self.assertEqual(r["L5_revcomp_pair"], 1)

    def test_revcomp(self):
        self.assertEqual(revcomp("ACGT"), "ACGT")
        self.assertEqual(revcomp("AACG"), "CGTT")


class TestGroupAwareSplit(unittest.TestCase):
    def test_groups_never_cross_splits(self):
        # 3 个 group × 各 4 个样本
        seqs = [s for s in ("AAA", "CCC", "GGG") for _ in range(4)]
        idx = np.arange(len(seqs))
        out = group_aware_split(idx, seqs, (0.34, 0.33, 0.33), seed=7)
        g = np.array(seqs)
        sets = {k: set(g[v]) for k, v in out.items()}
        self.assertFalse(sets["train"] & sets["validation"])
        self.assertFalse(sets["train"] & sets["test"])
        self.assertFalse(sets["validation"] & sets["test"])
        self.assertEqual(len(out["train"]) + len(out["validation"]) + len(out["test"]), len(seqs))

    def test_all_samples_assigned(self):
        seqs = [f"S{i}" for i in range(50) for _ in range(3)]
        out = group_aware_split(np.arange(len(seqs)), seqs, (0.7, 0.15, 0.15), seed=42)
        self.assertEqual(sum(len(v) for v in out.values()), len(seqs))


if __name__ == "__main__":
    unittest.main()
