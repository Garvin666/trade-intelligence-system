"""顶级 AI 对照组：数据切分、回复解析与评分测试。"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.control import benchmark
from src.control.benchmark import (
    MODEL_REGISTRY,
    check_number_grounded,
    extract_forecast_table,
    extract_numeric_claims,
    parse_recommendations,
    prepare_control_split,
    score_response,
    section_completeness,
    _user_content,
)

HOLDOUT_DATES = ["2026-04-10", "2026-04-17"]


def _fake_clean(weeks: int = 104, combos: tuple[tuple[str, str], ...] = (("cn_latiao", "us"), ("cn_changsha_mifen", "sea"))) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for cat, mkt in combos:
        dates = pd.date_range("2024-07-05", periods=weeks, freq="7D")
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "category": cat,
                    "market": mkt,
                    "sales_volume": np.arange(weeks, dtype=float),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _holdout_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"category": "cn_latiao", "market": "us", "date": "2026-04-10", "sales_volume": 100.0},
            {"category": "cn_latiao", "market": "us", "date": "2026-04-17", "sales_volume": 110.0},
            {"category": "cn_changsha_mifen", "market": "sea", "date": "2026-04-10", "sales_volume": 80.0},
            {"category": "cn_changsha_mifen", "market": "sea", "date": "2026-04-17", "sales_volume": 90.0},
        ]
    )


def test_prepare_control_split_boundaries() -> None:
    train, holdout = prepare_control_split(_fake_clean())
    assert len(train) == 2 * 92
    assert len(holdout) == 2 * 12
    assert train["date"].max().date().isoformat() == "2026-04-03"
    assert holdout["date"].min().date().isoformat() == "2026-04-10"
    assert holdout["date"].max().date().isoformat() == "2026-06-26"
    assert train.groupby(["category", "market"]).size().nunique() == 1
    assert holdout.groupby(["category", "market"]).size().nunique() == 1


def test_control_registry_only_deepseek() -> None:
    assert set(MODEL_REGISTRY) == {"deepseek"}


def test_prepare_control_split_invalid_short_series() -> None:
    with pytest.raises(ValueError):
        prepare_control_split(_fake_clean(weeks=10))


def test_parse_markdown_table() -> None:
    text = (
        "| category | market | date | predicted_sales_volume |\n"
        "|---|---|---|---|\n"
        "| cn_latiao | us | 2026-04-10 | 105.0 |\n"
        "| cn_changsha_mifen | sea | 2026-04-17 | 90.5 |"
    )
    rows = extract_forecast_table(text, HOLDOUT_DATES)
    assert rows == [
        {"category": "cn_latiao", "market": "us", "date": "2026-04-10", "value": 105.0},
        {"category": "cn_changsha_mifen", "market": "sea", "date": "2026-04-17", "value": 90.5},
    ]


def test_parse_csv_block_with_week_index() -> None:
    text = (
        "```csv\n"
        "category,market,date,sales_volume\n"
        "cn_latiao,us,2026-04-10,105.0\n"
        "cn_changsha_mifen,sea,第1周,90.5\n"
        "```"
    )
    rows = extract_forecast_table(text, HOLDOUT_DATES)
    assert rows == [
        {"category": "cn_latiao", "market": "us", "date": "2026-04-10", "value": 105.0},
        {"category": "cn_changsha_mifen", "market": "sea", "date": "2026-04-10", "value": 90.5},
    ]


def test_parse_plain_text_fallback() -> None:
    text = "cn_latiao us 2026-04-10 105.0\ncn_changsha_mifen sea 2026-04-17 90.5"
    rows = extract_forecast_table(text, HOLDOUT_DATES)
    assert len(rows) == 2
    assert rows[0]["category"] == "cn_latiao"
    assert rows[0]["value"] == 105.0


def test_parse_recommendations_chinese() -> None:
    text = (
        "## Top 5 选品建议\n"
        "1. 辣条 × 美国：搜索热度高。\n"
        "2. 长沙米粉 × 东南亚：评论增长活跃。\n"
        "3. 麻辣牛肉干 × 欧洲：竞争度较低。\n"
        "4. 西湖龙井 × 美国：季节性上行。\n"
        "5. 老干妈辣椒酱 × 东南亚：预测增长 25.7%。"
    )
    assert parse_recommendations(text) == [
        ("cn_latiao", "us"),
        ("cn_changsha_mifen", "sea"),
        ("cn_beef_jerky", "eu"),
        ("cn_longjing", "us"),
        ("cn_laoganma", "sea"),
    ]


def _complete_control_text() -> str:
    return (
        "## 核心洞察\n美国辣条搜索热度 95.7，建议备货 300 件。\n\n"
        "## 未来 12 周销量预测\n"
        "| category | market | date | predicted_sales_volume |\n"
        "|---|---|---|---|\n"
        "| cn_latiao | us | 2026-04-10 | 105.0 |\n"
        "| cn_latiao | us | 2026-04-17 | 112.0 |\n\n"
        "## Top 5 选品建议\n"
        "1. 辣条 × 美国：需求稳定。\n"
        "2. 长沙米粉 × 东南亚：评论增长活跃。\n"
        "3. 麻辣牛肉干 × 欧洲：竞争度较低。\n"
        "4. 西湖龙井 × 美国：季节性上行。\n"
        "5. 老干妈辣椒酱 × 东南亚：预测增长 25.7%。\n\n"
        "## 方法与不确定性\n使用线性外推与季节因子，假设趋势延续，"
        "置信区间 80%，风险为库存不足。\n"
    )


def test_section_completeness_accepts_full_response() -> None:
    result = section_completeness(_complete_control_text(), HOLDOUT_DATES)
    assert result["complete"] is True
    assert result["missing"] == []


@pytest.mark.parametrize(
    "remove_marker",
    ["核心洞察", "未来 12 周销量预测", "Top 5 选品建议", "方法与不确定性"],
)
def test_section_completeness_rejects_missing_section(remove_marker: str) -> None:
    text = _complete_control_text().replace(remove_marker, "缺失标题")
    result = section_completeness(text, HOLDOUT_DATES)
    assert result["complete"] is False
    assert result["missing"]


def test_grounding_check() -> None:
    values = np.array([95.7, 3.33, 50.0])
    assert check_number_grounded(95.7, values)
    assert check_number_grounded(3.33, values)
    assert not check_number_grounded(999.9, values)


def test_extract_numeric_claims_excludes_tables_and_dates() -> None:
    text = (
        "搜索热度 95.7，异常值 999.9，备货 300 件。\n"
        "| category | market | date | value |\n"
        "|---|---|---|---|\n"
        "| cn_latiao | us | 2026-04-10 | 105.0 |"
    )
    claims = extract_numeric_claims(text)
    values = {c["value"] for c in claims}
    assert 95.7 in values
    assert 999.9 in values
    assert 300 in values
    assert 105.0 not in values
    assert 2026 not in values


def test_score_response_metrics() -> None:
    holdout = _holdout_df()
    text = (
        "| category | market | date | predicted_sales_volume |\n"
        "|---|---|---|---|\n"
        "| cn_latiao | us | 2026-04-10 | 105.0 |\n"
        "| cn_latiao | us | 2026-04-17 | 112.0 |\n"
        "| cn_changsha_mifen | sea | 2026-04-10 | 90.0 |\n"
        "| cn_changsha_mifen | sea | 2026-04-17 | 95.0 |"
    )
    result = score_response(text, holdout, holdout, system_top5=[])
    assert result["forecast_cells"] == 4
    assert result["coverage"] == 1.0
    assert result["invalid_cells"] == 0
    assert result["mape_macro"] == pytest.approx((3.4090909 + 9.0277778) / 2, abs=1e-3)
    assert result["mae_macro"] == pytest.approx((3.5 + 7.5) / 2, abs=1e-3)
    assert result["mape_pooled"] == pytest.approx((5 + 1.8181818 + 12.5 + 5.5555556) / 4, abs=1e-3)


def test_score_response_completeness_partial() -> None:
    holdout = _holdout_df()
    text = (
        "| category | market | date | predicted_sales_volume |\n"
        "|---|---|---|---|\n"
        "| cn_latiao | us | 2026-04-10 | 105.0 |\n"
        "| cn_latiao | us | 2026-04-17 | 112.0 |"
    )
    result = score_response(text, holdout, holdout, system_top5=[])
    assert result["forecast_cells"] == 2
    assert result["coverage"] == 0.5
    assert result["mape_macro"] == pytest.approx(3.4090909, abs=1e-3)


def test_score_response_actionability_and_grounding() -> None:
    holdout = _holdout_df()
    text = (
        "## 核心洞察\n美国辣条搜索热度 95.7，异常值 999.9。\n"
        "## Top 5 选品建议\n辣条 × 美国：备货 300 件。\n"
        "## 假设与局限\n假设延续，置信区间 80%。"
    )
    result = score_response(text, holdout, holdout, system_top5=[("cn_latiao", "us")])
    assert result["has_inventory"] is True
    assert result["has_uncertainty"] is True
    assert result["has_assumptions"] is True
    assert result["recommendations"] == [("cn_latiao", "us")]
    assert result["recommendation_hits"] == 1
    assert result["recommendation_jaccard"] == 1.0
    assert result["grounding"]["claims_ungrounded"] >= 1


def test_score_response_top5_union_scope() -> None:
    holdout = _holdout_df()
    text = (
        "## Top 5 选品建议\n"
        "1. 辣条 × 美国：需求稳定。\n"
        "2. 长沙米粉 × 东南亚：评论增长活跃。\n"
        "3. 麻辣牛肉干 × 欧洲：竞争度较低。\n"
        "4. 西湖龙井 × 美国：季节性上行。\n"
        "5. 老干妈辣椒酱 × 东南亚：预测增长。"
    )
    result = score_response(
        text,
        holdout,
        holdout,
        system_top5=[("cn_beef_jerky", "eu"), ("intl_matcha", "uk"), ("cn_mooncake", "de"), ("intl_almonds", "vn"), ("cn_xinjiang_dates", "fr")],
        actual_top5=[("cn_latiao", "us"), ("cn_changsha_mifen", "sea"), ("cn_longjing", "us"), ("cn_laoganma", "sea"), ("cn_self_heating_hotpot", "mx")],
    )
    assert result["recommendation_hits_system"] == 1
    assert result["recommendation_hits_actual"] == 4
    assert result["recommendation_hits"] == 5
    assert result["recommendation_matches_system"] == [("cn_beef_jerky", "eu")]
    assert ("cn_latiao", "us") in result["recommendation_matches_actual"]


def test_context_grounding_uses_combo() -> None:
    holdout = _holdout_df()
    train = pd.DataFrame(
        [
            {"category": "cn_latiao", "market": "us", "sales_volume": 95.7},
            {"category": "cn_changsha_mifen", "market": "sea", "sales_volume": 999.9},
        ]
    )
    text = "## 核心洞察\n辣条 美国 搜索热度 999.9。\n"
    result = score_response(text, holdout, train, system_top5=[])
    assert result["grounding"]["claims_ungrounded"] >= 1
    candidate = next(
        c for c in result["grounding"]["candidates"] if c["value"] == 999.9
    )
    assert candidate["grounded"] is False
    assert candidate["scope_combo"] == ["cn_latiao", "us"]


def test_user_content_replaces_static_dates(tmp_path, monkeypatch) -> None:
    prompt_md = tmp_path / "prompt.md"
    prompt_md.write_text(
        "预测 2026-05-28 至 2026-08-13 每周五的 sales_volume。",
        encoding="utf-8",
    )
    train_csv = tmp_path / "train.csv"
    train_csv.write_text(
        "date,category,market,sales_volume\n"
        "2026-05-22,cn_latiao,us,100\n",
        encoding="utf-8",
    )
    holdout_csv = tmp_path / "holdout.csv"
    holdout_csv.write_text(
        "date,category,market,sales_volume\n"
        "2026-05-29,cn_latiao,us,105\n"
        "2026-06-05,cn_latiao,us,110\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(benchmark, "PROMPT_MD", prompt_md)
    monkeypatch.setattr(benchmark, "TRAIN_CSV", train_csv)
    monkeypatch.setattr(benchmark, "HOLDOUT_CSV", holdout_csv)
    monkeypatch.setattr(benchmark, "GITHUB_SIGNALS_JSON", tmp_path / "missing.json")
    monkeypatch.setattr(benchmark, "_github_signal_section", lambda combos: "")
    content = _user_content([("cn_latiao", "us")])
    assert "2026-05-29 至 2026-06-05" in content
    assert "2026-05-28 至 2026-08-13" not in content


def test_save_web_response_writes_files_and_scores(tmp_path, monkeypatch) -> None:
    prompt_md = tmp_path / "prompt.md"
    train_csv = tmp_path / "train.csv"
    prompt_md.write_text("# 提示词", encoding="utf-8")
    train_csv.write_text("date\n2026-01-01\n", encoding="utf-8")
    responses = tmp_path / "responses"
    monkeypatch.setattr(benchmark, "PROMPT_MD", prompt_md)
    monkeypatch.setattr(benchmark, "TRAIN_CSV", train_csv)
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", responses)
    calls: list[list[str]] = []

    def fake_score(models: list[str] | None) -> dict:
        calls.append(models or [])
        return {"models": {"deepseek": {"runs": {}}}}

    monkeypatch.setattr(benchmark, "score_all", fake_score)
    text = "| cn_latiao | us | 2026-01-01 | 10.0 |"
    result = benchmark.save_web_response(
        run=1,
        text=text,
        model_version="DeepSeek-V3",
        code_execution=True,
        note="截图",
    )
    md_path = responses / "deepseek" / "run1.md"
    meta_path = responses / "deepseek" / "run1.meta.json"
    assert md_path.exists()
    assert md_path.read_text(encoding="utf-8") == text
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["source"] == "web"
    assert meta["api_model_id"] == "DeepSeek-V3"
    assert meta["run"] == 1
    assert meta["code_execution"] is True
    assert meta["note"] == "截图"
    assert calls == [["deepseek"]]
    assert result["status"] == "ok"


def test_save_web_response_rejects_invalid(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", tmp_path / "responses")
    monkeypatch.setattr(benchmark, "PROMPT_MD", tmp_path / "prompt.md")
    monkeypatch.setattr(benchmark, "TRAIN_CSV", tmp_path / "train.csv")
    with pytest.raises(ValueError, match="run"):
        benchmark.save_web_response(run=3, text="ok")
    with pytest.raises(ValueError, match="空"):
        benchmark.save_web_response(run=1, text="   ")


def test_web_setup_reports_runs_and_files(tmp_path, monkeypatch) -> None:
    prompt_md = tmp_path / "prompt.md"
    train_csv = tmp_path / "train.csv"
    prompt_md.write_text("# 提示词", encoding="utf-8")
    train_csv.write_text("date\n2026-01-01\n2026-01-08\n", encoding="utf-8")
    responses = tmp_path / "responses"
    monkeypatch.setattr(benchmark, "PROMPT_MD", prompt_md)
    monkeypatch.setattr(benchmark, "TRAIN_CSV", train_csv)
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", responses)

    info = benchmark.web_setup()
    assert info["deepseek_url"] == "https://chat.deepseek.com"
    assert info["prompt_text"] == "# 提示词"
    assert info["train_rows"] == 2
    assert info["runs"]["1"]["saved"] is False

    (responses / "deepseek").mkdir(parents=True)
    (responses / "deepseek" / "run1.md").write_text("ok", encoding="utf-8")
    (responses / "deepseek" / "run1.meta.json").write_text(
        json.dumps({"source": "web"}), encoding="utf-8"
    )
    info = benchmark.web_setup()
    assert info["runs"]["1"]["saved"] is True
    assert info["runs"]["1"]["meta"]["source"] == "web"


def test_web_setup_requires_train_file(tmp_path, monkeypatch) -> None:
    prompt_md = tmp_path / "prompt.md"
    prompt_md.write_text("# 提示词", encoding="utf-8")
    monkeypatch.setattr(benchmark, "PROMPT_MD", prompt_md)
    monkeypatch.setattr(benchmark, "TRAIN_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", tmp_path / "responses")
    with pytest.raises(FileNotFoundError, match="prepare"):
        benchmark.web_setup()


def test_score_all_default_includes_global(tmp_path, monkeypatch) -> None:
    train = pd.DataFrame(
        [
            {"category": "cn_latiao", "market": "us", "date": "2026-04-03", "sales_volume": 90.0},
            {"category": "cn_latiao", "market": "us", "date": "2026-04-10", "sales_volume": 100.0},
        ]
    )
    holdout = pd.DataFrame(
        [
            {"category": "cn_latiao", "market": "us", "date": "2026-04-10", "sales_volume": 100.0},
            {"category": "cn_latiao", "market": "us", "date": "2026-04-17", "sales_volume": 110.0},
        ]
    )
    train_csv = tmp_path / "train.csv"
    holdout_csv = tmp_path / "holdout.csv"
    train_csv.write_text(train.to_csv(index=False), encoding="utf-8")
    holdout_csv.write_text(holdout.to_csv(index=False), encoding="utf-8")
    responses = tmp_path / "responses" / "global"
    responses.mkdir(parents=True)
    out_dir = tmp_path / "out"
    monkeypatch.setattr(benchmark, "TRAIN_CSV", train_csv)
    monkeypatch.setattr(benchmark, "HOLDOUT_CSV", holdout_csv)
    monkeypatch.setattr(benchmark, "RECOMMEND_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", tmp_path / "responses")
    monkeypatch.setattr(benchmark, "OUTPUT_DIR", out_dir)
    text = (
        "## 预测表\n"
        "| category | market | date | predicted_sales_volume |\n"
        "|---|---|---|---|\n"
        "| cn_latiao | us | 2026-04-10 | 101.0 |\n"
        "| cn_latiao | us | 2026-04-17 | 112.0 |"
    )
    (responses / "run1.md").write_text(text, encoding="utf-8")
    (responses / "run1.meta.json").write_text(
        json.dumps(
            {
                "model": "global",
                "label": "global",
                "api_model_id": "gpt-x",
                "source": "api",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = benchmark.score_all()
    assert "global" in payload["models"]
    assert payload["models"]["global"]["runs"]["1"]["coverage"] == 1.0


def test_score_all_reads_meta_labels(tmp_path, monkeypatch) -> None:
    train = pd.DataFrame(
        [
            {"category": "cn_latiao", "market": "us", "date": "2026-04-03", "sales_volume": 90.0},
            {"category": "cn_latiao", "market": "us", "date": "2026-04-10", "sales_volume": 100.0},
        ]
    )
    holdout = pd.DataFrame(
        [
            {"category": "cn_latiao", "market": "us", "date": "2026-04-10", "sales_volume": 100.0},
            {"category": "cn_latiao", "market": "us", "date": "2026-04-17", "sales_volume": 110.0},
        ]
    )
    train_csv = tmp_path / "train.csv"
    holdout_csv = tmp_path / "holdout.csv"
    train_csv.write_text(train.to_csv(index=False), encoding="utf-8")
    holdout_csv.write_text(holdout.to_csv(index=False), encoding="utf-8")
    responses = tmp_path / "responses" / "global"
    responses.mkdir(parents=True)
    out_dir = tmp_path / "out"
    monkeypatch.setattr(benchmark, "TRAIN_CSV", train_csv)
    monkeypatch.setattr(benchmark, "HOLDOUT_CSV", holdout_csv)
    monkeypatch.setattr(benchmark, "RECOMMEND_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", tmp_path / "responses")
    monkeypatch.setattr(benchmark, "OUTPUT_DIR", out_dir)
    text = (
        "## 预测表\n"
        "| category | market | date | predicted_sales_volume |\n"
        "|---|---|---|---|\n"
        "| cn_latiao | us | 2026-04-10 | 101.0 |\n"
        "| cn_latiao | us | 2026-04-17 | 112.0 |"
    )
    for run in (1, 2):
        (responses / f"run{run}.md").write_text(text, encoding="utf-8")
    meta = {
        "model": "global",
        "label": "全局 AI（gpt-x）",
        "api_model_id": "gpt-x",
        "base_url": "https://example.com/v1",
        "source": "api",
        "run": 1,
    }
    (responses / "run1.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    payload = benchmark.score_all(["global"])
    entry = payload["models"]["global"]
    assert entry["label"] == "全局 AI（gpt-x）"
    assert entry["api_model_id"] == "gpt-x"
    assert entry["base_url"] == "https://example.com/v1"
    assert entry["source"] == "api"
    summary = (out_dir / "score_summary.md").read_text(encoding="utf-8")
    assert "全局 AI（gpt-x）" in summary
