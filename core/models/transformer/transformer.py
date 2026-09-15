# core/models/transformer/transformer.py

"""
Transformer
===========

CRISPR-Cas9 sgRNA Editing Efficiency Prediction

本模块负责：

    1. 创建支持注意力权重提取的 Transformer Encoder 回归模型
    2. Training Set 训练与 Validation Set 监控 / Early Stopping
    3. 恢复最佳 Validation Checkpoint
    4. Held-out Test 最终评价
    5. 自注意力矩阵提取、Attention_Entropy (注意力熵) 与 Attention_SNR 计算
    6. 自注意力权重聚合 (Transformer_Attention / Attention_Entropy / Attention_SNR)
    ※ 学术红线: Transformer 不具备经典检验前提, 仅输出注意力白名单指标
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
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

try:
    from sklearn.preprocessing import StandardScaler
except ImportError:
    StandardScaler = None


# ============================================================
# 1. Random seed
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
    logger = logging.getLogger(f"Transformer_{log_path}")
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
# 3. Positional Encoding
# ============================================================

class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_length: int = 23):
        super().__init__()
        if d_model < 2:
            raise ValueError("d_model 必须 >= 2。")

        position = torch.arange(max_length, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2, dtype=torch.float32) * (-np.log(10000.0) / d_model))

        pe = torch.zeros(max_length, d_model)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term[:pe[:, 1::2].shape[1]])
        pe = pe.unsqueeze(0)

        self.register_buffer("pe", pe)
        self.max_length = max_length
        self.d_model = d_model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_len = x.size(1)
        if seq_len > self.max_length:
            raise ValueError(f"输入长度 {seq_len} 超过最大长度 {self.max_length}")
        return x + self.pe[:, :seq_len, :]


# ============================================================
# 4. Custom Transformer Layer with Attention Weights Export
# ============================================================

class TransformerEncoderLayerWithAttn(nn.Module):
    """
    可显式导出 Multihead Attention 矩阵的 Transformer Encoder Layer
    """
    def __init__(self, d_model: int, nhead: int, dim_feedforward: int = 128, dropout: float = 0.2):
        super().__init__()
        self.self_attn = nn.MultiheadAttention(d_model, nhead, dropout=dropout, batch_first=True)
        self.linear1 = nn.Linear(d_model, dim_feedforward)
        self.dropout = nn.Dropout(dropout)
        self.linear2 = nn.Linear(dim_feedforward, d_model)

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)
        self.activation = nn.GELU()

    def forward(self, src: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # Pre-LN 结构
        src_norm = self.norm1(src)
        src2, attn_weights = self.self_attn(src_norm, src_norm, src_norm, need_weights=True, average_attn_weights=False)
        src = src + self.dropout1(src2)

        src_norm2 = self.norm2(src)
        src2 = self.linear2(self.dropout(self.activation(self.linear1(src_norm2))))
        src = src + self.dropout2(src2)
        return src, attn_weights


class TransformerModel(nn.Module):
    def __init__(
        self,
        input_dim: int,
        max_sequence_length: int = 23,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 128,
        dropout: float = 0.2
    ):
        super().__init__()
        if input_dim <= 0 or d_model <= 0:
            raise ValueError("input_dim 与 d_model 必须 > 0。")
        if d_model % nhead != 0:
            raise ValueError(f"d_model={d_model} 必须能被 nhead={nhead} 整除。")

        self.input_dim = input_dim
        self.max_sequence_length = max_sequence_length
        self.d_model = d_model
        self.nhead = nhead
        self.num_layers = num_layers

        self.input_projection = nn.Linear(input_dim, d_model)
        self.position_encoding = PositionalEncoding(d_model=d_model, max_length=max_sequence_length)

        self.layers = nn.ModuleList([
            TransformerEncoderLayerWithAttn(d_model, nhead, dim_feedforward, dropout)
            for _ in range(num_layers)
        ])

        self.regressor = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 1)
        )

    def forward(self, x: torch.Tensor, return_attn: bool = False):
        if x.ndim != 3:
            raise ValueError(f"Transformer 输入必须为 (N, L, C)，当前为 {x.shape}")

        x = self.input_projection(x)
        x = self.position_encoding(x)

        all_attns = []
        for layer in self.layers:
            x, attn = layer(x)
            if return_attn:
                all_attns.append(attn)

        pooled = x.mean(dim=1)
        out = self.regressor(pooled)

        if return_attn:
            # 返回输出与最后一层的注意力矩阵 (N, nhead, L, L)
            return out, all_attns[-1]
        return out


# ============================================================
# 5. Metrics
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
# 6. Evaluation helper
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
# 7. Bioinformatics Robustness: Attention Focus & Entropy (XAI whitelist)
# ============================================================

def compute_transformer_attention_robustness(
    model: nn.Module,
    X: np.ndarray,
    device: torch.device
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    计算各 Position 的注意力强度 (Attn_Weight)、注意力熵 (Attn_Entropy) 与注意力信噪比 (Attn_SNR)
    """
    model.eval()
    N, L, C = X.shape
    with torch.no_grad():
        _, attn_mat = model(torch.from_numpy(X).to(device), return_attn=True)
        # attn_mat: (N, nhead, L, L)
        attn_mat = attn_mat.cpu().numpy()

    # 跨头求平均 -> (N, L, L)
    mean_head_attn = np.mean(attn_mat, axis=1)

    # 每个位点 j 被所有位置查询时的平均被关注度 -> (N, L)
    incoming_attn = np.mean(mean_head_attn, axis=1)
    pos_attn_mean = np.mean(incoming_attn, axis=0)  # (L,)
    pos_attn_std = np.std(incoming_attn, axis=0)    # (L,)
    pos_attn_snr = pos_attn_mean / (pos_attn_std + 1e-12)

    # 香农注意力熵: H = - sum(A * log2(A))
    eps = 1e-12
    entropy_per_sample = -np.sum(incoming_attn * np.log2(incoming_attn + eps), axis=1)
    mean_entropy = np.full(L, float(np.mean(entropy_per_sample)))

    return pos_attn_mean, mean_entropy, pos_attn_snr


