"""生成《已实现内容与参赛大纲》展示 PDF（reportlab + 中文字体）。"""

from __future__ import annotations

import json
import pathlib
import sys

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
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
SHOT_PATH = PROJECT_ROOT / "docs" / "dashboard_preview.png"
OUT_DIR = PROJECT_ROOT / "output" / "pdf"
OUT_PDF = OUT_DIR / "跨境电商智能选品系统-已实现内容与参赛大纲.pdf"

from src.config import (  # noqa: E402
    CATEGORIES,
    MARKETS,
    category_name,
    market_name,
)

COMBO_COUNT = len(CATEGORIES) * len(MARKETS)
FORECAST_ROWS = COMBO_COUNT * 90 * 2
CATEGORY_NAMES = " / ".join(CATEGORIES.values())
MARKET_NAMES = " / ".join(MARKETS.values())
HISTORY_ROWS = COMBO_COUNT * 52

# 注册中文字体
pdfmetrics.registerFont(TTFont("SimHei", str(FONT_DIR / "simhei.ttf")))
pdfmetrics.registerFont(TTFont("Deng", str(FONT_DIR / "Deng.ttf")))
pdfmetrics.registerFont(TTFont("DengB", str(FONT_DIR / "Dengb.ttf")))

# 配色
NAVY = colors.HexColor("#1E3A8A")
BLUE = colors.HexColor("#2563EB")
ORANGE = colors.HexColor("#F59E0B")
LIGHT = colors.HexColor("#F1F5F9")
TEXT = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#CBD5E1")

PAGE_W, PAGE_H = A4
MARGIN_L = 16 * mm
MARGIN_R = 16 * mm
MARGIN_T = 20 * mm
MARGIN_B = 18 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


def _load_metrics() -> dict:
    payload = json.loads((PROJECT_ROOT / "models" / "metrics.json").read_text(encoding="utf-8"))
    return payload


def _load_recommendations(top: int = 3) -> list[dict]:
    import csv

    path = PROJECT_ROOT / "models" / "recommendations.csv"
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))[:top]


def _load_image_size() -> tuple[int, int]:
    with Image.open(SHOT_PATH) as img:
        return img.size


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title", fontName="SimHei", fontSize=27, leading=36, textColor=NAVY,
            alignment=TA_CENTER, spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", fontName="DengB", fontSize=13, leading=19, textColor=MUTED,
            alignment=TA_CENTER, spaceAfter=4,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta", fontName="Deng", fontSize=11, leading=18, textColor=TEXT,
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "h1", fontName="SimHei", fontSize=17, leading=23, textColor=NAVY,
            spaceBefore=10, spaceAfter=8, keepWithNext=1,
        ),
        "h2": ParagraphStyle(
            "h2", fontName="DengB", fontSize=12.5, leading=17, textColor=BLUE,
            spaceBefore=8, spaceAfter=5, keepWithNext=1,
        ),
        "h3": ParagraphStyle(
            "h3", fontName="DengB", fontSize=11, leading=15, textColor=TEXT,
            spaceBefore=6, spaceAfter=3, keepWithNext=1,
        ),
        "body": ParagraphStyle(
            "body", fontName="Deng", fontSize=10.2, leading=15.6, textColor=TEXT,
            spaceAfter=4, alignment=TA_LEFT,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Deng", fontSize=10.2, leading=15.6,
            textColor=TEXT, leftIndent=10, spaceAfter=2.5,
        ),
        "note": ParagraphStyle(
            "note", fontName="Deng", fontSize=9, leading=13.5, textColor=MUTED, spaceAfter=3,
        ),
        "cell": ParagraphStyle(
            "cell", fontName="Deng", fontSize=9.2, leading=13.2, textColor=TEXT,
        ),
        "cell_head": ParagraphStyle(
            "cell_head", fontName="DengB", fontSize=9.4, leading=13.4, textColor=colors.white,
        ),
        "toc": ParagraphStyle(
            "toc", fontName="Deng", fontSize=10.5, leading=19, textColor=TEXT,
        ),
    }


