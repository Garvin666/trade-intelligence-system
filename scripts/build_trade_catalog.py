"""Rebuild data/trade_catalog.json from the unified category catalog."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
TRADE_CATALOG_JSON = PROJECT_ROOT / "data" / "trade_catalog.json"

from src.config import CATEGORY_CATALOG  # noqa: E402


def _weight(price: float) -> float:
    if price < 50:
        return 0.6
    if price < 150:
        return 1.2
    return 3.5


def _derived_entry(meta: dict[str, Any]) -> dict[str, Any]:
    price = float(meta["price"])
    return {
        "label": str(meta["name_cn"]),
        "basePrice": round(price * 1.03, 1),
        "baseSales": round(float(meta["base_sales"]) * 0.825, 2),
        "competition": round(float(meta["competition"]) + 1.4, 1),
        "cost": round(price * 0.46, 1),
        "weight": _weight(price),
        "returnRate": 0.07,
        "compliance": 62.0,
        "productLine": str(meta["keyword"]),
    }


def build() -> dict[str, Any]:
    existing: dict[str, Any] = {}
    if TRADE_CATALOG_JSON.exists():
        existing = json.loads(TRADE_CATALOG_JSON.read_text(encoding="utf-8"))
    categories = dict(existing.get("categories") or {})
    markets = dict(existing.get("markets") or {})
    platforms = dict(existing.get("platforms") or {})
    for code, meta in CATEGORY_CATALOG.items():
        if code not in categories:
            categories[code] = _derived_entry(meta)
    payload = {
        "categories": categories,
        "markets": markets,
        "platforms": platforms,
    }
    TRADE_CATALOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TRADE_CATALOG_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> int:
    payload = build()
    print(f"trade catalog categories={len(payload['categories'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
