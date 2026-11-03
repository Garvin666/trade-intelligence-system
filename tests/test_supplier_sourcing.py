"""货源/供应商采集适配器测试。"""

from __future__ import annotations

import json
import subprocess

from src.data import supplier_sourcing as suppliers


def test_offline_uses_deterministic_mock() -> None:
    payload = suppliers.collect_suppliers(offline=True)
    assert payload["provider"] == "mock"
    assert payload["fallback_used"] is True
    assert payload["source_count"] > 0
    assert all(row["source"] == "mock" for row in payload["rows"])
    status = suppliers.supplier_status(payload)
    assert status["enabled"] is True
    assert status["rows"] == payload["source_count"]


def test_cli_rows_normalized(monkeypatch) -> None:
    sample = [
        {
            "companyName": "深圳优选供应链",
            "memberId": "b2b-123",
            "province": "广东",
            "city": "深圳",
            "serviceYears": 8,
            "repeatRate": 0.72,
            "responseRate": 0.91,
            "score": 88.0,
            "signals": ["factory"],
        }
    ]
    monkeypatch.setattr(suppliers, "SUPPLIER_CLI_PATH", "1688")
    monkeypatch.setattr(
        suppliers,
        "_run_cli",
        lambda keyword, cli: json.dumps({"suppliers": sample}, ensure_ascii=False),
    )
    payload = suppliers.collect_suppliers(
        {"cn_changsha_mifen": "smart pet feeder"},
        providers=["1688_cli"],
        offline=False,
    )
    assert payload["provider"] == "1688_cli"
    assert payload["fallback_used"] is False
    row = payload["rows"][0]
    assert row["supplier_name"] == "深圳优选供应链"
    assert row["member_id"] == "b2b-123"
    assert row["location"] == "广东 深圳"
    assert row["service_years"] == 8.0
    assert row["repeat_rate"] == 0.72
    assert row["response_rate"] == 0.91
    assert row["source"] == "1688_cli"


def test_cli_missing_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(suppliers, "SUPPLIER_CLI_PATH", None)
    monkeypatch.setattr(suppliers.shutil, "which", lambda name: None)
    payload = suppliers.collect_suppliers(
        {"cn_changsha_mifen": "smart pet feeder"},
        providers=["1688_cli"],
        offline=False,
    )
    assert payload["provider"] == "mock"
    assert payload["fallback_used"] is True
    assert any("1688" in error for error in payload["errors"])


def test_cli_timeout_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(suppliers, "SUPPLIER_CLI_PATH", "1688")

    def boom(keyword: str, cli: str) -> str:
        raise subprocess.TimeoutExpired(cmd=cli, timeout=90)

    monkeypatch.setattr(suppliers, "_run_cli", boom)
    payload = suppliers.collect_suppliers(
        {"cn_changsha_mifen": "smart pet feeder"},
        providers=["1688_cli"],
        offline=False,
    )
    assert payload["provider"] == "mock"
    assert payload["fallback_used"] is True
    assert payload["errors"]


def test_cli_bad_json_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(suppliers, "SUPPLIER_CLI_PATH", "1688")
    monkeypatch.setattr(
        suppliers,
        "_run_cli",
        lambda keyword, cli: "not-json",
    )
    payload = suppliers.collect_suppliers(
        {"cn_changsha_mifen": "smart pet feeder"},
        providers=["1688_cli"],
        offline=False,
    )
    assert payload["provider"] == "mock"
    assert payload["fallback_used"] is True
    assert payload["coverage"]["real"] == 0
    assert payload["coverage"]["mock"] == 1


def test_partial_coverage_fills_missing_with_mock(monkeypatch) -> None:
    monkeypatch.setattr(suppliers, "SUPPLIER_CLI_PATH", "1688")

    def fake_run(keyword: str, cli: str) -> str:
        if keyword == "smart pet feeder":
            return json.dumps(
                [{"companyName": "深圳优选供应链", "score": 90.0}],
                ensure_ascii=False,
            )
        raise RuntimeError("login required")

    monkeypatch.setattr(suppliers, "_run_cli", fake_run)
    payload = suppliers.collect_suppliers(
        {"cn_changsha_mifen": "smart pet feeder", "cn_latiao": "home storage organizer"},
        providers=["1688_cli"],
        offline=False,
    )
    assert payload["provider"] == "1688_cli"
    assert payload["fallback_used"] is True
    assert payload["coverage"]["real"] == 1
    assert payload["coverage"]["mock"] == 1
    assert any(row["source"] == "mock" for row in payload["rows"])


def test_parse_cli_output_supports_jsonl() -> None:
    text = '{"companyName":"A"}\n{"companyName":"B"}\n'
    records = suppliers._parse_cli_output(text)
    assert [record["companyName"] for record in records] == ["A", "B"]


def test_save_load_status_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(suppliers, "SUPPLIER_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(suppliers, "SUPPLIER_LATEST_JSON", tmp_path / "latest.json")
    payload = suppliers.collect_suppliers(offline=True)
    path = suppliers.save_latest_suppliers(payload)
    assert path.exists()
    loaded = suppliers.load_latest_suppliers()
    assert loaded["source_count"] == payload["source_count"]
    status = suppliers.supplier_status(loaded)
    assert status["snapshot"] == "output/suppliers/latest.json"
