"""Regenerate recommendations using the per-combo best-MAPE forecast.

Reads existing processed/forecast/metrics artifacts and rewrites
models/recommendations.csv without retraining any model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402

from src.config import (  # noqa: E402
    FORECAST_CSV,
    METRICS_JSON,
    PROCESSED_CSV,
    RECOMMEND_CSV,
)
from src.models.recommend import (  # noqa: E402
    RecommendationEngine,
    select_best_model_forecast,
)
from src.trade.opportunity import build_opportunity_lookup  # noqa: E402


def main() -> int:
    if not (PROCESSED_CSV.exists() and FORECAST_CSV.exists()):
        print("processed or forecast CSV missing; run the pipeline first", file=sys.stderr)
        return 2

    history = pd.read_csv(PROCESSED_CSV, encoding="utf-8-sig")
    forecast = pd.read_csv(FORECAST_CSV, encoding="utf-8-sig")
    baseline_fc = forecast[forecast["model"] == "prophet_baseline"]
    advanced_fc = forecast[forecast["model"] == "lightgbm_advanced"]
    if baseline_fc.empty or advanced_fc.empty:
        print("forecast.csv must contain prophet_baseline and lightgbm_advanced", file=sys.stderr)
        return 2

    metrics = (
        json.loads(METRICS_JSON.read_text(encoding="utf-8"))
        if METRICS_JSON.exists()
        else {}
    )
    best_fc = select_best_model_forecast(
        baseline_fc,
        advanced_fc,
        metrics.get("baseline", []),
        metrics.get("advanced", []),
    )
    recommendations = RecommendationEngine().build(
        history,
        best_fc,
        opportunity=build_opportunity_lookup(),
    )
    RECOMMEND_CSV.parent.mkdir(parents=True, exist_ok=True)
    recommendations.to_csv(RECOMMEND_CSV, index=False, encoding="utf-8-sig")
    print(f"recommendations={len(recommendations)} rows forecast={len(best_fc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
