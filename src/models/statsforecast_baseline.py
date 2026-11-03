"""StatsForecast baseline: optional third forecast model for comparison."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
import pandas as pd

from src.config import TEST_WEEKS, TRAIN_WORKERS


def evaluate_all(df: pd.DataFrame) -> pd.DataFrame:
    """Evaluate AutoETS per category-market combo on the last TEST_WEEKS."""
    try:
        from statsforecast import StatsForecast
        from statsforecast.models import AutoETS
    except ImportError:  # pragma: no cover - optional dependency
        return pd.DataFrame(
            columns=[
                "category",
                "market",
                "model",
                "mape",
                "mae",
            ]
        )

    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    groups = list(frame.groupby(["category", "market"]))

    def _one(item: tuple[tuple[Any, Any], pd.DataFrame]) -> dict[str, Any]:
        (category, market), group = item
        group = group.sort_values("date")
        if len(group) <= TEST_WEEKS + 4:
            return {"category": category, "market": market, "model": "statsforecast", "mape": float("nan"), "mae": float("nan")}
        train = group.iloc[:-TEST_WEEKS]
        test = group.iloc[-TEST_WEEKS:]
        train_df = train[["date", "sales_volume"]].rename(
            columns={"date": "ds", "sales_volume": "y"}
        )
        try:
            sf = StatsForecast(
                models=[AutoETS(season_length=52)],
                freq="W",
                n_jobs=1,
            )
            sf.fit(train_df)
            forecast = sf.predict(h=len(test))
            predicted = forecast["AutoETS"].to_numpy(dtype=float)
        except Exception:  # noqa: BLE001 - keep pipeline running
            predicted = np.full(len(test), float(np.mean(train["sales_volume"])))
        actual = test["sales_volume"].to_numpy(dtype=float)
        mask = ~np.isnan(actual) & ~np.isnan(predicted) & (actual != 0)
        if mask.sum() == 0:
            mape = float("nan")
            mae = float("nan")
        else:
            a = actual[mask]
            p = predicted[mask]
            mape = float(np.mean(np.abs((a - p) / a)) * 100)
            mae = float(np.mean(np.abs(a - p)))
        return {
            "category": category,
            "market": market,
            "model": "statsforecast",
            "mape": round(mape, 3),
            "mae": round(mae, 3),
        }

    with ThreadPoolExecutor(max_workers=max(1, int(TRAIN_WORKERS))) as pool:
        rows = list(pool.map(_one, groups))
    return pd.DataFrame(rows)


__all__ = ["evaluate_all"]
