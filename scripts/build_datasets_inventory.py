"""盘点所有训练数据集元数据，输出 JSON 供索引生成使用。"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, ".")
from src.config import (
    CATEGORIES,
    MARKETS,
    PROCESSED_CSV,
    DEMO_CSV,
)

REPORT: dict = {"datasets": []}


def _fmt_rows(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def add(
    name: str,
    source: str,
    path: str,
    modality: str,
    rows: int | None,
    cols: int | None,
    lang: str,
    license: str,
    updated: str,
    url: str,
    usage: str,
    status: str = "已落地",
    note: str = "",
) -> None:
    REPORT["datasets"].append(
        {
            "name": name,
            "source": source,
            "path": path,
            "modality": modality,
            "rows": _fmt_rows(rows) if rows is not None else "未知",
            "rows_raw": rows,
            "cols": cols,
            "language": lang,
            "license": license,
            "updated": updated,
            "url": url,
            "usage": usage,
            "status": status,
            "note": note,
        }
    )


def size_mb(p: Path) -> float:
    if not p.exists():
        return 0.0
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1048576
    return p.stat().st_size / 1048576


# ---------- GitHub 公开样例 ----------
GH = Path("data/external/github")

amz = pd.read_csv(GH / "amazon" / "amazon-products.csv")
add(
    "Amazon Products Sample (Bright Data)",
    "GitHub / luminati-io",
    "data/external/github/amazon/",
    "表格/文本",
    len(amz), len(amz.columns), "英",
    "Bright Data 免费样例（全量商业）", "2023 年抓取",
    "https://github.com/luminati-io/Amazon-dataset-samples",
    "价格/BSR/评分信号；对照组信号源",
    note=f"{size_mb(GH/'amazon'):.1f} MB",
)

ebay = pd.read_csv(GH / "ebay" / "eBay-dataset-sample.csv")
add(
    "eBay Products Sample (Bright Data)",
    "GitHub / luminati-io",
    "data/external/github/ebay/",
    "表格/文本",
    len(ebay), len(ebay.columns), "英",
    "Bright Data 免费样例（全量商业）", "2023 年抓取",
    "https://github.com/luminati-io/eBay-dataset-sample",
    "价格/销量/卖家评分信号；对照组信号源",
    note=f"{size_mb(GH/'ebay'):.1f} MB",
)

octa = pd.read_csv(GH / "octaprice" / "amazon_com_bird_food_2025_01_24.csv")
add(
    "Octaprice Amazon Bird Food 2025-01",
    "GitHub / octaprice",
    "data/external/github/octaprice/",
    "表格/文本",
    len(octa), len(octa.columns), "英",
    "学术/研究/新闻用途免费", "2025-01-24",
    "https://github.com/octaprice/ecommerce-product-dataset",
    "宠物/鸟食品类价格与评分；对照组信号源",
    note=f"{size_mb(GH/'octaprice'):.1f} MB",
)

hs = pd.read_csv(GH / "hs" / "data" / "harmonized-system.csv")
add(
    "HS Code Harmonized System",
    "GitHub / datasets",
    "data/external/github/hs/",
    "表格",
    len(hs), len(hs.columns), "英",
    "公有领域（UN Comtrade/WCO 打包）", "2024 年打包",
    "https://github.com/datasets/harmonized-system",
    "HS 编码速查与品类映射",
    note=f"{size_mb(GH/'hs'):.1f} MB",
)

shopee_files = sorted((GH / "shopee").rglob("*.parquet"))
shopee_rows = sum(len(pd.read_parquet(f)) for f in shopee_files)
add(
    "Shopee Product Details (rebrowser)",
    "GitHub / rebrowser",
    "data/external/github/shopee/",
    "表格",
    shopee_rows, None, "多语（东南亚）",
    "研究/非商业用途免费（需署名）", "2026-07 快照",
    "https://github.com/rebrowser/shopee-dataset",
    "东南亚市场评分/点赞/评论信号；对照组信号源",
    note=f"{len(shopee_files)} parquet, {size_mb(GH/'shopee'):.1f} MB",
)

# ---------- Hugging Face 公开数据集 ----------
HF = Path("data/external/hf")


def _parquet_rows(paths: list[Path]) -> int:
    total = 0
    for p in paths:
        try:
            total += len(pd.read_parquet(p))
        except Exception:
            pass
    return total


ecom_files = list((HF / "ecom_classification" / "data").glob("*.parquet"))
add(
    "E-Commerce Product Classification (31,851)",
    "Hugging Face / Lezh1n",
    "data/external/hf/ecom_classification/",
    "文本",
    _parquet_rows(ecom_files), 3, "英",
    "CC BY-4.0", "2026-02-18",
    "https://huggingface.co/datasets/Lezh1n/ecommerce-product-classification-by-categories",
    "33 类电商产品描述分类，可训练分类模型",
    note=f"{size_mb(HF/'ecom_classification'):.1f} MB",
)

add(
    "E-Commerce Reviews Sentiment (11,606)",
    "Hugging Face / dipawidia",
    "data/external/hf/ecom_reviews_sentiment/",
    "文本",
    11606, None, "印尼语",
    "未知（HF 未声明）", "2024-06-19",
    "https://huggingface.co/datasets/dipawidia/ecommerce-product-reviews-sentiment",
    "印尼电商评论情感二分类（含翻译）",
    note=f"{size_mb(HF/'ecom_reviews_sentiment'):.1f} MB",
)

pol_files = list((HF / "amazon_polarity" / "amazon_polarity").glob("*.parquet"))
add(
    "Amazon Polarity (~3.6M 评论)",
    "Hugging Face / fancyzhx",
    "data/external/hf/amazon_polarity/",
    "文本",
    _parquet_rows(pol_files), 3, "英",
    "Apache-2.0", "2024-01-09",
    "https://huggingface.co/datasets/fancyzhx/amazon_polarity",
    "Amazon 评论正负情感，直接训练 sentiment 模型",
    note=f"{size_mb(HF/'amazon_polarity'):.1f} MB；信号层抽样 20 万",
)

add(
    "AMAZON-Products-2023",
    "Hugging Face / milistu",
    "data/external/hf/amazon_products_2023/",
    "表格/文本",
    117243, 16, "英",
    "MIT", "2025-12-04",
    "https://huggingface.co/datasets/milistu/AMAZON-Products-2023",
    "Amazon 产品列表（价格/评分/分类），可训练价格/分类模型",
    note=f"{size_mb(HF/'amazon_products_2023'):.1f} MB（arrow 格式，需 datasets 库）",
)

add(
    "M5 Forecasting 基准",
    "Hugging Face / denephew",
    "data/external/hf/m5_forecasting/",
    "表格（时序）",
    60980, 1919, "英/无",
    "CC（基准数据）", "2024-06-25",
    "https://huggingface.co/datasets/denephew/M5_Forecasting",
    "约 3 万商品 × 1941 天零售销量（validation+evaluation），销量时序预测基准",
    note=f"{size_mb(HF/'m5_forecasting'):.1f} MB；信号层按品类×市场聚合",
)

# ---------- 核心训练/控制数据（项目自身） ----------
for name, path, desc in [
    ("演示市场数据（合成）", DEMO_CSV, "132 品类×15 市场×约 104 周合成历史"),
    ("清洗后训练数据", PROCESSED_CSV, "全量 132×15 清洗数据"),
    ("对照组训练集", Path("data/control/train_data.csv"), "对照组 train 切片"),
    ("对照组留出集", Path("data/control/holdout_data.csv"), "对照组 holdout 切片"),
]:
    if path.exists():
        df = pd.read_csv(path)
        rel = str(path).replace(str(Path.cwd()), "").lstrip("\\/") or str(path)
        add(
            name, "项目合成/流程产物", rel, "表格（时序）",
            len(df), len(df.columns), "多语（中英）",
            "项目内部", "当日刷新",
            "", f"{desc}；{len(CATEGORIES)} 品类 × {len(MARKETS)} 市场",
            status="流程产物",
            note=f"{size_mb(path):.1f} MB",
        )

# ---------- Kaggle 候选（待接入，需凭据） ----------
kaggle_candidates = [
    (
        "Amazon Products Dataset 2023 (1.4M)",
        "Kaggle / asaniczka",
        "data/external/kaggle/amazon_products_1_4m/",
        "表格/文本", 1403994, 13, "英",
        "ODC-By", "2023-09 抓取",
        "https://www.kaggle.com/datasets/asaniczka/amazon-products-dataset-2023-1-4m-products",
        "价格/月销量/BSR，可训练价格与销量代理模型",
        "待接入（需 Kaggle 凭据）",
        "含 bought_past_month；同作者有 UK/CA/IN/BR 多市场版",
    ),
    (
        "Brazilian E-Commerce (Olist)",
        "Kaggle / olistbr",
        "data/external/kaggle/olist/",
        "表格/文本", 100000, None, "葡/英",
        "CC BY-NC-SA 4.0（非商业）", "2016-2018",
        "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "订单→支付→物流→评论全链路，评分/价格建模",
        "待接入（需 Kaggle 凭据）",
        "126 MB；非商业许可",
    ),
    (
        "eBay Product Listing (980K)",
        "Kaggle / promptcloud",
        "data/external/kaggle/ebay_listing/",
        "表格/文本", 980958, None, "英",
        "CC0", "2020-09~10",
        "https://www.kaggle.com/datasets/promptcloud/ebay-product-listing-dataset",
        "五档星级/价格/库存，定价模型",
        "待接入（需 Kaggle 凭据）",
        "页面样例 30K；CC0 可商用",
    ),
]
for args in kaggle_candidates:
    add(*args)

REPORT["summary"] = {
    "github_providers": len([p for p in GH.iterdir() if p.is_dir()]) if GH.exists() else 0,
    "hf_providers": len([p for p in HF.iterdir() if p.is_dir()]) if HF.exists() else 0,
    "kaggle_candidates": len(kaggle_candidates),
    "total_size_mb": sum(size_mb(d) for d in [GH, HF]),
    "categories": len(CATEGORIES),
    "markets": len(MARKETS),
}

out = Path("output/datasets_inventory.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"written {out}")
for d in REPORT["datasets"]:
    print(f"- {d['name']}  [{d['status']}] {d['rows']} rows  {d['license']}")
