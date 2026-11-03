"""平台榜单适配器框架：Keepa / Amazon / TikTok Shop，默认 mock 回退。"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    CATEGORIES,
    EBAY_APP_ID,
    EBAY_CERT_ID,
    EBAY_DEV_ID,
    GITHUB_DATA_DIR,
    KEEPA_API_KEY,
    MARKETS,
    PLATFORM_RANKING_PROVIDERS,
    PLATFORM_RANKINGS_LATEST_JSON,
    category_name,
    market_name,
)
from src.data.github_datasets import map_category, map_market
from src.data.base import generated_at as now_iso, save_latest, seed_int, today as today_iso
from src.data.legal_crawler import RobotsDisallowedError

_KEEPA_DOMAINS = {
    "us": 1,
    "uk": 2,
    "de": 3,
    "fr": 4,
    "jp": 5,
    "ca": 6,
    "au": 7,
}


def empty_rankings_payload() -> dict[str, Any]:
    return {
        "generated_at": None,
        "date": None,
        "offline": False,
        "fallback_used": False,
        "providers": [],
        "rows": [],
        "source_count": 0,
    }


def _mock_rows(
    categories: list[str],
    markets: list[str],
    provider: str = "mock",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    today = today_iso()
    for category in categories:
        for market in markets:
            seed = seed_int(category, market, provider)
            for index in range(5):
                rank = (seed + index * 7) % 120 + 1
                rows.append(
                    {
                        "date": today,
                        "category": category,
                        "category_name": category_name(category),
                        "market": market,
                        "market_name": market_name(market),
                        "platform": provider,
                        "rank": rank,
                        "product": f"{category_name(category)} 演示商品 {index + 1}",
                        "source": provider,
                        "fallback_used": True,
                    }
                )
    return rows


def _amazon_bestsellers_rows(
    categories: list[str],
    markets: list[str],
) -> list[dict[str, Any]]:
    from src.data.collector import collect_amazon_bestsellers

    frame = collect_amazon_bestsellers()
    rows: list[dict[str, Any]] = []
    today = today_iso()
    for index, item in enumerate(frame.head(20).to_dict(orient="records")):
        category = categories[index % len(categories)]
        market = markets[index % len(markets)]
        rows.append(
            {
                "date": today,
                "category": category,
                "category_name": category_name(category),
                "market": market,
                "market_name": market_name(market),
                "platform": "amazon_bestsellers",
                "rank": int(index + 1),
                "product": item.get("title", ""),
                "source": "amazon_bestsellers",
                "fallback_used": False,
            }
        )
    return rows


def _github_float(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(numeric):
        return 0.0
    return numeric


def _load_ebay_github_frame() -> pd.DataFrame:
    provider_dir = GITHUB_DATA_DIR / "ebay"
    files = sorted(
        path
        for path in provider_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".csv"
    )
    if not files:
        raise FileNotFoundError(f"缺少 GitHub eBay 免费样例 CSV: {provider_dir}")
    return pd.concat(
        [
            pd.read_csv(path, encoding="utf-8")
            for path in files
        ],
        ignore_index=True,
    )


def _ebay_github_rows(
    categories: list[str],
    markets: list[str],
    *,
    frame: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Rank products from the free GitHub eBay sample dataset without any key."""
    if frame is None:
        frame = _load_ebay_github_frame()
    rows: list[dict[str, Any]] = []
    today = today_iso()
    for category in categories:
        candidates: list[dict[str, Any]] = []
        for _, item in frame.iterrows():
            title = str(item.get("title") or "").strip()
            category_text = " ".join(
                str(item.get(column) or "")
                for column in ("root_category", "breadcrumbs", "popular_categories")
            )
            if map_category(title, category_text) != category:
                continue
            market = map_market(
                str(item.get("item_location") or ""),
                str(item.get("currency") or ""),
                str(item.get("ships_to") or ""),
            ) or "us"
            if market not in markets:
                continue
            candidates.append(
                {
                    "title": title or f"{category_name(category)} eBay 样例",
                    "url": str(item.get("url") or ""),
                    "market": market,
                    "sold_count": _github_float(item.get("sold_count")),
                    "price": _github_float(item.get("price")),
                }
            )
        candidates.sort(key=lambda item: item["sold_count"], reverse=True)
        for rank, item in enumerate(candidates[:5], start=1):
            rows.append(
                {
                    "date": today,
                    "category": category,
                    "category_name": category_name(category),
                    "market": item["market"],
                    "market_name": market_name(item["market"]),
                    "platform": "ebay_github",
                    "rank": rank,
                    "product": item["title"],
                    "source": "github/luminati-io/eBay-dataset-sample",
                    "fallback_used": False,
                    "url": item["url"],
                    "sold_count": item["sold_count"],
                    "price": item["price"],
                }
            )
    return rows


