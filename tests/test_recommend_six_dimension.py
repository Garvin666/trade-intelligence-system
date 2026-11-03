"""推荐引擎六维评分与 Go/No-Go 测试。"""

from __future__ import annotations

from src.data.synthetic import generate_market_data
from src.models.advanced import LightGBMAdvanced
from src.models.recommend import RecommendationEngine


def _build_records(weeks: int = 30, seed: int = 7):
    history = generate_market_data(weeks=weeks, seed=seed)
    forecast = LightGBMAdvanced("cn_dried_chili", "us").forecast(history)
    return history, forecast


def test_build_adds_six_dimension_columns() -> None:
    history, forecast = _build_records()
    rec = RecommendationEngine().build(history, forecast)
    for column in (
        "six_dimension_score",
        "verdict",
        "decision_reason",
        "dimension_demand",
        "dimension_trend",
        "dimension_competition",
        "dimension_margin",
        "dimension_compliance",
        "dimension_evidence",
    ):
        assert column in rec.columns
    assert set(rec["verdict"].unique()) <= {"Go", "Conditional", "No-Go"}


def test_verdict_go_requires_high_scores() -> None:
    history, forecast = _build_records()
    opportunity = {
        ("cn_dried_chili", "us"): {
            "margin_pct": 40.0,
            "compliance_feasibility": 90.0,
            "evidence": {"score": 80.0},
            "preflight": {"items": []},
        }
    }
    rec = RecommendationEngine().build(history, forecast, opportunity=opportunity)
    row = rec[(rec["category"] == "cn_dried_chili") & (rec["market"] == "us")].iloc[0]
    assert row["verdict"] in {"Go", "Conditional"}
    assert row["dimension_margin"] >= 70


def test_verdict_no_go_when_dimension_blocks() -> None:
    history, forecast = _build_records()
    opportunity = {
        ("cn_dried_chili", "us"): {
            "margin_pct": -10.0,
            "compliance_feasibility": 20.0,
            "evidence": {"score": 20.0},
            "preflight": {"items": [{"status": "attention", "item": "认证"}]},
        }
    }
    rec = RecommendationEngine().build(history, forecast, opportunity=opportunity)
    row = rec[(rec["category"] == "cn_dried_chili") & (rec["market"] == "us")].iloc[0]
    assert row["verdict"] == "No-Go"
