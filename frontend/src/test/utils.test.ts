import { describe, expect, it } from "vitest";
import { cn, formatNumber } from "@/shared/lib/utils";

describe("shared utils", () => {
  it("merges tailwind classes", () => {
    expect(cn("px-2", "px-3")).toBe("px-3");
  });

  it("formats numbers without breaking empty values", () => {
    expect(formatNumber(1234.56, 1)).toBe("1,234.6");
    expect(formatNumber(null)).toBe("--");
  });
});
