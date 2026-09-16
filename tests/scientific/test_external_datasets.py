"""外部数据集（Hiranniramol / Labuhn）与「去 DeepCRISPR 默认」的回归测试。

这些测试锁定三类容易再次漂移的行为：

1. **适配层**：三个数据集的原始格式都能被正确转成规范列，且
   * 不静默丢数据（丢弃必须记账，超过阈值直接失败）；
   * PAM 非 GG 会被拒绝；
   * 效率量纲按数据集声明转换（Hiranniramol 0-100 → /100；Labuhn 已是 [0,1]）。
2. **纯序列（4 通道）数据**：能加载、能划分（single/all/mixed）、
   环境组合只展开出 ``sequence``。
3. **不再有 DeepCRISPR 隐式默认**：缺 schema / 空目录 / 缺路径参数时**必须报错**，
   而不是回退到 4 个细胞系或 8 通道 schema。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

RAW_HIRAN = REPO_ROOT / "data/raw/Hiranniramol/Hiranniramol.CSV"
RAW_LABUHN = REPO_ROOT / "data/raw/Labuhn/Labuhn.CSV"
RAW_DEEP = REPO_ROOT / "data/raw/DeepCRISPR/hct116.csv"
HIRAN_PROCESSED = REPO_ROOT / "data/processed/Hiranniramol"
LABUHN_PROCESSED = REPO_ROOT / "data/processed/Labuhn"
DEEPCRISPR_PROCESSED = REPO_ROOT / "data/processed/DeepCRISPR"
FE_SCRIPT = REPO_ROOT / "core/features/engineering/feature_engineering.py"

needs_raw = pytest.mark.skipif(
    not (RAW_HIRAN.exists() and RAW_LABUHN.exists()),
    reason="原始外部数据集不在仓库中",
)


def _adapters():
    return pytest.importorskip("core.features.engineering.dataset_adapters")


# --------------------------------------------------------------------------- #
# 1. 适配层
# --------------------------------------------------------------------------- #
@needs_raw
def test_detect_format_for_all_three_datasets():
    ad = _adapters()
    assert ad.detect_format(pd.read_csv(RAW_HIRAN, nrows=5)) == "hiranniramol"
    assert ad.detect_format(pd.read_csv(RAW_LABUHN, nrows=5)) == "labuhn"
    assert ad.detect_format(pd.read_csv(RAW_DEEP, nrows=5)) == "deepcrispr"


@needs_raw
def test_detect_format_rejects_unknown_schema():
    ad = _adapters()
    with pytest.raises(ValueError, match="无法识别"):
        ad.detect_format(pd.DataFrame({"foo": [1], "bar": [2]}))


@needs_raw
def test_hiranniramol_adapter_scales_target_and_builds_23nt():
    ad = _adapters()
    df, report = ad.load_and_adapt(RAW_HIRAN)
    assert report.dataset == "hiranniramol"
    assert report.rows_out == len(df) > 1000
    # 纯度检查：一个都不能因为序列问题被丢
    assert report.n_dropped == 0
    # 0-100 -> 0-1
    assert df[ad.CANONICAL_TARGET].between(0, 1).all()
    assert report.target_range_in[1] == pytest.approx(100.0)
    # 全部是 23nt 且 PAM=GG
    assert df[ad.CANONICAL_SEQUENCE].str.len().eq(23).all()
    assert df[ad.CANONICAL_SEQUENCE].str[-3:].str.endswith("GG").all()
    assert report.pam_gg_fraction == pytest.approx(1.0)
    # 没有表观通道
    assert report.has_epigenetics is False


@needs_raw
def test_labuhn_adapter_uses_ko_reporter_assay_and_keeps_scale():
    ad = _adapters()
    df, report = ad.load_and_adapt(RAW_LABUHN)
    assert report.dataset == "labuhn"
    # KO_reporter_assay 本来就是 [0,1]，不能再除 100
    assert report.target_range_in[1] == pytest.approx(0.973, abs=1e-3)
    assert df[ad.CANONICAL_TARGET].max() == pytest.approx(report.target_range_in[1])
    assert df[ad.CANONICAL_TARGET].between(0, 1).all()
    assert df[ad.CANONICAL_SEQUENCE].str.len().eq(23).all()
    # 丢弃必须记账，且比例受控
    assert report.drop_fraction <= ad.MAX_DROP_FRACTION
    assert sum(report.drop_reasons.values()) == report.n_dropped


@needs_raw
def test_deepcrispr_adapter_is_lossless_and_keeps_epigenetics():
    ad = _adapters()
    for name in ("hct116", "hek293t", "hela", "hl60"):
        df, report = ad.load_and_adapt(REPO_ROOT / f"data/raw/DeepCRISPR/{name}.csv")
        assert report.n_dropped == 0, f"{name} 不应有丢弃"
        assert report.has_epigenetics is True
        assert df[ad.CANONICAL_SEQUENCE].str.len().eq(23).all()


def _hirani_frame(rows):
    """构造 Hiranniramol 形态的 DataFrame：rows = [(gRNA, extended, efficiency), ...]。"""
    return pd.DataFrame({
        "gRNA": [r[0] for r in rows],
        "Extended Target": [r[1] for r in rows],
        "Edit Efficiency": [r[2] for r in rows],
    })


def _make_ext(sp, tail="N" * 20):
    return "N" * 5 + sp + "AGG" + tail


def _unique_spacers(n):
    """生成 n 个互不相同、且在当前 extended 上下文里**唯一命中**的 20nt spacer。

    两个约束都是必须的：
    * 唯一：适配层会把"同序列"的重复测量取均值合并，循环取模会让多行并成一行；
    * 唯一命中：spacer 之后紧跟 ``AGG``，若 spacer 自身含长重复（例如 20 个 A），
      "spacer + AGG" 会连成更长的 A 串，使 20-mer 在切片窗口内二次命中而被判
      ``spacer_ambiguous``——那是测试数据的问题，不是被测逻辑的问题。
    """
    out = []
    i = 0
    while len(out) < n:
        x, chars = i, []
        for _ in range(20):
            chars.append("ACGT"[x % 4])
            x //= 4
        sp = "".join(chars)
        i += 1
        ext = _make_ext(sp)
        if ext.find(sp) == 5 and ext.find(sp, 6) == -1 and sp not in out:
            out.append(sp)
    return out


def _good_hirani_rows(n):
    """n 条合法且唯一的记录（PAM=GG），用于让坏行占比低于保护阈值。"""
    spacers = _unique_spacers(n)
    return [(sp, _make_ext(sp), 10.0 + i) for i, sp in enumerate(spacers)]


@needs_raw
def test_adapter_rejects_non_gg_pam_unless_allowed():
    """PAM 非 GG 的记录默认被拒；显式放行后保留。

    注意：坏行占比必须低于 MAX_DROP_FRACTION，否则会先触发
    "丢弃比例过高" 保护（该行为由 test_adapter_aborts_when_too_many_rows_dropped 覆盖）。
    """
    ad = _adapters()
    spacer = _unique_spacers(1)[0]
    rows = _good_hirani_rows(9) + [(spacer, "N" * 5 + spacer + "TTT" + "N" * 20, 50.0)]
    df, report = ad.adapt_hiranniramol(_hirani_frame(rows))
    assert report.drop_reasons.get("pam_not_gg") == 1
    assert report.rows_out == 9

    df2, report2 = ad.adapt_hiranniramol(_hirani_frame(rows), allow_non_gg_pam=True)
    assert report2.rows_out == 10
    assert (df2[ad.CANONICAL_SEQUENCE].str[-3:] == "TTT").sum() == 1


@needs_raw
def test_adapter_rejects_ambiguous_spacer_placement():
    """spacer 在 extended 中多次出现 -> 不能猜，必须丢弃并记账。"""
    ad = _adapters()
    spacer = _unique_spacers(1)[0]
    rows = _good_hirani_rows(9) + [(spacer, spacer + "AGG" + spacer + "AGG", 10.0)]
    _, report = ad.adapt_hiranniramol(_hirani_frame(rows))
    assert report.drop_reasons.get("spacer_ambiguous") == 1
    assert report.rows_out == 9


@needs_raw
def test_adapter_merges_replicate_measurements_of_same_guide():
    """同一 sgRNA 测两次、效率不同 -> 按均值合并并记账（Labuhn 实际有 5 条）。"""
    ad = _adapters()
    sp = _unique_spacers(1)[0]
    ext = _make_ext(sp)
    df, report = ad.adapt_hiranniramol(_hirani_frame([(sp, ext, 20.0), (sp, ext, 60.0)]))
    assert report.n_replicates_merged == 1
    assert report.rows_out == 1
    assert df[ad.CANONICAL_TARGET].iloc[0] == pytest.approx(0.40)   # (20+60)/2/100


@needs_raw
def test_adapter_aborts_when_too_many_rows_dropped():
    """坏行占比超过 MAX_DROP_FRACTION 时必须失败，而不是"成功"产出残缺数据。"""
    ad = _adapters()
    spacer = _unique_spacers(1)[0]
    rows = _good_hirani_rows(2) + [(spacer, "N" * 5 + spacer + "TTT" + "N" * 20, 50.0)] * 8
    with pytest.raises(ValueError, match="丢弃比例过高"):
        ad.adapt_hiranniramol(_hirani_frame(rows))


# --------------------------------------------------------------------------- #
# 2. 纯序列 (4 通道) 数据
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not HIRAN_PROCESSED.exists(), reason="Hiranniramol 尚未做特征工程")
@pytest.mark.parametrize("processed_dir", ["Hiranniramol", "Labuhn"])
def test_each_external_dataset_is_sequence_only(processed_dir):
    sys.path.insert(0, str(REPO_ROOT))
    from core.data.splitting.cell_line_division import load_feature_schema

    schema = load_feature_schema(str(REPO_ROOT / "data/processed" / processed_dir))
    assert schema["channel_count"] == 4
    assert schema["feature_count"] == 92
    assert schema["channel_names"] == ["A", "C", "G", "T"]
    assert schema["sequence_length"] == 23


def test_deepcrispr_dataset_is_8_channel():
    """回归：DeepCRISPR 仍是 8 通道 / 184 维。"""
    sys.path.insert(0, str(REPO_ROOT))
    from core.data.splitting.cell_line_division import load_feature_schema

    schema = load_feature_schema(str(DEEPCRISPR_PROCESSED))
    assert schema["channel_count"] == 8 and schema["feature_count"] == 184


@pytest.mark.skipif(not HIRAN_PROCESSED.exists(), reason="Hiranniramol 尚未做特征工程")
@pytest.mark.parametrize("processed_dir,expect", [
    ("Hiranniramol", ["hiranniramol"]),
    ("Labuhn", ["labuhn"]),
    ("DeepCRISPR", ["hct116", "hek293t", "hela", "hl60"]),
])
def test_processed_datasets_load_with_expected_shapes(processed_dir, expect):
    sys.path.insert(0, str(REPO_ROOT))
    from core.data.splitting.cell_line_division import (
        discover_available_cell_lines, load_cell_line, load_feature_schema,
    )

    base = REPO_ROOT / "data/processed" / processed_dir
    schema = load_feature_schema(str(base))
    cells = discover_available_cell_lines(str(base))
    assert cells == expect

    n_ch = schema["channel_count"]
    n_ft = schema["feature_count"]
    for cell in cells:
        ds = load_cell_line(str(base), cell, schema)
        n = len(ds["y"])
        assert ds["X_3d"].shape == (n, 23, n_ch)
        assert ds["X_2d"].shape == (n, n_ft)
        assert np.isfinite(ds["y"]).all()
        assert float(ds["y"].min()) >= 0.0 and float(ds["y"].max()) <= 1.0
        # 序列通道应当是 one-hot（前 4 个通道每行和为 1）
        assert np.allclose(ds["X_3d"][:, :, :4].sum(axis=2), 1.0)


@pytest.mark.skipif(not HIRAN_PROCESSED.exists(), reason="Hiranniramol 尚未做特征工程")


def test_sequence_only_schema_yields_single_environment():
    """0 个表观通道时不应额外产出与 sequence 等价的 "all"。"""
    sys.path.insert(0, str(REPO_ROOT))
    from core.features.channels.cell_environment_combination import generate_combination_names

    schema = {"sequence_length": 23, "channel_count": 4, "feature_count": 92,
              "channel_names": ["A", "C", "G", "T"],
              "sequence_channels": ["A", "C", "G", "T"]}
    assert generate_combination_names(schema, include_all=True,
                                      include_sequence=True, sizes=[0, 1, 2, 3]) == ["sequence"]


def test_deepcrispr_schema_still_yields_16_environments():
    """回归：8 通道 schema 仍应展开 16 种组合。"""
    sys.path.insert(0, str(REPO_ROOT))
    from core.features.channels.cell_environment_combination import generate_combination_names

    schema = {"sequence_length": 23, "channel_count": 8, "feature_count": 184,
              "channel_names": ["A", "C", "G", "T", "CTCF", "Dnase", "H3K4me3", "RRBS"],
              "sequence_channels": ["A", "C", "G", "T"]}
    combos = generate_combination_names(schema, include_all=True,
                                        include_sequence=True, sizes=[0, 1, 2, 3])
    assert len(combos) == 16
    assert combos[0] == "sequence" and "all" in combos


# --------------------------------------------------------------------------- #
# 3. 不再有 DeepCRISPR 隐式默认
# --------------------------------------------------------------------------- #
def test_missing_schema_raises_instead_of_writing_deepcrispr_default(tmp_path):
    sys.path.insert(0, str(REPO_ROOT))
    from core.data.splitting.cell_line_division import load_feature_schema

    empty = tmp_path / "empty_data"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="找不到特征 schema"):
        load_feature_schema(str(empty))
    # 关键：不能顺手写一份 8 通道 schema 进去
    assert not (empty / "feature_schema.json").exists()


def test_empty_data_dir_raises_instead_of_falling_back_to_four_cell_lines(tmp_path):
    sys.path.insert(0, str(REPO_ROOT))
    from core.data.splitting.cell_line_division import discover_available_cell_lines

    empty = tmp_path / "empty_data"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="没有发现任何细胞系"):
        discover_available_cell_lines(str(empty))


def test_resolve_dataset_is_case_insensitive_and_lists_alternatives():
    """--data-set 的名称解析：大小写不敏感、失败时列出可用数据集、不回退默认。"""
    sys.path.insert(0, str(REPO_ROOT))
    from core.common.paths import available_datasets, resolve_dataset

    names = available_datasets()
    assert {"DeepCRISPR", "Hiranniramol", "Labuhn"} <= set(names)

    for spelling in ("Hiranniramol", "hiranniramol", "HIRANNI RAMOL".replace(" ", "")):
        assert resolve_dataset(spelling).name == "Hiranniramol"

    with pytest.raises(FileNotFoundError) as exc:
        resolve_dataset("NoSuchDataset")
    msg = str(exc.value)
    assert "可用数据集" in msg and "DeepCRISPR" in msg


def test_resolve_data_dir_requires_exactly_one_of_set_or_dir():
    """--data-set 与 --data-dir 必须二选一；都不给要报错而不是用默认数据集。"""
    sys.path.insert(0, str(REPO_ROOT))
    from core.common.paths import resolve_data_dir

    assert resolve_data_dir(None, "Labuhn").name == "Labuhn"
    assert resolve_data_dir(str(LABUHN_PROCESSED), None).name == "Labuhn"

    with pytest.raises(ValueError, match="必须指定要跑的数据集"):
        resolve_data_dir(None, None)
    with pytest.raises(ValueError, match="只能给一个"):
        resolve_data_dir(str(LABUHN_PROCESSED), "Labuhn")


def test_processed_layout_mirrors_raw_layout():
    """data/processed/<Dataset> 与 data/raw/<Dataset> 一一对应。"""
    raw = {d.name for d in (REPO_ROOT / "data/raw").iterdir() if d.is_dir()}
    proc = {d.name for d in (REPO_ROOT / "data/processed").iterdir() if d.is_dir()}
    assert raw == proc, f"raw={sorted(raw)} processed={sorted(proc)}"


def test_feature_engineering_requires_all_three_paths():
    """--raw-data / --output-dir / --config 都必须显式给出（无默认值）。"""
    base = [sys.executable, str(FE_SCRIPT)]
    for args, missing in [
        (["--output-dir", "/tmp/x", "--config", "c.json"], "--raw-data"),
        (["--raw-data", "/tmp/x", "--config", "c.json"], "--output-dir"),
        (["--raw-data", "/tmp/x", "--output-dir", "/tmp/y"], "--config"),
    ]:
        proc = subprocess.run(base + args, capture_output=True, text=True)
        assert proc.returncode != 0
        assert missing in proc.stderr


def test_feature_engineering_rejects_nonexistent_raw_data(tmp_path):
    """指向不存在的原始路径必须立即失败，而不是回退到某个默认目录。"""
    proc = subprocess.run([
        sys.executable, str(FE_SCRIPT),
        "--raw-data", str(tmp_path / "does_not_exist"),
        "--output-dir", str(tmp_path / "out"),
        "--config", str(REPO_ROOT / "data/metadata/feature_config_sequence_only.json"),
    ], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "--raw-data 不存在" in proc.stderr
    # 不应写出任何东西
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


def test_data_digging_requires_data_dir():
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "workflows/training/data_digging.py"), "--dry-run"],
        capture_output=True, text=True)
    assert proc.returncode != 0
    assert "--data-dir" in proc.stderr


def test_run_sh_requires_data_dir():
    script = REPO_ROOT / "workflows/training/run.sh"
    if not script.exists():
        pytest.skip("run.sh 不存在")
    proc = subprocess.run(["bash", str(script), "single"],
                          capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert proc.returncode != 0
    assert "DATA_DIR" in (proc.stdout + proc.stderr)


def test_no_hardcoded_cell_line_choices_left_in_clis():
    """训练/预测 CLI 不应再把细胞系限定为 DeepCRISPR 的 4 个。"""
    for rel in ("workflows/training/data_digging.py",
                "workflows/prediction/predict.py",
                "workflows/design/design.py"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert 'choices=["hct116"' not in text, f"{rel} 仍有细胞系白名单"
        assert "CELL_LINES = [" not in text, f"{rel} 仍有硬编码细胞系常量"
