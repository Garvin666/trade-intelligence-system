"""Generate the advisor-facing Word document for the project.

Run with a Python environment that has python-docx installed:
    python scripts/build_advisor_doc.py
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "导师交流材料_跨境电商智能选品决策系统.docx"
FIG_DIR = ROOT / "docs" / "figures"

COLOR_DARK = RGBColor(0x1F, 0x3A, 0x5F)
COLOR_GRAY = RGBColor(0x59, 0x59, 0x59)
COLOR_HEADER_BG = "DCE6F1"


def set_run_font(
    run,
    name: str,
    size: float | None = None,
    bold: bool | None = None,
    color=None,
) -> None:
    """Set font name (including East Asian font) and optional run props."""
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def set_style_font(style, name: str, size: float) -> None:
    """Set style font, including the East Asian font used by Word."""
    style.font.name = name
    style.font.size = Pt(size)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)


def para(
    doc: Document,
    text: str = "",
    size: float = 11,
    bold: bool = False,
    align=None,
    color=None,
    space_after: float = 6,
    space_before: float = 0,
    left_indent: float = 0,
    line_spacing: float = 1.5,
) -> None:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    pf.line_spacing = line_spacing
    if left_indent:
        pf.left_indent = Cm(left_indent)
    if align is not None:
        p.alignment = align
    if text:
        run = p.add_run(text)
        set_run_font(run, "宋体", size, bold, color)


def bullet(
    doc: Document,
    text: str,
    level: int = 0,
    size: float = 11,
) -> None:
    p = doc.add_paragraph(style="List Bullet")
    pf = p.paragraph_format
    pf.space_after = Pt(3)
    pf.line_spacing = 1.5
    pf.left_indent = Cm(0.75 + level * 0.6)
    run = p.add_run(text)
    set_run_font(run, "宋体", size, False)


def numbered(
    doc: Document,
    text: str,
    size: float = 11,
) -> None:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(3)
    pf.line_spacing = 1.5
    pf.left_indent = Cm(0.75)
    run = p.add_run(text)
    set_run_font(run, "宋体", size, False)


def heading(doc: Document, text: str, level: int = 1) -> None:
    h = doc.add_heading(text, level=level)
    sizes = {1: 16, 2: 13, 3: 11.5}
    for run in h.runs:
        set_run_font(run, "微软雅黑", sizes.get(level, 11.5), True, COLOR_DARK)
    h.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    h.paragraph_format.space_after = Pt(6)
    h.paragraph_format.line_spacing = 1.3


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_text(
    cell,
    text: str,
    bold: bool = False,
    size: float = 10,
    bg: str | None = None,
) -> None:
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.2
    run = p.add_run(str(text))
    set_run_font(run, "宋体", size, bold)
    if bg:
        shade_cell(cell, bg)


def add_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    widths: list[float] | None = None,
    size: float = 10,
) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for j, header in enumerate(headers):
        set_cell_text(table.rows[0].cells[j], header, bold=True, size=size, bg=COLOR_HEADER_BG)
    for row in rows:
        cells = table.add_row().cells
        for j, value in enumerate(row):
            set_cell_text(cells[j], value, size=size)
    if widths:
        for row in table.rows:
            for j, width in enumerate(widths):
                row.cells[j].width = Cm(width)


def add_image(doc: Document, filename: str, caption: str) -> None:
    path = FIG_DIR / filename
    if not path.exists():
        para(doc, f"图片缺失：{filename}", size=9, color=COLOR_GRAY, space_after=4)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(str(path), width=Cm(14.5))
    para(doc, caption, size=9, align=WD_ALIGN_PARAGRAPH.CENTER, color=COLOR_GRAY, space_after=10)


def code_block(doc: Document, lines: list[str]) -> None:
    for line in lines:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = Pt(0)
        pf.line_spacing = 1.15
        pf.left_indent = Cm(0.6)
        run = p.add_run(line)
        set_run_font(run, "Consolas", 9)


def add_page_number(doc: Document) -> None:
    footer = doc.sections[0].footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    fld_char_1 = OxmlElement("w:fldChar")
    fld_char_1.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = "PAGE"
    fld_char_2 = OxmlElement("w:fldChar")
    fld_char_2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char_1)
    run._r.append(instr_text)
    run._r.append(fld_char_2)
    set_run_font(run, "宋体", 9)


def build_document() -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

    set_style_font(doc.styles["Normal"], "宋体", 11)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.5
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)

    doc.core_properties.title = "导师交流与技术说明材料：跨境电商智能选品决策系统"
    doc.core_properties.author = "项目成员"
    doc.core_properties.subject = "跨境电商智能选品决策系统"

    # Cover
    para(doc, "", size=11, space_after=24)
    para(
        doc,
        "跨境电商智能选品决策系统",
        size=26,
        bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        color=COLOR_DARK,
        space_after=6,
    )
    para(
        doc,
        "导师交流与技术说明材料",
        size=16,
        bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        color=COLOR_GRAY,
        space_after=24,
    )
    para(
        doc,
        "项目全称：基于多源数据融合的跨境电商智能选品决策系统",
        size=12,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=4,
    )
    para(
        doc,
        "一句话定位：以选品为入口，用 AI 聚合多源数据，帮助中小跨境卖家回答卖什么、怎么卖、卖到哪、是否值得卖。",
        size=12,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=12,
    )
    para(
        doc,
        "编制日期：2026 年 8 月",
        size=12,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=4,
    )
    para(
        doc,
        "适用场景：导师阶段交流、答辩准备",
        size=12,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=4,
    )
    para(
        doc,
        "阅读建议：先看第二章的项目结论，再读第四章的技术讲解；遇到看不懂的术语翻第五章的字典。",
        size=11,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        color=COLOR_GRAY,
        space_after=4,
    )
    doc.add_page_break()

    # Manual table of contents
    heading(doc, "目录", 1)
    toc_lines = [
        "一、项目为什么存在",
        "二、项目大纲与当前进度",
        "三、整体思路：一句话讲清系统怎么工作",
        "四、技术实现讲解（小白友好）",
        "五、技术名词人话字典",
        "六、我的理解与收获",
        "七、展望与下一步",
        "八、当前项目的瑕疵与问题",
        "九、导师与答辩问答速查",
        "十、附录：常用数字、材料地图与运行命令",
    ]
    for line in toc_lines:
        para(doc, line, size=12, space_after=6, left_indent=0.3)
    doc.add_page_break()

    # 1. Why this project exists
    heading(doc, "一、项目为什么存在", 1)
    para(
        doc,
        "我是这个项目的学生成员，技术基础比较薄。这份材料把我目前能讲明白的部分整理出来，也让导师一眼看到项目做到了什么、下一步该往哪里走。",
    )

    heading(doc, "1.1 我们想解决的问题", 2)
    bullet(doc, "中小跨境卖家通常没有专职数据团队，选品、关税、汇率、合规、物流成本分散在多个平台，靠人工查表容易漏，试错成本高。")
    bullet(doc, "政策变化的速度超过人工能跟踪的速度。美国 2025 年取消 800 美元以下小额包裹免税，欧盟 2026 年 7 月 1 日起对 150 欧元以下低价值包裹征税。")
    bullet(doc, "行业规模已经足够大。2025 年中国跨境电商进出口 2.75 万亿元，较 2020 年增长 69.7%，企业超过 12 万家。数字来源见《数据分析报告》附录。")
    bullet(doc, "Temu 等平台已经用 AI 实时监测关税变化并自动调整，说明这个需求已经被市场验证。")
    add_image(
        doc,
        "policy_timeline.png",
        "政策时间线配图，来自 docs/figures/policy_timeline.png（《数据分析报告》）。",
    )

    heading(doc, "1.2 项目想做成什么", 2)
    para(doc, "项目定位是跨境贸易决策智能（Trade Intelligence）。选品只是入口，政策、成本与合规风险才是系统的重心。")
    bullet(doc, "目标用户：Amazon、速卖通、Shopee、Temu 的中小卖家，外贸选品团队，供应链企业与独立站运营者。")
    bullet(doc, "核心闭环：多源数据、趋势预测、选品推荐、贸易成本与风险测算、决策建议。")
    bullet(doc, "参赛赛道：中国国际大学生创新大赛，高教赛道，创意组。")
    doc.add_page_break()

    # 2. Outline and current progress
    heading(doc, "二、项目大纲与当前进度", 1)
    para(doc, "项目按四个阶段推进，前三个阶段已经能跑通完整演示。")
    add_table(
        doc,
        ["阶段", "状态", "主题", "主要内容"],
        [
            ["MVP", "已完成", "多源预测 + 看板", "数据、特征、双模型、推荐、看板"],
            ["一期", "已完成", "政策风险 + 贸易成本", "关税政策引擎、到岸成本、汇率敏感性"],
            ["二期", "已完成", "合规 / IP / 物流 / 舆情", "市场准入、知识产权、运价、多语言舆情、CBAM、融资、冲突裁决"],
            ["远期", "规划中", "真实数据 + 商业落地", "真实 Key 数据源、HS6 核实、完整对照组、供应链金融"],
        ],
        widths=[1.8, 1.8, 4.2, 7.7],
    )
    para(doc, "", size=4, space_after=2)

    heading(doc, "2.1 当前做到了什么", 2)
    bullet(doc, "数据规模：132 个品类 × 15 个市场 = 1980 个组合，104 周周粒度数据，共 205,920 行。")
    bullet(doc, "预测能力：双模型输出未来 90 天预测和 80% 置信区间，预测产物共 356,400 行。Prophet 基线 MAPE 约 3.36%，LightGBM 进阶约 2.29%，相对提升约 32%。")
    bullet(doc, "推荐引擎：综合评分 + 六维评分 + Go / Conditional / No-Go 判定，推荐理由自动生成。")
    bullet(doc, "贸易决策：覆盖政策、成本、合规、IP、物流、舆情、CBAM、融资就绪与冲突裁决。")
    bullet(doc, "统一后端：FastAPI 同时提供 REST API、React 前端、MCP Server 与后台任务。")
    bullet(doc, "测试：后端 pytest 428 项通过，前端另有 Vitest 测试。")

    heading(doc, "2.2 我对当前进度的理解", 2)
    para(
        doc,
        "我把当前状态概括为：演示闭环已经完整，真实数据在逐步接入，商业化和数据治理是下一步。导师如果问项目有没有做完，我会说系统能跑通，但离可销售的产品还有距离，差距主要在真实数据、授权数据回流和真实业务验证。",
    )
    doc.add_page_break()

    # 3. Overall idea
    heading(doc, "三、整体思路：一句话讲清系统怎么工作", 1)
    para(doc, "整个系统是一条流水线，前一环节的输出是后一环节的输入。")
    code_block(
        doc,
        [
            "多源数据（搜索热度、榜单、出口、政策、评论）",
            "        ↓",
            "数据清洗与特征工程",
            "        ↓",
            "双模型预测（Prophet + LightGBM）",
            "        ↓",
            "选品推荐（综合评分 + 六维评分）",
            "        ↓",
            "贸易决策（成本、政策、合规、IP、物流、舆情、CBAM、融资）",
            "        ↓",
            "综合决策报告与看板",
        ],
    )
    para(
        doc,
        "用大白话说：系统先收集大量公开信息，再把信息整理成表格，用模型预测未来，用规则打分排序，最后把政策和成本算进去，给出一份能解释的决策建议。",
        space_before=6,
    )
    doc.add_page_break()

    # 4. Technical implementation
    heading(doc, "四、技术实现讲解（小白友好）", 1)
    para(doc, "这一章写给技术小白。每一节先讲这个概念解决什么问题，再讲项目里具体怎么做的。")

    heading(doc, "4.1 数据从哪里来", 2)
    para(doc, "数据像做饭的食材。系统要回答选品问题，需要搜索热度、平台榜单、海关出口、政策事件、评论数据等多类信息。")
    bullet(doc, "合成演示数据：src/data/synthetic.py 生成 132 品类 × 15 市场、104 周的周粒度数据，带趋势、季节性和品类差异，保证离线也能完整演示。")
    bullet(doc, "真实数据适配器：Google Trends、Amazon / eBay 免费样例、UN Comtrade / Open Trade Statistics、Open Food Facts 等已经接入，失败时自动回退到 mock 并标注。")
    bullet(doc, "政策官方源：中国政府网、美国 Federal Register、欧盟委员会、英国 GOV.UK 已接入政策雷达，官方原文优先。")
    bullet(doc, "清洗与存储：src/data/cleaner.py 统一字段、去重、填充缺失值，结果写入 data/processed/clean_data.csv 和 SQLite。")

    heading(doc, "4.2 特征工程是什么", 2)
    para(doc, "特征工程就是把原始数据整理成模型能看懂的线索。比如模型想知道下一周销量，就需要知道最近几周卖了多少、搜索热度升了还是降了、现在是几月。")
    bullet(doc, "滞后特征：用过去 1、2、4、8 周的值当线索。")
    bullet(doc, "滚动统计：算最近 4 周、8 周的均值，观察短期趋势。")
    bullet(doc, "增长率与差分：看销量、搜索热度、价格、竞争度的变化速度。")
    bullet(doc, "季节编码：把月份和星期编码成模型能用的数值。")

    heading(doc, "4.3 双模型预测", 2)
    para(doc, "预测模块回答的是：这个品类在这个市场，未来一段时间大概能卖多少。")
    bullet(doc, "Prophet 是时间序列基线模型，适合捕捉趋势和季节性；项目对销量做对数变换，输出未来 90 天预测和 80% 置信区间。")
    bullet(doc, "LightGBM 是梯度提升树模型，能用更多特征做回归，项目用它做进阶预测，评估指标用 MAPE 和 MAE。")
    bullet(doc, "MAPE 可以理解为预测值和真实值平均偏差的百分比。MAPE 越低，整体越准。")
    bullet(doc, "置信区间可以理解为预测不是一个点，而是大概率落在某个范围，项目输出 80% 区间。")
    add_table(
        doc,
        ["模型", "MAPE", "说明"],
        [
            ["Prophet 基线", "约 3.36%", "时间序列基线"],
            ["LightGBM 进阶", "约 2.29%", "相对基线下降约 32%"],
        ],
        widths=[4.5, 3.5, 7.5],
    )
    para(
        doc,
        "以上是当前合成演示数据口径；对照组同批 12 个组合实测约为 3.30% 与 2.31%，见 output/control/control_metrics.json。",
        size=9,
        color=COLOR_GRAY,
        space_before=4,
    )
    add_image(
        doc,
        "model_mape.png",
        "模型误差对比配图，来自 docs/figures/model_mape.png（《数据分析报告》）。",
    )

    heading(doc, "4.4 选品推荐引擎", 2)
    para(doc, "推荐引擎回答的是：1980 个组合里，哪些值得优先看。")
    bullet(doc, "综合评分公式：0.35 × 预测增长 + 0.30 × 搜索趋势 + 0.25 × 竞争度（反向）+ 0.10 × 评论增长。")
    bullet(doc, "六维评分：预测增长、搜索趋势、竞争度、利润空间、合规可行性、证据完整度，权重为 25%、20%、20%、20%、10%、5%。")
    bullet(doc, "判定规则：70 分以上且无弱项和待确认项为 Go；总分低于 55 分或任一维度低于 40 分为 No-Go；其余为 Conditional，建议小批量试单。")
    bullet(doc, "推荐理由按各维度阈值自动生成中文说明。")
    add_image(
        doc,
        "recommend_composition.png",
        "推荐构成配图，来自 docs/figures/recommend_composition.png（《数据分析报告》）。",
    )

    heading(doc, "4.5 贸易决策模块", 2)
    para(doc, "贸易决策模块回答的是：就算选品方向对，这笔生意到底赚不赚、能不能安全落地。")
    bullet(doc, "政策风险：把政策事件量化为有效税率、单件关税、到岸成本变化和利润冲击，输出应对建议，例如转正式清关、调价、切换市场、海外仓本地发货。")
    bullet(doc, "成本模型：覆盖采购、关税、汇率（±5% 敏感性）、支付通道、认证合规和物流三方案（小包直邮、海运整柜、海外仓）。")
    bullet(doc, "合规与准入：IOSS / VAT、CE / FCC / FDA / RoHS / CPSC / GPSR 等清单，输出认证成本、周期和准入评分。")
    bullet(doc, "知识产权：内置商标、专利、外观设计库，按品类 × 市场输出低 / 中 / 高风险。")
    bullet(doc, "物流：SCFI 风格运价序列，预测未来 4 周运价指数、单件物流成本和拥堵风险。")
    bullet(doc, "舆情：英、西、德、日、葡多语言情感词库，输出情绪分、正负中性占比和本地化建议。")
    bullet(doc, "绿色贸易：输出欧盟 CBAM 暴露度、预估碳成本和政策趋势。")
    bullet(doc, "融资就绪：把政策、物流、利润和数据覆盖度映射成融资就绪评分和建议融资档位。")
    bullet(doc, "冲突裁决：把市场、舆情、政策、物流、财务、准入、融资 7 类信号统一到 0 到 100 分，按置信度 × 权重裁决，输出风险优先建议。")

    heading(doc, "4.6 四脑引擎与 AI 接入", 2)
    para(doc, "四脑引擎模拟四种视角的分析：市场、舆情、供应链 / 政策、财务。")
    bullet(doc, "每个大脑独立输出分报告，并给出置信度，置信度来自数据完整度和模型拟合度。")
    bullet(doc, "结果统一进入冲突裁决，按置信度 × 权重得到综合结论。")
    bullet(doc, "主 Demo 顶部有统一 AI 接入配置，一次填写 API Key、Base URL 和模型，四脑工作台、贸易决策和看板共用；配置存在浏览器 localStorage 和后端内存，不写 .env。")
    bullet(doc, "联网研究支持爬虫优先、DuckDuckGo 回退、mock 标注，不用 Key 也能演示。")

    heading(doc, "4.7 前端、后端、API 与 MCP", 2)
    para(doc, "前端负责给用户看，后端负责算。")
    bullet(doc, "前端：React 19 + TypeScript + Vite，包含看板、贸易决策、四脑工作台、系统控制台等页面，图表用 ECharts。")
    bullet(doc, "后端：FastAPI 统一进程，同时提供 REST API、React 前端 /app、MCP /mcp 和后台任务 /api/jobs。")
    bullet(doc, "REST 示例：/api/recommendations 返回 Top N 推荐，/api/trade/decision 返回单组合贸易决策，/api/policy/events 返回政策事件清单，/api/data/status 返回数据更新状态。")
    bullet(doc, "MCP Server 把推荐、贸易决策、HS Code 速查和数据状态暴露为标准工具，供 Claude、Codex、Cursor 等客户端调用。")
    add_image(
        doc,
        "dashboard_html_preview.png",
        "Demo 看板效果图，来自 docs/figures/dashboard_html_preview.png。",
    )

    heading(doc, "4.8 每日数据更新与政策雷达", 2)
    para(doc, "数据不是一次生成就结束，而是每天刷新。")
    bullet(doc, "scripts/run_daily_update.py 刷新数据到当天，生成每日联网快照、Google Trends、平台榜单、海关出口、政策雷达和市场日报，并重建看板与前端。")
    bullet(doc, "政策雷达每 6 小时刷新一次官方源，只让已核实事件进入决策链，搜索结果仅作候选。")
    bullet(doc, "后台任务由 /api/jobs/* 管理，完成后自动失效缓存，不需要重启进程。")
    bullet(doc, "Windows 计划任务可以注册每日更新和政策雷达，双击一键启动也会先跑数据刷新。")

    heading(doc, "4.9 测试与质量", 2)
    para(doc, "测试的作用是防止改一处坏一片。")
    bullet(doc, "后端 pytest 428 项通过，覆盖数据、特征、模型、贸易决策、API 和流水线。")
    bullet(doc, "前端有 Vitest 测试，系统控制台有环境自检，可检查依赖、代码完善度和前后端连接。")
    bullet(doc, "模型和评估结果版本化，指标落盘到 JSON / CSV，固定随机种子保证可复现。")
    doc.add_page_break()

    # 5. Glossary
    heading(doc, "五、技术名词人话字典", 1)
    para(doc, "这一章把文档里可能出现的术语整理成三列：术语、通俗解释、在项目里用在哪。")
    add_table(
        doc,
        ["术语", "通俗解释", "在项目里用在哪"],
        [
            ["API", "程序之间约定的调用入口", "后端 FastAPI 提供 /api/* 给前端和 AI 工具调用"],
            ["FastAPI", "Python 的 Web 框架，用来快速搭建接口", "scripts/run_api.py 启动的统一后端"],
            ["React", "前端界面框架", "/app 页面"],
            ["TypeScript", "带类型检查的 JavaScript", "frontend 源码"],
            ["SQLite", "单文件数据库", "data/processed/market_data.db"],
            ["CSV", "逗号分隔的表格文件", "清洗数据、预测结果、推荐结果"],
            ["特征", "模型输入的一列线索", "滞后销量、搜索热度、价格、竞争度"],
            ["特征工程", "把原始数据整理成模型能用的输入", "src/features/builder.py"],
            ["时间序列", "按时间顺序排列的数据", "104 周销量"],
            ["滞后特征", "用过去几周的值当线索", "lag_1 / lag_2 / lag_4 / lag_8"],
            ["滚动统计", "过去几周的平均或汇总", "4 周、8 周均值"],
            ["季节性", "周期性波动", "8 月旺季、2 月低谷"],
            ["Prophet", "时间序列预测模型", "基线模型"],
            ["LightGBM", "梯度提升树模型", "进阶模型"],
            ["MAPE", "平均百分比误差", "约 3.36% 与 2.29%"],
            ["置信区间", "预测可能落在的范围", "80% 置信区间"],
            ["爬虫", "自动抓取网页内容的程序", "Wikimedia 公开爬虫、政策官方源"],
            ["回退", "主来源失败后换备用来源", "crawler 到 DuckDuckGo 到 mock"],
            ["JSON", "结构化文本数据格式", "接口返回、快照文件"],
            ["缓存", "把结果存起来避免重复计算", "数据源缓存、后端缓存失效"],
            ["后台任务", "不阻塞页面运行的长任务", "/api/jobs/* 每日更新"],
            ["MCP", "让 AI 客户端调用标准工具的协议", "/mcp 暴露推荐、决策、HS 速查"],
            ["HS Code", "国际商品海关编码", "品类对应 HS4 / HS6"],
            ["CBAM", "欧盟碳边境调节机制", "绿色贸易模块前瞻"],
            ["证据闸", "结论必须带来源和可信度标注", "报告与看板的证据清单"],
            ["自动化测试", "自动检查代码行为是否正确", "pytest 428 项"],
            ["计划任务", "系统定时运行的程序", "Windows 每日更新与政策雷达"],
        ],
        widths=[3.2, 6.0, 6.3],
        size=9.5,
    )
    doc.add_page_break()

    # 6. My understanding
    heading(doc, "六、我的理解与收获", 1)
    para(doc, "这一章是我自己的部分，先写我目前能讲明白的理解，再用占位符标出需要我补充的经历。")

    heading(doc, "6.1 我对项目最核心的理解", 2)
    bullet(doc, "项目不是做一个聊天机器人，而是把确定性计算和大模型能力分开。预测、成本、风险用固定规则和模型算，大模型负责研究综述和报告生成。")
    bullet(doc, "系统最有价值的地方不是某一个算法，而是把多源数据、政策事件、成本公式和推荐规则串成一条可复现、可解释的链路。")
    bullet(doc, "误差指标的意义是让项目敢说自己的预测有多准；证据闸的意义是让报告里的每个结论都能找到依据。")

    heading(doc, "6.2 我目前的技术水平", 2)
    para(doc, "我在技术上是小白，还在补基础。目前能讲明白上面这些概念，但独立实现还有距离。以下内容需要我本人填写，括号里是示例。")
    bullet(doc, "【待填写：我在项目里主要负责哪部分，例如整理数据、写文档、做演示、跑测试】")
    bullet(doc, "【待填写：我已经独立完成的事情，例如跑通一次 pipeline、看懂某个模块、给导师演示一次】")
    bullet(doc, "【待填写：我还在学的内容，例如 pandas、模型调参、React、国际贸易术语】")
    bullet(doc, "【待填写：我遇到的困难，例如读不懂某个代码、不知道某个指标怎么算、演示时某个环节报错】")

    heading(doc, "6.3 从零学技术的建议路径", 2)
    numbered(doc, "1. Python 基础，能读写表格数据，重点学 pandas 的 DataFrame。")
    numbered(doc, "2. 跟着 src/data、src/features、src/models 的流水线读一遍，先看数据怎么从 CSV 变成预测结果。")
    numbered(doc, "3. 学时间序列和误差指标，能把 MAPE、置信区间讲明白。")
    numbered(doc, "4. 学 FastAPI 和前端调用，理解一个接口从浏览器请求到后端计算的过程。")
    numbered(doc, "5. 再回来看贸易模块，把政策、成本、合规的公式和术语补起来。")

    heading(doc, "6.4 希望导师给的方向建议", 2)
    bullet(doc, "【待填写：例如希望导师帮忙判断真实数据接入的优先级】")
    bullet(doc, "【待填写：例如希望导师建议算法学习深度，是够用就好还是要系统学】")
    bullet(doc, "【待填写：例如希望导师建议参赛材料怎么突出个人贡献】")
    doc.add_page_break()

    # 7. Outlook
    heading(doc, "七、展望与下一步", 1)
    heading(doc, "7.1 产品 Roadmap", 2)
    bullet(doc, "真实数据推进：Google Trends、平台榜单、海关出口从已接入、可回退推进到默认真实。")
    bullet(doc, "数据升级：接入 Keepa、eBay、Comtrade 正式 Key。")
    bullet(doc, "数据治理：核实 HS6 码和待核实行业条目，补全证据来源。")
    bullet(doc, "对照实验：完整 23760 格结果回填，形成可对外引用的结论。")
    bullet(doc, "商业化：SaaS 订阅 + 企业定制 + 行业报告；远期接入授权经营数据做供应链金融。")

    heading(doc, "7.2 我的短期学习计划", 2)
    add_table(
        doc,
        ["时间", "内容", "可交付"],
        [
            ["2 周", "pandas 与 Python 基础", "能自己读取并清洗一份 CSV"],
            ["1 个月", "读懂特征与模型模块", "能讲清 lag、滚动统计、MAPE"],
            ["一学期", "前后端与贸易模块", "能独立跑通 API 并解释一个贸易决策"],
        ],
        widths=[2.5, 6.0, 7.0],
    )
    doc.add_page_break()

    # 8. Current flaws and issues
    heading(doc, "八、当前项目的瑕疵与问题", 1)
    para(
        doc,
        "这一章是我从现有材料、代码和运行产物里整理出的问题清单，按数据真实性、文档口径、对照组、工程维护、产品化五类列出来，目的是让导师知道项目还差什么。",
    )

    heading(doc, "8.1 数据与真实性", 2)
    bullet(doc, "当前运行产物的真实覆盖率很低。data_status.json 显示 crawler、Google Trends、海关出口、供应商、Open Food Facts 都回退到 mock，真实记录为 0；平台榜单在离线模式下被跳过。只有 GitHub 公开数据集信号层有 866 条真实记录。")
    bullet(doc, "政策雷达最新快照里四个官方源都显示 offline，21 个已核实事件来自缓存和历史事件，实时联网刷新没有真正成功。")
    bullet(doc, "部分真实数据源需要 Key 或网络，未配置时全部回退并标注，回退结果不能当真实证据。")

    heading(doc, "8.2 文档与口径一致性", 2)
    bullet(doc, "docs/项目大纲.md 仍写 106 项测试，README 与 AGENTS 已是 428 项，两处数字不一致。")
    bullet(doc, "docs/技术文档.md 的真实特征训练说明仍写约 690 组合、71,760 行，而当前 data_status.json 是 1980 组合、205,920 行，口径没有对齐。")
    bullet(doc, "对照组格数曾在不同材料里出现过 8280 与 11880 两种说法，正式口径应为 23760，即 1980 组合乘 12 周。")

    heading(doc, "8.3 对照组与评测", 2)
    bullet(doc, "output/control/control_metrics.json 里，两次 AI 运行的自动评分 coverage 都是 0，144 格全部 invalid，MAPE 为 null；只有人工按周对齐后才能算出 6.94% 与 7.52%。对外引用时必须说明这个前提。")
    bullet(doc, "完整 23760 格对照结果还没有回填，现有结论是轻量实测。")
    bullet(doc, "两次运行的推荐 Top5 Jaccard 为 0.6667，通用 AI 的复现性仍不理想，这也是对照实验设计需要说明的部分。")

    heading(doc, "8.4 工程与维护", 2)
    bullet(doc, "tmp/ 目录约 490 MB，主要是日志、检查脚本和一次性产物，可以定期清理。")
    bullet(doc, "爬虫缓存存在重复记录，最新质量统计里 duplicate_rate 约 0.56，需要去重治理。")
    bullet(doc, "部分文档和报告归档还残留旧口径，例如 46 品类、690 组合、71,760 行，虽然标为归档，检索时仍容易误导。")

    heading(doc, "8.5 产品化", 2)
    bullet(doc, "当前是演示口径：合成数据、内置税率和运价、演示商标库都不能直接当生产结论。")
    bullet(doc, "数据信用与 CBAM 是离线演示，真实授信需要授权经营数据和碳排因子库。")
    bullet(doc, "行业事实还有待核实条目，例如 Temu AI 监测与 SaaS 趋势条目标注待核实。")
    bullet(doc, "缺少真实卖家试点数据，推荐和贸易决策的实用性还没有被真实业务验证。")
    bullet(doc, "我个人是技术小白，对系统的理解还在加深，这份问题清单也需要继续补充。")
    doc.add_page_break()

    # 9. Q&A
    heading(doc, "九、导师与答辩问答速查", 1)
    para(doc, "下表是导师和评委最常问的七个方向。参考口径来自现有项目文档，使用前建议用自己的话再过一遍。")
    add_table(
        doc,
        ["问题方向", "参考口径", "证据材料"],
        [
            ["数据真实性", "当前以合成演示数据为主，真实信号层已接入；来源失败会回退并标注；证据闸只让有来源的结论进入评分", "docs/数据字典.md、output/data_status.json"],
            ["模型可解释性", "推荐评分公式公开，推荐理由按阈值生成；冲突裁决给出置信度和权重", "docs/技术文档.md、src/models/recommend.py"],
            ["创新点", "定位从选品工具升级为贸易决策智能；政策量化、冲突裁决、全链路闭环、对照组评测", "商业计划书、项目大纲"],
            ["与竞品差异", "竞品偏关键词和流量，本项目覆盖政策、成本与风险，输出可执行建议", "项目优势报告、路演大纲"],
            ["对照组结论", "通用 AI 擅长描述，但格式不可直接消费、可复现性和数字可追溯不足；轻量实测误差高于本项目", "docs/项目优势报告.md、output/control/control_metrics.json"],
            ["落地优先级", "先做关税 / 政策风险引擎与成本测算，再扩真实数据和商业化", "实施路径、项目大纲"],
            ["个人贡献", "【待填写：你负责哪部分、做了什么、学到什么】", "无"],
        ],
        widths=[2.3, 8.2, 5.0],
        size=9.5,
    )
    para(
        doc,
        "口径说明：对照组轻量实测为 12 个组合、144 个预测格；通用 AI 两次运行 MAPE 分别为 6.94% 与 7.52%，项目侧同批组合约 3.30%（Prophet）与 2.31%（LightGBM）。完整 23760 格结果待回填。",
        size=9.5,
        color=COLOR_GRAY,
        space_before=6,
    )
    doc.add_page_break()

    # 10. Appendix
    heading(doc, "十、附录：常用数字、材料地图与运行命令", 1)
    heading(doc, "10.1 常用数字", 2)
    add_table(
        doc,
        ["项目", "数值"],
        [
            ["品类 / 市场 / 组合", "132 / 15 / 1980"],
            ["数据规模", "104 周，205,920 行"],
            ["预测范围与产物", "未来 90 天，356,400 行"],
            ["模型误差", "Prophet 约 3.36%，LightGBM 约 2.29%"],
            ["自动化测试", "pytest 428 项通过"],
            ["贸易决策", "1980 组合，92 个高风险，平均融资就绪 77.4"],
            ["对照组", "轻量 12 组合 144 格；完整 23760 格"],
            ["推荐示例", "Top1 组合与综合评分以《数据分析报告》§七 的实际输出为准"],
            ["季节规律", "销量峰值约第 32 周（8 月），低谷约 2 月"],
        ],
        widths=[5.5, 10.0],
    )
    para(doc, "", size=4, space_after=2)

    heading(doc, "10.2 材料地图", 2)
    add_table(
        doc,
        ["材料", "位置", "用途"],
        [
            ["项目总说明", "README.md", "项目简介、启动方式"],
            ["技术文档", "docs/技术文档.md", "架构、数据管道、模型、贸易模块"],
            ["项目大纲", "docs/项目大纲.md", "定位、阶段、成果、下一步"],
            ["路演大纲", "docs/路演大纲.md", "10 分钟演示与答辩口径"],
            ["数据分析报告", "docs/数据分析报告.md", "图表、统计、来源"],
            ["项目优势报告", "docs/项目优势报告.md", "与通用 AI 的对照结论"],
        ],
        widths=[3.5, 6.0, 6.0],
    )
    para(doc, "", size=4, space_after=2)

    heading(doc, "10.3 常用运行命令", 2)
    code_block(
        doc,
        [
            ".venv\\Scripts\\python scripts\\run_pipeline.py",
            ".venv\\Scripts\\python scripts\\run_api.py",
            ".venv\\Scripts\\python scripts\\run_daily_update.py",
            ".venv\\Scripts\\python scripts\\run_trade_demo.py",
            ".venv\\Scripts\\python scripts\\run_data_analysis.py",
            ".venv\\Scripts\\python -m pytest tests -q",
        ],
    )
    para(
        doc,
        "这份材料生成于 2026 年 8 月 18 日。个人经历部分的占位符需要填完后再发给导师。",
        space_before=10,
    )

    add_page_number(doc)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUTPUT_PATH))
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_document()
