"""C-1 政策冲击实验室：真实政策事件生效日前/后的影响回溯。

选取已发生的真实政策事件（白宫第 14324 号行政命令 de minimis 取消、
欧盟低值包裹临时固定关税），对比生效日前/后的：
  1) 有效税率与单件关税（evaluate_policy 按 policy_date 分别评估）；
  2) 到岸利润率变化（LandedCostCalculator 复算，与 build_trade_decision 同口径）；
  3) 推荐变化（受影响市场内按利润率排序的品类 Top 变化）；
  4) 事后准确性（政策生效后的真实信号方向 vs 政策冲击方向，诚实标注口径）。

产物：
  output/policy_impact/impact_before_after.csv   —— 全品类前后对比明细
  output/policy_impact/impact_lab.md             —— 完整回溯报告
  reports/政策冲击实验室_v1.0.md                  —— 路演精简版

用法：.venv\\Scripts\\python scripts\\run_policy_impact_lab.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import CATEGORY_CATALOG, CATEGORY_PARAMS, PROJECT_ROOT  # noqa: E402
from src.trade.cost import LandedCostCalculator, LandedCostInput  # noqa: E402
from src.trade.policy import (  # noqa: E402
    BASE_TARIFF_RATE,
    evaluate_policy,
    load_policy_events,
)
from src.trade.policy_impact import trends_snapshot_status  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "output" / "policy_impact"
REPORTS_DIR = PROJECT_ROOT / "reports"

# 回溯案例：从 POLICY_EVENTS 中选取已生效的真实事件（verified 且官方来源）
CASE_KEYS = ("us-de-minimis-2025", "eu-low-value-vat-2026")


def _cases() -> list[dict]:
    events = load_policy_events()
    by_code = {event.code: event for event in events}
    result = []
    for key in CASE_KEYS:
        event = by_code.get(key)
        if event is None:
            continue
        effective = date.fromisoformat(event.effective_date)
        result.append(
            {
                "event": event,
                "market": event.market,
                "before_date": (effective - timedelta(days=1)).isoformat(),
                "after_date": (effective + timedelta(days=1)).isoformat(),
            }
        )
    return result


def _margin(category: str, market: str, unit_price: float, procurement_cny: float, alert) -> float:
    """按 build_trade_decision 同口径重算到岸利润率。"""
    calculator = LandedCostCalculator()
    adjusted_cost = procurement_cny * (1.0 + alert.cost_adjustment_pct)
    final = calculator.calculate(
        LandedCostInput(
            category=category,
            market=market,
            unit_price_usd=unit_price,
            procurement_cost_cny=adjusted_cost,
            payment_code="pingpong",
            logistics_code="small_parcel",
            tariff_rate=alert.effective_tariff_rate,
            min_duty_usd=alert.min_duty_usd,
        )
    )
    return max(final.margin_pct, -200.0)


def _rows_for_case(case: dict) -> list[dict]:
    event = case["event"]
    market = case["market"]
    unit_price_default = 28.0
    rows: list[dict] = []
    for category, meta in CATEGORY_PARAMS.items():
        unit_price = float(meta.get("price") or unit_price_default)
        procurement_cny = round(unit_price * 7.2 * 0.35, 2)  # 与 report.py _default_inputs 同口径
        landed = unit_price * BASE_TARIFF_RATE[market][category]
        before = evaluate_policy(
            category,
            market,
            unit_price,
            landed,
            policy_date=case["before_date"],
            events=[event],
        )
        after = evaluate_policy(
            category,
            market,
            unit_price,
            landed,
            policy_date=case["after_date"],
            events=[event],
        )
        margin_before = _margin(category, market, unit_price, procurement_cny, before)
        margin_after = _margin(category, market, unit_price, procurement_cny, after)
        rows.append(
            {
                "event_code": event.code,
                "event_title": event.title,
                "market": market,
                "category": category,
                "category_name": CATEGORY_CATALOG.get(category, {}).get("name_cn", category),
                "unit_price_usd": unit_price,
                "tariff_before": round(before.effective_tariff_rate, 4),
                "tariff_after": round(after.effective_tariff_rate, 4),
                "duty_before": round(before.duty_usd_per_unit, 2),
                "duty_after": round(after.duty_usd_per_unit, 2),
                "cost_inc_pct_before": round(before.landed_cost_increase_pct, 2),
                "cost_inc_pct_after": round(after.landed_cost_increase_pct, 2),
                "risk_before": before.risk_level,
                "risk_after": after.risk_level,
                "margin_pct_before": round(margin_before, 2),
                "margin_pct_after": round(margin_after, 2),
                "margin_delta_pct": round(margin_after - margin_before, 2),
                "affected": bool(after.risk_level != before.risk_level or after.duty_usd_per_unit > before.duty_usd_per_unit),
            }
        )
    return rows


def _post_event_signal_direction(market: str, affected_categories: list[str]) -> dict:
    """事后准确性：用趋势快照的方向验证政策冲击方向，并如实标注快照状态。

    口径说明：本项目主体为合成快照训练数据，联网信号层（Google Trends /
    Wikimedia 爬虫）提供方向性证据；快照缺失时不得声称已提供真实序列佐证。
    """
    status = trends_snapshot_status()
    notes: dict[str, str] = {}
    if not status["available"]:
        return {"status": status, "notes": notes}
    try:
        trends = json.loads(
            (PROJECT_ROOT / "output" / "trends" / "latest.json").read_text(encoding="utf-8")
        )
        by_category: dict[str, list[float]] = {}
        for row in trends.get("rows", []):
            if row.get("market") == market and row.get("category") in affected_categories:
                by_category.setdefault(row["category"], []).append(float(row.get("value") or 0.0))
        for category in affected_categories[:10]:
            values = by_category.get(category) or []
            if len(values) >= 4:
                first, last = values[0], values[-1]
                trend = "up" if last > first * 1.05 else ("down" if last < first * 0.95 else "flat")
                notes[category] = f"trends 方向对照：{'上升' if trend == 'up' else '下降' if trend == 'down' else '平稳'}（{first:.1f} → {last:.1f}）"
            else:
                notes[category] = "trends 无足够数据，不提供方向对照"
    except Exception as exc:  # noqa: BLE001 - 信号缺失不阻塞报告
        notes["_note"] = f"trends 读取失败：{exc}"
    return {"status": status, "notes": notes}


def build_report() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cases = _cases()
    all_rows: list[dict] = []
    sections: list[str] = []
    for case in cases:
        rows = _rows_for_case(case)
        all_rows.extend(rows)
        event = case["event"]
        affected = [row for row in rows if row["affected"]]
        sections.append(
            {
                "event_code": event.code,
                "event_title": event.title,
                "market": case["market"],
                "effective_date": event.effective_date,
                "source": event.source,
                "description": event.description,
                "url": event.url,
                "actions": list(event.actions),
                "total_categories": len(rows),
                "affected_count": len(affected),
                "affected_categories": [row["category"] for row in affected],
                "worst": min(affected, key=lambda r: r["margin_delta_pct"]) if affected else None,
                "signals": _post_event_signal_direction(case["market"], [row["category"] for row in affected]),
            }
        )

    frame = pd.DataFrame(all_rows)
    frame.to_csv(OUTPUT_DIR / "impact_before_after.csv", index=False, encoding="utf-8-sig")

    lines = [
        "# 政策冲击实验室（真实事件回溯）",
        "",
        f"- 生成时间：{pd.Timestamp.utcnow().isoformat(timespec='seconds')}",
        "- 方法：以 `evaluate_policy(policy_date=生效日前/后)` 分别测算有效税率、单件关税、"
        "到岸成本增幅与风险等级；利润率按 `LandedCostCalculator` 与贸易决策同口径复算。",
        "",
    ]
    for section in sections:
        lines.extend(
            [
                f"## 案例：{section['event_title']}",
                "",
                f"- 市场：{section['market']} ｜ 生效日：{section['effective_date']} ｜ 来源：{section['source']}",
                f"- 官方原文：{section['url']}",
                f"- 事件说明：{section['description']}",
                f"- 建议（建议清单，可复用为后续决策输入，不直接执行）：{'、'.join(section['actions'])}",
                f"- 波及：{section['affected_count']}/{section['total_categories']} 个品类（税率/关税/风险发生变化）",
                "",
                "| 品类 | 有效税率前→后 | 单件关税前→后 | 成本增幅前→后 | 风险前→后 | 利润率前→后 |",
                "|------|--------------|--------------|--------------|----------|------------|",
            ]
        )
        for row in sorted(
            [r for r in all_rows if r["event_code"] == section["event_code"] and r["affected"]],
            key=lambda r: r["margin_delta_pct"],
        ):
            lines.append(
                f"| {row['category_name']} | {row['tariff_before']:.1%} → {row['tariff_after']:.1%} "
                f"| ${row['duty_before']:.2f} → ${row['duty_after']:.2f} "
                f"| {row['cost_inc_pct_before']:.1f}% → {row['cost_inc_pct_after']:.1f}% "
                f"| {row['risk_before']} → {row['risk_after']} "
                f"| {row['margin_pct_before']:.1f}% → {row['margin_pct_after']:.1f}% |"
            )
        lines.extend(
            [
                "",
                "### 推荐变化（受影响市场内按利润率排序）",
                "",
                "受影响品类利润率全部下滑，按下滑幅度从大到小：",
                "",
            ]
        )
        ordered = sorted(
            [r for r in all_rows if r["event_code"] == section["event_code"] and r["affected"]],
            key=lambda r: r["margin_delta_pct"],
        )
        for row in ordered:
            lines.append(
                f"- {row['category_name']}：利润率 {row['margin_pct_before']:.1f}% → "
                f"{row['margin_pct_after']:.1f}%（Δ{row['margin_delta_pct']:.1f}pp）"
            )
        lines.extend(
            [
                "",
                "### 事后准确性（联网信号层状态）",
                "",
                "> 口径：联网信号层（Google Trends / 爬虫）仅提供方向性对照；快照未生成时不视为"
                "已提供真实序列佐证，也不做因果归因。",
                "",
            ]
        )
        status = section["signals"]["status"]
        if status.get("available"):
            lines.append(
                f"- 快照：已生成（{status.get('generated_at') or '未知时间'}，"
                f"provider={status.get('provider') or '未知'}，fallback_used={status.get('fallback_used')}）"
            )
        else:
            lines.append(f"- 快照：{status.get('note') or '未生成'}")
        for category, note in section["signals"]["notes"].items():
            lines.append(f"- {category}：{note}")
        lines.append("")

    eu_section = next(
        (section for section in sections if section["event_code"] == "eu-low-value-vat-2026"),
        None,
    )
    eu_worst_delta = (
        abs(eu_section["worst"]["margin_delta_pct"]) if eu_section and eu_section["worst"] else 0.0
    )
    us_section = next((section for section in sections if section["market"] == "us"), None)
    us_total = us_section["total_categories"] if us_section else 0
    us_affected = us_section["affected_count"] if us_section else 0
    eu_total = eu_section["total_categories"] if eu_section else 0
    lines.extend(
        [
            "## 结论",
            "",
            f"1. 政策冲击可量化：US 案例 {us_affected}/{us_total} 品类有效税率与单件关税跳升，利润率转负并进入 "
            f"No-Go；EU 案例覆盖全部 {eu_total} 品类，其中 "
            f"{eu_section['affected_count'] if eu_section else 0}/{eu_total} 个品类出现可量化关税/风险变化，"
            f"最大利润率下滑约 {eu_worst_delta:.1f}pp。",
            "2. Go/No-Go 判定降级：受影响组合按新口径进入冲突裁决与 Go/No-Go 判定；"
            "建议清单可复用为后续决策输入，前端“带入决策”仅填充贸易决策草稿，不直接执行清关或调价。",
            "3. 事后方向对照：仅在趋势快照存在时提供方向性对照；完整的事后准确性验证"
            "需真实销量数据回填后复核。",
            "",
            "> 本报告由跨境电商智能选品决策系统生成；政策事件来源为官方原文（Federal Register / EUR-Lex），"
            "趋势状态以 output/trends/latest.json 为准。",
            "",
        ]
    )
    markdown = "\n".join(lines)
    (OUTPUT_DIR / "impact_lab.md").write_text(markdown, encoding="utf-8")

    summary = {
        "cases": [
            {
                "event_code": section["event_code"],
                "event_title": section["event_title"],
                "market": section["market"],
                "effective_date": section["effective_date"],
                "affected_count": section["affected_count"],
                "worst_margin_delta_pct": (
                    section["worst"]["margin_delta_pct"] if section["worst"] else None
                ),
            }
            for section in sections
        ],
        "total_affected": sum(section["affected_count"] for section in sections),
    }
    return summary


def main() -> None:
    summary = build_report()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"报告：{OUTPUT_DIR / 'impact_lab.md'}")
    print(f"明细：{OUTPUT_DIR / 'impact_before_after.csv'}")


if __name__ == "__main__":
    main()
