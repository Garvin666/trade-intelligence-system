"""Run the MCP server exposing the cross-border selection decision tools."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.mcp_bridge import get_server  # noqa: E402


def main() -> int:
    server = get_server()
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
