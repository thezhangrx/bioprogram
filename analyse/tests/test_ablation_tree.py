"""消融树 (ablation tree) 测试。

结构约定 (用户规范):
  根 = sequence 基线; level1 = ALL(4 环境); level2 = 3 环境; level3 = 2 环境;
  "同一组合不消融" -> 每个组合在树中只出现一次;
  dup 只指异常实验 (数据/实验/参数异常) 对应节点 -> 不绘制, 且其下整棵子树一并剪除;
  节点颜色只由 dR2 决定; 每个非根节点显示 dR2/dMAE/dRMSE/dPearson/dSpearman。

注意: 旧单文件 analyse/visualization.py 被同名包遮蔽, 只能经 PEP 562 兼容桥加载。
"""
from __future__ import annotations

import unittest
from collections import Counter

import numpy as np
import pandas as pd

from analyse.visualization import _load_legacy_viz_module


def _legacy():
    return _load_legacy_viz_module()


def _combo_map_from(metrics_df, metric_cols):
    return {str(r["environment"]).lower():
            tuple(pd.to_numeric(r.get(c, np.nan), errors="coerce") for c in metric_cols)
            for _, r in metrics_df.iterrows()}


class TestAblationTreeStructure(unittest.TestCase):
    def setUp(self):
        m = _legacy()
        self.m = m
        self.cmap = _combo_map_from(m._demo_tree_metrics(), m.TREE_METRIC_COLS)

    def test_levels_root_all_three_two(self):
        root, pruned, notes = self.m._build_ablation_combo_tree(self.cmap, thr=10.0)
        self.assertEqual(notes, [])
        self.assertEqual(pruned, [])
        nodes = self.m._walk_combo_tree(root)
        self.assertEqual(len(nodes), 12)          # 1 + 1 + 4 + 6
        self.assertEqual(Counter(n.level for n in nodes), {0: 1, 1: 1, 2: 4, 3: 6})
        self.assertEqual(Counter(n.depth for n in nodes), {0: 1, 4: 1, 3: 4, 2: 6})
        self.assertTrue(root.is_root)

    def test_each_combo_appears_exactly_once(self):
        root, _, _ = self.m._build_ablation_combo_tree(self.cmap)
        combos = [self.m.combo_name(n.envs) for n in self.m._walk_combo_tree(root)]
        self.assertEqual(len(combos), len(set(combos)), "同一组合不得重复出现 (同一组合不消融)")
        self.assertIn("all", combos)
        self.assertIn("sequence", combos)

    def test_canonical_parent_is_unique(self):
        # 每个 2 环境组合只有一个规范父节点 -> 不会有第二个分支重复消融它
        for subset in (["ctcf", "rrbs"], ["dnase", "rrbs"], ["h3k4me3", "rrbs"]):
            parent = self.m.canonical_parent_envs(subset)
            self.assertEqual(len(parent), 3)
            self.assertTrue(set(subset).issubset(set(parent)))
        self.assertIsNone(self.m.canonical_parent_envs(["ctcf", "dnase", "h3k4me3", "rrbs"]))

    def test_delta_has_five_metrics(self):
        root, _, _ = self.m._build_ablation_combo_tree(self.cmap)
        for node in self.m._walk_combo_tree(root):
            if node.is_root:
                self.assertIsNone(node.delta)
                continue
            self.assertEqual(set(node.delta), {"dR2", "dMAE", "dRMSE", "dPearson", "dSpearman"})
            for key, val in node.delta.items():
                self.assertTrue(np.isfinite(val), f"{key} 必须为有限数值")

    def test_level1_delta_is_all_minus_sequence(self):
        root, _, _ = self.m._build_ablation_combo_tree(self.cmap)
        full = root.children[0]
        self.assertEqual(full.level, 1)
        self.assertEqual(self.m.combo_name(full.envs), "all")
        expected = self.cmap["all"][0] - self.cmap["sequence"][0]
        self.assertAlmostEqual(full.delta["dR2"], expected, places=9)

    def test_delta_is_child_minus_parent(self):
        root, _, _ = self.m._build_ablation_combo_tree(self.cmap)
        for node in self.m._walk_combo_tree(root):
            for child in node.children:
                expected = self.cmap[self.m.combo_name(child.envs)][0] - node.metric[0]
                self.assertAlmostEqual(child.delta["dR2"], expected, places=9)


