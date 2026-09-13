# Submit/analyse/visualization.py
"""
CRISPR-Cas9 sgRNA 空间位置归因与生信图表绘制引擎 (V6 显著性白色掩码热图与去重组合增量树图版)
====================================================================================
核心改进 (V6)：
  1. 23nt 位置热图：无显著性 (significant 为无) 的位点以白色显示，
     具有 ./*/**/*** 显著性的特征保留数值色域颜色 (与白色区分开)，
     显著性取自 summary/feature_importance/。不再使用方格内文字标注。
  2. 环境增量树图 (去重组合路径版)：
     - 树顶 (根)：sequence-only 基线的 R2 / MAE；
     - 每个节点 = 一个真实去重组合：路径内环境永不重复，组合按规范序唯一出现一次；
     - 每个非根节点均展示相对父节点 (少一个环境的组合) 的增量 dR2 / dMAE，
       节点三行：环境名 / dR2 / dMAE，仅以新加入的环境名标注，不显示组合全名；
     - 父/子组合实测数据缺失的分支直接剪除，不生成 dup / N/A 灰色占位节点；
     - 图内文字全部使用英文 (避免中文字体缺字)，叶节点字样紧凑不超框。
  3. 表观因子贡献对比图保持不变；Delta R2 环境泛化增益图已删除。
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def _ensure_repo_root_on_path() -> str:
    """让 `python analyse/visualization.py` 也能 import `analyse.*`。

    直接以脚本方式运行本文件时, sys.path[0] 是 analyse/ 目录, 仓库根不在路径上,
    于是 `import analyse.config` / `analyse.environment.factorial_dag` 会失败。
    这里把仓库根 (本文件的父目录的父目录) 插到 sys.path, 幂等且无副作用。
    通过 analyse.visualization 包导入 (backend_runner) 时该路径已存在, 不会有影响。
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


_REPO_ROOT = _ensure_repo_root_on_path()

# 基础绘图风格与字体设置
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False
sns.set_theme(style="whitegrid")

CHANNELS = ["A", "C", "G", "T", "CTCF", "Dnase", "H3K4me3", "RRBS"]
SEQ_CHANNELS = ["A", "C", "G", "T"]
EPI_CHANNELS = ["CTCF", "Dnase", "H3K4me3", "RRBS"]

# 显著性星级 -> 排序权重 (0 = 无显著性)
SIG_RANK = {"": 0, ".": 1, "*": 2, "**": 3, "***": 4}

# feature_importance 文件夹内 .md 文件名 -> 模型族 (CNN 按卷积核拆分)
FEATURE_IMPORTANCE_FILES = {
    "linear_coefficiency": "linear",
    "xgboost_importance": "xgboost",
    "mlp_importance": "mlp",
    "cnn33_importance": "cnn33",
    "cnn53_importance": "cnn53",
    "cnn73_importance": "cnn73",
    "cnn_importance": "cnn",          # 兼容旧版未拆分文件
    "transformer_importance": "transformer",
}

# 各模型专属生信指标配置
MODEL_METRIC_CONFIG = {
    "linear": {
        "col_candidates": ["Linear_Coefficient", "weight", "coefficient", "coef"],
        "metric_name": "Robust Linear Coefficient (β, Clipped to ±1.0)",
        "cmap": "RdBu_r",
        "center": 0.0
    },
    "xgboost": {
        "col_candidates": ["XGB_Gain", "importance_gain", "gain", "shap_snr"],
        "metric_name": "Feature Split Gain",
        "cmap": "YlOrRd",
        "center": None
    },
    "mlp": {
        "col_candidates": ["MLP_IG", "ig_mean", "ig_snr", "smoothgrad_snr"],
        "metric_name": "Integrated Gradients (IG Mean)",
        "cmap": "YlOrRd",
        "center": None
    },
    "cnn": {
        "col_candidates": ["CNN_ISM", "ism_mean_delta", "ism_snr"],
        "metric_name": "In-Silico Mutagenesis (ISM |Δy|)",
        "cmap": "Reds",
        "center": None
    },
    "transformer": {
        "col_candidates": ["Transformer_Attention", "attn_weight", "attn_snr", "ig_mean"],
        "metric_name": "Self-Attention Weight",
        "cmap": "Purples",
        "center": None
    }
}


def _metric_cfg(m_fam: str) -> Dict:
    """按模型族取指标配置 (cnn33/cnn53/cnn73 共用 cnn 配置)。"""
    m_fam = str(m_fam)
    if m_fam in MODEL_METRIC_CONFIG:
        return MODEL_METRIC_CONFIG[m_fam]
    if m_fam.startswith("cnn"):
        return MODEL_METRIC_CONFIG["cnn"]
    return MODEL_METRIC_CONFIG["linear"]


def _make_heatmap_cmap(cfg: Dict, m_fam: str):
    """
    构造热图色图：
      - 掩码(无显著性)单元格底色置为纯白；
      - 非线性模型 (xgboost/mlp/cnn*/transformer) 截断色图低端 (自 25% 起)，
        使低幅值但显著的格仍呈可见颜色，与白色掩码背景明确区分。
    """
    from matplotlib.colors import LinearSegmentedColormap
    base = plt.get_cmap(cfg["cmap"])
    if str(m_fam) == "linear":
        cmap = base.copy()
    else:
        cmap = LinearSegmentedColormap.from_list(
            f"{cfg['cmap']}_trunc", base(np.linspace(0.25, 1.0, 256))
        )
    cmap.set_bad("#ffffff")
    return cmap


# ============================================================
# 1. 基础数据解析与异常值隔离加载
# ============================================================

def parse_info_file(info_path: str) -> Dict:
    info = {}
    if not os.path.exists(info_path):
        return info
    with open(info_path, 'r', encoding='utf-8') as f:
        for line in f:
            if ':' in line:
                k, v = line.strip().split(':', 1)
                info[k.strip().lower()] = v.strip().lower()
    return info


