# 跨境电商智能选品决策系统

基于多源数据融合的跨境电商智能选品决策系统，面向中国国际大学生创新大赛（高教赛道·创意组）构建。

## 项目简介

帮助中小跨境卖家降低选品试错成本：聚合多平台公开数据，预测品类热度趋势，输出"卖什么、进多少、什么时候卖"的决策建议。

核心能力：

- 多源数据融合：搜索热度、畅销排名、出口金额、评论增长、竞争度
- 双模型预测：Prophet 基线 + LightGBM 进阶，输出未来 90 天销量预测区间
- 看板同时展示双模型预测曲线，推荐增长按每组合回测 MAPE 更优模型计算
- 选品推荐引擎：规则评分 + 预测增长加权，生成 Top N 推荐与中文推荐理由
- 贸易决策智能：关税 / 政策风险引擎、到岸成本测算、汇率敏感性、市场准入、知识产权、物流运价、多语言舆情、CBAM 前瞻与数据信用 / 供应链金融就绪评分（离线演示版）
- 完整贸易决策模拟工作台：方案预设、交易参数、风险假设、经营沙盘、目标市场对比与 AI 决策，由统一 FastAPI（`/api/catalog`、`/api/autofill`、`/api/analyze`）提供，统一使用全局 AI 接入配置
- 小助手：独立“小助手”页面，自然语言驱动系统查询、四脑/贸易分析、联网研究与后台任务；读操作直接执行，启动/停止任务、刷新政策、改权重、提交反馈、导出报告等写操作先确认；小助手完全复用顶部“AI 接入”的模型与搜索配置，分步 SSE 实时展示工具调用与来源
- 小助手控制台：提供工具目录、常用快捷指令与会话状态展示，运行中可一键停止，等待确认的写操作也可直接取消
- 数据分析：205,920 条周粒度数据全维度探索、品类 × 市场对比、季节性、相关性、模型误差与推荐构成
- 联网搜索：DuckDuckGo Lite 无 Key 直连，失败自动回退模拟结果；联网研究由全局 AI 接入统一驱动
- 全局 AI 接入：前端顶部“AI 接入”一次填写 API Key / Base URL / 模型 / 超时，四脑工作台、贸易决策工作台、小助手、完整看板、连接测试与“顶级 AI 对照”真实运行全部复用；各子系统不再自带 AI 接入面板；配置同时记忆在浏览器 localStorage 并同步到后端内存（不写 .env、不落盘）；“顶级 AI 对照”直接使用该配置中的 API 与模型完成评测，默认轻量跑 12 组合，可勾选“完整分批”跑 23760 格（旧 DeepSeek 网页版接口保留兼容，页面不再展示）
- 桌面端：`一键启动.bat` 启动统一后端后，在原生桌面窗口（Edge WebView2 / pywebview）中打开登录页（`/agent/login.html`，默认账号 `admin / 123456`），登录后进入 `/app`，不再跳转浏览器；设 `DEMO_OPEN_BROWSER=1` 或运行 `一键启动.bat /browser` 可回退到浏览器模式
- 每次启动 Demo 时先打开登录页，登录后进入 `/app`，再在后台刷新数据到当天（`scripts/run_daily_update.py`）、执行联网快照、刷新国外 / 国内 / 全球政策事件并参与 1980 组合重算、重建并同步看板与前端，完成后自动重启后端；政策雷达以官方原文优先，搜索/模拟结果仅作为候选，不进入决策链
- 数据源增强：Google Trends、平台榜单（Amazon / eBay GitHub 免费样例，Keepa/eBay 有 Key 可选）、海关出口（UN Comtrade / Open Trade Statistics）与 1688-cli 货源/供应商均已接入，默认离线回退；Amazon 抓取先查 robots，开源代码按 MIT/Apache/BSD/CC0 审计并登记；新增市场日报、HS Code/关税速查、卖前体检、供应商/客户尽调与证据闸
- 交互式看板：Streamlit 与 React 前端均含“数据分析”页签（图表 + 结论 + 证据清单）
- FastAPI 演示服务：将贸易决策、演示报告、推荐、政策事件与 HS Code 速查暴露为 JSON API

## 创新点

- 定位创新：从"选品工具"升级为跨境贸易决策智能（Trade Intelligence），覆盖选品、政策、成本、合规、IP、物流、舆情、CBAM 与融资。
- 决策创新：政策事件被量化为有效税率、最低关税与到岸成本利润冲击，输出可直接执行的应对建议。
- 方法创新：多源异构信号统一进入推荐评分与"置信度 × 权重"冲突裁决，保证决策可解释。
- 闭环创新：报告、Streamlit 看板与 FastAPI 服务共用同一套贸易决策计算，并配套 464 项自动化测试（pytest 实测）。
- 数据资产创新：设计用户授权数据回流机制，为运营诊断与远期供应链金融信用评分沉淀数据。
- 可验证性创新：建立与 ChatGPT / Claude / Gemini / DeepSeek 的统一对照组评测框架。

## 快速开始

