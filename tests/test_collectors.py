"""Google Trends / 平台榜单采集与回退测试。"""

from __future__ import annotations

from src.data.crawler_signals import compute_credibility, detect_conflicts
from src.data.platform_rankings import collect_rankings, rankings_status
from src.data.trends import collect_trends, trends_status


def test_trends_offline_uses_deterministic_fallback() -> None:
    payload = collect_trends(offline=True, weeks=12)
    assert payload["fallback_used"] is True
    assert payload["provider"] == "mock"
    assert payload["series_count"] > 0
    assert len(payload["rows"]) > 0
    status = trends_status(payload)
    assert status["enabled"] is True
    assert status["fallback_used"] is True


def test_rankings_offline_uses_mock() -> None:
    payload = collect_rankings(offline=True)
    assert payload["fallback_used"] is True
    assert payload["source_count"] > 0
    assert payload["rows"][0]["platform"] == "mock"
    status = rankings_status(payload)
    assert status["enabled"] is True
    assert status["rows"] == payload["source_count"]


def test_credibility_and_conflicts() -> None:
    score, level = compute_credibility([{"title": "a"}], [], True)
    assert score <= 40
    assert level == "low"
    conflicts = detect_conflicts([{"title": "totally unrelated"}], "latiao spicy snack")
    assert any(item["type"] == "keyword_pollution" for item in conflicts)


def test_amazon_bestsellers_parser_fixture() -> None:
    from src.data.collector import parse_amazon_bestsellers

    html = """
    <div class="zg-no-numbers" data-asin="B0TEST">
      <a class="a-link-normal" href="/dp/B0TEST">Test Product</a>
      <span class="p13n-sc-price">$19.99</span>
      <a href="#" aria-label="4.7 out of 5 stars 123 ratings">
        <i class="a-icon a-icon-star-small"></i>
      </a>
    </div>
    """
    products = parse_amazon_bestsellers(html)
    assert len(products) == 1
    assert products[0]["title"] == "Test Product"
    assert products[0]["asin"] == "B0TEST"
    assert products[0]["price"] == "$19.99"
    assert products[0]["rating"] == "4.7 out of 5"
    assert products[0]["review_count"] == "123"


def test_ebay_github_sample_provider(monkeypatch, tmp_path) -> None:
    import pandas as pd
    import src.data.platform_rankings as rankings

    (tmp_path / "ebay").mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "title": "Changsha Rice Noodles 长沙米粉 Spicy Rice Noodles",
                "root_category": "Grocery & Gourmet Food",
                "item_location": "United States",
                "currency": "USD",
                "ships_to": "Worldwide",
                "price": 29.99,
                "sold_count": 120,
                "url": "https://www.ebay.com/itm/123",
            }
        ]
    ).to_csv(tmp_path / "ebay" / "sample.csv", index=False, encoding="utf-8")
    monkeypatch.setattr(rankings, "GITHUB_DATA_DIR", tmp_path)

    rows = rankings._ebay_github_rows(["cn_changsha_mifen"], ["us"])
    assert rows
    assert rows[0]["platform"] == "ebay_github"
    assert rows[0]["product"] == "Changsha Rice Noodles 长沙米粉 Spicy Rice Noodles"
    assert rows[0]["sold_count"] == 120

    payload = rankings.collect_rankings(providers=["ebay_github"], offline=False)
    assert payload["providers"]["ebay_github"]["status"] == "ok"
    assert any(row["platform"] == "ebay_github" for row in payload["rows"])


def test_amazon_github_sample_provider(monkeypatch, tmp_path) -> None:
    import pandas as pd
    import src.data.platform_rankings as rankings

    (tmp_path / "amazon").mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "title": "Changsha Rice Noodles for Hot Pot 长沙米粉",
                "root_bs_category": "Grocery & Gourmet Food",
                "domain": "amazon.com",
                "root_bs_rank": 12,
                "final_price": 39.99,
                "rating": 4.5,
                "url": "https://www.amazon.com/dp/B0TEST",
            }
        ]
    ).to_csv(tmp_path / "amazon" / "sample.csv", index=False, encoding="utf-8")
    monkeypatch.setattr(rankings, "GITHUB_DATA_DIR", tmp_path)

    rows = rankings._amazon_github_rows(["cn_changsha_mifen"], ["us"])
    assert rows
    assert rows[0]["platform"] == "amazon_github"
    assert rows[0]["product"] == "Changsha Rice Noodles for Hot Pot 长沙米粉"
    assert rows[0]["root_bs_rank"] == 12

    payload = rankings.collect_rankings(providers=["amazon_github"], offline=False)
    assert payload["providers"]["amazon_github"]["status"] == "ok"
    assert any(row["platform"] == "amazon_github" for row in payload["rows"])
