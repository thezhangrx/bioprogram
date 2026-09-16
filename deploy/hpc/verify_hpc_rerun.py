#!/usr/bin/env python3
# scripts/verify_hpc_rerun.py
"""
HPC 1344 次重跑 — 落地验收 (只读)。

在超算上跑完 `bash run.sh` 之后执行, 用于回答:
  Q1  是否 1344 个实验全部产出 (缺失/多余/重复身份)?
  Q2  每个 run 是否完整 (_info.txt + _metrics.json + predictions)?
  Q3  划分是否真的无泄漏 (run 内 audit_* 字段 == 0)?
  Q4  训练时用的划分 == 本地重算的划分 (split_digest 逐 run 比对)?
  Q5  是否所有 run 用同一份数据/同一份代码 (fingerprint 一致性)?
  Q6  是否存在数值发散 run (|R²| >= 10, 需按 D6 规则剔除)?
  Q7  R² 分布概况 (按 split / model 汇总), 供与本地历史口径对照

用法:
  python scripts/verify_hpc_rerun.py --package . --batch-name batch_20260913_groupaware
  python deploy/hpc/verify_hpc_rerun.py --batch-name ultimate_run --out results/tables/audit/hpc_verify

输出:
  <out>_runs.csv      逐 run 记录
  <out>_summary.csv   按 split × model 汇总
  <out>_report.md     人读报告
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

FAILS: list[str] = []
WARNS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)


def warn(msg: str) -> None:
    WARNS.append(msg)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def parse_info(path: Path) -> dict:
    """解析 *_info.txt 的 `key: value` 行 (值统一小写, 与 data_digging 保持一致)。"""
    info = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            info[key.strip().lower()] = value.strip()
    return info


def to_int(value, default=None):
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def to_float(value, default=None):
    try:
        return float(str(value).strip())
    except Exception:
        return default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", default=".")
    ap.add_argument("--batch-name", default="batch_20260913_groupaware")
    ap.add_argument("--out", default="results/tables/audit/hpc_verify")
    ap.add_argument("--data-dir", default="data/processed",
                    help="训练所用的数据目录（相对 --package）；外部数据集用 data/processed/external")
    ap.add_argument("--skip-digest-check", action="store_true")
    args = ap.parse_args()

    root = Path(args.package).resolve()
    # 兼容两种布局：results/batches/<batch>（当前约定）与 results/<batch>（旧布局）
    batch_dir = root / "results" / "batches" / args.batch_name
    if not batch_dir.exists():
        batch_dir = root / "results" / args.batch_name
    out_base = Path(args.out)
    if not out_base.is_absolute():
        out_base = root / out_base
    out_base.parent.mkdir(parents=True, exist_ok=True)

    print(f"包目录: {root}\nbatch : {batch_dir}")
    if not batch_dir.exists():
        print("[FATAL] batch 目录不存在")
        return 2

    # ---------- 计划 ----------
    dd = load_module(root / "workflows" / "training" / "data_digging.py", "verify_data_digging")
    verify_data_dir = root / args.data_dir
    # 计划从 --data-dir 的 schema 与实际数据集推导（不再写死 DeepCRISPR 的 16×4 矩阵）
    environments = dd.load_environment_combinations(str(verify_data_dir))
    verify_cells = sorted(p.name.replace("_metadata.csv", "") for p in
                          verify_data_dir.glob("*_metadata.csv"))
    if not verify_cells:
        print(f"[FATAL] {verify_data_dir} 下没有 *_metadata.csv")
        return 2
    print(f"数据目录 : {verify_data_dir}")
    print(f"数据集   : {verify_cells}")
    print(f"环境组合 : {environments}")

    planned = {}
    planned_rows = []
    for split in ("single", "all", "mixed"):
        for exp in dd.generate_experiments(environments=environments, selected_splits=[split],
                                           available_cells=verify_cells):
            planned[dd.build_run_name(exp)] = exp
            planned_rows.append({"split_type": exp[2]})
    print(f"计划实验数: {len(planned)}")

    # ---------- 扫描 ----------
    run_dirs = sorted(p for p in batch_dir.iterdir() if p.is_dir() and p.name != "summary")
    print(f"实际 run 目录: {len(run_dirs)}")

    rows = []
    seen_keys = Counter()
    fingerprints, code_fingerprints = Counter(), Counter()
    devices = Counter()
    env_fingerprints = Counter()

    for run_dir in run_dirs:
        infos = list(run_dir.glob("*info*.txt"))
        metrics_files = list(run_dir.glob("*metrics*.json"))
        if not infos or not metrics_files:
            fail(f"{run_dir.name}: 缺少 info/metrics (info={len(infos)}, metrics={len(metrics_files)})")
            continue
        info = parse_info(infos[0])

        model_raw = info.get("model", "")
        model = ("linear" if "linear" in model_raw else "xgboost" if "xgb" in model_raw
                 else "mlp" if "mlp" in model_raw else "cnn" if "cnn" in model_raw
                 else "transformer" if "trans" in model_raw else model_raw)
        split_type = info.get("split_type", "")
        cell_line = info.get("cell_line", info.get("held_out_cell_line", ""))
        if split_type == "mixed" or cell_line in ("none", "", "unknown"):
            cell_line = None
        seed = to_int(info.get("random_seed", info.get("seed")), 42)
        kernel = to_int(info.get("sequence_kernel", info.get("kernel")), 3)

        metrics = {}
        for mf in metrics_files:
            try:
                metrics = json.loads(mf.read_text(encoding="utf-8"))
                break
            except Exception:
                continue
        r2 = to_float(metrics.get("R2"))

        audit_keys = {k: to_int(v, -1) for k, v in info.items() if k.startswith("audit_")}
        bad_audit = {k: v for k, v in audit_keys.items() if k.endswith("sequence_overlap") and v not in (0, -1)}
        if bad_audit:
            fail(f"{run_dir.name}: 仍存在序列重叠 {bad_audit}")
        missing_prov = [k for k in ("n_train", "n_valid", "n_test", "split_digest",
                                    "group_aware", "data_fingerprint", "code_fingerprint")
                        if k not in info]
        if missing_prov:
            fail(f"{run_dir.name}: 缺少溯源字段 {missing_prov}")

        if info.get("group_aware", "").lower() not in ("true", "1"):
            fail(f"{run_dir.name}: group_aware != True")

        if r2 is None:
            fail(f"{run_dir.name}: metrics 无 R2")
        elif abs(r2) >= 10:
            warn(f"{run_dir.name}: 数值发散 R2={r2} (分析层须按 |R²|<10 剔除)")

        devices[info.get("device_resolved", info.get("device", "?"))] += 1
        env_fingerprints[info.get("env_stack_id", "?")] += 1
        fingerprints[info.get("data_fingerprint", "?")] += 1
        code_fingerprints[info.get("code_fingerprint", "?")] += 1

        key = (model, info.get("environment", ""), split_type, cell_line,
               seed if split_type == "mixed" else None, kernel if model == "cnn" else None)
        seen_keys[key] += 1

        rows.append({
            "run_name": run_dir.name, "model": model, "split_type": split_type,
            "cell_line": cell_line or "", "seed": seed, "kernel": kernel if model == "cnn" else "",
            "environment": info.get("environment", ""),
            "n_train": to_int(info.get("n_train")), "n_valid": to_int(info.get("n_valid")),
            "n_test": to_int(info.get("n_test")),
            "excluded_heldout_seqs": to_int(info.get("heldout_sequences_excluded_from_train")),
            "audit_train_test_seq_overlap": audit_keys.get("audit_train_test_sequence_overlap"),
            "audit_train_test_revcomp_overlap": audit_keys.get("audit_train_test_revcomp_overlap"),
            "split_digest": info.get("split_digest", ""),
            "R2": r2, "Pearson": to_float(metrics.get("Pearson")),
            "MAE": to_float(metrics.get("MAE")),
            "device_resolved": info.get("device_resolved", ""),
            "env_stack_id": info.get("env_stack_id", ""),
            "env_cvd": (info.get("env_fingerprint", "").split("cvd=")[-1]
                        if "cvd=" in info.get("env_fingerprint", "") else ""),
            "torch_cuda_build": info.get("torch_cuda_build", ""),
            "data_fingerprint": info.get("data_fingerprint", ""),
            "code_fingerprint": info.get("code_fingerprint", ""),
        })

    # ---------- Q1 覆盖度 ----------
    actual_names = {r["run_name"] for r in rows}
    missing = sorted(set(planned) - actual_names)
    extra = sorted(actual_names - set(planned))
    if missing:
        fail(f"缺失 {len(missing)} 个实验, 例: {missing[:5]}")
    if extra:
        fail(f"多出 {len(extra)} 个未在计划内的 run, 例: {extra[:5]}")
    dup = {k: v for k, v in seen_keys.items() if v > 1}
    if dup:
        fail(f"{len(dup)} 个实验身份重复 (同 model/env/split/cell/seed/kernel), 例: {list(dup)[:3]}")

    per_split = Counter(r["split_type"] for r in rows)
    planned_per_split = Counter(r["split_type"] for r in planned_rows)
    print(f"计划分布: {dict(planned_per_split)}")
    print(f"实际分布: {dict(per_split)}")
    for split in sorted(set(planned_per_split) | set(per_split)):
        expect = planned_per_split.get(split, 0)
        if per_split.get(split, 0) != expect:
            fail(f"{split} 实际 {per_split.get(split, 0)} != 期望 {expect} (由计划推导)")

    if len(fingerprints) > 1:
        fail(f"data_fingerprint 不一致: {dict(fingerprints)}")
    if len(code_fingerprints) > 1:
        fail(f"code_fingerprint 不一致: {dict(code_fingerprints)}")
    if len(env_fingerprints) > 1:
        fail(f"env_stack_id 不一致 —— 全批不在同一套数值栈上: {dict(env_fingerprints)}")
    elif env_fingerprints:
        print(f"env_stack_id: {dict(env_fingerprints)}")

    nn_devices = {k: v for k, v in devices.items() if k not in ("?", "", "none")}
    if len(nn_devices) > 1:
        fail(f"NN 模型 device_resolved 不一致 (CPU/GPU 混跑会让数值口径 heterogeneous): {nn_devices}")
    elif nn_devices:
        print(f"device_resolved (NN 模型): {nn_devices}")
    non_nn = sum(v for k, v in devices.items() if k in ("?", "", "none"))
    if non_nn:
        print(f"device_resolved: {non_nn} 个非神经网络 run 不适用")

    # ---------- Q4 split_digest 复核 ----------
    digest_note = "skipped"
    if not args.skip_digest_check and rows:
        cld = load_module(root / "core" / "data" / "splitting" / "cell_line_division.py", "verify_cld")
        data_dir = str(root / args.data_dir)
        cells = sorted(p.name.replace("_metadata.csv", "") for p in
                       (root / args.data_dir).glob("*_metadata.csv"))
        cache: dict = {}

        def expected_digest(split_type, cell_line, seed):
            key = (split_type, cell_line, seed)
            if key not in cache:
                kwargs = {"cell_lines": cells, "random_seed": seed}
                if split_type == "single":
                    kwargs["cell_line"] = cell_line
                elif split_type == "all":
                    kwargs["cell_line"] = cell_line
                res = cld.divide_data(data_dir, split_type, **kwargs)
                cache[key] = (res["split_digest"], res["n_train"], res["n_valid"], res["n_test"])
            return cache[key]

        checked = mismatched = 0
        for r in rows:
            if not r["split_digest"]:
                continue
            seed = r["seed"] if r["split_type"] == "mixed" else 42
            cell = r["cell_line"] or (cells[0] if r["split_type"] == "single" else None)
            if r["split_type"] == "single" and not cell:
                continue
            try:
                dig, ntr, nva, nte = expected_digest(r["split_type"], cell, seed)
            except Exception as exc:
                fail(f"重算划分失败 {r['run_name']}: {exc}")
                continue
            checked += 1
            if dig != r["split_digest"]:
                mismatched += 1
                fail(f"{r['run_name']}: split_digest 不一致 (run={r['split_digest']} 本地={dig})")
            if (r["n_train"], r["n_valid"], r["n_test"]) != (ntr, nva, nte):
                mismatched += 1
                fail(f"{r['run_name']}: 样本数不一致 run={(r['n_train'], r['n_valid'], r['n_test'])} 本地={(ntr, nva, nte)}")
        digest_note = f"已复核 {checked} 个 run, 不一致 {mismatched}"

    # ---------- 输出 ----------
    import csv
    runs_csv = out_base.with_name(out_base.name + "_runs.csv")
    with runs_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["run_name"])
        writer.writeheader()
        writer.writerows(rows)

    summary = defaultdict(list)
    for r in rows:
        if r["R2"] is not None:
            summary[(r["split_type"], r["model"])].append(r["R2"])
    summary_csv = out_base.with_name(out_base.name + "_summary.csv")
    with summary_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["split_type", "model", "n", "n_valid(|R2|<10)", "median_R2", "mean_R2"])
        for (split, model), vals in sorted(summary.items()):
            good = [v for v in vals if abs(v) < 10]
            med = sorted(good)[len(good) // 2] if good else float("nan")
            mean = sum(good) / len(good) if good else float("nan")
            writer.writerow([split, model, len(vals), len(good), f"{med:.4f}", f"{mean:.4f}"])

    report = out_base.with_name(out_base.name + "_report.md")
    lines = [f"# HPC 重跑验收报告 — {args.batch_name}", "",
             f"- 计划实验: {len(planned)}", f"- 实际 run 目录: {len(run_dirs)}",
             f"- 可解析 run: {len(rows)}",
             f"- 分 split: {dict(per_split)}",
             f"- split_digest 复核: {digest_note}",
             f"- data_fingerprint: {dict(fingerprints)}",
             f"- code_fingerprint: {dict(code_fingerprints)}",
             f"- device_resolved: {dict(devices)}",
             f"- env_stack_id: {dict(env_fingerprints)}",
             f"- 失败项: {len(FAILS)}", f"- 警告项: {len(WARNS)}", ""]
    if FAILS:
        lines += ["## 失败", *[f"- {f}" for f in FAILS], ""]
    if WARNS:
        lines += ["## 警告", *[f"- {w}" for w in WARNS[:50]], ""]
    lines += ["## 按 split × model 汇总 (R²)", "",
              "| split | model | n | n_valid | median R² | mean R² |",
              "|---|---|---|---|---|---|"]
    for (split, model), vals in sorted(summary.items()):
        good = [v for v in vals if abs(v) < 10]
        med = sorted(good)[len(good) // 2] if good else float("nan")
        mean = sum(good) / len(good) if good else float("nan")
        lines.append(f"| {split} | {model} | {len(vals)} | {len(good)} | {med:.4f} | {mean:.4f} |")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines[:12]))
    print(f"\n输出: {runs_csv}\n      {summary_csv}\n      {report}")
    print("=" * 70)
    print(f"验收结论: {'FAIL' if FAILS else 'PASS'} (失败 {len(FAILS)}, 警告 {len(WARNS)})")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
