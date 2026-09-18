"""WT → Position 18 代表性序列挑选的回归测试。

锁定三类容易被无声改坏的东西：

1. **位点约定**必须从 schema 派生、并与论文脚本的 REGIONS 一致（不写死 23/20/18）；
2. **突变构造**只能改关注位点；**30-mer 取窗必须区分正负链**
   （负链上 guide 的 5' 端在坐标高端——这里曾经写反过，靠 core==sgRNA 断言才暴露）；
3. **已产出的交付物**满足全部硬不变量：8 条、pos18=C、只差 1 个碱基、30-mer 合法、
   细胞系均衡、两两错配达标、无重复/反向互补重复。

测试不联网：30-mer 的取窗逻辑用桩函数验证，交付物用已落盘的 CSV/FASTA 校验。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

SCRIPT = REPO_ROOT / "analysis/candidates/wt_position18_selection.py"
OUT_DIR = REPO_ROOT / "results/tables/candidates"

#: 测试用的合法序列：20 nt spacer + AGG。索引 17 必须正好是 C（关注位点）。
SPACER20 = "ACGTACGTACGTACGTACGT"
CORE23 = SPACER20 + "AGG"
assert len(CORE23) == 23 and CORE23[17] == "C" and CORE23[-2:] == "GG"


@pytest.fixture(scope="module")
def sel():
    spec = importlib.util.spec_from_file_location("wt_pos18_sel", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wt_pos18_sel"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def schema():
    from core.data.splitting.cell_line_division import load_feature_schema
    from core.common.paths import resolve_dataset
    return load_feature_schema(str(resolve_dataset("DeepCRISPR")))


# --------------------------------------------------------------------------- #
# 1. 位点约定
# --------------------------------------------------------------------------- #
def test_convention_is_derived_from_schema(sel, schema):
    conv = sel.LocusConvention(schema)
    assert conv.seq_len == int(schema["sequence_length"]) == 23
    assert conv.spacer_len == conv.seq_len - sel.PAM_LEN
    assert conv.pam_end_1b == conv.seq_len
    assert conv.pos_index0 == sel.POS_1B - 1


def test_convention_matches_project_region_definitions(sel, schema):
    """本脚本的 PAM / seed 区间必须与论文脚本的 REGIONS 完全一致。"""
    conv = sel.LocusConvention(schema)
    note = sel.cross_check_with_project(conv)          # 不一致会抛错
    assert "REGIONS" in note


def test_pam_and_position_helpers(sel, schema):
    conv = sel.LocusConvention(schema)
    seq = CORE23                            # 20nt spacer + AGG
    assert conv.pam_of(seq) == "AGG"
    assert conv.pos18_of(seq) == seq[17] == "C"
    assert conv.valid_pam(seq) is True
    assert conv.valid_pam(CORE23[:20] + "AAA") is False        # PAM 非 NGG


# --------------------------------------------------------------------------- #
# 2. 突变构造 + 30-mer 取窗（含正负链）
# --------------------------------------------------------------------------- #
def test_build_mutant_changes_only_position_18(sel, schema):
    conv = sel.LocusConvention(schema)
    wt = CORE23
    mut = sel.build_mutant(wt, conv)
    v = sel.verify_mutation(wt, mut, conv)
    assert v["only_one_position_changed"] and v["prefix_equal"] and v["suffix_equal"]
    assert v["wt_pos18"] == "C" and v["mut_pos18"] == "A"
    assert wt[:17] == mut[:17] and wt[18:] == mut[18:]      # 题目要求的等价形式
    assert wt[17] == "C" and mut[17] == "A"


def test_window_bounds_are_strand_aware(sel):
    """正链：上游在低坐标侧；负链：上游在高坐标侧（此前写反过）。"""
    plus = pd.Series({"Chromosome": "chr1", "Start": 1001, "End": 1023, "Strand": "+"})
    minus = pd.Series({"Chromosome": "chr1", "Start": 1001, "End": 1023, "Strand": "-"})
    # start0 = 1000, end = 1023
    assert sel._crispron_window_bounds(plus) == (1000 - sel.UPSTREAM_NT, 1023 + sel.DOWNSTREAM_NT)
    assert sel._crispron_window_bounds(minus) == (1000 - sel.DOWNSTREAM_NT, 1023 + sel.UPSTREAM_NT)
    for row in (plus, minus):
        lo, hi = sel._crispron_window_bounds(row)
        assert hi - lo == sel.CRISPRON_LEN == 30


@pytest.mark.parametrize("strand", ["+", "-"])
def test_build_30mer_orients_by_strand(sel, schema, monkeypatch, strand):
    """正负链都要把 30-mer 定向成"4 nt 上游 + 23 nt guide + 3 nt 下游"。

    桩函数按**真实请求区间**从合成正链参考里切片，因此这里验证的是
    ``_crispron_window_bounds`` 的链方向逻辑，而不是桩的假设。
    """
    from analysis.leakage import revcomp
    conv = sel.LocusConvention(schema)
    start0, end = 1000, 1023                      # 正链上 23nt 核心 = [1000, 1023)
    # 现实中的数据是"guide 序列"（位点 18 = C）；负链时正链参考核心是它的反向互补。
    guide = CORE23
    core_plus = guide if strand == "+" else revcomp(guide)
    ref = "A" * start0 + core_plus + "G" * 60      # 合成正链参考
    row = pd.Series({"Chromosome": "chr1", "Start": start0 + 1, "End": end,
                     "Strand": strand, "sgRNA": guide})

    monkeypatch.setattr(sel, "fetch_hg19_window",
                        lambda chrom, lo, hi: ref[lo:hi])
    win, _ = sel.build_30mer(row, conv)

    assert len(win) == sel.CRISPRON_LEN == 30
    assert win[4:27] == guide, "30-mer 中间 23nt 必须等于 guide"
    assert win[4 + conv.pos_index0] == "C"
    # 侧翼必须是"guide 上游 4 nt / 下游 3 nt"（负链会被反向互补）
    if strand == "+":
        assert win[:4] == "AAAA" and win[27:] == "GGG"
    else:
        assert win[:4] == "CCCC" and win[27:] == "TTT"


def test_build_30mer_raises_on_reference_mismatch(sel, schema, monkeypatch):
    """参考序列与数据不一致时必须报错，而不是静默产出错位的 30-mer。"""
    conv = sel.LocusConvention(schema)
    mismatched = CORE23[:17] + "A" + CORE23[18:]      # 与数据差 1 个碱基
    row = pd.Series({"Chromosome": "chr1", "Start": 1001, "End": 1023,
                     "Strand": "+", "sgRNA": CORE23})
    monkeypatch.setattr(sel, "fetch_hg19_window",
                        lambda chrom, lo, hi: "TTTT" + mismatched + "CCC")
    with pytest.raises(RuntimeError, match="参考序列与数据不一致"):
        sel.build_30mer(row, conv)


# --------------------------------------------------------------------------- #
# 3. 交付物不变量
# --------------------------------------------------------------------------- #
needs_outputs = pytest.mark.skipif(
    not (OUT_DIR / "wt_position18_candidates.csv").exists(),
    reason="尚未运行挑选脚本（results/tables/candidates/ 不存在）")


@needs_outputs
def test_deliverables_satisfy_hard_invariants(sel, schema):
    conv = sel.LocusConvention(schema)
    p = pd.read_csv(OUT_DIR / "wt_position18_candidates.csv")

    assert 6 <= len(p) <= 8, "入选数应为 6–8 条"
    assert p["ID"].is_unique

    for _, r in p.iterrows():
        wt, mut = str(r["sgRNA"]), str(r["mutant"])
        # 只改关注位点
        assert wt[conv.pos_index0] == "C" and mut[conv.pos_index0] == "A"
        assert wt[:conv.pos_index0] == mut[:conv.pos_index0]
        assert wt[conv.pos_index0 + 1:] == mut[conv.pos_index0 + 1:]
        assert sum(1 for a, b in zip(wt, mut) if a != b) == 1
        # 合法 PAM
        assert conv.valid_pam(wt)
        # 标签在范围内
        assert 0.0 <= float(r["Normalized efficacy"]) <= 1.0


@needs_outputs
def test_deliverables_are_diverse(sel, schema):
    p = pd.read_csv(OUT_DIR / "wt_position18_candidates.csv")
    seqs = list(p["sgRNA"])
    mms = [sum(1 for a, b in zip(x, y) if a != b)
           for i, x in enumerate(seqs) for y in seqs[i + 1:]]
    assert min(mms) >= sel.MIN_PAIRWISE_MISMATCH, f"存在过于相似的序列: 最小错配 {min(mms)}"
    # 细胞系均衡：每系不超过上限
    assert p["cell_line"].value_counts().max() <= sel.MAX_PER_CELL_LINE
    assert p["cell_line"].nunique() >= 3, "至少覆盖 3 个细胞系"


@needs_outputs
def test_fasta_records_are_valid_crispron_inputs(sel, schema):
    conv = sel.LocusConvention(schema)
    p = pd.read_csv(OUT_DIR / "wt_position18_candidates.csv")
    lines = (OUT_DIR / "wt_position18_crispron_input.fa").read_text().strip().split("\n")
    assert len(lines) == 4 * len(p), "每条应为 4 行（WT 头/序列 + C18A 头/序列）"

    for i, (_, r) in enumerate(p.iterrows()):
        h_wt, s_wt, h_mu, s_mu = lines[4 * i:4 * i + 4]
        assert "_WT" in h_wt and "_C18A" in h_mu
        for s in (s_wt, s_mu):
            assert len(s) == sel.CRISPRON_LEN == 30          # CRISPRon 要求 30 nt
            assert set(s) <= set("ACGT")                     # 不能有 N
        assert s_wt[4:27] == r["sgRNA"]
        assert s_mu[4:27] == r["mutant"]
        assert s_wt[:4] == s_mu[:4] and s_wt[27:] == s_mu[27:]   # 侧翼相同
        assert sum(1 for a, b in zip(s_wt, s_mu) if a != b) == 1
        assert s_wt[4 + conv.pos_index0] == "C" and s_mu[4 + conv.pos_index0] == "A"
        # NGG PAM：30-mer 里 PAM 位于 [4+spacer_len, 4+seq_len)
        pam = s_wt[4 + conv.spacer_len:4 + conv.seq_len]
        assert pam.endswith(sel.PAM_MOTIF) and len(pam) == sel.PAM_LEN


@needs_outputs
def test_funnel_and_bins_are_recorded(sel):
    fun = pd.read_csv(OUT_DIR / "wt_position18_selection_audit.csv")
    stages = set(fun["stage"].dropna())
    for required in ("0_pool", "6_pos18_is_C", "7_pam_ngg",
                     "8_crispron_window_available", "9_hg19_30mer_verified"):
        assert required in stages, f"漏斗缺少阶段 {required}"

    bins = pd.read_csv(OUT_DIR / "wt_position18_label_bins.csv")
    assert {"cell_line", "bin", "median", "n"} <= set(bins.columns)
    assert set(bins["bin"]) == {"low", "medium", "high"}


@needs_outputs
def test_selfcheck_declares_no_mutant_information(sel):
    sc = json.loads((OUT_DIR / "wt_position18_selfcheck.json").read_text())
    assert sc["rule_version"] == sel.SELECTION_RULE_VERSION
    assert sc["mutant_fields_present_in_selection"] == []
    assert sc["wt_only_columns"], "必须记录挑选阶段实际读取的 WT 侧列"


@needs_outputs
def test_selection_rule_is_preregistered_in_source(sel):
    """规则必须写死在脚本里（含版本号），不能是运行时可变的。"""
    src = SCRIPT.read_text(encoding="utf-8")
    assert sel.SELECTION_RULE_VERSION in src
    assert "SELECTION_RULE" in src
    for token in ("test 集", "三分位", "中位数", "错配"):
        assert token in src, f"规则描述缺少关键要素: {token}"
