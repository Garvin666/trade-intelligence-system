"""
四脑 AI 研究代理。

模型通过 JSON action 协议决定是否调用工具：联网搜索、抓取网页、读取本地数据。
后端执行工具后把结果追加到上下文中，模型再继续推理，直到输出 final。
"""

from __future__ import annotations

import json
from typing import Any

from src.four_brain import data_tools


TOOL_DESCRIPTIONS = """
你可以使用以下工具，每次只输出一个 JSON 对象：

联网搜索：
{"action":"web_search","query":"frozen chinese dumplings US market trend 2026 sales competition","max_results":5}

抓取网页：
{"action":"fetch_page","url":"https://taxation-customs.ec.europa.eu/news/e-commerce-150-eur-customs-duty-exemption-threshold-be-removed-2026-2025-11-13_en"}

读取本地看板数据：
{"action":"load_dashboard_data","category":"cn_latiao","market":"us"}

获取模拟平台数据：
{"action":"mock_market_data","category":"cn_latiao","market":"us"}

当信息足够时输出最终结果：
{"action":"final","summary":"研究总结","evidence":["证据1","证据2"]}
""".strip()


def run_research_agent(
    provider: Any,
    goal: str,
    data: dict[str, Any],
    max_steps: int = 5,
    search_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    system = (
        "你是跨境电商数据研究助手。你的任务是按用户需求获取数据并形成中文研究总结。"
        + TOOL_DESCRIPTIONS
        + (
            "\n要求："
            "1. 每轮搜索把“产品 + 市场 + 年份 + 关注维度”写清楚，例如“latiao spicy snack US 2026 customer reviews complaints”。"
            "2. summary 必须用中文输出，包含市场趋势、价格带、竞争、评论与合规要点，并尽量给出量化区间；"
            "3. 每条结论都要能对应到 evidence/来源标题与链接，不要编造工具结果，工具返回什么就引用什么；"
            "4. 如果来源缺失、语言混杂或数据日期不明，请在 summary 中明确标注“信息不足/待核验”，不要用模糊表述代替事实；"
            "5. 当工具返回的是模拟数据时，必须说明“模拟数据，需人工核验”。"
        )
    )
    user_text = f"研究目标：{goal}"
    steps: list[dict[str, Any]] = []

    for step in range(1, max_steps + 1):
        response = provider.chat_json(system, user_text)
        if not isinstance(response, dict):
            raise ValueError("Research agent response must be a JSON object")
        action = str(response.get("action") or "").strip().lower()
        if action == "final":
            return {
                "summary": str(response.get("summary") or ""),
                "evidence": response.get("evidence") or [],
                "steps": steps,
                "iterations": step,
            }
        tool_result, sources = data_tools.execute_tool_with_meta(response, data, search_config=search_config)
        steps.append(
            {
                "step": step,
                "action": response,
                "result_preview": tool_result[:500],
                "sources": sources,
            }
        )
        user_text += (
            f"\n\n工具调用 {step}：{json.dumps(response, ensure_ascii=False)}\n"
            f"工具返回：{tool_result}"
        )

    return {
        "summary": "已达到最大工具调用次数，将基于已有信息继续分析。",
        "evidence": [],
        "steps": steps,
        "iterations": max_steps,
    }


__all__ = ["TOOL_DESCRIPTIONS", "run_research_agent"]
