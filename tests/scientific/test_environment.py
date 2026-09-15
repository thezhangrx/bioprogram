"""analysis.tests.test_environment — 条件 ΔR² / 主效应 (Paired baseline) 测试。"""
from __future__ import annotations

import unittest

import pandas as pd

from analysis.environment.incremental_effect import (compute_conditional_increments,
                                                    compute_main_effects,
                                                    parse_environment_set)


def _table():
    rows = [
        # split, cell, model, seed, env, R2, RMSE, MAE
        ("single", "hct116", "linear", 42, "sequence", 0.50, 0.20, 0.15),
        ("single", "hct116", "linear", 42, "sequence_ctcf", 0.53, 0.19, 0.14),
        ("single", "hct116", "linear", 42, "sequence_dnase", 0.45, 0.24, 0.17),
        ("single", "hct116", "linear", 42, "sequence_ctcf_dnase", 0.55, 0.16, 0.12),
    ]
    df = pd.DataFrame(rows, columns=["split_type", "cell_line", "model", "random_seed",
                                     "environment", "R2", "RMSE", "MAE"])
    return df


class TestParseEnvSet(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_environment_set("sequence"), set())
        self.assertEqual(parse_environment_set("sequence_ctcf_dnase"), {"ctcf", "dnase"})
        self.assertEqual(parse_environment_set("all"),
                         {"ctcf", "dnase", "h3k4me3", "rrbs"})


class TestConditionalIncrements(unittest.TestCase):
    def test_pairing_is_same_seed_only(self):
        raw = compute_conditional_increments(_table())
        # 每 (e|S) 配对同 seed 行: 2 个 added 因子 x 2 背景
        self.assertEqual(len(raw), 4)
        lookup = {(r["environment_added"], r["background"]): r["delta_r2"]
                  for _, r in raw.iterrows()}
        self.assertAlmostEqual(lookup[("ctcf", "sequence")], 0.03)
        self.assertAlmostEqual(lookup[("dnase", "sequence")], -0.05)
        self.assertAlmostEqual(lookup[("ctcf", "sequence_dnase")], 0.10)
        self.assertAlmostEqual(lookup[("dnase", "sequence_ctcf")], 0.02)

    def test_no_cross_seed_pairing(self):
        base = _table()
        other = base.copy()
        other["random_seed"] = 43
        other["R2"] = other["R2"] + 0.1
        df = pd.concat([base, other], ignore_index=True)
        raw = compute_conditional_increments(df)
        # 每个 (add, background) 恰好 2 条: 每个 seed 各一条
        counts = raw.groupby(["environment_added", "background"]).size()
        self.assertTrue((counts == 2).all())


class TestMainEffects(unittest.TestCase):
    def test_two_factor_main_effect(self):
        raw = compute_conditional_increments(_table())
        main = compute_main_effects(raw)
        get = {(r["cell_line"], r["model"], r["environment"]): r["main_r2_delta"]
               for _, r in main.iterrows()}
        key = ("hct116", "linear")
        self.assertAlmostEqual(get[(key[0], key[1], "ctcf")], 0.065, places=6)
        self.assertAlmostEqual(get[(key[0], key[1], "dnase")], -0.015, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
