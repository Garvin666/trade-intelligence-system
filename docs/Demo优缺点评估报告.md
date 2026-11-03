# 跨境电商智能选品决策系统 · Demo 优缺点评估报告

> 评估对象：`跨境电商智能选品决策系统`（面向中国国际大学生创新大赛·高教赛道·创意组）
> 评估方式：先静态评审（源码、测试、配置、文档与构建产物核查），随后按用户要求以用户身份实际运行一遍（端到端 pipeline、贸易决策演示、FastAPI、pytest），实测结果见「四、实测运行记录」。凡实际运行的结论均以实测为准。
> 评估视角：区分"大赛创意组 Demo"与"可用于真实选品决策的产品"两个维度，避免以产品标准苛责 Demo、也避免以 Demo 完成度掩盖真实性短板。

---

## 一、项目概览

一句话定位：面向中小跨境卖家的选品与贸易决策智能，用多源数据 + AI 输出"卖什么、怎么卖、卖到哪、是否值得卖"。

- **技术栈**：Python 3.12；pandas / numpy / scikit-learn / Prophet / LightGBM / StatsForecast / Streamlit / FastAPI / plotly / reportlab / matplotlib；前端为单文件 HTML + ECharts。
- **代码规模**：142 个 Python 源文件（约 1.64MB 源码）；`src/` 下分层为 config / data / features / models / trade / analysis / api / app / control。
- **测试规模**：41 个测试文件、约 302 个测试函数（`pytest`）。
- **数据规模**：66 大品类 × 15 大市场 = 990 个组合；2 年周粒度历史数据（104 周），未来 90 天预测。
- **能力面**：数据采集/清洗 → 特征工程 → 三模型预测（Prophet + LightGBM + StatsForecast）→ 六维评分推荐 → 贸易决策（关税/政策、到岸成本、汇率、合规准入、IP、物流、多语言舆情、CBAM、数据信用/融资就绪）。
- **交付形态**：Streamlit 看板、单文件 HTML Demo、FastAPI 服务、MCP Server，另有每日联网更新、政策雷达、市场日报等配套脚本。

---

## 二、做得好的地方

### 2.1 工程完整度与可复现性

- **端到端流水线清晰**：`src/pipeline.py` 将"生成数据 → 清洗 → 训练 → 评估 → 预测 → 推荐"串成可一键执行的流程，`scripts/run_pipeline.py` 一条命令复现全链路。
- **确定性可复现**：固定随机种子（`RANDOM_SEED = 42`），评估指标、预测、推荐结果全部落盘（`models/metrics.json`、`forecast.csv`、`recommendations.csv`），同样的输入得到同样的输出。
- **三层预测基线**：Prophet 基线、LightGBM 进阶、StatsForecast 第三基线并存，`_save_metrics` 统一汇总三方指标，便于横向对比而非只报单一模型。

### 2.2 代码组织与可测试性

- **模块边界清晰**：`src/config.py` 集中管理品类、市场、路径、模型参数与推荐权重；`data/`、`features/`、`models/`、`trade/`、`analysis/` 职责单一，命名规范，中英文映射表集中维护。
- **测试覆盖广**：302 项测试覆盖 API（`test_api.py` 574 行、`test_ai_config.py` 649 行）、政策源与刷新（`test_policy_sources.py`、`test_policy_refresh.py`）、真实数据适配器（`test_real_data_adapters.py`）、推荐六维判定（`test_recommend_six_dimension.py`）、爬虫/供应商/证据闸等，远超一般课程项目。

### 2.3 鲁棒性与兜底设计

- **逐级降级 + 显式标注**：联网数据默认 `crawler`（Wikimedia 公开爬虫，无需 Key）→ 失败回退 `duckduckgo_html` → 再回退 `mock` 并标注 `fallback_used`；Google Trends、平台榜单、海关出口均"无 Key 可跑、有 Key 升级、失败回退 mock"。
- **降级意图被明确注释**：源码中大量 `except Exception: # noqa: BLE001 - ...` 均注释了降级原因（如"单个源失败不阻断整体""联网失败统一回退 mock"），而非静默吞异常。
- **抗幻觉的诚实机制**：政策与行业事实优先官方原文，搜索/模拟结果仅作候选、不进入决策链；无法核实条目标"待核实"；报告带证据闸；`docs/项目优势报告.md` 坦承"幻觉候选仍需人工复核"。

