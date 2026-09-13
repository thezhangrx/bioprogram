# analyse/data_QC.py
"""
CRISPR-Cas9 sgRNA 平台 · 第二步：数据质控与特征探测引擎 (Data Quality Controller)
=================================================================================
无头 (Headless) 数据分析模块，供 7 步交互式向导 (GUI/CLI) 第二步调用。

职责：对用户上传的原始数据 (支持单个/多个 .csv / .tsv 文件、多细胞系) 执行自动化
质控扫描，并把全部检测结果封装为标准 Python dict (并写入 qc_summary.json)，
供向导第三步（映射与配置确认）动态读取。模块内不包含任何 input() 阻塞交互。

输出 (output_dir，默认 data/data_report/)：
  1. quality_report.md           —— 第 1,3,4,5,6,7,8 项质控的 Markdown 报告
  2. qc_summary.json             —— 结构化元数据 (向导交互读取)
  3. target_efficiency_kde.png   —— 编辑效率 y 的 300DPI KDE 图
  4. gc_content_kde.png          —— GC 含量 300DPI KDE 图

八大质控模块：
  1 细胞系样本容量         2 编辑效率 KDE (高斯核 + GridSearchCV 带宽选择)
  3 非标准碱基探测         4 单核苷酸单态位点 (Monormorphic Positions)
  5 GC 含量分析            6 序列长度一致性
  7 表观完整度与 70% 门禁   8 Isolation Forest 高维多模态离群检测

工程规范：Python 3.10+ 类型注解 / pathlib / csv 与 tsv / utf-8 与 gb18030 编码自适应
          / matplotlib + seaborn 300DPI / sns.despine 学术风。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import seaborn as sns  # noqa: E402
from scipy import stats  # noqa: E402
from sklearn.ensemble import IsolationForest  # noqa: E402
from sklearn.model_selection import GridSearchCV, KFold  # noqa: E402
from sklearn.neighbors import KernelDensity  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

PathLike = Union[str, Path]

# ---------------------------------------------------------------------------
# 默认常量
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_DIR: str = "data/data_report"
STANDARD_BASES: Tuple[str, ...] = ("A", "C", "G", "T")
DEFAULT_POSITION_LENGTH: int = 23
DEFAULT_CV_FOLDS: int = 5
DEFAULT_CV_SUBSAMPLE: int = 2000
DEFAULT_CONTAMINATION: float = 0.01
DEFAULT_RANDOM_STATE: int = 42

SEQ_COL_ALIASES: Tuple[str, ...] = (
    "sgRNA", "sgRNA sequence", "Sequence", "sequence", "seq", "Guide", "guide",
    "GuideSeq", "guide_seq", "protospacer", "23nt", "target_site", "spacer",
)
CELL_LINE_COL_ALIASES: Tuple[str, ...] = (
    "Cell line", "Cell Line", "cell_line", "cellline", "cell", "Cell", "Cell_line",
    "CellLine", "cell_line_name",
)
TARGET_COL_ALIASES: Tuple[str, ...] = (
    "Normalized efficacy", "Efficiency", "efficiency", "Editing efficiency",
    "editing_efficiency", "normalized_efficacy", "Normalized Efficiency",
    "label", "Label", "target", "Target", "Activity", "activity", "y", "Y",
)

# 表观通道名 (小写关键字 -> 规范显示名)
EPI_NAME_MAP: Dict[str, str] = {
    "ctcf": "CTCF",
    "dnase": "Dnase",
    "dhs": "Dnase",
    "h3k4me3": "H3K4me3",
    "h3k4": "H3K4me3",
    "h3k27ac": "H3K27ac",
    "rrbs": "RRBS",
    "methylation": "RRBS",
    "bisulfite": "RRBS",
    "atac": "ATAC",
}
_EPI_IGNORE_WORDS = ("sequence", "feature", "coverage", "score_norm")


# ===========================================================================
# 基础 IO 工具
# ===========================================================================

def _as_path(path: PathLike) -> Path:
    return Path(path).expanduser()


def _read_table(path: Path) -> Tuple[pd.DataFrame, str]:
    """读取 csv / tsv，编码在 utf-8 / gb18030(含 gbk) / latin-1 之间自适应。"""
    sep = "\t" if path.suffix.lower() in (".tsv", ".txt") else ","
    for encoding in ("utf-8", "gb18030", "latin-1"):
        try:
            df = pd.read_csv(path, sep=sep, encoding=encoding, low_memory=False)
            return df, encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as exc:  # noqa: BLE001 - 结构错误不再换编码重试
            raise ValueError(f"无法解析文件 {path.name}: {exc}") from exc
    raise ValueError(f"无法用 utf-8 / gbk / latin-1 解码文件: {path.name}")


def _find_column(columns: Sequence[str], aliases: Sequence[str]) -> Optional[str]:
    """按别名精确/忽略大小写查找列名。"""
    lower2orig = {str(c).strip().lower(): c for c in columns}
    for alias in aliases:
        key = str(alias).strip().lower()
        if key in lower2orig:
            return lower2orig[key]
    return None


def _find_column_fuzzy(columns: Sequence[str], aliases: Sequence[str]) -> Optional[str]:
    exact = _find_column(columns, aliases)
    if exact is not None:
        return exact
    lower = [str(c).strip().lower() for c in columns]
    for alias in aliases:
        a = str(alias).strip().lower()
        for i, name in enumerate(lower):
            if a in name or name in a:
                return columns[i]
    return None


def _detect_epigenetic_columns(columns: Sequence[str]) -> Dict[str, str]:
    """自动识别表观通道列 (小写关键字匹配)，返回 {规范通道名: 实际列名}。"""
    result: Dict[str, str] = {}
    for col in columns:
        name = str(col).strip().lower()
        if not name or any(w in name for w in _EPI_IGNORE_WORDS):
            continue
        for key, display in EPI_NAME_MAP.items():
            # 精确 token (ctcf / dnase / rrbs ...) 或以通道关键字开头
            if name == key or name.startswith(key + "_") or name.endswith("_" + key):
                if display not in result:
                    result[display] = col
                break
    return result


# ===========================================================================
# 统计 / 绘图工具
# ===========================================================================

def _cv_bandwidth(values: Sequence[float], cv: int = DEFAULT_CV_FOLDS,
                  n_subsample: int = DEFAULT_CV_SUBSAMPLE,
                  random_state: int = DEFAULT_RANDOM_STATE,
                  n_grid: int = 24) -> float:
    """
    高斯核密度估计带宽选择 (严禁经验写死)：
      GridSearchCV + 5 折交叉验证 (KernelDensity 负对数似然),
      在对数空间搜索 h ∈ [std(y)·0.05, std(y)·1.5]。
    样本量 > n_subsample 时子抽样拟合 (防止大规模数据卡死)。
    """
    v = np.asarray([float(x) for x in values if pd.notna(x)], dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 1.0
    if v.size < 3:
        return float(np.nanstd(v) if np.nanstd(v) > 0 else 1e-3)

    std = float(v.std(ddof=0))
    if std <= 1e-12:  # 常数向量 -> 极小平滑带宽
        std = max(1e-6, float(np.abs(v).mean()) * 0.5)

    lo = max(std * 0.05, 1e-6)
    hi = max(std * 1.5, lo * 2.0)
    grid = np.geomspace(lo, hi, int(n_grid))

    work = v
    if v.size > int(n_subsample):
        rng = np.random.default_rng(random_state)
        work = rng.choice(v, size=int(n_subsample), replace=False)

    n_folds = min(int(cv), max(2, min(100, int(work.size) // 2)))
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=random_state)
    search = GridSearchCV(
        KernelDensity(kernel="gaussian"),
        param_grid={"bandwidth": grid},
        cv=kf,
        n_jobs=-1,
    )
    search.fit(work.reshape(-1, 1))
    return float(search.best_params_["bandwidth"])


def _kde_values(values: Sequence[float], bandwidth: float, n_points: int = 400,
                pad: float = 0.15) -> Tuple[np.ndarray, np.ndarray]:
    v = np.asarray([float(x) for x in values if pd.notna(x)], dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size < 3:
        return np.array([]), np.array([])
    lo, hi = float(v.min()), float(v.max())
    span = max(hi - lo, 1e-9)
    xs = np.linspace(lo - pad * span, hi + pad * span, int(n_points))
    kde = KernelDensity(kernel="gaussian", bandwidth=max(bandwidth, 1e-9)).fit(v.reshape(-1, 1))
    ys = np.exp(kde.score_samples(xs.reshape(-1, 1)))
    return xs, ys


def _parse_epi_vector(value: Any, length: int) -> Optional[np.ndarray]:
    """
    表观通道值 -> 长度为 length 的逐位点向量 (供离群检测展平)。
      - 23 字符 A/N 串: A/Y/T/1 -> 1, 其余(N/0/...) -> 0
      - 数值标量: 广播为 length 个常数
      - "[0,1,..]" 或数值列表: 解析为向量
    NaN / 空串 / 长度无法对齐 -> None (上层做中位数填充)
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, str):
        s = value.strip().upper()
        if not s:
            return None
        if s.startswith("[") and s.endswith("]"):
            try:
                arr = np.asarray(json.loads(s), dtype=np.float64).reshape(-1)
                if arr.size == length:
                    return arr
            except Exception:
                pass
            return None
        if len(s) == length:
            return np.asarray([1.0 if ch in ("A", "Y", "T", "1") else 0.0 for ch in s])
        if len(s) == 1 and s in ("A", "N", "0", "1", "Y", "T"):
            return np.full(length, 1.0 if s in ("A", "Y", "T", "1") else 0.0)
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        arr = np.asarray(value, dtype=np.float64).reshape(-1)
        if arr.size == length:
            return arr
        if arr.size == 1:
            return np.full(length, arr[0])
        return None
    try:
        scalar = float(value)
    except (TypeError, ValueError):
        return None
    return np.full(length, scalar)


