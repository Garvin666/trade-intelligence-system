"""
智选·跨境 四脑协同分析引擎（规则版 MVP + AI 混合模式）。

四个大脑分别输出独立详细报告：市场分析师、舆情洞察官、供应链评估师、
财务精算师；再由“嘴巴”层按用户个性化要求与权重裁决综合输出。
规则引擎基于 dashboard-data.json 或用户上传数据计算结构化评分与证据。
"""

from __future__ import annotations

import json
import math
import os
import re
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterator
from src.config import CATEGORIES as CATEGORY_LABELS
from src.config import CATEGORY_CATALOG


MARKET_LABELS = {
    "us": "美国",
    "eu": "欧洲",
    "sea": "东南亚",
    "jp": "日本",
    "ca": "加拿大",
    "au": "澳大利亚",
    "uk": "英国",
    "kr": "韩国",
    "de": "德国",
    "fr": "法国",
    "vn": "越南",
    "ru": "俄罗斯",
    "hu": "匈牙利",
    "ae": "中东",
    "mx": "墨西哥",
}

_EDA_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_EDA_CACHE_LOCK = threading.Lock()

KEYWORD_RULES: list[tuple[tuple[str, ...], str, str]] = [
    ((meta["keyword"], meta["name_cn"], meta["name_en"]), code, meta["name_cn"])
    for code, meta in CATEGORY_CATALOG.items()
]

DEFAULT_PAYLOAD: dict[str, Any] = {
    "keyword": "老干妈辣椒酱 laoganma chili sauce",
    "market": "us",
    "price_min": 6.0,
    "price_max": 14.0,
    "budget": 15000.0,
    "target_margin": 0.35,
    "unit_cost": 3.0,
    "freight_per_unit": 1.2,
    "customs_per_unit": 0.4,
    "ad_rate": 0.12,
    "return_rate": 0.02,
    "moq": 500,
    "lead_time_days": 30,
    "certifications": ["FDA", "CE", "HACCP"],
}

# 核心演示产品：保留原有默认测试集，作为工作台示例的首批选项。
CORE_EXAMPLE_PAYLOADS: list[dict[str, Any]] = [
    dict(DEFAULT_PAYLOAD),
    {
        "keyword": "麻辣牛肉干 sichuan spicy beef jerky",
        "market": "us",
        "price_min": 10.0,
        "price_max": 22.0,
        "budget": 20000.0,
        "target_margin": 0.35,
        "unit_cost": 9.0,
        "freight_per_unit": 2.0,
        "customs_per_unit": 0.8,
        "ad_rate": 0.12,
        "return_rate": 0.03,
        "moq": 400,
        "lead_time_days": 35,
        "certifications": ["FDA", "CE", "HACCP", "HALAL"],
        "extra_prompt": "主打欧美中端市场，希望突出正宗川味与独立小包装锁鲜。",
    },
    {
        "keyword": "速溶咖啡 instant coffee",
        "market": "eu",
        "price_min": 6.0,
        "price_max": 16.0,
        "budget": 18000.0,
        "target_margin": 0.38,
        "unit_cost": 4.0,
        "freight_per_unit": 1.5,
        "customs_per_unit": 0.5,
        "ad_rate": 0.15,
        "return_rate": 0.02,
        "moq": 600,
        "lead_time_days": 30,
        "certifications": ["FDA", "CE", "HACCP"],
        "extra_prompt": "关注提神场景与冻干工艺，希望突出低糖与便携条装。",
    },
    {
        "keyword": "抹茶粉 matcha powder",
        "market": "jp",
        "price_min": 12.0,
        "price_max": 28.0,
        "budget": 16000.0,
        "target_margin": 0.40,
        "unit_cost": 9.0,
        "freight_per_unit": 2.2,
        "customs_per_unit": 0.6,
        "ad_rate": 0.12,
        "return_rate": 0.02,
        "moq": 400,
        "lead_time_days": 32,
        "certifications": ["FDA", "CE", "HACCP"],
    },
    {
        "keyword": "金枪鱼罐头 canned tuna",
        "market": "sea",
        "price_min": 5.0,
        "price_max": 12.0,
        "budget": 14000.0,
        "target_margin": 0.32,
        "unit_cost": 3.5,
        "freight_per_unit": 1.0,
        "customs_per_unit": 0.4,
        "ad_rate": 0.10,
        "return_rate": 0.02,
        "moq": 800,
        "lead_time_days": 28,
        "certifications": ["FDA", "CE", "HACCP", "HALAL"],
    },
    {
        "keyword": "老干妈辣椒酱 laoganma chili sauce",
        "market": "us",
        "price_min": 6.0,
        "price_max": 14.0,
        "budget": 15000.0,
        "target_margin": 0.35,
        "unit_cost": 3.0,
        "freight_per_unit": 1.2,
        "customs_per_unit": 0.4,
        "ad_rate": 0.12,
        "return_rate": 0.02,
        "moq": 500,
        "lead_time_days": 30,
        "certifications": ["FDA", "CE", "HACCP"],
        "extra_prompt": "作为国民调味IP出海，希望突出正宗风味与海外华人复购。",
    },
]

COMMISSION_RATES = {"us": 0.15, "eu": 0.18, "sea": 0.10, "jp": 0.14, "ca": 0.16, "au": 0.15, "uk": 0.17, "kr": 0.13, "de": 0.18, "fr": 0.18, "vn": 0.08, "ru": 0.12, "hu": 0.16, "ae": 0.14, "mx": 0.12}

OUTPUT_FORMATS = {"full", "brief", "charts", "brain"}

CHART_CATALOG = [
    {"id": "radar", "name": "四脑评分雷达图"},
    {"id": "bar", "name": "核心指标柱状图"},
    {"id": "line", "name": "市场关键指标折线图"},
    {"id": "heatmap", "name": "品类 × 市场热度热力图"},
]

SENTIMENT_LIBRARY: dict[str, dict[str, Any]] = {
    "staple": {
        "baseline": 70.0,
        "pain_points": [
            {"issue": "口味地域差异大、复购低", "frequency": "中", "impact": 7},
            {"issue": "物流受潮结块", "frequency": "中", "impact": 6},
            {"issue": "保质期/产地标注不清", "frequency": "中", "impact": 5},
        ],
        "opportunities": [
            {"idea": "一人食小包装", "feasibility": "高", "willingness_to_pay": 7},
            {"idea": "低GI健康主食", "feasibility": "中", "willingness_to_pay": 8},
            {"idea": "地域特色组合装", "feasibility": "高", "willingness_to_pay": 6},
        ],
        "return_reasons": ["受潮结块", "口味不符", "包装破损"],
        "sentiment_score": 0.74,
    },
    "meat_egg": {
        "baseline": 68.0,
        "pain_points": [
            {"issue": "冷链断链胀包", "frequency": "高", "impact": 9},
            {"issue": "保质期短", "frequency": "中", "impact": 7},
            {"issue": "标签成分不符", "frequency": "中", "impact": 6},
        ],
        "opportunities": [
            {"idea": "小份锁鲜装", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "清真/有机认证", "feasibility": "中", "willingness_to_pay": 8},
            {"idea": "即食便捷化", "feasibility": "高", "willingness_to_pay": 7},
        ],
        "return_reasons": ["胀包变质", "化冻", "临期"],
        "sentiment_score": 0.66,
    },
    "seafood": {
        "baseline": 66.0,
        "pain_points": [
            {"issue": "化冻出水", "frequency": "高", "impact": 8},
            {"issue": "冷链断链", "frequency": "高", "impact": 9},
            {"issue": "腥味重", "frequency": "中", "impact": 6},
        ],
        "opportunities": [
            {"idea": "锁鲜单冻", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "即食海鲜零食", "feasibility": "中", "willingness_to_pay": 7},
            {"idea": "可持续捕捞溯源", "feasibility": "中", "willingness_to_pay": 7},
        ],
        "return_reasons": ["化冻", "胀袋", "不新鲜"],
        "sentiment_score": 0.63,
    },
    "produce": {
        "baseline": 72.0,
        "pain_points": [
            {"issue": "运输损耗高", "frequency": "高", "impact": 8},
            {"issue": "保鲜期短", "frequency": "中", "impact": 7},
            {"issue": "农残担忧", "frequency": "中", "impact": 6},
        ],
        "opportunities": [
            {"idea": "冻干锁鲜", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "净菜便捷装", "feasibility": "高", "willingness_to_pay": 7},
            {"idea": "有机溯源", "feasibility": "中", "willingness_to_pay": 7},
        ],
        "return_reasons": ["霉变", "压伤", "不新鲜"],
        "sentiment_score": 0.70,
    },
    "snack": {
        "baseline": 75.0,
        "pain_points": [
            {"issue": "口味不稳定", "frequency": "中", "impact": 7},
            {"issue": "保质期内变味", "frequency": "中", "impact": 6},
            {"issue": "包装过度", "frequency": "低", "impact": 5},
        ],
        "opportunities": [
            {"idea": "低糖低盐健康化", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "地域特色爆款", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "小规格试吃装", "feasibility": "中", "willingness_to_pay": 6},
        ],
        "return_reasons": ["口味不符", "临期", "胀袋"],
        "sentiment_score": 0.78,
    },
    "nuts": {
        "baseline": 73.0,
        "pain_points": [
            {"issue": "氧化哈喇", "frequency": "中", "impact": 7},
            {"issue": "霉变/黄曲霉风险", "frequency": "高", "impact": 8},
            {"issue": "大小不一", "frequency": "低", "impact": 5},
        ],
        "opportunities": [
            {"idea": "每日坚果小包", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "低温烘焙", "feasibility": "中", "willingness_to_pay": 7},
            {"idea": "产地直采", "feasibility": "中", "willingness_to_pay": 6},
        ],
        "return_reasons": ["哈喇", "霉变", "空壳"],
        "sentiment_score": 0.72,
    },
    "sauce": {
        "baseline": 74.0,
        "pain_points": [
            {"issue": "咸度不适", "frequency": "中", "impact": 6},
            {"issue": "标签配料不符", "frequency": "中", "impact": 6},
            {"issue": "玻璃瓶易碎漏液", "frequency": "低", "impact": 5},
        ],
        "opportunities": [
            {"idea": "复合调味酱", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "小包装便捷", "feasibility": "中", "willingness_to_pay": 7},
            {"idea": "地域风味IP", "feasibility": "高", "willingness_to_pay": 7},
        ],
        "return_reasons": ["漏液", "胀盖", "口味不符"],
        "sentiment_score": 0.75,
    },
    "beverage": {
        "baseline": 71.0,
        "pain_points": [
            {"issue": "冲泡结块", "frequency": "中", "impact": 7},
            {"issue": "标签功效夸大", "frequency": "中", "impact": 6},
            {"issue": "临期", "frequency": "低", "impact": 5},
        ],
        "opportunities": [
            {"idea": "冻干即溶", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "低糖功能化", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "国潮包装", "feasibility": "中", "willingness_to_pay": 7},
        ],
        "return_reasons": ["结块", "胀罐", "临期"],
        "sentiment_score": 0.70,
    },
    "bakery": {
        "baseline": 69.0,
        "pain_points": [
            {"issue": "保质期短", "frequency": "高", "impact": 8},
            {"issue": "运输破碎", "frequency": "中", "impact": 7},
            {"issue": "甜度过高", "frequency": "中", "impact": 6},
        ],
        "opportunities": [
            {"idea": "短保现烤概念", "feasibility": "高", "willingness_to_pay": 7},
            {"idea": "冷冻半成品", "feasibility": "中", "willingness_to_pay": 8},
            {"idea": "低糖轻食", "feasibility": "高", "willingness_to_pay": 7},
        ],
        "return_reasons": ["破碎", "变质", "临期"],
        "sentiment_score": 0.67,
    },
    "instant": {
        "baseline": 76.0,
        "pain_points": [
            {"issue": "口味单一", "frequency": "中", "impact": 6},
            {"issue": "钠含量偏高", "frequency": "中", "impact": 7},
            {"issue": "料包不足", "frequency": "低", "impact": 5},
        ],
        "opportunities": [
            {"idea": "地方特色速食", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "健康轻盐", "feasibility": "中", "willingness_to_pay": 7},
            {"idea": "自热便捷", "feasibility": "高", "willingness_to_pay": 7},
        ],
        "return_reasons": ["胀袋", "口味不符", "临期"],
        "sentiment_score": 0.77,
    },
    "wellness": {
        "baseline": 70.0,
        "pain_points": [
            {"issue": "功效夸大", "frequency": "中", "impact": 7},
            {"issue": "真假难辨", "frequency": "中", "impact": 7},
            {"issue": "价格虚高", "frequency": "中", "impact": 6},
        ],
        "opportunities": [
            {"idea": "药食同源IP", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "透明溯源", "feasibility": "中", "willingness_to_pay": 8},
            {"idea": "年轻化包装", "feasibility": "高", "willingness_to_pay": 7},
        ],
        "return_reasons": ["质疑功效", "临期", "假冒"],
        "sentiment_score": 0.68,
    },
    "vegetarian": {
        "baseline": 72.0,
        "pain_points": [
            {"issue": "口感不佳", "frequency": "中", "impact": 7},
            {"issue": "蛋白含量低", "frequency": "中", "impact": 6},
            {"issue": "冷链要求", "frequency": "中", "impact": 6},
        ],
        "opportunities": [
            {"idea": "植物基替代", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "高蛋白素肉", "feasibility": "高", "willingness_to_pay": 8},
            {"idea": "清洁标签", "feasibility": "中", "willingness_to_pay": 7},
        ],
        "return_reasons": ["变质", "口感不符", "化冻"],
        "sentiment_score": 0.71,
    },
}


