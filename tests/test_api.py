"""FastAPI 统一后端服务测试。"""

from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEST_DB = PROJECT_ROOT / "tmp" / "test_backend_state.db"
_TEST_DB.unlink(missing_ok=True)
os.environ["BACKEND_STATE_DB"] = str(_TEST_DB)

from fastapi.testclient import TestClient  # noqa: E402

from src.config import CATEGORIES, MARKETS  # noqa: E402
from src.api.app import app  # noqa: E402
from src.api import brain_bridge as brain_bridge_module  # noqa: E402

client = TestClient(app)


def test_health_endpoint() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert "data_status" in payload
    assert payload["data_status"]["data_as_of"]


def test_data_status_endpoint() -> None:
    resp = client.get("/api/data/status")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["data_as_of"]
    assert "online" in payload
    assert payload["next_update"]
    assert "trends" in payload
    assert "platform_rankings" in payload
    assert "market_daily" in payload
    assert "suppliers" in payload


def test_data_suppliers_endpoint() -> None:
    resp = client.get("/api/data/suppliers")
    assert resp.status_code == 200
    payload = resp.json()
    assert "provider" in payload
    assert "fallback_used" in payload
    assert "rows" in payload


def test_examples_endpoint() -> None:
    resp = client.get("/api/examples")
    assert resp.status_code == 200
    payload = resp.json()
    assert {"dashboard", "four_brain", "trade", "launch_report", "workflow"} <= set(payload)
    dashboard = payload["dashboard"]
    assert len(dashboard) >= 10
    pairs = [(item["category"], item["market"]) for item in dashboard]
    assert len(pairs) == len(set(pairs))
    for item in dashboard:
        assert item["id"]
        assert item["label"]
        assert item["category"] in CATEGORIES
        assert item["market"] in MARKETS
    assert payload["four_brain"]
    assert payload["trade"]


def test_anomalies_endpoint() -> None:
    resp = client.get("/api/anomalies")
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload.get("rows"), list)
    assert "source_count" in payload


