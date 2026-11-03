"""数据分析报告模块测试。"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.config import CATEGORIES, MARKETS, WEEKS_HISTORY
from src.analysis.report import (
    INDUSTRY_FACTS,
    compute_stats,
    load_all,
    render_markdown,
)


def test_compute_stats_overview() -> None:
    data = load_all()
    stats = compute_stats(
        data["history"],
        data["forecast"],
        data["recommendations"],
        data["metrics"],
        data["trade"],
    )
    overview = stats["overview"]
    assert overview["history_rows"] == len(CATEGORIES) * len(MARKETS) * WEEKS_HISTORY
    assert overview["weeks"] == WEEKS_HISTORY
    assert overview["categories"] == len(CATEGORIES)
    assert overview["markets"] == len(MARKETS)
    assert overview["forecast_rows"] == len(CATEGORIES) * len(MARKETS) * 90 * 2
    assert 0 < overview["advanced_mape_avg"] < overview["baseline_mape_avg"]
    assert overview["mape_improvement_pct"] > 0


def test_compute_stats_trade_and_recommendation() -> None:
    data = load_all()
    stats = compute_stats(
        data["history"],
        data["forecast"],
        data["recommendations"],
        data["metrics"],
        data["trade"],
    )
    assert 0 < stats["trade"]["high_risk"] <= len(CATEGORIES) * len(MARKETS)
    # 每日更新会刷新推荐分数，只校验结构不变量
    assert stats["recommendation"]["top1"]["rank"] == 1
    assert stats["recommendation"]["top1"]["score"] > 0
    assert stats["recommendation"]["market_counts"]


def test_render_markdown_has_required_sections() -> None:
    data = load_all()
    stats = compute_stats(
        data["history"],
        data["forecast"],
        data["recommendations"],
        data["metrics"],
        data["trade"],
    )
    text = render_markdown(stats)
    for section in ["结论摘要", "行业与市场数据分析", "探索性数据分析", "模型评估分析", "贸易决策情景分析", "待办 / 待核实清单", "附录 A：行业数据来源表"]:
        assert section in text
    assert re.search(r"\d+\.\d+%", text)
    assert "待核实" in text


def test_industry_facts_registered() -> None:
    assert len(INDUSTRY_FACTS) >= 5
    assert any(item["status"] == "已检索" for item in INDUSTRY_FACTS)
    assert any(item["status"] == "待核实" for item in INDUSTRY_FACTS)


def test_figures_directory_has_pngs() -> None:
    from src.analysis.report import FIGURES_DIR

    pngs = list(Path(FIGURES_DIR).glob("*.png"))
    assert len(pngs) >= 10


def test_render_markdown_has_crawler_section() -> None:
    data = load_all()
    stats = compute_stats(
        data["history"],
        data["forecast"],
        data["recommendations"],
        data["metrics"],
        data["trade"],
    )
    text = render_markdown(stats)
    assert "真实爬虫信号" in text
    assert "crawler_signals.png" in text
    assert stats["crawler"]["count"] >= 0
