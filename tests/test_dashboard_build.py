"""Dashboard dual-mode build checks (external data vs offline inline)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_html_dashboard  # noqa: E402


def test_collected_test_count_is_current() -> None:
    assert build_html_dashboard.collected_test_count() >= 269


def test_build_script_has_dual_outputs() -> None:
    source = (SCRIPTS / "dashboard_build" / "main.py").read_text(
        encoding="utf-8"
    ) + (SCRIPTS / "dashboard_build" / "templates.py").read_text(encoding="utf-8")
    assert "OUT_OFFLINE_HTML" in source
    assert "OUT_DATA_JSON" in source
    assert "async function loadDashboardData" in source
    assert (
        '<button class="head-action-btn primary" id="embedded-custom-run-btn" '
        'type="button">开始分析</button>'
    ) in source
    assert "unified-embedded-only\" id=\"embedded-custom-run-btn" not in source


def test_generated_artifacts_have_expected_shapes() -> None:
    online = PROJECT_ROOT / "output" / "dashboard.html"
    offline = PROJECT_ROOT / "output" / "dashboard-offline.html"
    data = PROJECT_ROOT / "output" / "dashboard-data.json"
    if not (online.exists() and offline.exists() and data.exists()):
        return
    online_text = online.read_text(encoding="utf-8", errors="replace")
    offline_text = offline.read_text(encoding="utf-8", errors="replace")
    assert '<script id="dashboard-data" type="application/json"></script>' in online_text
    assert "async function loadDashboardData" in online_text
    assert "(async function () {" in online_text
    assert "(async function () {" in offline_text
    assert data.stat().st_size > 1024 * 1024
