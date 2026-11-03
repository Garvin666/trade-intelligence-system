import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FourBrainPanel } from "@/features/four-brain/FourBrainPanel";

const LATIAO = "辣条 latiao spicy snack";
const LONGJING = "龙井绿茶 longjing green tea";

const mocks = vi.hoisted(() => {
  const examples = [
    {
      id: "fb_latiao",
      label: "辣条 latiao spicy snack",
      payload: {
        keyword: "辣条 latiao spicy snack",
        category: "cn_latiao",
        market: "us",
        price_min: 25,
        price_max: 45,
        budget: 20000,
        target_margin: 0.35,
        unit_cost: 9.5,
        freight_per_unit: 2.8,
        customs_per_unit: 0.9,
        ad_rate: 0.12,
        return_rate: 0.03,
        moq: 400,
        lead_time_days: 35,
        certifications: ["FDA 食品设施注册", "HACCP"],
      },
    },
    {
      id: "fb_longjing",
      label: "龙井绿茶 longjing green tea",
      payload: {
        keyword: "龙井绿茶 longjing green tea",
        category: "cn_longjing",
        market: "eu",
        price_min: 45,
        price_max: 90,
        budget: 25000,
        target_margin: 0.38,
        unit_cost: 18,
        freight_per_unit: 4.2,
        customs_per_unit: 1.5,
        ad_rate: 0.15,
        return_rate: 0.04,
        moq: 350,
        lead_time_days: 45,
        certifications: ["EU 1169/2011", "HACCP", "农残 MRL 检测"],
      },
    },
  ];
  return { examples, fetchFourBrain: vi.fn() };
});

vi.mock("@/shared/api/hooks", () => ({
  useExamples: () => ({ data: { four_brain: mocks.examples } }),
}));

vi.mock("@/shared/api/client", () => ({
  fetchFourBrain: mocks.fetchFourBrain,
}));

vi.mock("@/shared/ui/select", async () => {
  const { Select } = await import("@/test/mocks/Select");
  return { Select };
});

async function selectExample(user: ReturnType<typeof userEvent.setup>, label: string) {
  await user.selectOptions(screen.getByLabelText("选择四脑示例"), label);
}

describe("FourBrainPanel linkage", () => {
  beforeEach(() => {
    mocks.fetchFourBrain.mockReset();
  });

  it("sends full payload in quick mode when an example is selected", async () => {
    mocks.fetchFourBrain.mockResolvedValue({
      keyword: LONGJING,
      verdict: "conditional",
      score: 70,
    });
    const user = userEvent.setup();
    render(<FourBrainPanel />);

    await selectExample(user, LONGJING);

    expect(mocks.fetchFourBrain).toHaveBeenCalledWith(
      expect.objectContaining({
        keyword: LONGJING,
        category: "cn_longjing",
        ai: true,
        unit_cost: 18,
        freight_per_unit: 4.2,
        customs_per_unit: 1.5,
        moq: 350,
        lead_time_days: 45,
        research: false,
        tools: [],
        max_steps: 0,
        role_prompts: expect.objectContaining({
          market: expect.any(String),
          sentiment: expect.any(String),
          supply_chain: expect.any(String),
          finance: expect.any(String),
        }),
      }),
    );
  });

  it("shows concise conclusions in aligned role tabs", async () => {
    mocks.fetchFourBrain.mockResolvedValue({
      keyword: LONGJING,
      verdict: "conditional",
      score: 70,
      brains: {
        market: {
          name: "市场分析师",
          score: 75,
          direction: "推荐",
          summary: "市场结论",
          conclusion_points: ["增长快", "竞争低"],
        },
        sentiment: {
          name: "舆情洞察官",
          score: 68,
          direction: "谨慎",
          summary: "舆情结论",
          conclusion_points: ["痛点明确"],
        },
        supply_chain: {
          name: "供应链评估师",
          score: 72,
          direction: "推荐",
          summary: "供应链结论",
          conclusion_points: ["成本可控"],
        },
        finance: {
          name: "财务精算师",
          score: 71,
          direction: "推荐",
          summary: "财务结论",
          conclusion_points: ["毛利可接受"],
        },
      },
    });
    const user = userEvent.setup();
    render(<FourBrainPanel />);

    expect(screen.getByRole("tab", { name: "市场分析师" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "财务精算师" })).toBeInTheDocument();

    await selectExample(user, LONGJING);

    expect(await screen.findByText("市场结论")).toBeInTheDocument();
    expect(screen.getByText("增长快")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "财务精算师" }));
    expect(await screen.findByText("财务结论")).toBeInTheDocument();
    expect(screen.getByText("毛利可接受")).toBeInTheDocument();
  });

  it("clears the previous result before rerunning on a different example", async () => {
    mocks.fetchFourBrain.mockResolvedValueOnce({
      keyword: LATIAO,
      verdict: "conditional",
      score: 58,
      summary: "旧产品结果",
    });
    mocks.fetchFourBrain.mockReturnValueOnce(new Promise(() => {}));
    const user = userEvent.setup();
    render(<FourBrainPanel />);

    await selectExample(user, LATIAO);
    expect(await screen.findByText("旧产品结果")).toBeInTheDocument();

    await selectExample(user, LONGJING);

    expect(screen.queryByText("旧产品结果")).not.toBeInTheDocument();
    expect(mocks.fetchFourBrain).toHaveBeenCalledTimes(2);
  });
});
