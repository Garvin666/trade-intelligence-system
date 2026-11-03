"""Amazon Best Sellers 采集适配器（robots-aware，best-effort）。

说明：
- 默认情况下管道使用合成演示数据，保证离线可跑；本模块仅按需接入真实公开榜单。
- Amazon Best Sellers 解析改写自 scrape-do/amazon-scraper（MIT）：
  Source: https://github.com/scrape-do/amazon-scraper
  Audited commit: a27bd17bef4698472a32e8db696fa3c006c720f2
- 抓取前先查 robots.txt，不允许则返回 skipped；允许则限速并携带 User-Agent。
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from src.data.crawl_engine import LegalCrawlEngine
from src.data.http import BROWSER_USER_AGENT
from src.data.http import RobotsDisallowedError

HEADERS = {"User-Agent": BROWSER_USER_AGENT}

AMAZON_SCRAPER_SOURCE = (
    "Adapted from scrape-do/amazon-scraper (MIT) "
    "https://github.com/scrape-do/amazon-scraper "
    "commit a27bd17bef4698472a32e8db696fa3c006c720f2"
)


def parse_amazon_bestsellers(html: str) -> list[dict[str, Any]]:
    """解析 Amazon Best Sellers HTML 为规范化商品行。

    解析结构改写自 scrape-do/amazon-scraper 的 bestSellers.py。
    """
    soup = BeautifulSoup(html, "html.parser")
    products: list[dict[str, Any]] = []
    for index, item in enumerate(soup.find_all(class_="zg-no-numbers"), start=1):
        try:
            asin_elem = item if item.get("data-asin") else item.find(
                attrs={"data-asin": True}
            )
            asin = asin_elem.get("data-asin", "") if asin_elem else ""
            title = ""
            link = ""
            for a_tag in item.find_all("a", class_="a-link-normal"):
                href = a_tag.get("href", "")
                text = a_tag.get_text(strip=True)
                if "/dp/" in href and text:
                    link = (
                        href
                        if href.startswith("http")
                        else "https://www.amazon.com" + href
                    )
                    title = text
                    break
            price_tag = item.find(
                "span",
                class_=lambda cls: cls and "p13n-sc-price" in str(cls),
            )
            price = price_tag.get_text(strip=True) if price_tag else ""
            rating = ""
            review_count = ""
            star_icon = item.find(
                "i",
                class_=lambda cls: cls and "a-icon-star" in str(cls),
            )
            if star_icon:
                parent_link = star_icon.find_parent("a")
                if parent_link:
                    aria_label = parent_link.get("aria-label", "")
                    if aria_label and "stars" in aria_label:
                        parts = aria_label.split("stars")
                        rating = parts[0].strip() if parts[0] else ""
                        if len(parts) > 1:
                            review_count = (
                                parts[1].strip().lstrip(",").strip().replace(" ratings", "")
                            )
            if title:
                products.append(
                    {
                        "rank": str(index),
                        "asin": asin,
                        "title": title,
                        "price": price,
                        "rating": rating,
                        "review_count": review_count,
                        "link": link,
                    }
                )
        except Exception:  # noqa: BLE001 - 单条目解析失败跳过
            continue
    return products


def collect_amazon_bestsellers(
    url: str = "https://www.amazon.com/Best-Sellers/zgbs",
) -> pd.DataFrame:
    """Best-effort 抓取 Amazon 热销榜；robots 不允许时抛出 RobotsDisallowedError。"""
    engine = LegalCrawlEngine(user_agent=HEADERS["User-Agent"], delay=0.4, timeout=15)
    result = engine.fetch(url)
    if result.get("error"):
        raise RuntimeError(result["error"])
    rows = parse_amazon_bestsellers(result["html"])
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame.insert(0, "date", pd.Timestamp.today().date().isoformat())
        frame["source"] = "amazon_bestsellers"
        frame["adapted_from"] = AMAZON_SCRAPER_SOURCE
    return frame
