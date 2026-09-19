"""CRISPRon 外部模型验证的回归测试。

分三层：

1. **适配层**（纯函数，不依赖第三方软件）：位点映射从 schema 派生而非硬编码、
   30-mer 构造与校验、突变只改一个位置、CRISPRon 期望的 target ID 约定。
2. **与官方行为的对照**：用 CRISPRon 包自带的 ``test/outdir.original/`` 作为
   golden 参照，验证"23 nt 位于 30 nt 的 [4:27]、PAM 位于 [25:27] 且为 GG"
   这一布局与官方实现一致（若解压实例不在则跳过）。
3. **产出物不变量 + provenance 完整性**：标准化表只改位点 18、方向一致性可复算、
   manifest 里的 sha256 与真实文件一致、术语纪律（禁用措辞只出现在否定语境）。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

EXT = REPO_ROOT / "analysis" / "external_validation"
TABLE_DIR = REPO_ROOT / "results" / "tables" / "external_validation"
RUN_DIR = REPO_ROOT / "results" / "external_validation" / "crispron_pos18_v1"
FIG_DIR = REPO_ROOT / "results" / "figures" / "external_validation"
REPORT = REPO_ROOT / "docs" / "reproducibility" / "EXTERNAL_MODEL_VALIDATION_CRISPRON.md"
SOFTWARE_TEST = (REPO_ROOT / "deploy" / "external" / "crispron" / "software"
                 / "crispron-main" / "test")

WT_RUN = "crispron_pos18_v1"
MUT_RUN = "crispron_mutagenesis_v1"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, EXT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def CA():
    return _load("crispron_adapter")


@pytest.fixture(scope="module")
def schema():
    from core.common.paths import resolve_dataset
    from core.data.splitting.cell_line_division import load_feature_schema
    return load_feature_schema(str(resolve_dataset("DeepCRISPR")))


# --------------------------------------------------------------------------- #
# 1. 适配层
# --------------------------------------------------------------------------- #
def test_position_mapping_is_derived_from_schema(CA, schema):
    """位点映射必须由 schema 推导，且显式区分两套编号体系。"""
    spacer_len = int(schema["sequence_length"]) - CA.PRE_PAM - len(CA.PAM_MOTIF)
    assert spacer_len == 20
    m = CA.describe_mapping(spacer_len, 18)

    # 项目侧
    assert m["project_sequence_length"] == 23
    assert m["project_pam_range_1b"] == [21, 23]
    assert m["position_of_interest_1b"] == 18
    assert m["in_spacer"] is True
    # CRISPRon 侧：23 nt 落在 30 nt 的 [4, 26]，关注位点 = 4 + 18 - 1 = 21
    assert m["crispron_total"] == 30
    assert m["crispron_prefix_len"] == 4
    assert m["crispron_target_range_0b"] == [4, 23]
    assert m["crispron_pam_range_0b"] == [24, 26]
    assert m["crispron_index_of_interest_0b"] == 21
    # 关键：不是"把 23nt 的第 18 位直接当成 20nt gRNA 的第 18 位"，
    # 而是 position 18 恰好落在 protospacer 内（二者在此项目重合，但由计算得出）
    assert m["position_within_spacer_1b"] == 18


def test_build_crispron_input_and_pam_check(CA):
    seq = "ACGTACGTACGTACGTACGT" + "AGG"          # 20 nt spacer + AGG
    rec = CA.build_crispron_input("S1", seq, 20, "TTTT", "CCC")
    assert len(rec.crispron_seq) == 30
    assert rec.crispron_seq[:4] == "TTTT" and rec.crispron_seq[-3:] == "CCC"
    assert rec.crispron_seq[4:27] == seq
    assert rec.pam == "AGG"
    assert rec.target_20mer == seq[:20]
    assert rec.crispron_seq[CA.PAM_OFFSET:CA.PAM_OFFSET + 2] == "GG"
    assert rec.expected_target_id == "S1_p_5"

    with pytest.raises(ValueError, match="不是 GG"):
        CA.build_crispron_input("S2", "ACGTACGTACGTACGTACGT" + "AAA", 20, "TTTT", "CCC")
    with pytest.raises(ValueError, match="upstream"):
        CA.build_crispron_input("S3", seq, 20, "TTT", "CCC")
    with pytest.raises(ValueError, match="非 ACGT"):
        CA.build_crispron_input("S4", "ACGTNCGTACGTACGTACGT" + "AGG", 20, "TTTT", "CCC")


def test_mutation_changes_exactly_one_position(CA):
    seq = "ACGTACGTACGTACGTACGT" + "AGG"
    mut, info = CA.mutate_project_sequence(seq, 17, "A")
    assert info["wt_base"] == "C" and info["mut_base"] == "A"
    assert info["n_mismatch"] == 1
    assert info["prefix_equal"] and info["suffix_equal"]
    assert mut[:17] == seq[:17] and mut[18:] == seq[18:]
    assert mut[17] == "A"


def test_mutation_constructs_valid_30mer_with_same_flanks(CA):
    seq = "ACGTACGTACGTACGTACGT" + "AGG"
    mut, _ = CA.mutate_project_sequence(seq, 17, "A")
    wt = CA.build_crispron_input("W", seq, 20, "TTTT", "CCC")
    mu = CA.build_crispron_input("M", mut, 20, "TTTT", "CCC")
    assert wt.crispron_seq[:4] == mu.crispron_seq[:4]
    assert wt.crispron_seq[-3:] == mu.crispron_seq[-3:]
    assert wt.pam == mu.pam
    assert sum(a != b for a, b in zip(wt.crispron_seq, mu.crispron_seq)) == 1
    assert wt.crispron_seq[CA.TARGET_START_IN_30MER + 17] == "C"
    assert mu.crispron_seq[CA.TARGET_START_IN_30MER + 17] == "A"


# --------------------------------------------------------------------------- #
# 2. 与 CRISPRon 官方行为对照（golden）
# --------------------------------------------------------------------------- #
needs_software = pytest.mark.skipif(
    not (SOFTWARE_TEST / "outdir.original" / "30mers.fa").exists(),
    reason="CRISPRon 解压实例不在（见 deploy/external/crispron/INSTALL_NOTES.md）")


@needs_software
def test_official_30mer_layout_matches_our_constants():
    """官方 30mers.fa 里每条都必须是 prefix4 + target20 + PAM(NGG) + suffix3。"""
    fa = (SOFTWARE_TEST / "outdir.original" / "30mers.fa").read_text().strip().split("\n")
    seqs = [fa[i] for i in range(1, len(fa), 2)]
    assert seqs, "golden 30mers.fa 为空"
    for s in seqs:
        assert len(s) == 30
        assert s[25:27] == "GG", f"官方 PAM 位置不是 GG: {s}"
        assert re.fullmatch(r"[ACGT]+", s)
    # 与我们的常量一致
    import analysis.external_validation.crispron_adapter as C
    assert C.TOTAL == 30 and C.PAM_OFFSET == 25 and C.TARGET_START_IN_30MER == 4


@needs_software
def test_official_target_ids_follow_p_position_convention():
    """官方 ID 的 `_p_N` 里 N 就是 1-based 起始位置：前 4 nt 为 prefix 时 N=5。"""
    out = (SOFTWARE_TEST / "outdir.original" / "crispron.csv").read_text().strip().split("\n")
    rows = [l.split(",") for l in out[1:]]
    assert rows
    for rid, seq30, _ in rows:
        m = re.search(r"_([pm])_(\d+)$", rid)
        assert m, f"无法解析官方 ID: {rid}"
        strand, pos = m.group(1), int(m.group(2))
        if strand == "p":
            # plus: target 应从 pos-1 (0-based) 开始
            assert pos >= 5
            assert len(seq30) == 30


# --------------------------------------------------------------------------- #
# 3. 产出物不变量
# --------------------------------------------------------------------------- #
needs_wt = pytest.mark.skipif(
    not (TABLE_DIR / f"{WT_RUN}_wt_c18a_predictions.csv").exists(), reason="尚未运行外部验证")


@needs_wt
def test_standard_table_invariants():
    d = pd.read_csv(TABLE_DIR / f"{WT_RUN}_wt_c18a_predictions.csv")
    assert len(d) == 8
    for _, r in d.iterrows():
        assert len(r["WT_sequence"]) == 23 and len(r["mutant_sequence"]) == 23
        assert r["WT_sequence"][17] == "C" and r["mutant_sequence"][17] == "A"
        assert r["WT_sequence"][:17] == r["mutant_sequence"][:17]
        assert r["WT_sequence"][18:] == r["mutant_sequence"][18:]
        assert sum(a != b for a, b in zip(r["WT_sequence"], r["mutant_sequence"])) == 1
        assert str(r["PAM"]).endswith("GG")
        assert bool(r["qc_only_pos18_changed"]) and bool(r["qc_pam_unchanged"])
        assert bool(r["qc_flanks_identical"]) and bool(r["qc_orientation_preserved"])
        assert bool(r["qc_both_targets_found"])
        assert float(r["delta"]) == pytest.approx(
            float(r["mutant_prediction"]) - float(r["WT_prediction"]))
        assert 0.0 <= float(r["WT_prediction"]) <= 100.0
        assert 0.0 <= float(r["mutant_prediction"]) <= 100.0
    # 30-mer 里 23 nt 必须在 [4:27]，且 PAM 在 [25:27] 为 GG
    for _, r in d.iterrows():
        assert len(r["WT_30mer"]) == 30 and len(r["C18A_30mer"]) == 30
        assert r["WT_30mer"][4:27] == r["WT_sequence"]
        assert r["C18A_30mer"][4:27] == r["mutant_sequence"]
        assert r["WT_30mer"][25:27] == "GG"


@needs_wt
def test_summary_recomputable_from_table():
    d = pd.read_csv(TABLE_DIR / f"{WT_RUN}_wt_c18a_predictions.csv")
    summ = json.loads((TABLE_DIR / f"{WT_RUN}_summary.json").read_text())
    s = summ["summary"]
    valid = d.dropna(subset=["delta"])
    assert s["n_with_delta"] == len(valid)
    assert s["n_negative_delta"] == int((valid["delta"] < 0).sum())
    assert s["directional_consistency_P_delta_lt_0"] == pytest.approx(
        float((valid["delta"] < 0).mean()))


@needs_wt
def test_cross_model_agreement_recomputable():
    p = TABLE_DIR / f"{WT_RUN}_cross_model.csv"
    if not p.exists():
        pytest.skip("无 cross-model 表")
    m = pd.read_csv(p)
    v = m.dropna(subset=["delta", "delta_ours_mean"])
    assert len(v) == 8
    assert float(v["agree_direction"].mean()) == pytest.approx(
        float((v["sign_ours"] == v["sign_crispron"]).mean()))
    # 不一致样本必须被如实保留（不允许为了"好看"删掉）
    dis = v.loc[~v["agree_direction"], "sample_id"].tolist()
    summ = json.loads((TABLE_DIR / f"{WT_RUN}_summary.json").read_text())
    assert summ["cross_model_agreement"].get("disagreeing_samples", []) == dis


@needs_wt
def test_manifest_provenance_is_complete_and_hashes_match_files():
    man = pd.read_csv(RUN_DIR / "external_validation_manifest.csv", dtype=str).fillna("")
    assert len(man) >= 1
    r = man.iloc[-1]
    for col in ("run_id", "timestamp_utc", "software", "package_file", "package_sha256",
                "software_dir", "dependency", "dependency_version", "execution_command",
                "python_version", "dependency_versions_json", "input_file", "input_sha256",
                "n_input_records", "input_sequence_sha256", "model_config",
                "output_file", "output_sha256", "code_fingerprint"):
        assert str(r[col]).strip() != "", f"manifest 字段为空: {col}"

    def sha256(p: Path) -> str:
        h = hashlib.sha256()
        h.update(p.read_bytes())
        return h.hexdigest()

    inp = REPO_ROOT / r["input_file"]
    outp = REPO_ROOT / r["output_file"]
    assert inp.exists() and outp.exists()
    assert sha256(inp) == r["input_sha256"], "输入文件 sha256 与 manifest 不一致"
    assert sha256(outp) == r["output_sha256"], "输出文件 sha256 与 manifest 不一致"
    # 记录的执行命令必须包含 CRISPRon 三个组件
    for token in ("get_30mers_from_fa.py", "CRISPRspec_CRISPRoff_pipeline.py",
                  "DeepCRISPRon_eval.py"):
        assert token in r["execution_command"], f"manifest 未记录 {token}"


def test_archived_package_checksum_matches_recorded():
    """若归档包在本地，其 sha256 必须与归档时记录的 SHA256SUMS.txt 一致。"""
    base = REPO_ROOT / "deploy" / "external" / "crispron"
    for sums, target in ((base / "package" / "SHA256SUMS.txt", base / "package" / "crispron-main.zip"),
                         (base / "dependencies" / "SHA256SUMS.txt",
                          base / "dependencies" / "crisproff-1.1.2.tar.gz")):
        if not sums.exists():
            pytest.skip(f"{sums} 不存在")
        recorded = {}
        for line in sums.read_text().splitlines():
            parts = line.split()
            if len(parts) == 2:
                recorded[parts[1]] = parts[0]
        assert recorded, f"{sums} 为空"
        if not target.exists():
            continue          # 归档包本身不入版本控制，缺失时可从上游重新获取
        h = hashlib.sha256(target.read_bytes()).hexdigest()
        assert h == recorded[target.name], f"{target.name} 校验和不符"


# --------------------------------------------------------------------------- #
# 4. systematic mutagenesis
# --------------------------------------------------------------------------- #
needs_mut = pytest.mark.skipif(
    not (TABLE_DIR / f"{MUT_RUN}_effects.csv").exists(), reason="尚未运行 mutagenesis")


@needs_mut
def test_mutagenesis_covers_all_positions_and_excludes_pam_broken():
    eff = pd.read_csv(TABLE_DIR / f"{MUT_RUN}_effects.csv")
    ok = eff[eff["recognized"] & eff["delta"].notna()]
    # 8 条 × 每序列 20 个可评估位置（PAM 22/23 被破坏）
    assert ok["sample_id"].nunique() == 8
    assert set(ok["position_1b"].unique()) <= set(range(1, 22))
    broken = eff[eff.get("pam_preserved") == False]
    assert len(broken) > 0
    assert set(broken["position_1b"].unique()) <= {22, 23}
    assert broken["delta"].isna().all(), "PAM 被破坏的替换不得进入效应矩阵"


@needs_mut
def test_position18_is_the_top_effect_position():
    """Position 18 的 C→A 应当是全矩阵最强的负效应，且位置影响排名第一。

    这是本轮外部验证的核心结论；若它被改坏，测试必须失败。
    """
    ana = json.loads((TABLE_DIR / f"{MUT_RUN}_pos18_analysis.json").read_text())
    assert ana["pos18_rank_in_position_importance"] == 1
    eff = pd.read_csv(TABLE_DIR / f"{MUT_RUN}_effects.csv")
    ca = eff[(eff["substitution"] == "C>A") & eff["recognized"] & eff["delta"].notna()]
    p18 = ca.loc[ca["position_1b"] == 18, "delta"].mean()
    other = ca.loc[ca["position_1b"] != 18, "delta"].mean()
    assert p18 < other, f"位置 18 的 C→A ({p18:.3f}) 未强于其它位置 ({other:.3f})"
    assert p18 < 0, "位置 18 的 C→A 平均效应应为负"


# --------------------------------------------------------------------------- #
# 5. 图 / 报告 / 术语纪律
# --------------------------------------------------------------------------- #
def test_figures_exist():
    if not FIG_DIR.exists():
        pytest.skip("无图目录")
    for name in ("fig1_wt_vs_c18a_paired.png", "fig2_delta_distribution.png",
                 "fig3_ours_vs_crispron.png", "fig4_position_substitution_heatmap.png"):
        p = FIG_DIR / name
        assert p.exists() and p.stat().st_size > 5000, f"图缺失或过小: {p}"


def test_report_uses_required_terminology_and_no_causal_claim():
    if not REPORT.exists():
        pytest.skip("报告不存在")
    text = REPORT.read_text(encoding="utf-8")
    low = text.lower()
    for term in ("external model validation", "model-based counterfactual",
                 "in-silico mutagenesis", "directional consistency",
                 "cross-model consistency"):
        assert term in low, f"报告缺少必需术语: {term}"

    # 禁用措辞只允许出现在两类位置：
    #   (a) 术语对照表里作为"禁止列"被列举；
    #   (b) 行内带明确否定标记（不 / not / 不能 / ≠ …）。
    lines = low.splitlines()
    in_glossary = False
    for i, line in enumerate(lines, 1):
        if line.startswith("## 术语对照"):
            in_glossary = True
            continue
        if in_glossary and line.startswith("## "):
            in_glossary = False
        if in_glossary:
            continue                      # 术语表本身就是在声明这些词被禁用
        for forbidden in ("causal proof", "experimental effect",
                          "biological mechanism proof", "causes editing efficiency"):
            if forbidden in line:
                negation = ("不", "not ", "no ", "禁止", "不能", "≠", "cannot", "without")
                assert any(n in line for n in negation), (
                    f"报告第 {i} 行把 '{forbidden}' 当作结论使用：{line.strip()[:120]}")
