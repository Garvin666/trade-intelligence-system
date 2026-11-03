"""Four-brain analysis bridge backed by the merged src.four_brain package.

The rule engine and AI research modules now live inside the canonical source
tree, so this module is a thin adapter instead of a dynamic sys.path loader.
"""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Iterator

from src.api import ai_config
from src.config import OUTPUT_DIR, REAL_TRAINING_STATUS_JSON
from src.data.search import chain_search
from src.four_brain import ai_provider, data_tools, engine as four_brain

DASHBOARD_DATA_FILE = OUTPUT_DIR / "dashboard-data.json"
MAX_LAUNCH_PROMPT_CHARS = 20000

_DASHBOARD_CACHE: tuple[tuple[str, int, int], dict[str, Any]] | None = None
_DASHBOARD_CACHE_LOCK = threading.Lock()


def available() -> bool:
    return DASHBOARD_DATA_FILE.exists()


def describe() -> dict[str, Any]:
    return {
        "available": available(),
        "engine": "src.four_brain rule engine + optional AI provider",
        "module_dir": "src/four_brain",
        "data_file": str(DASHBOARD_DATA_FILE),
    }


def _provider(payload: dict[str, Any]) -> Any:
    timeout_raw = payload.get("timeout")
    try:
        timeout = float(timeout_raw) if timeout_raw not in (None, "") else None
    except (TypeError, ValueError):
        timeout = None
    return ai_provider.OpenAICompatibleProvider(
        api_key=(
            payload.get("api_key")
            or ai_config.get_api_key()
            or os.environ.get("OPENAI_API_KEY")
            or None
        ),
        base_url=(
            payload.get("base_url")
            or ai_config.get_base_url()
            or os.environ.get("OPENAI_BASE_URL")
            or ai_provider.DEFAULT_BASE_URL
        ),
        model=(
            payload.get("model")
            or ai_config.get_model()
            or os.environ.get("OPENAI_MODEL")
            or ai_provider.DEFAULT_MODEL
        ),
        timeout=timeout,
    )


def _search_config(payload: dict[str, Any]) -> dict[str, Any]:
    provider = str(
        payload.get("search_provider")
        or payload.get("provider")
        or ai_config.get_search_provider()
        or os.environ.get("SEARCH_PROVIDER")
        or "duckduckgo_html"
    ).strip().lower()
    if provider not in data_tools.SEARCH_PROVIDERS:
        raise ValueError(
            f"Invalid search_provider: {provider}. Allowed values: {sorted(data_tools.SEARCH_PROVIDERS)}"
        )
    try:
        max_results = int(
            payload.get("search_max_results")
            or payload.get("max_results")
            or ai_config.get_search_max_results()
            or os.environ.get("SEARCH_MAX_RESULTS")
            or 5
        )
    except (TypeError, ValueError):
        max_results = 5
    return {
        "provider": provider,
        "api_key": str(
            payload.get("search_api_key")
            or payload.get("api_key")
            or ai_config.get_search_api_key()
            or os.environ.get("SEARCH_API_KEY")
            or ""
        ).strip(),
        "api_url": str(
            payload.get("search_api_url")
            or payload.get("api_url")
            or ai_config.get_search_api_url()
            or os.environ.get("SEARCH_API_URL")
            or ""
        ).strip(),
        "max_results": max(1, min(20, max_results)),
    }


def _resolve_data(payload: dict[str, Any]) -> dict[str, Any]:
    """Use uploaded user_data, otherwise fall back to the canonical dashboard data."""
    raw = payload.get("user_data")
    if raw is None:
        if not DASHBOARD_DATA_FILE.exists():
            raise FileNotFoundError("dashboard-data.json is missing")
        return _load_dashboard_data()
    if not isinstance(raw, dict):
        raise ValueError("user_data must be a JSON object")
    normalized = four_brain.normalize_data(raw)
    if not normalized.get("history") and not normalized.get("recommendations"):
        raise ValueError("user_data must contain history/latest_history or recommendations")
    return normalized


