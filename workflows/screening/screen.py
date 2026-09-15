#!/usr/bin/env python3
"""screen.py — 一键虚拟筛选（对给定候选序列清单打分排序）。

定位（如实说明）
----------------
输入一份候选 23 nt 序列清单（CSV 或 FASTA），输出按预测效率排序的打分结果。
这是**候选优先级排序 / 虚拟筛选**，不是序列从头生成。

与 predict.py 的关系
--------------------
本脚本是 ``predict.py --target-input`` 的薄封装：只组装符合项目约定的路径与参数，
科学计算全部由 ``predict.py`` 与 ``src/`` 完成，本脚本不含任何模型或统计逻辑。

输入格式
--------
* CSV：需含一列 23 nt 序列，列名可用 ``sgRNA`` / ``sequence`` / ``seq`` 之一；
  其余列会原样保留在输出中。
* FASTA：``.fa`` / ``.fasta``，每条记录一条 23 nt 序列。
* 可选：用 ``--epigenetics`` 指定该批候选可用的表观通道（如 ``ctcf dnase``）；
  未指定时由 predict.py 自动识别。

输出
----
``<results-dir>/<batch-name>/summary/赛道二_results.csv``（字段与 design.py 一致）

用法
----
    python screen.py --input my_candidates.csv --dry-run
    python screen.py --input my_candidates.csv --epigenetics ctcf dnase --top-k 50
"""
from __future__ import annotations


# --- 项目根引导: 保证从任意工作目录运行/被导入都能解析 core、analysis、workflows ---
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # 项目根
PREDICT = ROOT / "workflows" / "prediction" / "predict.py"
DEFAULT_DATA_DIR = "data/processed"
DEFAULT_RESULTS_DIR = "results/batches"
DEFAULT_MODEL_DIR = "models/weights"
DEFAULT_LOGS_DIR = "results/logs"
DEFAULT_BATCH = "batch_20260909_full"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="候选序列批量虚拟筛选入口（复用 predict.py --target-input）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--input", required=True,
                   help="候选序列文件（CSV，含 sgRNA/sequence/seq 列；或 FASTA）")
    p.add_argument("--epigenetics", nargs="+", default=None,
                   help="候选可用的表观通道（如 ctcf dnase h3k4me3 rrbs）；缺省自动识别")
    p.add_argument("--batch-name", default=DEFAULT_BATCH, help="结果批次名")
    p.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="特征数据目录")
    p.add_argument("--results-dir", default=DEFAULT_RESULTS_DIR, help="结果根目录")
    p.add_argument("--model-dir", default=DEFAULT_MODEL_DIR,
                   help="模型权重根目录（与 train.py --model-dir 一致）")
    p.add_argument("--logs-dir", default=DEFAULT_LOGS_DIR,
                   help="日志根目录（与 train.py --logs-dir 一致）")
    p.add_argument("--top-k", "--candidate-top-k", dest="top_k", type=int, default=20,
                   help="输出候选数量")
    p.add_argument("--models", nargs="+", default=None,
                   choices=["linear", "xgboost", "mlp", "transformer", "cnn"],
                   help="参与筛选的模型族（默认全部）")
    p.add_argument("--epochs", type=int, default=15, help="筛选模型训练轮数")
    p.add_argument("--cv-folds", type=int, default=10, help="交叉验证折数")
    p.add_argument("--seed", type=int, default=42, help="随机种子")
    p.add_argument("--device", default=None, help="cpu / cuda（默认自动）")
    p.add_argument("--dry-run", action="store_true", help="只打印计划，不训练、不写文件")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = Path(args.input)
    if not target.exists():
        print(f"[screen.py] 错误：候选文件不存在 -> {target}", file=sys.stderr)
        return 2

    cmd = [sys.executable, str(PREDICT),
           "--target-input", str(target),
           "--batch-name", args.batch_name,
           "--data-dir", args.data_dir,
           "--results-dir", args.results_dir,
           "--candidate-top-k", str(args.top_k),
           "--ultimate-cv-folds", str(args.cv_folds),
           "--ultimate-epochs", str(args.epochs),
           "--ultimate-seed", str(args.seed)]
    if args.epigenetics:
        cmd += ["--target-epigenetics", *args.epigenetics]
    if args.models:
        cmd += ["--models", *args.models]
    if args.device:
        cmd += ["--device", args.device]
    if args.dry_run:
        cmd += ["--dry-run"]

    print("[screen.py] 候选虚拟筛选入口")
    print(f"[screen.py] 候选文件   : {target.resolve()}")
    print(f"[screen.py] 模型根目录 : {Path(args.model_dir).resolve()}")
    print(f"[screen.py] 日志根目录 : {Path(args.logs_dir).resolve()}")
    print(f"[screen.py] 输出清单   : "
          f"{Path(args.results_dir).resolve() / args.batch_name / 'summary' / '赛道二_results.csv'}")
    print("[screen.py] 调用        :", " ".join(cmd))
    print("[screen.py] 说明        : 本入口做候选虚拟筛选/排序，不做序列从头生成。")
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
