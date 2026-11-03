"""Real evidence aggregation for the merged backend.

Existing repo artifacts (GitHub platform samples, Wikimedia crawler snapshots,
trends rows and customs snapshots) are normalized into a per-category/market
evidence table. Mock/offline rows are counted separately and never merged into
the real evidence score.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import (
    CRAWLER_LATEST_JSON,
    CUSTOMS_LATEST_JSON,
    GITHUB_REAL_RESULTS_CSV,
    OUTPUT_DIR,
    TRENDS_LATEST_JSON,
)

REAL_OUTPUT_DIR = OUTPUT_DIR / "real"
STATUS_JSON = REAL_OUTPUT_DIR / "status.json"
VALIDATION_JSON = REAL_OUTPUT_DIR / "validation.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_github_real() -> list[dict[str, Any]]:
    if not GITHUB_REAL_RESULTS_CSV.exists():
        return []
    try:
        import csv

        with GITHUB_REAL_RESULTS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error):
        return []


def load_crawler_combos() -> list[dict[str, Any]]:
    return _read_json(CRAWLER_LATEST_JSON).get("combos", [])


def load_trends_rows() -> list[dict[str, Any]]:
    return _read_json(TRENDS_LATEST_JSON).get("rows", [])


def load_customs_rows() -> list[dict[str, Any]]:
    return _read_json(CUSTOMS_LATEST_JSON).get("rows", [])


def _median(values: list[float]) -> float | None:
    clean = [float(value) for value in values if value not in (None, "", "null")]
    return round(statistics.median(clean), 2) if clean else None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _combo_key(category: Any, market: Any) -> tuple[str, str]:
    return str(category or "").lower(), str(market or "").lower()


def build_validation() -> dict[str, Any]:
    github = load_github_real()
    crawler = load_crawler_combos()
    trends = load_trends_rows()
    customs = load_customs_rows()

    combos: set[tuple[str, str]] = set()
    for row in github:
        combos.add(_combo_key(row.get("category"), row.get("market")))
    for row in crawler:
        combos.add(_combo_key(row.get("category"), row.get("market")))
    for row in trends:
        combos.add(_combo_key(row.get("category"), row.get("market")))
    for row in customs:
        combos.add(_combo_key(row.get("category"), row.get("market")))

    rows: list[dict[str, Any]] = []
    for category, market in sorted(combos):
        github_rows = [
            row
            for row in github
            if _combo_key(row.get("category"), row.get("market")) == (category, market)
        ]
        crawler_combo = next(
            (
                row
                for row in crawler
                if _combo_key(row.get("category"), row.get("market")) == (category, market)
            ),
            None,
        )
        trends_rows = [
            row
            for row in trends
            if _combo_key(row.get("category"), row.get("market")) == (category, market)
        ]
        customs_rows = [
            row
            for row in customs
            if _combo_key(row.get("category"), row.get("market")) == (category, market)
        ]

        real_github = [row for row in github_rows if not _truthy(row.get("fallback_used"))]
        real_trends = [row for row in trends_rows if not _truthy(row.get("fallback_used"))]
        real_customs = [row for row in customs_rows if not _truthy(row.get("fallback_used"))]
        crawler_real = bool(
            crawler_combo
            and not _truthy(crawler_combo.get("fallback_used"))
            and int(crawler_combo.get("source_count") or 0) >= 2
        )

        evidence_score = None
        if crawler_real:
            evidence_score = round(
                max(0.0, min(100.0, 50.0 + float(crawler_combo.get("pageview_trend_pct") or 0) * 1.2)),
                1,
            )

        rows.append(
            {
                "category": category,
                "market": market,
                "evidence_score": evidence_score,
                "evidence_available": evidence_score is not None,
                "github_real_rows": len(real_github),
                "trends_real_rows": len(real_trends),
                "customs_real_rows": len(real_customs),
                "crawler_real": crawler_real,
                "price_median_usd": _median(
                    [row.get("value") for row in github_rows if row.get("keyword") == "final_price"]
                ),
                "rating_median": _median(
                    [row.get("value") for row in github_rows if row.get("keyword") == "rating"]
                ),
                "bestseller_rank_median": _median(
                    [row.get("value") for row in github_rows if row.get("keyword") == "root_bs_rank"]
                ),
                "sources": {
                    "github": len(github_rows),
                    "crawler": 1 if crawler_combo else 0,
                    "trends": len(trends_rows),
                    "customs": len(customs_rows),
                },
            }
        )

    real_counts = {
        "github": sum(1 for row in github if not _truthy(row.get("fallback_used"))),
        "crawler": sum(
            1
            for combo in crawler
            if not combo.get("fallback_used") and int(combo.get("source_count") or 0) >= 2
        ),
        "trends": sum(1 for row in trends if not _truthy(row.get("fallback_used"))),
        "customs": sum(1 for row in customs if not _truthy(row.get("fallback_used"))),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "combos": len(rows),
        "real_counts": real_counts,
        "evidence_available_combos": sum(1 for row in rows if row["evidence_available"]),
        "rows": rows,
    }


def build_status(validation: dict[str, Any] | None = None) -> dict[str, Any]:
    validation = validation or build_validation()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if validation["evidence_available_combos"] else "no_real_evidence",
        "combos": validation["combos"],
        "real_counts": validation["real_counts"],
        "evidence_available_combos": validation["evidence_available_combos"],
        "mock_isolated": True,
        "note": "真实证据与 mock/离线行分开统计；mock 不进入证据分。",
        "validation_file": str(VALIDATION_JSON),
    }


def save_real_validation() -> dict[str, Any]:
    REAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation = build_validation()
    VALIDATION_JSON.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    status = build_status(validation)
    STATUS_JSON.write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return status


def load_real_status() -> dict[str, Any]:
    if STATUS_JSON.exists():
        try:
            return json.loads(STATUS_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return build_status()
