"""MCP server bridge exposing the project's decision APIs as MCP tools.

The bridge uses plain Python functions so the project remains testable even
when the ``mcp`` SDK is not installed; the FastMCP server is only registered
when the SDK is available.
"""

from __future__ import annotations

import json
from typing import Any

from src.api import services
from src.trade.decision import build_trade_decision
from src.trade.hs_code import lookup_hs


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def recommendations_tool(top: int = 10, min_score: float | None = None) -> str:
    filters: dict[str, str | None] = {"top": str(max(1, min(int(top), 100)))}
    if min_score is not None:
        filters["min_score"] = str(min_score)
    try:
        return _dumps({"ok": True, "items": services.recommendations(filters)})
    except Exception as exc:  # noqa: BLE001
        return _dumps({"ok": False, "error": str(exc)})


def trade_decision_tool(
    category: str,
    market: str,
    unit_price_usd: float = 30.0,
    procurement_cost_cny: float = 75.0,
) -> str:
    try:
        result = build_trade_decision(
            category=str(category),
            market=str(market),
            unit_price_usd=float(unit_price_usd),
            procurement_cost_cny=float(procurement_cost_cny),
        )
        return _dumps({"ok": True, "decision": result})
    except Exception as exc:  # noqa: BLE001
        return _dumps({"ok": False, "error": str(exc)})


def hs_code_tool(category: str, market: str = "us") -> str:
    try:
        return _dumps({"ok": True, "hs_code": lookup_hs(str(category), str(market))})
    except Exception as exc:  # noqa: BLE001
        return _dumps({"ok": False, "error": str(exc)})


def data_status_tool() -> str:
    try:
        return _dumps({"ok": True, "status": services.data_status()})
    except Exception as exc:  # noqa: BLE001
        return _dumps({"ok": False, "error": str(exc)})


_mcp = None
try:
    from mcp.server.mcpserver import MCPServer

    _mcp = MCPServer("cross-border-selection", version="1.0.0")

    @_mcp.tool()
    def recommendations(top: int = 10, min_score: float | None = None) -> str:
        """Top N 选品推荐（综合评分 + Go/No-Go）。"""
        return recommendations_tool(top=top, min_score=min_score)

    @_mcp.tool()
    def trade_decision(
        category: str,
        market: str,
        unit_price_usd: float = 30.0,
        procurement_cost_cny: float = 75.0,
    ) -> str:
        """单组合完整贸易决策（政策、成本、合规、IP、物流、舆情）。"""
        return trade_decision_tool(
            category=category,
            market=market,
            unit_price_usd=unit_price_usd,
            procurement_cost_cny=procurement_cost_cny,
        )

    @_mcp.tool()
    def hs_code(category: str, market: str = "us") -> str:
        """品类默认 HS6 码与基础税率速查。"""
        return hs_code_tool(category, market)

    @_mcp.tool()
    def data_status() -> str:
        """每日数据更新与联网快照状态。"""
        return data_status_tool()

except ImportError:  # pragma: no cover - optional dependency
    _mcp = None


def get_server():
    if _mcp is None:
        raise RuntimeError(
            "mcp SDK is not installed; run: pip install mcp"
        )
    return _mcp


_mcp_session_manager = None


def available() -> bool:
    """Whether the MCP SDK is importable and the server was registered."""
    return _mcp is not None


def get_session_manager():
    """Return the MCP StreamableHTTPSessionManager for lifespan integration.

    The first call also builds the Streamable HTTP transport (which creates
    and stores the manager on the low-level server). The parent FastAPI app
    must enter ``get_session_manager().run()`` in its own lifespan for the
    mounted /mcp endpoint to serve requests.
    """
    global _mcp_session_manager
    if _mcp is None:
        raise RuntimeError("mcp SDK is not installed; run: pip install mcp")
    if _mcp_session_manager is None:
        _mcp.streamable_http_app(streamable_http_path="/")
        _mcp_session_manager = _mcp.session_manager
    return _mcp_session_manager


def get_streamable_http_app():
    """Return the raw MCP ASGI handler (no lifespan) for mounting under /mcp."""
    return get_session_manager().asgi_app


__all__ = [
    "available",
    "data_status_tool",
    "get_server",
    "get_session_manager",
    "get_streamable_http_app",
    "hs_code_tool",
    "recommendations_tool",
    "trade_decision_tool",
]
