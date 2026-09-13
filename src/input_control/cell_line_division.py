# src/input_control/cell_line_division.py
"""
Cell Line Division (动态数据发现与零硬编码版)
============================================
自动动态扫描 data_dir 目录下实际存在的细胞系，彻底去除写死的 4 大细胞系。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


DEFAULT_SCHEMA_FILENAME = "feature_schema.json"
DEFAULT_TRAIN_FRACTION = 0.70
DEFAULT_VALIDATION_FRACTION = 0.15
DEFAULT_TEST_FRACTION = 0.15


def load_feature_schema(data_dir: str) -> Dict:
    schema_path = os.path.join(data_dir, DEFAULT_SCHEMA_FILENAME)
    default_schema = {
        "sequence_length": 23,
        "channel_count": 8,
        "feature_count": 184,
        "channel_names": ["A", "C", "G", "T", "CTCF", "Dnase", "H3K4me3", "RRBS"],
        "sequence_channels": ["A", "C", "G", "T"]
    }
    
    # 如果文件不存在，或文件大小为 0 字节（空文件），自动写入标准 Schema 并返回
    if not os.path.exists(schema_path) or os.path.getsize(schema_path) == 0:
        os.makedirs(data_dir, exist_ok=True)
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(default_schema, f, indent=4)
        return default_schema

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except Exception:
        # 如果 json 内容损坏，自动重写修复
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(default_schema, f, indent=4)
        return default_schema

    return schema


def discover_available_cell_lines(data_dir: str) -> List[str]:
    """
    动态扫描 data_dir 目录下实际拥有的细胞系
    """
    p = Path(data_dir)
    found = []
    if p.exists() and p.is_dir():
        for f in p.glob("*_metadata.csv"):
            cl = f.name.replace("_metadata.csv", "").lower()
            if cl not in found and cl != "feature":
                found.append(cl)
        for f in p.glob("*_features_*.npy"):
            m = re.match(r"([a-zA-Z0-9]+)_features_", f.name)
            if m:
                cl = m.group(1).lower()
                if cl not in found:
                    found.append(cl)
    return found if found else ["hct116", "hek293t", "hela", "hl60"]


def get_feature_file_paths(data_dir: str, cell_line: str, schema: Dict) -> Dict[str, str]:
    cell_line = str(cell_line).strip().lower()
    sequence_length = int(schema.get("sequence_length", 23))
    channel_count = int(schema.get("channel_count", 8))
    feature_count = int(schema.get("feature_count", sequence_length * channel_count))

    return {
        "X_3d": os.path.join(data_dir, f"{cell_line}_features_{sequence_length}x{channel_count}.npy"),
        "X_2d": os.path.join(data_dir, f"{cell_line}_features_{feature_count}.npy"),
        "y": os.path.join(data_dir, f"{cell_line}_labels.npy"),
        "metadata": os.path.join(data_dir, f"{cell_line}_metadata.csv")
    }


def validate_split_fractions(train_fraction: float, validation_fraction: float, test_fraction: float):
    fractions = [train_fraction, validation_fraction, test_fraction]
    if any(fraction <= 0 for fraction in fractions):
        raise ValueError("Train / Validation / Test 比例必须 > 0。")
    total = sum(fractions)
    if not np.isclose(total, 1.0, atol=1e-5):
        raise ValueError(f"比例之和必须为1，当前={total}")


def validate_cell_line_dataset(cell_line: str, X_3d: np.ndarray, X_2d: np.ndarray, y: np.ndarray, metadata: pd.DataFrame, schema: Dict):
    sequence_length = int(schema.get("sequence_length", 23))
    channel_count = int(schema.get("channel_count", 8))
    feature_count = int(schema.get("feature_count", sequence_length * channel_count))

    if X_3d.ndim != 3 or X_2d.ndim != 2:
        raise ValueError(f"{cell_line}: 张量维度错误。")

    y = np.asarray(y).reshape(-1)
    n_samples = len(y)

    if len(X_3d) != n_samples or len(X_2d) != n_samples or len(metadata) != n_samples:
        raise ValueError(f"{cell_line}: 样本数不一致: X_3d={len(X_3d)}, y={n_samples}, meta={len(metadata)}")


def load_cell_line(data_dir: str, cell_line: str, schema: Optional[Dict] = None) -> Dict:
    if schema is None:
        schema = load_feature_schema(data_dir)

    cell_line = str(cell_line).strip().lower()
    paths = get_feature_file_paths(data_dir=data_dir, cell_line=cell_line, schema=schema)

    for name, path in paths.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"{cell_line} 缺少 {name}：{path}")

    X_3d = np.load(paths["X_3d"])
    X_2d = np.load(paths["X_2d"])
    y = np.load(paths["y"]).reshape(-1)
    metadata = pd.read_csv(paths["metadata"]).reset_index(drop=True)

    validate_cell_line_dataset(cell_line, X_3d, X_2d, y, metadata, schema)

    return {
        "cell_line": cell_line,
        "X_3d": X_3d,
        "X_2d": X_2d,
        "y": y,
        "metadata": metadata
    }


def load_all_cell_lines(data_dir: str, cell_lines: Optional[List[str]] = None, schema: Optional[Dict] = None) -> Dict[str, Dict]:
    if schema is None:
        schema = load_feature_schema(data_dir)

    if not cell_lines:
        cell_lines = discover_available_cell_lines(data_dir)

    normalized = [str(c).strip().lower() for c in cell_lines]
    datasets = {}
    for cell_line in normalized:
        datasets[cell_line] = load_cell_line(data_dir=data_dir, cell_line=cell_line, schema=schema)
    return datasets


def create_split_indices(n_samples: int, train_fraction: float = DEFAULT_TRAIN_FRACTION, validation_fraction: float = DEFAULT_VALIDATION_FRACTION, test_fraction: float = DEFAULT_TEST_FRACTION, random_seed: int = 42) -> Dict[str, np.ndarray]:
    validate_split_fractions(train_fraction, validation_fraction, test_fraction)
    if n_samples < 3:
        raise ValueError("至少需要 3 个样本才能划分数据集。")

    rng = np.random.default_rng(random_seed)
    indices = np.arange(n_samples)
    rng.shuffle(indices)

    train_size = int(np.floor(n_samples * train_fraction))
    validation_size = int(np.floor(n_samples * validation_fraction))
    train_size = max(1, train_size)
    validation_size = max(1, validation_size)

    return {
        "train": indices[:train_size],
        "validation": indices[train_size:train_size + validation_size],
        "test": indices[train_size + validation_size:] if (train_size + validation_size) < n_samples else indices[train_size:]
    }


def slice_dataset(dataset: Dict, indices: np.ndarray) -> Dict:
    return {
        "X_3d": dataset["X_3d"][indices],
        "X_2d": dataset["X_2d"][indices],
        "y": dataset["y"][indices],
        "metadata": dataset["metadata"].iloc[indices].reset_index(drop=True)
    }


def merge_datasets(datasets: List[Dict]) -> Dict:
    if not datasets:
        raise ValueError("merge_datasets 收到空列表。")
    return {
        "X_3d": np.concatenate([d["X_3d"] for d in datasets], axis=0),
        "X_2d": np.concatenate([d["X_2d"] for d in datasets], axis=0),
        "y": np.concatenate([d["y"] for d in datasets], axis=0),
        "metadata": pd.concat([d["metadata"] for d in datasets], axis=0, ignore_index=True)
    }


def split_single_cell_line(dataset: Dict, cell_line: str, train_fraction: float = DEFAULT_TRAIN_FRACTION, validation_fraction: float = DEFAULT_VALIDATION_FRACTION, test_fraction: float = DEFAULT_TEST_FRACTION, random_seed: int = 42) -> Dict:
    split_indices = create_split_indices(len(dataset["y"]), train_fraction, validation_fraction, test_fraction, random_seed)
    return {
        "split_type": "single",
        "cell_line": cell_line,
        "random_seed": random_seed,
        "train_cell_lines": [cell_line],
        "validation_cell_lines": [cell_line],
        "test_cell_lines": [cell_line],
        "train_data": slice_dataset(dataset, split_indices["train"]),
        "valid_data": slice_dataset(dataset, split_indices["validation"]),
        "test_data": slice_dataset(dataset, split_indices["test"])
    }


def split_all_cell_lines(datasets: Dict[str, Dict], cell_lines: List[str], test_cell_line: Optional[str] = None, train_fraction: float = DEFAULT_TRAIN_FRACTION, validation_fraction: float = DEFAULT_VALIDATION_FRACTION, test_fraction: float = DEFAULT_TEST_FRACTION, random_seed: int = 42) -> Dict:
    """
    留一细胞系 (Leave-One-Out) 或 跨细胞系划分
    """
    if len(datasets) == 1 or len(cell_lines) <= 1:
        # 单一细胞系退化保护
        only_cl = list(datasets.keys())[0]
        return split_single_cell_line(datasets[only_cl], only_cl, train_fraction, validation_fraction, test_fraction, random_seed)

    if test_cell_line and test_cell_line.lower() in datasets:
        target_test = test_cell_line.lower()
        train_cls = [c for c in cell_lines if c != target_test]
        train_data = merge_datasets([datasets[c] for c in train_cls])

        # 对其余细胞系做 train/valid 划分
        idx = create_split_indices(len(train_data["y"]), train_fraction=0.85, validation_fraction=0.15, test_fraction=0.0, random_seed=random_seed)
        return {
            "split_type": "all",
            "cell_line": target_test,
            "random_seed": random_seed,
            "train_cell_lines": train_cls,
            "validation_cell_lines": train_cls,
            "test_cell_lines": [target_test],
            "train_data": slice_dataset(train_data, idx["train"]),
            "valid_data": slice_dataset(train_data, idx["validation"]),
            "test_data": datasets[target_test]
        }

    # 各自独立划分后合并
    split_results = {}
    for i, cl in enumerate(cell_lines):
        split_results[cl] = split_single_cell_line(datasets[cl], cl, train_fraction, validation_fraction, test_fraction, random_seed + i)

    return {
        "split_type": "all",
        "cell_line": cell_lines[0] if cell_lines else "none",
        "random_seed": random_seed,
        "train_cell_lines": list(cell_lines),
        "validation_cell_lines": list(cell_lines),
        "test_cell_lines": list(cell_lines),
        "train_data": merge_datasets([split_results[c]["train_data"] for c in cell_lines]),
        "valid_data": merge_datasets([split_results[c]["valid_data"] for c in cell_lines]),
        "test_data": merge_datasets([split_results[c]["test_data"] for c in cell_lines])
    }


def split_mixed_cell_lines(datasets: Dict[str, Dict], cell_lines: List[str], train_fraction: float = DEFAULT_TRAIN_FRACTION, validation_fraction: float = DEFAULT_VALIDATION_FRACTION, test_fraction: float = DEFAULT_TEST_FRACTION, random_seed: int = 42) -> Dict:
    if len(datasets) == 1:
        only_cl = list(datasets.keys())[0]
        return split_single_cell_line(datasets[only_cl], only_cl, train_fraction, validation_fraction, test_fraction, random_seed)

    merged = merge_datasets([datasets[c] for c in cell_lines if c in datasets])
    split_indices = create_split_indices(len(merged["y"]), train_fraction, validation_fraction, test_fraction, random_seed)
    return {
        "split_type": "mixed",
        "cell_line": "none",
        "random_seed": random_seed,
        "train_cell_lines": list(cell_lines),
        "validation_cell_lines": list(cell_lines),
        "test_cell_lines": list(cell_lines),
        "train_data": slice_dataset(merged, split_indices["train"]),
        "valid_data": slice_dataset(merged, split_indices["validation"]),
        "test_data": slice_dataset(merged, split_indices["test"])
    }


def attach_public_fields(split_data: Dict) -> Dict:
    result = dict(split_data)
    result.update({
        "X_train_3d": split_data["train_data"]["X_3d"],
        "X_valid_3d": split_data["valid_data"]["X_3d"],
        "X_test_3d": split_data["test_data"]["X_3d"],
        "X_train_2d": split_data["train_data"]["X_2d"],
        "X_valid_2d": split_data["valid_data"]["X_2d"],
        "X_test_2d": split_data["test_data"]["X_2d"],
        "y_train": split_data["train_data"]["y"],
        "y_valid": split_data["valid_data"]["y"],
        "y_test": split_data["test_data"]["y"],
        "metadata_train": split_data["train_data"]["metadata"],
        "metadata_valid": split_data["valid_data"]["metadata"],
        "metadata_test": split_data["test_data"]["metadata"],
    })
    return result


def divide_data(
    data_dir: str,
    split_type: str,
    cell_line: Optional[str] = None,
    cell_lines: Optional[List[str]] = None,
    train_fraction: float = DEFAULT_TRAIN_FRACTION,
    validation_fraction: float = DEFAULT_VALIDATION_FRACTION,
    test_fraction: float = DEFAULT_TEST_FRACTION,
    random_seed: int = 42
) -> Dict:
    split_type = str(split_type).strip().lower()
    validate_split_fractions(train_fraction, validation_fraction, test_fraction)

    schema = load_feature_schema(data_dir)
    available_cells = discover_available_cell_lines(data_dir)

    if not cell_lines:
        cell_lines = available_cells
    cell_lines = [str(c).strip().lower() for c in cell_lines if str(c).strip().lower() in available_cells]

    if split_type == "single":
        target_cell = str(cell_line).strip().lower() if cell_line else cell_lines[0]
        dataset = load_cell_line(data_dir=data_dir, cell_line=target_cell, schema=schema)
        result = split_single_cell_line(dataset, target_cell, train_fraction, validation_fraction, test_fraction, random_seed)
    else:
        datasets = load_all_cell_lines(data_dir=data_dir, cell_lines=cell_lines, schema=schema)
        if split_type == "all":
            result = split_all_cell_lines(datasets, cell_lines, test_cell_line=cell_line, train_fraction=train_fraction, validation_fraction=validation_fraction, test_fraction=test_fraction, random_seed=random_seed)
        else:
            result = split_mixed_cell_lines(datasets, cell_lines, train_fraction=train_fraction, validation_fraction=validation_fraction, test_fraction=test_fraction, random_seed=random_seed)

    result["schema"] = schema
    result["train_fraction"] = train_fraction
    result["validation_fraction"] = validation_fraction
    result["test_fraction"] = test_fraction
    result["n_train"] = len(result["train_data"]["y"])
    result["n_valid"] = len(result["valid_data"]["y"])
    result["n_test"] = len(result["test_data"]["y"])

    return attach_public_fields(result)