def _styled_table(styles: dict, data: list, col_widths: list, header_row: bool = True, first_col_bg: bool = False) -> Table:
    """生成带表头与交替底纹的统一表格。"""
    table_rows = []
    for idx, row in enumerate(data):
        if idx == 0 and header_row:
            table_rows.append([Paragraph(x, styles["cell_head"]) for x in row])
        else:
            table_rows.append([Paragraph(x, styles["cell"]) for x in row])
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header_row:
        style_cmds.append(("BACKGROUND", (0, 0), (-1, 0), BLUE))
        style_cmds.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]))
    else:
        style_cmds.append(("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]))
    if first_col_bg:
        if header_row:
            style_cmds.append(("BACKGROUND", (0, 1), (0, -1), LIGHT))
        else:
            style_cmds.append(("BACKGROUND", (0, 0), (0, -1), LIGHT))
    return Table(
        table_rows,
        colWidths=col_widths,
        repeatRows=1 if header_row else 0,
        style=TableStyle(style_cmds),
    )


def _make_header_footer() -> callable:
    def draw(canvas, doc):
        canvas.saveState()
        # 页眉
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN_L, PAGE_H - 14 * mm, PAGE_W - MARGIN_R, PAGE_H - 14 * mm)
        canvas.setFont("Deng", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN_L, PAGE_H - 12 * mm, "跨境电商智能选品决策系统")
        canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 12 * mm, "大创项目展示")
        # 页脚
        canvas.setFont("Deng", 8)
        canvas.drawCentredString(PAGE_W / 2, 11 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    return draw


def _cover(styles: dict) -> list:
    story = []
    story.append(Spacer(1, 56))
    story.append(
        Table(
            [[Paragraph("中国国际大学生创新大赛", styles["cover_sub"])]],
            colWidths=[CONTENT_W],
            style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]),
        )
    )
    story.append(Spacer(1, 22))
    story.append(
        Table(
            [[Paragraph("跨境电商智能选品决策系统", styles["cover_title"])]],
            colWidths=[CONTENT_W],
            style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]),
        )
    )
    story.append(Spacer(1, 10))
    story.append(
        Table(
            [[Paragraph("基于多源数据融合的跨境贸易决策智能（Trade Intelligence）", styles["cover_sub"])]],
            colWidths=[CONTENT_W],
            style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]),
        )
    )
    story.append(Spacer(1, 18))
    band = Table(
        [[""]],
        colWidths=[CONTENT_W],
        rowHeights=[3],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BLUE),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )
    story.append(band)
    story.append(Spacer(1, 20))
    for line in [
        "高教赛道 · 创意组 · 国际贸易 × AI 数据",
        "以选品为入口，聚合关税、汇率、合规、物流与市场多源数据，",
        "实时测算到岸成本与风险，输出可执行的贸易决策建议。",
    ]:
        story.append(
            Table(
                [[Paragraph(line, styles["cover_meta"])]],
                colWidths=[CONTENT_W],
                style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]),
            )
        )
        story.append(Spacer(1, 4))
    story.append(Spacer(1, 40))
    story.append(
        Table(
            [[Paragraph("已实现内容与参赛大纲", styles["cover_sub"])]],
            colWidths=[CONTENT_W],
            style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]),
        )
    )
    story.append(Spacer(1, 12))
    story.append(PageBreak())
    return story


def _toc(styles: dict) -> list:
    story = []
    story.append(Paragraph("目录", styles["h1"]))
    toc_items = [
        ("01", "项目总览：定位、价值与核心能力"),
        ("02", "已实现内容：系统架构、数据、算法与展示"),
        ("03", "已实现内容：工程结构与验证结果"),
        ("04", "参赛大纲：商业计划书与路演"),
        ("05", "参赛大纲：技术文档与数据字典概要"),
        ("06", "下一步计划与附录"),
    ]
    rows = []
    for idx, (num, title) in enumerate(toc_items):
        rows.append(
            [
                Paragraph(num, styles["toc"]),
                Paragraph(title, styles["toc"]),
            ]
        )
    toc_table = Table(
        rows,
        colWidths=[16 * mm, CONTENT_W - 16 * mm],
        style=TableStyle(
            [
                ("TEXTCOLOR", (0, 0), (0, -1), BLUE),
                ("FONTNAME", (0, 0), (-1, -1), "Deng"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, idx), (-1, idx), 0.4, LINE),
            ]
        ),
    )
    story.append(toc_table)
    story.append(Spacer(1, 14))
    story.append(PageBreak())
    return story


