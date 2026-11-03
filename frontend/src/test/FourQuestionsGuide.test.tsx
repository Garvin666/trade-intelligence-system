import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { RouteTransitionProvider } from "@/widgets/RouteTransition";
import { FourQuestionsGuide } from "@/widgets/FourQuestionsGuide";

describe("FourQuestionsGuide（远帆四问导览）", () => {
  it("渲染四问卡片与进入看板入口", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route
            path="/"
            element={
              <RouteTransitionProvider>
                <FourQuestionsGuide />
              </RouteTransitionProvider>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("远帆四问")).toBeInTheDocument();
    for (const key of ["卖什么", "怎么卖", "卖到哪", "是否值得卖"]) {
      expect(screen.getAllByText(key).length).toBeGreaterThan(0);
    }
    expect(screen.getAllByText("进入选品看板").length).toBeGreaterThan(0);
  });
});
