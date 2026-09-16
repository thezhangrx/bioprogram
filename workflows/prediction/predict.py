# predict.py
"""
CRISPR-Cas9 mixed 十折交叉验证 + 目标数据集预测引擎
================================================================
从旧版 predict.py 拆分 (职责单一化):
    predict.py       只负责: 全部已测细胞系 mixed 数据 -> 10 折 CV 选超参 ->
                     全量重训终极模型 -> 对【目标待测数据集】做真实预测并排序
                     生成 赛道二_results.csv  (引导程序第4步之 3: Target Epigenetics)。
    data_digging.py  只负责: 已测数据训练挖掘网格实验 (引导程序第4步之 2: Training Scope)。

Target Epigenetics 对齐 (严格子集重训):
    按目标待测数据集【实际具备】的表观通道(sequence 通道恒有)裁剪 mixed 十折训练的
    输入通道后再训练与预测, 保证训练/预测特征空间完全一致:
        --target-input <csv 或目录>           目标待测序列/基因组 (调试/正式均可输入)
        --target-epigenetics CTCF Dnase ...  目标实际具备的表观通道 (缺省=从文件自动识别)
    通道命名/顺序以 data-dir 下 feature_schema.json 的 channel_names 为准。
    线性终极模型与 data_digging 网格 LR 保持同一参照处理: 若特征含 _T 参照列则剔除 (T 为基准)。
用法:
    python predict.py --data-dir data/processed --models linear xgboost \\
        --cell-lines hct116 hela \\
        --target-input 待测数据集.CSV --target-epigenetics CTCF Dnase \\
        --results-dir results --batch-name full   # -> results/[batch]/summary/赛道二_results.csv
    python predict.py ...(不带 --target-input)     # 兼容旧用法: 对 mixed 已测池自身 Top-K
"""

from __future__ import annotations


# --- 项目根引导: 保证从任意工作目录运行/被导入都能解析 core、analysis、workflows ---
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import io
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
MODELS = ["linear", "xgboost", "mlp", "transformer"]
CNN_MODELS = ["cnn"]
ALL_MODELS = [*MODELS, "cnn"]
# 数据集/细胞系列表**不再硬编码**：由 --data-dir 下实际发现的文件决定
# (core.data.splitting.cell_line_division.discover_available_cell_lines)。
SEQ_LETTERS = {"A", "C", "G", "T"}
SEQ_COL_CANDIDATES = ["sgRNA", "sequence", "Sequence", "23nt", "protospacer"]

ULTIMATE_MODEL_ORDER = ["lr", "xgboost", "mlp", "cnn33", "cnn53", "cnn73", "transformer"]
ULTIMATE_DISPLAY = {
    "lr": "Linear",
    "xgboost": "XGBoost",
    "mlp": "MLP",
    "cnn33": "CNN(3|3)",
    "cnn53": "CNN(5|3)",
    "cnn73": "CNN(7|3)",
    "transformer": "Transformer",
}
ULTIMATE_MODEL_MAP = {
    "lr": "Linear Regression",
    "xgboost": "XGBoost",
    "mlp": "MLP",
    "cnn33": "Dual-Branch CNN (k3|3)",
    "cnn53": "Dual-Branch CNN (k5|3)",
    "cnn73": "Dual-Branch CNN (k7|3)",
    "transformer": "Transformer",
}
ULTIMATE_GRIDS: Dict[str, List[Dict]] = {
    "lr": [{"use_scaler": False}],
    "xgboost": [
        {"n_estimators": 100, "max_depth": 3},
        {"n_estimators": 200, "max_depth": 4},
    ],
    "mlp": [
        {"hidden_dim1": 128, "dropout": 0.2},
        {"hidden_dim1": 256, "dropout": 0.3},
    ],
    "cnn33": [
        {"conv_channels1": 32, "conv_channels2": 64, "dropout": 0.2},
        {"conv_channels1": 48, "conv_channels2": 96, "dropout": 0.3},
    ],
    "cnn53": [
        {"conv_channels1": 32, "conv_channels2": 64, "dropout": 0.2},
    ],
    "cnn73": [
        {"conv_channels1": 32, "conv_channels2": 64, "dropout": 0.2},
    ],
    "transformer": [
        {"dropout": 0.1},
        {"dropout": 0.2},
    ],
}
KIND_USES_2D = {"lr", "xgboost", "mlp"}
TORCH_KINDS = {"mlp", "cnn33", "cnn53", "cnn73", "transformer"}


# ---------------------------------------------------------------------------
# 通道规划 / 目标数据集特征构建 (Target Epigenetics)
# ---------------------------------------------------------------------------

def build_channel_plan(schema: Dict, target_epis: Optional[List[str]] = None) -> Dict:
    """按目标实际具备的表观通道从 schema.channel_names 中选取列下标(保序)。

    sequence 通道恒选; 表观通道 = target_epis 中在 schema 存在的(忽略大小写)。
    target_epis 为空/None -> 纯 sequence 预测 (表观通道不参与训练与预测)。
    """
    channel_names = list(schema.get("channel_names") or [])
    if not channel_names:
        raise ValueError("feature_schema.json 缺少 channel_names")
    seq_len = int(schema.get("sequence_length", 23))

    seq_idx = [i for i, ch in enumerate(channel_names) if str(ch) in SEQ_LETTERS]
    if not seq_idx:
        raise ValueError("schema.channel_names 中未找到序列碱基通道 (A/C/G/T)")
    epi_all = [ch for i, ch in enumerate(channel_names) if i not in seq_idx]

    req = [str(e).strip().lower() for e in (target_epis or [])] if target_epis else []
    if req:
        missing = [e for e in req if e not in {c.lower() for c in epi_all}]
        if missing:
            print(f"[WARN] 目标表观通道不在数据 schema 中, 已忽略: {missing}")
    chosen_epi = [c for c in epi_all if c.lower() in req]

    keep = sorted(seq_idx + [channel_names.index(c) for c in chosen_epi])
    kept = [channel_names[i] for i in keep]
    plan = {
        "keep": keep,
        "channels": kept,
        "seq_letters": [channel_names[i] for i in seq_idx],
        "epi": chosen_epi,
        "n_seq": len(seq_idx),
        "n_channels": len(keep),
        "seq_len": seq_len,
        "feature_names": [f"pos{p}_{ch}" for p in range(1, seq_len + 1) for ch in kept],
    }
    return plan


