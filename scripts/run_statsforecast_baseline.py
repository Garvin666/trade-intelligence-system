"""Compute StatsForecast baseline metrics from the current clean dataset.

This is intentionally lighter than a full pipeline rerun: it only evaluates
AutoETS on the existing processed CSV and merges the rows into metrics.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import METRICS_JSON, PROCESSED_CSV  # noqa: E402
from src.models.statsforecast_baseline import evaluate_all  # noqa: E402


def main() -> int:
    if not PROCESSED_CSV.exists():
        print(f"未找到清洗数据：{PROCESSED_CSV}")
        return 1
    df = pd.read_csv(PROCESSED_CSV, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    rows = evaluate_all(df)
    if rows.empty:
        print("StatsForecast 不可用或数据不足，未写入 metrics.json")
        return 0
    metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    metrics["statsforecast"] = rows.to_dict(orient="records")
    METRICS_JSON.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    avg_mape = float(rows["mape"].mean())
    print(
        f"OK: StatsForecast 基线已写入 metrics.json "
        f"({len(rows)} 行，平均 MAPE {avg_mape:.2f}%)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
