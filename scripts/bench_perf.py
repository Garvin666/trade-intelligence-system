"""只读性能基准：对运行中的统一后端关键接口计时。

用法：
    python scripts/bench_perf.py
    python scripts/bench_perf.py --include-check --include-four-brain --format json

只发送只读 HTTP 请求，不修改项目文件；四脑为规则模式（无 AI、无联网）。
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from typing import Any, Callable


def _request(
    base_url: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> tuple[int, int]:
    url = base_url.rstrip("/") + path
    data = None
    headers: dict[str, str] = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms, len(body)


def _measure(
    base_url: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    iterations: int = 3,
) -> dict[str, Any]:
    samples: list[float] = []
    sizes: list[int] = []
    for _ in range(iterations):
        elapsed, size = _request(base_url, path, method=method, payload=payload)
        samples.append(elapsed)
        sizes.append(size)
    ordered = sorted(samples)
    return {
        "path": path,
        "first_ms": round(samples[0], 1),
        "min_ms": round(ordered[0], 1),
        "median_ms": round(ordered[len(ordered) // 2], 1),
        "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1], 1),
        "bytes": sizes[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BACKEND_BASE_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--include-check", action="store_true")
    parser.add_argument("--include-search", action="store_true")
    parser.add_argument("--include-four-brain", action="store_true")
    parser.add_argument("--format", choices=("md", "json"), default="md")
    args = parser.parse_args()

    endpoints: list[tuple[str, str, dict[str, Any] | None]] = [
        ("GET", "/api/health", None),
        ("GET", "/api/data/status", None),
        ("GET", "/api/dashboard-data?limit=200", None),
        ("GET", "/api/search/trends?category=pet&market=us", None),
        ("GET", "/api/competition/index?category=pet&market=us", None),
        ("GET", "/api/cost/metrics?category=pet&market=us", None),
        ("GET", "/api/risk/overview?category=pet&market=us", None),
        ("GET", "/api/platform/rankings?category=pet&market=us", None),
        ("GET", "/api/reviews/summary?category=pet&market=us", None),
        ("GET", "/api/trade/export-value?category=pet&market=us", None),
        ("GET", "/api/market/compare?category=pet", None),
        ("GET", "/api/recommendations?top=5", None),
        ("GET", "/api/trade/report?market=us&limit=100", None),
    ]
    if args.include_check:
        endpoints.append(("GET", "/api/check?depth=quick", None))
    if args.include_search:
        endpoints.append(
            ("GET", "/api/search?q=smart%20pet%20feeder&max_results=3", None)
        )
    if args.include_four_brain:
        endpoints.append(
            (
                "POST",
                "/api/four-brain",
                {"keyword": "辣条（网红休闲零食）", "market": "us", "research": False, "ai": False},
            )
        )

    results = [
        _measure(
            args.base_url,
            path,
            method=method,
            payload=payload,
            iterations=args.iterations,
        )
        for method, path, payload in endpoints
    ]

    if args.format == "json":
        print(json.dumps({"base_url": args.base_url, "results": results}, ensure_ascii=False, indent=2))
        return

    print(f"# 性能基准 {args.base_url}")
    print("")
    print("| 接口 | 首次 ms | 中位 ms | 体积 B |")
    print("|---|---:|---:|---:|")
    for item in results:
        print(f"| {item['path']} | {item['first_ms']} | {item['median_ms']} | {item['bytes']} |")


if __name__ == "__main__":
    main()
