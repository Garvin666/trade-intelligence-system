"""一键运行数据分析：生成统计 JSON、PNG 图表与《数据分析报告》Markdown。

用法：
    python scripts/run_data_analysis.py

产物：
    output/analysis/summary_stats.json
    docs/figures/*.png
    docs/数据分析报告.md
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.report import (  # noqa: E402
    ANALYSIS_OUT,
    FIGURES_DIR,
    REPORT_MD,
    load_all,
    save_report,
)

SUBMISSION_FIGURES = (
    PROJECT_ROOT
    / "发布与材料"
    / "提交材料包_整合优化版_20260805"
    / "03_支撑文档"
    / "figures"
)
SUBMISSION_REPORT = (
    PROJECT_ROOT
    / "发布与材料"
    / "提交材料包_整合优化版_20260805"
    / "03_支撑文档"
    / "数据分析报告.md"
)


def sync_submission_package() -> None:
    """把报告与图表同步到提交材料包 03_支撑文档。"""
    if not SUBMISSION_REPORT.parent.exists():
        print("SKIP: 提交材料包目录不存在，跳过同步")
        return
    SUBMISSION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    SUBMISSION_FIGURES.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPORT_MD, SUBMISSION_REPORT)
    for figure in FIGURES_DIR.glob("*.png"):
        shutil.copy2(figure, SUBMISSION_FIGURES / figure.name)
    print(f"SYNC: {len(list(FIGURES_DIR.glob('*.png')))} 张图表 + 报告已同步到提交包")


def main() -> None:
    data = load_all()
    result = save_report(
        data["history"],
        data["forecast"],
        data["recommendations"],
        out_stats=ANALYSIS_OUT,
        figures_dir=FIGURES_DIR,
        report_path=REPORT_MD,
    )
    stats = result["stats"]
    print(f"OK: 统计 JSON -> {ANALYSIS_OUT / 'summary_stats.json'}")
    print(f"OK: 图表 {len(result['figures'])} 张 -> {FIGURES_DIR}")
    print(f"OK: 报告 -> {REPORT_MD}")
    print(
        "SUMMARY: "
        f"{stats['overview']['history_rows']} rows / "
        f"{stats['overview']['weeks']} weeks / "
        f"MAPE {stats['overview']['advanced_mape_avg']}% / "
        f"improvement {stats['overview']['mape_improvement_pct']}%"
    )
    sync_submission_package()


if __name__ == "__main__":
    main()
