"""选品立项报告模板生成接口测试。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEST_DB = PROJECT_ROOT / "tmp" / "test_launch_report_state.db"
_TEST_DB.unlink(missing_ok=True)
os.environ["BACKEND_STATE_DB"] = str(_TEST_DB)

from src.api import ai_config  # noqa: E402
from src.api.app import app  # noqa: E402
from src.four_brain.ai_provider import AIProviderError, OpenAICompatibleProvider  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_ai_config(monkeypatch: pytest.MonkeyPatch) -> None:
    ai_config.clear_config()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    yield
    ai_config.clear_config()


def test_provider_chat_text_returns_raw_content() -> None:
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def read(self) -> bytes:
            return '{"choices":[{"message":{"content":"# 原始 Markdown\\n\\n正文"}}]}'.encode(
                "utf-8"
            )

    class FakeOpener:
        def open(self, request: object, timeout: object = None) -> FakeResponse:
            return FakeResponse()

    provider._opener = FakeOpener()  # type: ignore[attr-defined]
    text = provider.chat_text("system", "user")
    assert text == "# 原始 Markdown\n\n正文"


def test_provider_chat_json_keeps_parsing() -> None:
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def read(self) -> bytes:
            return '{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'.encode("utf-8")

    class FakeOpener:
        def open(self, request: object, timeout: object = None) -> FakeResponse:
            return FakeResponse()

    provider._opener = FakeOpener()  # type: ignore[attr-defined]
    assert provider.chat_json("system", "user") == {"ok": True}


def test_launch_report_requires_ai_config() -> None:
    resp = client.post(
        "/api/four-brain/launch-report",
        json={"prompt": "# Role\n\n请生成报告"},
    )
    assert resp.status_code == 400
    assert "AI 未配置" in resp.json()["detail"]


def test_launch_report_returns_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProvider:
        configured = True

        def chat_text(
            self,
            system: str,
            user: str,
            temperature: float = 0.3,
        ) -> str:
            assert temperature == 0.3
            return "# Codex 直出（逻辑版）\n\n## 执行摘要\n\n建议：条件式进入。"

        def status(self) -> dict[str, object]:
            return {"configured": True, "model": "gpt-test"}

    monkeypatch.setattr(
        "src.api.brain_bridge._provider",
        lambda payload: FakeProvider(),
    )
    resp = client.post(
        "/api/four-brain/launch-report",
        json={"prompt": "# Role\n\n请生成报告"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["report"].startswith("# Codex 直出")
    assert "执行摘要" in body["report"]
    assert body["mode"] == "launch-report-v1"
    assert body["generated_at"]
    assert body["ai"]["used"] is True
    assert body["ai"]["provider"]["model"] == "gpt-test"


def test_launch_report_returns_502_on_ai_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProvider:
        configured = True

        def chat_text(
            self,
            system: str,
            user: str,
            temperature: float = 0.3,
        ) -> str:
            raise AIProviderError("The read operation timed out")

    monkeypatch.setattr(
        "src.api.brain_bridge._provider",
        lambda payload: FakeProvider(),
    )
    resp = client.post(
        "/api/four-brain/launch-report",
        json={"prompt": "# Role\n\n请生成报告"},
    )
    assert resp.status_code == 502
    assert "AI 服务调用失败" in resp.json()["detail"]
    assert "timed out" in resp.json()["detail"]


def test_launch_report_rejects_empty_prompt() -> None:
    resp = client.post("/api/four-brain/launch-report", json={"prompt": "   "})
    assert resp.status_code == 400
    assert "prompt 不能为空" in resp.json()["detail"]


def test_launch_report_rejects_overlong_prompt() -> None:
    resp = client.post(
        "/api/four-brain/launch-report",
        json={"prompt": "x" * 20001},
    )
    assert resp.status_code == 400
    assert "prompt 过长" in resp.json()["detail"]


def test_launch_report_stream_returns_sse_deltas_and_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProvider:
        configured = True

        def chat_text_stream(
            self,
            system: str,
            user: str,
            temperature: float = 0.3,
        ):
            assert temperature == 0.3
            yield "# Codex 流式（逻辑版）\n\n"
            yield "## 执行摘要\n\n建议：条件式进入。"

        def status(self) -> dict[str, object]:
            return {"configured": True, "model": "gpt-test"}

    monkeypatch.setattr(
        "src.api.brain_bridge._provider",
        lambda payload: FakeProvider(),
    )
    with client.stream(
        "POST",
        "/api/four-brain/launch-report/stream",
        json={"prompt": "# Role\n\n请生成报告"},
    ) as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in body
    assert "event: delta" in body
    assert '"content": "# Codex 流式（逻辑版）\\n\\n"' in body
    assert '"content": "## 执行摘要\\n\\n建议：条件式进入。"' in body
    assert "event: done" in body
    assert '"mode": "launch-report-v1"' in body


def test_launch_report_stream_requires_ai_config() -> None:
    resp = client.post(
        "/api/four-brain/launch-report/stream",
        json={"prompt": "# Role\n\n请生成报告"},
    )
    assert resp.status_code == 400
    assert "AI 未配置" in resp.json()["detail"]


def test_launch_report_stream_rejects_empty_prompt() -> None:
    resp = client.post(
        "/api/four-brain/launch-report/stream",
        json={"prompt": "   "},
    )
    assert resp.status_code == 400
    assert "prompt 不能为空" in resp.json()["detail"]


def test_launch_report_stream_rejects_overlong_prompt() -> None:
    resp = client.post(
        "/api/four-brain/launch-report/stream",
        json={"prompt": "x" * 20001},
    )
    assert resp.status_code == 400
    assert "prompt 过长" in resp.json()["detail"]


def test_launch_report_stream_yields_error_event_on_ai_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProvider:
        configured = True

        def chat_text_stream(
            self,
            system: str,
            user: str,
            temperature: float = 0.3,
        ):
            raise AIProviderError("The read operation timed out")

    monkeypatch.setattr(
        "src.api.brain_bridge._provider",
        lambda payload: FakeProvider(),
    )
    with client.stream(
        "POST",
        "/api/four-brain/launch-report/stream",
        json={"prompt": "# Role\n\n请生成报告"},
    ) as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert "event: error" in body
    assert "The read operation timed out" in body


def test_launch_report_export_pdf_endpoint() -> None:
    resp = client.post(
        "/api/export/launch-report",
        json={"report": "# 选品立项报告\n\n## 执行摘要\n\n建议：条件式进入。"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_launch_report_export_markdown_endpoint() -> None:
    resp = client.post(
        "/api/export/launch-report",
        json={
            "report": "# 选品立项报告\n\n## 执行摘要\n\n建议：条件式进入。",
            "format": "md",
        },
    )
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert "选品立项报告" in resp.text


def test_launch_report_export_rejects_empty_payload() -> None:
    resp = client.post("/api/export/launch-report", json={"report": "   "})
    assert resp.status_code == 400
    assert "report 不能为空" in resp.json()["detail"]


def test_launch_report_export_rejects_invalid_format() -> None:
    resp = client.post(
        "/api/export/launch-report",
        json={"report": "# 选品立项报告", "format": "docx"},
    )
    assert resp.status_code == 400
    assert "format must be md or pdf" in resp.json()["detail"]
