"""基于当前数据重建 06B 系统评测指标（output/control/system_eval.json）。

评测口径与 src/models/advanced.py 保持一致：每个品类/市场组合取最近
TEST_WEEKS 周作为隐藏测试集，用 LightGBM 进阶模型重新训练并预测，汇总
MAPE/MAE、覆盖率、方向命中、峰值命中、选品排序与稳健性扰动。

用法：
    python scripts/build_system_eval.py
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    CATEGORIES,
    CONTROL_OUTPUT_DIR,
    MARKETS,
    PROCESSED_CSV,
    REAL_TRAINING_CSV,
    TARGET_COL,
    TEST_WEEKS,
)
from src.features.builder import FEATURE_COLS, build_features  # noqa: E402
from src.models.advanced import LightGBMAdvanced  # noqa: E402


def _mape_mae(actual: np.ndarray, pred: np.ndarray) -> tuple[float, float]:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(pred, dtype=float)
    mask = ~np.isnan(a) & ~np.isnan(p) & (a != 0)
    if mask.sum() == 0:
        return float("nan"), float("nan")
    a = a[mask]
    p = p[mask]
    mape = float(np.mean(np.abs((a - p) / a)) * 100)
    mae = float(np.mean(np.abs(a - p)))
    return mape, mae


def _predict_combo(model: LightGBMAdvanced, group: pd.DataFrame) -> dict | None:
    group = group.sort_values("date").reset_index(drop=True)
    features = build_features(group)
    features = features.dropna(subset=FEATURE_COLS + [TARGET_COL]).reset_index(drop=True)
    split = len(features) - TEST_WEEKS
    if split < 12:
        return None
    train = features.iloc[:split].copy()
    test = features.iloc[split:].copy()
    fitted = model._fit_model(train)
    pred = model._inverse_target(fitted.predict(test[FEATURE_COLS]))
    actual = test[TARGET_COL].to_numpy(dtype=float)
    return {"test": test, "actual": actual, "pred": pred}


def _direction_hit(actual: np.ndarray, pred: np.ndarray) -> float | None:
    if len(actual) < 2:
        return None
    a_diff = np.diff(actual)
    p_diff = np.diff(pred)
    mask = a_diff != 0
    if mask.sum() == 0:
        return None
    return float(np.mean(np.sign(a_diff[mask]) == np.sign(p_diff[mask])))


def _peak_hit(actual: np.ndarray, pred: np.ndarray, window: int = 2) -> bool:
    if len(actual) < 1:
        return False
    a_peak = int(np.nanargmax(actual))
    p_peak = int(np.nanargmax(pred))
    return abs(a_peak - p_peak) <= window


def _ndcg5(pred_top5: list, actual_top5: list) -> float:
    denom = [1.0 / np.log2(i + 2) for i in range(min(5, len(actual_top5)))]
    idcg = sum(denom)
    if idcg <= 0:
        return 0.0
    dcg = sum(
        denom[i] for i, combo in enumerate(pred_top5[:5]) if combo in actual_top5
    )
    return dcg / idcg


def _mrr(pred_top5: list, actual_top5: list) -> float:
    for i, combo in enumerate(pred_top5[:5], start=1):
        if combo in actual_top5:
            return 1.0 / i
    return 0.0


def _perturbed_train(
    features: pd.DataFrame,
    mode: str,
    seed: int = 42,
    fraction: float = 0.05,
) -> pd.DataFrame:
    train = features.copy()
    rng = np.random.default_rng(seed)
    if mode == "missing":
        drop = rng.choice(len(train), size=max(1, int(len(train) * fraction)), replace=False)
        train = train.drop(index=train.index[drop]).reset_index(drop=True)
    elif mode == "outlier":
        idx = rng.choice(len(train), size=max(1, int(len(train) * fraction)), replace=False)
        vals = train[TARGET_COL].to_numpy(dtype=float)
        span = float(np.nanstd(vals) * 5 + 1.0)
        vals[idx] = vals[idx] + np.where(vals[idx] >= 0, span, -span)
        train[TARGET_COL] = vals
    elif mode == "short":
        cut = max(24, int(len(train) * 0.8))
        train = train.iloc[:cut].reset_index(drop=True)
    return train


def main(argv: list[str] | None = None) -> int:
    training_csv = REAL_TRAINING_CSV if REAL_TRAINING_CSV.exists() else PROCESSED_CSV
    df = pd.read_csv(training_csv, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    combos = sorted(
        (cat, mkt)
        for cat in CATEGORIES
        for mkt in MARKETS
        if ((df["category"] == cat) & (df["market"] == mkt)).any()
    )
    total_cells = len(combos) * TEST_WEEKS
    valid_cells = 0
    mape_list: list[float] = []
    mae_list: list[float] = []
    direction_rates: list[float] = []
    correlations: list[float] = []
    peak_hits = 0
    growth_rows: list[dict] = []
    robust_mape: dict[str, list[float]] = {"baseline": [], "missing": [], "outlier": [], "short": []}

    for i, (category, market) in enumerate(combos, start=1):
        if i % 100 == 0:
            print(f"progress: {i}/{len(combos)}")
        group = df[(df["category"] == category) & (df["market"] == market)]
        model = LightGBMAdvanced(category, market)
        result = _predict_combo(model, group)
        if result is None:
            continue
        actual = result["actual"]
        pred = result["pred"]
        valid = ~np.isnan(actual) & ~np.isnan(pred) & (pred >= 0) & (actual != 0)
        valid_cells += int(valid.sum())
        mape, mae = _mape_mae(actual, pred)
        if not np.isnan(mape):
            mape_list.append(mape)
            mae_list.append(mae)
            robust_mape["baseline"].append(mape)
        direction = _direction_hit(actual, pred)
        if direction is not None:
            direction_rates.append(direction)
        if len(actual) >= 2 and np.std(actual) > 0 and np.std(pred) > 0:
            correlations.append(float(np.corrcoef(actual, pred)[0, 1]))
        if _peak_hit(actual, pred):
            peak_hits += 1
        a_growth = float(actual[-1] / actual[0] - 1) if actual[0] else float("nan")
        p_growth = float(pred[-1] / pred[0] - 1) if pred[0] else float("nan")
        growth_rows.append(
            {
                "category": category,
                "market": market,
                "actual_growth": a_growth,
                "pred_growth": p_growth,
            }
        )

        # 稳健性扰动（LightGBM 训练快，仅做一次代表性扰动）
        features = build_features(group)
        features = features.dropna(subset=FEATURE_COLS + [TARGET_COL]).reset_index(drop=True)
        split = len(features) - TEST_WEEKS
        if split >= 12:
            train = features.iloc[:split].copy()
            for mode in ("missing", "outlier", "short"):
                perturbed = _perturbed_train(train, mode)
                fitted = model._fit_model(perturbed)
                test = features.iloc[split:].copy()
                pred_p = model._inverse_target(fitted.predict(test[FEATURE_COLS]))
                mape_p, _ = _mape_mae(test[TARGET_COL].to_numpy(dtype=float), pred_p)
                if not np.isnan(mape_p):
                    robust_mape[mode].append(mape_p)

    actual_rank = sorted(
        (r for r in growth_rows if not np.isnan(r["actual_growth"])),
        key=lambda r: r["actual_growth"],
        reverse=True,
    )
    pred_rank = sorted(
        (r for r in growth_rows if not np.isnan(r["pred_growth"])),
        key=lambda r: r["pred_growth"],
        reverse=True,
    )
    actual_top5 = [(r["category"], r["market"]) for r in actual_rank[:5]]
    actual_top10 = [(r["category"], r["market"]) for r in actual_rank[:10]]
    pred_top5 = [(r["category"], r["market"]) for r in pred_rank[:5]]
    pred_top10 = [(r["category"], r["market"]) for r in pred_rank[:10]]
    hit5 = len(set(actual_top5) & set(pred_top5))
    hit10 = len(set(actual_top10) & set(pred_top10))
    jaccard = hit5 / len(set(actual_top5) | set(pred_top5)) if (set(actual_top5) | set(pred_top5)) else 0.0

    def _rel_change(baseline_vals: list[float], perturbed_vals: list[float]) -> float:
        base = statistics.mean(baseline_vals) if baseline_vals else float("nan")
        pert = statistics.mean(perturbed_vals) if perturbed_vals else float("nan")
        return float((pert - base) / base * 100) if base else float("nan")

    coverage_rate = valid_cells / total_cells if total_cells else 0.0
    direction_rate = statistics.mean(direction_rates) if direction_rates else float("nan")
    peak_rate = peak_hits / len(combos) if combos else 0.0
    macro_mape = statistics.mean(mape_list) if mape_list else float("nan")
    macro_mae = statistics.mean(mae_list) if mae_list else float("nan")

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": {
            "combos": len(combos),
            "test_weeks": TEST_WEEKS,
            "total_cells": total_cells,
        },
        "model": "lightgbm_advanced",
        "macro_mape": round(macro_mape, 4),
        "macro_mae": round(macro_mae, 4),
        "coverage": {
            "valid_cells": valid_cells,
            "total_cells": total_cells,
            "rate": round(coverage_rate, 4),
        },
        "direction": {
            "hit_rate": round(direction_rate, 4),
            "correlation": round(statistics.mean(correlations), 4) if correlations else None,
            "combos": len(direction_rates),
        },
        "peak": {
            "hit_rate": round(peak_rate, 4),
            "hits": peak_hits,
            "combos": len(combos),
        },
        "ranking": {
            "hit5": hit5,
            "hit10": hit10,
            "jaccard": round(jaccard, 4),
            "ndcg5": round(_ndcg5(pred_top5, actual_top5), 4),
            "mrr": round(_mrr(pred_top5, actual_top5), 4),
        },
        "robustness": {
            "missing_pct_change": round(
                _rel_change(robust_mape["baseline"], robust_mape["missing"]), 2
            ),
            "outlier_pct_change": round(
                _rel_change(robust_mape["baseline"], robust_mape["outlier"]), 2
            ),
            "short_window_pct_change": round(
                _rel_change(robust_mape["baseline"], robust_mape["short"]), 2
            ),
        },
        "acceptance": {
            "mape_max": 5.0,
            "coverage_min": 1.0,
            "direction_min": 0.65,
            "peak_window_weeks": 2,
            "ranking_hit5_min": 3,
            "robustness_max_pct": 10.0,
        },
        "pass": {
            "mape": macro_mape <= 5.0,
            "coverage": coverage_rate >= 1.0,
            "direction": direction_rate >= 0.65,
            "peak": peak_rate >= 0.8,
            "ranking": hit5 >= 3,
            "robustness": max(
                _rel_change(robust_mape["baseline"], robust_mape["missing"]),
                _rel_change(robust_mape["baseline"], robust_mape["outlier"]),
                _rel_change(robust_mape["baseline"], robust_mape["short"]),
            )
            <= 10.0,
        },
    }
    CONTROL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = CONTROL_OUTPUT_DIR / "system_eval.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
