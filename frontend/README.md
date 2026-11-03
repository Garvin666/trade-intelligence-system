# 远帆智品前端

React + Vite + TypeScript + Tailwind CSS 的液态玻璃拟态前端，面向答辩演示与真实选品决策工作台两种场景。

## 常用命令

```powershell
pnpm install          # 安装依赖
pnpm dev              # 本地开发（/api 与 /output 代理到 127.0.0.1:8000）
pnpm typecheck        # TypeScript 检查
pnpm lint             # ESLint
pnpm test             # Vitest 单测
pnpm build:online     # 在线构建 -> frontend/dist
pnpm build:offline    # 离线单文件构建 -> frontend/dist-offline
pnpm sync             # 同步到 output/app 与 output/app-offline.html
pnpm build            # 在线 + 离线 + 同步
```

## 环境配置（前后端联通）

前后端共享根目录一份 `.env`（模板见 `.env.example`，已被 gitignore，不提交真实密钥）。
Vite 的 `envDir` 指向项目根（见 `vite.config.ts`），仅 `VITE_*` 前缀变量会注入客户端代码：

| 变量 | 作用 | 默认 |
| --- | --- | --- |
| `VITE_API_BASE` | 前端请求后端 API 的完整 URL；**留空 = 同源**（生产 `/app` 部署由后端同源托管构建产物，保持留空） | 空 |
| `VITE_PROXY_TARGET` | `pnpm dev`（5173）时 `/api` 与 `/output` 的代理目标；前后端分离开发时指向后端地址 | `http://127.0.0.1:8000` |

两种运行模式：

- **同源部署（生产/演示，默认）**：后端 `scripts/run_api.py` 在 `/app` 同源托管 `output/app`，`VITE_API_BASE` 留空即可，无需代理、无跨域。
- **分离开发（Vite 5173 + FastAPI 8000）**：`pnpm dev` 启动 Vite，`/api`、`/output` 自动代理到 `VITE_PROXY_TARGET`（后端需先启动）；若把 `VITE_API_BASE` 设为后端完整地址（如 `http://127.0.0.1:8000`）则可直连后端（后端 `BACKEND_ALLOWED_ORIGINS` 默认 `*` 已放开跨域）。

后端 `BACKEND_HOST/BACKEND_PORT/BACKEND_ALLOWED_ORIGINS` 等由 `scripts/run_api.py` 与 `src/config.py` 从同一份根 `.env` 读取（python-dotenv，缺失时回退默认值）。

## 目录约定

- `src/app`：应用入口、Provider、路由。
- `src/pages`：路由级页面，懒加载。
- `src/widgets`：跨页面编排组件。
- `src/features`：业务功能与 use case。
- `src/entities`：领域模型与筛选逻辑。
- `src/shared`：UI、图表、API、品牌、样式、工具，只放可复用无业务规则的能力。

依赖只能从上层指向下层：`pages -> widgets -> features -> entities -> shared`，模块对外只暴露 `index` 级别的公共 API。

## 数据模式

- 在线模式：优先请求 FastAPI `/api/*`，通过 `/api/dashboard-data` 读取看板数据。
- 离线模式：构建时把 `output/dashboard-data.json` 内嵌为 `window.__TRADE_INTEL_OFFLINE__`，双击 `output/app-offline.html` 即可运行。
- 在线入口：FastAPI `/app`，客户端路由由后端 catch-all 回退到 `index.html`。
