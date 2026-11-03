import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  RouteTransitionProvider,
  useTransitionNavigate,
} from "@/widgets/RouteTransition";

function Probe() {
  const transitionNavigate = useTransitionNavigate();
  return (
    <button type="button" onClick={() => transitionNavigate("/dashboard")}>
      go
    </button>
  );
}

describe("RouteTransitionProvider", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("navigates immediately under reduced motion and keeps the overlay mounted", async () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: true,
        media: "",
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    );

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route
            path="/"
            element={
              <RouteTransitionProvider>
                <Probe />
              </RouteTransitionProvider>
            }
          />
          <Route path="/dashboard" element={<div>Dashboard page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(document.querySelector(".route-overlay")).not.toBeNull();
    await user.click(screen.getByRole("button", { name: "go" }));
    expect(screen.getByText("Dashboard page")).toBeInTheDocument();
  });

  it("does not navigate when the page is scrolled to the bottom", async () => {
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 800,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 200,
    });
    Object.defineProperty(document.documentElement, "scrollHeight", {
      configurable: true,
      get: () => 1000,
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route
            path="/"
            element={
              <RouteTransitionProvider>
                <Probe />
              </RouteTransitionProvider>
            }
          />
          <Route path="/dashboard" element={<div>Dashboard page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    window.dispatchEvent(
      new WheelEvent("wheel", {
        deltaY: 120,
        bubbles: true,
        cancelable: true,
      }),
    );
    await new Promise((resolve) => window.setTimeout(resolve, 50));

    expect(screen.queryByText("Dashboard page")).not.toBeInTheDocument();
  });
});
