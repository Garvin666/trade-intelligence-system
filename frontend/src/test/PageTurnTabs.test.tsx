import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PageTurnTabs } from "@/shared/ui/page-turn-tabs";

const tabs = [
  { value: "a", label: "A", content: <div>A content</div> },
  { value: "b", label: "B", content: <div>B content</div> },
  { value: "c", label: "C", content: <div>C content</div> },
];

describe("PageTurnTabs", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the default tab content", () => {
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

    render(<PageTurnTabs tabs={tabs} defaultValue="b" />);
    expect(screen.getByRole("tab", { name: "B" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByText("B content")).toBeInTheDocument();
  });

  it("switches content immediately under reduced motion", async () => {
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

    render(<PageTurnTabs tabs={tabs} defaultValue="a" />);
    await user.click(screen.getByRole("tab", { name: "C" }));

    expect(screen.getByText("C content")).toBeInTheDocument();
    expect(screen.queryByText("A content")).not.toBeInTheDocument();
  });
});
