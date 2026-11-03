import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDemoPlayback } from "@/features/demo/useDemoPlayback";

describe("useDemoPlayback", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("advances stages while playing", () => {
    const { result } = renderHook(() =>
      useDemoPlayback({ stageCount: 3, intervalMs: 100 }),
    );
    act(() => result.current.play());
    act(() => vi.advanceTimersByTime(250));
    expect(result.current.tick).toBe(2);
    expect(result.current.stageIndex).toBe(2);
  });

  it("loops back to the first stage", () => {
    const { result } = renderHook(() =>
      useDemoPlayback({ stageCount: 2, intervalMs: 100, loop: true }),
    );
    act(() => result.current.play());
    act(() => vi.advanceTimersByTime(250));
    expect(result.current.stageIndex).toBe(0);
    act(() => vi.advanceTimersByTime(100));
    expect(result.current.stageIndex).toBe(1);
  });

  it("pauses after the last stage when loop is disabled", () => {
    const { result } = renderHook(() =>
      useDemoPlayback({ stageCount: 2, intervalMs: 100, loop: false }),
    );
    act(() => result.current.play());
    act(() => vi.advanceTimersByTime(250));
    expect(result.current.playing).toBe(false);
    expect(result.current.stageIndex).toBe(1);
  });

  it("resets tick and pauses", () => {
    const { result } = renderHook(() =>
      useDemoPlayback({ stageCount: 3, intervalMs: 100 }),
    );
    act(() => result.current.play());
    act(() => vi.advanceTimersByTime(220));
    act(() => result.current.reset());
    expect(result.current.tick).toBe(0);
    expect(result.current.playing).toBe(false);
  });
});
