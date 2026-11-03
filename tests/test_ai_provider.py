"""OpenAI-compatible provider hardening tests (URL normalization + retry)."""

from __future__ import annotations

import json
import socket
import urllib.error

import pytest

from src.four_brain.ai_provider import (
    AIProviderError,
    OpenAICompatibleProvider,
    normalize_base_url,
)


class _FakeResponse:
    def __init__(self, payload: str = "") -> None:
        self._payload = payload
        self._read = False

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._payload.encode("utf-8")


class _ChunkedResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    def __enter__(self) -> "_ChunkedResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def test_normalize_base_url_adds_v1_for_deepseek() -> None:
    assert normalize_base_url("https://api.deepseek.com") == "https://api.deepseek.com/v1"
    assert normalize_base_url("https://api.deepseek.com/") == "https://api.deepseek.com/v1"
    assert (
        normalize_base_url("  https://api.deepseek.com/v1/  ")
        == "https://api.deepseek.com/v1"
    )


def test_normalize_base_url_keeps_custom_urls() -> None:
    assert (
        normalize_base_url("https://open.bigmodel.cn/api/paas/v4")
        == "https://open.bigmodel.cn/api/paas/v4"
    )
    assert (
        normalize_base_url("http://127.0.0.1:11434/v1")
        == "http://127.0.0.1:11434/v1"
    )
    assert normalize_base_url("") == ""


def test_normalize_base_url_adds_known_provider_paths() -> None:
    assert normalize_base_url("https://api.openai.com") == "https://api.openai.com/v1"
    assert normalize_base_url("https://api.anthropic.com") == "https://api.anthropic.com/v1"
    assert normalize_base_url("https://api.groq.com") == "https://api.groq.com/openai/v1"
    assert (
        normalize_base_url("https://generativelanguage.googleapis.com")
        == "https://generativelanguage.googleapis.com/v1beta/openai"
    )
    assert normalize_base_url("https://openrouter.ai") == "https://openrouter.ai/api/v1"
    assert normalize_base_url("https://ark.cn-beijing.volces.com") == "https://ark.cn-beijing.volces.com/api/v3"


def test_provider_retries_timeout_once_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_RETRIES", "1")
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )
    provider.retry_backoff_seconds = 0

    class FlakyOpener:
        def __init__(self) -> None:
            self.calls = 0

        def open(self, request: object, timeout: object = None) -> _FakeResponse:
            self.calls += 1
            if self.calls == 1:
                raise urllib.error.URLError(socket.timeout("timed out"))
            return _FakeResponse('{"choices":[{"message":{"content":"ok"}}]}')

    provider._opener = FlakyOpener()  # type: ignore[attr-defined]
    assert provider.chat_text("system", "user") == "ok"
    assert provider._opener.calls == 2


def test_provider_retries_http_503_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_RETRIES", "1")
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )
    provider.retry_backoff_seconds = 0

    class FlakyOpener:
        def __init__(self) -> None:
            self.calls = 0

        def open(self, request: object, timeout: object = None) -> _FakeResponse:
            self.calls += 1
            if self.calls == 1:
                raise urllib.error.HTTPError(
                    "https://example.com/v1/chat/completions",
                    503,
                    "Service Unavailable",
                    {},
                    None,
                )
            return _FakeResponse('{"choices":[{"message":{"content":"ok"}}]}')

    provider._opener = FlakyOpener()  # type: ignore[attr-defined]
    assert provider.chat_text("system", "user") == "ok"
    assert provider._opener.calls == 2


def test_provider_does_not_retry_http_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_RETRIES", "3")
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )

    class Http401Opener:
        def __init__(self) -> None:
            self.calls = 0

        def open(self, request: object, timeout: object = None) -> _FakeResponse:
            self.calls += 1
            raise urllib.error.HTTPError(
                "https://example.com/v1/chat/completions",
                401,
                "Unauthorized",
                {},
                None,
            )

    provider._opener = Http401Opener()  # type: ignore[attr-defined]
    with pytest.raises(AIProviderError, match="HTTP 401"):
        provider.chat_text("system", "user")
    assert provider._opener.calls == 1