def subset_arrays_3d(X3: np.ndarray, plan: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """按 plan 裁剪 (N,23,C) -> (N,23,K) 并展平 (N,23*K)。"""
    Xs = np.asarray(X3)[:, :, plan["keep"]]
    return Xs, Xs.reshape(len(Xs), -1)


def detect_sequence_column(df: pd.DataFrame) -> Optional[str]:
    for c in SEQ_COL_CANDIDATES:
        if c in df.columns:
            return c
    for c in df.columns:
        if "sgrna" in str(c).lower() or "seq" in str(c).lower():
            return c
    return None


def load_target_dataframe(target_input: str) -> Tuple[pd.DataFrame, str]:
    """读入目标待测数据集 (CSV 文件或含 CSV 的目录); 返回 (df, 使用文件路径)。"""
    p = Path(target_input)
    if p.is_dir():
        csvs = sorted(p.glob("*.csv")) + sorted(p.glob("*.CSV"))
        usable = []
        for f in csvs:
            try:
                df = pd.read_csv(f)
                if detect_sequence_column(df) is not None:
                    usable.append((f, df))
            except Exception:
                continue
        if not usable:
            raise FileNotFoundError(f"目录 {target_input} 下没有可用的目标序列 CSV")
        f, df = usable[0]
        return df, str(f)
    if p.is_file():
        return pd.read_csv(p), str(p)
    raise FileNotFoundError(f"目标待测数据集不存在: {target_input}")


def build_target_features(df: pd.DataFrame, schema: Dict, plan: Dict) -> Tuple[np.ndarray, str]:
    """把目标 CSV 编码为与训练一致的 (M,23,K) (通道顺序=plan, 保 schema 序)。

    序列: 4 碱基 One-Hot (仅 plan 中出现的碱基通道)。
    表观: 值=长度 23 的字符串(字符 1/A/Y/T=1, 其余=0) 或数值标量(整行填充);
          文件缺少所选表观列 -> 该通道全 0 并警告。
    """
    seq_col = detect_sequence_column(df)
    if seq_col is None:
        raise ValueError("目标 CSV 未找到序列列 (sgRNA/sequence/23nt/protospacer)")
    n = len(df)
    X = np.zeros((n, plan["seq_len"], plan["n_channels"]), dtype=np.float32)
    base_to_plan = {}
    for plan_i, ch in enumerate(plan["channels"]):
        if ch in SEQ_LETTERS:
            base_to_plan[ch] = plan_i
    epi_idx = {epi: plan["channels"].index(epi) for epi in plan["epi"]}
    missing_epi = []
    for i, (_, row) in enumerate(df.iterrows()):
        s = str(row[seq_col]).upper().strip() if pd.notna(row[seq_col]) else ""
        s = s.ljust(plan["seq_len"], "N")[:plan["seq_len"]]
        for p in range(plan["seq_len"]):
            b = s[p]
            if b in base_to_plan:
                X[i, p, base_to_plan[b]] = 1.0
        for epi_name in plan["epi"]:
            col = None
            for c in df.columns:
                if epi_name.lower() in str(c).lower():
                    col = c
                    break
            if col is None:
                if epi_name not in missing_epi:
                    missing_epi.append(epi_name)
                continue  # 缺失列 -> 0 (提示在下方统一给出)
            val = row[col]
            if isinstance(val, str) and len(val) == plan["seq_len"]:
                for p in range(plan["seq_len"]):
                    X[i, p, epi_idx[epi_name]] = 1.0 if val[p] in ("1", "A", "Y", "T") else 0.0
            elif isinstance(val, (int, float, np.number)) and not isinstance(val, bool):
                X[i, :, epi_idx[epi_name]] = float(val)
    if missing_epi:
        print(f"[WARN] 目标文件缺少所选表观列 {missing_epi}, 相应通道按 0 编码 "
              f"(若这些通道目标并不具备, 建议从 --target-epigenetics 中去掉以对齐训练)")
    return X, seq_col


def resolve_target_epis_from_file(df: pd.DataFrame, schema: Dict) -> List[str]:
    channel_names = list(schema.get("channel_names") or [])
    seq_idx = {i for i, ch in enumerate(channel_names) if str(ch) in SEQ_LETTERS}
    epi_all = [ch for i, ch in enumerate(channel_names) if i not in seq_idx]
    cols_lower = {str(c).lower(): c for c in df.columns}
    present = []
    for epi in epi_all:
        if epi.lower() in cols_lower or any(epi.lower() in k for k in cols_lower):
            present.append(epi)
    return present


# ---------------------------------------------------------------------------
# 数据装载 (mixed, 按 plan 子集)
# ---------------------------------------------------------------------------

def _load_mixed_subset(data_dir: str, schema: Dict, plan: Dict,
                       cell_lines: Optional[List[str]] = None):
    from core.data.splitting.cell_line_division import (
        discover_available_cell_lines, load_cell_line,
    )
    available = discover_available_cell_lines(data_dir)
    requested = [str(c).strip().lower() for c in (cell_lines or available)]
    chosen = [c for c in requested if c in available]
    if not chosen:
        raise FileNotFoundError(f"data_dir={data_dir} 下未找到可用细胞系 (可用: {available})")

    X3s, ys, metas = [], [], []
    for cl in chosen:
        ds = load_cell_line(data_dir=data_dir, cell_line=cl, schema=schema)
        X3s.append(np.asarray(ds["X_3d"], dtype=np.float32))
        ys.append(np.asarray(ds["y"], dtype=np.float32).reshape(-1))
        metas.append(ds["metadata"].reset_index(drop=True))
    X3 = np.concatenate(X3s, axis=0)
    y = np.concatenate(ys, axis=0)
    meta = pd.concat(metas, axis=0, ignore_index=True)
    X3, X2 = subset_arrays_3d(X3, plan)
    return X3, X2, y, meta, chosen


# ---------------------------------------------------------------------------
# Ultimate 模型 (10 折 CV 超参选择 + 全量重训)
# ---------------------------------------------------------------------------

def _expand_ultimate_models(selected_models: Optional[List[str]]) -> List[str]:
    kinds: List[str] = []
    for m in (selected_models or ALL_MODELS):
        m = str(m).lower()
        if m in ("lr",) or "linear" in m:
            if "lr" not in kinds:
                kinds.append("lr")
        elif "xgb" in m:
            if "xgboost" not in kinds:
                kinds.append("xgboost")
        elif m == "mlp":
            kinds.append("mlp")
        elif m == "cnn":
            for k in ("cnn33", "cnn53", "cnn73"):
                kinds.append(k)
        elif m in ULTIMATE_MODEL_MAP and m not in kinds:
            kinds.append(m)
    return kinds or ["lr"]


def _build_torch_model(kind: str, input_dim_2d: int, input_dim_3d_channels: int,
                       cfg: Dict, device: str, n_seq_channels: int):
    """构建 torch 模型 (n_seq_channels 由通道规划给出, 兼容 7ch/8ch 池)。"""
    if kind == "mlp":
        from core.models.mlp.mlp import MLPModel
        model = MLPModel(
            input_dim=input_dim_2d,
            hidden_dim1=int(cfg.get("hidden_dim1", 128)),
            hidden_dim2=64,
            dropout=float(cfg.get("dropout", 0.2)),
        )
        return model

    env_channels = max(int(input_dim_3d_channels) - int(n_seq_channels), 0)
    if kind.startswith("cnn"):
        seq_k = int(kind[3])  # cnn33 -> 3
        from core.models.cnn.cnn import CNNModel
        model = CNNModel(
            sequence_channels=n_seq_channels,
            environment_channels=env_channels,
            sequence_kernel=seq_k,
            environment_kernel=3,
            dropout=float(cfg.get("dropout", 0.2)),
        )
        return model

    if kind == "transformer":
        from core.models.transformer.transformer import TransformerModel
        model = TransformerModel(
            input_dim=int(input_dim_3d_channels),
            d_model=64,
            nhead=4,
            num_layers=2,
            dropout=float(cfg.get("dropout", 0.2)),
        )
        return model

    raise ValueError(f"未知 ultimate 模型: {kind}")


def _fit_torch_model(model, X: np.ndarray, y: np.ndarray, cfg: Dict,
                     device: str, epochs: int, seed: int):
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(int(seed))
    np.random.seed(int(seed))
    model = model.to(device)
    Xt = torch.tensor(X, dtype=torch.float32)
    yt = torch.tensor(y, dtype=torch.float32).reshape(-1, 1)
    loader = DataLoader(TensorDataset(Xt, yt), batch_size=256, shuffle=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(cfg.get("lr", 1e-3)), weight_decay=0.0)
    loss_fn = nn.MSELoss()

    model.train()
    for _ in range(int(epochs)):
        for xb, yb in loader:
            optimizer.zero_grad()
            out = model(xb.to(device))
            loss = loss_fn(out, yb.to(device))
            loss.backward()
            optimizer.step()
    return model


def _drop_lr_reference_columns(X2: np.ndarray, feature_names: List[str]):
    """线性终极模型与 data_digging 网格 LR 一致的参照处理:
    若列名含 _T (完整 A/C/G/T One-Hot), 剔除 _T 参照列 (T 为基准)。"""
    from core.models.linear.linear_regression import select_non_t_reference_features
    X_sub, names_sub, keep = select_non_t_reference_features(
        np.asarray(X2, dtype=np.float64), list(feature_names))
    if keep:
        return X_sub, list(names_sub)
    return np.asarray(X2, dtype=np.float64), list(feature_names)


def _fit_model(kind: str, cfg: Dict, X2: np.ndarray, X3: np.ndarray, y: np.ndarray,
               tr_idx: np.ndarray, device: str, epochs: int, seed: int,
               n_seq_channels: int):
    if kind == "lr":
        from core.models.linear.linear_regression import LinearRegressionModel
        model = LinearRegressionModel(use_scaler=bool(cfg.get("use_scaler", False)))
        model.fit(X2[tr_idx], y[tr_idx])
        return model

    if kind == "xgboost":
        import xgboost as xgb
        model = xgb.XGBRegressor(
            n_estimators=int(cfg.get("n_estimators", 100)),
            max_depth=int(cfg.get("max_depth", 3)),
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            n_jobs=-1,
            random_state=int(seed),
        )
        model.fit(X2[tr_idx], y[tr_idx])
        return model

    model = _build_torch_model(kind, X2.shape[1], X3.shape[2], cfg, device, n_seq_channels)
    use_2d = kind in KIND_USES_2D
    X = X2 if use_2d else X3
    return _fit_torch_model(model, X[tr_idx], y[tr_idx], cfg, device, epochs, seed)


def _predict_model(kind: str, model, X: np.ndarray, device: str = "cpu") -> np.ndarray:
    if kind not in TORCH_KINDS:  # lr / xgboost
        return np.asarray(model.predict(X), dtype=np.float64).reshape(-1)

    import torch
    model.eval()
    Xt = torch.tensor(X, dtype=torch.float32)
    outs = []
    with torch.no_grad():
        for i in range(0, len(Xt), 2048):
            outs.append(model(Xt[i:i + 2048].to(device)).detach().cpu().numpy().reshape(-1))
    return np.concatenate(outs) if outs else np.zeros(len(X))


def _run_ultimate_cv(kind: str, cfg: Dict, X2: np.ndarray, X3: np.ndarray, y: np.ndarray,
                     folds: int, device: str, epochs: int, seed: int, n_seq_channels: int):
    """对单个超参配置执行 K 折交叉验证, 返回 (mean_r2, mean_rmse, std_r2)。"""
    from sklearn.metrics import r2_score
    from sklearn.model_selection import KFold

    kf = KFold(n_splits=int(folds), shuffle=True, random_state=int(seed))
    X_all = X2 if kind in KIND_USES_2D else X3
    r2_list, rmse_list = [], []
    for tr, va in kf.split(np.arange(len(y))):
        model = _fit_model(kind, cfg, X2, X3, y, tr, device, epochs, seed, n_seq_channels)
        pred = np.clip(_predict_model(kind, model, X_all[va], device), 0.0, 1.0)
        r2_list.append(float(r2_score(y[va], pred)))
        rmse_list.append(float(np.sqrt(np.mean((y[va] - pred) ** 2))))
    return float(np.mean(r2_list)), float(np.mean(rmse_list)), float(np.std(r2_list))


def _atomic_bytes(path: str, data: bytes) -> None:
    """原子写: 先写同目录临时文件再 rename, 保证“文件存在即完整”。"""
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _save_ultimate_model(kind: str, model, best: Dict, feature_names: List[str],
                         ultimate_dir: str) -> Dict:
    os.makedirs(ultimate_dir, exist_ok=True)
    info = {
        "model": kind,
        "display": ULTIMATE_DISPLAY.get(kind, kind),
        "best_config": best.get("config", {}),
        "cv_r2_mean": best.get("cv_r2", np.nan),
        "cv_rmse_mean": best.get("cv_rmse", np.nan),
        "cv_r2_std": best.get("cv_r2_std", np.nan),
        "n_features": len(feature_names),
    }

    if kind == "lr":
        info["feature_names"] = feature_names
        info["weights"] = np.asarray(model.weights).tolist()
        info["std_errors"] = np.asarray(model.std_errors).tolist()
        info["t_stats"] = np.asarray(model.t_stats).tolist()
        info["use_scaler"] = bool(getattr(model, "use_scaler", False))
        file_path = os.path.join(ultimate_dir, f"ultimate_{kind}_model.json")
        _atomic_bytes(file_path, json.dumps(info, indent=4, ensure_ascii=False).encode("utf-8"))
    elif kind == "xgboost":
        import pickle
        file_path = os.path.join(ultimate_dir, f"ultimate_{kind}_model.pkl")
        buf = io.BytesIO()
        pickle.dump(model, buf)
        _atomic_bytes(file_path, buf.getvalue())
        _atomic_bytes(os.path.join(ultimate_dir, f"ultimate_{kind}_config.json"),
                      json.dumps(info, indent=4, ensure_ascii=False).encode("utf-8"))
    else:
        import torch
        file_path = os.path.join(ultimate_dir, f"ultimate_{kind}_model.pt")
        buf = io.BytesIO()
        torch.save({"state_dict": model.state_dict(), "config": best.get("config", {})}, buf)
        _atomic_bytes(file_path, buf.getvalue())
        _atomic_bytes(os.path.join(ultimate_dir, f"ultimate_{kind}_config.json"),
                      json.dumps(info, indent=4, ensure_ascii=False).encode("utf-8"))

    info["file"] = file_path
    return info


def train_ultimate_models(
    X2: np.ndarray,
    X3: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    selected_models: Optional[List[str]],
    ultimate_dir: str,
    cv_folds: int = 10,
    epochs: int = 15,
    device: Optional[str] = None,
    seed: int = 42,
    n_seq_channels: int = 3,
) -> Dict:
    """在给定 (已按目标通道裁剪的) mixed 数据上: 逐模型 10 折 CV 选超参 -> 全量重训。

    linear (lr) 额外执行与网格 LR 一致的 _T 参照列剔除, 保存剔除后的 feature_names。
    """
    if device is None:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    print(f"  - 计算设备: {device} | {cv_folds} 折交叉验证 | 每折训练 {epochs} epochs | "
          f"训练样本 {len(y)} | 通道数 {X3.shape[2]} (seq={n_seq_channels})")

    kinds = _expand_ultimate_models(selected_models)
    os.makedirs(ultimate_dir, exist_ok=True)

    trained: Dict = {}
    for kind in kinds:
        display = ULTIMATE_DISPLAY.get(kind, kind)
        # per-kind 输入: lr 剔除 _T 参照列
        X2v, X3v = X2, X3
        names_v = list(feature_names)
        if kind == "lr":
            X2v, names_v = _drop_lr_reference_columns(X2, feature_names)
        print(f"\n[*] Ultimate {display}: {cv_folds} 折 CV 超参选择 "
              f"({len(ULTIMATE_GRIDS.get(kind, [{}]))} 组配置)...")

        best = None
        for cfg in ULTIMATE_GRIDS.get(kind, [{}]):
            cv_r2, cv_rmse, cv_std = _run_ultimate_cv(
                kind, cfg, X2v, X3v, y, cv_folds, device, epochs, seed, n_seq_channels)
            print(f"    - config={cfg} -> CV R2={cv_r2:.4f} (RMSE={cv_rmse:.4f})")
            if best is None or cv_r2 > best["cv_r2"]:
                best = {"config": cfg, "cv_r2": cv_r2, "cv_rmse": cv_rmse, "cv_r2_std": cv_std}

        print(f"    => 最优配置: {best['config']} | CV R2={best['cv_r2']:.4f}")
        final_model = _fit_model(kind, best["config"], X2v, X3v, y, np.arange(len(y)),
                                 device, epochs, seed, n_seq_channels)
        info = _save_ultimate_model(kind, final_model, best, names_v, ultimate_dir)
        trained[kind] = {
            "model": final_model,
            "config": best["config"],
            "cv_r2": best["cv_r2"],
            "cv_rmse": best["cv_rmse"],
            "cv_r2_std": best["cv_r2_std"],
            "device": device,
            "file": info["file"],
            "names": names_v,
            "X2": X2v,
            "X3": X3v,
        }
        print(f"    [✓] saved -> {info['file']}")

    summary_path = os.path.join(ultimate_dir, "ultimate_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "n_samples": int(len(y)),
            "cv_folds": int(cv_folds),
            "epochs": int(epochs),
            "seed": int(seed),
            "n_seq_channels": int(n_seq_channels),
            "n_features": len(feature_names),
            "models": [
                {"model": k, "display": ULTIMATE_DISPLAY.get(k, k),
                 "best_config": trained[k]["config"], "cv_r2_mean": trained[k]["cv_r2"],
                 "file": trained[k]["file"]}
                for k in trained
            ],
        }, f, indent=4, ensure_ascii=False)
    print(f"[✓] Ultimate 模型参数已保存 -> {ultimate_dir} (含 {summary_path})")
    return trained


