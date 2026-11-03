"""Trade-decision demo AI and autofill tests against the merged FastAPI backend."""

from __future__ import annotations

import socket
from pathlib import Path
from threading import Thread

import pytest
from fastapi.testclient import TestClient

from src.api import ai_config
from src.api.app import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
client = TestClient(app)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture()
def mock_ai_server() -> str:
    from mock_ai_server import create_server

    server = create_server(port=free_port())
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def reset_ai_config() -> None:
    yield
    ai_config.clear_config()


def build_analyze_payload() -> dict:
    return {
        "scenario": {
            "input": {
                "category": "cn_changsha_mifen",
                "customCategory": "长沙米粉（鲜湿米粉）",
                "market": "us",
                "platform": "amazon",
                "route": "air",
                "quantity": 500,
                "price": 39.9,
                "cost": 13.6,
                "weight": 0.58,
                "freight": 3.4,
                "adRate": 0.09,
                "tariff": 0.08,
                "returnRate": 0.067,
                "fxRisk": 0.02,
                "paymentDays": 28,
                "inventoryDays": 18,
            },
            "profile": {
                "productKeyword": "长沙米粉 changsha rice noodles",
                "customerSegment": "mass",
                "businessStage": "explore",
                "goal": "growth",
                "riskTolerance": "medium",
                "budget": 30000,
                "stockPreference": "balanced",
                "complianceFocus": "standard",
                "customNeed": "主打小批量验证",
            },
            "result": {
                "decisionScore": 72,
                "netProfit": 3200,
                "margin": 0.16,
                "riskScore": 48,
                "cashDays": 88,
                "profileFit": 74,
            },
        },
        "catalog": {
            "category": {"key": "cn_changsha_mifen", "label": "长沙米粉"},
            "market": {"key": "us", "label": "美国"},
            "platform": {"key": "amazon", "label": "Amazon"},
            "route": {"key": "air", "label": "空运快反"},
        },
    }


def test_catalog_returns_full_merged_dictionary() -> None:
    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["categories"]) >= 40
    assert len(data["markets"]) == 15
    assert len(data["platforms"]) >= 6
    assert data["categories"][0]["basePrice"] > 0


def test_autofill_matches_three_profiles() -> None:
    profiles = [
        {
            "profile": {
                "productKeyword": "长沙米粉 changsha rice noodles",
                "budget": 30000,
                "businessStage": "test",
                "stockPreference": "light",
            },
            "current": {},
        },
        {
            "profile": {
                "productKeyword": "frozen chinese dumplings",
                "goal": "brand",
                "budget": 20000,
            },
            "current": {"customCategory": "速冻水饺"},
        },
        {
            "profile": {
                "productKeyword": "longjing green tea",
                "customNeed": "日本站",
                "budget": 50000,
                "businessStage": "scale",
            },
            "current": {},
        },
    ]
    for payload in profiles:
        resp = client.post("/api/autofill", json=payload)
        assert resp.status_code == 200
        data = resp.json()["data"]
        required = {
            "category",
            "customCategory",
            "market",
            "platform",
            "route",
            "quantity",
            "price",
            "cost",
            "weight",
            "freight",
            "adRate",
            "tariff",
            "returnRate",
            "fxRisk",
            "paymentDays",
            "inventoryDays",
        }
        assert required.issubset(data["input"].keys())
        assert data["signals"]


def test_ai_test_endpoint_ok(mock_ai_server: str) -> None:
    resp = client.post(
        "/api/ai/test",
        json={
            "base_url": mock_ai_server,
            "api_key": "test-key",
            "model": "mock-model",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["response"] == {"ok": True, "echo": "connected"}


def test_search_test_endpoint_uses_mock() -> None:
    resp = client.post(
        "/api/search/test",
        json={"query": "changsha rice noodles", "provider": "mock", "max_results": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["provider"] == "mock"
    assert data["results"]


def test_analyze_uses_openai_offline(mock_ai_server: str) -> None:
    payload = build_analyze_payload()
    payload["offline_only"] = True
    payload["ai"] = {
        "base_url": mock_ai_server,
        "api_key": "test-key",
        "model": "mock-model",
        "timeout": 20,
    }
    resp = client.post("/api/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_used"] is True
    assert data["mode"] == "openai"
    assert data["data"]["summary"]
    assert data["data"]["signals"]


def test_analyze_without_key_returns_400() -> None:
    payload = build_analyze_payload()
    payload["offline_only"] = True
    resp = client.post("/api/analyze", json=payload)
    assert resp.status_code == 400
