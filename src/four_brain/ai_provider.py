"""
OpenAI 兼容 Chat Completions 客户端。

使用 Python 标准库实现，不依赖 openai SDK。可以通过环境变量切换任意
OpenAI 兼容服务，例如 OpenAI、DeepSeek、本地 Ollama 或企业网关。
"""

from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator


DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 120
CONFIG_MISSING_MESSAGE = "AI 未配置：请先在顶部“AI 接入”中填写 API Key 与模型并保存配置"

_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
_RETRY_BACKOFF_SECONDS = 2.0

_BASE_URL_PATHS: dict[str, str] = {
    "api.deepseek.com": "/v1",
    "api.openai.com": "/v1",
    "api.anthropic.com": "/v1",
    "api.moonshot.cn": "/v1",
    "api.siliconflow.cn": "/v1",
    "api.x.ai": "/v1",
    "api.mistral.ai": "/v1",
    "api.together.xyz": "/v1",
    "api.groq.com": "/openai/v1",
    "generativelanguage.googleapis.com": "/v1beta/openai",
    "open.bigmodel.cn": "/api/paas/v4",
    "dashscope.aliyuncs.com": "/compatible-mode/v1",
    "ark.cn-beijing.volces.com": "/api/v3",
    "qianfan.baidubce.com": "/v2",
    "api.hunyuan.cloud.tencent.com": "/v1",
    "api.minimaxi.com": "/v1",
    "api.minimax.chat": "/v1",
    "api.lingyiwanwu.com": "/v1",
    "api.stepfun.com": "/v1",
    "api.baichuan-ai.com": "/v1",
    "spark-api-open.xf-yun.com": "/v1",
    "openrouter.ai": "/api/v1",
}


class AIProviderError(RuntimeError):
    """AI 服务调用或结果解析失败。"""


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def normalize_base_url(url: str) -> str:
    """Trim a provider base URL and add the canonical path for known hosts."""
    value = (url or "").strip().rstrip("/")
    if not value:
        return value
    try:
        parsed = urllib.parse.urlparse(value)
    except ValueError:
        return value
    host = (parsed.hostname or "").lower()
    suffix = _BASE_URL_PATHS.get(host, "")
    if suffix and parsed.path in ("", "/"):
        return f"{parsed.scheme}://{parsed.netloc}{suffix}"
    return value


