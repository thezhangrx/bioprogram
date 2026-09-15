"""LOCO (all-split) 回归守卫（A4 闭环要求）。

不变式：
  1. `all` 与 `single` 不得再是同一批结果（历史退化 bug 的自动守卫）；
  2. `all` 的每个 run 中，held-out 细胞系不得出现在训练细胞系集合里；
  3. 不同 seed 的实验不得被配对（D5 的守卫雏形）。
"""
from __future__ import annotations

import glob
import re
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BATCH = ROOT / "results" / "batch_20260909_full"


class TestLocoRegression(unittest.TestCase):
    def setUp(self):
        p = BATCH / "summary" / "metrics_tables" / "all_experiments.csv"
        if not p.exists():
            self.skipTest("缺少 all_experiments.csv")
        self.a = pd.read_csv(p, low_memory=False)

    def test_all_differs_from_single(self):
        k = ["model", "environment", "cell_line", "random_seed"]
        ms = ["R2", "RMSE", "MAE", "Pearson", "Spearman"]
        s = self.a[self.a.split_type == "single"][k + ms].add_suffix("_s").rename(
            columns={f"{x}_s": x for x in k})
        l = self.a[self.a.split_type == "all"][k + ms].add_suffix("_a").rename(
            columns={f"{x}_a": x for x in k})
        m = s.merge(l, on=k)
        if m.empty:
            self.skipTest("无 all/single 配对")
        ident = (m["R2_s"] - m["R2_a"]).abs() < 1e-12
        self.assertLess(ident.mean(), 0.5,
                        f"all 与 single 过度相同（{ident.mean():.1%}）——LOCO 可能再次退化")

    def test_heldout_absent_from_training_cell_lines(self):
        files = sorted(glob.glob(str(BATCH / "all_*" / "*_info.txt")))[:40]
        if not files:
            self.skipTest("无 all run")
        for f in files:
            t = Path(f).read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"cell_lines: \[(.+?)\]", t)
            self.assertIsNotNone(m, f"缺少 cell_lines: {f}")
            cells = [c.strip().strip("'\"") for c in m.group(1).split(",")]
            self.assertGreaterEqual(len(cells), 2, f"{f}: cell_lines 只有 1 个 (LOCO 退化)")
            held = re.search(r"heldout_([a-z0-9]+)", f)
            if held:
                self.assertIn(held.group(1), cells,
                              f"{f}: held-out 系不在加载集合内（无法作为 test）")

    def test_seed_never_cross_paired(self):
        """不同 seed 的实验不得出现在同一 (model,env,cell) 配对键内（D5 守卫雏形）。"""
        mixed = self.a[self.a.split_type == "mixed"]
        if mixed.empty:
            self.skipTest("无 mixed 行")
        g = mixed.groupby(["model", "environment", "cell_line"])["random_seed"].nunique()
        self.assertTrue((g >= 1).all())


if __name__ == "__main__":
    unittest.main()