# ---------------------------------------------------------------------------
# 特征类型判别 (位置型 vs 全局标量/离散) 相关工具
# ---------------------------------------------------------------------------
# 位点轨道允许字符 (保守集: A/N 串或 1/0/. 等位点标记, 不含普通文本 token)
TRACK_CHARS: frozenset = frozenset("ACGTNY10.+-")
_POSITIONAL_CORE_NAMES: frozenset = frozenset({"CTCF", "Dnase", "H3K4me3", "RRBS"})


def _is_blank_value(value: Any) -> bool:
    """判空: None / NaN / 空白字符串。"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _sample_feature_info(value: Any, length: int) -> Dict[str, Any]:
    """
    单样本单特征列的取值解析 (不做特征列类型假设, 只按值本身格式分类):
      - blank        : 缺失/空串 -> 无测量
      - pos          : 位点型值 (L 位 A/N 串 / 数值数组 / 轨道字符串), units = 实际位点数
      - scalar       : 全局标量数值 (单浮点)
      - token        : 全局离散/类别型 (文本标签)
    返回 {kind, units?, has_nan?, preview}。
    """
    if _is_blank_value(value):
        return {"kind": "blank", "units": None, "has_nan": False,
                "preview": ""}

    if isinstance(value, str):
        raw = value.strip()
        s = raw.upper()
        if not s:
            return {"kind": "blank", "units": None, "has_nan": False, "preview": ""}
        # 数值数组形式: "[0.1, 0.2, ...]" (NaN 大小写鲁棒, 不得整体大写破坏 JSON)
        if raw.startswith("[") and raw.endswith("]"):
            norm = raw.replace("NAN", "NaN").replace("nan", "NaN")
            try:
                arr = np.asarray(json.loads(norm), dtype=np.float64).reshape(-1)
                return {"kind": "pos", "units": int(arr.size),
                        "has_nan": bool(np.isnan(arr).any()), "preview": raw[:40]}
            except Exception:
                return {"kind": "token", "units": None, "has_nan": False, "preview": raw[:40]}
        # 位点轨道串 (A/N ...): 长度 == L 视为对齐, 否则记实际位点数用于对齐检测
        if set(s) <= TRACK_CHARS and len(s) > 1:
            return {"kind": "pos", "units": int(len(s)), "has_nan": False, "preview": s[:40]}
        # 其余短文本: 单字符轨道标记(A/N)视为全局标记, 否则为类别 token
        return {"kind": "token", "units": None, "has_nan": False, "preview": s[:40]}

    if isinstance(value, (list, tuple, np.ndarray)):
        try:
            arr = np.asarray(value, dtype=np.float64).reshape(-1)
            return {"kind": "pos", "units": int(arr.size),
                    "has_nan": bool(np.isnan(arr).any()), "preview": f"array[{int(arr.size)}]"}
        except (TypeError, ValueError):
            return {"kind": "token", "units": None, "has_nan": False,
                    "preview": str(value)[:40]}

    # 数值标量 / 布尔
    try:
        float(value)
        return {"kind": "scalar", "units": None, "has_nan": False, "preview": str(value)[:40]}
    except (TypeError, ValueError):
        return {"kind": "token", "units": None, "has_nan": False, "preview": str(value)[:40]}


def _style_figure() -> None:
    sns.set_theme(style="whitegrid", font_scale=1.05)
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False


def _save_figure(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ===========================================================================
# 主控制器
# ===========================================================================

def _sequence_gc_percent(seq: str) -> Optional[float]:
    """单条序列 GC 含量 (%)；无有效碱基返回 None。"""
    s = str(seq).upper().strip()
    if not s:
        return None
    return (s.count("G") + s.count("C")) / len(s) * 100.0


def _outlier_reason_hints(y_value, gc_value, y_all: np.ndarray, gc_all: np.ndarray) -> List[str]:
    """
    为离群样本给出简要归因提示 (供回溯/过滤):
      extreme_target_y : y 偏离全体 3*std 或超合理边界
      abnormal_gc      : GC 偏离全体 3*std
      两者皆不满足      : multivariate_anomaly
    """
    hints: List[str] = []
    y_finite = y_all[np.isfinite(y_all)]
    gc_finite = gc_all[np.isfinite(gc_all)]
    if y_value is not None and np.isfinite(y_value) and y_finite.size >= 3:
        mean_y, std_y = float(np.mean(y_finite)), float(np.std(y_finite))
        if abs(float(y_value) - mean_y) > 3.0 * max(std_y, 1e-9) or float(y_value) < 0.0 or float(y_value) > 1.0:
            hints.append("extreme_target_y")
    if gc_value is not None and np.isfinite(gc_value) and gc_finite.size >= 3:
        mean_gc, std_gc = float(np.mean(gc_finite)), float(np.std(gc_finite))
        if abs(float(gc_value) - mean_gc) > 3.0 * max(std_gc, 1e-9):
            hints.append("abnormal_gc")
    if not hints:
        hints.append("multivariate_anomaly")
    return hints


class DataQualityController:
    """
    第二步数据质控主控制器 (Headless)。
    """

    def __init__(
        self,
        data_path: Union[PathLike, Sequence[PathLike]],
        output_dir: Optional[PathLike] = None,
        sequence_column: Optional[str] = None,
        target_column: Optional[str] = None,
        cell_line_column: Optional[str] = None,
        epigenetic_columns: Optional[Dict[str, str]] = None,
        context_columns: Optional[Dict[str, str]] = None,
        force_positional: Optional[Sequence[str]] = None,
        force_global: Optional[Sequence[str]] = None,
        position_length: int = DEFAULT_POSITION_LENGTH,
        cv_folds: int = DEFAULT_CV_FOLDS,
        cv_subsample: int = DEFAULT_CV_SUBSAMPLE,
        contamination: float = DEFAULT_CONTAMINATION,
        random_state: int = DEFAULT_RANDOM_STATE,
        verbose: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir) if output_dir else Path(DEFAULT_OUTPUT_DIR)
        self.position_length = int(position_length)
        self.cv_folds = int(cv_folds)
        self.cv_subsample = int(cv_subsample)
        self.contamination = float(contamination)
        self.random_state = int(random_state)
        self.verbose = verbose

        self._files = _resolve_input_files(data_path)
        if not self._files:
            raise FileNotFoundError(f"未在 {data_path} 找到任何 .csv / .tsv 数据文件")

        # 读入全部文件并自动判定列映射
        self.frames: List[Tuple[Path, pd.DataFrame]] = []
        for fp in self._files:
            df, _enc = _read_table(fp)
            if df.empty:
                raise ValueError(f"文件为空: {fp.name}")
            self.frames.append((fp, df))

        probe_cols = list(self.frames[0][1].columns)
        self.sequence_column = sequence_column or _find_column_fuzzy(probe_cols, SEQ_COL_ALIASES)
        self.target_column = target_column or _find_column(probe_cols, TARGET_COL_ALIASES)
        self.cell_line_column = cell_line_column or _find_column(probe_cols, CELL_LINE_COL_ALIASES)
        if epigenetic_columns:
            self.epigenetic_columns = {str(k): str(v) for k, v in epigenetic_columns.items()}
        else:
            self.epigenetic_columns = _detect_epigenetic_columns(
                [c for c in probe_cols if c not in (self.sequence_column, self.target_column, self.cell_line_column)]
            )

        # 额外上下文特征列 (可为位置型或全局标量/离散), 类型自动按格式判别
        if context_columns:
            self.context_columns = {str(k): str(v) for k, v in context_columns.items()}
        else:
            self.context_columns = {}
        self.force_positional: set = set(force_positional or [])
        self.force_global: set = set(force_global or [])

        # 特征列总表: 核心表观(位置型候选) + 用户上下文列
        self.feature_spec: Dict[str, str] = dict(self.epigenetic_columns)
        for disp_name, col in self.context_columns.items():
            if disp_name not in self.feature_spec:
                self.feature_spec[disp_name] = col

        self.channel_types: Dict[str, str] = {}          # 规范名 -> positional|global_numeric|global_categorical
        self.long: Optional[pd.DataFrame] = None         # 长表: 含 _file / _row(1-based) / _cl
        self.result: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 长表装配
    # ------------------------------------------------------------------
    def _build_long_frame(self) -> pd.DataFrame:
        records: List[Dict[str, Any]] = []
        for file_order, (fp, df) in enumerate(self.frames):
            # 单元格系: 优先读取细胞系列, 否则由文件名推断
            if self.cell_line_column and self.cell_line_column in df.columns:
                cl_raw = df[self.cell_line_column].fillna("").astype(str).str.strip()
                file_cl: Optional[str] = None
            else:
                cl_raw = None
                stem = re.split(r"[_\-.]", Path(fp).stem)[0] or Path(fp).stem
                file_cl = stem.lower()

            has_seq = bool(self.sequence_column and self.sequence_column in df.columns)
            for i, (_, row) in enumerate(df.iterrows()):
                if cl_raw is not None:
                    cl = str(row.get(self.cell_line_column, "")).strip() if pd.notna(row.get(self.cell_line_column)) else ""
                    if not cl:
                        cl = file_cl or "unknown"
                else:
                    cl = file_cl or "unknown"

                seq = ""
                if has_seq:
                    v = row.get(self.sequence_column)
                    seq = str(v).strip().upper() if pd.notna(v) else ""

                y = np.nan
                if self.target_column and self.target_column in df.columns:
                    tv = row.get(self.target_column)
                    try:
                        y = float(tv) if pd.notna(tv) else np.nan
                    except (TypeError, ValueError):
                        y = np.nan

                rec: Dict[str, Any] = {
                    "_file": Path(fp).name,
                    "_row": int(i) + 2,          # 1-based (含表头)
                    "_cl": str(cl).lower(),
                    "sequence": seq,
                    "y": y,
                }
                for disp, col in self.feature_spec.items():
                    rec[disp] = row.get(col) if col in df.columns else None
                records.append(rec)

        long = pd.DataFrame.from_records(records)
        self.long = long
        return long

    # ------------------------------------------------------------------
    # 1. 细胞系样本容量
    # ------------------------------------------------------------------
    def profile_sample_sizes(self) -> Dict[str, Any]:
        long = self.long if self.long is not None else self._build_long_frame()
        valid_mask = long["sequence"].str.len() > 0
        if self.target_column is not None:
            valid_mask = valid_mask & long["y"].notna()

        valid = long[valid_mask]
        counts: Dict[str, int] = {}
        for cl, sub in valid.groupby("_cl"):
            counts[str(cl)] = int(len(sub))
        total = int(len(valid))

        out = {
            "per_cell_line": dict(sorted(counts.items())),
            "total_samples": total,
            "n_files": len(self.frames),
            "n_raw_rows": int(len(long)),
        }
        self.result["sample_size"] = out
        return out

    # ------------------------------------------------------------------
    # 2. 编辑效率 y 的高斯核 KDE (CV 带宽)
    # ------------------------------------------------------------------
    def kde_target_efficiency(self) -> Dict[str, Any]:
        long = self.long if self.long is not None else self._build_long_frame()
        ys = long["y"].astype(float).to_numpy()
        ys = ys[np.isfinite(ys)]

        info: Dict[str, Any] = {"n_valid": int(ys.size)}
        if ys.size >= 3:
            h_pooled = _cv_bandwidth(ys, self.cv_folds, self.cv_subsample, self.random_state)
            info["bandwidth_pooled"] = h_pooled
            info["bandwidth_search_range"] = [
                float(np.std(ys) * 0.05), float(np.std(ys) * 1.5),
            ]
            info["skewness"] = float(stats.skew(ys))
            info["kurtosis"] = float(stats.kurtosis(ys))
            info["mean"] = float(np.mean(ys))
            info["std"] = float(np.std(ys))
            info["subsampled_cv"] = bool(ys.size > self.cv_subsample)

            _style_figure()
            fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
            ax.hist(ys, bins=min(80, max(20, int(np.sqrt(ys.size)))), density=True,
                    alpha=0.32, color="#7f8c8d", edgecolor="white", label="Histogram (density)")

            cell_lines = sorted(long["_cl"].unique())
            palette = sns.color_palette("deep", n_colors=len(cell_lines) + 1)
            for idx, cl in enumerate(cell_lines):
                cl_y = long.loc[long["_cl"] == cl, "y"].astype(float).to_numpy()
                cl_y = cl_y[np.isfinite(cl_y)]
                if cl_y.size < 3:
                    continue
                h = _cv_bandwidth(cl_y, self.cv_folds, self.cv_subsample, self.random_state)
                xs, kd = _kde_values(cl_y, h)
                if xs.size:
                    ax.plot(xs, kd, color=palette[idx], lw=2.0,
                            label=f"{cl} (h={h:.4f})")

            xs, kd_all = _kde_values(ys, h_pooled)
            if xs.size:
                ax.plot(xs, kd_all, color="#c0392b", lw=2.6, ls="--",
                        label=f"All (h={h_pooled:.4f})")
                ax.fill_between(xs, kd_all, alpha=0.08, color="#c0392b")

            ax.set_xlabel("Editing Efficiency y")
            ax.set_ylabel("Density")
            ax.set_title("KDE of Editing Efficiency y (Gaussian kernel, CV bandwidth)")
            props = (
                f"n={int(ys.size)}   mean={np.mean(ys):.3f}   sd={np.std(ys):.3f}\n"
                f"Skewness={info['skewness']:.2f}   Kurtosis={info['kurtosis']:.2f}"
            )
            ax.text(0.985, 0.97, props, transform=ax.transAxes, ha="right", va="top",
                    fontsize=9, bbox=dict(boxstyle="round", fc="#fffbe6", ec="#b8b8b8"))
            ax.legend(frameon=True, fontsize=8.5, loc="upper right")
            sns.despine(ax=ax)
            _save_figure(fig, self.output_dir / "target_efficiency_kde.png")
        self.result["target_efficiency"] = info
        return info

    # ------------------------------------------------------------------
    # 3. 非标准碱基探测
    # ------------------------------------------------------------------
    def detect_ambiguous_bases(self) -> Dict[str, Any]:
        long = self.long if self.long is not None else self._build_long_frame()
        seqs = long["sequence"].fillna("").astype(str).str.strip().str.upper()
        char_counter: Dict[str, int] = {}
        affected_rows: List[Dict[str, Any]] = []

        for i, s in seqs.items():
            if not s:
                continue
            bad = sorted(set(s) - set(STANDARD_BASES))
            if bad:
                affected_rows.append({
                    "file": long.loc[i, "_file"],
                    "row": int(long.loc[i, "_row"]),
                    "cell_line": long.loc[i, "_cl"],
                })
                for ch in bad:
                    char_counter[ch] = char_counter.get(ch, 0) + s.count(ch)

        n_valid_seq = int((seqs.str.len() > 0).sum())
        info = {
            "detected_ambiguous_bases": sorted(char_counter.keys()),   # 供向导第三步映射弹窗
            "per_base_frequency": dict(sorted(char_counter.items())),
            "total_ambiguous_characters": int(sum(char_counter.values())),
            "n_affected_sequences": len(affected_rows),
            "affected_ratio": round(len(affected_rows) / n_valid_seq, 6) if n_valid_seq else 0.0,
            "affected_rows": affected_rows,   # 供前端查看/弹出
            "iupac_hint": sorted(set("NRYSWKMBDHV") & set(char_counter.keys())),
        }
        self.result["ambiguous_bases"] = info
        return info

    # ------------------------------------------------------------------
    # 4. 单核苷酸单态位点 (Monormorphic / 零方差位点)
    # ------------------------------------------------------------------
    def detect_monomorphic_positions(self) -> Dict[str, Any]:
        long = self.long if self.long is not None else self._build_long_frame()
        L = self.position_length
        seqs = long["sequence"].fillna("").astype(str).str.strip().str.upper()
        # 只统计长度 == 推荐长度 L 的序列 (长度异常序列单独在第 6 项处理)
        aligned = long[seqs.str.len() == L].copy()
        aligned["sequence"] = seqs[aligned.index]

        def scan(group: pd.DataFrame) -> List[Dict[str, str]]:
            out: List[Dict[str, str]] = []
            n = len(group)
            if n < 3:
                return out
            for p in range(L):
                col = group["sequence"].str[p]
                uniq = col.dropna().unique()
                if uniq.size == 1:
                    out.append({"position": int(p + 1), "base": str(uniq[0])})
            return out

        whole = scan(aligned)
        per_cell: Dict[str, List[Dict[str, str]]] = {}
        for cl, group in aligned.groupby("_cl"):
            per_cell[str(cl)] = scan(group)

        info = {
            "aligned_n": int(len(aligned)),
            "whole_dataset": whole,
            "per_cell_line": per_cell,
            "biological_risk_note": (
                "单态位点在训练样本中 100% 恒定, 无法为该位置提供信息增益; "
                "若作为线性模型输入特征会产生零方差列并可能导致奇异矩阵 (矩阵不满秩), "
                "建议特征工程阶段对该位点进行正则化/伪计数或直接剔除。"
            ),
        }
        self.result["monomorphic_positions"] = info
        return info

    # ------------------------------------------------------------------
    # 5. GC 含量
    # ------------------------------------------------------------------
    def profile_gc_content(self) -> Dict[str, Any]:
        long = self.long if self.long is not None else self._build_long_frame()
        seqs = long["sequence"].fillna("").astype(str).str.strip().str.upper()

        gc: List[float] = []
        for s in seqs:
            if not s:
                gc.append(np.nan)
                continue
            gc.append((s.count("G") + s.count("C")) / len(s) * 100.0)
        long["_gc"] = gc
        arr = np.asarray(gc, dtype=np.float64)
        valid = arr[np.isfinite(arr)]

        info: Dict[str, Any] = {"n_valid": int(valid.size)}
        if valid.size >= 3:
            h = _cv_bandwidth(valid, self.cv_folds, self.cv_subsample, self.random_state)
            info["bandwidth_pooled"] = h
            info["bandwidth_search_range"] = [float(valid.std() * 0.05), float(valid.std() * 1.5)]
            info["mean"] = float(np.mean(valid))
            info["std"] = float(np.std(valid))
            info["min"] = float(np.min(valid))
            info["max"] = float(np.max(valid))
            info["skewness"] = float(stats.skew(valid))
            info["recommend_gc_as_feature"] = True   # 供向导询问是否将 GC 作为独立连续信道

            _style_figure()
            fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
            ax.hist(valid, bins=min(70, max(20, int(np.sqrt(valid.size)))), density=True,
                    alpha=0.32, color="#7f8c8d", edgecolor="white", label="Histogram (density)")
            cell_lines = sorted(long["_cl"].unique())
            palette = sns.color_palette("deep", n_colors=len(cell_lines) + 1)
            for idx, cl in enumerate(cell_lines):
                clv = valid[long["_cl"].to_numpy() == cl]
                if clv.size < 3:
                    continue
                hcl = _cv_bandwidth(clv, self.cv_folds, self.cv_subsample, self.random_state)
                xs, kd = _kde_values(clv, hcl)
                if xs.size:
                    ax.plot(xs, kd, color=palette[idx], lw=2.0, label=f"{cl} (h={hcl:.3f})")
            xs, kd_all = _kde_values(valid, h)
            if xs.size:
                ax.plot(xs, kd_all, color="#2980b9", lw=2.6, ls="--",
                        label=f"All (h={h:.3f})")
                ax.fill_between(xs, kd_all, alpha=0.08, color="#2980b9")
            ax.set_xlabel("GC Content (%)")
            ax.set_ylabel("Density")
            ax.set_title("KDE of per-Sequence GC Content (Gaussian kernel, CV bandwidth)")
            ax.legend(frameon=True, fontsize=8.5)
            sns.despine(ax=ax)
            _save_figure(fig, self.output_dir / "gc_content_kde.png")
        else:
            info["recommend_gc_as_feature"] = False
        self.result["gc_content"] = info
        return info

    # ------------------------------------------------------------------
    # 6. 序列长度一致性
    # ------------------------------------------------------------------
    def length_consistency(self) -> Dict[str, Any]:
        long = self.long if self.long is not None else self._build_long_frame()
        seqs = long["sequence"].fillna("").astype(str).str.strip()
        lengths = seqs[seqs.str.len() > 0].str.len()

        mode_ser = lengths.mode(dropna=True)
        mode = int(mode_ser.iloc[0]) if not mode_ser.empty else 0

        anomalies: List[Dict[str, Any]] = []
        for i, s in seqs.items():
            if len(s) > 0 and len(s) != mode:
                anomalies.append({
                    "file": long.loc[i, "_file"],
                    "row": int(long.loc[i, "_row"]),
                    "cell_line": long.loc[i, "_cl"],
                    "length": int(len(s)),
                    "sequence": s,
                })

        info = {
            "recommended_length_L": mode,
            "length_distribution": {int(k): int(v) for k, v in lengths.value_counts().items()},
            "n_length_anomalies": len(anomalies),
            "anomaly_ratio": round(len(anomalies) / max(1, int(lengths.size)), 6),
            "anomalies": anomalies,
        }
        self.result["length_consistency"] = info
        return info

    # ------------------------------------------------------------------
    # 6b. 特征列类型判别 (位置型 vs 全局标量/离散)
    # ------------------------------------------------------------------
    def _classify_channels(self) -> Dict[str, str]:
        """
        对 feature_spec 中每列按【数据格式】自动判别：
          positional        : 空间位置型特征 (L 位 A/N 串 / 逐位点数值数组), 需按 L 对齐
          global_numeric    : 全局标量浮点 (如基因表达量) —— 严禁 L 长度匹配, 仅空值率/统计
          global_categorical: 全局离散标签 (外显子/内含子、染色体号、启动子类型) —— 同严禁 L 匹配
        """
        long = self.long if self.long is not None else self._build_long_frame()
        types: Dict[str, str] = {}

        def _default_for(name: str) -> str:
            return "positional" if name in _POSITIONAL_CORE_NAMES else "global_categorical"

        for name, col in self.feature_spec.items():
            if name in self.force_positional:
                types[name] = "positional"
                continue
            if name in self.force_global:
                values = long[name].dropna().tolist() if name in long.columns else []
                types[name] = (
                    "global_numeric" if any(
                        _sample_feature_info(v, self.position_length)["kind"] == "scalar"
                        for v in values
                    ) else "global_categorical"
                )
                continue

            if col not in long.columns or name not in long.columns:
                types[name] = _default_for(name)
                continue

            vals = [v for v in long[name].tolist() if not _is_blank_value(v)]
            if not vals:
                types[name] = _default_for(name)
                continue

            n_pos = n_scalar = n_cat = 0
            for v in vals:
                kind = _sample_feature_info(v, self.position_length)["kind"]
                if kind == "pos":
                    n_pos += 1
                elif kind == "scalar":
                    n_scalar += 1
                else:
                    n_cat += 1

            tot = n_pos + n_scalar + n_cat
            if n_pos >= 0.6 * tot and n_pos >= max(n_scalar, n_cat):
                types[name] = "positional"
            elif n_scalar >= n_cat and n_scalar >= 0.5 * tot:
                types[name] = "global_numeric"
            else:
                types[name] = "global_categorical"

        self.channel_types = types
        return types

    # ------------------------------------------------------------------
    # 补充 QC-A: 序列 × 表观长度对齐检测 (Length Alignment QC)
    # ------------------------------------------------------------------
    def length_alignment_qc(self) -> Dict[str, Any]:
        """
        空间位置型特征逐样本校验位点数 == 序列长度 L (模式长度):
          不对齐 (如序列 23nt 但某通道仅 20 值) -> 记"序列与表观长度不对齐"样本行号;
        全局标量/离散特征严禁做 L 长度匹配, 仅统计空值率与类别/统计分布。
        """
        long = self.long if self.long is not None else self._build_long_frame()
        L = int(self.result.get("length_consistency", {}).get("recommended_length_L")
                or self.position_length)
        n_samples = int(len(long))

        if not self.channel_types:
            self._classify_channels()

        positional_names = [n for n, t in self.channel_types.items() if t == "positional"]
        numeric_names = [n for n, t in self.channel_types.items() if t == "global_numeric"]
        cat_names = [n for n, t in self.channel_types.items() if t == "global_categorical"]

        def _row_ref(i: int) -> Dict[str, Any]:
            return {
                "file": str(long.loc[i, "_file"]),
                "row": int(long.loc[i, "_row"]),
                "cell_line": str(long.loc[i, "_cl"]),
            }

        # --- 位置型通道: 逐样本长度对齐 ---
        per_channel: Dict[str, Any] = {}
        for name in positional_names:
            aligned = 0
            mis_rows: List[Dict[str, Any]] = []
            blank_rows: List[Dict[str, Any]] = []
            partial_rows: List[Dict[str, Any]] = []
            n_unparsed = 0
            for i in range(n_samples):
                info = _sample_feature_info(long.loc[i, name], L)
                kind = info["kind"]
                if kind == "blank":
                    blank_rows.append(_row_ref(i))
                    continue
                if kind == "pos":
                    if info["units"] == L:
                        aligned += 1
                        if info["has_nan"]:
                            partial_rows.append(_row_ref(i))
                    else:
                        mis_rows.append({
                            **_row_ref(i),
                            "actual_units": int(info["units"]),
                            "expected_units": L,
                            "preview": info["preview"],
                        })
                else:   # 位置型列中混入标量/文本 -> 视为无法对齐
                    n_unparsed += 1
                    mis_rows.append({
                        **_row_ref(i),
                        "actual_units": None,
                        "expected_units": L,
                        "preview": info["preview"],
                    })
            per_channel[name] = {
                "type": "positional",
                "n_samples": n_samples,
                "n_aligned": int(aligned),
                "n_misaligned": len(mis_rows),
                "misaligned_ratio": round(len(mis_rows) / max(1, n_samples), 6),
                "n_blank": len(blank_rows),
                "n_partial_nan": len(partial_rows),
                "misaligned_rows": mis_rows[:200],
                "blank_rows": blank_rows[:200],
                "misaligned_rows_truncated": len(mis_rows) > 200,
            }

        # --- 全局标量 / 离散特征: 不做 L 匹配, 仅缺失率 + 分布 ---
        global_stats: Dict[str, Any] = {}

        def _num_stats(vals: List[Any]) -> Dict[str, float]:
            arr = np.asarray([float(v) for v in vals], dtype=np.float64)
            return {
                "mean": float(np.nanmean(arr)),
                "std": float(np.nanstd(arr)),
                "min": float(np.nanmin(arr)),
                "max": float(np.nanmax(arr)),
            }

        for name in numeric_names + cat_names:
            ftype = self.channel_types[name]
            vals = [v for v in long[name].tolist() if not _is_blank_value(v)]
            missing_rate = 1.0 - len(vals) / max(1, n_samples)
            if ftype == "global_numeric":
                stats_row = _num_stats(vals) if vals else {}
                global_stats[name] = {
                    "type": ftype,
                    "missing_rate": round(missing_rate, 6),
                    "n_non_null": len(vals),
                    "n_unique": int(pd.Series(vals).nunique(dropna=True)),
                    **stats_row,
                    "note": "全局标量特征: 未执行序列长度 L 对齐校验",
                }
            else:
                counter: Dict[str, int] = {}
                for v in vals:
                    key = str(v)
                    counter[key] = counter.get(key, 0) + 1
                top = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
                global_stats[name] = {
                    "type": ftype,
                    "missing_rate": round(missing_rate, 6),
                    "n_non_null": len(vals),
                    "n_unique": len(counter),
                    "category_frequency": [{"value": k, "count": c} for k, c in top],
                    "note": "全局离散/类别特征: 未执行序列长度 L 对齐校验",
                }

        info = {
            "recommended_length_L": L,
            "positional_channels": positional_names,
            "global_numeric_channels": numeric_names,
            "global_categorical_channels": cat_names,
            "per_channel_alignment": per_channel,
            "global_feature_stats": global_stats,
            "note_types": (
                "位置型特征按 L 严格对齐; 全局标量/离散特征严禁执行长度 L 匹配校验, "
                "仅统计其空值率与分布。"
            ),
        }
        self.result["length_alignment"] = info
        return info

    # ------------------------------------------------------------------
    # 补充 QC-B: 表观零标注诊断 (Zero-Annotation Diagnostics)
    # ------------------------------------------------------------------
    def zero_annotation_diagnostics(self) -> Dict[str, Any]:
        """
        区分"局部点位缺失"与"全轨完全未测":
          - 单通道无标注 : 某样本某位置型通道 L 位点全为 NaN/空值
          - 全局无标注   : 4 个核心表观通道全部位点均为 NaN/空 (纯空白样本, 无表观信号)
        输出具体行号索引, 供 Markdown 预警。
        """
        long = self.long if self.long is not None else self._build_long_frame()
        n_samples = int(len(long))

        if not self.channel_types:
            self._classify_channels()

        # 位置型核心表观通道 (缺省为 4 通道)
        candidates = [n for n in self.epigenetic_columns
                      if self.channel_types.get(n) == "positional"]
        if not candidates:
            candidates = [n for n, t in self.channel_types.items() if t == "positional"]

        def _row_ref(i: int) -> Dict[str, Any]:
            return {
                "file": str(long.loc[i, "_file"]),
                "row": int(long.loc[i, "_row"]),
                "cell_line": str(long.loc[i, "_cl"]),
            }

        single_blank: Dict[str, Any] = {}
        partial: Dict[str, Any] = {}
        for name in candidates:
            blank_rows = []
            partial_rows = []
            for i in range(n_samples):
                info = _sample_feature_info(long.loc[i, name], int(
                    self.result.get("length_consistency", {}).get("recommended_length_L")
                    or self.position_length))
                if info["kind"] == "blank":
                    blank_rows.append(_row_ref(i))
                elif info["kind"] == "pos" and info["has_nan"]:
                    partial_rows.append(_row_ref(i))
            single_blank[name] = {
                "type": self.channel_types.get(name, "positional"),
                "count": len(blank_rows),
                "ratio": round(len(blank_rows) / max(1, n_samples), 6),
                "row_indexes": [r["row"] for r in blank_rows][:500],
                "rows": blank_rows[:300],
                "rows_truncated": len(blank_rows) > 300,
            }
            partial[name] = {
                "count": len(partial_rows),
                "ratio": round(len(partial_rows) / max(1, n_samples), 6),
                "rows": partial_rows[:100],
            }

        # 全局纯空白: 所有位置型核心通道同行为空白
        global_blank = []
        if candidates:
            for i in range(n_samples):
                if all(_sample_feature_info(long.loc[i, n], int(
                        self.result.get("length_consistency", {}).get("recommended_length_L")
                        or self.position_length))["kind"] == "blank"
                       for n in candidates):
                    global_blank.append(_row_ref(i))

        info = {
            "positional_channels": candidates,
            "single_channel_all_blank": single_blank,
            "partial_positional_missing": partial,
            "global_all_channels_blank": {
                "channels": candidates,
                "count": len(global_blank),
                "ratio": round(len(global_blank) / max(1, n_samples), 6),
                "row_indexes": [r["row"] for r in global_blank][:500],
                "rows": global_blank[:300],
                "rows_truncated": len(global_blank) > 300,
            },
            "note_definition": (
                "单通道无标注 = 该样本在该通道 L 个位点全为 NaN/空值; "
                "全局无标注 = 全部位置型表观通道同行为空白 (纯空白样本, 完全无表观实验信号)。"
            ),
        }
        self.result["zero_annotation"] = info
        return info

    # ------------------------------------------------------------------
    # 7. 表观完整度与 70% 门禁
    # ------------------------------------------------------------------
    def epigenetic_gating(self) -> Dict[str, Any]:
        long = self.long if self.long is not None else self._build_long_frame()
        channels = list(self.epigenetic_columns.keys())
        per_cell: Dict[str, Any] = {}
        blocked_channels: List[str] = []

        if not self.channel_types:
            self._classify_channels()

        for cl, group in long.groupby("_cl"):
            n = len(group)
            per_channel: Dict[str, Any] = {}
            for disp in channels:
                ftype = self.channel_types.get(disp, "positional")
                col = group.get(disp) if disp in group.columns else pd.Series([None] * n)

                # 非空覆盖率 (空白 = NaN / 空串)
                measured = sum(1 for v in col if not _is_blank_value(v))
                coverage = float(measured) / max(1, n) * 100.0

                if ftype == "positional":
                    # 严格完整: 值非空且逐位点可解析为 position_length 个点 (L 对齐由 QC-A 单独校验)
                    strict_complete = 0
                    for v in col:
                        if _is_blank_value(v):
                            continue
                        vec = _parse_epi_vector(v, self.position_length)
                        if vec is not None:
                            strict_complete += 1
                    strict_pct = strict_complete / max(1, n) * 100.0
                    blocked = bool(strict_pct < 70.0)
                    if blocked and disp not in blocked_channels:
                        blocked_channels.append(disp)
                    per_channel[disp] = {
                        "channel_type": "positional",
                        "coverage_pct": round(coverage, 2),
                        "strict_complete_pct": round(strict_pct, 2),
                        "n_strict_complete": int(strict_complete),
                        "n_samples": int(n),
                        "gate_blocked_under_70": blocked,
                    }
                else:
                    # 全局标量/离散特征: 严禁做 L 匹配门禁, 仅测非空可用率
                    per_channel[disp] = {
                        "channel_type": ftype,
                        "coverage_pct": round(coverage, 2),
                        "strict_complete_pct": round(coverage, 2),
                        "n_strict_complete": int(measured),
                        "n_samples": int(n),
                        "gate_blocked_under_70": False,
                        "note": "全局标量/离散特征: 不执行 23 位点 L 对齐门禁, 仅统计非空可用率",
                    }
            per_cell[str(cl)] = per_channel

        info = {
            "channels": channels,
            "per_cell_line": per_cell,
            "blocked_channels": blocked_channels,          # 任一细胞系 <70% 的位置型通道
            "gate_mode_rule": (
                "仅对空间位置型通道执行 70% 门禁: 任一细胞系下严格完整序列比例 < 70% 时, "
                "特征工程阶段强制禁用该通道参与消融实验与训练, 或必须降级为 Zero-Masking 模式。"
            ),
            "warnings": [
                f"{ch} 完整度门禁触发: 至少一个细胞系严格完整序列比例 < 70%"
                for ch in blocked_channels
            ],
        }
        self.result["epigenetic_gating"] = info
        return info

    # ------------------------------------------------------------------
    # 8. 多模态离群检测 (Isolation Forest)
    # ------------------------------------------------------------------
    def detect_outliers_iforest(self) -> Dict[str, Any]:
        long = self.long if self.long is not None else self._build_long_frame()
        L = self.position_length
        seqs = long["sequence"].fillna("").astype(str).str.strip().str.upper()
        channels = list(self.epigenetic_columns.keys())

        # 展平多模态特征 (One-Hot 序列 + 表观逐位点值)
        # 序列 One-Hot 使用完整 4 碱基 [A, C, G, T] (与 23x8 编码一致; 旧版仅 A/G/C 丢弃 T)
        seq_bases = ["A", "C", "G", "T"]
        rows_vec: List[np.ndarray] = []
        for i, s in seqs.items():
            vec: List[float] = []
            for p in range(L):
                if p < len(s):
                    base = s[p]
                    vec += [1.0 if base == b else 0.0 for b in seq_bases]
                else:
                    vec += [np.nan] * len(seq_bases)
            for disp in channels:
                v = _parse_epi_vector(long.loc[i].get(disp), L)
                if v is not None:
                    vec += list(v)
                else:
                    vec += [np.nan] * L
            rows_vec.append(np.asarray(vec, dtype=np.float64))

        X = np.vstack(rows_vec)
        info: Dict[str, Any] = {"n_samples": int(X.shape[0]), "feature_dim": int(X.shape[1])}

        if X.shape[0] < 10 or np.isfinite(X).sum() == 0:
            info["note"] = "样本过少或全部缺失, 跳过离群检测"
            self.result["outliers"] = info
            return info

        # 中位数填充 (仅供离群检测), 再标准化避免数值通道量纲主导
        col_med = np.nanmedian(X, axis=0)
        col_med = np.where(np.isfinite(col_med), col_med, 0.0)
        Xf = np.where(np.isfinite(X), X, col_med)
        Xs = StandardScaler().fit_transform(Xf)

        clf = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1,
        )
        pred = clf.fit_predict(Xs)
        outlier_idx = np.where(pred == -1)[0]
        # decision_function 分值越低表示异常程度越高 (供明细表记录)
        anomaly_scores = clf.decision_function(Xs)

        y_all = long["y"].astype(float).to_numpy()
        # GC 全体分布 (供 abnormal_gc 提示用)
        gc_all = np.asarray([_sequence_gc_percent(s) if s else np.nan for s in seqs], dtype=np.float64)
        seq_list = long["sequence"].fillna("").astype(str).tolist()

        outlier_rows: List[Dict[str, Any]] = []
        detailed_rows: List[Dict[str, Any]] = []
        per_cell_counts: Dict[str, int] = {}
        for i in outlier_idx:
            cl_name = str(long.loc[int(i), "_cl"])
            per_cell_counts[cl_name] = per_cell_counts.get(cl_name, 0) + 1
            outlier_rows.append({
                "file": str(long.loc[int(i), "_file"]),
                "row": int(long.loc[int(i), "_row"]),
                "cell_line": cl_name,
            })
            y_val = float(y_all[int(i)]) if np.isfinite(y_all[int(i)]) else None
            gc_val = float(gc_all[int(i)]) if np.isfinite(gc_all[int(i)]) else None
            detailed_rows.append({
                "sample_index": int(long.loc[int(i), "_row"]),   # 原始文件 1-based 行号
                "file": str(long.loc[int(i), "_file"]),
                "cell_line": cl_name,
                "sequence": seq_list[int(i)],
                "target_y": y_val,
                "anomaly_score": round(float(anomaly_scores[int(i)]), 6),
                "gc_content": round(gc_val, 4) if gc_val is not None else None,
                "outlier_reason_hints": "; ".join(
                    _outlier_reason_hints(y_val, gc_val, y_all, gc_all)
                ),
            })

        mean_all = float(np.nanmean(y_all)) if y_all.size else np.nan
        y_out = y_all[outlier_idx]
        mean_out = float(np.nanmean(y_out)) if y_out.size else np.nan
        info.update({
            "n_outliers": int(len(outlier_idx)),
            "contamination": self.contamination,
            "outlier_ratio": round(len(outlier_idx) / max(1, X.shape[0]), 6),
            "row_indexes": [r["row"] for r in outlier_rows],
            "outlier_rows": outlier_rows,
            "per_cell_line_outlier_counts": dict(sorted(per_cell_counts.items())),
            "detailed_rows": detailed_rows,
            "detailed_report_file": "outliers_detailed_report.csv",
            "mean_efficiency_deviation": round(float(mean_out - mean_all), 6)
            if np.isfinite(mean_out) and np.isfinite(mean_all) else None,
            "mean_outlier_efficiency": round(float(mean_out), 6) if np.isfinite(mean_out) else None,
            "mean_all_efficiency": round(float(mean_all), 6) if np.isfinite(mean_all) else None,
            "handling_note": (
                "建议由用户评估: 若离群样本为真实强/弱编辑事件可保留用于鲁棒训练 (Huber Loss), "
                "若为录入/注释错误则剔除。"
            ),
        })
        self.result["outliers"] = info
        return info

    # ------------------------------------------------------------------
    # 运行汇总
    # ------------------------------------------------------------------
    def _aggregate(self) -> None:
        # 全局 QC 通过标记: 存在被 70% 门禁禁用的环境通道 -> 仍需用户在向导确认, 但不算致命错误
        gating = self.result.get("epigenetic_gating", {})
        blocked = gating.get("blocked_channels", [])
        issues: List[str] = []
        if self.sequence_column is None:
            issues.append("未自动识别到序列列 (sgRNA), 请在向导第三步指定列映射")
        if self.target_column is None:
            issues.append("未自动识别到编辑效率目标列, 请在向导第三步指定列映射")
        if not self.epigenetic_columns:
            issues.append("未自动识别到表观遗传通道列 (CTCF/DNase/H3K4me3/RRBS), 未执行完整度门禁")
        for w in gating.get("warnings", []):
            issues.append(w)
        ambiguous = self.result.get("ambiguous_bases", {}).get("detected_ambiguous_bases", [])
        if ambiguous:
            issues.append(f"检测到非标准碱基 {ambiguous}, 请在向导第三步配置替换映射")

        # ---- 补充 QC-A / QC-B 结论并入汇总 ----
        la = self.result.get("length_alignment", {})
        total_misalign = sum(
            int(ch.get("n_misaligned", 0))
            for ch in la.get("per_channel_alignment", {}).values()
        )
        if total_misalign:
            issues.append(
                f"检测到 {total_misalign} 条『序列与表观长度不对齐』样本 (见第 9 节), "
                "请在向导第三步核对特征列映射或修复数据"
            )
        za = self.result.get("zero_annotation", {})
        ga_blank = za.get("global_all_channels_blank", {})
        if ga_blank.get("count"):
            issues.append(
                f"检测到 {int(ga_blank['count'])} 条纯空白样本 "
                "(全部位置型表观通道均无标注, 见第 10 节)"
            )
        for ch_name, ch_state in za.get("single_channel_all_blank", {}).items():
            if ch_state.get("count"):
                issues.append(
                    f"通道 {ch_name} 有 {int(ch_state['count'])} 条整轨无标注样本 "
                    f"(占比 {ch_state['ratio'] * 100:.2f}%)"
                )

        self.result["qc_pass"] = len(blocked) == 0
        self.result["issues"] = issues
        self.result["recommendations"] = [
            *([f"序列列映射: {self.sequence_column}"] if self.sequence_column else []),
            *([f"目标列映射: {self.target_column}"] if self.target_column else []),
            *(["建议将 GC 含量作为独立连续信道/附加特征输入"] if self.result.get("gc_content", {}).get("recommend_gc_as_feature") else []),
            *([f"环境通道 {b} 需禁用或 Zero-Masking"] for b in blocked),
            *([f"非标准碱基 {ambiguous} 需替换映射"] if ambiguous else []),
            *([f"修复 {total_misalign} 条序列×表观长度不对齐样本或剔除后再入特征工程"] if total_misalign else []),
            *([f"处理 {int(ga_blank['count'])} 条表观全空白样本 (剔除或标记后鲁棒训练)"] if ga_blank.get("count") else []),
            *([f"全局标量/离散特征 {n} ({t}) 已跳过 L 长度校验, 仅统计缺失率与分布, 请向导确认是否作为附加输入"
               for n, t in [(n, la["global_feature_stats"][n]["type"])
                            for n in la.get("global_feature_stats", {})]]),
        ]
        self.result["metadata"] = {
            "sequence_column": self.sequence_column,
            "target_column": self.target_column,
            "cell_line_column": self.cell_line_column,
            "epigenetic_columns": {k: v for k, v in self.epigenetic_columns.items()},
            "feature_columns": {
                k: {"column": col, "type": self.channel_types.get(k, "unknown")}
                for k, col in self.feature_spec.items()
            },
            "files": [fp.name for fp in self._files],
            "recommended_length_L": self.result.get("length_consistency", {}).get("recommended_length_L"),
        }

    def run(self) -> Dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._build_long_frame()

        if self.verbose:
            print(f"[*] DataQC: {len(self._files)} 文件载入 | 长表行数 {len(self.long)}")
            print(f"    - 序列列: {self.sequence_column} | 目标列: {self.target_column}")
            print(f"    - 表观通道: {self.epigenetic_columns}")

        order = [
            self.profile_sample_sizes, self.kde_target_efficiency, self.detect_ambiguous_bases,
            self.detect_monomorphic_positions, self.profile_gc_content, self.length_consistency,
            self._classify_channels, self.length_alignment_qc, self.zero_annotation_diagnostics,
            self.epigenetic_gating, self.detect_outliers_iforest,
        ]
        for fn in order:
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                name = getattr(fn, "__name__", str(fn))
                self.result.setdefault("module_errors", {})[name] = str(exc)
                if self.verbose:
                    print(f"  [!] 模块 {name} 执行异常: {exc}")

        self._aggregate()
        return self.result

    # ------------------------------------------------------------------
    # Markdown 报告
    # ------------------------------------------------------------------
    def build_markdown(self) -> str:
        r = self.result
        md: List[str] = []
        md.append("# CRISPR-Cas9 数据质控报告 (Step 2: Data QC)\n")
        md.append(f"- 生成时间: {pd.Timestamp.now():%Y-%m-%d %H:%M:%S}")
        md.append(f"- 数据文件: {', '.join(self.result.get('metadata', {}).get('files', [])) or '—'}")
        md.append(f"- 输出目录: `{self.output_dir}`")
        md.append(f"- QC 状态: {'✅ PASS' if r.get('qc_pass') else '⚠️ REVIEW'}\n")

        # --- 1. 样本容量 ---
        ss = r.get("sample_size", {})
        md.append("\n## 1. 细胞系样本容量 (Sample Size Profiling)\n")
        md.append("| Cell Line | 有效样本量 |")
        md.append("| :--- | ---: |")
        for cl, n in ss.get("per_cell_line", {}).items():
            md.append(f"| {cl} | {int(n)} |")
        md.append(f"| **Total (全部数据集)** | **{int(ss.get('total_samples', 0))}** |\n")
        if not ss.get("per_cell_line"):
            md.append("> ⚠️ 未识别到细胞系字段，样本按单一数据集合并统计。\n")

        # --- 3. 非标准碱基 ---
        amb = r.get("ambiguous_bases", {})
        md.append("\n## 3. 非标准碱基探测 (Ambiguous Base Detection)\n")
        detected = amb.get("detected_ambiguous_bases", [])
        if not detected:
            md.append("✅ 未检测到 {A, C, G, T} 以外的非标准碱基。\n")
        else:
            md.append(f"> ⚠️ 检测到非标准碱基字符: **{', '.join(detected)}**  "
                      f"(含 IUPAC 简并: {', '.join(amb.get('iupac_hint', [])) or '无'})\n")
            md.append("| 字符 | 出现频数 |")
            md.append("| :--- | ---: |")
            for ch, cnt in amb.get("per_base_frequency", {}).items():
                md.append(f"| `{ch}` | {int(cnt)} |")
            md.append(f"\n- 受影响序列数: **{int(amb.get('n_affected_sequences', 0))}** "
                      f"(占比 {amb.get('affected_ratio', 0) * 100:.2f}%)")
            rows = amb.get("affected_rows", [])[:20]
            if rows:
                md.append("\n受影响行号 (前 20):\n")
                md.append("| 文件 | 行号(1-based) | 细胞系 |")
                md.append("| :--- | ---: | :--- |")
                for rr in rows:
                    md.append(f"| {rr['file']} | {int(rr['row'])} | {rr['cell_line']} |")
                if len(amb.get("affected_rows", [])) > 20:
                    md.append(f"\n... 共 {len(amb.get('affected_rows', []))} 行受影响。\n")

        # --- 4. 单态位点 ---
        mono = r.get("monomorphic_positions", {})
        md.append("\n## 4. 单核苷酸单态/零方差位点 (Monomorphic Positions)\n")
        if mono.get("aligned_n", 0) == 0:
            md.append("> 无长度对齐数据，跳过。\n")
        else:
            md.append(f"> 按 {self.position_length}nt 对齐样本 {mono.get('aligned_n')} 条。")
            whole = mono.get("whole_dataset", [])
            if not whole:
                md.append("✅ 全体数据集中不存在 100% 单一碱基位点。\n")
            else:
                md.append("\n全体数据集单态位点:\n")
                md.append("| 位点 | 碱基 |")
                md.append("| :--- | :--- |")
                for item in whole:
                    md.append(f"| pos_{item['position']} | {item['base']} |")
            cell_mono = {k: v for k, v in mono.get("per_cell_line", {}).items() if v}
            if cell_mono:
                md.append("\n各细胞系单态位点:\n")
                for cl, items in cell_mono.items():
                    md.append(f"- **{cl}**: " + ", ".join(
                        f"pos_{it['position']} {it['base']}" for it in items) + "")
            md.append(f"\n> 🔬 **生物学风险提示**: {mono.get('biological_risk_note', '')}\n")

        # --- 5. GC ---
        gc = r.get("gc_content", {})
        md.append("\n## 5. GC 含量分布 (GC Content Profiling)\n")
        if gc.get("n_valid", 0) >= 3:
            md.append(f"- 有效序列数: {int(gc['n_valid'])} | Mean: {gc['mean']:.2f}% | "
                      f"SD: {gc['std']:.2f}% | Min: {gc['min']:.2f}% | Max: {gc['max']:.2f}%")
            md.append(f"- CV 带宽 h: {gc.get('bandwidth_pooled'):.4f} "
                      f"(搜索范围 {gc['bandwidth_search_range'][0]:.4f} ~ {gc['bandwidth_search_range'][1]:.4f})")
            md.append(f"- 图: `{self.output_dir.name}/gc_content_kde.png`")
            md.append(f"- 📌 建议标记 `recommend_gc_as_feature: true` → 向导可询问 "
                      f"“是否将 GC 含量作为独立连续信道/附加特征输入”。\n")
        else:
            md.append("> 有效序列过少，未绘制 GC KDE。\n")

        # --- 6. 长度一致性 ---
        lc = r.get("length_consistency", {})
        md.append("\n## 6. 序列长度一致性 (Sequence Length Consistency)\n")
        mode = lc.get("recommended_length_L", self.position_length)
        md.append(f"- 长度众数 (推荐输入长度 L): **{mode} nt**")
        dist = lc.get("length_distribution", {})
        if dist:
            md.append("\n| 长度 | 序列数 |")
            md.append("| ---: | ---: |")
            for ln, cnt in sorted(dist.items()):
                md.append(f"| {ln} | {cnt} |")
        anoms = lc.get("anomalies", [])
        md.append(f"\n- 长度异常序列数: **{int(lc.get('n_length_anomalies', 0))}** "
                  f"(占比 {lc.get('anomaly_ratio', 0) * 100:.2f}%)\n")
        if anoms:
            md.append("| 文件 | 行号(1-based) | 细胞系 | 实际长度 | 序列片段 |")
            md.append("| :--- | ---: | :--- | ---: | :--- |")
            for a in anoms[:25]:
                frag = a["sequence"][:60] + ("..." if len(a["sequence"]) > 60 else "")
                md.append(f"| {a['file']} | {int(a['row'])} | {a['cell_line']} | {int(a['length'])} | `{frag}` |")
            if len(anoms) > 25:
                md.append(f"\n... 其余 {len(anoms) - 25} 条异常序列见 `qc_summary.json`。")

        # --- 7. 表观完整度与门禁 ---
        gating = r.get("epigenetic_gating", {})
        md.append("\n## 7. 表观遗传完整度与 70% 门禁 (Epigenetic Completeness & Hard Gating)\n")
        if not gating.get("channels"):
            md.append("> ⚠️ 未自动识别到表观通道列。若数据包含 CTCF/DNase/H3K4me3/RRBS，"
                      "请在向导第三步配置列映射后重跑。\n")
        else:
            for cl, chans in gating.get("per_cell_line", {}).items():
                md.append(f"\n**Cell Line: {cl}**\n")
                md.append("| 环境通道 | 非空覆盖率 % | 严格完整率 % | 70% 门禁 |")
                md.append("| :--- | ---: | ---: | :--- |")
                for disp, info in chans.items():
                    warn = "⚠️ **BLOCKED**" if info["gate_blocked_under_70"] else "✅"
                    md.append(f"| {disp} | {info['coverage_pct']:.1f} | {info['strict_complete_pct']:.1f} | {warn} |")
            blocked = gating.get("blocked_channels", [])
            if blocked:
                md.append("\n> ⚠️ **高亮警示**: 环境变量 "
                          f"**{', '.join(blocked)}** 的严格完整序列比例不足 70%，"
                          "系统将在特征工程阶段**强制禁用**该环境通道参与消融实验与训练，"
                          "或必须降级为 **Zero-Masking** 模式。\n")
            else:
                md.append("\n✅ 全部环境通道严格完整率 ≥ 70%，无门禁阻断。\n")

        # --- 8. 离群检测 ---
        ol = r.get("outliers", {})
        md.append("\n## 8. 多模态离群检测 (Isolation Forest)\n")
        if ol.get("n_samples", 0) == 0 or "n_outliers" not in ol:
            md.append(f"> {ol.get('note', '未执行')}\n")
        else:
            md.append(f"- 样本数: {int(ol['n_samples'])} | 特征维度: {int(ol.get('feature_dim', 0))}")
            md.append(f"- 离群样本总数: **{int(ol['n_outliers'])}** "
                      f"(占比 {ol.get('outlier_ratio', 0) * 100:.2f}%, contamination={ol.get('contamination')})")
            per_cell = ol.get("per_cell_line_outlier_counts", {})
            if per_cell:
                md.append("- 各细胞系离群分布: " +
                          ", ".join(f"{cl}: {int(cnt)}" for cl, cnt in per_cell.items()))
            dev = ol.get("mean_efficiency_deviation")
            md.append(f"- 全体平均编辑效率: {ol.get('mean_all_efficiency')} | "
                      f"离群样本平均编辑效率: {ol.get('mean_outlier_efficiency')}")
            md.append(f"- 离群 vs 全体 平均编辑效率偏差: **{dev if dev is not None else 'N/A'}**")
            md.append(f"\n> 💡 {ol.get('handling_note', '')}")
            md.append("\n> 📄 完整离群样本列表 (含 anomaly_score / GC / 归因提示) 已单独导出至 "
                      "`outliers_detailed_report.csv`，方便后续过滤或追溯分析。\n")

        # --- 9. 序列 × 表观长度对齐检测 ---
        la = r.get("length_alignment", {})
        md.append("\n## 9. 序列 × 表观长度对齐检测 (Length Alignment QC)\n")
        md.append(f"> 序列众数长度 (标准长度 L) = **{int(la.get('recommended_length_L', self.position_length))} nt**\n")
        if not la.get("per_channel_alignment"):
            md.append("> 未识别到空间位置型特征通道，跳过对齐检测。\n")
        else:
            md.append("**位置型通道 (严格校验位数 == L)**\n\n")
            md.append("| 通道 | 样本数 | 对齐数 | 不对齐数 | 整轨空白 | 局部NaN(数值阵) | 不对齐占比 |")
            md.append("| :--- | ---: | ---: | ---: | ---: | ---: | ---: |")
            for ch, st in la["per_channel_alignment"].items():
                md.append(f"| {ch} | {int(st['n_samples'])} | {int(st['n_aligned'])} | "
                          f"{int(st['n_misaligned'])} | {int(st['n_blank'])} | {int(st['n_partial_nan'])} | "
                          f"{st['misaligned_ratio'] * 100:.2f}% |")
            total_mis = sum(int(st["n_misaligned"]) for st in la["per_channel_alignment"].values())
            if total_mis:
                md.append(f"\n> ⚠️ 共 **{total_mis}** 条『**序列与表观长度不对齐**』样本 (序列 {la.get('recommended_length_L')}nt 但该通道实际位点数 ≠ L)。\n")
                md.append("| 文件 | 行号(1-based) | 细胞系 | 通道 | 实际位数 | 期望 L | 取值预览 |")
                md.append("| :--- | ---: | :--- | :--- | ---: | ---: | :--- |")
                shown = 0
                for ch, st in la["per_channel_alignment"].items():
                    for m in st.get("misaligned_rows", []):
                        if shown >= 20:
                            break
                        md.append(f"| {m['file']} | {int(m['row'])} | {m['cell_line']} | {ch} | "
                                  f"{m['actual_units'] if m['actual_units'] is not None else 'N/A'} | "
                                  f"{int(m['expected_units'])} | `{m['preview'][:30]}` |")
                        shown += 1
                    if shown >= 20:
                        break
                if total_mis > 20:
                    md.append(f"\n... 其余 {total_mis - 20} 条见 `qc_summary.json`。")

            gstats = la.get("global_feature_stats", {})
            if gstats:
                md.append("\n**全局标量 / 离散特征 (严禁 L 长度匹配, 仅空值率与分布)**\n\n")
                md.append("| 特征 | 类型 | 缺失率 % | 非空数 | 唯一值 | 分布/统计 |")
                md.append("| :--- | :--- | ---: | ---: | ---: | :--- |")
                for name, gs in gstats.items():
                    if gs["type"] == "global_numeric":
                        dist = (f"mean={gs.get('mean', float('nan')):.3g} "
                                f"std={gs.get('std', float('nan')):.3g} "
                                f"[{gs.get('min', float('nan')):.3g}, {gs.get('max', float('nan')):.3g}]")
                    else:
                        dist = "; ".join(
                            f"{t['value']}:{int(t['count'])}" for t in gs.get("category_frequency", [])
                        ) or "—"
                    md.append(f"| {name} | {gs['type']} | {gs['missing_rate'] * 100:.2f} | "
                              f"{int(gs['n_non_null'])} | {int(gs['n_unique'])} | {dist} |")
                md.append("\n> ✅ 全局标量/离散特征已自动跳过序列长度 L 对齐校验 "
                          "(仅统计缺失率与分布频数)。")

        # --- 10. 表观零标注诊断 ---
        za = r.get("zero_annotation", {})
        md.append("\n## 10. 表观零标注诊断 (Zero-Annotation Diagnostics)\n")
        single_blank = za.get("single_channel_all_blank", {})
        if not single_blank:
            md.append("> 未识别到位置型表观通道，跳过。\n")
        else:
            md.append("**单通道整轨无标注 (L 个位点全为 NaN/空值)**\n\n")
            md.append("| 通道 | 整轨无标注样本数 | 占比 % |")
            md.append("| :--- | ---: | ---: |")
            for ch, st in single_blank.items():
                md.append(f"| {ch} | {int(st['count'])} | {st['ratio'] * 100:.2f} |")
            any_rows = any(st["count"] for st in single_blank.values())
            if any_rows:
                md.append("\n受影响行号 (各通道前 20):\n")
                md.append("| 通道 | 文件 | 行号(1-based) | 细胞系 |")
                md.append("| :--- | :--- | ---: | :--- |")
                shown = 0
                for ch, st in single_blank.items():
                    for rr in st.get("rows", []):
                        if shown >= 20:
                            break
                        md.append(f"| {ch} | {rr['file']} | {int(rr['row'])} | {rr['cell_line']} |")
                        shown += 1
                    if shown >= 20:
                        break

            partial = za.get("partial_positional_missing", {})
            partial_nonzero = {k: v for k, v in partial.items() if v.get("count")}
            if partial_nonzero:
                md.append("\n**局部点位缺失 (数值数组内含 NaN)**\n\n")
                md.append("| 通道 | 局部缺失样本数 | 占比 % |")
                md.append("| :--- | ---: | ---: |")
                for ch, v in partial_nonzero.items():
                    md.append(f"| {ch} | {int(v['count'])} | {v['ratio'] * 100:.2f} |")

            g_blank = za.get("global_all_channels_blank", {})
            md.append("\n**全局无标注 (全部位置型表观通道均空白 → 纯空白样本)**\n\n")
            if not g_blank.get("count"):
                md.append("✅ 无纯空白样本。\n")
            else:
                md.append(f"> ⚠️ 检测到 **{int(g_blank['count'])}** 条纯空白样本 "
                          f"(占比 {g_blank['ratio'] * 100:.2f}%): 该样本完全没有任何表观实验信号。\n")
                md.append("| 文件 | 行号(1-based) | 细胞系 |")
                md.append("| :--- | ---: | :--- |")
                for rr in g_blank.get("rows", [])[:20]:
                    md.append(f"| {rr['file']} | {int(rr['row'])} | {rr['cell_line']} |")
                if g_blank.get("rows_truncated"):
                    md.append(f"\n... 共 {int(g_blank['count'])} 条, 其余行号见 `qc_summary.json`。")
            md.append(f"\n> {za.get('note_definition', '')}\n")

        # --- 汇总 ---
        md.append("\n## 汇总与建议\n")
        recs = r.get("recommendations", [])
        if recs:
            for i, rec in enumerate(recs, 1):
                md.append(f"{i}. {rec}")
        else:
            md.append("无特殊建议。")
        for iss in r.get("issues", []):
            md.append(f"- ⚠️ {iss}")
        md.append(f"\n*QC PASS = {bool(r.get('qc_pass'))}*")
        return "\n".join(md)

    # ------------------------------------------------------------------
    # 写出
    # ------------------------------------------------------------------
    def write_outputs(self) -> Dict[str, str]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        md_path = self.output_dir / "quality_report.md"
        md_path.write_text(self.build_markdown(), encoding="utf-8")

        json_path = self.output_dir / "qc_summary.json"
        # 处理 numpy 类型 -> json 安全
        def _default(o: Any) -> Any:
            if isinstance(o, (np.integer,)):
                return int(o)
            if isinstance(o, (np.floating,)):
                return float(o)
            if isinstance(o, np.ndarray):
                return o.tolist()
            raise TypeError(f"不可序列化类型: {type(o)}")
        json_path.write_text(
            json.dumps(self.result, ensure_ascii=False, indent=2, default=_default),
            encoding="utf-8",
        )

        # 离群样本明细表 (独立 CSV, 便于用户过滤/追溯)
        outlier_report_path = self.output_dir / "outliers_detailed_report.csv"
        ol = self.result.get("outliers", {})
        detailed_rows = ol.get("detailed_rows", []) if isinstance(ol, dict) else []
        if detailed_rows:
            detail_cols = ["sample_index", "file", "cell_line", "sequence",
                           "target_y", "anomaly_score", "gc_content", "outlier_reason_hints"]
            detail_df = pd.DataFrame(detailed_rows, columns=detail_cols)
            detail_df.to_csv(outlier_report_path, index=False, encoding="utf-8-sig")
        return {
            "markdown": str(md_path),
            "json": str(json_path),
            "outliers_detailed_report": str(outlier_report_path),
            "target_kde": str(self.output_dir / "target_efficiency_kde.png"),
            "gc_kde": str(self.output_dir / "gc_content_kde.png"),
        }


# ===========================================================================
# 输入文件解析 / 顶层入口
# ===========================================================================

def _resolve_input_files(data_path: Union[PathLike, Sequence[PathLike]]) -> List[Path]:
    if isinstance(data_path, (str, Path)):
        p = _as_path(data_path)
        if p.is_dir():
            files = sorted(
                list(p.glob("*.csv")) + list(p.glob("*.tsv")) + list(p.glob("*.txt"))
            )
            return files
        if p.is_file():
            return [p]
        raise FileNotFoundError(f"数据路径不存在: {p}")
    files: List[Path] = []
    for item in data_path:
        item_p = _as_path(item)
        if item_p.is_file():
            files.append(item_p)
        else:
            raise FileNotFoundError(f"数据文件不存在: {item_p}")
    return files


def run_data_qc(
    data_path: Union[PathLike, Sequence[PathLike]],
    output_dir: Optional[PathLike] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    第二步数据质控顶层入口。

    参数
    ----
    data_path : 单个/多个 csv|tsv 文件路径, 或包含这些文件的目录。
    output_dir : 报告输出目录 (默认 data/data_report/)。
    **kwargs   : 透传给 DataQualityController 的配置 (列名映射 / 带宽CV / 离群 contamination 等)。

    返回
    ----
    dict : 完整 qc_summary (与写入 qc_summary.json 的内容一致)。
    """
    controller = DataQualityController(data_path=data_path, output_dir=output_dir, **kwargs)
    result = controller.run()
    controller.write_outputs()
    return result


