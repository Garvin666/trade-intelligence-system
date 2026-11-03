"""PNG figure builders for the data-analysis report (S1 split)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import CATEGORIES, MARKETS, category_name, market_name

COMBO_COUNT = len(CATEGORIES) * len(MARKETS)

COLOR_BLUE = "#2563EB"
COLOR_ORANGE = "#F59E0B"
COLOR_GREEN = "#10B981"
COLOR_RED = "#EF4444"
COLOR_SLATE = "#64748B"

def _save(fig: plt.Figure, name: str, out_dir: Path, saved: list[Path]) -> None:
    path = out_dir / name
    fig.savefig(path, dpi=140)
    plt.close(fig)
    saved.append(path)


def _example_combo(history: pd.DataFrame) -> tuple[str, str]:
    """演示用「品类 × 市场」组合。

    优先取历史数据里首行的真实组合，绝不写死类目编码 —— 写死会在品类体系
    切换后指向一个已不存在的类目，导致该图取不到数据而静默画成空白。
    """
    if not history.empty:
        return str(history["category"].iloc[0]), str(history["market"].iloc[0])
    return next(iter(CATEGORIES)), next(iter(MARKETS))


def _fig_industry_market(stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    derived_2024 = round(2.75 / 1.697, 2)
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    bars = ax.bar(
        ["2024（按增速推算）", "2025（官方口径）"],
        [derived_2024, 2.75],
        color=[COLOR_SLATE, COLOR_BLUE],
        width=0.5,
    )
    ax.bar_label(bars, fmt="%.2f 万亿元", padding=3)
    ax.set_ylim(0, 3.4)
    ax.set_ylabel("万亿元")
    ax.set_title("中国跨境电商进出口规模与增速（较 2020 年 +69.7%）")
    ax.spines[["top", "right"]].set_visible(False)
    ax.annotate(
        "2025 年 2.75 万亿元，较 2020 年增长 69.7%\n（国新办 / 海关初步统计）",
        xy=(1, 2.75),
        xytext=(0.35, 2.85),
        fontsize=9,
        color=COLOR_SLATE,
    )
    _save(fig, "industry_market.png", out_dir, saved)


def _fig_policy_timeline(stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    events = stats["industry"]["policy_timeline"]
    dates = [e["date"] for e in events]
    labels = [e["label"] for e in events]
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    y = np.arange(len(events))
    colors = [COLOR_ORANGE if "美国" in e["group"] else COLOR_GREEN for e in events]
    ax.barh(y, [1] * len(events), color=colors, alpha=0.18, height=0.55)
    ax.scatter([0] * len(events), y, s=70, color=colors, zorder=3)
    for i, event in enumerate(events):
        ax.text(0.015, i, f"{event['date']}  {event['label']}", va="center", fontsize=9.5)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_title("国际贸易政策事件时间线（2025-2026）")
    for spine in ax.spines.values():
        spine.set_visible(False)
    _save(fig, "policy_timeline.png", out_dir, saved)


def _fig_category_market_sales(history: pd.DataFrame, out_dir: Path, saved: list[Path]) -> None:
    pivot = history.pivot_table(index="category", columns="market", values="sales_volume", aggfunc="mean")
    pivot.index = [category_name(code) for code in pivot.index]
    pivot.columns = [market_name(code) for code in pivot.columns]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    im = ax.imshow(pivot.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)), pivot.columns)
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            ax.text(j, i, f"{pivot.values[i, j]:.0f}", ha="center", va="center", fontsize=9)
    ax.set_title("品类 × 市场平均销量指数")
    fig.colorbar(im, ax=ax, shrink=0.8)
    _save(fig, "category_market_sales.png", out_dir, saved)


def _fig_search_export(stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    rows = stats["category_summary"]
    labels = [r["name"] for r in rows]
    exports = [r["avg_export"] for r in rows]
    searches = [r["avg_search"] for r in rows]
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.bar(labels, exports, color=COLOR_BLUE, alpha=0.85, label="平均出口金额（万美元）")
    ax.set_ylabel("出口金额（万美元）")
    ax2 = ax.twinx()
    ax2.plot(labels, searches, color=COLOR_ORANGE, marker="o", label="平均搜索热度（0-100）")
    ax2.set_ylabel("搜索热度")
    ax.set_title("品类出口金额与搜索热度对比")
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [line.get_label() for line in lines], loc="upper left", fontsize=9)
    _save(fig, "search_export.png", out_dir, saved)


def _fig_trend_seasonality(history: pd.DataFrame, stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    top1 = stats["recommendation"]["top1"]
    combo = (top1.get("category") or _example_combo(history)[0], top1.get("market") or "sea")
    sub = history[(history["category"] == combo[0]) & (history["market"] == combo[1])].sort_values("date")
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.0))
    axes[0].plot(sub["date"], sub["sales_volume"], color=COLOR_BLUE, linewidth=1.6, label="周销量")
    axes[0].plot(
        sub["date"],
        sub["sales_volume"].rolling(8, min_periods=1).mean(),
        color=COLOR_ORANGE,
        linewidth=2,
        label="8 周移动平均",
    )
    axes[0].set_title(f"{category_name(combo[0])} × {market_name(combo[1])} 销量趋势")
    axes[0].legend(fontsize=8)
    axes[0].tick_params(axis="x", rotation=30, labelsize=8)

    for (cat, market), sub2 in history.groupby(["category", "market"], observed=True):
        series = (sub2["sales_volume"] - sub2["sales_volume"].min()) / max(
            sub2["sales_volume"].max() - sub2["sales_volume"].min(), 1e-9
        )
        axes[1].plot(sub2["date"], series, color=COLOR_SLATE, alpha=0.35, linewidth=0.8)
    axes[1].plot(
        history.groupby("date")["sales_volume"]
        .mean()
        .pipe(lambda s: (s - s.min()) / max(s.max() - s.min(), 1e-9)),
        color=COLOR_GREEN,
        linewidth=2.2,
        label="全部组合均值（归一化）",
    )
    axes[1].set_title("销量趋势（归一化，季节性可见）")
    axes[1].legend(fontsize=8)
    axes[1].tick_params(axis="x", rotation=30, labelsize=8)
    fig.suptitle("典型组合趋势与多组合季节性对比", y=1.02)
    _save(fig, "trend_seasonality.png", out_dir, saved)


def _fig_weekly_seasonality(stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    weekly = stats["seasonality"]["weekly"]
    weeks = [int(item["week"]) for item in weekly]
    values = [float(item["sales_volume"]) for item in weekly]
    fig, ax = plt.subplots(figsize=(8.6, 3.8))
    ax.plot(weeks, values, color=COLOR_BLUE, marker="o", markersize=3, linewidth=1.8)
    peak = stats["seasonality"]["peak_week"]
    ax.axvline(peak, color=COLOR_ORANGE, linestyle="--", linewidth=1.2)
    ax.annotate(f"峰值周：第 {peak} 周", xy=(peak, max(values)), xytext=(peak - 8, max(values) * 0.96), fontsize=9)
    ax.set_xlabel("周序（ISO 周）")
    ax.set_ylabel("平均销量指数")
    ax.set_title("周粒度季节性模式（跨组合平均）")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "weekly_seasonality.png", out_dir, saved)


def _fig_model_mape(stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    baseline = stats["model_metrics"]["baseline"]
    advanced = stats["model_metrics"]["advanced"]
    labels = [
        f"{category_name(item['category'])[:2]}×{market_name(item['market'])[:2]}" for item in baseline
    ]
    x = np.arange(len(baseline))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9.4, 4.4))
    ax.bar(x - width / 2, [float(m["mape"]) for m in baseline], width, label="Prophet 基线", color=COLOR_SLATE)
    ax.bar(x + width / 2, [float(m["mape"]) for m in advanced], width, label="LightGBM 进阶", color=COLOR_BLUE)
    ax.axhline(
        stats["model_metrics"]["baseline_avg_mape"],
        color=COLOR_ORANGE,
        linestyle="--",
        linewidth=1,
        label=f"基线均值 {stats['model_metrics']['baseline_avg_mape']:.2f}%",
    )
    ax.axhline(
        stats["model_metrics"]["advanced_avg_mape"],
        color=COLOR_GREEN,
        linestyle="--",
        linewidth=1,
        label=f"进阶均值 {stats['model_metrics']['advanced_avg_mape']:.2f}%",
    )
    ax.set_xticks(x, labels, rotation=45, fontsize=8)
    ax.set_ylabel("MAPE（%）")
    ax.set_title(f"双模型 MAPE 对比（{COMBO_COUNT} 组合）")
    ax.legend(fontsize=8, ncol=2)
    _save(fig, "model_mape.png", out_dir, saved)


def _fig_forecast_interval(history: pd.DataFrame, forecast: pd.DataFrame, out_dir: Path, saved: list[Path]) -> None:
    combo = _example_combo(history)
    hist = history[(history["category"] == combo[0]) & (history["market"] == combo[1])].sort_values("date")
    fc = forecast[
        (forecast["category"] == combo[0])
        & (forecast["market"] == combo[1])
        & (forecast["model"] == "lightgbm_advanced")
    ].sort_values("date")
    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    ax.plot(hist["date"], hist["sales_volume"], color=COLOR_SLATE, linewidth=1.6, label="历史销量")
    if not fc.empty:
        ax.fill_between(
            fc["date"],
            fc["yhat_lower"],
            fc["yhat_upper"],
            color=COLOR_BLUE,
            alpha=0.18,
            label="80% 置信区间",
        )
        ax.plot(fc["date"], fc["yhat"], color=COLOR_BLUE, linestyle="--", linewidth=2, label="预测销量")
    ax.set_title(
        f"{category_name(combo[0])} × {market_name(combo[1])}：未来 90 天预测与置信区间（LightGBM）"
    )
    ax.legend(fontsize=8)
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    ax.set_ylabel("销量指数")
    _save(fig, "forecast_interval.png", out_dir, saved)


def _fig_recommend_composition(stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    top10 = stats["recommendation"]["top10"]
    labels = [
        f"{r['category_name']}×{r['market_name']}" for r in top10
    ][::-1]
    rows = list(reversed(top10))

    def norm(key: str) -> list[float]:
        values = [float(r[key]) for r in rows]
        low, high = min(values), max(values)
        return [(v - low) / (high - low) if high > low else 0.5 for v in values]

    weights = {"forecast_growth": 0.35, "search_trend": 0.30, "competition_rev": 0.25, "review_growth": 0.10}
    comp_forecast = [v * weights["forecast_growth"] for v in norm("forecast_growth")]
    comp_search = [v * weights["search_trend"] for v in norm("search_trend")]
    comp_competition = [(100 - float(r["competition"])) / 100 * weights["competition_rev"] for r in rows]
    comp_review = [v * weights["review_growth"] for v in norm("review_growth")]

    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.barh(labels, comp_forecast, color="#93C5FD", label="预测增长")
    ax.barh(labels, comp_search, left=comp_forecast, color="#FCD34D", label="搜索趋势")
    ax.barh(labels, comp_competition, left=[a + b for a, b in zip(comp_forecast, comp_search)], color="#6EE7B7", label="竞争反向")
    ax.barh(
        labels,
        comp_review,
        left=[a + b + c for a, b, c in zip(comp_forecast, comp_search, comp_competition)],
        color="#F9A8D4",
        label="评论增长",
    )
    ax.set_xlabel("近似构成（归一化 × 权重）")
    ax.set_title("Top 10 推荐评分构成（示意）")
    ax.legend(fontsize=8, ncol=2)
    _save(fig, "recommend_composition.png", out_dir, saved)


def _fig_landed_cost(stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    options = stats["trade"]["logistics_options"]
    if not options:
        return
    names = list(options.keys())
    costs = list(options.values())
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    bars = ax.bar(names, costs, color=[COLOR_BLUE, COLOR_GREEN, COLOR_ORANGE], width=0.5)
    ax.bar_label(bars, fmt="%.1f 美元", padding=3)
    ax.set_ylabel("平均单件到岸成本（美元）")
    ax.set_title(f"物流三方案平均到岸成本对比（{COMBO_COUNT} 组合）")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "landed_cost.png", out_dir, saved)


def _fig_policy_financing(stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    rows = stats["trade"]["rows"]
    if not rows:
        return
    colors = {"high": COLOR_RED, "medium": COLOR_ORANGE, "low": COLOR_GREEN}
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    for risk in ("high", "medium", "low"):
        sub = [r for r in rows if r.get("risk_level") == risk]
        if not sub:
            continue
        ax.scatter(
            [float(r["financing_ready_score"]) for r in sub],
            [float(r["margin_pct"]) for r in sub],
            s=70,
            color=colors.get(risk, COLOR_SLATE),
            alpha=0.75,
            label=f"风险：{ {'high': '高', 'medium': '中', 'low': '低'}[risk] }",
        )
    for r in rows[:6]:
        ax.annotate(
            f"{r['category_name'][:2]}×{r['market_name'][:2]}",
            (float(r["financing_ready_score"]), float(r["margin_pct"])),
            fontsize=8,
            xytext=(4, 4),
            textcoords="offset points",
        )
    ax.axhline(0, color=COLOR_SLATE, linestyle=":", linewidth=1)
    ax.set_xlabel("融资就绪评分（0-100）")
    ax.set_ylabel("利润率（%）")
    ax.set_title(f"政策风险 × 融资就绪 × 利润率（{COMBO_COUNT} 组合）")
    ax.legend(fontsize=8)
    _save(fig, "policy_financing.png", out_dir, saved)


def _fig_crawler_signals(stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    crawler = stats.get("crawler") or {}
    combos = crawler.get("combos") or []
    if not combos:
        return
    rows = combos[:12]
    names = [
        f"{c.get('category_name', c.get('category', ''))}×{c.get('market_name', c.get('market', ''))}"
        for c in rows
    ]
    trends = [float(c.get("pageview_trend_pct") or 0) for c in rows]
    sources = [int(c.get("source_count") or 0) for c in rows]
    fig, ax = plt.subplots(figsize=(8.6, 4.0))
    x = np.arange(len(names))
    ax.bar(x - 0.2, trends, width=0.4, color=COLOR_BLUE, label="浏览量趋势%")
    ax.bar(x + 0.2, sources, width=0.4, color=COLOR_GREEN, label="来源数")
    ax.set_xticks(x, names, rotation=35, fontsize=8)
    ax.set_ylabel("指标")
    ax.set_title("真实爬虫信号：浏览量趋势与来源数")
    ax.legend(fontsize=8)
    _save(fig, "crawler_signals.png", out_dir, saved)


def _fig_customs_exports(stats: dict[str, Any], out_dir: Path, saved: list[Path]) -> None:
    customs = stats.get("customs") or {}
    rows = customs.get("rows") or []
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    if not rows:
        ax.text(
            0.5,
            0.5,
            "暂无真实海关出口数据，请运行每日更新或接入 UN Comtrade 后重跑",
            ha="center",
            va="center",
            fontsize=10,
            color=COLOR_SLATE,
            transform=ax.transAxes,
        )
        ax.set_title("中国 HS4 品类出口信号（暂无真实数据）")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        _save(fig, "customs_exports.png", out_dir, saved)
        return
    labels = [row.get("category_name", row.get("category", "-")) for row in rows]
    values = [float(row.get("value") or 0) for row in rows]
    bars = ax.bar(labels, values, color=COLOR_BLUE, width=0.55)
    ax.bar_label(bars, fmt="%.0f", fontsize=8)
    ax.set_xticks(range(len(labels)), labels, rotation=40, fontsize=8)
    ax.set_ylabel("出口额（USD）")
    provider = customs.get("provider") or "mock"
    ax.set_title(f"中国 HS4 品类出口信号（{customs.get('period') or '-'}，来源 {provider}）")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "customs_exports.png", out_dir, saved)
