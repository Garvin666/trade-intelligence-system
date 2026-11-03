"""端到端流水线：数据生成、清洗、训练、评估与推荐输出。"""

from __future__ import annotations

import json

import pandas as pd

from src.config import (
    DEMO_CSV,
    FORECAST_CSV,
    METRICS_JSON,
    PROCESSED_CSV,
    RECOMMEND_CSV,
)
from src.data.cleaner import clean_market_data
from src.data.database import save_processed_data
from src.data.real_features import write_real_training_files
from src.data.synthetic import generate_market_data
from src.models import advanced as advanced_model
from src.models import baseline as baseline_model
from src.models import statsforecast_baseline
from src.models.recommend import RecommendationEngine, select_best_model_forecast
from src.trade.opportunity import build_opportunity_lookup


def prepare_data(
    force_regenerate: bool = False,
    end_date: str | None = None,
    use_real_features: bool = True,
) -> pd.DataFrame:
    """生成演示数据（如需）、清洗并持久化到 CSV 与 SQLite。"""
    if not DEMO_CSV.exists() or force_regenerate:
        raw = generate_market_data(end_date=end_date)
        DEMO_CSV.parent.mkdir(parents=True, exist_ok=True)
        raw.to_csv(DEMO_CSV, index=False)
    else:
        raw = pd.read_csv(DEMO_CSV)

    cleaned = clean_market_data(raw)
    PROCESSED_CSV.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(PROCESSED_CSV, index=False)
    save_processed_data(cleaned)
    if use_real_features:
        augmented, _ = write_real_training_files(cleaned)
        return augmented
    return cleaned


def _save_metrics(
    baseline_metrics: pd.DataFrame,
    advanced_metrics: pd.DataFrame,
    statsforecast_metrics: pd.DataFrame | None = None,
) -> None:
    payload = {
        "baseline": baseline_metrics.to_dict(orient="records"),
        "advanced": advanced_metrics.to_dict(orient="records"),
    }
    if statsforecast_metrics is not None and not statsforecast_metrics.empty:
        payload["statsforecast"] = statsforecast_metrics.to_dict(orient="records")
    METRICS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def train_and_evaluate(df: pd.DataFrame) -> dict:
    """训练两个模型，产出评估、预测、推荐并落盘。"""
    baseline_metrics = baseline_model.evaluate_all(df)
    advanced_metrics = advanced_model.evaluate_all(df)
    statsforecast_metrics = statsforecast_baseline.evaluate_all(df)
    _save_metrics(baseline_metrics, advanced_metrics, statsforecast_metrics)

    baseline_fc = baseline_model.forecast_all(df)
    advanced_fc = advanced_model.forecast_all(df)
    forecast = pd.concat([baseline_fc, advanced_fc], ignore_index=True)
    FORECAST_CSV.parent.mkdir(parents=True, exist_ok=True)
    forecast.to_csv(FORECAST_CSV, index=False)

    best_fc = select_best_model_forecast(
        baseline_fc,
        advanced_fc,
        baseline_metrics,
        advanced_metrics,
    )
    engine = RecommendationEngine()
    opportunity = build_opportunity_lookup()
    recommendations = engine.build(df, best_fc, opportunity=opportunity)
    recommendations.to_csv(RECOMMEND_CSV, index=False)

    return {
        "baseline_metrics": baseline_metrics,
        "advanced_metrics": advanced_metrics,
        "statsforecast_metrics": statsforecast_metrics,
        "forecast": forecast,
        "recommendations": recommendations,
    }


def run_full_pipeline(
    force_regenerate: bool = False,
    end_date: str | None = None,
    use_real_features: bool = True,
) -> dict:
    """执行完整流水线并返回报告对象。"""
    df = prepare_data(
        force_regenerate=force_regenerate,
        end_date=end_date,
        use_real_features=use_real_features,
    )
    result = train_and_evaluate(df)
    result["data"] = df
    return result
