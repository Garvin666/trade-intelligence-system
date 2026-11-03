import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EvidenceLedgerPanel } from "@/features/trade-decision/EvidenceLedgerPanel";

vi.mock("@/shared/api/hooks", () => ({
  useEvidenceLedger: () => ({
    data: {
      schema_version: 1,
      count: 2,
      expired_count: 0,
      items: [
        {
          key: "us-de-minimis-2025",
          title: "美国 de minimis 取消",
          source: "白宫",
          fetched_at: "2025-08-20T00:00:00",
          effective_date: "2025-08-29",
          expires_at: "2026-08-29",
          validity_days: 365,
          hs_version: null,
          formula: "政策事件 → 有效税率 / 到岸成本 / 风险等级",
          model_version: null,
          confidence_interval: null,
          review_status: "已核实",
          url: "https://example.com/order",
          status: "已核实",
          expiry_status: { status: "expiring_soon", days_left: 8, message: "即将过期" },
        },
        {
          key: "3924.20",
          title: "HS6 3924.20 塑料制餐具",
          source: "本地 Harmonized System 数据集",
          fetched_at: null,
          effective_date: null,
          expires_at: null,
          validity_days: null,
          hs_version: "HS2022",
          formula: "HS6 子目速查",
          model_version: null,
          confidence_interval: null,
          review_status: "已核实",
          url: null,
          status: "已核实",
          expiry_status: { status: "no_expiry", days_left: null, message: "长期有效" },
        },
      ],
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/shared/api/offline", () => ({ IS_OFFLINE: false }));

describe("EvidenceLedgerPanel（证据账本）", () => {
  it("渲染记录数、过期状态、HS 版本与来源", () => {
    render(<EvidenceLedgerPanel />);
    expect(screen.getByText("证据账本")).toBeInTheDocument();
    expect(screen.getByText("2 条记录")).toBeInTheDocument();
    expect(screen.getByText("无过期记录")).toBeInTheDocument();
    expect(screen.getByText("美国 de minimis 取消")).toBeInTheDocument();
    expect(screen.getByText("即将过期")).toBeInTheDocument();
    expect(screen.getByText("HS2022")).toBeInTheDocument();
    expect(screen.getAllByText("长期有效").length).toBeGreaterThan(0);
  });
});
