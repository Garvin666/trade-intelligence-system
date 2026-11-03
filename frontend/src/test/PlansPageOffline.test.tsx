import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PlansPage from "@/pages/PlansPage";
import { useTradeIntelStore } from "@/shared/store/trade-intel";

vi.mock("@/widgets/RouteTransition", () => ({
  useTransitionNavigate: () => vi.fn(),
}));

vi.mock("@/shared/api/hooks", () => ({
  useExamples: () => ({ data: { workflow: [] } }),
  useSystemStatus: () => ({ data: undefined, isLoading: false, isError: false }),
  useAiConfig: () => ({ data: undefined, isLoading: false, isError: false }),
  useDataStatus: () => ({ data: undefined, isLoading: false, isError: false }),
  useJobs: () => ({ data: undefined, isLoading: false, isError: false }),
}));

vi.mock("@/shared/api/offline", () => ({ IS_OFFLINE: true }));

vi.mock("@/shared/motion/Page3DScene", () => ({
  Page3DScene: () => <div data-testid="page3d" />,
}));

describe("PlansPage 离线模式", () => {
  beforeEach(() => {
    useTradeIntelStore.setState({
      seededDemo: true,
      selectionDraft: null,
      watchlist: [],
      scenarios: [],
      batchRuns: [],
    });
  });

  it("离线模式不渲染实时接口状态，只显示在线模式提示", () => {
    render(<PlansPage />);

    expect(screen.getByText(/离线单文件仅保留本地方案数据/)).toBeInTheDocument();
    expect(screen.queryByText("REST API")).not.toBeInTheDocument();
    expect(screen.queryByText("数据源与任务")).not.toBeInTheDocument();
  });
});
