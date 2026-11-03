import { describe, expect, it } from "vitest";
import { useTradeIntelStore } from "@/shared/store/trade-intel";

describe("trade intel store", () => {
  it("updates filters immutably", () => {
    useTradeIntelStore.getState().setFilters({ category: "cn_latiao" });
    const state = useTradeIntelStore.getState();
    expect(state.filters.category).toBe("cn_latiao");
    expect(state.filters.market).toBe("");
  });

  it("updates the route transition mode", () => {
    expect(useTradeIntelStore.getState().transitionMode).toBe("book");
    useTradeIntelStore.getState().setTransitionMode("cube");
    expect(useTradeIntelStore.getState().transitionMode).toBe("cube");
    useTradeIntelStore.getState().setTransitionMode("slide-x");
    expect(useTradeIntelStore.getState().transitionMode).toBe("slide-x");
    useTradeIntelStore.getState().setTransitionMode("book");
    expect(useTradeIntelStore.getState().transitionMode).toBe("book");
  });
});