class TestAblationTreeAnomalyPruning(unittest.TestCase):
    def _cmap(self):
        m = _legacy()
        return m, _combo_map_from(m._demo_tree_metrics(), m.TREE_METRIC_COLS)

    def test_missing_combination_prunes_branch(self):
        m, cmap = self._cmap()
        del cmap["sequence_ctcf_dnase_h3k4me3"]     # 一个 3 环境组合缺失
        root, pruned, _ = m._build_ablation_combo_tree(cmap)
        combos = [m.combo_name(n.envs) for n in m._walk_combo_tree(root)]
        self.assertNotIn("sequence_ctcf_dnase_h3k4me3", combos)
        # 其下 2 环境子树也必须一并剪除
        self.assertNotIn("sequence_ctcf_dnase", combos)
        self.assertTrue(any("missing" in r for _, r in pruned))

    def test_diverged_metric_node_is_pruned_with_subtree(self):
        m, cmap = self._cmap()
        cmap["sequence_ctcf_dnase_h3k4me3"] = (1e12, 0.1, 0.1, 0.5, 0.5)   # 发散 R2
        root, pruned, _ = m._build_ablation_combo_tree(cmap, thr=10.0)
        combos = [m.combo_name(n.envs) for n in m._walk_combo_tree(root)]
        self.assertNotIn("sequence_ctcf_dnase_h3k4me3", combos)
        self.assertNotIn("sequence_ctcf_dnase", combos)
        self.assertTrue(any("diverged" in r for _, r in pruned))

    def test_inconsistent_delta_is_pruned(self):
        m, cmap = self._cmap()
        # dR2 > 0 且 dRMSE > 0 -> 指标不一致 (实验异常)
        base = cmap["all"]
        cmap["sequence_ctcf_dnase_h3k4me3"] = (base[0] + 0.05, base[1], base[2] + 0.05,
                                               base[3] + 0.01, base[4] + 0.01)
        root, pruned, _ = m._build_ablation_combo_tree(cmap, thr=10.0)
        combos = [m.combo_name(n.envs) for n in m._walk_combo_tree(root)]
        self.assertNotIn("sequence_ctcf_dnase_h3k4me3", combos)
        self.assertTrue(any("inconsistency" in r for _, r in pruned))

    def test_anomalous_root_skips_tree(self):
        m, cmap = self._cmap()
        cmap["sequence"] = (float("nan"), 0.1, 0.1, 0.5, 0.5)
        root, _, notes = m._build_ablation_combo_tree(cmap)
        self.assertEqual(root.children, [])
        self.assertTrue(notes)

    def test_correlation_out_of_range_is_anomaly(self):
        m, cmap = self._cmap()
        cmap["sequence_ctcf_dnase"] = (0.6, 0.1, 0.1, 2.5, 0.5)
        _, pruned, _ = m._build_ablation_combo_tree(cmap)
        self.assertTrue(any("correlation out of range" in r for _, r in pruned))


class TestAblationTreeLayout(unittest.TestCase):
    def test_no_box_overlap_after_layout(self):
        m = _legacy()
        cmap = _combo_map_from(m._demo_tree_metrics(), m.TREE_METRIC_COLS)
        root, _, _ = m._build_ablation_combo_tree(cmap)
        n = m._layout_combo_tree(root)
        self.assertGreaterEqual(n, 1)
        self.assertEqual(m._check_no_box_overlap(root), 0)

    def test_leaf_slots_are_monotonic(self):
        m = _legacy()
        cmap = _combo_map_from(m._demo_tree_metrics(), m.TREE_METRIC_COLS)
        root, _, _ = m._build_ablation_combo_tree(cmap)
        m._layout_combo_tree(root)
        leaves = [n for n in m._walk_combo_tree(root) if n.terminal]
        xs = [n.x for n in sorted(leaves, key=lambda n: n.x)]
        self.assertEqual(xs, sorted(xs))
        self.assertEqual(len(xs), len(set(xs)), "叶节点不得共享槽位")


class TestTreeMetricPreparation(unittest.TestCase):
    def test_prepare_keeps_five_metrics(self):
        m = _legacy()
        df = pd.DataFrame({
            "split_type": ["single", "single"], "cell_line": ["hct116", "hct116"],
            "model": ["linear", "linear"], "environment": ["sequence", "all"],
            "R2": [0.1, 0.2], "MAE": [0.2, 0.19], "RMSE": [0.3, 0.28],
            "Pearson": [0.4, 0.45], "Spearman": [0.35, 0.42],
        })
        agg = m._prepare_tree_metrics(df)
        for col in ("R2", "MAE", "RMSE", "Pearson", "Spearman"):
            self.assertIn(col, agg.columns)

    def test_diverged_experiment_removed_before_aggregation(self):
        m = _legacy()
        df = pd.DataFrame({
            "split_type": ["single", "single"], "cell_line": ["hct116", "hct116"],
            "model": ["linear", "linear"], "environment": ["all", "all"],
            "R2": [-4.5e19, 0.2], "MAE": [0.2, 0.2], "RMSE": [0.3, 0.3],
            "Pearson": [0.4, 0.4], "Spearman": [0.4, 0.4],
        })
        agg = m._prepare_tree_metrics(df)
        self.assertAlmostEqual(float(agg["R2"].iloc[0]), 0.2, places=9)


if __name__ == "__main__":
    unittest.main()
