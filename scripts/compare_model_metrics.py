"""Compare optimized model metrics against a saved baseline snapshot.

The default acceptance rule is a >=10% relative reduction in macro-average MAPE
for both Prophet and LightGBM, with MAE allowed to regress at most 5%.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

DEFAULT_BASELINE = PROJECT_ROOT / "output" / "optimization" / "baseline_metrics_20260812.json"
DEFAULT_CURRENT = PROJECT_ROOT / "models" / "metrics.json"
DEFAULT_REPORT = PROJECT_ROOT / "output" / "optimization" / "comparison.md"


def load_metrics(path: Path) -> dict[str, pd.DataFrame]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "prophet": pd.DataFrame(payload["baseline"]),
        "lightgbm": pd.DataFrame(payload["advanced"]),
    }


def summarize(df: pd.DataFrame) -> dict[str, float | int]:
    return {
        "mean_mape": float(df["mape"].mean()),
        "median_mape": float(df["mape"].median()),
        "mean_mae": float(df["mae"].mean()),
        "nan": int(df["mape"].isna().sum()),
    }


def compare(
    baseline: dict[str, pd.DataFrame],
    current: dict[str, pd.DataFrame],
    threshold_pct: float = 10.0,
    mae_guard_pct: float = 5.0,
) -> tuple[list[tuple[str, bool]], dict[str, dict], dict[str, dict]]:
    before = {name: summarize(frame) for name, frame in baseline.items()}
    after = {name: summarize(frame) for name, frame in current.items()}
    checks = [
        (
            "Prophet MAPE >=10% lower",
            after["prophet"]["mean_mape"]
            <= before["prophet"]["mean_mape"] * (1 - threshold_pct / 100.0),
        ),
        (
            "LightGBM MAPE >=10% lower",
            after["lightgbm"]["mean_mape"]
            <= before["lightgbm"]["mean_mape"] * (1 - threshold_pct / 100.0),
        ),
        (
            "Prophet MAE guard",
            after["prophet"]["mean_mae"]
            <= before["prophet"]["mean_mae"] * (1 + mae_guard_pct / 100.0),
        ),
        (
            "LightGBM MAE guard",
            after["lightgbm"]["mean_mae"]
            <= before["lightgbm"]["mean_mae"] * (1 + mae_guard_pct / 100.0),
        ),
        (
            "LightGBM MAPE < Prophet MAPE",
            after["lightgbm"]["mean_mape"] < after["prophet"]["mean_mape"],
        ),
        (
            "No NaN MAPE",
            after["prophet"]["nan"] == 0 and after["lightgbm"]["nan"] == 0,
        ),
    ]
    return checks, before, after


def _row(name: str, key: str, before: dict, after: dict) -> str:
    b = before[name][key]
    a = after[name][key]
    delta = (a / b - 1.0) * 100 if b else float("nan")
    return f"| {name} {key} | {b:.4f} | {a:.4f} | {delta:+.2f}% |"


def render_report(
    checks: list[tuple[str, bool]],
    before: dict,
    after: dict,
    threshold_pct: float,
    mae_guard_pct: float,
) -> str:
    lines = [
        "# 模型精度优化对比",
        "",
        f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- MAPE 目标：相对基线下降 ≥{threshold_pct:g}%",
        f"- MAE 护栏：相对基线增幅 ≤{mae_guard_pct:g}%",
        "",
        "| 指标 | 基线 | 优化后 | 变化 |",
        "| --- | --- | --- | --- |",
        _row("prophet", "mean_mape", before, after),
        _row("prophet", "median_mape", before, after),
        _row("prophet", "mean_mae", before, after),
        _row("lightgbm", "mean_mape", before, after),
        _row("lightgbm", "median_mape", before, after),
        _row("lightgbm", "mean_mae", before, after),
        "",
        "## 检查项",
        "",
    ]
    for name, ok in checks:
        lines.append(f"- {'通过' if ok else '未通过'}：{name}")
    lines.append("")
    lines.append(f"结论：{'通过' if all(ok for _, ok in checks) else '未通过'}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare optimized metrics with baseline")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--threshold-pct", type=float, default=10.0)
    parser.add_argument("--mae-guard-pct", type=float, default=5.0)
    parser.add_argument("--no-fail", action="store_true", help="report only, exit 0")
    args = parser.parse_args(argv)

    baseline = load_metrics(args.baseline)
    current = load_metrics(args.current)
    checks, before, after = compare(
        baseline,
        current,
        threshold_pct=args.threshold_pct,
        mae_guard_pct=args.mae_guard_pct,
    )
    report = render_report(
        checks,
        before,
        after,
        threshold_pct=args.threshold_pct,
        mae_guard_pct=args.mae_guard_pct,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(report)
    ok = all(ok for _, ok in checks)
    return 0 if (ok or args.no_fail) else 1


if __name__ == "__main__":
    raise SystemExit(main())
