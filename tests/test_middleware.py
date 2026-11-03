"""Rate-limit dictionary pruning regression tests."""

from __future__ import annotations

import time

from src.api.middleware import RateLimitMiddleware


def test_rate_limit_prunes_stale_clients() -> None:
    middleware = RateLimitMiddleware(object())
    now = time.time()
    middleware._hits = {
        "stale": [now - 1000.0],
        "active": [now - 1.0],
    }
    middleware._last_prune = time.monotonic() - 400
    middleware._prune_stale_clients()
    assert "stale" not in middleware._hits
    assert "active" in middleware._hits


def test_rate_limit_keeps_entries_within_window() -> None:
    middleware = RateLimitMiddleware(object())
    now = time.time()
    middleware._hits = {
        "recent": [now - 10.0],
        "older": [now - 200.0],
    }
    middleware._last_prune = time.monotonic() - 400
    middleware._prune_stale_clients()
    assert "recent" in middleware._hits
    assert "older" not in middleware._hits
