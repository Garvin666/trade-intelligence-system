"""Official-source policy adapters for the Policy Radar.

The adapters only touch public official endpoints. Each source returns
normalized raw items, and ``collect_official_policy_events`` flattens them
into verified policy events with an official URL. Nothing is fabricated
when a source is offline.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Any

import requests

from src.data.crawl_engine import LegalCrawlEngine
from src.data.http import BROWSER_USER_AGENT as USER_AGENT
from src.data.policy_common import (
    ACTION_MAP as _ACTION_MAP,
    actions_for as _actions_for,
    business_impact_level as _business_impact_level,
    classify as _classify,
    clean_text as _clean_text,
    extract_min_duty as _extract_min_duty,
    extract_rate as _extract_rate,
    normalize_date as _normalize_date,
)

FEDERAL_REGISTER_API = "https://www.federalregister.gov/api/v1/documents.json"
EC_PRESS_API = "https://ec.europa.eu/commission/presscorner/api/search"
EC_NEWS_PAGE = "https://taxation-customs.ec.europa.eu/news"
GOV_UK_API = "https://www.gov.uk/api/search.json"
GOV_POLICY_URL = "https://www.gov.cn/zhengce/"

OFFICIAL_SOURCES = ("gov_cn", "federal_register", "eu", "uk")

SOURCE_LABELS = {
    "gov_cn": "中国政府网",
    "federal_register": "美国联邦公报",
    "eu": "欧盟委员会",
    "uk": "英国政府",
}

SOURCE_URLS = {
    "gov_cn": GOV_POLICY_URL,
    "federal_register": "https://www.federalregister.gov/documents/search",
    "eu": EC_PRESS_API,
    "uk": "https://www.gov.uk/search/news-and-communications",
}

CN_RELEVANT_HINTS = (
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

EU_RELEVANT_TERMS = (
    "customs",
    "tariff",
    "duty",
    "import",
    "export",
    "vat",
    "e-commerce",
    "de minimis",
    "trade",
)

US_RELEVANT_TERMS = (
    "tariff",
    "de minimis",
    "antidumping",
    "countervailing",
    "section 301",
    "export control",
    "customs",
    "import",
    "trade",
)

US_RELEVANT_AGENCIES = (
    "USTR",
    "Commerce",
    "Homeland Security",
    "Customs and Border Protection",
    "International Trade",
)

UK_RELEVANT_ORGS = (
    "HM Revenue & Customs",
    "HM Revenue and Customs",
    "Department for Business and Trade",
    "Department for Business & Trade",
)

UK_SKIP_TYPES = {"transaction"}

def _gov_link_date(link: str) -> str | None:
    match = re.search(r"/content/(20\d{2})(\d{2})/", link)
    if not match:
        return None
    try:
        return f"{match.group(1)}-{match.group(2)}-01"
    except ValueError:
        return None


def fetch_gov_cn(max_items: int = 12, timeout: int = 25, **kwargs: Any) -> list[dict[str, str]]:
    """Fetch the latest State Council policy list from gov.cn."""
    engine = LegalCrawlEngine(user_agent=USER_AGENT, timeout=timeout, delay=1.0)
    result = engine.fetch(GOV_POLICY_URL)
    if result.get("error"):
        raise RuntimeError(result["error"])
    text = result["html"]

    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{6,120})</a>', text):
        href, label = match.group(1), " ".join(match.group(2).split())
        if not label or "/zhengce/content/" not in href:
            continue
        if label in seen:
            continue
        seen.add(label)
        if href.startswith("./"):
            href = "https://www.gov.cn/zhengce/" + href[2:]
        elif href.startswith("/"):
            href = "https://www.gov.cn" + href
        item = {
            "title": label,
            "link": href,
            "snippet": "中国政府网政策文件",
            "source": "中国政府网",
            "provider": "gov_cn",
            "market": "cn",
            "region": "domestic",
            "policy_type": "macro",
            "published_at": _gov_link_date(href) or date.today().isoformat(),
        }
        if any(hint in label for hint in CN_RELEVANT_HINTS):
            items.append(item)
        if len(items) >= max_items:
            break
    return items[: max(1, min(int(max_items), 12))]


def _us_policy_type(text: str) -> str:
    lowered = text.lower()
    if "de minimis" in lowered or "duty-free" in lowered:
        return "customs"
    if "export control" in lowered or "entity list" in lowered:
        return "compliance"
    if any(
        term in lowered
        for term in ("tariff", "antidumping", "countervailing", "section 301", "duty")
    ):
        return "tariff"
    if any(term in lowered for term in ("import", "customs", "trade")):
        return "customs"
    return "compliance"


def fetch_federal_register(lookback_days: int = 14, timeout: int = 25, **kwargs: Any) -> list[dict[str, Any]]:
    """Fetch recent US trade-related documents from the Federal Register API."""
    since = (date.today() - timedelta(days=max(1, int(lookback_days)))).isoformat()
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for term in ("tariff", "de minimis", "export controls"):
        params = {
            "conditions[term]": term,
            "conditions[publication_date][gte]": since,
            "per_page": 20,
            "order": "newest",
            "fields[]": [
                "title",
                "publication_date",
                "html_url",
                "abstract",
                "agencies",
                "type",
                "document_number",
            ],
        }
        response = requests.get(
            FEDERAL_REGISTER_API,
            params=params,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        for row in response.json().get("results", []):
            title = _clean_text(row.get("title"))
            abstract = _clean_text(row.get("abstract"))
            agencies = " ".join(
                _clean_text(agency.get("name"))
                for agency in (row.get("agencies") or [])
            )
            url = str(row.get("html_url") or "")
            if not title or not url or url in seen:
                continue
            text = f"{title} {abstract} {agencies}".lower()
            if not any(term in text for term in US_RELEVANT_TERMS):
                continue
            if not any(agency in text for agency in US_RELEVANT_AGENCIES) and not any(
                term in title.lower() for term in US_RELEVANT_TERMS
            ):
                continue
            seen.add(url)
            items.append(
                {
                    "title": title,
                    "link": url,
                    "snippet": abstract or title,
                    "source": "Federal Register",
                    "provider": "federal_register",
                    "market": "us",
                    "region": "foreign",
                    "policy_type": _us_policy_type(text),
                    "published_at": _normalize_date(row.get("publication_date")),
                    "doc_type": _clean_text((row.get("type") or {}).get("label") if isinstance(row.get("type"), dict) else row.get("type")),
                }
            )
    return items


def _ec_press_items(timeout: int) -> list[dict[str, Any]]:
    params = {
        "categories": "TAXU",
        "languages": "en",
        "pageSize": 50,
    }
    response = requests.get(
        EC_PRESS_API,
        params=params,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    items: list[dict[str, Any]] = []
    for row in response.json().get("docuLanguageListResources", []):
        title = _clean_text(row.get("title"))
        ref = str(row.get("refCode") or "")
        doc_type = str((row.get("docutype") or {}).get("code") or "")
        if not title or not ref:
            continue
        lowered = title.lower()
        if doc_type == "MEX":
            continue
        url = "https://ec.europa.eu/commission/presscorner/detail/en/" + ref.replace("/", "_").lower()
        items.append(
            {
                "title": title,
                "link": url,
                "snippet": _clean_text(row.get("leadText")) or title,
                "source": "European Commission",
                "provider": "eu",
                "market": "eu",
                "region": "foreign",
                "policy_type": "customs"
                if any(term in lowered for term in ("customs", "duty", "tariff", "de minimis"))
                else "compliance",
                "published_at": _normalize_date(row.get("eventDate")),
                "ref_code": ref,
            }
        )
    return items


def _ec_taxation_news(timeout: int) -> list[dict[str, Any]]:
    engine = LegalCrawlEngine(user_agent=USER_AGENT, timeout=timeout, delay=1.0)
    result = engine.fetch(EC_NEWS_PAGE)
    if result.get("error"):
        raise RuntimeError(result["error"])
    text = result["html"]
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', text, re.S | re.I):
        label = _clean_text(label)
        if not label or len(label) < 8 or not href.startswith("/news/"):
            continue
        if href in seen:
            continue
        seen.add(href)
        url = "https://taxation-customs.ec.europa.eu" + href
        lowered = label.lower()
        items.append(
            {
                "title": label,
                "link": url,
                "snippet": label,
                "source": "European Commission Taxation and Customs",
                "provider": "eu",
                "market": "eu",
                "region": "foreign",
                "policy_type": "customs"
                if any(term in lowered for term in ("customs", "tariff", "duty", "import", "export"))
                else "compliance",
                "published_at": date.today().isoformat(),
            }
        )
    return items


def fetch_eu(lookback_days: int = 14, timeout: int = 25, **kwargs: Any) -> list[dict[str, Any]]:
    """Fetch EU official announcements from Press Corner and taxation-customs."""
    items = _ec_press_items(timeout)
    try:
        items.extend(_ec_taxation_news(timeout))
    except Exception:  # noqa: BLE001 - secondary source is optional
        pass
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        url = str(item.get("link") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(item)
    return unique


def _uk_policy_type(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ("tariff", "duty", "de minimis", "vat")):
        return "tariff" if "vat" not in lowered or "tariff" in lowered else "vat"
    if any(term in lowered for term in ("import", "export", "customs")):
        return "customs"
    return "compliance"


def fetch_uk(lookback_days: int = 14, timeout: int = 25, **kwargs: Any) -> list[dict[str, Any]]:
    """Fetch recent UK policy/news items from the official GOV.UK search API."""
    params = {
        "q": "customs tariff import export de minimis",
        "count": 50,
        "order": "-public_timestamp",
        "fields": [
            "title",
            "link",
            "description",
            "public_timestamp",
            "organisations",
            "content_store_document_type",
        ],
    }
    response = requests.get(
        GOV_UK_API,
        params=params,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in response.json().get("results", []):
        title = _clean_text(row.get("title"))
        link = str(row.get("link") or "")
        doc_type = str(row.get("content_store_document_type") or "")
        if not title or not link or link in seen:
            continue
        if doc_type in UK_SKIP_TYPES:
            continue
        if link.startswith("/"):
            link = "https://www.gov.uk" + link
        description = _clean_text(row.get("description"))
        orgs = " ".join(
            _clean_text(org.get("title")) for org in (row.get("organisations") or [])
        )
        published = _normalize_date(row.get("public_timestamp"))
        if published > date.today().isoformat():
            continue
        if (date.today() - date.fromisoformat(published)).days > max(1, int(lookback_days)):
            continue
        text = f"{title} {description} {orgs}".lower()
        if not any(term in text for term in US_RELEVANT_TERMS):
            continue
        if not any(org in orgs for org in UK_RELEVANT_ORGS) and not any(
            term in title.lower() for term in ("tariff", "customs", "import", "export", "de minimis")
        ):
            continue
        seen.add(link)
        items.append(
            {
                "title": title,
                "link": link,
                "snippet": description or title,
                "source": "GOV.UK",
                "provider": "uk",
                "market": "uk",
                "region": "foreign",
                "policy_type": _uk_policy_type(text),
                "published_at": published,
                "doc_type": doc_type,
            }
        )
    return items


_FETCHERS = {
    "gov_cn": fetch_gov_cn,
    "federal_register": fetch_federal_register,
    "eu": fetch_eu,
    "uk": fetch_uk,
}


def parse_official_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one official-source item into a verified policy event."""
    title = _clean_text(raw.get("title"))
    link = str(raw.get("link") or "").strip()
    snippet = _clean_text(raw.get("snippet")) or title
    provider = str(raw.get("provider") or "").strip()
    market = str(raw.get("market") or "global").strip()
    region = str(raw.get("region") or "foreign").strip()
    policy_type = str(raw.get("policy_type") or "macro").strip()
    published_at = _normalize_date(raw.get("published_at"))
    text = f"{title} {snippet}"
    impact_level, direction = _classify(text)
    impact_level = _business_impact_level(
        policy_type,
        _extract_rate(text),
        _extract_min_duty(text),
        0.0,
        (),
        text,
    )
    code_seed = f"{provider}|{link}|{title}".encode("utf-8")
    code = "pol-" + hashlib.sha1(code_seed).hexdigest()[:12]
    return {
        "code": code,
        "title": title or f"{region} 官方政策动态",
        "market": market,
        "region": region,
        "policy_type": policy_type,
        "effective_date": _normalize_date(raw.get("effective_date")) or published_at,
        "published_at": published_at,
        "rate_ad_valorem": _extract_rate(text),
        "min_duty_usd": _extract_min_duty(text),
        "cost_adjustment_pct": 0.0,
        "impact_level": impact_level,
        "direction": direction,
        "description": snippet,
        "source": str(raw.get("source") or SOURCE_LABELS.get(provider, "官方来源")),
        "url": link,
        "actions": _actions_for(policy_type, impact_level),
        "categories": [],
        "heuristic": False,
        "fallback_used": False,
        "verified": True,
        "official": True,
        "provider": provider,
        "source_type": "official",
    }


