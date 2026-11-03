"""生成《项目大纲》新版式 PDF（浅色编辑部风格，不再使用旧版深蓝封面/目录/密集表格）。"""

from __future__ import annotations

import pathlib
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
FONT_DIR = pathlib.Path(r"C:\Windows\Fonts")
OUT_DIR = PROJECT_ROOT / "output" / "pdf"
OUT_PDF = OUT_DIR / "跨境电商智能选品系统-项目大纲.pdf"

from src.config import CATEGORIES, MARKETS  # noqa: E402

COMBO_COUNT = len(CATEGORIES) * len(MARKETS)
FORECAST_ROWS = COMBO_COUNT * 90 * 2

# 中文字体
pdfmetrics.registerFont(TTFont("SimHei", str(FONT_DIR / "simhei.ttf")))
pdfmetrics.registerFont(TTFont("Deng", str(FONT_DIR / "Deng.ttf")))
pdfmetrics.registerFont(TTFont("DengB", str(FONT_DIR / "Dengb.ttf")))

# 新版式配色：浅色底 + 墨色文字 + 青绿主色 + 琥珀强调
INK = colors.HexColor("#1F2937")
SLATE = colors.HexColor("#5B6470")
TEAL = colors.HexColor("#0F766E")
TEAL_DARK = colors.HexColor("#115E59")
TEAL_MID = colors.HexColor("#2B7A74")
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
            "title", parent=base["Normal"], fontName="SimHei", fontSize=23, leading=30,
            textColor=INK, spaceAfter=4, wordWrap="CJK",
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontName="Deng", fontSize=11.5, leading=17,
            textColor=SLATE, wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Deng", fontSize=10.2, leading=16,
            textColor=INK, spaceAfter=4, wordWrap="CJK",
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Deng", fontSize=10.2, leading=15.8,
            textColor=INK, leftIndent=8, spaceAfter=3, wordWrap="CJK",
        ),
        "section_num": ParagraphStyle(
            "section_num", parent=base["Normal"], fontName="SimHei", fontSize=18, leading=22,
            textColor=TEAL, wordWrap="CJK",
        ),
        "section_title": ParagraphStyle(
            "section_title", parent=base["Normal"], fontName="SimHei", fontSize=14.5, leading=20,
            textColor=INK, wordWrap="CJK",
        ),
        "card_num": ParagraphStyle(
            "card_num", parent=base["Normal"], fontName="SimHei", fontSize=17, leading=20,
            textColor=GOLD, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "card_label": ParagraphStyle(
            "card_label", parent=base["Normal"], fontName="Deng", fontSize=8.6, leading=12,
            textColor=SLATE, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "flow_title": ParagraphStyle(
            "flow_title", parent=base["Normal"], fontName="DengB", fontSize=10.5, leading=15,
            textColor=WHITE, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "flow_body": ParagraphStyle(
            "flow_body", parent=base["Normal"], fontName="Deng", fontSize=9.2, leading=14,
            textColor=WHITE, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "phase": ParagraphStyle(
            "phase", parent=base["Normal"], fontName="DengB", fontSize=10.5, leading=14,
            textColor=WHITE, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "phase_desc": ParagraphStyle(
            "phase_desc", parent=base["Normal"], fontName="Deng", fontSize=8.6, leading=12.5,
            textColor=WHITE, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "ev_title": ParagraphStyle(
            "ev_title", parent=base["Normal"], fontName="DengB", fontSize=10.8, leading=15,
            textColor=WHITE, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "ev_body": ParagraphStyle(
            "ev_body", parent=base["Normal"], fontName="Deng", fontSize=8.6, leading=12.6,
            textColor=WHITE, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "arrow": ParagraphStyle(
            "arrow", parent=base["Normal"], fontName="SimHei", fontSize=13, leading=16,
            textColor=TEAL, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "note": ParagraphStyle(
            "note", parent=base["Normal"], fontName="Deng", fontSize=9, leading=13.5,
            textColor=SLATE, spaceBefore=2, wordWrap="CJK",
        ),
        "sub_head": ParagraphStyle(
            "sub_head", parent=base["Normal"], fontName="DengB", fontSize=10.2, leading=14,
            textColor=TEAL_DARK, spaceBefore=4, spaceAfter=4, wordWrap="CJK",
        ),
        "table_head": ParagraphStyle(
            "table_head", parent=base["Normal"], fontName="DengB", fontSize=8.3, leading=11,
            textColor=WHITE, alignment=TA_CENTER, wordWrap="CJK",
        ),
        "table_cell": ParagraphStyle(
            "table_cell", parent=base["Normal"], fontName="Deng", fontSize=8.4, leading=12,
            textColor=INK, wordWrap="CJK",
        ),
        "table_cell_bold": ParagraphStyle(
            "table_cell_bold", parent=base["Normal"], fontName="DengB", fontSize=8.4, leading=12,
            textColor=INK, wordWrap="CJK",
        ),
    }


def _header_footer(canvas, doc) -> None:
    canvas.saveState()
    # 页眉
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.7)
    canvas.line(MARGIN_L, PAGE_H - 13 * mm, PAGE_W - MARGIN_R, PAGE_H - 13 * mm)
    canvas.setFont("Deng", 8.5)
    canvas.setFillColor(SLATE)
    canvas.drawString(MARGIN_L, PAGE_H - 11 * mm, "跨境电商智能选品决策系统")
    canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 11 * mm, "项目大纲")
    # 页脚
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.7)
    canvas.line(MARGIN_L, 13 * mm, PAGE_W - MARGIN_R, 13 * mm)
    canvas.setFont("Deng", 8.5)
    canvas.setFillColor(SLATE)
    canvas.drawString(MARGIN_L, 10 * mm, "中国国际大学生创新大赛 · 高教赛道 · 创意组")
    canvas.drawRightString(PAGE_W - MARGIN_R, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def _section_header(styles: dict, num: str, title: str) -> Table:
    return Table(
        [[Paragraph(num, styles["section_num"]), Paragraph(title, styles["section_title"])]],
        colWidths=[18 * mm, CONTENT_W - 18 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, TEAL),
            ]
        ),
    )


def _bullet(styles: dict, text: str) -> Paragraph:
    return Paragraph("•  " + text, styles["bullet"])


def _banner(styles: dict) -> Table:
    text = (
        "<font name='DengB' color='#115E59'>项目一句话</font>："
        "以选品为入口，用 AI 实时聚合国际贸易政策、成本与风险，"
        "帮中小卖家回答“卖什么、怎么卖、卖到哪、是否值得卖”。"
    )
    return Table(
        [[Paragraph("", styles["body"]), Paragraph(text, styles["body"])]],
        colWidths=[5 * mm, CONTENT_W - 5 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), TEAL),
                ("BACKGROUND", (1, 0), (1, 0), MINT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 0),
                ("LEFTPADDING", (1, 0), (1, 0), 10),
                ("RIGHTPADDING", (1, 0), (1, 0), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        ),
    )


def _metrics(styles: dict) -> Table:
    data = [
        ("55 / 55", "自动化测试通过"),
        ("2.31%", "进阶模型 MAPE"),
        ("约 -31%", "相对基线误差下降"),
        ("90 天", "未来预测窗口"),
                (f"{COMBO_COUNT} 组合", "品类 × 市场演示"),
    ]
    cells = [
        [
            [Paragraph(num, styles["card_num"]), Paragraph(label, styles["card_label"])]
            for num, label in data
        ]
    ]
    col_w = CONTENT_W / len(data)
    t = Table(cells, colWidths=[col_w] * len(data), rowHeights=[24 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), MINT),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def _architecture(styles: dict) -> Table:
    def block(title: str, body: str, bg) -> Table:
        return Table(
            [[[Paragraph(title, styles["flow_title"]), Paragraph(body, styles["flow_body"])]]],
            colWidths=[CONTENT_W],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), bg),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            ),
        )

    rows = [
        [
            block(
                "国际贸易数据层",
                "关税税率库 · 汇率行情 · 政策公告 NLP · 物流运价 · 专利商标 · 法规合规",
                TEAL_DARK,
            )
        ],
        [Paragraph("↓", styles["arrow"])],
        [
            block(
                "分析内核",
                "市场 · 舆情 · 供应链 / 政策 · 财务（含关税、汇率）<br/>冲突裁决：置信度 × 权重",
                TEAL,
            )
        ],
        [Paragraph("↓", styles["arrow"])],
        [
            block(
                "综合决策报告",
                "选品推荐 · 到岸成本 · 政策风险预警 · 市场准入建议<br/>展示层：Streamlit 看板 / FastAPI 服务",
                INK,
            )
        ],
    ]
    t = Table(rows, colWidths=[CONTENT_W])
    t.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return t


