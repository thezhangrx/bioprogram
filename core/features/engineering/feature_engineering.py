# feature_engineering.py

"""
CRISPR-Cas9 sgRNA + Cell Environment
Config-driven Feature Engineering
==================================

核心思想
--------

本模块不再把 environment feature 写死在 Python 代码中。

所有环境变量均由 JSON 配置文件定义。

例如：

    CTCF
    Dnase
    H3K4me3
    RRBS

以后可以直接在 JSON 中增加：

    NHEJScore
    HRScore
    CellCycleScore
    DDRScore
    TargetExpression
    ...

无需修改本文件核心逻辑。

------------------------------------------------------------
支持的 environment 类型
------------------------------------------------------------

1. per_position_binary

    每个样本有一个23字符字符串：

        AAAAAANNNAA...

    通过 encoding 映射为：

        1 / 0

    适合：

        CTCF
        Dnase
        H3K4me3
        RRBS

------------------------------------------------------------

2. per_position_numeric

    每个样本有23个位置的连续数值。

    支持输入：

        [0.1,0.2,...]
        "0.1,0.2,..."

    输出：

        23 × 1

------------------------------------------------------------

3. global_numeric

    每个 cell line / sample 一个连续数值。

    例如：

        NHEJScore
        CellCycleScore
        DDRScore

    为了兼容 CNN / Transformer：

        一个 global scalar
            ↓
        broadcast 到 23 个 position

    因此：

        1 × 1
            ↓
        23 × 1

------------------------------------------------------------
输出
------------------------------------------------------------

data/processed/<数据集>/     # 按数据集分层，与 data/raw/>数据集>/ 一一对应

    hct116_23x8.csv              # 当前总 channel = 8 (A/C/G/T + 4 表观)
    hct116_23x8.npy

    hct116_184.csv               # 当前总维度 = 184 = 23 × 8
    hct116_184.npy

    hct116_features_23x8.npy

    hct116_features_184.npy

    hct116_labels.npy

    hct116_metadata.csv

    feature_schema.json

实际维度由配置自动决定，不再写死。
"""


import argparse
import glob
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --- 项目根引导: 保证从任意工作目录运行/被导入都能解析 core、analysis、workflows ---
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.features.engineering.dataset_adapters import (  # noqa: E402
    ADAPTERS as DATASET_ADAPTERS,
    detect_format,
    load_and_adapt,
)


# ============================================================
# 1. Global configuration
# ============================================================

SEQUENCE_LENGTH = 23

TARGET_COLUMN = "Normalized efficacy"

METADATA_COLUMNS = [
    "Cell line",
    "Chromosome",
    "Start",
    "End",
    "Strand",
    "sgRNA",
]

# 序列通道: 完整 4 碱基 One-Hot [A, C, G, T]
# (总通道 = 4 序列 + N 表观; 完整数据 23x8, 展平 184)
DEFAULT_SEQUENCE_CHANNELS = [
    "A",
    "C",
    "G",
    "T",
]


# ============================================================
# 2. Configuration loading
# ============================================================

def load_feature_config(config_file):
    """
    读取 feature configuration JSON。

    JSON 负责定义：

        environment features
        input columns
        encoding
        feature type

    返回：
        config : dict
    """

    if not os.path.exists(config_file):
        raise FileNotFoundError(
            f"找不到 feature config：{config_file}"
        )

    with open(
        config_file,
        "r",
        encoding="utf-8"
    ) as f:

        config = json.load(f)

    if not isinstance(config, dict):
        raise ValueError(
            "feature config 必须是 JSON object。"
        )

    if "environment_features" not in config:
        raise ValueError(
            "feature config 缺少 "
            "'environment_features'。"
        )

    if not isinstance(
        config["environment_features"],
        list
    ):
        raise ValueError(
            "'environment_features' 必须是 list。"
        )

    validate_feature_config(config)

    return config


# ============================================================
# 3. Validate feature configuration
# ============================================================

def validate_feature_config(config):
    """
    检查 feature config 是否合法。
    """

    seen_names = set()

    for index, spec in enumerate(
        config["environment_features"]
    ):

        if not isinstance(spec, dict):
            raise ValueError(
                f"environment_features[{index}] "
                "必须是 object。"
            )

        required_keys = [
            "name",
            "column",
            "type",
        ]

        for key in required_keys:

            if key not in spec:
                raise ValueError(
                    f"第 {index} 个环境特征缺少："
                    f"{key}"
                )

        name = spec["name"]

        if name in seen_names:
            raise ValueError(
                f"环境特征名称重复：{name}"
            )

        seen_names.add(name)

        feature_type = spec["type"]

        allowed_types = {
            "per_position_binary",
            "per_position_numeric",
            "global_numeric",
        }

        if feature_type not in allowed_types:
            raise ValueError(
                f"环境特征 {name} 的 type 非法："
                f"{feature_type}\n"
                f"允许：{allowed_types}"
            )

        if feature_type == (
            "per_position_binary"
        ):

            if "encoding" not in spec:
                raise ValueError(
                    f"{name} 是 "
                    "per_position_binary，"
                    "必须提供 encoding。"
                )

            if not isinstance(
                spec["encoding"],
                dict
            ):
                raise ValueError(
                    f"{name}.encoding 必须是 object。"
                )

        if "enabled" in spec:

            if not isinstance(
                spec["enabled"],
                bool
            ):
                raise ValueError(
                    f"{name}.enabled 必须是 bool。"
                )


