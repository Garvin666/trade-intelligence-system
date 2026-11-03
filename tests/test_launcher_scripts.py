"""Guard one-click launcher scripts against Windows PowerShell parsing issues.

The launcher invokes start_complete_demo.ps1 through Windows PowerShell 5.1.
Without a UTF-8 BOM, that host decodes UTF-8 files using the system ANSI code
page, so non-ASCII comments can corrupt the tokenizer and fail the whole
startup. Keep the launcher scripts ASCII-only, or save them with a BOM.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_launcher_scripts_are_ascii_safe_for_windows_powershell() -> None:
    patterns = (
        "start_complete_demo.ps1",
        "stop_complete_demo.ps1",
        "complete_demo_refresh.ps1",
    )
    scripts = []
    for pattern in patterns:
        scripts.extend(
            p
            for p in PROJECT_ROOT.rglob(pattern)
            if ".venv" not in p.parts and "node_modules" not in p.parts
        )
    assert scripts, "expected at least one launcher PowerShell script"
    for script in scripts:
        raw = script.read_bytes()
        assert max(raw) < 128, (
            f"{script} contains non-ASCII bytes; "
            "Windows PowerShell 5.1 may fail to parse it"
        )


def test_launcher_version_fingerprint_covers_market_intel() -> None:
    script = PROJECT_ROOT / "start_complete_demo.ps1"
    text = script.read_text(encoding="utf-8")
    assert "/openapi.json" in text
    assert "/api/market-intel" in text


def test_one_click_launcher_has_proxy_safe_pip_fallback() -> None:
    bat = (PROJECT_ROOT / "一键启动.bat").read_text(encoding="utf-8")
    powershell = (PROJECT_ROOT / "start_complete_demo.ps1").read_text(encoding="utf-8")

    for script in (bat, powershell):
        assert "https://pypi.tuna.tsinghua.edu.cn/simple" in script
        assert "--proxy=" in script
        assert "requirements.lock" in script
        assert "requirements.txt" in script

    assert "goto create_venv" in bat
    assert "Failed to create local virtual environment (.venv)." in bat
