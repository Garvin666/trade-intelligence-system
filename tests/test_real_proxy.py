"""Regression tests for the real-demand proxy model."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.models import real_proxy


def _dataset(rows: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    categories = ["cn_latiao", "cn_changsha_mifen", "cn_longjing"]
    markets = ["us", "sea", "eu"]
    index = np.arange(rows)
    frame = pd.DataFrame(
        {
            "provider": np.array(["shopee", "amazon", "ebay"])[index % 3],
            "category": np.array(categories)[index % 3],
            "market": np.array(markets)[index % 3],
            "date": pd.date_range("2026-07-01", periods=rows, freq="D"),
            "price": rng.uniform(5, 80, rows),
            "rating": rng.uniform(3.5, 5.0, rows),
            "reviews": rng.integers(0, 500, rows),
            "demand": rng.integers(1, 500, rows),
        }
    )
    frame["date"] = pd.to_datetime(frame["date"])
    frame["month_sin"] = np.sin(2 * np.pi * frame["date"].dt.month / 12)
    frame["month_cos"] = np.cos(2 * np.pi * frame["date"].dt.month / 12)
    frame["week_sin"] = np.sin(2 * np.pi * frame["date"].dt.isocalendar().week.astype(float) / 52)
    frame["week_cos"] = np.cos(2 * np.pi * frame["date"].dt.isocalendar().week.astype(float) / 52)
    frame["demand_log"] = np.log1p(frame["demand"])
    return frame


def test_train_proxy_model_and_score(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(real_proxy, "build_proxy_dataset", _dataset)
    monkeypatch.setattr(real_proxy, "REAL_PROXY_MODEL", tmp_path / "proxy.joblib")
    monkeypatch.setattr(real_proxy, "REAL_PROXY_META", tmp_path / "proxy_meta.json")
    monkeypatch.setattr(real_proxy, "REAL_PROXY_STATUS_JSON", tmp_path / "proxy_status.json")
    real_proxy.clear_proxy_cache()

    payload = real_proxy.train_real_proxy_model()
    assert payload["status"] == "ok"
    assert (tmp_path / "proxy.joblib").exists()
    assert payload["metrics"]["folds"] >= 2

    score = real_proxy.proxy_evidence_score("cn_latiao", "us")
    assert score["available"] is True
    assert 0.0 <= score["score"] <= 100.0


def test_train_proxy_model_skips_small_dataset(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(real_proxy, "build_proxy_dataset", lambda: _dataset(rows=10))
    monkeypatch.setattr(real_proxy, "REAL_PROXY_MODEL", tmp_path / "proxy.joblib")
    monkeypatch.setattr(real_proxy, "REAL_PROXY_META", tmp_path / "proxy_meta.json")
    monkeypatch.setattr(real_proxy, "REAL_PROXY_STATUS_JSON", tmp_path / "proxy_status.json")
    real_proxy.clear_proxy_cache()

    payload = real_proxy.train_real_proxy_model()
    assert payload["status"] == "skipped"
    assert real_proxy.load_real_proxy_model() is None
