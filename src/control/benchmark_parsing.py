"""Control benchmark parsing and scoring helpers (S1 split)."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    CATEGORY_CATALOG,
    DATA_DIR,
    PROCESSED_CSV,
    PROJECT_ROOT,
    REAL_TRAINING_CSV,
    TEST_WEEKS,
)

CONTROL_DIR = DATA_DIR / "control"
TRAIN_CSV = CONTROL_DIR / "train_data.csv"
HOLDOUT_CSV = CONTROL_DIR / "holdout_data.csv"
PROMPT_MD = CONTROL_DIR / "prompt.md"
OUTPUT_DIR = PROJECT_ROOT / "output" / "control"

# 食品品类别名表：由 132 食品 SKU 目录派生（code / 中文名 / 英文小写 / 搜索关键词），
# 剔除全部消费类目硬编码；用于把 AI 回复文本归一化回食品品类编码。
CATEGORY_ALIASES: dict[str, set[str]] = {
    code: {code, str(meta["name_cn"]), str(meta["name_en"]).lower(), str(meta["keyword"])}
    for code, meta in CATEGORY_CATALOG.items()
}


MARKET_ALIASES = {
    "us": {"us", "美国"},
    "eu": {"eu", "欧洲", "欧盟"},
    "sea": {"sea", "东南亚"},
    "jp": {"jp", "日本"},
    "ca": {"ca", "加拿大"},
    "au": {"au", "澳大利亚"},
    "uk": {"uk", "英国"},
    "kr": {"kr", "韩国"},
    "de": {"de", "德国"},
    "fr": {"fr", "法国"},
    "vn": {"vn", "越南"},
    "ru": {"ru", "俄罗斯"},
    "hu": {"hu", "匈牙利"},
    "ae": {"ae", "中东", "阿联酋"},
    "mx": {"mx", "墨西哥"},
}

INVENTORY_KEYWORDS = ("库存", "备货", "进货", "补货", "进多少", "采购量")
UNCERTAINTY_KEYWORDS = ("置信", "区间", "80%", "90%", "不确定性", "风险")
ASSUMPTION_KEYWORDS = ("假设", "局限", "前提", "简化")

_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_WEEK_RE = re.compile(r"(?:第\s*)?(\d{1,2})\s*(?:周|week|w)\b", re.IGNORECASE)
_WEEK_PREFIX_RE = re.compile(r"\b(?:week|w)\s*(\d{1,2})\b", re.IGNORECASE)


def prepare_control_split(clean_df: pd.DataFrame, test_weeks: int = TEST_WEEKS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """按品类/市场组合切分：最近 test_weeks 周为隐藏测试集，其余为训练集。"""
    train_frames: list[pd.DataFrame] = []
    holdout_frames: list[pd.DataFrame] = []
    for (_cat, _mkt), group in clean_df.groupby(["category", "market"], sort=False):
        g = group.sort_values("date").reset_index(drop=True)
        if len(g) < test_weeks + 8:
            raise ValueError(f"{_cat}/{_mkt} 只有 {len(g)} 周，不足以切分 {test_weeks} 周测试集")
        split_idx = len(g) - test_weeks
        train_frames.append(g.iloc[:split_idx])
        holdout_frames.append(g.iloc[split_idx:])
    train = pd.concat(train_frames, ignore_index=True)
    holdout = pd.concat(holdout_frames, ignore_index=True)

    expected = holdout["date"].astype(str).nunique()
    per_combo = holdout.groupby(["category", "market"], sort=False)["date"].nunique()
    if not ((per_combo == expected).all() and expected == test_weeks):
        raise ValueError("隐藏测试集日期不齐：各组合应包含相同且连续的 test_weeks 周")
    return train, holdout


def prepare_command() -> dict:
    """prepare 子命令：读取清洗数据并写出训练集/测试集。"""
    training_csv = REAL_TRAINING_CSV if REAL_TRAINING_CSV.exists() else PROCESSED_CSV
    if not training_csv.exists():
        raise FileNotFoundError(f"缺少 {PROCESSED_CSV}，请先运行 scripts/run_pipeline.py")
    clean_df = pd.read_csv(training_csv, parse_dates=["date"])
    train, holdout = prepare_control_split(clean_df)
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    train.to_csv(TRAIN_CSV, index=False)
    holdout.to_csv(HOLDOUT_CSV, index=False)
    return {
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "train_dates": f"{train['date'].min().date()} ~ {train['date'].max().date()}",
        "holdout_dates": f"{holdout['date'].min().date()} ~ {holdout['date'].max().date()}",
        "combos": train.groupby(["category", "market"], sort=False).ngroups,
    }


def _normalize_category(token: str) -> str | None:
    t = token.strip().lower()
    for code, aliases in CATEGORY_ALIASES.items():
        if t in aliases:
            return code
    return None


def _normalize_market(token: str) -> str | None:
    t = token.strip().lower()
    for code, aliases in MARKET_ALIASES.items():
        if t in aliases:
            return code
    return None


def _is_float(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


def _week_index(token: str) -> int | None:
    m = _WEEK_RE.search(token)
    if m:
        return int(m.group(1))
    m = _WEEK_PREFIX_RE.search(token)
    if m:
        return int(m.group(1))
    return None


def _tokens(line: str) -> list[str]:
    return [t.strip() for t in re.split(r"[\s\t|,;]+", line) if t.strip()]


def _pairs_in_line(line: str) -> list[tuple[str, str]]:
    """在单行文本中查找品类/市场组合（兼容中文条目与英文编码）。"""
    low = line.lower()
    cats: list[str] = []
    for code, aliases in CATEGORY_ALIASES.items():
        for alias in aliases:
            needle = alias.lower()
            if re.search(rf"\b{re.escape(needle)}\b", low) if re.fullmatch(r"[a-z_]+", needle) else (needle in low):
                cats.append(code)
                break
    mkts: list[str] = []
    for code, aliases in MARKET_ALIASES.items():
        for alias in aliases:
            needle = alias.lower()
            if re.search(rf"\b{re.escape(needle)}\b", low) if re.fullmatch(r"[a-z_]+", needle) else (needle in low):
                mkts.append(code)
                break
    if not cats or not mkts:
        return []
    return [(cats[0], mkts[0])]


def _parse_row_tokens(tokens: list[str], holdout_dates: list[str]) -> dict | None:
    category = market = None
    date_str = None
    value = None
    date_pos = None
    for idx, token in enumerate(tokens):
        if category is None and _normalize_category(token):
            category = _normalize_category(token)
        elif market is None and _normalize_market(token):
            market = _normalize_market(token)
        elif date_str is None and _DATE_RE.fullmatch(token):
            date_str = token
            date_pos = idx
        elif date_str is None and _week_index(token):
            week = _week_index(token)
            if 1 <= week <= len(holdout_dates):
                date_str = holdout_dates[week - 1]
                date_pos = idx
    if category is None or market is None or date_str is None:
        return None
    for token in tokens[date_pos + 1 :]:
        if _is_float(token) and not _DATE_RE.fullmatch(token):
            value = float(token)
            break
    if value is None:
        return None
    return {"category": category, "market": market, "date": date_str, "value": value}


def _column_role(header: str) -> str | None:
    name = header.lower().strip()
    if "categor" in name or "品类" in name:
        return "category"
    if "market" in name or "市场" in name:
        return "market"
    if "date" in name or "日期" in name or "week" in name or "周" in name:
        return "date"
    if any(k in name for k in ("sales", "pred", "yhat", "forecast", "销量", "预测", "value", "volume", "需求")):
        return "value"
    return None


def _parse_csv_block(lines: list[str], holdout_dates: list[str]) -> list[dict]:
    rows = list(csv.reader(io.StringIO("\n".join(lines))))
    header_idx = None
    roles: dict[int, str] = {}
    for i, row in enumerate(rows[:6]):
        roles = {j: _column_role(cell) for j, cell in enumerate(row) if _column_role(cell)}
        if "category" in roles.values() and "market" in roles.values() and "date" in roles.values():
            header_idx = i
            break
    if header_idx is None:
        return []
    results: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows[header_idx + 1 :]:
        if not row:
            continue
        category = market = date_str = None
        value = None
        for j, cell in enumerate(row):
            cell = cell.strip()
            role = roles.get(j)
            if role == "category" and _normalize_category(cell):
                category = _normalize_category(cell)
            elif role == "market" and _normalize_market(cell):
                market = _normalize_market(cell)
            elif role == "date":
                if _DATE_RE.fullmatch(cell):
                    date_str = cell
                else:
                    week = _week_index(cell)
                    if week and 1 <= week <= len(holdout_dates):
                        date_str = holdout_dates[week - 1]
            elif role == "value" and _is_float(cell):
                value = float(cell)
        if category is None or market is None or date_str is None or value is None:
            continue
        key = (category, market, date_str)
        if key in seen:
            continue
        seen.add(key)
        results.append({"category": category, "market": market, "date": date_str, "value": value})
    return results


def extract_forecast_table(text: str, holdout_dates: list[str]) -> list[dict]:
    """从回复中提取预测表，兼容 CSV 代码块、Markdown 表格与纯文本行。"""
    lines = text.splitlines()

    # 1) CSV/代码块
    fenced: list[list[str]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("```"):
            j = i + 1
            block: list[str] = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                block.append(lines[j])
                j += 1
            fenced.append(block)
            i = j + 1
        else:
            i += 1
    for block in fenced:
        parsed = _parse_csv_block(block, holdout_dates)
        if parsed:
            return parsed

    # 2) Markdown 表格
    tables: list[list[list[str]]] = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [t.strip() for t in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", cell.replace(" ", "")) for cell in cells):
                    rows.append(cells)
                i += 1
            tables.append(rows)
        else:
            i += 1
    for table in tables:
        if len(table) < 2:
            continue
        parsed: list[dict] = []
        seen: set[tuple[str, str, str]] = set()
        for row in table[1:]:
            item = _parse_row_tokens(row, holdout_dates)
            if not item:
                continue
            key = (item["category"], item["market"], item["date"])
            if key in seen:
                continue
            seen.add(key)
            parsed.append(item)
        if parsed:
            return parsed

    # 3) 纯文本行兜底
    parsed = []
    seen = set()
    for line in lines:
        item = _parse_row_tokens(_tokens(line), holdout_dates)
        if not item:
            continue
        key = (item["category"], item["market"], item["date"])
        if key in seen:
            continue
        seen.add(key)
        parsed.append(item)
    return parsed


def parse_recommendations(text: str) -> list[tuple[str, str]]:
    """尽力提取 Top 5 选品建议中的 (品类, 市场) 对，解析失败返回空列表。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.search(r"(top\s*5|top5|选品建议|选品推荐|推荐建议)", line, re.IGNORECASE) and len(line) < 100:
            start = i
            break
    if start is None:
        return []
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line in lines[start : start + 120]:
        for pair in _pairs_in_line(line):
            if pair not in seen:
                seen.add(pair)
                pairs.append(pair)
        if len(pairs) >= 5:
            break
    return pairs


