"""从 control_metrics.json 存档重建 significance_report.md（A-3 产物核对用）。

背景：对照组 responses 目录在运行后未保留，无法用 benchmark.compute_significance_tests
重新解析预测；但 score_all 已把 A 组显著性（models.*.significance_vs_system）写入
control_metrics.json。本脚本从该存档重建独立显著性报告：

- A 组：AI vs 系统 LightGBM 基线（各 run 的配对检验，q = BH(p)，单检验 q=p）；
- B 组：模型两两比较——当前仅一个全局模型时标注"无"；
- 报告头部诚实标注数据来源为存档重建，非重新运行。

用法：.venv\\Scripts\\python scripts\\rebuild_significance_report.py
产物：output/significance_report.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analysis.stats import bh_adjust  # noqa: E402
from src.config import CONTROL_METRICS_JSON, OUTPUT_DIR  # noqa: E402

ALPHA = 0.05
REPORT_PATH = OUTPUT_DIR / "significance_report.md"


def _load_control() -> dict:
    with open(CONTROL_METRICS_JSON, encoding="utf-8") as handle:
        return json.load(handle)


def build_report(payload: dict) -> str:
    models = payload.get("models") or {}
    generated_at = payload.get("generated_at") or "（未知）"
    lines = [
        "# 对照组显著性报告",
        "",
        f"- 生成时间：{generated_at}",
        "- 数据来源：由 output/control/control_metrics.json 存档重建（对照组 responses 目录缺失，未重新运行评测）",
        "- 校正方法：benjamini_hochberg（全族一次 FDR 校正；本存档单检验场景 q=p）",
        f"- 阈值：q < {ALPHA}",
        "",
        "## A 组：AI vs 系统 LightGBM 基线（按品类/市场配对宏 MAE）",
        "",
        "| 模型 | 运行 | 方法 | 配对组合 n | 均值差(系统-AI) | Cohen's dz | p | q(BH) | 显著 |",
        "|------|------|------|-----------|-----------------|-----------|----|-------|------|",
    ]
    tests: list[dict] = []
    for model_key, entry in models.items():
        label = str(entry.get("label") or model_key)
        sig_map = entry.get("significance_vs_system") or {}
        for run in sorted(sig_map, key=int):
            sig = sig_map[run]
            tests.append(
                {
                    "right": label,
                    "run": run,
                    "method": sig.get("method", "-"),
                    "n": sig.get("n"),
                    "mean_difference": sig.get("mean_difference"),
                    "effect_size": sig.get("effect_size"),
                    "p_value": sig.get("p_value"),
                }
            )
    q_values = bh_adjust([t["p_value"] for t in tests]) if tests else []
    for test, q in zip(tests, q_values):
        lines.append(
            "| {right} | run{run} | {method} | {n} | {md:.4g} | {d:.3f} | "
            "{p:.4g} | {q:.4g} | {ok} |".format(
                right=test["right"],
                run=test["run"],
                method=test["method"],
                n=test["n"] if test["n"] is not None else "-",
                md=test["mean_difference"] or 0.0,
                d=test["effect_size"] or 0.0,
                p=test["p_value"] or 1.0,
                q=q,
                ok="是" if q < ALPHA else "否",
            )
        )
    if not tests:
        lines.append("| （存档中无显著性数据，需重新运行对照组） | — | — | — | — | — | — | — | — |")

    n_significant = sum(1 for q in q_values if q < ALPHA)
    lines.extend(
        [
            "",
            "## B 组：模型两两比较（各取宏 MAE 最低 run 为代表）",
            "",
        ]
    )
    if len(models) >= 2:
        lines.append("| 模型A | 模型B | 说明 |")
        lines.append("|-------|-------|------|")
        keys = list(models)
        for index, left in enumerate(keys):
            for right in keys[index + 1 :]:
                lines.append(
                    f"| {models[left].get('label', left)} | {models[right].get('label', right)} | "
                    "需 responses 存档重算，见 benchmark.compute_significance_tests |"
                )
    else:
        lines.append("当前存档仅一个全局 AI 模型，无 B 组两两比较数据。")
    lines.extend(
        [
            "",
            f"- 检验总数：{len(tests)}；显著（q<{ALPHA}）：{n_significant}",
            "- 说明：BH 后部分结论降级属预期，结论以 q 值为准。",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = _load_control()
    REPORT_PATH.write_text(build_report(payload), encoding="utf-8")
    print(f"OK: 已重建 {REPORT_PATH}")


if __name__ == "__main__":
    main()