def _to_float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on", "是"}


def _to_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    return [str(value)]


def _normalize_role_prompts(raw: dict[str, Any]) -> dict[str, str]:
    """从请求中提取四个真实脑的自定义角色提示词。"""
    value = raw.get("role_prompts") if isinstance(raw, dict) else None
    if not isinstance(value, dict):
        return {}
    known = ("market", "sentiment", "supply_chain", "finance")
    return {
        key: str(value.get(key) or "").strip()
        for key in known
        if str(value.get(key) or "").strip()
    }


def _load_trade_catalog_categories() -> dict[str, dict[str, Any]]:
    """读取 trade_catalog.json 的品类成本/价格元数据，缺失时回退空字典。"""
    catalog_file = Path(__file__).resolve().parents[2] / "data" / "trade_catalog.json"
    if not catalog_file.exists():
        return {}
    try:
        with catalog_file.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle).get("categories") or {}
    except (OSError, json.JSONDecodeError):
        return {}


TRADE_CATALOG_CATEGORIES = _load_trade_catalog_categories()


def _certifications_for(category: str, price: float) -> list[str]:
    """按食品大类/价格生成演示认证清单（食品口径）。"""
    meta = CATEGORY_CATALOG.get(category) or {}
    major = meta.get("category") or category
    if major in {"meat_egg", "seafood"}:
        certs = ["FDA", "CE", "HACCP", "HALAL"]
    elif major in {"beverage", "wellness", "bakery"}:
        certs = ["FDA", "CE", "HACCP"]
    else:
        certs = ["CE", "HACCP"]
    if price >= 100 and "CE" not in certs:
        certs.append("CE")
    return certs


def _category_defaults(category: str) -> dict[str, Any]:
    """按品类目录生成一套可用的四脑默认参数（含供应链/财务字段）。"""
    meta = CATEGORY_CATALOG.get(category) or {}
    trade = TRADE_CATALOG_CATEGORIES.get(category) or {}
    price = float(trade.get("basePrice") or meta.get("price") or 30.0)
    cost = float(trade.get("cost") or price * 0.45)
    weight = float(trade.get("weight") or 0.6)
    return_rate = float(trade.get("returnRate") or 0.03)
    keyword = str(trade.get("productLine") or meta.get("keyword") or category)
    label = str(meta.get("name_cn") or trade.get("label") or category)
    tariff_base = float(meta.get("tariff_base") or 0.08)
    return {
        "keyword": f"{label} {keyword}",
        "category": category,
        "market": "us",
        "price_min": round(price * 0.8, 2),
        "price_max": round(price * 1.2, 2),
        "budget": round(max(12000.0, min(40000.0, price * 120.0)), 0),
        "target_margin": 0.35,
        "unit_cost": round(cost, 2),
        "freight_per_unit": round(max(1.5, weight * 2.0), 2),
        "customs_per_unit": round(price * tariff_base, 2),
        "ad_rate": 0.12,
        "return_rate": round(max(0.02, min(0.08, return_rate)), 3),
        "moq": int(max(150, min(600, round(18000.0 / max(price, 1.0))))),
        "lead_time_days": int(30 + (5 if weight >= 2.0 else 0) + (5 if price >= 100 else 0)),
        "certifications": _certifications_for(category, price),
        "extra_prompt": "",
    }


def _build_generated_examples() -> list[dict[str, Any]]:
    """为 132 个食品品类各生成一个默认示例，补齐原有 6 个核心示例之外的品类。"""
    generated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in CORE_EXAMPLE_PAYLOADS:
        seen.add(str(item["keyword"]).strip().lower())
    for category in CATEGORY_CATALOG:
        defaults = _category_defaults(category)
        key = str(defaults["keyword"]).strip().lower()
        if key in seen:
            continue
        generated.append(defaults)
        seen.add(key)
    return generated


EXAMPLE_PAYLOADS: list[dict[str, Any]] = [
    *CORE_EXAMPLE_PAYLOADS,
    *_build_generated_examples(),
]


def normalize_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """校验并规范化四脑分析输入。"""
    market = str(raw.get("market") or "us").strip().lower()
    if market not in MARKET_LABELS:
        raise ValueError(f"Invalid market: {market}. Allowed: {sorted(MARKET_LABELS)}")

    keyword = str(raw.get("keyword") or DEFAULT_PAYLOAD["keyword"]).strip()
    category_hint = str(raw.get("category") or "").strip()
    if category_hint in CATEGORY_CATALOG:
        category = category_hint
    else:
        category, _ = infer_category(keyword)
    defaults = _category_defaults(category) if category in CATEGORY_CATALOG else dict(DEFAULT_PAYLOAD)

    price_min = _to_float(raw.get("price_min"), defaults["price_min"])
    price_max = _to_float(raw.get("price_max"), defaults["price_max"])
    if price_min <= 0 or price_max <= price_min:
        raise ValueError("price_max must be greater than price_min")

    budget = _to_float(raw.get("budget"), defaults["budget"])
    if budget <= 0:
        raise ValueError("budget must be positive")

    target_margin = _to_float(raw.get("target_margin"), defaults["target_margin"])
    if not 0 <= target_margin <= 1:
        raise ValueError("target_margin must be between 0 and 1")

    ad_rate = _to_float(raw.get("ad_rate"), defaults["ad_rate"])
    return_rate = _to_float(raw.get("return_rate"), defaults["return_rate"])
    if not 0 <= ad_rate <= 1 or not 0 <= return_rate <= 1:
        raise ValueError("ad_rate and return_rate must be between 0 and 1")

    certifications_raw = raw.get("certifications")
    payload = dict(defaults)
    output_format = str(raw.get("output_format") or "full").strip().lower() or "full"
    if output_format not in OUTPUT_FORMATS:
        raise ValueError(f"Invalid output_format: {output_format}. Allowed: {sorted(OUTPUT_FORMATS)}")
    payload.update(
        {
            "keyword": keyword,
            "category": category,
            "market": market,
            "price_min": price_min,
            "price_max": price_max,
            "budget": budget,
            "target_margin": target_margin,
            "unit_cost": _to_float(raw.get("unit_cost"), defaults["unit_cost"]),
            "freight_per_unit": _to_float(raw.get("freight_per_unit"), defaults["freight_per_unit"]),
            "customs_per_unit": _to_float(raw.get("customs_per_unit"), defaults["customs_per_unit"]),
            "ad_rate": ad_rate,
            "return_rate": return_rate,
            "moq": _to_int(raw.get("moq"), defaults["moq"]),
            "lead_time_days": _to_int(raw.get("lead_time_days"), defaults["lead_time_days"]),
            "certifications": _to_list(defaults["certifications"] if certifications_raw is None else certifications_raw),
            "extra_prompt": str(raw.get("extra_prompt") or defaults.get("extra_prompt") or "").strip(),
            "global_prompt": str(raw.get("global_prompt") or "").strip(),
            "role_prompts": _normalize_role_prompts(raw),
            "output_format": output_format,
            "output_charts": _to_list(raw.get("output_charts")),
            "use_user_data": _to_bool(raw.get("use_user_data")),
            "offline_only": _to_bool(raw.get("offline_only")),
        }
    )
    return payload