def _section_overview(styles: dict) -> list:
    story = []
    story.append(Paragraph("01  项目总览", styles["h1"]))
    story.append(
        Paragraph(
            "项目面向 Amazon、速卖通、Shopee 等平台的中小卖家与外贸选品团队，"
            "定位为跨境贸易决策智能（Trade Intelligence）：以选品为入口，"
            "聚合国际贸易政策、成本与市场多源公开数据，输出选品、到岸成本、"
            "政策风险与市场准入的一体化决策建议。",
            styles["body"],
        )
    )

    cards = [
        ("目标用户", "中小跨境卖家、外贸选品团队、独立站运营者"),
        ("核心价值", "实时跟踪政策与成本变化，回答卖什么、怎么卖、卖到哪、是否值得卖"),
        ("参赛定位", "高教赛道 · 创意组 · 国际贸易 × AI 数据"),
    ]
    card_rows = []
    for title, text in cards:
        card_rows.append(
            [
                Paragraph(f"<font name='DengB' color='#1E3A8A'>{title}</font>", styles["cell"]),
                Paragraph(text, styles["cell"]),
            ]
        )
    card_table = Table(
        card_rows,
        colWidths=[34 * mm, CONTENT_W - 34 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        ),
    )
    story.append(card_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("核心能力", styles["h2"]))
    bullets = [
        "国际贸易数据层：关税税率库、汇率行情、政策公告 NLP、物流运价指数、专利商标库、法规合规库。",
        "多源市场数据：Google Trends 搜索热度、Amazon 畅销排名、海关出口金额、评论增长、竞争度。",
        "双模型预测：Prophet 基线 + LightGBM 进阶，输出未来 90 天销量预测与置信区间。",
        "决策报告：选品推荐、到岸成本测算、政策风险预警、市场准入建议，冲突裁决基于置信度 × 权重。",
    ]
    for b in bullets:
        story.append(Paragraph("•  " + b, styles["bullet"]))

    story.append(Paragraph("创新点", styles["h2"]))
    innovation_bullets = [
        "定位创新：从选品工具升级为跨境贸易决策智能，覆盖政策、成本、合规、IP、物流、舆情、CBAM 与融资全链路。",
        "决策创新：政策事件被量化为有效税率、最低关税与到岸成本利润冲击，输出可执行应对建议。",
        "方法创新：多源信号统一进入推荐评分，冲突裁决基于置信度 × 权重，保证决策可解释。",
        "闭环创新：报告、看板与 FastAPI 共用同一套贸易决策计算，106 个自动化测试验证。",
        "数据资产创新：授权脱敏经营数据回流，为供应链金融信用评分建立数据飞轮。",
    ]
    for b in innovation_bullets:
        story.append(Paragraph("•  " + b, styles["bullet"]))
    story.append(
        Paragraph(
            "边界：核心算法采用成熟方法，当前为离线演示；CBP / TARIC / USPTO 等真实数据接口与对照组结果待接入 / 回填。",
            styles["note"],
        )
    )
    story.append(PageBreak())
    return story


