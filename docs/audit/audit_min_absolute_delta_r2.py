#!/usr/bin/env python3
"""审计环境因子的 |ΔR²| ≥ 0.01 门槛（minimum absolute predictive gain threshold）。

只读已有产物，回答：
  1) baseline R² 分布（按 model / split）
  2) 边级 ΔR² 与因子级 main_r2_delta 分布
  3) |ΔR²| ≥ 0.01 覆盖多少行/边，以及它在 Tier 里实际起作用的位置（per-model 均值）
  4) 该阈值是否系统性偏向某些 model / split / cell line
  5) 为什么不能用 relative improvement = ΔR² / R²_baseline 作为主判据（R²≈0 / R²<0 时）

输出：docs/audit/evidence_tier_threshold_audit.csv（明细）+ stdout markdown（贴进审计文档）
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BASE = "results/batches/batch_20260909_full/summary/tables"   # 2026-09-13: analyse_out/ 已并入 summary/
THR = 0.01
OUT_CSV = "docs/audit/evidence_tier_threshold_audit.csv"


def md_table(rows, header):
    out = ["| " + " | ".join(header) + " |",
           "| " + " | ".join("---" for _ in header) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def main() -> None:
    exp = pd.read_csv(f"{BASE}/experiment_table.csv", low_memory=False)
    edges = pd.read_csv(f"{BASE}/environment_edges.csv")
    main = pd.read_csv(f"{BASE}/environment_main_effects.csv")
    print("# |ΔR²| ≥ 0.01 门槛审计\n")

    # ---------------- 1) baseline R² 分布 ----------------
    ok = exp[exp["R2"].abs() < 10].copy()
    rows = []
    for (model, split), sub in ok.groupby(["model", "split_type"]):
        q = sub["R2"].quantile([0.05, 0.5, 0.95])
        rows.append([model, split, len(sub), f"{q[0.05]:.4f}", f"{q[0.5]:.4f}", f"{q[0.95]:.4f}",
                     int((sub["R2"] <= 0).sum()), int((sub["R2"] < THR).sum())])
    print("## 1. baseline R² 分布（剔除发散 |R²|>=10）\n")
    print(md_table(rows, ["model", "split", "n", "P5", "P50", "P95", "R²<=0 的 run 数", f"R²<{THR} 的 run 数"]))
    print()

    # ---------------- 2) ΔR² 分布 ----------------
    print("## 2. ΔR² 分布\n")
    rows = []
    # factor 级先剔除不稳定上下文 (|Δ| >= unstable_effect_threshold=10), 与管线同口径
    main_stable = main[main["main_r2_delta"].abs() < 10]
    for name, s in [("edge-level (environment_edges.delta_r2)", edges["delta_r2"]),
                    ("factor-level (environment_main_effects.main_r2_delta, |Δ|<10)",
                     main_stable["main_r2_delta"])]:
        s = pd.to_numeric(s, errors="coerce").dropna()
        rows.append([name, len(s), f"{s.min():.4f}", f"{s.quantile(.25):.4f}", f"{s.median():.4f}",
                     f"{s.quantile(.75):.4f}", f"{s.max():.4f}",
                     int((s.abs() >= THR).sum()), f"{100 * (s.abs() >= THR).mean():.1f}%"])
    print(md_table(rows, ["层级", "n", "min", "P25", "P50", "P75", "max", f"|ΔR²|>={THR}", "占比"]))
    print()

    # ---------------- 3) Tier 中真正使用阈值的位置 ----------------
    per_model = (main[main["main_r2_delta"].abs() < 10]
                 .groupby(["environment", "model"])["main_r2_delta"].mean().reset_index())
    rows = []
    for factor, sub in per_model.groupby("environment"):
        a = sub["main_r2_delta"]
        rows.append([factor, len(a), f"{a.mean():.4f}", f"{a.min():.4f}", f"{a.max():.4f}",
                     int((a.abs() >= THR).sum()), "yes" if (a.abs() >= THR).any() else "no"])
    print(f"## 3. Tier 的 `strong` 门只在这里起作用：per (factor, model) 均值，是否有任一 |ΔR²| ≥ {THR}\n")
    print(md_table(rows, ["factor", "n_models", "model 均值", "min", "max", f"|ΔR²|>={THR} 的模型数", "strong=any(...)"]))
    print()

    # ---------------- 4) 阈值偏向性 ----------------
    print("## 4. 阈值是否系统性偏向某些 model / split / cell line（边级 |ΔR²| ≥ 0.01 占比）\n")
    e = edges.copy()
    e["absd"] = pd.to_numeric(e["delta_r2"], errors="coerce").abs()
    for key in ["model", "split_type", "cell_line"]:
        rows = []
        for k, sub in e.groupby(key):
            rows.append([k, len(sub), f"{sub['absd'].median():.4f}",
                         int((sub["absd"] >= THR).sum()), f"{100 * (sub['absd'] >= THR).mean():.1f}%"])
        print(f"**by {key}**\n")
        print(md_table(rows, [key, "n_edges", "median |ΔR²|", f"|ΔR²|>={THR}", "占比"]))
        print()

    # ---------------- 5) relative improvement 的不稳定性 ----------------
    print("## 5. 为什么不能用 ΔR²/|R²_baseline| 作为主判据\n")
    par = pd.to_numeric(edges["parent_r2"], errors="coerce")
    d = pd.to_numeric(edges["delta_r2"], errors="coerce")
    rel = d / par.replace(0.0, np.nan)
    rows = [
        ["parent R² <= 0（比值符号反转/无意义）", int((par <= 0).sum()), f"{100 * (par <= 0).mean():.1f}%"],
        ["parent R² < 0.01（分母接近 0 -> 比值爆炸）", int((par < 0.01).sum()), f"{100 * (par < 0.01).mean():.1f}%"],
        ["|相对提升| > 100%（ΔR² 大于 baseline 本身）", int((rel.abs() > 1).sum()),
         f"{100 * (rel.abs() > 1).mean():.1f}%"],
        ["相对提升为负且分母为负（符号已不可解释）", int(((rel < 0) & (par < 0)).sum()),
         f"{100 * ((rel < 0) & (par < 0)).mean():.1f}%"],
    ]
    print(md_table(rows, ["相对口径的失效情形", "n_edges", "占比"]))
    print()
    print("注：分母为负时相对提升的正负号与 ΔR² 完全相反（R² 越差、比值越大），"
          "因此相对口径不能作为 Tier 判据。")

    # 明细写出
    edges.assign(abs_delta_r2=e["absd"],
                 rel_delta_r2=rel).to_csv(OUT_CSV, index=False)
    print(f"\n[write] {OUT_CSV}")


if __name__ == "__main__":
    main()
