"""跨境贸易决策模块测试：政策风险、到岸成本与市场准入。"""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import CATEGORIES, MARKETS
from src.trade.compliance import ComplianceAssessor
from src.trade.conflict import resolve_trade_conflict
from src.trade.cost import (
    DEFAULT_FX_RATE,
    LOGISTICS_OPTIONS,
    PAYMENT_CHANNELS,
    LandedCostCalculator,
    LandedCostInput,
)
from src.trade.credit import CreditAssessor
from src.trade.green import GreenAssessor
from src.trade.ip import IpScreener
from src.trade.logistics import FreightForecaster
from src.trade.policy import (
    BASE_TARIFF_RATE,
    POLICY_EVENTS,
    active_policy_events,
    evaluate_policy,
)
from src.trade.sentiment import SentimentAnalyzer


def test_active_policy_events_respects_date() -> None:
    assert active_policy_events("2025-01-01", events=POLICY_EVENTS) == []
    codes = {
        event.code
        for event in active_policy_events("2026-08-04", events=POLICY_EVENTS)
    }
    assert {"us-de-minimis-2025", "eu-low-value-vat-2026"} <= codes


def test_us_policy_triggers_high_risk_with_min_duty() -> None:
    alert = evaluate_policy(
        category="cn_latiao",
        market="us",
        unit_price_usd=30.0,
        base_landed_cost_usd=20.0,
        policy_date="2026-08-04",
        events=POLICY_EVENTS,
    )
    assert alert.risk_level == "high"
    assert alert.effective_tariff_rate > 1.0
    assert alert.duty_usd_per_unit == 100.0
    assert alert.landed_cost_increase_pct > 100.0
    assert "转正式清关" in alert.actions


def test_eu_policy_applies_flat_customs_duty() -> None:
    alert = evaluate_policy(
        category="cn_latiao",
        market="eu",
        unit_price_usd=30.0,
        base_landed_cost_usd=18.0,
        policy_date="2026-08-04",
        events=POLICY_EVENTS,
    )
    assert alert.effective_tariff_rate == pytest.approx(BASE_TARIFF_RATE["eu"]["cn_latiao"], abs=1e-4)
    assert alert.duty_usd_per_unit == pytest.approx(3.60, abs=1e-2)
    assert alert.min_duty_usd == pytest.approx(3.60, abs=1e-4)


def test_landed_cost_components_and_margin() -> None:
    calculator = LandedCostCalculator()
    result = calculator.calculate(
        LandedCostInput(
            category="cn_latiao",
            market="sea",
            unit_price_usd=40.0,
            procurement_cost_cny=100.0,
            payment_code="pingpong",
            logistics_code="sea",
            tariff_rate=0.05,
            compliance_cost_usd=1.0,
        )
    )
    assert result.procurement_cost_usd == pytest.approx(100.0 / DEFAULT_FX_RATE, abs=1e-2)
    assert result.payment_fee_usd == pytest.approx(40.0 * PAYMENT_CHANNELS["pingpong"].fee_rate, abs=1e-2)
    assert result.duty_usd == pytest.approx(2.0, abs=1e-2)
    expected_landed = (
        100.0 / DEFAULT_FX_RATE
        + 40.0 * PAYMENT_CHANNELS["pingpong"].fee_rate
        + 2.0
        + LOGISTICS_OPTIONS["sea"].cost_cny_per_item / DEFAULT_FX_RATE
        + 1.0
    )
    assert result.landed_cost_usd == pytest.approx(expected_landed, abs=1e-2)
    assert 0 < result.margin_pct < 100


def test_fx_sensitivity_direction() -> None:
    calculator = LandedCostCalculator()
    result = calculator.calculate(
        LandedCostInput(
            category="cn_latiao",
            market="us",
            unit_price_usd=30.0,
            procurement_cost_cny=80.0,
            payment_code="pingpong",
            logistics_code="small_parcel",
            tariff_rate=BASE_TARIFF_RATE["us"]["cn_latiao"],
        )
    )
    up = result.fx_sensitivity["人民币升值5%"]["利润率%"]
    down = result.fx_sensitivity["人民币贬值5%"]["利润率%"]
    assert up < result.margin_pct < down


