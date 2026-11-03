import { useMemo, useState } from "react";
import type { EChartsOption } from "echarts";
import { Pause, Play, RotateCcw } from "lucide-react";
import type { ForecastRow, HistoryRow } from "@/shared/api/types";
import { AppChart } from "@/shared/charts/AppChart";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { useDemoPlayback } from "./useDemoPlayback";

interface LiveMarketChartProps {
  history: HistoryRow[];
  forecast: ForecastRow[];
  autoStart?: boolean;
}

const SPEEDS = [1, 2, 4] as const;

export function LiveMarketChart({
  history,
  forecast,
  autoStart = false,
}: LiveMarketChartProps) {
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const sortedHistory = useMemo(
    () => [...history].sort((a, b) => a.date.localeCompare(b.date)),
    [history],
  );
  const sortedForecast = useMemo(
    () => [...forecast].sort((a, b) => a.date.localeCompare(b.date)),
    [forecast],
  );
  const total = sortedHistory.length + sortedForecast.length;
  const { playing, tick, play, pause, reset } = useDemoPlayback({
    stageCount: Math.max(total, 1),
    intervalMs: 800 / speed,
    autoStart,
  });
  const cursor = total > 0 ? tick % total : 0;

  const option = useMemo<EChartsOption>(() => {
    const dates = [
      ...sortedHistory.map((row) => row.date),
      ...sortedForecast.map((row) => row.date),
    ];
    const currentDate = dates[cursor] ?? dates.at(-1) ?? "";
    const visibleDates = dates.slice(0, Math.max(8, cursor + 1));
    const historyData = sortedHistory.map((row, index) =>
      index < visibleDates.length ? row.sales_volume : null,
    );
    const forecastData = sortedForecast.map((row, index) => {
      const pointIndex = sortedHistory.length + index;
      return pointIndex < visibleDates.length ? row.yhat : null;
    });
    return {
      animation: true,
      animationDuration: 400,
      animationDurationUpdate: 300,
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(10,18,32,.92)",
        borderColor: "rgba(255,255,255,.12)",
        textStyle: { color: "#E8EEF6" },
      },
      legend: { top: 0, textStyle: { color: "#8FA3B8" } },
      grid: { left: 8, right: 12, top: 40, bottom: 8, containLabel: true },
      xAxis: {
        type: "category",
        data: visibleDates,
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
          data: historyData,
          smooth: true,
          symbol: "none",
          lineStyle: { color: "#94A3B8", width: 2 },
          itemStyle: { color: "#94A3B8" },
          markLine:
            currentDate && visibleDates.includes(currentDate)
              ? {
                  symbol: "none",
                  data: [{ xAxis: currentDate }],
                  lineStyle: { color: "#F59E0B", width: 1.5, type: "dashed" },
                  label: { show: false },
                }
              : undefined,
        },
        {
          name: "预测销量",
          type: "line",
          data: forecastData,
          smooth: true,
          symbol: "none",
          lineStyle: { color: "#22D3EE", width: 2.4 },
          itemStyle: { color: "#22D3EE" },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(34,211,238,.22)" },
                { offset: 1, color: "rgba(34,211,238,0)" },
              ],
            },
          },
        },
      ],
    };
  }, [sortedHistory, sortedForecast, cursor]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white">动态刷新市场图表</h2>
          <p className="mt-1 text-xs text-slate-400">滚动时间窗播放历史与预测曲线</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={playing ? pause : play}
            aria-label={playing ? "暂停图表" : "播放图表"}
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </Button>
          <Button variant="ghost" size="sm" onClick={reset} aria-label="重置图表">
            <RotateCcw className="h-4 w-4" />
          </Button>
          <div className="glass-inset flex rounded-lg p-0.5">
            {SPEEDS.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setSpeed(value)}
                className={cn(
                  "focus-ring rounded-md px-2.5 py-1 font-mono text-[11px] font-bold text-slate-500 transition-colors",
                  speed === value && "bg-cyan-400/15 text-accent",
                )}
                aria-pressed={speed === value}
              >
                {value}x
              </button>
            ))}
          </div>
        </div>
      </div>
      <AppChart
        option={option}
        height={300}
        empty={total === 0}
        ariaLabel="动态市场趋势图"
      />
    </div>
  );
}
