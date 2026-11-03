"""把《商业计划书》Markdown 源文档转换为 PDF（reportlab，浅色编辑部风格，符合商业计划书规范）。

规范要点：
1. 封面（项目名、定位、赛道、日期）
2. 目录带页码（TableOfContents + multiBuild 两遍构建）
3. 页眉（当前章节名 + 项目名）+ 页脚页码
4. 表题在表格上方（表 x-x 加粗居中）、图题在图片下方
5. 标题层级 h1（章）/ h2（节）/ h3

用法：
    .venv\\Scripts\\python scripts\\build_business_plan_pdf.py
    或指定源文件参数。

支持语法：标题（#/##/###）、表格（| 分隔）、图片（![说明](路径)）、
引用块（> 表注/说明）、无序列表（- ）、加粗（**文本**）与普通段落。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable, HRFlowable
from reportlab.platypus.tableofcontents import TableOfContents

FONT_DIR = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("SimHei", str(FONT_DIR / "simhei.ttf")))
pdfmetrics.registerFont(TTFont("Deng", str(FONT_DIR / "Deng.ttf")))
pdfmetrics.registerFont(TTFont("DengB", str(FONT_DIR / "Dengb.ttf")))

INK = colors.HexColor("#1F2937")
SLATE = colors.HexColor("#5B6470")
TEAL = colors.HexColor("#0F766E")
TEAL_DARK = colors.HexColor("#115E59")
LINE = colors.HexColor("#DCE8E4")
MINT = colors.HexColor("#F0F9F6")
WHITE = colors.white
GOLD = colors.HexColor("#B45309")

PAGE_W, PAGE_H = A4
MARGIN_L = 14 * mm
MARGIN_R = 14 * mm
MARGIN_T = 19 * mm
MARGIN_B = 15 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R
PROJECT_TITLE = "跨境电商智能选品决策系统 · 商业计划书"


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Normal"], fontName="SimHei", fontSize=27, leading=36,
            textColor=INK, alignment=TA_CENTER, spaceAfter=8, wordWrap="CJK",
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontName="DengB", fontSize=13, leading=20,
            textColor=TEAL, alignment=TA_CENTER, spaceAfter=5, wordWrap="CJK",
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta", parent=base["Normal"], fontName="Deng", fontSize=10.5, leading=17,
            textColor=SLATE, alignment=TA_CENTER, spaceAfter=3, wordWrap="CJK",
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Normal"], fontName="SimHei", fontSize=15, leading=21,
            textColor=INK, spaceBefore=5, spaceAfter=6, wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Normal"], fontName="SimHei", fontSize=11.5, leading=16,
            textColor=TEAL_DARK, spaceBefore=7, spaceAfter=3, wordWrap="CJK",
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Normal"], fontName="DengB", fontSize=10, leading=14,
            textColor=INK, spaceBefore=5, spaceAfter=3, wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Deng", fontSize=9.5, leading=14,
            textColor=INK, spaceAfter=4, wordWrap="CJK",
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Deng", fontSize=9.5, leading=14,
            textColor=INK, leftIndent=10, spaceAfter=2, wordWrap="CJK",
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"], fontName="Deng", fontSize=8.5, leading=12.5,
            textColor=SLATE, spaceBefore=2, spaceAfter=5, wordWrap="CJK",
        ),
        "table_title": ParagraphStyle(
            "table_title", parent=base["Normal"], fontName="DengB", fontSize=8.5, leading=12.5,
            textColor=INK, alignment=TA_CENTER, spaceBefore=3, spaceAfter=2, wordWrap="CJK",
        ),
        "note": ParagraphStyle(
            "note", parent=base["Normal"], fontName="Deng", fontSize=8.5, leading=13,
            textColor=GOLD, leftIndent=8, spaceAfter=4, wordWrap="CJK",
        ),
        "toc": ParagraphStyle(
            "toc", parent=base["Normal"], fontName="Deng", fontSize=10, leading=18,
            textColor=INK, spaceAfter=1, wordWrap="CJK",
        ),
        "toc_sub": ParagraphStyle(
            "toc_sub", parent=base["Normal"], fontName="Deng", fontSize=9.5, leading=16,
            textColor=SLATE, leftIndent=14, spaceAfter=0, wordWrap="CJK",
        ),
    }


def _escape(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return text


def _img_size(path: Path) -> tuple[float, float]:
    from PIL import Image as PILImage

    with PILImage.open(path) as im:
        w, h = im.size
    return w, h


class SectionHeader(Flowable):
    """Full-width chapter band with a gold accent."""

    def __init__(self, text: str, width: float) -> None:
        super().__init__()
        self.text = text
        self._width = width
        self.height = 8.5 * mm

    def wrap(self, avail_width: float, _avail_height: float) -> tuple[float, float]:
        self._width = avail_width
        return (avail_width, self.height)

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        c.setFillColor(TEAL)
        c.rect(0, 0, self._width, self.height, stroke=0, fill=1)
        c.setFillColor(GOLD)
        c.rect(0, 0, 2 * mm, self.height, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont("SimHei", 13)
        c.drawString(5 * mm, 2.4 * mm, self.text)
        c.restoreState()

    def getPlainText(self) -> str:
        return self.text


def build_pdf(md_path: Path, out_path: Path, fig_roots: list[Path]) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    st = _styles()
    chapter_pages: dict[str, int] = {}
    chapter_order: list[str] = []

    class _DocT(SimpleDocTemplate):
        def afterFlowable(self, flowable):  # noqa: N802 (reportlab 钩子命名)
            nonlocal chapter_pages
            if isinstance(flowable, SectionHeader):
                text = flowable.getPlainText()
                if text not in ("目录",):
                    self.notify("TOCEntry", (0, text, self.page))
                    chapter_pages[text] = self.page
            elif isinstance(flowable, Paragraph):
                style = flowable.style.name
                text = flowable.getPlainText()
                if style == "h1" and text not in ("目录",):
                    self.notify("TOCEntry", (0, text, self.page))
                    chapter_pages[text] = self.page
                elif style == "h2":
                    self.notify("TOCEntry", (1, text, self.page))

    doc = _DocT(
        str(out_path), pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title="商业计划书-跨境电商智能选品决策系统",
        author="跨境电商智能选品决策系统项目组",
    )

    def on_page(canvas, _doc):
        canvas.saveState()
        page_no = canvas.getPageNumber()
        if page_no == 1:
            canvas.setFillColor(TEAL)
            canvas.rect(0, PAGE_H - 15 * mm, PAGE_W, 15 * mm, stroke=0, fill=1)
            canvas.setFillColor(GOLD)
            canvas.rect(0, PAGE_H - 15.8 * mm, PAGE_W, 0.8 * mm, stroke=0, fill=1)
            canvas.setFillColor(TEAL_DARK)
            canvas.rect(0, 0, PAGE_W, 9 * mm, stroke=0, fill=1)
            canvas.setFillColor(GOLD)
            canvas.rect(0, 9 * mm, PAGE_W, 0.6 * mm, stroke=0, fill=1)
            canvas.setFillColor(WHITE)
            canvas.setFont("Deng", 7)
            canvas.drawCentredString(
                PAGE_W / 2, 4 * mm,
                "MULTI-SOURCE DATA · TRADE INTELLIGENCE · REPRODUCIBLE",
            )
            canvas.restoreState()
            return
        # 页眉
        current = "封面"
        for ch in chapter_order:
            if page_no >= chapter_pages.get(ch, 10**9):
                current = ch
        canvas.setFont("Deng", 7.5)
        canvas.setFillColor(SLATE)
        canvas.drawString(MARGIN_L, PAGE_H - 10 * mm, current)
        canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 10 * mm, PROJECT_TITLE)
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN_L, PAGE_H - 11.5 * mm, PAGE_W - MARGIN_R, PAGE_H - 11.5 * mm)
        # 页脚
        canvas.setStrokeColor(TEAL)
        canvas.setLineWidth(0.8)
        canvas.line(MARGIN_L, 13 * mm, PAGE_W - MARGIN_R, 13 * mm)
        canvas.setFillColor(TEAL)
        canvas.setFont("DengB", 8)
        canvas.drawCentredString(PAGE_W / 2, 9.5 * mm, str(page_no))
        canvas.restoreState()

    story: list = []
    cover_done = False
    toc_done = False
    in_toc = False
    body_started = False
    i = 0
    n = len(lines)

    def add_table(rows: list[list[str]]):
        data = [[_escape(c) for c in r] for r in rows]
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TEAL),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "DengB"),
            ("FONTNAME", (0, 1), (-1, -1), "Deng"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.2),
            ("LEADING", (0, 0), (-1, -1), 11),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, MINT]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("LINEBELOW", (0, 0), (-1, 0), 0.9, GOLD),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 3))

    while i < n:
        raw = lines[i]
        line = raw.rstrip()
        if not line.strip():
            i += 1
            continue

        # 封面
        if not cover_done and line.startswith("# "):
            story.append(Spacer(1, 52 * mm))
            story.append(Paragraph(_escape(line[2:].strip()), st["cover_title"]))
            j = i + 1
            while j < n:
                l2 = lines[j].strip()
                if not l2:
                    j += 1
                    continue
                if l2.startswith("#"):
                    break
                if l2.startswith("**") and l2.endswith("**"):
                    story.append(Paragraph(_escape(l2), st["cover_sub"]))
                elif l2 == "---":
                    story.append(Spacer(1, 8 * mm))
                else:
                    story.append(Paragraph(_escape(l2), st["cover_meta"]))
                j += 1
            story.append(PageBreak())
            cover_done = True
            i = j
            continue

        # 目录
        if not toc_done and line.startswith("# 目录"):
            toc = TableOfContents()
            toc.levelStyles = [
                ParagraphStyle("TOC1", fontName="DengB", fontSize=11, leading=20, textColor=INK),
                ParagraphStyle("TOC2", fontName="Deng", fontSize=10, leading=17, textColor=SLATE, leftIndent=14),
            ]
            story.append(toc)
            in_toc = True
            i += 1
            continue
        if in_toc:
            # 目录条目由 TableOfContents 统一渲染（带页码），此处仅跳过源列表
            if line.startswith("# "):
                in_toc = False
                story.append(PageBreak())
                toc_done = True
                body_started = True
                continue
            i += 1
            continue

        if line.startswith("# "):
            if body_started:
                story.append(PageBreak())
            title = line[2:].strip()
            story.append(SectionHeader(title, CONTENT_W))
            chapter_pages[title] = 0  # 占位，afterFlowable 填充
            chapter_order.append(title)
            body_started = True
            i += 1
            continue
        if line.startswith("## "):
            story.append(Paragraph(_escape(line[3:].strip()), st["h2"]))
            story.append(HRFlowable(width=16 * mm, thickness=1.1, color=GOLD, spaceBefore=1, spaceAfter=4, hAlign="LEFT"))
            i += 1
            continue
        if line.startswith("### "):
            story.append(Paragraph(_escape(line[4:].strip()), st["h3"]))
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                add_table(rows)
            continue
        if line.startswith("![") and ("](bp_figs/" in line or "](new_figs/" in line):
            m = re.match(r"!\[(.*?)\]\((.*?)\)", line)
            if m:
                caption, rel = m.group(1), m.group(2)
                img_path = None
                for root in fig_roots:
                    cand = root / rel
                    if cand.exists():
                        img_path = cand
                        break
                if img_path:
                    try:
                        w, h = _img_size(img_path)
                        target_w = min(CONTENT_W - 8 * mm, w)
                        target_h = target_w * h / w
                        if target_h > 115 * mm:
                            target_h = 115 * mm
                            target_w = target_h * w / h
                        img = Image(str(img_path), width=target_w, height=target_h)
                        img.hAlign = "CENTER"
                        story.append(img)
                        story.append(Paragraph(f"<b>{_escape(caption)}</b>", st["caption"]))
                    except Exception as exc:  # pragma: no cover
                        story.append(Paragraph(f"[图片缺失: {rel}]", st["note"]))
                else:
                    story.append(Paragraph(f"[图片缺失: {rel}]", st["note"]))
            i += 1
            continue
        if line.startswith("> "):
            content = line[2:].strip()
            # 表题规范：表 x-x 的说明放在表格上方
            if re.match(r"^表\s*\d", content) and story and isinstance(story[-1], Table):
                tbl = story.pop()
                story.append(Paragraph(_escape(content), st["table_title"]))
                story.append(tbl)
                story.append(Spacer(1, 2))
            elif re.match(r"^表\s*\d", content) and story and isinstance(story[-1], Spacer) and len(story) >= 2 and isinstance(story[-2], Table):
                tbl = story.pop(-2)
                sp = story.pop()
                story.append(Paragraph(_escape(content), st["table_title"]))
                story.append(tbl)
                story.append(sp)
            else:
                story.append(Paragraph(_escape(content), st["note"]))
            i += 1
            continue
        if line == "---":
            story.append(Spacer(1, 4 * mm))
            i += 1
            continue
        if re.match(r"^[-•] ", line):
            story.append(Paragraph("• " + _escape(line[2:].strip()), st["bullet"]))
            i += 1
            continue

        story.append(Paragraph(_escape(line), st["body"]))
        i += 1

    doc.multiBuild(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {out_path}")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("用法: python scripts/build_business_plan_pdf.py <商业计划书.md>")
        return
    md = Path(args[0])
    if not md.is_absolute():
        md = root / md
    out = md.with_suffix(".pdf")
    fig_roots = [
        root / ".business" / "research",
        md.parent,
    ]
    build_pdf(md, out, fig_roots)


if __name__ == "__main__":
    main()
