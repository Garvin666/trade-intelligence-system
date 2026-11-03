import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import TradePage from "@/pages/TradePage";
import WorkbenchPage from "@/pages/WorkbenchPage";

vi.mock("@/shared/ui/page-turn-tabs", () => ({
  PageTurnTabs: ({ defaultValue }: { defaultValue?: string }) => (
    <div data-testid="page-tabs" data-default={defaultValue ?? ""}>
      tabs
    </div>
  ),
}));

vi.mock("@/features/dashboard/ExportReportButton", () => ({
  ExportReportButton: () => null,
}));

describe("首页痛点深链", () => {
  it("TradePage 根据 tab=policy-impact 打开政策冲击", () => {
    render(
      <MemoryRouter initialEntries={["/trade?tab=policy-impact"]}>
        <Routes>
          <Route path="/trade" element={<TradePage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("page-tabs").dataset.default).toBe("policy-impact");
  });

  it("WorkbenchPage 根据 tab=import 打开数据接入", () => {
    render(
      <MemoryRouter initialEntries={["/workbench?tab=import"]}>
        <Routes>
          <Route path="/workbench" element={<WorkbenchPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("page-tabs").dataset.default).toBe("import");
  });
});
