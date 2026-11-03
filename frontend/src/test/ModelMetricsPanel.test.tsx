import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ModelMetricsPanel } from "@/features/dashboard/ModelMetricsPanel";

let mockBusinessMetrics: Record<string, unknown> | undefined;

vi.mock("@/shared/api/hooks", () => ({
  useModelMetrics: () => ({
    data: {
      baseline: [{ category: "cn_latiao", market: "us", model: "prophet_baseline", mape: 0.1135, mae: 4.2 }],
      advanced: [],
      statsforecast: [],
      business_metrics: mockBusinessMetrics,
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/shared/api/offline", () => ({ IS_OFFLINE: false }));

describe("ModelMetricsPanel（回测业务指标）", () => {
  beforeEach(() => {
    mockBusinessMetrics = {
      scope: { combos: 1980, prediction_points: 23760 },
      calibration: {
        status: "ok",
        mape_pct: 11.354,
        interval_coverage_pct: 50.78,
        interval_nominal_pct: 80.0,
      },
      direction_hit_rate: {
        status: "ok",
        hit_rate_pct: 66.52,
        up_hit_rate_pct: 44.08,
        down_hit_rate_pct: 85.45,
      },
      topn_posterior_return: {
        status: "ok",
        top_n: 10,
        horizon_days: 90,
        rows: [
          {
            rank: 1,
            category: "intl_plant_burger",
            market: "vn",
            realized_growth_pct: 11.05,
            forecast_growth_pct: 20.59,
            posterior_return_90d_usd: 31086.28,
          },
        ],
      },
      inventory_loss: {
        status: "ok",
        aggregates: {
          total_loss_annual_usd: 3517589.4,
          avg_loss_annual_per_combo_usd: 3553.12,
        },
      },
    };
  });

  it("渲染校准度、方向命中率、Top-N 后验收益与库存损失", () => {
    render(<ModelMetricsPanel filters={{}} />);
    expect(screen.getByText("业务指标（回测后验）")).toBeInTheDocument();
    expect(screen.getByText("预测校准度")).toBeInTheDocument();
    expect(screen.getByText("方向命中率")).toBeInTheDocument();
    expect(screen.getByText("Top-N 后验收益")).toBeInTheDocument();
    expect(screen.getByText("库存损失估算")).toBeInTheDocument();
    expect(screen.getByText("66.5%")).toBeInTheDocument();
    expect(screen.getByText("植物汉堡排 × 越南")).toBeInTheDocument();
    expect(screen.getAllByText("$31,086").length).toBeGreaterThan(0);
  });

  it("缺少回测指标时显示占位", () => {
    mockBusinessMetrics = undefined;
    render(<ModelMetricsPanel filters={{}} />);
    expect(screen.getByText("未生成回测业务指标，请先运行 scripts/rolling_backtest.py。")).toBeInTheDocument();
  });
});
