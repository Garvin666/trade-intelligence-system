"""Polite, robots-aware crawler for public e-commerce research signals.

The crawler only touches official public endpoints:
- Wikimedia core search API (JSON, no key required)
- Wikimedia pageviews API (JSON, no key required)

Safety rules enforced here:
- robots.txt is checked before every host is contacted.
- Requests are rate-limited and carry a descriptive User-Agent.
- Search result links are stored but never fetched automatically.
- Offline mode returns clearly-marked mock data and makes no network calls.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import threading
import urllib.parse
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.data.base import pageview_trend_pct
from src.data.http import (
    DEFAULT_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    PROJECT_USER_AGENT,
    PoliteFetcher,
    RobotsDisallowedError,
)

WIKIMEDIA_SEARCH_API = "https://api.wikimedia.org/core/v1/wikipedia/en/search/page"
WIKIMEDIA_PAGEVIEWS_API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
)


def parse_wikimedia_search_pages(
    payload: dict[str, Any],
    max_results: int = 5,
    query: str = "",
) -> list[dict[str, Any]]:
    """Convert a Wikimedia core search payload into normalized results."""
    results: list[dict[str, Any]] = []
    for page in (payload.get("pages") or [])[: max(1, int(max_results))]:
        title = str(page.get("title") or "")
        key = str(page.get("key") or "")
        excerpt = html.unescape(
            re.sub(r"<[^>]+>", "", str(page.get("excerpt") or "")).strip()
        )
        description = html.unescape(str(page.get("description") or ""))
        if not (title or key):
            continue
        results.append(
            {
                "title": title or query,
                "snippet": excerpt or description,
                "link": "https://en.wikipedia.org/wiki/"
                + urllib.parse.quote(key.replace(" ", "_")),
                "source": "wikimedia_search",
                "article_key": key,
                "description": description,
            }
        )
    return results


def parse_wikipedia_pageviews(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Wikimedia pageview items into daily rows."""
    rows: list[dict[str, Any]] = []
    for item in payload.get("items") or []:
        timestamp = str(item.get("timestamp") or "")
        if len(timestamp) < 8:
            continue
        rows.append(
            {
                "date": timestamp[:8],
                "views": int(item.get("views") or 0),
                "article": item.get("article"),
            }
        )
    return rows


