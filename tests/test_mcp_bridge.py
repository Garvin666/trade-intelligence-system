"""MCP bridge smoke tests: plain tool functions and server registration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api import mcp_bridge  # noqa: E402


def test_plain_tool_functions_return_json() -> None:
    rec = json.loads(mcp_bridge.recommendations_tool(2))
    assert rec["ok"] is True
    assert len(rec["items"]) <= 2

    hs = json.loads(mcp_bridge.hs_code_tool("cn_changsha_mifen", "us"))
    assert hs["ok"] is True
    assert hs["hs_code"]["category"] == "cn_changsha_mifen"

    status = json.loads(mcp_bridge.data_status_tool())
    assert status["ok"] is True
    assert "data_as_of" in status["status"]


def test_mcp_server_registers_expected_tools() -> None:
    server = mcp_bridge.get_server()
    tools = server._tool_manager.list_tools()
    names = {tool.name for tool in tools}
    assert {
        "recommendations",
        "trade_decision",
        "hs_code",
        "data_status",
    } <= names
