"""生成市场日报（可选推送到飞书/企业微信 webhook）。

用法：
    python scripts\\build_market_daily.py
    python scripts\\build_market_daily.py --date 2026-08-13 --push
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.market_daily import (  # noqa: E402
    build_market_daily_markdown,
    maybe_push_market_daily,
    write_market_daily,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成市场日报")
    parser.add_argument("--date", help="日报日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--push", action="store_true", help="尝试推送 webhook")
    args = parser.parse_args(argv)

    report_date = args.date or date.today().isoformat()
    markdown = build_market_daily_markdown(report_date)
    path = write_market_daily(markdown, report_date)
    print(f"市场日报已写入：{path}")
    if args.push:
        pushed = maybe_push_market_daily(markdown)
        print("推送结果：成功" if pushed else "推送结果：未配置 webhook 或推送失败")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
