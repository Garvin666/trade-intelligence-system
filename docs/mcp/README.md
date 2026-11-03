# MCP / Skill 接入说明

## 方式一：直接调用 HTTP API

后端默认运行在 `http://127.0.0.1:8000`，AI 助手可通过 HTTP 工具调用：

```http
GET /api/recommendations?top=10
GET /api/trade/decision?category=pet&market=us&unit_price_usd=22&procurement_cost_cny=55
GET /api/trade/hs-code?category=pet&market=us
GET /api/search/trends?category=pet&market=us
```

## 方式二：MCP Server（已内置）

项目已内置轻量 MCP Server，把推荐、贸易决策、HS 速查与数据状态暴露为
标准 MCP tools，支持 Claude / Codex / Cursor 等 MCP 客户端直接调用。

启动 MCP Server：

```powershell
.venv\Scripts\python scripts\run_mcp_server.py
```

客户端配置示例（stdio transport）：

```json
{
  "mcpServers": {
    "cross-border-selection": {
      "command": "python",
      "args": ["scripts/run_mcp_server.py"],
      "cwd": "E:\\大创"
    }
  }
}
```

可用 MCP tools：

- `recommendations(top, min_score)`：Top N 选品推荐。
- `trade_decision(category, market, unit_price_usd, procurement_cost_cny)`：单组合贸易决策。
- `hs_code(category, market)`：品类默认 HS6 码与基础税率。
- `data_status()`：每日数据更新与联网快照状态。

MCP Server 直接复用项目内 Python 服务，不依赖 HTTP 后端端口；若只想调用
已有 FastAPI 接口，仍可使用方式一的 HTTP 工具集。
