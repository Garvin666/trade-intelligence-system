"""特征工程：生成滞后特征、滚动统计、趋势与季节性特征。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import REAL_FEATURE_COLS, TARGET_COL

FEATURE_COLS = [
    "search_index",
    "bestseller_rank",
    "price_median",
    "review_growth",
    "export_value",
    "competition_index",
    "lag_1",
    "lag_2",
    "lag_4",
    "lag_8",
    "lag_7",
    "lag_14",
    "rolling_mean_4",
    "rolling_mean_7",
    "rolling_mean_8",
    "rolling_std_4",
    "rolling_std_8",
    "ewma_4",
    "growth_rate_1",
    "growth_rate_4",
    "lag_diff_1",
    "lag_diff_4",
    "rolling_min_4",
    "search_trend_4",
    "competition_change_4",
    "price_change_4",
    "month_sin",
    "month_cos",
    "week_sin",
    "week_cos",
] + REAL_FEATURE_COLS


def _build_group_features(group: pd.DataFrame) -> pd.DataFrame:
    """对单个品类/市场组合生成特征。"""
    g = group.sort_values("date").copy()
    for column in REAL_FEATURE_COLS:
        if column not in g.columns:
            g[column] = 0.0
    g["month_sin"] = np.sin(2 * np.pi * g["date"].dt.month / 12)
    g["month_cos"] = np.cos(2 * np.pi * g["date"].dt.month / 12)
    g["week_sin"] = np.sin(2 * np.pi * g["date"].dt.isocalendar().week.astype(float) / 52)
    g["week_cos"] = np.cos(2 * np.pi * g["date"].dt.isocalendar().week.astype(float) / 52)

    g["lag_1"] = g[TARGET_COL].shift(1)
    g["lag_2"] = g[TARGET_COL].shift(2)
    g["lag_4"] = g[TARGET_COL].shift(4)
    g["lag_8"] = g[TARGET_COL].shift(8)
    g["lag_7"] = g[TARGET_COL].shift(7)
    g["lag_14"] = g[TARGET_COL].shift(14)
    g["rolling_mean_4"] = g[TARGET_COL].rolling(4).mean()
    g["rolling_mean_7"] = g[TARGET_COL].rolling(7).mean()
    g["rolling_mean_8"] = g[TARGET_COL].rolling(8).mean()
    g["rolling_std_4"] = g[TARGET_COL].rolling(4).std()
    g["rolling_std_8"] = g[TARGET_COL].rolling(8).std()
    g["ewma_4"] = g[TARGET_COL].ewm(alpha=0.3, adjust=False).mean()
    g["growth_rate_1"] = g[TARGET_COL].pct_change(periods=1) * 100
    g["growth_rate_4"] = g[TARGET_COL].pct_change(periods=4) * 100
    g["lag_diff_1"] = g[TARGET_COL].shift(1) - g[TARGET_COL].shift(2)
    g["lag_diff_4"] = g[TARGET_COL].shift(1) - g[TARGET_COL].shift(5)
    g["rolling_min_4"] = g[TARGET_COL].rolling(4).min()
    g["search_trend_4"] = g["search_index"].pct_change(periods=4) * 100
    g["competition_change_4"] = g["competition_index"].diff(4)
    g["price_change_4"] = g["price_median"].pct_change(periods=4) * 100
    return g


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """为清洗后的市场数据生成特征，返回带特征列的数据。"""
    frames = []
    for (category, market), group in df.groupby(["category", "market"], observed=True):
        frames.append(_build_group_features(group))
    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(["category", "market", "date"]).reset_index(drop=True)


def make_features_for_next_row(
    last_row: pd.Series,
    next_date: pd.Timestamp,
    recent_sales: list[float],
) -> dict:
    """由历史销量序列与最新外部变量构造下一行特征（用于多步滚动预测）。

    recent_sales 按时间从旧到新排列，至少包含 8 个观测。
    外生特征（搜索热度、价格等）未来值未知，使用最近观测延续。
    """
    sales = list(recent_sales)
    lag = {i: sales[-i] if len(sales) >= i else sales[0] for i in (1, 2, 4, 7, 8, 14)}
    rolling4 = float(np.mean(sales[-4:]))
    rolling7 = float(np.mean(sales[-7:]))
    rolling8 = float(np.mean(sales[-8:]))
    rolling_std4 = float(np.std(sales[-4:], ddof=1)) if len(sales) >= 2 else 0.0
    rolling_std8 = float(np.std(sales[-8:], ddof=1)) if len(sales) >= 2 else 0.0
    ewma4 = float(pd.Series(sales).ewm(alpha=0.3, adjust=False).mean().iloc[-1])
    growth1 = (sales[-1] / sales[-2] - 1.0) * 100 if len(sales) >= 2 and sales[-2] else 0.0
    growth4 = (sales[-1] / sales[-5] - 1.0) * 100 if len(sales) >= 5 and sales[-5] else 0.0
    lag_diff_1 = sales[-1] - sales[-2] if len(sales) >= 2 else 0.0
    lag_diff_4 = sales[-1] - sales[-5] if len(sales) >= 5 else 0.0
    rolling_min_4 = float(np.min(sales[-4:]))

    return {
        "search_index": last_row["search_index"],
        "bestseller_rank": last_row["bestseller_rank"],
        "price_median": last_row["price_median"],
        "review_growth": last_row["review_growth"],
        "export_value": last_row["export_value"],
        "competition_index": last_row["competition_index"],
        "lag_1": lag[1],
        "lag_2": lag[2],
        "lag_4": lag[4],
        "lag_8": lag[8],
        "lag_7": lag[7],
        "lag_14": lag[14],
        "rolling_mean_4": rolling4,
        "rolling_mean_7": rolling7,
        "rolling_mean_8": rolling8,
        "rolling_std_4": rolling_std4,
        "rolling_std_8": rolling_std8,
        "ewma_4": ewma4,
        "growth_rate_1": growth1,
        "growth_rate_4": growth4,
        "lag_diff_1": lag_diff_1,
        "lag_diff_4": lag_diff_4,
        "rolling_min_4": rolling_min_4,
        "search_trend_4": last_row["search_trend_4"],
        "competition_change_4": last_row["competition_change_4"],
        "price_change_4": last_row["price_change_4"],
        "month_sin": np.sin(2 * np.pi * next_date.month / 12),
        "month_cos": np.cos(2 * np.pi * next_date.month / 12),
        "week_sin": np.sin(2 * np.pi * next_date.isocalendar().week / 52),
        "week_cos": np.cos(2 * np.pi * next_date.isocalendar().week / 52),
        **{
            column: (
                float(last_row[column])
                if column in last_row.index and pd.notna(last_row[column])
                else 0.0
            )
            for column in REAL_FEATURE_COLS
        },
    }
