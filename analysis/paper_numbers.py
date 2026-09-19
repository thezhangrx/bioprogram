#!/usr/bin/env python3
"""汇总论文重写所需的权威数字（唯一数据源，只读）。

数据来源
--------
results/batches/ultimate_run     DeepCRISPR 权威批次（1344 run）
results/batches/ultimate_run_1   Hiranniramol（7 run）
results/batches/ultimate_run_2   Labuhn（7 run）
data/processed/*/                特征、标签与元数据

产物
----
results/paper_rewrite/authoritative_numbers.json   论文全部数字的权威来源
results/paper_rewrite/all_runs_metrics.csv         1 358 个 run 的逐 run 测试集指标

口径约定（全文一致，不得混用）
------------------------------
* ``*_metrics.json``             = **测试集**指标（本脚本唯一采信的性能口径）
* ``*_validation_metrics.json``  = 验证集指标（仅用于发散计数对照）
* ``sequence_kernel``            = CNN 序列卷积核；``environment_kernel`` 与之无关
* R² 发散定义：``|R²| > 10``，仅用于隔离计数，不参与中位数/区间
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "paper_rewrite"
OUT.mkdir(parents=True, exist_ok=True)

DIVERGENCE_THRESHOLD = 10.0
_INFO_KEYS = {
    "model", "split_type", "cell_line", "environment", "combination",
    "environment_count", "sequence_kernel", "environment_kernel", "random_seed",
    "data_fingerprint", "code_fingerprint", "env_stack_id", "split_digest",
    "group_aware", "n_train", "n_valid", "n_test",
    "audit_train_test_sequence_overlap", "audit_train_test_revcomp_overlap",
    "audit_train_test_locus_overlap", "sequence_channels", "environment_channels",
    "channel_count", "device_resolved",
}


def _parse_info(run_dir: Path) -> dict:
    outs = glob.glob(str(run_dir / "*_info.txt"))
    if not outs:
        return {}
    info: dict = {}
    for line in Path(outs[0]).read_text().splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if k in _INFO_KEYS:
            info[k] = v
    return info


def _read_metric_files(run_dir: Path) -> tuple[dict | None, dict | None]:
    """返回 (测试集指标, 验证集指标)，键统一小写。"""
    test = valid = None
    for p in run_dir.glob("*_metrics.json"):
        m = {k.lower(): v for k, v in json.loads(p.read_text()).items()
             if isinstance(v, (int, float))}
        if "validation" in p.name:
            valid = m
        else:
            test = m
    return test, valid


def collect_batch(batch: str) -> pd.DataFrame:
    rows = []
    for d in sorted((ROOT / "results" / "batches" / batch).glob("*/")):
        if d.name == "summary":
            continue
        test, valid = _read_metric_files(d)
        if test is None:
            continue
        info = _parse_info(d)
        parts = d.name.split("_")
        model = info.get("model", parts[1] if len(parts) > 1 else "?")
        seq_k = info.get("sequence_kernel", "")
        label = f"cnn_k{seq_k}" if "cnn" in str(model).lower() and seq_k else str(model)
        rows.append({
            "batch": batch,
            "run": d.name,
            "split": parts[0],
            "dataset": batch.replace("ultimate_run_1", "Hiranniramol")
                             .replace("ultimate_run_2", "Labuhn")
                             .replace("ultimate_run", "DeepCRISPR"),
            "model": model,
            "model_label": label,
            "cell_line": info.get("cell_line", ""),
            "random_seed": info.get("random_seed", ""),
            "n_train": info.get("n_train", ""),
            "n_valid": info.get("n_valid", ""),
            "n_test": info.get("n_test", ""),
            **{f"test_{k}": test[k] for k in ("r2", "pearson", "spearman", "rmse", "mae", "mse") if k in test},
            **({f"valid_{k}": valid[k] for k in ("r2",) if k in valid} if valid else {}),
        })
    return pd.DataFrame(rows)


def label_stats(npy: Path, meta: Path | None = None) -> dict:
    y = np.load(npy)
    out = {
        "n": int(len(y)),
        "mean": float(np.mean(y)),
        "sd": float(np.std(y, ddof=1)),
        "min": float(np.min(y)),
        "max": float(np.max(y)),
        "n_unique": int(len(np.unique(y))),
    }
    if meta and meta.is_file():
        out["columns"] = list(pd.read_csv(meta).columns)
    return out


def cv_signal(dataset: str) -> dict:
    """与官方划分无关的独立信号度量：全数据 5 折 CV + 标签置换零分布。"""
    from scipy.stats import pearsonr
    from sklearn.linear_model import Ridge
    from sklearn.metrics import r2_score
    from sklearn.model_selection import KFold, cross_val_predict
    from sklearn.preprocessing import StandardScaler

    base = ROOT / "data" / "processed" / dataset
    X = np.load(base / f"{dataset.lower()}_features_92.npy")
    y = np.load(base / f"{dataset.lower()}_labels.npy")
    if X.ndim > 2:
        X = X.reshape(len(X), -1)
    Xs = StandardScaler().fit_transform(X)
    pred = cross_val_predict(Ridge(alpha=1.0), Xs, y,
                             cv=KFold(5, shuffle=True, random_state=0))
    rng = np.random.default_rng(0)
    null = [r2_score(rng.permutation(y), pred) for _ in range(200)]
    return {
        "cv5_r2": float(r2_score(y, pred)),
        "cv5_pearson": float(pearsonr(y, pred)[0]),
        "null_r2_mean": float(np.mean(null)),
        "null_r2_sd": float(np.std(null)),
        "cv5_minus_null_mean": float(r2_score(y, pred) - np.mean(null)),
    }


def attribution_position_stats() -> dict:
    """位置层级归因的权威统计。

    数据来源
    --------
    ``results/tables/paper/position_profile_by_model.csv``
        5 个模型类 × 23 个位置的归一化归因谱（模型内归一化后按上下文平均）。
    ``results/tables/paper/cross_model_position_consistency.csv``
        每个（cell_line, environment）上下文下各模型的归因峰值位置。

    重要：旧稿正文曾写「跨模型平均谱峰值 = 第 18 位（0.089）」与
    「逐 run 峰值落在 17--20 的比例：XGBoost 91.7%、MLP 86.5%、Transformer 64.6%、
    CNN 54.0%、Linear 52.9%」。这两组数字**无法从上述任何产物复算**，且与复算值
    差异显著（CNN 实为 96.9%、Linear 实为 21.9%）。本函数给出可复算的权威值，
    论文一律引用它。
    """
    prof = ROOT / "results" / "tables" / "paper" / "position_profile_by_model.csv"
    cons = ROOT / "results" / "tables" / "paper" / "cross_model_position_consistency.csv"
    out: dict = {}
    if not prof.is_file():
        return {"available": False}

    p = pd.read_csv(prof, index_col=0)
    models = [c for c in p.columns if c != "mean"]
    p = p[models].astype(float)

    def _top(series, k=5):
        s = series.sort_values(ascending=False).head(k)
        return [{"position_1b": int(i), "value": float(v)} for i, v in s.items()]

    out["available"] = True
    out["n_positions"] = int(len(p))
    out["models"] = models
    out["per_model_peak"] = {
        m: {"position_1b": int(p[m].idxmax()), "value": float(p[m].max())}
        for m in models
    }
    out["mean_all_models"] = _top(p.mean(axis=1))
    non_linear = [m for m in models if m != "linear"]
    out["mean_non_linear"] = _top(p[non_linear].mean(axis=1))
    out["non_linear_models"] = non_linear
    out["mean_peak_all_models_position"] = int(p.mean(axis=1).idxmax())
    out["mean_peak_non_linear_position"] = int(p[non_linear].mean(axis=1).idxmax())

    if cons.is_file():
        c = pd.read_csv(cons)
        single = c[c["cell_line"] != "none"]
        out["n_single_contexts"] = int(len(single))
        out["n_all_contexts"] = int(len(c))
        peak = {}
        for m in models:
            col = f"peak_{m}"
            if col not in single.columns:
                continue
            v = single[col].astype(float)
            peak[m] = {
                "n_in_17_20": int(v.between(17, 20).sum()),
                "n_contexts": int(len(v)),
                "fraction_in_17_20": float(v.between(17, 20).mean()),
                "modal_position": int(v.mode().iloc[0]),
            }
        out["per_context_peak_in_17_20_single_split"] = peak
    return out


def main() -> int:
    out: dict = {}

    frames = [collect_batch(b) for b in
              ("ultimate_run", "ultimate_run_1", "ultimate_run_2")]
    runs = pd.concat(frames, ignore_index=True)
    runs["r2"] = pd.to_numeric(runs["test_r2"], errors="coerce")
    runs["divergent"] = runs["r2"].abs() > DIVERGENCE_THRESHOLD
    runs.to_csv(OUT / "all_runs_metrics.csv", index=False)
    print(f"[collect] runs: {len(runs)}  " +
          str(runs.batch.value_counts().to_dict()))

    out["run_counts"] = {k: int(v) for k, v in runs.batch.value_counts().items()}

    # ---------- 1. 发散计数（测试集口径；验证集仅作对照） ----------
    dc = runs[runs.batch == "ultimate_run"]
    out["divergence"] = {
        "threshold": DIVERGENCE_THRESHOLD,
        "test_divergent_total": int(dc.divergent.sum()),
        "test_divergent_by_split": dc[dc.divergent].split.value_counts().to_dict(),
        "test_divergent_by_model": dc[dc.divergent].model.value_counts().to_dict(),
        "valid_divergent_total": int(
            (pd.to_numeric(dc["valid_r2"], errors="coerce").abs()
             > DIVERGENCE_THRESHOLD).sum()),
        "note": "旧稿引用的 33 为验证集发散数；测试集发散数为 20，本稿以测试集口径为准。",
    }

    # ---------- 2. DeepCRISPR 按划分 × 模型 ----------
    summary = {}
    for split in ("single", "mixed", "all"):
        s = dc[dc.split == split]
        per = {}
        for lab, g in s.groupby("model_label"):
            ok = g[~g.divergent].r2.dropna()
            per[lab] = {
                "n": int(len(ok)),
                "n_divergent": int(g.divergent.sum()),
                "median_r2": float(ok.median()),
                "q1": float(ok.quantile(0.25)),
                "q3": float(ok.quantile(0.75)),
                "min": float(ok.min()),
                "max": float(ok.max()),
                "median_pearson": float(pd.to_numeric(g[~g.divergent].test_pearson,
                                                      errors="coerce").median()),
                "median_spearman": float(pd.to_numeric(g[~g.divergent].test_spearman,
                                                       errors="coerce").median()),
            }
        summary[split] = dict(sorted(per.items()))
    out["deepcrispr_splits"] = summary

    # LOCO 按留出细胞系展开
    loco = {}
    for cell in ("hct116", "hek293t", "hela", "hl60"):
        sub = dc[(dc.split == "all") & (dc.cell_line == cell) & (~dc.divergent)]
        loco[cell] = {
            "n_runs": int(len(sub)),
            "median_r2": float(sub.r2.median()),
            "by_model": {lab: float(g.r2.median()) for lab, g in
                         sub.groupby("model_label")},
        }
    out["deepcrispr_loco_by_cell"] = loco

    # ---------- 3. DeepCRISPR 逐细胞系标签与样本量 ----------
    cells = {}
    ys = []
    for cell in ("hct116", "hek293t", "hela", "hl60"):
        base = ROOT / "data" / "processed" / "DeepCRISPR"
        st = label_stats(base / f"{cell}_labels.npy", base / f"{cell}_metadata.csv")
        ys.append(np.load(base / f"{cell}_labels.npy"))
        run_dir = ROOT / "results" / "batches" / "ultimate_run" / f"single_{cell}_linear_sequence"
        if run_dir.is_dir():
            info = _parse_info(run_dir)
            st["run_sizes"] = {k: info.get(k) for k in ("n_train", "n_valid", "n_test")}
        cells[cell] = st
    pooled = np.concatenate(ys)
    cells["_pooled"] = {
        "n": int(len(pooled)), "mean": float(pooled.mean()),
        "sd": float(pooled.std(ddof=1)), "min": float(pooled.min()),
        "max": float(pooled.max()), "n_cell_lines": 4,
    }
    out["deepcrispr_cells"] = cells

    # ---------- 4. 两个外部数据集 ----------
    for batch, ds in (("ultimate_run_1", "Hiranniramol"),
                      ("ultimate_run_2", "Labuhn")):
        sub = runs[runs.batch == batch].sort_values("model_label")
        base = ROOT / "data" / "processed" / ds
        first = _parse_info(next((ROOT / "results" / "batches" / batch).glob("single_*/")))
        out[f"{ds.lower()}_single"] = {
            "n_models": int(len(sub)),
            "n_train": first.get("n_train"), "n_valid": first.get("n_valid"),
            "n_test": first.get("n_test"),
            "model": first.get("model"),
            "sequence_channels": first.get("sequence_channels"),
            "environment_channels": first.get("environment_channels"),
            "data_fingerprint": first.get("data_fingerprint"),
            "per_model": [
                {"model_label": r.model_label,
                 "r2": round(r.test_r2, 4), "pearson": round(r.test_pearson, 4),
                 "spearman": round(r.test_spearman, 4), "rmse": round(r.test_rmse, 4),
                 "mae": round(r.test_mae, 4)}
                for r in sub.itertuples()
            ],
            "label_stats": label_stats(base / f"{ds.lower()}_labels.npy",
                                       base / f"{ds.lower()}_metadata.csv"),
            "cv5_signal": cv_signal(ds),
        }

    out["attribution_position"] = attribution_position_stats()

    (OUT / "authoritative_numbers.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str))
    print(f"[write] {OUT/'authoritative_numbers.json'}")

    # ---------- 速览 ----------
    print("\n--- 发散（测试集口径）---")
    print(f"  total={out['divergence']['test_divergent_total']} "
          f"by_split={out['divergence']['test_divergent_by_split']} "
          f"| validation={out['divergence']['valid_divergent_total']}")
    for ds in ("hiranniramol", "labuhn"):
        d = out[f"{ds}_single"]
        sig = d["cv5_signal"]
        print(f"\n--- {ds}: n_train={d['n_train']} n_test={d['n_test']} "
              f"CV5 R2={sig['cv5_r2']:+.4f} null={sig['null_r2_mean']:+.4f}"
              f"±{sig['null_r2_sd']:.4f} (Δ={sig['cv5_minus_null_mean']:+.4f})")
        for r in d["per_model"]:
            print(f"    {r['model_label']:12s} R2={r['r2']:+.4f} "
                  f"r={r['pearson']:+.4f} rho={r['spearman']:+.4f}")
    print("\n--- DeepCRISPR 中位 R² ---")
    for split, per in summary.items():
        print(f"  [{split}]")
        for lab, v in per.items():
            print(f"    {lab:12s} {v['median_r2']:+.4f} "
                  f"[{v['q1']:+.4f},{v['q3']:+.4f}] n={v['n']} div={v['n_divergent']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
