"""统计工具接线测试 (实现 → 接线 → 输出 → 报告 → 前端状态)。

覆盖任务书 §18 要求的 8 组 + 接线/状态:
  test_bh_fdr / test_bootstrap_ci / test_bootstrap_difference_ci / test_permutation_test /
  test_anova / test_paired_delta_r2 / test_metric_consistency / test_evidence_ci_integration
另加: per-sample paired ΔR² (同一 test 样本), 空结果与缺 artifact 的降级, 状态/artifact 契约,
      cell-line 四种 context 标签可达性。

执行顺序: unit test -> task runner test -> pipeline integration test -> real result smoke test。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analyse.config import AnalysisConfig
from analyse.stats.bootstrap import (bootstrap_ci, bootstrap_difference_ci,
                                     bootstrap_paired_metric_ci,
                                     bootstrap_paired_metrics_ci_fast, metric_r2)
from analyse.stats.hypothesis_tests import (anova_interface, factorial_anova,
                                            permutation_test_for_effect,
                                            permutation_test_for_effect_fast)
from analyse.stats.multiple_testing import bh_fdr

ROOT = Path(__file__).resolve().parent.parent.parent
BATCH = ROOT / "results" / "batch_20260909_full"


# ---------------------------------------------------------------------------
# unit tests
# ---------------------------------------------------------------------------
class TestBhFdr(unittest.TestCase):
    def test_matches_manual_bh(self):
        p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205]
        q = bh_fdr(p)
        expect = [0.008, 0.032, 0.0672, 0.0672, 0.0672, 0.08, 0.074 * 8 / 7, 0.205]
        for got, exp in zip(q, expect):
            self.assertAlmostEqual(got, exp, places=6)

    def test_monotone_and_nan_passthrough(self):
        q = bh_fdr([0.02, None, 0.01, float("nan")])
        self.assertTrue(q[1] is None or (isinstance(q[1], float) and np.isnan(q[1])))
        self.assertTrue(np.isnan(q[3]))
        self.assertLessEqual(q[0], 1.0)

    def test_single_p_value(self):
        self.assertAlmostEqual(bh_fdr([0.03])[0], 0.03, places=12)


class TestBootstrapCi(unittest.TestCase):
    def test_ci_covers_mean_and_flags_zero(self):
        rng = np.random.default_rng(0)
        data = rng.normal(0.5, 1.0, 200)
        res = bootstrap_ci(data, estimator=lambda x: float(np.mean(x)),
                           n_iterations=500, seed=1)
        self.assertTrue(res.available)
        self.assertLess(res.ci_low, res.estimate)
        self.assertGreater(res.ci_high, res.estimate)
        self.assertTrue(res.excludes_zero)
        self.assertEqual(res.n_iterations, 500)
        self.assertEqual(res.seed, 1)

    def test_unavailable_is_not_zero(self):
        res = bootstrap_ci([1.0, 2.0], estimator=lambda x: float(np.mean(x)))
        self.assertFalse(res.available)
        self.assertIsNone(res.estimate)
        self.assertIsNone(res.ci_low)
        self.assertFalse(res.excludes_zero)


class TestBootstrapDifferenceCi(unittest.TestCase):
    def test_paired_difference_ci(self):
        rng = np.random.default_rng(2)
        a = rng.normal(0, 1, 100)
        b = a + 0.4 + rng.normal(0, 0.1, 100)
        res = bootstrap_difference_ci(a, b, metric_fn=lambda x: float(np.mean(x)),
                                      n_iterations=400, seed=3)
        self.assertTrue(res.available)
        self.assertAlmostEqual(res.estimate, float(np.mean(b) - np.mean(a)), places=9)
        self.assertTrue(res.excludes_zero)

    def test_unpaired_size_mismatch_is_unavailable(self):
        res = bootstrap_difference_ci([1, 2, 3, 4], [1, 2, 3],
                                      metric_fn=lambda x: float(np.mean(x)))
        self.assertFalse(res.available)


class TestPairedDeltaR2(unittest.TestCase):
    """paired per-sample ΔR²: 同一 test 样本, 与逐迭代实现一致。"""

    def setUp(self):
        rng = np.random.default_rng(5)
        self.y = rng.normal(0, 1, 150)
        self.a = np.column_stack([self.y, self.y + rng.normal(0, 0.4, 150)])
        self.b = np.column_stack([self.y, self.y + rng.normal(0, 0.2, 150)])

    def test_estimate_equals_metric_difference(self):
        res = bootstrap_paired_metric_ci(self.a, self.b, metric_r2, 300, 7)
        self.assertAlmostEqual(res.estimate, metric_r2(self.b) - metric_r2(self.a), places=9)

    def test_fast_variant_matches_slow_variant(self):
        slow = bootstrap_paired_metric_ci(self.a, self.b, metric_r2, 500, 11)
        fast = bootstrap_paired_metrics_ci_fast(self.a, self.b, ("R2",), 500, 11)["R2"]
        self.assertAlmostEqual(slow.estimate, fast.estimate, places=9)
        self.assertAlmostEqual(slow.ci_low, fast.ci_low, places=6)
        self.assertAlmostEqual(slow.ci_high, fast.ci_high, places=6)

    def test_all_metrics_have_ci(self):
        res = bootstrap_paired_metrics_ci_fast(self.a, self.b, ("R2", "MAE", "RMSE"), 200, 3)
        for metric in ("R2", "MAE", "RMSE"):
            self.assertTrue(res[metric].available, metric)
            self.assertIsNotNone(res[metric].ci_low)

    def test_cohort_mismatch_is_unavailable(self):
        res = bootstrap_paired_metrics_ci_fast(self.a, self.b[:-5], ("R2",), 100, 3)["R2"]
        self.assertFalse(res.available)


class TestPermutationTest(unittest.TestCase):
    def test_detects_real_effect(self):
        rng = np.random.default_rng(4)
        vals = rng.normal(0.5, 1.0, 80)
        res = permutation_test_for_effect(vals, n_permutations=500, seed=9)
        self.assertLess(res.p_value, 0.05)
        self.assertEqual(res.n_permutations, 500)
        self.assertEqual(res.seed, 9)

    def test_null_is_not_significant(self):
        rng = np.random.default_rng(6)
        vals = rng.normal(0.0, 1.0, 80)
        res = permutation_test_for_effect(vals, n_permutations=500, seed=9)
        self.assertGreater(res.p_value, 0.05)

    def test_fast_variant_agrees(self):
        rng = np.random.default_rng(8)
        vals = rng.normal(0.3, 1.0, 60)
        slow = permutation_test_for_effect(vals, n_permutations=1000, seed=2)
        fast = permutation_test_for_effect_fast(vals, n_permutations=1000, seed=2)
        self.assertAlmostEqual(slow.p_value, fast.p_value, places=9)

    def test_zero_hypothesis_is_recorded(self):
        res = permutation_test_for_effect([0.1, 0.2, 0.3], null_effect=0.0)
        self.assertEqual(res.observed, float(np.mean([0.1, 0.2, 0.3])))
        self.assertAlmostEqual(res.observed - 0.0, 0.2, places=9)


class TestAnova(unittest.TestCase):
    def _frame(self, a_effect=0.05, interaction=0.03, n=8):
        rng = np.random.default_rng(1)
        rows = []
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    for d in (0, 1):
                        for rep in range(n):
                            y = 0.1 + a_effect * a + 0.01 * b + interaction * a * b \
                                + rng.normal(0, 0.01)
                            rows.append({"ctcf": a, "dnase": b, "h3k4me3": c, "rrbs": d,
                                         "model": f"m{rep % 3}", "cell_line": f"c{rep % 2}",
                                         "split_type": "single", "R2": y})
        return pd.DataFrame(rows)

    def test_real_effects_detected_and_nulls_not(self):
        terms = {t.factor: t for t in factorial_anova(
            self._frame(), "R2", ["ctcf", "dnase", "h3k4me3", "rrbs"],
            ["model", "cell_line", "split_type"], n_iterations=0)}
        self.assertLess(terms["ctcf"].p_value, 0.01)
        self.assertLess(terms["ctcf*dnase"].p_value, 0.01)
        self.assertGreater(terms["h3k4me3"].p_value, 0.05)
        self.assertGreater(terms["rrbs"].p_value, 0.05)

    def test_outputs_required_fields(self):
        terms = {t.factor: t for t in factorial_anova(
            self._frame(), "R2", ["ctcf", "dnase"], ["model"], n_iterations=50)}
        t = terms["ctcf"]
        for field in ("effect", "F_statistic", "p_value", "effect_size", "ci_low", "ci_high"):
            self.assertIsNotNone(getattr(t, field), field)
        self.assertIsNotNone(t.df_num)
        self.assertIsNotNone(t.df_den)

    def test_insufficient_data_is_unavailable(self):
        terms = factorial_anova(self._frame().head(10), "R2", ["ctcf", "dnase"])
        self.assertEqual(terms[0].status, "unavailable")
        self.assertIn("insufficient_data", terms[0].reason)
        self.assertIsNone(terms[0].p_value)

    def test_interface_wrapper_reports_unavailable(self):
        out = anova_interface(pd.DataFrame({"ctcf": [0, 1]}), ["ctcf"], "R2")
        self.assertFalse(out["available"])
        self.assertIsNone(out["p_value"])

    def test_interface_wrapper_reports_terms(self):
        out = anova_interface(self._frame(), ["ctcf", "dnase", "h3k4me3", "rrbs"], "R2",
                              design_info={"blocks": ["model"]},
                              config={"min_observations": 32, "ci_iterations": 0})
        self.assertTrue(out["available"])
        self.assertTrue(len(out["terms"]) >= 4)


# ---------------------------------------------------------------------------
# task runner tests (合成 batch: 含真实 predictions 文件)
# ---------------------------------------------------------------------------
def _write_fake_batch(root: Path, n: int = 60) -> pd.DataFrame:
    """构造 4 组合 × 1 模型的最小 batch (含 per-sample 预测), 用于 runner 测试。"""
    rng = np.random.default_rng(0)
    y = rng.normal(0, 1, n)
    rows = []
    quality = {"sequence": 0.5, "sequence_ctcf": 0.25, "sequence_dnase": 0.45,
               "sequence_ctcf_dnase": 0.2}
    for env, sd in quality.items():
        run = f"single_m_single_c1_{env}"
        d = root / run
        d.mkdir(parents=True, exist_ok=True)
        pred = y + rng.normal(0, sd, n)
        pd.DataFrame({"y_true": y, "y_pred": pred}).to_csv(d / "m_predictions.csv", index=False)
        r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
        rows.append({"model": "m", "split_type": "single", "cell_line": "c1",
                     "environment": env, "random_seed": 42, "R2": r2,
                     "RMSE": float(np.sqrt(np.mean((y - pred) ** 2))),
                     "MAE": float(np.mean(np.abs(y - pred))),
                     "Pearson": 0.5, "Spearman": 0.5, "run_name": run})
    return pd.DataFrame(rows)


class TestTaskRunners(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.table = _write_fake_batch(self.root)
        self.cfg = AnalysisConfig(bootstrap_iterations=200, permutation_iterations=200)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bootstrap_edges_from_predictions(self):
        from analyse.stats.tasks import bootstrap_environment_edges
        out = bootstrap_environment_edges(self.root, self.table, config=self.cfg)
        self.assertFalse(out.empty)
        self.assertIn("ci_low", out.columns)
        r2 = out[(out["metric"] == "R2") & (out["parent_combination"] == "sequence")]
        self.assertEqual(len(r2), 2)                     # ctcf / dnase
        self.assertTrue((r2["status"] == "ok").all())
        self.assertTrue((r2["n_bootstrap"] == 200).all())
        # 更好的 expanded 模型 (更小 sd) -> 正向 ΔR²
        self.assertGreater(float(r2["estimate"].max()), 0)

    def test_permutation_edges_have_null_hypothesis(self):
        from analyse.stats.tasks import permutation_environment_edges
        out = permutation_environment_edges(self.root, self.table, config=self.cfg)
        ok = out[out["status"] == "ok"]
        self.assertFalse(ok.empty)
        self.assertTrue(ok["null_hypothesis"].str.contains("= 0").all())
        self.assertTrue(ok["p_value"].between(0, 1).all())

    def test_missing_predictions_degrade_not_fake(self):
        from analyse.stats.tasks import bootstrap_environment_edges
        table = self.table.copy()
        table.loc[0, "run_name"] = "does_not_exist"
        out = bootstrap_environment_edges(self.root, table, config=self.cfg)
        bad = out[out["status"] == "unavailable"]
        self.assertFalse(bad.empty)
        self.assertTrue(bad["reason"].str.contains("prediction_artifact_missing").any())
        self.assertTrue(bad["ci_low"].isna().all())

    def test_fdr_by_family(self):
        from analyse.stats.tasks import apply_fdr
        df = pd.DataFrame({
            "family_key": ["f1", "f1", "f1", "f2"],
            "p_value": [0.01, 0.02, 0.03, 0.5],
        })
        out = apply_fdr(df, config=self.cfg)
        self.assertTrue(np.isfinite(out.loc[out["family_key"] == "f1", "FDR"]).all())
        # 单一成员 family -> not_applicable, 不伪造 FDR
        self.assertTrue(out.loc[out["family_key"] == "f2", "FDR"].isna().all())
        self.assertIn("not_applicable", out.loc[out["family_key"] == "f2", "fdr_status"].iloc[0])

    def test_anova_runner_per_group(self):
        from analyse.stats.tasks import run_anova_tasks
        out = run_anova_tasks(self.table, config=self.cfg)
        self.assertFalse(out.empty)
        self.assertIn("factor", out.columns)
        self.assertTrue(out["status"].isin(["ok", "unavailable"]).all())


# ---------------------------------------------------------------------------
# metric consistency + evidence CI integration
# ---------------------------------------------------------------------------
class TestMetricConsistency(unittest.TestCase):
    def test_flags_same_direction(self):
        from analyse.data.validation import metric_consistency_flags
        self.assertEqual(metric_consistency_flags(0.02, 0.01),
                         ["metric_inconsistency_same_increase"])
        self.assertEqual(metric_consistency_flags(-0.02, -0.01),
                         ["metric_inconsistency_same_decrease"])
        self.assertEqual(metric_consistency_flags(0.02, -0.01), [])


class TestEvidenceCiIntegration(unittest.TestCase):
    def _main(self):
        return pd.DataFrame([
            {"split_type": "single", "cell_line": "c1", "model": "m1",
             "environment": "ctcf", "main_r2_delta": 0.03},
            {"split_type": "single", "cell_line": "c1", "model": "m2",
             "environment": "ctcf", "main_r2_delta": 0.02},
            {"split_type": "single", "cell_line": "c1", "model": "m3",
             "environment": "ctcf", "main_r2_delta": 0.025},
        ])

    def test_ci_crossing_zero_forces_inconclusive(self):
        from analyse.evidence.integration import environment_evidence_matrix
        ci = pd.DataFrame([{"feature": "ctcf", "estimate": 0.025, "ci_low": -0.01,
                            "ci_high": 0.05, "excludes_zero": False, "n_bootstrap": 2000,
                            "status": "ok"}])
        matrix = environment_evidence_matrix(self._main(), config=AnalysisConfig(),
                                             bootstrap_ci=ci)
        self.assertEqual(matrix.iloc[0]["evidence_tier"], "Inconclusive")
        self.assertEqual(matrix.iloc[0]["ci_excludes_zero"], False)

    def test_ci_excluding_zero_allows_tier(self):
        from analyse.evidence.integration import environment_evidence_matrix
        cfg = AnalysisConfig()
        main = self._main()
        main.loc[len(main)] = {"split_type": "single", "cell_line": "c1", "model": "m4",
                               "environment": "ctcf", "main_r2_delta": 0.04}
        ci = pd.DataFrame([{"feature": "ctcf", "estimate": 0.03, "ci_low": 0.01,
                            "ci_high": 0.05, "excludes_zero": True, "n_bootstrap": 2000,
                            "status": "ok"}])
        matrix = environment_evidence_matrix(main, config=cfg, bootstrap_ci=ci)
        self.assertNotEqual(matrix.iloc[0]["evidence_tier"], "Inconclusive")

    def test_low_iteration_ci_does_not_decide_tier(self):
        from analyse.evidence.integration import environment_evidence_matrix
        ci = pd.DataFrame([{"feature": "ctcf", "estimate": 0.03, "ci_low": -0.01,
                            "ci_high": 0.05, "excludes_zero": False, "n_bootstrap": 10,
                            "status": "ok"}])
        matrix = environment_evidence_matrix(self._main(), config=AnalysisConfig(),
                                             bootstrap_ci=ci)
        self.assertIsNone(matrix.iloc[0]["ci_excludes_zero"])   # 迭代数不足 -> 不用
        self.assertNotEqual(matrix.iloc[0]["evidence_tier"], "Inconclusive")

    def test_permutation_fdr_feeds_statistical_evidence(self):
        from analyse.evidence.integration import environment_evidence_matrix
        perm = pd.DataFrame([{"factor": "ctcf", "p_value": 0.001, "FDR": 0.002}])
        matrix = environment_evidence_matrix(self._main(), config=AnalysisConfig(),
                                             permutation=perm)
        self.assertEqual(matrix.iloc[0]["permutation_status"], "ok")
        self.assertAlmostEqual(matrix.iloc[0]["permutation_fdr"], 0.002)


class TestCelllineLabelsReachable(unittest.TestCase):
    def test_all_four_labels(self):
        from analyse.cellline.consistency import classify_cellline_consistency_detail
        consistent = classify_cellline_consistency_detail(
            {"c1": 0.03, "c2": 0.031, "c3": 0.029, "c4": 0.030})["label"]
        dependent_magnitude = classify_cellline_consistency_detail(
            {"c1": 0.30, "c2": 0.031, "c3": 0.029, "c4": 0.030})["label"]
        conflicting = classify_cellline_consistency_detail(
            {"c1": 0.03, "c2": -0.02, "c3": 0.01, "c4": 0.02})["label"]
        uncertain = classify_cellline_consistency_detail({"c1": None, "c2": 0.01})["label"]
        self.assertEqual(consistent, "Context-consistent")
        self.assertEqual(dependent_magnitude, "Context-dependent")
        self.assertEqual(conflicting, "Context-conflicting")
        self.assertEqual(uncertain, "Uncertain")

    def test_ci_overlap_relaxes_conflict(self):
        from analyse.cellline.consistency import classify_cellline_consistency_detail
        d = classify_cellline_consistency_detail(
            {"c1": 0.030, "c2": 0.028, "c3": 0.031, "c4": -0.02},
            {"c1": (-0.01, 0.06), "c2": (-0.01, 0.06), "c3": (-0.01, 0.06),
             "c4": (-0.05, 0.02)})   # 反向 cell line 的 CI 与主体重叠
        self.assertEqual(d["label"], "Context-dependent")
        self.assertTrue(d["ci_overlap_relaxed"])
        # 无 CI 时同一组数据 -> conflicting (证明 CI 真的参与判定)
        d2 = classify_cellline_consistency_detail(
            {"c1": 0.030, "c2": 0.028, "c3": 0.031, "c4": -0.02})
        self.assertEqual(d2["label"], "Context-conflicting")


# ---------------------------------------------------------------------------
# real-batch smoke test (缺数据自动 skip, 不伪造)
# ---------------------------------------------------------------------------
class TestRealBatchArtifacts(unittest.TestCase):
    def test_statistics_tables_present_and_consistent(self):
        tables = BATCH / "analyse_out" / "tables"
        if not (tables / "bootstrap_results.csv").exists():
            self.skipTest("real batch statistics artifacts not generated yet")
        bs = pd.read_csv(tables / "bootstrap_results.csv")
        self.assertIn("ci_low", bs.columns)
        ok = bs[(bs["metric"] == "R2") & (bs["status"] == "ok")]
        self.assertGreater(len(ok), 0)
        self.assertTrue(ok["n_bootstrap"].min() >= 200)
        self.assertTrue(((ok["ci_low"] <= ok["estimate"]) & (ok["estimate"] <= ok["ci_high"])).all())

        perm = pd.read_csv(tables / "permutation_results.csv")
        self.assertTrue(perm["p_value"].dropna().between(0, 1).all())
        self.assertIn("fdr_family", perm.columns)

        status = json.loads((BATCH / "analyse_out" / "analysis_status.json").read_text())
        by_id = {t["task_id"]: t for t in status["tasks"]}
        for task in ("bootstrap", "hypothesis_testing"):
            self.assertIn(task, by_id)
            self.assertEqual(by_id[task]["status"], "completed")
            self.assertTrue(by_id[task]["artifact"].startswith("tables/"))


if __name__ == "__main__":
    unittest.main()
