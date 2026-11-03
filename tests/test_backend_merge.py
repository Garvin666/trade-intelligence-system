"""Regression tests for the merged backend, quality gates and decision fixes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import app as app_module
from src.api.app import app
from src.config import OUTPUT_DIR
from src.data.crawl_quality import build_crawl_quality

client = TestClient(app)


def test_crawl_quality_marks_mock_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.data import crawl_quality

    mock_customs = tmp_path / "customs.json"
    mock_customs.write_text(
        json.dumps(
            {
                "provider": "mock",
                "fallback_used": True,
                "rows": [{"category": "cn_latiao", "source": "mock"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(crawl_quality, "VERIFIED_STATIC_CACHE", {})
    monkeypatch.setattr(crawl_quality, "SOURCE_FILES", {"customs": mock_customs})
    quality = build_crawl_quality(
        {
            "crawler": {"provider": "wikimedia_search", "fallback_used": False, "rows": 5},
            "policy": {"provider": "crawler", "fallback_used": False, "rows": 5},
            "customs": {"provider": "mock", "fallback_used": True, "rows": 5},
        }
    )
    assert quality["sources"]["customs"]["mode"] == "mock"
    assert quality["decision_data_ready"] is False


def test_crawl_quality_accepts_verified_static_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.data import crawl_quality

    cache = tmp_path / "hs.csv"
    cache.write_text("code,description\n9403,test\n", encoding="utf-8")
    mock_customs = tmp_path / "customs-mock.json"
    mock_customs.write_text(
        json.dumps(
            {
                "provider": "mock",
                "fallback_used": True,
                "rows": [{"category": "cn_latiao", "source": "mock"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(crawl_quality, "VERIFIED_STATIC_CACHE", {"customs": cache})
    monkeypatch.setattr(crawl_quality, "SOURCE_FILES", {"customs": mock_customs})
    quality = build_crawl_quality(
        {
            "crawler": {"provider": "wikimedia_search", "fallback_used": False, "rows": 5},
            "policy": {"provider": "crawler", "fallback_used": False, "rows": 5},
            "customs": {"provider": "mock", "fallback_used": True, "rows": 5},
        }
    )
    assert quality["sources"]["customs"]["mode"] == "cache"


def test_crawl_quality_accepts_mixed_real_crawler_combos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.data import crawl_quality

    snapshot = tmp_path / "crawler.json"
    now = datetime.now(timezone.utc).isoformat()
    combos = []
    for index in range(10):
        real = index < 8
        combos.append(
            {
                "category": f"cat_{index}",
                "market": "us",
                "generated_at": now,
                "provider": "wikimedia_search" if real else "mock",
                "fallback_used": not real,
                "source_count": 4 if real else 1,
                "sources": [
                    {
                        "title": "source",
                        "snippet": "snippet",
                        "link": f"https://en.wikipedia.org/wiki/{index}",
                        "source": "wikimedia_search" if real else "mock",
                    }
                ],
            }
        )
    snapshot.write_text(
        json.dumps({"generated_at": now, "provider": "mock", "fallback_used": True, "combos": combos}),
        encoding="utf-8",
    )
    monkeypatch.setattr(crawl_quality, "SOURCE_FILES", {"crawler": snapshot})
    monkeypatch.setattr(crawl_quality, "CRAWLER_CACHE_DIR", tmp_path / "cache")
    quality = build_crawl_quality(
        {
            "crawler": {"provider": "mock", "fallback_used": True, "rows": 10, "updated_at": now},
            "policy": {"provider": "crawler", "fallback_used": False, "rows": 5, "updated_at": now},
            "customs": {"provider": "comtrade", "fallback_used": False, "rows": 5, "updated_at": now},
        }
    )
    assert quality["sources"]["crawler"]["mode"] == "real"
    assert quality["sources"]["crawler"]["real_count"] == 8
    assert quality["sources"]["crawler"]["mock_count"] == 2
    assert quality["decision_data_ready"] is True


def test_crawl_quality_marks_all_mock_crawler_combos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.data import crawl_quality

    snapshot = tmp_path / "crawler.json"
    now = datetime.now(timezone.utc).isoformat()
    snapshot.write_text(
        json.dumps(
            {
                "generated_at": now,
                "provider": "mock",
                "fallback_used": True,
                "combos": [
                    {
                        "category": "cn_latiao",
                        "market": "us",
                        "fallback_used": True,
                        "source_count": 1,
                        "sources": [{"title": "mock", "link": "", "source": "mock"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(crawl_quality, "SOURCE_FILES", {"crawler": snapshot})
    monkeypatch.setattr(crawl_quality, "CRAWLER_CACHE_DIR", tmp_path / "cache")
    quality = build_crawl_quality(
        {
            "crawler": {"provider": "mock", "fallback_used": True, "rows": 1, "updated_at": now},
            "policy": {"provider": "crawler", "fallback_used": False, "rows": 5, "updated_at": now},
            "customs": {"provider": "comtrade", "fallback_used": False, "rows": 5, "updated_at": now},
        }
    )
    assert quality["sources"]["crawler"]["mode"] == "mock"
    assert quality["decision_data_ready"] is False


def test_crawl_quality_accepts_fresh_crawler_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.data import crawl_quality

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    (cache_dir / "home_us.json").write_text(
        json.dumps(
            {
                "meta": {
                    "category": "cn_latiao",
                    "market": "us",
                    "generated_at": now,
                    "offline": False,
                },
                "queries": [
                    {
                        "provider": "wikimedia_search",
                        "results": [
                            {
                                "title": "Home",
                                "link": "https://en.wikipedia.org/wiki/Home",
                                "source": "wikimedia_search",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(crawl_quality, "SOURCE_FILES", {"crawler": tmp_path / "missing-crawler.json"})
    monkeypatch.setattr(crawl_quality, "CRAWLER_CACHE_DIR", cache_dir)
    quality = build_crawl_quality(
        {
            "crawler": {"provider": "mock", "fallback_used": True, "rows": 0, "updated_at": now},
            "policy": {"provider": "crawler", "fallback_used": False, "rows": 5, "updated_at": now},
            "customs": {"provider": "comtrade", "fallback_used": False, "rows": 5, "updated_at": now},
        }
    )
    assert quality["sources"]["crawler"]["mode"] == "cache"
    assert quality["decision_data_ready"] is True


def test_decision_gate_returns_503_when_data_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app_module.services,
        "data_status",
        lambda: {
            "crawl_quality": {
                "decision_data_ready": False,
                "reasons": ["customs 无真实或缓存数据（mode=mock）"],
            }
        },
    )
    resp = client.get("/api/recommendations?top=3")
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "data_gap"


def test_recommendations_top_contains_no_no_go_and_at_least_one_go() -> None:
    resp = client.get("/api/recommendations?top=10")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 10
    assert all(item["recommendable"] for item in items)
    assert all(item["verdict"] != "No-Go" for item in items)
    assert any(item["verdict"] == "Go" for item in items)


def test_dashboard_data_returns_stable_recommendable_top20() -> None:
    resp = client.get("/api/dashboard-data")
    assert resp.status_code == 200
    items = resp.json()["recommendations"]
    assert len(items) == 20
    assert all(item["verdict"] in {"Go", "Conditional"} for item in items)
    assert [item["rank"] for item in items] == list(range(1, 21))
    scores = [item["six_dimension_score"] for item in items]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


def test_dashboard_data_top20_ignores_category_market_filter() -> None:
    resp_all = client.get("/api/dashboard-data")
    resp_filtered = client.get(
        "/api/dashboard-data",
        params={"category": "cn_changsha_mifen", "market": "us"},
    )
    assert resp_all.status_code == 200
    assert resp_filtered.status_code == 200
    all_items = resp_all.json()["recommendations"]
    filtered_items = resp_filtered.json()["recommendations"]
    assert len(filtered_items) == 20

    def combo_keys(items: list[dict]) -> list[tuple[str, str]]:
        return [(item["category"], item["market"]) for item in items]

    assert combo_keys(all_items) == combo_keys(filtered_items)


def test_trade_decision_clamps_extreme_margin() -> None:
    resp = client.get(
        "/api/trade/decision",
        params={
            "category": "cn_changsha_mifen",
            "market": "us",
            "unit_price_usd": 25,
            "procurement_cost_cny": 60,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["margin_pct"] >= -200
    assert data["clamped"] is True
    assert data["warnings"]


def test_data_status_contains_quality_and_real_blocks() -> None:
    resp = client.get("/api/data/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "crawl_quality" in data
    assert "decision_data_ready" in data
    assert "real_data" in data
    assert "sources" in data["crawl_quality"]


def test_real_validation_artifacts_exist() -> None:
    status = OUTPUT_DIR / "real" / "status.json"
    validation = OUTPUT_DIR / "real" / "validation.json"
    assert status.exists()
    assert validation.exists()
    payload = json.loads(status.read_text(encoding="utf-8"))
    assert "evidence_available_combos" in payload
