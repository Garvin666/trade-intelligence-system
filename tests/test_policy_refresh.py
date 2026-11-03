"""Policy snapshot refresh and dynamic policy scoring tests."""

from __future__ import annotations

import json

import pytest

from src.data.policy_refresh import (
    MAX_EVENTS_PER_DAY,
    policy_snapshot_status,
    refresh_policy_snapshot,
)
from src.trade.policy import (
    evaluate_policy,
    load_policy_events,
    policy_watchlist,
)


def _write_latest(tmp_path, events) -> None:
    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps({"events": events}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_refresh_policy_snapshot_offline_writes_files(tmp_path) -> None:
    out_dir = tmp_path / "policy" / "daily"
    latest = tmp_path / "policy" / "latest.json"
    payload = refresh_policy_snapshot(
        offline=True,
        policy_date="2026-08-13",
        out_dir=out_dir,
        latest_path=latest,
        max_results=2,
    )
    assert payload["fallback_used"] is True
    assert payload["date"] == "2026-08-13"
    assert not payload["events"]
    assert payload["candidate_events"]
    regions = {event["region"] for event in payload["events"]}
    assert not regions
    candidate_regions = {event["region"] for event in payload["candidate_events"]}
    assert {"foreign", "domestic", "global"} <= candidate_regions
    assert (out_dir / "2026-08-13.json").exists()
    assert latest.exists()
    status = policy_snapshot_status(payload)
    assert status["verified_events"] == len(payload["events"])
    assert status["candidate_events"] == len(payload["candidate_events"])
    assert status["snapshot"] == "output/policy/latest.json"


def test_refresh_policy_snapshot_dedupes_and_caps(tmp_path) -> None:
    def same_search(query, max_results=3, provider="duckduckgo_html"):
        return {
            "provider": provider,
            "fallback_used": False,
            "results": [
                {
                    "title": "同一政策标题",
                    "snippet": "内容",
                    "link": "https://example.com",
                    "source": "test",
                }
            ],
        }

    payload = refresh_policy_snapshot(
        same_search,
        policy_date="2026-08-13",
        out_dir=tmp_path / "daily",
        latest_path=tmp_path / "latest.json",
        max_results=1,
        include_official_sources=False,
    )
    titles = [
        (event["title"], event["market"])
        for event in payload["candidate_events"]
    ]
    assert len(titles) == len(set(titles))
    assert len(payload["candidate_events"]) <= MAX_EVENTS_PER_DAY
    assert payload["events"] == []


def test_refresh_policy_snapshot_preserves_previous_verified_offline(tmp_path) -> None:
    latest = tmp_path / "policy" / "latest.json"
    latest.parent.mkdir(parents=True)
    previous = {
        "code": "pol-official-prev",
        "title": "此前已验证官方政策",
        "market": "us",
        "region": "foreign",
        "policy_type": "tariff",
        "effective_date": "2026-08-10",
        "published_at": "2026-08-10",
        "verified": True,
        "fallback_used": False,
        "url": "https://example.com/official/prev",
        "provider": "federal_register",
        "source_type": "official",
    }
    latest.write_text(
        json.dumps({"events": [previous]}),
        encoding="utf-8",
    )
    payload = refresh_policy_snapshot(
        offline=True,
        policy_date="2026-08-14",
        out_dir=tmp_path / "policy" / "daily",
        latest_path=latest,
        include_search=False,
    )
    assert payload["events"] == [previous]
    assert all(not event.get("fallback_used") for event in payload["events"])


def test_load_policy_events_merges_snapshot(monkeypatch, tmp_path) -> None:
    latest = _write_latest(
        tmp_path,
        [
            {
                "code": "pol-cn-1",
                "title": "国内退税新政",
                "market": "cn",
                "region": "domestic",
                "policy_type": "rebate",
                "effective_date": "2026-08-13",
                "rate_ad_valorem": 0.0,
                "min_duty_usd": 0.0,
                "cost_adjustment_pct": 0.02,
                "actions": ["核对退税"],
                "categories": [],
                "impact_level": "medium",
                "direction": "restrict",
                "heuristic": False,
                "verified": True,
            }
        ],
    )
    monkeypatch.setattr("src.trade.policy.POLICY_LATEST_JSON", latest)
    events = load_policy_events()
    codes = {event.code for event in events}
    assert {"us-de-minimis-2025", "eu-low-value-vat-2026", "pol-cn-1"} <= codes


def test_load_policy_events_skips_unverified_snapshot(monkeypatch, tmp_path) -> None:
    latest = _write_latest(
        tmp_path,
        [
            {
                "code": "pol-search-candidate",
                "title": "搜索候选事件",
                "market": "us",
                "region": "foreign",
                "policy_type": "tariff",
                "effective_date": "2026-08-13",
                "verified": False,
                "fallback_used": True,
            }
        ],
    )
    monkeypatch.setattr("src.trade.policy.POLICY_LATEST_JSON", latest)
    events = load_policy_events()
    codes = {event.code for event in events}
    assert "pol-search-candidate" not in codes


def test_domestic_event_affects_policy_alert(monkeypatch, tmp_path) -> None:
    latest = _write_latest(
        tmp_path,
        [
            {
                "code": "pol-cn-rebate",
                "title": "出口退税率下调",
                "market": "cn",
                "region": "domestic",
                "policy_type": "rebate",
                "effective_date": "2026-08-01",
                "cost_adjustment_pct": 0.10,
                "actions": ["核对退税档位"],
                "categories": [],
                "impact_level": "medium",
                "direction": "restrict",
                "verified": True,
            }
        ],
    )
    monkeypatch.setattr("src.trade.policy.POLICY_LATEST_JSON", latest)
    alert = evaluate_policy(
        "cn_latiao",
        "us",
        30.0,
        20.0,
        policy_date="2026-08-13",
    )
    assert alert.cost_adjustment_pct == pytest.approx(0.10, abs=1e-4)
    assert alert.heuristic is False


def test_official_watch_only_event_does_not_change_rate(monkeypatch, tmp_path) -> None:
    events = [
        {
            "code": "pol-news-official",
            "title": "目标国发布监管新规",
            "market": "global",
            "region": "global",
            "policy_type": "news",
            "effective_date": "2026-08-01",
            "impact_level": "high",
            "direction": "restrict",
            "actions": [],
            "categories": [],
            "verified": True,
            "heuristic": False,
        }
    ]
    latest = _write_latest(tmp_path, events)
    monkeypatch.setattr("src.trade.policy.POLICY_LATEST_JSON", latest)
    alert = evaluate_policy(
        "cn_latiao",
        "sea",
        30.0,
        20.0,
        policy_date="2026-08-13",
    )
    assert alert.cost_adjustment_pct == pytest.approx(0.0, abs=1e-4)
    # 基线税率由 132 个食品 SKU 的 tariff_base × 市场系数派生，此处按工程值比对，
    # 避免品类目录调整后再出现硬编码期望值漂移。
    from src.trade.policy_models import BASE_TARIFF_RATE

    assert alert.effective_tariff_rate == pytest.approx(
        BASE_TARIFF_RATE["sea"]["cn_latiao"], abs=1e-4
    )
    assert alert.heuristic is False


def test_build_trade_decision_applies_cost_adjustment(
    monkeypatch, tmp_path
) -> None:
    from src.trade.decision import build_trade_decision

    latest = _write_latest(
        tmp_path,
        [
            {
                "code": "pol-cn-cost",
                "title": "出口退税下调",
                "market": "cn",
                "region": "domestic",
                "policy_type": "rebate",
                "effective_date": "2026-08-01",
                "cost_adjustment_pct": 0.10,
                "actions": ["核对退税"],
                "categories": [],
                "impact_level": "medium",
                "direction": "restrict",
                "verified": True,
            }
        ],
    )
    monkeypatch.setattr("src.trade.policy.POLICY_LATEST_JSON", latest)
    row = build_trade_decision("cn_latiao", "sea", 30.0, 75.0)
    assert row["policy_cost_adjustment_pct"] == pytest.approx(0.10, abs=1e-4)
    assert "pol-cn-cost" in row["policy_event_codes"]
    assert row["policy_message"]


def test_policy_watchlist_includes_region_fields(monkeypatch, tmp_path) -> None:
    latest = _write_latest(
        tmp_path,
        [
            {
                "code": "pol-cn-zone",
                "title": "综试区扩围",
                "market": "cn",
                "region": "domestic",
                "policy_type": "macro",
                "effective_date": "2026-08-13",
                "actions": [],
                "categories": [],
                "impact_level": "low",
                "direction": "facilitate",
                "verified": True,
            }
        ],
    )
    monkeypatch.setattr("src.trade.policy.POLICY_LATEST_JSON", latest)
    items = policy_watchlist("2026-08-13")
    regions = {item["region"] for item in items}
    assert "foreign" in regions
    assert "domestic" in regions
    assert all("impact_level" in item and "policy_type" in item for item in items)
