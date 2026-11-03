"""真实数据适配器、EDA/统计/异常与事实回填测试。"""

from __future__ import annotations

import pandas as pd

from src.analysis.anomaly import build_anomalies_payload, detect_anomalies
from src.analysis.eda import build_eda_report
from src.analysis.report import INDUSTRY_FACTS
from src.analysis.stats import group_ab_test, paired_significance
from src.control.benchmark import _per_combo_mae
from src.data.customs import collect_customs_exports, customs_status
from src.data.daily import write_data_status
from src.data.platform_rankings import collect_rankings, rankings_status
from src.data.trends import collect_trends, trends_status


def _trends_rows(keywords, market, weeks=52):
    rows = []
    for index, (category, keyword) in enumerate(list(keywords.items())[:2]):
        for week in range(weeks):
            rows.append(
                {
                    "date": f"2026-01-0{(week % 9) + 1}",
                    "category": category,
                    "category_name": category,
                    "keyword": keyword,
                    "market": market,
                    "value": 50.0 + index,
                }
            )
    return rows, list(keywords.keys())[:2], list(keywords.keys())[2:], ["mock failure"]


def test_trends_partial_real_covers_rest_with_mock(monkeypatch) -> None:
    import src.data.trends as trends

    monkeypatch.setattr(trends, "GOOGLE_TRENDS_ENABLED", True)
    monkeypatch.setattr(trends, "GOOGLE_TRENDS_MAX_KEYWORDS", 100)
    monkeypatch.setattr(trends, "_pytrends_rows", _trends_rows)
    payload = collect_trends(
        {"cn_changsha_mifen": "smart pet feeder", "cn_latiao": "home storage", "cn_laoganma": "educational toys"},
        market="us",
        weeks=4,
    )
    assert payload["provider"] == "pytrends"
    assert payload["fallback_used"] is True
    assert payload["coverage"]["real"] == 2
    assert payload["coverage"]["mock"] == 1
    assert payload["errors"] == ["mock failure"]


