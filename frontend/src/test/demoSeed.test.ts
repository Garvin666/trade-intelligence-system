import { describe, expect, it, vi } from "vitest";
import {
  applyDemoSeed,
  buildDemoSeed,
  seedDemoIfEmpty,
  type DemoSeedActions,
} from "@/features/plans/demoSeed";

function noopActions(): DemoSeedActions {
  return {
    setSelectionDraft: vi.fn(),
    addToWatchlist: vi.fn(),
    addScenario: vi.fn(),
    saveBatchRun: vi.fn(),
  };
}

describe("方案中心演示预置（demoSeed）", () => {
  it("生成结构与系统类型一致：关注 id 唯一、判定与评分字段齐全", () => {
    const seed = buildDemoSeed("2026-08-16T00:00:00.000Z");
    expect(seed.selectionDraft.category).toBe("cn_latiao");
    expect(seed.selectionDraft.market).toBe("us");
    expect(seed.selectionDraft.isDemo).toBe(true);
    expect(seed.watchlist).toHaveLength(3);
    expect(seed.scenarios).toHaveLength(2);
    expect(seed.batchRuns).toHaveLength(2);
    const ids = seed.watchlist.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const item of seed.watchlist) {
      expect(item.verdict).toBeTruthy();
      expect(item.score).toBeGreaterThan(0);
      expect(item.createdAt).toBe("2026-08-16T00:00:00.000Z");
      expect(item.isDemo).toBe(true);
    }
    for (const scenario of seed.scenarios) {
      expect(scenario.quantity).toBeGreaterThan(0);
      expect(scenario.fx_rate).toBeGreaterThan(0);
      expect(scenario.id).toBeTruthy();
      expect(scenario.isDemo).toBe(true);
    }
    for (const run of seed.batchRuns) {
      expect(run.isDemo).toBe(true);
      expect(run.items.length).toBeGreaterThan(0);
      for (const item of run.items) {
        expect(item.label).toBeTruthy();
        expect(item.verdict).toBeTruthy();
      }
    }
  });

  it("applyDemoSeed 把预置内容完整写入 store actions", () => {
    const actions = noopActions();
    applyDemoSeed(actions, "2026-08-16T00:00:00.000Z");
    expect(actions.setSelectionDraft).toHaveBeenCalledTimes(1);
    expect(actions.addToWatchlist).toHaveBeenCalledTimes(3);
    expect(actions.addScenario).toHaveBeenCalledTimes(2);
    expect(actions.saveBatchRun).toHaveBeenCalledTimes(2);
  });

  it("已预置（seededDemo=true）时跳过，不重复填充", () => {
    const actions = noopActions();
    const markDemoSeeded = vi.fn();
    seedDemoIfEmpty(
      () => ({
        seededDemo: true,
        selectionDraft: null,
        watchlist: [],
        scenarios: [],
        batchRuns: [],
      }),
      { ...actions, markDemoSeeded },
    );
    expect(actions.setSelectionDraft).not.toHaveBeenCalled();
    expect(markDemoSeeded).not.toHaveBeenCalled();
  });

  it("用户已有真实内容时跳过预置", () => {
    const actions = noopActions();
    const markDemoSeeded = vi.fn();
    seedDemoIfEmpty(
      () => ({
        seededDemo: false,
        selectionDraft: { label: "我的方案", category: "cn_latiao", market: "us" },
        watchlist: [],
        scenarios: [],
        batchRuns: [],
      }),
      { ...actions, markDemoSeeded },
    );
    expect(actions.addToWatchlist).not.toHaveBeenCalled();
    expect(markDemoSeeded).not.toHaveBeenCalled();
  });

  it("四项全空且未预置时执行填充并置位标记", () => {
    const actions = noopActions();
    const markDemoSeeded = vi.fn();
    seedDemoIfEmpty(
      () => ({
        seededDemo: false,
        selectionDraft: null,
        watchlist: [],
        scenarios: [],
        batchRuns: [],
      }),
      { ...actions, markDemoSeeded },
    );
    expect(actions.setSelectionDraft).toHaveBeenCalledTimes(1);
    expect(actions.addToWatchlist).toHaveBeenCalledTimes(3);
    expect(actions.addScenario).toHaveBeenCalledTimes(2);
    expect(actions.saveBatchRun).toHaveBeenCalledTimes(2);
    expect(markDemoSeeded).toHaveBeenCalledTimes(1);
  });
});
