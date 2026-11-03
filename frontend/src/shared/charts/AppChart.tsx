import { useEffect, useRef, type CSSProperties } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";
import { Skeleton } from "@/shared/ui/skeleton";

interface AppChartProps {
  option: EChartsOption;
  height?: number;
  className?: string;
  loading?: boolean;
  empty?: boolean;
  ariaLabel?: string;
}

const chartTheme = {
  color: ["#22D3EE", "#D97706", "#34D399", "#94A3B8", "#7DD3FC"],
  textStyle: { fontFamily: "Manrope Variable, PingFang SC, Microsoft YaHei, sans-serif" },
};

export function AppChart({
  option,
  height = 320,
  className,
  loading = false,
  empty = false,
  ariaLabel = "数据图表",
}: AppChartProps) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, chartTheme);
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(
      {
        backgroundColor: "transparent",
        ...option,
      } as EChartsOption,
      true,
    );
  }, [option]);

  const style: CSSProperties = { height };
  return (
    <div className={className}>
      {loading ? (
        <Skeleton className="w-full" />
      ) : (
        <div
          ref={ref}
          role="img"
          aria-label={ariaLabel}
          className="w-full min-w-0"
          style={style}
        />
      )}
      {empty && (
        <div className="py-8 text-center text-sm text-slate-500">当前筛选下暂无图表数据</div>
      )}
    </div>
  );
}