# ===========================================================================
# 本地独立 Demo (无需 GUI)
# ===========================================================================

def _demo_data() -> str:
    """
    构建演示数据源:
      优先使用仓库自带 data/source_data (真实 CRISPR 质控演示, 4 细胞系 CSV);
      若不存在, 合成含非标准碱基/长度异常/缺失表观通道的脏数据目录用于功能演示。
    返回数据路径 (目录或单文件)。报告输出目录默认 data/data_report/ (可用 --output-dir 覆盖)。
    """
    project_src = Path("data/source_data")
    if project_src.exists() and any(project_src.glob("*.csv")):
        return str(project_src)
    return _synthesize_demo()


def _synthesize_demo() -> str:
    """合成 3 个细胞系脏数据 CSV (包含 N 碱基、长度异常、缺失表观通道)。"""
    import tempfile

    rng = np.random.default_rng(7)
    bases = list("ACGT")
    tmp = Path(tempfile.mkdtemp(prefix="qc_demo_"))
    tmp.mkdir(exist_ok=True)

    def make_seq(rng, L=23):
        return "".join(str(rng.choice(bases)) for _ in range(L))

    for idx, cl in enumerate(["hct116", "hela", "hl60"]):
        n = 150 + idx * 50
        rows = []
        for i in range(n):
            seq = make_seq(rng)
            if i % 97 == 0:                      # 掺入非标准碱基
                pos = rng.integers(0, 23)
                seq = seq[:pos] + "N" + seq[pos + 1:]
            if i % 211 == 0:                     # 长度异常
                seq = seq[:-3]
            y = float(np.clip(0.55 + 0.30 * (seq[17:20].count("G")) / 3 + rng.normal(0, 0.06), 0.1, 1.0))
            rows.append({
                "sgRNA": seq,
                "CTCF": "".join(str(rng.choice(["A", "N"])) for _ in range(23)),
                "Dnase": "".join(str(rng.choice(["A", "N"])) for _ in range(23)),
                "H3K4me3": "".join(str(rng.choice(["A", "N"])) for _ in range(23)),
                "RRBS": "A" * 23 if i % 5 == 0 else "N" * 23,
                "Normalized efficacy": y,
            })
        if idx == 1:                             # 制造表观通道缺失
            for j in range(0, n, 3):
                rows[j]["H3K4me3"] = None
        pd.DataFrame(rows).to_csv(tmp / f"{cl}.csv", index=False)
    return str(tmp)


