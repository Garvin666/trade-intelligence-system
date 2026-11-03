"""Build the real-data evidence validation report.

Aggregates existing real evidence artifacts (GitHub platform samples,
Wikimedia crawler, trends and customs snapshots) into
``output/real/status.json`` and ``output/real/validation.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.real_ingest import (  # noqa: E402
    VALIDATION_JSON,
    save_real_validation,
)


def main() -> int:
    status = save_real_validation()
    print(
        "REAL VALIDATION OK: "
        f"combos={status['combos']} "
        f"evidence_available={status['evidence_available_combos']} "
        f"real_counts={json.dumps(status['real_counts'], ensure_ascii=False)}"
    )
    print(f"status={status['status']} validation_file={VALIDATION_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
