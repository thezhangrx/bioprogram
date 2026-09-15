"""analysis.leakage — canonical sample identity, overlap taxonomy 与 leakage-controlled 评估。

科学定义（本模块是唯一权威来源，其他模块不得各自实现）
----------------------------------------------------
本项目的 split 声明的是 **sequence-level generalization**：
模型要在"没见过的 sgRNA 序列"上给出预测。因此阻止跨 split 分配的 canonical
grouping key 是 **sgRNA 序列本身**（而不是 cell line、不是行号）。

为保守起见，identity class 进一步取 **反向互补同一类**：
`identity(seq) = min(seq, revcomp(seq))`。理由：一个 sgRNA 与其反向互补
靶向同一 locus 的两条链，标签来自同一靶点，属于近重复观测；
实测库内确实存在此类对（跨系 hct116 ∩ rc(hela) = 30、hela ∩ rc(hl60) = 3，
系内 hct116 12 / hek293t 130 / hela 58）。若只按精确序列分组，
`train ∩ rc(test)` 实测非零（mixed 19 条、LOCO 3 条）。

理由（可核验）：
  * 同一 sgRNA 出现在不同 cell line 时，序列通道完全相同，只有表观通道不同；
    若一行进 train、另一行进 test，模型已见过该序列 → 违反 sequence-level 声明。
  * 同一 (sgRNA,label) 跨 cell line 重复（本批 hct116↔hela 2 506 行）是最强形式；
  * 同 locus 反向互补孪生同时被 identity class 吸收；`classify_overlaps`
    仍把 L5 单列，便于报告时区分"精确重复"与"反向互补近重复"。

唯一权威实现的镜像关系：
  * 分析层: `canonical_group_key()`（本文件）
  * 训练层: `src/input_control/cell_line_division.py::sequence_group_ids()`
    训练包必须可独立上传运行，故不 import 本模块，而是**镜像同一规则**；
    两实现的等价性由 `analysis/tests/test_split_code_parity.py` 强制校验。

重叠分类学（不默认等价，禁止 `drop_duplicates(["sgRNA"])` 式粗暴删除）：见 `classify_overlaps`。
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

SEQ_COL_CANDIDATES = ("sgRNA", "sgrna", "sequence", "seq", "target")
LABEL_COL_CANDIDATES = ("Normalized efficacy", "efficacy", "label", "y")


def _pick(df: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        low = str(c).lower()
        if any(k in low for k in ("sgrna", "sequence", "efficacy", "label")):
            return c
    return None


def sequence_key(meta: pd.DataFrame) -> pd.Series:
    """canonical sequence identity（去空格、大写）。"""
    col = _pick(meta, SEQ_COL_CANDIDATES)
    if col is None:
        raise KeyError(f"metadata 中找不到序列列: {list(meta.columns)}")
    return meta[col].astype(str).str.upper().str.strip()


def observation_key(meta: pd.DataFrame, ndigits: int = 6) -> pd.Series:
    """canonical observation identity = (sgRNA, label)（标签按小数位取整以吸收 float32 误差）。"""
    lab = _pick(meta, LABEL_COL_CANDIDATES)
    seq = sequence_key(meta)
    if lab is None:
        return seq
    return seq + "|" + meta[lab].astype(float).round(ndigits).astype(str)


def locus_key(meta: pd.DataFrame) -> Optional[pd.Series]:
    """canonical locus identity = (chromosome, start, end)（若字段存在）。"""
    need = ("Chromosome", "Start", "End")
    if not all(c in meta.columns for c in need):
        return None
    return (meta["Chromosome"].astype(str) + ":" + meta["Start"].astype(int).astype(str)
            + "-" + meta["End"].astype(int).astype(str))


def revcomp(seq: str) -> str:
    return seq.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def canonical_group_key(meta: pd.DataFrame, revcomp_canonical: bool = True) -> pd.Series:
    """跨 split 禁止共享的 canonical identity class（唯一权威定义）。

    = min(sgRNA, revcomp(sgRNA))；与训练层
    `src/input_control/cell_line_division.py::sequence_group_ids` 规则一致。
    """
    seqs = sequence_key(meta)
    if not revcomp_canonical:
        return seqs
    return seqs.map(lambda s: min(s, revcomp(s)))


def classify_overlaps(meta: pd.DataFrame, other: pd.DataFrame, label: str = "") -> Dict[str, object]:
    """对两份 metadata 统计 6 类重叠（count + 是否合法 cross-context observation）。"""
    s1, s2 = sequence_key(meta), sequence_key(other)
    o1, o2 = observation_key(meta), observation_key(other)
    l1, l2 = locus_key(meta), locus_key(other)
    out: Dict[str, object] = {"pair": label, "n_a": int(len(meta)), "n_b": int(len(other))}
    out["L2_same_observation"] = int(len(set(o1) & set(o2)))
    out["L3_same_sequence"] = int(len(set(s1) & set(s2)))
    if l1 is not None and l2 is not None:
        out["L4_same_locus"] = int(len(set(l1) & set(l2)))
        rc = {revcomp(x) for x in set(s2)}
        out["L5_revcomp_pair"] = int(len(set(s1) & rc))
    else:
        out["L4_same_locus"] = None
        out["L5_revcomp_pair"] = None
    return out


def leakage_mask(test_meta: pd.DataFrame, train_meta: pd.DataFrame,
                 group: str = "sequence", ndigits: int = 6) -> np.ndarray:
    """返回 test 中**允许保留**（未被 train 见过）的布尔掩码。

    group="sequence"   : 按 sgRNA 序列屏蔽（推荐；对应 sequence-level 声明）
    group="observation": 仅按 (sgRNA,label) 屏蔽（较宽松，对应 sample-level 声明）
    """
    if group == "observation":
        tr = set(observation_key(train_meta, ndigits))
        te_keys = observation_key(test_meta, ndigits)
    elif group == "sequence":
        # 使用 canonical identity class（含反向互补），与训练层划分规则一致
        tr = set(canonical_group_key(train_meta))
        te_keys = canonical_group_key(test_meta)
    else:
        raise ValueError(f"未知 group: {group}")
    return ~te_keys.isin(tr).to_numpy()


def group_aware_split(indices: np.ndarray, groups: Sequence[str], fractions: Tuple[float, float, float],
                      seed: int = 42) -> Dict[str, np.ndarray]:
    """按 group（默认 sgRNA）整体分配的 train/valid/test 划分。

    保证：同一 group 的全部样本落在同一个 split → 满足 sequence-level 声明。
    """
    uniq = np.array(sorted(set(groups)))
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(uniq))
    n = len(uniq)
    n_tr = int(np.floor(n * fractions[0]))
    n_va = int(np.floor(n * fractions[1]))
    g_tr = set(uniq[perm[:n_tr]])
    g_va = set(uniq[perm[n_tr:n_tr + n_va]])
    g_te = set(uniq[perm[n_tr + n_va:]])
    idx = np.asarray(indices)
    grp = np.asarray(groups)
    return {
        "train": idx[np.isin(grp, list(g_tr))],
        "validation": idx[np.isin(grp, list(g_va))],
        "test": idx[np.isin(grp, list(g_te))],
    }