def test_compare_logistics_returns_three_options() -> None:
    calculator = LandedCostCalculator()
    results = calculator.compare_logistics(
        LandedCostInput(
            category="cn_latiao",
            market="us",
            unit_price_usd=30.0,
            procurement_cost_cny=80.0,
            tariff_rate=BASE_TARIFF_RATE["us"]["cn_latiao"],
        )
    )
    assert len(results) == len(LOGISTICS_OPTIONS)
    assert results == sorted(results, key=lambda r: r.landed_cost_usd)


def test_compliance_assessor_returns_requirements() -> None:
    result = ComplianceAssessor().assess("eu")
    assert len(result.requirements) >= 3
    assert result.total_cost_usd > 0
    assert 0 <= result.feasibility_score <= 100
    assert result.max_duration_days > 0


def test_ip_screen_default_returns_demo_baseline() -> None:
    result = IpScreener().screen("cn_latiao", "us")
    assert result.risk_level in {"low", "medium", "high"}
    assert len(result.matched_records) > 0
    assert 0 <= result.risk_score <= 100


def test_ip_screen_product_match() -> None:
    result = IpScreener().screen("cn_latiao", "us", "SnapContainer")
    assert result.risk_level == "high"
    assert any(record.mark == "SnapContainer" for record in result.matched_records)


def test_ip_screen_no_match_is_low() -> None:
    result = IpScreener().screen("cn_latiao", "us", "TotallyUniqueProduct")
    assert result.risk_level == "low"
    assert result.matched_records == ()


def test_ip_screen_market_isolation() -> None:
    us = IpScreener().screen("cn_latiao", "us", "SnapContainer")
    eu = IpScreener().screen("cn_latiao", "eu", "SnapContainer")
    assert any(r.mark == "SnapContainer" for r in us.matched_records)
    assert not any(r.mark == "SnapContainer" for r in eu.matched_records)


def test_freight_forecast_returns_lane_for_market() -> None:
    forecast = FreightForecaster().forecast("us")
    assert forecast.lane
    assert forecast.risk in {"low", "medium", "high"}
    assert forecast.index_forecast > 0
    assert forecast.delivery_days_min < forecast.delivery_days_max


def test_freight_forecast_trend_direction() -> None:
    forecaster = FreightForecaster()
    us = forecaster.forecast("us")
    sea = forecaster.forecast("sea")
    assert us.trend_pct > 0
    assert sea.trend_pct < 0


def test_freight_forecast_risk_classification() -> None:
    forecaster = FreightForecaster()
    assert forecaster.forecast("us").risk == "high"
    assert forecaster.forecast("sea").risk == "low"


def test_sentiment_returns_languages_for_market() -> None:
    result = SentimentAnalyzer().analyze("eu")
    assert len(result.languages) == 3
    assert all(-1.0 <= item.score <= 1.0 for item in result.languages)


def test_sentiment_labels_and_trend() -> None:
    us = SentimentAnalyzer().analyze("us")
    assert us.languages[0].label == "positive"
    assert us.languages[0].trend == "rising"

    result = SentimentAnalyzer().analyze("eu")
    by_lang = {item.language: item for item in result.languages}
    assert by_lang["es"].label == "negative"
    assert by_lang["es"].trend == "falling"
    assert by_lang["pt"].label == "neutral"


def test_sentiment_recommendation_mentions_falling_language() -> None:
    result = SentimentAnalyzer().analyze("eu")
    assert "西班牙语" in result.recommendation


def test_green_eu_low_exposure() -> None:
    result = GreenAssessor().assess("cn_latiao", "eu", 40.0)
    assert result.exposure == "low"
    assert result.risk == "low"
    assert result.carbon_cost_usd == 0.0
    assert result.trend == "rising"


def test_green_us_low_risk() -> None:
    result = GreenAssessor().assess("cn_latiao", "us", 40.0)
    assert result.exposure == "low"
    assert result.risk == "low"
    assert result.carbon_cost_usd == 0.0


def test_green_low_exposure_recommendation_mentions_esg() -> None:
    result = GreenAssessor().assess("cn_latiao", "eu", 45.0)
    assert "CBAM" in result.recommendation
    assert "ESG" in result.recommendation


def test_credit_returns_financing_level() -> None:
    result = CreditAssessor().assess(
        "cn_latiao",
        "us",
        margin_pct=30.0,
        policy_risk="low",
        freight_risk="low",
    )
    assert result.financing_level == "可对接供应链金融"
    assert result.financing_ready_score >= 85
    assert 0 <= result.data_coverage_score <= 100
    assert len(result.recommended_data) >= 4