# ============================================================
# 4. Enabled environment features
# ============================================================

def get_enabled_environment_features(
    config
):
    """
    获取当前启用的 environment features。
    """

    features = []

    for spec in config[
        "environment_features"
    ]:

        enabled = spec.get(
            "enabled",
            True
        )

        if enabled:
            features.append(spec)

    return features


# ============================================================
# 5. Sequence encoding
# ============================================================

def validate_sequence(
    sequence,
    name="sequence"
):
    """
    检查序列长度是否为23。
    """

    sequence = (
        str(sequence)
        .strip()
        .upper()
    )

    if len(sequence) != SEQUENCE_LENGTH:

        raise ValueError(
            f"{name} 长度错误："
            f"'{sequence}'，"
            f"长度={len(sequence)}，"
            f"要求={SEQUENCE_LENGTH}。"
        )

    return sequence


def encode_sgrna(
    sgrna,
    sequence_channels=None
):
    """
    23nt sgRNA -> 23 × number_of_sequence_channels

    默认 (完整 4 碱基 One-Hot, 通道顺序与 sequence_channels 一致)：

        A -> [1,0,0,0]
        C -> [0,1,0,0]
        G -> [0,0,1,0]
        T -> [0,0,0,1]

    注意：
        线性回归侧通过剔除 _T 参照列 (哑变量陷阱防护) 以 T 为基准对照,
        但特征张量本身始终保留 T 通道 (树/深度模型使用完整 184 维)。
    """

    if sequence_channels is None:

        sequence_channels = (
            DEFAULT_SEQUENCE_CHANNELS
        )

    sgrna = validate_sequence(
        sgrna,
        name="sgRNA"
    )

    channel_count = len(
        sequence_channels
    )

    channel_to_index = {
        channel: index
        for index, channel
        in enumerate(sequence_channels)
    }

    encoded = np.zeros(
        (
            SEQUENCE_LENGTH,
            channel_count
        ),
        dtype=np.float32
    )

    for position, base in enumerate(
        sgrna
    ):

        # 4 碱基 One-Hot: A/C/G/T 各有专属通道 (T 不再隐式参照)
        if base not in channel_to_index:

            raise ValueError(
                f"sgRNA 第 {position + 1} 位出现"
                f"无法编码的碱基：'{base}'。"
                f"当前 sequence channels："
                f"{sequence_channels}"
            )

        channel_index = (
            channel_to_index[base]
        )

        encoded[
            position,
            channel_index
        ] = 1.0

    return encoded


# ============================================================
# 6. Per-position binary environment
# ============================================================

def encode_per_position_binary(
    sequence,
    feature_name,
    encoding
):
    """
    将23字符环境轨道编码为23×1。

    例如：

        A/N

    config：

        "A": 1,
        "N": 0
    """

    sequence = validate_sequence(
        sequence,
        name=feature_name
    )

    encoded = np.zeros(
        (
            SEQUENCE_LENGTH,
            1
        ),
        dtype=np.float32
    )

    for position, value in enumerate(
        sequence
    ):

        if value not in encoding:

            raise ValueError(
                f"{feature_name} "
                f"第 {position + 1} 位出现"
                f"无法编码的值：'{value}'。"
                f"允许：{list(encoding.keys())}"
            )

        encoded[
            position,
            0
        ] = float(
            encoding[value]
        )

    return encoded


# ============================================================
# 7. Parse 23 numeric values
# ============================================================

def parse_position_numeric_values(
    value,
    feature_name
):
    """
    解析23个 position-specific numeric values。

    支持：

        list
        tuple
        numpy array

    或字符串：

        "0.1,0.2,0.3,..."

    以及：

        "[0.1, 0.2, 0.3, ...]"
    """

    # --------------------------------------------------------
    # Already array-like
    # --------------------------------------------------------

    if isinstance(
        value,
        (
            list,
            tuple,
            np.ndarray
        )
    ):

        values = list(value)

    else:

        text = str(value).strip()

        # ----------------------------------------------------
        # Try JSON array
        # ----------------------------------------------------

        if (
            text.startswith("[")
            and text.endswith("]")
        ):

            try:

                values = json.loads(
                    text
                )

            except json.JSONDecodeError as error:

                raise ValueError(
                    f"{feature_name} 无法解析："
                    f"{text}"
                ) from error

        else:

            # ------------------------------------------------
            # Comma-separated
            # ------------------------------------------------

            values = [
                item.strip()
                for item in text.split(",")
            ]

    if len(values) != (
        SEQUENCE_LENGTH
    ):

        raise ValueError(
            f"{feature_name} 必须包含"
            f"{SEQUENCE_LENGTH} 个数值，"
            f"实际={len(values)}。"
        )

    try:

        numeric_values = np.asarray(
            values,
            dtype=np.float32
        )

    except ValueError as error:

        raise ValueError(
            f"{feature_name} 存在无法转换为"
            "float 的值："
            f"{values}"
        ) from error

    if not np.isfinite(
        numeric_values
    ).all():

        raise ValueError(
            f"{feature_name} 中存在 NaN 或 Inf。"
        )

    return numeric_values


