"""Evidence Tier 权威规则的最小测试集 (analysis/evidence/integration.py)。

覆盖任务要求的 9 条:
  1. CI 跨 0            -> 不满足 strong evidence (Inconclusive)
  2. CI 不跨 0          -> 可进入下一层判断
  3. concordance < 0.80 -> 不得标记为高一致性 (Tier1 被阻止)
  4. concordance >=0.80 -> 满足一致性门槛
  5. coverage 不足      -> Tier 降级/uncertain (supporting<2 且不 strong -> Inconclusive)
  6. |ΔR²| < 0.01       -> 不满足 absolute-effect threshold
  7. |ΔR²| >= 0.01      -> 满足 threshold
  8. permutation FDR 未通过 -> 不得误标为统计证据充分
  9. ANOVA 结果变化不得意外改变 edge-level Tier

并额外验证: 修改 Tier 阈值后, 最终 Tier 输出确实随之变化 (禁止伪参数)。
"""
from __future__ import annotations

import unittest
from dataclasses import replace

import numpy as np
import pandas as pd

from analysis.config import AnalysisConfig
from analysis.evidence.integration import (classify_evidence_tier, direction_concordance,
                                          environment_evidence_matrix)
from analysis.schemas import EvidenceTier


def _main_effects(ctcf_model_effects):
    """构造 environment_main_effects 风格的最小输入 (只测 ctcf 一个因子)。"""
    return pd.DataFrame({
        "split_type": ["single"] * len(ctcf_model_effects),
        "cell_line": ["hct116"] * len(ctcf_model_effects),
        "model": list(ctcf_model_effects.keys()),
        "environment": ["ctcf"] * len(ctcf_model_effects),
        "main_r2_delta": list(ctcf_model_effects.values()),
        "n_seeds": [1] * len(ctcf_model_effects),
    })


def _bootstrap_table(feature, lo, hi, n_bootstrap=2000, status="ok"):
    return pd.DataFrame([{
        "feature": feature, "estimate": (lo + hi) / 2, "ci_low": lo, "ci_high": hi,
        "excludes_zero": not (lo <= 0 <= hi), "n_bootstrap": n_bootstrap,
        "seed": 2024, "n_models": 7, "estimate_basis": "cross_model_mean_of_main_effect",
        "status": status, "reason": "",
    }])


def _perm_table(feature, fdr, n_contexts=1):
    """构造 permutation_results 风格输入。

    n_contexts>1 时复制出多个上下文（cell_line/model/split_type/observed_effect 各不相同），
    用于验证 R2 的 n_contexts / FWER 上界 / selected_context provenance。
    """
    rows = []
    for i in range(n_contexts):
        rows.append({
            "factor": feature, "p_value": fdr if i == 0 else min(1.0, fdr * (i + 2)),
            "FDR": fdr if i == 0 else min(1.0, fdr * (i + 2)),
            "test_type": "environment_main_effect",
            "split_type": "single", "cell_line": f"cell{i}", "model": f"m{i}",
            "observed_effect": -0.01 * (i + 1),
            "null_hypothesis": "H0", "alternative": "two-sided",
        })
    return pd.DataFrame(rows)


def _tier(effects, *, ci=None, perm=None, cfg=None, cellline=None):
    cfg = cfg or AnalysisConfig()
    m = environment_evidence_matrix(_main_effects(effects), cellline,
                                   cfg, bootstrap_ci=ci, permutation=perm)
    return m.iloc[0] if len(m) else None


# 7 个模型、方向一致率 1.0、效应量够大 -> 用于构造"本应 Tier1"的基线场景
_STRONG = {f"m{i}": -0.05 for i in range(7)}


