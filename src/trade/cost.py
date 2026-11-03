"""财务贸易成本模型（离线演示版）。

覆盖采购、关税、汇率、支付通道、认证合规与物流三方案，输出可直接套用的
到岸成本与利润测算，并给出汇率敏感性区间。
"""

from __future__ import annotations

from dataclasses import dataclass, replace

DEFAULT_FX_RATE = 7.15


@dataclass(frozen=True)
class PaymentChannel:
    code: str
    name: str
    fee_rate: float
    settlement_days: int
    note: str


PAYMENT_CHANNELS: dict[str, PaymentChannel] = {
    "paypal": PaymentChannel("paypal", "PayPal", 0.045, 1, "综合费率较高，适合起步阶段"),
    "pingpong": PaymentChannel("pingpong", "PingPong", 0.006, 1, "提现费率低、到账快"),
    "lianlian": PaymentChannel("lianlian", "连连支付", 0.007, 1, "费率接近主流水平"),
}


@dataclass(frozen=True)
class LogisticsOption:
    code: str
    name: str
    base_cost_cny: float
    cost_cny_per_kg: float
    weight_kg: float
    delivery_days: int
    note: str

    @property
    def cost_cny_per_item(self) -> float:
        return self.base_cost_cny + self.cost_cny_per_kg * self.weight_kg


LOGISTICS_OPTIONS: dict[str, LogisticsOption] = {
    "small_parcel": LogisticsOption(
        "small_parcel", "小包直邮", 25.0, 12.0, 0.5, 12, "de minimis 取消后清关环节成本高"
    ),
    "sea": LogisticsOption("sea", "海运整柜", 12.0, 6.0, 0.5, 35, "单件成本低但时效长，适合稳定补货"),
    "overseas_warehouse": LogisticsOption(
        "overseas_warehouse", "海外仓本地发货", 8.0, 4.0, 0.5, 5, "时效快，需承担备货与仓储风险"
    ),
}


@dataclass(frozen=True)
class LandedCostInput:
    category: str
    market: str
    unit_price_usd: float
    procurement_cost_cny: float
    payment_code: str = "pingpong"
    logistics_code: str = "small_parcel"
    tariff_rate: float = 0.0
    min_duty_usd: float = 0.0
    compliance_cost_usd: float = 0.0
    fx_rate: float = DEFAULT_FX_RATE


@dataclass(frozen=True)
class LandedCostResult:
    category: str
    market: str
    unit_price_usd: float
    procurement_cost_usd: float
    payment_fee_usd: float
    duty_usd: float
    logistics_cost_usd: float
    compliance_cost_usd: float
    landed_cost_usd: float
    profit_usd: float
    margin_pct: float
    payment_channel: PaymentChannel
    logistics: LogisticsOption
    fx_rate: float
    fx_sensitivity: dict[str, dict[str, float]]

    def breakdown(self) -> dict[str, float]:
        return {
            "采购成本": round(self.procurement_cost_usd, 2),
            "支付手续费": round(self.payment_fee_usd, 2),
            "关税": round(self.duty_usd, 2),
            "物流成本": round(self.logistics_cost_usd, 2),
            "认证合规成本": round(self.compliance_cost_usd, 2),
            "到岸总成本": round(self.landed_cost_usd, 2),
        }


def _compute_fx_margin(
    fx_rate: float,
    procurement_cny: float,
    logistics_cny: float,
    price_usd: float,
    payment_fee_usd: float,
    duty_usd: float,
    compliance_usd: float,
) -> float:
    landed = (
        procurement_cny / fx_rate
        + logistics_cny / fx_rate
        + payment_fee_usd
        + duty_usd
        + compliance_usd
    )
    profit = price_usd - landed
    return round(profit / max(price_usd, 1e-9) * 100.0, 2)


class LandedCostCalculator:
    """按输入参数计算到岸成本、利润率与汇率敏感性。"""

    def calculate(self, payload: LandedCostInput) -> LandedCostResult:
        channel = PAYMENT_CHANNELS[payload.payment_code]
        logistics = LOGISTICS_OPTIONS[payload.logistics_code]
        procurement_usd = payload.procurement_cost_cny / payload.fx_rate
        payment_fee = payload.unit_price_usd * channel.fee_rate
        duty = (
            max(payload.unit_price_usd * payload.tariff_rate, payload.min_duty_usd)
            if payload.tariff_rate > 0
            else 0.0
        )
        logistics_usd = logistics.cost_cny_per_item / payload.fx_rate
        landed = procurement_usd + payment_fee + duty + logistics_usd + payload.compliance_cost_usd
        profit = payload.unit_price_usd - landed
        margin = profit / max(payload.unit_price_usd, 1e-9) * 100.0

        fx_sensitivity: dict[str, dict[str, float]] = {}
        for label, factor in (("人民币升值5%", 0.95), ("当前汇率", 1.0), ("人民币贬值5%", 1.05)):
            fx = payload.fx_rate * factor
            sensitivity_margin = _compute_fx_margin(
                fx,
                payload.procurement_cost_cny,
                logistics.cost_cny_per_item,
                payload.unit_price_usd,
                payment_fee,
                duty,
                payload.compliance_cost_usd,
            )
            fx_sensitivity[label] = {
                "汇率": round(fx, 2),
                "利润率%": sensitivity_margin,
                # 前端兼容别名（TradeResultDetail 读取 margin_pct，见建议报告 S9）
                "margin_pct": sensitivity_margin,
            }

        return LandedCostResult(
            category=payload.category,
            market=payload.market,
            unit_price_usd=payload.unit_price_usd,
            procurement_cost_usd=round(procurement_usd, 2),
            payment_fee_usd=round(payment_fee, 2),
            duty_usd=round(duty, 2),
            logistics_cost_usd=round(logistics_usd, 2),
            compliance_cost_usd=payload.compliance_cost_usd,
            landed_cost_usd=round(landed, 2),
            profit_usd=round(profit, 2),
            margin_pct=round(margin, 2),
            payment_channel=channel,
            logistics=logistics,
            fx_rate=payload.fx_rate,
            fx_sensitivity=fx_sensitivity,
        )

    def compare_logistics(self, payload: LandedCostInput) -> list[LandedCostResult]:
        results: list[LandedCostResult] = []
        for code in LOGISTICS_OPTIONS:
            results.append(self.calculate(replace(payload, logistics_code=code)))
        return sorted(results, key=lambda r: r.landed_cost_usd)


def to_row(result: LandedCostResult) -> dict:
    return {
        "category": result.category,
        "market": result.market,
        "unit_price_usd": result.unit_price_usd,
        "payment_channel": result.payment_channel.name,
        # logistics 为历史字段；logistics_name/delivery_days 供前端 TradeResultDetail 展示。
        "logistics": result.logistics.name,
        "logistics_name": result.logistics.name,
        "delivery_days": result.logistics.delivery_days,
        "procurement_cost_usd": result.procurement_cost_usd,
        "payment_fee_usd": result.payment_fee_usd,
        "duty_usd": result.duty_usd,
        "logistics_cost_usd": result.logistics_cost_usd,
        "compliance_cost_usd": result.compliance_cost_usd,
        "landed_cost_usd": result.landed_cost_usd,
        "profit_usd": result.profit_usd,
        "margin_pct": result.margin_pct,
        "fx_rate": result.fx_rate,
    }