def test_provider_final_timeout_message_mentions_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_RETRIES", "1")
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )
    provider.retry_backoff_seconds = 0

    class TimeoutOpener:
        def open(self, request: object, timeout: object = None) -> _FakeResponse:
            raise urllib.error.URLError(socket.timeout("timed out"))

    provider._opener = TimeoutOpener()  # type: ignore[attr-defined]
    with pytest.raises(AIProviderError, match="本次已重试 1 次"):
        provider.chat_text("system", "user")


def test_provider_chat_json_messages_preserves_message_order() -> None:
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )
    captured: dict[str, object] = {}

    class CapturingOpener:
        def open(self, request: object, timeout: object = None) -> _FakeResponse:
            data = getattr(request, "data")
            captured["body"] = json.loads(data.decode("utf-8"))
            return _FakeResponse(
                '{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'
            )

    provider._opener = CapturingOpener()  # type: ignore[attr-defined]
    result = provider.chat_json_messages(
        "system prompt",
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    )
    assert result == {"ok": True}
    messages = captured["body"]["messages"]  # type: ignore[assignment]
    assert [item["role"] for item in messages] == ["system", "user", "assistant"]


def test_provider_chat_text_stream_yields_sse_deltas() -> None:
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )
    captured: dict[str, object] = {}

    class CapturingOpener:
        def open(self, request: object, timeout: object = None) -> _ChunkedResponse:
            data = getattr(request, "data")
            captured["body"] = json.loads(data.decode("utf-8"))
            return _ChunkedResponse(
                [
                    b'data: {"choices":[{"delta":{"content":"# "}}]}\n\n',
                    'data: {"choices":[{"delta":{"content":"报告"}}]}\n\n'.encode(
                        "utf-8"
                    ),
                    b"data: [DONE]\n\n",
                ]
            )

    provider._opener = CapturingOpener()  # type: ignore[attr-defined]
    assert list(provider.chat_text_stream("system", "user")) == ["# ", "报告"]
    assert captured["body"]["stream"] is True  # type: ignore[assignment]


def test_provider_chat_text_stream_handles_fragmented_blocks() -> None:
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )

    class FragmentedOpener:
        def open(self, request: object, timeout: object = None) -> _ChunkedResponse:
            return _ChunkedResponse(
                [
                    'data: {"choices":[{"delta":{"content":"你"}}]}'.encode("utf-8"),
                    (
                        '\n\ndata: {"choices":[{"delta":{"content":"好"}}]}\n\n'
                        "data: [DONE]\n\n"
                    ).encode("utf-8"),
                ]
            )

    provider._opener = FragmentedOpener()  # type: ignore[attr-defined]
    assert list(provider.chat_text_stream("system", "user")) == ["你", "好"]


def test_provider_chat_text_stream_falls_back_to_full_message() -> None:
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )

    class FullMessageOpener:
        def open(self, request: object, timeout: object = None) -> _FakeResponse:
            return _FakeResponse(
                '{"choices":[{"message":{"content":"完整报告"}}]}'
            )

    provider._opener = FullMessageOpener()  # type: ignore[attr-defined]
    assert list(provider.chat_text_stream("system", "user")) == ["完整报告"]


def test_provider_chat_text_stream_retries_timeout_once_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_RETRIES", "1")
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="gpt-test",
    )
    provider.retry_backoff_seconds = 0

    class FlakyOpener:
        def __init__(self) -> None:
            self.calls = 0

        def open(self, request: object, timeout: object = None) -> _ChunkedResponse:
            self.calls += 1
            if self.calls == 1:
                raise urllib.error.URLError(socket.timeout("timed out"))
            return _ChunkedResponse(
                [
                    b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n',
                    b"data: [DONE]\n\n",
                ]
            )

    provider._opener = FlakyOpener()  # type: ignore[attr-defined]
    assert list(provider.chat_text_stream("system", "user")) == ["ok"]
    assert provider._opener.calls == 2  # type: ignore[attr-defined]
