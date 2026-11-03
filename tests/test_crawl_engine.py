"""Crawlee-based legal crawl engine tests (no real network)."""

from __future__ import annotations

from typing import Any

import pytest

from src.data import crawl_engine as engine_module
from src.data.http import PoliteFetcher, RobotsDisallowedError


class _FakeResponse:
    def __init__(self, text: str = "", status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return {}


class _FakeSession:
    def __init__(self, robots_text: str, robots_status: int = 200) -> None:
        self.headers = {"User-Agent": "test-agent"}
        self.robots_text = robots_text
        self.robots_status = robots_status

    def get(
        self, url: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> _FakeResponse:
        if url.endswith("/robots.txt"):
            return _FakeResponse(text=self.robots_text, status_code=self.robots_status)
        return _FakeResponse()


def _fetcher(robots_text: str = "User-agent: *\nDisallow: /private\n") -> PoliteFetcher:
    return PoliteFetcher(delay=0, session=_FakeSession(robots_text))


def test_offline_fetch_many_returns_ordered_mocks() -> None:
    engine = engine_module.LegalCrawlEngine(offline=True)
    results = engine.fetch_many(
        ["https://example.com/a", "https://example.com/b"]
    )
    assert [item["url"] for item in results] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert all(item["provider"] == "mock" for item in results)
    assert all(item["fallback_used"] is True for item in results)
    assert all(item["robots"] == [] for item in results)


def test_robots_denial_skips_crawler(monkeypatch) -> None:
    engine = engine_module.LegalCrawlEngine(fetcher=_fetcher())

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("crawler must not run for disallowed URLs")

    monkeypatch.setattr(engine_module.asyncio, "run", boom)
    results = engine.fetch_many(["https://example.com/private/secret"])
    assert results[0]["error"] == "robots.txt disallows https://example.com/private/secret"
    assert results[0]["fallback_used"] is True


def test_fetch_many_preserves_order_with_mixed_denial(monkeypatch) -> None:
    engine = engine_module.LegalCrawlEngine(fetcher=_fetcher())

    async def fake_crawl(urls: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "url": url,
                "status": 200,
                "html": "<p>ok</p>",
                "title": "ok",
                "text": "ok",
                "provider": "crawlee",
                "fallback_used": False,
                "robots": [],
                "error": None,
            }
            for url in urls
        ]

    monkeypatch.setattr(engine, "_crawl_allowed", fake_crawl)
    results = engine.fetch_many(
        [
            "https://example.com/private/secret",
            "https://example.com/public",
        ]
    )
    assert [item["url"] for item in results] == [
        "https://example.com/private/secret",
        "https://example.com/public",
    ]
    assert results[0]["error"] is not None
    assert results[1]["error"] is None
    assert results[1]["status"] == 200


def test_fetch_raises_robots_disallowed() -> None:
    engine = engine_module.LegalCrawlEngine(fetcher=_fetcher())
    with pytest.raises(RobotsDisallowedError):
        engine.fetch("https://example.com/private/secret")
