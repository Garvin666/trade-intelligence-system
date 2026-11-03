import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DynamicDemoSection } from "@/features/demo/DynamicDemoSection";

vi.mock("@/shared/api/hooks", () => ({
  useCatalog: () => ({
    data: { categories: { pet: "辣条" }, markets: { us: "美国" } },
  }),
  useDashboardData: () => ({
    data: undefined,
    isLoading: true,
    isError: false,
  }),
}));

vi.mock("@/shared/ui/select", () => ({
  Select: ({ ariaLabel }: { ariaLabel?: string }) => (
    <select aria-label={ariaLabel} />
  ),
}));

vi.mock("@/features/demo/DemoDeck", () => ({
  DemoDeck: () => <div>deck</div>,
}));

vi.mock("@/features/demo/DemoSectionMotion", () => ({
  DemoSectionMotion: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("@/features/demo/InteractiveFlow", () => ({
  InteractiveFlow: () => <div>flow</div>,
}));

vi.mock("@/features/demo/LiveMarketChart", () => ({
  LiveMarketChart: () => <div>chart</div>,
}));

vi.mock("@/features/demo/OperationGuideDiagram", () => ({
  OperationGuideDiagram: () => <div>guide</div>,
}));

vi.mock("@/features/demo/PipelinePlayer", () => ({
  PipelinePlayer: () => <div>player</div>,
}));

vi.mock("@/features/demo/PipelineScene3D", () => ({
  PipelineScene3D: () => <div>scene</div>,
}));

describe("DynamicDemoSection（独立演示页）", () => {
  it("提供返回首页按钮并触发 onBack", async () => {
    const onBack = vi.fn();
    const user = userEvent.setup();
    render(<DynamicDemoSection hideDeckToggle onBack={onBack} />);

    const back = screen.getByRole("button", { name: "返回首页" });
    await user.click(back);

    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
