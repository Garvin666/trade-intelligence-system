"""Build a real-evidence feature bank from local datasets.

Raw Amazon/eBay/Shopee/Octaprice samples plus the existing trends,
platform-ranking, customs, crawler and validation snapshots are normalized
into numeric features that can be merged into the forecast training frame.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import (
    CRAWLER_LATEST_JSON,
    CUSTOMS_LATEST_JSON,
    GITHUB_DATA_DIR,
    OUTPUT_DIR,
    PLATFORM_RANKINGS_LATEST_JSON,
    PROCESSED_CSV,
    REAL_FEATURE_BANK_CSV,
    REAL_FEATURE_COLS,
    REAL_TRAINING_CSV,
    TRENDS_LATEST_JSON,
)
from src.data.github_datasets import map_category, map_market

SHOPEE_CURRENCY_MARKET = {
    "MYR": "sea",
    "SGD": "sea",
    "THB": "sea",
    "VND": "sea",
    "IDR": "sea",
    "PHP": "sea",
    "TWD": "sea",
}

PRODUCT_COLUMNS = [
    "provider",
    "category",
    "market",
    "date",
    "price",
    "rating",
    "reviews",
    "demand",
]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, np.ndarray):
        return json.dumps(value.tolist(), ensure_ascii=False)
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False)
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (list, dict, tuple, np.ndarray)):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "[PREMIUM]", "PREMIUM", "NAN", "NULL"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _date_text(value: Any) -> str:
    text = _safe_text(value)
    return text[:10] if len(text) >= 10 else ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _amazon_rows() -> list[dict[str, Any]]:
    path = GITHUB_DATA_DIR / "amazon" / "amazon-products.csv"
    if not path.exists():
        return []
    frame = pd.read_csv(path, low_memory=False)
    rows: list[dict[str, Any]] = []
    for item in frame.itertuples(index=False):
        title = _safe_text(item.title)
        category = map_category(
            title,
            _safe_text(item.categories),
            _safe_text(item.department),
            _safe_text(item.root_bs_category),
        )
        if category is None:
            continue
        market = map_market(_safe_text(item.domain)) or "us"
        rows.append(
            {
                "provider": "amazon",
                "category": category,
                "market": market,
                "date": _date_text(item.timestamp),
                "price": _safe_float(item.final_price) or _safe_float(item.initial_price),
                "rating": _safe_float(item.rating),
                "reviews": _safe_float(item.reviews_count),
                "demand": _safe_float(item.bought_past_month),
            }
        )
    return rows


def _ebay_rows() -> list[dict[str, Any]]:
    path = GITHUB_DATA_DIR / "ebay" / "eBay-dataset-sample.csv"
    if not path.exists():
        return []
    frame = pd.read_csv(path, low_memory=False)
    rows: list[dict[str, Any]] = []
    for item in frame.itertuples(index=False):
        title = _safe_text(item.title)
        category = map_category(
            title,
            _safe_text(item.root_category),
            _safe_text(item.breadcrumbs),
            _safe_text(item.popular_categories),
        )
        if category is None:
            continue
        market = map_market(
            _safe_text(item.item_location),
            _safe_text(item.currency),
            _safe_text(item.ships_to),
        ) or "us"
        reviews = _safe_float(item.item_reviews) or _safe_float(item.reviews_count)
        rows.append(
            {
                "provider": "ebay",
                "category": category,
                "market": market,
                "date": "",
                "price": _safe_float(item.price),
                "rating": _safe_float(item.seller_rating),
                "reviews": reviews,
                "demand": _safe_float(item.sold_count),
            }
        )
    return rows


def _shopee_rows() -> list[dict[str, Any]]:
    provider_dir = GITHUB_DATA_DIR / "shopee" / "product-details" / "data"
    if not provider_dir.exists():
        return []
    frames: list[pd.DataFrame] = []
    for path in sorted(provider_dir.glob("*.parquet")):
        frames.append(pd.read_parquet(path))
    if not frames:
        return []
    frame = pd.concat(frames, ignore_index=True)
    rows: list[dict[str, Any]] = []
    for item in frame.to_dict("records"):
        title = _safe_text(item.get("title"))
        category = map_category(title, _safe_text(item.get("categories")))
        if category is None:
            continue
        currency = _safe_text(item.get("currency")).upper()
        market = SHOPEE_CURRENCY_MARKET.get(currency)
        if market is None:
            market = map_market(_safe_text(item.get("shopLocation")), currency) or "us"
        rows.append(
            {
                "provider": "shopee",
                "category": category,
                "market": market,
                "date": _date_text(item.get("_lastSeenAt")) or _date_text(item.get("createdAt")),
                "price": _safe_float(item.get("price")),
                "rating": _safe_float(item.get("ratingAvg")),
                "reviews": _safe_float(item.get("commentCount")),
                "demand": _safe_float(item.get("likedCount")),
            }
        )
    return rows


def _octaprice_rows() -> list[dict[str, Any]]:
    path = GITHUB_DATA_DIR / "octaprice" / "amazon_com_bird_food_2025_01_24.csv"
    if not path.exists():
        return []
    frame = pd.read_csv(path, low_memory=False)
    rows: list[dict[str, Any]] = []
    for item in frame.itertuples(index=False):
        name = _safe_text(item.name)
        category = map_category(name, _safe_text(item.breadcrumbs))
        if category is None:
            continue
        market = map_market(_safe_text(item.url), _safe_text(item.sellerName)) or "us"
        rows.append(
            {
                "provider": "octaprice",
                "category": category,
                "market": market,
                "date": _date_text(item.scrapedDate),
                "price": _safe_float(item.salePrice) or _safe_float(item.listedPrice),
                "rating": _safe_float(item.rating),
                "reviews": _safe_float(item.reviewCount),
                "demand": None,
            }
        )
    return rows


def build_product_rows() -> pd.DataFrame:
    """Normalize raw product samples into a common long table."""
    rows: list[dict[str, Any]] = []
    rows.extend(_amazon_rows())
    rows.extend(_ebay_rows())
    rows.extend(_shopee_rows())
    rows.extend(_octaprice_rows())
    frame = pd.DataFrame(rows, columns=PRODUCT_COLUMNS)
    for column in ("price", "rating", "reviews", "demand"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _product_static_features(products: pd.DataFrame | None = None) -> pd.DataFrame:
    products = products if products is not None else build_product_rows()
    valid = products.dropna(subset=["category", "market"]).copy()
    if valid.empty:
        return pd.DataFrame(columns=["category", "market", "real_price_median", "real_rating_median", "real_reviews_median", "real_demand_median"])
    grouped = (
        valid.groupby(["category", "market"], as_index=False)
        .agg(
            real_price_median=("price", "median"),
            real_rating_median=("rating", "median"),
            real_reviews_median=("reviews", "median"),
            real_demand_median=("demand", "median"),
        )
    )
    return grouped


def _trend_date_features() -> pd.DataFrame:
    payload = _read_json(TRENDS_LATEST_JSON)
    rows = [
        {"category": row.get("category"), "market": row.get("market"), "date": str(row.get("date") or "")[:10], "value": _safe_float(row.get("value"))}
        for row in payload.get("rows") or []
        if isinstance(row, dict) and _safe_float(row.get("value")) is not None
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["category", "market", "date", "real_trend_value"])
    return (
        frame.groupby(["category", "market", "date"], as_index=False)["value"]
        .median()
        .rename(columns={"value": "real_trend_value"})
    )


def _ranking_date_features() -> pd.DataFrame:
    payload = _read_json(PLATFORM_RANKINGS_LATEST_JSON)
    rows = [
        {
            "category": row.get("category"),
            "market": row.get("market"),
            "date": str(row.get("date") or "")[:10],
            "rank": _safe_float(row.get("rank")),
        }
        for row in payload.get("rows") or []
        if isinstance(row, dict)
        and not bool(row.get("fallback_used"))
        and _safe_float(row.get("rank")) is not None
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["category", "market", "date", "real_rank_avg"])
    frame = frame.dropna(subset=["rank"])
    if frame.empty:
        return pd.DataFrame(columns=["category", "market", "date", "real_rank_avg"])
    return (
        frame.groupby(["category", "market", "date"], as_index=False)["rank"]
        .mean()
        .rename(columns={"rank": "real_rank_avg"})
    )


def _customs_static_features() -> pd.DataFrame:
    payload = _read_json(CUSTOMS_LATEST_JSON)
    rows = [
        {"category": row.get("category"), "value": _safe_float(row.get("value"))}
        for row in payload.get("rows") or []
        if isinstance(row, dict) and _safe_float(row.get("value")) is not None
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["category", "real_customs_export"])
    frame = frame.dropna(subset=["value"])
    if frame.empty:
        return pd.DataFrame(columns=["category", "real_customs_export"])
    return (
        frame.groupby("category", as_index=False)["value"]
        .median()
        .rename(columns={"value": "real_customs_export"})
    )


def _crawler_static_features() -> pd.DataFrame:
    payload = _read_json(CRAWLER_LATEST_JSON)
    rows = [
        {"category": row.get("category"), "market": row.get("market"), "value": _safe_float(row.get("pageview_trend_pct"))}
        for row in payload.get("combos") or []
        if isinstance(row, dict) and not bool(row.get("fallback_used"))
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["category", "market", "real_crawler_trend_pct"])
    frame = frame.dropna(subset=["value"])
    if frame.empty:
        return pd.DataFrame(columns=["category", "market", "real_crawler_trend_pct"])
    return (
        frame.groupby(["category", "market"], as_index=False)["value"]
        .median()
        .rename(columns={"value": "real_crawler_trend_pct"})
    )


def _evidence_static_features() -> pd.DataFrame:
    validation = _read_json(OUTPUT_DIR / "real" / "validation.json")
    rows = [
        {"category": row.get("category"), "market": row.get("market"), "score": _safe_float(row.get("evidence_score"))}
        for row in validation.get("rows") or []
        if isinstance(row, dict)
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["category", "market", "real_evidence_score"])
    frame = frame.dropna(subset=["score"])
    if frame.empty:
        return pd.DataFrame(columns=["category", "market", "real_evidence_score"])
    return (
        frame.groupby(["category", "market"], as_index=False)["score"]
        .median()
        .rename(columns={"score": "real_evidence_score"})
    )


def build_real_feature_bank() -> pd.DataFrame:
    """Build one row per category/market with static real-evidence features."""
    bank = _product_static_features()
    date_columns = {"real_trend_value", "real_rank_avg"}
    for frame, keys in (
        (_customs_static_features(), ["category"]),
        (_crawler_static_features(), ["category", "market"]),
        (_evidence_static_features(), ["category", "market"]),
    ):
        if frame.empty:
            continue
        bank = bank.merge(frame, on=keys, how="left")
    for column in REAL_FEATURE_COLS:
        if column not in bank.columns and column not in date_columns:
            bank[column] = np.nan
    return bank


def _safe_median(series: pd.Series) -> float:
    """median with empty-slice protection: all-NaN series -> 0.0."""
    if series.notna().any():
        return float(series.median())
    return 0.0


def _fill_real_features(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if "date" in frame.columns:
        frame = frame.sort_values(["category", "market", "date"]).reset_index(drop=True)
    for column in REAL_FEATURE_COLS:
        if column not in frame.columns:
            frame[column] = np.nan
    date_columns = {"real_trend_value", "real_rank_avg"}
    for column in date_columns:
        group_median = (
            frame.groupby(["category", "market"], observed=True)[column]
            .transform("median")
            if frame[column].notna().any()
            else pd.Series(0.0, index=frame.index)
        )
        frame[column] = (
            frame.groupby(["category", "market"], observed=True)[column]
            .ffill()
            .fillna(group_median)
            .fillna(_safe_median(frame[column]))
            .fillna(0.0)
        )
    for column in REAL_FEATURE_COLS:
        if column in date_columns:
            continue
        if frame[column].notna().any():
            frame[column] = (
                frame.groupby(["category", "market"], observed=True)[column]
                .transform("median")
                .fillna(_safe_median(frame[column]))
                .fillna(0.0)
            )
        else:
            frame[column] = 0.0
    return frame


def augment_clean_data(
    clean_df: pd.DataFrame,
    feature_bank: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge real features into the clean training frame."""
    frame = clean_df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    bank = feature_bank if feature_bank is not None else build_real_feature_bank()
    if not bank.empty:
        static_columns = [
            column
            for column in REAL_FEATURE_COLS
            if column in bank.columns and column not in {"real_trend_value", "real_rank_avg"}
        ]
        static = bank[["category", "market"] + static_columns]
        frame = frame.merge(static, on=["category", "market"], how="left")
    trend = _trend_date_features()
    rankings = _ranking_date_features()
    if not trend.empty:
        trend = trend.copy()
        trend["date"] = pd.to_datetime(trend["date"])
        frame = frame.merge(trend, on=["category", "market", "date"], how="left")
    if not rankings.empty:
        rankings = rankings.copy()
        rankings["date"] = pd.to_datetime(rankings["date"])
        frame = frame.merge(rankings, on=["category", "market", "date"], how="left")
    return _fill_real_features(frame)