def parse_feature_position_channel(feat_name: str) -> Tuple[int, str]:
    fn = str(feat_name).strip()
    if 'bias' in fn.lower() or 'intercept' in fn.lower():
        return -999, 'Bias'

    m = re.search(r'pos_?(\d+)', fn, re.IGNORECASE)
    pos = int(m.group(1)) if m else -1
    if pos == -1:
        m2 = re.search(r'_(\d+)$', fn)
        pos = int(m2.group(1)) if m2 else -1

    fn_lower = fn.lower()
    if 'h3k4me3' in fn_lower or 'h3k4' in fn_lower: ch = 'H3K4me3'
    elif 'ctcf' in fn_lower: ch = 'CTCF'
    elif 'dnase' in fn_lower: ch = 'Dnase'
    elif 'rrbs' in fn_lower: ch = 'RRBS'
    elif 'a' in fn_lower: ch = 'A'
    elif 'g' in fn_lower: ch = 'G'
    elif 'c' in fn_lower: ch = 'C'
    elif 't' in fn_lower: ch = 'T'
    else: ch = 'Unknown'

    if 0 <= pos <= 22:
        pos = pos + 1
    elif pos > 23:
        pos = ((pos - 1) % 23) + 1

    return pos, ch


def load_raw_feature_records(batch_dir: Path) -> pd.DataFrame:
    records = []
    csv_files = list(batch_dir.glob("**/*importance*.csv")) + list(batch_dir.glob("**/*weights*.csv"))

    for fpath in csv_files:
        if 'summary' in str(fpath) or 'pred' in fpath.name:
            continue

        exp_dir = fpath.parent
        info_files = list(exp_dir.glob("*info*.txt"))
        info = parse_info_file(str(info_files[0])) if info_files else {}

        model = str(info.get('model', '')).lower()
        if not model:
            if 'linear' in exp_dir.name.lower(): model = 'linear'
            elif 'xgb' in exp_dir.name.lower(): model = 'xgboost'
            elif 'mlp' in exp_dir.name.lower(): model = 'mlp'
            elif 'cnn' in exp_dir.name.lower(): model = 'cnn'
            elif 'trans' in exp_dir.name.lower(): model = 'transformer'
            else: continue

        model_family = "linear"
        if "xgb" in model:
            model_family = "xgboost"
        elif "mlp" in model:
            model_family = "mlp"
        elif "cnn" in model:
            # CNN 按序列卷积核拆分为 cnn33 / cnn53 / cnn73 (环境卷积核固定 3)
            try:
                seq_k = int(float(info.get('sequence_kernel', info.get('sequence_kernel_size', '3'))))
            except Exception:
                seq_k = 3
            if seq_k not in (3, 5, 7):
                seq_k = 3
            model_family = f"cnn{seq_k}3"
        elif "trans" in model:
            model_family = "transformer"

        split_type = str(info.get('split_type', 'single')).lower()
        cell_line = str(info.get('cell_line', info.get('held_out_cell_line', 'none'))).lower()
        if split_type == 'mixed': cell_line = 'none'
        environment = str(info.get('environment', info.get('combination', 'all'))).lower()
        seed = str(info.get('random_seed', info.get('seed', '42')))

        try:
            df = pd.read_csv(fpath)
            cols_lower = {c.lower(): c for c in df.columns}
            feat_col = cols_lower.get('feature', cols_lower.get('feat', None))
            if not feat_col: continue

            cfg = _metric_cfg(model_family)
            val_col = None
            for cand in cfg["col_candidates"]:
                if str(cand).lower() in cols_lower:
                    val_col = cols_lower[str(cand).lower()]
                    break
            if not val_col:
                val_col = df.columns[1]

            snr_col = cols_lower.get(
                'shap_snr', cols_lower.get('ism_snr', cols_lower.get('t_stat',
                cols_lower.get('ig_snr', cols_lower.get('attn_snr',
                cols_lower.get('attention_snr', None))))))

            for _, row in df.iterrows():
                feat = str(row[feat_col])
                pos, ch = parse_feature_position_channel(feat)
                if ch in ['Unknown', 'Bias'] or pos < 1 or pos > 23:
                    continue

                raw_val = float(row[val_col]) if pd.notna(row[val_col]) else 0.0
                snr_val = float(row[snr_col]) if snr_col and pd.notna(row[snr_col]) else abs(raw_val)

                # ========================================================
                # 关键：异常值隔离与鲁棒平滑 (防止污染画图)
                # ========================================================
                if model_family == "linear":
                    # 线性系数限制在 [-1.0, 1.0] 安全区间，防止异常值冲刷色阶
                    val = float(np.clip(raw_val, -1.0, 1.0))
                    abs_val = float(np.clip(abs(raw_val), 0.0, 1.0))
                    # t_stat 限制在合理动态范围
                    snr_clean = float(np.clip(abs(snr_val), 0.01, 10.0))
                else:
                    val = raw_val
                    abs_val = abs(raw_val)
                    snr_clean = max(0.01, min(15.0, abs(snr_val)))

                records.append({
                    "model_family": model_family,
                    "model_raw": model,
                    "split_type": split_type,
                    "cell_line": cell_line,
                    "environment": environment,
                    "seed": seed,
                    "feature": feat,
                    "position": pos,
                    "channel": ch,
                    "importance": val,
                    "abs_importance": abs_val,
                    "snr": snr_clean
                })
        except Exception:
            continue

    if not records:
        # 演示兜底数据 (CNN 也按卷积核拆分)
        rng = np.random.default_rng(42)
        for m_fam in ["linear", "xgboost", "mlp", "cnn33", "cnn53", "cnn73", "transformer"]:
            for st, cl in [("single", "hct116"), ("single", "hela"), ("all", "hl60"), ("mixed", "none")]:
                for p in range(1, 24):
                    for ch in CHANNELS:
                        base = 0.05
                        if 11 <= p <= 20 and ch == 'G': base = 0.35 + rng.normal(0, 0.02)
                        elif p >= 21 and ch == 'G': base = 0.28 + rng.normal(0, 0.02)
                        elif ch == 'Dnase': base = 0.22 + rng.normal(0, 0.02)
                        elif ch == 'CTCF': base = 0.18 + rng.normal(0, 0.02)
                        elif ch == 'RRBS': base = -0.10 if m_fam == "linear" else 0.10
                        records.append({
                            "model_family": m_fam,
                            "model_raw": m_fam,
                            "split_type": st,
                            "cell_line": cl,
                            "environment": "all",
                            "seed": "42",
                            "feature": f"pos{p}_{ch}",
                            "position": p,
                            "channel": ch,
                            "importance": base,
                            "abs_importance": abs(base),
                            "snr": max(0.1, abs(base) * 10)
                        })

    return pd.DataFrame(records)


