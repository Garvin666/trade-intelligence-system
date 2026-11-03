import { useMemo, useState } from "react";
import {
  ArrowRight,
  ExternalLink,
  Ship,
  TriangleAlert,
} from "lucide-react";
import { usePolicyEvents, usePolicyImpact, useTradeCatalog } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import type { PolicyImpactPayload, PolicyImpactRow } from "@/shared/api/types";
import { marketName } from "@/shared/lib/names";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { Select } from "@/shared/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { useTransitionNavigate } from "@/widgets/RouteTransition";

function verdictTone(verdict: string): "green" | "amber" | "red" {
  if (verdict.toLowerCase().includes("go")) return "green";
  if (verdict.toLowerCase().includes("no")) return "red";
  return "amber";
}

export function PolicyImpactPanel() {
  const transitionNavigate = useTransitionNavigate();
  const setSelectionDraft = useTradeIntelStore((state) => state.setSelectionDraft);
  const { data: eventsData } = usePolicyEvents();
  const { data: catalog } = useTradeCatalog();
  const [eventCode, setEventCode] = useState("");
  const [category, setCategory] = useState("");
  const [market, setMarket] = useState("");

  const events = useMemo(
    () =>
      ((eventsData?.items ?? []) as Array<{
        code?: string;
        title?: string;
        verified?: boolean;
      }>).filter((event) => event.code),
    [eventsData],
  );

  const defaultEventCode =
    events.find((event) => event.verified)?.code ?? events[0]?.code ?? "";
  const activeEventCode = eventCode || defaultEventCode;

  const categoryOptions = useMemo(() => {
    const items = catalog?.data?.categories ?? [];
    const mapped = items
      .filter((item) => item.key)
      .map((item) => ({ value: item.key, label: String(item.label ?? item.key) }));
    return [{ value: "", label: "全部品类" }, ...mapped];
  }, [catalog]);

  const marketOptions = useMemo(() => {
    const items = catalog?.data?.markets ?? [];
    const mapped = items
      .filter((item) => item.key)
      .map((item) => ({ value: item.key, label: String(item.label ?? marketName(item.key)) }));
    return [{ value: "", label: "事件市场" }, ...mapped];
  }, [catalog]);

  const { data, isLoading, isError } = usePolicyImpact(
    {
      event_code: activeEventCode,
      category: category || undefined,
      market: market || undefined,
    },
    Boolean(activeEventCode),
  );

  const enterTrade = (row: PolicyImpactRow) => {
    setSelectionDraft({
      label: `${row.category_name} × ${row.market_name ?? marketName(row.market)}`,
      keyword: row.category_name,
      category: row.category,
      market: row.market,
      price: row.unit_price_usd,
      procurement_cost_cny: Math.round(row.unit_price_usd * 7.2 * 0.35),
    });
    transitionNavigate("/trade");
  };

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">
          政策冲击实验室需要在线后端读取本地政策事件，离线模式不可用。
        </p>
      </GlassCard>
    );
  }

  return (
    <div className="grid gap-4">
      <GlassCard title="政策冲击实验室" description="政策生效日前/后的有效税率、关税、利润与 Go/No-Go 判定对比" strong>
        <div className="grid gap-3 sm:grid-cols-[1fr_220px_180px] sm:items-end">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">政策事件</span>
            <Select
              value={activeEventCode}
              onValueChange={setEventCode}
              options={events.map((event) => ({
                value: String(event.code ?? ""),
                label: String(event.title ?? event.code ?? ""),
              }))}
              ariaLabel="选择政策事件"
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">品类</span>
            <Select
              value={category}
              onValueChange={setCategory}
              options={categoryOptions}
              ariaLabel="选择品类"
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">市场</span>
            <Select
              value={market}
              onValueChange={setMarket}
              options={marketOptions}
              ariaLabel="选择市场"
            />
          </label>
        </div>
      </GlassCard>

      {isError && (
        <GlassCard>
          <p className="text-sm text-red-300">政策冲击数据加载失败，请确认后端已启动。</p>
        </GlassCard>
      )}

      {isLoading && !data && (
        <GlassCard>
          <div className="h-24 animate-pulse rounded-lg bg-white/5" />
        </GlassCard>
      )}

      {data && <ImpactSummary data={data} />}
      {data && <ImpactTable data={data} onEnterTrade={enterTrade} />}
    </div>
  );
}