# ============================================================
# 8. Per-position numeric environment
# ============================================================

def encode_per_position_numeric(
    value,
    feature_name
):
    """
    23个连续数值 -> 23×1。
    """

    numeric_values = (
        parse_position_numeric_values(
            value,
            feature_name
        )
    )

    return numeric_values.reshape(
        SEQUENCE_LENGTH,
        1
    )


# ============================================================
# 9. Global numeric environment
# ============================================================

def encode_global_numeric(
    value,
    feature_name
):
    """
    一个 global scalar -> 23×1。

    为兼容：

        CNN
        Transformer

    将 cell-level scalar broadcast
    到23个 position。

    例如：

        NHEJScore = 0.72

    变成：

        [0.72]
        [0.72]
        ...
        [0.72]
    """

    try:

        scalar = float(value)

    except (
        TypeError,
        ValueError
    ) as error:

        raise ValueError(
            f"{feature_name} "
            f"无法转换为 numeric："
            f"{value}"
        ) from error

    if not np.isfinite(
        scalar
    ):

        raise ValueError(
            f"{feature_name} "
            "存在 NaN 或 Inf。"
        )

    return np.full(
        (
            SEQUENCE_LENGTH,
            1
        ),
        scalar,
        dtype=np.float32
    )


# ============================================================
# 10. Encode one environment feature
# ============================================================

def encode_environment_feature(
    row,
    spec
):
    """
    根据 configuration 编码单个 environment feature。
    """

    name = spec["name"]
    column = spec["column"]
    feature_type = spec["type"]

    if column not in row.index:

        raise ValueError(
            f"环境特征 {name} "
            f"对应的原始列不存在：{column}"
        )

    value = row[column]

    if feature_type == (
        "per_position_binary"
    ):

        return encode_per_position_binary(
            value,
            feature_name=name,
            encoding=spec["encoding"]
        )

    if feature_type == (
        "per_position_numeric"
    ):

        return encode_per_position_numeric(
            value,
            feature_name=name
        )

    if feature_type == (
        "global_numeric"
    ):

        return encode_global_numeric(
            value,
            feature_name=name
        )

    raise RuntimeError(
        f"未处理的 environment type："
        f"{feature_type}"
    )


# ============================================================
# 11. Build channel schema
# ============================================================

def get_channel_specs(
    config
):
    """
    返回最终所有 channels 的定义。

    第一部分：
        sequence channels

    第二部分：
        enabled environment features
    """

    sequence_channels = config.get(
        "sequence_channels",
        DEFAULT_SEQUENCE_CHANNELS
    )

    if not isinstance(
        sequence_channels,
        list
    ):

        raise ValueError(
            "sequence_channels 必须是 list。"
        )

    channel_specs = []

    for channel in sequence_channels:

        channel_specs.append({
            "name": channel,
            "source": "sequence",
            "type": "sequence"
        })

    for spec in (
        get_enabled_environment_features(
            config
        )
    ):

        channel_specs.append({
            "name": spec["name"],
            "source": spec["column"],
            "type": spec["type"]
        })

    return channel_specs


# ============================================================
# 12. Build one feature matrix
# ============================================================

def build_feature_matrix(
    row,
    config
):
    """
    一条样本：

        23 × number_of_channels

    例如当前：

        23 × 7

    增加3个 global features 后：

        23 × 10

    所有 dimensions 都由 config 决定。
    """

    # --------------------------------------------------------
    # Sequence
    # --------------------------------------------------------

    sequence_channels = config.get(
        "sequence_channels",
        DEFAULT_SEQUENCE_CHANNELS
    )

    sequence_features = encode_sgrna(
        row["sgRNA"],
        sequence_channels=sequence_channels
    )

    matrices = [
        sequence_features
    ]

    # --------------------------------------------------------
    # Environment
    # --------------------------------------------------------

    for spec in (
        get_enabled_environment_features(
            config
        )
    ):

        feature = encode_environment_feature(
            row,
            spec
        )

        if feature.shape != (
            SEQUENCE_LENGTH,
            1
        ):

            raise RuntimeError(
                f"环境特征 {spec['name']} "
                f"输出形状错误："
                f"{feature.shape}"
            )

        matrices.append(
            feature
        )

    # --------------------------------------------------------
    # Concatenate
    # --------------------------------------------------------

    matrix = np.concatenate(
        matrices,
        axis=1
    )

    expected_channels = (
        len(sequence_channels)
        + len(
            get_enabled_environment_features(
                config
            )
        )
    )

    expected_shape = (
        SEQUENCE_LENGTH,
        expected_channels
    )

    if matrix.shape != expected_shape:

        raise RuntimeError(
            f"特征矩阵维度错误："
            f"{matrix.shape}，"
            f"预期={expected_shape}。"
        )

    return matrix


