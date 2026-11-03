import { describe, expect, it } from "vitest";
import { DEMO_STAGES } from "@/features/demo/DEMO_STAGES";

describe("demo stages", () => {
  it("keeps seven complete pipeline stages", () => {
    expect(DEMO_STAGES).toHaveLength(7);
    const ids = DEMO_STAGES.map((stage) => stage.id);
    expect(new Set(ids).size).toBe(ids.length);
    DEMO_STAGES.forEach((stage) => {
      expect(stage.label).toBeTruthy();
      expect(stage.description).toBeTruthy();
      expect(stage.metric).toBeTruthy();
    });
  });
});
