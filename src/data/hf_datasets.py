"""Normalize Hugging Face public datasets into the control-group signal layer.

Layer mirrors ``src/data/github_datasets.py``: it only adds evidence on top of
the synthetic control data; it never replaces train/holdout labels. Missing
source files are treated as hard errors.

Providers (downloaded to ``data/external/hf/<provider>/``):

- ``ecom_classification``: 31,851 English product descriptions / 33 e-commerce
  categories (CC BY-4.0), train/test/validation parquet.
- ``ecom_reviews_sentiment``: Indonesian e-commerce reviews with sentiment
  labels (11,606 rows), JSON.
- ``amazon_polarity``: ~3.6M Amazon reviews with positive/negative labels
  (Apache-2.0), parquet shards.
- ``amazon_products_2023``: Amazon product listings 2023 (MIT), arrow shards.
- ``m5_forecasting``: M5 retail sales forecasting benchmark CSVs (calendar,
  sell prices, daily sales matrix).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    HF_DATA_DIR,
    HF_MAX_ROWS_PER_PROVIDER,
    HF_REAL_RESULTS_CSV,
    HF_SIGNALS_JSON,
)
from src.data.github_datasets import map_category, map_market

ENABLED_PROVIDERS = (
    "ecom_classification",
    "ecom_reviews_sentiment",
    "amazon_polarity",
    "amazon_products_2023",
    "m5_forecasting",
)

PROVIDER_INFO = {
    "ecom_classification": {
        "label": "E-Commerce Product Classification (HF)",
        "source_url": "https://huggingface.co/datasets/Lezh1n/ecommerce-product-classification-by-categories",
        "license": "CC BY-4.0",
    },
    "ecom_reviews_sentiment": {
        "label": "E-Commerce Reviews Sentiment (HF)",
        "source_url": "https://huggingface.co/datasets/dipawidia/ecommerce-product-reviews-sentiment",
        "license": "unknown",
    },
    "amazon_polarity": {
        "label": "Amazon Polarity Reviews (HF)",
        "source_url": "https://huggingface.co/datasets/fancyzhx/amazon_polarity",
        "license": "Apache-2.0",
    },
    "amazon_products_2023": {
        "label": "AMAZON-Products-2023 (HF)",
        "source_url": "https://huggingface.co/datasets/milistu/AMAZON-Products-2023",
        "license": "MIT",
    },
    "m5_forecasting": {
        "label": "M5 Forecasting (HF)",
        "source_url": "https://huggingface.co/datasets/denephew/M5_Forecasting",
        "license": "CC (benchmark data)",
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

# ecom_classification labels (snake_case) -> project category codes（食品口径）
# 仅保留食品大类标签；非食品标签置 None，改由 map_category 文本兜底或直接跳过。
_ECOM_LABEL_TO_CATEGORY = {
    "grocery_food": "cn_latiao",
    "kitchen_dining": None,
    "health_wellness": None,
    "beauty_personal_care": None,
    "none": None,
    "books_media": None,
    "industrial_commercial": None,
}

# M5 category ids -> project category codes（食品口径）
# HOBBIES / HOUSEHOLD 属非食品，不再映射（未命中即跳过）。
_M5_CAT_TO_CATEGORY = {
    "FOODS": "cn_laoganma",
}
_M5_STATE_TO_MARKET = {
    "CA": "us",
    "TX": "us",
    "WI": "us",
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


def _load_parquet_concat(files: list[Path]) -> pd.DataFrame:
    frames = [pd.read_parquet(path) for path in files]
    return pd.concat(frames, ignore_index=True)


def _load_raw(provider: str, base_dir: Path) -> pd.DataFrame:
    provider_dir = _provider_dir(base_dir, provider)
    if not provider_dir.exists():
        raise FileNotFoundError(f"缺少 HF 数据目录: {provider_dir}")

    if provider == "ecom_classification":
        files = _list_files(provider_dir, (".parquet",))
        if not files:
            raise FileNotFoundError(f"缺少 ecom_classification parquet 文件: {provider_dir}")
        return _load_parquet_concat(files)

    if provider == "amazon_polarity":
        files = _list_files(provider_dir, (".parquet",))
        if not files:
            raise FileNotFoundError(f"缺少 amazon_polarity parquet 文件: {provider_dir}")
        # 信号层只需比例统计：只读前 2 个分片（约 180 万行）避免加载全量 1GB
        files = files[:2]
        return _load_parquet_concat(files)

    if provider == "ecom_reviews_sentiment":
        files = _list_files(provider_dir, (".json",))
        if not files:
            raise FileNotFoundError(f"缺少 ecom_reviews_sentiment json 文件: {provider_dir}")
        rows: list[dict[str, Any]] = []
        for path in files:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                rows.extend(payload)
            elif isinstance(payload, dict):
                # 单条 JSON 对象视为一行。
                rows.append(payload)
        return pd.DataFrame(rows)

    if provider == "amazon_products_2023":
        files = _list_files(provider_dir, (".arrow", ".parquet"))
        if not files:
            raise FileNotFoundError(f"缺少 amazon_products_2023 arrow 文件: {provider_dir}")
        if files[0].suffix.lower() == ".arrow":
            try:
                frames = [pd.read_feather(path) for path in files]
                return pd.concat(frames, ignore_index=True)
            except Exception:  # noqa: BLE001 - arrow 读取失败属预期降级，改用 datasets 库解析
                # HF datasets arrow 文件带自定义头，需用 datasets 库读取
                from datasets import load_dataset

                ds = load_dataset(
                    "arrow",
                    data_files=[str(path) for path in files],
                    split="train",
                )
                frame = ds.to_pandas()
                drop_cols = [c for c in ("embeddings", "image", "features", "details") if c in frame.columns]
                if drop_cols:
                    frame = frame.drop(columns=drop_cols)
                return frame
        frames = [pd.read_parquet(path) for path in files]
        return pd.concat(frames, ignore_index=True)

    if provider == "m5_forecasting":
        sales_files = [
            p for p in _list_files(provider_dir, (".csv",)) if "sales_train" in p.name
        ]
        price_files = [
            p for p in _list_files(provider_dir, (".csv",)) if "sell_prices" in p.name
        ]
        if not sales_files or not price_files:
            raise FileNotFoundError(f"缺少 m5_forecasting csv 文件: {provider_dir}")
        sales = pd.concat(
            [pd.read_csv(path) for path in sales_files], ignore_index=True
        )
        prices = pd.concat(
            [pd.read_csv(path) for path in price_files], ignore_index=True
        )
        # 每个 item 有多个 wm_yr_wk 价格行；先按 item 求均价，避免 merge 笛卡尔积
        price_avg = prices.groupby(["store_id", "item_id"], as_index=False)["sell_price"].mean()
        return sales.merge(price_avg, on=["store_id", "item_id"], how="left")

    raise FileNotFoundError(f"未知 HF provider: {provider}")


def _normalize_ecom_classification(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    counts: dict[str, int] = {}
    for _, item in frame.iterrows():
        raw_label = _safe_text(item.get("label")).strip()
        category = _ECOM_LABEL_TO_CATEGORY.get(raw_label)
        if category is None:
            category = map_category(raw_label.replace("_", " "), _safe_text(item.get("text")))
        if category is None:
            skipped += 1
            continue
        counts[category] = counts.get(category, 0) + 1
    url = PROVIDER_INFO["ecom_classification"]["source_url"]
    for category, count in sorted(counts.items()):
        row = _signal_row(
            "hf_ecom_classification",
            category,
            "",
            "sample_count",
            count,
            f"{category} 样本数",
            url,
            "hf/Lezh1n/ecommerce-product-classification-by-categories",
            "",
        )
        if row is not None:
            rows.append(row)
    return rows, skipped


def _normalize_ecom_reviews_sentiment(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    by_category: dict[str, dict[str, float]] = {}
    for _, item in frame.iterrows():
        text = " ".join(
            _safe_text(item.get(col)) for col in ("review", "translate") if item.get(col)
        )
        category = map_category(text)
        if category is None:
            skipped += 1
            continue
        sentimen = _safe_float(item.get("sentimen"))
        if sentimen is None:
            skipped += 1
            continue
        agg = by_category.setdefault(category, {"count": 0.0, "sum": 0.0})
        agg["count"] += 1
        agg["sum"] += sentimen
    url = PROVIDER_INFO["ecom_reviews_sentiment"]["source_url"]
    for category, agg in sorted(by_category.items()):
        row = _signal_row(
            "hf_ecom_reviews_sentiment",
            category,
            "",
            "sentiment_mean",
            agg["sum"] / agg["count"],
            f"{category} 评论情感均值",
            url,
            "hf/dipawidia/ecommerce-product-reviews-sentiment",
            "",
        )
        if row is not None:
            rows.append(row)
    return rows, skipped


def _normalize_amazon_polarity(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    # 信号层只需比例统计；360 万行逐行匹配过慢，抽样代表性样本
    if len(frame) > 200_000:
        frame = frame.sample(n=200_000, random_state=42)
    rows: list[dict[str, Any]] = []
    skipped = 0
    by_category: dict[str, dict[str, float]] = {}
    for _, item in frame.iterrows():
        text = " ".join(
            _safe_text(item.get(col)) for col in ("title", "content") if item.get(col)
        )
        category = map_category(text)
        if category is None:
            skipped += 1
            continue
        label = _safe_float(item.get("label"))
        if label is None:
            skipped += 1
            continue
        agg = by_category.setdefault(category, {"count": 0.0, "sum": 0.0})
        agg["count"] += 1
        agg["sum"] += label
    url = PROVIDER_INFO["amazon_polarity"]["source_url"]
    for category, agg in sorted(by_category.items()):
        row = _signal_row(
            "hf_amazon_polarity",
            category,
            "us",
            "positive_ratio",
            agg["sum"] / agg["count"],
            f"{category} 好评占比",
            url,
            "hf/fancyzhx/amazon_polarity",
            "",
        )
        if row is not None:
            rows.append(row)
    return rows, skipped


def _normalize_amazon_products_2023(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    if len(frame) > 60_000:
        frame = frame.sample(n=60_000, random_state=42)
    rows: list[dict[str, Any]] = []
    skipped = 0
    title_col = "title" if "title" in frame.columns else ("name" if "name" in frame.columns else None)
    if title_col is None:
        raise FileNotFoundError("amazon_products_2023 缺少 title/name 列")
    for _, item in frame.iterrows():
        title = _safe_text(item.get(title_col))
        category = map_category(title, _safe_text(item.get("main_category")))
        if category is None:
            skipped += 1
            continue
        url = _safe_text(item.get("parent_asin"))
        if url:
            url = f"https://www.amazon.com/dp/{url}"
        date = _safe_text(item.get("date_first_available"))
        provider = "hf/milistu/AMAZON-Products-2023"
        for keyword, field in (
            ("price", "price"),
            ("rating", "average_rating"),
            ("reviews_count", "rating_number"),
        ):
            if field not in frame.columns:
                continue
            row = _signal_row(
                "hf_amazon_products_2023",
                category,
                "us",
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


def _normalize_m5_forecasting(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    day_cols = [c for c in frame.columns if c.startswith("d_") and c[2:].isdigit()]
    recent_cols = day_cols[-28:] if len(day_cols) >= 28 else day_cols
    by_key: dict[tuple[str, str], dict[str, float]] = {}
    for _, item in frame.iterrows():
        cat_id = _safe_text(item.get("cat_id")).upper()
        category = _M5_CAT_TO_CATEGORY.get(cat_id)
        if category is None:
            skipped += 1
            continue
        state_id = _safe_text(item.get("state_id")).upper()
        market = _M5_STATE_TO_MARKET.get(state_id, "us")
        price = _safe_float(item.get("sell_price"))
        recent_sales = 0.0
        for col in recent_cols:
            val = _safe_float(item.get(col))
            if val is not None:
                recent_sales += val
        key = (category, market)
        agg = by_key.setdefault(key, {"count": 0.0, "sales": 0.0, "price_sum": 0.0, "price_n": 0.0})
        agg["count"] += 1
        agg["sales"] += recent_sales
        if price is not None:
            agg["price_sum"] += price
            agg["price_n"] += 1
    url = PROVIDER_INFO["m5_forecasting"]["source_url"]
    for (category, market), agg in sorted(by_key.items()):
        avg_price = agg["price_sum"] / agg["price_n"] if agg["price_n"] else None
        row = _signal_row(
            "hf_m5_forecasting",
            category,
            market,
            "recent_28d_sales",
            agg["sales"],
            f"{category}/{market} M5 近 28 天销量",
            url,
            "hf/denephew/M5_Forecasting",
            "",
        )
        if row is not None:
            rows.append(row)
        if avg_price is not None:
            price_row = _signal_row(
                "hf_m5_forecasting",
                category,
                market,
                "avg_sell_price",
                avg_price,
                f"{category}/{market} M5 平均售价",
                url,
                "hf/denephew/M5_Forecasting",
                "",
            )
            if price_row is not None:
                rows.append(price_row)
    return rows, skipped


_NORMALIZERS = {
    "ecom_classification": _normalize_ecom_classification,
    "ecom_reviews_sentiment": _normalize_ecom_reviews_sentiment,
    "amazon_polarity": _normalize_amazon_polarity,
    "amazon_products_2023": _normalize_amazon_products_2023,
    "m5_forecasting": _normalize_m5_forecasting,
}


def _cap_rows(rows: list[dict[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    if max_rows <= 0:
        return []
    rows = sorted(
        rows,
        key=lambda row: (
            row["category"],
            row["market"],
            row["keyword"],
            str(row.get("title") or ""),
        ),
    )
    return rows[:max_rows]


def build_hf_signals(
    base_dir: Path | None = None,
    output_path: Path | None = None,
    max_rows_per_provider: int | None = None,
) -> dict[str, Any]:
    base_dir = base_dir or HF_DATA_DIR
    output_path = output_path or HF_SIGNALS_JSON
    max_rows_per_provider = max_rows_per_provider or HF_MAX_ROWS_PER_PROVIDER
    payload_rows: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}

    for provider in ENABLED_PROVIDERS:
        frame = _load_raw(provider, base_dir)
        normalize = _NORMALIZERS[provider]
        rows, skipped = normalize(frame)
        capped = _cap_rows(rows, max_rows_per_provider)
        if not capped:
            raise RuntimeError(
                f"{provider} 映射后为空（mapped_rows=0），请检查 data/external/hf/{provider} 原始文件"
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


def load_hf_signals(path: Path | None = None) -> dict[str, Any]:
    path = path or HF_SIGNALS_JSON
    if not path.exists():
        return {"generated_at": None, "sources": {}, "rows": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"generated_at": None, "sources": {}, "rows": []}


def hf_real_result_rows(
    payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    payload = payload or load_hf_signals()
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


def build_hf_real_results(
    output_path: Path | None = None,
    payload: dict[str, Any] | None = None,
) -> Path:
    output_path = output_path or HF_REAL_RESULTS_CSV
    rows = hf_real_result_rows(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=REAL_RESULTS_COLUMNS)
    frame.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def signal_summary(
    combos: list[tuple[str, str]] | None = None,
    max_rows: int = 40,
    payload: dict[str, Any] | None = None,
) -> str:
    payload = payload or load_hf_signals()
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
        "## Hugging Face 公开数据集信号（仅辅助洞察，不作为预测目标）",
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
    "build_hf_real_results",
    "build_hf_signals",
    "hf_real_result_rows",
    "load_hf_signals",
    "signal_summary",
]
