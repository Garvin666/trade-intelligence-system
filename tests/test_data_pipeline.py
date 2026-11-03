"""数据管道测试。"""

from __future__ import annotations

import pandas as pd

from src.config import CATEGORIES, MARKETS
from src.data.cleaner import SCHEMA, clean_market_data
from src.data.synthetic import generate_market_data


def test_clean_pipeline_schema_and_dedup() -> None:
    raw = generate_market_data(weeks=52, seed=7)
    cleaned = clean_market_data(raw)

    assert list(cleaned.columns) == SCHEMA
    assert cleaned.empty is False
    assert cleaned["category"].nunique() == len(CATEGORIES)
    assert cleaned["market"].nunique() == len(MARKETS)
    # 每个组合 52 周，去重后应保持完整
    assert len(cleaned) == len(CATEGORIES) * len(MARKETS) * 52
    assert cleaned["sales_volume"].notna().all()


def test_clean_rejects_missing_columns() -> None:
    raw = generate_market_data(weeks=4)
    bad = raw.drop(columns=["price_median"])
    try:
        clean_market_data(bad)
    except ValueError as exc:
        assert "price_median" in str(exc)
    else:
        raise AssertionError("缺少列时应抛出 ValueError")


def test_clean_removes_invalid_enum() -> None:
    raw = generate_market_data(weeks=4)
    raw.loc[0, "market"] = "mars"
    cleaned = clean_market_data(raw)
    assert (cleaned["market"] == "mars").sum() == 0
