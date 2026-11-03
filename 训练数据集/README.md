# 跨境电商智能选品 — 训练数据集候选清单

> 整理时间：2026-08-15（2026-08-16 复核）
> 来源：Hugging Face API 实测查询 + Kaggle / GitHub / Hugging Face 网页检索确认
> 说明：所有链接均经搜索确认真实存在；gated / 需登录 / 需审批的数据集已在备注标注。Kaggle 下载需 Kaggle 凭据。
> 落地状态：已下载入库的数据集见 `data/DATASETS_INDEX.md`（含行数 / 大小 / 许可）；本目录 `data/product-reviews-sentiment/` 当前为空，`AnkitAI/product-reviews-sentiment` 尚未下载。

## 一、商品评论与情感分析（英文）

| 名称 | 来源 | 模态 | 规模 | 语言 | 许可证 | 链接 | 备注 |
|---|---|---|---|---|---|---|---|
| Amazon Reviews 2023 | Hugging Face | 文本 | 约 5.7 亿条评论（含元数据） | 多语言（主英/德/法/日等） | 未知（研究用途常见） | https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023 | 规模最大、最新；原始分片 parquet，需按需加载；可作情感/评分/商品属性任务 |
| product-reviews-sentiment | Hugging Face | 文本 | 9,000 条，4 类均衡 | en | MIT | https://huggingface.co/datasets/AnkitAI/product-reviews-sentiment | 4 分类（客服分流场景），CSV 可直接训练 |
| ecommerce-product-reviews-sentiment | Hugging Face | 文本 | 11,606 条 | id/en | 未知 | https://huggingface.co/datasets/dipawidia/ecommerce-product-reviews-sentiment | 印尼多平台电商（Shopee/Tokopedia 等）正负二分类 |
| synthetic_product_reviews_sentiment | Hugging Face | 文本 | <1K | en | MIT | https://huggingface.co/datasets/Suzana/synthetic_product_reviews_sentiment | 合成数据，仅适合冒烟测试 |

## 二、多语言评论

| 名称 | 来源 | 模态 | 规模 | 语言 | 许可证 | 链接 | 备注 |
|---|---|---|---|---|---|---|---|
| amazon_reviews_multi | Hugging Face | 文本 | 6 语言 × 约 21 万条（train 200k / valid 5k / test 5k） | de/en/es/fr/ja/zh | 未知 | https://huggingface.co/datasets/amazon_reviews_multi | 官方多语言评测集，跨语言情感迁移 |
| turkish_product_reviews_sentiment | Hugging Face | 文本 | 100K<n<1M | tr | 未知 | https://huggingface.co/datasets/anilguven/turkish_product_reviews_sentiment | 土耳其语（Hepsiburada）二分类 |

## 三、中文电商评论

| 名称 | 来源 | 模态 | 规模 | 语言 | 许可证 | 链接 | 备注 |
|---|---|---|---|---|---|---|---|
| JDReview-classification | Hugging Face | 文本 | 未知 | zh | 未知 | https://huggingface.co/datasets/C-MTEB/JDReview-classification | C-MTEB 中文评测套件中的京东评论分类任务 |

## 四、销量 / 需求预测（时序）

| 名称 | 来源 | 模态 | 规模 | 语言 | 许可证 | 链接 | 备注 |
|---|---|---|---|---|---|---|---|
| M5 Forecasting - Accuracy | Kaggle 竞赛 | 表格（时序） | 3,049 SKU × 10 店 × 1,941 天 | —（非文本） | 竞赛条款 | https://www.kaggle.com/competitions/m5-forecasting-accuracy | Walmart 层级销量预测，业界标准基线；需 Kaggle 凭据下载 |
| Favorita Grocery Sales Forecasting | Kaggle 竞赛 | 表格（时序） | 约 12.5 万 商店×商品组合，2013–2017 | —（非文本） | 竞赛条款 | https://www.kaggle.com/c/favorita-grocery-sales-forecasting | 厄瓜多尔杂货销量预测，含店/商品/促销特征 |

## 五、电商交易 / 客户（非时序结构化）

