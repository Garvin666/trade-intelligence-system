import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FourQuestionsMark } from "@/shared/brand/FourQuestionsMark";

describe("FourQuestionsMark（罗盘四问品牌图形）", () => {
  it("渲染品牌图形并携带可访问标签", () => {
    render(<FourQuestionsMark />);
    expect(screen.getByRole("img", { name: "远帆智品 · 罗盘四问" })).toBeInTheDocument();
  });

  it("支持尺寸与自定义类", () => {
    const { container } = render(<FourQuestionsMark size={64} className="text-white" />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("width")).toBe("64");
    expect(svg?.className.baseVal).toContain("text-white");
  });
});