# ============================================================
# 1.5 显著性星级加载 (自 summary/feature_importance/*.md 解析)
# ============================================================

def load_significance_table(batch_dir: Path) -> pd.DataFrame:
    """
    解析 summary/feature_importance/ 下 5 大模型的 .md 报告，
    提取每个特征 (position, channel) 的显著性星级 (., *, **, *** 或无)。
    """
    feature_importance_dir = batch_dir / "summary" / "feature_importance"
    if not feature_importance_dir.exists():
        return pd.DataFrame()

    records = []
    for fname, model_family in FEATURE_IMPORTANCE_FILES.items():
        md_file = feature_importance_dir / f"{fname}.md"
        if not md_file.exists():
            continue
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            continue

        for line in lines:
            line = line.strip()
            if not line.startswith('|') or not line.endswith('|'):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) < 5:
                continue
            # 跳过表头与分隔行
            if 'split_type' in cells[0].lower() or set(cells[1]) <= {'-', ':'}:
                continue

            split_type = cells[0].lower()
            environment = cells[1].lower()
            cell_line = cells[2].lower()
            feature = cells[3]
            sig = cells[-1] if cells else ""

            pos, ch = parse_feature_position_channel(feature)
            if ch in ['Unknown', 'Bias'] or pos < 1 or pos > 23:
                continue

            records.append({
                "model_family": model_family,
                "split_type": split_type,
                "cell_line": cell_line,
                "environment": environment,
                "feature": feature,
                "position": pos,
                "channel": ch,
                "significance": sig if sig in SIG_RANK else ""
            })

    return pd.DataFrame(records)


# ============================================================
# 2. 生成文件夹 1: 01_position_heatmaps/ (无显著性位点白色掩码)
# ============================================================

def generate_position_heatmaps(df_records: pd.DataFrame, output_dir: Path, sig_df: Optional[pd.DataFrame] = None):
    output_dir.mkdir(parents=True, exist_ok=True)
    if sig_df is None:
        sig_df = pd.DataFrame()

    single_all_df = df_records[df_records['split_type'].isin(['single', 'all'])].copy()
    if not single_all_df.empty:
        groups = single_all_df.groupby(['split_type', 'cell_line', 'model_family'])
        for (st, cl, m_fam), sub_df in groups:
            _draw_single_heatmap(
                sub_df=sub_df,
                title_prefix=f"{st.upper()} [{cl.upper()}] - {m_fam.upper()}",
                m_fam=m_fam,
                output_path=output_dir / f"{st}_{cl}_{m_fam}_heatmap.png",
                sig_df=sig_df,
                split_type=st,
                cell_line=cl
            )

    mixed_df = df_records[df_records['split_type'] == 'mixed'].copy()
    if not mixed_df.empty:
        m_groups = mixed_df.groupby('model_family')
        for m_fam, sub_df in m_groups:
            avg_sub_df = sub_df.groupby(['position', 'channel'], as_index=False)['importance'].mean()
            _draw_single_heatmap(
                sub_df=avg_sub_df,
                title_prefix=f"MIXED (4-Seed Averaged) - {m_fam.upper()}",
                m_fam=m_fam,
                output_path=output_dir / f"mixed_{m_fam}_heatmap.png",
                sig_df=sig_df,
                split_type='mixed',
                cell_line='none'
            )


def _build_significance_rank(sig_df: pd.DataFrame, m_fam: str, split_type: str, cell_line: str,
                             index_channels: List[str], columns_positions: List[int]) -> pd.DataFrame:
    """
    构造与热图 pivot 同形的显著性数值矩阵 (0=无, 1='.', 2='*', 3='**', 4='***')。
    多个环境/种子下同一特征出现多个星级时，取最高星级。
    """
    rank_matrix = pd.DataFrame(0, index=index_channels, columns=columns_positions, dtype=int)
    if sig_df.empty:
        return rank_matrix

    # 兼容: 旧版未按卷积核拆分的 cnn_importance.md (family='cnn') 同时适用于 cnn33/53/73
    families = {str(m_fam)}
    if str(m_fam).startswith("cnn"):
        families.add("cnn")

    sub = sig_df[
        (sig_df['model_family'].isin(families)) &
        (sig_df['split_type'] == split_type) &
        (sig_df['cell_line'] == cell_line)
    ]
    if sub.empty:
        return rank_matrix

    best = sub.groupby(['channel', 'position'])['significance'].agg(
        lambda s: max(s, key=lambda x: SIG_RANK.get(x, 0))
    ).reset_index()

    for _, r in best.iterrows():
        ch, pos, sym = r['channel'], r['position'], r['significance']
        if ch in rank_matrix.index and pos in rank_matrix.columns:
            rank_matrix.loc[ch, pos] = SIG_RANK.get(sym, 0)
    return rank_matrix


