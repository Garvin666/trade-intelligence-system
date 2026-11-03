"""检查引擎 src/checks.py 与 CLI scripts/run_env_check.py 的测试。

原则：
- 不依赖后端正在运行（connect 组用不可达地址验证“标记失败而非抛异常”）；
- 不递归执行 pytest（深度档只验证参数传递，不触发 pytest/typecheck 子进程）；
- 单项状态随环境变化（如缺失依赖），只断言不抛异常与结构正确。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import checks  # noqa: E402

ALL_STATUS = {"ok", "warn", "fail", "skip"}


def test_valid_groups_constant() -> None:
    assert checks.VALID_GROUPS == ("env", "deps", "code", "connect")
    assert set(checks.GROUP_LABELS) == set(checks.VALID_GROUPS)


def test_run_checks_quick_default_structure() -> None:
    report = checks.run_checks(depth="quick")
    assert isinstance(report, dict)
    assert report["depth"] == "quick"
    assert report["overall"] in ("ok", "fail")
    assert set(report["groups"]) == set(checks.VALID_GROUPS)
    summary = report["summary"]
    total = sum(summary.values())
    items = sum(len(g["results"]) for g in report["groups"].values())
    assert total == items
    for group in report["groups"].values():
        for item in group["results"]:
            assert item["status"] in ALL_STATUS
            assert item["id"] and item["label"]


def test_run_checks_group_filter() -> None:
    report = checks.run_checks(groups=["env"])
    assert set(report["groups"]) == {"env"}
    ids = [item["id"] for item in report["groups"]["env"]["results"]]
    assert "env.python" in ids and "env.env_keys" in ids


def test_run_checks_unknown_group_ignored() -> None:
    report = checks.run_checks(groups=["env", "bogus"])
    assert set(report["groups"]) == {"env"}


def test_run_checks_full_depth_without_code_ok() -> None:
    # 深度档若不含 code 组，不应触发 pytest/typecheck 子进程
    report = checks.run_checks(groups=["env"], depth="full")
    assert report["depth"] == "full"
    assert set(report["groups"]) == {"env"}


def test_code_group_quick_has_no_pytest() -> None:
    results = checks.run_code_group(depth="quick")
    ids = [item["id"] for item in results]
    assert "code.import_smoke" in ids
    assert "code.artifacts" in ids
    assert "code.entry_points" in ids
    assert "code.todo_scan" in ids
    assert "code.config_consistency" in ids
    assert "code.pytest" not in ids
    assert "code.typecheck" not in ids


def test_entry_points_no_longer_require_root_app_py() -> None:
    names = [name for name, _label in checks.REQUIRED_ENTRY_POINTS]
    assert "app.py" not in names
    assert "scripts/run_api.py" in names
    status, detail = checks._check_entry_points()
    assert status in ("ok", "fail")
    assert "app.py" not in detail


def test_cors_wildcard_is_warn() -> None:
    status, detail = checks._cors_check("*")
    assert status == "warn"
    assert "Access-Control-Allow-Origin: *" in detail
    status, detail = checks._cors_check("http://localhost:8000")
    assert status == "ok"


def test_env_group_never_raises() -> None:
    results = checks.run_env_group()
    for item in results:
        assert item["status"] in ALL_STATUS
        assert item["detail"] != "" or item["status"] == "ok"


def test_deps_group_never_raises() -> None:
    results = checks.run_deps_group()
    ids = [item["id"] for item in results]
    assert "deps.python_requirements" in ids
    assert "deps.node_modules" in ids
    for item in results:
        assert item["status"] in ALL_STATUS


def test_import_smoke_runs_and_counts_modules() -> None:
    status, detail = checks._check_import_smoke()
    assert status in ("ok", "fail")
    if status == "ok":
        assert "模块" in detail


def test_connect_unreachable_marks_fail_not_raise() -> None:
    results = checks.run_connect_group(base_url="http://127.0.0.1:9")
    by_id = {item["id"]: item for item in results}
    assert by_id["connect.backend_up"]["status"] == "fail"
    # 后端不可达时其余探测项应为 skip（不抛异常、不重复报错）
    for check_id, item in by_id.items():
        if check_id in ("connect.backend_up", "connect.offline_file"):
            continue
        assert item["status"] in ("skip", "warn", "fail"), check_id
    # 关键端点不会被误报为 ok
    assert all(
        by_id[cid]["status"] != "ok"
        for cid in ("connect.api.health", "connect.api.categories", "connect.api.jobs")
    )


def test_connect_endpoint_ids_exist() -> None:
    results = checks.run_connect_group(base_url="http://127.0.0.1:9")
    by_id = {item["id"]: item for item in results}
    for expected in (
        "connect.backend_up",
        "connect.api.health",
        "connect.recommendations",
        "connect.app_page",
        "connect.static_asset",
        "connect.cors",
        "connect.offline_file",
    ):
        assert expected in by_id, expected


def test_connect_browser_skips_without_flag() -> None:
    results = checks.run_connect_group(base_url="http://127.0.0.1:9", browser=False)
    assert all(item["id"] != "connect.browser" for item in results)


def test_exit_code() -> None:
    ok_report = {"summary": {"ok": 3, "warn": 1, "fail": 0, "skip": 0}}
    fail_report = {"summary": {"ok": 3, "warn": 1, "fail": 1, "skip": 0}}
    assert checks.exit_code(ok_report) == 0
    assert checks.exit_code(fail_report) == 1
    assert checks.exit_code({"nope": True}) == 2


def test_report_out_path(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    report = checks.run_checks(groups=["env"], out_path=out)
    assert out.exists()
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk["overall"] == report["overall"]
    assert set(on_disk["groups"]) == {"env"}


def test_cli_env_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from scripts.run_env_check import main

    out = tmp_path / "cli_report.json"
    code = main(["--groups", "env", "--json", "--out", str(out)])
    assert code in (0, 1)
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert payload["overall"] in ("ok", "fail")
    assert out.exists()


def test_cli_invalid_group_exits_2() -> None:
    from scripts.run_env_check import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--groups", "env,nope"])
    assert exc_info.value.code == 2
