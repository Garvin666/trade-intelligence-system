# GitHub 数据集来源与校验

获取日期：2026-08-13。以下文件由本项目直接入库，用于顶级 AI 对照的真实信号回填；原始许可与使用条款见各来源仓库。

| Provider | 来源仓库 | 许可证/条款 | 本地文件 |
|---|---|---|---|
| Amazon | https://github.com/luminati-io/Amazon-dataset-samples | Bright Data 免费样例；完整数据为商业服务 | `amazon/amazon-products.csv` |
| eBay | https://github.com/luminati-io/eBay-dataset-sample | Bright Data 免费样例；完整数据为商业服务 | `ebay/eBay-dataset-sample.csv` |
| Shopee | https://github.com/rebrowser/shopee-dataset | 研究/非商业用途免费，需署名；商业需付费 | `shopee/product-details/data/*.parquet` |
| Octaprice | https://github.com/octaprice/ecommerce-product-dataset | 学术/研究/新闻用途免费，遵循仓库 TOU | `octaprice/amazon_com_bird_food_2025_01_24.csv` |
| HS Code | https://github.com/datasets/harmonized-system | 公开数据包，原始数据来自 UN Comtrade/WCO | `hs/data/harmonized-system.csv` |

## 代表文件 SHA-256

| 文件 | SHA-256 |
|---|---|
| `amazon/amazon-products.csv` | `4D03CAC9BDEA07DD05AC3DA94241F77DEBEF040F787B845C722EB386583C9BAB` |
| `ebay/eBay-dataset-sample.csv` | `C540C595D12D59AE1607DEBE0E3875487499DFA7C40BF1F60F11A8FBB5668F54` |
| `shopee/product-details/data/2026-07-29.parquet` | `5F6A6FAC6F2C8C72C5BB92A00744A46F89E0418A7B2BA6A945A346C4E7EEC143` |
| `octaprice/amazon_com_bird_food_2025_01_24.csv` | `B2932424BACCFF6A88F27B45D768027B4CD6896A9EDA4E1B7CFC91BEB37E4846` |
| `hs/data/harmonized-system.csv` | `E77EE9E1CFD15A42D1FADEB2C0618D10F6B9ED9AEC0E5D66826DC7EF9D3126A5` |

## 刷新方式

```powershell
.venv\Scripts\python scripts\fetch_github_datasets.py --offline
.venv\Scripts\python scripts\backfill_control_real.py
```

离线模式下脚本只校验本地文件是否存在；缺失时给出明确路径，不会用 mock 数据替代。
