"""Regression tests for the single-process backend jobs and MCP mount."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api import jobs, mcp_bridge, services
from src.api.app import app

client = TestClient(app)


def test_health_includes_mcp_and_jobs() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "mcp" in data
    assert isinstance(data["mcp"], bool)
    assert "jobs" in data
    assert "items" in data["jobs"]


def test_jobs_endpoint_lists_registry() -> None:
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["items"]}
    assert {"daily_update", "market_daily", "control_run", "policy_refresh"} <= names


def test_mcp_route_mounted_when_available() -> None:
    if mcp_bridge.available():
        assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_job_start_unknown_returns_404() -> None:
    resp = client.post("/api/jobs/nope/start", json={})
    assert resp.status_code == 404


def test_daily_update_argv_builder() -> None:
    argv = jobs._daily_update_argv(
        {"offline": True, "skip_pipeline": True, "skip_rebuild": True, "workers": 4}
    )
    assert argv == ["--offline", "--skip-pipeline", "--skip-rebuild", "--workers", "4"]


def test_invalidate_caches_clears_cache() -> None:
    services._CACHE["test-key"] = (time.time(), {"x": 1})
    services.history_frame()
    services.invalidate_caches()
    assert services._CACHE == {}
    assert services.history_frame.cache_info().currsize == 0


def _wait_terminal(name: str, timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = jobs.status(name)
        if state["status"] in {"done", "error", "cancelled"}:
            return state
        time.sleep(0.05)
    raise AssertionError(f"job {name} did not reach a terminal state in time")


def test_job_lifecycle_with_fake_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    entered = threading.Event()
    release = threading.Event()

    def fake_runner(payload: dict[str, Any], progress) -> dict[str, Any]:
        captured["payload"] = payload
        progress("1/1", "working")
        entered.set()
        release.wait(timeout=5)
        return {"ok": True}

    monkeypatch.setattr(jobs, "_run_market_daily", fake_runner)
    started = jobs.start("market_daily", {"date": "2026-08-15"})
    assert started["status"] == "running"
    entered.wait(timeout=5)
    assert jobs.status("market_daily")["status"] == "running"
    release.set()
    state = _wait_terminal("market_daily")
    assert state["status"] == "done"
    assert state["result"] == {"ok": True}
    assert captured["payload"] == {"date": "2026-08-15"}


def test_exclusive_job_rejects_second_start(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = threading.Event()
    release = threading.Event()

    def slow_runner(payload: dict[str, Any], progress) -> dict[str, Any]:
        gate.set()
        release.wait(timeout=5)
        return {"ok": True}

    monkeypatch.setattr(jobs, "_run_market_daily", slow_runner)
    jobs.start("market_daily", {})
    gate.wait(timeout=5)
    with pytest.raises(ValueError):
        jobs.start("market_daily", {})
    release.set()
    _wait_terminal("market_daily")
