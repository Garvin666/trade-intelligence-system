"""Tests for the unified crawler signal layer."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from src.config import CATEGORIES, CATEGORY_KEYWORDS
from src.data import crawler_signals


def _raw_payload(offline: bool = False) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    provider = "mock" if offline else "wikimedia_search"
    return {
        "meta": {
            "keyword": "辣条 latiao",
            "market": "us",
            "category": "cn_latiao",
            "generated_at": now,
            "offline": offline,
            "max_results": 3,
        },
        "queries": [
            {
                "query": "辣条 latiao",
                "provider": provider,
                "results": [
                    {
                        "title": "Pet feeder",
                        "snippet": "snippet",
                        "link": "https://en.wikipedia.org/wiki/Pet_feeder",
                        "source": provider,
                    }
                ],
            }
        ],
        "pageviews": {
            "article": "Latiao",
            "items": [
                {"date": "20260701", "views": 100},
                {"date": "20260702", "views": 200},
            ],
        },
        "fallback_used": offline,
        "errors": [],
        "robots": [],
    }


def _fake_normalized(offline: bool = False) -> dict:
    payload = crawler_signals.normalize_signal(
        _raw_payload(offline), "辣条 latiao", "us", "cn_latiao"
    )
    payload["keyword"] = "辣条 latiao"
    return payload


def test_category_keywords_cover_all_categories() -> None:
    assert set(CATEGORY_KEYWORDS) == set(CATEGORIES)
    assert len(CATEGORY_KEYWORDS) == len(CATEGORIES)


def test_compute_pageview_trend() -> None:
    items = [
        {"date": "20260701", "views": 100},
        {"date": "20260702", "views": 100},
        {"date": "20260703", "views": 200},
        {"date": "20260704", "views": 200},
    ]
    assert crawler_signals.compute_pageview_trend(items) == 100.0
    assert crawler_signals.compute_pageview_trend([]) == 0.0
    assert crawler_signals.compute_pageview_trend([{"date": "20260701", "views": 10}]) == 0.0


def test_normalize_signal_shape() -> None:
    signal = crawler_signals.normalize_signal(
        _raw_payload(), "辣条 latiao", "us", "cn_latiao"
    )
    assert signal["key"] == "cn_latiao_us"
    assert signal["category_name"]
    assert signal["market_name"]
    assert signal["source_count"] == 1
    assert signal["pageview_trend_pct"] == 100.0
    assert signal["fallback_used"] is False
    assert signal["provider"] == "wikimedia_search"
    assert signal["top_sources"][0]["link"].startswith("http")


def test_collect_signal_offline_uses_mock(monkeypatch, tmp_path) -> None:
    calls: list[dict] = []

    def fake_collect(keyword, market="us", category="", **kwargs):
        calls.append({"keyword": keyword, "market": market, "category": category})
        return _raw_payload(offline=True)

    monkeypatch.setattr(
        crawler_signals.legal_crawler, "collect_product_signals", fake_collect
    )
    monkeypatch.setattr(crawler_signals, "CRAWLER_CACHE_DIR", tmp_path / "cache")
    signal = crawler_signals.collect_signal(
        "辣条 latiao", market="US", category="cn_latiao", offline=True
    )
    assert calls == [{"keyword": "辣条 latiao", "market": "us", "category": "cn_latiao"}]
    assert signal["fallback_used"] is True
    assert signal["provider"] == "mock"
    assert not list((tmp_path / "cache").glob("*.json"))


def test_collect_signal_cache_hit(monkeypatch, tmp_path) -> None:
    calls: list[int] = []

    def fake_collect(keyword, market="us", category="", **kwargs):
        calls.append(1)
        return _raw_payload()

    monkeypatch.setattr(
        crawler_signals.legal_crawler, "collect_product_signals", fake_collect
    )
    monkeypatch.setattr(crawler_signals, "CRAWLER_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(crawler_signals, "CRAWLER_CACHE_TTL_SECONDS", 60)

    first = crawler_signals.collect_signal("辣条 latiao", "us", "cn_latiao")
    second = crawler_signals.collect_signal("辣条 latiao", "us", "cn_latiao")
    assert len(calls) == 1
    assert first["keyword"] == second["keyword"]
    assert len(list((tmp_path / "cache").glob("*.json"))) == 1


def test_build_daily_combos_top_n() -> None:
    df = pd.DataFrame(
        [
            {"rank": 1, "category": "cn_latiao", "market": "us"},
            {"rank": 2, "category": "cn_changsha_mifen", "market": "eu"},
            {"rank": 3, "category": "intl_matcha", "market": "sea"},
        ]
    )
    combos = crawler_signals.build_daily_combos(df, count=2)
    assert [item["category"] for item in combos] == ["cn_latiao", "cn_changsha_mifen"]
    assert combos[0]["keyword"] == CATEGORY_KEYWORDS["cn_latiao"]
    assert combos[1]["market"] == "eu"


def test_build_snapshot_offline_writes_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        crawler_signals,
        "collect_signal",
        lambda keyword, market="us", category="", **kwargs: _fake_normalized(offline=True),
    )
    out = tmp_path / "latest.json"
    snapshot = crawler_signals.build_snapshot(
        [{"keyword": "辣条 latiao", "market": "us", "category": "cn_latiao"}],
        offline=True,
        out_path=out,
    )
    assert snapshot["fallback_used"] is True
    assert snapshot["sources_count"] == 1
    assert out.exists()
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["combos"][0]["key"] == "cn_latiao_us"


def test_load_filter_and_status(tmp_path, monkeypatch) -> None:
    latest = tmp_path / "latest.json"
    latest.write_text(
        json.dumps(
            {
                "generated_at": "2026-08-13T10:00:00+08:00",
                "date": "2026-08-13",
                "fallback_used": True,
                "sources_count": 2,
                "combos": [
                    {
                        "key": "cn_latiao_us",
                        "category": "cn_latiao",
                        "market": "us",
                        "keyword": "辣条 latiao",
                        "fallback_used": True,
                        "source_count": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(crawler_signals, "CRAWLER_LATEST_JSON", latest)
    snapshot = crawler_signals.load_latest_snapshot()
    assert snapshot["sources_count"] == 2
    filtered = crawler_signals.filter_snapshot(snapshot, market="us")
    assert len(filtered) == 1
    assert crawler_signals.filter_snapshot(snapshot, market="eu") == []
    status = crawler_signals.snapshot_status(snapshot)
    assert status["status"] == "ready"
    assert status["combos"] == 1
