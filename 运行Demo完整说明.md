# 跨境电商智能选品决策系统 · 完整 Demo 运行说明

本文件夹是一个自包含的完整运行包：包含后端源码、前端构建产物、演示数据、训练好的模型、脚本、文档和测试。把整个文件夹发给别人后，对方只需双击 `一键启动.bat` 即可启动完整系统。

## 1. 运行环境

- 操作系统：Windows 10 / 11（本运行包按 Windows 一键启动设计）
- Python：3.10 或更高（推荐 3.12），需要能执行 `python` 或 `py -3`
- 网络：首次启动安装 Python 依赖、使用联网搜索 / AI 功能时需要网络
- 硬盘空间：本包约 200 MB，首次安装依赖后约需额外 1 GB

## 2. 一键启动（推荐）

进入本文件夹，双击：

```text
一键启动.bat
```

启动器会自动完成：

1. 检查项目内 `.venv`，不存在时自动创建本地虚拟环境。
2. 检查依赖，缺失时自动执行 `pip install -r requirements.txt`（首次约 5-10 分钟）。
3. 启动统一 FastAPI 后端，并在原生桌面窗口（Edge WebView2 / pywebview）中打开登录页：

```text
http://127.0.0.1:8000/agent/login.html
```

默认不再跳转浏览器；桌面窗口关闭时会停止本次启动的后端。使用 Demo 账号 `admin / 123456` 登录，登录成功后自动进入主应用 `/app`。

如果 8000 被占用，启动器会自动尝试 8001 / 8010 / 8020，并打开实际使用的端口。

如需使用浏览器模式，可设置环境变量 `DEMO_OPEN_BROWSER=1`，或运行 `一键启动.bat /browser`。

如需指定端口，可运行 `一键启动.bat /port 8001`；未指定时会自动尝试 8000 / 8001 / 8010 / 8020。

停止系统时双击：

```text
停止完整Demo.bat
```

## 3. 功能入口

系统打开后先显示登录页，使用 Demo 账号 `admin / 123456` 登录后进入 React 前端 `/app`，主要功能都在顶部导航和全局“AI 接入”栏中：

- 数据看板：预测、推荐、趋势、市场对比、数据更新状态
- 四脑工作台：多提示词四角色分析，支持上传 CSV / JSON 后仅基于用户数据生成
- 贸易决策工作台：方案自动填充、本地规则引擎决策、AI 决策解读、HS Code 速查、政策冲击与证据账本
- 联网研究 / 爬虫工作台：真实联网检索与来源汇总
- 数据分析：图表、结论、证据清单
- 顶级 AI 对照：使用全局 AI 接入配置运行轻量或完整对照评测
- MCP：`/mcp` 提供 Streamable HTTP 接口；`scripts/run_mcp_server.py` 可独立启动 stdio 入口

API 文档地址（后端启动后）：

```text
http://127.0.0.1:8000/docs
```

## 4. AI 接入（可选）

不配置 AI 也能完整演示，四脑分析和贸易决策会自动回退到内置规则引擎。想使用大模型分析时：

1. 在 `/app` 顶部打开“AI 接入”。
2. 选择厂商预设或自定义：预设覆盖 DeepSeek、OpenAI、Anthropic Claude、Google Gemini、阿里云百炼 Qwen、Kimi、智谱 GLM、火山方舟 Doubao、腾讯混元、MiniMax、Groq、Mistral、xAI、OpenRouter、Ollama 等国内 / 国际 / 本地服务；任何其他 OpenAI 兼容服务可直接填写 Base URL 与模型名。
3. 配置只保存在浏览器和当前后端内存中，不写入本包，也不会上传。

## 5. 离线打开

不需要后端时，可以直接双击：

```text
output\app-offline.html
output\dashboard-offline.html
```

这两个文件内嵌演示数据，可以浏览界面；联网搜索、AI 分析和 API 功能需要启动后端才能使用。

## 6. 手动启动与常用命令

```powershell
# 启动统一后端（含 REST API + React /app + MCP /mcp + 后台任务）
python scripts\run_api.py

# 离线刷新数据到当天，不重训模型、不联网
python scripts\run_daily_update.py --offline --skip-pipeline

# 运行完整流水线：数据 -> 清洗 -> 训练 -> 预测 -> 推荐
python scripts\run_pipeline.py

# 运行测试
python -m pytest tests -q
```

## 7. 本包包含 / 不包含

包含：

- 后端源码 `src/`、脚本 `scripts/`、测试 `tests/`
- 前端源码 `frontend/`（不含 `node_modules`）与构建产物 `output/app/`
- 演示数据 `data/demo/`、`data/processed/`、`data/control/`、`data/external/github/`
- 训练好的模型 `models/`
- 看板、离线单文件、每日快照、政策 / 趋势 / 榜单 / 贸易决策产物 `output/`
- 项目文档 `docs/`、商业计划书 PDF、第三方 License 审计 `third_party/`

不包含：

- `.env`（只带 `.env.example` 模板，避免泄露任何密钥）
- `.venv` 和 `node_modules`（启动器首次运行自动创建 / 安装）
- `data/external/hf/`（约 3.2 GB 的可选 Hugging Face 增强数据集，缺少时系统自动降级，核心功能不受影响）
- 运行期缓存 `tmp/`、`storage/`

如果接收者需要完整 Hugging Face 增强数据，可从原始项目复制 `data/external/hf/` 到本包的 `data/external/hf/`。

## 8. 常见问题

### 双击后提示找不到 Python

先安装 Python 3.10+ 并勾选“Add Python to PATH”，再重新双击 `一键启动.bat`。

### 端口全部被占用

关闭占用 8000 / 8001 / 8010 / 8020 的程序后重试；启动器会自动切换可用端口。

### 桌面窗口没有打开

请确认 Windows 已安装 Microsoft Edge WebView2 Runtime（Win10 / Win11 通常自带）。启动器在桌面窗口失败时会自动回退到默认浏览器；也可以手动打开启动器提示的地址，例如 `http://127.0.0.1:8000/agent/login.html`，或使用 `一键启动.bat /browser` 的浏览器模式。

### AI 分析不可用

确认是通过后端 `/app` 打开的页面，而不是直接打开的离线 HTML；并在顶部“AI 接入”中填写有效配置，或留空使用内置规则引擎。

### 首次安装依赖失败

检查网络和 pip 源后重试；也可以先手动执行：

```powershell
python -m pip install -r requirements.txt
```
