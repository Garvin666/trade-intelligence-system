"""Small ASGI middlewares for local and classroom deployments."""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

RATE_LIMIT_REQUESTS = int(os.environ.get("BACKEND_RATE_LIMIT_REQUESTS", "180"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("BACKEND_RATE_LIMIT_WINDOW_SECONDS", "60"))
MAX_BODY_BYTES = int(os.environ.get("BACKEND_MAX_BODY_BYTES", "65536"))
BACKEND_API_KEY = os.environ.get("BACKEND_API_KEY", "").strip()
# 上传类端点（用户 CSV/JSON）单独放宽：文件内容远大于普通 JSON 请求。
UPLOAD_MAX_BYTES = int(os.environ.get("BACKEND_UPLOAD_MAX_BYTES", str(20 * 1024 * 1024)))
# 上传端点路径前缀白名单。
UPLOAD_PATH_PREFIXES = tuple(
    prefix.strip()
    for prefix in os.environ.get("BACKEND_UPLOAD_PATHS", "/api/eda").split(",")
    if prefix.strip()
)
# 限流字典裁剪间隔（秒）。
PRUNE_INTERVAL_SECONDS = 300


def _is_upload_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in UPLOAD_PATH_PREFIXES)


def _request_body_limit(path: str) -> int:
    """返回该路径的 body 上限：上传端点放宽，其余保持默认。"""
    if _is_upload_path(path):
        return UPLOAD_MAX_BYTES
    return MAX_BODY_BYTES


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Optional bearer-token gate for the local/classroom deployment.

    Disabled when ``BACKEND_API_KEY`` is empty (default demo mode). When set,
    every ``/api/*`` route except health and self-check requires
    ``Authorization: Bearer <key>``.
    """

    _PUBLIC_PREFIXES = ("/api/health", "/api/check")

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        if not BACKEND_API_KEY:
            return await call_next(request)
        path = request.url.path
        if not path.startswith("/api/") or path.startswith(self._PUBLIC_PREFIXES):
            return await call_next(request)
        auth = str(request.headers.get("Authorization") or "")
        expected = f"Bearer {BACKEND_API_KEY}"
        if auth != expected:
            return JSONResponse(
                {
                    "error": "Unauthorized",
                    "message": "缺少或错误的 BACKEND_API_KEY",
                    "status": 401,
                },
                status_code=401,
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-client sliding-window rate limiter."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._last_prune = time.monotonic()

    def _prune_stale_clients(self) -> None:
        """定期裁剪超过两个窗口无活动的客户端键，防止字典无限增长。"""
        now = time.monotonic()
        if now - self._last_prune < PRUNE_INTERVAL_SECONDS:
            return
        self._last_prune = now
        cutoff = time.time() - RATE_LIMIT_WINDOW_SECONDS * 2
        stale = [
            client
            for client, hits in self._hits.items()
            if not hits or hits[-1] < cutoff
        ]
        for client in stale:
            del self._hits[client]

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        if RATE_LIMIT_REQUESTS <= 0:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        with self._lock:
            self._prune_stale_clients()
            hits = [ts for ts in self._hits.get(client, []) if ts >= cutoff]
            if len(hits) >= RATE_LIMIT_REQUESTS:
                self._hits[client] = hits
                return JSONResponse(
                    {
                        "error": "Too Many Requests",
                        "message": "Too many requests, please slow down",
                        "status": 429,
                    },
                    status_code=429,
                )
            hits.append(now)
            self._hits[client] = hits
        return await call_next(request)


class BodySizeMiddleware(BaseHTTPMiddleware):
    """Reject oversized JSON bodies before they reach route handlers.

    Upload endpoints get a raised limit. Chunked transfer has no
    Content-Length header, so its size cannot be pre-checked here;
    chunked requests are therefore rejected outright (standard browsers
    and httpx send Content-Length for uploads).
    """

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        path = request.url.path
        limit = _request_body_limit(path)
        length = request.headers.get("Content-Length")
        if length and length.isdigit() and int(length) > limit:
            return JSONResponse(
                {
                    "error": "Payload Too Large",
                    "message": f"Request body is too large. Max bytes: {limit}",
                    "status": 413,
                },
                status_code=413,
            )
        # chunked 传输无 Content-Length，无法预检体积，一律拒绝防止绕过限制。
        if request.headers.get("Transfer-Encoding", "").lower() == "chunked":
            return JSONResponse(
                {
                    "error": "Payload Too Large",
                    "message": "Chunked request bodies are not accepted; send Content-Length.",
                    "status": 413,
                },
                status_code=413,
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add conservative browser security headers to every response."""

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
