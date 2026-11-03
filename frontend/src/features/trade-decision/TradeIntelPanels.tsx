import { useEffect, useMemo, useState } from "react";
import { MapPin, RefreshCw, Trophy } from "lucide-react";
import { fetchTradeDecision } from "@/shared/api/client";
import { useMarketCompare, useTradeCatalog } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import {
  categoryName,
  fallbackCategoryOptions,
  marketName,
} from "@/shared/lib/names";
import { computeDecisionScore, verdictTone } from "@/shared/lib/tradeVerdict";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
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

const ALL_MARKETS = [
  "us", "eu", "sea", "jp", "ca", "au", "uk", "kr", "de", "fr", "vn", "ru", "hu", "ae", "mx",
];

interface RankedMarket {
  market: string;
  marketName: string;
  score: number;
  verdict: string;
  marginPct: number;
  riskLevel: string;
  landedCostUsd: number;
}

export function TradeMarketComparePanel() {
  const [category, setCategory] = useState("cn_latiao");
  const { data: catalog } = useTradeCatalog();
  const categoryOptions = useMemo(() => {
    const items = catalog?.data?.categories ?? [];
    if (items.length) {
      return items
        .filter((item) => item.key)
        .map((item) => ({ value: item.key, label: String(item.label ?? categoryName(item.key)) }));
    }
    return fallbackCategoryOptions;
  }, [catalog]);
  const { data, isLoading } = useMarketCompare({ category });
  const setSelectionDraft = useTradeIntelStore((state) => state.setSelectionDraft);
  const [ranking, setRanking] = useState<{
    loading: boolean;
    error: string | null;
    rows: RankedMarket[];
  }>({ loading: false, error: null, rows: [] });

  const compareRows = useMemo(() => {
    const items = (data?.items ?? []) as Array<Record<string, unknown>>;
    const map: Record<string, Record<string, unknown>> = {};
    for (const row of items) map[String(row.market)] = row;
    return map;
  }, [data]);

  // 品类默认价格/成本（目录 basePrice + cost×7.15 换算 CNY）
  const defaults = useMemo(() => {
    const meta = (catalog?.data?.categories ?? []).find((item) => item.key === category) as
      | (Record<string, unknown> & { key: string })
      | undefined;
    const basePrice = Number(meta?.basePrice);
    const rawCost = Number(meta?.cost);
    return {
      price: Number.isFinite(basePrice) && basePrice > 0 ? basePrice : 32.9,
      cost: Number.isFinite(rawCost) && rawCost > 0 ? Math.round(rawCost * 7.15) : 88,
    };
  }, [catalog, category]);

  const runRanking = async () => {
    setRanking((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const results = await Promise.allSettled(
        ALL_MARKETS.map((market) =>
          fetchTradeDecision({
            category,
            market,
            unit_price_usd: defaults.price,
            procurement_cost_cny: defaults.cost,
          }),
        ),
      );
      const rows: RankedMarket[] = [];
      results.forEach((settled, index) => {
        if (settled.status !== "fulfilled") return;
        const payload = settled.value;
        const market = ALL_MARKETS[index];
        const verdict = computeDecisionScore(payload, {
          marketCompareRow: compareRows[market] ?? null,
        });
        rows.push({
          market,
          marketName: marketName(market),
          score: verdict.score,
          verdict: verdict.verdictLabel,
          marginPct: Number(payload.margin_pct ?? 0),
          riskLevel: String(payload.risk_level ?? "medium"),
          landedCostUsd: Number(payload.best_landed_cost_usd ?? 0),
        });
      });
      rows.sort((a, b) => b.score - a.score);
      setRanking({ loading: false, error: null, rows: rows.slice(0, 4) });
    } catch (err) {
      setRanking({
        loading: false,
        error: err instanceof Error ? err.message : "市场择优计算失败",
        rows: [],
      });
    }
  };

  useEffect(() => {
    // 延迟到回调中再触发 setState，避免在 effect 体内同步调用
    const timer = window.setTimeout(() => {
      void runRanking();
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category]);

  if (IS_OFFLINE) {
    return <GlassCard><p className="text-sm text-slate-400">市场对比需要在线后端。</p></GlassCard>;
  }

  const rows = (data?.items ?? []) as Array<Record<string, unknown>>;

  const pickMarket = (market: string) => {
    setSelectionDraft({
      category,
      market,
      price: defaults.price,
      procurement_cost_cny: defaults.cost,
      keyword: categoryName(category),
      fromMarketCard: true,
    });
  };

  return (
    <div className="grid gap-4">
      <GlassCard
        title="Top 4 推荐市场"
        description={"按品类即时测算 15 市场决策分，点击卡片切到「贸易决策」页签自动生成"}
        strong
      >
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Select
            value={category}
            onValueChange={setCategory}
            options={categoryOptions}
            className="w-56"
            ariaLabel="选择对比品类"
          />
          <Badge tone="neutral">售价 {"$" + defaults.price.toFixed(1)} · 采购 {defaults.cost} CNY</Badge>
          <Button variant="outline" size="sm" onClick={runRanking} disabled={ranking.loading}>
            <RefreshCw className={"h-3.5 w-3.5 " + (ranking.loading ? "animate-spin" : "")} />
            重算
          </Button>
        </div>
        {ranking.error && <p className="mb-3 text-xs text-red-300">{ranking.error}</p>}
        {ranking.rows.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {ranking.rows.map((item, index) => {
              const riskTone =
                item.riskLevel === "low" ? "green" : item.riskLevel === "medium" ? "amber" : "red";
              return (
                <button
                  key={item.market}
                  type="button"
                  onClick={() => pickMarket(item.market)}
                  className="glass-soft group cursor-pointer rounded-xl p-4 text-left transition-all hover:-translate-y-0.5 hover:border-cyan-300/40 hover:bg-white/[0.06]"
                  title={"选择 " + item.marketName + " 并在贸易决策页签自动生成"}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-sm font-bold text-white">
                      {index === 0 && <Trophy className="h-4 w-4 text-amber-300" />}
                      {item.marketName}
                    </span>
                    <Badge tone={verdictTone(item.verdict as "enter" | "trial" | "hold")}>
                      {item.verdict}
                    </Badge>
                  </div>
                  <p className="mt-2 flex items-baseline gap-1">
                    <span className="tabular text-2xl font-extrabold text-accent">{item.score}</span>
                    <span className="text-[11px] text-slate-500">决策分</span>
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-400">
                    <span>毛利 {item.marginPct.toFixed(1)}%</span>
                    <Badge tone={riskTone}>风险 {item.riskLevel}</Badge>
                    <span>到岸 {"$" + item.landedCostUsd.toFixed(2)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <MapPin className="h-4 w-4 text-accent/60" />
            {ranking.loading ? "正在测算 15 个市场…" : "暂无推荐，点击「重算」"}
          </p>
        )}
      </GlassCard>

      <GlassCard title="15 市场对比" description="按品类比较销量、竞争、价格与出口金额" strong>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Select
            value={category}
            onValueChange={setCategory}
            options={categoryOptions}
            className="w-56"
            ariaLabel="选择对比品类"
          />
          {isLoading && <Badge tone="cyan">加载中</Badge>}
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>市场</TableHead>
              <TableHead>平均销量</TableHead>
              <TableHead>竞争度</TableHead>
              <TableHead>价格中位数</TableHead>
              <TableHead>出口金额</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={String(row.market)}>
                <TableCell className="font-semibold text-white">
                  {String(row.market_name ?? marketName(String(row.market)))}
                </TableCell>
                <TableCell className="tabular">{num(row.avg_sales_volume)}</TableCell>
                <TableCell className="tabular">{num(row.avg_competition_index)}</TableCell>
                <TableCell className="tabular">{num(row.avg_price_median)}</TableCell>
                <TableCell className="tabular">{num(row.avg_export_value)}</TableCell>
              </TableRow>
            ))}
            {!rows.length && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-slate-500">暂无数据</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </GlassCard>
    </div>
  );
}

function num(value: unknown): string {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return String(value ?? "--");
}
