"""生成工程化状态 manifest（output/eng_status.json）。

记录 pytest 通过/收集数量、数据状态与 API 清单，供 07 工程化能力面板和
``/api/engineering/status`` 读取。默认执行完整测试并解析通过数；
``--collect-only`` 只统计收集数量（更快，但通过数缺失）。

用法：
    python scripts/build_eng_status.py            # 完整跑测
    python scripts/build_eng_status.py --collect-only
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ENG_STATUS_JSON, OUTPUT_DIR  # noqa: E402


def _pytest_summary(collect_only: bool) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "--basetemp=tmp/pytest-eng",
        "tests",
        "-q",
    ]
    collected = 0
    if not collect_only:
        quick = subprocess.run(
            cmd + ["--collect-only"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        quick_match = re.search(
            r"(\d+) (?:test|tests) collected",
            quick.stdout + quick.stderr,
        )
        if quick_match:
            collected = int(quick_match.group(1))
    if collect_only:
        cmd.append("--collect-only")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=1800)
    tail = (result.stdout + "\n" + result.stderr).strip().splitlines()[-20:]
    passed = None
    for line in tail:
        collected_match = re.search(r"(\d+) (?:test|tests) collected", line)
        if collected_match and not collected:
            collected = int(collected_match.group(1))
        passed_match = re.search(r"(\d+) passed", line)
        if passed_match:
            passed = int(passed_match.group(1))
        if re.search(r"\bpassed\b|\berrors?\b|\bfailed\b", line) and "==" in line:
            passed = passed if passed is not None else 0
    return {
        "collected": collected,
        "passed": passed,
        "exit_code": result.returncode,
        "collected_only": collect_only,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成工程化状态 manifest")
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="只统计收集数量，不执行测试",
    )
    args = parser.parse_args(argv)

    test_summary = _pytest_summary(args.collect_only)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "test_collected": test_summary["collected"],
        "test_passed": test_summary["passed"],
        "pytest_exit_code": test_summary["exit_code"],
        "collected_only": test_summary["collected_only"],
        "build": {
            "pipeline": "run_pipeline.py -> run_trade_demo.py -> run_daily_update.py",
            "rebuild": "scripts/run_daily_update.py --skip-pipeline",
            "start": "一键启动.bat",
            "stop": "停止完整Demo.bat",
        },
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ENG_STATUS_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {ENG_STATUS_JSON}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
