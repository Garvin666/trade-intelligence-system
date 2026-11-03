"""小助手后端测试。

使用 fake DeepSeek client 覆盖登录、JWT、工具调用、SSE 流式回答、
按用户名的多轮历史与 API key 隔离。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient


AGENT_DIR = Path(__file__).resolve().parents[1] / "小助手"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import main as smart_agent  # noqa: E402


client = TestClient(smart_agent.app)


class FakeMessage:
    def __init__(self, content: str = "", tool_calls: list[Any] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class FakeDelta:
    def __init__(self, content: str = "") -> None:
        self.content = content


class FakeChoice:
    def __init__(self, message: FakeMessage | None = None, delta: FakeDelta | None = None) -> None:
        self.message = message
        self.delta = delta


class FakeChunk:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(delta=FakeDelta(content))]


class FakeResponse:
    def __init__(self, message: FakeMessage) -> None:
        self.choices = [FakeChoice(message=message)]


class FakeToolCall:
    def __init__(self, tool_id: str, name: str, arguments: str) -> None:
        self.id = tool_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments)


class FakeCompletions:
    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, list):
            return iter(item)
        return item


class FakeClient:
    def __init__(self, script: list[Any]) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(script))


@pytest.fixture(autouse=True)
def _isolate_state(monkeypatch: pytest.MonkeyPatch) -> None:
    smart_agent.CONVERSATIONS.clear()
    smart_agent._ACTIVE_CHATS.clear()
    smart_agent.DEEPSEEK_API_KEY = "test-deepseek-key"
    smart_agent.JWT_SECRET = "test-jwt-secret-0123456789abcdef"
    smart_agent.ADMIN_USERNAME = "admin"
    smart_agent._DEMO_HASH = smart_agent.pwd_context.hash("123456")
    monkeypatch.setattr(
        smart_agent,
        "get_agent_client",
        lambda: FakeClient([]),
    )


def _token() -> str:
    return smart_agent.create_access_token("admin")


def _tool_call_script() -> list[Any]:
    return [
        FakeResponse(
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        "call_1",
                        "get_market_info",
                        '{"category": "cn_spicy_gluten", "market": "us"}',
                    )
                ]
            )
        ),
        FakeResponse(FakeMessage(content="")),
        [FakeChunk("电子产品"), FakeChunk("在美国"), FakeChunk("机会较高。")],
    ]


def test_login_success_returns_jwt() -> None:
    response = client.post(
        "/api/login",
        json={"username": "admin", "password": "123456"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_rejects_wrong_password() -> None:
    response = client.post(
        "/api/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401


def test_login_page_serves_starfield_background() -> None:
    response = client.get("/login.html")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-cache"
    html = response.text
    assert 'id="bg"' in html
    assert 'createElement("canvas")' in html
    assert "initStarfield" in html
    assert "requestAnimationFrame" in html
    assert "meteor" in html
    assert "drawDust" in html
    assert "pointermove" in html


def test_me_requires_valid_jwt() -> None:
    assert client.get("/api/me").status_code == 401
    bad = client.get(
        "/api/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert bad.status_code == 401
    ok = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert ok.status_code == 200
    assert ok.json()["username"] == "admin"


def test_get_market_info_filters_category_and_market() -> None:
    result = smart_agent.execute_get_market_info(
        {"category": "cn_spicy_gluten", "market": "us"}
    )
    assert result["ok"] is True
    payload = json.loads(result["result"])
    assert len(payload["categories"]) == 1
    assert payload["categories"][0]["id"] == "cn_spicy_gluten"
    assert len(payload["categories"][0]["markets"]) == 1
    assert payload["categories"][0]["markets"][0]["id"] == "us"


def test_get_market_info_returns_empty_for_unknown_category() -> None:
    result = smart_agent.execute_get_market_info({"category": "unknown"})
    assert result["ok"] is True
    payload = json.loads(result["result"])
    assert payload["categories"] == []


def test_chat_streams_tool_delta_and_done(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient(_tool_call_script())
    monkeypatch.setattr(smart_agent, "get_agent_client", lambda: fake)
    headers = {"Authorization": f"Bearer {_token()}"}
    with client.stream(
        "POST",
        "/api/chat",
        json={"message": "电子产品在美国的机会如何"},
        headers=headers,
    ) as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert "event: tool" in body
    assert "event: delta" in body
    assert "event: done" in body
    assert smart_agent.CONVERSATIONS["admin"][-1]["content"] == "电子产品在美国机会较高。"


def test_chat_keeps_multi_turn_history(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient(
        [
            *[item for item in _tool_call_script()],
            FakeResponse(FakeMessage(content="")),
            [FakeChunk("继续回答。")],
        ]
    )
    monkeypatch.setattr(smart_agent, "get_agent_client", lambda: fake)
    headers = {"Authorization": f"Bearer {_token()}"}
    first = client.post(
        "/api/chat",
        json={"message": "电子产品在美国的机会如何"},
        headers=headers,
    )
    assert first.status_code == 200
    first_body = "".join(first.iter_text())
    assert "event: done" in first_body

    second = client.post(
        "/api/chat",
        json={"message": "再总结一次"},
        headers=headers,
    )
    assert second.status_code == 200
    second_body = "".join(second.iter_text())
    assert "event: done" in second_body
    assert len(smart_agent.CONVERSATIONS["admin"]) == 4
    stream_call = fake.chat.completions.calls[-1]
    messages = stream_call["messages"]
    assert any(
        item.get("role") == "assistant"
        and item.get("content") == "电子产品在美国机会较高。"
        for item in messages
    )


def test_chat_stops_after_max_tool_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    script = [
        FakeResponse(
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        f"call_{i}",
                        "get_market_info",
                        '{"category": "cn_spicy_gluten"}',
                    )
                ]
            )
        )
        for i in range(smart_agent.MAX_TOOL_STEPS)
    ]
    fake = FakeClient(script)
    monkeypatch.setattr(smart_agent, "get_agent_client", lambda: fake)
    with client.stream(
        "POST",
        "/api/chat",
        json={"message": "一直查数据"},
        headers={"Authorization": f"Bearer {_token()}"},
    ) as response:
        body = "".join(response.iter_text())
    assert "event: done" in body
    assert "已达到最大工具调用次数" in body


def test_chat_returns_503_without_deepseek_key() -> None:
    smart_agent.DEEPSEEK_API_KEY = ""
    response = client.post(
        "/api/chat",
        json={"message": "hello"},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert response.status_code == 503
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


def test_chat_does_not_fall_back_to_root_openai_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "root-openai-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "root-deepseek-key")
    smart_agent.DEEPSEEK_API_KEY = ""
    response = client.post(
        "/api/chat",
        json={"message": "hello"},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert response.status_code == 503
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


def test_chat_rejects_empty_message() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "   "},
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert response.status_code == 400
