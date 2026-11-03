"""食品品类目录一致性测试（12 大类 / 132 食品 SKU）。"""

from __future__ import annotations

import json

from src.config import (
    CATEGORIES,
    CATEGORY_CATALOG,
    CATEGORY_HS_CODES,
    CATEGORY_KEYWORDS,
    CATEGORY_PARAMS,
    MARKETS,
)
from src.trade.hs_code import hs_lookup_table
from src.trade.policy import BASE_TARIFF_RATE


NEW_CATEGORIES = {
    "cn_changsha_mifen",
    "cn_latiao",
    "cn_laoganma",
    "cn_beef_jerky",
    "cn_pixian_doubanjiang",
    "cn_longjing",
    "cn_mooncake",
    "cn_xinjiang_dates",
    "cn_self_heating_hotpot",
    "cn_dried_shitake",
    "cn_egg_yolk_pastry",
    "intl_ramen_japan",
    "intl_matcha",
    "intl_canned_tuna",
    "intl_instant_coffee",
    "intl_avocado",
    "intl_almonds",
    "intl_salmon_fillet",
    "intl_quinoa",
    "intl_panettone",
}


def test_catalog_derived_dicts_cover_all_categories() -> None:
    assert len(CATEGORIES) == 132
    assert set(CATEGORY_CATALOG) == set(CATEGORIES)
    assert set(CATEGORY_PARAMS) == set(CATEGORIES)
    assert set(CATEGORY_KEYWORDS) == set(CATEGORIES)
    assert set(CATEGORY_HS_CODES) == set(CATEGORIES)
    assert NEW_CATEGORIES <= set(CATEGORIES)


def test_trade_catalog_contains_new_categories() -> None:
    from src.trade.catalog import TRADE_CATALOG_JSON

    payload = json.loads(TRADE_CATALOG_JSON.read_text(encoding="utf-8"))
    assert set(payload["categories"]) == set(CATEGORIES)
    assert all(
        "productLine" in meta
        for code, meta in payload["categories"].items()
        if code in NEW_CATEGORIES
    )


def test_tariff_and_hs_cover_all_markets() -> None:
    for market in MARKETS:
        assert set(BASE_TARIFF_RATE[market]) == set(CATEGORIES)
    rows = hs_lookup_table()
    assert len(rows) == len(CATEGORIES)
    assert {row["category"] for row in rows} == set(CATEGORIES)


def test_four_brain_infers_food_categories() -> None:
    from src.four_brain.engine import infer_category

    assert infer_category("老干妈辣椒酱")[0] == "cn_laoganma"
    assert infer_category("麻辣牛肉干")[0] == "cn_beef_jerky"
    assert infer_category("辣条")[0] == "cn_latiao"


def test_trade_modules_cover_new_categories() -> None:
    from src.trade.credit import CATEGORY_ADJUST
    from src.trade.green import GREEN_EXPOSURE

    assert set(CATEGORY_ADJUST) == set(CATEGORIES)
    assert set(GREEN_EXPOSURE["us"]) == set(CATEGORIES)
