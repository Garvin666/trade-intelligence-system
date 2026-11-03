"""Crawler-first search and fallback chain tests."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.api import ai_config, brain_bridge  # noqa: E402
from src.data import legal_crawler  # noqa: E402
from src.four_brain import data_tools  # noqa: E402


def _fake_crawler_payload() -> dict:
    return {
        "results": [
            {
                "title": "Pet feeder market",
                "snippet": "crawled evidence",
                "link": "https://en.wikipedia.org/wiki/Pet_feeder",
                "source": "wikimedia_search",
            }
        ],
        "pageviews": [
            {"date": "20260101", "views": 10},
            {"date": "20260102", "views": 12},
        ],
        "pageview_trend_pct": 20.0,
        "pageview_article": "Pet_feeder",
        "provider": "crawler",
        "fallback_used": False,
    }


def test_search_defaults_to_duckduckgo_html(monkeypatch) -> None:
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    ai_config.set_config({"search_provider": ""})
    assert brain_bridge.available()
    config = brain_bridge._search_config({})
    assert config["provider"] == "duckduckgo_html"


def test_search_uses_crawler_without_fallback(monkeypatch) -> None:
    assert brain_bridge.available()
    monkeypatch.setattr(
        data_tools, "crawler_search", lambda *args, **kwargs: _fake_crawler_payload()
    )
    result = brain_bridge.search("pet feeder", max_results=3, provider="crawler")
    assert result["provider"] == "crawler"
    assert result["fallback_used"] is False
    assert result["pageview_trend_pct"] == 20.0
    assert result["pageview_article"] == "Pet_feeder"
    assert result["results"][0]["source"] == "wikimedia_search"


def test_search_crawler_falls_back_to_duckduckgo_then_mock(monkeypatch) -> None:
    assert brain_bridge.available()

    def boom(*args, **kwargs):
        raise RuntimeError("crawler down")

    monkeypatch.setattr(data_tools, "crawler_search", boom)
    monkeypatch.setattr(
        data_tools,
        "search_web",
        lambda *args, **kwargs: [
            {"title": "ddg", "snippet": "s", "link": "https://example.com"}
        ],
    )
    result = brain_bridge.search("pet feeder", max_results=3, provider="crawler")
    assert result["fallback_used"] is True
    assert result["fallback_provider"] == "duckduckgo_html"
    assert result["results"][0]["title"] == "ddg"

    monkeypatch.setattr(data_tools, "search_web", lambda *args, **kwargs: [])
    result = brain_bridge.search("pet feeder", max_results=3, provider="crawler")
    assert result["fallback_used"] is True
    assert result["fallback_provider"] == "mock"
    assert result["results"]


def test_data_tools_crawler_search_builtin_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        data_tools,
        "_wikimedia_json_search",
        lambda query, max_results, timeout=20.0: [
            {
                "title": "t",
                "snippet": "s",
                "link": "https://en.wikipedia.org/wiki/T",
                "source": "wikimedia_search",
                "article_key": "T",
            }
        ],
    )
    monkeypatch.setattr(
        data_tools,
        "_wikimedia_pageviews",
        lambda article_key, timeout=20.0: [{"date": "20260101", "views": 10}],
    )
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if fromlist and "legal_crawler" in fromlist and name.endswith("src.data"):
            raise ImportError("standalone")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    payload = data_tools.crawler_search("pet feeder", max_results=3)
    assert payload["provider"] == "crawler"
    assert payload["fallback_used"] is False
    assert payload["results"][0]["source"] == "wikimedia_search"


def test_data_tools_preserves_legal_crawler_fallback_marker(monkeypatch) -> None:
    def fake_crawler(query: str, max_results: int = 5):
        return {
            "results": [
                {
                    "title": f"Mock result for {query}",
                    "snippet": "Offline mode: no network request was made by the legal crawler.",
                    "link": "https://duckduckgo.com/?q=test",
                    "source": "mock",
                }
            ],
            "pageviews": [],
            "pageview_trend_pct": 0.0,
            "pageview_article": None,
            "provider": "mock",
            "fallback_used": True,
        }

    monkeypatch.setattr(legal_crawler, "crawler_search", fake_crawler)
    payload = data_tools.crawler_search("pet feeder", max_results=3)
    assert payload["fallback_used"] is True
    assert payload["provider"] == "mock"
    assert payload["mock_used"] is True


def test_brain_bridge_falls_back_when_crawler_mock_marker_set(monkeypatch) -> None:
    def fake_crawler(query: str, max_results: int = 5, config: dict | None = None):
        return {
            "results": [
                {
                    "title": f"Mock result for {query}",
                    "snippet": "offline",
                    "link": "https://duckduckgo.com/?q=test",
                    "source": "mock",
                }
            ],
            "pageviews": [],
            "pageview_trend_pct": 0.0,
            "pageview_article": None,
            "provider": "mock",
            "fallback_used": True,
        }

    monkeypatch.setattr(data_tools, "crawler_search", fake_crawler)
    monkeypatch.setattr(data_tools, "search_web", lambda *args, **kwargs: [])
    result = brain_bridge.search("pet feeder", max_results=3, provider="crawler")
    assert result["fallback_used"] is True
    assert result["fallback_provider"] == "mock"
    assert result["results"]


def test_research_only_marks_mock_sources_and_counts(monkeypatch) -> None:
    def fake_search(query: str, **kwargs):
        return {
            "provider": "mock",
            "fallback_used": True,
            "mock_used": True,
            "results": [
                {
                    "title": f"Mock result for {query}",
                    "snippet": "offline",
                    "link": "https://duckduckgo.com/?q=test",
                    "source": "mock",
                }
            ],
            "pageviews": [],
            "pageview_trend_pct": 0.0,
            "pageview_article": None,
        }

    def fake_analyze(payload, data):
        return {
            "payload": payload,
            "normalized": payload,
            "keyword": "pet feeder",
            "market": "us",
            "category_name": "辣条",
        }

    monkeypatch.setattr(brain_bridge, "search", fake_search)
    monkeypatch.setattr(brain_bridge.four_brain, "analyze", fake_analyze)
    monkeypatch.setattr(
        brain_bridge.four_brain,
        "extract_search_history",
        lambda research, keyword, market: [],
    )
    monkeypatch.setattr(
        brain_bridge,
        "_attach_real_evidence",
        lambda result, payload: result,
    )

    result = brain_bridge.research_only(
        {
            "keyword": "pet feeder",
            "market": "us",
            "max_results": 3,
            "search_provider": "crawler",
        }
    )
    research = result["research"]
    assert research["mock_count"] > 0
    assert research["mock_used"] is True
    assert "离线模拟" in research["summary"]
    assert "有效链接 0 条" in research["summary"]


def test_research_only_uses_global_search_provider(monkeypatch) -> None:
    """联网研究未显式传 provider 时应跟随全局 AI 接入配置。"""
    ai_config.set_config({"search_provider": "mock"})
    captured: dict[str, str | None] = {}

    def fake_search(query: str, **kwargs):
        captured["provider"] = kwargs.get("provider")
        return {
            "provider": kwargs.get("provider"),
            "fallback_used": False,
            "results": [
                {
                    "title": "t",
                    "snippet": "s",
                    "link": "https://example.com",
                }
            ],
        }

    def fake_analyze(payload, data):
        return {
            "payload": {"keyword": "pet feeder", "market": "us"},
            "category_name": "辣条",
        }

    monkeypatch.setattr(brain_bridge, "_resolve_data", lambda payload: {"history": []})
    monkeypatch.setattr(brain_bridge, "search", fake_search)
    monkeypatch.setattr(brain_bridge.four_brain, "analyze", fake_analyze)
    monkeypatch.setattr(
        brain_bridge.four_brain,
        "extract_search_history",
        lambda research, keyword, market: [],
    )
    monkeypatch.setattr(
        brain_bridge,
        "_attach_real_evidence",
        lambda result, payload: result,
    )
    try:
        brain_bridge.research_only(
            {"keyword": "pet feeder", "market": "us", "max_results": 1}
        )
        assert captured["provider"] == "mock"
    finally:
        ai_config.clear_config()
