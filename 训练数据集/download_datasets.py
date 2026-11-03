# -*- coding: utf-8 -*-
"""训练数据集下载脚本（跨境电商智能选品项目）。

用法：
    python download_datasets.py --list                 # 列出可下载的数据集
    python download_datasets.py --name product-reviews-sentiment   # 下载单个
    python download_datasets.py --all-small            # 下载全部小/中规模数据集（跳过超大库）

说明：
    - Hugging Face 数据集用 datasets 库加载并落盘（需 pip install datasets）；
    - Kaggle 数据集需已配置 ~/.kaggle/kaggle.json 凭据，用 kaggle CLI；
    - Amazon Reviews 2023 / MEP-3M 为超大库，默认只下载极少量分片或跳过。
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

# name -> (source, remote_id, local_dir, note)
# source: hf = Hugging Face（datasets 库）；kaggle = Kaggle CLI（竞赛用 -c，数据集用 -d）
DATASETS = {
    "product-reviews-sentiment": (
        "hf", "AnkitAI/product-reviews-sentiment", "product-reviews-sentiment",
        "9,000 条英文 4 类评论（MIT，CSV）",
    ),
    "ecommerce-product-reviews-sentiment": (
        "hf", "dipawidia/ecommerce-product-reviews-sentiment", "ecommerce-product-reviews-sentiment",
        "11,606 条印尼多平台电商评论二分类",
    ),
    "amazon-reviews-multi": (
        "hf", "amazon_reviews_multi", "amazon-reviews-multi",
        "6 语言评论（de/en/es/fr/ja/zh），每语言约 21 万条",
    ),
    "jdreview-classification": (
        "hf", "C-MTEB/JDReview-classification", "jdreview-classification",
        "中文京东评论分类（C-MTEB 评测）",
    ),
    "hsclassify-benchmark": (
        "hf", "Mead0w1ark/HSClassify-benchmark", "hsclassify-benchmark",
        "商品描述 → HS 编码分类评测集",
    ),
    "olist": (
        "kaggle", "enzoschitini/brazilian-e-commerce-public-dataset-by-olist", "olist",
        "巴西电商 10 万订单全链路（Kaggle 数据集）",
    ),
    "m5-forecasting": (
        "kaggle-competition", "m5-forecasting-accuracy", "m5-forecasting",
        "Walmart M5 层级销量预测（Kaggle 竞赛，较大，约 GB 级）",
    ),
    "favorita": (
        "kaggle-competition", "favorita-grocery-sales-forecasting", "favorita",
        "厄瓜多尔杂货销量预测（Kaggle 竞赛，较大）",
    ),
}

# 超大库，默认跳过（需显式 --name 下载且只取分片）
HUGE = {
    "amazon-reviews-2023": "McAuley-Lab/Amazon-Reviews-2023",
    "mep-3m": "https://github.com/ChenDelong1999/MEP-3M.git",
}


def list_datasets():
    print("可下载数据集：")
    for name, (source, rid, local, note) in DATASETS.items():
        print(f"  [{source:>17}] {name:<34} -> data/{local}  ({note})")
    print("\n超大库（默认跳过，需显式下载分片）：")
    for name, rid in HUGE.items():
        print(f"  [huge] {name}  ({rid})")


def download_hf(remote_id: str, local_dir: Path):
    local_dir.mkdir(parents=True, exist_ok=True)
    code = (
        "from datasets import load_dataset\n"
        f"ds = load_dataset({remote_id!r}, split='train', streaming=False)\n"
        f"ds.to_parquet({str(local_dir / 'data.parquet')!r})\n"
        "print('saved:', len(ds))\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        script = f.name
    try:
        subprocess.run([sys.executable, script], check=True)
    finally:
        Path(script).unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(description="下载训练数据集")
    ap.add_argument("--list", action="store_true", help="列出数据集")
    ap.add_argument("--name", help="下载指定数据集（DATASETS 中的键）")
    ap.add_argument("--all-small", action="store_true", help="下载全部小/中规模数据集")
    args = ap.parse_args()

    if args.list:
        list_datasets()
        return
    if args.name:
        if args.name in HUGE:
            print(f"[警告] {args.name} 是超大库，请自行按分片/流式加载，勿整库下载。")
            return
        if args.name not in DATASETS:
            print(f"未知数据集：{args.name}，用 --list 查看。")
            sys.exit(1)
        source, rid, local, _ = DATASETS[args.name]
        local_dir = DATA_DIR / local
        if source == "hf":
            download_hf(rid, local_dir)
        else:
            cmd = ["kaggle", "datasets", "download", "-d", rid, "-p", str(local_dir), "--unzip"]
            if source == "kaggle-competition":
                cmd = ["kaggle", "competitions", "download", "-c", rid, "-p", str(local_dir)]
            subprocess.run(cmd, check=True)
        print(f"完成：data/{local}")
        return
    if args.all_small:
        for name, (source, rid, local, _) in DATASETS.items():
            if source == "kaggle-competition":
                print(f"跳过竞赛大库：{name}")
                continue
            print(f"下载 {name} ...")
            local_dir = DATA_DIR / local
            if source == "hf":
                download_hf(rid, local_dir)
            else:
                subprocess.run(
                    ["kaggle", "datasets", "download", "-d", rid, "-p", str(local_dir), "--unzip"],
                    check=True,
                )
        print("全部完成。")
        return
    list_datasets()


if __name__ == "__main__":
    main()
