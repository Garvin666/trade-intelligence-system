"""数据信用与供应链金融就绪度评估（离线演示版）。

将政策风险、物流风险、利润空间与经营数据覆盖度映射为可解释的融资就绪评分，
为远期对接脱敏经营数据信用模型与金融机构预留接口。
真实场景可替换为订单履约、退款、回款与物流妥投等授权经营数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from src.config import CATEGORY_CATALOG


@dataclass(frozen=True)
class CreditSignal:
    category: str
    market: str
    data_coverage_score: float
    order_stability: str
    completion_rate: float
    return_rate: float
    policy_risk_score: float
    financing_ready_score: float
    financing_level: str
    recommended_data: tuple[str, ...]
    recommendation: str


MARKET_PROFILES: dict[str, dict[str, float | str]] = {
    "us": {"stability": "high", "completion_rate": 98.6, "return_rate": 4.2, "data_coverage": 84.0},
    "eu": {"stability": "medium", "completion_rate": 97.8, "return_rate": 6.1, "data_coverage": 82.0},
    "sea": {"stability": "medium", "completion_rate": 96.9, "return_rate": 8.4, "data_coverage": 76.0},
    "jp": {"stability": "high", "completion_rate": 98.1, "return_rate": 5.0, "data_coverage": 80.0},
    "ca": {"stability": "medium", "completion_rate": 97.6, "return_rate": 5.6, "data_coverage": 81.0},
    "au": {"stability": "medium", "completion_rate": 97.4, "return_rate": 5.9, "data_coverage": 79.0},
    "uk": {"stability": "medium", "completion_rate": 97.9, "return_rate": 5.7, "data_coverage": 81.0},
    "kr": {"stability": "high", "completion_rate": 98.3, "return_rate": 4.8, "data_coverage": 80.0},
    "de": {"stability": "medium", "completion_rate": 97.9, "return_rate": 5.9, "data_coverage": 82.0},
    "fr": {"stability": "medium", "completion_rate": 97.7, "return_rate": 6.2, "data_coverage": 81.0},
    "vn": {"stability": "medium", "completion_rate": 95.8, "return_rate": 9.2, "data_coverage": 72.0},
    "ru": {"stability": "medium", "completion_rate": 96.5, "return_rate": 7.8, "data_coverage": 74.0},
    "hu": {"stability": "medium", "completion_rate": 97.2, "return_rate": 6.4, "data_coverage": 78.0},
    "ae": {"stability": "medium", "completion_rate": 97.0, "return_rate": 6.8, "data_coverage": 77.0},
    "mx": {"stability": "medium", "completion_rate": 96.2, "return_rate": 8.6, "data_coverage": 73.0},
}

# 食品品类信用调整：由 132 个食品 SKU 目录派生，剔除全部消费类目硬编码。
# 冷链（冷藏/冷冻）品类履约稳定性略降、退货率略升；常温食品最稳。
CATEGORY_ADJUST: dict[str, dict[str, float | str]] = {
    code: {
        "stability": "medium" if meta["storage_type"] in ("冷藏", "冷冻") else "high",
        "completion_delta": -0.2 if meta["storage_type"] in ("冷藏", "冷冻") else 0.0,
        "return_delta": 1.2 if meta["storage_type"] in ("冷藏", "冷冻") else 0.6,
    }
    for code, meta in CATEGORY_CATALOG.items()
}


STABILITY_SCORE = {"high": 95.0, "medium": 78.0, "low": 58.0}
POLICY_PENALTY = {"low": 0.0, "medium": 8.0, "high": 18.0}
FREIGHT_PENALTY = {"low": 0.0, "medium": 5.0, "high": 12.0}
RECOMMENDED_DATA = (
    "订单履约率",
    "退款与售后率",
    "回款周期",
    "物流妥投率",
    "平台店铺评分",
    "税务与主体合规",
)


def _combined_stability(category_stability: str, market_stability: str) -> str:
    order = ("low", "medium", "high")
    return order[min(order.index(category_stability), order.index(market_stability))]


def _margin_penalty(margin_pct: float) -> float:
    if margin_pct < 8.0:
        return 14.0
    if margin_pct < 15.0:
        return 8.0
    if margin_pct < 22.0:
        return 3.0
    return 0.0


class CreditAssessor:
    """评估品类 / 市场组合的数据信用与供应链金融就绪度。"""

    def assess(
        self,
        category: str,
        market: str,
        margin_pct: float,
        policy_risk: str = "low",
        freight_risk: str = "low",
    ) -> CreditSignal:
        market_profile = MARKET_PROFILES[market]
        category_adjust = CATEGORY_ADJUST[category]
        market_stability = str(market_profile["stability"])
        category_stability = str(category_adjust["stability"])
        stability = _combined_stability(category_stability, market_stability)

        completion_rate = round(
            float(market_profile["completion_rate"]) + float(category_adjust["completion_delta"]),
            1,
        )
        return_rate = round(
            float(market_profile["return_rate"]) + float(category_adjust["return_delta"]),
            1,
        )
        data_coverage = float(market_profile["data_coverage"])
        policy_risk_score = max(0.0, 100.0 - POLICY_PENALTY.get(policy_risk, 0.0))
        risk_score = max(
            0.0,
            100.0
            - POLICY_PENALTY.get(policy_risk, 0.0)
            - FREIGHT_PENALTY.get(freight_risk, 0.0)
            - _margin_penalty(margin_pct),
        )
        completion_component = min(100.0, max(0.0, (completion_rate - 90.0) * 10.0))
        return_component = min(100.0, max(0.0, 100.0 - return_rate * 6.0))
        financing_ready_score = round(
            0.25 * data_coverage
            + 0.20 * STABILITY_SCORE[stability]
            + 0.15 * completion_component
            + 0.10 * return_component
            + 0.30 * risk_score,
            1,
        )

        if financing_ready_score >= 85.0:
            financing_level = "可对接供应链金融"
            recommendation = (
                "数据覆盖与履约稳定性较高，可对接平台金融或银行贸易融资；"
                "正式授信前建议沉淀订单、回款与税务数据。"
            )
        elif financing_ready_score >= 70.0:
            financing_level = "可对接信用贷"
            recommendation = (
                "融资就绪度中等，建议补齐履约与回款数据并观察 1-2 个账期后再申请信用贷。"
            )
        elif financing_ready_score >= 55.0:
            financing_level = "小额试单"
            recommendation = "暂以小额定金或赊销试点为主，先积累稳定订单与履约记录。"
        else:
            financing_level = "暂不建议"
            recommendation = "当前政策、履约或利润风险偏高，建议先调整品类 / 市场策略，暂缓融资申请。"

        return CreditSignal(
            category=category,
            market=market,
            data_coverage_score=data_coverage,
            order_stability=stability,
            completion_rate=completion_rate,
            return_rate=return_rate,
            policy_risk_score=round(policy_risk_score, 1),
            financing_ready_score=financing_ready_score,
            financing_level=financing_level,
            recommended_data=RECOMMENDED_DATA,
            recommendation=recommendation,
        )
