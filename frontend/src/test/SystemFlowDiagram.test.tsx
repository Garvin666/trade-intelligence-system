import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SYSTEM_NODES, SystemFlowDiagram } from "@/features/demo/SystemFlowDiagram";

describe("SystemFlowDiagram", () => {
  it("keeps six connected system modules", () => {
    expect(SYSTEM_NODES).toHaveLength(6);
    expect(new Set(SYSTEM_NODES.map((node) => node.id)).size).toBe(6);
    SYSTEM_NODES.forEach((node) => {
      expect(node.label).toBeTruthy();
      expect(node.color).toMatch(/^#/);
    });
  });

  it("renders the flow panel with an accessible diagram", () => {
    render(<SystemFlowDiagram animate={false} />);
    expect(screen.getByText("系统流程动画示意图")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "系统流程动画示意图" })).toBeInTheDocument();
  });
});
