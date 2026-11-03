"""AI analysis speed: four brains and research searches run in parallel."""

from __future__ import annotations

import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.api import brain_bridge  # noqa: E402
from src.four_brain import engine as four_brain  # noqa: E402

MINI_DATA = {
    "history": [
        {
            "date": "2026-01-01",
            "category": "cn_changsha_mifen",
            "market": "us",
            "sales_volume": 10,
            "search_index": 10,
            "competition_index": 10,
            "price_median": 10,
        }
    ],
    "recommendations": [],
}


class SlowProvider:
    configured = True

    def __init__(self, delay: float = 0.4, fail_keyword: str = "") -> None:
        self.delay = delay
        self.fail_keyword = fail_keyword
        self.active = 0
        self.max_active = 0
        self.calls = 0
        self._lock = threading.Lock()

    def chat_json(self, system: str, user: str, temperature: float = 0.2) -> dict:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.calls += 1
        try:
            time.sleep(self.delay)
            if self.fail_keyword and self.fail_keyword in system:
                raise RuntimeError("brain failed")
            return {
                "score": 80,
                "confidence": 0.8,
                "direction": "推荐",
                "evidence": ["e1"],
                "summary": "s",
                "report": "r",
            }
        finally:
            with self._lock:
                self.active -= 1

    def status(self) -> dict:
        return {"configured": True}


class SlowSearch:
    def __init__(self, delay: float = 0.3) -> None:
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def __call__(
        self,
        query: str,
        max_results: int = 3,
        provider: str = "crawler",
        api_key: str | None = None,
        api_url: str | None = None,
    ) -> dict:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(self.delay)
            return {
                "provider": provider,
                "fallback_used": False,
                "results": [
                    {"title": f"{query} t", "snippet": "s", "link": "https://example.com"}
                ],
            }
        finally:
            with self._lock:
                self.active -= 1


def test_four_brain_ai_calls_run_in_parallel() -> None:
    payload = dict(four_brain.DEFAULT_PAYLOAD)
    provider = SlowProvider(delay=0.4)
    start = time.monotonic()
    result = four_brain.analyze_with_ai(payload, MINI_DATA, provider)
    elapsed = time.monotonic() - start
    assert provider.calls == 4
    assert provider.max_active >= 2
    assert elapsed < 1.2
    assert result["ai"]["used"] is True
    assert not result["ai"]["errors"]
    assert len(result["brains"]) == 4


def test_four_brain_single_brain_failure_falls_back() -> None:
    payload = dict(four_brain.DEFAULT_PAYLOAD)
    provider = SlowProvider(delay=0.05, fail_keyword="舆情")
    result = four_brain.analyze_with_ai(payload, MINI_DATA, provider)
    assert result["ai"]["errors"]
    assert any("sentiment" in error for error in result["ai"]["errors"])
    assert result["brains"]["market"]["ai_source"] is True
    assert "ai_error" in result["brains"]["sentiment"]


def test_research_only_runs_searches_in_parallel(monkeypatch) -> None:
    assert brain_bridge.available()
    search = SlowSearch(delay=0.3)
    monkeypatch.setattr(brain_bridge, "search", search)
    monkeypatch.setattr(brain_bridge, "_resolve_data", lambda payload: MINI_DATA)
    payload = {
        "keyword": "mini dehumidifier",
        "market": "us",
        "research": True,
        "search_provider": "crawler",
        "search_max_results": 3,
    }
    start = time.monotonic()
    result = brain_bridge.research_only(payload)
    elapsed = time.monotonic() - start
    assert search.max_active >= 2
    assert elapsed < 0.9
    steps = result["research"]["steps"]
    assert [step["step"] for step in steps] == [1, 2, 3, 4]
    assert result["research"]["provider"] == "crawler"
    assert result["research"]["sources"]
