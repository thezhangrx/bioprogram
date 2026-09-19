#!/usr/bin/env python3
"""Level 4：CRISPRon 上的 systematic in-silico mutagenesis（position × substitution）。

对每条代表性 WT，逐个位置、逐个替换碱基构造突变体并预测：

    Δ_{j,b} = f_CRISPRon(x^{j→b}) − f_CRISPRon(x)

产出 position × substitution 效应矩阵，并回答：
  * Position 18 的 C→A 效应在**同一条序列内**所有位置中排第几？
  * C→A 替换在 Position 18 与其它含 C 的位置相比是否更大？
  * Position 18 是否属于"稳定的高影响位置"（跨 8 条序列的秩一致性）？

重要边界
--------
* 这是 **model-based counterfactual / in-silico mutagenesis**，不是实验效应；
* 修改 PAM(21–23) 会破坏 NGG，CRISPRon 不再把该位点识别为 target —— 这类替换
  记为 ``not_recognized``，**不进入效应矩阵**（这是方法本身的边界，不是失败）；
* 全程复用 Project 既有代表性 WT，不做任何基于 CRISPRon 的反向筛选。
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

from analysis.external_validation import crispron_adapter as CA            # noqa: E402
from analysis.external_validation import provenance as PV                  # noqa: E402
from analysis.external_validation.validate_position18 import (            # noqa: E402
    CRISPRON_DIR, CRISPROFF_DIR, RUN_ROOT, RNAFOLD_SHIM, SOFTWARE_DIR,
    TABLE_DIR, VENV_PYTHON, load_representative_wt,
)

BASES = ["A", "C", "G", "T"]


def build_mutant_set(cands: pd.DataFrame, spacer_len: int, pos_index0: int,
                     pam_start_1b: int) -> pd.DataFrame:
    """枚举 (序列 × 位置 × 替换) 的全部突变体，并记录 WT 作为参照。"""
    rows = []
    for _, r in cands.iterrows():
        wt23 = str(r["sgRNA"]).upper()
        stored30 = str(r["crispron_30mer_wt"]).upper()
        up4, down3 = stored30[:CA.PRE_GUIDE], stored30[-CA.POST_PAM:]
        rec_wt = CA.build_crispron_input(f"{r['ID']}_WT", wt23, spacer_len, up4, down3)
        if rec_wt.crispron_seq != stored30:
            raise AssertionError(f"{r['ID']}: 30-mer 与项目候选表不一致")

        rows.append({"sample_id": r["ID"], "cell_line": r["cell_line"],
                     "record_id": rec_wt.record_id, "kind": "WT", "position_1b": np.nan,
                     "substitution": "WT", "seq23": wt23, "crispron_seq": rec_wt.crispron_seq,
                     "in_pam": False})
        for j0 in range(len(wt23)):
            pos1 = j0 + 1
            in_pam = pos1 >= pam_start_1b
            for b in BASES:
                if b == wt23[j0]:
                    continue
                mut23, _ = CA.mutate_project_sequence(wt23, j0, b)
                # 修改 PAM(21-23) 可能破坏 NGG。target 是由 NGG 定义的，
                # 这类替换 CRISPRon 原理上无法评估 —— 显式标记，不送进 CRISPRon，
                # 也不进入效应矩阵（方法边界，而非失败）。
                pam_ok = mut23[spacer_len + 1:spacer_len + 3] == CA.PAM_MOTIF
                if not pam_ok:
                    rows.append({"sample_id": r["ID"], "cell_line": r["cell_line"],
                                 "record_id": f"{r['ID']}_p{pos1}{b}", "kind": "mutant",
                                 "position_1b": pos1, "substitution": f"{wt23[j0]}>{b}",
                                 "seq23": mut23, "crispron_seq": "", "in_pam": bool(in_pam),
                                 "pam_preserved": False,
                                 "note": "PAM-destroying substitution: target no longer NGG"})
                    continue
                rec = CA.build_crispron_input(f"{r['ID']}_p{pos1}{b}", mut23, spacer_len, up4, down3)
                rows.append({"sample_id": r["ID"], "cell_line": r["cell_line"],
                             "record_id": rec.record_id, "kind": "mutant", "position_1b": pos1,
                             "substitution": f"{wt23[j0]}>{b}", "seq23": mut23,
                             "crispron_seq": rec.crispron_seq, "in_pam": bool(in_pam),
                             "pam_preserved": True})
    return pd.DataFrame(rows)


def predict_all(df: pd.DataFrame, run_dir: Path, run_id: str, skip_run: bool):
    fasta = run_dir / "inputs" / "systematic_mutagenesis_30mer.fa"
    raw_dir = run_dir / "raw"
    log_dir = run_dir / "logs"
    for d in (fasta.parent, raw_dir, log_dir):
        d.mkdir(parents=True, exist_ok=True)
    sendable = df[df["crispron_seq"].astype(str).str.len() > 0]
    CA.write_fasta(zip(sendable["record_id"], sendable["crispron_seq"]), fasta)

    planned = CA.build_crispron_commands(fasta, raw_dir, crispron_dir=SOFTWARE_DIR,
                                        crisproff_dir=CRISPROFF_DIR,
                                        python_exe=str(VENV_PYTHON), rnafold_exe=str(RNAFOLD_SHIM))
    if skip_run and (raw_dir / "crispron.csv").exists():
        result = None
    else:
        result = CA.run_crispron(fasta, raw_dir, crispron_dir=SOFTWARE_DIR,
                                 crisproff_dir=CRISPROFF_DIR, python_exe=str(VENV_PYTHON),
                                 rnafold_exe=str(RNAFOLD_SHIM),
                                 log_path=log_dir / "crispron_mutagenesis.log")
    preds = CA.parse_crispron_output(raw_dir)
    return fasta, preds, result, planned


def attach_predictions(df: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    """对齐预测并清点 target。

    两个不同的计数必须分开，否则会漏计（实测踩过）：
      * **目标预测** 用 30 nt 序列**精确匹配**定位（不依赖 CRISPRon 的编号公式）；
      * **该输入序列一共被识别出几个 target** 必须按 **CRISPRon ID 的记录名前缀**
        统计。因为 ``get_30mers_from_fa.py`` 会在**正负两条链**上找 NGG，
        负链命中会写出一个与输入**不同**的 30-mer（guide 方向），
        按 30-mer 字符串分组就会把这类额外 target 漏掉。
    """
    preds = preds.copy()
    preds["30mer"] = preds["30mer"].astype(str).str.upper()
    preds["ID"] = preds["ID"].astype(str)

    by_seq = preds.groupby("30mer").agg(prediction=("CRISPRon", "mean"),
                                        ids=("ID", lambda s: ";".join(map(str, s))))

    out = df.copy()
    out["prediction"] = out["crispron_seq"].map(by_seq["prediction"])
    out["intended_target_ids"] = out["crispron_seq"].map(by_seq["ids"]).fillna("")

    ids = preds["ID"]
    counts, spurious = [], []
    for rid in out["record_id"]:
        hit = preds[ids.str.startswith(str(rid) + "_")]
        counts.append(int(len(hit)))
        spurious.append(";".join(str(x) for x in hit["ID"]
                                 if str(x) not in str(by_seq["ids"].get("", ""))))
    out["n_targets_for_record"] = counts          # 该输入序列被识别出的 target 总数
    out["recognized"] = out["prediction"].notna()

    # 额外 target（非预期那条）
    wanted = out.set_index("record_id")["crispron_seq"].to_dict()
    extra = []
    for rid in out["record_id"]:
        hit = preds[ids.str.startswith(str(rid) + "_")]
        want30 = wanted.get(rid, "")
        extra.append(";".join(str(x) for x in hit.loc[hit["30mer"] != want30, "ID"]))
    out["extra_target_ids"] = extra
    out["n_extra_targets"] = out["extra_target_ids"].map(
        lambda s: 0 if not s else len(str(s).split(";")))
    return out


def effect_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Δ_{j,b} = f(mutant) − f(WT)，仅保留 WT 与突变体都被识别的条目。"""
    wt = df[df["kind"] == "WT"].set_index("sample_id")["prediction"].to_dict()
    m = df[df["kind"] == "mutant"].copy()
    m["wt_prediction"] = m["sample_id"].map(wt)
    m["delta"] = m["prediction"] - m["wt_prediction"]
    return m


