"""海关出口数据采集器：UN Comtrade 优先，Open Trade Statistics 兜底，mock 保底。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    COMTRADE_SUBSCRIPTION_KEY,
    CUSTOMS_LATEST_JSON,
    category_name,
)
from src.data.base import generated_at as now_iso, save_latest, seed_for, today as today_iso
from src.trade.hs_code import CATEGORY_HS_CODES

COMTRADE_URL = "https://comtradeplus.un.org/"
OTS_URL = "https://api.tradestatistics.io/trades"
REPORTER_CHINA = "156"
RECENT_YEARS = (2025, 2024, 2023)


def empty_customs_payload() -> dict[str, Any]:
    return {
        "generated_at": None,
        "date": None,
        "period": None,
        "provider": None,
        "source_url": None,
        "fallback_used": False,
        "rows": [],
        "source_count": 0,
        "errors": [],
    }


def _mock_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    today = today_iso()
    for category, entry in CATEGORY_HS_CODES.items():
        seed = seed_for(category)
        rows.append(
            {
                "date": today,
                "period": "2025",
                "category": category,
                "category_name": category_name(category),
                "hs_code": entry["code"],
                "hs_description": entry["description"],
                "reporter": REPORTER_CHINA,
                "reporter_name": "中国",
                "partner": None,
                "flow": "export",
                "value": round(500.0 + seed * 4500.0, 2),
                "source": "mock",
                "fallback_used": True,
            }
        )
    return rows


def _comtrade_rows() -> tuple[list[dict[str, Any]], str, list[str]]:
    import comtradeapicall  # 可选依赖

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    used_period = ""
    for year in RECENT_YEARS:
        if used_period:
            break
        for category, entry in CATEGORY_HS_CODES.items():
            try:
                call_kwargs = dict(
                    typeCode="C",
                    freqCode="A",
                    clCode="HS",
                    period=str(year),
                    reporterCode=REPORTER_CHINA,
                    cmdCode=entry["code"],
                    flowCode="X",
                    partnerCode=None,
                    partner2Code=None,
                    customsCode=None,
                    motCode=None,
                    maxRecords=2500 if COMTRADE_SUBSCRIPTION_KEY else 500,
                    format_output="JSON",
                    aggregateBy=None,
                    breakdownMode="classic",
                    countOnly=None,
                    includeDesc=True,
                )
                if COMTRADE_SUBSCRIPTION_KEY:
                    frame = comtradeapicall.getFinalData(
                        COMTRADE_SUBSCRIPTION_KEY, **call_kwargs
                    )
                else:
                    frame = comtradeapicall.previewFinalData(**call_kwargs)
                if frame is None or frame.empty:
                    continue
                value_column = (
                    "primaryValue" if "primaryValue" in frame.columns else "TradeValue"
                )
                value = float(pd.to_numeric(frame[value_column], errors="coerce").sum())
                rows.append(
                    {
                        "date": today_iso(),
                        "period": str(year),
                        "category": category,
                        "category_name": category_name(category),
                        "hs_code": entry["code"],
                        "hs_description": entry["description"],
                        "reporter": REPORTER_CHINA,
                        "reporter_name": "中国",
                        "partner": None,
                        "flow": "export",
                        "value": round(value, 2),
                        "source": "comtrade",
                        "fallback_used": False,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - 单品类失败不阻塞整体
                errors.append(f"{category}:{entry['code']}: {exc}")
        if rows:
            used_period = str(year)
    if not rows:
        raise RuntimeError("；".join(errors[-3:]) or "UN Comtrade 未返回数据")
    return rows, used_period, errors


def _ots_rows() -> tuple[list[dict[str, Any]], str, list[str]]:
    import requests

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    used_period = ""
    for year in RECENT_YEARS:
        if used_period:
            break
        for category, entry in CATEGORY_HS_CODES.items():
            try:
                response = requests.get(
                    OTS_URL,
                    params={
                        "reporter_iso": "chn",
                        "year": year,
                        "commodity_code": entry["code"],
                        "flow": "export",
                    },
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
                items = data if isinstance(data, list) else data.get("data", [])
                value = sum(
                    float(item.get("trade_value_usd") or 0) for item in items
                )
                rows.append(
                    {
                        "date": today_iso(),
                        "period": str(year),
                        "category": category,
                        "category_name": category_name(category),
                        "hs_code": entry["code"],
                        "hs_description": entry["description"],
                        "reporter": "chn",
                        "reporter_name": "中国",
                        "partner": None,
                        "flow": "export",
                        "value": round(value, 2),
                        "source": "ots",
                        "fallback_used": False,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - 单品类失败不阻塞整体
                errors.append(f"{category}:{entry['code']}: {exc}")
        if rows:
            used_period = str(year)
    if not rows:
        raise RuntimeError("；".join(errors[-3:]) or "Open Trade Statistics 未返回数据")
    return rows, used_period, errors


def collect_customs_exports(
    *,
    offline: bool = False,
) -> dict[str, Any]:
    """采集中国按 HS4 品类汇总的出口数据，失败时逐级回退 mock。"""
    generated_at = now_iso()
    if offline:
        rows = _mock_rows()
        return {
            "generated_at": generated_at,
            "date": today_iso(),
            "period": rows[0]["period"] if rows else None,
            "provider": "mock",
            "source_url": None,
            "fallback_used": True,
            "rows": rows,
            "source_count": len(rows),
            "errors": ["离线模式，未发起真实请求"],
        }

    errors: list[str] = []
    for provider, fetcher in (
        ("comtrade", _comtrade_rows),
        ("ots", _ots_rows),
    ):
        try:
            rows, period, source_errors = fetcher()
            if rows:
                return {
                    "generated_at": generated_at,
                    "date": today_iso(),
                    "period": period,
                    "provider": provider,
                    "source_url": COMTRADE_URL if provider == "comtrade" else OTS_URL,
                    "fallback_used": False,
                    "rows": rows,
                    "source_count": len(rows),
                    "errors": source_errors,
                }
        except Exception as exc:  # noqa: BLE001 - 逐级回退
            errors.append(f"{provider}: {exc}")

    rows = _mock_rows()
    return {
        "generated_at": generated_at,
        "date": today_iso(),
        "period": rows[0]["period"] if rows else None,
        "provider": "mock",
        "source_url": None,
        "fallback_used": True,
        "rows": rows,
        "source_count": len(rows),
        "errors": errors,
    }


def save_latest_customs(payload: dict[str, Any]) -> Path:
    return save_latest(payload, CUSTOMS_LATEST_JSON)


def load_latest_customs() -> dict[str, Any]:
    if not CUSTOMS_LATEST_JSON.exists():
        return empty_customs_payload()
    try:
        payload = json.loads(CUSTOMS_LATEST_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_customs_payload()
    payload.setdefault("rows", [])
    payload.setdefault("errors", [])
    return payload


def customs_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(payload.get("generated_at")),
        "provider": payload.get("provider"),
        "updated_at": payload.get("generated_at"),
        "period": payload.get("period"),
        "source_url": payload.get("source_url"),
        "fallback_used": bool(payload.get("fallback_used")),
        "rows": int(payload.get("source_count") or 0),
        "errors": payload.get("errors") or [],
        "snapshot": "output/customs/latest.json",
    }


__all__ = [
    "collect_customs_exports",
    "customs_status",
    "empty_customs_payload",
    "load_latest_customs",
    "save_latest_customs",
]
