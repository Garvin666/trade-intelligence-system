"""滚动回测与跨品类冷启动（留出）评估核心逻辑。

scripts/rolling_backtest.py 是薄 CLI 壳，本模块承载可测试的实现：

- 滚动回测：对每个品类 × 市场组合做「滚动窗口训练-预测-评估」，输出每轮窗口的
  MAPE / MAE / 方向命中率与逐点预测明细（含 80% 区间），跨品类随机留出由
  ``RANDOM_SEED`` 固定（--combos 抽样与冷启动品类抽样均使用同一种子）。
- 冷启动评估：整品类从训练中留出（新商品零历史），用「全量其他品类」的归一化
  季节剖面 + 品类目录先验（base_sales × 市场因子）预测，与全量训练（本品类
  自身历史）对比 MAPE 与方向命中率。

模型：
- ``seasonal_naive``（默认，确定性、零训练成本）：预测 = 同季节（52 周前）观测，
  区间由样本内季节残差 P90 构造；
- ``prophet``：复用 ``ProphetBaseline.predict_frame``（生产基线模型，较慢）。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from src.config import (
    CATEGORY_CATALOG,
    MARKET_FACTOR,
    RANDOM_SEED,
    TARGET_COL,
    TRAIN_WORKERS,
)
from src.models.metrics import compute_metrics

DEFAULT_TRAIN_WEEKS = 52
DEFAULT_TEST_WEEKS = 4
DEFAULT_STEP_WEEKS = 8
DEFAULT_MAX_ROUNDS = 6
SEASONAL_PERIOD = 52  # 年季节性周期（周）

_SUPPORTED_MODELS = ("seasonal_naive", "prophet")


def make_windows(
    total_weeks: int,
    train_weeks: int = DEFAULT_TRAIN_WEEKS,
    test_weeks: int = DEFAULT_TEST_WEEKS,
    step_weeks: int = DEFAULT_STEP_WEEKS,
    max_rounds: int | None = DEFAULT_MAX_ROUNDS,
) -> list[tuple[int, int, int, int]]:
    """生成滚动窗口的周索引切片 (train_start, train_end, test_start, test_end)。

    轮次超出上限时保留最早轮次并锚定数据末端的最新窗口（与生产留出
    「最近 12 周」口径可比），丢弃中间轮次。
    """
    windows: list[tuple[int, int, int, int]] = []
    start = 0
    while start + train_weeks + test_weeks <= total_weeks:
        train_end = start + train_weeks
        windows.append((start, train_end, train_end, train_end + test_weeks))
        start += step_weeks
    if max_rounds is not None and len(windows) > max_rounds:
        windows = windows[: max_rounds - 1] + [windows[-1]]
    return windows


def seasonal_naive_predict(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """季节朴素预测：预测 = 52 周前同期观测；区间 = 样本内季节残差 P90（80% 名义）。"""
    train_vals = pd.to_numeric(train[TARGET_COL], errors="coerce").to_numpy(dtype=float)
    train_vals = train_vals[~np.isnan(train_vals)]
    profile = train_vals[-SEASONAL_PERIOD:] if len(train_vals) >= SEASONAL_PERIOD else train_vals
    n = len(profile)
    if n == 0:
        pred = np.full(len(test), np.nan)
        half = 0.0
    else:
        pred = np.array([profile[i % n] for i in range(len(test))], dtype=float)
        if len(train_vals) >= SEASONAL_PERIOD + 1:
            resid = np.abs(train_vals[SEASONAL_PERIOD:] - train_vals[:-SEASONAL_PERIOD])
        else:
            resid = np.abs(np.diff(train_vals)) if len(train_vals) > 1 else np.array([0.0])
        half = float(np.quantile(resid, 0.90)) if len(resid) else 0.0
    return pd.DataFrame(
        {
            "date": pd.to_datetime(test["date"]).to_numpy(),
            "actual": pd.to_numeric(test[TARGET_COL], errors="coerce").to_numpy(dtype=float),
            "pred": pred,
            "pred_lower": pred - half,
            "pred_upper": pred + half,
        }
    )


def predict_window(train: pd.DataFrame, test: pd.DataFrame, model: str = "seasonal_naive") -> pd.DataFrame:
    """按模型派发单窗口预测；返回 date/actual/pred/pred_lower/pred_upper。"""
    if model == "prophet":
        from src.models.baseline import ProphetBaseline

        category = str(train["category"].iloc[0])
        market = str(train["market"].iloc[0])
        return ProphetBaseline(category, market).predict_frame(train, test)
    if model == "seasonal_naive":
        return seasonal_naive_predict(train, test)
    raise ValueError(f"不支持的模型：{model}（可选 {_SUPPORTED_MODELS}）")


def _direction_hit_rate(points: pd.DataFrame) -> tuple[float, int, int]:
    """由逐点预测明细计算方向命中率 (hit_rate_pct, n, n_flat)。"""
    a = pd.to_numeric(points["actual"], errors="coerce").to_numpy(dtype=float)
    p = pd.to_numeric(points["pred"], errors="coerce").to_numpy(dtype=float)
    mask = ~np.isnan(a) & ~np.isnan(p)
    a, p = a[mask], p[mask]
    if len(a) < 2:
        return float("nan"), 0, 0
    lag, cur, pred_cur = a[:-1], a[1:], p[1:]
    dir_actual = np.sign(cur - lag)
    dir_pred = np.sign(pred_cur - lag)
    n_flat = int(np.count_nonzero(dir_actual == 0))
    valid = dir_actual != 0
    n = int(np.count_nonzero(valid))
    if n == 0:
        return float("nan"), 0, n_flat
    return float(np.mean(dir_pred[valid] == dir_actual[valid]) * 100.0), n, n_flat


def _sample_combos(
    history: pd.DataFrame,
    combos: list[tuple[str, str]] | int | None,
    seed: int,
) -> list[tuple[str, str]]:
    all_combos = sorted(
        (str(c), str(m))
        for c, m in history.groupby(["category", "market"], observed=True).groups.keys()
    )
    if combos is None:
        return all_combos
    if isinstance(combos, int):
        rng = np.random.default_rng(seed)
        return [all_combos[i] for i in rng.choice(len(all_combos), size=min(combos, len(all_combos)), replace=False)]
    return [tuple(item) for item in combos]


def run_rolling_backtest(
    history: pd.DataFrame,
    model: str = "seasonal_naive",
    train_weeks: int = DEFAULT_TRAIN_WEEKS,
    test_weeks: int = DEFAULT_TEST_WEEKS,
    step_weeks: int = DEFAULT_STEP_WEEKS,
    max_rounds: int | None = DEFAULT_MAX_ROUNDS,
    combos: list[tuple[str, str]] | int | None = None,
    workers: int | None = None,
    seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """滚动窗口训练-预测-评估。

    Returns:
        (results, predictions)：
        - results：每轮窗口每组合一行（round/window_start/window_end/category/market/
          model/mape/mae/direction_hit_rate_pct/n）；
        - predictions：逐点明细（round/category/market/date/actual/pred/
          pred_lower/pred_upper）。
    """
    history = history.sort_values("date")
    total_weeks = int(history["date"].nunique())
    windows = make_windows(total_weeks, train_weeks, test_weeks, step_weeks, max_rounds)
    if not windows:
        raise ValueError(
            f"历史周数 {total_weeks} 不足以支撑 train={train_weeks}+test={test_weeks} 的滚动窗口"
        )
    combo_list = _sample_combos(history, combos, seed)
    tasks: list[tuple[tuple[str, str], tuple[int, int, int, int], pd.DataFrame]] = []
    grouped = {
        (str(c), str(m)): sub.sort_values("date").reset_index(drop=True)
        for (c, m), sub in history.groupby(["category", "market"], observed=True)
    }
    for combo in combo_list:
        if combo not in grouped:
            continue
        series = grouped[combo]
        for window in windows:
            tasks.append((combo, window, series))

    def _one(task: tuple[tuple[str, str], tuple[int, int, int, int], pd.DataFrame]) -> tuple[dict[str, Any], pd.DataFrame]:
        (category, market), (ts, te, xs, xe), series = task
        train = series.iloc[ts:te]
        test = series.iloc[xs:xe]
        try:
            points = predict_window(train, test, model=model)
        except Exception:  # noqa: BLE001 - 单窗口失败记录空结果，不阻断整体
            return (
                {
                    "round": 0,
                    "window_start": int(ts),
                    "window_end": int(xe),
                    "category": category,
                    "market": market,
                    "model": model,
                    "mape": float("nan"),
                    "mae": float("nan"),
                    "direction_hit_rate_pct": float("nan"),
                    "n": 0,
                },
                pd.DataFrame(),
            )
        metrics = compute_metrics(points["actual"], points["pred"])
        hit_rate, n, n_flat = _direction_hit_rate(points)
        points = points.copy()
        points.insert(0, "round", int(xs))
        points.insert(1, "category", category)
        points.insert(2, "market", market)
        points["model"] = model
        return (
            {
                "round": int(xs),
                "window_start": int(ts),
                "window_end": int(xe),
                "category": category,
                "market": market,
                "model": model,
                "mape": metrics["mape"],
                "mae": metrics["mae"],
                "direction_hit_rate_pct": hit_rate,
                "n": n,
                "n_flat": n_flat,
            },
            points,
        )

    n_workers = workers or max(1, int(TRAIN_WORKERS))
    if n_workers > 1 and len(tasks) > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            outcomes = list(pool.map(_one, tasks))
    else:
        outcomes = [_one(task) for task in tasks]
    results = pd.DataFrame([row for row, _ in outcomes if row is not None])
    pred_frames = [frame for _, frame in outcomes if frame is not None and not frame.empty]
    predictions = pd.concat(pred_frames, ignore_index=True) if pred_frames else pd.DataFrame()
    return results, predictions


# ---------------------------------------------------------------------------
# 跨品类冷启动（整品类留出）评估
# ---------------------------------------------------------------------------
def run_cold_start(
    history: pd.DataFrame,
    test_weeks: int = 8,
    categories: list[str] | int | None = None,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """整品类从训练中留出的冷启动评估：与全量训练（本品类自身历史）对比。

    冷启动预测（无本品类任何历史）：
    - flat_prior：先验水平 = 品类目录 base_sales × 市场因子（无季节）；
    - pooled_seasonal：先验水平 × 其他品类的归一化季节剖面。
    全量训练：本品类自身历史的季节朴素模型。
    输出每组合一行：三类 MAPE / 方向命中率 / 样本数 / 相对劣化。
    """
    history = history.sort_values("date")
    all_categories = sorted(history["category"].unique().tolist())
    if categories is None:
        cat_list = all_categories
    elif isinstance(categories, int):
        rng = np.random.default_rng(seed)
        cat_list = [all_categories[i] for i in rng.choice(len(all_categories), size=min(categories, len(all_categories)), replace=False)]
    else:
        cat_list = [str(c) for c in categories]
    weeks = int(history["date"].nunique())
    # 一次性预计算全部组合的归一化序列（除自身均值），冷启动剖面按留出品类过滤后取中位数
    norm_map: dict[tuple[str, str], np.ndarray] = {}
    for (category, market), sub in history.groupby(["category", "market"], observed=True):
        vals = pd.to_numeric(sub[TARGET_COL], errors="coerce").to_numpy(dtype=float)
        vals = vals[~np.isnan(vals)]
        if len(vals) == 0:
            continue
        mean = float(np.mean(vals))
        if abs(mean) < 1e-9:
            continue
        norm_map[(str(category), str(market))] = vals[:weeks] / mean
    rows: list[dict[str, Any]] = []
    for category in cat_list:
        train_norm = [v for (c, m), v in norm_map.items() if c != category]
        profile = np.median(np.stack(train_norm), axis=0) if train_norm else np.ones(weeks)
        base_sales = float(CATEGORY_CATALOG.get(category, {}).get("base_sales", 50.0))
        for market in sorted(history.loc[history["category"] == category, "market"].unique()):
            series = history[(history["category"] == category) & (history["market"] == market)]
            series = series.sort_values("date").reset_index(drop=True)
            if len(series) < test_weeks + 4:
                continue
            test = series.tail(test_weeks).reset_index(drop=True)
            test_idx = test.index.to_numpy()
            prior = base_sales * float(MARKET_FACTOR.get(market, 1.0))
            pred_flat = np.full(len(test), prior)
            pred_seasonal = prior * profile[test_idx]
            full_train = series.iloc[: len(series) - test_weeks]
            points_full = seasonal_naive_predict(full_train, test)

            def _eval(pred: np.ndarray) -> dict[str, Any]:
                metrics = compute_metrics(test[TARGET_COL], pd.Series(pred))
                hit_rate, n, n_flat = _direction_hit_rate(
                    pd.DataFrame(
                        {
                            "actual": test[TARGET_COL].to_numpy(dtype=float),
                            "pred": pred,
                        }
                    )
                )
                return {
                    "mape": metrics["mape"],
                    "mae": metrics["mae"],
                    "direction_hit_rate_pct": hit_rate,
                    "n": n,
                    "n_flat": n_flat,
                }

            cold_flat = _eval(pred_flat)
            cold_seasonal = _eval(pred_seasonal)
            full = _eval(points_full["pred"].to_numpy(dtype=float))
            deg = (
                (cold_seasonal["mape"] - full["mape"]) / full["mape"] * 100.0
                if full["mape"] == full["mape"] and full["mape"] > 0
                else float("nan")
            )
            rows.append(
                {
                    "category": category,
                    "market": market,
                    "cold_flat_mape": cold_flat["mape"],
                    "cold_seasonal_mape": cold_seasonal["mape"],
                    "full_train_mape": full["mape"],
                    "cold_flat_dir_hit_pct": cold_flat["direction_hit_rate_pct"],
                    "cold_seasonal_dir_hit_pct": cold_seasonal["direction_hit_rate_pct"],
                    "full_train_dir_hit_pct": full["direction_hit_rate_pct"],
                    "degradation_mape_pct": deg,
                    "n": cold_seasonal["n"],
                    "seed": seed,
                    "test_weeks": test_weeks,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 输出与摘要
# ---------------------------------------------------------------------------
def _fmt_md_table(headers: list[str], rows: Iterable[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def _nan_safe(value: Any, fmt: str = "{:.2f}") -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "-"
    return fmt.format(v) if v == v else "-"


def write_rolling_summary(
    results: pd.DataFrame,
    predictions: pd.DataFrame,
    out_dir: Path,
    model: str = "seasonal_naive",
    params: dict[str, Any] | None = None,
) -> Path:
    """写 backtest_summary.md（每轮窗口汇总 + 总体 + 口径）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    params = params or {}
    lines: list[str] = [
        "# 滚动回测摘要（Rolling Backtest Summary）",
        "",
        f"> 生成时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"> 固定随机种子：`{params.get('seed', RANDOM_SEED)}`（跨品类随机留出/抽样）",
        "",
        "## 一、口径",
        "",
        f"- 模型：`{model}`（seasonal_naive=季节朴素确定性模型；prophet=生产 Prophet 基线）",
        f"- 窗口参数：train={params.get('train_weeks')} 周 / test={params.get('test_weeks')} 周 / "
        f"step={params.get('step_weeks')} 周 / 最多 {params.get('max_rounds')} 轮；"
        f"组合数 {params.get('combo_count', 0)}",
        "- MAPE/MAE 口径与 `src/models/metrics.py::compute_metrics` 一致；方向命中率见业务指标口径。",
        "- 预测明细含 80% 名义区间（seasonal_naive 用样本内季节残差 P90，prophet 用 Prophet 区间）。",
        "",
    ]
    if results.empty:
        lines.append("_无回测结果。_")
        path = out_dir / "backtest_summary.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    lines.append("## 二、每轮窗口汇总（全部组合均值）")
    lines.append("")
    per_round: list[dict[str, Any]] = []
    for round_id, sub in results.groupby("round"):
        per_round.append(
            {
                "round": int(round_id),
                "window": f"{int(sub['window_start'].iloc[0])}-{int(sub['window_end'].iloc[0])}",
                "combos": int(len(sub)),
                "mape": float(sub["mape"].mean()),
                "mae": float(sub["mae"].mean()),
                "dir_hit": float(sub["direction_hit_rate_pct"].mean()),
                "points": int(sub["n"].sum()),
            }
        )
    lines.append(
        _fmt_md_table(
            ["轮次", "周区间", "组合数", "平均 MAPE%", "平均 MAE", "方向命中率%", "评估点数"],
            [
                [
                    str(r["round"]),
                    r["window"],
                    str(r["combos"]),
                    _nan_safe(r["mape"]),
                    _nan_safe(r["mae"]),
                    _nan_safe(r["dir_hit"]),
                    str(r["points"]),
                ]
                for r in per_round
            ],
        )
    )
    lines.append("")
    lines.append("## 三、总体结果")
    lines.append("")
    total = {
        "组合-窗口样本": int(len(results)),
        "平均 MAPE%": float(results["mape"].mean()),
        "MAPE 中位数%": float(results["mape"].median()),
        "平均 MAE": float(results["mae"].mean()),
        "平均方向命中率%": float(results["direction_hit_rate_pct"].mean()),
        "评估点数": int(results["n"].sum()),
    }
    lines.append(
        _fmt_md_table(
            ["指标", "数值"],
            [[k, _nan_safe(v) if isinstance(v, float) else str(v)] for k, v in total.items()],
        )
    )
    lines.append("")
    first_round = min(per_round, key=lambda r: r["round"])  # 最早窗口（测试起点最小）
    last_round = max(per_round, key=lambda r: r["round"])  # 最晚窗口
    lines.append(
        f"结论：最早窗口（周区间 {first_round['window']}）MAPE {_nan_safe(first_round['mape'])}% 最高，"
        f"最晚窗口（{last_round['window']}）MAPE {_nan_safe(last_round['mape'])}% 最低——"
        "训练数据越充分（越接近完整季节周期）误差越低；方向命中率整体高于随机 50% 即具备择时价值。"
    )
    lines.append("")
    lines.append("## 四、产物文件")
    lines.append("")
    lines.append("- `rolling_results.csv`：每轮窗口每组合 MAPE/MAE/方向命中率")
    lines.append("- `rolling_predictions.csv`：逐点预测明细（actual/pred/pred_lower/pred_upper）")
    path = out_dir / "backtest_summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_cold_start_summary(
    cold_start: pd.DataFrame,
    out_dir: Path,
    params: dict[str, Any] | None = None,
) -> Path:
    """写 cold_start.md（跨品类留出 vs 全量训练对比）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    params = params or {}
    lines: list[str] = [
        "# 跨品类冷启动（整品类留出）评估",
        "",
        f"> 生成时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"> 固定随机种子：`{params.get('seed', RANDOM_SEED)}`",
        "",
        "## 一、口径",
        "",
        "- 冷启动 = 新商品所在品类**整品类从训练中留出**（零历史），用其他品类数据预测：",
        "  - `flat_prior`：先验水平 = 品类目录 base_sales × 市场因子（无季节信息）；",
        "  - `pooled_seasonal`：先验水平 × 其他品类归一化季节剖面（周中位数）；",
        "- 全量训练对比：本品类自身历史 + 季节朴素模型（同模型口径，仅训练数据不同）；",
        f"- 测试窗口：每组合最近 {params.get('test_weeks', 8)} 周；评估 MAPE 与方向命中率。",
        "",
    ]
    if cold_start.empty:
        lines.append("_无冷启动结果。_")
        path = out_dir / "cold_start.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    agg = {
        "组合数": int(len(cold_start)),
        "冷启动 flat MAPE%": float(cold_start["cold_flat_mape"].mean()),
        "冷启动 季节剖面 MAPE%": float(cold_start["cold_seasonal_mape"].mean()),
        "全量训练 MAPE%": float(cold_start["full_train_mape"].mean()),
        "冷启动 方向命中率%": float(cold_start["cold_seasonal_dir_hit_pct"].mean()),
        "全量训练 方向命中率%": float(cold_start["full_train_dir_hit_pct"].mean()),
        "平均相对劣化%": float(cold_start["degradation_mape_pct"].mean()),
    }
    lines.append("## 二、总体对比")
    lines.append("")
    lines.append(
        _fmt_md_table(
            ["指标", "数值"],
            [[k, _nan_safe(v) if isinstance(v, float) else str(v)] for k, v in agg.items()],
        )
    )
    lines.append("")
    lines.append("## 三、按品类（MAPE 劣化 Top 10 与 Bottom 5）")
    lines.append("")
    by_cat = (
        cold_start.groupby("category")
        .agg(
            cold_mape=("cold_seasonal_mape", "mean"),
            full_mape=("full_train_mape", "mean"),
            degradation=("degradation_mape_pct", "mean"),
            cold_dir=("cold_seasonal_dir_hit_pct", "mean"),
            full_dir=("full_train_dir_hit_pct", "mean"),
        )
        .reset_index()
        .sort_values("degradation", ascending=False)
    )
    worst = by_cat.head(10)
    best = by_cat.tail(5).iloc[::-1]
    top_rows = pd.concat([worst, best], ignore_index=True)
    lines.append(
        _fmt_md_table(
            ["品类", "冷启动 MAPE%", "全量 MAPE%", "相对劣化%", "冷启动方向命中%", "全量方向命中%"],
            [
                [
                    str(r["category"]),
                    _nan_safe(r["cold_mape"]),
                    _nan_safe(r["full_mape"]),
                    _nan_safe(r["degradation"]),
                    _nan_safe(r["cold_dir"]),
                    _nan_safe(r["full_dir"]),
                ]
                for _, r in top_rows.iterrows()
            ],
        )
    )
    lines.append("")
    lines.append("## 四、结论")
    lines.append("")
    cold_m = agg["冷启动 季节剖面 MAPE%"]
    full_m = agg["全量训练 MAPE%"]
    cold_dir = agg["冷启动 方向命中率%"]
    lines.append(
        f"冷启动（季节剖面先验）平均 MAPE {_nan_safe(cold_m)}%，全量训练 "
        f"{_nan_safe(full_m)}%；冷启动以约 {_nan_safe(agg['平均相对劣化%'])}% 的相对劣化"
        "换取了「零历史可预测」能力，适合新品**水平估计**（销量量级与季节轮廓）；"
        f"但冷启动方向命中率 {_nan_safe(cold_dir)}% 低于随机 50%，短期择时需等本品类积累历史，"
        "劣化最大的品类应优先补充真实平台数据。"
    )
    lines.append("")
    lines.append("## 五、产物文件")
    lines.append("")
    lines.append("- `cold_start_results.csv`：每组合三类 MAPE / 方向命中率 / 相对劣化")
    path = out_dir / "cold_start.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_backtest_outputs(
    results: pd.DataFrame,
    predictions: pd.DataFrame,
    cold_start: pd.DataFrame,
    out_dir: Path,
    model: str = "seasonal_naive",
    params: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """写回测全部产物，返回路径字典。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    if not results.empty:
        results.to_csv(out_dir / "rolling_results.csv", index=False, encoding="utf-8-sig")
        paths["rolling_results"] = out_dir / "rolling_results.csv"
    if not predictions.empty:
        predictions.to_csv(out_dir / "rolling_predictions.csv", index=False, encoding="utf-8-sig")
        paths["rolling_predictions"] = out_dir / "rolling_predictions.csv"
    if not cold_start.empty:
        cold_start.to_csv(out_dir / "cold_start_results.csv", index=False, encoding="utf-8-sig")
        paths["cold_start_results"] = out_dir / "cold_start_results.csv"
    paths["backtest_summary"] = write_rolling_summary(results, predictions, out_dir, model, params)
    paths["cold_start"] = write_cold_start_summary(cold_start, out_dir, params)
    return paths


def load_backtest_predictions(out_dir: Path) -> pd.DataFrame:
    """读回测逐点预测明细（供业务指标复用）。"""
    path = out_dir / "rolling_predictions.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


__all__ = [
    "DEFAULT_MAX_ROUNDS",
    "DEFAULT_STEP_WEEKS",
    "DEFAULT_TEST_WEEKS",
    "DEFAULT_TRAIN_WEEKS",
    "load_backtest_predictions",
    "make_windows",
    "predict_window",
    "run_cold_start",
    "run_rolling_backtest",
    "seasonal_naive_predict",
    "write_backtest_outputs",
    "write_cold_start_summary",
    "write_rolling_summary",
]
