"""Data access and aggregation for the unified FastAPI backend.

All endpoints read the artifacts produced by the project pipeline (processed
CSV, forecast CSV, recommendations CSV, metrics JSON and the trade demo
report). Computed summaries reuse the formulas from the offline dashboard so
API results stay consistent with the demo pages.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from src.analysis.evidence import check_expiry, serialize_evidence
from src.config import (
    CATEGORIES,
    CATEGORY_CATALOG,
    CONTROL_METRICS_JSON,
    CRAWLER_LATEST_JSON,
    DATA_STATUS_JSON,
    ENG_STATUS_JSON,
    FORECAST_CSV,
    MARKETS,
    METRICS_JSON,
    OPEN_FOOD_FACTS_LATEST_JSON,
    OUTPUT_DIR as PROJECT_OUTPUT_DIR,
    PLATFORM_RANKINGS_LATEST_JSON,
    POLICY_LATEST_JSON,
    PROCESSED_CSV,
    REAL_PROXY_STATUS_JSON,
    REAL_TRAINING_STATUS_JSON,
    RECOMMEND_CSV,
    SUPPLIER_LATEST_JSON,
    SYSTEM_EVAL_JSON,
    TEST_WEEKS,
    TRENDS_LATEST_JSON,
    category_name,
    market_name,
)
from src.data.crawler_signals import (
    collect_signal,
    filter_snapshot,
    load_latest_snapshot,
    snapshot_status,
)
from src.data.crawl_quality import build_crawl_quality, write_coverage
from src.data.customs import customs_status, load_latest_customs
from src.data.open_food_facts import (
    load_latest_open_food_facts,
    open_food_facts_status,
)
from src.data.platform_rankings import (
    load_latest_rankings,
    rankings_status,
)
from src.data.real_ingest import load_real_status
from src.data.supplier_sourcing import (
    load_latest_suppliers,
    supplier_status,
)
from src.data.trends import load_latest_trends, trends_status
from src.api.examples import build_examples_payload
from src.trade.catalog import autofill as trade_autofill_build
from src.trade.catalog import catalog_payload
from src.trade.cost import DEFAULT_FX_RATE
from src.trade.hs_code import hs_lookup_table, lookup_hs
from src.trade.policy import _policy_impact_level as _event_impact_level
from src.trade.policy import policy_watchlist
from src.trade.report import OUTPUT_DIR

MODELS: dict[str, str] = {
    "prophet_baseline": "Prophet baseline",
    "lightgbm_advanced": "LightGBM advanced",
    "statsforecast": "StatsForecast baseline",
}

VALID_PLATFORMS = {"prototype", "amazon", "tiktok_shop", "shopee", "aliexpress", "temu"}
TRADE_REPORT_FILE = OUTPUT_DIR / "trade_demo_metrics.json"
CACHE_TTL_SECONDS = float(os.environ.get("BACKEND_CACHE_TTL_SECONDS", "60"))

# 冷链/生鲜食品类目的合规风险更高（保质期、温控与检验检疫要求）。
# 由食品目录的 storage_type 派生，避免硬编码类目名随目录漂移。
_COLD_CHAIN_CATEGORIES = frozenset(
    key
    for key, meta in CATEGORY_CATALOG.items()
    if str(meta.get("storage_type") or "") in {"冷冻", "冷藏"}
)
ENGINEERING_ENDPOINTS = [
    {"method": "GET", "path": "/api/health", "label": "服务健康检查"},
    {"method": "GET", "path": "/api/recommendations", "label": "Top N 选品推荐"},
    {"method": "GET", "path": "/api/policy/events", "label": "政策事件监控清单"},
    {"method": "GET", "path": "/api/policy/impact", "label": "政策冲击实验室"},
    {"method": "GET", "path": "/api/evidence/ledger", "label": "统一证据账本"},
    {"method": "POST", "path": "/api/policy/refresh", "label": "政策雷达立即刷新"},
    {"method": "GET", "path": "/api/trade/decision", "label": "单组合完整贸易决策"},
    {"method": "GET", "path": "/api/trade/report", "label": "15 组合演示报告"},
    {"method": "GET", "path": "/api/trade/hs-code", "label": "HS Code / 关税速查"},
    {"method": "GET", "path": "/api/data/suppliers", "label": "货源/供应商尽调数据"},
]

_LOCK = threading.RLock()
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_LOCKS: dict[str, threading.Lock] = {}
_CACHE_LOCKS_GUARD = threading.Lock()
_DATA_STATUS_CACHE: dict[tuple[str, ...], dict[str, Any]] = {}
_DATA_STATUS_CACHE_LOCK = threading.Lock()
_HISTORY_RECORDS_CACHE: tuple[tuple[int, int], list[dict[str, Any]]] | None = None
_LATEST_ROWS_CACHE: tuple[tuple[int, int], list[dict[str, Any]]] | None = None
_RECORDS_CACHE_LOCK = threading.Lock()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


@lru_cache(maxsize=1)
def history_frame() -> pd.DataFrame:
    return _read_csv(PROCESSED_CSV)


@lru_cache(maxsize=1)
def forecast_frame() -> pd.DataFrame:
    return _read_csv(FORECAST_CSV)


@lru_cache(maxsize=1)
def recommendations_frame() -> pd.DataFrame:
    return _read_csv(RECOMMEND_CSV)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _status_file(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except (OSError, json.JSONDecodeError):
            pass
    return {"enabled": False}


def _file_signature(path: Path) -> tuple[int, int]:
    if not path.exists():
        return (-1, -1)
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


def _history_records() -> list[dict[str, Any]]:
    """History 全量记录缓存（按 CSV mtime/size 失效）。"""
    global _HISTORY_RECORDS_CACHE
    sig = _file_signature(PROCESSED_CSV)
    with _RECORDS_CACHE_LOCK:
        if _HISTORY_RECORDS_CACHE is not None and _HISTORY_RECORDS_CACHE[0] == sig:
            return _HISTORY_RECORDS_CACHE[1]
    rows = _records(history_frame())
    with _RECORDS_CACHE_LOCK:
        _HISTORY_RECORDS_CACHE = (sig, rows)
    return rows


def _filter_records(
    rows: list[dict[str, Any]],
    filters: dict[str, str | None],
) -> list[dict[str, Any]]:
    """Python 侧记录过滤，替代 pandas 全表 to_json 后的重复序列化。"""
    _validate(filters)
    category = filters.get("category")
    market = filters.get("market")
    model = filters.get("model")
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    limit = filters.get("limit")

    result = rows
    if category:
        result = [row for row in result if row.get("category") == category]
    if market:
        result = [row for row in result if row.get("market") == market]
    if model:
        result = [
            row
            for row in result
            if "model" not in row or row.get("model") == model
        ]
    if date_from:
        result = [row for row in result if str(row.get("date", "")) >= date_from]
    if date_to:
        result = [row for row in result if str(row.get("date", "")) <= date_to]
    try:
        limit_value = int(limit) if limit else 0
    except (TypeError, ValueError):
        limit_value = 0
    if limit_value > 0:
        result = result[:limit_value]
    return result


def _cache_get(key: str, producer: Any) -> Any:
    if CACHE_TTL_SECONDS <= 0:
        return producer()
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] <= CACHE_TTL_SECONDS:
            return hit[1]
    with _CACHE_LOCKS_GUARD:
        lock = _CACHE_LOCKS.setdefault(key, threading.Lock())
    with lock:
        with _LOCK:
            hit = _CACHE.get(key)
            if hit and now - hit[0] <= CACHE_TTL_SECONDS:
                return hit[1]
        value = producer()
        with _LOCK:
            _CACHE[key] = (time.time(), value)
        return value


def _filter_key(filters: dict[str, str | None]) -> str:
    return "|".join(
        f"{key}={value or ''}"
        for key, value in sorted(filters.items())
        if value not in (None, "")
    )


def _validate(filters: dict[str, str | None]) -> None:
    checks = {
        "category": set(CATEGORIES),
        "market": set(MARKETS),
        "model": set(MODELS),
        "platform": VALID_PLATFORMS,
    }
    for key, allowed in checks.items():
        value = filters.get(key)
        if value and value not in allowed:
            raise ValueError(f"Invalid {key}: {value}. Allowed values: {sorted(allowed)}")


def _apply_filters(df: pd.DataFrame, filters: dict[str, str | None]) -> pd.DataFrame:
    _validate(filters)
    category = filters.get("category")
    market = filters.get("market")
    model = filters.get("model")
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    limit = filters.get("limit")

    result = df
    if not result.empty:
        if category:
            result = result[result["category"] == category]
        if market:
            result = result[result["market"] == market]
        if model and "model" in result.columns:
            result = result[result["model"] == model]
        if date_from:
            result = result[result["date"].astype(str) >= date_from]
        if date_to:
            result = result[result["date"].astype(str) <= date_to]
    try:
        limit_value = int(limit) if limit else 0
    except (TypeError, ValueError):
        limit_value = 0
    if limit_value > 0:
        result = result.head(limit_value)
    return result


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _pct_change(current: float, previous: float) -> float:
    return 0.0 if abs(previous) < 1e-9 else round((current - previous) / previous * 100, 2)


def categories() -> dict[str, str]:
    return CATEGORIES


def markets() -> dict[str, str]:
    return MARKETS


def models() -> dict[str, str]:
    return MODELS


def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "cross-border-selection-backend",
        "data_status": data_status(),
        "data_files": {
            "history": PROCESSED_CSV.exists(),
            "forecast": FORECAST_CSV.exists(),
            "recommendations": RECOMMEND_CSV.exists(),
            "metrics": METRICS_JSON.exists(),
            "trade_report": TRADE_REPORT_FILE.exists(),
        },
    }


def _data_status_version_key() -> tuple[str, ...]:
    paths = [
        DATA_STATUS_JSON,
        PROCESSED_CSV,
        FORECAST_CSV,
        RECOMMEND_CSV,
        METRICS_JSON,
        CRAWLER_LATEST_JSON,
        TRENDS_LATEST_JSON,
        PLATFORM_RANKINGS_LATEST_JSON,
        OPEN_FOOD_FACTS_LATEST_JSON,
        SUPPLIER_LATEST_JSON,
        POLICY_LATEST_JSON,
        REAL_TRAINING_STATUS_JSON,
        REAL_PROXY_STATUS_JSON,
    ]
    return tuple(
        f"{path.resolve()}:{_file_signature(path)}"
        for path in paths
    )


def data_status() -> dict[str, Any]:
    """返回每日数据更新状态；按产物版本缓存，不再每请求重算并写 coverage。"""
    version = _data_status_version_key()
    with _DATA_STATUS_CACHE_LOCK:
        cached = _DATA_STATUS_CACHE.get(version)
        if cached is not None:
            return cached
    status = _data_status_build()
    with _DATA_STATUS_CACHE_LOCK:
        _DATA_STATUS_CACHE[version] = status
    return status


def _data_status_build() -> dict[str, Any]:
    """未命中版本缓存时构建 data_status（仅在此路径写 coverage）。"""
    if DATA_STATUS_JSON.exists():
        try:
            status = json.loads(DATA_STATUS_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            status = None
        if status is not None:
            status.setdefault("crawler", snapshot_status(load_latest_snapshot()))
            status.setdefault("trends", trends_status(load_latest_trends()))
            status.setdefault(
                "platform_rankings",
                rankings_status(load_latest_rankings()),
            )
            status.setdefault("market_daily", {"enabled": False})
            status.setdefault(
                "open_food_facts",
                open_food_facts_status(load_latest_open_food_facts()),
            )
            status.setdefault(
                "suppliers",
                supplier_status(load_latest_suppliers()),
            )
            status.setdefault("real_training", {"enabled": False})
            status.setdefault("real_proxy", {"enabled": False})
            status["real_training"] = {
                **status["real_training"],
                **_status_file(REAL_TRAINING_STATUS_JSON),
            }
            status["real_proxy"] = {
                **status["real_proxy"],
                **_status_file(REAL_PROXY_STATUS_JSON),
            }
            quality = build_crawl_quality(status)
            status["crawl_quality"] = quality
            status["decision_data_ready"] = quality["decision_data_ready"]
            status["real_data"] = load_real_status()
            write_coverage(quality)
            return status
    rows = _history_records()
    latest = max((str(row["date"]) for row in rows), default=None)
    status = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "data_as_of": latest,
        "as_of_label": (
            f"数据更新至 {latest}（当日）" if latest else "数据未更新"
        ),
        "next_update": (
            pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
        ).strftime("%Y-%m-%d"),
        "online": {
            "provider": os.environ.get("SEARCH_PROVIDER", "duckduckgo_html"),
            "fallback_used": True,
            "snapshot": "",
            "sources_count": 0,
        },
        "updated_files": [],
        "crawler": snapshot_status(load_latest_snapshot()),
        "trends": trends_status(load_latest_trends()),
        "platform_rankings": rankings_status(load_latest_rankings()),
        "market_daily": {"enabled": False},
        "open_food_facts": open_food_facts_status(load_latest_open_food_facts()),
        "suppliers": supplier_status(load_latest_suppliers()),
        "real_training": _status_file(REAL_TRAINING_STATUS_JSON),
        "real_proxy": _status_file(REAL_PROXY_STATUS_JSON),
    }
    quality = build_crawl_quality(status)
    status["crawl_quality"] = quality
    status["decision_data_ready"] = quality["decision_data_ready"]
    status["real_data"] = load_real_status()
    write_coverage(quality)
    return status


def suppliers() -> dict[str, Any]:
    """返回最新货源/供应商快照及其状态。"""
    payload = load_latest_suppliers()
    return {
        **supplier_status(payload),
        "rows": payload.get("rows", []),
    }


def hs_code(category: str, market: str) -> dict[str, Any]:
    return lookup_hs(category, market)


def hs_codes() -> list[dict[str, Any]]:
    return hs_lookup_table()


def hs_codes_search(
    query: str | None = None,
    category: str | None = None,
    market: str | None = None,
) -> list[dict[str, Any]]:
    """按关键词 / 品类 / 市场检索 HS 速查表。"""
    q = (query or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for row in hs_lookup_table():
        if category and row["category"] != category:
            continue
        haystack = " ".join(
            [
                row.get("hs_code", ""),
                row.get("description", ""),
                row.get("category", ""),
            ]
        ).lower()
        if q and q not in haystack:
            continue
        if market:
            detail = lookup_hs(row["category"], market)
            row = {
                **row,
                "market": market,
                "base_tariff_rate": detail.get("base_tariff_rate", 0.0),
                "verified": detail.get("verified", False),
                "note": detail.get("note"),
            }
        rows.append(row)
    return rows


def examples() -> dict[str, Any]:
    """三套系统与立项报告的示例预设。"""
    return build_examples_payload()


def anomalies() -> dict[str, Any]:
    """最新异常监测快照；缺失时返回空列表而不是报错。"""
    from src.analysis.anomaly import load_latest_anomalies

    return load_latest_anomalies()


def history(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    key = f"history|{_filter_key(filters)}"
    return _cache_get(
        key,
        lambda: _filter_records(_history_records(), filters),
    )


def forecast(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    key = f"forecast|{_filter_key(filters)}"
    return _cache_get(key, lambda: _records(_apply_filters(forecast_frame(), filters)))


def metrics() -> dict[str, Any]:
    if not METRICS_JSON.exists():
        return {"baseline": [], "advanced": []}
    return json.loads(METRICS_JSON.read_text(encoding="utf-8"))


def model_metrics(filters: dict[str, str | None]) -> dict[str, Any]:
    _validate(filters)
    data = metrics()
    model = filters.get("model")
    if not model:
        return data
    filtered: dict[str, Any] = {}
    for key, rows in data.items():
        # 行列表键（baseline/advanced/statsforecast）按模型过滤；
        # 非行列表键（如 business_metrics 对象）原样透传，避免 str.get 崩溃。
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            filtered[key] = [row for row in rows if row.get("model") == model]
        else:
            filtered[key] = rows
    return filtered


def evidence_ledger() -> dict[str, Any]:
    """统一证据账本：政策事件 + HS6 速查条目，归一化并附过期状态。"""
    records: list[dict[str, Any]] = []
    for event in policy_watchlist():
        verified = bool(event.get("verified"))
        records.append(
            {
                "key": event.get("code"),
                "title": event.get("title"),
                "source": event.get("source") or event.get("url"),
                "url": event.get("url"),
                "fetched_at": event.get("published_at") or event.get("date"),
                "effective_date": event.get("effective_date"),
                "validity_days": 365,
                "hs_version": None,
                "formula": "政策事件 → 有效税率 / 到岸成本 / 风险等级",
                "model_version": None,
                "confidence_interval": None,
                "review_status": "已核实" if verified else "待复核",
                "status": "已核实" if verified else "待核实",
            }
        )
    for row in hs_lookup_table():
        verified = bool(row.get("verified"))
        title = f"HS6 {row.get('hs_code')} {row.get('description') or ''}".strip()
        records.append(
            {
                "key": row.get("hs_code"),
                "title": title,
                "source": "本地 Harmonized System 数据集",
                "url": None,
                "fetched_at": None,
                "effective_date": None,
                "validity_days": None,
                "hs_version": "HS2022",
                "formula": "HS6 子目速查（正式申报前需按海关税则核对）",
                "model_version": None,
                "confidence_interval": None,
                "review_status": "已核实" if verified else "待复核",
                "status": "已核实" if verified else "待核实",
            }
        )
    payload = serialize_evidence(records)
    for item in payload["items"]:
        item["expiry_status"] = check_expiry(item)
    return payload


def _system_baseline() -> dict[str, float | None]:
    """从 models/metrics.json 计算宏平均 MAPE，作为对照组系统基线。"""

    def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    payload = metrics()
    return {
        "prophet_mape": _mean(payload.get("baseline", []), "mape"),
        "lightgbm_mape": _mean(payload.get("advanced", []), "mape"),
    }


def _model_summary() -> dict[str, Any]:
    """当前全量模型指标的宏平均摘要（全组合 × 最近 12 周）。"""
    payload = metrics()

    def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    base_mape = _mean(payload.get("baseline", []), "mape")
    adv_mape = _mean(payload.get("advanced", []), "mape")
    combos = max(len(payload.get("baseline", [])), len(payload.get("advanced", [])))
    return {
        "combos": combos,
        "test_weeks": 12,
        "cells": combos * 12,
        "prophet": {
            "mape": base_mape,
            "mae": _mean(payload.get("baseline", []), "mae"),
        },
        "lightgbm": {
            "mape": adv_mape,
            "mae": _mean(payload.get("advanced", []), "mae"),
        },
        "improve_pct": (
            round((base_mape - adv_mape) / base_mape * 100, 2)
            if base_mape and adv_mape is not None
            else None
        ),
    }


def system_eval() -> dict[str, Any]:
    """只读返回当前系统评测指标（06B 技术能力检验数据源）。"""
    data: dict[str, Any] = {}
    if SYSTEM_EVAL_JSON.exists():
        try:
            data = json.loads(SYSTEM_EVAL_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"error": True}
    pass_map = data.get("pass") if isinstance(data, dict) else None
    failed_metrics = (
        sorted(key for key, value in pass_map.items() if not value)
        if isinstance(pass_map, dict)
        else []
    )
    return {
        "source": "file" if SYSTEM_EVAL_JSON.exists() else "missing",
        "system_eval": data,
        "model_summary": _model_summary(),
        "gate": {
            "passed": not failed_metrics,
            "failed_metrics": failed_metrics,
        },
    }


def control_metrics() -> dict[str, Any]:
    """只读返回顶级 AI 对照实验结果；未运行或文件缺失时给出明确状态。"""
    data: dict[str, Any] = {}
    source = "missing"
    candidates = [
        CONTROL_METRICS_JSON,
        OUTPUT_DIR / "control_metrics.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        source = "file"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"parse_error": True}
        break

    models_payload = data.get("models", {}) if isinstance(data, dict) else {}
    model_count = len(models_payload) if isinstance(models_payload, dict) else 0
    scope = next(
        (
            entry.get("scope")
            for entry in models_payload.values()
            if isinstance(entry, dict) and entry.get("scope")
        ),
        None,
    )
    if data.get("parse_error"):
        status = "error"
    elif model_count == 0:
        status = "not_run"
    elif all(
        isinstance(entry, dict) and len(entry.get("runs", {})) >= 2
        for entry in models_payload.values()
    ):
        status = "done"
    else:
        status = "partial"

    return {
        "source": source,
        "status": status,
        "generated_at": data.get("generated_at") if isinstance(data, dict) else None,
        "train_dates": data.get("train_dates") if isinstance(data, dict) else None,
        "holdout_dates": data.get("holdout_dates") if isinstance(data, dict) else None,
        "total_cells": (
            data.get("total_cells", len(CATEGORIES) * len(MARKETS) * TEST_WEEKS)
            if isinstance(data, dict)
            else len(CATEGORIES) * len(MARKETS) * TEST_WEEKS
        ),
        "system_baseline": (
            data.get("system_baseline", _system_baseline())
            if isinstance(data, dict)
            else _system_baseline()
        ),
        "scope": scope,
        "models": models_payload,
        **system_eval(),
    }


def engineering_status() -> dict[str, Any]:
    """只读返回工程化状态：数据更新、测试数量与公开 API 清单。"""
    data_status_payload = data_status()
    online = data_status_payload.get("online") or {}
    eng: dict[str, Any] = {}
    if ENG_STATUS_JSON.exists():
        try:
            eng = json.loads(ENG_STATUS_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            eng = {}
    return {
        "data_as_of": data_status_payload.get("data_as_of"),
        "generated_at": data_status_payload.get("generated_at"),
        "provider": online.get("provider"),
        "fallback_used": online.get("fallback_used"),
        "snapshot_sources": online.get("sources_count"),
        "capabilities": _capability_status(data_status_payload),
        "test_count": eng.get("test_count") or eng.get("test_collected"),
        "test_passed": eng.get("test_passed"),
        "build": eng.get("build", {}),
        "endpoints": ENGINEERING_ENDPOINTS,
    }


def _capability_status(data_status_payload: dict[str, Any]) -> dict[str, Any]:
    """Build live snapshot status for the policy/cost and compliance capabilities."""
    events: list[dict[str, Any]] = []
    snapshot: dict[str, Any] = {}
    status = "stale"
    try:
        if POLICY_LATEST_JSON.exists():
            snapshot = json.loads(POLICY_LATEST_JSON.read_text(encoding="utf-8"))
            events = list(snapshot.get("events") or [])
            status = "ready"
    except (OSError, json.JSONDecodeError):
        snapshot = {}
        events = []

    policy_status = data_status_payload.get("policy") or {}
    if (
        status != "ready"
        and isinstance(policy_status, dict)
        and policy_status.get("status") == "ready"
    ):
        status = "ready"
        snapshot = {
            "generated_at": policy_status.get("updated_at"),
            "date": policy_status.get("date"),
            "provider": policy_status.get("provider"),
            "fallback_used": policy_status.get("fallback_used"),
        }
        try:
            if POLICY_LATEST_JSON.exists():
                latest = json.loads(POLICY_LATEST_JSON.read_text(encoding="utf-8"))
                events = list(latest.get("events") or [])
                snapshot.update(
                    {
                        key: latest.get(key)
                        for key in (
                            "generated_at",
                            "date",
                            "provider",
                            "fallback_used",
                        )
                    }
                )
        except (OSError, json.JSONDecodeError):
            events = []

    compliance_types = {"compliance", "customs", "macro"}
    compliance_events = [
        event for event in events if event.get("policy_type") in compliance_types
    ]

    def _common(event_list: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "status": status,
            "updated_at": snapshot.get("generated_at")
            or (policy_status.get("updated_at") if isinstance(policy_status, dict) else "")
            or "",
            "date": snapshot.get("date")
            or (policy_status.get("date") if isinstance(policy_status, dict) else "")
            or "",
            "provider": snapshot.get("provider")
            or (policy_status.get("provider") if isinstance(policy_status, dict) else None)
            or None,
            "fallback_used": bool(
                snapshot.get("fallback_used")
                or (policy_status.get("fallback_used") if isinstance(policy_status, dict) else False)
            ),
            "events": len(event_list),
            "high_risk": sum(
                1 for event in event_list if _event_impact_level(event) == "high"
            ),
        }

    return {
        "policy_cost": _common(events),
        "compliance": _common(compliance_events),
    }


def recommendations(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    filters = dict(filters)
    min_score = filters.get("min_score")
    limit = filters.get("limit") or filters.get("top") or "10"
    include_no_go = filters.pop("include_no_go", None) == "1"
    filters.pop("top", None)
    df = _apply_filters(recommendations_frame(), filters)
    rows = _records(df)
    if min_score not in (None, ""):
        threshold = float(min_score)
        rows = [
            row
            for row in rows
            if float(row.get("six_dimension_score", row.get("score", 0))) >= threshold
        ]
    if not include_no_go:
        rows = [row for row in rows if row.get("verdict") in {"Go", "Conditional"}]
    rows = sorted(
        rows,
        key=lambda r: (
            -float(r.get("six_dimension_score", r.get("score", 0))),
            -float(r.get("forecast_growth", 0.0)),
            -float(r.get("search_trend", 0.0)),
            str(r.get("category", "")),
            str(r.get("market", "")),
        ),
    )
    try:
        limit_value = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit_value = 10
    result = []
    for index, row in enumerate(rows[:limit_value], start=1):
        item = dict(row)
        item["rank"] = index
        item["recommendable"] = item.get("verdict") != "No-Go"
        item["category_name"] = category_name(item.get("category", ""))
        item["market_name"] = market_name(item.get("market", ""))
        result.append(item)
    return result


def trade_report(
    filters: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """贸易演示报告；支持 market/risk_level/limit/offset 过滤，无参数返回全量。"""
    filters = filters or {}
    key = f"trade_report|{_filter_key(filters)}"

    def _build() -> dict[str, Any]:
        if not TRADE_REPORT_FILE.exists():
            raise FileNotFoundError(
                "Trade demo report is missing; run scripts/run_trade_demo.py first"
            )
        raw = json.loads(TRADE_REPORT_FILE.read_text(encoding="utf-8"))
        market = filters.get("market")
        risk_level = filters.get("risk_level")
        limit = filters.get("limit")
        offset = filters.get("offset")
        if not any((market, risk_level, limit, offset)):
            return raw
        rows = list(raw.get("rows") or [])
        if market:
            rows = [row for row in rows if row.get("market") == market]
        if risk_level:
            rows = [row for row in rows if row.get("risk_level") == risk_level]
        try:
            offset_value = int(offset) if offset else 0
        except (TypeError, ValueError):
            offset_value = 0
        try:
            limit_value = int(limit) if limit else 0
        except (TypeError, ValueError):
            limit_value = 0
        if offset_value > 0:
            rows = rows[offset_value:]
        if limit_value > 0:
            rows = rows[:limit_value]
        result = dict(raw)
        result["filtered"] = len(rows)
        result["rows"] = rows
        return result

    return _cache_get(key, _build)


def policy_events() -> list[dict[str, Any]]:
    return policy_watchlist()


def policy_watch_payload() -> dict[str, Any]:
    """Return verified policy events plus snapshot metadata for the UI."""
    items = policy_events()
    snapshot: dict[str, Any] = {}
    if POLICY_LATEST_JSON.exists():
        try:
            snapshot = json.loads(POLICY_LATEST_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            snapshot = {}
    snapshot_events = list(snapshot.get("events") or [])
    verified_events = [
        event for event in snapshot_events if bool(event.get("verified"))
    ]
    return {
        "items": items,
        "verified_count": int(
            snapshot.get("verified_count")
            or len(verified_events)
            or len(items)
        ),
        "candidate_count": int(snapshot.get("candidate_count") or 0),
        "candidate_items": list(snapshot.get("candidate_events") or []),
        "updated_at": snapshot.get("generated_at") or "",
        "date": snapshot.get("date") or "",
        "sources": snapshot.get("sources") or {},
        "fallback_used": bool(snapshot.get("fallback_used")),
        "official_only": bool(snapshot.get("official_only", True)),
    }


def refresh_policy(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Trigger an on-demand Policy Radar refresh."""
    from src.data.policy_refresh import (
        policy_snapshot_status,
        refresh_policy_snapshot,
    )

    payload = payload or {}
    offline = bool(payload.get("offline"))
    include_search = bool(payload.get("include_search"))
    providers_raw = payload.get("providers")
    providers = None
    if providers_raw:
        if isinstance(providers_raw, str):
            providers = [
                item.strip()
                for item in providers_raw.split(",")
                if item.strip()
            ]
        else:
            providers = [str(item) for item in providers_raw]
    search_func = None
    if include_search and not offline:
        from src.api import brain_bridge

        if brain_bridge.available():
            search_func = brain_bridge.search
    snapshot = refresh_policy_snapshot(
        search_func,
        offline=offline,
        provider="official",
        official_providers=providers,
        include_search=include_search,
    )
    return {
        "ok": True,
        "refreshed_at": snapshot.get("generated_at"),
        "status": policy_snapshot_status(snapshot),
        **policy_watch_payload(),
    }


