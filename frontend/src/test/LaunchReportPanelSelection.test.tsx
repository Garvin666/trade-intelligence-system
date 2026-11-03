import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LaunchReportPanel } from "@/features/four-brain/LaunchReportPanel";
import { useTradeIntelStore } from "@/shared/store/trade-intel";

const mocks = vi.hoisted(() => {
  const sections = [
    "summary",
    "market",
    "competitors",
    "pain_points",
    "product",
    "finance",
    "plan",
    "risk",
  ];
  return {
    presets: [
      {
        id: "launch_a",
        label: "示例产品 A 立项",
        fields: {
          market: "us",
          category: "cn_latiao",
          product: "示例产品 A",
          sections,
          style: "logic",
          output_format: "markdown",
        },
      },
      {
        id: "launch_b",
        label: "示例产品 B 立项",
        fields: {
          market: "eu",
          category: "cn_changsha_mifen",
          product: "示例产品 B",
          sections,
          style: "logic",
          output_format: "markdown",
        },
      },
    ],
    streamLaunchReport: vi.fn(),
  };
});

vi.mock("@/shared/api/hooks", () => ({
  useAiConfig: () => ({ data: { configured: true, model: "gpt-test" } }),
  useExamples: () => ({ data: { launch_report: mocks.presets } }),
  useTradeCatalog: () => ({
    data: {
      data: {
        categories: [
          { key: "cn_latiao", label: "辣条" },
          { key: "cn_changsha_mifen", label: "长沙米粉" },
          { key: "cn_longjing", label: "西湖龙井" },
        ],
      },
    },
  }),
}));

vi.mock("@/shared/api/client", () => ({
  streamLaunchReport: mocks.streamLaunchReport,
  exportLaunchReport: vi.fn(),
}));

vi.mock("@/shared/ui/select", async () => {
  const { Select } = await import("@/test/mocks/Select");
  return { Select };
});

async function selectPreset(user: ReturnType<typeof userEvent.setup>, label: string) {
  await user.selectOptions(screen.getByLabelText("选择立项示例"), label);
}

describe("LaunchReportPanel preset linkage", () => {
  beforeEach(() => {
    useTradeIntelStore.setState({ lastFourBrainResult: null });
    localStorage.clear();
    mocks.streamLaunchReport.mockReset();
    mocks.streamLaunchReport.mockImplementation(async (_payload, handlers) => {
      handlers?.onDelta?.("# 旧立项报告");
      return {
        report: "# 旧立项报告",
        mode: "launch-report-v1",
        generated_at: "2026-08-16T12:00:00",
        ai: { enabled: true, used: true, configured: true },
      };
    });
  });

  it("switches presets and clears the previous report", async () => {
    const user = userEvent.setup();
    render(<LaunchReportPanel />);

    await selectPreset(user, "示例产品 A 立项");
    expect(screen.getByLabelText(/候选产品/)).toHaveValue("示例产品 A");

    await user.click(screen.getByRole("button", { name: "生成报告" }));
    expect(await screen.findByRole("heading", { name: "旧立项报告" })).toBeInTheDocument();

    await selectPreset(user, "示例产品 B 立项");

    expect(screen.getByLabelText(/候选产品/)).toHaveValue("示例产品 B");
    expect(screen.queryByRole("heading", { name: "旧立项报告" })).not.toBeInTheDocument();
  });

  it("fills launch fields from the latest four-brain result payload", async () => {
    useTradeIntelStore.setState({
      lastFourBrainResult: {
        category: "cn_latiao",
        category_name: "辣条",
        payload: {
          keyword: "辣条（网红休闲零食） latiao spicy snack",
          market: "us",
          unit_cost: 22,
        },
        real_evidence: { market: "us" },
      },
    });
    const user = userEvent.setup();
    render(<LaunchReportPanel />);

    await user.click(screen.getByRole("button", { name: "从四脑结论填充" }));

    expect(screen.getByLabelText(/目标市场/)).toHaveValue("us");
    expect(screen.getByLabelText(/目标类目/)).toHaveValue("cn_latiao");
    expect(screen.getByLabelText(/候选产品/)).toHaveValue(
      "辣条（网红休闲零食） latiao spicy snack",
    );
    expect(screen.getByLabelText(/成本数据/)).toHaveValue("采购成本 ¥22/件");
    expect(screen.getByLabelText(/关键词数据/)).toHaveValue(
      "候选词：辣条（网红休闲零食） latiao spicy snack",
    );
  });
});
