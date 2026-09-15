# core/models/cnn/cnn.py

"""
CNN
===

CRISPR-Cas9 sgRNA Editing Efficiency Prediction

本模块负责：

    1. 创建双分支动态卷积神经网络（Sequence Branch + Environment Branch）
    2. Training Set 训练与 Validation Set 监控 / Early Stopping
    3. 恢复最佳 Validation Checkpoint
    4. Held-out Test 最终评价
    5. In-Silico Mutagenesis (ISM 虚拟饱和突变) 计算
    6. 3D 卷积原生 Integrated Gradients (IG) 计算
    ※ 学术红线: CNN 不具备经典检验前提, 仅输出白名单指标 (CNN_IG/CNN_ISM/ISM_SNR)
    8. 保存模型、预测结果、训练历史与特征稳健性统计表
"""

from __future__ import annotations

import copy
import json
import logging
import os
import pickle
import random
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

try:
    from sklearn.preprocessing import StandardScaler
except ImportError:
    StandardScaler = None


# ============================================================
# 1. Seed
# ============================================================

def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


# ============================================================
# 2. Logger
# ============================================================

def create_logger(log_dir: str):
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "training.log")
    logger = logging.getLogger(f"CNN_{log_path}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger, log_path


# ============================================================
# 3. CNN Model
# ============================================================

class CNNModel(nn.Module):
    def __init__(
        self,
        sequence_channels: int,
        environment_channels: int,
        sequence_kernel: int = 3,
        environment_kernel: int = 3,
        sequence_filters: int = 64,
        environment_filters: int = 64,
        fusion_filters: int = 128,
        dropout: float = 0.2
    ):
        super().__init__()

        if sequence_channels <= 0:
            raise ValueError("sequence_channels 必须 > 0。")
        if environment_channels < 0:
            raise ValueError("environment_channels 必须 >= 0。")
        if sequence_kernel <= 0 or environment_kernel <= 0:
            raise ValueError("kernel size 必须 > 0。")

        self.sequence_channels = sequence_channels
        self.environment_channels = environment_channels
        self.sequence_kernel = sequence_kernel
        self.environment_kernel = environment_kernel
        self.sequence_filters = sequence_filters
        self.environment_filters = environment_filters
        self.fusion_filters = fusion_filters
        self.dropout_rate = dropout

        # 序列分支卷积
        self.sequence_branch = nn.Sequential(
            nn.Conv2d(
                in_channels=1,
                out_channels=sequence_filters,
                kernel_size=(sequence_kernel, sequence_channels),
                padding=(sequence_kernel // 2, 0)
            ),
            nn.BatchNorm2d(sequence_filters),
            nn.ReLU(),
            nn.Conv2d(
                in_channels=sequence_filters,
                out_channels=sequence_filters,
                kernel_size=(sequence_kernel, 1),
                padding=(sequence_kernel // 2, 0)
            ),
            nn.BatchNorm2d(sequence_filters),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1))
        )

        # 环境分支卷积
        if environment_channels > 0:
            self.environment_branch = nn.Sequential(
                nn.Conv2d(
                    in_channels=1,
                    out_channels=environment_filters,
                    kernel_size=(environment_kernel, environment_channels),
                    padding=(environment_kernel // 2, 0)
                ),
                nn.BatchNorm2d(environment_filters),
                nn.ReLU(),
                nn.Conv2d(
                    in_channels=environment_filters,
                    out_channels=environment_filters,
                    kernel_size=(environment_kernel, 1),
                    padding=(environment_kernel // 2, 0)
                ),
                nn.BatchNorm2d(environment_filters),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d((1, 1))
            )
        else:
            self.environment_branch = None

        # 融合全连接层
        fusion_input = sequence_filters + (environment_filters if environment_channels > 0 else 0)
        self.fusion = nn.Sequential(
            nn.Linear(fusion_input, fusion_filters),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fusion_filters, fusion_filters // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fusion_filters // 2, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 3:
            raise ValueError(f"CNN 输入必须为 (N, L, C)，当前为 {x.shape}")

        batch_size = x.shape[0]
        expected_channels = self.sequence_channels + self.environment_channels
        if x.shape[2] != expected_channels:
            raise ValueError(f"CNN channel 数量错误：实际={x.shape[2]}, 预期={expected_channels}")

        # 序列部分 (N, 1, L, 3)
        seq_x = x[:, :, :self.sequence_channels].unsqueeze(1)
        seq_feat = self.sequence_branch(seq_x).reshape(batch_size, -1)

        features = [seq_feat]

        # 环境部分 (N, 1, L, E)
        if self.environment_channels > 0:
            env_x = x[:, :, self.sequence_channels:].unsqueeze(1)
            env_feat = self.environment_branch(env_x).reshape(batch_size, -1)
            features.append(env_feat)

        fused = torch.cat(features, dim=1)
        output = self.fusion(fused)
        return output


# ============================================================
# 4. Metrics
# ============================================================

def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray):
    y_true = np.asarray(y_true, dtype=np.float64).reshape(-1)
    y_pred = np.asarray(y_pred, dtype=np.float64).reshape(-1)

    if len(y_true) != len(y_pred):
        raise ValueError("y_true 和 y_pred 长度不一致。")
    if not np.isfinite(y_true).all() or not np.isfinite(y_pred).all():
        raise ValueError("y_true 或 y_pred 中存在 NaN/Inf。")

    error = y_true - y_pred
    mse = np.mean(error ** 2)
    rmse = np.sqrt(mse)
    mae = np.mean(np.abs(error))

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = np.nan if np.isclose(ss_tot, 0) else (1.0 - ss_res / ss_tot)

    if np.std(y_true) == 0 or np.std(y_pred) == 0:
        pearson = np.nan
    else:
        pearson = np.corrcoef(y_true, y_pred)[0, 1]

    true_rank = pd.Series(y_true).rank(method="average").to_numpy()
    pred_rank = pd.Series(y_pred).rank(method="average").to_numpy()

    if np.std(true_rank) == 0 or np.std(pred_rank) == 0:
        spearman = np.nan
    else:
        spearman = np.corrcoef(true_rank, pred_rank)[0, 1]

    return {
        "MSE": float(mse),
        "RMSE": float(rmse),
        "MAE": float(mae),
        "R2": float(r2),
        "Pearson": float(pearson),
        "Spearman": float(spearman)
    }


# ============================================================
# 5. Evaluation
# ============================================================

def evaluate_model(model: nn.Module, data_loader: DataLoader, criterion: nn.Module, device: torch.device):
    model.eval()
    total_loss = 0.0
    total_samples = 0
    predictions = []
    targets = []

    with torch.no_grad():
        for batch_x, batch_y in data_loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            prediction = model(batch_x).squeeze(-1)
            loss = criterion(prediction, batch_y)
            batch_count = len(batch_x)

            total_loss += loss.item() * batch_count
            total_samples += batch_count
            predictions.append(prediction.cpu().numpy())
            targets.append(batch_y.cpu().numpy())

    if total_samples == 0:
        raise ValueError("Evaluation dataset 为空。")

    average_loss = total_loss / total_samples
    y_pred = np.concatenate(predictions)
    y_true = np.concatenate(targets)
    return float(average_loss), y_true, y_pred


# ============================================================
# 6. Bioinformatics Robustness: ISM & IG (XAI whitelist)
# ============================================================

def compute_cnn_ism(
    model: nn.Module,
    X: np.ndarray,
    device: torch.device
) -> tuple[np.ndarray, np.ndarray]:
    """
    In-Silico Mutagenesis (ISM，虚拟饱和突变)
    对每个样本的 (23, C) 逐个位点通道进行置零/扰动突变，计算 |Delta y| 的均值与方差
    """
    model.eval()
    N, L, C = X.shape
    with torch.no_grad():
        base_preds = model(torch.from_numpy(X).to(device)).squeeze(-1).cpu().numpy()

    ism_deltas = np.zeros((N, L, C), dtype=np.float32)

    for l in range(L):
        for c in range(C):
            X_mut = X.copy()
            # 若已有值则置零，若为0则赋值1（模拟扰动）
            X_mut[:, l, c] = np.where(X_mut[:, l, c] > 0, 0.0, 1.0)
            with torch.no_grad():
                mut_preds = model(torch.from_numpy(X_mut).to(device)).squeeze(-1).cpu().numpy()
            ism_deltas[:, l, c] = np.abs(mut_preds - base_preds)

    mean_ism = np.mean(ism_deltas, axis=0)  # (L, C)
    std_ism = np.std(ism_deltas, axis=0)    # (L, C)
    return mean_ism, std_ism


def compute_cnn_integrated_gradients(
    model: nn.Module,
    X: np.ndarray,
    device: torch.device,
    steps: int = 25
) -> tuple[np.ndarray, np.ndarray]:
    """
    针对 3D 输入 (N, L, C) 的完备性积分梯度计算
    """
    model.eval()
    N, L, C = X.shape
    baseline = np.zeros_like(X, dtype=np.float32)
    ig_matrix = np.zeros((N, L, C), dtype=np.float32)
    alphas = np.linspace(0.0, 1.0, steps + 1)
    diff = X - baseline

    for i in range(N):
        x_orig = X[i]
        b_orig = baseline[i]
        step_pts = np.array([b_orig + a * (x_orig - b_orig) for a in alphas], dtype=np.float32)
        step_tensor = torch.from_numpy(step_pts).to(device).requires_grad_(True)

        preds = model(step_tensor).squeeze(-1)
        grads = torch.autograd.grad(preds.sum(), step_tensor)[0].cpu().numpy()
        avg_grads = np.mean(grads[:-1], axis=0)
        ig_matrix[i] = diff[i] * avg_grads

    mean_ig = np.mean(np.abs(ig_matrix), axis=0)  # (L, C)
    std_ig = np.std(ig_matrix, axis=0)           # (L, C)
    return mean_ig, std_ig


def compute_cnn_robustness_importance(
    model: nn.Module,
    X_eval: np.ndarray,
    channel_names: list[str],
    device: torch.device,
) -> pd.DataFrame:
    """
    CNN 双分支卷积的基因级归因 (XAI 白名单输出)：
        - CNN_ISM : 单核苷酸虚拟饱和突变预测变化量均值 (mean |Δŷ|)
        - ISM_SNR : mean/std 饱和突变效应信噪比
        - CNN_IG  : 卷积网络积分梯度归因均值
    学术红线：CNN 不具备经典参数检验前提 —— 不产生 t/p/FDR，置换检验与显著性列已移除。
    """
    N, L, C = X_eval.shape

    # 1. ISM 虚拟饱和突变 (生信黄金标准)
    ism_mean, ism_std = compute_cnn_ism(model, X_eval, device)
    ism_snr = ism_mean / (ism_std + 1e-12)

    # 2. Integrated Gradients
    ig_mean, _ig_std = compute_cnn_integrated_gradients(model, X_eval, device, steps=20)

    # 扁平化整合为 DataFrame
    records = []
    for l in range(L):
        for c in range(C):
            ch_name = channel_names[c] if c < len(channel_names) else f"Ch_{c}"
            feat_name = f"{ch_name}_pos_{l}"
            records.append({
                "Feature": feat_name,
                "Position": l,
                "Channel": ch_name,
                "ISM_Mean_Delta": float(ism_mean[l, c]),
                "ISM_SNR": float(ism_snr[l, c]),
                "IG_Mean": float(ig_mean[l, c]),
            })

    df = pd.DataFrame(records)

    # 学术红线白名单清洗: 仅保留 CNN_IG / CNN_ISM / ISM_SNR
    try:
        from core.xai.importance.xai_importance import export_feature_table
    except ImportError:
        from xai_importance import export_feature_table
    df = export_feature_table(
        "cnn", df,
        rename={"ISM_Mean_Delta": "CNN_ISM", "IG_Mean": "CNN_IG"},
        origin="cnn.compute_cnn_robustness_importance",
    )
    df.sort_values("CNN_ISM", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ============================================================
# 7. Save predictions & results
# ============================================================

def save_predictions(y_true, y_pred, output_file):
    predictions = pd.DataFrame({
        "y_true": np.asarray(y_true).reshape(-1),
        "y_pred": np.asarray(y_pred).reshape(-1)
    })
    predictions["error"] = predictions["y_true"] - predictions["y_pred"]
    predictions.to_csv(output_file, index=False)


def save_results(
    y_valid,
    y_valid_pred,
    valid_metrics,
    y_test,
    y_test_pred,
    test_metrics,
    history,
    result_dir,
    run_name,
    config,
    importance_df: Optional[pd.DataFrame] = None
):
    os.makedirs(result_dir, exist_ok=True)

    metrics_path = os.path.join(result_dir, "cnn_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(test_metrics, f, indent=4, ensure_ascii=False)

    validation_metrics_path = os.path.join(result_dir, "cnn_validation_metrics.json")
    if valid_metrics is not None:
        with open(validation_metrics_path, "w", encoding="utf-8") as f:
            json.dump(valid_metrics, f, indent=4, ensure_ascii=False)
    else:
        validation_metrics_path = None

    predictions_path = os.path.join(result_dir, "cnn_predictions.csv")
    save_predictions(y_true=y_test, y_pred=y_test_pred, output_file=predictions_path)

    validation_predictions_path = os.path.join(result_dir, "cnn_validation_predictions.csv")
    if y_valid is not None and y_valid_pred is not None:
        save_predictions(y_true=y_valid, y_pred=y_valid_pred, output_file=validation_predictions_path)
    else:
        validation_predictions_path = None

    # 保存生信稳健性重要性表
    importance_path = os.path.join(result_dir, "cnn_feature_importance.csv")
    if importance_df is not None:
        importance_df.to_csv(importance_path, index=False)

    history_path = os.path.join(result_dir, "cnn_training_history.csv")
    pd.DataFrame(history).to_csv(history_path, index=False)

    info_path = os.path.join(result_dir, "cnn_info.txt")
    with open(info_path, "w", encoding="utf-8") as f:
        f.write("CNN Experiment\n")
        f.write("========================================\n")
        f.write(f"Run name: {run_name}\n")
        f.write(f"Time: {datetime.now().isoformat()}\n\n")

        f.write("Configuration\n")
        f.write("----------------------------------------\n")
        for key, value in config.items():
            f.write(f"{key}: {value}\n")

        if valid_metrics is not None:
            f.write("\nValidation Metrics\n")
            f.write("----------------------------------------\n")
            for key, value in valid_metrics.items():
                f.write(f"{key}: {value}\n")

        f.write("\nTest Metrics\n")
        f.write("----------------------------------------\n")
        for key, value in test_metrics.items():
            f.write(f"{key}: {value}\n")

    return {
        "metrics_path": metrics_path,
        "validation_metrics_path": validation_metrics_path,
        "predictions_path": predictions_path,
        "validation_predictions_path": validation_predictions_path,
        "importance_path": importance_path,
        "history_path": history_path,
        "info_path": info_path
    }


def save_model(model: nn.Module, model_path: str, config: dict):
    torch.save({"model_state_dict": model.state_dict(), "config": config}, model_path)


# ============================================================
# 8. Unified train interface
# ============================================================

def train(
    X_train,
    y_train,
    X_test,
    y_test,
    X_valid=None,
    y_valid=None,
    feature_names=None,
    run_name="cnn",
    model_dir="models/weights",
    result_dir="results/batches",
    log_dir="results/logs",
    config: Optional[dict] = None,
    random_seed=42,
    epochs=100,
    batch_size=64,
    learning_rate=1e-3,
    sequence_kernel=3,
    environment_kernel=3,
    sequence_filters=64,
    environment_filters=64,
    fusion_filters=128,
    dropout=0.2,
    weight_decay=0.0,
    patience=20,
    min_delta=1e-6,
    num_workers=0,
    device=None,
    use_scaler=False
):
    set_seed(random_seed)

    current_model_dir = os.path.join(model_dir, run_name)
    current_result_dir = os.path.join(result_dir, run_name)
    current_log_dir = os.path.join(log_dir, run_name)

    os.makedirs(current_model_dir, exist_ok=True)
    os.makedirs(current_result_dir, exist_ok=True)
    os.makedirs(current_log_dir, exist_ok=True)

    logger, log_path = create_logger(current_log_dir)
    logger.info("Starting dual-branch CNN experiment.")

    # 格式转换
    X_train = np.asarray(X_train, dtype=np.float32)
    y_train = np.asarray(y_train, dtype=np.float32).reshape(-1)
    X_test = np.asarray(X_test, dtype=np.float32)
    y_test = np.asarray(y_test, dtype=np.float32).reshape(-1)

    if X_valid is not None:
        X_valid = np.asarray(X_valid, dtype=np.float32)
    if y_valid is not None:
        y_valid = np.asarray(y_valid, dtype=np.float32).reshape(-1)

    # 维度检查
    if X_train.ndim != 3 or X_test.ndim != 3:
        raise ValueError("CNN 输入必须为 (N, L, C)。")
    if len(X_train) != len(y_train) or len(X_test) != len(y_test):
        raise ValueError("样本数不匹配。")

    has_validation = (X_valid is not None and y_valid is not None)
    if has_validation:
        if X_valid.ndim != 3 or len(X_valid) != len(y_valid):
            raise ValueError("X_valid 维度或样本数不匹配。")

    config = dict(config or {})
    default_environment_order = ['ctcf', 'dnase', 'h3k4me3', 'rrbs']
    _NUCLEOTIDE_CHANNELS = {"A", "C", "G", "T"}
    total_in_channels = int(X_train.shape[2])

    # 序列/环境通道切分: 优先按 schema 的 channel_names 驱动
    #   (新 23x8 编码: 序列 = [A,C,G,T]; 旧 23x7 编码: 序列 = 前 3 碱基通道)
    schema_channels = [str(c) for c in (config.get('channel_names') or [])]
    if schema_channels and len(schema_channels) == total_in_channels:
        sequence_channels = sum(1 for c in schema_channels if c.upper() in _NUCLEOTIDE_CHANNELS)
        env_positions_abs = {
            c.lower(): idx for idx, c in enumerate(schema_channels)
            if c.upper() not in _NUCLEOTIDE_CHANNELS
        }
        env_order = list(env_positions_abs.keys())
    else:
        sequence_channels = 3
        env_positions_abs = None
        env_order = [e.lower() for e in config.get('environment_order', default_environment_order)]

    if sequence_channels < 1 or total_in_channels < sequence_channels:
        raise ValueError(f"输入通道数不能小于序列通道数 ({sequence_channels})。")

    # 环境通道选择 (selected_environments 为空 -> 纯序列; None -> 全部环境)
    selected_env = config.get('selected_environments', None)
    if selected_env is not None:
        selected_env = [e.lower() for e in selected_env]
        if len(selected_env) == 0:
            X_train = X_train[:, :, :sequence_channels]
            if X_valid is not None: X_valid = X_valid[:, :, :sequence_channels]
            X_test = X_test[:, :, :sequence_channels]
            environment_channels = 0
        else:
            if env_positions_abs is not None:
                env_indices_abs = [env_positions_abs[e] for e in selected_env if e in env_positions_abs]
            else:
                env_indices_abs = [
                    sequence_channels + env_order.index(e)
                    for e in selected_env if e in env_order
                ]
            seq_part = X_train[:, :, :sequence_channels]
            env_part = X_train[:, :, env_indices_abs]
            X_train = np.concatenate([seq_part, env_part], axis=2)

            if X_valid is not None:
                seq_v = X_valid[:, :, :sequence_channels]
                env_v = X_valid[:, :, env_indices_abs]
                X_valid = np.concatenate([seq_v, env_v], axis=2)

            seq_t = X_test[:, :, :sequence_channels]
            env_t = X_test[:, :, env_indices_abs]
            X_test = np.concatenate([seq_t, env_t], axis=2)

            environment_channels = len(env_indices_abs)
        config['selected_environments'] = selected_env
    else:
        actual_env_count = total_in_channels - sequence_channels
        environment_channels = max(0, actual_env_count)
        config['selected_environments'] = list(env_order)[:environment_channels]

    # 生成 channel_names 列表 (与最终 X 列顺序一致, 供日志/导出)
    seq_names = ["A", "C", "G", "T"][:sequence_channels] if sequence_channels == 4 else ["A", "G", "C"][:sequence_channels]
    selected_env_names = config.get('selected_environments') or []
    if env_positions_abs is not None:
        # env_canonical: lower -> original 大小写
        env_canonical = {str(c).lower(): c for c in schema_channels
                         if c.upper() not in _NUCLEOTIDE_CHANNELS}
        channel_names = seq_names + [
            env_canonical[e] for e in selected_env_names if e in env_canonical
        ]
    else:
        default_casing = {"ctcf": "CTCF", "dnase": "Dnase", "h3k4me3": "H3K4me3", "rrbs": "RRBS"}
        channel_names = seq_names + [
            default_casing.get(e, e.upper()) for e in selected_env_names
        ]

    # Scaler
    scaler = None
    if use_scaler:
        if StandardScaler is None: raise ImportError("use_scaler requires scikit-learn.")
        scaler = StandardScaler()
        N_tr, L_tr, C_tr = X_train.shape
        X_train = scaler.fit_transform(X_train.reshape(-1, C_tr)).reshape(N_tr, L_tr, C_tr).astype(np.float32)
        if has_validation:
            N_v, L_v, C_v = X_valid.shape
            X_valid = scaler.transform(X_valid.reshape(-1, C_v)).reshape(N_v, L_v, C_v).astype(np.float32)
        N_te, L_te, C_te = X_test.shape
        X_test = scaler.transform(X_test.reshape(-1, C_te)).reshape(N_te, L_te, C_te).astype(np.float32)

    # 设备配置
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    device_obj = torch.device(device)
    logger.info(f"Device: {device_obj}, Channels: {channel_names}")

    # 实例化模型
    model = CNNModel(
        sequence_channels=sequence_channels,
        environment_channels=environment_channels,
        sequence_kernel=sequence_kernel,
        environment_kernel=environment_kernel,
        sequence_filters=sequence_filters,
        environment_filters=environment_filters,
        fusion_filters=fusion_filters,
        dropout=dropout
    ).to(device_obj)

    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    # 数据加载器
    train_dataset = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers)

    valid_loader = None
    if has_validation:
        valid_dataset = TensorDataset(torch.from_numpy(X_valid), torch.from_numpy(y_valid))
        valid_loader = DataLoader(valid_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    # 训练循环
    history = []
    best_val_loss = np.inf
    best_epoch = None
    best_state_dict = None
    epochs_without_improvement = 0

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        sample_count = 0

        for batch_x, batch_y in train_loader:
            batch_x = batch_x.to(device_obj)
            batch_y = batch_y.to(device_obj)

            optimizer.zero_grad()
            prediction = model(batch_x).squeeze(-1)
            loss = criterion(prediction, batch_y)
            loss.backward()
            optimizer.step()

            batch_count = len(batch_x)
            epoch_loss += loss.item() * batch_count
            sample_count += batch_count

        train_loss = epoch_loss / sample_count
        val_loss = None
        if has_validation:
            val_loss, _, _ = evaluate_model(model=model, data_loader=valid_loader, criterion=criterion, device=device_obj)

        history.append({
            "epoch": epoch,
            "train_loss": float(train_loss),
            "validation_loss": float(val_loss) if val_loss is not None else np.nan
        })

        if has_validation:
            improvement = best_val_loss - val_loss
            if improvement > min_delta:
                best_val_loss = val_loss
                best_epoch = epoch
                best_state_dict = copy.deepcopy(model.state_dict())
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1

        should_log = (epoch == 1 or epoch % 10 == 0 or epoch == epochs or (has_validation and epoch == best_epoch))
        if should_log:
            if val_loss is None:
                logger.info(f"Epoch {epoch:4d} | Train Loss: {train_loss:.8f}")
            else:
                logger.info(f"Epoch {epoch:4d} | Train Loss: {train_loss:.8f} | Validation Loss: {val_loss:.8f}")

        if has_validation and epochs_without_improvement >= patience:
            logger.info(f"Early stopping triggered at epoch {epoch}. Best epoch: {best_epoch}")
            break

    # 恢复最佳权重
    if has_validation:
        model.load_state_dict(best_state_dict)
        logger.info(f"Restored best checkpoint from epoch {best_epoch}.")
    else:
        best_epoch = epoch

    # Final Validation
    valid_predictions = None
    valid_metrics = None
    if has_validation:
        final_valid_loss, final_y_valid, valid_predictions = evaluate_model(
            model=model, data_loader=valid_loader, criterion=criterion, device=device_obj
        )
        valid_metrics = calculate_metrics(final_y_valid, valid_predictions)
        logger.info(f"Final Validation R2: {valid_metrics['R2']:.4f}")

    # Final Test
    test_dataset = TensorDataset(torch.from_numpy(X_test), torch.from_numpy(y_test))
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    _, final_y_test, y_pred = evaluate_model(model=model, data_loader=test_loader, criterion=criterion, device=device_obj)
    test_metrics = calculate_metrics(final_y_test, y_pred)
    logger.info(f"Final Test Evaluation -> R2: {test_metrics['R2']:.4f}, Pearson: {test_metrics['Pearson']:.4f}")

    # 计算生信稳健性重要性 (XAI 白名单: CNN_IG / CNN_ISM / ISM_SNR)
    eval_X = X_test if len(X_test) > 0 else X_train
    eval_y = y_test if len(y_test) > 0 else y_train
    logger.info("Computing CNN In-Silico Mutagenesis (ISM) and Integrated Gradients...")
    importance_df = compute_cnn_robustness_importance(
        model=model,
        X_eval=eval_X,
        channel_names=channel_names,
        device=device_obj
    )
    logger.info(f"CNN XAI whitelist importance computed ({len(importance_df)} features).")

    # 保存配置与模型
    config.update({
        "model": "cnn_dual_branch",
        "sequence_channels": sequence_channels,
        "environment_channels": environment_channels,
        "sequence_kernel": sequence_kernel,
        "environment_kernel": environment_kernel,
        "best_epoch": best_epoch,
        "best_validation_loss": best_val_loss,
        "device_resolved": str(device_obj),
        "torch_version": torch.__version__,
        "torch_cuda_build": torch.version.cuda,
    })

    model_path = os.path.join(current_model_dir, "cnn_model.pt")
    save_model(model=model, model_path=model_path, config=config)

    scaler_path = None
    if scaler is not None:
        scaler_path = os.path.join(current_model_dir, "cnn_scaler.pkl")
        with open(scaler_path, "wb") as f:
            pickle.dump(scaler, f)

    config_path = os.path.join(current_model_dir, "cnn_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    result_paths = save_results(
        y_valid=final_y_valid if has_validation else None,
        y_valid_pred=valid_predictions if has_validation else None,
        valid_metrics=valid_metrics if has_validation else None,
        y_test=final_y_test,
        y_test_pred=y_pred,
        test_metrics=test_metrics,
        history=history,
        result_dir=current_result_dir,
        run_name=run_name,
        config=config,
        importance_df=importance_df
    )

    logger.info("CNN experiment finished successfully.")

    return {
        "model": model,
        "metrics": test_metrics,
        "valid_metrics": valid_metrics,
        "predictions": y_pred,
        "validation_predictions": valid_predictions,
        "feature_importance": importance_df,
        "history": history,
        "best_epoch": best_epoch,
        "best_validation_loss": best_val_loss,
        "model_paths": {
            "model_path": model_path,
            "config_path": config_path,
            "scaler_path": scaler_path
        },
        "result_paths": result_paths,
        "log_path": log_path
    }


# ============================================================
# 9. Standalone test
# ============================================================

if __name__ == "__main__":
    rng = np.random.default_rng(42)

    N_train, N_valid, N_test = 200, 50, 50
    L = 23
    seq_ch = 3
    env_ch = 2

    X_train = rng.integers(0, 2, size=(N_train, L, seq_ch + env_ch)).astype(np.float32)
    X_valid = rng.integers(0, 2, size=(N_valid, L, seq_ch + env_ch)).astype(np.float32)
    X_test = rng.integers(0, 2, size=(N_test, L, seq_ch + env_ch)).astype(np.float32)

    y_train = (0.4 * X_train[:, :, 0].mean(axis=1) + 0.3 * X_train[:, :, 3].mean(axis=1)).astype(np.float32)
    y_valid = (0.4 * X_valid[:, :, 0].mean(axis=1) + 0.3 * X_valid[:, :, 3].mean(axis=1)).astype(np.float32)
    y_test = (0.4 * X_test[:, :, 0].mean(axis=1) + 0.3 * X_test[:, :, 3].mean(axis=1)).astype(np.float32)

    result = train(
        X_train=X_train,
        y_train=y_train,
        X_valid=X_valid,
        y_valid=y_valid,
        X_test=X_test,
        y_test=y_test,
        run_name="example_cnn_robustness",
        config={
            "model": "cnn_dual_branch",
            "environment": "sequence_ctcf_dnase",
            "selected_environments": ["CTCF", "Dnase"]
        },
        epochs=10
    )

    print("\nTop 5 Features (XAI whitelist):")
    print(result["feature_importance"][["Feature", "CNN_IG", "CNN_ISM", "ISM_SNR"]].head(5))