class TestTierClassifyFunction(unittest.TestCase):
    def setUp(self):
        self.cfg = AnalysisConfig()

    def test_ci_crosses_zero_forces_inconclusive(self):
        """1) CI 跨 0 -> Inconclusive (即使覆盖度/一致率/强证据都满足)。"""
        tier = classify_evidence_tier(7, 7, 1.0, True, ci_crosses_zero=True, config=self.cfg)
        self.assertEqual(tier, EvidenceTier.INCONCLUSIVE)

    def test_ci_not_crossing_zero_allows_next_level(self):
        """2) CI 不跨 0 -> 可以进入下一层判断 (此处满足 -> Tier1)。"""
        tier = classify_evidence_tier(7, 7, 1.0, True, ci_crosses_zero=False, config=self.cfg)
        self.assertEqual(tier, EvidenceTier.TIER1)

    def test_missing_ci_does_not_block(self):
        """CI 缺失 (None) 时不阻塞判定, 但也不伪造 CI。"""
        tier = classify_evidence_tier(7, 7, 1.0, True, ci_crosses_zero=None, config=self.cfg)
        self.assertEqual(tier, EvidenceTier.TIER1)

    def test_low_concordance_blocks_tier1(self):
        """3) concordance < 0.80 -> 不得标记为 Tier1 (高一致性)。"""
        tier = classify_evidence_tier(7, 7, 0.70, True, ci_crosses_zero=False, config=self.cfg)
        self.assertEqual(tier, EvidenceTier.TIER2)

    def test_high_concordance_satisfies_gate(self):
        """4) concordance >= 0.80 -> 满足一致性门槛 (配合强证据 -> Tier1)。"""
        tier = classify_evidence_tier(7, 7, 0.80, True, ci_crosses_zero=False, config=self.cfg)
        self.assertEqual(tier, EvidenceTier.TIER1)

    def test_insufficient_coverage(self):
        """5) coverage 不足: supporting=1 且无强证据 -> Inconclusive (不是 Tier1/2)。"""
        tier = classify_evidence_tier(7, 1, 1.0, False, ci_crosses_zero=False, config=self.cfg)
        self.assertEqual(tier, EvidenceTier.INCONCLUSIVE)
        # supporting==1 且有强证据 -> Tier3 (模型特异), 仍不是 Tier1
        self.assertEqual(classify_evidence_tier(7, 1, 1.0, True, False, config=self.cfg),
                         EvidenceTier.TIER3)
        # applicable==0 -> 无证据 (不等于 no effect)
        self.assertEqual(classify_evidence_tier(0, 0, None, False, None, config=self.cfg),
                         EvidenceTier.NONE)

    def test_conflicting_direction_forces_inconclusive(self):
        tier = classify_evidence_tier(7, 7, 1.0, True, False, conflicting_direction=True,
                                      config=self.cfg)
        self.assertEqual(tier, EvidenceTier.INCONCLUSIVE)

    def test_ci_gate_is_parameterized(self):
        """禁止伪参数: 关闭 ci_crosses_zero_forces_inconclusive 后, CI 跨 0 不再一票否决。"""
        cfg = replace(self.cfg, evidence=replace(
            self.cfg.evidence, ci_crosses_zero_forces_inconclusive=False))
        tier = classify_evidence_tier(7, 7, 1.0, True, ci_crosses_zero=True, config=cfg)
        self.assertEqual(tier, EvidenceTier.TIER1)


class TestAbsoluteEffectGate(unittest.TestCase):
    """6) / 7) |ΔR²| 是否达到 min_absolute_delta_r2 门。"""

    def setUp(self):
        self.cfg = AnalysisConfig()

    def test_below_threshold_no_effect_gate(self):
        small = {f"m{i}": -0.005 for i in range(7)}          # |Δ| < 0.01
        row = _tier(small, ci=_bootstrap_table("ctcf", -0.006, -0.004), cfg=self.cfg)
        self.assertFalse(bool(row["effect_gate_pass"]))
        self.assertEqual(row["strong_evidence_basis"], "none")
        # 覆盖度与方向一致率都满足 -> 落到 Tier2 (不是 Inconclusive)
        self.assertEqual(row["evidence_tier"], EvidenceTier.TIER2.value)

    def test_above_threshold_passes_effect_gate(self):
        big = {f"m{i}": -0.05 for i in range(7)}             # |Δ| >= 0.01
        row = _tier(big, ci=_bootstrap_table("ctcf", -0.06, -0.04), cfg=self.cfg)
        self.assertTrue(bool(row["effect_gate_pass"]))
        self.assertEqual(row["strong_evidence_basis"], "absolute_effect")
        self.assertEqual(row["evidence_tier"], EvidenceTier.TIER1.value)

    def test_threshold_is_parameterized(self):
        """修改阈值后输出必须随之变化 (无伪参数)。"""
        small = {f"m{i}": -0.005 for i in range(7)}
        ci = _bootstrap_table("ctcf", -0.006, -0.004)
        row_default = _tier(small, ci=ci, cfg=self.cfg)
        self.assertFalse(bool(row_default["effect_gate_pass"]))
        cfg_loose = replace(self.cfg, evidence=replace(
            self.cfg.evidence, min_absolute_delta_r2=0.001))
        row_loose = _tier(small, ci=ci, cfg=cfg_loose)
        self.assertTrue(bool(row_loose["effect_gate_pass"]))
        self.assertEqual(row_loose["evidence_tier"], EvidenceTier.TIER1.value)
        self.assertEqual(row_loose["min_absolute_delta_r2"], 0.001)


