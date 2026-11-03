"""模型训练与预测测试（使用小样本加速）。"""

from __future__ import annotations

import pandas as pd

from src.config import FORECAST_HORIZON
from src.data.synthetic import generate_market_data
from src.models.advanced import LightGBMAdvanced
from src.models.baseline import ProphetBaseline


def _small_df(weeks: int = 80) -> pd.DataFrame:
    return generate_market_data(
        categories=["cn_latiao", "cn_changsha_mifen"], markets=["us"], weeks=weeks, seed=11
    )


def test_baseline_forecast_shape() -> None:
    df = _small_df()
    model = ProphetBaseline("cn_latiao", "us")
    fc = model.forecast(df[df["category"] == "cn_latiao"])
    assert len(fc) == FORECAST_HORIZON
    assert {"date", "yhat", "yhat_lower", "yhat_upper"}.issubset(fc.columns)
    assert (fc["yhat"] > 0).all()


def test_baseline_evaluate_returns_metrics() -> None:
    df = _small_df()
    model = ProphetBaseline("cn_latiao", "us")
    metrics = model.evaluate(df[df["category"] == "cn_latiao"], test_weeks=8)
    assert {"mape", "mae"}.issubset(metrics.keys())
    assert metrics["mape"] >= 0


def test_advanced_forecast_shape() -> None:
    df = _small_df()
    model = LightGBMAdvanced("cn_latiao", "us")
    fc = model.forecast(df)
    assert len(fc) == FORECAST_HORIZON
    assert {"date", "yhat", "yhat_lower", "yhat_upper"}.issubset(fc.columns)
    assert (fc["yhat"] > 0).all()


def test_advanced_evaluate_returns_metrics() -> None:
    df = _small_df()
    model = LightGBMAdvanced("cn_latiao", "us")
    metrics = model.evaluate(df, test_weeks=8)
    assert {"mape", "mae"}.issubset(metrics.keys())
    assert metrics["mape"] >= 0


def test_baseline_forecast_all_falls_back_on_single_failure(monkeypatch) -> None:
    from src.models import baseline as baseline_module

    df = _small_df()

    def _broken(self, group):
        raise RuntimeError("broken")

    monkeypatch.setattr(baseline_module.ProphetBaseline, "forecast", _broken)
    fc = baseline_module.forecast_all(df)
    combos = df.groupby(["category", "market"], observed=True).ngroups
    assert len(fc) == combos * FORECAST_HORIZON
    assert (fc["yhat"] > 0).all()


def test_advanced_forecast_all_falls_back_on_single_failure(monkeypatch) -> None:
    from src.models import advanced as advanced_module

    df = _small_df()

    def _broken(self, frame):
        raise RuntimeError("broken")

    monkeypatch.setattr(advanced_module.LightGBMAdvanced, "forecast", _broken)
    fc = advanced_module.forecast_all(df)
    combos = df.groupby(["category", "market"], observed=True).ngroups
    assert len(fc) == combos * FORECAST_HORIZON
    assert (fc["yhat"] > 0).all()
