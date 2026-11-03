import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PolicyImpactPanel } from "@/features/trade-decision/PolicyImpactPanel";
import type { PolicyImpactPayload } from "@/shared/api/types";

const mocks = vi.hoisted(() => ({
  transitionNavigate: vi.fn(),
}));

const impactPayload: PolicyImpactPayload = {
  event_code: "us-de-minimis-2025",
  event_title: "美国 de minimis 取消",
  event_description: "低值包裹小额豁免取消",
  market: "us",
  market_name: "美国",
  effective_date: "2025-08-29",
  source: "美国联邦公报（Federal Register，CBP Notice 90 FR 42418）",
  url: "https://www.federalregister.gov/documents/2025/09/02/2025-16802/notice-of-implementation-of-the-presidents-executive-order-14324-suspending-duty-free-de-minimis",
  policy_type: "tariff",
  source_type: "official",
  provider: "federal_register",
  verified: true,
  published_at: "2025-09-02",
  actions: ["转正式清关", "调价"],
  rate_ad_valorem: 1.2,
  min_duty_usd: 100,
  trends_status: {
    available: true,
    generated_at: "2026-08-22T09:49:52+08:00",
    provider: "pytrends",
    fallback_used: true,
    note: "趋势快照已生成，仅作方向性对照，不做因果归因",
  },
  before_date: "2025-08-28",
  after_date: "2025-08-30",
  total_categories: 1,
  affected_count: 1,
  worst: {
    category: "cn_latiao",
    category_name: "辣条",
    market: "us",
    market_name: "美国",
    unit_price_usd: 22,
    tariff_before: 0.06,
    tariff_after: 1.26,
    duty_before: 1.32,
    duty_after: 27.72,
    cost_increase_before: 0,
    cost_increase_after: 112,
    margin_before: 38.45,
    margin_after: -200,
    margin_delta_pct: -238.45,
    risk_before: "low",
    risk_after: "high",
    verdict_before: "Go",
    verdict_after: "No-Go",
    affected: true,
  },
  rows: [
    {
      category: "cn_latiao",
      category_name: "辣条",
      market: "us",
      market_name: "美国",
      unit_price_usd: 22,
      tariff_before: 0.06,
      tariff_after: 1.26,
      duty_before: 1.32,
      duty_after: 27.72,
      cost_increase_before: 0,
      cost_increase_after: 112,
      margin_before: 38.45,
      margin_after: -200,
      margin_delta_pct: -238.45,
      risk_before: "low",
      risk_after: "high",
      verdict_before: "Go",
      verdict_after: "No-Go",
      affected: true,
    },
  ],
};

vi.mock("@/shared/api/hooks", () => ({
  usePolicyEvents: () => ({
    data: {
      count: 1,
      items: [{ code: "us-de-minimis-2025", title: "美国 de minimis 取消", verified: true }],
    },
  }),
  useTradeCatalog: () => ({
    data: {
      data: {
        categories: [{ key: "cn_latiao", label: "辣条" }],
        markets: [{ key: "us", label: "美国" }],
      },
    },
  }),
  usePolicyImpact: () => ({
    data: impactPayload,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/shared/api/offline", () => ({ IS_OFFLINE: false }));
vi.mock("@/widgets/RouteTransition", () => ({
  useTransitionNavigate: () => mocks.transitionNavigate,
}));

describe("PolicyImpactPanel（政策冲击实验室）", () => {
  it("渲染事件、汇总与前后对比表", () => {
    render(<PolicyImpactPanel />);
    expect(screen.getByText("政策冲击实验室")).toBeInTheDocument();
    expect(screen.getAllByText("美国 de minimis 取消").length).toBeGreaterThan(0);
    expect(screen.getByText("波及品类")).toBeInTheDocument();
    expect(screen.getByText("1 / 1")).toBeInTheDocument();
    expect(screen.getByText("辣条")).toBeInTheDocument();
    expect(screen.getByText("Go → No-Go")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /带入决策/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开政策原文" })).toHaveAttribute(
      "href",
      impactPayload.url,
    );
    expect(screen.getByText("联网方向对照")).toBeInTheDocument();
  });
});
