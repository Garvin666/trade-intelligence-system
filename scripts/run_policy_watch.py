"""Run the Policy Radar watch: official-source policy snapshot + optional rebuild.

Examples:
    python scripts/run_policy_watch.py
    python scripts/run_policy_watch.py --offline --skip-rebuild
    python scripts/run_policy_watch.py --include-search --rebuild-full
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from src.data.policy_refresh import (  # noqa: E402
    policy_snapshot_status,
    refresh_policy_snapshot,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="政策雷达官方源近实时监控")
    parser.add_argument("--offline", action="store_true", help="跳过真实联网，保留上次已验证快照")
    parser.add_argument("--date", help="数据日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--lookback-days", type=int, default=None, help="官方源回看天数")
    parser.add_argument(
        "--providers",
        default=None,
        help="逗号分隔的官方源：gov_cn,federal_register,eu,uk",
    )
    parser.add_argument(
        "--include-search",
        action="store_true",
        help="额外生成搜索候选事件（不进入决策链）",
    )
    parser.add_argument(
        "--skip-rebuild",
        action="store_true",
        help="只刷新快照，不重建看板 HTML",
    )
    parser.add_argument(
        "--rebuild-full",
        action="store_true",
        help="重建主 Demo（比默认看板重建更耗时）",
    )
    args = parser.parse_args(argv)

    providers = None
    if args.providers:
        providers = [
            item.strip()
            for item in args.providers.split(",")
            if item.strip()
        ]

    payload = refresh_policy_snapshot(
        None,
        offline=args.offline,
        provider="official",
        policy_date=args.date,
        lookback_days=args.lookback_days,
        official_providers=providers,
        include_search=args.include_search,
    )
    status = policy_snapshot_status(payload)
    print(
        f"[政策雷达] 已验证事件 {status['verified_events']} 条，"
        f"候选 {status['candidate_events']} 条，"
        f"回退 {status['fallback_used']}，快照 {payload.get('latest')}"
    )
    for name, source in sorted((payload.get("sources") or {}).items()):
        print(
            f"    {name}: {source.get('status')} count={source.get('count', 0)}"
            + (f" error={source.get('error')}" if source.get("error") else "")
        )

    if args.skip_rebuild:
        return 0

    import build_html_dashboard

    build_html_dashboard.build()
    if args.rebuild_full:
        import subprocess

        subprocess.run(
            ["pnpm.cmd", "--dir", str(PROJECT_ROOT / "frontend"), "build"],
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
