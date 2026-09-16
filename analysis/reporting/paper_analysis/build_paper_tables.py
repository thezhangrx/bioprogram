#!/usr/bin/env python3
"""从批次产物重建论文中间表（唯一权威生成器，取代此前的孤儿 CSV）。

背景
----
审计问题 G1：`results/tables/paper/` 下 11 个论文用 CSV 此前**没有**仓库内生成器，
只有产物文件，无法确认它们对应哪个批次、也无法随批次切换而重算。本脚本为这些表
提供唯一、可复现的生成入口。

输入（只读）
------------
results/batches/<batch>/<run>/<model>_info.txt                运行配置
results/batches/<batch>/<run>/<model>_metrics.json            测试集指标
results/batches/<batch>/<run>/<model>_feature_importance.csv  白名单归因列
results/batches/<batch>/<run>/linear_regression_weights.csv   线性模型系数（无 importance 文件）
results/batches/<batch>/summary/tables/*.csv                  分析引擎产物
data/processed/<cell>_metadata.csv                            实测标签（观测性统计）

输出
----
results/tables/paper/*.csv  （22 张，含下列由本脚本生成的全部表）

用法
----
python analysis/reporting/paper_analysis/build_paper_tables.py --batch ultimate_run
"""
from __future__ import annotations

# --- 项目根引导 ---
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = _PROJECT_ROOT
CELLS = ["hct116", "hek293t", "hela", "hl60"]
CELL_LABEL = {"hct116": "HCT116", "hek293t": "HEK293T", "hela": "HeLa", "hl60": "HL60"}

#: 主归因列（每模型唯一，与 core/xai/importance 白名单一致）
PRIMARY_COL = {
    "linear": "Linear_Coefficient",
    "xgboost": "TreeSHAP",
    "mlp": "MLP_IG",
    "cnn": "CNN_IG",
    "transformer": "Transformer_Attention",
}
MODEL_DIR_HINT = {"linear": "linear", "xgboost": "xgboost", "mlp": "mlp", "cnn": "cnn",
                  "transformer": "transformer"}

#: 序列区域（1-based，含端点）
REGIONS = [("PAM-distal (1-8)", 1, 8), ("seed core (9-16)", 9, 16),
           ("PAM-proximal seed (17-20)", 17, 20), ("PAM (21-23)", 21, 23)]

UNSTABLE = 10.0          # |R²| >= 10 视为数值发散（项目既有规则）
RNG_SEED = 2024
BOOT = 2000


# --------------------------------------------------------------------------- #
# 读取
# --------------------------------------------------------------------------- #
def parse_info(run_dir: Path) -> dict:
    for f in run_dir.glob("*info*.txt"):
        info = {}
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip().lower()] = v.strip()
        return info
    return {}


def model_key(info: dict, run_name: str) -> str | None:
    m = str(info.get("model", "")).lower()
    for key in ("linear", "xgboost", "mlp", "cnn", "transformer"):
        if key in m:
            return key
    for key in ("linear", "xgboost", "mlp", "cnn", "transformer"):
        if f"_{key}_" in run_name or run_name.endswith(f"_{key}"):
            return key
    return None


def read_metrics(run_dir: Path) -> dict | None:
    for f in run_dir.glob("*metrics*.json"):
        if "validation" in f.name:
            continue
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


_POS_PAT = re.compile(r"^pos(\d+)_([A-Za-z]+)$")          # pos18_C（1-based）
_CHAN_PAT = re.compile(r"^([A-Za-z]+)_pos_(\d+)$")          # C_pos_18（0-based）


def parse_feature(feat: str) -> tuple[int, str] | None:
    """特征名 → (1-based position, channel)。兼容两种命名。"""
    feat = str(feat).strip()
    m = _POS_PAT.match(feat)
    if m:
        return int(m.group(1)), m.group(2)
    m = _CHAN_PAT.match(feat)
    if m:
        return int(m.group(2)) + 1, m.group(1)        # 原始 ISM 命名是 0-based
    return None


