# GitHub 同类项目调研

> 调研对象：本项目「跨境电商智能选品决策系统」
> 调研日期：2026-08-13
> 数据来源：GitHub Search API、各仓库 README 与仓库元数据（Star 数、最后更新时间会随时间变化）
> 可借鉴内容整理：[docs/GitHub同类项目可借鉴内容.md](docs/GitHub同类项目可借鉴内容.md)

## 一句话结论

GitHub 上没有找到与本项目完全 1:1 的开源系统，但存在大量高度相关的分领域项目，按相似度可归为四类：

1. 跨境电商 AI 选品 / 产品调研（最接近的赛道）
2. 贸易情报 / 市场监控 / 合规决策
3. 电商需求 / 销售预测与数据分析
4. 数据采集 / 货源 / 平台能力（支撑层）

同类项目的主流形态是「AI Agent / Skills + 第三方数据 API（Sorftime、Keepa、卖家精灵、1688 等）」。本项目「自包含 Python 全栈 + Prophet/LightGBM 双模型预测 + Top N 推荐 + 贸易决策 + 看板/API」的组合仍比较稀缺。

## 检索方法

- 使用 GitHub 仓库搜索并按 Stars 降序取前 N，关键词包括：`cross-border e-commerce product selection`、`跨境电商 选品`、`dropshipping product research`、`amazon product research`、`trade intelligence`、`ecommerce demand forecasting`、`ecommerce product trend analysis`、`选品 系统`、`product selection system amazon`、`marketplace intelligence ecommerce`、`tiktok shop product research`，以及 topic 检索（`cross-border-ecommerce`、`product-research`、`dropshipping` 等）。
- 入选仓库均通过 GitHub API 与 README 二次核对；下表中「最近更新」为仓库最后 push 时间。

## 第一类：跨境电商 AI 选品 / 产品调研

