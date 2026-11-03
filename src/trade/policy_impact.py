"""政策冲击实验室：政策生效日前/后的可量化影响回溯。

与 scripts/run_policy_impact_lab.py 共用同一套成本模型口径，但面向 API
按单个事件 + 可选品类/市场实时计算，供前端“政策冲击”Tab 使用。
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from src.config import CATEGORY_CATALOG, CATEGORY_PARAMS, MARKETS, TRENDS_LATEST_JSON
from src.trade.cost import LandedCostCalculator, LandedCostInput
from src.trade.policy import (
    BASE_TARIFF_RATE,
    evaluate_policy,
    load_policy_events,
)

DEFAULT_UNIT_PRICE = 28.0
DEFAULT_FX = 7.2
# 判定阈值：高风险直接 No-Go；到岸利润率低于该值按 Conditional 处理。
CONDITIONAL_MARGIN_PCT = 15.0


def _procurement_cost(unit_price: float) -> float:
    return round(unit_price * DEFAULT_FX * 0.35, 2)


def _margin(
    category: str,
    market: str,
    unit_price: float,
    procurement_cny: float,
    alert: Any,
) -> float:
    calculator = LandedCostCalculator()
    adjusted_cost = procurement_cny * (1.0 + alert.cost_adjustment_pct)
    final = calculator.calculate(
        LandedCostInput(
            category=category,
            market=market,
            unit_price_usd=unit_price,
            procurement_cost_cny=adjusted_cost,
            payment_code="pingpong",
            logistics_code="small_parcel",
            tariff_rate=alert.effective_tariff_rate,
            min_duty_usd=alert.min_duty_usd,
        )
    )
    return max(final.margin_pct, -200.0)


def _verdict(risk_level: str, margin_pct: float) -> str:
    if risk_level == "high":
        return "No-Go"
    if margin_pct < CONDITIONAL_MARGIN_PCT:
        return "Conditional"
    return "Go"


def trends_snapshot_status() -> dict[str, Any]:
    """返回趋势快照状态；文件缺失或解析失败时如实标注不可用。"""
    try:
        if not TRENDS_LATEST_JSON.exists():
            raise FileNotFoundError(TRENDS_LATEST_JSON)
        payload = json.loads(TRENDS_LATEST_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "available": False,
            "generated_at": None,
            "provider": None,
            "fallback_used": None,
            "note": "联网信号层未生成，方向对照不可用",
        }
    return {
        "available": True,
        "generated_at": payload.get("generated_at"),
        "provider": payload.get("provider"),
        "fallback_used": bool(payload.get("fallback_used")),
        "note": "趋势快照已生成，仅作方向性对照，不做因果归因",
    }


def build_policy_impact(
    event_code: str,
    category: str | None = None,
    market: str | None = None,
) -> dict[str, Any]:
    """计算指定政策事件生效日前/后各品类的税率、关税、利润与判定。"""
    events = load_policy_events()
    event = next((item for item in events if item.code == event_code), None)
    if event is None:
        raise ValueError(f"未知政策事件：{event_code}")
    target_market = market or event.market
    if target_market not in MARKETS:
        raise ValueError(f"不支持的市场：{target_market}")
    if target_market not in BASE_TARIFF_RATE:
        raise ValueError(f"缺少市场税率基线：{target_market}")

    effective = date.fromisoformat(event.effective_date)
    before_date = (effective - timedelta(days=1)).isoformat()
    after_date = (effective + timedelta(days=1)).isoformat()

    categories = list(CATEGORY_PARAMS)
    if category:
        if category not in CATEGORY_PARAMS:
            raise ValueError(f"不支持的品类：{category}")
        categories = [category]

    rows: list[dict[str, Any]] = []
    for code in categories:
        unit_price = float(CATEGORY_PARAMS[code].get("price") or DEFAULT_UNIT_PRICE)
        procurement_cny = _procurement_cost(unit_price)
        landed = unit_price * BASE_TARIFF_RATE[target_market][code]
        before = evaluate_policy(
            code,
            target_market,
            unit_price,
            landed,
            policy_date=before_date,
            events=[event],
        )
        after = evaluate_policy(
            code,
            target_market,
            unit_price,
            landed,
            policy_date=after_date,
            events=[event],
        )
        margin_before = _margin(code, target_market, unit_price, procurement_cny, before)
        margin_after = _margin(code, target_market, unit_price, procurement_cny, after)
        rows.append(
            {
                "category": code,
                "category_name": CATEGORY_CATALOG[code]["name_cn"],
                "market": target_market,
                "market_name": MARKETS[target_market],
                "unit_price_usd": round(unit_price, 2),
                "tariff_before": before.effective_tariff_rate,
                "tariff_after": after.effective_tariff_rate,
                "duty_before": before.duty_usd_per_unit,
                "duty_after": after.duty_usd_per_unit,
                "cost_increase_before": before.landed_cost_increase_pct,
                "cost_increase_after": after.landed_cost_increase_pct,
                "margin_before": round(margin_before, 2),
                "margin_after": round(margin_after, 2),
                "margin_delta_pct": round(margin_after - margin_before, 2),
                "risk_before": before.risk_level,
                "risk_after": after.risk_level,
                "verdict_before": _verdict(before.risk_level, margin_before),
                "verdict_after": _verdict(after.risk_level, margin_after),
                "affected": bool(
                    after.duty_usd_per_unit != before.duty_usd_per_unit
                    or after.risk_level != before.risk_level
                    or abs(margin_after - margin_before) >= 0.01
                ),
            }
        )

    affected_rows = [row for row in rows if row["affected"]]
    worst = (
        min(affected_rows, key=lambda row: row["margin_delta_pct"])
        if affected_rows
        else None
    )
    return {
        "event_code": event.code,
        "event_title": event.title,
        "event_description": event.description,
        "market": target_market,
        "market_name": MARKETS[target_market],
        "effective_date": event.effective_date,
        "source": event.source,
        "url": event.url,
        "policy_type": event.policy_type,
        "source_type": event.source_type,
        "provider": event.provider,
        "verified": event.verified,
        "published_at": event.published_at,
        "actions": list(event.actions),
        "rate_ad_valorem": event.rate_ad_valorem,
        "min_duty_usd": event.min_duty_usd,
        "trends_status": trends_snapshot_status(),
        "before_date": before_date,
        "after_date": after_date,
        "total_categories": len(rows),
        "affected_count": len(affected_rows),
        "worst": worst,
        "rows": rows,
    }


__all__ = ["CONDITIONAL_MARGIN_PCT", "build_policy_impact", "trends_snapshot_status"]
