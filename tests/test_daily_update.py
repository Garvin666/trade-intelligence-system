"""每日联网数据更新逻辑测试。"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from src.data.daily import (
    build_dashboard_payload,
    collect_daily_snapshot,
    latest_data_date,
    refresh_demo_payloads,
    write_data_status,
)
from src.data.synthetic import generate_market_data
from src.config import CATEGORIES, MARKETS


def _small_frames(weeks: int = 8, horizon: int = 14):
    history = generate_market_data(weeks=weeks, seed=9, end_date="2026-08-07")
    rows = []
    for (category, market), _group in history.groupby(["category", "market"]):
        start = pd.Timestamp("2026-08-08")
        for model in ("prophet_baseline", "lightgbm_advanced"):
            for index in range(horizon):
                rows.append(
                    {
                        "date": start + pd.Timedelta(days=index),
                        "category": category,
                        "market": market,
                        "model": model,
                        "yhat": 100.0 + index,
                        "yhat_lower": 90.0 + index,
                        "yhat_upper": 110.0 + index,
                    }
                )
    forecast = pd.DataFrame(rows)
    recommendations = pd.DataFrame(
        [
            {
                "rank": 1,
                "category": "cn_latiao",
                "market": "us",
                "score": 60.0,
                "forecast_growth": 10.0,
                "search_trend": 5.0,
                "competition": 50.0,
                "review_growth": 2.0,
                "reasons": "test",
            }
        ]
    )
    metrics = {
        "baseline": [{"category": "cn_latiao", "market": "us", "mape": 8.0, "mae": 9.0}],
        "advanced": [{"category": "cn_latiao", "market": "us", "mape": 4.0, "mae": 5.0}],
    }
    trade = {"summary": {"combos": 1}, "rows": [], "policy_events": []}
    return history, forecast, recommendations, metrics, trade


def test_latest_data_date_keeps_day() -> None:
    assert latest_data_date("2026-08-11") == pd.Timestamp("2026-08-11")
    assert latest_data_date("2026-08-07") == pd.Timestamp("2026-08-07")
    assert latest_data_date("2026-08-03") == pd.Timestamp("2026-08-03")


def test_generate_market_data_honors_end_date() -> None:
    df = generate_market_data(weeks=8, seed=3, end_date="2026-08-07")
    assert df["date"].max() == pd.Timestamp("2026-08-07")
    assert len(df) == len(CATEGORIES) * len(MARKETS) * 8
    df_non_friday = generate_market_data(weeks=8, seed=3, end_date="2026-08-13")
    assert df_non_friday["date"].max() == pd.Timestamp("2026-08-13")


def test_refresh_demo_payloads_writes_dashboard_data(tmp_path) -> None:
    history, forecast, recommendations, metrics, trade = _small_frames()
    target = tmp_path / "dashboard-data.json"
    result = refresh_demo_payloads(
        history,
        forecast,
        recommendations,
        metrics,
        trade,
        generated_at="2026-08-11",
        dashboard_data_path=target,
        crawler={"sources_count": 5, "combos": []},
    )
    assert result == {"dashboard_data": target}
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["history"] and payload["forecast"]
    assert payload["models_order"] == ["prophet_baseline", "lightgbm_advanced"]


def test_build_dashboard_payload_shape() -> None:
    history, forecast, recommendations, metrics, _trade = _small_frames()
    payload = build_dashboard_payload(
        history, forecast, recommendations, metrics,
        crawler={"sources_count": 5, "combos": []},
    )
    assert payload["history"] and payload["forecast"]
    assert len(payload["history"]) == len(CATEGORIES) * len(MARKETS) * 8
    assert payload["models_order"] == ["prophet_baseline", "lightgbm_advanced"]
    assert payload["recommendations"][0]["rank"] == 1
    assert payload["crawler"]["sources_count"] == 5


def test_collect_daily_snapshot_writes_file(tmp_path) -> None:
    def fake_search(query: str, max_results: int, provider: str) -> dict:
        return {
            "provider": provider,
            "fallback_used": False,
            "results": [
                {"title": f"{query} A", "snippet": "a", "link": "https://a"},
                {"title": f"{query} B", "snippet": "b", "link": "https://b"},
            ][:max_results],
        }

    payload = collect_daily_snapshot(
        fake_search,
        ["pet products", "home decor"],
        "duckduckgo_html",
        tmp_path,
        "2026-08-11",
    )
    path = tmp_path / "2026-08-11.json"
    assert path.exists()
    assert payload["sources_count"] == 4
    assert payload["fallback_used"] is False
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["date"] == "2026-08-11"


def test_collect_daily_snapshot_falls_back_on_error(tmp_path) -> None:
    def broken_search(query: str, max_results: int, provider: str) -> dict:
        raise ConnectionError("offline")

    payload = collect_daily_snapshot(
        broken_search, ["pet products"], "mock", tmp_path, "2026-08-11"
    )
    assert payload["fallback_used"] is True
    assert payload["queries"][0]["results"][0]["title"].startswith("模拟")


def test_write_data_status(tmp_path) -> None:
    status = write_data_status(
        tmp_path,
        data_as_of="2026-08-07",
        generated_at="2026-08-11T08:00:00+08:00",
        provider="duckduckgo_html",
        fallback_used=False,
        snapshot_path="output/daily_snapshots/2026-08-11.json",
        sources_count=12,
        updated_files=["models/forecast.csv"],
        crawler={
            "generated_at": "2026-08-13T10:00:00+08:00",
            "combos": [{"key": "pet_us"}],
            "sources_count": 3,
            "fallback_used": True,
        },
        trends={"enabled": True, "provider": "mock", "fallback_used": True},
        platform_rankings={"enabled": True, "rows": 5, "fallback_used": True},
        market_daily={"enabled": True, "path": "output/market_daily/2026-08-13.md"},
    )
    path = tmp_path / "data_status.json"
    assert path.exists()
    assert status["data_as_of"] == "2026-08-07"
    assert status["online"]["sources_count"] == 12
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["as_of_label"] == "数据更新至 2026-08-07（当日）"
    assert saved["next_update"] >= "2026-08-11"
    assert saved["crawler"]["status"] == "ready"
    assert saved["crawler"]["combos"] == 1
    assert saved["trends"]["provider"] == "mock"
    assert saved["platform_rankings"]["rows"] == 5
    assert saved["market_daily"]["enabled"] is True
