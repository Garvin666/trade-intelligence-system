"""示例数据聚合：供三套系统“一键填充示例”使用。

示例统一由后端生成，避免前端硬编码与 engine / catalog / config 漂移。
业务方向为食品类，示例全部使用 `src/config.py::CATEGORY_CATALOG` 中的食品 SKU 编码。
"""

from __future__ import annotations

from typing import Any


def _four_brain_examples() -> list[dict[str, Any]]:
    from src.four_brain.engine import EXAMPLE_PAYLOADS

    return [
        {
            "id": f"four_brain_{index}",
            "label": str(item.get("keyword", "示例产品")),
            "payload": dict(item),
        }
        for index, item in enumerate(EXAMPLE_PAYLOADS)
    ]


def _trade_examples() -> list[dict[str, Any]]:
    return [
        {
            "id": "trade_latiao_us",
            "label": "辣条 × 美国",
            "inputs": {
                "category": "cn_latiao",
                "market": "us",
                "product_name": "辣条（网红休闲零食）",
                "unit_price_usd": 4.9,
                "procurement_cost_cny": 12.0,
                "quantity": 3000,
                "ad_rate": 0.12,
                "return_rate": 0.03,
                "inventory_days": 45,
                "fx_rate": 7.15,
            },
        },
        {
            "id": "trade_longjing_eu",
            "label": "西湖龙井 × 欧洲",
            "inputs": {
                "category": "cn_longjing",
                "market": "eu",
                "product_name": "西湖龙井（明前绿茶）",
                "unit_price_usd": 29.9,
                "procurement_cost_cny": 96.0,
                "quantity": 500,
                "ad_rate": 0.15,
                "return_rate": 0.04,
                "inventory_days": 60,
                "fx_rate": 7.15,
            },
        },
        {
            "id": "trade_dumplings_sea",
            "label": "速冻水饺 × 东南亚",
            "inputs": {
                "category": "cn_frozen_dumplings",
                "market": "sea",
                "product_name": "速冻水饺（猪肉白菜）",
                "unit_price_usd": 15.9,
                "procurement_cost_cny": 42.0,
                "quantity": 800,
                "ad_rate": 0.1,
                "return_rate": 0.05,
                "inventory_days": 30,
                "fx_rate": 7.15,
            },
        },
    ]


def _launch_report_examples() -> list[dict[str, Any]]:
    core = [
        {
            "id": "launch_latiao_us",
            "label": "辣条立项（美国站）",
            "fields": {
                "market": "us",
                "market_custom": "Amazon 美国站",
                "category": "cn_latiao",
                "category_custom": "Grocery & Gourmet Food > Snacks > Spicy Strips",
                "product": "辣条（网红休闲零食）",
                "competitors": (
                    "竞品 A：售价 $4.99、评分 4.6、评论数约 2,400、月销约 6,800，"
                    "核心卖点“麻辣过瘾、独立小包装”；竞品 B：售价 $6.49、评分 4.3、"
                    "评论数约 1,100、月销约 2,600，核心卖点“低钠配方、配料表干净”。"
                    "示例数据，需替换为实际调研结果。"
                ),
                "reviews": (
                    "好评关键词聚类：够辣、口感筋道、分量足、复购；差评关键词聚类："
                    "过油、偏咸、包装漏气、运输压碎。示例聚类，需替换。"
                ),
                "costs": (
                    "采购价 ¥12/件（100g 装）、头程运费 ¥1.8/件、关税按 HS 1905 计征、"
                    "美国 800 美元免税额内为 0。示例数据，需替换。"
                ),
                "keywords": (
                    "核心词 latiao spicy strips：月搜索量约 12,000、CPC 约 $0.42；"
                    "长尾词 chinese spicy snack：月搜索量约 8,800、CPC 约 $0.35。"
                    "示例数据，需替换。"
                ),
                "sections": [
                    "summary",
                    "market",
                    "competitors",
                    "pain_points",
                    "product",
                    "finance",
                    "plan",
                    "risk",
                ],
                "style": "logic",
                "output_format": "markdown",
            },
        },
        {
            "id": "launch_longjing_eu",
            "label": "西湖龙井立项（欧盟）",
            "fields": {
                "market": "eu",
                "market_custom": "Amazon 欧洲站（DE）",
                "category": "cn_longjing",
                "category_custom": "Grocery > Tea > Green Tea",
                "product": "西湖龙井（明前绿茶）",
                "competitors": "竞品以 50-100g 礼盒装绿茶为主，售价 18-35 欧元，主打产地区分与有机认证。示例数据，需替换。",
                "reviews": "差评集中在香气流失、包装密封性与欧盟农残标准说明不足。示例数据，需替换。",
                "costs": "采购价 ¥96/盒（100g）、头程 ¥6/盒、VAT 19%、农残检测费另计。示例数据，需替换。",
                "keywords": "longjing green tea：月搜索量约 9,500；loose leaf green tea：月搜索量约 22,000。示例数据，需替换。",
                "sections": ["summary", "market", "competitors", "pain_points", "finance", "risk"],
                "style": "brief",
                "output_format": "checklist",
            },
        },
    ]
    from src.four_brain import engine as four_brain

    seen = {str(item["label"]) for item in core}
    for index, payload in enumerate(four_brain.EXAMPLE_PAYLOADS):
        label = f"{payload['keyword']} 立项"
        if label in seen:
            continue
        category = str(payload.get("category") or "")
        if category not in four_brain.CATEGORY_CATALOG:
            category, _ = four_brain.infer_category(str(payload.get("keyword") or ""))
        mid_price = (float(payload.get("price_min", 0)) + float(payload.get("price_max", 0))) / 2
        unit_cost = float(payload.get("unit_cost", 0))
        freight = float(payload.get("freight_per_unit", 0))
        core.append(
            {
                "id": f"launch_generated_{index}",
                "label": label,
                "fields": {
                    "market": str(payload.get("market") or "us"),
                    "category": category,
                    "product": str(payload.get("keyword") or ""),
                    "competitors": "竞品以同价位主流产品为主，需替换为实际调研结果。",
                    "reviews": "评论聚类与痛点需结合产品评价数据替换。",
                    "costs": (
                        f"采购价约 ${unit_cost:.2f}/件、头程约 ${freight:.2f}/件、"
                        f"目标售价 ${mid_price:.2f}。示例数据，需替换。"
                    ),
                    "keywords": f"候选词：{payload.get('keyword')}",
                    "sections": [
                        "summary",
                        "market",
                        "competitors",
                        "pain_points",
                        "product",
                        "finance",
                        "plan",
                        "risk",
                    ],
                    "style": "logic",
                    "output_format": "markdown",
                },
            }
        )
        seen.add(label)
    return core


