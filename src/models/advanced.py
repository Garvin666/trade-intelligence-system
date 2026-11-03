"""LightGBM 进阶模型：基于多源特征的回归预测与递归多步预测。"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.config import (
    FORECAST_HORIZON,
    LGBM_PARAMS,
    LGBM_TARGET_TRANSFORM,
    REAL_FEATURE_COLS,
    TARGET_COL,
    TEST_WEEKS,
    TRAIN_WORKERS,
)
from src.features.builder import FEATURE_COLS, build_features, make_features_for_next_row
from src.models.metrics import compute_metrics

logger = logging.getLogger(__name__)


class LightGBMAdvanced:
    """对单个品类/市场组合训练 LightGBM，支持评估与未来滚动预测。"""

    def __init__(
        self,
        category: str,
        market: str,
        horizon_days: int = FORECAST_HORIZON,
        params: dict | None = None,
        target_transform: str | None = None,
    ) -> None:
        self.category = category
        self.market = market
        self.horizon_days = horizon_days
        self.params = params or LGBM_PARAMS
        self.target_transform = target_transform or LGBM_TARGET_TRANSFORM
        self.model: lgb.LGBMRegressor | None = None
        self._residual_std: float = 0.0

    def _group(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[(df["category"] == self.category) & (df["market"] == self.market)]

    def _transform_target(self, values) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        if self.target_transform == "log1p":
            return np.log1p(arr)
        return arr

    def _inverse_target(self, values) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        if self.target_transform == "log1p":
            return np.expm1(arr)
        return arr

    def _fit_model(self, features: pd.DataFrame) -> lgb.LGBMRegressor:
        train = features.dropna(subset=FEATURE_COLS + [TARGET_COL]).copy()
        y = self._transform_target(train[TARGET_COL])
        model = lgb.LGBMRegressor(**self.params)
        model.fit(train[FEATURE_COLS], y)
        self._residual_std = float(np.std(y - model.predict(train[FEATURE_COLS])))
        return model

    def evaluate(self, df: pd.DataFrame, test_weeks: int = TEST_WEEKS) -> dict[str, float]:
        """按时间切分测试集，返回 MAPE/MAE。"""
        group = self._group(df).sort_values("date").reset_index(drop=True)
        features = build_features(group)
        features = features.dropna(subset=FEATURE_COLS + [TARGET_COL]).reset_index(drop=True)
        split_idx = len(features) - test_weeks
        if split_idx < 12:
            return {"mape": float("nan"), "mae": float("nan")}
        train = features.iloc[:split_idx]
        test = features.iloc[split_idx:]
        model = self._fit_model(train)
        pred = self._inverse_target(model.predict(test[FEATURE_COLS]))
        return compute_metrics(test[TARGET_COL], pd.Series(pred, index=test.index))

    def forecast(self, df: pd.DataFrame) -> pd.DataFrame:
        """递归预测未来 N 天（输出周粒度点并向前填充到日粒度）。"""
        group = self._group(df).sort_values("date").reset_index(drop=True)
        features = build_features(group).dropna(subset=FEATURE_COLS + [TARGET_COL]).reset_index(drop=True)
        self.model = self._fit_model(features)

        last_date = pd.to_datetime(features["date"]).max()
        last_row = features.iloc[-1]
        recent_sales = features[TARGET_COL].tolist()
        last_search = last_row["search_index"]

        weekly_points: list[dict] = []
        for week in range(1, 14):
            next_date = last_date + pd.Timedelta(days=week * 7)
            row = make_features_for_next_row(last_row, next_date, recent_sales)
            # 外生变量延续：搜索热度带轻微噪声衰减，价格与竞争沿用最近值
            row["search_index"] = float(np.clip(last_search * (1 - week * 0.005), 0, 100))
            row["search_trend_4"] = last_row["search_trend_4"]
            row["competition_change_4"] = last_row["competition_change_4"]
            row["price_change_4"] = last_row["price_change_4"]
            features_row = pd.DataFrame([row])[FEATURE_COLS]
            pred_t = float(self.model.predict(features_row)[0])
            pred = max(float(self._inverse_target(np.array([pred_t]))[0]), 1.0)
            lower_t = pred_t - 1.28 * self._residual_std
            upper_t = pred_t + 1.28 * self._residual_std
            yhat_lower = max(float(self._inverse_target(np.array([lower_t]))[0]), 0.0)
            yhat_upper = float(self._inverse_target(np.array([upper_t]))[0])
            weekly_points.append(
                {
                    "date": next_date.date().isoformat(),
                    "category": self.category,
                    "market": self.market,
                    "model": "lightgbm_advanced",
                    "yhat": round(pred, 2),
                    "yhat_lower": round(yhat_lower, 2),
                    "yhat_upper": round(yhat_upper, 2),
                }
            )
            recent_sales.append(pred)
            real_values = {
                column: (
                    float(row[column])
                    if column in row and pd.notna(row[column])
                    else 0.0
                )
                for column in REAL_FEATURE_COLS
            }
            last_row = pd.Series(
                {
                    "search_index": row["search_index"],
                    "bestseller_rank": last_row["bestseller_rank"],
                    "price_median": last_row["price_median"],
                    "review_growth": last_row["review_growth"],
                    "export_value": last_row["export_value"],
                    "competition_index": last_row["competition_index"],
                    TARGET_COL: pred,
                    "search_trend_4": row["search_trend_4"],
                    "competition_change_4": row["competition_change_4"],
                    "price_change_4": row["price_change_4"],
                    **real_values,
                }
            )

        weekly = pd.DataFrame(weekly_points)
        # 向前填充为日粒度，截取 horizon_days
        daily_rows = []
        for _, wp in weekly.iterrows():
            start = pd.Timestamp(wp["date"]) - pd.Timedelta(days=6)
            for day_offset in range(7):
                day = start + pd.Timedelta(days=day_offset)
                if day <= last_date + pd.Timedelta(days=self.horizon_days):
                    daily_rows.append(
                        {
                            "date": day.date().isoformat(),
                            "category": wp["category"],
                            "market": wp["market"],
                            "model": wp["model"],
                            "yhat": wp["yhat"],
                            "yhat_lower": wp["yhat_lower"],
                            "yhat_upper": wp["yhat_upper"],
                        }
                    )
        return pd.DataFrame(daily_rows).head(self.horizon_days)


def evaluate_all(df: pd.DataFrame, test_weeks: int = TEST_WEEKS) -> pd.DataFrame:
    """遍历所有品类/市场组合，返回进阶模型评估表。"""
    combos = list(df.groupby(["category", "market"], observed=True))

    def _one(item: tuple[tuple[Any, Any], pd.DataFrame]) -> dict[str, Any]:
        (category, market), _ = item
        try:
            metrics = LightGBMAdvanced(category, market).evaluate(
                df, test_weeks=test_weeks
            )
        except Exception as exc:  # noqa: BLE001 - 单组合失败不阻断全量演示
            logger.warning("LightGBM evaluate fallback: %s/%s: %s", category, market, exc)
            metrics = {"mape": float("nan"), "mae": float("nan")}
        return {
            "category": category,
            "market": market,
            "model": "lightgbm_advanced",
            **metrics,
        }

    with ThreadPoolExecutor(max_workers=max(1, int(TRAIN_WORKERS))) as pool:
        rows = list(pool.map(_one, combos))
    return pd.DataFrame(rows)


def forecast_all(df: pd.DataFrame) -> pd.DataFrame:
    """遍历所有品类/市场组合，返回汇总预测表。"""
    combos = list(df.groupby(["category", "market"], observed=True))

    def _one(item: tuple[tuple[Any, Any], pd.DataFrame]) -> pd.DataFrame:
        (category, market), _ = item
        try:
            return LightGBMAdvanced(category, market).forecast(df)
        except Exception as exc:  # noqa: BLE001 - 单组合失败不阻断全量演示
            logger.warning("LightGBM forecast fallback: %s/%s: %s", category, market, exc)
            group = df[(df["category"] == category) & (df["market"] == market)].sort_values("date")
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
                    "model": "lightgbm_advanced",
                    "yhat": round(mean, 2),
                    "yhat_lower": round(mean * 0.8, 2),
                    "yhat_upper": round(mean * 1.2, 2),
                }
            )

    with ThreadPoolExecutor(max_workers=max(1, int(TRAIN_WORKERS))) as pool:
        frames = list(pool.map(_one, combos))
    return pd.concat(frames, ignore_index=True)