def _load_dashboard_data() -> dict[str, Any]:
    import json

    stat = DASHBOARD_DATA_FILE.stat()
    cache_key = (
        str(DASHBOARD_DATA_FILE.resolve()),
        int(stat.st_mtime_ns),
        int(stat.st_size),
    )
    global _DASHBOARD_CACHE
    with _DASHBOARD_CACHE_LOCK:
        if _DASHBOARD_CACHE is not None and _DASHBOARD_CACHE[0] == cache_key:
            return _DASHBOARD_CACHE[1]
        with DASHBOARD_DATA_FILE.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        _DASHBOARD_CACHE = (cache_key, data)
        return data


def _attach_real_evidence(
    result: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Attach trained real-evidence/proxy status to every four-brain result."""
    import json

    category = (
        result.get("category")
        or (result.get("brains") or {}).get("market", {}).get("category")
    )
    market = (
        (result.get("payload") or {}).get("market")
        or payload.get("market")
        or "us"
    )
    proxy_payload: dict[str, Any] = {
        "available": False,
        "score": None,
        "predicted_demand": None,
        "level": "neutral",
        "note": "真实销量代理模型不可用。",
    }
    model_available = False
    if category:
        from src.models.real_proxy import load_real_proxy_model, proxy_evidence_score

        proxy_payload = proxy_evidence_score(str(category), str(market))
        model_available = load_real_proxy_model() is not None
    training_status: dict[str, Any] = {"enabled": False}
    if REAL_TRAINING_STATUS_JSON.exists():
        try:
            raw_training_status = json.loads(
                REAL_TRAINING_STATUS_JSON.read_text(encoding="utf-8")
            )
            training_status = {
                key: raw_training_status.get(key)
                for key in (
                    "status",
                    "enabled",
                    "rows",
                    "combos",
                    "real_feature_count",
                    "generated_at",
                )
            }
        except (OSError, json.JSONDecodeError):
            pass
    result["real_evidence"] = {
        "category": category,
        "market": market,
        "model_available": model_available,
        "training_status": training_status,
        "proxy": proxy_payload,
    }
    return result


def search(
    query: str,
    max_results: int = 5,
    provider: str | None = None,
    api_key: str | None = None,
    api_url: str | None = None,
) -> dict[str, Any]:
    """Real-first web search with explicit fallback markers returned to callers."""
    config = {
        "provider": str(
            provider
            or ai_config.get_search_provider()
            or os.environ.get("SEARCH_PROVIDER")
            or "duckduckgo_html"
        ).strip().lower(),
        "api_key": str(
            api_key
            or ai_config.get_search_api_key()
            or os.environ.get("SEARCH_API_KEY")
            or ""
        ).strip(),
        "api_url": str(
            api_url
            or ai_config.get_search_api_url()
            or os.environ.get("SEARCH_API_URL")
            or ""
        ).strip(),
        "max_results": max(
            1,
            min(
                20,
                int(
                    max_results
                    or ai_config.get_search_max_results()
                    or os.environ.get("SEARCH_MAX_RESULTS", 5)
                ),
            ),
        ),
    }
    if config["provider"] not in data_tools.SEARCH_PROVIDERS:
        raise ValueError(
            f"Invalid search_provider: {config['provider']}. Allowed values: {sorted(data_tools.SEARCH_PROVIDERS)}"
        )

    return chain_search(
        query,
        config["max_results"],
        provider=config["provider"],
        crawler_fn=data_tools.crawler_search,
        web_fn=data_tools.search_web,
        mock_fn=data_tools.mock_search,
        config=config,
    )


def research_only(payload: dict[str, Any]) -> dict[str, Any]:
    """No-AI research mode: multi-query search + source summary + rule conclusion."""
    data = _resolve_data(payload)
    offline = bool(payload.get("use_user_data") or payload.get("offline_only"))
    if offline:
        result = four_brain.analyze(payload, data)
        result["research"] = {
            "disabled": True,
            "summary": "已按用户要求仅使用上传/本地数据，本次分析未进行联网搜索。",
            "steps": [],
            "sources": [],
            "iterations": 0,
        }
        result["ai"] = {
            "enabled": False,
            "used": False,
            "research_only": False,
            "configured": _provider(payload).configured,
        }
        result["generated_at"] = "research-only-engine-v1"
        return _attach_real_evidence(result, payload)
    rule_result = four_brain.analyze(payload, data)
    normalized = rule_result["payload"]
    keyword = normalized["keyword"]
    market_label = {
        "us": "美国",
        "eu": "欧洲",
        "sea": "东南亚",
        "jp": "日本",
        "ca": "加拿大",
        "au": "澳大利亚",
        "uk": "英国",
        "kr": "韩国",
        "de": "德国",
        "fr": "法国",
        "vn": "越南",
        "ru": "俄罗斯",
        "hu": "匈牙利",
        "ae": "中东",
        "mx": "墨西哥",
    }.get(normalized["market"], normalized["market"])
    category_label = rule_result.get("category_name", "目标品类")

    queries = [
        f"{keyword} {market_label} {category_label} market trend competition",
        f"{keyword} {market_label} tariff regulation compliance 2026",
        f"{keyword} customer reviews complaints opportunities",
        f"{keyword} {market_label} cross border e commerce selection trend",
    ]
    config = _search_config(payload)
    steps: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    fallback_any = False

    def _is_mock_result(item: dict[str, Any]) -> bool:
        source = str(item.get("source") or "").strip().lower()
        title = str(item.get("title") or "")
        return source == "mock" or title.startswith("Mock result")

    def _one_search(index_query: tuple[int, str]) -> tuple[int, dict[str, Any]]:
        index, query = index_query
        try:
            item = search(
                query,
                max_results=config["max_results"],
                provider=config["provider"],
                api_key=config["api_key"],
                api_url=config["api_url"],
            )
        except Exception as exc:  # noqa: BLE001
            item = {
                "provider": config["provider"],
                "fallback_used": True,
                "mock_used": True,
                "results": [{"title": "模拟搜索结果", "snippet": f"联网失败：{exc}", "link": ""}],
            }
        return index, item

    with ThreadPoolExecutor(max_workers=4) as pool:
        ordered = list(pool.map(_one_search, enumerate(queries, start=1)))
    for index, item in ordered:
        query = queries[index - 1]
        fallback_any = fallback_any or bool(item["fallback_used"])
        for result in item["results"]:
            sources.append({**result, "query": query})
        steps.append(
            {
                "step": index,
                "action": {"action": "web_search", "query": query},
                "sources": item["results"],
                "provider": item["provider"],
                "fallback_used": item["fallback_used"],
            }
        )

    mock_count = sum(1 for source in sources if _is_mock_result(source))
    valid = [s for s in sources if s.get("link") and not _is_mock_result(s)]
    summary = (
        f"完成 {len(queries)} 组联网检索，共 {len(sources)} 条来源"
        f"（含有效链接 {len(valid)} 条）；主题覆盖市场趋势、政策合规与用户反馈。"
        + (f"其中 {mock_count} 条为离线模拟，未进入决策链。" if mock_count else "")
    )
    rule_result["research"] = {
        "summary": summary,
        "steps": steps,
        "sources": sources,
        "provider": config["provider"],
        "fallback_used": fallback_any,
        "mock_count": mock_count,
        "mock_used": fallback_any or mock_count > 0,
        "ai_used": False,
    }
    rule_result["search_history"] = four_brain.extract_search_history(
        rule_result["research"], normalized["keyword"], normalized["market"]
    )
    rule_result["ai"] = {
        "enabled": False,
        "used": False,
        "research_only": True,
        "configured": _provider(payload).configured,
    }
    rule_result["generated_at"] = "research-only-engine-v1"
    return _attach_real_evidence(rule_result, payload)


def analyze(
    payload: dict[str, Any],
    use_ai: bool = False,
    isolated: bool | None = None,
) -> dict[str, Any]:
    """四脑分析入口。

    - ``isolated=None``：默认按环境变量 ``FOUR_BRAIN_ISOLATED``（默认 "1"）决定
      是否在独立子进程执行（防 Windows 原生崩溃拖垮主进程，见建议报告 B4）。
    - ``isolated=False``：进程内执行（测试/调试用）。
    """
    if isolated is None:
        isolated = os.environ.get("FOUR_BRAIN_ISOLATED", "1") != "0"
    if isolated:
        from src.four_brain import worker

        return worker.run_isolated(payload, bool(use_ai))
    return _analyze_impl(payload, bool(use_ai))


def _analyze_impl(payload: dict[str, Any], use_ai: bool = False) -> dict[str, Any]:
    """进程内四脑分析实现（worker 子进程与测试均复用此函数）。"""
    data = _resolve_data(payload)
    offline = bool(payload.get("use_user_data") or payload.get("offline_only"))
    provider = _provider(payload)
    if payload.get("research") and not (use_ai and provider.configured) and not offline:
        result = research_only(payload)
        result["bridge"] = describe()
        return _attach_real_evidence(result, payload)
    if use_ai:
        if provider.configured:
            if (payload.get("research") or payload.get("tools")) and not offline:
                max_steps = int(
                    payload.get("max_steps") or os.environ.get("AI_MAX_TOOL_STEPS") or 5
                )
                result = four_brain.analyze_with_research(
                    payload,
                    data,
                    provider,
                    max_steps=max_steps,
                    search_config=_search_config(payload),
                )
            else:
                result = four_brain.analyze_with_ai(payload, data, provider)
        else:
            result = four_brain.analyze(payload, data)
            result["ai"] = {
                "enabled": True,
                "used": False,
                "configured": False,
                "errors": [ai_provider.CONFIG_MISSING_MESSAGE],
            }
            if offline:
                result["research"] = {
                    "disabled": True,
                    "summary": "已按用户要求仅使用上传/本地数据，本次分析未进行联网搜索。",
                    "steps": [],
                    "sources": [],
                }
    else:
        result = four_brain.analyze(payload, data)
        result["ai"] = {
            "enabled": False,
            "used": False,
            "configured": provider.configured,
        }
        if offline:
            result["research"] = {
                "disabled": True,
                "summary": "已按用户要求仅使用上传/本地数据，本次分析未进行联网搜索。",
                "steps": [],
                "sources": [],
            }
    if result.get("research") and payload.get("keyword"):
        result["search_history"] = four_brain.extract_search_history(
            result["research"], payload["keyword"], payload.get("market") or "us"
        )
    result["bridge"] = describe()
    return _attach_real_evidence(result, payload)


def analyze_batch(
    items: list[dict[str, Any]] | None,
    use_ai: bool = False,
) -> dict[str, Any]:
    """批量四脑分析：逐条复用单组合分析，单条失败不影响其余结果。"""
    items = items or []
    if not items:
        raise ValueError("items 不能为空")
    if len(items) > 20:
        raise ValueError("items 最多 20 条")
    results: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        label = (
            str(item.get("keyword") or item.get("product") or item.get("label"))
            or f"方案 {index + 1}"
        )
        try:
            result = analyze(item, use_ai=bool(item.get("ai", use_ai)))
            result["batch_index"] = index
            results.append({"ok": True, "label": label, "result": result})
        except Exception as exc:  # noqa: BLE001 - batch must degrade gracefully
            results.append(
                {
                    "ok": False,
                    "label": label,
                    "error": str(exc)[:500],
                }
            )
    ok_count = sum(1 for item in results if item.get("ok"))
    return {
        "items": results,
        "summary": {
            "total": len(results),
            "ok": ok_count,
            "error": len(results) - ok_count,
            "use_ai": bool(use_ai),
        },
    }


def _launch_report_system() -> str:
    return (
        "你是资深跨境电商选品与竞品分析专家。请严格按照用户提供的模板结构与数据生成专业 Markdown 报告；"
        "语言为专业中文，可夹杂必要的英文商业术语；只输出 Markdown 报告正文，不要输出解释。"
    )


def _launch_report_result(
    report: str,
    provider: Any,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "report": str(report or "").strip(),
        "mode": "launch-report-v1",
        "generated_at": generated_at
        or datetime.now().astimezone().isoformat(timespec="seconds"),
        "ai": {
            "enabled": True,
            "used": True,
            "configured": True,
            "provider": provider.status() if provider else {},
        },
    }


def _prepare_launch_report(payload: dict[str, Any]) -> tuple[str, Any]:
    """校验立项报告输入并构造 provider；错误在流式响应开始前抛出。"""
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt 不能为空")
    if len(prompt) > MAX_LAUNCH_PROMPT_CHARS:
        raise ValueError(f"prompt 过长：最多 {MAX_LAUNCH_PROMPT_CHARS} 字符")
    provider = _provider(payload)
    if not provider.configured:
        raise ValueError("AI 未配置：请先在顶部“AI 接入”中配置 API Key 与模型")
    return prompt, provider


def generate_template_report(payload: dict[str, Any]) -> dict[str, Any]:
    """按用户提供的完整提示词模板生成立项报告（纯 AI，不混入规则引擎）。"""
    prompt, provider = _prepare_launch_report(payload)
    system = _launch_report_system()
    report = provider.chat_text(system, prompt, temperature=0.3)
    return _launch_report_result(report, provider)


def generate_template_report_stream(
    payload: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    """校验后返回立项报告 SSE 事件流（status/delta/done/error）。"""
    prompt, provider = _prepare_launch_report(payload)
    return _launch_report_events(prompt, provider)


def _launch_report_events(
    prompt: str,
    provider: Any,
) -> Iterator[dict[str, Any]]:
    system = _launch_report_system()
    started_at = datetime.now().astimezone()
    yield {
        "event": "status",
        "data": {"phase": "connecting", "elapsed_ms": 0, "chars": 0},
    }
    parts: list[str] = []
    try:
        for chunk in provider.chat_text_stream(system, prompt, temperature=0.3):
            content = str(chunk or "")
            if not content:
                continue
            parts.append(content)
            yield {"event": "delta", "data": {"content": content}}
            yield {
                "event": "status",
                "data": {
                    "phase": "streaming",
                    "elapsed_ms": int(
                        (datetime.now().astimezone() - started_at).total_seconds() * 1000
                    ),
                    "chars": sum(len(item) for item in parts),
                },
            }
    except ai_provider.AIProviderError as exc:
        yield {"event": "error", "data": {"message": str(exc)}}
        return
    report = "".join(parts).strip()
    elapsed_ms = int((datetime.now().astimezone() - started_at).total_seconds() * 1000)
    yield {
        "event": "status",
        "data": {"phase": "done", "elapsed_ms": elapsed_ms, "chars": len(report)},
    }
    yield {"event": "done", "data": _launch_report_result(report, provider)}


def ai_status() -> dict[str, Any]:
    provider = ai_provider.OpenAICompatibleProvider(
        api_key=ai_config.get_api_key() or os.environ.get("OPENAI_API_KEY") or None,
        base_url=(
            ai_config.get_base_url()
            or os.environ.get("OPENAI_BASE_URL")
            or ai_provider.DEFAULT_BASE_URL
        ),
        model=(
            ai_config.get_model()
            or os.environ.get("OPENAI_MODEL")
            or ai_provider.DEFAULT_MODEL
        ),
    )
    status = provider.status()
    status["search_provider"] = (
        ai_config.get_search_provider()
        or os.environ.get("SEARCH_PROVIDER", "duckduckgo_html")
    )
    status["search_has_key"] = bool(
        ai_config.get_search_api_key() or os.environ.get("SEARCH_API_KEY")
    )
    status["bridge"] = describe()
    status["global_config"] = ai_config.get_status()
    return status


def ai_test(payload: dict[str, Any]) -> dict[str, Any]:
    provider = _provider(payload)
    if not provider.configured:
        return {
            "ok": False,
            "configured": False,
            "error": ai_provider.CONFIG_MISSING_MESSAGE,
        }
    try:
        response = provider.chat_json(
            "You are a connectivity tester. Reply with JSON only.",
            'Return exactly: {"ok": true, "echo": "connected"}',
        )
        return {
            "ok": True,
            "configured": True,
            "model": provider.model,
            "base_url": provider.base_url,
            "response": response,
        }
    except ai_provider.AIProviderError as exc:
        return {"ok": False, "configured": True, "error": str(exc)}


def search_test(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "跨境电商 最新趋势").strip()
    if not query:
        raise ValueError("query is required")
    config = _search_config(payload)
    try:
        results = data_tools.search_web(query, max_results=config["max_results"], config=config)
        return {"ok": True, "provider": config["provider"], "query": query, "results": results}
    except Exception as exc:  # noqa: BLE001 - report provider errors to the frontend
        return {"ok": False, "provider": config["provider"], "error": str(exc)}
