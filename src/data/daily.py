"""每日联网更新：日期对齐、演示载荷、联网快照与状态落盘。

供 ``scripts/run_daily_update.py`` 编排调用，核心函数可直接单测。
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

from src.config import CATEGORIES, MARKETS
from src.data.crawler_signals import load_latest_snapshot, snapshot_status

MODELS = {
    "prophet_baseline": "Prophet 基线",
    "lightgbm_advanced": "LightGBM 进阶",
}

ACTUAL_WEEKS = 26
FORECAST_WEEKS = 13
_WEEKLY_IDX = [i * 7 for i in range(FORECAST_WEEKS)]


def latest_data_date(as_of: Any = None) -> pd.Timestamp:
    """返回演示数据的截止日；默认今天，每日刷新时直接落在当天。"""
    as_of = (
        pd.Timestamp(as_of)
        if as_of is not None
        else pd.Timestamp.today().normalize()
    )
    return as_of.normalize()


def _rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return json.loads(out.to_json(orient="records", force_ascii=False))


def build_dashboard_payload(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    recommendations: pd.DataFrame,
    metrics: dict[str, Any],
    crawler: dict[str, Any] | None = None,
    policy_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """生成四脑引擎读取的 dashboard-data.json 载荷。"""
    models_order = [m for m in MODELS if m in set(forecast["model"].unique())]
    if not models_order:
        models_order = list(MODELS.keys())
    return {
        "categories": CATEGORIES,
        "markets": MARKETS,
        "models": MODELS,
        "models_order": models_order,
        "history": _rows(history),
        "forecast": _rows(forecast),
        "recommendations": recommendations.to_dict(orient="records"),
        "metrics": metrics,
        "crawler": crawler if crawler is not None else load_latest_snapshot(),
        "policy_events": policy_events or [],
    }


def collect_daily_snapshot(
    search_func: Callable[..., dict[str, Any]],
    queries: Iterable[str],
    provider: str,
    output_dir: Path,
    snapshot_date: date | str | None = None,
    workers: int = 8,
) -> dict[str, Any]:
    """执行每日联网检索并把结果落盘；单次失败自动回退模拟结果。

    ``workers`` 控制并发检索线程数；结果为 1 或查询数不足 2 时按顺序执行，
    结果顺序始终与 ``queries`` 保持一致。
    """
    snapshot_date = pd.Timestamp(
        snapshot_date or pd.Timestamp.today().normalize()
    ).date()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    query_list = list(queries)

    def _one(query: str) -> dict[str, Any]:
        try:
            result = search_func(query, max_results=3, provider=provider)
        except Exception as exc:  # noqa: BLE001 - 联网失败统一回退 mock
            result = {
                "provider": provider,
                "fallback_used": True,
                "results": [
                    {
                        "title": f"模拟搜索结果：{query}",
                        "snippet": f"联网失败：{exc}",
                        "link": "",
                    }
                ],
                "error": str(exc),
            }
        return {
            "query": query,
            "provider": result.get("provider") or provider,
            "fallback_used": bool(result.get("fallback_used")),
            "results": result.get("results", []),
        }

    if workers > 1 and len(query_list) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            entries = list(pool.map(_one, query_list))
    else:
        entries = [_one(query) for query in query_list]

    fallback_used = any(item["fallback_used"] for item in entries)

    payload = {
        "date": snapshot_date.isoformat(),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "provider": provider,
        "fallback_used": fallback_used,
        "queries": entries,
        "sources_count": sum(len(item["results"]) for item in entries),
    }
    path = output_dir / f"{snapshot_date.isoformat()}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def write_data_status(
    output_dir: Path,
    *,
    data_as_of: str,
    generated_at: str,
    provider: str,
    fallback_used: bool,
    snapshot_path: str | None,
    sources_count: int,
    updated_files: Iterable[str],
    next_update: str | None = None,
    crawler: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    trends: dict[str, Any] | None = None,
    platform_rankings: dict[str, Any] | None = None,
    market_daily: dict[str, Any] | None = None,
    customs: dict[str, Any] | None = None,
    open_food_facts: dict[str, Any] | None = None,
    anomalies: dict[str, Any] | None = None,
    suppliers: dict[str, Any] | None = None,
    real_training: dict[str, Any] | None = None,
    real_proxy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """写入每日数据更新状态，供 API 与看板展示。"""
    next_update = next_update or (
        pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
    ).strftime("%Y-%m-%d")
    payload = {
        "generated_at": generated_at,
        "data_as_of": str(data_as_of),
        "as_of_label": f"数据更新至 {data_as_of}（当日）",
        "next_update": next_update,
        "online": {
            "provider": provider,
            "fallback_used": bool(fallback_used),
            "snapshot": snapshot_path or "",
            "sources_count": int(sources_count),
        },
        "crawler": snapshot_status(crawler or load_latest_snapshot()),
        "policy": policy or {"enabled": False},
        "trends": trends or {"enabled": False},
        "platform_rankings": platform_rankings or {"enabled": False},
        "market_daily": market_daily or {"enabled": False},
        "customs": customs or {"enabled": False},
        "open_food_facts": open_food_facts or {"enabled": False},
        "anomalies": anomalies or {"enabled": False},
        "suppliers": suppliers or {"enabled": False},
        "real_training": real_training or {"enabled": False},
        "real_proxy": real_proxy or {"enabled": False},
        "updated_files": sorted(set(updated_files)),
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data_status.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def refresh_demo_payloads(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    recommendations: pd.DataFrame,
    metrics: dict[str, Any],
    trade_report: dict[str, Any],
    generated_at: str,
    dashboard_data_path: Path,
    crawler: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """刷新四脑数据文件（dashboard-data.json）。"""
    dashboard_data_path = Path(dashboard_data_path)
    dashboard_payload = build_dashboard_payload(
        history,
        forecast,
        recommendations,
        metrics,
        crawler=crawler,
        policy_events=trade_report.get("policy_events", []),
    )

    dashboard_data_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_data_path.write_text(
        json.dumps(
            dashboard_payload, ensure_ascii=False, separators=(",", ":")
        ),
        encoding="utf-8",
    )
    return {"dashboard_data": dashboard_data_path}