function ImpactSummary({ data }: { data: PolicyImpactPayload }) {
  return (
    <div className="grid gap-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="波及品类"
          value={`${data.affected_count} / ${data.total_categories}`}
          tone={data.affected_count > 0 ? "amber" : "green"}
        />
        <Stat
          label="最差利润冲击"
          value={data.worst ? `${data.worst.margin_delta_pct.toFixed(1)} pp` : "无变化"}
          tone="red"
        />
        <Stat label="生效日" value={data.effective_date} tone="cyan" mono />
        <div className="glass-inset flex min-w-0 items-center justify-between gap-2 p-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-slate-500">来源</p>
            <p className="mt-1 truncate text-xs font-bold text-white">{data.source ?? "--"}</p>
          </div>
          {data.url ? (
            <a
              href={data.url}
              target="_blank"
              rel="noreferrer"
              className="focus-ring shrink-0 rounded-lg p-1.5 text-slate-400 hover:text-accent"
              aria-label="打开政策原文"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          ) : (
            <span className="shrink-0 rounded-lg px-1.5 py-1 text-[11px] text-slate-500">
              暂无官方原文链接
            </span>
          )}
        </div>
      </div>
      {data.trends_status && (
        <div className="glass-inset flex min-w-0 items-center justify-between gap-3 p-3">
          <p className="text-[11px] font-semibold text-slate-500">联网方向对照</p>
          <p className="min-w-0 text-right text-xs text-slate-300">
            {data.trends_status.available
              ? `${data.trends_status.generated_at ?? "已生成"} · ${data.trends_status.provider ?? "未知 provider"}${
                  data.trends_status.fallback_used ? " · fallback" : ""
                }`
              : data.trends_status.note ?? "不可用"}
          </p>
        </div>
      )}
    </div>
  );
}

function ImpactTable({
  data,
  onEnterTrade,
}: {
  data: PolicyImpactPayload;
  onEnterTrade: (row: PolicyImpactRow) => void;
}) {
  return (
    <GlassCard
      title={`${data.event_title}`}
      description={`${data.market_name ?? data.market} · ${data.before_date ?? "--"} → ${data.after_date ?? "--"} · 本地政策事件与成本模型离线测算口径`}
    >
      <div className="max-h-[520px] overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>品类</TableHead>
              <TableHead className="text-right">有效税率</TableHead>
              <TableHead className="text-right">单件关税</TableHead>
              <TableHead className="text-right">利润率</TableHead>
              <TableHead>风险</TableHead>
              <TableHead>判定</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((row) => (
              <TableRow key={row.category} className={row.affected ? "bg-amber-400/[0.04]" : undefined}>
                <TableCell className="font-semibold text-white">
                  <div className="flex items-center gap-2">
                    {row.category_name}
                    {row.affected && (
                      <TriangleAlert className="h-3.5 w-3.5 text-amber-300" />
                    )}
                  </div>
                </TableCell>
                <TableCell className="tabular text-right">
                  {pct(row.tariff_before)} → {pct(row.tariff_after)}
                </TableCell>
                <TableCell className="tabular text-right">
                  ${row.duty_before.toFixed(2)} → ${row.duty_after.toFixed(2)}
                </TableCell>
                <TableCell className="tabular text-right">
                  {row.margin_before.toFixed(1)}% →{" "}
                  <span className={row.margin_delta_pct < 0 ? "text-red-300" : "text-emerald-300"}>
                    {row.margin_after.toFixed(1)}%
                  </span>
                </TableCell>
                <TableCell>
                  <Badge tone={row.risk_after === "high" ? "red" : row.risk_after === "medium" ? "amber" : "green"}>
                    {row.risk_before} → {row.risk_after}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge tone={verdictTone(row.verdict_after)}>
                    {row.verdict_before} → {row.verdict_after}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button size="sm" variant="outline" onClick={() => onEnterTrade(row)}>
                    <Ship className="h-3.5 w-3.5" />
                    带入决策
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </GlassCard>
  );
}

function Stat({
  label,
  value,
  tone,
  mono = false,
}: {
  label: string;
  value: string;
  tone: "green" | "amber" | "red" | "cyan";
  mono?: boolean;
}) {
  const color = {
    green: "text-emerald-300",
    amber: "text-amber-300",
    red: "text-red-300",
    cyan: "text-accent",
  }[tone];
  return (
    <div className="glass-inset p-3">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className={`tabular mt-1 text-lg font-extrabold ${mono ? "font-mono" : ""} ${color}`}>
        {value}
      </p>
    </div>
  );
}

function pct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}