# ---------------------------------------------------------------------------
# 候选输出 赛道二_results.csv (终极模型对目标数据的真实预测共识)
# ---------------------------------------------------------------------------

def extract_locus_from_row(row: pd.Series) -> str:
    chrom = None
    for c in ["Chromosome", "chromosome", "chr", "Chrom", "chrom"]:
        if c in row and pd.notna(row[c]):
            chrom = str(row[c]).strip()
            if not chrom.startswith("chr"):
                chrom = f"chr{chrom}"
            break

    start = None
    for s in ["Start", "start", "txStart", "pos_start", "from", "chromStart"]:
        if s in row and pd.notna(row[s]):
            try:
                start = int(float(row[s]))
            except Exception:
                pass
            break

    end = None
    for e in ["End", "end", "txEnd", "pos_end", "to", "chromEnd"]:
        if e in row and pd.notna(row[e]):
            try:
                end = int(float(row[e]))
            except Exception:
                pass
            break

    if chrom and start is not None and end is not None:
        return f"{chrom}({start}~{end})"

    gene = None
    for g in ["gene", "Gene", "gene_name", "name", "symbol"]:
        if g in row and pd.notna(row[g]):
            gene = str(row[g]).strip()
            break
    if gene:
        m = re.search(r"(chr[0-9a-zA-Z]+)[:\s_]+(\d+)[-~_](\d+)", gene)
        if m:
            return f"{m.group(1)}({m.group(2)}~{m.group(3)})"
    return f"chrUnknown({gene or 'NA'})"


