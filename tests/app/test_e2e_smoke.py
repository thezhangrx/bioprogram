"""端到端 smoke (无 GPU): QC(真实引擎) → 训练(校验+preflight+dry-run)
→ Analyse(真实 analysis.pipeline 于合成小批次) → 报告读取。

训练不做真实 1344 运行 (dry-run); 真跑训练需在 HPC/用户硬件执行 (见 HPC 协议)。
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent   # repo root


def _make_dataset(dirp: Path) -> Path:
    import pandas as pd
    import random
    rng = random.Random(5)
    rows = []
    for _ in range(80):
        seq = "".join(rng.choice("ACGT") for _ in range(23))
        rows.append({"sgRNA": seq, "Chromosome": "chr1", "Start": 1000, "End": 1022,
                     "Normalized efficacy": round(0.3 + 0.6 * rng.random(), 4)})
    f = dirp / "tiny.csv"
    pd.DataFrame(rows).to_csv(f, index=False)
    return f


def _make_mini_batch(batch: Path) -> None:
    import pandas as pd
    metrics = batch / "summary" / "metrics_tables"
    metrics.mkdir(parents=True)
    ENVS = ["sequence", "sequence_ctcf", "sequence_ctcf_dnase",
            "sequence_ctcf_dnase_h3k4me3"]
    DELTA = {"sequence_ctcf": 0.03, "sequence_ctcf_dnase": 0.05,
             "sequence_ctcf_dnase_h3k4me3": -0.02}
    rows = []
    for model, base in (("LinearRegression", 0.55), ("XGBoost", 0.60)):
        for cell in ("hct116", "hela"):
            for env in ENVS:
                d = DELTA.get(env, 0.0)
                rows.append({
                    "model": model, "split_type": "single", "cell_line": cell,
                    "environment": env, "random_seed": "42",
                    "n_train": 10, "n_valid": 5, "n_test": 5,
                    "R2": round(base + d, 4), "RMSE": round(0.35 - d * 2, 4),
                    "MAE": 0.3, "MSE": 0.2, "Pearson": 0.8, "Spearman": 0.8,
                })
    pd.DataFrame(rows).to_csv(metrics / "all_experiments.csv", index=False)


class TestEndToEndSmoke(unittest.TestCase):
    def test_workflow_smoke(self):
        try:
            import pandas  # noqa: F401
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("pandas/numpy unavailable")
        tmp = Path(tempfile.mkdtemp(prefix="crispr_e2e_"))
        if not os.environ.get("KEEP_E2E"):
            self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        os.environ["CRISPR_WORKSPACE_ROOT"] = str(tmp)
        self.addCleanup(lambda: os.environ.pop("CRISPR_WORKSPACE_ROOT", None))

        from crispr_workspace import analysis, artifacts, qc_service, training

        # 1) QC (真实引擎, CPU 只读)
        ds = _make_dataset(tmp)
        qc = qc_service.QCSessionManager(tmp)
        sess = qc.start(input_paths=[str(ds)], note="e2e")
        self.assertEqual(sess["status"], "completed", sess.get("stderr_tail"))
        summary_path = Path(sess["outputs"]["summary"])
        self.assertTrue(summary_path.exists())
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertIn("outliers", summary)
        fp = qc.fingerprint([str(ds)])
        self.assertTrue(qc.reusable(qc.get(sess["session_id"]), fp),
                        "same dataset must allow QC reuse")

        # 2) 训练: 校验 + preflight + dry-run 提交 (不真跑 1344)
        cfg = training.TrainingConfig(
            kind="dig", models=["linear"], cell_lines=["hct116"],
            split_types=["single"], environments=["sequence"],
            batch_name="e2e_batch", runtime="local_cpu", dry_run=True)
        self.assertEqual(cfg.validate(), [])
        pf = training.preflight(cfg)
        self.assertTrue(pf["ok"], pf)
        run = training.submit(cfg, workspace_root=tmp)
        self.assertEqual(run["status"], "dry-run")
        self.assertEqual(len(training.list_runs(tmp)), 1)

        # 3) Analyse: 真实 analysis.pipeline 于合成小批次
        batch_dir = tmp / "results_e2e" / "batch"
        _make_mini_batch(batch_dir)
        out = tmp / "analysis_out"
        selected = ["qc", "prediction", "environment_conditional_effect",
                    "environment_main_effect", "cellline_heterogeneity",
                    "evidence_integration", "hypothesis_generation"]
        manifest = analysis.run(str(batch_dir), str(out), selected, {"project_id": "smoke"})
        self.assertTrue(manifest["status"] == "running")
        deadline = time.time() + 300
        st = None
        while time.time() < deadline:
            st = analysis.analysis_status(str(out))
            if st.get("status") in ("completed", "failed"):
                break
            time.sleep(1.0)
        self.assertIsNotNone(st)
        self.assertEqual(st["status"], "completed",
                         json.dumps(st, ensure_ascii=False)[:800])

        # 4) 报告产物读取 (Artifact Resolver)
        #    引擎新布局为 <out>/reports/（旧为 <out>/summary/），测试兼容两者
        md_path = Path(out) / "reports" / "00_overview.md"
        if not md_path.exists():
            md_path = Path(out) / "summary" / "00_overview.md"
        self.assertTrue(md_path.exists())
        payload = artifacts.resolve_artifact(str(md_path))
        self.assertEqual(payload["kind"], "md")
        self.assertGreater(len(payload["text"]), 100)
        status_json = (out / "analysis_status.json")
        self.assertTrue(status_json.exists() and json.loads(status_json.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
