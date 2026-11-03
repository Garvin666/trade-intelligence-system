"""对照组显著性改造：BH 校正、配对检验加固与显著性报告测试。

覆盖 stats.py 的 bh_adjust / paired_significance 加固，以及 benchmark.py 的
_aligned_mae_pairs / compute_significance_tests / significance_report.md / lite 文案修复。
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from src.analysis.stats import bh_adjust, paired_significance
from src.control import benchmark
from src.control.benchmark import _aligned_mae_pairs

HOLDOUT_DATES = ["2026-04-10", "2026-04-17"]
COMBOS = [("cn_latiao", "us"), ("cn_changsha_mifen", "sea"), ("cn_guilin_mifen", "kr"), ("cn_laoganma", "fr")]
_ACTUAL_SALES = {
    ("cn_latiao", "us"): (100.0, 110.0),
    ("cn_changsha_mifen", "sea"): (80.0, 90.0),
    ("cn_guilin_mifen", "kr"): (60.0, 70.0),
    ("cn_laoganma", "fr"): (40.0, 50.0),
}


def _holdout_frame() -> pd.DataFrame:
    rows: list[dict] = []
    for cat, mkt in COMBOS:
        for date, value in zip(HOLDOUT_DATES, _ACTUAL_SALES[(cat, mkt)]):
            rows.append(
                {"category": cat, "market": mkt, "date": date, "sales_volume": value}
            )
    return pd.DataFrame(rows)


def _prediction_text(offset: float) -> str:
    """含完整四段的回复文本：预测值 = 真实值 + offset，故每组合 MAE = |offset|。"""
    rows = [
        "| category | market | date | predicted_sales_volume |",
        "|---|---|---|---|",
    ]
    for (cat, mkt), values in _ACTUAL_SALES.items():
        for date, value in zip(HOLDOUT_DATES, values):
            rows.append(f"| {cat} | {mkt} | {date} | {value + offset} |")
    table = "\n".join(rows)
    return (
        "## 核心洞察\n需求稳定，建议备货 300 件。\n\n"
        "## 未来 12 周销量预测\n"
        f"{table}\n\n"
        "## Top 5 选品建议\n"
        "1. 辣条 × 美国：需求稳定。\n"
        "2. 长沙米粉 × 东南亚：评论活跃。\n"
        "3. 桂林米粉 × 韩国：季节上行。\n"
        "4. 老干妈辣椒酱 × 法国：增长较快。\n"
        "5. 麻辣牛肉干 × 欧洲：竞争较低。\n\n"
        "## 方法与不确定性\n"
        "使用线性外推，置信区间 80%，风险为库存不足。\n"
    )


# ---------- A. stats.py：bh_adjust ----------


def test_bh_adjust_known_example() -> None:
    p_values = [0.01, 0.02, 0.03, 0.05]
    # n=4：0.01*4/1=0.04, 0.02*4/2=0.04, 0.03*4/3=0.04, 0.05*4/4=0.05
    assert bh_adjust(p_values) == [0.04, 0.04, 0.04, 0.05]


def test_bh_adjust_preserves_input_order_and_clips() -> None:
    q = bh_adjust([0.05, 0.01, 0.03, 0.02])
    assert q == [0.05, 0.04, 0.04, 0.04]
    # p=0 保持 0；空输入返回空列表；保序：大 p 不会因小 p 的 BH 值被压低
    assert bh_adjust([0.0, 0.01, 0.05]) == pytest.approx([0.0, 0.015, 0.05])
    assert bh_adjust([]) == []
    assert bh_adjust(np.array([0.3, 0.7])) == [0.6, 0.7]  # 0.3*2/1=0.6


def test_bh_adjust_keeps_nan() -> None:
    q = bh_adjust([0.01, math.nan, 0.05])
    assert q[0] == pytest.approx(0.02)
    assert math.isnan(q[1])
    assert q[2] == pytest.approx(0.05)


# ---------- A. stats.py：paired_significance 加固 ----------


def test_paired_significance_pratt_keeps_zero_diffs() -> None:
    a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    b = [1.0, 2.0, 4.0, 4.0, 6.0, 6.0]  # 差值 [0,0,-1,0,-1,0]
    sig = paired_significance(a, b)
    assert sig is not None
    assert sig["method"] == "wilcoxon"
    assert sig["zero_method"] == "pratt"
    assert sig["n_zero_diffs"] == 4
    assert sig["n"] == 6  # 保留零差对，样本量不虚降
    assert sig["degenerate"] is False


def test_paired_significance_all_zero_degenerate() -> None:
    a = b = [1.0, 2.0, 3.0, 4.0, 5.0]
    sig = paired_significance(a, b)
    assert sig is not None
    assert sig["p_value"] == 1.0
    assert sig["degenerate"] is True
    assert sig["significant"] is False
    assert sig["n_zero_diffs"] == 5


def test_paired_significance_constant_diff_ttest_degenerate() -> None:
    a = np.arange(40, dtype=float)
    b = a + 5.0  # n>=30 → ttest_rel，零方差退化
    sig = paired_significance(a, b)
    assert sig is not None
    assert sig["method"] == "ttest_rel"
    assert sig["degenerate"] is True
    assert sig["p_value"] == 1.0
    assert sig["effect_size"] == 0.0


def test_paired_significance_detects_improvement() -> None:
    system_mae = [10, 12, 11, 13, 14, 12, 11, 10, 13, 12, 14, 15]
    ai_mae = [5, 6, 5, 7, 8, 6, 5, 4, 7, 6, 8, 9]
    sig = paired_significance(system_mae, ai_mae)
    assert sig is not None
    assert sig["significant"] is True
    assert sig["p_value"] < 0.05
    assert sig["effect_size"] > 0
    assert set(sig) >= {"n", "n_zero_diffs", "zero_method", "degenerate"}


# ---------- B. benchmark.py：配对对齐与全族显著性 ----------


def test_aligned_mae_pairs_inner_join() -> None:
    system_mae = pd.Series(
        {("cn_latiao", "us"): 5.0, ("cn_changsha_mifen", "sea"): 6.0, ("cn_guilin_mifen", "kr"): 7.0}
    )
    ai_mae = pd.Series(
        {("cn_latiao", "us"): 1.0, ("cn_changsha_mifen", "sea"): 2.0, ("cn_laoganma", "fr"): 3.0}
    )
    common, ai_common = _aligned_mae_pairs(system_mae, ai_mae)
    assert list(common) == [5.0, 6.0]
    assert list(ai_common) == [1.0, 2.0]


def test_aligned_mae_pairs_drops_nan() -> None:
    system_mae = pd.Series(
        {("cn_latiao", "us"): 5.0, ("cn_changsha_mifen", "sea"): float("nan"), ("cn_guilin_mifen", "kr"): 7.0}
    )
    ai_mae = pd.Series(
        {("cn_latiao", "us"): 1.0, ("cn_changsha_mifen", "sea"): 2.0, ("cn_guilin_mifen", "kr"): 3.0}
    )
    common, ai_common = _aligned_mae_pairs(system_mae, ai_mae)
    assert list(common) == [5.0, 7.0]
    assert list(ai_common) == [1.0, 3.0]


def _significance_payload() -> dict:
    return {
        "models": {
            "m1": {
                "label": "模型一",
                "runs": {
                    "1": {"complete": True, "mae_macro": 1.0},
                    "2": {"complete": True, "mae_macro": 0.5},
                },
            },
            "m2": {
                "label": "模型二",
                "runs": {
                    "1": {"complete": True, "mae_macro": 2.0},
                    "2": {"complete": True, "mae_macro": 3.0},
                },
            },
        }
    }


def _setup_control_files(tmp_path, monkeypatch) -> None:
    holdout_csv = tmp_path / "holdout.csv"
    holdout_csv.write_text(_holdout_frame().to_csv(index=False), encoding="utf-8")
    responses = tmp_path / "responses"
    offsets = {"m1": {"1": 1.0, "2": 0.5}, "m2": {"1": 2.0, "2": 3.0}}
    for model, runs in offsets.items():
        for run, offset in runs.items():
            (responses / model).mkdir(parents=True, exist_ok=True)
            (responses / model / f"run{run}.md").write_text(
                _prediction_text(offset), encoding="utf-8"
            )
    monkeypatch.setattr(benchmark, "HOLDOUT_CSV", holdout_csv)
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", responses)
    monkeypatch.setattr(
        benchmark,
        "_system_mae_by_combo",
        lambda: pd.Series({combo: 10.0 for combo in COMBOS}),
    )


def test_compute_significance_tests_groups_and_bh(tmp_path, monkeypatch) -> None:
    _setup_control_files(tmp_path, monkeypatch)
    report = benchmark.compute_significance_tests(_significance_payload())
    assert report["adjustment"] == "benjamini_hochberg"
    assert report["n_tests"] == 5  # A 组 4 个（2 模型 × 2 run）+ B 组 1 个
    tests = report["tests"]
    group_a = [t for t in tests if t["group"] == "A"]
    group_b = [t for t in tests if t["group"] == "B"]
    assert len(group_a) == 4
    assert len(group_b) == 1
    b = group_b[0]
    # 代表 run 规则：各取宏 MAE 最低的 run
    assert b["left"] == "模型一" and b["run_left"] == 2
    assert b["right"] == "模型二" and b["run_right"] == 1
    for t in tests:
        assert "q_value" in t
        assert t["significant"] == (t["q_value"] < report["alpha"])
        assert t["n"] == 4
        assert t["degenerate"] is False


def test_score_all_writes_significance_report(tmp_path, monkeypatch) -> None:
    train = pd.DataFrame(
        [
            {"category": "cn_latiao", "market": "us", "date": "2026-04-03", "sales_volume": 90.0},
            {"category": "cn_changsha_mifen", "market": "sea", "date": "2026-04-03", "sales_volume": 70.0},
        ]
    )
    holdout_csv = tmp_path / "holdout.csv"
    holdout_csv.write_text(_holdout_frame().to_csv(index=False), encoding="utf-8")
    train_csv = tmp_path / "train.csv"
    train_csv.write_text(train.to_csv(index=False), encoding="utf-8")
    responses = tmp_path / "responses" / "global"
    responses.mkdir(parents=True)
    for run, offset in {"1": 0.5, "2": 1.0}.items():
        (responses / f"run{run}.md").write_text(_prediction_text(offset), encoding="utf-8")
    (responses / "run1.meta.json").write_text(
        json.dumps({"model": "global", "label": "全局 AI", "source": "api"}, ensure_ascii=False),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    monkeypatch.setattr(benchmark, "TRAIN_CSV", train_csv)
    monkeypatch.setattr(benchmark, "HOLDOUT_CSV", holdout_csv)
    monkeypatch.setattr(benchmark, "RECOMMEND_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(benchmark, "RESPONSES_DIR", tmp_path / "responses")
    monkeypatch.setattr(benchmark, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(
        benchmark,
        "_system_mae_by_combo",
        lambda: pd.Series({combo: 10.0 for combo in COMBOS}),
    )

    payload = benchmark.score_all(["global"])
    assert "significance" in payload
    assert payload["significance"]["n_tests"] == 2  # run1、run2 两个 A 组检验
    report_md = (out_dir / "significance_report.md").read_text(encoding="utf-8")
    assert "A 组" in report_md
    assert "BH" in report_md
    # q 值已写回 summary 所用字段
    sig_run1 = payload["models"]["global"]["significance_vs_system"]["1"]
    assert "q_value" in sig_run1


def test_summary_markdown_lite_scope_numbers() -> None:
    payload = {
        "train_dates": "2024-07-05 ~ 2026-04-03",
        "holdout_dates": "2026-04-10 ~ 2026-06-26",
        "total_cells": 23760,
        "system_baseline": {"prophet_mape": 7.73, "lightgbm_mape": 3.14},
        "scope": {
            "mode": "lite",
            "combos": [["cn_latiao", "us"], ["cn_changsha_mifen", "sea"]],
            "total_cells": 24,
        },
        "models": {},
    }
    md = benchmark._summary_markdown(payload)
    assert "共 2 组合 × 12 周 = 24 个预测格子" in md
    assert "轻量 2 组合 × 12 周 = 24 格" in md
    assert "990" not in md  # lite 口径不再混用 COMBO_COUNT
