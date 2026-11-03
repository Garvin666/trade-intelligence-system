"""自动 EDA：摘要统计、profile 报告、异常行与 A/B 检验。"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.analysis.anomaly import detect_anomalies
from src.analysis.stats import run_ab_tests
from src.config import EDA_OUTPUT_DIR


def _profile_report(
    df: pd.DataFrame,
    title: str,
    out_path: Path,
) -> tuple[bool, str]:
    """生成 profile HTML；fg-data-profiling 优先，旧 ydata_profiling 兼容。"""
    try:
        from data_profiling import ProfileReport

        library = "fg-data-profiling"
    except ImportError:
        try:
            from ydata_profiling import ProfileReport

            library = "ydata-profiling"
        except ImportError:
            return False, "unavailable"
    try:
        profile = ProfileReport(df, title=title, minimal=True)
        profile.to_file(str(out_path))
        return True, library
    except Exception as exc:  # noqa: BLE001 - profile 生成失败不阻塞摘要
        return False, str(exc)


def build_eda_report(
    df: pd.DataFrame,
    title: str = "数据体检报告",
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """统一 EDA 入口，返回摘要、列统计、异常行、A/B 与 profile 路径。"""
    output_dir = Path(output_dir or EDA_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    if df is None or df.empty:
        return {
            "title": title,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "summary": {"rows": 0, "columns": 0},
            "columns": [],
            "anomalies": [],
            "ab_tests": [],
            "html_report": None,
            "library": None,
        }

    numeric_cols = [
        col for col in df.select_dtypes(include=["number"]).columns
    ]
    summary = {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "missing_cells": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "numeric_columns": numeric_cols,
        "categorical_columns": [
            col for col in df.columns if col not in numeric_cols
        ][:30],
        "memory_kb": round(float(df.memory_usage(deep=True).sum()) / 1024, 1),
    }
    columns: list[dict[str, Any]] = []
    for column in df.columns[:30]:
        series = df[column]
        entry: dict[str, Any] = {
            "column": column,
            "dtype": str(series.dtype),
            "missing": int(series.isna().sum()),
            "unique": int(series.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(series):
            entry["mean"] = round(float(series.mean()), 3)
            entry["min"] = round(float(series.min()), 3)
            entry["max"] = round(float(series.max()), 3)
        columns.append(entry)

    html_path = output_dir / (
        f"eda_{hashlib.md5(title.encode('utf-8')).hexdigest()[:10]}.html"
    )
    generated, library = _profile_report(df, title, html_path)
    return {
        "title": title,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": summary,
        "columns": columns,
        "anomalies": detect_anomalies(df),
        "ab_tests": run_ab_tests(df),
        "html_report": str(html_path) if generated else None,
        "library": library if generated else None,
    }


__all__ = ["build_eda_report"]
