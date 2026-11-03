# 统一后端服务说明

这是跨境电商智能选品系统的一体化 FastAPI 后端程序，直接复用项目里已有的
数据处理产物（`data/processed/clean_data.csv`、`models/forecast.csv`、
`models/recommendations.csv`、`models/metrics.json`）和贸易决策模块，
并桥接 Demo 包里的四脑协同分析引擎。

## 启动

在项目根目录运行：

```powershell
python scripts\run_api.py
```

默认地址：

```text
API 文档：http://127.0.0.1:8000/docs
健康检查：http://127.0.0.1:8000/api/health
MCP Server：http://127.0.0.1:8000/mcp
最优 Demo：http://127.0.0.1:8000/dashboard
四脑工作台：http://127.0.0.1:8000/app（React 页面内，REST 接口见下表）
小助手：http://127.0.0.1:8000/app/agent
```

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BACKEND_HOST` | `127.0.0.1` | 监听地址，演示时可改为 `0.0.0.0` |
| `BACKEND_PORT` | `8000` | 服务端口 |
  | `BACKEND_ALLOWED_ORIGINS` | localhost 列表 | CORS 允许来源，多个用逗号分隔；生产按部署域名收紧 |
  | `BACKEND_API_KEY` | 空 | 可选简单鉴权；设置后 `/api/*` 需 `Authorization: Bearer <key>`（health/check 除外） |
| `BACKEND_RATE_LIMIT_REQUESTS` | `180` | 每个客户端限流窗口内最大请求数 |
| `BACKEND_RATE_LIMIT_WINDOW_SECONDS` | `60` | 限流窗口 |
| `BACKEND_MAX_BODY_BYTES` | `65536` | POST JSON 最大字节数 |
| `BACKEND_CACHE_TTL_SECONDS` | `15` | 只读聚合接口的短缓存时长 |
| `BACKEND_STATE_DB` | `data/backend_state.db` | 反馈与权重持久化 SQLite 路径 |
| `FOUR_BRAIN_AI` | `0` | 设为 `1` 默认启用四脑 AI 混合模式 |
| `BACKEND_POLICY_INTERVAL_SECONDS` | `0` | 进程内政策雷达自动刷新间隔（秒）；`0` 关闭（默认沿用 Windows 计划任务） |
| `BACKEND_AUTO_REFRESH` | `0` | 设为 `1` 时后端启动后立即在进程内触发一次每日数据更新（可选） |

## API 一览

### 基础数据

| 接口 | 说明 |
| --- | --- |
| `GET /api/health` | 健康检查与数据文件状态 |
| `GET /api/data/status` | 每日数据更新与联网快照状态（`data_as_of`、`online`、`next_update`） |
| `GET /api/data/status` | 额外返回 `crawl_quality`、`decision_data_ready` 与 `real_data` 爬取质量/真实证据状态 |
| `GET /api/categories` | 品类字典 |
| `GET /api/markets` | 市场字典 |
| `GET /api/models` | 模型字典 |
| `GET /api/dashboard-data` | 看板聚合数据（服务端聚合：双筛选=真实序列，否则按日期/模型均值聚合为图表序列，不再下发全量 55MB）；支持 `category`、`market`、`model`、`limit`（最近 N 期）过滤与 `meta=1`（轻量元信息，自检用） |
| `GET /api/examples` | 三套系统与立项报告的示例预设（一键填充示例） |
| `GET /api/anomalies` | 最新异常监测快照 |

### 看板与模型

| 接口 | 说明 |
| --- | --- |
| `GET /api/history` | 历史周度数据 |
| `GET /api/forecast` | 未来预测 |
| `GET /api/model-metrics` | 模型评估指标 |
| `GET /api/market-intel` | 看板「数据纵深」聚合：榜单/趋势/海关真实快照 + 特征口径风险/成本/评论/竞争 |
| `GET /api/summary` | 总体 KPI 摘要 |
| `GET /api/search/trends` | 搜索热度趋势 |
| `GET /api/reviews/summary` | 评论增长摘要 |
| `GET /api/trade/export-value` | 出口金额摘要 |
| `GET /api/competition/index` | 竞争度摘要 |
| `GET /api/platform/rankings` | 平台榜单式排名 |

### 决策与风控

| 接口 | 说明 |
| --- | --- |
| `GET /api/recommendations` | Top N 选品推荐，支持 `top`、`limit`、`min_score` |
| `GET /api/recommendations` | 默认过滤 No-Go，新增 `include_no_go=true` 可包含；缺真实数据时返回 503 `data_gap` |
| `GET /api/cost/metrics` | 经营成本估算 |
| `GET /api/risk/overview` | 经营风险总览 |
| `GET /api/market/compare` | 市场对比 |
| `GET /api/trade/decision` | 单组合贸易决策 |
| `GET /api/trade/decision` | 返回 `warnings`、`source_quality`、`clamped`；极端利润率被钳制 |
| `GET /api/trade/hs-codes` | HS6 速查表检索，支持 `q`、`category`、`market` |
| `GET /api/trade/report` | 最近一次贸易决策演示报告 |
| `GET /api/policy/events` | 政策事件监控清单 |
| `POST /api/policy/refresh` | 政策雷达立即刷新（官方源优先，可选 `include_search`） |

### 四脑与 AI

| 接口 | 说明 |
| --- | --- |
| `GET /api/four-brain` | 四脑规则引擎分析（查询参数） |
| `POST /api/four-brain` | 四脑分析，支持 `ai`、`research`、`tools` 参数 |
| `POST /api/four-brain/batch` | 批量四脑分析，输入 `items` 数组并返回汇总 |
| `POST /api/four-brain/launch-report` | 选品立项报告：模板 + 用户数据 -> AI Markdown 报告 |
| `POST /api/export/launch-report` | 立项报告 Markdown/PDF 导出下载（`format` 支持 `md` / `pdf`） |
| `GET /api/ai/status` | AI 接入状态 |
| `POST /api/ai/test` | 测试大模型连接 |
| `POST /api/search/test` | 测试搜索服务 |

### 小助手

| 接口 | 说明 |
| --- | --- |
| `POST /api/agent/chat` | 创建/续跑小助手会话；模型与搜索完全取自全局 AI 接入配置，忽略消息级 `api_key/base_url/model` |
| `GET /api/agent/tools` | 返回小助手可用工具目录（含读/写风险标记） |
| `GET /api/agent/sessions/{id}/events` | SSE 事件流：`step`、`confirm`、`cancelled`、`final`、`error`、`done` |
| `POST /api/agent/sessions/{id}/cancel` | 停止运行中的小助手，或取消等待确认的写操作 |
| `POST /api/agent/confirm` | 批准/拒绝待确认的写操作（任务、政策刷新、权重、反馈、导出） |
| `GET /api/agent/sessions/{id}` | 页面刷新后恢复会话快照 |

小助手遵循《全能系统操控AI Agent 正式提示词》的原则：内部数据优先、禁止幻觉、
无依据时如实说明数据不足；读工具直接执行，写工具必须由用户确认后才会真正执行。
运行中的小助手可通过 `/api/agent/sessions/{id}/cancel` 协作式停止，前端同步提供“停止”按钮。

AI 接入统一由主 Demo 顶部的全局配置管理：各子系统（四脑工作台、贸易决策 demo、看板）不再自带 AI 接入面板，统一读写 `/api/ai/config` 与 `trade_intel_ai_global`。

React 四脑工作台与批量分析请求均携带 `ai: true`：已配置全局 AI 时后端调用大模型生成四脑结论（单脑失败自动回退规则引擎），未配置时仍使用规则引擎 + 联网检索，不会报错中断。

### 反馈闭环

| 接口 | 说明 |
| --- | --- |
| `GET /api/scoring/weights` | 读取选品评分权重 |
| `POST /api/scoring/weights` | 更新评分权重，持久化到 SQLite |
| `GET /api/feedback` | 读取最近反馈 |
| `POST /api/feedback` | 提交反馈 |

### 后台任务与 MCP（单进程统一后端）

| 接口 | 说明 |
| --- | --- |
| `GET /api/jobs` | 后台任务注册表：daily_update / market_daily / control_run / policy_refresh 状态 |
| `POST /api/jobs/daily_update/start` | 触发每日数据更新（进程内；body 支持 `offline`、`skip_pipeline`、`skip_rebuild`、`date`、`provider`、`workers`） |
| `GET /api/jobs/daily_update` | 每日更新任务状态与进度 |
| `POST /api/jobs/daily_update/stop` | 协作式取消（阶段间生效） |
| `POST /api/jobs/market_daily/start` | 生成市场日报（body 支持 `date`、`push`） |
| `GET /api/jobs/market_daily` | 市场日报任务状态 |
| `/mcp` | MCP Server（Streamable HTTP），与 REST API 同进程同端口 |

刷新完成后后端通过缓存失效自动读到新数据，无需重启进程。MCP 端点默认启用 MCP SDK 的 DNS 重绑定防护，仅允许 `localhost` / `127.0.0.1` 访问。

## 页面路由

- `/app`：React 前端（统一入口）
- `/dashboard`：重定向到 `/app`
- `/output/dashboard.html`：数据看板（外置数据）
- `/output/dashboard-data.json`：看板数据

## 每日联网更新

后端只读产物来自 `scripts/run_daily_update.py` 的每日刷新。更新会：

1. 每次启动 Demo 时把合成数据刷新到当天并重跑模型管线；
2. 对 15 个品类 × 市场组合执行联网检索，快照写入 `output/daily_snapshots/YYYY-MM-DD.json`；
3. 政策雷达按官方原文优先拉取中国政府网 / 美国联邦公报 / 欧盟 / GOV.UK，写入 `output/policy/latest.json`；
4. 写入 `output/data_status.json`，供 `/api/health`、`/api/data/status` 与看板展示；
5. 重建 `output/dashboard.html`、四脑 `dashboard-data.json` 与主 Demo 并同步分发副本。

`--offline` 可跳过真实网络请求；Windows 计划任务见 `scripts/install_daily_update_task.ps1`。
政策雷达独立近实时任务见 `scripts/run_policy_watch.py` 与 `scripts/install_policy_watch_task.ps1`。

## 联网测试

```powershell
python scripts\test_online.py                     # 直连搜索自检
python scripts\test_online.py --base-url http://127.0.0.1:8000  # 经后端测试
python scripts\test_online.py --allow-fallback   # 回退也视为通过
```

真实联网成功（结果含可访问链接）退出码为 0，离线/回退为 1。看板“联网搜索”面板、
四脑工作台也提供“联网测试”按钮，统一调用 `POST /api/search/test`。

## 测试

```powershell
python -m pytest tests -q
```
