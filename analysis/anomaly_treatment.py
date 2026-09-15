# Submit/analysis/anomaly_treatment.py
"""
CRISPR-Cas9 批量实验异常检测与治疗报告生成器
=============================================
对批量基准测试结果执行两级异常检测并生成报告：

1. 实验级异常 (Experiment-Level Anomaly)
   - 规则：相对于 sequence-only 基线，加入表观环境后 delta_R2 与 delta_RMSE 出现
     "同向变化" (同为正或同为负)。正常情况下 R2 上升应伴随 RMSE 下降 (反向)，
     同向即视为指标矛盾、结果可疑，标记对应实验。
   - 数据来源：summary/metrics_tables/all_experiments.csv (缺失时自动回退扫描实验目录)。

2. 数据级异常 (Data-Level Anomaly)
   - 规则：线性回归解析解出现数值爆炸 (|Weight| 超过阈值，默认 10.0)。
     这类系数常伴随奇异/病态矩阵，标记对应细胞系与序列环境。
   - 数据来源：各实验目录下的 linear_regression_weights.csv 等权重文件。

输出：summary/anomaly_report.md
"""

from __future__ import annotations


# --- 项目根引导: 保证从任意工作目录运行/被导入都能解析 core、analysis、workflows ---
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import glob
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


DEFAULT_COEF_THRESHOLD = 10.0
DEFAULT_SIGN_TOL = 1e-6

MODEL_NAME_MAP = {
    "linear": "linear",
    "linear_regression": "linear",
    "xgboost": "xgboost",
    "mlp": "mlp",
    "cnn": "cnn",
    "transformer": "transformer",
}


# ============================================================
# 1. 基础解析工具
# ============================================================

def parse_info_file(info_path: str) -> Dict:
    info = {}
    if not os.path.exists(info_path):
        return info
    with open(info_path, 'r', encoding='utf-8') as f:
        for line in f:
            if ':' in line:
                k, v = line.strip().split(':', 1)
                info[k.strip().lower()] = v.strip().lower()
    return info


def normalize_model(raw_model: str) -> str:
    model = str(raw_model).strip().lower()
    if "linear" in model:
        return "linear"
    if "xgb" in model:
        return "xgboost"
    if "mlp" in model:
        return "mlp"
    if "cnn" in model:
        return "cnn"
    if "trans" in model:
        return "transformer"
    return model


def normalize_cell_line(split_type: str, raw_cell_line: str) -> str:
    st = str(split_type).strip().lower()
    if st == 'mixed':
        return 'none'
    if pd.isna(raw_cell_line) or not str(raw_cell_line).strip() or str(raw_cell_line).strip().lower() in ['none', 'unknown']:
        return 'unknown'
    return str(raw_cell_line).strip().lower()


# ============================================================
# 2. 指标数据加载 (优先 metrics_tables，缺失时回退全量扫描)
# ============================================================

def load_metrics_table(batch_dir: Path) -> pd.DataFrame:
    candidate_files = [
        batch_dir / "summary" / "metrics_tables" / "all_experiments.csv",
        batch_dir / "summary" / "all_experiments.csv",
    ]
    for fpath in candidate_files:
        if fpath.exists():
            try:
                df = pd.read_csv(fpath)
                if not df.empty:
                    return df
            except Exception:
                continue

    # 回退：直接扫描实验目录下的 metrics json
    try:
        from analysis.collect_results import collect_batch
        return collect_batch(batch_dir)
    except Exception:
        pass
    try:
        from collect_results import collect_batch
        return collect_batch(batch_dir)
    except Exception:
        pass
    return pd.DataFrame()


