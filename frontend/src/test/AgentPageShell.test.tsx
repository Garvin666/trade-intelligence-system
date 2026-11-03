import { render, screen } from "@testing-library/react";
import { Bot } from "lucide-react";
import { describe, expect, it } from "vitest";
import { AgentPageShell } from "@/widgets/AgentPageShell";

describe("AgentPageShell（小助手式页面外壳）", () => {
  it("渲染标题与内容区", () => {
    render(
      <AgentPageShell icon={Bot} title="小助手">
        <p>页面内容</p>
      </AgentPageShell>,
    );
    expect(screen.getByText("小助手")).toBeInTheDocument();
    expect(screen.getByText("页面内容")).toBeInTheDocument();
  });

  it("渲染描述与头部操作区", () => {
    render(
      <AgentPageShell
        icon={Bot}
        title="贸易决策工作台"
        description="描述文字"
        action={<button type="button">导出</button>}
      >
        <p>页面内容</p>
      </AgentPageShell>,
    );
    expect(screen.getByText("描述文字")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出" })).toBeInTheDocument();
  });
});
