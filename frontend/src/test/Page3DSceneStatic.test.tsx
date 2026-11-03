import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Page3DSceneStatic } from "@/shared/motion/Page3DSceneStatic";

describe("Page3DSceneStatic（3D 场景降级的管线状态面板）", () => {
  it("不再渲染空白长方形：包含品牌状态区与覆盖口径", () => {
    render(<Page3DSceneStatic height={132} />);
    expect(screen.getByText("远帆航线终端")).toBeInTheDocument();
    expect(
      screen.getByText("132 品类 × 15 市场 · 1980 组合 · 官方源优先"),
    ).toBeInTheDocument();
  });

  it("六步数据管线完整渲染，末端决策步骤高亮", () => {
    render(<Page3DSceneStatic height={132} />);
    // jsdom 不应用媒体查询，桌面六步与移动端精简管线同时存在于 DOM
    for (const label of ["港口", "清关", "装船", "航线", "靠港", "决策"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    for (const node of screen.getAllByText("决策")) {
      expect(node).toHaveClass("text-amber-200");
    }
  });

  it("迷你统计展示系统真实口径（品类/市场/政策/基线）", () => {
    render(<Page3DSceneStatic height={132} />);
    expect(screen.getByText("覆盖品类")).toBeInTheDocument();
    expect(screen.getByText("目标市场")).toBeInTheDocument();
    expect(screen.getByText("政策事件")).toBeInTheDocument();
    expect(screen.getByText("预测基线")).toBeInTheDocument();
    expect(screen.getByText("132")).toBeInTheDocument();
    expect(screen.getByText("21")).toBeInTheDocument();
  });

  it("保持装饰条的圆角深色底样式", () => {
    const { container } = render(<Page3DSceneStatic height={132} />);
    const bar = container.querySelector("[data-page-3d-static]");
    expect(bar).not.toBeNull();
    if (!bar) return;
    expect(bar).toHaveStyle({ height: "132px" });
    expect(bar.className).toContain("rounded-xl");
  });

  it("三个核心系统各自渲染专属内容（看板/四脑/贸易）", () => {
    const { rerender } = render(<Page3DSceneStatic height={132} variant="dashboard" />);
    expect(screen.getByText("选品看板")).toBeInTheDocument();
    expect(screen.getByText("需求")).toBeInTheDocument();
    expect(screen.getByText("合规")).toBeInTheDocument();
    expect(screen.getByText("推荐组合")).toBeInTheDocument();
    expect(screen.queryByText("每日联网快照")).not.toBeInTheDocument();

    rerender(<Page3DSceneStatic height={132} variant="workbench" />);
    expect(screen.getByText("四脑工作台")).toBeInTheDocument();
    expect(screen.getByText("战略脑")).toBeInTheDocument();
    expect(screen.getByText("风险脑")).toBeInTheDocument();
    expect(screen.getByText("并行脑")).toBeInTheDocument();
    expect(screen.queryByText("选品看板")).not.toBeInTheDocument();

    rerender(<Page3DSceneStatic height={132} variant="trade" />);
    expect(screen.getByText("贸易决策")).toBeInTheDocument();
    expect(screen.getByText("HS Code")).toBeInTheDocument();
    expect(screen.getByText("卖前体检")).toBeInTheDocument();
    expect(screen.getByText("汇率基准")).toBeInTheDocument();
    expect(screen.queryByText("四脑工作台")).not.toBeInTheDocument();
  });

  it("小助手 渲染专属智能体场景内容", () => {
    render(<Page3DSceneStatic height={132} variant="agent" />);
    expect(screen.getByText("小助手")).toBeInTheDocument();
    expect(screen.getByText("自然语言指令 · 分步执行 · 写操作先确认")).toBeInTheDocument();
    for (const label of ["意图", "工具", "确认", "执行", "来源", "完成"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("写操作")).toBeInTheDocument();
    expect(screen.getByText("需确认")).toBeInTheDocument();
    expect(screen.getByText("会话")).toBeInTheDocument();
  });
});