def aggregate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """对 mixed 多种子等重复实验求平均，得到 (split_type, cell_line, model, environment) 唯一行。"""
    if df.empty:
        return df
    work = df.copy()
    for col in ['model', 'split_type', 'cell_line', 'environment']:
        if col in work.columns:
            work[col] = work[col].astype(str).str.lower().str.strip()

    if 'model' in work.columns and 'model_raw' in work.columns:
        pass
    metric_cols = [c for c in ['R2', 'MAE', 'RMSE', 'MSE'] if c in work.columns]
    if not metric_cols:
        return pd.DataFrame()

    group_cols = ['split_type', 'cell_line', 'model', 'environment']
    agg = work.groupby(group_cols, dropna=False)[metric_cols].mean().reset_index()
    return agg


# ============================================================
# 3. 实验级异常：delta_R2 与 delta_RMSE 同向
# ============================================================

def detect_experiment_level_anomalies(metrics_df: pd.DataFrame, sign_tol: float = DEFAULT_SIGN_TOL) -> pd.DataFrame:
    """
    相对 sequence-only 基线计算 delta_R2 / delta_RMSE。
    R2 与 RMSE 同向变化 (同正或同负) 的实验被标记为异常。
    """
    if metrics_df.empty:
        return pd.DataFrame()

    agg = aggregate_metrics(metrics_df)
    if agg.empty or 'environment' not in agg.columns:
        return pd.DataFrame()

    baseline = agg[agg['environment'] == 'sequence'].copy()
    if baseline.empty:
        return pd.DataFrame()

    baseline_map = {}
    for _, row in baseline.iterrows():
        key = (row['split_type'], row['cell_line'], row['model'])
        baseline_map[key] = (row.get('R2', np.nan), row.get('RMSE', np.nan))

    records = []
    for _, row in agg.iterrows():
        if row['environment'] == 'sequence':
            continue
        key = (row['split_type'], row['cell_line'], row['model'])
        if key not in baseline_map:
            continue

        base_r2, base_rmse = baseline_map[key]
        r2 = row.get('R2', np.nan)
        rmse = row.get('RMSE', np.nan)
        if pd.isna(base_r2) or pd.isna(r2) or pd.isna(base_rmse) or pd.isna(rmse):
            continue

        delta_r2 = float(r2) - float(base_r2)
        delta_rmse = float(rmse) - float(base_rmse)

        if abs(delta_r2) <= sign_tol or abs(delta_rmse) <= sign_tol:
            continue

        same_sign = (delta_r2 > 0 and delta_rmse > 0) or (delta_r2 < 0 and delta_rmse < 0)
        if not same_sign:
            continue

        direction = "同增" if delta_r2 > 0 else "同减"
        verdict = (
            f"⚠️ 指标矛盾：R2 与 RMSE {direction}"
            f" (理论上应反向，R2 上升须伴随 RMSE 下降)"
        )
        records.append({
            'split_type': row['split_type'],
            'cell_line': row['cell_line'],
            'model': row['model'],
            'environment': row['environment'],
            'R2_baseline': base_r2,
            'R2': r2,
            'delta_R2': delta_r2,
            'RMSE_baseline': base_rmse,
            'RMSE': rmse,
            'delta_RMSE': delta_rmse,
            'verdict': verdict,
        })

    return pd.DataFrame(records)


# ============================================================
# 4. 数据级异常：线性回归权重系数极大
# ============================================================