class TestStatisticalGate(unittest.TestCase):
    """8) permutation FDR 未通过 -> 不得把统计证据当作充分。"""

    def setUp(self):
        self.cfg = AnalysisConfig()

    def test_permutation_fdr_fail_is_not_statistical_support(self):
        small = {f"m{i}": -0.005 for i in range(7)}
        row = _tier(small, ci=_bootstrap_table("ctcf", -0.006, -0.004),
                    perm=_perm_table("ctcf", 0.42), cfg=self.cfg)
        self.assertFalse(bool(row["statistical_gate_pass"]))
        self.assertEqual(row["strong_evidence_basis"], "none")
        self.assertEqual(row["evidence_tier"], EvidenceTier.TIER2.value)

    def test_permutation_fdr_alone_cannot_promote_to_tier1(self):
        """R3: RRBS 型场景（|ΔR²| < 0.01，仅统计门通过）**不得**因此进入 Tier 1。

        统计证据是支持性证据，不能单独提升到 Tier 1；该 factor 落在 Tier 2。
        """
        small = {f"m{i}": -0.0093 for i in range(7)}
        row = _tier(small, ci=_bootstrap_table("ctcf", -0.0105, -0.0085),
                    perm=_perm_table("ctcf", 0.0093), cfg=self.cfg)
        self.assertFalse(bool(row["effect_gate_pass"]))
        self.assertTrue(bool(row["statistical_gate_pass"]))
        self.assertEqual(row["strong_evidence_basis"], "permutation_fdr")
        self.assertEqual(row["tier_promotion_gate"], "statistical(disabled)")
        self.assertEqual(row["evidence_tier"], EvidenceTier.TIER2.value)

    def test_statistical_promotion_is_parameterized(self):
        """回归对照: 显式打开 statistical_gate_can_promote 时恢复旧 OR 行为（仅供敏感性分析）。"""
        cfg_or = replace(self.cfg, evidence=replace(
            self.cfg.evidence, statistical_gate_can_promote=True))
        small = {f"m{i}": -0.0093 for i in range(7)}
        row = _tier(small, ci=_bootstrap_table("ctcf", -0.0105, -0.0085),
                    perm=_perm_table("ctcf", 0.0093), cfg=cfg_or)
        self.assertEqual(row["evidence_tier"], EvidenceTier.TIER1.value)
        self.assertEqual(row["tier_promotion_gate"], "statistical")   # 显式启用时为统计门提升

    def test_permutation_gate_threshold_is_parameterized(self):
        small = {f"m{i}": -0.005 for i in range(7)}
        ci = _bootstrap_table("ctcf", -0.006, -0.004)
        perm = _perm_table("ctcf", 0.03)
        row = _tier(small, ci=ci, perm=perm, cfg=self.cfg)      # 0.03 < 0.05 -> pass
        self.assertTrue(bool(row["statistical_gate_pass"]))
        cfg_strict = replace(self.cfg, statistical=replace(self.cfg.statistical, fdr_weak=0.01))
        row_strict = _tier(small, ci=ci, perm=perm, cfg=cfg_strict)   # 0.03 > 0.01 -> fail
        self.assertFalse(bool(row_strict["statistical_gate_pass"]))


