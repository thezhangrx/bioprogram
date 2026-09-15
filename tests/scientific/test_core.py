"""analysis.tests — 核心科学函数测试 (unittest, 无 pytest 依赖)。

覆盖: paired baseline / ΔR² / ΔRMSE 一致性 / FDR / Bootstrap CI / SNR 标签 /
coverage / direction concordance / evidence tier / cell-line consistency /
AnalysisPlan 依赖校验。
"""
from __future__ import annotations

import math
import unittest

import numpy as np

from analysis.config import AnalysisConfig
from analysis.data.loaders import load_experiment_table
from analysis.data.validation import metric_consistency_flags, validate_metric_consistency
from analysis.evidence.integration import (classify_cellline_consistency,
                                          classify_evidence_tier,
                                          direction_concordance)
from analysis.plans import AnalysisPlan, Capabilities, validate_analysis_plan
from analysis.schemas import EvidenceTier
from analysis.stats.bootstrap import bootstrap_ci, bootstrap_difference_ci
from analysis.stats.effect_size import compute_paired_increment
from analysis.stats.multiple_testing import bh_fdr


class TestEffectSize(unittest.TestCase):
    def test_paired_increment_same_cohort(self):
        inc, ok = compute_paired_increment(0.50, 0.55, baseline_n=100, expanded_n=100)
        self.assertAlmostEqual(inc, 0.05)
        self.assertTrue(ok)

    def test_paired_increment_different_cohort_flagged(self):
        inc, ok = compute_paired_increment(0.50, 0.55, baseline_n=100, expanded_n=90)
        self.assertTrue(math.isnan(inc))
        self.assertFalse(ok)          # 破坏 paired baseline -> 不可用于归因


class TestMetricConsistency(unittest.TestCase):
    def test_same_increase_is_inconsistency(self):
        flags = metric_consistency_flags(delta_r2=0.03, delta_rmse=0.02)
        self.assertIn("metric_inconsistency_same_increase", flags)

    def test_same_decrease_is_inconsistency(self):
        flags = metric_consistency_flags(delta_r2=-0.03, delta_rmse=-0.02)
        self.assertIn("metric_inconsistency_same_decrease", flags)

    def test_opposite_signs_ok(self):
        self.assertEqual(metric_consistency_flags(0.03, -0.02), [])


class TestFDR(unittest.TestCase):
    def test_bh_known_result(self):
        p = [0.001, 0.004, 0.02, 0.1]
        q = bh_fdr(p)
        # q 单调非降 (按 p 序), 且 min(q*?) 人工核对: m=4
        self.assertTrue(all(q[i] <= q[i + 1] + 1e-12 for i in range(len(q) - 1)))
        self.assertAlmostEqual(q[0], min(0.004, 1.0), places=9)  # 0.001*4/1=0.004

    def test_nan_preserved(self):
        q = bh_fdr([0.01, None, 0.2])
        self.assertTrue(math.isnan(q[1]))
        self.assertLessEqual(q[2], 1.0)


class TestBootstrap(unittest.TestCase):
    def test_ci_reproducible_and_contains_mean(self):
        rng = np.random.default_rng(0)
        data = rng.normal(0.5, 0.1, 500).tolist()
        a = bootstrap_ci(data, np.mean, n_iterations=500, seed=7)
        b = bootstrap_ci(data, np.mean, n_iterations=500, seed=7)
        self.assertEqual(a.ci_low, b.ci_low)
        self.assertTrue(a.available)
        self.assertLessEqual(a.ci_low, a.estimate)
        self.assertGreaterEqual(a.ci_high, a.estimate)

    def test_unpaired_baseline_unavailable(self):
        res = bootstrap_difference_ci([0.1, 0.2, 0.3], [0.1, 0.2], np.mean)
        self.assertFalse(res.available)     # 配对被破坏 -> unavailable, 不是 0


class TestIntegration(unittest.TestCase):
    def test_direction_concordance(self):
        self.assertAlmostEqual(direction_concordance([0.1, 0.2, -0.3]), 2 / 3)
        self.assertIsNone(direction_concordance([None, None]))

    def test_cellline_consistency(self):
        label, direction = classify_cellline_consistency(
            {"hct116": 0.03, "hela": 0.02, "hl60": 0.04})
        self.assertEqual(label, "Context-consistent")
        self.assertEqual(direction, "+")

    def test_tier1_requires_two_models_and_strong_evidence(self):
        cfg = AnalysisConfig()
        tier = classify_evidence_tier(
            applicable_model_count=4, supporting_model_count=2,
            concordance=1.0, strong_stat_or_attribution=True,
            ci_crosses_zero=False, config=cfg)
        self.assertEqual(tier, EvidenceTier.TIER1)

    def test_conflicting_direction_inconclusive(self):
        cfg = AnalysisConfig()
        tier = classify_evidence_tier(
            applicable_model_count=4, supporting_model_count=2,
            concordance=0.5, strong_stat_or_attribution=True,
            ci_crosses_zero=False, conflicting_direction=True, config=cfg)
        self.assertEqual(tier, EvidenceTier.INCONCLUSIVE)


