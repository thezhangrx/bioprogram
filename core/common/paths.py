"""项目路径解析（唯一权威定义）。

设计原则
--------
* 所有默认路径由**项目根**推导，不写死绝对路径；
* 项目根由本文件位置推导（``core/paths.py`` → parents[1]），
  因此从任意工作目录运行、或被其它进程 import 都能正确定位；
* 各入口脚本（train / data_digging / predict / design / screen / analysis CLI）
  只引用本模块，不再各自拼路径。

目录约定
--------
    data/processed    已处理特征与标签（模型输入）
    data/raw          原始逐细胞系数据
    data/candidate    候选/待测序列表
    data/metadata     schema 与 feature 配置
    results/batches   每次实验批次的完整产物（<batch>/summary/...）
    results/logs      训练与运行日志
    results/tables    跨批次汇总表
    models/weights    训练产出的模型权重（按批次归档）
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

DATA_DIR: Path = PROJECT_ROOT / "data"
DATA_PROCESSED: Path = DATA_DIR / "processed"
DATA_RAW: Path = DATA_DIR / "raw"
DATA_CANDIDATE: Path = DATA_DIR / "candidate"
DATA_METADATA: Path = DATA_DIR / "metadata"

RESULTS_DIR: Path = PROJECT_ROOT / "results"
RESULTS_BATCHES: Path = RESULTS_DIR / "batches"
RESULTS_TABLES: Path = RESULTS_DIR / "tables"
LOGS_DIR: Path = RESULTS_DIR / "logs"

MODELS_DIR: Path = PROJECT_ROOT / "models"
MODELS_WEIGHTS: Path = MODELS_DIR / "weights"

#: 供 argparse default 使用的字符串形式
STR_DATA_PROCESSED = str(DATA_PROCESSED)
STR_RESULTS_BATCHES = str(RESULTS_BATCHES)
STR_MODELS_WEIGHTS = str(MODELS_WEIGHTS)
STR_LOGS = str(LOGS_DIR)