class TestAnovaIndependence(unittest.TestCase):
    """9) ANOVA 结果变化不得改变 edge-level Tier。

    `environment_evidence_matrix` 的输入签名里没有任何 ANOVA 参数; 这里通过"传入带 ANOVA 列的
    main_effects 且共变"来验证 Tier 只由 effect / CI / permutation / concordance / coverage 决定。
    """

    def test_anova_columns_do_not_affect_tier(self):
        cfg = AnalysisConfig()
        main = _main_effects(_STRONG)
        main["anova_F"] = 999.0
        main["anova_p"] = 1e-9
        ci = _bootstrap_table("ctcf", -0.06, -0.04)
        base = environment_evidence_matrix(_main_effects(_STRONG), None, cfg,
                                           bootstrap_ci=ci, permutation=None)
        with_anova = environment_evidence_matrix(main, None, cfg,
                                                bootstrap_ci=ci, permutation=None)
        self.assertEqual(base.iloc[0]["evidence_tier"], with_anova.iloc[0]["evidence_tier"])
        # 反向: 把 ANOVA 改成极不显著, Tier 也不动
        main2 = _main_effects(_STRONG)
        main2["anova_F"] = 0.0
        main2["anova_p"] = 1.0
        other = environment_evidence_matrix(main2, None, cfg, bootstrap_ci=ci, permutation=None)
        self.assertEqual(base.iloc[0]["evidence_tier"], other.iloc[0]["evidence_tier"])

    def test_signature_has_no_anova_input(self):
        import inspect
        params = set(inspect.signature(environment_evidence_matrix).parameters)
        self.assertNotIn("anova", params)
        self.assertNotIn("anova_results", params)


class TestProvenanceColumns(unittest.TestCase):
    def test_gate_provenance_is_recorded(self):
        cfg = AnalysisConfig()
        row = _tier(_STRONG, ci=_bootstrap_table("ctcf", -0.06, -0.04),
                    perm=_perm_table("ctcf", 0.009), cfg=cfg)
        self.assertEqual(row["strong_evidence_basis"], "both")
        self.assertEqual(row["permutation_selection"], "min FDR over rows of this factor")
        self.assertAlmostEqual(float(row["min_absolute_delta_r2"]), 0.01)


if __name__ == "__main__":
    unittest.main()


class TestPermutationEvidenceProvenance(unittest.TestCase):
    """R2: min(FDR) 只能作为 existence-oriented 证据，且 provenance 必须完整可审计。"""

    def setUp(self):
        self.cfg = AnalysisConfig()

    def test_selection_is_labelled_as_existence_oriented(self):
        row = _tier(_STRONG, ci=_bootstrap_table("ctcf", -0.06, -0.04),
                    perm=_perm_table("ctcf", 0.009, n_contexts=5), cfg=self.cfg)
        self.assertEqual(row["selection_basis"], "minimum_edge_level_FDR_across_tested_contexts")
        self.assertEqual(row["statistical_evidence_role"], "existence_oriented")
        self.assertIn("post-selection extremum", str(row["extremum_note"]))
        self.assertIn("NOT a factor-level FDR", str(row["extremum_note"]))

    def test_context_count_and_fwer_bound_recorded(self):
        row = _tier(_STRONG, ci=_bootstrap_table("ctcf", -0.06, -0.04),
                    perm=_perm_table("ctcf", 0.01, n_contexts=7), cfg=self.cfg)
        self.assertEqual(int(row["n_contexts"]), 7)
        self.assertEqual(int(row["n_contexts_after_dedup"]), 7)
        self.assertAlmostEqual(float(row["fwer_upper_bound"]), min(1.0, 0.01 * 7), places=12)
        self.assertEqual(row["selected_context"], "single/cell0/m0")

    def test_duplicate_contexts_are_deduplicated(self):
        """all ≡ single 型重复上下文必须只计一次（本批真实情形）。"""
        perm = _perm_table("ctcf", 0.01, n_contexts=3)
        dup = perm.copy()
        dup["split_type"] = "all"                      # 相同 (cell,model,effect,p) 再来一遍
        perm2 = pd.concat([perm, dup], ignore_index=True)
        row = _tier(_STRONG, ci=_bootstrap_table("ctcf", -0.06, -0.04), perm=perm2, cfg=self.cfg)
        self.assertEqual(int(row["n_contexts"]), 6)
        self.assertEqual(int(row["n_contexts_after_dedup"]), 3)
        self.assertAlmostEqual(float(row["fwer_upper_bound"]), min(1.0, 0.01 * 3), places=12)

    def test_tier_not_changed_by_provenance_only(self):
        """R2 只加 provenance，不改变 Tier 布尔结果。"""
        row = _tier(_STRONG, ci=_bootstrap_table("ctcf", -0.06, -0.04),
                    perm=_perm_table("ctcf", 0.009, n_contexts=4), cfg=self.cfg)
        self.assertEqual(row["evidence_tier"], EvidenceTier.TIER1.value)
        self.assertTrue(bool(row["statistical_gate_pass"]))


