import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MarketIntelPanel } from "@/features/dashboard/MarketIntelPanel";

vi.mock("@/shared/api/hooks", () => ({
  useMarketIntel: () => ({
    data: {
      rankings: {
        count: 2,
        items: [
          { rank: 1, category: "cn_latiao", market: "us", platform: "amazon_github", title: "Latiao Spicy Strips", score: 4.5, price: 4.9, fallback_used: false },
          { rank: 2, category: "cn_latiao", market: "us", platform: "mock", title: "辣条 演示商品 1", score: 0, fallback_used: true },
        ],
        source_level: "官方免费样例（GitHub 本地缓存）",
        fallback_used: true,
        real_count: 1,
        mock_count: 1,
      },
      risk: { count: 1, items: [{ category: "cn_latiao", market: "us", risk_score: 42, risk_level: "medium" }] },
      cost: { count: 1, items: [{ category: "cn_latiao", market: "us", gross_margin: 31.2, logistics_cost: 4.2, return_rate: 5, ad_cost_index: 12 }] },
      compare: { count: 1, items: [{ market: "us", market_name: "美国", avg_sales_volume: 100, avg_competition_index: 40, avg_price_median: 30, avg_export_value: 20 }] },
      reviews: { count: 0, items: [] },
      exportValue: {
        count: 1,
        items: [{ category: "cn_latiao", market: "", market_name: "中国出口", export_value: 20 }],
        provider: "comtrade",
        period: "2024",
        fallback_used: false,
      },
      competition: { count: 0, items: [] },
      searchTrends: {
        count: 1,
        items: [{ category: "cn_latiao", market: "us", search_trend: 12 }],
        coverage: { requested: 132, real: 10, mock: 56 },
        provider: "pytrends",
        fallback_used: true,
      },
      status: {
        platform_rankings: {
          source_level: "官方免费样例（GitHub 本地缓存）",
          fallback_used: true,
        },
        trends: { coverage: { requested: 132, real: 10, mock: 56 } },
        customs: { period: "2024", provider: "comtrade" },
      },
    },
  }),
}));

describe("MarketIntelPanel", () => {
  it("renders ranking, risk, cost and compare sections", () => {
    render(<MarketIntelPanel filters={{}} />);
    expect(screen.getAllByText("平台榜单").length).toBeGreaterThan(0);
    expect(screen.getByText("Latiao Spicy Strips")).toBeInTheDocument();
    expect(screen.getByText("经营风险")).toBeInTheDocument();
    expect(screen.getByText("成本结构")).toBeInTheDocument();
    expect(screen.getByText("市场对比")).toBeInTheDocument();
    expect(screen.getByText("美国")).toBeInTheDocument();
    expect(screen.getByText("官方免费样例（GitHub 本地缓存）")).toBeInTheDocument();
    expect(screen.getByText("含回退")).toBeInTheDocument();
    expect(screen.getByText("Amazon 样例")).toBeInTheDocument();
    expect(screen.getByText("真实 10 / 模拟 56")).toBeInTheDocument();
    expect(screen.getByText("中国出口 2024 · UN Comtrade")).toBeInTheDocument();
    expect(screen.getByText(/辣条 × 中国出口/)).toBeInTheDocument();
  });
});