def load_attribution(run_dir: Path, model: str) -> pd.DataFrame | None:
    """返回列 [position, channel, attribution]（未归一化，取绝对值）。"""
    col = PRIMARY_COL[model]
    cand = list(run_dir.glob("*feature_importance*.csv")) + \
           list(run_dir.glob("*weights*.csv"))
    for f in cand:
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if "Feature" not in df.columns or col not in df.columns:
            continue
        rows = []
        for feat, val in zip(df["Feature"], df[col]):
            parsed = parse_feature(feat)
            if parsed is None:
                continue
            pos, ch = parsed
            try:
                v = float(val)
            except Exception:
                continue
            if not np.isfinite(v):
                continue
            rows.append((pos, ch, abs(v)))
        if rows:
            return pd.DataFrame(rows, columns=["position", "channel", "attribution"])
    return None


def collect_runs(batch_dir: Path) -> pd.DataFrame:
    """扫描所有 run，返回逐 run 元数据 + 位置归因剖面（归一化到和为 1）。"""
    records = []
    for run_dir in sorted(p for p in batch_dir.iterdir() if p.is_dir()):
        if run_dir.name == "summary":
            continue
        info = parse_info(run_dir)
        model = model_key(info, run_dir.name)
        if model is None:
            continue
        met = read_metrics(run_dir) or {}
        r2 = met.get("R2")
        try:
            r2 = float(r2)
        except Exception:
            r2 = np.nan
        split = str(info.get("split_type", "")).lower()
        cell = str(info.get("cell_line", "")).lower()
        env = str(info.get("environment", info.get("combination", ""))).lower()
        seed = info.get("random_seed", info.get("seed", "42"))
        kernel = info.get("sequence_kernel", info.get("kernel", ""))
        attr = load_attribution(run_dir, model)
        profile = None
        if attr is not None:
            by_pos = attr.groupby("position")["attribution"].sum()
            total = float(by_pos.sum())
            if total > 0:
                profile = (by_pos / total).reindex(range(1, 24), fill_value=0.0)
        records.append({
            "run_name": run_dir.name, "model": model, "split_type": split, "cell_line": cell,
            "environment": env, "random_seed": str(seed), "kernel": str(kernel), "R2": r2,
            "diverged": bool(np.isfinite(r2) and abs(r2) >= UNSTABLE),
            "profile": profile,
        })
    return pd.DataFrame(records)


# --------------------------------------------------------------------------- #
# 各表
# --------------------------------------------------------------------------- #
def position_profile(prof: pd.DataFrame) -> pd.DataFrame:
    """23 个位置的跨上下文平均归一化归因（每 run 先归一化，再按模型平均）。"""
    rows = []
    for model in ("cnn", "linear", "mlp", "transformer", "xgboost"):
        sel = prof[(prof.model == model) & (~prof.diverged) & prof.profile.notna()]
        if sel.empty:
            continue
        mat = np.vstack([np.asarray(v, dtype=float) for v in sel.profile])
        # 剔除常数剖面（全 0 / 无信号）
        mat = mat[mat.sum(axis=1) > 0]
        rows.append(pd.Series(mat.mean(axis=0), name=model))
    out = pd.concat(rows, axis=1)
    out.index = range(1, 24)
    out.index.name = "position"
    out["mean"] = out.mean(axis=1)
    return out.reset_index()


