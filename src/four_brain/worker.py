"""Four-brain analysis executed inside an isolated worker process.

Windows 上四脑分析（55MB 看板数据 + 图表热力图路径）曾触发原生访问冲突
（0xc0000005）直接拖垮整个后端进程（见建议报告 B4）。把整条分析链路放进
spawn 子进程后，即使 worker 崩溃也只会影响本次请求：主进程捕获到
``BrokenProcessPool``/超时后重建池并向 API 层返回结构化错误，配合
``scripts/run_api.py --watchdog`` 自动拉起，演示不再"自杀"。

业务参数错误（ValueError/FileNotFoundError）在 worker 内转成结构化 dict
回传，由 ``run_isolated`` 重新抛出为对应异常类型，API 层据此返回 400/404；
真正的崩溃/超时才抛 ``RuntimeError``（API 层返回 503 降级提示）。

并发说明：FastAPI 同步端点运行于线程池，多个请求可并发调用
``run_isolated``，因此对全局进程池的创建/重建/关闭均以模块级
``threading.Lock`` 串行化，避免"超时重置池时连坐其他请求"与
"并发首次创建产生双池泄漏"两类竞态。
"""

from __future__ import annotations

import logging
import os
import threading
import traceback
from multiprocessing import get_context
from typing import Any

logger = logging.getLogger("src.four_brain.worker")

#: 联网研究 + AI 四脑最坏情况下的单次分析上限（秒）。
MAX_WORKER_SECONDS = int(os.environ.get("FOUR_BRAIN_WORKER_TIMEOUT", "420"))
#: 长驻 worker 进程泄漏保护：每个 worker 处理 N 次任务后自动回收重建。
#: 提高复用次数后，57MB dashboard-data.json 在常驻 worker 内只加载一次。
MAX_TASKS_PER_WORKER = int(
    os.environ.get("FOUR_BRAIN_WORKER_MAX_TASKS", "20")
)

_CTX = get_context("spawn")
_POOL: Any = None
_POOL_LOCK = threading.Lock()


def _run_analysis(payload: dict[str, Any], use_ai: bool) -> dict[str, Any]:
    """子进程内执行的顶层函数（必须可 pickle）。任何异常转结构化 dict。"""
    try:
        from src.api.brain_bridge import _analyze_impl

        return _analyze_impl(payload, bool(use_ai))
    except Exception as exc:  # noqa: BLE001 - 全部转结构化错误回传
        return {
            "__worker_error__": True,
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=6),
        }


def _pool() -> Any:
    global _POOL
    with _POOL_LOCK:
        if _POOL is None:
            _POOL = _CTX.Pool(1, maxtasksperchild=MAX_TASKS_PER_WORKER)
        return _POOL


def _reset_pool(reason: str) -> None:
    """终止并重建进程池（worker 崩溃/超时后调用），并发安全。"""
    global _POOL
    with _POOL_LOCK:
        if _POOL is None:
            return
        try:
            _POOL.terminate()
            _POOL.join(timeout=5)
        except Exception:  # noqa: BLE001 - 池可能已损坏，回收失败仅告警
            logger.warning("four-brain worker pool cleanup failed: %s", reason, exc_info=True)
        _POOL = None
        logger.warning("four-brain worker pool reset: %s", reason)


def run_isolated(
    payload: dict[str, Any],
    use_ai: bool = False,
    timeout: int = MAX_WORKER_SECONDS,
) -> dict[str, Any]:
    """在独立子进程中执行四脑分析。

    - 业务错误（ValueError/FileNotFoundError）：原样重新抛出。
    - worker 崩溃 / 超时：抛出 ``RuntimeError``（含降级提示），池已重建。
    """
    pool = _pool()
    try:
        future = pool.apply_async(_run_analysis, (payload, bool(use_ai)))
        result = future.get(timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - BrokenProcessPool / TimeoutError
        _reset_pool(reason=f"{type(exc).__name__}: {exc}")
        raise RuntimeError(
            f"四脑分析子进程异常（{type(exc).__name__}）：{exc}"
            "；本次分析已降级，请稍后重试或关闭图表/联网后再试"
        ) from exc
    if isinstance(result, dict) and result.get("__worker_error__"):
        error_type = str(result.get("type") or "Error")
        message = str(result.get("message") or "未知错误")
        worker_traceback = str(result.get("traceback") or "")
        if error_type == "ValueError":
            raise ValueError(message) from None
        if error_type == "FileNotFoundError":
            raise FileNotFoundError(message) from None
        detail = f"{error_type}: {message}"
        if worker_traceback:
            detail += f"（worker 堆栈：{worker_traceback.splitlines()[-1].strip()}）"
        raise RuntimeError(detail) from None
    return result


def close() -> None:
    """优雅关闭进程池（应用退出时调用，避免残留 worker 进程）。"""
    global _POOL
    with _POOL_LOCK:
        if _POOL is None:
            return
        try:
            _POOL.close()
            _POOL.join(timeout=10)
        except Exception:  # noqa: BLE001 - 退出阶段清理失败不影响关闭
            logger.warning("four-brain worker pool close failed", exc_info=True)
        _POOL = None


__all__ = ["close", "run_isolated"]