def match_ultimate_drivers(seq_23nt: str, lr_weights: Optional[np.ndarray],
                           feature_names: Optional[List[str]],
                           max_n: int = 4) -> str:
    """基于 Ultimate LR 系数推导候选序列自身携带的正向驱动特征与星级 (1~20nt 纯序列)。"""
    fallback = "N/A"
    if lr_weights is None or feature_names is None or len(feature_names) + 1 != len(np.asarray(lr_weights)):
        return fallback

    w = np.asarray(lr_weights, dtype=np.float64)[:-1]  # 去掉截距 (最后一列)
    if not np.isfinite(w).all():
        return fallback  # LR 权重非有限时不使用其系数

    seq_upper = str(seq_23nt).upper()
    name_to_idx = {name: i for i, name in enumerate(feature_names)}
    carried = []
    for p_idx in range(min(20, len(seq_upper))):
        base = seq_upper[p_idx]
        if base not in ["A", "G", "C", "T"]:
            continue
        fname = f"pos{p_idx + 1}_{base}"
        if fname in name_to_idx and w[name_to_idx[fname]] > 0:
            carried.append((fname, float(w[name_to_idx[fname]])))

    if not carried:
        return fallback

    carried.sort(key=lambda t: t[1], reverse=True)
    max_w = carried[0][1]
    drivers = []
    for fname, val in carried[:max_n]:
        ratio = val / max(1e-12, max_w)
        if ratio >= 0.8:
            stars = "***"
        elif ratio >= 0.5:
            stars = "**"
        elif ratio >= 0.2:
            stars = "*"
        else:
            stars = "."
        drivers.append(f"{fname}({stars})")
    return "; ".join(drivers)


