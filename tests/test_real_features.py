"""Regression tests for the real-evidence feature bank."""

from __future__ import annotations

import pandas as pd

from src.config import REAL_FEATURE_COLS
from src.data import real_features
from src.data.synthetic import generate_market_data


def test_augment_clean_data_preserves_rows_and_adds_real_columns(monkeypatch) -> None:
    clean = generate_market_data(
        categories=["cn_latiao", "cn_changsha_mifen"],
        markets=["us"],
        weeks=24,
        seed=7,
    )
    bank = pd.DataFrame(
        [
            {
                "category": "cn_latiao",
                "market": "us",
                "real_price_median": 32.5,
                "real_rating_median": 4.4,
                "real_reviews_median": 120.0,
                "real_demand_median": 90.0,
                "real_customs_export": 1200.0,
                "real_crawler_trend_pct": 2.5,
                "real_evidence_score": 60.0,
            }
        ]
    )
    monkeypatch.setattr(real_features, "_trend_date_features", lambda: pd.DataFrame())
    monkeypatch.setattr(real_features, "_ranking_date_features", lambda: pd.DataFrame())
    augmented = real_features.augment_clean_data(clean, feature_bank=bank)

    assert len(augmented) == len(clean)
    assert set(REAL_FEATURE_COLS).issubset(augmented.columns)
    assert augmented[REAL_FEATURE_COLS].notna().all().all()
    assert augmented.loc[augmented["category"] == "cn_latiao", "real_price_median"].eq(32.5).all()


def test_real_feature_bank_contains_expected_columns() -> None:
    bank = real_features.build_real_feature_bank()
    expected = {
        "category",
        "market",
        "real_price_median",
        "real_rating_median",
        "real_reviews_median",
        "real_demand_median",
        "real_customs_export",
        "real_crawler_trend_pct",
        "real_evidence_score",
    }
    assert expected.issubset(set(bank.columns))
