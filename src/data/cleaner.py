"""数据清洗：统一 Schema、去重、缺失值处理、类型校正。"""

from __future__ import annotations

import pandas as pd

from src.config import CATEGORIES, MARKETS, TARGET_COL

SCHEMA = [
    "date",
    "category",
    "market",
    "search_index",
    "bestseller_rank",
    "price_median",
    "review_growth",
    "export_value",
    "competition_index",
    "sales_volume",
]

NUMERIC_COLS = [
    "search_index",
    "bestseller_rank",
    "price_median",
    "review_growth",
    "export_value",
    "competition_index",
    "sales_volume",
]


def clean_market_data(df: pd.DataFrame) -> pd.DataFrame:
    """执行清洗流程并返回规范化的 DataFrame。"""
    if df.empty:
        raise ValueError("输入数据为空，无法清洗")

    cleaned = df.copy()

    # 1. 列名规范化：统一小写、去掉空格
    cleaned.columns = [str(c).strip().lower().replace(" ", "_") for c in cleaned.columns]

    # 2. 补齐缺失列（缺失则报错，避免静默错误）
    missing = [c for c in SCHEMA if c not in cleaned.columns]
    if missing:
        raise ValueError(f"数据缺少必需列: {missing}")

    cleaned = cleaned[SCHEMA]

    # 3. 日期标准化
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")

    # 4. 枚举校验
    cleaned = cleaned[cleaned["category"].isin(CATEGORIES.keys())]
    cleaned = cleaned[cleaned["market"].isin(MARKETS.keys())]

    # 5. 数值类型转换
    for col in NUMERIC_COLS:
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

    # 6. 去重（同品类/市场/日期只保留一行）
    cleaned = cleaned.drop_duplicates(subset=["date", "category", "market"], keep="last")

    # 7. 缺失值处理
    cleaned = cleaned.dropna(subset=["date", "category", "market", TARGET_COL])
    numeric_fill = {
        "search_index": 50.0,
        "bestseller_rank": 5000.0,
        "price_median": cleaned["price_median"].median() if cleaned["price_median"].notna().any() else 25.0,
        "review_growth": 0.0,
        "export_value": cleaned["export_value"].median() if cleaned["export_value"].notna().any() else 1000.0,
        "competition_index": 55.0,
    }
    for col, value in numeric_fill.items():
        if cleaned[col].isna().any():
            cleaned[col] = cleaned[col].fillna(value)

    # 8. 排序并重置索引
    cleaned = cleaned.sort_values(["category", "market", "date"]).reset_index(drop=True)
    return cleaned
