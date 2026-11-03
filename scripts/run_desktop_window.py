"""Open the unified backend in a native desktop window (WebView2 on Windows).

Used by start_complete_demo.ps1 / 一键启动.bat in desktop mode. The backend is
already running on the selected port; this script only hosts the web UI in a
pywebview window, so one-click start no longer opens a browser tab.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "tmp"
LOG_FILE = LOG_DIR / "desktop-window.log"
HEALTH_URL = "http://127.0.0.1:{port}/api/health"
LOGIN_URL = "http://127.0.0.1:{port}{path}"
DEFAULT_LOGIN_PATH = os.environ.get(
    "DEMO_LOGIN_URL",
    "/agent/login.html?v=20260822-starfield-v2",
)
WINDOW_TITLE = "跨境电商智能选品决策系统"
DEFAULT_SIZE = (1440, 900)
MIN_SIZE = (1024, 700)
CREATE_NO_WINDOW = 0x08000000


def _setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def _show_error(title: str, message: str) -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        except Exception:  # noqa: BLE001 - GUI-less fallback is fine
            logging.exception("failed to show desktop error dialog")
    logging.error("%s", message)


def _wait_healthy(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    url = HEALTH_URL.format(port=port)
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001 - backend may still be starting
            pass
        time.sleep(0.5)
    return False


def _stop_backend() -> None:
    """Stop the demo session through the same stop script used by 停止完整Demo.bat."""
    stop_script = PROJECT_ROOT / "stop_complete_demo.ps1"
    if not stop_script.exists():
        logging.warning("stop script not found: %s; backend keeps running", stop_script)
        return
    powershell = shutil.which("powershell.exe") or "powershell"
    cmd = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(stop_script),
    ]
    try:
        subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            creationflags=CREATE_NO_WINDOW,
            timeout=60,
            check=False,
        )
    except Exception:  # noqa: BLE001 - shutdown failure must not crash the exit path
        logging.exception("failed to stop backend on window close")


def _open_browser_fallback(port: int, login_path: str) -> None:
    import webbrowser

    webbrowser.open(LOGIN_URL.format(port=port, path=login_path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True, help="backend HTTP port")
    parser.add_argument(
        "--login-path",
        default=DEFAULT_LOGIN_PATH,
        help="login page path to open",
    )
    parser.add_argument(
        "--stop-backend-on-close",
        action="store_true",
        help="stop the demo backend after the desktop window is closed",
    )
    parser.add_argument(
        "--browser-fallback",
        action="store_true",
        help="open the login page in the default browser if WebView2 fails",
    )
    parser.add_argument("--debug", action="store_true", help="enable WebView2 devtools")
    parser.add_argument(
        "--smoke-close-after",
        type=float,
        default=0,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    _setup_logging()
    logging.info("desktop window starting for backend port %s", args.port)
    if not _wait_healthy(args.port):
        message = f"后端未就绪（端口 {args.port}），请先通过一键启动启动后端。"
        _show_error("启动失败", message)
        return 2

    try:
        import webview
    except Exception as exc:  # noqa: BLE001 - dependency failure handled below
        logging.exception("pywebview is not available")
        if args.browser_fallback:
            _open_browser_fallback(args.port, args.login_path)
            _show_error(
                "桌面端不可用",
                "WebView2 组件未能加载，已改用浏览器打开。",
            )
        else:
            _show_error(
                "桌面端不可用",
                f"无法加载桌面窗口组件：{exc}\n请运行一键启动重装依赖，或使用浏览器模式。",
            )
        return 1

    storage = LOG_DIR / "webview"
    storage.mkdir(parents=True, exist_ok=True)
    login_url = LOGIN_URL.format(port=args.port, path=args.login_path)
    window = webview.create_window(
        WINDOW_TITLE,
        login_url,
        width=DEFAULT_SIZE[0],
        height=DEFAULT_SIZE[1],
        min_size=MIN_SIZE,
        resizable=True,
        text_select=True,
        zoomable=True,
        background_color="#04070f",
    )
    if args.smoke_close_after > 0:
        threading.Timer(args.smoke_close_after, window.destroy).start()

    try:
        webview.start(
            gui="edgechromium",
            private_mode=False,
            storage_path=str(storage),
            debug=args.debug,
        )
    except Exception as exc:  # noqa: BLE001 - WebView2 runtime may be missing
        logging.exception("webview failed to start")
        if args.browser_fallback:
            _open_browser_fallback(args.port, args.login_path)
            _show_error(
                "桌面端不可用",
                f"桌面窗口启动失败：{exc}\n已改用浏览器打开。",
            )
        else:
            _show_error(
                "桌面端不可用",
                f"桌面窗口启动失败：{exc}\n请确认已安装 Microsoft Edge WebView2 Runtime。",
            )
        return 1

    logging.info("desktop window closed")
    if args.stop_backend_on_close:
        _stop_backend()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
