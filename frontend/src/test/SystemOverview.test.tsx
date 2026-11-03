import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SystemOverview } from "@/features/system/SystemOverview";

vi.mock("@/shared/api/hooks", () => ({
  useSystemStatus: () => ({
    data: {
      health: { status: "ok", jobs: { items: [] } },
      engineering: {
        test_count: 414,
        test_passed: 414,
        capabilities: {
          policy_cost: { status: "ready" },
          compliance: { status: "ready" },
        },
      },
      systemEval: {
        gate: { passed: false, failed_metrics: ["ranking", "robustness"] },
        system_eval: { pass: { ranking: false, robustness: false } },
        model_summary: {},
      },
      suppliers: { rows: [] },
    },
    isLoading: false,
    isError: false,
  }),
  useRefreshPolicy: () => ({
    isPending: false,
    isSuccess: false,
    data: null,
    mutate: vi.fn(),
  }),
}));

vi.mock("@/shared/api/offline", () => ({ IS_OFFLINE: false }));

describe("SystemOverview evaluation gate", () => {
  it("shows an explicit warning when acceptance metrics fail", () => {
    render(<SystemOverview />);
    expect(screen.getByText(/评测门禁未通过/)).toBeInTheDocument();
    expect(screen.getByText(/ranking、robustness/)).toBeInTheDocument();
    expect(screen.getByText("414 / 414 通过")).toBeInTheDocument();
  });
});
