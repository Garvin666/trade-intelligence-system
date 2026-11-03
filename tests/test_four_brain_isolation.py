"""本轮修复验收：四脑隔离（B4）、自检轻量（B5）、演示字段对齐（S9）、图表性能。

对应建议报告（后端 14:49 版）行动清单：
- B4：build_charts 预索引性能 + 子进程隔离降级
- B5：/api/dashboard-data?meta=1 轻量检查
- S9：preflight/osint/fx_sensitivity 字段别名
- N1：real_training 口径说明字段
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEST_DB = PROJECT_ROOT / "tmp" / "test_backend_state_isolation.db"
_TEST_DB.unlink(missing_ok=True)
import os  # noqa: E402

os.environ["BACKEND_STATE_DB"] = str(_TEST_DB)

from src.api.app import app  # noqa: E402
from src.four_brain import engine as four_brain  # noqa: E402
from src.trade.cost import LandedCostCalculator, LandedCostInput  # noqa: E402
from src.trade.osint import assess_osint  # noqa: E402
from src.trade.preflight import build_preflight  # noqa: E402

client = TestClient(app)


def _mini_brains() -> dict:
    return {
        "brains": {
            "market": {"score": 80, "confidence": 0.8, "metrics": {}},
            "sentiment": {"score": 70, "confidence": 0.7},
            "supply_chain": {"score": 60, "confidence": 0.6},
            "finance": {"score": 75, "confidence": 0.75},
        }
    }


# ---------------------------------------------------------------------------
# B4：build_charts 预索引性能
# ---------------------------------------------------------------------------

def test_build_charts_heatmap_scales_with_index() -> None:
    """10 万级 history 上 build_charts 应远快于原线性扫描（验收 < 1.5s）。"""
    from src.config import CATEGORIES, MARKETS

    history: list[dict] = []
    for category in sorted(CATEGORIES.keys()):
        for market in sorted(MARKETS.keys()):
            for week in range(104):
                history.append(
                    {
                        "date": f"2024-01-{week % 28 + 1:02d}",
                        "category": category,
                        "market": market,
                        "search_index": float(week % 100),
                        "sales_volume": 100.0,
                    }
                )
    assert len(history) == len(CATEGORIES) * len(MARKETS) * 104
    data = {"history": history}
    start = time.perf_counter()
    charts = four_brain.build_charts(_mini_brains(), data)
    elapsed = time.perf_counter() - start
    heatmap = next(c for c in charts if c["id"] == "heatmap")
    assert len(heatmap["values"]) == len(CATEGORIES)
    assert len(heatmap["values"][0]) == len(MARKETS)
    assert elapsed < 1.5, f"build_charts took {elapsed:.2f}s（应 < 1.5s）"


# ---------------------------------------------------------------------------
# B4：worker 子进程隔离降级
# ---------------------------------------------------------------------------

def test_worker_isolated_timeout_degrades_and_recovers() -> None:
    """worker 超时应抛 RuntimeError（API 层转 503），池重建后恢复可用。"""
    from src.four_brain import worker

    try:
        worker.run_isolated(
            {"keyword": "mini dehumidifier", "market": "us", "search_provider": "mock"},
            False,
            timeout=0.01,
        )
        pytest.fail("预期超时抛 RuntimeError，实际成功")
    except RuntimeError as exc:
        assert "四脑分析子进程异常" in str(exc)
    # 池已重建：再次调用应正常返回
    result = worker.run_isolated(
        {"keyword": "pet feeder", "market": "us", "search_provider": "mock"},
        False,
        timeout=300,
    )
    assert result.get("category")
    assert result.get("charts")
    worker.close()


def test_worker_isolated_value_error_passthrough() -> None:
    """业务参数错误（ValueError）应原样透传，而不是降级为 RuntimeError。"""
    from src.four_brain import worker

    with pytest.raises(ValueError):
        worker.run_isolated(
            {"keyword": "x", "market": "us", "use_user_data": True, "user_data": {"bad": True}},
            False,
            timeout=300,
        )
    worker.close()


# ---------------------------------------------------------------------------
# B5：/api/dashboard-data?meta=1 轻量检查
# ---------------------------------------------------------------------------

def test_dashboard_data_meta_lightweight() -> None:
    from src.config import OUTPUT_DIR

    if not (OUTPUT_DIR / "dashboard-data.json").exists():
        pytest.skip("output/dashboard-data.json 缺失（未构建看板数据）")
    resp = client.get("/api/dashboard-data", params={"meta": True})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("ok") is True
    assert payload.get("size_mb", 0) > 1
    assert payload.get("updated_at")
    assert payload.get("data_as_of")
    # meta 不应携带全量 history
    assert "history" not in payload


def test_check_connect_group_dashboard_data_ok() -> None:
    """自检 dashboard-data 检查已轻量化：不再在端点列表拉 55MB 全量。"""
    from src import checks as env_checks
    from src.api import services
    from src.config import OUTPUT_DIR

    # a) 服务端轻量元数据函数返回 ok
    if not (OUTPUT_DIR / "dashboard-data.json").exists():
        pytest.skip("output/dashboard-data.json 缺失（未构建看板数据）")
    meta = services._dashboard_data_meta()
    assert meta["ok"] is True
    assert meta["size_mb"] > 1
    # b) connect 组不再把 /api/dashboard-data 全量端点纳入探测
    assert not any(path == "/api/dashboard-data" for path, _label, _check in env_checks.CONNECT_ENDPOINTS)


# ---------------------------------------------------------------------------
# S9：演示字段别名（前端 TradeResultDetail 读取 name/message/title/margin_pct）
# ---------------------------------------------------------------------------

def test_preflight_to_dict_has_frontend_aliases() -> None:
    result = build_preflight("cn_changsha_mifen", "us")
    payload = result.to_dict()
    assert payload["items"], "体检清单不应为空"
    first = payload["items"][0]
    assert first["name"] == first["item"]
    assert first["message"] == first["note"]
    assert first["status"] in {"pass", "attention", "pending"}


def test_osint_to_dict_has_frontend_aliases() -> None:
    result = assess_osint("cn_changsha_mifen", "us", financing_ready_score=80.0)
    payload = result.to_dict()
    assert payload["readiness"] in {"ready", "conditional", "not_ready"}
    assert payload["checks"]
    first = payload["checks"][0]
    assert first["title"] == first["item"]
    assert first["name"] == first["item"]
    assert first["message"] == first["note"]


def test_fx_sensitivity_has_margin_pct() -> None:
    result = LandedCostCalculator().calculate(
        LandedCostInput(
            category="cn_changsha_mifen",
            market="us",
            unit_price_usd=30.0,
            procurement_cost_cny=30.0 * 7.15 * 0.35,
            tariff_rate=0.1,
        )
    )
    for label, item in result.fx_sensitivity.items():
        assert "利润率%" in item, label
        assert item["margin_pct"] == item["利润率%"], label
        assert item["margin_pct"] != 0 or item["汇率"] > 0


def test_trade_decision_api_carries_aliases() -> None:
    """/api/trade/decision 返回的 preflight/osint/fx_sensitivity 含前端别名。"""
    resp = client.get(
        "/api/trade/decision",
        params={"category": "cn_latiao", "market": "us", "unit_price_usd": 30.0, "procurement_cost_cny": 75.0},
    )
    assert resp.status_code == 200
    payload = resp.json()
    preflight = payload.get("preflight") or {}
    assert preflight.get("items"), "preflight.items 不应为空"
    assert "name" in preflight["items"][0] and "message" in preflight["items"][0]
    osint = payload.get("osint") or {}
    assert osint.get("checks")
    assert "title" in osint["checks"][0] and "message" in osint["checks"][0]
    fx = payload.get("fx_sensitivity") or {}
    assert fx, "fx_sensitivity 不应为空"
    for item in fx.values():
        assert "margin_pct" in item


# ---------------------------------------------------------------------------
# N1：real_training 口径说明
# ---------------------------------------------------------------------------

def test_real_training_status_has_caliber_note(monkeypatch, tmp_path) -> None:
    """train_real_enhanced.py 的 _write_status 应写入「主口径组合数 vs 实际组合数」的口径说明。"""
    import sys

    scripts_dir = PROJECT_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import train_real_enhanced  # noqa: E402

    status_file = tmp_path / "real_training_status.json"
    monkeypatch.setattr(train_real_enhanced, "REAL_TRAINING_STATUS_JSON", status_file)
    monkeypatch.setattr(train_real_enhanced, "REAL_TRAINING_CSV", tmp_path / "training.csv")

    import pandas as pd

    frame = pd.DataFrame(
        {
            "category": ["cn_changsha_mifen", "cn_changsha_mifen", "cn_latiao", "cn_latiao"],
            "market": ["us", "eu", "us", "eu"],
            "date": ["2026-01-01", "2026-01-01", "2026-01-01", "2026-01-01"],
            "sales_volume": [1.0, 2.0, 3.0, 4.0],
        }
    )
    train_real_enhanced._write_status(frame, proxy_status=None)
    raw = json.loads(status_file.read_text(encoding="utf-8"))
    assert raw["combos"] == 4
    assert "caliber_note" in raw
    note = raw["caliber_note"]
    assert "1980" in note and "合成特征" in note
