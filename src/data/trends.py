"""Google Trends 采集适配器（可选联网，默认离线回退）。"""

from __future__ import annotations

import json
import math
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.config import (
    CATEGORY_KEYWORDS,
    GOOGLE_TRENDS_COOKIE,
    GOOGLE_TRENDS_ENABLED,
    GOOGLE_TRENDS_MAX_KEYWORDS,
    GOOGLE_TRENDS_PROXIES,
    TRENDS_LATEST_JSON,
    category_name,
)
from src.data.base import generated_at as now_iso, save_latest, seed_for, today


def empty_trends_payload() -> dict[str, Any]:
    return {
        "generated_at": None,
        "date": None,
        "offline": False,
        "fallback_used": False,
        "provider": None,
        "keywords": [],
        "rows": [],
        "series_count": 0,
        "coverage": {"requested": 0, "real": 0, "mock": 0},
        "errors": [],
    }


def _fallback_rows(keywords: dict[str, str], market: str, weeks: int = 52) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    report_date = date.today()
    for category, keyword in keywords.items():
        seed = seed_for(category, market)
        for index in range(weeks):
            day = report_date - timedelta(weeks=weeks - index - 1)
            season = math.sin((index + seed * 12) / 6.0) * 12.0
            trend = index * 0.35
            wave = math.sin((index + seed * 37) / 4.0) * 8.0
            value = max(5.0, min(100.0, 50.0 + season + trend + wave + seed * 5.0))
            rows.append(
                {
                    "date": day.isoformat(),
                    "category": category,
                    "category_name": category_name(category),
                    "keyword": keyword,
                    "market": market,
                    "value": round(value, 2),
                }
            )
    return rows


def _chunked(items: list[tuple[str, str]], size: int = 5) -> Iterable[list[tuple[str, str]]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _cookie_dict(raw: str) -> dict[str, str]:
    """把 ``key=value; key2=value2`` 解析成 pytrends 会话 Cookie。"""
    result: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        if key.strip():
            result[key.strip()] = value.strip()
    return result


def _pytrends_rows(
    keywords: dict[str, str],
    market: str,
    weeks: int = 52,
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    from pytrends.request import TrendReq  # 可选依赖

    kwargs: dict[str, Any] = {"hl": "en-US", "tz": 360, "timeout": (10, 25)}
    if GOOGLE_TRENDS_PROXIES:
        kwargs["proxies"] = GOOGLE_TRENDS_PROXIES
    pytrends = TrendReq(**kwargs)
    if GOOGLE_TRENDS_COOKIE:
        pytrends.cookies = _cookie_dict(GOOGLE_TRENDS_COOKIE)

    rows: list[dict[str, Any]] = []
    real_keywords: list[str] = []
    failed_keywords: list[str] = []
    errors: list[str] = []

    for chunk in _chunked(list(keywords.items())):
        chunk_map = dict(chunk)
        chunk_keywords = [keyword for _, keyword in chunk]
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                pytrends.build_payload(
                    chunk_keywords,
                    timeframe="today 12-m",
                    geo="" if market == "us" else market.upper(),
                )
                frame = pytrends.interest_over_time()
                if frame is None or frame.empty:
                    raise RuntimeError("empty interest_over_time response")
                for category, keyword in chunk_map.items():
                    if keyword not in frame:
                        failed_keywords.append(category)
                        continue
                    values = frame[keyword].tail(weeks)
                    for date, value in values.items():
                        rows.append(
                            {
                                "date": str(pd.Timestamp(date).date()),
                                "category": category,
                                "category_name": category_name(category),
                                "keyword": keyword,
                                "market": market,
                                "value": round(float(value), 2),
                            }
                        )
                    real_keywords.append(category)
                break
            except Exception as exc:  # noqa: BLE001 - 429/网络波动按批次重试
                last_error = exc
                if attempt < 2:
                    time.sleep(2 * (2**attempt))
        if last_error is not None:
            failed_keywords.extend(chunk_map.keys())
            errors.append(f"{','.join(chunk_keywords)}: {last_error}")
    return rows, real_keywords, failed_keywords, errors


def collect_trends(
    keywords: dict[str, str] | None = None,
    market: str = "us",
    *,
    offline: bool = False,
    weeks: int = 52,
) -> dict[str, Any]:
    """采集 Google Trends，失败或未启用时回退确定性 mock 数据。"""
    keywords = keywords or dict(CATEGORY_KEYWORDS)
    generated_at = now_iso()
    fallback_used = True
    provider = "mock"
    rows: list[dict[str, Any]] = []
    error: str | None = None
    real_keywords: list[str] = []
    failed_keywords: list[str] = []
    errors: list[str] = []

    real_target = dict(
        list(keywords.items())[: max(1, GOOGLE_TRENDS_MAX_KEYWORDS)]
    )

    if not offline and GOOGLE_TRENDS_ENABLED:
        try:
            rows, real_keywords, failed_keywords, errors = _pytrends_rows(
                real_target, market, weeks=weeks
            )
            fallback_used = len(real_keywords) < len(keywords)
            provider = "pytrends" if real_keywords else "mock"
        except Exception as exc:  # noqa: BLE001 - 联网失败统一回退
            error = str(exc)
            fallback_used = True
            provider = "mock"
            errors = [str(exc)]

    missing_keywords = [
        category for category in keywords if category not in real_keywords
    ]
    if missing_keywords:
        rows = rows + _fallback_rows(
            {category: keywords[category] for category in missing_keywords},
            market,
            weeks=weeks,
        )

    payload = {
        "generated_at": generated_at,
        "date": today(),
        "offline": bool(offline),
        "fallback_used": fallback_used,
        "provider": provider,
        "keywords": list(keywords.keys()),
        "rows": rows,
        "series_count": len(keywords),
        "coverage": {
            "requested": len(keywords),
            "real": len(real_keywords),
            "mock": len(missing_keywords),
        },
        "errors": errors,
        "error": error,
    }
    return payload


def save_latest_trends(payload: dict[str, Any]) -> Path:
    return save_latest(payload, TRENDS_LATEST_JSON)


def load_latest_trends() -> dict[str, Any]:
    if not TRENDS_LATEST_JSON.exists():
        return empty_trends_payload()
    try:
        payload = json.loads(TRENDS_LATEST_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_trends_payload()
    payload.setdefault("rows", [])
    payload.setdefault("keywords", [])
    payload.setdefault(
        "coverage",
        {
            "requested": len(payload.get("keywords", [])),
            "real": 0,
            "mock": len(payload.get("keywords", [])),
        },
    )
    payload.setdefault("errors", [])
    return payload


def trends_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(payload.get("generated_at")),
        "provider": payload.get("provider"),
        "updated_at": payload.get("generated_at"),
        "date": payload.get("date"),
        "fallback_used": bool(payload.get("fallback_used")),
        "offline": bool(payload.get("offline")),
        "series_count": int(payload.get("series_count") or 0),
        "coverage": payload.get("coverage"),
        "errors": payload.get("errors") or [],
        "snapshot": "output/trends/latest.json",
    }


__all__ = [
    "collect_trends",
    "empty_trends_payload",
    "load_latest_trends",
    "save_latest_trends",
    "trends_status",
]
