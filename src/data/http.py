"""Unified HTTP layer for the data-crawling adapters.

Single source of truth for user agents, timeouts, retries and the
robots-aware ``PoliteFetcher``. Every network-touching adapter under
``src/data`` should import its session/fetcher helpers from here so that
rate-limiting, retry and robots.txt behaviour stay consistent.

The retry logic only retries transient failures (408, 429, 5xx and network
errors); non-retryable client errors (4xx) are raised immediately.
"""

from __future__ import annotations

import html
import random
import re
import time
import urllib.parse
from typing import Any

import requests

# Polite crawler identity (used for Wikimedia and other official JSON APIs).
PROJECT_USER_AGENT = (
    "CrossBorderSourcingResearch/1.0 "
    "(edu demo; contact: local-project-owner)"
)

# Browser-style identity for HTML scraping endpoints (gov.cn, Bing, ...).
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_RETRIES = 2

# Some official JSON APIs serve a redirect (or HTML page) instead of a usable
# robots.txt at their root host. Map those hosts to the robots policy of the
# content they actually expose so the polite fetcher does not fail closed.
ROBOTS_HOST_OVERRIDES = {
    "api.wikimedia.org": "en.wikipedia.org",
    "wikimedia.org": "www.wikimedia.org",
}
ROBOTS_RETRY_ATTEMPTS = 3

_RETRYABLE_STATUS = {408, 429}


def _is_retryable_status(status_code: int) -> bool:
    return status_code in _RETRYABLE_STATUS or status_code >= 500


def _legacy_clean_html(raw: str) -> str:
    """Strip scripts/styles/tags as the last-resort text fallback."""
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw or "")
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return html.unescape(text).strip()


