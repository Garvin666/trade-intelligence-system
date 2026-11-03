"""Fetch public GitHub dataset samples into data/external/github.

Usage:
    python scripts/fetch_github_datasets.py            # download missing samples
    python scripts/fetch_github_datasets.py --offline  # validate local files only
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import GITHUB_DATA_DIR  # noqa: E402

SOURCES = [
    {
        "provider": "amazon",
        "url": "https://codeload.github.com/luminati-io/Amazon-dataset-samples/zip/refs/heads/main",
        "expected": ("amazon-products.csv",),
    },
    {
        "provider": "ebay",
        "url": "https://codeload.github.com/luminati-io/eBay-dataset-sample/zip/refs/heads/main",
        "expected": ("eBay-dataset-sample.csv",),
    },
    {
        "provider": "shopee",
        "url": "https://codeload.github.com/rebrowser/shopee-dataset/zip/refs/heads/main",
        "expected": ("product-details/data/2026-07-29.parquet",),
    },
    {
        "provider": "octaprice",
        "url": "https://codeload.github.com/octaprice/ecommerce-product-dataset/zip/refs/heads/main",
        "expected": ("amazon_com_bird_food_2025_01_24.csv",),
    },
    {
        "provider": "hs",
        "url": "https://codeload.github.com/datasets/harmonized-system/zip/refs/heads/main",
        "expected": ("data/harmonized-system.csv", "data/sections.csv"),
    },
]


def _has_expected(provider_dir: Path, expected: tuple[str, ...]) -> bool:
    return any((provider_dir / name).exists() for name in expected)


def _download_and_extract(source: dict[str, object], base_dir: Path) -> None:
    provider = str(source["provider"])
    provider_dir = base_dir / provider
    provider_dir.mkdir(parents=True, exist_ok=True)
    archive = base_dir / f"_{provider}_download.zip"
    url = str(source["url"])
    print(f"[download] {provider} <- {url}")
    with requests.get(url, stream=True, timeout=1800) as resp:
        resp.raise_for_status()
        with archive.open("wb") as handle:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    handle.write(chunk)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(provider_dir)
    archive.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch/validate GitHub dataset samples")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="validate local files only; do not download",
    )
    args = parser.parse_args(argv)
    base_dir = GITHUB_DATA_DIR
    missing: list[str] = []
    for source in SOURCES:
        provider = str(source["provider"])
        expected = tuple(source["expected"])
        provider_dir = base_dir / provider
        present = _has_expected(provider_dir, expected)
        if present:
            print(f"[ok] {provider} already present")
        elif args.offline:
            missing.append(provider)
            print(f"[missing] {provider}: expected {', '.join(expected)}")
        else:
            _download_and_extract(source, base_dir)
            if not _has_expected(provider_dir, expected):
                missing.append(provider)
                print(f"[failed] {provider}: expected files not found after download")
            else:
                print(f"[ok] {provider} downloaded")
    if missing:
        print(f"缺失来源: {', '.join(missing)}")
        return 1
    print("GitHub dataset samples ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
