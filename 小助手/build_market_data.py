# -*- coding: utf-8 -*-
"""生成全量跨境电商市场资料 market.json。

数据口径：
- 品类与市场编码对齐仓库根目录 src/config.py 的 CATEGORY_CATALOG / MARKETS。
- 指数与价格基线来自 data/demo/demo_market_data.csv 的品类 x 市场聚合，
  并保留 market.json 原有 4 品类 x 3 市场的已认可数值。
- 关税/认证/时效均为参考基线，实际执行时需以官方源核验（见 sources）。
"""

from __future__ import annotations

import ast
import csv
import json
import math
import shutil
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
MARKET_JSON = BASE_DIR / "market.json"
RUNPACK_MARKET_JSON = (
    REPO_ROOT / "发布与材料" / "完整Demo运行包" / "小助手" / "market.json"
)
DEMO_CSV = REPO_ROOT / "data" / "demo" / "demo_market_data.csv"


def _load_config() -> tuple[dict, dict]:
    """加载 src/config.py 的品类目录与市场编码，失败时用 AST 兜底。"""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        import src.config as cfg  # type: ignore

        return cfg.CATEGORY_CATALOG, cfg.MARKETS
    except Exception:
        pass

    source = (REPO_ROOT / "src" / "config.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    catalog: dict[str, dict] = {}
    markets: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = getattr(target, "id", "")
                if name in ("CATEGORY_CATALOG", "MARKETS"):
                    try:
                        value = ast.literal_eval(node.value)
                    except Exception:
                        value = None
                    if value is None:
                        continue
                    if name == "CATEGORY_CATALOG":
                        catalog = value
                    else:
                        markets = value
    if not catalog or not markets:
        raise RuntimeError("无法解析 src/config.py 的品类或市场目录")
    return catalog, markets


_CATALOG, _MARKETS = _load_config()

# 食品合规要点：按「储运方式 → HS 大类」派生，避免逐条硬编码随目录漂移。
_STORAGE_COMPLIANCE: dict[str, str] = {
    "冷冻": "冷冻食品：需全程 -18°C 温控与 HACCP 体系，多数国家要求出口国注册厂号与检验检疫证书",
    "冷藏": "冷藏食品：需 0-4°C 冷链与保质期管理，进口多需卫生/兽医卫生证书",
}
_HS_COMPLIANCE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("0407",), "蛋类：需检疫与沙门氏菌控制，部分市场要求巴氏杀菌或熟制证明"),
    (("0403", "0406"), "乳制品：需巴氏杀菌/热处理证明与兽医卫生证书，全程冷链"),
    (("0409",), "蜂产品：关注抗生素（氯霉素）与农残残留，美国易触发 FDA 进口警报"),
    (("0304", "0305"), "水产及其制品：需水产风险控制与捕捞/养殖来源证明，冷链完整"),
    (("1601", "1602", "1604", "1605"), "熟制肉/水产制品：须经热处理工艺并按出口国注册厂号管理，需过敏原标注"),
    (("0901", "0902", "0903", "2101"), "茶叶/咖啡：按 EC 396/2005 等执行农残 MRL 与重金属限量，有机宣称需认证"),
    (("2103", "2104", "2209"), "调味品/汤料：需标签法规与食品添加剂申报，油浸制品部分按酸化食品管理"),
    (("0712", "0802", "0806", "0804", "0810", "0813", "1202", "1207", "1211", "1008", "1104"),
     "干果/坚果/籽类：关注二氧化硫残留、黄曲霉毒素与农残限量，需防潮密封包装"),
    (("1704", "1806", "1904", "1905"), "烘焙/糖果零食：需配料表与营养标签、添加剂申报，美国需 FDA 食品设施注册"),
    (("1902",), "米面制品：需食品设施注册与 FSMA 预防性控制，含麸质过敏原标注"),
    (("2106", "2008"), "植物蛋白/营养食品：多国按保健食品或新食品监管，功能宣称受限"),
    (("2204", "2206", "2208"), "酒类：需酒类进口许可、税费与酒精度标签，部分市场限制销售渠道"),
    (("2005",), "腌渍/罐藏蔬菜：需酸度与商业无菌控制，标签需标注固形物与添加剂"),
)
_DEFAULT_COMPLIANCE = (
    "预包装食品：需配料表、营养标签与保质期标注，境外销售需 FDA 食品设施注册等设施合规"
)