### 2.4 真实数据接入与开源合规

- **双轨真实数据**：Google Trends（分批/重试/覆盖率加固）、平台榜单（默认 Amazon / eBay GitHub 免费样例，Keepa/eBay 有 Key 可选）、海关出口（UN Comtrade 免 Key 预览 + Open Trade Statistics 回退）、政策雷达（gov.cn / Federal Register / 欧盟 / GOV.UK 官方源近实时刷新）。
- **开源 License 审计**：`third_party/PROVENANCE.md` 登记了 GitHub 同类开源项目（MIT/Apache/BSD/CC0）的来源与许可，随分发包同步，合规意识良好。

### 2.5 安全与密钥治理

- **无硬编码密钥**：全仓未发现明文 API Key；密钥统一从环境变量（`KEEPA_API_KEY`、`EBAY_APP_ID`、`COMTRADE_SUBSCRIPTION_KEY` 等）读取。
- **AI Key 不落盘**：全局 AI 接入的 Key 仅存于后端内存 + 浏览器 localStorage，读写走 `/api/ai/config` 并脱敏返回，不写 `.env`。
- **`.env.example` 规范**：清晰列出后端/API/AI/真实数据源/政策雷达/供应商的全部可配置项与默认值，含代理、超时、限流等。

### 2.6 交付、文档与可验证性

- **一键启动与自包含分发**：唯一入口 `一键启动.bat` 自动检查依赖并拉起统一后端；`发布与材料\完整Demo运行包` 提供自包含运行包；`停止完整Demo.bat` 停后端。
- **文档体系齐全**：商业计划书、技术文档、数据字典、数据分析报告、竞品分析、用户调研、实施计划、答辩稿与问答准备等一应俱全。
- **对照组评测框架**：与 ChatGPT / Claude / Gemini / DeepSeek 统一跑同一份训练/隐藏测试集，用配对显著性检验量化差距（`src/control/benchmark.py` 1410 行），比口头宣称"更好"有说服力。

---

## 三、做得不好的地方 / 待改进

> 按对项目可信度与可持续性的影响程度排序。

### 3.1 【核心】验证基础仍是合成数据

`src/data/synthetic.py` 用"趋势 + 年季节性 + 品类峰值脉冲 + 市场波动 + 随机噪声"等公式直接生成销量，搜索热度、畅销排名、评论增长等信号均由销量函数导出。因此：

- README 中"基线 MAPE 约 3.4%、进阶约 2.3%（相对提升约 32%）"本质上是在拟合**系统自己编造的数据**，不能证明对真实市场有任何预测能力；在合成数据上追求 2% 的 MAPE 几乎没有业务意义。
- 推荐引擎输出的"增长/蓝海/建议小批量试单"等结论，其可信度完全受制于虚构的输入分布。

> 这是本项目从"Demo"走向"真实选品决策产品"最大的鸿沟。README 与《项目优势报告》均已诚实标注"演示数据是合成快照、不代表真实市场"，此点值得肯定，但它仍是评审者（尤其投资/答辩评委）必然追问的第一软肋。

### 3.2 【核心】贸易决策为硬编码启发式

`src/trade/policy.py` 自述为"离线演示版"，关税基础为硬编码的 `BASE_TARIFF_RATE`（66 品类 × 15 市场约 690 个手写税率），政策冲击用启发式比例 `HEURISTIC_IMPACT_RATIO = {high:0.10, medium:0.05, low:0.02}` 与 `HEURISTIC_CAP = 0.25` 估算，而非真实关税/政策数据计算。其他贸易模块（合规成本、IP 风险、舆情、CBAM、融资就绪）同样为规则/打分引擎。

- 优点：离线可完整演示、可解释、可测试。
- 缺点：数值并非真实海关/法规口径，一旦用户误当作真实决策依据会产生误导；演示效果越"像真的"，此风险越高。

### 3.3 前端产物与生成脚本

