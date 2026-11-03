"""In-memory global AI configuration for the unified backend.

The demo page lets the user enter an OpenAI-compatible API key, base URL and
model once.  In online mode the frontend keeps only non-sensitive settings
(base URL, model, provider, search options) in localStorage and posts the
API key here so backend-mediated calls (four-brain, connectivity test, control
benchmark) can reuse the same configuration; the raw key is deliberately NOT
written to localStorage.  In the offline single-file demo (no backend) the
browser keeps the key locally as an explicit exception for browser-direct use.
The search provider, key and URL are stored the same way so research and
connectivity tests can reuse the page-level configuration too.
The key is kept only in process memory and is never written to disk or
returned to clients.
"""

from __future__ import annotations

import os
import threading
from typing import Any

from src.four_brain.ai_provider import normalize_base_url

_LOCK = threading.RLock()
_STATE: dict[str, Any] = {
    "api_key": "",
    "base_url": "",
    "model": "",
    "preset": "",
    "timeout": 120,
    "search_provider": "",
    "search_api_key": "",
    "search_api_url": "",
    "search_max_results": 5,
}


def set_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Merge a partial config into memory and return the masked status."""
    with _LOCK:
        for key in ("api_key", "base_url", "model", "preset"):
            if key in payload:
                value = str(payload.get(key) or "").strip()
                if key == "base_url":
                    value = normalize_base_url(value)
                _STATE[key] = value
        for key in ("search_provider", "search_api_key", "search_api_url"):
            if key in payload:
                _STATE[key] = str(payload.get(key) or "").strip()
        if "timeout" in payload:
            try:
                _STATE["timeout"] = max(1, min(600, int(payload["timeout"])))
            except (TypeError, ValueError):
                pass
        if "search_max_results" in payload:
            try:
                raw = int(payload["search_max_results"])
            except (TypeError, ValueError):
                raw = (
                    5
                    if str(payload.get("search_max_results") or "").strip() == ""
                    else None
                )
            if raw is not None:
                _STATE["search_max_results"] = max(1, min(20, raw))
    return get_status()


def clear_config() -> dict[str, Any]:
    with _LOCK:
        _STATE["api_key"] = ""
        _STATE["base_url"] = ""
        _STATE["model"] = ""
        _STATE["preset"] = ""
        _STATE["timeout"] = 120
        _STATE["search_provider"] = ""
        _STATE["search_api_key"] = ""
        _STATE["search_api_url"] = ""
        _STATE["search_max_results"] = 5
    return get_status()


def get_status() -> dict[str, Any]:
    """Return a masked status suitable for the frontend."""
    with _LOCK:
        memory_key = str(_STATE.get("api_key") or "").strip()
        env_key = str(os.environ.get("OPENAI_API_KEY") or "").strip()
        key = memory_key or env_key
        base_url = normalize_base_url(
            str(
                _STATE.get("base_url")
                or os.environ.get("OPENAI_BASE_URL")
                or "https://api.deepseek.com/v1"
            ).strip()
        )
        model = str(
            _STATE.get("model")
            or os.environ.get("OPENAI_MODEL")
            or "deepseek-chat"
        ).strip()
        timeout = int(_STATE.get("timeout") or 120)
        search_provider = str(
            _STATE.get("search_provider")
            or os.environ.get("SEARCH_PROVIDER")
            or "duckduckgo_html"
        ).strip()
        search_key = str(_STATE.get("search_api_key") or "").strip()
        search_max_results = int(_STATE.get("search_max_results") or 5)
        source = "memory" if memory_key else ("env" if env_key else "none")
        return {
            "configured": bool(key and model),
            "has_key": bool(memory_key),
            "model": model,
            "base_url": base_url or "https://api.deepseek.com/v1",
            "preset": str(_STATE.get("preset") or ""),
            "timeout": timeout,
            "source": source,
            "search_provider": search_provider,
            "search_has_key": bool(search_key),
            "search_max_results": max(1, min(20, search_max_results)),
        }


def get_api_key() -> str:
    with _LOCK:
        return str(_STATE.get("api_key") or "").strip()


def get_base_url() -> str:
    with _LOCK:
        return normalize_base_url(str(_STATE.get("base_url") or "").strip())


def get_model() -> str:
    with _LOCK:
        return str(_STATE.get("model") or "").strip()


def get_timeout() -> int:
    with _LOCK:
        return int(_STATE.get("timeout") or 45)


def get_search_provider() -> str:
    with _LOCK:
        return str(_STATE.get("search_provider") or "").strip()


def get_search_api_key() -> str:
    with _LOCK:
        return str(_STATE.get("search_api_key") or "").strip()


def get_search_api_url() -> str:
    with _LOCK:
        return str(_STATE.get("search_api_url") or "").strip()


def get_search_max_results() -> int:
    with _LOCK:
        return int(_STATE.get("search_max_results") or 5)
