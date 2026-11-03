"""供应商与客户尽调检查清单（轻量演示版）。

借鉴 ``wo9230/osint-agent`` 的外贸尽调思路，不发起真实外呼或抓取，
基于现有信用评估输出可勾选的尽调清单；有 1688-cli 真实快照时，
把供应商名称、地区、经营年限、复购率与响应率并入清单。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OsintCheck:
    subject: str
    item: str
    status: str  # pass / attention / pending
    note: str

    def to_dict(self) -> dict[str, str]:
        return {
            "subject": self.subject,
            "item": self.item,
            "status": self.status,
            "note": self.note,
            # 前端兼容别名（TradeResultDetail 读取 title/name/message，见建议报告 S9）
            "title": self.item,
            "name": self.item,
            "message": self.note,
        }


@dataclass(frozen=True)
class OsintResult:
    category: str
    market: str
    checks: tuple[OsintCheck, ...]
    risk_level: str
    recommendation: str

    @property
    def readiness(self) -> str:
        """尽调就绪度：ready / conditional / not_ready（供前端直接展示）。"""
        return {
            "low": "ready",
            "medium": "conditional",
            "high": "not_ready",
        }.get(self.risk_level, "conditional")

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "market": self.market,
            "checks": [check.to_dict() for check in self.checks],
            "risk_level": self.risk_level,
            "recommendation": self.recommendation,
            "readiness": self.readiness,
        }


def assess_osint(
    category: str,
    market: str,
    *,
    financing_ready_score: float | None = None,
    suppliers: dict[str, Any] | None = None,
) -> OsintResult:
    """基于数据信用分数与可选供应商快照生成供应商/客户尽调清单。"""
    credit = 50.0 if financing_ready_score is None else float(financing_ready_score)
    checks = [
        OsintCheck(
            "供应商",
            "工商资质与经营年限",
            "pass" if credit >= 60 else "attention",
            "建议核对营业执照、经营年限与法人变更记录",
        ),
        OsintCheck(
            "供应商",
            "样品与产线验证",
            "pending",
            "批量下单前完成样品确认与产线验厂",
        ),
        OsintCheck(
            "供应商",
            "账期与履约条款",
            "attention",
            "明确付款节点、交期违约金与质量退款条款",
        ),
        OsintCheck(
            "供应商",
            "知识产权授权",
            "pending",
            "涉及品牌/专利/外观时索取授权文件",
        ),
        OsintCheck(
            "客户",
            "付款方式与信用",
            "pass" if credit >= 70 else "attention",
            "新客户优先采用平台担保或信用证等低风险结算",
        ),
        OsintCheck(
            "客户",
            "退换货与纠纷记录",
            "pending",
            "结合历史退换货率与纠纷率设定售后预算",
        ),
        OsintCheck(
            "客户",
            "目标市场合规背景",
            "attention",
            f"{market.upper()} 市场建议查询当地海关与消费者保护规则",
        ),
    ]
    if suppliers is None:
        from src.data.supplier_sourcing import load_latest_suppliers

        suppliers = load_latest_suppliers()
    real_rows = [
        row
        for row in (suppliers.get("rows") or [])
        if not row.get("fallback_used") and row.get("source") not in (None, "mock")
    ]
    for row in real_rows[:3]:
        name = str(row.get("supplier_name") or "-")
        location = str(row.get("location") or "-")
        years = float(row.get("service_years") or 0)
        repeat = float(row.get("repeat_rate") or 0)
        response = float(row.get("response_rate") or 0)
        score = float(row.get("score") or 0)
        checks.append(
            OsintCheck(
                "供应商",
                f"1688 货源：{name}（{location}）",
                "pass" if score >= 60 else "attention",
                (
                    f"经营 {years:.1f} 年 · 复购 {repeat:.0%} · "
                    f"响应 {response:.0%} · 来源 1688-cli"
                ),
            )
        )
    risk = "low" if credit >= 75 else ("medium" if credit >= 55 else "high")
    if risk == "low":
        recommendation = "尽调总体风险较低，可进入供应商筛选与试单阶段。"
    elif risk == "medium":
        recommendation = "尽调存在待确认项，建议先完成样品与资质核验再放量。"
    else:
        recommendation = "尽调数据覆盖不足，建议先补齐供应商与客户信用信息。"
    return OsintResult(
        category=category,
        market=market,
        checks=tuple(checks),
        risk_level=risk,
        recommendation=recommendation,
    )


__all__ = ["OsintCheck", "OsintResult", "assess_osint"]
