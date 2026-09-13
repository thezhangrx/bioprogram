#!/usr/bin/env python3
"""design.py — 一键候选设计（候选优先级排序 / candidate prioritization）。

定位（如实说明）
----------------
本入口**不是**序列从头生成（de novo generation）。它的实际作用是：
在已测数据池上，用平台的多模型流程对候选 23 nt sgRNA 进行**打分、排序与优先级筛选**，
输出符合大赛模板的候选清单（候选编号 / 序列 / 预测效率 / 推荐模型 / 排序理由）。

与 predict.py 的关系
--------------------
本脚本是 ``predict.py`` 的薄封装（thin wrapper），只负责：
  1) 用项目约定的默认路径（data/proceeded_data、results/、models/、logs/）组装命令；
  2) 调用 ``predict.py --generate-candidates``；
不复制任何训练或统计逻辑。所有科学计算都在 ``predict.py`` 与其依赖的 ``src/`` 中完成。

输出
----
``<results-dir>/<batch-name>/summary/赛道二_results.csv``  （UTF-8，含候选编号等字段）
``<results-dir>/<batch-name>/summary/ultimate/``           （本次候选排序所使用的模型）

用法
----
    python design.py --dry-run                       # 只打印计划，不训练/不写文件
    python design.py --candidate-top-k 50            # 生成前 50 个候选
    python design.py --models xgboost cnn --epochs 15

注意：默认流程会在 mixed 已测池上拟合候选排序模型（属 predict.py 既有设计），
首次运行需要一定时间；若只需查看计划请加 ``--dry-run``。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = "data/proceeded_data"
DEFAULT_RESULTS_DIR = "results"
DEFAULT_MODEL_DIR = "models"
DEFAULT_LOGS_DIR = "logs"
DEFAULT_BATCH = "batch_20260909_full"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="候选 sgRNA 设计入口（多模型打分 + 优先级排序；复用 predict.py）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--batch-name", default=DEFAULT_BATCH, help="结果批次名（写入 results/<batch>/summary/）")
    p.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="特征数据目录")
    p.add_argument("--results-dir", default=DEFAULT_RESULTS_DIR, help="结果根目录")
    p.add_argument("--model-dir", default=DEFAULT_MODEL_DIR,
                   help="模型权重根目录（与 train.py --model-dir 一致）")
    p.add_argument("--logs-dir", default=DEFAULT_LOGS_DIR,
                   help="日志根目录（与 train.py --logs-dir 一致）")
    p.add_argument("--candidate-top-k", "--top-k", dest="candidate_top_k", type=int, default=20,
                   help="输出候选数量")
    p.add_argument("--models", nargs="+", default=None,
                   choices=["linear", "xgboost", "mlp", "transformer", "cnn"],
                   help="参与候选排序的模型族（默认全部）")
    p.add_argument("--cell-lines", nargs="+", default=None,
                   choices=["hct116", "hek293t", "hela", "hl60"], help="限定细胞系")
    p.add_argument("--epochs", type=int, default=15, help="候选排序模型的训练轮数")
    p.add_argument("--cv-folds", type=int, default=10, help="交叉验证折数")
    p.add_argument("--seed", type=int, default=42, help="随机种子")
    p.add_argument("--device", default=None, help="cpu / cuda（默认自动）")
    p.add_argument("--dry-run", action="store_true", help="只打印计划，不训练、不写文件")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cmd = [sys.executable, str(ROOT / "predict.py"),
           "--generate-candidates",
           "--batch-name", args.batch_name,
           "--data-dir", args.data_dir,
           "--results-dir", args.results_dir,
           "--candidate-top-k", str(args.candidate_top_k),
           "--ultimate-cv-folds", str(args.cv_folds),
           "--ultimate-epochs", str(args.epochs),
           "--ultimate-seed", str(args.seed)]
    if args.models:
        cmd += ["--models", *args.models]
    if args.cell_lines:
        cmd += ["--cell-lines", *args.cell_lines]
    if args.device:
        cmd += ["--device", args.device]
    if args.dry_run:
        cmd += ["--dry-run"]

    print("[design.py] 候选设计（优先级排序）入口")
    print(f"[design.py] 模型根目录 : {Path(args.model_dir).resolve()}")
    print(f"[design.py] 日志根目录 : {Path(args.logs_dir).resolve()}")
    print(f"[design.py] 输出清单   : "
          f"{Path(args.results_dir).resolve() / args.batch_name / 'summary' / '赛道二_results.csv'}")
    print("[design.py] 调用        :", " ".join(cmd))
    print("[design.py] 说明        : 本入口做候选优先级排序，不做序列从头生成。")
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
