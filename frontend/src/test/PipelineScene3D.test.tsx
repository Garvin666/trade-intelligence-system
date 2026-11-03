import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PipelineScene3D } from "@/features/demo/PipelineScene3D";

describe("PipelineScene3D", () => {
  it("falls back to the SVG system flow when WebGL is unavailable", () => {
    render(<PipelineScene3D />);
    expect(
      screen.getByRole("img", { name: "系统流程动画示意图" }),
    ).toBeInTheDocument();
  });
});
