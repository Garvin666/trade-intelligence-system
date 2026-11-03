"""Managed background jobs for the unified single-process backend.

Long-running work that used to run as separate scripts (daily data update and
the market daily report) is registered here so it can be triggered and polled
from the FastAPI app inside the same process. Jobs run on daemon threads, so
they terminate with the process. Exclusive jobs reject a second start while
one is already running. Cancellation is cooperative: it only takes effect at
stage boundaries (between the heavy steps), which is the documented behaviour.
"""

from __future__ import annotations

import threading
import uuid
from datetime import date, datetime, timezone
from typing import Any, Callable

from src.api import services

Progress = Callable[[str, str], None]


class JobCancelled(Exception):
    """Raised inside a job thread when a cooperative stop is requested."""


_LOCK = threading.RLock()
_STATE: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _register(name: str, label: str) -> None:
    with _LOCK:
        _STATE[name] = {
            "name": name,
            "label": label,
            "status": "idle",
            "exclusive": True,
            "job_id": None,
            "progress": None,
            "error": None,
            "result": None,
            "started_at": None,
            "finished_at": None,
            "_cancel": False,
        }


_register("daily_update", "每日数据更新")
_register("market_daily", "市场日报生成")


def _daily_update_argv(payload: dict[str, Any]) -> list[str]:
    argv: list[str] = []
    if payload.get("offline"):
        argv.append("--offline")
    if payload.get("skip_pipeline"):
        argv.append("--skip-pipeline")
    if payload.get("skip_rebuild"):
        argv.append("--skip-rebuild")
    if payload.get("date"):
        argv += ["--date", str(payload["date"])]
    if payload.get("provider"):
        argv += ["--provider", str(payload["provider"])]
    if payload.get("workers"):
        argv += ["--workers", str(int(payload["workers"]))]
    if payload.get("crawler_combos"):
        argv += ["--crawler-combos", str(int(payload["crawler_combos"]))]
    return argv


def _run_daily_update(payload: dict[str, Any], progress: Progress) -> dict[str, Any]:
    from scripts import run_daily_update

    argv = _daily_update_argv(payload)
    code = run_daily_update.main(argv, progress=progress)
    if code != 0:
        raise RuntimeError(f"每日更新退出码 {code}，请检查数据产物是否齐全")
    return {"exit_code": code}


def _run_market_daily(payload: dict[str, Any], progress: Progress) -> dict[str, Any]:
    from src.data.market_daily import (
        build_market_daily_markdown,
        maybe_push_market_daily,
        write_market_daily,
    )

    report_date = str(payload.get("date") or date.today().isoformat())
    progress("1/2", f"生成市场日报 {report_date}")
    markdown = build_market_daily_markdown(report_date)
    path = write_market_daily(markdown, report_date)
    pushed = False
    if payload.get("push"):
        pushed = maybe_push_market_daily(markdown)
    progress("2/2", "市场日报写入完成")
    return {"date": report_date, "path": str(path), "pushed": pushed}


def _start(name: str, runner: Callable[[dict[str, Any], Progress], dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        job = _STATE.get(name)
        if job is None:
            raise KeyError(name)
        if job["status"] == "running":
            raise ValueError(f"任务 {job['label']} 已在运行，请等待完成后再试")
        job_id = uuid.uuid4().hex[:12]
        job.update(
            status="running",
            job_id=job_id,
            progress={"stage": "0", "message": "排队中"},
            error=None,
            result=None,
            started_at=_now(),
            finished_at=None,
            _cancel=False,
        )

    def _set_progress(stage: str, message: str) -> None:
        with _LOCK:
            current = _STATE[name]
            if current.get("_cancel"):
                raise JobCancelled("任务已取消")
            current["progress"] = {"stage": str(stage), "message": str(message)}

    def _run() -> None:
        try:
            result = runner(payload, _set_progress)
            with _LOCK:
                current = _STATE[name]
                current["status"] = "done"
                current["result"] = result
                current["finished_at"] = _now()
            services.invalidate_caches()
        except JobCancelled as exc:
            with _LOCK:
                current = _STATE[name]
                current["status"] = "cancelled"
                current["error"] = str(exc)
                current["finished_at"] = _now()
        except Exception as exc:  # noqa: BLE001 - surfaced through status()
            with _LOCK:
                current = _STATE[name]
                current["status"] = "error"
                current["error"] = str(exc)
                current["finished_at"] = _now()

    threading.Thread(target=_run, daemon=True).start()
    with _LOCK:
        return _public(dict(_STATE[name]))


def _public(job: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in job.items()
        if not key.startswith("_")
    }


def start(name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    if name == "daily_update":
        return _start("daily_update", _run_daily_update, payload)
    if name == "market_daily":
        return _start("market_daily", _run_market_daily, payload)
    raise KeyError(name)


def status(name: str | None = None) -> Any:
    with _LOCK:
        if name is None:
            return [_public(dict(job)) for job in _STATE.values()]
        if name not in _STATE:
            raise KeyError(name)
        return _public(dict(_STATE[name]))


def stop(name: str) -> dict[str, Any]:
    with _LOCK:
        if name not in _STATE:
            raise KeyError(name)
        job = _STATE[name]
        if job["status"] != "running":
            return {"name": name, "accepted": False, "status": job["status"]}
        job["_cancel"] = True
        return {"name": name, "accepted": True, "status": job["status"]}


__all__ = ["start", "status", "stop"]
