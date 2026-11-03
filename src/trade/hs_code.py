"""品类默认 HS 编码速查（演示口径）。

思路参考 ``chnjames/tradehot-skill``（该仓库无明确 License，仅借鉴速查结构，
不复制代码）。映射表为项目演示口径，正式使用前需按海关税则核对。
"""

from __future__ import annotations

import csv
from functools import lru_cache
from typing import Any

from src.config import CATEGORY_HS_CODES, GITHUB_DATA_DIR
from src.trade.policy import BASE_TARIFF_RATE


@lru_cache(maxsize=1)
def _hs6_index() -> dict[str, dict[str, str]]:
    """从本地 Harmonized System 数据集构建 HS6 子目索引。"""
    path = GITHUB_DATA_DIR / "hs" / "data" / "harmonized-system.csv"
    if not path.exists():
        return {}
    index: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = str(row.get("hscode") or "").strip()
            parent = str(row.get("parent") or "").strip()
            description = str(row.get("description") or "").strip()
            if code and parent and description:
                index.setdefault(parent, {"code": code, "description": description})
    return index


def _hs6_for_code(code: str) -> dict[str, str] | None:
    return _hs6_index().get(code)


def lookup_hs(category: str, market: str | None = None) -> dict[str, Any]:
    """返回品类默认 HS6 码与基础税率速查结果。"""
    category = str(category or "").strip()
    entry = CATEGORY_HS_CODES.get(category)
    if entry is None:
        return {
            "category": category,
            "market": market,
            "hs_code": "",
            "description": "",
            "base_tariff_rate": 0.0,
            "verified": False,
            "note": "暂无可演示的 HS 映射，请补充品类或核对官方税则。",
        }
    market = str(market or "").strip().lower()
    tariff = 0.0
    if market in BASE_TARIFF_RATE and category in BASE_TARIFF_RATE[market]:
        tariff = float(BASE_TARIFF_RATE[market][category])
    hs6 = _hs6_for_code(entry["code"]) if len(entry["code"]) == 4 else None
    hs_code = hs6["code"] if hs6 else entry["code"]
    description = hs6["description"] if hs6 else entry["description"]
    return {
        "category": category,
        "market": market or None,
        "hs_code": hs_code,
        "description": description,
        "base_tariff_rate": tariff,
        "verified": hs6 is not None,
        "note": (
            "HS6 子目来自本地 Harmonized System 数据集，正式申报前需按海关税则核对。"
            if hs6
            else "暂未匹配到 HS6 子目，正式申报前需按海关税则核对。"
        ),
    }


def hs_lookup_table() -> list[dict[str, Any]]:
    """返回全品类速查表，便于报告与看板一次性展示。"""
    rows = []
    for category in sorted(CATEGORY_HS_CODES):
        info = lookup_hs(category)
        rows.append(
            {
                "category": category,
                "hs_code": info["hs_code"],
                "description": info["description"],
                "verified": info["verified"],
                "note": info["note"],
            }
        )
    return rows


__all__ = ["CATEGORY_HS_CODES", "hs_lookup_table", "lookup_hs"]