- 数据看板产物为 `output/dashboard.html`（外置数据）与 `output/dashboard-offline.html`（离线单文件）；React 前端在线构建到 `output/app`，离线单文件为 `output/app-offline.html`。
- 数据看板由 `scripts/build_html_dashboard.py` 生成，React 前端源码在 `frontend/`，较旧单文件 Demo 的可维护性与首屏加载均有改善。

### 3.4 零 Git 提交、无版本历史

经核查：仓库存在 `.git` 目录，但 `git log` 无任何提交、`git status` 全部文件处于 untracked 状态。这意味着整个项目没有任何版本历史与变更可追溯性，无法复盘演进过程，也无法回滚；对答辩中"项目是怎么一步步做出来的"这一问题缺乏过程证据支撑。

### 3.5 依赖不可完全复现

`requirements.txt` 中 `numpy`/`pandas`/`lightgbm`/`pytrends` 等少数包精确锁定版本，但 `scikit-learn`、`streamlit`、`fastapi`、`reportlab`、`pytest` 等大量使用 `>=` 宽松约束，且无 lock 文件（无 `poetry.lock` / `requirements.lock` / `pyproject.toml`）。换环境重装可能因依赖漂移导致行为不一致。

### 3.6 分发副本多重嵌套、存在同步漂移风险

`发布与材料` 下存在多层重复副本（`完整Demo运行包` 内再套一层 `完整Demo运行包`），`data/`、`scripts/`、`src/` 在根目录、`Demo运行包/`、`发布与材料/完整Demo运行包/` 多处拷贝，`output/*.html` 多份。`AGENTS.md` 也明确要求"改动后需同步"。人工同步极易漏改，长期会造成副本漂移、演示版本不一致。

### 3.7 真实数据未闭环、待核实条目未清

- Keepa / UN Comtrade 付费接口为可选升级，默认免费方案无需 Key，尚未用真实数据验证。
- HS6 码与部分行业事实条目仍标"待核实"。
- 对照组完整"11,880 格"模式虽已实现，但真实结果尚未回填，目前仅有轻量 12 组合 / 144 格的结果（《项目优势报告》已坦承此点）。

### 3.8 测试口径表述不一、存在环境脆弱用例

- 对测试数量的描述多处不一致：README 写"300+ 项自动化测试"、AGENTS.md 写"当前 297 项"与"根测试 305 项"，而本评估实测约 302 个测试函数。
- AGENTS.md 自陈"四脑图表用例在部分 Windows 环境下可能触发原生访问冲突"，说明存在环境相关的不稳定用例。

### 3.9 大量魔法数与手调超参硬编码

`src/config.py` 中 LightGBM 超参被硬编码为调参产物的精确值（如 `learning_rate: 0.034484844346092995`、`feature_fraction: 0.5924198110299715` 等），推荐引擎的维度映射斜率（`50 + growth * 1.2`、`50 + search_trend * 1.5`、`50 + review * 3.0`）、六维权重（0.25/0.20/0.20/0.20/0.10/0.05）均以字面量散落代码中。调参来源与取值过程不透明，复现与论证困难。

### 3.10 次要：API Key 存于浏览器 localStorage

全局 AI Key 记忆在浏览器 `localStorage`（README 明确表述）。相对"仅内存、不落盘"的后端策略，浏览器端持久化存在 XSS 泄露面的次要风险；对纯本地演示影响有限，但若要对外部署需改为服务端会话或提示用户选择。

---

## 四、实测运行记录（2026-08-14 补充）

> 运行环境：Windows 11 + PowerShell，项目自带 `.venv`（Python 3.12.4），代码页 936（GBK）。以下为以用户身份实际执行的结果，均带退出码或可复现命令。

### 4.1 端到端 pipeline：成功，但耗时过长

`scripts\run_pipeline.py` 完整跑通，**退出码 0，总耗时约 2062 秒（约 34 分钟）**。实测输出：

| 项 | 实测值 |
| --- | --- |
| 数据规模 | 102,960 行（= 66 品类 × 15 市场 × 104 周） |
| 预测记录 | 178,200 行（990 组合 × 90 天 × 2 模型） |
| 推荐记录 | 690 行 |
| 基线 MAPE（Prophet）均值 | **3.361%** |
| 进阶 MAPE（LightGBM）均值 | **2.304%** |
| StatsForecast 基线均值 | **9.652%**（未被对外材料重点宣传） |

