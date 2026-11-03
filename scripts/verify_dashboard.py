"""浏览器级看板验收：真实渲染、切换贸易决策页、截图并检查关键内容。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHOT_PATH = PROJECT_ROOT / "docs" / "dashboard_preview.png"
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:8501")


def main() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("text=跨境电商智能选品决策系统", timeout=60000)
        page.wait_for_selector("text=多源热度趋势", timeout=60000)

        # 关键内容检查
        checks = {
            "标题": "跨境电商智能选品决策系统",
            "多源热度趋势": "多源热度趋势",
            "未来90天预测": "未来90天预测",
            "选品推荐": "选品推荐",
            "市场对比": "市场对比",
        }
        for label, text in checks.items():
            page.wait_for_selector(f"text={text}", timeout=60000)
            count = page.get_by_text(text, exact=False).count()
            print(f"[check] {label}: {count}")
            assert count > 0, f"缺少关键内容: {label}"

        page.get_by_text("概览", exact=True).first.click()
        page.wait_for_selector("text=决策概览", timeout=60000)
        assert page.get_by_text("综合结论", exact=True).count() > 0
        print("[check] 概览（AI 设置已统一由全局 AI 接入管理）")

        page.get_by_text("组合对比", exact=True).first.click()
        page.wait_for_selector("text=组合对比", timeout=60000)
        assert page.get_by_text("请至少选择 2 个组合进行对比", exact=True).count() == 0
        print("[check] 组合对比")

        page.get_by_text("联网搜索", exact=True).first.click()
        page.wait_for_selector("text=搜索关键词", timeout=60000)
        print("[check] 联网搜索")

        page.get_by_text("贸易决策", exact=True).first.click()
        page.wait_for_selector("text=数据信用与供应链金融（离线演示版）", timeout=60000)
        page.wait_for_selector("text=多脑冲突裁决", timeout=60000)
        credit_checks = {
            "数据信用与供应链金融": "数据信用与供应链金融（离线演示版）",
            "融资就绪分": "融资就绪分",
            "融资档位": "融资档位",
            "多脑冲突裁决": "多脑冲突裁决（置信度 × 权重）",
            "冲突等级": "冲突等级",
            "裁决后得分": "裁决后得分",
        }
        for label, text in credit_checks.items():
            page.wait_for_selector(f"text={text}", timeout=60000)
            count = page.get_by_text(text, exact=False).count()
            print(f"[check] {label}: {count}")
            assert count > 0, f"缺少关键内容: {label}"

        page.get_by_text("概览", exact=True).first.click()
        page.wait_for_selector("text=一键导出决策报告", timeout=60000)
        page.get_by_text("生成 Markdown / PDF 报告", exact=True).first.click()
        page.wait_for_selector("text=报告已生成", timeout=120000)
        page.wait_for_selector('a[download]', timeout=30000)
        assert page.locator('a[download]').count() >= 2
        print("[check] 一键导出报告")

        page.screenshot(path=str(SHOT_PATH), full_page=True)
        print(f"[ok] 截图已保存: {SHOT_PATH}")
        browser.close()


if __name__ == "__main__":
    main()