| 仓库 | Stars | 语言 | 最近更新 | 定位与相似点 |
|---|---|---|---|---|
| [liangdabiao/amazon-sorftime-research-MCP-skill](https://github.com/liangdabiao/amazon-sorftime-research-MCP-skill) | 699 | Python | 2026-07-08 | 亚马逊竞品分析与品类选品：Sorftime/Sif/卖家精灵 MCP 驱动的 Listing 穿透、品类选品、关键词、评论分析、产品调研；选品分析链路与本项目最贴近，但依赖商业数据 MCP，无自有预测与贸易决策。 |
| [nexscope-ai/eCommerce-Skills](https://github.com/nexscope-ai/eCommerce-Skills) | 675 | Python | 2026-07-23 | 157 个跨平台电商 Agent Skills（Amazon/Shopify/eBay/Etsy/TikTok Shop/Walmart），覆盖产品调研、营销自动化、供应链与业务分析；Skill 合集，非单一大系统。 |
| [zach22-1999/amazon-skills](https://github.com/zach22-1999/amazon-skills) | 150 | Python | 2026-07-18 | 亚马逊卖家实战 Skill：选品验证、Listing 审计、广告搜索词分析、CVR 诊断；可执行、有代码，但偏单点技能。 |
| [afadtc/afa-dtc-skills](https://github.com/afadtc/afa-dtc-skills) | 141 | Python | 2026-05-10 | 独立站 / DTC 的 30 个增长顾问技能，含诊断、选品、品牌、广告、CRO；偏运营顾问而非数据决策系统。 |
| [hikari0511/awesome-amazon-ec-skills](https://github.com/hikari0511/awesome-amazon-ec-skills) | 110 | - | 2026-05-19 | 亚马逊跨境 AI Agent Skills 精选合集：选品→竞品→Listing→视觉→广告→评论，含 1688 上游；索引型仓库。 |
| [xiaolu7586/ecommerce-product-scout-agent](https://github.com/xiaolu7586/ecommerce-product-scout-agent) | 50 | TypeScript | 2026-03-20 | 海购选品助手：Amazon/TikTok Shop/eBay/Shopee 多平台采集、利润模型、六维评分、Go/No-Go 决策、Excel 五表报告；与本项目选品推荐链路最像，无 Prophet/LightGBM 预测与贸易决策。 |
| [nexscope-ai/nexscope-ecommerce-skills](https://github.com/nexscope-ai/nexscope-ecommerce-skills) | 42 | Python | 2026-07-31 | 99 个电商情报 Skill：产品调研、关键词、竞品、定价监控、专利/商标筛查、市场趋势；与本项目多项能力重叠。 |
| [yyf2002-oos/merchant-agent](https://github.com/yyf2002-oos/merchant-agent) | 27 | Python | 2026-07-18 | AI 电商全流程自动化：选品→上架→客服→运营分析→货源筛选，DeepSeek + Ollama ReAct Agent。 |
| [UnknowTT16/WeaveAI_Agent](https://github.com/UnknowTT16/WeaveAI_Agent) | 26 | JavaScript | 2025-11-01 | 机会洞察→数据验证（LSTM/KMeans/Apriori/VADER）→行动计划→HTML 报告；前后端一体，覆盖预测与情感分析。 |
| [Umair706/amazon-omniscient](https://github.com/Umair706/amazon-omniscient) | 17 | Python | 2026-03-19 | 开源 Amazon FBA 选品引擎（对标 Helium10/Jungle Scout）：BSR 追踪、竞品分析、利润计算、52 周财务预测、1688 供货匹配。 |
| [DannylydST/sorftime-seller-agent](https://github.com/DannylydST/sorftime-seller-agent) | 15 | Python | 2026-08-13 | 6 平台（Amazon/Walmart/TikTok/Shopee/TEMU/1688）marketplace intelligence，80+ MCP 工具、Hidden Profit Index。 |
| [xiaodong-l/amazon-1688-selector](https://github.com/xiaodong-l/amazon-1688-selector) | 14 | HTML | 2026-03-27 | 亚马逊选品系统：数据采集 + 趋势分析 + 1688 供应商匹配，Python 3.12、29 个测试。 |
| [markwaveio/cross-border-selection-kit](https://github.com/markwaveio/cross-border-selection-kit) | 8 | Python | 2026-07-03 | Amazon 信号 → Ad Library/Trends/1688 三源交叉验证 → 六维打分 → 可视化报告，强调防假数据。 |
| [sidqian123/e_commerce_helper](https://github.com/sidqian123/e_commerce_helper) | 8 | Python | 2024-03-28 | XPath 抓取 Amazon/eBay 热销数据 → AI 可视化 → 选品决策；已停止更新。 |
| [YENTERTAINR01/product_selection_analysis](https://github.com/YENTERTAINR01/product_selection_analysis) | 4 | Python | 2025-06-18 | 多市场规则映射、选品优先级排序、自动化配置管理。 |
| [1huangyuhang/Cross-border-Product-Selection-System](https://github.com/1huangyuhang/Cross-border-Product-Selection-System) | 0 | Python | 2026-03-23 | 全栈跨境电商选品系统：数据分析、竞品监控、销量预测、智能推荐；概念最接近本项目但无维护、无文档。 |
| [liyushan12/demo](https://github.com/liyushan12/demo) | 0 | Python | 2026-07-03 | 多 Agent 选品分析：亚马逊评论爬取、情感分析、痛点提取、选品报告。 |

## 第二类：贸易情报 / 市场监控 / 合规决策

| 仓库 | Stars | 语言 | 最近更新 | 定位与相似点 |
|---|---|---|---|---|
| [zhangzuomin/-AI-Trade-Intelligence-Decision-Platform](https://github.com/zhangzuomin/-AI-Trade-Intelligence-Decision-Platform) | 43 | Shell | 2025-10-09 | AI 贸易情报决策平台，名称与定位和本项目「Trade Intelligence」最接近；README 简略，无活跃维护。 |
| [kangise/ecommerce-ai-skills](https://github.com/kangise/ecommerce-ai-skills) | 44 | Python | 2026-08-11 | 跨境电商 AI 知识底座：69 篇三语指南、878 个结构化提示词、领域本体、MCP 服务；事实带日期、CI 核验、反幻觉护栏。 |
| [noique/cross-border-ecommerce-skills](https://github.com/noique/cross-border-ecommerce-skills) | 23 | Python | 2026-08-01 | 58 个跨境/DTC AI 技能：品牌、市场调研、选品、Listing、广告、财务资本、EU 入市等。 |
| [lien0219/trademind-ai](https://github.com/lien0219/trademind-ai) | 16 | Go | 2026-08-13 | 开源 AI 跨境电商运营平台：商品采集→草稿→AI 内容优化→刊登→订单与库存协同。 |
| [chnjames/tradehot-skill](https://github.com/chnjames/tradehot-skill) | 12 | Python | 2026-06-17 | 外贸情报 Skill：日报、平台政策、HS Code、关税速查、风险预警；直接对标本项目贸易决策与政策事件模块。 |
| [JuneYaooo/launchfit-ai](https://github.com/JuneYaooo/launchfit-ai) | 12 | Python | 2026-06-18 | 出海体检官：卖前合规、目标市场基准、本地化、文档、标签、定价、物流体检；对标贸易合规与准入。 |
| [hooper-lee/crosspulse](https://github.com/hooper-lee/crosspulse) | 11 | Python | 2026-06-06 | 跨境电商大盘监控：每日抓取平台政策/爆品趋势/类目机会 → AI 日报 → 飞书推送；对标每日联网快照。 |
| [wo9230/osint-agent](https://github.com/wo9230/osint-agent) | 8 | Python | 2026-07-07 | 外贸防诈骗、客户背调、供应商尽调、B2B 情报；与数据信用和融资尽调模块相关。 |

## 第三类：电商需求 / 销售预测与数据分析

| 仓库 | Stars | 语言 | 最近更新 | 定位与相似点 |
|---|---|---|---|---|
| [thatzme-akbar/Machine-Learning-Based-Product-Prediction-System-for-Drop-shippers-](https://github.com/thatzme-akbar/Machine-Learning-Based-Product-Prediction-System-for-Drop-shippers-) | 16 | Jupyter Notebook | 2024-03-10 | 用 Random Forest 预测产品是否适合 dropshipping；课程项目，未维护。 |
| [mageprince/magento2-mage-ai-predict](https://github.com/mageprince/magento2-mage-ai-predict) | 7 | PHP | 2026-07-22 | Magento 2 预测补货：统计引擎 + AI 解释，输出次月需求、补货时间、呆滞库存。 |
| [MakazhanAlpamys/Kaspi-Analytics-Platform](https://github.com/MakazhanAlpamys/Kaspi-Analytics-Platform) | 6 | TypeScript | 2026-02-14 | 21 万+ 商品的价格与需求洞察 + ML 预测，Next.js + FastAPI。 |
| [RahulNenavath/Olist-Ecommerce-TimeSeries-Forecasting](https://github.com/RahulNenavath/Olist-Ecommerce-TimeSeries-Forecasting) | 2 | Jupyter Notebook | 2025-01-06 | 电商日销量/需求预测：ARIMA、SARIMA、SARIMAX、XGBoost。 |
| [DeepakSawalka/Amazon-FBA-Product-Search-Analysis](https://github.com/DeepakSawalka/Amazon-FBA-Product-Search-Analysis) | 4 | Jupyter Notebook | 2023-02-26 | 用 ML 做 FBA 选品推荐；课程/作业性质。 |

## 第四类：数据采集 / 货源 / 平台能力

| 仓库 | Stars | 语言 | 最近更新 | 定位与相似点 |
|---|---|---|---|---|
| [sudheer-ranga/aliexpress-product-scraper](https://github.com/sudheer-ranga/aliexpress-product-scraper) | 314 | JavaScript | 2026-05-08 | AliExpress 商品/评论/变体/物流 JSON 抓取，可作数据采集参考。 |
| [superjack2050/1688-cli](https://github.com/superjack2050/1688-cli) | 56 | TypeScript | 2026-06-27 | 1688 找货、供应商调研、询价、下单 CLI，面向 AI Agent；对标货源与供应商数据接入。 |
| [cosjef/keepa_MCP](https://github.com/cosjef/keepa_MCP) | 31 | TypeScript | 2026-02-11 | Keepa Amazon 数据 MCP：销售速度、库存周转、缺货风险、季节性、机会评分。 |
| [uni-infiniteai/clawec-agents](https://github.com/uni-infiniteai/clawec-agents) | 25 | Shell | 2026-08-12 | 多平台 91 个 API Skill（选品、榜单、趋势、详情、流量词、达人等），MIT。 |
| [arsss6630/meli-picker](https://github.com/arsss6630/meli-picker) | 21 | HTML | 2025-12-26 | 美客多（拉美）AI 选品：市场竞争、蓝海挖掘、1688 货源匹配。 |
| [Pasindunabesinghe/Automated-Dropshipping-Price-Sentiment-Analysis-Tool](https://github.com/Pasindunabesinghe/Automated-Dropshipping-Price-Sentiment-Analysis-Tool) | 21 | VBScript | 2024-08-09 | UiPath RPA：Amazon/BestBuy 抓取、价格过滤、评论情感分析、PDF 报告。 |
| [nadinev6/dropship](https://github.com/nadinev6/dropship) | 13 | TypeScript | 2025-08-28 | n8n + Bright Data 的 AI 产品调研应用，推荐批发供应商。 |
| [Tomi431/Tomi](https://github.com/Tomi431/Tomi) | 1 | HTML | 2026-08-10 | MCP-native marketplace intelligence playbook（Amazon/Walmart/TikTok/1688/Shopee/TEMU）。 |
| [awesome-oversea/cross-border-erp](https://github.com/awesome-oversea/cross-border-erp) | 4 | Java | 2026-05-09 | 云原生 DDD 多租户跨境电商 ERP（Spring Boot/Next.js/PostgreSQL），覆盖选品到订单全链路。 |

## 值得深读的 Top 6

1. [liangdabiao/amazon-sorftime-research-MCP-skill](https://github.com/liangdabiao/amazon-sorftime-research-MCP-skill)：Star 最高、选品分析技能深度最贴近。
2. [nexscope-ai/eCommerce-Skills](https://github.com/nexscope-ai/eCommerce-Skills)：跨平台 Skill 生态最全，可对照能力清单。
3. [xiaolu7586/ecommerce-product-scout-agent](https://github.com/xiaolu7586/ecommerce-product-scout-agent)：多平台采集 + 六维评分 + Go/No-Go 报告，与本项目推荐链路最像。
4. [Umair706/amazon-omniscient](https://github.com/Umair706/amazon-omniscient)：全栈 FBA 选品引擎，含利润、预测、1688 匹配。
5. [chnjames/tradehot-skill](https://github.com/chnjames/tradehot-skill)：贸易情报/HS Code/关税/风险预警，直接对标本项目贸易决策模块。
6. [hooper-lee/crosspulse](https://github.com/hooper-lee/crosspulse)：每日市场监控与日报，对标每日联网快照机制。

## 对本项目的启示

1. GitHub 上类似项目多为「Agent/Skills + 商业数据 API」，本项目是自包含 Python 全栈（数据→特征→模型→推荐→贸易决策→API→看板），组合方式仍具稀缺性，可作为差异化叙述。
2. 多数项目没有 Prophet + LightGBM 的 90 天销量区间预测，也没有关税/合规/IP/物流/舆情/CBAM/融资一体的贸易决策模块；这两点是本项目最强的区分点。
3. 可借鉴的成熟做法：六维/多源评分与 Go/No-Go 决策（xiaolu7586、markwaveio）、真实数据源接入方式 MCP/API（Keepa、Sorftime、1688、卖家精灵）、每日市场监控推送（crosspulse）、卖前合规体检（launchfit-ai）、防假数据与证据闸设计（markwaveio、kangise）。
4. 风险提示：热门仓库多为 2026 年新出现的 Agent Skills，Star 数增长快但质量参差；部分仓库 README 简略或已停止更新（如 zhangzuomin、sidqian123、1huangyuhang）。引用或借鉴前需核对 License 与数据来源合规性。

## 数据与链接核实说明

- 以上 Star 数、语言、最近更新时间均来自 GitHub API（检索日 2026-08-13），随时间会变化。
- 所有仓库均通过 GitHub API 与 README 核对，链接可直接访问。
