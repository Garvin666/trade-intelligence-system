# CONTEXT.md — 项目域词汇与关键约束

> 项目：跨境电商智能选品决策系统（面向中小跨境卖家的选品与贸易决策智能）。
> 完整运行说明见 `AGENTS.md`；本文只记录域词汇与关键约束，供设计与代码统一用语。

## 域词汇表

| 词汇 | 含义 | 代码位置/约定 |
|---|---|---|
| 品类 category | 132 个食品 SKU（12 大类：谷物主食/肉禽蛋奶/海鲜水产/果蔬生鲜/中式零食/坚果果干/调味酱料/茶饮酒水/烘焙甜点/方便速食/滋补保健/素食清真），唯一事实源 `src/config.py` 的 `CATEGORIES` | `CATEGORY_CATALOG` 含名称/关键词/HS4/关税基线 |
| 市场 market | 15 个目标市场（us/eu/sea/...），见 `MARKETS` | `MARKET_FACTOR` 0.42~1.00 |
| 组合 combo | 品类 × 市场 = 1980 组合（132×15） | `len(CATEGORIES)*len(MARKETS)` |
| 周粒度数据 | 132×15×104 周 = 205,920 行（不含表头） | `data/processed/clean_data.csv` 205,921 行含表头 |
| 四脑引擎 | 多提示词个性化输入 + 四脑独立分报告 + 综合输出 | `src/four_brain/engine.py` |
| 小助手 | 工具驱动的系统操作助手：内部数据优先、禁止幻觉、读工具直行、写工具确认 | `src/system_agent/` |
| 贸易决策 | 政策/成本/合规/IP/物流/舆情/CBAM/融资/冲突裁决 | `src/trade/decision.py::build_trade_decision` |
| 政策事件 PolicyEvent | 关税/成本调整/宏观事件；`categories` 空 = 市场级事件 | `src/trade/policy.py`；`KNOW_EVENT_CATEGORIES` 兜底标注 |
| 市场级税率事件 | categories 空但有数值且 verified 的事件（de minimis、EU VAT、国内退税），参与税率重算 | `evaluate_policy` 中 `market_level_rate_or_cost` |
| 证据闸 | 报告结论必须附证据与来源标注，mock 不进证据分 | `fallback_used` 标志体系 |
| 统一后端 | 单进程 FastAPI：REST `/api/*` + React `/app` + MCP `/mcp` + 后台任务 `/api/jobs/*` | `scripts/run_api.py` |
| 桌面端 | 一键启动默认用 pywebview + Edge WebView2 打开登录页，不再跳浏览器；关闭窗口停止本次启动的后端 | `scripts/run_desktop_window.py`；`start_complete_demo.ps1 -Desktop` |
| 版本指纹 | 品类数（132）+ `/openapi.json` 必需端点（`/api/market-intel`）用于检测旧代码进程 | `start_complete_demo.ps1::Test-VersionMatches` |

## 关键约束

- 品类数/组合数/行数以 `src/config.py` 的 `CATEGORIES`/`MARKETS`/`WEEKS_HISTORY` 为唯一事实源，docs 不得写死旧口径（46/690/71,760）。
- 政策事件：无 `categories` 标注的事件仅作市场级提醒，不参与品类税率重算；有数值的市场级税率事件保留参与。
- 演示分发：`发布与材料/` 下两个分发包（完整Demo运行包 + 嵌套子包）须与根目录同步 src/docs/scripts/tests。
- 汇率以 `src/trade/cost.py::DEFAULT_FX_RATE`（7.15）为唯一来源，前端不得硬编码（7.1 已清除）。
- 安全底线：`.env` 不入库、导出 payload 脱敏、路径遍历防护、上传行数上限（EDA_MAX_ROWS=200,000）。