也可进入 `发布与材料\完整Demo运行包` 双击唯一的 `一键启动.bat`：自动检查/安装依赖并启动统一后端，在原生桌面窗口（Edge WebView2 / pywebview）中打开登录页 `http://127.0.0.1:<端口>/agent/login.html`，登录后进入 `/app`；双击 `停止完整Demo.bat` 停止后端，桌面模式下关闭桌面窗口也会停止本次启动的后端。

如需指定端口，可运行 `一键启动.bat /port 8001`；未指定时会自动尝试 8000 / 8001 / 8010 / 8020。浏览器模式可用 `一键启动.bat /browser` 或设 `DEMO_OPEN_BROWSER=1`。

```powershell
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 2. 一键执行完整流水线（生成演示数据 -> 清洗 -> 训练 -> 评估 -> 推荐）
.venv\Scripts\python scripts\run_pipeline.py

# 2.5 使用本地真实数据集增强重训（Amazon/eBay/Shopee/Octaprice + Trends/榜单/海关/爬虫特征，并训练真实销量代理模型）
.venv\Scripts\python scripts\train_real_enhanced.py

# 3. 生成贸易决策演示报告（政策风险 + 到岸成本 + 市场准入 + 数据信用）
.venv\Scripts\python scripts\run_trade_demo.py

完整贸易决策模拟工作台已并入统一 FastAPI：`/api/catalog` 返回目录，`/api/autofill` 自动补全方案，`/api/analyze` 执行 AI 分析；前端统一入口为 `/app`。

  # 4. 启动可视化看板（React 前端由统一后端托管）
  # 已迁移到统一后端：.venv\Scripts\python scripts\run_api.py 后打开 http://127.0.0.1:8000/app
  # Streamlit 兼容入口：.venv\Scripts\streamlit run src\app\dashboard.py

# 5. 启动 FastAPI 演示服务（可选）
.venv\Scripts\python scripts\run_api.py
# 打开 http://127.0.0.1:8000/app 使用 React 前端；/dashboard 会重定向到 /app

# 5.1 桌面窗口模式（后端已启动时使用；一键启动会自动调用）
.venv\Scripts\python scripts\run_desktop_window.py --port 8000

# 6. 生成《数据分析报告》（统计 JSON + 13 张报告图表 PNG + Markdown）
.venv\Scripts\python scripts\run_data_analysis.py

# 7. 生成《数据分析报告》PDF
.venv\Scripts\python scripts\build_data_analysis_pdf.py

# 8. 每日联网数据更新（一键启动时会自动执行；刷新到当天、联网快照并重建 Demo）
.venv\Scripts\python scripts\run_daily_update.py
# 注册 Windows 计划任务，每天 08:00 自动执行
powershell -ExecutionPolicy Bypass -File scripts\install_daily_update_task.ps1

# 9. 联网连通性测试（真实搜索一次并输出报告）
.venv\Scripts\python scripts\test_online.py

# 9.1 政策雷达官方源近实时刷新 + 联网自检（每 6 小时任务可注册）
.venv\Scripts\python scripts\run_policy_watch.py
.venv\Scripts\python scripts\test_policy_sources.py
powershell -ExecutionPolicy Bypass -File scripts\install_policy_watch_task.ps1

# 10. 生成市场日报（可选推送到飞书/企业微信 webhook）
.venv\Scripts\python scripts\build_market_daily.py

# 11. 回填对照组真实结果（从 trends / rankings / crawler 快照聚合）
.venv\Scripts\python scripts\backfill_control_real.py

# 12. 跳过模型重训，仅刷新快照、市场日报与重建看板
.venv\Scripts\python scripts\run_daily_update.py --offline --skip-pipeline

# 13. 系统检查模式（环境 / 依赖 / 代码完善度 / 前后端连接）
.venv\Scripts\python scripts\run_env_check.py                # 快速档，默认四组全检
.venv\Scripts\python scripts\run_env_check.py --full         # 深度档：额外跑 pytest 全套 + 前端 typecheck
.venv\Scripts\python scripts\run_env_check.py --browser      # 加浏览器级渲染检查（需 playwright）
.venv\Scripts\python scripts\run_env_check.py --start-backend
# 报告落盘 tmp\check_report.json；退出码 0=全过 1=有失败 2=参数错误。
# 网页入口：系统控制台 -> 环境自检 页签（后端 GET /api/check，仅快速档）。
```

打开浏览器访问 `http://localhost:8501` 即可查看看板。
API 文档地址：`http://127.0.0.1:8000/docs`

可选：复制 `.env.example` 为根目录 `.env` 后按需修改——后端监听/跨域（`BACKEND_HOST`、`BACKEND_PORT`、`BACKEND_ALLOWED_ORIGINS`）与前端联通（`VITE_API_BASE`、`VITE_PROXY_TARGET`）由这一份文件同时驱动，后端启动（`scripts/run_api.py`）与前端构建/dev（Vite `envDir` 指向项目根）会自动读取；不建 `.env` 时全部使用默认值，行为与旧版一致。

## API 演示服务

