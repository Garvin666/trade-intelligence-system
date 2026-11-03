import { describe, expect, it } from "vitest";
import { isMockSource } from "@/features/four-brain/FourBrainPanel";

describe("isMockSource", () => {
  it("recognizes legal-crawler mock results", () => {
    expect(isMockSource({ source: "mock" })).toBe(true);
    expect(isMockSource({ title: "Mock result for pet feeder" })).toBe(true);
    expect(isMockSource({ source: "wikimedia_search" })).toBe(false);
    expect(isMockSource({ title: "Pet feeder market" })).toBe(false);
  });
});