def empty_sources() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "status": "offline",
            "count": 0,
            "error": None,
            "source_url": SOURCE_URLS[name],
        }
        for name in OFFICIAL_SOURCES
    }


def collect_official_policy_events(
    *,
    offline: bool = False,
    lookback_days: int = 14,
    providers: list[str] | tuple[str, ...] | None = None,
    timeout: int = 25,
) -> dict[str, Any]:
    """Collect and dedupe verified events from the enabled official sources."""
    enabled = [
        name
        for name in (providers or OFFICIAL_SOURCES)
        if name in OFFICIAL_SOURCES
    ]
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    events: list[dict[str, Any]] = []
    sources: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    fallback_any = bool(offline)

    for name in enabled:
        source_url = SOURCE_URLS[name]
        if offline:
            sources[name] = {
                "status": "offline",
                "count": 0,
                "error": None,
                "source_url": source_url,
            }
            continue
        try:
            raw_items = _FETCHERS[name](lookback_days=lookback_days, timeout=timeout)
            parsed = [parse_official_event(item) for item in raw_items]
            seen: set[str] = set()
            unique: list[dict[str, Any]] = []
            for event in parsed:
                key = str(event.get("url") or event.get("code") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                unique.append(event)
            sources[name] = {
                "status": "ok",
                "count": len(unique),
                "error": None,
                "source_url": source_url,
            }
            events.extend(unique)
        except Exception as exc:  # noqa: BLE001 - one source may fail
            fallback_any = True
            sources[name] = {
                "status": "error",
                "count": 0,
                "error": str(exc)[:300],
                "source_url": source_url,
            }
            errors.append({"provider": name, "error": str(exc)[:300]})

    deduped: dict[str, dict[str, Any]] = {}
    for event in events:
        key = str(event.get("url") or event.get("code") or "")
        if key and key not in deduped:
            deduped[key] = event
    final_events = list(deduped.values())
    return {
        "generated_at": generated_at,
        "offline": bool(offline),
        "lookback_days": max(1, int(lookback_days)),
        "sources": sources,
        "events": final_events,
        "count": len(final_events),
        "fallback_used": fallback_any,
        "errors": errors,
    }


__all__ = [
    "EC_NEWS_PAGE",
    "EC_PRESS_API",
    "FEDERAL_REGISTER_API",
    "GOV_UK_API",
    "GOV_POLICY_URL",
    "OFFICIAL_SOURCES",
    "SOURCE_LABELS",
    "SOURCE_URLS",
    "collect_official_policy_events",
    "empty_sources",
    "fetch_eu",
    "fetch_federal_register",
    "fetch_gov_cn",
    "fetch_uk",
    "parse_official_event",
]
