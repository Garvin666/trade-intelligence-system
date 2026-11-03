"""S9/S6 修复测试：演示数据占位符与导出文件名。"""

from __future__ import annotations

import pandas as pd
import pytest

from src.trade.cost import LandedCostCalculator, LandedCostInput, to_row
from src.trade.decision import build_trade_decision
from src.trade.report import build_selection_report


def test_logistics_row_has_frontend_keys() -> None:
    """S9：物流三方案行必须提供前端读取的 logistics_name / delivery_days。"""
    calculator = LandedCostCalculator()
    result = calculator.calculate(
        LandedCostInput(
            category="cn_latiao",
            market="us",
            unit_price_usd=30.0,
            procurement_cost_cny=80.0,
            payment_code="pingpong",
            logistics_code="small_parcel",
            tariff_rate=0.05,
        )
    )
    row = to_row(result)
    assert row["logistics_name"] == "小包直邮"
    assert row["delivery_days"] == 12


def test_trade_decision_osint_readiness_present() -> None:
    """S9：尽调就绪度由后端提供，前端不再显示 --。"""
    row = build_trade_decision("cn_changsha_mifen", "us", 30.0, 75.0)
    assert row["osint"]["readiness"] in {"ready", "conditional", "not_ready"}
    logistics = row["logistics"]
    assert len(logistics) >= 3
    for option in logistics:
        assert option.get("logistics_name")
        assert option.get("delivery_days")


def test_selection_report_filenames_include_timestamp(tmp_path) -> None:
    """S6：导出报告文件名带时间戳，多次导出不互覆盖。"""
    first = build_selection_report(
        {"category": "cn_changsha_mifen", "market": "us", "generated_at": "2026-08-16T10:00:00"},
        output_dir=tmp_path,
    )
    second = build_selection_report(
        {"category": "cn_changsha_mifen", "market": "us", "generated_at": "2026-08-16T11:00:00"},
        output_dir=tmp_path,
    )
    assert first["markdown_path"].name != second["markdown_path"].name
    assert "2026081610" in first["markdown_path"].name
    assert "2026081611" in second["markdown_path"].name
    assert first["pdf_path"].exists() and second["pdf_path"].exists()
