"""Regression tests for four-brain real-evidence integration."""

from __future__ import annotations

import json
from pathlib import Path

from src.api import brain_bridge
from src.models import real_proxy


def test_four_brain_result_attaches_real_evidence(tmp_path: Path, monkeypatch) -> None:
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps({"status": "ok", "combos": 1980}),
        encoding="utf-8",
    )
    monkeypatch.setattr(brain_bridge, "REAL_TRAINING_STATUS_JSON", status_path)
    monkeypatch.setattr(
        real_proxy,
        "proxy_evidence_score",
        lambda category, market: {
            "available": True,
            "score": 72.5,
            "predicted_demand": 188.0,
            "level": "high",
            "note": "真实销量代理证据已接入。",
        },
    )
    monkeypatch.setattr(real_proxy, "load_real_proxy_model", lambda: (object(), {}))

    result = brain_bridge._attach_real_evidence(
        {"category": "cn_latiao", "payload": {"market": "us"}},
        {"market": "us"},
    )
    evidence = result["real_evidence"]
    assert evidence["proxy"]["available"] is True
    assert evidence["proxy"]["score"] == 72.5
    assert evidence["training_status"]["combos"] == 1980
