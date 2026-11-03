"""证据闸测试：缺来源/日期时不得放行 AI 引用。"""

from __future__ import annotations

from src.analysis.evidence import build_evidence_section, check_evidence, evidence_gate


def test_valid_evidence_passes() -> None:
    item = {
        "key": "market_size",
        "title": "市场规模",
        "source": "海关统计",
        "url": "https://example.com",
        "status": "已检索",
    }
    assert check_evidence(item) == []
    assert evidence_gate([item])["valid"] is True


def test_missing_source_fails() -> None:
    item = {"key": "x", "title": "没有来源", "status": "已检索"}
    assert "缺少来源" in check_evidence(item)
    assert evidence_gate([item])["valid"] is False


def test_missing_date_or_url_fails() -> None:
    item = {"key": "y", "title": "没有日期", "source": "某报告"}
    assert "缺少日期或可核验链接" in check_evidence(item)


def test_evidence_section_contains_gate() -> None:
    markdown = build_evidence_section([{"key": "a", "title": "事实", "source": "来源", "status": "待核实"}])
    assert "证据闸" in markdown
    assert "待核实" in markdown
