"""看板「数据纵深」真实快照聚合接口测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import services
from src.api.app import app

client = TestClient(app)


def _rankings_payload() -> dict:
    return {
        "generated_at": "2026-08-22T08:00:00+08:00",
        "date": "2026-08-22",
        "offline": False,
        "fallback_used": True,
        "providers": {
            "amazon_github": {
                "status": "ok",
                "note": "amazon_github（GitHub 免费样例，非实时）",
            },
            "mock": {"status": "fallback", "note": "mock"},
        },
        "rows": [
            {
                "date": "2026-08-22",
                "category": "cn_changsha_mifen",
                "category_name": "辣条",
                "market": "us",
                "market_name": "美国",
                "platform": "amazon_github",
                "rank": 1,
                "product": "Pet Feeder",
                "source": "github/luminati-io/Amazon-dataset-samples",
                "fallback_used": False,
                "url": "https://www.amazon.com/dp/B000000000",
                "price": 39.9,
                "rating": 4.5,
            },
            {
                "date": "2026-08-22",
                "category": "cn_changsha_mifen",
                "category_name": "辣条",
                "market": "us",
                "market_name": "美国",
                "platform": "mock",
                "rank": 2,
                "product": "辣条 演示商品 1",
                "source": "mock",
                "fallback_used": True,
            },
        ],
        "source_count": 2,
    }


def _trends_payload() -> dict:
    rows = []
    for index, value in enumerate([10, 20, 30, 40, 50, 60, 70, 80], start=1):
        rows.append(
            {
                "date": f"2026-0{index}-01",
                "category": "cn_changsha_mifen",
                "category_name": "辣条",
                "keyword": "smart pet feeder",
                "market": "us",
                "value": float(value),
            }
        )
    return {
        "generated_at": "2026-08-22T08:00:00+08:00",
        "date": "2026-08-22",
        "offline": False,
        "fallback_used": True,
        "provider": "pytrends",
        "rows": rows,
        "series_count": 1,
        "coverage": {"requested": 1, "real": 1, "mock": 0},
        "errors": [],
    }


def _customs_payload() -> dict:
    return {
        "generated_at": "2026-08-22T08:00:00+08:00",
        "date": "2026-08-22",
        "period": "2024",
        "provider": "comtrade",
        "source_url": "https://comtradeplus.un.org/",
        "fallback_used": False,
        "rows": [
            {
                "date": "2026-08-22",
                "period": "2024",
                "category": "cn_changsha_mifen",
                "category_name": "辣条",
                "hs_code": "3924",
                "hs_description": "塑料制餐具及食品接触用厨房用具",
                "reporter": "156",
                "reporter_name": "中国",
                "partner": None,
                "flow": "export",
                "value": 123.0,
                "source": "comtrade",
                "fallback_used": False,
            }
        ],
        "source_count": 1,
        "errors": [],
    }


def test_market_intel_reads_real_snapshots(monkeypatch) -> None:
    monkeypatch.setattr(services, "load_latest_rankings", _rankings_payload)
    monkeypatch.setattr(services, "load_latest_trends", _trends_payload)
    monkeypatch.setattr(services, "load_latest_customs", _customs_payload)

    payload = services.market_intel({"category": "cn_changsha_mifen", "market": "us", "limit": "20"})

    assert payload["rankings"]["count"] == 2
    assert payload["rankings"]["real_count"] == 1
    assert payload["rankings"]["mock_count"] == 1
    first = payload["rankings"]["items"][0]
    assert first["platform"] == "amazon_github"
    assert first["title"] == "Pet Feeder"
    assert first["score"] == 4.5
    assert first["fallback_used"] is False
    assert payload["rankings"]["source_level"] == "官方免费样例（GitHub 本地缓存）"

    assert payload["searchTrends"]["count"] == 1
    trend = payload["searchTrends"]["items"][0]
    assert trend["category"] == "cn_changsha_mifen"
    assert trend["market"] == "us"
    assert trend["search_trend"] == 160.0
    assert payload["searchTrends"]["coverage"]["real"] == 1

    assert payload["exportValue"]["count"] == 1
    export_item = payload["exportValue"]["items"][0]
    assert export_item["market_name"] == "中国出口"
    assert export_item["export_value"] == 123.0
    assert export_item["period"] == "2024"
    assert payload["exportValue"]["provider"] == "comtrade"

    assert payload["status"]["trends"]["coverage"]["real"] == 1
    assert payload["status"]["customs"]["period"] == "2024"


def test_market_intel_filters_snapshots(monkeypatch) -> None:
    monkeypatch.setattr(services, "load_latest_rankings", _rankings_payload)
    monkeypatch.setattr(services, "load_latest_trends", _trends_payload)
    monkeypatch.setattr(services, "load_latest_customs", _customs_payload)

    payload = services.market_intel({"category": "cn_latiao", "market": "us"})

    assert payload["rankings"]["count"] == 0
    assert payload["searchTrends"]["count"] == 0
    assert payload["exportValue"]["count"] == 0


def test_market_intel_empty_snapshots(monkeypatch) -> None:
    monkeypatch.setattr(
        services,
        "load_latest_rankings",
        lambda: {
            "generated_at": None,
            "date": None,
            "offline": False,
            "fallback_used": False,
            "providers": {},
            "rows": [],
            "source_count": 0,
        },
    )
    monkeypatch.setattr(
        services,
        "load_latest_trends",
        lambda: {
            "generated_at": None,
            "date": None,
            "offline": False,
            "fallback_used": False,
            "provider": None,
            "rows": [],
            "series_count": 0,
            "coverage": {"requested": 0, "real": 0, "mock": 0},
            "errors": [],
        },
    )
    monkeypatch.setattr(
        services,
        "load_latest_customs",
        lambda: {
            "generated_at": None,
            "date": None,
            "period": None,
            "provider": None,
            "source_url": None,
            "fallback_used": False,
            "rows": [],
            "source_count": 0,
            "errors": [],
        },
    )

    payload = services.market_intel({})

    assert payload["rankings"]["count"] == 0
    assert payload["searchTrends"]["count"] == 0
    assert payload["exportValue"]["count"] == 0


def test_market_intel_endpoint_smoke() -> None:
    resp = client.get("/api/market-intel?category=cn_changsha_mifen&market=us")
    assert resp.status_code == 200
    payload = resp.json()
    assert {
        "rankings",
        "searchTrends",
        "exportValue",
        "risk",
        "cost",
        "compare",
        "reviews",
        "competition",
        "status",
    } <= set(payload)
