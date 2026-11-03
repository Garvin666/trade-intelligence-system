# -*- coding: utf-8 -*-
"""校验 market.json 的结构、锚点一致性，以及与 main.py 工具的兼容性。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
MARKET_JSON = BASE_DIR / "market.json"
RUNPACK_MARKET_JSON = (
    REPO_ROOT / "发布与材料" / "完整Demo运行包" / "小助手" / "market.json"
)

EXPECTED_CATEGORY_COUNT = 132
EXPECTED_MARKET_IDS = [
    "us",
    "eu",
    "sea",
    "jp",
    "ca",
    "au",
    "uk",
    "kr",
    "de",
    "fr",
    "vn",
    "ru",
    "hu",
    "ae",
    "mx",
]
REQUIRED_MARKET_FIELDS = {
    "id": str,
    "name": str,
    "demand_index": int,
    "competition_index": int,
    "price_range_usd": list,
    "opportunity_score": int,
    "top_products": list,
    "platforms": str,
    "logistics_note": str,
    "compliance_note": str,
    "tariff_baseline": int,
    "season_note": str,
}

# 食品切换后重新基线化的锚点（2026-09-22）：3 个食品 SKU × 3 市场，
# 值取自当前 market.json，用于锁定已认可的数值不被后续生成漂移。
ANCHORS = {
    ("cn_latiao", "us"): {
        "demand_index": 98,
        "competition_index": 78,
        "price_range_usd": [4, 8],
        "opportunity_score": 70,
        "top_products": [
            {"name": "辣条", "price": 4.0, "note": "价格带清晰，利润空间可期"},
            {"name": "Spicy Wheat Strips", "price": 4.6, "note": "季节性上行，旺季前备货"},
        ],
    },
    ("cn_latiao", "eu"): {
        "demand_index": 95,
        "competition_index": 72,
        "price_range_usd": [4, 9],
        "opportunity_score": 73,
        "top_products": [
            {"name": "辣条", "price": 4.0, "note": "价格带清晰，利润空间可期"},
            {"name": "Spicy Wheat Strips", "price": 4.6, "note": "季节性上行，旺季前备货"},
        ],
    },
    ("cn_latiao", "sea"): {
        "demand_index": 93,
        "competition_index": 61,
        "price_range_usd": [2, 6],
        "opportunity_score": 82,
        "top_products": [
            {"name": "辣条", "price": 4.0, "note": "价格带清晰，利润空间可期"},
            {"name": "Spicy Wheat Strips", "price": 4.6, "note": "季节性上行，旺季前备货"},
        ],
    },
    ("cn_longjing", "us"): {
        "demand_index": 88,
        "competition_index": 74,
        "price_range_usd": [25, 56],
        "opportunity_score": 64,
        "top_products": [
            {"name": "西湖龙井", "price": 28.0, "note": "口碑扩散中，评论增长活跃"},
            {"name": "West Lake Longjing Tea", "price": 32.2, "note": "价格带清晰，利润空间可期"},
        ],
    },
    ("cn_longjing", "eu"): {
        "demand_index": 84,
        "competition_index": 68,
        "price_range_usd": [28, 62],
        "opportunity_score": 66,
        "top_products": [
            {"name": "西湖龙井", "price": 28.0, "note": "口碑扩散中，评论增长活跃"},
            {"name": "West Lake Longjing Tea", "price": 32.2, "note": "价格带清晰，利润空间可期"},
        ],
    },
    ("cn_longjing", "sea"): {
        "demand_index": 82,
        "competition_index": 57,
        "price_range_usd": [17, 39],
        "opportunity_score": 75,
        "top_products": [
            {"name": "西湖龙井", "price": 28.0, "note": "口碑扩散中，评论增长活跃"},
            {"name": "West Lake Longjing Tea", "price": 32.2, "note": "价格带清晰，利润空间可期"},
        ],
    },
    ("cn_frozen_dumplings", "us"): {
        "demand_index": 98,
        "competition_index": 74,
        "price_range_usd": [13, 28],
        "opportunity_score": 74,
        "top_products": [
            {"name": "速冻水饺", "price": 14.0, "note": "需求稳定，适合跨境试销"},
            {"name": "Frozen Dumplings", "price": 16.1, "note": "口碑扩散中，评论增长活跃"},
        ],
    },
    ("cn_frozen_dumplings", "eu"): {
        "demand_index": 96,
        "competition_index": 68,
        "price_range_usd": [14, 31],
        "opportunity_score": 78,
        "top_products": [
            {"name": "速冻水饺", "price": 14.0, "note": "需求稳定，适合跨境试销"},
            {"name": "Frozen Dumplings", "price": 16.1, "note": "口碑扩散中，评论增长活跃"},
        ],
    },
    ("cn_frozen_dumplings", "sea"): {
        "demand_index": 94,
        "competition_index": 57,
        "price_range_usd": [8, 20],
        "opportunity_score": 87,
        "top_products": [
            {"name": "速冻水饺", "price": 14.0, "note": "需求稳定，适合跨境试销"},
            {"name": "Frozen Dumplings", "price": 16.1, "note": "口碑扩散中，评论增长活跃"},
        ],
    },
}


def _fail(message: str) -> None:
    raise AssertionError(message)


def main() -> None:
    data = json.loads(MARKET_JSON.read_text(encoding="utf-8"))

    categories = data["categories"]
    if len(categories) != EXPECTED_CATEGORY_COUNT:
        _fail(f"品类数量应为 {EXPECTED_CATEGORY_COUNT}，实际 {len(categories)}")

    for category in categories:
        for field in ("id", "name", "aliases", "hs_code", "price_band", "peak_months"):
            if field not in category:
                _fail(f"{category.get('id')} 缺少品类字段 {field}")
        if not isinstance(category["aliases"], list):
            _fail(f"{category.get('id')} 的 aliases 类型错误")
        markets = category["markets"]
        if [m["id"] for m in markets] != EXPECTED_MARKET_IDS:
            _fail(f"{category['id']} 的市场 id 顺序与预期不一致")
        for market in markets:
            for field, field_type in REQUIRED_MARKET_FIELDS.items():
                if field not in market:
                    _fail(
                        f"{category['id']}/{market.get('id')} 缺少市场字段 {field}"
                    )
                if not isinstance(market[field], field_type):
                    _fail(
                        f"{category['id']}/{market.get('id')} 的 {field} "
                        f"类型错误：{type(market[field]).__name__}"
                    )
            if not market["top_products"]:
                _fail(f"{category['id']}/{market['id']} 的 top_products 为空")

    for (category_id, market_id), expected in ANCHORS.items():
        category = next(
            c for c in categories if c["id"] == category_id
        )
        market = next(
            m for m in category["markets"] if m["id"] == market_id
        )
        for field, value in expected.items():
            if market.get(field) != value:
                _fail(
                    f"锚点变化：{category_id}/{market_id} 的 {field} "
                    f"应为 {value!r}，实际 {market.get(field)!r}"
                )

    for section, fields in {
        "platforms": ("id", "name", "markets", "fees", "best_categories", "notes"),
        "logistics": ("id", "name", "time", "cost", "best_price_usd", "notes"),
        "regulations": (
            "market",
            "framework",
            "key_certifications",
            "documents",
            "notes",
        ),
        "payments": ("provider", "features", "settlement", "notes"),
        "sources": ("name", "url", "use"),
    }.items():
        items = data.get(section)
        if not items:
            _fail(f"缺少顶层区块 {section}")
        for item in items:
            for field in fields:
                if field not in item:
                    _fail(f"{section} 条目缺少字段 {field}")

    root_bytes = MARKET_JSON.read_bytes()
    if not RUNPACK_MARKET_JSON.exists():
        # 分发包由打包脚本产出，未打包时不做一致性判定（不静默跳过，明确提示）。
        print("[skip] 分发包副本不存在，跳过一致性校验：" + str(RUNPACK_MARKET_JSON))
        print(
            "verify ok: "
            f"{len(categories)} categories, "
            f"{sum(len(c['markets']) for c in categories)} market entries, "
            f"anchors preserved, copies NOT checked (dist package absent)"
        )
        return

    runpack_bytes = RUNPACK_MARKET_JSON.read_bytes()
    if root_bytes != runpack_bytes:
        _fail("根目录与分发包 market.json 不一致")
    if hashlib.sha256(root_bytes).hexdigest() != hashlib.sha256(
        runpack_bytes
    ).hexdigest():
        _fail("根目录与分发包 market.json 哈希不一致")

    print(
        "verify ok: "
        f"{len(categories)} categories, "
        f"{sum(len(c['markets']) for c in categories)} market entries, "
        f"anchors preserved, copies identical"
    )


if __name__ == "__main__":
    main()
