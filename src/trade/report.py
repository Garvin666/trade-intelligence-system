"""贸易决策演示报告：汇总政策风险、到岸成本、市场准入与数据信用。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from src.analysis.evidence import (
    build_evidence_section,
    check_expiry,
    normalize_provenance,
    provenance_record,
)
from src.config import CATEGORIES, CATEGORY_PARAMS, MARKETS, PROJECT_ROOT
from src.trade.cost import DEFAULT_FX_RATE
from src.trade.decision import build_trade_decision
from src.trade.policy import policy_watchlist

OUTPUT_DIR = PROJECT_ROOT / "output" / "trade"


def _default_inputs() -> dict[tuple[str, str], dict]:
    defaults: dict[tuple[str, str], dict] = {}
    for category in CATEGORIES:
        for market in MARKETS:
            price = float(CATEGORY_PARAMS.get(category, {}).get("price", 28.0))
            defaults[(category, market)] = {
                "unit_price_usd": price,
                "procurement_cost_cny": round(price * DEFAULT_FX_RATE * 0.35, 2),
            }
    return defaults


def _latest_inputs(clean_df: pd.DataFrame | None) -> dict[tuple[str, str], dict]:
    if clean_df is None or clean_df.empty:
        return _default_inputs()
    latest = clean_df.sort_values("date").groupby(["category", "market"], as_index=False).last()
    result: dict[tuple[str, str], dict] = {}
    for row in latest.itertuples(index=False):
        price = float(row.price_median)
        result[(row.category, row.market)] = {
            "unit_price_usd": round(price, 2),
            "procurement_cost_cny": round(price * DEFAULT_FX_RATE * 0.35, 2),
        }
    return result


def build_trade_demo_report(clean_df: pd.DataFrame | None = None) -> dict:
    """生成并落盘贸易决策演示报告。"""
    inputs = _latest_inputs(clean_df)
    rows: list[dict] = []

    for (category, market), values in inputs.items():
        rows.append(
            build_trade_decision(
                category=category,
                market=market,
                unit_price_usd=values["unit_price_usd"],
                procurement_cost_cny=values["procurement_cost_cny"],
            )
        )

    summary = {
        "combos": len(rows),
        "high_risk": sum(1 for r in rows if r["risk_level"] == "high"),
        "medium_risk": sum(1 for r in rows if r["risk_level"] == "medium"),
        "avg_margin_pct": round(sum(r["margin_pct"] for r in rows) / len(rows), 2),
        "ip_high": sum(1 for r in rows if r["ip_risk_level"] == "high"),
        "ip_medium": sum(1 for r in rows if r["ip_risk_level"] == "medium"),
        "ip_low": sum(1 for r in rows if r["ip_risk_level"] == "low"),
        "freight_high": sum(1 for r in rows if r["freight_risk"] == "high"),
        "freight_medium": sum(1 for r in rows if r["freight_risk"] == "medium"),
        "freight_low": sum(1 for r in rows if r["freight_risk"] == "low"),
        "sentiment_avg": round(sum(r["sentiment_avg_score"] for r in rows) / len(rows), 3),
        "sentiment_positive": sum(1 for r in rows if r["sentiment_overall"] == "positive"),
        "sentiment_neutral": sum(1 for r in rows if r["sentiment_overall"] == "neutral"),
        "sentiment_negative": sum(1 for r in rows if r["sentiment_overall"] == "negative"),
        "green_high": sum(1 for r in rows if r["green_risk"] == "high"),
        "green_medium": sum(1 for r in rows if r["green_risk"] == "medium"),
        "green_avg_cost": round(sum(r["green_carbon_cost_usd"] for r in rows) / len(rows), 2),
        "credit_avg": round(sum(r["financing_ready_score"] for r in rows) / len(rows), 1),
        "credit_supply_chain_finance": sum(1 for r in rows if r["financing_level"] == "可对接供应链金融"),
        "credit_loan": sum(1 for r in rows if r["financing_level"] == "可对接信用贷"),
        "credit_trial": sum(1 for r in rows if r["financing_level"] == "小额试单"),
        "credit_not_ready": sum(1 for r in rows if r["financing_level"] == "暂不建议"),
        "conflict_high": sum(1 for r in rows if r["conflict_level"] == "high"),
        "conflict_medium": sum(1 for r in rows if r["conflict_level"] == "medium"),
        "conflict_low": sum(1 for r in rows if r["conflict_level"] == "low"),
        "conflict_risk_first": sum(1 for r in rows if "降低备货规模" in r["conflict_decision"]),
    }
    payload = {
        "generated_at": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
        "policy_events": policy_watchlist(),
        "summary": summary,
        "rows": rows,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "trade_demo_metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    flat_rows: list[dict] = []
    for row in rows:
        for logistics_row in row["logistics"]:
            flat_rows.append(
                {
                    **logistics_row,
                    "risk_level": row["risk_level"],
                    "ip_risk_level": row["ip_risk_level"],
                    "freight_risk": row["freight_risk"],
                    "freight_trend_pct": row["freight_trend_pct"],
                    "freight_index_now": row["freight_index_now"],
                    "freight_index_forecast": row["freight_index_forecast"],
                    "freight_delivery_days": row["freight_delivery_days"],
                    "sentiment_avg_score": row["sentiment_avg_score"],
                    "sentiment_overall": row["sentiment_overall"],
                    "green_exposure": row["green_exposure"],
                    "green_carbon_cost_usd": row["green_carbon_cost_usd"],
                    "financing_ready_score": row["financing_ready_score"],
                    "financing_level": row["financing_level"],
                    "conflict_level": row["conflict_level"],
                    "conflict_decision": row["conflict_decision"],
                }
            )
    pd.DataFrame(flat_rows).to_csv(OUTPUT_DIR / "trade_landed_cost.csv", index=False, encoding="utf-8-sig")
    (OUTPUT_DIR / "trade_demo_report.md").write_text(_report_markdown(payload), encoding="utf-8")
    return payload


def _report_markdown(payload: dict) -> str:
    lines = [
        "# 跨境贸易决策演示报告",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 组合数：{payload['summary']['combos']}；高风险：{payload['summary']['high_risk']}；中风险：{payload['summary']['medium_risk']}",
        f"- 平均利润率：{payload['summary']['avg_margin_pct']}%",
        f"- IP 风险：高风险 {payload['summary']['ip_high']} / 中风险 {payload['summary']['ip_medium']} / 低风险 {payload['summary']['ip_low']}",
        f"- 物流风险：高风险 {payload['summary']['freight_high']} / 中风险 {payload['summary']['freight_medium']} / 低风险 {payload['summary']['freight_low']}",
        f"- 舆情：平均情绪分 {payload['summary']['sentiment_avg']}；正面 {payload['summary']['sentiment_positive']} / 中性 {payload['summary']['sentiment_neutral']} / 负面 {payload['summary']['sentiment_negative']}",
        f"- 绿色贸易：CBAM 高风险 {payload['summary']['green_high']} / 中风险 {payload['summary']['green_medium']}；平均碳成本 ${payload['summary']['green_avg_cost']}",
        f"- 数据信用：平均融资就绪分 {payload['summary']['credit_avg']}；供应链金融 {payload['summary']['credit_supply_chain_finance']} / 信用贷 {payload['summary']['credit_loan']} / 小额试单 {payload['summary']['credit_trial']} / 暂不建议 {payload['summary']['credit_not_ready']}",
        f"- 冲突裁决：高风险 {payload['summary']['conflict_high']} / 中风险 {payload['summary']['conflict_medium']} / 低风险 {payload['summary']['conflict_low']}；风险优先建议 {payload['summary']['conflict_risk_first']}",
        "",
        "## 政策监控（过期提醒：生效日 + 有效期）",
        "",
    ]
    for event in payload["policy_events"]:
        record = normalize_provenance(
            {
                "key": event.get("code") or event.get("title"),
                "title": event.get("title"),
                "source": event.get("source"),
                "effective_date": event.get("effective_date"),
                "fetched_at": event.get("published_at") or event.get("generated_at") or event.get("updated_at"),
            }
        )
        expiry = check_expiry(record)
        status_label = {
            "expired": "⚠️ 已过期",
            "expiring_soon": "⏳ 即将过期",
            "no_expiry": "长期有效/待确认",
            "valid": "有效",
        }[expiry["status"]]
        lines.append(
            f"- **{event['title']}**（{event['effective_date']} 生效，{event['market']}）："
            f"{event['description']} ｜ 来源：{record.get('source') or '-'} "
            f"｜ 有效期至：{record.get('expires_at') or '-'} ｜ {status_label}"
        )
    lines.append("")
    lines.append("## 组合明细")
    lines.append("")
    lines.append("| 品类 | 市场 | 风险 | 有效税率 | 单件关税 | 利润率 | 最佳物流 | 准入评分 | IP 风险 | 融资就绪 | 裁决 |")
    lines.append("|------|------|------|---------|---------|--------|---------|---------|---------|---------|------|")
    for row in payload["rows"]:
        lines.append(
            f"| {row['category_name']} | {row['market_name']} | {row['risk_level']} | "
            f"{row['effective_tariff_rate']:.0%} | ${row['duty_usd_per_unit']:.2f} | "
            f"{row['margin_pct']:.2f}% | {row['best_logistics']} | {row['feasibility_score']} | "
            f"{row['ip_risk_level']} | {row['financing_level']} | {row['conflict_level']} |"
        )
    lines.append("")
    lines.append("> 本报告为离线演示口径：关税、汇率、支付费率、认证成本与物流价格均为可替换的演示参数。")
    return "\n".join(lines) + "\n"


EXPORT_DIR = PROJECT_ROOT / "output" / "export"

_SENSITIVE_KEYS = {"api_key", "search_api_key"}


def _sanitize_report_payload(payload: dict) -> dict:
    """Remove user credentials before a report is written to disk."""
    import copy

    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k not in _SENSITIVE_KEYS}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(copy.deepcopy(payload))


def _fmt(value, default: str = "-") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return "、".join(_fmt(item) for item in value)
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _selection_markdown(payload: dict) -> str:
    data = _sanitize_report_payload(payload)
    filters = data.get("filters") or {}
    recommendation = data.get("recommendation") or {}
    if isinstance(recommendation, list):
        recommendation = recommendation[0] if recommendation else {}
    decision = data.get("trade_decision") or {}
    evidence = data.get("evidence") or []
    policy_events = data.get("policy_events") or []
    conclusion = data.get("conclusion") or ""
    data_status = data.get("data_status") or {}
    generated_at = data.get("generated_at") or pd.Timestamp.utcnow().isoformat(timespec="seconds")

    lines = [
        "# 跨境电商智能选品决策报告",
        "",
        f"- 生成时间：{generated_at}",
    ]
    if data_status.get("data_as_of"):
        lines.append(f"- 数据更新至：{data_status['data_as_of']}")
    lines.append("")

    lines.append("## 一、筛选条件")
    lines.append("")
    lines.append("| 项目 | 取值 |")
    lines.append("|------|------|")
    for key, label in [
        ("category", "品类"),
        ("market", "市场"),
        ("model", "模型"),
        ("date_from", "起始日期"),
        ("date_to", "截止日期"),
        ("top", "Top N"),
    ]:
        lines.append(f"| {label} | {_fmt(filters.get(key))} |")
    lines.append("")

    lines.append("## 二、推荐结果")
    lines.append("")
    lines.append("> 以下数值来自模型与统计计算；推荐理由为规则解释，非 AI 生成的数值。")
    lines.append("")
    if recommendation:
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        for key, label in [
            ("category", "品类"),
            ("market", "市场"),
            ("rank", "排名"),
            ("score", "综合评分"),
            ("six_dimension_score", "六维评分"),
            ("verdict", "Go/No-Go 判定"),
            ("decision_reason", "判定理由"),
            ("forecast_growth", "预测增长%"),
            ("search_trend", "搜索趋势%"),
            ("competition", "竞争度"),
            ("review_growth", "评价增长%"),
            ("reasons", "推荐理由"),
        ]:
            if recommendation.get(key) is not None:
                lines.append(f"| {label} | {_fmt(recommendation.get(key))} |")
    else:
        lines.append("暂无推荐数据。")
    lines.append("")

    lines.append("## 三、贸易决策")
    lines.append("")
    lines.append("> 以下数值来自成本、政策与合规模型；建议由规则或 AI 生成，二者不会混同。")
    lines.append("")
    if decision:
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        for key, label in [
            ("category_name", "品类"),
            ("market_name", "市场"),
            ("hs_code", "默认 HS6 编码"),
            ("hs_description", "HS 描述"),
            ("risk_level", "风险等级"),
            ("risk_message", "风险说明"),
            ("margin_pct", "到岸利润率%"),
            ("effective_tariff_rate", "有效税率"),
            ("duty_usd_per_unit", "单件关税"),
            ("best_logistics", "最佳物流"),
            ("feasibility_score", "准入评分"),
            ("ip_risk_level", "IP 风险"),
            ("financing_level", "融资档位"),
            ("conflict_level", "冲突等级"),
            ("conflict_decision", "冲突决策"),
        ]:
            value = decision.get(key)
            if value is not None:
                if key == "effective_tariff_rate" and isinstance(value, float):
                    value = f"{value:.0%}"
                lines.append(f"| {label} | {_fmt(value)} |")
    else:
        lines.append("暂无贸易测算数据。")
    lines.append("")

    lines.append("## 四、证据清单")
    lines.append("")
    if evidence:
        for index, item in enumerate(evidence, start=1):
            record = normalize_provenance(item)
            title = record.get("title") or record.get("snippet") or f"来源 {index}"
            expiry = check_expiry(record)
            lines.append(f"{index}. **{_fmt(title)}**")
            if record.get("snippet"):
                lines.append(f"   - 摘要：{_fmt(record.get('snippet'))}")
            if record.get("source") or record.get("url"):
                lines.append(f"   - 来源：{_fmt(record.get('source') or record.get('url'))}")
            if record.get("fetched_at"):
                lines.append(f"   - 抓取时间：{_fmt(record.get('fetched_at'))}")
            if record.get("effective_date"):
                lines.append(f"   - 生效日：{_fmt(record.get('effective_date'))}")
            if record.get("expires_at"):
                lines.append(f"   - 有效期至：{_fmt(record.get('expires_at'))}")
            if record.get("review_status"):
                lines.append(f"   - 人工复核：{_fmt(record.get('review_status'))}")
            if expiry["status"] in ("expired", "expiring_soon"):
                lines.append(f"   - ⚠️ {expiry['message']}")
    else:
        lines.append("暂无证据。")
    lines.append("")

    # 政策/认证类结论过期提醒（A-1：生效日 + 有效期，防引用已失效结论）
    lines.append("### 政策事件时效（过期提醒）")
    lines.append("")
    if policy_events:
        lines.append("| 政策 | 来源 | 生效日 | 有效期至 | 状态 |")
        lines.append("|---|---|---|---|---|")
        for event in policy_events:
            record = normalize_provenance(
                {
                    "key": event.get("code") or event.get("title"),
                    "title": event.get("title"),
                    "source": event.get("source"),
                    "effective_date": event.get("effective_date"),
                    "fetched_at": event.get("published_at") or event.get("generated_at") or event.get("updated_at"),
                    "status": "已检索",
                }
            )
            expiry = check_expiry(record)
            status_label = {
                "expired": "⚠️ 已过期",
                "expiring_soon": "⏳ 即将过期",
                "no_expiry": "长期有效/待确认",
                "valid": "有效",
            }[expiry["status"]]
            lines.append(
                f"| {_fmt(record.get('title') or '-')} "
                f"| {_fmt(record.get('source') or '-')} "
                f"| {_fmt(record.get('effective_date') or '-')} "
                f"| {_fmt(record.get('expires_at') or '-')} "
                f"| {status_label} |"
            )
    else:
        lines.append("暂无政策事件。")
    lines.append("")

    evidence_items = [
        provenance_record(
            key=item.get("key") or f"evidence_{index}",
            title=item.get("title") or item.get("snippet") or f"来源 {index}",
            source=item.get("source") or item.get("link") or item.get("provider"),
            url=item.get("link"),
            fetched_at=item.get("fetched_at") or item.get("generated_at") or item.get("date"),
            effective_date=item.get("effective_date"),
            expires_at=item.get("expires_at"),
            validity_days=item.get("validity_days"),
            hs_version=item.get("hs_version"),
            formula=item.get("formula"),
            model_version=item.get("model_version"),
            confidence_interval=item.get("confidence_interval"),
            review_status=item.get("review_status") or "未复核",
            status="已检索" if (item.get("link") or item.get("source")) else "待核实",
        )
        for index, item in enumerate(evidence, start=1)
    ]
    lines.append(build_evidence_section(evidence_items))

    lines.append("## 六、结论")
    lines.append("")
    lines.append(str(conclusion) if conclusion else "暂无结论。")
    lines.append("")
    lines.append("> 本报告由跨境电商智能选品决策系统生成，仅供决策参考。")
    return "\n".join(lines) + "\n"


def _pick_fonts(registered: list[str]) -> tuple[str, str, str]:
    """从已注册字体中选取 (title, body, bold) 三元组，不足时回退 Helvetica。"""
    if len(registered) >= 3:
        return registered[0], registered[1], registered[2]
    if len(registered) == 2:
        return registered[0], registered[1], registered[1]
    return "Helvetica", "Helvetica", "Helvetica-Bold"


def _register_pdf_fonts() -> tuple[str, str, str]:
    """注册中文字体：优先系统 TTF，缺失时回退 reportlab 内置 CID 字体。

    跨平台探测常见字体目录（Windows / Linux / macOS），
    均不可用时回退 Helvetica，避免 Linux 打包 PDF 中文缺失。
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    font_dirs = [
        Path(r"C:\Windows\Fonts"),
        Path("/usr/share/fonts"),
        Path("/usr/share/fonts/opentype/noto"),
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
    ]
    candidates = [
        ("SimHei", "simhei.ttf"),
        ("Deng", "Deng.ttf"),
        ("DengB", "Dengb.ttf"),
        ("NotoSansCJK", "NotoSansCJKsc-Regular.otf"),
    ]
    registered: list[str] = []
    for name, file_name in candidates:
        font_path = next(
            (font_dir / file_name for font_dir in font_dirs if (font_dir / file_name).exists()),
            None,
        )
        if font_path is None:
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, str(font_path)))
            registered.append(name)
        except Exception:  # noqa: BLE001 - 字体注册失败时回退内置字体
            pass
    if len(registered) >= 2:
        return _pick_fonts(registered)
    # 外部字体不足时回退 reportlab 内置 CJK 字体，保证中文可渲染。
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        registered.append("STSong-Light")
    except Exception:  # noqa: BLE001 - 内置字体注册失败时最终回退 Helvetica
        pass
    return _pick_fonts(registered)


