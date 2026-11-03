"""Tune Prophet and LightGBM hyperparameters with Optuna.

Validation uses the last 12 weeks inside the training window; the final 12-week
holdout (the same split used by the dashboard metrics) is never touched here.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from prophet import Prophet

from src.config import (
    PROCESSED_CSV,
    PROPHET_REGRESSORS,
    RANDOM_SEED,
    TARGET_COL,
    TEST_WEEKS,
)
from src.features.builder import FEATURE_COLS, build_features
from src.models.metrics import compute_metrics

TUNE_COMBOS = [
    ("cn_latiao", "us"),
    ("cn_longjing", "eu"),
    ("cn_laoganma", "sea"),
    ("cn_frozen_dumplings", "jp"),
    ("cn_beef_jerky", "ca"),
    ("cn_changsha_mifen", "uk"),
    ("cn_tanghulu", "kr"),
    ("cn_self_heating_hotpot", "de"),
    ("cn_ningxia_goji", "au"),
    ("cn_mooncake", "mx"),
    ("cn_baijiu_mini", "vn"),
    ("cn_goji_honey", "ru"),
]


def _group_features(df: pd.DataFrame, category: str, market: str) -> pd.DataFrame:
    group = df[(df["category"] == category) & (df["market"] == market)]
    group = group.sort_values("date").reset_index(drop=True)
    features = build_features(group)
    features = features.dropna(subset=FEATURE_COLS + [TARGET_COL]).reset_index(drop=True)
    return features


def _train_val_split(features: pd.DataFrame, test_weeks: int = TEST_WEEKS):
    val_end = len(features) - test_weeks
    train_end = val_end - test_weeks
    if train_end < 12 or val_end <= train_end:
        return None, None
    return features.iloc[:train_end], features.iloc[train_end:val_end]


def _transform(y: pd.Series, mode: str) -> np.ndarray:
    arr = y.to_numpy(dtype=float)
    if mode == "log1p":
        return np.log1p(arr)
    return arr


def _inverse(y: np.ndarray, mode: str) -> np.ndarray:
    if mode == "log1p":
        return np.expm1(y)
    return y


def _mean_mape(scores: list[float]) -> float:
    valid = [s for s in scores if s == s]
    return float(np.mean(valid)) if valid else float("inf")


def score_lightgbm_params(
    features_by_combo: dict[tuple[str, str], pd.DataFrame],
    params: dict,
    transform: str,
) -> float:
    scores: list[float] = []
    for features in features_by_combo.values():
        train, val = _train_val_split(features)
        if train is None or val is None or len(val) == 0:
            continue
        model_params = {
            **params,
            "objective": "regression",
            "metric": "mae",
            "verbose": -1,
            "random_state": RANDOM_SEED,
            "n_jobs": 1,
        }
        model = lgb.LGBMRegressor(**model_params)
        model.fit(
            train[FEATURE_COLS],
            _transform(train[TARGET_COL], transform),
            eval_set=[(val[FEATURE_COLS], _transform(val[TARGET_COL], transform))],
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        iters = getattr(model, "best_iteration_", None) or model.n_estimators
        pred_t = model.predict(val[FEATURE_COLS], num_iteration=iters)
        pred = _inverse(pred_t, transform)
        metrics = compute_metrics(val[TARGET_COL], pd.Series(pred, index=val.index))
        scores.append(metrics["mape"])
    return _mean_mape(scores)


def _lgbm_objective(
    trial: optuna.Trial,
    features_by_combo: dict[tuple[str, str], pd.DataFrame],
) -> float:
    transform = trial.suggest_categorical("target_transform", ["raw", "log1p"])
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 300, 1200, step=100),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 8, 64),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "bagging_freq": trial.suggest_int("bagging_freq", 1, 5),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 60),
        "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 2.0),
    }
    return score_lightgbm_params(features_by_combo, params, transform)


def score_prophet_params(df: pd.DataFrame, combos: list[tuple[str, str]], params: dict) -> float:
    scores: list[float] = []
    for category, market in combos:
        group = df[(df["category"] == category) & (df["market"] == market)]
        group = group.sort_values("date").reset_index(drop=True)
        val_end = len(group) - TEST_WEEKS
        train_end = val_end - TEST_WEEKS
        if train_end < 8 or val_end <= train_end:
            continue
        train = group.iloc[:train_end]
        val = group.iloc[train_end:val_end]
        prophet_df = pd.DataFrame(
            {
                "ds": pd.to_datetime(train["date"]),
                "y": np.log(np.maximum(train[TARGET_COL].to_numpy(dtype=float), 1e-6)),
            }
        )
        for name in PROPHET_REGRESSORS:
            prophet_df[name] = train[name].to_numpy(dtype=float)
        model = Prophet(**params)
        for name in PROPHET_REGRESSORS:
            model.add_regressor(name)
        model.fit(prophet_df)
        future = pd.DataFrame({"ds": pd.to_datetime(val["date"])})
        for name in PROPHET_REGRESSORS:
            future[name] = val[name].to_numpy(dtype=float)
        fc = model.predict(future)
        pred = np.exp(fc["yhat"].to_numpy(dtype=float))
        metrics = compute_metrics(val[TARGET_COL], pd.Series(pred, index=val.index))
        scores.append(metrics["mape"])
    return _mean_mape(scores)


def _prophet_objective(trial: optuna.Trial, df: pd.DataFrame, combos: list[tuple[str, str]]) -> float:
    params = {
        "seasonality_mode": trial.suggest_categorical(
            "seasonality_mode", ["additive", "multiplicative"]
        ),
        "changepoint_prior_scale": trial.suggest_float(
            "changepoint_prior_scale", 0.001, 0.2, log=True
        ),
        "seasonality_prior_scale": trial.suggest_float(
            "seasonality_prior_scale", 0.1, 15.0, log=True
        ),
        "yearly_seasonality": trial.suggest_int("yearly_seasonality", 10, 30),
        "weekly_seasonality": trial.suggest_int("weekly_seasonality", 5, 15),
        "changepoint_range": trial.suggest_float("changepoint_range", 0.6, 0.95),
        "daily_seasonality": False,
    }
    return score_prophet_params(df, combos, params)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tune prediction model hyperparameters")
    parser.add_argument("--trials-lgbm", type=int, default=40)
    parser.add_argument("--trials-prophet", type=int, default=30)
    parser.add_argument("--quick", action="store_true", help="smoke test with fewer combos/trials")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "output" / "optimization")
    args = parser.parse_args(argv)

    combos = TUNE_COMBOS[:2] if args.quick else TUNE_COMBOS
    trials_lgbm = 3 if args.quick else args.trials_lgbm
    trials_prophet = 3 if args.quick else args.trials_prophet

    df = pd.read_csv(PROCESSED_CSV, parse_dates=["date"])
    features_by_combo = {combo: _group_features(df, *combo) for combo in combos}
    print(f"Tuning on {len(combos)} combos: {', '.join(f'{c} x {m}' for c, m in combos)}")

    lgbm_study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED),
    )
    lgbm_study.optimize(
        lambda trial: _lgbm_objective(trial, features_by_combo),
        n_trials=trials_lgbm,
        show_progress_bar=True,
    )

    prophet_study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED),
    )
    prophet_study.optimize(
        lambda trial: _prophet_objective(trial, df, combos),
        n_trials=trials_prophet,
        show_progress_bar=True,
    )

    lgbm_best = dict(lgbm_study.best_params)
    transform = lgbm_best.pop("target_transform", "raw")
    prophet_best = dict(prophet_study.best_params)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "combos": [f"{c}|{m}" for c, m in combos],
        "validation": "last 12 weeks inside training window; final 12-week holdout untouched",
        "lightgbm": {
            "best_validation_mape": round(lgbm_study.best_value, 4),
            "target_transform": transform,
            "params": lgbm_best,
        },
        "prophet": {
            "best_validation_mape": round(prophet_study.best_value, 4),
            "params": prophet_best,
        },
    }
    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / f"tuned_params_{datetime.now():%Y%m%d_%H%M%S}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nLightGBM best validation MAPE: {lgbm_study.best_value:.4f}")
    print(f"  target_transform = {transform!r}")
    for key, value in lgbm_best.items():
        print(f"  {key} = {value}")
    print(f"\nProphet best validation MAPE: {prophet_study.best_value:.4f}")
    for key, value in prophet_best.items():
        print(f"  {key} = {value}")
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
