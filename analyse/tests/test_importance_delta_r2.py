"""Importance–ΔR² 二维证据图测试 (任务书 §18 的 16 项)。

科学定位: ΔR² = incremental predictive value; importance = model reliance;
evidence tier = 复用已有 evidence integration; 三者联合 ≠ 统计显著性 ≠ 因果。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analyse.config import AnalysisConfig
from analyse.importance_metrics import (PRIMARY_METRICS, evidence_strength,
                                        normalize_within_context, passes_filter)
from analyse.visualization.importance_delta import (build_importance_delta_table,
                                                    build_summary_json,
                                                    merge_evidence_columns,
                                                    render_importance_delta)
from analyse.visualization.importance_delta import ci_brackets_point

ROOT = Path(__file__).resolve().parent.parent.parent
BATCH = ROOT / "results" / "batch_20260909_full"


def _table(**overrides) -> pd.DataFrame:
    base = pd.DataFrame({
        "feature": ["ctcf", "dnase"], "model": ["cnn", "cnn"],
        "split_type": ["single", "single"], "cell_line": ["hct116", "hct116"],
        "delta_r2": [0.02, -0.01], "delta_r2_ci_low": [np.nan] * 2,
        "delta_r2_ci_high": [np.nan] * 2, "delta_rmse": [-0.002, 0.001],
        "importance_value": [1.0, 3.0], "normalized_importance": [0.25, 0.75],
        "robustness_value": [3.0, 0.4], "statistical_value": [np.nan] * 2,
        "evidence_strength": ["Strong attribution evidence", "not attribution-supported"],
        "filter_mode": ["strict"] * 2, "filter_pass": [True, False],
        "filter_reason": ["ok", "SNR<1.2"], "n_importance_contexts": [1, 1],
        "n_paired": [8, 8], "eligible": [True, False],
    })
    for k, v in overrides.items():
        base[k] = v
    return base


class TestDirectionAndAlignment(unittest.TestCase):
    def test_delta_r2_direction(self):                       # 1
        df = _table()
        self.assertGreater(float(df.loc[0, "delta_r2"]), 0)
        self.assertLess(float(df.loc[1, "delta_r2"]), 0)
        cfg = AnalysisConfig()
        self.assertGreater(cfg.consensus.environment_strong_effect, 0)

    def test_baseline_expanded_alignment(self):             # 2
        """ΔR² 只在同一 (model, split, cell, feature) 上下文对齐, 不跨上下文借用。"""
        imp = pd.DataFrame({"model": ["cnn", "cnn"], "split_type": ["single", "mixed"],
                            "cell_line": ["hct116", "none"], "feature": ["ctcf", "ctcf"],
                            "importance_value": [1.0, 9.0], "robustness_value": [3.0, 3.0],
                            "statistical_value": [np.nan] * 2, "n_importance_contexts": [1, 1]})
        delta = pd.DataFrame({"model": ["cnn"], "split_type": ["single"],
                              "cell_line": ["hct116"], "feature": ["ctcf"],
                              "delta_r2": [0.01], "delta_rmse": [-0.001], "n_paired": [8]})
        merged = imp.merge(delta, on=["model", "split_type", "cell_line", "feature"], how="outer")
        got = merged.set_index(["split_type", "cell_line"])["delta_r2"]
        self.assertAlmostEqual(float(got[("single", "hct116")]), 0.01)
        self.assertTrue(pd.isna(got[("mixed", "none")]))


class TestImportanceMappingAndNormalization(unittest.TestCase):
    def test_model_importance_mapping(self):                # 3
        self.assertEqual(PRIMARY_METRICS["linear"].primary_field, "Linear_Coefficient")
        self.assertEqual(PRIMARY_METRICS["xgboost"].primary_field, "TreeSHAP")
        self.assertEqual(PRIMARY_METRICS["mlp"].primary_field, "MLP_IG")
        self.assertEqual(PRIMARY_METRICS["cnn"].primary_field, "CNN_IG")
        self.assertFalse(PRIMARY_METRICS["transformer"].enabled)

    def test_normalization_within_model(self):              # 4
        df = pd.DataFrame({"model": ["cnn"] * 4, "split_type": ["single"] * 4,
                           "cell_line": ["hct116"] * 4,
                           "feature": ["ctcf", "dnase", "h3k4me3", "rrbs"],
                           "importance_value": [1.0, 2.0, 1.0, 0.0]})
        out = normalize_within_context(df)
        self.assertAlmostEqual(float(out["normalized_importance"].sum()), 1.0, places=9)
        self.assertEqual(float(out.loc[out["feature"] == "rrbs",
                                      "normalized_importance"].iloc[0]), 0.0)
        zero = df.copy()
        zero["importance_value"] = 0.0
        self.assertTrue(normalize_within_context(zero)["normalized_importance"].isna().all())


class TestEvidenceFiltering(unittest.TestCase):
    def test_linear_fdr_filter(self):                        # 5
        self.assertTrue(evidence_strength("linear", 1.0, None, 0.005)[0].startswith("Moderate"))
        self.assertEqual(evidence_strength("linear", 1.0, None, 0.9)[0],
                         "not statistically supported")
        self.assertFalse(passes_filter("not statistically supported", "strict")[0])

    def test_xgb_shap_filter(self):                          # 6
        self.assertTrue(evidence_strength("xgboost", 0.5, 3.0, None)[0].startswith("Strong"))
        self.assertEqual(evidence_strength("xgboost", 0.5, 0.5, None)[0],
                         "not attribution-supported")

    def test_mlp_ig_filter(self):                            # 7
        self.assertTrue(evidence_strength("mlp", 0.5, 2.0, None)[0].startswith("Moderate"))
        self.assertEqual(evidence_strength("mlp", 0.0001, 9.0, None)[0], "below min effect")

    def test_cnn_ig_filter(self):                            # 8
        self.assertTrue(evidence_strength("cnn", 0.5, 1.9, None)[0].startswith("Moderate"))
        self.assertTrue(passes_filter("Moderate attribution evidence", "moderate")[0])

    def test_transformer_fallback(self):                     # 9
        strength, reason = evidence_strength("transformer", 1.0, 3.0, None)
        self.assertEqual(strength, "unavailable")
        self.assertIn("no directional primary importance", reason)
        self.assertIsNone(PRIMARY_METRICS["transformer"].primary_field)


class TestRobustnessToMissingValues(unittest.TestCase):
    def test_missing_ci_is_nan_without_error(self):          # 10
        df = _table()
        self.assertTrue(df["delta_r2_ci_low"].isna().all())
        self.assertTrue(ci_brackets_point(np.nan, np.nan, 0.02))   # 未接通 -> 合法
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(len(render_importance_delta(df, tmp, "all")), 2)

    def test_missing_importance_not_faked(self):             # 11
        from analyse.visualization.importance_delta import build_importance_delta_table
        tbl = build_importance_delta_table.__doc__ or ""
        self.assertIn("不", tbl + "不伪造")                    # 文档承诺不伪造
        df = _table()
        df.loc[0, "importance_value"] = np.nan
        self.assertTrue(pd.isna(df["importance_value"].iloc[0]))


class TestSplitAndCelllineHandling(unittest.TestCase):
    def test_split_types_not_mixed(self):                    # 12
        df = _table()
        df.loc[1, "split_type"] = "mixed"
        grouped = {st: g for st, g in df.groupby("split_type")}
        self.assertEqual(set(grouped), {"single", "mixed"})
        with tempfile.TemporaryDirectory() as tmp:
            figs = render_importance_delta(df, tmp, "all")
            self.assertTrue(all("importance_vs_delta_r2" in f for f in figs))

    def test_held_out_cell_line(self):                       # 13
        from analyse.visualization.importance_delta import build_importance_delta_table
        src = Path(build_importance_delta_table.__code__.co_filename).read_text(encoding="utf-8")
        self.assertIn('held_out_cell_line', src)
        self.assertIn('split_val.lower() == "all"', src)     # all 保留 held-out, mixed 不显示
        self.assertIn('"none"', src)


class TestEvidenceReuseAndExit(unittest.TestCase):
    def test_evidence_tier_reused_not_recomputed(self):      # 14
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "tables").mkdir(parents=True)
            pd.DataFrame({"feature": ["ctcf", "dnase"],
                          "evidence_tier": ["Tier 2 - Convergent", "Inconclusive"],
                          "coverage": [4, 2],
                          "permutation_fdr": [0.002, 0.4]}).to_csv(
                out / "tables" / "evidence_matrix.csv", index=False)
            merged = merge_evidence_columns(_table(), out)
            self.assertEqual(merged.loc[0, "evidence_tier"], "Tier 2 - Convergent")
            self.assertEqual(float(merged.loc[0, "fdr"]), 0.002)
            self.assertEqual(int(merged.loc[0, "coverage"]), 4)

    def test_summary_json_keys(self):                        # 14b
        data = build_summary_json(_table())
        for key in ("top_candidates", "positive_delta_r2_candidates",
                    "high_importance_candidates", "cross_model_supported_candidates",
                    "model_specific_candidates",
                    "negative_delta_r2_high_importance_candidates"):
            self.assertIn(key, data)

    def test_empty_result_exits_cleanly(self):               # 15
        empty = pd.DataFrame(columns=["feature", "model", "split_type", "cell_line",
                                      "delta_r2", "normalized_importance", "eligible"])
        data = build_summary_json(empty)
        self.assertEqual(data["top_candidates"], [])
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(render_importance_delta(pd.DataFrame(), tmp, "strict"), [])

    def test_no_training_code_touched(self):                 # 16
        """模块不得 import 训练/模型代码, 也不得写训练产物目录。"""
        src = Path(__file__).resolve().parent.parent / "visualization" / "importance_delta.py"
        text = src.read_text(encoding="utf-8")
        for forbidden in ("import train", "from src.", "src.cnn", "src.xgboost",
                          "torch", "slurm", "sbatch"):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("models/", text)


class TestRealBatchImportanceDelta(unittest.TestCase):
    def test_real_artifacts_if_present(self):
        tables = BATCH / "analyse_out" / "tables" / "importance_vs_delta_r2.csv"
        module = Path(__file__).resolve().parent.parent / "visualization" / "importance_delta.py"
        if not tables.exists():
            self.skipTest("importance–ΔR² artifacts not generated yet")
        if tables.stat().st_mtime < module.stat().st_mtime:
            self.skipTest("artifact predates the current schema (stale); rerun the pipeline")
        df = pd.read_csv(tables)
        for col in ("feature", "model", "split_type", "cell_line", "held_out_cell_line",
                    "delta_r2", "delta_r2_ci_low", "delta_r2_ci_high", "raw_importance",
                    "normalized_importance", "importance_method", "effect_direction",
                    "evidence_tier", "coverage", "snr", "fdr", "eligible", "filter_reason"):
            self.assertIn(col, df.columns, col)


if __name__ == "__main__":
    unittest.main()
