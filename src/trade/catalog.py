"""Trade-decision catalog and autofill served by the unified backend.

The Node server kept category/market/platform dictionaries in `catalog.js`
and computed autofill suggestions in `server.js`. This module is the Python
equivalent so the merged FastAPI backend owns the whole trade workflow.
"""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config import DATA_DIR
from src.trade.cost import DEFAULT_FX_RATE

TRADE_CATALOG_JSON = DATA_DIR / "trade_catalog.json"

ROUTE_PROFILES = {
    "air": {"freight": 5.8, "paymentDays": 28, "inventoryDays": 18, "label": "空运快反"},
    "sea": {"freight": 2.6, "paymentDays": 35, "inventoryDays": 42, "label": "海运标准"},
    "bonded": {"freight": 3.2, "paymentDays": 30, "inventoryDays": 30, "label": "海外仓备货"},
    "rail": {"freight": 3.8, "paymentDays": 34, "inventoryDays": 36, "label": "铁路联运"},
}

CATEGORY_RULES = [
    ("cn_latiao", re.compile(r"辣条|麻辣|零食|小吃|膨化|latiao|spicy snack|spicy strip")),
    ("cn_longjing", re.compile(r"茶|茶叶|茶饮|龙井|tea|green tea|oolong|绿茶")),
    ("cn_frozen_dumplings", re.compile(r"速冻|水饺|饺子|冷冻|frozen dumpling|frozen food")),
    ("cn_beef_jerky", re.compile(r"牛肉干|肉干|肉脯|jerky|cured meat|beef jerky")),
    ("cn_laoganma", re.compile(r"辣椒酱|辣酱|酱料|调味|sauce|condiment|chili sauce|豆瓣")),
    ("cn_changsha_mifen", re.compile(r"米粉|米线|rice noodle|changsha|长沙")),
    ("cn_guilin_mifen", re.compile(r"桂林|guilin")),
    ("cn_spicy_gluten", re.compile(r"面筋|素肉|麻辣面筋|gluten|spicy gluten")),
    ("cn_dried_chili", re.compile(r"干辣椒|辣椒|chili|dried pepper|cayenne")),
    ("cn_pixian_doubanjiang", re.compile(r"豆瓣酱|douban|bean paste|郫县")),
    ("cn_green_bean_cake", re.compile(r"绿豆糕|糕点|饼干|biscuit|cake|pastry|月饼")),
    ("cn_xiaomi_zhou", re.compile(r"小米粥|八宝粥|congee|porridge|粥")),
    ("cn_bajiang_mian", re.compile(r"八宝粥|杂粮|grain porridge")),
    ("cn_tea_egg", re.compile(r"茶叶蛋|marinated egg|tea egg")),
    ("cn_salted_duck_egg", re.compile(r"咸鸭蛋|皮蛋|salted egg|century egg|蛋")),
    ("cn_handmade_noodles", re.compile(r"挂面|手工面|handmade noodle|wheat noodle")),
    ("cn_handmade_noodles", re.compile(r"挂面|手工面|方便面|泡面|handmade noodle|wheat noodle|instant noodle|速食面")),
    ("intl_ramen_japan", re.compile(r"拉面|日式拉面|japanese ramen")),
    ("intl_pasta", re.compile(r"意面| pasta|spaghetti|通心粉")),
    ("intl_oats", re.compile(r"燕麦|oats|cereal|麦片")),
    ("intl_quinoa", re.compile(r"藜麦|quinoa")),
    ("intl_greek_yogurt", re.compile(r"酸奶|yogurt|希腊酸奶")),
    ("intl_cheddar", re.compile(r"奶酪|芝士|cheese|切达")),
    ("intl_firm_tofu", re.compile(r"豆腐|tofu|豆干")),
    ("intl_hummus", re.compile(r"鹰嘴豆|hummus|chickpea")),
    ("cn_shrimp_paste", re.compile(r"虾酱|鱼酱|shrimp paste")),
    ("cn_dried_seaweed", re.compile(r"紫菜|海苔|seaweed|nori")),
    ("intl_canned_tuna", re.compile(r"金枪鱼|吞拿|tuna")),
    ("intl_salmon_fillet", re.compile(r"三文鱼| salmon|fish fillet|鱼柳")),
    ("cn_guaiwei_dou", re.compile(r"怪味豆|蚕豆|broad bean|fava")),
    ("intl_frozen_pizza", re.compile(r"披萨|pizza")),
]

MARKET_RULES = [
    ("us", re.compile(r"美国|北美|amazon")),
    ("eu", re.compile(r"欧洲|德国|法国|欧盟")),
    ("jp", re.compile(r"日本|日本站")),
    ("kr", re.compile(r"韩国")),
    ("au", re.compile(r"澳洲|澳大利亚")),
    ("uk", re.compile(r"英国")),
    ("latam", re.compile(r"拉美|巴西|墨西哥")),
]


def _clean(value: Any, max_length: int = 120) -> str:
    text = str(value if value is not None else "")
    text = text.replace("<", "").replace(">", "")
    text = "".join(" " if ord(ch) < 32 or ord(ch) == 127 else ch for ch in text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def _js_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return float("nan")
    return float("nan")


def _number_in(value: Any, fallback: float, low: float, high: float) -> float:
    number = _js_number(value)
    if math.isnan(number):
        return fallback
    return max(low, min(high, number))


def _fixed(value: float, digits: int) -> float:
    quant = Decimal("1." + "0" * digits)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict[str, dict[str, Any]]]:
    if not TRADE_CATALOG_JSON.exists():
        raise FileNotFoundError(f"Trade catalog missing: {TRADE_CATALOG_JSON}")
    return json.loads(TRADE_CATALOG_JSON.read_text(encoding="utf-8"))


