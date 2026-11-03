import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { EarthHero } from "@/widgets/EarthHero";

const mocks = vi.hoisted(() => ({
  transitionNavigate: vi.fn(),
}));

vi.mock("@/widgets/RouteTransition", () => ({
  useTransitionNavigate: () => mocks.transitionNavigate,
}));

describe("EarthHero（首页决策定位与痛点账板）", () => {
  it("渲染精简后的决策定位文案", () => {
    render(
      <MemoryRouter>
        <EarthHero />
      </MemoryRouter>,
    );
    expect(screen.getByText("远帆智品 · Trade Intelligence")).toBeInTheDocument();
    expect(screen.getByText("可追溯的 Go/No-Go 选品决策")).toBeInTheDocument();
    expect(
      screen.getByText("把销量趋势、关税政策、到岸成本与合规风险合并为可追溯的 Go/No-Go 决策"),
    ).toBeInTheDocument();
    expect(screen.getByText("卖什么 · 怎么卖 · 卖到哪 · 是否值得卖")).toBeInTheDocument();
    expect(screen.getByText("每日联网快照")).toBeInTheDocument();
    expect(screen.getByText("证据闸 · 官方源优先")).toBeInTheDocument();
  });

  it("渲染四个痛点入口，并携带深链跳转", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <EarthHero />
      </MemoryRouter>,
    );
    expect(screen.getByText("政策突变难量化")).toBeInTheDocument();
    expect(screen.getByText("结论依据不可追溯")).toBeInTheDocument();
    expect(screen.getByText("黑盒指标不敢信")).toBeInTheDocument();
    expect(screen.getByText("结论难执行、换工具成本高")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /政策突变难量化/ }));
    expect(mocks.transitionNavigate).toHaveBeenCalledWith("/trade?tab=policy-impact");

    await user.click(screen.getByRole("button", { name: /黑盒指标不敢信/ }));
    expect(mocks.transitionNavigate).toHaveBeenCalledWith("/dashboard?tab=data-depth");
  });
});