def _section_body(text: str, patterns: tuple[str, ...]) -> str:
    """Return text under the first heading whose title contains a pattern."""
    start = None
    for match in re.finditer(r"(?im)^\s*#{1,6}\s+([^\n]+)", text):
        title = match.group(1)
        if any(pattern.lower() in title.lower() for pattern in patterns):
            start = match.start()
            break
    if start is None:
        return ""
    heading_end = match.end()
    tail = text[heading_end:]
    next_heading = re.search(r"(?m)^\s*#{1,6}\s+", tail)
    end = heading_end + (next_heading.start() if next_heading else len(tail))
    body = text[heading_end:end]
    body = re.sub(r"(?m)^\s*\|.*$", "", body)
    return body.strip()


def _has_heading(text: str, patterns: tuple[str, ...]) -> bool:
    return any(
        any(pattern.lower() in title.lower() for pattern in patterns)
        for title in re.findall(r"(?im)^\s*#{1,6}\s+([^\n]+)", text)
    )


def section_completeness(text: str, holdout_dates: list[str]) -> dict[str, object]:
    """Check that all four mandatory response sections contain real content."""
    forecast_rows = extract_forecast_table(text, holdout_dates)
    recommendations = parse_recommendations(text)
    insight_body = _section_body(text, ("核心洞察", "核心观察", "core insight"))
    method_body = _section_body(
        text,
        ("方法与不确定性", "方法", "不确定性", "假设", "局限"),
    )
    checks = {
        "core_insights": bool(
            insight_body and len(insight_body) >= 10 and re.search(r"\d", insight_body)
        ),
        "forecast": bool(forecast_rows)
        and _has_heading(
            text, ("未来 12 周销量预测", "销量预测", "预测表")
        ),
        "top5": _has_heading(text, ("Top 5", "Top5", "选品建议"))
        and len(recommendations) >= 5,
        "method": bool(
            method_body and len(method_body) >= 10 and re.search(r"\d", method_body)
        ),
    }
    missing = [key for key, ok in checks.items() if not ok]
    return {
        **checks,
        "complete": not missing,
        "missing": missing,
        "forecast_rows": len(forecast_rows),
        "top5_count": len(recommendations),
    }


