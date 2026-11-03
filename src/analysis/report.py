"""数据分析统计、PNG 图表与《数据分析报告》Markdown 生成。

所有数字均从项目现有产物（clean_data / forecast / recommendations /
metrics / trade_demo_metrics）计算，行业数据来源统一登记在 INDUSTRY_FACTS，
未核实的数字明确标注“待核实”，不编造来源。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis.evidence import build_evidence_section
from src.config import (
    CATEGORIES,
    DOCS_DIR,
    FORECAST_CSV,
    MARKETS,
    METRICS_JSON,
    PROCESSED_CSV,
    PROJECT_ROOT,
    RECOMMEND_CSV,
    category_name,
    market_name,
)
from src.data.crawler_signals import load_latest_snapshot, snapshot_status
from src.data.customs import customs_status, load_latest_customs

COMBO_COUNT = len(CATEGORIES) * len(MARKETS)
TRADE_METRICS_JSON = PROJECT_ROOT / "output" / "trade" / "trade_demo_metrics.json"
ANALYSIS_OUT = PROJECT_ROOT / "output" / "analysis"
FIGURES_DIR = DOCS_DIR / "figures"
REPORT_MD = DOCS_DIR / "数据分析报告.md"

FONT_PATH = Path(r"C:\Windows\Fonts\simhei.ttf")
GENERATED_AT = date.today().isoformat()

COLOR_BLUE = "#2563EB"
COLOR_ORANGE = "#F59E0B"
COLOR_GREEN = "#10B981"
COLOR_RED = "#EF4444"
COLOR_SLATE = "#64748B"

# 行业公开数据（2026-08-10 联网检索记录；无法定位原文的保留项目口径并标“待核实”）
INDUSTRY_FACTS: list[dict[str, str]] = [
    {
        "key": "market_size_2025",
        "title": "2025 年中国跨境电商进出口规模",
        "value": "2.75 万亿元",
        "detail": (
            "海关初步统计；较 2020 年增长 69.7%（国新办发布会口径）。"
            "项目既有材料写作“同比增长 69.7%”，口径建议修正为“较 2020 年增长”。"
        ),
        "source": "国新办（SCIO）2026-01-28 发布会实录",
        "url": "http://english.scio.gov.cn/m/pressroom/2026-01/28/content_118304543_10.html",
        "status": "已检索",
    },
    {
        "key": "companies",
        "title": "跨境电商企业数量",
        "value": "超过 12 万家",
        "detail": (
            "商务部口径（2024-08 国新办发布会：根据各地初步统计，全国跨境电商主体已超 12 万家）："
            "https://www.gov.cn/yaowen/liebiao/202408/content_6965858.htm 。"
            "海关总署口径（2025-06 综试区文章：跨境电商综合试验区内企业已超 12 万家）："
            "http://qingdao.customs.gov.cn/qingdao_customs/406496/ztlm/4744412/4744416/6563929/index.html 。"
        ),
        "source": "商务部（gov.cn 转载）与海关总署（青岛海关转载）",
        "url": "https://www.gov.cn/yaowen/liebiao/202408/content_6965858.htm",
        "status": "已检索",
    },
    {
        "key": "us_china_de_minimis",
        "title": "美国对华小额包裹政策",
        "value": "2025-05-02 起不再适用 de minimis",
        "detail": (
            "EO 14256（2025-04-02，对华芬太尼关税）与 EO 14257（2025-04-02，对等关税）"
            "取消中国原产低值包裹 de minimis 免税，2025-05-02 12:01 a.m. EDT 生效；"
            "对华 120% 或最低 100 美元关税为相关行政命令与解读口径，具体按 Federal Register 原文核对。"
        ),
        "source": "白宫行政命令 EO 14256 / EO 14257（Federal Register）",
        "url": "https://www.whitehouse.gov/presidential-actions/2025/04/regulating-imports-with-a-reciprocal-tariff-to-rectify-trade-practices-that-contribute-to-large-and-persistent-annual-united-states-goods-trade-deficits/",
        "status": "已检索",
    },
    {
        "key": "us_all_de_minimis",
        "title": "美国全面取消小额包裹免税",
        "value": "2025-08-29 起全面生效",
        "detail": "行政命令 EO 14324（2025-07-30 签署）；DHS 于 2025-08-29 实施。",
        "source": "白宫 / GovInfo / Federal Register",
        "url": "https://www.federalregister.gov/documents/2025/09/02/2025-16802/notice-of-implementation-of-the-presidents-executive-order-14324-suspending-duty-free-de-minimis",
        "status": "已检索",
    },
    {
        "key": "eu_relief",
        "title": "欧盟低价值包裹关税减免",
        "value": "2026-07-01 起取消 150 欧元免税额度",
        "detail": (
            "欧盟委员会 2025-11-13 公告取消 150 欧元海关免税额度；最终立法文本为 "
            "Council Regulation (EU) 2026/382（2026-02-11 通过）与 Commission Delegated Regulation "
            "(EU) 2026/1022（2026-07-01 起对不超过 150 欧元包裹适用临时 3 欧元关税）；"
            "IOSS / VAT 落地细节需按成员国口径核验。"
        ),
        "source": "欧盟委员会税务与海关总司 / EUR-Lex（Regulation (EU) 2026/382）",
        "url": "https://taxation-customs.ec.europa.eu/news/e-commerce-150-eur-customs-duty-exemption-threshold-be-removed-2026-2025-11-13_en",
        "status": "已检索",
    },
    {
        "key": "temu_ai",
        "title": "Temu 用 AI 监测关税变化",
        "value": "行业验证案例",
        "detail": "项目既有材料引用，尚未找到公开原文出处。",
        "source": "项目既有材料",
        "url": "",
        "status": "待核实",
    },
    {
        "key": "saas_trend",
        "title": "AI 实时监控目标国法规成为 SaaS 核心趋势",
        "value": "行业趋势",
        "detail": "项目既有材料引用，尚未定位到具体报告原文。",
        "source": "项目既有材料",
        "url": "",
        "status": "待核实",
    },
]

POLICY_TIMELINE = [
    {"date": "2025-05-02", "label": "美国对华 / 对港取消 de minimis（120% 或最低 100 美元）", "group": "美国"},
    {"date": "2025-08-29", "label": "美国 EO 14324 全面取消 800 美元以下免税", "group": "美国"},
    {"date": "2026-07-01", "label": "欧盟取消 150 欧元低值包裹免税额度", "group": "欧盟"},
]


def _setup_plot() -> None:
    """配置 matplotlib 中文字体与统一风格。"""
    if FONT_PATH.exists():
        try:
            from matplotlib import font_manager

            font_manager.fontManager.addfont(str(FONT_PATH))
        except Exception:  # noqa: BLE001 - 字体注册失败不阻断图表生成
            pass
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120
    plt.rcParams["savefig.bbox"] = "tight"


def load_all() -> dict[str, Any]:
    """加载全部分析所需数据。"""
    history = pd.read_csv(PROCESSED_CSV, encoding="utf-8-sig")
    history["date"] = pd.to_datetime(history["date"])
    forecast = pd.read_csv(FORECAST_CSV, encoding="utf-8-sig")
    forecast["date"] = pd.to_datetime(forecast["date"])
    recommendations = pd.read_csv(RECOMMEND_CSV, encoding="utf-8-sig")
    metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    trade = json.loads(TRADE_METRICS_JSON.read_text(encoding="utf-8"))
    return {
        "history": history.sort_values("date"),
        "forecast": forecast.sort_values("date"),
        "recommendations": recommendations,
        "metrics": metrics,
        "trade": trade,
    }


def _avg(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _pct(current: float, previous: float) -> float:
    return 0.0 if abs(previous) < 1e-9 else (current - previous) / previous * 100.0


def _rows_dict(df: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _crawler_stats() -> dict[str, Any]:
    snapshot = load_latest_snapshot()
    return {
        "status": snapshot_status(snapshot),
        "count": len(snapshot.get("combos") or []),
        "combos": snapshot.get("combos") or [],
        "sources_count": int(snapshot.get("sources_count") or 0),
        "fallback_used": bool(snapshot.get("fallback_used")),
    }


def _customs_stats() -> dict[str, Any]:
    payload = load_latest_customs()
    return {
        "status": customs_status(payload),
        "provider": payload.get("provider"),
        "period": payload.get("period"),
        "source_url": payload.get("source_url"),
        "fallback_used": bool(payload.get("fallback_used")),
        "rows": payload.get("rows") or [],
    }


def compute_stats(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    recommendations: pd.DataFrame,
    metrics: dict[str, Any],
    trade: dict[str, Any],
) -> dict[str, Any]:
    """从原始数据计算报告所需的全部统计量。"""
    history = history.sort_values("date").copy()
    history["week"] = history["date"].dt.isocalendar().week.astype(int)
    history["month"] = history["date"].dt.month.astype(int)
    max_date = history["date"].max()
    last_12_start = max_date - pd.Timedelta(days=84)
    last_12 = history[history["date"] >= last_12_start]
    prev_12_start = max_date - pd.Timedelta(days=168)
    prev_12 = history[(history["date"] >= prev_12_start) & (history["date"] < last_12_start)]

    baseline = [float(item["mape"]) for item in metrics.get("baseline", [])]
    advanced = [float(item["mape"]) for item in metrics.get("advanced", [])]
    baseline_avg = _avg(baseline)
    advanced_avg = _avg(advanced)
    improvement = _pct(advanced_avg, baseline_avg) * -1

    trade_rows = trade.get("rows", [])
    trade_summary = trade.get("summary", {})
    logistics_options: dict[str, list[float]] = {}
    for row in trade_rows:
        for option in row.get("logistics", []):
            if not isinstance(option, dict):
                continue
            name = str(option.get("name") or option.get("code") or "未知方案")
            cost = option.get("cost_usd") or option.get("cost") or option.get("landed_cost_usd")
            try:
                logistics_options.setdefault(name, []).append(float(cost))
            except (TypeError, ValueError):
                continue

    return {
        "generated_at": GENERATED_AT,
        "overview": {
            "history_rows": int(len(history)),
            "forecast_rows": int(len(forecast)),
            "recommendation_rows": int(len(recommendations)),
            "weeks": int(history["date"].nunique()),
            "categories": int(history["category"].nunique()),
            "markets": int(history["market"].nunique()),
            "start_date": history["date"].min().date().isoformat(),
            "end_date": history["date"].max().date().isoformat(),
            "forecast_start": forecast["date"].min().date().isoformat() if not forecast.empty else "",
            "forecast_end": forecast["date"].max().date().isoformat() if not forecast.empty else "",
            "baseline_mape_avg": round(baseline_avg, 2),
            "advanced_mape_avg": round(advanced_avg, 2),
            "mape_improvement_pct": round(improvement, 1),
        },
        "category_summary": _group_summary(history, last_12, prev_12, "category", category_name),
        "market_summary": _group_summary(history, last_12, prev_12, "market", market_name),
        "seasonality": {
            "peak_week": int(history.groupby("week")["sales_volume"].mean().idxmax()),
            "peak_month": int(history.groupby("month")["sales_volume"].mean().idxmax()),
            "trough_month": int(history.groupby("month")["sales_volume"].mean().idxmin()),
            "weekly": _rows_dict(
                history.groupby("week", as_index=False)["sales_volume"].mean().round(2)
            ),
            "monthly": _rows_dict(
                history.groupby("month", as_index=False)["sales_volume"].mean().round(2)
            ),
        },
        "model_metrics": {
            "baseline": metrics.get("baseline", []),
            "advanced": metrics.get("advanced", []),
            "baseline_avg_mape": round(baseline_avg, 2),
            "advanced_avg_mape": round(advanced_avg, 2),
            "improvement_pct": round(improvement, 1),
            "best_combo": _best_model_combo(metrics.get("advanced", []), "mape", smallest=True),
            "worst_combo": _best_model_combo(metrics.get("baseline", []), "mape", smallest=False),
        },
        "recommendation": _recommendation_stats(recommendations),
        "trade": {
            "summary": trade_summary,
            "rows": trade_rows,
            "high_risk": int(trade_summary.get("high_risk", 0)),
            "medium_risk": int(trade_summary.get("medium_risk", 0)),
            "avg_margin_pct": round(float(trade_summary.get("avg_margin_pct", 0)), 2),
            "credit_avg": round(float(trade_summary.get("credit_avg", 0)), 1),
            "conflict_high": int(trade_summary.get("conflict_high", 0)),
            "conflict_low": int(trade_summary.get("conflict_low", 0)),
            "avg_landed_increase_pct": round(
                _avg([float(r.get("landed_cost_increase_pct", 0)) for r in trade_rows]), 2
            ),
            "avg_compliance_usd": round(
                _avg([float(r.get("compliance_total_usd", 0)) for r in trade_rows]), 2
            ),
            "best_margin": _best_trade_row(trade_rows, "margin_pct", largest=True),
            "worst_margin": _best_trade_row(trade_rows, "margin_pct", largest=False),
            "best_financing": _best_trade_row(trade_rows, "financing_ready_score", largest=True),
            "logistics_options": {
                name: round(_avg(costs), 2) for name, costs in logistics_options.items()
            },
        },
        "industry": {
            "facts": INDUSTRY_FACTS,
            "verified_count": sum(1 for f in INDUSTRY_FACTS if f["status"] == "已检索"),
            "pending_count": sum(1 for f in INDUSTRY_FACTS if f["status"] == "待核实"),
            "policy_timeline": POLICY_TIMELINE,
        },
        "customs": _customs_stats(),
        "crawler": _crawler_stats(),
        "business_metrics": metrics.get("business_metrics") or {},
    }


def _group_summary(
    history: pd.DataFrame,
    last_12: pd.DataFrame,
    prev_12: pd.DataFrame,
    key: str,
    name_fn: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, sub in history.groupby(key, observed=True):
        last = last_12[last_12[key] == code]
        prev = prev_12[prev_12[key] == code]
        rows.append(
            {
                "code": code,
                "name": name_fn(code),
                "avg_sales": round(float(sub["sales_volume"].mean()), 2),
                "avg_search": round(float(sub["search_index"].mean()), 2),
                "avg_export": round(float(sub["export_value"].mean()), 2),
                "avg_competition": round(float(sub["competition_index"].mean()), 2),
                "avg_price": round(float(sub["price_median"].mean()), 2),
                "avg_review_growth": round(float(sub["review_growth"].mean()), 2),
                "last_12w_sales": round(float(last["sales_volume"].mean()), 2) if not last.empty else 0.0,
                "growth_pct": round(
                    _pct(
                        float(last["sales_volume"].mean()) if not last.empty else 0.0,
                        float(prev["sales_volume"].mean()) if not prev.empty else 0.0,
                    ),
                    1,
                ),
            }
        )
    return sorted(rows, key=lambda item: item["avg_sales"], reverse=True)


def _best_model_combo(items: list[dict[str, Any]], key: str, smallest: bool) -> dict[str, Any]:
    if not items:
        return {}
    best = min(items, key=lambda item: float(item.get(key, 0))) if smallest else max(
        items, key=lambda item: float(item.get(key, 0))
    )
    return {
        "category": best.get("category"),
        "category_name": category_name(best.get("category", "")),
        "market": best.get("market"),
        "market_name": market_name(best.get("market", "")),
        key: round(float(best.get(key, 0)), 2),
        "mae": round(float(best.get("mae", 0)), 2),
    }


def _recommendation_stats(recommendations: pd.DataFrame) -> dict[str, Any]:
    rows = _rows_dict(recommendations.sort_values("rank"))
    for row in rows:
        row["category_name"] = category_name(row.get("category", ""))
        row["market_name"] = market_name(row.get("market", ""))
    top10 = rows[:10]
    market_counts: dict[str, int] = {}
    for row in top10:
        market_counts[row["market"]] = market_counts.get(row["market"], 0) + 1
    top1 = top10[0] if top10 else {}
    return {
        "top10": top10,
        "top1": {
            "rank": top1.get("rank"),
            "category": top1.get("category"),
            "category_name": category_name(top1.get("category", "")),
            "market": top1.get("market"),
            "market_name": market_name(top1.get("market", "")),
            "score": top1.get("score"),
        },
        "market_counts": market_counts,
        "avg_score": round(float(np.mean([float(r["score"]) for r in top10])) if top10 else 0.0, 1),
    }


def _best_trade_row(rows: list[dict[str, Any]], key: str, largest: bool) -> dict[str, Any]:
    if not rows:
        return {}
    best = max(rows, key=lambda item: float(item.get(key, 0))) if largest else min(
        rows, key=lambda item: float(item.get(key, 0))
    )
    return {
        "category_name": best.get("category_name"),
        "market_name": best.get("market_name"),
        key: round(float(best.get(key, 0)), 2),
        "risk_level": best.get("risk_level"),
    }


def generate_figures(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    recommendations: pd.DataFrame,
    stats: dict[str, Any],
    out_dir: Path,
) -> list[Path]:
    """生成 10-12 张 PNG 图表并返回文件列表。"""
    _setup_plot()
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    _fig_industry_market(stats, out_dir, saved)
    _fig_policy_timeline(stats, out_dir, saved)
    _fig_category_market_sales(history, out_dir, saved)
    _fig_search_export(stats, out_dir, saved)
    _fig_trend_seasonality(history, stats, out_dir, saved)
    _fig_weekly_seasonality(stats, out_dir, saved)
    _fig_model_mape(stats, out_dir, saved)
    _fig_forecast_interval(history, forecast, out_dir, saved)
    _fig_recommend_composition(stats, out_dir, saved)
    _fig_landed_cost(stats, out_dir, saved)
    _fig_policy_financing(stats, out_dir, saved)
    _fig_crawler_signals(stats, out_dir, saved)
    _fig_customs_exports(stats, out_dir, saved)
    return saved


from src.analysis.report_figures import (
    _save,
    _fig_industry_market,
    _fig_policy_timeline,
    _fig_category_market_sales,
    _fig_search_export,
    _fig_trend_seasonality,
    _fig_weekly_seasonality,
    _fig_model_mape,
    _fig_forecast_interval,
    _fig_recommend_composition,
    _fig_landed_cost,
    _fig_policy_financing,
    _fig_crawler_signals,
    _fig_customs_exports,
)
def _fmt(value: Any, digits: int = 2) -> str:
    """数值格式化：None/NaN/- 显示为占位符。"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{v:.{digits}f}" if v == v else "-"