def _markdown_pdf(
    markdown: str,
    pdf_path: Path,
    title: str = "跨境电商智能选品决策报告",
) -> None:
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    title_font, body_font, bold_font = _register_pdf_fonts()
    styles = {
        "title": ParagraphStyle(
            "title", fontName=title_font, fontSize=18, leading=24,
            spaceAfter=6, wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "h2", fontName=bold_font, fontSize=13, leading=18,
            spaceBefore=10, spaceAfter=4, wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "body", fontName=body_font, fontSize=9.5, leading=14,
            spaceAfter=3, wordWrap="CJK",
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName=body_font, fontSize=9.5, leading=13.5,
            leftIndent=10, spaceAfter=2, wordWrap="CJK",
        ),
        "th": ParagraphStyle(
            "th", fontName=bold_font, fontSize=8.5, leading=11,
            textColor=colors.white, wordWrap="CJK",
        ),
        "td": ParagraphStyle(
            "td", fontName=body_font, fontSize=8.5, leading=11,
            wordWrap="CJK",
        ),
        "note": ParagraphStyle(
            "note", fontName=body_font, fontSize=8.5, leading=12,
            textColor=colors.HexColor("#64748B"), wordWrap="CJK",
        ),
    }

    def table_element(rows):
        table = Table(rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E4E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ]
            )
        )
        return table

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(body_font, 8)
        canvas.setFillColor(colors.HexColor("#94A3B8"))
        canvas.drawCentredString(A4[0] / 2, 10 * mm, str(doc.page))
        canvas.restoreState()

    story = []
    table_rows: list[list[Paragraph]] = []
    in_table = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("|"):
            cells = [escape(cell.strip()) for cell in line.strip("|").split("|")]
            if not in_table:
                table_rows = [[Paragraph(cell, styles["th"]) for cell in cells]]
                in_table = True
            else:
                table_rows.append([Paragraph(cell, styles["td"]) for cell in cells])
            continue
        if in_table:
            story.append(table_element(table_rows))
            table_rows = []
            in_table = False
        if line.startswith("### "):
            story.append(Paragraph(escape(line[4:]), styles["h2"]))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), styles["h2"]))
        elif line.startswith("# "):
            story.append(Paragraph(escape(line[2:]), styles["title"]))
        elif line.startswith("- "):
            story.append(Paragraph("• " + escape(line[2:]), styles["bullet"]))
        elif line.startswith("> "):
            story.append(Paragraph(escape(line[2:]), styles["note"]))
        else:
            story.append(Paragraph(escape(line), styles["body"]))
    if in_table:
        story.append(table_element(table_rows))

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def _selection_pdf(markdown: str, pdf_path: Path) -> None:
    _markdown_pdf(markdown, pdf_path)


