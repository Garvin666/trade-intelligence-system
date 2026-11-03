"""Start the unified single-process backend.

One process serves everything:
- REST API under /api/*
- demo pages under /app
- MCP server over Streamable HTTP under /mcp
- managed background jobs (daily update, market daily) under /api/jobs/*

Usage:
    python scripts/run_api.py               # 前台运行（默认）
    python scripts/run_api.py --watchdog    # 看门狗模式：子进程崩溃自动拉起
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 统一日志格式：应用内 logger（含全局异常处理器的 traceback）与 uvicorn 共用。
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def _load_env() -> None:
    """加载项目根目录 .env（可选）：在导入 src.api 之前执行，

    确保 BACKEND_* 等配置在中间件/路由模块读取 os.environ 前已就绪。
    未安装 python-dotenv 时静默跳过（兼容旧环境）。
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:  # pragma: no cover - 可选依赖
        pass


def _bind() -> tuple[str, int]:
    _load_env()
    host = os.environ.get("BACKEND_HOST", "127.0.0.1")
    port = int(os.environ.get("BACKEND_PORT", os.environ.get("API_PORT", "8000")))
    return host, port


def _serve() -> None:
    """实际后端服务入口（--serve）：仅启动 uvicorn。"""
    import uvicorn

    host, port = _bind()
    print(f"Unified backend starting at http://{host}:{port}")
    print(f"API docs:    http://{host}:{port}/docs")
    print(f"MCP (HTTP):  http://{host}:{port}/mcp")
    uvicorn.run("src.api.app:app", host=host, port=port, reload=False)


#: 看门狗重启退避序列（秒）：进程崩溃后依次等待再拉起。
WATCHDOG_BACKOFF = (1, 2, 4, 8, 16)
#: 一小时内最多自动重启次数（超过后停止并提示手动处理）。
WATCHDOG_MAX_RESTARTS_PER_HOUR = 5


def _watchdog() -> None:
    """看门狗模式：以子进程运行后端，崩溃后自动重启。

    修复建议报告 B4：四脑分析曾在 Windows 触发原生访问冲突（0xc0000005）
    直接拖垮整个后端进程，现场无守护、需手动拉起。本模式保证进程退出后
    自动恢复，退出码为 0（正常 shutdown）时不重启。
    """
    host, port = _bind()
    log_dir = PROJECT_ROOT / "tmp"
    log_dir.mkdir(parents=True, exist_ok=True)
    out_log = log_dir / "complete-demo-backend.log"
    err_log = log_dir / "complete-demo-backend.err.log"
    pid_file = log_dir / "complete-demo-backend.pid"

    restarts: list[float] = []
    attempt = 0
    print(f"[watchdog] backend supervisor on http://{host}:{port}; auto-restart on crash")
    while True:
        stdout = open(out_log, "a", encoding="utf-8")
        stderr = open(err_log, "a", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, "-m", "scripts.run_api", "--serve"],
            cwd=str(PROJECT_ROOT),
            stdout=stdout,
            stderr=stderr,
        )
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        now = time.time()
        restarts = [t for t in restarts if now - t < 3600]
        print(f"[watchdog] backend up (pid {proc.pid})")
        try:
            proc.wait()
        except KeyboardInterrupt:  # 手动 Ctrl+C：先停后端再退出
            print("[watchdog] shutting down backend...")
            _terminate(proc)
            return
        finally:
            stdout.close()
            stderr.close()

        code = proc.returncode
        if code == 0:
            print("[watchdog] backend exited cleanly (code 0); supervisor stops.")
            return
        print(f"[watchdog] backend exited with code {code}; restarting...")
        if len(restarts) >= WATCHDOG_MAX_RESTARTS_PER_HOUR:
            print(
                f"[watchdog] exceeded {WATCHDOG_MAX_RESTARTS_PER_HOUR} restarts in one hour; "
                "stopping. Check tmp/complete-demo-backend.err.log"
            )
            return
        restarts.append(time.time())
        delay = WATCHDOG_BACKOFF[min(attempt, len(WATCHDOG_BACKOFF) - 1)]
        attempt += 1
        print(f"[watchdog] waiting {delay}s before restart (attempt {attempt})")
        time.sleep(delay)


def _terminate(proc: subprocess.Popen) -> None:
    """跨平台终止子进程（Windows 无 SIGTERM，使用 terminate/kill）。"""
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:  # noqa: BLE001 - 终止失败则强杀
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    args = [arg.lower() for arg in sys.argv[1:]]
    if "--serve" in args:
        _serve()
    elif "--watchdog" in args:
        _watchdog()
    else:
        _serve()


if __name__ == "__main__":
    main()
