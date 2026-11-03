"""业务指标与滚动回测模块测试（任务清单 A-2）。

覆盖：四类业务指标计算（小型构造数据）、metrics.json 落盘结构、
滚动回测脚本 --smoke 可运行、冷启动评估不崩溃且固定种子可复现。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analysis.backtest import (
    make_windows,
    run_cold_start,
    run_rolling_backtest,
)
from src.analysis.business_metrics import (
    build_business_metrics,
    compute_calibration,
    compute_direction_hit_rate,
    compute_topn_posterior_return,
    estimate_inventory_loss,
    load_business_metrics,
    save_business_metrics,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def tiny_history() -> pd.DataFrame:
    """3 品类 × 2 市场 × 30 周小型历史数据（确定性：固定种子噪声 + 季节 + 趋势）。"""
    rng = np.random.default_rng(7)
    rows: list[dict] = []
    dates = pd.date_range("2025-01-01", periods=30, freq="W")
    for category in ("cn_latiao", "cn_changsha_mifen", "cn_laoganma"):
        for market in ("us", "sea"):
            for i, date in enumerate(dates):
                season = 1.0 + 0.3 * np.sin(2 * np.pi * i / 52)
                trend = 1.0 + 0.01 * i
                noise = 1.0 + rng.normal(0, 0.05)
                rows.append(
                    {
                        "date": date,
                        "category": category,
                        "market": market,
                        "sales_volume": round(80.0 * season * trend * noise, 2),
                    }
                )
    return pd.DataFrame(rows)


def _tiny_recommendations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"rank": 1, "category": "cn_latiao", "market": "us", "forecast_growth": 10.0},
            {"rank": 2, "category": "cn_changsha_mifen", "market": "sea", "forecast_growth": 5.0},
        ]
    )


# ---------------------------------------------------------------------------
# 1) 预测校准度
# ---------------------------------------------------------------------------
def test_compute_calibration_basic() -> None:
    actual = np.array([100.0, 110.0, 90.0, 120.0, 95.0])
    pred = np.array([102.0, 108.0, 92.0, 118.0, 98.0])
    result = compute_calibration(actual, pred, pred - 5.0, pred + 5.0)
    assert result["status"] == "ok"
    assert result["n"] == 5
    # bias = mean(pred-actual)/mean(actual)*100 = (0.6/103)*100
    assert abs(result["bias_pct"] - 0.5825) < 0.01
    assert result["mape_pct"] > 0
    assert result["interval_coverage_pct"] == 100.0
    assert result["coverage_gap_pct"] == 20.0
    assert result["spearman_rho"] is not None
    assert set(result["error_quantiles_pct"]) == {"p10", "p25", "p50", "p75", "p90"}


def test_compute_calibration_missing() -> None:
    result = compute_calibration([], [])
    assert result["status"] == "missing"
    assert result["n"] == 0


def test_compute_calibration_no_intervals() -> None:
    result = compute_calibration([10.0, 11.0], [10.5, 11.5])
    assert result["status"] == "ok"
    assert "interval_coverage_pct" not in result


# ---------------------------------------------------------------------------
# 2) 方向命中率
# ---------------------------------------------------------------------------
def test_direction_hit_rate_all_hits() -> None:
    actual = [100.0, 110.0, 120.0, 100.0, 100.0, 110.0]
    pred = [105.0, 115.0, 115.0, 105.0, 100.0, 105.0]
    result = compute_direction_hit_rate(actual, pred)
    assert result["status"] == "ok"
    assert result["n"] == 4  # t=4 环比持平不计入
    assert result["n_flat"] == 1
    assert result["hit_rate_pct"] == 100.0


def test_direction_hit_rate_partial() -> None:
    actual = [100.0, 110.0, 120.0, 100.0, 100.0, 110.0]
    pred = [105.0, 95.0, 115.0, 105.0, 100.0, 105.0]
    result = compute_direction_hit_rate(actual, pred)
    # t=1 误判（实际涨、预测跌），其余 3 个有效点命中 → 75%
    assert result["hit_rate_pct"] == 75.0
    assert result["up_hit_rate_pct"] is not None
    assert result["down_hit_rate_pct"] == 100.0


def test_direction_hit_rate_too_short() -> None:
    assert compute_direction_hit_rate([100.0], [100.0])["status"] == "missing"


# ---------------------------------------------------------------------------
# 3) Top-N 后验收益
# ---------------------------------------------------------------------------
def test_topn_posterior_return(tiny_history: pd.DataFrame) -> None:
    rec = _tiny_recommendations()
    result = compute_topn_posterior_return(
        tiny_history, rec, top_n=2, margin_pct=0.3, horizon_days=90
    )
    assert result["status"] == "ok"
    assert result["n"] == 2
    assert len(result["rows"]) == 2
    for row in result["rows"]:
        assert row["posterior_return_90d_usd"] > 0
        assert row["realized_growth_pct"] is not None
        assert row["price_usd"] > 0
    assert result["aggregates"]["total_posterior_return_90d_usd"] > 0
    assert "benchmark" in result and "topn_uplift_pct" in result["benchmark"]
    # 毛利 30%：posterior = 周均销量 × 价格 × 0.3 × 90/7
    home = result["rows"][0]
    assert abs(home["margin_pct"] - 30.0) < 1e-6
    assert home["price_usd"] == 4.0  # config CATEGORY_CATALOG["cn_latiao"]["price"]


def test_topn_posterior_return_empty() -> None:
    result = compute_topn_posterior_return(pd.DataFrame(), pd.DataFrame())
    assert result["status"] == "missing"


# ---------------------------------------------------------------------------
# 4) 库存损失估算
# ---------------------------------------------------------------------------
def test_inventory_loss_formula() -> None:
    rows = [
        {"category": "cn_latiao", "market": "us", "mae": 10.0},
        {"category": "cn_changsha_mifen", "market": "sea", "mae": 5.0},
    ]
    result = estimate_inventory_loss(
        rows, margin_pct=0.3, holding_rate_yearly=0.25, overstock_share=0.5
    )
    assert result["status"] == "ok"
    assert result["n"] == 2
    home = result["rows"][0]
    # 高估 5 件 × $4 × 周持有成本率(0.25/52)
    assert abs(home["overstock_loss_weekly_usd"] - 5 * 4 * 0.25 / 52) < 0.01
    # 缺货 5 件 × $4 × 30% 毛利
    assert abs(home["stockout_loss_weekly_usd"] - 5 * 4 * 0.30) < 0.01
    assert result["aggregates"]["total_loss_annual_usd"] > 0


def test_inventory_loss_direction_and_share() -> None:
    rows = [{"category": "cn_latiao", "market": "us", "mae": 10.0}]
    result = estimate_inventory_loss(
        rows,
        margin_pct=0.3,
        overstock_share={("cn_latiao", "us"): 1.0},
        direction_stats={("cn_latiao", "us"): {"direction_error_rate_pct": 50.0, "mean_abs_change": 4.0}},
    )
    home = result["rows"][0]
    assert home["overstock_loss_weekly_usd"] > 0
    assert home["stockout_loss_weekly_usd"] == 0.0  # 高估占比 100% → 无缺货
    # 方向误判：0.5 × 4 × $4 × 30% = $2.4/周
    assert abs(home["direction_loss_weekly_usd"] - 2.4) < 0.01


# ---------------------------------------------------------------------------
# 装配 + metrics.json 落盘结构
# ---------------------------------------------------------------------------
def test_build_and_save_metrics(tmp_path: Path, tiny_history: pd.DataFrame) -> None:
    rec = _tiny_recommendations()
    metrics = {
        "baseline": [
            {"category": "cn_latiao", "market": "us", "model": "prophet_baseline", "mape": 5.0, "mae": 10.0}
        ]
    }
    rng = np.random.default_rng(0)
    dates = pd.date_range("2025-01-01", periods=8, freq="W")
    actual = np.concatenate([rng.normal(100, 5, 8), rng.normal(80, 4, 8)])
    pred = actual * 0.95
    preds = pd.DataFrame(
        {
            "date": np.concatenate([dates.values, dates.values]),
            "category": ["cn_latiao"] * 8 + ["cn_changsha_mifen"] * 8,
            "market": ["us"] * 8 + ["sea"] * 8,
            "actual": actual,
            "pred": pred,
            "pred_lower": pred * 0.9,
            "pred_upper": pred * 1.1,
        }
    )
    payload = build_business_metrics(
        tiny_history, rec, metrics, predictions=preds, margin_pct=0.3, seed=42
    )
    assert payload["generated_at"]
    assert payload["口径"] and len(payload["口径"]) == 4
    assert payload["calibration"]["status"] == "ok"
    assert payload["direction_hit_rate"]["status"] == "ok"
    assert payload["topn_posterior_return"]["status"] == "ok"
    assert payload["inventory_loss"]["status"] == "ok"
    assert payload["scope"]["seed"] == 42

    path = tmp_path / "metrics.json"
    path.write_text(json.dumps({"baseline": [{"keep": True}]}), encoding="utf-8")
    merged = save_business_metrics(payload, path)
    assert "baseline" in merged and "business_metrics" in merged  # 既有键保留
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["business_metrics"]["calibration"]["n"] > 0
    assert load_business_metrics(path)["generated_at"] == payload["generated_at"]

    # 缺预测数据 → 校准/方向占位不报错，其余指标仍计算
    payload2 = build_business_metrics(tiny_history, rec, metrics, predictions=None, margin_pct=0.3)
    assert payload2["calibration"]["status"] == "missing"
    assert payload2["direction_hit_rate"]["status"] == "missing"
    assert payload2["topn_posterior_return"]["status"] == "ok"
    assert payload2["inventory_loss"]["status"] == "ok"


def test_load_business_metrics_missing(tmp_path: Path) -> None:
    assert load_business_metrics(tmp_path / "nope.json") == {}


def test_margin_for_returns_fraction() -> None:
    from src.analysis.business_metrics import margin_for

    margin = margin_for("cn_longjing", "us")
    assert 0.0 < margin <= 1.0  # 项目成本模型返回百分点，必须转小数
    assert abs(margin_for("cn_longjing", "us") - margin) < 1e-9  # 缓存一致


# ---------------------------------------------------------------------------
# 滚动回测
# ---------------------------------------------------------------------------
def test_make_windows() -> None:
    windows = make_windows(total_weeks=30, train_weeks=10, test_weeks=4, step_weeks=5, max_rounds=None)
    assert windows[0] == (0, 10, 10, 14)
    assert all(ts + 10 + 4 <= 30 for ts, _, _, _ in windows)
    assert len(windows) == 4
    capped = make_windows(total_weeks=30, train_weeks=10, test_weeks=4, step_weeks=5, max_rounds=2)
    assert len(capped) == 2


def test_rolling_backtest_smoke(tiny_history: pd.DataFrame) -> None:
    results, predictions = run_rolling_backtest(
        tiny_history,
        model="seasonal_naive",
        train_weeks=10,
        test_weeks=4,
        step_weeks=5,
        max_rounds=None,
        combos=None,
        workers=2,
        seed=42,
    )
    assert not results.empty
    assert set(results["model"].unique()) == {"seasonal_naive"}
    assert results["mape"].notna().all()
    assert results["mae"].notna().all()
    assert {"round", "window_start", "window_end", "category", "market", "direction_hit_rate_pct"} <= set(results.columns)
    assert not predictions.empty
    assert {"actual", "pred", "pred_lower", "pred_upper"} <= set(predictions.columns)
    assert predictions["pred"].notna().all()


def test_rolling_backtest_seed_reproducible(tiny_history: pd.DataFrame) -> None:
    r1, p1 = run_rolling_backtest(
        tiny_history, combos=2, train_weeks=10, test_weeks=4, step_weeks=5, max_rounds=None, seed=42
    )
    r2, p2 = run_rolling_backtest(
        tiny_history, combos=2, train_weeks=10, test_weeks=4, step_weeks=5, max_rounds=None, seed=42
    )
    assert sorted(r1[["category", "market"]].drop_duplicates().values.tolist()) == sorted(
        r2[["category", "market"]].drop_duplicates().values.tolist()
    )
    pd.testing.assert_frame_equal(
        r1.sort_values(["round", "category", "market"]).reset_index(drop=True),
        r2.sort_values(["round", "category", "market"]).reset_index(drop=True),
    )


# ---------------------------------------------------------------------------
# 冷启动评估
# ---------------------------------------------------------------------------
def test_cold_start_no_crash(tiny_history: pd.DataFrame) -> None:
    result = run_cold_start(tiny_history, test_weeks=4, categories=["cn_latiao", "cn_changsha_mifen"], seed=42)
    assert not result.empty
    assert {"cold_seasonal_mape", "full_train_mape", "degradation_mape_pct"} <= set(result.columns)
    assert result["full_train_mape"].notna().all()
    assert result["cold_seasonal_mape"].notna().all()
    assert result["n"].min() > 0


def test_cold_start_seed_reproducible(tiny_history: pd.DataFrame) -> None:
    r1 = run_cold_start(tiny_history, test_weeks=4, categories=2, seed=42)
    r2 = run_cold_start(tiny_history, test_weeks=4, categories=2, seed=42)
    assert sorted(r1["category"].unique()) == sorted(r2["category"].unique())


# ---------------------------------------------------------------------------
# 脚本 --smoke 可运行（子进程）
# ---------------------------------------------------------------------------
def _write_small_data(path: Path) -> None:
    rng = np.random.default_rng(3)
    rows: list[dict] = []
    dates = pd.date_range("2025-01-01", periods=30, freq="W")
    for category in ("cn_latiao", "cn_changsha_mifen"):
        for market in ("us", "sea"):
            for i, date in enumerate(dates):
                rows.append(
                    {
                        "date": date,
                        "category": category,
                        "market": market,
                        "sales_volume": round(70.0 + 10 * np.sin(i / 5) + rng.normal(0, 2), 2),
                    }
                )
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def test_script_smoke(tmp_path: Path) -> None:
    data_path = tmp_path / "data.csv"
    rec_path = tmp_path / "rec.csv"
    metrics_path = tmp_path / "metrics.json"
    out_dir = tmp_path / "out"
    _write_small_data(data_path)
    pd.DataFrame(
        [{"rank": 1, "category": "cn_latiao", "market": "us", "forecast_growth": 8.0}]
    ).to_csv(rec_path, index=False, encoding="utf-8-sig")
    metrics_path.write_text(
        json.dumps({"baseline": [{"category": "cn_latiao", "market": "us", "mape": 4.0, "mae": 3.0}]}),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "rolling_backtest.py"),
            "--smoke",
            "--data",
            str(data_path),
            "--recommendations",
            str(rec_path),
            "--out-dir",
            str(out_dir),
            "--metrics-json",
            str(metrics_path),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (out_dir / "backtest_summary.md").exists()
    assert (out_dir / "cold_start.md").exists()
    assert (out_dir / "rolling_results.csv").exists()
    assert (out_dir / "rolling_predictions.csv").exists()
    assert (out_dir / "cold_start_results.csv").exists()
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert "business_metrics" in data
    assert "baseline" in data  # 既有键保留
    assert data["business_metrics"]["calibration"]["status"] == "ok"
