#!/usr/bin/env python3
"""R1–R7 阶段化再生成工具（复用 analyse 引擎的同一函数，不重训模型）。

用法:
    python scripts/regenerate_permutation_and_evidence.py            # dry-run：比对差异
    python scripts/regenerate_permutation_and_evidence.py --write     # 写回 permutation/evidence 资产

做三件事（与 analysis/pipeline.py 的调用完全一致）：
  1) table -> compute_conditional_increments -> summarize_conditional -> compute_main_effects
  2) permutation_environment_edges + permutation_main_effects + permutation_interactions -> apply_fdr
  3) environment_evidence_matrix（环境行）+ 保留 motif 行 -> evidence_matrix.csv
并对"改动前 / 改动后"的 permutation 行数与 factor 级 min-FDR/FWER 做对照。
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

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.config import AnalysisConfig                                  # noqa: E402
from analysis.data.loaders import load_experiment_table                     # noqa: E402
from analysis.environment.incremental_effect import (compute_conditional_increments,
                                                    compute_main_effects,
                                                    summarize_conditional)  # noqa: E402
from analysis.evidence.integration import environment_evidence_matrix       # noqa: E402
from analysis.stats.tasks import (apply_fdr, bootstrap_main_effects,        # noqa: E402
                                 permutation_environment_edges,
                                 permutation_interactions, permutation_main_effects)

BATCH = ROOT / "results" / "batch_20260909_full"
TABLES = BATCH / "summary" / "tables"
FAC = ["ctcf", "dnase", "h3k4me3", "rrbs"]


def build_permutation(table, cond_summary, cfg):
    parts = [permutation_environment_edges(BATCH, table, config=cfg)]
    if cond_summary is not None:
        parts.append(permutation_main_effects(cond_summary, config=cfg))
    parts.append(permutation_interactions(BATCH, table, config=cfg))
    perm = pd.concat([p for p in parts if p is not None and not p.empty], ignore_index=True)
    return apply_fdr(perm, config=cfg)


def factor_summary(perm: pd.DataFrame) -> pd.DataFrame:
    m = perm[perm.test_type == "environment_main_effect"]
    rows = []
    for f in FAC:
        s = m[m.factor == f].dropna(subset=["FDR"])
        if s.empty:
            rows.append({"factor": f, "n_contexts": 0, "min_p": np.nan, "min_fdr": np.nan,
                         "selected_context": "", "fwer_unique": np.nan})
            continue
        i = s.FDR.idxmin()
        r = s.loc[i]
        uniq = s[s.split_type != "all"]
        rows.append({"factor": f, "n_contexts": len(s),
                     "min_p": float(s.p_value.min()), "min_fdr": float(s.FDR.min()),
                     "selected_context": f"{r.split_type}/{r.cell_line}/{r.model}",
                     "fwer_unique": float(len(uniq) * s.p_value.min())})
    return pd.DataFrame(rows)


def main() -> int:
    write = "--write" in sys.argv
    cfg = AnalysisConfig()
    table = load_experiment_table(BATCH)
    cond_raw = compute_conditional_increments(table)
    cond_summary = summarize_conditional(cond_raw)
    main_df = compute_main_effects(cond_raw)

    print("=== 生成新的 permutation 资产（R1 过滤生效）===")
    perm_new = build_permutation(table, cond_summary, cfg)
    old = pd.read_csv(TABLES / "permutation_results.csv")
    old_main = old[old.test_type == "environment_main_effect"]

    print(f"  行数: 旧 {len(old)} -> 新 {len(perm_new)}")
    print(f"  main-effect 中 |observed_effect| > 10 的行: 旧 {int((old_main.observed_effect.abs() > 10).sum())} "
          f"-> 新 {int((perm_new[perm_new.test_type == 'environment_main_effect'].observed_effect.abs() > 10).sum())}")
    print(f"  main-effect 中 status=unavailable 的行: 旧 "
          f"{int((old_main.status != 'ok').sum())} -> 新 "
          f"{int((perm_new[perm_new.test_type == 'environment_main_effect'].status != 'ok').sum())}")
    if "n_values_excluded" in perm_new.columns:
        mm = perm_new[perm_new.test_type == "environment_main_effect"]
        print(f"  被 R1 剔除的记录数合计 = {int(mm.n_values_excluded.sum())}；"
              f"受影响上下文数 = {int((mm.n_values_excluded > 0).sum())}")

    fs_old = factor_summary(old)
    fs_new = factor_summary(perm_new)
    cmp = fs_old.merge(fs_new, on="factor", suffixes=("_old", "_new"))
    print("\n=== factor 级 min-FDR 对照（min FDR 只在数值上变化，语义在 R2 中修正）===")
    print(cmp[["factor", "n_contexts_old", "min_p_old", "min_fdr_old", "selected_context_old",
               "n_contexts_new", "min_p_new", "min_fdr_new", "selected_context_new",
               "fwer_unique_new"]].round(6).to_string(index=False))

    print("\n=== 重建 Model-Level Bootstrap Interval（R6: 新增 interval_type 列）===")
    boot_new = bootstrap_main_effects(main_df, config=cfg)
    if write:
        boot_new.to_csv(TABLES / "bootstrap_main_effects.csv", index=False)
        print(f"  [write] bootstrap_main_effects.csv ({len(boot_new)} 行, "
              f"interval_type={boot_new.interval_type.iloc[0] if len(boot_new) else '-'})")

    print("\n=== 环境证据矩阵 Tier 对照 ===")
    boot = boot_new
    cellline = pd.read_csv(TABLES / "cellline_effects.csv")
    env_new = environment_evidence_matrix(main_df, cellline, cfg, bootstrap_ci=boot,
                                          permutation=perm_new)
    old_matrix = pd.read_csv(TABLES / "evidence_matrix.csv")
    old_env = old_matrix[old_matrix.feature_type == "environment"].set_index("feature")
    new_env = env_new.set_index("feature")
    for f in FAC:
        print(f"  {f:<8} {old_env.loc[f,'evidence_tier']:<46} -> {new_env.loc[f,'evidence_tier']}")

    if not write:
        print("\n[dry-run] 未写入。加 --write 才更新 permutation_results.csv / evidence_matrix.csv")
        return 0

    perm_new.to_csv(TABLES / "permutation_results.csv", index=False)
    motif = old_matrix[old_matrix.feature_type != "environment"]
    merged = pd.concat([env_new.reset_index(), motif], ignore_index=True, sort=False)
    merged.to_csv(TABLES / "evidence_matrix.csv", index=False)
    # R7: 同步生成 evidence 汇总 markdown 与生物假设 markdown（与 pipeline 同一函数）
    from analysis.reports.markdown_report import build_evidence_md, build_hypotheses_md
    summary_dir = BATCH / "summary" / "reports"
    (summary_dir / "06_evidence_integration.md").write_text(
        build_evidence_md(merged), encoding="utf-8")
    (summary_dir / "07_biological_hypotheses.md").write_text(
        build_hypotheses_md(merged), encoding="utf-8")
    print(f"[write] {summary_dir/'06_evidence_integration.md'}")
    print(f"[write] {summary_dir/'07_biological_hypotheses.md'}")

    print(f"\n[write] {TABLES/'permutation_results.csv'} ({len(perm_new)} 行)")
    print(f"[write] {TABLES/'evidence_matrix.csv'} ({len(merged)} 行)")
    print(merged.groupby(["feature_type", "evidence_tier"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
