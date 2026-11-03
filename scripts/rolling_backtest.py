"""滚动回测 + 跨品类冷启动评估 + 业务指标落盘（任务清单 A-2）。

用法：
    python scripts/rolling_backtest.py                 # 全量（132 品类 × 15 市场）
    python scripts/rolling_backtest.py --smoke         # 快速冒烟（2 品类 × 2 市场 × 2 轮）
    python scripts/rolling_backtest.py --model prophet --combos 20   # 用生产 Prophet 基线抽样
    python scripts/rolling_backtest.py --skip-metrics  # 不写 metrics.json

产物：
    output/backtest/rolling_results.csv        每轮窗口每组合 MAPE/MAE/方向命中率
    output/backtest/rolling_predictions.csv    逐点预测明细（含 80% 区间）
    output/backtest/cold_start_results.csv     冷启动 vs 全量训练对比
    output/backtest/backtest_summary.md        回测摘要
    output/backtest/cold_start.md              冷启动评估报告
    models/metrics.json["business_metrics"]    业务指标（校准度/方向命中/Top-N 后验收益/库存损失）

固定随机种子 RANDOM_SEED=42（src/config.py），跨品类随机留出/抽样均可复现。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.backtest import (  # noqa: E402
    DEFAULT_MAX_ROUNDS,
    DEFAULT_STEP_WEEKS,
    DEFAULT_TEST_WEEKS,
    DEFAULT_TRAIN_WEEKS,
    run_cold_start,
    run_rolling_backtest,
    write_backtest_outputs,
)
from src.analysis.business_metrics import (  # noqa: E402
    build_business_metrics,
    save_business_metrics,
)
from src.config import (  # noqa: E402
    METRICS_JSON,
    OUTPUT_DIR,
    PROCESSED_CSV,
    RANDOM_SEED,
    RECOMMEND_CSV,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="滚动回测 + 冷启动评估 + 业务指标")
    parser.add_argument("--data", default=str(PROCESSED_CSV), help="清洗数据 CSV 路径")
    parser.add_argument(
        "--recommendations",
        default=str(RECOMMEND_CSV),
        help="Top-N 推荐 CSV（缺省 models/recommendations.csv）",
    )
    parser.add_argument(
        "--model",
        default="seasonal_naive",
        choices=("seasonal_naive", "prophet"),
        help="回测模型（seasonal_naive 确定性快速；prophet 为生产基线）",
    )
    parser.add_argument("--train-weeks", type=int, default=DEFAULT_TRAIN_WEEKS)
    parser.add_argument("--test-weeks", type=int, default=DEFAULT_TEST_WEEKS)
    parser.add_argument("--step-weeks", type=int, default=DEFAULT_STEP_WEEKS)
    parser.add_argument("--rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    parser.add_argument(
        "--combos",
        type=int,
        default=None,
        help="抽样组合数（缺省全量；用种子 42 随机留出抽样）",
    )
    parser.add_argument(
        "--cold-start-categories",
        type=int,
        default=None,
        help="冷启动留出的品类数（缺省全部品类）",
    )
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--out-dir", default=str(OUTPUT_DIR / "backtest"))
    parser.add_argument("--metrics-json", default=str(METRICS_JSON))
    parser.add_argument("--skip-metrics", action="store_true", help="不写 metrics.json")
    parser.add_argument("--skip-cold-start", action="store_true", help="跳过冷启动评估")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="快速冒烟：2 品类 × 2 市场 × 2 轮，seasonal_naive",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_path = Path(args.data)
    if not data_path.exists():
        print(f"未找到清洗数据：{data_path}")
        return 1

    import pandas as pd

    history = pd.read_csv(data_path, encoding="utf-8-sig")
    history["date"] = pd.to_datetime(history["date"])

    model = args.model
    train_weeks, test_weeks, step_weeks, max_rounds = (
        args.train_weeks,
        args.test_weeks,
        args.step_weeks,
        args.rounds,
    )
    combos: int | None = args.combos
    cold_categories: int | None = args.cold_start_categories
    if args.smoke:
        model = "seasonal_naive"
        train_weeks, test_weeks, step_weeks, max_rounds = 24, 4, 4, 2
        combos = 4
        cold_categories = 2
        if args.skip_cold_start:
            cold_categories = 0

    print(
        f"[backtest] model={model} train={train_weeks} test={test_weeks} "
        f"step={step_weeks} rounds={max_rounds} combos={combos} seed={args.seed}"
    )
    results, predictions = run_rolling_backtest(
        history,
        model=model,
        train_weeks=train_weeks,
        test_weeks=test_weeks,
        step_weeks=step_weeks,
        max_rounds=max_rounds,
        combos=combos,
        seed=args.seed,
    )
    print(f"[backtest] 完成：结果 {len(results)} 行，逐点预测 {len(predictions)} 行")

    cold_start = (
        run_cold_start(
            history,
            test_weeks=test_weeks if test_weeks >= 4 else 4,
            categories=cold_categories,
            seed=args.seed,
        )
        if not args.skip_cold_start and cold_categories != 0
        else None
    )
    if cold_start is not None:
        print(f"[cold-start] 完成：{len(cold_start)} 行（留出品类 {len(cold_start['category'].unique())} 个）")

    out_dir = Path(args.out_dir)
    params = {
        "model": model,
        "train_weeks": train_weeks,
        "test_weeks": test_weeks,
        "step_weeks": step_weeks,
        "max_rounds": max_rounds,
        "combo_count": int(results["category"].nunique() * results["market"].nunique())
        if not results.empty
        else 0,
        "seed": args.seed,
    }
    paths = write_backtest_outputs(
        results, predictions, cold_start if cold_start is not None else _empty_cold(), out_dir, model, params
    )
    for name, path in paths.items():
        print(f"[output] {name} -> {path}")

    if not args.skip_metrics:
        metrics_path = Path(args.metrics_json)
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        else:
            metrics = {}
        recommendations = pd.DataFrame()
        rec_path = Path(args.recommendations)
        if rec_path.exists():
            recommendations = pd.read_csv(rec_path, encoding="utf-8-sig")
        payload = build_business_metrics(
            history,
            recommendations,
            metrics,
            predictions=predictions if not predictions.empty else None,
            seed=args.seed,
            predictions_label=f"rolling_backtest:{model}",
        )
        save_business_metrics(payload, metrics_path)
        print(
            f"[metrics] business_metrics 已写入 {metrics_path} "
            f"(校准 {payload['calibration']['status']} / 方向 {payload['direction_hit_rate']['status']} / "
            f"Top-N {payload['topn_posterior_return']['status']} / 库存 {payload['inventory_loss']['status']})"
        )
    else:
        print("[metrics] 已跳过（--skip-metrics）")
    print("DONE")
    return 0


def _empty_cold():
    import pandas as pd

    return pd.DataFrame()


if __name__ == "__main__":
    raise SystemExit(main())
