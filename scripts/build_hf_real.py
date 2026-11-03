"""构建 Hugging Face 公开数据集信号层（无需联网，基于本地下载数据）。

用法：
    python scripts\\build_hf_real.py
    python scripts\\build_hf_real.py --skip-csv

产物：
    output/control/hf_signals.json
    output/control/hf_real_results.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.hf_datasets import (  # noqa: E402
    build_hf_real_results,
    build_hf_signals,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建 HF 公开数据集信号层")
    parser.add_argument(
        "--skip-csv",
        action="store_true",
        help="仅生成 hf_signals.json，不生成 hf_real_results.csv",
    )
    args = parser.parse_args(argv)

    payload = build_hf_signals()
    print(
        "已写入 hf_signals.json："
        f"{len(payload['sources'])} 个来源 / {len(payload['rows'])} 行信号"
    )
    if not args.skip_csv:
        path = build_hf_real_results(payload=payload)
        print(f"已写入 {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
