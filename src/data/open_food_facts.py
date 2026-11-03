"""Open Food Facts official API adapter (ODbL open product database).

The adapter only calls the public REST API v2 at
``https://world.openfoodfacts.org/api/v2/search``. The database is open data
under ODbL; snapshots generated from it retain the source attribution in the
payload and are intended for academic demo use, not for redistributing a
combined database.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.config import (
    CATEGORIES,
    CATEGORY_KEYWORDS,
    MARKETS,
    OPEN_FOOD_FACTS_ENABLED,
    OPEN_FOOD_FACTS_LATEST_JSON,
    OPEN_FOOD_FACTS_MAX_PRODUCTS,
    category_name,
    market_name,
)
from src.data.base import generated_at as now_iso, save_latest, seed_for, today as today_iso
from src.data.http import PROJECT_USER_AGENT, request_with_retry

OPEN_FOOD_FACTS_API = "https://world.openfoodfacts.org/api/v2/search"
OPEN_FOOD_FACTS_SOURCE = (
    "Open Food Facts (ODbL) https://world.openfoodfacts.org "
    "data reuse: https://wiki.openfoodfacts.org/Reuse"
)
OFF_API_DELAY_SECONDS = 1.0
_LAST_OFF_API_CALL = 0.0

# 本表以「本项目的食品 SKU 编码」为键，值为 Open Food Facts 的 categories_tags_en 标签族。
# ⚠️ 键必须是 src.config.CATEGORY_CATALOG 中真实存在的食品 SKU 编码：collect_open_food_facts()
# 会用 `category in CATEGORIES` 做交集过滤，键写错（例如旧版那个通用 "food"）会让交集恒为空，
# 真实采集静默变成 0 条而不报错。此处覆盖零食 / 调味酱料 / 乳品 / 水产罐头 / 茶饮 / 糖果 /
# 速冻七族；族数 × 市场数即为请求数（适配器自带 1s 限速），故不逐 SKU 枚举全部 132 项。
OFF_CATEGORY_TAGS: dict[str, tuple[str, ...]] = {
    "cn_latiao": ("snacks", "salty-snacks", "plant-based-foods"),
    "cn_laoganma": ("sauces", "condiments"),
    "intl_greek_yogurt": ("dairy-foods", "yogurts"),
    "intl_canned_tuna": ("canned-foods", "seafood"),
    "cn_longjing": ("beverages", "teas"),
    "intl_chocolate_bar": ("confectioneries", "chocolates"),
    "cn_frozen_dumplings": ("frozen-foods", "meals"),
}

OFF_MARKET_COUNTRIES: dict[str, tuple[str, ...]] = {
    "us": ("united-states",),
    "uk": ("united-kingdom",),
    "de": ("germany",),
    "fr": ("france",),
    "jp": ("japan",),
    "ca": ("canada",),
    "au": ("australia",),
    "kr": ("south-korea",),
    "mx": ("mexico",),
    "eu": ("france", "germany", "italy", "spain", "netherlands", "poland"),
    "sea": ("singapore", "malaysia", "thailand", "vietnam", "indonesia", "philippines"),
    "vn": ("vietnam",),
    "ru": ("russia",),
    "hu": ("hungary",),
    "ae": ("united-arab-emirates",),
}


def _official_api_get_json(url: str, params: dict[str, Any]) -> Any:
    """Call the documented Open Food Facts API with identification + throttle.

    robots.txt disallows ``/api`` for web crawlers, but ``/api/v2/search`` is
    the project's official programmatic interface documented at
    https://openfoodfacts.github.io/documentation/. We follow the API docs:
    descriptive User-Agent, moderate rate limit, small trimmed fields.
    """
    global _LAST_OFF_API_CALL
    wait = OFF_API_DELAY_SECONDS - (time.monotonic() - _LAST_OFF_API_CALL)
    if wait > 0:
        time.sleep(wait)
    _LAST_OFF_API_CALL = time.monotonic()
    response = request_with_retry(
        "GET",
        url,
        params=params,
        timeout=20,
        retries=2,
        user_agent=PROJECT_USER_AGENT,
    )
    return response.json()


def empty_open_food_facts_payload() -> dict[str, Any]:
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


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def default_off_category() -> str:
    """返回一个必定存在于食品 SKU 目录中的 Open Food Facts 采样类目编码。"""
    for code in OFF_CATEGORY_TAGS:
        if code in CATEGORIES:
            return code
    return next(iter(OFF_CATEGORY_TAGS))


def _mock_rows(markets: list[str], category: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    today = today_iso()
    category = category or default_off_category()
    for market in markets:
        seed = seed_for(category, market, "open_food_facts")
        rows.append(
            {
                "date": today,
                "category": category,
                "category_name": category_name(category),
                "keyword": CATEGORY_KEYWORDS.get(category, ""),
                "market": market,
                "market_name": market_name(market),
                "product_code": "",
                "product_name": f"Open Food Facts 演示商品（{market_name(market)}）",
                "brand": "",
                "nutrition_grade": "",
                "unique_scans": int(seed * 10000),
                "last_modified_t": None,
                "source": "mock",
                "fallback_used": True,
            }
        )
    return rows


def _row_from_product(
    item: dict[str, Any],
    *,
    category: str,
    keyword: str,
    market: str,
) -> dict[str, Any]:
    return {
        "date": today_iso(),
        "category": category,
        "category_name": category_name(category),
        "keyword": keyword,
        "market": market,
        "market_name": market_name(market),
        "product_code": _safe_text(item.get("code")),
        "product_name": _safe_text(item.get("product_name")),
        "brand": _safe_text(item.get("brands")),
        "nutrition_grade": _safe_text(item.get("nutrition_grades")),
        "unique_scans": _safe_int(item.get("unique_scans_n") or item.get("unique_scans")),
        "last_modified_t": item.get("last_modified_t"),
        "source": "open_food_facts",
        "fallback_used": False,
    }


def parse_open_food_facts_search(
    payload: dict[str, Any],
    *,
    category: str,
    keyword: str,
    market: str,
    max_rows: int = 20,
) -> list[dict[str, Any]]:
    """Normalize one Open Food Facts search page into product signal rows."""
    rows: list[dict[str, Any]] = []
    for item in (payload.get("products") or [])[: max(1, int(max_rows))]:
        row = _row_from_product(
            item,
            category=category,
            keyword=keyword,
            market=market,
        )
        if row["product_code"] or row["product_name"]:
            rows.append(row)
    return rows


def collect_open_food_facts(
    keywords: dict[str, str] | None = None,
    markets: list[str] | None = None,
    *,
    offline: bool = False,
) -> dict[str, Any]:
    """Collect real open product signals, falling back to marked mock rows."""
    generated_at = now_iso()
    categories = [
        category
        for category in OFF_CATEGORY_TAGS
        if category in CATEGORIES
    ]
    coverage_gap: list[str] = []
    if not categories:
        # 防御：OFF_CATEGORY_TAGS 的键与 CATEGORY_CATALOG 脱节时交集恒为空，
        # 真实采集会静默返回 0 条。这里显式留痕并回退 mock，避免“看起来成功”。
        coverage_gap.append(
            "Open Food Facts 类目表与食品 SKU 目录无交集，真实采集已跳过"
            f"（OFF_CATEGORY_TAGS={sorted(OFF_CATEGORY_TAGS)}）"
        )
    sample_category = default_off_category()
    keywords = keywords or {
        category: CATEGORY_KEYWORDS.get(category, category_name(category))
        for category in categories
    }
    markets = markets or list(MARKETS)
    requested_markets = [market for market in markets if market in MARKETS]
    if not requested_markets:
        requested_markets = ["us"]

    if offline or not OPEN_FOOD_FACTS_ENABLED:
        rows = _mock_rows(requested_markets, sample_category)
        return {
            "generated_at": generated_at,
            "date": today_iso(),
            "offline": bool(offline),
            "fallback_used": True,
            "provider": "mock",
            "rows": rows,
            "source_count": len(rows),
            "coverage": {
                "requested": len(requested_markets),
                "real": 0,
                "mock": len(requested_markets),
            },
            "errors": coverage_gap + ["离线/未启用，未发起真实请求"],
        }

    rows: list[dict[str, Any]] = []
    real_markets: set[str] = set()
    errors: list[str] = list(coverage_gap)
    for market in requested_markets:
        countries = OFF_MARKET_COUNTRIES.get(market)
        if not countries:
            errors.append(f"{market}: 未配置 Open Food Facts 国家标签")
            continue
        for category in categories:
            try:
                params = {
                    "categories_tags_en": "|".join(OFF_CATEGORY_TAGS[category]),
                    "countries_tags_en": "|".join(countries),
                    "sort_by": "unique_scans_n",
                    "page": 1,
                    "page_size": max(1, int(OPEN_FOOD_FACTS_MAX_PRODUCTS)),
                    "fields": (
                        "code,product_name,brands,nutrition_grades,"
                        "countries_tags_en,unique_scans_n,last_modified_t"
                    ),
                }
                payload = _official_api_get_json(OPEN_FOOD_FACTS_API, params)
                market_rows = parse_open_food_facts_search(
                    payload,
                    category=category,
                    keyword=keywords.get(category, ""),
                    market=market,
                    max_rows=OPEN_FOOD_FACTS_MAX_PRODUCTS,
                )
                if not market_rows:
                    raise RuntimeError("Open Food Facts 未返回商品")
                rows.extend(market_rows)
                real_markets.add(market)
            except Exception as exc:  # noqa: BLE001 - 单市场失败回退 mock
                errors.append(f"{market}:{category}: {exc}")

    missing_markets = [market for market in requested_markets if market not in real_markets]
    if missing_markets:
        rows.extend(_mock_rows(missing_markets, sample_category))

    provider = "open_food_facts" if real_markets else "mock"
    return {
        "generated_at": generated_at,
        "date": today_iso(),
        "offline": False,
        "fallback_used": bool(missing_markets),
        "provider": provider,
        "rows": rows,
        "source_count": len(rows),
        "coverage": {
            "requested": len(requested_markets),
            "real": len(real_markets),
            "mock": len(missing_markets),
        },
        "errors": errors,
        "source_url": OPEN_FOOD_FACTS_API,
        "source": OPEN_FOOD_FACTS_SOURCE,
    }


def save_latest_open_food_facts(payload: dict[str, Any]) -> Path:
    return save_latest(payload, OPEN_FOOD_FACTS_LATEST_JSON)


def load_latest_open_food_facts() -> dict[str, Any]:
    if not OPEN_FOOD_FACTS_LATEST_JSON.exists():
        return empty_open_food_facts_payload()
    try:
        payload = json.loads(OPEN_FOOD_FACTS_LATEST_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_open_food_facts_payload()
    payload.setdefault("rows", [])
    payload.setdefault("errors", [])
    payload.setdefault(
        "coverage",
        {"requested": 0, "real": 0, "mock": 0},
    )
    return payload


def open_food_facts_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(payload.get("generated_at")),
        "provider": payload.get("provider"),
        "updated_at": payload.get("generated_at"),
        "fallback_used": bool(payload.get("fallback_used")),
        "rows": int(payload.get("source_count") or 0),
        "coverage": payload.get("coverage") or {},
        "errors": payload.get("errors") or [],
        "snapshot": "output/open_food_facts/latest.json",
    }


__all__ = [
    "OPEN_FOOD_FACTS_API",
    "OPEN_FOOD_FACTS_SOURCE",
    "collect_open_food_facts",
    "default_off_category",
    "empty_open_food_facts_payload",
    "load_latest_open_food_facts",
    "open_food_facts_status",
    "parse_open_food_facts_search",
    "save_latest_open_food_facts",
]
