"""卖家精灵 / 浏览器导出 CSV 字段字典与归一化（C-2 P1-1）。

- 字段字典：卖家精灵导出列名（中英文别名）→ 系统标准字段；
- 必需列校验：关键词列必填 + 至少一个数值列；
- normalize：重命名 + 数值清洗 + 输出映射报告（匹配/未匹配/缺失列）。

用法（API 层）：POST /api/import/seller-magic（multipart CSV）→ 本模块校验并归一化。
"""

from __future__ import annotations

import pandas as pd
from typing import Any

# 卖家精灵导出列名别名 → 系统标准字段
SELLER_MAGIC_FIELD_DICT: dict[str, tuple[str, ...]] = {
    "keyword": ("关键词", "keyword", "搜索词"),
    "search_index": ("搜索热度", "月搜索量", "search_volume", "月搜索热度"),
    "sales_volume": ("月销量", "月销售量", "monthly_sales", "销量"),
    "price_median": ("平均价格", "avg_price", "价格"),
    "review_count": ("评论数", "评论数量", "review_count", "reviews"),
    "rating": ("评分", "rating", "星级"),
    "competition_index": ("竞争度", "competition", "竞争强度"),
    "click_rate": ("点击率", "click_rate"),
    "conversion_rate": ("转化率", "conversion_rate"),
    "product_count": ("商品数", "product_count"),
    "online_product_count": ("在线商品数", "online_product_count"),
    "click_concentration": ("点击集中度", "click_concentration"),
    "home_page_ratio": ("首页占比", "home_page_ratio"),
    "purchase_volume": ("月购买量", "purchase_volume"),
    "supply_demand_ratio": ("供需比", "supply_demand_ratio"),
}

REQUIRED_COLUMNS = ("keyword",)
NUMERIC_COLUMNS = tuple(
    field
    for field in SELLER_MAGIC_FIELD_DICT
    if field != "keyword"
)

# 反向查找：别名（小写）→ 标准字段
_ALIAS_LOOKUP: dict[str, str] = {}
for _field, _aliases in SELLER_MAGIC_FIELD_DICT.items():
    for _alias in _aliases:
        _ALIAS_LOOKUP[_alias.strip().lower()] = _field


def normalize_seller_magic_csv(
    df: pd.DataFrame,
    *,
    max_rows: int = 20000,
) -> dict[str, Any]:
    """归一化卖家精灵导出 CSV，返回 {df, report}。

    report 含：matched / unmatched（未识别列）/ missing（缺失必需列）/
    dropped（超行截断）/ numeric_columns。
    """
    df = df.copy()
    report: dict[str, Any] = {"matched": {}, "unmatched": [], "missing": [], "dropped": 0}

    if df.empty:
        return {"df": df, "report": report}

    # 表头行可能出现在第 1 行之后（卖家精灵导出偶带说明行），尝试下探表头
    header_index = None
    for index in range(min(3, len(df))):
        cells = [str(cell).strip() for cell in df.iloc[index].tolist()]
        if any(cell.strip().lower() in _ALIAS_LOOKUP for cell in cells):
            header_index = index
            break
    if header_index is not None:
        df.columns = df.iloc[header_index].tolist()
        df = df.iloc[header_index + 1 :].reset_index(drop=True)

    # 列名归一化：别名 → 标准字段
    column_map: dict[str, str] = {}
    for column in df.columns:
        normalized = str(column).strip().lower()
        matched = _ALIAS_LOOKUP.get(normalized)
        if matched:
            column_map[column] = matched
            report["matched"][str(column)] = matched
        else:
            report["unmatched"].append(str(column))
    df = df.rename(columns=column_map)

    # 必需列校验
    report["missing"] = [field for field in REQUIRED_COLUMNS if field not in df.columns]

    # 数值清洗（非数值 → NaN）
    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    # 行数截断
    if len(df) > max_rows:
        report["dropped"] = len(df) - max_rows
        df = df.head(max_rows)

    report["numeric_columns"] = [column for column in NUMERIC_COLUMNS if column in df.columns]
    return {"df": df, "report": report}


def build_verdict_export(rows: list[dict[str, Any]]) -> str:
    """把 Go/No-Go 决策行序列化为标准 CSV（含证据链引用字段）。"""
    if not rows:
        return ""
    frame = pd.DataFrame(rows)
    export_columns = [
        "category",
        "market",
        "verdict",
        "score",
        "margin_pct",
        "risk_level",
        "hs_code",
        "evidence_source",
        "evidence_fetched_at",
        "evidence_expires_at",
        "generated_at",
    ]
    available = [column for column in export_columns if column in frame.columns]
    return frame[available].to_csv(index=False, encoding="utf-8-sig")


__all__ = [
    "SELLER_MAGIC_FIELD_DICT",
    "build_verdict_export",
    "normalize_seller_magic_csv",
]