def generate_track2_results_ultimate(
    trained: Dict,
    X2_target: np.ndarray,
    X3_target: np.ndarray,
    meta_target: pd.DataFrame,
    full_feature_names: List[str],
    top_k: int,
    output_path: str,
) -> str:
    """由终极模型对目标数据 X 做真实预测, 共识排序取 Top-K, 输出 赛道二_results.csv。

    每个模型使用与其训练同构的目标输入:
      lr      先按 full_feature_names 剔除 _T 参照列, 再预测 (与训练端一致);
      xgb/mlp 使用目标 X2; cnn/transformer 使用目标 X3 (通道数=训练子集)。
    """
    preds: Dict[str, np.ndarray] = {}
    for kind, entry in trained.items():
        if kind == "lr":
            X2k, _ = _drop_lr_reference_columns(X2_target, full_feature_names)
            preds[kind] = np.clip(
                _predict_model(kind, entry["model"], X2k, entry.get("device", "cpu")), 0.0, 1.0)
        elif kind in KIND_USES_2D:
            preds[kind] = np.clip(
                _predict_model(kind, entry["model"], X2_target, entry.get("device", "cpu")), 0.0, 1.0)
        else:
            preds[kind] = np.clip(
                _predict_model(kind, entry["model"], X3_target, entry.get("device", "cpu")), 0.0, 1.0)

    usable = [k for k in trained if trained[k]["cv_r2"] > 0] or list(trained)
    consensus = np.mean([preds[k] for k in usable], axis=0)

    lr_weights = None
    lr_names = None
    if "lr" in trained:
        lr_weights = getattr(trained["lr"]["model"], "weights", None)
        lr_names = trained["lr"]["names"]

    top_idx = np.argsort(consensus)[::-1][: int(top_k)]

    seq_col = detect_sequence_column(meta_target)

    rows = []
    for rank, idx in enumerate(top_idx, start=1):
        meta_row = meta_target.iloc[idx]
        real_seq = str(meta_row[seq_col]).upper().strip() if seq_col and pd.notna(meta_row[seq_col]) else "N" * 23
        real_seq = real_seq[:23].ljust(23, "N")

        breakdown = "|".join(f"{ULTIMATE_DISPLAY[k]}:{preds[k][idx]:.2f}" for k in trained)
        eff_display = f"{float(consensus[idx]):.4f} [{breakdown}]"
        model_title = f"Ultimate_Consensus ({'+'.join(ULTIMATE_DISPLAY[k] for k in usable)})"

        rows.append({
            "训练方式_细胞系": "mixed_all",
            "候选编号": f"CAND_sgRNA_{rank:03d}",
            "位点": extract_locus_from_row(meta_row),
            "候选序列(23nt)": real_seq,
            "预测编辑效率": eff_display,
            "最显著正向促进特征 (Top Positive Drivers)": match_ultimate_drivers(real_seq, lr_weights, lr_names),
            "对应模型": model_title,
        })

    df_out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_out.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[✓] 成功生成赛道二交付物 (Ultimate 交叉验证模型共识): {output_path} (Top-{len(df_out)} 高置信候选)")
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="CRISPR mixed 十折交叉验证 + 目标待测数据集预测 (Target Epigenetics). "
                    "已测数据网格挖掘请改用 data_digging.py (Training Scope).")
    parser.add_argument("--data-dir", type=str, required=True,
                        help="已处理数据目录（必须含 feature_schema.json）。必填，无默认值。\n"
                             "  DeepCRISPR -> data/processed\n"
                             "  外部数据集 -> data/processed/external")
    parser.add_argument("--results-dir", type=str, default="results/batches")
    parser.add_argument("--batch-name", default="", type=str,
                        help="输出批次名: 结果写到 results/[batch]/summary/ (为空直接 results/summary/)")
    parser.add_argument("--models", nargs="+", default=None, choices=ALL_MODELS,
                        help="终极模型 (default: 全部; cnn 展开为 3 种卷积核)")
    parser.add_argument("--cell-lines", nargs="+", default=None,
                        help="参与 mixed 十折 CV 的已测数据集/细胞系；缺省=数据目录内全部。"
                             "不再限制为 DeepCRISPR 的 4 个。")

    # 目标待测数据集 (Target Epigenetics)
    parser.add_argument("--target-input", type=str, default="",
                        help="目标待测数据集: CSV 文件或含 CSV 的目录 (调试/正式输入). "
                             "缺省 = 兼容旧行为: 对 mixed 已测池自身做 Top-K")
    parser.add_argument("--target-epigenetics", nargs="+", default=None,
                        help="目标序列【实际具备】的表观通道 (向导第4步选项3), 例如 CTCF Dnase; "
                             "缺省 = 从目标文件列自动识别")
    parser.add_argument("--candidate-top-k", type=int, default=20)
    parser.add_argument("--ultimate-dir", type=str, default=None,
                        help="终极模型参数目录 (default: results/[batch]/summary/ultimate)")
    parser.add_argument("--ultimate-cv-folds", type=int, default=10)
    parser.add_argument("--ultimate-epochs", type=int, default=15)
    parser.add_argument("--ultimate-seed", type=int, default=42)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印: 目标识别 / 通道规划对齐 / mixed 数据量 / 模型计划; 不训练、不写任何文件")
    parser.add_argument("--generate-candidates", action="store_true",
                        help="(兼容旧参数, 已无意义) 本程序始终运行 Ultimate CV+预测")
    return parser.parse_args()


