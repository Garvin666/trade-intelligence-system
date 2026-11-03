# 训练数据集总索引（跨境电商智能选品）

> 生成时间：2026-11-03 22:58；共 **17** 个数据集，合计约 **0.04 GB**。
> 机器可读清单：`data/datasets_manifest.json`；重建：`python scripts\build_datasets_inventory.py`

## 一、总览

| # | 数据集 | 来源 | 模态 | 规模 | 语言 | 许可证 | 用途 | 状态 |
|---|---|---|---|---|---|---|---|---|
| 1 | Amazon Products Sample (Bright Data) | GitHub / luminati-io | 表格/文本 | 1K | 英 | Bright Data 免费样例（全量商业） | 价格/BSR/评分信号；对照组信号源 | 已落地 |
| 2 | eBay Products Sample (Bright Data) | GitHub / luminati-io | 表格/文本 | 1K | 英 | Bright Data 免费样例（全量商业） | 价格/销量/卖家评分信号；对照组信号源 | 已落地 |
| 3 | Octaprice Amazon Bird Food 2025-01 | GitHub / octaprice | 表格/文本 | 972 | 英 | 学术/研究/新闻用途免费 | 宠物/鸟食品类价格与评分；对照组信号源 | 已落地 |
| 4 | HS Code Harmonized System | GitHub / datasets | 表格 | 7K | 英 | 公有领域（UN Comtrade/WCO 打包） | HS 编码速查与品类映射 | 已落地 |
| 5 | Shopee Product Details (rebrowser) | GitHub / rebrowser | 表格 | 27K | 多语（东南亚） | ⚠️ 研究/非商业用途免费（需署名） | 东南亚市场评分/点赞/评论信号；对照组信号源 | 已落地 |
| 6 | E-Commerce Product Classification (31,851) | Hugging Face / Lezh1n | 文本 | 0 | 英 | CC BY-4.0 | 33 类电商产品描述分类，可训练分类模型 | 已落地 |
| 7 | E-Commerce Reviews Sentiment (11,606) | Hugging Face / dipawidia | 文本 | 12K | 印尼语 | 未知（HF 未声明） | 印尼电商评论情感二分类（含翻译） | 已落地 |
| 8 | Amazon Polarity (~3.6M 评论) | Hugging Face / fancyzhx | 文本 | 0 | 英 | Apache-2.0 | Amazon 评论正负情感，直接训练 sentiment 模型 | 已落地 |
| 9 | AMAZON-Products-2023 | Hugging Face / milistu | 表格/文本 | 117K | 英 | MIT | Amazon 产品列表（价格/评分/分类），可训练价格/分类模型 | 已落地 |
| 10 | M5 Forecasting 基准 | Hugging Face / denephew | 表格（时序） | 61K | 英/无 | CC（基准数据） | 约 3 万商品 × 1941 天零售销量（validation+evaluation），销量时序预测基准 | 已落地 |
| 11 | 演示市场数据（合成） | 项目合成/流程产物 | 表格（时序） | 206K | 多语（中英） | 项目内部 | 132 品类×15 市场×约 104 周合成历史；132 品类 × 15 市场 | 流程产物 |
| 12 | 清洗后训练数据 | 项目合成/流程产物 | 表格（时序） | 206K | 多语（中英） | 项目内部 | 全量 132×15 清洗数据；132 品类 × 15 市场 | 流程产物 |
| 13 | 对照组训练集 | 项目合成/流程产物 | 表格（时序） | 182K | 多语（中英） | 项目内部 | 对照组 train 切片；132 品类 × 15 市场 | 流程产物 |
| 14 | 对照组留出集 | 项目合成/流程产物 | 表格（时序） | 24K | 多语（中英） | 项目内部 | 对照组 holdout 切片；132 品类 × 15 市场 | 流程产物 |
| 15 | Amazon Products Dataset 2023 (1.4M) | Kaggle / asaniczka | 表格/文本 | 1.4M | 英 | ODC-By | 价格/月销量/BSR，可训练价格与销量代理模型 | 待接入（需 Kaggle 凭据） |
| 16 | Brazilian E-Commerce (Olist) | Kaggle / olistbr | 表格/文本 | 100K | 葡/英 | ⚠️ CC BY-NC-SA 4.0（非商业） | 订单→支付→物流→评论全链路，评分/价格建模 | 待接入（需 Kaggle 凭据） |
| 17 | eBay Product Listing (980K) | Kaggle / promptcloud | 表格/文本 | 981K | 英 | CC0 | 五档星级/价格/库存，定价模型 | 待接入（需 Kaggle 凭据） |

## 二、分组明细

### Hugging Face（5 个）

