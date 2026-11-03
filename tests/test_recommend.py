"""推荐引擎测试。"""

from __future__ import annotations

import pandas as pd

from src.config import CATEGORIES, MARKETS
from src.data.synthetic import generate_market_data
from src.models.advanced import LightGBMAdvanced
from src.models.recommend import RecommendationEngine, select_best_model_forecast


def test_recommendation_ranking() -> None:
    df = generate_market_data(weeks=80, seed=3)
    fc = LightGBMAdvanced("cn_latiao", "us").forecast(df)
    frames = []
    for (category, market), _ in df.groupby(["category", "market"], observed=True):
        model = LightGBMAdvanced(category, market)
        frames.append(model.forecast(df))
    forecast = pd.concat(frames, ignore_index=True)

    engine = RecommendationEngine()
    rec = engine.build(df, forecast)
    assert len(rec) == len(CATEGORIES) * len(MARKETS)
    verdict_order = rec["verdict"].map({"Go": 0, "Conditional": 1, "No-Go": 2})
    assert verdict_order.is_monotonic_increasing
    for _verdict, group in rec.groupby("verdict", observed=True):
        assert group["six_dimension_score"].is_monotonic_decreasing
    assert (rec["rank"] == range(1, len(rec) + 1)).all()
    assert rec["reasons"].str.len().gt(0).all()


def test_top_n() -> None:
    df = generate_market_data(weeks=60, seed=5)
    forecast = LightGBMAdvanced("cn_latiao", "us").forecast(df)
    rec = RecommendationEngine().top_n(df, forecast, n=3)
    assert len(rec) == 3
    assert rec["rank"].tolist() == [1, 2, 3]


def test_select_best_model_forecast_picks_lower_mape_per_combo() -> None:
    baseline_fc = pd.DataFrame(
        [
            {
                "date": "2026-09-01",
                "category": "cn_latiao",
                "market": "us",
                "model": "prophet_baseline",
                "yhat": 10,
                "yhat_lower": 9,
                "yhat_upper": 11,
            },
            {
                "date": "2026-09-01",
                "category": "cn_changsha_mifen",
                "market": "us",
                "model": "prophet_baseline",
                "yhat": 20,
                "yhat_lower": 18,
                "yhat_upper": 22,
            },
        ]
    )
    advanced_fc = pd.DataFrame(
        [
            {
                "date": "2026-09-01",
                "category": "cn_latiao",
                "market": "us",
                "model": "lightgbm_advanced",
                "yhat": 12,
                "yhat_lower": 11,
                "yhat_upper": 13,
            },
            {
                "date": "2026-09-01",
                "category": "cn_changsha_mifen",
                "market": "us",
                "model": "lightgbm_advanced",
                "yhat": 19,
                "yhat_lower": 18,
                "yhat_upper": 20,
            },
        ]
    )
    baseline_metrics = [
        {"category": "cn_latiao", "market": "us", "model": "prophet_baseline", "mape": 2.0, "mae": 1.0},
        {"category": "cn_changsha_mifen", "market": "us", "model": "prophet_baseline", "mape": 4.0, "mae": 1.0},
    ]
    advanced_metrics = [
        {"category": "cn_latiao", "market": "us", "model": "lightgbm_advanced", "mape": 3.0, "mae": 1.0},
        {"category": "cn_changsha_mifen", "market": "us", "model": "lightgbm_advanced", "mape": 2.0, "mae": 1.0},
    ]

    best = select_best_model_forecast(
        baseline_fc,
        advanced_fc,
        baseline_metrics,
        advanced_metrics,
    )
    picked = best.set_index(["category", "market"])["model"].to_dict()
    assert picked == {
        ("cn_latiao", "us"): "prophet_baseline",
        ("cn_changsha_mifen", "us"): "lightgbm_advanced",
    }
    assert len(best) == len(baseline_fc)


def test_select_best_model_forecast_falls_back_to_advanced() -> None:
    baseline_fc = pd.DataFrame(
        [
            {
                "date": "2026-09-01",
                "category": "cn_latiao",
                "market": "us",
                "model": "prophet_baseline",
                "yhat": 10,
                "yhat_lower": 9,
                "yhat_upper": 11,
            }
        ]
    )
    advanced_fc = pd.DataFrame(
        [
            {
                "date": "2026-09-01",
                "category": "cn_latiao",
                "market": "us",
                "model": "lightgbm_advanced",
                "yhat": 12,
                "yhat_lower": 11,
                "yhat_upper": 13,
            }
        ]
    )
    best = select_best_model_forecast(baseline_fc, advanced_fc, [], [])
    assert best["model"].tolist() == ["lightgbm_advanced"]


def test_select_best_model_forecast_uses_available_frame() -> None:
    baseline_fc = pd.DataFrame(
        [
            {
                "date": "2026-09-01",
                "category": "cn_latiao",
                "market": "us",
                "model": "prophet_baseline",
                "yhat": 10,
                "yhat_lower": 9,
                "yhat_upper": 11,
            }
        ]
    )
    best = select_best_model_forecast(
        baseline_fc,
        pd.DataFrame(),
        [],
        [],
    )
    assert best["model"].tolist() == ["prophet_baseline"]
