"""Tests for the shared data-crawler foundation (base / http / search / policy_common)."""

from __future__ import annotations

import json

from src.data.base import (
    load_latest,
    pageview_trend_pct,
    save_latest,
    seed_for,
    seed_int,
)
from src.data.policy_common import (
    actions_for,
    classify,
    extract_min_duty,
    extract_rate,
    normalize_date,
)
from src.data.search import SEARCH_PROVIDER_CHAIN, chain_search


def test_seed_int_is_deterministic_and_bounded() -> None:
    a = seed_int("cn_changsha_mifen", "us")
    b = seed_int("cn_changsha_mifen", "us")
    c = seed_int("cn_changsha_mifen", "eu")
    assert a == b
    assert a != c
    assert 0 <= a <= 0xFFFFFFFF


def test_seed_for_is_float_in_unit_interval() -> None:
    value = seed_for("cn_latiao", "us")
    assert 0.0 <= value < 1.0
    assert seed_for("cn_latiao", "us") == value


def test_pageview_trend_pct_halves() -> None:
    items = [
        {"date": "20260701", "views": 100},
        {"date": "20260702", "views": 100},
        {"date": "20260703", "views": 200},
        {"date": "20260704", "views": 200},
    ]
    assert pageview_trend_pct(items) == 100.0
    assert pageview_trend_pct([]) == 0.0
    assert pageview_trend_pct([{"date": "20260701", "views": 10}]) == 0.0


def test_save_and_load_latest_roundtrip(tmp_path) -> None:
    path = tmp_path / "nested" / "latest.json"
    payload = {"generated_at": "2026-08-13", "rows": [1, 2]}
    assert save_latest(payload, path) == path
    assert path.exists()
    assert load_latest(path) == payload


def test_load_latest_returns_default_on_missing(tmp_path) -> None:
    default = {"rows": []}
    assert load_latest(tmp_path / "missing.json", default) == default
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    assert load_latest(corrupt, default) == default


def test_classify_direction_and_impact() -> None:
    assert classify("美国加征关税") == ("high", "restrict")
    assert classify("上调进口关税") == ("medium", "restrict")
    assert classify("支持跨境电商综试区扩容") == ("medium", "facilitate")
    assert classify("简化清关流程") == ("low", "facilitate")
    assert classify("the tariff rate increases") == ("medium", "restrict")


def test_extract_rate_and_min_duty() -> None:
    assert extract_rate("税率上调 25%") == 0.25
    assert extract_rate("无数字文本") == 0.0
    assert extract_min_duty("$ 800 美元以下免税") == 800.0
    assert extract_min_duty("免税额度 150美元") == 150.0
    assert extract_min_duty("无金额") == 0.0


def test_normalize_date_formats() -> None:
    assert normalize_date("2026-08-13") == "2026-08-13"
    assert normalize_date("2026/8/3") == "2026-08-03"
    assert normalize_date("2026年8月13日") == "2026-08-13"
    assert normalize_date(None, "2026-01-01") == "2026-01-01"


def test_actions_for_truncates_low_impact() -> None:
    assert actions_for("tariff", "low") == ["核对清关方式", "转正式清关"]
    assert len(actions_for("tariff", "high")) == 3
    assert actions_for("unknown", "high") == ["持续监控政策公告"]


def test_chain_search_crawler_success() -> None:
    def crawler(query, max_results=None, config=None):
        return {
            "results": [{"title": "t", "snippet": "s", "link": "http://x"}],
            "fallback_used": False,
            "pageview_trend_pct": 1.5,
        }

    payload = chain_search(
        "pet feeder",
        3,
        provider="crawler",
        crawler_fn=crawler,
        web_fn=lambda q, **k: [],
        mock_fn=lambda q, n: [],
    )
    assert payload["provider"] == "crawler"
    assert payload["fallback_used"] is False
    assert payload["pageview_trend_pct"] == 1.5


