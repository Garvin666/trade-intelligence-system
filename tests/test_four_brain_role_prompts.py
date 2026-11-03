"""Role prompt wiring and detailed conclusion contract for the four-brain engine."""

from __future__ import annotations

from typing import Any

from src.four_brain import engine as four_brain


MINI_DATA = {
    "history": [
        {
            "date": "2026-01-01",
            "category": "cn_changsha_mifen",
            "market": "us",
            "sales_volume": 10,
            "search_index": 10,
            "competition_index": 10,
            "price_median": 10,
        }
    ],
    "recommendations": [],
}


class RecordingProvider:
    configured = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def chat_json(self, system: str, user: str, temperature: float = 0.2) -> dict[str, Any]:
        self.calls.append((system, user))
        if "财务精算师" in system:
            return {
                "score": 71,
                "confidence": 0.8,
                "direction": "推荐",
                "summary": "财务可行性偏积极。",
                "conclusion_points": ["毛利可接受", "现金流健康"],
                "evidence": ["e1"],
                "report": "# 财务简洁结论",
            }
        return {
            "score": 70,
            "confidence": 0.8,
            "direction": "推荐",
            "summary": "结论偏积极。",
            "conclusion_points": ["p1"],
            "evidence": ["e1"],
            "report": "# 简洁结论",
        }

    def status(self) -> dict[str, Any]:
        return {"configured": True}


def test_build_ai_prompts_embeds_matching_role_prompts() -> None:
    rule_result = four_brain.analyze(dict(four_brain.DEFAULT_PAYLOAD), MINI_DATA)
    prompts = four_brain.build_ai_prompts(
        rule_result["payload"],
        MINI_DATA,
        rule_result,
        role_prompts={
            "market": "只谈美国市场机会",
            "finance": "请特别关注现金流风险",
        },
    )
    assert "只谈美国市场机会" in prompts["market"]["user"]
    assert "请特别关注现金流风险" in prompts["finance"]["user"]
    assert "请特别关注现金流风险" not in prompts["market"]["user"]


def test_build_ai_prompts_uses_detailed_contract() -> None:
    rule_result = four_brain.analyze(dict(four_brain.DEFAULT_PAYLOAD), MINI_DATA)
    prompts = four_brain.build_ai_prompts(rule_result["payload"], MINI_DATA, rule_result)
    for prompt in prompts.values():
        text = prompt["user"] + prompt["system"]
        assert "summary" in text
        assert "conclusion_points" in text
        assert "最多 5 条" in text
        assert "不少于 600 字" in text


def test_analyze_with_ai_forwards_role_prompts_and_returns_points() -> None:
    payload = dict(four_brain.DEFAULT_PAYLOAD)
    payload["role_prompts"] = {"finance": "请特别关注现金流风险"}
    provider = RecordingProvider()
    result = four_brain.analyze_with_ai(payload, MINI_DATA, provider)
    finance_user = next(
        user
        for system, user in provider.calls
        if "财务精算师" in system
    )
    assert "请特别关注现金流风险" in finance_user
    finance = result["brains"]["finance"]
    assert finance["summary"] == "财务可行性偏积极。"
    assert finance["conclusion_points"] == ["毛利可接受", "现金流健康"]


def test_rule_brains_expose_summary_and_conclusion_points() -> None:
    result = four_brain.analyze(dict(four_brain.DEFAULT_PAYLOAD), MINI_DATA)
    for brain in result["brains"].values():
        assert brain["summary"]
        assert isinstance(brain["conclusion_points"], list)
        assert len(brain["conclusion_points"]) <= 5
