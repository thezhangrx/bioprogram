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

data/processed/

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

import numpy as np
import pandas as pd


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

def get_required_columns(
    config
):
    """
    根据 config 动态生成 required columns。
    """

    columns = [
        "Chromosome",
        "Start",
        "End",
        "Strand",
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
    csv_file,
    cell_line,
    config
):
    """
    读取一个 source CSV。

    完成：

        1. 列检查
        2. 缺失值检查
        3. 完全重复行删除
        4. 添加 Cell line
    """

    df = pd.read_csv(
        csv_file
    )

    if df.empty:

        raise ValueError(
            f"文件为空：{csv_file}"
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
            f"\n文件：{csv_file}\n"
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
            f"\n文件：{csv_file}\n"
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

    output_df = df[
        METADATA_COLUMNS
    ].copy()

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

    metadata_df = df[
        METADATA_COLUMNS
    ].reset_index(
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

def save_metadata(
    df,
    output_file
):
    """
    保存 metadata。
    """

    metadata_df = df[
        METADATA_COLUMNS
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
    config
):
    """
    处理单个 cell-line CSV。
    """

    cell_line = os.path.splitext(
        os.path.basename(
            csv_file
        )
    )[0]

    print("\n")
    print("=" * 70)

    print(
        f"Processing: {cell_line}"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    (
        df,
        duplicate_count
    ) = load_source_csv(
        csv_file,
        cell_line,
        config
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
        metadata_csv
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

def process_all_csv(
    source_dir,
    output_dir,
    config
):
    """
    批量处理所有 CSV。
    """

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Find CSV
    # --------------------------------------------------------

    csv_files = sorted(
        glob.glob(
            os.path.join(
                source_dir,
                "*.csv"
            )
        )
    )

    if not csv_files:

        raise FileNotFoundError(
            f"在目录中没有找到 CSV："
            f"{source_dir}"
        )

    print("=" * 70)

    print(
        "CRISPR Feature Engineering"
    )

    print("=" * 70)

    print(
        f"Source directory : {source_dir}"
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

    for csv_file in csv_files:

        print(
            "   ",
            os.path.basename(
                csv_file
            )
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

    for csv_file in csv_files:

        summary = process_one_csv(
            csv_file,
            output_dir,
            config
        )

        summaries.append(
            summary
        )

    # --------------------------------------------------------
    # Global summary
    # --------------------------------------------------------

    summary_df = pd.DataFrame(
        summaries
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
        f"Total CSV files: "
        f"{len(csv_files)}"
    )

    print(
        f"Original samples: "
        f"{summary_df['original_samples'].sum()}"
    )

    print(
        f"Duplicate rows removed: "
        f"{summary_df['duplicate_rows'].sum()}"
    )

    print(
        f"Final samples: "
        f"{summary_df['final_samples'].sum()}"
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
            "Config-driven feature engineering "
            "for CRISPR datasets."
        )
    )

    parser.add_argument(
        "--source-dir",
        type=str,
        default="data/raw",
        help=(
            "原始 CSV 目录。"
        )
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed",
        help=(
            "处理后数据目录。"
        )
    )

    parser.add_argument(
        "--config",
        type=str,
        default=(
            "data/metadata/feature_config.json"
        ),
        help=(
            "feature configuration JSON。"
        )
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
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        config=config
    )


if __name__ == "__main__":

    main()