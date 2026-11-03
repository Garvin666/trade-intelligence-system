"""生成并清洗演示数据。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import prepare_data  # noqa: E402


def main() -> None:
    df = prepare_data(force_regenerate=True)
    print(f"演示数据生成完成：{len(df)} 行，{df['category'].nunique()} 个品类，{df['market'].nunique()} 个市场")


if __name__ == "__main__":
    main()
