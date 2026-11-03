import { Gauge } from "lucide-react";
import type { VerdictResult } from "@/shared/lib/tradeVerdict";
import { STRATEGY_LABELS, verdictTone } from "@/shared/lib/tradeVerdict";
import { Badge } from "@/shared/ui/badge";
import { GlassCard } from "@/shared/ui/glass-card";

/**
 * 决策建议横幅：决策分 + 建议进入/小批试单/暂缓进入 + 依据 + 四维分量。
 * 移植自解析报告所述的"决策分 + getDecisionStatus"优势能力。
 */
export function VerdictBanner({ verdict }: { verdict: VerdictResult }) {
  const tone = verdictTone(verdict.verdict);
  const components = [
    { label: "需求", value: verdict.components.demand },
    { label: "利润", value: verdict.components.profit },
    { label: "现金", value: verdict.components.cash },
    { label: "风险", value: verdict.components.risk },
  ];

  return (
    <GlassCard
      title="决策建议"
      description={`综合 ${STRATEGY_LABELS[verdict.strategy]}策略的多维加权裁决（演示口径）`}
      strong
    >
      <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
        <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <div className="flex items-end gap-1">
            <span className="tabular text-5xl font-extrabold text-white">
              {verdict.score}
            </span>
            <span className="pb-1.5 text-sm text-slate-500">/ 100</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-cyan-600"
              style={{ width: `${Math.max(0, Math.min(100, verdict.score))}%` }}
            />
          </div>
          <Badge tone={tone} className="mt-1 px-3 py-1 text-xs">
            {verdict.verdictLabel}
          </Badge>
          <p className="text-[11px] text-slate-500">现金周期 {verdict.cashDays} 天（库存 45 + 账期 30 假设）</p>
        </div>

        <div className="grid gap-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {components.map((item) => (
              <div key={item.label} className="glass-inset p-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-slate-500">
                    {item.label}
                  </span>
                  <span className="tabular text-xs font-bold text-accent">
                    {item.value}
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-cyan-400/70"
                    style={{ width: `${Math.max(0, Math.min(100, item.value))}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="grid gap-1.5">
            {verdict.reasons.map((reason, index) => (
              <p key={index} className="flex items-start gap-2 text-xs text-slate-300">
                <Gauge className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent/70" />
                {reason}
              </p>
            ))}
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
