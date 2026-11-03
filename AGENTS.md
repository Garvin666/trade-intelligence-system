# 跨境电商智能选品决策系统

一句话定位：面向中小跨境卖家的选品与贸易决策智能（Trade Intelligence），用多源数据和 AI 输出"卖什么、怎么卖、卖到哪、是否值得卖"。

## 怎么跑起来

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\run_pipeline.py      # 数据 -> 清洗 -> 训练 -> 预测 -> 推荐
.venv\Scripts\python scripts\train_real_enhanced.py  # 真实特征增强重训 + 真实销量代理模型
.venv\Scripts\python scripts\run_trade_demo.py     # 贸易决策演示报告
.venv\Scripts\python scripts\run_data_analysis.py  # 数据分析报告 + 13 张图表
.venv\Scripts\python scripts\build_data_analysis_pdf.py
.venv\Scripts\python scripts\run_api.py           # 统一后端（REST API + React 前端 /app + MCP /mcp + 后台任务 /api/jobs），默认 http://127.0.0.1:8000
.venv\Scripts\python scripts\run_desktop_window.py --port 8000  # 原生桌面窗口（WebView2，需后端已启动；一键启动会自动调用）
.venv\Scripts\streamlit run src\app\dashboard.py  # Streamlit 兼容入口（可选，React 前端 /app 为主）
.venv\Scripts\python scripts\run_mcp_server.py    # MCP server 独立 stdio 入口（HTTP 方式已并入 run_api.py 的 /mcp）
.venv\Scripts\python scripts\run_daily_update.py  # 每日联网更新：数据刷新到当天 + 联网快照 + 重建同步
.venv\Scripts\python scripts\run_daily_update.py --offline --skip-pipeline  # 仅刷新快照/市场日报并重建，不重训
.venv\Scripts\python scripts\run_policy_watch.py  # 政策雷达：官方源近实时刷新（gov.cn/Federal Register/欧盟/GOV.UK）
.venv\Scripts\python scripts\test_policy_sources.py  # 政策官方源联网自检
powershell -ExecutionPolicy Bypass -File scripts\install_policy_watch_task.ps1  # 注册每 6 小时政策雷达任务
.venv\Scripts\python scripts\build_market_daily.py  # 生成市场日报（可选推送 webhook）
.venv\Scripts\python scripts\backfill_control_real.py  # 从 trends/rankings/crawler 回填对照组真实结果
.venv\Scripts\python scripts\build_hf_real.py        # 构建 Hugging Face 公开数据集信号层（本地数据，无需联网；产物 output/control/hf_signals.json + hf_real_results.csv）
.venv\Scripts\python scripts\build_datasets_index.py  # 训练数据集总索引：先跑 build_datasets_inventory.py 再跑本脚本，产出 data/DATASETS_INDEX.md + data/datasets_manifest.json
.venv\Scripts\python scripts\test_online.py       # 联网连通性测试：真实搜索一次并输出报告
.venv\Scripts\python scripts\control_group.py run --global  # 顶级 AI 对照：使用 OPENAI_API_KEY/OPENAI_BASE_URL/OPENAI_MODEL 或 --api-key/--base-url/--model-id 运行；--mode lite（默认 12 组合）/ --mode full（完整分批 23760 格）
powershell -ExecutionPolicy Bypass -File scripts\install_daily_update_task.ps1  # 注册 Windows 每日任务
```

测试：`.venv\Scripts\python -m pytest -p no:cacheprovider --basetemp=tmp\pytest-check tests -q`（当前 550 passed / 0 skipped；四脑分析已由子进程隔离 + 看门狗守护（`run_api.py --watchdog`），无平台跳过）

一键启动：根目录、`发布与材料\完整Demo运行包` 统一只保留 `一键启动.bat` 一个入口：自动检查依赖（没有 `.venv` 时先创建本地虚拟环境）、启动 FastAPI 后端并在原生桌面窗口（Edge WebView2 / pywebview）打开登录页 `http://127.0.0.1:<端口>/agent/login.html`（默认账号 `admin / 123456`），登录后进入 React 前端 `/app`，不再跳转浏览器；如需浏览器模式，设 `DEMO_OPEN_BROWSER=1` 或运行 `一键启动.bat /browser`，可用 `/port 8001` 指定端口。双击 `停止完整Demo.bat` 停止后端；桌面模式下关闭窗口也会停止本次启动的后端。

## 技术栈

Python 3.12：pandas / numpy / Prophet / LightGBM / Streamlit / FastAPI / pywebview / plotly / reportlab / matplotlib；前端以 React（`frontend/`，构建到 `output/app`）为主，数据看板用 ECharts；桌面端使用 pywebview + Edge WebView2；四脑引擎在 `src/four_brain`。

## 目录与约定

