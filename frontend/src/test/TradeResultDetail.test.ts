import { describe, expect, it } from "vitest";
import { showValue, UNFETCHED } from "@/features/trade-decision/TradeResultDetail";

describe("TradeResultDetail 占位语义化（N-F4）", () => {
  it("null / undefined 统一为未取到", () => {
    expect(showValue(null)).toBe(UNFETCHED);
    expect(showValue(undefined)).toBe(UNFETCHED);
  });

  it("后端占位符（-- 或空串）统一为未取到，避免答辩误读", () => {
    expect(showValue("--")).toBe(UNFETCHED);
    expect(showValue("")).toBe(UNFETCHED);
  });

  it("真实值原样返回", () => {
    expect(showValue(65.2)).toBe("65.2");
    expect(showValue("attention")).toBe("attention");
    expect(showValue(0)).toBe("0");
  });
});
