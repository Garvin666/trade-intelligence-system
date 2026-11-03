"""四脑工作台 132 品类产品库与选品差异化回归测试。"""

from __future__ import annotations

from src.api.examples import build_examples_payload
from src.config import CATEGORY_CATALOG
from src.four_brain import engine


def test_example_library_covers_all_categories() -> None:
    payload = build_examples_payload()
    four_brain = payload["four_brain"]
    launch = payload["launch_report"]

    assert len(four_brain) >= len(CATEGORY_CATALOG)
    assert len(launch) >= len(CATEGORY_CATALOG)
    categories = set()
    for item in four_brain:
        product = item["payload"]
        category = str(product.get("category") or "")
        if category not in CATEGORY_CATALOG:
            category, _ = engine.infer_category(str(product.get("keyword") or ""))
        categories.add(category)
    assert set(CATEGORY_CATALOG) <= categories


def test_normalize_payload_uses_category_defaults() -> None:
    payload = engine.normalize_payload(
        {
            "keyword": "龙井绿茶 longjing green tea",
            "market": "us",
            "category": "cn_frozen_dumplings",
        }
    )
    defaults = engine._category_defaults("cn_frozen_dumplings")
    assert payload["category"] == "cn_frozen_dumplings"
    assert payload["unit_cost"] == defaults["unit_cost"]
    assert payload["moq"] == defaults["moq"]
    assert payload["lead_time_days"] == defaults["lead_time_days"]
    assert payload["certifications"] == defaults["certifications"]


def test_same_category_products_differ_with_full_payload() -> None:
    latiao = {
        "keyword": "辣条 latiao spicy snack",
        "category": "cn_frozen_dumplings",
        "market": "us",
        "price_min": 25.0,
        "price_max": 45.0,
        "budget": 20000.0,
        "target_margin": 0.35,
        "unit_cost": 9.5,
        "freight_per_unit": 2.8,
        "customs_per_unit": 0.9,
        "ad_rate": 0.12,
        "return_rate": 0.03,
        "moq": 400,
        "lead_time_days": 35,
    }
    longjing = {
        "keyword": "龙井绿茶 longjing green tea",
        "category": "cn_frozen_dumplings",
        "market": "eu",
        "price_min": 45.0,
        "price_max": 90.0,
        "budget": 25000.0,
        "target_margin": 0.38,
        "unit_cost": 18.0,
        "freight_per_unit": 4.2,
        "customs_per_unit": 1.5,
        "ad_rate": 0.15,
        "return_rate": 0.04,
        "moq": 350,
        "lead_time_days": 45,
    }

    p1 = engine.normalize_payload(latiao)
    p2 = engine.normalize_payload(longjing)
    finance_1 = engine.analyze_finance(p1)
    finance_2 = engine.analyze_finance(p2)
    supply_1 = engine.analyze_supply_chain(p1)
    supply_2 = engine.analyze_supply_chain(p2)

    assert finance_1["metrics"]["unit_profit"] != finance_2["metrics"]["unit_profit"]
    assert finance_1["metrics"]["gross_margin"] != finance_2["metrics"]["gross_margin"]
    assert supply_1["metrics"]["landed_cost"] != supply_2["metrics"]["landed_cost"]
    assert finance_1["score"] != finance_2["score"] or supply_1["score"] != supply_2["score"]

    report_1 = engine.render_markdown(
        {"market": {"category_name": "速冻水饺"}, "finance": {"metrics": {}}},
        {"verdict": "谨慎", "score": 60, "base_score": 60, "risk_penalty": 0, "conflicts": []},
        p1,
    )
    report_2 = engine.render_markdown(
        {"market": {"category_name": "速冻水饺"}, "finance": {"metrics": {}}},
        {"verdict": "谨慎", "score": 60, "base_score": 60, "risk_penalty": 0, "conflicts": []},
        p2,
    )
    assert p1["keyword"] in report_1
    assert p2["keyword"] in report_2
