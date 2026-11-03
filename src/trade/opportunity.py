"""选品机会评分辅助：把贸易成本、合规与证据可信度映射为六维输入。"""

from __future__ import annotations

from typing import Any

from src.config import CATEGORIES, CATEGORY_PARAMS, MARKETS, REAL_PROXY_EVIDENCE_WEIGHT
from src.data.crawler_signals import load_latest_snapshot
from src.trade.compliance import ComplianceAssessor
from src.trade.cost import DEFAULT_FX_RATE, LandedCostCalculator, LandedCostInput
from src.trade.logistics import FreightForecaster
from src.trade.policy import BASE_TARIFF_RATE
from src.trade.preflight import PreflightResult, build_preflight


def estimate_margin(category: str, market: str) -> float:
    """用品类基准价格与演示采购成本估算单件利润率。"""
    price = float(CATEGORY_PARAMS.get(category, {}).get("price", 30.0))
    tariff = BASE_TARIFF_RATE.get(market, {}).get(category, 0.0)
    result = LandedCostCalculator().calculate(
        LandedCostInput(
            category=category,
            market=market,
            unit_price_usd=price,
            procurement_cost_cny=price * DEFAULT_FX_RATE * 0.35,
            tariff_rate=tariff,
        )
    )
    return result.margin_pct


def _evidence_metrics(category: str, market: str, snapshot: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = snapshot or load_latest_snapshot()
    from src.models.real_proxy import proxy_evidence_score

    proxy = proxy_evidence_score(category, market)
    combo = None
    for item in snapshot.get("combos") or []:
        if str(item.get("category") or "").lower() == category and str(
            item.get("market") or ""
        ).lower() == market:
            combo = item
            break
    if combo is None:
        if proxy.get("available"):
            return {
                "score": proxy["score"],
                "level": proxy["level"],
                "note": proxy["note"],
                "missing": False,
                "proxy": proxy,
            }
        return {
            "score": 50.0,
            "level": "neutral",
            "note": "暂无该组合的联网证据，按中性分处理并标记缺失。",
            "missing": True,
            "proxy": proxy,
        }
    trend = float(combo.get("pageview_trend_pct") or 0.0)
    sources = int(combo.get("source_count") or 0)
    fallback = bool(combo.get("fallback_used"))
    if fallback:
        if proxy.get("available"):
            return {
                "score": proxy["score"],
                "level": proxy["level"],
                "note": proxy["note"],
                "missing": False,
                "proxy": proxy,
            }
        return {
            "score": 50.0,
            "level": "neutral",
            "note": "该组合存在模拟回退证据，按中性分处理并标记缺失。",
            "missing": True,
            "proxy": proxy,
        }
    score = max(0.0, min(100.0, 50.0 + trend * 1.2))
    if sources < 2:
        if proxy.get("available"):
            return {
                "score": proxy["score"],
                "level": proxy["level"],
                "note": proxy["note"],
                "missing": False,
                "proxy": proxy,
            }
        return {
            "score": 50.0,
            "level": "neutral",
            "note": f"该组合证据来源仅 {sources} 条，按中性分处理并标记不足。",
            "missing": True,
            "proxy": proxy,
        }
    if proxy.get("available"):
        score = round(
            (1.0 - REAL_PROXY_EVIDENCE_WEIGHT) * score
            + REAL_PROXY_EVIDENCE_WEIGHT * float(proxy["score"]),
            1,
        )
        level = "high" if score >= 70 else ("medium" if score >= 50 else "low")
        return {
            "score": score,
            "level": level,
            "note": (
                f"浏览趋势 {trend:+.1f}%，来源 {sources} 条"
                f"，真实代理 {proxy['score']} 分。"
            ),
            "missing": False,
            "proxy": proxy,
        }
    level = "high" if score >= 70 else ("medium" if score >= 50 else "low")
    return {
        "score": round(score, 1),
        "level": level,
        "note": f"浏览趋势 {trend:+.1f}%，来源 {sources} 条"
        + "，来源充分。",
        "missing": False,
        "proxy": proxy,
    }


def build_opportunity_metrics(
    category: str,
    market: str,
    *,
    crawler_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """返回一个组合的利润、合规、体检与证据输入。"""
    margin = estimate_margin(category, market)
    compliance = ComplianceAssessor().assess(market)
    freight = FreightForecaster().forecast(market)
    preflight: PreflightResult = build_preflight(
        category,
        market,
        margin_pct=margin,
        freight_risk=freight.risk,
        compliance_result=compliance,
    )
    evidence = _evidence_metrics(category, market, crawler_snapshot)
    return {
        "category": category,
        "market": market,
        "margin_pct": margin,
        "compliance_feasibility": compliance.feasibility_score,
        "preflight": preflight.to_dict(),
        "evidence": evidence,
    }


def build_opportunity_lookup(
    *,
    categories: list[str] | None = None,
    markets: list[str] | None = None,
    crawler_snapshot: dict[str, Any] | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    """为全品类/市场组合生成机会评分输入。"""
    snapshot = crawler_snapshot if crawler_snapshot is not None else load_latest_snapshot()
    categories = categories or list(CATEGORIES.keys())
    markets = markets or list(MARKETS.keys())
    return {
        (category, market): build_opportunity_metrics(
            category,
            market,
            crawler_snapshot=snapshot,
        )
        for category in categories
        for market in markets
    }


__all__ = [
    "build_opportunity_lookup",
    "build_opportunity_metrics",
    "estimate_margin",
]
