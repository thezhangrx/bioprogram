# data_digging.py
"""
CRISPR-Cas9 已测数据训练挖掘引擎 (Training Scope 网格实验)
================================================================
从 predict.py 拆分 (职责单一化):
    data_digging.py  已测数据集"深入挖掘"网格实验 (引导程序第4步之 2)
                     对已测数据按所选表观特征(Training Scope)组合 -> 训练全网格,
                     输出到 results/[batch]/ 与 logs/、models/。
    predict.py       只做 mixed 十折交叉验证 + 目标数据集预测
                     (引导程序第4步之 3, Target Epigenetics)。
用法:
    python data_digging.py --batch-name <b> --models linear xgboost \
        --cell-lines hct116 hela --split-types single all mixed \
        --environments sequence sequence_ctcf ...          # 显式环境组合
    python data_digging.py --training-scope-epis ctcf dnase h3k4me3 rrbs   # 由第4步选项2展开
    python data_digging.py --dry-run ...                                   # 只打印实验计划
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def build_training_scope_combinations(active_epis: List[str]) -> List[str]:
    """由第4步选项2(Training Scope)勾选的表观特征展开为网格环境组合。

    与 Input/backend_runner.build_active_environment_combinations 同规则:
    sequence 基线 + 各非空子集 + 全4项时补 'all'。
    """
    active = [e.lower().strip() for e in active_epis if e and str(e).strip()]
    if not active:
        return ["sequence"]
    combos = ["sequence"]
    for r in range(1, len(active) + 1):
        for subset in itertools.combinations(active, r):
            combos.append("sequence_" + "_".join(sorted(subset)))
    if set(active) == {"ctcf", "dnase", "h3k4me3", "rrbs"} and "all" not in combos:
        combos.append("all")
    return combos


MODELS = ["linear", "xgboost", "mlp", "transformer"]
CNN_MODELS = ["cnn"]
ALL_MODELS = [*MODELS, "cnn"]
CELL_LINES = ["hct116", "hek293t", "hela", "hl60"]
MIXED_SEEDS = [42, 43, 44, 45]
CNN_KERNELS = [3, 5, 7]


def _canonicalize_combinations(combos: List[str]) -> List[str]:
    """归一化环境组合: “全部表观特征”的组合统一只保留 `all`。

    个别来源/手写列表可能同时带 `sequence_ctcf_dnase_h3k4me3_rrbs`(显式全特征)
    与 `all`(同一含义) -> 造成环境组合重复、实验翻倍(1428 = 17×84)。
    规则: 只要列表中含 `all`, 就丢弃与之等价的显式全特征名; 否则保留原样。
    """
    combos = list(combos)
    if "all" not in combos:
        return combos
    # 全集 = 所有组合里出现过的表观 token 的并集 (含单/双/三元 -> 恒为 4 个)
    universe: set = set()
    for c in combos:
        if c == "all":
            continue
        universe.update(t for t in str(c).split("_") if t != "sequence" and t)
    if not universe:
        return combos
    out = []
    removed = 0
    for c in combos:
        if c == "all":
            out.append(c)
            continue
        toks = {t for t in str(c).split("_") if t != "sequence" and t}
        if toks == universe:
            removed += 1   # 显式全特征组合 == all, 丢弃
            continue
        out.append(c)
    if removed:
        print(f"[Environments] 检测到 {removed} 个与 `all` 等价的显式全特征组合, 已并入 `all`")
    return out


def load_environment_combinations(data_dir: str) -> List[str]:
    schema_path = Path(data_dir) / "feature_schema.json"
    if not schema_path.exists():
        # 如果 schema 尚未生成，提供标准 16 种默认组合
        return [
            "sequence", "sequence_ctcf", "sequence_dnase", "sequence_h3k4me3", "sequence_rrbs",
            "sequence_ctcf_dnase", "sequence_ctcf_h3k4me3", "sequence_ctcf_rrbs",
            "sequence_dnase_h3k4me3", "sequence_dnase_rrbs", "sequence_h3k4me3_rrbs",
            "sequence_ctcf_dnase_h3k4me3", "sequence_ctcf_dnase_rrbs", "sequence_ctcf_h3k4me3_rrbs",
            "sequence_dnase_h3k4me3_rrbs", "all"
        ]

    try:
        from src.input_control.cell_environment_combination import generate_combination_names
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return list(generate_combination_names(schema, include_all=True, include_sequence=True, sizes=[0, 1, 2, 3]))
    except Exception:
        return ["sequence", "all"]


Experiment = Tuple[str, str, str, Optional[str], Optional[int], Optional[int]]


def sanitize_batch_name(batch_name: str) -> str:
    return str(batch_name).strip().lower().replace(" ", "_").replace("/", "_").replace("\\", "_")


def generate_experiments(
    environments: List[str],
    selected_models: Optional[List[str]] = None,
    selected_cells: Optional[List[str]] = None,
    selected_splits: Optional[List[str]] = None
) -> List[Experiment]:
    experiments = []
    models_to_run = [m for m in (selected_models or ALL_MODELS) if m != "cnn"]
    include_cnn = "cnn" in (selected_models or ALL_MODELS)
    cells_to_run = selected_cells or CELL_LINES
    splits_to_run = [s.lower() for s in (selected_splits or ["single", "all", "mixed"])]

    for model in models_to_run:
        for environment in environments:
            if "single" in splits_to_run:
                for cell_line in cells_to_run:
                    experiments.append((model, environment, "single", cell_line, None, None))
            if "all" in splits_to_run:
                for cell_line in cells_to_run:
                    experiments.append((model, environment, "all", cell_line, None, None))
            if "mixed" in splits_to_run:
                for seed in MIXED_SEEDS:
                    experiments.append((model, environment, "mixed", None, seed, None))

    if include_cnn:
        for environment in environments:
            if "single" in splits_to_run:
                for cell_line in cells_to_run:
                    for kernel in CNN_KERNELS:
                        experiments.append(("cnn", environment, "single", cell_line, None, kernel))
            if "all" in splits_to_run:
                for cell_line in cells_to_run:
                    for kernel in CNN_KERNELS:
                        experiments.append(("cnn", environment, "all", cell_line, None, kernel))
            if "mixed" in splits_to_run:
                for seed in MIXED_SEEDS:
                    for kernel in CNN_KERNELS:
                        experiments.append(("cnn", environment, "mixed", None, seed, kernel))

    return experiments


def build_run_name(experiment: Experiment) -> str:
    (model, environment, split_type, cell_line, seed, kernel) = experiment
    if split_type == "single":
        name = f"single_{cell_line}_{model}_{environment}"
    elif split_type == "all":
        name = f"all_{model}_{environment}_heldout_{cell_line}"
    elif split_type == "mixed":
        name = f"mixed_{model}_{environment}_seed_{seed}"
    else:
        name = f"{split_type}_{model}_{environment}"

    if model == "cnn" and kernel:
        name += f"_kernel_{kernel}"
    return name


def parse_folder_info(folder: Path) -> Optional[dict]:
    info_files = list(folder.glob("*info*.txt"))
    metric_files = list(folder.glob("*metrics*.json"))
    if not info_files or not metric_files: return None

    info = {}
    with open(info_files[0], "r", encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                k, v = line.strip().split(":", 1)
                info[k.strip().lower()] = v.strip().lower()
    return info


def build_completed_lookup(results_batch_dir: Path) -> dict:
    lookup = {}
    if not results_batch_dir.exists(): return lookup

    for run_dir in results_batch_dir.iterdir():
        if not run_dir.is_dir() or run_dir.name == "summary": continue
        info = parse_folder_info(run_dir)
        if not info: continue

        model = info.get("model", "")
        if "linear" in model: model = "linear"
        elif "xgb" in model: model = "xgboost"
        elif "mlp" in model: model = "mlp"
        elif "cnn" in model: model = "cnn"
        elif "trans" in model: model = "transformer"

        env = info.get("environment", info.get("combination", ""))
        split_type = info.get("split_type", "")
        cell_line = info.get("cell_line", info.get("held_out_cell_line", ""))
        if split_type == "mixed": cell_line = None
        elif cell_line in ["none", "", "unknown"]: cell_line = None

        seed_str = info.get("random_seed", info.get("seed", "42"))
        try: seed = int(seed_str)
        except Exception: seed = 42

        kernel_str = info.get("sequence_kernel", info.get("kernel", "3"))
        try: kernel = int(kernel_str)
        except Exception: kernel = 3

        key = (model, env, split_type, cell_line, seed if split_type == "mixed" else None, kernel if model == "cnn" else None)
        lookup[key] = run_dir
    return lookup


def classify_experiments(experiments: List[Experiment], results_batch_dir: Path):
    completed_lookup = build_completed_lookup(results_batch_dir)
    completed = []
    pending = []

    for exp in experiments:
        (model, environment, split_type, cell_line, seed, kernel) = exp
        norm_cell = str(cell_line).lower() if cell_line else None
        norm_env = str(environment).lower()
        key = (model, norm_env, split_type, norm_cell, seed if split_type == "mixed" else None, kernel if model == "cnn" else None)

        if key in completed_lookup:
            completed.append((exp, completed_lookup[key]))
        else:
            pending.append(exp)
    return completed, pending


def build_command(
    experiment: Experiment,
    batch_name: str,
    data_dir: str,
    model_dir: str,
    results_dir: str,
    logs_dir: str,
    train_ratio: float,
    valid_ratio: float,
    test_ratio: float,
    use_scaler: bool,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    dropout: float,
    weight_decay: float,
    patience: int,
    min_delta: float,
    hidden_dim1: int,
    hidden_dim2: int,
    conv_channels1: int,
    conv_channels2: int,
    device: Optional[str]
) -> List[str]:
    (model, environment, split_type, cell_line, seed, kernel) = experiment
    random_seed = seed if split_type == "mixed" else 42
    run_name = build_run_name(experiment)

    # 关键：调用 train.py (原 main.py)
    train_script = str(Path(__file__).resolve().parent / "train.py")

    command = [
        sys.executable, train_script,
        "--model", model,
        "--split-type", split_type,
        "--environment", environment,
        "--batch-name", batch_name,
        "--run-name", run_name,
        "--data-dir", data_dir,
        "--model-dir", model_dir,
        "--results-dir", results_dir,
        "--logs-dir", logs_dir,
        "--train-ratio", str(train_ratio),
        "--valid-ratio", str(valid_ratio),
        "--test-ratio", str(test_ratio),
        "--seed", str(random_seed),
        "--epochs", str(epochs),
        "--batch-size", str(batch_size),
        "--learning-rate", str(learning_rate),
        "--dropout", str(dropout),
        "--weight-decay", str(weight_decay),
        "--patience", str(patience),
        "--min-delta", str(min_delta),
        "--hidden-dim1", str(hidden_dim1),
        "--hidden-dim2", str(hidden_dim2),
        "--conv-channels1", str(conv_channels1),
        "--conv-channels2", str(conv_channels2),
    ]

    if cell_line is not None:
        command.extend(["--cell-line", cell_line])

    if model == "cnn":
        command.extend(["--sequence-kernel", str(kernel), "--environment-kernel", "3"])

    if device is not None:
        command.extend(["--device", device])

    if use_scaler:
        command.append("--use-scaler")

    return command


def run_one_experiment(experiment: Experiment, index: int, total: int, env: Optional[Dict[str, str]] = None,
                       **kwargs) -> Dict:
    (model, environment, split_type, cell_line, seed, kernel) = experiment
    command = build_command(experiment=experiment, **kwargs)
    run_name = build_run_name(experiment)

    print(f"\n[Experiment {index}/{total}] Starting: {run_name}")
    try:
        result = subprocess.run(command, check=False, env=env)
        status = "success" if result.returncode == 0 else "failed"
    except Exception as error:
        print(f"[!] Execution failed: {error}")
        return {"model": model, "run_name": run_name, "return_code": -1, "status": "failed"}

    return {"model": model, "run_name": run_name, "return_code": result.returncode, "status": status}


def run_experiment_in_process(experiment: Experiment, index: int, total: int, **kwargs) -> Dict:
    """
    进程内执行单实验: 复用当前 python 解释器调用 train.main(),
    argv 与子进程路径完全一致 (消除每实验一次 python 启动/import 开销)。
    仅限顺序执行使用 (不得与多线程并发混用, 因 sys.argv 为进程全局状态)。
    """
    (model, environment, split_type, cell_line, seed, kernel) = experiment
    command = build_command(experiment=experiment, **kwargs)
    run_name = build_run_name(experiment)
    print(f"\n[Experiment {index}/{total}] Starting (in-process): {run_name}")

    old_argv = sys.argv
    sys.argv = [str(command[1])] + [str(c) for c in command[2:]]
    try:
        import train as train_mod
        train_mod.main()
        return {"model": model, "run_name": run_name, "return_code": 0, "status": "success"}
    except Exception as error:
        print(f"[!] In-process execution failed: {error}")
        return {"model": model, "run_name": run_name, "return_code": -1, "status": "failed"}
    finally:
        sys.argv = old_argv


def build_worker_env(workers: int, per_worker_threads: int = 0) -> Optional[Dict[str, str]]:
    """
    并发执行时的子进程线程环境 (Phase-9 调优接口)。
    默认 (per_worker_threads<=0): 不封顶线程, 子进程环境与串行完全一致 -> 数值结果逐位一致。
    显式指定 >0 时按『每实验线程数』封顶 OMP/MKL/BLAS, 可提升并发吞吐, 但会改变
    线性代数/归约的浮点求和顺序 -> 可能引入 ~1e-4 级数值漂移 (病态线性 'all' 实验更敏感),
    需用户显式接受后才启用。
    """
    if int(workers) <= 1 or int(per_worker_threads) <= 0:
        return None
    env = os.environ.copy()
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        env[var] = str(int(per_worker_threads))
    return env


# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="CRISPR 已测数据训练挖掘引擎 (Training Scope 网格实验). "
                    "由 predict.py 拆分而来: 本程序不再负责 mixed 十折/候选预测 (见 predict.py).")
    parser.add_argument("--batch-name", default="", type=str, help="批次名称，为空时直接存放在根目录")
    parser.add_argument("--data-dir", type=str, default="data/proceeded_data")
    parser.add_argument("--model-dir", type=str, default="models")
    parser.add_argument("--results-dir", type=str, default="results")
    parser.add_argument("--logs-dir", type=str, default="logs")

    # 第4步选项2接口: 由勾选的表观特征展开网格组合; 或显式 --environments
    parser.add_argument("--training-scope-epis", nargs="+", default=None,
                        help="向导第4步选项2 (Training Scope): 已测数据训练要深入挖掘的表观特征, "
                             "据此自动展开全部环境组合")
    parser.add_argument("--environments", nargs="+", default=None,
                        help="显式环境组合列表 (与 --training-scope-epis 二选一)")

    parser.add_argument("--models", nargs="+", default=None, choices=ALL_MODELS)
    parser.add_argument("--cell-lines", nargs="+", default=None, choices=CELL_LINES)
    parser.add_argument("--split-types", nargs="+", default=["single", "all", "mixed"], choices=["single", "all", "mixed"])
    parser.add_argument("--mixed-seeds", nargs="+", type=int, default=MIXED_SEEDS)
    parser.add_argument("--cnn-kernels", nargs="+", type=int, choices=CNN_KERNELS, default=CNN_KERNELS)

    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--valid-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--min-delta", type=float, default=1e-6)

    parser.add_argument("--hidden-dim1", type=int, default=128)
    parser.add_argument("--hidden-dim2", type=int, default=64)
    parser.add_argument("--conv-channels1", type=int, default=32)
    parser.add_argument("--conv-channels2", type=int, default=64)

    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--use-scaler", action="store_true")
    parser.add_argument("--workers", type=int, default=1,
                        help="实验级并发数 (workers=1 时保持原有串行子进程执行, 结果逐位一致)")
    parser.add_argument("--in-process", action="store_true",
                        help="进程内顺序执行实验 (复用解释器, 省去每实验一次 python 启动/import; "
                             "仅建议与 workers=1 同用)")
    parser.add_argument("--threads-per-worker", type=int, default=0,
                        help="并发时每实验 CPU 线程数封顶 (0=不封顶; 封顶可能改变浮点结果, 默认不启用)")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()

    # 展开/解析环境组合 (向导第4步选项2: Training Scope)
    if args.training_scope_epis is not None:
        environments = build_training_scope_combinations(args.training_scope_epis)
        print(f"[Training Scope] 由表观特征 {args.training_scope_epis} 展开环境组合...")
    else:
        environments = args.environments if args.environments is not None \
            else load_environment_combinations(args.data_dir)
    environments = _canonicalize_combinations(environments)
    print(f"[Environments] 共 {len(environments)} 种: {', '.join(environments)}")

    batch_name = sanitize_batch_name(args.batch_name) if args.batch_name else ""
    experiments = generate_experiments(environments=environments,
                                       selected_models=args.models,
                                       selected_cells=args.cell_lines,
                                       selected_splits=args.split_types)

    results_batch_dir = Path(args.results_dir) / batch_name if batch_name else Path(args.results_dir)
    completed, pending = classify_experiments(experiments=experiments, results_batch_dir=results_batch_dir)

    print(f"\n{'='*70}\nExperiment Plan -> Total: {len(experiments)} | "
          f"Completed: {len(completed)} | Pending: {len(pending)}\n{'='*70}")

    if args.dry_run:
        print("[*] Dry run completed.")
        return

    common_kwargs = {
        "batch_name": batch_name,
        "data_dir": args.data_dir,
        "model_dir": args.model_dir,
        "results_dir": args.results_dir,
        "logs_dir": args.logs_dir,
        "train_ratio": args.train_ratio,
        "valid_ratio": args.valid_ratio,
        "test_ratio": args.test_ratio,
        "use_scaler": args.use_scaler,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "dropout": args.dropout,
        "weight_decay": args.weight_decay,
        "patience": args.patience,
        "min_delta": args.min_delta,
        "hidden_dim1": args.hidden_dim1,
        "hidden_dim2": args.hidden_dim2,
        "conv_channels1": args.conv_channels1,
        "conv_channels2": args.conv_channels2,
        "device": args.device,
    }

    if pending:
        total_pending = len(pending)
        n_workers = int(args.workers or 1)

        if args.in_process:
            if n_workers > 1:
                print("[Note] --in-process 与 --workers>1 不同时使用; 已忽略 workers, 采用顺序执行。")
            for idx, exp in enumerate(pending, start=1):
                run_experiment_in_process(exp, idx, total_pending, **common_kwargs)
        elif n_workers > 1:
            worker_env = build_worker_env(n_workers, int(args.threads_per_worker or 0))
            with ThreadPoolExecutor(max_workers=n_workers, thread_name_prefix="exp") as pool:
                futures = [pool.submit(run_one_experiment, exp, idx, total_pending,
                                       env=worker_env, **common_kwargs)
                           for idx, exp in enumerate(pending, start=1)]
                results = [f.result() for f in futures]
            n_ok = sum(1 for r in results if r.get("status") == "success")
            n_fail = len(results) - n_ok
            print(f"\n[✓] Batch executed with workers={n_workers}: success={n_ok}, failed={n_fail}")
        else:
            for idx, exp in enumerate(pending, start=1):
                run_one_experiment(exp, idx, total_pending, **common_kwargs)

        print("\n[✓] All batch experiments executed.")
    else:
        print("\n[✓] All experiments already completed!")


if __name__ == "__main__":
    main()