```text
GET /api/health            服务健康检查
GET /api/data/status       每日数据更新与联网快照状态（数据截止日、来源数、Trends/榜单/市场日报状态）
GET /api/data/suppliers    货源/供应商尽调数据
GET /api/trade/decision    单组合贸易决策（政策、成本、合规、IP、物流、舆情、CBAM、数据信用、冲突裁决、卖前体检、HS 速查、尽调）
GET /api/trade/hs-code     HS Code / 关税速查
GET /api/trade/report      最近一次 1980 组合贸易决策演示报告
GET /api/recommendations   Top N 选品推荐
GET /api/policy/events     政策事件监控清单
POST /api/policy/refresh   政策雷达立即刷新（官方源优先，可选 include_search）
GET /api/search            联网数据（默认 crawler 爬虫，回退 DuckDuckGo/mock）
POST /api/search/research  联网研究模式（无需 AI Key，多查询搜索 + 来源汇总）
POST /api/search/test      联网测试端点（真实搜索并返回 ok/results/error）
GET/POST /api/ai/config    全局 AI 配置（脱敏读取 / 内存写入，不返回明文 Key）
POST /api/agent/chat       创建/续跑小助手会话（使用全局 AI 接入配置）
GET /api/agent/tools       小助手工具目录（读/写标记）
GET /api/agent/sessions/{id}/events  小助手 SSE 事件流（step/confirm/cancelled/final/error/done）
POST /api/agent/sessions/{id}/cancel  停止运行中的小助手 / 取消待确认操作
POST /api/agent/confirm    确认/取消 小助手写操作
GET /api/agent/sessions/{id}  恢复小助手会话快照
POST /api/control/run      页面内真实运行顶级 AI 对照（OpenAI 兼容模型；lite=12 组合默认，full=完整分批 23760 格）
GET /api/control/run/status  对照任务运行状态轮询
GET /api/control/web/setup  （旧版兼容，页面不再展示）DeepSeek 网页版对照准备信息
GET /api/control/train-data 下载对照组训练数据 CSV（旧版兼容用途）
POST /api/control/web/save  （旧版兼容，页面不再展示）保存 DeepSeek 网页版回复并评分
GET /api/data/status       每日数据更新与联网快照状态
```

也可直接启动内置 MCP Server（`scripts/run_mcp_server.py`），把推荐、贸易决策、
HS 速查与数据状态暴露为标准 MCP tools，供 Claude / Codex / Cursor 等客户端调用。

## 数据分析报告

- Markdown：`docs/数据分析报告.md`
- PDF：`output/pdf/数据分析报告.pdf`
- 图表：`docs/figures/`（22 张 PNG，含报告图表与界面素材）
- 统计 JSON：`output/analysis/summary_stats.json`

报告覆盖行业与市场数据（含来源表与“待核实”标记）、数据总览、探索性分析、模型评估、推荐结果和贸易决策情景，全部可由 `scripts/run_data_analysis.py` 复现。Streamlit 看板与单文件 HTML Demo 均新增“数据分析”页签与联网搜索面板。

## 项目结构

```text
src/
  config.py            全局配置（品类、市场、路径、模型参数）
  data/                数据采集、清洗、SQLite 存储、合成数据
  features/            特征工程（滞后、滚动、趋势、季节性）
  models/               Prophet 基线、LightGBM 进阶、推荐引擎、评估指标
  trade/                关税政策风险、贸易成本、合规准入、数据信用与融资就绪评估
  analysis/             数据分析统计、图表与《数据分析报告》生成
  api/                  FastAPI 演示服务
  app/dashboard.py     Streamlit 看板
  pipeline.py          端到端流水线
scripts/               一键脚本（生成数据/训练/完整流水线）
data/                  原始/清洗/演示数据
models/                模型产物、预测、推荐、评估报告
output/trade/          贸易决策演示报告与明细
docs/
  项目内容分类总览.md             项目内容分类与检索总览
  报告归档/                        建议报告与代码解析报告
tests/                 自动化测试
发布与材料/
   完整Demo运行包/                自包含运行包（唯一 `一键启动.bat`，缺 `.venv` 时自动创建）
  提交材料包_整合优化版_20260805/  大创申报/答辩/结题提交材料
```

## 数据说明

当前默认使用内置合成演示数据（2 年周粒度，132 个食品品类 × 15 大市场，1980 组合），完全离线可运行。
真实场景可扩展接入 Google Trends、Amazon 热销榜、海关出口数据与 Kaggle 公开数据集，
并在授权与脱敏前提下回流订单、履约、退款与回款数据，
采集框架位于 `src/data/collector.py`。

## 验证结果（合成演示数据）

- 基线模型 MAPE：约 3.4%
- 进阶模型 MAPE：约 2.3%（相对基线提升约 32%）
- 口径注：上述 MAPE 基于合成快照 + 轻量对照组，外部代表性待真实数据复核
- 推荐结果通过人工抽检与自动化测试验证
- 贸易决策演示：1980 组合生成政策风险、到岸成本、市场准入、IP 风险、物流运价、多语言舆情、CBAM 与融资就绪评分，可运行 `scripts\run_trade_demo.py` 复现

## 测试

```powershell
.venv\Scripts\python -m pytest tests -q
```
