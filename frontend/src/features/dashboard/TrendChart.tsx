import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import type { HistoryRow } from "@/shared/api/types";
import { AppChart } from "@/shared/charts/AppChart";

function scale(values: number[]): number[] {
  const max = Math.max(...values);
  const min = Math.min(...values);
  if (max === min) return values.map(() => 50);
  return values.map((value) => ((value - min) / (max - min)) * 100);
}

export function TrendChart({ rows }: { rows: HistoryRow[] }) {
  const option = useMemo<EChartsOption>(() => {
    const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date));
    const dates = sorted.map((row) => row.date);
    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(10,18,32,.92)",
        borderColor: "rgba(255,255,255,.12)",
        textStyle: { color: "#E8EEF6" },
      },
      legend: {
        top: 0,
        textStyle: { color: "#8FA3B8" },
        itemWidth: 14,
      },
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
      series: [
        {
          name: "销量指数",
          type: "line",
          smooth: true,
          symbol: "none",
          data: scale(sorted.map((row) => row.sales_volume)),
          lineStyle: { width: 2.4, color: "#22D3EE" },
          itemStyle: { color: "#22D3EE" },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(34,211,238,.24)" },
                { offset: 1, color: "rgba(34,211,238,0)" },
              ],
            },
          },
        },
        {
          name: "搜索热度",
          type: "line",
          smooth: true,
          symbol: "none",
          data: scale(sorted.map((row) => row.search_index)),
          lineStyle: { width: 1.8, color: "#F59E0B", type: "dashed" },
          itemStyle: { color: "#F59E0B" },
        },
        {
          name: "出口金额",
          type: "line",
          smooth: true,
          symbol: "none",
          data: scale(sorted.map((row) => row.export_value)),
          lineStyle: { width: 1.8, color: "#34D399", type: "dotted" },
          itemStyle: { color: "#34D399" },
        },
      ],
    };
  }, [rows]);

  return (
    <AppChart
      option={option}
      height={320}
      loading={false}
      empty={rows.length === 0}
      ariaLabel="多源热度趋势图"
    />
  );
}