class TestLoaderAndValidation(unittest.TestCase):
    def test_loader_and_same_cohort_consistency(self):
        import tempfile
        from pathlib import Path
        import pandas as pd
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            (batch / "summary" / "metrics_tables").mkdir(parents=True)
            rows = [
                # sequence baseline: R2=0.50, RMSE=0.20 (同 seed)
                dict(run_name="r0", model="linear", split_type="single", cell_line="hct116",
                     environment="sequence", random_seed=42, n_train=10, n_valid=5, n_test=5,
                     R2=0.50, RMSE=0.20, MAE=0.15, Pearson=0.8, Spearman=0.8),
                # ctcf 同 seed: R2 升且 RMSE 升 -> 同 cohort 下指标矛盾
                dict(run_name="r1", model="linear", split_type="single", cell_line="hct116",
                     environment="sequence_ctcf", random_seed=42, n_train=10, n_valid=5, n_test=5,
                     R2=0.53, RMSE=0.23, MAE=0.16, Pearson=0.8, Spearman=0.8),
                # 另一 seed 的 ctcf: R2 升 RMSE 降 -> 正常 (不同 seed 不应误伤)
                dict(run_name="r2", model="linear", split_type="mixed", cell_line="none",
                     environment="sequence", random_seed=43, n_train=10, n_valid=5, n_test=5,
                     R2=0.40, RMSE=0.30, MAE=0.2, Pearson=0.7, Spearman=0.7),
                dict(run_name="r3", model="linear", split_type="mixed", cell_line="none",
                     environment="sequence_ctcf", random_seed=43, n_train=10, n_valid=5, n_test=5,
                     R2=0.42, RMSE=0.28, MAE=0.19, Pearson=0.7, Spearman=0.7),
            ]
            pd.DataFrame(rows).to_csv(
                batch / "summary" / "metrics_tables" / "all_experiments.csv", index=False)
            table = load_experiment_table(batch)
            self.assertEqual(len(table), 4)
            self.assertEqual(int(table["R2"].notna().sum()), 4)
            flags = validate_metric_consistency(table)
            self.assertEqual(len(flags), 1)          # 只有 r1 同 seed 同号
            self.assertIn("metric_inconsistency_same_increase", flags.iloc[0]["flags"])


class TestAnalysisPlanValidator(unittest.TestCase):
    def test_motif_enrichment_needs_discovery(self):
        plan = AnalysisPlan()
        plan.sequence.motif_enrichment = True
        plan.sequence.motif_discovery = False
        caps = Capabilities(n_cell_lines=4, n_environment_factors=4, n_models=5,
                            has_cnn=True, has_transformer=True, has_environment_features=True,
                            environment_factorial_observations=16, replication_per_cellline=4)
        states = validate_analysis_plan(plan, caps)
        self.assertFalse(states["motif_enrichment"]["available"])
        self.assertEqual(states["motif_enrichment"]["status"], "skipped")

    def test_selected_but_unavailable_anova(self):
        plan = AnalysisPlan()
        plan.environment.anova = True
        caps = Capabilities(n_cell_lines=4, n_environment_factors=1, n_models=2,
                            has_environment_features=True, environment_factorial_observations=0,
                            replication_per_cellline=1)
        states = validate_analysis_plan(plan, caps)
        self.assertTrue(states["environment_anova"]["selected"])
        self.assertFalse(states["environment_anova"]["available"])
        self.assertEqual(states["environment_anova"]["status"], "skipped")

    def test_cellline_needs_two_lines(self):
        plan = AnalysisPlan()
        caps = Capabilities(n_cell_lines=1, n_environment_factors=4, n_models=2,
                            has_environment_features=True, environment_factorial_observations=16,
                            replication_per_cellline=4)
        states = validate_analysis_plan(plan, caps)
        self.assertFalse(states["cellline_heterogeneity"]["available"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