def write_real_training_files(
    clean_df: pd.DataFrame,
    feature_bank: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Persist the feature bank and the augmented training frame."""
    bank = feature_bank if feature_bank is not None else build_real_feature_bank()
    augmented = augment_clean_data(clean_df, feature_bank=bank)
    REAL_FEATURE_BANK_CSV.parent.mkdir(parents=True, exist_ok=True)
    REAL_TRAINING_CSV.parent.mkdir(parents=True, exist_ok=True)
    bank.to_csv(REAL_FEATURE_BANK_CSV, index=False, encoding="utf-8-sig")
    augmented.to_csv(REAL_TRAINING_CSV, index=False, encoding="utf-8-sig")
    return augmented, bank


def load_real_training_frame() -> pd.DataFrame:
    """Load the augmented training frame, falling back to plain clean data."""
    if REAL_TRAINING_CSV.exists():
        frame = pd.read_csv(REAL_TRAINING_CSV, encoding="utf-8-sig")
        frame["date"] = pd.to_datetime(frame["date"])
        return frame
    frame = pd.read_csv(PROCESSED_CSV, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"])
    return augment_clean_data(frame)


__all__ = [
    "REAL_FEATURE_COLS",
    "augment_clean_data",
    "build_product_rows",
    "build_real_feature_bank",
    "load_real_training_frame",
    "write_real_training_files",
]
