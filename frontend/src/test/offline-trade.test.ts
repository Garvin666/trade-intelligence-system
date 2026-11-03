import { describe, expect, it, vi } from "vitest";
import { fetchTradeDecision } from "@/shared/api/client";

// 强制离线分支：无后端时贸易决策由前端快照计算（F7：汇率不再硬编码 7.1）
vi.mock("@/shared/api/offline", () => ({
  IS_OFFLINE: true,
  getOfflineData: () => null,
}));

describe("offline trade decision fx rate", () => {
  it("uses fx_rate from the offline snapshot when present", async () => {
    vi.stubGlobal(
      "window",
      Object.assign(window, {
        __TRADE_INTEL_OFFLINE__: { fx_rate: 7.2 },
      }),
    );
    const result = await fetchTradeDecision({
      category: "cn_latiao",
      market: "us",
      unit_price_usd: 20,
      procurement_cost_cny: 100,
    });
    expect(result.fx_rate).toBe(7.2);
    // 20*7.2=144，毛利=(144-135)/144=6.25%
    expect(result.margin_pct).toBeCloseTo(6.3, 1);
    expect(result.best_landed_cost_usd).toBeCloseTo(18.75, 2);
    vi.unstubAllGlobals();
  });

  it("falls back to the shared default fx rate when snapshot has none", async () => {
    vi.stubGlobal("window", Object.assign(window, { __TRADE_INTEL_OFFLINE__: {} }));
    const result = await fetchTradeDecision({
      category: "cn_latiao",
      market: "us",
      unit_price_usd: 20,
      procurement_cost_cny: 100,
    });
    // 回退常量 7.15 与后端 src/trade/cost.py 的 DEFAULT_FX_RATE 保持一致
    expect(result.fx_rate).toBe(7.15);
    expect(result.best_landed_cost_usd).toBeCloseTo(18.88, 2);
    vi.unstubAllGlobals();
  });
});