def extract_main_text(raw: str, url: str | None = None) -> str:
    """Extract readable article text with Trafilatura, falling back to regex.

    ``trafilatura`` is imported lazily so offline code paths keep working even
    when the optional dependency is missing.
    """
    if raw and raw.strip():
        try:
            from trafilatura import extract

            extracted = extract(
                raw,
                url=url or None,
                include_comments=False,
                include_tables=True,
                favor_precision=True,
            )
            if extracted and extracted.strip():
                return extracted.strip()
        except Exception:  # noqa: BLE001 - extraction is best-effort
            pass
    return _legacy_clean_html(raw)


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt does not allow a requested URL."""


class PoliteFetcher:
    """Fetch public JSON endpoints with robots checks and throttling."""

    def __init__(
        self,
        user_agent: str = PROJECT_USER_AGENT,
        delay: float = DEFAULT_DELAY_SECONDS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.delay = max(0.0, float(delay))
        self.timeout = float(timeout)
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self._last_request_at = 0.0
        self._robots_parsers: dict[str, Any] = {}
        self._robots_unreachable: set[str] = set()
        self.robots_checked: list[dict[str, Any]] = []

    def _throttle(self) -> None:
        now = time.monotonic()
        wait = self.delay - (now - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _load_robots(self, url: str) -> Any | None:
        """Fetch and cache the Protego parser for a URL host."""
        host = urllib.parse.urlparse(url).netloc
        if host in self._robots_unreachable:
            return None
        parser = self._robots_parsers.get(host)
        if host not in self._robots_parsers:
            parser = None
            scheme = urllib.parse.urlparse(url).scheme or "https"
            robots_host = ROBOTS_HOST_OVERRIDES.get(host, host)
            robots_url = f"{scheme}://{robots_host}/robots.txt"
            for attempt in range(ROBOTS_RETRY_ATTEMPTS):
                try:
                    self._throttle()
                    resp = self.session.get(robots_url, timeout=self.timeout)
                    if resp.status_code < 400:
                        from protego import Protego

                        parser = Protego.parse(resp.text)
                    elif resp.status_code in (401, 403):
                        raise RuntimeError(f"robots.txt returned HTTP {resp.status_code}")
                    else:
                        from protego import Protego

                        parser = Protego.parse("")
                    break
                except Exception as exc:  # noqa: BLE001 - fail closed after retries
                    if attempt >= ROBOTS_RETRY_ATTEMPTS - 1:
                        self._robots_unreachable.add(host)
                        return None
                    time.sleep(0.5 * (attempt + 1))
            self._robots_parsers[host] = parser
        return self._robots_parsers.get(host)

    def robots_allowed(self, url: str) -> bool:
        host = urllib.parse.urlparse(url).netloc
        if host in self._robots_unreachable:
            self.robots_checked.append(
                {"host": host, "url": url, "allowed": False, "error": "robots unreachable"}
            )
            return False
        parser = self._load_robots(url)
        if parser is None:
            self.robots_checked.append(
                {"host": host, "url": url, "allowed": False, "error": "robots unreachable"}
            )
            return False
        allowed = parser.can_fetch(url, self.user_agent)
        self.robots_checked.append(
            {"host": host, "url": url, "allowed": bool(allowed)}
        )
        return bool(allowed)

    def robots_crawl_delay(self, url: str) -> float | None:
        """Return the robots.txt ``Crawl-delay`` for this URL, if any."""
        parser = self._load_robots(url)
        if parser is None:
            return None
        try:
            delay = parser.crawl_delay(self.user_agent)
            return float(delay) if delay is not None else None
        except (TypeError, ValueError):
            return None

    def robots_request_rate(self, url: str) -> dict[str, int] | None:
        """Return the robots.txt ``Request-rate`` for this URL, if any."""
        parser = self._load_robots(url)
        if parser is None:
            return None
        rate = parser.request_rate(self.user_agent)
        if rate is None:
            return None
        return {"requests": int(rate.requests), "seconds": int(rate.seconds)}

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if not self.robots_allowed(url):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")
        self._throttle()
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()


def new_session(user_agent: str = BROWSER_USER_AGENT) -> requests.Session:
    """Return a ``requests.Session`` with a descriptive User-Agent preset."""
    session = requests.Session()
    session.headers["User-Agent"] = user_agent
    return session


def request_with_retry(
    method: str,
    url: str,
    *,
    session: requests.Session | None = None,
    params: dict[str, Any] | None = None,
    json: Any = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    backoff: float = 2.0,
    user_agent: str = BROWSER_USER_AGENT,
) -> requests.Response:
    """Perform one HTTP request with exponential backoff on transient errors.

    Non-retryable client errors (other 4xx) raise ``requests.HTTPError``
    immediately without retrying.
    """
    session = session or new_session(user_agent)
    attempts = max(0, int(retries)) + 1
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = session.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers,
                timeout=timeout,
            )
        except requests.RequestException as exc:  # noqa: BLE001 - retry below
            last_exc = exc
            if attempt >= attempts - 1:
                raise
            time.sleep(backoff * (2**attempt) + random.uniform(0, 0.5))
            continue
        if not _is_retryable_status(resp.status_code):
            resp.raise_for_status()
            return resp
        last_exc = RuntimeError(f"HTTP {resp.status_code} for {url}")
        if attempt >= attempts - 1:
            resp.raise_for_status()
        time.sleep(backoff * (2**attempt) + random.uniform(0, 0.5))
    raise last_exc  # pragma: no cover - unreachable given loop semantics


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    user_agent: str = BROWSER_USER_AGENT,
) -> Any:
    """GET a JSON endpoint and return the decoded payload."""
    resp = request_with_retry(
        "GET",
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        retries=retries,
        user_agent=user_agent,
    )
    return resp.json()


def get_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    user_agent: str = BROWSER_USER_AGENT,
) -> str:
    """GET an HTML/text endpoint and return decoded text."""
    resp = request_with_retry(
        "GET",
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        retries=retries,
        user_agent=user_agent,
    )
    try:
        return resp.content.decode("utf-8", errors="replace")
    except (LookupError, UnicodeDecodeError):
        return resp.text


def post_json(
    url: str,
    payload: Any,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    user_agent: str = BROWSER_USER_AGENT,
) -> Any:
    """POST a JSON payload and return the decoded response."""
    merged = {"Content-Type": "application/json"}
    if headers:
        merged.update(headers)
    resp = request_with_retry(
        "POST",
        url,
        json=payload,
        headers=merged,
        timeout=timeout,
        retries=retries,
        user_agent=user_agent,
    )
    return resp.json()


__all__ = [
    "BROWSER_USER_AGENT",
    "DEFAULT_DELAY_SECONDS",
    "DEFAULT_RETRIES",
    "DEFAULT_TIMEOUT_SECONDS",
    "PROJECT_USER_AGENT",
    "PoliteFetcher",
    "RobotsDisallowedError",
    "extract_main_text",
    "get_json",
    "get_text",
    "new_session",
    "post_json",
    "request_with_retry",
]
