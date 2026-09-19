"""schema ↔ feature tensor 一致性测试。

这一层保护的是**最危险的一类 bug**：``feature_schema.json`` 声明一种编码，
而实际张量按另一种编码构造（例如 schema 写 A/C/G/T 而代码用 G/C/A/T，或环境通道
顺序不一致）。这类 silent mismatch 不会让训练报错，只会让模型在错误的通道上学习，
因此必须由断言拦截，而不是靠人读代码。

实现方式：直接复用用户级校验器
``core/features/engineering/validate_feature_schema.py``，保证"用户跑的命令"与
"CI 跑的检查"是同一份逻辑——避免两套实现漂移。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.common.paths import available_datasets, resolve_dataset  # noqa: E402
from core.features.engineering.validate_feature_schema import (  # noqa: E402
    Checker,
    validate_dataset,
)

DATASETS = available_datasets()


def _schema(data_dir: Path) -> dict:
    return json.loads((data_dir / "feature_schema.json").read_text(encoding="utf-8"))


def test_at_least_one_processed_dataset_exists() -> None:
    """没有任何已处理数据集时，整个项目无法运行——必须显式失败而不是静默跳过。"""
    assert DATASETS, (
        "data/processed 下没有已处理数据集（缺 feature_schema.json）。"
        "请先运行 §6 预处理命令。"
    )


@pytest.mark.parametrize("name", DATASETS)
def test_schema_matches_tensor(name: str) -> None:
    """对每个数据集跑完整的 schema↔tensor 校验，任何失败项都要报出来。"""
    chk = Checker()
    validate_dataset(resolve_dataset(name), chk)
    assert chk.good, f"{name} schema 与实际张量不一致：\n  " + "\n  ".join(chk.failed)


@pytest.mark.parametrize("name", DATASETS)
def test_schema_declares_encoding_v2(name: str) -> None:
    """schema v2 的声明块必须齐备——用户靠它们确定编码，不必读源码。"""
    s = _schema(resolve_dataset(name))
    assert s.get("schema_version", 1) >= 2, (
        f"{name}: schema_version < 2，缺少 encoding/layout/sequence_definition 等声明块；"
        "请重跑特征工程"
    )
    for block in ("encoding", "layout", "sequence_definition",
                  "normalization", "model_compatibility", "source"):
        assert block in s, f"{name}: schema 缺少声明块 {block}"

    seq = s["encoding"]["sequence"]
    assert seq["encoding"] == "one_hot"
    assert seq["unknown_base_policy"] == "error", (
        "未知碱基必须报错而不是静默置零"
    )
    assert s["layout"]["position_indexing"] == "1-based"
    assert s["layout"]["flatten_order"] == "position_major"
    assert s["sequence_definition"]["pam_included_in_tensor"] is True
    assert s["normalization"]["applied_in_tensor"] is False


@pytest.mark.parametrize("name", DATASETS)
def test_channel_names_match_environment_declaration(name: str) -> None:
    """channel_names 的环境段必须与 environment_features 的声明顺序逐一对应。"""
    s = _schema(resolve_dataset(name))
    n_seq = len(s["sequence_channels"])
    declared_env = s["channel_names"][n_seq:]
    expect_env = [f["name"] for f in s.get("environment_features", [])]
    assert declared_env == expect_env, (
        f"{name}: channel_names 环境段 {declared_env} != environment_features "
        f"声明顺序 {expect_env}（silent channel mismatch）"
    )


@pytest.mark.parametrize("name", DATASETS)
def test_linear_dim_declaration_is_consistent(name: str) -> None:
    """线性模型剔除 *_T 后的维度声明必须等于 feature_count - sequence_length。"""
    s = _schema(resolve_dataset(name))
    expected = int(s["feature_count"]) - int(s["sequence_length"])
    got = s["model_compatibility"]["linear"]["input_dim"]
    assert got == expected, (
        f"{name}: linear.input_dim 声明 {got} != {s['feature_count']} - "
        f"{s['sequence_length']} = {expected}"
    )


def test_sequence_length_constant_is_single_valued() -> None:
    """SEQUENCE_LENGTH 在仓库中有多处定义，必须保持一致（否则 schema 会与实际脱节）。"""
    from core.features.engineering.dataset_adapters import SEQUENCE_LENGTH as A
    from core.features.engineering.feature_engineering import SEQUENCE_LENGTH as B

    assert A == B, f"SEQUENCE_LENGTH 定义不一致：dataset_adapters={A}, feature_engineering={B}"

    # 已处理数据集的 schema 也必须与常量一致
    for name in DATASETS:
        s = _schema(resolve_dataset(name))
        assert int(s["sequence_length"]) == A, (
            f"{name}: schema.sequence_length={s['sequence_length']} != 常量 {A}"
        )


def test_default_sequence_channels_consistent() -> None:
    """DEFAULT_SEQUENCE_CHANNELS 同样有多处定义，必须一致且与 schema 的序列段一致。"""
    from core.features.channels.cell_environment_combination import (
        DEFAULT_SEQUENCE_CHANNELS as A,
    )
    from core.features.engineering.feature_engineering import (
        DEFAULT_SEQUENCE_CHANNELS as B,
    )

    assert A == B, f"DEFAULT_SEQUENCE_CHANNELS 定义不一致：{A} vs {B}"
    for name in DATASETS:
        s = _schema(resolve_dataset(name))
        n_seq = len(s["sequence_channels"])
        assert s["channel_names"][:n_seq] == list(A)[:n_seq], (
            f"{name}: schema 序列段 {s['channel_names'][:n_seq]} != 常量 {A}"
        )