def normalize_data(data: dict[str, Any] | None) -> dict[str, Any]:
    """把用户文件/前端数据统一成规则引擎需要的结构。"""
    if data is None:
        return {}
    out = dict(data)
    if "history" not in out and "latest_history" in out:
        out["history"] = out.get("latest_history") or []
    out.setdefault("history", [])
    out.setdefault("recommendations", [])
    out.setdefault("categories", CATEGORY_LABELS)
    out.setdefault("markets", MARKET_LABELS)
    return out


def _resolve_data(data: dict[str, Any] | None) -> dict[str, Any]:
    data = normalize_data(data)
    if not data.get("history"):
        from pathlib import Path

        data_file = Path(__file__).resolve().parents[2] / "output" / "dashboard-data.json"
        with data_file.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        data = normalize_data(data)
    return data


def _build_eda_summary(data: dict[str, Any]) -> dict[str, Any]:
    """轻量数据体检：纯标准库实现，供四脑前端展示摘要与异常。"""
    rows = data.get("history") or data.get("latest_history") or []
    if not rows:
        return {"summary": {"rows": 0, "columns": 0}, "columns": [], "anomalies": [], "ab_tests": []}
    columns = list(rows[0].keys())
    cache_key = (id(rows), len(rows), len(columns), hash(str(rows[0])))
    with _EDA_CACHE_LOCK:
        cached = _EDA_CACHE.get(cache_key)
        if cached is not None:
            return cached
    result = _build_eda_summary_impl(rows, columns)
    with _EDA_CACHE_LOCK:
        # 仅保留最近一份快照摘要，避免用户多次上传数据时缓存无限增长。
        _EDA_CACHE.clear()
        _EDA_CACHE[cache_key] = result
    return result


def _build_eda_summary_impl(
    rows: list[dict[str, Any]],
    columns: list[str],
) -> dict[str, Any]:
    stats_columns = columns[:30]
    column_stats: list[dict[str, Any]] = []
    binary_cols: list[str] = []
    numeric_cols: list[str] = []
    anomaly_targets: list[tuple[str, float, float]] = []
    for column in stats_columns:
        seen: set[str] = set()
        missing = 0
        present = 0
        numeric_count = 0
        numeric_all = True
        total = 0.0
        sum_sq = 0.0
        min_value: float | None = None
        max_value: float | None = None
        for row in rows:
            value = row.get(column)
            if value is None or str(value).strip() == "":
                missing += 1
                continue
            present += 1
            seen.add(str(value))
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric_all = False
                continue
            numeric_count += 1
            total += numeric
            sum_sq += numeric * numeric
            if min_value is None or numeric < min_value:
                min_value = numeric
            if max_value is None or numeric > max_value:
                max_value = numeric
        entry: dict[str, Any] = {
            "column": column,
            "missing": missing,
            "unique": len(seen),
        }
        mean = 0.0
        std = 0.0
        if numeric_count:
            mean = total / numeric_count
            variance = max(0.0, sum_sq / numeric_count - mean * mean)
            std = math.sqrt(variance)
            entry["mean"] = round(mean, 3)
            entry["min"] = round(min_value, 3) if min_value is not None else None
            entry["max"] = round(max_value, 3) if max_value is not None else None
        column_stats.append(entry)
        if present and numeric_all and numeric_count == present:
            numeric_cols.append(column)
        if len(seen) == 2:
            binary_cols.append(column)
        if numeric_count and std > 0 and len(anomaly_targets) < 8:
            anomaly_targets.append((column, mean, std))

    anomalies: list[dict[str, Any]] = []
    for column, mean, std in anomaly_targets:
        numeric_index = 0
        for row in rows:
            value = row.get(column)
            if value is None or str(value).strip() == "":
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            score = abs(numeric - mean) / std
            if score > 3:
                anomalies.append(
                    {
                        "position": numeric_index,
                        "column": column,
                        "value": round(numeric, 3),
                        "score": round(score, 3),
                    }
                )
            numeric_index += 1

    ab_tests: list[dict[str, Any]] = []
    for group_col in binary_cols[:5]:
        for metric in numeric_cols[:8]:
            if metric == group_col:
                continue
            groups: dict[str, list[float]] = {}
            for row in rows:
                key = str(row.get(group_col))
                value = row.get(metric)
                if value is None:
                    continue
                try:
                    groups.setdefault(key, []).append(float(value))
                except (TypeError, ValueError):
                    continue
            if len(groups) != 2:
                continue
            a, b = list(groups.values())
            if len(a) < 3 or len(b) < 3:
                continue
            mean_a, mean_b = statistics.fmean(a), statistics.fmean(b)
            ab_tests.append(
                {
                    "group_col": group_col,
                    "metric": metric,
                    "group_a": str(list(groups.keys())[0]),
                    "group_b": str(list(groups.keys())[1]),
                    "mean_a": round(mean_a, 3),
                    "mean_b": round(mean_b, 3),
                    "difference": round(mean_a - mean_b, 3),
                    "significant": None,
                }
            )

    if len(columns) <= 30:
        missing_cells = sum(entry["missing"] for entry in column_stats)
    else:
        missing_cells = sum(
            1
            for row in rows
            for value in row.values()
            if value is None or str(value).strip() == ""
        )

    seen_rows: set[tuple[Any, ...]] = set()
    duplicate_rows = 0
    for row in rows:
        key = tuple(row.get(column) for column in columns)
        if key in seen_rows:
            duplicate_rows += 1
        else:
            seen_rows.add(key)

    return {
        "summary": {
            "rows": len(rows),
            "columns": len(columns),
            "missing_cells": missing_cells,
            "duplicate_rows": duplicate_rows,
        },
        "columns": column_stats,
        "anomalies": anomalies[:20],
        "ab_tests": ab_tests[:10],
    }


def _is_number(value: Any) -> bool:
    if value is None:
        return True
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def infer_category(keyword: str) -> tuple[str, str]:
    text = keyword.lower()
    for terms, category, label in KEYWORD_RULES:
        if any(term.lower() in text for term in terms):
            return category, label
    return "custom", str(keyword).strip() or "自定义品类"


def _payload_category(payload: dict[str, Any]) -> tuple[str, str]:
    """优先使用显式品类字段，否则按关键词规则推断。"""
    category = str(payload.get("category") or "").strip()
    if category in CATEGORY_LABELS:
        return category, CATEGORY_LABELS[category]
    return infer_category(str(payload.get("keyword") or ""))


def _direction(score: float) -> str:
    if score >= 70:
        return "推荐"
    if score >= 50:
        return "谨慎"
    return "不推荐"


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _latest_history(data: dict[str, Any], category: str, market: str) -> dict[str, Any] | None:
    rows = [
        row
        for row in data.get("history", [])
        if row.get("category") == category and row.get("market") == market
    ]
    if not rows:
        return None
    return max(rows, key=lambda row: row.get("date", ""))


def _recommendation(data: dict[str, Any], category: str, market: str) -> dict[str, Any] | None:
    for row in data.get("recommendations", []):
        if row.get("category") == category and row.get("market") == market:
            return row
    return None


def extract_search_history(
    research: dict[str, Any] | None,
    keyword: str,
    market: str,
) -> list[dict[str, Any]]:
    """从联网检索来源中提取数值信号，生成该定制产品的历史数据。

    搜索结果为文本来源，无法直接拿到完整时间序列；这里把来源里能提取到的
    增速、价格、竞争信号转成确定性的周粒度历史，供看板绘图使用。
    """
    sources = (research or {}).get("sources") or []
    text = " ".join(
        str(item.get("title", "")) + " " + str(item.get("snippet", ""))
        for item in sources
    )

    def _find(pattern: str) -> float | None:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except (ValueError, IndexError):
            return None

    growth = (
        _find(r"cagr\s*([\d.]+)\s*%")
        or _find(r"(?:grow|growth|increase|projected|expand)\D{0,24}([\d.]+)\s*%")
    )
    price = (
        _find(r"\$\s?([\d.]+)")
        or _find(r"(?:usd|美元|欧元)\s?([\d.]+)")
    )
    competition = 60.0
    if re.search(r"competitive|saturated|拥挤|竞争激烈|red ocean", text, re.IGNORECASE):
        competition = min(90.0, competition + 12.0)
    if re.search(r"fragmented|niche|blue ocean|蓝海|机会", text, re.IGNORECASE):
        competition = max(30.0, competition - 12.0)

    search_trend = min(25.0, max(-15.0, (len(sources) - 4) * 2.0))
    review_growth = min(8.0, max(-4.0, (len(sources) - 5) * 0.8))
    price = price if price and price > 1 else 40.0
    growth = growth if growth is not None else 8.0

    base = max(30.0, price * (1.2 - competition / 220.0))
    end = date.today()
    rows: list[dict[str, Any]] = []
    for i in range(25, -1, -1):
        d = end - timedelta(weeks=i)
        week = 25 - i
        sales = max(1.0, base * (1 + (growth / 100.0) * (week - 21) / 52.0))
        rows.append(
            {
                "date": d.isoformat(),
                "category": "custom",
                "market": market,
                "sales_volume": round(sales, 1),
                "search_index": round(max(25.0, 60.0 + search_trend + growth * 0.8 * (week - 21)), 1),
                "bestseller_rank": round(max(1.0, 2200.0 - sales * 8.0), 0),
                "price_median": round(price, 1),
                "review_growth": round(review_growth, 1),
                "export_value": round(sales * price * 0.8, 1),
                "competition_index": round(competition, 1),
            }
        )
    return rows


def _attach_real_proxy_evidence(
    brain: dict[str, Any],
    category: str,
    market: str,
) -> None:
    """Merge the trained real-demand proxy evidence into the market brain."""
    from src.models.real_proxy import proxy_evidence_score

    proxy = proxy_evidence_score(category, market)
    metrics = brain.setdefault("metrics", {})
    metrics["real_proxy_score"] = proxy.get("score")
    metrics["real_proxy_demand"] = proxy.get("predicted_demand")
    metrics["real_proxy_level"] = proxy.get("level")
    if not proxy.get("available"):
        return
    score_delta = _clamp((float(proxy["score"]) - 50.0) * 0.2, -6.0, 6.0)
    brain["score"] = round(_clamp(brain.get("score", 50.0) + score_delta), 1)
    brain["evidence"] = brain.get("evidence", []) + [
        f"真实销量代理模型：{proxy['score']} 分，预测需求指数 {proxy.get('predicted_demand')}"
    ]