def build_selection_report(payload: dict, output_dir: Path | None = None) -> dict:
    """Build a Markdown + PDF selection report and persist it under output/export."""
    data = _sanitize_report_payload(payload)
    generated_at = data.get("generated_at") or pd.Timestamp.utcnow().isoformat(timespec="seconds")
    out_dir = output_dir or EXPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown = _selection_markdown({**data, "generated_at": generated_at})
    # 文件名带生成时间戳，避免多次导出互相覆盖；下载端文件名由调用方固定。
    stamp = re.sub(r"[-:T]", "", generated_at)[:15]
    markdown_path = out_dir / f"dashboard_selection_report_{stamp}.md"
    pdf_path = out_dir / f"dashboard_selection_report_{stamp}.pdf"
    markdown_path.write_text(markdown, encoding="utf-8")
    _selection_pdf(markdown, pdf_path)
    return {
        "markdown": markdown,
        "markdown_path": markdown_path,
        "pdf_path": pdf_path,
        "generated_at": generated_at,
    }


def build_launch_report(payload: dict, output_dir: Path | None = None) -> dict:
    """Build a Markdown + PDF launch report and persist it under output/export."""
    data = _sanitize_report_payload(payload)
    markdown = str(data.get("report") or data.get("markdown") or "").strip()
    if not markdown:
        raise ValueError("report 不能为空")
    generated_at = data.get("generated_at") or pd.Timestamp.utcnow().isoformat(timespec="seconds")
    out_dir = output_dir or EXPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[-:T]", "", generated_at)[:15]
    markdown_path = out_dir / f"launch_report_{stamp}.md"
    pdf_path = out_dir / f"launch_report_{stamp}.pdf"
    markdown_path.write_text(markdown, encoding="utf-8")
    _markdown_pdf(markdown, pdf_path, title="选品立项报告")
    return {
        "markdown": markdown,
        "markdown_path": markdown_path,
        "pdf_path": pdf_path,
        "generated_at": generated_at,
    }
