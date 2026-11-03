"""选品推荐引擎：规则评分 + 预测增长 + 多源信号加权。"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.config import RECOMMEND_WEIGHTS, VERDICT_THRESHOLDS

TARGET = "sales_volume"
VERDICT_ORDER = {"Go": 0, "Conditional": 1, "No-Go": 2}


def _clip_score(value: float) -> float:
    return float(np.clip(value, 0, 100))


def _finite_mape_map(rows) -> dict[tuple[str, str], float]:
    """Convert metric rows into {(category, market): finite MAPE}."""
    result: dict[tuple[str, str], float] = {}
    if rows is None:
        return result
    if hasattr(rows, "to_dict"):
        rows = rows.to_dict(orient="records")
    for row in rows:
        category = row.get("category")
        market = row.get("market")
        mape = row.get("mape")
        if category is None or market is None:
            continue
        if isinstance(mape, (int, float)) and math.isfinite(float(mape)):
            result[(str(category), str(market))] = float(mape)
    return result


def select_best_model_forecast(
    baseline_fc: pd.DataFrame,
    advanced_fc: pd.DataFrame,
    baseline_metrics=None,
    advanced_metrics=None,
) -> pd.DataFrame:
    """按组合回测 MAPE 选择 Prophet 或 LightGBM 的 90 天预测。"""
    if baseline_fc is None or advanced_fc is None:
        return pd.DataFrame()
    baseline_map = _finite_mape_map(baseline_metrics)
    advanced_map = _finite_mape_map(advanced_metrics)
    baseline_marked = baseline_fc.copy()
    baseline_marked["_select_model"] = "prophet_baseline"
    advanced_marked = advanced_fc.copy()
    advanced_marked["_select_model"] = "lightgbm_advanced"
    combined = pd.concat([baseline_marked, advanced_marked], ignore_index=True)
    parts: list[pd.DataFrame] = []
    for (category, market), _group in combined.groupby(
        ["category", "market"], observed=True
    ):
        key = (str(category), str(market))
        baseline_mape = baseline_map.get(key)
        advanced_mape = advanced_map.get(key)
        chosen = (
            "prophet_baseline"
            if baseline_mape is not None
            and (advanced_mape is None or baseline_mape < advanced_mape)
            else "lightgbm_advanced"
        )
        selected = combined[
            (combined["category"] == category)
            & (combined["market"] == market)
            & (combined["_select_model"] == chosen)
        ]
        if selected.empty:
            fallback = (
                "lightgbm_advanced"
                if chosen == "prophet_baseline"
                else "prophet_baseline"
            )
            selected = combined[
                (combined["category"] == category)
                & (combined["market"] == market)
                & (combined["_select_model"] == fallback)
            ]
        parts.append(selected)
    if not parts:
        return pd.DataFrame()
    return (
        pd.concat(parts, ignore_index=True)
        .drop(columns="_select_model")
        .reset_index(drop=True)
    )


class RecommendationEngine:
    """基于历史信号与未来预测输出 Top N 选品推荐。"""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights or RECOMMEND_WEIGHTS
        self.verdict_thresholds = dict(VERDICT_THRESHOLDS)

    def build(
        self,
        history: pd.DataFrame,
        forecast: pd.DataFrame,
        opportunity: dict[tuple[str, str], dict] | None = None,
    ) -> pd.DataFrame:
        """构建全组合评分并返回按分数降序的推荐表。"""
        rows: list[dict] = []
        for (category, market), group in history.groupby(["category", "market"], observed=True):
            group = group.sort_values("date")
            recent4 = group.tail(4)
            prev4 = group.iloc[-8:-4]

            history_mean = group[TARGET].tail(13).mean() if len(group) >= 13 else group[TARGET].mean()
            fc = forecast[(forecast["category"] == category) & (forecast["market"] == market)]
            forecast_mean = fc["yhat"].mean() if not fc.empty else history_mean
            growth = (forecast_mean / history_mean - 1) * 100 if history_mean else 0.0

            search_trend = (
                (recent4["search_index"].mean() / prev4["search_index"].mean() - 1) * 100
                if len(prev4) and prev4["search_index"].mean() > 0
                else 0.0
            )
            competition = float(recent4["competition_index"].mean())
            review = float(recent4["review_growth"].mean())

            forecast_growth_score = _clip_score(50 + growth * 1.2)
            search_trend_score = _clip_score(50 + search_trend * 1.5)
            competition_score = _clip_score(100 - competition)
            review_score = _clip_score(50 + review * 3.0)
            total = (
                self.weights["forecast_growth"] * forecast_growth_score
                + self.weights["search_trend"] * search_trend_score
                + self.weights["competition"] * competition_score
                + self.weights["review_growth"] * review_score
            )

            opp = (opportunity or {}).get((category, market))
            margin_score = (
                _clip_score(float(opp.get("margin_pct", 0.0)) / 40.0 * 100.0)
                if opp
                else 50.0
            )
            compliance_score = (
                _clip_score(float(opp.get("compliance_feasibility", 0.0)))
                if opp
                else 50.0
            )
            evidence_meta = (opp or {}).get("evidence") or {}
            evidence_missing = not opp or bool(evidence_meta.get("missing", True))
            evidence_score = (
                50.0
                if evidence_missing
                else _clip_score(float(evidence_meta.get("score", 50.0)))
            )
            six_dimension_score = (
                0.25 * forecast_growth_score
                + 0.20 * search_trend_score
                + 0.20 * competition_score
                + 0.20 * margin_score
                + 0.10 * compliance_score
                + 0.05 * evidence_score
            )
            verdict, decision_reason = self._verdict(
                six_dimension_score,
                forecast_growth_score,
                search_trend_score,
                competition_score,
                margin_score,
                compliance_score,
                evidence_score,
                opp,
            )

            reasons = self._build_reasons(growth, search_trend, competition, review)
            rows.append(
                {
                    "category": category,
                    "market": market,
                    "score": round(total, 1),
                    "six_dimension_score": round(six_dimension_score, 1),
                    "verdict": verdict,
                    "decision_reason": decision_reason,
                    "dimension_demand": round(forecast_growth_score, 1),
                    "dimension_trend": round(search_trend_score, 1),
                    "dimension_competition": round(competition_score, 1),
                    "dimension_margin": round(margin_score, 1),
                    "dimension_compliance": round(compliance_score, 1),
                    "dimension_evidence": round(evidence_score, 1),
                    "evidence_missing": evidence_missing,
                    "forecast_growth": round(growth, 2),
                    "search_trend": round(search_trend, 2),
                    "competition": round(competition, 1),
                    "review_growth": round(review, 2),
                    "reasons": "；".join(reasons),
                }
            )

        result = pd.DataFrame(rows)
        result["_verdict_order"] = result["verdict"].map(VERDICT_ORDER).fillna(2)
        result = result.sort_values(
            [
                "_verdict_order",
                "six_dimension_score",
                "forecast_growth",
                "search_trend",
                "category",
                "market",
            ],
            ascending=[True, False, False, False, True, True],
        ).reset_index(drop=True)
        result = result.drop(columns="_verdict_order")
        result.insert(0, "rank", result.index + 1)
        return result

    def _verdict(
        self,
        total: float,
        demand: float,
        trend: float,
        competition: float,
        margin: float,
        compliance: float,
        evidence: float,
        opportunity: dict | None,
    ) -> tuple[str, str]:
        thresholds = self.verdict_thresholds
        dimensions = [demand, trend, competition, margin, compliance, evidence]
        preflight = (opportunity or {}).get("preflight") or {}
        has_blocker = any(score < thresholds["conditional_dimension_min"] for score in dimensions)
        has_weak = any(score < thresholds["dimension_min"] for score in dimensions)
        has_pending = any(
            item.get("status") == "pending" for item in preflight.get("items") or []
        )

        if total >= thresholds["go_min"] and not has_weak and not has_pending:
            return "Go", "六维评分充足且无待确认项，建议进入小批量验证。"
        if has_blocker:
            return "No-Go", "存在低于 40 分的核心维度，建议重新选品或调整市场。"
        if total < thresholds["conditional_min"]:
            return "No-Go", "六维评分低于 55 分，暂不建议进入备货。"
        return "Conditional", "存在弱项或待确认项，建议小批量试单并补齐证据。"

    @staticmethod
    def _build_reasons(growth: float, search_trend: float, competition: float, review: float) -> list[str]:
        reasons: list[str] = []
        if growth >= 5:
            reasons.append(f"未来90天预测销量增长 {growth:.1f}%")
        elif growth <= -5:
            reasons.append(f"未来90天预测销量回落 {abs(growth):.1f}%，需谨慎备货")
        else:
            reasons.append("未来90天销量预测基本平稳")
        if search_trend >= 3:
            reasons.append(f"搜索热度环比上升 {search_trend:.1f}%")
        elif search_trend <= -3:
            reasons.append(f"搜索热度环比下降 {abs(search_trend):.1f}%")
        else:
            reasons.append("搜索热度保持稳定")
        if competition <= 45:
            reasons.append(f"竞争度较低（{competition:.0f}/100），蓝海空间明显")
        elif competition >= 70:
            reasons.append(f"竞争度较高（{competition:.0f}/100），建议差异化切入")
        else:
            reasons.append(f"竞争度中等（{competition:.0f}/100）")
        if review >= 2:
            reasons.append(f"评论增长活跃（{review:.1f}%）")
        return reasons

    def top_n(
        self,
        history: pd.DataFrame,
        forecast: pd.DataFrame,
        n: int = 10,
        opportunity: dict[tuple[str, str], dict] | None = None,
    ) -> pd.DataFrame:
        """返回 Top N 推荐。"""
        return self.build(history, forecast, opportunity=opportunity).head(n)
