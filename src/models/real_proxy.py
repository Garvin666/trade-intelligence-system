"""Real-demand proxy model trained from local product datasets.

Amazon bought-past-month, eBay sold-count and Shopee liked-count values are
used as demand labels. The model is advisory only: recommendation evidence
blends it with crawler evidence and falls back to the existing heuristic when
it is unavailable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from src.config import (
    RANDOM_SEED,
    REAL_PROXY_META,
    REAL_PROXY_MODEL,
    REAL_PROXY_STATUS_JSON,
)
from src.data.real_features import build_product_rows

MIN_LABELED_ROWS = 500

NUMERIC_FEATURES = [
    "price",
    "rating",
    "reviews",
    "month_sin",
    "month_cos",
    "week_sin",
    "week_cos",
]
CATEGORICAL_FEATURES = ["provider", "category", "market"]

_PROXY_CACHE: tuple[Any, dict[str, Any]] | None = None
def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_cycle_columns(dates: pd.Series) -> pd.DataFrame:
    parsed = pd.to_datetime(dates, errors="coerce")
    return pd.DataFrame(
        {
            "month_sin": np.sin(2 * np.pi * parsed.dt.month / 12),
            "month_cos": np.cos(2 * np.pi * parsed.dt.month / 12),
            "week_sin": np.sin(2 * np.pi * parsed.dt.isocalendar().week.astype(float) / 52),
            "week_cos": np.cos(2 * np.pi * parsed.dt.isocalendar().week.astype(float) / 52),
        },
        index=dates.index,
    )


def build_proxy_dataset() -> pd.DataFrame:
    """Return product rows that have a real demand label and complete features."""
    products = build_product_rows()
    labeled = products[
        products["demand"].notna()
        & (products["demand"] > 0)
        & products["category"].notna()
        & products["market"].notna()
    ].copy()
    if labeled.empty:
        return labeled
    for column in ("price", "rating", "reviews"):
        median = labeled[column].median()
        labeled[column] = labeled[column].fillna(median).fillna(0.0)
    labeled["date"] = pd.to_datetime(labeled["date"], errors="coerce")
    labeled["date"] = labeled["date"].fillna(pd.Timestamp.now().normalize())
    cycles = _date_cycle_columns(labeled["date"])
    labeled = pd.concat([labeled, cycles], axis=1)
    labeled["demand_log"] = np.log1p(labeled["demand"])
    return labeled.reset_index(drop=True)


def _one_hot(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    encoded = pd.get_dummies(
        frame[CATEGORICAL_FEATURES],
        columns=CATEGORICAL_FEATURES,
        drop_first=False,
        dtype=float,
    )
    return encoded, list(encoded.columns)


def _features(dataset: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    encoded, encoded_columns = _one_hot(dataset)
    features = pd.concat([dataset[NUMERIC_FEATURES], encoded], axis=1)
    return features, NUMERIC_FEATURES + encoded_columns


def _model_params() -> dict[str, Any]:
    return {
        "objective": "regression",
        "metric": "mae",
        "n_estimators": 300,
        "learning_rate": 0.05,
        "num_leaves": 15,
        "max_depth": 4,
        "min_child_samples": 20,
        "reg_alpha": 0.1,
        "reg_lambda": 0.5,
        "random_state": RANDOM_SEED,
        "n_jobs": 1,
        "verbose": -1,
    }


def _fold_metrics(
    model: lgb.LGBMRegressor,
    x_test: pd.DataFrame,
    y_test_log: pd.Series,
    y_test: pd.Series,
    threshold: float,
) -> dict[str, float]:
    pred_log = model.predict(x_test)
    pred = np.maximum(np.expm1(pred_log), 0.0)
    actual = y_test.to_numpy(dtype=float)
    mask = actual > 0
    if mask.sum() == 0:
        return {"mape": float("nan"), "mae": float("nan"), "f1": float("nan")}
    mape = float(np.mean(np.abs((actual[mask] - pred[mask]) / actual[mask])) * 100)
    mae = float(np.mean(np.abs(actual[mask] - pred[mask])))
    pred_high = pred >= threshold
    actual_high = actual >= threshold
    tp = float(np.sum(pred_high & actual_high))
    fp = float(np.sum(pred_high & ~actual_high))
    fn = float(np.sum(~pred_high & actual_high))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"mape": round(mape, 3), "mae": round(mae, 3), "f1": round(f1, 3)}


def _combo_stats(dataset: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (category, market), group in dataset.groupby(["category", "market"], observed=True):
        provider = group["provider"].mode().iloc[0] if not group["provider"].mode().empty else "shopee"
        rows.append(
            {
                "category": str(category),
                "market": str(market),
                "price": float(group["price"].median()),
                "rating": float(group["rating"].median()),
                "reviews": float(group["reviews"].median()),
                "provider": str(provider),
            }
        )
    return rows


def _save_status(payload: dict[str, Any]) -> None:
    REAL_PROXY_STATUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    REAL_PROXY_STATUS_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_proxy_cache() -> None:
    global _PROXY_CACHE
    _PROXY_CACHE = None


def train_real_proxy_model() -> dict[str, Any]:
    """Train and persist the real-demand proxy model, or mark it skipped."""
    global _PROXY_CACHE
    dataset = build_proxy_dataset()
    generated_at = datetime.now(timezone.utc).isoformat()
    if len(dataset) < MIN_LABELED_ROWS or dataset.groupby(["category", "market"], observed=True).ngroups < 2:
        # 样本不足时必须清掉旧产物：否则 load_real_proxy_model() 会因为
        # model + meta 仍在而加载上一版（旧品类口径）训练出的模型。
        stale: list[str] = []
        for path in (REAL_PROXY_MODEL, REAL_PROXY_META):
            if path.exists():
                path.unlink()
                stale.append(str(path))
        payload = {
            "generated_at": generated_at,
            "status": "skipped",
            "reason": f"labeled_rows={len(dataset)} below minimum {MIN_LABELED_ROWS} or combos < 2",
            "cleaned_stale_artifacts": stale,
        }
        _save_status(payload)
        _PROXY_CACHE = None
        return payload

    x_all, feature_columns = _features(dataset)
    y_all_log = dataset["demand_log"]
    y_all = dataset["demand"]
    groups = (dataset["category"].astype(str) + "|" + dataset["market"].astype(str)).to_numpy()
    n_splits = min(5, dataset.groupby(["category", "market"], observed=True).ngroups)
    splitter = GroupKFold(n_splits=n_splits)
    fold_scores: list[dict[str, float]] = []
    for train_index, test_index in splitter.split(x_all, y_all, groups=groups):
        x_train, x_test = x_all.iloc[train_index], x_all.iloc[test_index]
        y_train_log, y_test_log = y_all_log.iloc[train_index], y_all_log.iloc[test_index]
        y_test = y_all.iloc[test_index]
        model = lgb.LGBMRegressor(**_model_params())
        model.fit(x_train, y_train_log)
        threshold = float(np.quantile(np.expm1(y_train_log), 0.75))
        fold_scores.append(_fold_metrics(model, x_test, y_test_log, y_test, threshold))

    final_model = lgb.LGBMRegressor(**_model_params())
    final_model.fit(x_all, y_all_log)
    stats = _combo_stats(dataset)
    score_values: list[float] = []
    combo_scores: list[dict[str, Any]] = []
    for combo in stats:
        row = _combo_feature_row(combo["category"], combo["market"], stats, feature_columns)
        pred_log = float(final_model.predict(pd.DataFrame([row])[feature_columns])[0])
        combo_scores.append({**combo, "predicted_demand": round(float(np.expm1(pred_log)), 2)})
        score_values.append(pred_log)
    metrics = {
        "mean_mape": round(float(np.nanmean([s["mape"] for s in fold_scores])), 3),
        "mean_mae": round(float(np.nanmean([s["mae"] for s in fold_scores])), 3),
        "mean_f1": round(float(np.nanmean([s["f1"] for s in fold_scores])), 3),
        "folds": len(fold_scores),
    }
    payload = {
        "generated_at": generated_at,
        "status": "ok",
        "labeled_rows": int(len(dataset)),
        "combos": len(stats),
        "feature_columns": feature_columns,
        "combo_stats": stats,
        "combo_scores": combo_scores,
        "score_bounds": {
            "min_log": float(np.min(score_values)) if score_values else 0.0,
            "max_log": float(np.max(score_values)) if score_values else 0.0,
        },
        "metrics": metrics,
    }
    REAL_PROXY_MODEL.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, REAL_PROXY_MODEL)
    REAL_PROXY_META.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _save_status(payload)
    _PROXY_CACHE = (final_model, payload)
    return payload


def _global_combo_row(stats: list[dict[str, Any]]) -> dict[str, Any]:
    price = float(np.median([item["price"] for item in stats])) if stats else 0.0
    rating = float(np.median([item["rating"] for item in stats])) if stats else 0.0
    reviews = float(np.median([item["reviews"] for item in stats])) if stats else 0.0
    providers = [item["provider"] for item in stats]
    provider = max(set(providers), key=providers.count) if providers else "shopee"
    return {"price": price, "rating": rating, "reviews": reviews, "provider": provider}


def _combo_feature_row(
    category: str,
    market: str,
    stats: list[dict[str, Any]],
    feature_columns: list[str],
) -> dict[str, Any]:
    combo = next(
        (
            item
            for item in stats
            if str(item.get("category")) == category and str(item.get("market")) == market
        ),
        None,
    )
    if combo is None:
        combo = _global_combo_row(stats)
        combo["category"] = category
        combo["market"] = market
    now = pd.Timestamp.now()
    row: dict[str, Any] = {
        "price": float(combo.get("price") or 0.0),
        "rating": float(combo.get("rating") or 0.0),
        "reviews": float(combo.get("reviews") or 0.0),
        "month_sin": float(np.sin(2 * np.pi * now.month / 12)),
        "month_cos": float(np.cos(2 * np.pi * now.month / 12)),
        "week_sin": float(np.sin(2 * np.pi * now.isocalendar().week / 52)),
        "week_cos": float(np.cos(2 * np.pi * now.isocalendar().week / 52)),
        "provider": str(combo.get("provider") or "shopee"),
        "category": str(category),
        "market": str(market),
    }
    encoded = pd.get_dummies(
        pd.DataFrame([row])[CATEGORICAL_FEATURES],
        columns=CATEGORICAL_FEATURES,
        drop_first=False,
        dtype=float,
    )
    for column in feature_columns:
        if column not in row and column not in encoded.columns:
            row[column] = 0.0
    for column in encoded.columns:
        row[column] = float(encoded.iloc[0][column])
    return row


def load_real_proxy_model() -> tuple[Any, dict[str, Any]] | None:
    global _PROXY_CACHE
    if _PROXY_CACHE is None:
        if not (REAL_PROXY_MODEL.exists() and REAL_PROXY_META.exists()):
            return None
        try:
            meta = json.loads(REAL_PROXY_META.read_text(encoding="utf-8"))
            if meta.get("status") != "ok":
                return None
            model = joblib.load(REAL_PROXY_MODEL)
            _PROXY_CACHE = (model, meta)
        except (OSError, json.JSONDecodeError, ValueError):
            return None
    return _PROXY_CACHE


def proxy_evidence_score(category: str, market: str) -> dict[str, Any]:
    """Return a 0-100 real-demand evidence score for one category/market."""
    loaded = load_real_proxy_model()
    if loaded is None:
        return {
            "available": False,
            "score": None,
            "level": "neutral",
            "note": "真实销量代理模型不可用，按缺失处理。",
            "missing": True,
        }
    model, meta = loaded
    feature_columns = meta.get("feature_columns") or []
    row = _combo_feature_row(category, market, meta.get("combo_stats") or [], feature_columns)
    pred_log = float(model.predict(pd.DataFrame([row])[feature_columns])[0])
    bounds = meta.get("score_bounds") or {"min_log": 0.0, "max_log": 0.0}
    spread = float(bounds["max_log"]) - float(bounds["min_log"])
    if spread > 0:
        score = float(np.clip(50.0 + 40.0 * (pred_log - float(bounds["min_log"])) / spread, 0.0, 100.0))
    else:
        score = 50.0
    level = "high" if score >= 70 else ("medium" if score >= 50 else "low")
    return {
        "available": True,
        "score": round(score, 1),
        "predicted_demand": round(float(np.expm1(pred_log)), 2),
        "level": level,
        "note": f"真实销量代理预测 {round(float(np.expm1(pred_log)), 2)}，证据分 {round(score, 1)}。",
        "missing": False,
    }


__all__ = [
    "build_proxy_dataset",
    "clear_proxy_cache",
    "load_real_proxy_model",
    "proxy_evidence_score",
    "train_real_proxy_model",
]
