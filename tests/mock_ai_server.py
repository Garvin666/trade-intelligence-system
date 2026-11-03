"""OpenAI-compatible mock AI server for local verification."""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


TRADE_ANALYSIS = {
    "title": "建议小批试单验证",
    "summary": "这是本地 mock AI 生成的贸易决策分析，用于验证 OpenAI 兼容接入链路。",
    "confidence": 82,
    "signals": ["mock AI 链路已连通", "请在实际使用前替换为真实 API Key"],
    "actions": ["先用小批量验证需求", "回填真实订单数据"],
}


def build_chat_response(content: str) -> dict[str, Any]:
    return {
        "id": "mock-chat",
        "object": "chat.completion",
        "model": "mock-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            body = {}
        if parsed.path.rstrip("/").endswith("/chat/completions"):
            user_text = " ".join(
                str(message.get("content", ""))
                for message in body.get("messages", [])
                if message.get("role") == "user"
            )
            if "echo" in user_text:
                content = json.dumps({"ok": True, "echo": "connected"}, ensure_ascii=False)
            else:
                content = json.dumps(TRADE_ANALYSIS, ensure_ascii=False)
            self._send_json(200, build_chat_response(content))
            return
        self._send_json(404, {"error": "not found"})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/").endswith("/health"):
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"error": "not found"})

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-Id"
        )

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: ARG002
        pass


def create_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18080
    server = create_server(port=port)
    print(f"mock AI server: http://127.0.0.1:{server.server_address[1]}/v1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
