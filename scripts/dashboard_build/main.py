"""Build a self-contained HTML dashboard from project data.

Output: output/dashboard.html
The file embeds ECharts, history, forecasts and recommendations so it can be
opened offline in any modern browser.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import CATEGORIES, MARKETS  # noqa: E402
from src.trade.cost import DEFAULT_FX_RATE  # noqa: E402

DATA_CSV = ROOT / "data" / "processed" / "clean_data.csv"
FORECAST_CSV = ROOT / "models" / "forecast.csv"
RECOMMEND_CSV = ROOT / "models" / "recommendations.csv"
METRICS_JSON = ROOT / "models" / "metrics.json"
ECHARTS_JS = ROOT / "tmp" / "echarts.min.js"
OUT_HTML = ROOT / "output" / "dashboard.html"
OUT_OFFLINE_HTML = ROOT / "output" / "dashboard-offline.html"
OUT_DATA_JSON = ROOT / "output" / "dashboard-data.json"
DATA_STATUS_JSON = ROOT / "output" / "data_status.json"

COVERAGE_TEXT = f"热力图直接呈现 {len(CATEGORIES)} 品类 × {len(MARKETS)} 市场的销量结构。"

MODELS = {
    "prophet_baseline": "Prophet 基线",
    "lightgbm_advanced": "LightGBM 进阶",
    "statsforecast": "StatsForecast 基线",
}


def read_history() -> pd.DataFrame:
    df = pd.read_csv(DATA_CSV, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def read_forecast() -> pd.DataFrame:
    df = pd.read_csv(FORECAST_CSV, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def read_recommendations() -> pd.DataFrame:
    return pd.read_csv(RECOMMEND_CSV, encoding="utf-8-sig")


def read_metrics() -> dict:
    return json.loads(METRICS_JSON.read_text(encoding="utf-8"))


def collected_test_count() -> int:
    """Return the pytest collection count so the demo never shows a stale total."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=ROOT,
        )
        match = re.search(r"(\d+) tests? collected", proc.stdout or "")
        if match:
            return int(match.group(1))
    except (OSError, subprocess.SubprocessError):
        pass
    return 269


def compute_analysis_payload(
    history: pd.DataFrame,
    recommendations: pd.DataFrame,
    metrics: dict,
) -> dict:
    """为数据分析页签预计算图表数据。"""
    cat_market = history.pivot_table(
        index="category", columns="market", values="sales_volume", aggfunc="mean"
    )
    category_names = [CATEGORIES[code] for code in cat_market.index]
    market_names = [MARKETS[code] for code in cat_market.columns]
    category_market = [
        {
            "category_index": i,
            "market_index": j,
            "value": round(float(cat_market.iloc[i, j]), 1),
        }
        for i in range(len(cat_market.index))
        for j in range(len(cat_market.columns))
    ]

    hist = history.copy()
    hist["week"] = hist["date"].dt.isocalendar().week.astype(int)
    weekly = (
        hist.groupby("week")["sales_volume"]
        .mean()
        .round(2)
        .reset_index()
        .to_dict(orient="records")
    )

    baseline = metrics.get("baseline", [])
    advanced = metrics.get("advanced", [])
    statsforecast = metrics.get("statsforecast", [])
    stats_by_key = {
        (item.get("category"), item.get("market")): item for item in statsforecast
    }
    model_compare = []
    for index, item in enumerate(baseline):
        if index >= len(advanced):
            break
        row = {
            "label": f"{CATEGORIES[item['category']]}×{MARKETS[item['market']]}",
            "baseline": round(float(item["mape"]), 2),
            "advanced": round(float(advanced[index]["mape"]), 2),
        }
        stats = stats_by_key.get((item["category"], item["market"]))
        if stats is not None:
            row["statsforecast"] = round(float(stats["mape"]), 2)
        model_compare.append(row)

    top10 = recommendations.sort_values("rank").head(10)
    recommend_top10 = [
        {
            "label": f"{CATEGORIES[row['category']]}×{MARKETS[row['market']]}",
            "forecast_growth": round(float(row["forecast_growth"]), 1),
            "search_trend": round(float(row["search_trend"]), 1),
            "competition": round(float(row["competition"]), 1),
            "review_growth": round(float(row["review_growth"]), 1),
        }
        for _, row in top10.iterrows()
    ]

    return {
        "category_names": category_names,
        "market_names": market_names,
        "category_market": category_market,
        "weekly": weekly,
        "model_compare": model_compare,
        "recommend_top10": recommend_top10,
    }


