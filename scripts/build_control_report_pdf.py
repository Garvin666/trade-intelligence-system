"""生成《顶级 AI 对照组分析报告》PDF（reportlab + 中文字体）。"""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = Path(r"C:\Windows\Fonts")
MD_PATH = PROJECT_ROOT / "docs" / "对照组分析报告.md"
OUT_DIR = PROJECT_ROOT / "output" / "pdf"
OUT_PDF = OUT_DIR / "顶级AI对照组分析报告.pdf"

pdfmetrics.registerFont(TTFont("SimHei", str(FONT_DIR / "simhei.ttf")))
pdfmetrics.registerFont(TTFont("Deng", str(FONT_DIR / "Deng.ttf")))
pdfmetrics.registerFont(TTFont("DengB", str(FONT_DIR / "Dengb.ttf")))

NAVY = colors.HexColor("#1E3A8A")
BLUE = colors.HexColor("#2563EB")
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


def _styles() -> dict:
    return {
        "cover_title": ParagraphStyle(
            "cover_title", fontName="SimHei", fontSize=24, leading=32, textColor=NAVY,
            alignment=TA_CENTER, spaceAfter=10,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", fontName="DengB", fontSize=13, leading=20, textColor=MUTED,
            alignment=TA_CENTER, spaceAfter=6,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta", fontName="Deng", fontSize=10.5, leading=17, textColor=TEXT,
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "h1", fontName="SimHei", fontSize=15, leading=21, textColor=NAVY,
            spaceBefore=10, spaceAfter=7, keepWithNext=1,
        ),
        "h2": ParagraphStyle(
            "h2", fontName="DengB", fontSize=12, leading=17, textColor=BLUE,
            spaceBefore=8, spaceAfter=5, keepWithNext=1,
        ),
        "body": ParagraphStyle(
            "body", fontName="Deng", fontSize=10.2, leading=15.8, textColor=TEXT,
            spaceAfter=4, alignment=TA_LEFT,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName="Deng", fontSize=10.2, leading=15.8, textColor=TEXT,
            leftIndent=10, spaceAfter=3,
        ),
        "note": ParagraphStyle(
            "note", fontName="Deng", fontSize=9, leading=13.5, textColor=MUTED,
            leftIndent=6, spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "code", fontName="Deng", fontSize=9.5, leading=14.5, textColor=TEXT,
            leftIndent=4, spaceAfter=0,
        ),
        "cell": ParagraphStyle(
            "cell", fontName="Deng", fontSize=8.8, leading=12.6, textColor=TEXT,
        ),
        "cell_head": ParagraphStyle(
            "cell_head", fontName="DengB", fontSize=9, leading=12.8, textColor=colors.white,
        ),
    }


def _inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`([^`]+)`", r"\1", text)


def _parse_table(lines: list[str]) -> tuple[Table, int] | None:
    rows: list[list[str]] = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells):
            continue
        rows.append(cells)
    if not rows:
        return None
    n_cols = max(len(r) for r in rows)
    col_w = CONTENT_W / n_cols
    data = [
        [Paragraph(_inline(cell), _styles()["cell_head"] if i == 0 else _styles()["cell"]) for cell in row]
        for i, row in enumerate(rows)
    ]
    table = Table(
        data,
        colWidths=[col_w] * n_cols,
        repeatRows=1,
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        ),
    )
    return table, len(lines)


def _cover(styles: dict) -> list:
    story = []
    story.append(Spacer(1, 70))
    story.append(Table(
        [[Paragraph("中国国际大学生创新大赛 · 高教赛道 · 创意组", styles["cover_sub"])]],
        colWidths=[CONTENT_W],
        style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]),
    ))
    story.append(Spacer(1, 26))
    story.append(Table(
        [[Paragraph("顶级 AI 对照组分析报告", styles["cover_title"])]],
        colWidths=[CONTENT_W],
        style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]),
    ))
    story.append(Spacer(1, 10))
    story.append(Table(
        [[Paragraph("跨境电商智能选品决策系统 · 现有顶级 AI 数据分析能力与问题", styles["cover_sub"])]],
        colWidths=[CONTENT_W],
        style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]),
    ))
    story.append(Spacer(1, 18))
    story.append(Table(
        [[""]], colWidths=[CONTENT_W], rowHeights=[3],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BLUE),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]),
    ))
    story.append(Spacer(1, 24))
    for line in [
        "同一份训练数据 · 同一套提示词 · 同一评分口径",
        "ChatGPT / Claude / Gemini / DeepSeek",
        "2026-08-04 · 方法版 v1",
    ]:
        story.append(Table(
            [[Paragraph(line, styles["cover_meta"])]],
            colWidths=[CONTENT_W],
            style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]),
        ))
        story.append(Spacer(1, 6))
    story.append(PageBreak())
    return story


def _build_story(md_text: str, styles: dict) -> list:
    story = _cover(styles)
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("|"):
            j = i
            block: list[str] = []
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                block.append(lines[j])
                j += 1
            parsed = _parse_table(block)
            if parsed:
                table, _n = parsed
                story.append(Spacer(1, 3))
                story.append(table)
                story.append(Spacer(1, 5))
            i = j
            continue
        if line.startswith("```"):
            j = i + 1
            code_lines: list[str] = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                code_lines.append(lines[j])
                j += 1
            code_block = Table(
                [[Paragraph("<br/>".join(_inline(c) for c in code_lines), styles["code"])]],
                colWidths=[CONTENT_W],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ]
                ),
            )
            story.append(code_block)
            story.append(Spacer(1, 5))
            i = j + 1
            continue
        if line.startswith(">"):
            story.append(Paragraph(_inline(line.lstrip("> ")), styles["note"]))
            i += 1
            continue
        if line.startswith("### "):
            story.append(Paragraph(_inline(line[4:]), styles["h2"]))
            i += 1
            continue
        if line.startswith("## "):
            story.append(Paragraph(_inline(line[3:]), styles["h1"]))
            i += 1
            continue
        if line.startswith("# "):
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", line):
            story.append(Paragraph(_inline(re.sub(r"^\s*[-*]\s+", "", line)), styles["bullet"]))
            i += 1
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            story.append(Paragraph(_inline(re.sub(r"^\s*(\d+\.)\s+", r"\1 ", line)), styles["bullet"]))
            i += 1
            continue
        story.append(Paragraph(_inline(line), styles["body"]))
        i += 1
    return story


def _make_header_footer():
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN_L, PAGE_H - 14 * mm, PAGE_W - MARGIN_R, PAGE_H - 14 * mm)
        canvas.setFont("Deng", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN_L, PAGE_H - 12 * mm, "跨境电商智能选品决策系统")
        canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 12 * mm, "顶级 AI 对照组")
        canvas.setFont("Deng", 8)
        canvas.drawCentredString(PAGE_W / 2, 11 * mm, f"第 {doc.page} 页")
        canvas.restoreState()
    return draw


def main() -> None:
    if not MD_PATH.exists():
        raise FileNotFoundError(f"缺少报告文件 {MD_PATH}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="顶级 AI 对照组分析报告",
        author="跨境电商智能选品决策系统",
    )
    story = _build_story(MD_PATH.read_text(encoding="utf-8"), _styles())
    doc.build(story, onFirstPage=_make_header_footer(), onLaterPages=_make_header_footer())
    print(f"PDF 已生成：{OUT_PDF}")


if __name__ == "__main__":
    main()
