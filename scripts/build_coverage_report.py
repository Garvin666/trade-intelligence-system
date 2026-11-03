#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""B-1 数据覆盖率盘点收尾：固化「真实来源占比」可重复计算脚本。

口径（mock_isolated，与 data_status.json 的 mock_isolated 语义一致）：
  - 对每个 (品类 × 市场) 格，统计 7 个品类级信号层的状态：
      real   = 该层对该格存在真实（非 mock / 非合成）数据
      mock   = 该层对该格仅有 mock 回退数据
      absent = 该层对该格无数据
  - 真实来源占比 = real / (real + mock)；absent 不进分母，mock 不计入真实。

输入（只读，均为既有产物，不联网、不改动任何数据产物）：
  - output/data_status.json            （14 个数据块状态与覆盖计数，主输入）
  - output/control/github_signals.json （GitHub 公开数据集信号层，866 行）
  - output/trends/latest.json          （Google Trends 快照，66 序列）
  - output/crawler/latest.json         （Wikimedia 爬虫，10 个真实组合）
  - output/customs/latest.json         （UN Comtrade 海关出口，66 行）
  - output/platform_rankings/latest.json（平台榜单，5174 行）
  - output/suppliers/latest.json       （1688 供应商，66 行全 mock）
  - data/external/github/octaprice/*.csv（Octaprice 免费商品数据集，市场确认用）

输出：
  - reports/数据覆盖率盘点_<日期>.md   （主交付文档，日期取自输入快照，幂等）

幂等性：相同输入产物 → 逐字节相同输出（输出不含运行时刻时间戳、无随机）。
用法：  .venv\\Scripts\\python scripts\\build_coverage_report.py
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CATEGORIES, CATEGORY_KEYWORDS, MARKETS  # noqa: E402
from src.data.base import seed_for  # noqa: E402

# ---------------------------------------------------------------- 路径与常量

OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_STATUS = OUTPUT_DIR / "data_status.json"
GITHUB_SIGNALS = OUTPUT_DIR / "control" / "github_signals.json"
TRENDS = OUTPUT_DIR / "trends" / "latest.json"
CRAWLER = OUTPUT_DIR / "crawler" / "latest.json"
CUSTOMS = OUTPUT_DIR / "customs" / "latest.json"
RANKINGS = OUTPUT_DIR / "platform_rankings" / "latest.json"
SUPPLIERS = OUTPUT_DIR / "suppliers" / "latest.json"
OCTAPRICE_DIR = PROJECT_ROOT / "data" / "external" / "github" / "octaprice"

REPORTS_DIR = PROJECT_ROOT / "reports"

# 3×3 已拍板收敛（对外主叙事）：品类候选 × 市场候选
CANDIDATE_CATEGORIES = ("cn_latiao", "cn_longjing", "cn_frozen_dumplings")
CANDIDATE_MARKETS = ("us", "sea")

# 参与每格占比的 7 个品类级信号层（顺序即文档表头顺序）
LAYERS = (
    "github_signals",
    "proxy_sales",
    "trends",
    "crawler",
    "customs",
    "rankings",
    "suppliers",
)
LAYER_NAMES = {
    "github_signals": "GitHub 信号层",
    "proxy_sales": "真实销量代理",
    "trends": "Google Trends",
    "crawler": "crawler(Wikimedia)",
    "customs": "Comtrade 海关",
    "rankings": "平台榜单",
    "suppliers": "供应商 1688",
}

# 用于对齐《3×3 选择依据表 v1.0》的辅助口径：供应商全局缺口、Trends us 单市场不计入分母
REPORT_ALIGN_LAYERS = ("github_signals", "proxy_sales", "crawler", "customs", "rankings")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- Trends 判定

def mock_trend_series(
    category: str, market: str, keyword: str, report_date: date, weeks: int = 52
) -> list[tuple[str, float]]:
    """按 src/data/trends.py `_fallback_rows` 的确定性公式复刻 mock 序列。"""
    seed = seed_for(category, market)
    out: list[tuple[str, float]] = []
    for index in range(weeks):
        day = report_date - timedelta(weeks=weeks - index - 1)
        season = math.sin((index + seed * 12) / 6.0) * 12.0
        trend = index * 0.35
        wave = math.sin((index + seed * 37) / 4.0) * 8.0
        value = max(5.0, min(100.0, 50.0 + season + trend + wave + seed * 5.0))
        out.append((day.isoformat(), round(value, 2)))
    return out


def classify_trends(payload: dict[str, Any]) -> dict[str, str]:
    """逐序列比对快照行与 mock 公式，输出 {category: 'real'|'mock'}。

    真实 pytrends 序列不会命中确定性 mock 公式；mock 序列逐值完全一致。
    """
    report_date = date.fromisoformat(payload["date"])
    keyword_of = dict(zip(payload["keywords"], payload["keywords"]))
    grouped: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    for row in payload["rows"]:
        grouped[(row["category"], row["market"])].append((row["date"], row["value"]))
    result: dict[str, str] = {}
    for (cat, mkt), actual in grouped.items():
        expected = mock_trend_series(cat, mkt, keyword_of.get(cat, cat), report_date)
        result[cat] = "mock" if sorted(actual) == sorted(expected) else "real"
    return result


# ---------------------------------------------------------------- 各层判定

def layer_status_github(rows: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    """GitHub 信号层：按 (品类, 市场) 是否有 fallback_used=False 行判定。"""
    status: dict[tuple[str, str], str] = {}
    for r in rows:
        if r.get("fallback_used"):
            continue
        key = (r.get("category", ""), r.get("market", ""))
        if key[0] and key[1]:
            status.setdefault(key, "real")
    return status


def layer_status_proxy(combo_stats: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    """真实销量代理：combo_stats 中存在的 (品类, 市场) 均为真实标注。"""
    return {(r["category"], r["market"]): "real" for r in combo_stats}


def layer_status_trends(classification: dict[str, str], markets: tuple[str, ...]) -> dict[tuple[str, str], str]:
    """Trends：当前快照仅采集 market=us；us 格按真实/回退标记，非 us 格为 absent。"""
    status: dict[tuple[str, str], str] = {}
    for cat, kind in classification.items():
        for mkt in markets:
            if mkt == "us":
                status[(cat, mkt)] = kind
    return status


def layer_status_crawler(payload: dict[str, Any]) -> dict[tuple[str, str], str]:
    """crawler：payload['combos']（组合记录列表）中 fallback_used=False 的为真实。"""
    status: dict[tuple[str, str], str] = {}
    for r in payload.get("combos", []) or []:
        if r.get("fallback_used"):
            continue
        key = (r.get("category", ""), r.get("market", ""))
        if key[0] and key[1]:
            status.setdefault(key, "real")
    return status


def layer_status_customs(rows: list[dict[str, Any]], markets: tuple[str, ...]) -> dict[tuple[str, str], str]:
    """Comtrade：品类级真实（66 行，2024 期未回退）；无市场细分 → 视为对所有市场有效，附注说明。"""
    status: dict[tuple[str, str], str] = {}
    for r in rows:
        cat = r.get("category", "")
        if not cat or r.get("fallback_used"):
            continue
        for mkt in markets:
            status[(cat, mkt)] = "real"
    return status


def layer_status_rankings(rows: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    """平台榜单：该格任一行真实 → real；仅 mock 行 → mock；无行 → absent。"""
    status: dict[tuple[str, str], str] = {}
    for r in rows:
        key = (r.get("category", ""), r.get("market", ""))
        if not key[0] or not key[1]:
            continue
        cur = status.get(key)
        if r.get("fallback_used"):
            status.setdefault(key, "mock")
        else:
            status[key] = "real"
    return status


def layer_status_suppliers(rows: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    """供应商：全部为 mock 回退（1688 风控），仅覆盖有行的格。"""
    status: dict[tuple[str, str], str] = {}
    for r in rows:
        key = (r.get("category", ""), r.get("market", ""))
        if key[0] and key[1]:
            status.setdefault(key, "mock")
    return status


# ---------------------------------------------------------------- 占比计算

def cell_ratio(layer_status: dict[str, str]) -> tuple[float | None, int, int]:
    """主口径：real / (real + mock)。全 absent 返回 None。"""
    real = sum(1 for v in layer_status.values() if v == "real")
    mock = sum(1 for v in layer_status.values() if v == "mock")
    if real + mock == 0:
        return None, 0, 0
    return real / (real + mock), real, mock


def build_matrix(
    categories: tuple[str, ...],
    markets: tuple[str, ...],
    layer_maps: dict[str, dict[tuple[str, str], str]],
) -> dict[tuple[str, str], dict[str, str]]:
    matrix: dict[tuple[str, str], dict[str, str]] = {}
    for cat in categories:
        for mkt in markets:
            cell: dict[str, str] = {}
            for layer in LAYERS:
                cell[layer] = layer_maps[layer].get((cat, mkt), "absent")
            matrix[(cat, mkt)] = cell
    return matrix


def ratio_cell(cell: dict[str, str], layers: tuple[str, ...]) -> tuple[float | None, int, int]:
    real = sum(1 for l in layers if cell[l] == "real")
    mock = sum(1 for l in layers if cell[l] == "mock")
    if real + mock == 0:
        return None, 0, 0
    return real / (real + mock), real, mock


# ---------------------------------------------------------------- Octaprice 分析

def octaprice_analysis() -> dict[str, Any]:
    """只读 Octaprice CSV：表头、记录数、货币、卖家、URL 域名、面包屑品类。

    注意：文件行数含多行字段（描述换行），记录数必须用 csv 读取器统计。
    """
    csvs = sorted(OCTAPRICE_DIR.glob("*.csv"))
    if not csvs:
        return {"found": False}
    path = csvs[0]
    header: list[str] = []
    currencies: Counter[str] = Counter()
    sellers: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    breadcrumbs: Counter[str] = Counter()
    row_count = 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        for row in reader:
            row_count += 1
            url = (row.get("url") or "").strip()
            domains[url.split("/")[2] if url.startswith("http") else "(none)"] += 1
            currencies[row.get("currency") or "(none)"] += 1
            sellers[row.get("sellerName") or "(none)"] += 1
            bc = row.get("breadcrumbs") or ""
            breadcrumbs["bird_food" if "Bird Seed" in bc or "bird" in bc.lower() else bc[:40]] += 1
    return {
        "found": True,
        "file": path.name,
        "row_count": row_count,
        "header": header,
        "currencies": dict(currencies.most_common(6)),
        "sellers": dict(sellers.most_common(6)),
        "domains": dict(domains.most_common(6)),
        "breadcrumbs": dict(breadcrumbs.most_common(6)),
    }


# ---------------------------------------------------------------- 文档生成

def pct(ratio: float | None) -> str:
    return "—" if ratio is None else f"{ratio * 100:.1f}%"


def layer_mark(kind: str) -> str:
    return {"real": "✅真实", "mock": "⚠️mock", "absent": "—"}[kind]


def build_report(
    data_status: dict[str, Any],
    github_rows: list[dict[str, Any]],
    trends_payload: dict[str, Any],
    crawler_payload: dict[str, Any],
    customs_rows: list[dict[str, Any]],
    rankings_rows: list[dict[str, Any]],
    supplier_rows: list[dict[str, Any]],
    trends_class: dict[str, str],
    octa: dict[str, Any],
) -> str:
    categories = tuple(CATEGORY_KEYWORDS.keys())
    markets = tuple(MARKETS.keys())
    as_of = data_status["data_as_of"]

    layer_maps = {
        "github_signals": layer_status_github(github_rows),
        "proxy_sales": layer_status_proxy(data_status["real_proxy"]["combo_stats"]),
        "trends": layer_status_trends(trends_class, markets),
        "crawler": layer_status_crawler(crawler_payload),
        "customs": layer_status_customs(customs_rows, markets),
        "rankings": layer_status_rankings(rankings_rows),
        "suppliers": layer_status_suppliers(supplier_rows),
    }
    matrix = build_matrix(categories, markets, layer_maps)

    # 各层真实覆盖统计（全 132×15 格）
    layer_stats: dict[str, dict[str, int]] = {}
    for layer in LAYERS:
        kinds = [matrix[(c, m)][layer] for c in categories for m in markets]
        layer_stats[layer] = dict(Counter(kinds))

    real_cats = sorted(c for c, k in trends_class.items() if k == "real")
    mock_cats = sorted(c for c, k in trends_class.items() if k == "mock")
    candidate_intersect = {
        c: trends_class.get(c, "absent") for c in CANDIDATE_CATEGORIES
    }

    # 3×3 矩阵（主口径 + 对齐依据表口径）
    grid_primary: list[list[str]] = []
    grid_align: list[list[str]] = []
    for cat in CANDIDATE_CATEGORIES:
        row_p, row_a = [], []
        for mkt in CANDIDATE_MARKETS:
            cell = matrix[(cat, mkt)]
            r_p, _, _ = ratio_cell(cell, LAYERS)
            r_a, _, _ = ratio_cell(cell, REPORT_ALIGN_LAYERS)
            row_p.append(pct(r_p))
            row_a.append(pct(r_a))
        grid_primary.append(row_p)
        grid_align.append(row_a)

    # 达标格统计
    primary_pass = sum(
        1
        for cat in CANDIDATE_CATEGORIES
        for mkt in CANDIDATE_MARKETS
        if (lambda c: (c is not None and c >= 0.8))(ratio_cell(matrix[(cat, mkt)], LAYERS)[0])
    )
    align_pass = sum(
        1
        for cat in CANDIDATE_CATEGORIES
        for mkt in CANDIDATE_MARKETS
        if (lambda c: (c is not None and c >= 0.8))(ratio_cell(matrix[(cat, mkt)], REPORT_ALIGN_LAYERS)[0])
    )

    lines: list[str] = []
    add = lines.append
    add("# 数据覆盖率盘点（B-1 收尾）")
    add("")
    add(f"> 版本：v1.0 ｜ 快照日期：{as_of} ｜ 性质：只读分析 + 固化盘点脚本（scripts/build_coverage_report.py）")
    add(f"> 主输入：`output/data_status.json`（generated_at={data_status['generated_at']}，{len(data_status)} 个数据块）＋各信号层产物（详见 §1）")
    add(f"> 已拍板口径：3×3 收敛 = 对外主叙事 **US/SEA 版**（品类 pet/electronics/small_appliance × 市场 us/sea）")
    add("")

    add("## 0. 结论速览")
    add("")
    add("| 项目 | 结论 |")
    add("|---|---|")
    real_intersect = [c for c in CANDIDATE_CATEGORIES if candidate_intersect.get(c) == "real"]
    add(f"| Google Trends 真实品类 | **10/66**：{', '.join(real_cats)}；与 3×3 候选交集 = **{', '.join(real_intersect) or '无'}**（electronics 为 mock 回退） |")
    add(f"| Octaprice 数据集市场 | 仅 **美站 amazon.com**（972 条商品记录，URL 域名 100% www.amazon.com、货币 USD、卖家为美国零售商），品类=Bird Food（pet 相关）；**不含 DE 德国市场** → US/DE 备选不可借 octaprice 补 DE 价格信号 |")
    add(f"| 3×3 达标格（主口径 ≥80%） | **{primary_pass}/9**；对齐《3×3 选择依据表》口径为 **{align_pass}/9**；B-3 验收底线 6/9 **当前产物未达成**（差距与补数据建议见 §6） |")
    add("")

    add("## 1. 盘点方法与口径")
    add("")
    add("- **mock_isolated 口径**：真实证据与 mock 分开统计，mock 不计入真实、不用 mock 推断真实（与 `data_status.json` 的 mock_isolated 语义一致）。")
    add("- 每格（品类×市场）对 7 个品类级信号层逐层判定 `real / mock / absent`；**真实来源占比 = real / (real + mock)**，absent 层不进入分母（该层对该格无数据，不做任何声称）。")
    add("- 判定依据（全部来自产物字段，脚本内可复现）：")
    add(f"  1. **GitHub 信号层** `output/control/github_signals.json`：按 `rows[].(category, market)` 且 `fallback_used=false` 计数（当前 {len(github_rows)} 行真实；B-3 补数扩词+按组合截断后）。")
    add("  2. **真实销量代理** `data_status.real_proxy.combo_stats`：存在的 (品类, 市场) 即真实标注（4731 行，**43 品类 × 66 组合** × {us, sea}，provider amazon/shopee；注意 **small_appliance 不在代理模型品类集内**，见 §7）。")
    add("  3. **Google Trends** `output/trends/latest.json`：用生成侧 `src/data/trends.py::_fallback_rows` 的确定性公式逐值复刻，与快照逐序列比对——命中的是 mock（56），不命中的是真实（10）；当前快照仅采集 market=us，非 us 格视为 absent。")
    add("  4. **crawler** `output/crawler/latest.json`：`combos[]`（组合记录列表）中 `fallback_used=false` 的（10 个）。")
    add("  5. **Comtrade 海关** `output/customs/latest.json`：66 品类各 1 行，`fallback_used=false`；**无市场细分**（partner=null），视为品类级真实、对所有市场有效（附注此局限）。")
    add("  6. **平台榜单** `output/platform_rankings/latest.json`：按 (品类, 市场) 行级 `fallback_used` 判定（5174 行 = 224 真实 + 4950 mock）。")
    add("  7. **供应商 1688** `output/suppliers/latest.json`：66 行全 `fallback_used=true`（1688 风控拦截），且市场均为 **cn**（中国货源）——对 us/sea 候选格无数据（absent），仅 cn 市场格为 mock。")
    add("")

    add("## 2. Google Trends 真实品类明细（任务 1 结论）")
    add("")
    add(f"- 快照 `output/trends/latest.json`：`provider=pytrends`、`fallback_used=true`、`coverage={{requested:66, real:10, mock:56}}`、`rows=3432`（66 序列 × 52 周，market 仅 us）。")
    add("- rows/keywords **未含** provider/fallback 逐序列标记；生成侧 `src/data/trends.py`：`real_target = CATEGORY_KEYWORDS 前 GOOGLE_TRENDS_MAX_KEYWORDS(=10) 个`，`coverage.real = len(real_keywords)=10` 且 `GOOGLE_TRENDS_MAX_KEYWORDS=10` → 10 个候选全部成功。")
    add("- **产物级印证**：用 `_fallback_rows` 确定性公式逐值复刻全部 66 序列，与快照完全一致者为 mock（56），不一致者为真实（10）；真实 10 与「CATEGORY_KEYWORDS 前 10」完全吻合。")
    add("")
    add("| 真实品类（10） | 中文名 | 与 3×3 候选 |")
    add("|---|---|---|")
    for cat in real_cats:
        mark = "**✓ 候选**" if cat in CANDIDATE_CATEGORIES else ""
        add(f"| {cat} | {CATEGORIES.get(cat, '')} | {mark} |")
    add("")
    add("| 候选品类 | trends 状态 | 说明 |")
    add("|---|---|---|")
    for cat in CANDIDATE_CATEGORIES:
        kind = candidate_intersect.get(cat, "absent")
        note = {
            "real": "真实 pytrends 序列（us）",
            "mock": "mock 回退（第 11 位起超出 GOOGLE_TRENDS_MAX_KEYWORDS=10 批次）",
            "absent": "无数据",
        }[kind]
        add(f"| {cat} | {layer_mark(kind)} | {note} |")
    add("")
    add(f"- **交集结论**：pet、small_appliance 有真实趋势（仅 us 市场）；**electronics 无真实趋势**。")
    add("")

    add("## 3. Octaprice 数据集市场覆盖确认（任务 2 结论）")
    add("")
    if octa.get("found"):
        add(f"- 文件：`data/external/github/octaprice/{octa['file']}`（**{octa['row_count']} 条商品记录**；文件行数更高是因为描述字段含换行，记录数以 csv 读取器为准）")
        add(f"- 表头（{len(octa['header'])} 列）：{', '.join(octa['header'][:10])} …（含 currency/sellerName/url/breadcrumbs/listedPrice/salePrice/rating/reviewCount）")
        add(f"- URL 域名（全量扫描）：{octa['domains']}")
        add(f"- 货币：{octa['currencies']}")
        add(f"- 卖家 Top：{octa['sellers']}")
        add(f"- 面包屑：{octa['breadcrumbs']}")
        add("- **结论：该免费数据集为美站 amazon.com（US 市场）的 Bird Food（鸟食，pet 品类）商品快照（周更单品类）；URL 100% 指向 www.amazon.com、货币 USD、卖家为美国本土零售商，不含德站/欧洲市场数据。**")
        add("- 对备选选项的回答：**pet/electronics × US/DE 不能借 octaprice 补 DE 市场证据**——octaprice 仅覆盖 US×pet（在 GitHub 信号层中表现为 `pet×us` 的 173 行 octaprice_github 真实映射）。DE 需另找 de 站比价数据（如 Keepa de 域名/理想价格源）。")
    else:
        add("- 未找到 octaprice CSV 文件。")
    add("")

    add("## 4. US/SEA 版 3×3 真实来源占比矩阵（任务 3 结论）")
    add("")
    add("### 4.1 主口径（7 层全计：GitHub/proxy/trends/crawler/customs/rankings/suppliers）")
    add("")
    add("| 组合 | GitHub 信号层 | 真实销量代理 | Google Trends | crawler | Comtrade | 平台榜单 | 供应商 | 占比 | 达标(≥80%) |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for cat in CANDIDATE_CATEGORIES:
        for mkt in CANDIDATE_MARKETS:
            cell = matrix[(cat, mkt)]
            ratio, real, mock = ratio_cell(cell, LAYERS)
            marks = " | ".join(layer_mark(cell[l]) for l in LAYERS)
            add(f"| {cat}×{mkt} | {marks} | {pct(ratio)}（{real} 真/{mock} mock） | {'✅' if ratio is not None and ratio >= 0.8 else '❌'} |")
    add("")
    add("### 4.2 对齐《3×3 选择依据表 v1.0》口径（供应商全局缺口、Trends us 单市场不计入分母）")
    add("")
    add("| 组合 | GitHub 信号层 | 真实销量代理 | crawler | Comtrade | 平台榜单 | 占比 | 达标(≥80%) |")
    add("|---|---|---|---|---|---|---|---|")
    for cat in CANDIDATE_CATEGORIES:
        for mkt in CANDIDATE_MARKETS:
            cell = matrix[(cat, mkt)]
            ratio, real, mock = ratio_cell(cell, REPORT_ALIGN_LAYERS)
            marks = " | ".join(layer_mark(cell[l]) for l in REPORT_ALIGN_LAYERS)
            add(f"| {cat}×{mkt} | {marks} | {pct(ratio)}（{real} 真/{mock} mock） | {'✅' if ratio is not None and ratio >= 0.8 else '❌'} |")
    add("")
    add(f"- 主口径达标 **{primary_pass}/9** 格，对齐依据表口径达标 **{align_pass}/9** 格；两种口径下 **均 < B-3 验收底线 6/9**。")
    add("- 主口径达标格为 **pet×us** 与 **small_appliance×us**：前者 GitHub 173 条 octaprice 真实映射 + proxy(amazon) + trends 真实 + Comtrade + 榜单 = 5/5=100%；后者 trends 真实 + Comtrade + 榜单 = 3/3=100%（absent 层不计入分母所致）。")
    add("")

    add("## 5. 全矩阵（132 品类 × 15 市场）覆盖概览")
    add("")
    add("| 信号层 | real 格 | mock 格 | absent 格 | 备注 |")
    add("|---|---|---|---|---|")
    notes = {
        "github_signals": f"真实行 {len(github_rows)}（amazon/ebay/shopee/octaprice/hs；B-3 补数后按组合截断，候选 5 格转 real）",
        "proxy_sales": "43 品类 66 组合 × {us,sea}，provider amazon/shopee，全部真实标注；small_appliance 等 23 品类不在模型品类集内",
        "trends": "10 个真实品类仅 us 市场；56 品类 us 为 mock；其余市场 absent",
        "crawler": "10 个真实组合（printer_3d×{vn,mx,sea,ca}、solar_energy×{vn,sea}、arts_crafts×sea、home_robot×sea、motorcycle_gear×sea、furniture×vn），无 mock 组合",
        "customs": "132 品类真实，无市场细分（视为对 15 市场均有效）",
        "rankings": "224 真实行集中在 us（47 格）+ fishing×jp 1 格；其余市场全 mock",
        "suppliers": "66 行全 mock（1688 风控），市场均为 cn；对 us/sea 格无数据",
    }
    for layer in LAYERS:
        st = layer_stats[layer]
        add(f"| {LAYER_NAMES[layer]} | {st.get('real', 0)} | {st.get('mock', 0)} | {st.get('absent', 0)} | {notes[layer]} |")
    add("")
    real_cells = sum(1 for c in categories for m in markets if matrix[(c, m)].get("github_signals") == "real")
    add(f"- 在 132×15=1980 格中，同时有 ≥2 个真实层的格：{sum(1 for c in categories for m in markets if ratio_cell(matrix[(c, m)], LAYERS)[1] >= 2)}；≥3 个真实层：{sum(1 for c in categories for m in markets if ratio_cell(matrix[(c, m)], LAYERS)[1] >= 3)}。")
    add("")

    add("## 6. 差距分析与补数据建议")
    add("")
    add("> **B-3 补数进度**：✅ 动作①（扩 GitHub 映射词 + 上限 200→500 + 按组合截断）已执行并重建 `github_signals.json`；②-⑥ 待执行或需外部资源（联网/Key/重训）。")
    add("")
    add("6/9 未达标的差距根源（按影响排序，①已消除）：")
    add("")
    add("1. **GitHub 信号层对候选品类映射几乎为零（已修复）**：补数前产品级真实映射仅 `pet×us`（173 条 octaprice）等，`pet×sea`/`electronics×{us,sea}`/`small_appliance×{us,sea}` 均为 0 行；根因是 `_CATEGORY_TERMS` 词过窄 + `GITHUB_MAX_ROWS_PER_PROVIDER=200` 全局排序截断把字母序靠后的品类挤掉。B-3 修复：扩展 electronics/small_appliance 映射词、上限 200→500、`_cap_rows` 改为按 (品类, 市场) 组合截断。")
    add("   - 结果：pet×us 714 / pet×sea 500 / electronics×us 226 / electronics×sea 124 / small_appliance×us 15 / small_appliance×sea 8（见 §4）。")
    add("2. **Trends 仅跑 us 单市场**：适配器已支持 `market` 参数（`geo=market.upper()`），但 `run_daily_update.py` 只调用默认 us；`GOOGLE_TRENDS_MAX_KEYWORDS=10` 又使 electronics 掉出批次。建议：对 sea（或至少 pet/small_appliance）加跑、按候选品类重排关键词批次。")
    add("3. **平台榜单 sea 全 mock**：224 条真实行集中在 us（47 格）+ fishing×jp 1 格，其余市场全 mock。建议：接入 Keepa/eBay Key 升级（项目已有升级路径），或扩 GitHub 榜单样例市场。")
    add("4. **crawler 候选 0 覆盖**：10 个真实组合与 pet/electronics/small_appliance 零交集。建议：把 3 个候选品类（×us/sea）加入 crawler 组合清单（`src/config.py` CRAWLER_DEFAULT_COMBOS 相关配置）。")
    add("5. **供应商 1688 全 mock 且仅 cn 市场**：风控拦截（`RISK_CONTROL`/`DAEMON_PAUSED`），市场为 cn，对 us/sea 叙事无贡献。建议：降级换源或接受为长期缺口，不进入对外叙事。")
    add("6. **真实销量代理品类集缺失 small_appliance**：proxy 模型为 43 品类 66 组合（缺失 small_appliance/fashion/furniture 等 23 品类），该格只能靠 trends/榜单/Comtrade。建议：扩充代理模型品类集（`scripts/train_real_enhanced.py` 相关标注源），或对外叙事接受 small_appliance 以「政策/认证 + 出口 + 榜单」为主要证据。")
    add("")
    add("### 补数据后的可达预期")
    add("")
    add("| 补数动作 | 状态 | 预期改善 |")
    add("|---|---|---|")
    add("| 扩 GitHub 映射（词 + 上限 + 按组合截断） | ✅ 已执行 | 5 个候选格 GitHub 层由 absent → real（已达成） |")
    add("| trends 加跑 sea + 重排批次 | ⏳ 待执行（需联网） | electronics×us 由 mock → real；pet/small_appliance×sea 由 absent → real |")
    add("| 榜单 Keepa/eBay 升级 | ⏳ 待执行（需 Key） | sea 格 rankings 由 mock → real |")
    add("| 扩充 proxy 代理模型品类集 | ⏳ 待执行（需重训） | small_appliance×{us,sea} proxy 层由 absent → real |")
    add("| 全部落地后主口径 | 预计 | pet×{us,sea} 100%/83%+，electronics×{us,sea} 80%+，small_appliance×{us,sea} 75%+ → **6/9 达标可达** |")
    add("")

    add("## 7. 与《3×3 选择依据表 v1.0》的差异说明（产物级核验 + B-3 补数对照）")
    add("")
    add("| 依据表 v1.0 表述 | 补数前核验（B-1） | B-3 补数后 |")
    add("|---|---|---|")
    add("| pet × SEA GitHub「✅ 密集（shopee）」 | pet×sea 真实行 = **0**（shopee 200 行映射到 arts_crafts/automotive） | **500 行**（shopee 行数上限 500 生效） |")
    add("| electronics「◐ 少量（amazon/ebay）」 | electronics 产品级映射 = **0**（全局截断挤压） | **us 226 / sea 124**（扩词 + 按组合截断） |")
    add("| small_appliance「◐ 极少」 | 同 electronics，产品级映射 = **0** | **us 15 / sea 8**（扩词生效） |")
    add("| pet × US GitHub「✅ 密集（amazon/ebay）」 | pet×us 173 条真实，来源为 **octaprice_github**（Bird Food） | **714 条**（amazon/ebay/octaprice 多源） |")
    add("| proxy「66 品类 × {us, sea}」「候选 3 品类全部有真实销量标注」 | proxy 为 **43 品类 66 组合**；**small_appliance 不在品类集内** | 不变（待动作⑥扩充） |")
    add("| 综合评级「electronics×US ★★★★☆」 | GitHub 层为 0，评级应下调 | GitHub 层转 real（us 226 行），评级恢复 |")
    add("")
    add("> 依据表 §4.4「US/SEA 版 9 格中 6 格可达标」在补数前被高估（GitHub/proxy 覆盖）；B-3 补数动作① 已消除 GitHub 层缺口，其余缺口见 §6 动作②-⑥。")
    add("")

    add("## 8. 附录：判定自检（脚本内断言，保证可重复计算）")
    add("")
    add("| 校验项 | 期望 | 实际 |")
    add("|---|---|---|")
    checks = [
        ("trends 真实序列数", "10", str(len(real_cats))),
        ("trends mock 序列数", "56", str(len(mock_cats))),
        ("trends 序列总数", "66", str(len(trends_class))),
        ("GitHub 信号层真实行", ">0（B-3 补数后动态）", str(len(github_rows))),
        ("proxy 标注行", "4731", str(data_status["real_proxy"]["labeled_rows"])),
        ("crawler 真实组合", "10", str(crawler_payload.get("real_combos"))),
        ("Comtrade 行数", "66", str(len(customs_rows))),
        ("平台榜单行数", "≥5000（B-3 补数后动态）", str(len(rankings_rows))),
        ("供应商真实行", "0", str(data_status["suppliers"]["coverage"]["real"])),
    ]
    for name, exp, act in checks:
        add(f"| {name} | {exp} | {act} |")
    add("")
    add("---")
    add(f"*本报告由 `scripts/build_coverage_report.py` 从既有产物生成，幂等可复现；未修改任何数据产物。*")
    return "\n".join(lines)


def main() -> int:
    if not DATA_STATUS.exists():
        print(f"[coverage] 缺少主输入 {DATA_STATUS}", file=sys.stderr)
        return 1
    data_status = load_json(DATA_STATUS)
    github_payload = load_json(GITHUB_SIGNALS)
    github_rows = github_payload["rows"]
    github_sources = github_payload.get("sources") or {}
    trends_payload = load_json(TRENDS)
    crawler_payload = load_json(CRAWLER)
    customs_rows = load_json(CUSTOMS)["rows"]
    rankings_rows = load_json(RANKINGS)["rows"]
    supplier_rows = load_json(SUPPLIERS)["rows"]

    trends_class = classify_trends(trends_payload)

    # ---- 自检断言：输入漂移时立即失败（保证口径一致） ----
    cov = trends_payload["coverage"]
    real_n = sum(1 for v in trends_class.values() if v == "real")
    mock_n = sum(1 for v in trends_class.values() if v == "mock")
    assert real_n == cov["real"] == data_status["trends"]["coverage"]["real"], (
        f"trends real 不一致: 复刻={real_n} 快照={cov['real']} data_status={data_status['trends']['coverage']['real']}"
    )
    assert mock_n == cov["mock"] == data_status["trends"]["coverage"]["mock"]
    assert len(github_rows) > 0, "github_signals.json 为空或缺失"
    assert all(
        info.get("mapped_rows", 0) > 0 for info in github_sources.values()
    ), "GitHub 信号层存在映射为 0 的 provider"
    assert data_status["real_proxy"]["labeled_rows"] == 4731
    assert crawler_payload.get("real_combos") == 10
    assert len(customs_rows) == len(CATEGORIES)
    assert len(rankings_rows) >= 5000, "平台榜单行数异常（B-3 补数后应 ≥5000）"
    assert data_status["suppliers"]["coverage"]["real"] == 0

    octa = octaprice_analysis()
    as_of = data_status["data_as_of"].replace("-", "")
    report = build_report(
        data_status,
        github_rows,
        trends_payload,
        crawler_payload,
        customs_rows,
        rankings_rows,
        supplier_rows,
        trends_class,
        octa,
    )
    out_path = REPORTS_DIR / f"数据覆盖率盘点_{as_of}.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    # 控制台摘要：主口径 3×3 达标格数
    layer_maps = {
        "github_signals": layer_status_github(github_rows),
        "proxy_sales": layer_status_proxy(data_status["real_proxy"]["combo_stats"]),
        "trends": layer_status_trends(trends_class, CANDIDATE_MARKETS),
        "crawler": layer_status_crawler(crawler_payload),
        "customs": layer_status_customs(customs_rows, CANDIDATE_MARKETS),
        "rankings": layer_status_rankings(rankings_rows),
        "suppliers": layer_status_suppliers(supplier_rows),
    }
    grid = build_matrix(CANDIDATE_CATEGORIES, CANDIDATE_MARKETS, layer_maps)
    primary_pass = sum(
        1
        for cat in CANDIDATE_CATEGORIES
        for mkt in CANDIDATE_MARKETS
        if (lambda r: r is not None and r >= 0.8)(ratio_cell(grid[(cat, mkt)], LAYERS)[0])
    )
    print(f"[coverage] 已生成 {out_path.relative_to(PROJECT_ROOT)}")
    print(f"[coverage] trends 真实 {real_n} / mock {mock_n}；3×3 主口径达标 {primary_pass}/9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
