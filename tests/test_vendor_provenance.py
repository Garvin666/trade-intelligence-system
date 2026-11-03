"""第三方来源记录与许可证完整性测试。"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = PROJECT_ROOT / "third_party" / "PROVENANCE.md"


def test_provenance_file_exists_and_has_license_audit() -> None:
    assert PROVENANCE.exists()
    content = PROVENANCE.read_text(encoding="utf-8")
    assert "许可证与来源" in content
    assert "仅参考思路，不复制代码" in content


def test_saved_license_files_exist() -> None:
    content = PROVENANCE.read_text(encoding="utf-8")
    license_entries = re.findall(r"`(third_party/[\w./\-]+LICENSE)`", content)
    assert license_entries
    for relative in license_entries:
        assert (PROJECT_ROOT / relative).exists(), relative


def test_new_dependency_licenses_registered() -> None:
    content = PROVENANCE.read_text(encoding="utf-8")
    for repo in (
        "GeneralMills/pytrends",
        "uncomtrade/comtradeapicall",
        "Data-Centric-AI-Community/fg-data-profiling",
        "maximtrp/scikit-posthocs",
        "yzhao062/pyod",
        "999Diogo/keepa",
        "eBay/ebaysdk",
    ):
        assert repo in content


def test_amazon_scraper_provenance_and_source_header() -> None:
    content = PROVENANCE.read_text(encoding="utf-8")
    assert "scrape-do/amazon-scraper" in content
    assert "hughie21/Customs-Crawler" in content
    license_path = (
        PROJECT_ROOT
        / "third_party"
        / "scrape-do"
        / "amazon-scraper"
        / "LICENSE"
    )
    assert license_path.exists()
    collector = PROJECT_ROOT / "src" / "data" / "collector.py"
    text = collector.read_text(encoding="utf-8")
    assert "scrape-do/amazon-scraper" in text
    assert "a27bd17bef4698472a32e8db696fa3c006c720f2" in text