- ✅ 优势实锤：pipeline 确定性可复现，MAPE 数字与 README 宣称（约 3.4% / 2.3%）一致，说明"指标落盘 + 固定种子"确实可复现。
- ⚠️ 问题 1：**耗时 34 分钟**，主因是 Prophet 对 990 个组合逐条串行拟合（每条约 1 秒）；期间 cmdstanpy 的 INFO 日志（"Chain [1] start/done processing"）以每组合 2 行刷屏，把真正的汇总输出淹没在数千行日志里。
- ⚠️ 问题 2：**README 数字笔误**——README 曾写"717120 条周粒度数据"，与实测 102,960 行存在 10 倍出入，现已统一为 66 品类 × 15 市场 × 104 周 = 102,960 行；`run_pipeline.py` 打印"推荐 Top10：990 行"仍是变量名与语义不符的标签小误。
- ⚠️ 问题 3：StatsForecast 第三基线 MAPE 高达 9.65%，明显劣于另两个模型，说明"第三基线"目前仅是接入、尚未调优。

### 4.2 贸易决策演示：成功且轻量

`scripts\run_trade_demo.py` 退出码 0，**约 2 秒**跑完 990 组合：高风险 132 / 中风险 0，平均利润率 32.28%，平均融资就绪分 77.5。规则引擎路径健康、速度快。

### 4.3 FastAPI：可用，但默认环境全部真实数据离线

启动 `scripts\run_api.py`（端口 8010）后，`/api/health`、`/api/data/status`、`/api/trade/hs-code`、`/api/trade/decision`、`/api/policy/events` 均正常返回合法 JSON。

实测 `data_status` 显示：Google Trends `real=0 / mock=46`、平台榜单四家全部 `skipped(离线)`、海关 `mock`（"离线模式，未发起真实请求"）、供应商 `mock`、政策官方源 gov.cn / Federal Register / 欧盟 / GOV.UK 全部 `offline`。**即：不配 Key 的默认环境下，所有"真实数据"都处于 mock/离线回退态**，与 3.7 节的"真实数据未闭环"结论一致。

### 4.4 实测新发现的问题（静态评审未覆盖到的）

1. **【重要】Go/No-Go 判定实际"永远不 Go"**：对 `models/recommendations.csv` 全量统计，990 组合的 verdict 分布为 **Go = 0、No-Go = 513、Conditional = 177**。原因是证据维度 `dimension_evidence` 恒约 34.8（无真实证据数据），低于 `conditional_dimension_min=40` 的"一票否决"阈值，导致 `_verdict` 永远触发 No-Go。更严重的是**排序用的 `score` 与判定用的 `verdict` 自相矛盾**：按 score 排名的 Top 10 推荐**全部是 No-Go**（Top 20 中 14 个 No-Go），系统把"不建议备货"的项当成"Top 推荐"展示给用户，推荐结果不可信。

2. **【重要】贸易决策可输出极端值**：`/api/trade/decision?category=pet&market=us&unit_price_usd=25&procurement_cost_cny=60` 返回 `effective_tariff_rate=1.26`（126%）与 `margin_pct=-351.51`。根因是 `src/trade/policy.py` 的 `evaluate_policy` 用硬编码政策事件的 `rate_ad_valorem`（如美国 de minimis 2026 关税按 120% 叠加）与启发式 `HEURISTIC_IMPACT_RATIO` 估算，对部分组合会产生明显不合实际的数值。

3. **【重要】pytest 原生访问冲突复现**：`pytest -q` 跑到约第 243 个用例（约 70%+27）时**进程崩溃**，退出码 -1、无 "N passed" 汇总行、无 Python traceback（典型 Windows 原生访问冲突）。这复现了 AGENTS.md 已记载的"四脑图表用例在部分 Windows 环境触发原生访问冲突"，意味着"300+ 项测试通过"在本机无法完整复现。

4. **【次要】CLI 控制台中文乱码**：`scripts/run_pipeline.py`、`run_trade_demo.py` 的 `print` 输出在 Windows 控制台（GBK）下正常，但经重定向/UTF-8 终端捕获时中文变为乱码（`stdout.encoding=gbk`）。已确认**存储的 JSON/API 数据本身为正确 UTF-8**（`data_status.json` 读回正常），故仅是 CLI 脚本未统一 `sys.stdout` 编码所致，不影响浏览器/API 展示。

