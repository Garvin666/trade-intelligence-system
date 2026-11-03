"""Prophet 基线模型：单变量时间序列预测。"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
import pandas as pd
from prophet import Prophet

from src.config import (
    FORECAST_HORIZON,
    PROPHET_PARAMS,
    PROPHET_REGRESSORS,
    TARGET_COL,
    TEST_WEEKS,
    TRAIN_WORKERS,
)
from src.models.metrics import compute_metrics

logger = logging.getLogger(__name__)


def _prophet_df(df: pd.DataFrame, regressors: list[str] | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "ds": pd.to_datetime(df["date"]),
            "y": df[TARGET_COL].astype(float),
        }
    ).dropna()
    for name in regressors or ():
        if name not in df.columns:
            continue
        frame[name] = df[name].to_numpy(dtype=float)
    return frame


class ProphetBaseline:
    """对单个品类/市场组合训练 Prophet 并产出评估与预测。"""

    def __init__(
        self,
        category: str,
        market: str,
        horizon_days: int = FORECAST_HORIZON,
        params: dict | None = None,
        regressors: list[str] | None = None,
    ) -> None:
        self.category = category
        self.market = market
        self.horizon_days = horizon_days
        self.params = params or PROPHET_PARAMS
        self.regressors = list(regressors if regressors is not None else PROPHET_REGRESSORS)
        self.model: Prophet | None = None

    def _fit(self, df: pd.DataFrame) -> Prophet:
        model = Prophet(**self.params)
        regressors = [name for name in self.regressors if name in df.columns]
        prophet_df = _prophet_df(df, regressors)
        # 对数变换提升小样本稳定性，避免加性模型预测出负销量
        prophet_df["y"] = np.log(np.maximum(prophet_df["y"], 1e-6))
        for name in regressors:
            model.add_regressor(name)
        model.fit(prophet_df)
        return model

    def predict_frame(self, train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
        """在 ``train`` 上训练，逐点预测 ``test``，返回含实际值与区间的明细。

        列：date / actual / pred / pred_lower / pred_upper（pred_* 为反对数变换后的销量）。
        供滚动回测、业务指标（校准度/方向命中率）复用；``evaluate`` 即基于本方法汇总。
        """
        model = self._fit(train)
        regressors = [name for name in self.regressors if name in test.columns]
        future = pd.DataFrame({"ds": pd.to_datetime(test["date"])})
        for name in regressors:
            future[name] = test[name].to_numpy(dtype=float)
        pred = model.predict(future)
        return pd.DataFrame(
            {
                "date": pd.to_datetime(test["date"]).to_numpy(),
                "actual": pd.to_numeric(test[TARGET_COL], errors="coerce").to_numpy(dtype=float),
                "pred": np.exp(pred["yhat"].to_numpy(dtype=float)),
                "pred_lower": np.exp(pred["yhat_lower"].to_numpy(dtype=float)),
                "pred_upper": np.exp(pred["yhat_upper"].to_numpy(dtype=float)),
            }
        )

    def evaluate(self, df: pd.DataFrame, test_weeks: int = TEST_WEEKS) -> dict[str, float]:
        """使用最近 N 周作为测试集，返回 MAPE/MAE。"""
        df = df.sort_values("date").reset_index(drop=True)
        split_idx = len(df) - test_weeks
        if split_idx < 8:
            return {"mape": float("nan"), "mae": float("nan")}
        train = df.iloc[:split_idx]
        test = df.iloc[split_idx:]
        points = self.predict_frame(train, test)
        return compute_metrics(points["actual"], points["pred"])

    def forecast(self, df: pd.DataFrame) -> pd.DataFrame:
        """基于全量历史预测未来 N 天，返回日粒度预测。"""
        self.model = self._fit(df)
        future = self.model.make_future_dataframe(periods=self.horizon_days, freq="D")
        regressors = [name for name in self.regressors if name in df.columns]
        if regressors:
            last = df.iloc[-1]
            for name in regressors:
                future[name] = float(last[name])
        fc = self.model.predict(future)
        fc = fc.tail(self.horizon_days).copy()
        result = pd.DataFrame(
            {
                "date": pd.to_datetime(fc["ds"]).dt.date.astype(str),
                "category": self.category,
                "market": self.market,
                "model": "prophet_baseline",
                "yhat": np.exp(fc["yhat"].to_numpy(dtype=float)).round(2),
                "yhat_lower": np.exp(fc["yhat_lower"].to_numpy(dtype=float)).round(2),
                "yhat_upper": np.exp(fc["yhat_upper"].to_numpy(dtype=float)).round(2),
            }
        )
        return result

    def save(self, path) -> None:
        if self.model is None:
            raise RuntimeError("模型尚未训练，无法保存")
        payload = {
            "category": self.category,
            "market": self.market,
            "horizon_days": self.horizon_days,
            "model_json": self.model.to_json(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path, category: str, market: str) -> "ProphetBaseline":
        payload = json.loads(path.read_text(encoding="utf-8"))
        obj = cls(category, market, horizon_days=payload["horizon_days"])
        obj.model = Prophet.from_json(payload["model_json"])
        return obj


def evaluate_all(df: pd.DataFrame, test_weeks: int = TEST_WEEKS) -> pd.DataFrame:
    """遍历所有品类/市场组合，返回基线评估表。"""
    groups = list(df.groupby(["category", "market"], observed=True))

    def _one(item: tuple[tuple[Any, Any], pd.DataFrame]) -> dict[str, Any]:
        (category, market), group = item
        try:
            metrics = ProphetBaseline(category, market).evaluate(
                group, test_weeks=test_weeks
            )
        except Exception as exc:  # noqa: BLE001 - 单组合失败不阻断全量演示
            logger.warning("Prophet evaluate fallback: %s/%s: %s", category, market, exc)
            metrics = {"mape": float("nan"), "mae": float("nan")}
        return {
            "category": category,
            "market": market,
            "model": "prophet_baseline",
            **metrics,
        }

    with ThreadPoolExecutor(max_workers=max(1, int(TRAIN_WORKERS))) as pool:
        rows = list(pool.map(_one, groups))
    return pd.DataFrame(rows)


def forecast_all(df: pd.DataFrame) -> pd.DataFrame:
    """遍历所有品类/市场组合，返回汇总预测表。"""
    groups = list(df.groupby(["category", "market"], observed=True))

    def _one(item: tuple[tuple[Any, Any], pd.DataFrame]) -> pd.DataFrame:
        (category, market), group = item
        try:
            return ProphetBaseline(category, market).forecast(group)
        except Exception as exc:  # noqa: BLE001 - 单组合失败不阻断全量演示
            logger.warning("Prophet forecast fallback: %s/%s: %s", category, market, exc)
            group = group.sort_values("date")
            mean = float(group[TARGET_COL].mean()) if not group.empty else 1.0
            last_date = pd.to_datetime(group["date"]).max() if not group.empty else pd.Timestamp.today()
            return pd.DataFrame(
                {
                    "date": [
                        (last_date + pd.Timedelta(days=offset)).date().isoformat()
                        for offset in range(1, FORECAST_HORIZON + 1)
                    ],
                    "category": category,
                    "market": market,
                    "model": "prophet_baseline",
                    "yhat": round(mean, 2),
                    "yhat_lower": round(mean * 0.8, 2),
                    "yhat_upper": round(mean * 1.2, 2),
                }
            )

    with ThreadPoolExecutor(max_workers=max(1, int(TRAIN_WORKERS))) as pool:
        frames = list(pool.map(_one, groups))
    return pd.concat(frames, ignore_index=True)
