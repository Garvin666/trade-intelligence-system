"""绿色贸易与 CBAM 前瞻评估（离线演示版）。

按市场 / 品类输出欧盟 CBAM 暴露度、预估碳成本与趋势建议。
真实场景可替换为 CBAM 申报数据与碳排因子库。
"""

from __future__ import annotations

from dataclasses import dataclass
from src.config import CATEGORY_CATALOG, MARKETS


@dataclass(frozen=True)
class GreenSignal:
    market: str
    category: str
    exposure: str
    carbon_cost_usd: float
    trend: str
    risk: str
    recommendation: str


# 绿色贸易与 CBAM：食品均属低隐含碳暴露（无高耗能工业品），
# 全品类、全市场统一为 "low"，由 132 食品 SKU 与 MARKETS 派生。
GREEN_EXPOSURE: dict[str, dict[str, str]] = {
    market: {code: "low" for code in CATEGORY_CATALOG}
    for market in MARKETS
}


GREEN_TREND = {"eu": "rising", "us": "flat", "sea": "flat", "jp": "flat", "ca": "flat", "au": "flat", "uk": "rising", "kr": "flat", "de": "rising", "fr": "flat", "vn": "flat", "ru": "flat", "hu": "rising", "ae": "flat", "mx": "flat"}

_COST_RATE = {"high": 0.03, "medium": 0.012, "low": 0.0}


class GreenAssessor:
    """评估目标市场的 CBAM 暴露度与碳成本趋势。"""

    def assess(self, category: str, market: str, unit_price_usd: float) -> GreenSignal:
        exposure = GREEN_EXPOSURE[market][category]
        carbon_cost = round(unit_price_usd * _COST_RATE[exposure], 2)
        trend = GREEN_TREND[market]
        risk = exposure if exposure in {"high", "medium"} else "low"

        if exposure == "high":
            recommendation = (
                "CBAM 覆盖品类，建议优先完成隐含碳排放核算与供应商碳数据收集，预留碳成本。"
            )
        elif exposure == "medium" and market == "eu":
            recommendation = (
                "欧盟 CBAM 试运行期政策仍可能扩展，建议建立碳成本基线并持续跟踪申报要求。"
            )
        else:
            recommendation = "当前 CBAM 暴露度低，可将其作为 ESG 叙事与品牌溢价点。"

        return GreenSignal(
            market=market,
            category=category,
            exposure=exposure,
            carbon_cost_usd=carbon_cost,
            trend=trend,
            risk=risk,
            recommendation=recommendation,
        )