def _section_implemented_arch(styles: dict) -> list:
    story = []
    story.append(Paragraph("02  已实现内容：系统架构、数据、算法与展示", styles["h1"]))

    story.append(Paragraph("系统架构", styles["h2"]))
    layers = [
        ("数据层", "数据采集框架（Amazon 热销榜 / 海关接口）、统一清洗管道、SQLite 存储、合成演示数据"),
        ("算法层", "特征工程（20 维）、Prophet 基线、LightGBM 进阶、规则+预测推荐引擎"),
        ("展示层", "Streamlit 看板 + FastAPI 演示服务：多源趋势、预测、推荐、市场对比与贸易决策 JSON 接口"),
    ]
    rows = []
    for name, desc in layers:
        rows.append(
            [
                Paragraph(f"<font name='DengB' color='#1E3A8A'>{name}</font>", styles["cell"]),
                Paragraph(desc, styles["cell"]),
            ]
        )
    layer_table = Table(
        rows,
        colWidths=[30 * mm, CONTENT_W - 30 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        ),
    )
    story.append(layer_table)
    story.append(
        Paragraph(
            "目标架构升级：国际贸易数据层（关税税率库 / 汇率行情 / 政策公告 NLP / 物流运价 / 专利商标 / 法规合规）→ 分析内核 → 综合决策报告，详见 05 参赛大纲。",
            styles["note"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("数据层", styles["h2"]))
    data_bullets = [
        "采集：Collector 注册式框架，支持 Amazon Best Sellers 抓取与海关出口统计扩展。",
        "清洗：统一 Schema、去重、枚举校验、缺失值填充，输出 clean_data.csv 与 SQLite。",
        f"演示数据：2 年周粒度，{len(CATEGORIES)} 大品类（{CATEGORY_NAMES}）× "
        f"{len(MARKETS)} 大市场（{MARKET_NAMES}），共 {HISTORY_ROWS} 行。",
    ]
    for b in data_bullets:
        story.append(Paragraph("•  " + b, styles["bullet"]))

    story.append(Paragraph("算法层", styles["h2"]))
    algo_bullets = [
        "特征工程：销量滞后 1/2/4/8 周、4/8 周滚动均值、增长率、搜索/价格/竞争度趋势、月周季节性编码。",
        "Prophet 基线：周/年季节性，对数变换提升稳定性，输出 90 天日粒度预测与 80% 区间。",
        "LightGBM 进阶：20 个特征回归，滚动递归多步预测，训练残差估计置信区间。",
        "推荐引擎：综合评分 = 0.35×预测增长 + 0.30×搜索趋势 + 0.25×(100−竞争度) + 0.10×评论增长。",
    ]
    for b in algo_bullets:
        story.append(Paragraph("•  " + b, styles["bullet"]))

    story.append(Paragraph("展示层", styles["h2"]))
    view_bullets = [
        "多源热度趋势：销量、搜索热度、出口金额归一化叠加对比。",
        "未来 90 天预测：历史销量 + 预测曲线 + 置信区间，支持双模型切换。",
        "选品推荐：Top 10 榜单、综合评分、推荐理由。",
        "市场对比：近 12 周销量、竞争度与价格对比。",
    ]
    for b in view_bullets:
        story.append(Paragraph("•  " + b, styles["bullet"]))
    story.append(PageBreak())
    return story


def _section_impl_result(styles: dict, shot_w: float, shot_h: float) -> list:
    story = []
    story.append(Paragraph("03  已实现内容：工程结构与验证结果", styles["h1"]))

    story.append(Paragraph("工程结构", styles["h2"]))
    tree_lines = [
        "src/                 核心包（config / data / features / models / trade / api / app）",
        "scripts/             一键脚本（生成数据 / 训练 / 完整流水线 / 看板验收 / API 启动）",
        "data/                原始数据、清洗数据、演示数据",
        "models/              模型产物、预测、推荐、评估报告",
        "docs/                商业计划书、技术文档、数据字典、路演大纲",
        "tests/               自动化测试（数据管道 / 模型 / 推荐 / 贸易决策）",
    ]
    for line in tree_lines:
        story.append(Paragraph(line, styles["bullet"]))

    story.append(Paragraph("验证结果", styles["h2"]))
    metrics = _load_metrics()
    baseline_mape = round(
        sum(m["mape"] for m in metrics["baseline"] if m["mape"] == m["mape"]) / len(metrics["baseline"]), 2
    )
    advanced_mape = round(
        sum(m["mape"] for m in metrics["advanced"] if m["mape"] == m["mape"]) / len(metrics["advanced"]), 2
    )
    improvement = round((baseline_mape - advanced_mape) / baseline_mape * 100)

    metric_rows = [
        ["自动化测试", "106 / 106 通过"],
        ["基线模型 MAPE", f"{baseline_mape:.2f}%"],
        ["进阶模型 MAPE", f"{advanced_mape:.2f}%（相对提升 {improvement}%）"],
        ["预测记录", f"{FORECAST_ROWS} 行（{COMBO_COUNT} 组合 × 90 天 × 2 模型）"],
    ]
    mt = Table(
        [[Paragraph(a, styles["cell"]), Paragraph(b, styles["cell"])] for a, b in metric_rows],
        colWidths=[60 * mm, CONTENT_W - 60 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        ),
    )
    story.append(mt)
    story.append(Spacer(1, 8))

    story.append(Paragraph("推荐 Top 3（演示数据）", styles["h2"]))
    recs = _load_recommendations(3)
    rec_header = [Paragraph("排名", styles["cell_head"]), Paragraph("品类", styles["cell_head"]),
                  Paragraph("市场", styles["cell_head"]), Paragraph("综合评分", styles["cell_head"]),
                  Paragraph("预测增长", styles["cell_head"]), Paragraph("推荐理由", styles["cell_head"])]
    rec_rows = [rec_header]
    name_map = {code: category_name(code) for code in CATEGORIES}
    market_map = {code: market_name(code) for code in MARKETS}
    for r in recs:
        rec_rows.append(
            [
                Paragraph(str(r["rank"]), styles["cell"]),
                Paragraph(name_map.get(r["category"], r["category"]), styles["cell"]),
                Paragraph(market_map.get(r["market"], r["market"]), styles["cell"]),
                Paragraph(str(r["score"]), styles["cell"]),
                Paragraph(f"{r['forecast_growth']}%", styles["cell"]),
                Paragraph(r["reasons"], styles["cell"]),
            ]
        )
    rec_table = Table(
        rec_rows,
        colWidths=[14 * mm, 30 * mm, 24 * mm, 24 * mm, 24 * mm, CONTENT_W - 116 * mm],
        repeatRows=1,
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]
        ),
    )
    story.append(rec_table)

    story.append(Paragraph("看板运行效果", styles["h2"]))
    avail_h = PAGE_H - MARGIN_T - MARGIN_B - 40
    max_w = CONTENT_W
    ratio = min(max_w / shot_w, avail_h / shot_h)
    img_w = shot_w * ratio
    img_h = shot_h * ratio
    img = RLImage(str(SHOT_PATH), width=img_w, height=img_h)
    img.hAlign = "CENTER"
    story.append(img)
    story.append(PageBreak())
    return story


