"""生成《数据分析报告》PDF（reportlab 浅色编辑部风格）。

用法：
    python scripts/build_data_analysis_pdf.py

前置：先运行 scripts/run_data_analysis.py 生成统计 JSON 与图表。
产物：
    output/pdf/数据分析报告.pdf
    发布与材料/提交材料包_整合优化版_20260805/05_原始材料/数据分析报告.pdf
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.report import FIGURES_DIR  # noqa: E402

FONT_DIR = Path(r"C:\Windows\Fonts")
STATS_JSON = PROJECT_ROOT / "output" / "analysis" / "summary_stats.json"
OUT_DIR = PROJECT_ROOT / "output" / "pdf"
OUT_PDF = OUT_DIR / "数据分析报告.pdf"
SUBMISSION_PDF_DIR = (
    PROJECT_ROOT / "发布与材料" / "提交材料包_整合优化版_20260805" / "05_原始材料"
)

pdfmetrics.registerFont(TTFont("SimHei", str(FONT_DIR / "simhei.ttf")))
pdfmetrics.registerFont(TTFont("Deng", str(FONT_DIR / "Deng.ttf")))
pdfmetrics.registerFont(TTFont("DengB", str(FONT_DIR / "Dengb.ttf")))

INK = colors.HexColor("#1F2937")
SLATE = colors.HexColor("#5B6470")
TEAL = colors.HexColor("#0F766E")
TEAL_DARK = colors.HexColor("#115E59")
MINT = colors.HexColor("#ECFDF5")
GOLD = colors.HexColor("#B45309")
LINE = colors.HexColor("#DCE8E4")
WHITE = colors.white

PAGE_W, PAGE_H = A4
MARGIN_L = 16 * mm
MARGIN_R = 16 * mm
MARGIN_T = 18 * mm
MARGIN_B = 18 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle(
            "kicker", parent=base["Normal"], fontName="DengB", fontSize=8.6, leading=12,
            textColor=TEAL, spaceAfter=4, wordWrap="CJK",
        ),
        "title": ParagraphStyle(
            "title", parent=base["Normal"], fontName="SimHei", fontSize=22, leading=29,
            textColor=INK, spaceAfter=4, wordWrap="CJK",
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontName="Deng", fontSize=11, leading=16,
            textColor=SLATE, wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Normal"], fontName="SimHei", fontSize=14, leading=20,
            textColor=INK, spaceBefore=10, spaceAfter=6, wordWrap="CJK",
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Normal"], fontName="DengB", fontSize=10.8, leading=15,
            textColor=TEAL_DARK, spaceBefore=6, spaceAfter=4, wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Deng", fontSize=9.6, leading=15,
            textColor=INK, spaceAfter=4, wordWrap="CJK",
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Deng", fontSize=9.6, leading=14.6,
            textColor=INK, leftIndent=8, spaceAfter=3, wordWrap="CJK",
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"], fontName="Deng", fontSize=8.2, leading=11,
            textColor=SLATE, alignment=TA_CENTER, spaceBefore=2, spaceAfter=8, wordWrap="CJK",
        ),
        "th": ParagraphStyle(
            "th", parent=base["Normal"], fontName="DengB", fontSize=8, leading=11,
            textColor=WHITE, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "td": ParagraphStyle(
            "td", parent=base["Normal"], fontName="Deng", fontSize=8, leading=11,
            textColor=INK, wordWrap="CJK",
        ),
        "note": ParagraphStyle(
            "note", parent=base["Normal"], fontName="Deng", fontSize=8.2, leading=12,
            textColor=SLATE, spaceBefore=2, wordWrap="CJK",
        ),
    }


def _header_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.7)
    canvas.line(MARGIN_L, PAGE_H - 13 * mm, PAGE_W - MARGIN_R, PAGE_H - 13 * mm)
    canvas.setFont("Deng", 8.5)
    canvas.setFillColor(SLATE)
    canvas.drawString(MARGIN_L, PAGE_H - 11 * mm, "跨境电商智能选品决策系统")
    canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 11 * mm, "数据分析报告")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.7)
    canvas.line(MARGIN_L, 13 * mm, PAGE_W - MARGIN_R, 13 * mm)
    canvas.setFont("Deng", 8.5)
    canvas.setFillColor(SLATE)
    canvas.drawString(MARGIN_L, 10 * mm, "中国国际大学生创新大赛 · 高教赛道 · 创意组")
    canvas.drawRightString(PAGE_W - MARGIN_R, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def _table(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    style = _styles()
    data = [[Paragraph(h, style["th"]) for h in headers]]
    data += [[Paragraph(c, style["td"]) for c in row] for row in rows]
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, MINT]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _figure(stats: dict[str, Any], styles: dict, name: str, caption: str):
    path = FIGURES_DIR / name
    if not path.exists():
        return []
    img = Image(str(path))
    ratio = img.imageWidth / max(img.imageHeight, 1)
    img.drawWidth = CONTENT_W * 0.92
    img.drawHeight = img.drawWidth / ratio
    if img.drawHeight > 150 * mm:
        img.drawHeight = 150 * mm
        img.drawWidth = img.drawHeight * ratio
    return [
        Spacer(1, 4),
        img,
        Paragraph(caption, styles["caption"]),
    ]


def build() -> None:
    if not STATS_JSON.exists():
        raise SystemExit("缺少 output/analysis/summary_stats.json，请先运行 scripts/run_data_analysis.py")
    stats = json.loads(STATS_JSON.read_text(encoding="utf-8"))
    styles = _styles()
    overview = stats["overview"]
    trade = stats["trade"]
    industry = stats["industry"]
    rec = stats["recommendation"]
    seasonality = stats["seasonality"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="数据分析报告",
        author="跨境电商智能选品决策系统",
    )
    flow: list[Any] = []

    flow.append(Paragraph("数据驱动 · 跨境贸易决策智能", styles["kicker"]))
    flow.append(Paragraph("数据分析报告", styles["title"]))
    flow.append(
        Paragraph(
            "基于多源数据融合的跨境电商智能选品决策系统 · "
            f"生成日期 {stats['generated_at']}",
            styles["subtitle"],
        )
    )
    flow.append(Spacer(1, 8))

    combo_count = overview["categories"] * overview["markets"]
    findings = [
        f"数据基础：{overview['history_rows']} 条周粒度清洗数据、{overview['weeks']} 周、"
        f"{overview['categories']} 品类 × {overview['markets']} 市场 {combo_count} 组合，"
        f"预测产物 {overview['forecast_rows']} 行。",
        f"模型精度：LightGBM 进阶 MAPE {overview['advanced_mape_avg']:.2f}%，较 Prophet 基线 "
        f"{overview['baseline_mape_avg']:.2f}% 相对下降 {overview['mape_improvement_pct']:.1f}%。",
        f"推荐 Top1：{rec['top1'].get('category_name', '-')} × {rec['top1'].get('market_name', '-')}，"
        f"综合评分 {rec['top1'].get('score', '-')}。",
        f"季节性：销量峰值集中在第 {seasonality['peak_week']} 周（约 {seasonality['peak_month']} 月），"
        f"低点约在 {seasonality['trough_month']} 月。",
        f"贸易决策：{combo_count} 组合中高风险 {trade['high_risk']} 个，"
        f"平均利润冲击 {trade['avg_margin_pct']:.1f}%，"
        f"平均融资就绪评分 {trade['credit_avg']:.1f}。",
    ]
    flow.append(Paragraph("一、结论摘要", styles["h2"]))
    for item in findings:
        flow.append(Paragraph(f"1. {item}", styles["bullet"]))
    flow.append(
        Paragraph(
            "行业数据以“已检索 / 待核实”双口径登记，未核实条目不得作为答辩引用依据。",
            styles["note"],
        )
    )

    flow.append(Paragraph("二、行业与市场数据分析", styles["h2"]))
    flow.append(
        Paragraph(
            "2025 年中国跨境电商进出口规模达到 2.75 万亿元，较 2020 年增长 69.7%"
            "（国新办 2026-01-28 发布会引用海关初步统计）。项目既有材料写作“同比增长 69.7%”，"
            "本报告按官方口径修正为“较 2020 年增长”。",
            styles["body"],
        )
    )
    flow += _figure(stats, styles, "industry_market.png", "图 1：中国跨境电商进出口规模与增速")
    flow += _figure(stats, styles, "policy_timeline.png", "图 2：国际贸易政策事件时间线（2025-2026）")

    flow.append(Paragraph("三、项目数据总览", styles["h2"]))
    overview_rows = [
        ["历史数据条数", str(overview["history_rows"]), "时间粒度 / 周期", f"周粒度，{overview['start_date']} 至 {overview['end_date']}"],
        ["覆盖范围", f"{overview['categories']} 品类 × {overview['markets']} 市场", "预测范围", f"{overview['forecast_start']} 至 {overview['forecast_end']}"],
        ["预测条数", str(overview["forecast_rows"]), "推荐结果", str(overview["recommendation_rows"])],
        ["基线模型 MAPE", f"{overview['baseline_mape_avg']:.2f}%", "进阶模型 MAPE", f"{overview['advanced_mape_avg']:.2f}%（相对提升 {overview['mape_improvement_pct']:.1f}%）"],
    ]
    flow.append(_table(["指标", "数值", "指标", "数值"], overview_rows, [CONTENT_W * 0.22] * 4))

    flow.append(Paragraph("四、探索性数据分析", styles["h2"]))
    flow += _figure(stats, styles, "category_market_sales.png", "图 3：品类 × 市场平均销量指数")
    flow += _figure(stats, styles, "search_export.png", "图 4：品类出口金额与搜索热度对比")
    flow += _figure(stats, styles, "trend_seasonality.png", "图 5：典型组合趋势与多组合季节性对比")
    flow += _figure(stats, styles, "weekly_seasonality.png", "图 6：周粒度季节性模式")
    flow.append(Paragraph("五、模型评估分析", styles["h2"]))
    flow += _figure(stats, styles, "model_mape.png", f"图 8：双模型 MAPE 对比（{combo_count} 组合）")
    flow += _figure(stats, styles, "forecast_interval.png", "图 9：未来 90 天预测与置信区间示例")

    flow.append(Paragraph("六、推荐结果分析", styles["h2"]))
    rec_rows = [
        [
            str(r["rank"]),
            r["category_name"],
            r["market_name"],
            f"{float(r['score']):.1f}",
            f"{float(r['forecast_growth']):+.1f}%",
            f"{float(r['search_trend']):+.1f}%",
            f"{float(r['competition']):.1f}",
            str(r["reasons"]),
        ]
        for r in rec["top10"]
    ]
    flow.append(
        _table(
            ["排名", "品类", "市场", "评分", "预测增长", "搜索趋势", "竞争度", "推荐理由"],
            rec_rows,
            [CONTENT_W * 0.07] * 7 + [CONTENT_W * 0.51],
        )
    )
    flow += _figure(stats, styles, "recommend_composition.png", "图 10：Top 10 推荐评分构成（示意）")

    flow.append(Paragraph("七、贸易决策情景分析", styles["h2"]))
    flow += _figure(stats, styles, "landed_cost.png", "图 11：物流三方案平均到岸成本对比")
    flow += _figure(stats, styles, "policy_financing.png", "图 12：政策风险 × 融资就绪 × 利润率")
    flow.append(
        Paragraph(
            f"{combo_count} 组合中高风险 {trade['high_risk']} 个、中风险 {trade['medium_risk']} 个；"
            f"平均利润冲击 {trade['avg_margin_pct']:.1f}%，平均融资就绪评分 {trade['credit_avg']:.1f}，"
            f"冲突高风险组合 {trade['conflict_high']} 个。",
            styles["body"],
        )
    )

    flow.append(Paragraph("八、行业数据来源表", styles["h2"]))
    source_rows = [
        [
            f["title"],
            f["value"],
            f["detail"],
            f["source"],
            f["status"],
        ]
        for f in industry["facts"]
    ]
    flow.append(
        _table(
            ["条目", "数值 / 内容", "口径说明", "来源", "状态"],
            source_rows,
            [CONTENT_W * 0.17, CONTENT_W * 0.13, CONTENT_W * 0.38, CONTENT_W * 0.18, CONTENT_W * 0.08],
        )
    )

    flow.append(Paragraph("九、待办 / 待核实清单", styles["h2"]))
    todos = [
        "回填“跨境电商企业超 12 万家”的商务部 / 海关原文。",
        "核对美国 2025-05-02 对华 120% 或最低 100 美元关税的行政命令编号与原文。",
        "核对欧盟 2026-07-01 低值包裹增值税与海关免税额度取消的最终立法文本。",
        "为“Temu 用 AI 监测关税”和“SaaS 法规监控趋势”补充公开报道或行业报告出处。",
        "接入真实 Google Trends / 平台榜单 / 海关出口数据后重新生成全部图表与统计。",
    ]
    for todo in todos:
        flow.append(Paragraph(f"- {todo}", styles["bullet"]))
    flow.append(
        Paragraph(
            "说明：本报告全部项目统计可由 scripts/run_data_analysis.py 复现；"
            "行业数字均以来源表登记，未核实条目标注“待核实”。",
            styles["note"],
        )
    )

    doc.build(flow, onFirstPage=_header_footer, onLaterPages=_header_footer)
    print(f"OK: {OUT_PDF} ({OUT_PDF.stat().st_size / 1024:.1f} KB)")

    if SUBMISSION_PDF_DIR.exists():
        SUBMISSION_PDF_DIR.mkdir(parents=True, exist_ok=True)
        target = SUBMISSION_PDF_DIR / OUT_PDF.name
        shutil.copy2(OUT_PDF, target)
        print(f"SYNC: {target}")


if __name__ == "__main__":
    build()
