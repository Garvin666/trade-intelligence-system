"""Tests for the Hugging Face dataset signal layer."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.data import hf_datasets as hf


def _write_fixture(base: Path) -> None:
    ecom = pd.DataFrame(
        [
            {"id": 1, "text": "spicy latiao snack", "label": "grocery_food"},
            {"id": 2, "text": "longjing green tea", "label": "unknown_label"},
            {"id": 3, "text": "changsha rice noodles", "label": "kitchen_dining"},
        ]
    )
    reviews = [
        {"review": "latiao enak sekali", "sentimen": 1, "translate": "very good latiao snack"},
        {"review": "teh pahit", "sentimen": 0, "translate": "longjing green tea bitter"},
        {"review": "mifen lezat", "sentimen": 1, "translate": "changsha rice noodles delicious"},
    ]
    polarity = pd.DataFrame(
        [
            {"label": 1, "title": "spicy latiao snack", "content": "very tasty"},
            {"label": 0, "title": "longjing green tea", "content": "stale leaves"},
            {"label": 1, "title": "changsha rice noodles", "content": "great noodles"},
        ]
    )
    products = pd.DataFrame(
        [
            {
                "parent_asin": "B000000001",
                "title": "spicy latiao snack pack",
                "main_category": "Snacks",
                "price": 2.99,
                "average_rating": 4.6,
                "rating_number": 120,
                "date_first_available": "2023-01-01",
            },
            {
                "parent_asin": "B000000002",
                "title": "longjing green tea loose leaf",
                "main_category": "Grocery",
                "price": 9.99,
                "average_rating": 4.5,
                "rating_number": 80,
                "date_first_available": "2023-02-01",
            },
        ]
    )
    sales_cols = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"] + [
        f"d_{i}" for i in range(1, 32)
    ]
    m5 = pd.DataFrame(
        [
            ["HOBBIES_1_001_CA_1_validation", "HOBBIES_1_001", "HOBBIES_1", "HOBBIES", "CA_1", "CA"]
            + [1.0] * 31,
            ["FOODS_1_001_CA_1_validation", "FOODS_1_001", "FOODS_1", "FOODS", "CA_1", "CA"]
            + [2.0] * 31,
        ],
        columns=sales_cols,
    )
    prices = pd.DataFrame(
        [
            {"store_id": "CA_1", "item_id": "HOBBIES_1_001", "wm_yr_wk": 11325, "sell_price": 9.58},
            {"store_id": "CA_1", "item_id": "FOODS_1_001", "wm_yr_wk": 11325, "sell_price": 3.2},
        ]
    )

    (base / "ecom_classification" / "data").mkdir(parents=True)
    (base / "ecom_reviews_sentiment").mkdir(parents=True)
    (base / "amazon_polarity" / "amazon_polarity").mkdir(parents=True)
    (base / "amazon_products_2023").mkdir(parents=True)
    (base / "m5_forecasting").mkdir(parents=True)

    ecom.to_parquet(base / "ecom_classification" / "data" / "train.parquet", index=False)
    with (base / "ecom_reviews_sentiment" / "reviews.json").open("w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False)
    polarity.to_parquet(
        base / "amazon_polarity" / "amazon_polarity" / "train-00000-of-00004.parquet",
        index=False,
    )
    products.to_feather(base / "amazon_products_2023" / "data-00000-of-00004.arrow")
    m5.to_csv(base / "m5_forecasting" / "sales_train_validation.csv", index=False)
    prices.to_csv(base / "m5_forecasting" / "sell_prices.csv", index=False)


def test_build_hf_signals_all_providers_mapped(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    out = tmp_path / "hf_signals.json"
    payload = hf.build_hf_signals(
        base_dir=tmp_path,
        output_path=out,
        max_rows_per_provider=50,
    )
    assert set(payload["sources"]) == set(hf.ENABLED_PROVIDERS)
    for provider in hf.ENABLED_PROVIDERS:
        assert payload["sources"][provider]["mapped_rows"] > 0
    assert payload["rows"]
    for row in payload["rows"]:
        assert row["source_type"]
        assert row["category"]
        assert row["value"] is not None


def test_build_hf_signals_missing_provider_fails(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    (tmp_path / "m5_forecasting" / "sell_prices.csv").unlink()
    with pytest.raises(FileNotFoundError, match="m5_forecasting"):
        hf.build_hf_signals(base_dir=tmp_path, output_path=tmp_path / "out.json")


def test_hf_real_results_columns_and_idempotent(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    payload = hf.build_hf_signals(
        base_dir=tmp_path,
        output_path=tmp_path / "hf_signals.json",
        max_rows_per_provider=50,
    )
    first = tmp_path / "real_results.csv"
    hf.build_hf_real_results(output_path=first, payload=payload)
    hf.build_hf_real_results(output_path=first, payload=payload)
    frame = pd.read_csv(first)
    assert list(frame.columns) == hf.REAL_RESULTS_COLUMNS
    assert not frame.empty


def test_signal_summary_filters_combos(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    payload = hf.build_hf_signals(
        base_dir=tmp_path,
        output_path=tmp_path / "hf_signals.json",
        max_rows_per_provider=50,
    )
    summary = hf.signal_summary([("cn_changsha_mifen", "")], max_rows=5, payload=payload)
    assert "Hugging Face" in summary
    assert "cn_changsha_mifen" in summary
    assert "仅辅助洞察" in summary


def test_signal_summary_empty_without_payload() -> None:
    assert hf.signal_summary(payload={"sources": {}, "rows": []}) == ""


def test_load_hf_signals_missing_returns_empty(tmp_path: Path) -> None:
    payload = hf.load_hf_signals(tmp_path / "missing.json")
    assert payload["sources"] == {}
    assert payload["rows"] == []


def test_m5_recent_sales_aggregation(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    payload = hf.build_hf_signals(
        base_dir=tmp_path,
        output_path=tmp_path / "hf_signals.json",
        max_rows_per_provider=50,
    )
    m5_rows = [
        row
        for row in payload["rows"]
        if row["source_type"] == "hf_m5_forecasting"
        and row["keyword"] == "recent_28d_sales"
    ]
    # M5 cat_id FOODS -> cn_laoganma，近 28 天销量 = 2.0 × 28 = 56.0
    assert any(row["category"] == "cn_laoganma" and row["value"] == 56.0 for row in m5_rows)
