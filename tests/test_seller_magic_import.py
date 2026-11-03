"""C-2 数据连接器：卖家精灵 CSV 导入映射 + 标准导出（含证据链引用）。"""

from __future__ import annotations

import pandas as pd

from src.data.seller_magic_mapping import (
    build_verdict_export,
    normalize_seller_magic_csv,
)


def test_chinese_aliases_map_to_standard_fields() -> None:
    df = pd.DataFrame(
        [
            {"关键词": "辣条 latiao spicy snack", "搜索热度": 1000, "平均价格": 22.5, "月销量": 120},
            {"关键词": "自动饮水机", "搜索热度": 800, "平均价格": 18.0, "月销量": 90},
        ]
    )
    result = normalize_seller_magic_csv(df)
    report = result["report"]
    assert report["matched"]["关键词"] == "keyword"
    assert report["matched"]["搜索热度"] == "search_index"
    assert report["matched"]["平均价格"] == "price_median"
    assert "keyword" in result["df"].columns
    assert "search_index" in result["df"].columns
    assert result["df"]["search_index"].tolist() == [1000, 800]
    assert report["missing"] == []


def test_missing_keyword_column_reported() -> None:
    df = pd.DataFrame([{"搜索热度": 100, "平均价格": 10}])
    report = normalize_seller_magic_csv(df)["report"]
    assert "keyword" in report["missing"]


def test_header_detection_in_later_row() -> None:
    df = pd.DataFrame(
        [
            ["卖家精灵导出", "", ""],
            ["关键词", "搜索热度", "平均价格"],
            ["猫粮", 500, 25.0],
        ]
    )
    result = normalize_seller_magic_csv(df)
    assert "keyword" in result["df"].columns
    assert len(result["df"]) == 1
    assert result["df"].iloc[0]["keyword"] == "猫粮"


def test_numeric_coercion_and_unmatched_columns() -> None:
    df = pd.DataFrame(
        [{"keyword": "A", "月销量": "120", "价格": "22.5", "自定义列": "x"}]
    )
    result = normalize_seller_magic_csv(df)
    assert result["df"]["sales_volume"].tolist() == [120.0]
    assert "自定义列" in result["report"]["unmatched"]


def test_verdict_export_includes_evidence_references() -> None:
    rows = [
        {
            "category": "cn_changsha_mifen",
            "market": "us",
            "verdict": "go",
            "score": 88.5,
            "margin_pct": 12.3,
            "risk_level": "low",
            "hs_code": "3924",
            "evidence_source": "白宫第 14324 号行政命令",
            "evidence_fetched_at": "2026-08-21T00:00:00",
            "evidence_expires_at": "2027-08-29",
            "generated_at": "2026-08-21T00:00:00",
        }
    ]
    csv_text = build_verdict_export(rows)
    assert "verdict" in csv_text
    assert "evidence_source" in csv_text
    assert "evidence_expires_at" in csv_text
    assert "白宫第 14324 号行政命令" in csv_text


def test_verdict_export_empty_rows() -> None:
    assert build_verdict_export([]) == ""
