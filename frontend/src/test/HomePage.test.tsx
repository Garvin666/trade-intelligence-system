import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import HomePage from "@/pages/HomePage";

vi.mock("@/widgets/EarthHero", () => ({
  EarthHero: () => <div>Earth Hero Mock</div>,
}));

describe("HomePage（首页）", () => {
  it("渲染全屏航海首屏且不再展示动态演示入口", () => {
    render(<HomePage />);

    expect(screen.getByText("Earth Hero Mock")).toBeInTheDocument();
    expect(screen.queryByText("动态演示")).not.toBeInTheDocument();
    expect(screen.queryByText("进入动态演示")).not.toBeInTheDocument();
  });
});
