import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import DemoPage from "@/pages/DemoPage";

const mocks = vi.hoisted(() => ({
  transitionNavigate: vi.fn(),
}));

vi.mock("@/features/demo/DynamicDemoSection", () => ({
  DynamicDemoSection: ({
    onBack,
    hideDeckToggle,
  }: {
    onBack?: () => void;
    hideDeckToggle?: boolean;
  }) => (
    <div>
      <button type="button" onClick={onBack}>
        返回首页
      </button>
      {hideDeckToggle ? <span>hideDeck</span> : null}
    </div>
  ),
}));

vi.mock("@/widgets/RouteTransition", () => ({
  useTransitionNavigate: () => mocks.transitionNavigate,
}));

describe("DemoPage（独立动态演示页）", () => {
  it("返回首页按钮触发回到首页导航", async () => {
    const user = userEvent.setup();
    render(<DemoPage />);

    expect(screen.getByText("hideDeck")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "返回首页" }));

    expect(mocks.transitionNavigate).toHaveBeenCalledWith("/");
  });
});
