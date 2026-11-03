"""Generate the offline four-brain/launch example sets for the React app.

The generated TypeScript file keeps offline mode consistent with the backend
example endpoint without duplicating the 66-category payloads by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = (
    PROJECT_ROOT
    / "frontend"
    / "src"
    / "shared"
    / "api"
    / "fourBrainExamples.ts"
)


def _ts_literal(value: object, indent: int = 2) -> str:
    return json.dumps(value, ensure_ascii=False, indent=indent)


def main() -> None:
    import sys

    sys.path.insert(0, str(PROJECT_ROOT))
    from src.api.examples import build_examples_payload

    payload = build_examples_payload()
    four_brain = payload["four_brain"]
    launch = payload["launch_report"]
    lines = [
        "import type { ExamplePreset } from \"@/shared/api/types\";",
        "",
        "export const OFFLINE_FOUR_BRAIN_EXAMPLES: ExamplePreset[] = "
        + _ts_literal(four_brain, 2)
        + ";",
        "",
        "export const OFFLINE_LAUNCH_EXAMPLES: ExamplePreset[] = "
        + _ts_literal(launch, 2)
        + ";",
        "",
    ]
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"WROTE {OUTPUT} ({len(four_brain)} four-brain, {len(launch)} launch)")


if __name__ == "__main__":
    main()