def _aliases_for(category_id: str) -> list[str]:
    """品类别名：中文名 / 英文名 / 检索关键词，供 Agent 按常用名理解。"""
    meta = _CATALOG.get(category_id) or {}
    out: list[str] = []
    for key in ("name_cn", "name_en", "keyword"):
        value = str(meta.get(key) or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def _product_base_for(category_id: str) -> str:
    """品类商品名模板：直接取食品目录的中文名，缺失回退「食品」。"""
    return str((_CATALOG.get(category_id) or {}).get("name_cn") or "食品")


def _compliance_for(category_id: str) -> str:
    """品类合规要点：先看储运方式，再按 HS 大类前缀匹配。"""
    meta = _CATALOG.get(category_id) or {}
    storage = str(meta.get("storage_type") or "")
    if storage in _STORAGE_COMPLIANCE:
        return _STORAGE_COMPLIANCE[storage]
    hs4 = str(meta.get("hs4") or "")
    for prefixes, text in _HS_COMPLIANCE:
        if any(hs4.startswith(prefix) for prefix in prefixes):
            return text
    return _DEFAULT_COMPLIANCE


def _demo_stats() -> dict[tuple[str, str], dict[str, float]]:
    """聚合 demo 数据的 search_index / price_median / competition_index。"""
    sums: dict[tuple[str, str], list[float]] = {}
    with DEMO_CSV.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            key = (row["category"], row["market"])
            bucket = sums.setdefault(key, [0.0, 0.0, 0.0, 0.0])
            bucket[0] += float(row["search_index"])
            bucket[1] += float(row["price_median"])
            bucket[2] += float(row["competition_index"])
            bucket[3] += 1.0
    return {
        key: {
            "search_index": values[0] / values[3],
            "price_median": values[1] / values[3],
            "competition_index": values[2] / values[3],
        }
        for key, values in sums.items()
    }


def _round_price(value: float) -> float:
    if value >= 10:
        return round(value, 1)
    return round(value, 2)


def _price_range(category_meta: dict, market_factor: float, stats: dict) -> list[float]:
    base = 0.45 * float(category_meta["price"]) + 0.55 * stats.get(
        "price_median", float(category_meta["price"])
    )
    low = round(base * market_factor * 0.55, 1)
    high = round(base * market_factor * 1.8, 1)
    return [low, high]


def _demand_index(
    category_meta: dict,
    market_id: str,
    stats: dict,
    market_factor: float,
    category_mean: float,
) -> int:
    stat = stats.get("search_index", 50.0)
    raw = 0.88 * category_mean + 0.12 * stat + 18 * (market_factor - 0.5)
    return max(40, min(96, int(round(raw))))


def _competition_index(
    category_meta: dict,
    stats: dict,
    market_id: str,
) -> int:
    raw = (
        0.72 * stats.get("competition_index", 55.0)
        + 0.28 * float(category_meta["competition"])
    )
    return max(30, min(96, int(round(raw))))


def _opportunity_score(demand: int, competition: int) -> int:
    raw = demand * 0.6 - competition * 0.15 + 32
    return max(50, min(95, int(round(raw))))




# 市场资料：显示名、规模因子、主力平台、物流/季节/合规模板参数
MARKET_META: dict[str, dict] = {
    "us": {
        "name": "美国",
        "factor": 1.00,
        "tariff_factor": 1.0,
        "platforms": "Amazon、Walmart、eBay、Temu、TikTok Shop",
        "logistics": "直发 8-15 天，海外仓/FBA 2-5 天；旺季末端派送易延误，液体与易腐食品建议海外仓",
        "season": "旺季 10-12 月（黑五、圣诞），次高峰 6-7 月（Prime Day）；Q1 相对平缓",
        "compliance": "FDA 食品设施注册与 FSVP、21 CFR 101 营养与过敏原标签、各州销售税；禁售品与侵权高风险",
    },
    "eu": {
        "name": "欧洲",
        "factor": 0.82,
        "tariff_factor": 1.0,
        "platforms": "Amazon EU、eBay、Temu、TikTok Shop、OTTO",
        "logistics": "直发 10-20 天，德国仓/泛欧 FBA 3-6 天；清关需 IOSS，低货值走 DDP 更稳",
        "season": "旺季 10-12 月（黑五、圣诞），次高峰 6-8 月（夏促）；8 月部分国家休假",
        "compliance": "EC 1169/2011 食品标签、农残限量 EC 396/2005、食品接触材料 EC 1935/2004；EPR 需按时申报",
    },
    "sea": {
        "name": "东南亚",
        "factor": 0.65,
        "tariff_factor": 0.6,
        "platforms": "Shopee、Lazada、TikTok Shop、Temu",
        "logistics": "直发 7-15 天，海外仓 3-5 天；菲律宾/印尼清关与税号需提前准备",
        "season": "旺季 10-12 月（11.11、12.12），次高峰 4-5 月（斋月/开斋节，印尼、马来）",
        "compliance": "清真认证（印尼、马来）、BPOM/SIRIM 等本地食品登记、进口商登记",
    },
    "jp": {
        "name": "日本",
        "factor": 0.78,
        "tariff_factor": 0.7,
        "platforms": "Amazon JP、乐天、Yahoo!、Qoo10",
        "logistics": "直发 7-12 天，日本海外仓 2-3 天；食品进口申报与日文标签是硬门槛",
        "season": "旺季 11-12 月（圣诞、年末赠礼），次高峰 7-8 月（お盆、夏休）",
        "compliance": "食品卫生法进口申报、JAS 有机与特定标示、日文食品标签",
    },
    "ca": {
        "name": "加拿大",
        "factor": 0.95,
        "tariff_factor": 0.95,
        "platforms": "Amazon CA、Walmart CA、eBay",
        "logistics": "直发 10-18 天，海外仓 3-5 天；冬季暴雪影响末端派送，超大件建议海外仓",
        "season": "旺季 10-12 月（黑五、圣诞），次高峰 6-7 月（Prime Day、国庆日）",
        "compliance": "CFIA 食品进口合规、Health Canada 食品标准、英法双语食品标签",
    },
    "au": {
        "name": "澳大利亚",
        "factor": 0.88,
        "tariff_factor": 0.9,
        "platforms": "Amazon AU、eBay AU、Catch",
        "logistics": "直发 10-18 天，海外仓 3-5 天；低货值走 AUSPOST 或专线，动植物制品限制严",
        "season": "旺季 11-12 月（圣诞、Boxing Day），次高峰 5-6 月（财年末促销）",
        "compliance": "FSANZ 食品标准、进口食品检验计划（IFIS）、GST 税务登记；动植物源食品限制严",
    },
    "uk": {
        "name": "英国",
        "factor": 0.86,
        "tariff_factor": 0.9,
        "platforms": "Amazon UK、eBay UK、TikTok Shop UK",
        "logistics": "直发 10-16 天，海外仓 3-5 天；脱欧后单独清关，IOSS 与英国食品标签需评估",
        "season": "旺季 10-12 月（黑五、圣诞），次高峰 6-7 月（Prime Day）",
        "compliance": "英国 FSA 食品合规、UK 食品标签与过敏原标注、英国 EPR",
    },
    "kr": {
        "name": "韩国",
        "factor": 0.76,
        "tariff_factor": 0.75,
        "platforms": "Coupang、Naver Smart Store、Gmarket、Temu",
        "logistics": "直发 8-14 天，韩国海外仓 2-3 天；食品申报与标示审查严",
        "season": "旺季 11-12 月（年末赠礼），次高峰 5-6 月（父母节、儿童节）",
        "compliance": "MFDS 进口食品申报、韩文食品标签与添加剂审查；标识需韩文",
    },
    "de": {
        "name": "德国",
        "factor": 0.80,
        "tariff_factor": 1.0,
        "platforms": "Amazon DE、OTTO、eBay DE、Temu",
        "logistics": "直发 10-20 天，德国仓 3-5 天；包装法（VerpackG）与 EPR 注册必需",
        "season": "旺季 10-12 月（黑五、圣诞、Advent），次高峰 6-7 月（夏促）",
        "compliance": "EC 1169/2011 食品标签、德国包装法（VerpackG）、德语食品标签；EPR 注册必需",
    },
    "fr": {
        "name": "法国",
        "factor": 0.74,
        "tariff_factor": 1.0,
        "platforms": "Amazon FR、Cdiscount、Fnac、eBay FR",
        "logistics": "直发 10-20 天，法国仓 3-5 天；EPR（Triman/生态费）覆盖包装",
        "season": "旺季 10-12 月（黑五、圣诞），次高峰 1 月（冬季大促）",
        "compliance": "EC 1169/2011 食品标签、Triman 标识与生态费、法语食品标签",
    },
    "vn": {
        "name": "越南",
        "factor": 0.60,
        "tariff_factor": 0.5,
        "platforms": "Shopee、TikTok Shop、Lazada、Temu",
        "logistics": "直发 7-12 天，海外仓 3-4 天；清关与税号（MST）需提前准备",
        "season": "旺季 10-12 月（11.11、12.12），次高峰 1-2 月（春节 Tet）",
        "compliance": "越南食品产品自我声明、进口许可证；部分品类禁入",
    },
    "ru": {
        "name": "俄罗斯",
        "factor": 0.52,
        "tariff_factor": 1.15,
        "platforms": "Ozon、Wildberries、AliExpress Russia、Yandex Market",
        "logistics": "直发 15-30 天，海外仓/边境仓 5-10 天；EAC 食品符合性声明范围广，冬季物流波动大",
        "season": "旺季 10-12 月（新年、圣诞），次高峰 2-3 月（情人节、3.8 节）",
        "compliance": "EAC 食品符合性声明（TR CU 021/022）、俄语食品标识、强制性标签（部分品类）",
    },
    "hu": {
        "name": "匈牙利",
        "factor": 0.42,
        "tariff_factor": 1.0,
        "platforms": "Amazon HU 周边、eBay、AliExpress、Temu",
        "logistics": "直发 12-22 天，中东欧仓 4-7 天；清关需 IOSS/OSS，本地派送时效波动",
        "season": "旺季 10-12 月（黑五、圣诞），次高峰 6-7 月（夏促）",
        "compliance": "EC 1169/2011 食品标签、欧盟 EPR（按国注册）、匈牙利语食品标签",
    },
    "ae": {
        "name": "中东",
        "factor": 0.55,
        "tariff_factor": 1.05,
        "platforms": "Noon、Amazon AE、SHEIN、Temu",
        "logistics": "直发 10-20 天，迪拜仓 3-5 天；高温与斋月影响派送节奏",
        "season": "旺季 11-12 月（迪拜购物节、新年），次高峰 2-4 月（斋月、开斋节）",
        "compliance": "GSO 食品标签与 Halal 认证、食品进口登记、清关需进口商/保人；食品宗教要求严",
    },
    "mx": {
        "name": "墨西哥",
        "factor": 0.58,
        "tariff_factor": 1.05,
        "platforms": "Amazon MX、Mercado Libre、Temu、SHEIN",
        "logistics": "直发 15-30 天，墨西哥仓 4-7 天；清关与 RFC 税号、食品标签标准是关键难点",
        "season": "旺季 11-12 月（El Buen Fin、圣诞），次高峰 5-6 月（Hot Sale、儿童节）",
        "compliance": "COFEPRIS 食品进口许可、NOM-051 食品标签、RFC 税务登记；清关代理常用",
    },
}





MARKET_VARIANT = {
    "us": ["便携", "多功能"],
    "eu": ["轻量", "环保"],
    "sea": ["高性价比", "迷你"],
    "jp": ["日系简约", "小型"],
    "ca": ["防寒", "大容量"],
    "au": ["耐晒", "户外"],
    "uk": ["通勤", "紧凑"],
    "kr": ["韩系", "高颜值"],
    "de": ["高效", "耐用"],
    "fr": ["精致", "轻便"],
    "vn": ["平价", "轻巧"],
    "ru": ["防冻", "加强款"],
    "hu": ["经济", "实用"],
    "ae": ["高温适用", "紧凑"],
    "mx": ["耐用", "经济"],
}

MARKET_NOTE = {
    "us": "通勤与家庭高频需求",
    "eu": "环保与品质需求突出",
    "sea": "低价高频，年轻用户为主",
    "jp": "重视品质与收纳习惯",
    "ca": "冬季场景与居家需求",
    "au": "户外与耐候需求强",
    "uk": "通勤与家庭场景稳定",
    "kr": "颜值与尝新驱动",
    "de": "耐用与环保偏好明显",
    "fr": "设计与轻便偏好",
    "vn": "价格敏感、增长快",
    "ru": "耐寒与节日送礼场景",
    "hu": "价格敏感、实用导向",
    "ae": "高温与节日购物季",
    "mx": "促销季驱动，价格敏感",
}


PLATFORMS = [
    {
        "id": "amazon",
        "name": "Amazon",
        "markets": "美国、欧洲、日本、澳洲、加拿大、墨西哥、中东",
        "fees": "佣金约 8%-15%（品类不同），FBA 仓储配送费另计",
        "best_categories": "食品、调味酱料、休闲零食、茶叶、速食",
        "notes": "流量最大、退货率与认证要求也最高；FBA 适合稳定款，新品可自发货测款",
    },
    {
        "id": "ebay",
        "name": "eBay",
        "markets": "美国、欧洲、澳洲、英国、加拿大",
        "fees": "成交费约 12%-14%（含支付），个人/企业费率不同",
        "best_categories": "休闲零食、茶叶、地方特产、中低客单食品",
        "notes": "对卖家门槛低、翻新与二手友好；物流时效评分影响流量",
    },
    {
        "id": "temu",
        "name": "Temu",
        "markets": "美国、欧洲、东南亚、中东、拉美",
        "fees": "全托管/半托管模式，平台定价与备货制",
        "best_categories": "休闲零食、速食、调味品、坚果蜜饯、茶饮",
        "notes": "低价引流强、爆款起量快；平台控价与质检严，利润薄",
    },
    {
        "id": "tiktok_shop",
        "name": "TikTok Shop",
        "markets": "美国、英国、东南亚（印尼/泰国/越南/马来/菲律宾）、沙特",
        "fees": "佣金约 2%-8%（地区不同），达人带货分成另计",
        "best_categories": "休闲零食、调味品、速食、茶饮、养生食品",
        "notes": "内容驱动、短视频+直播转化快；达人合作与内容素材是关键",
    },
    {
        "id": "shein",
        "name": "SHEIN",
        "markets": "全球（重点美国、欧洲、中东、拉美）",
        "fees": "供应商供货/半托管模式，平台统一定价",
        "best_categories": "茶饮、休闲零食、坚果蜜饯、食品礼盒",
        "notes": "款式迭代极快，适合柔性供应链；对上新速度与价格要求高",
    },
    {
        "id": "shopee",
        "name": "Shopee",
        "markets": "东南亚（印尼/泰国/越南/马来/菲律宾/新加坡）、巴西、墨西哥",
        "fees": "佣金约 2%-6%，活动与物流费用另计",
        "best_categories": "休闲零食、调味品、速食、坚果蜜饯、茶饮",
        "notes": "东南亚份额领先，大促（11.11/12.12）爆发强；本地化运营重要",
    },
    {
        "id": "lazada",
        "name": "Lazada",
        "markets": "东南亚（印尼/泰国/越南/马来/菲律宾/新加坡）",
        "fees": "佣金约 2%-6%（品类不同）",
        "best_categories": "休闲零食、调味品、速食、茶饮、罐装食品",
        "notes": "客单略高于 Shopee，跨境物流体系成熟，适合品牌化运营",
    },
    {
        "id": "aliexpress",
        "name": "AliExpress",
        "markets": "俄罗斯、欧洲、中东、拉美、美国",
        "fees": "佣金约 5%-8%（品类不同）",
        "best_categories": "地方特产、调味品、休闲零食、茶叶、罐装食品",
        "notes": "新兴市场覆盖广，物流与价格带灵活；对物流时效与评分敏感",
    },
    {
        "id": "walmart",
        "name": "Walmart Marketplace",
        "markets": "美国、加拿大、墨西哥",
        "fees": "佣金约 6%-20%（品类不同），无月租",
        "best_categories": "食品、调味酱料、休闲零食、速食、罐装食品",
        "notes": "与亚马逊同客群竞争，审核严、卖家门槛高，适合有经验的卖家",
    },
    {
        "id": "etsy",
        "name": "Etsy",
        "markets": "美国、欧洲、英国、澳洲",
        "fees": "上架费 0.20 美元/件 + 成交费约 6.5%",
        "best_categories": "手工食品、茶叶、烘焙糕点、地方特产",
        "notes": "适合差异化手工与创意品，客群接受溢价；侵权与手工属性审查严",
    },
]

LOGISTICS = [
    {
        "id": "postal_small_packet",
        "name": "邮政小包/国际 e 邮宝",
        "time": "美国 8-15 天，欧洲 10-20 天，东南亚 7-12 天",
        "cost": "低，按克计费",
        "best_price_usd": "10-50",
        "notes": "适合轻小件与测款；旺季时效波动大，液体与易腐食品不可走",
    },
    {
        "id": "express_line",
        "name": "专线（空运专线/小包专线）",
        "time": "美国 6-10 天，欧洲 8-14 天，东南亚 5-9 天",
        "cost": "中，按公斤计费",
        "best_price_usd": "20-150",
        "notes": "粉末与部分敏感品可走，签收率与追踪完善，是目前跨境主流",
    },
    {
        "id": "sea_freight",
        "name": "海运/海派",
        "time": "美国 25-40 天，欧洲 35-50 天，东南亚 12-20 天",
        "cost": "低（体积/重量大时优势明显）",
        "best_price_usd": "100 以上或大件",
        "notes": "适合补货与海外仓备货；资金占用长，需提前排期",
    },
    {
        "id": "overseas_warehouse",
        "name": "海外仓（FBA 或第三方仓）",
        "time": "本地 1-5 天派送",
        "cost": "仓储费 + 配送费，单价中高",
        "best_price_usd": "稳定爆款",
        "notes": "提升转化与退换体验；需销量预测，滞销仓储费高",
    },
    {
        "id": "semi_managed",
        "name": "平台半托管/全托管",
        "time": "由平台仓统一履约，通常 5-10 天",
        "cost": "平台佣金 + 物流费，价格可控",
        "best_price_usd": "全品类小件",
        "notes": "适合缺运营团队的工厂型卖家；平台控价、结算周期长",
    },
]

REGULATIONS = [
    {
        "market": "美国",
        "framework": "FDA 食品设施注册与 FSVP + 21 CFR 101 标签 + 州级销售税",
        "key_certifications": "FDA 食品设施注册、FSVP 验证、营养与过敏原标签、加州 Prop 65",
        "documents": "商业发票、装箱单、提单、FDA 注册号、进口商记录",
        "notes": "食品责任与标签抽查严；建议每款保留配料表、营养检测与过敏原清单",
    },
    {
        "market": "欧盟",
        "framework": "EC 1169/2011 标签 + EC 396/2005 农残 + EC 1935/2004 接触材料 + EPR",
        "key_certifications": "食品标签合规、农残检测报告、食品接触材料符合性、各国 EPR",
        "documents": "EU 责任人声明、配料与营养检测报告、EPR 注册号",
        "notes": "包装 EPR 需按时申报；标签语言与过敏原标注需符合目的国要求",
    },
    {
        "market": "英国",
        "framework": "英国 FSA 食品标准 + 食品标签与过敏原标注 + 英国 EPR",
        "key_certifications": "英国食品标签合规、过敏原标注、EPR 注册",
        "documents": "英国责任人声明、配料与营养检测报告、EPR 注册号",
        "notes": "脱欧后清关与合规独立；低货值建议使用 IOSS 便捷清关",
    },
    {
        "market": "日本",
        "framework": "食品卫生法 + JAS 法 + 食品标示法",
        "key_certifications": "食品进口申报、JAS 有机认证、日文食品标签",
        "documents": "日文标签、进口食品申报受理书、进口商信息",
        "notes": "无食品进口申报难以清关销售；标签必须日文并含过敏原与保质期",
    },
    {
        "market": "东南亚",
        "framework": "各国本地认证 + 进口商登记（印尼/马来/泰国/越南/菲律宾）",
        "key_certifications": "BPOM、SIRIM、清真认证、各国食品登记",
        "documents": "进口许可证、食品登记证、清真证书、税号",
        "notes": "认证国别差异大；食品标签与清真要求是监管重点",
    },
    {
        "market": "墨西哥",
        "framework": "COFEPRIS + NOM-051 + RFC 税务登记",
        "key_certifications": "COFEPRIS 食品进口许可、NOM-051 标签",
        "documents": "RFC 税号、COFEPRIS 许可、进口商记录、清关代理文件",
        "notes": "清关与税务复杂度高，多数卖家依赖本地清关代理与海外仓",
    },
    {
        "market": "中东",
        "framework": "海湾 GSO 食品标准 + 各国认证（沙特/阿联酋/科威特等）",
        "key_certifications": "SASO 食品标签、ESMA 食品登记、清真认证",
        "documents": "进口商/保人、认证证书、食品进口登记",
        "notes": "沙特强制 SABER 平台注册；食品宗教合规要求严",
    },
]

PAYMENTS = [
    {
        "provider": "Payoneer",
        "features": "多平台收款 + 多币种账户，提现人民币/外币",
        "settlement": "平台回款后 1-3 个工作日到账",
        "notes": "覆盖 Amazon、Shopee、Lazada、Fiverr 等主流渠道",
    },
    {
        "provider": "PingPong",
        "features": "跨境电商收款 + 结汇 + 供应商付款",
        "settlement": "回款后通常 1-2 个工作日",
        "notes": "支持 Amazon、eBay、Temu、TikTok Shop 等多平台",
    },
    {
        "provider": "连连支付",
        "features": "跨境收款与结汇，费率透明",
        "settlement": "回款后 1-2 个工作日",
        "notes": "电商平台覆盖广，也支持独立站收单",
    },
    {
        "provider": "万里汇（WorldFirst）",
        "features": "平台收款 + 全球付款 + 汇率锁定",
        "settlement": "回款后 1-2 个工作日",
        "notes": "蚂蚁旗下，费率与汇率有竞争力",
    },
    {
        "provider": "平台回款",
        "features": "Amazon/Shopee/Temu 等按周期自动结算",
        "settlement": "Amazon 约 14 天，Shopee 约 7-14 天，Temu 托管约 15-30 天",
        "notes": "回款周期影响现金流，需预留备货资金",
    },
]

SOURCES = [
    {
        "name": "WTO Tariff Data",
        "url": "https://tao.wto.org/",
        "use": "查询各国约束税率与贸易统计，适合关税基线交叉核验",
    },
    {
        "name": "WCO 商品名称及编码协调制度",
        "url": "https://www.wcoomd.org/en/topics/nomenclature.aspx",
        "use": "HS 编码官方框架与版本说明",
    },
    {
        "name": "美国 HTS / USITC",
        "url": "https://hts.usitc.gov/",
        "use": "美国进口关税编码与税率查询",
    },
    {
        "name": "美国 CBP（海关与边境保护局）",
        "url": "https://www.cbp.gov/trade",
        "use": "美国进口程序、低值免税（de minimis）、合规公告",
    },
    {
        "name": "欧盟 Access2Markets",
        "url": "https://trade.ec.europa.eu/access-to-markets/en/home",
        "use": "欧盟关税、原产地规则、进口要求与贸易救济",
    },
    {
        "name": "欧盟食品安全（Food Safety）",
        "url": "https://food.ec.europa.eu/food-safety_en",
        "use": "欧盟食品安全法规、标签要求与进口说明",
    },
    {
        "name": "英国 Trade Tariff",
        "url": "https://www.gov.uk/trade-tariff",
        "use": "英国进口关税与编码查询",
    },
    {
        "name": "英国食品标准局（FSA）",
        "url": "https://www.food.gov.uk/",
        "use": "英国食品安全、标签与过敏原要求",
    },
    {
        "name": "日本海关（税関）",
        "url": "https://www.customs.go.jp/english/",
        "use": "日本关税、进口程序与统计",
    },
    {
        "name": "日本厚生劳动省（食品）",
        "url": "https://www.meti.go.jp/english/",
        "use": "日本食品卫生法、进口食品申报与检验",
    },
    {
        "name": "韩国关税厅",
        "url": "https://unipass.customs.go.kr/clip/index.do",
        "use": "韩国关税与进出口程序",
    },
    {
        "name": "墨西哥 SAT",
        "url": "https://www.sat.gob.mx/",
        "use": "墨西哥税务、RFC 与进口规定",
    },
    {
        "name": "澳大利亚 ABF",
        "url": "https://www.abf.gov.au/importing-exporting-and-managing-goods",
        "use": "澳洲进口程序、生物安全与限制品",
    },
    {
        "name": "加拿大 CBSA",
        "url": "https://www.cbsa-asfc.gc.ca/import-importation-eng.html",
        "use": "加拿大进口程序与关税",
    },
    {
        "name": "中国海关总署",
        "url": "https://www.customs.gov.cn/",
        "use": "HS 归类、出口退税与统计参考",
    },
    {
        "name": "UN Comtrade",
        "url": "https://comtradeplus.un.org/",
        "use": "全球商品贸易统计，观察品类进出口规模",
    },
]


def _preserve_or_generate_products(
    category_id: str,
    market_id: str,
    price_range: list[float],
    anchors: dict[tuple[str, str], list[dict]],
) -> list[dict]:
    if (category_id, market_id) in anchors:
        return anchors[(category_id, market_id)]

    product_base = _product_base_for(category_id)
    variants = MARKET_VARIANT[market_id]
    note = MARKET_NOTE[market_id]
    price_low = price_range[0]
    price_high = price_range[1]
    price_1 = _round_price(price_low + (price_high - price_low) * 0.45)
    price_2 = _round_price(price_low + (price_high - price_low) * 0.8)
    return [
        {
            "name": f"{variants[0]}{product_base}",
            "price": price_1,
            "note": note,
        },
        {
            "name": f"{variants[1]}{product_base}",
            "price": price_2,
            "note": f"{note}，升级款",
        },
    ]


def main() -> None:
    catalog, markets = _load_config()
    stats = _demo_stats()

    # 每个品类的 demo 搜索均值（跨市场），用于新组合的需求推算
    category_search_mean: dict[str, float] = {}
    category_monthly_sales: dict[str, dict[int, float]] = {}
    with DEMO_CSV.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            category_id = row["category"]
            month = int(row["date"][5:7])
            monthly = category_monthly_sales.setdefault(category_id, {})
            monthly[month] = monthly.get(month, 0.0) + float(row["sales_volume"])
    for (category_id, _market), row in stats.items():
        category_search_mean[category_id] = (
            category_search_mean.get(category_id, 0.0) + row["search_index"]
        )
    for category_id in category_search_mean:
        category_search_mean[category_id] /= len(markets)

    def _peak_months(category_id: str, config_month: int) -> list[int]:
        monthly = category_monthly_sales.get(category_id, {})
        ranked = sorted(monthly, key=lambda m: (monthly[m], m), reverse=True)[:2]
        months = [config_month] + [m for m in ranked if m != config_month]
        return sorted(months[:3])

    original = json.loads(MARKET_JSON.read_text(encoding="utf-8"))
    anchors: dict[tuple[str, str], list[dict]] = {}
    for cat in original["categories"]:
        for m in cat["markets"]:
            anchors[(cat["id"], m["id"])] = m["top_products"]

    original_order = [cat["id"] for cat in original["categories"]]
    category_ids = original_order + [
        cat_id for cat_id in catalog if cat_id not in original_order
    ]

    categories: list[dict] = []
    for category_id in category_ids:
        meta = catalog[category_id]
        markets_out: list[dict] = []
        for market_id, market_name in markets.items():
            market_meta = MARKET_META[market_id]
            stat = stats.get((category_id, market_id), {})
            stat.setdefault("search_index", category_search_mean.get(category_id, 55.0))
            stat.setdefault("competition_index", float(meta["competition"]))
            stat.setdefault("price_median", float(meta["price"]))

            demand = _demand_index(
                meta,
                market_id,
                stat,
                market_meta["factor"],
                category_search_mean.get(category_id, 55.0),
            )
            competition = _competition_index(meta, stat, market_id)
            opportunity = _opportunity_score(demand, competition)
            price_range = _price_range(meta, market_meta["factor"], stat)

            existing = next(
                (
                    market
                    for category in original["categories"]
                    if category["id"] == category_id
                    for market in category["markets"]
                    if market["id"] == market_id
                ),
                None,
            )
            if existing:
                demand = existing["demand_index"]
                competition = existing["competition_index"]
                opportunity = existing["opportunity_score"]
                price_range = existing["price_range_usd"]

            tariff = max(
                0,
                min(
                    35,
                    int(round(meta["tariff_base"] * 100 * market_meta["tariff_factor"])),
                ),
            )
            top_products = _preserve_or_generate_products(
                category_id, market_id, price_range, anchors
            )
            markets_out.append(
                {
                    "id": market_id,
                    "name": market_name,
                    "demand_index": demand,
                    "competition_index": competition,
                    "price_range_usd": price_range,
                    "opportunity_score": opportunity,
                    "top_products": top_products,
                    "platforms": market_meta["platforms"],
                    "logistics_note": market_meta["logistics"],
                    "compliance_note": (
                        _compliance_for(category_id)
                        + "；"
                        + market_meta["compliance"]
                    ),
                    "tariff_baseline": tariff,
                    "season_note": market_meta["season"],
                }
            )

        categories.append(
            {
                "id": category_id,
                "name": meta["name_cn"],
                "aliases": _aliases_for(category_id),
                "hs_code": {
                    "code": meta["hs4"],
                    "description": meta["hs_description"],
                },
                "price_band": {
                    "low_usd": round(meta["price"] * 0.55, 1),
                    "high_usd": round(meta["price"] * 1.75, 1),
                },
                "peak_months": _peak_months(category_id, meta["peak_month"]),
                "markets": markets_out,
            }
        )

    payload = {
        "updated_at": original.get(
            "updated_at", "2026-08-19T00:00:00+08:00"
        ),
        "description": (
            "跨境选品市场资料库。demand_index/competition_index/opportunity_score 为"
            " 0-100 综合参考分；price_range_usd/tariff_baseline 为基线参考值，"
            "实际以 HS6 编码与官方源核验为准。"
        ),
        "categories": categories,
        "recommendations": original["recommendations"],
        "platforms": PLATFORMS,
        "logistics": LOGISTICS,
        "regulations": REGULATIONS,
        "payments": PAYMENTS,
        "sources": SOURCES,
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    MARKET_JSON.write_text(text, encoding="utf-8")

    if RUNPACK_MARKET_JSON.parent.exists():
        shutil.copyfile(MARKET_JSON, RUNPACK_MARKET_JSON)
    print(f"generated: {MARKET_JSON} ({len(text)} bytes)")
    print(f"categories={len(payload['categories'])}")
    print(
        "market entries="
        f"{sum(len(cat['markets']) for cat in payload['categories'])}"
    )


if __name__ == "__main__":
    main()
