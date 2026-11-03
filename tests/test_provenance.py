"""A-1 统一证据账本（provenance）测试：结构、别名映射、过期提醒、同源序列化。"""

from __future__ import annotations

from datetime import date, timedelta

from src.analysis.evidence import (
    PROVENANCE_FIELDS,
    build_evidence_section,
    check_expiry,
    normalize_provenance,
    provenance_record,
    serialize_evidence,
)
from src.trade.report import _selection_markdown


def test_normalize_full_record_keeps_standard_fields() -> None:
    item = {
        "key": "k1",
        "title": "某品类关税调整",
        "source": "白宫第 14324 号行政命令",
        "url": "https://www.whitehouse.gov/example",
        "fetched_at": "2026-08-21T10:00:00Z",
        "effective_date": "2025-08-29",
        "expires_at": "2026-08-29",
        "hs_version": "HS2022",
        "formula": "rate = base + surcharge",
        "model_version": "policy_v1",
        "confidence_interval": [0.05, 0.15],
        "review_status": "已复核",
    }
    record = normalize_provenance(item)
    for field in PROVENANCE_FIELDS:
        assert field in record, f"缺少标准字段 {field}"
    assert record["source"] == "白宫第 14324 号行政命令"
    assert record["hs_version"] == "HS2022"
    assert record["review_status"] == "已复核"
    assert record["fetched_at"] is not None


def test_normalize_aliases_maps_legacy_fields() -> None:
    record = normalize_provenance(
        {
            "title": "旧格式条目",
            "link": "https://example.com/a",
            "updated_at": "2026-01-01T00:00:00",
            "generated_at": "2026-02-01T00:00:00",
        }
    )
    assert record["url"] == "https://example.com/a"
    assert record["source"] == "https://example.com/a"  # source 缺省回退 url
    # updated_at 优先于 generated_at（别名表按顺序取第一个非空）
    assert record["fetched_at"].startswith("2026-01-01")


def test_expiry_inferred_from_effective_date() -> None:
    record = normalize_provenance({"effective_date": "2026-01-01", "title": "政策"})
    assert record["validity_days"] == 365
    assert record["expires_at"] is not None
    assert record["expires_at"].startswith("2027-01-01")


def test_check_expiry_statuses() -> None:
    today = date(2026, 8, 21)
    # 已过期
    assert check_expiry({"expires_at": "2026-01-01"}, today=today)["status"] == "expired"
    # 即将过期（30 天内）
    soon = (today + timedelta(days=10)).isoformat()
    assert check_expiry({"expires_at": soon}, today=today)["status"] == "expiring_soon"
    # 有效
    far = (today + timedelta(days=120)).isoformat()
    assert check_expiry({"expires_at": far}, today=today)["status"] == "valid"
    # 无有效期
    assert check_expiry({"title": "长期条目"}, today=today)["status"] == "no_expiry"


def test_serialize_evidence_same_source_structure() -> None:
    payload = serialize_evidence(
        [
            {"title": "A", "source": "src1", "effective_date": "2020-01-01"},
            {"title": "B", "source": "src2"},
        ]
    )
    assert payload["schema_version"] == 1
    assert payload["count"] == 2
    assert payload["expired_count"] == 1  # A 已于 2021 过期
    assert all(field in payload["items"][0] for field in PROVENANCE_FIELDS)


def test_build_evidence_section_has_expiry_columns() -> None:
    markdown = build_evidence_section(
        [{"title": "事实", "source": "来源", "effective_date": "2020-01-01", "status": "已检索"}]
    )
    assert "抓取时间" in markdown
    assert "有效期" in markdown
    assert "人工复核" in markdown
    assert "⚠️ 已过期" in markdown


def test_provenance_record_defaults_unreviewed() -> None:
    record = provenance_record(title="新条目", source="官方源")
    assert record["review_status"] == "未复核"
    assert record["status"] == "已检索"
    assert record["confidence_interval"] is None


def test_report_markdown_contains_policy_expiry_warning() -> None:
    payload = {
        "generated_at": "2026-08-21T00:00:00",
        "filters": {"category": "cn_changsha_mifen", "market": "us", "model": "lgbm"},
        "recommendation": {"category": "cn_changsha_mifen", "score": 88.0},
        "trade_decision": {"risk_level": "low", "margin_pct": 12.3},
        "evidence": [{"title": "来源一", "link": "https://example.com/1", "snippet": "摘要"}],
        "policy_events": [
            {
                "code": "P1",
                "title": "某关税调整",
                "source": "官方公告",
                "effective_date": "2020-01-01",
                "description": "测试事件",
            }
        ],
        "conclusion": "结论",
        "data_status": {},
    }
    markdown = _selection_markdown(payload)
    assert "## 四、证据清单" in markdown
    assert "### 政策事件时效（过期提醒）" in markdown
    assert "⚠️ 已过期" in markdown
    assert "## 六、结论" in markdown
    assert "人工复核" in markdown
