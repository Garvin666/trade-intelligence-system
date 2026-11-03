import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import type { ForecastRow, HistoryRow } from "@/shared/api/types";
import { AppChart } from "@/shared/charts/AppChart";
import { modelName } from "@/shared/lib/names";

interface ForecastChartProps {
  history: HistoryRow[];
  forecast: ForecastRow[];
  modelsOrder?: string[];
  primaryModel?: string;
}

const MODEL_COLORS: Record<string, string> = {
  prophet_baseline: "#F59E0B",
  lightgbm_advanced: "#22D3EE",
};

const MODEL_BAND_COLORS: Record<string, string> = {
  prophet_baseline: "rgba(245,158,11,.10)",
  lightgbm_advanced: "rgba(34,211,238,.10)",
};

export function buildForecastOption(
  history: HistoryRow[],
  forecast: ForecastRow[],
  options: { modelsOrder?: string[]; primaryModel?: string } = {},
): EChartsOption {
  const histRows = [...history].sort((a, b) => a.date.localeCompare(b.date));
  const fcRows = [...forecast].sort((a, b) => a.date.localeCompare(b.date));
  const histByDate = new Map(histRows.map((row) => [row.date, row]));
  const fcByModel = new Map<string, ForecastRow[]>();
  for (const row of fcRows) {
    const group = fcByModel.get(row.model) ?? [];
    group.push(row);
    fcByModel.set(row.model, group);
  }
  const modelCodes = (options.modelsOrder ?? []).filter((model) =>
    fcByModel.has(model),
  );
  for (const model of fcByModel.keys()) {
    if (!modelCodes.includes(model)) modelCodes.push(model);
  }
  const dates = Array.from(
    new Set([...histByDate.keys(), ...fcRows.map((row) => row.date)]),
  ).sort((a, b) => a.localeCompare(b));
  const historyData = dates.map((date) => histByDate.get(date)?.sales_volume ?? null);

  const series: EChartsOption["series"] = [
    {
      name: "历史销量",
      type: "line",
      data: historyData,
      smooth: true,
      symbol: "none",
      lineStyle: { color: "#94A3B8", width: 2 },
      itemStyle: { color: "#94A3B8" },
    },
  ];
  const legendData = ["历史销量"];
  for (const model of modelCodes) {
    const rows = fcByModel.get(model) ?? [];
    const fcByDate = new Map(rows.map((row) => [row.date, row]));
    const lowerData = dates.map((date) => fcByDate.get(date)?.yhat_lower ?? null);
    const bandData = dates.map((date) => {
      const row = fcByDate.get(date);
      return row ? row.yhat_upper - row.yhat_lower : null;
    });
    const forecastData = dates.map((date) => fcByDate.get(date)?.yhat ?? null);
    const color = MODEL_COLORS[model] ?? "#22D3EE";
    const isPrimary = model === options.primaryModel;
    const shortName =
      model === "prophet_baseline"
        ? "Prophet"
        : model === "lightgbm_advanced"
          ? "LightGBM"
          : modelName(model);
    const label = `${shortName} 预测`;
    legendData.push(label);
    series.push(
      {
        name: `${modelName(model)} 下界`,
        type: "line",
        data: lowerData,
        stack: `confidence-${model}`,
        symbol: "none",
        lineStyle: { opacity: 0 },
        tooltip: { show: false },
      },
      {
        name: `${modelName(model)} 区间`,
        type: "line",
        data: bandData,
        stack: `confidence-${model}`,
        symbol: "none",
        lineStyle: { opacity: 0 },
        tooltip: { show: false },
        areaStyle: { color: MODEL_BAND_COLORS[model] ?? "rgba(34,211,238,.10)" },
      },
      {
        name: label,
        type: "line",
        data: forecastData,
        smooth: true,
        symbol: "none",
        lineStyle: {
          color,
          width: isPrimary ? 3 : 2,
          type: isPrimary ? "solid" : "dashed",
        },
        itemStyle: { color },
      },
    );
  }

  return {
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(10,18,32,.92)",
      borderColor: "rgba(255,255,255,.12)",
      textStyle: { color: "#E8EEF6" },
    },
    legend: { top: 0, data: legendData, textStyle: { color: "#8FA3B8" } },
    grid: { left: 8, right: 12, top: 40, bottom: 8, containLabel: true },
    xAxis: {
      type: "category",
      data: dates,
      axisLine: { lineStyle: { color: "rgba(148,163,184,.2)" } },
      axisLabel: { color: "#8FA3B8", hideOverlap: true },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "rgba(148,163,184,.12)" } },
      axisLabel: { color: "#8FA3B8" },
    },
    series,
  };
}

export function ForecastChart({
  history,
  forecast,
  modelsOrder,
  primaryModel,
}: ForecastChartProps) {
  const option = useMemo(
    () => buildForecastOption(history, forecast, { modelsOrder, primaryModel }),
    [history, forecast, modelsOrder, primaryModel],
  );

  return (
    <AppChart
      option={option}
      height={320}
      empty={fcEmpty(forecast)}
      ariaLabel="销售预测图"
    />
  );
}

function fcEmpty(forecast: ForecastRow[]): boolean {
  return forecast.length === 0;
}
