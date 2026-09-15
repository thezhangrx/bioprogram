# train.py (原 main.py)

"""
CRISPR-Cas9 Editing Efficiency Prediction
=========================================
统一单次实验训练与评估主运行入口 (已对齐参数与透传机制)
"""

from __future__ import annotations


# --- 项目根引导: 保证从任意工作目录运行/被导入都能解析 core、analysis、workflows ---
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import hashlib
import importlib
import inspect
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np


# ============================================================
# 0. Artifact provenance (P2 整改: 每次运行记录数据/代码指纹与划分审计)
# ============================================================

SPLIT_PROVENANCE_KEYS = (
    "group_aware",
    "split_digest",
    "n_train",
    "n_valid",
    "n_test",
    "heldout_sequences_excluded_from_train",
    "audit_train_test_sequence_overlap",
    "audit_train_valid_sequence_overlap",
    "audit_valid_test_sequence_overlap",
    "audit_unique_train_sequences",
    "audit_unique_valid_sequences",
    "audit_unique_test_sequences",
    "audit_train_test_locus_overlap",
    "audit_train_test_revcomp_overlap",
)


def build_data_fingerprint(data_dir: str) -> str:
    """数据指纹: metadata 内容 sha256 + 特征/标签文件大小。

    用于事后证明所有运行使用的是同一份数据 (消除 T1 数据一致性疑虑)。
    """
    root = Path(data_dir)
    digest = hashlib.sha256()
    if not root.exists():
        return "missing"
    for pattern in ("*_metadata.csv", "*_labels.npy", "*_features_*.npy"):
        for path in sorted(root.glob(pattern)):
            digest.update(path.name.encode("utf-8"))
            if pattern.endswith(".csv"):
                digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
            else:
                digest.update(str(path.stat().st_size).encode("ascii"))
    return digest.hexdigest()[:16]


ENV_FINGERPRINT_PACKAGES = ("numpy", "pandas", "scipy", "scikit-learn",
                             "xgboost", "torch", "numba", "joblib")


def build_env_stack() -> str:
    """数值栈本体: Python + 决定 R² 的包版本 (不含设备, 用于全批一致性判定)。"""
    import importlib.metadata as md
    import platform
    parts = [f"py={platform.python_version()}"]
    for name in ENV_FINGERPRINT_PACKAGES:
        try:
            parts.append(f"{name}={md.version(name)}")
        except Exception:
            parts.append(f"{name}=?")
    return "|".join(parts)


def build_env_fingerprint() -> str:
    """完整环境记录 = 数值栈 + 本 run 绑定的可见设备。

    多卡节点上 worker i 会被绑到不同 GPU (cvd 不同) —— 这是**预期**行为,
    因此一致性判定只用 env_stack_id (不含 cvd), cvd 仅作留痕。
    """
    return build_env_stack() + "|cvd=" + os.environ.get("CUDA_VISIBLE_DEVICES", "unset")


def build_code_fingerprint() -> str:
    """代码指纹: 决定划分与训练结果的关键源文件 md5。"""
    digest = hashlib.sha256()
    here = Path(__file__).resolve().parent
    for rel in ("train.py",
                "core/data/splitting/cell_line_division.py",
                "core/features/engineering/feature_engineering.py"):
        path = here / rel
        digest.update(rel.encode("utf-8"))
        if path.exists():
            digest.update(hashlib.md5(path.read_bytes()).hexdigest().encode("ascii"))
        else:
            digest.update(b"missing")
    return digest.hexdigest()[:16]


# ============================================================
# 1. Default configuration
# ============================================================

DEFAULT_DATA_DIR = "data/processed"
DEFAULT_MODEL_DIR = "models/weights"
DEFAULT_RESULTS_DIR = "results/batches"
DEFAULT_LOGS_DIR = "results/logs"
DEFAULT_BATCH_NAME = "default"
DEFAULT_RANDOM_SEED = 42

DEFAULT_TRAIN_RATIO = 0.70
DEFAULT_VALID_RATIO = 0.15
DEFAULT_TEST_RATIO = 0.15

ALL_MODELS = [
    "linear",
    "xgboost",
    "mlp",
    "cnn",
    "transformer",
]

