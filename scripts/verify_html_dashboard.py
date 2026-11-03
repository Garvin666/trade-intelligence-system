"""Browser-level verification for the generated offline HTML dashboard."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CATEGORIES, MARKETS  # noqa: E402

DASHBOARD_HTML = PROJECT_ROOT / "output" / "dashboard-offline.html"
SHOT_PATH = PROJECT_ROOT / "docs" / "dashboard_html_preview.png"

_GEN_SOURCE = (
    (PROJECT_ROOT / "scripts" / "dashboard_build" / "main.py").read_text(encoding="utf-8")
    + "\n"
    + (PROJECT_ROOT / "scripts" / "dashboard_build" / "templates.py").read_text(encoding="utf-8")
)


def _js_array(name: str) -> list[str]:
    match = re.search(rf"const {name} = \[(.*?)\];", _GEN_SOURCE, re.S)
    if not match:
        raise AssertionError(f"missing JS constant {name}")
    return ast.literal_eval("[" + match.group(1) + "]")


CATEGORY_QUICK = _js_array("CATEGORY_QUICK")
MARKET_QUICK = _js_array("MARKET_QUICK")
EXPECTED_CAT_CHIPS = len(CATEGORIES) + len([v for v in CATEGORY_QUICK if v not in CATEGORIES.values()])
EXPECTED_MKT_CHIPS = len(MARKETS) + len([v for v in MARKET_QUICK if v not in MARKETS.values()])
EXPECTED_CAT_QUICK = len([v for v in CATEGORY_QUICK if v not in CATEGORIES.values()])
EXPECTED_MKT_QUICK = len([v for v in MARKET_QUICK if v not in MARKETS.values()])
COMBO_COUNT = len(CATEGORIES) * len(MARKETS)


def attach_console_capture(page) -> list[str]:
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    return errors


def main() -> None:
    from playwright.sync_api import sync_playwright

    uri = DASHBOARD_HTML.as_uri()
    all_errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Desktop: single-screen overview + drill-down drawer.
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.add_init_script("localStorage.clear();")
        all_errors += attach_console_capture(page)
        page.goto(uri, wait_until="load")
        page.wait_for_selector("#panel-overview.active", timeout=30000)
        print("[check] overview visible")

        assert page.locator("#date-from").count() == 1
        assert page.locator("#export-md-btn").count() == 1
        assert page.locator("#presentation-btn").count() == 1
        assert page.locator("#copy-link-btn").count() == 1
        assert page.locator("#export-md-btn-0").count() == 1
        assert page.locator("#sidebar-collapse-btn").count() == 1
        assert page.locator("#tabs").is_visible()
        assert page.locator("#tabs .tab-btn").count() == 10
        for tab in ["market", "ops", "eda"]:
            assert page.locator(f'[data-tab="{tab}"]').count() == 1
            assert page.locator(f'#panel-{tab}').count() == 1
        print("[check] date range / header actions present (AI 设置已统一由全局 AI 接入管理)")

        assert page.evaluate("typeof readGlobalAiConfig") == "function"
        assert page.evaluate("typeof aiSettings") == "function"
        page.evaluate(
            "localStorage.setItem('trade_intel_ai_global', JSON.stringify({api_key:'sk-global', base_url:'https://example.com/v1', model:'gpt-global', preset:'custom', timeout:60}));"
        )
        assert page.evaluate("aiSettings().api_key") == "sk-global"
        assert page.evaluate("aiSettings().model") == "gpt-global"
        page.evaluate("localStorage.removeItem('trade_intel_ai_global');")
        print("[check] dashboard reads global AI config shared key")

        assert page.locator('[data-tab="data"]').count() == 0
        assert page.locator("#panel-data").count() == 0
        assert page.locator("#filter-categories .filter-chip").count() == EXPECTED_CAT_CHIPS
        assert page.locator("#filter-markets .filter-chip").count() == EXPECTED_MKT_CHIPS
        assert page.locator("#analysis-common").is_visible()
        print("[check] multi-select filters and overview grid visible")

        # New backend-driven panels degrade to explicit offline placeholders.
        page.locator('[data-tab="market"]').click()
        page.wait_for_selector("#panel-market.active", timeout=10000)
        page.wait_for_selector("#market-rankings .ops-table, #market-rankings .ops-status", timeout=30000)
        assert page.locator("#market-rankings").inner_text().strip() != ""
        print("[check] market intelligence panel renders data or offline placeholder")

        page.locator('[data-tab="ops"]').click()
        page.wait_for_selector("#panel-ops.active", timeout=10000)
        page.wait_for_selector("#ops-health .ops-row, #ops-health .ops-status", timeout=30000)
        assert page.locator("#ops-health").inner_text().strip() != ""
        print("[check] ops console panel renders data or offline placeholder")

        page.locator('[data-tab="eda"]').click()
        page.wait_for_selector("#panel-eda.active", timeout=10000)
        assert page.locator("#eda-file").count() == 1
        print("[check] EDA panel visible")

        page.locator('[data-tab="overview"]').click()
        page.wait_for_selector("#panel-overview.active", timeout=10000)

        # Multi-select filter changes KPI count and recommendation table.
        first_cat = page.locator("#filter-categories .filter-chip").first
        assert first_cat.get_attribute("aria-pressed") == "true"
        first_cat.click()
        assert page.locator("#filter-cat-count").inner_text() == str(len(CATEGORIES) - 1)
        assert page.locator("#kpi-grid .kpi").first.locator(".kpi-value").inner_text() == str(len(CATEGORIES) - 1)
        assert page.locator("#filter-categories .filter-chip").first.get_attribute("aria-pressed") == "false"
        print("[check] category multi-select updates KPI")
        page.locator("#filter-cat-reset").click()
        assert page.locator("#filter-cat-count").inner_text() == str(len(CATEGORIES))

        # Sidebar collapse / expand keeps the main view cleaner.
        collapse_btn = page.locator("#sidebar-collapse-btn")
        assert collapse_btn.inner_text() == "收起筛选"
        collapse_btn.click()
        page.wait_for_timeout(250)
        assert "sidebar-collapsed" in page.locator("body").get_attribute("class")
        assert page.locator(".sidebar").is_visible() is False
        assert collapse_btn.inner_text() == "展开筛选"
        collapse_btn.click()
        page.wait_for_timeout(250)
        assert "sidebar-collapsed" not in page.locator("body").get_attribute("class")
        assert page.locator(".sidebar").is_visible() is True
        assert collapse_btn.inner_text() == "收起筛选"
        print("[check] sidebar collapse / expand toggles")

        # Free-text category/market input drives labels and charts.
        cat_text = page.locator("#filter-category-text")
        mkt_text = page.locator("#filter-market-text")
        assert cat_text.count() == 1
        cat_text.fill("智能猫砂盆")
        page.keyboard.press("Tab")
        page.wait_for_timeout(250)
        assert page.locator("#kpi-grid .kpi").nth(0).locator(".kpi-value").inner_text() == "智能猫砂盆"
        assert "智能猫砂盆" in page.locator("#trend-title").inner_text()
        mkt_text.fill("加拿大")
        page.keyboard.press("Tab")
        page.wait_for_timeout(250)
        assert page.locator("#kpi-grid .kpi").nth(1).locator(".kpi-value").inner_text() == "加拿大"
        assert "智能猫砂盆 × 加拿大" in page.locator("#trend-title").inner_text()
        page.locator("#filter-category-clear").click()
        page.locator("#filter-market-clear").click()
        page.wait_for_timeout(150)
        assert page.locator("#filter-category-text").input_value() != "智能猫砂盆"
        print("[check] free-text category/market input drives labels")

        # Quick-select now includes more kinds directly (no separate examples row).
        assert page.locator("#category-quick-examples").count() == 0
        assert page.locator("#market-quick-examples").count() == 0
        assert page.locator("#filter-categories [data-quick-kind='category']").count() == EXPECTED_CAT_QUICK
        assert page.locator("#filter-markets [data-quick-kind='market']").count() == EXPECTED_MKT_QUICK
        quick_cat = None
        if EXPECTED_CAT_QUICK:
            page.locator("#filter-categories [data-quick-kind='category']").first.click()
            page.wait_for_timeout(200)
            quick_cat = page.locator("#filter-categories [data-quick-kind='category']").first.inner_text()
            assert page.locator("#filter-category-text").input_value() == quick_cat
            assert quick_cat in page.locator("#trend-title").inner_text()
        quick_mkt = None
        if EXPECTED_MKT_QUICK:
            page.locator("#filter-markets [data-quick-kind='market']").first.click()
            page.wait_for_timeout(200)
            quick_mkt = page.locator("#filter-markets [data-quick-kind='market']").first.inner_text()
            assert page.locator("#filter-market-text").input_value() == quick_mkt
            if quick_cat is not None:
                assert quick_cat + " × " + quick_mkt in page.locator("#trend-title").inner_text()
        page.locator("#filter-category-clear").click()
        page.locator("#filter-market-clear").click()
        print(f"[check] quick-select covers {EXPECTED_CAT_QUICK} category + {EXPECTED_MKT_QUICK} market extra kinds")

        # Combo presets apply a category x market combo and open the drill-down.
        preset_count = page.locator("#combo-presets .filter-chip").count()
        assert preset_count >= 10
        page.locator("#combo-presets .filter-chip").first.click()
        page.wait_for_selector("#drilldown-layer:not([hidden])", timeout=10000)
        page.wait_for_selector("#panel-trade.active", timeout=10000)
        assert page.locator("#drilldown-title").inner_text() != ""
        page.locator("#drilldown-layer .drill-close").click()
        page.wait_for_selector("#drilldown-layer[hidden]", state="attached", timeout=10000)
        print(f"[check] combo presets open drill-down ({preset_count} presets)")

        # Recommendation row opens drill-down drawer with trade view.
        page.locator("#recommend-table tr[data-reco-category]").first.click()
        page.wait_for_selector("#drilldown-layer:not([hidden])", timeout=10000)
        page.wait_for_selector("#panel-trade.active", timeout=10000)
        assert page.locator("#drilldown-title").inner_text() != ""
        print("[check] recommendation row opens drill-down drawer -> trade")

        # Drawer segmented views switch correctly.
        page.locator('#dview-nav .dview-btn[data-dview="compare"]').click()
        page.wait_for_selector("#panel-compare.active", timeout=10000)
        assert page.locator("#compare-table-wrap tr").count() >= 3
        coverage = int(page.locator("#compare-coverage").inner_text())
        assert coverage == COMBO_COUNT
        assert page.locator("#compare-select-all").count() == 1
        assert page.locator("#compare-clear-all").count() == 1
        page.locator("#compare-select-all").click()
        page.wait_for_timeout(200)
        assert int(page.locator("#compare-selected").inner_text()) == coverage
        assert page.locator("#compare-table-wrap tr").count() >= coverage + 1
        page.locator("#compare-clear-all").click()
        page.wait_for_timeout(200)
        assert int(page.locator("#compare-selected").inner_text()) == 2
        print(f"[check] drawer compare view covers {coverage} combos")

        page.locator('#dview-nav .dview-btn[data-dview="search"]').click()
        page.wait_for_selector("#panel-search.active", timeout=10000)
        assert page.locator("#analysis-search-input").count() == 1
        assert page.locator("#followup-input").count() == 1
        assert page.locator("#daily-snapshot").count() == 1
        print("[check] drawer search view + follow-up present")

        page.locator('#dview-nav .dview-btn[data-dview="charts"]').click()
        page.wait_for_selector("#panel-dcharts.active", timeout=10000)
        assert page.locator("#dchart-toolbar").count() == 1
        assert page.locator("#dchart-export-btn").count() == 1
        assert page.locator("#dchart-model-select").count() == 1
        assert page.locator("#dchart-range-btns .dchart-btn").count() == 4
        assert page.locator("#dchart-metric-toggle .dchart-btn").count() == 2
        assert page.locator("#panel-dcharts .dchart-download-btn").count() == 5
        for cid in ["chart-dforecast", "chart-dstage", "chart-dmetrics", "chart-dmape", "chart-drecommend"]:
            assert page.locator(f"#{cid} canvas").count() == 1
        assert page.locator("#dforecast-title").inner_text() != ""
        print("[check] drawer charts view: 5 combo charts + toolbar")

        page.locator('#dchart-metric-toggle .dchart-btn[data-view="bar"]').click()
        page.wait_for_timeout(150)
        assert "active" in page.locator('#dchart-metric-toggle .dchart-btn[data-view="bar"]').get_attribute("class")
        page.locator('#dchart-metric-toggle .dchart-btn[data-view="radar"]').click()
        page.wait_for_timeout(150)
        page.select_option("#dchart-model-select", "lightgbm_advanced")
        page.wait_for_timeout(150)
        assert page.locator("#dchart-model-select").input_value() == "lightgbm_advanced"
        page.locator('#dchart-range-btns .dchart-btn[data-days="30"]').click()
        page.wait_for_timeout(150)
        assert "active" in page.locator('#dchart-range-btns .dchart-btn[data-days="30"]').get_attribute("class")
        print("[check] drawer charts interactions (radar/bar, model, range)")

        with page.expect_download() as dchart_download:
            page.locator('#panel-dcharts .dchart-download-btn[data-chart-id="chart-dforecast"]').click()
        assert dchart_download.value.suggested_filename.startswith("drilldown_")
        print("[check] single chart PNG download")

        page.locator('#dview-nav .dview-btn[data-dview="result"]').click()
        page.wait_for_selector("#panel-result.active", timeout=10000)
        print("[check] drawer result view")

        # Close drawer and reopen via KPI.
        page.locator("#drilldown-layer .drill-close").click()
        page.wait_for_selector("#drilldown-layer[hidden]", state="attached", timeout=10000)
        page.locator("#kpi-grid .kpi").first.click()
        page.wait_for_selector("#drilldown-layer:not([hidden])", timeout=10000)
        page.locator("#drilldown-layer .drill-close").click()
        page.wait_for_selector("#drilldown-layer[hidden]", state="attached", timeout=10000)
        print("[check] drawer open/close")

        # Deep link opens drill-down directly with prefilled trade inputs.
        deep = browser.new_page(viewport={"width": 1440, "height": 900})
        deep.add_init_script("localStorage.clear();")
        all_errors += attach_console_capture(deep)
        deep.goto(
            uri + "#view=drilldown&combo=pet×us&dview=trade&category=pet&market=us",
            wait_until="load",
        )
        deep.wait_for_selector("#drilldown-layer:not([hidden])", timeout=30000)
        deep.wait_for_selector("#panel-trade.active", timeout=30000)
        price = deep.locator("#trade-price").input_value()
        assert price != "30"
        print(f"[check] deep link drill-down prefill: {price}")

        with deep.expect_download() as download_info:
            deep.locator("#export-md-btn-2").click()
        download = download_info.value
        assert download.suggested_filename.endswith(".md")
        download.save_as(str(PROJECT_ROOT / "tmp" / "dashboard_selection_report.md"))
        print("[check] markdown export downloads")
        deep.close()

        # Legacy deep link: #view=trade&category=pet&market=us enters the trade view.
        legacy = browser.new_page(viewport={"width": 1440, "height": 900})
        legacy.add_init_script("localStorage.clear();")
        all_errors += attach_console_capture(legacy)
        legacy.goto(
            uri + "#view=trade&category=pet&market=us",
            wait_until="load",
        )
        legacy.wait_for_selector("#drilldown-layer:not([hidden])", timeout=30000)
        legacy.wait_for_selector("#panel-trade.active", timeout=30000)
        legacy_price = legacy.locator("#trade-price").input_value()
        assert legacy_price != "30"
        assert legacy.locator("#drilldown-title").inner_text() != ""
        print(f"[check] legacy trade deep link prefill: {legacy_price}")
        legacy.close()

        # Custom free-text deep link prefill.
        custom = browser.new_page(viewport={"width": 1440, "height": 900})
        custom.add_init_script("localStorage.clear();")
        all_errors += attach_console_capture(custom)
        custom.goto(
            uri + "#category=" + quote("智能猫砂盆") + "&market=" + quote("加拿大"),
            wait_until="load",
        )
        custom.wait_for_selector("#panel-overview.active", timeout=30000)
        assert custom.locator("#filter-category-text").input_value() == "智能猫砂盆"
        assert custom.locator("#filter-market-text").input_value() == "加拿大"
        assert custom.locator("#kpi-grid .kpi").nth(0).locator(".kpi-value").inner_text() == "智能猫砂盆"
        assert "智能猫砂盆 × 加拿大" in custom.locator("#trend-title").inner_text()
        print("[check] custom deep link prefill")
        custom.close()

        page.screenshot(path=str(SHOT_PATH), full_page=True)

        # Mobile: no horizontal overflow, filter drawer toggles.
        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.add_init_script("localStorage.clear();")
        all_errors += attach_console_capture(mobile)
        mobile.goto(uri, wait_until="load")
        mobile.wait_for_selector("#panel-overview.active", timeout=30000)
        scroll_width = mobile.evaluate("document.documentElement.scrollWidth")
        client_width = mobile.evaluate("document.documentElement.clientWidth")
        assert scroll_width <= client_width + 2, f"horizontal overflow: {scroll_width} > {client_width}"
        assert mobile.locator("#filter-toggle-btn").is_visible()
        mobile.locator("#filter-toggle-btn").click()
        mobile.wait_for_selector(".sidebar.open", timeout=10000)
        assert mobile.locator("body").evaluate("(el) => getComputedStyle(el).overflow") != "hidden" or "sidebar-open" in mobile.locator("body").get_attribute("class")
        mobile.keyboard.press("Escape")
        assert mobile.locator(".sidebar.open").count() == 0
        assert mobile.locator("#headMoreToggle").is_visible()
        mobile.locator("#headMoreToggle").click()
        mobile.wait_for_selector("#headMore.open", timeout=10000)
        assert mobile.locator("#headMoreMenu #presentation-btn").is_visible()
        mobile.keyboard.press("Escape")
        assert mobile.locator("#headMore.open").count() == 0
        print("[check] mobile no overflow + filter drawer and more menu toggle")

        mobile_charts = browser.new_page(viewport={"width": 390, "height": 844})
        mobile_charts.add_init_script("localStorage.clear();")
        all_errors += attach_console_capture(mobile_charts)
        mobile_charts.goto(uri + "#view=drilldown&combo=pet×us&dview=charts&category=pet&market=us", wait_until="load")
        mobile_charts.wait_for_selector("#panel-dcharts.active", timeout=30000)
        scroll_width = mobile_charts.evaluate("document.documentElement.scrollWidth")
        client_width = mobile_charts.evaluate("document.documentElement.clientWidth")
        assert scroll_width <= client_width + 2, f"mobile drilldown charts overflow: {scroll_width} > {client_width}"
        print("[check] mobile drilldown charts no overflow")
        mobile_charts.close()

        browser.close()

    print(f"[ok] 截图已保存: {SHOT_PATH}")
    if all_errors:
        print("[warn] console errors:", all_errors[:10])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
