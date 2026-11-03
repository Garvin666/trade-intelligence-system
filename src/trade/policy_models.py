"""Base tariff rates shared by the policy engine.

Split from src/trade/policy.py (S1 module split).
"""

from __future__ import annotations

from dataclasses import dataclass
from src.config import CATEGORY_CATALOG, MARKETS

@dataclass(frozen=True)
class PolicyEvent:
    code: str
    title: str
    market: str
    effective_date: str
    rate_ad_valorem: float
    min_duty_usd: float
    description: str
    source: str
    actions: tuple[str, ...]
    region: str = "foreign"
    policy_type: str = "tariff"
    categories: tuple[str, ...] = ()
    cost_adjustment_pct: float = 0.0
    impact_level: str = "low"
    direction: str = "restrict"
    url: str = ""
    heuristic: bool = False
    verified: bool = False
    published_at: str = ""
    provider: str = ""
    source_type: str = "search"


POLICY_EVENTS: tuple[PolicyEvent, ...] = (
    PolicyEvent(
        code="us-de-minimis-2025",
        title="美国取消小额包裹免税",
        market="us",
        effective_date="2025-08-29",
        rate_ad_valorem=1.20,
        min_duty_usd=100.0,
        description=(
            "美国自 2025-08-29 起按第 14324 号行政命令取消 800 美元以下 "
            "de minimis 免税，非邮政渠道需正式报关；系统按 120% + 100 美元"
            "最低税额的简化口径测算，不代表所有渠道的唯一官方规则。"
        ),
        source="美国联邦公报（Federal Register，CBP Notice 90 FR 42418）",
        actions=("转正式清关", "调价", "切换市场", "海外仓本地发货"),
        impact_level="high",
        verified=True,
        published_at="2025-09-02",
        provider="federal_register",
        source_type="official",
        url=(
            "https://www.federalregister.gov/documents/2025/09/02/2025-16802/"
            "notice-of-implementation-of-the-presidents-executive-order-14324-"
            "suspending-duty-free-de-minimis"
        ),
    ),
    PolicyEvent(
        code="eu-low-value-vat-2026",
        title="欧盟低值包裹临时固定关税",
        market="eu",
        effective_date="2026-07-01",
        rate_ad_valorem=0.0,
        min_duty_usd=3.6,
        description=(
            "欧盟自 2026-07-01 至 2028-07-01 对总价值不超过 150 欧元的低值"
            "包裹按每件商品征收 3 欧元临时固定关税；系统按 EUR/USD 1.20 折算"
            "为 3.60 美元最低税额的简化口径测算，不视为 20% VAT。"
        ),
        source="欧盟官方公报（EUR-Lex，OJ L 2026/382）",
        actions=("核对 IOSS 申报资格", "转正式清关", "海外仓本地发货", "调价"),
        impact_level="high",
        verified=True,
        published_at="2026-02-18",
        provider="eu",
        source_type="official",
        policy_type="customs",
        url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202600382",
    ),
)

# 基础关税（演示口径：食品品类 x 市场）。
# 由 132 个食品 SKU 的 tariff_base 乘以市场系数派生，剔除全部消费类目硬编码。
_TARIFF_MARKET_FACTOR = {
    "us": 1.00, "eu": 1.20, "sea": 0.70, "jp": 0.90, "ca": 1.10, "au": 0.80,
    "uk": 1.10, "kr": 0.90, "de": 1.20, "fr": 1.10, "vn": 0.70, "ru": 0.90,
    "hu": 0.80, "ae": 0.80, "mx": 0.90,
}

BASE_TARIFF_RATE: dict[str, dict[str, float]] = {
    market: {
        code: round(float(meta["tariff_base"]) * _TARIFF_MARKET_FACTOR.get(market, 1.0), 4)
        for code, meta in CATEGORY_CATALOG.items()
    }
    for market in MARKETS
}