def check_number_grounded(value: float, train_values: np.ndarray, tolerance: float = 0.05) -> bool:
    """判断数字是否能在训练数据原始值中找到（用于幻觉核验的第一道筛子）。"""
    if train_values.size == 0:
        return False
    return bool(np.any(np.abs(train_values - value) <= tolerance))


def extract_numeric_claims(text: str) -> list[dict]:
    """提取洞察/建议正文中的数字（排除表格与日期），供人工复核。"""
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.S)
    cleaned = "\n".join(
        line for line in cleaned.splitlines() if not line.lstrip().startswith("|")
    )
    cleaned = re.sub(r"\d{4}-\d{2}-\d{2}", " ", cleaned)
    cleaned = re.sub(r"\d{4}年\d{1,2}月", " ", cleaned)

    claims: list[dict] = []
    for m in re.finditer(r"(?<!\d)(\d{1,4}(?:\.\d{1,3})?)(%?)(?![.\d])", cleaned):
        raw = m.group(1)
        value = float(raw)
        percent = bool(m.group(2))
        if not percent and 1900 <= value <= 2100:
            continue
        context = " ".join(cleaned[max(0, m.start() - 20) : m.end() + 20].split())
        claims.append({"value": value, "percent": percent, "context": context})
    return claims


def _combo_metrics(actual: pd.Series, pred: pd.Series) -> dict:
    actual = actual.astype(float)
    pred = pred.astype(float)
    mape = float(np.mean(np.abs((actual - pred) / actual)) * 100)
    mae = float(np.mean(np.abs(actual - pred)))
    return {"mape": round(mape, 4), "mae": round(mae, 4)}