def wikimedia_search_pages(
    fetcher: PoliteFetcher,
    query: str,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Search English Wikipedia through the official Wikimedia core API."""
    payload = fetcher.get_json(
        WIKIMEDIA_SEARCH_API,
        params={"q": query, "limit": max(1, int(max_results))},
    )
    return parse_wikimedia_search_pages(
        payload, max_results=max_results, query=query
    )


def wikipedia_pageviews(
    fetcher: PoliteFetcher,
    article_title: str,
    days: int = 90,
    language: str = "en",
) -> dict[str, Any]:
    """Fetch daily pageviews for a resolved Wikipedia article title."""
    title = (article_title or "").strip()
    if not title:
        return {"article": None, "items": []}
    end = date.today()
    start = end - timedelta(days=max(1, int(days)) - 1)
    safe_title = urllib.parse.quote(title.replace(" ", "_"))
    url = (
        f"{WIKIMEDIA_PAGEVIEWS_API}/{language}.wikipedia/all-access/user/"
        f"{safe_title}/daily/{start:%Y%m%d}/{end:%Y%m%d}"
    )
    payload = fetcher.get_json(url)
    items = parse_wikipedia_pageviews(payload)
    return {"article": title, "items": items}


def _mock_results(query: str, max_results: int) -> list[dict[str, Any]]:
    return [
        {
            "title": f"Mock result for {query}",
            "snippet": "Offline mode: no network request was made by the legal crawler.",
            "link": "https://duckduckgo.com/?q=" + urllib.parse.quote(query),
            "source": "mock",
        }
        for _ in range(max(1, min(int(max_results), 5)))
    ]


def _pageview_trend_pct(items: list[dict[str, Any]]) -> float:
    """Percent change between the recent half and earlier half of pageviews."""
    return pageview_trend_pct(items)


_FETCHER: PoliteFetcher | None = None
_FETCHER_LOCK = threading.Lock()


def _shared_fetcher(
    delay: float = DEFAULT_DELAY_SECONDS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> PoliteFetcher:
    """复用同一个 PoliteFetcher，缓存 robots 解析结果与连接池。"""
    global _FETCHER
    with _FETCHER_LOCK:
        if _FETCHER is None:
            _FETCHER = PoliteFetcher(delay=delay, timeout=timeout)
        return _FETCHER


def crawler_search(
    query: str,
    max_results: int = 5,
    *,
    offline: bool = False,
    delay: float = DEFAULT_DELAY_SECONDS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    fetcher: PoliteFetcher | None = None,
) -> dict[str, Any]:
    """Crawl public sources for one query and return normalized search results.

    The returned payload follows the ``search_web`` result shape so every
    consumer can switch from DuckDuckGo to the crawler without changing its
    schema, while pageview evidence stays available for trend display.
    """
    query = str(query or "").strip()
    if not query:
        return {
            "query": "",
            "results": [],
            "pageviews": [],
            "pageview_trend_pct": 0.0,
            "pageview_article": None,
            "provider": "crawler",
            "fallback_used": True,
        }
    if offline:
        results = _mock_results(query, max_results)
        return {
            "query": query,
            "results": results,
            "pageviews": [],
            "pageview_trend_pct": 0.0,
            "pageview_article": None,
            "provider": "mock",
            "fallback_used": True,
        }

    own_fetcher = fetcher is None
    fetcher = fetcher or _shared_fetcher(delay=delay, timeout=timeout)
    lock = _FETCHER_LOCK if own_fetcher else nullcontext()
    with lock:
        results: list[dict[str, Any]] = []
        try:
            results = wikimedia_search_pages(fetcher, query, max_results)
        except Exception:  # noqa: BLE001 - pageviews are optional
            results = []

        article_key = next(
            (
                result["article_key"]
                for result in results
                if result.get("article_key")
            ),
            None,
        )
        pageviews: list[dict[str, Any]] = []
        if article_key:
            try:
                pageviews = wikipedia_pageviews(fetcher, article_key).get("items") or []
            except Exception:  # noqa: BLE001 - pageviews are optional
                pageviews = []

    fallback_used = not results and not pageviews
    if fallback_used:
        results = _mock_results(query, max_results)
    return {
        "query": query,
        "results": results,
        "pageviews": pageviews,
        "pageview_trend_pct": _pageview_trend_pct(pageviews),
        "pageview_article": article_key,
        "provider": "mock" if fallback_used else "crawler",
        "fallback_used": fallback_used,
    }


def collect_product_signals(
    keyword: str,
    market: str = "US",
    category: str = "",
    *,
    max_results: int = 5,
    delay: float = DEFAULT_DELAY_SECONDS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    offline: bool = False,
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    """Collect public signals for one product/market combination.

    Returns a structured payload with meta, search results, pageviews,
    robots checks and errors. Offline mode writes clearly-marked mocks.
    """
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(
        timespec="seconds"
    )
    base_queries = [
        keyword,
        f"{keyword} {market} cross-border e-commerce product trend",
        f"{keyword} {market} import export market data",
    ]
    if category:
        base_queries.insert(
            1, f"{category} {keyword} {market} cross-border e-commerce trend"
        )
    queries = list(dict.fromkeys(base_queries))

    payload: dict[str, Any] = {
        "meta": {
            "keyword": keyword,
            "market": market,
            "category": category,
            "generated_at": generated_at,
            "offline": bool(offline),
            "user_agent": PROJECT_USER_AGENT,
            "max_results": max(1, int(max_results)),
        },
        "queries": [],
        "pageviews": None,
        "fallback_used": False,
        "errors": [],
        "robots": [],
    }

    if offline:
        payload["fallback_used"] = True
        for query in queries:
            payload["queries"].append(
                {
                    "query": query,
                    "provider": "mock",
                    "results": _mock_results(query, max_results),
                }
            )
    else:
        fetcher = PoliteFetcher(delay=delay, timeout=timeout)
        for query in queries:
            try:
                results = wikimedia_search_pages(fetcher, query, max_results)
                payload["queries"].append(
                    {
                        "query": query,
                        "provider": "wikimedia_search",
                        "results": results,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - one source may fail
                payload["errors"].append(
                    {
                        "query": query,
                        "provider": "wikimedia_search",
                        "error": str(exc),
                    }
                )
                payload["queries"].append(
                    {"query": query, "provider": "wikimedia_search", "results": []}
                )
        article_key = next(
            (
                result["article_key"]
                for entry in payload["queries"]
                for result in entry["results"]
                if result.get("article_key")
            ),
            None,
        )
        try:
            payload["pageviews"] = wikipedia_pageviews(fetcher, article_key)
        except Exception as exc:  # noqa: BLE001 - pageviews are optional
            payload["errors"].append(
                {"provider": "wikimedia_pageviews", "error": str(exc)}
            )
        payload["robots"] = fetcher.robots_checked

        real_results = [
            result
            for entry in payload["queries"]
            for result in entry["results"]
            if result.get("source") != "mock"
        ]
        pageview_items = (payload.get("pageviews") or {}).get("items") or []
        if not real_results and not pageview_items:
            payload["fallback_used"] = True
            for entry in payload["queries"]:
                if not entry["results"]:
                    entry["provider"] = "mock"
                    entry["results"] = _mock_results(entry["query"], max_results)

    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        payload["saved_to"] = str(path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Legal crawler for public cross-border e-commerce signals"
    )
    parser.add_argument("--keyword", required=True, help="product keyword")
    parser.add_argument("--market", default="US", help="target market")
    parser.add_argument("--category", default="", help="optional category label")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--out", default=None, help="output JSON path")
    args = parser.parse_args(argv)

    payload = collect_product_signals(
        args.keyword,
        market=args.market,
        category=args.category,
        max_results=args.max_results,
        delay=args.delay,
        timeout=args.timeout,
        offline=args.offline,
        out_path=args.out,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
