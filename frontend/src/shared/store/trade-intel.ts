import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  BatchRun,
  SelectionDraft,
  TradeScenario,
  WatchlistItem,
} from "@/shared/api/types";

export type TransitionMode = "slide-x" | "slide-y" | "cube" | "book";

export interface TradeFilters {
  category: string;
  market: string;
  model: string;
}

interface TradeIntelState {
  filters: TradeFilters;
  offline: boolean;
  transitionMode: TransitionMode;
  selectionDraft: SelectionDraft | null;
  launchDraft: Record<string, unknown> | null;
  lastFourBrainResult: Record<string, unknown> | null;
  watchlist: WatchlistItem[];
  scenarios: TradeScenario[];
  batchRuns: BatchRun[];
  /** 方案中心演示预置是否已执行（持久化，避免删光后重复填充） */
  seededDemo: boolean;
  setFilters: (filters: Partial<TradeFilters>) => void;
  setOffline: (offline: boolean) => void;
  setTransitionMode: (mode: TransitionMode) => void;
  setSelectionDraft: (draft: SelectionDraft | null) => void;
  setLaunchDraft: (draft: Record<string, unknown> | null) => void;
  setLastFourBrainResult: (result: Record<string, unknown> | null) => void;
  addToWatchlist: (item: WatchlistItem) => void;
  removeFromWatchlist: (id: string) => void;
  addScenario: (scenario: TradeScenario) => void;
  removeScenario: (id: string) => void;
  saveBatchRun: (run: BatchRun) => void;
  removeBatchRun: (id: string) => void;
  markDemoSeeded: () => void;
  reset: () => void;
}

const initialFilters: TradeFilters = {
  category: "",
  market: "",
  model: "lightgbm_advanced",
};

export const useTradeIntelStore = create<TradeIntelState>()(
  persist(
    (set) => ({
      filters: initialFilters,
      offline: false,
      transitionMode: "book",
      selectionDraft: null,
      launchDraft: null,
      lastFourBrainResult: null,
      watchlist: [],
      scenarios: [],
      batchRuns: [],
      seededDemo: false,
      setFilters: (filters) =>
        set((state) => ({ filters: { ...state.filters, ...filters } })),
      setOffline: (offline) => set({ offline }),
      setTransitionMode: (mode) => set({ transitionMode: mode }),
      setSelectionDraft: (draft) => set({ selectionDraft: draft }),
      setLaunchDraft: (draft) => set({ launchDraft: draft }),
      setLastFourBrainResult: (result) => set({ lastFourBrainResult: result }),
      addToWatchlist: (item) =>
        set((state) => {
          if (state.watchlist.some((existing) => existing.id === item.id)) {
            return state;
          }
          return { watchlist: [item, ...state.watchlist] };
        }),
      removeFromWatchlist: (id) =>
        set((state) => ({
          watchlist: state.watchlist.filter((item) => item.id !== id),
        })),
      addScenario: (scenario) =>
        set((state) => {
          if (state.scenarios.some((existing) => existing.id === scenario.id)) {
            return {
              scenarios: state.scenarios.map((item) =>
                item.id === scenario.id ? scenario : item,
              ),
            };
          }
          return { scenarios: [scenario, ...state.scenarios] };
        }),
      removeScenario: (id) =>
        set((state) => ({
          scenarios: state.scenarios.filter((item) => item.id !== id),
        })),
      saveBatchRun: (run) =>
        set((state) => ({
          batchRuns: [run, ...state.batchRuns].slice(0, 30),
        })),
      removeBatchRun: (id) =>
        set((state) => ({
          batchRuns: state.batchRuns.filter((item) => item.id !== id),
        })),
      markDemoSeeded: () => set({ seededDemo: true }),
      reset: () =>
        set({
          filters: initialFilters,
          selectionDraft: null,
          launchDraft: null,
          lastFourBrainResult: null,
          watchlist: [],
          scenarios: [],
          batchRuns: [],
          seededDemo: false,
        }),
    }),
    {
      name: "yuanfan-trade-intel",
      version: 5,
      migrate: (persistedState) =>
        ({
          ...(persistedState as object),
          filters:
            (persistedState as { filters?: TradeFilters })?.filters ??
            initialFilters,
          transitionMode: "book",
          selectionDraft: null,
          launchDraft: null,
          lastFourBrainResult: null,
          watchlist: [],
          scenarios: [],
          batchRuns: [],
        }) as unknown as TradeIntelState,
      partialize: (state) => ({
        filters: state.filters,
        transitionMode: state.transitionMode,
        selectionDraft: state.selectionDraft,
        launchDraft: state.launchDraft,
        lastFourBrainResult: state.lastFourBrainResult,
        watchlist: state.watchlist,
        scenarios: state.scenarios,
        batchRuns: state.batchRuns,
        seededDemo: state.seededDemo,
      }),
    },
  ),
);
