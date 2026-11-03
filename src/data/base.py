"""Shared helpers for the data-crawling adapters.

Provides the small, repeated primitives that every adapter used to
hand-roll: timestamps, deterministic mock seeds, and JSON persistence.
Adapters keep their public ``empty_*_payload`` / ``save_latest_*`` /
``load_latest_*`` names as thin wrappers around these helpers so callers
and tests are unaffected.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_PAYLOAD_KEYS = (
    "generated_at",
    "date",
    "offline",
    "fallback_used",
    "provider",
    "rows",
    "source_count",
    "errors",
)


def generated_at() -> str:
    """ISO timestamp with local timezone offset, to the second."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today() -> str:
    """Local date as ``YYYY-MM-DD``."""
    return datetime.now().date().isoformat()


def seed_int(*parts: Any) -> int:
    """Deterministic integer in ``[0, 0xFFFFFFFF]`` from string parts."""
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def seed_for(*parts: Any) -> float:
    """Deterministic float in ``[0, 1)`` from a set of string parts.

    Used by the mock row generators so offline data is stable across runs.
    """
    return seed_int(*parts) / 0xFFFFFFFF


def pageview_trend_pct(items: Any) -> float:
    """Percent change between the recent half and earlier half of pageviews.

    ``items`` is an iterable of ``{"date": str, "views": number}`` records.
    Returns 0.0 when there are fewer than two dated rows.
    """
    rows = [
        item
        for item in items
        if str(item.get("date") or "") and item.get("views") is not None
    ]
    rows.sort(key=lambda item: str(item.get("date", "")))
    if len(rows) < 2:
        return 0.0
    mid = max(1, len(rows) // 2)
    recent = [float(item["views"]) for item in rows[mid:]]
    previous = [float(item["views"]) for item in rows[:mid]]
    avg_recent = sum(recent) / len(recent)
    avg_previous = sum(previous) / len(previous)
    if avg_previous <= 0:
        return 0.0
    return round((avg_recent - avg_previous) / avg_previous * 100.0, 2)


def write_json(payload: dict[str, Any], path: str | Path) -> Path:
    """Write a JSON payload, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def save_latest(payload: dict[str, Any], path: str | Path) -> Path:
    """Persist the latest snapshot and return its path."""
    return write_json(payload, path)


def load_latest(
    path: str | Path,
    default: dict[str, Any] | None = None,
    *,
    ensure_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Read a latest-snapshot JSON, or return the default on miss/corruption."""
    path = Path(path)
    if not path.exists():
        return dict(default or {})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default or {})
    if not isinstance(payload, dict):
        return dict(default or {})
    for key in ensure_keys:
        payload.setdefault(key, None)
    return payload


def base_payload(
    *,
    provider: str | None = None,
    offline: bool = False,
    fallback_used: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """Build an adapter payload with the shared timestamp/flag keys."""
    payload: dict[str, Any] = {
        "generated_at": generated_at(),
        "date": today(),
        "offline": bool(offline),
        "fallback_used": bool(fallback_used),
        "provider": provider,
    }
    payload.update(extra)
    return payload


__all__ = [
    "DEFAULT_PAYLOAD_KEYS",
    "base_payload",
    "generated_at",
    "load_latest",
    "pageview_trend_pct",
    "save_latest",
    "seed_for",
    "seed_int",
    "today",
    "write_json",
]
