"""合规与市场准入评估（离线演示版）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComplianceRequirement:
    market: str
    item: str
    cost_usd: float
    duration_days: int
    source: str
    required: bool
    note: str


COMPLIANCE_MATRIX: dict[str, tuple[ComplianceRequirement, ...]] = {
    "us": (
        ComplianceRequirement("us", "FDA 食品设施注册（FSMA）", 2000.0, 14, "美国 FDA", True, "出口食品生产企业需注册并指定美国代理人"),
        ComplianceRequirement("us", "FSVP 外国供应商验证", 1500.0, 21, "美国 FDA", True, "进口商需完成 FSVP 验证并留存记录"),
        ComplianceRequirement("us", "营养标签与过敏原标注（21 CFR 101）", 1200.0, 28, "美国 FDA", False, "预包装食品配料表、营养声明与过敏原"),
    ),
    "eu": (
        ComplianceRequirement("eu", "食品标签法规 EC 1169/2011", 1800.0, 21, "欧盟委员会", True, "配料表、营养声明与过敏原标注"),
        ComplianceRequirement("eu", "农残限量 EC 396/2005", 1200.0, 14, "欧盟 EFSA", True, "植物源食品农残限量合规"),
        ComplianceRequirement("eu", "IOSS / VAT 注册", 300.0, 7, "欧盟税务", True, "低价值包裹"),
        ComplianceRequirement("eu", "食品接触材料合规 EC 1935/2004", 800.0, 14, "欧盟委员会", True, "包装与内衬材料需符合接触材料要求"),
    ),
    "sea": (
        ComplianceRequirement("sea", "目的国清关文件", 300.0, 5, "各国海关", True, "发票 / 产地证等"),
        ComplianceRequirement("sea", "清真 / 本地食品认证（可选）", 1000.0, 30, "目的国认证机构", False, "穆斯林市场清真食品认证"),
    ),
    "jp": (
        ComplianceRequirement("jp", "日本食品卫生法进口申报", 1800.0, 21, "日本厚生劳动省", True, "进口食品需完成申报与检验"),
        ComplianceRequirement("jp", "JAS 有机 / 特定标示食品申报", 1000.0, 30, "日本农林水产省", False, "有机或功能性标示食品"),
        ComplianceRequirement("jp", "目的国清关文件", 300.0, 5, "日本海关", True, "发票 / 产地证等"),
    ),
    "ca": (
        ComplianceRequirement("ca", "CFIA 食品进口合规", 1500.0, 21, "加拿大食品检验局", True, "进口食品需符合 CFIA 要求"),
        ComplianceRequirement("ca", "英法双语食品标签", 900.0, 14, "加拿大卫生部", True, "预包装食品标签需英法双语"),
        ComplianceRequirement("ca", "目的国清关文件", 300.0, 5, "加拿大边境服务署", True, "发票 / 产地证等"),
    ),
    "au": (
        ComplianceRequirement("au", "FSANZ 食品标准合规", 1600.0, 21, "澳新食品标准局", True, "食品成分与标签标准"),
        ComplianceRequirement("au", "进口食品检验计划（IFIS）", 800.0, 14, "澳大利亚农业水利环境部", True, "风险食品抽样检验"),
        ComplianceRequirement("au", "目的国清关文件", 300.0, 5, "澳大利亚海关", True, "发票 / 产地证等"),
    ),
    "uk": (
        ComplianceRequirement("uk", "英国食品标准局（FSA）合规", 1800.0, 21, "英国 FSA", True, "食品标签与安全标准"),
        ComplianceRequirement("uk", "英国食品标签与过敏原标注", 700.0, 14, "英国食品标准局", True, "预包装食品标签要求"),
        ComplianceRequirement("uk", "目的国清关文件", 300.0, 5, "英国海关", True, "发票 / 产地证等"),
    ),
    "kr": (
        ComplianceRequirement("kr", "MFDS 进口食品申报", 1700.0, 21, "韩国食品医药品安全处", True, "进口食品需完成申报"),
        ComplianceRequirement("kr", "韩文标签与食品添加剂审查", 900.0, 30, "韩国食品医药品安全处", False, "韩文标签与添加剂使用标准"),
        ComplianceRequirement("kr", "目的国清关文件", 300.0, 5, "韩国海关", True, "发票 / 产地证等"),
    ),
    "de": (
        ComplianceRequirement("de", "食品标签法规 EC 1169/2011", 1800.0, 21, "欧盟委员会", True, "配料表、营养声明与过敏原标注"),
        ComplianceRequirement("de", "农残限量 EC 396/2005", 1200.0, 14, "欧盟 EFSA", True, "植物源食品农残限量合规"),
        ComplianceRequirement("de", "IOSS / VAT 注册", 300.0, 7, "德国税务", True, "低价值包裹"),
        ComplianceRequirement("de", "德语食品标签合规", 800.0, 14, "德国联邦食品与农业部", True, "标签须使用德语并含过敏原提示"),
    ),
    "fr": (
        ComplianceRequirement("fr", "食品标签法规 EC 1169/2011", 1800.0, 21, "欧盟委员会", True, "配料表、营养声明与过敏原标注"),
        ComplianceRequirement("fr", "农残限量 EC 396/2005", 1200.0, 14, "欧盟 EFSA", True, "植物源食品农残限量合规"),
        ComplianceRequirement("fr", "IOSS / VAT 注册", 300.0, 7, "法国税务", True, "低价值包裹"),
        ComplianceRequirement("fr", "食品接触材料合规 EC 1935/2004", 800.0, 14, "欧盟委员会", True, "包装与内衬材料需符合接触材料要求"),
        ComplianceRequirement("fr", "法语标签合规", 500.0, 10, "法国海关", True, "产品说明与标签需法语"),
    ),
    "vn": (
        ComplianceRequirement("vn", "目的国清关文件", 300.0, 5, "越南海关", True, "发票 / 产地证等"),
        ComplianceRequirement("vn", "越南食品产品自我声明", 700.0, 20, "越南卫生部", False, "预包装食品需完成产品声明"),
    ),
    "ru": (
        ComplianceRequirement("ru", "EAC 食品符合性声明（TR CU 021/022）", 2000.0, 25, "欧亚经济联盟 EAC", True, "食品需 EAC 符合性声明"),
        ComplianceRequirement("ru", "目的国清关文件", 350.0, 6, "俄罗斯海关", True, "发票 / 产地证等"),
    ),
    "hu": (
        ComplianceRequirement("hu", "食品标签法规 EC 1169/2011", 1800.0, 21, "欧盟委员会", True, "配料表、营养声明与过敏原标注"),
        ComplianceRequirement("hu", "农残限量 EC 396/2005", 1200.0, 14, "欧盟 EFSA", True, "植物源食品农残限量合规"),
        ComplianceRequirement("hu", "IOSS / VAT 注册", 300.0, 7, "匈牙利税务", True, "低价值包裹"),
        ComplianceRequirement("hu", "食品接触材料合规 EC 1935/2004", 800.0, 14, "欧盟委员会", True, "包装与内衬材料需符合接触材料要求"),
    ),
    "ae": (
        ComplianceRequirement("ae", "目的国清关文件与产地证", 400.0, 7, "阿联酋海关", True, "发票 / 产地证等"),
        ComplianceRequirement("ae", "GCC 食品标签与清真认证（可选）", 1900.0, 25, "海湾标准化组织 GCC", False, "海湾市场食品标签与清真认证"),
        ComplianceRequirement("ae", "阿联酋食品进口登记", 900.0, 25, "阿联酋食品与农业部", False, "食品进口需完成登记"),
    ),
    "mx": (
        ComplianceRequirement("mx", "COFEPRIS 食品进口合规", 1900.0, 25, "墨西哥 COFEPRIS", True, "食品卫生与进口许可"),
        ComplianceRequirement("mx", "NOM-051 食品标签标准", 350.0, 7, "墨西哥经济部", True, "预包装食品标签与警示标注"),
    ),
}


@dataclass(frozen=True)
class ComplianceResult:
    market: str
    requirements: tuple[ComplianceRequirement, ...]
    total_cost_usd: float
    max_duration_days: int
    feasibility_score: float
    recommendation: str


class ComplianceAssessor:
    """按目标市场输出合规清单、认证成本与准入可行性评分。"""

    def assess(self, market: str) -> ComplianceResult:
        requirements = COMPLIANCE_MATRIX.get(market, ())
        if not requirements:
            return ComplianceResult(
                market=market,
                requirements=(),
                total_cost_usd=0.0,
                max_duration_days=0,
                feasibility_score=100.0,
                recommendation="暂无可演示的合规清单，请补充目标国法规。",
            )
        total = sum(item.cost_usd for item in requirements)
        max_days = max(item.duration_days for item in requirements)
        cost_score = max(0.0, 100.0 - total / 50.0)
        time_score = max(0.0, 100.0 - max_days * 2.0)
        score = round(0.6 * cost_score + 0.4 * time_score, 1)
        if score >= 80:
            recommendation = "市场准入可行性高，建议先完成必选认证并预留认证周期。"
        elif score >= 60:
            recommendation = "市场准入可行性中等，需评估认证成本与备货节奏。"
        else:
            recommendation = "认证成本或周期偏高，建议优先选择合规成本更低的市场或品类。"
        return ComplianceResult(
            market=market,
            requirements=requirements,
            total_cost_usd=round(total, 2),
            max_duration_days=max_days,
            feasibility_score=score,
            recommendation=recommendation,
        )