def _top_combos(
    recs: pd.DataFrame,
    allowed: set[tuple[str, str]] | None = None,
    n: int = 5,
) -> list[tuple[str, str]]:
    """从系统推荐表取 Top N；lite 模式时先过滤到对照组合。"""
    if recs is None or recs.empty:
        return []
    frame = recs.copy()
    if allowed is not None:
        mask = frame.apply(
            lambda row: (str(row["category"]), str(row["market"])) in allowed,
            axis=1,
        )
        frame = frame[mask]
    return list(
        zip(
            frame["category"].astype(str),
            frame["market"].astype(str),
            strict=False,
        )
    )[:n]


def _actual_top5(holdout_df: pd.DataFrame) -> list[tuple[str, str]]:
    """用隐藏期实际销量首末周增长率排序，取真实 Top 5。"""
    if holdout_df is None or holdout_df.empty:
        return []
    rows: list[tuple[float, str, str]] = []
    for (cat, mkt), group in holdout_df.groupby(
        ["category", "market"], sort=False
    ):
        group = group.sort_values("date").reset_index(drop=True)
        first = float(group["sales_volume"].iloc[0])
        last = float(group["sales_volume"].iloc[-1])
        if first != 0:
            rows.append((last / first - 1.0, str(cat), str(mkt)))
    rows.sort(key=lambda item: item[0], reverse=True)
    return [(cat, mkt) for _, cat, mkt in rows[:5]]


def _ground_claim(
    claim: dict,
    train_df: pd.DataFrame,
    fallback_values: np.ndarray,
) -> tuple[bool, tuple[str, str] | None]:
    """按 claim 上下文识别品类/市场，只用该组合训练数字核验。"""
    pairs = _pairs_in_line(str(claim.get("context") or ""))
    if pairs:
        cat, mkt = pairs[0]
        subset = train_df[
            (train_df["category"] == cat) & (train_df["market"] == mkt)
        ]
        if not subset.empty:
            numeric = subset.select_dtypes(include=[np.number])
            if not numeric.empty:
                values = numeric.to_numpy(dtype=float).ravel()
                return check_number_grounded(claim["value"], values), (cat, mkt)
    return check_number_grounded(claim["value"], fallback_values), None


