"""Daily policy snapshot: official-first policy events plus search candidates.

The snapshot keeps two layers:

- ``events``: verified events from official government sources only. These
  are the only events that enter the trade-decision scoring pipeline.
- ``candidate_events``: search/mock results kept for human review. They are
  never treated as real policy changes.

When an official source is offline, the previous verified snapshot is
retained instead of fabricating mock data.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable

from src.config import (
    MARKETS,
    POLICY_DAILY_DIR,
    POLICY_LATEST_JSON,
    POLICY_WATCH_LOOKBACK_DAYS,
)
from src.data.policy_common import (
    ACTION_MAP as _ACTION_MAP,
    actions_for as _actions_for,
    business_impact_level as _business_impact_level,
    classify as _classify,
    extract_min_duty as _extract_min_duty,
    extract_rate as _extract_rate,
    normalize_date as _normalize_date,
)
from src.data.policy_sources import (
    OFFICIAL_SOURCES,
    SOURCE_LABELS,
    collect_official_policy_events,
)

MAX_EVENTS_PER_DAY = 40
HEURISTIC_IMPACT_RATIO = {"high": 0.10, "medium": 0.05, "low": 0.02}
REGION_CAPS = {"foreign": 20, "domestic": 12, "global": 8}
BING_SEARCH_URL = "https://www.bing.com/search"
GOV_POLICY_URL = "https://www.gov.cn/zhengce/"
BING_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_POLICY_NOISE = (
    "百度百科",
    "维基百科",
    "门户网站",
    "国家概况",
    "概况",
    "电子税务局",
    "服务网",
    "首页",
    "主页",
    "专区",
    "官网",
    "社区",
    "平台",
    "指南",
    "入门",
    "白皮书",
    "是什么",
    "知乎",
    "雨果",
    "跨境知道",
    "1688",
    "亚马逊",
    "汇总表",
)

_STRONG_POLICY_HINTS = (
    "政策",
    "新政",
    "新规",
    "通知",
    "公告",
    "办法",
    "意见",
    "条例",
    "规定",
    "扩围",
    "退税",
    "关税",
    "监管",
    "实施",
    "调整",
    "方案",
    "解读",
    "综试区",
    "数字贸易",
    "规则",
)

GOV_RELEVANT_HINTS = (
    "外贸",
    "出口",
    "进口",
    "关税",
    "跨境",
    "电商",
    "贸易",
    "税收",
    "知识产权",
    "口岸",
    "海关",
    "外汇",
    "数字经济",
    "综合试验区",
    "RCEP",
)

FOREIGN_QUERY_TEMPLATES = (
    "{market} 跨境电商 关税 政策 最新 2026",
    "{market} 低价值包裹 增值税 免税 新规",
)

DOMESTIC_QUERIES = (
    ("中国 跨境电商 政策 最新 2026", "macro"),
    ("商务部 跨境电商 综合试验区 扩容 政策 2026", "macro"),
    ("海关总署 跨境电商 通关 监管 新规 2026", "customs"),
    ("税务总局 跨境电商 出口退税 政策 2026", "rebate"),
    ("出口退税 税率 调整 政策 解读 2026", "rebate"),
    ("跨境电商 综合试验区 扩容 政策 解读 2026", "macro"),
    ("跨境 支付 外汇 结算 新规 政策 2026", "compliance"),
    ("RCEP 关税 原产地 规则 政策 解读 2026", "macro"),
    ("跨境电商 数据安全 个人信息 合规 新规 2026", "compliance"),
    ("跨境电商 政策 通知 公告 2026", "news"),
)

GLOBAL_QUERIES = (
    ("RCEP 关税 政策 解读 2026", "macro"),
    ("WTO 电商 关税 免税 政策 2026", "macro"),
    ("数字贸易 规则 跨境电商 全球 政策 2026", "news"),
)

def policy_queries() -> list[dict[str, str]]:
    """Build the full daily query set for foreign, domestic and global policy."""
    queries: list[dict[str, str]] = []
    for market in MARKETS:
        market_name = MARKETS[market]
        for template in FOREIGN_QUERY_TEMPLATES:
            queries.append(
                {
                    "query": template.format(market=market_name),
                    "market": market,
                    "region": "foreign",
                    "policy_type": "tariff",
                }
            )
    for query, policy_type in DOMESTIC_QUERIES:
        queries.append(
            {
                "query": query,
                "market": "cn",
                "region": "domestic",
                "policy_type": policy_type,
            }
        )
    for query, policy_type in GLOBAL_QUERIES:
        queries.append(
            {
                "query": query,
                "market": "global",
                "region": "global",
                "policy_type": policy_type,
            }
        )
    return queries


def _extract_date(text: str, default: str) -> str:
    match = re.search(r"(20\d{2})[-年](\d{1,2})[-月](\d{1,2})", text)
    if match:
        try:
            return date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            ).isoformat()
        except ValueError:
            pass
    return default


def _extract_rebate_adjustment(text: str) -> float:
    if "退税" not in text:
        return 0.0
    down = re.search(r"(?:下调|降低|减少)\D*?(\d+(?:\.\d+)?)\s*%", text)
    if down:
        return round(float(down.group(1)) / 100.0, 4)
    up = re.search(r"(?:上调|提高|增加|扩大)\D*?(\d+(?:\.\d+)?)\s*%", text)
    if up:
        return -round(float(up.group(1)) / 100.0, 4)
    return 0.0


def _mock_results(query: str, max_results: int = 3) -> list[dict[str, str]]:
    return [
        {
            "title": f"模拟政策检索：{query}",
            "snippet": "离线每日更新：未发起真实联网检索，结果仅用于演示。",
            "link": "",
            "source": "mock",
        }
        for _ in range(max(1, min(int(max_results), 5)))
    ]


def _keep_policy_result(item: dict[str, Any]) -> bool:
    """Keep results that look like actual policy articles instead of portals."""
    text = " ".join(
        str(item.get(key) or "") for key in ("title", "link", "snippet")
    )
    if any(noise in text for noise in _POLICY_NOISE):
        return False
    return any(hint in text for hint in _STRONG_POLICY_HINTS)


class _BingParser(HTMLParser):
    """Extract ``li.b_algo`` items from Bing HTML search results."""

    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._h2_depth = 0
        self._title_buffer: list[str] = []
        self._snippet_buffer: list[str] = []
        self._snippet_on = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        classes = set(attr_map.get("class", "").split())
        if tag == "li" and "b_algo" in classes:
            self._current = {"title": "", "snippet": "", "link": ""}
        elif self._current is not None and tag == "h2":
            self._h2_depth += 1
            self._title_buffer = []
        elif self._current is not None and self._h2_depth and tag == "a":
            href = attr_map.get("href", "")
            if not self._current["link"] and href.startswith("http"):
                self._current["link"] = href
        elif self._current is not None and tag == "p":
            self._snippet_on = bool(
                classes & {"b_lineclamp", "b_paractl"} or "b_lineclamp" in classes
            )
            if self._snippet_on:
                self._snippet_buffer = []
        elif self._current is not None and tag == "span" and "b_algoSlug" in classes:
            self._snippet_on = False

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return
        if self._h2_depth:
            self._title_buffer.append(data)
        if self._snippet_on:
            self._snippet_buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return
        if tag == "h2" and self._h2_depth:
            self._h2_depth -= 1
            if not self._current["title"]:
                self._current["title"] = " ".join(
                    "".join(self._title_buffer).split()
                ).strip()
            self._title_buffer = []
        if tag == "p" and self._snippet_on:
            self._current["snippet"] = " ".join(
                "".join(self._snippet_buffer).split()
            ).strip()
            self._snippet_on = False
        if tag == "li" and self._current:
            if self._current["title"] or self._current["link"]:
                self.items.append(self._current)
            self._current = None
            self._h2_depth = 0
            self._snippet_on = False


def bing_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Fetch Bing HTML results for Chinese queries with a browser-like UA."""
    url = BING_SEARCH_URL + "?" + urllib.parse.urlencode(
        {
            "q": query,
            "setlang": "zh-hans",
            "mkt": "zh-CN",
            "cc": "CN",
            "count": str(max(1, min(int(max_results), 10))),
        }
    )
    request = urllib.request.Request(url, headers={"User-Agent": BING_USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read().decode("utf-8", errors="replace")
    parser = _BingParser()
    parser.feed(raw)
    return parser.items[: max(1, min(int(max_results), 10))]


def parse_policy_event(
    result: dict[str, Any],
    *,
    market: str,
    region: str,
    policy_type: str,
    policy_date: str,
    fallback_used: bool,
) -> dict[str, Any]:
    """Normalize one search hit into an unverified candidate event."""
    title = str(result.get("title") or "").strip()
    snippet = str(result.get("snippet") or "").strip()
    link = str(result.get("link") or "").strip()
    source = str(result.get("source") or "").strip() or title or "公开来源"
    text = f"{title} {snippet}"
    effective_date = _extract_date(text, policy_date)
    rate = _extract_rate(text)
    min_duty = _extract_min_duty(text)
    cost_adjustment = (
        _extract_rebate_adjustment(text)
        if policy_type == "rebate"
        else 0.0
    )
    impact_level, direction = _classify(text)
    impact_level = _business_impact_level(
        policy_type,
        rate,
        min_duty,
        cost_adjustment,
        (),
        text,
    )
    heuristic = not (
        rate > 0 or min_duty > 0 or abs(cost_adjustment) > 1e-9
    )
    code_seed = f"{market}|{title}|{effective_date}".encode("utf-8")
    code = "pol-" + hashlib.sha1(code_seed).hexdigest()[:12]
    return {
        "code": code,
        "title": title or f"{region} 政策动态",
        "market": market,
        "region": region,
        "policy_type": policy_type,
        "effective_date": effective_date,
        "published_at": effective_date,
        "rate_ad_valorem": rate,
        "min_duty_usd": min_duty,
        "cost_adjustment_pct": cost_adjustment,
        "impact_level": impact_level,
        "direction": direction,
        "description": snippet or title or "",
        "source": source,
        "url": link,
        "actions": _actions_for(policy_type, impact_level),
        "categories": [],
        "heuristic": heuristic,
        "fallback_used": fallback_used,
        "verified": False,
        "official": False,
        "source_type": "search",
    }


def _is_verified_event(event: dict[str, Any]) -> bool:
    if not bool(event.get("verified")):
        return False
    if bool(event.get("fallback_used")):
        return False
    if "模拟" in str(event.get("title") or ""):
        return False
    return True


def _load_previous_verified(latest_path: Path) -> list[dict[str, Any]]:
    if not latest_path.exists():
        return []
    try:
        payload = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    retained: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        if not _is_verified_event(event):
            continue
        title = str(event.get("title") or "")
        provider = str(event.get("provider") or "")
        if provider == "gov_cn" and not any(
            hint in title for hint in GOV_RELEVANT_HINTS
        ):
            continue
        retained.append(event)
    return retained


def _cap_regions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    capped: list[dict[str, Any]] = []
    for event in events:
        region = str(event.get("region") or "foreign")
        if counts.get(region, 0) >= REGION_CAPS.get(region, 10):
            continue
        counts[region] = counts.get(region, 0) + 1
        capped.append(event)
        if len(capped) >= MAX_EVENTS_PER_DAY:
            break
    return capped


def _interleave_by_provider(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Round-robin official sources so region caps do not starve one provider."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        provider = str(event.get("provider") or "other")
        buckets.setdefault(provider, []).append(event)
    result: list[dict[str, Any]] = []
    remaining = True
    while remaining:
        remaining = False
        for provider in buckets:
            if buckets[provider]:
                result.append(buckets[provider].pop(0))
                remaining = True
    return result


def _collect_candidates(
    search_func: Callable[..., dict[str, Any]] | None,
    *,
    offline: bool,
    provider: str,
    policy_date: str,
    max_results: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    if search_func is None and not offline:
        def _default_search(query: str, max_results: int, provider: str) -> dict[str, Any]:
            try:
                results = [
                    item
                    for item in bing_search(query, max_results)
                    if _keep_policy_result(item)
                ]
                return {
                    "provider": "bing",
                    "fallback_used": False,
                    "results": results,
                }
            except Exception:  # noqa: BLE001
                return {
                    "provider": "mock",
                    "fallback_used": True,
                    "results": _mock_results(query, max_results),
                }

        search_func = _default_search

    query_entries: list[dict[str, Any]] = []
    region_events: dict[str, list[dict[str, Any]]] = {
        "foreign": [],
        "domestic": [],
        "global": [],
    }
    seen: set[tuple[str, str]] = set()
    fallback_any = False

    for item in policy_queries():
        query = item["query"]
        provider_used = provider
        fallback = False
        try:
            if offline:
                results = _mock_results(query, max_results)
                provider_used = "mock"
                fallback = True
            else:
                raw = search_func(query, max_results=max_results, provider=provider)
                results = raw.get("results", [])
                provider_used = str(raw.get("provider") or provider)
                fallback = bool(raw.get("fallback_used"))
                if fallback or not results:
                    try:
                        bing_results = [
                            item
                            for item in bing_search(query, max_results)
                            if _keep_policy_result(item)
                        ]
                        if bing_results:
                            results = bing_results
                            provider_used = "bing"
                            fallback = False
                    except Exception:  # noqa: BLE001 - keep the original result
                        pass
        except Exception as exc:  # noqa: BLE001 - one query may fail
            results = [
                {
                    "title": f"政策检索失败：{query}",
                    "snippet": str(exc),
                    "link": "",
                    "source": "error",
                }
            ]
            provider_used = "mock"
            fallback = True

        fallback_any = fallback_any or fallback
        query_entries.append(
            {
                "query": query,
                "market": item["market"],
                "region": item["region"],
                "policy_type": item["policy_type"],
                "provider": provider_used,
                "fallback_used": fallback,
                "results": results,
            }
        )
        for result in results:
            event = parse_policy_event(
                result,
                market=item["market"],
                region=item["region"],
                policy_type=item["policy_type"],
                policy_date=policy_date,
                fallback_used=fallback,
            )
            event["provider"] = provider_used
            dedupe_key = (event["title"].casefold(), event["market"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            region_events.setdefault(event["region"], []).append(event)

    candidates: list[dict[str, Any]] = []
    for region in ("foreign", "domestic", "global"):
        candidates.extend(region_events[region][: REGION_CAPS.get(region, 10)])
    return candidates[:MAX_EVENTS_PER_DAY], query_entries, fallback_any


def refresh_policy_snapshot(
    search_func: Callable[..., dict[str, Any]] | None = None,
    *,
    offline: bool = False,
    provider: str = "crawler",
    policy_date: str | date | datetime | None = None,
    max_results: int = 5,
    out_dir: str | Path | None = None,
    latest_path: str | Path | None = None,
    include_official_sources: bool = True,
    lookback_days: int | None = None,
    official_providers: list[str] | tuple[str, ...] | None = None,
    include_search: bool = True,
) -> dict[str, Any]:
    """Run the daily policy snapshot and write the snapshot files."""
    date_str = _normalize_date(policy_date)
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    out_dir = Path(out_dir) if out_dir is not None else POLICY_DAILY_DIR
    latest_path = Path(latest_path) if latest_path is not None else POLICY_LATEST_JSON
    lookback = int(
        lookback_days
        if lookback_days is not None
        else POLICY_WATCH_LOOKBACK_DAYS
    )

    previous = _load_previous_verified(latest_path)
    if include_official_sources:
        official_payload = collect_official_policy_events(
            offline=offline,
            lookback_days=lookback,
            providers=official_providers,
        )
        official_events = list(official_payload["events"])
        official_sources = dict(official_payload["sources"])
    else:
        official_payload = {
            "events": [],
            "sources": {},
            "fallback_used": False,
        }
        official_events = []
        official_sources = {}

    seen: set[str] = set()
    events: list[dict[str, Any]] = []
    for event in previous + official_events:
        if not _is_verified_event(event):
            continue
        key = str(event.get("code") or event.get("url") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        events.append(event)
    events = _cap_regions(_interleave_by_provider(events))

    candidate_events: list[dict[str, Any]] = []
    query_entries: list[dict[str, Any]] = []
    candidate_fallback = False
    if include_search:
        candidate_events, query_entries, candidate_fallback = _collect_candidates(
            search_func,
            offline=offline,
            provider=provider,
            policy_date=date_str,
            max_results=max_results,
        )

    fallback_any = (
        bool(official_payload.get("fallback_used"))
        or candidate_fallback
        or offline
    )
    counts = {
        "total": len(events),
        "foreign": sum(1 for e in events if e.get("region") == "foreign"),
        "domestic": sum(1 for e in events if e.get("region") == "domestic"),
        "global": sum(1 for e in events if e.get("region") == "global"),
    }
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "date": date_str,
        "provider": provider,
        "fallback_used": fallback_any,
        "offline": bool(offline),
        "official_only": True,
        "queries": query_entries,
        "events": events,
        "candidate_events": candidate_events,
        "sources": official_sources,
        "sources_count": sum(len(entry["results"]) for entry in query_entries),
        "events_count": len(events),
        "candidate_count": len(candidate_events),
        "verified_count": len(events),
        "counts": counts,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    daily_path = out_dir / f"{date_str}.json"
    daily_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    payload["saved_to"] = str(daily_path)
    payload["latest"] = str(latest_path)
    return payload


def empty_snapshot() -> dict[str, Any]:
    """Return a safe empty payload when no policy snapshot exists yet."""
    return {
        "generated_at": "",
        "date": "",
        "provider": None,
        "fallback_used": False,
        "offline": False,
        "official_only": True,
        "queries": [],
        "events": [],
        "candidate_events": [],
        "sources": {},
        "sources_count": 0,
        "events_count": 0,
        "candidate_count": 0,
        "verified_count": 0,
        "counts": {"total": 0, "foreign": 0, "domestic": 0, "global": 0},
    }


def policy_snapshot_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize a policy snapshot for ``data_status.json``."""
    counts = payload.get("counts") or {}
    events = payload.get("events") or []
    candidates = payload.get("candidate_events") or []
    return {
        "enabled": True,
        "status": "ready" if events or candidates else "pending",
        "updated_at": payload.get("generated_at") or "",
        "date": payload.get("date") or "",
        "provider": payload.get("provider"),
        "fallback_used": bool(payload.get("fallback_used")),
        "official_only": bool(payload.get("official_only", True)),
        "events": len(events),
        "verified_events": len(events),
        "candidate_events": len(candidates),
        "foreign": int(counts.get("foreign") or 0),
        "domestic": int(counts.get("domestic") or 0),
        "global": int(counts.get("global") or 0),
        "sources": payload.get("sources") or {},
        "snapshot": "output/policy/latest.json",
    }


def load_latest_events() -> list[dict[str, Any]]:
    """Read verified events from the latest policy snapshot."""
    if not POLICY_LATEST_JSON.exists():
        return []
    try:
        payload = json.loads(POLICY_LATEST_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return list(payload.get("events", []))


__all__ = [
    "GOV_POLICY_URL",
    "MAX_EVENTS_PER_DAY",
    "bing_search",
    "empty_snapshot",
    "load_latest_events",
    "parse_policy_event",
    "policy_queries",
    "policy_snapshot_status",
    "refresh_policy_snapshot",
]
