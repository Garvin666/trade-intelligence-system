"""Open Food Facts official API adapter tests."""

from __future__ import annotations

from typing import Any

from src.config import CATEGORIES
from src.data import open_food_facts as off


def _search_payload() -> dict[str, Any]:
    return {
        "count": 2,
        "products": [
            {
                "code": "3017620422003",
                "product_name": "Plant Snack",
                "brands": "DemoBrand",
                "nutrition_grades": "b",
                "countries_tags_en": ["united-states"],
                "unique_scans_n": 1234,
                "last_modified_t": 1710000000,
            },
            {
                "code": "",
                "product_name": "",
                "brands": "",
                "nutrition_grades": "",
                "countries_tags_en": [],
                "unique_scans_n": 0,
                "last_modified_t": None,
            },
        ],
    }


def test_parse_open_food_facts_search() -> None:
    rows = off.parse_open_food_facts_search(
        _search_payload(),
        category="cn_latiao",
        keyword="latiao spicy snack",
        market="us",
    )
    assert len(rows) == 1
    assert rows[0]["product_code"] == "3017620422003"
    assert rows[0]["product_name"] == "Plant Snack"
    assert rows[0]["unique_scans"] == 1234
    assert rows[0]["source"] == "open_food_facts"
    assert rows[0]["fallback_used"] is False
    assert rows[0]["market"] == "us"


def test_offline_returns_marked_mock() -> None:
    payload = off.collect_open_food_facts(
        keywords={"cn_latiao": "latiao spicy snack"},
        markets=["us", "uk"],
        offline=True,
    )
    assert payload["provider"] == "mock"
    assert payload["fallback_used"] is True
    assert payload["coverage"]["real"] == 0
    assert payload["coverage"]["mock"] == 2
    assert all(row["source"] == "mock" for row in payload["rows"])
    assert all(row["fallback_used"] is True for row in payload["rows"])


def test_status_shape() -> None:
    payload = off.collect_open_food_facts(
        keywords={"cn_latiao": "latiao spicy snack"},
        markets=["us"],
        offline=True,
    )
    status = off.open_food_facts_status(payload)
    assert status["enabled"] is True
    assert status["provider"] == "mock"
    assert status["snapshot"] == "output/open_food_facts/latest.json"
    assert status["rows"] == payload["source_count"]


class _FakeApi:
    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, params: dict[str, Any]) -> Any:
        self.calls.append((url, params))
        market = (params or {}).get("countries_tags_en", "").split(",")[0]
        if market not in self.payloads:
            raise RuntimeError(f"no payload for {market}")
        return self.payloads[market]


def test_real_provider_uses_api_and_trimmed_fields(monkeypatch) -> None:
    payload = _search_payload()
    fake = _FakeApi({"united-states": payload})
    monkeypatch.setattr(off, "_official_api_get_json", fake)

    result = off.collect_open_food_facts(
        keywords={"cn_latiao": "latiao spicy snack"},
        markets=["us"],
    )
    assert result["provider"] == "open_food_facts"
    assert result["fallback_used"] is False
    assert result["rows"]
    assert fake.calls
    _, params = fake.calls[0]
    assert params["sort_by"] == "unique_scans_n"
    assert "|" in params["categories_tags_en"]
    assert "," not in params["countries_tags_en"]
    assert "product_name" in params["fields"]


def test_partial_market_failure_falls_back(monkeypatch) -> None:
    payload = _search_payload()
    fake = _FakeApi({"united-states": payload})
    monkeypatch.setattr(off, "_official_api_get_json", fake)

    result = off.collect_open_food_facts(
        keywords={"cn_latiao": "latiao spicy snack"},
        markets=["us", "uk"],
    )
    assert result["fallback_used"] is True
    assert result["coverage"]["real"] == 1
    assert result["coverage"]["mock"] == 1
    assert any(row["source"] == "open_food_facts" for row in result["rows"])
    assert any(row["source"] == "mock" for row in result["rows"])


def test_off_category_tags_intersect_food_catalog() -> None:
    """回归守卫：OFF 类目表的键必须全部命中食品 SKU 目录。

    旧版该类目表的键是通用 "food"，食品化切换后与 CATEGORIES 的交集恒为空，
    真实采集会静默返回 0 条（provider 退化为 mock）而完全不报错。
    """
    assert off.OFF_CATEGORY_TAGS, "OFF 类目表不能为空"
    matched = [code for code in off.OFF_CATEGORY_TAGS if code in CATEGORIES]
    assert matched == list(off.OFF_CATEGORY_TAGS), (
        "OFF 类目表存在不在食品 SKU 目录中的键："
        f"{sorted(set(off.OFF_CATEGORY_TAGS) - set(CATEGORIES))}"
    )
    assert off.default_off_category() in CATEGORIES


def test_empty_intersection_reports_error_instead_of_silent_success(monkeypatch) -> None:
    """类目表与 SKU 目录脱节时必须显式留痕并回退 mock，而不是伪装成成功。"""
    monkeypatch.setattr(off, "OFF_CATEGORY_TAGS", {"food": ("snacks",)})

    result = off.collect_open_food_facts(markets=["us"])

    assert result["provider"] == "mock"
    assert result["coverage"]["real"] == 0
    assert any("无交集" in err for err in result["errors"])
    assert result["rows"]
