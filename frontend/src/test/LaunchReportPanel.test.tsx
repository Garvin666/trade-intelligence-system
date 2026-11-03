import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  exportLaunchReport,
  streamLaunchReport,
  type LaunchReportStreamHandlers,
} from "@/shared/api/client";
import type { LaunchReportResult } from "@/shared/api/types";
import { LaunchReportPanel } from "@/features/four-brain/LaunchReportPanel";
import { LAUNCH_TEMPLATE, buildLaunchPrompt } from "@/features/four-brain/launchTemplate";

vi.mock("@/shared/api/hooks", () => ({
  useAiConfig: () => ({ data: { configured: true, model: "gpt-test" } }),
  useExamples: () => ({ data: { launch_report: [] } }),
  useTradeCatalog: () => ({
    data: {
      data: {
        categories: [
          { key: "cn_latiao", label: "辣条" },
          { key: "cn_longjing", label: "西湖龙井" },
          { key: "cn_frozen_dumplings", label: "速冻水饺" },
        ],
      },
    },
  }),
}));

vi.mock("@/shared/api/client", () => ({
  streamLaunchReport: vi.fn(),
  exportLaunchReport: vi.fn(),
}));

describe("LaunchReportPanel", () => {
  beforeEach(() => {
    vi.mocked(streamLaunchReport).mockImplementation(
      async (_payload, handlers) => {
        handlers?.onStatus?.({ phase: "connecting", elapsed_ms: 0, chars: 0 });
        handlers?.onDelta?.("# 示例立项报告\n\n");
        handlers?.onStatus?.({ phase: "streaming", elapsed_ms: 40, chars: 9 });
        handlers?.onDelta?.("| 指标 | 数值 |\n| --- | --- |\n| 综合评分 | 78 |");
        handlers?.onStatus?.({ phase: "done", elapsed_ms: 60, chars: 40 });
        return {
          report:
            "# 示例立项报告\n\n| 指标 | 数值 |\n| --- | --- |\n| 综合评分 | 78 |",
          mode: "launch-report-v1",
          generated_at: "2026-08-15T12:00:00",
          ai: { enabled: true, used: true, configured: true },
        };
      },
    );
  });

  it("renders structured fields and fills the example", async () => {
    const user = userEvent.setup();
    render(<LaunchReportPanel />);

    expect(screen.getByLabelText(/目标市场/)).toBeInTheDocument();
    expect(screen.getByLabelText(/目标类目/)).toBeInTheDocument();
    expect(screen.getByLabelText(/候选产品/)).toBeInTheDocument();
    expect(screen.getByLabelText(/竞品数据/)).toBeInTheDocument();
    expect(screen.getByLabelText(/评论分析/)).toBeInTheDocument();
    expect(screen.getByLabelText(/成本数据/)).toBeInTheDocument();
    expect(screen.getByLabelText(/关键词数据/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "填充示例" }));
    expect(screen.getByLabelText(/候选产品/)).toHaveValue("辣条（网红休闲零食）");
  });

  it("builds a prompt with placeholder data substituted", () => {
    const prompt = buildLaunchPrompt(
      {
        market: "us",
        market_custom: "Amazon 美国站",
        category: "cn_latiao",
        category_custom: "Grocery & Gourmet Food > Snacks > Spicy Strips",
        product: "辣条（网红休闲零食）",
        competitors: "竞品 A：$4.99",
        reviews: "差评集中在包装漏气",
        costs: "采购价 ¥12",
        keywords: "latiao spicy strips",
        sections: ["summary", "market", "competitors", "pain_points", "product", "finance", "plan", "risk"],
        style: "logic",
        output_format: "markdown",
      },
      LAUNCH_TEMPLATE,
    );
    expect(prompt).toContain("**目标市场**：Amazon 美国站");
    expect(prompt).toContain("**候选产品**：辣条（网红休闲零食）");
    expect(prompt).toContain("竞品 A：$4.99");
    expect(prompt).toContain("### 1. 执行摘要");
    expect(prompt).not.toContain("{{market}}");
  });

  it("generates and renders a markdown report", async () => {
    const user = userEvent.setup();
    render(<LaunchReportPanel />);

    await user.click(screen.getByRole("button", { name: "填充示例" }));
    await user.click(screen.getByRole("button", { name: "生成报告" }));

    const calledPrompt = vi.mocked(streamLaunchReport).mock.calls[0][0].prompt;
    expect(calledPrompt).toContain("**目标市场**：Amazon 美国站");
    expect(await screen.findByRole("heading", { name: "示例立项报告" })).toBeInTheDocument();
    expect(screen.getByText("综合评分")).toBeInTheDocument();
  });

  it("shows live status and incremental content while streaming", async () => {
    const user = userEvent.setup();
    let resolveStream: (value: LaunchReportResult) => void = () => undefined;
    let capturedHandlers: LaunchReportStreamHandlers = {};
    vi.mocked(streamLaunchReport).mockImplementation((_payload, handlers) => {
      capturedHandlers = handlers ?? {};
      return new Promise((resolve) => {
        resolveStream = resolve;
      });
    });
    render(<LaunchReportPanel />);

    await user.click(screen.getByRole("button", { name: "生成报告" }));
    expect(await screen.findByText(/正在连接 AI/)).toBeInTheDocument();

    act(() => {
      capturedHandlers.onStatus?.({ phase: "connecting", elapsed_ms: 0, chars: 0 });
      capturedHandlers.onDelta?.("# 示例立项报告\n\n");
      capturedHandlers.onStatus?.({ phase: "streaming", elapsed_ms: 50, chars: 9 });
      capturedHandlers.onDelta?.("正文内容");
    });

    expect(screen.getByRole("heading", { name: "示例立项报告" })).toBeInTheDocument();
    expect(screen.getByText(/AI 正在生成报告/)).toBeInTheDocument();

    await act(async () => {
      resolveStream({
        report: "# 示例立项报告\n\n正文内容",
        mode: "launch-report-v1",
        generated_at: "2026-08-15T12:00:00",
        ai: { enabled: true, used: true, configured: true },
      });
    });
    expect(await screen.findByRole("button", { name: "导出 PDF" })).toBeInTheDocument();
  });

  it("exports the generated report as pdf", async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn(() => "blob:launch-report");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectURL,
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.mocked(exportLaunchReport).mockResolvedValue(
      new Blob(["%PDF"], { type: "application/pdf" }),
    );

    render(<LaunchReportPanel />);
    await user.click(screen.getByRole("button", { name: "生成报告" }));
    await user.click(await screen.findByRole("button", { name: "导出 PDF" }));

    expect(exportLaunchReport).toHaveBeenCalledWith(
      expect.objectContaining({
        format: "pdf",
        report: expect.stringContaining("# 示例立项报告"),
      }),
    );
    expect(click).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:launch-report");
  });
});