def _latest_history_rows() -> list[dict[str, Any]]:
    global _LATEST_ROWS_CACHE
    sig = _file_signature(PROCESSED_CSV)
    with _RECORDS_CACHE_LOCK:
        if _LATEST_ROWS_CACHE is not None and _LATEST_ROWS_CACHE[0] == sig:
            return _LATEST_ROWS_CACHE[1]
    rows = _history_records()
    if not rows:
        return []
    latest_date = max(str(row["date"]) for row in rows)
    latest = [row for row in rows if str(row["date"]) == latest_date]
    with _RECORDS_CACHE_LOCK:
        _LATEST_ROWS_CACHE = (sig, latest)
    return latest


def _summarize_latest(metric: str, filters: dict[str, str | None]) -> list[dict[str, Any]]:
    filtered = _filter_records(_latest_history_rows(), filters)
    result = []
    for row in filtered:
        result.append(
            {
                "category": row["category"],
                "category_name": category_name(row["category"]),
                "market": row["market"],
                "market_name": market_name(row["market"]),
                "date": row["date"],
                metric: row.get(metric),
            }
        )
    return result


def search_trends(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    key = f"search_trends|{_filter_key(filters)}"

    def _build() -> list[dict[str, Any]]:
        rows = _filter_records(_history_records(), filters)
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault((row["category"], row["market"]), []).append(row)

        result = []
        for (category, market), items in grouped.items():
            ordered = sorted(items, key=lambda r: str(r["date"]))
            recent = ordered[-4:]
            previous = ordered[-8:-4]
            recent_avg = _average([float(r["search_index"]) for r in recent])
            previous_avg = _average([float(r["search_index"]) for r in previous])
            result.append(
                {
                    "category": category,
                    "category_name": category_name(category),
                    "market": market,
                    "market_name": market_name(market),
                    "recent_search_index": recent_avg,
                    "previous_search_index": previous_avg,
                    "trend_pct": _pct_change(recent_avg, previous_avg),
                    "series": [
                        {"date": r["date"], "search_index": r["search_index"]}
                        for r in ordered
                    ],
                }
            )
        return sorted(result, key=lambda r: r["trend_pct"], reverse=True)

    return _cache_get(key, _build)


def review_summary(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    key = f"review_summary|{_filter_key(filters)}"

    def _build() -> list[dict[str, Any]]:
        rows = _filter_records(_history_records(), filters)
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault((row["category"], row["market"]), []).append(row)

        result = []
        for (category, market), items in grouped.items():
            ordered = sorted(items, key=lambda r: str(r["date"]))
            recent = ordered[-4:]
            avg_growth = _average([float(r["review_growth"]) for r in recent])
            result.append(
                {
                    "category": category,
                    "category_name": category_name(category),
                    "market": market,
                    "market_name": market_name(market),
                    "avg_review_growth": avg_growth,
                    "activity_level": (
                        "active"
                        if avg_growth >= 2
                        else "stable"
                        if avg_growth >= 0
                        else "weak"
                    ),
                }
            )
        return sorted(result, key=lambda r: r["avg_review_growth"], reverse=True)

    return _cache_get(key, _build)


def export_value(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    key = f"export_value|{_filter_key(filters)}"
    return _cache_get(
        key,
        lambda: _summarize_latest("export_value", filters),
    )


def competition_index(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    key = f"competition_index|{_filter_key(filters)}"
    return _cache_get(
        key,
        lambda: _summarize_latest("competition_index", filters),
    )


def platform_rankings(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    key = f"platform_rankings|{_filter_key(filters)}"

    def _build() -> list[dict[str, Any]]:
        _validate(filters)
        rows = _filter_records(_latest_history_rows(), filters)
        limit = int(filters.get("limit") or 20)
        platform = filters.get("platform") or "prototype"
        ranked = sorted(
            rows,
            key=lambda r: (
                float(r.get("bestseller_rank", 999999)),
                -float(r.get("sales_volume", 0)),
            ),
        )
        result = []
        for index, row in enumerate(ranked[: min(limit, 100)], start=1):
            result.append(
                {
                    "rank": index,
                    "platform": platform,
                    "category": row["category"],
                    "category_name": category_name(row["category"]),
                    "market": row["market"],
                    "market_name": market_name(row["market"]),
                    "date": row["date"],
                    "bestseller_rank": row["bestseller_rank"],
                    "sales_volume": row["sales_volume"],
                    "price_median": row["price_median"],
                }
            )
        return result

    return _cache_get(key, _build)


def cost_metrics(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    key = f"cost_metrics|{_filter_key(filters)}"

    def _build() -> list[dict[str, Any]]:
        rows = _filter_records(_latest_history_rows(), filters)
        result = []
        for row in rows:
            price = float(row["price_median"])
            competition = float(row["competition_index"])
            market = row["market"]
            logistics_rates = {
                "us": 0.12, "eu": 0.15, "sea": 0.10, "jp": 0.13,
                "ca": 0.12, "au": 0.11, "uk": 0.13, "kr": 0.10,
                "de": 0.14, "fr": 0.15, "vn": 0.09, "ru": 0.17,
                "hu": 0.12, "ae": 0.13, "mx": 0.15,
            }
            logistics_rate = logistics_rates.get(market, 0.10)
            logistics_cost = round(price * logistics_rate, 2)
            ad_cost_index = round(competition * 0.72 + 12, 2)
            return_rate = round(4.0 + competition / 30, 2)
            gross_margin = round(
                max(8.0, 42.0 - logistics_cost / max(price, 1) * 100 - ad_cost_index / 10),
                2,
            )
            compliance_risk = round(
                competition * 0.35
                + (12 if row["category"] in _COLD_CHAIN_CATEGORIES else 6),
                2,
            )
            result.append(
                {
                    "category": row["category"],
                    "category_name": category_name(row["category"]),
                    "market": market,
                    "market_name": market_name(market),
                    "date": row["date"],
                    "gross_margin": gross_margin,
                    "logistics_cost": logistics_cost,
                    "return_rate": return_rate,
                    "ad_cost_index": ad_cost_index,
                    "compliance_risk": compliance_risk,
                    "risk_score": round(
                        (100 - gross_margin) * 0.25
                        + return_rate * 2
                        + compliance_risk * 0.45
                        + ad_cost_index * 0.15,
                        2,
                    ),
                    "source": "prototype_estimate",
                }
            )
        return result

    return _cache_get(key, _build)


def risk_overview(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    key = f"risk_overview|{_filter_key(filters)}"

    def _build() -> list[dict[str, Any]]:
        rows = cost_metrics(filters)
        result = []
        for row in rows:
            item = dict(row)
            score = float(item["risk_score"])
            item["risk_level"] = (
                "high" if score >= 55 else "medium" if score >= 38 else "low"
            )
            item["risk_reason"] = "综合毛利、物流、退货、广告成本和合规风险"
            result.append(item)
        return sorted(result, key=lambda r: r["risk_score"], reverse=True)

    return _cache_get(key, _build)


def market_compare(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    key = f"market_compare|{_filter_key(filters)}"

    def _build() -> list[dict[str, Any]]:
        rows = _filter_records(_history_records(), filters)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row["market"]), []).append(row)
        result = []
        for market, items in grouped.items():
            result.append(
                {
                    "market": market,
                    "market_name": market_name(market),
                    "avg_sales_volume": _average(
                        [float(r["sales_volume"]) for r in items]
                    ),
                    "avg_competition_index": _average(
                        [float(r["competition_index"]) for r in items]
                    ),
                    "avg_price_median": _average(
                        [float(r["price_median"]) for r in items]
                    ),
                    "avg_export_value": _average(
                        [float(r["export_value"]) for r in items]
                    ),
                }
            )
        return sorted(result, key=lambda r: r["avg_sales_volume"], reverse=True)

    return _cache_get(key, _build)


def market_intel(filters: dict[str, str | None]) -> dict[str, Any]:
    """看板「数据纵深」聚合：榜单/趋势/海关直接读真实快照，其余沿用特征口径。"""
    key = f"market_intel|{_filter_key(filters)}|{_data_status_version_key()}"

    def _build() -> dict[str, Any]:
        category = filters.get("category")
        market = filters.get("market")
        try:
            limit = max(1, min(int(filters.get("limit") or 20), 100))
        except (TypeError, ValueError):
            limit = 20

        def _match(row: dict[str, Any]) -> bool:
            return (not category or row.get("category") == category) and (
                not market or row.get("market") == market
            )

        rankings_payload = load_latest_rankings()
        ranking_rows = [
            row for row in rankings_payload.get("rows", []) if _match(row)
        ]
        ranking_rows.sort(
            key=lambda r: (
                int(r.get("rank") or 999999),
                str(r.get("platform") or ""),
            )
        )
        real_rank = sum(
            1 for row in ranking_rows if not bool(row.get("fallback_used"))
        )
        ranking_items = [
            {
                "rank": index,
                "category": row.get("category"),
                "category_name": row.get("category_name")
                or category_name(str(row.get("category") or "")),
                "market": row.get("market"),
                "market_name": row.get("market_name")
                or market_name(str(row.get("market") or "")),
                "platform": row.get("platform"),
                "title": row.get("product") or row.get("title") or "--",
                "price": row.get("price"),
                "score": (
                    row.get("rating")
                    if row.get("rating") is not None
                    else row.get("sold_count")
                ),
                "source": row.get("source"),
                "fallback_used": bool(row.get("fallback_used")),
                "url": row.get("url"),
            }
            for index, row in enumerate(ranking_rows[:limit], start=1)
        ]
        rankings = {
            "count": len(ranking_rows),
            "items": ranking_items,
            "real_count": real_rank,
            "mock_count": len(ranking_rows) - real_rank,
            **rankings_status(rankings_payload),
        }

        trends_payload = load_latest_trends()
        trend_rows = [
            row for row in trends_payload.get("rows", []) if _match(row)
        ]
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in trend_rows:
            key_pair = (
                str(row.get("category") or ""),
                str(row.get("market") or ""),
            )
            grouped.setdefault(key_pair, []).append(row)

        trend_items: list[dict[str, Any]] = []
        for (cat, mkt), series in grouped.items():
            ordered = sorted(series, key=lambda r: str(r.get("date") or ""))
            recent = ordered[-4:]
            previous = ordered[-8:-4]
            recent_avg = _average(
                [float(r.get("value") or 0) for r in recent]
            )
            previous_avg = _average(
                [float(r.get("value") or 0) for r in previous]
            )
            trend_items.append(
                {
                    "category": cat,
                    "category_name": category_name(cat),
                    "market": mkt,
                    "market_name": market_name(mkt),
                    "search_trend": _pct_change(recent_avg, previous_avg),
                    "latest_value": recent[-1].get("value") if recent else None,
                    "fallback_used": bool(trends_payload.get("fallback_used")),
                }
            )
        trend_items.sort(
            key=lambda r: float(r.get("search_trend") or 0), reverse=True
        )
        search_trends = {
            "count": len(trend_items),
            "items": trend_items[:12],
            **trends_status(trends_payload),
        }

        customs_payload = load_latest_customs()
        customs_rows = [
            row
            for row in customs_payload.get("rows", [])
            if not category or row.get("category") == category
        ]
        customs_items = [
            {
                "category": row.get("category"),
                "category_name": row.get("category_name")
                or category_name(str(row.get("category") or "")),
                "market": "",
                "market_name": "中国出口",
                "export_value": row.get("value"),
                "hs_code": row.get("hs_code"),
                "hs_description": row.get("hs_description"),
                "period": customs_payload.get("period"),
                "source": row.get("source"),
                "fallback_used": bool(row.get("fallback_used")),
            }
            for row in customs_rows[:12]
        ]
        export_value_payload = {
            "count": len(customs_rows),
            "items": customs_items,
            **customs_status(customs_payload),
        }

        def _wrap(rows: list[dict[str, Any]], top: int = 20) -> dict[str, Any]:
            return {"count": len(rows), "items": rows[:top]}

        status_payload = data_status()
        status_blocks = {
            "online": status_payload.get("online"),
            "trends": trends_status(trends_payload),
            "platform_rankings": rankings_status(rankings_payload),
            "customs": customs_status(customs_payload),
            "suppliers": status_payload.get("suppliers"),
            "policy": status_payload.get("policy"),
            "as_of_label": status_payload.get("as_of_label"),
        }

        return {
            "rankings": rankings,
            "searchTrends": search_trends,
            "exportValue": export_value_payload,
            "risk": _wrap(risk_overview(filters)),
            "cost": _wrap(cost_metrics(filters)),
            "compare": _wrap(market_compare(filters)),
            "reviews": _wrap(review_summary(filters), 12),
            "competition": _wrap(competition_index(filters), 12),
            "status": status_blocks,
        }

    return _cache_get(key, _build)


def summary(
    filters: dict[str, str | None],
    status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key = f"summary|{_filter_key(filters)}"

    def _build() -> dict[str, Any]:
        history_rows = _apply_filters(history_frame(), filters)
        latest_df = pd.DataFrame(_latest_history_rows())
        latest_rows = _apply_filters(latest_df, filters)
        baseline = [float(m["mape"]) for m in metrics().get("baseline", [])]
        advanced = [float(m["mape"]) for m in metrics().get("advanced", [])]
        latest_records = _records(latest_rows)
        baseline_avg = _average(baseline)
        advanced_avg = _average(advanced)
        return {
            **(status if status is not None else data_status()),
            "categories": len(CATEGORIES),
            "markets": len(MARKETS),
            "history_rows": len(history_rows),
            "forecast_rows": len(_apply_filters(forecast_frame(), filters)),
            "recommendation_rows": len(recommendations_frame()),
            "latest_date": max((str(r["date"]) for r in latest_records), default=None),
            "latest_avg_sales": _average([float(r["sales_volume"]) for r in latest_records]),
            "baseline_avg_mape": baseline_avg,
            "advanced_avg_mape": advanced_avg,
            "mape_improvement_pct": _pct_change(advanced_avg, baseline_avg) * -1,
        }

    return _cache_get(key, _build)


def _trade_report_summary() -> dict[str, Any]:
    """看板内嵌的贸易演示报告只下发摘要；完整明细走 GET /api/trade/report。"""
    return _cache_get("trade_report_summary", _trade_report_summary_impl)


def _trade_report_summary_impl() -> dict[str, Any]:
    try:
        raw = json.loads(TRADE_REPORT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"available": False, "detail": "output/trade/trade_demo_metrics.json 缺失"}
    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    return {
        "available": True,
        "generated_at": raw.get("generated_at"),
        "summary": summary,
        "detail": f"完整 {len(CATEGORIES) * len(MARKETS)} 组合贸易演示明细见 GET /api/trade/report",
    }


def _aggregate_history(df: pd.DataFrame) -> pd.DataFrame:
    """跨组合按日期均值聚合历史序列（保留全部数值列，图表字段语义无损）。"""
    if df.empty:
        return df
    numeric = list(df.select_dtypes(include="number").columns)
    agg = df.groupby("date", as_index=False)[numeric].mean()
    agg = agg.sort_values("date").reset_index(drop=True)
    # 聚合行不再区分组合：补空组合字段，满足前端 HistoryRow 类型（category/market 为 string）。
    agg["category"] = ""
    agg["market"] = ""
    return agg


def _aggregate_forecast(df: pd.DataFrame) -> pd.DataFrame:
    """跨组合按 (date, model) 均值聚合预测序列。"""
    if df.empty:
        return df
    numeric = [c for c in ("yhat", "yhat_lower", "yhat_upper") if c in df.columns]
    agg = df.groupby(["date", "model"], as_index=False)[numeric].mean()
    agg = agg.sort_values(["date", "model"]).reset_index(drop=True)
    agg["category"] = ""
    agg["market"] = ""
    return agg


def _limit_tail(df: pd.DataFrame, limit: str | None, multiplier: int = 1) -> pd.DataFrame:
    """取最近 limit 期（tail 语义，图表序列专用；独立端点 /api/history 的 limit 仍为 head 语义）。"""
    try:
        n = int(limit) if limit else 0
    except (TypeError, ValueError):
        n = 0
    if n <= 0 or df.empty:
        return df
    return df.tail(n * multiplier)


def _without_limit(filters: dict[str, str | None]) -> dict[str, str | None]:
    """剔除 limit 键：limit 只作用于图表序列截断，不泄漏到筛选与统计（summary/recommendations）。"""
    return {k: v for k, v in filters.items() if k != "limit"}


def _dashboard_history_series(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    """看板 history 图表序列：category+market 双筛选返回真实序列，否则按日期跨组合均值聚合。

    聚合目标是消除全量行下发（原 10 万+ 行）：图表（TrendChart/ForecastChart）只消费
    date/sales_volume/search_index/export_value 构成的序列，跨组合均值语义可读且体积降 99%+。
    limit 为最近 N 期（tail 语义）。
    """
    df = _apply_filters(history_frame(), _without_limit(filters))
    if not (filters.get("category") and filters.get("market")):
        df = _aggregate_history(df)
    else:
        df = df.sort_values("date").reset_index(drop=True)
    return _records(_limit_tail(df, filters.get("limit")))


def _dashboard_forecast_series(filters: dict[str, str | None]) -> list[dict[str, Any]]:
    """看板 forecast 图表序列：双筛选返回真实序列，否则按 (date, model) 均值聚合。

    model 筛选恒生效；聚合后行数 = 模型数 × 预测天数（原全量 17 万+ 行）。limit 为最近 N 期（tail 语义）。
    """
    df = _apply_filters(forecast_frame(), _without_limit(filters))
    if not (filters.get("category") and filters.get("market")):
        df = _aggregate_forecast(df)
    else:
        df = df.sort_values(["date", "model"]).reset_index(drop=True)
    model_count = 1
    if not df.empty and "model" in df.columns:
        model_count = max(1, int(df["model"].nunique()))
    return _records(_limit_tail(df, filters.get("limit"), model_count))


def dashboard_data(filters: dict[str, str | None]) -> dict[str, Any]:
    category = filters.get("category")
    market = filters.get("market")
    model = filters.get("model")
    if filters.get("meta") == "1":
        # 轻量元数据模式：供 /api/check 自检使用，避免拉取 55MB 全量数据。
        return _dashboard_data_meta()
    key = f"dashboard|{_filter_key(filters)}"

    def _build() -> dict[str, Any]:
        # limit 只作用于图表序列（history/forecast），不泄漏到 summary/recommendations。
        meta_filters = _without_limit(filters)
        recommendation_filters = {"top": "20"}
        data_status_payload = data_status()
        return {
            "data_status": data_status_payload,
            "fx_rate": DEFAULT_FX_RATE,
            "categories": CATEGORIES,
            "markets": MARKETS,
            "models": MODELS,
            "history": _dashboard_history_series(filters),
            "forecast": _dashboard_forecast_series(filters),
            "recommendations": recommendations(recommendation_filters),
            "metrics": metrics(),
            "summary": summary(meta_filters, status=data_status_payload),
            "trade_report": _trade_report_summary(),
            "policy_events": policy_events(),
        }

    return _cache_get(key, _build)


def _dashboard_data_meta() -> dict[str, Any]:
    """看板数据轻量元信息（不加载 55MB 全量文件，供自检/监控使用）。"""
    path = PROJECT_OUTPUT_DIR / "dashboard-data.json"
    if not path.exists():
        return {
            "ok": False,
            "path": str(path),
            "detail": "output/dashboard-data.json 缺失",
        }
    stat = path.stat()
    size_mb = round(stat.st_size / 1024 / 1024, 1)
    data_as_of: str | None = None
    decision_ready: bool | None = None
    try:
        raw = json.loads(DATA_STATUS_JSON.read_text(encoding="utf-8"))
        data_as_of = raw.get("data_as_of")
        decision_ready = raw.get("decision_data_ready")
    except (OSError, json.JSONDecodeError):
        pass
    updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(
        timespec="seconds"
    )
    return {
        "ok": True,
        "path": str(path),
        "size_bytes": stat.st_size,
        "size_mb": size_mb,
        "updated_at": updated_at,
        "data_as_of": data_as_of,
        "decision_data_ready": decision_ready,
        "detail": f"dashboard-data.json {size_mb}MB",
    }


def crawler_signals(filters: dict[str, str | None]) -> dict[str, Any]:
    """Return the latest crawler snapshot, optionally filtered."""
    snapshot = load_latest_snapshot()
    combos = filter_snapshot(
        snapshot,
        category=filters.get("category"),
        market=filters.get("market"),
        keyword=filters.get("keyword"),
    )
    return {
        "status": snapshot_status(snapshot),
        "count": len(combos),
        "combos": combos,
    }


def crawler_signal_live(payload: dict[str, Any]) -> dict[str, Any]:
    """Run one on-demand crawl and return the normalized evidence signal."""
    keyword = str(payload.get("keyword") or "").strip()
    if not keyword:
        raise ValueError("keyword is required")
    market = str(payload.get("market") or "us").strip().lower()
    category = str(payload.get("category") or "").strip()
    try:
        max_results = int(payload.get("max_results") or 5)
    except (TypeError, ValueError):
        max_results = 5
    max_results = max(1, min(max_results, 20))
    offline = bool(payload.get("offline"))
    return collect_signal(
        keyword,
        market=market,
        category=category,
        max_results=max_results,
        offline=offline,
    )


def _mock_search_results(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """后端不可达时的本地 mock 结果，保证接口始终可用。"""
    fallback_link = "https://duckduckgo.com/?q=" + urllib.parse.quote(query)
    return [
        {
            "title": f"模拟搜索结果：{query}",
            "snippet": "后端搜索服务不可用或联网失败，已自动回退模拟结果；请启动完整 Demo 后端后使用真实联网搜索。",
            "link": fallback_link,
        }
    ][: max(1, max_results)]


def web_search(
    query: str,
    max_results: int = 5,
    provider: str | None = None,
    api_key: str | None = None,
    api_url: str | None = None,
) -> dict[str, Any]:
    """统一联网搜索入口：真实搜索失败时回退 mock，返回 provider 与 fallback 标记。"""
    try:
        from src.api import brain_bridge

        if not brain_bridge.available():
            raise RuntimeError("search engine unavailable")
        return brain_bridge.search(
            query,
            max_results=max_results,
            provider=provider,
            api_key=api_key,
            api_url=api_url,
        )
    except Exception as exc:  # noqa: BLE001 - 任何失败都回退 mock
        return {
            "provider": provider or os.environ.get("SEARCH_PROVIDER", "duckduckgo_html"),
            "fallback_used": True,
            "results": _mock_search_results(query, max_results),
            "error": str(exc),
        }


def online_test(
    query: str = "smart pet feeder",
    max_results: int = 3,
    provider: str | None = None,
    allow_fallback: bool = False,
    search_fn: Any = None,
) -> dict[str, Any]:
    """执行一次真实联网自检，返回结构化报告。

    ``search_fn`` 用于注入假搜索实现，默认走 ``web_search`` 的真实联网路径。
    """
    import time

    started = time.time()
    search_fn = search_fn or web_search
    try:
        result = search_fn(query, max_results=max_results, provider=provider)
    except Exception as exc:  # noqa: BLE001
        result = {
            "provider": provider or os.environ.get("SEARCH_PROVIDER", "duckduckgo_html"),
            "fallback_used": True,
            "results": [],
            "error": str(exc),
        }
    latency_ms = round((time.time() - started) * 1000, 1)
    results = result.get("results") or []
    linked = [item for item in results if str(item.get("link") or "").startswith("http")]
    fallback = bool(result.get("fallback_used")) or result.get("provider") == "mock"
    ok = bool(linked) and not fallback
    report: dict[str, Any] = {
        "ok": ok,
        "provider": provider or result.get("provider") or "duckduckgo_html",
        "query": query,
        "latency_ms": latency_ms,
        "fallback_used": fallback,
        "results_count": len(results),
        "linked_count": len(linked),
        "first_links": [item.get("link") for item in linked[:3]],
        "error": result.get("error"),
    }
    if allow_fallback and not ok:
        report["ok"] = True
    return report


TRADE_PLATFORM_CATALOG = {
    "amazon": {"label": "Amazon"},
    "tiktok": {"label": "TikTok Shop"},
    "shopee": {"label": "Shopee"},
    "aliexpress": {"label": "AliExpress"},
    "temu": {"label": "Temu"},
    "lazada": {"label": "Lazada"},
    "walmart": {"label": "Walmart Marketplace"},
    "etsy": {"label": "Etsy"},
    "ebay": {"label": "eBay"},
    "shopify": {"label": "Shopify 独立站"},
}


def trade_catalog() -> dict[str, Any]:
    """Canonical trade-decision catalog served by the unified backend."""
    return catalog_payload()


def trade_autofill(payload: dict[str, Any]) -> dict[str, Any]:
    """Server-side autofill for trade-decision scenarios."""
    return trade_autofill_build(payload)


def _trade_research(payload: dict[str, Any]) -> dict[str, Any] | None:
    from src.api import brain_bridge

    if not payload.get("research"):
        return None
    scenario = payload.get("scenario") or {}
    profile = scenario.get("profile") or payload.get("profile") or {}
    catalog = payload.get("catalog") or {}
    category = str(
        (catalog.get("category") or {}).get("label")
        or (scenario.get("input") or {}).get("customCategory")
        or (scenario.get("input") or {}).get("category")
        or "跨境电商品类"
    ).strip()
    market = str(
        (catalog.get("market") or {}).get("label")
        or (scenario.get("input") or {}).get("market")
        or "目标市场"
    ).strip()
    keyword = str(
        (scenario.get("input") or {}).get("productKeyword")
        or profile.get("productKeyword")
        or category
        or "跨境电商选品"
    ).strip()
    config = brain_bridge._search_config(payload)
    queries = [
        f"{keyword} {category} {market} market trend 2026 sales competition",
        f"{keyword} {category} {market} tariff regulation compliance 2026",
        f"{keyword} customer reviews complaints opportunities",
        f"{keyword} {market} cross border e commerce selection trend",
    ]

    def _one(index_query: tuple[int, str]) -> tuple[int, dict[str, Any]]:
        index, query = index_query
        try:
            item = brain_bridge.search(
                query,
                max_results=config["max_results"],
                provider=config["provider"],
                api_key=config["api_key"],
                api_url=config["api_url"],
            )
        except Exception as exc:  # noqa: BLE001
            item = {
                "provider": config["provider"],
                "fallback_used": True,
                "results": [
                    {
                        "title": "模拟搜索结果",
                        "snippet": f"联网失败：{exc}",
                        "link": "",
                    }
                ],
            }
        return index, item

    with ThreadPoolExecutor(max_workers=4) as pool:
        ordered = list(pool.map(_one, enumerate(queries, start=1)))
    sources: list[dict[str, Any]] = []
    fallback_any = False
    for index, item in ordered:
        query = queries[index - 1]
        fallback_any = fallback_any or bool(item["fallback_used"])
        for result in item["results"]:
            sources.append({**result, "query": query})
    return {
        "sources": sources,
        "summary": (
            f"完成 {len(queries)} 组联网检索，共 {len(sources)} 条来源"
            f"（含有效链接 {len([s for s in sources if s.get('link')])} 条）。"
        ),
        "provider": config["provider"],
        "fallback_used": fallback_any,
    }


def trade_ai_analyze(payload: dict[str, Any]) -> dict[str, Any]:
    """Server-side trade AI analysis used by the embedded trade demo."""
    from src.api import ai_config, brain_bridge

    ai = payload.get("ai") or {}
    merged = dict(payload)
    merged["api_key"] = str(
        ai.get("api_key")
        or ai.get("apiKey")
        or ai_config.get_api_key()
        or os.environ.get("OPENAI_API_KEY")
        or ""
    ).strip()
    merged["base_url"] = str(
        ai.get("base_url")
        or ai.get("baseUrl")
        or ai_config.get_base_url()
        or os.environ.get("OPENAI_BASE_URL")
        or ""
    ).strip()
    merged["model"] = str(
        ai.get("model")
        or payload.get("model")
        or ai_config.get_model()
        or os.environ.get("OPENAI_MODEL")
        or ""
    ).strip()
    try:
        merged["timeout"] = float(
            ai.get("timeout")
            or ai_config.get_timeout()
            or os.environ.get("AI_TIMEOUT_SECONDS")
            or 45
        )
    except (TypeError, ValueError):
        merged["timeout"] = float(ai_config.get_timeout() or 45)
    if not merged["base_url"] and merged["api_key"] and merged["model"]:
        merged["base_url"] = "https://api.deepseek.com/v1"
    if not (merged["api_key"] and merged["model"]):
        raise ValueError("AI 未配置：缺少 API Key / 模型")
    if not brain_bridge.available():
        raise ValueError("四脑引擎不可用")

    provider = brain_bridge._provider(merged)
    if not provider.configured:
        raise ValueError("AI 未配置")
    research = _trade_research(payload)
    research_text = ""
    if research:
        research_text = "\n".join(
            f"{index}. {item.get('title') or '未命名来源'}\n"
            f"   {item.get('snippet') or ''}\n   {item.get('link') or ''}"
            for index, item in enumerate((research.get("sources") or [])[:8], start=1)
        )

    scenario = payload.get("scenario") or {}
    catalog = payload.get("catalog") or {}
    context = json.dumps(
        {"scenario": scenario, "catalog": catalog}, ensure_ascii=False
    )[:8000]
    lang = str(payload.get("lang") or "zh").lower()
    if lang == "en":
        system = (
            "You are a senior cross-border trade decision consultant. Based on the scenario data and research, "
            'output English JSON in the format: {"title":"conclusion title","summary":"comprehensive analysis within 200 words",'
            '"confidence":80,"signals":["key judgment"],"actions":["next action"]}. Output only JSON.'
        )
        user = (
            f"Scenario data:\n{context}\n\nResearch:\n"
            f"{research_text or '(research not enabled)'}\n\nProvide a trade decision recommendation based on the data and research."
        )
    else:
        system = (
            "你是资深跨境贸易决策顾问。根据给定的方案数据与联网研究资料，"
            "输出中文 JSON，格式为：{\"title\":\"结论标题\",\"summary\":\"200 字以内综合分析\","
            "\"confidence\":80,\"signals\":[\"关键判断\"],\"actions\":[\"下一步动作\"]}。"
            "只输出 JSON，不要输出其他内容。"
        )
        user = (
            f"方案数据：\n{context}\n\n联网研究资料：\n"
            f"{research_text or '（未启用联网研究）'}\n\n请结合数据与研究资料给出贸易决策建议。"
        )
    try:
        parsed = provider.chat_json(system, user)
    except Exception as exc:  # noqa: BLE001 - demo must degrade gracefully
        fallback_title = (
            "AI unavailable; using local rule engine"
            if lang == "en"
            else "AI 暂不可用，已使用本地规则引擎"
        )
        fallback_summary = (
            "AI call or response parsing failed; automatically fell back to local trade decision calculations. Check the model config and retry."
            if lang == "en"
            else "AI 调用或结果解析失败，已自动回退到本地贸易决策计算；检查模型配置后重试即可。"
        )
        fallback_signals = (
            ["Model response could not be parsed or API call failed", "Current result comes from the local rule engine"]
            if lang == "en"
            else ["模型返回内容无法解析或接口调用失败", "当前结果来自本地规则引擎"]
        )
        fallback_actions = (
            ["Check API Key / Base URL / model config", "Click Start Analysis again"]
            if lang == "en"
            else ["检查 API Key / Base URL / 模型配置", "重新点击开始分析"]
        )
        return {
            "data": {
                "title": fallback_title,
                "summary": fallback_summary,
                "confidence": 60,
                "signals": fallback_signals,
                "actions": fallback_actions,
            },
            "ai_used": False,
            "mode": "fallback",
            "reason": str(exc)[:300],
            "research": research,
        }
    return {"data": parsed, "ai_used": True, "mode": "openai", "research": research}


def invalidate_caches() -> None:
    """Drop in-memory data caches after a refresh so the running backend

    serves freshly written artifacts without a process restart.
    """
    global _HISTORY_RECORDS_CACHE, _LATEST_ROWS_CACHE
    history_frame.cache_clear()
    forecast_frame.cache_clear()
    recommendations_frame.cache_clear()
    with _LOCK:
        _CACHE.clear()
    with _RECORDS_CACHE_LOCK:
        _HISTORY_RECORDS_CACHE = None
        _LATEST_ROWS_CACHE = None
    with _DATA_STATUS_CACHE_LOCK:
        _DATA_STATUS_CACHE.clear()
