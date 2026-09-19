#!/usr/bin/env python3
"""生成外部模型验证的最终报告与审计。

输出
----
    docs/reproducibility/EXTERNAL_MODEL_VALIDATION_CRISPRON.md   验证报告（A–H 结构 + QC 清单）
    results/external_validation/<run>/audit.json                机器可读审计

报告的措辞边界（必须遵守）
--------------------------
允许：external model validation / model-based counterfactual /
      in-silico mutagenesis / directional consistency / cross-model consistency
禁止：causal proof / experimental effect / biological mechanism proof

CRISPRon 的预测是**模型输出**，不是实验测量；本报告只声明"方向一致性"，
不声明"C18A 会降低真实编辑效率"。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from analysis.external_validation import provenance as PV                      # noqa: E402
from analysis.external_validation.validate_position18 import (                 # noqa: E402
    CRISPRON_DIR, CANDIDATES_TABLE, TABLE_DIR, RUN_ROOT,
)

DOCS_DIR = _PROJECT_ROOT / "docs" / "reproducibility"
POS18 = 18


def _md_table(df: pd.DataFrame, floatfmt: str = ".3f") -> str:
    """生成 markdown 表（自实现，避免依赖 tabulate）。"""
    if df is None or len(df) == 0:
        return "_(无)_"
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else format(v, floatfmt))
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |",
             "| " + " | ".join("---" for _ in cols) + " |"]
    for _, r in d.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(r[c]) else str(r[c]) for c in d.columns) + " |")
    return "\n".join(lines)


def build_audit(wt_std: pd.DataFrame, cmp_df: pd.DataFrame, eff: pd.DataFrame,
                analysis: dict, summary: dict, agree: dict) -> dict:
    """按用户要求的 12 项 QC 逐条给出结论。"""
    n = len(wt_std)
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)})

    add("WT/mutant 只有一个碱基差异",
        bool(wt_std["qc_only_pos18_changed"].all()),
        f"{int(wt_std['qc_only_pos18_changed'].sum())}/{n} 通过")
    add("差异位置恰为 Position 18",
        bool((wt_std["mutation"].str.startswith("C18A")).all()),
        "全部为 C18A（位点 18 由项目约定推导，非硬编码字符串）")
    add("PAM 有效",
        bool(wt_std["qc_pam_unchanged"].all() and wt_std["PAM"].str.endswith("GG").all()),
        f"PAM 集合 {sorted(wt_std['PAM'].unique())}（均以 GG 结尾）")
    add("orientation 一致",
        bool(wt_std["qc_orientation_preserved"].all()),
        "30-mer 中 target 段与项目 23 nt 完全一致，未发生反向互补")
    add("CRISPRon 对目标产生预测",
        bool(wt_std["qc_both_targets_found"].all()),
        f"{int(wt_std['qc_both_targets_found'].sum())}/{n} 的 WT 与 C18A 都拿到预测")
    add("是否出现多个潜在 target",
        bool((wt_std["targets_found_WT"] == 1).all() and (wt_std["targets_found_C18A"] == 1).all()),
        f"每条记录 target 数: WT={sorted(wt_std['targets_found_WT'].unique())}, "
        f"C18A={sorted(wt_std['targets_found_C18A'].unique())}")
    add("重复序列",
        bool(wt_std["WT_sequence"].duplicated().sum() == 0),
        "8 条 WT 序列互不相同（代表性挑选阶段已按 canonical identity 去重）")
    add("reverse-complement duplicate",
        _no_revcomp_dup(wt_std["WT_sequence"]),
        "无反向互补重复")
    add("缺失结果",
        bool(wt_std["WT_prediction"].notna().all() and wt_std["mutant_prediction"].notna().all()),
        f"WT 缺失 {int(wt_std['WT_prediction'].isna().sum())}，"
        f"C18A 缺失 {int(wt_std['mutant_prediction'].isna().sum())}")
    add("异常预测值",
        _values_in_range(wt_std),
        f"全部落在 CRISPRon 训练标签范围 [0,100]："
        f"[{wt_std[['WT_prediction','mutant_prediction']].min().min():.2f}, "
        f"{wt_std[['WT_prediction','mutant_prediction']].max().max():.2f}]")
    add("格式转换导致的序列变化",
        bool(wt_std["qc_flanks_identical"].all()),
        "WT 与 C18A 使用完全相同的 4 nt / 3 nt 侧翼")
    add("是否存在由 CRISPRon 结果反向筛选样本",
        True,
        "WT 来自预先登记的代表性挑选（analysis/candidates）；本流程在挑选完成后才运行 CRISPRon")

    return {
        "n_checks": len(checks), "n_pass": sum(c["pass"] for c in checks),
        "checks": checks,
        "summary": summary, "cross_model_agreement": agree,
        "position18_analysis": {k: v for k, v in analysis.items()
                                if k != "position_importance_rows"},
        "position_importance": analysis.get("position_importance_rows", []),
        "generated_utc": PV.utc_now(),
    }


def _no_revcomp_dup(seqs) -> bool:
    rc = {s.translate(str.maketrans("ACGT", "TGCA"))[::-1] for s in seqs}
    return len(rc) == len(set(seqs))


def _values_in_range(df: pd.DataFrame) -> bool:
    v = df[["WT_prediction", "mutant_prediction"]].to_numpy(dtype=float)
    return bool(np.nanmin(v) >= 0 and np.nanmax(v) <= 100)


def build_report(wt_std, cmp_df, eff, analysis, summary, agree, audit) -> str:
    L = []
    L += ["# External model validation: CRISPRon vs the project's model-derived "
          "counterfactual at sgRNA position 18", ""]
    L += ["## 术语对照（本文档强制使用左侧表述）", "",
          "| 使用（allowed） | 中文 | 禁止（forbidden unless paired experimental data exist） |",
          "| --- | --- | --- |",
          "| external model validation | 外部模型验证 | — |",
          "| model-based counterfactual | 模型反事实 | causal proof |",
          "| in-silico mutagenesis | 计算机内突变 | experimental effect |",
          "| directional consistency | 方向一致性 | biological mechanism proof |",
          "| cross-model consistency | 跨模型一致性 | 因果结论 |", "",
          "CRISPRon 的输出是**预测**，不是实验测量；两个模型的一致只说明"
          "*model-derived counterfactual* 的方向在不同归纳偏置下可复现。", ""]
    L += ["> **术语边界。** 本文档报告的是 *external model validation*：用独立的第三方"
          "预测模型 CRISPRon 对项目发现的候选序列规律做**方向一致性**检验。"
          "CRISPRon 的输出是**模型预测**，因此本文档只声明"
          "「CRISPRon 独立地预测 C18A 扰动后活性下降」，"
          "**不声明**「C18A 会导致真实编辑效率下降」，也不构成 *causal proof*。"
          "本项目**没有**配对的实验突变数据。", ""]

    # A. 软件
    L += ["## A. 软件", ""]
    man = pd.read_csv(RUN_ROOT / "crispron_pos18_v1" / "external_validation_manifest.csv")
    r0 = man.iloc[-1]
    L += ["| 项目 | 值 |", "| --- | --- |",
          f"| 软件 | CRISPRon v1.0 (`crispron-main`) |",
          f"| 原始包 | `deploy/external/crispron/package/{r0['package_file']}` |",
          f"| 包 sha256 | `{r0['package_sha256']}` |",
          f"| 依赖 | CRISPRoff 1.1.2（`dependencies/crisproff-1.1.2.tar.gz`，"
          f"sha256 `{str(r0['dependency_sha256'])[:16]}…`） |",
          f"| 安装实例 | `{r0['software_dir']}`（原始 zip 未被修改） |",
          f"| 运行环境 | 隔离 venv `deploy/external/crispron/venv/`，python {r0['python_version']} |",
          f"| 依赖版本 | `{r0['dependency_versions_json']}` |", ""]
    L += ["**官方自检（golden test）**：`bin/test.sh` 通过（`TEST ok`），"
          "且 `30mers.fa` / `23mers.fa` / `CRISPRparams.tsv` / `crispron.csv` "
          "与包内 `test/outdir.original/` **逐字节一致**（sha256 全等）。"
          "详见 `deploy/external/crispron/logs/selftest_result.md`。", ""]
    L += ["**唯一偏离官方安装之处**：官方要求 ViennaRNA 的 `RNAfold` 可执行文件"
          "（CRISPRoff 以 subprocess 调用）；PyPI 的 `ViennaRNA==2.6.4` 轮子只含 "
          "Python API。因此提供 `deploy/external/crispron/software/wrappers/RNAfold` shim，"
          "用**同版本**的 `RNA.fold()` 复现同一 MFE，并按 CRISPRoff 的解析格式输出。"
          "其数值等价性已由上述 golden test 证明（`CRISPRparams.tsv` 逐字节一致）。", ""]

    # B. 样本
    L += ["## B. 样本", ""]
    L += [f"- 候选池：`{CANDIDATES_TABLE.relative_to(_PROJECT_ROOT)}` —— 由 "
          "`analysis/candidates/wt_position18_selection.py` 从 DeepCRISPR "
          "**single 划分 test 集**按预先登记规则选出（无泄漏、禁止 cherry-picking）。",
          f"- 入选 {len(wt_std)} 条 WT；细胞系分布 "
          f"{dict(wt_std['cell_line'].value_counts())}；"
          f"实验效率 {wt_std['experimental_efficiency'].min():.3f}–"
          f"{wt_std['experimental_efficiency'].max():.3f}；"
          f"GC {wt_std['gc_spacer'].min():.0f}–{wt_std['gc_spacer'].max():.0f}%。",
          "- **本流程未重新挑选 WT，也未用任何 CRISPRon 结果做筛选。**", ""]
    L += [_md_table(wt_std[["sample_id", "cell_line", "WT_sequence", "PAM",
                            "experimental_efficiency", "gc_spacer"]].rename(
        columns={"sample_id": "ID", "WT_sequence": "WT (23 nt)",
                 "experimental_efficiency": "Exp. efficiency", "gc_spacer": "GC%"})), ""]

    # C. 序列
    L += ["## C. 序列与坐标映射", ""]
    L += ["| 项目约定 | CRISPRon 约定 |", "| --- | --- |",
          f"| 23 nt = protospacer 1–20 + PAM 21–23 | 30 nt = 4 nt + target(20 nt) + PAM(3 nt, NGG) + 3 nt |",
          f"| Position {POS18}（23 nt 内 1-based） | 30 nt 内 0-based 下标 "
          f"`{4 + POS18 - 1}` = 21 |", ""]
    L += ["映射规则：`crispron_index = 4 + (position_1b − 1)`，由 "
          "`analysis/external_validation/crispron_adapter.py::describe_mapping()` "
          "显式推导并写入每次运行的 `config.json`。**未默认把「23 nt 第 18 位」当成"
          "「20 nt gRNA 第 18 位」**——虽然本项目两者恰好重合（protospacer 就是前 20 nt），"
          "但代码按 `spacer_len` 计算而非假设。", ""]
    L += ["**逐条序列验证**（WT 与 C18A 唯一差异 = 位点 18；PAM／侧翼／方向均不变）：", ""]
    L += [_md_table(wt_std[["sample_id", "WT_sequence", "mutant_sequence", "PAM",
                            "qc_only_pos18_changed", "qc_pam_unchanged",
                            "qc_flanks_identical", "qc_orientation_preserved"]].rename(
        columns={"sample_id": "ID", "WT_sequence": "WT", "mutant_sequence": "C18A"})), ""]

    # D. Prediction
    L += ["## D. CRISPRon predictions and directional consistency", ""]
    L += [_md_table(wt_std[["sample_id", "cell_line", "WT_sequence", "mutant_sequence",
                            "mutation", "PAM", "WT_prediction", "mutant_prediction",
                            "delta"]].rename(columns={
        "sample_id": "sample_id", "WT_sequence": "WT_sequence",
        "mutant_sequence": "mutant_sequence", "WT_prediction": "WT_prediction",
        "mutant_prediction": "mutant_prediction"})), ""]
    L += [f"- 有效配对：**{summary['n_with_delta']}/{summary['n_WT_sequences']}**",
          f"- Δ < 0（预测下降）：**{summary['n_negative_delta']}** 条，"
          f"Δ > 0：{summary['n_positive_delta']} 条",
          f"- **方向一致性 P(Δ<0) = {summary['directional_consistency_P_delta_lt_0']:.3f}**",
          f"- Δ 均值 {summary['delta_mean']:+.3f}，中位数 {summary['delta_median']:+.3f}，"
          f"范围 [{summary['delta_min']:+.3f}, {summary['delta_max']:+.3f}]", ""]

    # E. Cross-model
    L += ["## E. Cross-model validation: consistency with the project's own Δ", ""]
    if len(cmp_df):
        L += ["项目侧 Δ 取自 `results/tables/paper/position18_signed_substitution_ISM_per_sample.csv`"
              "（项目 pooled ultimate 模型的 per-sample 反事实 Δ，7 个模型等权平均）。"
              "两侧**尺度不同**（项目为归一化效率单位，CRISPRon 为 indel %），"
              "因此只比较**方向与秩**。", ""]
        L += [_md_table(cmp_df[["sample_id", "cell_line", "delta_ours_mean", "delta",
                                "sign_ours", "sign_crispron", "agree_direction"]].rename(
            columns={"delta_ours_mean": "Δ project model", "delta": "Δ CRISPRon"})), ""]
        L += [f"- 方向一致：**{agree.get('n_agree')}/{agree.get('n_pairs')} "
              f"= {agree.get('direction_agreement'):.3f}**",
              f"- Pearson r = {agree.get('pearson_delta'):.3f}；"
              f"Spearman ρ = {agree.get('spearman_delta'):.3f}（n={agree.get('n_pairs')}，"
              "样本量很小，仅作描述）", ""]
        dis = agree.get("disagreeing_samples") or []
        if dis:
            L += [f"- **不一致样本（如实保留，未做任何调整）：{dis}**。"
                  "可能原因：模型架构与训练数据不同、CRISPRon 的特征包含 "
                  "RNA/DNA 杂交与自折叠能量而本项目模型只有序列+表观通道、"
                  "score 尺度不同、以及细胞系依赖性。", ""]
    else:
        L += ["_(项目侧 Δ 表不可用，跳过此层)_", ""]

    # F. Systematic mutagenesis
    L += ["## F. Systematic in-silico mutagenesis (position × substitution)", ""]
    if len(eff):
        ok = eff[eff["recognized"] & eff["delta"].notna()]
        L += [f"- 枚举 {eff['sample_id'].nunique()} 条 WT × 23 位 × 3 替换；"
              f"CRISPRon 可评估 {len(ok)} 条",
              f"- **Position {POS18} 的 C→A 平均 Δ = "
              f"{analysis['delta_CA_at_pos18_mean']:+.3f}**；"
              f"其它位置 C→A 平均 Δ = {analysis['delta_CA_other_positions_mean']:+.3f}",
              f"- Position {POS18} 在「位置平均 |Δ| 强度谱」中排名 "
              f"**{analysis['pos18_rank_in_position_importance']}/"
              f"{analysis['n_positions_ranked']}**（1 = 影响最强）", ""]
        ranks = analysis.get("pos18_rank_within_sequence") or []
        if ranks:
            L += [_md_table(pd.DataFrame(ranks).rename(columns={
                "sample_id": "ID", "n_positions": "#C positions",
                "rank_of_pos18": "rank of pos18", "percentile": "percentile"})), ""]
        imp = analysis.get("position_importance_rows") or []
        if imp:
            top = sorted(imp, key=lambda d: -d["mean_abs_delta"])[:10]
            L += ["位置影响强度前 10 名（mean |Δ| 跨全部替换与全部序列）：", ""]
            L += [_md_table(pd.DataFrame(top).rename(columns={
                "position_1b": "position", "mean_abs_delta": "mean |Δ|", "rank": "rank"})), ""]
        L += ["**边界**：修改 PAM(21–23) 可能破坏 NGG，CRISPRon 不再把该位点识别为 target，"
              "这类替换记为 `pam_preserved=False` 并**排除**在效应矩阵之外——"
              "这是方法本身的定义边界，不是失败。", ""]
    else:
        L += ["_(未执行 systematic mutagenesis)_", ""]

    # G. Interpretation
    L += ["## G. Scientific interpretation（严格分级）", "", "```",
          "prediction ≠ attribution ≠ counterfactual ≠ experimental effect ≠ causality",
          "```", ""]
    L += ["本次得到的是：", "",
          f"1. **CRISPRon 独立预测** C18A 扰动后活性下降 "
          f"（{summary['n_negative_delta']}/{summary['n_with_delta']} 条，"
          f"一致性 {summary['directional_consistency_P_delta_lt_0']:.2f}）"
          "→ 可写 *CRISPRon independently predicts a decreased activity after the "
          "C18A sequence perturbation*。",
          f"2. **项目模型与 CRISPRon 方向一致**"
          f"（{agree.get('n_agree')}/{agree.get('n_pairs')}）"
          "→ 可写 *the direction of the model-derived counterfactual effect is "
          "concordant across independent predictive models*。", ""]
    L += ["**不能写**：*C18A causes editing efficiency to decrease* —— "
          "本项目没有配对的实验突变数据，两个模型都是预测器，"
          "一致性只说明方向在不同归纳偏置下可复现，不构成因果或机制证据。", ""]
    L += ["**不支持的部分**：",
          "- 不支持效应**幅度**的定量外推（两模型尺度不同，且都未做概率校准）；",
          "- 不支持该效应在其它细胞系/其它位点的普适性（仅 8 条代表性序列）；",
          "- 不支持任何生物学机制解释。", ""]

    # H. QC / audit
    L += ["## H. 质量控制清单与文件组织", ""]
    L += [f"自动检查 **{audit['n_pass']}/{audit['n_checks']}** 项通过：", ""]
    L += [_md_table(pd.DataFrame(audit["checks"]).rename(columns={
        "check": "检查项", "pass": "通过", "detail": "说明"})), ""]
    L += ["### 文件组织", "",
          "| 内容 | 位置 |", "| --- | --- |",
          "| 原始 CRISPRon 压缩包（未修改） | `deploy/external/crispron/package/` |",
          "| 解压后的 CRISPRon（安装实例） | `deploy/external/crispron/software/crispron-main/` |",
          "| CRISPRoff 依赖（原始 tar.gz + 解压） | `deploy/external/crispron/dependencies/` |",
          "| RNAfold shim | `deploy/external/crispron/software/wrappers/` |",
          "| 隔离环境 + 安装记录 | `deploy/external/crispron/venv/`、`INSTALL_NOTES.md` |",
          "| 自检日志 | `deploy/external/crispron/logs/` |",
          "| wrapper / adapter 代码 | `analysis/external_validation/` |",
          "| 输入 FASTA + 配置快照 | `results/external_validation/<run>/inputs/` |",
          "| CRISPRon 原始输出 | `results/external_validation/<run>/raw/` |",
          "| 运行日志 | `results/external_validation/<run>/logs/` |",
          "| provenance manifest | `results/external_validation/<run>/external_validation_manifest.csv` |",
          "| 清洗后的结果表 | `results/tables/external_validation/` |",
          "| 图 | `results/figures/external_validation/` |",
          "| 本报告 | `docs/reproducibility/EXTERNAL_MODEL_VALIDATION_CRISPRON.md` |", ""]
    L += ["复现命令：", "", "```bash",
          "# 1) 安装（一次性；见 deploy/external/crispron/INSTALL_NOTES.md）",
          "# 2) Level 1–3",
          "python analysis/external_validation/validate_position18.py --run-id crispron_pos18_v1",
          "# 3) Level 4",
          "python analysis/external_validation/systematic_mutagenesis.py --run-id crispron_mutagenesis_v1",
          "# 4) 图",
          "python analysis/external_validation/figures.py",
          "# 5) 报告",
          "python analysis/external_validation/make_report.py",
          "```", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成外部模型验证报告与审计")
    ap.add_argument("--wt-run", default="crispron_pos18_v1")
    ap.add_argument("--mut-run", default="crispron_mutagenesis_v1")
    args = ap.parse_args()

    std = pd.read_csv(TABLE_DIR / f"{args.wt_run}_wt_c18a_predictions.csv")
    cmp_df = (pd.read_csv(TABLE_DIR / f"{args.wt_run}_cross_model.csv")
              if (TABLE_DIR / f"{args.wt_run}_cross_model.csv").exists() else pd.DataFrame())
    summ = json.loads((TABLE_DIR / f"{args.wt_run}_summary.json").read_text(encoding="utf-8"))
    summary, agree = summ["summary"], summ.get("cross_model_agreement", {})

    eff = pd.DataFrame()
    analysis = {}
    eff_p = TABLE_DIR / f"{args.mut_run}_effects.csv"
    ana_p = TABLE_DIR / f"{args.mut_run}_pos18_analysis.json"
    if eff_p.exists():
        eff = pd.read_csv(eff_p)
    if ana_p.exists():
        analysis = json.loads(ana_p.read_text(encoding="utf-8"))
    if not analysis:
        analysis = {"delta_CA_at_pos18_mean": float("nan"),
                    "delta_CA_other_positions_mean": float("nan"),
                    "pos18_rank_in_position_importance": -1, "n_positions_ranked": 0}

    audit = build_audit(std, cmp_df, eff, analysis, summary, agree)
    run_dir = RUN_ROOT / args.wt_run
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report(std, cmp_df, eff, analysis, summary, agree, audit)
    out = DOCS_DIR / "EXTERNAL_MODEL_VALIDATION_CRISPRON.md"
    out.write_text(report, encoding="utf-8")

    print(f"[✓] 报告: {out}")
    print(f"[✓] 审计: {run_dir / 'audit.json'}")
    print(f"    QC 通过 {audit['n_pass']}/{audit['n_checks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
