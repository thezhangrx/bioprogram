"""analysis.tests.test_phase6 — pipeline 端到端报告/图形产物 (Phase 6)。

通过小型合成批次跑 run_analysis (只读语义), 验证:
  - reports 00-08 md 齐全 (本切片含 01/08 批次级报告);
  - tables/anomaly_report.csv 机器可读;
  - figures 由 render_all 生成且 execution_log 记录;
  - 未选中任务不执行 (skipped), 不伪造 unavailable 之外的状态。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analysis.config import AnalysisConfig
from analysis.pipeline import run_analysis
from analysis.plans import AnalysisPlan

ENVS = ["sequence", "sequence_ctcf", "sequence_ctcf_dnase",
        "sequence_ctcf_dnase_h3k4me3"]
ENV_DELTA_R2 = {  # 相对 sequence: 两个 cell line 同向 -> Context-consistent
    "sequence_ctcf": 0.03,
    "sequence_ctcf_dnase": 0.05,
    "sequence_ctcf_dnase_h3k4me3": -0.02,
}
MODELS = ["LinearRegression", "XGBoost"]
CELLS = ["hct116", "hela"]
BASELINE_R2 = {"LinearRegression": 0.55, "XGBoost": 0.60}
BASELINE_RMSE = {"LinearRegression": 0.40, "XGBoost": 0.35}


def _make_batch(root: Path) -> Path:
    batch = root / "batch_mini"
    metrics = batch / "summary" / "metrics_tables"
    metrics.mkdir(parents=True)
    rows = []
    for model in MODELS:
        for cell in CELLS:
            base_r2 = BASELINE_R2[model]
            base_rmse = BASELINE_RMSE[model]
            for i, env in enumerate(ENVS):
                delta = ENV_DELTA_R2.get(env, 0.0)
                # 改善方向: ΔR² 增 => RMSE 减 (同 cohort 配对, seed 固定)
                rows.append({
                    "model": model, "split_type": "single", "cell_line": cell,
                    "environment": env, "random_seed": "42",
                    "n_train": 10, "n_valid": 5, "n_test": 5,
                    "R2": round(base_r2 + delta, 4),
                    "RMSE": round(base_rmse - delta * 2.0, 4),
                    "MAE": 0.3, "MSE": 0.2, "Pearson": 0.8, "Spearman": 0.8,
                })
    pd.DataFrame(rows).to_csv(metrics / "all_experiments.csv", index=False)
    return batch


class TestPhase6PipelineReports(unittest.TestCase):
    def test_pipeline_reports_and_figures(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = _make_batch(Path(tmp))
            plan = AnalysisPlan()
            plan.sequence.enabled = False        # 本切片无 importance 文件
            plan.sequence.position_attribution = False
            plan.statistics.bootstrap = False     # 未实现 runner, 不选中
            plan.statistics.hypothesis_testing = False
            plan.statistics.fdr_correction = False
            out = Path(tmp) / "out"
            status = run_analysis(batch_dir=batch, output=out,
                                  plan=plan, config=AnalysisConfig())

            tasks = {t["task_id"]: t["status"] for t in status["tasks"]}
            for done in ("qc", "prediction", "environment_conditional_effect",
                         "environment_main_effect", "cellline_heterogeneity",
                         "evidence_integration", "hypothesis_generation"):
                self.assertEqual(tasks[done], "completed", done)
            self.assertNotEqual(tasks["sequence_attribution"], "failed")

            # summary md: 00-08 (本切片应有 00/01/02/03/05/06/07/08)
            for name in ("00_overview", "01_data_quality", "02_prediction_generalization",
                         "03_environment_effects", "05_cellline_heterogeneity",
                         "06_evidence_integration", "07_biological_hypotheses",
                         "08_anomaly_report"):
                md = (out / "reports" / f"{name}.md")   # 2026-09-13: 报告子目录 summary/ -> reports/
                self.assertTrue(md.exists(), name)
                text = md.read_text(encoding="utf-8")
                self.assertGreater(len(text.strip()), 50, name)
            dq = (out / "reports" / "01_data_quality.md").read_text(encoding="utf-8")
            self.assertIn("01 Data Quality", dq)
            self.assertIn("cell-line × environment 覆盖", dq)
            an = (out / "reports" / "08_anomaly_report.md").read_text(encoding="utf-8")
            self.assertIn("08 Anomaly Report", an)
            self.assertIn("明细", an)

            # anomaly_report.csv 固定 header (无异常也必须有列名)
            ar = pd.read_csv(out / "tables" / "anomaly_report.csv")
            self.assertIn("anomaly_type", ar.columns)

            # figures + execution_log 记录
            pngs = sorted(out.glob("figures/*/*.png"))
            self.assertGreaterEqual(len(pngs), 3)
            log = json.loads((out / "execution_log.json").read_text(encoding="utf-8"))
            self.assertEqual(log["executed"]["visualization"], "completed")
            self.assertGreaterEqual(len(log.get("figures", [])), 3)
            self.assertTrue(all("png" in f for f in log["figures"]))


if __name__ == "__main__":
    unittest.main()