5. **【观察】一键启动后台任务会与手动 pipeline 竞争**：运行期间另观察到 `run_daily_update.py`、`pytest`、多份 `run_api.py` 进程并存（且 `.venv` 与 `anaconda3` 两套解释器同时存在），说明一键启动脚本的后台数据刷新/重建与手动运行 pipeline 会并发争用 CPU 与 `models/`、`output/` 文件，存在竞态与漂移风险（呼应 3.6 节）。

---

## 五、总体评价

| 维度 | 评价 |
| --- | --- |
| 作为**大赛创意组 Demo** | **完成度很高**。功能面极广（选品→预测→推荐→贸易决策→数据看板→对照评测），工程结构清晰、可复现、测试充分、文档齐全，且具备罕见的"诚实标注 + 证据闸 + 兜底链"意识，演示性与可解释性俱佳。 |
| 作为**可真实使用的选品决策产品** | **尚不成立**。核心预测建立在合成数据上，贸易决策为硬编码启发式（实测可输出 126% 关税、-351% 利润），推荐引擎 Go/No-Go 判定恒不"Go"且与排序自相矛盾，真实数据接口未用 Key 跑通、待核实条目未清、对照组完整结果未回填。 |
| 作为**可持续迭代的工程** | **偏弱**。零 Git 历史、无依赖锁定、巨型单文件 HTML、多重分发副本，都会显著抬高后续维护与协作成本；实测 pipeline 单次需约 34 分钟、pytest 在本机原生崩溃，迭代反馈慢。 |

一句话结论：**这是一个"演示系统"意义上的优秀作品、但"决策系统"意义上的未验证原型**。优势集中在广度、工程规范与诚实性；短板集中在真实性闭环、推荐逻辑自洽性与工程可持续性。实测进一步确认：pipeline/API/贸易演示都能跑通且可复现，但"推荐结果不可信（Top 全 No-Go）""贸易决策可出极端值""测试套件本机崩溃"三个问题，是答辩与后续评审时最可能被追问的硬伤。

---

## 六、改进建议（按优先级）

- **P0 · 补一个真实数据闭环做验证**：选 1–2 个品类接入可获得的真实数据（如 Amazon 榜单/Google Trends/Comtrade 免 Key 预览），跑通真实训练与验证并重算 MAPE，用真实误差替换合成数据上的 2.3%/3.4%，这是把"演示"变成"证据"的关键一步。
- **P0 · 修复推荐引擎 Go/No-Go 失效**：实测 990 组合 Go=0，证据维度恒 ~34.8 低于 40 的一票否决线，且按 `score` 排名的 Top 推荐清一色 No-Go。需重新校准六维阈值/证据维度缺省分，并让排序与判定口径一致（例如排序改用 `six_dimension_score` 或过滤 No-Go 后再出 Top N），否则"推荐"输出自相矛盾。
- **P0 · 政策/关税替换硬编码**：至少对主要市场接入真实关税税率（或明确可溯源的数据文件），并在界面上把"演示口径估算值"与"官方实测值"显式区分，杜绝误导；同时为 `rate_ad_valorem` 等硬编码政策事件加合理的上限/校验，避免出现 126% 关税、-351% 利润率的极端输出。
- **P1 · 建立版本控制与依赖锁定**：补首次 commit 并建立提交规范；生成依赖 lock（如 `pip-compile` / `poetry.lock`），使环境可复现。
- **P1 · 拆解巨型前端**：将 52MB 单文件 HTML 与 5779 行生成脚本重构为模块化模板 + 外置静态资源，提升可维护性与加载性能。
- **P1 · 收敛分发副本**：确立"单一事实源"，用脚本自动打包分发副本而非手工拷贝，消除嵌套重复与漂移。
- **P2 · 统一测试口径并修复脆弱用例**：统一对外口径的测试数量，定位并隔离 Windows 下原生访问冲突的图表用例（如标记 skip / 改用无原生依赖的渲染方式）。
- **P2 · 清空"待核实"清单**：核验 HS6 码与剩余行业事实条目，回填对照组完整 11,880 格结果，使所有对外材料都有据可查。
