"""市场日报生成测试。"""

from __future__ import annotations

from src.data.market_daily import (
    build_market_daily_markdown,
    market_daily_status,
    write_market_daily,
)


def test_market_daily_markdown_sections(tmp_path) -> None:
    markdown = build_market_daily_markdown(
        "2026-08-13",
        crawler={"combos": [], "fallback_used": True, "generated_at": "t"},
        policy={"events": []},
        trends={"generated_at": "t", "fallback_used": True},
        rankings={"rows": [], "source_count": 0},
        customs={"rows": [], "source_count": 0},
        anomalies={"rows": [], "source_count": 0},
        suppliers={"rows": [], "source_count": 0},
    )
    assert "# 市场日报" in markdown
    assert "推荐组合" in markdown
    assert "政策与风险" in markdown
    assert "货源/供应商" in markdown
    assert "数据可信度说明" in markdown


def test_market_daily_includes_supplier_section() -> None:
    markdown = build_market_daily_markdown(
        "2026-08-13",
        crawler={"combos": [], "fallback_used": True, "generated_at": "t"},
        policy={"events": []},
        trends={"generated_at": "t", "fallback_used": True},
        rankings={"rows": [], "source_count": 0},
        customs={"rows": [], "source_count": 0},
        anomalies={"rows": [], "source_count": 0},
        suppliers={
            "rows": [
                {
                    "supplier_name": "深圳优选供应链",
                    "category_name": "辣条",
                    "location": "广东 深圳",
                    "service_years": 8.0,
                    "repeat_rate": 0.72,
                    "response_rate": 0.91,
                    "source": "1688_cli",
                }
            ],
            "source_count": 1,
        },
    )
    assert "## 五、货源/供应商" in markdown
    assert "深圳优选供应链" in markdown
    assert "1688_cli" in markdown


def test_write_market_daily_and_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("src.data.market_daily.MARKET_DAILY_OUTPUT_DIR", tmp_path)
    path = write_market_daily("日报", "2026-08-13")
    assert path.exists()
    status = market_daily_status("2026-08-13")
    assert status["enabled"] is True
    assert status["path"] == str(path)
