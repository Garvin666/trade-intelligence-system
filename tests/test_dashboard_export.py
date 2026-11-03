"""Dashboard selection report export tests."""

from __future__ import annotations

from pathlib import Path

from src.trade.report import build_launch_report, build_selection_report


SAMPLE = {
    "filters": {
        "category": "cn_changsha_mifen",
        "market": "us",
        "model": "lightgbm_advanced",
        "date_from": "2025-08-16",
        "date_to": "2026-08-07",
        "top": 5,
    },
    "recommendation": {
        "category": "cn_changsha_mifen",
        "market": "us",
        "rank": 1,
        "score": 88.5,
        "forecast_growth": 12.3,
        "search_trend": 9.1,
        "competition": 42.0,
        "review_growth": 6.2,
        "reasons": ["需求增长稳定", "竞争度适中"],
    },
    "trade_decision": {
        "category_name": "辣条",
        "market_name": "美国",
        "risk_level": "medium",
        "risk_message": "政策风险提示",
        "margin_pct": 18.6,
        "effective_tariff_rate": 0.15,
        "duty_usd_per_unit": 2.1,
        "best_logistics": "小包直邮",
        "feasibility_score": 82.0,
        "ip_risk_level": "low",
        "financing_level": "可对接供应链金融",
        "conflict_level": "medium",
        "conflict_decision": "降低备货规模",
    },
    "evidence": [
        {
            "title": "US de minimis 2026 update",
            "link": "https://example.com/de-minimis",
            "snippet": "关税门槛调整影响小包直邮。",
        }
    ],
    "conclusion": "建议优先进入美国辣条市场，先小批量测试。",
    "data_status": {"data_as_of": "2026-08-07"},
}


def test_build_selection_report_writes_markdown_and_pdf(tmp_path: Path) -> None:
    result = build_selection_report(SAMPLE, output_dir=tmp_path)
    markdown_path = result["markdown_path"]
    pdf_path = result["pdf_path"]
    assert markdown_path.exists()
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")
    text = markdown_path.read_text(encoding="utf-8")
    assert "# 跨境电商智能选品决策报告" in text
    assert "## 一、筛选条件" in text
    assert "## 三、贸易决策" in text
    assert "US de minimis 2026 update" in text
    assert "建议优先进入美国辣条市场" in text
    assert result["generated_at"]


def test_build_selection_report_strips_api_keys(tmp_path: Path) -> None:
    payload = {
        **SAMPLE,
        "api_key": "sk-secret-value",
        "search_api_key": "tvly-secret-value",
        "filters": {**SAMPLE["filters"], "api_key": "sk-nested-value"},
    }
    result = build_selection_report(payload, output_dir=tmp_path)
    text = result["markdown"]
    assert "sk-secret-value" not in text
    assert "tvly-secret-value" not in text
    assert "sk-nested-value" not in text


def test_build_selection_report_accepts_list_recommendation(tmp_path: Path) -> None:
    payload = {**SAMPLE, "recommendation": [SAMPLE["recommendation"]]}
    result = build_selection_report(payload, output_dir=tmp_path)
    assert "综合评分" in result["markdown"]


def test_selection_report_uses_timestamped_filenames(tmp_path: Path) -> None:
    first = build_selection_report(
        {**SAMPLE, "generated_at": "2026-08-16T10:00:00"},
        output_dir=tmp_path,
    )
    second = build_selection_report(
        {**SAMPLE, "generated_at": "2026-08-16T11:00:00"},
        output_dir=tmp_path,
    )
    assert first["markdown_path"].name != second["markdown_path"].name
    assert first["pdf_path"].name != second["pdf_path"].name
    assert first["markdown_path"].exists()
    assert second["markdown_path"].exists()


def test_build_selection_report_empty_payload(tmp_path: Path) -> None:
    result = build_selection_report({}, output_dir=tmp_path)
    assert "暂无推荐数据" in result["markdown"]
    assert result["pdf_path"].exists()


def test_build_launch_report_writes_markdown_and_pdf(tmp_path: Path) -> None:
    result = build_launch_report(
        {
            "report": "# 选品立项报告\n\n## 执行摘要\n\n建议：条件式进入。",
            "generated_at": "2026-08-16T10:00:00",
        },
        output_dir=tmp_path,
    )
    markdown_path = result["markdown_path"]
    pdf_path = result["pdf_path"]
    assert markdown_path.exists()
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert "# 选品立项报告" in markdown_path.read_text(encoding="utf-8")
    assert result["generated_at"] == "2026-08-16T10:00:00"


def test_build_launch_report_rejects_empty_markdown(tmp_path: Path) -> None:
    try:
        build_launch_report({"report": "   "}, output_dir=tmp_path)
    except ValueError as exc:
        assert "report 不能为空" in str(exc)
    else:
        raise AssertionError("empty launch report should raise ValueError")


def test_dashboard_builder_has_supplier_status_renderer() -> None:
    root = Path(__file__).resolve().parent.parent
    text = (root / "scripts" / "dashboard_build" / "templates.py").read_text(
        encoding="utf-8"
    )
    assert "supplierStatusHtml" in text
    assert "货源/供应商" in text
