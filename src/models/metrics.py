"""模型评估指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    """计算 MAPE 与 MAE。"""
    actual = pd.to_numeric(actual, errors="coerce")
    predicted = pd.to_numeric(predicted, errors="coerce")
    a = actual.to_numpy(dtype=float)
    p = predicted.to_numpy(dtype=float)
    mask = ~np.isnan(a) & ~np.isnan(p) & (a != 0)
    if mask.sum() == 0:
        return {"mape": float("nan"), "mae": float("nan")}
    a = a[mask]
    p = p[mask]
    mape = float(np.mean(np.abs((a - p) / a)) * 100)
    mae = float(np.mean(np.abs(a - p)))
    return {"mape": round(mape, 3), "mae": round(mae, 3)}