def _by_key(items: dict[str, dict[str, Any]], key: str, fallback_key: str) -> tuple[str, dict[str, Any]]:
    if key in items:
        return key, items[key]
    if fallback_key in items:
        return fallback_key, items[fallback_key]
    first = next(iter(items.items()), ("", {}))
    return first


def normalize_profile(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("profile") or (payload.get("scenario") or {}).get("profile") or {}
    return {
        "productKeyword": _clean(raw.get("productKeyword"), 80),
        "customerSegment": _clean(raw.get("customerSegment") or "mass", 40),
        "businessStage": _clean(raw.get("businessStage") or "explore", 40),
        "goal": _clean(raw.get("goal") or "growth", 40),
        "riskTolerance": _clean(raw.get("riskTolerance") or "medium", 40),
        "budget": _number_in(raw.get("budget"), 30000, 1000, 2000000),
        "stockPreference": _clean(raw.get("stockPreference") or "balanced", 40),
        "complianceFocus": _clean(raw.get("complianceFocus") or "standard", 40),
        "customNeed": _clean(raw.get("customNeed"), 240),
    }


def pick_category(profile: dict[str, Any], current: dict[str, Any]) -> dict[str, str]:
    manual = _clean(current.get("customCategory"), 40)
    text = f"{profile['productKeyword']} {profile['customNeed']} {manual}".lower()
    matched = next((key for key, rule in CATEGORY_RULES if rule.search(text)), None)
    selected = _clean(current.get("category"), 40)
    return {"key": matched or selected or "cn_latiao", "customCategory": manual}


def pick_market(profile: dict[str, Any], current: dict[str, Any]) -> str:
    text = f"{profile['productKeyword']} {profile['customNeed']}".lower()
    matched = next((key for key, rule in MARKET_RULES if rule.search(text)), None)
    return matched or _clean(current.get("market"), 40) or "sea"


def pick_platform(profile: dict[str, Any], market: str, current: dict[str, Any]) -> str:
    if profile["goal"] == "brand":
        return "prototype"
    if market == "sea":
        return "shopee"
    if market in {"us", "eu", "uk"}:
        return "amazon"
    if market in {"jp", "kr"}:
        return "tiktok_shop"
    return _clean(current.get("platform"), 40) or "aliexpress"


def pick_route(profile: dict[str, Any]) -> str:
    if profile["stockPreference"] == "light" or profile["businessStage"] == "test":
        return "air"
    if profile["stockPreference"] == "deep" or profile["businessStage"] == "scale":
        return "bonded"
    return "sea"


def autofill(payload: dict[str, Any]) -> dict[str, Any]:
    catalog = load_catalog()
    profile = normalize_profile(payload)
    current = payload.get("current") or (payload.get("scenario") or {}).get("input") or {}
    category_pick = pick_category(profile, current)
    market_key = pick_market(profile, current)
    platform_key = pick_platform(profile, market_key, current)
    route_key = pick_route(profile)
    category_key, category = _by_key(catalog["categories"], category_pick["key"], "cn_latiao")
    market_key, market = _by_key(catalog["markets"], market_key, "sea")
    platform_key, platform = _by_key(catalog["platforms"], platform_key, "shopee")
    route = ROUTE_PROFILES.get(route_key, ROUTE_PROFILES["sea"])
    quantity_base = math.floor(
        (profile["budget"] / max(float(category.get("cost", 0)) + float(route["freight"]) + 4, 1)) / 10
    ) * 10
    quantity_min = 500 if profile["businessStage"] == "scale" else 120
    quantity_max = 8000 if profile["businessStage"] == "scale" else 2500
    quantity = _number_in(quantity_base, 300, quantity_min, quantity_max)

    return {
        "data": {
            "input": {
                "category": category_key,
                "customCategory": category_pick["customCategory"],
                "market": market_key,
                "platform": platform_key,
                "route": route_key,
                "quantity": int(quantity),
                "price": _fixed(float(category.get("basePrice", 0)) * float(market.get("priceMultiplier", 1)), 1),
                "cost": _fixed(float(category.get("cost", 0)), 1),
                "weight": _fixed(float(category.get("weight", 0)), 2),
                "freight": _fixed(
                    float(route["freight"]) * max(0.8, float(category.get("weight", 0)) * 0.8),
                    1,
                ),
                "adRate": _fixed(float(platform.get("adDefault", 0)) * 100, 1),
                "tariff": _fixed(float(market.get("tariff", 0)) * 100, 1),
                "returnRate": _fixed(
                    (float(category.get("returnRate", 0)) + float(market.get("returnAdj", 0))) * 100,
                    1,
                ),
                "fxRisk": _fixed(float(market.get("fx", 0)) * 100, 1),
                "paymentDays": route["paymentDays"],
                "inventoryDays": route["inventoryDays"],
            },
            "profile": profile,
            "signals": [
                "已根据商品关键词、客户画像、预算和风险偏好生成方案",
                f"匹配品类：{category_pick['customCategory'] or category.get('label', '')}",
                f"推荐市场：{market.get('label', '')}",
                f"推荐平台：{platform.get('label', '')}",
                f"推荐履约：{route['label']}",
            ],
        }
    }


def catalog_payload() -> dict[str, Any]:
    catalog = load_catalog()
    return {
        "fx_rate": DEFAULT_FX_RATE,
        "data": {
            "categories": [
                {"key": key, **meta}
                for key, meta in catalog["categories"].items()
            ],
            "markets": [
                {"key": key, **meta}
                for key, meta in catalog["markets"].items()
            ],
            "platforms": [
                {"key": key, **meta}
                for key, meta in catalog["platforms"].items()
            ],
            "recommendations": [],
            "signals": ["后端商品、市场与平台字典已同步", "目录来源：data/trade_catalog.json"],
        }
    }
