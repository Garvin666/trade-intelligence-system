"""统计显著性与 A/B 对照工具：配对检验、效应量与多组事后比较。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as ss

ALPHA = 0.05


def bh_adjust(p_values: Any) -> list[float]:
    """Benjamini-Hochberg 保序 FDR 校正，返回与原输入同顺序的校正后 p 值。

    - 空输入返回空列表；NaN 原样保留。
    - 校正值保证非递减（保序，取尾部累计最小值），并裁剪到 [0, 1]。
    """
    p = np.asarray(p_values, dtype=float)
    if p.size == 0:
        return []
    nan_mask = np.isnan(p)
    finite = p[~nan_mask]
    n = len(finite)
    out = np.full(p.shape, np.nan, dtype=float)
    if n:
        order = np.argsort(finite, kind="stable")
        adjusted = finite[order] * n / np.arange(1, n + 1, dtype=float)
        monotone = np.minimum.accumulate(adjusted[::-1])[::-1]
        result = np.clip(monotone, 0.0, 1.0)
        positions = np.nonzero(~nan_mask)[0]
        out[positions[order]] = result
    return out.tolist()


def paired_significance(
    a: Any,
    b: Any,
    *,
    alpha: float = ALPHA,
    method: str = "auto",
    zero_method: str = "pratt",
) -> dict[str, Any] | None:
    """对两组配对样本做 t 检验或 Wilcoxon，并返回 Cohen's dz 效应量。

    - ``zero_method="pratt"``（默认）在 Wilcoxon 排名中保留零差对而不是直接丢弃，
      避免样本量虚降；``n_zero_diffs`` 记录零差对数量。
    - 全零差 / 零方差等退化情形不抛异常：返回 p=1 并标记 ``degenerate=True``。
    - 保留 ``n`` 键（非 NaN 配对对数）以兼容既有调用方。
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    mask = ~(np.isnan(a) | np.isnan(b))
    a, b = a[mask], b[mask]
    if len(a) < 3:
        return None
    if method == "auto":
        method = "wilcoxon" if len(a) < 30 else "ttest_rel"
    diff = a - b
    std_diff = float(diff.std(ddof=1))
    n_zero_diffs = int(np.count_nonzero(diff == 0))
    degenerate = False
    if method == "wilcoxon":
        if n_zero_diffs == len(diff):
            # scipy 的 wilcox/pratt 在全零差时抛 ValueError，退化按 p=1 处理。
            statistic, p_value = 0.0, 1.0
            degenerate = True
        else:
            statistic, p_value = ss.wilcoxon(a, b, zero_method=zero_method)
    else:
        if std_diff == 0:
            # 零方差时 t 统计量无定义，退化按 p=1 处理。
            statistic, p_value = 0.0, 1.0
            degenerate = True
        else:
            statistic, p_value = ss.ttest_rel(a, b)
    effect_size = float(diff.mean() / std_diff) if std_diff > 0 else 0.0
    return {
        "method": method,
        "statistic": float(statistic),
        "p_value": float(p_value),
        "n": int(len(a)),
        "n_zero_diffs": n_zero_diffs,
        "zero_method": zero_method,
        "degenerate": degenerate,
        "mean_difference": float(diff.mean()),
        "effect_size": effect_size,
        "significant": bool(p_value < alpha),
        "alpha": alpha,
    }


def group_ab_test(
    df: pd.DataFrame,
    group_col: str,
    metric: str,
    *,
    alpha: float = ALPHA,
) -> dict[str, Any] | None:
    """对二值分组做 A/B 检验：Welch t 或 Mann-Whitney U + 合并 Cohen's d。"""
    groups = sorted(df[group_col].dropna().unique().tolist())
    if len(groups) != 2:
        return None
    a = pd.to_numeric(df.loc[df[group_col] == groups[0], metric], errors="coerce").dropna()
    b = pd.to_numeric(df.loc[df[group_col] == groups[1], metric], errors="coerce").dropna()
    if len(a) < 3 or len(b) < 3:
        return None
    if min(len(a), len(b)) < 30:
        method = "mannwhitneyu"
        statistic, p_value = ss.mannwhitneyu(a, b, alternative="two-sided")
    else:
        method = "welch_t"
        statistic, p_value = ss.ttest_ind(a, b, equal_var=False)
    mean_a, mean_b = float(a.mean()), float(b.mean())
    var_a, var_b = float(a.var(ddof=1)), float(b.var(ddof=1))
    pooled = np.sqrt(((len(a) - 1) * var_a + (len(b) - 1) * var_b) / (len(a) + len(b) - 2))
    effect_size = float((mean_a - mean_b) / pooled) if pooled > 0 else 0.0
    return {
        "group_col": group_col,
        "group_a": str(groups[0]),
        "group_b": str(groups[1]),
        "metric": metric,
        "method": method,
        "statistic": float(statistic),
        "p_value": float(p_value),
        "n_a": int(len(a)),
        "n_b": int(len(b)),
        "mean_a": mean_a,
        "mean_b": mean_b,
        "effect_size": effect_size,
        "significant": bool(p_value < alpha),
        "alpha": alpha,
    }


def posthoc_pairwise(
    df: pd.DataFrame,
    group_col: str,
    metric: str,
    *,
    alpha: float = ALPHA,
) -> list[dict[str, Any]]:
    """三组以上时用 scikit-posthocs 做 Dunn 事后比较；库缺失时返回空列表。"""
    groups = sorted(df[group_col].dropna().unique().tolist())
    if len(groups) < 3:
        return []
    try:
        import scikit_posthocs as sp
    except ImportError:
        return []
    result = sp.posthoc_dunn(df, val_col=metric, group_col=group_col, p_adjust="bonferroni")
    rows: list[dict[str, Any]] = []
    for index, left in enumerate(groups):
        for right in groups[index + 1 :]:
            p_value = float(result.loc[left, right])
            rows.append(
                {
                    "group_col": group_col,
                    "metric": metric,
                    "group_a": str(left),
                    "group_b": str(right),
                    "method": "dunn_bonferroni",
                    "p_value": p_value,
                    "significant": bool(p_value < alpha),
                }
            )
    return rows


def run_ab_tests(df: pd.DataFrame) -> list[dict[str, Any]]:
    """自动扫描二值分组列与数值列，输出最多 20 组 A/B 结果。"""
    if df is None or df.empty:
        return []
    group_cols = [
        col
        for col in df.columns
        if df[col].nunique(dropna=True) == 2 and df[col].notna().sum() >= 6
    ]
    metric_cols = [
        col for col in df.select_dtypes(include=[np.number]).columns
    ]
    results: list[dict[str, Any]] = []
    for group_col in group_cols[:5]:
        for metric in metric_cols[:8]:
            if metric == group_col:
                continue
            result = group_ab_test(df, group_col, metric)
            if result:
                results.append(result)
        if metric_cols:
            results.extend(posthoc_pairwise(df, group_col, metric_cols[0])[:5])
    return results[:20]


__all__ = [
    "bh_adjust",
    "group_ab_test",
    "paired_significance",
    "posthoc_pairwise",
    "run_ab_tests",
]