def test_chain_search_crawler_falls_back_to_duckduckgo() -> None:
    def crawler(query, max_results=None, config=None):
        raise ConnectionError("offline")

    def web(query, max_results=None, config=None):
        return [{"title": "ddg", "snippet": "s", "link": "http://ddg"}]

    payload = chain_search(
        "pet feeder",
        3,
        provider="crawler",
        crawler_fn=crawler,
        web_fn=web,
        mock_fn=lambda q, n: [],
    )
    assert payload["fallback_used"] is True
    assert payload["fallback_provider"] == "duckduckgo_html"
    assert payload["results"][0]["title"] == "ddg"


def test_chain_search_falls_back_to_mock() -> None:
    def crawler(query, max_results=None, config=None):
        raise ConnectionError("offline")

    def web(query, max_results=None, config=None):
        raise ConnectionError("offline")

    def mock(query, max_results=None):
        return [{"title": "模拟结果", "snippet": "s", "link": ""}]

    payload = chain_search(
        "pet feeder",
        3,
        provider="crawler",
        crawler_fn=crawler,
        web_fn=web,
        mock_fn=mock,
    )
    assert payload["fallback_used"] is True
    assert payload["fallback_provider"] == "mock"
    assert payload["results"][0]["title"] == "模拟结果"


def test_chain_search_non_crawler_provider() -> None:
    def web(query, max_results=None, config=None):
        raise ConnectionError("offline")

    payload = chain_search(
        "pet feeder",
        3,
        provider="tavily",
        crawler_fn=lambda q, **k: {},
        web_fn=web,
        mock_fn=lambda q, n: [{"title": "mock", "snippet": "", "link": ""}],
    )
    assert payload["provider"] == "tavily"
    assert payload["fallback_used"] is True
    assert payload["fallback_provider"] == "mock"


def test_search_provider_chain_constant() -> None:
    assert SEARCH_PROVIDER_CHAIN == ("crawler", "duckduckgo_html", "mock")


def test_search_config_timeout_reads_milliseconds(monkeypatch) -> None:
    from src.four_brain.data_tools import _resolve_search_config

    monkeypatch.setenv("SEARCH_TIMEOUT_MS", "30000")
    monkeypatch.delenv("FOUR_BRAIN_SEARCH_TIMEOUT", raising=False)
    assert _resolve_search_config({})["timeout"] == 30.0


def test_search_config_timeout_falls_back_to_seconds(monkeypatch) -> None:
    from src.four_brain.data_tools import _resolve_search_config

    monkeypatch.delenv("SEARCH_TIMEOUT_MS", raising=False)
    monkeypatch.setenv("FOUR_BRAIN_SEARCH_TIMEOUT", "42")
    assert _resolve_search_config({})["timeout"] == 42.0


def test_search_config_timeout_default_when_unset(monkeypatch) -> None:
    from src.four_brain.data_tools import _resolve_search_config

    monkeypatch.delenv("SEARCH_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("FOUR_BRAIN_SEARCH_TIMEOUT", raising=False)
    assert _resolve_search_config({})["timeout"] == 20.0


def test_sources_registry_shape_and_enabled() -> None:
    from src.config import SEARCH_PROVIDERS, SOURCES, enabled_sources

    expected_order = [
        "crawler",
        "policy",
        "trends",
        "platform_rankings",
        "customs",
        "open_food_facts",
        "suppliers",
        "market_daily",
    ]
    assert list(SOURCES) == expected_order
    assert enabled_sources() == expected_order
    for name, cfg in SOURCES.items():
        assert "label" in cfg
        assert "enabled" in cfg
        assert "providers" in cfg or name == "market_daily"
        assert "output_dir" in cfg
    # 回退链里的 provider 都必须在受支持集合里
    assert set(SEARCH_PROVIDER_CHAIN) <= SEARCH_PROVIDERS
    # 搜索常量在 config / search / data_tools 之间是同一对象（单一来源）
    assert SEARCH_PROVIDER_CHAIN == ("crawler", "duckduckgo_html", "mock")


def test_foundation_json_roundtrip_preserves_unicode(tmp_path) -> None:
    path = tmp_path / "latest.json"
    save_latest({"标题": "关税", "rows": [{"date": "2026-08-13"}]}, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["标题"] == "关税"
