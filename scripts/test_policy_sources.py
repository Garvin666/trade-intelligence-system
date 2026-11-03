"""Live smoke test for the Policy Radar official sources.

Usage:
    python scripts/test_policy_sources.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data import policy_sources  # noqa: E402


def main() -> int:
    results: dict[str, dict] = {}
    for name, fetcher in policy_sources._FETCHERS.items():
        try:
            items = fetcher(lookback_days=14, timeout=25)
            linked = [item for item in items if str(item.get("link") or "").startswith("http")]
            results[name] = {
                "ok": bool(linked),
                "count": len(items),
                "linked": len(linked),
                "first": linked[0]["link"] if linked else None,
            }
        except Exception as exc:  # noqa: BLE001 - report per-source failures
            results[name] = {
                "ok": False,
                "count": 0,
                "linked": 0,
                "first": None,
                "error": str(exc)[:300],
            }
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if any(entry.get("ok") for entry in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
