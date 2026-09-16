#!/usr/bin/env python3
# scripts/preflight_hpc_rerun.py
"""
HPC 1344 次重跑 — 起飞前自检 (只读, 不训练)。

检查项:
  P1  实验计划 == 1344, 且三 split 各 448; 模型/环境/细胞系/seed/kernel 分布正确
  P2  运行名唯一, 与 data_digging 的 build_run_name 一致
  P3  数据完整性: schema/形状/样本数/标签范围/细胞系内序列唯一性
  P4  划分无泄漏: single/mixed(4 seed)/all(4 留出系) 的 train/valid/test 序列重叠 == 0
      (直接调用待上传包的 core.data.splitting.cell_line_division.divide_data)
  P5  留出系确实不在训练细胞系中; LOCO 训练池已剔除留出系序列
  P6  结果目录不会复用旧的(泄漏)结果: 目标 batch 目录不存在或为空
  P7  指纹与元数据字段齐全 (train.py 会写出 n_train/n_valid/n_test/audit_*/split_digest)
  P8  环境依赖可导入 (torch/xgboost/sklearn/pandas/numpy)

用法:
  python scripts/preflight_hpc_rerun.py                 # 检查仓库根目录
  python scripts/preflight_hpc_rerun.py --package Submit # 检查待上传包
  python scripts/preflight_hpc_rerun.py --batch-name batch_20260913_groupaware
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

FAILS: list[str] = []
WARNS: list[str] = []
CHECKS = 0


def check(condition: bool, label: str, detail: str = "") -> bool:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  [PASS] {label}" + (f" — {detail}" if detail else ""))
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
        FAILS.append(label)
    return bool(condition)


def warn(label: str, detail: str = "") -> None:
    print(f"  [WARN] {label}" + (f" — {detail}" if detail else ""))
    WARNS.append(label)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", default=".", help="待上传包目录 (含 data_digging.py/train.py/src)")
    parser.add_argument("--batch-name", default="batch_20260913_groupaware")
    parser.add_argument("--skip-split-check", action="store_true", help="跳过 P4/P5 (较慢)")
    parser.add_argument("--data-dir", default="data/processed",
                        help="待训练的数据目录（相对 --package）。新数据集用 data/processed/external")
    parser.add_argument("--strict-1344", action="store_true",
                        help="额外断言 DeepCRISPR 的 1344 矩阵形状 (448/split、192 CNN)。"
                             "默认按 --data-dir 的实际维度推导期望值，因此也适用于外部数据集。")
    args = parser.parse_args()

    root = Path(args.package).resolve()
    print(f"待上传包: {root}")
    print(f"目标 batch: {args.batch_name}")

    # ---------------- P1/P2: 计划 ----------------
    section("P1/P2 实验计划与运行名")
    dd = load_module(root / "workflows" / "training" / "data_digging.py", "preflight_data_digging")

    data_dir = root / args.data_dir
    if args.strict_1344:
        environments = dd._canonicalize_combinations(
            dd.build_training_scope_combinations(["ctcf", "dnase", "h3k4me3", "rrbs"]))
        expected_cells = ["hct116", "hek293t", "hela", "hl60"]
    else:
        # 期望值来自数据本身，而不是 DeepCRISPR 常量
        environments = dd.load_environment_combinations(str(data_dir))
        expected_cells = sorted(
            p.name.replace("_metadata.csv", "") for p in data_dir.glob("*_metadata.csv"))

    n_env = len(environments)
    n_cells = len(expected_cells)
    # ALL_MODELS 里 'cnn' 只算 1 项，但实际会按 kernel 展开成 n_kernels 个实验
    n_models = (len(dd.ALL_MODELS) - 1) + len(dd.CNN_KERNELS)
    n_seeds = len(dd.MIXED_SEEDS)
    n_kernels = len(dd.CNN_KERNELS)

    print(f"    数据目录 : {data_dir}")
    print(f"    数据集   : {n_cells} 个 {expected_cells}")
    print(f"    环境组合 : {n_env} 种 {environments}")

    check(n_env >= 1, "至少 1 种环境组合", f"实际 {n_env}")
    check(n_cells >= 1, "至少 1 个数据集", f"实际 {n_cells}")
    check(len(set(environments)) == n_env, "环境组合无重复")

    # 期望值按公式推导（与数据集规模无关）：
    #   single/all = (非CNN模型数 + CNN核数) × 环境数 × 数据集数
    #   mixed      = (非CNN模型数 + CNN核数) × 环境数 × seed 数
    per_split = {}
    all_names = []
    for split in ("single", "all", "mixed"):
        exps = dd.generate_experiments(environments=environments, selected_splits=[split],
                                       available_cells=list(expected_cells))
        per_split[split] = exps
        names = [dd.build_run_name(e) for e in exps]
        all_names.extend(names)
        if split in ("single", "all"):
            expect = n_models * n_env * n_cells
        else:
            expect = n_models * n_env * n_seeds
        # 注意：mixed 不按数据集数展开（所有数据集一起做 mixed），故用 n_seeds
        check(len(exps) == expect, f"{split} 计划数 == {expect}", f"实际 {len(exps)}")
        check(len(set(names)) == len(names), f"{split} 运行名唯一", f"{len(names)-len(set(names))} 个重复")

    total = sum(len(v) for v in per_split.values())
    check(len(set(all_names)) == total, "全部运行名唯一", f"重复 {total-len(set(all_names))}")
    print(f"    计划总数 : {total}")

    if args.strict_1344:
        check(total == 1344, "总计划数 == 1344 (DeepCRISPR)", f"实际 {total}")
        for split, expect in (("single", 448), ("all", 448), ("mixed", 448)):
            check(len(per_split[split]) == expect, f"{split} == 448 (DeepCRISPR)",
                  f"实际 {len(per_split[split])}")
        check(len([e for e in per_split['single'] if e[0] == 'cnn']) == 192,
              "CNN single == 192 (DeepCRISPR)")
        check(len([e for e in per_split['mixed'] if e[0] == 'cnn']) == 192,
              "CNN mixed == 192 (DeepCRISPR)")

    cnn_single = [e for e in per_split["single"] if e[0] == "cnn"]
    cnn_mixed = [e for e in per_split["mixed"] if e[0] == "cnn"]
    check(len(cnn_single) == n_kernels * n_env * n_cells,
          f"CNN single == {n_kernels} kernels × {n_env} env × {n_cells} datasets",
          f"实际 {len(cnn_single)}")
    check(len(cnn_mixed) == n_kernels * n_env * n_seeds,
          f"CNN mixed == {n_kernels} kernels × {n_env} env × {n_seeds} seeds",
          f"实际 {len(cnn_mixed)}")
    n_noncnn = len(dd.ALL_MODELS) - 1        # 'cnn' 展开成 n_kernels 个, 本身不算 1 个
    check(len([e for e in per_split['mixed'] if e[0] != 'cnn']) == n_noncnn * n_env * n_seeds,
          f"非 CNN mixed == {n_noncnn} models × {n_env} env × {n_seeds} seeds",
          f"实际 {len([e for e in per_split['mixed'] if e[0] != 'cnn'])}")
    check(sorted({e[4] for e in per_split["mixed"] if e[0] == "cnn"}) == sorted(dd.MIXED_SEEDS),
          f"mixed seed 集合 == {sorted(dd.MIXED_SEEDS)}")

    # ---------------- P3: 数据 ----------------
    section("P3 数据完整性")
    schema_path = data_dir / "feature_schema.json"
    check(schema_path.exists(), "feature_schema.json 存在", str(schema_path))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    _sl = int(schema.get("sequence_length", 0))
    _cc = int(schema.get("channel_count", 0))
    _fc = int(schema.get("feature_count", 0))
    _names = list(schema.get("channel_names") or [])
    check(_sl == 23, "sequence_length == 23", f"实际 {_sl}")
    check(_cc == len(_names) and _cc > 0, "channel_count == len(channel_names)",
          f"channel_count={_cc} names={_names}")
    check(_fc == _sl * _cc, "feature_count == 23 × channel_count",
          f"feature_count={_fc} 期望 {_sl * _cc}")
    if args.strict_1344:
        check(_cc == 8, "channel_count == 8 (DeepCRISPR)", f"实际 {_cc}")

    import numpy as np
    import pandas as pd

    cells = sorted(p.name.replace("_metadata.csv", "") for p in data_dir.glob("*_metadata.csv"))
    check(len(cells) >= 1, "至少发现 1 个数据集", str(cells))
    if args.strict_1344:
        check(len(cells) == 4, "发现 4 个细胞系 (DeepCRISPR)", str(cells))
    check(set(cells) == set(expected_cells), "P1 的计划数据集与 P3 的文件一致",
          f"plan={expected_cells} files={cells}")
    for cell in cells:
        y = np.load(data_dir / f"{cell}_labels.npy")
        x3 = np.load(data_dir / f"{cell}_features_23x{_cc}.npy")
        x2 = np.load(data_dir / f"{cell}_features_{_fc}.npy")
        meta = pd.read_csv(data_dir / f"{cell}_metadata.csv")
        ok = (x3.shape == (len(y), 23, _cc) and x2.shape == (len(y), _fc) and len(meta) == len(y))
        check(ok, f"{cell} 形状一致", f"y={len(y)} x3={x3.shape} x2={x2.shape} meta={len(meta)}")
        check(bool(np.isfinite(y).all()) and float(y.min()) >= -1.5 and float(y.max()) <= 1.5,
              f"{cell} 标签有限且落在 [-1.5,1.5]", f"[{float(y.min()):.3f}, {float(y.max()):.3f}]")
        seqs = meta["sgRNA"].astype(str).str.upper().str.strip()
        check(seqs.nunique() == len(meta), f"{cell} 系内 sgRNA 序列唯一",
              f"uniq={seqs.nunique()} rows={len(meta)}")
        check(bool(np.isfinite(x3).all()) and bool(np.isfinite(x2).all()), f"{cell} 特征无 NaN/Inf")

    # ---------------- P4/P5: 划分 ----------------
    if not args.skip_split_check:
        section("P4/P5 划分无泄漏 (调用待上传包自身的实现)")
        sys.path.insert(0, str(root))
        for mod in [m for m in list(sys.modules) if m.startswith("core") or m.startswith("preflight_cld")]:
            del sys.modules[mod]
        cld = load_module(root / "core" / "data" / "splitting" / "cell_line_division.py", "preflight_cld")

        for cell in cells:
            res = cld.divide_data(str(data_dir), "single", cell_line=cell, random_seed=42)
            check(res["audit_train_test_sequence_overlap"] == 0, f"single/{cell} train∩test 序列 = 0",
                  f"n={res['n_train']}/{res['n_valid']}/{res['n_test']}")
            check(res["group_aware"] is True, f"single/{cell} group_aware=True")
            check(res["audit_train_test_revcomp_overlap"] == 0,
                  f"single/{cell} train∩revcomp(test) = 0 (L5)",
                  f"revcomp={res['audit_train_test_revcomp_overlap']}")

        for seed in (42, 43, 44, 45):
            res = cld.divide_data(str(data_dir), "mixed", cell_lines=cells, random_seed=seed)
            check(res["audit_train_test_sequence_overlap"] == 0, f"mixed seed={seed} train∩test 序列 = 0",
                  f"n_train={res['n_train']} leaked={res['audit_train_test_sequence_overlap']}")
            check(res["audit_train_valid_sequence_overlap"] == 0 and res["audit_valid_test_sequence_overlap"] == 0,
                  f"mixed seed={seed} valid 无重叠")
            check(res["audit_train_test_revcomp_overlap"] == 0,
                  f"mixed seed={seed} train∩revcomp(test) = 0 (L5)",
                  f"revcomp={res['audit_train_test_revcomp_overlap']}")

        if len(cells) < 2:
            check(True, "只有 1 个数据集 -> 跳过 LOCO 检查 (all 会退化为 single)",
                  "请在计划层面确认没有排 all/mixed 实验")
        for held in (cells if len(cells) >= 2 else []):
            res = cld.divide_data(str(data_dir), "all", cell_line=held, cell_lines=cells, random_seed=42)
            check(res["audit_train_test_sequence_overlap"] == 0, f"LOCO held={held} train∩test 序列 = 0",
                  f"n_train={res['n_train']} excluded={res['heldout_sequences_excluded_from_train']}")
            check(held not in [c.lower() for c in res["train_cell_lines"]],
                  f"LOCO held={held} 不在训练细胞系", str(res["train_cell_lines"]))
            check(set(res["test_cell_lines"]) == {held}, f"LOCO held={held} test 只含留出系")
            check(res["audit_train_test_revcomp_overlap"] == 0,
                  f"LOCO held={held} train∩revcomp(test) = 0 (L5)",
                  f"revcomp={res['audit_train_test_revcomp_overlap']}")
            check(res["n_test"] == int(len(pd.read_csv(data_dir / f"{held}_metadata.csv"))),
                  f"LOCO held={held} test = 留出系全量样本", f"n_test={res['n_test']}")

    # ---------------- P6: 结果目录 ----------------
    section("P6 结果目录复用检查")
    batch_dir = root / "results" / "batches" / args.batch_name
    if not batch_dir.exists():
        batch_dir = root / "results" / args.batch_name
    if batch_dir.exists():
        n_sub = sum(1 for p in batch_dir.iterdir() if p.is_dir())
        check(n_sub == 0, f"results/{args.batch_name} 为空目录 (否则旧结果会被跳过)",
              f"已存在 {n_sub} 个 run 目录 -> 必须更换 batch 名或清空")
    else:
        check(True, f"results/{args.batch_name} 尚不存在 (全新批次)", "旧泄漏结果不会被复用")

    # ---------------- P7: 元数据字段 ----------------
    section("P7 溯源字段")
    train_src = (root / "workflows" / "training" / "train.py").read_text(encoding="utf-8")
    for key in ("data_fingerprint", "code_fingerprint", "SPLIT_PROVENANCE_KEYS", "n_train"):
        check(key in train_src, f"train.py 记录 {key}")
    cld_src = (root / "core" / "data" / "splitting" / "cell_line_division.py").read_text(encoding="utf-8")
    for key in ("assert_no_sequence_leakage", "split_digest", "group_aware_split_indices",
                "heldout_sequences_excluded_from_train", "sorted(found)"):
        check(key in cld_src, f"cell_line_division.py 含 {key}")

    # ---------------- P8: 依赖 ----------------
    section("P8 依赖与版本锁定")
    import platform
    print(f"  python {platform.python_version()}")

    # ---- 平台约束检查 (CentOS 7 / glibc 2.17 / CUDA 12.4 类环境) ----
    import platform as _pf
    import shutil as _sh
    print(f"  OS: {_pf.platform()} / libc: {_pf.libc_ver()}")
    if _sh.which("nvidia-smi"):
        try:
            import subprocess as _sp
            out = _sp.run(["nvidia-smi", "--query-gpu=name,driver_version,count",
                           "--format=csv,noheader"], capture_output=True, text=True, timeout=20)
            print(f"  GPU: {out.stdout.strip() or out.stderr.strip()}")
        except Exception as exc:
            warn(f"nvidia-smi 调用失败: {exc}")
    else:
        warn("未找到 nvidia-smi —— 若在 GPU 节点上运行, 请确认命令在 PATH 中")

    # ---- 版本比对: 分两级 ----
    #   A) requirements_hpc.txt  = 本平台实际安装的目标栈 -> 必须精确匹配 (FAIL)
    #   B) requirements_frozen.txt = 开发机审计栈        -> 差异只告警 (平台约束所致)
    import importlib.metadata as md

    def parse_req(path: Path) -> dict:
        pins = {}
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.split("#")[0].strip()
            if not line or line.startswith("-") or "==" not in line:
                continue
            name, want = (part.strip() for part in line.split("==", 1))
            pins[name] = want
        return pins

    def compare(pins: dict, label: str, strict: bool) -> dict:
        """逐包比对。只比较 release 段 (忽略 +cu124 这类本地 build 标签),
        但把完整字符串打印出来, 便于识别 CUDA build 差异。"""
        drift = {}
        for name, want in pins.items():
            try:
                have_full = md.version(name)
            except Exception:
                if strict:
                    check(False, f"{label}: 依赖 {name} 未安装", f"要求 {want}")
                else:
                    warn(f"{label}: 依赖 {name} 未安装", f"要求 {want}")
                continue
            have = have_full.split("+", 1)[0]
            if have != want:
                drift[name] = f"{have_full} != {want}"
                if strict:
                    check(False, f"{label}: {name} 版本不符", f"装={have_full} 期望={want}")
            elif have_full != want:
                print(f"  [PASS] {name} {have_full} (release {want} 一致, 本地 build 标签不同)")
        if strict and not drift:
            print(f"  [PASS] {label}: {len(pins)} 个锁定版本全部匹配")
        return drift

    env_dir = root / "deploy" / "environment" / "python"
    hpc_path = env_dir / "requirements_hpc.txt"
    frozen_path = env_dir / "requirements_frozen.txt"

    # 先判断"这台机器是哪一套栈":
    #   - 若与开发机审计栈完全一致 -> 本机是开发机, HPC 目标栈校验不适用, 跳过强校验
    #   - 否则视为目标平台 (超算) -> 必须精确匹配 requirements_hpc.txt
    on_dev_stack = False
    if frozen_path.exists():
        drift = compare(parse_req(frozen_path), "开发机审计栈", strict=False)
        if drift:
            warn("与开发机审计栈存在版本差异 (平台约束所致, 需在报告中声明并做等价性验证): "
                 + "; ".join(f"{k}: {v}" for k, v in drift.items()))
        else:
            on_dev_stack = True
            print("  [PASS] 本机 = 开发机审计栈")
    else:
        warn("缺少 requirements_frozen.txt —— 无法与审计栈比对")

    if hpc_path.exists():
        if on_dev_stack:
            print("  [SKIP] HPC 目标栈校验不适用 (本机是开发机; 请在超算上运行本脚本)")
        else:
            compare(parse_req(hpc_path), "HPC 目标栈(requirements_hpc.txt)", strict=True)
    else:
        warn("缺少 requirements_hpc.txt —— 无法校验本平台目标栈")

    # ---- CUDA / torch 可用性 ----
    try:
        import torch as _torch
        cuda_ok = bool(_torch.cuda.is_available())
        n_gpu = _torch.cuda.device_count() if cuda_ok else 0
        print(f"  torch {_torch.__version__} (cuda build {_torch.version.cuda}) "
              f"cuda_available={cuda_ok} n_gpu={n_gpu}")
        if not cuda_ok:
            warn("torch.cuda 不可用 —— 若平台有 GPU, 检查驱动/CUDA build 匹配 (550 驱动 -> cu124)")
        elif n_gpu >= 2:
            print(f"  [PASS] 检测到 {n_gpu} 张卡: 建议 WORKERS=min({n_gpu}, 实验并发上限), 脚本会自动逐槽绑定")
    except Exception as exc:
        warn(f"torch 导入失败: {exc}")

    for mod in ("numpy", "pandas", "sklearn", "xgboost"):
        try:
            m = __import__(mod)
            print(f"  [PASS] import {mod} {getattr(m, '__version__', '?')}")
        except Exception as exc:  # pragma: no cover
            check(False, f"import {mod}", str(exc))

    # ---------------- 汇总 ----------------
    print("\n" + "=" * 70)
    print(f"自检完成: {CHECKS} 项断言, 失败 {len(FAILS)}, 警告 {len(WARNS)}")
    if FAILS:
        print("失败项:")
        for f in FAILS:
            print("  - " + f)
        print("结论: NOT READY —— 禁止提交 1344 次重跑")
        return 1
    if WARNS:
        print("警告项:")
        for w in WARNS:
            print("  - " + w)
    print("结论: READY —— 可以提交 HPC 重跑")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
