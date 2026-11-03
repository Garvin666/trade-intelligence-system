"""生成跨境贸易决策演示报告（政策风险 + 到岸成本 + 市场准入）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import PROCESSED_CSV
from src.trade.report import OUTPUT_DIR, build_trade_demo_report


def main() -> None:
    clean_df = pd.read_csv(PROCESSED_CSV) if PROCESSED_CSV.exists() else None
    payload = build_trade_demo_report(clean_df)
    summary = payload["summary"]
    print(f"贸易决策演示报告生成完成：{OUTPUT_DIR}")
    print(f"  组合数：{summary['combos']}")
    print(f"  高风险：{summary['high_risk']} / 中风险：{summary['medium_risk']}")
    print(f"  平均利润率：{summary['avg_margin_pct']}%")
    print(
        f"  数据信用：平均融资就绪分 {summary['credit_avg']}；"
        f"供应链金融 {summary['credit_supply_chain_finance']} / "
        f"信用贷 {summary['credit_loan']} / "
        f"小额试单 {summary['credit_trial']} / "
        f"暂不建议 {summary['credit_not_ready']}"
    )
    for row in payload["rows"][:5]:
        print(
            f"  {row['category_name']} x {row['market_name']}: "
            f"risk={row['risk_level']}, margin={row['margin_pct']}%, "
            f"best={row['best_logistics']}, financing={row['financing_level']}"
        )


if __name__ == "__main__":
    main()
