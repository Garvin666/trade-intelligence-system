import {
  BadgeCheck,
  Banknote,
  FileCheck2,
  ListChecks,
  Scale,
  Ship,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import type { ReactNode } from "react";
import type { TradeDecision } from "@/shared/api/types";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { GlassCard } from "@/shared/ui/glass-card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

/** 缺失值统一占位：null/undefined/空串/后端 "--" 均视为"未取到"，避免答辩时误读为数据异常 */
export const UNFETCHED = "未取到";

export function showValue(value: unknown): string {
  if (value === undefined || value === null) return UNFETCHED;
  const text = String(value);
  if (text === "" || text === "--") return UNFETCHED;
  return text;
}

export function TradeResultDetail({ result }: { result: TradeDecision }) {
  const preflight = (result.preflight as Record<string, unknown> | undefined) ?? {};
  const osint = (result.osint as Record<string, unknown> | undefined) ?? {};
  const preflightItems = Array.isArray(preflight.items) ? preflight.items : [];
  const logistics = Array.isArray(result.logistics) ? result.logistics : [];
  const sentimentLanguages = Array.isArray(result.sentiment_languages)
    ? result.sentiment_languages
    : [];
  const conflictSignals = Array.isArray(result.conflict_signals)
    ? result.conflict_signals
    : [];
  const osintChecks = Array.isArray(osint.checks)
    ? (osint.checks as unknown[])
    : [];

  return (
    <div className="grid gap-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <Section
          icon={Scale}
          title="到岸成本与政策"
          items={[
            ["到岸成本", landedCost(result.best_landed_cost_usd)],
            ["单件关税", landedCost(result.duty_usd_per_unit)],
            ["成本冲击", result.landed_cost_increase_pct != null ? `${Number(result.landed_cost_increase_pct).toFixed(1)}%` : UNFETCHED],
            ["政策调整", result.policy_cost_adjustment_pct != null ? `${(Number(result.policy_cost_adjustment_pct) * 100).toFixed(1)}%` : UNFETCHED],
          ]}
        >
          <p className="text-sm text-slate-300">{String(result.risk_message ?? "")}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {((result.policy_actions ?? []) as unknown[]).map((action, index) => (
              <Badge key={index} tone="amber">
                {String(action)}
              </Badge>
            ))}
          </div>
          {Array.isArray(result.warnings) && result.warnings.length > 0 && (
            <div className="mt-2 grid gap-1 text-[11px] text-slate-500">
              {(result.warnings as unknown[]).map((warning, index) => (
                <p key={index}>- {String(warning)}</p>
              ))}
            </div>
          )}
        </Section>

        <Section
          icon={FileCheck2}
          title="合规与 IP"
          items={[
            ["准入评分", showValue(result.feasibility_score)],
            ["合规成本", result.compliance_total_usd != null ? `$${Number(result.compliance_total_usd).toFixed(2)}` : UNFETCHED],
            ["IP 风险", showValue(result.ip_risk_level)],
          ]}
        >
          <p className="text-sm text-slate-300">
            {String(result.compliance_recommendation ?? "")}
          </p>
          <p className="mt-2 text-sm text-slate-300">{String(result.ip_recommendation ?? "")}</p>
        </Section>
      </div>

      <Section
        icon={Ship}
        title="物流三方案"
        items={[]}
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>方案</TableHead>
              <TableHead>到岸成本</TableHead>
              <TableHead>时效</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logistics.map((row, index) => (
              <TableRow key={index}>
                <TableCell className="font-semibold text-white">
                  {String(row.logistics_name ?? row.name ?? "--")}
                </TableCell>
                <TableCell className="tabular">
                  ${Number(row.landed_cost_usd ?? 0).toFixed(2)}
                </TableCell>
                <TableCell className="tabular">
                  {String(row.delivery_days ?? row.timeline ?? "--")}
                </TableCell>
              </TableRow>
            ))}
            {!logistics.length && (
              <TableRow>
                <TableCell colSpan={3} className="text-center text-slate-500">
                  暂无物流明细
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Section
          icon={ListChecks}
          title="卖前体检"
          items={[
            ["体检评分", showValue(preflight.score)],
            ["是否就绪", preflight.ready === true ? "是" : "否"],
          ]}
        >
          {preflightItems.length === 0 ? (
            <p className="text-xs text-slate-500">暂无体检明细数据（该组合演示数据缺失）。</p>
          ) : (
            <div className="grid gap-1.5">
              {preflightItems.map((item, index) => {
                const name = showValue(item.name ?? item.check);
                const status = showValue(item.status);
                return (
                  <div key={index} className="glass-soft p-2 text-xs text-slate-300">
                    <span className="font-semibold">
                      {name === UNFETCHED ? "未命名检查项" : name}
                    </span>
                    {"："}
                    {status === UNFETCHED ? (
                      <span className="italic text-slate-500">未取到状态</span>
                    ) : (
                      status
                    )}
                    {item.message ? `（${String(item.message)}）` : ""}
                  </div>
                );
              })}
            </div>
          )}
        </Section>

        <Section
          icon={BadgeCheck}
          title="舆情与绿色贸易"
          items={[
            ["情绪分", showValue(result.sentiment_avg_score)],
            ["总体评价", showValue(result.sentiment_overall)],
            ["CBAM 暴露", showValue(result.green_exposure)],
            ["碳成本", result.green_carbon_cost_usd != null ? `$${Number(result.green_carbon_cost_usd).toFixed(2)}` : UNFETCHED],
          ]}
        >
          {sentimentLanguages.length > 0 && (
            <p className="text-xs text-slate-500">
              覆盖语种：{sentimentLanguages.map((item) => String(item.language_name ?? item.language)).join(" / ")}
            </p>
          )}
        </Section>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Section
          icon={Wallet}
          title="融资与尽调"
          items={[
            ["融资就绪分", showValue(result.financing_ready_score)],
            ["融资档位", showValue(result.financing_level)],
            ["尽调就绪", showValue(osint.readiness)],
          ]}
        >
          {osintChecks.length === 0 ? (
            <p className="text-xs text-slate-500">暂无尽调明细数据（该组合演示数据缺失）。</p>
          ) : (
            <div className="grid gap-1.5">
              {osintChecks.slice(0, 5).map((rawCheck, index) => {
                const check = rawCheck as Record<string, unknown>;
                const title = showValue(check.title ?? check.name);
                const status = showValue(check.status ?? check.note);
                return (
                  <p key={index} className="text-xs text-slate-400">
                    - {title === UNFETCHED ? "未命名检查项" : title}：
                    {status === UNFETCHED ? (
                      <span className="italic text-slate-500">未取到状态</span>
                    ) : (
                      status
                    )}
                  </p>
                );
              })}
            </div>
          )}
        </Section>

        <Section
          icon={ShieldCheck}
          title="冲突裁决"
          items={[
            ["冲突级别", showValue(result.conflict_level)],
            ["裁决建议", showValue(result.conflict_decision)],
            ["分数变化", showValue(result.conflict_score_change)],
          ]}
        >
          {conflictSignals.length === 0 ? (
            <p className="text-xs text-slate-500">暂无冲突信号数据（该组合演示数据缺失）。</p>
          ) : (
            <div className="grid gap-1.5">
              {conflictSignals.slice(0, 6).map((signal, index) => (
                <p key={index} className="text-xs text-slate-400">
                  {showValue(signal.name ?? signal.code)}：{showValue(signal.score)}
                </p>
              ))}
            </div>
          )}
        </Section>
      </div>

      <Section
        icon={Banknote}
        title="汇率敏感性"
        items={[]}
      >
        <div className="grid gap-2 sm:grid-cols-3">
          {renderFxSensitivity(result.fx_sensitivity)}
        </div>
      </Section>
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  items,
  children,
}: {
  icon: typeof Scale;
  title: string;
  items: Array<[string, string]>;
  children?: ReactNode;
}) {
  return (
    <GlassCard title={title}>
      {items.length > 0 && (
        <div className="mb-3 grid grid-cols-2 gap-2">
          {items.map(([label, value]) => (
            <div key={label} className="glass-inset p-2.5">
              <p className="text-[11px] font-semibold text-slate-500">{label}</p>
              <p
                className={cn(
                  "tabular mt-0.5 text-sm",
                  value === UNFETCHED
                    ? "font-medium text-slate-600 italic"
                    : "font-bold text-accent",
                )}
              >
                {value}
              </p>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-start gap-2">
        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </GlassCard>
  );
}

function landedCost(value: unknown): string {
  if (value === undefined || value === null) return UNFETCHED;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return UNFETCHED;
  return `$${numeric.toFixed(2)}`;
}

function renderFxSensitivity(value: unknown) {
  if (typeof value !== "object" || value === null) {
    return <p className="text-xs text-slate-500">暂无汇率敏感性数据（该组合演示数据缺失）。</p>;
  }
  const record = value as Record<string, unknown>;
  const entries = Object.entries(record);
  if (!entries.length) {
    return <p className="text-xs text-slate-500">暂无汇率敏感性数据（该组合演示数据缺失）。</p>;
  }
  return (
    <>
      {entries.map(([key, item]) => {
        const raw =
          typeof item === "object" && item !== null
            ? (item as Record<string, unknown>).margin_pct ??
              (item as Record<string, unknown>).margin
            : item;
        const margin = showValue(raw);
        return (
          <div key={key} className="glass-soft p-3">
            <p className="text-[11px] font-semibold text-slate-500">{key}</p>
            {margin === UNFETCHED ? (
              <p className="mt-1 text-xs italic text-slate-500">未取到数据</p>
            ) : (
              <p className="tabular mt-1 text-sm font-bold text-emerald-300">{margin}%</p>
            )}
          </div>
        );
      })}
      {entries.some(([, item]) => {
        const raw =
          typeof item === "object" && item !== null
            ? (item as Record<string, unknown>).margin_pct ??
              (item as Record<string, unknown>).margin
            : item;
        return showValue(raw) === UNFETCHED;
      }) && (
        <p className="col-span-full text-[11px] text-slate-600">
          注：汇率敏感性为演示指标，部分档位未取到数据。
        </p>
      )}
    </>
  );
}
