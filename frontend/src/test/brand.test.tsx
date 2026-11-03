import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LogoMark } from "@/shared/brand/LogoMark";
import { Button } from "@/shared/ui/button";

describe("brand and ui primitives", () => {
  it("renders logo with accessible label", () => {
    const { container } = render(<LogoMark size={32} />);
    const logo = screen.getByRole("img", { name: "远帆智品" });
    expect(logo).toBeInTheDocument();
    expect(logo.closest(".logo-mark")).not.toBeNull();
    expect(container.querySelectorAll(".logo-star").length).toBeGreaterThanOrEqual(5);
  });

  it("renders a disabled button", () => {
    render(<Button disabled>分析</Button>);
    expect(screen.getByRole("button", { name: "分析" })).toBeDisabled();
  });
});
