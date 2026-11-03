"""业务指标：预测校准度、方向命中率、Top-N 后验收益、库存损失估算。

口径总览（全部公式与假设随指标落盘到 ``models/metrics.json`` 顶层键
``business_metrics``，报告按该口径展示）：

1. 预测校准度（calibration）：预测 vs 实际的系统性偏差与分位校准。
   - bias_pct = mean(pred - actual) / mean(actual) * 100（预测相对实际的系统性偏离）
   - mpe_pct  = mean((pred - actual) / actual * 100)（符号化平均百分比误差）
   - mape_pct = mean(|pred - actual| / actual * 100)
   - error_quantiles_pct：误差百分比 (pred-actual)/actual 的 P10/P25/P50/P75/P90
   - spearman_rho：预测与实际的秩相关（排序单调一致性）
   - interval_coverage_pct：实际值落在 [pred_lower, pred_upper] 的比例
     （名义 80% 区间；prediction 数据带区间时才有，否则记 missing）

2. 方向命中率（direction hit rate）：预测环比方向（涨/跌）与实际的命中比例。
   - dir_pred[t]  = sign(pred[t] - actual[t-1])，dir_actual[t] = sign(actual[t] - actual[t-1])
   - 环比持平（dir_actual == 0）的点方向无定义，不计入分母，单独记 n_flat

3. Top-N 后验收益（Top-N posterior return）：按 recommendations.csv 的 Top-N 组合，
   用实际销量 × 品类价格 × 综合毛利率（项目贸易成本模型口径，回退默认 30%）
   估算的 90 天后验毛利贡献；并给出实际实现的环比增长与全组合基准对比。
   - weekly_contribution_usd = mean(近 12 周实际销量) × price × margin
   - posterior_return_90d_usd = weekly_contribution_usd × 90 / 7

4. 库存损失估算（inventory loss）：由预测误差（MAE/方向错误）推算的备货成本损失。
   - 高估（pred > actual）→ 库存积压：mae × 高估占比 × 价格 × 周持有成本率
     （年化持有成本率 25% ÷ 52）
   - 低估（pred < actual）→ 缺货损失：mae × (1 - 高估占比) × 价格 × 毛利率
   - 方向误判（环比方向预测错误）→ 趋势增量机会损失：
     误判率 × mean(|actual[t]-actual[t-1]|) × 价格 × 毛利率
   - 每周三项加总 × 52 为年化损失；高估占比可由预测数据实测，缺省 0.5
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as ss

from src.config import (
    CATEGORY_CATALOG,
    MARKET_FACTOR,
    METRICS_JSON,
    RANDOM_SEED,
    TARGET_COL,
)

# 默认经营假设（与报告口径一致；可用参数覆盖）
DEFAULT_MARGIN_PCT = 0.30  # 综合毛利率（回退值；优先用项目贸易成本模型逐组合测算）
DEFAULT_HOLDING_RATE_YEARLY = 0.25  # 年化库存持有成本率（资金占用 + 仓储 + 损耗）
DEFAULT_TOP_N = 10  # Top-N 后验收益的 N
DEFAULT_HORIZON_DAYS = 90  # 预测期（天），与 FORECAST_HORIZON 一致
RECENT_WEEKS = 12  # 后验窗口：近 12 周实际销量
NOMINAL_INTERVAL_PCT = 80.0  # 名义预测区间覆盖率（80%）

_MARGIN_CACHE: dict[tuple[str, str], float] = {}


def price_for(category: str) -> float:
    """品类基准价格（美元），来自 src/config.py CATEGORY_CATALOG。"""
    return float(CATEGORY_CATALOG.get(category, {}).get("price", 30.0))


def margin_for(category: str, market: str) -> float:
    """组合综合毛利率（0~1 小数）：优先项目贸易成本模型（LandedCostCalculator 返回百分点，÷100），
    失败回退 DEFAULT_MARGIN_PCT。"""
    key = (category, market)
    if key in _MARGIN_CACHE:
        return _MARGIN_CACHE[key]
    value = DEFAULT_MARGIN_PCT
    try:
        from src.trade.preflight import _default_margin

        # trade 模块 margin_pct 语义为百分点（如 38.72 表示 38.72%），此处统一转小数
        value = float(_default_margin(category, market)) / 100.0
    except Exception:  # noqa: BLE001 - 成本模型失败不阻断指标计算
        value = DEFAULT_MARGIN_PCT
    _MARGIN_CACHE[key] = value
    return value


def _as_float_array(series: Any) -> np.ndarray:
    return pd.to_numeric(pd.Series(series), errors="coerce").to_numpy(dtype=float)


# ---------------------------------------------------------------------------
# 1) 预测校准度
# ---------------------------------------------------------------------------
def compute_calibration(
    actual: Any,
    pred: Any,
    pred_lower: Any | None = None,
    pred_upper: Any | None = None,
) -> dict[str, Any]:
    """预测 vs 实际的系统性偏差与分位校准。缺数据时返回 status=missing。"""
    a = _as_float_array(actual)
    p = _as_float_array(pred)
    mask = ~np.isnan(a) & ~np.isnan(p)
    a, p = a[mask], p[mask]
    n = int(len(a))
    if n == 0:
        return {"status": "missing", "n": 0}
    denom = np.where(a == 0, np.nan, a)
    err_pct = (p - a) / denom * 100.0
    finite = err_pct[~np.isnan(err_pct)]
    result: dict[str, Any] = {
        "status": "ok",
        "n": n,
        "bias_pct": round(float(np.mean(p - a) / np.mean(a) * 100.0), 3)
        if np.mean(a) != 0
        else float("nan"),
        "mpe_pct": round(float(np.mean(finite)), 3) if len(finite) else float("nan"),
        "mape_pct": round(float(np.mean(np.abs(finite))), 3) if len(finite) else float("nan"),
        "error_quantiles_pct": {
            f"p{q}": round(float(np.percentile(finite, q)), 3) for q in (10, 25, 50, 75, 90)
        }
        if len(finite)
        else {},
    }
    if len(a) >= 3:
        rho, _ = ss.spearmanr(a, p)
        result["spearman_rho"] = round(float(rho), 3) if not np.isnan(rho) else None
    else:
        result["spearman_rho"] = None
    if pred_lower is not None and pred_upper is not None:
        lo = _as_float_array(pred_lower)[mask]
        up = _as_float_array(pred_upper)[mask]
        coverage = float(np.mean((a >= lo) & (a <= up)) * 100.0)
        result["interval_coverage_pct"] = round(coverage, 2)
        result["interval_nominal_pct"] = NOMINAL_INTERVAL_PCT
        result["coverage_gap_pct"] = round(coverage - NOMINAL_INTERVAL_PCT, 2)
    return result


# ---------------------------------------------------------------------------
# 2) 方向命中率
# ---------------------------------------------------------------------------
def compute_direction_hit_rate(actual: Any, pred: Any) -> dict[str, Any]:
    """预测环比方向（涨/跌）命中率。平盘点（环比持平）不计入分母，单独记 n_flat。"""
    a = _as_float_array(actual)
    p = _as_float_array(pred)
    mask = ~np.isnan(a) & ~np.isnan(p)
    a, p = a[mask], p[mask]
    if len(a) < 2:
        return {"status": "missing", "n": 0, "n_flat": 0}
    lag, cur, pred_cur = a[:-1], a[1:], p[1:]
    dir_actual = np.sign(cur - lag)
    dir_pred = np.sign(pred_cur - lag)
    n_flat = int(np.count_nonzero(dir_actual == 0))
    valid = dir_actual != 0
    n = int(np.count_nonzero(valid))
    if n == 0:
        return {"status": "missing", "n": 0, "n_flat": n_flat}
    hits = dir_pred[valid] == dir_actual[valid]
    dir_valid = dir_actual[valid]
    up = dir_valid > 0
    down = dir_valid < 0
    up_hit = float(np.mean(hits[up])) if up.sum() else float("nan")
    down_hit = float(np.mean(hits[down])) if down.sum() else float("nan")
    return {
        "status": "ok",
        "n": n,
        "n_flat": n_flat,
        "hit_rate_pct": round(float(np.mean(hits) * 100.0), 2),
        "up_hit_rate_pct": round(up_hit * 100.0, 2) if not np.isnan(up_hit) else None,
        "down_hit_rate_pct": round(down_hit * 100.0, 2) if not np.isnan(down_hit) else None,
    }


# ---------------------------------------------------------------------------
# 3) Top-N 后验收益
# ---------------------------------------------------------------------------
def _combo_series(
    history: pd.DataFrame, category: str, market: str
) -> pd.DataFrame:
    sub = history[(history["category"] == category) & (history["market"] == market)]
    return sub.sort_values("date")


def _realized_growth_pct(sales: np.ndarray) -> float:
    """近窗口实际环比增长：后一半均值相对前一半均值的百分比变化。"""
    if len(sales) < 4:
        return float("nan")
    half = len(sales) // 2
    first, second = sales[:half], sales[half:]
    base = float(np.mean(first))
    if abs(base) < 1e-9:
        return float("nan")
    return float((np.mean(second) - base) / base * 100.0)


def compute_topn_posterior_return(
    history: pd.DataFrame,
    recommendations: pd.DataFrame,
    top_n: int = DEFAULT_TOP_N,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    recent_weeks: int = RECENT_WEEKS,
    prices: dict[str, float] | None = None,
    margins: dict[tuple[str, str], float] | None = None,
    margin_pct: float | None = None,
) -> dict[str, Any]:
    """Top-N 推荐组合的后验收益（实际销量 × 价格 × 毛利率折算 90 天毛利贡献）。"""
    if recommendations is None or recommendations.empty:
        return {"status": "missing", "n": 0}
    top = recommendations.sort_values("rank").head(top_n).copy()
    rows: list[dict[str, Any]] = []
    for _, item in top.iterrows():
        category = str(item["category"])
        market = str(item["market"])
        series = _combo_series(history, category, market)
        recent = series.tail(recent_weeks)[TARGET_COL].to_numpy(dtype=float)
        avg_sales = float(np.mean(recent)) if len(recent) else float("nan")
        price = (prices or {}).get(category, price_for(category))
        if margin_pct is not None:
            margin = float(margin_pct)
        elif margins is not None:
            margin = float(margins.get((category, market), margin_for(category, market)))
        else:
            margin = margin_for(category, market)
        weekly_contribution = avg_sales * price * margin if not np.isnan(avg_sales) else float("nan")
        try:
            forecast_growth = float(item.get("forecast_growth") or float("nan"))
        except (TypeError, ValueError):
            forecast_growth = float("nan")
        rows.append(
            {
                "rank": int(item["rank"]),
                "category": category,
                "market": market,
                "actual_sales_avg_12w": round(avg_sales, 2),
                "realized_growth_pct": round(_realized_growth_pct(recent), 2),
                "forecast_growth_pct": round(forecast_growth, 2) if not np.isnan(forecast_growth) else None,
                "price_usd": round(price, 2),
                "margin_pct": round(margin * 100.0, 1),
                "weekly_contribution_usd": round(weekly_contribution, 2),
                "posterior_return_90d_usd": round(weekly_contribution * horizon_days / 7.0, 2),
            }
        )
    valid_rows = [r for r in rows if not np.isnan(r["posterior_return_90d_usd"])]
    if not valid_rows:
        return {"status": "missing", "n": 0, "rows": rows}
    returns = np.array([r["posterior_return_90d_usd"] for r in valid_rows])
    growth = np.array([r["realized_growth_pct"] for r in valid_rows])
    growth = growth[~np.isnan(growth)]

    # 全组合基准（所有组合的后验收益与实现增长）
    bench_rows: list[float] = []
    bench_growth: list[float] = []
    for (category, market), sub in history.groupby(["category", "market"], observed=True):
        recent = sub.sort_values("date").tail(recent_weeks)[TARGET_COL].to_numpy(dtype=float)
        if len(recent) < 4:
            continue
        price = (prices or {}).get(category, price_for(category))
        if margin_pct is not None:
            margin = float(margin_pct)
        elif margins is not None:
            margin = float(margins.get((category, market), margin_for(category, market)))
        else:
            margin = margin_for(category, market)
        bench_rows.append(float(np.mean(recent)) * price * margin * horizon_days / 7.0)
        g = _realized_growth_pct(recent)
        if not np.isnan(g):
            bench_growth.append(g)
    bench_avg = float(np.mean(bench_rows)) if bench_rows else float("nan")
    bench_growth_avg = float(np.mean(bench_growth)) if bench_growth else float("nan")
    uplift = (float(np.mean(returns)) - bench_avg) / bench_avg * 100.0 if bench_avg else float("nan")
    confirmation = float(np.mean(growth > 0) * 100.0) if len(growth) else float("nan")

    fg = np.array([r["forecast_growth_pct"] for r in valid_rows if r["forecast_growth_pct"] is not None])
    rg = np.array(
        [r["realized_growth_pct"] for r in valid_rows if r["forecast_growth_pct"] is not None]
    )
    forecast_realized_rho = None
    if len(fg) >= 3 and len(rg) == len(fg):
        rho, _ = ss.spearmanr(fg, rg)
        if not np.isnan(rho):
            forecast_realized_rho = round(float(rho), 3)

    return {
        "status": "ok",
        "n": len(valid_rows),
        "top_n": top_n,
        "horizon_days": horizon_days,
        "rows": rows,
        "aggregates": {
            "total_posterior_return_90d_usd": round(float(np.sum(returns)), 2),
            "avg_posterior_return_90d_usd": round(float(np.mean(returns)), 2),
            "median_posterior_return_90d_usd": round(float(np.median(returns)), 2),
            "avg_realized_growth_pct": round(float(np.mean(growth)), 2) if len(growth) else None,
            "confirmation_rate_pct": round(confirmation, 1) if not np.isnan(confirmation) else None,
        },
        "benchmark": {
            "avg_posterior_return_all_combos_usd": round(bench_avg, 2) if not np.isnan(bench_avg) else None,
            "avg_realized_growth_all_combos_pct": round(bench_growth_avg, 2) if not np.isnan(bench_growth_avg) else None,
            "topn_uplift_pct": round(uplift, 1) if not np.isnan(uplift) else None,
        },
        "forecast_realized_spearman_rho": forecast_realized_rho,
    }


# ---------------------------------------------------------------------------
# 4) 库存损失估算
# ---------------------------------------------------------------------------
def _per_combo_overstock_share(predictions: pd.DataFrame | None) -> dict[tuple[str, str], float]:
    """预测数据可测的高估占比：pred > actual 的点占比，缺省 0.5。"""
    out: dict[tuple[str, str], float] = {}
    if predictions is None or predictions.empty:
        return out
    for (category, market), sub in predictions.groupby(["category", "market"], observed=True):
        a = _as_float_array(sub["actual"])
        p = _as_float_array(sub["pred"])
        mask = ~np.isnan(a) & ~np.isnan(p)
        if mask.sum() == 0:
            continue
        out[(category, market)] = float(np.mean(p[mask] > a[mask]))
    return out


def _per_combo_direction_stats(
    predictions: pd.DataFrame | None,
) -> dict[tuple[str, str], dict[str, float]]:
    """预测数据可测的每组合方向误判率与周均实际波动幅度。"""
    out: dict[tuple[str, str], dict[str, float]] = {}
    if predictions is None or predictions.empty:
        return out
    for (category, market), sub in predictions.groupby(["category", "market"], observed=True):
        a = _as_float_array(sub["actual"])
        p = _as_float_array(sub["pred"])
        mask = ~np.isnan(a) & ~np.isnan(p)
        a, p = a[mask], p[mask]
        if len(a) < 3:
            continue
        lag, cur, pred_cur = a[:-1], a[1:], p[1:]
        dir_actual = np.sign(cur - lag)
        dir_pred = np.sign(pred_cur - lag)
        valid = dir_actual != 0
        if valid.sum() == 0:
            continue
        err_rate = float(np.mean(dir_pred[valid] != dir_actual[valid]))
        mean_abs_change = float(np.mean(np.abs(cur - lag)))
        out[(category, market)] = {
            "direction_error_rate_pct": round(err_rate * 100.0, 2),
            "mean_abs_change": round(mean_abs_change, 3),
        }
    return out


def estimate_inventory_loss(
    mae_rows: list[dict[str, Any]],
    prices: dict[str, float] | None = None,
    margins: dict[tuple[str, str], float] | None = None,
    margin_pct: float | None = None,
    holding_rate_yearly: float = DEFAULT_HOLDING_RATE_YEARLY,
    overstock_share: float | dict[tuple[str, str], float] = 0.5,
    direction_stats: dict[tuple[str, str], dict[str, float]] | None = None,
) -> dict[str, Any]:
    """由 MAE（周均绝对误差）与方向误判率推算的备货成本损失（美元/周，×52 年化）。

    - overstock_share 可为全局浮点或按 (category, market) 的字典（预测实测高估占比）。
    - direction_stats：每组合 {"direction_error_rate_pct", "mean_abs_change"}。
    """
    if not mae_rows:
        return {"status": "missing", "n": 0}
    weekly_holding_rate = holding_rate_yearly / 52.0
    rows: list[dict[str, Any]] = []
    for item in mae_rows:
        category = str(item.get("category", ""))
        market = str(item.get("market", ""))
        try:
            mae = float(item.get("mae"))
        except (TypeError, ValueError):
            continue
        if np.isnan(mae):
            continue
        key = (category, market)
        price = (prices or {}).get(category, price_for(category))
        if margin_pct is not None:
            margin = float(margin_pct)
        elif margins is not None:
            margin = float(margins.get(key, margin_for(category, market)))
        else:
            margin = margin_for(category, market)
        share = (
            overstock_share.get(key, 0.5)
            if isinstance(overstock_share, dict)
            else float(overstock_share)
        )
        over_units = mae * share
        short_units = mae * (1.0 - share)
        over_loss = over_units * price * weekly_holding_rate
        short_loss = short_units * price * margin
        dir_loss = 0.0
        if direction_stats and key in direction_stats:
            der = direction_stats[key]
            dir_loss = (
                der["direction_error_rate_pct"] / 100.0
                * der["mean_abs_change"] * price * margin
            )
        total_weekly = over_loss + short_loss + dir_loss
        rows.append(
            {
                "category": category,
                "market": market,
                "mae_units_per_week": round(mae, 3),
                "overstock_share": round(share, 3),
                "price_usd": round(price, 2),
                "margin_pct": round(margin * 100.0, 1),
                "overstock_loss_weekly_usd": round(over_loss, 2),
                "stockout_loss_weekly_usd": round(short_loss, 2),
                "direction_loss_weekly_usd": round(dir_loss, 2),
                "total_loss_weekly_usd": round(total_weekly, 2),
                "total_loss_annual_usd": round(total_weekly * 52.0, 2),
            }
        )
    if not rows:
        return {"status": "missing", "n": 0}
    weekly = np.array([r["total_loss_weekly_usd"] for r in rows])
    return {
        "status": "ok",
        "n": len(rows),
        "holding_rate_yearly": holding_rate_yearly,
        "aggregates": {
            "total_loss_annual_usd": round(float(np.sum(weekly) * 52.0), 2),
            "avg_loss_weekly_per_combo_usd": round(float(np.mean(weekly)), 2),
            "median_loss_weekly_per_combo_usd": round(float(np.median(weekly)), 2),
            "avg_loss_annual_per_combo_usd": round(float(np.mean(weekly) * 52.0), 2),
        },
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# 装配与落盘
# ---------------------------------------------------------------------------
def _calibration_and_direction_from_predictions(
    predictions: pd.DataFrame | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if predictions is None or predictions.empty:
        return (
            {"status": "missing", "n": 0},
            {"status": "missing", "n": 0, "n_flat": 0},
        )
    return (
        compute_calibration(
            predictions["actual"],
            predictions["pred"],
            predictions.get("pred_lower"),
            predictions.get("pred_upper"),
        ),
        compute_direction_hit_rate(predictions["actual"], predictions["pred"]),
    )


def build_business_metrics(
    history: pd.DataFrame,
    recommendations: pd.DataFrame,
    metrics: dict[str, Any],
    predictions: pd.DataFrame | None = None,
    top_n: int = DEFAULT_TOP_N,
    margin_pct: float | None = None,
    holding_rate_yearly: float = DEFAULT_HOLDING_RATE_YEARLY,
    overstock_share: float = 0.5,
    prices: dict[str, float] | None = None,
    seed: int = RANDOM_SEED,
    predictions_label: str = "rolling_backtest",
) -> dict[str, Any]:
    """装配 business_metrics 载荷：口径 + 四类指标（含数值与样本数）。

    ``predictions`` 为回测/留出预测明细（列：category/market/date/actual/pred/
    [pred_lower/pred_upper]），用于校准度、方向命中率与库存损失的实测占比；
    缺省时校准度与方向命中率返回 status=missing（报告显示占位）。
    """
    calibration, direction = _calibration_and_direction_from_predictions(predictions)
    topn = compute_topn_posterior_return(
        history, recommendations, top_n=top_n, prices=prices, margin_pct=margin_pct
    )
    overstock_by_combo = _per_combo_overstock_share(predictions)
    if isinstance(overstock_share, float) and overstock_by_combo:
        effective_share: float | dict[tuple[str, str], float] = overstock_by_combo
    else:
        effective_share = overstock_share
    inventory = estimate_inventory_loss(
        metrics.get("baseline", []) or [],
        prices=prices,
        margin_pct=margin_pct,
        holding_rate_yearly=holding_rate_yearly,
        overstock_share=effective_share,
        direction_stats=_per_combo_direction_stats(predictions),
    )

    scope = {
        "categories": int(history["category"].nunique()) if not history.empty else 0,
        "markets": int(history["market"].nunique()) if not history.empty else 0,
        "combos": int(history.groupby(["category", "market"], observed=True).ngroups)
        if not history.empty
        else 0,
        "prediction_points": int(len(predictions)) if predictions is not None else 0,
        "predictions_source": predictions_label,
        "seed": seed,
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": scope,
        "口径": [
            {
                "指标": "预测校准度",
                "公式": (
                    "bias_pct=mean(pred-actual)/mean(actual)×100；mpe_pct=mean((pred-actual)/actual×100)；"
                    "mape_pct=mean(|pred-actual|/actual×100)；error_quantiles_pct 为误差百分比分位；"
                    "interval_coverage_pct=mean(actual∈[pred_lower,pred_upper])×100（名义 80% 区间）"
                ),
                "假设": "实际值取历史清洗数据；区间仅预测带区间时计算",
            },
            {
                "指标": "方向命中率",
                "公式": (
                    "dir_pred[t]=sign(pred[t]-actual[t-1])，dir_actual[t]=sign(actual[t]-actual[t-1])；"
                    "hit_rate_pct=mean(dir_pred==dir_actual)×100"
                ),
                "假设": "环比持平（dir_actual==0）不计入分母，单独记 n_flat",
            },
            {
                "指标": "Top-N 后验收益",
                "公式": (
                    "weekly_contribution=mean(近12周实际销量)×价格×毛利率；"
                    "posterior_return_90d=weekly_contribution×90/7；"
                    "realized_growth_pct=后6周均值相对前6周均值的环比"
                ),
                "假设": f"价格取 src/config.py 品类基准价格；毛利率优先项目贸易成本模型，回退 {DEFAULT_MARGIN_PCT:.0%}；"
                        f"Top-N={top_n}，后验窗口 12 周",
            },
            {
                "指标": "库存损失估算",
                "公式": (
                    "高估损失=MAE×高估占比×价格×周持有成本率；缺货损失=MAE×(1-高估占比)×价格×毛利率；"
                    "方向误判损失=误判率×mean(|Δactual|)×价格×毛利率；周损失×52 年化"
                ),
                "假设": (
                    f"MAE 取 metrics.json baseline 每组合周均误差；年化持有成本率 {holding_rate_yearly:.0%}（÷52 周）；"
                    "高估占比由预测数据实测（pred>actual 占比），缺省 0.5"
                ),
            },
        ],
        "calibration": calibration,
        "direction_hit_rate": direction,
        "topn_posterior_return": topn,
        "inventory_loss": inventory,
    }


def save_business_metrics(payload: dict[str, Any], path: Path | str | None = None) -> dict[str, Any]:
    """把 business_metrics 写入 metrics.json 顶层新键，保留既有键（baseline 等）。"""
    target = Path(path) if path else METRICS_JSON
    if target.exists():
        data = json.loads(target.read_text(encoding="utf-8"))
    else:
        data = {}
    data["business_metrics"] = payload
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load_business_metrics(path: Path | str | None = None) -> dict[str, Any]:
    """读取 metrics.json 的 business_metrics，缺失返回空 dict（报告显示占位）。"""
    target = Path(path) if path else METRICS_JSON
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):  # noqa: S110
        return {}
    return data.get("business_metrics") or {}


__all__ = [
    "DEFAULT_HOLDING_RATE_YEARLY",
    "DEFAULT_MARGIN_PCT",
    "DEFAULT_TOP_N",
    "RECENT_WEEKS",
    "build_business_metrics",
    "compute_calibration",
    "compute_direction_hit_rate",
    "compute_topn_posterior_return",
    "estimate_inventory_loss",
    "load_business_metrics",
    "margin_for",
    "price_for",
    "save_business_metrics",
]
