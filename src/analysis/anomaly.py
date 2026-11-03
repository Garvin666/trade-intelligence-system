"""异常检测：用户数据离群行与每日销量/价格序列异常。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from src.config import ANOMALIES_LATEST_JSON, ANOMALIES_OUTPUT_DIR


def detect_anomalies(
    df: pd.DataFrame,
    numeric_cols: list[str] | None = None,
    *,
    contamination: float = 0.05,
    method: str = "auto",
) -> list[dict[str, Any]]:
    """对数值列做异常检测，返回异常行（位置、得分、取值与列名）。"""
    if df is None or df.empty:
        return []
    numeric_cols = numeric_cols or [
        col for col in df.select_dtypes(include=[np.number]).columns
    ]
    numeric_cols = [
        col for col in numeric_cols if df[col].notna().sum() >= 5
    ]
    if not numeric_cols:
        return []

    matrix = df[numeric_cols].copy()
    matrix = matrix.fillna(matrix.median(numeric_only=True))
    scaled = StandardScaler().fit_transform(matrix)

    try:
        from pyod.models.iforest import IForest

        model = IForest(contamination=contamination, random_state=42)
        model.fit(scaled)
        scores = np.asarray(model.decision_function(scaled), dtype=float)
        labels = np.asarray(model.labels_, dtype=int)
        used_method = "pyod_iforest"
    except Exception:  # noqa: BLE001 - 可选依赖缺失时回退 sklearn
        try:
            model = IsolationForest(contamination=contamination, random_state=42)
            model.fit(scaled)
            scores = -np.asarray(model.score_samples(scaled), dtype=float)
            labels = (np.asarray(model.predict(scaled)) == -1).astype(int)
            used_method = "sklearn_isolation_forest"
        except Exception:  # noqa: BLE001 - 环境异常时回退稳健 z-score
            centered = np.abs(scaled - scaled.mean(axis=0))
            scores = centered.mean(axis=1)
            threshold = max(2.0, float(np.percentile(scores, 100 * (1 - contamination))))
            labels = (scores >= threshold).astype(int)
            used_method = "robust_zscore"

    rows: list[dict[str, Any]] = []
    for position in range(len(matrix)):
        if labels[position] != 1:
            continue
        rows.append(
            {
                "position": int(position),
                "index": str(matrix.index[position]),
                "score": float(scores[position]),
                "method": used_method,
                "columns": numeric_cols,
                "values": {
                    col: float(matrix.iloc[position][col])
                    for col in numeric_cols
                },
            }
        )
    return sorted(rows, key=lambda row: -row["score"])[:50]


def detect_series_anomalies(
    clean_df: pd.DataFrame,
    value_cols: tuple[str, ...] = ("sales_volume", "price_median"),
) -> list[dict[str, Any]]:
    """按品类 × 市场对销量/价格序列做异常检测。"""
    if clean_df is None or clean_df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for (category, market), group in clean_df.groupby(["category", "market"]):
        group = group.sort_values("date")
        for column in value_cols:
            if column not in group.columns:
                continue
            frame = pd.DataFrame(
                {
                    "date": group["date"],
                    "value": pd.to_numeric(group[column], errors="coerce"),
                }
            ).dropna()
            if len(frame) < 10:
                continue
            anomalies = detect_anomalies(
                frame,
                numeric_cols=["value"],
                contamination=0.05,
            )
            for item in anomalies:
                date_value = frame.iloc[item["position"]]["date"]
                rows.append(
                    {
                        "category": category,
                        "market": market,
                        "column": column,
                        "date": str(pd.Timestamp(date_value).date()),
                        "value": round(float(item["values"]["value"]), 2),
                        "score": round(float(item["score"]), 4),
                        "method": item["method"],
                    }
                )
    return sorted(rows, key=lambda row: -row["score"])[:100]


def build_anomalies_payload(clean_df: pd.DataFrame) -> dict[str, Any]:
    rows = detect_series_anomalies(clean_df)
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "date": datetime.now().date().isoformat(),
        "fallback_used": False,
        "rows": rows,
        "source_count": len(rows),
        "method": "pyod_iforest|sklearn_isolation_forest",
    }


def save_latest_anomalies(payload: dict[str, Any]) -> Path:
    ANOMALIES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ANOMALIES_LATEST_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return ANOMALIES_LATEST_JSON


def load_latest_anomalies() -> dict[str, Any]:
    if not ANOMALIES_LATEST_JSON.exists():
        return {"enabled": False, "rows": [], "source_count": 0}
    try:
        payload = json.loads(ANOMALIES_LATEST_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"enabled": False, "rows": [], "source_count": 0}
    payload.setdefault("rows", [])
    payload.setdefault("source_count", 0)
    payload["enabled"] = True
    return payload


def anomalies_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(payload.get("generated_at")),
        "updated_at": payload.get("generated_at"),
        "date": payload.get("date"),
        "fallback_used": bool(payload.get("fallback_used")),
        "rows": int(payload.get("source_count") or 0),
        "snapshot": "output/anomalies/latest.json",
    }


__all__ = [
    "anomalies_status",
    "build_anomalies_payload",
    "detect_anomalies",
    "detect_series_anomalies",
    "load_latest_anomalies",
    "save_latest_anomalies",
]
