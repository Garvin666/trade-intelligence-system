"""性能优化回归测试：缓存命中、字段兼容与搜索复用。

覆盖 2026-08-19 性能优化批次的 P0/P1 关键改动，避免后续改动
把 data_status/intel/搜索/自检/四脑 EDA 的缓存与兼容语义悄悄回退。
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEST_DB = PROJECT_ROOT / "tmp" / "test_backend_state_perf.db"
_TEST_DB.unlink(missing_ok=True)
os.environ["BACKEND_STATE_DB"] = str(_TEST_DB)

from fastapi.testclient import TestClient  # noqa: E402

from src.api.app import app  # noqa: E402
from src.api import services  # noqa: E402
from src.data import search as search_module  # noqa: E402
from src.four_brain import data_tools  # noqa: E402
from src.four_brain import engine as four_brain  # noqa: E402
from src import checks as env_checks  # noqa: E402

client = TestClient(app)


def test_data_status_cache_avoids_repeated_coverage_write(monkeypatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(services, "write_coverage", lambda quality: calls.append(quality))
    services._DATA_STATUS_CACHE.clear()
    first = services.data_status()
    second = services.data_status()
    assert first is second
    assert len(calls) == 1


def test_intel_endpoint_cache_returns_same_object() -> None:
    services.invalidate_caches()
    filters = {"category": "cn_changsha_mifen", "market": "us"}
    first = services.competition_index(filters)
    second = services.competition_index(filters)
    assert first is second


def test_trade_report_filter_is_backward_compatible() -> None:
    services.invalidate_caches()
    full = services.trade_report()
    assert "filtered" not in full
    filtered = services.trade_report(
        {
            "market": "us",
            "risk_level": "high",
            "limit": "10",
            "offset": "0",
        }
    )
    assert filtered["filtered"] == len(filtered["rows"])
    assert all(row["market"] == "us" for row in filtered["rows"])
    assert all(row["risk_level"] == "high" for row in filtered["rows"])
    assert len(filtered["rows"]) <= 10

    resp = client.get(
        "/api/trade/report",
        params={"market": "us", "limit": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["filtered"] == len(body["rows"])
    assert all(row["market"] == "us" for row in body["rows"])


def test_chain_search_cache_hits_without_calling_providers() -> None:
    search_module._CHAIN_CACHE.clear()
    calls = {"n": 0}

    def crawler(query: str, max_results: int = 5, config: dict | None = None):
        calls["n"] += 1
        return {
            "results": [{"title": "ok", "snippet": "s", "link": "https://e.com"}],
            "fallback_used": False,
            "provider": "crawler",
            "pageviews": [],
        }

    def web(*args, **kwargs):
        raise AssertionError("缓存命中时不应调用 web fallback")

    def mock(*args, **kwargs):
        raise AssertionError("缓存命中时不应调用 mock fallback")

    first = search_module.chain_search(
        "query",
        5,
        provider="crawler",
        crawler_fn=crawler,
        web_fn=web,
        mock_fn=mock,
    )
    second = search_module.chain_search(
        "query",
        5,
        provider="crawler",
        crawler_fn=crawler,
        web_fn=web,
        mock_fn=mock,
    )
    assert calls["n"] == 1
    assert first == second
    search_module._CHAIN_CACHE.clear()


def test_search_web_cache_hits_without_second_call(monkeypatch) -> None:
    data_tools._SEARCH_RESULT_CACHE.clear()
    calls = {"n": 0}

    def fake_impl(query: str, max_results: int = 5, config: dict | None = None):
        calls["n"] += 1
        return [
            {"title": "t", "snippet": "s", "link": "https://example.com"}
        ]

    monkeypatch.setattr(data_tools, "_search_web_raw_impl", fake_impl)
    first = data_tools.search_web("q", 3, {"provider": "mock"})
    second = data_tools.search_web("q", 3, {"provider": "mock"})
    assert calls["n"] == 1
    assert first == second
    data_tools._SEARCH_RESULT_CACHE.clear()


def test_check_import_smoke_uses_cache(monkeypatch) -> None:
    env_checks._IMPORT_SMOKE_CACHE.clear()
    calls = {"n": 0}

    def fake_impl():
        calls["n"] += 1
        return ("ok", "全部模块可导入")

    monkeypatch.setattr(env_checks, "_check_import_smoke_impl", fake_impl)
    first = env_checks._check_import_smoke()
    second = env_checks._check_import_smoke()
    assert calls["n"] == 1
    assert first[0] == "ok"
    assert "基于缓存" in second[1]


def test_eda_summary_cache_and_fields() -> None:
    data = {
        "history": [
            {
                "date": "2026-01-01",
                "category": "cn_changsha_mifen",
                "market": "us",
                "sales_volume": 10,
                "competition_index": 20,
            },
            {
                "date": "2026-01-01",
                "category": "cn_changsha_mifen",
                "market": "us",
                "sales_volume": 10,
                "competition_index": 20,
            },
        ]
    }
    first = four_brain._build_eda_summary(data)
    second = four_brain._build_eda_summary(data)
    assert first is second
    for key in ("summary", "columns", "anomalies", "ab_tests"):
        assert key in first
    assert first["summary"]["rows"] == 2
    assert first["summary"]["duplicate_rows"] == 1
