import { describe, expect, it } from "vitest";
import type { EChartsOption } from "echarts";
import { buildForecastOption } from "@/features/dashboard/ForecastChart";
import type { ForecastRow, HistoryRow } from "@/shared/api/types";

const history: HistoryRow[] = [
  {
    date: "2026-08-15",
    category: "cn_latiao",
    market: "us",
    search_index: 10,
    bestseller_rank: 2,
    price_median: 20,
    review_growth: 1,
    export_value: 5,
    competition_index: 3,
    sales_volume: 50,
  },
];

const forecast: ForecastRow[] = [
  {
    date: "2026-08-16",
    category: "cn_latiao",
    market: "us",
    model: "lightgbm_advanced",
    yhat: 55,
    yhat_lower: 52,
    yhat_upper: 58,
  },
];

const prophetForecast: ForecastRow = {
  date: "2026-08-16",
  category: "cn_latiao",
  market: "us",
  model: "prophet_baseline",
  yhat: 53,
  yhat_lower: 50,
  yhat_upper: 56,
};

function seriesData(option: EChartsOption, name: string): Array<number | null> {
  const series = option.series as Array<{
    name?: string;
    data?: Array<number | null>;
  }>;
  return series.find((item) => item.name === name)?.data ?? [];
}

function legendData(option: EChartsOption): string[] {
  const legend = option.legend as { data?: string[] } | Array<{ data?: string[] }>;
  return (Array.isArray(legend) ? legend[0]?.data : legend?.data) ?? [];
}

function seriesLine(
  option: EChartsOption,
  name: string,
): { width?: number; type?: string } {
  const series = option.series as Array<{
    name?: string;
    lineStyle?: { width?: number; type?: string };
  }>;
  return series.find((item) => item.name === name)?.lineStyle ?? {};
}

describe("ForecastChart", () => {
  it("aligns forecast after history instead of the chart start", () => {
    const option = buildForecastOption(history, forecast, {
      modelsOrder: ["prophet_baseline", "lightgbm_advanced"],
      primaryModel: "lightgbm_advanced",
    });
    const xAxis = option.xAxis as { data?: string[] } | Array<{ data?: string[] }>;
    const axisData = Array.isArray(xAxis) ? xAxis[0].data : xAxis?.data;
    expect(axisData).toEqual(["2026-08-15", "2026-08-16"]);
    expect(seriesData(option, "历史销量")).toEqual([50, null]);
    expect(seriesData(option, "LightGBM 预测")).toEqual([null, 55]);
    expect(seriesData(option, "LightGBM 进阶 下界")).toEqual([null, 52]);
    expect(legendData(option)).toEqual(["历史销量", "LightGBM 预测"]);
  });

  it("renders both model curves without overwriting same dates", () => {
    const option = buildForecastOption(
      history,
      [prophetForecast, ...forecast],
      {
        modelsOrder: ["prophet_baseline", "lightgbm_advanced"],
        primaryModel: "lightgbm_advanced",
      },
    );
    expect(legendData(option)).toEqual([
      "历史销量",
      "Prophet 预测",
      "LightGBM 预测",
    ]);
    expect(seriesData(option, "Prophet 预测")).toEqual([null, 53]);
    expect(seriesData(option, "LightGBM 预测")).toEqual([null, 55]);
    expect(seriesData(option, "Prophet 基线 下界")).toEqual([null, 50]);
    expect(seriesData(option, "LightGBM 进阶 区间")).toEqual([null, 6]);
    expect(seriesLine(option, "LightGBM 预测")).toMatchObject({
      width: 3,
      type: "solid",
    });
    expect(seriesLine(option, "Prophet 预测")).toMatchObject({
      width: 2,
      type: "dashed",
    });
  });
});
