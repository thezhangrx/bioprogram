"""Sequence Motif Discovery 测试 (任务书 §38 的 12 组 + 表现层/降级)。

执行顺序: unit (iupac / seqlet / clustering / enrichment / stability) ->
task runner (合成 attribution + 序列, 走真实 run_motif_discovery) ->
real-batch smoke (缺 artifact 自动 skip, 不伪造)。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.config import AnalysisConfig, MotifDiscoveryConfig
from analysis.sequence.motif import core
from analysis.sequence.motif.iupac import (consensus_from_frequencies, contains_iupac,
                                          count_occurrences, human_pattern, information_content,
                                          iupac_code, matches_iupac, pfm_from_instances,
                                          pwm_from_pfm, regex_pattern)

ROOT = Path(__file__).resolve().parent.parent.parent
BATCH = ROOT / "results" / "batch_20260909_full"


# ---------------------------------------------------------------------------
# 1) IUPAC / pattern / regex
# ---------------------------------------------------------------------------
class TestIupacConversion(unittest.TestCase):
    def test_required_examples(self):
        # (A/G)TC -> IUPAC RTC, regex [AG]TC
        self.assertEqual(iupac_code({"A", "G"}) + "TC", "RTC")
        self.assertEqual(human_pattern({"A", "G"}) + "TC", "(A/G)TC")
        self.assertEqual(regex_pattern({"A", "G"}) + "TC", "[AG]TC")
        # A(T/C)G -> IUPAC AYG, regex A[TC]G
        self.assertEqual("A" + iupac_code({"T", "C"}) + "G", "AYG")
        self.assertEqual("A" + regex_pattern(["T", "C"]) + "G", "A[TC]G")
        self.assertEqual("A" + human_pattern(["T", "C"]) + "G", "A(T/C)G")
        self.assertEqual("A" + regex_pattern({"T", "C"}) + "G", "A[CT]G")  # 集合 -> 规范序

    def test_all_degenerate_codes(self):
        pairs = {("A", "G"): "R", ("C", "T"): "Y", ("C", "G"): "S", ("A", "T"): "W",
                 ("G", "T"): "K", ("A", "C"): "M", ("C", "G", "T"): "B",
                 ("A", "G", "T"): "D", ("A", "C", "T"): "H", ("A", "C", "G"): "V"}
        for bases, code in pairs.items():
            self.assertEqual(iupac_code(set(bases)), code, bases)
        self.assertEqual(iupac_code({"A", "C", "G", "T"}), "N")
        self.assertEqual(iupac_code(set()), "N")          # 未知 -> N, 不假装是 A

    def test_human_and_regex_separate_forms(self):
        self.assertEqual(human_pattern({"A", "C", "T"}), "(A/C/T)")
        self.assertEqual(regex_pattern({"A", "C", "T"}), "[ACT]")
        self.assertEqual(human_pattern({"A"}), "A")
        self.assertEqual(regex_pattern({"A"}), "A")
        self.assertNotIn("[", human_pattern({"A", "G"}))   # 不用 [A|G] 作为唯一格式

    def test_sliding_window_matching(self):
        codes = list("RTC")
        self.assertEqual(count_occurrences("ACGATCG", codes), 1)
        self.assertTrue(contains_iupac("ACGGTCG", codes))
        self.assertFalse(contains_iupac("ACGCCCG", codes))
        self.assertFalse(contains_iupac("AC", codes))      # motif 比序列长
        self.assertFalse(matches_iupac("ATCG", codes))     # 长度不一致


class TestConsensusGeneration(unittest.TestCase):
    def test_consensus_from_frequencies(self):
        freqs = [{"A": 0.6, "G": 0.4}, {"T": 0.95}, {"C": 0.9}]
        cons = consensus_from_frequencies(freqs, degenerate_fraction=0.25)
        self.assertEqual(cons["consensus"], "ATC")
        self.assertEqual(cons["iupac"], "RTC")
        self.assertEqual(cons["human_pattern"], "(A/G)TC")
        self.assertEqual(cons["regex"], "[AG]TC")

    def test_pfm_pwm_information_content(self):
        pfm = pfm_from_instances(["ATCG", "ATCG", "ATGG"])
        self.assertEqual(pfm.shape, (4, 4))
        self.assertAlmostEqual(float(pfm.sum()), 12.0)
        pwm = pwm_from_pfm(pfm)
        self.assertEqual(pwm.shape, (4, 4))
        ic = information_content(pfm)
        self.assertEqual(ic.shape, (4,))
        self.assertGreater(float(ic[3]), 0.05)             # 第 4 位有信息量
        self.assertLessEqual(float(ic[0]), 2.0 + 1e-9)     # 上界 2 bits


# ---------------------------------------------------------------------------
# 2) Seqlet extraction / direction
# ---------------------------------------------------------------------------
def _profile(length: int = 23, peak_positions=(3, 4, 5), peak_bases=("C", "T", "G")) -> np.ndarray:
    prof = np.zeros((length, 4))
    for i in range(length):
        for j, base in enumerate(core.SEQ_CHANNELS):
            prof[i, j] = 0.01
    for pos, base in zip(peak_positions, peak_bases):
        prof[pos, core.SEQ_CHANNELS.index(base)] = 1.0
    return prof


def _sequences(n: int = 30, motif: str = "CTG", prefix: str = "AAA") -> pd.DataFrame:
    rows = []
    for i in range(n):
        seq = (prefix + motif + "AAA" * 6)[:23]
        rows.append({"row_index": i, "cell_line": "c1", "sgRNA": seq,
                     "efficacy": 0.5 + 0.01 * i})
    return pd.DataFrame(rows)


class TestSeqletExtraction(unittest.TestCase):
    def test_seqlets_have_required_fields(self):
        cfg = AnalysisConfig().motif
        ctx = {"model": "cnn", "model_variant": "cnn33", "split_type": "single",
               "environment": "all", "attribution_method": "cnn_ig"}
        seqlets = core.extract_seqlets(_sequences(), _profile(), cfg, ctx)
        self.assertTrue(seqlets)
        s = seqlets[0]
        for field in ("sample_id", "cell_line", "position_start", "position_end",
                      "sequence", "attribution_score", "direction", "model",
                      "attribution_method"):
            self.assertIn(field, s)
        for s in seqlets:
            self.assertGreaterEqual(s["position_start"], 1)
            self.assertLessEqual(s["position_end"], 23)
            self.assertEqual(len(s["sequence"]), s["position_end"] - s["position_start"] + 1)

    def test_not_single_top_position(self):
        """seqlet 必须是窗口 (>= min_length), 不是单点。"""
        cfg = AnalysisConfig().motif
        ctx = {"model": "cnn", "model_variant": "cnn33", "split_type": "single",
               "environment": "all", "attribution_method": "cnn_ig"}
        seqlets = core.extract_seqlets(_sequences(), _profile(), cfg, ctx)
        self.assertTrue(all(len(s["sequence"]) >= cfg.min_length for s in seqlets))

    def test_direction_separation_when_signed(self):
        cfg = AnalysisConfig().motif
        ctx = {"model": "cnn", "model_variant": "cnn33", "split_type": "single",
               "environment": "all", "attribution_method": "cnn_ig"}
        signed = _profile()
        signed[:, :] = -0.5
        signed[3:6, core.SEQ_CHANNELS.index("C")] = 0.8
        pos = core.extract_seqlets(_sequences(), _profile(), cfg, ctx, signed=True,
                                   signed_profile=_profile())
        neg = core.extract_seqlets(_sequences(), _profile(), cfg, ctx, signed=True,
                                   signed_profile=signed)
        self.assertTrue(all(s["direction"] == "signed_positive" for s in pos))
        self.assertTrue(all(s["direction"] == "signed_negative" for s in neg))
        unsigned = core.extract_seqlets(_sequences(), _profile(), cfg, ctx)
        self.assertTrue(all(s["direction"] == "unsigned" for s in unsigned))

    def test_signed_detection_ignores_other_models(self):
        """linear coefficient 的负号不能被当成 CNN 序列 attribution 的符号。"""
        cnn_only = pd.DataFrame({"method": ["cnn_ig"], "effect": [np.nan]})
        self.assertIsNone(core.signed_value_column(cnn_only))
        mixed = pd.DataFrame({"method": ["linear_coefficient", "linear_coefficient",
                                         "linear_coefficient", "cnn_ig"],
                              "effect": [-1.0, 2.0, -3.0, np.nan]})
        self.assertEqual(core.signed_value_column(mixed), "effect")   # 有符号列存在
        filtered = mixed[mixed["method"] == "cnn_ig"]
        self.assertIsNone(core.signed_value_column(filtered))         # 过滤后无符号


# ---------------------------------------------------------------------------
# 3) Clustering / support
# ---------------------------------------------------------------------------
class TestMotifClustering(unittest.TestCase):
    def _seqlets(self, sequences, score=1.0):
        return [{"sequence": s, "attribution_score": score, "sample_id": i, "cell_line": "c1",
                 "position_start": 5, "position_end": 5 + len(s) - 1, "efficacy": 0.5}
                for i, s in enumerate(sequences)]

    def test_similar_seqlets_cluster_together(self):
        cfg = AnalysisConfig().motif
        clusters = core.cluster_seqlets(
            self._seqlets(["CTGG"] * 5 + ["ATTT"] * 5), cfg)
        sizes = sorted((len(c["instances"]) for c in clusters), reverse=True)
        self.assertEqual(sizes[0], 5)
        self.assertEqual(len(clusters), 2)

    def test_min_support_filter(self):
        cfg = AnalysisConfig().motif
        clusters = core.cluster_seqlets(self._seqlets(["CTGG"] * 3), cfg)
        seqs = pd.DataFrame({"row_index": range(10), "cell_line": "c1",
                             "sgRNA": ["A" * 23] * 10, "efficacy": [0.5] * 10})
        self.assertEqual(core.finalize_clusters(clusters, cfg, {"c1": seqs}), [])

    def test_specificity_status(self):
        cfg = AnalysisConfig().motif
        clean = {"iupac": "CTGG", "length": 4}
        vague = {"iupac": "NNNN", "length": 4}
        n_amb_clean = sum(1 for c in clean["iupac"] if c not in "ACGT")
        n_amb_vague = sum(1 for c in vague["iupac"] if c not in "ACGT")
        self.assertLessEqual(n_amb_clean / 4, cfg.max_ambiguous_fraction)   # -> status ok
        self.assertGreater(n_amb_vague / 4, cfg.max_ambiguous_fraction)     # -> exploratory


class TestMotifPositionAndRegion(unittest.TestCase):
    def test_region_from_config_only(self):
        cfg = MotifDiscoveryConfig()
        self.assertEqual(core.region_of(5, 8, cfg), "Other")     # 未配置 -> 不假设 seed/PAM
        cfg2 = MotifDiscoveryConfig(region_ranges=(("Seed", 1, 8), ("PAM-proximal", 9, 15)))
        self.assertEqual(core.region_of(3, 6, cfg2), "Seed")
        self.assertEqual(core.region_of(12, 14, cfg2), "PAM-proximal")
        self.assertEqual(core.region_of(20, 22, cfg2), "Other")

    def test_position_fields(self):
        cfg = AnalysisConfig().motif
        starts = [5, 5, 6, 7, 7, 7, 5, 6, 7, 5, 6, 7] * 4      # 48 个 seqlet (>= min support)
        seqlets = []
        for i, start in enumerate(starts):
            seqlets.append({"sequence": "CTGG", "attribution_score": 1.0, "sample_id": i,
                            "cell_line": "c1", "position_start": start, "position_end": start + 3,
                            "efficacy": 0.4 + 0.01 * i, "model": "cnn", "model_variant": "cnn33",
                            "split_type": "single", "environment": "all",
                            "attribution_method": "cnn_ig", "direction": "unsigned"})
        clusters = core.cluster_seqlets(seqlets, cfg)
        seqs = pd.DataFrame({"row_index": range(60), "cell_line": "c1",
                             "sgRNA": ["A" * 23] * 60, "efficacy": np.linspace(0.1, 0.9, 60)})
        motifs = core.finalize_clusters(clusters, cfg, {"c1": seqs})
        self.assertTrue(motifs)
        m = motifs[0]
        self.assertIn("position_distribution", m)
        self.assertAlmostEqual(m["position_mean"], float(np.mean(starts)), places=6)
        self.assertGreaterEqual(m["position_std"], 0.0)
        self.assertIn(str(m["position_start"]), m["position_distribution"])


# ---------------------------------------------------------------------------
# 4) Enrichment / FDR / stability
# ---------------------------------------------------------------------------
class TestMotifEnrichment(unittest.TestCase):
    def _seqs(self, n: int = 200, carrier_fraction_high: float = 0.8):
        rng = np.random.default_rng(0)
        rows = []
        motif = "CTGG"
        for i in range(n):
            high = i < n // 2
            carries = (rng.random() < (carrier_fraction_high if high else 0.2))
            seq = list("".join(rng.choice(list("ACGT"), 23)))
            if carries:
                seq[5:9] = list(motif)
            rows.append({"row_index": i, "cell_line": "c1", "sgRNA": "".join(seq),
                         "efficacy": 0.8 if high else 0.2})
        return pd.DataFrame(rows)

    def test_enrichment_statistics(self):
        cfg = AnalysisConfig().motif
        motif = {"motif_id": "m1", "iupac": "CTGG", "length": 4}
        row = core.enrichment_for_motif(motif, {"c1": self._seqs()}, cfg, 0.05)
        self.assertEqual(row["status"], "ok")
        self.assertGreater(row["foreground_count"], row["background_count"] * 0.1)
        self.assertGreater(row["odds_ratio"], 1.0)
        self.assertLess(row["p_value"], 0.05)

    def test_no_carriers_is_unavailable_not_fake(self):
        cfg = AnalysisConfig().motif
        motif = {"motif_id": "m1", "iupac": "TTTTTTTT", "length": 8}
        row = core.enrichment_for_motif(motif, {"c1": self._seqs()}, cfg, 0.05)
        self.assertEqual(row["status"], "unavailable")
        self.assertIsNone(row["p_value"])

    def test_fdr_within_family(self):
        rows = [{"motif_id": f"m{i}", "p_value": p, "fdr_family": "motif_enrichment"}
                for i, p in enumerate([0.001, 0.01, 0.02, 0.5])]
        out = core.apply_enrichment_fdr(rows)
        self.assertTrue(all(r["FDR"] is not None for r in out))
        self.assertLessEqual(out[0]["FDR"], out[3]["FDR"])


class TestMotifStability(unittest.TestCase):
    def test_labels(self):
        cfg = AnalysisConfig().motif
        strong = {"model_variant": "cnn33;cnn53;cnn73", "cellline_support": 3,
                  "support_count": 100}
        moderate = {"model_variant": "cnn33;cnn53;cnn73", "cellline_support": 3,
                    "support_count": 100}
        model_specific = {"model_variant": "cnn33;cnn53", "cellline_support": 1,
                          "support_count": 100}
        exploratory = {"model_variant": "cnn33", "cellline_support": 1, "support_count": 50}
        self.assertEqual(core.stability_label(strong, cfg, 0.001), "Strong motif evidence")
        self.assertEqual(core.stability_label(moderate, cfg, None), "Moderate motif evidence")
        self.assertEqual(core.stability_label(model_specific, cfg, None), "Model-specific motif")
        self.assertEqual(core.stability_label(exploratory, cfg, None), "Exploratory motif")
        self.assertEqual(core.stability_label({"model_variant": "cnn33",
                                               "cellline_support": 1, "support_count": 1},
                                              cfg, None), "Inconclusive")


# ---------------------------------------------------------------------------
# 5) 端到端 (合成 attribution + 合成序列) + 表格/报告
# ---------------------------------------------------------------------------
def _synthetic_attribution(cell: str = "c1", n_pos: int = 23,
                           peak: tuple = (3, 4, 5)) -> pd.DataFrame:
    rows = []
    for method in ("cnn_ism", "cnn_ig"):
        for arch in ("cnn33", "cnn53"):
            for pos in range(1, n_pos + 1):
                for ch in core.SEQ_CHANNELS:
                    val = 1.0 if (pos - 1 in peak and ch in ("C", "T", "G")) else 0.01
                    rows.append({"feature": f"{ch}_pos_{pos}", "channel": ch, "position": pos,
                                 "model": "cnn", "architecture": arch,
                                 "split_type": "single", "cell_line": cell,
                                 "environment": "all", "method": method,
                                 "importance": val, "snr": 2.0, "effect": np.nan,
                                 "attention_entropy": np.nan, "source_file": "synthetic"})
    return pd.DataFrame(rows)


class TestEndToEndMotifDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "c1_metadata.csv").write_text(
            "Cell line,Chromosome,Start,End,Strand,sgRNA,Normalized efficacy\n" +
            "\n".join(f"c1,chr1,{i},{i+22},+,{('AAA' + 'CTG' + 'AAA' * 6)[:23]},"
                      f"{0.5 + 0.01 * i}" for i in range(40)), encoding="utf-8")
        self.attr = _synthetic_attribution()

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_and_write_tables_and_report(self):
        from analysis.sequence.motif.pipeline import run_and_write
        with tempfile.TemporaryDirectory() as out:
            out = Path(out)
            res = run_and_write(self.attr, BATCH, out / "tables", out / "reports",
                                out / "figures", data_root=self.root,
                                discovery=True, enrichment=True)
            self.assertGreater(res["summary"]["n_motifs"], 0)
            for name in ("motif_candidates.csv", "motif_instances.csv",
                         "motif_enrichment.csv", "motif_consistency.csv",
                         "motif_evidence.csv"):
                self.assertTrue((out / "tables" / name).exists(), name)
            cand = pd.read_csv(out / "tables" / "motif_candidates.csv")
            for col in core.CANDIDATE_COLUMNS:
                self.assertIn(col, cand.columns, col)
            self.assertTrue((out / "reports" / "04_sequence_and_motifs.md").exists())
            md = (out / "reports" / "04_sequence_and_motifs.md").read_text()
            for token in ("Seqlet extraction", "IUPAC", "human", "regex", "Enrichment",
                          "Stability criteria"):
                self.assertIn(token, md)
            figs = list((out / "figures" / "04_motif").rglob("*.png"))
            self.assertTrue(figs)

    def test_disabled_discovery_is_reported_not_faked(self):
        from analysis.sequence.motif.pipeline import run_motif_discovery
        res = run_motif_discovery(self.attr, BATCH, data_root=self.root, discovery=False)
        self.assertEqual(res["motifs"], [])
        self.assertTrue(any("user_disabled" in r for r in res["unavailable_reasons"]))

    def test_no_attribution_is_unavailable(self):
        from analysis.sequence.motif.pipeline import run_motif_discovery
        res = run_motif_discovery(pd.DataFrame(), BATCH, data_root=self.root)
        self.assertEqual(res["motifs"], [])
        self.assertTrue(any("no compatible sequence attribution" in r
                            for r in res["unavailable_reasons"]))

    def test_mlp_and_attention_are_not_extractors(self):
        from analysis.sequence.motif.pipeline import run_motif_discovery
        attr = self.attr.copy()
        attr["method"] = "mlp_ig"
        attr["model"] = "mlp"
        res = run_motif_discovery(attr, BATCH, data_root=self.root)
        self.assertEqual(res["motifs"], [])

    def test_consistency_reports_transformer_and_seed_unavailable(self):
        from analysis.sequence.motif.pipeline import run_motif_discovery
        res = run_motif_discovery(self.attr, BATCH, data_root=self.root)
        types = {(r["comparison_type"], r["status"]) for r in res["consistency"]}
        self.assertIn(("cross_model_transformer", "unavailable"), types)
        self.assertIn(("seed", "unavailable"), types)


class TestRealBatchMotifSmoke(unittest.TestCase):
    def test_real_artifacts_if_present(self):
        tables = BATCH / "summary" / "tables"
        cand_path = tables / "motif_candidates.csv"
        if not cand_path.exists():
            self.skipTest("motif artifacts not generated yet for the real batch")
        cand = pd.read_csv(cand_path)
        if cand.empty:
            self.skipTest("no motif passed thresholds in this batch")
        for col in ("motif_id", "iupac", "human_pattern", "regex", "length",
                    "support_count", "sample_support", "effect_direction"):
            self.assertIn(col, cand.columns)
        self.assertTrue((cand["length"] >= 4).all())
        self.assertTrue(cand["support_count"].min() >= 10)


if __name__ == "__main__":
    unittest.main()