def _roadmap(styles: dict) -> Table:
    phases = [
        ("MVP（已完成）", "多源预测 + 看板", TEAL_DARK),
        ("一期（已演示）", "政策风险 + 贸易成本", TEAL),
        ("二期（已演示）", "合规 / IP / 物流 / 舆情", TEAL_MID),
        ("远期", "数据信用 + 绿色贸易", INK),
    ]
    arrow_w = 12 * mm
    phase_w = (CONTENT_W - 3 * arrow_w) / 4
    row = []
    for i, (name, desc, bg) in enumerate(phases):
        if i:
            row.append(Paragraph("→", styles["arrow"]))
        cell = Table(
            [[[Paragraph(name, styles["phase"]), Paragraph(desc, styles["phase_desc"])]]],
            colWidths=[phase_w],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), bg),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        )
        row.append(cell)
    col_widths = [phase_w if i % 2 == 0 else arrow_w for i in range(7)]
    t = Table([row], colWidths=col_widths)
    t.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return t


def _evidence_band(styles: dict) -> Table:
    """02 为什么是现在：三列证据卡。"""
    cards = [
        (
            "政策变化快于人工",
            "美国取消 de minimis 免税<br/>欧盟 2026-07 低价值包裹征税<br/>关税 / 税率实时变化",
            TEAL_DARK,
        ),
        (
            "市场已被验证",
            "2025 进出口 2.75 万亿元<br/>同比增长 69.7%<br/>企业超 12 万家",
            TEAL,
        ),
        (
            "行业趋势已验证",
            "Temu 用 AI 实时监测关税<br/>法规 AI 监控成为 SaaS 核心趋势<br/>竞品缺少一体化决策建议",
            TEAL_MID,
        ),
    ]
    col_w = CONTENT_W / 3
    cells = [
        [
            Table(
                [[[Paragraph(t, styles["ev_title"]), Paragraph(b, styles["ev_body"])]]],
                colWidths=[col_w],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), bg),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            )
            for t, b, bg in cards
        ]
    ]
    table = Table(cells, colWidths=[col_w] * 3)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _brains_band(styles: dict) -> Table:
    """03 分析内核：四大脑色块。"""
    brains = [
        ("大脑 1 · 市场", "搜索热度 / 畅销排名 / 出口金额 / 评论增长", TEAL_DARK),
        ("大脑 2 · 舆情", "多语种情感分析 / 评论聚合 / 本地化建议", TEAL),
        ("大脑 3 · 供应链 / 政策", "关税 / 政策公告 NLP / 断货与供给风险", TEAL_MID),
        ("大脑 4 · 财务", "关税 / 汇率 / 支付费率 / 认证合规 / 物流成本", INK),
    ]
    col_w = CONTENT_W / 4
    cells = [
        [
            Table(
                [[[Paragraph(t, styles["flow_title"]), Paragraph(b, styles["flow_body"])]]],
                colWidths=[col_w],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), bg),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            )
            for t, b, bg in brains
        ]
    ]
    table = Table(cells, colWidths=[col_w] * 4)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _capability_band(styles: dict) -> Table:
    """01 项目定位：核心能力速览。"""
    items = [
        ("数据聚合", "关税 / 汇率 / 合规 / 物流 / 市场数据一站式收拢", TEAL_DARK),
        ("趋势预测", "双模型预测未来 90 天销量与 80% 置信区间", TEAL),
        ("选品推荐", "Top N 选品 + 中文推荐理由，逐条可解释可追溯", TEAL_MID),
        ("贸易决策", "到岸成本 / 政策风险 / 准入与备货建议", INK),
    ]
    col_w = CONTENT_W / 4
    cells = [
        [
            Table(
                [[[Paragraph(t, styles["flow_title"]), Paragraph(b, styles["flow_body"])]]],
                colWidths=[col_w],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), bg),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            )
            for t, b, bg in items
        ]
    ]
    table = Table(cells, colWidths=[col_w] * 4)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _pain_band(styles: dict) -> Table:
    """01 项目定位：目标用户与痛点速览。"""
    return _data_table(
        styles,
        ["目标用户", "核心痛点", "系统如何解决"],
        [
            ["中小平台卖家", "政策、成本、合规分散在多平台，靠人工查表与经验试错", "一站式收拢数据，输出可直接执行的贸易决策建议"],
            ["外贸选品团队", "选品依赖关键词与流量工具，缺少关税与到岸成本测算", "趋势预测 + 到岸成本 + 准入建议同步给出"],
            ["供应链 / 独立站", "多市场信息割裂，断货与政策突变难以及时感知", "四大脑联合分析，冲突场景按置信度 × 权重裁决"],
        ],
        [36 * mm, 70 * mm, 72 * mm],
        first_col_bold=True,
    )


