"""analysis.tests.test_phase5 — cell-line 一致性 + evidence matrix 测试。"""
from __future__ import annotations

import unittest

import pandas as pd

from analysis.cellline.consistency import summarize_environment_by_cellline
from analysis.config import AnalysisConfig
from analysis.evidence.integration import environment_evidence_matrix
from analysis.schemas import EvidenceTier


def _main_effects() -> pd.DataFrame:
    rows = [
        # split, cell, model, env, main delta
        ("single", "hct116", "m1", "ctcf", 0.030),
        ("single", "hela", "m1", "ctcf", 0.020),
        ("single", "hct116", "m2", "ctcf", 0.010),
        ("single", "hela", "m2", "ctcf", -0.020),   # cell 方向冲突
        ("single", "hct116", "m1", "dnase", 0.050),
        ("single", "hela", "m1", "dnase", 0.040),
        ("single", "hct116", "m2", "dnase", 0.030),
        ("single", "hela", "m2", "dnase", 0.020),
        # 数值不稳定上下文 (|Δ| >> 阈值) -> 应被证据矩阵隔离
        ("single", "hct116", "m1", "ctcf", 1.0e13),
        ("single", "hct116", "m2", "ctcf", -1.0e13),
    ]
    return pd.DataFrame(rows, columns=["split_type", "cell_line", "model",
                                       "environment", "main_r2_delta"])


class TestEvidenceMatrixPhase5(unittest.TestCase):
    def test_unstable_rows_excluded(self):
        cfg = AnalysisConfig()
        matrix = environment_evidence_matrix(_main_effects(), config=cfg)
        row = matrix[matrix["feature"] == "ctcf"].iloc[0]
        self.assertGreaterEqual(row["unstable_rows_excluded"], 2)
        # 不稳定值不进 overall effect
        self.assertLess(abs(float(row["overall_effect"])), 1.0)

    def test_context_conflict_downgrades_to_inconclusive(self):
        cfg = AnalysisConfig()
        summary = pd.DataFrame([
            {"split_type": "single", "model": "m1", "factor": "ctcf",
             "context_label": "Context-conflicting"},
            {"split_type": "single", "model": "m2", "factor": "ctcf",
             "context_label": "Context-conflicting"},
        ])
        matrix = environment_evidence_matrix(_main_effects(), cellline_summary=summary,
                                             config=cfg)
        row = matrix[matrix["feature"] == "ctcf"].iloc[0]
        self.assertEqual(row["evidence_tier"], EvidenceTier.INCONCLUSIVE.value)

    def test_cellline_summary_labels(self):
        out = summarize_environment_by_cellline(_main_effects())
        ctcf = out[(out["model"] == "m1") & (out["factor"] == "ctcf")]
        self.assertEqual(ctcf.iloc[0]["context_label"], "Context-consistent")
        self.assertEqual(len(out), 4)   # 2 模型 x 2 env


if __name__ == "__main__":
    unittest.main(verbosity=2)