def _draw_single_heatmap(sub_df: pd.DataFrame, title_prefix: str, m_fam: str, output_path: Path,
                         sig_df: pd.DataFrame, split_type: str, cell_line: str):
    pivot = sub_df.pivot_table(index='channel', columns='position', values='importance', aggfunc='mean')
    ordered_channels = [c for c in CHANNELS if c in pivot.index]
    pivot = pivot.reindex(ordered_channels)

    for p in range(1, 24):
        if p not in pivot.columns:
            pivot[p] = 0.0
    pivot = pivot[sorted(pivot.columns)]

    # 显著性掩码：无显著性 (rank=0) 的位点 -> 白色；显著 (>= '.') 保留数值色域颜色。
    # 仅当 feature_importance 显著性数据存在时启用掩码；缺失时保持完整色域。
    sig_rank = _build_significance_rank(
        sig_df=sig_df,
        m_fam=m_fam,
        split_type=split_type,
        cell_line=cell_line,
        index_channels=ordered_channels,
        columns_positions=list(pivot.columns)
    )
    has_sig_info = bool(sig_df is not None and not sig_df.empty and (sig_rank.values > 0).any())
    mask = (sig_rank.values == 0) if has_sig_info else None

    cfg = _metric_cfg(m_fam)

    # 动态计算色阶边界，杜绝单一异常值冲淡全图
    if m_fam == "linear":
        v_max = max(0.35, min(1.0, float(np.nanpercentile(np.abs(pivot.values), 98))))
        v_min = -v_max
        center_val = 0.0
    else:
        # 非线性模型: 下限取 0 (色图低端已截断 -> 低幅值显著格仍可见有色)
        v_min = 0.0
        v_max = max(1e-3, float(np.nanpercentile(pivot.values, 98)))
        center_val = None

    fig, ax = plt.subplots(figsize=(15, 4.8), dpi=300)
    heat_cmap = _make_heatmap_cmap(cfg, m_fam)
    sns.heatmap(
        pivot,
        cmap=heat_cmap,
        center=center_val,
        vmin=v_min,
        vmax=v_max,
        mask=mask,                # 无显著性位点 -> 白色背景；显著位点 -> 数值色域
        ax=ax,
        linewidths=0.8,
        linecolor='white',
        cbar_kws={'label': cfg["metric_name"]}
    )

    if has_sig_info:
        note = " | White cells: no significance | Colored cells: significant (.,*,**,***)"
    else:
        note = " | (no significance data: full color range shown)"
    ax.set_title(f"23nt Position Attribution Heatmap: {title_prefix}{note}",
                 fontsize=10, fontweight='bold', pad=28)
    ax.set_xlabel("sgRNA Target Locus (1 to 20: Protospacer Guide, 21 to 23: PAM)", fontsize=10, labelpad=8)
    ax.set_ylabel("Multimodal Channel", fontsize=10)

    ax.axvline(x=10, color='red', linestyle='--', linewidth=1.5, alpha=0.85)
    ax.axvline(x=20, color='darkred', linestyle='-', linewidth=2.0, alpha=0.95)

    ax.text(5, -0.22, "Non-Seed (1-10nt)", color='dimgray', ha='center', fontsize=9, fontweight='bold')
    ax.text(15, -0.22, "Seed Region (11-20nt)", color='red', ha='center', fontsize=9, fontweight='bold')
    ax.text(21.5, -0.22, "PAM (NGG)", color='darkred', ha='center', fontsize=9, fontweight='bold')

    plt.subplots_adjust(top=0.82, bottom=0.18, left=0.08, right=0.98)
    plt.savefig(output_path, dpi=300)
    plt.close()


# ============================================================
# 3. 生成文件夹 2: 02_env_increment_trees/ (四层环境增量树图)
# ============================================================

def load_metrics_table(batch_dir: Path) -> pd.DataFrame:
    """加载评测指标表 (优先 metrics_tables/all_experiments.csv)。"""
    candidates = [
        batch_dir / "summary" / "metrics_tables" / "all_experiments.csv",
        batch_dir / "summary" / "all_experiments.csv",
    ]
    for fpath in candidates:
        if fpath.exists():
            try:
                df = pd.read_csv(fpath)
                if not df.empty:
                    return df
            except Exception:
                continue

    try:
        from analyse.collect_results import collect_batch
        return collect_batch(batch_dir)
    except Exception:
        pass
    try:
        from collect_results import collect_batch
        return collect_batch(batch_dir)
    except Exception:
        pass
    return pd.DataFrame()


def _filter_valid_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """剔除发散实验 (与 collect_results.filter_valid 同规则)。"""
    if df.empty:
        return df
    work = df.copy()
    for col in ['R2', 'MAE', 'RMSE']:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors='coerce')
    mask = pd.Series(True, index=work.index)
    if 'R2' in work.columns:
        mask &= ~(work['R2'].isna() | (work['R2'].abs() > 10.0))
    if 'MAE' in work.columns:
        mask &= ~(work['MAE'].isna() | (work['MAE'] > 10.0))
    if 'RMSE' in work.columns:
        mask &= ~(work['RMSE'].isna() | (work['RMSE'] > 10.0))
    return work[mask].copy()


