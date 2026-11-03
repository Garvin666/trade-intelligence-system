import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  GUIDE_STEPS,
  OperationGuideDiagram,
} from "@/features/demo/OperationGuideDiagram";

describe("OperationGuideDiagram", () => {
  it("keeps five onboarding steps with unique ids", () => {
    expect(GUIDE_STEPS).toHaveLength(5);
    expect(new Set(GUIDE_STEPS.map((step) => step.id)).size).toBe(5);
    GUIDE_STEPS.forEach((step) => {
      expect(step.label).toBeTruthy();
      expect(step.description).toBeTruthy();
    });
  });

  it("renders the operation guide panel", () => {
    render(<OperationGuideDiagram autoStart={false} />);
    expect(screen.getByText("系统操作指引")).toBeInTheDocument();
    expect(screen.getByText("选择组合")).toBeInTheDocument();
    expect(screen.getByText("导出报告")).toBeInTheDocument();
  });
});
