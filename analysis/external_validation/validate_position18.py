#!/usr/bin/env python3
"""Level 1–3 外部模型验证：CRISPRon 对 Position 18 C→A 的预测变化。

    WT → C18A → CRISPRon(WT), CRISPRon(C18A) → Δ_CRISPRon = f(C18A) - f(WT)

复用而非重写
------------
* 代表性 WT：**直接复用** ``results/tables/candidates/wt_position18_candidates.csv``
  （由 ``analysis/candidates/wt_position18_selection.py`` 按预先登记规则选出），
  本脚本**不重新挑选**，也**不使用任何 CRISPRon 结果**做筛选；
* 30-mer 构造：``crispron_adapter``（纯函数，可单测）；
* 项目自身 Δ：``results/tables/paper/position18_signed_substitution_ISM_per_sample.csv``
  （项目 pooled ultimate 模型的 per-sample 反事实 Δ）；
* provenance：``provenance.py``。

产物
----
    results/external_validation/<run_id>/inputs/         输入 FASTA + 配置快照
    results/external_validation/<run_id>/raw/            CRISPRon 全部原始输出
    results/external_validation/<run_id>/logs/           运行日志
    results/external_validation/<run_id>/external_validation_manifest.csv
    results/tables/external_validation/                  标准化表 + 汇总
    results/figures/external_validation/                 图

术语纪律：本脚本产出的是 **model-based counterfactual / in-silico mutagenesis**
的方向一致性证据，**不是** experimental effect，也不构成 causal proof。
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

from analysis.external_validation import crispron_adapter as CA          # noqa: E402
from analysis.external_validation import provenance as PV                # noqa: E402
from core.common.paths import RESULTS_TABLES, resolve_dataset            # noqa: E402
from core.data.splitting.cell_line_division import load_feature_schema   # noqa: E402

CANDIDATES_TABLE = RESULTS_TABLES / "candidates" / "wt_position18_candidates.csv"
PROJECT_DELTA_TABLE = RESULTS_TABLES / "paper" / "position18_signed_substitution_ISM_per_sample.csv"
RUN_ROOT = _PROJECT_ROOT / "results" / "external_validation"
TABLE_DIR = RESULTS_TABLES / "external_validation"
FIG_DIR = _PROJECT_ROOT / "results" / "figures" / "external_validation"

CRISPRON_DIR = _PROJECT_ROOT / "deploy" / "external" / "crispron"
SOFTWARE_DIR = CRISPRON_DIR / "software" / "crispron-main"
CRISPROFF_DIR = CRISPRON_DIR / "dependencies" / "crisproff-1.1.2"
VENV_PYTHON = CRISPRON_DIR / "venv" / "bin" / "python"
RNAFOLD_SHIM = CRISPRON_DIR / "software" / "wrappers" / "RNAfold"


# --------------------------------------------------------------------------- #
def load_representative_wt() -> pd.DataFrame:
    """复用项目既有的代表性 WT 表（不重新挑选）。"""
    if not CANDIDATES_TABLE.exists():
        raise FileNotFoundError(
            f"找不到代表性 WT 表 {CANDIDATES_TABLE}；"
            "请先运行 analysis/candidates/wt_position18_selection.py"
        )
    df = pd.read_csv(CANDIDATES_TABLE)
    need = {"ID", "cell_line", "sgRNA", "mutant", "crispron_30mer_wt", "Normalized efficacy"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"代表性 WT 表缺列 {missing}")
    return df


def build_wt_mutant_pairs(cands: pd.DataFrame, pos_index0: int, spacer_len: int):
    """返回 [(wt_rec, mut_rec, verify_dict), ...]。"""
    pairs = []
    for _, r in cands.iterrows():
        wt23 = str(r["sgRNA"]).upper()
        stored30 = str(r["crispron_30mer_wt"]).upper()
        up4, down3 = stored30[:CA.PRE_GUIDE], stored30[-CA.POST_PAM:]

        rec_wt = CA.build_crispron_input(f"{r['ID']}_WT", wt23, spacer_len, up4, down3)
        if rec_wt.crispron_seq != stored30:
            raise AssertionError(
                f"{r['ID']}: 适配层重建的 30-mer 与项目候选表不一致\n"
                f"  重建={rec_wt.crispron_seq}\n  项目={stored30}")

        mut23, v = CA.mutate_project_sequence(wt23, pos_index0, "A")
        expected_mut = str(r["mutant"]).upper()
        if mut23 != expected_mut:
            raise AssertionError(f"{r['ID']}: C18A 序列与项目候选表不一致 {mut23} != {expected_mut}")

        rec_mut = CA.build_crispron_input(f"{r['ID']}_C18A", mut23, spacer_len, up4, down3)

        # 硬验证：只改一个位置；侧翼与 PAM 不变；方向未被反转
        v = dict(v)
        v["pam_unchanged"] = (rec_wt.pam == rec_mut.pam)
        v["flanks_identical"] = (rec_wt.crispron_seq[:CA.PRE_GUIDE] == rec_mut.crispron_seq[:CA.PRE_GUIDE]
                                 and rec_wt.crispron_seq[-CA.POST_PAM:] == rec_mut.crispron_seq[-CA.POST_PAM:])
        v["same_target_context"] = v["flanks_identical"]
        v["crispron_seq_only_one_diff"] = (sum(a != b for a, b in zip(rec_wt.crispron_seq, rec_mut.crispron_seq)) == 1)
        v["crispron_mut_index0"] = CA.TARGET_START_IN_30MER + pos_index0
        v["orientation_preserved"] = (rec_wt.crispron_seq[CA.TARGET_START_IN_30MER:
                                                          CA.TARGET_START_IN_30MER + spacer_len]
                                      == wt23[:spacer_len])
        if not all([v["length_equal"], v["n_mismatch"] == 1, v["prefix_equal"],
                    v["suffix_equal"], v["pam_unchanged"], v["crispron_seq_only_one_diff"],
                    v["orientation_preserved"]]):
            raise AssertionError(f"{r['ID']}: 突变验证未通过: {v}")
        pairs.append((rec_wt, rec_mut, v, r))
    return pairs


# --------------------------------------------------------------------------- #
def qc_and_standardize(pairs, predictions: pd.DataFrame) -> pd.DataFrame:
    """把 CRISPRon 输出对齐回每条 WT，并做 QC。"""
    rows = []
    for wt_rec, mut_rec, v, cand in pairs:
        m_wt = CA.match_intended_target(predictions, wt_rec)
        m_mu = CA.match_intended_target(predictions, mut_rec)
        d = None
        if m_wt["found"] and m_mu["found"]:
            d = m_mu["prediction"] - m_wt["prediction"]
        rows.append({
            "sample_id": cand["ID"],
            "cell_line": cand["cell_line"],
            "WT_sequence": wt_rec.project_seq,
            "mutant_sequence": mut_rec.project_seq,
            "mutation": f"{v['wt_base']}18{v['mut_base']}",
            "PAM": wt_rec.pam,
            "WT_prediction": m_wt["prediction"],
            "mutant_prediction": m_mu["prediction"],
            "delta": d,
            # --- 溯源与 QC ---
            "WT_30mer": wt_rec.crispron_seq,
            "C18A_30mer": mut_rec.crispron_seq,
            "expected_target_id_WT": wt_rec.expected_target_id,
            "expected_target_id_C18A": mut_rec.expected_target_id,
            "target_id_WT": m_wt["target_id"],
            "target_id_C18A": m_mu["target_id"],
            "target_id_matches_expected_WT": m_wt["id_matches_expected"],
            "target_id_matches_expected_C18A": m_mu["id_matches_expected"],
            "targets_found_WT": m_wt["n_targets_for_record"],
            "targets_found_C18A": m_mu["n_targets_for_record"],
            "extra_targets_WT": ";".join(m_wt["extra_target_ids"]),
            "extra_targets_C18A": ";".join(m_mu["extra_target_ids"]),
            "qc_only_pos18_changed": v["n_mismatch"] == 1,
            "qc_pam_unchanged": v["pam_unchanged"],
            "qc_flanks_identical": v["flanks_identical"],
            "qc_orientation_preserved": v["orientation_preserved"],
            "qc_both_targets_found": bool(m_wt["found"] and m_mu["found"]),
            "qc_single_target_each": (m_wt["n_targets_for_record"] == 1
                                      and m_mu["n_targets_for_record"] == 1),
            "experimental_efficiency": float(cand["Normalized efficacy"]),
            "gc_spacer": float(cand["gc_spacer"]) if "gc_spacer" in cand else np.nan,
            "label_bin": cand.get("label_bin", ""),
            "data_source": "DeepCRISPR single-split test set (representative WT table)",
        })
    return pd.DataFrame(rows)


def summarize(standard: pd.DataFrame) -> dict:
    ok = standard[standard["qc_both_targets_found"]]
    d = ok["delta"].astype(float)
    return {
        "n_WT_sequences": int(len(standard)),
        "n_valid_WT": int(standard["WT_prediction"].notna().sum()),
        "n_valid_mutants": int(standard["mutant_prediction"].notna().sum()),
        "n_with_delta": int(len(ok)),
        "n_negative_delta": int((d < 0).sum()),
        "n_positive_delta": int((d > 0).sum()),
        "n_zero_delta": int((d == 0).sum()),
        "directional_consistency_P_delta_lt_0": float((d < 0).mean()) if len(d) else float("nan"),
        "delta_mean": float(d.mean()) if len(d) else float("nan"),
        "delta_median": float(d.median()) if len(d) else float("nan"),
        "delta_min": float(d.min()) if len(d) else float("nan"),
        "delta_max": float(d.max()) if len(d) else float("nan"),
        "n_extra_targets_WT": int((standard["targets_found_WT"] > 1).sum()),
        "n_extra_targets_C18A": int((standard["targets_found_C18A"] > 1).sum()),
    }


# --------------------------------------------------------------------------- #
def project_delta_for(sample_ids, seqs) -> pd.DataFrame:
    """取项目自身对同一批序列的反事实 Δ（模型等权平均）。"""
    if not PROJECT_DELTA_TABLE.exists():
        return pd.DataFrame()
    d = pd.read_csv(PROJECT_DELTA_TABLE)
    sub = d[d["sgRNA"].isin(set(seqs))].copy()
    if sub.empty:
        return pd.DataFrame()
    # 同一 sgRNA 可能出现在多个细胞系 -> 取该序列的行；再按模型等权平均
    per_model = (sub.groupby(["sgRNA", "model"], as_index=False)["delta_C_A"].mean())
    agg = per_model.groupby("sgRNA", as_index=False).agg(
        delta_ours_mean=("delta_C_A", "mean"),
        delta_ours_std=("delta_C_A", "std"),
        n_models=("delta_C_A", "size"),
    )
    agg["delta_ours_min"] = per_model.groupby("sgRNA")["delta_C_A"].min().values
    agg["delta_ours_max"] = per_model.groupby("sgRNA")["delta_C_A"].max().values
    return agg


def cross_model_compare(standard: pd.DataFrame) -> pd.DataFrame:
    ours = project_delta_for(standard["sample_id"], standard["WT_sequence"])
    if ours.empty:
        return pd.DataFrame()
    m = standard.merge(ours, left_on="WT_sequence", right_on="sgRNA", how="left")
    m["sign_ours"] = np.sign(m["delta_ours_mean"])
    m["sign_crispron"] = np.sign(m["delta"])
    m["agree_direction"] = (m["sign_ours"] == m["sign_crispron"])
    return m


def agreement_stats(m: pd.DataFrame) -> dict:
    v = m.dropna(subset=["delta", "delta_ours_mean"])
    if v.empty:
        return {}
    out = {
        "n_pairs": int(len(v)),
        "direction_agreement": float(v["agree_direction"].mean()),
        "n_agree": int(v["agree_direction"].sum()),
    }
    if len(v) >= 3:
        x = v["delta_ours_mean"].to_numpy(dtype=float)
        y = v["delta"].to_numpy(dtype=float)
        # 不引入 scipy：Pearson 用 corrcoef；Spearman 用秩上的 Pearson（等价定义）
        if np.std(x) > 0 and np.std(y) > 0:
            out["pearson_delta"] = float(np.corrcoef(x, y)[0, 1])
            out["spearman_delta"] = float(np.corrcoef(_rankdata(x), _rankdata(y))[0, 1])
        else:
            out["pearson_delta"] = float("nan")
            out["spearman_delta"] = float("nan")
        # 方向不一致的样本（保留给报告，不做任何"修正"）
        out["disagreeing_samples"] = list(v.loc[~v["agree_direction"], "sample_id"])
    return out


def _rankdata(x: np.ndarray) -> np.ndarray:
    """平均秩（与 scipy.stats.rankdata 的 default 一致），用于 Spearman。"""
    order = np.argsort(x, kind="stable")
    ranks = np.empty(len(x), dtype=float)
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="CRISPRon 外部模型验证：Position 18 C→A")
    ap.add_argument("--dataset", default="DeepCRISPR")
    ap.add_argument("--run-id", default="crispron_pos18_v1")
    ap.add_argument("--skip-run", action="store_true", help="复用已有 raw 输出，不重跑 CRISPRon")
    ap.add_argument("--stage", default="wt_c18a")
    args = ap.parse_args()

    dataset_dir = resolve_dataset(args.dataset)
    schema = load_feature_schema(str(dataset_dir))
    spacer_len = int(schema["sequence_length"]) - CA.PRE_PAM - len(CA.PAM_MOTIF)
    pos_index0 = 17  # 由 analysis/candidates 的约定给定；下面用 mapping 复查
    mapping = CA.describe_mapping(spacer_len, pos_index0 + 1)
    print(f"[位点映射] {json.dumps(mapping, ensure_ascii=False)}")
    if not mapping["in_spacer"]:
        raise AssertionError("关注位点不在 protospacer 内，坐标映射需要重新确认")

    run_dir = RUN_ROOT / args.run_id
    in_dir, raw_dir, log_dir = run_dir / "inputs", run_dir / "raw", run_dir / "logs"
    for d in (in_dir, raw_dir, log_dir):
        d.mkdir(parents=True, exist_ok=True)

    print("[1/6] 读取代表性 WT（复用项目既有选择）...")
    cands = load_representative_wt()
    print(f"        {len(cands)} 条；细胞系分布 {dict(cands['cell_line'].value_counts())}")

    print("[2/6] 构造 WT / C18A 的 30-mer 并验证 ...")
    pairs = build_wt_mutant_pairs(cands, pos_index0, spacer_len)
    print(f"        {len(pairs)} 对；全部通过「仅改一个位置 + PAM 不变 + 侧翼不变 + 方向未反转」验证")

    fasta = in_dir / "wt_c18a_30mer.fa"
    records = []
    for wt_rec, mut_rec, _v, _ in pairs:
        records.append((wt_rec.record_id, wt_rec.crispron_seq))
        records.append((mut_rec.record_id, mut_rec.crispron_seq))
    CA.write_fasta(records, fasta)
    print(f"        输入 FASTA: {fasta} ({len(records)} 条记录)")

    # 配置快照（本实验的全部关键设置）
    cfg = {
        "run_id": args.run_id, "stage": args.stage, "dataset": args.dataset,
        "dataset_dir": str(dataset_dir), "schema": schema,
        "position_mapping": mapping,
        "crispron_constants": {
            "PRE_GUIDE": CA.PRE_GUIDE, "GUIDE": CA.GUIDE, "PRE_PAM": CA.PRE_PAM,
            "PAM_MOTIF": CA.PAM_MOTIF, "POST_PAM": CA.POST_PAM, "TOTAL": CA.TOTAL,
        },
        "candidates_table": str(CANDIDATES_TABLE),
        "n_pairs": len(pairs),
        "selection_note": "WT 序列来自预先登记的代表性挑选规则；本轮未做任何基于 CRISPRon 的筛选",
    }
    (in_dir / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[3/6] 运行 CRISPRon（三步：抽 target → CRISPRoff 能量 → 深度模型）...")
    planned = CA.build_crispron_commands(fasta, raw_dir, crispron_dir=SOFTWARE_DIR,
                                        crisproff_dir=CRISPROFF_DIR,
                                        python_exe=str(VENV_PYTHON), rnafold_exe=str(RNAFOLD_SHIM))
    reused = args.skip_run and (raw_dir / "crispron.csv").exists()
    if reused:
        print("        --skip-run：复用已有 raw/crispron.csv（manifest 仍记录产生它的命令）")
        result = None
    else:
        if not VENV_PYTHON.exists():
            raise FileNotFoundError(f"CRISPRon venv 不存在: {VENV_PYTHON}（见 INSTALL_NOTES.md）")
        result = CA.run_crispron(fasta, raw_dir, crispron_dir=SOFTWARE_DIR,
                                 crisproff_dir=CRISPROFF_DIR, python_exe=str(VENV_PYTHON),
                                 rnafold_exe=str(RNAFOLD_SHIM),
                                 log_path=log_dir / "crispron_run.log")
        print(f"        returncodes={result.returncodes} ok={result.ok}")

    print("[4/6] 解析与 QC ...")
    predictions = CA.parse_crispron_output(raw_dir)
    print(f"        CRISPRon 原始预测行数 {len(predictions)}")
    standard = qc_and_standardize(pairs, predictions)
    summary = summarize(standard)
    print(f"        有效配对 {summary['n_with_delta']}/{summary['n_WT_sequences']}；"
          f"Δ<0 比例 {summary['directional_consistency_P_delta_lt_0']:.3f}")

    print("[5/6] 与项目自身 Δ 比较（cross-model）...")
    cmp_df = cross_model_compare(standard)
    agree = agreement_stats(cmp_df) if not cmp_df.empty else {}
    print(f"        方向一致: {agree}")

    print("[6/6] 写出结果 ...")
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out_std = TABLE_DIR / f"{args.run_id}_wt_c18a_predictions.csv"
    standard.to_csv(out_std, index=False, encoding="utf-8-sig")
    (TABLE_DIR / f"{args.run_id}_summary.json").write_text(
        json.dumps({"summary": summary, "cross_model_agreement": agree,
                    "position_mapping": mapping}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not cmp_df.empty:
        cmp_df.to_csv(TABLE_DIR / f"{args.run_id}_cross_model.csv", index=False, encoding="utf-8-sig")

    # manifest
    env = PV.collect_environment(str(VENV_PYTHON))
    zip_path = CRISPRON_DIR / "package" / "crispron-main.zip"
    dep_path = CRISPRON_DIR / "dependencies" / "crisproff-1.1.2.tar.gz"
    row = PV.build_manifest_row(
        run_id=args.run_id, stage=args.stage, timestamp_utc=PV.utc_now(),
        software="CRISPRon", software_version="v1.0 (crispron-main)",
        package_file=zip_path.name, package_sha256=PV.sha256_file(zip_path),
        software_dir=str(SOFTWARE_DIR.relative_to(_PROJECT_ROOT)),
        dependency="CRISPRoff", dependency_version="1.1.2",
        dependency_sha256=PV.sha256_file(dep_path),
        execution_command=(" ; ".join(" ".join(c) for c in (result.commands if result else planned))
                            + ("   [reused existing raw output]" if reused else "")),
        python_version=env["python_version"], python_executable=env["python_executable"],
        dependency_versions_json=env["dependency_versions_json"],
        input_file=str(fasta.relative_to(_PROJECT_ROOT)),
        input_sha256=PV.sha256_file(fasta),
        n_input_records=len(records),
        input_sequence_sha256=PV.sha256_of_sequences(s for _, s in records),
        model_config=json.dumps({"models": "data/deep_models/best/*.model.best (6 models, averaged)",
                                 "rnafold": str(RNAFOLD_SHIM.relative_to(_PROJECT_ROOT)),
                                 "crisprpon_constants": cfg["crispron_constants"]}, ensure_ascii=False),
        output_file=str((raw_dir / "crispron.csv").relative_to(_PROJECT_ROOT)),
        output_sha256=PV.sha256_file(raw_dir / "crispron.csv"),
        code_fingerprint=PV.code_fingerprint(),
        data_source="DeepCRISPR single-split test set representative WT",
        batch=args.run_id,
        notes=f"n_valid_pairs={summary['n_with_delta']}",
    )
    man = PV.append_manifest(run_dir / "external_validation_manifest.csv", [row])
    print(f"        manifest: {man}")

    # QC 异常写入 audit
    bad = standard[~standard["qc_both_targets_found"]]
    (run_dir / "qc_failures.csv").write_text(
        bad.to_csv(index=False), encoding="utf-8-sig")
    print(f"        QC 失败 {len(bad)} 条 -> qc_failures.csv")
    print(f"\n[✓] 标准化表: {out_std}")
    print(f"[✓] 运行目录  : {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
