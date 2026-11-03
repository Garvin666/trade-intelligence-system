"""Shared policy-normalization helpers used by policy_sources and policy_refresh.

These were previously duplicated across the two modules. They handle date
parsing, duty/rate extraction, impact classification and the action map.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_RESTRICTIVE = (
    "取消",
    "加征",
    "上调",
    "禁止",
    "限制",
    "收紧",
    "处罚",
    "强化",
    "increase",
    "raise",
    "remove",
    "ban",
    "restrict",
    "tighten",
)

_FACILITATIVE = (
    "支持",
    "促进",
    "减税",
    "降费",
    "补贴",
    "便利化",
    "放宽",
    "简化",
    "开放",
    "扩容",
    "试点",
    "support",
    "promote",
    "reduce",
    "simplify",
    "expand",
)

_CUSTOMS_TRADE_TERMS = (
    "de minimis",
    "low value",
    "低值",
    "跨境电商",
    "e-commerce",
    "cross border",
    "duty-free",
    "免税",
    "清关",
    "tariff",
)

ACTION_MAP = {
    "tariff": ("核对清关方式", "转正式清关", "调整定价"),
    "vat": ("注册 IOSS / VAT", "调整定价", "核对低值免税额度"),
    "rebate": ("核对出口退税档位", "更新报关价格"),
    "customs": ("更新报关资质", "预留通关时间"),
    "compliance": ("核对目标国合规要求", "更新产品认证"),
    "macro": ("关注配套细则", "评估经营影响"),
    "news": ("持续监控", "评估经营影响"),
}


def clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def normalize_date(value: Any, default: str | None = None) -> str:
    if value is None or str(value).strip() in ("", "None"):
        return default or date.today().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.search(r"(\d{4})[/.](\d{1,2})[/.](\d{1,2})", text)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})", text)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return default or date.today().isoformat()


def extract_rate(text: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if not match:
        return 0.0
    return round(float(match.group(1)) / 100.0, 4)


def extract_min_duty(text: str) -> float:
    match = re.search(r"\$\s*(\d+(?:\.\d+)?)", text)
    if not match:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:美元|USD)", text)
    if not match:
        return 0.0
    return round(float(match.group(1)), 2)


def classify(text: str) -> tuple[str, str]:
    lowered = text.lower()
    strong_restrict = (
        "取消",
        "加征",
        "禁止",
        "限制",
        "收紧",
        "处罚",
        "remove",
        "ban",
        "restrict",
    )
    if any(keyword in text for keyword in _RESTRICTIVE) or any(
        keyword in lowered
        for keyword in ("increase", "raise", "remove", "ban", "restrict", "tighten")
    ):
        impact = (
            "high"
            if any(keyword in text for keyword in strong_restrict)
            or any(keyword in lowered for keyword in ("remove", "ban", "restrict"))
            else "medium"
        )
        return impact, "restrict"
    if any(keyword in text for keyword in _FACILITATIVE) or any(
        keyword in lowered
        for keyword in ("support", "promote", "reduce", "simplify", "expand")
    ):
        impact = (
            "medium"
            if any(keyword in text for keyword in ("试点", "扩容", "调整", "优化"))
            else "low"
        )
        return impact, "facilitate"
    return "low", "neutral"


def business_impact_level(
    policy_type: str,
    rate_ad_valorem: float = 0.0,
    min_duty_usd: float = 0.0,
    cost_adjustment_pct: float = 0.0,
    categories: tuple[str, ...] | list[str] = (),
    text: str = "",
) -> str:
    """Derive display impact from trade-business semantics rather than raw wording.

    Numeric tariff/VAT/cost changes and category-specific events are the only
    ``high``/``medium`` signals; generic customs or compliance announcements
    are treated as low-reference items so the radar never inverts priorities.
    """
    rate = max(0.0, float(rate_ad_valorem or 0.0))
    min_duty = max(0.0, float(min_duty_usd or 0.0))
    cost_adj = abs(float(cost_adjustment_pct or 0.0))
    if rate >= 0.20 or min_duty >= 50.0 or cost_adj >= 0.5:
        return "high"
    if rate > 0.0 or min_duty > 0.0 or cost_adj > 1e-9:
        return "medium"
    if categories:
        return "medium"
    lowered = f"{policy_type} {text}".lower()
    if policy_type in ("tariff", "vat", "rebate") and any(
        term in lowered for term in _CUSTOMS_TRADE_TERMS
    ):
        return "medium"
    if policy_type == "customs" and any(
        term in lowered for term in _CUSTOMS_TRADE_TERMS
    ):
        return "medium"
    return "low"


def actions_for(policy_type: str, impact_level: str) -> list[str]:
    actions = list(ACTION_MAP.get(policy_type, ("持续监控政策公告",)))
    return actions[:2] if impact_level == "low" else actions


__all__ = [
    "ACTION_MAP",
    "actions_for",
    "business_impact_level",
    "classify",
    "clean_text",
    "extract_min_duty",
    "extract_rate",
    "normalize_date",
]
