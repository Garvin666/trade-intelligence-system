"""把联网证据回填到对照组真实结果文件（默认不调用外部 API）。

用法：
    python scripts\\backfill_control_real.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CONTROL_OUTPUT_DIR, OUTPUT_DIR  # noqa: E402
from src.data.github_datasets import (  # noqa: E402
    build_github_real_results,
    build_github_signals,
    github_real_result_rows,
)
from src.data.hf_datasets import (  # noqa: E402
    build_hf_real_results,
    build_hf_signals,
    hf_real_result_rows,
)


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def build_real_results() -> list[dict]:
    """从 trends / rankings / crawler 快照聚合真实证据行。"""
    rows: list[dict] = []
    trends = _load(OUTPUT_DIR / "trends" / "latest.json")
    for item in trends.get("rows") or []:
        rows.append(
            {
                "source_type": "google_trends",
                "category": item.get("category", ""),
                "market": item.get("market", ""),
                "keyword": item.get("keyword", ""),
                "value": item.get("value"),
                "provider": trends.get("provider", ""),
                "fallback_used": trends.get("fallback_used", True),
                "url": "",
                "date": item.get("date", ""),
            }
        )
    rankings = _load(OUTPUT_DIR / "platform_rankings" / "latest.json")
    for item in rankings.get("rows") or []:
        rows.append(
            {
                "source_type": "platform_ranking",
                "category": item.get("category", ""),
                "market": item.get("market", ""),
                "keyword": "",
                "value": item.get("rank"),
                "provider": item.get("platform", ""),
                "fallback_used": item.get("fallback_used", True),
                "url": item.get("source", ""),
                "date": item.get("date", ""),
            }
        )
    crawler = _load(OUTPUT_DIR / "crawler" / "latest.json")
    for item in crawler.get("combos") or []:
        rows.append(
            {
                "source_type": "crawler_signal",
                "category": item.get("category", ""),
                "market": item.get("market", ""),
                "keyword": item.get("keyword", ""),
                "value": item.get("pageview_trend_pct"),
                "provider": crawler.get("provider", ""),
                "fallback_used": crawler.get("fallback_used", True),
                "url": "",
                "date": crawler.get("date", ""),
            }
        )
    github_payload = build_github_signals()
    build_github_real_results(payload=github_payload)
    rows.extend(github_real_result_rows(github_payload))
    try:
        hf_payload = build_hf_signals()
        build_hf_real_results(payload=hf_payload)
        rows.extend(hf_real_result_rows(hf_payload))
    except FileNotFoundError as exc:
        print(f"[warn] HF 公开数据集信号跳过（数据缺失）：{exc}")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="回填对照组真实结果")
    parser.add_argument(
        "--output",
        type=Path,
        default=CONTROL_OUTPUT_DIR / "real_results.csv",
        help="输出 CSV 路径",
    )
    args = parser.parse_args(argv)

    import csv

    rows = build_real_results()
    seen: set[tuple] = set()
    unique_rows: list[dict] = []
    for row in rows:
        key = tuple(
            row.get(field)
            for field in (
                "source_type",
                "category",
                "market",
                "keyword",
                "value",
                "provider",
                "fallback_used",
                "url",
                "date",
            )
        )
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_type",
                "category",
                "market",
                "keyword",
                "value",
                "provider",
                "fallback_used",
                "url",
                "date",
            ],
        )
        writer.writeheader()
        writer.writerows(unique_rows)
    print(f"已写入 {args.output}，共 {len(rows)} 条真实证据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
