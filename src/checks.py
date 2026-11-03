"""系统检查引擎：环境配置 / 依赖 / 代码完善度 / 前后端连接 四组检查。

供两类入口复用，避免两套逻辑漂移：
- CLI：``scripts/run_env_check.py``
- Web：``src/api/app.py`` 的 ``GET /api/check``

设计约束：
- 本模块顶层只依赖标准库（可选能力如 playwright 在函数内延迟导入）；
- 每个检查项返回 ``{id, label, status, detail, duration_ms}``，
  status ∈ ok / warn / fail / skip；
- ``run_checks()`` 产出可直接 JSON 序列化的报告，永不抛异常（单项失败记 fail）。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECK_REPORT_DEFAULT = PROJECT_ROOT / "tmp" / "check_report.json"

# 检查分组（顺序即展示顺序）
GROUP_LABELS: dict[str, str] = {
    "env": "环境配置",
    "deps": "依赖检查",
    "code": "代码完善度",
    "connect": "前后端连接",
}
VALID_GROUPS = tuple(GROUP_LABELS)

# .env 必填键（缺失视为环境未配置完成）
REQUIRED_ENV_KEYS = [
    "BACKEND_HOST",
    "BACKEND_PORT",
    "API_BASE_URL",
    "SEARCH_PROVIDER",
    "GOOGLE_TRENDS_ENABLED",
    "PLATFORM_RANKING_PROVIDERS",
    "POLICY_SOURCES",
    "VITE_PROXY_TARGET",
]

# 可选键（可留空，项目按“无 Key 回退 mock”设计，仅提示）
OPTIONAL_ENV_KEYS = [
    "OPENAI_API_KEY",
    "AI_API_KEY",
    "SEARCH_API_KEY",
    "KEEPA_API_KEY",
    "EBAY_APP_ID",
    "EBAY_DEV_ID",
    "EBAY_CERT_ID",
    "COMTRADE_SUBSCRIPTION_KEY",
    "OPEN_FOOD_FACTS_ENABLED",
    "GOOGLE_TRENDS_COOKIE",
    "SUPPLIER_CLI_PATH",
    "AI_PROXY_URL",
    "AI_NO_PROXY_FLAG",
    "SEARCH_PROXY_URL",
]

# 发行包名 -> 导入名（默认把 - 换成 _ 即可，这里仅列特例）
IMPORT_NAME_OVERRIDES = {
    "fg-data-profiling": ("ydata_profiling", "fg_data_profiling"),
    "python-dotenv": ("dotenv",),
    "scikit-learn": ("sklearn",),
    "scikit-posthocs": ("scikit_posthocs",),
    "beautifulsoup4": ("bs4",),
    "pyyaml": ("yaml",),
    "pillow": ("PIL",),
}

# 前端关键依赖（node_modules 存在性检查）
FRONTEND_KEY_PACKAGES = [
    "react",
    "react-dom",
    "vite",
    "echarts",
    "three",
    "zustand",
    "@tanstack/react-query",
    "tailwindcss",
    "typescript",
    "lucide-react",
]

# 关键产物（数据/模型/前端构建）
REQUIRED_ARTIFACTS: list[tuple[str, str]] = [
    ("data/processed/clean_data.csv", "清洗后历史数据"),
    ("models/forecast.csv", "预测结果"),
    ("models/recommendations.csv", "Top N 推荐"),
    ("models/metrics.json", "模型指标"),
    ("output/app/index.html", "React 前端构建"),
    ("output/dashboard.html", "在线看板页面"),
    ("output/dashboard-data.json", "看板数据"),
    ("output/data_status.json", "每日数据更新状态"),
    ("output/app-offline.html", "离线单文件前端"),
]

REQUIRED_ENTRY_POINTS: list[tuple[str, str]] = [
    ("scripts/run_api.py", "统一后端入口"),
    ("frontend/package.json", "前端工程"),
    ("start_complete_demo.ps1", "一键启动脚本"),
    ("一键启动.bat", "一键启动批处理"),
]

# 请求关键端点：期望 200；None 表示特殊处理。
# 注意：/api/dashboard-data 全量 55MB（6.5s）不再在此探测，避免自检超时
# 与页面结果矛盾（建议报告 B5）；改由 _probe_dashboard_data_meta 轻量检查。
CONNECT_ENDPOINTS: list[tuple[str, str, Callable[[Any], str] | None]] = [
    ("/api/health", "服务健康检查", None),
    ("/api/categories", "品类字典", None),
    ("/api/markets", "市场字典", None),
    ("/api/engineering/status", "工程化状态", None),
    ("/api/system/eval", "系统评测指标", None),
    ("/api/jobs", "后台任务注册表", None),
]

STATUS_ORDER = {"ok": 0, "warn": 1, "fail": 2, "skip": 3}


def _result(
    check_id: str,
    label: str,
    status: str,
    detail: str = "",
    duration_ms: int = 0,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "detail": detail,
        "duration_ms": int(duration_ms),
    }


def _timed(producer: Callable[[], tuple[str, str]]) -> dict[str, Any]:
    """包装一个返回 (status, detail) 的检查函数，附加耗时。"""
    start = time.perf_counter()
    try:
        status, detail = producer()
    except Exception as exc:  # noqa: BLE001 - 引擎兜底，单项失败不中断
        status, detail = "fail", f"检查内部异常：{type(exc).__name__}: {exc}"
    duration_ms = int((time.perf_counter() - start) * 1000)
    return status, detail, duration_ms


def _http_get(
    url: str,
    timeout: int = 5,
    headers: dict[str, str] | None = None,
) -> tuple[int | None, Any, bytes | None, str | None]:
    """安全 GET；返回 (status, headers, body, error)。"""
    request = urllib.request.Request(
        url,
        headers=headers or {"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, resp.headers, resp.read(), None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read()
        except Exception:  # noqa: BLE001
            body = None
        return exc.code, exc.headers, body, None
    except Exception as exc:  # noqa: BLE001 - 连接失败 / 超时
        return None, None, None, str(exc)


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in re.split(r"[.\-+]", version.strip()):
        if part.isdigit():
            parts.append(int(part))
        elif not parts:
            continue
        else:
            break
    return tuple(parts)


def _parse_requirement(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    match = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*(.*)$", line)
    if not match:
        return None
    spec = match.group(2).strip()
    constraints: list[tuple[str, str]] = []
    for clause in [c.strip() for c in spec.split(",") if c.strip()]:
        clause_match = re.match(r"^(==|>=|<=|>|<|!=)\s*([0-9][A-Za-z0-9.\-+]*)$", clause)
        if clause_match:
            constraints.append((clause_match.group(1), clause_match.group(2)))
    return {
        "name": match.group(1),
        "constraints": constraints,
        "raw": line,
    }


def _dist_name(name: str) -> str:
    return name.lower().replace("_", "-")


def _import_names(dist_name: str) -> tuple[str, ...]:
    lower = dist_name.lower()
    if lower in IMPORT_NAME_OVERRIDES:
        return IMPORT_NAME_OVERRIDES[lower]
    return (lower.replace("-", "_"),)


def _merge_env(env_file: Path | None) -> dict[str, str]:
    """合并 os.environ 与 .env 文件（.env 仅作补充，进程环境优先）。"""
    merged = dict(os.environ)
    if env_file and env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key and key not in merged:
                merged[key] = value.strip().strip('"').strip("'")
    return merged


def _run_subprocess(
    args: list[str] | str,
    cwd: Path | None = None,
    timeout: int = 60,
    shell: bool = False,
) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        return -1, str(exc.stdout or ""), f"超时（>{timeout}s）"
    except Exception as exc:  # noqa: BLE001
        return -1, "", f"执行失败：{type(exc).__name__}: {exc}"


# =========================================================================
# env 组
# =========================================================================

def _check_python_version() -> tuple[str, str]:
    version = sys.version_info
    label = f"{version.major}.{version.minor}.{version.micro}"
    if version >= (3, 12):
        return "ok", f"Python {label}（项目目标版本 3.12）"
    if version >= (3, 10):
        return "warn", f"Python {label}（建议 3.12，最低 3.10）"
    return "fail", f"Python {label}（低于最低要求 3.10）"


def _check_venv() -> tuple[str, str]:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    in_venv = sys.prefix.startswith(str(PROJECT_ROOT / ".venv"))
    if venv_python.exists():
        if in_venv:
            return "ok", "使用项目虚拟环境 .venv"
        return "warn", ".venv 存在但当前解释器未激活（建议使用 .venv\\Scripts\\python.exe）"
    if in_venv:
        return "ok", f"运行于虚拟环境 {sys.prefix}"
    return "warn", "未发现 .venv（可使用 .venv\\Scripts\\python -m venv .venv 创建）"


def _check_node() -> tuple[str, str]:
    node = shutil.which("node")
    if not node:
        return "warn", "未找到 node（仅前端构建/typecheck 需要）"
    code, out, err = _run_subprocess([node, "--version"], timeout=15)
    if code != 0:
        return "warn", f"node 执行失败：{err.strip()[:80]}"
    return "ok", f"node {out.strip()}"


def _check_pnpm() -> tuple[str, str]:
    if not shutil.which("pnpm"):
        return "warn", "未找到 pnpm（仅前端构建/typecheck 需要）"
    code, out, err = _run_subprocess("pnpm --version", timeout=15, shell=True)
    if code != 0:
        return "warn", f"pnpm 执行失败：{err.strip()[:80]}"
    return "ok", f"pnpm {out.strip()}"


def _check_env_file() -> tuple[str, str]:
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        return "ok", f".env 存在（{env_file}）"
    example = PROJECT_ROOT / ".env.example"
    hint = "请复制 .env.example 为 .env 并按需填写" if example.exists() else "缺少 .env"
    return "fail", hint


def _check_env_keys() -> tuple[str, str]:
    env_file = PROJECT_ROOT / ".env"
    merged = _merge_env(env_file if env_file.exists() else None)
    missing = [key for key in REQUIRED_ENV_KEYS if not (merged.get(key) or "").strip()]
    empty_optional = [
        key for key in OPTIONAL_ENV_KEYS if not (merged.get(key) or "").strip()
    ]
    parts = []
    if not missing:
        parts.append(f"必填键 {len(REQUIRED_ENV_KEYS)}/{len(REQUIRED_ENV_KEYS)} 齐全")
        status = "ok"
    else:
        parts.append(f"缺少必填键：{', '.join(missing)}")
        status = "fail"
    if empty_optional:
        parts.append(f"可选键留空（按设计回退 mock）：{len(empty_optional)} 项")
        if status == "ok":
            status = "ok" if len(empty_optional) <= 6 else "warn"
    return status, "；".join(parts)


def _check_writable_dirs() -> tuple[str, str]:
    targets = [PROJECT_ROOT / "output", PROJECT_ROOT / "tmp"]
    bad: list[str] = []
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / f".check_probe_{os.getpid()}"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            bad.append(f"{target.name}（{exc}）")
    if bad:
        return "fail", "不可写：" + "；".join(bad)
    return "ok", "output/ 与 tmp/ 目录可写"


def run_env_group() -> list[dict[str, Any]]:
    items = [
        ("env.python", "Python 版本", _check_python_version),
        ("env.venv", "虚拟环境", _check_venv),
        ("env.node", "Node.js", _check_node),
        ("env.pnpm", "pnpm", _check_pnpm),
        ("env.env_file", ".env 文件", _check_env_file),
        ("env.env_keys", ".env 关键配置", _check_env_keys),
        ("env.writable", "输出目录可写", _check_writable_dirs),
    ]
    results: list[dict[str, Any]] = []
    for check_id, label, producer in items:
        status, detail, duration_ms = _timed(producer)
        results.append(_result(check_id, label, status, detail, duration_ms))
    return results


# =========================================================================
# deps 组
# =========================================================================

def _check_python_requirements() -> tuple[str, str]:
    req_file = PROJECT_ROOT / "requirements.txt"
    if not req_file.exists():
        return "fail", "缺少 requirements.txt"
    entries = [
        entry
        for line in req_file.read_text(encoding="utf-8").splitlines()
        if (entry := _parse_requirement(line)) is not None
    ]
    if not entries:
        return "fail", "requirements.txt 无有效依赖条目"
    missing: list[str] = []
    mismatch: list[str] = []
    checked = 0
    for entry in entries:
        dist = _dist_name(entry["name"])
        try:
            installed = metadata.version(dist)
        except metadata.PackageNotFoundError:
            missing.append(entry["name"])
            continue
        checked += 1
        for op, want in entry["constraints"]:
            installed_v = _version_tuple(installed)
            want_v = _version_tuple(want)
            if op == "==" and installed_v != want_v:
                mismatch.append(f"{entry['name']} {installed} != {want}")
            elif op == ">=" and installed_v < want_v:
                mismatch.append(f"{entry['name']} {installed} < {want}")
    status = "ok"
    parts = [f"{checked}/{len(entries)} 已安装"]
    if missing:
        status = "fail"
        parts.append("缺失：" + ", ".join(missing[:8]))
    if mismatch:
        status = "fail"
        parts.append("版本不符：" + "; ".join(mismatch[:5]))
    if status == "ok":
        parts.append("版本约束全部满足")
    return status, "；".join(parts)


def _check_lock_file() -> tuple[str, str]:
    lock = PROJECT_ROOT / "requirements.lock"
    if lock.exists():
        return "ok", f"requirements.lock 存在（{lock.stat().st_size} B）"
    return "warn", "缺少 requirements.lock（可选，用于版本固化）"


def _check_node_modules() -> tuple[str, str]:
    nm = PROJECT_ROOT / "frontend" / "node_modules"
    if not nm.exists():
        return "fail", "frontend/node_modules 缺失（在 frontend/ 下执行 pnpm install）"
    return "ok", "frontend/node_modules 存在"


def _check_frontend_packages() -> tuple[str, str]:
    nm = PROJECT_ROOT / "frontend" / "node_modules"
    if not nm.exists():
        return "skip", "node_modules 缺失，跳过包解析"
    missing = [
        name for name in FRONTEND_KEY_PACKAGES if not (nm / name / "package.json").exists()
    ]
    if missing:
        return "fail", "关键包缺失：" + ", ".join(missing)
    return "ok", f"关键包 {len(FRONTEND_KEY_PACKAGES)}/{len(FRONTEND_KEY_PACKAGES)} 就绪"


def _check_playwright_browsers() -> tuple[str, str]:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return "warn", "playwright 未安装（仅 --browser 浏览器级检查需要）"
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright",
        Path.home() / "AppData" / "Local" / "ms-playwright",
    ]
    for root in candidates:
        if root.exists() and any(root.iterdir()):
            return "ok", "playwright chromium 浏览器已安装"
    return "warn", "playwright 已装但未下载浏览器（仅 --browser 需要，可 npx playwright install chromium）"


def run_deps_group() -> list[dict[str, Any]]:
    items = [
        ("deps.python_requirements", "Python 依赖（requirements.txt）", _check_python_requirements),
        ("deps.lock_file", "依赖锁定文件", _check_lock_file),
        ("deps.node_modules", "前端 node_modules", _check_node_modules),
        ("deps.frontend_packages", "前端关键包", _check_frontend_packages),
        ("deps.playwright_browsers", "Playwright 浏览器", _check_playwright_browsers),
    ]
    results: list[dict[str, Any]] = []
    for check_id, label, producer in items:
        status, detail, duration_ms = _timed(producer)
        results.append(_result(check_id, label, status, detail, duration_ms))
    return results


# =========================================================================
# code 组
# =========================================================================

_IMPORT_SMOKE_SCRIPT = r"""
import importlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1]) / "src"
mods = []
for p in sorted(root.rglob("*.py")):
    rel = p.relative_to(root)
    parts = list(rel.parts[:-1]) + ([rel.stem] if rel.name != "__init__.py" else [])
    if not parts:
        continue
    mods.append("src." + ".".join(parts))
