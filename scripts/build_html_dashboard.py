"""Legacy dashboard build entrypoint (facade over scripts.dashboard_build)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dashboard_build.main import *  # noqa: E402,F401,F403
from scripts.dashboard_build.main import build  # noqa: E402

if __name__ == "__main__":
    build()