def region_attribution(prof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (cell, env), grp in prof[~prof.diverged].groupby(["cell_line", "environment"]):
        for model, sub in grp.groupby("model"):
            mats = [np.asarray(v, dtype=float) for v in sub.profile.dropna()]
            if not mats:
                continue
            mean_profile = np.vstack(mats).mean(axis=0)
            for name, lo, hi in REGIONS:
                rows.append({"cell_line": cell, "environment": env, "region": name,
                             "model": model,
                             "mean_norm_attribution": float(mean_profile[lo - 1:hi].sum())})
    return pd.DataFrame(rows)


def cross_model_consistency(prof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (cell, env), grp in prof[~prof.diverged].groupby(["cell_line", "environment"]):
        per_model = {}
        for model, sub in grp.groupby("model"):
            mats = [np.asarray(v, dtype=float) for v in sub.profile.dropna()]
            if mats:
                per_model[model] = np.vstack(mats).mean(axis=0)
        if len(per_model) < 2:
            continue
        models = sorted(per_model)
        rhos, overlaps = [], []
        for i in range(len(models)):
            for j in range(i + 1, len(models)):
                a, b = per_model[models[i]], per_model[models[j]]
                rho = pd.Series(a).corr(pd.Series(b), method="spearman")
                if np.isfinite(rho):
                    rhos.append(rho)
                ta = set(np.argsort(-a)[:3] + 1)
                tb = set(np.argsort(-b)[:3] + 1)
                overlaps.append(len(ta & tb) / 3.0)
        row = {"cell_line": cell, "environment": env, "n_positions": 23}
        for m in ("linear", "xgboost", "mlp", "cnn", "transformer"):
            row[f"peak_{m}"] = (int(np.argmax(per_model[m]) + 1) if m in per_model else np.nan)
        row["mean_pairwise_spearman"] = float(np.mean(rhos)) if rhos else np.nan
        row["mean_top3_overlap"] = float(np.mean(overlaps)) if overlaps else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def position18_attribution(prof: pd.DataFrame) -> pd.DataFrame:
    """第 18 位归因中 C 通道的占比（按细胞系/环境/划分/模型）。"""
    rows = []
    for (cell, env, split, model), grp in prof[~prof.diverged].groupby(
            ["cell_line", "environment", "split_type", "model"]):
        c_abs, total = [], []
        for v in grp.profile.dropna():
            arr = np.asarray(v, dtype=float)
            total.append(arr[17])
        # 需要原始（未归一化）通道拆分：重新读一次该组 run 的归因
        c_vals, t_vals = [], []
        for run_name in grp.run_name:
            attr = load_attribution(ROOT / "results" / "batches" / BATCH / run_name, model)
            if attr is None:
                continue
            sub = attr[attr.position == 18]
            c_vals.append(float(sub[sub.channel == "C"]["attribution"].sum()))
            t_vals.append(float(sub["attribution"].sum()))
        if not t_vals or sum(t_vals) == 0:
            continue
        rows.append({"cell_line": cell, "environment": env, "split_type": split, "model": model,
                     "C18_abs": float(np.mean(c_vals)) if c_vals else np.nan,
                     "pos18_total_abs": float(np.mean(t_vals)),
                     "C18_share_within_pos18": float(np.sum(c_vals) / np.sum(t_vals))})
    return pd.DataFrame(rows)


def kernel_position_profile(prof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for kernel, label in ((3, "cnn33"), (5, "cnn53"), (7, "cnn73")):
        sel = prof[(prof.model == "cnn") & (prof.kernel.astype(str) == str(kernel))
                   & (~prof.diverged) & prof.profile.notna()]
        if sel.empty:
            continue
        mat = np.vstack([np.asarray(v, dtype=float) for v in sel.profile])
        rows.append(pd.Series(mat.mean(axis=0), name=label))
    out = pd.concat(rows, axis=1)
    out.index = range(1, 24)
    out.index.name = "position"
    return out.reset_index()


def cnn_kernel_paired(prof: pd.DataFrame) -> pd.DataFrame:
    """严格配对（同划分/细胞系/环境/种子，仅核不同）的 ΔR² 与 bootstrap CI。"""
    cnn = prof[(prof.model == "cnn") & (~prof.diverged)].copy()
    cnn["kernel"] = cnn.kernel.astype(str)
    key = ["split_type", "cell_line", "environment", "random_seed"]
    piv = cnn.pivot_table(index=key, columns="kernel", values="R2", aggfunc="mean")
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for label, (a, b) in (("k5 - k3", ("5", "3")), ("k7 - k3", ("7", "3")), ("k7 - k5", ("7", "5"))):
        if a not in piv.columns or b not in piv.columns:
            continue
        d = (piv[a] - piv[b]).dropna().to_numpy()
        if d.size == 0:
            continue
        idx = rng.integers(0, d.size, size=(BOOT, d.size))
        boot = d[idx].mean(axis=1)
        rows.append({"comparison": label, "n_pairs": int(d.size), "mean_dR2": float(d.mean()),
                     "ci_low": float(np.percentile(boot, 2.5)),
                     "ci_high": float(np.percentile(boot, 97.5)),
                     "pct_positive": float((d > 0).mean()),
                     "excludes_zero": bool(np.percentile(boot, 2.5) > 0 or np.percentile(boot, 97.5) < 0)})
    return pd.DataFrame(rows)


def position18_efficacy() -> pd.DataFrame:
    """观测性统计：第 18 位碱基 × 细胞系 的实测归一化效率（来自 metadata，非模型产物）。"""
    rows = []
    merged = []
    for cell in CELLS:
        p = ROOT / "data" / "processed" / f"{cell}_metadata.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        seq_col = "sgRNA" if "sgRNA" in df.columns else df.columns[0]
        y_col = "Normalized efficacy" if "Normalized efficacy" in df.columns else df.columns[-1]
        base = df[seq_col].astype(str).str.upper().str.strip().str[17]     # 0-based 17 = 第 18 位
        eff = pd.to_numeric(df[y_col], errors="coerce")
        tmp = pd.DataFrame({"cell_line": cell, "pos18_base": base, "efficacy": eff})
        merged.append(tmp)
        for b, sub in tmp.groupby("pos18_base"):
            rows.append({"cell_line": cell, "pos18_base": b, "n": int(len(sub)),
                         "mean_efficacy": float(sub.efficacy.mean()),
                         "median_efficacy": float(sub.efficacy.median()),
                         "std_efficacy": float(sub.efficacy.std(ddof=1))})
        rows.append({"cell_line": cell, "pos18_base": "ALL", "n": int(len(tmp)),
                     "mean_efficacy": float(tmp.efficacy.mean()),
                     "median_efficacy": float(tmp.efficacy.median()),
                     "std_efficacy": float(tmp.efficacy.std(ddof=1))})
    return pd.DataFrame(rows)


def nucleotide_frequency() -> pd.DataFrame:
    rows = []
    for cell in CELLS:
        p = ROOT / "data" / "processed" / f"{cell}_metadata.csv"
        if not p.exists():
            continue
        seqs = pd.read_csv(p)["sgRNA"].astype(str).str.upper().str.strip()
        for pos in range(23):
            counts = seqs.str[pos].value_counts()
            rows.append({"cell_line": cell, "position": pos + 1,
                         **{b: float(counts.get(b, 0)) for b in ("A", "C", "G", "T")}})
    return pd.DataFrame(rows)


def derive_from_analysis(summary_dir: Path) -> dict[str, pd.DataFrame]:
    """由分析引擎产物派生 2 张因子级长/宽表（factor_level_ci 与 bootstrap_edge_by_factor
    由 make_assets.py 生成，不在此处产出）。"""
    out = {}
    tables = summary_dir / "tables"

    # (1) 长表：factor × cell_line → 平均 ΔR² 与样本数（供 Figure 6 热图）
    cl = tables / "cellline_effects.csv"
    if cl.exists():
        e = pd.read_csv(cl)
        rows = []
        for _, r in e.iterrows():
            for cell in CELLS:
                col = f"effect_{cell}"
                if col in e.columns and pd.notna(r.get(col)):
                    rows.append({"factor": r["factor"], "cell_line": cell,
                                 "mean_dR2": float(r[col]), "n": int(len(e))})
        if rows:
            long = pd.DataFrame(rows)
            long = (long.groupby(["factor", "cell_line"], as_index=False)
                        .agg(mean_dR2=("mean_dR2", "mean"), n=("mean_dR2", "size")))
            out["environment_by_cellline"] = long

    # (2) 宽表：factor → 跨模型汇总 + 每个模型的平均效应（供 Table 3）
    if cl.exists():
        e = pd.read_csv(cl)
        eff_cols = [f"effect_{c}" for c in CELLS if f"effect_{c}" in e.columns]
        e = e.assign(_mean=e[eff_cols].mean(axis=1))
        rows = []
        for factor, g in e.groupby("factor"):
            vals = g["_mean"].dropna().to_numpy()
            if vals.size == 0:
                continue
            row = {"factor": factor, "n_models": int(vals.size),
                   "mean_dR2": float(vals.mean()), "min": float(vals.min()),
                   "max": float(vals.max()),
                   "n_negative": int((vals < 0).sum()), "n_positive": int((vals > 0).sum())}
            for model, sub in g.groupby("model"):
                row[f"model_{model}"] = float(sub["_mean"].iloc[0]) if pd.notna(sub["_mean"].iloc[0]) else np.nan
            rows.append(row)
        if rows:
            out["environment_cross_model"] = pd.DataFrame(rows)

    # (3) CNN ISM 位置谱：attribution_summary.csv 的 cnn_ism 行按位置取均值。
    # 此前该表只有 2026-09-12（重构前、废弃泄漏批次）的版本且仓库内无生成脚本，
    # 现纳入权威生成器，保证与 ultimate_run 同源。
    attr_path = tables / "attribution_summary.csv"
    if attr_path.exists():
        attr = pd.read_csv(attr_path, low_memory=False)
        ci = attr[attr["method"] == "cnn_ism"]
        if len(ci):
            out["cnn_ism_position_profile"] = (
                ci.groupby("position", as_index=False)["importance"].mean())
    return out


# --------------------------------------------------------------------------- #
def main() -> int:
    global BATCH
    ap = argparse.ArgumentParser(description="从批次产物重建论文中间表")
    ap.add_argument("--batch", default="ultimate_run")
    ap.add_argument("--out", default=str(ROOT / "results" / "tables" / "paper"))
    args = ap.parse_args()
    BATCH = args.batch

    batch_dir = ROOT / "results" / "batches" / BATCH
    summary_dir = batch_dir / "summary"
    if not summary_dir.exists():
        print(f"[FATAL] 缺少分析产物: {summary_dir}（先运行 python -m analysis.pipeline）")
        return 2
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] 批次: {BATCH}")
    prof = collect_runs(batch_dir)
    print(f"[*] 扫描 run: {len(prof)}；含归因剖面: {int(prof.profile.notna().sum())}；"
          f"发散(已剔除): {int(prof.diverged.sum())}")

    written = []
    for name, frame in (
        ("position_profile_by_model", position_profile(prof)),
        ("region_attribution", region_attribution(prof)),
        ("cross_model_position_consistency", cross_model_consistency(prof)),
        ("position18_attribution", position18_attribution(prof)),
        ("kernel_position_profile", kernel_position_profile(prof)),
        ("cnn_kernel_paired", cnn_kernel_paired(prof)),
        ("position18_efficacy_by_base", position18_efficacy()),
        ("nucleotide_frequency_by_position", nucleotide_frequency()),
    ):
        path = out_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        written.append((name, frame.shape))

    for name, frame in derive_from_analysis(summary_dir).items():
        path = out_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        written.append((name, frame.shape))

    print("[✓] 已生成:")
    for name, shape in written:
        print(f"      {name}.csv  {shape}")
    print(f"[✓] 输出目录: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
