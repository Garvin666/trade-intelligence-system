"""Train forecast models on the real-feature-augmented training frame.

Usage:
    python scripts/train_real_enhanced.py                # default full retrain
    python scripts/train_real_enhanced.py --quick         # smaller proxy trials
    python scripts/train_real_enhanced.py --skip-proxy    # skip proxy model
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402

from src.config import (  # noqa: E402
    PROCESSED_CSV,
    REAL_FEATURE_COLS,
    REAL_TRAINING_CSV,
    REAL_TRAINING_STATUS_JSON,
)
from src.control.benchmark import (  # noqa: E402
    CONTROL_DIR,
    HOLDOUT_CSV,
    TRAIN_CSV,
    prepare_control_split,
)
from src.models.real_proxy import train_real_proxy_model  # noqa: E402
from src.data.real_features import write_real_training_files  # noqa: E402
from src.pipeline import prepare_data, train_and_evaluate  # noqa: E402


def _load_training_frame(skip_real_features: bool, force_regenerate: bool, end_date: str | None) -> pd.DataFrame:
    if force_regenerate:
        return prepare_data(
            force_regenerate=True,
            end_date=end_date,
            use_real_features=not skip_real_features,
        )
    if skip_real_features:
        training_csv = PROCESSED_CSV
    elif REAL_TRAINING_CSV.exists():
        training_csv = REAL_TRAINING_CSV
    else:
        clean = pd.read_csv(PROCESSED_CSV, encoding="utf-8-sig")
        clean["date"] = pd.to_datetime(clean["date"])
        augmented, _ = write_real_training_files(clean)
        return augmented
    frame = pd.read_csv(training_csv, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def _write_control_split(frame: pd.DataFrame) -> dict[str, Any]:
    train, holdout = prepare_control_split(frame)
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    train.to_csv(TRAIN_CSV, index=False, encoding="utf-8-sig")
    holdout.to_csv(HOLDOUT_CSV, index=False, encoding="utf-8-sig")
    return {
        "train_rows": int(len(train)),
        "holdout_rows": int(len(holdout)),
        "train_dates": f"{pd.to_datetime(train['date']).min().date()} ~ {pd.to_datetime(train['date']).max().date()}",
        "holdout_dates": f"{pd.to_datetime(holdout['date']).min().date()} ~ {pd.to_datetime(holdout['date']).max().date()}",
    }


def _write_status(frame: pd.DataFrame, proxy_status: dict[str, Any] | None) -> None:
    from src.config import CATEGORIES, MARKETS

    combos = int(frame.groupby(["category", "market"], observed=True).ngroups)
    total_combos = len(CATEGORIES) * len(MARKETS)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "enabled": True,
        "rows": int(len(frame)),
        "combos": combos,
        # 口径说明（建议报告 N1）：主口径为 len(CATEGORIES)×len(MARKETS) 组合；
        # 真实特征训练只覆盖有真实信号（Trends/榜单/Comtrade/爬虫证据）的
        # combos 个子集组合，其余 (total - combos) 组合走合成特征。
        "caliber_note": (
            f"真实特征训练覆盖 {combos} 个（品类×市场）组合，"
            f"主口径 {len(CATEGORIES)}×{len(MARKETS)}={total_combos} 组合中"
            f"其余 {total_combos - combos} 个组合走合成特征；"
            "rows = combos × 104 周"
        ),
        "real_feature_columns": [column for column in REAL_FEATURE_COLS if column in frame.columns],
        "real_feature_count": len([column for column in REAL_FEATURE_COLS if column in frame.columns]),
        "training_csv": str(REAL_TRAINING_CSV),
        "proxy": proxy_status,
    }
    REAL_TRAINING_STATUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    REAL_TRAINING_STATUS_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_real_enhanced_pipeline(
    *,
    force_regenerate: bool = False,
    end_date: str | None = None,
    skip_real_features: bool = False,
    skip_proxy: bool = False,
    quick: bool = False,
) -> dict[str, Any]:
    frame = _load_training_frame(skip_real_features, force_regenerate, end_date)
    if quick:
        categories = sorted(frame["category"].dropna().unique())[:2]
        markets = sorted(frame["market"].dropna().unique())[:2]
        frame = frame[frame["category"].isin(categories) & frame["market"].isin(markets)].copy()
    result = train_and_evaluate(frame)
    proxy_status = None
    if not skip_proxy:
        proxy_status = train_real_proxy_model()
    control = _write_control_split(frame)
    _write_status(frame, proxy_status)
    return {
        **result,
        "data": frame,
        "control_split": control,
        "proxy_status": proxy_status,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Real-feature-enhanced model retrain")
    parser.add_argument("--quick", action="store_true", help="smoke mode")
    parser.add_argument("--skip-real-features", action="store_true")
    parser.add_argument("--skip-proxy", action="store_true")
    parser.add_argument("--force-regenerate", action="store_true")
    parser.add_argument("--end-date", help="YYYY-MM-DD")
    args = parser.parse_args(argv)
    result = run_real_enhanced_pipeline(
        force_regenerate=args.force_regenerate,
        end_date=args.end_date,
        skip_real_features=args.skip_real_features,
        skip_proxy=args.skip_proxy,
        quick=args.quick,
    )
    print(
        f"rows={len(result['data'])} forecast={len(result['forecast'])} "
        f"recommendations={len(result['recommendations'])} quick={args.quick}"
    )
    print(f"control={result['control_split']}")
    print(f"proxy_status={result['proxy_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