def position18_analysis(eff: pd.DataFrame, pos18: int = 18) -> dict:
    ok = eff[eff["recognized"] & eff["delta"].notna()]
    out = {}
    # (1) C→A 在 18 位 vs 其它含 C 位置
    ca = ok[ok["substitution"] == "C>A"]
    p18 = ca[ca["position_1b"] == pos18]
    other = ca[ca["position_1b"] != pos18]
    out["n_positions_with_CA"] = int(ca["position_1b"].nunique())
    out["delta_CA_at_pos18_mean"] = float(p18["delta"].mean()) if len(p18) else float("nan")
    out["delta_CA_other_positions_mean"] = float(other["delta"].mean()) if len(other) else float("nan")
    out["delta_CA_pos18_vs_others_mannwhitney_note"] = (
        "样本量小（每条序列 1 个 18 位观测），只报描述统计，不做显著性检验")

    # (2) 位置 18 在同序列内的 |Δ| 秩
    ranks = []
    for sid, g in ok.groupby("sample_id"):
        subs = g[g["substitution"] == "C>A"].copy()
        if subs.empty:
            continue
        subs["abs_delta"] = subs["delta"].abs()
        subs = subs.sort_values("abs_delta", ascending=False, kind="stable")
        pos = list(subs["position_1b"])
        if pos18 in pos:
            ranks.append({"sample_id": sid, "n_positions": len(pos),
                          "rank_of_pos18": pos.index(pos18) + 1,
                          "percentile": 1.0 - (pos.index(pos18)) / max(len(pos) - 1, 1)})
    out["pos18_rank_within_sequence"] = ranks
    if ranks:
        out["pos18_rank_median"] = float(np.median([r["rank_of_pos18"] for r in ranks]))
        out["pos18_rank_percentile_mean"] = float(np.mean([r["percentile"] for r in ranks]))

    # (3) 每个位置在所有替换上的平均 |Δ| —— 位置影响强度谱
    pos_imp = (ok.assign(abs_delta=ok["delta"].abs())
                 .groupby("position_1b", as_index=False)["abs_delta"].mean()
                 .rename(columns={"abs_delta": "mean_abs_delta"}))
    pos_imp["rank"] = pos_imp["mean_abs_delta"].rank(ascending=False, method="min").astype(int)
    out["position_importance_rows"] = pos_imp.to_dict(orient="records")
    r18 = pos_imp.loc[pos_imp["position_1b"] == pos18, "rank"]
    out["pos18_rank_in_position_importance"] = int(r18.iloc[0]) if len(r18) else -1
    out["n_positions_ranked"] = int(len(pos_imp))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="CRISPRon systematic in-silico mutagenesis")
    ap.add_argument("--run-id", default="crispron_mutagenesis_v1")
    ap.add_argument("--skip-run", action="store_true")
    args = ap.parse_args()

    cands = load_representative_wt()
    # 位点约定与 validate_position18 保持一致
    spacer_len, pos_index0 = 20, 17
    pam_start_1b = spacer_len + 1
    run_dir = RUN_ROOT / args.run_id

    print(f"[1/5] 枚举突变体：{len(cands)} 条 WT × 23 位 × 3 替换 ...")
    mut = build_mutant_set(cands, spacer_len, pos_index0, pam_start_1b)
    n_mut = int((mut["kind"] == "mutant").sum())
    n_pam_broken = int((mut.get("pam_preserved") == False).sum()) if "pam_preserved" in mut else 0
    print(f"        共 {len(mut)} 条记录（WT {len(cands)} + 突变 {n_mut}）；"
          f"其中 PAM 被破坏、CRISPRon 无法评估的 {n_pam_broken} 条")

    print("[2/5] 运行 CRISPRon ...")
    fasta, preds, result, planned_cmds = predict_all(mut, run_dir, args.run_id, args.skip_run)
    _rc = f"；returncodes={result.returncodes}" if result else "（复用已有输出）"
    print(f"        CRISPRon 输出 {len(preds)} 行{_rc}")

    print("[3/5] 对齐预测 ...")
    full = attach_predictions(mut, preds)
    n_unrec = int((~full["recognized"]).sum())
    n_pam_broken2 = int((full.get("pam_preserved") == False).sum()) if "pam_preserved" in full else 0
    n_extra = int((full["n_extra_targets"] > 0).sum())
    print(f"        未被识别为 target 的记录 {n_unrec}"
          f"（其中 PAM 被破坏的 {n_pam_broken2} 条属方法边界）")
    print(f"        同一输入序列被识别出 >1 个 target 的记录 {n_extra} 条"
          f"（CRISPRon 在两条链上都会扫 NGG；已逐条登记 extra_target_ids）")

    print("[4/5] 计算效应矩阵与 Position 18 分析 ...")
    eff = effect_matrix(full)
    analysis = position18_analysis(eff, pos18=pos_index0 + 1)

    print("[5/5] 写出结果 ...")
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    full_path = TABLE_DIR / f"{args.run_id}_all_records.csv"
    eff_path = TABLE_DIR / f"{args.run_id}_effects.csv"
    full.to_csv(full_path, index=False, encoding="utf-8-sig")
    eff.to_csv(eff_path, index=False, encoding="utf-8-sig")

    mat = (eff[eff["recognized"] & eff["delta"].notna()]
           .pivot_table(index=["sample_id", "position_1b"], columns="substitution",
                        values="delta", aggfunc="mean"))
    mat_path = TABLE_DIR / f"{args.run_id}_delta_matrix.csv"
    mat.to_csv(mat_path, encoding="utf-8-sig")

    (TABLE_DIR / f"{args.run_id}_pos18_analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    env = PV.collect_environment(str(VENV_PYTHON))
    zip_path = CRISPRON_DIR / "package" / "crispron-main.zip"
    dep_path = CRISPRON_DIR / "dependencies" / "crisproff-1.1.2.tar.gz"
    row = PV.build_manifest_row(
        run_id=args.run_id, stage="systematic_mutagenesis", timestamp_utc=PV.utc_now(),
        software="CRISPRon", software_version="v1.0 (crispron-main)",
        package_file=zip_path.name, package_sha256=PV.sha256_file(zip_path),
        software_dir=str(SOFTWARE_DIR.relative_to(_PROJECT_ROOT)),
        dependency="CRISPRoff", dependency_version="1.1.2",
        dependency_sha256=PV.sha256_file(dep_path),
        execution_command=" ; ".join(" ".join(c) for c in (result.commands if result else planned_cmds)),
        python_version=env["python_version"], python_executable=env["python_executable"],
        dependency_versions_json=env["dependency_versions_json"],
        input_file=str(fasta.relative_to(_PROJECT_ROOT)),
        input_sha256=PV.sha256_file(fasta),
        n_input_records=len(mut),
        input_sequence_sha256=PV.sha256_of_sequences(mut["crispron_seq"]),
        model_config=json.dumps({"models": "data/deep_models/best/*.model.best (6 averaged)"}),
        output_file=str((run_dir / "raw" / "crispron.csv").relative_to(_PROJECT_ROOT)),
        output_sha256=PV.sha256_file(run_dir / "raw" / "crispron.csv"),
        code_fingerprint=PV.code_fingerprint(),
        data_source="DeepCRISPR representative WT (reused)", batch=args.run_id,
        notes=f"n_unrecognized={n_unrec}",
    )
    PV.append_manifest(run_dir / "external_validation_manifest.csv", [row])

    print("\n" + "=" * 72)
    print(f"  Position 18 C→A 平均 Δ          {analysis['delta_CA_at_pos18_mean']:+.3f}")
    print(f"  其它位置 C→A 平均 Δ             {analysis['delta_CA_other_positions_mean']:+.3f}")
    print(f"  位置 18 在位置影响谱中的排名     "
          f"{analysis['pos18_rank_in_position_importance']}/{analysis['n_positions_ranked']}")
    if analysis.get("pos18_rank_median"):
        print(f"  位置 18 在同序列 |Δ| 秩中位数    {analysis['pos18_rank_median']:.1f} "
              f"/ {analysis['n_positions_with_CA']}")
    print("=" * 72)
    for p in (full_path, eff_path, mat_path):
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
