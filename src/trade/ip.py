"""知识产权风险筛查（离线演示版）。

候选品与演示用商标 / 专利 / 外观设计库比对，输出侵权风险等级。
真实场景可替换为 USPTO / EUIPO 官方公开数据接口。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import CATEGORIES


@dataclass(frozen=True)
class IpRecord:
    mark: str
    category: str
    market: str
    kind: str
    holder: str
    source: str
    risk: str
    keywords: tuple[str, ...]
    note: str


IP_LIBRARY: tuple[IpRecord, ...] = (
    IpRecord(
        "SnapContainer", "cn_latiao", "us", "商标", "SnapCo Inc.", "USPTO", "high",
        ("snap", "container"), "美国已注册商标，辣条类包装容器近似度高",
    ),
    IpRecord(
        "SnackNest", "cn_latiao", "eu", "外观设计", "NestFoods Ltd.", "EUIPO", "medium",
        ("nest", "snack"), "欧盟外观设计，辣条类休闲零食存在近似风险",
    ),
    IpRecord(
        "RumahSnack", "cn_latiao", "sea", "商标", "SmartSnack Asia", "东南亚商标局", "medium",
        ("rumah", "snack"), "东南亚已注册休闲零食相关商标",
    ),
    IpRecord(
        "NoodleWand", "cn_changsha_mifen", "us", "商标", "NoodleWand LLC", "USPTO", "high",
        ("wand", "noodle"), "美国米粉类冲调产品知名商标",
    ),
    IpRecord(
        "KatzNudel", "cn_changsha_mifen", "eu", "商标", "KatzNudel GmbH", "EUIPO", "medium",
        ("katz", "nudel"), "欧盟米粉类商标，德语区常用词",
    ),
    IpRecord(
        "LokalMi", "cn_changsha_mifen", "sea", "商标", "LokalMi Sdn Bhd", "东南亚商标局", "low",
        ("lokal", "mi"), "东南亚本地化米粉类商标",
    ),
    IpRecord(
        "TeaFlex", "cn_longjing", "us", "商标", "TeaFlex Trading", "USPTO", "high",
        ("flex", "tea"), "美国茶饮类核心商标",
    ),
    IpRecord(
        "TeaForm", "cn_longjing", "eu", "外观设计", "TeaForm BV", "EUIPO", "medium",
        ("form", "tea"), "欧盟茶饮类外观设计",
    ),
    IpRecord(
        "GilaTea", "cn_longjing", "sea", "商标", "Gila Tea Co.", "东南亚商标局", "medium",
        ("gila", "tea"), "东南亚茶饮类相关商标",
    ),
    IpRecord(
        "FrostPack", "cn_frozen_dumplings", "us", "专利", "FrostPack Inc.", "USPTO", "high",
        ("frost", "pack"), "美国速冻食品锁鲜包装专利",
    ),
    IpRecord(
        "TeigPro", "cn_frozen_dumplings", "eu", "商标", "TeigPro AG", "EUIPO", "medium",
        ("teig", "pro"), "欧盟速冻食品商标",
    ),
    IpRecord(
        "DumplingKu", "cn_frozen_dumplings", "sea", "商标", "DumplingKu Pte Ltd", "东南亚商标局", "high",
        ("dumpling", "ku"), "东南亚速冻水饺知名商标",
    ),
    IpRecord(
        "SnackSafe", "cn_beef_jerky", "us", "专利", "SnackSafe Inc.", "USPTO", "high",
        ("snack", "safe"), "美国肉干类安全包装专利",
    ),
    IpRecord(
        "AlpJerky", "cn_beef_jerky", "eu", "商标", "AlpJerky SARL", "EUIPO", "medium",
        ("alp", "jerky"), "欧盟肉干类休闲食品商标",
    ),
    IpRecord(
        "JerkyNus", "cn_beef_jerky", "sea", "商标", "Nusantara Snacks", "东南亚商标局", "low",
        ("nus", "jerky"), "东南亚本地肉干类商标",
    ),
)

_RISK_RANK = {"high": 0, "medium": 1, "low": 2}
_RISK_SCORE = {"high": 20.0, "medium": 50.0, "low": 85.0}


@dataclass(frozen=True)
class IpRiskResult:
    category: str
    market: str
    product_name: str | None
    risk_level: str
    risk_score: float
    matched_records: tuple[IpRecord, ...]
    recommendation: str


class IpScreener:
    """按品类 / 市场 / 候选品名称输出知识产权风险等级。"""

    def screen(
        self,
        category: str,
        market: str,
        product_name: str | None = None,
    ) -> IpRiskResult:
        candidates = [
            record
            for record in IP_LIBRARY
            if record.category == category and record.market == market
        ]
        if not candidates:
            return IpRiskResult(
                category=category,
                market=market,
                product_name=product_name,
                risk_level="low",
                risk_score=100.0,
                matched_records=(),
                recommendation="演示库暂无该组合记录，需接入官方商标 / 专利库做最终核验。",
            )

        if product_name:
            needle = product_name.lower()
            matched = [r for r in candidates if any(keyword in needle for keyword in r.keywords)]
        else:
            matched = list(candidates)

        if not matched:
            return IpRiskResult(
                category=category,
                market=market,
                product_name=product_name,
                risk_level="low",
                risk_score=_RISK_SCORE["low"],
                matched_records=(),
                recommendation="演示库未命中高风险记录，仍需结合官方库做最终核验。",
            )

        risk = min(matched, key=lambda r: _RISK_RANK[r.risk]).risk
        if risk == "high":
            recommendation = "存在明显近似标记 / 专利，建议先做专业自由实施（FTO）检索并更换命名或设计。"
        elif risk == "medium":
            recommendation = "存在潜在近似风险，建议比对 USPTO / EUIPO 原文并预留规避方案。"
        else:
            recommendation = "演示库未发现高风险记录，仍需官方库复核。"
        if not product_name:
            recommendation = "未填写候选品名称，" + recommendation

        return IpRiskResult(
            category=category,
            market=market,
            product_name=product_name,
            risk_level=risk,
            risk_score=_RISK_SCORE[risk],
            matched_records=tuple(matched),
            recommendation=recommendation,
        )
