"""analysis.stats.bootstrap — Bootstrap CI (仅稳定性证据, 非因果/显著)。


"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

import numpy as np


@dataclass
class BootstrapResult:
    estimate: Optional[float]
    ci_low: Optional[float]
    ci_high: Optional[float]
    bootstrap_std: Optional[float]
    n_iterations: int
    seed: int
    excludes_zero: bool
    available: bool = True       # CI 缺失用 unavailable, 绝不用 0 冒充


def _bootstrap_stats(
    values: np.ndarray,
    estimator: Callable[[np.ndarray], float],
    n_iterations: int,
    seed: int,
    alpha: float,
) -> BootstrapResult:
    rng = np.random.default_rng(seed)
    est = float(estimator(values))
    boot = np.empty(int(n_iterations))
    n = values.size
    for i in range(int(n_iterations)):
        boot[i] = float(estimator(values[rng.integers(0, n, size=n)]))
    lo = float(np.percentile(boot, 100 * alpha / 2))
    hi = float(np.percentile(boot, 100 * (1 - alpha / 2)))
    return BootstrapResult(
        estimate=est,
        ci_low=lo,
        ci_high=hi,
        bootstrap_std=float(np.std(boot, ddof=1)) if n_iterations > 1 else None,
        n_iterations=int(n_iterations),
        seed=int(seed),
        excludes_zero=not (lo <= 0 <= hi),
        available=True,
    )


def bootstrap_ci(
    data: Sequence[float],
    estimator: Callable[[np.ndarray], float],
    n_iterations: int = 2000,
    seed: int = 2024,
    alpha: float = 0.05,
) -> BootstrapResult:
    """对 data 重采样估计 estimator 的 percentile CI (estimator: np.ndarray -> float)。"""
    arr = np.asarray(
        [float(x) for x in data if x is not None and np.isfinite(x)], dtype=np.float64
    )
    if arr.size < 3:
        return BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
    return _bootstrap_stats(arr, estimator, n_iterations, seed, alpha)


def bootstrap_difference_ci(
    baseline: Sequence[float],
    expanded: Sequence[float],
    metric_fn: Callable[[np.ndarray], float],
    n_iterations: int = 2000,
    seed: int = 2024,
    alpha: float = 0.05,
    paired: bool = True,
) -> BootstrapResult:
    """
    环境增量 Δmetric 的 Bootstrap CI (Paired baseline 原则):
      paired=True 时逐对重采样 (metric(b[idx]) - metric(a[idx])); 样本数不等 -> unavailable。
      paired=False 时分别重采样两侧 (仅用于无法配对的探索性分析)。
    结果 = 稳定性/不确定性证据, 不等于统计显著或因果。
    """
    a = np.asarray([float(x) for x in baseline if x is not None and np.isfinite(x)])
    b = np.asarray([float(x) for x in expanded if x is not None and np.isfinite(x)])
    if a.size < 3 or b.size < 3:
        return BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
    if paired and a.size != b.size:
        return BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
    rng = np.random.default_rng(seed)
    est = float(metric_fn(b) - metric_fn(a))
    boot = np.empty(int(n_iterations))
    for i in range(int(n_iterations)):
        if paired:
            idx = rng.integers(0, a.size, size=a.size)
            boot[i] = float(metric_fn(b[idx]) - metric_fn(a[idx]))
        else:
            ai = rng.integers(0, a.size, size=a.size)
            bi = rng.integers(0, b.size, size=b.size)
            boot[i] = float(metric_fn(b[bi]) - metric_fn(a[ai]))
    lo = float(np.percentile(boot, 100 * alpha / 2))
    hi = float(np.percentile(boot, 100 * (1 - alpha / 2)))
    return BootstrapResult(
        estimate=est, ci_low=lo, ci_high=hi,
        bootstrap_std=float(np.std(boot, ddof=1)) if n_iterations > 1 else None,
        n_iterations=int(n_iterations), seed=int(seed),
        excludes_zero=not (lo <= 0 <= hi), available=True,
    )


# ---------------------------------------------------------------------------
# Paired per-sample metric bootstrap (ΔR² / ΔMAE / ΔRMSE on the SAME test samples)
# ---------------------------------------------------------------------------
def metric_r2(pairs: np.ndarray) -> float:
    """pairs: (n, 2) = [y_true, y_pred] -> R² (分母为 0 时 NaN, 不伪造)。"""
    y = np.asarray(pairs)[:, 0]
    p = np.asarray(pairs)[:, 1]
    ss_res = float(np.sum((y - p) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return float("nan") if ss_tot <= 0 else 1.0 - ss_res / ss_tot


def metric_mae(pairs: np.ndarray) -> float:
    arr = np.asarray(pairs)
    return float(np.mean(np.abs(arr[:, 0] - arr[:, 1])))


def metric_rmse(pairs: np.ndarray) -> float:
    arr = np.asarray(pairs)
    return float(np.sqrt(np.mean((arr[:, 0] - arr[:, 1]) ** 2)))


def bootstrap_paired_metric_ci(
    pairs_baseline: np.ndarray,
    pairs_expanded: np.ndarray,
    metric_fn: Callable[[np.ndarray], float],
    n_iterations: int = 2000,
    seed: int = 2024,
    alpha: float = 0.05,
) -> BootstrapResult:
    """Δmetric 的 paired per-sample bootstrap (expanded - baseline)。

    pairs_*: (n, 2) = [y_true, y_pred], **同一 eligible cohort / 同一 test 样本**;
    每次迭代对**同一批样本索引**重采样两侧模型, 因此 Δ 的方差包含样本组成相关性,
    符合 Paired baseline 原则。样本数不等 -> unavailable (绝不悄悄改成非配对)。
    该结果 = 不确定性/稳定性证据, 不是统计显著性, 也不是因果。
    """
    a = np.asarray(pairs_baseline, dtype=np.float64)
    b = np.asarray(pairs_expanded, dtype=np.float64)
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != 2 or b.shape[1] != 2:
        return BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
    if a.shape[0] < 3 or a.shape[0] != b.shape[0]:
        return BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        return BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
    n = a.shape[0]
    rng = np.random.default_rng(seed)
    est = float(metric_fn(b) - metric_fn(a))
    boot = np.empty(int(n_iterations), dtype=np.float64)
    for i in range(int(n_iterations)):
        idx = rng.integers(0, n, size=n)
        boot[i] = float(metric_fn(b[idx]) - metric_fn(a[idx]))
    lo = float(np.percentile(boot, 100 * alpha / 2))
    hi = float(np.percentile(boot, 100 * (1 - alpha / 2)))
    return BootstrapResult(
        estimate=est, ci_low=lo, ci_high=hi,
        bootstrap_std=float(np.std(boot, ddof=1)) if n_iterations > 1 else None,
        n_iterations=int(n_iterations), seed=int(seed),
        excludes_zero=not (lo <= 0 <= hi), available=True,
    )


PAIRED_METRIC_FUNCTIONS: dict = {"R2": metric_r2, "MAE": metric_mae, "RMSE": metric_rmse}


def _metric_from_resamples(y: np.ndarray, p: np.ndarray, metric: str) -> np.ndarray:
    """向量化: y/p 形状 (B, n) -> 每个重采样的 metric 值 (B,)。"""
    if metric == "R2":
        ss_res = np.sum((y - p) ** 2, axis=1)
        ss_tot = np.sum((y - np.mean(y, axis=1, keepdims=True)) ** 2, axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(ss_tot > 0, 1.0 - ss_res / ss_tot, np.nan)
    if metric == "MAE":
        return np.mean(np.abs(y - p), axis=1)
    if metric == "RMSE":
        return np.sqrt(np.mean((y - p) ** 2, axis=1))
    raise ValueError(f"unsupported metric: {metric}")


def bootstrap_paired_metric_ci_fast(
    pairs_baseline: np.ndarray,
    pairs_expanded: np.ndarray,
    metric: str = "R2",
    n_iterations: int = 2000,
    seed: int = 2024,
    alpha: float = 0.05,
) -> BootstrapResult:
    """`bootstrap_paired_metric_ci` 的向量化实现 (相同语义, 用于批量 effect 接线)。

    逐次迭代重采样**同一批样本索引**, Δ = metric(expanded) - metric(baseline)。
    与逐迭代版本在相同 seed 下不保证逐位一致 (随机数消耗方式不同), 但分布等价。
    """
    a = np.asarray(pairs_baseline, dtype=np.float64)
    b = np.asarray(pairs_expanded, dtype=np.float64)
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != 2 or b.shape[1] != 2:
        return BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
    n = a.shape[0]
    if n < 3 or b.shape[0] != n or not (np.isfinite(a).all() and np.isfinite(b).all()):
        return BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(int(n_iterations), n))
    ya, pa = a[idx, 0], a[idx, 1]
    yb, pb = b[idx, 0], b[idx, 1]
    boot = _metric_from_resamples(yb, pb, metric) - _metric_from_resamples(ya, pa, metric)
    boot = boot[np.isfinite(boot)]
    if boot.size == 0:
        return BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
    est = float(_metric_from_resamples(b[None, :, 0], b[None, :, 1], metric)[0]
                - _metric_from_resamples(a[None, :, 0], a[None, :, 1], metric)[0])
    lo = float(np.percentile(boot, 100 * alpha / 2))
    hi = float(np.percentile(boot, 100 * (1 - alpha / 2)))
    return BootstrapResult(
        estimate=est, ci_low=lo, ci_high=hi,
        bootstrap_std=float(np.std(boot, ddof=1)) if boot.size > 1 else None,
        n_iterations=int(n_iterations), seed=int(seed),
        excludes_zero=not (lo <= 0 <= hi), available=True,
    )


# ---------------------------------------------------------------------------
# 高效批量版: 同一 n/seed 复用 multinomial 计数矩阵 (matvec), 一次算全部 metric
# ---------------------------------------------------------------------------
_COUNT_CACHE: dict = {}


def _count_matrix(n: int, n_iterations: int, seed: int) -> np.ndarray:
    """(B, n) multinomial 计数矩阵 (同一 n/seed 复用; 与逐次 index 重采样等价)。"""
    key = (int(n), int(n_iterations), int(seed))
    cached = _COUNT_CACHE.get(key)
    if cached is None:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, n, size=(int(n_iterations), n))
        mat = np.zeros((int(n_iterations), n), dtype=np.float32)
        for i in range(int(n_iterations)):
            mat[i] = np.bincount(idx[i], minlength=n)
        _COUNT_CACHE[key] = mat
        cached = mat
    return cached


def bootstrap_paired_metrics_ci_fast(
    pairs_baseline: np.ndarray,
    pairs_expanded: np.ndarray,
    metrics: Sequence[str] = ("R2", "MAE", "RMSE"),
    n_iterations: int = 2000,
    seed: int = 2024,
    alpha: float = 0.05,
) -> dict:
    """一次重采样同时给出多个 metric 的 paired CI (Δ = expanded - baseline)。

    等价于 `bootstrap_paired_metric_ci_fast`, 但用计数矩阵 matvec 复用同一批重采样,
    批量接线 (~2600 条边) 时快一个数量级。返回 {metric: BootstrapResult}。
    """
    out = {m: BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
           for m in metrics}
    a = np.asarray(pairs_baseline, dtype=np.float64)
    b = np.asarray(pairs_expanded, dtype=np.float64)
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != 2 or b.shape[1] != 2:
        return out
    n = int(a.shape[0])
    if n < 3 or b.shape[0] != n or not (np.isfinite(a).all() and np.isfinite(b).all()):
        return out
    C = _count_matrix(n, int(n_iterations), int(seed))
    nf = float(n)
    ya, pa = a[:, 0], a[:, 1]
    yb, pb = b[:, 0], b[:, 1]
    ea, aea = (ya - pa) ** 2, np.abs(ya - pa)
    eb, aeb = (yb - pb) ** 2, np.abs(yb - pb)
    # 重采样分布用 float32 matvec (只用于 percentile); 点估计仍用 float64 原值
    f32 = lambda v: np.ascontiguousarray(v, dtype=np.float32)  # noqa: E731
    ya32, yb32 = f32(ya), f32(yb)
    sy_a, sy2_a = C @ ya32, C @ f32(ya * ya)
    sy_b, sy2_b = C @ yb32, C @ f32(yb * yb)
    ssr_a, ssr_b = C @ f32(ea), C @ f32(eb)
    sae_a, sae_b = C @ f32(aea), C @ f32(aeb)

    def _summ(boot: np.ndarray, est: float) -> BootstrapResult:
        boot = boot[np.isfinite(boot)]
        if boot.size == 0:
            return BootstrapResult(None, None, None, None, 0, int(seed), False, available=False)
        lo = float(np.percentile(boot, 100 * alpha / 2))
        hi = float(np.percentile(boot, 100 * (1 - alpha / 2)))
        return BootstrapResult(est, lo, hi, float(np.std(boot, ddof=1)),
                               int(n_iterations), int(seed), not (lo <= 0 <= hi), available=True)

    est_r2a = metric_r2(a[None, :, :][0])
    if "R2" in metrics:
        with np.errstate(invalid="ignore", divide="ignore"):
            r2a = 1.0 - ssr_a / (sy2_a - sy_a ** 2 / nf)
            r2b = 1.0 - ssr_b / (sy2_b - sy_b ** 2 / nf)
        out["R2"] = _summ(r2b - r2a, metric_r2(b) - est_r2a)
    if "MAE" in metrics:
        out["MAE"] = _summ(sae_b / nf - sae_a / nf, metric_mae(b) - metric_mae(a))
    if "RMSE" in metrics:
        out["RMSE"] = _summ(np.sqrt(ssr_b / nf) - np.sqrt(ssr_a / nf),
                            metric_rmse(b) - metric_rmse(a))
    return out
