"""市场日报生成与可选推送（借鉴 crosspulse 的日报结构，MIT）。"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.config import MARKET_DAILY_OUTPUT_DIR, MARKET_DAILY_PUSH_URL, POLICY_LATEST_JSON
from src.analysis.anomaly import load_latest_anomalies
from src.data.crawler_signals import load_latest_snapshot
from src.data.customs import load_latest_customs
from src.data.platform_rankings import load_latest_rankings
from src.data.supplier_sourcing import load_latest_suppliers
from src.data.trends import load_latest_trends


def _fmt_time(value: Any) -> str:
    return str(value or "-")


def build_market_daily_markdown(
    report_date: str | date,
    *,
    crawler: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    trends: dict[str, Any] | None = None,
    rankings: dict[str, Any] | None = None,
    customs: dict[str, Any] | None = None,
    anomalies: dict[str, Any] | None = None,
    suppliers: dict[str, Any] | None = None,
) -> str:
    crawler = crawler if crawler is not None else load_latest_snapshot()
    policy = policy if policy is not None else _load_policy()
    trends = trends if trends is not None else load_latest_trends()
    rankings = rankings if rankings is not None else load_latest_rankings()
    customs = customs if customs is not None else load_latest_customs()
    anomalies = anomalies if anomalies is not None else load_latest_anomalies()
    suppliers = suppliers if suppliers is not None else load_latest_suppliers()

    lines = [
        f"# 市场日报 {report_date}",
        "",
        f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 联网快照：{_fmt_time(crawler.get('generated_at'))}，回退 {'是' if crawler.get('fallback_used') else '否'}",
        f"- Google Trends：{_fmt_time(trends.get('generated_at'))}，回退 {'是' if trends.get('fallback_used') else '否'}",
        f"- 平台榜单：{_fmt_time(rankings.get('generated_at'))}，来源 {rankings.get('source_count', 0)} 条",
        f"- 海关出口：{_fmt_time(customs.get('generated_at'))}，"
        f"来源 {customs.get('provider', '-')}，回退 {'是' if customs.get('fallback_used') else '否'}",
        f"- 异常检测：{_fmt_time(anomalies.get('generated_at'))}，"
        f"异常 {anomalies.get('source_count', 0)} 条",
        f"- 货源/供应商：{_fmt_time(suppliers.get('generated_at'))}，"
        f"来源 {suppliers.get('provider', '-')}，回退 {'是' if suppliers.get('fallback_used') else '否'}",
        "",
    ]

    lines.append("## 一、推荐组合")
    lines.append("")
    combos = crawler.get("combos") or []
    if combos:
        lines.append("| 排名 | 品类 | 市场 | 关键词 | 浏览趋势 | 可信度 |")
        lines.append("|---|---|---|---|---|---|")
        for index, combo in enumerate(combos[:10], start=1):
            lines.append(
                f"| {index} | {combo.get('category_name') or combo.get('category')} "
                f"| {combo.get('market_name') or combo.get('market')} "
                f"| {combo.get('keyword')} "
                f"| {combo.get('pageview_trend_pct', 0):+.1f}% "
                f"| {combo.get('credibility_level', 'low')} |"
            )
    else:
        lines.append("暂无推荐组合快照。")
    lines.append("")

    lines.append("## 二、政策与风险")
    lines.append("")
    events = policy.get("events") or []
    if events:
        lines.append("| 日期 | 市场 | 事件 | 风险 | 来源 | 校验 |")
        lines.append("|---|---|---|---|---|---|")
        for event in events[:10]:
            lines.append(
                f"| {event.get('effective_date') or event.get('published_at') or '-'} "
                f"| {event.get('market', '-')} "
                f"| {event.get('title', event.get('event', '-'))} "
                f"| {event.get('impact_level', '-')} "
                f"| {event.get('source', '-')} "
                f"| {'官方原文' if event.get('verified') else '候选待核'} |"
            )
    else:
        lines.append("暂无政策事件。")
    lines.append("")

    lines.append("## 三、平台榜单")
    lines.append("")
    ranking_rows = rankings.get("rows") or []
    if ranking_rows:
        lines.append("| 平台 | 品类 | 市场 | 排名 | 商品 |")
        lines.append("|---|---|---|---|---|")
        for row in ranking_rows[:10]:
            lines.append(
                f"| {row.get('platform')} "
                f"| {row.get('category_name')} "
                f"| {row.get('market_name')} "
                f"| {row.get('rank')} "
                f"| {row.get('product')} |"
            )
    else:
        lines.append("暂无平台榜单数据。")
    lines.append("")

    lines.append("## 四、海关出口信号")
    lines.append("")
    customs_rows = customs.get("rows") or []
    if customs_rows:
        lines.append("| 品类 | HS4 | 中国出口额 | 来源 |")
        lines.append("|---|---|---|---|")
        for row in customs_rows[:10]:
            lines.append(
                f"| {row.get('category_name')} "
                f"| {row.get('hs_code')} "
                f"| {row.get('value', 0):,.0f} USD "
                f"| {row.get('source')} |"
            )
        source_url = customs.get("source_url")
        if source_url:
            lines.append("")
            lines.append(f"数据来源：{source_url}")
    else:
        lines.append("暂无海关出口数据。")
    lines.append("")

    lines.append("## 五、货源/供应商")
    lines.append("")
    supplier_rows = suppliers.get("rows") or []
    if supplier_rows:
        lines.append("| 供应商 | 品类 | 地区 | 经营年限 | 复购率 | 响应率 | 来源 |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in supplier_rows[:10]:
            lines.append(
                f"| {row.get('supplier_name')} "
                f"| {row.get('category_name')} "
                f"| {row.get('location')} "
                f"| {row.get('service_years', 0):.1f} 年 "
                f"| {row.get('repeat_rate', 0):.0%} "
                f"| {row.get('response_rate', 0):.0%} "
                f"| {row.get('source')} |"
            )
    else:
        lines.append("暂无货源/供应商数据。")
    lines.append("")

    lines.append("## 六、异常信号")
    lines.append("")
    anomaly_rows = anomalies.get("rows") or []
    if anomaly_rows:
        lines.append("| 品类 | 市场 | 指标 | 日期 | 数值 | 得分 |")
        lines.append("|---|---|---|---|---|---|")
        for row in anomaly_rows[:10]:
            lines.append(
                f"| {row.get('category')} "
                f"| {row.get('market')} "
                f"| {row.get('column')} "
                f"| {row.get('date')} "
                f"| {row.get('value')} "
                f"| {row.get('score')} |"
            )
    else:
        lines.append("暂无异常信号。")
    lines.append("")

    lines.append("## 七、数据可信度说明")
    lines.append("")
    lines.append(
        "本日报区分“数值/统计”与“AI 解释”。回退数据、缺少来源或未核实事实均明确标注，"
        "不作为申报或投资依据。"
    )
    return "\n".join(lines) + "\n"


def _load_policy() -> dict[str, Any]:
    if not POLICY_LATEST_JSON.exists():
        return {}
    try:
        return json.loads(POLICY_LATEST_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_market_daily(
    markdown: str,
    report_date: str | date,
) -> Path:
    MARKET_DAILY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = MARKET_DAILY_OUTPUT_DIR / f"{report_date}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def maybe_push_market_daily(
    markdown: str,
    *,
    webhook_url: str | None = None,
) -> bool:
    """有 webhook 配置时推送飞书风格消息，默认只返回 False。"""
    url = (webhook_url or MARKET_DAILY_PUSH_URL or "").strip()
    if not url:
        return False
    import requests

    payload = {"msg_type": "text", "content": {"text": markdown[:4000]}}
    response = requests.post(url, json=payload, timeout=10)
    return response.ok


def market_daily_status(report_date: str | date) -> dict[str, Any]:
    path = MARKET_DAILY_OUTPUT_DIR / f"{report_date}.md"
    return {
        "enabled": path.exists(),
        "path": str(path) if path.exists() else None,
        "updated_at": (
            datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
            if path.exists()
            else None
        ),
    }


__all__ = [
    "build_market_daily_markdown",
    "market_daily_status",
    "maybe_push_market_daily",
    "write_market_daily",
]