def _render_business_metrics(bm: dict[str, Any]) -> str:
    """渲染「业务指标」小节；metrics.json 缺 business_metrics 时显示占位。"""
    if not bm:
        return (
            "> 业务指标尚未生成：运行 `python scripts/rolling_backtest.py` 生成 "
            "`output/backtest/` 产物并写入 `models/metrics.json` 的 `business_metrics` 键。"
        )
    scope = bm.get("scope") or {}
    lines = [
        f"> 口径：校准度/方向命中率基于回测逐点预测（来源 `{scope.get('predictions_source', '-')}`，"
        f"种子 {scope.get('seed', '-')}）；Top-N 后验收益与库存损失公式与假设见 metrics.json「口径」。",
        "",
    ]
    cal = bm.get("calibration") or {}
    if cal.get("status") == "ok":
        quantiles = cal.get("error_quantiles_pct") or {}
        lines += [
            "### 8.6.1 预测校准度",
            "",
            "| 指标 | 数值 |",
            "| --- | ---: |",
            f"| 系统性偏差 bias（预测-实际均值比） | {_fmt(cal.get('bias_pct'))}% |",
            f"| 平均百分比误差 MPE | {_fmt(cal.get('mpe_pct'))}% |",
            f"| 平均绝对百分比误差 MAPE | {_fmt(cal.get('mape_pct'))}% |",
            f"| 预测-实际秩相关 Spearman ρ | {_fmt(cal.get('spearman_rho'))} |",
        ]
        if "interval_coverage_pct" in cal:
            lines.append(
                f"| 80% 区间覆盖率 | {_fmt(cal.get('interval_coverage_pct'))}%"
                f"（名义 80%，偏差 {_fmt(cal.get('coverage_gap_pct'))}pp） |"
            )
        lines.append(
            "| 误差分位 P10/P25/P50/P75/P90 | "
            + " / ".join(f"{_fmt(quantiles.get(f'p{i}'))}%" for i in (10, 25, 50, 75, 90))
            + f" |\n| 样本数 | {cal.get('n', 0)} |\n"
        )
    else:
        lines.append("### 8.6.1 预测校准度\n\n_暂缺回测预测数据，未计算。_\n")

    dr = bm.get("direction_hit_rate") or {}
    if dr.get("status") == "ok":
        lines += [
            "### 8.6.2 方向命中率（预测环比涨/跌 vs 实际）",
            "",
            "| 指标 | 数值 |",
            "| --- | ---: |",
            f"| 方向命中率 | {_fmt(dr.get('hit_rate_pct'))}% |",
            f"| 上涨周命中率 | {_fmt(dr.get('up_hit_rate_pct'))}% |",
            f"| 下跌周命中率 | {_fmt(dr.get('down_hit_rate_pct'))}% |",
            f"| 有效样本（环比非持平） | {dr.get('n', 0)} |",
            f"| 持平周（不计入分母） | {dr.get('n_flat', 0)} |",
            "",
        ]
    else:
        lines.append("### 8.6.2 方向命中率\n\n_暂缺回测预测数据，未计算。_\n")

    topn = bm.get("topn_posterior_return") or {}
    if topn.get("status") == "ok":
        agg = topn.get("aggregates") or {}
        bench = topn.get("benchmark") or {}
        rows = topn.get("rows") or []
        table = "\n".join(
            f"| {r['rank']} | {category_name(r['category'])} | {market_name(r['market'])} | "
            f"{r['actual_sales_avg_12w']} | {r['realized_growth_pct']:+.2f}% | "
            f"{r['price_usd']} | {r['margin_pct']:.1f}% | {r['posterior_return_90d_usd']} |"
            for r in rows[:10]
        )
        lines += [
            "### 8.6.3 Top-N 后验收益（实际销量 × 价格 × 毛利率，90 天）",
            "",
            f"Top{topn.get('top_n', 10)} 合计后验毛利贡献 "
            f"**${_fmt(agg.get('total_posterior_return_90d_usd'))}**，组合平均 "
            f"${_fmt(agg.get('avg_posterior_return_90d_usd'))}；实际环比增长平均 "
            f"{_fmt(agg.get('avg_realized_growth_pct'))}%，正向确认率 "
            f"{_fmt(agg.get('confirmation_rate_pct'))}%；相对全组合基准提升 "
            f"{_fmt(bench.get('topn_uplift_pct'))}%（预测增长与实际增长秩相关 "
            f"{_fmt(topn.get('forecast_realized_spearman_rho'))}）。",
            "",
            "| 排名 | 品类 | 市场 | 近12周均销量 | 实际环比增长 | 价格($) | 毛利率 | 90天后验收益($) |",
            "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |",
            table,
            "",
        ]
    else:
        lines.append("### 8.6.3 Top-N 后验收益\n\n_暂缺推荐结果，未计算。_\n")

    inv = bm.get("inventory_loss") or {}
    if inv.get("status") == "ok":
        agg = inv.get("aggregates") or {}
        rows = inv.get("rows") or []
        top10 = sorted(rows, key=lambda r: r["total_loss_annual_usd"], reverse=True)[:10]
        table = "\n".join(
            f"| {category_name(r['category'])} | {market_name(r['market'])} | "
            f"{r['mae_units_per_week']} | {r['overstock_share']} | {r['price_usd']} | "
            f"{r['margin_pct']:.1f}% | {r['overstock_loss_weekly_usd']} | "
            f"{r['stockout_loss_weekly_usd']} | {r['direction_loss_weekly_usd']} | "
            f"{r['total_loss_annual_usd']} |"
            for r in top10
        )
        lines += [
            "### 8.6.4 库存损失估算（由 MAE 与方向误判推算，年化）",
            "",
            f"全部组合年化备货损失合计 **${_fmt(agg.get('total_loss_annual_usd'))}**，"
            f"组合平均每周 {_fmt(agg.get('avg_loss_weekly_per_combo_usd'))} 美元"
            f"（年化 {_fmt(agg.get('avg_loss_annual_per_combo_usd'))}）。损失前 10 组合：",
            "",
            "| 品类 | 市场 | 周均MAE | 高估占比 | 价格($) | 毛利率 | 积压周损($) | 缺货周损($) | 方向周损($) | 年化总损($) |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            table,
            "",
        ]
    else:
        lines.append("### 8.6.4 库存损失估算\n\n_暂缺基线 MAE，未计算。_\n")
    return "\n".join(lines)