| 名称 | 来源 | 模态 | 规模 | 语言 | 许可证 | 链接 | 备注 |
|---|---|---|---|---|---|---|---|
| Brazilian E-Commerce Public Dataset by Olist | Kaggle | 表格 | 约 10 万订单（2016–2018） | pt/en | 竞赛条款（Kaggle 免费公开） | https://www.kaggle.com/datasets/enzoschitini/brazilian-e-commerce-public-dataset-by-olist/ | 订单/商品/卖家/评价全链路，适合选品与客户分析 |

## 六、HS Code / 国际贸易分类

| 名称 | 来源 | 模态 | 规模 | 语言 | 许可证 | 链接 | 备注 |
|---|---|---|---|---|---|---|---|
| HSClassify-benchmark | Hugging Face | 文本 | 未知 | en | 未知 | https://huggingface.co/datasets/Mead0w1ark/HSClassify-benchmark | 商品描述 → HS 编码分类评测集，直接对应本项目贸易决策 |
| trade_compliance | Hugging Face | 文本 | 未知 | en | gated | https://huggingface.co/datasets/alerterra/trade_compliance | **需同意共享联系方式才能访问（gated）** |
| UN Comtrade / WITS | 官方数据源 | 表格 | 按需查询 | — | 官方条款 | https://comtradeplus.un.org/ / https://wits.worldbank.org/ | 海关进出口统计源，非训练集；本项目已接入 UN Comtrade 免 Key 预览 + Open Trade Statistics 回退 |

## 七、商品多模态 / 图像

| 名称 | 来源 | 模态 | 规模 | 语言 | 许可证 | 链接 | 备注 |
|---|---|---|---|---|---|---|---|
| MEP-3M | GitHub | 多模态（图像+文本） | 300 万商品（3M 图像） | zh/en | 未知（LTDL@IJCAI-21 Best Dataset） | https://github.com/ChenDelong1999/MEP-3M | 大规模电商多模态商品数据集，图像-文本检索/分类 |

## 八、本地已有数据（无需下载）

| 名称 | 位置 | 说明 |
|---|---|---|
| eBay 公开样例 | `data/external/github/ebay/eBay-dataset-sample.csv` | GitHub 免费样例，已随项目分发 |
| Amazon / eBay 榜单适配器 | `src/data/github_datasets.py` + `scripts/fetch_github_datasets.py` | 平台榜单默认 Amazon / eBay GitHub 免费样例，Keepa/eBay 有 Key 可选升级 |
| 每日联网快照 | `output/daily_snapshots/` | 46 品类 × 15 市场联网检索结果，可作自建特征/标签 |
| 市场日报 | `output/market_daily/*.md` | 每日市场观察文本 |

## 下载命令速查

```bash
# Hugging Face（任选其一）
huggingface-cli download McAuley-Lab/Amazon-Reviews-2023 --repo-type dataset --include "*" --local-dir data/amazon-reviews-2023
pip install datasets
python -c "from datasets import load_dataset; ds = load_dataset('AnkitAI/product-reviews-sentiment'); print(ds)"

# Kaggle（需先配置 ~/.kaggle/kaggle.json 凭据）
kaggle competitions download -c m5-forecasting-accuracy
kaggle competitions download -c favorita-grocery-sales-forecasting
kaggle datasets download -d enzoschitini/brazilian-e-commerce-public-dataset-by-olist

# MEP-3M（GitHub）
git clone https://github.com/ChenDelong1999/MEP-3M.git data/mep-3m
```

## 使用建议（对接本项目）

1. **评论情感/商品属性** → Amazon Reviews 2023（抽样）、`AnkitAI/product-reviews-sentiment`，用于"卖什么"的评论洞察模块；
2. **销量预测** → M5 / Favorita 训练 Prophet / LightGBM 基线，验证 `src/models` 双模型相对优势；
3. **HS 编码** → HSClassify-benchmark 直接评测贸易决策的 HS Code 速查/分类能力；
4. **多模态** → MEP-3M 用于商品图搜/属性识别扩展；
5. 大文件（Amazon Reviews 2023 约百 GB 级、MEP-3M 数 TB 级）**不要整库下载**，用 `load_dataset` 按分片/流式加载。