| 数据集 | 路径 | 规模 | 许可证 | 更新 | 链接 | 备注 |
|---|---|---|---|---|---|---|
| **E-Commerce Product Classification (31,851)** | `data/external/hf/ecom_classification/` | 0 | CC BY-4.0 | 2026-02-18 | [链接](https://huggingface.co/datasets/Lezh1n/ecommerce-product-classification-by-categories) | 0.0 MB |
| **E-Commerce Reviews Sentiment (11,606)** | `data/external/hf/ecom_reviews_sentiment/` | 12K | 未知（HF 未声明） | 2024-06-19 | [链接](https://huggingface.co/datasets/dipawidia/ecommerce-product-reviews-sentiment) | 0.0 MB |
| **Amazon Polarity (~3.6M 评论)** | `data/external/hf/amazon_polarity/` | 0 | Apache-2.0 | 2024-01-09 | [链接](https://huggingface.co/datasets/fancyzhx/amazon_polarity) | 0.0 MB；信号层抽样 20 万 |
| **AMAZON-Products-2023** | `data/external/hf/amazon_products_2023/` | 117K | MIT | 2025-12-04 | [链接](https://huggingface.co/datasets/milistu/AMAZON-Products-2023) | 0.0 MB（arrow 格式，需 datasets 库） |
| **M5 Forecasting 基准** | `data/external/hf/m5_forecasting/` | 61K | CC（基准数据） | 2024-06-25 | [链接](https://huggingface.co/datasets/denephew/M5_Forecasting) | 0.0 MB；信号层按品类×市场聚合 |

### GitHub（5 个）

| 数据集 | 路径 | 规模 | 许可证 | 更新 | 链接 | 备注 |
|---|---|---|---|---|---|---|
| **Amazon Products Sample (Bright Data)** | `data/external/github/amazon/` | 1K | Bright Data 免费样例（全量商业） | 2023 年抓取 | [链接](https://github.com/luminati-io/Amazon-dataset-samples) | 5.8 MB |
| **eBay Products Sample (Bright Data)** | `data/external/github/ebay/` | 1K | Bright Data 免费样例（全量商业） | 2023 年抓取 | [链接](https://github.com/luminati-io/eBay-dataset-sample) | 15.4 MB |
| **Octaprice Amazon Bird Food 2025-01** | `data/external/github/octaprice/` | 972 | 学术/研究/新闻用途免费 | 2025-01-24 | [链接](https://github.com/octaprice/ecommerce-product-dataset) | 3.4 MB |
| **HS Code Harmonized System** | `data/external/github/hs/` | 7K | 公有领域（UN Comtrade/WCO 打包） | 2024 年打包 | [链接](https://github.com/datasets/harmonized-system) | 0.8 MB |
| **Shopee Product Details (rebrowser)** | `data/external/github/shopee/` | 27K | 研究/非商业用途免费（需署名） | 2026-07 快照 | [链接](https://github.com/rebrowser/shopee-dataset) | 30 parquet, 17.8 MB |

### 项目流程产物（4 个）

| 数据集 | 路径 | 规模 | 许可证 | 更新 | 链接 | 备注 |
|---|---|---|---|---|---|---|
| **演示市场数据（合成）** | `data\demo\demo_market_data.csv` | 206K | 项目内部 | 当日刷新 | — | 14.7 MB |
| **清洗后训练数据** | `data\processed\clean_data.csv` | 206K | 项目内部 | 当日刷新 | — | 14.7 MB |
| **对照组训练集** | `data\control\train_data.csv` | 182K | 项目内部 | 当日刷新 | — | 19.2 MB |
| **对照组留出集** | `data\control\holdout_data.csv` | 24K | 项目内部 | 当日刷新 | — | 2.5 MB |

### 待接入候选（Kaggle，需凭据）（3 个）

| 数据集 | 路径 | 规模 | 许可证 | 更新 | 链接 | 备注 |
|---|---|---|---|---|---|---|
| **Amazon Products Dataset 2023 (1.4M)** | `data/external/kaggle/amazon_products_1_4m/` | 1.4M | ODC-By | 2023-09 抓取 | [链接](https://www.kaggle.com/datasets/asaniczka/amazon-products-dataset-2023-1-4m-products) | 含 bought_past_month；同作者有 UK/CA/IN/BR 多市场版 |
| **Brazilian E-Commerce (Olist)** | `data/external/kaggle/olist/` | 100K | CC BY-NC-SA 4.0（非商业） | 2016-2018 | [链接](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) | 126 MB；非商业许可 |
| **eBay Product Listing (980K)** | `data/external/kaggle/ebay_listing/` | 981K | CC0 | 2020-09~10 | [链接](https://www.kaggle.com/datasets/promptcloud/ebay-product-listing-dataset) | 页面样例 30K；CC0 可商用 |

## 三、用途速查

| 训练目标 | 推荐数据集 |
|---|---|
| 评论情感分析 | Amazon Polarity（360 万条）、E-Commerce Reviews Sentiment（印尼语） |
| 产品分类/品类映射 | E-Commerce Product Classification（33 类）、AMAZON-Products-2023、HS Code |
| 价格/销量代理 | Amazon Products Sample、eBay Sample、Octaprice、AMAZON-Products-2023、M5 |
| 销量时序预测 | M5 Forecasting（3 万商品×1941 天）、演示市场数据（132×15 合成时序） |
| 市场信号/对照组 | Shopee、Amazon/eBay 样例、Google Trends（output 侧） |

## 四、许可提醒

- **可商用**：HS Code（公有领域）、eBay Product Listing（CC0）、amazon_polarity（Apache-2.0）、AMAZON-Products-2023（MIT）、E-Commerce Classification（CC BY-4.0）。
- **非商业（⚠️）**：Olist（CC BY-NC-SA）、Datafiniti 评论（CC BY-NC-SA）、42K+ Amazon（CC BY-NC）——商用演示需谨慎，建议仅用于学术验证。
- **样例/商业**：Bright Data 的 Amazon/eBay 免费样例（全量数据集为商业产品）、Octaprice（学术用途免费）。
- **未声明**：E-Commerce Reviews Sentiment（HF 未标注许可证），使用前建议联系作者确认。

---

*本索引由 `scripts/build_datasets_inventory.py` + `scripts/build_datasets_index.py` 自动生成；新增数据集后请重跑。*
