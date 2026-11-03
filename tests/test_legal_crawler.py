"""Tests for the polite, robots-aware legal crawler."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from src.data import legal_crawler


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        text: str = "",
        status_code: int = 200,
    ) -> None:
        self._payload = payload if payload is not None else {}
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._payload


class FakeSession:
    def __init__(
        self,
        robots_text: str,
        json_payload: dict[str, Any],
        robots_status: int = 200,
    ) -> None:
        self.headers = {"User-Agent": "test-agent"}
        self.robots_text = robots_text
        self.json_payload = json_payload
        self.robots_status = robots_status
        self.calls: list[tuple[str, Any]] = []

    def get(
        self, url: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> FakeResponse:
        self.calls.append((url, params))
        if url.endswith("/robots.txt"):
            return FakeResponse(
                text=self.robots_text, status_code=self.robots_status
            )
        return FakeResponse(payload=self.json_payload)


def test_parse_wikimedia_search_pages() -> None:
    payload = {
        "pages": [
            {
                "key": "Home_automation",
                "title": "Home automation",
                "excerpt": '<span class="searchmatch">smart</span> home devices',
                "description": "Building automation for a home",
            },
            {
                "key": "Smartphone",
                "title": "Smartphone",
                "excerpt": "A mobile device.",
                "description": "Mobile phone",
            },
        ]
    }
    results = legal_crawler.parse_wikimedia_search_pages(
        payload, max_results=5, query="smartphone"
    )
    assert len(results) == 2
    assert results[0]["title"] == "Home automation"
    assert results[0]["snippet"] == "smart home devices"
    assert results[0]["article_key"] == "Home_automation"
    assert results[0]["link"] == "https://en.wikipedia.org/wiki/Home_automation"
    assert all(item["source"] == "wikimedia_search" for item in results)


def test_parse_wikipedia_pageviews() -> None:
    payload = {
        "items": [
            {"timestamp": "2026080100", "views": 12, "article": "Smartphone"},
            {"timestamp": "2026080200", "views": 18, "article": "Smartphone"},
        ]
    }
    rows = legal_crawler.parse_wikipedia_pageviews(payload)
    assert rows[0]["date"] == "20260801"
    assert rows[0]["views"] == 12
    assert rows[1]["views"] == 18


def test_offline_collect_marks_fallback_and_saves(tmp_path) -> None:
    out = tmp_path / "crawl.json"
    payload = legal_crawler.collect_product_signals(
        "smartphone", "US", offline=True, out_path=out
    )
    assert payload["fallback_used"] is True
    assert payload["meta"]["offline"] is True
    assert payload["queries"]
    assert all(entry["provider"] == "mock" for entry in payload["queries"])
    assert all(entry["results"] for entry in payload["queries"])
    assert payload["robots"] == []
    assert out.exists()
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["meta"]["keyword"] == "smartphone"


def test_robots_disallow_private_path() -> None:
    session = FakeSession(
        robots_text="User-agent: *\nDisallow: /private\n", json_payload={}
    )
    fetcher = legal_crawler.PoliteFetcher(delay=0, session=session)
    assert fetcher.robots_allowed("https://example.com/public") is True
    assert fetcher.robots_allowed("https://example.com/private/secret") is False


def test_missing_robots_allows_by_default() -> None:
    session = FakeSession(
        robots_text="", json_payload={}, robots_status=404
    )
    fetcher = legal_crawler.PoliteFetcher(delay=0, session=session)
    assert fetcher.robots_allowed("https://example.com/api") is True


def test_wikimedia_official_api_uses_en_wikipedia_robots() -> None:
    session = FakeSession(robots_text="User-agent: *\n", json_payload={})
    fetcher = legal_crawler.PoliteFetcher(delay=0, session=session)
    assert (
        fetcher.robots_allowed(
            "https://api.wikimedia.org/core/v1/wikipedia/en/search/page"
        )
        is True
    )
    assert (
        fetcher.robots_allowed(
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
        )
        is True
    )
    robots_calls = [
        url for url, _params in session.calls if url.endswith("/robots.txt")
    ]
    assert robots_calls == [
        "https://en.wikipedia.org/robots.txt",
        "https://www.wikimedia.org/robots.txt",
    ]


def test_protego_crawl_delay_and_request_rate() -> None:
    session = FakeSession(
        robots_text=(
            "User-agent: *\n"
            "Disallow: /private\n"
            "Crawl-delay: 3\n"
            "Request-rate: 1/10\n"
        ),
        json_payload={},
    )
    fetcher = legal_crawler.PoliteFetcher(delay=0, session=session)
    assert fetcher.robots_allowed("https://example.com/public") is True
    assert fetcher.robots_crawl_delay("https://example.com/public") == 3.0
    assert fetcher.robots_request_rate("https://example.com/public") == {
        "requests": 1,
        "seconds": 10,
    }


def test_rate_limiter_sleeps(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
    session = FakeSession(robots_text="User-agent: *\n", json_payload={})
    fetcher = legal_crawler.PoliteFetcher(delay=0.02, session=session)
    fetcher.get_json("https://api.example.com/data", params={"q": "x"})
    fetcher.get_json("https://api.example.com/other", params={"q": "y"})
    assert sleeps
    assert all(value >= 0 for value in sleeps)


class FakeFetcher:
    robots_checked = [
        {
            "host": "api.duckduckgo.com",
            "url": "https://api.duckduckgo.com/",
            "allowed": True,
        }
    ]

    def __init__(self, **kwargs: Any) -> None:
        pass

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if "core/v1/wikipedia" in url:
            return {
                "pages": [
                    {
                        "key": "Home_automation",
                        "title": "Home automation",
                        "excerpt": "Trend data for the product.",
                        "description": "Product trend article",
                    }
                ]
            }
        if "pageviews" in url:
            return {
                "items": [
                    {
                        "timestamp": "2026080100",
                        "views": 5,
                        "article": "Home_automation",
                    }
                ]
            }
        return {}


def test_online_collect_uses_public_providers(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        legal_crawler, "PoliteFetcher", lambda **kwargs: FakeFetcher()
    )
    out = tmp_path / "online.json"
    payload = legal_crawler.collect_product_signals(
        "smartphone", "US", out_path=out
    )
    assert payload["fallback_used"] is False
    assert any(
        entry["provider"] == "wikimedia_search" and entry["results"]
        for entry in payload["queries"]
    )
    assert payload["pageviews"]["article"] == "Home_automation"
    assert payload["pageviews"]["items"]
    assert payload["robots"]
    assert out.exists()
