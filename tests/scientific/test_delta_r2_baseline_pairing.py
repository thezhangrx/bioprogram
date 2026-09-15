# analysis/tests/test_delta_r2_baseline_pairing.py
"""P1/D5 回归测试: ΔR² 必须与同一实验身份的 sequence 基线配对。

旧实现只用 (split_type, cell_line, model) 作为基线键, 会把
mixed 的 4 个 seed、CNN 的 3 个 kernel 的 sequence 基线互相覆盖,
从而把不同 seed/kernel 的结果相减。
"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from analysis.collect_results import _delta_baseline_key, calculate_delta_R2


def _frame() -> pd.DataFrame:
    return pd.DataFrame([
        # mixed: 每个 seed 有各自的 sequence 基线 (数值不同)
        {"split_type": "mixed", "cell_line": "none", "model": "xgboost", "environment": "sequence", "R2": 0.10, "random_seed": 42, "sequence_kernel": 3},
        {"split_type": "mixed", "cell_line": "none", "model": "xgboost", "environment": "sequence", "R2": 0.20, "random_seed": 43, "sequence_kernel": 3},
        {"split_type": "mixed", "cell_line": "none", "model": "xgboost", "environment": "ctcf", "R2": 0.30, "random_seed": 42, "sequence_kernel": 3},
        {"split_type": "mixed", "cell_line": "none", "model": "xgboost", "environment": "ctcf", "R2": 0.50, "random_seed": 43, "sequence_kernel": 3},
        # cnn: 每个 sequence-kernel 有各自的 sequence 基线
        {"split_type": "mixed", "cell_line": "none", "model": "cnn", "environment": "sequence", "R2": 0.05, "random_seed": 42, "sequence_kernel": 3},
        {"split_type": "mixed", "cell_line": "none", "model": "cnn", "environment": "sequence", "R2": 0.08, "random_seed": 42, "sequence_kernel": 7},
        {"split_type": "mixed", "cell_line": "none", "model": "cnn", "environment": "ctcf", "R2": 0.15, "random_seed": 42, "sequence_kernel": 3},
        {"split_type": "mixed", "cell_line": "none", "model": "cnn", "environment": "ctcf", "R2": 0.28, "random_seed": 42, "sequence_kernel": 7},
        # LOCO: 留出系不同 -> 基线不同
        {"split_type": "all", "cell_line": "hela", "model": "mlp", "environment": "sequence", "R2": 0.02, "random_seed": 42, "sequence_kernel": 3},
        {"split_type": "all", "cell_line": "hl60", "model": "mlp", "environment": "sequence", "R2": 0.12, "random_seed": 42, "sequence_kernel": 3},
        {"split_type": "all", "cell_line": "hela", "model": "mlp", "environment": "dnase", "R2": 0.16, "random_seed": 42, "sequence_kernel": 3},
        {"split_type": "all", "cell_line": "hl60", "model": "mlp", "environment": "dnase", "R2": 0.09, "random_seed": 42, "sequence_kernel": 3},
    ])


class TestDeltaR2BaselinePairing(unittest.TestCase):
    def test_delta_r2_uses_seed_and_kernel_in_baseline_key(self):
        out = calculate_delta_R2(_frame())
        expected = [0.0, 0.0, 0.20, 0.30, 0.0, 0.0, 0.10, 0.20, 0.0, 0.0, 0.14, -0.03]
        np.testing.assert_allclose(out["delta_R2"].to_numpy(), expected)

    def test_baseline_key_separates_identity_axes(self):
        df = _frame()
        keys = {_delta_baseline_key(row) for _, row in df.iterrows()}
        # mixed(seed42) / mixed(seed43) / cnn-k3 / cnn-k7 / all-hela / all-hl60
        self.assertEqual(len(keys), 6)

    def test_sequence_rows_have_zero_delta(self):
        out = calculate_delta_R2(_frame())
        seq = out[out["environment"] == "sequence"]
        self.assertTrue((seq["delta_R2"] == 0.0).all())

    def test_unmatched_environment_yields_nan_not_wrong_pair(self):
        df = _frame()
        df = df[~((df["environment"] == "sequence") & (df["random_seed"] == 43))]
        out = calculate_delta_R2(df)
        rows = out[(out["random_seed"] == 43) & (out["environment"] == "ctcf")]
        self.assertTrue(rows["delta_R2"].isna().all())


if __name__ == "__main__":
    unittest.main()