def _data_table(
    styles: dict,
    headers: list[str],
    rows: list[list[str]],
    col_widths: list[float] | None = None,
    first_col_bold: bool = False,
) -> Table:
    """浅色数据表：深青表头 + 白/薄荷交替行。"""
    head = [Paragraph(h, styles["table_head"]) for h in headers]
    body = [
        [
            Paragraph(
                cell,
                styles["table_cell_bold"] if (i == 0 and first_col_bold) else styles["table_cell"],
            )
            for i, cell in enumerate(row)
        ]
        for row in rows
    ]
    if col_widths is None:
        col_widths = [CONTENT_W / len(headers)] * len(headers)
    t = Table([head] + body, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TEAL_DARK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, MINT]),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    return t


def main() -> None:
    styles = _styles()
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="跨境电商智能选品决策系统 - 项目大纲",
        author="大创项目团队",
    )
    story = []

    # 标题区
    story.append(Paragraph("中国国际大学生创新大赛 · 高教赛道 · 创意组", styles["kicker"]))
    story.append(Paragraph("跨境电商智能选品决策系统", styles["title"]))
    story.append(Paragraph("基于多源数据融合的跨境贸易决策智能（Trade Intelligence）", styles["subtitle"]))
    story.append(Spacer(1, 8))
    story.append(_banner(styles))
    story.append(Spacer(1, 14))

    # 01 项目定位
    story.append(_section_header(styles, "01", "项目定位"))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "选品只是入口，贸易政策、成本与合规风险才是真正的护城河。"
            "系统把分散在多个平台的关税、汇率、合规、物流与市场数据收拢到一套决策链路中，"
            "替代卖家的人工查表与经验试错。",
            styles["body"],
        )
    )
    story.append(Spacer(1, 4))
    story.append(_bullet(styles, "项目名称：基于多源数据融合的跨境电商智能选品决策系统"))
    story.append(_bullet(styles, "升级定位：跨境贸易决策智能（Trade Intelligence）"))
    story.append(_bullet(styles, "目标用户：Amazon / 速卖通 / Shopee / Temu 中小卖家，外贸选品团队、供应链企业与独立站运营者"))
    story.append(_bullet(styles, "核心闭环：多源数据 → 趋势预测 → 选品推荐 → 贸易成本与风险测算 → 决策建议"))
    story.append(_bullet(styles, "核心价值：政策变化的速度已经超过人工能跟踪的速度，“AI 监控 + 实时成本测算”从可选项变成刚需"))
    story.append(_bullet(styles, "数据合规：优先官方 API 与公开政策库（CBP / TARIC / USPTO / EUIPO / 汇率与运价指数），用户经营数据授权并脱敏后回流"))
    story.append(_bullet(styles, "参赛赛道：中国国际大学生创新大赛 · 高教赛道 · 创意组"))
    story.append(Paragraph("核心能力速览", styles["sub_head"]))
    story.append(_capability_band(styles))
    story.append(Paragraph("目标用户与痛点", styles["sub_head"]))
    story.append(_pain_band(styles))
    story.append(Spacer(1, 10))

    # 02 为什么是现在
    story.append(_section_header(styles, "02", "为什么是现在"))
    story.append(Spacer(1, 6))
    story.append(_evidence_band(styles))
    story.append(Paragraph("机会验证清单", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["验证项", "证据", "结论"],
            [
                ["政策变化速度", "美国取消 de minimis 免税；欧盟 2026-07 低价值包裹征税", "人工跟不住，实时监控与成本测算成为刚需"],
                ["市场增长", "2025 跨境电商进出口 2.75 万亿元，同比增长 69.7%", "选品与合规决策需求持续扩大"],
                ["技术趋势", "Temu 已用 AI 实时监测关税；法规 AI 监控成为跨境 SaaS 核心", "一体化决策建议存在市场空白"],
                ["竞品空白", "卖家精灵 / Jungle Scout 偏关键词与流量工具", "政策、成本、风险一体化决策闭环尚未补齐"],
            ],
            [30 * mm, 86 * mm, 62 * mm],
        )
    )
    story.append(Paragraph("政策变化时间线", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["时间", "事件", "影响"],
            [
                ["2025-08", "美国取消 800 美元以下小额包裹 de minimis 免税", "小额包裹清关成本、关税与合规门槛上升"],
                ["2026-07", "欧盟对 150 欧元以下低价值包裹征税", "平台与直邮模式的成本结构发生变化"],
                ["持续", "AI 监控目标国法规成为跨境 SaaS 核心趋势", "“AI 监控 + 实时成本测算”从可选项变成刚需"],
            ],
            [30 * mm, 78 * mm, 70 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(_bullet(styles, "政策变化快于人工：美国取消 de minimis 免税，欧盟 2026 年 7 月起对低价值包裹征税"))
    story.append(_bullet(styles, "市场已被验证：2025 年中国跨境电商进出口 2.75 万亿元，增长 69.7%，企业超 12 万家"))
    story.append(_bullet(styles, "行业已验证需求：Temu 用 AI 实时监测关税变化并自动调整；“AI 监控目标国法规”成为跨境 SaaS 核心趋势"))
    story.append(_bullet(styles, "中小卖家普遍缺少数据团队，政策、成本、合规分散在多平台，试错成本高"))
    story.append(Spacer(1, 10))

    # 03 我们怎么做
    story.append(_section_header(styles, "03", "我们怎么做"))
    story.append(Spacer(1, 6))
    story.append(_architecture(styles))
    story.append(Paragraph("从数据到决策", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["环节", "做什么", "产出示例"],
            [
                ["数据层", "收拢关税 / 汇率 / 物流 / 市场 / 舆情数据，统一 Schema", "标准化数据集与事件库"],
                ["分析内核", "四大脑并行输出结论与置信度", "“市场热销” + “政策风险高”"],
                ["冲突裁决", "按置信度 × 决策权重合并结论", "综合决策意见与理由"],
                ["决策输出", "生成选品 Top N、到岸成本、风险预警、准入建议", "可直接执行的中文建议"],
            ],
            [30 * mm, 74 * mm, 74 * mm],
        )
    )
    story.append(Paragraph("数据源与更新频率", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["数据源", "内容", "更新频率", "状态"],
            [
                ["CBP / TARIC", "关税税率、政策公告", "按日抓取 + NLP 解析", "规划接入"],
                ["汇率 / 运价指数", "汇率行情、SCFI 风格运价", "按日 / 周", "演示版内置"],
                ["搜索热度", "Google Trends 等趋势数据", "按日 / 周", "规划接入"],
                ["Amazon SP-API / Ads API", "销量、排名、广告表现", "实时 / 按日", "规划接入"],
                ["Shopee Open Platform", "东南亚市场数据", "实时 / 按日", "规划接入"],
                ["USPTO / EUIPO", "商标、专利、外观设计", "官方公开数据", "规划接入"],
                ["用户回流", "订单、履约、退款、回款", "授权 + 脱敏", "远期规划"],
            ],
            [38 * mm, 62 * mm, 42 * mm, 36 * mm],
        )
    )
    story.append(Paragraph("数据管道与特征工程", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["阶段", "内容", "产出"],
            [
                ["采集", "可扩展采集框架；演示数据带趋势、季节性与品类差异，保证离线可运行", "raw 数据集"],
                ["清洗", "统一 Schema、去重、枚举校验、缺失值填充", "clean_data.csv + SQLite"],
                ["特征", "20 个特征列：lag 1/2/4/8、滚动均值（4/8 周）、增长率与差分、月份 / 周数季节编码", "训练特征表"],
                ["规划特征", "外部事件：关税政策生效日期、汇率跳变、Prime Day / 黑五", "事件特征列"],
            ],
            [26 * mm, 108 * mm, 44 * mm],
        )
    )
    story.append(_brains_band(styles))
    story.append(Paragraph("四大脑输入输出", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["大脑", "核心输入", "输出与置信度"],
            [
                ["大脑 1 · 市场", "搜索热度、畅销排名、出口金额、评论增长", "品类 / 市场趋势判断"],
                ["大脑 2 · 舆情", "多语种评论与情感词库", "情绪分、正 / 负 / 中性占比、本地化建议"],
                ["大脑 3 · 供应链 / 政策", "政策公告 NLP、断货与供给指标", "政策与供给风险等级"],
                ["大脑 4 · 财务", "关税、汇率、支付费率、认证合规、物流成本", "到岸成本、利润测算、三方案对比"],
            ],
            [36 * mm, 74 * mm, 68 * mm],
        )
    )
    story.append(Paragraph("所有结论均附带置信度 = 数据完整度 × 模型拟合度，冲突场景按“置信度 × 决策权重”裁决。", styles["note"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("双模型预测", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["模型", "方法", "表现"],
            [
                ["Prophet 基线", "单变量时间序列，对数变换，周 / 年季节性", "MAPE 3.36%"],
                ["LightGBM 进阶", "20 特征梯度提升，滚动递归预测", "MAPE 2.31%"],
            ],
            [40 * mm, 96 * mm, 42 * mm],
        )
    )
    story.append(Paragraph("相对提升约 31%，满足计划验收标准（相对提升 ≥ 10%）；输出未来 90 天日粒度预测与 80% 置信区间。", styles["note"]))
    story.append(Paragraph("推荐信号与中文说明", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["信号", "示例条件", "自动生成说明"],
            [
                ["高增长", "预测增长高于同类中位数", "“该品类未来 90 天预测增长 XX%，建议关注”"],
                ["搜索升温", "搜索热度连续 4 周上行", "“搜索热度进入上升通道，可提前备货”"],
                ["蓝海 / 红海", "竞争度低于 / 高于阈值", "“竞争度低，适合切入；或竞争激烈，谨慎进入”"],
                ["评论活跃", "评论增长高于阈值", "“评论活跃，转化潜力较高”"],
                ["政策预警", "目标市场关税 / 合规变化", "“建议暂缓或切换市场，并更新成本测算”"],
            ],
            [28 * mm, 64 * mm, 86 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(_bullet(styles, "综合评分 = 0.35 × 预测增长 + 0.30 × 搜索趋势 + 0.25 × 竞争度（反向）+ 0.10 × 评论增长"))
    story.append(_bullet(styles, "决策输出：选品 Top N、到岸成本、政策风险预警、市场准入建议；Streamlit 看板与 FastAPI 均可集成"))
    story.append(Paragraph("推荐权重与数据来源", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["权重", "信号", "计分口径", "数据来源"],
            [
                ["0.35", "预测增长", "未来 90 天预测增长相对同类中位数", "双模型预测"],
                ["0.30", "搜索趋势", "搜索热度连续 4 周上行", "Google Trends / 搜索热度"],
                ["0.25", "竞争度（反向）", "竞争度越低得分越高", "竞品数 / 价格中位数 / 评论集中度"],
                ["0.10", "评论增长", "评论增长高于阈值", "平台评论数据"],
            ],
            [18 * mm, 30 * mm, 66 * mm, 64 * mm],
        )
    )
    story.append(Spacer(1, 10))

    # 04 已经做到哪
    story.append(_section_header(styles, "04", "已经做到哪"))
    story.append(Spacer(1, 6))
    story.append(_metrics(styles))
    story.append(Spacer(1, 6))
    story.append(Paragraph("验证结果", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["指标", "数值", "说明"],
            [
                ["自动化测试", "55 / 55", "全部通过，指标落盘 + 版本化评估"],
                ["基线 MAPE", "3.36%", "Prophet：对数变换 + 周 / 年季节性"],
                ["进阶 MAPE", "2.31%", "LightGBM：20 特征 + 滚动递归预测"],
                ["相对提升", "约 31%", "满足验收标准（相对提升 ≥ 10%）"],
                ["预测规模", f"{FORECAST_ROWS} 行", f"{COMBO_COUNT} 组合 × 90 天 × 2 模型"],
                ["数据口径", "92 周训练 / 12 周隐藏测试", "固定随机种子，保证可复现"],
            ],
            [36 * mm, 34 * mm, 108 * mm],
        )
    )
    story.append(_bullet(styles, "端到端流水线 + Streamlit 看板 + FastAPI 演示服务"))
    story.append(_bullet(styles, "双模型预测：Prophet 基线 MAPE 3.36% → LightGBM 进阶 2.31%（相对提升约 31%，满足验收标准 ≥ 10%）"))
    story.append(
        _bullet(
            styles,
            f"{COMBO_COUNT} 组合（{len(CATEGORIES)} 品类 × {len(MARKETS)} 市场）× 90 天 × 2 模型，"
            f"共 {FORECAST_ROWS} 行预测；指标落盘 + 版本化评估",
        )
    )
    story.append(_bullet(styles, "贸易决策演示：政策风险、到岸成本、合规准入、知识产权、物流、多语言舆情、CBAM、融资就绪与多脑冲突裁决离线演示"))
    story.append(Paragraph("贸易决策模块清单", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["模块", "演示能力"],
            [
                ["关税与政策风险", "政策事件、有效税率、单件关税、到岸成本、利润冲击与应对建议"],
                ["财务贸易成本", "采购、关税、汇率 ±5% 敏感性、支付通道、三物流方案（小包直邮 / 海运整柜 / 海外仓）"],
                ["合规与市场准入", "IOSS / VAT、CE / FCC / FDA / RoHS / CPSC / GPSR 清单与准入可行性评分"],
                ["知识产权", "商标 / 专利 / 外观设计库，低 / 中 / 高风险，支持候选品名称匹配"],
                ["物流运价", "SCFI 风格演示序列，未来 4 周指数、单件成本、时效与拥堵风险"],
                ["多语言舆情", "英 / 西 / 德 / 日 / 葡情感词库，情绪分与本地化建议"],
                ["绿色贸易", "CBAM 暴露度、预估碳成本与政策趋势"],
                ["数据信用", "融资就绪评分与建议档位（供应链金融 / 信用贷 / 小额试单 / 暂不建议）"],
                ["多脑冲突裁决", "按置信度 × 权重融合 7 类信号，输出冲突等级、裁决后得分与风险优先建议"],
            ],
            [42 * mm, 136 * mm],
            first_col_bold=True,
        )
    )
    story.append(Paragraph("API 演示服务", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["接口", "说明"],
            [
                ["GET /api/health", "服务健康检查"],
                ["GET /api/policy/events", "政策事件监控清单"],
                ["GET /api/trade/decision", "按品类 / 市场 / 售价 / 采购成本返回完整贸易决策（含多脑冲突裁决）"],
                ["GET /api/trade/report", f"最近一次 {COMBO_COUNT} 组合演示报告"],
                ["GET /api/recommendations", "Top N 选品推荐"],
            ],
            [66 * mm, 112 * mm],
            first_col_bold=True,
        )
    )
    story.append(Paragraph("已实现 / 规划边界", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["能力", "状态", "说明"],
            [
                ["多源选品预测", "已实现演示版", "合成数据 + 双模型 + 90 天预测"],
                ["贸易决策九模块", "已实现离线演示", "政策 / 成本 / 合规 / IP / 物流 / 舆情 / CBAM / 信用 / 冲突裁决"],
                ["API 演示服务", "已实现", "5 个接口，含 /docs 文档"],
                ["真实数据接入", "规划中", "Google Trends / Amazon / CBP / TARIC / USPTO / EUIPO"],
                ["实时预警与推送", "规划中", "API 定时任务 + 前端数据更新"],
                ["授权经营数据与信用", "远期", "融资就绪评分已离线演示，真实授信需授权数据"],
            ],
            [40 * mm, 30 * mm, 108 * mm],
        )
    )
    story.append(Spacer(1, 10))

    # 05 为什么是我们
    story.append(_section_header(styles, "05", "为什么是我们"))
    story.append(Spacer(1, 6))
    story.append(_bullet(styles, "对照顶级 AI：同一份 92 周训练数据 + 12 周隐藏测试（23760 格）+ 统一提示词，DeepSeek 跑 2 次；通用 AI 在完整率、数字可追溯、置信区间、复现性与批量自动化上存在系统性缺口"))
    story.append(Paragraph("与顶级 AI 的对照", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["维度", "通用 AI", "本项目"],
            [
                ["描述性洞察", "擅长", "同样提供中文推荐说明"],
                ["预测完整率", "存在缺口", "统一预测表 + 字段字典校验"],
                ["数字可追溯", "弱", "指标落盘 JSON / CSV，逐条可追溯"],
                ["置信区间", "不保证", "输出 80% 置信区间"],
                ["可复现性", "弱", "固定随机种子 + 版本化评估"],
                ["批量自动化", "弱", "端到端流水线 + 55 项自动化测试"],
            ],
            [34 * mm, 74 * mm, 70 * mm],
        )
    )
    story.append(_bullet(styles, "与竞品差异：卖家精灵、Jungle Scout 偏关键词与流量工具；自建表格零成本但缺自动化与实时预警；本项目补齐政策、成本、风险一体化决策闭环"))
    story.append(Paragraph("与竞品差异", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["竞品", "优势", "本项目差异化"],
            [
                ["卖家精灵", "数据全、用户多", "关税 / 政策风险引擎与完整到岸成本测算"],
                ["Jungle Scout", "国外成熟", "中国卖家视角、出口数据、政策合规"],
                ["自建表格分析", "零成本", "自动化、可视化、实时预警"],
            ],
            [30 * mm, 56 * mm, 92 * mm],
        )
    )
    story.append(_bullet(styles, "落地可复现：55 项自动化测试、指标落盘、版本化评估、固定随机种子，决策建议可解释、可追溯、可复现"))
    story.append(Spacer(1, 10))

    # 06 下一步
    story.append(_section_header(styles, "06", "下一步"))
    story.append(Spacer(1, 6))
    story.append(_roadmap(styles))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "阶段说明：MVP 已完成演示版；一期、二期为已实现的离线演示能力；远期保留数据信用与绿色贸易叙事。",
            styles["note"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(Paragraph("分阶段验收标准", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["阶段", "验收标准", "演示证据"],
            [
                ["MVP", "预测流水线一键运行，双模型 MAPE 达标，看板可展示预测与推荐", "55 / 55 测试、MAPE 3.14%、看板"],
                ["一期", "政策风险与到岸成本可离线测算，并输出应对建议", "政策 / 成本模块演示"],
                ["二期", "合规 / IP / 物流 / 舆情覆盖目标市场，输出准入与风险等级", "合规 / IP / 物流 / 舆情演示"],
                ["远期", "数据信用与绿色贸易叙事完整，融资就绪评分与 CBAM 趋势可演示", "信用 / CBAM 模块演示"],
            ],
            [26 * mm, 88 * mm, 64 * mm],
        )
    )
    story.append(Spacer(1, 6))
    story.append(Paragraph("行动清单", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["行动", "类型", "优先级", "预期产出"],
            [
                ["接入 Google Trends 与 Amazon Best Sellers", "数据接入", "高", "真实热度与榜单特征"],
                ["按 HS 编码映射海关出口数据到品类", "数据接入", "高", "品类级出口金额"],
                ["接入 CBP / TARIC 政策公告与 USPTO / EUIPO", "数据接入", "高", "政策事件库 + 税率更新"],
                ["扩充市场与品类，扩展训练数据", "数据", "中", "训练数据规模提升"],
                ["引入外部事件特征（Prime Day、黑五、关税、汇率）", "特征", "中", "事件特征列"],
                ["API 定时任务与预警推送，前端支持数据更新", "工程", "中", "自动化监控闭环"],
                ["CBAM 申报数据与碳排因子库", "远期", "低", "绿色贸易模块升级"],
            ],
            [72 * mm, 26 * mm, 22 * mm, 58 * mm],
        )
    )
    story.append(_bullet(styles, "接入真实 Google Trends 与 Amazon Best Sellers；按 HS 编码映射海关出口数据到品类，扩充市场与品类训练数据"))
    story.append(_bullet(styles, "接入 CBP / TARIC 政策公告、USPTO / EUIPO、SCFI / 船司运价接口；引入外部事件特征（Prime Day、黑五、关税政策、汇率跳变）"))
    story.append(_bullet(styles, "API 增加定时任务与预警推送，前端应用支持数据更新；远期沉淀授权经营数据升级信用模型、补充 CBAM 碳排因子库"))
    story.append(Spacer(1, 10))

    # 07 支撑材料
    story.append(_section_header(styles, "07", "支撑材料"))
    story.append(Spacer(1, 6))
    story.append(
        _data_table(
            styles,
            ["材料", "位置与说明"],
            [
                ["商业计划书 / 技术文档 / 数据字典 / 路演大纲 / 对照组分析报告", "docs/"],
                ["演示看板", "app.py（Streamlit，本地 8501 端口）"],
                ["FastAPI 演示服务", "scripts/run_api.py（/docs 接口文档）"],
                ["模型产物", "models/（预测、推荐、评估报告）"],
                ["自动化测试", "tests/（55 项，可一键复跑）"],
                ["贸易决策演示产物", "output/trade/（报告、结构化指标、到岸成本明细）"],
            ],
            [66 * mm, 112 * mm],
            first_col_bold=True,
        )
    )
    story.append(_bullet(styles, "商业计划书、技术文档、数据字典、路演大纲、对照组分析报告"))
    story.append(_bullet(styles, "演示看板、FastAPI 文档、模型产物、自动化测试"))
    story.append(_bullet(styles, "贸易决策演示产物：output/trade/（报告、结构化指标、到岸成本明细）"))

    # 08 商业模式与团队
    story.append(Spacer(1, 10))
    story.append(_section_header(styles, "08", "商业模式与团队"))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "以“免费工具引流 → 专业版订阅 → 企业定制与数据报告”三层递进变现；"
            "初期团队自研为主，成本集中在算力、数据采集与市场推广，目标 6 个月内完成种子用户验证。",
            styles["body"],
        )
    )
    story.append(Paragraph("商业模式", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["模式", "收入来源", "关键动作"],
            [
                ["SaaS 订阅", "基础版免费 / 专业版按月付费", "先以免费版沉淀用户与反馈"],
                ["企业定制", "供应链与品牌出海数据咨询", "面向外贸企业与品牌方"],
                ["数据报告", "品类趋势 / 政策影响周报", "提升品牌影响与获客"],
                ["远期数据服务", "融资就绪评分与供应链金融分润", "授权经营数据脱敏后沉淀"],
            ],
            [30 * mm, 64 * mm, 84 * mm],
        )
    )
    story.append(Paragraph("团队构成", styles["sub_head"]))
    story.append(
        _data_table(
            styles,
            ["角色", "覆盖内容"],
            [
                ["数据", "数据采集、清洗、统一 Schema 与数据字典"],
                ["算法", "预测模型、推荐引擎、评估与可复现"],
                ["产品", "看板、API、演示链路与用户场景"],
                ["商业", "商业模式、市场调研、竞品分析与路演"],
                ["跨境顾问", "政策合规与国际贸易业务背景支撑（含顾问）"],
            ],
            [30 * mm, 148 * mm],
            first_col_bold=True,
        )
    )
    story.append(_bullet(styles, "验证要求：补充卖家访谈数量与结论、试用用户反馈、付费意愿问卷结果；市场规模给出可追溯的推导链"))
    story.append(Spacer(1, 10))

    # 09 风险与对策
    story.append(_section_header(styles, "09", "风险与对策"))
    story.append(Spacer(1, 6))
    story.append(
        _data_table(
            styles,
            ["风险", "对策"],
            [
                ["政策数据获取受限", "全部采用官方 / 公开数据（CBP / TARIC / USPTO / 汇率与运价指数），并明确更新频率"],
                ["模型精度不足", "规则引擎 + 预测混合，冲突裁决给出置信度与权重来源"],
                ["合规门槛高", "先做市场准入清单与认证成本提示，不替代专业法律意见"],
                ["时间紧张", "优先完成关税 / 政策风险引擎与财务贸易成本模型，其余进入 Roadmap"],
                ["真实数据依赖", "演示数据带趋势与季节性保证离线可运行；接入顺序按优先级推进"],
            ],
            [36 * mm, 142 * mm],
            first_col_bold=True,
        )
    )

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    print("PDF generated:", OUT_PDF)


if __name__ == "__main__":
    main()