def test_trends_total_failure_falls_back_to_mock(monkeypatch) -> None:
    import src.data.trends as trends

    def broken(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(trends, "GOOGLE_TRENDS_ENABLED", True)
    monkeypatch.setattr(trends, "GOOGLE_TRENDS_MAX_KEYWORDS", 100)
    monkeypatch.setattr(trends, "_pytrends_rows", broken)
    payload = collect_trends({"cn_changsha_mifen": "smart pet feeder"}, weeks=4)
    assert payload["provider"] == "mock"
    assert payload["fallback_used"] is True
    assert payload["coverage"]["real"] == 0
    assert payload["coverage"]["mock"] == 1
    status = trends_status(payload)
    assert status["provider"] == "mock"
    assert status["coverage"]["mock"] == 1


def test_rankings_skip_providers_without_keys(monkeypatch) -> None:
    import src.data.platform_rankings as rankings

    monkeypatch.setattr(rankings, "KEEPA_API_KEY", "")
    monkeypatch.setattr(rankings, "EBAY_APP_ID", "")
    payload = collect_rankings(
        providers=["keepa", "ebay"],
        offline=False,
    )
    assert payload["fallback_used"] is True
    assert payload["providers"]["keepa"]["status"] == "skipped"
    assert payload["providers"]["ebay"]["status"] == "skipped"
    assert payload["rows"][0]["platform"] == "mock"
    assert rankings_status(payload)["providers"]["keepa"]["status"] == "skipped"


def test_customs_offline_uses_mock() -> None:
    payload = collect_customs_exports(offline=True)
    assert payload["provider"] == "mock"
    assert payload["fallback_used"] is True
    assert payload["source_count"] > 0
    assert payload["rows"][0]["hs_code"]
    status = customs_status(payload)
    assert status["provider"] == "mock"
    assert status["rows"] == payload["source_count"]


def test_customs_comtrade_priority(monkeypatch) -> None:
    import src.data.customs as customs

    def comtrade():
        return (
            [
                {
                    "category": "cn_changsha_mifen",
                    "category_name": "辣条",
                    "hs_code": "3924",
                    "period": "2024",
                    "value": 1234.0,
                    "source": "comtrade",
                }
            ],
            "2024",
            [],
        )

    monkeypatch.setattr(customs, "_comtrade_rows", comtrade)
    payload = collect_customs_exports()
    assert payload["provider"] == "comtrade"
    assert payload["fallback_used"] is False
    assert payload["period"] == "2024"
    assert payload["source_url"] == customs.COMTRADE_URL


def test_customs_falls_back_to_mock(monkeypatch) -> None:
    import src.data.customs as customs

    def broken_comtrade():
        raise RuntimeError("comtrade down")

    def broken_ots():
        raise RuntimeError("ots down")

    monkeypatch.setattr(customs, "_comtrade_rows", broken_comtrade)
    monkeypatch.setattr(customs, "_ots_rows", broken_ots)
    payload = collect_customs_exports()
    assert payload["provider"] == "mock"
    assert payload["fallback_used"] is True
    assert len(payload["errors"]) == 2


def test_stats_paired_and_group_ab() -> None:
    a = list(range(1, 31))
    b = [value + (index % 3) + 1 for index, value in enumerate(a)]
    sig = paired_significance(a, b)
    assert sig is not None
    assert sig["significant"] is True
    assert abs(sig["effect_size"]) > 0
    frame = pd.DataFrame(
        {
            "group": ["A"] * 20 + ["B"] * 20,
            "value": [1.0] * 20 + [10.0] * 20,
        }
    )
    result = group_ab_test(frame, "group", "value")
    assert result is not None
    assert result["significant"] is True
    assert result["mean_b"] > result["mean_a"]


def test_anomaly_detects_seeded_outlier() -> None:
    frame = pd.DataFrame({"value": [0.0] * 99 + [100.0]})
    anomalies = detect_anomalies(frame)
    assert len(anomalies) >= 1
    assert anomalies[0]["values"]["value"] == 100.0


def test_build_eda_report_shape() -> None:
    frame = pd.DataFrame(
        {
            "category": ["A", "B"] * 10,
            "sales": list(range(20)),
            "score": [1.0] * 20,
        }
    )
    report = build_eda_report(frame)
    assert report["summary"]["rows"] == 20
    assert report["summary"]["columns"] == 3
    assert isinstance(report["anomalies"], list)
    assert isinstance(report["ab_tests"], list)


def test_series_anomalies_payload() -> None:
    clean = pd.DataFrame(
        {
            "category": ["cn_changsha_mifen"] * 30,
            "market": ["us"] * 30,
            "date": pd.date_range("2026-01-01", periods=30),
            "sales_volume": [10.0] * 29 + [500.0],
            "price_median": [20.0] * 30,
        }
    )
    payload = build_anomalies_payload(clean)
    assert payload["source_count"] >= 1
    assert any(row["column"] == "sales_volume" for row in payload["rows"])


def test_per_combo_mae() -> None:
    predictions = pd.DataFrame(
        {
            "category": ["cn_changsha_mifen"] * 2,
            "market": ["us"] * 2,
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "value": [11.0, 21.0],
        }
    )
    holdout = pd.DataFrame(
        {
            "category": ["cn_changsha_mifen"] * 2,
            "market": ["us"] * 2,
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "sales_volume": [10.0, 20.0],
        }
    )
    series = _per_combo_mae(predictions, holdout)
    assert float(series.iloc[0]) == 1.0


def test_industry_facts_official_sources() -> None:
    by_key = {item["key"]: item for item in INDUSTRY_FACTS}
    for key in ("companies", "us_china_de_minimis", "eu_relief"):
        assert by_key[key]["status"] == "已检索"
        assert by_key[key]["url"]
    assert by_key["temu_ai"]["status"] == "待核实"
    assert by_key["saas_trend"]["status"] == "待核实"


def test_write_data_status_includes_customs_and_anomalies(tmp_path) -> None:
    payload = write_data_status(
        tmp_path,
        data_as_of="2026-08-13",
        generated_at="2026-08-13T10:00:00+08:00",
        provider="crawler",
        fallback_used=False,
        snapshot_path="output/daily_snapshots/2026-08-13.json",
        sources_count=3,
        updated_files=["output/customs/latest.json"],
        customs={"enabled": True, "provider": "comtrade", "rows": 66},
        anomalies={"enabled": True, "rows": 3},
        suppliers={"enabled": True, "provider": "1688_cli", "rows": 5},
    )
    assert payload["customs"]["provider"] == "comtrade"
    assert payload["anomalies"]["rows"] == 3
    assert payload["suppliers"]["provider"] == "1688_cli"
    assert payload["suppliers"]["rows"] == 5


def test_services_data_status_fallback_includes_suppliers(monkeypatch, tmp_path) -> None:
    import src.api.services as services
    import src.data.supplier_sourcing as supplier_sourcing

    monkeypatch.setattr(services, "DATA_STATUS_JSON", tmp_path / "missing.json")
    monkeypatch.setattr(
        supplier_sourcing,
        "SUPPLIER_LATEST_JSON",
        tmp_path / "missing_suppliers.json",
    )
    payload = services.data_status()
    assert "suppliers" in payload
    assert payload["suppliers"]["enabled"] is False


def test_customs_comtrade_subscription_key(monkeypatch) -> None:
    import sys

    import pandas as pd

    import src.data.customs as customs

    class FakeComtrade:
        calls: list[tuple[str, dict]] = []

        @staticmethod
        def getFinalData(subscription_key: str, **kwargs):
            FakeComtrade.calls.append((subscription_key, kwargs))
            return pd.DataFrame({"primaryValue": [123.0]})

        @staticmethod
        def previewFinalData(**kwargs):
            raise AssertionError("preview should not be used when key configured")

    monkeypatch.setitem(sys.modules, "comtradeapicall", FakeComtrade)
    monkeypatch.setattr(customs, "COMTRADE_SUBSCRIPTION_KEY", "secret")
    monkeypatch.setattr(
        customs,
        "CATEGORY_HS_CODES",
        {"cn_changsha_mifen": {"code": "3924", "description": "塑料制品"}},
    )
    monkeypatch.setattr(customs, "RECENT_YEARS", (2024,))
    rows, period, errors = customs._comtrade_rows()
    assert FakeComtrade.calls
    assert FakeComtrade.calls[0][0] == "secret"
    assert rows[0]["source"] == "comtrade"
    assert period == "2024"


def test_amazon_robots_disallowed_skips(monkeypatch) -> None:
    import src.data.platform_rankings as rankings
    from src.data.legal_crawler import RobotsDisallowedError

    def blocked(*args, **kwargs):
        raise RobotsDisallowedError("robots.txt disallows")

    monkeypatch.setattr(
        "src.data.collector.collect_amazon_bestsellers",
        blocked,
    )
    payload = rankings.collect_rankings(
        providers=["amazon_bestsellers"],
        offline=False,
    )
    assert payload["providers"]["amazon_bestsellers"]["status"] == "skipped"
    assert payload["rows"][0]["platform"] == "mock"
