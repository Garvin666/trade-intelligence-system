import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RouteStatusBar } from "@/shared/motion/RouteStatusBar";

describe("RouteStatusBar（静态航海状态条）", () => {
  it("渲染品牌区与四个状态格", () => {
    render(
      <RouteStatusBar
        items={[
          { label: "数据更新", value: "实时快照", tone: "green" },
          { label: "预测基线", value: "3 模型", tone: "cyan" },
          { label: "证据闸", value: "开启", tone: "amber" },
          { label: "推荐组合", value: "1980", tone: "cyan" },
        ]}
      />,
    );
    expect(screen.getByText("远帆智品")).toBeInTheDocument();
    expect(screen.getByText("实时快照")).toBeInTheDocument();
    expect(screen.getByText("1980")).toBeInTheDocument();
  });

  it("不包含旧全息条循环动画容器", () => {
    const { container } = render(
      <RouteStatusBar
        items={[
          { label: "会话", value: "在线", tone: "green" },
          { label: "传输", value: "SSE", tone: "cyan" },
        ]}
      />,
    );
    expect(container.querySelector(".holo-bar")).toBeNull();
    expect(container.querySelector(".holo-chip")).toBeNull();
  });
});
