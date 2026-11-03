"""
四脑 AI 研究代理的工具层。

工具包括：联网搜索、网页抓取、读取本地看板数据、返回模拟平台数据。
所有工具都返回文本结果，方便大模型在下一轮继续推理。
"""

from __future__ import annotations

from html.parser import HTMLParser
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from src.config import CATEGORY_CATALOG, SEARCH_PROVIDERS
from src.data.crawl_engine import LegalCrawlEngine
from src.data.base import pageview_trend_pct
from src.data.http import extract_main_text

# 模拟平台数据的默认品类：与四脑默认测试产品（老干妈辣椒酱 laoganma chili sauce）对齐，
# 避免调用方未传 category 时落回一个已不存在的消费类目。
DEFAULT_MOCK_CATEGORY = (
    "cn_laoganma" if "cn_laoganma" in CATEGORY_CATALOG else next(iter(CATEGORY_CATALOG))
)


USER_AGENT = "ZhixuanCrossBorderResearch/1.0"
MAX_TOOL_TEXT = 6000
SEARCH_RESULT_CACHE_TTL_SECONDS = float(
    os.environ.get("SEARCH_RESULT_CACHE_TTL", "300")
)
_SEARCH_RESULT_CACHE: dict[
    tuple[str, str, int, str, str],
    tuple[float, list[dict[str, Any]]],
] = {}
_SEARCH_RESULT_CACHE_LOCK = threading.Lock()
_DDG_ENGINE: LegalCrawlEngine | None = None
_DDG_ENGINE_LOCK = threading.Lock()
WIKIMEDIA_SEARCH_API = "https://api.wikimedia.org/core/v1/wikipedia/en/search/page"
WIKIMEDIA_PAGEVIEWS_API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _search_timeout() -> float:
    """Resolve the per-request web-search timeout from configuration.

    ``SEARCH_TIMEOUT_MS`` is the documented primary setting (milliseconds);
    ``FOUR_BRAIN_SEARCH_TIMEOUT`` (seconds) is kept as a compatibility
    fallback so four-brain research never waits on a single network call
    indefinitely.
    """
    raw_ms = _env("SEARCH_TIMEOUT_MS")
    if raw_ms:
        try:
            return max(1.0, float(raw_ms) / 1000.0)
        except (TypeError, ValueError):
            pass
    try:
        return max(1.0, float(_env("FOUR_BRAIN_SEARCH_TIMEOUT", "20")))
    except (TypeError, ValueError):
        return 20.0