def main():
    args = parse_args()
    from core.data.splitting.cell_line_division import load_feature_schema

    schema = load_feature_schema(args.data_dir)

    # 1) 通道规划 (Target Epigenetics)
    if args.target_input:
        target_df, target_file = load_target_dataframe(args.target_input)
        if args.target_epigenetics is not None:
            epis = list(args.target_epigenetics)
        else:
            epis = resolve_target_epis_from_file(target_df, schema)
            print(f"[Target] 自动识别目标表观通道: {epis or '(无 -> 纯序列)'}")
        plan = build_channel_plan(schema, epis)
        print(f"[Target] 输入: {target_file} | 序列 {len(target_df)} 条 | "
              f"通道规划: seq={plan['seq_letters']} epi={plan['epi'] or []} "
              f"({plan['n_channels']} 通道, 训练将按此裁剪对齐)")
        X3t, _ = build_target_features(target_df, schema, plan)
        meta_target = target_df.reset_index(drop=True)
        predict_mode = "target"
    else:
        channel_names = list(schema.get("channel_names") or [])
        plan = build_channel_plan(schema, [c for c in channel_names if c not in SEQ_LETTERS])
        print("[Pooled] 未提供 --target-input: 按 schema 全部通道, 对 mixed 已测池自身 Top-K (旧行为)")
        predict_mode = "pooled"

    # 2) mixed 数据按通道规划子集加载 (严格对齐训练/预测特征空间)
    X3, X2, y, meta, chosen = _load_mixed_subset(args.data_dir, schema, plan, args.cell_lines)
    feature_names = list(plan["feature_names"])
    print(f"[Mixed] {len(y)} 样本 x 23nt x {plan['n_channels']}ch | 细胞系: {chosen} | "
          f"特征 {X2.shape[1]} 维")
    assert X2.shape[1] == len(feature_names) == 23 * plan["n_channels"], \
        f"特征维度不一致: X2={X2.shape[1]} vs names={len(feature_names)}"

    # 3) mixed 十折 CV + 全量重训
    batch_name = str(args.batch_name).strip().lower().replace(" ", "_") if args.batch_name else ""
    base_dir = Path(args.results_dir) / batch_name if batch_name else Path(args.results_dir)
    summary_dir = base_dir / "summary"
    ultimate_dir = Path(args.ultimate_dir) if args.ultimate_dir else (summary_dir / "ultimate")

    # --dry-run: 只打印计划, 不训练、不建目录、不写文件
    if args.dry_run:
        kinds = _expand_ultimate_models(args.models)
        lr_drop_note = ""
        if any(f.endswith("_T") for f in feature_names):
            lr_drop_note = f" (LR 剔除 _T 参照列后 {23 * plan['n_channels'] - 23} 维, T 为基准)"
        print("\n[Dry-run] 计划摘要 (未执行任何训练/写入):")
        print(f"  - 模式            : {predict_mode} "
              f"{'(目标 ' + str(len(meta_target)) + ' 条)' if predict_mode == 'target' else '(mixed 已测池自身)'}")
        print(f"  - 通道规划        : seq={plan['seq_letters']} epi={plan['epi'] or []} "
              f"-> {plan['n_channels']} 通道 / {23 * plan['n_channels']} 维{lr_drop_note}")
        print(f"  - Mixed 训练数据  : {len(y)} 样本 x {X2.shape[1]} 维 | 细胞系: {chosen}")
        print(f"  - Ultimate 模型   : {[ULTIMATE_DISPLAY.get(k, k) for k in kinds]}")
        print(f"  - CV/训练参数     : {args.ultimate_cv_folds} 折 | {args.ultimate_epochs} epochs | seed={args.ultimate_seed}")
        print(f"  - 将输出          : {summary_dir / '赛道二_results.csv'}")
        print(f"  - 模型将保存至    : {ultimate_dir}")
        print("[Dry-run] 完成 (加 --dry-run 时为计划模式, 移除后才会真正训练与输出)")
        return

    summary_dir.mkdir(parents=True, exist_ok=True)

    # 3)+4) mixed 十折 CV + 全量重训 + 预测 (断点续跑: 完成判据为本 run 完成标记,
    #        不扫 results/batch 目录 —— 未跑完的实验目录一律忽略, 只重跑缺完成标记的模型)
    output_path = summary_dir / "赛道二_results.csv"
    run_ultimate_with_resume(
        X2=X2, X3=X3, y=y,
        feature_names=feature_names,
        selected_models=args.models,
        ultimate_dir=str(ultimate_dir),
        cv_folds=args.ultimate_cv_folds,
        epochs=args.ultimate_epochs,
        device=args.device,
        seed=args.ultimate_seed,
        n_seq_channels=plan["n_seq"],
        target_X2=X3t.reshape(len(X3t), -1) if predict_mode == "target" else X2,
        target_X3=X3t if predict_mode == "target" else X3,
        target_meta=meta_target if predict_mode == "target" else meta,
        top_k=args.candidate_top_k,
        output_path=str(output_path),
    )

    print(f"\n[✓] 赛道二_results.csv -> {output_path}")
    print(f"    Ultimate 模型(含断点标记) -> {ultimate_dir}")




