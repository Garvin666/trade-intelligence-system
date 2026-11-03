"""Unified crawler signal layer shared by every demo system.

Wraps ``src.data.legal_crawler`` (Wikimedia search + pageviews) into a
normalized evidence layer consumed by the main demo, four-brain workbench,
trade decision demo, FastAPI, Streamlit dashboard and data analysis report.
The layer only adds evidence on top of the synthetic market data; it never
changes the frames used for model training.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.config import (
    CATEGORY_KEYWORDS,
    CRAWLER_CACHE_DIR,
    CRAWLER_CACHE_TTL_SECONDS,
    CRAWLER_LATEST_JSON,
    CRAWLER_OUTPUT_DIR,
    category_name,
    market_name,
)
from src.data import legal_crawler
from src.data.base import pageview_trend_pct


def empty_snapshot() -> dict[str, Any]:
    """Return the canonical payload used when no crawler snapshot exists."""
    return {
        "generated_at": None,
        "date": None,
        "offline": False,
        "fallback_used": False,
        "provider": None,
        "combos": [],
        "sources_count": 0,
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def cache_key(
    keyword: str,
    market: str,
    category: str,
    max_results: int,
    offline: bool,
) -> str:
    """Stable cache filename for one on-demand crawl."""
    raw = "|".join(
        [
            str(keyword).strip().lower(),
            str(market).strip().lower(),
            str(category).strip().lower(),
            str(int(max_results)),
            "offline" if offline else "online",
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
    prefix = _slug(str(keyword))[:40] or "keyword"
    return f"{prefix}_{digest}.json"


def cache_path(
    keyword: str,
    market: str,
    category: str,
    max_results: int,
    offline: bool,
) -> Path:
    return CRAWLER_CACHE_DIR / cache_key(keyword, market, category, max_results, offline)


def read_cached_payload(
    keyword: str,
    market: str,
    category: str,
    max_results: int,
    offline: bool,
) -> dict[str, Any] | None:
    """Read a fresh crawler payload from disk cache, or None on miss/stale."""
    path = cache_path(keyword, market, category, max_results, offline)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    meta = payload.get("meta") or {}
    generated = meta.get("generated_at") or payload.get("generated_at")
    if not generated:
        return None
    try:
        timestamp = datetime.fromisoformat(str(generated)).timestamp()
    except ValueError:
        return None
    if time.time() - timestamp > float(CRAWLER_CACHE_TTL_SECONDS):
        return None
    return payload


def write_cached_payload(
    payload: dict[str, Any],
    keyword: str,
    market: str,
    category: str,
    max_results: int,
    offline: bool,
) -> Path:
    CRAWLER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(keyword, market, category, max_results, offline)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def compute_pageview_trend(items: Iterable[dict[str, Any]]) -> float:
    """Percent change between the recent half and earlier half of pageviews."""
    return pageview_trend_pct(items)


def compute_credibility(
    sources: list[dict[str, Any]],
    pageviews: list[dict[str, Any]],
    fallback_used: bool,
) -> tuple[float, str]:
    """按来源数量、浏览数据与回退状态估算证据可信度。"""
    score = 70.0
    if fallback_used:
        score = 30.0
    if not sources:
        score = min(score, 25.0)
    elif len(sources) >= 2:
        score += 10.0
    if len(pageviews) >= 2:
        score += 10.0
    score = round(max(0.0, min(100.0, score)), 1)
    level = "high" if score >= 70 else ("medium" if score >= 50 else "low")
    return score, level


def detect_conflicts(
    sources: list[dict[str, Any]],
    keyword: str,
) -> list[dict[str, str]]:
    """检测来源冲突、关键词污染与来源单一等证据问题。"""
    conflicts: list[dict[str, str]] = []
    if not sources:
        conflicts.append(
            {
                "type": "no_source",
                "severity": "high",
                "note": "未检索到有效来源，证据不可依赖。",
            }
        )
        return conflicts
    if len(sources) < 2:
        conflicts.append(
            {
                "type": "single_source",
                "severity": "medium",
                "note": "仅有一个来源，存在结论偏差风险。",
            }
        )
    tokens = [token for token in re.split(r"\W+", str(keyword).lower()) if len(token) > 2]
    if tokens:
        matched = 0
        for source in sources:
            text = f"{source.get('title') or ''} {source.get('snippet') or ''}".lower()
            if any(token in text for token in tokens):
                matched += 1
        if matched / max(len(sources), 1) < 0.3:
            conflicts.append(
                {
                    "type": "keyword_pollution",
                    "severity": "medium",
                    "note": "多数来源未命中关键词，可能存在检索污染。",
                }
            )
    promoted = [
        source
        for source in sources
        if any(
            marker in f"{source.get('title') or ''} {source.get('snippet') or ''}".lower()
            for marker in ("sponsored", "ad", "广告", "推广")
        )
    ]
    if promoted:
        conflicts.append(
            {
                "type": "promoted_content",
                "severity": "low",
                "note": f"{len(promoted)} 条来源疑似推广内容，权重已降低。",
            }
        )
    return conflicts


def normalize_signal(
    payload: dict[str, Any],
    keyword: str,
    market: str,
    category: str,
) -> dict[str, Any]:
    """Convert one legal_crawler payload into the shared evidence schema."""
    meta = payload.get("meta") or {}
    queries = payload.get("queries") or []
    sources = [
        {**result, "query": entry.get("query", "")}
        for entry in queries
        for result in (entry.get("results") or [])
    ]
    pageviews = payload.get("pageviews") or {}
    items = pageviews.get("items") or []
    top_sources = [
        {key: source.get(key) for key in ("title", "snippet", "link", "source")}
        for source in sources[:5]
    ]
    fallback_used = bool(payload.get("fallback_used"))
    credibility, credibility_level = compute_credibility(sources, items, fallback_used)
    conflicts = detect_conflicts(sources, keyword)
    provider = "mock" if fallback_used else (
        queries[0].get("provider") if queries else "wikimedia_search"
    )
    generated_at = meta.get("generated_at") or payload.get("generated_at")
    # A-1 统一证据账本：每条信号附带同源 provenance 字段（看板 / API / 报告共用）
    from src.analysis.evidence import normalize_provenance

    provenance = normalize_provenance(
        {
            "key": f"{category}_{market}",
            "title": f"{category_name(category)} × {market_name(market)} 联网信号",
            "source": provider,
            "fetched_at": generated_at,
            "formula": "pageview_trend_pct = (近期 PV - 基线 PV) / 基线 PV × 100",
            "model_version": "crawler_signals_v1",
            "review_status": "未复核",
            "status": "已检索" if not fallback_used else "模拟",
            "url": None,
        }
    )
    return {
        "key": f"{category}_{market}",
        "category": category,
        "category_name": category_name(category),
        "market": market,
        "market_name": market_name(market),
        "keyword": keyword,
        "generated_at": generated_at,
        "offline": fallback_used or bool(meta.get("offline")),
        "fallback_used": fallback_used,
        "provider": provider,
        "source_count": len(sources),
        "sources": sources,
        "top_sources": top_sources,
        "pageviews": items,
        "pageview_trend_pct": compute_pageview_trend(items),
        "pageview_article": pageviews.get("article"),
        "credibility": credibility,
        "credibility_level": credibility_level,
        "conflicts": conflicts,
        "errors": payload.get("errors") or [],
        "robots": payload.get("robots") or [],
        "saved_to": payload.get("saved_to"),
        "provenance": provenance,
    }


def collect_signal(
    keyword: str,
    market: str = "us",
    category: str = "",
    *,
    max_results: int = 5,
    offline: bool = False,
    delay: float | None = None,
    timeout: float | None = None,
    use_cache: bool = True,
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    """Crawl one product/market and return the normalized evidence signal."""
    keyword = str(keyword or "").strip()
    if not keyword:
        raise ValueError("keyword is required")
    market = str(market or "us").strip().lower()
    category = str(category or "").strip()
    max_results = max(1, min(int(max_results or 5), 20))

    if use_cache and not offline:
        cached = read_cached_payload(keyword, market, category, max_results, offline)
        if cached is not None:
            return normalize_signal(cached, keyword, market, category)

    payload = legal_crawler.collect_product_signals(
        keyword,
        market=market,
        category=category,
        max_results=max_results,
        delay=delay if delay is not None else legal_crawler.DEFAULT_DELAY_SECONDS,
        timeout=timeout if timeout is not None else legal_crawler.DEFAULT_TIMEOUT_SECONDS,
        offline=offline,
        out_path=out_path,
    )
    if use_cache and not offline:
        write_cached_payload(payload, keyword, market, category, max_results, offline)
    return normalize_signal(payload, keyword, market, category)


def build_daily_combos(
    recommendations: pd.DataFrame,
    count: int = 10,
) -> list[dict[str, str]]:
    """Pick the top-ranked recommendation combos for the daily crawler batch."""
    if recommendations is None or recommendations.empty:
        return []
    df = recommendations.copy()
    if "rank" in df.columns:
        df = df.sort_values("rank", ascending=True)
    limit = max(1, min(int(count or 10), len(CATEGORY_KEYWORDS)))
    combos: list[dict[str, str]] = []
    for _, row in df.head(limit).iterrows():
        category = str(row.get("category") or "").strip()
        market = str(row.get("market") or "us").strip().lower()
        keyword = CATEGORY_KEYWORDS.get(category, category or "cross border e commerce")
        combos.append({"keyword": keyword, "market": market, "category": category})
    return combos


def build_snapshot(
    combos: Iterable[dict[str, str]],
    *,
    offline: bool = False,
    max_results: int = 3,
    out_path: str | Path | None = None,
    workers: int = 4,
) -> dict[str, Any]:
    """Crawl a batch of combos and write the unified latest snapshot.

    ``workers`` controls concurrent per-combo crawling; order of results is
    preserved. The per-host rate limit in the HTTP layer still applies.
    """
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    combo_list = list(combos)

    def _one(combo: dict[str, str]) -> dict[str, Any]:
        return collect_signal(
            combo.get("keyword") or "",
            market=combo.get("market") or "us",
            category=combo.get("category") or "",
            max_results=max_results,
            offline=offline,
            use_cache=not offline,
        )

    if workers > 1 and len(combo_list) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            signals = list(pool.map(_one, combo_list))
    else:
        signals = [_one(combo) for combo in combo_list]

    fallback_any = any(bool(signal.get("fallback_used")) for signal in signals)
    real_any = any(not bool(signal.get("fallback_used")) for signal in signals)
    provider = "wikimedia_search" if real_any else "mock"
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "date": datetime.now().astimezone().date().isoformat(),
        "offline": bool(offline),
        "fallback_used": fallback_any,
        "provider": provider,
        "combos": signals,
        "sources_count": sum(int(signal.get("source_count") or 0) for signal in signals),
        "real_combos": sum(not bool(signal.get("fallback_used")) for signal in signals),
        "mock_combos": sum(bool(signal.get("fallback_used")) for signal in signals),
    }
    if out_path is not None:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        payload["saved_to"] = str(path)
    return payload


def save_latest_snapshot(payload: dict[str, Any]) -> Path:
    CRAWLER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CRAWLER_LATEST_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return CRAWLER_LATEST_JSON


def load_latest_snapshot() -> dict[str, Any]:
    """Read the latest aggregate snapshot, falling back to an empty payload."""
    if not CRAWLER_LATEST_JSON.exists():
        return empty_snapshot()
    try:
        payload = json.loads(CRAWLER_LATEST_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_snapshot()
    payload.setdefault("combos", [])
    payload.setdefault("sources_count", 0)
    payload.setdefault("fallback_used", False)
    return payload


def filter_snapshot(
    snapshot: dict[str, Any],
    *,
    category: str | None = None,
    market: str | None = None,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    """Filter the snapshot combos by category, market or keyword fragment."""
    combos = snapshot.get("combos") or []
    category = str(category or "").strip().lower()
    market = str(market or "").strip().lower()
    keyword = str(keyword or "").strip().lower()
    result = []
    for combo in combos:
        if category and str(combo.get("category") or "").lower() != category:
            continue
        if market and str(combo.get("market") or "").lower() != market:
            continue
        if keyword and keyword not in str(combo.get("keyword") or "").lower():
            continue
        result.append(combo)
    return result


def snapshot_status(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compact crawler status embedded in data_status and dashboard payloads."""
    combos = snapshot.get("combos") or []
    generated = snapshot.get("generated_at")
    real_combos = snapshot.get("real_combos")
    mock_combos = snapshot.get("mock_combos")
    if real_combos is None or mock_combos is None:
        real_combos = sum(not bool(item.get("fallback_used")) for item in combos if isinstance(item, dict))
        mock_combos = sum(bool(item.get("fallback_used")) for item in combos if isinstance(item, dict))
    return {
        "enabled": bool(generated),
        "status": "ready" if generated else "not_generated",
        "updated_at": generated,
        "date": snapshot.get("date"),
        "combos": len(combos),
        "real_combos": int(real_combos or 0),
        "mock_combos": int(mock_combos or 0),
        "fallback_used": bool(snapshot.get("fallback_used")),
        "offline": bool(snapshot.get("offline")),
        "provider": snapshot.get("provider"),
        "sources_count": int(snapshot.get("sources_count") or 0),
        "snapshot": "output/crawler/latest.json",
    }


__all__ = [
    "build_daily_combos",
    "build_snapshot",
    "compute_credibility",
    "collect_signal",
    "detect_conflicts",
    "empty_snapshot",
    "filter_snapshot",
    "load_latest_snapshot",
    "normalize_signal",
    "save_latest_snapshot",
    "snapshot_status",
]