VALID_SPLIT_TYPES = [
    "single",
    "all",
    "mixed",
]


# ============================================================
# 2. Model module mapping
# ============================================================

MODEL_MODULES = {
    "linear": "core.models.linear.linear_regression",
    "linear_regression": "core.models.linear.linear_regression",
    "xgboost": "core.models.xgboost.xgboost",
    "mlp": "core.models.mlp.mlp",
    "cnn": "core.models.cnn.cnn",
    "transformer": "core.models.transformer.transformer",
}


# ============================================================
# 3. Basic utilities
# ============================================================

def sanitize_name(value: str) -> str:
    value = str(value).strip().lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
    if not value:
        raise ValueError("名称不能为空。")
    return value


def sanitize_batch_name(value: str) -> str:
    return sanitize_name(value)


# ============================================================
# 4. Validate paths
# ============================================================

def validate_data_dir(data_dir: str):
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"数据目录不存在：{data_dir}")
    if not os.path.isdir(data_dir):
        raise NotADirectoryError(f"数据路径不是目录：{data_dir}")


def validate_feature_schema(data_dir: str) -> Dict:
    schema_path = os.path.join(data_dir, "feature_schema.json")
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"feature_schema.json 不存在：{schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    required_keys = ["sequence_length", "channel_count", "channel_names"]
    missing = [key for key in required_keys if key not in schema]
    if missing:
        raise ValueError("feature_schema.json 缺少字段：" + ", ".join(missing))

    return schema


# ============================================================
# 5. Model loading
# ============================================================

def load_model_train_function(model: str, model_module: Optional[str] = None):
    model = sanitize_name(model)

    if model_module is None:
        if model not in MODEL_MODULES:
            raise ValueError(f"未知模型：{model}\n允许：{ALL_MODELS}")
        module_path = MODEL_MODULES[model]
    else:
        module_path = model_module

    try:
        module = importlib.import_module(module_path)
    except ImportError as error:
        raise ImportError(f"无法导入模型模块：{module_path}\n原始错误：{error}") from error

    if not hasattr(module, "train"):
        raise AttributeError(f"模块 {module_path} 没有 train() 函数。")

    train_function = getattr(module, "train")
    return train_function, module_path


# ============================================================
# 6. Train interface
# ============================================================

def get_train_signature(train_function: Callable) -> inspect.Signature:
    return inspect.signature(train_function)


def print_train_interface(train_function: Callable, module_path: str):
    signature = get_train_signature(train_function)
    print("\n" + "=" * 80)
    print("Model Train Interface")
    print("=" * 80)
    print(f"Module: {module_path}")
    print(f"train{signature}")
    print("=" * 80)


# ============================================================
# 7. Build run name
# ============================================================