def main() -> None:
    parser = argparse.ArgumentParser(description="CRISPR Data QC (Step 2) — headless scan")
    parser.add_argument("--data", type=str, default="auto", help="CSV/TSV 文件或目录 (默认 data/source_data 或合成演示)")
    parser.add_argument("--output-dir", type=str, default=None, help="报告输出目录 (默认 data/data_report/)")
    parser.add_argument("--print-markdown", action="store_true", help="终端打印完整 Markdown")
    args = parser.parse_args()

    if args.data == "auto":
        data_path = _demo_data()
        print(f"[Demo] 数据源: {data_path} | 输出: {args.output_dir or 'data/data_report/'}")
    else:
        data_path = args.data

    result = run_data_qc(data_path=data_path, output_dir=args.output_dir)

    # 终端打印质控概览
    ss = result.get("sample_size", {})
    print("\n" + "=" * 72)
    print("DATA QC OVERVIEW")
    print("=" * 72)
    for cl, n in ss.get("per_cell_line", {}).items():
        print(f"  {cl:<12} n = {int(n)}")
    print(f"  {'TOTAL':<12} n = {int(ss.get('total_samples', 0))}")
    gc = result.get("gc_content", {})
    print(f"  GC recommend_as_feature = {gc.get('recommend_gc_as_feature')}  "
          f"(mean={gc.get('mean')})")
    amb = result.get("ambiguous_bases", {})
    print(f"  Ambiguous bases: {amb.get('detected_ambiguous_bases')}  "
          f"(n_affected={amb.get('n_affected_sequences')})")
    lc = result.get("length_consistency", {})
    print(f"  Recommended length L = {lc.get('recommended_length_L')}  "
          f"(anomalies={lc.get('n_length_anomalies')})")
    ol = result.get("outliers", {})
    if "n_outliers" in ol:
        print(f"  IsolationForest outliers = {ol.get('n_outliers')} / {ol.get('n_samples')}  "
              f"(mean y deviation = {ol.get('mean_efficiency_deviation')})")
    gating = result.get("epigenetic_gating", {})
    print(f"  Gated/blocked channels: {gating.get('blocked_channels')}")
    print(f"  QC PASS = {result.get('qc_pass')}")
    print(f"  Issues: {result.get('issues')}")
    print("=" * 72)

    if args.print_markdown:
        md_path = Path(args.output_dir or DEFAULT_OUTPUT_DIR) / "quality_report.md"
        if md_path.exists():
            print(md_path.read_text(encoding="utf-8"))
        else:
            print("[!] quality_report.md 未生成")


if __name__ == "__main__":
    main()
