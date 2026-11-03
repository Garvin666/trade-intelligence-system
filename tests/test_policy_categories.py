"""B1 修复测试：政策事件品类标注与过滤，无关政策不得污染决策。"""

from __future__ import annotations

import pytest

from src.trade.policy import (
    BASE_TARIFF_RATE,
    POLICY_EVENTS,
    PolicyEvent,
    applicable_events_for,
    evaluate_policy,
    load_policy_events,
    _policy_impact_level,
)


def _food_tariff_event() -> PolicyEvent:
    return PolicyEvent(
        code="test-fish-anti-dumping",
        title="越南冷冻鱼片反倾销终裁",
        market="us",
        effective_date="2026-01-01",
        rate_ad_valorem=0.25,
        min_duty_usd=0.0,
        description="测试用：越南冷冻鱼片反倾销",
        source="test",
        actions=("转口",),
        categories=("cn_latiao",),
        verified=True,
    )


def _market_rate_event() -> PolicyEvent:
    return PolicyEvent(
        code="test-market-rate",
        title="市场级税率事件",
        market="us",
        effective_date="2026-01-01",
        rate_ad_valorem=0.10,
        min_duty_usd=0.0,
        description="test",
        source="test",
        actions=(),
        categories=(),
        verified=True,
    )


def test_category_specific_event_only_matches_its_categories() -> None:
    event = _food_tariff_event()
    codes = {e.code for e in applicable_events_for("cn_latiao", "us", "2026-08-01", events=[event])}
    assert "test-fish-anti-dumping" in codes
    assert applicable_events_for("cn_changsha_mifen", "us", "2026-08-01", events=[event]) == []


def test_market_level_event_applies_to_all_categories() -> None:
    events = [_food_tariff_event(), _market_rate_event()]
    codes = {
        e.code
        for e in applicable_events_for("cn_changsha_mifen", "us", "2026-08-01", events=events)
    }
    assert "test-market-rate" in codes
    assert "test-fish-anti-dumping" not in codes


def test_food_sku_us_alert_ignores_unrelated_food_event() -> None:
    events = [POLICY_EVENTS[0], _food_tariff_event()]
    alert = evaluate_policy(
        "cn_changsha_mifen", "us", 30.0, 20.0, policy_date="2026-08-01", events=events
    )
    assert "鱼片" not in alert.message
    assert "test-fish-anti-dumping" not in alert.event_codes
    assert "us-de-minimis-2025" in alert.event_codes


def test_alert_splits_category_and_market_level_events() -> None:
    events = [_food_tariff_event(), POLICY_EVENTS[0]]
    alert = evaluate_policy(
        "cn_latiao", "us", 30.0, 20.0, policy_date="2026-08-01", events=events
    )
    assert "test-fish-anti-dumping" in alert.category_event_codes
    assert "us-de-minimis-2025" in alert.market_level_event_codes
    assert set(alert.event_codes) == {"test-fish-anti-dumping", "us-de-minimis-2025"}


def test_non_numeric_market_event_is_reminder_only() -> None:
    news = PolicyEvent(
        code="test-macro-news",
        title="目标国宏观政策观察",
        market="us",
        effective_date="2026-01-01",
        rate_ad_valorem=0.0,
        min_duty_usd=0.0,
        description="test",
        source="test",
        actions=(),
        categories=(),
        verified=True,
        policy_type="news",
    )
    alert = evaluate_policy(
        "cn_changsha_mifen", "us", 30.0, 20.0, policy_date="2026-08-01", events=[news]
    )
    assert alert.effective_tariff_rate == pytest.approx(BASE_TARIFF_RATE["us"]["cn_changsha_mifen"])
    assert "test-macro-news" not in alert.event_codes
    assert alert.market_level_event_codes == ("test-macro-news",)


def test_real_snapshot_does_not_pollute_food_sku_us() -> None:
    events = load_policy_events()
    assert len(events) >= 2
    alert = evaluate_policy(
        "cn_changsha_mifen", "us", 30.0, 20.0, policy_date="2026-08-16", events=events
    )
    assert "鱼片" not in alert.message
    assert "豆粕" not in alert.message
    assert "钢丝" not in alert.message
    assert alert.effective_tariff_rate > 1.0  # de minimis 市场级税率事件保留


def test_seed_events_are_high_impact() -> None:
    by_code = {event.code: event for event in POLICY_EVENTS}
    assert by_code["us-de-minimis-2025"].impact_level == "high"
    assert by_code["eu-low-value-vat-2026"].impact_level == "high"


def test_unrelated_macro_news_is_downgraded_to_low() -> None:
    item = {
        "title": "EU receives €1.4 billion in revenue from immobilised Russian assets",
        "description": "unrelated macro announcement",
        "policy_type": "compliance",
        "rate_ad_valorem": 0.0,
        "min_duty_usd": 0.0,
        "cost_adjustment_pct": 0.0,
        "categories": [],
    }
    assert _policy_impact_level(item) == "low"


def test_numeric_tariff_event_stays_high() -> None:
    item = {
        "title": "US de minimis removal",
        "description": "120% tariff on low-value parcels",
        "policy_type": "tariff",
        "rate_ad_valorem": 1.20,
        "min_duty_usd": 100.0,
        "cost_adjustment_pct": 0.0,
        "categories": [],
    }
    assert _policy_impact_level(item) == "high"
