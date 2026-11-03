import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { DemoDeck, type DemoSlide } from "@/features/demo/DemoDeck";

const slides: DemoSlide[] = [
  { id: "a", label: "A", node: <div>A content</div> },
  { id: "b", label: "B", node: <div>B content</div> },
  { id: "c", label: "C", node: <div>C content</div> },
];

function DeckHarness({
  onShowAll = vi.fn(),
}: {
  onShowAll?: () => void;
}) {
  const [index, setIndex] = useState(0);
  return (
    <DemoDeck
      slides={slides}
      activeIndex={index}
      onIndexChange={setIndex}
      mode="slide-x"
      playing={false}
      onTogglePlaying={vi.fn()}
      onShowAll={onShowAll}
    />
  );
}

function BookModeHarness() {
  const [index, setIndex] = useState(0);
  return (
    <DemoDeck
      slides={slides}
      activeIndex={index}
      onIndexChange={setIndex}
      mode="book"
      playing={false}
      onTogglePlaying={vi.fn()}
      onShowAll={vi.fn()}
    />
  );
}

describe("DemoDeck", () => {
  it("moves forward and backward through slides", async () => {
    const user = userEvent.setup();
    render(<DeckHarness />);
    expect(screen.getByText("A content")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByText("B content")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "上一页" }));
    expect(screen.getByText("A content")).toBeInTheDocument();
  });

  it("jumps to a slide from the progress dots", async () => {
    const user = userEvent.setup();
    render(<DeckHarness />);
    await user.click(screen.getByRole("button", { name: "切换到 C" }));
    expect(screen.getByText("C content")).toBeInTheDocument();
  });

  it("exposes the all-show action", async () => {
    const user = userEvent.setup();
    const onShowAll = vi.fn();
    render(<DeckHarness onShowAll={onShowAll} />);
    await user.click(screen.getByRole("button", { name: "全部展示" }));
    expect(onShowAll).toHaveBeenCalledTimes(1);
  });

  it("keeps the homepage cube behavior when the global mode is book", async () => {
    const user = userEvent.setup();
    render(<BookModeHarness />);
    expect(screen.getByText("A content")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByText("B content")).toBeInTheDocument();
  });
});