# ============================================================
# 13. Generate feature names
# ============================================================

def generate_vector_feature_names(
    config
):
    """
    根据 config 动态生成：

        pos1_A
        pos1_G
        pos1_C
        pos1_CTCF
        ...

    不再写死 161。
    """

    channel_specs = get_channel_specs(
        config
    )

    names = []

    for position in range(
        1,
        SEQUENCE_LENGTH + 1
    ):

        for channel in channel_specs:

            names.append(
                f"pos{position}_{channel['name']}"
            )

    return names


# ============================================================
# 14. Feature schema
# ============================================================

def generate_feature_schema(
    config
):
    """
    生成完整 feature schema。

    方便后续：

        ML
        analysis
        reproducibility
    """

    sequence_channels = config.get(
        "sequence_channels",
        DEFAULT_SEQUENCE_CHANNELS
    )

    environment_features = (
        get_enabled_environment_features(
            config
        )
    )

    channel_specs = (
        get_channel_specs(
            config
        )
    )

    total_channels = len(
        channel_specs
    )

    total_features = (
        SEQUENCE_LENGTH
        * total_channels
    )

    return {
        "sequence_length":
            SEQUENCE_LENGTH,

        "sequence_channels":
            sequence_channels,

        "environment_features":
            environment_features,

        "channel_count":
            total_channels,

        "feature_count":
            total_features,

        "channel_names":
            [
                channel["name"]
                for channel in channel_specs
            ],

        "feature_names":
            generate_vector_feature_names(
                config
            )
    }


# ============================================================
# 15. Required columns
# ============================================================

def get_metadata_columns(config=None):
    """metadata CSV 要写哪些列。

    默认沿用 DeepCRISPR 时代的列顺序（保证既有 processed 产物逐字节不变）；
    新数据集通过 config 里的 ``metadata_columns`` 声明自己拥有的列，
    例如只有序列的数据集就是 ``["Cell line", "sgRNA"]``。
    实际写入时会自动跳过数据里不存在的列。
    """
    if config and isinstance(config.get("metadata_columns"), list) and config["metadata_columns"]:
        return [str(c) for c in config["metadata_columns"]]
    return list(METADATA_COLUMNS)


def get_required_columns(
    config
):
    """
    根据 config 动态生成 required columns。

    只强制要求**特征工程真正需要**的列：

        sgRNA            —— 序列
        Normalized efficacy —— 标签
        各启用的表观通道列

    基因组坐标（Chromosome/Start/End）与 Strand 不再是必需列：
    只有 DeepCRISPR 提供它们；Hiranniramol/Labuhn 没有坐标，
    强行要求会逼适配器写入假的坐标值。它们存在时仍会写进 metadata。
    """

    columns = [
        "sgRNA",
        TARGET_COLUMN,
    ]

    for spec in (
        get_enabled_environment_features(
            config
        )
    ):

        column = spec["column"]

        if column not in columns:

            columns.append(
                column
            )

    return columns


# ============================================================
# 16. Remove duplicated rows
# ============================================================

