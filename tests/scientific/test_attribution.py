"""analysis.tests.test_attribution — attribution 统一抽取测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analysis.attribution.extractors import extract_attribution_table
from analysis.attribution.summary import top_attribution_features


def _make_batch() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="attr_"))
    # linear 新白名单 CSV
    lin_dir = tmp / "single_hct116_linear_all"
    lin_dir.mkdir()
    (lin_dir / "linear_regression_info.txt").write_text(
        "model: linear\nsplit_type: single\ncell_line: hct116\nenvironment: all\n",
        encoding="utf-8")
    pd.DataFrame({
        "Feature": ["pos18_C", "Bias"],
        "Linear_Coefficient": [0.5, 1.0],
        "SE": [0.02, 0.1],
        "t_stat": [25.0, 10.0],
        "p_value": [1e-9, 0.01],
        "FDR": [1e-8, 0.02],
    }).to_csv(lin_dir / "linear_regression_weights.csv", index=False)

    # xgboost 旧列 (含已弃用的 permutation 列, 抽取不应外泄)
    xgb_dir = tmp / "single_hct116_xgboost_all"
    xgb_dir.mkdir()
    (xgb_dir / "xgboost_info.txt").write_text(
        "model: xgboost\nsplit_type: single\ncell_line: hct116\nenvironment: all\n",
        encoding="utf-8")
    pd.DataFrame({
        "Feature": ["pos20_G", "pos1_A"],
        "Importance_gain": [0.8, 0.1],
        "SHAP_mean": [0.3, 0.02],
        "SHAP_SNR": [6.0, 0.5],
        "Permutation_p_val": [0.0, 0.4],
    }).to_csv(xgb_dir / "xgboost_feature_importance.csv", index=False)
    return tmp


class TestAttributionExtraction(unittest.TestCase):
    def test_canonical_rows(self):
        table = extract_attribution_table(_make_batch())
        # linear 1 行 (Bias 剔除), xgboost: treeshap+gain 2 特征 x 2 方法 = 4 行
        self.assertEqual(len(table), 1 + 4)
        methods = set(table["method"])
        self.assertIn("linear_coefficient", methods)
        self.assertIn("xgboost_treeshap", methods)
        self.assertIn("xgboost_gain", methods)
        self.assertTrue((table["feature"] != "Bias").all())
        # 不允许统计字段外泄到统一 schema
        for col in ("p_value", "fdr", "permutation"):
            self.assertNotIn(col, table.columns)

    def test_position_channel_parsing(self):
        table = extract_attribution_table(_make_batch())
        g = table[table["feature"] == "pos20_G"].iloc[0]
        self.assertEqual(g["position"], 20)
        self.assertEqual(g["channel"], "G")
        c = table[table["feature"] == "pos18_C"].iloc[0]
        self.assertEqual(c["channel"], "C")

    def test_top_summary(self):
        table = extract_attribution_table(_make_batch())
        top = top_attribution_features(table, top_n=2)
        self.assertFalse(top.empty)
        n_groups = table.groupby(["model", "method"]).ngroups
        self.assertLessEqual(len(top), 2 * n_groups)


if __name__ == "__main__":
    unittest.main(verbosity=2)