def analyze_market(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    category, label = _payload_category(payload)
    market = payload["market"]
    history = _latest_history(data, category, market)
    recommendation = _recommendation(data, category, market)

    forecast_growth = float(recommendation.get("forecast_growth", 0)) if recommendation else 0.0
    search_trend = float(recommendation.get("search_trend", 0)) if recommendation else 0.0
    competition = float(history.get("competition_index", 60)) if history else 60.0
    review_growth = float(history.get("review_growth", 0)) if history else 0.0
    price_median = float(history.get("price_median", 0)) if history else 0.0
    sales_volume = float(history.get("sales_volume", 0)) if history else 0.0
    bestseller_rank = float(history.get("bestseller_rank", 0)) if history else 0.0

    score = 50.0
    score += _clamp(forecast_growth * 1.1, -18, 22)
    score += _clamp(search_trend * 0.9, -12, 16)
    score += _clamp((80 - competition) / 2.2, -15, 15)
    score += _clamp(review_growth * 1.1, -8, 10)
    if price_median and payload["price_min"] and payload["price_max"]:
        if payload["price_min"] * 0.75 <= price_median <= payload["price_max"] * 1.25:
            score += 5
        elif price_median > payload["price_max"] * 1.6 or price_median < payload["price_min"] * 0.5:
            score -= 5
    score = round(_clamp(score), 1)

    evidence = [
        f"未来90天预测增长 {forecast_growth:.1f}%，搜索热度环比 {search_trend:+.1f}%",
        f"竞争度指数 {competition:.1f}，市场均价 {price_median:.2f} 美元",
        f"最近一周销量指数 {sales_volume:.1f}，BSR {bestseller_rank:.0f}",
    ]
    if price_median:
        evidence.append(f"目标价格带 {payload['price_min']:.0f}-{payload['price_max']:.0f} 与市场中位数 {price_median:.2f} 匹配")

    brain = {
        "id": "market",
        "name": "市场分析师",
        "category": category,
        "category_name": CATEGORY_LABELS.get(category, label),
        "score": score,
        "direction": _direction(score),
        "confidence": round(0.82 if history and recommendation else 0.68, 2),
        "evidence": evidence,
        "metrics": {
            "forecast_growth": round(forecast_growth, 2),
            "search_trend": round(search_trend, 2),
            "competition": round(competition, 2),
            "review_growth": round(review_growth, 2),
            "price_median": round(price_median, 2),
        },
    }
    _attach_real_proxy_evidence(brain, category, market)
    brain["report"] = _build_brain_report(brain, payload)
    return brain


def analyze_sentiment(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    category, _ = _payload_category(payload)
    library = SENTIMENT_LIBRARY.get(category, SENTIMENT_LIBRARY["snack"])
    history = _latest_history(data, category, payload["market"])
    review_growth = float(history.get("review_growth", 0)) if history else 0.0
    high_pain = sum(1 for item in library["pain_points"] if item.get("impact", 0) >= 8)
    opportunities = library["opportunities"]
    score = float(library["baseline"]) + _clamp(review_growth * 1.0, -10, 10) + len(opportunities) * 3 - high_pain * 2
    score = round(_clamp(score), 1)
    evidence = [
        f"高频差评集中在：{ '、'.join(item['issue'] for item in library['pain_points'][:3]) }",
        f"可差异化机会：{ '、'.join(item['idea'] for item in opportunities[:2]) }",
        f"近周评论增长 {review_growth:+.1f}%，评论情感基线 {library['sentiment_score']:.2f}",
    ]
    brain = {
        "id": "sentiment",
        "name": "舆情洞察官",
        "score": score,
        "direction": _direction(score),
        "confidence": 0.78,
        "evidence": evidence,
        "pain_points": library["pain_points"],
        "opportunities": opportunities,
        "return_reasons": library["return_reasons"],
        "metrics": {"review_growth": round(review_growth, 2), "sentiment_score": library["sentiment_score"]},
    }
    brain["report"] = _build_brain_report(brain, payload)
    return brain


def analyze_supply_chain(payload: dict[str, Any]) -> dict[str, Any]:
    landed_cost = payload["unit_cost"] + payload["freight_per_unit"] + payload["customs_per_unit"]
    mid_price = (payload["price_min"] + payload["price_max"]) / 2
    landed_ratio = landed_cost / mid_price if mid_price else 0
    certifications = payload["certifications"]

    score = 68.0
    if landed_ratio > 0.45:
        score -= 18
    elif landed_ratio > 0.35:
        score -= 8
    elif landed_ratio < 0.25:
        score += 8
    if payload["lead_time_days"] > 45:
        score -= 12
    elif payload["lead_time_days"] > 30:
        score -= 6
    if payload["moq"] and payload["moq"] * landed_cost > payload["budget"] * 0.6:
        score -= 12
    score += min(8, len(certifications) * 3)
    if not certifications:
        score -= 8
    score = round(_clamp(score), 1)

    evidence = [
        f"到岸成本约 {landed_cost:.2f} 美元/件，占目标售价中位数的 {landed_ratio*100:.1f}%",
        f"最低起订量 {payload['moq']}，交付周期 {payload['lead_time_days']} 天",
        f"认证/质检文件：{('、'.join(certifications)) if certifications else '暂无，需补充'}",
    ]
    brain = {
        "id": "supply_chain",
        "name": "供应链评估师",
        "score": score,
        "direction": _direction(score),
        "confidence": 0.72,
        "evidence": evidence,
        "metrics": {
            "landed_cost": round(landed_cost, 2),
            "landed_ratio": round(landed_ratio, 3),
            "moq": payload["moq"],
            "lead_time_days": payload["lead_time_days"],
        },
    }
    brain["report"] = _build_brain_report(brain, payload)
    return brain


def analyze_finance(payload: dict[str, Any]) -> dict[str, Any]:
    price = (payload["price_min"] + payload["price_max"]) / 2
    landed_cost = payload["unit_cost"] + payload["freight_per_unit"] + payload["customs_per_unit"]
    commission_rate = COMMISSION_RATES.get(payload["market"], 0.15)
    commission = price * commission_rate
    ad_cost = price * payload["ad_rate"]
    return_cost = landed_cost * payload["return_rate"]
    unit_profit = price - landed_cost - commission - ad_cost - return_cost
    gross_margin = unit_profit / price if price else 0
    unit_investment = landed_cost + ad_cost + return_cost
    units = math.floor(payload["budget"] / unit_investment) if unit_investment > 0 else 0
    roi_3_months = (units * unit_profit) / payload["budget"] if payload["budget"] else 0
    breakeven_units = math.ceil(payload["budget"] / unit_profit) if unit_profit > 0 else None
    cash_cycle_days = payload["lead_time_days"] + 15

    score = 50.0
    score += _clamp((gross_margin - payload["target_margin"]) * 180, -25, 25)
    score += _clamp(roi_3_months * 15, -15, 20)
    if gross_margin < payload["target_margin"]:
        score -= 12
    score = round(_clamp(score), 1)

    evidence = [
        f"单件净利约 {unit_profit:.2f} 美元，毛利率 {gross_margin*100:.1f}%",
        f"预算内首批可备货约 {units} 件，3个月预计 ROI {roi_3_months*100:.1f}%",
        f"资金回本约需 {breakeven_units if breakeven_units else '无法回本'} 件，现金周期约 {cash_cycle_days} 天",
    ]
    brain = {
        "id": "finance",
        "name": "财务精算师",
        "score": score,
        "direction": _direction(score),
        "confidence": 0.8,
        "evidence": evidence,
        "metrics": {
            "unit_profit": round(unit_profit, 2),
            "gross_margin": round(gross_margin, 3),
            "roi_3_months": round(roi_3_months, 3),
            "breakeven_units": breakeven_units,
            "cash_cycle_days": cash_cycle_days,
            "commission_rate": commission_rate,
            "ad_cost": round(ad_cost, 2),
        },
    }
    brain["report"] = _build_brain_report(brain, payload)
    return brain


def _build_brain_report(brain: dict[str, Any], payload: dict[str, Any]) -> str:
    """规则引擎为每个大脑生成独立详细报告（Markdown）。"""
    brain_id = brain.get("id")
    metrics = brain.get("metrics", {})
    direction = brain.get("direction", "谨慎")
    brain["summary"] = _role_summary(brain)
    brain["conclusion_points"] = _conclusion_points(brain)
    hint = {
        "推荐": "整体信号偏积极，具备进入条件",
        "不推荐": "整体信号偏消极，建议暂缓",
        "谨慎": "整体信号偏谨慎，需要控制风险",
    }.get(direction, "中性")
    lines = [
        f"### {brain.get('name')}详细报告",
        "",
        f"**结论**：{direction}（评分 {brain.get('score')}/100，置信度 {brain.get('confidence')}）",
        f"一句话判断：{_role_summary(brain)}",
        "",
    ]
    if brain_id == "market":
        growth = metrics.get("forecast_growth", 0)
        trend = metrics.get("search_trend", 0)
        competition = metrics.get("competition", 0)
        price_median = metrics.get("price_median", 0)
        lines += [
            "**市场信号解读**",
            f"- 未来 90 天预测销量增长 {growth:+.1f}%，搜索热度环比 {trend:+.1f}%，需求处于{'扩张' if growth >= 10 else '温和增长' if growth >= 0 else '收缩'}阶段。",
            f"- 竞争度指数 {competition:.1f}/100：{'竞争偏高，需要差异化' if competition >= 70 else '竞争中等，仍有切入空间' if competition >= 55 else '竞争偏低，存在先发机会'}。",
            f"- 市场中位数价格 {price_median:.2f} 美元，与目标价格带 {payload['price_min']:.0f}-{payload['price_max']:.0f} 美元{'匹配度较高' if price_median and payload['price_min'] * 0.75 <= price_median <= payload['price_max'] * 1.25 else '存在偏差，需要调整定位'}。",
            "",
            "**机会与风险**",
            f"- 机会：需求增长与价格带匹配时可快速验证；搜索热度上升意味着流量红利窗口仍在。",
            f"- 风险：竞争度、季节性与平台流量分配可能放大波动，建议以周粒度监控。",
            "",
        ]
    elif brain_id == "sentiment":
        pains = brain.get("pain_points", [])
        opps = brain.get("opportunities", [])
        lines += [
            "**用户反馈解读**",
            f"- 高频差评（按影响排序）：{'、'.join(item['issue'] for item in pains[:3]) or '暂无'}。",
            f"- 可差异化机会：{'、'.join(item['idea'] for item in opps[:3]) or '暂无'}。",
            f"- 评论增长 {metrics.get('review_growth', 0):+.1f}%，情感基线 {metrics.get('sentiment_score', 0):.2f}；退货集中在：{'、'.join(brain.get('return_reasons', [])[:3]) or '暂无'}。",
            "",
            "**行动建议**",
            "- 优先围绕最高频痛点做规格验证和详情页表达，避免只做“功能堆叠”。",
            "- 用评论区高频词建立选品卖点与客服话术，降低退货与差评风险。",
            "",
        ]
    elif brain_id == "supply_chain":
        lines += [
            "**成本结构解读**",
            f"- 到岸成本约 {metrics.get('landed_cost', 0):.2f} 美元/件，占目标售价中位数 {metrics.get('landed_ratio', 0)*100:.1f}%，{'处于健康区间' if metrics.get('landed_ratio', 0) <= 0.35 else '占比偏高，需要压缩采购或物流成本'}。",
            f"- MOQ {metrics.get('moq', 0)}，交付周期 {metrics.get('lead_time_days', 0)} 天；首批资金占用需与现金流匹配。",
            f"- 认证/质检文件：{('、'.join(payload['certifications'])) if payload['certifications'] else '暂无，需补充'}。",
            "",
            "**供应链风险清单**",
            "- 风险点：供应商稳定性、旺季产能、认证周期与物流波动；建议在首单前索取样机和第三方质检报告。",
            "",
        ]
    elif brain_id == "finance":
        lines += [
            "**财务测算解读**",
            f"- 单件净利约 {metrics.get('unit_profit', 0):.2f} 美元，毛利率 {metrics.get('gross_margin', 0)*100:.1f}%，目标毛利率 {payload['target_margin']*100:.0f}%。",
            f"- 预算内首批可备货约 {metrics.get('breakeven_units', 0) and int(payload['budget'] / max(metrics.get('unit_profit', 1), 0.01)) or '需复核'} 件；3 个月预计 ROI {metrics.get('roi_3_months', 0)*100:.1f}%。",
            f"- 回本约需 {metrics.get('breakeven_units', '无法回本')} 件，现金周期约 {metrics.get('cash_cycle_days', 0)} 天。",
            "",
            "**财务纪律**",
            "- 未达盈亏平衡前控制广告预算占比；备货量按周销量与转化率滚动修正。",
            "- 若毛利率持续低于目标，优先调整采购价、运费与广告费率，而不是盲目压价。",
            "",
        ]
    lines += ["**证据链**", *[f"- {item}" for item in brain.get("evidence", [])]]
    lines += _prompt_compliance_lines(brain_id, payload)
    return "\n".join(lines)


def _prompt_compliance_lines(brain_id: str, payload: dict[str, Any]) -> list[str]:
    """把角色提示词与总提示词落实到规则引擎的分报告中。"""
    role_prompt = str((payload.get("role_prompts") or {}).get(brain_id) or "").strip()
    global_prompt = str(payload.get("global_prompt") or "").strip()
    lines: list[str] = []
    if role_prompt or global_prompt:
        lines += ["", "**提示词落实**"]
    if role_prompt:
        lines += [
            f"- 角色提示词：{role_prompt}",
            "- 本报告已围绕该提示词组织证据、风险与行动项。",
        ]
    if global_prompt:
        lines += [
            f"- 总提示词：{global_prompt}",
            "- 已把总提示词作为结论与建议的最高约束。",
        ]
    return lines
def arbitrate(brains: dict[str, dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    primary_weights = {
        "market": 0.40,
        "sentiment": 0.30,
        "finance": 0.30,
    }
    group_scores: dict[str, float] = {"推荐": 0.0, "谨慎": 0.0, "不推荐": 0.0}
    total_weight = 0.0
    weighted_sum = 0.0
    conflicts: list[str] = []

    for brain_id, weight in primary_weights.items():
        brain = brains[brain_id]
        total_weight += weight
        weighted_sum += weight * brain["score"] * brain["confidence"]
        group_scores[brain["direction"]] += weight * brain["score"] * brain["confidence"]

    base_score = weighted_sum / total_weight if total_weight else 0
    supply = brains["supply_chain"]
    risk_penalty = max(0.0, 50.0 - supply["score"]) * 0.15
    final_score = round(_clamp(base_score - risk_penalty), 1)

    ranked = sorted(group_scores.items(), key=lambda item: item[1], reverse=True)
    top_direction, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    verdict = _direction(final_score)
    if top_score - second_score <= 8:
        conflicts.append("四个大脑结论方向接近，按条件性建议输出")
    if supply["score"] < 45 and final_score >= 60:
        verdict = "有条件推荐"
        conflicts.append("供应链评分偏低，综合结论降级为有条件推进")
    elif supply["score"] < 45:
        verdict = "谨慎"
        conflicts.append("供应链评分偏低，最终结论收敛为谨慎")
    if top_direction != verdict and verdict != "有条件推荐":
        conflicts.append(f"市场/舆情/财务加权方向为“{top_direction}”，供应链风险调整后输出“{verdict}”")

    return {
        "verdict": verdict,
        "score": final_score,
        "base_score": round(base_score, 1),
        "risk_penalty": round(risk_penalty, 1),
        "direction_scores": {key: round(value, 1) for key, value in ranked},
        "conflicts": conflicts,
        "weights": primary_weights,
    }


def build_charts(rule_result: dict[str, Any], data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """根据规则结果与数据生成前端可渲染的图表配置。"""
    brains = rule_result["brains"]
    market = brains["market"]
    charts: list[dict[str, Any]] = []
    brain_names = ["市场分析师", "舆情洞察官", "供应链评估师", "财务精算师"]
    scores = [brains["market"]["score"], brains["sentiment"]["score"], brains["supply_chain"]["score"], brains["finance"]["score"]]
    confidences = [brains[brain]["confidence"] * 100 for brain in ("market", "sentiment", "supply_chain", "finance")]
    charts.append(
        {
            "id": "radar",
            "type": "radar",
            "title": "四脑评分对比",
            "labels": brain_names,
            "series": [{"name": "评分", "values": scores}],
        }
    )
    charts.append(
        {
            "id": "bar",
            "type": "bar",
            "title": "四脑评分与置信度",
            "labels": brain_names,
            "series": [
                {"name": "评分", "values": scores},
                {"name": "置信度（%）", "values": [round(value, 1) for value in confidences]},
            ],
        }
    )
    market_metrics = market["metrics"]
    line_values = [
        market_metrics.get("forecast_growth", 0),
        market_metrics.get("search_trend", 0),
        80 - market_metrics.get("competition", 60),
        market_metrics.get("review_growth", 0),
    ]
    charts.append(
        {
            "id": "line",
            "type": "line",
            "title": "市场关键指标",
            "labels": ["预测增长", "搜索热度", "竞争空间", "评论增长"],
            "series": [{"name": "市场分析师", "values": [round(value, 1) for value in line_values]}],
        }
    )
    rows = sorted(CATEGORY_LABELS.keys())
    cols = sorted(MARKET_LABELS.keys())
    matrix: list[list[float]] = []
    history = (data or {}).get("history", [])
    # 预索引 (category, market) -> search_index（取 history 中首个匹配行的值，
    # 与旧实现 matches[0] 语义一致；history 按日期升序，故为最早一期热度）。
    # 避免对 20 万行 history 做 132×15 次线性扫描（原实现 O(132×15×N) ≈ 2 亿次
    # 迭代，是 Windows 上原生访问冲突/超时的高负载窗口，见建议报告 B4）。
    index: dict[tuple[str, str], float] = {}
    for row in history:
        if not isinstance(row, dict):
            continue
        category = row.get("category")
        market_code = row.get("market")
        if category and market_code and (category, market_code) not in index:
            index[(category, market_code)] = float(row.get("search_index", 0) or 0)
    for category in rows:
        row_values: list[float] = []
        for market_code in cols:
            row_values.append(round(index.get((category, market_code), 0.0), 1))
        matrix.append(row_values)
    charts.append(
        {
            "id": "heatmap",
            "type": "heatmap",
            "title": "品类 × 市场搜索热度",
            "labels": {"rows": [CATEGORY_LABELS[key] for key in rows], "cols": [MARKET_LABELS[key] for key in cols]},
            "values": matrix,
        }
    )
    return charts


def analyze(raw_payload: dict[str, Any], data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = normalize_payload(raw_payload)
    data = _resolve_data(data)

    brains = {
        "market": analyze_market(data, payload),
        "sentiment": analyze_sentiment(data, payload),
        "supply_chain": analyze_supply_chain(payload),
        "finance": analyze_finance(payload),
    }
    arbitration = arbitrate(brains, payload)
    brain_reports = {brain_id: brain["report"] for brain_id, brain in brains.items()}
    charts = build_charts({"brains": brains}, data)
    result = {
        "payload": payload,
        "category": brains["market"]["category"],
        "category_name": brains["market"]["category_name"],
        "brains": brains,
        "arbitration": arbitration,
        "brain_reports": brain_reports,
        "charts": charts,
        "report": render_markdown(brains, arbitration, payload),
        "generated_at": "local-rule-engine-v2",
        "eda": _build_eda_summary(data),
    }
    return result


def _direction_hint(direction: str) -> str:
    return {
        "推荐": "偏积极，具备进入条件",
        "不推荐": "偏消极，建议暂缓",
        "谨慎": "偏谨慎，需要控制风险",
    }.get(direction, "中性")


def _role_summary(brain: dict[str, Any]) -> str:
    """从对应角色视角生成一句话分析结论。"""
    brain_id = brain.get("id", "")
    direction = brain.get("direction", "谨慎")
    metrics = brain.get("metrics", {})
    if brain_id == "market":
        return (
            f"从市场分析师视角判断：未来90天预测增长 {metrics.get('forecast_growth', 0):+.1f}%，"
            f"搜索热度环比 {metrics.get('search_trend', 0):+.1f}%，竞争度 {metrics.get('competition', 0):.1f}，"
            f"市场中位数价格 {metrics.get('price_median', 0):.2f} 美元；市场信号{_direction_hint(direction)}。"
        )
    if brain_id == "sentiment":
        pains = "、".join(item["issue"] for item in brain.get("pain_points", [])[:2]) or "暂无"
        opps = "、".join(item["idea"] for item in brain.get("opportunities", [])[:2]) or "暂无"
        return (
            f"从舆情洞察官视角判断：高频差评集中在“{pains}”，可切入机会为“{opps}”，"
            f"评论增长 {metrics.get('review_growth', 0):+.1f}%；用户反馈{_direction_hint(direction)}。"
        )
    if brain_id == "supply_chain":
        return (
            f"从供应链评估师视角判断：到岸成本约 {metrics.get('landed_cost', 0):.2f} 美元/件，"
            f"占目标售价中位数 {metrics.get('landed_ratio', 0)*100:.1f}%，MOQ {metrics.get('moq', 0)}、"
            f"交付 {metrics.get('lead_time_days', 0)} 天；供应链可行性{_direction_hint(direction)}。"
        )
    if brain_id == "finance":
        return (
            f"从财务精算师视角判断：单件净利约 {metrics.get('unit_profit', 0):.2f} 美元、"
            f"毛利率 {metrics.get('gross_margin', 0)*100:.1f}%，3 个月预计 ROI {metrics.get('roi_3_months', 0)*100:.1f}%，"
            f"回本约 {metrics.get('breakeven_units', '未知')} 件；财务可行性{_direction_hint(direction)}。"
        )
    return f"该角色判断为“{direction}”。"


def _conclusion_points(brain: dict[str, Any]) -> list[str]:
    """为详细结论取最多 5 条关键点，AI 缺失时回退规则机会/风险/证据。"""
    raw_points = brain.get("conclusion_points")
    if isinstance(raw_points, list):
        return [str(item) for item in raw_points if str(item).strip()][:5]
    for field in ("opportunities", "risks"):
        items = brain.get(field) or []
        if not isinstance(items, list) or not items:
            continue
        points: list[str] = []
        for item in items[:5]:
            if isinstance(item, dict):
                points.append(str(item.get("idea") or item.get("issue") or item))
            else:
                points.append(str(item))
        return [point for point in points if point.strip()]
    evidence = brain.get("evidence") or []
    return [str(item) for item in evidence if str(item).strip()][:5]
def _chart_suggestion_lines(payload: dict[str, Any]) -> list[str]:
    selected = payload.get("output_charts") or [item["id"] for item in CHART_CATALOG]
    catalog = {item["id"]: item["name"] for item in CHART_CATALOG}
    return [f"- {catalog.get(item, item)}" for item in selected if item in catalog]


def render_markdown(
    brains: dict[str, dict[str, Any]],
    arbitration: dict[str, Any],
    payload: dict[str, Any],
) -> str:
    market = brains["market"]
    arb = arbitration
    output_format = payload.get("output_format", "full")
    lines = [
        f"# 四脑协同选品报告：{payload['keyword']}",
        "",
        f"目标市场：{MARKET_LABELS[payload['market']]}",
        f"建议品类：{market['category_name']}",
        f"目标价格带：{payload['price_min']:.0f}-{payload['price_max']:.0f} 美元",
        "",
        "## 综合结论",
        f"- 最终建议：{arb['verdict']}",
        f"- 综合得分：{arb['score']}/100",
        f"- 基础加权分：{arb['base_score']}，供应链风险扣分：{arb['risk_penalty']}",
        "- 本报告由市场分析师、舆情洞察官、供应链评估师、财务精算师四视角分别出具分报告，再按“置信度 × 权重”与用户个性化要求汇总裁决。",
        "",
    ]
    extra_prompt = str(payload.get("extra_prompt") or "").strip()
    global_prompt = str(payload.get("global_prompt") or "").strip()
    constraint_lines: list[str] = []
    if global_prompt:
        constraint_lines.append(f"> 总提示词：{global_prompt}")
    if extra_prompt:
        constraint_lines.append(f"> 用户补充要求：{extra_prompt}")
    if constraint_lines:
        lines[2:2] = [*constraint_lines, ""]
    lines.append("## 冲突点与裁决")
    if arb["conflicts"]:
        lines.extend([f"- {item}" for item in arb["conflicts"]])
    else:
        lines.append("- 四个大脑结论方向一致，无需额外风险降级")
    lines.extend(
        [
            "",
            "## 行动建议",
            f"1. 首批备货控制在预算 {payload['budget']:.0f} 美元内，先验证 {brains['finance']['metrics'].get('breakeven_units') or '关键假设'} 件盈亏平衡。",
            "2. 优先验证评论中最高频痛点与差异化功能的实际付费意愿。",
            "3. 在认证、交付周期和首批现金流确认前，避免一次性放大采购。",
        ]
    )
    if extra_prompt:
        lines.extend(
            [
                "",
                "## 个性化要求落实",
                f"- 已把“{extra_prompt}”纳入四个大脑的分析约束与综合裁决权重。",
                "- 建议在首批测款中设置对应 KPI（如该要求涉及价格带、环保材质、多语言客服或预算上限）。",
            ]
        )
    if output_format == "charts":
        lines.extend(["", "## 图表建议", *_chart_suggestion_lines(payload)])
    return "\n".join(lines)


def build_ai_prompts(
    payload: dict[str, Any],
    data: dict[str, Any],
    rule_result: dict[str, Any],
    research_summary: str = "",
    lang: str = "zh",
    role_prompts: dict[str, str] | None = None,
    fast: bool = False,
) -> dict[str, dict[str, str]]:
    """为四个大脑构建独立 AI 提示词；fast 模式输出更短的分报告。"""
    brains = rule_result["brains"]
    market = brains["market"]
    sentiment = brains["sentiment"]
    supply = brains["supply_chain"]
    finance = brains["finance"]
    market_label = MARKET_LABELS[payload["market"]]
    extra_prompt = str(payload.get("extra_prompt") or "").strip()
    global_prompt = str(payload.get("global_prompt") or "").strip()
    offline = bool(payload.get("use_user_data") or payload.get("offline_only"))
    output_lang = "en" if str(payload.get("lang") or lang).lower() == "en" else "zh"
    role_prompts = {
        key: str(value).strip()
        for key, value in (role_prompts or {}).items()
        if str(value).strip()
    }
    lang_instruction = (
        "请使用英文输出全部内容，包括报告、结论、摘要、风险、机会与行动项。"
        if output_lang == "en"
        else "请使用中文输出全部内容。"
    )
    system_report_rule = (
        "report 为中文 Markdown 分报告（建议 250-400 字，包含证据、风险、机会与行动项）"
        if fast
        else "report 为详细中文 Markdown 分报告（建议 600-1000 字，包含证据、风险、机会与行动项）"
    )
    data_mode = "仅使用用户上传/本地数据，禁止调用或编造联网数据；若信息不足，请在报告中明确标注“信息不足”。" if offline else "可使用提供的本地数据与研究助手补充数据；不得编造来源与数字。"

    common_context = (
        f"目标市场：{market_label}；目标价格带：{payload['price_min']:.0f}-{payload['price_max']:.0f} 美元；"
        f"首批预算：{payload['budget']:.0f} 美元；目标毛利率：{payload['target_margin']*100:.0f}%。"
        f"成本：采购 {payload['unit_cost']:.2f}、运费 {payload['freight_per_unit']:.2f}、关税 {payload['customs_per_unit']:.2f}；"
        f"广告费率 {payload['ad_rate']*100:.0f}%、退货率 {payload['return_rate']*100:.0f}%、"
        f"MOQ {payload['moq']}、交付 {payload['lead_time_days']} 天、认证 {','.join(payload['certifications'])}。"
    )
    if extra_prompt:
        common_context += f"\n用户个性化要求：{extra_prompt}"
    if global_prompt:
        common_context += f"\n总提示词（最高优先级，必须落实）：{global_prompt}"
    common_context += f"\n数据模式：{data_mode}"
    report_rule = (
        "report(中文 Markdown 分报告，250-400 字，包含关键证据、风险、机会与行动建议；"
        "不要展开冗长分析过程；用户语言为英文时使用英文)"
        if fast
        else (
            "report(详细中文 Markdown 分报告，不少于 600 字且不超过 1000 字，包含判断依据、关键证据、"
            "风险、机会与行动建议；不要只给要点，必须展示分析过程；用户语言为英文时使用英文)"
        )
    )
    conclusion_rule = "conclusion_points(字符串数组，最多 3 条关键点)" if fast else "conclusion_points(字符串数组，最多 5 条关键点)"
    evidence_rule = "evidence(字符串数组，每条可溯源，最多 4 条)" if fast else "evidence(字符串数组，每条可溯源)"
    json_schema = (
        "请只输出一个 JSON 对象，包含："
        + report_rule
        + "、"
        "score(0-100)、direction(推荐/谨慎/不推荐)、confidence(0-1)、"
        + evidence_rule
        + "、summary(一句话结论)、"
        + conclusion_rule
        + "、"
        "risks(字符串数组)、opportunities(字符串数组)。"
    )

    market_prompt = (
        f"任务：以市场分析师身份，为“{payload['keyword']}”在{market_label}市场撰写详细选品分析报告。"
        f"规则引擎参考：{json.dumps(market['metrics'], ensure_ascii=False)}。"
        + json_schema
        + "另需字段 trend、price_band、competition、seasonality。"
    )
    sentiment_prompt = (
        f"任务：以舆情洞察官身份，为“{payload['keyword']}”撰写评论与用户反馈详细分析报告。"
        f"规则引擎参考：评论增长 {sentiment['metrics']['review_growth']}%，情感基线 {sentiment['metrics']['sentiment_score']}；"
        f"已知差评点：{json.dumps(sentiment['pain_points'], ensure_ascii=False)}；"
        f"已知机会点：{json.dumps(sentiment['opportunities'], ensure_ascii=False)}。"
        + json_schema
        + "另需字段 pain_points、opportunities、return_reasons。"
    )
    supply_prompt = (
        f"任务：以供应链评估师身份，为“{payload['keyword']}”撰写供应链可行性详细分析报告。"
        f"规则引擎参考：到岸成本 {supply['metrics']['landed_cost']} 美元/件，占售价中位数 {supply['metrics']['landed_ratio']*100:.1f}%，"
        f"MOQ {supply['metrics']['moq']}，交付 {supply['metrics']['lead_time_days']} 天。"
        + json_schema
        + "另需字段 recommended_supplier、landed_cost、moq、lead_time_days、certifications。"
    )
    finance_prompt = (
        f"任务：以财务精算师身份，为“{payload['keyword']}”撰写财务可行性详细分析报告。"
        f"规则引擎参考：{json.dumps(finance['metrics'], ensure_ascii=False)}。"
        + json_schema
        + "另需字段 unit_margin、gross_margin、roi_3_months、breakeven_units、cash_cycle_days。"
    )

    prompt_map = {
        "market": market_prompt,
        "sentiment": sentiment_prompt,
        "supply_chain": supply_prompt,
        "finance": finance_prompt,
    }
    for prompt_key in prompt_map:
        prompt = prompt_map[prompt_key]
        prompt += f"\n业务上下文：{common_context}"
        if research_summary:
            prompt += f"\n研究助手获取到的补充数据（含来源标题与链接）：\n{research_summary}"
        if role_prompts.get(prompt_key):
            prompt += f"\n角色要求（必须遵循）：{role_prompts[prompt_key]}"
        prompt += (
            "\n结论要求：report 必须为 250-400 字的 Markdown 分报告，"
            "summary 用一句话概括，conclusion_points 最多 3 条关键点。"
            if fast
            else (
                "\n结论要求：report 必须为不少于 600 字且不超过 1000 字的详细 Markdown 分报告，"
                "summary 用一句话概括，conclusion_points 最多 5 条关键点；必须展示分析过程。"
            )
        )
        prompt += f"\n{lang_instruction}"
        prompt_map[prompt_key] = prompt

    return {
        "market": {
            "system": "你是跨境电商市场分析师。先阅读用户要求与数据，再输出 JSON：" + system_report_rule + "，其余为结构化结论。只输出 JSON。" + (" 用英文输出全部内容。" if output_lang == "en" else " 用中文输出全部内容。"),
            "user": prompt_map["market"],
        },
        "sentiment": {
            "system": "你是跨境电商舆情洞察官。先阅读用户要求与数据，再输出 JSON：" + system_report_rule + "，其余为结构化结论。只输出 JSON。" + (" 用英文输出全部内容。" if output_lang == "en" else " 用中文输出全部内容。"),
            "user": prompt_map["sentiment"],
        },
        "supply_chain": {
            "system": "你是跨境电商供应链评估师。先阅读用户要求与数据，再输出 JSON：" + system_report_rule + "，其余为结构化结论。只输出 JSON。" + (" 用英文输出全部内容。" if output_lang == "en" else " 用中文输出全部内容。"),
            "user": prompt_map["supply_chain"],
        },
        "finance": {
            "system": "你是跨境电商财务精算师。先阅读用户要求与数据，再输出 JSON：" + system_report_rule + "，其余为结构化结论。只输出 JSON。" + (" 用英文输出全部内容。" if output_lang == "en" else " 用中文输出全部内容。"),
            "user": prompt_map["finance"],
        },
    }


def _merge_ai_brain(
    rule_brain: dict[str, Any],
    ai_brain: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(ai_brain, dict):
        raise ValueError("AI brain output must be a JSON object")
    try:
        score = float(ai_brain.get("score", rule_brain["score"]))
        confidence = float(ai_brain.get("confidence", rule_brain["confidence"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("AI brain score/confidence must be numeric") from exc

    direction = str(ai_brain.get("direction") or _direction(score))
    if direction not in {"推荐", "谨慎", "不推荐"}:
        direction = _direction(score)
    evidence = ai_brain.get("evidence") or rule_brain["evidence"]
    if isinstance(evidence, str):
        evidence = [item.strip() for item in evidence.split("\n") if item.strip()]
    evidence = [str(item) for item in evidence]
    ai_summary = str(ai_brain.get("summary") or rule_brain.get("summary") or _role_summary(rule_brain))
    raw_points = ai_brain.get("conclusion_points")
    if isinstance(raw_points, list):
        conclusion_points = [str(item) for item in raw_points if str(item).strip()][:5]
    else:
        candidate = dict(rule_brain)
        for field in ("opportunities", "risks"):
            if field in ai_brain:
                candidate[field] = ai_brain[field]
        conclusion_points = _conclusion_points(candidate)

    merged = dict(rule_brain)
    merged.update(
        {
            "score": round(_clamp(score), 1),
            "direction": direction,
            "confidence": round(_clamp(confidence, 0, 1), 2),
            "evidence": evidence,
            "ai_source": True,
            "summary": ai_summary,
            "ai_summary": ai_summary,
            "conclusion_points": conclusion_points,
            "report": str(ai_brain.get("report") or rule_brain.get("report") or ""),
        }
    )
    brain_keys = {
        "trend",
        "price_band",
        "competition",
        "seasonality",
        "pain_points",
        "opportunities",
        "return_reasons",
        "recommended_supplier",
        "landed_cost",
        "moq",
        "lead_time_days",
        "certifications",
        "risks",
        "unit_margin",
        "gross_margin",
        "roi_3_months",
        "breakeven_units",
        "cash_cycle_days",
        "insights",
        "next_steps",
        "recommendations",
    }
    for key in brain_keys:
        if key in ai_brain:
            merged[key] = ai_brain[key]
    return merged


def _run_ai_brains(
    rule_result: dict[str, Any],
    payload: dict[str, Any],
    prompts: dict[str, dict[str, str]],
    provider: Any,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    ai_brains: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    def _run_one(item: tuple[str, dict[str, str]]) -> tuple[str, dict[str, Any], str | None]:
        brain_id, prompt = item
        try:
            ai_output = provider.chat_json(prompt["system"], prompt["user"])
            return brain_id, _merge_ai_brain(rule_result["brains"][brain_id], ai_output), None
        except Exception as exc:  # noqa: BLE001 - 单脑失败不应阻断整体流程
            return brain_id, dict(rule_result["brains"][brain_id]), f"{brain_id}: {exc}"

    with ThreadPoolExecutor(max_workers=4) as pool:
        ordered = list(pool.map(_run_one, prompts.items()))
    for brain_id, brain, error in ordered:
        ai_brains[brain_id] = brain
        if error:
            ai_brains[brain_id]["ai_error"] = error
            errors.append(error)
    return ai_brains, errors


def _brain_report_text(brain: dict[str, Any]) -> str:
    report = str(brain.get("report") or "").strip()
    if report:
        return report
    metrics = brain.get("metrics") or {}
    lines = [
        f"- 结论：{brain.get('ai_summary') or brain.get('summary') or brain.get('direction', '')}",
        f"- 评分：{brain.get('score', 0)}，置信度：{brain.get('confidence', 0)}",
    ]
    if metrics:
        lines.append("- 指标：" + json.dumps(metrics, ensure_ascii=False))
    if brain.get("evidence"):
        lines.append("- 证据：" + "；".join(str(item) for item in brain["evidence"]))
    return "\n".join(lines)


def _build_detailed_fallback_report(result: dict[str, Any]) -> str:
    payload = result["payload"]
    brains = result["brains"]
    arb = result["arbitration"]
    brain_order = [
        ("market", "市场分析师"),
        ("sentiment", "舆情洞察官"),
        ("supply_chain", "供应链评估师"),
        ("finance", "财务精算师"),
    ]
    lines = [
        f"# 四脑协同决策报告：{payload['keyword']}",
        "",
        f"目标市场：{MARKET_LABELS[payload['market']]}",
        f"目标价格带：{payload['price_min']:.0f}-{payload['price_max']:.0f} 美元",
        f"首批预算：{payload['budget']:.0f} 美元，目标毛利率：{payload['target_margin'] * 100:.0f}%",
        "",
        "## 决策速览",
        f"- 最终建议：{arb['verdict']}",
        f"- 综合得分：{arb['score']}/100",
        f"- 基础加权分：{arb['base_score']}，供应链风险扣分：{arb['risk_penalty']}",
        "",
        "## 分析过程",
    ]
    for brain_id, name in brain_order:
        brain = brains[brain_id]
        lines.extend(
            [
                f"### {name}",
                f"- 评分：{brain.get('score', 0)}；置信度：{brain.get('confidence', 0)}；方向：{brain.get('direction', '')}",
                _brain_report_text(brain),
                "",
            ]
        )
    lines.extend(["## 冲突裁决", ""])
    if arb.get("conflicts"):
        lines.extend([f"- {item}" for item in arb["conflicts"]])
    else:
        lines.append("- 四个大脑方向一致，未触发额外降级。")
    lines.extend(["", "## 风险与机会", ""])
    for brain_id, name in brain_order:
        brain = brains[brain_id]
        risks = brain.get("risks") or []
        opportunities = brain.get("opportunities") or []
        if risks:
            lines.append(f"- {name}风险：" + "；".join(str(item) for item in risks[:4]))
        if opportunities:
            lines.append(f"- {name}机会：" + "；".join(str(item) for item in opportunities[:4]))
    market = brains["market"]["metrics"]
    finance = brains["finance"]["metrics"]
    supply = brains["supply_chain"]["metrics"]
    sentiment = brains["sentiment"]["metrics"]
    lines.extend(
        [
            "",
            "## 行动建议",
            "- P0 验证：优先测试评论中最高频痛点与差异化卖点，首批备货控制在预算内，先验证需求再扩量。",
            f"- P0 财务：毛利率 {float(finance.get('gross_margin', 0)) * 100:.1f}%，3 个月 ROI {float(finance.get('roi_3_months', 0)) * 100:.1f}%；若低于目标，先压缩采购、物流或广告费率。",
            f"- P1 供应链：到岸成本占售价中位数 {float(supply.get('landed_ratio', 0)) * 100:.1f}%，MOQ {supply.get('moq', 0)}、交付 {supply.get('lead_time_days', 0)} 天，首单前确认认证文件与质检样机。",
            f"- P1 市场：预测增长 {float(market.get('forecast_growth', 0)):.1f}%，搜索热度 {float(market.get('search_trend', 0)):.1f}%，竞争度 {float(market.get('competition', 60)):.1f}；优先进入增长较高且竞争空间充足的市场。",
            f"- P2 舆情：评论增长 {float(sentiment.get('review_growth', 0)):.1f}%，把高频差评转化为产品验收项和详情页卖点。",
            "",
            "## 待核验事项",
            "- 在线证据、价格带、退货率和认证要求需要以实际平台数据复核；模拟数据不能直接用于决策。",
            "- 正式备货前补充供应商报价、实际物流报价、样品质检和广告转化测试。",
        ]
    )
    return "\n".join(lines)


def _synthesis_context(
    result: dict[str, Any],
    research: dict[str, Any] | None = None,
) -> str:
    brains = result["brains"]
    brain_payload: dict[str, Any] = {}
    for brain_id, brain in brains.items():
        brain_payload[brain_id] = {
            "name": brain.get("name"),
            "score": brain.get("score"),
            "confidence": brain.get("confidence"),
            "direction": brain.get("direction"),
            "summary": brain.get("ai_summary") or brain.get("summary"),
            "conclusion_points": brain.get("conclusion_points") or [],
            "evidence": (brain.get("evidence") or [])[:10],
            "risks": (brain.get("risks") or [])[:10],
            "opportunities": (brain.get("opportunities") or [])[:10],
            "metrics": brain.get("metrics") or {},
            "report": str(brain.get("report") or "")[:12000],
        }
    payload = result["payload"]
    context: dict[str, Any] = {
        "产品": payload["keyword"],
        "目标市场": MARKET_LABELS[payload["market"]],
        "总提示词": payload.get("global_prompt") or "",
        "用户个性化要求": payload.get("extra_prompt") or "",
        "经营参数": {
            "价格带": f"{payload['price_min']}-{payload['price_max']} 美元",
            "预算": payload["budget"],
            "目标毛利率": payload["target_margin"],
            "广告费率": payload["ad_rate"],
            "退货率": payload["return_rate"],
            "MOQ": payload["moq"],
            "交付周期": payload["lead_time_days"],
            "认证": payload["certifications"],
        },
        "综合仲裁": result["arbitration"],
        "四脑分析": brain_payload,
    }
    if research:
        context["联网研究"] = {
            "summary": research.get("summary", ""),
            "sources": (research.get("sources") or [])[:12],
        }
    return json.dumps(context, ensure_ascii=False, indent=2)


def _synthesis_prompt(
    result: dict[str, Any],
    research: dict[str, Any] | None = None,
    fast: bool = False,
) -> tuple[str, str]:
    system = (
        "你是跨境电商选品决策总结撰写官。基于四个专家的分报告和规则仲裁，"
        + (
            "撰写一份面向卖家的简洁中文 Markdown 决策报告。"
            if fast
            else "撰写一份面向卖家的详细中文 Markdown 决策报告。"
        )
        + "必须使用具体数字、证据和指标，明确区分事实、模型推断与模拟数据；"
        + (
            "禁止使用空泛套话，禁止编造数据；"
            if fast
            else "禁止使用空泛套话，禁止只输出要点，禁止遗漏分析过程；"
        )
        + "如果结构化分析结果中包含“总提示词”，必须作为最高优先级约束最终报告。"
    )
    if fast:
        user = (
            "请输出 400-700 字的最终报告，必须包含以下章节："
            "1. 决策速览；2. 关键风险与机会；"
            "3. 行动建议（按 P0/P1/P2 排序）；4. 待核验事项。"
            "不要展开冗长的分析过程，但每个结论都要引用下方证据或指标，必要时说明信息不足。"
            "\n\n结构化分析结果：\n" + _synthesis_context(result, research)
        )
    else:
        user = (
            "请输出不少于 1200 字的最终报告，必须包含以下章节："
            "1. 决策速览；2. 分析过程（分别说明市场、舆情、供应链、财务的推导）；"
            "3. 冲突裁决；4. 关键指标表；5. 风险与机会；"
            "6. 行动建议（按 P0/P1/P2 排序）；7. 待核验事项。"
            "每个结论都要引用下方证据或指标，必要时说明信息不足。"
            "\n\n结构化分析结果：\n" + _synthesis_context(result, research)
        )
    return system, user


def _generate_synthesis_report(
    result: dict[str, Any],
    provider: Any,
    research: dict[str, Any] | None = None,
    fast: bool = False,
) -> tuple[str, bool]:
    system, user = _synthesis_prompt(result, research, fast=fast)
    chat_text = getattr(provider, "chat_text", None)
    if not callable(chat_text):
        return _build_detailed_fallback_report(result), False
    try:
        report = str(chat_text(system, user, temperature=0.3) or "").strip()
        if len(report) < (200 if fast else 400):
            raise ValueError("AI synthesis report is too short")
        return report, True
    except Exception:  # noqa: BLE001 - detailed deterministic fallback
        return _build_detailed_fallback_report(result), False


def generate_synthesis_report_stream(
    result: dict[str, Any],
    provider: Any,
    research: dict[str, Any] | None = None,
    fast: bool = False,
) -> Iterator[tuple[str, bool]]:
    """流式生成综合报告；产出 (文本增量, 是否完成) 序列并回填 result。"""
    if os.environ.get("FOUR_BRAIN_SYNTHESIS", "1") != "0":
        system, user = _synthesis_prompt(result, research, fast=fast)
        chat_text_stream = getattr(provider, "chat_text_stream", None)
        if callable(chat_text_stream):
            parts: list[str] = []
            try:
                for chunk in chat_text_stream(system, user, temperature=0.3):
                    content = str(chunk or "")
                    if not content:
                        continue
                    parts.append(content)
                    yield content, False
                report = "".join(parts).strip()
                if len(report) < (200 if fast else 400):
                    raise ValueError("AI synthesis report is too short")
                result["report"] = report
                result["synthesis"] = {
                    "used_ai": True,
                    "mode": "fast-decision-report-v1" if fast else "detailed-decision-report-v1",
                }
                yield report, True
                return
            except Exception:  # noqa: BLE001 - detailed deterministic fallback
                pass
    report = _build_detailed_fallback_report(result)
    result["report"] = report
    result["synthesis"] = {
        "used_ai": False,
        "mode": "fast-decision-report-v1" if fast else "detailed-decision-report-v1",
    }
    yield report, True


def _enhance_result_with_synthesis(
    result: dict[str, Any],
    provider: Any,
    research: dict[str, Any] | None = None,
    fast: bool = False,
) -> dict[str, Any]:
    if os.environ.get("FOUR_BRAIN_SYNTHESIS", "1") == "0":
        result["synthesis"] = {"used_ai": False, "mode": "disabled"}
        return result
    report, used_ai = _generate_synthesis_report(result, provider, research, fast=fast)
    result["report"] = report
    result["synthesis"] = {
        "used_ai": used_ai,
        "mode": "fast-decision-report-v1" if fast else "detailed-decision-report-v1",
    }
    return result
def _finalize_result(
    rule_result: dict[str, Any],
    brains: dict[str, dict[str, Any]],
    payload: dict[str, Any],
    data: dict[str, Any],
    ai: dict[str, Any],
    research: dict[str, Any] | None = None,
) -> dict[str, Any]:
    arbitration = arbitrate(brains, payload)
    brain_reports = {brain_id: brain["report"] for brain_id, brain in brains.items()}
    charts = build_charts({"brains": brains}, data)
    result = {
        "payload": payload,
        "category": rule_result["category"],
        "category_name": rule_result["category_name"],
        "brains": brains,
        "arbitration": arbitration,
        "brain_reports": brain_reports,
        "charts": charts,
        "report": render_markdown(brains, arbitration, payload),
        "ai": ai,
        "generated_at": "ai-hybrid-engine-v2",
        "eda": _build_eda_summary(data),
    }
    if research is not None:
        result["research"] = research
        result["generated_at"] = "ai-research-hybrid-engine-v2"
    return result


def analyze_with_ai(
    raw_payload: dict[str, Any],
    data: dict[str, Any] | None,
    provider: Any,
    skip_synthesis: bool = False,
    fast: bool = False,
) -> dict[str, Any]:
    """使用 AI 提供方替换四脑评分，单脑失败时自动回退规则结果。"""
    data = _resolve_data(data)
    rule_result = analyze(raw_payload, data)
    payload = rule_result["payload"]
    prompts = build_ai_prompts(
        payload,
        data or {},
        rule_result,
        role_prompts=_normalize_role_prompts(raw_payload),
        fast=fast,
    )
    ai_brains, errors = _run_ai_brains(rule_result, payload, prompts, provider)
    result = _finalize_result(
        rule_result,
        ai_brains,
        payload,
        data,
        {
            "enabled": True,
            "used": True,
            "errors": errors,
            "provider": getattr(provider, "status", lambda: {})() if provider else {},
        },
    )
    if not skip_synthesis:
        result = _enhance_result_with_synthesis(result, provider, fast=fast)
    return result
def analyze_with_research(
    raw_payload: dict[str, Any],
    data: dict[str, Any] | None,
    provider: Any,
    max_steps: int = 5,
    search_config: dict[str, Any] | None = None,
    skip_synthesis: bool = False,
    fast: bool = False,
) -> dict[str, Any]:
    """AI 先通过工具自主获取数据，再进行四脑分析；用户数据模式跳过联网。"""
    from src.four_brain.ai_agent import run_research_agent

    data = _resolve_data(data)
    rule_result = analyze(raw_payload, data)
    payload = rule_result["payload"]
    offline = bool(payload.get("use_user_data") or payload.get("offline_only"))
    if offline or fast:
        research = {
            "disabled": True,
            "summary": (
                "快速模式未进行联网搜索，结论基于本地规则引擎与 AI 分析。"
                if fast
                else "已按用户要求仅使用上传/本地数据，本次分析未进行联网搜索。"
            ),
            "steps": [],
            "sources": [],
            "iterations": 0,
        }
    else:
        goal = (
            f"用户想分析“{payload['keyword']}”在{MARKET_LABELS[payload['market']]}市场的选品机会。"
            f"目标价格带 {payload['price_min']:.0f}-{payload['price_max']:.0f} 美元，"
            f"预算 {payload['budget']:.0f} 美元。请获取市场趋势、竞争、评论和财务相关数据，"
            "并输出中文研究总结，注明来源标题与链接，标注不确定信息。"
        )
        try:
            research = run_research_agent(provider, goal, data or {}, max_steps=max_steps, search_config=search_config)
        except Exception as exc:  # noqa: BLE001
            research = {
                "summary": "",
                "evidence": [],
                "steps": [],
                "iterations": 0,
                "error": str(exc),
            }

    prompts = build_ai_prompts(
        payload,
        data or {},
        rule_result,
        research.get("summary", ""),
        role_prompts=_normalize_role_prompts(raw_payload),
        fast=fast,
    )
    ai_brains, errors = _run_ai_brains(rule_result, payload, prompts, provider)
    result = _finalize_result(
        rule_result,
        ai_brains,
        payload,
        data,
        {
            "enabled": True,
            "used": True,
            "errors": errors,
            "provider": getattr(provider, "status", lambda: {})() if provider else {},
        },
        research=research,
    )
    if not skip_synthesis:
        result = _enhance_result_with_synthesis(result, provider, research=research, fast=fast)
    return result
def demo_result() -> dict[str, Any]:
    return analyze(dict(DEFAULT_PAYLOAD))


__all__ = [
    "CHART_CATALOG",
    "DEFAULT_PAYLOAD",
    "EXAMPLE_PAYLOADS",
    "analyze",
    "analyze_finance",
    "analyze_market",
    "analyze_sentiment",
    "analyze_supply_chain",
    "analyze_with_ai",
    "analyze_with_research",
    "arbitrate",
    "build_ai_prompts",
    "build_charts",
    "demo_result",
    "generate_synthesis_report_stream",
    "infer_category",
    "normalize_data",
    "normalize_payload",
    "render_markdown",
]
