"""StatsForecast baseline smoke test on a small synthetic dataset."""

from __future__ import annotations

import pandas as pd
import pytest

from src.models.statsforecast_baseline import evaluate_all


@pytest.fixture
def small_frame() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2024-01-01", periods=70, freq="W")
    for category in ("cn_latiao", "cn_changsha_mifen"):
        for i, date in enumerate(dates):
            rows.append(
                {
                    "category": category,
                    "market": "us",
                    "date": date,
                    "sales_volume": 100 + 10 * (i % 12),
                }
            )
    return pd.DataFrame(rows)


def test_evaluate_all_returns_statsforecast_rows(small_frame: pd.DataFrame) -> None:
    result = evaluate_all(small_frame)
    assert not result.empty
    assert set(result["model"].unique()) == {"statsforecast"}
    assert set(result["category"].unique()) == {"cn_latiao", "cn_changsha_mifen"}
    assert result["mape"].notna().all()
