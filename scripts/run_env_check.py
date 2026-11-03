"""系统检查模式命令行入口（环境 / 依赖 / 代码完善度 / 前后端连接）。

用法：
    .venv\\Scripts\\python scripts\\run_env_check.py
    .venv\\Scripts\\python scripts\\run_env_check.py --full        # 深度档：额外跑 pytest 与前端 typecheck
    .venv\\Scripts\\python scripts\\run_env_check.py --groups env,deps
    .venv\\Scripts\\python scripts\\run_env_check.py --json        # 仅输出 JSON
    .venv\\Scripts\\python scripts\\run_env_check.py --start-backend
    .venv\\Scripts\\python scripts\\run_env_check.py --browser     # 浏览器级渲染检查（需 playwright）

退出码：0 = 全部通过（warn 允许）；1 = 存在 fail；2 = 参数错误。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import checks  # noqa: E402

_STATUS_SYMBOL = {"ok": "[OK]  ", "warn": "[WARN]", "fail": "[FAIL]", "skip": "[SKIP]"}


def _print_report(report: dict) -> None:
    summary = report.get("summary", {})
    print("=" * 78)
    print("系统检查报告（跨境电商智能选品决策系统）")
    print(f"  时间：{report.get('generated_at')}  深度：{report.get('depth')}")
    print(f"  Python：{report.get('python')}  后端地址：{report.get('base_url')}")
    print("=" * 78)
    for name, group in report.get("groups", {}).items():
        print(f"\n■ {group.get('label', name)}（{name}）")
        for item in group.get("results", []):
            symbol = _STATUS_SYMBOL.get(item.get("status", "skip"), "[?]  ")
            print(f"  {symbol} {item.get('label', item.get('id', ''))}")
            detail = item.get("detail") or ""
            if detail:
                for line in detail.split("；")[:3]:
                    print(f"        {line}")
    print("\n" + "=" * 78)
    total = sum(summary.values())
    print(
        f"汇总：ok={summary.get('ok', 0)}  warn={summary.get('warn', 0)}  "
        f"fail={summary.get('fail', 0)}  skip={summary.get('skip', 0)}  （共 {total} 项）"
    )
    print(f"总体判定：{'PASS（通过）' if report.get('overall') == 'ok' else 'FAIL（未通过）'}（exit {checks.exit_code(report)}）")
    print(f"报告已写入：{report.get('_out_path', '（未落盘）')}")
    print("=" * 78)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="系统检查模式：环境 / 依赖 / 代码完善度 / 前后端连接",
    )
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 报告")
    parser.add_argument(
        "--groups",
        default=",".join(checks.VALID_GROUPS),
        help="要检查的分组，逗号分隔（env,deps,code,connect），默认全部",
    )
    depth_group = parser.add_mutually_exclusive_group()
    depth_group.add_argument("--quick", action="store_true", help="快速档（默认）：不跑 pytest/typecheck")
    depth_group.add_argument("--full", action="store_true", help="深度档：额外执行 pytest 全套与前端 typecheck")
    parser.add_argument("--start-backend", action="store_true", help="后端未运行时自动拉起并等待健康")
    parser.add_argument("--browser", action="store_true", help="执行浏览器级渲染检查（需 playwright）")
    parser.add_argument("--base-url", help="后端地址，默认从 BACKEND_HOST/BACKEND_PORT 读取")
    parser.add_argument("--out", default=str(checks.CHECK_REPORT_DEFAULT), help="JSON 报告输出路径")
    args = parser.parse_args(argv)

    groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    invalid = [g for g in groups if g not in checks.VALID_GROUPS]
    if invalid:
        parser.error(f"未知检查分组：{', '.join(invalid)}（可选 {', '.join(checks.VALID_GROUPS)}）")

    depth = "full" if args.full else "quick"
    report = checks.run_checks(
        groups=groups,
        depth=depth,
        base_url=args.base_url,
        start_backend=args.start_backend,
        browser=args.browser,
        out_path=args.out,
    )
    report["_out_path"] = str(Path(args.out).resolve())

    if args.json:
        report.pop("_out_path", None)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    return checks.exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