- `src/config.py`：品类、市场、路径、模型与推荐权重；默认测试产品在四脑引擎 `DEFAULT_PAYLOAD`（现为"老干妈辣椒酱 laoganma chili sauce"，食品口径，定义于 `src/four_brain/engine.py`）。
- `src/data`、`src/features`、`src/models`、`src/trade`、`src/api`、`src/app/dashboard.py`、`src/analysis`：数据、特征、模型、贸易决策、API、看板、数据分析报告。
- `scripts/`：一键脚本；`tests/`：根测试 464 项通过（0 skipped）。
- `docs/` 与 `发布与材料\提交材料包_整合优化版_20260805`、`发布与材料\完整Demo运行包`：文档与分发副本，改动后需同步。
- `third_party/`：GitHub 同类开源项目 License 审计与来源记录（`PROVENANCE.md`），随分发包同步。
- `发布与材料/`：归拢两个对外分发包；前端统一由 `frontend/` 与 `output/app` 提供，四脑引擎、贸易自动填充与看板数据均由根目录 `src/` 提供。
- 联网数据默认 `crawler`（Wikimedia 公开爬虫，无需 Key），失败回退 `duckduckgo_html` 再回退 mock 并标注；浏览器直连模式先实时爬虫检索，再通过"DeepSeek 网页版生成报告"打开免费对话并复制提示词；上传用户数据文件（CSV/JSON）可只基于用户数据生成并关闭联网。
- 每次启动 Demo（`start_complete_demo.ps1` / `一键启动.bat`）都会先启动统一后端并立即打开登录页，登录后进入 `/app`，再把合成数据刷新到当天（进程内后台任务 `/api/jobs/daily_update`，复用 `scripts/run_daily_update.py` 逻辑）：执行 1980 组联网检索（132 品类 × 15 市场）写入 `output/daily_snapshots/`，同时刷新 Google Trends、平台榜单、政策雷达（官方原文优先）与市场日报，产出 `output/data_status.json`，再重建 `dashboard.html`、`dashboard-data.json` 与 React 前端并同步分发副本，刷新完成后由后端自动失效缓存加载新数据（无需重启）；`-WaitForRefresh` 可切回前台等待，`-OfflineData` 跳过联网，`-SkipDataRefresh` 跳过刷新。

## 当前状态和下一步

端到端演示已完成：双模型预测、Top N 推荐、贸易决策、数据分析报告、联网搜索、用户数据文件、四角色视角报告、中英切换。四脑工作台已升级为“多提示词个性化输入 + 四脑独立详细分报告 + 按提示词综合输出 + 可选图表”，并支持上传 CSV/JSON 后仅基于用户数据生成、关闭联网搜索干扰；默认测试产品已换成一套覆盖 132 个食品 SKU（12 大类）的食品产品集，联网研究代理会输出中文总结并标注来源与不确定信息。AI 接入已统一收敛到主 Demo 顶部全局“AI 接入”（`/api/ai/config` + `trade_intel_ai_global`），四脑工作台、贸易决策 demo 与看板不再自带 AI 接入面板；“顶级 AI 对照”统一使用“AI 接入”中的 API 与模型完成评测（旧 `/api/control/web/*` + `control_group.py web` 保留兼容，页面不再展示），默认轻量跑 12 组合、可勾选“完整分批”跑 23760 格。数据更新链路已接入每日联网快照、Google Trends 适配器、平台榜单适配器与市场日报：每次启动 Demo 时 `run_daily_update.py` 都会刷新数据到当天、落盘联网来源与 `data_status.json`，并在看板/API 展示“数据更新至”、“每日联网快照”、Trends/榜单/市场日报状态。真实数据已按双轨接入：Google Trends 加固（分批/重试/覆盖率），平台榜单默认 Amazon / eBay GitHub 免费样例（Keepa/eBay 有 Key 可选升级），海关出口使用 UN Comtrade 免 Key 预览 + Open Trade Statistics 回退；行业事实已回填商务部/海关总署/欧盟立法原文，仅剩 Temu AI 监测与 SaaS 趋势条目标“待核实”。推荐引擎新增六维评分与 Go/No-Go 判定，贸易决策新增 HS Code 速查、卖前体检与供应商/客户尽调，报告统一带证据闸；用户数据新增自动 EDA、A/B 检验与异常检测，对照组新增配对显著性。下一步：可选接入 Keepa/Comtrade Key 升级数据，核实 HS6 码与剩余“待核实”行业条目，并用真实数据回填对照组结果。

主 Demo 已移除顶部全局配置栏；内部页面（看板 / 四脑 / 贸易 / 方案 / 系统等）统一进入 `trade-console` 清关账本设计系统（首页同源深海蓝底 + 青蓝 / 琥珀 / 翠绿数据色 + 纸面账板 + 等宽数据标签），首页保持原有沉浸式航海场景不变，品类 / 市场 / 模型等上下文仍由 `useTradeIntelStore` 持久化并在页面间联动。

在线版已启用 GZip + 外置看板数据（`output/dashboard.html` + `output/dashboard-data.json`），React 前端统一入口为 `/app`，`/dashboard` 重定向到 `/app`；离线单文件前端为 `output/app-offline.html`。已接入 StatsForecast 第三预测基线与 MCP Server。后端已整合为单进程统一后端：`scripts/run_api.py` 同时提供 REST API、React 前端、MCP Server（`/mcp`，Streamable HTTP）与受管后台任务（`/api/jobs/*`：每日数据更新、市场日报、对照组评测、政策雷达），数据刷新完成后通过缓存失效自动加载新数据、无需重启进程；MCP 独立 stdio 入口（`scripts/run_mcp_server.py`）与 Windows 计划任务保留兼容。
