"""联网连通性自检：执行一次真实搜索并输出结构化报告。

用法：
    python scripts\\test_online.py
    python scripts\\test_online.py --base-url http://127.0.0.1:8000
    python scripts\\test_online.py --allow-fallback

退出码：真实联网成功（结果含可访问链接）返回 0，离线/回退返回 1；
``--allow-fallback`` 时回退也被视为通过。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _http_search(base_url: str, timeout: int) -> Any:
    """构造通过后端 /api/search/test 执行联网测试的搜索函数。"""

    def search(query: str, max_results: int, provider: str) -> dict[str, Any]:
        payload = json.dumps(
            {"query": query, "provider": provider, "max_results": max_results}
        ).encode("utf-8")
        request = urllib.request.Request(
            base_url.rstrip("/") + "/api/search/test",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("ok"):
            return {
                "provider": provider,
                "fallback_used": False,
                "results": data.get("results", []),
            }
        return {
            "provider": provider,
            "fallback_used": True,
            "results": [],
            "error": data.get("error") or "online test failed",
        }

    return search


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="联网连通性自检")
    parser.add_argument("--query", default="smart pet feeder 2026")
    parser.add_argument("--max-results", type=int, default=3)
    parser.add_argument(
        "--provider",
        default=os.environ.get("SEARCH_PROVIDER", "crawler"),
    )
    parser.add_argument("--base-url", help="后端地址，例如 http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="联网失败但已标注模拟回退时也视为通过",
    )
    args = parser.parse_args(argv)

    from src.api import services

    if args.base_url:
        search_fn = _http_search(args.base_url, args.timeout)
    else:
        search_fn = None
    report = services.online_test(
        query=args.query,
        max_results=args.max_results,
        provider=args.provider,
        allow_fallback=args.allow_fallback,
        search_fn=search_fn,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    status = "OK" if report["ok"] else "OFFLINE"
    print(f"联网测试结果：{status}（provider={report['provider']}）")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
