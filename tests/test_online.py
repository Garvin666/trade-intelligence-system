"""联网测试：真实搜索路径、自检报告与 /api/search/test 端点。"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEST_DB = PROJECT_ROOT / "tmp" / "test_backend_state_online.db"
_TEST_DB.unlink(missing_ok=True)
os.environ["BACKEND_STATE_DB"] = str(_TEST_DB)

from fastapi.testclient import TestClient  # noqa: E402

from src.api import services  # noqa: E402
from src.api.app import app  # noqa: E402

client = TestClient(app)


def _fake_online_search(query: str, max_results: int, provider: str) -> dict:
    return {
        "provider": provider,
        "fallback_used": False,
        "results": [
            {
                "title": f"{query} A",
                "snippet": "snippet A",
                "link": "https://example.com/a",
            },
            {
                "title": f"{query} B",
                "snippet": "snippet B",
                "link": "https://example.com/b",
            },
        ][:max_results],
    }


def _fake_fallback_search(query: str, max_results: int, provider: str) -> dict:
    return {
        "provider": provider,
        "fallback_used": True,
        "results": [{"title": f"模拟搜索结果：{query}", "snippet": "offline", "link": ""}],
    }


def test_online_test_reports_real_network_success() -> None:
    report = services.online_test(
        query="pet feeder",
        max_results=2,
        provider="duckduckgo_html",
        search_fn=_fake_online_search,
    )
    assert report["ok"] is True
    assert report["provider"] == "duckduckgo_html"
    assert report["results_count"] == 2
    assert report["linked_count"] == 2
    assert report["first_links"][0] == "https://example.com/a"
    assert report["latency_ms"] >= 0


def test_online_test_marks_fallback_and_allow_flag() -> None:
    report = services.online_test(
        query="pet feeder",
        max_results=2,
        provider="duckduckgo_html",
        search_fn=_fake_fallback_search,
    )
    assert report["ok"] is False
    assert report["fallback_used"] is True
    assert report["linked_count"] == 0

    allowed = services.online_test(
        query="pet feeder",
        max_results=2,
        provider="duckduckgo_html",
        allow_fallback=True,
        search_fn=_fake_fallback_search,
    )
    assert allowed["ok"] is True


def test_online_test_real_network_path_shape() -> None:
    """真实调用 DuckDuckGo 联网路径；离线时也须返回标注回退的结构化结果。"""
    report = services.online_test(
        query="smart pet feeder",
        max_results=2,
        provider="duckduckgo_html",
    )
    assert report["provider"] == "duckduckgo_html"
    assert isinstance(report["fallback_used"], bool)
    assert report["results_count"] >= 0
    if report["fallback_used"]:
        # 回退结果也会补齐可点击的 DuckDuckGo 检索链接，但必须保留回退标记
        assert report["ok"] is False
    else:
        assert report["linked_count"] > 0
        assert report["ok"] is True


def test_search_test_endpoint_real_provider() -> None:
    resp = client.post(
        "/api/search/test",
        json={
            "query": "mini dehumidifier",
            "provider": "duckduckgo_html",
            "max_results": 2,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["provider"] == "duckduckgo_html"
    assert isinstance(payload.get("ok"), bool)
    if payload.get("ok"):
        assert isinstance(payload["results"], list)
    else:
        assert payload.get("error")