def test_hs_codes_search_endpoint() -> None:
    resp = client.get("/api/trade/hs-codes", params={"q": "1902"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] >= 1
    assert any("1902" in item["hs_code"] for item in payload["items"])


def test_eda_report_path_traversal_blocked() -> None:
    resp = client.get("/eda/reports/..%2Fdata_status.json")
    assert resp.status_code == 404


def test_four_brain_batch_rejects_empty() -> None:
    resp = client.post("/api/four-brain/batch", json={"items": []})
    assert resp.status_code == 400


def test_four_brain_batch_runs(monkeypatch) -> None:
    def fake_analyze(payload, use_ai=False):
        return {
            "keyword": payload.get("keyword"),
            "category": "cn_changsha_mifen",
            "verdict": "Go",
            "score": 78,
        }

    monkeypatch.setattr(brain_bridge_module, "analyze", fake_analyze)
    resp = client.post(
        "/api/four-brain/batch",
        json={"items": [{"keyword": "辣条 latiao spicy snack", "market": "us"}]},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["summary"]["total"] == 1
    assert payload["summary"]["ok"] == 1
    assert payload["items"][0]["result"]["verdict"] == "Go"


def test_four_brain_batch_item_ai_flag_enables_model(monkeypatch) -> None:
    seen: list[tuple[str, bool]] = []

    def fake_analyze(payload, use_ai=False):
        seen.append((str(payload.get("keyword")), bool(use_ai)))
        return {"keyword": payload.get("keyword"), "verdict": "Go", "score": 78}

    monkeypatch.setattr(brain_bridge_module, "analyze", fake_analyze)
    resp = client.post(
        "/api/four-brain/batch",
        json={"items": [{"keyword": "辣条 latiao spicy snack", "market": "us", "ai": True}]},
    )
    assert resp.status_code == 200
    assert seen == [("辣条 latiao spicy snack", True)]


def test_dashboard_data_cache_invalidates_on_file_change(monkeypatch, tmp_path) -> None:
    """四脑数据文件同一版本只读一次，文件更新后自动重读。"""
    import json

    from src.api import brain_bridge

    path = tmp_path / "dashboard-data.json"
    path.write_text(json.dumps({"history": []}), encoding="utf-8")
    monkeypatch.setattr(brain_bridge, "DASHBOARD_DATA_FILE", path)

    first = brain_bridge._load_dashboard_data()
    second = brain_bridge._load_dashboard_data()
    assert first is second

    path.write_text(
        json.dumps({"history": [{"date": "2026-01-01"}]}),
        encoding="utf-8",
    )
    third = brain_bridge._load_dashboard_data()
    assert third is not first
    assert third["history"]


def test_policy_events_endpoint() -> None:
    resp = client.get("/api/policy/events")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] >= 2
    assert payload["verified_count"] >= 2
    assert "candidate_count" in payload
    assert "sources" in payload


def test_policy_refresh_endpoint(monkeypatch) -> None:
    from src.api import services as services_module

    def fake_refresh(payload=None):
        return {
            "ok": True,
            "refreshed_at": "2026-08-14T15:00:00+08:00",
            "status": {"verified_events": 3},
            "items": [{"code": "pol-live"}],
            "verified_count": 3,
            "candidate_count": 0,
            "candidate_items": [],
            "sources": {},
            "updated_at": "2026-08-14T15:00:00+08:00",
            "date": "2026-08-14",
            "fallback_used": False,
            "official_only": True,
        }

    monkeypatch.setattr(services_module, "refresh_policy", fake_refresh)
    resp = client.post("/api/policy/refresh", json={"include_search": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["verified_count"] == 3
    assert body["status"]["verified_events"] == 3


def test_trade_decision_endpoint() -> None:
    resp = client.get(
        "/api/trade/decision",
        params={
            "category": "cn_latiao",
            "market": "sea",
            "unit_price_usd": 30.0,
            "procurement_cost_cny": 75.0,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["risk_level"] in {"low", "medium", "high"}
    assert payload["margin_pct"] > 0
    assert payload["financing_level"] in {"可对接供应链金融", "可对接信用贷", "小额试单", "暂不建议"}
    assert "logistics" in payload
    assert payload["hs_code"]
    assert payload["preflight"]["ready"] in {True, False}
    assert payload["osint"]["risk_level"] in {"low", "medium", "high"}


def test_hs_code_endpoint() -> None:
    resp = client.get("/api/trade/hs-code", params={"category": "cn_changsha_mifen", "market": "us"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["hs_code"].startswith("1902")
    assert len(payload["hs_code"]) == 6
    assert payload["verified"] is True

    resp = client.get("/api/trade/hs-code", params={"category": "invalid", "market": "us"})
    assert resp.status_code == 400


def test_trade_decision_invalid_market() -> None:
    resp = client.get(
        "/api/trade/decision",
        params={
            "category": "cn_latiao",
            "market": "invalid",
            "unit_price_usd": 30.0,
            "procurement_cost_cny": 75.0,
        },
    )
    assert resp.status_code == 400


def test_trade_report_endpoint() -> None:
    resp = client.get("/api/trade/report")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["summary"]["combos"] == len(CATEGORIES) * len(MARKETS)
    assert "credit_avg" in payload["summary"]


def test_recommendations_endpoint() -> None:
    resp = client.get("/api/recommendations", params={"top": 3})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 3
    assert "score" in payload["items"][0]


def test_summary_endpoint() -> None:
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["history_rows"] > 0
    assert payload["mape_improvement_pct"] > 0


def test_history_and_forecast_filtering() -> None:
    resp = client.get("/api/history", params={"market": "sea", "limit": 5})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 5
    assert all(item["market"] == "sea" for item in payload["items"])

    resp = client.get("/api/forecast", params={"model": "lightgbm_advanced", "limit": 3})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 3
    assert all(item["model"] == "lightgbm_advanced" for item in payload["items"])


def test_dashboard_data_with_model_filter() -> None:
    resp = client.get(
        "/api/dashboard-data",
        params={"category": "cn_changsha_mifen", "market": "us", "model": "lightgbm_advanced"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["history"]
    assert isinstance(payload["recommendations"], list)
    assert payload["forecast"]
    assert all(item["model"] == "lightgbm_advanced" for item in payload["forecast"])


def test_model_metrics_filtering() -> None:
    resp = client.get("/api/model-metrics", params={"model": "prophet_baseline"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["baseline"]
    assert payload["advanced"] == []


def test_model_metrics_includes_business_metrics() -> None:
    resp = client.get("/api/model-metrics")
    assert resp.status_code == 200
    payload = resp.json()
    assert "business_metrics" in payload
    assert payload["business_metrics"]["calibration"]["status"] == "ok"
    assert payload["business_metrics"]["direction_hit_rate"]["status"] == "ok"


def test_policy_impact_endpoint() -> None:
    resp = client.get(
        "/api/policy/impact",
        params={"event_code": "us-de-minimis-2025"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["event_code"] == "us-de-minimis-2025"
    assert payload["market"] == "us"
    assert payload["affected_count"] > 0
    assert payload["total_categories"] == len(CATEGORIES)
    assert payload["source_type"] == "official"
    assert payload["verified"] is True
    assert payload["policy_type"] == "tariff"
    assert payload["url"].startswith(
        "https://www.federalregister.gov/documents/2025/09/02/"
    )
    assert isinstance(payload["trends_status"], dict)
    assert "available" in payload["trends_status"]
    row = payload["rows"][0]
    assert {"category", "tariff_before", "tariff_after", "margin_before", "margin_after"} <= set(row)
    assert row["verdict_before"] in {"Go", "Conditional", "No-Go"}
    assert row["verdict_after"] in {"Go", "Conditional", "No-Go"}


def test_policy_impact_endpoint_filters_category() -> None:
    resp = client.get(
        "/api/policy/impact",
        params={"event_code": "us-de-minimis-2025", "category": "cn_changsha_mifen", "market": "us"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total_categories"] == 1
    assert payload["rows"][0]["category"] == "cn_changsha_mifen"
    assert payload["rows"][0]["affected"] is True


def test_policy_impact_invalid_event_rejected() -> None:
    resp = client.get(
        "/api/policy/impact",
        params={"event_code": "missing-event"},
    )
    assert resp.status_code == 400
    assert "未知政策事件" in resp.json()["detail"]


def test_policy_impact_eu_flat_customs_duty() -> None:
    resp = client.get(
        "/api/policy/impact",
        params={"event_code": "eu-low-value-vat-2026"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["event_code"] == "eu-low-value-vat-2026"
    assert payload["policy_type"] == "customs"
    assert payload["source_type"] == "official"
    assert payload["url"].startswith("https://eur-lex.europa.eu/")
    assert payload["rate_ad_valorem"] == 0.0
    assert payload["min_duty_usd"] == 3.6
    assert 0 < payload["affected_count"] <= payload["total_categories"]
    assert payload["rows"][0]["affected"] is True


def test_evidence_ledger_endpoint() -> None:
    resp = client.get("/api/evidence/ledger")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["schema_version"] == 1
    assert payload["count"] >= 1
    assert "expired_count" in payload
    assert len(payload["items"]) == payload["count"]
    first = payload["items"][0]
    for field in ("key", "title", "source", "fetched_at", "effective_date", "expires_at"):
        assert field in first
    assert "expiry_status" in first
    assert any(item.get("hs_version") == "HS2022" for item in payload["items"])


def test_control_metrics_endpoint() -> None:
    resp = client.get("/api/control/metrics")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] in {"not_run", "partial", "done", "error"}
    assert payload["source"] in {"missing", "file"}
    assert "system_baseline" in payload
    assert "prophet_mape" in payload["system_baseline"]
    assert "models" in payload
    assert "system_eval" in payload
    assert "model_summary" in payload
    assert payload["model_summary"]["combos"] >= len(CATEGORIES) * len(MARKETS)
    assert payload["total_cells"] >= 0


def test_engineering_status_endpoint() -> None:
    resp = client.get("/api/engineering/status")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["data_as_of"]
    assert "capabilities" in payload
    assert "policy_cost" in payload["capabilities"]
    assert "compliance" in payload["capabilities"]
    assert isinstance(payload["endpoints"], list)
    assert any(item["path"] == "/api/health" for item in payload["endpoints"])
    assert any(item["path"] == "/api/trade/report" for item in payload["endpoints"])


def test_system_eval_endpoint_exposes_gate() -> None:
    resp = client.get("/api/system/eval")
    assert resp.status_code == 200
    payload = resp.json()
    assert "gate" in payload
    assert isinstance(payload["gate"]["passed"], bool)
    assert isinstance(payload["gate"]["failed_metrics"], list)


def test_engineering_status_test_count_falls_back_to_collected(
    monkeypatch, tmp_path
) -> None:
    from src.api import services as services_module

    eng_path = tmp_path / "eng_status.json"
    eng_path.write_text(
        json.dumps(
            {
                "test_passed": 100,
                "test_collected": 120,
                "generated_at": "2026-08-16T12:00:00+08:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(services_module, "ENG_STATUS_JSON", eng_path)
    payload = services_module.engineering_status()
    assert payload["test_count"] == 120
    assert payload["test_passed"] == 100


def test_optional_api_key_middleware(monkeypatch) -> None:
    from fastapi import FastAPI
    from src.api.middleware import ApiKeyMiddleware

    from src.api import middleware as middleware_module

    isolated = FastAPI()

    @isolated.get("/api/health")
    def health() -> dict[str, str]:
        return {"ok": "1"}

    @isolated.get("/api/items")
    def items() -> dict[str, list[str]]:
        return {"items": []}

    isolated.add_middleware(ApiKeyMiddleware)
    isolated_client = TestClient(isolated)
    monkeypatch.setattr(middleware_module, "BACKEND_API_KEY", "secret")
    assert isolated_client.get("/api/health").status_code == 200
    assert isolated_client.get("/api/items").status_code == 401
    assert (
        isolated_client.get(
            "/api/items", headers={"Authorization": "Bearer secret"}
        ).status_code
        == 200
    )
    monkeypatch.setattr(middleware_module, "BACKEND_API_KEY", "")
    assert isolated_client.get("/api/items").status_code == 200


def test_engineering_status_capabilities_use_policy_snapshot(monkeypatch, tmp_path) -> None:
    from src.api import services as services_module

    data_status_path = tmp_path / "data_status.json"
    policy_path = tmp_path / "policy" / "latest.json"
    policy_path.parent.mkdir(parents=True)
    data_status_path.write_text(
        json.dumps(
            {
                "data_as_of": "2026-08-14",
                "generated_at": "2026-08-14T10:00:00+08:00",
                "policy": {
                    "enabled": True,
                    "status": "ready",
                    "updated_at": "2026-08-14T10:00:00+08:00",
                    "date": "2026-08-14",
                    "provider": "crawler",
                    "fallback_used": False,
                    "events": 4,
                },
            }
        ),
        encoding="utf-8",
    )
    policy_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-08-14T10:00:00+08:00",
                "date": "2026-08-14",
                "provider": "crawler",
                "fallback_used": False,
                "events": [
                    {
                        "code": "e1",
                        "title": "关税上调",
                        "policy_type": "tariff",
                        "impact_level": "high",
                        "region": "foreign",
                    },
                    {
                        "code": "e2",
                        "title": "合规新规",
                        "policy_type": "compliance",
                        "impact_level": "medium",
                        "region": "domestic",
                    },
                    {
                        "code": "e3",
                        "title": "通关便利化",
                        "policy_type": "customs",
                        "impact_level": "low",
                        "region": "domestic",
                    },
                    {
                        "code": "e4",
                        "title": "宏观政策",
                        "policy_type": "macro",
                        "impact_level": "high",
                        "region": "global",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(services_module, "DATA_STATUS_JSON", data_status_path)
    monkeypatch.setattr(services_module, "POLICY_LATEST_JSON", policy_path)

    caps = services_module.engineering_status()["capabilities"]
    assert caps["policy_cost"]["status"] == "ready"
    assert caps["policy_cost"]["date"] == "2026-08-14"
    assert caps["policy_cost"]["provider"] == "crawler"
    assert caps["policy_cost"]["events"] == 4
    # M3：无关宏观/合规新闻按业务语义降级，不再以原文关键词标 high
    assert caps["policy_cost"]["high_risk"] == 0
    assert caps["compliance"]["events"] == 3
    assert caps["compliance"]["high_risk"] == 0


def test_engineering_status_capabilities_stale_without_snapshot(monkeypatch, tmp_path) -> None:
    from src.api import services as services_module

    data_status_path = tmp_path / "data_status_missing_policy.json"
    data_status_path.write_text(
        json.dumps({"data_as_of": "2026-08-14", "policy": None}),
        encoding="utf-8",
    )
    monkeypatch.setattr(services_module, "DATA_STATUS_JSON", data_status_path)
    monkeypatch.setattr(
        services_module,
        "POLICY_LATEST_JSON",
        tmp_path / "policy" / "missing.json",
    )

    caps = services_module.engineering_status()["capabilities"]
    assert caps["policy_cost"]["status"] == "stale"
    assert caps["compliance"]["status"] == "stale"


def test_system_eval_endpoint() -> None:
    resp = client.get("/api/system/eval")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["source"] in {"missing", "file"}
    assert "system_eval" in payload
    assert "model_summary" in payload
    assert payload["model_summary"]["combos"] >= len(CATEGORIES) * len(MARKETS)


def test_scoring_weights_flow() -> None:
    resp = client.get("/api/scoring/weights")
    assert resp.status_code == 200
    assert resp.json()["forecast_growth"] == 0.35

    resp = client.post("/api/scoring/weights", json={"forecast_growth": 0.4})
    assert resp.status_code == 200
    assert resp.json()["weights"]["forecast_growth"] == 0.4

    resp = client.get("/api/scoring/weights")
    assert resp.json()["forecast_growth"] == 0.4


def test_feedback_flow() -> None:
    resp = client.post("/api/feedback", json={"recommendation_id": 1, "accepted": True})
    assert resp.status_code == 201
    assert resp.json()["feedback"]["accepted"] is True

    resp = client.get("/api/feedback")
    assert resp.status_code == 200
    assert any(item["recommendation_id"] == 1 for item in resp.json()["items"])


def test_four_brain_rule_engine() -> None:
    resp = client.get(
        "/api/four-brain",
        params={"keyword": "mini latiao", "market": "us"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "brains" in payload
    assert payload["ai"]["used"] is False


def test_four_brain_ai_fallback_returns_conclusion() -> None:
    """看板“自动生成结论”调用路径：无 AI Key 时后端回退规则引擎并返回报告。"""
    resp = client.post(
        "/api/four-brain",
        json={
            "keyword": "pet feeder",
            "market": "us",
            "research": True,
            "ai": True,
            "search_provider": "mock",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("report")
    assert payload.get("ai", {}).get("used") is False
    assert payload.get("research", {}).get("summary")


def test_four_brain_custom_panel_with_user_data() -> None:
    """看板“个性化定制”板块请求：自定义品类/市场 + 用户数据 + 个性化要求。"""
    resp = client.post(
        "/api/four-brain",
        json={
            "keyword": "自定义品类 mini latiao",
            "market": "eu",
            "extra_prompt": "预算有限，突出静音",
            "offline_only": True,
            "use_user_data": True,
            "user_data": {
                "latest_history": [
                    {
                        "date": "2026-08-07",
                        "category": "cn_frozen_dumplings",
                        "market": "eu",
                        "sales_volume": 120.0,
                        "search_index": 80.0,
                        "competition_index": 55.0,
                        "price_median": 39.0,
                    }
                ],
                "recommendations": [],
            },
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("report")
    assert payload.get("payload", {}).get("extra_prompt") == "预算有限，突出静音"
    assert payload.get("payload", {}).get("market") == "eu"


def test_four_brain_custom_keyword_keeps_user_label() -> None:
    """未匹配内置品类的关键词应保留用户填写的品类名，而不是回退成某个内置食品 SKU。"""
    resp = client.post(
        "/api/four-brain",
        json={"keyword": "火星矿物提取器 mars mineral extractor", "market": "us", "search_provider": "mock"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("category") == "custom"
    assert payload.get("category_name") == "火星矿物提取器 mars mineral extractor"


def test_four_brain_food_keyword_maps_to_catalog_category() -> None:
    """食品关键词应命中目录内的食品 SKU，而不是回退成 custom。"""
    resp = client.post(
        "/api/four-brain",
        json={
            "keyword": "老干妈辣椒酱 laoganma chili sauce",
            "market": "us",
            "search_provider": "mock",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("category") == "cn_laoganma"
    assert payload.get("category_name") == "老干妈辣椒酱"


def test_four_brain_research_returns_search_history() -> None:
    """看板绘图数据源：联网研究应返回该定制产品的历史序列。"""
    resp = client.post(
        "/api/four-brain",
        json={
            "keyword": "工业机械臂 industrial robot arm",
            "market": "us",
            "research": True,
            "search_provider": "mock",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    history = payload.get("search_history") or []
    assert history
    assert history[0]["category"] == "custom"
    assert history[0]["market"] == "us"
    assert all("date" in row and "sales_volume" in row for row in history)


def test_demo_pages_served() -> None:
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/app"
    assert client.get("/four-brain").status_code == 404
    assert client.get("/trade-demo").status_code == 404
    assert client.get("/app").status_code == 200


def test_export_report_markdown_endpoint() -> None:
    resp = client.post(
        "/api/export/report",
        json={
            "filters": {"category": "cn_changsha_mifen", "market": "us"},
            "recommendation": {"rank": 1, "score": 88.5, "reasons": ["需求稳定"]},
            "trade_decision": {"risk_level": "low", "margin_pct": 20.0},
            "evidence": [{"title": "来源", "link": "https://example.com"}],
            "conclusion": "建议小批量测试。",
            "format": "md",
        },
    )
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert "跨境电商智能选品决策报告" in resp.text


def test_export_report_pdf_endpoint() -> None:
    resp = client.post(
        "/api/export/report",
        json={
            "filters": {"category": "cn_latiao", "market": "eu"},
            "recommendation": {"score": 80.0},
            "trade_decision": {"margin_pct": 15.0},
            "conclusion": "可以进入。",
            "format": "pdf",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_export_report_empty_payload_rejected() -> None:
    resp = client.post("/api/export/report", json={})
    assert resp.status_code == 400


def test_export_report_invalid_format_rejected() -> None:
    resp = client.post(
        "/api/export/report",
        json={"filters": {"category": "cn_latiao"}, "format": "docx"},
    )
    assert resp.status_code == 400


def test_four_brain_passes_ai_settings(monkeypatch) -> None:
    captured: dict = {}

    def fake_analyze(payload, use_ai=False):
        captured["payload"] = payload
        captured["use_ai"] = use_ai
        return {"ok": True, "ai": {"used": use_ai}}

    monkeypatch.setattr("src.api.app.brain_bridge.analyze", fake_analyze)
    resp = client.post(
        "/api/four-brain",
        json={
            "keyword": "pet feeder",
            "market": "us",
            "api_key": "sk-test",
            "base_url": "https://example.com/v1",
            "model": "gpt-test",
            "timeout": 20,
        },
    )
    assert resp.status_code == 200
    assert captured["payload"]["api_key"] == "sk-test"
    assert captured["payload"]["base_url"] == "https://example.com/v1"
    assert captured["payload"]["model"] == "gpt-test"
    assert captured["payload"]["timeout"] == 20


def test_ai_test_passes_ai_settings(monkeypatch) -> None:
    captured: dict = {}

    def fake_ai_test(payload):
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr("src.api.app.brain_bridge.ai_test", fake_ai_test)
    resp = client.post(
        "/api/ai/test",
        json={
            "api_key": "sk-test",
            "base_url": "https://example.com/v1",
            "model": "gpt-test",
        },
    )
    assert resp.status_code == 200
    assert captured["payload"]["api_key"] == "sk-test"
    assert captured["payload"]["base_url"] == "https://example.com/v1"
    assert captured["payload"]["model"] == "gpt-test"


def test_trade_analyze_falls_back_to_global_ai_config(monkeypatch) -> None:
    from src.api import ai_config, brain_bridge
    from src.api import services as services_module

    ai_config.clear_config()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    ai_config.set_config(
        {
            "api_key": "sk-memory",
            "base_url": "https://memory.example/v1",
            "model": "gpt-memory",
            "timeout": 20,
        }
    )
    captured: dict = {}

    class FakeProvider:
        configured = True
        model = "gpt-memory"
        base_url = "https://memory.example/v1"

        def chat_json(self, system: str, user: str) -> dict:
            return {"ok": True, "echo": "memory"}

    def fake_provider(payload):
        captured.update(payload)
        return FakeProvider()

    monkeypatch.setattr(services_module, "_trade_research", lambda payload: None)
    monkeypatch.setattr(brain_bridge, "_provider", fake_provider)
    try:
        resp = client.post("/api/analyze", json={"ai": {}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ai_used"] is True
        assert body["data"]["echo"] == "memory"
        assert captured["api_key"] == "sk-memory"
        assert captured["base_url"] == "https://memory.example/v1"
        assert captured["model"] == "gpt-memory"
        assert captured["timeout"] == 20
    finally:
        ai_config.clear_config()


def test_trade_analyze_without_ai_config_returns_400(monkeypatch) -> None:
    from src.api import ai_config

    ai_config.clear_config()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    resp = client.post("/api/analyze", json={"ai": {}})
    assert resp.status_code == 400
    assert "AI 未配置" in resp.json()["detail"]


def test_trade_analyze_requires_brain_bridge(monkeypatch) -> None:
    from src.api import ai_config, brain_bridge

    ai_config.clear_config()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    ai_config.set_config(
        {
            "api_key": "sk-memory",
            "base_url": "https://memory.example/v1",
            "model": "gpt-memory",
        }
    )
    monkeypatch.setattr(brain_bridge, "available", lambda: False)
    resp = client.post("/api/analyze", json={"ai": {}})
    assert resp.status_code == 400
    assert "四脑引擎不可用" in resp.json()["detail"]


def test_crawler_signals_get_empty(monkeypatch) -> None:
    from src.api import services as services_module
    from src.data import crawler_signals

    monkeypatch.setattr(
        services_module, "load_latest_snapshot", crawler_signals.empty_snapshot
    )
    resp = client.get("/api/crawler/signals")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"]["status"] == "not_generated"
    assert payload["count"] == 0


def test_crawler_signals_post_offline(monkeypatch) -> None:
    from src.api import services as services_module
    from src.data import crawler_signals

    def fake_collect(keyword, market="us", category="", **kwargs):
        payload = {
            "meta": {
                "keyword": keyword,
                "market": market,
                "category": category,
                "generated_at": "2026-08-13T10:00:00+08:00",
                "offline": True,
                "max_results": 5,
            },
            "queries": [
                {
                    "query": keyword,
                    "provider": "mock",
                    "results": [
                        {"title": "mock", "snippet": "s", "link": "https://example.com"}
                    ],
                }
            ],
            "pageviews": None,
            "fallback_used": True,
            "errors": [],
            "robots": [],
        }
        return crawler_signals.normalize_signal(payload, keyword, market, category)

    monkeypatch.setattr(services_module, "collect_signal", fake_collect)
    resp = client.post(
        "/api/crawler/signals",
        json={"keyword": "pet feeder", "market": "us", "offline": True},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["fallback_used"] is True
    assert payload["keyword"] == "pet feeder"


def test_crawler_signals_post_requires_keyword() -> None:
    resp = client.post("/api/crawler/signals", json={})
    assert resp.status_code == 400