def _load_amazon_github_frame() -> pd.DataFrame:
    provider_dir = GITHUB_DATA_DIR / "amazon"
    files = sorted(
        path
        for path in provider_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".csv"
    )
    if not files:
        raise FileNotFoundError(f"缺少 GitHub Amazon 免费样例 CSV: {provider_dir}")
    return pd.concat(
        [pd.read_csv(path, encoding="utf-8") for path in files],
        ignore_index=True,
    )


def _amazon_github_rows(
    categories: list[str],
    markets: list[str],
    *,
    frame: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Rank products from the free GitHub Amazon sample dataset without any key."""
    if frame is None:
        frame = _load_amazon_github_frame()
    rows: list[dict[str, Any]] = []
    today = today_iso()
    for category in categories:
        candidates: list[dict[str, Any]] = []
        for _, item in frame.iterrows():
            title = str(item.get("title") or "").strip()
            category_text = " ".join(
                str(item.get(column) or "")
                for column in (
                    "categories",
                    "root_bs_category",
                    "department",
                    "bs_category",
                )
            )
            if map_category(title, category_text) != category:
                continue
            market = map_market(str(item.get("domain") or "")) or "us"
            if market not in markets:
                continue
            rank_value = _github_float(item.get("root_bs_rank"))
            candidates.append(
                {
                    "title": title or f"{category_name(category)} Amazon 样例",
                    "url": str(item.get("url") or ""),
                    "market": market,
                    "rank": rank_value if rank_value > 0 else 999999,
                    "price": _github_float(item.get("final_price")),
                    "rating": _github_float(item.get("rating")),
                }
            )
        candidates.sort(key=lambda item: item["rank"])
        for rank, item in enumerate(candidates[:5], start=1):
            rows.append(
                {
                    "date": today,
                    "category": category,
                    "category_name": category_name(category),
                    "market": item["market"],
                    "market_name": market_name(item["market"]),
                    "platform": "amazon_github",
                    "rank": rank,
                    "product": item["title"],
                    "source": "github/luminati-io/Amazon-dataset-samples",
                    "fallback_used": False,
                    "url": item["url"],
                    "root_bs_rank": item["rank"],
                    "price": item["price"],
                    "rating": item["rating"],
                }
            )
    return rows


def _keepa_rows(
    categories: list[str],
    markets: list[str],
) -> tuple[list[dict[str, Any]], bool, str]:
    if not KEEPA_API_KEY:
        return [], True, "skipped: 缺少 KEEPA_API_KEY，已跳过真实请求"
    try:
        import keepa as keepa_client
    except ImportError:
        return [], True, "keepa 包未安装，已跳过真实请求"

    api = keepa_client.Keepa(KEEPA_API_KEY)
    rows: list[dict[str, Any]] = []
    today = today_iso()
    errors: list[str] = []
    token_estimate: dict[str, Any] | None = None
    for category in categories:
        keyword = category_name(category)
        domain_ids = [
            _KEEPA_DOMAINS[market]
            for market in markets
            if market in _KEEPA_DOMAINS
        ]
        for domain in domain_ids or [1]:
            try:
                found = api.product_finder(
                    {"title": keyword, "domain": domain, "csv": 0}
                ) or []
                asins = [item.get("asin") for item in found if item.get("asin")]
                products = api.query(asins[:5], stats=180) if asins else []
                market = next(
                    (m for m, d in _KEEPA_DOMAINS.items() if d == domain),
                    "us",
                )
                for index, product in enumerate(products[:5]):
                    row: dict[str, Any] = {
                        "date": today,
                        "category": category,
                        "category_name": category_name(category),
                        "market": market,
                        "market_name": market_name(market),
                        "platform": "keepa",
                        "rank": int(index + 1),
                        "product": product.get("title") or keyword,
                        "source": "keepa",
                        "fallback_used": False,
                        "asin": product.get("asin"),
                        "bsr": product.get("salesRankReference"),
                    }
                    # B-2：Keepa 衍生特征（价格稳定性/折扣噪声/BSR 波动/价格弹性/异常促销）
                    try:
                        from src.features.keepa_features import keepa_features

                        row.update(keepa_features(product))
                    except Exception:  # noqa: BLE001 - 特征计算失败不回退整行
                        pass
                    rows.append(row)
                if asins:
                    try:
                        from src.features.keepa_features import estimate_keepa_tokens

                        token_estimate = estimate_keepa_tokens(len(asins[:5]), stats_days=180)
                    except Exception:  # noqa: BLE001
                        token_estimate = None
            except Exception as exc:  # noqa: BLE001 - 单品类失败不阻塞整体
                errors.append(f"{category}: {exc}")
    if not rows:
        return [], True, "；".join(errors) or "Keepa 未返回结果"
    note = "keepa"
    if errors:
        note += "；部分品类失败：" + "；".join(errors[:2])
    if token_estimate:
        note += f"；token 估算 {token_estimate['total_tokens_est']:g}"
    return rows, False, note


def _ebay_rows(
    categories: list[str],
    markets: list[str],
) -> tuple[list[dict[str, Any]], bool, str]:
    if not EBAY_APP_ID:
        return [], True, "skipped: 缺少 EBAY_APP_ID，已跳过真实请求"
    try:
        from ebaysdk.finding import Connection as FindingConnection
    except ImportError:
        return [], True, "ebaysdk 未安装，已跳过真实请求"

    connection = FindingConnection(
        appid=EBAY_APP_ID,
        devid=EBAY_DEV_ID or None,
        certid=EBAY_CERT_ID or None,
        config_file=None,
    )
    rows: list[dict[str, Any]] = []
    today = today_iso()
    errors: list[str] = []
    for index, category in enumerate(categories):
        keyword = category_name(category)
        market = markets[index % len(markets)]
        try:
            response = connection.execute(
                "findItemsAdvanced",
                {
                    "keywords": keyword,
                    "sortOrder": "BestMatch",
                    "paginationInput": {"pageNumber": 1, "entriesPerPage": 5},
                },
            )
            items = response.reply.searchResult.item or []
            for rank, item in enumerate(items[:5], start=1):
                rows.append(
                    {
                        "date": today,
                        "category": category,
                        "category_name": category_name(category),
                        "market": market,
                        "market_name": market_name(market),
                        "platform": "ebay",
                        "rank": rank,
                        "product": getattr(item, "title", "") or keyword,
                        "source": "ebay",
                        "fallback_used": False,
                    }
                )
        except Exception as exc:  # noqa: BLE001 - 单品类失败不阻塞整体
            errors.append(f"{category}: {exc}")
    if not rows:
        return [], True, "；".join(errors) or "eBay 未返回结果"
    note = "ebay"
    if errors:
        note += "；部分品类失败：" + "；".join(errors[:2])
    return rows, False, note


def _shopee_github_rows(
    categories: list[str],
    markets: list[str],
    *,
    signals_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Rank products from the free GitHub Shopee sample (SEA market).

    B-3 补数：Shopee 是东南亚电商平台，其 GitHub 免费样例为 sea 市场提供真实榜单证据
    （复用已构建的 github_signals.json 中 shopee_github 行，无需联网）。
    """
    from src.config import GITHUB_SIGNALS_JSON

    path = signals_path or GITHUB_SIGNALS_JSON
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows: list[dict[str, Any]] = []
    today = today_iso()
    signals = payload.get("rows") or []
    for category in categories:
        candidates = [
            item
            for item in signals
            if item.get("source_type") == "shopee_github"
            and item.get("category") == category
            and item.get("market") in markets
            and item.get("keyword") in ("liked_count", "rating_count", "comment_count", "rating_avg")
            and not item.get("fallback_used")
            and (item.get("value") or 0) > 0
        ]
        candidates.sort(key=lambda item: float(item.get("value") or 0.0), reverse=True)
        for rank, item in enumerate(candidates[:5], start=1):
            rows.append(
                {
                    "date": today,
                    "category": category,
                    "category_name": category_name(category),
                    "market": item["market"],
                    "market_name": market_name(item["market"]),
                    "platform": "shopee_github",
                    "rank": rank,
                    "product": str(item.get("title") or "")[:120] or f"{category_name(category)} Shopee 样例",
                    "source": "github/rebrowser/shopee-dataset",
                    "fallback_used": False,
                    "url": item.get("url") or "",
                    "rating_count": float(item.get("value") or 0.0),
                }
            )
    return rows


def _provider_rows(
    provider: str,
    categories: list[str],
    markets: list[str],
    offline: bool,
) -> tuple[list[dict[str, Any]], bool, str]:
    if provider == "mock":
        return _mock_rows(categories, markets, "mock"), True, "mock"
    if provider == "keepa":
        if offline:
            return [], True, "skipped: 离线模式，已跳过真实请求"
        return _keepa_rows(categories, markets)
    if provider == "ebay":
        if offline:
            return [], True, "skipped: 离线模式，已跳过真实请求"
        return _ebay_rows(categories, markets)
    if provider == "ebay_github":
        if offline:
            return [], True, "skipped: 离线模式，已跳过真实请求"
        try:
            rows = _ebay_github_rows(categories, markets)
        except Exception as exc:  # noqa: BLE001 - 样例缺失或解析失败统一跳过
            return [], True, f"skipped: {exc}"
        if not rows:
            return [], True, "ebay_github: 未匹配到当前品类/市场"
        return rows, False, "ebay_github（GitHub 免费样例，非实时）"
    if provider == "amazon_github":
        if offline:
            return [], True, "skipped: 离线模式，已跳过真实请求"
        try:
            rows = _amazon_github_rows(categories, markets)
        except Exception as exc:  # noqa: BLE001 - 样例缺失或解析失败统一跳过
            return [], True, f"skipped: {exc}"
        if not rows:
            return [], True, "amazon_github: 未匹配到当前品类/市场"
        return rows, False, "amazon_github（GitHub 免费样例，非实时）"
    if provider == "shopee_github":
        if offline:
            return [], True, "skipped: 离线模式，已跳过真实请求"
        try:
            rows = _shopee_github_rows(categories, markets)
        except Exception as exc:  # noqa: BLE001 - 样例缺失或解析失败统一跳过
            return [], True, f"skipped: {exc}"
        if not rows:
            return [], True, "shopee_github: 未匹配到当前品类/市场"
        return rows, False, "shopee_github（GitHub 免费样例，SEA 市场）"
    if provider == "amazon_bestsellers" and not offline:
        try:
            return _amazon_bestsellers_rows(categories, markets), False, "amazon_bestsellers"
        except RobotsDisallowedError as exc:
            return (
                [],
                True,
                f"skipped: robots.txt disallows amazon_bestsellers ({exc})",
            )
        except Exception as exc:  # noqa: BLE001 - 反爬/网络失败统一回退
            return _mock_rows(categories, markets, "amazon_mock"), True, str(exc)
    if provider == "amazon_bestsellers":
        return [], True, "skipped: 离线模式，已跳过真实请求"
    if provider == "tiktok_shop":
        return _mock_rows(categories, markets, "tiktok_mock"), True, "TikTok Shop 榜单暂为占位回退"
    return _mock_rows(categories, markets, provider), True, f"{provider} 回退 mock"


def collect_rankings(
    categories: list[str] | None = None,
    markets: list[str] | None = None,
    *,
    providers: list[str] | None = None,
    offline: bool = True,
) -> dict[str, Any]:
    """采集平台榜单，按配置的 provider 逐个执行并统一回退。"""
    categories = categories or list(CATEGORIES.keys())
    markets = markets or list(MARKETS.keys())
    providers = providers or PLATFORM_RANKING_PROVIDERS or ["mock"]

    rows: list[dict[str, Any]] = []
    provider_status: dict[str, dict[str, str]] = {}
    fallback_any = False
    for provider in providers:
        provider_rows, fallback, status = _provider_rows(
            provider,
            categories,
            markets,
            offline,
        )
        rows.extend(provider_rows)
        fallback_any = fallback_any or fallback
        if status.startswith("skipped:"):
            provider_status[provider] = {"status": "skipped", "note": status}
        else:
            provider_status[provider] = {
                "status": "fallback" if fallback else "ok",
                "note": status,
            }
    if not rows:
        rows = _mock_rows(categories, markets, "mock")
        fallback_any = True

    payload = {
        "generated_at": now_iso(),
        "date": today_iso(),
        "offline": bool(offline),
        "fallback_used": fallback_any,
        "providers": provider_status,
        "rows": rows,
        "source_count": len(rows),
    }
    return payload


def save_latest_rankings(payload: dict[str, Any]) -> Path:
    return save_latest(payload, PLATFORM_RANKINGS_LATEST_JSON)


def load_latest_rankings() -> dict[str, Any]:
    if not PLATFORM_RANKINGS_LATEST_JSON.exists():
        return empty_rankings_payload()
    try:
        payload = json.loads(PLATFORM_RANKINGS_LATEST_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_rankings_payload()
    payload.setdefault("rows", [])
    payload.setdefault("providers", [])
    return payload


def _source_level(payload: dict[str, Any]) -> str:
    """按 providers 状态计算来源层级：Keepa/官方源 > 官方免费样例 > 本地缓存 > 合成回退。

    B-2 降级机制：结论标注来源层级，供报告与 API 显式展示。
    """
    providers = payload.get("providers") or {}
    if not providers:
        return "无数据"
    ok = [
        (name, info)
        for name, info in providers.items()
        if isinstance(info, dict) and info.get("status") == "ok"
    ]
    if ok:
        names = [name for name, _ in ok]
        if any(name in ("keepa", "ebay") for name in names):
            return "实时官方源（Keepa/eBay API）"
        if any(name in ("amazon_github", "ebay_github") for name in names):
            return "官方免费样例（GitHub 本地缓存）"
        return "官方源（本地样例）"
    if any(
        isinstance(info, dict)
        and info.get("status") == "fallback"
        and "mock" not in str(info.get("note") or "").lower()
        for info in providers.values()
    ):
        return "降级（部分回退）"
    return "合成回退（mock）"


def rankings_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(payload.get("generated_at")),
        "updated_at": payload.get("generated_at"),
        "date": payload.get("date"),
        "fallback_used": bool(payload.get("fallback_used")),
        "offline": bool(payload.get("offline")),
        "providers": payload.get("providers"),
        "source_level": _source_level(payload),
        "rows": int(payload.get("source_count") or 0),
        "snapshot": "output/platform_rankings/latest.json",
    }


__all__ = [
    "collect_rankings",
    "empty_rankings_payload",
    "load_latest_rankings",
    "rankings_status",
    "save_latest_rankings",
]
