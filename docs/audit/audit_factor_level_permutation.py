#!/usr/bin/env python3
"""Evidence Tier 最终审计的定量支撑（只读）。

回答：
  1) factor 级 permutation 证据链：family 结构、BH 校验、min-p / min-FDR 的来源行
  2) min-FDR 的多重比较风险：Bonferroni/FWER 上界、重复上下文（all≡single）计数
  3) effect gate 的实际驱动模型（per-factor × per-model 主效应）
  4) direction concordance 的分母与 dead-zone 敏感性
  5) cross-model bootstrap 的单元复算（n=7 模型）
输出：stdout markdown（写入最终审计报告）
"""
from __future__ import annotations

import numpy as np
import pandas as pd

T = "results/batches/batch_20260909_full/summary/tables"   # 2026-09-13: analyse_out/ 已并入 summary/
pd.set_option("display.width", 250)


def md(rows, header):
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def main() -> None:
    perm = pd.read_csv(f"{T}/permutation_results.csv")
    main_eff = pd.read_csv(f"{T}/environment_main_effects.csv")
    boot = pd.read_csv(f"{T}/bootstrap_main_effects.csv")
    FAC = ["ctcf", "dnase", "h3k4me3", "rrbs"]

    # ---------------- 1. family 结构与 BH 校验 ----------------
    m = perm[perm.test_type == "environment_main_effect"]
    print("## 1. factor 级 permutation 证据链\n")
    print(f"- main-effect 行数 = {len(m)}；BH family 数 = {m.family_key.nunique()}；"
          f"每族行数 = {sorted(m.groupby('family_key').size().unique())}")
    print(f"- 每个 family 内的 factor 集合 = {sorted(m.groupby('family_key')['factor'].apply(lambda s: tuple(sorted(s))).iloc[0])}")
    k = m.family_key.iloc[0]
    fam = m[m.family_key == k][["factor", "p_value", "FDR"]].sort_values("p_value")
    mm = len(fam)
    R = (mm / np.arange(1, mm + 1)) * fam.p_value.values          # BH 原始 q
    q = np.minimum.accumulate(R[::-1])[::-1]                      # step-up 单调化
    print(f"\nBH 校验（family `{k}`）：stored FDR = {list(np.round(fam.FDR.values, 6))}，"
          f"手算 BH = {list(np.round(q, 6))} → {'一致' if np.allclose(q, fam.FDR.values) else '不一致'}")
    print()

    # ---------------- 2. min-p / min-FDR 与多重比较风险 ----------------
    print("## 2. min-p / min-FDR 的来源与多重比较风险\n")
    rows = []
    for f in FAC:
        s = m[m.factor == f].dropna(subset=["FDR"])
        # unique 上下文：all 与 single 在本批为重复（同一模型/细胞系，指标逐位相同）
        uniq = s.drop_duplicates(subset=["cell_line", "model", "split_type"], keep="first")
        uniq_no_all = s[s.split_type != "all"]
        imin = s.FDR.idxmin()
        r = s.loc[imin]
        rows.append([f, len(s), len(uniq_no_all), f"{s.p_value.min():.6f}", f"{s.FDR.min():.6f}",
                     f"{r.split_type}/{r.cell_line}/{r.model}", f"{r.observed_effect:.4f}",
                     f"{len(s) * s.p_value.min():.3f}", f"{len(uniq_no_all) * s.p_value.min():.3f}"])
    print(md(rows, ["factor", "contexts(全部)", "unique 上下文(去 all)", "min raw p", "min FDR",
                    "min-FDR 来源", "该行 observed ΔR²", "Bonferroni FWER(全部)", "FWER(unique)"]))
    print("\n注：BH 的 family 只含同一 (split, cell, model) 下的 4 个 factor（族大小=4），"
          "因此族内校正极小；而 factor 级取值是对 63 个上下文取最小 —— 这 63 次选择没有任何校正。\n")

    # ---------------- 3. effect gate 的驱动模型 ----------------
    print("## 3. effect gate（任一模型 |ΔR²| ≥ 0.01）的实际驱动模型\n")
    per = (main_eff[main_eff.main_r2_delta.abs() < 10]
           .groupby(["environment", "model"])["main_r2_delta"].mean().reset_index())
    rows = []
    for f in FAC:
        s = per[per.environment == f].set_index("model")["main_r2_delta"].sort_values()
        n_pass = int((s.abs() >= 0.01).sum())
        rows.append([f, f"{s.mean():+.5f}", f"{s.median():+.5f}", f"{s.abs().max():.5f}",
                     f"{s.abs().idxmax()}", n_pass, "PASS" if n_pass else "fail"])
    print(md(rows, ["factor", "模型等权均值", "模型间中位", "max|ΔR²|", "驱动模型", "≥0.01 的模型数", "effect gate"]))
    print("\n各 factor 的 per-model 主效应（ΔR²，模型等权前的原始值）：\n")
    piv = per.pivot_table(index="model", columns="environment", values="main_r2_delta").round(5)
    piv["|max|"] = piv.abs().max(axis=1).round(5)
    print(piv.to_string())
    print()

    # ---------------- 4. concordance 分母与 dead-zone ----------------
    print("## 4. direction concordance 的分母与 neutral dead-zone\n")
    rows = []
    for f in FAC:
        s = per[per.environment == f].set_index("model")["main_r2_delta"]
        n = len(s)
        pos = int((s > 0).sum())
        neg = int((s < 0).sum())
        zero = int((s == 0).sum())
        cur = max(pos, neg) / (pos + neg) if (pos + neg) else float("nan")
        # 定义 A：分母 = 全部模型
        defA = max(pos, neg) / n
        dead = {}
        for tau in (0.0, 1e-6, 1e-4, 1e-3, 0.01):
            p2 = int((s > tau).sum()); n2 = int((s < -tau).sum()); z2 = n - p2 - n2
            dead[tau] = (max(p2, n2) / (p2 + n2) if (p2 + n2) else float("nan"), z2)
        rows.append([f, n, pos, neg, zero, f"{cur:.3f}", f"{defA:.3f}",
                     f"{dead[1e-4][0]:.3f}", dead[1e-4][1], f"{dead[0.01][0]:.3f}", dead[0.01][1]])
    print(md(rows, ["factor", "n", "+", "−", "==0", "当前 concordance(分母=非零)", "定义A(分母=全部)",
                    "τ=1e-4", "τ=1e-4 中性数", "τ=0.01", "τ=0.01 中性数"]))
    print("\n|ΔR²| 的最小量级（判断是否需要 dead-zone 的数据依据）：")
    for f in FAC:
        s = per[per.environment == f]["main_r2_delta"].abs().sort_values()
        print(f"  {f}: min|Δ| = {s.iloc[0]:.3e}, 第2小 = {s.iloc[1]:.3e}, 中位 = {s.median():.3e}")
    print()

    # ---------------- 5. cross-model bootstrap 复算 ----------------
    print("## 5. cross-model bootstrap 的单元复算\n")
    rows = []
    for f in FAC:
        s = per[per.environment == f].set_index("model")["main_r2_delta"]
        b = boot[boot.feature == f].iloc[0]
        rows.append([f, len(s), f"{s.mean():.6f}", f"{b.estimate:.6f}",
                     f"[{b.ci_low:.5f}, {b.ci_high:.5f}]", bool(b.excludes_zero),
                     int(b.n_bootstrap), int(b.n_models), b.estimate_basis])
    print(md(rows, ["factor", "n(模型)", "7 模型等权均值", "stored estimate", "stored CI",
                    "CI 排除 0", "B", "n_models", "estimate_basis"]))
    print("\n7 个模型共享同一份 16 749 条训练数据、标签、预处理与划分 → 不是独立重复，"
          "该区间度量的是**跨模型归纳偏置的一致性**，不是 sgRNA 抽样的不确定性。\n")

    # ---------------- 6. 上下文相关性结构 ----------------
    print("## 6. 上下文之间的相关性结构（是否可视为独立检验）\n")
    print(f"- 共享模型：每个 factor 的 63 行只来自 7 个模型配置（每模型 9 个上下文）")
    print(f"- 共享细胞系/划分：9 个上下文 = single 4 细胞系 + all 4 留出细胞系 + mixed 1")
    print(f"- all 与 single 的 p 值完全相同（本批 all 退化为 single）→ 63 行中 28 行为重复")
    print(f"- 共享背景/序列：同一 (split, cell, model) 下的多个背景共享序列与划分")
    print()


if __name__ == "__main__":
    main()