def detect_data_level_anomalies(batch_dir: Path, coef_threshold: float = DEFAULT_COEF_THRESHOLD) -> pd.DataFrame:
    """
    扫描线性回归权重文件，|Weight| 超过阈值即标记。
    聚合到 (cell_line, environment) 维度，并保留特征明细。
    """
    records = []
    weight_files = list(batch_dir.glob("**/*weights*.csv"))
    if not weight_files:
        # 兼容其它命名 (如 linear_coefficients.csv)
        weight_files = list(batch_dir.glob("**/linear*coefficient*.csv"))

    for fpath in weight_files:
        if 'summary' in str(fpath):
            continue

        exp_dir = fpath.parent
        info_files = list(exp_dir.glob("*info*.txt"))
        info = parse_info_file(str(info_files[0])) if info_files else {}

        model = normalize_model(info.get('model', exp_dir.name))
        if model != 'linear':
            continue

        split_type = str(info.get('split_type', 'unknown')).lower()
        cell_line = normalize_cell_line(split_type, info.get('cell_line', info.get('held_out_cell_line', 'unknown')))
        environment = str(info.get('environment', info.get('combination', 'unknown'))).lower()

        try:
            df = pd.read_csv(fpath)
        except Exception:
            continue

        cols_lower = {c.lower(): c for c in df.columns}
        feat_col = cols_lower.get('feature', cols_lower.get('feat', None))
        val_col = cols_lower.get('linear_coefficient', cols_lower.get('weight', cols_lower.get('coefficient', cols_lower.get('coef', None))))
        if not feat_col or not val_col:
            continue

        t_col = cols_lower.get('t_stat', cols_lower.get('t_value', None))

        for _, row in df.iterrows():
            feat_name = str(row[feat_col])
            # 截距/偏置项不是位点特征，不参与位点级异常标记
            if 'bias' in feat_name.lower() or 'intercept' in feat_name.lower():
                continue
            try:
                val = float(row[val_col])
            except Exception:
                continue
            if not np.isfinite(val) or abs(val) <= coef_threshold:
                continue

            records.append({
                'split_type': split_type,
                'cell_line': cell_line,
                'environment': environment,
                'feature': feat_name,
                'weight': val,
                't_stat': float(row[t_col]) if t_col and pd.notna(row[t_col]) else np.nan,
            })

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def aggregate_data_anomalies(detail_df: pd.DataFrame) -> pd.DataFrame:
    """按 (cell_line, environment) 聚合数据级异常。"""
    if detail_df.empty:
        return pd.DataFrame()
    agg = detail_df.groupby(['cell_line', 'environment'], as_index=False).agg(
        anomaly_count=('feature', 'count'),
        max_abs_weight=('weight', lambda s: float(np.max(np.abs(s)))),
    )
    agg['example_features'] = agg.apply(
        lambda r: "; ".join(
            detail_df[(detail_df['cell_line'] == r['cell_line']) &
                      (detail_df['environment'] == r['environment'])]
            .assign(_abs=lambda d: d['weight'].abs())
            .sort_values('_abs', ascending=False)['feature'].head(3).tolist()
        ),
        axis=1
    )
    agg = agg.sort_values('max_abs_weight', ascending=False)
    return agg


# ============================================================
# 5. 报告生成
# ============================================================

def _fmt(value, digits: int = 4) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.{digits}f}"


