#!/usr/bin/env python3
"""论文术语纪律与关键数字的回归测试。

存在理由（为什么需要这个测试）
------------------------------
`docs/paper/` 的重写把两条约束写进了论文：

1. **术语纪律**：模型归因（E3）不得被称为"显著"或"证明"；模型内部反事实（E4）
   不得被写成实验效应（E5）；外部模型一致不得被写成"证实了因果"。
2. **口径纪律**：所有性能数字一律为测试集口径；数值发散 run 为 20（不是 33）。

这两条约束靠人工 grep 维持是不可靠的——措辞会随后续编辑漂移。本测试把
上述约束固化为断言，使违反时立刻失败。

设计原则
--------
* 禁用措辞**允许**出现在明确否定语境中（"不构成"、"不是"、"放弃"）。
  判定方式与 `test_external_validation_crispron.py` 一致：同一行内出现否定标记即放过。
* 只检查确定性的、可机械判定的性质；不检查文风。
* 覆盖范围：`docs/paper/sections/*.tex` 与 `docs/paper/tables/*.tex`。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SECTIONS = ROOT / "docs" / "paper" / "sections"
TABLES = ROOT / "docs" / "paper" / "tables"
MANUSCRIPT = ROOT / "docs" / "paper" / "zh" / "论文.md"

NEGATION_MARKERS = (
    "不", "非", "未", "无", "禁止", "放弃", "≠",
    "not ", "no ", "cannot", "without",
)


def _paper_files() -> list[Path]:
    """两个交付物都要检查：LaTeX 正式稿与中文长稿。"""
    files = sorted(SECTIONS.glob("*.tex")) + sorted(TABLES.glob("*.tex"))
    if MANUSCRIPT.is_file():
        files.append(MANUSCRIPT)
    if not files:
        pytest.skip("docs/paper 下没有可检查的正文文件")
    return files


def _iter_lines():
    for f in _paper_files():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            yield f, i, line


# --------------------------------------------------------------------------
# 1. 禁用措辞只允许出现在否定语境
# --------------------------------------------------------------------------
FORBIDDEN_CLAIMS = (
    "因果证明",
    "证明了因果",
    "生物学机制证明",
    "C18A 导致",
    "证实了编辑效率",
    "所有模型类一致指向 PAM 邻近区",
    "所有模型类的最高归因区域均为 PAM 邻近区",
)


@pytest.mark.parametrize("phrase", FORBIDDEN_CLAIMS)
def test_forbidden_claims_only_in_negation(phrase: str) -> None:
    offenders = []
    for f, i, line in _iter_lines():
        if phrase not in line:
            continue
        if any(m in line for m in NEGATION_MARKERS):
            continue
        offenders.append(f"{f.name}:{i}: {line.strip()[:140]}")
    assert not offenders, (
        f"禁用措辞 '{phrase}' 被当作结论使用（未处于否定语境）：\n  "
        + "\n  ".join(offenders)
    )


def test_attribution_magnitude_never_called_significant() -> None:
    """归因幅值只能被写成描述性汇总，不能被写成"显著"。"""
    import re

    pattern = re.compile(r"归因幅值[^。；\n]{0,25}(显著|证明)")
    offenders = []
    for f, i, line in _iter_lines():
        for m in pattern.finditer(line):
            ctx = line[max(0, m.start() - 20):m.end() + 20]
            if any(n in ctx for n in NEGATION_MARKERS):
                continue
            offenders.append(f"{f.name}:{i}: {ctx.strip()}")
    assert not offenders, "归因幅值被写成统计显著性：\n  " + "\n  ".join(offenders)


# --------------------------------------------------------------------------
# 2. 六层证据必须被形式化且 E5 必须为空
# --------------------------------------------------------------------------
def test_six_evidence_layers_are_defined() -> None:
    p = TABLES / "tab10_evidence_layers.tex"
    if not p.is_file():
        pytest.skip("缺少 tab10_evidence_layers.tex")
    text = p.read_text(encoding="utf-8")
    for layer, name in (("E1", "预测证据"), ("E2", "关联证据"), ("E3", "归因证据"),
                        ("E4", "反事实证据"), ("E5", "实验证据"), ("E6", "因果证据")):
        assert layer in text and name in text, f"六层证据定义缺少 {layer} {name}"
    assert "本文无" in text, "E5（实验证据）必须显式标注为本文没有"
    assert "本文不作任何此类断言" in text, "E6（因果证据）必须显式声明本文不作断言"


# --------------------------------------------------------------------------
# 3. 三个数据集必须全部被报告，包括复现失败的那个
# --------------------------------------------------------------------------
@pytest.mark.parametrize("dataset", ["DeepCRISPR", "Hiranniramol", "Labuhn"])
def test_all_three_datasets_reported(dataset: str) -> None:
    blob = "\n".join(p.read_text(encoding="utf-8")
                     for p in (SECTIONS / "00_abstract.tex",
                               SECTIONS / "03_results.tex",
                               SECTIONS / "06_conclusion.tex")
                     if p.is_file())
    assert dataset in blob, f"{dataset} 未在摘要/结果/结论中出现"


def test_replication_failure_is_not_hidden() -> None:
    """Labuhn 的复现失败必须是主要结果，不得只出现在补充材料。"""
    results = (SECTIONS / "03_results.tex").read_text(encoding="utf-8")
    abstract = (SECTIONS / "00_abstract.tex").read_text(encoding="utf-8")
    conclusion = (SECTIONS / "06_conclusion.tex").read_text(encoding="utf-8")
    for name, text in (("结果", results), ("摘要", abstract), ("结论", conclusion)):
        assert "Labuhn" in text, f"{name}中未报告 Labuhn（复现失败结果被隐藏）"
    assert "-0.725" in results, "结果中缺少 Labuhn 的最低 R²（-0.725）"


# --------------------------------------------------------------------------
# 4. 口径纪律：测试集口径与发散计数
# --------------------------------------------------------------------------
def test_divergence_count_is_test_set_scope() -> None:
    tab0 = (TABLES / "tab0_data_quality.tex").read_text(encoding="utf-8")
    assert "20（全部为 Linear Regression）" in tab0, (
        "tab0 的数值发散计数必须为测试集口径的 20；"
        "33 是验证集口径，不得作为性能依据"
    )
    assert "33（全部为 Linear Regression）" not in tab0


def test_placeholder_is_rendered() -> None:
    """曾出现过未求值的 f-string 占位符 {n//3} 被写入 PDF。"""
    tab0 = (TABLES / "tab0_data_quality.tex").read_text(encoding="utf-8")
    assert "{n//3}" not in tab0, "tab0 中残留未渲染的占位符 {n//3}"
    assert "448/448/448" in tab0, "实验矩阵分布应为 448/448/448"


def test_candidate_table_has_no_hardcoded_region_count() -> None:
    tab6 = (TABLES / "tab6_candidates.tex").read_text(encoding="utf-8")
    assert "2/5" in tab6, "C1 的 PAM 邻近区最高区域计数应为 2/5（实际计算值）"
    assert "highest for 4/5" not in tab6, "tab6 中残留硬编码的错误计数 4/5"


# --------------------------------------------------------------------------
# 5. 关键数字必须在论文中一致出现
# --------------------------------------------------------------------------
KEY_NUMBERS = (
    "0.489",      # Hiranniramol Transformer R²
    "-0.725",     # Labuhn Linear R²（最低）
    "-12.425",    # 第 18 位 C→A 平均变化
    "+0.144",     # 其余位置 C→A 平均变化
    "0.629",      # 跨模型 Δ 的 Pearson
    "1/21",       # 第 18 位在饱和突变中的排名
    "0.875",      # CRISPRon 侧方向一致率
)

# 位置层级归因的权威值（由 analysis/paper_numbers.py 计算，见
# results/paper_rewrite/authoritative_numbers.json 的 attribution_position 字段）
ATTRIBUTION_NUMBERS = (
    "0.0864",     # 五模型（含 Linear）平均谱峰值
    "0.0799",     # 五模型平均谱中的第 18 位
    "0.0878",     # 四模型（剔除 Linear）平均谱峰值
    "100.0%",     # XGBoost 逐上下文峰值落在 17–20 的比例
    "96.9%",      # CNN
    "90.6%",      # MLP
    "65.6%",      # Transformer
    "21.9%",      # Linear（例外）
)

# 已修正的旧数字：这些数字曾出现在论文中但**无法从任何产物复算**
# （2026-09-19 修正）。它们不得重新出现。
STALE_NUMBERS = (
    "0.089",      # 旧稿的"跨模型平均谱峰值"
    "91.7",       # 旧稿的 XGBoost 逐 run 峰值比例
    "86.5",       # 旧稿的 MLP 比例
    "54.0",       # 旧稿的 CNN 比例（实际 96.9）
    "52.9",       # 旧稿的 Linear 比例（实际 21.9）
    "0.529",      # 旧稿的 Linear 最高区域值（实际 PAM 远端区 0.416）
    "-0.049",     # 旧稿的 Labuhn Transformer R²（未舍入值 -0.0495，表格显示 -0.050）
    "0.041--0.095",  # 旧稿的 mixed 上限（实际 0.094）
    # 注意"4/5"本身不是旧数字：它现在有正当含义（5 个模型类中 4 个的峰值进入
    # 17--20 窗口）。旧稿的错误在于把它用作"最高区域为 PAM 邻近区的模型数"，
    # 该用法由 test_candidate_table_has_no_hardcoded_region_count 单独检查。
)


@pytest.mark.parametrize("value", KEY_NUMBERS)
def test_key_numbers_present(value: str) -> None:
    blob = "\n".join(p.read_text(encoding="utf-8")
                     for p in SECTIONS.glob("*.tex"))
    tab7 = TABLES / "tab7_replication.tex"
    if tab7.is_file():
        blob += "\n" + tab7.read_text(encoding="utf-8")
    assert value in blob, f"论文中缺少关键数字 {value}"


@pytest.mark.parametrize("value", KEY_NUMBERS)
def test_key_numbers_present_in_manuscript(value: str) -> None:
    """中文长稿必须与 LaTeX 稿报告同一组关键数字（同一字节序列）。"""
    if not MANUSCRIPT.is_file():
        pytest.skip("中文长稿不存在")
    text = MANUSCRIPT.read_text(encoding="utf-8")
    assert value in text, f"中文长稿缺少关键数字 {value}"


def test_manuscript_uses_ascii_minus() -> None:
    """负号必须用 ASCII '-'，以便与 authoritative_numbers.json 和 LaTeX 源码一致地检索。

    U+2212（MINUS SIGN）在排版上更正确，但会让跨交付物的数字核对静默失败
    （grep '-0.725' 找不到 '−0.725'）。区间用 U+2013、中文破折号用 U+2014，
    因此 U+2212 只可能是数值负号，应统一为 ASCII。
    """
    if not MANUSCRIPT.is_file():
        pytest.skip("中文长稿不存在")
    text = MANUSCRIPT.read_text(encoding="utf-8")
    assert "\u2212" not in text, (
        "中文长稿使用了 U+2212 减号，与 authoritative_numbers.json / LaTeX 源码不一致；"
        "请统一为 ASCII '-'"
    )


def test_stale_region_value_removed() -> None:
    """旧稿称 Linear 的最高区域为 PAM（0.529），与现产物不符。"""
    for p in list(SECTIONS.glob("*.tex")) + list(TABLES.glob("*.tex")):
        text = p.read_text(encoding="utf-8")
        assert "0.529" not in text, f"{p.name} 中残留与产物不符的旧数值 0.529"


@pytest.mark.parametrize("value", ATTRIBUTION_NUMBERS)
def test_attribution_numbers_present(value: str) -> None:
    """位置层级归因必须使用可复算的权威值。"""
    blob = "\n".join(p.read_text(encoding="utf-8") for p in _paper_files())
    assert value in blob, (
        f"论文缺少可复算的归因权威值 {value}；"
        "请用 analysis/paper_numbers.py 重新生成后引用"
    )


@pytest.mark.parametrize("value", STALE_NUMBERS)
def test_stale_attribution_numbers_removed(value: str) -> None:
    """曾出现且无法从产物复算的旧数字不得重新出现。

    这些数字（尤其是 0.089 / 91.7% / 54.0% / 52.9%）在 2026-09-19 的重写中被发现
    与 results/tables/paper/position_profile_by_model.csv 和
    cross_model_position_consistency.csv 不一致，已按可复算值替换。
    """
    offenders = []
    for p in _paper_files():
        text = p.read_text(encoding="utf-8")
        if value in text:
            offenders.append(f"{p.name}")
    assert not offenders, (
        f"旧数字 '{value}' 重新出现在：{', '.join(offenders)}。"
        "该值无法从 results/tables/paper/ 的产物复算，请改用权威值。"
    )


def test_attribution_numbers_match_authoritative_source() -> None:
    """论文引用的归因值必须与 authoritative_numbers.json 一致。

    这是防止"论文数字与产物漂移"的核心断言：从 JSON 读出权威值，
    再检查每个值确实出现在论文中。
    """
    import json

    src = ROOT / "results" / "paper_rewrite" / "authoritative_numbers.json"
    if not src.is_file():
        pytest.skip("authoritative_numbers.json 不存在；请先运行 analysis/paper_numbers.py")
    a = json.loads(src.read_text(encoding="utf-8")).get("attribution_position", {})
    if not a.get("available"):
        pytest.skip("authoritative_numbers.json 不含 attribution_position")

    blob = "\n".join(p.read_text(encoding="utf-8") for p in _paper_files())

    # 五模型与四模型平均谱的首位值必须出现在论文中
    for key in ("mean_all_models", "mean_non_linear"):
        top = a[key][0]
        assert f"{top['value']:.4f}" in blob, (
            f"{key} 的峰值 {top['value']:.4f}（第 {top['position_1b']} 位）未出现在论文中"
        )

    # 逐上下文比例必须出现（含 Linear 的例外值）
    for m, v in a["per_context_peak_in_17_20_single_split"].items():
        pct = f"{v['fraction_in_17_20'] * 100:.1f}%"
        assert pct in blob, (
            f"模型 {m} 的逐上下文峰值比例 {pct} 未出现在论文中"
        )