def test_credit_policy_risk_lowers_score() -> None:
    assessor = CreditAssessor()
    low = assessor.assess("cn_latiao", "us", 30.0, policy_risk="low", freight_risk="low").financing_ready_score
    high = assessor.assess("cn_latiao", "us", 30.0, policy_risk="high", freight_risk="low").financing_ready_score
    assert high < low


def test_credit_freight_risk_lowers_score() -> None:
    assessor = CreditAssessor()
    low = assessor.assess("cn_latiao", "us", 30.0, policy_risk="low", freight_risk="low").financing_ready_score
    high = assessor.assess("cn_latiao", "us", 30.0, policy_risk="low", freight_risk="high").financing_ready_score
    assert high < low


def test_credit_low_margin_and_risks_downgrade_level() -> None:
    assessor = CreditAssessor()
    good = assessor.assess("cn_frozen_dumplings", "vn", 30.0, policy_risk="low", freight_risk="low")
    bad = assessor.assess("cn_frozen_dumplings", "vn", 5.0, policy_risk="high", freight_risk="high")
    assert bad.financing_ready_score < good.financing_ready_score
    assert bad.financing_level in {"小额试单", "暂不建议"}


def test_credit_recommendation_mentions_data() -> None:
    result = CreditAssessor().assess("cn_latiao", "eu", 24.0, policy_risk="medium", freight_risk="medium")
    assert "数据" in result.recommendation


def test_conflict_high_risk_shifts_decision() -> None:
    verdict = resolve_trade_conflict(
        growth_score=85.0,
        policy_risk="high",
        freight_risk="high",
        margin_pct=15.0,
        feasibility_score=60.0,
        sentiment_score=0.3,
        financing_score=60.0,
    )
    assert verdict.conflict_level == "high"
    assert verdict.adjusted_score < verdict.original_score
    assert "风险信号置信度更高" in verdict.decision
    assert len(verdict.signals) == 7


def test_conflict_aligned_signals_keeps_decision() -> None:
    verdict = resolve_trade_conflict(
        growth_score=80.0,
        policy_risk="low",
        freight_risk="low",
        margin_pct=30.0,
        feasibility_score=80.0,
        sentiment_score=0.4,
        financing_score=80.0,
    )
    assert verdict.conflict_level == "low"
    assert verdict.decision == "各脑信号方向一致，维持原决策"
    assert verdict.score_change >= -5.0


def test_conflict_reasons_include_confidence_and_weight() -> None:
    verdict = resolve_trade_conflict(
        growth_score=90.0,
        policy_risk="high",
        freight_risk="medium",
        margin_pct=12.0,
        feasibility_score=55.0,
        sentiment_score=0.5,
        financing_score=55.0,
    )
    assert verdict.reasons
    assert any("置信度" in reason and "权重" in reason for reason in verdict.reasons)


def test_trade_report_builds_without_clean_data(tmp_path) -> None:
    from src.trade.report import build_trade_demo_report

    payload = build_trade_demo_report(pd.DataFrame())
    assert payload["summary"]["combos"] == len(CATEGORIES) * len(MARKETS)
    assert len(payload["rows"]) == len(CATEGORIES) * len(MARKETS)
    assert payload["rows"][0]["risk_level"] in {"low", "medium", "high"}
    assert "ip_risk_level" in payload["rows"][0]
    assert "ip_risk_score" in payload["rows"][0]
    assert "ip_recommendation" in payload["rows"][0]
    assert "freight_risk" in payload["rows"][0]
    assert "freight_trend_pct" in payload["rows"][0]
    assert "freight_delivery_days" in payload["rows"][0]
    assert "sentiment_avg_score" in payload["rows"][0]
    assert "sentiment_overall" in payload["rows"][0]
    assert "sentiment_languages" in payload["rows"][0]
    assert "green_exposure" in payload["rows"][0]
    assert "green_carbon_cost_usd" in payload["rows"][0]
    assert "green_recommendation" in payload["rows"][0]
    assert "financing_ready_score" in payload["rows"][0]
    assert "financing_level" in payload["rows"][0]
    assert "credit_recommendation" in payload["rows"][0]
    assert "credit_avg" in payload["summary"]
    assert "conflict_level" in payload["rows"][0]
    assert "conflict_score_after" in payload["rows"][0]
    assert "conflict_decision" in payload["rows"][0]
    assert "conflict_high" in payload["summary"]