def generate_run_name(model: str, split_type: str, environment: str, cell_line: Optional[str] = None) -> str:
    model = sanitize_name(model)
    split_type = sanitize_name(split_type)
    environment = sanitize_name(environment)

    if split_type == "single":
        prefix = f"single_{cell_line}_{model}_{environment}"
    elif split_type == "all":
        prefix = f"all_{model}_{environment}_heldout_{cell_line}"
    elif split_type == "mixed":
        prefix = f"mixed_{model}_{environment}"
    else:
        raise ValueError(f"未知 split_type：{split_type}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}"


# ============================================================
# 8. Build output directories
# ============================================================

def build_batch_directories(
    batch_name: str,
    model_root_dir: str,
    results_root_dir: str,
    logs_root_dir: str
):
    # 如果 batch_name 为空，直接使用根目录，不加二级子文件夹
    if not batch_name or str(batch_name).strip() in [".", "none", "flat"]:
        os.makedirs(model_root_dir, exist_ok=True)
        os.makedirs(results_root_dir, exist_ok=True)
        os.makedirs(logs_root_dir, exist_ok=True)
        return model_root_dir, results_root_dir, logs_root_dir

    batch_name = sanitize_batch_name(batch_name)
    model_dir = os.path.join(model_root_dir, batch_name)
    results_dir = os.path.join(results_root_dir, batch_name)
    logs_dir = os.path.join(logs_root_dir, batch_name)

    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    return model_dir, results_dir, logs_dir


# ============================================================
# 9. Validate split configuration
# ============================================================

def validate_split_configuration(
    split_type: str,
    cell_line: Optional[str],
    train_ratio: float,
    valid_ratio: float,
    test_ratio: float
):
    split_type = sanitize_name(split_type)

    if split_type not in VALID_SPLIT_TYPES:
        raise ValueError(f"未知 split_type：{split_type}\n允许：{VALID_SPLIT_TYPES}")

    if split_type in {"single", "all"}:
        if cell_line is None:
            pass  # 允许由 cell_lines 列表动态决定

    total = train_ratio + valid_ratio + test_ratio
    if not np.isclose(total, 1.0, atol=1e-8):
        raise ValueError("Train / Validation / Test 比例必须加起来等于 1。")


# ============================================================
# 10. Prepare split data
# ============================================================

def prepare_split_data(
    data_dir: str,
    split_type: str,
    cell_line: Optional[str],
    cell_lines: Optional[List[str]] = None,
    train_ratio: float = 0.70,
    valid_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42
) -> Dict:
    import core.data.splitting.cell_line_division as cld
    return cld.divide_data(
        data_dir=data_dir,
        split_type=split_type,
        cell_line=cell_line,
        cell_lines=cell_lines,
        train_fraction=train_ratio,
        validation_fraction=valid_ratio,
        test_fraction=test_ratio,
        random_seed=random_seed
    )


# ============================================================
# 11. Validate split result
# ============================================================

def validate_split_result(split_data: Dict):
    required = ["X_train_3d", "X_valid_3d", "X_test_3d", "y_train", "y_valid", "y_test"]
    missing = [key for key in required if key not in split_data]
    if missing:
        raise ValueError("cell_line_division.py 返回结果缺少字段：" + ", ".join(missing))

    X_train = np.asarray(split_data["X_train_3d"])
    X_valid = np.asarray(split_data["X_valid_3d"])
    X_test = np.asarray(split_data["X_test_3d"])
    y_train = np.asarray(split_data["y_train"]).reshape(-1)
    y_valid = np.asarray(split_data["y_valid"]).reshape(-1)
    y_test = np.asarray(split_data["y_test"]).reshape(-1)

    if X_train.ndim != 3 or X_valid.ndim != 3 or X_test.ndim != 3:
        raise ValueError("X_3d 必须是 3D 张量。")
    if len(X_train) != len(y_train) or len(X_valid) != len(y_valid) or len(X_test) != len(y_test):
        raise ValueError("样本数不一致。")

    return {
        "X_train_3d": X_train,
        "X_valid_3d": X_valid,
        "X_test_3d": X_test,
        "y_train": y_train,
        "y_valid": y_valid,
        "y_test": y_test,
    }


# ============================================================
# 12. Prepare environment controlled model input
# ============================================================

def prepare_model_data(split_data: Dict, schema: Dict, environment: str, model_name: str) -> Dict:
    module = importlib.import_module("core.features.channels.cell_environment_combination")
    prepare_function = getattr(module, "prepare_train_valid_test")
    return prepare_function(
        split_data=split_data,
        schema=schema,
        combination=environment,
        model_type=model_name,
    )


# ============================================================
# 13. Build feature names
# ============================================================

def build_feature_names(schema: Dict, model_name: str, X_train: np.ndarray) -> List[str]:
    channel_names = list(schema["channel_names"])
    sequence_length = int(schema["sequence_length"])
    model_name = sanitize_name(model_name)

    if X_train.ndim == 2:
        feature_names = []
        for position in range(1, sequence_length + 1):
            for channel in channel_names:
                feature_names.append(f"pos{position}_{channel}")

        if len(feature_names) != X_train.shape[1]:
            feature_names = [f"feature_{index}" for index in range(X_train.shape[1])]

        return feature_names

    return channel_names


# ============================================================
# 14. Validate model shape
# ============================================================

def validate_model_input_shape(model_name: str, X_train: np.ndarray, X_valid: np.ndarray, X_test: np.ndarray):
    model_name = sanitize_name(model_name)
    table_models = {"linear", "linear_regression", "xgboost", "mlp"}
    sequence_models = {"cnn", "transformer"}

    if model_name in table_models:
        expected_dim = 2
    elif model_name in sequence_models:
        expected_dim = 3
    else:
        raise ValueError(f"未知 model：{model_name}")

    for name, array in [("X_train", X_train), ("X_valid", X_valid), ("X_test", X_test)]:
        if array.ndim != expected_dim:
            raise ValueError(f"{model_name} 要求 {expected_dim}D 输入，{name} 实际为 {array.ndim}D：{array.shape}")


# ============================================================
# 15. Build train kwargs
# ============================================================

def build_train_kwargs(
    train_function: Callable,
    X_train,
    y_train,
    X_valid,
    y_valid,
    X_test,
    y_test,
    feature_names,
    run_name,
    model_dir,
    results_dir,
    logs_dir,
    config,
    random_seed,
    use_scaler,
    sequence_kernel: int = 3,
    environment_kernel: int = 3,
    epochs: int = 100,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
    dropout: float = 0.2,
    patience: int = 20,
    min_delta: float = 1e-6,
    hidden_dim1: int = 128,
    hidden_dim2: int = 64,
    conv_channels1: int = 32,
    conv_channels2: int = 64,
    weight_decay: float = 0.0,
    device: Optional[str] = None,
):
    signature = inspect.signature(train_function)
    all_kwargs = {
        "X_train": X_train,
        "y_train": y_train,
        "X_valid": X_valid,
        "y_valid": y_valid,
        "X_test": X_test,
        "y_test": y_test,
        "feature_names": feature_names,
        "run_name": run_name,
        "model_dir": model_dir,
        "model_dir_root": model_dir,
        "result_dir": results_dir,
        "results_dir": results_dir,
        "log_dir": logs_dir,
        "logs_dir": logs_dir,
        "config": config,
        "random_seed": random_seed,
        "seed": random_seed,
        "use_scaler": use_scaler,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "dropout": dropout,
        "patience": patience,
        "min_delta": min_delta,
        "hidden_dim1": hidden_dim1,
        "hidden_dim2": hidden_dim2,
        "conv_channels1": conv_channels1,
        "conv_channels2": conv_channels2,
        "weight_decay": weight_decay,
        "device": device,
        "sequence_kernel": sequence_kernel,
        "environment_kernel": environment_kernel,
        "sequence_kernel_size": sequence_kernel,
        "environment_kernel_size": environment_kernel,
    }

    parameters = signature.parameters
    accepts_kwargs = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    if accepts_kwargs:
        return all_kwargs

    train_kwargs = {key: value for key, value in all_kwargs.items() if key in parameters}
    required_core = ["X_train", "y_train", "X_test", "y_test"]
    missing_core = [key for key in required_core if key not in train_kwargs]
    if missing_core:
        raise TypeError("模型 train() 缺少统一接口参数：" + ", ".join(missing_core))

    return train_kwargs


# ============================================================
# 16. Run one experiment
# ============================================================

def run_one_experiment(
    model_name: str,
    split_type: str,
    cell_line: Optional[str],
    cell_lines: Optional[List[str]],
    environment: str,
    data_dir: str,
    batch_name: str,
    model_dir: str,
    results_dir: str,
    logs_dir: str,
    random_seed: int,
    train_ratio: float,
    valid_ratio: float,
    test_ratio: float,
    use_scaler: bool,
    sequence_kernel: int,
    environment_kernel: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    hidden_dim1: int,
    hidden_dim2: int,
    conv_channels1: int,
    conv_channels2: int,
    dropout: float,
    weight_decay: float,
    patience: int,
    min_delta: float,
    device: Optional[str],
    model_module: Optional[str] = None,
    run_name: Optional[str] = None,
):
    model_name = sanitize_name(model_name)
    split_type = sanitize_name(split_type)
    environment = sanitize_name(environment)

    if run_name is None:
        run_name = generate_run_name(
            model=model_name,
            split_type=split_type,
            environment=environment,
            cell_line=cell_line
        )

    schema = validate_feature_schema(data_dir)
    train_function, module_path = load_model_train_function(model=model_name, model_module=model_module)

    split_data = prepare_split_data(
        data_dir=data_dir,
        split_type=split_type,
        cell_line=cell_line,
        cell_lines=cell_lines,
        train_ratio=train_ratio,
        valid_ratio=valid_ratio,
        test_ratio=test_ratio,
        random_seed=random_seed
    )
    split_data = validate_split_result(split_data) | split_data

    prepared = prepare_model_data(
        split_data=split_data,
        schema=schema,
        environment=environment,
        model_name=model_name
    )

    X_train = prepared["X_train"]
    y_train = prepared["y_train"]
    X_valid = prepared["X_valid"]
    y_valid = prepared["y_valid"]
    X_test = prepared["X_test"]
    y_test = prepared["y_test"]

    validate_model_input_shape(model_name=model_name, X_train=X_train, X_valid=X_valid, X_test=X_test)
    feature_names = build_feature_names(schema=schema, model_name=model_name, X_train=X_train)

    config = {
        "run_name": run_name,
        "model": model_name,
        "model_module": module_path,
        "split_type": split_type,
        "cell_line": cell_line,
        "cell_lines": cell_lines,
        "environment": environment,
        "combination": prepared.get("combination"),
        "selected_environments": prepared.get("selected_environments"),
        "environment_count": prepared.get("environment_count"),
        "random_seed": random_seed,
        "train_ratio": train_ratio,
        "validation_ratio": valid_ratio,
        "test_ratio": test_ratio,
        "sequence_length": schema["sequence_length"],
        "channel_count": schema["channel_count"],
        "channel_names": schema["channel_names"],
        "input_shape_train": list(X_train.shape),
        "input_shape_valid": list(X_valid.shape),
        "input_shape_test": list(X_test.shape),
        "use_scaler": use_scaler,
        "sequence_kernel": sequence_kernel,
        "environment_kernel": environment_kernel,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "hidden_dim1": hidden_dim1,
        "hidden_dim2": hidden_dim2,
        "conv_channels1": conv_channels1,
        "conv_channels2": conv_channels2,
        "dropout": dropout,
        "weight_decay": weight_decay,
        "patience": patience,
        "min_delta": min_delta,
        "data_fingerprint": build_data_fingerprint(data_dir),
        "code_fingerprint": build_code_fingerprint(),
        "env_fingerprint": build_env_fingerprint(),
    }
    config["env_stack_id"] = hashlib.sha256(
        build_env_stack().encode("utf-8")).hexdigest()[:16]

    # 划分审计/溯源自证字段 (全部为标量, 会被写入 *_info.txt 与 *_config.json)
    for key in SPLIT_PROVENANCE_KEYS:
        if key in split_data:
            config[key] = split_data[key]

    train_kwargs = build_train_kwargs(
        train_function=train_function,
        X_train=X_train,
        y_train=y_train,
        X_valid=X_valid,
        y_valid=y_valid,
        X_test=X_test,
        y_test=y_test,
        feature_names=feature_names,
        run_name=run_name,
        model_dir=model_dir,
        results_dir=results_dir,
        logs_dir=logs_dir,
        config=config,
        random_seed=random_seed,
        use_scaler=use_scaler,
        sequence_kernel=sequence_kernel,
        environment_kernel=environment_kernel,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        hidden_dim1=hidden_dim1,
        hidden_dim2=hidden_dim2,
        conv_channels1=conv_channels1,
        conv_channels2=conv_channels2,
        dropout=dropout,
        weight_decay=weight_decay,
        patience=patience,
        min_delta=min_delta,
        device=device,
    )

    result = train_function(**train_kwargs)
    return {"run_name": run_name, "config": config, "result": result}


# ============================================================
# 17. CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="CRISPR-Cas9 single experiment runner (train.py).")

    parser.add_argument("--model", type=str, required=True, choices=ALL_MODELS)
    parser.add_argument("--model-module", type=str, default=None)
    parser.add_argument("--split-type", type=str, required=True, choices=VALID_SPLIT_TYPES)

    # 关键：同时支持 --cell-line (单数) 与 --cell-lines (复数)
    parser.add_argument("--cell-line", type=str, default=None, help="目标单细胞系或留一测试细胞系")
    parser.add_argument("--cell-lines", nargs="+", default=None, help="多细胞系列表")

    parser.add_argument("--environment", type=str, required=True)
    parser.add_argument("--data-dir", type=str, default=DEFAULT_DATA_DIR)
    parser.add_argument("--batch-name", type=str, default=DEFAULT_BATCH_NAME)
    parser.add_argument("--run-name", type=str, default=None)

    parser.add_argument("--model-dir", type=str, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--results-dir", type=str, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--logs-dir", type=str, default=DEFAULT_LOGS_DIR)

    parser.add_argument("--train-ratio", type=float, default=DEFAULT_TRAIN_RATIO)
    parser.add_argument("--valid-ratio", type=float, default=DEFAULT_VALID_RATIO)
    parser.add_argument("--test-ratio", type=float, default=DEFAULT_TEST_RATIO)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument("--use-scaler", action="store_true")

    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--min-delta", type=float, default=1e-6)

    parser.add_argument("--hidden-dim1", type=int, default=128)
    parser.add_argument("--hidden-dim2", type=int, default=64)
    parser.add_argument("--conv-channels1", type=int, default=32)
    parser.add_argument("--conv-channels2", type=int, default=64)
    parser.add_argument("--sequence-kernel", type=int, choices=[3, 5, 7], default=3)
    parser.add_argument("--environment-kernel", type=int, choices=[3, 5, 7], default=3)
    parser.add_argument("--device", type=str, default=None)

    return parser.parse_args()


# ============================================================
# 18. Main
# ============================================================

def execute_args(args):
    """
    由已解析的 CLI 参数执行单次实验 (与 main() 完全同一路径;
    供 predict.py 进程内调度复用, 避免每个实验启动一次 python 解释器)。
    """
    validate_data_dir(args.data_dir)
    schema = validate_feature_schema(args.data_dir)

    cell_line = sanitize_name(args.cell_line) if args.cell_line is not None else None
    cell_lines = [sanitize_name(c) for c in args.cell_lines] if args.cell_lines is not None else None

    # 如果只传了 cell_line 单数，构造 cell_lines 列表
    if cell_line and not cell_lines:
        cell_lines = [cell_line]
    elif cell_lines and not cell_line:
        cell_line = cell_lines[0]

    # mixed 是跨细胞系混合划分, cell_line 无意义 (旧口径记录为 None);
    # 显式清零可避免 --cell-lines 传入后把它写成 cell_lines[0]。
    if sanitize_name(args.split_type) == "mixed":
        cell_line = None

    validate_split_configuration(
        split_type=args.split_type,
        cell_line=cell_line,
        train_ratio=args.train_ratio,
        valid_ratio=args.valid_ratio,
        test_ratio=args.test_ratio
    )

    model_name = sanitize_name(args.model)
    split_type = sanitize_name(args.split_type)
    environment = sanitize_name(args.environment)
    batch_name = sanitize_batch_name(args.batch_name) if args.batch_name else ""

    batch_model_dir, batch_results_dir, batch_logs_dir = build_batch_directories(
        batch_name=batch_name,
        model_root_dir=args.model_dir,
        results_root_dir=args.results_dir,
        logs_root_dir=args.logs_dir
    )

    result = run_one_experiment(
        model_name=model_name,
        split_type=split_type,
        cell_line=cell_line,
        cell_lines=cell_lines,
        environment=environment,
        data_dir=args.data_dir,
        batch_name=batch_name,
        model_dir=batch_model_dir,
        results_dir=batch_results_dir,
        logs_dir=batch_logs_dir,
        random_seed=args.seed,
        train_ratio=args.train_ratio,
        valid_ratio=args.valid_ratio,
        test_ratio=args.test_ratio,
        use_scaler=args.use_scaler,
        sequence_kernel=args.sequence_kernel,
        environment_kernel=args.environment_kernel,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        hidden_dim1=args.hidden_dim1,
        hidden_dim2=args.hidden_dim2,
        conv_channels1=args.conv_channels1,
        conv_channels2=args.conv_channels2,
        dropout=args.dropout,
        weight_decay=args.weight_decay,
        patience=args.patience,
        min_delta=args.min_delta,
        device=args.device,
        model_module=args.model_module,
        run_name=args.run_name,
    )

    print(f"\n[✓] Experiment {result['run_name']} Finished Successfully.")
    return result


def main():
    args = parse_args()
    return execute_args(args)


if __name__ == "__main__":
    main()