def _dashboard_examples() -> list[dict[str, Any]]:
    return [
        {
            "id": "dashboard_latiao_us",
            "label": "辣条 × 美国",
            "category": "cn_latiao",
            "market": "us",
            "keyword": "latiao spicy strips",
        },
        {
            "id": "dashboard_longjing_uk",
            "label": "西湖龙井 × 英国",
            "category": "cn_longjing",
            "market": "uk",
            "keyword": "longjing green tea",
        },
        {
            "id": "dashboard_dumplings_jp",
            "label": "速冻水饺 × 日本",
            "category": "cn_frozen_dumplings",
            "market": "jp",
            "keyword": "frozen chinese dumplings",
        },
        {
            "id": "dashboard_laoganma_ca",
            "label": "老干妈辣椒酱 × 加拿大",
            "category": "cn_laoganma",
            "market": "ca",
            "keyword": "laoganma chili crisp",
        },
        {
            "id": "dashboard_beef_jerky_au",
            "label": "麻辣牛肉干 × 澳大利亚",
            "category": "cn_beef_jerky",
            "market": "au",
            "keyword": "sichuan spicy beef jerky",
        },
        {
            "id": "dashboard_changsha_mifen_sea",
            "label": "长沙米粉 × 东南亚",
            "category": "cn_changsha_mifen",
            "market": "sea",
            "keyword": "changsha rice noodles",
        },
        {
            "id": "dashboard_hotpot_kr",
            "label": "自热火锅 × 韩国",
            "category": "cn_self_heating_hotpot",
            "market": "kr",
            "keyword": "self heating hot pot",
        },
        {
            "id": "dashboard_tanghulu_de",
            "label": "糖葫芦 × 德国",
            "category": "cn_tanghulu",
            "market": "de",
            "keyword": "tanghulu candied hawthorn",
        },
        {
            "id": "dashboard_goji_fr",
            "label": "宁夏枸杞 × 法国",
            "category": "cn_ningxia_goji",
            "market": "fr",
            "keyword": "ningxia goji berries",
        },
        {
            "id": "dashboard_mooncake_vn",
            "label": "广式月饼 × 越南",
            "category": "cn_mooncake",
            "market": "vn",
            "keyword": "cantonese mooncake",
        },
        {
            "id": "dashboard_baijiu_ru",
            "label": "小瓶白酒 × 俄罗斯",
            "category": "cn_baijiu_mini",
            "market": "ru",
            "keyword": "baijiu mini bottle",
        },
        {
            "id": "dashboard_goji_honey_ae",
            "label": "枸杞蜂蜜 × 阿联酋",
            "category": "cn_goji_honey",
            "market": "ae",
            "keyword": "goji honey",
        },
    ]


def _workflow_example() -> dict[str, Any]:
    return {
        "id": "workflow_latiao_us",
        "label": "辣条出口完整流程",
        "plan": {
            "keyword": "辣条（网红休闲零食）",
            "category": "cn_latiao",
            "market": "us",
            "price": 4.9,
            "procurement_cost_cny": 12.0,
            "target_margin": 0.35,
            "budget": 20000.0,
        },
    }


def build_examples_payload() -> dict[str, Any]:
    return {
        "dashboard": _dashboard_examples(),
        "four_brain": _four_brain_examples(),
        "trade": _trade_examples(),
        "launch_report": _launch_report_examples(),
        "workflow": [_workflow_example()],
    }


__all__ = ["build_examples_payload"]
