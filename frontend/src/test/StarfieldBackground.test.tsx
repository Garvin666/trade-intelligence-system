import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StarfieldBackground } from "@/shared/motion/StarfieldBackground";

describe("StarfieldBackground（深空粒子背景）", () => {
  it("渲染 canvas 与页面变体标记", () => {
    const { container } = render(<StarfieldBackground variant="trade" />);
    const root = container.querySelector("[data-starfield]");
    expect(root).not.toBeNull();
    expect(root?.getAttribute("data-starfield")).toBe("trade");
    expect(root?.querySelector("canvas")).not.toBeNull();
  });

  it("减少动态效果模式下不报错", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: true,
        media: "",
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    );
    const { container } = render(<StarfieldBackground variant="workbench" />);
    expect(container.querySelector("canvas")).not.toBeNull();
    vi.unstubAllGlobals();
  });
});