def _http_get(url: str, timeout: float = 20.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _http_post_json(
    url: str, payload: dict[str, Any], timeout: float = 20.0
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def _resolve_search_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    try:
        max_results = int(cfg.get("max_results") or _env("SEARCH_MAX_RESULTS", "5"))
    except (TypeError, ValueError):
        max_results = 5
    return {
        "provider": str(cfg.get("provider") or _env("SEARCH_PROVIDER", "duckduckgo_html")).strip().lower(),
        "api_key": str(cfg.get("api_key") or _env("SEARCH_API_KEY")).strip(),
        "api_url": str(cfg.get("api_url") or _env("SEARCH_API_URL")).strip(),
        "max_results": max(1, min(20, max_results)),
        "timeout": _search_timeout(),
    }


def _truncate(text: str, max_chars: int = MAX_TOOL_TEXT) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _clean_html(raw: str) -> str:
    return extract_main_text(raw)


def _search_url(query: str) -> str:
    """为没有可解析原始链接的结果提供可点击的检索页链接。"""
    return "https://duckduckgo.com/?q=" + urllib.parse.quote(query)


def _ensure_links(results: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    fallback = _search_url(query)
    return [
        {
            "title": str(item.get("title", "")),
            "snippet": str(item.get("snippet", "")),
            "link": str(item.get("link") or "").strip() or fallback,
        }
        for item in results
    ]


class _DuckDuckGoParser(HTMLParser):
    """Extract result title, snippet and link from DuckDuckGo HTML/Lite pages."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._mode: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        classes = set(attr_map.get("class", "").split())
        if tag == "a" and classes & {"result__a", "result-link"}:
            self._current = {"title": "", "snippet": "", "link": attr_map.get("href", "")}
            self._mode = "title"
            self._buffer = []
        elif tag == "td" and "result-snippet" in classes and self._current:
            self._mode = "snippet"
            self._buffer = []
        elif tag == "a" and "result__snippet" in classes and self._current:
            self._mode = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._mode:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return
        text = " ".join("".join(self._buffer).split()).strip()
        if tag == "a" and self._mode == "title":
            self._current["title"] = text
            self._mode = None
            self._buffer = []
            return
        if tag in {"a", "td"} and self._mode == "snippet":
            self._current["snippet"] = text
            self._buffer = []
            if self._current.get("title") or self._current.get("snippet"):
                self.results.append(self._current)
            self._current = None
            self._mode = None


def _decode_duckduckgo_link(url: str) -> str:
    if "uddg=" not in url:
        return url
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    return query.get("uddg", [url])[0]


def duckduckgo_html_search(
    query: str, max_results: int = 5, timeout: float = 20.0
) -> list[dict[str, str]]:
    url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": query})
    try:
        engine = _shared_ddg_engine(timeout)
        with _DDG_ENGINE_LOCK:
            result = engine.fetch(url)
        raw = result.get("html") or ""
        if not raw:
            raise RuntimeError(result.get("error") or "empty DuckDuckGo response")
    except Exception as exc:  # noqa: BLE001
        return _ensure_links(
            [{"title": "DuckDuckGo 请求失败", "snippet": str(exc), "link": ""}],
            query,
        )
    parser = _DuckDuckGoParser()
    parser.feed(raw)
    return _ensure_links(
        [
            {
                "title": item["title"] or item["snippet"][:80],
                "snippet": item["snippet"],
                "link": _decode_duckduckgo_link(item["link"]),
            }
            for item in parser.results[:max_results]
        ],
        query,
    )


def _shared_ddg_engine(timeout: float) -> LegalCrawlEngine:
    """复用同一 Crawlee 引擎实例，保留 robots 与节流语义。"""
    global _DDG_ENGINE
    with _DDG_ENGINE_LOCK:
        if _DDG_ENGINE is None:
            _DDG_ENGINE = LegalCrawlEngine(
                user_agent=USER_AGENT,
                timeout=max(1.0, float(timeout)),
                delay=1.0,
            )
        return _DDG_ENGINE


def mock_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    q = query.lower()
    topics: list[tuple[tuple[str, ...], list[dict[str, str]]]] = [
        (
            ("辣条", "latiao", "spicy strips", "麻辣零食"),
            [
                {
                    "title": "模拟·北美辣条零食市场观察",
                    "snippet": "2026 年北美华人零食与嗜辣零食需求持续上升，Amazon 热销价格带集中在 3-6 美元；评论高频提及辣度、油感与独立小包装。",
                    "link": "",
                },
                {
                    "title": "模拟·辣条差评与机会点",
                    "snippet": "常见差评包括过油、偏咸、包装漏气与运输压碎；可差异化方向为低钠配方、充氮保鲜与耐压外箱。",
                    "link": "",
                },
                {
                    "title": "模拟·食品合规提示",
                    "snippet": "进入美国市场需完成 FDA 食品设施注册并落实 FSMA 预防性控制与营养成分标签；欧盟需符合 (EU) No 1169/2011 标签法规并申报食品添加剂 E 编号。",
                    "link": "",
                },
            ],
        ),
        (
            ("辣椒酱", "chili sauce", "chili crisp", "老干妈", "laoganma"),
            [
                {
                    "title": "模拟·辣椒酱出海价格带",
                    "snippet": "老干妈等中式辣椒酱在北美与东南亚常年动销，6-14 美元价格带竞争中等，玻璃瓶装与多规格组合是主要形态。",
                    "link": "",
                },
                {
                    "title": "模拟·辣椒酱评论洞察",
                    "snippet": "差评集中在玻璃瓶运输破损、漏油与辣度批次不稳；机会点包括防漏内盖、耐摔外包装与辣度分级标识。",
                    "link": "",
                },
                {
                    "title": "模拟·辣椒酱合规提示",
                    "snippet": "油浸辣椒制品在美国通常按酸化/低酸罐头食品管理（21 CFR 113/114），需工艺备案；过敏原（大豆、小麦）必须醒目标注。",
                    "link": "",
                },
            ],
        ),
        (
            ("速冻水饺", "frozen dumplings", "dumpling", "冷冻食品", "速冻"),
            [
                {
                    "title": "模拟·速冻水饺海外需求",
                    "snippet": "海外华人家庭与亚洲超市渠道带动速冻水饺增长，11-18 美元价格带为主流；馅料口味与煮制不易破皮是复购关键。",
                    "link": "",
                },
                {
                    "title": "模拟·速冻水饺差评分析",
                    "snippet": "差评集中在破皮、馅料偏少、解冻后粘连与冰霜过多；皮料配方与全程 -18°C 冷链是核心控制点。",
                    "link": "",
                },
                {
                    "title": "模拟·冷链合规提示",
                    "snippet": "出口需 HACCP 体系与冷冻食品风险控制，欧盟另需兽医卫生证书；全程温控记录与解冻指示标签是常见审核项。",
                    "link": "",
                },
            ],
        ),
        (
            ("龙井", "longjing", "green tea", "绿茶", "茶叶"),
            [
                {
                    "title": "模拟·欧洲绿茶市场观察",
                    "snippet": "欧洲散装绿茶与礼盒装需求稳定，20-35 美元/100g 价格带以产地故事与有机认证区分；明前采摘是溢价点。",
                    "link": "",
                },
                {
                    "title": "模拟·绿茶评论洞察",
                    "snippet": "差评集中在香气流失、包装密封性不足与农残疑虑；建议充氮铝箔内袋 + 避光罐体，并附第三方检测报告。",
                    "link": "",
                },
                {
                    "title": "模拟·茶叶合规提示",
                    "snippet": "欧盟按 EC 396/2005 执行农药残留限量（MRL）并设铅等重金属限值；有机宣称需 EU 有机认证，美国需 FDA 食品设施注册与 FSMA 合规。",
                    "link": "",
                },
            ],
        ),
        (
            ("自热火锅", "self heating hot pot", "self-heating", "方便食品", "自热"),
            [
                {
                    "title": "模拟·自热火锅渠道机会",
                    "snippet": "东南亚与北美留学生渠道对自热火锅接受度高，15-22 美元价格带适合试水；菜包丰富度与加热包稳定性是差异化点。",
                    "link": "",
                },
                {
                    "title": "模拟·自热火锅用户反馈",
                    "snippet": "差评集中在加热不足、汤包漏液与气味偏重；用户关注加热时长一致性与多语言操作说明。",
                    "link": "",
                },
                {
                    "title": "模拟·运输合规提示",
                    "snippet": "发热包含氧化钙/铝粉，属航空运输受限或禁运品，需按危险品规则申报并改走海运；欧盟还需符合食品接触材料 (EU) 10/2011。",
                    "link": "",
                },
            ],
        ),
        (
            ("枸杞", "goji", "wolfberry", "蜂蜜", "honey", "养生"),
            [
                {
                    "title": "模拟·养生食品跨境需求",
                    "snippet": "宁夏枸杞与枸杞蜂蜜在东南亚、中东市场增长明显，11-25 美元价格带竞争中等；溯源与零添加是主要卖点。",
                    "link": "",
                },
                {
                    "title": "模拟·枸杞蜂蜜评论洞察",
                    "snippet": "差评集中在含水率偏高、结块、疑似硫磺熏蒸与掺糖；建议提供批次检测、含水率指标与产区溯源二维码。",
                    "link": "",
                },
                {
                    "title": "模拟·养生食品合规提示",
                    "snippet": "干果与蜂产品在美国易触发 FDA 进口警报，需关注二氧化硫残留、农残与蜂产品抗生素（氯霉素）限量；欧盟需符合 EC 396/2005 并做进口商合规声明。",
                    "link": "",
                },
            ],
        ),
    ]
    for terms, results in topics:
        if any(term in q for term in terms):
            return _ensure_links(results[:max_results], query)
    return _ensure_links(
        [
            {
                "title": "模拟·市场研究占位结果",
                "snippet": f"已为查询“{query}”生成结构化模拟摘要。真实联网时请核对来源、数据日期与统计口径；当前结果仅用于演示，不可作为决策依据。",
                "link": "",
            }
        ][:max_results],
        query,
    )


def _wikimedia_json_search(
    query: str, max_results: int = 5, timeout: float = 20.0
) -> list[dict[str, Any]]:
    """Wikimedia core search fallback used when the root crawler is unavailable."""
    url = WIKIMEDIA_SEARCH_API + "?" + urllib.parse.urlencode(
        {"q": query, "limit": max(1, int(max_results))}
    )
    raw = json.loads(_http_get(url, timeout=max(1.0, float(timeout))))
    results: list[dict[str, Any]] = []
    for page in (raw.get("pages") or [])[: max(1, int(max_results))]:
        title = str(page.get("title") or "")
        key = str(page.get("key") or "")
        excerpt = re.sub(r"<[^>]+>", "", str(page.get("excerpt") or "")).strip()
        description = str(page.get("description") or "").strip()
        if not (title or key):
            continue
        results.append(
            {
                "title": title or query,
                "snippet": excerpt or description,
                "link": "https://en.wikipedia.org/wiki/"
                + urllib.parse.quote(key.replace(" ", "_")),
                "source": "wikimedia_search",
                "article_key": key,
            }
        )
    return results


def _wikimedia_pageviews(
    article_key: str, days: int = 90, timeout: float = 20.0
) -> list[dict[str, Any]]:
    """Wikimedia pageview rows for the top search hit, used for trend display."""
    if not article_key:
        return []
    end = date.today()
    start = end - timedelta(days=max(1, int(days)) - 1)
    safe_title = urllib.parse.quote(article_key.replace(" ", "_"))
    url = (
        f"{WIKIMEDIA_PAGEVIEWS_API}/en.wikipedia/all-access/user/"
        f"{safe_title}/daily/{start:%Y%m%d}/{end:%Y%m%d}"
    )
    raw = json.loads(_http_get(url, timeout=max(1.0, float(timeout))))
    rows: list[dict[str, Any]] = []
    for item in raw.get("items") or []:
        timestamp = str(item.get("timestamp") or "")
        if len(timestamp) < 8:
            continue
        rows.append({"date": timestamp[:8], "views": int(item.get("views") or 0)})
    return rows


def crawler_search(
    query: str,
    max_results: int = 5,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crawler-first research: Wikimedia search + pageviews with robots checks.

    Prefers ``src.data.legal_crawler`` (robots.txt + rate limit + cache-ready)
    when running inside the unified backend; otherwise falls back to direct
    Wikimedia API calls so the standalone demo package still works.
    """
    timeout = float((config or {}).get("timeout") or _search_timeout())
    try:
        from src.data import legal_crawler

        payload = legal_crawler.crawler_search(query, max_results=max_results)
    except Exception:  # noqa: BLE001 - standalone demo fallback
        results = _wikimedia_json_search(query, max_results, timeout=timeout)
        article_key = next(
            (r.get("article_key") for r in results if r.get("article_key")), None
        )
        pageviews = (
            _wikimedia_pageviews(article_key, timeout=timeout) if article_key else []
        )
        payload = {
            "results": results,
            "pageviews": pageviews,
            "pageview_article": article_key,
            "provider": "mock" if not results and not pageviews else "crawler",
            "fallback_used": not results and not pageviews,
        }

    results = [dict(item) for item in (payload.get("results") or [])]
    for item in results:
        item.pop("article_key", None)
    pageviews = payload.get("pageviews") or []
    fallback_used = bool(payload.get("fallback_used"))
    provider = str(payload.get("provider") or ("mock" if fallback_used else "crawler"))
    return {
        "query": query,
        "results": results,
        "pageviews": pageviews,
        "pageview_trend_pct": pageview_trend_pct(pageviews),
        "pageview_article": payload.get("pageview_article"),
        "provider": provider,
        "fallback_used": fallback_used,
        "mock_used": fallback_used,
    }


def search_web(
    query: str, max_results: int = 5, config: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    """统一搜索入口：任何提供方/错误结果都补齐可点击链接。"""
    return _ensure_links(_search_web_raw(query, max_results, config), query)


def _cacheable_search_results(results: list[dict[str, Any]]) -> bool:
    if not results:
        return False
    failure_markers = ("请求失败", "配置缺失", "未知搜索服务")
    return not any(
        any(marker in str(item.get("title", "")) for marker in failure_markers)
        for item in results
    )


def _search_web_raw(
    query: str, max_results: int = 5, config: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    resolved = _resolve_search_config(config)
    key = (
        resolved["provider"],
        query,
        max_results,
        resolved.get("api_url") or "",
        resolved.get("api_key") or "",
    )
    now = time.time()
    with _SEARCH_RESULT_CACHE_LOCK:
        hit = _SEARCH_RESULT_CACHE.get(key)
        if hit is not None and now - hit[0] <= SEARCH_RESULT_CACHE_TTL_SECONDS:
            return list(hit[1])
    results = _search_web_raw_impl(query, max_results, config)
    if _cacheable_search_results(results):
        with _SEARCH_RESULT_CACHE_LOCK:
            _SEARCH_RESULT_CACHE[key] = (now, list(results))
    return results


def _search_web_raw_impl(
    query: str, max_results: int = 5, config: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    resolved = _resolve_search_config(config)
    provider = resolved["provider"]
    if provider not in SEARCH_PROVIDERS:
        return [
            {
                "title": "未知搜索服务",
                "snippet": f"SEARCH_PROVIDER={provider} 不受支持，请使用 {sorted(SEARCH_PROVIDERS)}",
                "link": "",
            }
        ]
    if provider == "mock":
        return mock_search(query, max_results)
    if provider == "crawler":
        return crawler_search(query, max_results, config)["results"]
    if provider == "duckduckgo":
        url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        )
        data = json.loads(_http_get(url, timeout=resolved["timeout"]))
        results = []
        if data.get("AbstractText"):
            results.append({"title": data.get("Heading", "DuckDuckGo"), "snippet": data["AbstractText"], "link": data.get("AbstractURL", "")})
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if "Topics" in topic:
                for sub in topic["Topics"][:max_results]:
                    results.append({"title": sub.get("Text", "")[:120], "snippet": sub.get("Text", ""), "link": sub.get("FirstURL", "")})
            else:
                results.append({"title": topic.get("Text", "")[:120], "snippet": topic.get("Text", ""), "link": topic.get("FirstURL", "")})
        return results[:max_results]
    if provider == "duckduckgo_html":
        return duckduckgo_html_search(
            query, max_results, timeout=resolved["timeout"]
        )
    if provider == "tavily":
        api_key = resolved["api_key"]
        if not api_key:
            return [{"title": "配置缺失", "snippet": "SEARCH_API_KEY 未配置，无法调用 Tavily。", "link": ""}]
        data = _http_post_json(
            resolved["api_url"] or "https://api.tavily.com/search",
            {"api_key": api_key, "query": query, "max_results": max_results},
            timeout=resolved["timeout"],
        )
        return [
            {"title": item.get("title", ""), "snippet": item.get("content", ""), "link": item.get("url", "")}
            for item in data.get("results", [])
        ][:max_results]
    if provider == "serpapi":
        api_key = resolved["api_key"]
        url = (resolved["api_url"] or "https://serpapi.com/search.json") + "?" + urllib.parse.urlencode(
            {"q": query, "api_key": api_key, "num": max_results}
        )
        data = json.loads(_http_get(url, timeout=resolved["timeout"]))
        return [
            {"title": item.get("title", ""), "snippet": item.get("snippet", ""), "link": item.get("link", "")}
            for item in data.get("organic_results", [])
        ][:max_results]
    if provider == "generic":
        api_url = resolved["api_url"]
        api_key = resolved["api_key"]
        if not api_url:
            return [{"title": "配置缺失", "snippet": "SEARCH_API_URL 未配置。", "link": ""}]
        data = _http_post_json(
            api_url,
            {"query": query, "api_key": api_key, "max_results": max_results},
            timeout=resolved["timeout"],
        )
        rows = data.get("results") or data.get("organic_results") or data.get("data") or []
        return [
            {"title": str(item.get("title", "")), "snippet": str(item.get("snippet") or item.get("content") or ""), "link": str(item.get("url") or item.get("link") or "")}
            for item in rows
        ][:max_results]
    return mock_search(query, max_results)


def fetch_page(
    url: str, max_chars: int = MAX_TOOL_TEXT, timeout: float | None = None
) -> dict[str, str]:
    try:
        raw = _http_get(
            url, timeout=max(1.0, float(timeout if timeout is not None else _search_timeout()))
        )
        text = _truncate(_clean_html(raw), max_chars)
        return {"url": url, "text": text, "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "text": f"抓取失败：{exc}", "status": "error"}


def load_dashboard_snapshot(data: dict[str, Any], category: str | None = None, market: str | None = None) -> dict[str, Any]:
    rows = data.get("history", [])
    if category:
        rows = [row for row in rows if row.get("category") == category]
    if market:
        rows = [row for row in rows if row.get("market") == market]
    latest_date = max((row.get("date", "") for row in rows), default=None)
    latest = [row for row in rows if row.get("date") == latest_date]
    recommendations = data.get("recommendations", [])
    if category:
        recommendations = [row for row in recommendations if row.get("category") == category]
    if market:
        recommendations = [row for row in recommendations if row.get("market") == market]
    return {
        "latest_date": latest_date,
        "latest_rows": latest[:20],
        "recommendations": recommendations[:10],
        "categories": data.get("categories", {}),
        "markets": data.get("markets", {}),
    }


def execute_tool_with_meta(
    action: dict[str, Any],
    data: dict[str, Any],
    search_config: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    tool = str(action.get("action") or action.get("tool") or "").strip().lower()
    if tool in {"web_search", "search_web", "search"}:
        query = str(action.get("query") or action.get("q") or "")
        resolved = _resolve_search_config(search_config)
        max_results = int(action.get("max_results") or resolved["max_results"])
        results = search_web(query, max_results=max_results, config=search_config)
        sources = [
            {"title": str(item.get("title", "")), "snippet": str(item.get("snippet", "")), "link": str(item.get("link", ""))}
            for item in results
        ]
        return "搜索结果：\n" + json.dumps(results, ensure_ascii=False)[:MAX_TOOL_TEXT], sources
    if tool in {"fetch_page", "fetch_url"}:
        url = str(action.get("url") or "")
        resolved = _resolve_search_config(search_config)
        return (
            "网页内容：\n"
            + json.dumps(
                fetch_page(url, timeout=resolved["timeout"]), ensure_ascii=False
            )[:MAX_TOOL_TEXT],
            [
                {"title": url, "snippet": "", "link": url}
            ],
        )
    if tool in {"load_dashboard_data", "local_data"}:
        snapshot = load_dashboard_snapshot(data, action.get("category"), action.get("market"))
        return "本地看板数据：\n" + json.dumps(snapshot, ensure_ascii=False)[:MAX_TOOL_TEXT], []
    if tool in {"mock_market_data", "platform_data"}:
        keyword = str(action.get("keyword") or action.get("q") or "")
        payload = {
            "category": action.get("category") or DEFAULT_MOCK_CATEGORY,
            "market": action.get("market") or "us",
            "source": "mock-platform",
            "keyword": keyword,
            "sales_volume": 92.0,
            "search_index": 86.0,
            "competition_index": 58.0,
            "price_median": 35.0,
            "review_growth": 8.0,
            "export_value": 3600.0,
        }
        return "模拟平台数据：\n" + json.dumps(payload, ensure_ascii=False), []
    return f"未知工具：{tool}", []


def execute_tool(
    action: dict[str, Any],
    data: dict[str, Any],
    search_config: dict[str, Any] | None = None,
) -> str:
    return execute_tool_with_meta(action, data, search_config)[0]


__all__ = [
    "SEARCH_PROVIDERS",
    "crawler_search",
    "duckduckgo_html_search",
    "execute_tool",
    "execute_tool_with_meta",
    "fetch_page",
    "load_dashboard_snapshot",
    "mock_search",
    "search_web",
]