failed = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as exc:
        failed.append(f"{{m}}: {{type(exc).__name__}}: {{exc}}")
print("IMPORT_SMOKE " + json.dumps({"mods": len(mods), "failed": failed[:40]}))
"""

_IMPORT_SMOKE_CACHE: dict[
    tuple[str, str],
    tuple[float, tuple[str, str]],
] = {}
_IMPORT_SMOKE_TTL_SECONDS = 300


def _import_smoke_key() -> tuple[str, str]:
    """源码 mtime 签名 + 解释器路径，源码或解释器变化即失效。"""
    src_root = PROJECT_ROOT / "src"
    files = sorted(src_root.rglob("*.py")) if src_root.exists() else []
    newest = max((path.stat().st_mtime_ns for path in files), default=0)
    return (sys.executable, f"{len(files)}|{newest}")


def _check_import_smoke_impl() -> tuple[str, str]:
    code, out, err = _run_subprocess(
        [sys.executable, "-c", _IMPORT_SMOKE_SCRIPT, str(PROJECT_ROOT)],
        cwd=PROJECT_ROOT,
        timeout=300,
    )
    failed_lines: list[str] = []
    total = 0
    for line in out.splitlines():
        if line.startswith("IMPORT_SMOKE "):
            try:
                payload = json.loads(line[len("IMPORT_SMOKE "):])
                total = int(payload.get("mods") or 0)
                failed_lines = [str(item) for item in (payload.get("failed") or [])]
            except (json.JSONDecodeError, TypeError, ValueError):
                total = 0
                failed_lines = []
    if failed_lines:
        return "fail", f"{total} 个模块中 {len(failed_lines)} 个导入失败：{'；'.join(failed_lines[:3])}"
    if code != 0:
        return "fail", f"导入冒烟进程异常退出（exit {code}）：{err.strip()[:120]}"
    return "ok", f"src/ 下 {total} 个模块全部可导入"


def _check_import_smoke() -> tuple[str, str]:
    """导入冒烟子进程按源码版本缓存，热机自检避免重复 4.5s+。"""
    key = _import_smoke_key()
    now = time.time()
    hit = _IMPORT_SMOKE_CACHE.get(key)
    if hit is not None and now - hit[0] <= _IMPORT_SMOKE_TTL_SECONDS:
        status, detail = hit[1]
        return status, detail + "（基于缓存，未重新导入）"
    status, detail = _check_import_smoke_impl()
    _IMPORT_SMOKE_CACHE[key] = (now, (status, detail))
    return status, detail


def _check_artifacts() -> tuple[str, str]:
    missing = [
        f"{name}（{label}）"
        for name, label in REQUIRED_ARTIFACTS
        if not (PROJECT_ROOT / name).exists()
    ]
    if missing:
        return "fail", "缺失产物：" + "；".join(missing)
    return "ok", f"关键产物 {len(REQUIRED_ARTIFACTS)}/{len(REQUIRED_ARTIFACTS)} 齐全"


def _check_entry_points() -> tuple[str, str]:
    missing = [
        name for name, _label in REQUIRED_ENTRY_POINTS if not (PROJECT_ROOT / name).exists()
    ]
    if missing:
        return "fail", "缺失入口：" + "；".join(missing)
    return "ok", f"关键入口 {len(REQUIRED_ENTRY_POINTS)}/{len(REQUIRED_ENTRY_POINTS)} 齐全"


_TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK|Not" + "Implemented)\b", re.IGNORECASE)
_TODO_DIRS = ("src", "scripts", "frontend/src", "tests")


def _check_todo_scan() -> tuple[str, str]:
    total = 0
    by_file: list[tuple[int, str]] = []
    for rel_dir in _TODO_DIRS:
        base = PROJECT_ROOT / rel_dir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "node_modules" in path.parts or ".venv" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            count = len(_TODO_RE.findall(text))
            if count:
                total += count
                by_file.append((count, str(path.relative_to(PROJECT_ROOT))))
    by_file.sort(reverse=True)
    top = "；".join(f"{name} ×{count}" for count, name in by_file[:5])
    status = "warn" if total > 50 else "ok"
    detail = f"共 {total} 处待办标记" + (f"（{top}）" if top else "")
    return status, detail


def _check_config_consistency() -> tuple[str, str]:
    try:
        from src.config import CATEGORIES, CATEGORY_KEYWORDS, MARKETS, RECOMMEND_WEIGHTS
    except Exception as exc:  # noqa: BLE001
        return "fail", f"src.config 导入失败：{type(exc).__name__}: {exc}"
    problems: list[str] = []
    if not CATEGORIES:
        problems.append("CATEGORIES 为空")
    if not MARKETS:
        problems.append("MARKETS 为空")
    uncovered = [code for code in CATEGORIES if code not in CATEGORY_KEYWORDS]
    if uncovered:
        problems.append(f"CATEGORY_KEYWORDS 未覆盖品类：{', '.join(uncovered[:5])}")
    if len(RECOMMEND_WEIGHTS) != 4:
        problems.append(f"RECOMMEND_WEIGHTS 维度数异常（{len(RECOMMEND_WEIGHTS)}）")
    if problems:
        return "fail", "；".join(problems)
    return "ok", f"{len(CATEGORIES)} 品类 × {len(MARKETS)} 市场，关键词覆盖齐全"


def _check_build_freshness() -> tuple[str, str]:
    index_html = PROJECT_ROOT / "output" / "app" / "index.html"
    src_root = PROJECT_ROOT / "frontend" / "src"
    if not index_html.exists() or not src_root.exists():
        return "skip", "前端构建或源码缺失，跳过时效检查"
    newest_src = max(
        (p.stat().st_mtime for p in src_root.rglob("*") if p.is_file()),
        default=0,
    )
    built_at = index_html.stat().st_mtime
    if newest_src > built_at + 3600:
        return "warn", "frontend/src 有比 output/app 更新的改动（建议 pnpm run build 重建）"
    return "ok", "前端构建产物未过期"


def _check_eng_status() -> tuple[str, str]:
    eng_file = PROJECT_ROOT / "output" / "eng_status.json"
    if not eng_file.exists():
        return "ok", "无 eng_status.json（信息项）"
    try:
        data = json.loads(eng_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "warn", "eng_status.json 解析失败"
    passed = data.get("test_passed")
    collected = data.get("test_collected")
    generated = str(data.get("generated_at") or "")[:19]
    if passed is None:
        return "ok", f"eng_status.json（{generated}）"
    return "ok", f"上次测试 {passed}/{collected} 通过（{generated}）"


def _check_pytest() -> tuple[str, str]:
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "--basetemp=tmp/pytest-check",
        "tests",
        "-q",
    ]
    code, out, err = _run_subprocess(pytest_cmd, cwd=PROJECT_ROOT, timeout=1800)
    tail = (out + "\n" + err).strip().splitlines()
    tail_text = " | ".join(line.strip() for line in tail[-3:] if line.strip())[:300]
    passed = re.search(r"(\d+) passed", out)
    skipped = re.search(r"(\d+) skipped", out)
    failed = re.search(r"(\d+) failed", out)
    if code != 0 or (failed and int(failed.group(1)) > 0):
        return "fail", f"pytest 未全绿（exit {code}）：{tail_text}"
    parts = []
    if passed:
        parts.append(f"{passed.group(1)} passed")
    if skipped:
        parts.append(f"{skipped.group(1)} skipped")
    return "ok", "pytest " + " / ".join(parts) if parts else f"pytest 通过（exit 0）"


def _check_typecheck() -> tuple[str, str]:
    frontend = PROJECT_ROOT / "frontend"
    if not shutil.which("pnpm"):
        return "skip", "未找到 pnpm，跳过 typecheck"
    code, out, err = _run_subprocess("pnpm typecheck", cwd=frontend, timeout=600, shell=True)
    tail = (out + "\n" + err).strip().splitlines()
    tail_text = " | ".join(line.strip() for line in tail[-3:] if line.strip())[:300]
    if code != 0:
        return "fail", f"tsc --noEmit 未通过（exit {code}）：{tail_text}"
    return "ok", "tsc --noEmit 通过"


def run_code_group(depth: str = "quick") -> list[dict[str, Any]]:
    items = [
        ("code.import_smoke", "模块导入冒烟", _check_import_smoke),
        ("code.artifacts", "关键产物清单", _check_artifacts),
        ("code.entry_points", "关键入口文件", _check_entry_points),
        ("code.todo_scan", "待办标记扫描", _check_todo_scan),
        ("code.config_consistency", "配置一致性", _check_config_consistency),
        ("code.build_freshness", "前端构建时效", _check_build_freshness),
        ("code.eng_status", "上次测试状态", _check_eng_status),
    ]
    if depth == "full":
        items.append(("code.pytest", "pytest 全套测试", _check_pytest))
        items.append(("code.typecheck", "前端 TypeScript 检查", _check_typecheck))
    results: list[dict[str, Any]] = []
    for check_id, label, producer in items:
        status, detail, duration_ms = _timed(producer)
        results.append(_result(check_id, label, status, detail, duration_ms))
    return results


# =========================================================================
# connect 组
# =========================================================================

def _describe_status(status: int | None) -> str:
    if status is None:
        return "不可达"
    return f"HTTP {status}"


def _connect_result(
    label: str,
    status_code: int | None,
    error: str | None,
    ok_detail: str,
    backend_reachable: bool,
    allow_503_warn: bool = False,
) -> tuple[str, str]:
    """把 HTTP 探测结果统一转成 (status, detail)。"""
    if status_code is None:
        if backend_reachable:
            return "fail", f"请求失败：{error or '未知错误'}"
        return "skip", "后端不可达，跳过"
    if status_code == 200:
        return "ok", ok_detail
    if status_code == 503 and allow_503_warn:
        return "warn", "HTTP 503（决策数据闸 data_gap，按设计拒绝 mock 计算）"
    return "fail", f"{label} 返回 {_describe_status(status_code)}"


def _cors_check(allowed: str) -> tuple[str, str]:
    """Classify the CORS allow-origin header for the self-check report."""
    allowed = allowed.strip()
    if allowed == "*":
        return "warn", "Access-Control-Allow-Origin: *（建议按部署域名收紧）"
    if allowed:
        return "ok", f"Access-Control-Allow-Origin: {allowed}"
    return "warn", "HTTP 200 但无 Access-Control-Allow-Origin 头（开发分离模式可能受影响）"


def _start_backend() -> tuple[bool, str]:
    """按需启动统一后端，等待健康；返回 (是否就绪, 说明)。"""
    log_dir = PROJECT_ROOT / "tmp"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / "check-backend.log"
    python = sys.executable
    try:
        proc = subprocess.Popen(
            [python, "scripts/run_api.py"],
            cwd=str(PROJECT_ROOT),
            stdout=open(log, "w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"后端启动失败：{type(exc).__name__}: {exc}"
    base = _default_base_url()
    for _ in range(30):
        time.sleep(0.5)
        if proc.poll() is not None:
            return False, f"后端进程提前退出（exit {proc.returncode}），日志：{log}"
        status, _headers, _body, error = _http_get(base + "/api/health", timeout=2)
        if status == 200:
            return True, f"已自动启动后端（pid {proc.pid}），日志：{log}"
    return False, f"后端启动超时，日志：{log}"


def _default_base_url() -> str:
    host = os.environ.get("BACKEND_HOST", "127.0.0.1")
    port = os.environ.get("BACKEND_PORT", os.environ.get("API_PORT", "8000"))
    return f"http://{host}:{port}"


def run_connect_group(
    base_url: str | None = None,
    start_backend: bool = False,
    browser: bool = False,
) -> list[dict[str, Any]]:
    base = (base_url or _default_base_url()).rstrip("/")
    results: list[dict[str, Any]] = []

    # 1) 后端可达性（可能自动拉起）
    def _probe_backend() -> tuple[str, str]:
        started = False
        hint = ""
        status, _headers, body, error = _http_get(base + "/api/health", timeout=4)
        if status is None and start_backend and not started:
            started = True
            ok, note = _start_backend()
            if ok:
                status, _headers, body, error = _http_get(base + "/api/health", timeout=4)
                hint = note
        if status == 200:
            return "ok", f"后端在线（{base}）" + (f"；{hint}" if hint else "")
        return (
            "fail",
            f"未检测到后端（{base}）：{error or f'HTTP {status}'}；"
            "可运行 .venv\\Scripts\\python scripts\\run_api.py 或一键启动.bat（--start-backend 可自动拉起）",
        )

    backend_status, backend_detail, backend_ms = _timed(_probe_backend)
    backend_reachable = backend_status == "ok"
    results.append(_result("connect.backend_up", "后端服务可达", backend_status, backend_detail, backend_ms))

    # 2) 关键端点
    def _probe_endpoint(path: str, label: str) -> tuple[str, str]:
        status, _headers, body, error = _http_get(base + path, timeout=5)
        detail = f"{path} → {_describe_status(status)}"
        if status == 200 and body:
            try:
                payload = json.loads(body.decode("utf-8"))
                if isinstance(payload, dict) and len(payload) == 0:
                    return "warn", detail + "（返回空对象）"
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
        return _connect_result(label, status, error, detail, backend_reachable)

    for path, label, _check in CONNECT_ENDPOINTS:
        status, detail, ms = _timed(lambda p=path, l=label: _probe_endpoint(p, l))
        results.append(_result(f"connect{path.replace('/', '.')}", label, status, detail, ms))

    # 2.5) 看板聚合数据（轻量元数据模式，避免拉 55MB 全量导致自检超时）
    def _probe_dashboard_data_meta() -> tuple[str, str]:
        status, _headers, body, error = _http_get(base + "/api/dashboard-data?meta=1", timeout=15)
        if status != 200 or not body:
            return _connect_result(
                "看板聚合数据",
                status,
                error,
                "/api/dashboard-data?meta=1 → HTTP 200",
                backend_reachable,
            )
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "fail", "/api/dashboard-data?meta=1 返回非 JSON"
        if not payload.get("ok"):
            return "fail", f"看板数据不可用：{payload.get('detail') or 'unknown'}"
        size_mb = payload.get("size_mb")
        as_of = payload.get("data_as_of") or "未知"
        return "ok", f"看板数据就绪（{size_mb}MB，数据截至 {as_of}）"

    status, detail, ms = _timed(_probe_dashboard_data_meta)
    results.append(_result("connect.dashboard_data", "看板聚合数据", status, detail, ms))

    # 3) 推荐接口（决策闸 503 视为 warn）
    def _probe_recommendations() -> tuple[str, str]:
        status, _headers, _body, error = _http_get(base + "/api/recommendations", timeout=5)
        return _connect_result(
            "选品推荐",
            status,
            error,
            "/api/recommendations → HTTP 200",
            backend_reachable,
            allow_503_warn=True,
        )

    status, detail, ms = _timed(_probe_recommendations)
    results.append(_result("connect.recommendations", "选品推荐接口", status, detail, ms))

    # 4) /app 页面与静态资源
    def _probe_app_page() -> tuple[str, str]:
        status, headers, body, error = _http_get(base + "/app", timeout=5)
        if status == 200 and body:
            text = body.decode("utf-8", errors="ignore")
            if '<div id="root">' in text:
                return "ok", "/app → HTTP 200（React 挂载点就绪）"
            return "fail", "/app → HTTP 200 但缺少 #root 挂载点（output/app 构建可能损坏）"
        return _connect_result("React 前端页面", status, error, "/app → HTTP 200", backend_reachable)

    status, detail, ms = _timed(_probe_app_page)
    results.append(_result("connect.app_page", "React 前端页面", status, detail, ms))

    def _probe_static_asset() -> tuple[str, str]:
        assets = PROJECT_ROOT / "output" / "app" / "assets"
        if not assets.exists() or not any(assets.iterdir()):
            return "skip", "output/app/assets 为空，跳过"
        name = sorted(p.name for p in assets.iterdir() if p.is_file())[0]
        status, _headers, _body, error = _http_get(base + "/app/assets/" + name, timeout=5)
        if status == 200:
            return "ok", f"静态资源 /app/assets/{name} → HTTP 200"
        return _connect_result("静态资源", status, error, "", backend_reachable)

    status, detail, ms = _timed(_probe_static_asset)
    results.append(_result("connect.static_asset", "前端静态资源", status, detail, ms))

    # 5) CORS
    def _probe_cors() -> tuple[str, str]:
        status, headers, _body, error = _http_get(
            base + "/api/categories",
            timeout=5,
            headers={"Origin": "http://localhost:5173"},
        )
        if status is None:
            return _connect_result("CORS 头", status, error, "", backend_reachable)
        allowed = ""
        if headers:
            allowed = str(headers.get("Access-Control-Allow-Origin") or "")
        if status == 200 and allowed:
            return _cors_check(allowed)
        if status == 200:
            return "warn", "HTTP 200 但无 Access-Control-Allow-Origin 头（开发分离模式可能受影响）"
        return "fail", f"CORS 探测返回 {_describe_status(status)}"

    status, detail, ms = _timed(_probe_cors)
    results.append(_result("connect.cors", "CORS 跨域头", status, detail, ms))

    # 6) 离线单文件（信息项）
    offline = PROJECT_ROOT / "output" / "app-offline.html"
    results.append(
        _result(
            "connect.offline_file",
            "离线单文件前端",
            "ok" if offline.exists() else "warn",
            f"output/app-offline.html {'存在' if offline.exists() else '缺失（不影响在线模式）'}",
        )
    )

    # 7) 浏览器级渲染（可选）
    if browser:
        def _probe_browser() -> tuple[str, str]:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as exc:
                return "warn", f"playwright 未安装：{exc}"
            try:
                with sync_playwright() as p:
                    browser_ctx = p.chromium.launch(headless=True)
                    page = browser_ctx.new_page(viewport={"width": 1440, "height": 900})
                    console_errors: list[str] = []
                    page.on(
                        "console",
                        lambda msg: console_errors.append(msg.text)
                        if msg.type == "error"
                        else None,
                    )
                    page.goto(base + "/app", wait_until="networkidle", timeout=60000)
                    page.wait_for_selector("text=系统控制台", timeout=60000)
                    browser_ctx.close()
            except Exception as exc:  # noqa: BLE001 - 浏览器缺失/启动失败降级 warn
                return "warn", f"浏览器检查不可用：{type(exc).__name__}: {str(exc)[:120]}"
            if console_errors:
                return "warn", f"页面渲染成功但存在 {len(console_errors)} 条 console 错误（首条：{console_errors[0][:100]}）"
            return "ok", "headless 打开 /app 渲染成功，无 console 错误"

        status, detail, ms = _timed(_probe_browser)
        results.append(_result("connect.browser", "浏览器级渲染", status, detail, ms))

    return results


# =========================================================================
# 汇总与入口
# =========================================================================

def run_checks(
    groups: list[str] | None = None,
    depth: str = "quick",
    base_url: str | None = None,
    start_backend: bool = False,
    browser: bool = False,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """运行一组检查并返回 JSON 可序列化报告。永不抛异常（单项失败记 fail）。"""
    if depth not in ("quick", "full"):
        depth = "quick"
    selected = [g for g in (groups or list(VALID_GROUPS)) if g in GROUP_LABELS]

    group_results: dict[str, dict[str, Any]] = {}
    for name in VALID_GROUPS:
        if name not in selected:
            continue
        if name == "env":
            results = run_env_group()
        elif name == "deps":
            results = run_deps_group()
        elif name == "code":
            results = run_code_group(depth=depth)
        else:
            results = run_connect_group(
                base_url=base_url,
                start_backend=start_backend,
                browser=browser,
            )
        group_results[name] = {"label": GROUP_LABELS[name], "results": results}

    summary = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
    for group in group_results.values():
        for item in group["results"]:
            summary[item["status"]] = summary.get(item["status"], 0) + 1

    report: dict[str, Any] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "depth": depth,
        "base_url": (base_url or _default_base_url()).rstrip("/"),
        "groups": group_results,
        "summary": summary,
        "overall": "fail" if summary["fail"] > 0 else "ok",
    }
    if out_path:
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return report


def exit_code(report: dict[str, Any]) -> int:
    """0 = 全过（warn 允许）；1 = 存在 fail；2 = 报告异常。"""
    if not isinstance(report, dict) or "summary" not in report:
        return 2
    return 1 if report.get("summary", {}).get("fail", 0) > 0 else 0