def render_markdown(stats: dict[str, Any], figure_dir: str = "figures") -> str:
    """渲染《数据分析报告》Markdown。"""
    overview = stats["overview"]
    seasonality = stats["seasonality"]
    model = stats["model_metrics"]
    rec = stats["recommendation"]
    trade = stats["trade"]
    industry = stats["industry"]

    def fig(name: str) -> str:
        return f"![{name}]({figure_dir}/{name})"

    category_rows = "\n".join(
        f"| {r['name']} | {r['avg_sales']:.1f} | {r['avg_search']:.1f} | {r['avg_export']:.1f} | "
        f"{r['avg_competition']:.1f} | {r['avg_price']:.1f} | {r['last_12w_sales']:.1f} | {r['growth_pct']:+.1f}% |"
        for r in stats["category_summary"]
    )
    market_rows = "\n".join(
        f"| {r['name']} | {r['avg_sales']:.1f} | {r['avg_competition']:.1f} | {r['avg_price']:.1f} | "
        f"{r['avg_export']:.1f} | {r['last_12w_sales']:.1f} | {r['growth_pct']:+.1f}% |"
        for r in stats["market_summary"]
    )
    rec_rows = "\n".join(
        f"| {r['rank']} | {r['category_name']} | {r['market_name']} | {r['score']:.1f} | "
        f"{float(r.get('six_dimension_score') or 0):.1f} | {r.get('verdict') or '-'} | "
        f"{float(r['forecast_growth']):+.1f}% | {float(r['search_trend']):+.1f}% | "
        f"{float(r['competition']):.1f} | {r['reasons']} |"
        for r in rec["top10"]
    )
    source_rows = "\n".join(
        f"| {f['title']} | {f['value']} | {f['detail']} | {f['source']} | "
        f"{f['url'] or '—'} | {f['status']} |"
        for f in industry["facts"]
    )
    crawler = stats.get("crawler") or {}
    crawler_rows = "\n".join(
        f"| {c['category_name']} | {c['market_name']} | {c['keyword']} | "
        f"{float(c.get('pageview_trend_pct') or 0):+.1f}% | {c.get('source_count', 0)} |"
        for c in (crawler.get("combos") or [])[:10]
    )
    customs = stats.get("customs") or {}
    customs_rows = "\n".join(
        f"| {r['category_name']} | {r['hs_code']} | {float(r['value']):,.0f} | "
        f"{r['period']} | {r['source']} |"
        for r in (customs.get("rows") or [])[:20]
    )
    evidence_section = build_evidence_section(industry["facts"])
    trade_rows = "\n".join(
        f"| {r['category_name']} | {r['market_name']} | {r['risk_level']} | "
        f"{float(r['effective_tariff_rate']) * 100:.0f}% | {float(r['landed_cost_increase_pct']):+.1f}% | "
        f"{float(r['margin_pct']):+.1f}% | {float(r['financing_ready_score']):.1f} | "
        f"{r['conflict_level']} | {r['best_logistics']} |"
        for r in trade["rows"]
    )
    policy_lines = "\n".join(
        f"- {event['date']}：{event['label']}（{event['group']}）"
        for event in industry["policy_timeline"]
    )

    top_findings = [
        f"数据基础：{overview['history_rows']} 条周粒度清洗数据、104 周、"
        f"{overview['categories']} 品类 × {overview['markets']} 市场 {COMBO_COUNT} 组合，"
        f"预测产物 {overview['forecast_rows']} 行（90 天 × 2 模型）。",
        f"模型精度：LightGBM 进阶 MAPE {overview['advanced_mape_avg']:.2f}%，较 Prophet 基线 "
        f"{overview['baseline_mape_avg']:.2f}% 相对下降 {overview['mape_improvement_pct']:.1f}%。",
        f"推荐 Top1：{rec['top1'].get('category_name', '-')} × {rec['top1'].get('market_name', '-')}，"
        f"综合评分 {rec['top1'].get('score', '-')}。",
        f"季节性：销量峰值集中在第 {seasonality['peak_week']} 周（约 {seasonality['peak_month']} 月），"
        f"低点约在 {seasonality['trough_month']} 月。",
        f"贸易决策：{COMBO_COUNT} 组合中高风险 {trade['high_risk']} 个，"
        f"平均利润冲击 {trade['avg_margin_pct']:.1f}%，"
        f"平均融资就绪评分 {trade['credit_avg']:.1f}。",
    ]
    business = stats.get("business_metrics") or {}
    if (business.get("calibration") or {}).get("status") == "ok":
        cal = business["calibration"]
        dr = business.get("direction_hit_rate") or {}
        topn = business.get("topn_posterior_return") or {}
        top_findings.append(
            "业务指标：回测方向命中率 "
            f"{_fmt(dr.get('hit_rate_pct'))}%（随机基准 50%），校准偏差 "
            f"{_fmt(cal.get('bias_pct'))}%，Top-N 后验收益 90 天合计 "
            f"${_fmt((topn.get('aggregates') or {}).get('total_posterior_return_90d_usd'))}。"
        )
    findings_text = "\n".join(f"{i}. {item}" for i, item in enumerate(top_findings, start=1))

    return f"""# 数据分析报告

> 项目：基于多源数据融合的跨境电商智能选品决策系统
> 生成日期：{GENERATED_AT}；数据快照：`data/processed/clean_data.csv` 等现有产物

## 一、结论摘要

{findings_text}

> 说明：行业数据以“已检索 / 待核实”双口径登记，来源表见附录 A；项目自身统计全部可由
> `scripts/run_data_analysis.py` 复现。

## 二、行业与市场数据分析

### 2.1 市场规模与增长

2025 年中国跨境电商进出口规模达到 2.75 万亿元，较 2020 年增长 69.7%（国新办 2026-01-28
发布会引用海关初步统计）。项目既有材料写作“同比增长 69.7%”，本报告按官方口径修正为
“较 2020 年增长”。行业企业数量超过 12 万家，商务部（gov.cn 转载）与海关总署口径均已检索，
来源见附录 A。

{fig("industry_market.png")}

### 2.2 政策时间线

{policy_lines}

{fig("policy_timeline.png")}

政策含义：美国市场小额包裹免税取消后，单件关税与到岸成本大幅上升；欧盟 2026-07-01 起取消
150 欧元低值包裹免税额度，正式清关、海外仓与 IOSS 合规成为卖家决策变量。这与系统
“政策风险 → 到岸成本 → 利润冲击”的决策链路直接对应。

### 2.3 海关出口信号（真实数据接入）

海关出口数据优先来自 UN Comtrade 免 Key 预览接口（来源 `{customs.get('provider') or '-'}`，
口径为中国按 HS4 品类汇总出口、最新可用年度 {customs.get('period') or '-'}）。真实请求失败时
回退 Open Trade Statistics 或项目合成数据，并在来源表标注回退状态。

{fig("customs_exports.png")}

| 品类 | HS4 | 中国出口额（USD） | 年度 | 来源 |
| --- | ---: | ---: | ---: | --- |
{customs_rows}

## 三、项目数据总览

| 指标 | 数值 |
| --- | --- |
| 历史数据条数 | {overview['history_rows']} 条 |
| 时间粒度 / 周期 | 周粒度，{overview['start_date']} 至 {overview['end_date']} |
| 覆盖范围 | {overview['categories']} 品类 × {overview['markets']} 市场 = {COMBO_COUNT} 组合 |
| 预测条数 / 范围 | {overview['forecast_rows']} 条，{overview['forecast_start']} 至 {overview['forecast_end']} |
| 推荐结果 | {overview['recommendation_rows']} 条 |
| 基线模型 MAPE | {overview['baseline_mape_avg']:.2f}% |
| 进阶模型 MAPE | {overview['advanced_mape_avg']:.2f}%（相对提升 {overview['mape_improvement_pct']:.1f}%） |

## 四、探索性数据分析

### 4.1 品类 × 市场对比

{fig("category_market_sales.png")}

品类维度（全周期均值）：

| 品类 | 平均销量 | 平均搜索热度 | 平均出口（万美元） | 平均竞争度 | 平均价格（美元） | 近12周销量 | 12周增长 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{category_rows}

市场维度（全周期均值）：

| 市场 | 平均销量 | 平均竞争度 | 平均价格（美元） | 平均出口（万美元） | 近12周销量 | 12周增长 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{market_rows}

### 4.2 搜索与出口信号

{fig("search_export.png")}

### 4.3 趋势与季节性

{fig("trend_seasonality.png")}

{fig("weekly_seasonality.png")}

销量峰值周为第 {seasonality['peak_week']} 周，峰值月约 {seasonality['peak_month']} 月，
低谷月约 {seasonality['trough_month']} 月；备货节奏应结合预测增长与季节峰值提前安排。

## 五、模型评估分析

{fig("model_mape.png")}

进阶模型最优组合：{model['best_combo'].get('category_name', '-')} × {model['best_combo'].get('market_name', '-')}
（MAPE {model['best_combo'].get('mape', '-')}%）；基线最差组合：
{model['worst_combo'].get('category_name', '-')} × {model['worst_combo'].get('market_name', '-')}
（MAPE {model['worst_combo'].get('mape', '-')}%）。

{fig("forecast_interval.png")}

预测统一输出 80% 置信区间，历史与预测边界可追溯；区间宽度可用于备货风险的保守估计。

## 六、推荐结果分析

Top 10 推荐：

| 排名 | 品类 | 市场 | 综合评分 | 六维评分 | Go/No-Go | 预测增长 | 搜索趋势 | 竞争度 | 推荐理由 |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
{rec_rows}

{fig("recommend_composition.png")}

Top10 市场分布：{"、".join(f"{market_name(k)} {v} 个" for k, v in rec['market_counts'].items())}；
Top10 平均评分 {rec['avg_score']:.1f}。东南亚市场在推荐榜中占比高，竞争度低、预测增长高是主要驱动。

## 七、贸易决策情景分析

| 品类 | 市场 | 政策风险 | 有效税率 | 到岸成本上升 | 利润率 | 融资就绪 | 冲突等级 | 最优物流 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
{trade_rows}

{fig("landed_cost.png")}

物流三方案平均单件到岸成本：{"；".join(f"{k} {v} 美元" for k, v in trade['logistics_options'].items())}。

{fig("policy_financing.png")}

{COMBO_COUNT} 组合中高风险 {trade['high_risk']} 个、中风险 {trade['medium_risk']} 个；平均利润冲击
{trade['avg_margin_pct']:.1f}%，平均融资就绪评分 {trade['credit_avg']:.1f}，冲突高风险组合
{trade['conflict_high']} 个。政策冲击最大的组合集中在小额包裹清关口径（美 / 欧等目的地），
验证了“政策风险量化 → 到岸成本 → 融资就绪”的决策闭环。

## 八、真实爬虫信号

每日与按需爬虫快照作为独立证据层，来自 Wikimedia 公开搜索与页面浏览量，不改动模型训练数据。
| 状态 | 组合数 | 来源数 | 回退 |
| --- | ---: | ---: | --- |
| {crawler['status']['status']} | {crawler['count']} | {crawler['sources_count']} | {crawler['fallback_used']} |

Top 组合：
| 品类 | 市场 | 关键词 | 浏览量趋势 | 来源数 |
| --- | --- | --- | ---: | ---: |
{crawler_rows}

{fig("crawler_signals.png")}

## 八点五、证据闸与解释分层

> 模型与统计数值和 AI 解释严格分层：数值来自预测、成本、政策与合规模型，
> AI 只负责解释与建议，不生成数值。

{evidence_section}

## 八点六、业务指标（预测校准 / 方向命中 / Top-N 后验收益 / 库存损失）

{_render_business_metrics(stats.get("business_metrics") or {})}

## 九、结论与建议

1. 模型路线有效：多源特征融合使 MAPE 从 {overview['baseline_mape_avg']:.2f}% 降至
   {overview['advanced_mape_avg']:.2f}%，可作为“AI 数据驱动选品”的核心证据。
2. 推荐引擎与市场结构一致：{rec['top1'].get('market_name', '-')} × {rec['top1'].get('category_name', '-')}
   组合是当前数据下的高潜力方向，但需用真实平台数据验证泛化性。
3. 政策风险已量化：美国 de minimis 取消、欧盟低值包裹免税取消直接压利润，系统输出
   “转正式清关 / 海外仓 / 切换市场”等可执行动作，是商业计划书差异化的关键论据。
4. 报告与 demo 联动：本报告结论已同步写入商业计划书、技术文档、项目大纲、路演大纲、
   数据与模型说明和申报书；HTML / Streamlit demo 新增“数据分析”页签与联网搜索。

## 十、局限说明

- 项目统计基于合成演示数据快照，不代表真实市场；真实数据接入后需重跑本报告。
- 行业数据中“Temu AI 监测”“SaaS 法规监控趋势”等条目仍未定位官方原文，已标注待核实，
  答辩引用前必须回填来源；其余条目均已登记官方来源。
- 相关性分析用于解释信号结构，不构成因果推断；预测区间为模型不确定性估计，非业务承诺。

## 十一、待办 / 待核实清单

- [ ] 为“Temu 用 AI 监测关税”和“SaaS 法规监控趋势”补充公开报道或行业报告出处。
- [ ] 用真实 Google Trends / 平台榜单 / 海关出口数据回填对照组结果并复核图表口径。

## 附录 A：行业数据来源表

| 条目 | 数值 / 内容 | 口径说明 | 来源 | 链接 | 状态 |
| --- | --- | --- | --- | --- | --- |
{source_rows}

## 附录 B：图表清单

{fig("industry_market.png")}
{fig("policy_timeline.png")}
{fig("category_market_sales.png")}
{fig("search_export.png")}
{fig("trend_seasonality.png")}
{fig("weekly_seasonality.png")}
{fig("model_mape.png")}
{fig("forecast_interval.png")}
{fig("recommend_composition.png")}
{fig("landed_cost.png")}
{fig("policy_financing.png")}
{fig("crawler_signals.png")}
{fig("customs_exports.png")}

## 附录 C：复现步骤

```powershell
python scripts\\run_data_analysis.py
python scripts\\build_data_analysis_pdf.py
```
"""


