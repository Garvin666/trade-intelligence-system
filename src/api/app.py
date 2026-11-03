"""Unified FastAPI backend for the cross-border product-selection system.

The service combines the project pipeline artifacts (history, forecast,
recommendations, model metrics, trade demo report) with the four-brain
analysis engine and a small SQLite state store for feedback and scoring
weights. It also serves the existing demo pages so the frontend can be
developed against the same origin.
"""

from __future__ import annotations

import io
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger("src.api.app")

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse

from src.api import (
    ai_config,
    brain_bridge,
    control_run,
    jobs,
    mcp_bridge,
    services,
    store,
)
from src.analysis.eda import build_eda_report
from src.data.seller_magic_mapping import (
    build_verdict_export,
    normalize_seller_magic_csv,
)
from src.api.middleware import (
    ApiKeyMiddleware,
    BodySizeMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from src import checks as env_checks
from src.config import CATEGORIES, EDA_OUTPUT_DIR, MARKETS, OUTPUT_DIR
from src.control import benchmark as control_benchmark
from src.four_brain import ai_provider
from src.trade.decision import build_trade_decision
from src.trade.policy_impact import build_policy_impact
from src.trade.report import build_launch_report, build_selection_report

COMBO_COUNT = len(CATEGORIES) * len(MARKETS)  # 132 食品 SKU × 15 市场 = 1980

ALLOWED_ORIGINS = [
    s.strip()
    for s in os.environ.get(
        "BACKEND_ALLOWED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if s.strip()
]

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup hook: launch the optional policy scheduler and enter the MCP

    session manager lifecycle when the MCP endpoint is mounted.
    """
    _start_policy_scheduler()
    if os.environ.get("BACKEND_AUTO_REFRESH", "0") == "1":
        try:
            jobs.start("daily_update", {})
            logger.info("BACKEND_AUTO_REFRESH=1: 已在启动时触发每日数据更新")
        except Exception as exc:  # noqa: BLE001 - 启动期失败不应阻断服务
            logger.warning("启动时自动刷新失败: %s", exc)
    try:
        if MCP_MOUNTED and _mcp_manager is not None:
            async with _mcp_manager.run():
                yield
        else:
            yield
    finally:
        # 退出时回收四脑隔离 worker 进程池，避免残留子进程。
        try:
            from src.four_brain import worker as four_brain_worker

            four_brain_worker.close()
        except Exception:  # noqa: BLE001 - 退出阶段清理失败不影响关闭
            pass


app = FastAPI(
    title="跨境电商智能选品系统后端服务",
    description=(
        "统一后端 API：看板数据、模型指标、选品推荐、贸易决策、政策事件、"
        "四脑协同分析、反馈与权重配置。"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(ApiKeyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(BodySizeMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_smart_agent_app() -> FastAPI:
    """加载独立小助手应用并返回其 FastAPI app。"""
    import importlib.util

    module_path = Path(__file__).resolve().parents[2] / "小助手" / "main.py"
    spec = importlib.util.spec_from_file_location("smart_agent_app", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载小助手模块: {module_path}")
    spec.loader.exec_module(module)
    return module.app


smart_agent_app = _load_smart_agent_app()
app.mount("/agent", smart_agent_app, name="smart-agent")

OUTPUT_DASHBOARD_HTML = OUTPUT_DIR / "dashboard.html"
OUTPUT_DASHBOARD_DATA = OUTPUT_DIR / "dashboard-data.json"
APP_OUTPUT_DIR = OUTPUT_DIR / "app"

# /api/eda 单次上传数据行数上限（防整文件入内存后的资源滥用）。
EDA_MAX_ROWS = 200_000

FOUR_BRAIN_QUERY_KEYS = [
    "keyword",
    "market",
    "price_min",
    "price_max",
    "budget",
    "target_margin",
    "unit_cost",
    "freight_per_unit",
    "customs_per_unit",
    "ad_rate",
    "return_rate",
    "moq",
    "lead_time_days",
    "certifications",
    "research",
    "tools",
    "max_steps",
    "search_provider",
    "search_api_key",
    "search_api_url",
    "search_max_results",
    "extra_prompt",
    "global_prompt",
    "fast",
]


def _safe(producer: Any) -> Any:
    try:
        return producer()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ai_provider.AIProviderError as exc:
        logger.warning("AI 服务调用失败：%s", exc)
        raise HTTPException(status_code=502, detail=f"AI 服务调用失败：{exc}") from exc


def _filters(
    category: str | None = None,
    market: str | None = None,
    model: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    platform: str | None = None,
    min_score: float | None = None,
    top: int | None = None,
) -> dict[str, str | None]:
    result: dict[str, str | None] = {
        "category": category,
        "market": market,
        "model": model,
        "date_from": date_from,
        "date_to": date_to,
        "platform": platform,
    }
    if limit is not None:
        result["limit"] = str(limit)
    if min_score is not None:
        result["min_score"] = str(min_score)
    if top is not None:
        result["top"] = str(top)
    return result


def _file_response(path: Path, cache: str = "no-cache") -> FileResponse:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path.name}")
    return FileResponse(path, headers={"Cache-Control": cache})


def _decision_gate(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    if payload.get("user_data") or payload.get("use_user_data") or payload.get("offline_only"):
        return {"decision_data_ready": True, "reason": "user data mode"}
    status = services.data_status()
    quality = status.get("crawl_quality") or {}
    if not quality.get("decision_data_ready"):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "data_gap",
                "message": "决策链缺少真实或已验证缓存数据，拒绝使用 mock 计算。",
                "reasons": quality.get("reasons") or ["未生成爬取质量状态"],
            },
        )
    return quality


def _jobs_summary() -> dict[str, Any]:
    items = list(jobs.status())
    items.append(_control_run_summary())
    items.append(_policy_refresh_summary())
    return {"count": len(items), "items": items}


def _control_run_summary() -> dict[str, Any]:
    state = control_run.status()
    return {
        "name": "control_run",
        "label": "顶级 AI 对照",
        "status": state.get("status") or "idle",
        "exclusive": True,
        "job_id": state.get("job_id"),
        "progress": state.get("progress"),
        "error": state.get("error"),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
    }


def _policy_refresh_summary() -> dict[str, Any]:
    payload = services.policy_watch_payload()
    updated_at = payload.get("updated_at") or ""
    return {
        "name": "policy_refresh",
        "label": "政策雷达刷新",
        "status": "ready" if updated_at else "idle",
        "exclusive": False,
        "updated_at": updated_at,
        "date": payload.get("date") or "",
        "verified_count": payload.get("verified_count"),
    }


def _start_policy_scheduler() -> None:
    import threading
    import time

    interval = int(os.environ.get("BACKEND_POLICY_INTERVAL_SECONDS", "0") or "0")
    if interval <= 0:
        return

    def _loop() -> None:
        while True:
            time.sleep(interval)
            try:
                services.refresh_policy({})
            except Exception:  # noqa: BLE001 - keep the scheduler alive
                pass

    threading.Thread(target=_loop, daemon=True).start()


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    if APP_OUTPUT_DIR.exists():
        return RedirectResponse("/app")
    return RedirectResponse("/docs")


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> RedirectResponse:
    return RedirectResponse("/app", status_code=307)


@app.get("/output/dashboard.html", include_in_schema=False)
def output_dashboard() -> FileResponse:
    return _file_response(OUTPUT_DASHBOARD_HTML, cache="public, max-age=300")


@app.get("/output/dashboard-data.json", include_in_schema=False)
def output_dashboard_data() -> FileResponse:
    return _file_response(
        OUTPUT_DASHBOARD_DATA,
        cache="public, max-age=300, must-revalidate",
    )


@app.get("/app", include_in_schema=False)
def app_index() -> FileResponse:
    return _file_response(APP_OUTPUT_DIR / "index.html")


@app.get("/app/{full_path:path}", include_in_schema=False)
def app_spa(full_path: str) -> FileResponse:
    if not APP_OUTPUT_DIR.exists():
        raise HTTPException(status_code=404, detail="React app not built")
    candidate = (APP_OUTPUT_DIR / full_path).resolve()
    if (
        full_path
        and candidate.is_file()
        and candidate.is_relative_to(APP_OUTPUT_DIR.resolve())
    ):
        if full_path.startswith("assets/"):
            return _file_response(
                candidate,
                cache="public, max-age=31536000, immutable",
            )
        return _file_response(candidate, cache="public, max-age=300")
    return _file_response(APP_OUTPUT_DIR / "index.html", cache="no-cache")

MCP_MOUNTED = False
_mcp_manager = None
if mcp_bridge.available():
    try:
        _mcp_manager = mcp_bridge.get_session_manager()
        app.mount("/mcp", _mcp_manager.asgi_app, name="mcp")
        MCP_MOUNTED = True
    except RuntimeError:  # pragma: no cover - SDK present but setup failed
        MCP_MOUNTED = False


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        **services.health(),
        "mcp": MCP_MOUNTED,
        "jobs": _jobs_summary(),
    }


@app.get("/api/jobs")
def jobs_list() -> dict[str, Any]:
    """统一后台任务注册表（单进程后端）。"""
    return _jobs_summary()


@app.get("/api/jobs/{name}")
def job_status(name: str) -> dict[str, Any]:
    try:
        return jobs.status(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job: {name}") from exc


@app.post("/api/jobs/{name}/start")
def job_start(name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return {"ok": True, "job": jobs.start(name, payload or {})}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job: {name}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/jobs/{name}/stop")
def job_stop(name: str) -> dict[str, Any]:
    try:
        return jobs.stop(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job: {name}") from exc


@app.get("/api/data/status")
def data_status() -> dict[str, Any]:
    """每日数据更新与联网快照状态。"""
    return services.data_status()


@app.get("/api/data/suppliers")
def data_suppliers() -> dict[str, Any]:
    """最新货源/供应商尽调快照。"""
    return services.suppliers()


@app.get("/api/examples")
def examples() -> dict[str, Any]:
    """三套系统与立项报告的示例预设（一键填充）。"""
    return services.examples()


@app.get("/api/anomalies")
def anomalies() -> dict[str, Any]:
    """最新异常监测快照。"""
    return services.anomalies()


@app.get("/api/categories")
def categories() -> dict[str, str]:
    return services.categories()


@app.get("/api/markets")
def markets() -> dict[str, str]:
    return services.markets()


@app.get("/api/models")
def models() -> dict[str, str]:
    return services.models()


@app.get("/api/history")
def history(
    category: str | None = Query(None),
    market: str | None = Query(None),
    model: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=5000),
) -> dict[str, Any]:
    filters = _filters(category, market, model, date_from, date_to, limit)
    items = _safe(lambda: services.history(filters))
    return {"count": len(items), "items": items}


@app.get("/api/forecast")
def forecast(
    category: str | None = Query(None),
    market: str | None = Query(None),
    model: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=5000),
) -> dict[str, Any]:
    filters = _filters(category, market, model, date_from, date_to, limit)
    items = _safe(lambda: services.forecast(filters))
    return {"count": len(items), "items": items}


@app.get("/api/model-metrics")
def model_metrics(
    category: str | None = Query(None),
    market: str | None = Query(None),
    model: str | None = Query(None),
) -> dict[str, Any]:
    filters = _filters(category, market, model)
    return _safe(lambda: services.model_metrics(filters))


@app.get("/api/market-intel")
def market_intel(
    category: str | None = Query(None),
    market: str | None = Query(None),
    limit: int | None = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    filters = _filters(category, market, limit=limit)
    return _safe(lambda: services.market_intel(filters))


@app.get("/api/control/metrics")
def control_metrics() -> dict[str, Any]:
    """顶级 AI 对照实验只读结果：未运行/部分运行/完成三种状态。"""
    return services.control_metrics()


@app.get("/api/ai/config")
def ai_config_get() -> dict[str, Any]:
    """Read the in-memory global AI config (masked, never returns the key)."""
    return ai_config.get_status()


@app.post("/api/ai/config")
def ai_config_post(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist the page-level AI config into backend memory."""
    return ai_config.set_config(payload)


@app.post("/api/control/run")
def control_run_start(payload: dict[str, Any]) -> dict[str, Any]:
    """Start a real top-AI control run with the configured model."""
    try:
        return control_run.start(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/control/run/status")
def control_run_status() -> dict[str, Any]:
    """Poll the background control benchmark job."""
    return control_run.status()


@app.get("/api/control/web/setup")
def control_web_setup() -> dict[str, Any]:
    """DeepSeek 网页版对照运行准备信息（无需 API Key）。"""
    return _safe(lambda: control_benchmark.web_setup())


@app.get("/api/control/train-data")
def control_train_data() -> FileResponse:
    """下载对照组训练数据 CSV，供 DeepSeek 网页版上传。"""
    if not control_benchmark.TRAIN_CSV.exists():
        raise HTTPException(
            status_code=404,
            detail="缺少 data/control/train_data.csv，请先运行 scripts/control_group.py prepare",
        )
    return FileResponse(
        control_benchmark.TRAIN_CSV,
        media_type="text/csv",
        filename="train_data.csv",
    )


@app.post("/api/control/web/save")
def control_web_save(payload: dict[str, Any]) -> dict[str, Any]:
    """保存一次 DeepSeek 网页版回复并评分（无需 API Key）。"""
    try:
        run = int(payload.get("run"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="run 必须是 1 或 2") from exc
    text = str(payload.get("text") or "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="回复内容不能为空")
    try:
        return control_benchmark.save_web_response(
            run=run,
            text=text,
            model_version=str(payload.get("model_version") or "").strip() or None,
            code_execution=bool(payload.get("code_execution", False)),
            note=str(payload.get("note") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/system/eval")
def system_eval() -> dict[str, Any]:
    """06B 系统评测指标：当前模型宏平均与覆盖/方向/峰值/排序/稳健性。"""
    return services.system_eval()


@app.get("/api/engineering/status")
def engineering_status() -> dict[str, Any]:
    """工程化状态：数据更新、测试数量与 API 清单。"""
    return services.engineering_status()


@app.get("/api/check")
def env_check(
    groups: str | None = Query(None),
    depth: str = Query("quick"),
) -> dict[str, Any]:
    """系统检查模式（快速档）：环境 / 依赖 / 代码完善度 / 前后端连接。

    深度档（pytest 全套 + 前端 typecheck）请通过 CLI 执行：
    ``scripts/run_env_check.py --full``。
    """
    if depth != "quick":
        raise HTTPException(
            status_code=400,
            detail="Web 检查仅支持快速档；深度档请运行 scripts/run_env_check.py --full",
        )
    group_list = [
        g.strip()
        for g in (groups or ",".join(env_checks.VALID_GROUPS)).split(",")
        if g.strip()
    ]
    invalid = [g for g in group_list if g not in env_checks.VALID_GROUPS]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"未知检查分组：{', '.join(invalid)}（可选 {', '.join(env_checks.VALID_GROUPS)}）",
        )
    return env_checks.run_checks(groups=group_list, depth="quick")


@app.get("/api/recommendations")
def recommendations(
    category: str | None = Query(None),
    market: str | None = Query(None),
    model: str | None = Query(None),
    min_score: float | None = Query(None, ge=0, le=100),
    top: int | None = Query(None, ge=1, le=100),
    limit: int | None = Query(None, ge=1, le=100),
    include_no_go: bool = Query(False),
) -> dict[str, Any]:
    _decision_gate()
    filters = _filters(category, market, model, limit=limit, min_score=min_score, top=top)
    filters["include_no_go"] = "1" if include_no_go else "0"
    items = _safe(lambda: services.recommendations(filters))
    return {"count": len(items), "items": items}


@app.get("/api/summary")
def summary(
    category: str | None = Query(None),
    market: str | None = Query(None),
    model: str | None = Query(None),
) -> dict[str, Any]:
    filters = _filters(category, market, model)
    return _safe(lambda: services.summary(filters))


@app.get("/api/search/trends")
def search_trends(
    category: str | None = Query(None),
    market: str | None = Query(None),
) -> dict[str, Any]:
    filters = _filters(category, market)
    items = _safe(lambda: services.search_trends(filters))
    return {"count": len(items), "items": items}


@app.get("/api/search")
def web_search(
    q: str = Query(..., min_length=1, max_length=300),
    provider: str | None = Query(None),
    max_results: int = Query(5, ge=1, le=20),
) -> dict[str, Any]:
    """联网搜索：默认 DuckDuckGo Lite 直连，失败自动回退 mock。"""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="q is required")
    return services.web_search(
        query,
        max_results=max_results,
        provider=provider,
    )


@app.post("/api/eda")
def eda_report(file: UploadFile = File(...)) -> dict[str, Any]:
    """上传 CSV/JSON 文件，返回数据体检摘要、异常行与 A/B 检验。"""
    raw = file.file.read()
    name = file.filename or "upload.csv"
    if name.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(raw))
    else:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"JSON 解析失败：{exc}") from exc
        records = (
            data
            if isinstance(data, list)
            else data.get("rows") or data.get("history") or []
        )
        df = pd.DataFrame(records)
    if len(df) > EDA_MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"数据行数 {len(df):,} 超过上限 {EDA_MAX_ROWS:,}，请裁剪后重试。",
        )
    report = build_eda_report(df, title=f"数据体检：{name}")
    if report.get("html_report"):
        report["report_url"] = "/eda/reports/" + Path(report["html_report"]).name
    return report


@app.get("/eda/reports/{name}")
def eda_report_file(name: str) -> FileResponse:
    safe_name = Path(name).name
    if not safe_name:
        raise HTTPException(status_code=404, detail="report not found")
    return _file_response(EDA_OUTPUT_DIR / safe_name)


@app.post("/api/import/seller-magic")
def import_seller_magic(file: UploadFile = File(...)) -> dict[str, Any]:
    """卖家精灵 / 浏览器导出 CSV 一键导入（C-2）：字段字典映射 + 必需列校验 + 摘要。"""
    raw = file.file.read()
    name = file.filename or "upload.csv"
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:  # noqa: BLE001 - 解析失败返回 400
        raise HTTPException(status_code=400, detail=f"CSV 解析失败：{exc}") from exc
    result = normalize_seller_magic_csv(df)
    report = result["mapping"] if "mapping" in result else result["report"]
    if report.get("missing"):
        raise HTTPException(
            status_code=400,
            detail=f"缺少必需列：{report['missing']}（需含关键词列，如「关键词/keyword」）",
        )
    frame = result["df"]
    summary = {
        "rows": int(len(frame)),
        "matched_columns": len(report.get("matched", {})),
        "unmatched_columns": report.get("unmatched", []),
        "numeric_columns": report.get("numeric_columns", []),
        "dropped_rows": report.get("dropped", 0),
        "keyword_count": int(frame["keyword"].nunique()) if "keyword" in frame.columns else 0,
        "avg_price": (
            round(float(frame["price_median"].mean()), 2)
            if "price_median" in frame.columns and frame["price_median"].notna().any()
            else None
        ),
    }
    preview_frame = (
        frame.groupby("keyword", as_index=False)["price_median"].mean()
        if "price_median" in frame.columns
        else frame[["keyword"]].drop_duplicates()
    )
    top_keywords = [
        {
            "keyword": str(row.get("keyword")),
            "avg_price": (
                round(float(row.get("price_median")), 2)
                if row.get("price_median") is not None
                else None
            ),
        }
        for row in preview_frame.head(10).to_dict("records")
    ]
    return {
        "ok": True,
        "mapping": report,
        "summary": summary,
        "top_keywords": top_keywords,
        "file": name,
    }


def _push_webhook(url: str, payload: dict[str, Any], timeout: int = 10) -> dict[str, Any]:
    """Webhook 推送（C-2）：POST JSON，失败返回 warning 不阻断导出。"""
    import urllib.request

    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"status": "ok", "http": response.status}
    except Exception as exc:  # noqa: BLE001 - 推送失败仅告警
        return {"status": "warning", "detail": str(exc)}


@app.post("/api/export/verdicts")
def export_verdicts(payload: dict[str, Any]) -> dict[str, Any]:
    """Go/No-Go 结论标准导出（CSV 含证据链引用）+ 可选 Webhook 推送（C-2）。"""
    rows = payload.get("rows") or []
    if not rows:
        raise HTTPException(status_code=400, detail="rows 不能为空")
    csv_text = build_verdict_export(rows)
    webhook_url = str(payload.get("webhook_url") or "").strip()
    push_result = _push_webhook(webhook_url, payload) if webhook_url else None
    return {
        "ok": True,
        "csv": csv_text,
        "row_count": len(rows),
        "webhook": push_result,
    }


@app.post("/api/search/research")
def search_research(payload: dict[str, Any]) -> dict[str, Any]:
    """联网研究模式：无 AI Key 也能执行多查询搜索并汇总来源。"""
    if not brain_bridge.available():
        raise HTTPException(status_code=503, detail=brain_bridge.describe())
    return brain_bridge.research_only(payload)


@app.get("/api/crawler/signals")
def crawler_signals_get(
    category: str | None = Query(None),
    market: str | None = Query(None),
    keyword: str | None = Query(None),
) -> dict[str, Any]:
    """Latest crawler evidence snapshot, optionally filtered."""
    filters = _filters(category, market)
    if keyword:
        filters["keyword"] = keyword.strip()
    return _safe(lambda: services.crawler_signals(filters))


@app.post("/api/crawler/signals")
def crawler_signals_post(payload: dict[str, Any]) -> dict[str, Any]:
    """Run an on-demand crawler signal for one keyword/market."""
    return _safe(lambda: services.crawler_signal_live(payload))


@app.get("/api/reviews/summary")
def reviews_summary(
    category: str | None = Query(None),
    market: str | None = Query(None),
) -> dict[str, Any]:
    filters = _filters(category, market)
    items = _safe(lambda: services.review_summary(filters))
    return {"count": len(items), "items": items}


@app.get("/api/trade/export-value")
def export_value(
    category: str | None = Query(None),
    market: str | None = Query(None),
) -> dict[str, Any]:
    filters = _filters(category, market)
    items = _safe(lambda: services.export_value(filters))
    return {"count": len(items), "items": items}


@app.get("/api/competition/index")
def competition_index(
    category: str | None = Query(None),
    market: str | None = Query(None),
) -> dict[str, Any]:
    filters = _filters(category, market)
    items = _safe(lambda: services.competition_index(filters))
    return {"count": len(items), "items": items}


@app.get("/api/cost/metrics")
def cost_metrics(
    category: str | None = Query(None),
    market: str | None = Query(None),
) -> dict[str, Any]:
    filters = _filters(category, market)
    items = _safe(lambda: services.cost_metrics(filters))
    return {"count": len(items), "items": items}


@app.get("/api/platform/rankings")
def platform_rankings(
    category: str | None = Query(None),
    market: str | None = Query(None),
    platform: str | None = Query(None),
    limit: int | None = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    filters = _filters(category, market, limit=limit, platform=platform)
    items = _safe(lambda: services.platform_rankings(filters))
    return {"count": len(items), "items": items}


@app.get("/api/risk/overview")
def risk_overview(
    category: str | None = Query(None),
    market: str | None = Query(None),
) -> dict[str, Any]:
    filters = _filters(category, market)
    items = _safe(lambda: services.risk_overview(filters))
    return {"count": len(items), "items": items}


@app.get("/api/market/compare")
def market_compare(
    category: str | None = Query(None),
) -> dict[str, Any]:
    filters = _filters(category)
    items = _safe(lambda: services.market_compare(filters))
    return {"count": len(items), "items": items}


@app.get("/api/dashboard-data")
def dashboard_data(
    category: str | None = Query(None),
    market: str | None = Query(None),
    model: str | None = Query(None),
    limit: int | None = Query(None, description="图表序列最大期数（最近 N 周/天）"),
    meta: bool = Query(False, description="仅返回轻量元信息（自检用，不拉全量数据）"),
) -> dict[str, Any]:
    filters = _filters(category, market, model, limit=limit)
    if meta:
        filters["meta"] = "1"
    return _safe(lambda: services.dashboard_data(filters))


@app.get("/api/scoring/weights")
def scoring_weights_get() -> dict[str, float]:
    return store.get_weights()


@app.post("/api/scoring/weights")
def scoring_weights_post(payload: dict[str, float]) -> dict[str, Any]:
    return {"ok": True, "weights": _safe(lambda: store.update_weights(payload))}


@app.get("/api/feedback")
def feedback_get() -> dict[str, Any]:
    return {"count": len(store.list_feedback()), "items": store.list_feedback()}


@app.post("/api/feedback", status_code=201)
def feedback_post(payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "feedback": store.add_feedback(payload)}


@app.get("/api/trade/decision")
def trade_decision(
    category: str = Query(..., description="category code: home / pet / fitness / small_appliance / outdoor"),
    market: str = Query(..., description="market code: us / eu / sea"),
    unit_price_usd: float = Query(..., gt=0),
    procurement_cost_cny: float = Query(..., gt=0),
    payment_code: str = Query("pingpong"),
    logistics_code: str = Query("small_parcel"),
    product_name: str | None = Query(None),
) -> dict[str, Any]:
    _decision_gate()
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Unsupported category: {category}")
    if market not in MARKETS:
        raise HTTPException(status_code=400, detail=f"Unsupported market: {market}")
    try:
        return build_trade_decision(
            category=category,
            market=market,
            unit_price_usd=unit_price_usd,
            procurement_cost_cny=procurement_cost_cny,
            payment_code=payment_code,
            logistics_code=logistics_code,
            product_name=product_name,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported parameter: {exc}") from exc


@app.get("/api/trade/report")
def trade_report(
    market: str | None = Query(None, description="按市场代码过滤"),
    risk_level: str | None = Query(
        None,
        description="按风险等级过滤：low / medium / high",
    ),
    limit: int | None = Query(None, ge=1, le=COMBO_COUNT, description="返回行数上限"),
    offset: int | None = Query(None, ge=0, description="跳过行数"),
) -> dict[str, Any]:
    if market is not None and market not in MARKETS:
        raise HTTPException(status_code=400, detail=f"Unsupported market: {market}")
    if risk_level is not None and risk_level not in {"low", "medium", "high"}:
        raise HTTPException(
            status_code=400,
            detail="risk_level must be low / medium / high",
        )
    return _safe(
        lambda: services.trade_report(
            {
                "market": market,
                "risk_level": risk_level,
                "limit": str(limit) if limit is not None else None,
                "offset": str(offset) if offset is not None else None,
            }
        )
    )


@app.get("/api/trade/hs-code")
def trade_hs_code(
    category: str = Query(..., description="category code: home / pet / fitness"),
    market: str = Query("us", description="market code: us / eu / sea"),
) -> dict[str, Any]:
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Unsupported category: {category}")
    if market not in MARKETS:
        raise HTTPException(status_code=400, detail=f"Unsupported market: {market}")
    return services.hs_code(category, market)


@app.get("/api/trade/hs-codes")
def trade_hs_codes(
    q: str | None = Query(None, description="按 HS 编码或描述搜索"),
    category: str | None = Query(None),
    market: str | None = Query(None),
) -> dict[str, Any]:
    """HS6 速查表检索（关键词 / 品类 / 市场可选）。"""
    items = services.hs_codes_search(query=q, category=category, market=market)
    return {"count": len(items), "items": items}


@app.get("/api/catalog")
def trade_catalog() -> dict[str, Any]:
    """Compatibility catalog for the embedded trade-decision demo."""
    return services.trade_catalog()


@app.post("/api/autofill")
def trade_autofill(payload: dict[str, Any]) -> dict[str, Any]:
    """No-op compatibility endpoint for the embedded trade demo."""
    return services.trade_autofill(payload)


@app.post("/api/analyze")
def trade_analyze(payload: dict[str, Any]) -> dict[str, Any]:
    """Server-side trade AI analysis; the embedded demo falls back here."""
    _decision_gate(payload)
    return _safe(lambda: services.trade_ai_analyze(payload))


@app.get("/api/policy/events")
def policy_events() -> dict[str, Any]:
    payload = services.policy_watch_payload()
    return {
        "count": len(payload["items"]),
        "items": payload["items"],
        "verified_count": payload["verified_count"],
        "candidate_count": payload["candidate_count"],
        "updated_at": payload["updated_at"],
        "date": payload["date"],
        "sources": payload["sources"],
        "fallback_used": payload["fallback_used"],
        "official_only": payload["official_only"],
    }


@app.post("/api/policy/refresh")
def policy_refresh(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """立即刷新政策雷达官方源快照（默认仅官方源，不生成搜索候选）。"""
    return _safe(lambda: services.refresh_policy(payload))


@app.get("/api/policy/impact")
def policy_impact(
    event_code: str = Query(..., description="政策事件 code"),
    category: str | None = Query(None, description="品类 code，缺省为全部"),
    market: str | None = Query(None, description="市场 code，缺省为事件市场"),
) -> dict[str, Any]:
    """政策冲击实验室：事件生效日前/后的税率、关税、利润与判定对比。"""
    return _safe(
        lambda: build_policy_impact(
            event_code=event_code,
            category=category,
            market=market,
        )
    )


@app.get("/api/evidence/ledger")
def evidence_ledger() -> dict[str, Any]:
    """统一证据账本：政策事件与 HS6 条目的来源、有效期与复核状态。"""
    return services.evidence_ledger()


@app.get("/api/four-brain")
def four_brain_get(request: Request) -> dict[str, Any]:
    _decision_gate({key: request.query_params[key] for key in request.query_params})
    if not brain_bridge.available():
        raise HTTPException(status_code=503, detail=brain_bridge.describe())
    payload = {
        key: request.query_params[key]
        for key in FOUR_BRAIN_QUERY_KEYS
        if key in request.query_params
    }
    use_ai = request.query_params.get("ai") == "1" or os.environ.get("FOUR_BRAIN_AI", "0") == "1"
    return _four_brain_guard(lambda: brain_bridge.analyze(payload, use_ai=use_ai))


@app.post("/api/four-brain")
def four_brain_post(payload: dict[str, Any]) -> dict[str, Any]:
    _decision_gate(payload)
    if not brain_bridge.available():
        raise HTTPException(status_code=503, detail=brain_bridge.describe())
    use_ai = payload.get("ai") in (True, "1", 1) or os.environ.get("FOUR_BRAIN_AI", "0") == "1"
    return _four_brain_guard(lambda: brain_bridge.analyze(payload, use_ai=use_ai))


def _four_brain_guard(producer: Any) -> Any:
    """四脑端点统一守卫：子进程崩溃/超时 → 503 结构化降级提示（替代裸 500）。"""
    try:
        return producer()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        # 子进程崩溃/超时属设计内降级路径（主进程存活），记 warning 即可。
        logger.warning("四脑分析降级：%s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                f"{exc}。可关闭“联网研究/AI”后重试，或检查 output/dashboard-data.json 是否完整。"
            ),
        ) from exc


@app.post("/api/four-brain/batch")
def four_brain_batch(payload: dict[str, Any]) -> dict[str, Any]:
    """批量四脑分析：输入多条产品方案，逐条分析并汇总。"""
    items = payload.get("items")
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="items 必须是数组")
    if not brain_bridge.available():
        raise HTTPException(status_code=503, detail=brain_bridge.describe())
    for item in items:
        _decision_gate(item if isinstance(item, dict) else None)
    use_ai = payload.get("ai") in (True, "1", 1) or os.environ.get("FOUR_BRAIN_AI", "0") == "1"
    try:
        return brain_bridge.analyze_batch(items, use_ai=use_ai)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/four-brain/launch-report")
def four_brain_launch_report(payload: dict[str, Any]) -> dict[str, Any]:
    """选品立项报告：模板 + 用户数据 -> AI Markdown 报告（不依赖看板数据闸）。"""
    return _safe(lambda: brain_bridge.generate_template_report(payload))


def _sse_events(events: Any):
    """把事件 dict 序列化为 text/event-stream 文本块。"""
    for event in events:
        name = str(event.get("event") or "message")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/four-brain/launch-report/stream")
def four_brain_launch_report_stream(payload: dict[str, Any]) -> StreamingResponse:
    """选品立项报告流式生成：SSE status/delta/done/error 事件。"""
    try:
        events = brain_bridge.generate_template_report_stream(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ai_provider.AIProviderError as exc:
        logger.warning("AI 服务调用失败：%s", exc)
        raise HTTPException(status_code=502, detail=f"AI 服务调用失败：{exc}") from exc
    return StreamingResponse(
        _sse_events(events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/ai/status")
def ai_status() -> dict[str, Any]:
    return brain_bridge.ai_status()


@app.post("/api/ai/test")
def ai_test(payload: dict[str, Any]) -> dict[str, Any]:
    return brain_bridge.ai_test(payload)


@app.post("/api/search/test")
def search_test(payload: dict[str, Any]) -> dict[str, Any]:
    return _safe(lambda: brain_bridge.search_test(payload))


@app.post("/api/export/report")
def export_report(payload: dict[str, Any]) -> FileResponse:
    """Export the current dashboard selection as Markdown or PDF."""
    if not payload or not any(
        key in payload for key in ("filters", "recommendation", "trade_decision", "evidence", "conclusion")
    ):
        raise HTTPException(status_code=400, detail="report payload is empty")
    fmt = str(payload.get("format") or "md").strip().lower()
    if fmt not in {"md", "pdf"}:
        raise HTTPException(status_code=400, detail="format must be md or pdf")
    result = build_selection_report(payload)
    if fmt == "pdf":
        return FileResponse(
            result["pdf_path"],
            media_type="application/pdf",
            filename="dashboard_selection_report.pdf",
        )
    return FileResponse(
        result["markdown_path"],
        media_type="text/markdown; charset=utf-8",
        filename="dashboard_selection_report.md",
    )


@app.post("/api/export/launch-report")
def export_launch_report(payload: dict[str, Any]) -> FileResponse:
    """Export the generated launch report as Markdown or PDF."""
    if not payload or not str(payload.get("report") or "").strip():
        raise HTTPException(status_code=400, detail="report 不能为空")
    fmt = str(payload.get("format") or "pdf").strip().lower()
    if fmt not in {"md", "pdf"}:
        raise HTTPException(status_code=400, detail="format must be md or pdf")
    result = _safe(lambda: build_launch_report(payload))
    if fmt == "pdf":
        return FileResponse(
            result["pdf_path"],
            media_type="application/pdf",
            filename="launch_report.pdf",
        )
    return FileResponse(
        result["markdown_path"],
        media_type="text/markdown; charset=utf-8",
        filename="launch_report.md",
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "服务内部错误，请查看后端日志。",
            "status": 500,
        },
    )
