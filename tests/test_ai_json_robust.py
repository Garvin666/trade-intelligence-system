"""AI JSON parsing robustness and /api/analyze graceful fallback tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.four_brain.ai_provider import AIProviderError, extract_json


def test_extract_json_accepts_fenced_json() -> None:
    result = extract_json('```json\n{"title":"ok","score":1}\n```')
    assert result == {"title": "ok", "score": 1}


def test_extract_json_repairs_invalid_escape() -> None:
    raw = '{"summary":"成本\\d上升","ok":true}'
    result = extract_json(raw)
    assert result["ok"] is True
    assert "成本" in result["summary"]


def test_extract_json_rejects_non_object() -> None:
    with pytest.raises(AIProviderError):
        extract_json("plain text")


def test_trade_ai_analyze_falls_back_on_provider_error() -> None:
    from src.api import brain_bridge, services

    class _FakeProvider:
        configured = True

        def chat_json(self, system: str, user: str) -> dict:
            raise AIProviderError("AI response JSON parse failed: boom")

    payload = {
        "ai": {
            "api_key": "sk-test",
            "base_url": "https://example.com/v1",
            "model": "gpt-test",
        },
        "scenario": {},
        "catalog": {},
    }
    with (
        patch.object(services, "_trade_research", return_value={"sources": []}),
        patch.object(brain_bridge, "_provider", return_value=_FakeProvider()),
    ):
        result = services.trade_ai_analyze(payload)
    assert result["mode"] == "fallback"
    assert result["ai_used"] is False
    assert "本地规则引擎" in result["data"]["title"]
    assert "boom" in result["reason"]
