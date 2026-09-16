#!/usr/bin/env python3
# scripts/compare_env_equivalence.py
"""
环境等价性验证 —— 当超算的数值栈与开发机审计栈不完全一致时, 量化其影响。

背景
----
开发机 (审计栈): numpy 2.5.2 / pandas 3.0.5 / scipy 1.18.0 / sklearn 1.9.0 /
                 xgboost 3.4.1 / torch 2.13.0+cu130
超算 (目标栈):   同版本号, 但 torch 必须是 cu124 build (驱动 550),
                 且 glibc 2.17 可能迫使个别包走 conda-forge 构建。

只要版本不同, "数值完全一致" 就不再是默认假设, 必须实测。
本脚本对**同名 run** 比对两批结果, 给出逐 run 的 |ΔR²| / |ΔMAE| 与最大偏差,
用于在报告中声明: 环境差异是否影响结论。

用法
----
# A. 先在超算上跑一小批参考实验 (与开发机完全相同的 run 名与配置)
cd <repo> && python workflows/training/data_digging.py --batch-name env_check --split-types single all mixed \
    --models linear xgboost mlp cnn --environments sequence sequence_ctcf \
    --workers 8 --results-dir results/batches

# B. 在开发机上跑同一批 (CPU 即可) 到 local_env_check
python workflows/training/data_digging.py --batch-name local_env_check --split-types single all mixed \
    --models linear xgboost mlp cnn --environments sequence sequence_ctcf \
    --workers 4 --results-dir results/batches
#   注意: CNN/MLP 在 CPU 与 GPU 上本就不逐位一致, 因此 A/B 比对建议只在
#         **同设备类型** 之间进行 (GPU vs GPU, 或 CPU vs CPU)。

# C. 比对
python scripts/compare_env_equivalence.py \
    --reference results/local_env_check --candidate results/env_check \
    --out results/tables/audit/env_equivalence

判定
----
* linear / xgboost: 纯 CPU 确定性实现 → 环境一致时 |ΔR²| 应为 0 (或 <1e-9)。
* mlp / cnn: 受 BLAS/CUDA kernel 影响, 允许极小漂移; 本项目阈值取 1e-4,
  超出则说明环境差异已进入"影响结论"的量级, 必须在论文中写明。
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

DETERMINISTIC_TOL = 1e-9
STOCHASTIC_TOL = 1e-4


def read_metrics(run_dir: Path) -> dict:
    for mf in run_dir.glob("*metrics*.json"):
        try:
            return json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def read_info(run_dir: Path) -> dict:
    info = {}
    for f in run_dir.glob("*info*.txt"):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip().lower()] = v.strip()
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True, help="参考批次目录 (如开发机 local_env_check)")
    ap.add_argument("--candidate", required=True, help="候选批次目录 (如超算 env_check)")
    ap.add_argument("--out", default="results/tables/audit/env_equivalence")
    args = ap.parse_args()

    ref_dir, cand_dir = Path(args.reference), Path(args.candidate)
    for d in (ref_dir, cand_dir):
        if not d.exists():
            print(f"[FATAL] 目录不存在: {d}")
            return 2

    rows, worst = [], []
    for cand_run in sorted(p for p in cand_dir.iterdir() if p.is_dir()):
        ref_run = ref_dir / cand_run.name
        if not ref_run.exists():
            continue
        info = read_info(cand_run)
        model = info.get("model", "")
        model = ("linear" if "linear" in model else "xgboost" if "xgb" in model
                 else "mlp" if "mlp" in model else "cnn" if "cnn" in model else model)
        m_ref, m_cand = read_metrics(ref_run), read_metrics(cand_run)
        if not m_ref or not m_cand:
            continue
        row = {"run_name": cand_run.name, "model": model,
               "env_ref": read_info(ref_run).get("env_fingerprint_id", ""),
               "env_cand": info.get("env_fingerprint_id", ""),
               "device_ref": read_info(ref_run).get("device_resolved", ""),
               "device_cand": info.get("device_resolved", "")}
        for key in ("R2", "MAE", "RMSE", "Pearson", "Spearman"):
            a, b = m_ref.get(key), m_cand.get(key)
            row[f"{key}_ref"] = a
            row[f"{key}_cand"] = b
            row[f"d_{key}"] = (abs(a - b) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None)
        rows.append(row)

    if not rows:
        print("[FATAL] 两批之间没有同名 run, 无法比对")
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    csv_path = out.with_name(out.name + "_runs.csv")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    fails = []
    for row in rows:
        tol = DETERMINISTIC_TOL if row["model"] in ("linear", "xgboost") else STOCHASTIC_TOL
        for key in ("R2", "MAE", "RMSE"):
            d = row.get(f"d_{key}")
            if d is None:
                continue
            if d > tol:
                fails.append((row["run_name"], key, d, tol))
        dr2 = row.get("d_R2")
        if dr2 is not None:
            worst.append((dr2, row["run_name"], row["model"]))

    worst.sort(reverse=True)
    lines = [f"# 环境等价性比对 — {cand_dir.name} vs {ref_dir.name}", "",
             f"- 可比对 run 数: {len(rows)}",
             f"- 参考栈指纹: {sorted({r['env_ref'] for r in rows})}",
             f"- 候选栈指纹: {sorted({r['env_cand'] for r in rows})}",
             f"- 参考设备: {sorted({r['device_ref'] for r in rows})}",
             f"- 候选设备: {sorted({r['device_cand'] for r in rows})}",
             f"- 判定阈值: 确定性模型 {DETERMINISTIC_TOL}, 随机模型 {STOCHASTIC_TOL}", "",
             "## |ΔR²| 最大的 5 个 run", "",
             "| run | model | \\|ΔR²\\| |", "|---|---|---|"]
    for dr2, name, model in worst[:5]:
        lines.append(f"| {name} | {model} | {dr2:.3e} |")
    lines += ["", "## 结论", ""]
    if fails:
        lines.append(f"**存在 {len(fails)} 项超出阈值** —— 环境差异已影响数值, 必须在论文中声明:")
        lines += [f"- {n} {k}: |Δ|={d:.3e} > {t:.1e}" for n, k, d, t in fails[:20]]
    else:
        lines.append("全部指标在阈值内 —— 环境差异不影响结论, 可在报告中声明为等价。")
    report = out.with_name(out.name + "_report.md")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print(f"\n输出: {csv_path}\n      {report}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