def rows_from_frame(df: pd.DataFrame) -> list[dict]:
    return df.assign(date=df["date"].dt.strftime("%Y-%m-%d")).to_dict(orient="records")


from scripts.dashboard_build.templates import (
    HTML_TEMPLATE,
    _UPGRADE_CSS,
    _UPGRADE_JS_POLISH,
    _SIDEBAR_UPGRADE_HTML,
    _TABS_UPGRADE_HTML,
    _PANELS_UPGRADE_HTML,
    _RESULT_EXPORT_HTML,
    _UPGRADE_JS,
    _HEAD_ACTIONS_HTML,
    _DRILLDOWN_HTML,
    _TOAST_HTML,
    _OPS_CSS,
    _CRAWLER_CSS,
    _CRAWLER_HTML,
    _UPGRADE_JS_CRAWLER,
    _UPGRADE_JS_OPS,
    _UPGRADE_JS_V2,
    _UPGRADE_JS_UNIFIED,
)
def _apply_dashboard_upgrades(html: str) -> str:
    dark_marker = "/* demo dark command-center adaptation */"
    if dark_marker in html:
        upgrade_css = _UPGRADE_CSS.strip()
        if upgrade_css.startswith("<style>"):
            upgrade_css = upgrade_css[len("<style>"):]
        if upgrade_css.endswith("</style>"):
            upgrade_css = upgrade_css[: -len("</style>")]
        html = html.replace(
            dark_marker, upgrade_css + "\n" + _OPS_CSS + "\n" + _CRAWLER_CSS + "\n" + dark_marker, 1
        )
    else:
        html = html.replace("</head>", _UPGRADE_CSS + "\n" + _OPS_CSS + "\n</head>", 1)
    html = html.replace(
        '<div class="filter-label">个性化定制</div>',
        _SIDEBAR_UPGRADE_HTML + '<div class="filter-label">个性化定制</div>',
        1,
    )
    html = html.replace(
        '<span class="source-pill" id="source-pill">内嵌演示数据 · 离线可用</span>',
        _HEAD_ACTIONS_HTML,
        1,
    )
    html = html.replace(
        '</div>\n\n<script id="dashboard-data"',
        '</div>\n' + _DRILLDOWN_HTML + _TOAST_HTML + '\n<script id="dashboard-data"',
        1,
    )
    html = html.replace(
        '<nav class="tabs" id="tabs">\n      <button class="tab-btn active" data-tab="charts"',
        '<nav class="tabs" id="tabs">\n' + _TABS_UPGRADE_HTML + '      <button class="tab-btn" data-tab="charts"',
        1,
    )
    html = html.replace(
        '<section class="panel active" id="panel-charts">',
        _PANELS_UPGRADE_HTML + '<section class="panel" id="panel-charts">',
        1,
    )
    html = html.replace(
        '    </section>\n\n    <p class="footer-note"',
        _RESULT_EXPORT_HTML + '    </section>\n\n    <p class="footer-note"',
        1,
    )
    html = html.replace(
        '<div class="daily-snapshot" id="daily-snapshot"></div>',
        '<div class="daily-snapshot" id="daily-snapshot"></div>\n' + _CRAWLER_HTML,
        1,
    )

    # Remove the standalone "data" tab and merge its content into charts.
    data_btn = html.find('data-tab="data"')
    if data_btn >= 0:
        btn_start = html.rfind("<button", 0, data_btn)
        btn_end = html.find("</button>", data_btn)
        if btn_start >= 0 and btn_end >= 0:
            html = html[:btn_start] + html[btn_end + len("</button>"):]

    charts_open = '<section class="panel" id="panel-charts">'
    charts_idx = html.find(charts_open)
    daily_marker = '<div class="daily-snapshot" id="daily-snapshot">'
    if charts_idx >= 0:
        search_start = html.find(daily_marker, charts_idx)
        charts_close = html.find("</section>", search_start)
        if search_start >= 0 and charts_close >= 0:
            search_tail = html[search_start:charts_close]
            html = html[:search_start] + html[charts_close:]
            search_panel = (
                '<section class="panel" id="panel-search">\n      <div class="card">\n'
                + search_tail
                + "\n      </div>\n    </section>\n\n"
            )
            html = html.replace(charts_open, search_panel + charts_open, 1)

    data_open = '<section class="panel" id="panel-data">'
    open_idx = html.find(data_open)
    if open_idx >= 0:
        close_idx = html.find("</section>", open_idx)
        if close_idx >= 0:
            close_idx += len("</section>")
            data_section = html[open_idx:close_idx]
            inner = data_section[len(data_open):-len("</section>")]
            html = html[:open_idx] + html[close_idx:]
            charts_idx = html.find(charts_open)
            charts_close = html.find("</section>", charts_idx)
            if charts_idx >= 0 and charts_close >= 0:
                html = html[:charts_close] + "\n" + inner + "\n" + html[charts_close:]

    html = html.replace(
        "const renderers = { charts: renderAnalysis, data: renderAnalysis };",
        "const renderers = { charts: renderAnalysis, overview: renderOverview, compare: renderComparePanel, trade: renderTradePanel, search: renderSearchPanel, policy: renderPolicyPanel };",
        1,
    )
    html = html.replace(
        '  model: RAW.models_order[0] || "lightgbm_advanced"\n};',
        '  model: RAW.models_order[0] || "lightgbm_advanced",\n  date_from: "",\n  date_to: "",\n  top_n: 20,\n  compare: [],\n  initialTab: null,\n  categories: Object.keys(CATEGORIES),\n  markets: Object.keys(MARKETS),\n  view: "overview",\n  drilldown: null,\n  favorites: [],\n  drillCharts: { range: 0, model: "all", metricView: "radar" },\n  displayPrefs: { presentation: false, sidebarCollapsed: false },\n  customCategoryInput: "",\n  customMarketInput: ""\n};',
        1,
    )
    html = html.replace(
        "      common.style.display = (btn.dataset.tab === \"charts\" || btn.dataset.tab === \"data\") ? \"\" : \"none\";",
        "      common.style.display = \"\";",
        1,
    )
    html = html.replace(
        "function renderAll() {\n  renderKpis();",
        "function renderAll() {\n  renderKpis();\n  renderFavorites();\n  renderCrawlerPanel();",
        1,
    )
    html = html.replace(
        "function historyFor(category, market) {\n  const rows = dataHistory();\n  if (customCategoryLabel) return rows.filter(r => r.market === market);\n  return rows.filter(r => r.category === category && r.market === market);\n}",
        "function historyFor(category, market) {\n  let rows = dataHistory();\n  const cat = state.customCategoryInput || category;\n  const mkt = state.customMarketInput || market;\n  if (customInputActive()) rows = rows.filter(r => (r.category === cat || CATEGORIES[r.category] === cat) && (r.market === mkt || MARKETS[r.market] === mkt));\n  else rows = rows.filter(r => r.category === category && r.market === market);\n  if (state.date_from) rows = rows.filter(r => String(r.date) >= state.date_from);\n  if (state.date_to) rows = rows.filter(r => String(r.date) <= state.date_to);\n  return rows;\n}",
        1,
    )
    html = html.replace("source.slice(0, 10)", "source.slice(0, state.top_n || 20)")
    html = html.replace(
        '<tr class="${isTop3 ? "top3" : ""}">',
        '<tr class="${isTop3 ? "top3" : ""}" data-reco-category="${r.category}" data-reco-market="${r.market}" style="cursor:pointer">',
        1,
    )
    html = html.replace(
        '<div class="fb-row" data-tip="${tip}">',
        '<div class="fb-row" data-reco-category="${r.category}" data-reco-market="${r.market}" data-tip="${tip}">',
        1,
    )
    html = html.replace(
        "      search_max_results: 5,\n      lang: LANG\n    };",
        "      search_max_results: 5,\n      lang: LANG,\n      api_key: aiSettings().api_key,\n      base_url: aiSettings().base_url,\n      model: aiSettings().model,\n      timeout: aiSettings().timeout\n    };",
        1,
    )
    html = html.replace(
        "    resultEl.textContent = String(err);\n    runBtn.disabled = false;",
        "    try {\n      const direct = await browserDirectAnalysis(category, marketCode, extraPrompt);\n      customResult = direct;\n      activeSource = null;\n      customCategoryLabel = category;\n      onlineSource = true;\n      renderAll();\n      renderCustomResult(direct);\n      setProgress(100, \"浏览器直连完成（全局 AI 接入生效）\", \"live\");\n      resultEl.textContent = \"浏览器直连完成，已使用全局 AI 接入生成结果。\";\n    } catch (directErr) {\n      resultEl.textContent = String(directErr);\n    }\n    runBtn.disabled = false;",
        1,
    )
    html = html.replace(
        "updateLangUI();\nrenderAll();\nwatchChartVisibility();",
        "updateLangUI();\nrenderAll();\nif (typeof window.renderActiveTab === \"function\") window.renderActiveTab();\nwatchChartVisibility();",
        1,
    )
    html = html.replace(
        "renderCustomResult(direct);",
        "renderCustomResult(direct); applyDashboardStaticLang();",
        1,
    )
    html = html.replace("initTabs();\n", "initTabs();\napplyInitialTab();\n", 1)
    html = html.replace(
        "\ninitSelects();\n",
        "\n" + _UPGRADE_JS + _UPGRADE_JS_V2 + _UPGRADE_JS_CRAWLER + _UPGRADE_JS_OPS + _UPGRADE_JS_UNIFIED + _UPGRADE_JS_POLISH + "\ninitSelects();\n",
        1,
    )
    return html


