"""Global AI config and page-driven control benchmark tests."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from fastapi.testclient import TestClient  # noqa: E402

from src.api import ai_config, brain_bridge, control_run  # noqa: E402
from src.api.app import app  # noqa: E402
from src.control import benchmark  # noqa: E402
from src.four_brain import ai_provider  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_ai_state() -> None:
    ai_config.clear_config()
    control_run._JOB.update(
        status="idle",
        job_id=None,
        mode="lite",
        progress=None,
        error=None,
        started_at=None,
        finished_at=None,
    )
    yield
    ai_config.clear_config()
    control_run._JOB.update(
        status="idle",
        job_id=None,
        mode="lite",
        progress=None,
        error=None,
        started_at=None,
        finished_at=None,
    )


def _write_control_files(
    tmp_path: Path,
    combos: list[tuple[str, str]],
) -> tuple[pd.DataFrame, list[str]]:
    dates = pd.date_range("2024-07-05", periods=104, freq="7D")
    train_frames: list[pd.DataFrame] = []
    holdout_frames: list[pd.DataFrame] = []
    for cat, mkt in combos:
        group = pd.DataFrame(
            {
                "date": dates,
                "category": cat,
                "market": mkt,
                "sales_volume": range(104),
            }
        )
        train_frames.append(group.iloc[:-12])
        holdout_frames.append(group.iloc[-12:])
    train = pd.concat(train_frames, ignore_index=True)
    holdout = pd.concat(holdout_frames, ignore_index=True)
    (tmp_path / "train.csv").write_text(train.to_csv(index=False), encoding="utf-8")
    (tmp_path / "holdout.csv").write_text(holdout.to_csv(index=False), encoding="utf-8")
    (tmp_path / "prompt.md").write_text(
        "请给出 holdout 期间的销量预测表与 Top 5 建议。", encoding="utf-8"
    )
    dates_str = sorted(holdout["date"].dt.strftime("%Y-%m-%d").unique().tolist())
    return holdout, dates_str


def _forecast_text(holdout: pd.DataFrame) -> str:
    rows = []
    for _, row in holdout.iterrows():
        date_str = row["date"].strftime("%Y-%m-%d")
        rows.append(
            f"| {row['category']} | {row['market']} | {date_str} | "
            f"{float(row['sales_volume']) + 1.0} |"
        )
    return (
        "## 预测表\n"
        "| category | market | date | predicted_sales_volume |\n"
        "|---|---|---|---|\n"
        + "\n".join(rows)
    )


def _write_github_signals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    combos: list[tuple[str, str]],
) -> Path:
    signal_path = tmp_path / "github_signals.json"
    rows = [
        {
            "source_type": "amazon_github",
            "category": category,
            "market": market,
            "keyword": "final_price",
            "value": 10.0,
            "title": "sample",
            "url": "https://example.com/item",
            "provider": "github/test",
            "fallback_used": False,
            "date": "2026-01-01",
        }
        for category, market in combos[:2]
    ]
    payload = {
        "generated_at": "2026-08-13T00:00:00Z",
        "sources": {
            "amazon": {
                "status": "ready",
                "label": "Amazon",
                "raw_rows": 1,
                "mapped_rows": len(rows),
                "skipped_rows": 0,
            }
        },
        "rows": rows,
    }
    signal_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(benchmark, "GITHUB_SIGNALS_JSON", signal_path)
    return signal_path


def _complete_response(holdout: pd.DataFrame) -> str:
    return (
        "## 核心洞察\n美国辣条搜索热度 95.7，建议备货 300 件。\n\n"
        + _forecast_text(holdout)
        + "\n\n## Top 5 选品建议\n"
        "1. cn_latiao × us：需求稳定。\n"
        "2. cn_changsha_mifen × sea：评论增长活跃。\n"
        "3. intl_matcha × eu：竞争度较低。\n"
        "4. intl_avocado × jp：季节性上行。\n"
        "5. cn_longjing × au：预测增长 25.7%。\n\n"
        "## 方法与不确定性\n使用线性外推与季节因子，假设延续当前趋势，"
        "置信区间 80%，风险为库存不足。\n"
    )


def test_ai_config_endpoint_is_masked() -> None:
    resp = client.get("/api/ai/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "api_key" not in body
    assert body["configured"] is False

    resp = client.post(
        "/api/ai/config",
        json={
            "api_key": "sk-test",
            "base_url": "https://example.com/v1",
            "model": "gpt-x",
            "timeout": 60,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["has_key"] is True
    assert body["model"] == "gpt-x"
    assert body["base_url"] == "https://example.com/v1"
    assert "api_key" not in body
    assert "sk-test" not in json.dumps(body)


def test_ai_config_defaults_to_deepseek(monkeypatch) -> None:
    ai_config.clear_config()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    resp = client.get("/api/ai/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["base_url"] == "https://api.deepseek.com/v1"
    assert body["model"] == "deepseek-chat"
    assert body["timeout"] == 120


def test_ai_config_normalizes_deepseek_base_url() -> None:
    resp = client.post(
        "/api/ai/config",
        json={"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_url"] == "https://api.deepseek.com/v1"
    assert body["model"] == "deepseek-chat"


def test_ai_test_without_config_returns_friendly_guide(monkeypatch) -> None:
    ai_config.clear_config()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    resp = client.post("/api/ai/test", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["configured"] is False
    assert "AI 未配置" in body["error"]
    assert "AI 接入" in body["error"]


def test_ai_test_uses_payload_credentials_before_saving(monkeypatch) -> None:
    ai_config.clear_config()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    def fake_chat_json(self: object, system: str, user: str, temperature: float = 0.2) -> dict[str, object]:
        return {"ok": True, "echo": "connected"}

    monkeypatch.setattr(ai_provider.OpenAICompatibleProvider, "chat_json", fake_chat_json)
    resp = client.post(
        "/api/ai/test",
        json={
            "api_key": "sk-payload",
            "base_url": "https://example.com/v1",
            "model": "payload-model",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["configured"] is True
    assert body["model"] == "payload-model"


def test_ai_config_can_be_cleared() -> None:
    client.post("/api/ai/config", json={"api_key": "sk-test", "model": "gpt-x"})
    assert client.get("/api/ai/config").json()["has_key"] is True
    resp = client.post("/api/ai/config", json={"api_key": "", "model": ""})
    body = resp.json()
    assert body["has_key"] is False
    assert body["configured"] is False


def test_ai_config_search_fields_are_masked() -> None:
    resp = client.post(
        "/api/ai/config",
        json={
            "search_provider": "tavily",
            "search_api_key": "tvly-secret-value",
            "search_api_url": "https://api.tavily.com/search",
            "search_max_results": 8,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["search_provider"] == "tavily"
    assert body["search_has_key"] is True
    assert body["search_max_results"] == 8
    assert "search_api_key" not in body
    assert "tvly-secret-value" not in json.dumps(body)


def test_ai_config_search_can_be_cleared() -> None:
    client.post(
        "/api/ai/config",
        json={
            "search_provider": "tavily",
            "search_api_key": "tvly-secret-value",
            "search_max_results": 8,
        },
    )
    resp = client.post(
        "/api/ai/config",
        json={
            "search_provider": "",
            "search_api_key": "",
            "search_api_url": "",
            "search_max_results": "",
        },
    )
    body = resp.json()
    assert body["search_has_key"] is False
    assert body["search_provider"] == "duckduckgo_html"
    assert body["search_max_results"] == 5


def test_brain_bridge_provider_falls_back_to_memory(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class FakeProvider:
        def __init__(self, **kwargs: str) -> None:
            captured.update(kwargs)

    fake_module = type("FakeAiProvider", (), {"OpenAICompatibleProvider": FakeProvider})()
    monkeypatch.setattr(brain_bridge, "ai_provider", fake_module)
    ai_config.set_config(
        {
            "api_key": "sk-memory",
            "base_url": "https://memory.example/v1",
            "model": "gpt-memory",
        }
    )

    brain_bridge._provider({})

    assert captured["api_key"] == "sk-memory"
    assert captured["base_url"] == "https://memory.example/v1"
    assert captured["model"] == "gpt-memory"


def test_brain_bridge_search_config_falls_back_to_memory(monkeypatch) -> None:
    fake_data_tools = type(
        "FakeDataTools",
        (),
        {"SEARCH_PROVIDERS": {"tavily": "Tavily", "duckduckgo_html": "DuckDuckGo"}},
    )()
    monkeypatch.setattr(brain_bridge, "data_tools", fake_data_tools)
    ai_config.set_config(
        {
            "search_provider": "tavily",
            "search_api_key": "tvly-memory",
            "search_api_url": "https://api.tavily.com/search",
            "search_max_results": 7,
        }
    )

    config = brain_bridge._search_config({})

    assert config["provider"] == "tavily"
    assert config["api_key"] == "tvly-memory"
    assert config["api_url"] == "https://api.tavily.com/search"
    assert config["max_results"] == 7


def test_control_run_endpoint_uses_global_config(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(**kwargs: object) -> dict:
        calls.append(kwargs)
        return {"models": {"global": {"runs": {}}}}

    monkeypatch.setattr(benchmark, "run_global_benchmark", fake_run)
    resp = client.post(
        "/api/control/run",
        json={
            "api_key": "sk-x",
            "base_url": "https://example.com/v1",
            "model": "gpt-x",
            "runs": 2,
            "timeout": 30,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert "sk-x" not in json.dumps(body)

    deadline = time.time() + 5
    state: dict = {}
    while time.time() < deadline:
        state = client.get("/api/control/run/status").json()
        if state["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert state["status"] == "done"
    assert len(calls) == 1
    assert calls[0]["api_key"] == "sk-x"
    assert calls[0]["model"] == "gpt-x"


def test_control_run_requires_key_when_not_configured() -> None:
    resp = client.post("/api/control/run", json={})
    assert resp.status_code == 400
    assert "API Key" in resp.json()["detail"]


def test_control_run_accepts_mode_and_updates_progress(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(**kwargs: object) -> dict:
        calls.append(kwargs)
        progress = kwargs.get("on_progress")
        if callable(progress):
            progress(
                {
                    "run": 1,
                    "total_runs": 2,
                    "batch": 3,
                    "total_batches": 15,
                    "mode": "full",
                }
            )
        return {"models": {"global": {"runs": {}}}}

    monkeypatch.setattr(benchmark, "run_global_benchmark", fake_run)
    resp = client.post(
        "/api/control/run",
        json={
            "api_key": "sk-x",
            "base_url": "https://example.com/v1",
            "model": "gpt-x",
            "mode": "full",
            "runs": 2,
            "timeout": 30,
        },
    )
    assert resp.status_code == 200
    deadline = time.time() + 5
    state: dict = {}
    while time.time() < deadline:
        state = client.get("/api/control/run/status").json()
        if state["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert state["status"] == "done"
    assert state["mode"] == "full"
    assert state["progress"] == {
        "run": 1,
        "total_runs": 2,
        "batch": 3,
        "total_batches": 15,
        "mode": "full",
    }
    assert calls[0]["mode"] == "full"


def test_control_run_rejects_invalid_mode() -> None:
    resp = client.post(
        "/api/control/run",
        json={"api_key": "sk-x", "model": "gpt-x", "mode": "weird"},
    )
    assert resp.status_code == 400
    assert "lite" in resp.json()["detail"]


def test_control_run_defaults_to_control_timeout(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(**kwargs: object) -> dict:
        calls.append(kwargs)
        return {"models": {"global": {"runs": {}}}}

    monkeypatch.setattr(benchmark, "run_global_benchmark", fake_run)
    resp = client.post(
        "/api/control/run",
        json={"api_key": "sk-x", "model": "gpt-x"},
    )
    assert resp.status_code == 200
    deadline = time.time() + 5
    state: dict = {}
    while time.time() < deadline:
        state = client.get("/api/control/run/status").json()
        if state["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert state["status"] == "done"
    assert calls[0]["timeout"] == benchmark.CONTROL_TIMEOUT_SECONDS


def test_run_global_benchmark_writes_scored_metrics(tmp_path, monkeypatch) -> None:
    combos = [("cn_latiao", "us"), ("cn_changsha_mifen", "sea")]
    dates = pd.date_range("2024-07-05", periods=104, freq="7D")
    train_frames: list[pd.DataFrame] = []
    holdout_frames: list[pd.DataFrame] = []
    for cat, mkt in combos:
        group = pd.DataFrame(
            {
                "date": dates,
                "category": cat,
                "market": mkt,
                "sales_volume": range(104),
            }
        )
        train_frames.append(group.iloc[:-12])
        holdout_frames.append(group.iloc[-12:])
    train = pd.concat(train_frames, ignore_index=True)
    holdout = pd.concat(holdout_frames, ignore_index=True)

    train_csv = tmp_path / "train.csv"
    holdout_csv = tmp_path / "holdout.csv"
    prompt_md = tmp_path / "prompt.md"
    train_csv.write_text(train.to_csv(index=False), encoding="utf-8")
    holdout_csv.write_text(holdout.to_csv(index=False), encoding="utf-8")
    prompt_md.write_text(
        "请给出 holdout 期间的销量预测表与 Top 5 建议。"
        "数据共 1980 个品类 × 市场组合；对全部 1980 个组合给出预测，"
        "全部 1980 × 12 = 23760 个预测值。",
        encoding="utf-8",
    )

    monkeypatch.setattr(benchmark, "TRAIN_CSV", train_csv)
    monkeypatch.setattr(benchmark, "HOLDOUT_CSV", holdout_csv)
    monkeypatch.setattr(benchmark, "PROMPT_MD", prompt_md)
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", tmp_path / "responses")
    monkeypatch.setattr(benchmark, "OUTPUT_DIR", tmp_path / "out")
    _write_github_signals(tmp_path, monkeypatch, combos)

    holdout_dates = sorted(holdout["date"].dt.strftime("%Y-%m-%d").unique())
    rows = []
    for _, row in holdout.iterrows():
        date_str = row["date"].strftime("%Y-%m-%d")
        rows.append(f"| {row['category']} | {row['market']} | {date_str} | {float(row['sales_volume']) + 1.0} |")
    fake_text = (
        "## 预测表\n"
        "| category | market | date | predicted_sales_volume |\n"
        "|---|---|---|---|\n"
        + "\n".join(rows)
    )

    def fake_call(
        key: str,
        base_url: str,
        model: str,
        content: str,
        temperature: float,
        timeout: int,
    ) -> str:
        assert key == "sk-test"
        assert base_url == "https://example.com/v1"
        assert model == "gpt-x"
        assert holdout_dates
        assert "本批次数据文件仅包含 12 个组合" in content
        assert "共 12 × 12 = 144 行" in content
        assert "对数据文件中的 12 个组合" in content
        assert "全部 12 × 12 = 144 个预测值" in content
        return _complete_response(holdout)

    monkeypatch.setattr(benchmark, "_call_openai_compatible", fake_call)

    result = benchmark.run_global_benchmark(
        "sk-test", "https://example.com/v1", "gpt-x", runs=2, timeout=30
    )

    assert (tmp_path / "responses/global/run1.md").exists()
    assert (tmp_path / "responses/global/run2.md").exists()
    metrics = json.loads(
        (tmp_path / "out/control_metrics.json").read_text(encoding="utf-8")
    )
    assert "global" in metrics["models"]
    assert len(metrics["models"]["global"]["runs"]) == 2
    entry = metrics["models"]["global"]
    assert entry["label"] == "全局 AI（gpt-x）"
    assert entry["api_model_id"] == "gpt-x"
    assert entry["base_url"] == "https://example.com/v1"
    assert entry["source"] == "api"
    assert entry["scope"]["mode"] == "lite"
    assert entry["scope"]["total_cells"] == 24
    assert metrics["scope"]["mode"] == "lite"
    meta = json.loads(
        (tmp_path / "responses/global/run1.meta.json").read_text(encoding="utf-8")
    )
    assert meta["api_model_id"] == "gpt-x"
    assert "sk-test" not in json.dumps(meta)
    assert result["models"]["global"]["runs"]
    assert "global" not in benchmark.MODEL_REGISTRY


def test_run_global_benchmark_full_mode_batches_and_merges(tmp_path, monkeypatch) -> None:
    combos = [("cn_latiao", "us"), ("cn_changsha_mifen", "sea")]
    holdout, _ = _write_control_files(tmp_path, combos)
    monkeypatch.setattr(benchmark, "TRAIN_CSV", tmp_path / "train.csv")
    monkeypatch.setattr(benchmark, "HOLDOUT_CSV", tmp_path / "holdout.csv")
    monkeypatch.setattr(benchmark, "PROMPT_MD", tmp_path / "prompt.md")
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", tmp_path / "responses")
    monkeypatch.setattr(benchmark, "OUTPUT_DIR", tmp_path / "out")
    _write_github_signals(tmp_path, monkeypatch, combos)
    calls: list[str] = []

    def fake_call(
        key: str,
        base_url: str,
        model: str,
        content: str,
        temperature: float,
        timeout: int,
    ) -> str:
        calls.append(content)
        return _complete_response(holdout)

    monkeypatch.setattr(benchmark, "_call_openai_compatible", fake_call)
    result = benchmark.run_global_benchmark(
        "sk-test",
        "https://example.com/v1",
        "gpt-x",
        runs=1,
        timeout=30,
        mode="full",
    )
    responses = tmp_path / "responses" / "global"
    assert len(calls) == 15
    assert (responses / "run1_b01.md").exists()
    assert (responses / "run1_b15.md").exists()
    combined = (responses / "run1.md").read_text(encoding="utf-8")
    assert "批次 1/15" in combined
    assert "批次 15/15" in combined
    entry = result["models"]["global"]
    assert entry["scope"]["mode"] == "full"
    assert result["scope"]["mode"] == "full"
    assert entry["runs"]["1"]["coverage"] == 1.0


def test_run_global_benchmark_retries_incomplete_response(tmp_path, monkeypatch) -> None:
    combos = [("cn_latiao", "us"), ("cn_changsha_mifen", "sea")]
    holdout, _ = _write_control_files(tmp_path, combos)
    monkeypatch.setattr(benchmark, "TRAIN_CSV", tmp_path / "train.csv")
    monkeypatch.setattr(benchmark, "HOLDOUT_CSV", tmp_path / "holdout.csv")
    monkeypatch.setattr(benchmark, "PROMPT_MD", tmp_path / "prompt.md")
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", tmp_path / "responses")
    monkeypatch.setattr(benchmark, "OUTPUT_DIR", tmp_path / "out")
    _write_github_signals(tmp_path, monkeypatch, combos)
    calls: list[str] = []

    def fake_call(
        key: str,
        base_url: str,
        model: str,
        content: str,
        temperature: float,
        timeout: int,
    ) -> str:
        calls.append(content)
        if len(calls) == 1:
            return "## 核心洞察\n只有一段，没有预测、Top5 和方法。"
        return _complete_response(holdout)

    monkeypatch.setattr(benchmark, "_call_openai_compatible", fake_call)
    result = benchmark.run_global_benchmark(
        "sk-test", "https://example.com/v1", "gpt-x", runs=1, timeout=30
    )
    meta = json.loads(
        (tmp_path / "responses/global/run1.meta.json").read_text(encoding="utf-8")
    )
    assert len(calls) == 2
    assert meta["attempts"] == 2
    assert meta["completeness"]["complete"] is True
    assert meta["github_signals_file"]
    assert result["models"]["global"]["runs"]["1"]["complete"] is True


def test_run_global_benchmark_persistent_incomplete_is_failed(
    tmp_path, monkeypatch
) -> None:
    combos = [("cn_latiao", "us"), ("cn_changsha_mifen", "sea")]
    holdout, _ = _write_control_files(tmp_path, combos)
    monkeypatch.setattr(benchmark, "TRAIN_CSV", tmp_path / "train.csv")
    monkeypatch.setattr(benchmark, "HOLDOUT_CSV", tmp_path / "holdout.csv")
    monkeypatch.setattr(benchmark, "PROMPT_MD", tmp_path / "prompt.md")
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", tmp_path / "responses")
    monkeypatch.setattr(benchmark, "OUTPUT_DIR", tmp_path / "out")
    _write_github_signals(tmp_path, monkeypatch, combos)

    def fake_call(
        key: str,
        base_url: str,
        model: str,
        content: str,
        temperature: float,
        timeout: int,
    ) -> str:
        return "## 核心洞察\n只有一段，始终缺失其它三段。"

    monkeypatch.setattr(benchmark, "_call_openai_compatible", fake_call)
    result = benchmark.run_global_benchmark(
        "sk-test", "https://example.com/v1", "gpt-x", runs=1, timeout=30
    )
    meta = json.loads(
        (tmp_path / "responses/global/run1.meta.json").read_text(encoding="utf-8")
    )
    assert meta["attempts"] == 3
    assert meta["completeness"]["complete"] is False
    run_result = result["models"]["global"]["runs"]["1"]
    assert run_result["complete"] is False
    summary = (tmp_path / "out/score_summary.md").read_text(encoding="utf-8")
    assert "失败（缺" in summary


def test_call_openai_compatible_surfaces_provider_error(monkeypatch) -> None:
    class _FakeResponse:
        status_code = 400
        text = '{"error":{"message":"maximum context length exceeded"}}'

        def raise_for_status(self) -> None:
            raise requests.HTTPError("400 Client Error")

    monkeypatch.setattr(
        benchmark.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(),
    )
    with pytest.raises(RuntimeError, match="maximum context length"):
        benchmark._call_openai_compatible(
            "sk-test",
            "https://example.com/v1",
            "gpt-x",
            "content",
            0.2,
            30,
        )


def test_call_openai_compatible_retries_transient_timeout(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class _FakeResponse:
        status_code = 200
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(*args: object, **kwargs: object) -> _FakeResponse:
        calls.append(kwargs)
        if len(calls) < 3:
            raise requests.Timeout("Read timed out.")
        return _FakeResponse()

    monkeypatch.setattr(benchmark.requests, "post", fake_post)
    monkeypatch.setattr(benchmark.time, "sleep", lambda _seconds: None)
    result = benchmark._call_openai_compatible(
        "sk-test",
        "https://example.com/v1",
        "gpt-x",
        "content",
        0.2,
        30,
    )
    assert result == "ok"
    assert len(calls) == 3


def test_control_web_setup_endpoint(monkeypatch) -> None:
    def fake_setup() -> dict:
        return {
            "deepseek_url": "https://chat.deepseek.com",
            "prompt_text": "统一提示词",
            "train_rows": 2,
            "runs": {
                "1": {"saved": False, "meta": {}},
                "2": {"saved": False, "meta": {}},
            },
        }

    monkeypatch.setattr(benchmark, "web_setup", fake_setup)
    resp = client.get("/api/control/web/setup")
    assert resp.status_code == 200
    body = resp.json()
    assert body["deepseek_url"] == "https://chat.deepseek.com"
    assert body["prompt_text"] == "统一提示词"


def test_control_web_save_endpoint_without_key(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_save(**kwargs: object) -> dict:
        calls.append(kwargs)
        return {
            "status": "ok",
            "model": "deepseek",
            "run": kwargs["run"],
            "file": "data/control/responses/deepseek/run1.md",
            "metrics": {"models": {}},
        }

    monkeypatch.setattr(benchmark, "save_web_response", fake_save)
    resp = client.post(
        "/api/control/web/save",
        json={
            "run": 1,
            "text": "| cn_latiao | us | 2026-01-01 | 10.0 |",
            "model_version": "DeepSeek-V3",
            "code_execution": True,
            "note": "ok",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert calls[0]["run"] == 1
    assert calls[0]["text"] == "| cn_latiao | us | 2026-01-01 | 10.0 |"
    assert calls[0]["model_version"] == "DeepSeek-V3"
    assert calls[0]["code_execution"] is True


def test_control_web_save_requires_text() -> None:
    resp = client.post("/api/control/web/save", json={"run": 1, "text": "   "})
    assert resp.status_code == 400
    assert "空" in resp.json()["detail"]


def test_control_web_save_rejects_bad_run() -> None:
    resp = client.post("/api/control/web/save", json={"run": 3, "text": "ok"})
    assert resp.status_code == 400


def test_control_train_data_download(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "train_data.csv"
    csv_path.write_text("date\n2026-01-01\n", encoding="utf-8")
    monkeypatch.setattr(benchmark, "TRAIN_CSV", csv_path)
    resp = client.get("/api/control/train-data")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "train_data.csv" in resp.headers.get("content-disposition", "")