class TestEffectGateAggregation(unittest.TestCase):
    """R4: effect 门的统计单位 = 模型配置（等权均值），且不得隐藏模型间异质性。"""

    def setUp(self):
        self.cfg = AnalysisConfig()

    def _mixed_models(self):
        # 1 个极端模型 + 6 个微小模型：旧 "any_model" 口径会通过，等权均值口径不通过
        eff = {f"m{i}": 0.001 for i in range(6)}
        eff["linear"] = -0.05
        return eff

    def test_model_mean_mode_blocks_single_extreme_model(self):
        row = _tier(self._mixed_models(), ci=_bootstrap_table("ctcf", -0.02, 0.02),
                    cfg=self.cfg)
        self.assertEqual(row["effect_gate_mode"], "model_mean")
        self.assertAlmostEqual(float(row["effect_gate_value"]),
                               abs((6 * 0.001 - 0.05) / 7), places=6)
        self.assertFalse(bool(row["effect_gate_pass"]))
        self.assertEqual(row["tier_promotion_gate"], "none")

    def test_any_model_mode_is_sensitivity_only(self):
        cfg_any = replace(self.cfg, evidence=replace(self.cfg.evidence,
                                                     effect_gate_mode="any_model"))
        row = _tier(self._mixed_models(), ci=_bootstrap_table("ctcf", -0.02, 0.02), cfg=cfg_any)
        self.assertEqual(row["effect_gate_mode"], "any_model")
        self.assertAlmostEqual(float(row["effect_gate_value"]), 0.05, places=6)
        self.assertTrue(bool(row["effect_gate_pass"]))

    def test_heterogeneity_is_preserved(self):
        row = _tier(self._mixed_models(), ci=_bootstrap_table("ctcf", -0.02, 0.02),
                    cfg=self.cfg)
        self.assertEqual(int(row["n_models"]), 7)
        self.assertAlmostEqual(float(row["median_effect"]), 0.001, places=6)
        self.assertTrue(bool(row["model_direction_conflict"]))
        self.assertIn("linear=-0.0500", str(row["model_effects"]))


class TestConcordanceDenominator(unittest.TestCase):
    """R5: 分母 = 全部有效模型，不因中性/零效应缩小（避免虚高）。"""

    def test_zeros_do_not_inflate_concordance(self):
        # 1 正 + 6 精确零：旧口径 = 1/1 = 100%，新口径 = 1/7
        vals = [0.05] + [0.0] * 6
        self.assertAlmostEqual(direction_concordance(vals), 1 / 7, places=6)
        self.assertAlmostEqual(direction_concordance(vals, denominator=1), 1.0, places=6)  # 旧口径

    def test_denominator_recorded_in_matrix(self):
        cfg = AnalysisConfig()
        m = _main_effects({f"m{i}": -0.05 for i in range(7)})
        m.loc[m.model == "m0", "main_r2_delta"] = 0.0        # 一个精确零
        row = environment_evidence_matrix(m, None, cfg).iloc[0]
        self.assertEqual(int(row["concordance_denominator"]), 7)      # 分母不缩小
        self.assertEqual(int(row["n_neutral_models"]), 1)
        self.assertAlmostEqual(float(row["direction_concordance"]), 6 / 7, places=6)

    def test_all_zero_returns_none(self):
        self.assertIsNone(direction_concordance([0.0] * 7))


class TestBootstrapNaming(unittest.TestCase):
    """R6: 自助区间的重采样单元是模型配置（n=7），命名与 provenance 必须明确。"""

    def test_interval_type_and_unit_recorded(self):
        from analysis.stats.tasks import bootstrap_main_effects
        main = pd.DataFrame({
            "split_type": ["single"] * 7, "cell_line": ["hct116"] * 7,
            "model": [f"m{i}" for i in range(7)], "environment": ["ctcf"] * 7,
            "main_r2_delta": [-0.01, -0.012, -0.008, -0.011, -0.009, -0.013, -0.010],
        })
        out = bootstrap_main_effects(main, config=AnalysisConfig()).iloc[0]
        self.assertEqual(out["interval_type"], "model_level_bootstrap")
        self.assertEqual(int(out["n_models"]), 7)
        self.assertEqual(out["estimate_basis"], "cross_model_mean_of_main_effect")
        self.assertEqual(str(out["interval_type"]), "model_level_bootstrap")