# ---------------------------------------------------------------------------
# 断点续跑 (Ultimate): 完成判据 = 本 run 的完成标记 (ultimate/progress.json 条目 +
# 原子写好的 preds_<kind>.npy), 绝不扫 results/batch 目录 (未跑完实验的目录会被忽略)。
# 中断后重跑同一命令 -> 只补“没有完成标记”的模型 (CV+训练+预测)。
# ---------------------------------------------------------------------------
PROGRESS_FILE = "progress.json"


def _progress_path(ultimate_dir: str) -> str:
    return os.path.join(ultimate_dir, PROGRESS_FILE)


def _load_progress(ultimate_dir: str) -> List[Dict]:
    p = _progress_path(ultimate_dir)
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f).get("models", [])
    except Exception:
        return []


def _save_progress(ultimate_dir: str, rows: List[Dict]) -> None:
    _atomic_bytes(_progress_path(ultimate_dir),
                  json.dumps({"models": rows}, ensure_ascii=False, indent=2).encode("utf-8"))


def _kind_done(rows: List[Dict], kind: str) -> bool:
    for r in rows:
        if r.get("model") == kind and os.path.exists(r.get("preds_file", "")):
            return True
    return False


def _preds_on_target(kind: str, model, X2_full: np.ndarray, X3: np.ndarray,
                     full_feature_names: List[str], device: str) -> np.ndarray:
    """对目标(或已测池)做预测; lr 使用与训练一致的 _T 剔除列。"""
    if kind == "lr":
        PX, _ = _drop_lr_reference_columns(X2_full, full_feature_names)
    elif kind in KIND_USES_2D:
        PX = X2_full
    else:
        PX = X3
    return np.clip(_predict_model(kind, model, PX, device), 0.0, 1.0)


