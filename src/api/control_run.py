"""Background runner for the page-driven top-AI control benchmark."""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from src.api import ai_config
from src.control import benchmark

_LOCK = threading.RLock()
_JOB: dict[str, Any] = {
    "status": "idle",
    "job_id": None,
    "mode": "lite",
    "progress": None,
    "error": None,
    "started_at": None,
    "finished_at": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def start(payload: dict[str, Any]) -> dict[str, Any]:
    """Start one benchmark run in a background thread (single job at a time)."""
    with _LOCK:
        if _JOB.get("status") == "running":
            raise ValueError("已有对照任务在运行，请等待完成后再试")
        api_key = str(
            payload.get("api_key") or ai_config.get_api_key() or ""
        ).strip()
        base_url = str(
            payload.get("base_url")
            or ai_config.get_base_url()
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.deepseek.com/v1"
        ).strip()
        model = str(
            payload.get("model")
            or ai_config.get_model()
            or os.environ.get("OPENAI_MODEL")
            or ""
        ).strip()
        if not api_key:
            raise ValueError("缺少 API Key，请先在页面“AI 接入”中填写")
        if not model:
            raise ValueError("缺少模型名称，请先在页面“AI 接入”中填写")
        mode = str(payload.get("mode") or "lite").strip().lower()
        if mode not in benchmark.CONTROL_MODES:
            raise ValueError(f"mode 只能是 lite 或 full：{mode}")
        try:
            runs = max(1, min(4, int(payload.get("runs") or 2)))
            temperature = float(payload.get("temperature") or 0.2)
            default_timeout = benchmark.CONTROL_TIMEOUT_SECONDS
            timeout = max(10, min(600, int(payload.get("timeout") or default_timeout)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"运行参数无效：{exc}") from exc

        job_id = uuid.uuid4().hex[:12]
        _JOB.update(
            status="running",
            job_id=job_id,
            mode=mode,
            progress=None,
            error=None,
            started_at=_now(),
            finished_at=None,
        )

        def _set_progress(progress: dict[str, Any]) -> None:
            with _LOCK:
                _JOB["progress"] = progress

        def _run() -> None:
            try:
                benchmark.run_global_benchmark(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    runs=runs,
                    temperature=temperature,
                    timeout=timeout,
                    mode=mode,
                    on_progress=_set_progress,
                )
                with _LOCK:
                    _JOB["status"] = "done"
                    _JOB["finished_at"] = _now()
            except Exception as exc:  # noqa: BLE001 - surfaced through status
                with _LOCK:
                    _JOB["status"] = "error"
                    _JOB["error"] = str(exc)
                    _JOB["finished_at"] = _now()

        threading.Thread(target=_run, daemon=True).start()
        return {"status": "running", "job_id": job_id}


def status() -> dict[str, Any]:
    with _LOCK:
        return dict(_JOB)
