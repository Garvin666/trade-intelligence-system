"""Keepa 可选源衍生特征（B-2 P0-3）。

从 Keepa 商品历史序列（价格 / offer / salesRankReference）计算五类衍生特征：
  1. price_stability   价格稳定性（1 - 价格变异系数，越高越稳定）
  2. discount_noise    折扣噪声（价格序列波动率，捕捉频繁调价/折扣）
  3. bsr_volatility    BSR 波动（销售排名变异系数）
  4. price_elasticity  价格弹性（价格与 BSR 的相关性，负值=涨价掉排名）
  5. promo_anomaly     异常促销（价格环比骤降事件次数与最大跌幅）

输入为 Keepa product dict 的常见字段（price / offer / salesRankReference 等时间序列，
格式为 [[ts0, v0], [ts1, v1], ...]）。所有函数对缺失/畸形数据容错返回 None，
不抛异常，保证无 Keepa Key 或数据不全时流水线不中断。

Keepa 官方计费为 token 制（估算见 ``estimate_keepa_tokens``，非官方精确费率，
用于单次决策数据成本核算）。
"""

from __future__ import annotations

import math
from typing import Any, Sequence

# 异常促销阈值：单次价格环比跌幅超过该比例视为一次促销事件
PROMO_DROP_THRESHOLD = 0.15
# 弹性相关性需至少 N 个配对点
MIN_ELASTICITY_POINTS = 5
# Keepa token 估算参数（官方按请求维度计费，以下为保守估算）
TOKEN_PRODUCT_FINDER = 1.0
TOKEN_PER_ASIN_STATS180 = 3.0


def _series_values(product: dict[str, Any], key: str) -> list[float]:
    """提取 Keepa 时间序列字段的数值序列（[[ts, v], ...] 或 [v, ...]）。"""
    raw = product.get(key)
    if raw is None:
        return []
    values: list[float] = []
    for entry in raw:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            value = entry[1]
        elif isinstance(entry, (int, float)):
            value = entry
        else:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)
    return values


def _cv(values: Sequence[float]) -> float | None:
    """变异系数（CV）；少于 2 个点或均值为 0 时返回 None。"""
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if mean == 0:
        return None
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    std = math.sqrt(variance)
    return std / abs(mean)


def price_stability(product: dict[str, Any]) -> float | None:
    """价格稳定性 = 1 - 价格 CV（0~1 越接近 1 越稳定）。"""
    cv = _cv(_series_values(product, "price"))
    if cv is None:
        return None
    return round(max(0.0, min(1.0, 1.0 - cv)), 4)


def discount_noise(product: dict[str, Any]) -> float | None:
    """折扣噪声 = 价格序列波动率（CV）；缺失价格返回 None。"""
    cv = _cv(_series_values(product, "price"))
    return round(cv, 4) if cv is not None else None


def bsr_volatility(product: dict[str, Any]) -> float | None:
    """BSR 波动 = salesRankReference 序列 CV。"""
    cv = _cv(_series_values(product, "salesRankReference"))
    return round(cv, 4) if cv is not None else None


def price_elasticity(product: dict[str, Any]) -> float | None:
    """价格弹性 = corr(price, salesRankReference)。

    负值表示涨价伴随排名（数字）上升=排名变差（需求对价格敏感）；
    正值表示涨价反而排名变好（稀缺/高端品）；数据不足返回 None。
    """
    prices = _series_values(product, "price")
    ranks = _series_values(product, "salesRankReference")
    if len(prices) < MIN_ELASTICITY_POINTS or len(ranks) < MIN_ELASTICITY_POINTS:
        return None
    n = min(len(prices), len(ranks))
    prices, ranks = prices[-n:], ranks[-n:]
    mean_p = sum(prices) / n
    mean_r = sum(ranks) / n
    cov = sum((p - mean_p) * (r - mean_r) for p, r in zip(prices, ranks)) / n
    var_p = sum((p - mean_p) ** 2 for p in prices) / n
    var_r = sum((r - mean_r) ** 2 for r in ranks) / n
    if var_p == 0 or var_r == 0:
        return None
    return round(cov / math.sqrt(var_p * var_r), 4)


def promo_anomaly(product: dict[str, Any]) -> dict[str, Any] | None:
    """异常促销：价格环比骤降事件。

    返回 {"events": int, "max_drop_pct": float}；无价格序列返回 None。
    """
    prices = _series_values(product, "price")
    if len(prices) < 2:
        return None
    events = 0
    max_drop = 0.0
    for previous, current in zip(prices, prices[1:]):
        if previous <= 0:
            continue
        drop = (previous - current) / previous
        if drop >= PROMO_DROP_THRESHOLD:
            events += 1
            max_drop = max(max_drop, drop)
    if events == 0:
        return {"events": 0, "max_drop_pct": 0.0}
    return {"events": events, "max_drop_pct": round(max_drop * 100, 2)}


def keepa_features(product: dict[str, Any]) -> dict[str, Any]:
    """聚合五类特征为一行记录；全部缺数据时各项为 None。"""
    promo = promo_anomaly(product)
    return {
        "keepa_price_stability": price_stability(product),
        "keepa_discount_noise": discount_noise(product),
        "keepa_bsr_volatility": bsr_volatility(product),
        "keepa_price_elasticity": price_elasticity(product),
        "keepa_promo_events": promo["events"] if promo else None,
        "keepa_promo_max_drop_pct": promo["max_drop_pct"] if promo else None,
    }


def estimate_keepa_tokens(asins: int, *, stats_days: int = 180) -> dict[str, Any]:
    """单次决策的数据成本估算（Keepa token 制，保守估算，非官方精确费率）。

    成本项：product_finder 请求 + 每个 ASIN 的 product query（token 随 stats 天数
    与 offer 数增长；此处按 stats 窗口线性估算）。
    """
    finder_tokens = TOKEN_PRODUCT_FINDER
    query_tokens = max(0, asins) * TOKEN_PER_ASIN_STATS180 * max(1, stats_days / 180.0)
    total = finder_tokens + query_tokens
    return {
        "product_finder_tokens": round(finder_tokens, 2),
        "product_query_tokens": round(query_tokens, 2),
        "total_tokens_est": round(total, 2),
        "asins": int(asins),
        "stats_days": int(stats_days),
        "note": "Keepa token 估算（非官方精确费率，用于成本核算）",
    }


__all__ = [
    "bsr_volatility",
    "discount_noise",
    "estimate_keepa_tokens",
    "keepa_features",
    "price_elasticity",
    "price_stability",
    "promo_anomaly",
]
