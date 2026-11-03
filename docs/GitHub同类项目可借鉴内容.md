# GitHub 同类项目可借鉴内容整理

> 配套调研：`docs/GitHub同类项目调研.md`
> 整理日期：2026-08-13
> 用途：把 GitHub 上同类开源项目里可复用的做法，按「直接落地 / 数据源接入 / 预测增强 / 产品形态 / 优先级」整理，并映射到本项目现有模块。

## 1. 总体判断

本项目在「自包含 Python 全栈 + Prophet/LightGBM 双模型预测 + Top N 推荐 + 贸易决策 + 看板/API」组合上仍比较稀缺。同类项目值得借鉴的不是整套系统，而是五类「零件」：

1. 评分与决策框架：六维评分、Go/No-Go、三源交叉验证、防假数据。
2. 真实数据源接入：Google Trends、Keepa/Sorftime/卖家精灵、1688、TikTok Shop、海关数据。
3. 贸易情报与合规清单：HS Code/关税速查、政策日报、卖前体检。
4. 预测与分析增强：统计引擎 + LLM 解释分层、补充模型对照。
5. 产品形态：MCP/Skill 包装、批量报告导出、市场日报推送。

## 2. 可直接借鉴并落地到本项目的内容

| 借鉴点 | 来源仓库 | 本项目现状 | 建议落点 | 优先级 |
|---|---|---|---|---|
| 六维评分 + Go/No-Go 决策输出 | [xiaolu7586/ecommerce-product-scout-agent](https://github.com/xiaolu7586/ecommerce-product-scout-agent)、[markwaveio/cross-border-selection-kit](https://github.com/markwaveio/cross-border-selection-kit) | 已有推荐综合评分（`src/models/recommend.py`，权重在 `src/config.py`） | 增加「Go/No-Go + 决策理由」输出字段，看板与 API 同步展示 | P1 |
| 三源交叉验证与防假数据 | [markwaveio/cross-border-selection-kit](https://github.com/markwaveio/cross-border-selection-kit) | 已有 crawler 回退与来源标注（`src/data/crawler_signals.py`） | 增加来源冲突/关键词污染标记，报告标注数据可信度 | P1 |
| 卖前合规体检清单 | [JuneYaooo/launchfit-ai](https://github.com/JuneYaooo/launchfit-ai) | `src/trade/compliance.py` 已覆盖认证/准入清单 | 增加「卖前体检」汇总页：准入、标签、认证、物流、定价逐项打勾 | P1 |
| HS Code / 关税速查与风险预警 | [chnjames/tradehot-skill](https://github.com/chnjames/tradehot-skill) | `src/trade/policy.py` 已有政策事件与有效税率 | 补品类默认 HS 码映射表与速查输出，风险按品类/市场展示 | P0 |
| 每日市场监控与日报推送 | [hooper-lee/crosspulse](https://github.com/hooper-lee/crosspulse) | `scripts/run_daily_update.py` 已有每日联网快照 | 增加「市场日报」Markdown 模板与可选飞书/邮件推送 | P2 |
| 统计引擎 + LLM 解释分层 | [mageprince/magento2-mage-ai-predict](https://github.com/mageprince/magento2-mage-ai-predict) | 预测用 Prophet/LightGBM，报告用全局 AI | 报告显式区分「数值来自模型、解释来自 LLM」，避免 LLM 被当作数值预测 | P1 |
| 事实标注与反幻觉护栏 | [kangise/ecommerce-ai-skills](https://github.com/kangise/ecommerce-ai-skills)、[noique/cross-border-ecommerce-skills](https://github.com/noique/cross-border-ecommerce-skills) | 联网研究已标注来源与不确定信息 | 对照「证据闸」规则完善 AI 报告模板与测试：来源、日期、数据不足时明说 | P1 |
| 蓝海机会评分 | [DannylydST/sorftime-seller-agent](https://github.com/DannylydST/sorftime-seller-agent)、[cosjef/keepa_MCP](https://github.com/cosjef/keepa_MCP) | 推荐分含竞争度反向分 | 增加「蓝海机会分」列（需求强度 / 竞争烈度 / 利润空间）并进入推荐排序 | P2 |

## 3. 可接入的真实数据源（对标本项目「下一步」）

| 数据源 | 参考项目/工具 | 接入方式 | 本项目落点 | 成本与合规提示 |
|---|---|---|---|---|
| Google Trends | [markwaveio/cross-border-selection-kit](https://github.com/markwaveio/cross-border-selection-kit)、[faizazizan/google-trend-analyzer](https://github.com/faizazizan/google-trend-analyzer) | pytrends 或官方 Trends API，按品类关键词周度抓取 | `src/data/collector.py` 增加 Google Trends 采集器，替换/补充搜索热度 | 免费额度有限，需遵守服务条款，接入前核实 2026 年 API 政策 |
| Amazon 榜单/BSR/Listing | [cosjef/keepa_MCP](https://github.com/cosjef/keepa_MCP)、[liangdabiao/amazon-sorftime-research-MCP-skill](https://github.com/liangdabiao/amazon-sorftime-research-MCP-skill)、[Umair706/amazon-omniscient](https://github.com/Umair706/amazon-omniscient) | Keepa API / Sorftime MCP / 卖家精灵导出 / Amazon Best Sellers 页面 | `collector.py` 增加平台榜单适配，`output/data_status.json` 记录来源 | 商业 API 需订阅，页面抓取需遵守 robots/ToS |
| TikTok Shop 榜单 | [uni-infiniteai/clawec-agents](https://github.com/uni-infiniteai/clawec-agents)、[XiRenyyds/tiktok-shop-1688-product-analysis](https://github.com/XiRenyyds/tiktok-shop-1688-product-analysis) | 官方/第三方榜单 API 或 MCP | 同上，新增 TikTok 数据字段 | 多为商业 API，需先申请权限 |
| 1688 货源/供应商 | [superjack2050/1688-cli](https://github.com/superjack2050/1688-cli)、[xiaodong-l/amazon-1688-selector](https://github.com/xiaodong-l/amazon-1688-selector) | 1688 CLI 或网页检索 | `src/trade/cost.py` 采购成本与供应商字段 | CLI 只读部分可离线使用，登录/下单需账号授权 |
| 海关/贸易数据 | [chnjames/tradehot-skill](https://github.com/chnjames/tradehot-skill)、UN Comtrade/海关统计 | 公开下载或 API | 出口金额特征与外贸趋势模块 | 月度/季度更新，口径需与品类映射对齐 |
| 自有店铺/ERP 数据 | [zach22-1999/lingxing-mcp](https://github.com/zach22-1999/lingxing-mcp)、[lien0219/trademind-ai](https://github.com/lien0219/trademind-ai) | 领星 ERP MCP 只读 API | 用户数据回流与运营诊断 | 需卖家授权，只读访问，脱敏后使用 |
| 舆情/评论 | [liyushan12/demo](https://github.com/liyushan12/demo)、[Pasindunabesinghe/Automated-Dropshipping-Price-Sentiment-Analysis-Tool](https://github.com/Pasindunabesinghe/Automated-Dropshipping-Price-Sentiment-Analysis-Tool) | 评论抓取 + VADER/多语种情感 | `src/trade/sentiment.py` 接真实评论样本 | 遵守平台条款，不保存个人信息 |

## 4. 预测与分析增强（可做对照实验）

1. 统计 + LLM 混合：数值预测保持 Prophet/LightGBM，LLM 只做解释与建议，参考 [mageprince/magento2-mage-ai-predict](https://github.com/mageprince/magento2-mage-ai-predict)。本项目已有该基础，建议在报告模板中显式区分模型数值与 AI 解释。
2. 补充预测基线：ARIMA/SARIMA/XGBoost 可参照 [RahulNenavath/Olist-Ecommerce-TimeSeries-Forecasting](https://github.com/RahulNenavath/Olist-Ecommerce-TimeSeries-Forecasting) 加入对照组，验证 Prophet/LightGBM 的相对优势。
3. 是否值得卖的二分类：Random Forest 适合度预测参考 [thatzme-akbar/Machine-Learning-Based-Product-Prediction-System-for-Drop-shippers-](https://github.com/thatzme-akbar/Machine-Learning-Based-Product-Prediction-System-for-Drop-shippers-)，可作为推荐引擎之上的「值得卖 / 谨慎卖 / 不推荐」视图。
4. LSTM / 聚类 / 购物篮：LSTM、KMeans、Apriori、VADER 的组合见 [UnknowTT16/WeaveAI_Agent](https://github.com/UnknowTT16/WeaveAI_Agent)，属于扩展方向，不建议当前优先级。

## 5. 产品形态与交互（可扩展）

1. MCP/Skill 包装：同类热门项目多以 Claude Code / Codex / OpenClaw Skill 分发。本项目已有 FastAPI 与四脑引擎，可低成本提供 `/api/...` 决策接口 + 一份 `SKILL.md` / MCP 配置，让 AI 助手直接调用。
2. 批量报告导出：已有 PDF/Markdown 报告，可参照 [xiaolu7586/ecommerce-product-scout-agent](https://github.com/xiaolu7586/ecommerce-product-scout-agent) 增加 Excel 五表风格导出（执行摘要、原始数据、分析汇总、利润分析、机会排名）。
3. 市场日报推送：参照 [hooper-lee/crosspulse](https://github.com/hooper-lee/crosspulse)，把「每日联网快照」加工成市场日报并可选推送飞书/企业微信/邮件。

## 6. 落地优先级

P0（直接对应 AGENTS 中的下一步）：

1. Google Trends 真实接入。
2. 平台榜单数据源适配（Keepa / Sorftime / 公开榜单）。
3. HS Code / 关税速查表核对。

P1（完善决策质量与演示）：

4. Go/No-Go 与六维评分输出。
5. 卖前合规体检清单汇总。
6. 统计/LLM 解释分层与证据闸。

P2（扩展与差异化）：

7. MCP/Skill 包装。
8. 每日市场监控推送。
9. 供应商/客户尽调（OSINT）。
10. 对照组真实结果回填。

## 7. 风险与注意

1. License：优先参考 MIT/CC0 仓库（nexscope、zach22、hikari0511、kangise 等）；无 License 或 NOASSERTION 仓库只参考思路，不复制代码。
2. 数据合规：商业 API 订阅、平台服务条款、隐私与脱敏要求需在接入前确认。
3. 维护状态：部分仓库已停止更新（如 zhangzuomin、sidqian123、1huangyuhang），Star 数不代表代码质量。
4. 时间敏感性：GitHub 仓库与第三方 API 政策变化较快，正式接入前需重新核实。

## 8. 可写入答辩的表述

1. 本项目与 GitHub 同类项目相比，多数项目依赖商业数据 API 或仅提供 Skill 模板；本项目把「数据 → 预测 → 推荐 → 贸易决策 → 看板/API」做成一体的可运行系统。
2. 本项目吸收但不照搬业界做法：六维评分、Go/No-Go、三源交叉验证、合规体检、统计 + LLM 分层，均可在现有模块上验证。
3. 已接入 Google Trends（pytrends 加固）、平台榜单（Keepa/eBay/Amazon best-effort）与
   海关出口数据（UN Comtrade / Open Trade Statistics），并用真实数据回填对照组结果。

## 9. 落地状态（2026-08-13）

- 已实现：六维评分与 Go/No-Go 判定（`src/models/recommend.py`）、HS Code/关税速查（`src/trade/hs_code.py`）、卖前体检（`src/trade/preflight.py`）、供应商/客户尽调（`src/trade/osint.py`）、证据闸（`src/analysis/evidence.py`）。
- 已实现：Google Trends 加固（分批/重试/覆盖率）、平台榜单 Keepa/eBay/Amazon 适配器、
  海关出口采集器（Comtrade/OTS/mock 三级回退）、异常检测、用户数据 EDA 与 A/B 检验。
- 已登记：`third_party/PROVENANCE.md` 保存 License 审计结果；MIT/CC0 仓库许可证已随分发包同步。
- 已接入：`Nixtla/statsforecast`（Apache-2.0）作为第三预测基线；`modelcontextprotocol/python-sdk`（MIT）提供标准 MCP Server（推荐 / 贸易决策 / HS 速查 / 数据状态）。
- 待后续：用真实 Key 跑通 Keepa/Comtrade 付费接口，核实 HS6 码与剩余“待核实”行业条目。