def remove_duplicate_rows(
    df
):
    """
    删除完全重复的原始记录。

    只删除整行完全相同的数据。
    """

    original_count = len(
        df
    )

    duplicate_mask = (
        df.duplicated(
            keep="first"
        )
    )

    duplicate_count = int(
        duplicate_mask.sum()
    )

    cleaned_df = (
        df.loc[
            ~duplicate_mask
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )

    cleaned_count = len(
        cleaned_df
    )

    print(
        "\nDuplicate check"
    )

    print(
        "    Original samples :",
        original_count
    )

    print(
        "    Duplicate rows    :",
        duplicate_count
    )

    print(
        "    Cleaned samples   :",
        cleaned_count
    )

    return (
        cleaned_df,
        duplicate_count
    )


# ============================================================
# 17. Load one raw CSV
# ============================================================

def load_source_csv(
    source,
    cell_line,
    config,
    source_file=None
):
    """
    规范化后的 DataFrame -> 可做特征工程的 DataFrame。

    完成：

        1. 列检查
        2. 缺失值检查
        3. 完全重复行删除
        4. 添加 Cell line

    ``source`` 可以是 DataFrame（适配层输出）或 CSV 路径（旧式直接读盘，
    要求该文件本身就是规范格式）。
    """

    if isinstance(source, pd.DataFrame):
        df = source.copy()
        label = source_file or "<DataFrame>"
    else:
        df = pd.read_csv(source)
        label = str(source)

    if df.empty:

        raise ValueError(
            f"数据为空：{label}"
        )

    required_columns = (
        get_required_columns(
            config
        )
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            f"\n文件：{label}\n"
            f"缺少以下必要列：\n"
            +
            "\n".join(
                f"    {column}"
                for column in missing_columns
            )
        )

    # --------------------------------------------------------
    # Missing values
    # --------------------------------------------------------

    if (
        df[
            required_columns
        ]
        .isnull()
        .any()
        .any()
    ):

        missing = (
            df[
                required_columns
            ]
            .isnull()
            .sum()
        )

        missing = missing[
            missing > 0
        ]

        raise ValueError(
            f"\n文件：{label}\n"
            f"存在缺失值：\n"
            f"{missing}"
        )

    # --------------------------------------------------------
    # Duplicate rows
    # --------------------------------------------------------

    (
        df,
        duplicate_count
    ) = remove_duplicate_rows(
        df
    )

    # --------------------------------------------------------
    # Cell line
    # --------------------------------------------------------

    df.insert(
        0,
        "Cell line",
        cell_line
    )

    return (
        df,
        duplicate_count
    )


# ============================================================
# 18. Feature engineering for DataFrame
# ============================================================

def engineer_dataframe(
    df,
    config
):
    """
    DataFrame ->

        features_3d : (N,23,C)
        features_2d : (N,23*C)
        labels      : (N,)
    """

    matrices = []

    for index, row in df.iterrows():

        try:

            matrix = build_feature_matrix(
                row,
                config
            )

        except Exception as error:

            raise ValueError(
                f"处理第 {index + 2} 行失败：\n"
                f"{error}"
            ) from error

        matrices.append(
            matrix
        )

    features_3d = np.asarray(
        matrices,
        dtype=np.float32
    )

    if features_3d.ndim != 3:

        raise RuntimeError(
            "features_3d 维度错误："
            f"{features_3d.shape}"
        )

    channel_count = (
        features_3d.shape[2]
    )

    features_2d = (
        features_3d.reshape(
            len(df),
            SEQUENCE_LENGTH
            * channel_count
        )
    )

    labels = df[
        TARGET_COLUMN
    ].to_numpy(
        dtype=np.float32
    )

    expected_3d_shape = (
        len(df),
        SEQUENCE_LENGTH,
        channel_count
    )

    expected_2d_shape = (
        len(df),
        SEQUENCE_LENGTH
        * channel_count
    )

    if features_3d.shape != (
        expected_3d_shape
    ):

        raise RuntimeError(
            f"23×C 数据维度错误："
            f"{features_3d.shape}"
        )

    if features_2d.shape != (
        expected_2d_shape
    ):

        raise RuntimeError(
            f"2D 数据维度错误："
            f"{features_2d.shape}"
        )

    return (
        features_3d,
        features_2d,
        labels
    )


# ============================================================
# 19. Save matrix CSV
# ============================================================

def save_matrix_csv(
    df,
    features_3d,
    output_file,
    config
):
    """
    保存 metadata + matrix。

    features：

        23 × C
    """

    output_df = _metadata_frame(df, config)

    output_df[
        "features"
    ] = [
        matrix.tolist()
        for matrix in features_3d
    ]

    output_df[
        TARGET_COLUMN
    ] = df[
        TARGET_COLUMN
    ].values

    output_df.to_csv(
        output_file,
        index=False
    )


# ============================================================
# 20. Save vector CSV
# ============================================================

def save_vector_csv(
    df,
    features_2d,
    output_file,
    config
):
    """
    保存 metadata + 动态维度特征。
    """

    feature_names = (
        generate_vector_feature_names(
            config
        )
    )

    if features_2d.shape[1] != len(
        feature_names
    ):

        raise RuntimeError(
            "feature_names 数量与 "
            "features_2d 维度不一致："
            f"{len(feature_names)} "
            f"!= "
            f"{features_2d.shape[1]}"
        )

    feature_df = pd.DataFrame(
        features_2d,
        columns=feature_names
    )

    metadata_df = _metadata_frame(df, config).reset_index(
        drop=True
    )

    output_df = pd.concat(
        [
            metadata_df,
            feature_df
        ],
        axis=1
    )

    output_df[
        TARGET_COLUMN
    ] = df[
        TARGET_COLUMN
    ].values

    output_df.to_csv(
        output_file,
        index=False
    )


# ============================================================
# 21. Save NumPy arrays
# ============================================================

def save_numpy_files(
    features_3d,
    features_2d,
    labels,
    output_dir,
    cell_line
):
    """
    保存动态维度 NumPy arrays。
    """

    channel_count = (
        features_3d.shape[2]
    )

    feature_count = (
        features_2d.shape[1]
    )

    np.save(
        os.path.join(
            output_dir,
            f"{cell_line}_features_23x"
            f"{channel_count}.npy"
        ),
        features_3d
    )

    np.save(
        os.path.join(
            output_dir,
            f"{cell_line}_features_"
            f"{feature_count}.npy"
        ),
        features_2d
    )

    np.save(
        os.path.join(
            output_dir,
            f"{cell_line}_labels.npy"
        ),
        labels
    )


# ============================================================
# 22. Save metadata
# ============================================================

def _metadata_frame(df, config=None):
    """按 config 选出 metadata 列（列顺序与 DeepCRISPR 时代一致）。"""
    columns = [
        column
        for column in get_metadata_columns(config)
        if column in df.columns
    ]
    return df[columns].copy()


def save_metadata(
    df,
    output_file,
    config=None
):
    """
    保存 metadata。

    列由 config 的 ``metadata_columns`` 决定（缺省为 DeepCRISPR 的列顺序），
    只写数据里实际存在的列，再始终附上标签列。
    """

    columns = [
        column
        for column in get_metadata_columns(config)
        if column in df.columns
    ]

    missing_essentials = [
        column
        for column in ("Cell line", "sgRNA")
        if column not in columns
    ]

    if missing_essentials:

        raise ValueError(
            "metadata 缺少必需列："
            f"{missing_essentials}；"
            f"数据现有列：{list(df.columns)}"
        )

    metadata_df = df[
        columns
    ].copy()

    metadata_df[
        TARGET_COLUMN
    ] = df[
        TARGET_COLUMN
    ].values

    metadata_df.to_csv(
        output_file,
        index=False
    )


# ============================================================
# 23. Save feature schema
# ============================================================

def save_feature_schema(
    config,
    output_file
):
    """
    保存 feature schema。

    这是后续复现实验非常重要的文件。
    """

    schema = generate_feature_schema(
        config
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            schema,
            f,
            indent=4,
            ensure_ascii=False
        )


# ============================================================
# 24. Process one CSV
# ============================================================

def process_one_csv(
    csv_file,
    output_dir,
    config,
    source_format=None,
    cell_line=None,
    allow_non_gg_pam=False
):
    """
    处理单个原始 CSV。

    流程：适配层（不同数据集 -> 规范列）→ 列/缺失值校验 → 去重 →
    特征工程 → 落盘。

    ``cell_line`` 缺省时由文件名推导（统一转小写，因为下游
    ``discover_available_cell_lines`` 用 ``<cell>_features_*.npy`` 反推名字）。
    """

    if cell_line is None:
        cell_line = os.path.splitext(
            os.path.basename(
                csv_file
            )
        )[0]

    cell_line = str(cell_line).strip().lower()

    print("\n")
    print("=" * 70)

    print(
        f"Processing: {cell_line}"
    )

    print(
        f"    source  : {csv_file}"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # 适配层：raw -> 规范列
    # --------------------------------------------------------

    (
        adapted,
        adapt_report
    ) = load_and_adapt(
        csv_file,
        source_format,
        allow_non_gg_pam=allow_non_gg_pam
    )

    print(adapt_report.line())

    # --------------------------------------------------------
    # 校验 / 去重 / 加 Cell line
    # --------------------------------------------------------

    (
        df,
        duplicate_count
    ) = load_source_csv(
        adapted,
        cell_line,
        config,
        source_file=csv_file
    )

    print(
        "\nAfter cleaning:"
    )

    print(
        "    Samples:",
        len(df)
    )

    # --------------------------------------------------------
    # Feature engineering
    # --------------------------------------------------------

    (
        features_3d,
        features_2d,
        labels
    ) = engineer_dataframe(
        df,
        config
    )

    channel_count = (
        features_3d.shape[2]
    )

    feature_count = (
        features_2d.shape[1]
    )

    # --------------------------------------------------------
    # Output paths
    # --------------------------------------------------------

    matrix_csv = os.path.join(
        output_dir,
        f"{cell_line}_23x"
        f"{channel_count}.csv"
    )

    vector_csv = os.path.join(
        output_dir,
        f"{cell_line}_{feature_count}.csv"
    )

    metadata_csv = os.path.join(
        output_dir,
        f"{cell_line}_metadata.csv"
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_matrix_csv(
        df,
        features_3d,
        matrix_csv,
        config
    )

    save_vector_csv(
        df,
        features_2d,
        vector_csv,
        config
    )

    save_numpy_files(
        features_3d,
        features_2d,
        labels,
        output_dir,
        cell_line
    )

    save_metadata(
        df,
        metadata_csv,
        config
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print(
        "\nCompleted:"
    )

    print(
        "    Original samples :",
        len(df) + duplicate_count
    )

    print(
        "    Duplicate rows   :",
        duplicate_count
    )

    print(
        "    Final samples    :",
        len(df)
    )

    print(
        "    3D features      :",
        features_3d.shape
    )

    print(
        "    2D features      :",
        features_2d.shape
    )

    print(
        "    labels           :",
        labels.shape
    )

    print(
        "\nOutput:"
    )

    print(
        "   ",
        matrix_csv
    )

    print(
        "   ",
        vector_csv
    )

    print(
        "   ",
        metadata_csv
    )

    return {
        "cell_line":
            cell_line,

        "source_format":
            adapt_report.dataset,

        "source_file":
            os.path.basename(str(csv_file)),

        "rows_in_raw":
            adapt_report.rows_in,

        "rows_dropped_by_adapter":
            adapt_report.n_dropped,

        "adapter_drop_reasons":
            json.dumps(adapt_report.drop_reasons, ensure_ascii=False, sort_keys=True),

        "target_range":
            f"{adapt_report.target_range_out[0]:.6g}~{adapt_report.target_range_out[1]:.6g}",

        "has_epigenetics":
            bool(adapt_report.has_epigenetics),

        "original_samples":
            len(df) + duplicate_count,

        "duplicate_rows":
            duplicate_count,

        "final_samples":
            len(df),

        "channel_count":
            channel_count,

        "feature_count":
            feature_count,
    }


# ============================================================
# 25. Process all CSVs
# ============================================================

def _merge_summary(summary_file, new_df):
    """把本次结果并入已有 summary（同一 cell_line 覆盖，其余保留）。

    多个数据集可以分多次处理进同一个 ``--output-dir``（例如把两个外部数据集
    放进同一个 ``--output-dir``，以便把两个数据集当成两个"细胞系"做 leave-one-dataset-out），
    这时第二次运行不能把第一次的 summary 覆盖掉。
    """
    if not os.path.exists(summary_file) or "cell_line" not in new_df.columns:
        return new_df

    try:
        old = pd.read_csv(summary_file)
    except Exception:
        return new_df

    if "cell_line" not in old.columns or old.empty:
        return new_df

    keep = ~old["cell_line"].astype(str).isin(new_df["cell_line"].astype(str))
    merged = pd.concat([old[keep], new_df], ignore_index=True)

    # 以新表的列为准，保证列顺序一致
    cols = [c for c in new_df.columns if c in merged.columns]
    extra = [c for c in merged.columns if c not in cols]
    return merged[cols + extra]


def discover_raw_files(raw_data):
    """把 ``--raw-data`` 解析成待处理的原始文件列表。

    接受：

    * 单个文件（任意大小写扩展名，含 ``.CSV``）
    * 目录（递归查找 ``*.csv`` / ``*.CSV``，因此 ``data/raw`` 这种
      按数据集分层的目录可以直接传）
    """
    path = Path(raw_data).expanduser()

    if path.is_file():
        return [path]

    if not path.is_dir():
        raise FileNotFoundError(
            f"--raw-data 不存在：{path}\n"
            "  请传入原始数据文件或目录（不再使用任何内置默认路径）。"
        )

    files = sorted(
        p for p in path.rglob("*")
        if p.is_file() and p.suffix.lower() == ".csv"
    )

    if not files:
        raise FileNotFoundError(
            f"目录中没有找到任何 CSV：{path}\n"
            "  请确认原始数据放在该目录下（含子目录）。"
        )

    return files


def _cell_line_for(raw_file, raw_root):
    """由文件名推导 cell line 名（小写）；同名不同目录时报错，避免互相覆盖。"""
    return raw_file.stem.strip().lower()


def process_all_csv(
    raw_data,
    output_dir,
    config,
    source_format=None,
    cell_lines=None,
    allow_non_gg_pam=False
):
    """
    批量处理原始文件（``raw_data`` 可以是文件或目录）。
    """

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Find raw files
    # --------------------------------------------------------

    csv_files = discover_raw_files(raw_data)

    if cell_lines:
        wanted = [str(c).strip().lower() for c in cell_lines]
        by_name = {p.stem.strip().lower(): p for p in csv_files}
        unknown = [c for c in wanted if c not in by_name]
        if unknown:
            raise FileNotFoundError(
                f"--cell-lines 指定的名字没有对应文件：{unknown}\n"
                f"  可用：{sorted(by_name)}"
            )
        csv_files = [by_name[c] for c in wanted]

    stem_counts = {}
    for p in csv_files:
        key = p.stem.strip().lower()
        stem_counts[key] = stem_counts.get(key, 0) + 1
    duplicated = sorted(k for k, v in stem_counts.items() if v > 1)
    if duplicated:
        raise ValueError(
            f"这些文件名（去掉扩展名后）重复，会产生同名输出互相覆盖：{duplicated}\n"
            "  请用 --cell-lines 挑选，或重命名后再处理。"
        )

    print("=" * 70)

    print(
        "CRISPR Feature Engineering"
    )

    print("=" * 70)

    print(
        f"Raw data         : {raw_data}"
    )

    print(
        f"Output directory : {output_dir}"
    )

    print(
        f"CSV files found  : {len(csv_files)}"
    )

    schema = generate_feature_schema(
        config
    )

    print(
        f"Sequence length  : "
        f"{schema['sequence_length']}"
    )

    print(
        f"Channel count    : "
        f"{schema['channel_count']}"
    )

    print(
        f"Feature count    : "
        f"{schema['feature_count']}"
    )

    print(
        "\nChannels:"
    )

    for channel in schema[
        "channel_names"
    ]:

        print(
            "   ",
            channel
        )

    print(
        "\nFiles:"
    )

    for raw_file in csv_files:

        print(
            "   ",
            raw_file
        )

    # --------------------------------------------------------
    # Save schema once
    # --------------------------------------------------------

    schema_file = os.path.join(
        output_dir,
        "feature_schema.json"
    )

    save_feature_schema(
        config,
        schema_file
    )

    # --------------------------------------------------------
    # Process
    # --------------------------------------------------------

    summaries = []

    for raw_file in csv_files:

        cell_line = cell_lines[csv_files.index(raw_file)] if cell_lines else None

        summary = process_one_csv(
            str(raw_file),
            output_dir,
            config,
            source_format=source_format,
            cell_line=cell_line,
            allow_non_gg_pam=allow_non_gg_pam
        )

        summaries.append(
            summary
        )

    # --------------------------------------------------------
    # Global summary
    # --------------------------------------------------------

    run_df = pd.DataFrame(summaries)

    summary_df = _merge_summary(
        os.path.join(output_dir, "feature_engineering_summary.csv"),
        run_df
    )

    summary_file = os.path.join(
        output_dir,
        "feature_engineering_summary.csv"
    )

    summary_df.to_csv(
        summary_file,
        index=False
    )

    print("\n")
    print("=" * 70)

    print(
        "ALL DATASETS PROCESSED"
    )

    print("=" * 70)

    print(
        f"Files processed this run: "
        f"{len(csv_files)}  ({', '.join(run_df['cell_line'].astype(str))})"
    )

    print(
        f"Original samples (this run): "
        f"{run_df['original_samples'].sum()}"
    )

    print(
        f"Duplicate rows removed (this run): "
        f"{run_df['duplicate_rows'].sum()}"
    )

    print(
        f"Final samples (this run): "
        f"{run_df['final_samples'].sum()}"
    )

    if len(summary_df) != len(run_df):

        print(
            f"\n输出目录累计（含既有数据集）: "
            f"{len(summary_df)} 个 cell line / "
            f"{summary_df['final_samples'].sum()} 样本 "
            f"-> {', '.join(summary_df['cell_line'].astype(str))}"
        )

    print(
        f"Channel count: "
        f"{schema['channel_count']}"
    )

    print(
        f"Feature count: "
        f"{schema['feature_count']}"
    )

    print(
        f"\nSchema saved to:\n"
        f"    {schema_file}"
    )

    print(
        f"\nSummary saved to:\n"
        f"    {summary_file}"
    )


# ============================================================
# 26. CLI
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Config-driven feature engineering for CRISPR datasets.\n\n"
            "三个输入路径（--raw-data / --output-dir / --config）都必须显式给出，"
            "不再有指向任何特定数据集的默认值——这样不会误处理、也不会覆盖别的数据集。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  # DeepCRISPR（8 通道，含表观遗传）\n"
            "  python core/features/engineering/feature_engineering.py \\\n"
            "      --raw-data data/raw/DeepCRISPR \\\n"
            "      --output-dir data/processed/DeepCRISPR \\\n"
            "      --config data/metadata/feature_config.json\n\n"
            "  # 外部数据集（4 通道，仅序列）：可多次输出到同一目录以支持 LODO\n"
            "  python core/features/engineering/feature_engineering.py \\\n"
            "      --raw-data data/raw/Hiranniramol/Hiranniramol.CSV \\\n"
            "      --output-dir data/processed/Hiranniramol \\\n"
            "      --config data/metadata/feature_config_sequence_only.json \\\n"
            "      --format hiranniramol\n"
        )
    )

    parser.add_argument(
        "--raw-data",
        "--source-dir",
        dest="raw_data",
        type=str,
        required=True,
        help="原始数据文件或目录（目录会递归查找 *.csv/*.CSV）。必填。"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="处理后数据输出目录。必填，不会被任何默认值覆盖。"
    )

    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="feature configuration JSON。必填。"
             "8 通道用 data/metadata/feature_config.json；"
             "纯序列用 data/metadata/feature_config_sequence_only.json。"
    )

    parser.add_argument(
        "--format",
        type=str,
        default="",
        choices=[""] + sorted(DATASET_ADAPTERS),
        help="原始文件格式；留空则按列名自动识别。"
    )

    parser.add_argument(
        "--cell-lines",
        nargs="+",
        default=None,
        help="只处理这些文件（按文件名去扩展名匹配），顺序即输出顺序。"
    )

    parser.add_argument(
        "--allow-non-gg-pam",
        action="store_true",
        help="允许 PAM 不以 GG 结尾（默认拒绝并在适配层报错）。"
    )

    return parser.parse_args()


# ============================================================
# 27. Main
# ============================================================

def main():

    args = parse_args()

    config = load_feature_config(
        args.config
    )

    process_all_csv(
        raw_data=args.raw_data,
        output_dir=args.output_dir,
        config=config,
        source_format=args.format or None,
        cell_lines=args.cell_lines,
        allow_non_gg_pam=args.allow_non_gg_pam
    )


if __name__ == "__main__":

    main()