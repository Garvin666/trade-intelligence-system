# 第三方开源项目来源记录

> 审计日期：2026-08-13。本目录保存许可证审计结果；仅 MIT/BSD/Apache/CC0 仓库允许
> 直接复制代码。无 License 或 NOASSERTION 仓库只参考思路，不复制代码。

## 许可证与来源

| 仓库 | License | 审计提交 SHA | 引用方式 | 本项目落点 |
|---|---|---|---|---|
| markwaveio/cross-border-selection-kit | 无 LICENSE | d9a9f0a65de3b16f9c4c102746ac83049e87d36f | 仅参考思路 | 六维评分、三源交叉验证、证据可信度 |
| xiaolu7586/ecommerce-product-scout-agent | 无 LICENSE | 12cb76f1652b1761bda696c2d46b64fc4f026264 | 仅参考思路 | Go/No-Go 与六维评分结构 |
| chnjames/tradehot-skill | 无 LICENSE | 02fa914126e6790a3ea950beb791492206836509 | 仅参考思路 | HS Code / 关税速查结构 |
| JuneYaooo/launchfit-ai | NOASSERTION | 99d5a18cdee40bfeb9f117531577c5fdb55d3627 | 仅参考思路 | 卖前合规体检清单 |
| hooper-lee/crosspulse | MIT | 4a8bfa479d1216746fb659f2e9b70b6584b112c8 | 许可证可复用；本次原生实现 | 市场日报结构 |
| kangise/ecommerce-ai-skills | CC0-1.0 | a6a6204ccfb34201f5d532448efc1aa24dda0e97 | 许可证可复用；本次原生实现 | 证据闸与反幻觉护栏 |
| cosjef/keepa_MCP | MIT | fcba449314a28f1243ce4114cbf7c545919b60fb | 许可证可复用；本次原生实现 | 平台榜单适配器框架 |
| superjack2050/1688-cli | MIT | 5f958211c002ba3f210bfd88d9d838080c4593f0 | 许可证可复用；本次原生实现 | 货源/供应商采集思路 |
| zach22-1999/amazon-skills | MIT | f8b5873ce30a3705172e07d0241b32caf5e47703 | 许可证可复用；本次原生实现 | Amazon 榜单与选品验证思路 |
| scrape-do/amazon-scraper | MIT | a27bd17bef4698472a32e8db696fa3c006c720f2 | 许可证可复用；解析函数改写并标注来源 | Amazon Best Sellers 解析 |
| hughie21/Customs-Crawler | 无 LICENSE | 未取得 | 仅参考思路，不复制不打包 | 海关记录爬取思路 |
| mageprince/magento2-mage-ai-predict | GPL-3.0 | 审计未取得 | 仅参考思路，不复制代码 | 统计引擎 + LLM 解释分层 |
| wo9230/osint-agent | NOASSERTION | 审计未取得 | 仅参考思路，不复制代码 | 供应商/客户尽调清单 |
| nexscope-ai/eCommerce-Skills | MIT | 56f3288dd1ba3ae7cae43d369115a915229e510b | 许可证可复用；本次未复制 | 跨平台电商能力清单对照 |
| GeneralMills/pytrends | Apache-2.0 | 仓库已于 2025-04 归档（read-only） | 仅作为 pip 依赖调用，不复制源码 | Google Trends 采集 |
| apify/crawlee-python | Apache-2.0 | PyPI crawlee 1.9.1 | 仅作为 pip 依赖调用，不复制源码 | HTML 抓取引擎（`src/data/crawl_engine.py`） |
| scrapy/protego | BSD-3-Clause | PyPI protego 0.6.2 | 仅作为 pip 依赖调用，不复制源码 | robots.txt 解析与 Crawl-delay/Request-rate |
| adbar/trafilatura | Apache-2.0 | PyPI trafilatura 2.2.0 | 仅作为 pip 依赖调用，不复制源码 | HTML 正文/元数据提取 |
| uncomtrade/comtradeapicall | MIT | 官方维护，PyPI 1.3.2 | 仅作为 pip 依赖调用，不复制源码 | 中国 HS4 出口数据 |
| Data-Centric-AI-Community/fg-data-profiling | MIT | 原 ydata-profiling 已更名，4.19.1 | 仅作为 pip 依赖调用，不复制源码 | 用户 CSV/JSON 自动 EDA |
| maximtrp/scikit-posthocs | MIT | PyPI 0.10.x | 仅作为 pip 依赖调用，不复制源码 | 多组事后比较 |
| yzhao062/pyod | BSD-2-Clause | PyOD 3.x | 仅作为 pip 依赖调用，不复制源码 | 异常检测 |
| 999Diogo/keepa | Apache-2.0 | PyPI keepa 1.4.4 | 有 Key 时作为 pip 依赖调用，不复制源码 | Amazon BSR 平台榜单 |
| eBay/ebaysdk | CDDL-1.0 | PyPI ebaysdk 2.x | 仅调用 API，不复制源码 | eBay 榜单/搜索信号 |
| Nixtla/statsforecast | Apache-2.0 | 官方仓库 1.7+ | 仅作为 pip 依赖调用，不复制源码 | 第三预测基线（AutoETS） |
| modelcontextprotocol/python-sdk | MIT | 官方仓库 1.0+ | 作为 pip 依赖调用，不复制源码 | MCP server 工具桥接 |

