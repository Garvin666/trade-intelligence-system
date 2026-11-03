import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { SystemConsole } from "@/features/system/SystemConsole";

vi.mock("@/shared/api/client", () => ({
  fetchEnvCheck: vi.fn(async () => ({ overall: "ok", groups: {} })),
}));

vi.mock("@/shared/api/offline", () => ({ IS_OFFLINE: false }));

vi.mock("@/features/system/SystemOverview", () => ({
  SystemOverview: () => <div>概览内容</div>,
}));

vi.mock("@/features/system/JobsPanel", () => ({
  JobsPanel: () => <div>后台任务内容</div>,
}));

vi.mock("@/features/ai-config/AiConfigPanel", () => ({
  AiConfigPanel: () => <div>AI 接入内容</div>,
}));

vi.mock("@/features/system/FeedbackWeightsPanel", () => ({
  FeedbackWeightsPanel: () => <div>反馈与权重内容</div>,
}));

vi.mock("@/features/system/ControlBenchmarkPanel", () => ({
  ControlBenchmarkPanel: () => <div>AI 对照内容</div>,
}));

vi.mock("@/features/system/EnvCheckPanel", () => ({
  EnvCheckPanel: () => <div>环境自检内容</div>,
}));

vi.mock("@/features/plans/IntegrationPanel", () => ({
  IntegrationPanel: ({ showSystemLink }: { showSystemLink?: boolean }) => (
    <div>
      真实能力内容
      {showSystemLink === false && <span>控制台内不显示自引用链接</span>}
    </div>
  ),
}));

describe("SystemConsole 真实能力页签", () => {
  it("展示对接状态页签，且控制台内不出现跳转自身页面的按钮", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <SystemConsole />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("tab", { name: /真实能力/ })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /真实能力/ }));

    expect(screen.getByText("真实能力内容")).toBeInTheDocument();
    expect(screen.getByText("控制台内不显示自引用链接")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "查看系统控制台" })).not.toBeInTheDocument();
  });
});
