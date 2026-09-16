#!/usr/bin/env python3
"""复用已有中间资产重新生成 evidence tier 资产（不重跑 1 344 次实验）。

用法:
    python scripts/regenerate_evidence_tier_assets.py            # 只做回归比对（dry-run）
    python scripts/regenerate_evidence_tier_assets.py --write     # 写回 evidence_matrix.csv

行为:
  1) 读已有 intermediate artifacts:
       tables/environment_main_effects.csv, tables/cellline_effects.csv,
       tables/bootstrap_main_effects.csv, tables/permutation_results.csv
  2) 调用唯一权威实现 environment_evidence_matrix() 重建 environment 行；
  3) motif 行原样保留（其 effect/统计门阈值取值未变：0.01 / fdr_weak）；
  4) 断言 evidence_tier 逐行不变，然后（仅 --write）写回并提供 tier 分布摘要。
"""
from __future__ import annotations


# --- 项目根引导: 保证从任意工作目录运行/被导入都能解析 core、analysis、workflows ---
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

import sys
from pathlib import Path

import pandas as pd

ROOT = _PROJECT_ROOT
sys.path.insert(0, str(ROOT))

from analysis.config import AnalysisConfig                      # noqa: E402
from analysis.evidence.integration import environment_evidence_matrix  # noqa: E402
from core.common.paths import RESULTS_BATCHES                   # noqa: E402


def _batch_from_argv(default: str = "ultimate_run") -> str:
    for i, a in enumerate(sys.argv):
        if a == "--batch" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith("--batch="):
            return a.split("=", 1)[1]
    return default


BATCH_NAME = _batch_from_argv()
TABLES = RESULTS_BATCHES / BATCH_NAME / "summary" / "tables"
MATRIX = TABLES / "evidence_matrix.csv"


def main() -> int:
    write = "--write" in sys.argv
    cfg = AnalysisConfig()
    main_eff = pd.read_csv(TABLES / "environment_main_effects.csv")
    cellline = pd.read_csv(TABLES / "cellline_effects.csv")
    boot = pd.read_csv(TABLES / "bootstrap_main_effects.csv")
    perm = pd.read_csv(TABLES / "permutation_results.csv")

    env_new = environment_evidence_matrix(main_eff, cellline, cfg,
                                          bootstrap_ci=boot, permutation=perm)
    old = pd.read_csv(MATRIX)
    old_env = old[old["feature_type"] == "environment"].set_index("feature")
    new_env = env_new.set_index("feature")

    print(f"[env] 重建 {len(env_new)} 行 | 原资产 {len(old_env)} 行")
    same = True
    for f in sorted(set(old_env.index) | set(new_env.index)):
        t_old = old_env.loc[f, "evidence_tier"] if f in old_env.index else "<missing>"
        t_new = new_env.loc[f, "evidence_tier"] if f in new_env.index else "<missing>"
        flag = "OK " if t_old == t_new else "DIFF"
        same &= (t_old == t_new)
        basis = new_env.loc[f, "strong_evidence_basis"] if f in new_env.index else "-"
        eg = new_env.loc[f, "effect_gate_pass"] if f in new_env.index else "-"
        sg = new_env.loc[f, "statistical_gate_pass"] if f in new_env.index else "-"
        print(f"  {flag} {f:<8} tier={t_new:<46} effect_gate={eg} stat_gate={sg} basis={basis}")
    for col in ("coverage", "direction_concordance", "overall_effect", "ci_excludes_zero",
                "permutation_fdr"):
        if col in old_env.columns and col in new_env.columns:
            a = pd.to_numeric(old_env[col].astype(float), errors="coerce")
            b = pd.to_numeric(new_env[col].astype(float), errors="coerce")
            diff = (a - b).abs().max()
            ok = (diff != diff) or diff < 1e-9
            same &= bool(ok)
            print(f"  [col] {col:<22} max|Δ| = {diff if diff == diff else 0:.2e} {'OK' if ok else 'DIFF'}")

    if not same:
        print("\n[ABORT] Tier 或关键列发生变化 -> 生产规则被改动, 需人工确认后再写入。")
        return 1

    if not write:
        print("\n[dry-run] Tier 与关键列逐行一致；加 --write 才会写回 evidence_matrix.csv")
        return 0

    motif = old[old["feature_type"] != "environment"]
    merged = pd.concat([env_new.reset_index(), motif], ignore_index=True, sort=False)
    merged.to_csv(MATRIX, index=False)
    print(f"\n[write] {MATRIX} ({len(merged)} 行; environment {len(env_new)} + motif {len(motif)})")
    print(merged.groupby(["feature_type", "evidence_tier"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
