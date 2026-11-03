"""Unified search fallback chain shared by the API bridge and the daily update.

Implements the crawler-first chain ``crawler -> duckduckgo_html -> mock`` as a
pure function so the orchestration lives in exactly one place. The provider
executors are injected as callables, which keeps this module free of any
dependency on the four-brain engine package and makes it trivially testable.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from src.config import SEARCH_PROVIDER_CHAIN

SEARCH_CHAIN_CACHE_TTL_SECONDS = float(
    os.environ.get("SEARCH_RESULT_CACHE_TTL", "300")
)

# 单阶段（crawler / duckduckgo）网络上限与整条回退链的硬截止时间。
SEARCH_STAGE_TIMEOUT_SECONDS = float(
    os.environ.get("SEARCH_STAGE_TIMEOUT_SECONDS", "6")
)
SEARCH_CHAIN_DEADLINE_SECONDS = float(
    os.environ.get("SEARCH_CHAIN_DEADLINE_SECONDS", "12")
)
_CHAIN_CACHE: dict[
    tuple[str, str, int, str, str, int, int, int],
    tuple[float, dict[str, Any]],
] = {}
_CHAIN_CACHE_LOCK = threading.Lock()


def _empty(items: list[dict[str, Any]]) -> bool:
    if not items:
        return True
    if all(
        not str(item.get("title", "")).strip()
        and not str(item.get("snippet", "")).strip()
        for item in items
    ):
        return True
    return any(
        "请求失败" in str(item.get("title", ""))
        or "配置缺失" in str(item.get("title", ""))
        for item in items
    )


def _run_with_timeout(
    fn: Callable[..., Any],
    timeout: float,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Run a search stage with a hard timeout; timed-out work is abandoned."""
    if timeout <= 0:
        return fn(*args, **kwargs)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="search-stage")
    future = pool.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    finally:
        pool.shutdown(wait=False)


def chain_search(
    query: str,
    max_results: int,
    *,
    provider: str,
    crawler_fn: Callable[..., dict[str, Any]],
    web_fn: Callable[..., list[dict[str, Any]]],
    mock_fn: Callable[..., list[dict[str, Any]]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one query through the crawler-first fallback chain.

    Returns ``{provider, fallback_used, fallback_provider, results, ...}`` with
    optional crawler pageview evidence when the crawler provider succeeded.
    """
    config = dict(config or {})
    provider_name = str(provider or "crawler").strip().lower()
    cache_key = (
        provider_name,
        query,
        int(max_results),
        str(config.get("api_url") or ""),
        str(config.get("api_key") or ""),
        id(crawler_fn),
        id(web_fn),
        id(mock_fn),
    )
    now = time.time()
    if SEARCH_CHAIN_CACHE_TTL_SECONDS > 0:
        with _CHAIN_CACHE_LOCK:
            hit = _CHAIN_CACHE.get(cache_key)
            if hit is not None and now - hit[0] <= SEARCH_CHAIN_CACHE_TTL_SECONDS:
                return hit[1]
    result = _chain_search_impl(
        query,
        max_results,
        provider=provider,
        crawler_fn=crawler_fn,
        web_fn=web_fn,
        mock_fn=mock_fn,
        config=config,
    )
    if (
        SEARCH_CHAIN_CACHE_TTL_SECONDS > 0
        and not result.get("fallback_used")
        and str(result.get("provider") or "").lower() != "mock"
        and result.get("results")
    ):
        with _CHAIN_CACHE_LOCK:
            _CHAIN_CACHE[cache_key] = (now, result)
    return result


def _chain_search_impl(
    query: str,
    max_results: int,
    *,
    provider: str,
    crawler_fn: Callable[..., dict[str, Any]],
    web_fn: Callable[..., list[dict[str, Any]]],
    mock_fn: Callable[..., list[dict[str, Any]]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = dict(config or {})
    provider_name = str(provider or "crawler").strip().lower()
    deadline = time.monotonic() + SEARCH_CHAIN_DEADLINE_SECONDS

    def _remaining() -> float:
        return max(0.0, deadline - time.monotonic())

    fallback_used = False
    fallback_provider: str | None = None
    crawler_evidence: dict[str, Any] = {}
    results: list[dict[str, Any]] = []

    if provider_name == "crawler":
        failed = False
        try:
            crawled = _run_with_timeout(
                crawler_fn,
                min(SEARCH_STAGE_TIMEOUT_SECONDS, _remaining()),
                query,
                max_results=max_results,
                config=config,
            )
            results = crawled.get("results") or []
            failed = _empty(results) or bool(crawled.get("fallback_used"))
            if not failed:
                crawler_evidence = {
                    key: crawled.get(key)
                    for key in ("pageview_trend_pct", "pageview_article", "pageviews")
                }
            else:
                results = []
        except Exception:  # noqa: BLE001 - one source may fail
            results = []
            failed = True

        if failed:
            fallback_used = True
            fallback_config = {**config, "provider": "duckduckgo_html"}
            if _remaining() <= 0:
                results = []
            else:
                try:
                    results = _run_with_timeout(
                        web_fn,
                        min(SEARCH_STAGE_TIMEOUT_SECONDS, _remaining()),
                        query,
                        max_results=max_results,
                        config=fallback_config,
                    )
                    if _empty(results):
                        results = []
                except Exception:  # noqa: BLE001 - search also failed
                    results = []
            if results:
                fallback_provider = "duckduckgo_html"
            else:
                fallback_provider = "mock"
                results = mock_fn(query, max_results)
    else:
        failed = False
        if _remaining() <= 0:
            results = []
            failed = True
        else:
            try:
                results = _run_with_timeout(
                    web_fn,
                    min(SEARCH_STAGE_TIMEOUT_SECONDS, _remaining()),
                    query,
                    max_results=max_results,
                    config=config,
                )
                failed = _empty(results)
            except Exception:  # noqa: BLE001 - 联网失败统一回退 mock
                results = []
                failed = True

        if failed and provider_name != "mock":
            results = mock_fn(query, max_results)
            fallback_used = True
            fallback_provider = "mock"

    payload: dict[str, Any] = {
        "provider": provider_name,
        "fallback_used": fallback_used,
        "results": results,
    }
    if fallback_provider:
        payload["fallback_provider"] = fallback_provider
    payload.update(crawler_evidence)
    return payload


__all__ = [
    "SEARCH_PROVIDER_CHAIN",
    "chain_search",
]
