"""Run the legal crawler from the command line.

Example:
    .venv/Scripts/python scripts/run_legal_crawler.py \\
        --keyword "smart pet feeder" --market US --out output/crawler/demo.json
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.legal_crawler import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