def build_anomaly_report(
    batch_dir: Path,
    exp_anoms: pd.DataFrame,
    data_anoms_detail: pd.DataFrame,
    data_anoms_agg: pd.DataFrame,
    metrics_found: bool,
    coef_threshold: float,
    sign_tol: float,
) -> str:
    batch_name = batch_dir.name if batch_dir.name not in ("results", "batch_run") else str(batch_dir)
    lines: List[str] = []
    lines.append(f"# Anomaly Report: {batch_name}\n")
    lines.append(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 检测范围: `{batch_dir}`")
    lines.append(f"- 实验级规则: delta_R2 与 delta_RMSE 同向 (容差 ±{sign_tol:.0e})")
    lines.append(f"- 数据级规则: |Linear Weight| > {coef_threshold:g}\n")

    # --------------------------------------------------------
    # 1. 实验级异常
    # --------------------------------------------------------
    lines.append("---\n\n## 1. 实验级异常 (指标同向矛盾)\n")
    lines.append(
        "> 规则：相对 `sequence` 基线，加入表观环境后 **R2 与 RMSE 同向变化** "
        "(同增或同减) 即标记。正常实验中 R2 与 RMSE 应反向变动。\n"
    )
    if not metrics_found:
        lines.append("⚠️ 未找到指标数据 (`summary/metrics_tables/all_experiments.csv` 与实验目录扫描均失败)，跳过实验级检测。\n")
    elif exp_anoms.empty:
        lines.append("✅ 未检测到 R2 / RMSE 同向矛盾的实验。\n")
    else:
        lines.append(f"共标记 **{len(exp_anoms)}** 个异常实验：\n")
        lines.append("| split_type | cell_line | model | environment | R2(seq) | R2 | delta_R2 | RMSE(seq) | RMSE | delta_RMSE | 判定 |")
        lines.append("| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |")
        for _, r in exp_anoms.iterrows():
            lines.append(
                f"| {r['split_type']} | {r['cell_line']} | {r['model']} | {r['environment']} "
                f"| {_fmt(r['R2_baseline'])} | {_fmt(r['R2'])} | {_fmt(r['delta_R2'])} "
                f"| {_fmt(r['RMSE_baseline'])} | {_fmt(r['RMSE'])} | {_fmt(r['delta_RMSE'])} "
                f"| {r['verdict']} |"
            )

    # --------------------------------------------------------
    # 2. 数据级异常
    # --------------------------------------------------------
    lines.append("\n---\n\n## 2. 数据级异常 (线性回归系数极大)\n")
    lines.append(
        f"> 规则：线性回归解析解中 `|Weight| > {coef_threshold:g}` 即视为数值爆炸，"
        "通常由病态/奇异设计矩阵引起，标记对应 **细胞系** 与 **序列环境**。\n"
    )
    if data_anoms_detail.empty:
        lines.append("✅ 未检测到线性回归系数极大异常。\n")
    else:
        lines.append("### 2.1 按细胞系 × 序列环境汇总\n")
        lines.append("| cell_line | environment | 异常特征数 | 最大|Weight| | 示例特征 (前3) |")
        lines.append("| :--- | :--- | ---: | ---: | :--- |")
        for _, r in data_anoms_agg.iterrows():
            lines.append(
                f"| {r['cell_line']} | {r['environment']} | {int(r['anomaly_count'])} "
                f"| {r['max_abs_weight']:.3e} | {r['example_features']} |"
            )

        lines.append("\n### 2.2 异常特征明细 (按 |Weight| 降序，最多 200 条)\n")
        detail_sorted = data_anoms_detail.assign(_abs=data_anoms_detail['weight'].abs()) \
            .sort_values('_abs', ascending=False).head(200)
        lines.append("| split_type | cell_line | environment | feature | weight | t_stat |")
        lines.append("| :--- | :--- | :--- | :--- | ---: | ---: |")
        for _, r in detail_sorted.iterrows():
            t_str = _fmt(r['t_stat'], 3)
            lines.append(
                f"| {r['split_type']} | {r['cell_line']} | {r['environment']} "
                f"| {r['feature']} | {r['weight']:.6e} | {t_str} |"
            )

    # --------------------------------------------------------
    # 3. 汇总与建议
    # --------------------------------------------------------
    lines.append("\n---\n\n## 3. 汇总统计与处置建议\n")
    lines.append(f"- 实验级异常实验数: **{len(exp_anoms)}**")
    lines.append(f"- 数据级异常特征数: **{len(data_anoms_detail)}**")
    if not exp_anoms.empty:
        lines.append("- 建议：实验级异常实验建议复核对应环境组合的训练日志与指标文件；"
                     "必要时在指标汇总 (collect_results) 中将其排除或重新训练。")
    if not data_anoms_detail.empty:
        lines.append("- 建议：数据级异常细胞系/环境建议检查特征矩阵的秩与条件数，"
                     "或对线性模型启用 `--use-scaler` 与正则化后再训练。")
    if exp_anoms.empty and data_anoms_detail.empty:
        lines.append("- 未发现异常，全部实验通过两级检测。")

    return "\n".join(lines) + "\n"


# ============================================================
# 6. 主流程
# ============================================================

def run_anomaly_treatment(
    batch_dir: str,
    summary_dir: Optional[str] = None,
    coef_threshold: float = DEFAULT_COEF_THRESHOLD,
    sign_tol: float = DEFAULT_SIGN_TOL,
) -> str:
    batch_path = Path(batch_dir)
    out_dir = Path(summary_dir) if summary_dir else (batch_path / "summary")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[*] 异常检测引擎启动 -> 目标批次: {batch_path}")
    print(f"  - 实验级规则: delta_R2 / delta_RMSE 同向 (容差 {sign_tol:.0e})")
    print(f"  - 数据级规则: |Linear Weight| > {coef_threshold:g}")

    # 1. 实验级
    metrics_df = load_metrics_table(batch_path)
    metrics_found = not metrics_df.empty
    if not metrics_found:
        print("  [!] 未找到指标数据，实验级检测跳过。")
    exp_anoms = detect_experiment_level_anomalies(metrics_df, sign_tol=sign_tol)
    print(f"  [实验级] 检测到 {len(exp_anoms)} 个同向矛盾实验")

    # 2. 数据级
    data_anoms_detail = detect_data_level_anomalies(batch_path, coef_threshold=coef_threshold)
    data_anoms_agg = aggregate_data_anomalies(data_anoms_detail)
    print(f"  [数据级] 检测到 {len(data_anoms_detail)} 条线性系数极大特征")

    # 3. 报告
    report = build_anomaly_report(
        batch_dir=batch_path,
        exp_anoms=exp_anoms,
        data_anoms_detail=data_anoms_detail,
        data_anoms_agg=data_anoms_agg,
        metrics_found=metrics_found,
        coef_threshold=coef_threshold,
        sign_tol=sign_tol,
    )
    report_path = out_dir / "anomaly_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[✓] 异常检测报告已生成 -> {report_path}")
    return str(report_path)


