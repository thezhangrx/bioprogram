#!/usr/bin/env python3
"""P0 整改（A1/A2）：对已训练模型做 leakage-controlled 评估重算。

不做任何训练：直接使用每个 run 已保存的预测表，按 canonical identity policy 屏蔽
"序列已被训练池见过"的 test 行，再重算指标；同时保留旧指标以便 before→after 对照。

输出（不覆盖任何旧资产）：
    results/analysis/leakage_controlled_metrics.csv
    docs/audit/leakage_controlled_recompute.md
"""
from __future__ import annotations


# --- 项目根引导: 保证从任意工作目录运行/被导入都能解析 core、analysis、workflows ---
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

import glob
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.leakage import leakage_mask                      # noqa: E402
from core.data.splitting.cell_line_division import divide_data, discover_available_cell_lines  # noqa: E402

BATCH = ROOT / "results" / "batch_20260909_full"
ORDER = list(discover_available_cell_lines(str(ROOT / "data" / "proceeded_data")))
OUT_CSV = ROOT / "results" / "analysis" / "leakage_controlled_metrics.csv"
OUT_MD = ROOT / "docs" / "audit" / "leakage_controlled_recompute.md"
TOL = 1e-6


def split_meta(run_name: str):
    """按 run 名复现该 run 的 split（返回 test metadata 与对齐后的泄漏掩码）。"""
    if run_name.startswith("mixed_"):
        seed = int(re.search(r"seed_(\d+)", run_name).group(1))
        o = divide_data(data_dir="data/processed", split_type="mixed", cell_lines=ORDER,
                        train_fraction=.7, validation_fraction=.15, test_fraction=.15,
                        random_seed=seed)
    elif run_name.startswith("all_"):
        held = re.search(r"heldout_([a-z0-9]+)", run_name).group(1)
        o = divide_data(data_dir="data/processed", split_type="all", cell_line=held,
                        cell_lines=ORDER, train_fraction=.7, validation_fraction=.15,
                        test_fraction=.15, random_seed=42)
    else:
        return None
    return o["train_data"]["metadata"], o["test_data"]["metadata"]


def main() -> int:
    rows, skipped = [], 0
    cache = {}
    for split in ("mixed", "all"):
        runs = sorted(glob.glob(str(BATCH / f"{split}_*")))
        for r in runs:
            name = Path(r).name
            preds = [p for p in sorted(glob.glob(str(Path(r) / "*_predictions.csv")))
                     if "validation" not in p]
            if not preds:
                skipped += 1
                continue
            d = pd.read_csv(preds[0])
            if not {"y_true", "y_pred"}.issubset(d.columns):
                skipped += 1
                continue
            key = name if name in cache else None
            if key is None:
                m = split_meta(name)
                if m is None:
                    skipped += 1
                    continue
                cache[name] = m
            train_meta, test_meta = cache[name]
            y, yh = d.y_true.to_numpy(), d.y_pred.to_numpy()
            n = min(len(y), len(test_meta))
            aligned = n == len(test_meta) and np.allclose(y[:n], test_meta["Normalized efficacy"]
                                                          .to_numpy()[:n], atol=TOL)
            keep = leakage_mask(test_meta.iloc[:n], train_meta, group="sequence")
            leaked = ~keep
            old = json.loads(Path(glob.glob(str(Path(r) / "*_metrics.json"))[0]).read_text()) \
                if glob.glob(str(Path(r) / "*_metrics.json")) else {}
            rows.append({
                "run": name, "split": split,
                "model": next((k for k in ("linear", "xgboost", "mlp", "cnn", "transformer")
                               if f"_{k}" in name), "?"),
                "kernel": (re.search(r"kernel_(\d+)", name).group(1) if "kernel_" in name else "-"),
                "cell_line": (re.search(r"heldout_([a-z0-9]+)", name).group(1) if split == "all" else "mixed"),
                "environment": re.sub(r"^(mixed|all)_[a-z0-9]+_", "", name).split("_heldout")[0]
                               .replace("_kernel_", "|kernel_"),
                "n_test": int(n), "n_clean": int(keep.sum()), "n_leaked": int(leaked.sum()),
                "frac_leaked": round(float(leaked.mean()), 4),
                "aligned": bool(aligned),
                "old_R2": float(old.get("R2", np.nan)),
                "leak_controlled_R2": float(r2_score(y[:n][keep], yh[:n][keep])) if keep.sum() > 2 else np.nan,
                "leak_controlled_MAE": float(mean_absolute_error(y[:n][keep], yh[:n][keep])) if keep.sum() > 2 else np.nan,
                "leaked_subset_R2": float(r2_score(y[:n][leaked], yh[:n][leaked])) if leaked.sum() > 2 else np.nan,
            })
    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    lines = ["# P0 整改：leakage-controlled 评估重算（A1/A2）\n",
             f"- 重算 run 数：**{len(df)}**（mixed + all），跳过（缺预测/未对齐）：{skipped}",
             f"- 行对齐失败（y_true 与复现 test 不一致）的 run：**{int((~df.aligned).sum())}**",
             "- 旧指标保留在 `summary/metrics_tables/all_experiments.csv`，本表为新增资产，未覆盖任何旧结果。\n",
             "## 按 split 汇总\n"]
    for sp, g in df.groupby("split"):
        lines.append(f"### {sp}（{len(g)} runs）\n")
        lines.append("| 指标 | Old R²（含泄漏） | Leakage-controlled R² | 泄漏子集 R² | 平均泄漏比例 |")
        lines.append("| :--- | ---: | ---: | ---: | ---: |")
        lines.append(f"| 中位 | {g.old_R2.median():+.4f} | {g.leak_controlled_R2.median():+.4f} | "
                     f"{g.leaked_subset_R2.median():+.4f} | {g.frac_leaked.mean():.1%} |")
        lines.append(f"| 均值 | {g.old_R2.mean():+.4f} | {g.leak_controlled_R2.mean():+.4f} | "
                     f"{g.leaked_subset_R2.mean():+.4f} | |\n")
        top = g.groupby("model").agg(old=("old_R2", "median"),
                                     clean=("leak_controlled_R2", "median"),
                                     leaked=("leaked_subset_R2", "median"),
                                     frac=("frac_leaked", "mean")).round(4)
        lines.append(top.to_string() + "\n")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:14]))
    print(f"\n[write] {OUT_CSV}\n[write] {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
