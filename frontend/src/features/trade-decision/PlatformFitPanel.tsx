import { useMemo, useState } from "react";
import { Store } from "lucide-react";
import { useTradeCatalog } from "@/shared/api/hooks";
import type { CatalogOption } from "@/shared/api/types";
import { calculateTradeScenario } from "@/shared/lib/tradeScenario";
import {
  categoryName,
  fallbackCategoryOptions,
  fallbackMarketOptions,
  marketName,
} from "@/shared/lib/names";
import { Badge } from "@/shared/ui/badge";
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

interface PlatformRow {
  key: string;
  label: string;
  commission: number;
  adDefault: number;
  netProfit: number;
  fit: number;
  risk: number;
  note: string;
}

/**
 * 平台适配排行（移植报告所述"平台适配排行"优势）：按各平台佣金/默认广告测算净利润排序。
 * 平台字典来自 /api/catalog 的 platforms（6 平台），佣金与适配度为演示参数。
 */
export function PlatformFitPanel() {
  const { data: catalog } = useTradeCatalog();
  const [category, setCategory] = useState("cn_latiao");
  const [market, setMarket] = useState("us");

  const categoryOptions = useMemo(() => {
    const items = catalog?.data?.categories ?? [];
    if (items.length) return items.map((item) => ({ value: item.key, label: String(item.label ?? categoryName(item.key)) }));
    return fallbackCategoryOptions;
  }, [catalog]);

  const marketOptions = useMemo(() => {
    const items = catalog?.data?.markets ?? [];
    if (items.length) return items.map((item) => ({ value: item.key, label: String(item.label ?? marketName(item.key)) }));
    return fallbackMarketOptions;
  }, [catalog]);

  const platforms = useMemo(() => {
    const items = (catalog?.data?.platforms ?? []) as CatalogOption[];
    return items.filter((item) => item.key);
  }, [catalog]);

  const categoryMeta = useMemo(() => {
    const found = (catalog?.data?.categories ?? []).find((item) => item.key === category);
    return found ?? null;
  }, [catalog, category]);

  const price = useMemo(() => {
    const base = Number((categoryMeta as Record<string, unknown> | undefined)?.basePrice);
    return Number.isFinite(base) && base > 0 ? base : 32.9;
  }, [categoryMeta]);

  const cost = useMemo(() => {
    const raw = Number((categoryMeta as Record<string, unknown> | undefined)?.cost);
    // 目录成本按 USD 计，换算为 CNY 采购成本（×7.15）
    return Number.isFinite(raw) && raw > 0 ? Math.round(raw * 7.15) : 88;
  }, [categoryMeta]);

  const rows = useMemo<PlatformRow[]>(() => {
    const list: PlatformRow[] = [];
    for (const platform of platforms) {
      const meta = platform as Record<string, unknown>;
      const commission = toNum(meta.commission, 0.1);
      const adDefault = toNum(meta.adDefault, 0.12);
      const fitMap = (meta.fit ?? {}) as Record<string, unknown>;
      const fit = toNum(fitMap[market], 50);
      const risk = toNum(meta.risk, 50);
      const scenario = calculateTradeScenario({
        category,
        market,
        unit_price_usd: price,
        procurement_cost_cny: cost,
        quantity: 300,
        ad_rate: adDefault,
        return_rate: 0.03,
        inventory_days: 45,
        fx_rate: 7.15,
        platform_commission_rate: commission,
      });
      list.push({
        key: String(platform.key),
        label: String(meta.label ?? platform.key),
        commission,
        adDefault,
        netProfit: scenario.net_profit,
        fit,
        risk,
        note: String(meta.note ?? ""),
      });
    }
    return list.sort((a, b) => b.netProfit - a.netProfit);
  }, [category, cost, market, platforms, price]);

  return (
    <GlassCard title="平台适配排行" description="按平台佣金与默认广告测算净利润排序（演示参数）" strong>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Select value={category} onValueChange={setCategory} options={categoryOptions} className="w-52" ariaLabel="选择品类" />
        <Select value={market} onValueChange={setMarket} options={marketOptions} className="w-44" ariaLabel="选择市场" />
        <Badge tone="neutral">售价 ${price.toFixed(1)} · 采购 {cost} CNY</Badge>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>平台</TableHead>
            <TableHead>佣金</TableHead>
            <TableHead>默认广告</TableHead>
            <TableHead>净利润（300 件）</TableHead>
            <TableHead>市场适配</TableHead>
            <TableHead>平台风险</TableHead>
            <TableHead>说明</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.key}>
              <TableCell className="font-semibold text-white">
                <span className="flex items-center gap-1.5">
                  <Store className="h-3.5 w-3.5 text-accent" />
                  {row.label}
                </span>
              </TableCell>
              <TableCell className="tabular">{(row.commission * 100).toFixed(1) + "%"}</TableCell>
              <TableCell className="tabular">{(row.adDefault * 100).toFixed(1) + "%"}</TableCell>
              <TableCell className="tabular font-bold" style={{ color: row.netProfit >= 0 ? "#6ee7b7" : "#fca5a5" }}>
                {"$" + row.netProfit.toFixed(0)}
              </TableCell>
              <TableCell className="tabular">{row.fit}</TableCell>
              <TableCell className="tabular">{row.risk}</TableCell>
              <TableCell className="max-w-[240px] text-xs text-slate-400">{row.note || "--"}</TableCell>
            </TableRow>
          ))}
          {!rows.length && (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-slate-500">暂无平台数据</TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </GlassCard>
  );
}

function toNum(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
