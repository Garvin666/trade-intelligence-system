import { useMemo, useState } from "react";
import { Activity, Save } from "lucide-react";
import type { TradeDecision } from "@/shared/api/types";
import {
  applyTradeAction,
  buildScenarioVerdict,
  TRADE_ACTIONS,
  type TradeActionId,
  type TradeSandboxInputs,
  type TradeStrategy,
  verdictTone,
} from "@/shared/lib/tradeVerdict";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

interface InteractionEntry {
  id: string;
  label: string;
  scoreDelta: number;
  profitDelta: number;
  riskDelta: number;
  time: string;
}

const MAX_LOG = 6;

export function TradeScenarioSandbox({
  result,
  category,
  market,
  strategy = "balanced",
}: {
  result: TradeDecision;
  category: string;
  market: string;
  strategy?: TradeStrategy;
}) {
  const addScenario = useTradeIntelStore((state) => state.addScenario);
  const [unitPrice, setUnitPrice] = useState(Number(result.unit_price_usd ?? 0));
  const [procurementCost, setProcurementCost] = useState(Number(result.procurement_cost_cny ?? 0));
  const [quantity, setQuantity] = useState(300);
  const [adRate, setAdRate] = useState(0.12);
  const [returnRate, setReturnRate] = useState(0.03);
  const [inventoryDays, setInventoryDays] = useState(45);
  const [fxRate, setFxRate] = useState(7.15);
  const [log, setLog] = useState<InteractionEntry[]>([]);

  const inputs: TradeSandboxInputs = useMemo(
    () => ({
      unit_price_usd: unitPrice,
      procurement_cost_cny: procurementCost,
      quantity,
      ad_rate: adRate,
      return_rate: returnRate,
      inventory_days: inventoryDays,
      fx_rate: fxRate,
      landed_cost_usd: Number(result.best_landed_cost_usd ?? 0),
    }),
    [adRate, fxRate, inventoryDays, procurementCost, quantity, result, returnRate, unitPrice],
  );

  const current = useMemo(
    () => buildScenarioVerdict(result, inputs, { strategy }),
    [inputs, result, strategy],
  );
  const scenario = current.scenario;
  const verdict = current.verdict;

  const runAction = (actionId: TradeActionId) => {
    const meta = TRADE_ACTIONS.find((item) => item.id === actionId);
    if (!meta) return;
    const before = buildScenarioVerdict(result, inputs, { strategy });
    const next = applyTradeAction(inputs, actionId);
    const after = buildScenarioVerdict(result, next, { strategy });
    setUnitPrice(next.unit_price_usd);
    setProcurementCost(next.procurement_cost_cny);
    setAdRate(next.ad_rate);
    setReturnRate(next.return_rate);
    setInventoryDays(next.inventory_days);
    setFxRate(next.fx_rate);
    setLog((prev) =>
      [
        {
          id: makeId(),
          label: meta.label,
          scoreDelta: round1(after.verdict.score - before.verdict.score),
          profitDelta: round0(after.scenario.net_profit - before.scenario.net_profit),
          riskDelta: round1(after.verdict.components.risk - before.verdict.components.risk),
          time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
        },
        ...prev,
      ].slice(0, MAX_LOG),
    );
  };

  const save = () => {
    addScenario({
      id: makeId(),
      label: String(result.category_name ?? category) + " × " + String(result.market_name ?? market),
      category,
      market,
      unit_price_usd: unitPrice,
      procurement_cost_cny: procurementCost,
      quantity,
      ad_rate: adRate,
      return_rate: returnRate,
      inventory_days: inventoryDays,
      fx_rate: fxRate,
      result,
      createdAt: new Date().toISOString(),
    });
  };

  const stressRows = useMemo(() => {
    const tiers: Array<{ label: string; tone: "green" | "neutral" | "red"; input: TradeSandboxInputs }> = [
      {
        label: "乐观",
        tone: "green",
        input: {
          ...inputs,
          unit_price_usd: round2(inputs.unit_price_usd * 1.05),
          ad_rate: Math.max(0.02, round2(inputs.ad_rate - 0.02)),
          return_rate: Math.max(0.005, round2(inputs.return_rate - 0.01)),
        },
      },
      { label: "基准", tone: "neutral", input: inputs },
      {
        label: "承压",
        tone: "red",
        input: {
          ...inputs,
          unit_price_usd: round2(inputs.unit_price_usd * 0.92),
          procurement_cost_cny: round2(inputs.procurement_cost_cny * 1.1),
          ad_rate: round2(inputs.ad_rate + 0.03),
          return_rate: round2(inputs.return_rate + 0.03),
        },
      },
    ];
    return tiers.map((tier) => {
      const row = buildScenarioVerdict(result, tier.input, { strategy });
      return {
        label: tier.label,
        tone: tier.tone,
        profit: row.scenario.net_profit,
        margin: row.scenario.margin_pct,
        verdictLabel: row.verdict.verdictLabel,
        verdictTone: verdictTone(row.verdict.verdict),
        risk: row.verdict.components.risk,
      };
    });
  }, [inputs, result, strategy]);

  return (
    <GlassCard title="方案沙盘" description="数量、广告、退货、库存与汇率假设 · 一键动作 + 压力测试（前端演示口径）">
      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        <div className="grid gap-4">
          <div className="grid gap-2">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400">
              <Activity className="h-3.5 w-3.5 text-accent" />
              一键动作
            </p>
            <div className="flex flex-wrap gap-2">
              {TRADE_ACTIONS.map((action) => (
                <Button
                  key={action.id}
                  variant="outline"
                  size="sm"
                  title={action.description}
                  onClick={() => runAction(action.id)}
                >
                  {action.label}
                </Button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <NumberField label="售价 USD" value={unitPrice} onChange={setUnitPrice} step={0.1} />
            <NumberField label="采购成本 CNY" value={procurementCost} onChange={setProcurementCost} step={1} />
            <NumberField label="首批数量" value={quantity} onChange={setQuantity} step={50} />
            <NumberField label="广告费率 %" value={adRate * 100} onChange={(value) => setAdRate(value / 100)} step={0.5} />
            <NumberField label="退货率 %" value={returnRate * 100} onChange={(value) => setReturnRate(value / 100)} step={0.5} />
            <NumberField label="库存天数" value={inventoryDays} onChange={setInventoryDays} step={5} />
            <NumberField label="汇率" value={fxRate} onChange={setFxRate} step={0.05} />
            <div className="flex items-end">
              <Button variant="secondary" className="w-full" onClick={save}>
                <Save className="h-4 w-4" />
                保存方案
              </Button>
            </div>
          </div>
        </div>
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Metric label="营收" value={"$" + scenario.revenue.toFixed(0)} />
            <Metric label="净利润" value={"$" + scenario.net_profit.toFixed(0)} tone={scenario.net_profit >= 0 ? "green" : "red"} />
            <Metric label="净利率" value={scenario.margin_pct.toFixed(1) + "%"} tone={scenario.margin_pct >= 15 ? "green" : "amber"} />
            <Metric label="单位贡献" value={"$" + scenario.contribution.toFixed(2)} />
            <Metric label="盈亏平衡件数" value={Number.isFinite(scenario.break_even_units) ? String(scenario.break_even_units) : "无限"} />
            <Metric label="现金周期" value={scenario.cash_days + " 天"} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={verdictTone(verdict.verdict)}>决策：{verdict.verdictLabel}</Badge>
            <Badge tone="cyan">决策分 {verdict.score}</Badge>
            <Badge tone="neutral">现金 {verdict.cashDays} 天</Badge>
          </div>

          {log.length > 0 && (
            <div className="grid gap-1.5">
              <p className="text-[11px] font-semibold text-slate-400">交互日志（最多 {MAX_LOG} 条）</p>
              {log.map((entry) => (
                <div key={entry.id} className="glass-soft flex flex-wrap items-center gap-2 p-2 text-xs">
                  <span className="font-semibold text-white">{entry.label}</span>
                  <DeltaBadge label="决策分" value={entry.scoreDelta} />
                  <DeltaBadge label="净利润" value={entry.profitDelta} prefix="$" />
                  <DeltaBadge label="风险" value={entry.riskDelta} invert />
                  <span className="ml-auto text-[10px] text-slate-500">{entry.time}</span>
                </div>
              ))}
            </div>
          )}

          <div>
            <p className="mb-2 text-[11px] font-semibold text-slate-400">压力测试（乐观 / 基准 / 承压）</p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>档位</TableHead>
                  <TableHead>净利润</TableHead>
                  <TableHead>净利率</TableHead>
                  <TableHead>决策建议</TableHead>
                  <TableHead>风险分</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stressRows.map((row) => (
                  <TableRow key={row.label}>
                    <TableCell className="font-semibold text-white">{row.label}</TableCell>
                    <TableCell
                      className="tabular"
                      style={{ color: row.tone === "neutral" ? undefined : row.tone === "green" ? "#6ee7b7" : "#fca5a5" }}
                    >
                      {"$" + row.profit.toFixed(0)}
                    </TableCell>
                    <TableCell className="tabular">{row.margin.toFixed(1) + "%"}</TableCell>
                    <TableCell>
                      <Badge tone={row.verdictTone}>{row.verdictLabel}</Badge>
                    </TableCell>
                    <TableCell className="tabular">{row.risk}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

function DeltaBadge({
  label,
  value,
  prefix = "",
  invert = false,
}: {
  label: string;
  value: number;
  prefix?: string;
  invert?: boolean;
}) {
  const up = invert ? value < 0 : value >= 0;
  const tone = value === 0 ? "neutral" : up ? "green" : "red";
  const sign = value > 0 ? "+" : "";
  return (
    <Badge tone={tone}>
      {label} {sign}{prefix}{value}
    </Badge>
  );
}

function NumberField({
  label,
  value,
  onChange,
  step,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step: number;
}) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-semibold text-slate-400">{label}</span>
      <input
        type="number"
        value={value}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
        className="glass-inset focus-ring h-10 w-full px-3 text-sm"
      />
    </label>
  );
}

function Metric({
  label,
  value,
  tone = "cyan",
}: {
  label: string;
  value: string;
  tone?: "green" | "red" | "amber" | "cyan";
}) {
  const color = {
    green: "text-emerald-300",
    red: "text-red-300",
    amber: "text-amber-300",
    cyan: "text-accent",
  }[tone];
  return (
    <div className="glass-inset p-3">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className={"tabular mt-1 text-lg font-extrabold " + color}>{value}</p>
    </div>
  );
}

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

function round0(value: number): number {
  return Math.round(value);
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return String(Date.now()) + "-" + Math.random().toString(36).slice(2, 10);
}