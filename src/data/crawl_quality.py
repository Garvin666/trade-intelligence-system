"""Crawl quality gates and decision-chain readiness for the merged backend.

Decision-critical endpoints must consume real-time crawls or verified real
cache snapshots. Mock/offline rows are allowed only in pure presentation
views and must never silently feed recommendations, arbitration, or trade
decisions.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import (
    CRAWLER_CACHE_DIR,
    CRAWLER_LATEST_JSON,
    CUSTOMS_LATEST_JSON,
    DATA_STATUS_JSON,
    GITHUB_REAL_RESULTS_CSV,
    HARMONIZED_SYSTEM_CSV,
    OUTPUT_DIR,
    PLATFORM_RANKINGS_LATEST_JSON,
    POLICY_LATEST_JSON,
    SUPPLIER_LATEST_JSON,
    TRENDS_LATEST_JSON,
)

CRAWL_QUALITY_DIR = OUTPUT_DIR / "crawl_quality"
COVERAGE_JSON = CRAWL_QUALITY_DIR / "coverage.json"

REQUIRED_DECISION_SOURCES = ("crawler", "policy", "customs")
EVIDENCE_OPTIONAL_SOURCES = ("trends", "platform_rankings", "github_real")
DECISION_MAX_AGE_HOURS = float(os.environ.get("DECISION_DATA_MAX_AGE_HOURS", "72"))
VERIFIED_STATIC_CACHE = {"customs": HARMONIZED_SYSTEM_CSV}
CRAWLER_MIN_REAL_COMBO_SOURCES = 2

SOURCE_FILES = {
    "crawler": CRAWLER_LATEST_JSON,
    "trends": TRENDS_LATEST_JSON,
    "platform_rankings": PLATFORM_RANKINGS_LATEST_JSON,
    "customs": CUSTOMS_LATEST_JSON,
    "policy": POLICY_LATEST_JSON,
    "suppliers": SUPPLIER_LATEST_JSON,
}


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fresh(value: Any) -> bool:
    parsed = _parse_time(value)
    if parsed is None:
        return False
    age_hours = (datetime.now(timezone.utc) - parsed).total_seconds() / 3600
    return age_hours <= DECISION_MAX_AGE_HOURS


def _cache_fresh(value: Any) -> bool:
    return _fresh(value)


def _count_value(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, (list, dict)):
        return len(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _source_records(name: str, status: dict[str, Any]) -> list[dict[str, Any]]:
    if name == "github_real":
        if not GITHUB_REAL_RESULTS_CSV.exists():
            return []
        try:
            import csv

            with GITHUB_REAL_RESULTS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
                return list(csv.DictReader(f))
        except (OSError, csv.Error):
            return []
    if name == "crawler":
        return _crawler_source_records(status)
    path = SOURCE_FILES.get(name)
    if path is None or not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    for key in ("items", "rows", "results", "events", "series", "records", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _crawler_latest_payload() -> dict[str, Any]:
    path = SOURCE_FILES.get("crawler")
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _crawler_combos() -> list[dict[str, Any]]:
    return [item for item in (_crawler_latest_payload().get("combos") or []) if isinstance(item, dict)]


def _crawler_cache_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not CRAWLER_CACHE_DIR.exists():
        return records
    for path in sorted(CRAWLER_CACHE_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        meta = payload.get("meta") or {}
        generated = meta.get("generated_at") or payload.get("generated_at")
        if not generated or not _cache_fresh(generated):
            continue
        if bool(meta.get("offline")) or bool(payload.get("offline")):
            continue
        for query in payload.get("queries") or []:
            if not isinstance(query, dict):
                continue
            for source in query.get("results") or []:
                if not isinstance(source, dict):
                    continue
                provider = str(source.get("source") or source.get("provider") or "").strip()
                if provider.lower() == "mock":
                    continue
                record = {
                    **source,
                    "_cache": True,
                    "_generated_at": generated,
                    "category": meta.get("category"),
                    "market": meta.get("market"),
                    "date": generated,
                    "provider": provider,
                    "source": provider,
                    "fallback_used": False,
                }
                if not record.get("link") and source.get("url"):
                    record["link"] = source["url"]
                records.append(record)
    return records


def _crawler_source_records(status: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _crawler_latest_payload()
    records: list[dict[str, Any]] = []
    for combo in payload.get("combos") or []:
        if not isinstance(combo, dict):
            continue
        fallback = bool(combo.get("fallback_used"))
        provider = str(combo.get("provider") or "")
        sources = combo.get("sources") or combo.get("results") or []
        if not sources and (combo.get("title") or combo.get("link") or combo.get("source_url")):
            sources = [combo]
        for source in sources:
            if not isinstance(source, dict):
                continue
            provider = str(source.get("source") or source.get("provider") or provider)
            record = {
                **source,
                "category": combo.get("category"),
                "market": combo.get("market"),
                "date": combo.get("generated_at") or payload.get("date"),
                "provider": provider,
                "source": provider,
                "fallback_used": fallback,
            }
            if not record.get("link") and source.get("url"):
                record["link"] = source["url"]
            records.append(record)
    records.extend(_crawler_cache_records())
    return records


def _crawler_stats() -> dict[str, int]:
    combos = _crawler_combos()
    real = 0
    mock = 0
    for combo in combos:
        if bool(combo.get("fallback_used")):
            mock += 1
            continue
        sources = combo.get("sources") or combo.get("results") or []
        real_sources = [
            source
            for source in sources
            if isinstance(source, dict)
            and str(source.get("source") or source.get("provider") or "").lower() != "mock"
            and (source.get("link") or source.get("url") or source.get("title"))
        ]
        if int(combo.get("source_count") or len(real_sources)) >= CRAWLER_MIN_REAL_COMBO_SOURCES and real_sources:
            real += 1
        else:
            mock += 1
    cache_records = sum(1 for record in _crawler_cache_records() if record.get("link"))
    return {
        "real_combos": real,
        "mock_combos": mock,
        "total_combos": len(combos),
        "cache_records": cache_records,
    }


def _file_status(name: str) -> dict[str, Any] | None:
    if name == "customs":
        custom_path = SOURCE_FILES.get("customs")
        if custom_path is not None and custom_path.exists():
            try:
                payload = json.loads(custom_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            provider = str(payload.get("provider") or "").lower()
            rows = payload.get("rows") or []
            real_rows = [
                row
                for row in rows
                if isinstance(row, dict)
                and str(row.get("source") or row.get("provider") or "").lower() != "mock"
            ]
            if (
                provider not in {"", "mock", "harmonized-system"}
                and not payload.get("fallback_used")
                and real_rows
            ):
                return {
                    "provider": provider,
                    "fallback_used": False,
                    "offline": bool(payload.get("offline")),
                    "rows": len(real_rows),
                    "updated_at": payload.get("generated_at"),
                }
        cache_path = VERIFIED_STATIC_CACHE.get("customs")
        if cache_path is not None and cache_path.exists():
            return {
                "provider": "harmonized-system",
                "fallback_used": False,
                "offline": False,
                "rows": sum(1 for _ in cache_path.open("r", encoding="utf-8-sig")) - 1,
                "updated_at": datetime.fromtimestamp(
                    cache_path.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        return None
    if name == "github_real":
        records = _source_records(name, {})
        return {"provider": "github", "fallback_used": False, "rows": len(records)}
    path = SOURCE_FILES.get(name)
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict):
        return {
            "provider": payload.get("provider"),
            "fallback_used": payload.get("fallback_used"),
            "offline": payload.get("offline"),
            "rows": payload.get("rows")
            or payload.get("events")
            or payload.get("combos")
            or payload.get("series_count"),
            "updated_at": payload.get("generated_at"),
        }
    return None


def _precision(name: str, status: dict[str, Any]) -> dict[str, Any]:
    records = _source_records(name, status)
    if not records:
        return {"record_count": 0, "field_completeness": {}, "duplicate_rate": 0.0}
    url_keys = ("source_url", "url", "link", "canonical_url")
    has_url = 0
    seen: set[str] = set()
    duplicates = 0
    for record in records:
        url = next((str(record.get(key) or "").strip() for key in url_keys if record.get(key)), "")
        if url:
            has_url += 1
            if url in seen:
                duplicates += 1
            seen.add(url)
    fields = ["provider", "date", "category", "market"]
    completeness: dict[str, float] = {}
    for field in fields:
        filled = sum(1 for record in records if str(record.get(field) or "").strip())
        completeness[field] = round(filled / len(records), 4)
    return {
        "record_count": len(records),
        "field_completeness": completeness,
        "url_completeness": round(has_url / len(records), 4),
        "duplicate_rate": round(duplicates / max(len(records), 1), 4),
    }


def _mode_for(name: str, status: dict[str, Any]) -> str:
    if name == "crawler":
        stats = _crawler_stats()
        if stats["real_combos"] > 0:
            return "real"
        if stats["cache_records"] > 0:
            return "cache"
    cache_path = VERIFIED_STATIC_CACHE.get(name) if name in VERIFIED_STATIC_CACHE else None
    if cache_path is not None and cache_path.exists():
        file_status = _file_status(name)
        provider = str((file_status or {}).get("provider") or "").lower()
        if (
            file_status is None
            or provider in {"mock", "harmonized-system"}
            or bool(file_status.get("fallback_used"))
        ):
            return "cache"
    file_status = _file_status(name)
    if file_status is not None:
        status = {**status, **{k: v for k, v in file_status.items() if v is not None}}
    provider = str(status.get("provider") or "")
    fallback_used = bool(status.get("fallback_used") or status.get("offline"))
    count = _count_value(
        status.get("rows")
        or status.get("events")
        or status.get("combos")
        or status.get("series_count")
        or 0
    )
    if provider.lower() == "mock":
        return "mock"
    records = _source_records(name, status)
    if records and any(
        str(record.get("source") or record.get("provider") or "").lower() == "mock"
        for record in records[:50]
    ):
        return "mock"
    if fallback_used and not records:
        return "mock"
    if count > 0:
        return "real"
    if records and any(
        str(record.get(key) or "").strip()
        for record in records[:20]
        for key in ("source_url", "url", "link", "canonical_url")
    ):
        return "cache"
    return "missing"


def build_crawl_quality(data_status: dict[str, Any] | None = None) -> dict[str, Any]:
    status = data_status or {}
    if not status and DATA_STATUS_JSON.exists():
        try:
            status = json.loads(DATA_STATUS_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            status = {}

    sources: dict[str, Any] = {}
    for name in (
        "crawler",
        "trends",
        "platform_rankings",
        "customs",
        "policy",
        "suppliers",
        "github_real",
    ):
        source_status = status.get(name) or {}
        mode = _mode_for(name, source_status)
        coverage = source_status.get("coverage") or {}
        if isinstance(coverage, dict):
            real_count = int(coverage.get("real") or 0)
            mock_count = int(coverage.get("mock") or 0)
        else:
            real_count = 0
            mock_count = 0
        if name == "github_real":
            real_count = len(_source_records(name, source_status))
        elif name == "crawler":
            crawler_stats = _crawler_stats()
            real_count = crawler_stats["real_combos"]
            mock_count = crawler_stats["mock_combos"]
        sources[name] = {
            "source": name,
            "mode": mode,
            "provider": str(source_status.get("provider") or ""),
            "fallback_used": bool(source_status.get("fallback_used")),
            "offline": bool(source_status.get("offline")),
            "last_success": source_status.get("updated_at") or status.get("generated_at"),
            "fresh": _fresh(source_status.get("updated_at") or status.get("generated_at")),
            "real_count": real_count,
            "mock_count": mock_count,
            "precision": _precision(name, source_status),
        }

    reasons: list[str] = []
    for name in REQUIRED_DECISION_SOURCES:
        item = sources[name]
        if item["mode"] not in {"real", "cache"}:
            reasons.append(f"{name} 无真实或缓存数据（mode={item['mode']}）")
        elif not item["fresh"]:
            reasons.append(f"{name} 数据已超过 {DECISION_MAX_AGE_HOURS:g} 小时未刷新")

    evidence_ready = any(
        sources[name]["mode"] in {"real", "cache"}
        for name in EVIDENCE_OPTIONAL_SOURCES
    )
    ready = not reasons and evidence_ready
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision_max_age_hours": DECISION_MAX_AGE_HOURS,
        "sources": sources,
        "reasons": reasons,
        "evidence_ready": evidence_ready,
        "decision_data_ready": ready,
    }


def write_coverage(coverage: dict[str, Any]) -> Path:
    CRAWL_QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    COVERAGE_JSON.write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return COVERAGE_JSON


def load_coverage() -> dict[str, Any]:
    if COVERAGE_JSON.exists():
        try:
            return json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return build_crawl_quality()