def main():
    parser = argparse.ArgumentParser(description="Detect & report CRISPR experiment anomalies.")
    parser.add_argument("--results-dir", type=str, default="results/batches", help="Root results directory")
    parser.add_argument("--batch-name", type=str, default="", help="Specific batch folder name")
    parser.add_argument("--batch-dir", type=str, default="", help="Direct path to batch directory")
    parser.add_argument("--latest", action="store_true", help="Process the latest batch folder")
    parser.add_argument("--summary-dir", type=str, default="", help="Custom output dir for anomaly_report.md (default: <batch>/summary)")
    parser.add_argument("--coef-threshold", type=float, default=DEFAULT_COEF_THRESHOLD,
                        help="Linear weight absolute threshold for data-level anomaly (default: 10.0)")
    parser.add_argument("--sign-tol", type=float, default=DEFAULT_SIGN_TOL,
                        help="Tolerance for zero in same-sign detection (default: 1e-6)")
    args = parser.parse_args()

    if args.batch_dir:
        batch_path = Path(args.batch_dir)
    elif args.batch_name:
        batch_path = Path(args.results_dir) / args.batch_name
    else:
        results_root = Path(args.results_dir)
        if any(d.is_dir() and d.name.startswith(("single_", "all_", "mixed_")) for d in results_root.iterdir()):
            batch_path = results_root
        else:
            sub_dirs = [d for d in results_root.iterdir() if d.is_dir() and d.name != "summary"]
            batch_path = max(sub_dirs, key=os.path.getmtime) if sub_dirs else results_root

    if not batch_path.exists():
        print(f"[Error] Target directory does not exist: {batch_path}")
        return

    run_anomaly_treatment(
        batch_dir=str(batch_path),
        summary_dir=args.summary_dir or None,
        coef_threshold=args.coef_threshold,
        sign_tol=args.sign_tol,
    )


if __name__ == "__main__":
    main()
