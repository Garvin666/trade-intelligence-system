"""联网搜索接口与回退逻辑测试。"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEST_DB = PROJECT_ROOT / "tmp" / "test_backend_state_search.db"
_TEST_DB.unlink(missing_ok=True)
os.environ["BACKEND_STATE_DB"] = str(_TEST_DB)

from fastapi.testclient import TestClient  # noqa: E402

from src.api.app import app  # noqa: E402

client = TestClient(app)


def test_search_endpoint_mock_provider() -> None:
    resp = client.get("/api/search", params={"q": "mini dehumidifier", "provider": "mock"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["provider"] == "mock"
    assert payload["fallback_used"] is False
    assert payload["results"]
    assert all("title" in item for item in payload["results"])


def test_search_mock_results_include_links() -> None:
    resp = client.get("/api/search", params={"q": "mini dehumidifier", "provider": "mock"})
    payload = resp.json()
    assert payload["results"]
    for item in payload["results"]:
        assert item.get("link")
        assert item["link"].startswith("http")


def test_search_endpoint_requires_query() -> None:
    resp = client.get("/api/search")
    assert resp.status_code == 422


def test_search_test_endpoint_defaults_query_with_mock() -> None:
    resp = client.post(
        "/api/search/test",
        json={"search_provider": "mock", "search_max_results": 3},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["query"]
    assert payload["results"]
    assert len(payload["results"]) <= 3


def test_search_fallback_on_invalid_provider() -> None:
    resp = client.get("/api/search", params={"q": "pet products", "provider": "invalid"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["fallback_used"] is True
    assert payload["results"]


def test_research_only_endpoint_with_mock() -> None:
    resp = client.post(
        "/api/search/research",
        json={
            "keyword": "mini dehumidifier",
            "market": "us",
            "search_provider": "mock",
            "search_max_results": 3,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    research = payload.get("research", {})
    assert research.get("ai_used") is False
    assert research.get("steps")
    assert "完成" in research.get("summary", "")


def test_four_brain_research_without_ai_uses_research_only() -> None:
    resp = client.post(
        "/api/four-brain",
        json={
            "keyword": "pet feeder",
            "market": "sea",
            "research": True,
            "search_provider": "mock",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ai"]["research_only"] is True
    assert payload["research"]["ai_used"] is False
