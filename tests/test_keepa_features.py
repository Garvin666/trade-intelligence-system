"""B-2 Keepa 可选源：衍生特征、token 成本估算、降级来源层级标注。"""

from __future__ import annotations

from src.data.platform_rankings import _source_level, _keepa_rows
from src.features.keepa_features import (
    bsr_volatility,
    discount_noise,
    estimate_keepa_tokens,
    keepa_features,
    price_elasticity,
    price_stability,
    promo_anomaly,
)


def _product(price_values: list[float], rank_values: list[float] | None = None) -> dict:
    product = {"title": "测试商品", "price": price_values}
    if rank_values is not None:
        product["salesRankReference"] = rank_values
    return product


def test_price_stability_high_for_stable_price() -> None:
    stable = _product([10.0, 10.2, 10.1, 10.0, 10.3, 10.2, 10.1, 10.0])
    volatile = _product([10.0, 5.0, 12.0, 6.0, 11.0, 5.5, 12.5, 6.5])
    assert price_stability(stable) > price_stability(volatile)
    assert 0.0 <= price_stability(stable) <= 1.0


def test_discount_noise_reflects_price_volatility() -> None:
    flat = _product([10.0] * 8)
    noisy = _product([10.0, 8.0, 12.0, 7.0, 11.0, 8.5, 12.5, 9.0])
    assert discount_noise(noisy) > discount_noise(flat)
    assert discount_noise(flat) == 0.0


def test_bsr_volatility_and_elasticity() -> None:
    product = _product(
        [10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
        rank_values=[100, 200, 300, 400, 500, 600],
    )
    assert bsr_volatility(product) is not None
    elasticity = price_elasticity(product)
    assert elasticity is not None
    assert elasticity > 0.9  # 价格与排名同向 → 正相关


def test_promo_anomaly_counts_drops() -> None:
    product = _product([10.0, 7.0, 10.0, 6.0, 10.0, 10.0])
    promo = promo_anomaly(product)
    assert promo is not None
    assert promo["events"] == 2  # 10→7 与 10→6 两处骤降（跌幅 ≥15%）


def test_keepa_features_missing_data_is_tolerant() -> None:
    features = keepa_features({"title": "无历史"})
    assert features["keepa_price_stability"] is None
    assert features["keepa_discount_noise"] is None
    assert features["keepa_bsr_volatility"] is None
    assert features["keepa_price_elasticity"] is None
    assert features["keepa_promo_events"] is None


def test_estimate_keepa_tokens_scales_with_asins() -> None:
    small = estimate_keepa_tokens(1)
    large = estimate_keepa_tokens(5)
    assert large["total_tokens_est"] > small["total_tokens_est"]
    assert large["asins"] == 5
    assert "估算" in large["note"]


def test_keepa_rows_skipped_without_key(monkeypatch) -> None:
    monkeypatch.setattr("src.data.platform_rankings.KEEPA_API_KEY", "")
    rows, fallback, note = _keepa_rows(["cn_changsha_mifen"], ["us"])
    assert rows == []
    assert fallback is True
    assert "缺少 KEEPA_API_KEY" in note


def test_source_level_classification() -> None:
    assert _source_level({}) == "无数据"
    keepa = {
        "providers": {
            "amazon_github": {"status": "ok", "note": "amazon_github"},
            "keepa": {"status": "skipped", "note": "缺少 KEEPA_API_KEY"},
        }
    }
    assert "官方免费样例" in _source_level(keepa)
    mock = {"providers": {"mock": {"status": "fallback", "note": "mock"}}}
    assert "合成回退" in _source_level(mock)
