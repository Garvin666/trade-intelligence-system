"""在已有清洗数据上训练模型并输出评估、预测、推荐。"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import PROCESSED_CSV, REAL_TRAINING_CSV  # noqa: E402
from src.pipeline import train_and_evaluate  # noqa: E402


def main() -> None:
    training_csv = REAL_TRAINING_CSV if REAL_TRAINING_CSV.exists() else PROCESSED_CSV
    if not training_csv.exists():
        print("未找到清洗数据，请先运行 scripts\\generate_demo_data.py")
        return
    df = pd.read_csv(training_csv)
    df["date"] = pd.to_datetime(df["date"])
    result = train_and_evaluate(df)

    bm = result["baseline_metrics"]
    am = result["advanced_metrics"]
    print("\n模型评估（MAPE%）：")
    print(bm.groupby("model")["mape"].mean().to_string())
    print(am.groupby("model")["mape"].mean().to_string())
    print(f"\n预测记录：{len(result['forecast'])} 行")
    print(f"推荐记录：{len(result['recommendations'])} 行")


if __name__ == "__main__":
    main()
