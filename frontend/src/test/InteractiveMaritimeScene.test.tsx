import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InteractiveMaritimeScene } from "@/shared/motion/InteractiveMaritimeScene";

describe("InteractiveMaritimeScene（远帆号 3D 旗舰场景）", () => {
  it("无 WebGL 时渲染静态降级面板", () => {
    render(<InteractiveMaritimeScene fullscreen />);
    expect(screen.getByText("远帆航线终端")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "开启 3D 场景" })).not.toBeInTheDocument();
  });
});
