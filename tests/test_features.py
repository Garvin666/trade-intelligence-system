"""Feature engineering and target-transform regression tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import FORECAST_HORIZON, REAL_FEATURE_COLS, TARGET_COL
from src.data.synthetic import generate_market_data
from src.features.builder import FEATURE_COLS, build_features, make_features_for_next_row
from src.models.advanced import LightGBMAdvanced


def _small_df(weeks: int = 80) -> pd.DataFrame:
    return generate_market_data(
        categories=["cn_latiao", "cn_changsha_mifen"], markets=["us"], weeks=weeks, seed=11
    )


def test_build_features_contains_all_feature_cols() -> None:
    feat = build_features(_small_df())
    assert set(FEATURE_COLS).issubset(feat.columns)
    assert len(FEATURE_COLS) == 30 + len(REAL_FEATURE_COLS)


def test_next_row_features_match_feature_cols() -> None:
    df = _small_df()
    group = df[df["category"] == "cn_latiao"].sort_values("date").reset_index(drop=True)
    feat = build_features(group).dropna(subset=FEATURE_COLS + [TARGET_COL]).reset_index(drop=True)
    row = make_features_for_next_row(
        feat.iloc[-1],
        pd.Timestamp("2026-01-01"),
        feat[TARGET_COL].tolist(),
    )
    assert set(row.keys()) == set(FEATURE_COLS)
    assert all(v is not None and not (isinstance(v, float) and np.isnan(v)) for v in row.values())


def test_log1p_forecast_and_eval() -> None:
    df = _small_df()
    model = LightGBMAdvanced("cn_latiao", "us", target_transform="log1p")
    fc = model.forecast(df)
    assert len(fc) == FORECAST_HORIZON
    assert (fc["yhat"] > 0).all()
    assert (fc["yhat_lower"] <= fc["yhat_upper"]).all()
    metrics = model.evaluate(df, test_weeks=8)
    assert metrics["mape"] == metrics["mape"]
    assert metrics["mae"] == metrics["mae"]