def _prepare_tree_metrics(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """按 (split_type, cell_line, model, environment) 求平均 (mixed 多种子合并)。

    保留消融树需要的全部指标: R2 / MAE / RMSE / Pearson / Spearman。
    """
    if metrics_df.empty:
        return pd.DataFrame()

    work = _filter_valid_metrics(metrics_df)
    if work.empty:
        return pd.DataFrame()

    for col in ['model', 'split_type', 'cell_line', 'environment']:
        if col in work.columns:
            work[col] = work[col].astype(str).str.lower().str.strip()

    metric_cols = [c for c in TREE_METRIC_COLS if c in work.columns]
    if 'R2' not in metric_cols:
        return pd.DataFrame()

    agg = work.groupby(['split_type', 'cell_line', 'model', 'environment'], dropna=False)[metric_cols].mean().reset_index()
    return agg


def _demo_tree_metrics() -> pd.DataFrame:
    """指标数据缺失时的演示兜底 (保持引擎零报错)。"""
    rows = []
    base_r2, base_mae, base_rmse = 0.55, 0.142, 0.170
    base_p, base_s = 0.70, 0.68
    inc = {"ctcf": 0.030, "dnase": 0.050, "h3k4me3": 0.020, "rrbs": -0.010}
    combos = [("sequence", [])]
    for r in (1, 2, 3):
        import itertools as _it
        for subset in _it.combinations(["CTCF", "Dnase", "H3K4me3", "RRBS"], r):
            combos.append((f"sequence_{'_'.join(e.lower() for e in sorted(subset))}", list(subset)))
    combos.append(("all", ["CTCF", "Dnase", "H3K4me3", "RRBS"]))
    for env_name, envs in combos:
        dr2 = sum(inc[e.lower()] for e in envs)
        rows.append({
            "split_type": "single", "cell_line": "hct116", "model": "linear",
            "environment": env_name,
            "R2": round(base_r2 + dr2, 5),
            "MAE": round(base_mae - 0.5 * dr2, 5),
            "RMSE": round(base_rmse - 0.6 * dr2, 5),
            "Pearson": round(base_p + 0.8 * dr2, 5),
            "Spearman": round(base_s + 0.7 * dr2, 5),
        })
    return pd.DataFrame(rows)


def combo_name(env_list: List[str]) -> str:
    envs = sorted({str(e).strip().lower() for e in env_list})
    if not envs:
        return "sequence"
    if len(envs) == 4:
        return "all"
    return "sequence_" + "_".join(envs)


# ============================================================
# 去重组合树：节点 = 组合集合 (唯一出现), 路径内环境永不重复
# ============================================================

# ============================================================
# 消融树 (ablation tree): 根 = sequence 基线, 逐层移除一个环境
#   level 0: sequence (基线参考; 只显示实测指标, 无 delta)
#   level 1: ALL (4 环境)      <-- 用户要求 "4环境"
#   level 2: 3 环境组合        <-- "3环境"
#   level 3: 2 环境组合        <-- "2环境"
# 规则:
#   * "同一组合不消融": 每个组合在整棵树中只出现一次;
#     2 环境组合的唯一父节点 = 该组合 ∪ {缺失环境中规范序最靠前者} 所属的 3 环境组合;
#   * 异常节点 (指标缺失 / 发散 / 指标不一致) 即 dup: 不绘制, 且其下整棵子树一并剪除;
#   * 颜色仍只以 dR2 为准; 每个非根节点显示 5 个 delta:
#     dR2 / dMAE / dRMSE / dPearson / dSpearman。
# ============================================================

TREE_METRIC_COLS = ["R2", "MAE", "RMSE", "Pearson", "Spearman"]
ENV_ORDER_LOWER = [e.lower() for e in EPI_CHANNELS]   # ctcf < dnase < h3k4me3 < rrbs


class _ComboTreeNode:
    """消融树节点 (envs = 该节点保留的环境集合; 无 children 即为叶)。"""

    __slots__ = ("envs", "add_env", "removed_env", "depth", "level", "x",
                 "children", "delta", "terminal", "metric", "is_root")

    def __init__(self, envs, add_env=None, removed_env=None, level=0, is_root=False):
        self.envs = list(envs)
        self.add_env = add_env            # 兼容旧字段
        self.removed_env = removed_env    # 本节点相对父节点被移除的环境
        self.depth = len(self.envs)       # 环境个数 (4 / 3 / 2)
        self.level = level                # 绘图层级 (0..3)
        self.x = 0.0
        self.children = []
        self.delta = None                 # dict(dR2, dMAE, dRMSE, dPearson, dSpearman)
        self.terminal = True
        self.metric = None                # np.ndarray: (R2, MAE, RMSE, Pearson, Spearman)
        self.is_root = is_root


def _metric_vector(metric) -> np.ndarray:
    """(R2, MAE, RMSE, Pearson, Spearman) -> float 向量 (缺失补 NaN)。"""
    if metric is None:
        return np.full(len(TREE_METRIC_COLS), np.nan)
    vals = list(metric)[:len(TREE_METRIC_COLS)]
    vals = vals + [np.nan] * (len(TREE_METRIC_COLS) - len(vals))
    return np.asarray(vals, dtype=float)


def _metric_anomaly_reason(metric, thr: float) -> Optional[str]:
    """实测指标异常 (缺失 / 发散 / 越界) -> 原因; 正常返回 None。

    对应研究规范中的 "数据异常 / 参数异常": 发散实验 (|R2|/|RMSE| 超
    consensus.unstable_effect_threshold) 与相关系数越界都不得进入树。
    """
    vec = _metric_vector(metric)
    if not np.isfinite(vec[0]):
        return "R2 missing"
    for i, name in enumerate(TREE_METRIC_COLS):
        v = vec[i]
        if not np.isfinite(v):
            return f"{name} missing"
        if name in ("MAE", "RMSE", "R2") and abs(v) > thr:
            return f"|{name}|={abs(v):.3g} > {thr:g} (diverged / parameter anomaly)"
        if name in ("Pearson", "Spearman") and abs(v) > 1.5:
            return f"|{name}|={abs(v):.3g} > 1.5 (correlation out of range)"
    return None


def _delta_anomaly_reason(delta: Dict[str, float], thr: float) -> Optional[str]:
    """增量异常: 超阈, 或 R2 与 RMSE 同向 (指标不一致 -> 实验异常)。"""
    dr2, drmse = delta.get("dR2", np.nan), delta.get("dRMSE", np.nan)
    for key, v in delta.items():
        if v is not None and np.isfinite(v) and abs(v) > thr:
            return f"|{key}|={abs(v):.3g} > {thr:g} (anomalous increment)"
    if np.isfinite(dr2) and np.isfinite(drmse):
        if dr2 > 0 and drmse > 0:
            return "metric inconsistency: dR2>0 while dRMSE>0"
        if dr2 < 0 and drmse < 0:
            return "metric inconsistency: dR2<0 while dRMSE<0"
    return None


def _make_delta(parent_metric, child_metric) -> Dict[str, float]:
    p, c = _metric_vector(parent_metric), _metric_vector(child_metric)
    d = c - p
    return {"dR2": float(d[0]), "dMAE": float(d[1]), "dRMSE": float(d[2]),
            "dPearson": float(d[3]), "dSpearman": float(d[4])}


def canonical_parent_envs(envs) -> Optional[List[str]]:
    """组合在消融树中的唯一父节点 = 该组合 ∪ {缺失环境中规范序最靠前者}。

    保证 "同一组合不消融" (每个组合只出现一次, 不产生重复分支)。
    """
    envs = [str(e).lower() for e in envs]
    missing = [e for e in ENV_ORDER_LOWER if e not in envs]
    if not missing:
        return None
    keep = set(envs) | {missing[0]}
    return [e for e in ENV_ORDER_LOWER if e in keep]


def _build_ablation_combo_tree(combo_map: Dict[str, tuple], thr: float = 10.0):
    """构建消融树, 返回 (root, pruned, notes)。

    root   : 根节点 (sequence 基线); 无可用数据时 children 为空
    pruned : [(combo, reason)] 被判为异常/dup 而剪除的节点 (其子树一并隐藏)
    notes  : 结构性说明 (如根基线缺失)
    """
    pruned: List[tuple] = []
    notes: List[str] = []
    root = _ComboTreeNode([], level=0, is_root=True)
    root_metric = combo_map.get("sequence")
    if root_metric is None:
        notes.append("sequence baseline missing -> tree not drawn")
        return root, pruned, notes
    root.metric = _metric_vector(root_metric)
    root_reason = _metric_anomaly_reason(root_metric, thr)
    if root_reason is not None:
        notes.append(f"sequence baseline anomalous ({root_reason}) -> tree not drawn")
        return root, pruned, notes

    def add_child(node, child_envs, removed_env):
        combo = combo_name(child_envs)
        metric = combo_map.get(combo)
        if metric is None or not np.isfinite(_metric_vector(metric)[0]):
            pruned.append((combo, "metrics missing for this combination"))
            return None
        own = _metric_anomaly_reason(metric, thr)
        if own is not None:
            pruned.append((combo, f"anomalous experiment: {own}"))
            return None
        delta = _make_delta(node.metric, metric)
        dreason = _delta_anomaly_reason(delta, thr)
        if dreason is not None:
            pruned.append((combo, f"anomalous increment: {dreason}"))
            return None
        child = _ComboTreeNode(child_envs, add_env=removed_env, removed_env=removed_env,
                               level=node.level + 1)
        child.metric = _metric_vector(metric)
        child.delta = delta
        node.children.append(child)
        node.terminal = False
        return child

    # level 1: ALL (4 环境)
    full = add_child(root, list(ENV_ORDER_LOWER), None)
    if full is None:
        return root, pruned, notes

    def expand(node):
        if node.level >= 3 or node.depth <= 2:
            return
        for env in list(node.envs):
            child_envs = [e for e in node.envs if e != env]
            if canonical_parent_envs(child_envs) != list(node.envs):
                continue   # 只保留唯一父节点 -> 同一组合只消融一次
            child = add_child(node, child_envs, env)
            if child is not None:
                expand(child)

    expand(full)
    return root, pruned, notes


def _walk_combo_tree(root: "_ComboTreeNode"):
    """先序遍历消融树 (用于校验/测试)。"""
    nodes = [root]
    for child in root.children:
        nodes.extend(_walk_combo_tree(child))
    return nodes


# 各层节点框宽 (绘制几何); 横向槽距 STEP 须大于最大框宽以保证同层方框不重叠
BOX_W_BY_DEPTH = {0: 2.1, 1: 1.5, 2: 1.5, 3: 1.5}
LAYOUT_STEP = 2.2


def _layout_combo_tree(root: _ComboTreeNode, step: float = LAYOUT_STEP) -> int:
    """
    自上而下对消融树做叶槽布局：
      叶节点占据 [0..n) * step 槽位；内部节点 x = 首末子节点中心 (子节点跨度中点)。
    返回叶节点总数。
    """
    slot_ref = [0]

    def place(node: _ComboTreeNode):
        if node.terminal:
            node.x = float(slot_ref[0]) * step
            slot_ref[0] += 1
            return
        for child in node.children:
            place(child)
        node.x = float(np.mean([c.x for c in node.children]))

    place(root)
    return max(1, slot_ref[0])


def _check_no_box_overlap(root: _ComboTreeNode, step: float = LAYOUT_STEP,
                          box_w_by_depth: Dict[int, float] = BOX_W_BY_DEPTH) -> int:
    """
    校验同层节点方框是否横向重叠 (仅用于测试/调试)。
    返回重叠的节点对数。
    """
    nodes = _walk_combo_tree(root)
    by_level: Dict[int, List[_ComboTreeNode]] = {}
    for n in nodes:
        by_level.setdefault(getattr(n, "level", n.depth), []).append(n)

    overlaps = 0
    for level, group in by_level.items():
        w = box_w_by_depth.get(level, 1.5)
        group_sorted = sorted(group, key=lambda n: n.x)
        for i in range(len(group_sorted) - 1):
            a, b = group_sorted[i], group_sorted[i + 1]
            if (b.x - a.x) < (w / 2 + w / 2):
                overlaps += 1
    return overlaps


def generate_environment_ablation(batch_dir: Path, output_dir: Path):
    """
    Ablation view (辅助视图; 主视图是 Environment Factorial DAG)：
      - 根 = sequence-only 基线实测指标 (R2/MAE/RMSE/Pearson/Spearman);
      - level1 = ALL (4 环境), 显示相对 sequence 的增量;
      - level2/level3 = 依次移除一个环境后的 3 环境 / 2 环境组合,
        显示相对父组合 (多一个环境) 的增量;
      - 每个组合只出现一次;
      - 异常实验对应节点视为 dup: 不绘制, 其下整棵子树一并隐藏。

    科学量: ΔR²_ablation = R²(S) - R²(S\\{e}) (移除效应), 与 additive DAG 的
    ΔR²_{e|S} = R²(S∪{e}) - R²(S) 是**不同的量**, 不得混称 environment contribution。
    每个 (split_type, cell_line, model) 生成一张，以文件名区分。
    """
    _ensure_repo_root_on_path()
    from analyse.config import AnalysisConfig

    output_dir.mkdir(parents=True, exist_ok=True)
    thr = float(AnalysisConfig().consensus.unstable_effect_threshold)

    agg = _prepare_tree_metrics(load_metrics_table(batch_dir))
    if agg.empty:
        print("  [!] 未找到可用评测指标，使用演示数据生成示例树图。")
        agg = _demo_tree_metrics()

    groups = list(agg.groupby(['split_type', 'cell_line', 'model']))
    if not groups:
        print("  [!] 指标表无有效分组，跳过树图生成。")
        return

    saved_count = 0
    total_pruned = 0
    report_rows = []
    for (st, cl, model), sub_df in groups:
        combo_map = {}
        for _, r in sub_df.iterrows():
            combo_map[str(r['environment']).lower()] = tuple(
                pd.to_numeric(r.get(c, np.nan), errors='coerce') for c in TREE_METRIC_COLS)

        root, pruned, notes = _build_ablation_combo_tree(combo_map, thr=thr)
        total_pruned += len(pruned)
        if not root.children:
            why = "; ".join(notes) or "; ".join(f"{c}: {r}" for c, r in pruned) \
                or "no reachable ablation combos"
            print(f"  [-] 跳过 {st}/{cl}/{model}: {why}")
            report_rows.append({"split_type": st, "cell_line": cl, "model": model,
                                "status": "skipped", "n_nodes": 0, "n_pruned": len(pruned),
                                "pruned_nodes": " | ".join(f"{c}: {r}" for c, r in pruned),
                                "note": why})
            continue

        safe = re.sub(r'[^A-Za-z0-9]+', '_', f"tree_{st}_{cl}_{model}").strip('_')
        out_path = output_dir / f"{safe}.png"
        _draw_env_increment_tree(
            root=root,
            pruned=pruned,
            title=f"Ablation Tree (sequence -> ALL -> 3 env -> 2 env) | {st.upper()} | {cl.upper()} | {model}",
            output_path=out_path,
            thr=thr,
        )
        saved_count += 1
        n_nodes = len(_walk_combo_tree(root))
        report_rows.append({"split_type": st, "cell_line": cl, "model": model,
                            "status": "drawn", "n_nodes": n_nodes, "n_pruned": len(pruned),
                            "pruned_nodes": " | ".join(f"{c}: {r}" for c, r in pruned),
                            "note": out_path.name})
        if pruned:
            detail = "; ".join(f"{c} [{reason}]" for c, reason in pruned[:8])
            more = "" if len(pruned) <= 8 else f" (+{len(pruned) - 8} more)"
            print(f"  [!] {st}/{cl}/{model}: 剪除 {len(pruned)} 个异常(dup)节点 -> {detail}{more}")

    # 附带剪枝/跳过原因报告 (便于回溯数据异常导致的缺图)
    if report_rows:
        rep = pd.DataFrame(report_rows)
        rep.to_csv(output_dir / "_ablation_tree_report.csv", index=False)
        lines = [
            "# Ablation Tree Report",
            "",
            "结构: 根 = sequence 基线 → level1 = ALL(4 环境) → level2 = 3 环境 → level3 = 2 环境。",
            "每层相对父组合消融一个环境; 每个组合只出现一次; 异常节点 (缺失/发散/指标不一致) 视为 dup,",
            "不绘制且其下整棵子树一并隐藏。",
            "",
            f"- 生成图: {saved_count} / 分组 {len(report_rows)}; 累计剪除/缺失节点 {total_pruned}",
            f"- 异常阈值: |metric| > {thr:g} (consensus.unstable_effect_threshold) 或 dR2 与 dRMSE 同向",
            "",
            "| split | cell_line | model | status | nodes | pruned | 说明 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for r in report_rows:
            note = (r["pruned_nodes"] or r["note"]).replace("|", "/")
            esc = lambda v: str(v).replace("|", "\\|")  # noqa: E731  (| 会破坏 md 表格)
            lines.append(f"| {esc(r['split_type'])} | {esc(r['cell_line'])} | {esc(r['model'])} | {r['status']} | "
                         f"{r['n_nodes']} | {r['n_pruned']} | {note[:300]} |")
        lines.append("")
        (output_dir / "_ablation_tree_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"  [+] 共生成 {saved_count} 张消融树图 -> {output_dir} (累计剪除异常节点 {total_pruned})")


def _draw_env_increment_tree(root: "_ComboTreeNode", pruned: List[tuple], title: str,
                             output_path: Path, thr: float = 10.0):
    """绘制消融树: 根=sequence 基线, 逐层消融一个环境; 颜色只由 dR2 决定。"""
    STEP = LAYOUT_STEP
    n_terminals = _layout_combo_tree(root, step=STEP)
    n_total = len(_walk_combo_tree(root))

    fig_w = max(12.0, float(n_terminals) * STEP + 6.0)
    fig, ax = plt.subplots(figsize=(fig_w, 12.0), dpi=150)
    ax.axis('off')

    y_level = {0: 4.35, 1: 3.05, 2: 1.75, 3: 0.45}
    box_h = 1.0
    box_w_by_level = {0: 2.1, 1: 1.5, 2: 1.5, 3: 1.5}
    font_by_level = {0: 7.5, 1: 6.3, 2: 5.9, 3: 5.5}

    def draw_node(node: "_ComboTreeNode"):
        x, y = node.x, y_level[node.level]
        box_w = box_w_by_level.get(node.level, 1.5)
        fs = font_by_level.get(node.level, 5.5)

        if node.is_root:
            m = node.metric
            fc = "#f5b041"
            label = ("sequence (baseline)\n"
                     f"R2 {m[0]:.3f}   MAE {m[1]:.3f}\n"
                     f"RMSE {m[2]:.3f}\n"
                     f"Pearson {m[3]:.3f}\n"
                     f"Spearman {m[4]:.3f}")
        else:
            d = node.delta
            if d["dR2"] > 0:
                fc = "#a9dfbf"
            elif d["dR2"] < 0:
                fc = "#f5b7b1"
            else:
                fc = "#f9e79f"
            if node.level == 1:
                head = "ALL 4 envs\n(dR2 vs sequence)"
            else:
                head = f"-{node.removed_env}  ({node.depth} envs)"
            label = (head +
                     f"\ndR2 {d['dR2']:+.3f}\ndMAE {d['dMAE']:+.3f}\ndRMSE {d['dRMSE']:+.3f}"
                     f"\ndP {d['dPearson']:+.3f}\ndS {d['dSpearman']:+.3f}")

        ax.add_patch(plt.Rectangle((x - box_w / 2, y - box_h / 2), box_w, box_h,
                                   facecolor=fc, edgecolor="#34495e", linewidth=0.8, zorder=3))
        ax.text(x, y, label, ha='center', va='center', fontsize=fs, zorder=4)

        for child in node.children:
            ax.plot([x, child.x], [y - box_h / 2, y_level[child.level] + box_h / 2],
                    color="#7f8c8d", linewidth=0.7, zorder=2)
            draw_node(child)

    draw_node(root)

    ax.set_title(title, fontsize=12, fontweight='bold', pad=16)
    ax.text((float(n_terminals) - 1) * STEP / 2.0, 5.15,
            f"Root = sequence baseline; level1 = ALL(4 env); level2 = 3 env; level3 = 2 env; "
            f"color = dR2 sign only; {n_total} unique combos, each ablated once",
            ha='center', fontsize=9, color='#2c3e50')
    ax.text((float(n_terminals) - 1) * STEP / 2.0, 4.95,
            f"dP / dS = Pearson / Spearman delta;  dRMSE < 0 with dR2 > 0 = consistent;  "
            f"{len(pruned)} anomalous (dup) node(s) pruned with subtrees (|metric| > {thr:g} or metric inconsistency)",
            ha='center', fontsize=8, color='#7f8c8d')

    x_right = (float(n_terminals) - 1) * STEP + STEP * 0.7
    ax.set_xlim(-STEP * 0.7, x_right)
    ax.set_ylim(-0.35, 5.35)

    legend_items = [
        ("Root (sequence baseline)", "#f5b041"),
        ("dR2 > 0", "#a9dfbf"),
        ("dR2 < 0", "#f5b7b1"),
        ("dR2 = 0", "#f9e79f"),
    ]
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=c, edgecolor="#34495e") for _, c in legend_items]
    ax.legend(handles, [t for t, _ in legend_items], loc='upper center', bbox_to_anchor=(0.5, -0.01),
              ncol=4, fontsize=8, frameon=False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


# ============================================================
# 4. 生成文件夹 3: 03_epigenetic_comparisons/ (保持不变)
# ============================================================

def generate_epigenetic_comparisons(df_records: pd.DataFrame, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    df_epi = df_records[df_records['channel'].isin(EPI_CHANNELS)].copy()
    if df_epi.empty: return

    palette = {"CTCF": "#1b9e77", "Dnase": "#d95f02", "H3K4me3": "#7570b3", "RRBS": "#e7298a"}

    single_all = df_epi[df_epi['split_type'].isin(['single', 'all'])]
    if not single_all.empty:
        for (st, cl), sub_df in single_all.groupby(['split_type', 'cell_line']):
            _draw_epi_box(sub_df, f"{st.upper()} [{cl.upper()}]", palette, output_dir / f"{st}_{cl}_epi_comparison.png")

    mixed = df_epi[df_epi['split_type'] == 'mixed']
    if not mixed.empty:
        _draw_epi_box(mixed, "MIXED (4-Seed Averaged)", palette, output_dir / "mixed_epi_comparison.png")


def _draw_epi_box(sub_df: pd.DataFrame, title_str: str, palette: Dict, output_path: Path):
    plt.figure(figsize=(7.5, 4.5), dpi=300)
    
    sns.boxplot(
        data=sub_df,
        x='channel',
        y='snr',
        hue='channel',
        palette=palette,
        legend=False,
        width=0.45,
        showmeans=True,
        meanprops={"marker": "o", "markerfacecolor": "white", "markeredgecolor": "black", "markersize": "6"}
    )

    plt.title(f"Epigenetic Factors Robustness (SNR): {title_str}", fontsize=11, fontweight='bold', pad=15)
    plt.xlabel("Epigenetic Channel", fontsize=10)
    plt.ylabel("Attribution Signal-to-Noise Ratio (SNR)", fontsize=10)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


# ============================================================
# 5. 对外统一调度总入口 (API)
# ============================================================

def generate_all_visualizations(batch_dir_str: str, plots_dir_str: Optional[str] = None):
    batch_dir = Path(batch_dir_str)
    plots_root = Path(plots_dir_str) if plots_dir_str else (batch_dir / "summary" / "plots")
    plots_root.mkdir(parents=True, exist_ok=True)

    print(f"\n[*] 启动全景生信绘图引擎 (V5) -> 目标根目录: {plots_root}")

    df_records = load_raw_feature_records(batch_dir)
    sig_df = load_significance_table(batch_dir)

    print(f"  [1/4] 绘制 23nt 位置热图 (无显著性位点白色, 显著位点保留色域) -> plots/01_position_heatmaps/")
    generate_position_heatmaps(df_records, plots_root / "01_position_heatmaps", sig_df=sig_df)

    print(f"  [2/4] 绘制 Environment Factorial DAG (2^4 lattice; 16 nodes / 32 conditional edges; "
          f"颜色 = effect direction, 非显著性) -> plots/03_environment/factorial_dag/")
    try:
        _ensure_repo_root_on_path()
        from analyse.environment.factorial_dag import generate_environment_factorial_dag
        dag_res = generate_environment_factorial_dag(
            batch_dir, figures_dir=plots_root / "03_environment",
            tables_dir=batch_dir / "summary" / "tables",
            summary_dir=batch_dir / "summary")
        print(f"        tables: {Path(dag_res['paths']['nodes']).name}, "
              f"{Path(dag_res['paths']['edges']).name}; "
              f"DAG 图 {len(dag_res['dag_figures'])} 张")
    except Exception as exc:  # noqa: BLE001 - 图失败不阻断其它视图
        print(f"  [!] Factorial DAG 生成失败 (其余视图继续): {exc}")

    print(f"  [3/4] 绘制 Ablation view 树图 (辅助视图: ALL -> 3 -> 2; 与 additive view 不同) "
          f"-> plots/05_ablation/")
    generate_environment_ablation(batch_dir, plots_root / "05_ablation")

    print(f"  [4/4] 绘制 4 类表观因子贡献对比图 (已截断保护) -> plots/03_epigenetic_comparisons/")
    generate_epigenetic_comparisons(df_records, plots_root / "03_epigenetic_comparisons")

    print(f"[🎉] 全部图表已分类保存 (主视图 factorial_dag / 辅助视图 05_ablation)！")


def generate_env_increment_trees(batch_dir: Path, output_dir: Path):
    """Backward-compatible alias -> ablation view (旧名保留, 不再有第二份实现)。

    主视图请用 analyse.environment.factorial_dag.generate_environment_factorial_dag。
    """
    return generate_environment_ablation(batch_dir, output_dir)


def main():
    parser = argparse.ArgumentParser(description="Multi-Model Biological Visualizations for CRISPR sgRNA.")
    parser.add_argument('--results-dir', type=str, default=os.path.join(_REPO_ROOT, 'results'),
                        help='Root results directory (默认: <repo>/results)')
    parser.add_argument('--batch-name', type=str, default='', help='Specific batch folder name')
    parser.add_argument('--batch-dir', type=str, default='', help='Direct path to batch directory')
    parser.add_argument('--output-dir', type=str, default='', help='Custom output directory for plots')
    args = parser.parse_args()

    if args.batch_dir:
        target_batch = Path(args.batch_dir)
    else:
        results_root = Path(args.results_dir)
        if args.batch_name:
            target_batch = results_root / args.batch_name
        else:
            sub_dirs = [d for d in results_root.iterdir() if d.is_dir() and d.name != "summary"]
            target_batch = max(sub_dirs, key=os.path.getmtime) if sub_dirs else results_root

    if not target_batch.exists():
        print(f"[Error] Target directory does not exist: {target_batch}")
        return

    generate_all_visualizations(str(target_batch), args.output_dir if args.output_dir else None)


if __name__ == "__main__":
    main()
