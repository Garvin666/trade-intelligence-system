"""Normalize public GitHub datasets into the control-group signal layer.

The layer only adds evidence on top of the synthetic control data; it never
replaces train/holdout labels. Missing source files are treated as hard errors.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    CATEGORIES,
    GITHUB_DATA_DIR,
    GITHUB_MAX_ROWS_PER_PROVIDER,
    GITHUB_REAL_RESULTS_CSV,
    GITHUB_SIGNALS_JSON,
)
from src.trade.hs_code import CATEGORY_HS_CODES

ENABLED_PROVIDERS = ("amazon", "ebay", "shopee", "octaprice", "hs")

PROVIDER_INFO = {
    "amazon": {
        "label": "Amazon",
        "source_url": "https://github.com/luminati-io/Amazon-dataset-samples",
        "license": "Bright Data sample; free sample, full dataset is commercial",
    },
    "ebay": {
        "label": "eBay",
        "source_url": "https://github.com/luminati-io/eBay-dataset-sample",
        "license": "Bright Data sample; free sample, full dataset is commercial",
    },
    "shopee": {
        "label": "Shopee",
        "source_url": "https://github.com/rebrowser/shopee-dataset",
        "license": "Free for research/non-commercial use with attribution",
    },
    "octaprice": {
        "label": "Octaprice",
        "source_url": "https://github.com/octaprice/ecommerce-product-dataset",
        "license": "Free for academic, research, and journalistic purposes",
    },
    "hs": {
        "label": "HS Code",
        "source_url": "https://github.com/datasets/harmonized-system",
        "license": "Public domain data packaged from UN Comtrade/WCO",
    },
}

REAL_RESULTS_COLUMNS = [
    "source_type",
    "category",
    "market",
    "keyword",
    "value",
    "provider",
    "fallback_used",
    "url",
    "date",
]

_CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    # 食品 SKU -> 外部商品文本关键词（子串匹配，dict 顺序即优先序，具体在前）
    "cn_tea_egg": ("tea egg", "茶叶蛋"),
    "cn_latiao": ("latiao", "spicy snack", "spicy strip", "辣条"),
    "cn_changsha_mifen": ("changsha rice noodle", "changsha", "长沙米粉", "米线"),
    "cn_guilin_mifen": ("guilin rice noodle", "guilin", "桂林米粉"),
    "cn_handmade_noodles": ("handmade noodle", "wheat noodle", "instant noodle", "挂面", "方便面"),
    "cn_beef_jerky": ("beef jerky", "jerky", "牛肉干", "肉干"),
    "cn_frozen_dumplings": ("frozen dumpling", "dumpling", "速冻水饺", "水饺", "饺子"),
    "cn_laoganma": ("laoganma", "chili sauce", "老干妈", "辣椒酱"),
    "cn_dried_chili": ("dried chili", "chili pepper", "干辣椒"),
    "cn_spicy_gluten": ("spicy gluten", "seitan", "面筋"),
    "cn_longjing": ("longjing", "green tea", "dragon well", "龙井", "绿茶", "茶叶"),
    "cn_pixian_doubanjiang": ("doubanjiang", "pixian", "bean paste", "豆瓣酱"),
    "cn_green_bean_cake": ("mung bean cake", "green bean cake", "绿豆糕"),
    "cn_xiaomi_zhou": ("millet porridge", "小米粥", "congee"),
    "cn_salted_duck_egg": ("salted duck egg", "咸鸭蛋"),
    "cn_sichuan_sausage": ("sichuan sausage", "sausage", "川味香肠", "香肠"),
    "cn_shrimp_paste": ("shrimp paste", "虾酱"),
    "cn_guaiwei_dou": ("broad bean", "fava", "怪味豆", "蚕豆"),
    "cn_dried_seaweed": ("seaweed", "nori", "紫菜", "海苔"),
    "intl_salmon_fillet": ("salmon", "fish fillet", "三文鱼"),
    "intl_canned_tuna": ("canned tuna", "tuna", "金枪鱼"),
    "intl_firm_tofu": ("tofu", "豆腐"),
    "intl_hummus": ("hummus", "chickpea", "鹰嘴豆"),
    "intl_pasta": ("pasta", "spaghetti", "意大利面"),
    "intl_oats": ("oats", "oatmeal", "rolled oats", "燕麦"),
    "intl_cheddar": ("cheddar", "cheese", "奶酪"),
    "intl_greek_yogurt": ("yogurt", "酸奶"),
    "intl_frozen_pizza": ("frozen pizza", "pizza", "披萨"),
    "intl_ramen_japan": ("ramen", "日式拉面", "拉面"),
    "intl_quinoa": ("quinoa", "藜麦"),
    "intl_pepperoni": ("pepperoni", "salami", "萨拉米"),
    "intl_prosciutto": ("prosciutto", "帕尔玛火腿"),
    "intl_mozzarella": ("mozzarella", "马苏里拉"),
    "cn_bajiang_mian": ("eight treasure congee", "八宝粥"),
    "cn_century_egg": ("century egg", "preserved egg", "松花蛋", "皮蛋"),
}

_MARKET_TERMS: dict[str, tuple[str, ...]] = {
    "us": ("united states", "美国", "usa", "amazon.com"),
    "eu": ("europe", "欧洲", "欧盟", "euro"),
    "sea": (
        "southeast asia",
        "东南亚",
        "singapore",
        "malaysia",
        "thailand",
        "vietnam",
        "indonesia",
        "philippines",
        "taiwan",
        "新加坡",
        "马来西亚",
        "泰国",
        "越南",
        "印度尼西亚",
        "菲律宾",
        "台湾",
    ),
    "jp": ("japan", "日本", "amazon.co.jp"),
    "ca": ("canada", "加拿大"),
    "au": ("australia", "澳大利亚", "澳洲"),
    "uk": ("united kingdom", "英国", "amazon.co.uk"),
    "kr": ("korea", "韩国"),
    "de": ("germany", "德国", "amazon.de"),
    "fr": ("france", "法国", "amazon.fr"),
    "vn": ("vietnam", "越南"),
    "ru": ("russia", "俄罗斯"),
    "hu": ("hungary", "匈牙利"),
    "ae": ("united arab emirates", "阿联酋", "中东"),
    "mx": ("mexico", "墨西哥"),
}

_SHOPEE_CURRENCY_MARKET = {
    "MYR": "sea",
    "SGD": "sea",
    "THB": "sea",
    "VND": "sea",
    "IDR": "sea",
    "PHP": "sea",
    "TWD": "sea",
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False)
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "[PREMIUM]", "PREMIUM", "NAN"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def map_category(*parts: Any) -> str | None:
    text = " ".join(_safe_text(p) for p in parts).lower()
    for code, terms in _CATEGORY_TERMS.items():
        for term in terms:
            if term.lower() in text:
                return code
    return None


def map_market(*parts: Any) -> str | None:
    text = " ".join(_safe_text(p) for p in parts).lower()
    for code, terms in _MARKET_TERMS.items():
        for term in terms:
            if term.lower() in text:
                return code
    return None


def _signal_row(
    source_type: str,
    category: str,
    market: str,
    keyword: str,
    value: Any,
    title: str,
    url: str,
    provider: str,
    date: str,
) -> dict[str, Any] | None:
    numeric = _safe_float(value)
    if numeric is None:
        return None
    return {
        "source_type": source_type,
        "category": category,
        "market": market,
        "keyword": keyword,
        "value": numeric,
        "title": _safe_text(title)[:160],
        "url": _safe_text(url),
        "provider": provider,
        "fallback_used": False,
        "date": _safe_text(date),
    }


def _provider_dir(base_dir: Path, provider: str) -> Path:
    return base_dir / provider


def _list_files(provider_dir: Path, extensions: tuple[str, ...]) -> list[Path]:
    return sorted(
        path
        for path in provider_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in extensions
    )


def _load_raw(provider: str, base_dir: Path) -> pd.DataFrame:
    provider_dir = _provider_dir(base_dir, provider)
    if provider == "shopee":
        files = _list_files(provider_dir, (".parquet",))
        if not files:
            raise FileNotFoundError(f"缺少 Shopee parquet 文件: {provider_dir}")
        frames = [pd.read_parquet(path) for path in files]
        return pd.concat(frames, ignore_index=True)
    if provider == "hs":
        files = _list_files(provider_dir, (".csv",))
        if not files:
            raise FileNotFoundError(f"缺少 HS 数据文件: {provider_dir}")
        return pd.concat(
            [pd.read_csv(path) for path in files if "harmonized-system" in path.name],
            ignore_index=True,
        )
    files = _list_files(provider_dir, (".csv",))
    if not files:
        raise FileNotFoundError(f"缺少 {provider} CSV 文件: {provider_dir}")
    return pd.concat(
        [pd.read_csv(path) for path in files],
        ignore_index=True,
    )


def _normalize_amazon(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    for _, item in frame.iterrows():
        title = _safe_text(item.get("title"))
        category_text = " ".join(
            _safe_text(item.get(col))
            for col in ("categories", "root_bs_category", "department", "bs_category")
        )
        category = map_category(title, category_text)
        if category is None:
            skipped += 1
            continue
        domain = _safe_text(item.get("domain"))
        market = map_market(domain) or "us"
        url = _safe_text(item.get("url"))
        date = _safe_text(item.get("timestamp")) or _safe_text(item.get("date_first_available"))
        provider = "github/luminati-io/Amazon-dataset-samples"
        for keyword, field in (
            ("root_bs_rank", "root_bs_rank"),
            ("final_price", "final_price"),
            ("reviews_count", "reviews_count"),
            ("rating", "rating"),
            ("bought_past_month", "bought_past_month"),
        ):
            row = _signal_row(
                "amazon_github",
                category,
                market,
                keyword,
                item.get(field),
                title,
                url,
                provider,
                date,
            )
            if row is not None:
                rows.append(row)
    return rows, skipped


def _normalize_ebay(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    for _, item in frame.iterrows():
        title = _safe_text(item.get("title"))
        category_text = " ".join(
            _safe_text(item.get(col))
            for col in ("root_category", "breadcrumbs", "popular_categories")
        )
        category = map_category(title, category_text)
        if category is None:
            skipped += 1
            continue
        market = map_market(
            _safe_text(item.get("item_location")),
            _safe_text(item.get("currency")),
            _safe_text(item.get("ships_to")),
        ) or "us"
        url = _safe_text(item.get("url"))
        provider = "github/luminati-io/eBay-dataset-sample"
        for keyword, field in (
            ("sold_count", "sold_count"),
            ("price", "price"),
            ("seller_rating", "seller_rating"),
            ("item_reviews", "item_reviews"),
            ("reviews_count", "reviews_count"),
        ):
            row = _signal_row(
                "ebay_github",
                category,
                market,
                keyword,
                item.get(field),
                title,
                url,
                provider,
                "",
            )
            if row is not None:
                rows.append(row)
    return rows, skipped


def _normalize_shopee(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    for _, item in frame.iterrows():
        currency = _safe_text(item.get("currency")).upper()
        market = _SHOPEE_CURRENCY_MARKET.get(currency)
        if market is None:
            skipped += 1
            continue
        title = _safe_text(item.get("title"))
        category = map_category(title, _safe_text(item.get("categories")))
        if category is None:
            skipped += 1
            continue
        url = _safe_text(item.get("productUrl"))
        if url.upper() == "[PREMIUM]":
            url = ""
        date = (
            _safe_text(item.get("_lastSeenAt"))
            or _safe_text(item.get("_firstSeenAt"))
            or _safe_text(item.get("createdAt"))
        )
        provider = "github/rebrowser/shopee-dataset"
        for keyword, field in (
            ("rating_avg", "ratingAvg"),
            ("rating_count", "ratingCount"),
            ("comment_count", "commentCount"),
            ("liked_count", "likedCount"),
        ):
            row = _signal_row(
                "shopee_github",
                category,
                market,
                keyword,
                item.get(field),
                title,
                url,
                provider,
                date,
            )
            if row is not None:
                rows.append(row)
    return rows, skipped


def _normalize_octaprice(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    for _, item in frame.iterrows():
        name = _safe_text(item.get("name"))
        category = map_category(name, _safe_text(item.get("breadcrumbs")))
        if category is None:
            skipped += 1
            continue
        url = _safe_text(item.get("url"))
        market = map_market(url, _safe_text(item.get("sellerName"))) or "us"
        provider = "github/octaprice/ecommerce-product-dataset"
        date = _safe_text(item.get("scrapedDate"))
        for keyword, field in (
            ("sale_price", "salePrice"),
            ("listed_price", "listedPrice"),
            ("rating", "rating"),
            ("review_count", "reviewCount"),
        ):
            row = _signal_row(
                "octaprice_github",
                category,
                market,
                keyword,
                item.get(field),
                name,
                url,
                provider,
                date,
            )
            if row is not None:
                rows.append(row)
    return rows, skipped


def _normalize_hs(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    by_code: dict[str, str] = {}
    for _, item in frame.iterrows():
        code = _safe_text(item.get("hscode"))
        if not code:
            continue
        by_code.setdefault(code, _safe_text(item.get("description")))
    for category, entry in CATEGORY_HS_CODES.items():
        target = str(entry["code"])
        matched = [code for code in by_code if code.startswith(target) or target.startswith(code)]
        if not matched:
            skipped += 1
            continue
        row = _signal_row(
            "hs_github",
            category,
            "",
            "hs_code",
            int(matched[0]),
            entry["description"],
            PROVIDER_INFO["hs"]["source_url"],
            PROVIDER_INFO["hs"]["source_url"],
            "",
        )
        if row is not None:
            rows.append(row)
    return rows, skipped


_NORMALIZERS = {
    "amazon": _normalize_amazon,
    "ebay": _normalize_ebay,
    "shopee": _normalize_shopee,
    "octaprice": _normalize_octaprice,
    "hs": _normalize_hs,
}


def _cap_rows(rows: list[dict[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    """按 (品类, 市场) 组合分别截断（B-3 补数修复）。

    旧的全局排序截断会让字母序靠前的品类占满名额（如 electronics 被挤到 0 行），
    改为每组合最多 max_rows 行，保证各品类/市场覆盖均衡；行内按字段稳定排序。
    """
    if max_rows <= 0:
        return []
    capped: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["category"], row["market"]), []).append(row)
    for key in sorted(groups):
        group = groups[key]
        group = sorted(
            group,
            key=lambda row: (
                row["keyword"],
                str(row.get("title") or ""),
            ),
        )
        capped.extend(group[:max_rows])
    return capped


def build_github_signals(
    base_dir: Path | None = None,
    output_path: Path | None = None,
    max_rows_per_provider: int | None = None,
) -> dict[str, Any]:
    base_dir = base_dir or GITHUB_DATA_DIR
    output_path = output_path or GITHUB_SIGNALS_JSON
    max_rows_per_provider = max_rows_per_provider or GITHUB_MAX_ROWS_PER_PROVIDER
    payload_rows: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}

    for provider in ENABLED_PROVIDERS:
        frame = _load_raw(provider, base_dir)
        normalize = _NORMALIZERS[provider]
        rows, skipped = normalize(frame)
        capped = _cap_rows(rows, max_rows_per_provider)
        if not capped:
            raise RuntimeError(
                f"{provider} 映射后为空（mapped_rows=0），请检查 data/external/github/{provider} 原始文件"
            )
        raw_count = int(len(frame))
        sources[provider] = {
            "status": "ready",
            "label": PROVIDER_INFO[provider]["label"],
            "source_url": PROVIDER_INFO[provider]["source_url"],
            "license": PROVIDER_INFO[provider]["license"],
            "raw_rows": raw_count,
            "mapped_rows": len(capped),
            "skipped_rows": int(skipped),
            "max_rows_per_provider": max_rows_per_provider,
        }
        payload_rows.extend(capped)

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": sources,
        "rows": payload_rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def load_github_signals(path: Path | None = None) -> dict[str, Any]:
    path = path or GITHUB_SIGNALS_JSON
    if not path.exists():
        return {"generated_at": None, "sources": {}, "rows": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"generated_at": None, "sources": {}, "rows": []}


def github_real_result_rows(
    payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    payload = payload or load_github_signals()
    rows: list[dict[str, Any]] = []
    for item in payload.get("rows") or []:
        rows.append(
            {
                "source_type": item.get("source_type", ""),
                "category": item.get("category", ""),
                "market": item.get("market", ""),
                "keyword": item.get("keyword", ""),
                "value": item.get("value"),
                "provider": item.get("provider", ""),
                "fallback_used": bool(item.get("fallback_used", False)),
                "url": item.get("url", ""),
                "date": item.get("date", ""),
            }
        )
    return rows


def build_github_real_results(
    output_path: Path | None = None,
    payload: dict[str, Any] | None = None,
) -> Path:
    output_path = output_path or GITHUB_REAL_RESULTS_CSV
    rows = github_real_result_rows(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=REAL_RESULTS_COLUMNS)
    frame.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def signal_summary(
    combos: list[tuple[str, str]] | None = None,
    max_rows: int = 40,
    payload: dict[str, Any] | None = None,
) -> str:
    payload = payload or load_github_signals()
    sources = payload.get("sources") or {}
    rows = payload.get("rows") or []
    combo_set = {tuple(c) for c in combos} if combos else None
    if combo_set is not None:
        rows = [
            row
            for row in rows
            if (row.get("category"), row.get("market")) in combo_set
        ]
    if not rows and not sources:
        return ""

    lines = [
        "## 真实平台信号（GitHub 公开样例，仅辅助洞察，不作为预测目标）",
        "",
        "### 来源覆盖",
        "",
        "| 来源 | 原始行数 | 已映射行数 | 未映射行数 |",
        "|---|---|---|---|",
    ]
    for provider in ENABLED_PROVIDERS:
        info = sources.get(provider) or {}
        lines.append(
            f"| {info.get('label', provider)} | {info.get('raw_rows', '-')} "
            f"| {info.get('mapped_rows', '-')} | {info.get('skipped_rows', '-')} |"
        )
    lines.extend(["", "### 与本次组合相关的样例", ""])
    lines.append(
        "| 来源 | 品类 | 市场 | 指标 | 数值 | 链接 |"
    )
    lines.append("|---|---|---|---|---|---|")
    selected = rows[:max_rows]
    for row in selected:
        lines.append(
            f"| {row.get('source_type', '')} | {row.get('category', '')} "
            f"| {row.get('market', '')} | {row.get('keyword', '')} "
            f"| {row.get('value', '')} | {row.get('url', '')} |"
        )
    lines.extend(
        [
            "",
            "真实信号只作为背景证据；预测标签仍以 train_data.csv 的 sales_volume 为准。",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "ENABLED_PROVIDERS",
    "PROVIDER_INFO",
    "REAL_RESULTS_COLUMNS",
    "build_github_real_results",
    "build_github_signals",
    "github_real_result_rows",
    "load_github_signals",
    "map_category",
    "map_market",
    "signal_summary",
]
