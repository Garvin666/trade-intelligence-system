"""关税与贸易政策风险引擎（离线演示版）。

以公开政策事件为基线，对品类 / 市场组合测算政策生效后的关税负担与利润冲击，
输出风险等级与应对建议。真实场景可替换为 CBP / TARIC 政策公告抓取与 NLP 解析。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, Sequence

from src.config import CATEGORY_CATALOG, POLICY_LATEST_JSON

HEURISTIC_IMPACT_RATIO = {"high": 0.10, "medium": 0.05, "low": 0.02}
HEURISTIC_CAP = 0.25
MAX_EFFECTIVE_TARIFF_RATE = 2.0
MIN_MARGIN_PCT = -200.0

# 基础关税（演示口径：品类 × 市场）
from src.trade.policy_models import (  # noqa: E402
    BASE_TARIFF_RATE,
    POLICY_EVENTS,
    PolicyEvent,
)


def _policy_impact_level(item: dict[str, Any]) -> str:
    """Re-grade snapshot events with trade-business semantics before display."""
    from src.data.policy_common import business_impact_level

    def _float(key: str, default: float = 0.0) -> float:
        try:
            return float(item.get(key, default))
        except (TypeError, ValueError):
            return default

    return business_impact_level(
        str(item.get("policy_type") or "macro"),
        _float("rate_ad_valorem"),
        _float("min_duty_usd"),
        _float("cost_adjustment_pct"),
        tuple(str(category) for category in (item.get("categories") or [])),
        f"{item.get('title') or ''} {item.get('description') or ''}",
    )


def _event_from_dict(item: dict[str, Any]) -> PolicyEvent:
    """Build a PolicyEvent from a snapshot dict with tolerant defaults."""

    def _float(key: str, default: float = 0.0) -> float:
        try:
            return float(item.get(key, default))
        except (TypeError, ValueError):
            return default

    def _tuple(key: str) -> tuple[str, ...]:
        value = item.get(key) or []
        if isinstance(value, str):
            value = [value]
        return tuple(str(entry) for entry in value)

    return PolicyEvent(
        code=str(item.get("code") or ""),
        title=str(item.get("title") or ""),
        market=str(item.get("market") or ""),
        effective_date=str(item.get("effective_date") or ""),
        rate_ad_valorem=_float("rate_ad_valorem"),
        min_duty_usd=_float("min_duty_usd"),
        description=str(item.get("description") or ""),
        source=str(item.get("source") or ""),
        actions=_tuple("actions"),
        region=str(item.get("region") or "foreign"),
        policy_type=str(item.get("policy_type") or "tariff"),
        categories=tuple(str(category) for category in (item.get("categories") or [])),
        cost_adjustment_pct=_float("cost_adjustment_pct"),
        impact_level=_policy_impact_level(item),
        direction=str(item.get("direction") or "restrict"),
        url=str(item.get("url") or ""),
        heuristic=bool(item.get("heuristic")),
        verified=bool(item.get("verified")),
        published_at=str(item.get("published_at") or ""),
        provider=str(item.get("provider") or ""),
        source_type=str(item.get("source_type") or "search"),
    )


# 已知品类特定事件的品类兜底标注：快照刷新若丢失 categories，
# 仍能按品类过滤，避免无关反倾销/关税事件污染其他品类决策。
# 非食品领域的事件（风力发电塔 / 木制家具 / 多晶硅）不属于食品业务，
# 统一打 NON_FOOD_SECTOR 标记：它不对应任何食品 SKU，因此对所有食品 SKU 都不生效；
# 同时保留「非空 categories」，避免被当成市场级税率事件把无关反倾销税加到食品成本上。
NON_FOOD_SECTOR = "non_food_sector"

KNOWN_EVENT_CATEGORIES: dict[str, tuple[str, ...]] = {
    "pol-3950d4a0289b": ("intl_salmon_fillet",),  # 越南冷冻鱼片反倾销
    "pol-6aacd5ba3dbe": ("intl_firm_tofu",),  # 印度大豆粕反倾销（豆制品）
    "pol-f1d429cde72d": (NON_FOOD_SECTOR,),  # 印尼风力发电塔反倾销（非食品）
    "pol-6e110edc4615": (NON_FOOD_SECTOR,),  # 中国木制卧室家具反倾销（非食品）
    "pol-d2661f7b933e": (NON_FOOD_SECTOR,),  # 美国多晶硅及衍生品进口调整（非食品）
}


def load_policy_events() -> list[PolicyEvent]:
    """Merge the built-in baseline events with the latest online snapshot."""
    baseline = list(POLICY_EVENTS)
    try:
        if not POLICY_LATEST_JSON.exists():
            return baseline
        payload = json.loads(POLICY_LATEST_JSON.read_text(encoding="utf-8"))
        dynamic = [
            _event_from_dict(item)
            for item in payload.get("events", [])
            if bool(item.get("verified"))
        ]
    except (OSError, json.JSONDecodeError, TypeError):
        return baseline
    seen = {event.code for event in baseline if event.code}
    merged = list(baseline)
    for event in dynamic:
        if event.code in seen:
            continue
        if event.code:
            seen.add(event.code)
        if event.code in KNOWN_EVENT_CATEGORIES and not event.categories:
            event = replace(event, categories=KNOWN_EVENT_CATEGORIES[event.code])
        merged.append(event)
    return merged


@dataclass(frozen=True)
class PolicyAlert:
    category: str
    market: str
    event: PolicyEvent | None
    base_tariff_rate: float
    effective_tariff_rate: float
    min_duty_usd: float
    duty_usd_per_unit: float
    landed_cost_increase_pct: float
    risk_level: str
    actions: tuple[str, ...]
    message: str
    event_codes: tuple[str, ...] = ()
    cost_adjustment_pct: float = 0.0
    heuristic: bool = False
    warnings: tuple[str, ...] = ()
    source_quality: str = "official"
    clamped: bool = False
    category_event_codes: tuple[str, ...] = ()
    market_level_event_codes: tuple[str, ...] = ()


def _parse_date(value: str | date | datetime | None, default: date | None = None) -> date:
    if value is None:
        return default or date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def active_policy_events(
    policy_date: str | date | datetime | None = None,
    events: Sequence[PolicyEvent] | None = None,
) -> list[PolicyEvent]:
    """返回截至 policy_date 已生效的政策事件。"""
    as_date = _parse_date(policy_date)
    source = list(events) if events is not None else load_policy_events()
    return [event for event in source if _parse_date(event.effective_date) <= as_date]


def active_events_for_market(
    market: str,
    policy_date: str | date | datetime | None = None,
    events: Sequence[PolicyEvent] | None = None,
) -> list[PolicyEvent]:
    as_date = _parse_date(policy_date)
    source = list(events) if events is not None else load_policy_events()
    return [
        event
        for event in source
        if event.market == market and _parse_date(event.effective_date) <= as_date
    ]


def applicable_events_for(
    category: str,
    market: str,
    policy_date: str | date | datetime | None = None,
    events: Sequence[PolicyEvent] | None = None,
) -> list[PolicyEvent]:
    """返回对指定品类 / 市场生效的政策事件（含国内与全球政策）。"""
    as_date = _parse_date(policy_date)
    source = list(events) if events is not None else load_policy_events()
    result: list[PolicyEvent] = []
    for event in source:
        if _parse_date(event.effective_date) > as_date:
            continue
        if event.categories and category not in event.categories:
            continue
        if event.region in ("domestic", "global"):
            result.append(event)
        elif event.market == market:
            result.append(event)
    return result


def risk_level_for_increase(increase_pct: float) -> str:
    if increase_pct >= 15.0:
        return "high"
    if increase_pct >= 8.0:
        return "medium"
    return "low"


def evaluate_policy(
    category: str,
    market: str,
    unit_price_usd: float,
    base_landed_cost_usd: float,
    policy_date: str | date | datetime | None = None,
    events: Sequence[PolicyEvent] | None = None,
) -> PolicyAlert:
    """测算政策影响并生成预警。"""
    base_rate = BASE_TARIFF_RATE[market][category]
    active = applicable_events_for(category, market, policy_date, events)
    old_duty = unit_price_usd * base_rate

    if not active:
        return PolicyAlert(
            category=category,
            market=market,
            event=None,
            base_tariff_rate=base_rate,
            effective_tariff_rate=base_rate,
            min_duty_usd=0.0,
            duty_usd_per_unit=round(old_duty, 2),
            landed_cost_increase_pct=0.0,
            risk_level="low",
            actions=("维持现有渠道", "持续监控政策公告"),
            message="当前无新增政策冲击，保持现有清关与物流渠道即可。",
        )

    # 品类特定事件（标注了 categories）只影响匹配品类；
    # categories 为空的事件为市场级事件：有数值（税率/最低税额/成本调整）的
    # 视为市场级税率事件参与重算（如 de minimis、欧盟低值包裹临时固定关税、国内退税），
    # 无数值的宏观/制度事件仅作市场级提醒，不进入核心结论与税率重算。
    category_events = [event for event in active if event.categories]
    market_level_events = [event for event in active if not event.categories]
    market_level_rate_or_cost = [
        event
        for event in market_level_events
        if event.verified
        and (
            event.rate_ad_valorem > 0
            or event.min_duty_usd > 0
            or abs(event.cost_adjustment_pct) > 1e-9
        )
    ]
    core_events = category_events + market_level_rate_or_cost
    warnings: list[str] = []
    market_reminder_events = [
        event for event in market_level_events if event not in market_level_rate_or_cost
    ]
    if market_reminder_events:
        market_titles = "；".join(event.title for event in market_reminder_events)
        warnings.append(
            f"另监测到 {len(market_reminder_events)} 条市场级政策动态（{market_titles}），"
            "与本品类无直接数值关联，仅供参考，未计入税率测算。"
        )

    rate_events = [
        event
        for event in core_events
        if event.verified
        and (event.rate_ad_valorem > 0 or event.min_duty_usd > 0)
    ]
    unverified_rate_events = [
        event
        for event in core_events
        if not event.verified
        and (event.rate_ad_valorem > 0 or event.min_duty_usd > 0)
    ]
    cost_events = [
        event
        for event in core_events
        if event.verified and abs(event.cost_adjustment_pct) > 1e-9
    ]
    heuristic_events = [
        event
        for event in core_events
        if event.heuristic
        and event.policy_type in ("macro", "news")
    ]

    clamped = False
    if rate_events:
        new_rate = min(
            base_rate + sum(event.rate_ad_valorem for event in rate_events),
            MAX_EFFECTIVE_TARIFF_RATE,
        )
        if (
            base_rate + sum(event.rate_ad_valorem for event in rate_events)
            > MAX_EFFECTIVE_TARIFF_RATE
        ):
            clamped = True
            warnings.append(f"有效税率超过上限 {MAX_EFFECTIVE_TARIFF_RATE:.0%}，已钳制并标注。")
        min_duty = max(event.min_duty_usd for event in rate_events)
        new_duty = max(unit_price_usd * new_rate, min_duty)
    else:
        new_rate = base_rate
        min_duty = 0.0
        new_duty = old_duty
    duty_increase_pct = (
        (new_duty - old_duty) / max(base_landed_cost_usd, 1.0) * 100.0
    )

    numeric_cost_adj = sum(event.cost_adjustment_pct for event in cost_events)
    heuristic_cost_adj = 0.0
    for event in heuristic_events:
        ratio = HEURISTIC_IMPACT_RATIO.get(event.impact_level, 0.02)
        if event.direction == "facilitate":
            ratio = -ratio
        heuristic_cost_adj += ratio
    heuristic_cost_adj = max(
        -HEURISTIC_CAP, min(HEURISTIC_CAP, heuristic_cost_adj)
    )
    total_cost_adj = numeric_cost_adj + heuristic_cost_adj
    combined_increase = duty_increase_pct + total_cost_adj * 100.0
    risk = risk_level_for_increase(max(combined_increase, 0.0))

    joined_actions: list[str] = []
    for event in core_events:
        for action in event.actions:
            if action not in joined_actions:
                joined_actions.append(action)
    if not joined_actions:
        joined_actions = ["持续监控政策公告"]

    titles = "；".join(event.title for event in core_events)
    parts: list[str] = []
    if titles:
        parts.append(f"{titles}已生效")
    else:
        parts.append("暂无与本品类直接相关的数值政策事件")
    if rate_events:
        parts.append(f"有效税率从 {base_rate:.0%} 升至 {new_rate:.0%}")
    parts.append(f"单件关税约 ${new_duty:.2f}")
    if abs(total_cost_adj) > 1e-9:
        parts.append(f"出口成本影响 {total_cost_adj:+.1%}")
    if heuristic_events:
        parts.append("无数值政策按影响等级启发式估算")
        warnings.append("存在启发式政策估算，结果仅供演示，不视为官方税率。")
    if unverified_rate_events:
        warnings.append(
            f"跳过 {len(unverified_rate_events)} 条未核验数值政策事件，未叠加其税率。"
        )
    parts.append(f"到岸成本变化 {combined_increase:+.1f}%")
    message = (
        "，".join(parts) + "。"
    )
    return PolicyAlert(
        category=category,
        market=market,
        event=active[0] if len(active) == 1 else None,
        base_tariff_rate=base_rate,
        effective_tariff_rate=round(new_rate, 4),
        min_duty_usd=min_duty,
        duty_usd_per_unit=round(new_duty, 2),
        landed_cost_increase_pct=round(combined_increase, 2),
        risk_level=risk,
        actions=tuple(joined_actions),
        message=message,
        event_codes=tuple(event.code for event in core_events),
        cost_adjustment_pct=round(total_cost_adj, 4),
        heuristic=bool(heuristic_events),
        warnings=tuple(warnings),
        source_quality=(
            "official"
            if not heuristic_events and not unverified_rate_events
            else "official+heuristic"
            if not heuristic_events
            else "heuristic"
        ),
        clamped=clamped,
        category_event_codes=tuple(event.code for event in category_events),
        market_level_event_codes=tuple(event.code for event in market_level_events),
    )


def policy_watchlist(policy_date: str | date | datetime | None = None) -> list[dict]:
    """输出待监控政策事件（用于报告）。"""
    return [
        {
            "code": event.code,
            "title": event.title,
            "market": event.market,
            "region": event.region,
            "policy_type": event.policy_type,
            "effective_date": event.effective_date,
            "description": event.description,
            "source": event.source,
            "url": event.url,
            "actions": list(event.actions),
            "categories": list(event.categories),
            "rate_ad_valorem": event.rate_ad_valorem,
            "min_duty_usd": event.min_duty_usd,
            "cost_adjustment_pct": event.cost_adjustment_pct,
            "impact_level": event.impact_level,
            "direction": event.direction,
            "heuristic": event.heuristic,
            "verified": event.verified,
            "published_at": event.published_at,
            "provider": event.provider,
            "source_type": event.source_type,
        }
        for event in active_policy_events(policy_date)
    ]
