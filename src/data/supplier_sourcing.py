"""货源/供应商采集适配器：1688-cli 可选外部 CLI，默认离线回退 mock。

合规说明：
- superjack2050/1688-cli 为 MIT 许可，本模块只以独立子进程调用该 CLI，
  不复制其源码；未安装/未登录/超时/解析失败均回退 mock 并明确标注。
- 本模块不发起网页爬取，不触碰第三方站点 ToS。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.config import (
    CATEGORIES,
    CATEGORY_KEYWORDS,
    MARKETS,
    SUPPLIER_CLI_PATH,
    SUPPLIER_CLI_TIMEOUT_SECONDS,
    SUPPLIER_LATEST_JSON,
    SUPPLIER_MAX_KEYWORDS,
    SUPPLIER_OUTPUT_DIR,
    SUPPLIER_SOURCE_PROVIDERS,
    category_name,
    market_name,
)
from src.data.base import generated_at as now_iso, save_latest, seed_for, today as today_iso

SUPPLIER_MARKET = "cn"
SUPPLIER_MARKET_NAME = "中国货源"


def empty_suppliers_payload() -> dict[str, Any]:
    return {
        "generated_at": None,
        "date": None,
        "offline": False,
        "fallback_used": False,
        "provider": None,
        "rows": [],
        "source_count": 0,
        "coverage": {"requested": 0, "real": 0, "mock": 0},
        "errors": [],
    }


def _mock_rows(
    keywords: dict[str, str],
    markets: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    today = today_iso()
    for category, keyword in keywords.items():
        seed = seed_for(category)
        market = markets[0] if markets else SUPPLIER_MARKET
        rows.append(
            {
                "date": today,
                "category": category,
                "category_name": category_name(category),
                "keyword": keyword,
                "market": SUPPLIER_MARKET,
                "market_name": SUPPLIER_MARKET_NAME,
                "rank": 1,
                "supplier_name": f"演示供应商 {category_name(category)}",
                "member_id": "",
                "location": "广东·深圳（演示）",
                "service_years": round(1.0 + seed * 9.0, 1),
                "repeat_rate": round(0.2 + seed * 0.7, 2),
                "response_rate": round(0.3 + seed * 0.6, 2),
                "score": round(40.0 + seed * 55.0, 1),
                "signals": [],
                "source": "mock",
                "fallback_used": True,
            }
        )
    return rows


def _pick(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _row_from_record(
    record: dict[str, Any],
    category: str,
    keyword: str,
    rank: int,
) -> dict[str, Any]:
    name = str(
        _pick(
            record,
            "companyName",
            "company_name",
            "supplierName",
            "supplier_name",
            "name",
            default=f"1688 供应商 {_pick(record, 'memberId', 'member_id', 'supplierId', default='')}",
        )
        or ""
    ).strip()
    province = str(_pick(record, "province", default="") or "").strip()
    city = str(_pick(record, "city", default="") or "").strip()
    location = str(
        _pick(record, "location", "address", default="") or ""
    ).strip()
    if not location:
        location = f"{province} {city}".strip()
    signals = record.get("signals")
    if not isinstance(signals, list):
        signals = []
    return {
        "date": today_iso(),
        "category": category,
        "category_name": category_name(category),
        "keyword": keyword,
        "market": SUPPLIER_MARKET,
        "market_name": SUPPLIER_MARKET_NAME,
        "rank": int(rank),
        "supplier_name": name or f"1688 供应商 {category_name(category)}",
        "member_id": str(
            _pick(
                record,
                "memberId",
                "member_id",
                "supplierId",
                "supplier_id",
                default="",
            )
            or ""
        ),
        "location": location,
        "service_years": round(
            _as_float(
                _pick(
                    record,
                    "serviceYears",
                    "service_years",
                    "years",
                    default=0.0,
                )
            ),
            1,
        ),
        "repeat_rate": round(
            _as_float(
                _pick(
                    record,
                    "repeatRate",
                    "repeat_rate",
                    "repeatOrderRate",
                    default=0.0,
                )
            ),
            2,
        ),
        "response_rate": round(
            _as_float(
                _pick(
                    record,
                    "responseRate",
                    "response_rate",
                    "replyRate",
                    default=0.0,
                )
            ),
            2,
        ),
        "score": round(
            _as_float(
                _pick(
                    record,
                    "score",
                    "supplierScore",
                    "score_total",
                    default=0.0,
                )
            ),
            1,
        ),
        "signals": signals,
        "source": "1688_cli",
        "fallback_used": False,
    }


def _parse_cli_output(text: str) -> list[dict[str, Any]]:
    """兼容 1688-cli 的单 JSON 与 JSONL 输出。"""
    text = (text or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("suppliers", "results", "rows", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        if any(key in data for key in ("companyName", "company_name", "supplierName", "name")):
            return [data]
        return []
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, list):
            records.extend(item for item in item if isinstance(item, dict))
        elif isinstance(item, dict):
            records.append(item)
    return records


def _run_cli(keyword: str, cli: str) -> str:
    result = subprocess.run(
        [cli, "supplier", "research", keyword, "--enrich", "top:5", "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=SUPPLIER_CLI_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[:300]
        raise RuntimeError(detail or f"1688-cli exited with {result.returncode}")
    return result.stdout


def _cli_rows(
    keywords: dict[str, str],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    cli = SUPPLIER_CLI_PATH or shutil.which("1688")
    if not cli:
        return [], [], [
            "skipped: 未找到 1688 CLI（配置 SUPPLIER_CLI_PATH 或安装 1688-cli）"
        ]
    rows: list[dict[str, Any]] = []
    real_categories: list[str] = []
    errors: list[str] = []
    for category, keyword in keywords.items():
        try:
            text = _run_cli(keyword, cli)
            records = _parse_cli_output(text)
            if not records:
                raise RuntimeError("1688-cli 未返回供应商记录")
            for rank, record in enumerate(records[:5], start=1):
                rows.append(
                    _row_from_record(record, category, keyword, rank)
                )
            real_categories.append(category)
        except Exception as exc:  # noqa: BLE001 - 单品类失败不阻断整体
            errors.append(f"{category}: {exc}")
    return rows, real_categories, errors


def collect_suppliers(
    keywords: dict[str, str] | None = None,
    markets: list[str] | None = None,
    *,
    offline: bool = False,
    providers: list[str] | None = None,
) -> dict[str, Any]:
    """采集货源/供应商数据；1688-cli 失败或离线时回退 mock。"""
    keywords = keywords or dict(CATEGORY_KEYWORDS)
    markets = markets or list(MARKETS.keys())
    providers = providers or SUPPLIER_SOURCE_PROVIDERS or ["mock"]
    generated_at = now_iso()
    target = dict(list(keywords.items())[: max(1, SUPPLIER_MAX_KEYWORDS)])
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    real_categories: list[str] = []

    if offline:
        errors.append("离线模式，未发起真实请求")
    else:
        for provider in providers:
            if provider == "1688_cli":
                provider_rows, provider_real, provider_errors = _cli_rows(target)
                rows.extend(provider_rows)
                real_categories.extend(provider_real)
                errors.extend(provider_errors)
            elif provider == "mock":
                continue

    missing = [category for category in keywords if category not in real_categories]
    if missing:
        rows = rows + _mock_rows(
            {category: keywords[category] for category in missing},
            markets,
        )

    payload = {
        "generated_at": generated_at,
        "date": today_iso(),
        "offline": bool(offline),
        "fallback_used": len(real_categories) < len(keywords),
        "provider": "1688_cli" if real_categories else "mock",
        "rows": rows,
        "source_count": len(rows),
        "coverage": {
            "requested": len(keywords),
            "real": len(real_categories),
            "mock": len(missing),
        },
        "errors": errors,
    }
    return payload


def save_latest_suppliers(payload: dict[str, Any]) -> Path:
    return save_latest(payload, SUPPLIER_LATEST_JSON)


def load_latest_suppliers() -> dict[str, Any]:
    if not SUPPLIER_LATEST_JSON.exists():
        return empty_suppliers_payload()
    try:
        payload = json.loads(SUPPLIER_LATEST_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_suppliers_payload()
    payload.setdefault("rows", [])
    payload.setdefault("errors", [])
    payload.setdefault(
        "coverage",
        {
            "requested": len(payload.get("rows", [])),
            "real": 0,
            "mock": len(payload.get("rows", [])),
        },
    )
    return payload


def supplier_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(payload.get("generated_at")),
        "provider": payload.get("provider"),
        "updated_at": payload.get("generated_at"),
        "date": payload.get("date"),
        "fallback_used": bool(payload.get("fallback_used")),
        "rows": int(payload.get("source_count") or 0),
        "coverage": payload.get("coverage"),
        "errors": payload.get("errors") or [],
        "snapshot": "output/suppliers/latest.json",
    }


__all__ = [
    "collect_suppliers",
    "empty_suppliers_payload",
    "load_latest_suppliers",
    "save_latest_suppliers",
    "supplier_status",
]
