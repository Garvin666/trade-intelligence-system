"""卖前合规体检清单。

借鉴 ``JuneYaooo/launchfit-ai`` 的“出海体检”思路（该仓库 LICENSE 为
NOASSERTION，仅参考清单结构，不复制代码），基于项目现有合规、物流与成本模块
生成可逐项勾选的卖前体检结果。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.config import CATEGORY_PARAMS
from src.trade.compliance import ComplianceAssessor, ComplianceResult
from src.trade.cost import DEFAULT_FX_RATE, LandedCostCalculator, LandedCostInput
from src.trade.logistics import FreightForecaster
from src.trade.policy import BASE_TARIFF_RATE


@dataclass(frozen=True)
class PreflightItem:
    group: str
    item: str
    status: str  # pass / attention / pending
    note: str

    def to_dict(self) -> dict[str, str]:
        return {
            "group": self.group,
            "item": self.item,
            "status": self.status,
            "note": self.note,
            # 前端兼容别名（TradeResultDetail 读取 name/message，见建议报告 S9）
            "name": self.item,
            "message": self.note,
        }


@dataclass(frozen=True)
class PreflightResult:
    category: str
    market: str
    items: tuple[PreflightItem, ...]
    ready: bool
    score: float
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "market": self.market,
            "items": [item.to_dict() for item in self.items],
            "ready": self.ready,
            "score": self.score,
            "recommendation": self.recommendation,
        }


def _default_margin(category: str, market: str) -> float:
    price = float(CATEGORY_PARAMS.get(category, {}).get("price", 30.0))
    tariff = BASE_TARIFF_RATE.get(market, {}).get(category, 0.0)
    result = LandedCostCalculator().calculate(
        LandedCostInput(
            category=category,
            market=market,
            unit_price_usd=price,
            procurement_cost_cny=price * DEFAULT_FX_RATE * 0.35,
            tariff_rate=tariff,
        )
    )
    return result.margin_pct


def build_preflight(
    category: str,
    market: str,
    *,
    margin_pct: float | None = None,
    freight_risk: str | None = None,
    compliance_result: ComplianceResult | None = None,
) -> PreflightResult:
    """生成卖前体检清单并按准入/标签/认证/物流/定价分组。"""
    compliance = compliance_result or ComplianceAssessor().assess(market)
    margin = margin_pct if margin_pct is not None else _default_margin(category, market)
    freight = freight_risk or FreightForecaster().forecast(market).risk

    items: list[PreflightItem] = []

    required = [item for item in compliance.requirements if item.required]
    optional = [item for item in compliance.requirements if not item.required]
    if required:
        hardest = max(required, key=lambda item: item.duration_days)
        status = "pass" if hardest.cost_usd <= 1200 and hardest.duration_days <= 21 else "attention"
        items.append(
            PreflightItem(
                "准入",
                f"{market.upper()} 必需认证/准入",
                status,
                f"最高成本 ${hardest.cost_usd:.0f} / {hardest.duration_days} 天，需预留办理周期",
            )
        )
    for item in optional:
        items.append(
            PreflightItem(
                "准入",
                item.item,
                "attention",
                f"{item.note}，可选认证按实际品类确认",
            )
        )

    label_markets = {"fr", "jp", "kr", "de", "ru", "mx", "hu", "ae"}
    items.append(
        PreflightItem(
            "标签",
            "本地语言标签与说明书",
            "attention" if market in label_markets else "pass",
            "需按目标国语言准备标签/说明书" if market in label_markets else "无额外语言要求",
        )
    )

    items.append(
        PreflightItem(
            "物流",
            "物流时效与清关稳定性",
            "pass" if freight == "low" else "attention",
            "当前运价与时效风险较低" if freight == "low" else f"物流风险等级：{freight}",
        )
    )

    if margin >= 20:
        pricing_status = "pass"
        pricing_note = f"估算利润率 {margin:.1f}%，定价空间充足"
    elif margin >= 10:
        pricing_status = "attention"
        pricing_note = f"估算利润率 {margin:.1f}%，建议优化采购或物流成本"
    else:
        pricing_status = "pending"
        pricing_note = f"估算利润率 {margin:.1f}%，需重新定价或更换货源"
    items.append(PreflightItem("定价", "定价与利润空间", pricing_status, pricing_note))

    status_weight = {"pass": 100.0, "attention": 60.0, "pending": 40.0}
    score = round(sum(status_weight[item.status] for item in items) / max(len(items), 1), 1)
    ready = all(item.status == "pass" for item in items)
    if ready:
        recommendation = "卖前体检通过，可按计划进入备货与上架。"
    elif score >= 75:
        recommendation = "整体可控，但存在待确认项，建议先补齐认证/标签/定价后再批量备货。"
    else:
        recommendation = "存在多项待确认或高风险项，建议先小批量试单验证。"

    return PreflightResult(
        category=category,
        market=market,
        items=tuple(items),
        ready=ready,
        score=score,
        recommendation=recommendation,
    )


__all__ = ["PreflightItem", "PreflightResult", "build_preflight"]
