"""analysis.data.loaders — 从训练产物建立统一实验表 (只读, 不修改原始结果)。

输入优先顺序 (自动探测, 发现字段差异走 adapter 而不是改训练输出):
  1. <batch>/summary/metrics_tables/all_experiments.csv  (最新 schema, 含 info 键)
  2. <batch>/summary/all_experiments.csv
  3. 直接扫描实验目录 (legacy adapter, 隔离在 legacy_fallback)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from analysis.schemas import ExperimentRecord

METRIC_COLUMNS = ["R2", "MAE", "RMSE", "Pearson", "Spearman", "MSE"]
REQUIRED_ID_COLUMNS = ["model", "split_type", "cell_line", "environment"]


def resolve_batch_dir(batch_dir: str | Path, results_root: str | Path = "results") -> Path:
    """解析批次目录; 允许传 results 根目录(自动选最新含 summary 的批次)。"""
    p = Path(batch_dir)
    if p.exists():
        return p
    root = Path(results_root)
    if not root.exists():
        raise FileNotFoundError(f"结果根目录不存在: {root}")
    candidates = [d for d in root.iterdir() if d.is_dir() and d.name != "summary"]
    return max(candidates, key=lambda d: d.stat().st_mtime)


def _coerce_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def load_experiment_table(batch_dir: str | Path) -> pd.DataFrame:
    """建立统一 experiment table (DataFrame), 列: run/model/.../metrics。"""
    batch = Path(batch_dir)
    candidates = [
        batch / "summary" / "metrics_tables" / "all_experiments.csv",
        batch / "summary" / "all_experiments.csv",
    ]
    table: Optional[pd.DataFrame] = None
    source = ""
    for cand in candidates:
        if cand.exists():
            try:
                df = pd.read_csv(cand)
            except Exception as exc:  # noqa: BLE001 - 解析失败换下一候选
                raise ValueError(f"读取 {cand} 失败: {exc}") from exc
            if not df.empty:
                table = df
                source = str(cand)
                break
    if table is None:
        table = _legacy_scan_experiments(batch)
        source = "legacy-directory-scan"
    if table is None or table.empty:
        raise RuntimeError(f"在 {batch} 下未找到可用的实验指标表")

    # 字段适配: id 列大小写归一, 指标列保留 canonical 大小写 (R2/MAE/RMSE/...)
    lower2col = {str(c).strip().lower(): c for c in table.columns}
    work = table.copy()
    keep_original = set(table.columns)
    for col in REQUIRED_ID_COLUMNS + ["random_seed", "n_train", "n_valid", "n_test"]:
        actual = lower2col.get(col)
        if actual is None:
            if col != "environment":
                work[col] = pd.NA
            else:
                work[col] = "unknown"
        elif actual != col:
            work[col] = work[actual]
    for col in METRIC_COLUMNS:
        actual = lower2col.get(col.lower())
        if actual is None:
            work[col] = float("nan")
        else:
            work[col] = _coerce_float(work[actual])
    work["source_table"] = source
    # 输出统一 schema 列 (原始多余列不再暴露给分析层)
    schema_cols = (REQUIRED_ID_COLUMNS + ["random_seed", "n_train", "n_valid", "n_test"]
                   + METRIC_COLUMNS + ["source_table", "run_name"])
    work = work[[c for c in schema_cols if c in work.columns]].copy()
    return work


def _legacy_scan_experiments(batch: Path) -> Optional[pd.DataFrame]:
    """legacy adapter: 无 summary 表时直接扫实验目录 info+metrics json。"""
    rows: List[Dict[str, Any]] = []
    for exp_dir in batch.iterdir():
        if not exp_dir.is_dir() or exp_dir.name == "summary":
            continue
        info = _parse_info(exp_dir)
        if not info:
            continue
        metrics = _load_metrics_json(exp_dir)
        if not metrics:
            continue
        row: Dict[str, Any] = {
            "model": str(info.get("model", exp_dir.name)).lower(),
            "split_type": str(info.get("split_type", "single")).lower(),
            "cell_line": str(info.get("cell_line", "none")).lower(),
            "environment": str(info.get("environment", info.get("combination", "all"))).lower(),
            "random_seed": int(float(info.get("random_seed", 42) or 42)),
        }
        for key in METRIC_COLUMNS:
            row[key] = metrics.get(key, float("nan"))
        rows.append(row)
    return pd.DataFrame(rows) if rows else None


def _parse_info(exp_dir: Path) -> Dict[str, str]:
    files = list(exp_dir.glob("*info*.txt"))
    if not files:
        return {}
    info: Dict[str, str] = {}
    for line in files[0].read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip().lower()] = v.strip()
    return info


def _load_metrics_json(exp_dir: Path) -> Dict[str, Any]:
    files = [p for p in exp_dir.glob("*_metrics.json") if "validation" not in p.name]
    if not files:
        return {}
    return json.loads(files[0].read_text(encoding="utf-8", errors="ignore"))


def iter_experiment_records(table: pd.DataFrame) -> List[ExperimentRecord]:
    """把统一表逐行转为 ExperimentRecord (缺失统计量保留 NaN, 不伪造)。"""
    records: List[ExperimentRecord] = []
    for _, r in table.iterrows():
        rec = ExperimentRecord(
            experiment_id=str(r.get("run_name", "")),
            model=str(r.get("model", "unknown")),
            architecture=str(r.get("sequence_kernel", "") or "") or None,
            split_type=str(r.get("split_type", "unknown")),
            cell_line=str(r.get("cell_line", "none")),
            environment=str(r.get("environment", "unknown")),
            seed=int(float(r["random_seed"])) if pd.notna(r.get("random_seed")) else 0,
            n_train=int(float(r["n_train"])) if pd.notna(r.get("n_train")) else 0,
            n_valid=int(float(r["n_valid"])) if pd.notna(r.get("n_valid")) else 0,
            n_test=int(float(r["n_test"])) if pd.notna(r.get("n_test")) else 0,
            r2=float(r["R2"]),
            mae=float(r["MAE"]),
            rmse=float(r["RMSE"]),
            pearson=float(r["Pearson"]),
            spearman=float(r["Spearman"]),
            batch=str(r.get("source_table", "")),
            raw=r.to_dict(),
        )
        records.append(rec)
    return records


def coverage_summary(table: pd.DataFrame) -> Dict[str, Any]:
    """00_overview 所需的 model/cell-line/environment 覆盖。"""
    return {
        "experiment_count": int(len(table)),
        "valid_count": int(
            table["R2"].notna().sum()
            if "R2" in table.columns else len(table)
        ),
        "models": sorted(table["model"].dropna().unique().tolist()),
        "cell_lines": sorted(table["cell_line"].dropna().unique().tolist()),
        "environments": sorted(table["environment"].dropna().unique().tolist()),
        "splits": sorted(table["split_type"].dropna().unique().tolist()),
    }
