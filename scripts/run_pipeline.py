"""一键执行完整流水线：数据 → 模型 → 评估 → 推荐。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import run_full_pipeline  # noqa: E402


def main() -> None:
    result = run_full_pipeline()
    df = result["data"]
    baseline = result["baseline_metrics"]
    advanced = result["advanced_metrics"]
    forecast = result["forecast"]
    recommendations = result["recommendations"]

    print("=" * 60)
    print("跨境电商智能选品决策系统 - 流水线执行完成")
    print("=" * 60)
    print(f"数据规模：{len(df)} 行 | 品类 {df['category'].nunique()} | 市场 {df['market'].nunique()}")
    print(f"预测记录：{len(forecast)} 行 | 推荐 Top10：{len(recommendations)} 行")
    print("\n基线模型 MAPE（均值）：")
    print(baseline.groupby("model")["mape"].mean().to_string())
    print("\n进阶模型 MAPE（均值）：")
    print(advanced.groupby("model")["mape"].mean().to_string())
    print("\n推荐 Top 5：")
    print(recommendations.head(5).to_string(index=False))
    print("\n启动看板：python -m streamlit run app.py")


if __name__ == "__main__":
    main()
