"""Tests for the GitHub dataset signal layer."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.data import github_datasets as gh


def _write_fixture(base: Path) -> None:
    amazon = pd.DataFrame(
        [
            {
                "title": "spicy latiao snack",
                "categories": "Snacks",
                "root_bs_rank": 12,
                "final_price": 2.5,
                "reviews_count": 120,
                "rating": 4.6,
                "url": "https://example.com/a1",
                "timestamp": "2026-01-01",
                "domain": "amazon.com",
            }
        ]
    )
    ebay = pd.DataFrame(
        [
            {
                "title": "changsha rice noodles",
                "root_category": "Noodles",
                "price": 3.2,
                "sold_count": 40,
                "item_location": "US",
                "url": "https://example.com/e1",
            }
        ]
    )
    shopee = pd.DataFrame(
        [
            {
                "title": "桂林米粉整箱",
                "categories": [{"catid": 1}],
                "currency": "SGD",
                "ratingAvg": 4.8,
                "ratingCount": 99,
                "productUrl": "https://example.com/s1",
                "_lastSeenAt": "2026-07-29",
            }
        ]
    )
    octaprice = pd.DataFrame(
        [
            {
                "name": "longjing green tea 250g",
                "breadcrumbs": "Grocery > Tea",
                "salePrice": 14.98,
                "rating": 4.7,
                "reviewCount": 120,
                "url": "https://example.com/o1",
                "scrapedDate": "2025-01-23",
            }
        ]
    )
    hs = pd.DataFrame([{"hscode": "1902", "description": "米、面制食品"}])

    (base / "amazon").mkdir(parents=True)
    (base / "ebay").mkdir(parents=True)
    (base / "shopee").mkdir(parents=True)
    (base / "octaprice").mkdir(parents=True)
    (base / "hs" / "data").mkdir(parents=True)
    amazon.to_csv(base / "amazon" / "amazon.csv", index=False)
    ebay.to_csv(base / "ebay" / "ebay.csv", index=False)
    shopee.to_parquet(base / "shopee" / "shopee.parquet", index=False)
    octaprice.to_csv(base / "octaprice" / "octaprice.csv", index=False)
    hs.to_csv(base / "hs" / "data" / "harmonized-system.csv", index=False)


def test_build_github_signals_all_providers_mapped(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    out = tmp_path / "github_signals.json"
    payload = gh.build_github_signals(
        base_dir=tmp_path,
        output_path=out,
        max_rows_per_provider=10,
    )
    assert set(payload["sources"]) == set(gh.ENABLED_PROVIDERS)
    for provider in gh.ENABLED_PROVIDERS:
        assert payload["sources"][provider]["mapped_rows"] > 0
    assert payload["rows"]
    for row in payload["rows"]:
        assert row["source_type"]
        assert row["category"]
        assert row["value"] is not None


def test_build_github_signals_missing_provider_fails(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    (tmp_path / "hs" / "data" / "harmonized-system.csv").unlink()
    with pytest.raises(FileNotFoundError, match="HS"):
        gh.build_github_signals(base_dir=tmp_path, output_path=tmp_path / "out.json")


def test_map_category_and_market() -> None:
    assert gh.map_category("spicy latiao snack", "Snacks") == "cn_latiao"
    assert gh.map_category("changsha rice noodles") == "cn_changsha_mifen"
    assert gh.map_category("longjing green tea") == "cn_longjing"
    assert gh.map_category("sichuan beef jerky") == "cn_beef_jerky"
    assert gh.map_category("frozen dumplings") == "cn_frozen_dumplings"
    assert gh.map_market("United States") == "us"
    assert gh.map_market("Singapore") == "sea"


def test_github_real_results_columns_and_idempotent(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    payload = gh.build_github_signals(
        base_dir=tmp_path,
        output_path=tmp_path / "github_signals.json",
        max_rows_per_provider=10,
    )
    first = tmp_path / "real_results.csv"
    gh.build_github_real_results(output_path=first, payload=payload)
    gh.build_github_real_results(output_path=first, payload=payload)
    frame = pd.read_csv(first)
    assert list(frame.columns) == gh.REAL_RESULTS_COLUMNS
    assert not frame.empty


def test_signal_summary_filters_combos(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    payload = gh.build_github_signals(
        base_dir=tmp_path,
        output_path=tmp_path / "github_signals.json",
        max_rows_per_provider=10,
    )
    summary = gh.signal_summary([("cn_latiao", "us")], max_rows=5, payload=payload)
    assert "Amazon" in summary
    assert "cn_latiao" in summary
    assert "仅辅助洞察" in summary


def test_signal_summary_empty_without_payload() -> None:
    assert gh.signal_summary(payload={"sources": {}, "rows": []}) == ""


def test_load_github_signals_missing_returns_empty(tmp_path: Path) -> None:
    payload = gh.load_github_signals(tmp_path / "missing.json")
    assert payload["sources"] == {}
    assert payload["rows"] == []