def _section_outline_business(styles: dict) -> list:
    story = []
    story.append(Paragraph("04  参赛大纲：商业计划书与路演", styles["h1"]))

    story.append(Paragraph("项目定位", styles["h2"]))
    positioning = [
        ["项目名称", "基于多源数据融合的跨境电商智能选品决策系统"],
        ["升级定位", "跨境贸易决策智能（Trade Intelligence）：以选品为入口，政策、成本与风险为护城河"],
        ["核心主线", "政策变化快于人工跟踪 → 到岸成本与合规风险成为利润关键 → AI 实时测算与决策建议"],
        ["参赛赛道", "中国国际大学生创新大赛 · 高教赛道 · 创意组 · 国际贸易 × AI 数据"],
    ]
    story.append(_styled_table(styles, positioning, [40 * mm, CONTENT_W - 40 * mm], header_row=False, first_col_bg=True))
    story.append(Spacer(1, 8))

    story.append(Paragraph("商业计划书大纲（十章）", styles["h2"]))
    bp_items = [
        ("一、项目概述", "项目名称、参赛赛道、Trade Intelligence 定位与核心判断", "一句话定位、核心判断、名词口径"),
        ("二、市场分析", "2025 年跨境电商 2.75 万亿元、增长 69.7%、企业超 12 万家；美国取消 de minimis、欧盟 2026 年征税", "政策背景时间线、市场规模推导链、目标用户画像"),
        ("三、产品与服务", "关税 / 政策风险引擎、财务贸易成本模型、多源选品预测、合规准入、知识产权、物流、多语言舆情、供应链金融、绿色贸易", "模块优先级、核心功能清单、商业模式"),
        ("四、数据与技术", "官方 API + 公开政策库（CBP / TARIC / USPTO / EUIPO）、NLP 政策解析、双模型预测、冲突裁决（置信度 × 权重）", "数据来源表、更新频率、算法方法论"),
        ("五、竞争分析", "卖家精灵、Jungle Scout 等竞品对比", "差异化矩阵、政策 / 成本 / 风险维度"),
        ("六、商业模式", "SaaS 订阅 + 企业定制 + 数据报告，远期数据服务 / 供应链金融分润", "定价结构、客户生命周期、收入模型"),
        ("七、财务预估", "订阅收入模型、成本结构与种子用户验证", "访谈数量与结论、试用反馈、付费意愿问卷"),
        ("八、风险与对策", "政策数据、模型精度、合规门槛、时间规划", "风险矩阵、应对策略、优先级排序"),
        ("九、团队介绍", "数据、算法、产品、商业四类角色 + 国际贸易背景成员 / 顾问", "团队分工表、顾问证明"),
        ("十、实施路径", "MVP → 一期（政策风险 + 贸易成本）→ 二期（合规 / IP / 物流 / 舆情）→ 远期（供应链金融 / 绿色贸易）", "Roadmap、里程碑、验收标准"),
    ]
    story.append(
        _styled_table(
            styles,
            [["章节", "核心内容", "关键论证 / 交付点"]] + bp_items,
            [26 * mm, 92 * mm, 60 * mm],
            header_row=True,
            first_col_bg=False,
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("路演大纲（10 分钟）", styles["h2"]))
    pitch_items = [
        ("1 分钟", "开场", "一句话说清项目：AI 实时跟踪国际贸易政策与成本，替卖家做“卖什么、怎么卖、卖到哪”的决策", "看板首页 / 一句话金句"),
        ("2 分钟", "痛点与机会", "美国取消 de minimis、欧盟 2026 年征税，政策变化快于人工；2025 年跨境电商 2.75 万亿元、增长 69.7%", "政策时间线 / 市场规模数据"),
        ("4 分钟", "产品 Demo", "选品看板、90 天预测、Top 10 推荐；关税 / 政策风险引擎；贸易成本测算；市场准入与知识产权筛查", "看板实机 / 风险引擎模拟"),
        ("1 分钟", "对照组：顶级 AI 的边界", "同一份 92 周数据 + 统一提示词测试 ChatGPT / Claude / Gemini / DeepSeek；通用 AI 在预测完整率、数字可追溯、置信区间、复现性上有缺口", "docs/对照组分析报告.md / output/pdf/顶级AI对照组分析报告.pdf"),
        ("2 分钟", "技术亮点", "国际贸易数据层 + 分析内核两层架构、双模型（MAPE 3.1%）、冲突裁决（置信度 × 权重）", "架构图 / MAPE 对比表"),
        ("1 分钟", "商业模式与团队", "SaaS + 企业定制 + 数据报告；团队补充国际贸易背景成员", "商业模式图 / 团队分工"),
        ("30 秒", "结尾", "政策变化快于人工跟踪，数据替卖家做更难、更及时的决定", "收束金句"),
    ]
    story.append(
        _styled_table(
            styles,
            [["时长", "环节", "讲述要点", "演示 / 素材"]] + pitch_items,
            [18 * mm, 30 * mm, 90 * mm, 40 * mm],
            header_row=True,
            first_col_bg=False,
        )
    )
    story.append(Paragraph("注：合计约 11.5 分钟，现场可按需将 Demo 压缩至 3 分钟，或把对照组并入技术亮点。", styles["note"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("答辩 Q&A 准备要点", styles["h2"]))
    qa_items = [
        ("数据真实性", "当前为合成演示数据，已规划官方 API 与公开政策库接入", "Amazon SP-API、Shopee Open Platform、CBP、TARIC、USPTO；更新频率已写入数据字典"),
        ("模型可解释性", "推荐理由由规则 + 预测生成；冲突裁决给出置信度与权重来源", "综合评分公式、置信度 × 权重规则、矛盾案例"),
        ("与竞品差异", "从“选品查询工具”升级为“贸易决策智能”", "政策、成本、风险一体化决策矩阵"),
        ("落地优先级", "先做关税 / 政策风险引擎与财务贸易成本模型", "Roadmap 一期 / 二期 / 远期"),
        ("对照组结论", "通用 AI 擅长描述洞察，但在预测完整率、数字可追溯、置信区间与复现性上存在缺口", "对照组分析报告（结论待回填）"),
    ]
    story.append(
        _styled_table(
            styles,
            [["问题方向", "回答口径", "证据 / 依据"]] + qa_items,
            [32 * mm, 78 * mm, 68 * mm],
            header_row=True,
            first_col_bg=False,
        )
    )
    story.append(PageBreak())
    return story


def _section_outline_tech(styles: dict) -> list:
    story = []
    story.append(Paragraph("05  参赛大纲：技术文档与数据字典概要", styles["h1"]))

    story.append(Paragraph("技术文档大纲", styles["h2"]))
    tech_items = [
        ("1. 系统架构", "两层架构：国际贸易数据层 → 分析内核（四大脑）→ 综合决策报告", "架构图、数据流、模块边界"),
        ("2. 数据管道", "官方 API + 公开政策库 + 统一清洗 + SQLite 存储；政策公告按日更新", "CBP / TARIC / USPTO / EUIPO、更新频率"),
        ("3. 特征工程", "滞后、滚动、趋势、季节性特征；规划加入关税政策与汇率事件特征", "20 维特征列、事件特征清单"),
        ("4. 预测模型", "Prophet 基线（对数变换）+ LightGBM 进阶（滚动递归）", "MAPE 3.1%、置信区间方法"),
        ("5. 推荐与裁决", "综合评分公式 + 冲突裁决（置信度 × 决策权重）", "评分权重、矛盾案例、可解释理由"),
                ("6. 评估结果", "MAPE / MAE、双模型对比、自动化测试", f"自动化测试通过、{FORECAST_ROWS} 行预测记录"),
        ("7. 贸易决策模块", "关税 / 政策风险、财务贸易成本、合规准入、知识产权、物流、多语言舆情、绿色贸易、数据信用、冲突裁决", "模块清单、数据来源、输出物"),
        ("8. API 与扩展建议", "FastAPI 演示服务已实现，后续接入真实数据、HS 编码映射、外部事件特征、定时更新", "trade/decision、trade/report、recommendations、policy/events"),
    ]
    story.append(
        _styled_table(
            styles,
            [["章节", "核心内容", "关键方法 / 数据来源"]] + tech_items,
            [32 * mm, 94 * mm, 52 * mm],
            header_row=True,
            first_col_bg=False,
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("数据字典概要", styles["h2"]))
    schema_rows = [
        ["字段", "类型", "说明"],
        ["date", "date", "周粒度日期（每周五）"],
        ["category", "str", "品类编码：home / pet / fitness / small_appliance / outdoor"],
        ["market", "str", "市场编码：us / eu / sea"],
        ["search_index", "float", "搜索热度（0-100）"],
        ["bestseller_rank", "float", "畅销排名（越小越畅销）"],
        ["price_median", "float", "价格中位数（美元）"],
        ["review_growth", "float", "评论周增长率（%）"],
        ["export_value", "float", "出口金额（万美元）"],
        ["competition_index", "float", "竞争度（0-100）"],
        ["sales_volume", "float", "周销量指数（目标变量）"],
    ]
    story.append(
        _styled_table(
            styles,
            schema_rows,
            [38 * mm, 22 * mm, CONTENT_W - 60 * mm],
            header_row=True,
            first_col_bg=False,
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("特征工程字段", styles["h3"]))
    feature_rows = [
        ["特征", "说明"],
        ["lag_1/2/4/8", "销量滞后 1/2/4/8 周"],
        ["rolling_mean_4/8", "销量 4/8 周滚动均值"],
        ["growth_rate_4", "销量 4 周增长率（%）"],
        ["search_trend_4", "搜索热度 4 周变化率（%）"],
        ["competition_change_4", "竞争度 4 周变化"],
        ["price_change_4", "价格 4 周变化率（%）"],
        ["month_sin/cos", "月份季节性特征"],
        ["week_sin/cos", "周数季节性特征"],
    ]
    story.append(
        _styled_table(
            styles,
            feature_rows,
            [60 * mm, CONTENT_W - 60 * mm],
            header_row=True,
            first_col_bg=False,
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("贸易决策模块（演示版已实现）", styles["h3"]))
    trade_rows = [
        ["字段", "类型", "说明"],
        ["tariff_rate", "float", "目标国关税税率（%），来源 CBP / TARIC"],
        ["policy_effective_date", "date", "政策生效日期，NLP 解析政策公告得到"],
        ["policy_risk_level", "int", "政策突变风险等级（0-5）"],
        ["exchange_rate", "float", "人民币兑目标币种汇率（日 / 周更新）"],
        ["payment_fee_rate", "float", "支付通道费率（%）"],
        ["logistics_cost", "float", "单件物流成本（小包 / 海运 / 海外仓）"],
        ["freight_index", "float", "SCFI 风格运价指数（当前 + 4 周预测）"],
        ["compliance_cost", "float", "认证与合规成本（美元）"],
        ["sentiment_score", "float", "多语言舆情平均情绪分（-1 至 1）"],
        ["carbon_cost", "float", "CBAM 预估碳成本（美元 / 件）"],
        ["ip_risk_level", "str", "知识产权侵权风险等级（low / medium / high）"],
        ["data_coverage_score", "float", "数据信用经营数据覆盖度（0-100）"],
        ["completion_rate", "float", "数据信用订单履约率（%）"],
        ["return_rate", "float", "数据信用退款率（%）"],
        ["financing_ready_score", "float", "供应链金融融资就绪分（0-100）"],
        ["financing_level", "str", "建议融资档位：供应链金融 / 信用贷 / 小额试单 / 暂不建议"],
        ["conflict_level", "str", "多脑冲突裁决等级（low / medium / high）"],
        ["conflict_score_before", "float", "冲突裁决前综合得分（0-100）"],
        ["conflict_score_after", "float", "按置信度 × 权重计算的裁决后综合得分（0-100）"],
        ["conflict_decision", "str", "冲突裁决建议（风险优先 / 增长占优 / 小批量试单等）"],
    ]
    story.append(
        _styled_table(
            styles,
            trade_rows,
            [44 * mm, 24 * mm, CONTENT_W - 68 * mm],
            header_row=True,
            first_col_bg=False,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "演示产物：output/trade/trade_demo_report.md、trade_demo_metrics.json、trade_landed_cost.csv",
            styles["note"],
        )
    )
    story.append(PageBreak())
    return story


def _section_next_and_appendix(styles: dict) -> list:
    story = []
    story.append(Paragraph("06  下一步计划与附录", styles["h1"]))

    story.append(Paragraph("分阶段实施计划", styles["h2"]))
    plan_rows = [
        ["阶段", "目标", "关键任务", "验收口径"],
        ["MVP（已完成）", "多源选品预测 + 看板", "合成数据流水线、双模型、Top N 推荐", "106/106 测试通过、MAPE 3.3%"],
        ["一期（演示版已实现）", "关税 / 政策风险引擎 + 财务贸易成本模型", "政策事件库、到岸成本、汇率敏感性、支付比价、合规准入；后续接入 CBP / TARIC", "政策预警、成本测算可复现"],
        ["二期（合规 / IP / 物流 / 舆情演示版已实现）", "合规准入、知识产权、物流、多语言舆情", "法规合规库、USPTO / EUIPO 比对演示库、SCFI 风格运价预测、多语种情感演示库", "市场准入评分、侵权风险等级、物流时效预测、情绪分"],
        ["远期", "数据信用与供应链金融（融资就绪演示版已实现）、绿色贸易（CBAM 趋势演示版已实现）", "授权经营数据接入与授信模型、CBAM 碳排因子库", "融资就绪评分、数据服务 / 分润模式、趋势页"],
    ]
    story.append(
        _styled_table(
            styles,
            plan_rows,
            [28 * mm, 48 * mm, 66 * mm, 36 * mm],
            header_row=True,
            first_col_bg=False,
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("附录：关键交付物清单", styles["h2"]))
    files = [
        ["交付物", "说明"],
        ["src/", "数据、特征、模型、看板、贸易决策、FastAPI 与流水线核心代码"],
        ["src/api/", "FastAPI 演示服务（/api/trade/decision、/api/trade/report 等）"],
        ["scripts/", "一键生成数据 / 训练 / 完整流水线 / 看板验收 / API 启动脚本"],
        ["data/", "演示与清洗数据（demo_market_data.csv / clean_data.csv / SQLite）"],
        ["models/", "metrics.json / forecast.csv / recommendations.csv"],
        ["docs/", "商业计划书、技术文档、数据字典、路演大纲、对照组分析报告"],
        ["output/trade/", "贸易决策演示报告（政策风险 / 到岸成本 / 市场准入 / 数据信用）"],
        ["tests/", "106 个自动化测试（数据管道 / 模型 / 推荐 / 贸易决策 / 冲突裁决 / API）"],
        ["app.py", "看板入口（streamlit run app.py）"],
    ]
    story.append(
        _styled_table(
            styles,
            files,
            [40 * mm, CONTENT_W - 40 * mm],
            header_row=True,
            first_col_bg=False,
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "本 PDF 为项目展示材料，完整代码、文档与数据见工作区 E:\\大创。",
            styles["note"],
        )
    )
    return story


def main() -> None:
    styles = _styles()
    shot_w, shot_h = _load_image_size()
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="跨境电商智能选品决策系统 - 已实现内容与参赛大纲",
        author="大创项目团队",
    )
    story: list = []
    story += _cover(styles)
    story += _toc(styles)
    story += _section_overview(styles)
    story += _section_implemented_arch(styles)
    story += _section_impl_result(styles, shot_w, shot_h)
    story += _section_outline_business(styles)
    story += _section_outline_tech(styles)
    story += _section_next_and_appendix(styles)
    doc.build(story, onFirstPage=_make_header_footer(), onLaterPages=_make_header_footer())
    print("PDF generated:", OUT_PDF)


if __name__ == "__main__":
    main()