## 直接入库的公开数据集

| 数据集仓库 | License / 条款 | 引用方式 | 本项目落地 |
|---|---|---|---|
| luminati-io/Amazon-dataset-samples | Bright Data 免费样例；完整数据为商业服务 | 样例 CSV 直接入库 `data/external/github/amazon` | 真实平台信号回填 |
| luminati-io/eBay-dataset-sample | Bright Data 免费样例；完整数据为商业服务 | 样例 CSV 直接入库 `data/external/github/ebay` | 真实平台信号回填 |
| rebrowser/shopee-dataset | 研究/非商业免费需署名；商业需付费 | Parquet 样例直接入库 `data/external/github/shopee` | 东南亚平台信号 |
| octaprice/ecommerce-product-dataset | 学术/研究/新闻用途免费，遵循仓库 TOU | CSV 样例直接入库 `data/external/github/octaprice` | 商品价格/评论信号 |
| datasets/harmonized-system | 公开数据包，数据源自 UN Comtrade/WCO | CSV 直接入库 `data/external/github/hs` | HS 码参考信号 |
| openfoodfacts/openfoodfacts.org | Open Database License (ODbL-1.0) | 官方 REST API v2 按官方文档调用（标识 UA + 限速；robots 面向网页爬虫），快照落盘 `output/open_food_facts/latest.json` | 食品品类商品信号；派生快照需保留来源与 ODbL 声明 |

## 已保存许可证

以下仓库的 LICENSE 原文已保存在本目录对应子目录，便于随完整 Demo 包分发：

- `third_party/hooper-lee/crosspulse/LICENSE`
- `third_party/kangise/ecommerce-ai-skills/LICENSE`
- `third_party/cosjef/keepa_MCP/LICENSE`
- `third_party/superjack2050/1688-cli/LICENSE`
- `third_party/zach22-1999/amazon-skills/LICENSE`
- `third_party/nexscope-ai/eCommerce-Skills/LICENSE`
- `third_party/scrape-do/amazon-scraper/LICENSE`

## 说明

本项目按“原生实现 + 必要时直接复用许可代码”的方式落地。当前版本以原生实现为主，
所有参考仓库的 License 与提交 SHA 已审计登记；后续若直接复制代码，必须在对应
`src/` 文件头部增加来源头，并同步更新本表。

依赖类仓库（pytrends / comtradeapicall / fg-data-profiling / scikit-posthocs /
pyod / keepa / ebaysdk）仅通过 `requirements.txt` 以 pip 方式引用，不复制其
源码；对应许可证仅作登记，不随分发包额外附带许可证文件。

`superjack2050/1688-cli` 仅作为外部 CLI 子进程调用，不复制其源码；未安装、未登录
或超时均由 `src/data/supplier_sourcing.py` 自动回退 mock 并标注来源。`scrape-do/
amazon-scraper` 的解析逻辑已改写进 `src/data/collector.py`，文件头保留来源与审计
SHA；`hughie21/Customs-Crawler` 无 LICENSE，仅记录思路，不进入本项目源码或分发包。