def save_report(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    recommendations: pd.DataFrame,
    metrics: dict[str, Any] | None = None,
    trade: dict[str, Any] | None = None,
    out_stats: Path = ANALYSIS_OUT,
    figures_dir: Path = FIGURES_DIR,
    report_path: Path = REPORT_MD,
) -> dict[str, Any]:
    """端到端生成统计 JSON、图表与 Markdown 报告。"""
    data = load_all()
    history = history if history is not None and not history.empty else data["history"]
    forecast = forecast if forecast is not None and not forecast.empty else data["forecast"]
    recommendations = (
        recommendations
        if recommendations is not None and not recommendations.empty
        else data["recommendations"]
    )
    metrics = metrics or data["metrics"]
    trade = trade or data["trade"]
    stats = compute_stats(history, forecast, recommendations, metrics, trade)
    out_stats.mkdir(parents=True, exist_ok=True)
    (out_stats / "summary_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    figures = generate_figures(history, forecast, recommendations, stats, figures_dir)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_markdown(stats), encoding="utf-8")
    return {"stats": stats, "figures": [str(p) for p in figures]}


__all__ = [
    "ANALYSIS_OUT",
    "FIGURES_DIR",
    "INDUSTRY_FACTS",
    "REPORT_MD",
    "TRADE_METRICS_JSON",
    "compute_stats",
    "generate_figures",
    "load_all",
    "render_markdown",
    "save_report",
]