def _write_track2_from_preds(rows: List[Dict], preds: Dict[str, np.ndarray],
                             meta: pd.DataFrame, top_k: int, output_path: str) -> str:
    """由各模型已保存的预测数组生成 赛道二_results.csv (不再需要模型对象)。"""
    usable = [r["model"] for r in rows if float(r.get("cv_r2", -1)) > 0] or [r["model"] for r in rows]
    pred_mat = np.stack([preds[k] for k in usable], axis=0)
    consensus = pred_mat.mean(axis=0)
    top_idx = np.argsort(consensus)[::-1][: int(top_k)]

    lr_row = next((r for r in rows if r.get("model") == "lr"), None)
    lr_weights = lr_row.get("lr_weights") if lr_row else None
    lr_names = lr_row.get("lr_names") if lr_row else None

    seq_col = detect_sequence_column(meta)
    out_rows = []
    for rank, idx in enumerate(top_idx, start=1):
        meta_row = meta.iloc[idx]
        real_seq = str(meta_row[seq_col]).upper().strip() if seq_col and pd.notna(meta_row[seq_col]) else "N" * 23
        real_seq = real_seq[:23].ljust(23, "N")
        breakdown = "|".join(f"{ULTIMATE_DISPLAY[k]}:{float(preds[k][idx]):.2f}" for k in preds)
        eff = f"{float(consensus[idx]):.4f} [{breakdown}]"
        out_rows.append({
            "训练方式_细胞系": "mixed_all",
            "候选编号": f"CAND_sgRNA_{rank:03d}",
            "位点": extract_locus_from_row(meta_row),
            "候选序列(23nt)": real_seq,
            "预测编辑效率": eff,
            "最显著正向促进特征 (Top Positive Drivers)":
                match_ultimate_drivers(real_seq,
                                       np.asarray(lr_weights, dtype=np.float64) if lr_weights else None,
                                       lr_names),
            "对应模型": f"Ultimate_Consensus ({'+'.join(ULTIMATE_DISPLAY[k] for k in usable)})",
        })
    df_out = pd.DataFrame(out_rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_out.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[✓] 赛道二交付物 (断点续跑版): {output_path} (Top-{len(df_out)})")
    return output_path


def run_ultimate_with_resume(
    X2: np.ndarray, X3: np.ndarray, y: np.ndarray, feature_names: List[str],
    selected_models: Optional[List[str]], ultimate_dir: str, cv_folds: int, epochs: int,
    device: Optional[str], seed: int, n_seq_channels: int,
    target_X2: np.ndarray, target_X3: np.ndarray, target_meta: pd.DataFrame,
    top_k: int, output_path: str) -> None:
    """mixed 十折 CV + 全量重训 + 预测, 支持中断续跑 (完成判据见函数说明)。"""
    os.makedirs(ultimate_dir, exist_ok=True)
    if device is None:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    rows = _load_progress(ultimate_dir)
    kinds = _expand_ultimate_models(selected_models)
    preds: Dict[str, np.ndarray] = {}

    for kind in kinds:
        if _kind_done(rows, kind):
            row = next(r for r in rows if r.get("model") == kind)
            preds[kind] = np.load(row["preds_file"])
            print(f"[Resume] {ULTIMATE_DISPLAY.get(kind, kind)} 已完成, 跳过训练 "
                  f"(cv_r2={float(row['cv_r2']):.4f}) -> 复用 {row['preds_file']}")
            continue

        # 未完成/未开始 -> 补跑
        X2v, X3v, names_v = X2, X3, list(feature_names)
        if kind == "lr":
            X2v, names_v = _drop_lr_reference_columns(X2, feature_names)
        print(f"\n[*] Ultimate {ULTIMATE_DISPLAY.get(kind, kind)}: 补跑 {cv_folds} 折 CV "
              f"({len(ULTIMATE_GRIDS.get(kind, [{}]))} 组配置)...")
        best = None
        for cfg in ULTIMATE_GRIDS.get(kind, [{}]):
            cv_r2, cv_rmse, cv_std = _run_ultimate_cv(
                kind, cfg, X2v, X3v, y, cv_folds, device, epochs, seed, n_seq_channels)
            print(f"    - config={cfg} -> CV R2={cv_r2:.4f} (RMSE={cv_rmse:.4f})")
            if best is None or cv_r2 > best["cv_r2"]:
                best = {"config": cfg, "cv_r2": cv_r2, "cv_rmse": cv_rmse, "cv_r2_std": cv_std}
        print(f"    => 最优配置: {best['config']} | CV R2={best['cv_r2']:.4f}")

        final_model = _fit_model(kind, best["config"], X2v, X3v, y, np.arange(len(y)),
                                 device, epochs, seed, n_seq_channels)
        info = _save_ultimate_model(kind, final_model, best, names_v, ultimate_dir)

        arr = _preds_on_target(kind, final_model, target_X2, target_X3, feature_names, device)
        preds_file = os.path.join(ultimate_dir, f"preds_{kind}.npy")
        buf = io.BytesIO()
        np.save(buf, arr)
        _atomic_bytes(preds_file, buf.getvalue())

        row = {"model": kind, "config": best["config"], "cv_r2": best["cv_r2"],
               "cv_rmse": best["cv_rmse"], "cv_r2_std": best["cv_r2_std"],
               "file": info["file"], "preds_file": preds_file, "n_rows": int(arr.shape[0])}
        if kind == "lr":
            row["lr_weights"] = list(np.asarray(final_model.weights).tolist())
            row["lr_names"] = list(names_v)
        # 移除旧同模型条目后追加 (同一目录重复 run 的场景)
        rows = [r for r in rows if r.get("model") != kind]
        rows.append(row)
        _save_progress(ultimate_dir, rows)
        preds[kind] = arr
        print(f"    [✓] {ULTIMATE_DISPLAY.get(kind, kind)} 完成并已落盘完成标记")

    # 汇总 (含跳过模型)
    with open(os.path.join(ultimate_dir, "ultimate_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"n_samples": int(len(y)), "cv_folds": int(cv_folds), "epochs": int(epochs),
                   "seed": int(seed), "n_seq_channels": int(n_seq_channels),
                   "models": rows}, f, ensure_ascii=False, indent=4)

    if not preds:
        raise RuntimeError("没有可用的模型预测 (progress.json 存在但无 preds 文件?)")
    _write_track2_from_preds(rows, preds, target_meta, top_k, output_path)



if __name__ == "__main__":
    main()