def score_response(
    text: str,
    holdout_df: pd.DataFrame,
    train_df: pd.DataFrame,
    system_top5: list[tuple[str, str]],
    actual_top5: list[tuple[str, str]] | None = None,
    model: str = "sample",
    run: int = 1,
) -> dict:
    """对单次 AI 回复执行完整评分。"""
    holdout = holdout_df.copy()
    if pd.api.types.is_datetime64_any_dtype(holdout["date"]):
        holdout["date"] = holdout["date"].dt.strftime("%Y-%m-%d")
    else:
        holdout["date"] = holdout["date"].astype(str)
    holdout_dates = sorted(holdout["date"].unique().tolist())
    raw_rows = extract_forecast_table(text, holdout_dates)
    sections = section_completeness(text, holdout_dates)

    holdout_date_set = set(holdout_dates)
    pred_rows = [r for r in raw_rows if r["date"] in holdout_date_set]
    outside = [r for r in raw_rows if r["date"] not in holdout_date_set]
    invalid = len(outside) + sum(1 for r in pred_rows if r["value"] < 0 or not np.isfinite(r["value"]))

    pred_df = pd.DataFrame(pred_rows)
    if pred_df.empty:
        pred_df = pd.DataFrame(columns=["category", "market", "date", "value"])
    pred_df = pred_df.drop_duplicates(["category", "market", "date"], keep="first")

    merged = holdout.merge(
        pred_df.rename(columns={"value": "predicted"}),
        on=["category", "market", "date"],
        how="left",
    )
    valid = merged[merged["predicted"].notna() & (merged["predicted"] >= 0)]

    total_cells = int(len(holdout_df))
    coverage = round(len(valid) / total_cells, 4) if total_cells else 0.0

    per_combo: list[dict] = []
    for (cat, mkt), g in valid.groupby(["category", "market"], sort=False):
        per_combo.append(
            {
                "category": cat,
                "market": mkt,
                "n": int(len(g)),
                **{k: round(v, 4) for k, v in _combo_metrics(g["sales_volume"], g["predicted"]).items()},
            }
        )
    mape_mean = float(np.mean([c["mape"] for c in per_combo])) if per_combo else None
    mae_mean = float(np.mean([c["mae"] for c in per_combo])) if per_combo else None
    pooled = (
        _combo_metrics(valid["sales_volume"], valid["predicted"])
        if len(valid)
        else {"mape": None, "mae": None}
    )

    claims = extract_numeric_claims(text)
    train_num = train_df.select_dtypes(include=[np.number])
    fallback_values = (
        train_num.to_numpy(dtype=float).ravel() if not train_num.empty else np.array([])
    )
    for claim in claims:
        claim["grounded"], scope_combo = _ground_claim(
            claim,
            train_df,
            fallback_values,
        )
        claim["scope_combo"] = list(scope_combo) if scope_combo else None
    ungrounded = [c for c in claims if not c["grounded"]]

    pairs = parse_recommendations(text)
    ai_set = set(pairs)
    system_set = set(system_top5)
    actual_set = set(actual_top5 or [])
    reference_set = system_set | actual_set
    hits_system = len(ai_set & system_set)
    hits_actual = len(ai_set & actual_set)
    hits = len(ai_set & reference_set)
    jaccard = (
        round(hits / len(ai_set | reference_set), 4)
        if (ai_set | reference_set)
        else 0.0
    )

    return {
        "model": model,
        "run": run,
        "sections": sections,
        "complete": bool(sections["complete"]),
        "forecast_cells": int(len(valid)),
        "coverage": coverage,
        "invalid_cells": int(invalid),
        "mape_macro": round(mape_mean, 4) if mape_mean is not None else None,
        "mae_macro": round(mae_mean, 4) if mae_mean is not None else None,
        "mape_pooled": pooled["mape"],
        "mae_pooled": pooled["mae"],
        "per_combo": per_combo,
        "recommendations": pairs,
        "recommendation_hits": int(hits),
        "recommendation_hits_system": int(hits_system),
        "recommendation_hits_actual": int(hits_actual),
        "recommendation_matches_system": sorted(ai_set & system_set),
        "recommendation_matches_actual": sorted(ai_set & actual_set),
        "system_top5": sorted(system_top5),
        "actual_top5": sorted(actual_top5 or []),
        "recommendation_jaccard": jaccard,
        "has_inventory": any(k in text for k in INVENTORY_KEYWORDS),
        "has_uncertainty": any(k in text for k in UNCERTAINTY_KEYWORDS),
        "has_assumptions": any(k in text for k in ASSUMPTION_KEYWORDS),
        "grounding": {
            "claims_total": len(claims),
            "claims_ungrounded": len(ungrounded),
            "candidates": claims,
            "ungrounded_samples": ungrounded[:20],
        },
    }
