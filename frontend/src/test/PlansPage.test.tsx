import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PlansPage from "@/pages/PlansPage";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { buildDemoSeed } from "@/features/plans/demoSeed";

const mocks = vi.hoisted(() => ({
  transitionNavigate: vi.fn(),
}));

vi.mock("@/widgets/RouteTransition", () => ({
  useTransitionNavigate: () => mocks.transitionNavigate,
}));

vi.mock("@/shared/api/hooks", () => ({
  useExamples: () => ({ data: { workflow: [] } }),
  useSystemStatus: () => ({
    data: {
      health: { status: "ok", mcp: true, jobs: { items: [] } },
      engineering: {},
      systemEval: {},
      suppliers: { rows: Array.from({ length: 66 }, () => ({})) },
    },
    isLoading: false,
    isError: false,
  }),
  useAiConfig: () => ({
    data: {
      configured: true,
      has_key: true,
      model: "deepseek-chat",
      base_url: "https://api.deepseek.com/v1",
    },
    isLoading: false,
    isError: false,
  }),
  useDataStatus: () => ({
    data: {
      online: {
        provider: "duckduckgo_html",
        fallback_used: true,
        sources_count: 990,
      },
      trends: {
        provider: "mock",
        fallback_used: true,
        coverage: { requested: 66, real: 0, mock: 66 },
      },
      platform_rankings: {
        providers: {
          amazon_github: { status: "ok" },
          mock: { status: "fallback" },
        },
        fallback_used: true,
        rows: 5174,
      },
      customs: {
        provider: "comtrade",
        fallback_used: false,
        rows: 66,
      },
      policy: {
        status: "ready",
        provider: "duckduckgo_html",
        fallback_used: false,
        events: 21,
      },
      suppliers: {
        provider: "mock",
        fallback_used: true,
        rows: 66,
        coverage: { requested: 66, real: 0, mock: 66 },
        errors: ["1688 risk control"],
      },
      as_of_label: "数据更新至 2026-08-22",
    },
    isLoading: false,
    isError: false,
  }),
  useJobs: () => ({
    data: {
      items: [
        { name: "daily_update", status: "done" },
        { name: "market_daily", status: "idle" },
        { name: "control_run", status: "idle" },
        { name: "policy_refresh", status: "ready" },
      ],
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/shared/api/offline", () => ({ IS_OFFLINE: false }));

vi.mock("@/shared/motion/Page3DScene", () => ({
  Page3DScene: () => <div data-testid="page3d" />,
}));

describe("PlansPage（方案中心）", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useTradeIntelStore.setState({
      seededDemo: true,
      selectionDraft: null,
      watchlist: [],
      scenarios: [],
      batchRuns: [],
    });
  });

  it("在线模式渲染四个归档区块、联动链路与真实能力对接", () => {
    render(<PlansPage />);

    expect(screen.getByRole("heading", { name: "方案中心" })).toBeInTheDocument();
    expect(screen.getByText("联动链路")).toBeInTheDocument();
    expect(screen.getByText("当前方案草稿")).toBeInTheDocument();
    expect(screen.getByText("关注清单")).toBeInTheDocument();
    expect(screen.getAllByText("方案沙盘").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("批量分析历史")).toBeInTheDocument();
    expect(screen.getByText("真实能力对接")).toBeInTheDocument();
    expect(screen.getByText("数据源与任务")).toBeInTheDocument();
    expect(screen.getByText("REST API")).toBeInTheDocument();
    expect(screen.getByText("MCP Server")).toBeInTheDocument();
    expect(screen.getByText("AI 接入")).toBeInTheDocument();
  });

  it("数据源状态按 ready/fallback/error 映射为对应徽标", () => {
    render(<PlansPage />);

    expect(screen.getByText("在线")).toBeInTheDocument();
    expect(screen.getByText("已挂载")).toBeInTheDocument();
    expect(screen.getByText("已配置")).toBeInTheDocument();
    expect(screen.getAllByText("回退").length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText("就绪").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("模拟")).toBeInTheDocument();
    expect(screen.getByText("模拟 · 真实 0 / 模拟 66 / 共 66 · 66 行 · 1 条错误")).toBeInTheDocument();
  });

  it("后台任务状态显示为完成/空闲/就绪", () => {
    render(<PlansPage />);

    expect(screen.getByText("每日数据更新")).toBeInTheDocument();
    expect(screen.getByText("市场日报")).toBeInTheDocument();
    expect(screen.getByText("对照组评测")).toBeInTheDocument();
    expect(screen.getAllByText("政策雷达").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("完成")).toBeInTheDocument();
    expect(screen.getAllByText("空闲").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("就绪").length).toBeGreaterThanOrEqual(1);
  });

  it("联动按钮使用真实路由跳转", async () => {
    const user = userEvent.setup();
    render(<PlansPage />);

    await user.click(screen.getAllByRole("button", { name: "去选品看板" })[0]);
    expect(mocks.transitionNavigate).toHaveBeenCalledWith("/dashboard");
    await user.click(screen.getAllByRole("button", { name: "去四脑工作台" })[0]);
    expect(mocks.transitionNavigate).toHaveBeenCalledWith("/workbench");
    await user.click(screen.getAllByRole("button", { name: "去贸易决策" })[0]);
    expect(mocks.transitionNavigate).toHaveBeenCalledWith("/trade");
  });

  it("预置记录展示演示预置角标，用户记录不展示", () => {
    const seed = buildDemoSeed("2026-08-22T00:00:00.000Z");
    useTradeIntelStore.setState({
      seededDemo: true,
      selectionDraft: seed.selectionDraft,
      watchlist: [
        ...seed.watchlist,
        {
          id: "user-item",
          label: "我的真实关注",
          category: "cn_latiao",
          market: "us",
          verdict: "Go",
          score: 80,
          createdAt: "2026-08-22T00:00:00.000Z",
          isDemo: false,
        },
      ],
      scenarios: seed.scenarios,
      batchRuns: seed.batchRuns,
    });

    render(<PlansPage />);

    expect(screen.getAllByText("演示预置").length).toBe(8);
    expect(screen.getByText("我的真实关注")).toBeInTheDocument();
    expect(
      screen.getByText("我的真实关注").closest(".glass-soft")?.textContent ?? "",
    ).not.toContain("演示预置");
  });

  it("无方案草稿时四脑立项与贸易决策按钮禁用", () => {
    render(<PlansPage />);

    expect(screen.getByRole("button", { name: "四脑立项" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "贸易决策" })).toBeDisabled();
  });
});
