"""物流成本与时效预测（离线演示版）。

以 SCFI 风格的演示运价序列为输入，预测未来 4 周运价走势、
单件物流成本、交付时效与拥堵风险。真实场景可替换为 SCFI / 各船司运价接口。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FreightLane:
    market: str
    lane: str
    index_now: float
    history: tuple[float, ...]
    cost_cny_per_kg: float
    congestion: str
    note: str


FREIGHT_LANES: dict[str, FreightLane] = {
    "us": FreightLane(
        market="us",
        lane="中国 - 美国（美西）",
        index_now=1050.0,
        history=(960.0, 980.0, 990.0, 1010.0, 1030.0, 1040.0, 1050.0, 1050.0),
        cost_cny_per_kg=12.0,
        congestion="high",
        note="美西航线运价高位震荡，港口拥堵推升时效不确定性",
    ),
    "eu": FreightLane(
        market="eu",
        lane="中国 - 欧洲（鹿特丹）",
        index_now=1180.0,
        history=(1120.0, 1140.0, 1150.0, 1170.0, 1180.0, 1175.0, 1180.0, 1180.0),
        cost_cny_per_kg=10.5,
        congestion="medium",
        note="欧洲航线运价缓慢上行，清关新规增加合规环节",
    ),
    "sea": FreightLane(
        market="sea",
        lane="中国 - 东南亚（新加坡 / 曼谷）",
        index_now=720.0,
        history=(740.0, 735.0, 730.0, 725.0, 728.0, 720.0, 718.0, 720.0),
        cost_cny_per_kg=8.5,
        congestion="low",
        note="东南亚航线运价平稳，时效相对稳定",
    ),
    "jp": FreightLane(
        market="jp",
        lane="中国 - 日本（东京 / 大阪）",
        index_now=890.0,
        history=(860.0, 870.0, 875.0, 880.0, 885.0, 888.0, 890.0, 890.0),
        cost_cny_per_kg=9.8,
        congestion="medium",
        note="日本航线运价温和上行，港口与清关时效稳定",
    ),
    "ca": FreightLane(
        market="ca",
        lane="中国 - 加拿大（温哥华）",
        index_now=1010.0,
        history=(970.0, 985.0, 990.0, 995.0, 1000.0, 1005.0, 1010.0, 1010.0),
        cost_cny_per_kg=11.2,
        congestion="medium",
        note="加拿大航线与美西联动，拥堵风险中等",
    ),
    "au": FreightLane(
        market="au",
        lane="中国 - 澳大利亚（悉尼 / 墨尔本）",
        index_now=950.0,
        history=(930.0, 935.0, 940.0, 940.0, 945.0, 945.0, 948.0, 950.0),
        cost_cny_per_kg=9.0,
        congestion="low",
        note="澳大利亚航线运价平稳，时效稳定",
    ),
    "uk": FreightLane(
        market="uk",
        lane="中国 - 英国（费利克斯托）",
        index_now=1150.0,
        history=(1080.0, 1100.0, 1120.0, 1130.0, 1140.0, 1145.0, 1150.0, 1150.0),
        cost_cny_per_kg=10.8,
        congestion="medium",
        note="英国航线运价温和上行，脱欧后清关环节需关注",
    ),
    "kr": FreightLane(
        market="kr",
        lane="中国 - 韩国（釜山）",
        index_now=760.0,
        history=(730.0, 735.0, 740.0, 745.0, 750.0, 755.0, 760.0, 760.0),
        cost_cny_per_kg=8.0,
        congestion="low",
        note="韩国航线运价平稳，时效快",
    ),
    "de": FreightLane(
        market="de",
        lane="中国 - 德国（汉堡）",
        index_now=1170.0,
        history=(1100.0, 1120.0, 1140.0, 1150.0, 1160.0, 1165.0, 1170.0, 1170.0),
        cost_cny_per_kg=10.6,
        congestion="medium",
        note="德国航线运价温和上行，欧洲内陆转运时效需关注",
    ),
    "fr": FreightLane(
        market="fr",
        lane="中国 - 法国（勒阿弗尔）",
        index_now=1190.0,
        history=(1120.0, 1140.0, 1150.0, 1160.0, 1175.0, 1185.0, 1190.0, 1190.0),
        cost_cny_per_kg=10.9,
        congestion="medium",
        note="法国航线运价上行，清关与标签合规环节增加",
    ),
    "vn": FreightLane(
        market="vn",
        lane="中国 - 越南（胡志明 / 海防）",
        index_now=620.0,
        history=(600.0, 605.0, 610.0, 612.0, 615.0, 618.0, 620.0, 620.0),
        cost_cny_per_kg=7.2,
        congestion="low",
        note="越南航线运价平稳，陆运与海运时效快",
    ),
    "ru": FreightLane(
        market="ru",
        lane="中国 - 俄罗斯（莫斯科）",
        index_now=1420.0,
        history=(1350.0, 1370.0, 1390.0, 1400.0, 1410.0, 1415.0, 1420.0, 1420.0),
        cost_cny_per_kg=16.5,
        congestion="high",
        note="俄罗斯航线运价高位，陆运与清关时效波动大",
    ),
    "hu": FreightLane(
        market="hu",
        lane="中国 - 匈牙利（布达佩斯）",
        index_now=1220.0,
        history=(1160.0, 1180.0, 1190.0, 1200.0, 1210.0, 1215.0, 1220.0, 1220.0),
        cost_cny_per_kg=11.6,
        congestion="medium",
        note="匈牙利航线与欧洲内陆衔接，时效稳定",
    ),
    "ae": FreightLane(
        market="ae",
        lane="中国 - 中东（迪拜 / 杰贝阿里）",
        index_now=1010.0,
        history=(980.0, 990.0, 995.0, 1000.0, 1005.0, 1008.0, 1010.0, 1010.0),
        cost_cny_per_kg=12.8,
        congestion="medium",
        note="中东航线运价温和上行，转口辐射能力强",
    ),
    "mx": FreightLane(
        market="mx",
        lane="中国 - 墨西哥（曼萨尼约）",
        index_now=1330.0,
        history=(1260.0, 1280.0, 1300.0, 1310.0, 1320.0, 1325.0, 1330.0, 1330.0),
        cost_cny_per_kg=14.5,
        congestion="high",
        note="墨西哥航线运价高位，口岸拥堵风险较高",
    ),
}


@dataclass(frozen=True)
class FreightForecast:
    market: str
    lane: str
    index_now: float
    index_forecast: float
    trend_pct: float
    cost_cny_per_kg: float
    cost_forecast_cny_per_kg: float
    delivery_days_min: int
    delivery_days_max: int
    congestion: str
    risk: str
    note: str


_DELIVERY_DAYS = {
    "us": (10, 14),
    "eu": (14, 20),
    "sea": (7, 12),
    "jp": (8, 12),
    "ca": (11, 16),
    "au": (9, 14),
    "uk": (12, 16),
    "kr": (6, 9),
    "de": (13, 18),
    "fr": (14, 19),
    "vn": (5, 9),
    "ru": (20, 30),
    "hu": (15, 22),
    "ae": (14, 20),
    "mx": (18, 26),
}


class FreightForecaster:
    """按航线预测未来 4 周运价与时效风险。"""

    def forecast(self, market: str) -> FreightForecast:
        lane = FREIGHT_LANES[market]
        window = lane.history[-4:]
        trend_pct = (window[-1] - window[0]) / max(window[0], 1.0) * 100.0
        damped_pct = trend_pct / 2.0
        index_forecast = lane.index_now * (1.0 + damped_pct / 100.0)
        cost_forecast = lane.cost_cny_per_kg * (index_forecast / max(lane.index_now, 1.0))

        if lane.congestion == "high" or trend_pct > 5.0:
            risk = "high"
        elif lane.congestion == "medium" or trend_pct > 2.0:
            risk = "medium"
        else:
            risk = "low"

        min_days, max_days = _DELIVERY_DAYS[market]
        return FreightForecast(
            market=market,
            lane=lane.lane,
            index_now=lane.index_now,
            index_forecast=round(index_forecast, 1),
            trend_pct=round(trend_pct, 2),
            cost_cny_per_kg=lane.cost_cny_per_kg,
            cost_forecast_cny_per_kg=round(cost_forecast, 2),
            delivery_days_min=min_days,
            delivery_days_max=max_days,
            congestion=lane.congestion,
            risk=risk,
            note=lane.note,
        )
