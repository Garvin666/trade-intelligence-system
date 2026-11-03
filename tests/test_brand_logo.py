"""Brand logo checks across current generated surfaces."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRAND = "远帆智品"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_logo_asset_exists() -> None:
    logo = PROJECT_ROOT / "assets" / "logo.jpg"
    assert logo.exists(), "缺少 assets/logo.jpg"
    assert logo.stat().st_size > 1000


def test_dashboard_generator_has_brand_logo() -> None:
    source = _read(PROJECT_ROOT / "scripts" / "dashboard_build" / "main.py") + _read(
        PROJECT_ROOT / "scripts" / "dashboard_build" / "templates.py"
    )
    assert "brand-logo" in source
    assert "brand-logo-float" in source
    assert "brand-logo-orbit" in source
    assert BRAND in source
    assert "data:image/jpeg;base64," in source


def test_generated_dashboards_have_brand_logo() -> None:
    for name in ("dashboard.html", "dashboard-offline.html"):
        path = PROJECT_ROOT / "output" / name
        if not path.exists():
            continue
        text = _read(path)
        assert "brand-logo" in text, name
        assert "brand-logo-float" in text, name
        assert BRAND in text, name
        assert "data:image/jpeg;base64," in text, name


def test_streamlit_dashboard_has_animated_logo() -> None:
    source = _read(PROJECT_ROOT / "src" / "app" / "dashboard.py")
    assert "st-logo-wrap" in source
    assert "_render_animated_logo" in source


def test_frontend_app_has_brand() -> None:
    sources = [
        path
        for root in ("pages", "widgets", "shared")
        for path in (PROJECT_ROOT / "frontend" / "src" / root).rglob("*.tsx")
    ]
    assert sources, "frontend/src 缺少品牌相关页面"
    assert any(BRAND in _read(path) for path in sources), "frontend 缺少品牌名"