def compute_transformer_integrated_gradients(
    model: nn.Module,
    X: np.ndarray,
    device: torch.device,
    steps: int = 20
) -> tuple[np.ndarray, np.ndarray]:
    """
    3D 输入 (N, L, C) 的完备性积分梯度计算
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


def compute_transformer_robustness_importance(
    model: nn.Module,
    X_eval: np.ndarray,
    channel_names: list[str],
    device: torch.device,
) -> pd.DataFrame:
    """
    Transformer 自注意力空间聚焦度归因 (XAI 白名单输出)：
        - Transformer_Attention : 多头注意力权重聚合均值 (position 级)
        - Attention_Entropy     : 注意力权重的香农熵 (弥散 vs 聚焦)
        - Attention_SNR         : mean/std 注意力信噪比
    学术红线：Transformer 不具备经典参数检验前提 —— 不产生 t/p/FDR，
    IG 与置换检验列已从导出中移除。
    """
    N, L, C = X_eval.shape

    # 1. 注意力强度 / 熵 / 信噪比 (仅依赖 position)
    attn_mean, attn_entropy, attn_snr = compute_transformer_attention_robustness(model, X_eval, device)

    # 2. 整合为 (l, c) 粒度行 (与特征名解析保持一致; 注意力指标为 position 级)
    records = []
    for l in range(L):
        for c in range(C):
            ch_name = channel_names[c] if c < len(channel_names) else f"Ch_{c}"
            feat_name = f"{ch_name}_pos_{l}"
            records.append({
                "Feature": feat_name,
                "Position": l,
                "Channel": ch_name,
                "Attn_Weight": float(attn_mean[l]),
                "Attn_Entropy": float(attn_entropy[l]),
                "Attn_SNR": float(attn_snr[l]),
            })

    df = pd.DataFrame(records)

    # 学术红线白名单清洗: 仅保留 Transformer_Attention / Attention_Entropy / Attention_SNR
    try:
        from core.xai.importance.xai_importance import export_feature_table
    except ImportError:
        from xai_importance import export_feature_table
    df = export_feature_table(
        "transformer", df,
        rename={"Attn_Weight": "Transformer_Attention",
                "Attn_Entropy": "Attention_Entropy",
                "Attn_SNR": "Attention_SNR"},
        origin="transformer.compute_transformer_robustness_importance",
    )
    df.sort_values("Transformer_Attention", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ============================================================
# 8. Save predictions & results
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

    metrics_path = os.path.join(result_dir, "transformer_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(test_metrics, f, indent=4, ensure_ascii=False)

    validation_metrics_path = os.path.join(result_dir, "transformer_validation_metrics.json")
    if valid_metrics is not None:
        with open(validation_metrics_path, "w", encoding="utf-8") as f:
            json.dump(valid_metrics, f, indent=4, ensure_ascii=False)
    else:
        validation_metrics_path = None

    predictions_path = os.path.join(result_dir, "transformer_predictions.csv")
    save_predictions(y_true=y_test, y_pred=y_test_pred, output_file=predictions_path)

    validation_predictions_path = os.path.join(result_dir, "transformer_validation_predictions.csv")
    if y_valid is not None and y_valid_pred is not None:
        save_predictions(y_true=y_valid, y_pred=y_valid_pred, output_file=validation_predictions_path)
    else:
        validation_predictions_path = None

    # 保存生信稳健性重要性表
    importance_path = os.path.join(result_dir, "transformer_feature_importance.csv")
    if importance_df is not None:
        importance_df.to_csv(importance_path, index=False)

    history_path = os.path.join(result_dir, "transformer_training_history.csv")
    pd.DataFrame(history).to_csv(history_path, index=False)

    info_path = os.path.join(result_dir, "transformer_info.txt")
    with open(info_path, "w", encoding="utf-8") as f:
        f.write("Transformer Experiment\n")
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
# 9. Unified train interface
# ============================================================

def train(
    X_train,
    y_train,
    X_test,
    y_test,
    X_valid=None,
    y_valid=None,
    feature_names=None,
    run_name="transformer",
    model_dir="models/weights",
    result_dir="results/batches",
    log_dir="results/logs",
    config: Optional[dict] = None,
    random_seed=42,
    epochs=100,
    batch_size=64,
    learning_rate=1e-3,
    d_model=64,
    nhead=4,
    num_layers=2,
    dim_feedforward=128,
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
    logger.info("Starting Transformer experiment.")

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
        raise ValueError("Transformer 输入必须为三维 (N, L, C)。")
    if len(X_train) != len(y_train) or len(X_test) != len(y_test):
        raise ValueError("样本数不匹配。")

    sequence_length = X_train.shape[1]
    channel_count = X_train.shape[2]

    has_validation = (X_valid is not None and y_valid is not None)
    if has_validation:
        if X_valid.ndim != 3 or len(X_valid) != len(y_valid):
            raise ValueError("X_valid 维度或样本数不匹配。")

    # 通道名称定义
    schema_channels = ["A", "G", "C", "CTCF", "Dnase", "H3K4me3", "RRBS"]
    if feature_names is not None and len(feature_names) == channel_count:
        channel_names = list(feature_names)
    else:
        channel_names = schema_channels[:channel_count] if channel_count <= len(schema_channels) else [f"Ch_{i}" for i in range(channel_count)]

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
    model = TransformerModel(
        input_dim=channel_count,
        max_sequence_length=sequence_length,
        d_model=d_model,
        nhead=nhead,
        num_layers=num_layers,
        dim_feedforward=dim_feedforward,
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

    # 计算生信稳健性重要性 (XAI 白名单: Transformer_Attention / Attention_Entropy / Attention_SNR)
    eval_X = X_test if len(X_test) > 0 else X_train
    logger.info("Computing Transformer Attention Entropy whitelist importance...")
    importance_df = compute_transformer_robustness_importance(
        model=model,
        X_eval=eval_X,
        channel_names=channel_names,
        device=device_obj
    )
    logger.info(f"Transformer XAI whitelist importance computed ({len(importance_df)} rows).")

    # 保存配置与模型
    config = dict(config or {})
    config.update({
        "model": "transformer",
        "sequence_length": sequence_length,
        "channel_count": channel_count,
        "d_model": d_model,
        "nhead": nhead,
        "num_layers": num_layers,
        "best_epoch": best_epoch,
        "best_validation_loss": best_val_loss,
        "device_resolved": str(device_obj),
        "torch_version": torch.__version__,
        "torch_cuda_build": torch.version.cuda,
    })

    model_path = os.path.join(current_model_dir, "transformer_model.pt")
    save_model(model=model, model_path=model_path, config=config)

    scaler_path = None
    if scaler is not None:
        scaler_path = os.path.join(current_model_dir, "transformer_scaler.pkl")
        with open(scaler_path, "wb") as f:
            pickle.dump(scaler, f)

    config_path = os.path.join(current_model_dir, "transformer_config.json")
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

    logger.info("Transformer experiment finished successfully.")

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
# 10. Standalone test
# ============================================================

if __name__ == "__main__":
    rng = np.random.default_rng(42)

    N_train, N_valid, N_test = 200, 50, 50
    sequence_length = 23
    channel_count = 8

    X_train = rng.random((N_train, sequence_length, channel_count)).astype(np.float32)
    y_train = rng.random(N_train).astype(np.float32)
    X_valid = rng.random((N_valid, sequence_length, channel_count)).astype(np.float32)
    y_valid = rng.random(N_valid).astype(np.float32)
    X_test = rng.random((N_test, sequence_length, channel_count)).astype(np.float32)
    y_test = rng.random(N_test).astype(np.float32)

    result = train(
        X_train=X_train,
        y_train=y_train,
        X_valid=X_valid,
        y_valid=y_valid,
        X_test=X_test,
        y_test=y_test,
        run_name="example_transformer_robustness",
        epochs=10
    )

    print("\nTop 5 Features with Attention Entropy and IG Robustness Stats:")
    print(result["feature_importance"][["Feature", "Transformer_Attention", "Attention_Entropy", "Attention_SNR"]].head(5))
