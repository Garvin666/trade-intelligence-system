"""F2 看板服务端聚合测试：/api/dashboard-data 只下发图表序列，不再全量下发。"""

from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEST_DB = PROJECT_ROOT / "tmp" / "test_dashboard_agg_state.db"
_TEST_DB.unlink(missing_ok=True)
os.environ["BACKEND_STATE_DB"] = str(_TEST_DB)

from fastapi.testclient import TestClient  # noqa: E402

from src.api.app import app  # noqa: E402
from src.api.services import forecast_frame, history_frame  # noqa: E402

client = TestClient(app)

# 数据规模动态取自真实 CSV（每周一行 / 未来 N 天 / 模型数），避免与固定规模强耦合。
HISTORY_DATES = int(history_frame()["date"].nunique())
FORECAST_DAYS = int(forecast_frame()["date"].nunique())
FORECAST_MODELS = int(forecast_frame()["model"].nunique())


def _payload_size_mb(payload: dict) -> float:
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) / 1024 / 1024


def test_dashboard_data_no_filters_is_aggregated_small() -> None:
    """无筛选时只下发聚合图表序列：history ≤ 104 行、forecast ≤ 180 行、payload < 1MB。"""
    resp = client.get("/api/dashboard-data")
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["history"]) <= HISTORY_DATES
    assert len(payload["forecast"]) <= FORECAST_DAYS * FORECAST_MODELS
    assert _payload_size_mb(payload) < 1.0


def test_dashboard_data_aggregation_keeps_chart_fields() -> None:
    """聚合序列保留前端图表所需字段（行结构兼容）。"""
    resp = client.get("/api/dashboard-data")
    payload = resp.json()
    assert payload["history"], "聚合后 history 不应为空"
    first = payload["history"][0]
    for key in ("date", "sales_volume", "search_index", "export_value"):
        assert key in first, f"history 行缺少图表字段 {key}"
    fc_first = payload["forecast"][0]
    for key in ("date", "model", "yhat", "yhat_lower", "yhat_upper"):
        assert key in fc_first, f"forecast 行缺少字段 {key}"
    # 聚合序列按 date 唯一（无重复日期）
    dates = [row["date"] for row in payload["history"]]
    assert len(dates) == len(set(dates)), "聚合后的 history 不应有重复日期"
    # 保留非图表小数据块
    assert payload["recommendations"]
    assert payload["metrics"]["baseline"]


def test_dashboard_data_category_only_aggregated() -> None:
    """仅 category 筛选（跨市场）时同样按日期聚合。"""
    resp = client.get("/api/dashboard-data", params={"category": "cn_changsha_mifen"})
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["history"]) <= HISTORY_DATES
    assert len(payload["forecast"]) <= FORECAST_DAYS * FORECAST_MODELS


def test_dashboard_data_market_only_aggregated() -> None:
    """仅 market 筛选（跨品类）时同样按日期聚合。"""
    resp = client.get("/api/dashboard-data", params={"market": "us"})
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["history"]) <= HISTORY_DATES
    assert len(payload["forecast"]) <= FORECAST_DAYS * FORECAST_MODELS


def test_dashboard_data_both_filters_returns_real_series() -> None:
    """category+market 双筛选返回真实序列（不聚合），行数与历史周期一致。"""
    resp = client.get("/api/dashboard-data", params={"category": "cn_changsha_mifen", "market": "us"})
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["history"]) == HISTORY_DATES
    assert all(row["category"] == "cn_changsha_mifen" and row["market"] == "us" for row in payload["history"])
    # 双筛无 model：所有模型 × 预测天数
    assert len(payload["forecast"]) == FORECAST_DAYS * FORECAST_MODELS
    assert {row["model"] for row in payload["forecast"]} == set(forecast_frame()["model"].unique())


def test_dashboard_data_model_filter_applies_to_aggregated_forecast() -> None:
    """model 筛选在聚合模式下恒生效：forecast 只含该模型。"""
    resp = client.get(
        "/api/dashboard-data", params={"model": "lightgbm_advanced"}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["forecast"]) <= FORECAST_DAYS
    assert all(row["model"] == "lightgbm_advanced" for row in payload["forecast"])


def test_dashboard_data_limit_param() -> None:
    """limit 参数作用于聚合序列。"""
    resp = client.get("/api/dashboard-data", params={"limit": 52})
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["history"]) == 52
    assert len(payload["forecast"]) == 52 * FORECAST_MODELS


def test_dashboard_data_meta_mode_unchanged() -> None:
    """meta=1 轻量元信息行为不变（不拉取序列）。"""
    resp = client.get("/api/dashboard-data", params={"meta": "1"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert "size_mb" in payload
    assert "history" not in payload


def test_dashboard_data_with_model_filter_regression() -> None:
    """既有断言保持：双筛选 + model 时 forecast 全行匹配 model。"""
    resp = client.get(
        "/api/dashboard-data",
        params={"category": "cn_changsha_mifen", "market": "us", "model": "lightgbm_advanced"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["history"]
    assert payload["forecast"]
    assert all(item["model"] == "lightgbm_advanced" for item in payload["forecast"])
