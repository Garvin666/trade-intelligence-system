"""单组合贸易决策计算：供演示报告与 FastAPI 服务复用。"""

from __future__ import annotations

from src.config import CATEGORIES, MARKETS
from src.trade.compliance import ComplianceAssessor
from src.trade.conflict import resolve_trade_conflict
from src.trade.cost import LandedCostCalculator, LandedCostInput, to_row
from src.trade.credit import CreditAssessor
from src.trade.green import GreenAssessor
from src.trade.hs_code import lookup_hs
from src.trade.ip import IpScreener
from src.trade.logistics import FreightForecaster
from src.trade.osint import assess_osint
from src.trade.policy import BASE_TARIFF_RATE, MIN_MARGIN_PCT, evaluate_policy
from src.trade.preflight import build_preflight
from src.trade.sentiment import SentimentAnalyzer


def build_trade_decision(
    category: str,
    market: str,
    unit_price_usd: float,
    procurement_cost_cny: float,
    payment_code: str = "pingpong",
    logistics_code: str = "small_parcel",
    product_name: str | None = None,
) -> dict:
    """计算一个品类 / 市场组合的完整贸易决策结果。"""
    calculator = LandedCostCalculator()
    base = calculator.calculate(
        LandedCostInput(
            category=category,
            market=market,
            unit_price_usd=unit_price_usd,
            procurement_cost_cny=procurement_cost_cny,
            payment_code=payment_code,
            logistics_code=logistics_code,
            tariff_rate=BASE_TARIFF_RATE[market][category],
        )
    )
    alert = evaluate_policy(category, market, unit_price_usd, base.landed_cost_usd)
    adjusted_cost_cny = procurement_cost_cny * (1.0 + alert.cost_adjustment_pct)
    final = calculator.calculate(
        LandedCostInput(
            category=category,
            market=market,
            unit_price_usd=unit_price_usd,
            procurement_cost_cny=adjusted_cost_cny,
            payment_code=payment_code,
            logistics_code=logistics_code,
            tariff_rate=alert.effective_tariff_rate,
            min_duty_usd=alert.min_duty_usd,
        )
    )
    raw_margin_pct = final.margin_pct
    margin_clamped = raw_margin_pct < MIN_MARGIN_PCT
    margin_pct = max(raw_margin_pct, MIN_MARGIN_PCT)
    compliance_result = ComplianceAssessor().assess(market)
    ip_result = IpScreener().screen(category, market, product_name)
    freight = FreightForecaster().forecast(market)
    preflight = build_preflight(
        category,
        market,
        margin_pct=margin_pct,
        freight_risk=freight.risk,
        compliance_result=compliance_result,
    )
    sentiment = SentimentAnalyzer().analyze(market)
    green = GreenAssessor().assess(category, market, unit_price_usd)
    credit = CreditAssessor().assess(
        category,
        market,
        margin_pct=margin_pct,
        policy_risk=alert.risk_level,
        freight_risk=freight.risk,
    )
    osint = assess_osint(
        category,
        market,
        financing_ready_score=credit.financing_ready_score,
    )
    hs = lookup_hs(category, market)
    growth_score = 50.0 + sentiment.avg_score * 50.0
    conflict = resolve_trade_conflict(
        growth_score=growth_score,
        policy_risk=alert.risk_level,
        freight_risk=freight.risk,
        margin_pct=margin_pct,
        feasibility_score=compliance_result.feasibility_score,
        sentiment_score=sentiment.avg_score,
        financing_score=credit.financing_ready_score,
    )
    logistics = calculator.compare_logistics(
        LandedCostInput(
            category=category,
            market=market,
            unit_price_usd=unit_price_usd,
            procurement_cost_cny=adjusted_cost_cny,
            payment_code=payment_code,
            tariff_rate=alert.effective_tariff_rate,
            min_duty_usd=alert.min_duty_usd,
        )
    )
    best = logistics[0]
    warnings = list(alert.warnings)
    if margin_clamped:
        warnings.append(
            f"利润率低于 {MIN_MARGIN_PCT:g}%，已钳制展示值，原始测算值为 {raw_margin_pct:.1f}%。"
        )
    return {
        "category": category,
        "category_name": CATEGORIES[category],
        "market": market,
        "market_name": MARKETS[market],
        "unit_price_usd": unit_price_usd,
        "procurement_cost_cny": procurement_cost_cny,
        "risk_level": alert.risk_level,
        "risk_message": alert.message,
        "actions": list(alert.actions),
        "effective_tariff_rate": alert.effective_tariff_rate,
        "duty_usd_per_unit": alert.duty_usd_per_unit,
        "landed_cost_increase_pct": alert.landed_cost_increase_pct,
        "policy_event_codes": list(alert.event_codes),
        "policy_category_event_codes": list(alert.category_event_codes),
        "policy_market_level_event_codes": list(alert.market_level_event_codes),
        "policy_actions": list(alert.actions),
        "policy_message": alert.message,
        "policy_cost_adjustment_pct": alert.cost_adjustment_pct,
        "policy_heuristic": alert.heuristic,
        "source_quality": alert.source_quality,
        "warnings": warnings,
        "clamped": margin_clamped or alert.clamped,
        "margin_pct": margin_pct,
        "raw_margin_pct": raw_margin_pct,
        "best_logistics": best.logistics.name,
        "best_landed_cost_usd": best.landed_cost_usd,
        "feasibility_score": compliance_result.feasibility_score,
        "compliance_total_usd": compliance_result.total_cost_usd,
        "compliance_recommendation": compliance_result.recommendation,
        "preflight": preflight.to_dict(),
        "hs_code": hs["hs_code"],
        "hs_description": hs["description"],
        "hs_verified": hs["verified"],
        "osint": osint.to_dict(),
        "ip_risk_level": ip_result.risk_level,
        "ip_risk_score": ip_result.risk_score,
        "ip_product_name": ip_result.product_name,
        "ip_matched": [
            {
                "mark": record.mark,
                "kind": record.kind,
                "holder": record.holder,
                "source": record.source,
                "risk": record.risk,
                "note": record.note,
            }
            for record in ip_result.matched_records
        ],
        "ip_recommendation": ip_result.recommendation,
        "freight_risk": freight.risk,
        "freight_trend_pct": freight.trend_pct,
        "freight_index_now": freight.index_now,
        "freight_index_forecast": freight.index_forecast,
        "freight_cost_forecast_cny_per_kg": freight.cost_forecast_cny_per_kg,
        "freight_delivery_days": f"{freight.delivery_days_min}-{freight.delivery_days_max}",
        "freight_note": freight.note,
        "sentiment_avg_score": sentiment.avg_score,
        "sentiment_overall": sentiment.overall,
        "sentiment_recommendation": sentiment.recommendation,
        "sentiment_languages": [
            {
                "language": item.language,
                "language_name": item.language_name,
                "comment_count": item.comment_count,
                "positive": item.positive,
                "negative": item.negative,
                "neutral": item.neutral,
                "score": item.score,
                "label": item.label,
                "trend": item.trend,
                "sample_summary": item.sample_summary,
            }
            for item in sentiment.languages
        ],
        "green_exposure": green.exposure,
        "green_carbon_cost_usd": green.carbon_cost_usd,
        "green_trend": green.trend,
        "green_risk": green.risk,
        "green_recommendation": green.recommendation,
        "credit_data_coverage_score": credit.data_coverage_score,
        "credit_order_stability": credit.order_stability,
        "credit_completion_rate": credit.completion_rate,
        "credit_return_rate": credit.return_rate,
        "credit_policy_risk_score": credit.policy_risk_score,
        "financing_ready_score": credit.financing_ready_score,
        "financing_level": credit.financing_level,
        "credit_recommended_data": list(credit.recommended_data),
        "credit_recommendation": credit.recommendation,
        "conflict_level": conflict.conflict_level,
        "conflict_score_before": conflict.original_score,
        "conflict_score_after": conflict.adjusted_score,
        "conflict_score_change": conflict.score_change,
        "conflict_decision": conflict.decision,
        "conflict_reasons": list(conflict.reasons),
        "conflict_dominant_signals": list(conflict.dominant_signals),
        "conflict_signals": [
            {
                "code": signal.code,
                "name": signal.name,
                "score": signal.score,
                "confidence": signal.confidence,
                "weight": signal.weight,
                "source": signal.source,
            }
            for signal in conflict.signals
        ],
        "fx_sensitivity": final.fx_sensitivity,
        "logistics": [to_row(r) for r in logistics],
    }
