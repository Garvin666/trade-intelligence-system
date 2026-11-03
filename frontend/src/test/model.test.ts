import { describe, expect, it } from "vitest";
import {
  bestForecastModel,
  dashboardExampleFilters,
  filterDashboardData,
  filterRecommendations,
  recommendableTop,
} from "@/entities/dashboard/model";
import type { DashboardData } from "@/shared/api/types";

const base: DashboardData = {
  categories: { pet: "辣条" },
  markets: { us: "美国" },
  models: { lightgbm_advanced: "LightGBM" },
  models_order: ["lightgbm_advanced"],
  history: [
    { date: "2026-08-01", category: "cn_latiao", market: "us", search_index: 10, bestseller_rank: 2, price_median: 20, review_growth: 1, export_value: 5, competition_index: 3, sales_volume: 50 },
    { date: "2026-08-01", category: "cn_longjing", market: "us", search_index: 10, bestseller_rank: 2, price_median: 20, review_growth: 1, export_value: 5, competition_index: 3, sales_volume: 60 },
  ],
  forecast: [
    { date: "2026-08-02", category: "cn_latiao", market: "us", model: "lightgbm_advanced", yhat: 55, yhat_lower: 52, yhat_upper: 58 },
  ],
  recommendations: [
    { rank: 1, category: "cn_latiao", market: "us", score: 80, six_dimension_score: 75, verdict: "Go", decision_reason: "", dimension_demand: 1, dimension_trend: 1, dimension_competition: 1, dimension_margin: 1, dimension_compliance: 1, dimension_evidence: 1, evidence_missing: false, forecast_growth: 10, search_trend: 5, competition: 20, review_growth: 2, reasons: "" },
  ],
  metrics: {
    baseline: [{ category: "cn_latiao", market: "us", model: "prophet", mape: 4, mae: 2 }],
    advanced: [{ category: "cn_latiao", market: "us", model: "lgb", mape: 2, mae: 1 }],
    statsforecast: [],
  },
  trade: {},
  policy_events: [],
  policy_candidates: [],
  policy_snapshot: {},
  analysis: {},
  crawler: {},
  data_status: { generated_at: "", data_as_of: "" },
};

describe("dashboard model", () => {
  it("filters history by category and market", () => {
    const filtered = filterDashboardData(base, { category: "cn_latiao", market: "us" });
    expect(filtered.history).toHaveLength(1);
    expect(filtered.history[0].category).toBe("cn_latiao");
  });

  it("keeps recommendations when filters match", () => {
    const filtered = filterDashboardData(base, { category: "cn_latiao", market: "us" });
    expect(filtered.recommendations).toHaveLength(1);
  });

  it("sorts by six_dimension_score, drops No-Go rows and renumbers rank", () => {
    // 输入模拟后端候选池（services.py: 六维分 → 增长 → 趋势 → 字典序），前端统一重排
    const rows = [
      { ...base.recommendations[0], category: "cn_longjing", market: "us", rank: 3, verdict: "Go", six_dimension_score: 70 },
      { ...base.recommendations[0], category: "cn_latiao", market: "us", rank: 5, verdict: "Conditional", six_dimension_score: 82 },
      { ...base.recommendations[0], category: "cn_longjing", market: "us", rank: 99, verdict: "No-Go", six_dimension_score: 90 },
    ];
    const top = recommendableTop(rows);
    expect(top.map((row) => row.category)).toEqual(["cn_latiao", "cn_longjing"]);
    expect(top.map((row) => row.rank)).toEqual([1, 2]);
  });

  it("returns global top recommendations regardless of filters", () => {
    const rows = [
      { ...base.recommendations[0], category: "cn_latiao", market: "us", six_dimension_score: 75 },
      { ...base.recommendations[0], category: "cn_longjing", market: "us", six_dimension_score: 80 },
    ];
    const filtered = filterRecommendations(rows, { category: "cn_latiao", market: "us" });
    expect(filtered.map((row) => row.category)).toEqual(["cn_longjing", "cn_latiao"]);
  });
});

describe("dashboard examples", () => {
  it("resolves category/market filters from an example id", () => {
    const examples = [
      { id: "cn_latiao_us", label: "辣条 × 美国", category: "cn_latiao", market: "us" },
      { id: "cn_longjing_eu", label: "西湖龙井 × 欧洲", category: "cn_longjing", market: "eu" },
    ];
    expect(dashboardExampleFilters(examples, "cn_longjing_eu")).toEqual({
      category: "cn_longjing",
      market: "eu",
    });
    expect(dashboardExampleFilters(examples, "missing")).toBeNull();
  });
});

describe("bestForecastModel", () => {
  const metrics = {
    baseline: [
      { category: "cn_latiao", market: "us", model: "prophet_baseline", mape: 4, mae: 2 },
      { category: "cn_latiao", market: "eu", model: "prophet_baseline", mape: 3, mae: 2 },
    ],
    advanced: [
      { category: "cn_latiao", market: "us", model: "lightgbm_advanced", mape: 2, mae: 1 },
      { category: "cn_latiao", market: "eu", model: "lightgbm_advanced", mape: 5, mae: 3 },
    ],
    statsforecast: [],
  };

  it("picks the lower-MAPE model for an exact combo", () => {
    expect(bestForecastModel(metrics, "cn_latiao", "us")).toBe("lightgbm_advanced");
    expect(bestForecastModel(metrics, "cn_latiao", "eu")).toBe("prophet_baseline");
  });

  it("averages filtered rows when no exact combo is selected", () => {
    expect(bestForecastModel(metrics, "cn_latiao")).toBe("prophet_baseline");
    expect(bestForecastModel(metrics)).toBe("prophet_baseline");
  });

  it("falls back to LightGBM when MAPE is missing", () => {
    const missing = {
      baseline: [{ category: "cn_latiao", market: "us", model: "prophet_baseline", mape: Number.NaN, mae: 2 }],
      advanced: [],
      statsforecast: [],
    };
    expect(bestForecastModel(missing, "cn_latiao", "us")).toBe("lightgbm_advanced");
    expect(bestForecastModel(undefined)).toBe("lightgbm_advanced");
  });
});
