import { Activity, Compass, Gauge, Layers } from "lucide-react";
import type { DashboardData } from "@/shared/api/types";
import { average, categoryOptions, marketOptions } from "@/entities/dashboard/model";
import { formatNumber, formatPercent } from "@/shared/lib/utils";
import { GlassCard } from "@/shared/ui/glass-card";
import { KpiValue } from "@/shared/ui/data";
import { cn } from "@/shared/lib/utils";

const iconTone: Record<string, string> = {
  cyan: "text-accent",
  amber: "text-amber-300",
  green: "text-emerald-300",
};

export function MetricsGrid({ data }: { data?: DashboardData }) {
  const categories = categoryOptions(data).length;
  const markets = marketOptions(data).length;
  const baseline = average((data?.metrics.baseline ?? []).map((item) => item.mape));
  const advanced = average((data?.metrics.advanced ?? []).map((item) => item.mape));
  const improvement = baseline > 0 ? ((baseline - advanced) / baseline) * 100 : 0;

  const latest = data?.history?.reduce(
    (acc, row) => (row.date > acc ? row.date : acc),
    "",
  );
  const latestRows = latest
    ? (data?.history ?? []).filter((row) => row.date === latest)
    : [];
  const latestAvgSales = average(latestRows.map((row) => row.sales_volume));

  const items = [
    {
      label: "覆盖品类",
      value: String(categories),
      hint: `覆盖 ${categories} 个在库品类`,
      icon: Layers,
      tone: "cyan",
    },
    {
      label: "目标市场",
      value: String(markets),
      hint: `覆盖 ${markets} 个核心市场`,
      icon: Compass,
      tone: "amber",
    },
    {
      label: "最新销量指数",
      value: formatNumber(latestAvgSales),
      hint: latest ? `截至 ${latest}` : "暂无",
      icon: Activity,
      tone: "green",
    },
    {
      label: "模型精度提升",
      value: formatPercent(improvement),
      hint: "LightGBM 相对 Prophet 基线",
      icon: Gauge,
      tone: "cyan",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <GlassCard key={item.label} className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-slate-400">{item.label}</p>
              <KpiValue className="mt-1" value={item.value} />
              <p className="mt-1 truncate text-[11px] text-slate-500">{item.hint}</p>
            </div>
            <div
              className={cn(
                "glass-inset flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
                iconTone[item.tone] ?? "text-accent",
              )}
            >
              <item.icon className="h-5 w-5" />
            </div>
          </div>
        </GlassCard>
      ))}
    </div>
  );
}
