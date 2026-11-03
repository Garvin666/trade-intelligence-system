"""I1/I3 修复测试：异常日志、上传限额放宽与 EDA 行数保护。"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi.testclient import TestClient
from starlette.requests import Request

from src.api.app import app, unhandled_exception_handler
from src.api.middleware import (
    MAX_BODY_BYTES,
    RATE_LIMIT_WINDOW_SECONDS,
    UPLOAD_MAX_BYTES,
    BodySizeMiddleware,
    RateLimitMiddleware,
    _is_upload_path,
    _request_body_limit,
)

client = TestClient(app)


def _http_scope(path: str = "/api/eda") -> dict:
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
        "scheme": "http",
        "http_version": "1.1",
    }


class _FakeUrl:
    path = "/api/boom"


class _FakeRequest:
    method = "POST"
    url = _FakeUrl()


def test_unhandled_exception_handler_logs_traceback(caplog) -> None:
    """I1：全局异常处理器必须先记录 traceback 再返回 500。"""
    with caplog.at_level(logging.ERROR, logger="src.api.app"):
        response = asyncio.run(
            unhandled_exception_handler(_FakeRequest(), ValueError("boom"))
        )
    assert response.status_code == 500
    records = list(caplog.records)
    assert any(
        "Unhandled error on POST /api/boom" in record.message for record in records
    )
    assert any(
        record.exc_info and record.exc_info[0] is ValueError for record in records
    )


def test_oversized_regular_json_body_rejected() -> None:
    """普通 JSON 请求仍受 64KB 上限约束。"""
    body = "x" * (MAX_BODY_BYTES + 1024)
    response = client.post(
        "/api/nonexistent-route",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_upload_path_accepts_larger_body() -> None:
    """上传端点（/api/eda）放宽到 20MB：>64KB 的 CSV 不再 413。"""
    big_csv = "date,sales\n" + "".join(f"2026-01-01,{i}\n" for i in range(6000))
    assert len(big_csv.encode("utf-8")) > MAX_BODY_BYTES
    assert len(big_csv.encode("utf-8")) < UPLOAD_MAX_BYTES
    response = client.post(
        "/api/eda", files={"file": ("big.csv", big_csv, "text/csv")}
    )
    assert response.status_code != 413


def test_eda_row_limit_rejects_huge_file() -> None:
    """超过 20 万行的上传返回 400 而非拖垮服务。"""
    rows = "date,sales\n" + "".join(f"2026-01-01,{i}\n" for i in range(200_001))
    response = client.post(
        "/api/eda", files={"file": ("huge.csv", rows, "text/csv")}
    )
    assert response.status_code == 400
    assert "上限" in response.text


def test_body_limit_helper_paths() -> None:
    """上传路径放宽、普通路径保持默认。"""
    assert _request_body_limit("/api/eda") == UPLOAD_MAX_BYTES
    assert _request_body_limit("/api/summary") == MAX_BODY_BYTES
    assert _is_upload_path("/api/eda")
    assert not _is_upload_path("/api/summary")


def test_chunked_request_rejected_everywhere() -> None:
    """I3：chunked 传输无 Content-Length，无法预检体积，一律 413。"""

    async def call_next(_request):
        raise AssertionError("chunked 请求不应进入下一层中间件/路由")

    async def run() -> int:
        scope = _http_scope("/api/eda")
        scope["headers"] = [(b"transfer-encoding", b"chunked")]
        middleware = BodySizeMiddleware(app)
        response = await middleware.dispatch(Request(scope), call_next)
        return response.status_code

    assert asyncio.run(run()) == 413


def test_rate_limit_prunes_stale_clients() -> None:
    """S6：限流字典超过裁剪间隔后清理无活动客户端键。"""

    async def call_next(_request):
        return None

    async def run() -> dict:
        middleware = RateLimitMiddleware(app)
        middleware._hits = {
            "stale-client": [time.time() - RATE_LIMIT_WINDOW_SECONDS * 5],
            "active-client": [time.time()],
        }
        middleware._last_prune = time.monotonic() - 301  # 超过 5 分钟裁剪间隔
        scope = _http_scope("/api/health")
        scope["client"] = ("127.0.0.1", 54321)
        await middleware.dispatch(Request(scope), call_next)
        return dict(middleware._hits)

    hits = asyncio.run(run())
    assert "stale-client" not in hits
    assert "active-client" in hits
