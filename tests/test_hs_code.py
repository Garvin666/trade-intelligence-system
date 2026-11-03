"""HS Code 速查模块测试。"""

from __future__ import annotations

from src.config import CATEGORIES
from src.trade.hs_code import CATEGORY_HS_CODES, hs_lookup_table, lookup_hs


def test_all_categories_have_hs_mapping() -> None:
    missing = set(CATEGORIES) - set(CATEGORY_HS_CODES)
    assert missing == set()


def test_lookup_returns_code_and_tariff() -> None:
    result = lookup_hs("cn_changsha_mifen", "us")
    assert len(result["hs_code"]) == 6
    assert result["hs_code"].startswith("1902")
    assert result["base_tariff_rate"] > 0
    assert result["verified"] is True
    assert "核对" in result["note"]


def test_lookup_unknown_category() -> None:
    result = lookup_hs("unknown")
    assert result["hs_code"] == ""
    assert "暂无可演示" in result["note"]


def test_lookup_table_covers_all_markets() -> None:
    rows = hs_lookup_table()
    assert len(rows) == len(CATEGORIES)
    assert all(row["hs_code"] for row in rows)
    assert {row["category"] for row in rows} == set(CATEGORIES)


def test_lookup_tariff_defaults_to_zero_for_unknown_market() -> None:
    result = lookup_hs("cn_changsha_mifen", "unknown")
    assert result["base_tariff_rate"] == 0.0
