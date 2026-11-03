"""证据闸 + 统一证据账本（provenance ledger）。

两层职责：

1. 证据闸（既有能力）：行业事实进入 AI 结论前必须带来源、日期与状态；
2. 统一证据账本（A-1 P0-1）：任何政策 / HS / 认证 / 成本结论可一键回溯到
   原始来源与版本。字段在数据层（``normalize_provenance`` / ``serialize_evidence``）
   与序列化层（看板 / 贸易决策报告 / API）三处同源输出，并带"过期提醒"
   （生效日 + 有效期），防止引用已失效的政策或认证结论。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable

VALID_STATUS = {"已检索", "已核实", "待核实", "模拟", "verified", "pending", "mock"}

# 统一证据记录字段（顺序即文档/JSON 输出顺序）。
# 除兼容既有字段（title/key/status/url/date）外，其余为 A-1 证据账本标准字段。
PROVENANCE_FIELDS: tuple[str, ...] = (
    "key",                    # 记录唯一键
    "title",                  # 事实/结论标题
    "source",                 # 数据源（名称或原始 URL）
    "fetched_at",             # 抓取时间（ISO）
    "effective_date",         # 政策/规则生效日（ISO；无则 None）
    "expires_at",             # 过期时间（ISO；None 表示长期有效）
    "validity_days",          # 自生效日起有效期天数（用于推算 expires_at）
    "hs_version",             # HS 版本（如 "HS2022"；无则 None）
    "formula",                # 计算公式 / 统计口径
    "model_version",          # 模型版本（如 "prophet_baseline"）
    "confidence_interval",    # 置信区间 [low, high] 或字符串
    "review_status",          # 人工复核状态：未复核 / 已复核 / 复核中
    "url",                    # 可核验链接
    "status",                 # 证据闸状态（兼容既有 VALID_STATUS）
    "date",                   # 兼容旧字段（回退到 fetched_at）
)

VALID_REVIEW_STATUS = {"", "未复核", "已复核", "复核中", "待复核"}

# 政策/认证类结论默认有效期：365 天（可按条目覆盖）
DEFAULT_VALIDITY_DAYS = 365
# 即将过期阈值（天）
EXPIRING_SOON_DAYS = 30

# 旧字段名 -> 标准字段名 别名表（normalize 时回退填充）
_FIELD_ALIASES: dict[str, str] = {
    "link": "url",
    "updated_at": "fetched_at",
    "generated_at": "fetched_at",
    "captured_at": "fetched_at",
    "effectiveDate": "effective_date",
    "expiresAt": "expires_at",
    "validityDays": "validity_days",
    "hsVersion": "hs_version",
    "modelVersion": "model_version",
    "confidenceInterval": "confidence_interval",
    "reviewStatus": "review_status",
    "source_type": "source",   # 政策事件的 source_type（official/search）不覆盖 source
}


def _iso(value: Any) -> str | None:
    """把任意日期值规整为 ISO 字符串；无效输入返回 None。"""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat(timespec="seconds") if isinstance(value, datetime) else value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).isoformat(timespec="seconds")
    except ValueError:
        return None


def check_evidence(item: dict[str, Any]) -> list[str]:
    """校验一条行业事实是否满足证据闸要求。"""
    issues: list[str] = []
    source = str(item.get("source") or item.get("url") or "").strip()
    if not source:
        issues.append("缺少来源")
    date_value = item.get("date") or item.get("updated_at") or item.get("generated_at")
    if not date_value and not item.get("url"):
        issues.append("缺少日期或可核验链接")
    status = str(item.get("status") or "").strip()
    if status and status not in VALID_STATUS:
        issues.append(f"状态未按规范标注：{status}")
    return issues


def evidence_gate(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """批量校验，返回总体是否通过与逐条问题。"""
    issues_by_key: dict[str, list[str]] = {}
    valid = True
    for item in items:
        key = str(item.get("key") or item.get("title") or "item")
        issues = check_evidence(item)
        issues_by_key[key] = issues
        if issues:
            valid = False
    return {"valid": valid, "issues": issues_by_key}


def normalize_provenance(item: dict[str, Any]) -> dict[str, Any]:
    """把任意证据/结论条目规整为统一 provenance 记录（A-1 标准结构）。

    - 旧字段（link/updated_at/generated_at/...）自动映射到标准字段；
    - 缺失的标准字段填 None，保证三处输出字段名完全一致（同源）；
    - ``expires_at`` 缺失但给了 ``effective_date``/``validity_days`` 时按
      ``effective_date + validity_days`` 推算（默认 365 天）。
    """
    record: dict[str, Any] = {}
    for field in PROVENANCE_FIELDS:
        value = item.get(field)
        if value is None:
            for alias, target in _FIELD_ALIASES.items():
                if target == field and item.get(alias) is not None:
                    value = item.get(alias)
                    break
        record[field] = value

    # 兼容别名：source 缺省时回退 url/link
    if not record.get("source"):
        record["source"] = record.get("url") or None
    # fetched_at 缺省时回退 date
    if not record.get("fetched_at"):
        record["fetched_at"] = _iso(record.get("date"))
    else:
        record["fetched_at"] = _iso(record["fetched_at"])
    record["date"] = record["fetched_at"]

    record["effective_date"] = _iso(record.get("effective_date"))
    # 有效期推算
    validity_days = record.get("validity_days")
    if isinstance(validity_days, (int, float)) and validity_days > 0:
        validity_days = int(validity_days)
    elif record.get("effective_date"):
        validity_days = DEFAULT_VALIDITY_DAYS
    else:
        validity_days = None
    record["validity_days"] = validity_days
    if not record.get("expires_at") and record.get("effective_date") and validity_days:
        try:
            base = datetime.fromisoformat(str(record["effective_date"]))
            record["expires_at"] = (base + timedelta(days=validity_days)).isoformat(timespec="seconds")
        except ValueError:
            record["expires_at"] = None
    else:
        record["expires_at"] = _iso(record.get("expires_at"))

    # 复核状态规范化
    review_status = str(record.get("review_status") or "").strip()
    if review_status and review_status not in VALID_REVIEW_STATUS:
        review_status = "待复核"
    record["review_status"] = review_status

    # 数值/区间字段保持原样（None 归一）
    for field in ("hs_version", "formula", "model_version", "confidence_interval"):
        if record.get(field) is None:
            record[field] = None
    return record


def provenance_record(
    *,
    key: str | None = None,
    title: str | None = None,
    source: str | None = None,
    url: str | None = None,
    fetched_at: str | None = None,
    effective_date: str | None = None,
    expires_at: str | None = None,
    validity_days: int | None = None,
    hs_version: str | None = None,
    formula: str | None = None,
    model_version: str | None = None,
    confidence_interval: Any = None,
    review_status: str = "未复核",
    status: str = "已检索",
) -> dict[str, Any]:
    """显式构造一条标准 provenance 记录（默认未人工复核）。"""
    return normalize_provenance(
        {
            "key": key,
            "title": title,
            "source": source,
            "url": url,
            "fetched_at": fetched_at,
            "effective_date": effective_date,
            "expires_at": expires_at,
            "validity_days": validity_days,
            "hs_version": hs_version,
            "formula": formula,
            "model_version": model_version,
            "confidence_interval": confidence_interval,
            "review_status": review_status,
            "status": status,
        }
    )


def check_expiry(item: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """过期提醒：按 ``expires_at``（或生效日+有效期）判定结论是否仍可引用。

    返回 {"status": "valid"|"expiring_soon"|"expired"|"no_expiry",
          "days_left": int|None, "message": str}。
    - valid：未过期且距过期 > EXPIRING_SOON_DAYS 天；
    - expiring_soon：距过期 ≤ EXPIRING_SOON_DAYS 天（建议人工复核）；
    - expired：已过期，结论不应再引用；
    - no_expiry：无生效日/过期日（长期有效或信息不足）。
    """
    today = today or date.today()
    record = normalize_provenance(item)
    expires_raw = record.get("expires_at")
    if not expires_raw:
        return {"status": "no_expiry", "days_left": None, "message": "无有效期信息（按长期有效处理）"}
    try:
        expires = datetime.fromisoformat(str(expires_raw)).date()
    except ValueError:
        return {"status": "no_expiry", "days_left": None, "message": "有效期格式无法解析"}
    days_left = (expires - today).days
    if days_left < 0:
        return {
            "status": "expired",
            "days_left": days_left,
            "message": f"已于 {expires.isoformat()} 过期（{abs(days_left)} 天前），结论需复核或弃用",
        }
    if days_left <= EXPIRING_SOON_DAYS:
        return {
            "status": "expiring_soon",
            "days_left": days_left,
            "message": f"将于 {expires.isoformat()} 过期（剩 {days_left} 天），建议人工复核",
        }
    return {
        "status": "valid",
        "days_left": days_left,
        "message": f"有效，将于 {expires.isoformat()} 过期（剩 {days_left} 天）",
    }


def serialize_evidence(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """同源 JSON 序列化：看板与 API 输出统一走此结构（schema_version 固定）。"""
    records = [normalize_provenance(item) for item in items]
    expired = sum(1 for record in records if check_expiry(record)["status"] == "expired")
    return {
        "schema_version": 1,
        "count": len(records),
        "expired_count": expired,
        "items": records,
    }


def _expiry_flag(item: dict[str, Any], today: date | None = None) -> str:
    """给 build_evidence_section 用的紧凑过期标记（⚠ 已过期 / ⏳ 即将过期 / 空）。"""
    status = check_expiry(item, today=today)["status"]
    if status == "expired":
        return "⚠️ 已过期"
    if status == "expiring_soon":
        return "⏳ 即将过期"
    return ""


def build_evidence_section(
    items: Iterable[dict[str, Any]],
    *,
    ai_note: str = "本报告明确区分模型/统计数值与 AI 解释。",
) -> str:
    """生成报告中的证据闸 Markdown 区块（A-1：含抓取时间/生效日/有效期/复核列）。"""
    items = list(items)
    gate = evidence_gate(items)
    lines = [
        "## 证据闸",
        "",
        f"{ai_note}",
        "",
        "| 事实 | 来源 | 抓取时间 | 生效日 | 有效期 | 人工复核 | 状态 |",
        "|---|---|---|---|---|---|---|",
    ]
    if not items:
        lines.append("| 暂无行业事实 | - | - | - | - | - | - |")
    for item in items:
        record = normalize_provenance(item)
        expiry_flag = _expiry_flag(record)
        expiry_display = (
            f"{record['expires_at'] or '长期'}"
            + (f"（{expiry_flag}）" if expiry_flag else "")
        )
        title = record.get("title") or record.get("key") or "-"
        source = record.get("source") or record.get("url") or "-"
        lines.append(
            f"| {title} "
            f"| {source} "
            f"| {record['fetched_at'] or '-'} "
            f"| {record['effective_date'] or '-'} "
            f"| {expiry_display} "
            f"| {record['review_status'] or '-'} "
            f"| {record.get('status') or '-'} |"
        )
    lines.append("")
    if not gate["valid"]:
        lines.append("存在未通过校验的事实条目，AI 结论不得引用这些条目：")
        lines.append("")
        for key, issues in gate["issues"].items():
            if issues:
                lines.append(f"- {key}：{'、'.join(issues)}")
    else:
        lines.append("全部行业事实已通过证据闸校验。")
    return "\n".join(lines) + "\n"


__all__ = [
    "PROVENANCE_FIELDS",
    "build_evidence_section",
    "check_evidence",
    "check_expiry",
    "evidence_gate",
    "normalize_provenance",
    "provenance_record",
    "serialize_evidence",
]
