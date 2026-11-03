"""生成演示用合成数据：包含趋势、季节性与品类差异，可完全离线运行。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    CATEGORIES,
    CATEGORY_PARAMS,
    MARKETS,
    MARKET_FACTOR,
    RANDOM_SEED,
    WEEKS_HISTORY,
)
from src.data.daily import latest_data_date


def _sales_base(category: str, market: str, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """生成基础销量指数：市场因子 x 品类基准 x (趋势 + 年季节性 + 品类峰值 + 噪声)。"""
    params = CATEGORY_PARAMS[category]
    market_f = MARKET_FACTOR[market]
    years = t / 52.0

    # 长期温和增长趋势（约 15%/2 年）
    trend = 1.0 + 0.15 * (years / 2.0)

    # 年季节性：12 月附近高点，夏季中低
    season = 1.0 + 0.22 * np.cos(2 * np.pi * years - 0.35)

    # 品类特有峰值：在 peak_month 前后出现一个脉冲
    peak = params["peak_month"]
    pulse = 0.18 * np.exp(-((years * 12 - peak) ** 2) / 18.0)

    # 小趋势波动（市场特有）
    market_wave = 0.05 * np.sin(2 * np.pi * years / 1.7 + 1.3 * len(market))

    noise = 1.0 + rng.normal(0, 0.045, size=t.shape)
    return params["base_sales"] * market_f * trend * (season + pulse + market_wave) * noise


def _search_index(sales: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """搜索热度与销量强相关，叠加自身噪声，映射到 0-100。"""
    raw = 100.0 * (sales / np.max(sales)) ** 0.9
    raw = raw + rng.normal(0, 3.5, size=sales.shape)
    return np.clip(raw, 5, 100)


def _bestseller_rank(sales: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """畅销排名：销量越高排名数字越小（1 为最畅销）。"""
    norm = sales / np.max(sales)
    rank = 12000 * np.exp(-2.2 * norm) + 80
    rank = rank + rng.normal(0, rank * 0.06, size=sales.shape)
    return np.maximum(rank, 1)


def _price_median(category: str, years: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """价格中位数：基准价格 + 缓慢通胀 + 节日小幅上浮。"""
    params = CATEGORY_PARAMS[category]
    price = params["price"] * (1 + 0.06 * years / 2.0)
    price = price * (1 + 0.05 * np.cos(2 * np.pi * years - 0.2))
    price = price + rng.normal(0, params["price"] * 0.015, size=years.shape)
    return np.maximum(price, 1.0)


def _review_growth(sales: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """评论增长率：跟随销量周环比，限制在合理区间。"""
    diff = np.diff(sales, prepend=sales[0])
    growth = diff / np.maximum(sales, 1e-6) * 100.0
    growth = growth + rng.normal(0, 0.8, size=sales.shape)
    return np.clip(growth, -6, 15)


def _export_value(sales: np.ndarray, price: np.ndarray, market: str, rng: np.random.Generator) -> np.ndarray:
    """出口金额（万美元）：销量 x 价格 x 市场换算系数。"""
    factor = {
        "us": 1.0,
        "eu": 1.15,
        "sea": 0.9,
        "jp": 1.05,
        "ca": 0.95,
        "au": 1.0,
        "uk": 1.10,
        "kr": 0.95,
        "de": 1.12,
        "fr": 1.05,
        "vn": 0.85,
        "ru": 1.00,
        "hu": 0.95,
        "ae": 1.05,
        "mx": 0.90,
    }[market]
    value = sales * price * 0.8 * factor
    value = value + rng.normal(0, value * 0.05, size=sales.shape)
    return np.maximum(value, 1.0)


def _competition_index(category: str, years: np.ndarray, market: str, rng: np.random.Generator) -> np.ndarray:
    """竞争度指数：基线 + 市场成熟度趋势 + 季节性小幅波动。"""
    params = CATEGORY_PARAMS[category]
    base = params["competition"]
    maturity = {
        "us": 8.0,
        "eu": 5.0,
        "sea": 2.5,
        "jp": 6.0,
        "ca": 4.0,
        "au": 3.5,
        "uk": 5.0,
        "kr": 7.0,
        "de": 5.5,
        "fr": 5.8,
        "vn": 4.0,
        "ru": 5.5,
        "hu": 6.0,
        "ae": 5.0,
        "mx": 5.8,
    }[market]
    trend = maturity * (years / 2.0)
    wave = 6.0 * np.sin(2 * np.pi * years / 1.3 + 0.7 * len(category))
    noise = rng.normal(0, 2.2, size=years.shape)
    return np.clip(base + trend + wave + noise, 5, 95)


def generate_market_data(
    categories: list[str] | None = None,
    markets: list[str] | None = None,
    weeks: int = WEEKS_HISTORY,
    seed: int = RANDOM_SEED,
    end_date: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """生成演示市场数据。

    Args:
        end_date: 数据截止日，缺省时取当天；最后一个数据点精确落在截止日。

    Returns:
        DataFrame，列为 date/category/market/search_index/bestseller_rank/
        price_median/review_growth/export_value/competition_index/sales_volume。
    """
    categories = categories or list(CATEGORIES.keys())
    markets = markets or list(MARKETS.keys())
    rng = np.random.default_rng(seed)

    rows: list[dict] = []
    end = latest_data_date(end_date) if end_date is None else pd.Timestamp(end_date).normalize()
    dates = pd.date_range(end=end, periods=weeks, freq="7D")

    for category in categories:
        for market in markets:
            t = np.arange(weeks, dtype=float)
            years = t / 52.0
            sales = _sales_base(category, market, t, rng)
            search = _search_index(sales, rng)
            rank = _bestseller_rank(sales, rng)
            price = _price_median(category, years, rng)
            review = _review_growth(sales, rng)
            export = _export_value(sales, price, market, rng)
            competition = _competition_index(category, years, market, rng)

            for i, date in enumerate(dates):
                rows.append(
                    {
                        "date": date.date().isoformat(),
                        "category": category,
                        "market": market,
                        "search_index": round(float(search[i]), 2),
                        "bestseller_rank": round(float(rank[i]), 2),
                        "price_median": round(float(price[i]), 2),
                        "review_growth": round(float(review[i]), 2),
                        "export_value": round(float(export[i]), 2),
                        "competition_index": round(float(competition[i]), 2),
                        "sales_volume": round(float(sales[i]), 2),
                    }
                )

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["category", "market", "date"]).reset_index(drop=True)
