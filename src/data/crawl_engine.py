"""Crawlee-based polite HTML crawl engine.

The engine wraps ``apify/crawlee-python`` (Apache-2.0) as the HTML fetch
layer while keeping the project's strict compliance defaults:

- robots.txt is checked up front through Protego and unreachable robots
  fail closed;
- requests are throttled per domain, including robots.txt ``Crawl-delay``;
- no proxy rotation, session rotation or stealth features are enabled;
- offline mode returns clearly-marked mock results without any network call.

Official JSON APIs (Wikimedia, Federal Register, UN Comtrade, ...) keep using
the lightweight ``PoliteFetcher`` in ``src.data.http`` because the async
crawler adds no value for simple REST endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import math
import urllib.parse
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

from src.config import CRAWLER_OUTPUT_DIR
from src.data.http import (
    BROWSER_USER_AGENT,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
    PoliteFetcher,
    RobotsDisallowedError,
    extract_main_text,
)

CRAWL_ENGINE_STORAGE_DIR = CRAWLER_OUTPUT_DIR / "crawlee_storage"


def _netloc(url: str) -> str:
    return urllib.parse.urlparse(str(url or "")).netloc


def _mock_item(url: str) -> dict[str, Any]:
    return {
        "url": url,
        "status": None,
        "html": "",
        "title": None,
        "text": "Offline mode: no network request was made by the crawl engine.",
        "provider": "mock",
        "fallback_used": True,
        "robots": [],
        "error": None,
    }


def _error_item(
    url: str,
    error: str,
    *,
    robots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "url": url,
        "status": None,
        "html": "",
        "title": None,
        "text": "",
        "provider": "crawlee",
        "fallback_used": True,
        "robots": robots or [],
        "error": error,
    }


class LegalCrawlEngine:
    """Polite HTML crawl facade backed by Crawlee for Python."""

    def __init__(
        self,
        *,
        user_agent: str = BROWSER_USER_AGENT,
        delay: float = DEFAULT_DELAY_SECONDS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retries: int = DEFAULT_RETRIES,
        offline: bool = False,
        storage_dir: str | Path | None = None,
        max_requests_per_crawl: int | None = None,
        fetcher: PoliteFetcher | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.delay = max(0.0, float(delay))
        self.timeout = max(1.0, float(timeout))
        self.retries = max(0, int(retries))
        self.offline = bool(offline)
        self.storage_dir = Path(storage_dir or CRAWL_ENGINE_STORAGE_DIR)
        self.max_requests_per_crawl = max_requests_per_crawl
        self.fetcher = fetcher or PoliteFetcher(
            user_agent=user_agent,
            delay=max(0.0, float(delay) - 0.1),
            timeout=self.timeout,
        )

    def _robots_delay(self, url: str) -> int:
        delay = self.fetcher.robots_crawl_delay(url)
        if delay is None:
            delay = self.delay
        return max(1, int(math.ceil(max(0.0, float(delay)))))

    async def _crawl_allowed(self, urls: Sequence[str]) -> list[dict[str, Any]]:
        logging.getLogger("crawlee").setLevel(logging.ERROR)
        from crawlee.configuration import Configuration
        from crawlee.crawlers import BeautifulSoupCrawler
        from crawlee.events import EventManager
        from crawlee.request_loaders import ThrottlingRequestManager
        from crawlee.storages import RequestQueue

        config = Configuration(storage_dir=str(self.storage_dir))

        async def queue_opener(*args: Any, **kwargs: Any) -> RequestQueue:
            kwargs.setdefault("configuration", config)
            return await RequestQueue.open(*args, **kwargs)

        queue = await queue_opener()
        domains = sorted({_netloc(url) for url in urls if _netloc(url)})
        throttler = ThrottlingRequestManager(
            queue,
            domains=domains,
            request_manager_opener=queue_opener,
            base_delay=timedelta(seconds=min(2.0, self.delay)),
            max_delay=timedelta(seconds=60),
        )
        for url in urls:
            throttler.set_crawl_delay(url, self._robots_delay(url))

        crawler = BeautifulSoupCrawler(
            max_requests_per_crawl=self.max_requests_per_crawl or len(urls),
            configuration=config,
            event_manager=EventManager(),
            request_manager=throttler,
            respect_robots_txt_file=False,
            retry_on_blocked=False,
            max_request_retries=self.retries,
            request_handler_timeout=timedelta(seconds=self.timeout),
            configure_logging=False,
        )

        results: dict[str, dict[str, Any]] = {}
        errors: list[tuple[str, str]] = []

        @crawler.router.default_handler
        async def handler(context: Any) -> None:
            raw = (await context.http_response.read()).decode("utf-8", errors="replace")
            title = context.soup.title.string if context.soup.title else None
            results[context.request.url] = {
                "url": context.request.url,
                "status": int(context.http_response.status_code),
                "html": raw,
                "title": str(title).strip() if title else None,
                "text": extract_main_text(raw, context.request.url),
                "provider": "crawlee",
                "fallback_used": False,
                "robots": list(self.fetcher.robots_checked),
                "error": None,
            }

        @crawler.failed_request_handler
        async def failed_handler(context: Any, error: Exception) -> None:
            errors.append((context.request.url, str(error)))

        await crawler.run(list(urls), purge_request_queue=True)

        for url in urls:
            if url in results:
                continue
            message = next(
                (error for item_url, error in errors if item_url == url),
                "crawl failed",
            )
            results[url] = _error_item(
                url,
                message,
                robots=list(self.fetcher.robots_checked),
            )
        return [results[url] for url in urls]

    def fetch_many(self, urls: Iterable[str]) -> list[dict[str, Any]]:
        """Fetch HTML pages and return results in the same order as input."""
        urls = [str(url).strip() for url in urls if str(url or "").strip()]
        if self.offline:
            return [_mock_item(url) for url in urls]

        entries: dict[str, dict[str, Any]] = {}
        allowed: list[str] = []
        for url in urls:
            if not self.fetcher.robots_allowed(url):
                entries[url] = _error_item(
                    url,
                    f"robots.txt disallows {url}",
                    robots=list(self.fetcher.robots_checked),
                )
            else:
                allowed.append(url)

        if allowed:
            crawled = asyncio.run(self._crawl_allowed(allowed))
            for item in crawled:
                entries[item["url"]] = item
        return [entries[url] for url in urls]

    def fetch(self, url: str) -> dict[str, Any]:
        """Fetch one page; robots-disallowed URLs raise like ``PoliteFetcher``."""
        result = self.fetch_many([url])[0]
        error = result.get("error") or ""
        if "robots.txt disallows" in error:
            raise RobotsDisallowedError(error)
        return result

    def fetch_batch(self, urls: Iterable[str]) -> list[dict[str, Any]]:
        return self.fetch_many(urls)


__all__ = [
    "CRAWL_ENGINE_STORAGE_DIR",
    "LegalCrawlEngine",
]