def build() -> None:
    history = read_history()
    forecast = read_forecast()
    recommendations = read_recommendations()
    metrics = read_metrics()
    trade_payload = {}
    trade_path = ROOT / "output" / "trade" / "trade_demo_metrics.json"
    if trade_path.exists():
        try:
            trade_payload = json.loads(trade_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            trade_payload = {}
    policy_payload = {}
    policy_path = ROOT / "output" / "policy" / "latest.json"
    if policy_path.exists():
        try:
            policy_payload = json.loads(policy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            policy_payload = {}
    policy_events = list(policy_payload.get("events") or [])
    policy_candidates = list(policy_payload.get("candidate_events") or [])

    models_order = [c for c in MODELS if c in set(forecast["model"].unique())]
    if not models_order:
        models_order = list(MODELS.keys())

    payload = {
        "categories": CATEGORIES,
        "markets": MARKETS,
        "models": MODELS,
        "models_order": models_order,
        "fx_rate": DEFAULT_FX_RATE,
        "history": rows_from_frame(history),
        "forecast": rows_from_frame(forecast),
        "recommendations": recommendations.to_dict(orient="records"),
        "metrics": metrics,
        "trade": trade_payload,
        "policy_events": policy_events,
        "policy_candidates": policy_candidates,
        "policy_snapshot": policy_payload,
        "analysis": compute_analysis_payload(history, recommendations, metrics),
    }
    crawler_payload = {}
    crawler_path = ROOT / "output" / "crawler" / "latest.json"
    if crawler_path.exists():
        try:
            crawler_payload = json.loads(crawler_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            crawler_payload = {}
    payload["crawler"] = crawler_payload
    if DATA_STATUS_JSON.exists():
        payload["data_status"] = json.loads(
            DATA_STATUS_JSON.read_text(encoding="utf-8")
        )
    else:
        payload["data_status"] = {}
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    test_count = str(collected_test_count())

    echarts_js = ECHARTS_JS.read_text(encoding="utf-8")
    echarts_js = echarts_js.replace("</script>", "<\\/script>")

    OUT_DATA_JSON.write_text(data_json, encoding="utf-8")

    def render(data_placeholder: str) -> str:
        html = (
            HTML_TEMPLATE.replace("__DATA__", data_placeholder)
            .replace("__ECHARTS__", echarts_js)
        )
        html = _apply_dashboard_upgrades(html)
        return html.replace(
            "热力图直接呈现 5 品类 × 3 市场的销量结构。", COVERAGE_TEXT
        )

    offline_html = render(data_json).replace("__TEST_COUNT__", test_count)
    online_html = render("").replace("__TEST_COUNT__", test_count)
    OUT_OFFLINE_HTML.write_text(offline_html, encoding="utf-8")
    OUT_HTML.write_text(online_html, encoding="utf-8")
    print(
        f"OK: {OUT_HTML} ({OUT_HTML.stat().st_size / 1024:.1f} KB, external data)"
    )
    print(
        f"OK: {OUT_OFFLINE_HTML} ({OUT_OFFLINE_HTML.stat().st_size / 1024:.1f} KB, inline data)"
    )
    print(
        f"OK: {OUT_DATA_JSON} ({OUT_DATA_JSON.stat().st_size / 1024:.1f} KB)"
    )


if __name__ == "__main__":
    build()