def _fix_escapes(value: str) -> str:
    """Repair common backslash mistakes produced by chat models."""
    out: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt in '"\\/bfnrtu':
                out.append(ch + nxt)
                i += 2
                continue
            if nxt == "'":
                out.append(nxt)
                i += 2
                continue
            out.append("\\\\" + nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _candidate_texts(text: str) -> list[str]:
    candidates = [text]
    stripped = re.sub(
        r"^\s*```(?:json)?\s*|\s*```\s*$",
        "",
        text.strip(),
        flags=re.IGNORECASE | re.S,
    )
    if stripped and stripped != text:
        candidates.append(stripped)
        candidates.append(_fix_escapes(stripped))
    candidates.append(_fix_escapes(text))
    return candidates


def extract_json(text: str) -> dict[str, Any]:
    """从模型输出中提取第一个 JSON 对象，并容忍常见格式噪声。"""
    if not text:
        raise AIProviderError("AI response is empty")
    last_error: Exception | None = None
    for candidate in _candidate_texts(text):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            continue
        try:
            parsed = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed
        last_error = ValueError("AI response JSON must be an object")
    if last_error is not None:
        raise AIProviderError(f"AI response JSON parse failed: {last_error}") from last_error
    raise AIProviderError("AI response does not contain a JSON object")


def _delta_text(payload: dict[str, Any]) -> str:
    """Extract the incremental text from one streaming chat chunk."""
    try:
        return str(payload["choices"][0]["delta"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return ""


def _sse_delta_content(block: str) -> str:
    """Parse one SSE block (or ndjson line) and return its text delta."""
    lines = block.strip().splitlines()
    data_payloads: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("data:"):
            data_payloads.append(stripped[5:].strip())
    if data_payloads:
        text = ""
        for payload in data_payloads:
            if payload == "[DONE]":
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            text += _delta_text(parsed)
        return text
    try:
        parsed = json.loads(block.strip())
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    # 某些网关忽略 stream=true 时仍返回完整 message，兼容兜底。
    try:
        return str(parsed["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return _delta_text(parsed)


class OpenAICompatibleProvider:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else _env("OPENAI_API_KEY")
        self.base_url = normalize_base_url(
            base_url or _env("OPENAI_BASE_URL", DEFAULT_BASE_URL)
        )
        self.model = model or _env("OPENAI_MODEL", DEFAULT_MODEL)
        self.timeout = timeout or float(_env("AI_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT)))
        self.proxy = _env("AI_PROXY_URL")
        self.no_proxy = _env("AI_NO_PROXY_FLAG", "0") == "1"
        try:
            self.retries = max(0, int(_env("AI_RETRIES", "1") or "0"))
        except ValueError:
            self.retries = 1
        self.retry_backoff_seconds = _RETRY_BACKOFF_SECONDS
        self._opener = self._build_opener()

    def _build_opener(self) -> urllib.request.OpenerDirector:
        host = urllib.parse.urlparse(self.base_url).hostname or ""
        local_host = host in {"localhost", "127.0.0.1", "::1"}
        if self.proxy and not self.no_proxy and not local_host:
            return urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": self.proxy, "https": self.proxy})
            )
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "base_url": self.base_url,
            "model": self.model,
            "timeout_seconds": self.timeout,
            "proxy": self.proxy or None,
            "no_proxy": self.no_proxy,
        }

    def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        return extract_json(self._chat(system, user, temperature))

    def chat_text(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
    ) -> str:
        """返回模型原始文本输出，适合长 Markdown 报告等非 JSON 场景。"""
        return self._chat(system, user, temperature)

    def chat_text_stream(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
    ) -> Iterator[str]:
        """流式返回模型文本增量，适合长报告边生成边展示。"""
        if not self.configured:
            raise AIProviderError(CONFIG_MISSING_MESSAGE)
        body = {
            "model": self.model,
            "temperature": temperature,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        for attempt in range(self.retries + 1):
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    buffer = ""
                    while True:
                        chunk = response.read(4096)
                        if not chunk:
                            break
                        buffer += chunk.decode("utf-8", errors="replace").replace(
                            "\r\n", "\n"
                        )
                        while "\n\n" in buffer:
                            block, buffer = buffer.split("\n\n", 1)
                            content = _sse_delta_content(block)
                            if content:
                                yield content
                    if buffer.strip():
                        content = _sse_delta_content(buffer)
                        if content:
                            yield content
                break
            except urllib.error.HTTPError as exc:
                detail = ""
                if exc.fp is not None:
                    detail = exc.fp.read().decode("utf-8", errors="replace")[:300]
                retried = f"；本次已重试 {attempt} 次" if attempt else ""
                if exc.code in _RETRYABLE_HTTP_STATUS and attempt < self.retries:
                    time.sleep(self.retry_backoff_seconds)
                    continue
                raise AIProviderError(
                    f"AI API HTTP {exc.code}: {detail}{retried}"
                ) from exc
            except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
                if attempt < self.retries:
                    time.sleep(self.retry_backoff_seconds)
                    continue
                raise AIProviderError(
                    f"AI API request failed: {exc} (base_url={self.base_url}, model={self.model}; "
                    "如果是 WinError 10013，通常是防火墙、杀毒软件或沙箱阻止了出站连接，"
                    "可尝试设置 AI_NO_PROXY_FLAG=1、关闭代理/VPN，或在系统终端直接运行后端；"
                    "如果是 WinError 10060 或连接超时，通常是当前网络无法直连该 API 地址，"
                    "请把 Base URL 换成 DeepSeek（https://api.deepseek.com/v1，模型 deepseek-chat）"
                    "等 OpenAI 兼容服务，或在 .env 中设置 AI_PROXY_URL=http://127.0.0.1:端口"
                    f"{'；本次已重试 ' + str(attempt) + ' 次' if attempt else ''})"
                ) from exc
            except Exception as exc:
                raise AIProviderError(
                    f"AI API request failed: {exc} (base_url={self.base_url}, model={self.model}; "
                    "如果是 WinError 10013，通常是防火墙、杀毒软件或沙箱阻止了出站连接，"
                    "可尝试设置 AI_NO_PROXY_FLAG=1、关闭代理/VPN，或在系统终端直接运行后端；"
                    "如果是 WinError 10060 或连接超时，通常是当前网络无法直连该 API 地址，"
                    "请把 Base URL 换成 DeepSeek（https://api.deepseek.com/v1，模型 deepseek-chat）"
                    "等 OpenAI 兼容服务，或在 .env 中设置 AI_PROXY_URL=http://127.0.0.1:端口"
                    f"{'；本次已重试 ' + str(attempt) + ' 次' if attempt else ''})"
                ) from exc

    def chat_json_messages(
        self,
        system: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Chat with a full message history and return a parsed JSON object."""
        body = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                *messages,
            ],
        }
        return extract_json(self._request(body))

    def _chat(
        self,
        system: str,
        user: str,
        temperature: float,
    ) -> str:
        body = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        return self._request(body)

    def _request(self, body: dict[str, Any]) -> str:
        if not self.configured:
            raise AIProviderError(CONFIG_MISSING_MESSAGE)

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        for attempt in range(self.retries + 1):
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                break
            except urllib.error.HTTPError as exc:
                detail = ""
                if exc.fp is not None:
                    detail = exc.fp.read().decode("utf-8", errors="replace")[:300]
                retried = f"；本次已重试 {attempt} 次" if attempt else ""
                if exc.code in _RETRYABLE_HTTP_STATUS and attempt < self.retries:
                    time.sleep(self.retry_backoff_seconds)
                    continue
                raise AIProviderError(
                    f"AI API HTTP {exc.code}: {detail}{retried}"
                ) from exc
            except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
                if attempt < self.retries:
                    time.sleep(self.retry_backoff_seconds)
                    continue
                raise AIProviderError(
                    f"AI API request failed: {exc} (base_url={self.base_url}, model={self.model}; "
                    "如果是 WinError 10013，通常是防火墙、杀毒软件或沙箱阻止了出站连接，"
                    "可尝试设置 AI_NO_PROXY_FLAG=1、关闭代理/VPN，或在系统终端直接运行后端；"
                    "如果是 WinError 10060 或连接超时，通常是当前网络无法直连该 API 地址，"
                    "请把 Base URL 换成 DeepSeek（https://api.deepseek.com/v1，模型 deepseek-chat）"
                    "等 OpenAI 兼容服务，或在 .env 中设置 AI_PROXY_URL=http://127.0.0.1:端口"
                    f"{'；本次已重试 ' + str(attempt) + ' 次' if attempt else ''})"
                ) from exc
            except Exception as exc:
                raise AIProviderError(
                    f"AI API request failed: {exc} (base_url={self.base_url}, model={self.model}; "
                    "如果是 WinError 10013，通常是防火墙、杀毒软件或沙箱阻止了出站连接，"
                    "可尝试设置 AI_NO_PROXY_FLAG=1、关闭代理/VPN，或在系统终端直接运行后端；"
                    "如果是 WinError 10060 或连接超时，通常是当前网络无法直连该 API 地址，"
                    "请把 Base URL 换成 DeepSeek（https://api.deepseek.com/v1，模型 deepseek-chat）"
                    "等 OpenAI 兼容服务，或在 .env 中设置 AI_PROXY_URL=http://127.0.0.1:端口"
                    f"{'；本次已重试 ' + str(attempt) + ' 次' if attempt else ''})"
                ) from exc

        try:
            payload = json.loads(raw)
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AIProviderError(f"Unexpected AI API response: {raw[:300]}") from exc
        return content


__all__ = [
    "AIProviderError",
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "CONFIG_MISSING_MESSAGE",
    "OpenAICompatibleProvider",
    "extract_json",
    "normalize_base_url",
]
