"""多脑冲突裁决：按置信度 × 权重融合市场、政策、物流、财务等异构信号。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class DecisionSignal:
    code: str
    name: str
    score: float
    confidence: float
    weight: float
    source: str


@dataclass(frozen=True)
class ConflictVerdict:
    original_score: float
    adjusted_score: float
    score_change: float
    conflict_level: str
    decision: str
    reasons: tuple[str, ...]
    dominant_signals: tuple[str, ...]
    signals: tuple[DecisionSignal, ...]


def _clip(value: float) -> float:
    return max(0.0, min(100.0, value))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 50.0


def _policy_score(risk: str) -> float:
    return {"low": 100.0, "medium": 75.0, "high": 55.0}.get(risk, 100.0)


def _freight_score(risk: str) -> float:
    return {"low": 100.0, "medium": 75.0, "high": 55.0}.get(risk, 100.0)


def build_trade_signals(
    growth_score: float,
    policy_risk: str,
    freight_risk: str,
    margin_pct: float,
    feasibility_score: float,
    sentiment_score: float,
    financing_score: float,
) -> tuple[DecisionSignal, ...]:
    """把四大脑输出映射为可比较的 0-100 信号。"""
    return (
        DecisionSignal(
            code="market_growth",
            name="市场增长",
            score=_clip(growth_score),
            confidence=0.65,
            weight=0.25,
            source="大脑1：预测 / 趋势",
        ),
        DecisionSignal(
            code="sentiment",
            name="舆情情绪",
            score=_clip(50 + sentiment_score * 50),
            confidence=0.55,
            weight=0.10,
            source="大脑2：舆情",
        ),
        DecisionSignal(
            code="policy_risk",
            name="政策风险",
            score=_policy_score(policy_risk),
            confidence=0.85,
            weight=0.25,
            source="大脑3：CBP / TARIC",
        ),
        DecisionSignal(
            code="freight_risk",
            name="物流履约",
            score=_freight_score(freight_risk),
            confidence=0.80,
            weight=0.15,
            source="大脑3：SCFI / 船司",
        ),
        DecisionSignal(
            code="margin",
            name="财务利润",
            score=_clip(margin_pct / 40.0 * 100.0),
            confidence=0.70,
            weight=0.20,
            source="大脑4：贸易成本",
        ),
        DecisionSignal(
            code="market_access",
            name="市场准入",
            score=_clip(feasibility_score),
            confidence=0.60,
            weight=0.15,
            source="法规合规库",
        ),
        DecisionSignal(
            code="financing",
            name="融资就绪",
            score=_clip(financing_score),
            confidence=0.50,
            weight=0.10,
            source="数据信用",
        ),
    )


def resolve_conflict(signals: Sequence[DecisionSignal]) -> ConflictVerdict:
    """按置信度 × 权重重新计算综合得分并给出裁决建议。"""
    weight_sum = sum(signal.weight for signal in signals) or 1.0
    weighted_sum = sum(signal.score * signal.weight for signal in signals)
    original_score = weighted_sum / weight_sum

    confidence_weight_sum = sum(signal.confidence * signal.weight for signal in signals) or 1.0
    adjusted_sum = sum(signal.score * signal.confidence * signal.weight for signal in signals)
    adjusted_score = adjusted_sum / confidence_weight_sum

    positives = [signal for signal in signals if signal.score >= 60.0]
    negatives = [signal for signal in signals if signal.score < 45.0]
    gap = _mean([s.score for s in positives]) - _mean([s.score for s in negatives])
    if positives and negatives and gap >= 25.0:
        conflict_level = "high"
    elif positives and negatives and gap >= 12.0:
        conflict_level = "medium"
    else:
        conflict_level = "low"

    risk_codes = {"policy_risk", "freight_risk", "market_access"}
    risk_signals = [signal for signal in signals if signal.code in risk_codes]
    growth_signals = [signal for signal in signals if signal.code not in risk_codes]
    growth_avg = _mean([signal.score for signal in growth_signals])
    risk_avg = _mean([signal.score for signal in risk_signals])

    if conflict_level != "low":
        if any(signal.score < 60.0 and signal.confidence >= 0.75 for signal in risk_signals):
            decision = "风险信号置信度更高，建议降低备货规模或调整品类 / 市场策略"
        elif growth_avg >= risk_avg:
            decision = "增长信号占优，可保留推荐但降低备货优先级并设置止损阈值"
        else:
            decision = "综合风险与增长信号，建议小批量试单验证"
    else:
        decision = "各脑信号方向一致，维持原决策"

    reasons: list[str] = []
    for signal in sorted(signals, key=lambda s: abs(s.score - 50.0), reverse=True)[:3]:
        if abs(signal.score - 50.0) >= 15.0:
            reasons.append(
                f"{signal.name}评分 {signal.score:.0f}，置信度 {signal.confidence:.0%}，"
                f"权重 {signal.weight:.0%}（{signal.source}）"
            )
    if conflict_level != "low":
        reasons.append("存在增长与风险信号冲突，已按置信度 × 权重重新裁决")

    dominant = sorted(signals, key=lambda s: s.score * s.confidence * s.weight, reverse=True)[:3]
    return ConflictVerdict(
        original_score=round(original_score, 1),
        adjusted_score=round(adjusted_score, 1),
        score_change=round(adjusted_score - original_score, 1),
        conflict_level=conflict_level,
        decision=decision,
        reasons=tuple(reasons),
        dominant_signals=tuple(signal.name for signal in dominant),
        signals=tuple(signals),
    )


def resolve_trade_conflict(
    growth_score: float,
    policy_risk: str,
    freight_risk: str,
    margin_pct: float,
    feasibility_score: float,
    sentiment_score: float,
    financing_score: float,
) -> ConflictVerdict:
    """基于当前贸易决策输出生成冲突裁决结果。"""
    signals = build_trade_signals(
        growth_score=growth_score,
        policy_risk=policy_risk,
        freight_risk=freight_risk,
        margin_pct=margin_pct,
        feasibility_score=feasibility_score,
        sentiment_score=sentiment_score,
        financing_score=financing_score,
    )
    return resolve_conflict(signals)
