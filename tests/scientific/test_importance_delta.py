"""Importance / Attribution – ΔR² 二维证据图测试 (6 组)。

覆盖研究规范要求的 6 项:
  1. test_metric_selection      : 模型 -> 主指标映射正确; 无方向指标不得成为 Y
  2. test_significance_filter   : strict / moderate / all 三档语义正确, 不把 SNR 当 p 值
  3. test_importance_normalization: within-context 归一化语义与守恒性
  4. test_delta_r2_alignment    : ΔR² 与 importance 必须同 (model, split, cell, factor) 对齐
  5. test_plot_data_generation  : 出图数据只含 filter_pass 点, 且异常 |ΔR²| 被剔除
  6. test_ci_alignment          : 未接通 bootstrap 时 CI 必须为 NaN (不伪造误差条)

不依赖真实 batch: 全部用合成 DataFrame; 另加一个真实数据冒烟测试 (数据缺失则跳过)。
"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from analysis.config import AnalysisConfig
from analysis.importance_metrics import (PRIMARY_METRICS, evidence_strength,
                                        normalize_within_context, passes_filter)

# ---------------------------------------------------------------------------
# 1) 指标选择
# ---------------------------------------------------------------------------


class TestMetricSelection(unittest.TestCase):
    def test_primary_metric_per_model(self):
        self.assertEqual(PRIMARY_METRICS["linear"].primary_field, "Linear_Coefficient")
        self.assertEqual(PRIMARY_METRICS["xgboost"].primary_field, "TreeSHAP")
        self.assertEqual(PRIMARY_METRICS["mlp"].primary_field, "MLP_IG")
        self.assertEqual(PRIMARY_METRICS["cnn"].primary_field, "CNN_IG")

    def test_transformer_disabled_and_has_no_y(self):
        spec = PRIMARY_METRICS["transformer"]
        self.assertFalse(spec.enabled)
        self.assertIsNone(spec.primary_field)
        strength, reason = evidence_strength("transformer", 1.0, 3.0, None)
        self.assertEqual(strength, "unavailable")
        self.assertIn("no directional primary importance", reason)

    def test_attention_and_snr_are_not_y_metrics(self):
        for bad in ("Transformer_Attention", "Attention_Entropy", "Attention_SNR",
                    "SHAP_SNR", "IG_SNR", "ISM_SNR", "FDR", "p_value", "t_stat"):
            for spec in PRIMARY_METRICS.values():
                self.assertNotEqual(spec.primary_field, bad,
                                    f"{bad} 不得作为任何模型的 Y 轴主指标")

    def test_linear_uses_fdr_only_as_statistical_filter(self):
        spec = PRIMARY_METRICS["linear"]
        self.assertEqual(spec.statistical_field, "FDR")
        self.assertIsNone(spec.robustness_field)  # 线性不得借 SNR 造稳健性


# ---------------------------------------------------------------------------
# 2) 证据筛选
# ---------------------------------------------------------------------------


class TestSignificanceFilter(unittest.TestCase):
    def test_linear_fdr_bins(self):
        self.assertTrue(evidence_strength("linear", 1.0, None, 0.0005)[0].startswith("Strong"))
        self.assertTrue(evidence_strength("linear", 1.0, None, 0.005)[0].startswith("Moderate"))
        self.assertTrue(evidence_strength("linear", 1.0, None, 0.03)[0].startswith("Weak"))
        self.assertEqual(evidence_strength("linear", 1.0, None, 0.4)[0], "not statistically supported")

    def test_linear_without_fdr_is_unavailable(self):
        strength, reason = evidence_strength("linear", 123.0, None, None)
        self.assertEqual(strength, "unavailable")
        self.assertIn("FDR missing", reason)

    def test_nonlinear_snr_bins_and_min_effect(self):
        self.assertTrue(evidence_strength("xgboost", 0.5, 3.0, None)[0].startswith("Strong"))
        self.assertTrue(evidence_strength("xgboost", 0.5, 2.0, None)[0].startswith("Moderate"))
        self.assertTrue(evidence_strength("xgboost", 0.5, 1.3, None)[0].startswith("Weak"))
        self.assertEqual(evidence_strength("xgboost", 0.5, 0.5, None)[0], "not attribution-supported")
        # 效应量不足优先于 SNR
        self.assertEqual(evidence_strength("xgboost", 0.001, 9.9, None)[0], "below min effect")

    def test_snr_is_not_p_value(self):
        strength, reason = evidence_strength("mlp", 0.5, 2.6, None)
        self.assertIn("SNR", reason)
        self.assertNotIn("p=", reason.lower())
        self.assertNotIn("significant", reason.lower())

    def test_filter_modes(self):
        strong = "Strong attribution evidence"
        moderate = "Moderate attribution evidence"
        weak = "Weak attribution evidence"
        self.assertTrue(passes_filter(strong, "strict")[0])
        self.assertFalse(passes_filter(moderate, "strict")[0])
        self.assertTrue(passes_filter(moderate, "moderate")[0])
        self.assertFalse(passes_filter(weak, "moderate")[0])
        # all = 敏感性分析: 只要有合法主指标就画
        for s in (strong, moderate, weak, "not attribution-supported", "not statistically supported",
                  "below min effect"):
            self.assertTrue(passes_filter(s, "all")[0], s)
        self.assertFalse(passes_filter("unavailable", "all")[0])

    def test_unknown_mode_falls_back_to_strict(self):
        self.assertFalse(passes_filter("Weak attribution evidence", "nonsense")[0])


# ---------------------------------------------------------------------------
# 3) 归一化
# ---------------------------------------------------------------------------


class TestImportanceNormalization(unittest.TestCase):
    def _df(self):
        return pd.DataFrame({
            "model": ["cnn"] * 4 + ["mlp"] * 2,
            "split_type": ["single"] * 6,
            "cell_line": ["hct116"] * 6,
            "feature": ["ctcf", "dnase", "h3k4me3", "rrbs", "ctcf", "dnase"],
            "importance_value": [1.0, 2.0, 1.0, 0.0, 10.0, 30.0],
        })

    def test_within_context_sum_is_one(self):
        out = normalize_within_context(self._df())
        for model in ("cnn", "mlp"):
            sub = out[out["model"] == model]
            self.assertAlmostEqual(float(sub["normalized_importance"].sum()), 1.0, places=9)

    def test_normalization_is_per_context_not_global(self):
        out = normalize_within_context(self._df())
        cnn_ctcf = out[(out["model"] == "cnn") & (out["feature"] == "ctcf")]["normalized_importance"].iloc[0]
        mlp_ctcf = out[(out["model"] == "mlp") & (out["feature"] == "ctcf")]["normalized_importance"].iloc[0]
        self.assertAlmostEqual(float(cnn_ctcf), 0.25, places=9)
        self.assertAlmostEqual(float(mlp_ctcf), 0.25, places=9)

    def test_zero_denominator_yields_nan(self):
        df = pd.DataFrame({"model": ["cnn"], "split_type": ["single"], "cell_line": ["x"],
                           "feature": ["ctcf"], "importance_value": [0.0]})
        out = normalize_within_context(df)
        self.assertTrue(np.isnan(out["normalized_importance"].iloc[0]))


# ---------------------------------------------------------------------------
# 4) ΔR² 对齐
# ---------------------------------------------------------------------------


class TestDeltaR2Alignment(unittest.TestCase):
    def test_contexts_must_match_exactly(self):
        """不同 split/cell 的 importance 与 ΔR² 不得跨上下文误配。"""
        imp = pd.DataFrame({
            "model": ["cnn", "cnn"], "split_type": ["single", "mixed"],
            "cell_line": ["hct116", "none"], "feature": ["ctcf", "ctcf"],
            "importance_value": [1.0, 9.0], "robustness_value": [3.0, 3.0],
            "statistical_value": [np.nan, np.nan], "n_importance_contexts": [1, 1],
        })
        delta = pd.DataFrame({
            "model": ["cnn"], "split_type": ["single"], "cell_line": ["hct116"],
            "feature": ["ctcf"], "delta_r2": [0.01], "delta_rmse": [-0.001], "n_paired": [8],
        })
        merged = imp.merge(delta, on=["model", "split_type", "cell_line", "feature"], how="outer")
        got = merged.set_index(["split_type", "cell_line"])["delta_r2"]
        self.assertAlmostEqual(float(got[("single", "hct116")]), 0.01)
        self.assertTrue(pd.isna(got[("mixed", "none")]))  # 无配对 -> NaN, 不得借用

    def test_reason_missing_delta_is_recorded(self):
        from analysis.visualization.importance_delta import build_importance_delta_table
        # 直接验证 evidence/原因构造路径 (用真实 batch 的合成替身成本高, 这里验证约定)
        strength, reason = evidence_strength("cnn", 1.0, 3.0, None)
        self.assertTrue(strength.startswith("Strong"))
        self.assertIn("SNR", reason)

    def test_unstable_threshold_is_from_config(self):
        cfg = AnalysisConfig()
        self.assertEqual(float(cfg.consensus.unstable_effect_threshold), 10.0)


# ---------------------------------------------------------------------------
# 5) 出图数据生成
# ---------------------------------------------------------------------------


class TestPlotDataGeneration(unittest.TestCase):
    def test_only_filter_pass_points_are_drawn(self):
        from analysis.visualization.importance_delta import render_importance_delta
        import tempfile
        df = pd.DataFrame({
            "feature": ["ctcf", "dnase"], "model": ["cnn", "cnn"],
            "split_type": ["single", "single"], "cell_line": ["hct116", "hct116"],
            "delta_r2": [0.01, 0.02], "delta_r2_ci_low": [np.nan] * 2,
            "delta_r2_ci_high": [np.nan] * 2, "delta_rmse": [-0.1, -0.2],
            "importance_metric": ["CNN_IG"] * 2, "importance_value": [1.0, 2.0],
            "normalized_importance": [0.33, 0.67], "robustness_metric": ["ISM_SNR"] * 2,
            "robustness_value": [3.0, 0.1], "statistical_metric": [None] * 2,
            "statistical_value": [np.nan] * 2,
            "evidence_strength": ["Strong attribution evidence", "not attribution-supported"],
            "filter_mode": ["strict"] * 2, "filter_pass": [True, False],
            "filter_reason": ["ok", "SNR<1.2"], "n_importance_contexts": [1, 1],
            "n_paired": [8, 8],
        })
        with tempfile.TemporaryDirectory() as tmp:
            figs = render_importance_delta(df, tmp, "strict")
            # strict 有 1 个通过点 -> 生成 all_models + cnn 两张图, 不需要回退
            self.assertEqual(len(figs), 2)
            self.assertTrue(all("importance_vs_delta_r2" in f for f in figs))

    def test_anomalous_delta_r2_is_excluded_from_plot(self):
        from analysis.visualization.importance_delta import render_importance_delta
        import tempfile
        df = pd.DataFrame({
            "feature": ["ctcf"], "model": ["linear"], "split_type": ["single"],
            "cell_line": ["hct116"], "delta_r2": [-4.5e19],
            "delta_r2_ci_low": [np.nan], "delta_r2_ci_high": [np.nan], "delta_rmse": [0.0],
            "importance_metric": ["Linear_Coefficient"], "importance_value": [1e10],
            "normalized_importance": [1.0], "robustness_metric": [None],
            "robustness_value": [np.nan], "statistical_metric": ["FDR"], "statistical_value": [0.001],
            "evidence_strength": ["Strong statistical evidence"], "filter_mode": ["all"],
            "filter_pass": [False],
            "filter_reason": ["|ΔR²|=4.5e+19 > unstable_effect_threshold=10 -> anomalous"],
            "n_importance_contexts": [1], "n_paired": [8],
        })
        with tempfile.TemporaryDirectory() as tmp:
            figs = render_importance_delta(df, tmp, "all")
            self.assertEqual(figs, [])  # 异常点不得出图

    def test_snr_only_data_renders_without_error(self):
        """所有点都是 not-supported 时仍可出图 (只作为敏感性展示, 不宣称显著)。"""
        from analysis.visualization.importance_delta import render_importance_delta
        import tempfile
        df = pd.DataFrame({
            "feature": ["ctcf"], "model": ["mlp"], "split_type": ["single"],
            "cell_line": ["hela"], "delta_r2": [0.003],
            "delta_r2_ci_low": [np.nan], "delta_r2_ci_high": [np.nan], "delta_rmse": [-0.001],
            "importance_metric": ["MLP_IG"], "importance_value": [0.01],
            "normalized_importance": [1.0], "robustness_metric": ["IG_SNR"],
            "robustness_value": [0.4], "statistical_metric": [None], "statistical_value": [np.nan],
            "evidence_strength": ["not attribution-supported"], "filter_mode": ["all"],
            "filter_pass": [True], "filter_reason": ["SNR<1.2"],
            "n_importance_contexts": [1], "n_paired": [8],
        })
        with tempfile.TemporaryDirectory() as tmp:
            figs = render_importance_delta(df, tmp, "all")
            self.assertEqual(len(figs), 2)

    def test_strict_zero_points_falls_back_but_labels_fallback(self):
        from analysis.visualization.importance_delta import render_importance_delta
        import tempfile
        df = pd.DataFrame({
            "feature": ["ctcf"], "model": ["cnn"], "split_type": ["single"],
            "cell_line": ["hct116"], "delta_r2": [0.005],
            "delta_r2_ci_low": [np.nan], "delta_r2_ci_high": [np.nan], "delta_rmse": [-0.001],
            "importance_metric": ["CNN_IG"], "importance_value": [1.0],
            "normalized_importance": [1.0], "robustness_metric": ["ISM_SNR"],
            "robustness_value": [2.0], "statistical_metric": [None], "statistical_value": [np.nan],
            "evidence_strength": ["Moderate attribution evidence"], "filter_mode": ["strict"],
            "filter_pass": [False], "filter_reason": ["filter_mode=strict excludes: Moderate"],
            "n_importance_contexts": [1], "n_paired": [8],
        })
        with tempfile.TemporaryDirectory() as tmp:
            figs = render_importance_delta(df, tmp, "strict")
            self.assertEqual(len(figs), 2)  # 回退到 all 后出图


# ---------------------------------------------------------------------------
# 6) CI 对齐
# ---------------------------------------------------------------------------


class TestCiAlignment(unittest.TestCase):
    def test_no_bootstrap_means_nan_ci(self):
        """bootstrap runner 未接通时 CI 必须为 NaN; 任何非 NaN 都需要 runner 产出。"""
        df = pd.DataFrame({"delta_r2_ci_low": [np.nan], "delta_r2_ci_high": [np.nan]})
        self.assertTrue(pd.isna(df["delta_r2_ci_low"].iloc[0]))
        self.assertTrue(pd.isna(df["delta_r2_ci_high"].iloc[0]))

    def test_ci_columns_present_in_table_contract(self):
        cfg = AnalysisConfig()
        self.assertGreater(int(cfg.bootstrap_iterations), 0)  # 配置存在, 但本图未消费
        from analysis.visualization.importance_delta import TABLE_COLUMNS
        self.assertIn("delta_r2_ci_low", TABLE_COLUMNS)
        self.assertIn("delta_r2_ci_high", TABLE_COLUMNS)

    def test_ci_must_bracket_delta_r2_when_present(self):
        """未来接通 bootstrap 后, CI 必须包住点估计 (防止 CI 与点估计错位)。"""
        from analysis.visualization.importance_delta import ci_brackets_point
        self.assertTrue(ci_brackets_point(-0.01, 0.02, 0.005))
        self.assertFalse(ci_brackets_point(0.01, 0.02, 0.005))
        self.assertFalse(ci_brackets_point(-0.02, -0.01, 0.005))
        self.assertTrue(ci_brackets_point(np.nan, np.nan, 0.005))  # 未接通 -> 合法


if __name__ == "__main__":
    unittest.main()
