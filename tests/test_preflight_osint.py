"""卖前体检与尽调模块测试。"""

from __future__ import annotations

from src.trade.decision import build_trade_decision
from src.trade.osint import assess_osint
from src.trade.preflight import build_preflight


def test_preflight_has_groups_and_statuses() -> None:
    result = build_preflight("cn_changsha_mifen", "us")
    assert result.items
    assert result.ready in {True, False}
    assert 0 <= result.score <= 100
    assert {item.status for item in result.items} <= {"pass", "attention", "pending"}
    assert result.to_dict()["items"]


def test_preflight_pricing_status_changes_with_margin() -> None:
    high = build_preflight("cn_changsha_mifen", "us", margin_pct=30.0)
    low = build_preflight("cn_changsha_mifen", "us", margin_pct=5.0)
    pricing = {item.item: item.status for item in high.items}
    pricing_low = {item.item: item.status for item in low.items}
    assert pricing["定价与利润空间"] == "pass"
    assert pricing_low["定价与利润空间"] == "pending"


def test_osint_returns_checks_and_risk() -> None:
    result = assess_osint("cn_changsha_mifen", "us", financing_ready_score=80.0)
    assert len(result.checks) >= 5
    assert result.risk_level in {"low", "medium", "high"}
    assert result.to_dict()["checks"]


def test_osint_uses_real_supplier_rows() -> None:
    result = assess_osint(
        "cn_changsha_mifen",
        "us",
        suppliers={
            "rows": [
                {
                    "supplier_name": "深圳优选供应链",
                    "location": "广东 深圳",
                    "service_years": 8.0,
                    "repeat_rate": 0.72,
                    "response_rate": 0.91,
                    "score": 88.0,
                    "source": "1688_cli",
                    "fallback_used": False,
                }
            ]
        },
    )
    assert any("1688 货源" in check.item for check in result.checks)
    assert any("深圳优选供应链" in check.item for check in result.checks)


def test_trade_decision_includes_new_fields() -> None:
    decision = build_trade_decision(
        category="cn_changsha_mifen",
        market="us",
        unit_price_usd=22.0,
        procurement_cost_cny=55.0,
    )
    assert decision["hs_code"]
    assert decision["hs_description"]
    assert decision["preflight"]["ready"] in {True, False}
    assert decision["osint"]["risk_level"] in {"low", "medium", "high"}
